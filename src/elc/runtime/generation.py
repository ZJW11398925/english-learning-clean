"""Runtime-owned GenerationAction authority (DOMAIN_MODEL §16).

docs/DOMAIN_MODEL.md §16 lists GenerationActionIntent and ProviderAttempt
under **Runtime-specific records**, and docs/RUNTIME_ARCHITECTURE.md §3
assigns the orchestrator "coordinate generation/delivery" and "recover
incomplete actions". This module is therefore the single home of the
§14 GenerationActionStatus state machine: the durable port every
coordinator-facing consumer programs against, plus the pure transition /
recovery policy (STATE_MACHINES §14) that the platform persistence layer
executes. It mirrors how TurnRecord already works: TERMINAL_TURN_STATUSES
policy lives in elc.runtime.types while the conversation store is only the
CAS executor.

Phase 1 shape (TASK-OPI-eaaa5a1d.6): the port is consumed by
PersonaRuntime (the generation pipeline body: prompt → provider →
validator) and by ConversationCoordinator (delivery legs + recovery
claims); the SQLite implementation lives in
elc.platform.db.generation_store. Pure logic only — no sqlite3, no SQL,
no DB call surface (Gate item 2 AST-scans this package).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import (
    ActionId,
    DomainError,
    DomainErrorCode,
    Result,
    RuntimeEpoch,
    TurnId,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    ProviderAttemptRecord,
)

__all__ = [
    "GENERATION_ACTION_TRANSITIONS",
    "GenerationActionStore",
    "RECOVERY_REARM_STATUS",
    "claim_rearm",
    "transition_refusal",
    "terminal_refusal",
]

#: §14 nonterminal statuses (every status except TERMINAL).
_NONTERMINAL_STATUSES: tuple[GenerationActionStatus, ...] = tuple(
    status
    for status in GenerationActionStatus
    if status != GenerationActionStatus.TERMINAL
)

#: STATE_MACHINES §14 seven-value machine as an explicit edge table: the
#: forward pipeline, the two bounded action-level retry back-edges (§15 /
#: R-INV-007), and the generic "<nonterminal> → TERMINAL" rule (bounded
#: retries exhausted, supervisor abort, late-callback discard). TERMINAL
#: is never a source — a late result for a cancelled/superseded/terminal
#: action must not produce a canonical side effect (§14).
GENERATION_ACTION_TRANSITIONS: frozenset[
    tuple[GenerationActionStatus, GenerationActionStatus]
] = frozenset(
    {
        (
            GenerationActionStatus.PREPARED,
            GenerationActionStatus.REQUESTED,
        ),
        (
            GenerationActionStatus.REQUESTED,
            GenerationActionStatus.GENERATING,
        ),
        (
            GenerationActionStatus.GENERATING,
            GenerationActionStatus.VALIDATING,
        ),
        # provider failure → action-level retry (R-INV-007).
        (
            GenerationActionStatus.GENERATING,
            GenerationActionStatus.REQUESTED,
        ),
        # validator RETRY, bounded (§15).
        (
            GenerationActionStatus.VALIDATING,
            GenerationActionStatus.REQUESTED,
        ),
        # validator ACCEPT → buffered validated delivery (RUNTIME §13).
        (
            GenerationActionStatus.VALIDATING,
            GenerationActionStatus.READY_TO_DELIVER,
        ),
        (
            GenerationActionStatus.READY_TO_DELIVER,
            GenerationActionStatus.DELIVERING,
        ),
    }
    | {
        (status, GenerationActionStatus.TERMINAL)
        for status in _NONTERMINAL_STATUSES
    }
)

#: Startup-recovery re-arm status (RUNTIME §22/§24; SM §17.1 rule 3): a
#: newly adopted old-epoch nonterminal action is re-armed at REQUESTED so
#: re-dispatch retries at the action level under the same stable
#: action_id (§23 "继续同 action_id").
RECOVERY_REARM_STATUS = GenerationActionStatus.REQUESTED


def transition_refusal(
    action_id: ActionId,
    expected: GenerationActionStatus,
    new: GenerationActionStatus,
) -> DomainError | None:
    """Pure §14 decision for a proposed (expected → new) advance: the
    refusal when §14 does not admit the edge, None when it does.

    TERMINAL is immutable (never a source), so a transition whose expected
    status is TERMINAL is refused here — the §14 late-result rule. This is
    the policy half; the durable CAS (status/owner_epoch guards) is the
    persistence half in elc.platform.db.generation_store."""

    if (expected, new) in GENERATION_ACTION_TRANSITIONS:
        return None
    if expected == GenerationActionStatus.TERMINAL:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"action {action_id} is TERMINAL — late results never"
                " overwrite a terminal action (STATE_MACHINES §14)"
            ),
        )
    return DomainError(
        code=DomainErrorCode.VALIDATION_FAILED,
        message=(
            f"action {action_id}: {expected.value} → {new.value} is not a"
            " STATE_MACHINES §14 transition"
        ),
    )


def terminal_refusal(
    action_id: ActionId, durable: GenerationActionStatus
) -> DomainError | None:
    """Pure §14 decision on the durable status read back from the store:
    a TERMINAL row refuses every advance — no canonical side effect from
    late work."""

    if durable == GenerationActionStatus.TERMINAL:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"action {action_id} is TERMINAL ({durable.value}) — no"
                " canonical side effect from late work"
            ),
        )
    return None


def claim_rearm(
    status: GenerationActionStatus, owner_epoch: int | None, current_epoch: int
) -> bool:
    """Pure §24 claim decision: does a recovery claim re-arm this action?

    True only for a nonterminal action owned by an older epoch — the new
    runtime epoch adopts it and re-arms it at RECOVERY_REARM_STATUS.
    TERMINAL actions and actions already owned by the current epoch are
    returned unchanged (idempotent; a validated own-epoch buffer is never
    discarded)."""

    if status == GenerationActionStatus.TERMINAL:
        return False
    return owner_epoch != current_epoch


@runtime_checkable
class GenerationActionStore(Protocol):
    """Durable face for GenerationActionIntent / ProviderAttempt rows —
    runtime-owned records (docs/DOMAIN_MODEL.md §16), implemented by
    elc.platform.db.generation_store.SqliteGenerationStore; §14 state
    authority lives in this module, CP2.5 attempt log per RUNTIME §6."""

    def create_action(
        self, intent: GenerationActionIntentRecord
    ) -> Result[ActionId]:
        ...

    def transition_action(
        self,
        action_id: ActionId,
        expected: GenerationActionStatus,
        new: GenerationActionStatus,
    ) -> Result[GenerationActionIntentRecord]:
        ...

    def record_attempt(
        self, attempt: ProviderAttemptRecord
    ) -> Result[ProviderAttemptRecord]:
        ...

    def get_action(
        self, action_id: ActionId
    ) -> Result[GenerationActionIntentRecord | None]:
        ...

    def get_action_for_turn(
        self, turn_id: TurnId
    ) -> Result[GenerationActionIntentRecord | None]:
        ...

    def claim_action_for_recovery(
        self, action_id: ActionId
    ) -> Result[GenerationActionIntentRecord]:
        ...

    def recoverable_generation_actions(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[GenerationActionIntentRecord, ...]:
        ...
