"""Pedagogy Planner — application service over Learning/Curriculum/Scheduler/
Conversation/User Configuration views. Owns no canonical truth.

docs/DOMAIN_MODEL.md §10-§12. Decision/execution-status separation types are
canonically defined in elc.platform.types and re-exported here.

P7-0 (TASK-OPI-b99560d4-….36 ③) adds :mod:`elc.planner.feature_assembly` — the
authority boundary BF-02 §5 states (``feature_assembly_status`` /
``snapshot_status`` / ``missing_authorities[]``, and the rule that an
incomplete assembly is DEGRADED carrying no decision). The decision kernel is
not here: :class:`PlannerService` is still the Phase 0 skeleton, and the
assembly answers *what the Planner may assume*, never what it decides.
"""

from elc.planner.commands import PlannerCommands
from elc.planner.controller import PlannerService
from elc.planner.feature_assembly import (
    FEATURE_ASSEMBLY_MODEL_VERSION,
    POLICY_PROFILE_MAPPING_VERSION,
    SCHEDULE_URGENCY_BANDS,
    TEACHING_FREQUENCY_TO_PROFILE,
    AuthorityName,
    FeatureAssemblyStatus,
    FeatureAuthority,
    GoalPortfolioPort,
    LearningSnapshotPort,
    PlannerProfile,
    ProfileMapping,
    ScheduleAuthority,
    ScheduleRowPort,
    ScheduleViewPort,
    SnapshotStatus,
    TeachingPolicyPort,
    assemble_feature_authority,
    execution_status_of,
    goal_relevance_of,
    profile_mapping_of,
    schedule_authority_of,
    schedule_urgency_of,
)
from elc.planner.queries import PlannerQueries
from elc.planner.types import (
    InitiativeClass,
    LearningIntent,
    PlannerDecision,
    PlannerDecisionOutcome,
    PlannerEvaluation,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlanningOutcome,
    PlanningRequest,
    TargetCandidate,
    TargetMode,
    UserIntentScope,
)

__all__ = [
    "FEATURE_ASSEMBLY_MODEL_VERSION",
    "POLICY_PROFILE_MAPPING_VERSION",
    "SCHEDULE_URGENCY_BANDS",
    "TEACHING_FREQUENCY_TO_PROFILE",
    "AuthorityName",
    "FeatureAssemblyStatus",
    "FeatureAuthority",
    "GoalPortfolioPort",
    "InitiativeClass",
    "LearningIntent",
    "LearningSnapshotPort",
    "PlannerCommands",
    "PlannerDecision",
    "PlannerDecisionOutcome",
    "PlannerEvaluation",
    "PlannerExecutionStatusRecord",
    "PlannerExecutionStatusValue",
    "PlannerProfile",
    "PlannerQueries",
    "PlannerService",
    "PlanningOutcome",
    "PlanningRequest",
    "ProfileMapping",
    "ScheduleAuthority",
    "ScheduleRowPort",
    "ScheduleViewPort",
    "SnapshotStatus",
    "TargetCandidate",
    "TargetMode",
    "TeachingPolicyPort",
    "UserIntentScope",
    "assemble_feature_authority",
    "execution_status_of",
    "goal_relevance_of",
    "profile_mapping_of",
    "schedule_authority_of",
    "schedule_urgency_of",
]
