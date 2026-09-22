"""User Configuration / Profile Domain Controller (Phase 4 P4-3 graduation;
Phase 6 P6-0 graduation of the three remaining faces).

Phase 4 P4-3 (TASK-OPI-4d516e4f-….19 ③): this controller graduates from the
Phase 0 empty skeleton into the real User Configuration/Profile authority
face — the P3-0/P3-1A/P4-1 LearningController / TeachingController /
RelationshipController graduation precedent. docs/DOMAIN_MODEL.md §18: the
Domain Controller decides VALIDATE / COMMIT / REJECT / ABSTAIN, and §5.1
makes this context the owner of UserProfile / DisclosurePolicy / the
portfolios ("Goal/Policy/Profile owned by User Configuration/Profile
authority, not Learning").

Phase 6 P6-0 (TASK-OPI-a68fd9eb-….48 ④): the three faces that used to raise
with a phase pointer are real too — :meth:`upsert_goal_portfolio`,
:meth:`upsert_teaching_policy`, :meth:`set_session_focus`, plus the three
reads (:meth:`get_goal_portfolio`, :meth:`get_teaching_policy`,
:meth:`get_session_focus`). Nothing about the P4-3 faces changed: the
profile/disclosure methods, their gate and the disclosure ladder are the
same source they were, and the persona-facing port still carries only
``DisclosedUserProfile``.

Phase 6 P6-1 (TASK-OPI-6259f6fd-….12 ②⑥, F-7): one incremental read lands —
:meth:`get_session_focus_for_conversation`, the per-conversation route §5.1's
object had none of. Nothing else about P6-0's faces changed: the id-keyed
:meth:`get_session_focus` still answers the way it did, and the write faces
are untouched.

Phase 6 P6-3 (TASK-OPI-5a0be06d-….20 ③.4): §9's PlannerConstraint gets the
five faces the durable row needs — two writes
(:meth:`record_planner_constraint`, :meth:`set_planner_constraint_active`) and
three reads (:meth:`get_planner_constraint`, :meth:`active_constraints`,
:meth:`active_constraints_for_target`). Like the P6-0 faces, they add **no**
rule of their own: every refusal, the append-first identity and the
instant-window reading are the store's, stated once there. **Nothing consumes
a constraint yet**: no Planner reads these rows, no Gate consults them, and no
face turns a user's sentence into one (Phase 8's extraction face).

P7-0 (TASK-OPI-b99560d4-….36 ①④): two **consumer views** land —
:meth:`get_effective_session_focus` (the conversation's focus in force at an
instant, ``expires_at`` honoured, instants parsed) and
:meth:`get_planner_constraint_view` (the in-force rows normalized, the
half-declared target leg and the ``THIS_SESSION`` binding frozen in
:mod:`elc.user_config.constraints`). Neither adds a column, writes a row or
changes an existing face: the byte-order focus read and the three constraint
reads answer exactly what they answered before.

Six faces, the same three layers:

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

The goal/policy/focus faces add **no** gate and **no** rule of their own:
the version discipline (a moved version replaces, the same version with
different content is refused) and the append-first identity rule of
SessionFocus are the store's, stated once in elc.user_config.store. What
this face owes is the *shape* of the answer: the two Phase 0 write faces
declare a version as their result (``Result[GoalVersion]`` /
``Result[PolicyVersion]``) and the focus face declares the durable focus, so
the version-returning faces hand back the version of the durable row the
store just wrote — the same value a later ``get_goal_portfolio`` /
``get_teaching_policy`` reads back.

Failure semantics: every face returns a ``Result``; nothing raises into a
caller except a stale-epoch store (a programming error, the repo-wide fence
convention).
"""

from __future__ import annotations

