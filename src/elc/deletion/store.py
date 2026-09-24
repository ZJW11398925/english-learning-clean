"""BF-05 source-aware deletion — the durable executor (every statement).

The bounded context's write face for *removals*: this module is where the SQL
lives, and it is the only module in the tree that carries a ``DELETE FROM``
against another domain's table. The ordinary create/update verbs stay with
their own stores; deletion is a cross-cutting operation (a conversation's
removal spans conversation, learning, teaching, relationship and runtime
rows), so its statements have one home instead of a delete method grafted
onto a dozen packages.

What the faces mean:

- :meth:`SqliteDeletionStore.execute` runs one :class:`DeletionRequest` to
  completion **in one short transaction** — the durable half of §18's
  "Deletion 的最低语义", and the place SEC-028's immediacy is satisfied
  (unfinished projection jobs are removed inside this transaction, not at the
  next startup);
- :meth:`SqliteDeletionStore.tombstone_ledger` and
  :meth:`SqliteDeletionStore.list_tombstones` are the §24 reads;
- :meth:`SqliteDeletionStore.table_names` is what §23's sweep guard reads.

**Order is the foreign keys'.** Every table is deleted children-first: a
``NO ACTION`` constraint under ``PRAGMA foreign_keys=ON`` is checked at the
statement, so "delete the parents and hope" is not a strategy — it is an
error. The declared order lives in elc/deletion/types.py and a probe replays
a full sweep against a real database with foreign keys on.

**Rebuild is not here.** §18's last clauses (LearnerState rebuild, projection
rebuild, index rebuild) are calls into the faces that already compute those
projections — ``rebuild_learner_state``, ``recompute_schedule_item`` and the
CP4 EPISODE executor — and they live in elc/deletion/controller.py, because a
rebuild is not SQL and must not become a second implementation of one
(TASK-OPI-b99560d4-….19: "重建一律调用既有面…不得另建平行机制"). This
module's job ends at handing the controller the keys whose sources moved
(``affected_targets`` / ``affected_episodes``).

**What is deliberately absent.** No embedding or retrieval-index table is
touched, because V1 has none (the contract's "indexes/embeddings deleted or
rebuilt" has no storage to act on, and the absence is registered rather than
simulated). No persona definition row is touched, because V1's app.db holds
none. No remote provider call is made, ever — that judgement belongs to
elc/deletion/plan.py's ``plan_external_deletion`` and is a word, not a wire.

All SQL is fixed literal text with bound parameters. The only generated SQL is
a run of ``?`` placeholders inside an ``IN (…)`` clause whose *values* are
bound (the elc/teaching/store.py precedent); no identifier, predicate or
table name is ever assembled from a runtime value — a table name reaches a
statement only as a lookup key into a literal mapping.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable, Mapping, Sequence, TypeVar

from elc.deletion.plan import (
    ENTITY_FIELD_SEPARATOR,
    UnknownTableError,
    assert_known_tables,
    entity_hash_for,
    tombstone_id_for,
)
from elc.deletion.types import (
    ALL_USER_DATA_SWEPT_TABLES,
    DELETION_POLICY_VERSION,
    LEARNING_HISTORY_SWEPT_TABLES,
    PROFILE_FIELD_ENTITY_KIND,
    RETAINED_TABLES,
    SWEPT_TABLES,
    DeletionExecution,
    DeletionRequest,
    DeletionScope,
    EpisodeRebuildKey,
    TableTally,
    TargetKey,
    TombstoneRecord,
)
from elc.planner.ledger import LedgerKeyType, ObligationScope
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = ["SqliteDeletionStore", "StaleDeletionStoreError"]

T = TypeVar("T")

#: The §24 ledger, migration 0014 (the only table this module creates rows in
#: besides the removals it performs).
TOMBSTONE_TABLE = "deletion_tombstone"

#: The §22.1 queue's two unfinished states — what SEC-028 removes inside the
#: deletion transaction. The five words are frozen by migration 0002 and this
#: cut adds none (TASK-OPI-b99560d4-….19: "不新增状态词").
_UNFINISHED_JOB_STATES = ("PENDING", "FAILED_RETRYABLE")

#: table → ``SELECT rowid, <identity columns…> FROM <table>``. One literal per
#: table; the identity columns are the ones §24's opaque identity is derived
#: from, and ``rowid`` is what the paired delete keys on (an identity may be
#: composite, a rowid never is).
_SURFACE_SELECT: Mapping[str, str] = {
    "active_teaching_lock": (
        "SELECT rowid, conversation_id FROM active_teaching_lock"
    ),
    "analysis_artifact": "SELECT rowid, analysis_id FROM analysis_artifact",
    "assistant_turn": "SELECT rowid, assistant_turn_id FROM assistant_turn",
    "attempt_evaluation_record": (
        "SELECT rowid, attempt_evaluation_id FROM attempt_evaluation_record"
    ),
    "attempt_record": "SELECT rowid, attempt_id FROM attempt_record",
    "conversation": "SELECT rowid, conversation_id FROM conversation",
    "decision_cycle": "SELECT rowid, decision_cycle_id FROM decision_cycle",
    "disclosure_policy": (
        "SELECT rowid, disclosure_policy_id FROM disclosure_policy"
    ),
    "episode": "SELECT rowid, episode_id FROM episode",
    "evidence_claim": "SELECT rowid, evidence_claim_id FROM evidence_claim",
    "evidence_commit": (
        "SELECT rowid, evidence_commit_id FROM evidence_commit"
    ),
    "evidence_group": "SELECT rowid, evidence_group_id FROM evidence_group",
    "evidence_watermark": "SELECT rowid, user_scope_id FROM evidence_watermark",
    "expression_need": "SELECT rowid, expression_need_id FROM expression_need",
    "gate_decision": "SELECT rowid, gate_decision_id FROM gate_decision",
    "gate_execution_status": (
        "SELECT rowid, gate_execution_status_id FROM gate_execution_status"
    ),
    "generation_action_intent": (
        "SELECT rowid, action_id FROM generation_action_intent"
    ),
    "goal_portfolio": "SELECT rowid, goal_portfolio_id FROM goal_portfolio",
    "input_envelope": "SELECT rowid, input_id FROM input_envelope",
    "interrupt_request": "SELECT rowid, input_id FROM interrupt_request",
    "learner_self_report": (
        "SELECT rowid, self_report_id FROM learner_self_report"
    ),
    "learner_target_state": (
        "SELECT rowid, user_scope_id, target_type, target_id,"
        " evidence_modality FROM learner_target_state"
    ),
    "learning_opportunity_record": (
        "SELECT rowid, learning_opportunity_id"
        " FROM learning_opportunity_record"
    ),
    "planner_constraint": "SELECT rowid, constraint_id FROM planner_constraint",
    "planner_decision": (
        "SELECT rowid, planner_decision_id FROM planner_decision"
    ),
    "planner_evaluation": (
        "SELECT rowid, planner_evaluation_id FROM planner_evaluation"
    ),
    "planner_execution_status": (
        "SELECT rowid, decision_cycle_id FROM planner_execution_status"
    ),
    "projection_job": "SELECT rowid, projection_id FROM projection_job",
    "provider_attempt": (
        "SELECT rowid, provider_attempt_id FROM provider_attempt"
    ),
    "relationship_memory": (
        "SELECT rowid, relationship_memory_id FROM relationship_memory"
    ),
    "review_event": "SELECT rowid, review_event_id FROM review_event",
    "runtime_decision_outcome": (
        "SELECT rowid, turn_id FROM runtime_decision_outcome"
    ),
    "schedule_item": "SELECT rowid, schedule_item_id FROM schedule_item",
    "session_focus": "SELECT rowid, session_focus_id FROM session_focus",
    "teaching_evidence_proposal": (
        "SELECT rowid, proposal_id FROM teaching_evidence_proposal"
    ),
    "teaching_moment": "SELECT rowid, moment_id FROM teaching_moment",
    "teaching_policy": (
        "SELECT rowid, teaching_policy_profile_id FROM teaching_policy"
    ),
    "turn_record": "SELECT rowid, turn_id FROM turn_record",
    "user_profile": "SELECT rowid, user_profile_id FROM user_profile",
    "user_turn": "SELECT rowid, user_turn_id FROM user_turn",
    # P8-3's PlanningLedger (migration 0016): the log's identity is its event
    # id, the row's is its key, an obligation's its own key.
    "coverage_obligation": (
        "SELECT rowid, obligation_key FROM coverage_obligation"
    ),
    "planning_ledger": (
        "SELECT rowid, ledger_key FROM planning_ledger"
    ),
    "planning_ledger_event": (
        "SELECT rowid, event_id FROM planning_ledger_event"
    ),
}

#: table → the delete head. An ``IN (…)`` run of bound rowids is appended;
#: everything before it is literal.
_DELETE_BY_ROWID: Mapping[str, str] = {
    "active_teaching_lock": "DELETE FROM active_teaching_lock WHERE rowid IN (",
    "analysis_artifact": "DELETE FROM analysis_artifact WHERE rowid IN (",
    "assistant_turn": "DELETE FROM assistant_turn WHERE rowid IN (",
    "attempt_evaluation_record": (
        "DELETE FROM attempt_evaluation_record WHERE rowid IN ("
    ),
    "attempt_record": "DELETE FROM attempt_record WHERE rowid IN (",
    "conversation": "DELETE FROM conversation WHERE rowid IN (",
    "decision_cycle": "DELETE FROM decision_cycle WHERE rowid IN (",
    "disclosure_policy": "DELETE FROM disclosure_policy WHERE rowid IN (",
    "episode": "DELETE FROM episode WHERE rowid IN (",
    "evidence_claim": "DELETE FROM evidence_claim WHERE rowid IN (",
    "evidence_commit": "DELETE FROM evidence_commit WHERE rowid IN (",
    "evidence_group": "DELETE FROM evidence_group WHERE rowid IN (",
    "evidence_watermark": "DELETE FROM evidence_watermark WHERE rowid IN (",
    "expression_need": "DELETE FROM expression_need WHERE rowid IN (",
    "gate_decision": "DELETE FROM gate_decision WHERE rowid IN (",
    "gate_execution_status": (
        "DELETE FROM gate_execution_status WHERE rowid IN ("
    ),
    "generation_action_intent": (
        "DELETE FROM generation_action_intent WHERE rowid IN ("
    ),
    "goal_portfolio": "DELETE FROM goal_portfolio WHERE rowid IN (",
    "input_envelope": "DELETE FROM input_envelope WHERE rowid IN (",
    "interrupt_request": "DELETE FROM interrupt_request WHERE rowid IN (",
    "learner_self_report": "DELETE FROM learner_self_report WHERE rowid IN (",
    "learner_target_state": "DELETE FROM learner_target_state WHERE rowid IN (",
    "learning_opportunity_record": (
        "DELETE FROM learning_opportunity_record WHERE rowid IN ("
    ),
    "planner_constraint": "DELETE FROM planner_constraint WHERE rowid IN (",
    "planner_decision": "DELETE FROM planner_decision WHERE rowid IN (",
    "planner_evaluation": "DELETE FROM planner_evaluation WHERE rowid IN (",
    "planner_execution_status": (
        "DELETE FROM planner_execution_status WHERE rowid IN ("
    ),
    "projection_job": "DELETE FROM projection_job WHERE rowid IN (",
    "provider_attempt": "DELETE FROM provider_attempt WHERE rowid IN (",
    "relationship_memory": "DELETE FROM relationship_memory WHERE rowid IN (",
    "review_event": "DELETE FROM review_event WHERE rowid IN (",
    "runtime_decision_outcome": (
        "DELETE FROM runtime_decision_outcome WHERE rowid IN ("
    ),
    "schedule_item": "DELETE FROM schedule_item WHERE rowid IN (",
    "session_focus": "DELETE FROM session_focus WHERE rowid IN (",
    "teaching_evidence_proposal": (
        "DELETE FROM teaching_evidence_proposal WHERE rowid IN ("
    ),
    "teaching_moment": "DELETE FROM teaching_moment WHERE rowid IN (",
    "teaching_policy": "DELETE FROM teaching_policy WHERE rowid IN (",
    "turn_record": "DELETE FROM turn_record WHERE rowid IN (",
    "user_profile": "DELETE FROM user_profile WHERE rowid IN (",
    "user_turn": "DELETE FROM user_turn WHERE rowid IN (",
    "coverage_obligation": (
        "DELETE FROM coverage_obligation WHERE rowid IN ("
    ),
    "planning_ledger": "DELETE FROM planning_ledger WHERE rowid IN (",
    "planning_ledger_event": (
        "DELETE FROM planning_ledger_event WHERE rowid IN ("
    ),
}

if set(_SURFACE_SELECT) != set(SWEPT_TABLES) or set(_DELETE_BY_ROWID) != set(
    SWEPT_TABLES
):
    raise RuntimeError(
        "elc.deletion.store's per-table literal maps and"
        " elc.deletion.types.SWEPT_TABLES have drifted apart — every swept"
        " table needs exactly one SELECT and one DELETE literal"
    )


class StaleDeletionStoreError(StaleEpochError):
    """This store's epoch is no longer the newest durable epoch."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


