"""W-1-3 — the reveal queue, the communication orchestration and the
inbox's durable half (the ten pin groups).

The living-world program's fifth cut (the adjudication chain
DEC-OPI-7e3744ee…49; the spec §4.1 dual start + §4.2 checkpoint
semantics — 揭示是呈现触发非运转动力; AD-1's conservative overlay: the
conversation pipeline's write face is untouched). The slice VAL groups,
each a section below:

1. **migration pins** — 0026 is the registered head, the
   ``world_reveal_item`` table carries its columns in order, and the
   schema's own declarations hold: the three FKs, the CHECK vocabulary,
   the index, the double ``'26'`` stamp and the RESTRICT posture;
2. **run_step's dual triggers** — the letter winds the first run
   (seed = the world's run count, deterministic; the triggering turn
   rides the row), a letter after a finished run winds the next one
   (the engine no longer pauses mid-run — A2R DEC-…99 — so the resume
   superset has no reachable state left), continue refuses anything
   that is not a checkpoint, and an unknown trigger word is refused
   naming the vocabulary;
3. **the reveal enqueue** — every event a step wrote leaves exactly one
   ``PENDING`` item (derived id, the world's own byline or the comms
   actor's), the enqueue shape is refused not silently moved, and a
   refused step enqueues nothing (零撕裂 — the trace is read only after
   ``advance`` answers ``Ok``);
4. **the inbox's atomic reveal** — ``reveal_all`` flips the world's
   whole pending slice at one moment and reads everything back
   ascending, a second reveal keeps the first stamp (历史接续), and a
   dangling world is a refusal;
5-7. the web half — served in ``tests/host/test_w13_web.py`` (the
   endpoints, the turn wiring's fail-soft, the ``run_web`` binding);
8. **the deletion bucket move** — the binding rows go with the
   conversation (ALL_USER_DATA sweep passes end to end; the CONVERSATION
   scope carries its own binding), the world-owned half stays;
9. **the webui instrument** — the page's inbox region is textContent-only
   with the continue interaction retired at the source (A2R DEC-…99);
10. **the migration touch faces** — the census and the AOCI ledger
    record this cut (the N12/N13/N20 family obligation, pinned so the
    next touch cannot silently skip it).
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from elc.deletion.store import SqliteDeletionStore
from elc.deletion.types import DeletionRequest, DeletionScope
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.types import Err, Ok
from elc.world.engine.orchestrate import (
    TRIGGER_CONTINUE,
    TRIGGER_LETTER,
    run_step,
)
from elc.world.engine.types import EngineConfig, MomentKind, PoolEvent
from elc.world.store import SqliteWorldStore, WorldRevealItem
from elc.world.types import StateEffect, WorldEvent
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)

NOW = "2026-10-05T00:00:00+00:00"
LATER = "2026-10-05T09:30:00+00:00"
EVEN_LATER = "2026-10-05T18:00:00+00:00"

WORLD = "world-main"


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection with the production
    foreign-keys-ON profile (the w12 fixture shape)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _seed_world(store: SqliteWorldStore, world_id: str = WORLD) -> None:
    assert store.create_world(world_id, "Main", None, NOW).value is not None


def _seed_persona_card(
    conn: sqlite3.Connection, persona_id: str, *, builtin: bool = False
) -> None:
    """One minimal character_card row (the w12 helper shape — the persona
    FK target, real on a fresh db). The deletion E2E seeds a **builtin**
    card: that is the production cast shape (the official family), and
    it is the shape the sweep keeps — a user-authored card goes with the
    user's data and its removal would rightly refuse on the world_actor
    FK (the registered consequence the types module documents)."""

    exists = conn.execute(
        "SELECT 1 FROM character_card WHERE persona_id = ?", (persona_id,)
    ).fetchone()
    if exists is not None:
        return
    conn.execute(
        "INSERT INTO character_card ("
        " character_id, persona_id, name, identity, personality, background,"
        " speech_style, \"values\", boundaries, opening, scenario,"
        " generation_policy, lore_refs, revision, status, is_builtin,"
        " created_at, updated_at"
        ") VALUES (?, ?, 'Nell', '', '', '', '', '', '', '', '', '', '[]',"
        " 1, 'ACTIVE', ?, ?, ?)",
        (f"card-for-{persona_id}", persona_id, 1 if builtin else 0, NOW, NOW),
    )
    conn.commit()


NOTICE_POOL: tuple[PoolEvent, ...] = (
    PoolEvent(
        kind="happen",
        narration="A notice arrives from the world.",
        effects=(StateEffect(key="last", statement="a notice arrived"),),
        moment=MomentKind.NOTICE,
    ),
)

RESPONSE_POOL: tuple[PoolEvent, ...] = (
    PoolEvent(
        kind="happen",
        narration="The world asks for a reply.",
        effects=(StateEffect(key="last", statement="the world asked"),),
        moment=MomentKind.RESPONSE,
    ),
)


def _fresh_db(tmp_path: Path, name: str) -> sqlite3.Connection:
    db = sqlite3.connect(tmp_path / name)
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


# ---------------------------------------------------------------------------
# 1 — the migration
# ---------------------------------------------------------------------------


def test_0026_is_the_registered_head() -> None:
    """W-1-3's migration is the head, immediately behind W-1-2's
    0025_world_runs; the shared constants say so, and the stamp a fresh
    database carries is 26 (the stamp-pin discipline every head move
    has followed since P8-4)."""

    assert MIGRATION_IDS[-1] == "0026_world_reveal"
    assert MIGRATION_IDS[-2] == "0025_world_runs"
    assert SCHEMA_HEAD_FILE == "0026_world_reveal.sql"
    assert (REPO_ROOT / "migrations" / SCHEMA_HEAD_FILE).is_file()
    assert SCHEMA_HEAD_VERSION == "26"

    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0026_world_reveal"
    assert applied[-2] == "0025_world_runs"
    assert schema_version(fresh) == "26"


def test_world_reveal_item_carries_its_columns() -> None:
    """The physical column set, in order — the task book's enumeration,
    column for column (the id/type/pk triplets PRAGMA reports; SQLite's
    ``notnull`` flag reads 0 on the TEXT primary key — the 0023/0024
    tables' own shape, the PK is the declaration)."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    rows = fresh.execute("PRAGMA table_info(world_reveal_item)").fetchall()
    expected = [
        ("item_id", "TEXT", 1),
        ("world_id", "TEXT", 0),
        ("source_event_id", "TEXT", 0),
        ("actor_id", "TEXT", 0),
        ("status", "TEXT", 0),
        ("revealed_at", "TEXT", 0),
        ("created_at", "TEXT", 0),
    ]
    assert [(str(row[1]), str(row[2]), int(row[5])) for row in rows] == expected


def test_the_reveal_table_declares_its_posture() -> None:
    """The schema's own refusals: the three FKs (world / world_event /
    world_actor), the CHECK vocabulary (a third word cannot reach the
    row), the index that serves the inbox read, the RESTRICT posture
    against deleting a world with items, and the double ``'26'``
    stamp."""

    fresh = sqlite3.connect(":memory:")
    fresh.execute("PRAGMA foreign_keys=ON")
    apply_migrations(fresh)

    foreign_keys = fresh.execute(
        "PRAGMA foreign_key_list(world_reveal_item)"
    ).fetchall()
    assert sorted(
        (str(row[2]), str(row[3]), str(row[4])) for row in foreign_keys
    ) == sorted(
        [
            ("world", "world_id", "world_id"),
            ("world_event", "source_event_id", "event_id"),
            ("world_actor", "actor_id", "actor_id"),
        ]
    )

    indexes = fresh.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
        " AND tbl_name = 'world_reveal_item'"
    ).fetchall()
    assert "idx_world_reveal_item_world_status" in {
        str(row[0]) for row in indexes
    }

    fresh.execute(
        "INSERT INTO world (world_id, name, created_at) VALUES"
        " ('w', 'Main', ?)",
        (NOW,),
    )
    fresh.execute(
        "INSERT INTO world_event (event_id, world_id, kind, narration,"
        " effects, occurred_at, source) VALUES"
        " ('e', 'w', 'kind', 'narration', '[]', ?, 'src')",
        (NOW,),
    )
    base = (
        "INSERT INTO world_reveal_item (item_id, world_id, source_event_id,"
        " actor_id, status, revealed_at, created_at)"
        " VALUES (?, 'w', 'e', NULL, ?, ?, ?)"
    )
    # The legal rows land: PENDING with a NULL reveal moment, and a
    # REVEALED row carrying its moment.
    fresh.execute(base, ("i-pending", "PENDING", None, NOW))
    fresh.execute(base, ("i-revealed", "REVEALED", NOW, NOW))
    # A third lifecycle word cannot reach the row.
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute(base, ("i-seen", "SEEN", None, NOW))

    # RESTRICT posture: a world with items does not delete.
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute("DELETE FROM world WHERE world_id = 'w'")

    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps["schema_version"] == "26"
    assert stamps["runtime_schema_version"] == "26"


