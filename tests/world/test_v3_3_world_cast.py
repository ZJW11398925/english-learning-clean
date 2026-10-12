"""V3-3 — World Cast & Player Identity (eight pin groups).

The Narrative V3 program's third cut (TASK-OPI-bab4da9f…52 /
VAL-OPI-bab4da9f…54): migration 0031's two tables —
``world_player_character`` (the reader's own durable character in one
world; ``UNIQUE (world_id)`` is the one-player-per-world structural
law) and ``world_actor_profile`` (the AI actor's narrative profile:
story role, POV eligibility and weight, long-term drive, current arc
seed, private context — DATA §26.2.1's note: CharacterCard ≠ 本表;
its storage shape since rebuilt by 0032's composite FK) —
plus the store (:mod:`elc.world.cast`), the seed wired into the
world's birth (``ensure_builtin_worlds`` / ``open_host``) and the one
derivation (:func:`elc.world.cast.participant_namespace`) that unifies
the participant vocabulary (the durable actor ids ∪
{player_character_id} — the V3-3R identity freeze).
The contract was already canonical — DATA §26.2.1's two entity
entries, DOMAIN §20.1's Cast row and §20.2's authority table, the
design supplement §7.1 (the user character durable, ``world_actor``
untouched) and §7.2 (the profile's six fields never migrate back onto
the card), IMPLEMENTATION_PLAN §20's V3-3 row. The groups:

1. **migration and shape** — both tables' column sets verbatim
   (PRAGMA order), the ``story_role`` CHECK's three-word vocabulary
   (a fourth word refuses; the three words and NULL are legal — NULL
   is the honest undeclared, not a fourth word), ``pov_eligible``
   refusing 2 (0/1/NULL legal — SQLite has no boolean),
   ``pov_weight`` refusing a negative, the ``UNIQUE (world_id)``
   structural law (two player rows under one world refuse), both FKs
   refusing dangling references, the ``state_version > 0`` CHECK, the
   composite-FK storage invariant 0032 rebuilt onto
   ``world_actor_profile`` (a profile filed under a world its actor
   is not bound to refuses at the database's own surface; the rebuilt
   DDL carries ``FOREIGN KEY (actor_id, world_id)`` — the store's
   precheck stays the human-words layer), and the chain self-pin (the
   shared constants say ``0037_actor_memory_chapter_settlement`` / ``37``, a
   fresh database stamps exactly that — the head literal moved on with
   V3-5's 0033_segment_commit, V3-5R's 0034_segment_terminality,
   V3-6's 0035_user_gate_action, V3-6R's 0036_action_replan and
   V3-7's 0037_actor_memory_chapter_settlement);
2. **the open-time seed from the package** — a builtin package's
   birth carries its cast's durable half: Nell's profile with the six
   fields verbatim (``PROTAGONIST`` / ``True`` / ``1`` / the three arc
   sentences), the other actors none (berrymoor binds one), the
   player character under the package's own unchanged id
   (``actor-berrymoor-you``), name / background(anchor) /
   location(home) verbatim and the other five content fields the
   empty string;
3. **idempotent and never rewriting (this cut's core machine pin)** —
   a replayed seed (and a full reopen) writes nothing (row counts and
   every field byte-identical), and the package file edited between
   opens — Nell's ``long_term_drive`` re-worded, the player's name
   changed — still writes nothing: the open succeeds and the stored
   rows are byte-identical to the first write (the N-INV-006 machine
   half's sibling, the Bible's own pin's shape);
4. **the honest undeclared** — a minimal v8 package (a cast member
   with only persona_id and name, no ``user_character`` section)
   seeds a profile whose three nullable columns are all ``None`` and
   whose three arc texts are all empty, and whose world answers
   ``player_character(...) is None`` — the conditional law;
5. **the read face** — one profile by id, the world's profiles in
   ``actor_id`` ascending order, and an unseeded world answering
   ``None`` / the empty tuple;
6. **the participant namespace** — :func:`participant_namespace`'s
   pure-function law (``None`` and empty strings drop out; order
   free) and the end-to-end assembly pin: berrymoor seeded, the
   ``actor_id`` halves from ``actors_of`` ∪ the player id from the
   cast store assemble exactly the two durable identities — with the
   freeze's negative controls (the persona id, the CharacterCard /
   template identity, and the package's resident names, no durable
   V3 participant identity yet, both stay out);
7. **the package v8 wall** — v8 accepted; v7 refused (the message
   carries "version must be 8"); v9 refused; the shipped berrymoor
   loads at version 8 with the six keys decoded verbatim; the bad
   shapes refused one by one (a ``story_role`` outside the three
   words, a non-bool ``pov_eligible``, a negative or boolean
   ``pov_weight``, a blank arc text);
8. **the old world_actor zero-touch** — the seeded berrymoor's
   ``world_actor`` still carries exactly one row under the derived id
   (``actor-berrymoor-nell``, the derivation law unchanged), the
   profile's FK rides it, and :mod:`elc.world.cast` imports cold (the
   P4-3 cold-start discipline).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.bible import SqliteBibleStore
from elc.world.cast import (
    SqliteCastStore,
    StoryRole,
    participant_namespace,
)
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WORLD_PACKAGE_VERSION,
    ensure_builtin_worlds,
    load_world_package,
)
from elc.world.store import SqliteWorldStore
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)

REPO = Path(__file__).resolve().parents[2]

NOW = "2026-10-12T00:00:00+00:00"
LATER = "2026-10-12T01:00:00+00:00"

BERRYMOOR = "world-berrymoor"
TEST_WORLD_ID = "world-casttest"

# The shipped Nell's six profile words, verbatim from the package
# (the seed's source of truth — these ride the JSON as authored).
NELL_DRIVE = (
    "Keep the green door open on her own terms — the bindery working,"
    " her grandfather's tools staying hers, and the sign repainted"
    " rather than taken down."
)
NELL_ARC = (
    "The order book is thinning and the town has started to talk about"
    " the shop in the past tense; the first hard frost is coming."
)
NELL_PRIVATE = (
    "She has priced the tools once already, on the back page of the"
    " ledger, and has told no one."
)

# The two-identity namespace the end-to-end assembly pin expects: the
# AI-controlled durable characters' actor ids ∪ the player's durable
# id — the V3-3R canonical identity. The persona id (the
# CharacterCard / template identity) and the residents' names (no
# durable V3 participant identity yet) stay out; the negative
# controls ride the assembly pin itself.
BERRYMOOR_NAMESPACE = frozenset(
    {
        "actor-berrymoor-nell",
        "actor-berrymoor-you",
    }
)


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db — the production profile's
    foreign-keys-ON (the dangling-reference refusals are the database's
    own, so the fixture must spell the same posture
    ``elc.platform.db.connection.connect`` does)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def cast(conn: sqlite3.Connection) -> SqliteCastStore:
    """The cast store over the fresh database."""

    return SqliteCastStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def world_store(conn: sqlite3.Connection) -> SqliteWorldStore:
    """The world store over the same fresh database."""

    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _write_world(directory: Path, payload: dict, filename: str) -> Path:
    """One world package file into a temporary worlds directory (the
    seed tests' material; the bytes written are the bytes the loader
    reads)."""

    directory.mkdir(exist_ok=True)
    path = directory / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _minimal_payload() -> dict:
    """A minimal valid v8 package: identity, calendar start, setting,
    a cast of one bare member (no profile keys), a one-event pool, a
    supply declaration — and no ``user_character`` section."""

    return {
        "world_id": TEST_WORLD_ID,
        "name": "Casttest",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2026-01-01",
        "setting": ["A small town for cast tests."],
        "cast": [{"persona_id": "persona-nell-alder", "name": "Nell"}],
        "event_pool": [
            {
                "kind": "morning",
                "narration": "The mill wheel turns.",
                "narration_zh": "磨坊的水轮转了起来。",
                "days": 1,
            }
        ],
        "supply": {"families": ["DISC"], "note": "declared-not-consumed"},
    }


def _berrymoor_dir(tmp_path: Path) -> Path:
    """A temporary worlds directory carrying the shipped berrymoor
    package, byte for byte as it ships (the seed tests ride the real
    file's content through the real loader)."""

    directory = tmp_path / "worlds"
    directory.mkdir(exist_ok=True)
    (directory / "berrymoor.json").write_bytes(
        (BUILTIN_WORLDS_DIR / "berrymoor.json").read_bytes()
    )
    return directory


def _fresh_stores(
    db_path: Path,
) -> tuple[
    SqliteWorldStore, SqliteBibleStore, SqliteCastStore, sqlite3.Connection
]:
    """One fresh database, the world-side stores over it (the seed
    tests' composition-root shape: the trio rides one connection)."""

    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    fence = open_runtime_epoch(db)
    return (
        SqliteWorldStore(db, fence),
        SqliteBibleStore(db, fence),
        SqliteCastStore(db, fence),
        db,
    )


def _seed_berrymoor(
    tmp_path: Path,
) -> tuple[
    Path, SqliteWorldStore, SqliteCastStore, sqlite3.Connection
]:
    """Seed the shipped berrymoor through a temporary worlds
    directory over a fresh database — the machine every seed-side pin
    rides."""

    directory = _berrymoor_dir(tmp_path)
    store, bible, cast_store, db = _fresh_stores(tmp_path / "seed.db")
    ensure_builtin_worlds(
        store,
        directory,
        persona_exists=lambda persona_id: persona_id
        == "persona-nell-alder",
        bible_store=bible,
        cast_store=cast_store,
    )
    return directory, store, cast_store, db


def _rerun_seed(
    directory: Path,
    db: sqlite3.Connection,
    cast_store: SqliteCastStore,
) -> None:
    """One replayed ``ensure_builtin_worlds`` pass over the same
    database and directory (the idempotence pins' second move)."""

    fence = open_runtime_epoch(db)
    ensure_builtin_worlds(
        SqliteWorldStore(db, fence),
        directory,
        persona_exists=lambda persona_id: persona_id
        == "persona-nell-alder",
        bible_store=SqliteBibleStore(db, fence),
        cast_store=cast_store,
    )


# ---------------------------------------------------------------------------
# 1. migration and shape
# ---------------------------------------------------------------------------


def test_the_shared_constants_and_a_fresh_db_say_the_chain_head() -> None:
    assert MIGRATION_IDS[-1] == "0037_actor_memory_chapter_settlement"
    assert SCHEMA_HEAD_FILE == "0037_actor_memory_chapter_settlement.sql"
    assert SCHEMA_HEAD_VERSION == "37"
    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0037_actor_memory_chapter_settlement"
    assert schema_version(fresh) == SCHEMA_HEAD_VERSION == "37"
    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": "37",
        "runtime_schema_version": "37",
    }


