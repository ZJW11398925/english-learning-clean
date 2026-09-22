"""User Configuration / Profile query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import ConversationId, PersonaId, Result, UserId
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
        """The user's long-term portfolio (P6-0; ``None`` = never written).

        Keyed by the user's own id — the Local V1 convention §5.1's missing
        owner column forces (``goal_portfolio_id`` is the user's id; the
        ``user_profile_id`` precedent).
        """
        ...

    def get_teaching_policy(
        self, user_id: UserId
    ) -> Result[TeachingPolicyProfile | None]:
        """The user's teaching policy (P6-0; same keying convention)."""
        ...

    def get_disclosure_policy(
        self, user_id: UserId, persona_id: PersonaId | None
    ) -> Result[DisclosurePolicy | None]:
        ...

    def get_session_focus(
        self, session_focus_id: str
    ) -> Result[SessionFocus | None]:
        """One focus by its own identity (P6-0).

        The Phase 0 placeholder spelled this parameter ``user_id``; §5.1's
        SessionFocus has no user leg (it names a conversation), so the read
        is keyed by ``session_focus_id`` — the object's own key — and the
        parameter is spelled to match the face it mirrors.
        """
        ...

    def get_session_focus_for_conversation(
        self, conversation_id: ConversationId
    ) -> Result[SessionFocus | None]:
        """The conversation's current focus (P6-1, F-7; ``None`` = none).

        §5.1 leaves the object reachable only by its own id, which a consumer
        holding a conversation cannot use; this read answers by conversation
        instead. **Derived reading**: the current focus is the one with the
        largest ``starts_at``, ties broken by the largest
        ``session_focus_id`` (lexicographic), with **no** ``expires_at``
        filter and **no** clock comparison — whether a window is still valid
        is the consumer's call. The full statement is on the store method.
        """
        ...