#: The durable constraint families a deletion can still hit once its order is
#: right, in the order they are looked for in sqlite's text. The names are
#: this module's (they are what the refusal means to a caller), never the
#: database's phrasing.
_CONSTRAINT_FAMILIES = ("FOREIGN KEY", "UNIQUE", "CHECK", "NOT NULL")


def _constraint_family(exc: sqlite3.IntegrityError) -> str:
    """Which durable rule refused the deletion, in this module's words.

    sqlite's message is **read**, never re-emitted: a ``DomainError.message``
    is this domain's vocabulary, so what a caller gets is the family it can
    act on.
    """

    text = str(exc)
    for family in _CONSTRAINT_FAMILIES:
        if family in text:
            return family
    return "UNKNOWN"


def _placeholders(count: int) -> str:
    """One ``?`` per value: the only SQL text this module ever generates."""

    return ", ".join("?" for _ in range(count))


def _us_join(parts: Iterable[object]) -> str:
    return ENTITY_FIELD_SEPARATOR.join(str(part) for part in parts)


def _decode_array(document: str) -> tuple[str, ...]:
    """One durable JSON array column, decoded (the relationship store's own
    ``_array_from_document`` convention: a ``sort_keys`` compact array)."""

    try:
        loaded = json.loads(document)
    except ValueError:
        return ()
    if not isinstance(loaded, list):
        return ()
    return tuple(str(item) for item in loaded)


