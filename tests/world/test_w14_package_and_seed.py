"""W-1-4 — the world package face: the ``worlds/`` format, the strict
loader, and the host's idempotent builtin seed (six pin groups).

The living-world program's fifth cut (the adjudication chain
DEC-OPI-7e3744ee…36; the first shipped world package is Berrymoor).
The slice VAL groups, each a section below:

1. **strict loading** — the five refusal targets all refuse: bad JSON,
   a missing key, a value of the wrong shape, an unknown moment word
   (``DIRECTION`` cannot ride in through a package — W-2-2's word), and
   a supply family word outside the declared five; every refusal's
   message names the offending key or word;
2. **package truth** — the shipped ``worlds/berrymoor.json`` carries all
   seven sections with their pinned values (cast is migration 0019's
   penpal card, machine-cross-checked), the pool's state keys share
   nothing with the twelve builtin lore canonical keys (read live from
   ``elc.world_lore.content``), and the pool is engine-ready through
   ``to_event_pool`` with its ambient / chained structure;
3. **seed idempotence** — two opens answer the same row counts, the
   same-id different-shape create is still a ``CONFLICT``, and a cast
   persona with no card is refused before anything is written;
4. **fail-closed assembly** — a bad package directory and a missing
   directory each fail the open (``WorldPackageError``), the lore seed
   posture;
5. **engine E2E** — the real Berrymoor pool runs through the real
   engine on a host-seeded world: seed 18 walks the storm chain
   (``night_storm`` → ``roof_repair`` → ``nell_thanks``) inside one
   call to its RESPONSE stop (A2R DEC-…99: beats never pause), facts
   settle, the chronicle lands with the engine's source word, and a
   multi-seed scan over fresh databases reaches both exits (the
   RESPONSE terminals and the LIMIT ceilings — the always-mature
   ambient beats keep a barren stretch honest) with the flats event
   reachable;
6. **the ledgers** — the surface census and the AOCI code ledger track
   the package face (the two books this cut is required to carry).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.host import open_host
from elc.persona.provider import ScriptedPersonaProvider
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err
from elc.world.engine.engine import (
    ENGINE_SOURCE,
    OUTCOME_LIMIT,
    OUTCOME_TERMINAL,
    advance,
)
from elc.world.engine.types import EngineConfig, PoolEvent
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    SUPPLY_FAMILY_WORDS,
    WORLD_PACKAGE_VERSION,
    WorldPackageError,
    ensure_builtin_worlds,
    load_world_package,
)
from elc.world.store import SqliteWorldStore
from elc.world_lore.content import BERRYMOOR_WORLD_FACTS

REPO = Path(__file__).resolve().parents[2]
CENSUS_FILE = REPO / "tests" / "architecture" / "test_surface_census.py"
AOCI_FILE = REPO / "aoci.code.txt"
PACKAGE_PATH = BUILTIN_WORLDS_DIR / "berrymoor.json"

NOW = "2026-10-05T08:00:00+00:00"
PENPAL_PERSONA_ID = "persona-nell-alder"


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection with the production
    foreign-keys-ON profile — the persona refusal below is the
    database's own FK posture (the one ``elc.platform.db.connection``
    spells)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _valid_payload() -> dict[str, object]:
    """One minimal valid package payload — the negative tests mutate a
    copy of this and expect the loader to refuse the copy, never the
    shipped Berrymoor file. v5 (C2; the v4 face kept): every event
    carries both narrations and its story span (``days``), the package
    names the virtual world's day zero (``calendar_start``), and the
    version word is the loader's own constant. The optional v4/v5
    additions (a cast ``vignette``, a ``residents`` section, an
    ``initial_storylines`` section) are absent
    here on purpose — their absence is legal and pinned in the wr-9 /
    C2 files."""

    return {
        "world_id": "world-x",
        "name": "X",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2025-09-14",
        "setting": ["one", "two", "three"],
        "cast": [{"persona_id": PENPAL_PERSONA_ID, "name": "Nell"}],
        "event_pool": [
            {
                "kind": "k",
                "narration": "n",
                "narration_zh": "n-中文",
                "days": 1,
                "effects": [],
                "conditions": [],
                "moment": "NOTICE",
            }
        ],
        "supply": {"note": "declared-not-consumed", "families": ["DISC"]},
    }


def _write_package(tmp_path: Path, payload: object, name: str) -> Path:
    path = tmp_path / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fresh_store(db_path: Path) -> SqliteWorldStore:
    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return SqliteWorldStore(db, open_runtime_epoch(db))


def _drive_one_call(
    store: SqliteWorldStore,
    run_id: str,
    pool: tuple,
    seed: int,
) -> tuple[str, list[str], list[str]]:
    """Advance one run with a single ``advance`` call (A2R DEC-…99: the
    engine walks beats and stops inside one call — nothing to resume);
    the caller's safety cap is gone because there is no loop left to
    hang."""

    run = store.create_run(run_id, "world-berrymoor", None, seed, NOW).value
    assert run is not None
    trace = advance(store, run, pool, EngineConfig(), NOW)
    assert isinstance(trace, object)
    assert not isinstance(trace, Err), trace.error.message
    kinds = [
        cycle.selected for cycle in trace.value.cycles if cycle.selected
    ]
    return trace.value.outcome, [trace.value.outcome], kinds


# ---------------------------------------------------------------------------
# 1 — strict loading: the five refusal targets
# ---------------------------------------------------------------------------


def test_load_refuses_bad_json(tmp_path: Path) -> None:
    path = _write_package(tmp_path, "{ not json", "world-bad.json")
    result = load_world_package(path)
    assert isinstance(result, Err)
    assert "not valid JSON" in result.error.message


def test_load_refuses_missing_key(tmp_path: Path) -> None:
    payload = _valid_payload()
    del payload["supply"]
    path = _write_package(tmp_path, payload, "world-bad.json")
    result = load_world_package(path)
    assert isinstance(result, Err)
    assert "'supply'" in result.error.message


def test_load_refuses_bad_value_shape(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["event_pool"] = [{"kind": "k", "narration": 7}]
    path = _write_package(tmp_path, payload, "world-bad.json")
    result = load_world_package(path)
    assert isinstance(result, Err)
    assert "narration" in result.error.message


def test_load_refuses_unexpected_top_level_key(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["extra"] = 1
    path = _write_package(tmp_path, payload, "world-bad.json")
    result = load_world_package(path)
    assert isinstance(result, Err)
    assert "'extra'" in result.error.message


def test_load_refuses_unknown_moment_word_disclosing_it(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["event_pool"] = [
        {
            "kind": "k",
            "narration": "n",
            "narration_zh": "n-中文",
            "days": 1,
            "moment": "DIRECTION",
        }
    ]
    path = _write_package(tmp_path, payload, "world-bad.json")
    result = load_world_package(path)
    assert isinstance(result, Err)
    # The offending word rides the message, and W-2-2's word cannot ride
    # in through a package.
    assert "DIRECTION" in result.error.message


def test_load_refuses_family_word_outside_declared_vocabulary(
    tmp_path: Path,
) -> None:
    payload = _valid_payload()
    payload["supply"] = {"note": "n", "families": ["NAR"]}
    path = _write_package(tmp_path, payload, "world-bad.json")
    result = load_world_package(path)
    assert isinstance(result, Err)
    # NAR is a real curriculum family word — outside the declared five
    # is still a refusal, the word disclosed.
    assert "NAR" in result.error.message


# ---------------------------------------------------------------------------
# 2 — package truth: the shipped Berrymoor file
# ---------------------------------------------------------------------------


def test_real_package_carries_the_v4_sections() -> None:
    result = load_world_package(PACKAGE_PATH)
    assert not isinstance(result, Err), result.error.message
    package = result.value
    assert package.world_id == "world-berrymoor"
    assert package.name == "Berrymoor"
    assert package.version == WORLD_PACKAGE_VERSION
    assert package.calendar_start == "2025-09-14"
    assert 3 <= len(package.setting) <= 5
    assert all(paragraph.strip() for paragraph in package.setting)
    assert [(m.persona_id, m.name) for m in package.cast] == [
        (PENPAL_PERSONA_ID, "Nell Alder")
    ]
    assert 8 <= len(package.event_pool) <= 12
    assert {event.moment.value for event in package.event_pool} == {
        "NOTICE",
        "RESPONSE",
    }
    assert all(event.days >= 0 for event in package.event_pool)
    assert set(package.supply.families) <= set(SUPPLY_FAMILY_WORDS)
    assert package.supply.note.startswith("declared-not-consumed")


def test_cast_persona_is_migration_0019s_card(conn: sqlite3.Connection) -> None:
    """Machine cross-check: the package's cast persona is exactly the
    card migration 0019 seeds — the cast binds through a real card."""

    package = load_world_package(PACKAGE_PATH).value
    assert package.cast[0].persona_id == PENPAL_PERSONA_ID
    row = conn.execute(
        "SELECT 1 FROM character_card WHERE persona_id = ?",
        (PENPAL_PERSONA_ID,),
    ).fetchone()
    assert row is not None


def test_pool_state_keys_disjoint_from_lore_canonical_keys() -> None:
    """The cross-check pin: the pool's state keys share nothing with the
    twelve builtin lore canonical keys, read live from the lore
    content module (the projection and the lore never collide)."""

    lore_keys = {fact.canonical_key for fact in BERRYMOOR_WORLD_FACTS}
    assert len(BERRYMOOR_WORLD_FACTS) == 12
    pool = load_world_package(PACKAGE_PATH).value.to_event_pool()
    pool_keys = {
        effect.key
        for event in pool
        for effect in event.effects
    } | {
        condition.canonical_key
        for event in pool
        for condition in event.conditions
    }
    assert pool_keys
    assert pool_keys.isdisjoint(lore_keys)
    assert all("lore-" not in key for key in pool_keys)


def test_event_pool_carries_ambient_and_chained_structure() -> None:
    """``to_event_pool`` answers the engine's own shapes: ambient events
    (empty conditions, always mature), chained events whose conditions
    are earlier events' settled claims (the storm chain), both exits."""

    package = load_world_package(PACKAGE_PATH).value
    pool = package.to_event_pool()
    assert pool == package.event_pool
    assert all(isinstance(event, PoolEvent) for event in pool)
    ambient = [event for event in pool if not event.conditions]
    chained = [event for event in pool if event.conditions]
    assert len(ambient) >= 4
    assert len(chained) >= 3
    effect_pairs = {
        (effect.key, effect.statement)
        for event in pool
        for effect in event.effects
    }
    for event in chained:
        for condition in event.conditions:
            assert (condition.canonical_key, condition.statement) in effect_pairs


