"""W-1-1 — the World bounded context's event tree and its minimal state
projection (ten pin groups).

The living-world program's second cut (the adjudication chain
DEC-OPI-7e3744ee…17; M0.1 AD-3R — the static lore keeps its own table,
the living state lives here, two tables; AD-2 — no model face, narration
arrives as the caller's string). The slice VAL groups, each a section
below:

1. **migration pins** — 0024 is in the chain behind W-1-2's 0025 head
   (the shared constants and the stamp a fresh database carries say 25)
   and the two tables carry their columns, in order;
2. **declaration pins** — the FKs, the one index, the ``status`` CHECK,
   the absence of any UNIQUE on the key and the RESTRICT posture (no ON
   DELETE anywhere), all read off the live schema through PRAGMA;
3. **record_event atomic projection** — one call lands the chronicle
   entry *and* its CURRENT settlement rows together (fact id derived as
   ``<event_id>:<key>``, ``recorded_at`` = the event's own
   ``occurred_at``);
4. **the supersede chain** — a second event on one key flips the older
   CURRENT fact to SUPERSEDED and the history reads oldest-first;
5. **idempotence** — the same event replayed is a whole-face no-op
   (neither the entry nor its settlement is redone), and a replayed id
   with a different shape is a ``CONFLICT``;
6. **pure narration** — an empty effects tuple lands the event with zero
   settlement rows;
7. **the refusals** — one event cannot carry one key twice (nothing
   written), an unknown world is a ``NOT_FOUND`` (nothing written);
8. **the effects codec** — bad JSON / non-array / missing-or-non-string
   fields each refused with the discriminating word, the round trip is
   exact, and the chronicle answers a hand-corrupted column with a
   value-semantics ``Err`` (never an exception);
9. **the registration** — six canonical objects under ``OWNER_WORLD``
   (no version field) and seven ``GLOBAL_CONTENT_TABLES`` members (zero
   sweep face);
10. **N-W10-6 regression** — ``create_world``'s refusal no longer blames
    the template for every database failure: the FK refusal keeps the
    template ``NOT_FOUND``, any other failure answers the storage word.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.deletion.types import GLOBAL_CONTENT_TABLES, RETAINED_TABLES, SWEPT_TABLES
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.registry import CANONICAL_OBJECTS, OWNER_WORLD
from elc.platform.types import Err
from elc.world.engine.types import WorldRunRecord
from elc.world.store import SqliteWorldStore
from elc.world.types import (
    StateEffect,
    WorldEvent,
    WorldRecord,
    WorldStateFact,
    decode_effects,
    encode_effects,
)
from tests.conftest import MIGRATION_IDS, SCHEMA_HEAD_FILE, SCHEMA_HEAD_VERSION

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "migrations"

NOW = "2026-10-05T00:00:00+00:00"
LATER = "2026-10-05T09:30:00+00:00"
EARLIER = "2026-10-04T08:00:00+00:00"


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection with the production
    foreign-keys-ON profile — the dangling-world refusal below is the
    database's own FK (backstopping the store's pre-check), so the
    fixture must spell the posture elc.platform.db.connection.connect
    does."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _seed_world(store: SqliteWorldStore, world_id: str = "world-main") -> None:
    result = store.create_world(world_id, "Berrymoor", None, NOW)
    assert result.value is not None


def _event(
    event_id: str,
    world_id: str = "world-main",
    occurred_at: str = NOW,
    effects: tuple[StateEffect, ...] = (),
    kind: str = "world_turn",
    narration: str = "the bell rings over Berrymoor",
    source: str = "test",
) -> WorldEvent:
    return WorldEvent(
        event_id=event_id,
        world_id=world_id,
        kind=kind,
        narration=narration,
        effects=effects,
        occurred_at=occurred_at,
        source=source,
    )


def _assert_err(result: object, code: str) -> None:
    assert isinstance(result, Err), result
    assert result.error.code == code, result.error
    assert isinstance(result.error.message, str) and result.error.message


# ---------------------------------------------------------------------------
# 1 — the migration
# ---------------------------------------------------------------------------


def test_0025_is_the_registered_head() -> None:
    """W-1-1's migration is in the chain, behind W-1-2's 0025_world_runs
    and W-1-3's 0026_world_reveal (the stamp-pin discipline every head
    move has
    followed since P8-4; the pin read "0024 is the head" while 0024 was
    the head); the shared constants say so, and the stamp a fresh
    database carries is 26."""

    assert MIGRATION_IDS[-1] == "0026_world_reveal"
    assert MIGRATION_IDS[-2] == "0025_world_runs"
    assert SCHEMA_HEAD_FILE == "0026_world_reveal.sql"
    assert (MIGRATIONS / SCHEMA_HEAD_FILE).is_file()
    assert SCHEMA_HEAD_VERSION == "26"

    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0026_world_reveal"
    assert applied[-2] == "0025_world_runs"
    assert schema_version(fresh) == "26"


def test_the_two_tables_carry_their_columns() -> None:
    """The physical column set, in order — the adjudication's own
    spelling, column for column."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    expected = {
        "world_event": [
            "event_id",
            "world_id",
            "kind",
            "narration",
            "effects",
            "occurred_at",
            "source",
        ],
        "world_state_fact": [
            "fact_id",
            "world_id",
            "source_event_id",
            "canonical_key",
            "statement",
            "status",
            "recorded_at",
        ],
    }
    for table, columns in expected.items():
        read = [
            str(row[1])
            for row in fresh.execute(f"PRAGMA table_info({table})").fetchall()
        ]
        assert read == columns, (table, read)