# ---------------------------------------------------------------------------
# 2 — run_step's dual triggers
# ---------------------------------------------------------------------------


def test_the_letter_winds_the_first_run(store: SqliteWorldStore) -> None:
    """The letter trigger on a world with no runs: the run is created
    with the world's run count as its seed (zero), the derived id, the
    triggering turn carried through, and the engine's advance answers
    the ceiling (A2R DEC-…99: the single-event NOTICE pool is always
    mature, so every cycle writes the beat again until ``max_cycles``
    cuts in — the run terminalizes with the LIMIT exit)."""

    _seed_world(store)
    stepped = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "turn-1"
    )
    assert isinstance(stepped, Ok), stepped.error
    assert stepped.value.outcome == "LIMIT"
    assert len(stepped.value.cycles) == 8
    runs = store.list_runs(WORLD)
    assert [run.run_id for run in runs] == ["run-main-0000"]
    assert runs[0].seed == 0
    assert runs[0].trigger_turn_id == "turn-1"
    assert runs[0].status.value == "TERMINAL"


def test_the_letter_seed_is_the_run_count(
    store: SqliteWorldStore, tmp_path: Path
) -> None:
    """The seed is the world's run count — deterministic end to end: the
    same world history replayed in a second fresh database drives the
    same seeds, the same run ids and the same chronicle, and a letter
    after a TERMINAL run seeds the next one with the count (one)."""

    _seed_world(store)
    first = run_step(
        store, WORLD, RESPONSE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1"
    )
    assert isinstance(first, Ok) and first.value.outcome == "TERMINAL"
    second = run_step(
        store, WORLD, RESPONSE_POOL, EngineConfig(), TRIGGER_LETTER, EVEN_LATER, "t2"
    )
    assert isinstance(second, Ok) and second.value.outcome == "TERMINAL"
    runs = store.list_runs(WORLD)
    assert [(run.run_id, run.seed) for run in runs] == [
        ("run-main-0000", 0),
        ("run-main-0001", 1),
    ]
    chronicle = store.chronicle_of(WORLD)
    assert isinstance(chronicle, Ok)
    replay = SqliteWorldStore(
        _fresh_db(tmp_path, "replay.db"), open_runtime_epoch(
            _fresh_db(tmp_path, "replay.db")
        )
    )
    replay.create_world(WORLD, "Main", None, NOW)
    for _ in range(2):
        replayed = run_step(
            replay, WORLD, RESPONSE_POOL, EngineConfig(), TRIGGER_LETTER, LATER
        )
        assert isinstance(replayed, Ok)
    replay_chronicle = replay.chronicle_of(WORLD)
    assert isinstance(replay_chronicle, Ok)
    assert [event.event_id for event in replay_chronicle.value] == [
        event.event_id for event in chronicle.value
    ]


