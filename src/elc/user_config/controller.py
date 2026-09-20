"""Empty User Configuration / Profile controller (Phase 6 goal views /
Phase 1 disclosure views will implement)."""

from __future__ import annotations

from elc.platform.types import GoalVersion, PersonaId, PolicyVersion, Result, UserId
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosurePolicy,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingPolicyProfile,
    UserProfile,
)


class UserConfigController:
    """Owns profile/goal/policy truth. Phase 0: no logic."""

    def upsert_user_profile(
        self, profile: UserProfile, explicit_consent: bool
    ) -> Result[UserProfile]:
        raise NotImplementedError("Phase 1: profile with consent gate")

    def upsert_goal_portfolio(
        self, portfolio: LearningGoalPortfolio
    ) -> Result[GoalVersion]:
        raise NotImplementedError("Phase 6: goal portfolio")

    def upsert_teaching_policy(
        self, policy: TeachingPolicyProfile
    ) -> Result[PolicyVersion]:
        raise NotImplementedError("Phase 6: teaching policy")

    def set_disclosure_policy(
        self, policy: DisclosurePolicy
    ) -> Result[DisclosurePolicy]:
        raise NotImplementedError("Phase 1: disclosure policy")

    def set_session_focus(self, focus: SessionFocus) -> Result[SessionFocus]:
        raise NotImplementedError("Phase 6: session focus re-weighting")

    def get_disclosed_user_profile(
        self, user_id: UserId, persona_id: PersonaId
    ) -> Result[DisclosedUserProfile]:
        raise NotImplementedError("Phase 1: minimal disclosure view")
