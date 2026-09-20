"""User Configuration / Profile command face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import GoalVersion, PolicyVersion, Result
from elc.user_config.types import (
    DisclosurePolicy,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingPolicyProfile,
    UserProfile,
)


@runtime_checkable
class UserConfigCommands(Protocol):
    """Versioned configuration writes (never Learning Evidence)."""

    def upsert_user_profile(
        self,
        profile: UserProfile,
        explicit_consent: bool,
    ) -> Result[UserProfile]:
        """High-sensitive attributes persist only with explicit consent
        (docs/DOMAIN_MODEL.md §18.1)."""
        ...

    def upsert_goal_portfolio(
        self, portfolio: LearningGoalPortfolio
    ) -> Result[GoalVersion]:
        ...

    def upsert_teaching_policy(
        self, policy: TeachingPolicyProfile
    ) -> Result[PolicyVersion]:
        ...

    def set_disclosure_policy(
        self, policy: DisclosurePolicy
    ) -> Result[DisclosurePolicy]:
        ...

    def set_session_focus(self, focus: SessionFocus) -> Result[SessionFocus]:
        ...
