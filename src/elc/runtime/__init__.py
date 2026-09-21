"""Runtime / Platform domain — Conversation Orchestrator.

docs/DOMAIN_MODEL.md §16. Sequencing, not truth. All DB mechanics stay in
elc.platform.db and the conversation domain store; this package is SQL-free
by architecture test. The §14 GenerationAction authority (port + pure
state-machine policy, elc.runtime.generation) lives here because
GenerationActionIntent / ProviderAttempt are Runtime-specific records —
its durable executor is elc.platform.db.generation_store.

The controller module loads lazily (PEP 562): both the conversation and
persona command faces import elc.runtime.types, so importing the
controller eagerly here would create an initialization cycle.
"""

from typing import Any

from elc.runtime.commands import RuntimeCommands
from elc.runtime.decision_cycles import (
    DecisionCycleBindings,
    DecisionCycleStore,
)
from elc.runtime.generation import (
    GENERATION_ACTION_TRANSITIONS,
    RECOVERY_REARM_STATUS,
    GenerationActionStore,
    claim_rearm,
    terminal_refusal,
    transition_refusal,
)
from elc.runtime.lease import (
    ConversationCoordinatorLease,
    LeaseGuard,
    StaleCoordinatorEpoch,
)
from elc.runtime.queries import RuntimeQueries
from elc.runtime.recovery import (
    TEACHING_LOCK_RECOVERY_ACTION,
    StartupRecoveryScanner,
    TeachingLockRecoverySource,
    TurnRecordRecoverySource,
    recovery_disposition,
)
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    DecisionCycleRecord,
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    ProjectionJobRecord,
    ProjectionJobState,
    ProviderAttemptRecord,
    RecoveryAction,
    TurnCompletion,
    TurnRecordData,
    TurnStatus,
    ValidatorResultRecord,
)

#: Names the lazily-imported controller module provides on this package.
_CONTROLLER_EXPORTS = (
    "AssistantDelivery",
    "ConversationCoordinator",
    "RuntimeOrchestrator",
    "TeachingTurnResult",
)

__all__ = [
    "AssistantDelivery",
    "GENERATION_ACTION_TRANSITIONS",
    "RECOVERY_REARM_STATUS",
    "TERMINAL_TURN_STATUSES",
    "ConversationCoordinator",
    "ConversationCoordinatorLease",
    "DecisionCycleBindings",
    "DecisionCycleRecord",
    "DecisionCycleStore",
    "GenerationActionIntentRecord",
    "GenerationActionStatus",
    "GenerationActionStore",
    "GenerationActionType",
    "InputEnvelope",
    "InterruptRequest",
    "LeaseGuard",
    "ProjectionJobRecord",
    "ProjectionJobState",
    "ProviderAttemptRecord",
    "RecoveryAction",
    "RuntimeCommands",
    "RuntimeOrchestrator",
    "RuntimeQueries",
    "StartupRecoveryScanner",
    "StaleCoordinatorEpoch",
    "TEACHING_LOCK_RECOVERY_ACTION",
    "TeachingLockRecoverySource",
    "TurnCompletion",
    "TurnRecordData",
    "TurnRecordRecoverySource",
    "TurnStatus",
    "ValidatorResultRecord",
    "claim_rearm",
    "recovery_disposition",
    "terminal_refusal",
    "transition_refusal",
]


def __getattr__(name: str) -> Any:
    if name in _CONTROLLER_EXPORTS:
        from elc.runtime import controller

        return getattr(controller, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CONTROLLER_EXPORTS))
