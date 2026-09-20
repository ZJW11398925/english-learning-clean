"""Runtime Orchestrator command face — sequencing only, never truth.

docs/DOMAIN_MODEL.md §16 + D-INV-001: the orchestrator calls domain
commands (conversation / teaching / planner / …); it never mutates
domain-owned canonical state and never issues SQL itself (Gate item 2 is
enforced by tests/architecture on this package's imports and call surface).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.conversation.types import CommitUserTurn
from elc.platform.types import (
    ActionId,
    DecisionCycleId,
    InputId,
    ProjectionJobId,
    ProviderAttemptId,
    Result,
    TurnId,
)
from elc.runtime.types import (
    DecisionCycleRecord,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    ProjectionJobRecord,
    ProviderAttemptRecord,
    RecoveryAction,
    TurnCompletion,
)


@runtime_checkable
class RuntimeCommands(Protocol):
    """Turn coordination writes (runtime-owned coordination records only)."""

    def ingest_input(self, envelope: InputEnvelope) -> Result[InputId]:
        """Durable dedupe (client_message_id) outside the coordinator guard."""
        ...

    def request_interrupt(self, interrupt: InterruptRequest) -> Result[InputId]:
        ...

    def begin_turn(self, command: CommitUserTurn) -> Result[TurnCompletion]:
        """Minimum closed loop (Phase 1 P1B): coordinator guard → CP0
        (idempotent) → generation pipeline (STATE_MACHINES §14 action state
        machine, action-level retry) → BUFFERED_VALIDATED delivery →
        canonical AssistantTurn → turn terminalization. Never retries a
        whole turn (R-INV-007)."""
        ...

    def open_decision_cycle(
        self, cycle: DecisionCycleRecord
    ) -> Result[DecisionCycleId]:
        ...

    def create_generation_action(
        self,
        turn_id: TurnId,
        action_type: GenerationActionType,
        action_id: ActionId,
    ) -> Result[ActionId]:
        ...

    def create_provider_attempt(
        self, action_id: ActionId, attempt: ProviderAttemptRecord
    ) -> Result[ProviderAttemptId]:
        """Action-level retry: new attempt, same stable action (R-INV-007)."""
        ...

    def enqueue_projection(self, job: ProjectionJobRecord) -> Result[ProjectionJobId]:
        """CP4 work, executed after guard release; never blocks a turn."""
        ...

    def startup_recovery(self) -> Result[tuple[RecoveryAction, ...]]:
        """New runtime_epoch fences old-epoch nonterminal work (§24)."""
        ...