@dataclass
class _Run:
    """The mutable accumulator one ``execute`` fills."""

    scope: DeletionScope
    deleted_at: str
    tallies: dict[str, int] = field(default_factory=dict)
    tombstoned: int = 0
    cancelled_projection_jobs: int = 0
    cancelled_provider_actions: int = 0
    sent_provider_actions: int = 0
    cleared_provenance_legs: int = 0
    affected_targets: list[TargetKey] = field(default_factory=list)
    affected_episodes: list[EpisodeRebuildKey] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, table: str, removed: int) -> None:
        if removed:
            self.tallies[table] = self.tallies.get(table, 0) + removed

    def execution(self) -> DeletionExecution:
        return DeletionExecution(
            scope=self.scope,
            deleted_at=self.deleted_at,
            tallies=tuple(
                TableTally(table=table, removed=count)
                for table, count in self.tallies.items()
                if count
            ),
            tombstoned=self.tombstoned,
            cancelled_projection_jobs=self.cancelled_projection_jobs,
            cancelled_provider_actions=self.cancelled_provider_actions,
            sent_provider_actions=self.sent_provider_actions,
            cleared_provenance_legs=self.cleared_provenance_legs,
            affected_targets=tuple(self.affected_targets),
            affected_episodes=tuple(self.affected_episodes),
            notes=tuple(self.notes),
        )


