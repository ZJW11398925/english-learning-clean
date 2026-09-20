"""Empty Teaching Domain Controller (Phase 3 user-initiated / Phase 8 auto)."""

from __future__ import annotations

from elc.platform.types import (
    AttemptEvaluationId,
    AttemptId,
    ConversationId,
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


class TeachingController:
    """Owns TeachingMoment lifecycle + Gate authority. Phase 0: no logic."""

    def decide_gate(
        self,
        candidate_id: str,
        context: str,
        decision_cycle_id: str | None,
        moment_id: str | None,
    ) -> Result[GateDecisionRecord | GateExecutionStatusRecord]:
        raise NotImplementedError("Phase 3/8: Gate v1.1 decision")

    def open_teaching_moment(
        self, moment: TeachingMomentRecord
    ) -> Result[MomentId]:
        raise NotImplementedError("Phase 3: CP2 atomic open + durable lock")

    def record_attempt(self, attempt: AttemptRecord) -> Result[AttemptId]:
        raise NotImplementedError("Phase 3: attempt recording")

    def record_attempt_evaluation(
        self, evaluation: AttemptEvaluationRecord
    ) -> Result[AttemptEvaluationId]:
        raise NotImplementedError("Phase 3: attempt evaluation")

    def terminalize_moment(
        self, moment_id: MomentId, outcome: str
    ) -> Result[MomentState]:
        raise NotImplementedError("Phase 3: terminalization + lock release")

    def issue_ephemeral_directive(
        self, moment_id: MomentId
    ) -> Result[EphemeralTeachingDirective]:
        raise NotImplementedError("Phase 3: Teaching Planner directive")

    def get_active_moment(
        self, conversation_id: ConversationId
    ) -> Result[TeachingMomentRecord | None]:
        raise NotImplementedError("Phase 3: active lock read")

    def get_moment(self, moment_id: MomentId) -> Result[TeachingMomentRecord | None]:
        raise NotImplementedError("Phase 3: moment read")
