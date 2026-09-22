"""User Configuration / Profile query face.

The three P6-3 reads (docs/DATA_MODEL.md §9; TASK-OPI-5a0be06d-….20 ③.4) are
the constraint truth's read side:

- :meth:`UserConfigQueries.get_planner_constraint` — one row by its own
  identity, exactly as written (``None`` = never written);
- :meth:`UserConfigQueries.active_constraints` — every constraint **in force
  at** an instant: ``active`` ∧ ``starts_at <= as_of`` ∧ (``expires_at`` is
  NULL ∨ ``as_of <= expires_at``), boundaries inclusive, compared as
  instants rather than as bytes;
- :meth:`UserConfigQueries.active_constraints_for_target` — the same reading
  plus the target leg (a NULL target leg is not target-limited and applies to
  every target).

``scope`` is carried by all three and interpreted by none: §9's
``THIS_SESSION`` names a session the canonical object has **no column for**,
so which session is current is the consumer's question, and the first consumer
that must honour it is Phase 7's ``PlannerConstraintView``. The full reading,
including the refusal vocabulary for an unusable timestamp, is on the store
methods.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import (
    ConversationId,
    PersonaId,
    Result,
    TargetId,
    UserId,
)
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosurePolicy,
    LearningGoalPortfolio,
    PlannerConstraint,
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

    def get_planner_constraint(
        self, constraint_id: str
    ) -> Result[PlannerConstraint | None]:
        """One constraint by its own identity (P6-3; ``None`` = none written).

        The raw durable row — no window judgement, no clock, ``active``
        included. "In force at this instant" is what the two active reads
        answer.
        """
        ...

    def active_constraints(
        self, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """Every constraint in force at ``as_of`` (P6-3), ordered by id.

        **Derived reading** (R7), in the caller's instant: ``active`` ∧
        ``starts_at <= as_of`` ∧ (``expires_at`` is NULL ∨ ``as_of <=
        expires_at``), both boundaries inclusive, compared as instants (an
        empty, unparseable or naive ``as_of`` is ``VALIDATION_FAILED``).
        ``scope`` is carried and never interpreted here.
        """
        ...

    def active_constraints_for_target(
        self, target_type: str, target_id: TargetId, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """The constraints in force for one target at ``as_of`` (P6-3).

        The same reading plus the target leg: a NULL target leg means the
        constraint is not target-limited (and applies to every target), both
        legs matching verbatim means it applies to this one, and a
        half-declared leg applies to none. The full statement is on the store
        method.
        """
        ...