def test_the_letter_after_a_finished_run_winds_the_next(
    store: SqliteWorldStore,
) -> None:
    """A2R (DEC-…99): the engine never pauses mid-run, so the letter's
    resume superset has no reachable state left — a letter onto a
    finished world winds the **next** run (the second winch is the only
    letter a finished world can get; nothing is re-rolled)."""

    _seed_world(store)
    first = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1"
    )
    assert isinstance(first, Ok)
    assert first.value.outcome == "LIMIT"  # the single-event pool's ceiling
    second = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, EVEN_LATER, "t2"
    )
    assert isinstance(second, Ok)
    runs = store.list_runs(WORLD)
    assert [(run.run_id, run.trigger_turn_id) for run in runs] == [
        ("run-main-0000", "t1"),
        ("run-main-0001", "t2"),
    ]
    # The second letter's events belong to the new run only.
    assert {cycle.event_id.split(":")[0] for cycle in second.value.cycles} == {
        "run-main-0001"
    }


def test_continue_refuses_off_a_checkpoint(store: SqliteWorldStore) -> None:
    """Continue is only the checkpoint's light action: with no run at
    all, and with the run TERMINAL, the refusal is the human word — the
    world is not waiting."""

    _seed_world(store)
    nothing = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_CONTINUE, LATER
    )
    assert isinstance(nothing, Err)
    assert nothing.error.code.value == "VALIDATION_FAILED"
    assert "not waiting at a checkpoint" in nothing.error.message

    run_step(store, WORLD, RESPONSE_POOL, EngineConfig(), TRIGGER_LETTER, LATER)
    done = run_step(
        store, WORLD, RESPONSE_POOL, EngineConfig(), TRIGGER_CONTINUE, LATER
    )
    assert isinstance(done, Err)
    assert "not waiting at a checkpoint" in done.error.message


