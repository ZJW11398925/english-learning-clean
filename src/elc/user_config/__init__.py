"""User Configuration / Profile bounded context (docs/DOMAIN_MODEL.md §5.1)."""

from elc.user_config.commands import UserConfigCommands
from elc.user_config.controller import (
    HIGH_SENSITIVITY_CONSENT_REQUIRED,
    UserConfigController,
)
from elc.user_config.disclosure import decide_disclosure
from elc.user_config.queries import UserConfigQueries
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    LearningGoal,
    LearningGoalPortfolio,
    ProfileFact,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
    UserProfile,
)

__all__ = [
    "HIGH_SENSITIVITY_CONSENT_REQUIRED",
    "DisclosureLevel",
    "DisclosurePolicy",
    "DisclosureRule",
    "DisclosedUserProfile",
    "LearningGoal",
    "LearningGoalPortfolio",
    "ProfileFact",
    "SessionFocus",
    "SqliteUserConfigStore",
    "TeachingFrequency",
    "TeachingPolicyProfile",
    "UserConfigCommands",
    "UserConfigController",
    "UserConfigQueries",
    "UserProfile",
    "decide_disclosure",
]