# ---------------------------------------------------------------------------
# 3 — seed idempotence
# ---------------------------------------------------------------------------


def test_open_host_seed_is_idempotent_across_reopens(tmp_path: Path) -> None:
    """Two opens over one app.db: the second seed is a no-op — same
    world row, same actor row, no chronicle or state rows."""

    counts: list[tuple[int, int, int, int]] = []
    for _ in range(2):
        host = open_host(
            tmp_path / "app.db", provider=ScriptedPersonaProvider()
        )
        try:
            world = host.world_store
            chronicle = host.db.execute(
                "SELECT COUNT(*) FROM world_event"
            ).fetchone()[0]
            facts = host.db.execute(
                "SELECT COUNT(*) FROM world_state_fact"
            ).fetchone()[0]
            counts.append(
                (
                    len(world.list_worlds()),
                    len(world.actors_of("world-berrymoor")),
                    chronicle,
                    facts,
                )
            )
        finally:
            host.close()
    assert counts[0] == counts[1] == (1, 1, 0, 0)


def test_same_world_id_different_shape_refused_after_seed(
    tmp_path: Path,
) -> None:
    host = open_host(tmp_path / "app.db", provider=ScriptedPersonaProvider())
    try:
        refused = host.world_store.create_world(
            "world-berrymoor", "Not Berrymoor", None, NOW
        )
        assert isinstance(refused, Err)
        assert refused.error.code == "CONFLICT"
    finally:
        host.close()