class SqliteDeletionStore:
    """Durable deletion over one app.db connection (§18–§24)."""

    def __init__(
        self, conn: sqlite3.Connection, fence: RuntimeEpochFence
    ) -> None:
        self._conn = conn
        self._fence = fence

    # -- epoch -------------------------------------------------------------

    def _require_current_epoch(self) -> None:
        row = self._conn.execute(
            "SELECT MAX(epoch) FROM runtime_epoch"
        ).fetchone()
        current = None if row is None or row[0] is None else int(row[0])
        if current is None or self._fence.current != current:
            raise StaleDeletionStoreError(
                f"deletion store epoch={self._fence.current} is not the newest"
                f" durable epoch={current}"
            )

    # -- reads -------------------------------------------------------------

    def table_names(self) -> Result[tuple[str, ...]]:
        """Every ordinary table in this database, ordered by name.

        ``sqlite_%`` internals are excluded: the guard in
        ``plan.assert_known_tables`` is what consumes this, and it must see
        exactly the tables a migration creates.
        """

        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return Ok(tuple(str(row[0]) for row in rows))

    def tombstone_ledger(self) -> Result[frozenset[tuple[str, str]]]:
        """The ``(entity_kind, entity_hash)`` set the import guard asks about."""

        rows = self._conn.execute(
            "SELECT entity_kind, entity_hash FROM deletion_tombstone"
        ).fetchall()
        return Ok(frozenset((str(row[0]), str(row[1])) for row in rows))

    def list_tombstones(
        self, scope: DeletionScope | None = None
    ) -> Result[tuple[TombstoneRecord, ...]]:
        """The §24 ledger, optionally narrowed to one scope.

        Ordered by ``(entity_kind, entity_hash)`` — a durable, content-derived
        order rather than insertion order, so two runs that deleted the same
        entities report the same sequence.
        """

        if scope is None:
            rows = self._conn.execute(
                "SELECT tombstone_id, entity_kind, entity_hash, deleted_at,"
                " deletion_scope, scope_version FROM deletion_tombstone"
                " ORDER BY entity_kind, entity_hash"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT tombstone_id, entity_kind, entity_hash, deleted_at,"
                " deletion_scope, scope_version FROM deletion_tombstone"
                " WHERE deletion_scope = ? ORDER BY entity_kind, entity_hash",
                (scope.value,),
            ).fetchall()
        return Ok(
            tuple(
                TombstoneRecord(
                    tombstone_id=str(row[0]),
                    entity_kind=str(row[1]),
                    entity_hash=str(row[2]),
                    deleted_at=str(row[3]),
                    deletion_scope=DeletionScope(str(row[4])),
                    scope_version=str(row[5]),
                )
                for row in rows
            )
        )

    # -- the one write face ------------------------------------------------

    def execute(self, request: DeletionRequest) -> Result[DeletionExecution]:
        """Run one deletion request to completion, atomically.

        Everything happens inside one ``BEGIN IMMEDIATE``: the tombstones, the
        removals and SEC-028's cancellation of unfinished work. A refusal
        before the transaction writes nothing; a failure inside rolls the
        whole unit back, so a caller never observes half a deletion.
        """

        invalid = self._validate(request)
        if invalid is not None:
            return Err(invalid)
        deleted_at = request.deleted_at or _now()
        run = _Run(scope=request.scope, deleted_at=deleted_at)
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                known = self.table_names()
                if isinstance(known, Err):
                    return known
                assert_known_tables(known.value)
                self._dispatch(request, run)
        except UnknownTableError as exc:
            # §23's closure failed: the database carries a table this package
            # has not classified, so the sweep refuses instead of walking past
            # it. Rolled back by the context manager, so nothing was written.
            return _err(DomainErrorCode.VALIDATION_FAILED, str(exc))
        except sqlite3.IntegrityError as exc:
            return _err(
                DomainErrorCode.CONFLICT,
                "deletion refused by a durable constraint ("
                + _constraint_family(exc)
                + ")",
            )
        return Ok(run.execution())

    def _validate(self, request: DeletionRequest) -> DomainError | None:
        """The request's own shape — checked before anything is opened."""

        scope = request.scope
        if scope is DeletionScope.CONVERSATION:
            if request.conversation_id is None:
                return DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "CONVERSATION deletion needs a conversation_id (§19):"
                        " a conversation scope without one is not a wider"
                        " deletion, it is an unanswered question"
                    ),
                )
        elif scope is DeletionScope.LEARNING_TARGET:
            if request.target_id is None:
                return DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "LEARNING_TARGET deletion needs a target_id (§20)"
                    ),
                )
        elif scope is DeletionScope.RELATIONSHIP_PAIR:
            if request.persona_id is None:
                return DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "RELATIONSHIP_PAIR deletion needs a persona_id (§21):"
                        " the scope is Persona × User, never a bare user sweep"
                    ),
                )
        elif scope is DeletionScope.PROFILE_FIELD:
            if not request.field_key:
                return DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "PROFILE_FIELD deletion needs a field_key (benchmark"
                        " S44)"
                    ),
                )
        return None

    def _dispatch(self, request: DeletionRequest, run: _Run) -> None:
        scope = request.scope
        if scope is DeletionScope.CONVERSATION:
            self._conversation(str(request.conversation_id), run)
        elif scope is DeletionScope.LEARNING_TARGET:
            self._learning_target(request, run)
        elif scope is DeletionScope.ALL_LEARNING_HISTORY:
            self._all_learning_history(run)
        elif scope is DeletionScope.RELATIONSHIP_PAIR:
            self._relationship_pair(str(request.persona_id), run)
        elif scope is DeletionScope.PROFILE_FIELD:
            self._profile_field(request, run)
        elif scope is DeletionScope.PERSONA_PACKAGE:
            self._persona_package(request, run)
        else:
            self._all_user_data(run)

    # -- primitives --------------------------------------------------------

    def _column(self, sql: str, params: Sequence[object]) -> tuple[str, ...]:
        return tuple(
            str(row[0]) for row in self._conn.execute(sql, params).fetchall()
        )

    def _count(self, sql: str, params: Sequence[object] = ()) -> int:
        row = self._conn.execute(sql, params).fetchone()
        return 0 if row is None else int(row[0])

    def _write_tombstones(
        self, kind: str, ids: Sequence[str], run: _Run
    ) -> None:
        """§24: one minimal ledger row per removed entity — never the body."""

        if not ids:
            return
        rows = []
        for entity_id in ids:
            digest = entity_hash_for(kind, entity_id)
            rows.append(
                (
                    tombstone_id_for(kind, digest),
                    kind,
                    digest,
                    run.deleted_at,
                    run.scope.value,
                    DELETION_POLICY_VERSION,
                )
            )
        cursor = self._conn.executemany(
            "INSERT INTO deletion_tombstone (tombstone_id, entity_kind,"
            " entity_hash, deleted_at, deletion_scope, scope_version)"
            " VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(tombstone_id) DO NOTHING",
            rows,
        )
        # A conflicted insert changes nothing, so rowcount counts the ledger
        # rows this run actually minted: re-deleting an entity under a second
        # scope does not inflate the count.
        run.tombstoned += cursor.rowcount

    def _remove(
        self,
        *,
        table: str,
        predicate: str,
        params: Sequence[object],
        run: _Run,
        identity: str | None = None,
    ) -> tuple[str, ...]:
        """Remove every ``table`` row the predicate selects, tombstoning it.

        ``identity`` names a single identity column for the rare table whose
        identity is not the concatenation of every non-rowid column the
        surface select returned (``relationship_memory``, whose JSON
        provenance columns are not part of its identity).
        """

        sql = _SURFACE_SELECT[table]
        if predicate:
            sql = sql + " WHERE " + predicate
        rows = self._conn.execute(sql, params).fetchall()
        return self._remove_rows(
            table=table, rows=rows, run=run, identity=identity
        )

    def _remove_in(
        self,
        *,
        table: str,
        column: str,
        values: Sequence[str],
        run: _Run,
    ) -> tuple[str, ...]:
        """``_remove`` for the ``column IN (…)`` shape, empty list included.

        An empty value list is not "match nothing and fail": it is a step with
        no rows to remove, and this face returns before any SQL is built
        (``IN ()`` is not valid SQLite).
        """

        if not values:
            return ()
        return self._remove(
            table=table,
            predicate=column + " IN (" + _placeholders(len(values)) + ")",
            params=values,
            run=run,
        )

    def _remove_rows(
        self,
        *,
        table: str,
        rows: Sequence[Sequence[object]],
        run: _Run,
        identity: str | None = None,
    ) -> tuple[str, ...]:
        """Remove an already-decided set of ``(rowid, identity…)`` tuples.

        The face a Python-side predicate uses: the solely-derived
        relationship rule reads JSON provenance arrays, so the decision is
        Python's and only its result reaches SQL.
        """

        if not rows:
            return ()
        rowids = [int(str(row[0])) for row in rows]
        if identity is None:
            ids = [_us_join(row[1:]) for row in rows]
        else:
            ids = [str(row[1]) for row in rows]
        self._write_tombstones(table, ids, run)
        self._conn.execute(
            _DELETE_BY_ROWID[table] + _placeholders(len(rowids)) + ")",
            rowids,
        )
        run.add(table, len(rowids))
        return tuple(ids)

    # -- §19 conversation --------------------------------------------------

    def _conversation(self, conversation_id: str, run: _Run) -> None:
        """§19, in foreign-key order."""

        cid = conversation_id
        persona_row = self._conn.execute(
            "SELECT persona_id FROM conversation WHERE conversation_id = ?",
            (cid,),
        ).fetchone()
        if persona_row is None:
            run.notes.append(f"conversation {cid} was already absent")
            return
        persona = None if persona_row[0] is None else str(persona_row[0])

        turn_ids = self._column(
            "SELECT turn_id FROM turn_record WHERE conversation_id = ?", (cid,)
        )
        user_turn_ids = self._column(
            "SELECT user_turn_id FROM user_turn WHERE conversation_id = ?",
            (cid,),
        )
        assistant_turn_ids = self._column(
            "SELECT assistant_turn_id FROM assistant_turn"
            " WHERE conversation_id = ?",
            (cid,),
        )
        moment_ids = self._column(
            "SELECT moment_id FROM teaching_moment WHERE conversation_id = ?",
            (cid,),
        )
        cycle_ids = self._column(
            "SELECT decision_cycle_id FROM decision_cycle"
            " WHERE turn_id IN (" + _placeholders(len(turn_ids)) + ")",
            turn_ids,
        )
        group_ids = self._column(
            "SELECT evidence_group_id FROM evidence_group"
            " WHERE conversation_id = ?"
            + (
                " OR source_turn_id IN ("
                + _placeholders(len(turn_ids))
                + ")"
                if turn_ids
                else ""
            ),
            (cid, *turn_ids),
        )
        action_ids = self._column(
            "SELECT action_id FROM generation_action_intent"
            " WHERE turn_id IN (" + _placeholders(len(turn_ids)) + ")"
            " OR decision_cycle_id IN ("
            + _placeholders(len(cycle_ids))
            + ")"
            " OR moment_id IN (" + _placeholders(len(moment_ids)) + ")",
            (*turn_ids, *cycle_ids, *moment_ids),
        )

        # The rebuild inputs are collected *before* the evidence goes: these
        # are the keys whose materialized state and schedule row lost a
        # source, and nothing after this point could name them.
        self._collect_affected_targets(
            "SELECT DISTINCT target_type, target_id, evidence_modality"
            " FROM evidence_claim WHERE conversation_id = ?"
            + (
                " OR source_turn_id IN ("
                + _placeholders(len(turn_ids))
                + ")"
                if turn_ids
                else ""
            ),
            (cid, *turn_ids),
            run,
        )

        # -- SEC-028 (counted here, removed with the queue below) ----------
        self._cancel_unfinished_jobs_from_turns(turn_ids, run)
        # -- SEC-021 / SEC-022: the conversation's own actions -------------
        self._classify_actions(action_ids, run)
        # -- §19's provenance closure over the pair's memories -------------
        deleted_refs = frozenset(
            (*turn_ids, *user_turn_ids, *assistant_turn_ids)
        )
        memory_rows = self._solely_derived_memories(deleted_refs, persona)
        # The surviving rows must lose their dangling refs *before* the turn
        # rows go: `source_turn_id` is a NO ACTION foreign key, so a leg left
        # pointing at a deleted turn would refuse the delete outright.
        self._prune_surviving_memory_refs(
            deleted_refs,
            persona,
            {int(str(row[0])) for row in memory_rows},
            run,
        )

        # -- removals, children first --------------------------------------
        self._remove(
            table="active_teaching_lock",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove(
            table="assistant_turn",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove(
            table="episode",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove_in(
            table="evidence_commit",
            column="evidence_group_id",
            values=group_ids,
            run=run,
        )
        self._remove(
            table="evidence_claim",
            predicate="conversation_id = ?"
            + (
                " OR source_turn_id IN ("
                + _placeholders(len(turn_ids))
                + ")"
                if turn_ids
                else ""
            ),
            params=(cid, *turn_ids),
            run=run,
        )
        self._remove_in(
            table="review_event",
            column="source_turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove_in(
            table="review_event",
            column="evidence_group_id",
            values=group_ids,
            run=run,
        )
        self._remove(
            table="evidence_group",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove_in(
            table="expression_need",
            column="source_turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove_in(
            table="gate_execution_status",
            column="moment_id",
            values=moment_ids,
            run=run,
        )
        self._remove(
            table="interrupt_request",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove_in(
            table="learner_self_report",
            column="user_turn_id",
            values=user_turn_ids,
            run=run,
        )
        self._clear_constraint_legs(turn_ids, run)
        self._remove_in(
            table="projection_job",
            column="source_turn_id",
            values=turn_ids,
            run=run,
        )
        # §27's receipt leaves whole with the conversation it belongs to. In
        # V1 the durable ``provider_attempt`` row *is* the receipt's non-body
        # audit state, and this cut keeps no separate marker beside it; the
        # disclosure it records was counted by ``_classify_actions`` before
        # the row goes, and nothing about the remote copy is claimed
        # (``_classify_actions``' docstring carries the registration).
        self._remove_in(
            table="provider_attempt",
            column="action_id",
            values=action_ids,
            run=run,
        )
        self._remove_rows(
            table="relationship_memory",
            rows=memory_rows,
            run=run,
            identity="relationship_memory_id",
        )
        self._remove(
            table="session_focus",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove_in(
            table="teaching_evidence_proposal",
            column="moment_id",
            values=moment_ids,
            run=run,
        )
        self._remove_in(
            table="analysis_artifact",
            column="turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove_in(
            table="attempt_evaluation_record",
            column="moment_id",
            values=moment_ids,
            run=run,
        )
        self._remove_in(
            table="generation_action_intent",
            column="turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove_in(
            table="learning_opportunity_record",
            column="source_turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove_in(
            table="attempt_record",
            column="moment_id",
            values=moment_ids,
            run=run,
        )
        self._remove(
            table="teaching_moment",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove(
            table="user_turn",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        # P8-0's §14 planner records: the conversation's own cycles' decision
        # trail (and the turn-level outcome row). Children first — a decision
        # names its evaluation, and all four name the cycle or the turn that
        # is removed right below them.
        self._remove_in(
            table="planner_decision",
            column="decision_cycle_id",
            values=cycle_ids,
            run=run,
        )
        self._remove_in(
            table="planner_evaluation",
            column="decision_cycle_id",
            values=cycle_ids,
            run=run,
        )
        self._remove_in(
            table="planner_execution_status",
            column="decision_cycle_id",
            values=cycle_ids,
            run=run,
        )
        self._remove_in(
            table="runtime_decision_outcome",
            column="turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove_in(
            table="gate_decision",
            column="decision_cycle_id",
            values=cycle_ids,
            run=run,
        )
        self._remove_in(
            table="decision_cycle",
            column="turn_id",
            values=turn_ids,
            run=run,
        )
        self._remove(
            table="turn_record",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove(
            table="input_envelope",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )
        self._remove(
            table="conversation",
            predicate="conversation_id = ?",
            params=(cid,),
            run=run,
        )

        # -- §19's "revalidate/rebuild from surviving sources" -------------
        if memory_rows:
            run.notes.append(
                "relationship memories whose remaining provenance still"
                " supported them were revalidated rather than deleted, and"
                " the pair's projection is re-derived on read (§19)"
            )
        if persona is None:
            run.notes.append(
                "the conversation carried no persona, so no other"
                " conversation's episode projection depends on its memories"
                " (a persona-less conversation owns no pair)"
            )
            return
        self._collect_episode_rebuilds(persona, exclude=cid, run=run)
        self._invalidate_episode_jobs(run)

    def _invalidate_episode_jobs(self, run: _Run) -> None:
        """Drop the CP4 job row of every episode that must be re-derived.

        Only the *job* row goes, never the episode row: the job is what makes
        the projection run again, and ``SqliteEpisodeStore.upsert_episode``
        already knows how to replace a moved version in place. Deleting the
        episode first would leave a window in which a rebuild failure has
        destroyed the row it was going to repair — invalidation is enough, and
        it is the smaller change.

        The predicate names the type word and the anchor turn, so exactly one
        row per affected conversation is released. The sibling RELATIONSHIP
        job (same turn, other type) is untouched: its projection is computed
        from the pair's memories on read and needs no re-run.
        """

        for key in run.affected_episodes:
            self._remove(
                table="projection_job",
                predicate=(
                    "source_turn_id = ? AND projection_type = 'EPISODE'"
                ),
                params=(key.anchor_turn_id,),
                run=run,
            )

    def _prune_surviving_memory_refs(
        self,
        deleted_refs: frozenset[str],
        persona_id: str | None,
        removed_rowids: set[int],
        run: _Run,
    ) -> None:
        """§19's revalidate branch, made concrete for the rows that survive.

        A memory that keeps a living source keeps its row — but not its
        dangling refs: ``source_turn_id`` is a foreign key the deletion would
        otherwise break, and the two JSON arrays are §17 provenance that must
        not go on naming turns that no longer exist. Only refs that are in the
        deleted set are dropped, so a surviving memory keeps at least the one
        source that saved it (and §17's "no long-term memory without
        provenance" is not violated by the pruning). Rows this run is about to
        delete are skipped — their refs leave with them.
        """

        if persona_id is None:
            rows = self._conn.execute(
                "SELECT rowid, relationship_memory_id, source_turn_id,"
                " source_turn_ids, provenance_refs FROM relationship_memory"
                " ORDER BY relationship_memory_id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT rowid, relationship_memory_id, source_turn_id,"
                " source_turn_ids, provenance_refs FROM relationship_memory"
                " WHERE persona_id = ? ORDER BY relationship_memory_id",
                (persona_id,),
            ).fetchall()
        for row in rows:
            if int(str(row[0])) in removed_rowids:
                continue
            source_turn_id = None if row[2] is None else str(row[2])
            turn_sources = tuple(_decode_array(str(row[3])))
            refs = tuple(_decode_array(str(row[4])))
            new_leg = (
                None
                if source_turn_id is not None and source_turn_id in deleted_refs
                else source_turn_id
            )
            new_sources = tuple(
                item for item in turn_sources if item not in deleted_refs
            )
            new_refs = tuple(item for item in refs if item not in deleted_refs)
            if (
                new_leg == source_turn_id
                and new_sources == turn_sources
                and new_refs == refs
            ):
                continue
            self._conn.execute(
                "UPDATE relationship_memory SET source_turn_id = ?,"
                " source_turn_ids = ?, provenance_refs = ? WHERE rowid = ?",
                (
                    new_leg,
                    json.dumps(list(new_sources), sort_keys=True,
                               separators=(",", ":")),
                    json.dumps(list(new_refs), sort_keys=True,
                               separators=(",", ":")),
                    int(row[0]),
                ),
            )
            run.cleared_provenance_legs += 1

    def _collect_affected_targets(
        self, sql: str, params: Sequence[object], run: _Run
    ) -> None:
        seen = {
            (key.target_type, key.target_id, key.evidence_modality)
            for key in run.affected_targets
        }
        for row in self._conn.execute(sql, params).fetchall():
            key = (str(row[0]), str(row[1]), str(row[2]))
            if key in seen:
                continue
            seen.add(key)
            run.affected_targets.append(
                TargetKey(
                    target_type=key[0],
                    target_id=key[1],
                    evidence_modality=key[2],
                )
            )

    def _collect_episode_rebuilds(
        self, persona_id: str, *, exclude: str | None, run: _Run
    ) -> None:
        """The pair's surviving conversations whose episode must be re-derived.

        §21 keeps the transcript and §19 rebuilds partially-supported views;
        an episode's ``open_threads`` *is* the pair's summary, so a deletion
        that moved the pair's memories leaves those episodes stale even though
        nothing in them was addressed directly. Only conversations with a
        COMPLETED turn are collected — a conversation with no canonical
        outcome has no episode to rebuild, and inventing one is exactly the
        empty artifact the episode executor refuses.
        """

        rows = self._conn.execute(
            "SELECT conversation_id FROM conversation WHERE persona_id = ?"
            " ORDER BY conversation_id",
            (persona_id,),
        ).fetchall()
        for row in rows:
            conversation_id = str(row[0])
            if conversation_id == exclude:
                continue
            if any(
                key.conversation_id == conversation_id
                for key in run.affected_episodes
            ):
                continue
            anchor = self._conn.execute(
                "SELECT turn_id FROM turn_record"
                " WHERE conversation_id = ? AND status = 'COMPLETED'"
                " ORDER BY turn_sequence DESC, turn_id DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if anchor is None:
                continue
            run.affected_episodes.append(
                EpisodeRebuildKey(
                    conversation_id=conversation_id,
                    anchor_turn_id=str(anchor[0]),
                )
            )

    def _solely_derived_memories(
        self, deleted_refs: frozenset[str], persona_id: str | None
    ) -> tuple[Sequence[object], ...]:
        """§19's rule for the relationship leg: delete, or revalidate.

        A memory is removed when **every** turn-level source it names is going
        away — §17's ``source_ids`` question answered against the deletion —
        and nothing else. A memory with one surviving turn source is
        revalidated instead (it still has an independent provenance), and a
        memory that names no turn at all is left alone unless its
        ``provenance_refs`` reach into the deleted set, which is the case the
        Recorder cannot produce but a hand-written row could.

        Both JSON legs are read here rather than compared in SQL: the columns
        are arrays, and an SQL predicate over them would be a second, cleverer
        implementation of the same rule.
        """

        if persona_id is None:
            rows = self._conn.execute(
                "SELECT rowid, relationship_memory_id, source_turn_id,"
                " source_turn_ids, provenance_refs FROM relationship_memory"
                " ORDER BY relationship_memory_id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT rowid, relationship_memory_id, source_turn_id,"
                " source_turn_ids, provenance_refs FROM relationship_memory"
                " WHERE persona_id = ? ORDER BY relationship_memory_id",
                (persona_id,),
            ).fetchall()
        selected = []
        for row in rows:
            source_turn_id = None if row[2] is None else str(row[2])
            sources = set(_decode_array(str(row[3])))
            if source_turn_id is not None:
                sources.add(source_turn_id)
            if sources:
                if not sources <= deleted_refs:
                    continue
            elif not (set(_decode_array(str(row[4]))) & deleted_refs):
                continue
            selected.append(row)
        return tuple(selected)

    def _cancel_unfinished_jobs_from_turns(
        self, turn_ids: Sequence[str], run: _Run
    ) -> None:
        """SEC-028's count for the conversation scope, before the removal.

        The count is the queue's two unfinished words (PENDING /
        FAILED_RETRYABLE) — the states that mean "work is queued and will be
        attempted". The rows themselves leave with their source turn in the
        ``projection_job`` step below, RUNNING included: a RUNNING row whose
        turn is gone can never land anyway (the shipped executor recomputes
        the canonical slice and refuses when it is absent), and leaving it
        would strand a claimed job in a queue whose source no longer exists.
        That the two facts agree — the count is unfinished-only, the removal
        is source-scoped — is asserted by the S47/SEC-028 probes.
        """

        if not turn_ids:
            return
        run.cancelled_projection_jobs += self._count(
            "SELECT COUNT(*) FROM projection_job WHERE status IN (?, ?)"
            " AND source_turn_id IN ("
            + _placeholders(len(turn_ids))
            + ")",
            (*_UNFINISHED_JOB_STATES, *turn_ids),
        )

    def _classify_actions(self, action_ids: Sequence[str], run: _Run) -> None:
        """SEC-021/§27: split the conversation's actions by transmission.

        An action with no ``provider_attempt`` row was never transmitted — it
        is cancelled before transmission (§25) and counted. One with an
        attempt was sent: §27 keeps the non-body audit state, and in V1 that
        state *is* the ``provider_attempt`` row, so it is counted as a
        disclosure that happened and handed to the external-deletion
        judgement rather than claimed revoked. Both kinds then leave with
        their conversation, because ``generation_action_intent``'s
        turn/cycle/moment foreign keys are ``NO ACTION`` against rows this
        scope removes — a structural fact of migrations 0002/0007/0008, not a
        choice this cut made.

        **Registered trade-off (Gate 2 review F4).** §27 allows a receipt to
        drop its content refs while keeping the non-body audit state "直到对应
        诊断/用户数据删除范围要求移除". This cut keeps **no separate non-body
        marker**: the ``provider_attempt`` row is the receipt, and a user-data
        deletion that reaches its conversation removes it whole — the "until
        the user-data deletion scope requires removal" half of §27, read as
        the user's deletion being that scope. Nothing is lost from the count
        (the disclosure was tallied here first), and nothing about the remote
        copy is asserted either way (§26; the two honest answers live in
        ``plan_external_deletion``). The removal itself is in
        ``_conversation``, at the ``provider_attempt`` step.
        """

        if not action_ids:
            return
        placeholders = _placeholders(len(action_ids))
        sent = self._count(
            "SELECT COUNT(*) FROM generation_action_intent"
            " WHERE action_id IN (" + placeholders + ")"
            " AND EXISTS (SELECT 1 FROM provider_attempt"
            " WHERE provider_attempt.action_id ="
            " generation_action_intent.action_id)",
            action_ids,
        )
        run.sent_provider_actions += sent
        run.cancelled_provider_actions += len(action_ids) - sent

    def _clear_constraint_legs(
        self, turn_ids: Sequence[str], run: _Run
    ) -> None:
        """A user's setting survives its originating turn; its leg does not.

        §9 spells ``created_from_turn_id?`` optional, and §18.1's
        TRUSTED_AUTHORITY makes a typed user setting the user's own statement
        rather than data derived from a turn — so the row is not deleted with
        the conversation, and the provenance leg that can no longer be
        resolved is cleared (the §27 precedent: drop the content ref, keep the
        non-body state). The column is nullable for exactly this case.
        """

        if not turn_ids:
            return
        cursor = self._conn.execute(
            "UPDATE planner_constraint SET created_from_turn_id = NULL"
            " WHERE created_from_turn_id IN ("
            + _placeholders(len(turn_ids))
            + ")",
            turn_ids,
        )
        run.cleared_provenance_legs += cursor.rowcount

    # -- §20 learning ------------------------------------------------------

    def _learning_target(self, request: DeletionRequest, run: _Run) -> None:
        """§20 LEARNING_TARGET: the target's evidence, state and review rows.

        The transcript is untouched by construction: no conversation, turn or
        input table is in this scope's surface, and none is written here.
        ``planner_constraint`` is a user setting (§9/§18.1), not learning
        history, so a constraint that names this target stays — its ``active``
        flag is the user's, and erasing a target's learning history says
        nothing about whether the user still wants it suppressed.

        Nothing is rebuilt afterwards: every claim and state row for the
        target is gone, so a recomputation would write an empty projection
        over an empty evidence set.
        """

        target_id = str(request.target_id)
        target_type = request.target_type
        suffix = "" if target_type is None else " AND target_type = ?"
        extra: tuple[object, ...] = (
            () if target_type is None else (target_type,)
        )
        schedule_ids = self._column(
            "SELECT schedule_item_id FROM schedule_item WHERE target_id = ?"
            + suffix,
            (target_id, *extra),
        )
        self._remove(
            table="evidence_claim",
            predicate="target_id = ?" + suffix,
            params=(target_id, *extra),
            run=run,
        )
        self._remove_in(
            table="review_event",
            column="schedule_item_id",
            values=schedule_ids,
            run=run,
        )
        self._remove(
            table="learner_self_report",
            predicate="target_id = ?" + suffix,
            params=(target_id, *extra),
            run=run,
        )
        self._remove(
            table="schedule_item",
            predicate="target_id = ?" + suffix,
            params=(target_id, *extra),
            run=run,
        )
        self._remove(
            table="learner_target_state",
            predicate="target_id = ?" + suffix,
            params=(target_id, *extra),
            run=run,
        )
        # -- the ledger half (P8-3). §20's LEARNING_TARGET list names "related
        # PlanningLedger history", and the three rows a target owns are
        # exact: its TARGET-keyed ledger row, that row's event log, and its
        # TARGET-scoped obligations. The key face is read, not assumed, so a
        # *family* row whose id spells this target's is left standing (the
        # contract's scope is the target, not every string that looks like it);
        # the log is reached through the keys the row read returned, because
        # the log has no key-face column of its own.
        ledger_keys = self._column(
            "SELECT ledger_key FROM planning_ledger WHERE ledger_key_type = ?"
            " AND ledger_key = ?",
            (LedgerKeyType.TARGET.value, target_id),
        )
        self._remove_in(
            table="planning_ledger_event",
            column="ledger_key",
            values=ledger_keys,
            run=run,
        )
        self._remove(
            table="planning_ledger",
            predicate="ledger_key_type = ? AND ledger_key = ?",
            params=(LedgerKeyType.TARGET.value, target_id),
            run=run,
        )
        self._remove(
            table="coverage_obligation",
            predicate="scope_type = ? AND target_or_family_id = ?",
            params=(ObligationScope.TARGET.value, target_id),
            run=run,
        )

    def _all_learning_history(self, run: _Run) -> None:
        """§20 ALL_LEARNING_HISTORY: the learning side entire.

        Kept by surface, deliberately: conversation and transcript,
        relationship memory, profile, goals, and the user's own settings
        (§20's keep list, plus §18.1's reading of a typed user setting).
        ``affected_targets`` stays empty because nothing survives to rebuild
        *from*.
        """

        self._count_queue_and_actions(run)
        for table in LEARNING_HISTORY_SWEPT_TABLES:
            self._remove(table=table, predicate="", params=(), run=run)

    # -- §21 relationship --------------------------------------------------

    def _relationship_pair(self, persona_id: str, run: _Run) -> None:
        """§21 RELATIONSHIP_PAIR: the pair's memories, and nothing else.

        No learning table is in this scope's surface and none is written here
        (SEC-027), and the transcript keeps every row (§21's "不自动删除").
        The pair's *projection* is computed on read from these memories, so
        removing them is removing it; what does need re-deriving is the
        episode projection of the pair's conversations, whose
        ``open_threads`` column is built from the summary — those
        conversations are handed to the controller, which re-runs them
        through the shipped CP4 path.
        """

        rows = self._conn.execute(
            "SELECT rowid, relationship_memory_id FROM relationship_memory"
            " WHERE persona_id = ? ORDER BY relationship_memory_id",
            (persona_id,),
        ).fetchall()
        self._remove_rows(
            table="relationship_memory",
            rows=rows,
            run=run,
            identity="relationship_memory_id",
        )
        self._collect_episode_rebuilds(persona_id, exclude=None, run=run)
        self._invalidate_episode_jobs(run)
        if not rows:
            run.notes.append(
                f"persona {persona_id} held no relationship memory; the scope"
                " removed nothing (a fact about the data, not a refusal)"
            )

    # -- benchmark S44 PROFILE_FIELD ---------------------------------------

    def _profile_field(self, request: DeletionRequest, run: _Run) -> None:
        """The benchmark's PROFILE_FIELD scope, fail-closed (§17 vs §5.1).

        §17 requires every profile fact to answer "它来自哪些 source_ids？",
        and §5.1's ``user_profile`` column set — frozen, and frozen on purpose
        — has no such column. Without it there is no way to decide *which*
        fact the caller named: ``profile_facts`` is a JSON array of
        ``{text, sensitivity}`` with no per-fact identity and no provenance.

        The choice this cut makes is **delete more, not less**: the whole fact
        set is cleared, because leaving a fact the user asked to remove is the
        failure §17 exists to prevent, while removing a sibling fact is a loss
        the user can repair by restating it. The divergence from the
        reference's per-field precision is registered here rather than
        papered over — S44's ``must_delete: ["profile_city"]`` is honoured as
        a subset (the named field's content is gone) and its
        ``must_keep: ["profile_lang"]`` is *not* preserved, which is what the
        conflict between §17 and §5.1 costs until a canonical revision
        authorises a provenance column. No column is added by this cut.

        ``preferences`` and ``settings`` are left alone: they are not the
        ``profile_facts`` set, and the scope named a field of the facts. The
        row's ``revision`` moves — a §1.4 stamp must not describe content it
        no longer stamps — and the new stamp is derived, not invented per
        call.
        """

        field_key = str(request.field_key)
        rows = self._conn.execute(
            "SELECT rowid, user_profile_id, revision FROM user_profile"
            " ORDER BY user_profile_id"
        ).fetchall()
        if not rows:
            run.notes.append(
                "no user_profile row exists, so the field deletion removed"
                " nothing"
            )
            return
        digest = entity_hash_for(PROFILE_FIELD_ENTITY_KIND, field_key)
        self._write_tombstones(PROFILE_FIELD_ENTITY_KIND, (field_key,), run)
        for row in rows:
            self._conn.execute(
                "UPDATE user_profile SET profile_facts = '[]', revision = ?,"
                " updated_at = ? WHERE rowid = ?",
                (_revised_profile_stamp(str(row[2]), digest), run.deleted_at,
                 int(str(row[0]))),
            )
        run.add("user_profile", len(rows))
        run.notes.append(
            "user_profile carries no per-fact provenance column (§17 asks for"
            " one; §5.1's column set has none and this cut adds none), so the"
            " deletion is fail-closed: the whole profile_facts set was"
            " removed rather than guessing which entry the caller named"
        )

    # -- §22 PERSONA_PACKAGE ----------------------------------------------

    def _persona_package(self, request: DeletionRequest, run: _Run) -> None:
        """§22: the low-level scope deletes a Persona definition/package.

        V1's app.db has no persona definition table — ``elc.persona`` is a
        runtime assembly over ``CharacterPackageRecord`` values the caller
        supplies (elc/persona/types.py), and no migration creates a table for
        one. So this scope's app.db face is **empty**, and this method removes
        nothing: reaching for the nearest user table (the pair's memories, the
        persona's conversations, their transcripts) would be precisely the
        "暗中扩大删除范围" §22 forbids. The product-level "彻底删除这个角色" is
        the *composition* §22 describes — PERSONA_PACKAGE + RELATIONSHIP_PAIR
        + the persona-scoped episode projection — and a caller that wants it
        issues those scopes.

        Nothing is tombstoned either: a ledger row claims an entity was
        removed, and claiming a removal that did not happen would make the
        §24 guard refuse a backup of data this app never deleted.
        """

        persona_id = (
            "unspecified"
            if request.persona_id is None
            else str(request.persona_id)
        )
        run.notes.append(
            f"PERSONA_PACKAGE({persona_id}): app.db holds no persona"
            " definition/package table in V1, so this scope's app.db face is"
            " empty by construction (§22); whether the persona's transcript is"
            " deleted is the caller's separate choice and this scope does not"
            " make it"
        )

    # -- §23 ALL_USER_DATA -------------------------------------------------

    def _all_user_data(self, run: _Run) -> None:
        """§23: the table-driven sweep, with the guard that closes it.

        :data:`SWEPT_TABLES` is walked in its declared (children-first) order.
        The guard that every table of this database is classified already ran
        in :meth:`execute`, before the transaction wrote anything — a
        migration that lands an unclassified table makes this scope *fail*
        rather than quietly sweep past it.

        ``deletion_tombstone`` and the three infrastructure tables are not
        swept (§23's deletion-protection ledger, the schema lineage, the
        restart fence); the ledger is what is being *written* here.
        """

        assert_known_tables(
            tuple(ALL_USER_DATA_SWEPT_TABLES) + tuple(RETAINED_TABLES)
        )
        self._count_queue_and_actions(run)
        for table in ALL_USER_DATA_SWEPT_TABLES:
            self._remove(table=table, predicate="", params=(), run=run)
        run.notes.append(
            "ALL_USER_DATA swept every user table and kept only schema_meta,"
            " schema_migrations, runtime_epoch and the §24 deletion ledger"
            " (§23); V1 keeps no secret in app.db (the SecretStore is a"
            " separate store) and has no embedding or retrieval-index table,"
            " so those two clauses of §23 have no storage to act on"
        )

    def _count_queue_and_actions(self, run: _Run) -> None:
        """SEC-021/SEC-028's counts for the two whole-database scopes.

        Counted before the rows go, so the outcome reports what was pending
        and what had already been transmitted rather than only what is gone.
        """

        if self._count("SELECT COUNT(*) FROM projection_job"):
            run.cancelled_projection_jobs += self._count(
                "SELECT COUNT(*) FROM projection_job WHERE status IN (?, ?)",
                _UNFINISHED_JOB_STATES,
            )
        total = self._count("SELECT COUNT(*) FROM generation_action_intent")
        if total:
            sent = self._count(
                "SELECT COUNT(*) FROM generation_action_intent WHERE EXISTS"
                " (SELECT 1 FROM provider_attempt WHERE"
                " provider_attempt.action_id ="
                " generation_action_intent.action_id)"
            )
            run.sent_provider_actions += sent
            run.cancelled_provider_actions += total - sent


#: ALL_LEARNING_HISTORY's walk is elc/deletion/types.py's own
#: ``LEARNING_HISTORY_SWEPT_TABLES`` — the declaration *is* the order, and a
#: second tuple here would be a second thing to keep in step (the P6-3
#: lesson about duplicated lineage constants). Its children-first property is
#: pinned by test against the real schema.


def _revised_profile_stamp(revision: str, digest: str) -> str:
    """The profile revision after a fail-closed fact removal (§1.4).

    §1.4 asks a versioned object to move its stamp when its content moves, and
    §5.1 pins the column without pinning how a stamp is derived. A deletion
    has no caller-supplied version, so the new stamp is **derived** from the
    old one and the removal's own digest — deterministic (the same removal of
    the same revision yields the same new revision) and visibly a deletion
    stamp rather than a hand-written one.
    """

    return "del-" + entity_hash_for(revision, digest)[:20]