def test_world_player_character_carries_the_contract_columns(
    conn: sqlite3.Connection,
) -> None:
    """The physical column set, in order — DATA §26.2.1's
    ``world_player_character`` entity contract verbatim (the id, the
    world FK, the eight content fields in the canonical order, the
    bookkeeping pair, the CAS counter)."""

    columns = [
        str(row[1])
        for row in conn.execute(
            "PRAGMA table_info(world_player_character)"
        ).fetchall()
    ]
    assert columns == [
        "player_character_id",
        "world_id",
        "name",
        "background",
        "appearance",
        "abilities",
        "limits",
        "location",
        "state",
        "knowledge_refs",
        "created_at",
        "updated_at",
        "state_version",
    ]


def test_world_actor_profile_carries_the_contract_columns(
    conn: sqlite3.Connection,
) -> None:
    """The physical column set, in order — DATA §26.2.1's
    ``world_actor_profile`` entity contract verbatim (the actor FK,
    the world FK, the three nullable declaration columns, the three
    arc texts, the bookkeeping pair, the CAS counter)."""

    columns = [
        str(row[1])
        for row in conn.execute(
            "PRAGMA table_info(world_actor_profile)"
        ).fetchall()
    ]
    assert columns == [
        "actor_id",
        "world_id",
        "story_role",
        "pov_eligible",
        "pov_weight",
        "long_term_drive",
        "current_arc_seed",
        "private_context",
        "created_at",
        "updated_at",
        "state_version",
    ]


