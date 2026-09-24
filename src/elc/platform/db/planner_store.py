"""SQLite adapter for the §14 planner records — CP2's durable half (P8-0).

TASK-OPI-64c88704-….7 ②③④. docs/DATA_MODEL.md §14 "Planner Data" names four
records and docs/RUNTIME_ARCHITECTURE.md §6 CP2 is the commit point that
makes a cycle's rows durable. The **port** — the Protocol, the record one
commit returns, and the single column map — is
:mod:`elc.planner.records` (the §14 section is Planner Data, and the port is
SQL-free); this module is where the SQL lives, colocated with the other
app.db adapters (``elc.platform.db.decision_cycle_store`` is the sibling this
one is modelled on: same fence, same ``Ok``/``Err`` envelope, same
fixed-literal statements).

**One short transaction, all or nothing.** :meth:`record_planner_cycle`
commits the whole CP2 unit — ``planner_execution_status``,
``planner_evaluation``, ``planner_decision`` when the run succeeded,
``runtime_decision_outcome`` for the turn, and the
``decision_cycle.planner_decision_id`` back-reference — inside one
``short_transaction`` under the owner-epoch fence. A failure anywhere (a
fenced epoch, a foreign key the caller's data cannot satisfy) rolls the unit
back whole; there is no half-committed cycle.

**No fabricated decision.** The outcome value is
:func:`elc.planner.kernel.runtime_decision_outcome_of`'s answer for the
submitted status — one implementation of BF-02 §5's coupling, called rather
than re-spelled. When the status is ``DEGRADED`` / ``FAILED`` /
``UNAVAILABLE`` this face writes **no** ``planner_decision`` row and leaves
``decision_cycle.planner_decision_id`` NULL: §14 line 889 ("Runtime
degradation is not a PlannerDecision.") is a shape of the durable data here,
not a convention.

**Replay, not re-decision.** ``planner_execution_status``'s key is the
decision cycle, so a cycle that already carries a status row is already
decided: the unit reads its rows back and writes nothing (RA §23's crash
windows — "Crash after CP1 … 不重复 Evidence", "Crash after CP2 … 不新建
Moment" — reach the Planner as "a re-entry writes no second evaluation and
no second decision"). A re-entry whose submitted records disagree with the
durable ones — the status word with its error code, the evaluation's five
derived values, or the decision — is refused with ``CONFLICT`` rather than
overwritten or silently answered with somebody else's row
(``_replay``; elc/planner/records.py, judgement 3). The turn-level
``runtime_decision_outcome`` is the one row that **moves**: it is keyed by
the turn, so a same-turn second cycle (a replan) upserts it to name the
newest cycle — the row is the turn's current answer, not a history
(judgement 2).

**The back-reference is an UPDATE, never an INSERT or a DELETE.** This module
is the ``decision_cycle.planner_decision_id`` writer; migration 0015's header
records why that column stays plain data (no FK), and the pointer and the
decision row ride the same transaction so a partial commit cannot strand it.

**What is deliberately absent.** No teaching row is written: §6's
``TeachingMoment`` / ``TeachingLockLease`` / ``active_teaching_lock`` /
``GenerationActionIntent`` half of CP2 is the Gate's automatic face (p8-1),
and this module does not reach for it. No clock is read outside the unit's
own ``created_at`` stamp, and no caller-supplied timestamp is trusted.

All SQL is a fixed literal with bound parameters — no identifier assembly.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import TypeVar

from elc.planner.kernel import PlannerTrace, runtime_decision_outcome_of
from elc.planner.records import PlannerCycleRecords
from elc.planner.trace_document import (
    decode_factor_trace,
    factor_trace_document,
    factor_trace_of,
)
from elc.planner.types import PlannerEvaluation, PlanningOutcome
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    FactorTraceDocument,
    Ok,
    PlannerDecision,
    PlannerDecisionId,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerEvaluationRecord,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
    Result,
    RuntimeDecisionOutcome,
    RuntimeDecisionOutcomeValue,
    RuntimeEpoch,
    TargetId,
    TurnId,
)

__all__ = ["SqlitePlannerRecordStore", "StalePlannerRecordStoreError"]

T = TypeVar("T")


class StalePlannerRecordStoreError(StaleEpochError):
    """A §14 planner-record write was fenced by a newer runtime epoch."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _array_document(values: tuple[str, ...]) -> str:
    """The deterministic JSON array document the list columns carry.

    Reused from elc/teaching/store.py's ``_array_document`` (same call, same
    options) rather than a second spelling: ``sort_keys`` is meaningless over
    a list of strings and is kept because the seam's whole point is that the
    two modules encode alike.
    """

    return json.dumps(list(values), sort_keys=True, separators=(",", ":"))