def test_missing_cast_persona_refused_before_any_write(tmp_path: Path) -> None:
    """A cast persona with no character card fails the seed loudly, and
    the refusal lands before any write: no world row exists after it."""

    directory = tmp_path / "worlds"
    directory.mkdir()
    payload = _valid_payload()
    payload["world_id"] = "world-orphan"
    payload["cast"] = [{"persona_id": "persona-nobody", "name": "Nobody"}]
    _write_package(directory, payload, "world-orphan.json")
    store = _fresh_store(tmp_path / "seed.db")
    with pytest.raises(WorldPackageError) as excinfo:
        ensure_builtin_worlds(
            store,
            directory,
            persona_exists=lambda persona_id: persona_id == PENPAL_PERSONA_ID,
        )
    assert "persona-nobody" in str(excinfo.value)
    assert store.list_worlds() == ()


# ---------------------------------------------------------------------------
# 4 — fail-closed assembly
# ---------------------------------------------------------------------------


def test_bad_package_directory_fails_the_open(tmp_path: Path) -> None:
    directory = tmp_path / "worlds"
    directory.mkdir()
    _write_package(directory, "{ not json", "world-bad.json")
    with pytest.raises(WorldPackageError):
        open_host(
            tmp_path / "app.db",
            provider=ScriptedPersonaProvider(),
            worlds_dir=directory,
        )


