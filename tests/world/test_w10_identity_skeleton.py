"""W-1-0 — the World bounded context's identity skeleton (nine pin groups).

The living-world program's first cut (direction DEC-OPI-7e3744ee…2 — the
user's living-world mainline; the program's opening ruling
DEC-OPI-7e3744ee…4 R1–R9; M0.1 DEC-OPI-d96fd92d…7: AD-1 conservative
overlay, AD-5 the three identity tables land once). The slice VAL groups,
each a section below:

1. **migration pins** — 0023 is the registered head (the shared constants
   and the stamp a fresh database carries say 23), the three tables carry
   their columns, and the FK/UNIQUE declarations are read off the live
   schema through PRAGMA — including the composite FK
   ``(actor_id, world_id)`` that keeps a binding's actor inside its own
   world;
2. **create_world pins** — the same id replayed with the same shape is an
   ``Ok`` no-op (W-1-4's host seed sits on this), a same-id different
   shape is a ``CONFLICT``;
3. **bind_actor pins** — the same tuple replayed is a no-op, and the
   table's ``UNIQUE (world_id, persona_id)`` refuses a second actor for
   one persona in one world;
4. **bind_conversation pins** — the same tuple replayed is a no-op, a
   conversation already bound is refused (the column's UNIQUE — one
   conversation, one world), and the composite FK refuses an actor that
   belongs to another world;
5. **dangling-reference pins** — a missing template world, a missing
   persona card and a missing conversation each come back as value-
   semantics ``NOT_FOUND`` answers, never exceptions;
6. **host pins** — ``open_host`` builds the world store in both tiers
   (the world_lore always-built shape) and the store works over the real
   assembly; ``close()`` is clean;
7. **registry pins** — the three canonical objects are registered with
   ``OWNER_WORLD`` and the record classes import from the package;
8. **census pin** — the census table carries the ``world`` row and its
   declared face imports (the bidirectional on-disk pin lives in
   ``tests/architecture/test_surface_census.py`` itself);
9. **banner pin** — every ``elc.*`` symbol the package banner names
   imports (the prep-0 pin-8 shape, applied to the new package).
"""

from __future__ import annotations

import importlib
import re
import sqlite3
from pathlib import Path

import pytest

from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.registry import CANONICAL_OBJECTS, OWNER_WORLD
from elc.platform.types import Err
from elc.world.store import SqliteWorldStore
from elc.world.types import (
    WorldActorRecord,
    WorldConversationRecord,
    WorldRecord,
)
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "migrations"

NOW = "2026-10-05T00:00:00+00:00"

#: The penpal card's persona id (migration 0019's seed row carries it —
#: the persona FK target every bind_actor pin uses, real on a fresh db).
PENPAL_PERSONA_ID = "persona-nell-alder"

# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> SqliteWorldStore:
    """The world store over a fresh, fully migrated app.db — the
    connection carries the production profile's foreign-keys-ON (the
    dangling-reference refusals and the composite FK are the database's
    own, so the fixture must spell the same posture elc.platform.db
    .connection.connect does)."""

    conn = sqlite3.connect(tmp_path / "app.db")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    fence = open_runtime_epoch(conn)
    return SqliteWorldStore(conn, fence)


def _seed_persona_card(conn: sqlite3.Connection, persona_id: str) -> None:
    """One minimal character_card row — the persona FK target.

    The 0019 columns are NOT NULL across the board (the card's "not
    written yet" spelling is the empty string, never NULL), so the minimal
    honest row is empty strings plus the ids and the stamp.
    """

    conn.execute(
        "INSERT INTO character_card ("
        " character_id, persona_id, name, identity, personality, background,"
        " speech_style, \"values\", boundaries, opening, scenario,"
        " generation_policy, lore_refs, revision, status, is_builtin,"
        " created_at, updated_at"
        ") VALUES (?, ?, '', '', '', '', '', '', '', '', '', '', '[]',"
        " 1, 'ACTIVE', 0, ?, ?)",
        (f"card-for-{persona_id}", persona_id, NOW, NOW),
    )
    conn.commit()


