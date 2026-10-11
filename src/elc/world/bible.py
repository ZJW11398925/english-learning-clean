"""The World Bible (V3-2, TASK-OPI-bab4da9f…29) —
:class:`SqliteBibleStore`, the SQL face of migration 0030's
``world_bible_revision`` table: the instance-level world's setting,
rules and history as versioned, append-only rows.

The Bible is the **sole authority** for what a world is like (DOMAIN
§20.2's authority table; the design supplement §五): one world, one
current revision, every past revision kept and citable. The
template/package relationship is one-way (DOMAIN §20.3-6, N-INV-006):
a template seeds the world's first revision at creation time
(:meth:`SqliteBibleStore.seed_bible`, called from
``elc.world.package.ensure_builtin_worlds`` so the Bible is born with
the world), and a template's later updates **never** rewrite an
existing world — a replayed seed is a zero-write no-op that answers
what is already stored, and a real change is an explicit
:meth:`SqliteBibleStore.revise_bible` decision, never a silent
template push.

Discipline (the house store law, :mod:`elc.world.store`'s and
:mod:`elc.world.narrative.store`'s posture):

- **Value semantics** — every refusal is a ``Result`` ``Err``, never an
  exception: ``CONFLICT`` = a stale ``state_version`` (or, through the
  database's own surface, a uniqueness clash); ``NOT_FOUND`` = a
  referenced identity (the world) does not exist, or the row to revise
  is gone (through the database's own surface, a FOREIGN KEY refusal
  is the same answer); ``DEPENDENCY_UNAVAILABLE`` = the database itself
  failed outside the vocabulary above (a locked or broken database is
  never re-attributed as a missing identity; the raw sqlite error
  rides the message). Messages are human sentences naming the row and
  the reason.
- **state_version CAS** — creation mints ``state_version = 1``; the
  revision move takes the caller's ``expected_state_version`` and
  updates under ``WHERE ... state_version = ?``: a rowcount of zero
  means either the row is gone (``NOT_FOUND``) or another writer moved
  it first (``CONFLICT`` — re-read and retry is the caller's move).
  Every successful write bumps the counter it touches.
- **Append-only versioning** — a revision never rewrites; it
  supersedes. :meth:`SqliteBibleStore.revise_bible` flips the current
  row to ``SUPERSEDED`` and lands the new ``CURRENT`` row in **one
  short transaction** (supersede first, insert second — the order the
  partial UNIQUE index demands); rows are never deleted (DATA
  §26.2.1's 「不减删」) and every past revision stays citable through
  :meth:`SqliteBibleStore.get_bible`.
- **Full-content revisions** — a revision carries all fourteen content
  fields explicitly; an omitted field is an honest *undeclared*
  (stored as the empty string), never an inheritance from the previous
  revision. The caller says what the world is like; the store does not
  guess the rest.
- **No hidden clock** — every row's ``created_at`` / ``updated_at`` is
  stamped with the caller's ``now`` (both write faces take it as a
  parameter); the store consults no clock of its own.
- **One short transaction per write** — ``BEGIN IMMEDIATE`` …
  ``COMMIT``/``ROLLBACK`` with the began-flag posture (a failed BEGIN
  owns nothing; a failing ROLLBACK of our own must not break the
  Result contract).

**One authority, zero legacy touch**: every SQL statement in this
module names ``world_bible_revision`` alone (its FK names ``world``)
and never names any legacy lore table — the authority direction runs
World Bible → projection/adapter → legacy view, never the reverse (the
design supplement §五), and the projection/adapter is a later cut's
work; this module builds none and reads none.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = [
    "BIBLE_FIELDS",
    "BibleRevision",
    "BibleRevisionStatus",
    "SqliteBibleStore",
]

#: The fourteen content fields of one Bible revision, in the canonical
#: order (DATA §26.2.1's semantic fields, the migration's column order
#: after ``status``). The single vocabulary source: the record, the
#: store's SQL and the tests all spell the same list, and the seed
#: face writes the empty string into every field but ``premise`` —
#: the honest "not yet declared" — so a caller can tell a field the
#: world's template never spoke from one it did.
BIBLE_FIELDS: tuple[str, ...] = (
    "premise",
    "genre",
    "tone",
    "calendar",
    "physics",
    "magic_rules",
    "geography",
    "society",
    "politics",
    "technology",
    "religion",
    "history",
    "hard_rules",
    "narrative_preferences",
)


class BibleRevisionStatus(StrEnum):
    """The Bible revision row's two-word lifecycle (DATA §26.2.1's
    vocabulary, word for word).

    ``CURRENT`` — the world's live Bible (at most one per world, the
    partial UNIQUE index's own law); ``SUPERSEDED`` — a past revision,
    kept forever and citable by number (append-only versioning: rows
    are never deleted, never rewritten).
    """

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class BibleRevision:
    """One Bible revision row — the world's setting as it stood at
    ``revision`` (DATA §26.2.1's entity contract).

    ``parent_revision`` is ``None`` for the seed revision (the
    template's own word — the source the world was born from) and the
    previous revision's number for every revision after it. The
    fourteen content fields ride as they were written: a field the
    writer did not declare is the empty string, an honest
    undeclared — never inherited, never guessed.
    """

    bible_revision_id: str
    world_id: str
    revision: int
    parent_revision: int | None
    status: BibleRevisionStatus
    premise: str
    genre: str
    tone: str
    calendar: str
    physics: str
    magic_rules: str
    geography: str
    society: str
    politics: str
    technology: str
    religion: str
    history: str
    hard_rules: str
    narrative_preferences: str
    created_at: str
    updated_at: str
    state_version: int


class SqliteBibleStore:
    """Migration 0030's ``world_bible_revision`` write and read face.

    ``fence`` is the house constructor shape (every app.db store takes
    the shared epoch fence); migration 0030 carries no ``write_epoch``
    column, so the fence is held unused — the Bible rows are
    creator-stamped, not epoch-guarded (the 0023/0029 posture).
    """

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- write faces -----------------------------------------------------------

    def seed_bible(
        self,
        bible_revision_id: str,
        world_id: str,
        premise: str,
        now: str,
    ) -> Result[BibleRevision]:
        """Seed the world's first Bible revision — the template's
        creation-time word (N-INV-006's machine half).

        **Idempotent and never rewriting**: if the world already holds
        a ``CURRENT`` revision the stored row is answered unchanged and
        *nothing is written* — the caller's ``premise`` is not compared
        and not applied, so a template's later update replayed through
        this face is silently ignored (a template does not own an
        existing world's rewrite; making it so is an explicit
        :meth:`revise_bible` decision, a later cut's business). The
        seed mints revision 1 with ``parent_revision = NULL`` (the
        source the world was born from), ``CURRENT``, the caller's
        ``premise`` and the empty string in the other thirteen content
        fields (honest undeclared — the template spoke only the
        premise), ``created_at`` / ``updated_at`` the caller's ``now``
        and ``state_version = 1``. A dangling ``world_id`` is refused
        by the table's own FK and surfaces as ``NOT_FOUND``.
        """

        existing = self.current_bible(world_id)
        if existing is not None:
            return Ok(existing)
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_bible_revision ("
                " bible_revision_id, world_id, revision, parent_revision,"
                " status, premise, genre, tone, calendar, physics,"
                " magic_rules, geography, society, politics, technology,"
                " religion, history, hard_rules, narrative_preferences,"
                " created_at, updated_at, state_version"
                ") VALUES (?, ?, 1, NULL, 'CURRENT', ?,"
                " '', '', '', '', '', '', '', '', '', '', '', '', '',"
                " ?, ?, 1)",
                (bible_revision_id, world_id, premise, now, now),
            )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=self._refusal_code(exc),
                    message=(
                        f"bible revision {bible_revision_id!r} not"
                        f" seeded for world {world_id!r}: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        created = self.get_bible(world_id, 1)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    def revise_bible(
        self,
        bible_revision_id: str,
        world_id: str,
        *,
        premise: str,
        genre: str,
        tone: str,
        calendar: str,
        physics: str,
        magic_rules: str,
        geography: str,
        society: str,
        politics: str,
        technology: str,
        religion: str,
        history: str,
        hard_rules: str,
        narrative_preferences: str,
        expected_state_version: int,
        now: str,
    ) -> Result[BibleRevision]:
        """Write the world's next Bible revision — the explicit
        full-content decision (never a template push, N-INV-006).

        Every one of the fourteen content fields is **required and
        written as given**: a revision is self-contained, so an omitted
        or empty field lands as the empty string — honest undeclared,
        **not** an inheritance from the previous revision (the caller
        says what the world is like; the store does not carry old
        words forward on the caller's behalf). Semantics: a world with
        no ``CURRENT`` revision has nothing to revise
        (``NOT_FOUND``); a stale ``expected_state_version`` is refused
        ``CONFLICT`` (the expected and actual counters ride the
        message). Otherwise one short transaction supersedes the
        current row (``status = 'SUPERSEDED'``, ``updated_at`` the
        caller's ``now``, ``state_version`` bumped) and lands the new
        row (``revision = old + 1``, ``parent_revision = old``,
        ``CURRENT``, the fourteen fields as given, both stamps the
        caller's ``now``, ``state_version = 1``) — supersede first,
        insert second, the order the single-CURRENT partial UNIQUE
        index demands; both words land or neither does. The old row is
        kept forever (append-only; 不减删) and stays citable through
        :meth:`get_bible`.
        """

        current = self.current_bible(world_id)
        if current is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"world {world_id!r} has no Bible revision to"
                        " revise"
                    ),
                )
            )
        if current.state_version != expected_state_version:
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"world {world_id!r}'s current Bible revision"
                        " not revised: another writer moved it first"
                        f" (the expected state_version was"
                        f" {expected_state_version}; its state_version"
                        f" is now {current.state_version}) — re-read"
                        " and retry"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            cursor = self._conn.execute(
                "UPDATE world_bible_revision SET status = 'SUPERSEDED',"
                " updated_at = ?, state_version = state_version + 1"
                " WHERE bible_revision_id = ? AND state_version = ?",
                (now, current.bible_revision_id, expected_state_version),
            )
            if cursor.rowcount != 1:
                self._conn.execute("ROLLBACK")
                began = False
                return self._cas_miss(world_id, current.bible_revision_id)
            self._conn.execute(
                "INSERT INTO world_bible_revision ("
                " bible_revision_id, world_id, revision, parent_revision,"
                " status, premise, genre, tone, calendar, physics,"
                " magic_rules, geography, society, politics, technology,"
                " religion, history, hard_rules, narrative_preferences,"
                " created_at, updated_at, state_version"
                ") VALUES (?, ?, ?, ?, 'CURRENT',"
                " ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    bible_revision_id,
                    world_id,
                    current.revision + 1,
                    current.revision,
                    premise,
                    genre,
                    tone,
                    calendar,
                    physics,
                    magic_rules,
                    geography,
                    society,
                    politics,
                    technology,
                    religion,
                    history,
                    hard_rules,
                    narrative_preferences,
                    now,
                    now,
                ),
            )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=self._refusal_code(exc),
                    message=(
                        f"bible revision {bible_revision_id!r} not"
                        f" written for world {world_id!r}: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        created = self.get_bible(world_id, current.revision + 1)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    # -- read faces ------------------------------------------------------------

    def current_bible(self, world_id: str) -> BibleRevision | None:
        """The world's one ``CURRENT`` Bible revision, or ``None`` —
        the honest answer for a world whose Bible was never seeded (a
        missing world is an answer, not an error)."""

        row = self._conn.execute(
            "SELECT bible_revision_id, world_id, revision,"
            " parent_revision, status, premise, genre, tone, calendar,"
            " physics, magic_rules, geography, society, politics,"
            " technology, religion, history, hard_rules,"
            " narrative_preferences, created_at, updated_at,"
            " state_version FROM world_bible_revision"
            " WHERE world_id = ? AND status = 'CURRENT'",
            (world_id,),
        ).fetchone()
        if row is None:
            return None
        return self._revision_from_row(row)

    def get_bible(
        self, world_id: str, revision: int
    ) -> BibleRevision | None:
        """One Bible revision by world and number, or ``None`` — the
        citation read: a ``SUPERSEDED`` revision answers exactly as it
        was written (history is rows, not errors)."""

        row = self._conn.execute(
            "SELECT bible_revision_id, world_id, revision,"
            " parent_revision, status, premise, genre, tone, calendar,"
            " physics, magic_rules, geography, society, politics,"
            " technology, religion, history, hard_rules,"
            " narrative_preferences, created_at, updated_at,"
            " state_version FROM world_bible_revision"
            " WHERE world_id = ? AND revision = ?",
            (world_id, revision),
        ).fetchone()
        if row is None:
            return None
        return self._revision_from_row(row)

    def bible_revisions(self, world_id: str) -> tuple[BibleRevision, ...]:
        """One world's Bible revisions, ``revision`` ascending — the
        version history, every word riding out (a superseded revision
        is the Bible's history, not an error)."""

        rows = self._conn.execute(
            "SELECT bible_revision_id, world_id, revision,"
            " parent_revision, status, premise, genre, tone, calendar,"
            " physics, magic_rules, geography, society, politics,"
            " technology, religion, history, hard_rules,"
            " narrative_preferences, created_at, updated_at,"
            " state_version FROM world_bible_revision"
            " WHERE world_id = ? ORDER BY revision ASC",
            (world_id,),
        ).fetchall()
        return tuple(self._revision_from_row(row) for row in rows)

    # -- shared machinery --------------------------------------------------------

    def _revision_from_row(self, row: tuple[Any, ...]) -> BibleRevision:
        """One record off one selected row (the column order every
        read above spells, and the migration's own)."""

        return BibleRevision(
            bible_revision_id=str(row[0]),
            world_id=str(row[1]),
            revision=int(row[2]),
            parent_revision=None if row[3] is None else int(row[3]),
            status=BibleRevisionStatus(str(row[4])),
            premise=str(row[5]),
            genre=str(row[6]),
            tone=str(row[7]),
            calendar=str(row[8]),
            physics=str(row[9]),
            magic_rules=str(row[10]),
            geography=str(row[11]),
            society=str(row[12]),
            politics=str(row[13]),
            technology=str(row[14]),
            religion=str(row[15]),
            history=str(row[16]),
            hard_rules=str(row[17]),
            narrative_preferences=str(row[18]),
            created_at=str(row[19]),
            updated_at=str(row[20]),
            state_version=int(row[21]),
        )

    def _cas_miss(
        self, world_id: str, bible_revision_id: str
    ) -> Err[BibleRevision]:
        """The guarded UPDATE's two honest answers: the row is gone
        (``NOT_FOUND``) or another writer moved it first
        (``CONFLICT``)."""

        row = self._conn.execute(
            "SELECT state_version FROM world_bible_revision"
            " WHERE bible_revision_id = ?",
            (bible_revision_id,),
        ).fetchone()
        if row is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"world {world_id!r}'s current Bible revision"
                        f" ({bible_revision_id!r}) not revised: it does"
                        " not exist"
                    ),
                )
            )
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"world {world_id!r}'s current Bible revision not"
                    " revised: another writer moved it first (its"
                    f" state_version is now {int(row[0])}; the expected"
                    " one is stale) — re-read and retry"
                ),
            )
        )

    @staticmethod
    def _refusal_code(exc: sqlite3.Error) -> DomainErrorCode:
        """Map the database's own refusal to the store's vocabulary —
        the world store's ``create_world`` narrowing (N-W10-6) spelled
        the same here: a UNIQUE clash is a ``CONFLICT`` (the identities
        exist, the shapes collide); a FOREIGN KEY refusal is
        ``NOT_FOUND`` (a referenced identity — the world — is missing);
        any other database failure is the database's own and answers
        ``DEPENDENCY_UNAVAILABLE`` with the raw error riding the
        message (a locked/broken database is never re-attributed as a
        missing identity)."""

        text = str(exc)
        if "UNIQUE constraint failed" in text:
            return DomainErrorCode.CONFLICT
        if "FOREIGN KEY constraint failed" in text:
            return DomainErrorCode.NOT_FOUND
        return DomainErrorCode.DEPENDENCY_UNAVAILABLE
