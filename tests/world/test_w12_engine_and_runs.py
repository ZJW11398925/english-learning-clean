"""W-1-2 — the world-run engine v1 and its durable ``world_run`` row
(ten pin groups).

The living-world program's third cut (the adjudication chain
DEC-OPI-7e3744ee…26; the spec §4.2 v2.1 seven-step sequence;
M0.1 AD-6 — the run is durable so a restart does not re-roll the dice).
The slice VAL groups, each a section below:

1. **migration pins** — 0025 is the registered head, the ``world_run``
   table carries its ten columns in order, and the schema's own
   declarations hold: the single FK to ``world``, the CHECK vocabularies
   (``DIRECTION`` absent), the cursor / version guards, the double
   ``'25'`` stamp and the RESTRICT posture;
2. **deterministic replay** — the same seed drives two independent
   runs (two fresh databases) to bit-for-bit identical traces and
   chronicles, and a different seed diverges;
3. **resume without re-rolling** — a NOTICE pause followed by a resume
   continues the sequence from the persisted cursor (a re-rolled cycle
   would derive an existing event id with a fresh ``occurred_at`` and
   hit the chronicle's append-only CONFLICT — the pin holds precisely
   because none of that happens);
4. **the double exit** — NOTICE pauses at the checkpoint, RESPONSE
   terminates, a multi-checkpoint chain walks the same run through
   several pauses, and ``DIRECTION`` cannot reach the row;
5. **record_event integration** — the engine's events settle their
   effects through the store's one atomic face (projection, derived
   fact ids, the engine's source word, the caller's moment);
6. **communication v1** — at most one actor writes or the world stays
   silent, the decision is deterministic and trace-only (no letters);
7. **the fail-closed ceiling** — an empty pool or never-mature
   conditions burn pure time-advance cycles to ``max_cycles`` and
   terminate with the LIMIT exit (上限终止), never an infinite loop;
   nonsense configs are refused;
8. **run CRUD** — creation is the zeroth checkpoint, replay idempotence,
   dangling-world refusal, monotone ``state_version``, durable read
   order;
9. **the registration** — six canonical objects under ``OWNER_WORLD``
   (no version field) and seven ``GLOBAL_CONTENT_TABLES`` members;
10. **the declared structure** — the seven steps in order and the
    banner's honesty lists (what the engine claims and what it refuses
    to simulate).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.deletion.types import GLOBAL_CONTENT_TABLES, RETAINED_TABLES, SWEPT_TABLES
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations, schema_version
from elc.platform.registry import CANONICAL_OBJECTS, OWNER_WORLD
from elc.platform.types import Err, Ok
from elc.world import engine as engine_package
from elc.world.engine import steps as engine_steps
from elc.world.engine.engine import (
    ENGINE_SOURCE,
    OUTCOME_CHECKPOINT,
    OUTCOME_LIMIT,
    OUTCOME_TERMINAL,
    advance,
)
from elc.world.engine.types import (
    Condition,
    EngineConfig,
    MomentKind,
    PoolEvent,
    RunStatus,
    WorldRunRecord,
)
from elc.world.store import SqliteWorldStore
from elc.world.types import StateEffect
from tests.conftest import MIGRATION_IDS, SCHEMA_HEAD_FILE, SCHEMA_HEAD_VERSION

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "migrations"

NOW = "2026-10-05T00:00:00+00:00"
LATER = "2026-10-05T09:30:00+00:00"
EVEN_LATER = "2026-10-05T18:00:00+00:00"


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


#: The penpal card's persona id (migration 0019's seed row carries it —
#: the persona FK target, real on a fresh db).
PENPAL_PERSONA_ID = "persona-nell-alder"


def _seed_persona_card(conn: sqlite3.Connection, persona_id: str) -> None:
    """One minimal character_card row — the persona FK target for the
    second actor (w10's helper shape: the 0019 columns are NOT NULL
    across the board, the minimal honest row is empty strings plus the
    ids and the stamp). Idempotent by persona: a world recipe replayed
    must not collide with the card UNIQUE."""

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
        ") VALUES (?, ?, '', '', '', '', '', '', '', '', '', '', '[]',"
        " 1, 'ACTIVE', 0, ?, ?)",
        (f"card-for-{persona_id}", persona_id, NOW, NOW),
    )
    conn.commit()


def _bind_actors(store: SqliteWorldStore, world_id: str = "world-main") -> None:
    """Two actors, id-ascending: ``actor-nell`` (index 0) and
    ``actor-theo`` (index 1) — the comms step walks the roster in the
    store's durable order. One card speaks as at most one actor per
    world (the 0023 UNIQUE), so the second actor carries its own freshly
    seeded card."""

    conn = store._conn
    _seed_persona_card(conn, "persona-theo-bright")
    for actor_id, persona_id in (
        ("actor-nell", PENPAL_PERSONA_ID),
        ("actor-theo", "persona-theo-bright"),
    ):
        bound = store.bind_actor(actor_id, world_id, persona_id, NOW)
        assert bound.value is not None


def _two_event_pool() -> tuple[PoolEvent, ...]:
    """Two unconditionally-mature events: index 0 carries the NOTICE
    moment and settles one state claim; index 1 is the RESPONSE stop."""

    return (
        PoolEvent(
            kind="morning_bell",
            narration="the bell rings over Berrymoor",
            effects=(StateEffect(key="weather", statement="rain over the moor"),),
            moment=MomentKind.NOTICE,
        ),
        PoolEvent(
            kind="reply_arrives",
            narration="her reply is waiting at the desk",
            moment=MomentKind.RESPONSE,
        ),
    )


def _chain_pool() -> tuple[PoolEvent, ...]:
    """Three events whose maturity unfolds as the earlier ones settle:
    the door opens (NOTICE), a knock is heard (NOTICE, mature only once
    the door is open), her letter finally arrives (RESPONSE, mature only
    once the knock was heard). Seed 15 walks exactly this order."""

    return (
        PoolEvent(
            kind="door_opens",
            narration="the shop door swings open",
            effects=(StateEffect(key="door", statement="open"),),
            moment=MomentKind.NOTICE,
        ),
        PoolEvent(
            kind="knock_heard",
            narration="someone knocks twice",
            conditions=(Condition(canonical_key="door", statement="open"),),
            effects=(StateEffect(key="knock", statement="heard"),),
            moment=MomentKind.NOTICE,
        ),
        PoolEvent(
            kind="letter_arrives",
            narration="her letter lands on the counter",
            conditions=(Condition(canonical_key="knock", statement="heard"),),
            moment=MomentKind.RESPONSE,
        ),
    )


def _fresh_run(
    store: SqliteWorldStore,
    seed: int,
    run_id: str = "run-1",
    world_id: str = "world-main",
    actors: bool = True,
) -> WorldRunRecord:
    _seed_world(store, world_id)
    if actors:
        _bind_actors(store, world_id)
    created = store.create_run(run_id, world_id, "turn-1", seed, NOW)
    assert created.value is not None
    return created.value


def _assert_err(result: object, code: str) -> None:
    assert isinstance(result, Err), result
    assert result.error.code == code, result.error
    assert isinstance(result.error.message, str) and result.error.message


# ---------------------------------------------------------------------------
# 1 — the migration
# ---------------------------------------------------------------------------


def test_0025_is_the_registered_head() -> None:
    """W-1-2's migration is the head, immediately behind W-1-1's
    0024_world_events; the shared constants say so, and the stamp a
    fresh database carries is 25."""

    assert MIGRATION_IDS[-1] == "0025_world_runs"
    assert MIGRATION_IDS[-2] == "0024_world_events"
    assert SCHEMA_HEAD_FILE == "0025_world_runs.sql"
    assert (MIGRATIONS / SCHEMA_HEAD_FILE).is_file()
    assert SCHEMA_HEAD_VERSION == "25"

    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0025_world_runs"
    assert applied[-2] == "0024_world_events"
    assert schema_version(fresh) == "25"


def test_world_run_carries_its_ten_columns() -> None:
    """The physical column set, in order — the adjudication's own
    spelling, column for column: types and the ``run_id`` primary key
    (the name/type/pk triplets PRAGMA reports; SQLite's ``notnull`` flag
    reads 0 on the TEXT primary key — the 0023/0024 tables' own shape,
    the PK is the declaration)."""

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    rows = fresh.execute("PRAGMA table_info(world_run)").fetchall()
    expected = [
        ("run_id", "TEXT", 1),
        ("world_id", "TEXT", 0),
        ("trigger_turn_id", "TEXT", 0),
        ("seed", "INTEGER", 0),
        ("status", "TEXT", 0),
        ("checkpoint_kind", "TEXT", 0),
        ("cursor", "INTEGER", 0),
        ("state_version", "INTEGER", 0),
        ("created_at", "TEXT", 0),
        ("updated_at", "TEXT", 0),
    ]
    assert [(str(row[1]), str(row[2]), int(row[5])) for row in rows] == expected


def test_the_run_table_declares_its_posture() -> None:
    """The schema's own refusals: one FK to ``world`` (and nothing else —
    ``trigger_turn_id`` deliberately carries none), the CHECK
    vocabularies (``DIRECTION`` cannot reach the row), the cursor /
    version guards, the RESTRICT posture against deleting a world with
    runs, and the double ``'25'`` stamp."""

    fresh = sqlite3.connect(":memory:")
    fresh.execute("PRAGMA foreign_keys=ON")
    apply_migrations(fresh)

    foreign_keys = fresh.execute("PRAGMA foreign_key_list(world_run)").fetchall()
    assert [(str(row[2]), str(row[3]), str(row[4])) for row in foreign_keys] == [
        ("world", "world_id", "world_id")
    ]

    base = (
        "INSERT INTO world_run (run_id, world_id, trigger_turn_id, seed,"
        " status, checkpoint_kind, \"cursor\", state_version, created_at,"
        " updated_at) VALUES ('r', 'w', NULL, 1, ?, 'NOTICE', 0, 1, ?, ?)"
    )
    fresh.execute("INSERT INTO world (world_id, name, created_at)"
                  " VALUES ('w', 'Berrymoor', ?)", (NOW,))
    fresh.execute(base, ("AT_CHECKPOINT", NOW, NOW))  # the legal row lands

    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id, seed,"
            " status, checkpoint_kind, \"cursor\", state_version, created_at,"
            " updated_at) VALUES ('r2', 'w', NULL, 1, 'PAUSED', 'NOTICE',"
            " 0, 1, ?, ?)",
            (NOW, NOW),
        )
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id, seed,"
            " status, checkpoint_kind, \"cursor\", state_version, created_at,"
            " updated_at) VALUES ('r3', 'w', NULL, 1, 'AT_CHECKPOINT',"
            " 'DIRECTION', 0, 1, ?, ?)",
            (NOW, NOW),
        )
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id, seed,"
            " status, checkpoint_kind, \"cursor\", state_version, created_at,"
            " updated_at) VALUES ('r4', 'w', NULL, 1, 'AT_CHECKPOINT',"
            " 'NOTICE', -1, 1, ?, ?)",
            (NOW, NOW),
        )
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id, seed,"
            " status, checkpoint_kind, \"cursor\", state_version, created_at,"
            " updated_at) VALUES ('r5', 'w', NULL, 1, 'AT_CHECKPOINT',"
            " 'NOTICE', 0, 0, ?, ?)",
            (NOW, NOW),
        )

    # RESTRICT posture: a world with runs does not delete.
    with pytest.raises(sqlite3.IntegrityError):
        fresh.execute("DELETE FROM world WHERE world_id = 'w'")

    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps["schema_version"] == "25"
    assert stamps["runtime_schema_version"] == "25"


# ---------------------------------------------------------------------------
# 2 — deterministic replay
# ---------------------------------------------------------------------------


def test_the_same_seed_replays_the_same_run_bit_for_bit(
    tmp_path: Path,
) -> None:
    """Two fresh databases, the same world recipe, the same pool, the
    same seed: two independent runs walk to bit-for-bit identical traces
    and identical chronicles — the run's dice live in ``(seed, cursor)``,
    not in any ambient state (AD-6)."""

    def _play(directory: Path) -> tuple[object, list[tuple[str, str]]]:
        directory.mkdir(parents=True)
        db = sqlite3.connect(directory / "app.db")
        db.execute("PRAGMA foreign_keys=ON")
        apply_migrations(db)
        store = SqliteWorldStore(db, open_runtime_epoch(db))
        run = _fresh_run(store, seed=42)
        trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
        assert isinstance(trace, Ok)
        chronicle = store.chronicle_of("world-main")
        assert isinstance(chronicle, Ok)
        db.close()
        return trace.value, [
            (event.event_id, event.narration) for event in chronicle.value
        ]

    first = _play(tmp_path / "a")
    second = _play(tmp_path / "b")
    assert first == second
    # The literal shape (seed 42, cursor 0: pool index 0, then the
    # terminal): the pin is exact, not merely "equal to each other".
    trace, chronicle = first
    assert [(c.cursor, c.selected, c.moment) for c in trace.cycles] == [
        (0, "morning_bell", "NOTICE")
    ]
    assert chronicle == [("run-1:0", "the bell rings over Berrymoor")]


def test_a_different_seed_diverges(store: SqliteWorldStore) -> None:
    """The same pool under a different seed draws a different event at
    the same cursor — the seed is the run's dice, and the engine never
    falls back to an unseeded draw."""

    traces = []
    for seed in (7, 42):
        run = _fresh_run(store, seed=seed, run_id=f"run-{seed}")
        trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
        assert isinstance(trace, Ok)
        traces.append(trace.value)
    assert traces[0].cycles[0].selected == "reply_arrives"  # seed 7: index 1
    assert traces[1].cycles[0].selected == "morning_bell"  # seed 42: index 0


# ---------------------------------------------------------------------------
# 3 — resume without re-rolling
# ---------------------------------------------------------------------------


def test_resume_continues_the_sequence_without_re_rolling(
    store: SqliteWorldStore,
) -> None:
    """A NOTICE pause, then a resume from the re-read row: the second
    call starts at the persisted cursor (its trace holds exactly one
    cycle, cursor 1), the chronicle holds both events in order, and
    nothing conflicts — a re-rolled cycle 0 would derive the existing
    ``run-1:0`` id with the resume's fresh ``occurred_at`` and hit the
    chronicle's append-only CONFLICT, so an ``Ok`` here is the pin."""

    run = _fresh_run(store, seed=42)
    pool = _two_event_pool()

    first = advance(store, run, pool, EngineConfig(), LATER)
    assert isinstance(first, Ok) and first.value.outcome == OUTCOME_CHECKPOINT

    resumed = store.get_run("run-1")
    assert resumed is not None and resumed.cursor == 1
    second = advance(store, resumed, pool, EngineConfig(), EVEN_LATER)
    assert isinstance(second, Ok)
    assert second.value.outcome == OUTCOME_TERMINAL
    assert [(c.cursor, c.selected, c.moment) for c in second.value.cycles] == [
        (1, "reply_arrives", "RESPONSE")
    ]

    chronicle = store.chronicle_of("world-main")
    assert isinstance(chronicle, Ok)
    assert [(event.event_id, event.kind) for event in chronicle.value] == [
        ("run-1:0", "morning_bell"),
        ("run-1:1", "reply_arrives"),
    ]
    final = store.get_run("run-1")
    assert final is not None
    assert final.status == RunStatus.TERMINAL
    # The cursor freezes at the last checkpoint boundary on terminal (the
    # store's terminalize moves status/kind/version only): cycle 1 ran
    # and the run finished; the trace above is its record.
    assert final.cursor == 1


