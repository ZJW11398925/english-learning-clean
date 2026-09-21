"""SQLite durable store for the Teaching domain (Phase 3 P3-1A).

TASK-OPI-2babb21e-….17 ③④. The Teaching domain owns TeachingMoment /
TeachingLockLease / Gate lifecycle (docs/DOMAIN_MODEL.md §14), so its
durable executor lives in the domain package — the conversation-store and
learning-store precedent. The Gate's *decision policy* stays pure in
elc.teaching.gate; this module only executes the CP2 commit point durably.

CP2 (docs/RUNTIME_ARCHITECTURE.md §6 "CP2 — Decision durable"; §4 step
10B): one short transaction creates, together and atomically,

1. GateExecutionStatus(SUCCEEDED) — the execution fact,
2. GateDecision(ALLOW) — the authorization decision,
3. TeachingMoment — committed with lifecycle_state = OPENING (the moment
   is authorized → acquires the lock → becomes OPENING inside the unit;
   AUTHORIZED is *not* removed from the STATE_MACHINES §1 vocabulary),
4. active_teaching_lock(conversation_id UNIQUE, moment_id, state_version=1),
5. GenerationActionIntent(TEACHING_OPEN, PREPARED) — the first teaching
   action, dispatched by P3-1B.

Five facts or none: any failure (including a lock race lost inside the
unit) rolls the whole thing back — a moment without a lock, or a lock
without a moment, must be unreachable (STATE_MACHINES §9; RUNTIME §24.2
"Gate ALLOW 不等于锁已预留").

DENY: two facts in one short transaction — GateExecutionStatus(SUCCEEDED)
+ GateDecision(DENY) — and no Moment / Lock / Action.

DEGRADED: one fact — GateExecutionStatus(DEGRADED) with the
missing_or_unknown fact keys and **no** GateDecision row (docs/
DATA_MODEL.md §14.1: never a synthetic DENY).

Fencing (TASK-…17 ⑨): every write checks the store epoch against the
newest durable epoch and refuses fenced work before anything is written
(StaleStoreEpochError family), and CP2 additionally refuses a turn owned by
another epoch (AUTHORITY_VIOLATION) — the canonicalize_assistant_turn
paradigm.

All SQL is a fixed literal with bound parameters — no identifier assembly.
JSON columns follow migration 0007's storage note (the 0004 qualifiers
precedent).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ActionId,
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    EvidenceModality,
    GateDecisionId,
    MomentId,
    Ok,
    PersonaId,
    PolicyVersion,
    Result,
    RuntimeEpoch,
    TurnId,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
)
from elc.teaching.types import (
    AuthorizationBasis,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)

__all__ = [
    "CP2OpenRequest",
    "SqliteTeachingStore",
    "StaleStoreEpochError",
]

T = TypeVar("T")

#: active_teaching_lock.state_version written by CP2 (DATA_MODEL §18: the
#: durable one-focus lock row; Local V1 needs no expiry/heartbeat).
LOCK_STATE_VERSION_AT_OPEN = 1


class StaleStoreEpochError(StaleEpochError):
    """A teaching-store write was fenced by a newer runtime epoch."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


@dataclass(frozen=True)
class CP2OpenRequest:
    """The five facts one ALLOW commit writes (RUNTIME §6 CP2 / §4 10B)."""

    gate_execution_status: GateExecutionStatusRecord
    gate_decision: GateDecisionRecord
    moment: TeachingMomentRecord
    action: GenerationActionIntentRecord
    owner_epoch: int


def _target_document(target: TeachingTargetRef) -> str:
    return json.dumps(
        target.as_document(), sort_keys=True, separators=(",", ":")
    )


def _targets_document(targets: tuple[TeachingTargetRef, ...]) -> str:
    return json.dumps(
        [target.as_document() for target in targets],
        sort_keys=True,
        separators=(",", ":"),
    )


def _target_from_document(document: object) -> TeachingTargetRef:
    assert isinstance(document, dict)  # our own durable encoding
    return TeachingTargetRef(
        target_type=str(document["target_type"]),
        target_id=str(document["target_id"]),
    )


def _array_document(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), sort_keys=True, separators=(",", ":"))


def _array_from_document(document: str) -> tuple[str, ...]:
    loaded = json.loads(document)
    return tuple(str(item) for item in loaded)


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