def test_an_unknown_trigger_is_refused(store: SqliteWorldStore) -> None:
    """A trigger outside the two words is a caller bug: the refusal
    names the vocabulary (a typo must not silently mean either)."""

    _seed_world(store)
    refused = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), "nudge", LATER
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "'letter'" in refused.error.message
    assert "'continue'" in refused.error.message


# ---------------------------------------------------------------------------
# 3 — the reveal enqueue
# ---------------------------------------------------------------------------


def test_each_event_leaves_exactly_one_pending_item(
    store: SqliteWorldStore,
) -> None:
    """One event the step wrote, one PENDING queue item: the id derives
    from the event, the byline is the world's own (no cast — actor_id
    NULL), and nothing is revealed yet. The single-event pool writes
    eight beats in one step (the ceiling), so eight items — one per
    event, id for id."""

    _seed_world(store)
    stepped = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1"
    )
    assert isinstance(stepped, Ok)
    rows = store._conn.execute(
        "SELECT item_id, world_id, source_event_id, actor_id, status,"
        " revealed_at, created_at FROM world_reveal_item"
        " ORDER BY item_id ASC"
    ).fetchall()
    assert len(rows) == len(stepped.value.cycles) == 8
    for index, row in enumerate(rows):
        event_id = f"{stepped.value.run_id}:{index}"
        assert (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            row[3],
            str(row[4]),
            row[5],
            str(row[6]),
        ) == (
            f"{event_id}:reveal",
            WORLD,
            event_id,
            None,
            "PENDING",
            None,
            LATER,
        )


def test_the_item_signs_the_cast_actor_when_the_draw_chose_one(
    store: SqliteWorldStore, conn: sqlite3.Connection
) -> None:
    """With a cast, each item's byline is its own cycle's comms
    correspondent or the world's own narration — either way a real actor
    id or NULL, never a name the world does not know."""

    _seed_world(store)
    _seed_persona_card(conn, "persona-nell")
    assert store.bind_actor("actor-main-nell", WORLD, "persona-nell", NOW).value
    stepped = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1"
    )
    assert isinstance(stepped, Ok)
    trace_actors = {
        str(cycle.event_id): cycle.actor
        for cycle in stepped.value.cycles
        if cycle.event_id is not None
    }
    rows = store._conn.execute(
        "SELECT source_event_id, actor_id FROM world_reveal_item"
    ).fetchall()
    assert len(rows) == len(trace_actors) == 8
    for source_event_id, actor_id in rows:
        item_actor = None if actor_id is None else str(actor_id)
        assert item_actor == trace_actors[str(source_event_id)]
        if item_actor is not None:
            assert item_actor == "actor-main-nell"


def test_a_refused_step_enqueues_nothing(store: SqliteWorldStore) -> None:
    """零撕裂: the trace is read only after ``advance`` answers ``Ok`` —
    a step whose event write is refused (the chronicle's append-only
    CONFLICT, staged here by pre-writing the derived event id) leaves
    the queue exactly as it found it."""

    _seed_world(store)
    # Stage the refusal: the id the step's first event would derive is
    # already in the chronicle with a different shape.
    conflict = store.record_event(
        WorldEvent(
            event_id="run-main-0000:0",
            world_id=WORLD,
            kind="staged",
            narration="a different shape",
            effects=(),
            occurred_at=NOW,
            source="stage",
        )
    )
    assert isinstance(conflict, Ok)
    refused = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1"
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"
    # The staged event wrote nothing into the queue, and neither did the
    # refused step: zero items, full stop.
    assert store._conn.execute(
        "SELECT COUNT(*) FROM world_reveal_item"
    ).fetchone() == (0,)


