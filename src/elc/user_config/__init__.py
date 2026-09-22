"""User Configuration / Profile bounded context (docs/DOMAIN_MODEL.md §5.1)."""

from elc.user_config.commands import UserConfigCommands
from elc.user_config.constraints import (
    applies_to,
    build_view,
    entries_for_target,
    entries_of_type,
    target_leg_of,
)
from elc.user_config.controller import (
    HIGH_SENSITIVITY_CONSENT_REQUIRED,
    UserConfigController,
)
from elc.user_config.disclosure import decide_disclosure
from elc.user_config.queries import UserConfigQueries
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    PLANNER_CONSTRAINT_SCOPES,
    PLANNER_CONSTRAINT_TYPES,
    DisclosedUserProfile,
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    EffectiveSessionFocusView,
    LearningGoal,
    LearningGoalPortfolio,
    PlannerConstraint,
    PlannerConstraintEntry,
    PlannerConstraintScope,
    PlannerConstraintType,
    PlannerConstraintView,
    ProfileFact,
    SessionFocus,
    TargetLeg,
    TeachingFrequency,
    TeachingPolicyProfile,
    UserProfile,
)

__all__ = [
    "HIGH_SENSITIVITY_CONSENT_REQUIRED",
    "PLANNER_CONSTRAINT_SCOPES",
    "PLANNER_CONSTRAINT_TYPES",
    "DisclosureLevel",
    "DisclosurePolicy",
    "DisclosureRule",
    "DisclosedUserProfile",
    "EffectiveSessionFocusView",
    "LearningGoal",
    "LearningGoalPortfolio",
    "PlannerConstraint",
    "PlannerConstraintEntry",
    "PlannerConstraintScope",
    "PlannerConstraintType",
    "PlannerConstraintView",
    "ProfileFact",
    "SessionFocus",
    "SqliteUserConfigStore",
    "TargetLeg",
    "TeachingFrequency",
    "TeachingPolicyProfile",
    "UserConfigCommands",
    "UserConfigController",
    "UserConfigQueries",
    "UserProfile",
    "applies_to",
    "build_view",
    "decide_disclosure",
    "entries_for_target",
    "entries_of_type",
    "target_leg_of",
]