def _insert_world(conn: sqlite3.Connection, world_id: str) -> None:
    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES (?, 'W', NULL, ?)",
        (world_id, NOW),
    )
    # Committed at once: the store faces run their own
    # ``BEGIN IMMEDIATE`` transactions, and an open implicit
    # transaction would refuse them.
    conn.commit()


def _insert_card(conn: sqlite3.Connection, persona_id: str) -> None:
    """One minimal character card (the card a non-builtin persona's
    actor binding needs — ``world_actor.persona_id`` rides the card
    table's own FK)."""

    conn.execute(
        "INSERT INTO character_card ("
        " character_id, persona_id, name, identity, personality,"
        " background, speech_style, \"values\", boundaries, opening,"
        " scenario, generation_policy, lore_refs, revision, status,"
        " is_builtin, created_at, updated_at"
        ") VALUES (?, ?, 'N', 'i', 'p', 'b', 's', 'v', 'bo', 'o',"
        " 'sc', 'auto', '', 1, 'active', 1, ?, ?)",
        (f"cpkg-{persona_id}", persona_id, NOW, NOW),
    )


def _insert_actor(
    conn: sqlite3.Connection,
    actor_id: str,
    world_id: str,
    persona_id: str = "persona-nell-alder",
) -> None:
    if persona_id != "persona-nell-alder":
        _insert_card(conn, persona_id)
    conn.execute(
        "INSERT INTO world_actor (actor_id, world_id, persona_id,"
        " created_at) VALUES (?, ?, ?, ?)",
        (actor_id, world_id, persona_id, NOW),
    )
    conn.commit()