# ---------------------------------------------------------------------------
# 4 — the double exit
# ---------------------------------------------------------------------------


def test_notice_pauses_the_run_at_its_checkpoint(store: SqliteWorldStore) -> None:
    """The NOTICE exit: the call returns the CHECKPOINT outcome, the
    cycle trace names the four executed steps and the NOTICE moment, and
    the row stays ``AT_CHECKPOINT`` / ``NOTICE`` with the cursor advanced
    and the version bumped."""

    run = _fresh_run(store, seed=42)
    trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
    assert isinstance(trace, Ok)
    assert trace.value.outcome == OUTCOME_CHECKPOINT
    cycle = trace.value.cycles[0]
    assert cycle.steps == (
        engine_steps.STEP_TIME,
        engine_steps.STEP_EVENTS,
        engine_steps.STEP_COMMS,
        engine_steps.STEP_MOMENT,
    )
    assert cycle.moment == "NOTICE"
    paused = store.get_run("run-1")
    assert paused is not None
    assert paused.status == RunStatus.AT_CHECKPOINT
    assert paused.checkpoint_kind == MomentKind.NOTICE
    assert paused.cursor == 1
    assert paused.state_version == 2


def test_response_terminates_the_run(store: SqliteWorldStore) -> None:
    """The RESPONSE exit: the run becomes ``TERMINAL`` / ``RESPONSE``,
    and a finished run refuses to advance again (``VALIDATION_FAILED``)
    — terminal is absorbing."""

    run = _fresh_run(store, seed=7)
    trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
    assert isinstance(trace, Ok)
    assert trace.value.outcome == OUTCOME_TERMINAL
    finished = store.get_run("run-1")
    assert finished is not None
    assert finished.status == RunStatus.TERMINAL
    assert finished.checkpoint_kind == MomentKind.RESPONSE
    assert finished.state_version == 2

    refusal = advance(store, finished, _two_event_pool(), EngineConfig(), LATER)
    _assert_err(refusal, "VALIDATION_FAILED")