def _array_from_document(document: object) -> tuple[str, ...]:
    loaded = json.loads(str(document))
    return tuple(str(item) for item in loaded)


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


def _ranked_candidate_ids(evaluation: PlannerEvaluation) -> tuple[str, ...]:
    """§14's ``ranked_candidate_ids``: the record's ranking, ids only (see
    ``elc/planner/records.py``'s column map — the objects are not durable)."""

    return tuple(
        candidate.candidate_id for candidate in evaluation.ranked_candidates
    )


#: §14 column order used by every SELECT in this module.
_EVALUATION_COLUMNS = (
    "planner_evaluation_id",
    "decision_cycle_id",
    "frontier_candidate_ids",
    "ranked_candidate_ids",
    "factor_trace",
    "planner_version",
    "policy_profile_version",
    "created_at",
)

_DECISION_COLUMNS = (
    "planner_decision_id",
    "decision_cycle_id",
    "decision",
    "selected_candidate_id",
    "no_target_reason",
    "planner_evaluation_id",
    "created_at",
)

_STATUS_COLUMNS = ("decision_cycle_id", "status", "error_code", "created_at")

_OUTCOME_COLUMNS = (
    "turn_id",
    "decision_cycle_id",
    "outcome",
    "reason_codes",
    "created_at",
)


def _evaluation_record(row: sqlite3.Row) -> PlannerEvaluationRecord:
    """Decode one §14 row (default tuple rows; positional order is
    ``_EVALUATION_COLUMNS``, the literal every SELECT here uses).

    ``factor_trace`` is decoded by the document's own reader
    (``elc.planner.trace_document.decode_factor_trace``): a versioned object
    becomes the structured document, and the legacy bare array a row written
    before P9-0 carries becomes the tuple of prose lines it always was.
    """

    return PlannerEvaluationRecord(
        planner_evaluation_id=PlannerEvaluationId(str(row[0])),
        decision_cycle_id=DecisionCycleId(str(row[1])),
        frontier_candidate_ids=_array_from_document(row[2]),
        ranked_candidate_ids=_array_from_document(row[3]),
        factor_trace=decode_factor_trace(row[4]),
        planner_version=PlannerVersion(str(row[5])),
        policy_profile_version=PolicyVersion(str(row[6])),
        created_at=str(row[7]),
    )


def _trace_document_of(
    evaluation: PlannerEvaluation, trace: PlannerTrace | None
) -> FactorTraceDocument:
    """The evaluation's ``factor_trace``, as this unit writes it.

    One builder for both the INSERT and the replay comparison, so the bytes a
    write lands and the bytes a re-entry is compared against cannot be built
    by two different readings: the document's ``candidates`` are the trace's
    own (empty when the caller held none), its ``reasons`` are the
    evaluation's ``reason_trace``, and its ``provenance`` word says which of
    the two cases this is (``elc/planner/records.py`` judgements 9 and 10).
    """

    return factor_trace_of(
        reasons=evaluation.reason_trace,
        candidates=() if trace is None else trace.candidates,
        traced=trace is not None,
    )


def _decision_record(row: sqlite3.Row) -> PlannerDecision:
    return PlannerDecision(
        planner_decision_id=PlannerDecisionId(str(row[0])),
        decision_cycle_id=DecisionCycleId(str(row[1])),
        decision=PlannerDecisionOutcome(str(row[2])),
        selected_candidate_id=(
            None if row[3] is None else TargetId(str(row[3]))
        ),
        no_target_reason=None if row[4] is None else str(row[4]),
        planner_evaluation_id=PlannerEvaluationId(str(row[5])),
    )


def _status_record(row: sqlite3.Row) -> PlannerExecutionStatusRecord:
    return PlannerExecutionStatusRecord(
        decision_cycle_id=DecisionCycleId(str(row[0])),
        status=PlannerExecutionStatusValue(str(row[1])),
        error_code=None if row[2] is None else str(row[2]),
    )