def test_the_story_role_vocabulary_is_exactly_the_canonical_three_words(
    conn: sqlite3.Connection,
) -> None:
    """The CHECK's word list is PROTAGONIST / MAJOR / SUPPORTING — a
    word borrowed from another table refuses, while the three words
    and NULL (the honest undeclared) are all legal (each on its own
    actor row — one profile per actor)."""

    _insert_world(conn, "w")
    insert = (
        "INSERT INTO world_actor_profile ("
        " actor_id, world_id, story_role, pov_eligible, pov_weight,"
        " long_term_drive, current_arc_seed, private_context,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'w', ?, NULL, NULL, '', '', '', ?, ?, 1)"
    )
    _insert_actor(conn, "a-bad", "w", persona_id="persona-bad")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("a-bad", "ADOPTED", NOW, NOW))
    for ordinal, word in enumerate(
        ("PROTAGONIST", "MAJOR", "SUPPORTING", None)
    ):
        actor_id = f"a-{ordinal}"
        _insert_actor(conn, actor_id, "w", persona_id=f"persona-{actor_id}")
        conn.execute(insert, (actor_id, word, NOW, NOW))
        stored = conn.execute(
            "SELECT story_role FROM world_actor_profile WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()[0]
        assert stored == word


def test_the_pov_checks_hold(
    conn: sqlite3.Connection,
) -> None:
    """``pov_eligible`` carries 0/1/NULL and refuses 2 (SQLite has no
    boolean — the column stores the int half); ``pov_weight`` refuses
    a negative and accepts zero (each on its own actor row — one
    profile per actor)."""

    _insert_world(conn, "w")
    insert = (
        "INSERT INTO world_actor_profile ("
        " actor_id, world_id, story_role, pov_eligible, pov_weight,"
        " long_term_drive, current_arc_seed, private_context,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'w', NULL, ?, ?, '', '', '', ?, ?, 1)"
    )
    _insert_actor(conn, "a-bad", "w", persona_id="persona-bad")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("a-bad", 2, 0, NOW, NOW))
    for ordinal, (eligible, weight) in enumerate(
        ((0, 0), (1, 3), (None, None))
    ):
        actor_id = f"a-ok-{ordinal}"
        _insert_actor(conn, actor_id, "w", persona_id=f"persona-{actor_id}")
        conn.execute(insert, (actor_id, eligible, weight, NOW, NOW))
    _insert_actor(conn, "a-negative", "w", persona_id="persona-negative")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("a-negative", None, -1, NOW, NOW))


def test_one_player_character_per_world_is_a_storage_fact(
    conn: sqlite3.Connection,
) -> None:
    """The ``UNIQUE (world_id)`` structural law: two player character
    rows under one world refuse — the reader enters each world as one
    durable person."""

    _insert_world(conn, "w")
    insert = (
        "INSERT INTO world_player_character ("
        " player_character_id, world_id, name, background, appearance,"
        " abilities, limits, location, state, knowledge_refs,"
        " created_at, updated_at, state_version"
        ") VALUES (?, 'w', 'You', '', '', '', '', '', '', '', ?, ?, 1)"
    )
    conn.execute(insert, ("pc-1", NOW, NOW))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("pc-2", NOW, NOW))
    conn.rollback()


