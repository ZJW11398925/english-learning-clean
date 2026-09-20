"""Runtime / Platform domain — Conversation Orchestrator.

docs/DOMAIN_MODEL.md §16. Sequencing, not truth. All DB mechanics stay in
elc.platform.db (and, since Phase 1 P1A, in the conversation store); this
package is SQL-free by architecture test.
"""

from elc.runtime.commands import RuntimeCommands
from elc.runtime.controller import RuntimeOrchestrator
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
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    ProjectionJobRecord,
    ProjectionJobState,
    ProviderAttemptRecord,
    RecoveryAction,
    TurnRecordData,
    TurnStatus,
    ValidatorResultRecord,
)

__all__ = [
    "TERMINAL_TURN_STATUSES",
    "ConversationCoordinatorLease",
    "DecisionCycleRecord",
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
    "TurnRecordData",
    "TurnRecordRecoverySource",
    "TurnStatus",
    "ValidatorResultRecord",
    "recovery_disposition",
]