def test_a_run_walks_a_multi_checkpoint_chain(store: SqliteWorldStore) -> None:
    """Several checkpoints inside one run: seed 15 walks the unfolding
    chain through two NOTICE pauses (cursors 1 and 2, versions 2 and 3)
    to the RESPONSE stop (version 4), the chronicle holding all three
    cycles' events in cursor order. The same run resumes; no second
    winch is involved."""

    run = _fresh_run(store, seed=15)
    pool = _chain_pool()

    first = advance(store, run, pool, EngineConfig(), LATER)
    assert isinstance(first, Ok)
    assert first.value.outcome == OUTCOME_CHECKPOINT
    assert first.value.cycles[0].selected == "door_opens"
    assert first.value.cycles[0].actor is None  # roster draw 2 of 2: silent

    mid = store.get_run("run-1")
    assert mid is not None and mid.cursor == 1
    second = advance(store, mid, pool, EngineConfig(), LATER)
    assert isinstance(second, Ok)
    assert second.value.outcome == OUTCOME_CHECKPOINT
    assert second.value.cycles[0].cursor == 1
    assert second.value.cycles[0].selected == "knock_heard"

    late = store.get_run("run-1")
    assert late is not None and late.cursor == 2
    third = advance(store, late, pool, EngineConfig(), EVEN_LATER)
    assert isinstance(third, Ok)
    assert third.value.outcome == OUTCOME_TERMINAL
    assert third.value.cycles[0].cursor == 2
    assert third.value.cycles[0].selected == "letter_arrives"
    assert third.value.cycles[0].actor == "actor-theo"  # draw 1 of 2: writes

    chronicle = store.chronicle_of("world-main")
    assert isinstance(chronicle, Ok)
    assert [event.event_id for event in chronicle.value] == [
        "run-1:0",
        "run-1:1",
        "run-1:2",
    ]
    final = store.get_run("run-1")
    assert final is not None
    # The cursor freezes at the last checkpoint boundary (cursor 2 = two
    # NOTICE pauses completed); the terminal cycle's record is the trace.
    assert final.cursor == 2
    assert final.state_version == 4