# ---------------------------------------------------------------------------
# 2 — the declarations, read off the live schema
# ---------------------------------------------------------------------------


def test_the_fk_index_check_and_restrict_declarations_are_real() -> None:
    """Every declared relationship and refusal: the two tables' FKs (both
    pointing at real parents), the one settlement index, the ``status``
    CHECK, no UNIQUE on the key (several rows per key are the design),
    and the RESTRICT posture (NO ACTION delete rule, the 0023
    convention)."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)

    event_fks = {
        (str(row[2]), str(row[3]), str(row[4]), str(row[6]))
        for row in fresh.execute("PRAGMA foreign_key_list(world_event)").fetchall()
    }
    assert event_fks == {("world", "world_id", "world_id", "NO ACTION")}

    fact_fks = {
        (str(row[2]), str(row[3]), str(row[4]), str(row[6]))
        for row in fresh.execute(
            "PRAGMA foreign_key_list(world_state_fact)"
        ).fetchall()
    }
    assert fact_fks == {
        ("world", "world_id", "world_id", "NO ACTION"),
        ("world_event", "source_event_id", "event_id", "NO ACTION"),
    }

    # The one index serves the CURRENT read and the history walk; it is a
    # plain 'c'-origin index (created), not a UNIQUE constraint.
    indexed = [
        (str(idx[2]),)
        for row in fresh.execute(
            "PRAGMA index_list(world_state_fact)"
        ).fetchall()
        if str(row[3]) == "c"
        for idx in fresh.execute(f"PRAGMA index_info({str(row[1])})").fetchall()
    ]
    assert ("world_id",) in indexed[:1]
    index_columns = []
    for row in fresh.execute("PRAGMA index_list(world_state_fact)").fetchall():
        if str(row[3]) != "c":
            continue
        cols = [
            str(info[2])
            for info in fresh.execute(f"PRAGMA index_info({str(row[1])})").fetchall()
        ]
        index_columns.append(tuple(cols))
    assert index_columns == [("world_id", "canonical_key", "status")]

    # And the PK autoindex is the only 'u'-origin index — no UNIQUE on
    # (world_id, canonical_key): the superseded history is the design.
    uniques = []
    for row in fresh.execute("PRAGMA index_list(world_state_fact)").fetchall():
        if str(row[3]) != "u":
            continue
        cols = [
            str(info[2])
            for info in fresh.execute(f"PRAGMA index_info({str(row[1])})").fetchall()
        ]
        uniques.append(tuple(cols))
    assert uniques == []

    # The CHECK: a status outside the two words is refused by the schema
    # itself (write one event first — the settlement FK needs it).
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    from elc.platform.db.epoch import open_runtime_epoch as _open

    world_store = SqliteWorldStore(conn, _open(conn))
    seeded = world_store.create_world("w", "W", None, NOW)
    assert seeded.value is not None
    landed = world_store.record_event(
        _event("e-check", "w", effects=(StateEffect("k", "s"),))
    )
    assert landed.value is not None
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO world_state_fact ("
            " fact_id, world_id, source_event_id, canonical_key,"
            " statement, status, recorded_at"
            ") VALUES ('f-x', 'w', 'e-check', 'k', 's', 'PENDING', ?)",
            (NOW,),
        )


# ---------------------------------------------------------------------------
# 3 — record_event: the atomic projection
# ---------------------------------------------------------------------------


def test_record_event_lands_event_and_current_facts_together(
    store: SqliteWorldStore,
) -> None:
    """One call, one face: the chronicle entry and its CURRENT settlement
    rows land together — the fact id is derived from the event, and the
    fact's clock is the event's own."""

    _seed_world(store)
    event = _event(
        "e-1",
        effects=(
            StateEffect("weather", "rain sweeps the harbour"),
            StateEffect("bell", "the chapel bell is cracked"),
        ),
    )
    result = store.record_event(event)
    assert result.value == event

    chronicle = store.chronicle_of("world-main")
    assert chronicle.value is not None and len(chronicle.value) == 1
    assert chronicle.value[0] == event

    current = store.current_facts("world-main")
    assert [f.canonical_key for f in current] == ["bell", "weather"]
    assert all(f.status == "CURRENT" for f in current)
    assert all(f.source_event_id == "e-1" for f in current)
    assert all(f.recorded_at == NOW for f in current)
    by_key = {f.canonical_key: f for f in current}
    assert by_key["bell"].fact_id == "e-1:bell"
    assert by_key["bell"].statement == "the chapel bell is cracked"
    assert by_key["weather"].fact_id == "e-1:weather"
    assert by_key["weather"].statement == "rain sweeps the harbour"


def test_two_events_on_one_key_chain_the_supersede(
    store: SqliteWorldStore,
) -> None:
    """A second event on one key flips the older CURRENT fact to
    SUPERSEDED; the history reads oldest-first with both rows honestly
    labelled, and the CURRENT read answers only the newest."""

    _seed_world(store)
    first = store.record_event(
        _event("e-1", occurred_at=NOW, effects=(StateEffect("weather", "fog"),))
    )
    second = store.record_event(
        _event(
            "e-2", occurred_at=LATER, effects=(StateEffect("weather", "clear skies"),)
        )
    )
    assert first.value is not None and second.value is not None

    current = store.current_facts("world-main")
    assert len(current) == 1
    assert current[0].fact_id == "e-2:weather"
    assert current[0].statement == "clear skies"
    assert current[0].status == "CURRENT"

    history = store.fact_history("world-main", "weather")
    assert [(f.fact_id, f.status, f.source_event_id) for f in history] == [
        ("e-1:weather", "SUPERSEDED", "e-1"),
        ("e-2:weather", "CURRENT", "e-2"),
    ]
    # The superseded row keeps its own story: its recorded_at is its
    # source event's occurred_at, not the supersede moment.
    assert history[0].recorded_at == NOW
    assert history[0].statement == "fog"


# ---------------------------------------------------------------------------
# 4 — idempotence
# ---------------------------------------------------------------------------


def test_replaying_the_same_event_is_a_whole_face_noop(
    store: SqliteWorldStore,
) -> None:
    """The same event replayed answers the stored event unchanged, and
    neither the chronicle entry nor its settlement is redone."""

    _seed_world(store)
    event = _event("e-1", effects=(StateEffect("weather", "fog"),))
    first = store.record_event(event)
    assert first.value == event

    replay = store.record_event(event)
    assert replay.value == event
    assert len(store.chronicle_of("world-main").value or ()) == 1
    assert len(store.current_facts("world-main")) == 1
    assert len(store.fact_history("world-main", "weather")) == 1


def test_a_replayed_id_with_a_different_shape_conflicts(
    store: SqliteWorldStore,
) -> None:
    """Events are append-only: the same id with a different shape is a
    CONFLICT, never a rewrite."""

    _seed_world(store)
    first = store.record_event(_event("e-1", narration="one story"))
    assert first.value is not None
    _assert_err(
        store.record_event(_event("e-1", narration="another story")), "CONFLICT"
    )
    _assert_err(
        store.record_event(
            _event("e-1", narration="one story", effects=(StateEffect("k", "s"),))
        ),
        "CONFLICT",
    )


# ---------------------------------------------------------------------------
# 5 — pure narration
# ---------------------------------------------------------------------------


def test_a_pure_narration_event_lands_without_settlement(
    store: SqliteWorldStore,
) -> None:
    """An empty effects tuple is legal: the chronicle entry lands, zero
    settlement rows."""

    _seed_world(store)
    result = store.record_event(_event("e-quiet"))
    assert result.value is not None
    chronicle = store.chronicle_of("world-main")
    assert chronicle.value is not None and len(chronicle.value) == 1
    assert chronicle.value[0].effects == ()
    assert store.current_facts("world-main") == ()
    assert store.fact_history("world-main", "weather") == ()


# ---------------------------------------------------------------------------
# 6 — the refusals
# ---------------------------------------------------------------------------


def test_one_event_cannot_carry_one_key_twice(store: SqliteWorldStore) -> None:
    """A duplicated canonical key inside one event is a
    ``VALIDATION_FAILED`` — and the whole face refuses before anything is
    written (zero half-write)."""

    _seed_world(store)
    _assert_err(
        store.record_event(
            _event(
                "e-dup",
                effects=(
                    StateEffect("weather", "fog"),
                    StateEffect("weather", "rain"),
                ),
            )
        ),
        "VALIDATION_FAILED",
    )
    assert store.chronicle_of("world-main").value == ()
    assert store.current_facts("world-main") == ()


def test_an_event_for_an_unknown_world_is_refused(store: SqliteWorldStore) -> None:
    """A dangling ``world_id`` is a ``NOT_FOUND`` (the table's FK is the
    backstop) — and nothing is written."""

    _seed_world(store)
    _assert_err(
        store.record_event(_event("e-orphan", world_id="world-absent")), "NOT_FOUND"
    )
    chronicle = store.chronicle_of("world-main")
    assert chronicle.value == ()
    assert store.current_facts("world-main") == ()


# ---------------------------------------------------------------------------
# 7 — the effects codec
# ---------------------------------------------------------------------------


def test_decode_effects_refuses_each_bad_payload() -> None:
    """The strict codec: bad JSON, a non-array payload, and elements
    missing a field or carrying a non-string each come back as a
    ``VALIDATION_FAILED`` whose message names the reason."""

    for bad, word in (
        ("not json at all{", "not valid JSON"),
        ('"just a string"', "not a JSON array"),
        ('{"key": "k", "statement": "s"}', "not a JSON array"),
        ('[{"statement": "s"}]', "missing 'key'"),
        ('[{"key": "k"}]', "missing 'statement'"),
        ('[{"key": 1, "statement": "s"}]', "is not a string"),
        ('[{"key": "k", "statement": 2}]', "is not a string"),
        ('[{"key": "k", "statement": "s", "extra": 1}]', "unexpected fields"),
        ("[]", None),  # the legal empty array — no refusal
    ):
        decoded = decode_effects(bad)
        if word is None:
            assert decoded.value == ()
        else:
            assert isinstance(decoded, Err), (bad, decoded)
            assert word in decoded.error.message, (bad, decoded.error.message)


def test_the_effects_round_trip_is_exact_and_deterministic() -> None:
    """encode → decode answers the tuple unchanged, and the same tuple
    always encodes to the same bytes (a replay writes what the first
    write wrote)."""

    effects = (
        StateEffect("weather", "rain sweeps the harbour"),
        StateEffect("bell", "钟楼的声音哑了"),
    )
    text = encode_effects(effects)
    assert text == encode_effects(effects)
    decoded = decode_effects(text)
    assert decoded.value == effects


def test_chronicle_refuses_a_hand_corrupted_effects_column(
    store: SqliteWorldStore, conn: sqlite3.Connection
) -> None:
    """A corrupted ``effects`` column (writable only by bypassing the
    store) is a value-semantics ``Err`` naming the offending event —
    never an exception, never a silently-decoded fact."""

    _seed_world(store)
    landed = store.record_event(
        _event("e-1", effects=(StateEffect("weather", "fog"),))
    )
    assert landed.value is not None
    conn.execute("UPDATE world_event SET effects = '{{not json' WHERE event_id = 'e-1'")
    conn.commit()
    chronicle = store.chronicle_of("world-main")
    _assert_err(chronicle, "VALIDATION_FAILED")
    assert "e-1" in chronicle.error.message


# ---------------------------------------------------------------------------
# 8 — the three read faces, in their durable orders
# ---------------------------------------------------------------------------


def test_the_three_read_faces_are_deterministic(store: SqliteWorldStore) -> None:
    """The chronicle reads by (occurred_at, event_id), the CURRENT facts
    by key, one key's history by (recorded_at, fact_id); unknown worlds
    read as empty, not as errors."""

    _seed_world(store)
    # Insert out of order: e-2 is later in time, e-a/e-b share a moment
    # (the id breaks the tie).
    for args in (
        ("e-2", LATER),
        ("e-b", NOW),
        ("e-a", NOW),
        ("e-1", EARLIER),
    ):
        landed = store.record_event(
            _event(args[0], occurred_at=args[1], kind="tick")
        )
        assert landed.value is not None

    chronicle = store.chronicle_of("world-main")
    assert chronicle.value is not None
    assert [e.event_id for e in chronicle.value] == ["e-1", "e-a", "e-b", "e-2"]

    # Two keys settled in scrambled order read key-ascending.
    assert store.record_event(
        _event("e-z", effects=(StateEffect("z-key", "z"),))
    ).value is not None
    assert store.record_event(
        _event("e-y", effects=(StateEffect("a-key", "a"),))
    ).value is not None
    assert [f.canonical_key for f in store.current_facts("world-main")] == [
        "a-key",
        "z-key",
    ]
    # History: the recorded_at rides the source event's occurred_at, the
    # fact id breaks ties.
    a_history = store.fact_history("world-main", "a-key")
    assert [f.fact_id for f in a_history] == ["e-y:a-key"]

    # Unknown worlds: empty reads, value semantics (never exceptions).
    empty = store.chronicle_of("world-absent")
    assert empty.value == ()
    assert store.current_facts("world-absent") == ()
    assert store.fact_history("world-absent", "weather") == ()


# ---------------------------------------------------------------------------
# 9 — the registration
# ---------------------------------------------------------------------------


def test_the_registry_carries_the_six_world_objects() -> None:
    """Six canonical objects under ``OWNER_WORLD`` — the three identity
    rows, W-1-1's event and fact, and W-1-2's run — each schema'd by the
    exported record class and carrying no version field (append-first
    rows; the projection's lifecycle lives in the row, not in a version
    column; ``state_version`` is not a canonical version spelling)."""

    assert OWNER_WORLD == "world"
    for key, schema in (
        ("world", WorldRecord),
        ("world_actor", None),
        ("world_conversation", None),
        ("world_event", WorldEvent),
        ("world_state_fact", WorldStateFact),
        ("world_run", WorldRunRecord),
    ):
        entry = CANONICAL_OBJECTS[key]
        assert entry.owner == OWNER_WORLD, key
        assert entry.version_field is None, key
        if schema is not None:
            assert entry.schema is schema, key


def test_global_content_tables_carry_the_seven_members() -> None:
    """W-1-1's two tables and W-1-2's run row joined the keep half
    (SEC-025's conservative reading) and W-1-3's reveal queue joins it the
    same way, while W-1-3's deletion face moves ``world_conversation``
    into the conversation scope's sweep: still seven members, and the
    classification is registration — no sweep walks the world-owned half,
    nothing keeps it as retained either."""

    assert GLOBAL_CONTENT_TABLES == (
        "world_lore_fact",
        "world",
        "world_actor",
        "world_event",
        "world_state_fact",
        "world_run",
        "world_reveal_item",
    )
    for table in ("world_event", "world_state_fact", "world_run",
                  "world_reveal_item"):
        assert table not in SWEPT_TABLES
        assert table not in RETAINED_TABLES


# ---------------------------------------------------------------------------
# 10 — N-W10-6: create_world's narrowed attribution
# ---------------------------------------------------------------------------


def test_create_world_no_longer_blames_the_template_for_every_failure(
    store: SqliteWorldStore,
) -> None:
    """The FK refusal keeps its template ``NOT_FOUND`` (the message names
    the template); any *other* database failure answers the storage word
    (``DEPENDENCY_UNAVAILABLE``, world_lore's precedent) with the raw
    error riding the message — never re-attributed to the template."""

    _seed_world(store, "world-root")
    # The FK arm: a dangling template is still the template's NOT_FOUND.
    result = store.create_world("world-orphan", "Nowhere", "world-absent", NOW)
    _assert_err(result, "NOT_FOUND")
    assert result.error is not None
    assert "template" in result.error.message

    # The residual arm, triggered deterministically: a caller-side NOT
    # NULL refusal (the name column) is not a template problem.
    broken = store.create_world("world-x", None, None, NOW)  # type: ignore[arg-type]
    _assert_err(broken, "DEPENDENCY_UNAVAILABLE")
    assert "NOT NULL constraint failed" in broken.error.message
    assert "template world does not exist" not in broken.error.message
    assert store.get_world("world-x") is None
