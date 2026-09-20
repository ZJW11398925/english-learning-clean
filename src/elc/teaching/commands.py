"""Teaching domain command face — Gate authority + moment lifecycle."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import (
    AttemptEvaluationId,
    AttemptId,
    GateDecisionId,
    MomentId,
    Result,
)
from elc.teaching.types import (
    AttemptEvaluationRecord,
    AttemptRecord,
    EphemeralTeachingDirective,
    GateDecisionRecord,
    GateExecutionStatusRecord,
    MomentState,
    TeachingMomentRecord,
)


@runtime_checkable
class TeachingCommands(Protocol):
    """Teaching writes. CP2 opens Gate+Moment+Lock+first Action atomically."""

    def decide_gate(
        self,
        candidate_id: str,
        context: str,
        decision_cycle_id: str | None,
        moment_id: str | None,
    ) -> Result[GateDecisionRecord | GateExecutionStatusRecord]:
        """ALLOW/DENY, or a DEGRADED execution status — never synthetic DENY."""
        ...

    def open_teaching_moment(
        self, moment: TeachingMomentRecord
    ) -> Result[MomentId]:
        """CP2 unit: GateDecision + Moment + active_teaching_lock + first
        GenerationAction, one short transaction."""
        ...

    def record_attempt(self, attempt: AttemptRecord) -> Result[AttemptId]:
        ...

    def record_attempt_evaluation(
        self, evaluation: AttemptEvaluationRecord
    ) -> Result[AttemptEvaluationId]:
        ...

    def terminalize_moment(
        self, moment_id: MomentId, outcome: str
    ) -> Result[MomentState]:
        """TEACHING_TERMINAL releases the durable lock in the same short tx."""
        ...

    def issue_ephemeral_directive(
        self, moment_id: MomentId
    ) -> Result[EphemeralTeachingDirective]:
        """Teaching Planner: candidate → directive for Persona Runtime."""
        ...