def test_direction_is_not_in_the_schema_vocabulary(
    store: SqliteWorldStore,
) -> None:
    """The run face refuses the third word twice over — the engine's
    vocabulary has two moments, and the store's update cannot write the
    word the migration's CHECK refuses (W-2-2 opens DIRECTION; until
    then nothing here carries it)."""

    _seed_world(store)
    created = store.create_run("run-1", "world-main", None, 1, NOW)
    assert created.value is not None

    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO world_run (run_id, world_id, trigger_turn_id, seed,"
            " status, checkpoint_kind, \"cursor\", state_version, created_at,"
            " updated_at) VALUES ('r-d', 'world-main', NULL, 1,"
            " 'AT_CHECKPOINT', 'DIRECTION', 0, 1, ?, ?)",
            (NOW, NOW),
        )
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "UPDATE world_run SET checkpoint_kind = 'DIRECTION'"
            " WHERE run_id = 'run-1'"
        )


# ---------------------------------------------------------------------------
# 5 — record_event integration
# ---------------------------------------------------------------------------


def test_engine_events_settle_their_effects(store: SqliteWorldStore) -> None:
    """The engine writes through the store's one atomic event face: the
    chronicle entry carries the pool event's pre-authored narration, the
    engine's source word and the caller's moment; the effect settles as
    the CURRENT fact with the derived id and the event's own time."""

    run = _fresh_run(store, seed=42)
    trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
    assert isinstance(trace, Ok)

    chronicle = store.chronicle_of("world-main")
    assert isinstance(chronicle, Ok)
    assert len(chronicle.value) == 1
    event = chronicle.value[0]
    assert event.event_id == "run-1:0"
    assert event.kind == "morning_bell"
    assert event.narration == "the bell rings over Berrymoor"
    assert event.source == ENGINE_SOURCE == "world_engine"
    assert event.occurred_at == LATER  # the caller's moment — no hidden clock
    assert event.effects == (
        StateEffect(key="weather", statement="rain over the moor"),
    )

    facts = store.current_facts("world-main")
    assert [
        (fact.fact_id, fact.canonical_key, fact.statement, fact.status)
        for fact in facts
    ] == [("run-1:0:weather", "weather", "rain over the moor", "CURRENT")]
    assert facts[0].recorded_at == LATER


