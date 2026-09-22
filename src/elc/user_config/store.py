"""SQLite durable store for User Configuration / Profile (Phase 4 P4-3,
extended by Phase 6 P6-0 and P6-3).

The bounded context owns UserProfile / DisclosurePolicy / LearningGoalPortfolio
/ TeachingPolicyProfile / SessionFocus truth (docs/DOMAIN_MODEL.md §5.1), so
its durable executor lives in the domain package — the conversation /
learning / teaching / relationship store precedent. The authority face is
elc.user_config.controller; the pure disclosure decision is
elc.user_config.disclosure; every byte that reaches the disk is here, in the
six tables migrations 0010, 0011 and 0013 create.

**Versioned objects (P6-0, migration 0011).** goal_portfolio and
teaching_policy follow the discipline the two P4-3 tables already ship:

- **idempotent replay** — the same id with the same version *and* the same
  content returns the durable row and writes nothing (the crash-retry face);
- **a moved version** — a different ``goal_version`` / ``policy_version``
  replaces the content and stamps a fresh ``updated_at`` from this store's
  own clock;
- **a stamped version that would be rewritten** — the same version with
  *different* content is a ``CONFLICT``: a version is a version stamp, not
  decoration (DATA_MODEL §1.4 "version every derived model"), and a silent
  content change under an unchanged stamp is exactly the drift the stamp
  exists to prevent. §5.1 pins no ordering for these stamps, so "前进" is
  spelled "differs" here — the store compares versions for equality, never
  for order.

**SessionFocus — no stamp column, one-shot identity.** §5.1 gives this
object no ``version`` / ``revision`` column at all (``base_goal_portfolio_
version`` names the portfolio the focus was derived from, not the focus's
own version), so there is no stamp to compare and no stamp to move. The rule
this slice declares, and why:

- the identity is ``session_focus_id``; the same id with the same content is
  an idempotent replay (returns the durable row, writes nothing);
- the same id with *different* content is a ``CONFLICT`` — **not** a
  replace. Without a version there is no way for a caller to declare "this
  is a new version of the focus under the same id", so rewriting the row in
  place would be precisely the silent content change under an unchanged
  identity the rest of this store refuses (DATA_MODEL §1.4), and a durable
  row that nothing could version. A new focus is a new object (a new
  ``session_focus_id``), which is also the append-first reading §5.1's
  ``starts_at`` / ``expires_at`` window invites (DATA_MODEL §1.3: 不原地抹除
  历史) — several focuses for one conversation over time are the history,
  and migration 0011 deliberately lands no unique index on
  ``conversation_id``.

Fencing: every write checks the store epoch against the newest durable epoch
before anything is written (the teaching / relationship store precedent; a
stale store is a programming error and raises).

**PlannerConstraint — the user's own constraint, with one movable column
(P6-3, migration 0013).** docs/DATA_MODEL.md §9's object, placed in this
package as a derived judgement (the reasons are in elc/user_config/types.py;
§5.1's Owns list does not name it). Two rules govern its rows, and both are
declared here:

- **content is append-first, like SessionFocus.** §9 carries no ``version`` /
  ``revision`` column, so there is no stamp to move: the same
  ``constraint_id`` with the same content is an idempotent replay, and the
  same id with *different* content is a ``CONFLICT`` rather than a rewrite
  (docs/DATA_MODEL.md §1.3/§1.4). **This holds for every column including
  ``active``**: an inbound constraint whose ``active`` differs from the
  durable row is refused too, so the content-write face cannot carry a flag
  change through it;
- **``active`` has its own transfer face** — :meth:`set_planner_constraint_
  active`, and it is the only place the flag moves. The reason is BF-03's
  rule that re-enabling a constraint is the User Constraint layer's act
  ("Gate 不偷偷修改用户约束"): a suppression the user can only *enter* would make
  ``UNTIL_USER_REENABLES`` unendable. The transfer writes the one column and
  touches no other, and re-transferring the current value writes nothing at
  all (the idempotent-replay rule, applied to the flag).

**The active-window read faces compare instants, not bytes (P6-3).**
:meth:`SqliteUserConfigStore.active_constraints` and its target-scoped sibling
answer "which constraints are in force at ``as_of``": ``active`` ∧
``starts_at <= as_of`` ∧ (``expires_at`` is NULL ∨ ``as_of <= expires_at``).
The comparison is ``datetime``-based, because the question is temporal —
the deliberate opposite of p6-1's byte-order rule for ``created_at``'s
immutable replay, which asks "is this the same durable fact?" rather than "has
the moment arrived?" (the same split :mod:`elc.scheduler.spacing` declares for
its own window). ``starts_at`` / ``expires_at`` / ``as_of`` are ISO-8601
instants carrying a UTC offset, and an empty, unparseable or naive one is
refused with ``VALIDATION_FAILED`` rather than assumed to be UTC.

**``scope`` is carried, never interpreted (P6-3).** No read face here branches
on it, and none can: §9's ``THIS_SESSION`` names a session and the object has
**no conversation column** anywhere in the canonical block, so "which session
is current?" is a question this table cannot answer and this module does not
guess at. The three words travel verbatim and the first consumer that must
honour one (Phase 7's ``PlannerConstraintView``) owns that reading. Revisit
condition: a consumer that needs a session leg the canonical block does not
carry is a canonical revision, not an implementation choice.

Keying convention (Local V1, declared rather than assumed): §5.1 pins
``user_profile_id``, ``disclosure_policy_id``, ``goal_portfolio_id`` and
``teaching_policy_profile_id`` but **no owner column** linking any of them
to a user, so this slice keys all four by the user's own id —
``UserProfile.user_profile_id`` and ``LearningGoalPortfolio.goal_portfolio_id``
are typed ``UserId``, and ``get_teaching_policy(user_id)`` reads the row
whose ``teaching_policy_profile_id`` is that user's id. A second table or an
added column would exceed the canonical column set (§2 non-goals
notwithstanding, the *set* is canonical), so the linking rule lives here, in
one place, and the controller names it too. ``SessionFocus`` needs no such
convention: §5.1 gives it ``conversation_id`` and it is read by its own id —
plus, since P6-1's F-7, by conversation
(:meth:`SqliteUserConfigStore.get_session_focus_for_conversation`, where the
"which focus is current" reading is declared and its clock-free, deterministic
nature is stated).

The two time columns a caller owns — ``effective_from`` (portfolio /
policy) and ``starts_at`` / ``expires_at`` (focus) — are carried **verbatim**:
the store never invents an effective date or a window, because only the
caller can say when a configuration or a focus applies; ``updated_at`` is
the only column this module's clock writes.

The BF-05 sensitive-memory gate is **not** here: this module persists what it
is handed, and refuses only the revision/version conflicts above. The consent
gate (§18.1) is the controller's, one layer up — the P4-1 split (validate / gate
in the domain face, rows here) kept identical.

All SQL is a fixed literal with bound parameters — no identifier assembly,
no runtime value in any statement text. The list/map columns follow migration
0004/0009/0010's storage note: a canonical list stores as JSON text with
sorted keys, never as a second table.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Mapping, TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    GoalId,
    GoalModality,
    GoalVersion,
    Ok,
    PersonaId,
    PolicyVersion,
    Result,
    TargetId,
    TurnId,
    UserId,
)
from elc.relationship.types import MemorySensitivityClass
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    LearningGoal,
    LearningGoalPortfolio,
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
    ProfileFact,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
    UserProfile,
)

__all__ = ["StaleStoreEpochError", "SqliteUserConfigStore"]

T = TypeVar("T")

#: §9's two ``target_type`` words — the vocabulary 0004/0005/0012 already
#: enforce and migration 0013 restates on this table. Declared here as the
#: write face's pre-check so a bad value comes back as this domain's
#: ``VALIDATION_FAILED`` rather than as a bare sqlite CHECK failure.
_TARGET_TYPES = ("RESOURCE", "CAPABILITY")


class StaleStoreEpochError(StaleEpochError):
    """This store's epoch is no longer the newest durable epoch."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _facts_document(facts: tuple[ProfileFact, ...]) -> str:
    return json.dumps(
        [
            {"sensitivity": fact.sensitivity.value, "text": fact.text}
            for fact in facts
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def _facts_from_document(document: str) -> tuple[ProfileFact, ...]:
    loaded = json.loads(document)
    return tuple(
        ProfileFact(
            text=str(item["text"]),
            sensitivity=MemorySensitivityClass(str(item["sensitivity"])),
        )
        for item in loaded
    )


def _strings_document(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), sort_keys=True, separators=(",", ":"))


def _strings_from_document(document: str) -> tuple[str, ...]:
    loaded = json.loads(document)
    return tuple(str(item) for item in loaded)


def _rules_document(rules: tuple[DisclosureRule, ...]) -> str:
    return json.dumps(
        [
            {
                "disclosure_level": rule.disclosure_level.value,
                "persona_id": (
                    None if rule.persona_id is None else str(rule.persona_id)
                ),
            }
            for rule in rules
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def _rules_from_document(document: str) -> tuple[DisclosureRule, ...]:
    loaded = json.loads(document)
    return tuple(
        DisclosureRule(
            persona_id=(
                None
                if item["persona_id"] is None
                else PersonaId(str(item["persona_id"]))
            ),
            disclosure_level=DisclosureLevel(str(item["disclosure_level"])),
        )
        for item in loaded
    )


def _goals_document(goals: tuple[LearningGoal, ...]) -> str:
    """The §5.1 ``goals[]`` column: one JSON array of goal documents."""

    return json.dumps(
        [
            {
                "description": goal.description,
                "goal_id": str(goal.goal_id),
                "goal_modality": goal.goal_modality.value,
            }
            for goal in goals
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def _goals_from_document(document: str) -> tuple[LearningGoal, ...]:
    loaded = json.loads(document)
    return tuple(
        LearningGoal(
            goal_id=GoalId(str(item["goal_id"])),
            goal_modality=GoalModality(str(item["goal_modality"])),
            description=str(item["description"]),
        )
        for item in loaded
    )


def _weights_document(weights: Mapping[GoalModality, float]) -> str:
    """A ``GoalModality → float`` weight column (a JSON object).

    The document is also this module's **normal form** for comparing two
    weight mappings: sorted keys, no whitespace, so two mappings that say the
    same thing in a different insertion order compare equal — and two that
    differ in any pair (including an extra zero) do not.
    """

    return json.dumps(
        {key.value: float(weight) for key, weight in weights.items()},
        sort_keys=True,
        separators=(",", ":"),
    )


def _weights_from_document(document: str) -> dict[GoalModality, float]:
    loaded = json.loads(document)
    return {
        GoalModality(str(key)): float(value) for key, value in loaded.items()
    }


def _parse_instant(text: str, *, field: str) -> Result[datetime]:
    """One ISO-8601 timestamp of this store's inputs, as an instant (P6-3).

    ``field`` names the column in the message, so a refusal says which input
    was unusable (the row's id travels beside it, never inside it). The three
    refusals are ``VALIDATION_FAILED`` and are worded here — an exception's own
    text never travels (this file's one-vocabulary rule):

    - empty: an instant that was never written cannot be compared;
    - unparseable: not ISO-8601 in any spelling ``datetime`` accepts;
    - **naive**: no UTC offset. This store will not assume a zone for a
      caller, exactly as :func:`elc.scheduler.spacing.parse_instant` refuses
      to for the Scheduler's window.

    The same three refusals are declared by that function, and this is a
    second declaration rather than an import: this package imports no other
    domain (the scheduler's own rule, which p6-1/p6-2 kept), so the reading is
    restated here and pinned by this suite's own tests rather than borrowed
    across a package boundary.
    """

    if not text:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} is empty; an instant must be an ISO-8601 timestamp"
            " carrying a UTC offset",
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} {text!r} is not an ISO-8601 timestamp",
        )
    if parsed.tzinfo is None:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} {text!r} carries no UTC offset; this store will not"
            " assume a zone (write the offset, e.g. +00:00)",
        )
    return Ok(parsed)


