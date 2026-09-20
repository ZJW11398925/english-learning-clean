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
    """Decision XOR degraded status — never both, never neither.

    docs/DOMAIN_MODEL.md §10: planner failure/unavailable must not be
    disguised as PlannerDecision(NO_TARGET).
    """

    evaluation: PlannerEvaluation
    decision: PlannerDecision | None
    execution_status: PlannerExecutionStatusRecord | None

    def __post_init__(self) -> None:
        if (self.decision is None) == (self.execution_status is None):
            raise ValueError(
                "PlanningOutcome requires exactly one of PlannerDecision / "
                "PlannerExecutionStatus (degradation is not a decision)"
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