# ---------------------------------------------------------------------------
# 6 — communication v1
# ---------------------------------------------------------------------------


def test_the_comms_step_is_deterministic_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """At most one actor writes, chosen by the same per-cycle RNG in the
    roster's durable order (or the world stays silent), the decision is
    identical across independent runs, and it writes nothing but the
    trace — the chronicle carries events, never letters."""

    def _play(directory: Path) -> tuple[str | None, int]:
        directory.mkdir(parents=True)
        db = sqlite3.connect(directory / "app.db")
        db.execute("PRAGMA foreign_keys=ON")
        apply_migrations(db)
        store = SqliteWorldStore(db, open_runtime_epoch(db))
        run = _fresh_run(store, seed=42)
        trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
        assert isinstance(trace, Ok)
        chronicle = store.chronicle_of("world-main")
        assert isinstance(chronicle, Ok)
        db.close()
        return trace.value.cycles[0].actor, len(chronicle.value)

    actor_a, chronicle_a = _play(tmp_path / "a")
    actor_b, chronicle_b = _play(tmp_path / "b")
    assert actor_a == actor_b == "actor-theo"  # seed 42's draw 1 of 2
    assert chronicle_a == chronicle_b == 1  # one event, zero letters


def test_an_empty_roster_stays_silent(store: SqliteWorldStore) -> None:
    """A world with no actors cannot correspond: the comms step answers
    silence without drawing, and the trace records it."""

    run = _fresh_run(store, seed=42, actors=False)
    trace = advance(store, run, _two_event_pool(), EngineConfig(), LATER)
    assert isinstance(trace, Ok)
    assert trace.value.cycles[0].actor is None