def test_the_enqueue_shape_is_refused_not_silently_moved(
    store: SqliteWorldStore,
) -> None:
    """The enqueue face's only legal shape is PENDING with no reveal
    moment: anything else is a VALIDATION_FAILED before anything is
    written (the flip is reveal_all's alone)."""

    _seed_world(store)
    item = WorldRevealItem(
        item_id="e:reveal",
        world_id=WORLD,
        source_event_id="e",
        actor_id=None,
        status="REVEALED",
        revealed_at=NOW,
        created_at=NOW,
    )
    refused = store.enqueue_reveals((item,))
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert store._conn.execute(
        "SELECT COUNT(*) FROM world_reveal_item"
    ).fetchone() == (0,)


def test_an_empty_enqueue_is_a_legal_noop(store: SqliteWorldStore) -> None:
    """A step whose trace carried no events (the LIMIT exit's shape)
    enqueues nothing and answers Ok — there is nothing to write."""

    noop = store.enqueue_reveals(())
    assert isinstance(noop, Ok)
    assert noop.value == ()


# ---------------------------------------------------------------------------
# 4 — the inbox's atomic reveal
# ---------------------------------------------------------------------------


def test_reveal_all_flips_the_pending_slice_and_reads_it_back(
    store: SqliteWorldStore,
) -> None:
    """The presentation trigger: one call flips the world's whole
    PENDING slice to REVEALED at one moment and reads the whole inbox
    back — every item is PENDING before, REVEALED with the stamp after
    (the single-event pool's step leaves eight of them)."""

    _seed_world(store)
    stepped = run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1"
    )
    assert isinstance(stepped, Ok)
    before = store.reveal_all(WORLD, EVEN_LATER)
    assert isinstance(before, Ok)
    assert len(before.value) == 8
    assert {item.status for item in before.value} == {"REVEALED"}
    assert {item.revealed_at for item in before.value} == {EVEN_LATER}