def test_the_dangling_references_are_refused_by_the_table_fks(
    conn: sqlite3.Connection,
) -> None:
    """Both FK chains are the tables' own: a player character for a
    world that does not exist refuses, and a profile for an actor
    (and a world) that do not exist refuse (the store surfaces both
    as ``NOT_FOUND``)."""

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_player_character ("
            " player_character_id, world_id, name, background,"
            " appearance, abilities, limits, location, state,"
            " knowledge_refs, created_at, updated_at, state_version"
            ") VALUES ('pc-ghost', 'world-nowhere', 'You', '', '',"
            " '', '', '', '', '', ?, ?, 1)",
            (NOW, NOW),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_actor_profile ("
            " actor_id, world_id, story_role, pov_eligible, pov_weight,"
            " long_term_drive, current_arc_seed, private_context,"
            " created_at, updated_at, state_version"
            ") VALUES ('a-ghost', 'world-nowhere', NULL, NULL, NULL,"
            " '', '', '', ?, ?, 1)",
            (NOW, NOW),
        )
    conn.rollback()


def test_the_state_version_check_holds(
    conn: sqlite3.Connection,
) -> None:
    """``state_version > 0`` is both tables' own CAS floor: a zero
    mints nothing."""

    _insert_world(conn, "w")
    _insert_actor(conn, "a1", "w")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_player_character ("
            " player_character_id, world_id, name, background,"
            " appearance, abilities, limits, location, state,"
            " knowledge_refs, created_at, updated_at, state_version"
            ") VALUES ('pc-zero', 'w', 'You', '', '', '', '', '', '',"
            " '', ?, ?, 0)",
            (NOW, NOW),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_actor_profile ("
            " actor_id, world_id, story_role, pov_eligible, pov_weight,"
            " long_term_drive, current_arc_seed, private_context,"
            " created_at, updated_at, state_version"
            ") VALUES ('a1', 'w', NULL, NULL, NULL, '', '', '',"
            " ?, ?, 0)",
            (NOW, NOW),
        )
    conn.rollback()


def test_a_profile_filed_under_another_world_refuses_at_the_storage_level(
    conn: sqlite3.Connection,
) -> None:
    """The V3-3R storage invariant (the external review's item 4,
    migration 0032): a profile filed under a world its actor is not
    bound to refuses at the database's own surface — the composite
    ``(actor_id, world_id) → world_actor(actor_id, world_id)`` FK,
    whose target key is 0023's own ``UNIQUE (actor_id, world_id)`` —
    and the rebuilt table's DDL carries the composite clause (the
    store's precheck is the human-words layer above this backstop)."""

    _insert_world(conn, "w")
    _insert_world(conn, "w2")
    _insert_actor(conn, "a1", "w")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_actor_profile ("
            " actor_id, world_id, story_role, pov_eligible, pov_weight,"
            " long_term_drive, current_arc_seed, private_context,"
            " created_at, updated_at, state_version"
            ") VALUES ('a1', 'w2', NULL, NULL, NULL, '', '', '',"
            " ?, ?, 1)",
            (NOW, NOW),
        )
    conn.rollback()
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master"
        " WHERE type = 'table' AND name = 'world_actor_profile'"
    ).fetchone()[0]
    assert "FOREIGN KEY (actor_id, world_id)" in ddl


# ---------------------------------------------------------------------------
# 2. the open-time seed from the package
# ---------------------------------------------------------------------------


def test_the_seed_lands_nells_profile_and_the_player_character(
    tmp_path: Path,
) -> None:
    """A builtin package's birth carries its cast's durable half, the
    real machine: the shipped berrymoor's Nell gets her profile with
    the six fields verbatim (``PROTAGONIST`` / ``True`` / ``1`` / the
    three arc sentences), the player character lands under the
    package's own unchanged id with name / background(anchor) /
    location(home) verbatim and the other five content fields
    honestly empty."""

    _directory, _store, cast_store, _db = _seed_berrymoor(tmp_path)

    profiles = cast_store.actor_profiles_of(BERRYMOOR)
    assert [profile.actor_id for profile in profiles] == [
        "actor-berrymoor-nell"
    ]
    nell = profiles[0]
    assert nell.world_id == BERRYMOOR
    assert nell.story_role is StoryRole.PROTAGONIST
    assert nell.pov_eligible is True
    assert nell.pov_weight == 1
    assert nell.long_term_drive == NELL_DRIVE
    assert nell.current_arc_seed == NELL_ARC
    assert nell.private_context == NELL_PRIVATE

    player = cast_store.player_character(BERRYMOOR)
    assert player is not None
    assert player.player_character_id == "actor-berrymoor-you"
    assert player.world_id == BERRYMOOR
    assert player.name == "你"
    assert player.background == "你是镇上的人，住在装订铺楼上的小房间"
    assert player.location == "装订铺楼上"
    assert player.appearance == ""
    assert player.abilities == ""
    assert player.limits == ""
    assert player.state == ""
    assert player.knowledge_refs == ""


def test_the_open_host_wires_the_same_seed(
    tmp_path: Path,
) -> None:
    """The production path: an ``open_host`` pass seeds the real
    builtin world's cast half — Nell's profile and the player
    character both present through the real wiring."""

    host = open_host(tmp_path / "app.db", provider=ScriptedPersonaProvider())
    try:
        cast_store = SqliteCastStore(host.db, open_runtime_epoch(host.db))
        nell = cast_store.actor_profile("actor-berrymoor-nell")
        assert nell is not None
        assert nell.story_role is StoryRole.PROTAGONIST
        assert nell.pov_eligible is True
        assert nell.pov_weight == 1
        player = cast_store.player_character(BERRYMOOR)
        assert player is not None
        assert player.player_character_id == "actor-berrymoor-you"
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 3. idempotent and never rewriting (this cut's core machine pin)
# ---------------------------------------------------------------------------


def test_a_replayed_seed_and_a_reopen_write_nothing(
    tmp_path: Path,
) -> None:
    """The idempotence law: a replayed seed — and a reopen of the same
    database through fresh store objects — leave both tables' row
    counts and every stored field exactly as the first write left
    them."""

    directory, _store, cast_store, db = _seed_berrymoor(tmp_path)
    profiles_before = cast_store.actor_profiles_of(BERRYMOOR)
    player_before = cast_store.player_character(BERRYMOOR)
    assert len(profiles_before) == 1
    assert player_before is not None

    _rerun_seed(directory, db, cast_store)
    assert cast_store.actor_profiles_of(BERRYMOOR) == profiles_before
    assert cast_store.player_character(BERRYMOOR) == player_before

    fence = open_runtime_epoch(db)
    reopened = SqliteCastStore(db, fence)
    _rerun_seed(directory, db, reopened)
    assert reopened.actor_profiles_of(BERRYMOOR) == profiles_before
    assert reopened.player_character(BERRYMOOR) == player_before
    assert db.execute("SELECT COUNT(*) FROM world_actor_profile").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM world_player_character").fetchone()[0]
        == 1
    )


def test_a_template_edit_does_not_rewrite_the_seeded_rows(
    tmp_path: Path,
) -> None:
    """The N-INV-006 machine half's sibling (the Bible's own pin's
    shape): the package file edited between opens — Nell's
    ``long_term_drive`` re-worded, the player's ``name`` changed, her
    id even swapped — then the seed re-run: the open succeeds and the
    stored rows are byte-identical to the first write, one row each
    still. A template does not own an existing world's rewrite."""

    directory, _store, cast_store, db = _seed_berrymoor(tmp_path)
    profiles_before = cast_store.actor_profiles_of(BERRYMOOR)
    player_before = cast_store.player_character(BERRYMOOR)
    assert profiles_before[0].long_term_drive == NELL_DRIVE
    assert player_before is not None
    assert player_before.name == "你"

    payload = json.loads(
        (directory / "berrymoor.json").read_text(encoding="utf-8")
    )
    payload["cast"][0]["long_term_drive"] = "A template's later word."
    payload["user_character"]["name"] = "Template Name"
    payload["user_character"]["id"] = "actor-berrymoor-renamed"
    (directory / "berrymoor.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )

    _rerun_seed(directory, db, cast_store)

    assert cast_store.actor_profiles_of(BERRYMOOR) == profiles_before
    assert cast_store.player_character(BERRYMOOR) == player_before
    assert db.execute("SELECT COUNT(*) FROM world_actor_profile").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM world_player_character").fetchone()[0]
        == 1
    )
    # Byte-identical means the raw columns too — not just the records'
    # equality (the stamps and the unchanged id included).
    raw = db.execute(
        "SELECT actor_id, world_id, story_role, pov_eligible,"
        " pov_weight, long_term_drive, current_arc_seed,"
        " private_context, created_at, updated_at, state_version"
        " FROM world_actor_profile WHERE actor_id ="
        " 'actor-berrymoor-nell'"
    ).fetchone()
    assert raw[5] == NELL_DRIVE
    assert raw[8] == profiles_before[0].created_at
    raw_player = db.execute(
        "SELECT player_character_id, world_id, name, created_at"
        " FROM world_player_character WHERE world_id = ?",
        (BERRYMOOR,),
    ).fetchone()
    assert raw_player[0] == "actor-berrymoor-you"
    assert raw_player[2] == "你"
    assert raw_player[3] == player_before.created_at


# ---------------------------------------------------------------------------
# 4. the honest undeclared
# ---------------------------------------------------------------------------


def test_a_minimal_package_seeds_the_honest_undeclared(
    tmp_path: Path,
) -> None:
    """The minimal v8 package: a cast member with only persona_id and
    name (no profile keys) seeds a profile whose three nullable
    columns are all ``None`` and whose three arc texts are all empty;
    and a package with no ``user_character`` section leaves the
    world's player read answering ``None`` — the conditional law."""

    directory = tmp_path / "worlds"
    _write_world(directory, _minimal_payload(), f"{TEST_WORLD_ID}.json")
    _store, bible, cast_store, _db = _fresh_stores(tmp_path / "seed.db")
    ensure_builtin_worlds(
        _store,
        directory,
        persona_exists=lambda _: True,
        bible_store=bible,
        cast_store=cast_store,
    )

    profiles = cast_store.actor_profiles_of(TEST_WORLD_ID)
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.actor_id == "actor-casttest-nell"
    assert profile.story_role is None
    assert profile.pov_eligible is None
    assert profile.pov_weight is None
    assert profile.long_term_drive == ""
    assert profile.current_arc_seed == ""
    assert profile.private_context == ""
    assert cast_store.player_character(TEST_WORLD_ID) is None


# ---------------------------------------------------------------------------
# 5. the read face
# ---------------------------------------------------------------------------


def test_the_read_faces_answer_by_id_and_in_order(
    conn: sqlite3.Connection,
    cast: SqliteCastStore,
) -> None:
    """One profile by id; the world's profiles in ``actor_id``
    ascending order; an unseeded world answers ``None`` / the empty
    tuple — the honest zeros."""

    _insert_world(conn, "w")
    for actor_id, persona in (
        ("actor-b", "persona-b"),
        ("actor-a", "persona-a"),
        ("actor-c", "persona-c"),
    ):
        _insert_actor(conn, actor_id, "w", persona_id=persona)
    seeded = cast.seed_actor_profile(
        "actor-b", "w", story_role=StoryRole.MAJOR, now=NOW
    )
    assert isinstance(seeded, Ok)
    seeded = cast.seed_actor_profile(
        "actor-a", "w", story_role=StoryRole.PROTAGONIST, now=NOW
    )
    assert isinstance(seeded, Ok)

    one = cast.actor_profile("actor-a")
    assert one is not None
    assert one.actor_id == "actor-a"
    assert one.story_role is StoryRole.PROTAGONIST
    assert cast.actor_profile("actor-nowhere") is None

    ordered = cast.actor_profiles_of("w")
    assert [profile.actor_id for profile in ordered] == [
        "actor-a",
        "actor-b",
    ]
    assert cast.actor_profiles_of("world-nowhere") == ()
    assert cast.player_character("world-nowhere") is None


def test_the_seed_faces_answer_the_stored_row(
    conn: sqlite3.Connection,
    cast: SqliteCastStore,
) -> None:
    """The two seed faces' Ok shapes: a seeded profile answers the
    record with ``state_version = 1`` and both stamps the caller's
    ``now``; a seeded player character the same."""

    _insert_world(conn, "w")
    _insert_actor(conn, "a1", "w")
    profile = cast.seed_actor_profile(
        "a1",
        "w",
        story_role=StoryRole.SUPPORTING,
        pov_eligible=False,
        pov_weight=2,
        long_term_drive="drive",
        current_arc_seed="arc",
        private_context="private",
        now=NOW,
    )
    assert isinstance(profile, Ok)
    assert profile.value.state_version == 1
    assert profile.value.created_at == profile.value.updated_at == NOW
    assert profile.value.story_role is StoryRole.SUPPORTING
    assert profile.value.pov_eligible is False
    assert profile.value.pov_weight == 2

    player = cast.seed_player_character(
        "pc-1",
        "w",
        name="You",
        background="bg",
        appearance="ap",
        abilities="ab",
        limits="li",
        location="lo",
        state="st",
        knowledge_refs="kr",
        now=NOW,
    )
    assert isinstance(player, Ok)
    assert player.value.state_version == 1
    assert player.value.name == "You"
    assert player.value.knowledge_refs == "kr"


def test_the_seed_faces_refuse_in_human_sentences(
    conn: sqlite3.Connection,
    cast: SqliteCastStore,
) -> None:
    """The refusal vocabulary's own sentences: a profile aimed at an
    actor that does not exist is ``NOT_FOUND``; one aimed at an actor
    bound to another world is ``VALIDATION_FAILED`` naming both ids;
    a nameless player character is ``VALIDATION_FAILED``; a dangling
    world under the player face is ``NOT_FOUND``."""

    _insert_world(conn, "w")
    _insert_world(conn, "w2")
    _insert_actor(conn, "a1", "w2")

    refused = cast.seed_actor_profile("a-nowhere", "w", now=NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND

    refused = cast.seed_actor_profile("a1", "w", now=NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "a1" in refused.error.message
    assert "w2" in refused.error.message

    refused = cast.seed_player_character("pc-1", "w", name="", now=NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    refused = cast.seed_player_character("pc-1", "w", name="   ", now=NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED

    refused = cast.seed_player_character("pc-1", "world-nowhere", name="You", now=NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND


def test_a_second_seed_under_one_world_answers_the_existing_row(
    conn: sqlite3.Connection,
    cast: SqliteCastStore,
) -> None:
    """The idempotence's world-keyed shape through the store's own
    surface: a second seed under a world that already holds its one
    player character — even under a **different id** — answers the
    stored row unchanged and writes nothing (the instance is the
    authority; the UNIQUE (world_id) storage law itself is pinned at
    the table level above)."""

    _insert_world(conn, "w")
    seeded = cast.seed_player_character("pc-1", "w", name="You", now=NOW)
    assert isinstance(seeded, Ok)
    replayed = cast.seed_player_character(
        "pc-2", "w", name="Other", now=LATER
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == seeded.value
    assert replayed.value.player_character_id == "pc-1"
    assert replayed.value.name == "You"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM world_player_character"
        ).fetchone()[0]
        == 1
    )


# ---------------------------------------------------------------------------
# 6. the participant namespace
# ---------------------------------------------------------------------------


def test_participant_namespace_is_a_pure_union() -> None:
    """The pure-function law (the V3-3R signature): the namespace is
    exactly the union of the two durable identity sources, ``None``
    and empty strings drop out (an empty word names nobody), and the
    result is order-free — two assemblies of the same town answer
    equal sets."""

    assert participant_namespace(
        actor_ids=["actor-a", "actor-b"],
        player_character_id="pc-1",
    ) == frozenset({"actor-a", "actor-b", "pc-1"})
    assert participant_namespace(
        actor_ids=["actor-a", "", "actor-a"],
        player_character_id=None,
    ) == frozenset({"actor-a"})
    assert participant_namespace(actor_ids=[]) == frozenset()
    assert participant_namespace(
        actor_ids=["actor-a"], player_character_id="actor-a"
    ) == frozenset({"actor-a"})


def test_the_end_to_end_assembly_answers_the_two_durable_identities(
    tmp_path: Path,
) -> None:
    """The THE ONE derivation over the real town (the V3-3R freeze's
    executable face): berrymoor seeded, the ``actor_id`` halves from
    ``actors_of`` ∪ the player id from the cast store assemble exactly
    the two durable identities — and the negative controls hold: the
    persona id (the CharacterCard / template identity, not a V3
    canonical world participant identity) and the package's resident
    names (no durable V3 participant identity yet) both stay out of
    the vocabulary."""

    _directory, store, cast_store, _db = _seed_berrymoor(tmp_path)
    player = cast_store.player_character(BERRYMOOR)
    namespace = participant_namespace(
        actor_ids=[
            str(record.actor_id)
            for record in store.actors_of(BERRYMOOR)
        ],
        player_character_id=(
            player.player_character_id if player is not None else None
        ),
    )
    assert namespace == BERRYMOOR_NAMESPACE
    # The freeze's negative controls: the persona id is the
    # CharacterCard / template identity, and the residents' names are
    # prose / scene material — neither is a V3 canonical world
    # participant identity.
    assert "persona-nell-alder" not in namespace
    assert "Old Tam" not in namespace


# ---------------------------------------------------------------------------
# 7. the package v8 wall
# ---------------------------------------------------------------------------


def _load(tmp_path: Path, payload: dict, name: str):
    """One load of one payload through the real loader."""

    directory = tmp_path / "loads"
    _write_world(directory, payload, name)
    return load_world_package(directory / name)


def test_v8_is_accepted_and_v7_v9_are_refused(tmp_path: Path) -> None:
    """The wall: v8 rides in; a v7 stamp and a v9 stamp are refused
    with the number in the message — an old file cannot ride in
    half-read, and a future version must be read by the cut that
    writes it."""

    payload = _minimal_payload()
    accepted = _load(tmp_path, payload, "v8.json")
    assert isinstance(accepted, Ok)
    assert accepted.value.version == 8

    for version in (7, 9):
        stamped = dict(payload)
        stamped["version"] = version
        refused = _load(tmp_path, stamped, f"v{version}.json")
        assert isinstance(refused, Err)
        assert "version must be 8" in refused.error.message
        assert f"got {version}" in refused.error.message


def test_the_shipped_package_is_v8_with_nells_six_keys(
    tmp_path: Path,
) -> None:
    """The shipped berrymoor: version 8, and Nell's six profile keys
    decoded verbatim into the member."""

    loaded = load_world_package(BUILTIN_WORLDS_DIR / "berrymoor.json")
    assert isinstance(loaded, Ok), loaded.error.message
    package = loaded.value
    assert package.version == WORLD_PACKAGE_VERSION == 8
    nell = package.cast[0]
    assert nell.name == "Nell Alder"
    assert nell.story_role == "PROTAGONIST"
    assert nell.pov_eligible is True
    assert nell.pov_weight == 1
    assert nell.long_term_drive == NELL_DRIVE
    assert nell.current_arc_seed == NELL_ARC
    assert nell.private_context == NELL_PRIVATE


def test_bad_profile_shapes_are_refused_one_by_one(tmp_path: Path) -> None:
    """The profile six's strict decode: a ``story_role`` outside the
    three canonical words, a non-bool ``pov_eligible`` (a JSON 1 is a
    number, not a bool), a negative or boolean ``pov_weight``, and a
    blank arc text — each refused with the offending key named."""

    accepted = _load(
        tmp_path,
        _minimal_payload()
        | {
            "cast": [
                {
                    "persona_id": "persona-nell-alder",
                    "name": "Nell",
                    "story_role": "PROTAGONIST",
                    "pov_eligible": False,
                    "pov_weight": 0,
                }
            ]
        },
        "ok.json",
    )
    assert isinstance(accepted, Ok)
    assert accepted.value.cast[0].story_role == "PROTAGONIST"
    assert accepted.value.cast[0].pov_eligible is False
    assert accepted.value.cast[0].pov_weight == 0

    for key, value in (
        ("story_role", "ADOPTED"),
        ("story_role", "protagonist"),
        ("pov_eligible", 1),
        ("pov_eligible", "yes"),
        ("pov_weight", -1),
        ("pov_weight", True),
        ("pov_weight", 1.5),
        ("long_term_drive", "   "),
        ("current_arc_seed", ""),
        ("private_context", None),
    ):
        payload = _minimal_payload()
        payload["cast"] = [
            {
                "persona_id": "persona-nell-alder",
                "name": "Nell",
                key: value,
            }
        ]
        refused = _load(tmp_path, payload, "bad.json")
        assert isinstance(refused, Err), (key, value)
        assert key in refused.error.message, (key, value)


# ---------------------------------------------------------------------------
# 8. the old world_actor zero-touch
# ---------------------------------------------------------------------------


def test_the_old_world_actor_chain_is_untouched(tmp_path: Path) -> None:
    """The §7.1 boundary: the seeded berrymoor's ``world_actor`` still
    carries exactly one row under the derived id
    (``actor-berrymoor-nell`` — the derivation law unchanged), the
    profile's FK rides that row, and no second actor appears."""

    _directory, store, cast_store, db = _seed_berrymoor(tmp_path)
    actors = store.actors_of(BERRYMOOR)
    assert [actor.actor_id for actor in actors] == ["actor-berrymoor-nell"]
    assert [str(actor.persona_id) for actor in actors] == [
        "persona-nell-alder"
    ]
    profile = cast_store.actor_profile("actor-berrymoor-nell")
    assert profile is not None
    assert profile.world_id == BERRYMOOR
    # The profile's FK rides the actor's own row: deleting the actor
    # is what the database refuses to allow while the profile stands
    # (the RESTRICT posture's own shape).
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "DELETE FROM world_actor WHERE actor_id ="
            " 'actor-berrymoor-nell'"
        )
    db.rollback()


def test_the_cast_modules_import_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline): a fresh interpreter
    importing the new module — and the package that now imports it —
    first must succeed; no import cycle may hide behind a lucky
    test-session order."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.world.cast, elc.world.package"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