# ---------------------------------------------------------------------------
# 7 — the fail-closed ceiling
# ---------------------------------------------------------------------------


def test_an_empty_pool_fails_closed_to_the_ceiling(store: SqliteWorldStore) -> None:
    """No pool at all: pure time-advance cycles to ``max_cycles``, then
    the LIMIT exit (上限终止) — the run terminalizes, the trace records
    every burned cycle honestly (days, no selection), and the terminal
    run refuses to advance again. The engine never loops forever."""

    run = _fresh_run(store, seed=42)
    trace = advance(store, run, (), EngineConfig(max_cycles=5), LATER)
    assert isinstance(trace, Ok)
    assert trace.value.outcome == OUTCOME_LIMIT
    assert len(trace.value.cycles) == 5
    for index, cycle in enumerate(trace.value.cycles):
        assert cycle.cursor == index
        assert cycle.steps == (engine_steps.STEP_TIME, engine_steps.STEP_EVENTS)
        assert cycle.days_advanced == 1
        assert cycle.mature_kinds == ()
        assert cycle.selected is None
        assert cycle.event_id is None
        assert cycle.moment is None

    finished = store.get_run("run-1")
    assert finished is not None
    assert finished.status == RunStatus.TERMINAL
    assert finished.checkpoint_kind == MomentKind.RESPONSE
    assert finished.state_version == 2
    assert finished.cursor == 0  # the last checkpoint boundary — the
    # trace, not the row, carries the limit's cycle count

    chronicle = store.chronicle_of("world-main")
    assert isinstance(chronicle, Ok)
    assert chronicle.value == ()
    refusal = advance(store, finished, (), EngineConfig(), LATER)
    _assert_err(refusal, "VALIDATION_FAILED")


def test_unmet_conditions_terminate_at_the_ceiling(store: SqliteWorldStore) -> None:
    """A pool whose conditions never hold is the same fail-closed shape:
    nothing matures, the ceiling burns, LIMIT is the honest exit."""

    run = _fresh_run(store, seed=42)
    pool = (
        PoolEvent(
            kind="never_matures",
            narration="a door that never opens",
            conditions=(Condition(canonical_key="door", statement="open"),),
        ),
    )
    trace = advance(store, run, pool, EngineConfig(max_cycles=3), LATER)
    assert isinstance(trace, Ok)
    assert trace.value.outcome == OUTCOME_LIMIT
    assert [cycle.days_advanced for cycle in trace.value.cycles] == [1, 1, 1]
    assert store.get_run("run-1") is not None
    assert store.get_run("run-1").status == RunStatus.TERMINAL  # type: ignore[union-attr]