def test_missing_worlds_directory_fails_the_open(tmp_path: Path) -> None:
    with pytest.raises(WorldPackageError):
        open_host(
            tmp_path / "app.db",
            provider=ScriptedPersonaProvider(),
            worlds_dir=tmp_path / "absent",
        )


# ---------------------------------------------------------------------------
# 5 — engine E2E over the real pool
# ---------------------------------------------------------------------------


def test_engine_runs_the_real_berrymoor_pool_end_to_end(
    tmp_path: Path,
) -> None:
    """The host-seeded world runs the shipped pool through the real
    engine: seed 18 walks the whole storm chain inside one call — the
    two NOTICE beats, then the RESPONSE stop — the effects settle into
    the projection, and the chronicle carries the engine's own source
    word. The chain is the pool's own pacing: its conditions mature as
    the earlier beats settle, and the seed draws each link in order."""

    host = open_host(tmp_path / "app.db", provider=ScriptedPersonaProvider())
    try:
        pool = load_world_package(PACKAGE_PATH).value.to_event_pool()
        outcome, _outcomes, kinds = _drive_one_call(
            host.world_store, "run-e2e", pool, seed=18
        )
        assert outcome == OUTCOME_TERMINAL
        # The storm chain, in order, inside the one call.
        assert kinds[:3] == ["night_storm", "roof_repair", "nell_thanks"]
        facts = {
            (fact.canonical_key, fact.statement)
            for fact in host.world_store.current_facts("world-berrymoor")
        }
        assert (
            "alderson.roof",
            "the roof is patched and the workbench is dry again",
        ) in facts
        rows = host.db.execute(
            "SELECT event_id, kind, source FROM world_event ORDER BY rowid"
        ).fetchall()
        assert len(rows) == len(kinds)
        assert {row[2] for row in rows} == {ENGINE_SOURCE}
        run = host.world_store.get_run("run-e2e")
        assert run is not None
        assert run.status.value == "TERMINAL"
        assert run.state_version >= 2
    finally:
        host.close()


def test_seed_scan_reaches_both_exits_and_the_flats(
    tmp_path: Path,
) -> None:
    """Multi-seed scan over fresh databases (a run's dice are per-run;
    the world's facts are per-world, so each seed gets its own world):
    every run reaches an exit inside its own single call — RESPONSE
    terminals and LIMIT ceilings both occur (A2R DEC-…99: the
    always-mature ambient beats keep drawing until the ceiling when no
    RESPONSE comes) — and the flats event is seed-reachable. The storm
    chain's reachability is the E2E's pin above."""

    pool = load_world_package(PACKAGE_PATH).value.to_event_pool()
    all_outcomes: set[str] = set()
    tam_reached = False
    for seed in range(16):
        store = _fresh_store(tmp_path / f"scan-{seed}.db")
        ensure_builtin_worlds(
            store, persona_exists=lambda persona_id: True
        )
        outcome, _outcomes, kinds = _drive_one_call(
            store, f"run-{seed}", pool, seed=seed
        )
        assert outcome in (OUTCOME_TERMINAL, OUTCOME_LIMIT)
        all_outcomes.add(outcome)
        tam_reached = tam_reached or "tam_at_the_flats" in kinds
    assert all_outcomes == {OUTCOME_TERMINAL, OUTCOME_LIMIT}
    assert tam_reached


# ---------------------------------------------------------------------------
# 6 — the ledgers
# ---------------------------------------------------------------------------


def test_census_registers_the_package_loader() -> None:
    """The surface census's world row tracks the package face — the
    loader is registered where a reader looks for the live face."""

    text = CENSUS_FILE.read_text(encoding="utf-8")
    assert "load_world_package" in text
    assert "ensure_builtin_worlds" in text
    block = text.split("# W-1-0（活世界程序首刀）", 1)[1].split(
        'Row(\n        "world_lore",', 1
    )[0]
    assert "load_world_package" in block
    assert 'live_face="elc.world.store:SqliteWorldStore"' in block


def test_aoci_ledger_tracks_the_package_face() -> None:
    """The AOCI code ledger carries the cut: a ``worlds/`` section with
    the shipped package, the loader's own entry, and the host entry's
    seed face."""

    text = AOCI_FILE.read_text(encoding="utf-8")
    assert "===D:/english-learning-clean/worlds/===" in text
    assert "berrymoor.json[" in text
    assert "package.py[" in text
    assert "ensure_builtin_worlds" in text