from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    GoalVersion,
    Ok,
    PersonaId,
    PolicyVersion,
    Result,
    TargetId,
    UserId,
)
from elc.user_config.constraints import build_view
from elc.user_config.disclosure import decide_disclosure
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    DisclosedUserProfile,
    DisclosurePolicy,
    EffectiveSessionFocusView,
    LearningGoalPortfolio,
    PlannerConstraint,
    PlannerConstraintView,
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

    # -- the goal / policy / focus faces (Phase 6 P6-0) ---------------------

    def upsert_goal_portfolio(
        self, portfolio: LearningGoalPortfolio
    ) -> Result[GoalVersion]:
        """Commit one long-term goal portfolio (§5.1; the P6-0 face).

        The Phase 0 interface declares the *version* as this face's result,
        so the version of the durable row the store wrote is what comes back
        — identical to the ``goal_version`` a later :meth:`get_goal_portfolio`
        reads. The version discipline itself (a moved version replaces the
        content; the same version with different content is refused) is the
        store's, stated once there.

        No gate here: a portfolio is configuration, not personal content. The
        §18.1 consent gate belongs to profile facts, and DOMAIN_MODEL §5.1's
        rule that a temporary focus may not silently modify long-term goals
        is structural — a focus is another table (:mod:`elc.user_config.store`),
        and nothing in this face reads or writes it.
        """

        written = self._store.upsert_goal_portfolio(portfolio)
        if isinstance(written, Err):
            return written
        return Ok(written.value.goal_version)

    def upsert_teaching_policy(
        self, policy: TeachingPolicyProfile
    ) -> Result[PolicyVersion]:
        """Commit one teaching policy (§5.1; the P6-0 face).

        Same shape as the portfolio face: the declared result is the durable
        ``policy_version``. A policy is how/how-often configuration
        (DOMAIN_MODEL §5.1 Rules "TeachingPolicy 只改变'如何/多频繁教学'，不改
        Learner State truth"), which is why this face has no Learning port at
        all — it cannot touch evidence or state even by mistake.
        """

        written = self._store.upsert_teaching_policy(policy)
        if isinstance(written, Err):
            return written
        return Ok(written.value.policy_version)

    def set_session_focus(self, focus: SessionFocus) -> Result[SessionFocus]:
        """Commit one temporary re-weighting (§5.1; the P6-0 face).

        The durable focus comes back. The identity rule is the store's: §5.1
        pins no version column for this object, so the same
        ``session_focus_id`` with different content is refused instead of
        rewritten — a new focus is a new id (append-first). Writing a focus
        never touches a goal portfolio row (DOMAIN_MODEL §5.1 Rules), and
        that is pinned by test rather than promised here.
        """

        return self._store.set_session_focus(focus)

    # -- the goal / policy / focus reads (Phase 6 P6-0) ---------------------

    def get_goal_portfolio(
        self, user_id: UserId
    ) -> Result[LearningGoalPortfolio | None]:
        """The user's long-term goal portfolio (``None`` = never written).

        The Local V1 keying convention applies: ``goal_portfolio_id`` is the
        user's own id (§5.1 pins no owner column; the ``user_profile_id``
        precedent, declared in :mod:`elc.user_config.store`).
        """

        return self._store.get_goal_portfolio(user_id)

    def get_teaching_policy(
        self, user_id: UserId
    ) -> Result[TeachingPolicyProfile | None]:
        """The user's teaching policy (``None`` = never written)."""

        return self._store.get_teaching_policy(user_id)

    def get_session_focus(
        self, session_focus_id: str
    ) -> Result[SessionFocus | None]:
        """One session focus by its own identity (``None`` = never written).

        §5.1's SessionFocus has no user leg — it names a conversation — so
        this read is keyed by ``session_focus_id``, the object's own key,
        rather than by the user keying convention the four user-owned rows
        share.
        """

        return self._store.get_session_focus(session_focus_id)

    def get_session_focus_for_conversation(
        self, conversation_id: ConversationId
    ) -> Result[SessionFocus | None]:
        """The conversation's current focus (P6-1, F-7; ``None`` = none).

        The read a consumer holding a *conversation* needs: §5.1 makes the
        focus reachable only by its own id, and several focuses for one
        conversation over time are the append-first history migration 0011
        keeps. The current one is the row with the largest ``starts_at``,
        ties broken by the largest ``session_focus_id`` (lexicographic), with
        **no** ``expires_at`` filter and **no** clock comparison — a derived
        reading, declared in full (with its reasons) on the store method.

        Pure delegation, like the rest of this face: the ordering rule and the
        decode live in :mod:`elc.user_config.store`, one layer down.
        """

        return self._store.get_session_focus_for_conversation(conversation_id)

    # -- the consumer views (Phase 7 P7-0) ----------------------------------

    def get_effective_session_focus(
        self, conversation_id: ConversationId, as_of: str
    ) -> Result[EffectiveSessionFocusView | None]:
        """The conversation's focus in force at ``as_of`` (P7-0; ``None`` = none).

        The consumer-side overlay §5.1's ``expires_at?`` needs: real instants,
        inclusive boundaries, and ``None`` for "nothing governs this
        conversation at this instant". **The byte-order read this package
        already shipped is untouched** — :meth:`get_session_focus_for_conversation`
        still answers by ``(starts_at, session_focus_id)`` byte order with no
        clock, and its pinned test still holds; a consumer that needs the
        byte-order winner asks that face. The window reading, its boundaries and
        the winner rule live in :mod:`elc.user_config.store` (one statement of
        the rule), and this face only states the view's shape: the row's seven
        columns plus the ``as_of`` the reading was made at.
        """

        effective = self._store.effective_session_focus(
            conversation_id, as_of
        )
        if isinstance(effective, Err):
            return effective
        if effective.value is None:
            return Ok(None)
        focus = effective.value
        return Ok(
            EffectiveSessionFocusView(
                session_focus_id=focus.session_focus_id,
                conversation_id=focus.conversation_id,
                base_goal_portfolio_version=(
                    focus.base_goal_portfolio_version
                ),
                temporary_goal_weights=focus.temporary_goal_weights,
                manual_focus_target=focus.manual_focus_target,
                starts_at=focus.starts_at,
                expires_at=focus.expires_at,
                as_of=as_of,
            )
        )

    def get_planner_constraint_view(
        self, as_of: str, bound_conversation_id: ConversationId
    ) -> Result[PlannerConstraintView]:
        """The constraints in force at ``as_of``, as a consumer reads them (P7-0).

        Two steps, each with one home: the rows are the store's reading
        (``active_constraints`` — ``active`` ∧ the instant window, boundaries
        inclusive, unreadable stamps refused), and their normalization plus the
        two frozen readings (the half-declared target leg, the ``THIS_SESSION``
        binding) are :func:`elc.user_config.constraints.build_view`'s, a pure
        module. Nothing here branches on a constraint and nothing applies one:
        the suppression a row will one day cause is the consumer's — this is the
        *shape* handed over, not a decision (the P6-3 statement stands).
        """

        rows = self._store.active_constraints(as_of)
        if isinstance(rows, Err):
            return rows
        return Ok(
            build_view(
                rows.value,
                as_of=as_of,
                bound_conversation_id=bound_conversation_id,
            )
        )

    # -- the constraint faces (Phase 6 P6-3) --------------------------------

    def record_planner_constraint(
        self, constraint: PlannerConstraint
    ) -> Result[PlannerConstraint]:
        """Commit one user constraint (§9; the P6-3 content write).

        The durable row comes back. Everything that can refuse it is the
        store's and is stated there: the append-first identity (§9 carries no
        version column, so the same id with different content is refused
        rather than rewritten — a different constraint is a different id), the
        ``NOT_FOUND`` for a ``created_from_turn_id`` that names no durable
        turn, and the ``VALIDATION_FAILED`` for a ``target_type`` outside §9's
        two words.

        **``active`` is content on this face**: an inbound constraint whose
        flag differs from the durable row is refused like any other
        difference. The flag moves through :meth:`set_planner_constraint_active`
        and nowhere else (R6 — the store's docstring carries the BF-03 reason).
        """

        return self._store.record_planner_constraint(constraint)

    def set_planner_constraint_active(
        self, constraint_id: str, active: bool
    ) -> Result[PlannerConstraint]:
        """Move the one movable column of a constraint (R6; the P6-3 face).

        BF-03 makes re-enabling (or clearing) a user constraint the User
        Constraint layer's act — "Gate 不偷偷修改用户约束" — which is why this
        face exists at all: without it ``UNTIL_USER_REENABLES`` could never
        end. It writes ``active`` and nothing else, a ``constraint_id`` with no
        durable row is ``NOT_FOUND``, and transferring the current value is an
        idempotent replay. The rules are the store's.
        """

        return self._store.set_planner_constraint_active(constraint_id, active)

    def get_planner_constraint(
        self, constraint_id: str
    ) -> Result[PlannerConstraint | None]:
        """One constraint by its own identity (``None`` = never written).

        The raw durable row, ``active`` included, with no window judgement:
        "is it in force at this instant?" is what the two active reads answer.
        """

        return self._store.get_planner_constraint(constraint_id)

    def active_constraints(
        self, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """Every constraint in force at ``as_of`` (ordered by id).

        **Derived reading** (R7): ``active`` ∧ ``starts_at <= as_of`` ∧
        (``expires_at`` is NULL ∨ ``as_of <= expires_at``), both boundaries
        inclusive, compared as **instants** (ISO-8601 with a UTC offset; an
        empty, unparseable or naive ``as_of`` is ``VALIDATION_FAILED``, never
        assumed to be UTC). ``scope`` is carried and **not** interpreted — in
        particular ``THIS_SESSION`` names a session the canonical object has no
        column for, so which session is current stays the consumer's question
        (Phase 7's view). The full statement is on the store method.
        """

        return self._store.active_constraints(as_of)

    def active_constraints_for_target(
        self, target_type: str, target_id: TargetId, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """The constraints in force for one target at ``as_of`` (R7).

        The same reading as :meth:`active_constraints` plus the target leg: a
        row with a NULL target leg is not target-limited and applies to every
        target, a row whose two legs match the arguments verbatim applies to
        this one, and a half-declared target leg applies to none. Ordering,
        boundaries and refusals are the store's, identical to the read above.
        """

        return self._store.active_constraints_for_target(
            target_type, target_id, as_of
        )