def test_the_engine_config_refuses_nonsense() -> None:
    """Nonsense knobs are refused at construction — a negative day count
    or a zero ceiling would make the fail-closed ceiling meaningless
    (both numbers are calibratable, Revisit W-4-2)."""

    with pytest.raises(ValueError):
        EngineConfig(days_per_cycle=-1)
    with pytest.raises(ValueError):
        EngineConfig(max_cycles=0)
    config = EngineConfig(days_per_cycle=3, max_cycles=4)
    assert config.days_per_cycle == 3 and config.max_cycles == 4


# ---------------------------------------------------------------------------
# 8 — run CRUD
# ---------------------------------------------------------------------------


def test_create_run_starts_at_the_zeroth_checkpoint(store: SqliteWorldStore) -> None:
    """Creation is the zeroth checkpoint: ``AT_CHECKPOINT`` / ``NOTICE`` /
    cursor 0 / version 1, with the seed and the trigger recorded. The
    same-shape replay is a no-op; a same-id different-shape call is a
    ``CONFLICT``."""

    _seed_world(store)
    first = store.create_run("run-1", "world-main", "turn-1", 42, NOW)
    assert isinstance(first, Ok)
    assert first.value.status == RunStatus.AT_CHECKPOINT
    assert first.value.checkpoint_kind == MomentKind.NOTICE
    assert first.value.cursor == 0
    assert first.value.state_version == 1
    assert first.value.seed == 42
    assert first.value.trigger_turn_id == "turn-1"

    replay = store.create_run("run-1", "world-main", "turn-1", 42, LATER)
    assert isinstance(replay, Ok) and replay.value == first.value
    _assert_err(
        store.create_run("run-1", "world-main", "turn-1", 43, NOW), "CONFLICT"
    )


def test_create_run_refuses_a_dangling_world(store: SqliteWorldStore) -> None:
    """A run naming a world that does not exist is refused — the table's
    own FK is the backstop, the store answers the value word."""

    _assert_err(
        store.create_run("run-1", "world-absent", None, 1, NOW), "NOT_FOUND"
    )


def test_state_version_is_monotonic_and_reads_are_ordered(
    store: SqliteWorldStore,
) -> None:
    """Every run write bumps ``state_version`` by exactly one, in
    creation order; ``list_runs`` answers the durable order
    (``created_at``, then ``run_id``); an unknown id reads ``None``."""

    _seed_world(store)
    for run_id in ("run-b", "run-a"):
        created = store.create_run(run_id, "world-main", None, 1, NOW)
        assert created.value is not None

    stepped = store.checkpoint_run("run-b", LATER)
    assert isinstance(stepped, Ok)
    assert (stepped.value.cursor, stepped.value.state_version) == (1, 2)
    terminal = store.terminalize_run("run-b", LATER)
    assert isinstance(terminal, Ok)
    assert terminal.value.state_version == 3

    # Durable read order: same created_at falls back to run_id ascending.
    runs = store.list_runs("world-main")
    assert [run.run_id for run in runs] == ["run-a", "run-b"]
    # A later creation sorts by time first.
    third = store.create_run("run-c", "world-main", None, 1, LATER)
    assert third.value is not None
    assert [run.run_id for run in store.list_runs("world-main")] == [
        "run-a",
        "run-b",
        "run-c",
    ]
    assert store.get_run("run-absent") is None


def test_checkpoint_run_refuses_a_terminal_run(store: SqliteWorldStore) -> None:
    """A TERMINAL run is absorbing for the checkpoint mover too — the
    store answers ``VALIDATION_FAILED`` instead of stepping a finished
    run (review W-1-2 LOW-1: this refusal previously carried no pin)."""

    _seed_world(store)
    created = store.create_run("run-term", "world-main", None, 1, NOW)
    assert created.value is not None
    terminal = store.terminalize_run("run-term", LATER)
    assert isinstance(terminal, Ok)
    _assert_err(
        store.checkpoint_run("run-term", LATER), "VALIDATION_FAILED"
    )


def test_terminalize_run_refuses_a_second_terminalization(
    store: SqliteWorldStore,
) -> None:
    """Terminalizing twice is refused and must not bump the version on
    an already-finished run (review W-1-2 LOW-1)."""

    _seed_world(store)
    created = store.create_run("run-term2", "world-main", None, 1, NOW)
    assert created.value is not None
    first = store.terminalize_run("run-term2", LATER)
    assert isinstance(first, Ok)
    _assert_err(
        store.terminalize_run("run-term2", LATER), "VALIDATION_FAILED"
    )
    assert (
        store.get_run("run-term2").state_version == first.value.state_version
    )


