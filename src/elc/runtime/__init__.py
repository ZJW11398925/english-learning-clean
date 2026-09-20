"""Runtime / Platform domain — Conversation Orchestrator.

docs/DOMAIN_MODEL.md §16. Sequencing, not truth. All DB mechanics stay in
elc.platform.db; this package is SQL-free by architecture test.
"""

from elc.runtime.commands import RuntimeCommands
from elc.runtime.controller import RuntimeOrchestrator
from elc.runtime.queries import RuntimeQueries
from elc.runtime.types import (
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
    "DecisionCycleRecord",
    "GenerationActionStatus",
    "GenerationActionType",
    "InputEnvelope",
    "InterruptRequest",
    "ProjectionJobRecord",
    "ProjectionJobState",
    "ProviderAttemptRecord",
    "RecoveryAction",
    "RuntimeCommands",
    "RuntimeOrchestrator",
    "RuntimeQueries",
    "TurnRecordData",
    "TurnStatus",
    "ValidatorResultRecord",
]