def _constraint_from_row(row: tuple[object, ...]) -> PlannerConstraint:
    """One ``planner_constraint`` row (the 0013 column order) decoded.

    One decode point, five readers: the content write face's replay check, the
    ``active`` transfer, and the three read faces.
    """

    return PlannerConstraint(
        constraint_id=str(row[0]),
        target_type=None if row[1] is None else str(row[1]),
        target_id=None if row[2] is None else TargetId(str(row[2])),
        constraint_type=PlannerConstraintType(str(row[3])),
        scope=PlannerConstraintScope(str(row[4])),
        starts_at=str(row[5]),
        expires_at=None if row[6] is None else str(row[6]),
        created_from_turn_id=(
            None if row[7] is None else TurnId(str(row[7]))
        ),
        active=bool(row[8]),
    )


def _same_constraint(
    durable: PlannerConstraint, incoming: PlannerConstraint
) -> bool:
    """Whether the durable row already holds exactly this content.

    Every one of the nine §9 columns is compared, ``active`` included: a
    constraint has no version stamp, so the only way a caller can declare
    "this is the constraint I already wrote" is to hand back the same content
    — and a differing ``active`` is a flag change, which belongs to
    :meth:`SqliteUserConfigStore.set_planner_constraint_active` rather than to
    the content-write face (the R6 exception, stated in :mod:`elc.user_config`
    types and in the module docstring).
    """

    return (
        durable.target_type == incoming.target_type
        and durable.target_id == incoming.target_id
        and durable.constraint_type == incoming.constraint_type
        and durable.scope == incoming.scope
        and durable.starts_at == incoming.starts_at
        and durable.expires_at == incoming.expires_at
        and durable.created_from_turn_id == incoming.created_from_turn_id
        and durable.active == incoming.active
    )