def _seed_conversation(conn: sqlite3.Connection, conversation_id: str) -> None:
    """One minimal conversation row — the binding FK target."""

    conn.execute(
        "INSERT INTO conversation ("
        " conversation_id, persona_id, scene_id, created_at, status,"
        " next_turn_sequence, next_message_sequence"
        ") VALUES (?, NULL, NULL, ?, 'ACTIVE', 1, 1)",
        (conversation_id, NOW),
    )
    conn.commit()


def _seed_world(store: SqliteWorldStore, world_id: str = "world-main") -> None:
    result = store.create_world(world_id, "Berrymoor", None, NOW)
    assert result.value is not None


def _seed_actor(
    store: SqliteWorldStore,
    world_id: str = "world-main",
    actor_id: str = "actor-nell",
) -> None:
    result = store.bind_actor(actor_id, world_id, PENPAL_PERSONA_ID, NOW)
    assert result.value is not None


def _assert_err(result: object, code: str) -> None:
    assert isinstance(result, Err), result
    assert result.error.code == code, result.error
    assert isinstance(result.error.message, str) and result.error.message


# ---------------------------------------------------------------------------
# 1 — the migration
# ---------------------------------------------------------------------------


def test_0023_is_in_place_behind_the_head() -> None:
    """W-1-0's migration is in the chain — no longer the head: W-1-1's
    0024_world_events sits above it (the stamp-pin discipline every head
    move has followed since P8-4; the pin read "0023 is the head" while
    0023 was the head). The shared constants say so, and the stamp a
    fresh database carries is 24."""

    assert MIGRATION_IDS[-1] == "0024_world_events"
    assert MIGRATION_IDS[-2] == "0023_world_identity"
    assert SCHEMA_HEAD_FILE == "0024_world_events.sql"
    assert (MIGRATIONS / SCHEMA_HEAD_FILE).is_file()
    assert (MIGRATIONS / "0023_world_identity.sql").is_file()
    assert SCHEMA_HEAD_VERSION == "24"

    conn = sqlite3.connect(":memory:")
    applied = apply_migrations(conn)
    assert applied[-1] == "0024_world_events"
    assert applied[-2] == "0023_world_identity"
    assert schema_version(conn) == "24"