class SqliteTeachingStore:
    """Durable Teaching rows: CP2, Gate facts, moment + lock reads."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> RuntimeEpoch:
        return RuntimeEpoch(self._fence.current)

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"teaching store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- CP2: the five-fact atomic open ------------------------------------

    def open_teaching_moment(self, request: CP2OpenRequest) -> Result[MomentId]:
        """CP2 ALLOW: five facts, one short transaction (§6; §4 step 10B).

        Idempotent replay: an existing moment for the same decision cycle
        returns that moment and writes nothing (the crash-after-CP2
        "继续同 action_id" resume path, RUNTIME §23). The durable
        moment/first-action pair stays canonical on a replay — see the
        branch comment below (review F6).
        """

        moment = request.moment
        if moment.lifecycle_state != MomentState.OPENING:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "CP2 commits a moment as OPENING (AUTHORIZED is the "
                "pre-lock state inside the unit; STATE_MACHINES §1/§9)",
            )
        if request.gate_decision.decision != GateDecisionValue.ALLOW:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "CP2 opens a moment only on GateDecision(ALLOW) — a DENY "
                "never creates a Moment (STATE_MACHINES §2)",
            )
        if request.gate_execution_status.status != (
            GateExecutionStatusValue.SUCCEEDED
        ):
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "CP2 requires GateExecutionStatus(SUCCEEDED)",
            )
        if moment.gate_decision_id != request.gate_decision.gate_decision_id:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "the moment must reference the GateDecision it was "
                "authorized by",
            )
        if moment.decision_cycle_id != request.gate_decision.decision_cycle_id:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "the moment must be bound to the deciding cycle",
            )

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                turn_owner = self._conn.execute(
                    "SELECT owner_epoch FROM turn_record WHERE turn_id = ?",
                    (request.action.turn_id,),
                ).fetchone()
                if turn_owner is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"turn record not found: {request.action.turn_id}",
                    )
                if int(turn_owner[0]) != request.owner_epoch:
                    return _err(
                        DomainErrorCode.AUTHORITY_VIOLATION,
                        f"owner_epoch={turn_owner[0]} fenced by"
                        f" current epoch={request.owner_epoch}",
                    )

                existing = self._conn.execute(
                    "SELECT moment_id FROM teaching_moment"
                    " WHERE decision_cycle_id = ?",
                    (moment.decision_cycle_id,),
                ).fetchone()
                if existing is not None:
                    # Replay: the durable (moment, first action) pair is
                    # canonical. A re-dispatch that carries a different
                    # action_id (a freshly minted one) is discarded, not
                    # adopted — the caller reads the canonical action back
                    # through the generation store (get_action_for_turn),
                    # which is exactly what the coordinator's replay path
                    # does. No second action row can exist for one cycle's
                    # moment (review F6: named here, not silently passed).
                    return Ok(MomentId(str(existing[0])))

                created_at = moment.created_at or _now()
                self._conn.execute(
                    "INSERT INTO gate_execution_status ("
                    " gate_execution_status_id, decision_cycle_id, moment_id,"
                    " gate_context, authorization_basis,"
                    " authorization_status, status, missing_or_unknown,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.gate_execution_status.gate_execution_status_id,
                        request.gate_execution_status.decision_cycle_id,
                        None,  # OPEN binds the DecisionCycle, not a moment
                        request.gate_execution_status.gate_context.value,
                        request.gate_execution_status.authorization_basis.value,
                        request.gate_execution_status.authorization_status,
                        request.gate_execution_status.status.value,
                        _array_document(
                            request.gate_execution_status.missing_or_unknown
                        ),
                        request.gate_execution_status.created_at or created_at,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO gate_decision ("
                    " gate_decision_id, decision_cycle_id, candidate_id,"
                    " context, decision, reason_codes, policy_version,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.gate_decision.gate_decision_id,
                        request.gate_decision.decision_cycle_id,
                        request.gate_decision.candidate_id,
                        request.gate_decision.context.value,
                        request.gate_decision.decision.value,
                        _array_document(request.gate_decision.reason_codes),
                        request.gate_decision.policy_version,
                        request.gate_decision.created_at or created_at,
                    ),
                )
                self._insert_moment(moment, created_at)
                self._conn.execute(
                    "INSERT INTO generation_action_intent ("
                    " action_id, turn_id, decision_cycle_id, moment_id,"
                    " assistant_turn_id, action_type, generation_contract_id,"
                    " status, attempt_count, owner_epoch, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.action.action_id,
                        request.action.turn_id,
                        request.action.decision_cycle_id,
                        request.action.moment_id,
                        request.action.assistant_turn_id,
                        GenerationActionType(request.action.action_type).value,
                        request.action.generation_contract_id,
                        GenerationActionStatus(request.action.status).value,
                        request.action.attempt_count,
                        request.action.owner_epoch
                        if request.action.owner_epoch is not None
                        else request.owner_epoch,
                        request.action.created_at or created_at,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO active_teaching_lock ("
                    " conversation_id, moment_id, state_version"
                    ") VALUES (?, ?, ?)",
                    (
                        moment.conversation_id,
                        moment.moment_id,
                        LOCK_STATE_VERSION_AT_OPEN,
                    ),
                )
                return Ok(moment.moment_id)
        except sqlite3.IntegrityError as exc:
            # Includes the lost lock race: the whole unit rolled back, so
            # no half-open moment is reachable.
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def record_gate_denial(
        self,
        status: GateExecutionStatusRecord,
        decision: GateDecisionRecord,
    ) -> Result[GateDecisionId]:
        """DENY: GateExecutionStatus(SUCCEEDED) + GateDecision(DENY), one
        short transaction; no Moment / Lock / Action (STATE_MACHINES §2)."""

        if decision.decision != GateDecisionValue.DENY:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "record_gate_denial carries a DENY decision",
            )
        if not decision.reason_codes:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a DENY carries at least one BF-03 reason code",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                created_at = _now()
                self._insert_execution_status(status, created_at, moment_id=None)
                self._conn.execute(
                    "INSERT INTO gate_decision ("
                    " gate_decision_id, decision_cycle_id, candidate_id,"
                    " context, decision, reason_codes, policy_version,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        decision.gate_decision_id,
                        decision.decision_cycle_id,
                        decision.candidate_id,
                        decision.context.value,
                        decision.decision.value,
                        _array_document(decision.reason_codes),
                        decision.policy_version,
                        created_at,
                    ),
                )
                return Ok(decision.gate_decision_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def record_gate_degraded(
        self, status: GateExecutionStatusRecord
    ) -> Result[str]:
        """DEGRADED: one fact, no GateDecision (docs/DATA_MODEL.md §14.1)."""

        if status.status != GateExecutionStatusValue.DEGRADED:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "record_gate_degraded carries GateExecutionStatus(DEGRADED)",
            )
        if not status.missing_or_unknown:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a DEGRADED execution status names its missing_or_unknown"
                " fact keys",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._insert_execution_status(status, _now(), moment_id=None)
                return Ok(status.gate_execution_status_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    # -- reads --------------------------------------------------------------

    def get_active_moment(
        self, conversation_id: ConversationId
    ) -> Result[TeachingMomentRecord | None]:
        """The moment the conversation's durable lock points at (None when
        no teaching focus is active)."""

        row = self._conn.execute(
            "SELECT moment_id FROM active_teaching_lock"
            " WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return Ok(None)
        return self.get_moment(MomentId(str(row[0])))

    def get_moment(
        self, moment_id: MomentId
    ) -> Result[TeachingMomentRecord | None]:
        row = self._moment_row(moment_id)
        return Ok(None if row is None else self._moment_record(row))

    def get_lock_moment_id(
        self, conversation_id: ConversationId
    ) -> Result[MomentId | None]:
        """The raw lock row: which moment holds the conversation's
        one-focus guarantee (None = no lock)."""

        row = self._conn.execute(
            "SELECT moment_id FROM active_teaching_lock"
            " WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return Ok(None if row is None else MomentId(str(row[0])))

    def get_moment_for_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[TeachingMomentRecord | None]:
        """The moment opened by one decision cycle — the replay lookup
        (a cycle opens at most one moment; the ALLOW path is idempotent
        on it)."""

        row = self._conn.execute(
            "SELECT moment_id FROM teaching_moment WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        if row is None:
            return Ok(None)
        return self.get_moment(MomentId(str(row[0])))

    def get_gate_decisions(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[tuple[GateDecisionRecord, ...]]:
        rows = self._conn.execute(
            "SELECT gate_decision_id, decision_cycle_id, candidate_id,"
            " context, decision, reason_codes, policy_version, created_at"
            " FROM gate_decision WHERE decision_cycle_id = ?"
            " ORDER BY created_at, gate_decision_id",
            (decision_cycle_id,),
        ).fetchall()
        return Ok(
            tuple(
                GateDecisionRecord(
                    gate_decision_id=GateDecisionId(str(row[0])),
                    decision_cycle_id=DecisionCycleId(str(row[1])),
                    candidate_id=str(row[2]),
                    context=GateDecisionContext(str(row[3])),
                    decision=GateDecisionValue(str(row[4])),
                    reason_codes=_array_from_document(str(row[5])),
                    policy_version=PolicyVersion(str(row[6])),
                    created_at=_optional(row[7]),
                )
                for row in rows
            )
        )

    def get_gate_execution_statuses(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[tuple[GateExecutionStatusRecord, ...]]:
        rows = self._conn.execute(
            "SELECT gate_execution_status_id, decision_cycle_id, moment_id,"
            " gate_context, authorization_basis, authorization_status,"
            " status, missing_or_unknown, created_at"
            " FROM gate_execution_status WHERE decision_cycle_id = ?"
            " ORDER BY created_at, gate_execution_status_id",
            (decision_cycle_id,),
        ).fetchall()
        return Ok(
            tuple(
                GateExecutionStatusRecord(
                    gate_execution_status_id=str(row[0]),
                    decision_cycle_id=(
                        None
                        if row[1] is None
                        else DecisionCycleId(str(row[1]))
                    ),
                    moment_id=None if row[2] is None else MomentId(str(row[2])),
                    gate_context=GateDecisionContext(str(row[3])),
                    authorization_basis=AuthorizationBasis(str(row[4])),
                    authorization_status=str(row[5]),
                    status=GateExecutionStatusValue(str(row[6])),
                    missing_or_unknown=_array_from_document(str(row[7])),
                    created_at=_optional(row[8]),
                )
                for row in rows
            )
        )

    # -- internals ----------------------------------------------------------

    def _insert_execution_status(
        self,
        status: GateExecutionStatusRecord,
        created_at: str,
        moment_id: MomentId | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO gate_execution_status ("
            " gate_execution_status_id, decision_cycle_id, moment_id,"
            " gate_context, authorization_basis, authorization_status,"
            " status, missing_or_unknown, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                status.gate_execution_status_id,
                status.decision_cycle_id,
                status.moment_id if status.moment_id is not None else moment_id,
                status.gate_context.value,
                status.authorization_basis.value,
                status.authorization_status,
                status.status.value,
                _array_document(status.missing_or_unknown),
                status.created_at or created_at,
            ),
        )

    def _insert_moment(
        self, moment: TeachingMomentRecord, created_at: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO teaching_moment ("
            " moment_id, conversation_id, persona_id, source,"
            " decision_cycle_id, candidate_id, gate_decision_id,"
            " focus_target, supporting_targets, target_mode, learning_intent,"
            " evidence_modality, evidence_goal, preferred_support_ceiling,"
            " learning_snapshot_id, evidence_watermark, curriculum_version,"
            " content_version, policy_version, lifecycle_state,"
            " presentation_phase, attempt_index, support_level,"
            " completion_outcome, abort_reason, state_version, created_at,"
            " opened_at, teaching_terminal_at, closed_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                moment.moment_id,
                moment.conversation_id,
                moment.persona_id,
                MomentSource(moment.source).value,
                moment.decision_cycle_id,
                moment.candidate_id,
                moment.gate_decision_id,
                _target_document(moment.focus_target),
                _targets_document(moment.supporting_targets),
                moment.target_mode,
                moment.learning_intent,
                EvidenceModality(moment.evidence_modality).value,
                moment.evidence_goal,
                moment.preferred_support_ceiling,
                moment.learning_snapshot_id,
                moment.evidence_watermark,
                moment.curriculum_version,
                moment.content_version,
                moment.policy_version,
                MomentState(moment.lifecycle_state).value,
                PresentationPhase(moment.presentation_phase).value,
                moment.attempt_index,
                TeachingSupportLevel(moment.support_level).value,
                moment.completion_outcome,
                moment.abort_reason,
                moment.state_version,
                moment.created_at or created_at,
                moment.opened_at or created_at,
                moment.teaching_terminal_at,
                moment.closed_at,
            ),
        )

    def _moment_row(self, moment_id: MomentId) -> sqlite3.Row | None:
        # Column order: moment_id, conversation_id, persona_id, source,
        # decision_cycle_id, candidate_id, gate_decision_id, focus_target,
        # supporting_targets, target_mode, learning_intent, evidence_modality,
        # evidence_goal, preferred_support_ceiling, learning_snapshot_id,
        # evidence_watermark, curriculum_version, content_version,
        # policy_version, lifecycle_state, presentation_phase, attempt_index,
        # support_level, completion_outcome, abort_reason, state_version,
        # created_at, opened_at, teaching_terminal_at, closed_at.
        return self._conn.execute(
            "SELECT moment_id, conversation_id, persona_id, source,"
            " decision_cycle_id, candidate_id, gate_decision_id,"
            " focus_target, supporting_targets, target_mode, learning_intent,"
            " evidence_modality, evidence_goal, preferred_support_ceiling,"
            " learning_snapshot_id, evidence_watermark, curriculum_version,"
            " content_version, policy_version, lifecycle_state,"
            " presentation_phase, attempt_index, support_level,"
            " completion_outcome, abort_reason, state_version, created_at,"
            " opened_at, teaching_terminal_at, closed_at"
            " FROM teaching_moment WHERE moment_id = ?",
            (moment_id,),
        ).fetchone()

    def _moment_record(self, row: sqlite3.Row) -> TeachingMomentRecord:
        return TeachingMomentRecord(
            moment_id=MomentId(str(row[0])),
            conversation_id=ConversationId(str(row[1])),
            persona_id=None if row[2] is None else PersonaId(str(row[2])),
            source=MomentSource(str(row[3])),
            decision_cycle_id=DecisionCycleId(str(row[4])),
            candidate_id=str(row[5]),
            gate_decision_id=GateDecisionId(str(row[6])),
            focus_target=_target_from_document(json.loads(str(row[7]))),
            supporting_targets=tuple(
                _target_from_document(document)
                for document in json.loads(str(row[8]))
            ),
            target_mode=str(row[9]),
            learning_intent=str(row[10]),
            evidence_modality=EvidenceModality(str(row[11])),
            evidence_goal=_optional(row[12]),
            preferred_support_ceiling=_optional(row[13]),
            learning_snapshot_id=_optional(row[14]),
            evidence_watermark=(
                None if row[15] is None else int(row[15])
            ),
            curriculum_version=_optional(row[16]),
            content_version=_optional(row[17]),
            policy_version=_optional(row[18]),
            lifecycle_state=MomentState(str(row[19])),
            presentation_phase=PresentationPhase(str(row[20])),
            attempt_index=int(row[21]),
            support_level=TeachingSupportLevel(str(row[22])),
            completion_outcome=_optional(row[23]),
            abort_reason=_optional(row[24]),
            state_version=int(row[25]),
            created_at=_optional(row[26]),
            opened_at=_optional(row[27]),
            teaching_terminal_at=_optional(row[28]),
            closed_at=_optional(row[29]),
        )


def cp2_action_intent(
    *,
    turn_id: TurnId,
    moment_id: MomentId,
    decision_cycle_id: DecisionCycleId,
    action_id: ActionId,
    assistant_turn_id: str,
    generation_contract_id: str,
    owner_epoch: int,
) -> GenerationActionIntentRecord:
    """Build the CP2 §20 first action: TEACHING_OPEN at PREPARED with the
    moment link — the state P3-1B dispatches from (the persona-runtime
    ``action_intent_for_turn`` precedent, with the moment/cycle links the
    teaching path needs)."""

    return GenerationActionIntentRecord(
        action_id=action_id,
        turn_id=turn_id,
        decision_cycle_id=decision_cycle_id,
        moment_id=moment_id,
        assistant_turn_id=assistant_turn_id,
        action_type=GenerationActionType.TEACHING_OPEN,
        generation_contract_id=generation_contract_id,
        status=GenerationActionStatus.PREPARED,
        attempt_count=0,
        created_at=None,
        owner_epoch=RuntimeEpoch(owner_epoch),
    )
