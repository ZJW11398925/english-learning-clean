"""SQLite durable store for User Configuration / Profile (Phase 4 P4-3,
extended by Phase 6 P6-0).

The bounded context owns UserProfile / DisclosurePolicy / LearningGoalPortfolio
/ TeachingPolicyProfile / SessionFocus truth (docs/DOMAIN_MODEL.md §5.1), so
its durable executor lives in the domain package — the conversation /
learning / teaching / relationship store precedent. The authority face is
elc.user_config.controller; the pure disclosure decision is
elc.user_config.disclosure; every byte that reaches the disk is here, in the
five tables migrations 0010 and 0011 create.

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
from typing import Mapping, TypeVar

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
    UserId,
)
from elc.relationship.types import MemorySensitivityClass
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    LearningGoal,
    LearningGoalPortfolio,
    ProfileFact,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
    UserProfile,
)

__all__ = ["StaleStoreEpochError", "SqliteUserConfigStore"]

T = TypeVar("T")


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
