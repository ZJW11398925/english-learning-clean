"""User Configuration / Profile command face.

The P6-3 pair (docs/DATA_MODEL.md §9; TASK-OPI-5a0be06d-….20 ③.4) is the
constraint write face, and its split is deliberate:

- :meth:`UserConfigCommands.record_planner_constraint` — the content write.
  §9 carries no version column, so the identity is append-first: the same
  ``constraint_id`` with the same content is an idempotent replay, and the
  same id with different content is refused rather than rewritten (a
  different constraint is a different id);
- :meth:`UserConfigCommands.set_planner_constraint_active` — the flag
  transfer, and the **only** way ``active`` moves. BF-03 makes re-enabling a
  user constraint the User Constraint layer's act ("Gate 不偷偷修改用户约束"),
  so the content write refuses a differing flag instead of carrying it; the
  rules are stated in elc.user_config.store.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import GoalVersion, PolicyVersion, Result
from elc.user_config.types import (
    DisclosurePolicy,
    LearningGoalPortfolio,
    PlannerConstraint,
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

    def record_planner_constraint(
        self, constraint: PlannerConstraint
    ) -> Result[PlannerConstraint]:
        """Commit one user constraint (§9; P6-3).

        The durable row comes back. ``active`` is **content** here: a
        constraint whose flag differs from the durable row is refused, and the
        flag moves through :meth:`set_planner_constraint_active` alone.
        """
        ...

    def set_planner_constraint_active(
        self, constraint_id: str, active: bool
    ) -> Result[PlannerConstraint]:
        """Move the one movable column of a constraint (R6; P6-3).

        The face BF-03 requires: a suppression the user can only *enter* would
        make ``UNTIL_USER_REENABLES`` unendable. Unknown id = ``NOT_FOUND``;
        the current value again = an idempotent replay.
        """
        ...