def test_a_second_reveal_keeps_the_first_stamp(
    store: SqliteWorldStore,
) -> None:
    """历史接续: a second reveal does not re-stamp — the UPDATE matches
    nothing, the read returns the same rows, every ``revealed_at`` stays
    the first reveal's moment."""

    _seed_world(store)
    run_step(store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1")
    store.reveal_all(WORLD, EVEN_LATER)
    again = store.reveal_all(WORLD, "2026-10-06T00:00:00+00:00")
    assert isinstance(again, Ok)
    assert len(again.value) == 8
    assert {item.revealed_at for item in again.value} == {EVEN_LATER}


def test_the_inbox_reads_ascending_with_history(
    store: SqliteWorldStore,
) -> None:
    """Two steps' items read back in the durable order (created_at, then
    item_id), revealed history included — the inbox is the world's
    whole ledger of what it owes you, not a transient unread pile. The
    second step is a letter onto the finished first run (A2R DEC-…99:
    the light continue has no reachable state left)."""

    _seed_world(store)
    run_step(store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1")
    run_step(
        store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, EVEN_LATER, "t2"
    )
    inbox = store.reveal_all(WORLD, "2026-10-05T23:00:00+00:00")
    assert isinstance(inbox, Ok)
    assert len(inbox.value) == 16
    # Durable order: the first run's eight items (LATER) before the
    # second run's eight (EVEN_LATER); within a run, cursor order.
    stamps = [item.created_at for item in inbox.value]
    assert stamps == sorted(stamps)
    assert [item.created_at for item in inbox.value[:8]] == [LATER] * 8
    assert [item.created_at for item in inbox.value[8:]] == [EVEN_LATER] * 8
    assert inbox.value[0].item_id == "run-main-0000:0:reveal"
    assert inbox.value[7].item_id == "run-main-0000:7:reveal"
    assert inbox.value[8].item_id == "run-main-0001:0:reveal"
    assert {item.status for item in inbox.value} == {"REVEALED"}


def test_reveal_all_refuses_a_dangling_world(store: SqliteWorldStore) -> None:
    """An inbox of a world that does not exist is a refusal, never an
    empty read (the value-semantics posture the store holds everywhere)."""

    refused = store.reveal_all("world-nowhere", LATER)
    assert isinstance(refused, Err)
    assert refused.error.code.value == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 8 — the deletion bucket move (the three-cut Revisit closed)
# ---------------------------------------------------------------------------


def _bind_and_load(conn: sqlite3.Connection, store: SqliteWorldStore) -> None:
    """One real binding over one real conversation row, plus one reveal
    item hanging off one real event — the E2E world the sweeps walk."""

    _seed_world(store)
    _seed_persona_card(conn, "persona-nell", builtin=True)
    assert store.bind_actor("actor-main-nell", WORLD, "persona-nell", NOW).value
    conn.execute(
        "INSERT INTO conversation (conversation_id, persona_id, created_at,"
        " status, next_turn_sequence, next_message_sequence)"
        " VALUES ('conv-1', 'persona-nell', ?, 'ACTIVE', 1, 1)",
        (NOW,),
    )
    # The binding store runs its own short transactions: the conversation
    # row must be committed before the bind's BEGIN IMMEDIATE (the same
    # connection would otherwise carry the insert inside an implicit
    # transaction and refuse the store's own).
    conn.commit()
    assert store.bind_conversation(
        "bind-conv-1", WORLD, "actor-main-nell", "conv-1", NOW
    ).value
    conn.execute(
        "INSERT INTO world_event (event_id, world_id, kind, narration,"
        " effects, occurred_at, source) VALUES"
        " ('e-1', ?, 'kind', 'narration', '[]', ?, 'src')",
        (WORLD, NOW),
    )
    conn.commit()


def test_all_user_data_sweeps_the_binding_and_keeps_the_world(
    conn: sqlite3.Connection, store: SqliteWorldStore, tmp_path: Path
) -> None:
    """The E2E the three-cut Revisit owed: a database with a bound
    conversation runs the ALL_USER_DATA sweep end to end — it passes
    (the RESTRICT posture can no longer refuse it), the binding rows go
    with the user's data, and the world-owned half stays."""

    _bind_and_load(conn, store)
    run_step(store, WORLD, NOTICE_POOL, EngineConfig(), TRIGGER_LETTER, LATER, "t1")
    deletion = SqliteDeletionStore(conn, open_runtime_epoch(conn))
    result = deletion.execute(DeletionRequest(scope=DeletionScope.ALL_USER_DATA))
    assert isinstance(result, Ok), result
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "world_conversation",
            "world",
            "world_actor",
            "world_event",
            "world_state_fact",
            "world_run",
            "world_reveal_item",
        )
    }
    assert counts["world_conversation"] == 0
    assert counts["world"] == 1
    assert counts["world_actor"] == 1
    # Ten events: the fixture's staged chronicle entry plus the step's
    # own eight beats (the single-event pool's ceiling) — both
    # world-owned, all kept.
    assert counts["world_event"] == 9
    assert counts["world_state_fact"] == 8
    assert counts["world_run"] == 1
    assert counts["world_reveal_item"] == 8


def test_the_conversation_scope_carries_its_own_binding(
    conn: sqlite3.Connection, store: SqliteWorldStore
) -> None:
    """§19's closure: the CONVERSATION scope sweeps the conversation's
    world binding with the conversation it bound (and the world stays)."""

    _bind_and_load(conn, store)
    deletion = SqliteDeletionStore(conn, open_runtime_epoch(conn))
    result = deletion.execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id="conv-1")
    )
    assert isinstance(result, Ok), result
    assert conn.execute(
        "SELECT COUNT(*) FROM world_conversation"
    ).fetchone() == (0,)
    assert conn.execute("SELECT COUNT(*) FROM world").fetchone() == (1,)


# ---------------------------------------------------------------------------
# 9 — the webui instrument (structural, as the page actually ships)
# ---------------------------------------------------------------------------


