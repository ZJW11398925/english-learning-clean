"""SQLite durable store for User Configuration / Profile (Phase 4 P4-3).

The bounded context owns UserProfile / DisclosurePolicy truth
(docs/DOMAIN_MODEL.md §5.1), so its durable executor lives in the domain
package — the conversation / learning / teaching / relationship store
precedent. The authority face is elc.user_config.controller; the pure
disclosure decision is elc.user_config.disclosure; every byte that reaches
the disk is here, in the two tables migration 0010 creates.

One write unit is one short transaction (docs/DATA_MODEL.md §2 short atomic
commits):

- **idempotent replay** — the same id with the same revision *and* the same
  content returns the id and writes nothing (the crash-retry face);
- **a moved revision** — a different ``revision`` replaces the content and
  stamps a fresh ``updated_at`` from this store's own clock;
- **a stamped revision that would be rewritten** — the same ``revision``
  with *different* content is a ``CONFLICT``: a revision is a version stamp,
  not decoration (DATA_MODEL §1.4 "version every derived model"), and a
  silent content change under an unchanged stamp is exactly the drift the
  stamp exists to prevent. §5.1 pins no ordering for these stamps, so
  "前进" is spelled "differs" here — the store compares revisions for
  equality, never for order.

Fencing: every write checks the store epoch against the newest durable epoch
before anything is written (the teaching / relationship store precedent; a
stale store is a programming error and raises).

Keying convention (Local V1, declared rather than assumed): §5.1 pins
``user_profile_id`` and ``disclosure_policy_id`` but **no owner column**
linking the two objects to each other or to a user, so this slice keys both
by the user's own id — ``UserProfile.user_profile_id`` is typed ``UserId``,
and ``get_disclosure_policy(user_id)`` reads the row whose
``disclosure_policy_id`` is that user's id. A second table or an added
column would exceed the canonical column set (§2 non-goals notwithstanding,
the *set* is canonical), so the linking rule lives here, in one place, and
the controller names it too.

The BF-05 sensitive-memory gate is **not** here: this module persists what it
is handed, and refuses only the revision conflicts above. The consent gate
(§18.1) is the controller's, one layer up — the P4-1 split (validate / gate
in the domain face, rows here) kept identical.

All SQL is a fixed literal with bound parameters — no identifier assembly,
no runtime value in any statement text. The list columns follow migration
0009/0004's storage note: a canonical list stores as JSON text with sorted
keys, never as a second table.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
    UserId,
)
from elc.relationship.types import MemorySensitivityClass
from elc.user_config.types import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    ProfileFact,
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


class SqliteUserConfigStore:
    """Durable ``user_profile`` / ``disclosure_policy`` rows."""

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
