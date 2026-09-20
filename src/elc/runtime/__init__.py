"""Runtime / Platform domain — Conversation Orchestrator.

docs/DOMAIN_MODEL.md §16. Sequencing, not truth. All DB mechanics stay in
elc.platform.db (and, since Phase 1 P1A, in the conversation store; since
P1B, in the persona generation store); this package is SQL-free by
architecture test.

The controller module loads lazily (PEP 562): both the conversation and
persona command faces import elc.runtime.types, so importing the
controller eagerly here would create an initialization cycle.
"""

from typing import Any

from elc.runtime.commands import RuntimeCommands
from elc.runtime.lease import (
    ConversationCoordinatorLease,
    LeaseGuard,
    StaleCoordinatorEpoch,
)
from elc.runtime.queries import RuntimeQueries
from elc.runtime.recovery import (
    StartupRecoveryScanner,
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
)

__all__ = [
    "AssistantDelivery",
    "TERMINAL_TURN_STATUSES",
    "ConversationCoordinator",
    "ConversationCoordinatorLease",
    "DecisionCycleRecord",
    "GenerationActionIntentRecord",
    "GenerationActionStatus",
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
    "TurnCompletion",
    "TurnRecordData",
    "TurnRecordRecoverySource",
    "TurnStatus",
    "ValidatorResultRecord",
    "recovery_disposition",
]


def __getattr__(name: str) -> Any:
    if name in _CONTROLLER_EXPORTS:
        from elc.runtime import controller

        return getattr(controller, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CONTROLLER_EXPORTS))