def test_run_movers_refuse_an_unknown_run_id(store: SqliteWorldStore) -> None:
    """Both movers answer the ``NOT_FOUND`` value word for an unknown
    run id — no raised lookup error (review W-1-2 LOW-1)."""

    _assert_err(store.checkpoint_run("run-absent", NOW), "NOT_FOUND")
    _assert_err(store.terminalize_run("run-absent", NOW), "NOT_FOUND")


# ---------------------------------------------------------------------------
# 9 — the registration
# ---------------------------------------------------------------------------


def test_the_registry_carries_the_six_world_objects() -> None:
    """Six canonical objects under ``OWNER_WORLD`` — the three identity
    rows, the event, the fact and W-1-2's run — each schema'd by the
    exported record class; the run carries no version field
    (``state_version`` is not a canonical version spelling)."""

    assert OWNER_WORLD == "world"
    entry = CANONICAL_OBJECTS["world_run"]
    assert entry.owner == OWNER_WORLD
    assert entry.version_field is None
    assert entry.schema is WorldRunRecord
    world_objects = [
        key
        for key, candidate in CANONICAL_OBJECTS.items()
        if candidate.owner == OWNER_WORLD
    ]
    assert world_objects == [
        "world",
        "world_actor",
        "world_conversation",
        "world_event",
        "world_state_fact",
        "world_run",
    ]


def test_global_content_tables_carry_the_seven_members() -> None:
    """W-1-2's run row joins the keep half (SEC-025's conservative
    reading): seven members, and the classification is registration —
    no sweep walks the run, nothing keeps it as retained either."""

    assert GLOBAL_CONTENT_TABLES == (
        "world_lore_fact",
        "world",
        "world_actor",
        "world_conversation",
        "world_event",
        "world_state_fact",
        "world_run",
    )
    assert "world_run" not in SWEPT_TABLES
    assert "world_run" not in RETAINED_TABLES


# ---------------------------------------------------------------------------
# 10 — the declared structure
# ---------------------------------------------------------------------------


def test_the_seven_steps_are_declared_in_order() -> None:
    """The seven steps exist as named constants, in the spec §4.2 v2.1
    order — the winch first (the caller's act), the deterministic body
    next, the two declared-not-simulated presentation halves last."""

    assert engine_steps.STEPS == (
        "1-winch",
        "2-time-advance",
        "3-event-maturity",
        "4-communication",
        "5-moment",
        "6-render",
        "7-wait",
    )
    assert engine_steps.STEP_RENDER == "6-render"
    assert engine_steps.STEP_WAIT == "7-wait"


def test_the_pool_defends_its_tuples_at_runtime() -> None:
    """This cut's own answer to the DC4T LOW-1 shape (the effects tuple
    that is not runtime-defended in elc.world.types): a sequence passed
    where PoolEvent declares a tuple is coerced at construction, so the
    record the engine hands the store carries exact tuples and the
    replay comparison downstream stays byte-equal."""

    event = PoolEvent(
        kind="list_shaped",
        narration="a caller passing lists",
        effects=[StateEffect(key="weather", statement="clear")],  # type: ignore[arg-type]
        conditions=[Condition(canonical_key="door", statement="open")],  # type: ignore[arg-type]
    )
    assert isinstance(event.effects, tuple)
    assert isinstance(event.conditions, tuple)
    assert event.effects == (StateEffect(key="weather", statement="clear"),)
    assert event.conditions == (Condition(canonical_key="door", statement="open"),)


def test_the_banner_claims_exactly_its_horizon() -> None:
    """The engine's banner is honest in both directions: the claim list
    (deterministic orchestration, replayable sequencing, durable run
    state, the double exit) and the refusal list (rendering, waiting,
    letters, reveal, DIRECTION, world clock, model generation) — the
    words are pinned so a silent widening reads red."""

    banner = " ".join((engine_package.__doc__ or "").split())
    for claimed in (
        "deterministic run orchestration",
        "replayable sequencing",
        "durable run state",
        "double exit",
        "``NOTICE`` checkpoints pause the run",
        "``RESPONSE`` terminates it",
        "never re-rolls",
    ):
        assert claimed in banner, claimed
    for refused in (
        "no presentation rendering",
        "no waiting behaviour",
        "no real letters",
        "no reveal face",
        "``DIRECTION`` word",
        "no world clock",
        "no model",
        "the engine invents nothing",
    ):
        assert refused in banner, refused
