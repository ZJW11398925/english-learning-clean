"""Empty Conversation Orchestrator (Phase 1 minimum runtime will implement).

The orchestrator coordinates through domain command/query interfaces only:
its DB posture is "none" — no sqlite3 import, no SQL execution, no direct
table mutation (Gate item 2; enforced by tests/architecture). Persistence of
its own coordination records goes through the platform DB primitives in a
later phase, never through ad-hoc SQL here.
"""

from __future__ import annotations

from elc.platform.sync import KeyedMutex
from elc.platform.types import (
    ActionId,
    ConversationId,
    DecisionCycleId,
    InputId,
    ProjectionJobId,
    ProviderAttemptId,
    Result,
    TurnId,
    RuntimeEpoch,
)
from elc.runtime.types import (
    DecisionCycleRecord,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    ProjectionJobRecord,
    ProviderAttemptRecord,
    RecoveryAction,
    TurnRecordData,
)


class RuntimeOrchestrator:
    """Sequencing, retry, recovery — owns no canonical truth (Phase 0)."""

    def __init__(self) -> None:
        # Live per-conversation coordinator (docs/RUNTIME_ARCHITECTURE.md §24).
        # In-process keyed mutex + runtime_epoch + durable turn/action state;
        # deliberately NOT a distributed lock service.
        self._mutex = KeyedMutex()
        self._epoch: RuntimeEpoch | None = None

    @property
    def runtime_epoch(self) -> RuntimeEpoch | None:
        """Epoch opened at startup; None until the startup fence runs."""
        return self._epoch

    def open_startup_fence(self, current_epoch: RuntimeEpoch) -> None:
        """Adopt the current epoch (opened via platform.db.epoch at startup)."""
        self._epoch = current_epoch

    def ingest_input(self, envelope: InputEnvelope) -> Result[InputId]:
        raise NotImplementedError("Phase 1: durable input ingest + dedupe")

    def request_interrupt(self, interrupt: InterruptRequest) -> Result[InputId]:
        raise NotImplementedError("Phase 9: guarded barge-in handoff")

    def begin_turn(self, turn: TurnRecordData) -> Result[TurnId]:
        raise NotImplementedError("Phase 1: CP0 coordination unit")

    def open_decision_cycle(
        self, cycle: DecisionCycleRecord
    ) -> Result[DecisionCycleId]:
        raise NotImplementedError("Phase 1: decision cycle")

    def create_generation_action(
        self,
        turn_id: TurnId,
        action_type: GenerationActionType,
        action_id: ActionId,
    ) -> Result[ActionId]:
        raise NotImplementedError("Phase 1: action intent")

    def create_provider_attempt(
        self, action_id: ActionId, attempt: ProviderAttemptRecord
    ) -> Result[ProviderAttemptId]:
        raise NotImplementedError("Phase 1: action-level provider retry")

    def enqueue_projection(
        self, job: ProjectionJobRecord
    ) -> Result[ProjectionJobId]:
        raise NotImplementedError("Phase 4: CP4 projection job")

    def startup_recovery(self) -> Result[tuple[RecoveryAction, ...]]:
        raise NotImplementedError("Phase 10: epoch-fenced recovery plan")

    def get_turn_record(self, turn_id: TurnId) -> Result[TurnRecordData | None]:
        raise NotImplementedError("Phase 1: turn record read")

    def get_decision_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[DecisionCycleRecord | None]:
        raise NotImplementedError("Phase 1: decision cycle read")