def _page_source() -> str:
    webui = REPO_ROOT / "src" / "elc" / "webui"
    parts = [
        (webui / "index.html").read_text(encoding="utf-8"),
        (webui / "app.js").read_text(encoding="utf-8"),
        (webui / "components.js").read_text(encoding="utf-8"),
    ]
    return "\n".join(parts)


def test_the_page_carries_the_world_inbox_instrument() -> None:
    """DEC-…92's retirement, as strings the browser actually runs, plus
    A2R's (DEC-…99): the resident inbox region is gone (no section, no
    bottom mount — the world's only presentation is the inline story
    block in the letter flow), the story block's own code paths render
    through textContent (the XSS face — the family pin re-asserted), the
    continue interaction is retired at the source (no ``at_checkpoint``
    branch, no actions row, no continue fetch — the engine never pauses
    mid-run, so the page has nothing to wait for), and the load arm's
    item check stays defensive."""

    app = (REPO_ROOT / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "worldInboxSec" not in app
    assert 'insertAdjacentElement("afterend"' not in app
    assert "insertBefore(worldInboxSec" not in app
    # The continue interaction, retired whole: no checkpoint branch, no
    # actions row, no fetch, no dead import (A2R DEC-…99).
    assert "event.at_checkpoint" not in app
    assert "fetchWorldContinue" not in app
    assert "world-story-actions" not in app
    assert "世界没能继续" not in app
    assert "Array.isArray(data.items)" in app
    # The XSS face, family re-assertion: the page's text paths stay inert.
    page = _page_source()
    assert "textContent" in page
    assert ".innerHTML" not in page
    # The style sheet carries no dead rule for the retired actions row.
    css = (REPO_ROOT / "src" / "elc" / "webui" / "components.css").read_text(
        encoding="utf-8"
    )
    assert "world-story-actions" not in css
    # The transport module carries no retired endpoint call.
    api = (REPO_ROOT / "src" / "elc" / "webui" / "api.js").read_text(
        encoding="utf-8"
    )
    assert "world/continue" not in api


def test_the_turn_does_not_reread_the_inbox() -> None:
    """DEC-…92's law, carried past A2R (DEC-…99): the turn no longer
    rereads the inbox (the streamed pre-step already revealed and the
    story frame already presented — a second read is a dead call), and
    the continue interaction's strings retired with the button (the
    page's dead-text face stays empty — nothing lingers that no code
    path can render)."""

    app = (REPO_ROOT / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )
    # The turn's response block carries no inbox reread any more (the
    # pre-step's reveal + the story frame did the presenting).
    turn_block = app[app.find("async function postTurn") : app.find(
        "async function postTeachMe"
    )]
    assert "loadWorldInbox" not in turn_block
    # The continue failure arm and its button text are gone with the
    # interaction (A2R DEC-…99).
    assert 'typeof fresh.error === "string"' not in app
    assert "世界没能继续" not in app
    assert '"Continue"' not in app


# ---------------------------------------------------------------------------
# 10 — the migration touch faces (N12/N13/N20 family)
# ---------------------------------------------------------------------------


def test_the_census_records_the_w13_touch() -> None:
    """The census header records this cut's own re-measurement (the
    family obligation every touch of that file carries), and the world
    row's declared face still imports."""

    census = (
        REPO_ROOT / "tests" / "architecture" / "test_surface_census.py"
    ).read_text(encoding="utf-8")
    assert "W-1-3 触碰本文件时同刀" in census
    assert "复测为 **585** / 148 / **184**" in census
    tree = ast.parse(
        (REPO_ROOT / "src" / "elc" / "world" / "store.py").read_text(
            encoding="utf-8"
        )
    )
    classes = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    assert "SqliteWorldStore" in classes
    assert "WorldRevealItem" in classes


def test_the_aoci_ledger_records_the_w13_faces() -> None:
    """The AOCI ledger's 刀内随迁: the new execution face, the new
    migration and the moved deletion face each carry their entry — the
    next reader's one-hop index stays true."""

    ledger = (REPO_ROOT / "aoci.code.txt").read_text(encoding="utf-8")
    assert "orchestrate.py[DB7T]" in ledger
    assert "0026_world_reveal.sql[PD7T]" in ledger
    assert "世界收件箱/轻继续/turn 接线（W-1-3）" in ledger
    assert "已换桶入 CONVERSATION_SWEPT_TABLES" in ledger
