"""Pedagogy Planner — application service, owns no canonical truth.

docs/DOMAIN_MODEL.md §10: the Planner straddles Learning / Curriculum /
Scheduler / Conversation / User Configuration but owns none of them. It
reads input-authority views and produces a two-layer result:
PlannerEvaluation (ranked candidates + reason trace) and PlannerDecision
(SELECT | NO_TARGET).

Hard rules (docs/DOMAIN_MODEL.md §10.1):
- missing authoritative views or invalid snapshots produce
  PlannerExecutionStatus=DEGRADED/FAILED/UNAVAILABLE — never a synthetic
  PlannerDecision(NO_TARGET);
- the Planner never writes Learner State (D-INV-004) and never authorizes
  teaching (the Gate does).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    DecisionCycleId,
    PlannerDecision,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
    TargetId,
)


class InitiativeClass(StrEnum):
    """docs/DOMAIN_MODEL.md §11."""

    REACTIVE = "REACTIVE"
    OPPORTUNISTIC = "OPPORTUNISTIC"
    PROACTIVE = "PROACTIVE"


class TargetMode(StrEnum):
    """docs/DOMAIN_MODEL.md §11."""

    RESOURCE_PRACTICE = "RESOURCE_PRACTICE"
    CAPABILITY_PRACTICE = "CAPABILITY_PRACTICE"
    PROBE = "PROBE"
    REVIEW = "REVIEW"
    TRANSFER = "TRANSFER"


class LearningIntent(StrEnum):
    """docs/DOMAIN_MODEL.md §11."""

    ESTABLISH = "ESTABLISH"
    DEVELOP = "DEVELOP"
    WITHDRAW_SUPPORT = "WITHDRAW_SUPPORT"
    CONSOLIDATE = "CONSOLIDATE"
    PROBE = "PROBE"
    TRANSFER = "TRANSFER"
    EXPAND_REPERTOIRE = "EXPAND_REPERTOIRE"


class UserIntentScope(StrEnum):
    """docs/DOMAIN_MODEL.md §12. TARGETED_LEARNING_REQUEST is a candidate-scope
    constraint, not an ordinary bonus."""

    OPEN = "OPEN"
    LEARNING_REQUEST = "LEARNING_REQUEST"
    TARGETED_LEARNING_REQUEST = "TARGETED_LEARNING_REQUEST"
    JUST_CHAT = "JUST_CHAT"
    NON_LEARNING_TASK = "NON_LEARNING_TASK"
    ACTIVE_TEACHING_CONTINUATION = "ACTIVE_TEACHING_CONTINUATION"


@dataclass(frozen=True)
class TargetCandidate:
    """One candidate in the ranked set (docs/DOMAIN_MODEL.md §11)."""

    candidate_id: str
    canonical_key: str
    target_id: TargetId
    initiative_class: InitiativeClass
    target_mode: TargetMode
    learning_intent: LearningIntent
    request_priority: int | None
    goal_relation: str  # NONE | PREPARATORY | DIRECT_TARGET_LEVEL


@dataclass(frozen=True)
class PlannerEvaluation:
    """Layer 1: ranked TargetCandidateSet + factor/reason trace."""

    planner_evaluation_id: PlannerEvaluationId
    decision_cycle_id: DecisionCycleId
    planner_version: PlannerVersion
    policy_version: PolicyVersion
    ranked_candidates: tuple[TargetCandidate, ...]
    reason_trace: tuple[str, ...]


@dataclass(frozen=True)
class PlanningRequest:
    """Input authorities assembled by the orchestrator (docs/DOMAIN_MODEL.md §10)."""

    decision_cycle_id: DecisionCycleId
    learning_snapshot: object | None
    curriculum_candidate_view: object | None
    schedule_view: object | None
    goal_view: object | None
    teaching_policy_view: object | None
    context_opportunity_set: object | None
    planner_constraint_view: object | None
    session_budget_view: object | None
    user_intent_scope: UserIntentScope
    conversation_priority_view: object | None
    planning_ledger: object | None


@dataclass(frozen=True)
class PlanningOutcome:
    """Canonical decision/status coupling — keyed by PlannerExecutionStatus.

    docs/DOMAIN_MODEL.md §10: "Planner failure/unavailable 不伪装成
    PlannerDecision；它由 Runtime 的 PlannerExecutionStatus 表达。" §10.1:
    "缺失 authoritative view 或 invalid snapshot 进入
    PlannerExecutionStatus=DEGRADED/FAILED/UNAVAILABLE，不得伪造 NO_TARGET。"
    behavioral_baselines/planner/BF-02_Planner_Decision_Spec_v1.1.md §5:
    PlannerExecutionStatus = DEGRADED 时 PlannerDecision = none.

    Rule: SUCCEEDED ⟹ a PlannerDecision (SELECT or NO_TARGET) must be
    present; DEGRADED/FAILED/UNAVAILABLE ⟹ no PlannerDecision at all.
    """

    evaluation: PlannerEvaluation
    execution_status: PlannerExecutionStatusRecord
    decision: PlannerDecision | None

    def __post_init__(self) -> None:
        succeeded = (
            self.execution_status.status is PlannerExecutionStatusValue.SUCCEEDED
        )
        if succeeded and self.decision is None:
            raise ValueError(
                "PlanningOutcome with PlannerExecutionStatus=SUCCEEDED "
                "requires a PlannerDecision (SELECT or NO_TARGET)"
            )
        if not succeeded and self.decision is not None:
            raise ValueError(
                "PlanningOutcome with PlannerExecutionStatus="
                f"{self.execution_status.status.value} must carry no "
                "PlannerDecision (degradation is not a decision)"
            )


__all__ = [
    "InitiativeClass",
    "LearningIntent",
    "PlanningOutcome",
    "PlanningRequest",
    "PlannerDecisionOutcome",
    "PlannerEvaluation",
    "PlannerExecutionStatusRecord",
    "PlannerExecutionStatusValue",
    "TargetCandidate",
    "TargetMode",
    "UserIntentScope",
]
