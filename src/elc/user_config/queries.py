"""User Configuration / Profile query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import PersonaId, Result, UserId
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosurePolicy,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingPolicyProfile,
    UserProfile,
)


@runtime_checkable
class UserConfigQueries(Protocol):
    """Configuration reads; Persona Runtime gets only DisclosedUserProfile."""

    def get_user_profile(self, user_id: UserId) -> Result[UserProfile | None]:
        ...

    def get_disclosed_user_profile(
        self, user_id: UserId, persona_id: PersonaId
    ) -> Result[DisclosedUserProfile]:
        """Action-specific minimal disclosure view (§18.1)."""
        ...

    def get_goal_portfolio(
        self, user_id: UserId
    ) -> Result[LearningGoalPortfolio | None]:
        ...

    def get_teaching_policy(
        self, user_id: UserId
    ) -> Result[TeachingPolicyProfile | None]:
        ...

    def get_disclosure_policy(
        self, user_id: UserId, persona_id: PersonaId | None
    ) -> Result[DisclosurePolicy | None]:
        ...

    def get_session_focus(
        self, user_id: UserId
    ) -> Result[SessionFocus | None]:
        ...