def _matches_target(
    constraint: PlannerConstraint, target_type: str, target_id: TargetId
) -> bool:
    """Whether a constraint speaks about this ``(target_type, target_id)``.

    Two ways to match, and a half-null row matches neither (the R7 reading):

    - **the target leg is NULL** — ``target_type is None`` **and**
      ``target_id is None`` — which is what "非目标限定" means: a constraint
      about teaching/review/chat in general, not about one target. Such a row
      is in force for every target;
    - **both legs match verbatim** — ``target_type`` equal as text and
      ``target_id`` equal as text.

    A row carrying one leg and not the other is not called illegal by this
    store (:class:`elc.user_config.types.PlannerConstraint` says why: §9 pins
    no such rule), but it is *not target-limited either*, so it matches no
    target and is returned by no target-scoped read. It stays visible through
    :meth:`SqliteUserConfigStore.get_planner_constraint`, where no matching is
    involved.
    """

    if constraint.target_type is None and constraint.target_id is None:
        return True
    return (
        constraint.target_type == target_type
        and constraint.target_id is not None
        and str(constraint.target_id) == str(target_id)
    )


class SqliteUserConfigStore:
    """Durable ``user_profile`` / ``disclosure_policy`` / ``goal_portfolio``
    / ``teaching_policy`` / ``session_focus`` rows."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"user_config store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- the write units ---------------------------------------------------

    def upsert_user_profile(self, profile: UserProfile) -> Result[UserProfile]:
        """One durable profile write; the timestamps are the store's.

        ``profile.updated_at`` is ignored — the durable clock is this
        module's, exactly as in the teaching / relationship stores. The value
        that comes back is the *durable* state (stamped, and identical to
        what a later read returns), never the caller's construction.
        """

        user_id = profile.user_profile_id
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._profile_row(user_id)
                if existing is not None and existing.revision == profile.revision:
                    if _same_profile(existing, profile):
                        return Ok(
                            UserProfile(
                                user_profile_id=user_id,
                                revision=existing.revision,
                                profile_facts=existing.facts,
                                preferences=existing.preferences,
                                settings=existing.settings,
                                updated_at=existing.updated_at,
                            )
                        )
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"user profile {user_id} already carries revision"
                        f" {profile.revision} with different content; bump the"
                        " revision to change the profile (docs/DATA_MODEL.md"
                        " §1.4)",
                    )
                now = _now()
                if existing is None:
                    self._insert_profile(profile, now=now)
                else:
                    self._replace_profile(profile, now=now)
                return Ok(
                    UserProfile(
                        user_profile_id=user_id,
                        revision=profile.revision,
                        profile_facts=profile.profile_facts,
                        preferences=profile.preferences,
                        settings=profile.settings,
                        updated_at=now,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def set_disclosure_policy(
        self, policy: DisclosurePolicy
    ) -> Result[DisclosurePolicy]:
        """One durable disclosure-policy write; same stamp discipline."""

        policy_id = policy.disclosure_policy_id
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._policy_row(policy_id)
                if existing is not None:
                    if existing.revision == policy.revision:
                        if existing.rules == policy.rules:
                            return Ok(existing)
                        return _err(
                            DomainErrorCode.CONFLICT,
                            f"disclosure policy {policy_id} already carries"
                            f" revision {policy.revision} with different"
                            " rules; bump the revision to change the policy"
                            " (docs/DATA_MODEL.md §1.4)",
                        )
                    now = _now()
                    self._replace_policy(policy, now=now)
                else:
                    now = _now()
                    self._insert_policy(policy, now=now)
                return Ok(
                    DisclosurePolicy(
                        disclosure_policy_id=policy_id,
                        revision=policy.revision,
                        rules=policy.rules,
                        updated_at=now,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def upsert_goal_portfolio(
        self, portfolio: LearningGoalPortfolio
    ) -> Result[LearningGoalPortfolio]:
        """One durable goal-portfolio write (§5.1; P6-0).

        Versioned configuration, so the rule is the profile/policy rule: the
        same id with the same ``goal_version`` and the same content is an
        idempotent replay, a moved version replaces, and the same version
        with different content is refused (``CONFLICT``) — a portfolio is
        never silently rewritten (DOMAIN_MODEL §5.1 Rules: 不能静默修改长期
        目标). ``effective_from`` is the caller's and is never invented;
        ``updated_at`` is this store's clock.
        """

        portfolio_id = portfolio.goal_portfolio_id
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._portfolio_row(portfolio_id)
                if (
                    existing is not None
                    and existing.goal_version == portfolio.goal_version
                ):
                    if _same_portfolio(existing, portfolio):
                        return Ok(existing)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"goal portfolio {portfolio_id} already carries"
                        f" version {portfolio.goal_version} with different"
                        " content; bump goal_version to change the portfolio"
                        " (docs/DATA_MODEL.md §1.4)",
                    )
                now = _now()
                if existing is None:
                    self._insert_portfolio(portfolio, now=now)
                else:
                    self._replace_portfolio(portfolio, now=now)
                return Ok(
                    LearningGoalPortfolio(
                        goal_portfolio_id=portfolio_id,
                        goal_version=portfolio.goal_version,
                        goals=tuple(portfolio.goals),
                        modality_weights=dict(portfolio.modality_weights),
                        assessment_targets=tuple(portfolio.assessment_targets),
                        register_style_goals=tuple(
                            portfolio.register_style_goals
                        ),
                        effective_from=portfolio.effective_from,
                        updated_at=now,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def upsert_teaching_policy(
        self, policy: TeachingPolicyProfile
    ) -> Result[TeachingPolicyProfile]:
        """One durable teaching-policy write (§5.1; P6-0).

        Same version discipline as the portfolio. The eight unpinned columns
        are persisted and returned **verbatim** (``None`` = not configured):
        this module interprets none of them, so nothing here can give an
        unknown policy knob a meaning it was not written with.
        """

        policy_id = policy.teaching_policy_profile_id
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._teaching_policy_row(policy_id)
                if (
                    existing is not None
                    and existing.policy_version == policy.policy_version
                ):
                    if _same_teaching_policy(existing, policy):
                        return Ok(existing)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"teaching policy {policy_id} already carries version"
                        f" {policy.policy_version} with different content;"
                        " bump policy_version to change the policy"
                        " (docs/DATA_MODEL.md §1.4)",
                    )
                now = _now()
                if existing is None:
                    self._insert_teaching_policy(policy, now=now)
                else:
                    self._replace_teaching_policy(policy, now=now)
                return Ok(
                    TeachingPolicyProfile(
                        teaching_policy_profile_id=policy_id,
                        policy_version=policy.policy_version,
                        teaching_frequency=policy.teaching_frequency,
                        mode=policy.mode,
                        interruption_budget=policy.interruption_budget,
                        curriculum_initiative=policy.curriculum_initiative,
                        correction_strictness=policy.correction_strictness,
                        hint_policy=policy.hint_policy,
                        assessment_visibility=policy.assessment_visibility,
                        practice_density=policy.practice_density,
                        persona_freedom=policy.persona_freedom,
                        effective_from=policy.effective_from,
                        updated_at=now,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def set_session_focus(self, focus: SessionFocus) -> Result[SessionFocus]:
        """One durable session-focus write (§5.1; P6-0).

        Append-first, because §5.1 gives this object no version stamp: the
        same ``session_focus_id`` with the same content is an idempotent
        replay, and the same id with different content is refused
        (``CONFLICT``) rather than rewritten — a new focus is a new id (the
        module docstring carries the full reasoning). ``starts_at`` /
        ``expires_at`` are the caller's window, carried verbatim; the row
        has no store-stamped column at all, so nothing here reads a clock.
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._focus_row(focus.session_focus_id)
                if existing is not None:
                    if _same_focus(existing, focus):
                        return Ok(existing)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"session focus {focus.session_focus_id} already"
                        " exists with different content; mint a new"
                        " session_focus_id for a new focus (§5.1 pins no"
                        " version column to rewrite the row under —"
                        " docs/DATA_MODEL.md §1.3/§1.4)",
                    )
                self._insert_focus(focus)
                return Ok(
                    SessionFocus(
                        session_focus_id=focus.session_focus_id,
                        conversation_id=focus.conversation_id,
                        base_goal_portfolio_version=(
                            focus.base_goal_portfolio_version
                        ),
                        temporary_goal_weights=dict(
                            focus.temporary_goal_weights
                        ),
                        manual_focus_target=focus.manual_focus_target,
                        starts_at=focus.starts_at,
                        expires_at=focus.expires_at,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def record_planner_constraint(
        self, constraint: PlannerConstraint
    ) -> Result[PlannerConstraint]:
        """One durable user constraint (§9; P6-3).

        Append-first, because §9 gives this object no version stamp: the same
        ``constraint_id`` with the same content is an idempotent replay
        (returns the durable row, writes nothing), and the same id with
        different content is refused (``CONFLICT``) rather than rewritten — a
        different constraint is a different id.

        **``active`` is content here.** An inbound constraint whose ``active``
        differs from the durable row is refused exactly like any other
        difference: the flag moves through
        :meth:`set_planner_constraint_active` and nowhere else (R6; the
        module docstring carries the reason).

        Two refusals are pre-checked so no raw sqlite text can reach a
        ``DomainError`` message (the p6-1 F-2 rule):

        - ``created_from_turn_id`` naming a turn that is not a durable
          ``turn_record`` row is ``NOT_FOUND`` — the foreign key 0013 declares
          is the reason the row cannot exist, and the probe is what turns
          "sqlite refused to insert" into this domain's vocabulary;
        - a ``target_type`` outside §9's two words (RESOURCE / CAPABILITY) is
          ``VALIDATION_FAILED``. The migration's CHECK is the mechanism; this
          is the same rule said in the caller's vocabulary.

        **This face does not parse the window (L-2, stated because the two
        faces are deliberately asymmetrical).** ``starts_at`` / ``expires_at``
        are carried **verbatim**: §9 pins no timestamp format, so the write
        side stores whatever string it is handed — including an unusable one —
        exactly as the canonical column set allows (the same reading
        ``starts_at`` carries in the column note above). The ISO-8601 /
        UTC-offset rule is enforced **when the window is read**, by
        :meth:`active_constraints` and its target-scoped sibling, because that
        is where an instant has to be compared. The consequence is honest but
        sharp, so it is written here rather than discovered: a row written
        with an unreadable window makes those two *reads* refuse
        (``VALIDATION_FAILED``, naming the row and the field) until it is out
        of the question — and the **recovery path is the flag's own face**:
        :meth:`set_planner_constraint_active` with ``active=False`` disables
        the row, the reads stop having to compare its window, and they answer
        again. Validating the window *here* instead would be a rule §9 does not
        make (a format the canonical set never pins), so it is deliberately
        not done.
        """

        rejection = self._constraint_rejection(constraint)
        if rejection is not None:
            return rejection
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._constraint_row(constraint.constraint_id)
                if existing is not None:
                    if _same_constraint(existing, constraint):
                        return Ok(existing)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"planner constraint {constraint.constraint_id} already"
                        " exists with different content; mint a new"
                        " constraint_id for a new constraint (§9 pins no"
                        " version column to rewrite the row under —"
                        " docs/DATA_MODEL.md §1.3/§1.4), and move `active`"
                        " only through set_planner_constraint_active",
                    )
                self._insert_constraint(constraint)
                return Ok(
                    PlannerConstraint(
                        constraint_id=constraint.constraint_id,
                        target_type=constraint.target_type,
                        target_id=constraint.target_id,
                        constraint_type=constraint.constraint_type,
                        scope=constraint.scope,
                        starts_at=constraint.starts_at,
                        expires_at=constraint.expires_at,
                        created_from_turn_id=constraint.created_from_turn_id,
                        active=constraint.active,
                    )
                )
        except sqlite3.IntegrityError:
            return _err(
                DomainErrorCode.CONFLICT,
                f"planner constraint {constraint.constraint_id} was refused by"
                " a durable rule (0013's CHECK vocabularies, or the id taken"
                " between the replay check and the insert); nothing was"
                " written",
            )

    def set_planner_constraint_active(
        self, constraint_id: str, active: bool
    ) -> Result[PlannerConstraint]:
        """Move the one movable column of a constraint (R6; P6-3).

        ``active`` is the exception §9's missing version column forces, and it
        is the only thing this face may change: every other column of the row
        is written back byte for byte, so a caller cannot smuggle a content
        edit through the flag's transfer. The BF-03 reason is in the module
        docstring: re-enabling (or clearing a suppression) is the User
        Constraint layer's act — "Gate 不偷偷修改用户约束" — and without this
        face ``UNTIL_USER_REENABLES`` could never end.

        A ``constraint_id`` with no durable row is ``NOT_FOUND``; transferring
        the value the row already carries is an idempotent replay (returns the
        durable row, writes nothing).
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._constraint_row(constraint_id)
                if existing is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"planner constraint {constraint_id} has no durable"
                        " row; a constraint's flag can only be transferred on"
                        " a constraint that exists",
                    )
                if existing.active == active:
                    return Ok(existing)
                self._conn.execute(
                    "UPDATE planner_constraint SET active = ?"
                    " WHERE constraint_id = ?",
                    (1 if active else 0, constraint_id),
                )
                return Ok(
                    PlannerConstraint(
                        constraint_id=existing.constraint_id,
                        target_type=existing.target_type,
                        target_id=existing.target_id,
                        constraint_type=existing.constraint_type,
                        scope=existing.scope,
                        starts_at=existing.starts_at,
                        expires_at=existing.expires_at,
                        created_from_turn_id=existing.created_from_turn_id,
                        active=active,
                    )
                )
        except sqlite3.IntegrityError:
            return _err(
                DomainErrorCode.CONFLICT,
                f"planner constraint {constraint_id} was refused by 0013's"
                " active CHECK (the column is 0 or 1 and nothing else);"
                " nothing was written",
            )

    def _constraint_rejection(
        self, constraint: PlannerConstraint
    ) -> Err[PlannerConstraint] | None:
        """The two pre-checks the content write face owes (§9; P6-3).

        ``None`` = the row may be written. Both refusals name the field and
        the reason in this domain's words; neither carries sqlite's text.
        """

        turn_id = constraint.created_from_turn_id
        if turn_id is not None:
            row = self._conn.execute(
                "SELECT 1 FROM turn_record WHERE turn_id = ?", (str(turn_id),)
            ).fetchone()
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"turn {turn_id} is not a durable turn record; a constraint"
                    " created from a turn must name one that exists"
                    " (docs/DATA_MODEL.md §9 created_from_turn_id?)",
                )
        target_type = constraint.target_type
        if target_type is not None and target_type not in _TARGET_TYPES:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"target_type {target_type!r} is not one of 0013's two words"
                f" ({', '.join(_TARGET_TYPES)}); a target-type'd constraint"
                " names one of them (docs/DATA_MODEL.md §9 target_type?)",
            )
        return None

    def _insert_constraint(self, constraint: PlannerConstraint) -> None:
        # No clock column on this row: §9's PlannerConstraint carries only the
        # caller's window (starts_at / expires_at) and the caller's flag, so
        # there is nothing for this store to stamp.
        self._conn.execute(
            "INSERT INTO planner_constraint ("
            " constraint_id, target_type, target_id, constraint_type, scope,"
            " starts_at, expires_at, created_from_turn_id, active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                constraint.constraint_id,
                constraint.target_type,
                (
                    None
                    if constraint.target_id is None
                    else str(constraint.target_id)
                ),
                constraint.constraint_type.value,
                constraint.scope.value,
                constraint.starts_at,
                constraint.expires_at,
                (
                    None
                    if constraint.created_from_turn_id is None
                    else str(constraint.created_from_turn_id)
                ),
                1 if constraint.active else 0,
            ),
        )

    def _insert_profile(self, profile: UserProfile, *, now: str) -> None:
        self._conn.execute(
            "INSERT INTO user_profile ("
            " user_profile_id, revision, profile_facts, preferences, settings,"
            " updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(profile.user_profile_id),
                profile.revision,
                _facts_document(profile.profile_facts),
                _strings_document(profile.preferences),
                _strings_document(profile.settings),
                now,
            ),
        )

    def _replace_profile(self, profile: UserProfile, *, now: str) -> None:
        self._conn.execute(
            "UPDATE user_profile SET revision = ?, profile_facts = ?,"
            " preferences = ?, settings = ?, updated_at = ?"
            " WHERE user_profile_id = ?",
            (
                profile.revision,
                _facts_document(profile.profile_facts),
                _strings_document(profile.preferences),
                _strings_document(profile.settings),
                now,
                str(profile.user_profile_id),
            ),
        )

    def _insert_policy(self, policy: DisclosurePolicy, *, now: str) -> None:
        self._conn.execute(
            "INSERT INTO disclosure_policy ("
            " disclosure_policy_id, revision, rules, updated_at"
            ") VALUES (?, ?, ?, ?)",
            (
                policy.disclosure_policy_id,
                policy.revision,
                _rules_document(policy.rules),
                now,
            ),
        )

    def _replace_policy(self, policy: DisclosurePolicy, *, now: str) -> None:
        self._conn.execute(
            "UPDATE disclosure_policy SET revision = ?, rules = ?,"
            " updated_at = ? WHERE disclosure_policy_id = ?",
            (
                policy.revision,
                _rules_document(policy.rules),
                now,
                policy.disclosure_policy_id,
            ),
        )

    def _insert_portfolio(
        self, portfolio: LearningGoalPortfolio, *, now: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO goal_portfolio ("
            " goal_portfolio_id, goal_version, goals, modality_weights,"
            " assessment_targets, register_style_goals, effective_from,"
            " updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(portfolio.goal_portfolio_id),
                portfolio.goal_version,
                _goals_document(portfolio.goals),
                _weights_document(portfolio.modality_weights),
                _strings_document(portfolio.assessment_targets),
                _strings_document(portfolio.register_style_goals),
                portfolio.effective_from,
                now,
            ),
        )

    def _replace_portfolio(
        self, portfolio: LearningGoalPortfolio, *, now: str
    ) -> None:
        self._conn.execute(
            "UPDATE goal_portfolio SET goal_version = ?, goals = ?,"
            " modality_weights = ?, assessment_targets = ?,"
            " register_style_goals = ?, effective_from = ?, updated_at = ?"
            " WHERE goal_portfolio_id = ?",
            (
                portfolio.goal_version,
                _goals_document(portfolio.goals),
                _weights_document(portfolio.modality_weights),
                _strings_document(portfolio.assessment_targets),
                _strings_document(portfolio.register_style_goals),
                portfolio.effective_from,
                now,
                str(portfolio.goal_portfolio_id),
            ),
        )

    def _insert_teaching_policy(
        self, policy: TeachingPolicyProfile, *, now: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO teaching_policy ("
            " teaching_policy_profile_id, policy_version, mode,"
            " teaching_frequency, interruption_budget, curriculum_initiative,"
            " correction_strictness, hint_policy, assessment_visibility,"
            " practice_density, persona_freedom, effective_from, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(policy.teaching_policy_profile_id),
                policy.policy_version,
                policy.mode,
                policy.teaching_frequency.value,
                policy.interruption_budget,
                policy.curriculum_initiative,
                policy.correction_strictness,
                policy.hint_policy,
                policy.assessment_visibility,
                policy.practice_density,
                policy.persona_freedom,
                policy.effective_from,
                now,
            ),
        )

    def _replace_teaching_policy(
        self, policy: TeachingPolicyProfile, *, now: str
    ) -> None:
        self._conn.execute(
            "UPDATE teaching_policy SET policy_version = ?, mode = ?,"
            " teaching_frequency = ?, interruption_budget = ?,"
            " curriculum_initiative = ?, correction_strictness = ?,"
            " hint_policy = ?, assessment_visibility = ?,"
            " practice_density = ?, persona_freedom = ?, effective_from = ?,"
            " updated_at = ?"
            " WHERE teaching_policy_profile_id = ?",
            (
                policy.policy_version,
                policy.mode,
                policy.teaching_frequency.value,
                policy.interruption_budget,
                policy.curriculum_initiative,
                policy.correction_strictness,
                policy.hint_policy,
                policy.assessment_visibility,
                policy.practice_density,
                policy.persona_freedom,
                policy.effective_from,
                now,
                str(policy.teaching_policy_profile_id),
            ),
        )

    def _insert_focus(self, focus: SessionFocus) -> None:
        # No clock column on this row: §5.1's SessionFocus carries only the
        # caller's window (starts_at / expires_at), so there is nothing for
        # this store to stamp.
        self._conn.execute(
            "INSERT INTO session_focus ("
            " session_focus_id, conversation_id,"
            " base_goal_portfolio_version, temporary_goal_weights,"
            " manual_focus_target, starts_at, expires_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                focus.session_focus_id,
                str(focus.conversation_id),
                focus.base_goal_portfolio_version,
                _weights_document(focus.temporary_goal_weights),
                (
                    None
                    if focus.manual_focus_target is None
                    else str(focus.manual_focus_target)
                ),
                focus.starts_at,
                focus.expires_at,
            ),
        )

    # -- reads -------------------------------------------------------------

    def get_user_profile(self, user_id: UserId) -> Result[UserProfile | None]:
        """The user's profile row (``None`` = never written)."""

        durable = self._profile_row(user_id)
        if durable is None:
            return Ok(None)
        return Ok(
            UserProfile(
                user_profile_id=user_id,
                revision=durable.revision,
                profile_facts=durable.facts,
                preferences=durable.preferences,
                settings=durable.settings,
                updated_at=durable.updated_at,
            )
        )

    def get_disclosure_policy(
        self, user_id: UserId
    ) -> Result[DisclosurePolicy | None]:
        """The user's disclosure policy (the Local V1 keying convention:
        ``disclosure_policy_id`` is the user's own id)."""

        return Ok(self._policy_row(str(user_id)))

    def get_goal_portfolio(
        self, user_id: UserId
    ) -> Result[LearningGoalPortfolio | None]:
        """The user's goal portfolio (the same Local V1 keying convention:
        ``goal_portfolio_id`` is the user's own id; ``None`` = never
        written)."""

        return Ok(self._portfolio_row(user_id))

    def get_teaching_policy(
        self, user_id: UserId
    ) -> Result[TeachingPolicyProfile | None]:
        """The user's teaching policy (``None`` = never written)."""

        return Ok(self._teaching_policy_row(str(user_id)))

    def get_session_focus(
        self, session_focus_id: str
    ) -> Result[SessionFocus | None]:
        """One focus row by its own identity (``None`` = never written).

        §5.1's SessionFocus has no user leg (it names a conversation), so it
        is read by ``session_focus_id`` — the object's own key — and not by
        the user keying convention the four user-owned rows share.
        """

        return Ok(self._focus_row(session_focus_id))

    def get_session_focus_for_conversation(
        self, conversation_id: ConversationId
    ) -> Result[SessionFocus | None]:
        """The conversation's current focus (``None`` = none written).

        **F-7 (P6-1): the per-conversation read face §5.1's object had no
        route to.** ``get_session_focus`` answers by the focus's own id, which
        is what a caller that already knows the id wants; a consumer holding a
        *conversation* (the Planner/Persona view a later cut wires) has no id
        to ask with, and §5.1 gives the object no unique index to lean on —
        several focuses for one conversation over time are the append-first
        history migration 0011 deliberately keeps.

        The reading this slice declares, and why:

        - the row with the **largest ``starts_at``** is the conversation's
          current focus — that is the only ordering §5.1 supplies;
        - a tie is broken by the **largest ``session_focus_id``**
          (lexicographic), so the answer never depends on row insertion order
          or on a query plan;
        - the comparison is done here in Python rather than by ``ORDER BY`` so
          it is byte-wise lexicographic by construction, independent of any
          database collation (there is one comparison rule, and this is it);
        - **the ordering is byte order (code-point order), not instant
          order** — a derived judgement, because §5.1 pins no timestamp
          format for ``starts_at`` and this slice mints none. Two offsets
          therefore compare as text: ``2026-09-22T12:00:00+08:00`` sorts
          *after* ``2026-09-22T05:00:00+00:00`` even though the first instant
          (04:00Z) is earlier than the second (05:00Z). That is the reading
          this store declares, and a consumer that needs instant order parses
          the timestamps itself; changing *this* to instant order is a
          decision to take explicitly (a pinned test asserts the byte-order
          winner), not a silent repair;
        - **``expires_at`` is not consulted**: whether a window is still
          *valid* is the consumer's question, answered by the consumer's
          clock. This read introduces no clock judgement at all, which also
          makes two calls answer identically.
        """

        rows = self._conn.execute(
            "SELECT session_focus_id, conversation_id,"
            " base_goal_portfolio_version, temporary_goal_weights,"
            " manual_focus_target, starts_at, expires_at"
            " FROM session_focus WHERE conversation_id = ?",
            (str(conversation_id),),
        ).fetchall()
        if not rows:
            return Ok(None)
        return Ok(
            max(
                (_focus_from_row(tuple(row)) for row in rows),
                key=lambda focus: (focus.starts_at, focus.session_focus_id),
            )
        )

    # -- the constraint reads (Phase 6 P6-3) --------------------------------

    def get_planner_constraint(
        self, constraint_id: str
    ) -> Result[PlannerConstraint | None]:
        """One constraint row by its own identity (``None`` = never written).

        No window judgement and no clock: this is the raw row, exactly as the
        content write face left it (``active`` included). A caller that wants
        "in force at *this* instant" asks one of the two active reads.
        """

        return Ok(self._constraint_row(constraint_id))

    def active_constraints(
        self, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """Every constraint in force at ``as_of``, ordered by ``constraint_id``.

        The reading (R7), and each leg of it is deliberate:

        - ``active`` must be true — a row the user turned off is not in force,
          whatever its window says;
        - ``starts_at <= as_of`` — the window opens at its start instant
          **inclusive** (the scheduler's boundary rule: ``as_of ==
          starts_at`` is the instant the constraint takes effect);
        - ``expires_at`` is NULL (no end declared — an open-ended constraint)
          **or** ``as_of <= expires_at`` (the window closes at its end
          instant, inclusive);
        - the comparison is **instant** order, not byte order: two spellings
          of one instant compare equal, and two offsets of the same moment do
          not decide the answer by their text. This is the deliberate opposite
          of p6-1's byte-order rule for an immutable fact's replay, and the
          same split :mod:`elc.scheduler.spacing` declares for its window;
        - the order is ``constraint_id`` ascending, byte order (code-point
          order) rather than ``ORDER BY``, so it is collation-independent by
          construction (p6-1's ``get_session_focus_for_conversation``
          precedent for the same choice).

        ``as_of`` is the caller's instant. An empty, unparseable or naive one
        is ``VALIDATION_FAILED`` (never assumed to be UTC), and so is an
        unreadable ``starts_at`` / ``expires_at`` on a row the read would have
        to compare: the refusal names the row and the field rather than
        silently dropping the constraint or triaging it as inactive. A row
        already filtered out as inactive is never parsed, so a disabled row's
        timestamps cannot break a read.
        """

        parsed = _parse_instant(as_of, field="as_of")
        if isinstance(parsed, Err):
            return parsed
        return self._active_constraints(
            lambda constraint: True, parsed.value
        )

    def active_constraints_for_target(
        self, target_type: str, target_id: TargetId, as_of: str
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """The constraints in force for one target at ``as_of`` (R7; P6-3).

        The same reading as :meth:`active_constraints` with one leg added: a
        constraint is in the answer when it is in force **and** it speaks
        about this target — either because its target leg is NULL (it is not
        target-limited and therefore applies to every target) or because both
        of its legs match the arguments verbatim (:func:`_matches_target`
        carries the rule, including what a half-declared target leg does).
        Ordering, boundaries, instant comparison and the refusal vocabulary
        are exactly as in :meth:`active_constraints`.
        """

        parsed = _parse_instant(as_of, field="as_of")
        if isinstance(parsed, Err):
            return parsed
        return self._active_constraints(
            lambda constraint: _matches_target(
                constraint, target_type, target_id
            ),
            parsed.value,
        )

    def _active_constraints(
        self,
        matches: Callable[[PlannerConstraint], bool],
        as_of: datetime,
    ) -> Result[tuple[PlannerConstraint, ...]]:
        """The one implementation of both active reads.

        The SQL narrows to ``active = 1`` (the one leg a statement can decide
        without a timestamp format), and every temporal leg is decided here as
        instants — a row is selected exactly when it is active, its window
        contains ``as_of``, and ``matches`` accepts it.
        """

        rows = self._conn.execute(
            "SELECT constraint_id, target_type, target_id, constraint_type,"
            " scope, starts_at, expires_at, created_from_turn_id, active"
            " FROM planner_constraint WHERE active = 1"
        ).fetchall()
        in_force: list[PlannerConstraint] = []
        for row in rows:
            constraint = _constraint_from_row(tuple(row))
            if not matches(constraint):
                continue
            opens = _parse_instant(
                constraint.starts_at,
                field=(
                    f"starts_at of planner constraint"
                    f" {constraint.constraint_id}"
                ),
            )
            if isinstance(opens, Err):
                return opens
            if as_of < opens.value:
                continue
            if constraint.expires_at is not None:
                closes = _parse_instant(
                    constraint.expires_at,
                    field=(
                        f"expires_at of planner constraint"
                        f" {constraint.constraint_id}"
                    ),
                )
                if isinstance(closes, Err):
                    return closes
                if as_of > closes.value:
                    continue
            in_force.append(constraint)
        return Ok(tuple(sorted(in_force, key=lambda c: c.constraint_id)))

    # -- internals ---------------------------------------------------------

    def _profile_row(self, user_id: UserId) -> _StoredProfile | None:
        """One durable profile row, decoded (``None`` = never written)."""
        row = self._conn.execute(
            "SELECT revision, profile_facts, preferences, settings, updated_at"
            " FROM user_profile WHERE user_profile_id = ?",
            (str(user_id),),
        ).fetchone()
        if row is None:
            return None
        return _StoredProfile(
            revision=str(row[0]),
            facts=_facts_from_document(str(row[1])),
            preferences=_strings_from_document(str(row[2])),
            settings=_strings_from_document(str(row[3])),
            updated_at=str(row[4]),
        )

    def _policy_row(self, policy_id: str) -> DisclosurePolicy | None:
        row = self._conn.execute(
            "SELECT disclosure_policy_id, revision, rules, updated_at"
            " FROM disclosure_policy WHERE disclosure_policy_id = ?",
            (policy_id,),
        ).fetchone()
        if row is None:
            return None
        return DisclosurePolicy(
            disclosure_policy_id=str(row[0]),
            revision=str(row[1]),
            rules=_rules_from_document(str(row[2])),
            updated_at=str(row[3]),
        )

    def _portfolio_row(self, user_id: UserId) -> LearningGoalPortfolio | None:
        row = self._conn.execute(
            "SELECT goal_portfolio_id, goal_version, goals, modality_weights,"
            " assessment_targets, register_style_goals, effective_from,"
            " updated_at FROM goal_portfolio WHERE goal_portfolio_id = ?",
            (str(user_id),),
        ).fetchone()
        if row is None:
            return None
        return LearningGoalPortfolio(
            goal_portfolio_id=UserId(str(row[0])),
            goal_version=GoalVersion(str(row[1])),
            goals=_goals_from_document(str(row[2])),
            modality_weights=_weights_from_document(str(row[3])),
            assessment_targets=_strings_from_document(str(row[4])),
            register_style_goals=_strings_from_document(str(row[5])),
            effective_from=str(row[6]),
            updated_at=str(row[7]),
        )

    def _teaching_policy_row(
        self, policy_id: str
    ) -> TeachingPolicyProfile | None:
        row = self._conn.execute(
            "SELECT teaching_policy_profile_id, policy_version, mode,"
            " teaching_frequency, interruption_budget, curriculum_initiative,"
            " correction_strictness, hint_policy, assessment_visibility,"
            " practice_density, persona_freedom, effective_from, updated_at"
            " FROM teaching_policy WHERE teaching_policy_profile_id = ?",
            (policy_id,),
        ).fetchone()
        if row is None:
            return None
        return TeachingPolicyProfile(
            teaching_policy_profile_id=UserId(str(row[0])),
            policy_version=PolicyVersion(str(row[1])),
            teaching_frequency=TeachingFrequency(str(row[3])),
            mode=None if row[2] is None else str(row[2]),
            interruption_budget=None if row[4] is None else str(row[4]),
            curriculum_initiative=None if row[5] is None else str(row[5]),
            correction_strictness=None if row[6] is None else str(row[6]),
            hint_policy=None if row[7] is None else str(row[7]),
            assessment_visibility=None if row[8] is None else str(row[8]),
            practice_density=None if row[9] is None else str(row[9]),
            persona_freedom=None if row[10] is None else str(row[10]),
            effective_from=str(row[11]),
            updated_at=str(row[12]),
        )

    def _focus_row(self, session_focus_id: str) -> SessionFocus | None:
        row = self._conn.execute(
            "SELECT session_focus_id, conversation_id,"
            " base_goal_portfolio_version, temporary_goal_weights,"
            " manual_focus_target, starts_at, expires_at"
            " FROM session_focus WHERE session_focus_id = ?",
            (session_focus_id,),
        ).fetchone()
        if row is None:
            return None
        return _focus_from_row(tuple(row))

    def _constraint_row(self, constraint_id: str) -> PlannerConstraint | None:
        """One durable constraint row, decoded (``None`` = never written)."""

        row = self._conn.execute(
            "SELECT constraint_id, target_type, target_id, constraint_type,"
            " scope, starts_at, expires_at, created_from_turn_id, active"
            " FROM planner_constraint WHERE constraint_id = ?",
            (constraint_id,),
        ).fetchone()
        if row is None:
            return None
        return _constraint_from_row(tuple(row))


@dataclass(frozen=True)
class _StoredProfile:
    """One durable profile row, decoded (the comparison basis of the
    idempotent-replay rule; ``updated_at`` is carried for the read face)."""

    revision: str
    facts: tuple[ProfileFact, ...]
    preferences: tuple[str, ...]
    settings: tuple[str, ...]
    updated_at: str


def _same_profile(durable: _StoredProfile, incoming: UserProfile) -> bool:
    """Whether the row already holds exactly this content.

    ``updated_at`` is deliberately not compared: it is the store's clock,
    and two writes of unchanged content differ only there.
    """

    return (
        durable.facts == incoming.profile_facts
        and durable.preferences == incoming.preferences
        and durable.settings == incoming.settings
    )


def _same_portfolio(
    durable: LearningGoalPortfolio, incoming: LearningGoalPortfolio
) -> bool:
    """Whether the durable row already holds exactly this content.

    Compares content only — never ``updated_at`` (the store's clock) and
    never the version (the caller's, compared by the caller of this helper).
    The weight maps compare through their normal form, so key order is not
    content; a differing pair is. The list columns compare as sequences, so
    an unsorted-but-equal sequence is a different content (the canonical
    order of a list is the caller's statement).
    """

    return (
        tuple(durable.goals) == tuple(incoming.goals)
        and _weights_document(durable.modality_weights)
        == _weights_document(incoming.modality_weights)
        and tuple(durable.assessment_targets)
        == tuple(incoming.assessment_targets)
        and tuple(durable.register_style_goals)
        == tuple(incoming.register_style_goals)
        and durable.effective_from == incoming.effective_from
    )


def _same_teaching_policy(
    durable: TeachingPolicyProfile, incoming: TeachingPolicyProfile
) -> bool:
    """Whether the durable row already holds exactly this content.

    Every one of the eight unpinned columns is compared verbatim (``None``
    is a value, not a wildcard): this slice interprets none of them, so it
    cannot decide that two different raw values mean the same thing.
    """

    return (
        durable.teaching_frequency == incoming.teaching_frequency
        and durable.mode == incoming.mode
        and durable.interruption_budget == incoming.interruption_budget
        and durable.curriculum_initiative == incoming.curriculum_initiative
        and durable.correction_strictness == incoming.correction_strictness
        and durable.hint_policy == incoming.hint_policy
        and durable.assessment_visibility == incoming.assessment_visibility
        and durable.practice_density == incoming.practice_density
        and durable.persona_freedom == incoming.persona_freedom
        and durable.effective_from == incoming.effective_from
    )


def _focus_from_row(row: tuple[object, ...]) -> SessionFocus:
    """One ``session_focus`` row (the 0011 column order) decoded.

    One decode point, two readers: ``get_session_focus`` (by the focus's own
    id) and ``get_session_focus_for_conversation`` (by conversation, F-7).
    """

    return SessionFocus(
        session_focus_id=str(row[0]),
        conversation_id=ConversationId(str(row[1])),
        base_goal_portfolio_version=GoalVersion(str(row[2])),
        temporary_goal_weights=_weights_from_document(str(row[3])),
        manual_focus_target=(
            None if row[4] is None else TargetId(str(row[4]))
        ),
        starts_at=str(row[5]),
        expires_at=None if row[6] is None else str(row[6]),
    )


def _same_focus(durable: SessionFocus, incoming: SessionFocus) -> bool:
    """Whether the durable row already holds exactly this content.

    ``session_focus_id`` is the identity (the row was read by it) and the
    conversation is compared too: the same content under a different
    conversation is a different focus.
    """

    return (
        str(durable.conversation_id) == str(incoming.conversation_id)
        and durable.base_goal_portfolio_version
        == incoming.base_goal_portfolio_version
        and _weights_document(durable.temporary_goal_weights)
        == _weights_document(incoming.temporary_goal_weights)
        and durable.manual_focus_target == incoming.manual_focus_target
        and durable.starts_at == incoming.starts_at
        and durable.expires_at == incoming.expires_at
    )
