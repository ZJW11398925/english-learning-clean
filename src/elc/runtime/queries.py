"""Runtime Orchestrator query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.runtime.types import (
    DecisionCycleRecord,
    ProjectionJobRecord,
    RecoveryAction,
    TurnRecordData,
)
from elc.platform.types import (
    ConversationId,
    DecisionCycleId,
    ProjectionJobId,
    Result,
    TurnId,
)


@runtime_checkable
class RuntimeQueries(Protocol):
    """Coordination reads."""

    def get_turn_record(self, turn_id: TurnId) -> Result[TurnRecordData | None]:
        ...

    def get_decision_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[DecisionCycleRecord | None]:
        ...

    def pending_projections(
        self, conversation_id: ConversationId
    ) -> Result[tuple[ProjectionJobRecord, ...]]:
        ...

    def recovery_plan(self) -> Result[tuple[RecoveryAction, ...]]:
        ...