def _outcome_record(row: sqlite3.Row) -> RuntimeDecisionOutcome:
    return RuntimeDecisionOutcome(
        turn_id=TurnId(str(row[0])),
        decision_cycle_id=(
            None if row[1] is None else DecisionCycleId(str(row[1]))
        ),
        outcome=RuntimeDecisionOutcomeValue(str(row[2])),
        reason_codes=_array_from_document(row[3]),
    )


def _record_refusal(outcome: PlanningOutcome) -> DomainError | None:
    """The submitted records must already agree with each other.

    ``PlanningOutcome`` enforces the *status/decision* coupling
    (SUCCEEDED ⟺ a decision is present); these two checks are the
    cross-references it cannot see: the evaluation and the decision must name
    the status's cycle, and the decision must name the evaluation. A unit
    that fails them is the caller's data, and it is refused **before** the
    transaction opens (nothing to roll back).
    """

    status = outcome.execution_status
    evaluation = outcome.evaluation
    if evaluation.decision_cycle_id != status.decision_cycle_id:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"evaluation {evaluation.planner_evaluation_id} names cycle"
                f" {evaluation.decision_cycle_id}, status names cycle"
                f" {status.decision_cycle_id}"
            ),
        )
    decision = outcome.decision
    if decision is None:
        return None
    if decision.decision_cycle_id != status.decision_cycle_id:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"decision {decision.planner_decision_id} names cycle"
                f" {decision.decision_cycle_id}, status names cycle"
                f" {status.decision_cycle_id}"
            ),
        )
    if decision.planner_evaluation_id != evaluation.planner_evaluation_id:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"decision {decision.planner_decision_id} names evaluation"
                f" {decision.planner_evaluation_id}, the unit carries"
                f" {evaluation.planner_evaluation_id}"
            ),
        )
    return None


