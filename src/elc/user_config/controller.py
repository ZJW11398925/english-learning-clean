"""User Configuration / Profile Domain Controller (Phase 4 P4-3 graduation).

Phase 4 P4-3 (TASK-OPI-4d516e4f-….19 ③): this controller graduates from the
Phase 0 empty skeleton into the real User Configuration/Profile authority
face — the P3-0/P3-1A/P4-1 LearningController / TeachingController /
RelationshipController graduation precedent. docs/DOMAIN_MODEL.md §18: the
Domain Controller decides VALIDATE / COMMIT / REJECT / ABSTAIN, and §5.1
makes this context the owner of UserProfile / DisclosurePolicy ("Goal/Policy/
Profile owned by User Configuration/Profile authority, not Learning").

Three faces, three layers:

- **the sensitive-persistence gate** (§18.1 "高敏感 Profile/Relationship
  persistence 需要显式用户许可；模型不得把推断的高敏感属性直接提交为长期
  事实") — :meth:`upsert_user_profile` refuses a profile carrying any
  HIGH_SENSITIVITY fact unless the caller passes ``explicit_consent=True``.
  This is the P4-1 sensitive-memory-gate shape, one domain over: the gate is
  consulted *before* anything is written, a refusal is
  ``VALIDATION_FAILED``, and nothing about the profile reaches the store;
- **the write delegation** — the durable rows, the epoch fence and every SQL
  statement live in :mod:`elc.user_config.store`;
- **the disclosure decision** — :meth:`get_disclosed_user_profile` reads the
  profile and the user's policy and hands both to
  :func:`elc.user_config.disclosure.decide_disclosure`, the pure function
  that produces the per-persona view. The PromptCompiler can only ever see
  that view (§5.1 Rules "Persona Runtime 只能获得 DisclosedUserProfile，不能
  读取完整 UserProfile"), so the full profile never leaves this face.

Phase 6 keeps the goal/teaching-policy/session-focus faces raising:
LearningGoalPortfolio, TeachingPolicyProfile and SessionFocus belong to the
Scheduler + Goal Portfolio phase (docs/IMPLEMENTATION_PLAN.md §1.5 Phase 6),
not to this slice — each method names that phase instead of pretending.

Failure semantics: every face returns a ``Result``; nothing raises into a
caller except a stale-epoch store (a programming error, the repo-wide fence
convention).
"""

from __future__ import annotations

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    GoalVersion,
    Ok,
    PersonaId,
    PolicyVersion,
    Result,
    UserId,
)
from elc.user_config.disclosure import decide_disclosure
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosurePolicy,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingPolicyProfile,
    UserProfile,
)

__all__ = ["UserConfigController"]

#: The reason the gate gives when a high-sensitivity fact arrives without
#: consent — one string, so the refusal is recognisable without parsing it.
HIGH_SENSITIVITY_CONSENT_REQUIRED = (
    "explicit user consent required for high-sensitivity profile facts"
)


class UserConfigController:
    """Owns profile/disclosure truth over :class:`SqliteUserConfigStore`."""

    def __init__(self, store: SqliteUserConfigStore) -> None:
        self._store = store

    # -- the write face (§5.1 + §18.1) --------------------------------------

    def upsert_user_profile(
        self, profile: UserProfile, explicit_consent: bool
    ) -> Result[UserProfile]:
        """Validate → gate → commit one profile (docs/DOMAIN_MODEL.md §18.1).

        The gate is the P4-1 sensitive-memory shape: a profile carrying any
        HIGH_SENSITIVITY fact needs ``explicit_consent=True``, and the rule
        is checked **before** the store is touched, so a refused write
        leaves the durable row exactly as it was (zero writes — the profile
        is a long-term fact, and a model-inferred high-sensitivity attribute
        must never become one by write path alone).

        The content/revision rules (a stamped revision is never rewritten
        under an unchanged stamp) live in the store and surface here as
        ``CONFLICT``; everything else is the store's ``Result`` untouched.
        """

        if profile.high_sensitivity_facts and not explicit_consent:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"{HIGH_SENSITIVITY_CONSENT_REQUIRED}: user profile"
                        f" {profile.user_profile_id} carries"
                        f" {len(profile.high_sensitivity_facts)}"
                        " HIGH_SENSITIVITY fact(s) and explicit_consent=False"
                        " (docs/DOMAIN_MODEL.md §18.1)"
                    ),
                )
            )
        return self._store.upsert_user_profile(profile)

    def set_disclosure_policy(
        self, policy: DisclosurePolicy
    ) -> Result[DisclosurePolicy]:
        """Commit one disclosure policy (§5.1; "Produces DisclosedUserProfile").

        No extra gate here: a policy is not personal content — it is the
        authorization *about* content, and it authorizes nothing by itself
        (the disclosure ladder in elc.user_config.disclosure decides what
        any given level may reveal, and the default rule can never reveal
        high-sensitivity facts).
        """

        return self._store.set_disclosure_policy(policy)

    # -- the read faces -----------------------------------------------------

    def get_user_profile(self, user_id: UserId) -> Result[UserProfile | None]:
        """The full profile — this authority face may see it; persona-facing
        consumers may not (§5.1 Rules)."""

        return self._store.get_user_profile(user_id)

    def get_disclosed_user_profile(
        self, user_id: UserId, persona_id: PersonaId
    ) -> Result[DisclosedUserProfile]:
        """The action-specific minimal view (§18.1 / §24.3).

        Total by construction: a user with no profile, a user with no policy,
        or a policy that names no rule for this persona all yield the empty
        MINIMAL disclosure, never an error — an unconfigured world discloses
        nothing, which is the fail-closed reading §18.1 asks for.
        """

        profile = self._store.get_user_profile(user_id)
        if isinstance(profile, Err):
            return profile
        policy = self._store.get_disclosure_policy(user_id)
        if isinstance(policy, Err):
            return policy
        return Ok(decide_disclosure(profile.value, policy.value, persona_id))

    # -- later phases (unchanged skeletons, with accurate pointers) ---------

    def upsert_goal_portfolio(
        self, portfolio: LearningGoalPortfolio
    ) -> Result[GoalVersion]:
        raise NotImplementedError(
            "Phase 6: goal portfolio (docs/IMPLEMENTATION_PLAN.md §1.5"
            " 'Phase 6 Goal Portfolio + Scheduler views')"
        )

    def upsert_teaching_policy(
        self, policy: TeachingPolicyProfile
    ) -> Result[PolicyVersion]:
        raise NotImplementedError(
            "Phase 6: teaching policy (docs/IMPLEMENTATION_PLAN.md §1.5"
            " Phase 6)"
        )

    def set_session_focus(self, focus: SessionFocus) -> Result[SessionFocus]:
        raise NotImplementedError(
            "Phase 6: session focus re-weighting (docs/IMPLEMENTATION_PLAN.md"
            " §1.5 Phase 6)"
        )