def test_the_three_tables_carry_their_columns() -> None:
    """The physical column set, in order — the adjudication's own spelling
    (M0.1 AD-5), column for column."""

    conn = sqlite3.connect(":memory:")
    apply_migrations(conn)
    expected = {
        "world": ["world_id", "name", "template_world_id", "created_at"],
        "world_actor": ["actor_id", "world_id", "persona_id", "created_at"],
        "world_conversation": [
            "binding_id",
            "world_id",
            "actor_id",
            "conversation_id",
            "created_at",
        ],
    }
    for table, columns in expected.items():
        read = [
            str(row[1])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        assert read == columns, (table, read)


def test_the_fk_and_unique_declarations_are_real() -> None:
    """The declared relationships, read off the live schema: every FK
    (including the composite ``(actor_id, world_id)`` one) and every
    UNIQUE is what the migration spells — a constraint deleted from the
    file cannot pass this pin."""

    conn = sqlite3.connect(":memory:")
    apply_migrations(conn)

    world_fks = {
        (str(row[2]), str(row[3]), str(row[4]))
        for row in conn.execute("PRAGMA foreign_key_list(world)").fetchall()
    }
    # (table, from, to): the fork lineage points at the world table itself.
    assert ("world", "template_world_id", "world_id") in world_fks

    actor_fks = {
        (str(row[2]), str(row[3]), str(row[4]))
        for row in conn.execute("PRAGMA foreign_key_list(world_actor)").fetchall()
    }
    assert ("world", "world_id", "world_id") in actor_fks
    assert ("character_card", "persona_id", "persona_id") in actor_fks

    conversation_fks = {
        (str(row[2]), str(row[3]), str(row[4]))
        for row in conn.execute(
            "PRAGMA foreign_key_list(world_conversation)"
        ).fetchall()
    }
    # The composite FK: the parent key is (actor_id, world_id) — PRAGMA
    # spells it one row per column, same FK id, sequenced.
    composite = sorted(
        (str(row[3]), str(row[4]))
        for row in conn.execute(
            "PRAGMA foreign_key_list(world_conversation)"
        ).fetchall()
        if str(row[2]) == "world_actor"
    )
    assert composite == [("actor_id", "actor_id"), ("world_id", "world_id")]
    assert ("conversation", "conversation_id", "conversation_id") in conversation_fks

    # The UNIQUEs: world_actor carries (world_id, persona_id) and
    # (actor_id, world_id); world_conversation carries conversation_id.
    # PRAGMA index_list's origin column spells the provenance: 'u' is a
    # UNIQUE constraint, 'pk' is the primary key — the pin reads only 'u'
    # (the PK's autoindex is not a UNIQUE declaration).
    def _unique_columns(table: str) -> set[tuple[str, ...]]:
        uniques: set[tuple[str, ...]] = set()
        for row in conn.execute(f"PRAGMA index_list({table})").fetchall():
            if str(row[3]) != "u":  # origin: 'u' = UNIQUE constraint
                continue
            cols = [
                str(idx[2])
                for idx in conn.execute(
                    f"PRAGMA index_info({str(row[1])})"
                ).fetchall()
            ]
            uniques.add(tuple(cols))
        return uniques

    assert _unique_columns("world_actor") == {
        ("world_id", "persona_id"),
        ("actor_id", "world_id"),
    }
    assert ("conversation_id",) in _unique_columns("world_conversation")


# ---------------------------------------------------------------------------
# 2 — create_world
# ---------------------------------------------------------------------------


def test_create_world_replays_idempotently(store: SqliteWorldStore) -> None:
    """The same id with the same shape answers the stored row unchanged —
    twice (a re-open re-seed is the consumer shape, W-1-4)."""

    first = store.create_world("world-main", "Berrymoor", None, NOW)
    second = store.create_world("world-main", "Berrymoor", None, NOW)
    third = store.create_world(
        "world-main", "Berrymoor", None, "2999-01-01T00:00:00+00:00"
    )
    assert isinstance(first.value, WorldRecord)
    assert second.value == first.value
    # The stamp rides the first write; a replay's differing clock changes
    # nothing — the idempotence is by identity shape (name + template),
    # which is what makes re-seeding safe.
    assert third.value == first.value
    assert store.get_world("world-main") == first.value
    assert [w.world_id for w in store.list_worlds()] == ["world-main"]


def test_create_world_conflicts_on_a_different_shape(
    store: SqliteWorldStore,
) -> None:
    """A same-id different-shape call is a CONFLICT — worlds do not rename
    or re-parent through the create face — and a fork with a real parent
    lands (the lineage column works end to end)."""

    _seed_world(store, "world-root")
    forked = store.create_world("world-fork", "Harbour", "world-root", NOW)
    assert isinstance(forked.value, WorldRecord)
    assert forked.value.template_world_id == "world-root"

    _assert_err(
        store.create_world("world-fork", "Renamed", "world-root", NOW),
        "CONFLICT",
    )
    # Same name, template dropped — a different shape is still a conflict.
    _assert_err(
        store.create_world("world-fork", "Harbour", None, NOW),
        "CONFLICT",
    )


# ---------------------------------------------------------------------------
# 3 — bind_actor
# ---------------------------------------------------------------------------


def test_bind_actor_replays_idempotently(store: SqliteWorldStore) -> None:
    _seed_world(store)
    first = store.bind_actor("actor-nell", "world-main", PENPAL_PERSONA_ID, NOW)
    second = store.bind_actor("actor-nell", "world-main", PENPAL_PERSONA_ID, NOW)
    assert isinstance(first.value, WorldActorRecord)
    assert second.value == first.value
    assert [a.actor_id for a in store.actors_of("world-main")] == ["actor-nell"]


def test_bind_actor_unique_refuses_a_second_actor_for_one_persona(
    store: SqliteWorldStore,
) -> None:
    """One card speaks as at most one actor per world (the table's
    UNIQUE) — the refusal is the database's own, surfaced as CONFLICT."""

    _seed_world(store)
    _seed_actor(store)
    _assert_err(
        store.bind_actor("actor-echo", "world-main", PENPAL_PERSONA_ID, NOW),
        "CONFLICT",
    )
    # A same-id different-shape replay conflicts too.
    _assert_err(
        store.bind_actor("actor-nell", "world-main", "persona-other", NOW),
        "CONFLICT",
    )


# ---------------------------------------------------------------------------
# 4 — bind_conversation
# ---------------------------------------------------------------------------


def test_bind_conversation_replays_idempotently(
    store: SqliteWorldStore, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_path / "app.db")
    _seed_world(store)
    _seed_actor(store)
    _seed_conversation(conn, "conv-1")
    first = store.bind_conversation(
        "binding-1", "world-main", "actor-nell", "conv-1", NOW
    )
    second = store.bind_conversation(
        "binding-1", "world-main", "actor-nell", "conv-1", NOW
    )
    assert isinstance(first.value, WorldConversationRecord)
    assert second.value == first.value
    assert [b.binding_id for b in store.conversations_of("world-main")] == [
        "binding-1"
    ]


def test_bind_conversation_refuses_rebinding_one_conversation(
    store: SqliteWorldStore, tmp_path: Path
) -> None:
    """One conversation binds to at most one world: a second binding —
    through any actor — is refused (the column's UNIQUE, surfaced as
    CONFLICT)."""

    conn = sqlite3.connect(tmp_path / "app.db")
    _seed_world(store)
    _seed_actor(store)
    _seed_conversation(conn, "conv-1")
    bound = store.bind_conversation(
        "binding-1", "world-main", "actor-nell", "conv-1", NOW
    )
    assert bound.value is not None
    _assert_err(
        store.bind_conversation(
            "binding-2", "world-main", "actor-nell", "conv-1", NOW
        ),
        "CONFLICT",
    )


def test_bind_conversation_refuses_an_actor_of_another_world(
    store: SqliteWorldStore, tmp_path: Path
) -> None:
    """The composite FK keeps a binding's actor inside its own world: an
    actor that exists but belongs to another world is refused — never
    stored (the pairing, not the identity, is what fails)."""

    conn = sqlite3.connect(tmp_path / "app.db")
    _seed_world(store, "world-main")
    _seed_world(store, "world-other")
    _seed_actor(store, "world-main", "actor-nell")
    _seed_conversation(conn, "conv-2")
    _assert_err(
        store.bind_conversation(
            "binding-x", "world-other", "actor-nell", "conv-2", NOW
        ),
        "CONFLICT",
    )


# ---------------------------------------------------------------------------
# 5 — dangling references
# ---------------------------------------------------------------------------


def test_dangling_references_are_value_semantics_refusals(
    store: SqliteWorldStore,
) -> None:
    """The three NOT_FOUND targets: a template world that does not exist,
    a persona card that does not exist, a conversation that does not
    exist — each comes back as an ``Err`` answer, never an exception (and
    nothing is half-written)."""

    _seed_world(store)
    _seed_actor(store)

    _assert_err(
        store.create_world("world-orphan", "Nowhere", "world-absent", NOW),
        "NOT_FOUND",
    )
    _assert_err(
        store.bind_actor("actor-orphan", "world-absent", PENPAL_PERSONA_ID, NOW),
        "NOT_FOUND",
    )
    _assert_err(
        store.bind_actor("actor-orphan", "world-main", "persona-absent", NOW),
        "NOT_FOUND",
    )
    _assert_err(
        store.bind_conversation(
            "binding-orphan", "world-main", "actor-nell", "conv-absent", NOW
        ),
        "NOT_FOUND",
    )
    # The refusals wrote nothing.
    assert store.get_world("world-orphan") is None
    assert [a.actor_id for a in store.actors_of("world-main")] == ["actor-nell"]
    assert store.conversations_of("world-main") == ()


# ---------------------------------------------------------------------------
# 6 — the host
# ---------------------------------------------------------------------------


def test_open_host_builds_the_world_store(tmp_path: Path) -> None:
    """The identity store is assembled with the rest of the prep-1 tier
    (the world_lore always-built shape — the store needs only the shared
    connection and fence, so the full chain's tier builds it by the same
    construction), works over the real assembly, and the host closes
    cleanly. No seeding: a fresh host opens with zero worlds."""

    host = open_host(tmp_path / "app.db", provider=ScriptedPersonaProvider())
    try:
        assert host.world_store is not None
        assert isinstance(host.world_store, SqliteWorldStore)
        assert host.world_store.list_worlds() == ()
        bound = host.world_store.create_world("world-host", "Host", None, NOW)
        assert bound.value is not None
        assert host.world_store.get_world("world-host") == bound.value
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 7 — the registry
# ---------------------------------------------------------------------------


def test_the_registry_carries_the_three_world_objects() -> None:
    """Three canonical objects, one owner word, the record classes as the
    schemas — no version_field anywhere (identity rows carry none)."""

    assert OWNER_WORLD == "world"
    for key, schema in (
        ("world", WorldRecord),
        ("world_actor", WorldActorRecord),
        ("world_conversation", WorldConversationRecord),
    ):
        entry = CANONICAL_OBJECTS[key]
        assert entry.owner == OWNER_WORLD, key
        assert entry.schema is schema, key
        assert entry.version_field is None, key


def test_the_record_classes_import_from_the_package() -> None:
    """The package exports the store and the three record shapes, and the
    registry's schemas ARE those exported classes."""

    package = importlib.import_module("elc.world")
    for name in (
        "SqliteWorldStore",
        "WorldRecord",
        "WorldActorRecord",
        "WorldConversationRecord",
    ):
        assert getattr(package, name) is not None, name


# ---------------------------------------------------------------------------
# 8 — the census
# ---------------------------------------------------------------------------


def test_the_census_row_covers_the_world_package() -> None:
    """The census table carries the ``world`` row and its declared face
    imports (the row cannot outlive the package, and the package cannot
    appear without the row — the bidirectional pin in
    test_surface_census.py holds that against the disk; this pin names the
    row itself so deleting it is a local RED)."""

    from tests.architecture.test_surface_census import SURFACE_CENSUS

    rows = [row for row in SURFACE_CENSUS if row.package == "world"]
    assert len(rows) == 1
    row = rows[0]
    assert row.live_face == "elc.world.store:SqliteWorldStore"
    assert row.store == row.live_face
    module_name, _, attr = (row.live_face or "").partition(":")
    assert getattr(importlib.import_module(module_name), attr) is SqliteWorldStore


# ---------------------------------------------------------------------------
# 9 — the banner
# ---------------------------------------------------------------------------


def test_the_package_banner_names_only_importable_symbols() -> None:
    """Every ``elc.*`` symbol the package banner spells imports (the
    prep-0 pin-8 shape, applied to the new package: a broken pointer in
    the text whose whole job is "use this face" cannot ship)."""

    banner = REPO / "src" / "elc" / "world" / "__init__.py"
    tokens = sorted(
        set(
            re.findall(
                r"elc(?:\.[A-Za-z_][A-Za-z0-9_]*)+(?::[A-Za-z_][A-Za-z0-9_]*)?",
                banner.read_text(encoding="utf-8"),
            )
        )
    )
    assert tokens, "the banner names no elc.* symbol at all"
    for token in tokens:
        if ":" in token:
            module_name, _, attr = token.partition(":")
            assert getattr(importlib.import_module(module_name), attr) is not None, (
                token
            )
        else:
            module_name, _, last = token.rpartition(".")
            if last[:1].isupper():
                assert getattr(importlib.import_module(module_name), last), token
            else:
                importlib.import_module(token)