class SqlitePlannerRecordStore:
    """Durable §14 planner rows (the CP2 unit, app.db)."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> RuntimeEpoch:
        return RuntimeEpoch(self._fence.current)

    def _require_current_epoch(self) -> None:
        """Fence inside the write transaction: the adopted epoch must still
        be the newest epoch row in app.db (RUNTIME §24 restart ownership;
        the ``SqliteDecisionCycleStore`` rule)."""

        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StalePlannerRecordStoreError(
                f"planner-record store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- the CP2 unit ------------------------------------------------------

    def record_planner_cycle(
        self,
        *,
        turn_id: TurnId,
        outcome: PlanningOutcome,
        reason_codes: tuple[str, ...] = (),
        trace: PlannerTrace | None = None,
    ) -> Result[PlannerCycleRecords]:
        """One short transaction: the cycle's §14 rows and the back-reference.

        The four records (§14) plus ``decision_cycle.planner_decision_id``
        land together or not at all. A cycle that already carries a status
        row is replayed, not re-decided; a same-turn newer cycle moves the
        turn's ``runtime_decision_outcome`` row.

        ``trace`` is the same run's kernel trace (``ShadowRun.trace``) and it
        is what the evaluation's ``factor_trace`` document is built from
        (:func:`_trace_document_of`): with it, the durable column carries the
        per-candidate trace; without it, the document says so in its
        ``provenance`` word instead of claiming an empty run
        (``elc/planner/records.py`` judgements 9 and 10).
        """

        refusal = _record_refusal(outcome)
        if refusal is not None:
            return Err(refusal)
        status = outcome.execution_status
        decision = outcome.decision
        evaluation = outcome.evaluation
        cycle_id = status.decision_cycle_id
        runtime_outcome = runtime_decision_outcome_of(status.status)
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                cycle = self._conn.execute(
                    "SELECT turn_id FROM decision_cycle"
                    " WHERE decision_cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if cycle is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"decision cycle not found: {cycle_id}",
                    )
                if str(cycle[0]) != turn_id:
                    return _err(
                        DomainErrorCode.VALIDATION_FAILED,
                        f"decision cycle {cycle_id} belongs to turn"
                        f" {cycle[0]}, not {turn_id}",
                    )
                durable = self._conn.execute(
                    "SELECT " + ", ".join(_STATUS_COLUMNS)
                    + " FROM planner_execution_status WHERE decision_cycle_id = ?",
                    (cycle_id,),
                ).fetchone()
                if durable is not None:
                    return self._replay(
                        cycle_id=cycle_id,
                        turn_id=turn_id,
                        outcome=outcome,
                        trace=trace,
                        durable_status=durable,
                    )
                created_at = _now()
                self._conn.execute(
                    "INSERT INTO planner_execution_status ("
                    " decision_cycle_id, status, error_code, created_at"
                    ") VALUES (?, ?, ?, ?)",
                    (
                        cycle_id,
                        status.status.value,
                        status.error_code,
                        created_at,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO planner_evaluation ("
                    " planner_evaluation_id, decision_cycle_id,"
                    " frontier_candidate_ids, ranked_candidate_ids,"
                    " factor_trace, planner_version, policy_profile_version,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        evaluation.planner_evaluation_id,
                        cycle_id,
                        _array_document(evaluation.frontier_candidate_ids),
                        _array_document(_ranked_candidate_ids(evaluation)),
                        factor_trace_document(
                            _trace_document_of(evaluation, trace)
                        ),
                        evaluation.planner_version,
                        evaluation.policy_version,
                        created_at,
                    ),
                )
                if decision is not None:
                    self._conn.execute(
                        "INSERT INTO planner_decision ("
                        " planner_decision_id, decision_cycle_id, decision,"
                        " selected_candidate_id, no_target_reason,"
                        " planner_evaluation_id, created_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            decision.planner_decision_id,
                            cycle_id,
                            decision.decision.value,
                            (
                                None
                                if decision.selected_candidate_id is None
                                else str(decision.selected_candidate_id)
                            ),
                            decision.no_target_reason,
                            decision.planner_evaluation_id,
                            created_at,
                        ),
                    )
                    cursor = self._conn.execute(
                        "UPDATE decision_cycle SET planner_decision_id = ?"
                        " WHERE decision_cycle_id = ?",
                        (decision.planner_decision_id, cycle_id),
                    )
                    if cursor.rowcount != 1:
                        # The cycle was read above inside this transaction;
                        # a miss here is a state the unit cannot explain —
                        # raise so the whole unit rolls back rather than
                        # committing rows whose back-reference is missing.
                        raise RuntimeError(
                            "decision_cycle.planner_decision_id UPDATE"
                            f" matched no row for {cycle_id}"
                        )
                self._conn.execute(
                    "INSERT INTO runtime_decision_outcome ("
                    " turn_id, decision_cycle_id, outcome, reason_codes,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT(turn_id) DO UPDATE SET"
                    " decision_cycle_id = excluded.decision_cycle_id,"
                    " outcome = excluded.outcome,"
                    " reason_codes = excluded.reason_codes,"
                    " created_at = excluded.created_at",
                    (
                        turn_id,
                        cycle_id,
                        runtime_outcome.value,
                        _array_document(reason_codes),
                        created_at,
                    ),
                )
                written = self._read_cycle_records(cycle_id, turn_id)
                assert written is not None  # the unit wrote the status row above
                return Ok(written)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def _replay(
        self,
        *,
        cycle_id: DecisionCycleId,
        turn_id: TurnId,
        outcome: PlanningOutcome,
        trace: PlannerTrace | None,
        durable_status: sqlite3.Row,
    ) -> Result[PlannerCycleRecords]:
        """The durable records for a cycle that already carries a status row.

        A re-entry is a replay only if it *is* the same unit: the status word
        with its error code, the evaluation's five derived values — the two
        id lists, the ``factor_trace`` **document** (P9-0: the candidates, the
        prose and the provenance word are compared together, which is the
        same agreement the bare prose used to carry plus the candidate trace
        beside it), and the two version words — and the decision (id, word,
        selected candidate, reason, evaluation link) must agree with the
        durable rows. A difference is a refusal — returning the durable
        records for a submission that contradicts them would make every
        subsequent read a guess (elc/planner/records.py, judgement 3).

        A durable row written before P9-0 carries the legacy prose array, so
        a post-cut re-entry of *that* cycle compares a document against lines
        and is refused: a decoder cannot vouch that a structured submission
        and a pre-cut row are the same unit, and guessing would be the one
        thing this path exists to prevent (judgement 9's revisit names the
        migration that would re-encode such rows).

        Nothing is written on this path, which is what makes RA §23's two
        Planner-side crash windows hold: a re-entry cannot produce a second
        evaluation or a second decision.
        """

        status = outcome.execution_status
        if str(durable_status[1]) != status.status.value or (
            _optional(durable_status[2]) != status.error_code
        ):
            return _err(
                DomainErrorCode.CONFLICT,
                f"decision cycle {cycle_id} is already durable with status"
                f" {durable_status[1]} (error_code {durable_status[2]!r});"
                f" the submitted status {status.status.value} (error_code"
                f" {status.error_code!r}) would contradict it",
            )
        durable = self._read_cycle_records(cycle_id, turn_id)
        assert durable is not None  # the status row was just read
        evaluation = outcome.evaluation
        submitted = (
            evaluation.frontier_candidate_ids,
            _ranked_candidate_ids(evaluation),
            _trace_document_of(evaluation, trace),
            str(evaluation.planner_version),
            str(evaluation.policy_version),
        )
        stored = (
            durable.evaluation.frontier_candidate_ids,
            durable.evaluation.ranked_candidate_ids,
            durable.evaluation.factor_trace,
            durable.evaluation.planner_version,
            durable.evaluation.policy_profile_version,
        )
        if submitted != stored:
            return _err(
                DomainErrorCode.CONFLICT,
                f"decision cycle {cycle_id} is already durable with a"
                " different evaluation; a replay must be the same unit",
            )
        if durable.decision != outcome.decision:
            return _err(
                DomainErrorCode.CONFLICT,
                f"decision cycle {cycle_id} is already durable with a"
                " different decision; a replay must be the same unit",
            )
        return Ok(durable)

    def _read_cycle_records(
        self, decision_cycle_id: DecisionCycleId, turn_id: TurnId
    ) -> PlannerCycleRecords | None:
        """Read one cycle's rows back inside the caller's transaction.

        ``None`` when the cycle has no status row — the write face returns
        this only after its own unit wrote one, so the ``None`` arm is the
        honest shape of "no unit ran", never a state the unit produces.
        The evaluation is read **by cycle**: this face writes one per cycle
        (the status row's key is the replay guard), so the two reads agree by
        construction.
        """

        status_row = self._conn.execute(
            "SELECT " + ", ".join(_STATUS_COLUMNS)
            + " FROM planner_execution_status WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        if status_row is None:
            return None
        evaluation_row = self._conn.execute(
            "SELECT " + ", ".join(_EVALUATION_COLUMNS)
            + " FROM planner_evaluation WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        assert evaluation_row is not None  # the unit writes both together
        decision_row = self._conn.execute(
            "SELECT " + ", ".join(_DECISION_COLUMNS)
            + " FROM planner_decision WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        outcome_row = self._conn.execute(
            "SELECT " + ", ".join(_OUTCOME_COLUMNS)
            + " FROM runtime_decision_outcome WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        return PlannerCycleRecords(
            execution_status=_status_record(status_row),
            evaluation=_evaluation_record(evaluation_row),
            decision=(
                None if decision_row is None else _decision_record(decision_row)
            ),
            runtime_decision_outcome=(
                None if outcome_row is None else _outcome_record(outcome_row)
            ),
        )

    # -- reads -------------------------------------------------------------

    def get_planner_execution_status(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[PlannerExecutionStatusRecord | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_STATUS_COLUMNS)
            + " FROM planner_execution_status WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        return Ok(None if row is None else _status_record(row))

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlannerEvaluationRecord | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_EVALUATION_COLUMNS)
            + " FROM planner_evaluation WHERE planner_evaluation_id = ?",
            (planner_evaluation_id,),
        ).fetchone()
        return Ok(None if row is None else _evaluation_record(row))

    def get_planner_decision(
        self, planner_decision_id: PlannerDecisionId
    ) -> Result[PlannerDecision | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_DECISION_COLUMNS)
            + " FROM planner_decision WHERE planner_decision_id = ?",
            (planner_decision_id,),
        ).fetchone()
        return Ok(None if row is None else _decision_record(row))

    def get_planner_decision_for_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[PlannerDecision | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_DECISION_COLUMNS)
            + " FROM planner_decision WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        return Ok(None if row is None else _decision_record(row))

    def get_runtime_decision_outcome(
        self, turn_id: TurnId
    ) -> Result[RuntimeDecisionOutcome | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_OUTCOME_COLUMNS)
            + " FROM runtime_decision_outcome WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        return Ok(None if row is None else _outcome_record(row))

    def get_planner_decision_id(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[str | None]:
        """The ``decision_cycle.planner_decision_id`` back-reference.

        ``Ok(None)`` covers both "no such cycle" and "a cycle with no
        decision"; the cycle row is ``SqliteDecisionCycleStore``'s, and its
        own read tells the two apart.
        """

        row = self._conn.execute(
            "SELECT planner_decision_id FROM decision_cycle"
            " WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return Ok(None)
        return Ok(str(row[0]))
