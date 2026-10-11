"""The World Cast & the player's identity (V3-3, TASK-OPI-bab4da9f…52)
— :class:`SqliteCastStore`, the SQL face of migration 0031's two
tables, and :func:`participant_namespace`, the one derivation that
unifies the cast's names.

Two durable faces Director's first planning must read (DOMAIN §20.1's
Cast row: ``world_actor`` — reused and untouched — plus these two):

- ``world_player_character`` — the reader's own durable character in
  one world (the design supplement §7.1's promotion of the package's
  ``user_character`` declaration from prompt material to a stored
  person): background, appearance, abilities, limits, location, state
  and what she knows. **One per world** — the table's ``UNIQUE
  (world_id)`` is the structural law, so a second row under the same
  world refuses at the storage level. The old ``world_actor`` is not
  reshaped (§7.1's boundary: it keeps representing AI-controlled
  actors); the player joins the participant namespace through this
  table's id instead.
- ``world_actor_profile`` — the AI actor's narrative profile
  (DATA §26.2.1's note: CharacterCard ≠ 本表): the story role
  (``PROTAGONIST`` / ``MAJOR`` / ``SUPPORTING``), whether the actor may
  carry a POV and at what weight, the long-term drive, the current
  arc's seed, and the private context no other character knows. §7.2's
  separation is this table's reason to exist: the card answers *who
  she is*, the profile answers *who she is in this world* — the six
  fields never migrate back onto the card.

The three profile columns that may be absent ride as NULL — the honest
*undeclared*: ``story_role`` / ``pov_eligible`` / ``pov_weight`` a
package (or a caller) never spoke answer ``None``, never a guessed
default, so a consumer can tell a field the template never took a
stance on from one it did. The profile's three arc texts and the
player character's eight content fields are the opposite posture: NOT
NULL columns the store writes as the empty string when the caller
declares nothing — the same honest-undeclared spelling the Bible's
content fields keep (0030's posture).

**THE ONE derivation** (:func:`participant_namespace`, DATA §26.2.1's
own note — 与 participants namespace 统一): the participant vocabulary
is ``cast ids ∪ {player_character_id} ∪ 居民名``, assembled — never
stored. The assembly recipe, one place:

- the **cast ids** are the persona ids
  :meth:`elc.world.store.SqliteWorldStore.actors_of` answers for the
  world (its records' ``persona_id`` half — the same ids the
  chronicle's ``participants`` column has always carried; the narrator
  computes the vocabulary live from the package today, and this
  function is the durable half's same shape — the narrator itself is
  *not* rewired by this cut, its consumers move in V3-4+);
- the **player id** is :meth:`SqliteCastStore.player_character`'s row
  id for the world (``None`` when the world declares no player — an
  honest world without a declared player contributes nothing, the
  conditional law);
- the **resident names** are the package's ``WorldPackage.residents``
  (包侧素材，按合同不进表 — prompt material, never store rows).

Discipline (the house store law, :mod:`elc.world.bible`'s posture):

- **Value semantics** — every refusal is a ``Result`` ``Err``, never an
  exception: ``CONFLICT`` = a uniqueness clash through the database's
  own surface (the player table's ``UNIQUE (world_id)``); ``NOT_FOUND``
  = a referenced identity (the world, the actor) does not exist (a
  FOREIGN KEY refusal is the same answer); ``VALIDATION_FAILED`` = the
  caller's own shape is wrong (a nameless player, a profile aimed at an
  actor bound to another world); ``DEPENDENCY_UNAVAILABLE`` = the
  database itself failed outside the vocabulary above (a locked or
  broken database is never re-attributed as a missing identity; the raw
  sqlite error rides the message). Messages are human sentences naming
  the row and the reason.
- **Idempotent and never rewriting** — both seed faces answer an
  already-seeded row unchanged and *write nothing*: the seed
  arguments are not compared and not applied, so a template's later
  update replayed through the open pass changes no stored row (the
  N-INV-006 machine half's sibling — the instance rows are the
  authority, a template edit is an explicit later decision, never a
  silent push).
- **CAS state_version** — creation mints ``state_version = 1`` (the
  counter belongs to its row).
- **No hidden clock** — every row's ``created_at`` / ``updated_at`` is
  stamped with the caller's ``now`` (both write faces take it as a
  parameter); the store consults no clock of its own.
- **One short transaction per write** — ``BEGIN IMMEDIATE`` …
  ``COMMIT``/``ROLLBACK`` with the began-flag posture (a failed BEGIN
  owns nothing; a failing ROLLBACK of our own must not break the
  Result contract).
- **Zero legacy touch** — the profile's reads name ``world_actor`` in
  SELECT only (the FK's own target); no statement of this module
  writes any pre-existing table.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = [
    "ActorProfileRecord",
    "PlayerCharacterRecord",
    "SqliteCastStore",
    "StoryRole",
    "participant_namespace",
]


class StoryRole(StrEnum):
    """The story-role vocabulary (DATA §26.2.1's word list, word for
    word): ``PROTAGONIST`` — the story is hers; ``MAJOR`` — her arc
    carries chapters; ``SUPPORTING`` — she colours the town's scenes.
    A profile the package (or caller) never declared rides ``None`` —
    the honest undeclared, not a fourth word. This enum and migration
    0031's ``story_role`` CHECK literal are one word list in two
    spellings: if the vocabulary ever grows, the DDL moves in the same
    cut (the loader's validation reads this enum, never a second
    tuple)."""

    PROTAGONIST = "PROTAGONIST"
    MAJOR = "MAJOR"
    SUPPORTING = "SUPPORTING"


@dataclass(frozen=True)
class ActorProfileRecord:
    """One ``world_actor_profile`` row — the AI actor's narrative
    profile in one world (DATA §26.2.1's entity contract).

    ``story_role`` / ``pov_eligible`` / ``pov_weight`` ride ``None``
    when never declared — the honest undeclared, never a guessed
    default. ``long_term_drive`` / ``current_arc_seed`` /
    ``private_context`` ride as they were written: a field the writer
    did not declare is the empty string."""

    actor_id: str
    world_id: str
    story_role: StoryRole | None
    pov_eligible: bool | None
    pov_weight: int | None
    long_term_drive: str
    current_arc_seed: str
    private_context: str
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class PlayerCharacterRecord:
    """One ``world_player_character`` row — the reader's own durable
    character in one world (DATA §26.2.1's entity contract).

    The eight content fields ride as they were written: a field the
    writer did not declare is the empty string, an honest undeclared —
    never inherited, never guessed. One row per world (the table's own
    ``UNIQUE (world_id)``)."""

    player_character_id: str
    world_id: str
    name: str
    background: str
    appearance: str
    abilities: str
    limits: str
    location: str
    state: str
    knowledge_refs: str
    created_at: str
    updated_at: str
    state_version: int


class SqliteCastStore:
    """Migration 0031's ``world_player_character`` and
    ``world_actor_profile`` write and read face.

    ``fence`` is the house constructor shape (every app.db store takes
    the shared epoch fence); migration 0031 carries no ``write_epoch``
    column, so the fence is held unused — the cast rows are
    creator-stamped, not epoch-guarded (the 0023/0029/0030 posture).
    """

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- write faces -----------------------------------------------------------

    def seed_actor_profile(
        self,
        actor_id: str,
        world_id: str,
        *,
        story_role: StoryRole | None = None,
        pov_eligible: bool | None = None,
        pov_weight: int | None = None,
        long_term_drive: str = "",
        current_arc_seed: str = "",
        private_context: str = "",
        now: str,
    ) -> Result[ActorProfileRecord]:
        """Seed one AI actor's narrative profile — the package's
        creation-time word about who this actor is *in this world*.

        **Idempotent and never rewriting**: if the actor already holds
        a profile the stored row is answered unchanged and *nothing is
        written* — the seed arguments are not compared and not
        applied, so a template's later edit replayed through this face
        is silently ignored (a template does not own an existing
        world's rewrite; the N-INV-006 machine half's sibling).

        Refusals: an ``actor_id`` no ``world_actor`` row carries is
        ``NOT_FOUND`` (the profile's FK rides the actor's own row); an
        actor that exists but answers to a **different** world is
        ``VALIDATION_FAILED`` naming both ids (the profile's
        ``world_id`` must be the actor's own world — a profile filed
        under the wrong world would be a lie about where the actor
        lives). Otherwise one short transaction lands the row: the
        declared ``story_role`` rides its canonical word (or NULL —
        the honest undeclared), ``pov_eligible`` rides 1/0 (or NULL;
        SQLite has no boolean), ``pov_weight`` the non-negative int as
        given, the three arc texts as given (an undeclared field the
        empty string), ``created_at`` / ``updated_at`` the caller's
        ``now`` and ``state_version = 1``.
        """

        existing = self.actor_profile(actor_id)
        if existing is not None:
            return Ok(existing)
        actor_world = self._actor_world_id(actor_id)
        if actor_world is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"actor profile {actor_id!r} not seeded for"
                        f" world {world_id!r}: no actor {actor_id!r} is"
                        " bound in this database"
                    ),
                )
            )
        if actor_world != world_id:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"actor profile {actor_id!r} not seeded for"
                        f" world {world_id!r}: the actor is bound to"
                        f" world {actor_world!r}, not to world"
                        f" {world_id!r} — a profile's world must name"
                        " the actor's own world"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_actor_profile ("
                " actor_id, world_id, story_role, pov_eligible,"
                " pov_weight, long_term_drive, current_arc_seed,"
                " private_context, created_at, updated_at, state_version"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    actor_id,
                    world_id,
                    None if story_role is None else story_role.value,
                    None if pov_eligible is None else int(pov_eligible),
                    pov_weight,
                    long_term_drive,
                    current_arc_seed,
                    private_context,
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
                        f"actor profile {actor_id!r} not seeded for"
                        f" world {world_id!r}: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        created = self.actor_profile(actor_id)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    def seed_player_character(
        self,
        player_character_id: str,
        world_id: str,
        *,
        name: str,
        background: str = "",
        appearance: str = "",
        abilities: str = "",
        limits: str = "",
        location: str = "",
        state: str = "",
        knowledge_refs: str = "",
        now: str,
    ) -> Result[PlayerCharacterRecord]:
        """Seed the world's one durable player character — the reader
        enters this world as this person (the design supplement §7.1's
        durable promotion of the package's ``user_character``
        declaration; the declared id survives unchanged as the stored
        row's id).

        **Idempotent per world, never rewriting**: if the world
        already holds its player character the stored row is answered
        unchanged and *nothing is written* — the seed arguments are
        not compared and not applied, so a package re-worded between
        opens (the player's name, even a changed id) changes no stored
        row: the instance is the authority, the open never fails
        because a template moved (the N-INV-006 machine half's
        sibling, keyed by world — the ``UNIQUE (world_id)`` law's
        read-side shape).

        Refusals: a ``name`` that is empty (or blank) is
        ``VALIDATION_FAILED`` — a half-drawn person does not sit at
        the table; a dangling ``world_id`` is refused by the table's
        own FK and surfaces as ``NOT_FOUND``; a second player
        character row under one world (a different id against a world
        that already has one) collides with the table's
        ``UNIQUE (world_id)`` and surfaces as ``CONFLICT``. Otherwise
        one short transaction lands the row: the eight content fields
        as given (an undeclared field the empty string — honest
        undeclared, never inherited, never guessed), both stamps the
        caller's ``now`` and ``state_version = 1``.
        """

        if not name.strip():
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"player character {player_character_id!r} not"
                        f" seeded for world {world_id!r}: the name must"
                        " be a non-empty string — a half-drawn person"
                        " does not sit at the table"
                    ),
                )
            )
        existing = self.player_character(world_id)
        if existing is not None:
            return Ok(existing)
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_player_character ("
                " player_character_id, world_id, name, background,"
                " appearance, abilities, limits, location, state,"
                " knowledge_refs, created_at, updated_at, state_version"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    player_character_id,
                    world_id,
                    name,
                    background,
                    appearance,
                    abilities,
                    limits,
                    location,
                    state,
                    knowledge_refs,
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
                        f"player character {player_character_id!r} not"
                        f" seeded for world {world_id!r}: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        created = self.player_character(world_id)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    # -- read faces ------------------------------------------------------------

    def actor_profile(self, actor_id: str) -> ActorProfileRecord | None:
        """One actor's narrative profile by id, or ``None`` — the
        honest answer for an actor whose profile was never seeded (a
        missing profile is an answer, not an error)."""

        row = self._conn.execute(
            "SELECT actor_id, world_id, story_role, pov_eligible,"
            " pov_weight, long_term_drive, current_arc_seed,"
            " private_context, created_at, updated_at, state_version"
            " FROM world_actor_profile WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        if row is None:
            return None
        return self._profile_from_row(row)

    def actor_profiles_of(
        self, world_id: str
    ) -> tuple[ActorProfileRecord, ...]:
        """One world's actor profiles, ``actor_id`` ascending — the
        deterministic read Director's cast input walks (a replayed
        open answers the same order)."""

        rows = self._conn.execute(
            "SELECT actor_id, world_id, story_role, pov_eligible,"
            " pov_weight, long_term_drive, current_arc_seed,"
            " private_context, created_at, updated_at, state_version"
            " FROM world_actor_profile WHERE world_id = ?"
            " ORDER BY actor_id ASC",
            (world_id,),
        ).fetchall()
        return tuple(self._profile_from_row(row) for row in rows)

    def player_character(self, world_id: str) -> PlayerCharacterRecord | None:
        """The world's one player character, or ``None`` — the honest
        answer for a world that declares no player (a missing world is
        an answer, not an error; the conditional law the
        ``UNIQUE (world_id)`` structure makes total: at most one row
        exists to find)."""

        row = self._conn.execute(
            "SELECT player_character_id, world_id, name, background,"
            " appearance, abilities, limits, location, state,"
            " knowledge_refs, created_at, updated_at, state_version"
            " FROM world_player_character WHERE world_id = ?",
            (world_id,),
        ).fetchone()
        if row is None:
            return None
        return self._player_from_row(row)

    # -- shared machinery --------------------------------------------------------

    def _actor_world_id(self, actor_id: str) -> str | None:
        """The world an actor row answers to, or ``None`` when no such
        actor is bound (the profile FK's own target, read not
        written — the pre-check that lets the two refusals above speak
        human sentences instead of raw FK text)."""

        row = self._conn.execute(
            "SELECT world_id FROM world_actor WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def _profile_from_row(self, row: tuple[Any, ...]) -> ActorProfileRecord:
        """One record off one selected row (the column order every
        read above spells, and the migration's own)."""

        return ActorProfileRecord(
            actor_id=str(row[0]),
            world_id=str(row[1]),
            story_role=None if row[2] is None else StoryRole(str(row[2])),
            pov_eligible=None if row[3] is None else bool(row[3]),
            pov_weight=None if row[4] is None else int(row[4]),
            long_term_drive=str(row[5]),
            current_arc_seed=str(row[6]),
            private_context=str(row[7]),
            created_at=str(row[8]),
            updated_at=str(row[9]),
            state_version=int(row[10]),
        )

    def _player_from_row(
        self, row: tuple[Any, ...]
    ) -> PlayerCharacterRecord:
        """One record off one selected row (the column order every
        read above spells, and the migration's own)."""

        return PlayerCharacterRecord(
            player_character_id=str(row[0]),
            world_id=str(row[1]),
            name=str(row[2]),
            background=str(row[3]),
            appearance=str(row[4]),
            abilities=str(row[5]),
            limits=str(row[6]),
            location=str(row[7]),
            state=str(row[8]),
            knowledge_refs=str(row[9]),
            created_at=str(row[10]),
            updated_at=str(row[11]),
            state_version=int(row[12]),
        )

    @staticmethod
    def _refusal_code(exc: sqlite3.Error) -> DomainErrorCode:
        """Map the database's own refusal to the store's vocabulary —
        the Bible store's mapping spelled the same here: a UNIQUE
        clash is a ``CONFLICT`` (the identities exist, the shapes
        collide); a FOREIGN KEY refusal is ``NOT_FOUND`` (a referenced
        identity — the world — is missing); any other database failure
        is the database's own and answers
        ``DEPENDENCY_UNAVAILABLE`` with the raw error riding the
        message (a locked/broken database is never re-attributed as a
        missing identity)."""

        text = str(exc)
        if "UNIQUE constraint failed" in text:
            return DomainErrorCode.CONFLICT
        if "FOREIGN KEY constraint failed" in text:
            return DomainErrorCode.NOT_FOUND
        return DomainErrorCode.DEPENDENCY_UNAVAILABLE


def participant_namespace(
    *,
    persona_ids: Iterable[str],
    player_character_id: str | None = None,
    resident_names: Iterable[str] = (),
) -> frozenset[str]:
    """The one derivation DATA §26.2.1's note names — 与 participants
    namespace 统一: the vocabulary a chronicle event's ``participants``
    column may carry, assembled from the world's three person sources
    and never stored:

    - ``persona_ids`` — the cast's persona ids
      (:meth:`elc.world.store.SqliteWorldStore.actors_of`'s records'
      ``persona_id`` half for the world; the ids the chronicle has
      always carried);
    - ``player_character_id`` — the durable player character's id
      (:meth:`SqliteCastStore.player_character`'s row id; ``None``
      contributes nothing — an honest world without a declared player
      has exactly the pre-player vocabulary);
    - ``resident_names`` — the town's purely narrative residents
      (``WorldPackage.residents`` — 包侧素材，按合同不进表: prompt
      material, never store rows).

    A ``None`` player id and empty strings drop out (an empty word
    names nobody); the result is a ``frozenset`` — order-free, so two
    assemblies of the same town answer equal sets. Pure function: no
    store, no clock, no I/O — the caller gathers the three sources
    (the recipe above is the whole contract).
    """

    words: set[str] = set()
    for word in persona_ids:
        if word:
            words.add(word)
    if player_character_id:
        words.add(player_character_id)
    for word in resident_names:
        if word:
            words.add(word)
    return frozenset(words)
