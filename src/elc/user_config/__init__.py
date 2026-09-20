"""User Configuration / Profile bounded context (docs/DOMAIN_MODEL.md §5.1)."""

from elc.user_config.commands import UserConfigCommands
from elc.user_config.controller import UserConfigController
from elc.user_config.queries import UserConfigQueries
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosedUserProfile,
    LearningGoal,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
    UserProfile,
)

__all__ = [
    "DisclosureLevel",
    "DisclosurePolicy",
    "DisclosedUserProfile",
    "LearningGoal",
    "LearningGoalPortfolio",
    "SessionFocus",
    "TeachingFrequency",
    "TeachingPolicyProfile",
    "UserConfigCommands",
    "UserConfigController",
    "UserConfigQueries",
    "UserProfile",
]
