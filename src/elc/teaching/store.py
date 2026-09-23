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

Owner-lineage fencing (P4-0 ②; DEC-…5ba74efc.68 C2): the two *normal*
moment-mutation faces — :meth:`SqliteTeachingStore.transition_moment` and
:meth:`SqliteTeachingStore.terminalize_moment` — additionally require the
moment's owning turn to belong to the current runtime epoch, along the
durable lineage Moment → decision_cycle_id → decision_cycle.turn_id →
turn_record.owner_epoch. A foreign-epoch moment is another process's live
work, so a normal mutation refuses it with AUTHORITY_VIOLATION and names
the explicit recovery channel; the only faces that may touch foreign-epoch
residue are the recovery sweep
(:meth:`SqliteTeachingStore.recover_orphan_teaching_locks`) and the
recovery adoption of the owning turn (``claim_turn_for_recovery``), which
moves the lineage on purpose rather than bypassing the fence.

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
    AttemptEvaluationId,
    AttemptId,
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
    UserTurnId,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
)
from elc.teaching.types import (
    ABORT_REASONS,
    ATTEMPT_OUTCOMES,
    COMPLETION_OUTCOMES,
    AbortReason,
    AnswerExposureState,
    AttemptEvaluationRecord,
    AttemptRecord,
    AuthorizationBasis,
    ExposureEstimateCertainty,
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

#: The canonical §5 / §6 / §7 word lists the store validates against (the
#: migration CHECKs are the durable enforcement of the same sets).
_ATTEMPT_OUTCOMES = ATTEMPT_OUTCOMES
_COMPLETION_OUTCOMES = COMPLETION_OUTCOMES
_ABORT_REASONS = ABORT_REASONS

#: The §15 column list every moment read selects, in the exact order
#: :meth:`SqliteTeachingStore._moment_record` unpacks it: moment_id,
#: conversation_id, persona_id, source, decision_cycle_id, candidate_id,
#: gate_decision_id, focus_target, supporting_targets, target_mode,
#: learning_intent, evidence_modality, evidence_goal,
#: preferred_support_ceiling, learning_snapshot_id, evidence_watermark,
#: curriculum_version, content_version, policy_version, lifecycle_state,
#: presentation_phase, attempt_index, support_level, completion_outcome,
#: abort_reason, state_version, created_at, opened_at, teaching_terminal_at,
#: closed_at. **One spelling**: the single-row read and the per-conversation
#: list read (P8-2) share it, so a second SELECT cannot silently rotate the
#: columns out from under the unpacker.
_MOMENT_COLUMNS = (
    "moment_id, conversation_id, persona_id, source,"
    " decision_cycle_id, candidate_id, gate_decision_id,"
    " focus_target, supporting_targets, target_mode, learning_intent,"
    " evidence_modality, evidence_goal, preferred_support_ceiling,"
    " learning_snapshot_id, evidence_watermark, curriculum_version,"
    " content_version, policy_version, lifecycle_state,"
    " presentation_phase, attempt_index, support_level,"
    " completion_outcome, abort_reason, state_version, created_at,"
    " opened_at, teaching_terminal_at, closed_at"
)

__all__ = [
    "CP2OpenRequest",
    "MomentTransition",
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


@dataclass(frozen=True)
class MomentTransition:
    """One CAS-guarded TeachingMoment advance (P3-1B).

    Every field is optional: a transition names only what it changes
    (``None`` = leave the column alone), so the ladder and the lifecycle
    move independently inside one short transaction. ``expected_state_
    version`` is the §20 compare-and-swap guard: a stale writer is refused
    instead of silently overwriting a newer state.
    """

    lifecycle_state: MomentState | None = None
    presentation_phase: PresentationPhase | None = None
    support_level: TeachingSupportLevel | None = None
    attempt_index: int | None = None
    completion_outcome: str | None = None
    abort_reason: str | None = None
    teaching_terminal_at: str | None = None
    closed_at: str | None = None
    opened_at: str | None = None


#: The generation action types that count as one delivered teaching turn
#: (TASK-…2.2 ⑦; the tuple mirrors elc.teaching.limits).
_TEACHING_TURN_ACTION_TYPES = (
    "TEACHING_OPEN",
    "TEACHING_HINT",
    "TEACHING_REVEAL",
    "TEACHING_EXPLANATION",
)


def _terminal_tail_refusal(
    state: MomentState, target: MomentState
) -> str | None:
    """The SM §1 tail rule at the durable boundary (None = allowed).

    STATE_MACHINES.md §1 lines 49-58 spell the tail out as two arms:

        COMPLETING / ABORTING → finalize teaching outcome → TEACHING_TERMINAL
        TEACHING_TERMINAL     → release TeachingLockLease
            ├─ resume needed → RESUMING
            └─ no resume ────→ CLOSED
        RESUMING              → delivered / failed → CLOSED

    so a terminal moment may legitimately move to RESUMING (the resume arm)
    *or* straight to CLOSED (the no-resume arm), and a RESUMING moment only
    closes. Any other target would resurrect an episode whose lock is
    already released; and CLOSED itself is only reached along that tail —
    closing a live moment from AWAITING_USER / EVALUATING / DECIDING would
    produce exactly the "terminal moment still holding its lock" state the
    coordinator declares unreachable (elc.runtime.controller).
    """

    if state is MomentState.TEACHING_TERMINAL and target not in (
        MomentState.RESUMING,
        MomentState.CLOSED,
    ):
        return (
            "a TEACHING_TERMINAL moment only resumes or closes"
            f" (STATE_MACHINES §1); {target.value} would resurrect a"
            " finished episode"
        )
    if state is MomentState.RESUMING and target is not MomentState.CLOSED:
        return (
            "a RESUMING moment only closes (STATE_MACHINES §1);"
            f" {target.value} would resurrect a finished episode"
        )
    if target is MomentState.CLOSED and state not in (
        MomentState.RESUMING,
        MomentState.TEACHING_TERMINAL,
    ):
        return (
            "CLOSED is reached from TEACHING_TERMINAL or RESUMING only"
            f" (STATE_MACHINES §1); closing a {state.value} moment would"
            " leave the TeachingLockLease held by a closed episode"
        )
    return None


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

    def _owning_epoch_refusal(self, moment_id: MomentId) -> DomainError | None:
        """The owner-lineage fence of the two normal *lifecycle* mutation
        faces — ``transition_moment`` / ``terminalize_moment`` (P4-0 ②;
        DEC-…5ba74efc.68 C2).

        Fence scope (P4-1, review F4 disposition DEC-…5ba74efc.96): "the two
        normal mutation faces" means exactly that lifecycle pair. The two
        attempt-recording faces (``record_attempt`` /
        ``record_attempt_evaluation``) are store-epoch fenced *only* — a
        foreign-epoch moment's attempt rows are writable. The review ratified
        that as acceptable: the normal chain cannot reach it (a live epoch
        never opens a moment for a dead epoch's turn), the impact is bounded
        to the attempt counter and ``state_version``, and the residue is still
        collected by the recovery sweep below. P4-1 takes the documented
        qualifier rather than adding the fence: fencing the attempt faces
        changes the teaching write path's behaviour, which is a
        teaching-slice decision, not a relationship-slice one.

        The store-epoch fence answers "is this store still the newest
        process?" and raises, because a stale store is a programming error.
        This one answers a different question and returns an Err, because it
        is a *policy* outcome: the moment's owning turn belongs to another
        runtime epoch along the durable lineage

            Moment → decision_cycle_id → decision_cycle.turn_id →
            turn_record.owner_epoch

        so the moment is another process's live work. Before P4-0 the two
        normal mutation faces only checked the store fence, which meant a
        live epoch could advance (or terminalize) a dead epoch's episode
        without ever passing through recovery — the bypass this closes.

        Foreign-epoch residue has exactly two owner-sanctioned exits:

        1. the explicit recovery channel —
           :meth:`recover_orphan_teaching_locks`,
           ``ConversationCoordinator.recover_orphan_teaching`` and the
           ``StartupRecoveryScanner`` LOCK plan item
           (``RELEASE_ORPHAN_TEACHING_LOCK``) — which closes the orphan with
           ``SYSTEM_RECOVERY_ABORT`` and releases its lock; and
        2. ``claim_turn_for_recovery`` on the owning turn, which moves
           ``turn_record.owner_epoch`` to the current epoch on purpose
           (RUNTIME §24 restart ownership) and thereby makes the lineage
           current.

        ``None`` = the lineage row is missing (the caller's NOT_FOUND path
        owns that case) or the moment is ours.
        """

        row = self._conn.execute(
            "SELECT t.owner_epoch FROM teaching_moment m"
            " JOIN decision_cycle d"
            " ON d.decision_cycle_id = m.decision_cycle_id"
            " JOIN turn_record t ON t.turn_id = d.turn_id"
            " WHERE m.moment_id = ?",
            (moment_id,),
        ).fetchone()
        if row is None:
            return None
        owning = int(row[0])
        if owning == self._fence.current:
            return None
        return DomainError(
            code=DomainErrorCode.AUTHORITY_VIOLATION,
            message=(
                f"moment {moment_id} belongs to the turn of runtime epoch"
                f" {owning}; current epoch {self._fence.current} — a normal"
                " transition / terminalize never mutates another epoch's"
                " teaching work (STATE_MACHINES §9). Foreign-epoch residue"
                " is released through the explicit recovery channel:"
                " ConversationCoordinator.recover_orphan_teaching /"
                " StartupRecoveryScanner"
                " (RELEASE_ORPHAN_TEACHING_LOCK), or claim the owning turn"
                " for recovery first"
            ),
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
        short transaction; no Moment / Lock / Action (STATE_MACHINES §2).

        Idempotent on the fact ids (review F1): a same-turn re-entry that
        already recorded this decision gets the durable row back instead of
        a PRIMARY KEY conflict — the durable fact is canonical, and a
        re-entry never rewrites a Gate outcome.
        """

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
                if self._gate_fact_recorded(
                    status.gate_execution_status_id,
                    decision.gate_decision_id,
                ):
                    return Ok(decision.gate_decision_id)
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

    def record_gate_allow(
        self,
        status: GateExecutionStatusRecord,
        decision: GateDecisionRecord,
    ) -> Result[GateDecisionId]:
        """ALLOW: GateExecutionStatus(SUCCEEDED) + GateDecision(ALLOW), one
        short transaction.

        The continuation authorization trace writes this pair: a
        USER_REQUESTED_CONTINUE that the Gate authorized must be as durable
        as a denial, or a re-entry could not tell "allowed and not yet
        executed" from "never decided". An OPEN ALLOW is *not* this face —
        it is the CP2 five-fact unit (elc.teaching.store.
        open_teaching_moment), because an opening authorization is never
        held without its Moment.

        Idempotent on the fact ids, like the DENY face (review F1): the
        continuation facts are deterministic per turn, so a second call
        replays the durable pair.
        """

        if decision.decision != GateDecisionValue.ALLOW:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "record_gate_allow carries an ALLOW decision",
            )
        if decision.reason_codes:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "an ALLOW carries no DENY reason codes",
            )
        if status.status is not GateExecutionStatusValue.SUCCEEDED:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "an ALLOW carries GateExecutionStatus(SUCCEEDED)",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                if self._gate_fact_recorded(
                    status.gate_execution_status_id,
                    decision.gate_decision_id,
                ):
                    return Ok(decision.gate_decision_id)
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
        """DEGRADED: one fact, no GateDecision (docs/DATA_MODEL.md §14.1).

        Idempotent on the fact id (review F1): the execution-status row is
        the whole trace of the degradation, so a re-entry replays it.
        """

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
                if self._gate_fact_recorded(
                    status.gate_execution_status_id, None
                ):
                    return Ok(status.gate_execution_status_id)
                self._insert_execution_status(status, _now(), moment_id=None)
                return Ok(status.gate_execution_status_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def _gate_fact_recorded(
        self,
        status_id: str,
        decision_id: GateDecisionId | None,
    ) -> bool:
        """True when the durable Gate facts of one decision already exist.

        The caller holds the transaction; the check is the replay guard of
        the three record_gate_* faces (review F1). A status row alone is
        the DEGRADED shape; a (status, decision) pair is the SUCCEEDED one.
        """

        existing_status = self._conn.execute(
            "SELECT 1 FROM gate_execution_status"
            " WHERE gate_execution_status_id = ?",
            (status_id,),
        ).fetchone()
        if existing_status is None:
            return False
        if decision_id is not None:
            existing_decision = self._conn.execute(
                "SELECT 1 FROM gate_decision WHERE gate_decision_id = ?",
                (decision_id,),
            ).fetchone()
            return existing_decision is not None
        return True

    # -- P3-1B: attempts, evaluations, lifecycle ----------------------------

    def record_attempt(self, attempt: AttemptRecord) -> Result[AttemptId]:
        """One durable AttemptRecord (DATA_MODEL §17) plus the moment's
        attempt counter, in ONE short transaction.

        The moment must be in its EVALUATING slot (STATE_MACHINES §1:
        AWAITING_USER → TeachingResponseEnvelope → optional attempt →
        EVALUATING) — a terminal / closed moment has no attempts, and an
        attempt recorded outside the evaluating slot would be an out-of-order
        write. ``attempt_index`` is validated against the moment's durable
        counter (UNIQUE(moment_id, attempt_index) is the §25 identity).

        Idempotency (review F3): the identity of an attempt is *(moment, user
        turn)* — one user turn contributes at most one attempt to a moment.
        Both the attempt id and that pair are checked before the insert, so a
        re-entry after a crash between the attempt and its evaluation returns
        the durable attempt instead of recording a second one (which would
        both inflate the §8 attempt budget and leave the first evaluation's
        ``evidence_proposal_refs`` pointing at a different attempt).

        Fencing (P4-1 review F4): this face is *store-epoch* fenced only, not
        owner-lineage fenced — a foreign-epoch moment's attempt rows are
        writable; see :meth:`_owning_epoch_refusal` for the ratified reasoning
        and the recovery sweep that collects the residue.
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._conn.execute(
                    "SELECT attempt_id, attempt_index FROM attempt_record"
                    " WHERE attempt_id = ? OR (moment_id = ? AND"
                    " user_turn_id = ?) ORDER BY attempt_index",
                    (
                        attempt.attempt_id,
                        attempt.moment_id,
                        attempt.user_turn_id,
                    ),
                ).fetchone()
                if existing is not None:
                    # Replay: the durable attempt is canonical. A re-entry
                    # that re-derived a *different* attempt id (because the
                    # moment's counter had already moved) is deliberately
                    # NOT adopted here — the durable row wins.
                    return Ok(AttemptId(str(existing[0])))
                moment = self._moment_row(MomentId(attempt.moment_id))
                if moment is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"moment not found: {attempt.moment_id}",
                    )
                state = MomentState(str(moment[19]))
                if state is not MomentState.EVALUATING:
                    return _err(
                        DomainErrorCode.VALIDATION_FAILED,
                        "an attempt is recorded in the moment's EVALUATING"
                        f" slot (STATE_MACHINES §1); moment {attempt.moment_id}"
                        f" is {state.value}",
                    )
                recorded = int(moment[21])
                if attempt.attempt_index != recorded + 1:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        "attempt_index must continue the moment's counter"
                        f" ({recorded} → {recorded + 1}); got"
                        f" {attempt.attempt_index}",
                    )
                created_at = attempt.created_at or _now()
                self._conn.execute(
                    "INSERT INTO attempt_record ("
                    " attempt_id, moment_id, attempt_index, user_turn_id,"
                    " support_level_before_attempt, answer_exposure_state,"
                    " exposure_estimate_id, support_attribution_certainty,"
                    " support_attribution_basis, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        attempt.attempt_id,
                        attempt.moment_id,
                        attempt.attempt_index,
                        attempt.user_turn_id,
                        attempt.support_level_before_attempt.value,
                        attempt.answer_exposure_state.value,
                        attempt.exposure_estimate_id,
                        attempt.support_attribution_certainty.value,
                        attempt.support_attribution_basis,
                        created_at,
                    ),
                )
                self._conn.execute(
                    "UPDATE teaching_moment"
                    " SET attempt_index = ?, state_version = state_version + 1"
                    " WHERE moment_id = ? AND state_version = ?",
                    (attempt.attempt_index, attempt.moment_id, int(moment[25])),
                )
                return Ok(attempt.attempt_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def record_attempt_evaluation(
        self, evaluation: AttemptEvaluationRecord
    ) -> Result[AttemptEvaluationId]:
        """One durable AttemptEvaluationRecord (DATA_MODEL §17).

        §17's normative write-order rule — "必须在下一不可逆教学动作前
        durable" — is enforced by *ordering* (the coordinator writes this
        before it creates the next teaching action) and by the schema: the
        row's FK to attempt_record means an evaluation can never exist
        without its attempt, and UNIQUE(attempt_id) means a second
        evaluation of the same attempt is refused rather than silently
        appended. A replay of the same evaluation id returns Ok.

        Fencing (P4-1 review F4): like ``record_attempt``, this face is
        *store-epoch* fenced only, not owner-lineage fenced — see
        :meth:`_owning_epoch_refusal` for the ratified reasoning.
        """

        if evaluation.outcome not in _ATTEMPT_OUTCOMES:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "outcome must be one of the STATE_MACHINES §5 five values"
                f" (got {evaluation.outcome!r})",
            )
        if not 0.0 <= evaluation.confidence <= 1.0:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "confidence must be within [0, 1] (got"
                f" {evaluation.confidence})",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._conn.execute(
                    "SELECT attempt_evaluation_id"
                    " FROM attempt_evaluation_record"
                    " WHERE attempt_evaluation_id = ?",
                    (evaluation.attempt_evaluation_id,),
                ).fetchone()
                if existing is not None:
                    return Ok(evaluation.attempt_evaluation_id)
                self._conn.execute(
                    "INSERT INTO attempt_evaluation_record ("
                    " attempt_evaluation_id, moment_id, attempt_id,"
                    " evaluator_id, evaluator_version, outcome, confidence,"
                    " evidence_proposal_refs, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        evaluation.attempt_evaluation_id,
                        evaluation.moment_id,
                        evaluation.attempt_id,
                        evaluation.evaluator_id,
                        evaluation.evaluator_version,
                        evaluation.outcome,
                        evaluation.confidence,
                        _array_document(evaluation.evidence_proposal_refs),
                        evaluation.created_at or _now(),
                    ),
                )
                return Ok(evaluation.attempt_evaluation_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def transition_moment(
        self,
        moment_id: MomentId,
        transition: MomentTransition,
        expected_state_version: int,
    ) -> Result[TeachingMomentRecord]:
        """One CAS-guarded moment advance (STATE_MACHINES §20).

        Only the named columns move; ``state_version`` always advances.
        CLOSED is final — a closed moment is never reopened by a later
        caller (SM §2 "Closed 不允许 reopen"; the refusal is here, at the
        durable boundary, not only in the caller).

        P3-2 (SM §1 graph at the durable boundary, the CLOSED precedent):
        the *post-terminal tail* is one-way too. From TEACHING_TERMINAL the
        legal targets are RESUMING (the resume arm) and CLOSED (the
        no-resume arm); from RESUMING the only legal target is CLOSED; and
        CLOSED is only reachable along that tail — closing a live moment
        directly would leave a closed episode still holding its
        TeachingLockLease. A ladder-only move (no lifecycle target) stays
        free — it does not touch the lifecycle column at all.

        P4-0 ②: a foreign-epoch moment is refused before the CAS is even
        evaluated (``_owning_epoch_refusal``) — authority beats staleness,
        and the refusal names the recovery channel that may release the
        residue.
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                row = self._moment_row(moment_id)
                if row is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"moment not found: {moment_id}",
                    )
                lineage = self._owning_epoch_refusal(moment_id)
                if lineage is not None:
                    return Err(lineage)
                current = int(row[25])
                if current != expected_state_version:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        "moment state_version is"
                        f" {current}, expected {expected_state_version}",
                    )
                state = MomentState(str(row[19]))
                if state is MomentState.CLOSED:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"moment {moment_id} is CLOSED — closed moments are"
                        " never reopened (STATE_MACHINES §2)",
                    )
                target = transition.lifecycle_state
                if target is not None:
                    tail_error = _terminal_tail_refusal(state, target)
                    if tail_error is not None:
                        return _err(DomainErrorCode.CONFLICT, tail_error)
                assignments: list[str] = []
                values: list[object] = []
                for column, value in (
                    (
                        "lifecycle_state",
                        None
                        if transition.lifecycle_state is None
                        else transition.lifecycle_state.value,
                    ),
                    (
                        "presentation_phase",
                        None
                        if transition.presentation_phase is None
                        else transition.presentation_phase.value,
                    ),
                    (
                        "support_level",
                        None
                        if transition.support_level is None
                        else transition.support_level.value,
                    ),
                    ("attempt_index", transition.attempt_index),
                    ("completion_outcome", transition.completion_outcome),
                    ("abort_reason", transition.abort_reason),
                    ("teaching_terminal_at", transition.teaching_terminal_at),
                    ("closed_at", transition.closed_at),
                    ("opened_at", transition.opened_at),
                ):
                    if value is None:
                        continue
                    assignments.append(f"{column} = ?")
                    values.append(value)
                assignments.append("state_version = state_version + 1")
                values.extend([moment_id, expected_state_version])
                self._conn.execute(
                    "UPDATE teaching_moment SET "
                    + ", ".join(assignments)
                    + " WHERE moment_id = ? AND state_version = ?",
                    tuple(values),
                )
                updated = self._moment_row(moment_id)
                assert updated is not None  # the CAS above kept the row
                return Ok(self._moment_record(updated))
        except sqlite3.IntegrityError as exc:
            # e.g. the completion_outcome / abort_reason CHECK vocabularies
            return _err(DomainErrorCode.VALIDATION_FAILED, str(exc))

    def terminalize_moment(
        self,
        moment_id: MomentId,
        *,
        completion_outcome: str | None = None,
        abort_reason: str | None = None,
    ) -> Result[TeachingMomentRecord]:
        """TEACHING_TERMINAL — and the TeachingLockLease release — in ONE
        short transaction (STATE_MACHINES §1/§9; DATA_MODEL §18: "TEACHING_
        TERMINAL 与 lock release 同短事务提交").

        Exactly one closure is written, and it must match the state the
        moment is in: COMPLETING closes with a §6 outcome, ABORTING closes
        with a §7 reason (SM §1 "finalize teaching outcome"). The lock row
        is deleted in the same unit, so "moment terminal, lock still held"
        is unreachable.

        P4-0 ②: like ``transition_moment``, this normal mutation face
        refuses a foreign-epoch moment (AUTHORITY_VIOLATION naming the
        recovery channel) before anything is written.
        """

        if (completion_outcome is None) == (abort_reason is None):
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "a terminal moment carries exactly one closure: a"
                " completion_outcome (COMPLETING) or an abort_reason"
                " (ABORTING)",
            )
        if (
            completion_outcome is not None
            and completion_outcome not in _COMPLETION_OUTCOMES
        ):
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"{completion_outcome!r} is not a STATE_MACHINES §6"
                " completion outcome",
            )
        if abort_reason is not None and abort_reason not in _ABORT_REASONS:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"{abort_reason!r} is not a STATE_MACHINES §7 abort reason",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                row = self._moment_row(moment_id)
                if row is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"moment not found: {moment_id}",
                    )
                lineage = self._owning_epoch_refusal(moment_id)
                if lineage is not None:
                    return Err(lineage)
                state = MomentState(str(row[19]))
                if state is MomentState.TEACHING_TERMINAL:
                    # Replay: the durable terminal row is canonical.
                    return Ok(self._moment_record(row))
                expected = (
                    MomentState.COMPLETING
                    if completion_outcome is not None
                    else MomentState.ABORTING
                )
                if state is not expected:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"moment {moment_id} is {state.value}; it can only"
                        f" terminalize from {expected.value}",
                    )
                now = _now()
                self._conn.execute(
                    "UPDATE teaching_moment SET lifecycle_state = ?,"
                    " completion_outcome = ?, abort_reason = ?,"
                    " teaching_terminal_at = ?,"
                    " state_version = state_version + 1"
                    " WHERE moment_id = ? AND state_version = ?",
                    (
                        MomentState.TEACHING_TERMINAL.value,
                        completion_outcome,
                        abort_reason,
                        now,
                        moment_id,
                        int(row[25]),
                    ),
                )
                self._conn.execute(
                    "DELETE FROM active_teaching_lock WHERE moment_id = ?",
                    (moment_id,),
                )
                updated = self._moment_row(moment_id)
                assert updated is not None
                return Ok(self._moment_record(updated))
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.VALIDATION_FAILED, str(exc))

    def lock_moment_id(
        self, conversation_id: ConversationId
    ) -> Result[MomentId | None]:
        """The lock row as an Ok (the controller's ``observed_lock_state``
        reads it through this face; the raw query stays in the store)."""

        return self.get_lock_moment_id(conversation_id)

    def recover_orphan_teaching_locks(
        self, current_epoch: RuntimeEpoch
    ) -> Result[tuple[str, ...]]:
        """Startup recovery: release the locks of moments owned by an older
        runtime epoch (STATE_MACHINES §9 "startup recovery 通过 durable
        Moment state + runtime_epoch revalidate/release orphan lock";
        RUNTIME §22).

        A lock is *orphan* when the turn that owns its moment belongs to a
        runtime epoch other than the current one: the process that held the
        conversation's one-focus guarantee is gone, so its lock is not a
        mutual-exclusion fact any more — it is residue. Each orphan is
        closed in ONE short transaction: the moment becomes
        ABORTING → TEACHING_TERMINAL → CLOSED with the §7
        ``SYSTEM_RECOVERY_ABORT`` reason (no RESUMING delivery: the owning
        process died, so there is no conversation to return to — RA §23
        "resume 可 retry 或由下个 turn 自然恢复"), and the lock row is
        deleted, which is what unseals the conversation for a new request.

        Returns the recovered moment ids (empty when there is no orphan).

        P4-0 ②: this sweep is — with ``claim_turn_for_recovery`` — one of the
        two sanctioned exits for foreign-epoch residue, and therefore the
        *only lifecycle* face that mutates a moment its own epoch fence would
        refuse (it writes the rows directly, under the store-epoch fence,
        precisely because the owner-lineage fence of the normal faces exists
        to route the residue here). The two attempt-recording faces are not
        owner-lineage fenced at all (P4-1 review F4; see
        :meth:`_owning_epoch_refusal`).
        """

        rows = self._orphan_lock_rows(current_epoch)
        if not rows:
            return Ok(())
        recovered: list[str] = []
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                now = _now()
                for moment_id, lock_version, _state, moment_version in rows:
                    self._conn.execute(
                        "UPDATE teaching_moment SET lifecycle_state = ?,"
                        " abort_reason = ?, teaching_terminal_at = ?,"
                        " closed_at = ?, state_version = state_version + 1"
                        " WHERE moment_id = ? AND state_version = ?",
                        (
                            MomentState.CLOSED.value,
                            AbortReason.SYSTEM_RECOVERY_ABORT.value,
                            now,
                            now,
                            moment_id,
                            int(moment_version),
                        ),
                    )
                    self._conn.execute(
                        "DELETE FROM active_teaching_lock"
                        " WHERE moment_id = ? AND state_version = ?",
                        (moment_id, int(lock_version)),
                    )
                    recovered.append(str(moment_id))
                return Ok(tuple(recovered))
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def orphan_teaching_lock_moments(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        """The orphan-lock read face (P3-2 carry-over ①): the moment ids
        whose lock is residue of an older runtime epoch, in durable order.

        The pure-read half of :meth:`recover_orphan_teaching_locks` — one
        shared query, so the startup scan and the sweep can never disagree
        about which lock is residue. Writes nothing (the plan is the read;
        the coordinator's apply face is the write).
        """

        return tuple(
            str(row[0]) for row in self._orphan_lock_rows(current_epoch)
        )

    def _orphan_lock_rows(
        self, current_epoch: RuntimeEpoch
    ) -> list[sqlite3.Row]:
        """The durable rows of the orphan-lock JOIN (see the two faces)."""

        return self._conn.execute(
            "SELECT l.moment_id, l.state_version,"
            " m.lifecycle_state, m.state_version"
            " FROM active_teaching_lock l"
            " JOIN teaching_moment m ON m.moment_id = l.moment_id"
            " JOIN decision_cycle d ON d.decision_cycle_id ="
            "      m.decision_cycle_id"
            " JOIN turn_record t ON t.turn_id = d.turn_id"
            " WHERE t.owner_epoch != ?"
            " ORDER BY m.created_at, l.moment_id",
            (current_epoch,),
        ).fetchall()

    # -- P3-1B reads ---------------------------------------------------------

    def count_attempts(self, moment_id: MomentId) -> int:
        """The durable AttemptRecord count of one moment (the §8 attempt
        count; UNIQUE(moment_id, attempt_index) makes it exact)."""

        row = self._conn.execute(
            "SELECT COUNT(*) FROM attempt_record WHERE moment_id = ?",
            (moment_id,),
        ).fetchone()
        return 0 if row is None else int(row[0])

    def count_delivered_teaching_turns(self, moment_id: MomentId) -> int:
        """Delivered teaching turns of one moment (TASK-…2.2 ⑦): the
        TEACHING_OPEN / TEACHING_HINT / TEACHING_REVEAL / TEACHING_
        EXPLANATION actions that actually reached the transcript. An action
        whose delivery failed has no assistant_turn row and does not count.
        """

        placeholders = ", ".join("?" for _ in _TEACHING_TURN_ACTION_TYPES)
        row = self._conn.execute(
            "SELECT COUNT(DISTINCT a.action_id)"
            " FROM generation_action_intent a"
            " JOIN assistant_turn t ON t.action_id = a.action_id"
            " WHERE a.moment_id = ? AND a.action_type IN ("
            + placeholders
            + ")",
            (moment_id, *_TEACHING_TURN_ACTION_TYPES),
        ).fetchone()
        return 0 if row is None else int(row[0])

    def get_attempts(
        self, moment_id: MomentId
    ) -> Result[tuple[AttemptRecord, ...]]:
        rows = self._conn.execute(
            "SELECT attempt_id, moment_id, attempt_index, user_turn_id,"
            " support_level_before_attempt, answer_exposure_state,"
            " exposure_estimate_id, support_attribution_certainty,"
            " support_attribution_basis, created_at"
            " FROM attempt_record WHERE moment_id = ?"
            " ORDER BY attempt_index",
            (moment_id,),
        ).fetchall()
        return Ok(
            tuple(
                AttemptRecord(
                    attempt_id=AttemptId(str(row[0])),
                    moment_id=MomentId(str(row[1])),
                    attempt_index=int(row[2]),
                    user_turn_id=UserTurnId(str(row[3])),
                    support_level_before_attempt=TeachingSupportLevel(
                        str(row[4])
                    ),
                    answer_exposure_state=AnswerExposureState(str(row[5])),
                    exposure_estimate_id=_optional(row[6]),
                    support_attribution_certainty=ExposureEstimateCertainty(
                        str(row[7])
                    ),
                    support_attribution_basis=str(row[8]),
                    created_at=_optional(row[9]),
                )
                for row in rows
            )
        )

    def count_delivered_slot_actions(
        self, moment_id: MomentId, slot: str
    ) -> int:
        """Delivered teaching actions of one moment in one ladder slot.

        ``slot`` is the action id's role suffix (``hint`` / ``retry`` /
        ``reveal`` / ``explanation`` / ``resume``): the crash reconciliation
        rebuilds the ladder rung from how many *hint* deliveries really
        happened, which is durable fact (the assistant turn exists) rather
        than an intention. The suffix travels as a bound parameter — it is a
        value, never assembled SQL.
        """

        row = self._conn.execute(
            "SELECT COUNT(DISTINCT a.action_id)"
            " FROM generation_action_intent a"
            " JOIN assistant_turn t ON t.action_id = a.action_id"
            " WHERE a.moment_id = ? AND a.action_id LIKE ?",
            (moment_id, f"%-{slot}"),
        ).fetchone()
        return 0 if row is None else int(row[0])

    def get_attempt_for_turn(
        self, moment_id: MomentId, user_turn_id: UserTurnId
    ) -> Result[AttemptRecord | None]:
        """The durable attempt one user turn contributed to one moment.

        The (moment, user turn) pair is the attempt's idempotency key
        (review F3): a re-entry reads the attempt it already recorded
        instead of deriving a new index — the read face the coordinator uses
        before it assembles a second AttemptRecord.
        """

        row = self._conn.execute(
            "SELECT attempt_id, moment_id, attempt_index, user_turn_id,"
            " support_level_before_attempt, answer_exposure_state,"
            " exposure_estimate_id, support_attribution_certainty,"
            " support_attribution_basis, created_at"
            " FROM attempt_record WHERE moment_id = ? AND user_turn_id = ?",
            (moment_id, user_turn_id),
        ).fetchone()
        if row is None:
            return Ok(None)
        return Ok(
            AttemptRecord(
                attempt_id=AttemptId(str(row[0])),
                moment_id=MomentId(str(row[1])),
                attempt_index=int(row[2]),
                user_turn_id=UserTurnId(str(row[3])),
                support_level_before_attempt=TeachingSupportLevel(str(row[4])),
                answer_exposure_state=AnswerExposureState(str(row[5])),
                exposure_estimate_id=_optional(row[6]),
                support_attribution_certainty=ExposureEstimateCertainty(
                    str(row[7])
                ),
                support_attribution_basis=str(row[8]),
                created_at=_optional(row[9]),
            )
        )

    def get_attempt_evaluation(
        self, attempt_id: AttemptId
    ) -> Result[AttemptEvaluationRecord | None]:
        row = self._conn.execute(
            "SELECT attempt_evaluation_id, moment_id, attempt_id,"
            " evaluator_id, evaluator_version, outcome, confidence,"
            " evidence_proposal_refs, created_at"
            " FROM attempt_evaluation_record WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None:
            return Ok(None)
        return Ok(
            AttemptEvaluationRecord(
                attempt_evaluation_id=AttemptEvaluationId(str(row[0])),
                moment_id=MomentId(str(row[1])),
                attempt_id=AttemptId(str(row[2])),
                evaluator_id=str(row[3]),
                evaluator_version=str(row[4]),
                outcome=str(row[5]),
                confidence=float(row[6]),
                evidence_proposal_refs=_array_from_document(str(row[7])),
                created_at=_optional(row[8]),
            )
        )

    # -- reads --------------------------------------------------------------

    def evidence_proposal_refs(
        self,
    ) -> Result[tuple[tuple[str, tuple[str, ...]], ...]]:
        """Every §17 ``evidence_proposal_refs`` row, in durable order (P4-2).

        The refs↔proposal reconciliation read (DEC-…5ba74efc.96 F1): the
        teaching side *names* which evidence proposal each evaluation
        recorded, and the runtime checks those names against Learning's
        durable proposal table — the teaching package may not import
        ``elc.learning``, so the existence check stays on the runtime side
        (the same split as every other teaching↔learning seam).

        Read-only and complete: every evaluation row is returned with the
        refs exactly as the row carries them — never re-derived, never
        filtered by a prefix (a ref whose shape nobody recognizes is still a
        ref that has to resolve), and an evaluation with no refs (ABSTAIN)
        is returned with an empty tuple rather than hidden.
        """

        rows = self._conn.execute(
            "SELECT attempt_evaluation_id, evidence_proposal_refs"
            " FROM attempt_evaluation_record"
            " ORDER BY created_at, attempt_evaluation_id",
        ).fetchall()
        return Ok(
            tuple(
                (str(row[0]), _array_from_document(str(row[1])))
                for row in rows
            )
        )

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

    def list_moments_for_conversation(
        self, conversation_id: ConversationId
    ) -> Result[tuple[TeachingMomentRecord, ...]]:
        """Every moment of one conversation, in the durable order
        ``(created_at, moment_id)`` — the per-conversation history read
        (P8-2).

        The order is the store's own durable order, the one
        ``get_gate_decisions`` and the orphan-lock read already use: the
        stored ``created_at`` byte order, tie-broken by the id, so two reads
        of one world answer in the same sequence whatever the query plan
        does. It is **not** an instant order — a caller classifying by time
        parses the instants itself (``elc.teaching.budget`` does, and says
        why). ``Ok(())`` means the conversation has no teaching history yet,
        which is the ordinary state of a fresh conversation, not an error.
        """

        rows = self._conn.execute(
            "SELECT " + _MOMENT_COLUMNS + " FROM teaching_moment"
            " WHERE conversation_id = ?"
            " ORDER BY created_at, moment_id",
            (conversation_id,),
        ).fetchall()
        return Ok(tuple(self._moment_record(row) for row in rows))

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
        return self._conn.execute(
            "SELECT " + _MOMENT_COLUMNS + " FROM teaching_moment"
            " WHERE moment_id = ?",
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
