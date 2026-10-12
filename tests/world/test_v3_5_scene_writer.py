"""V3-5 — Scene + Dossier + POV Writer + ``narrative_passage`` +
SEGMENT COMMIT (TASK-OPI-be7b094f…34 / the opening ruling
DEC-OPI-be7b094f…32; VAL-OPI-be7b094f…36).

The Narrative V3 program's fifth cut: migration 0033's three tables
(``narrative_passage`` / ``reader_exposure`` / ``segment_commit``), the
SEGMENT COMMIT transaction (:mod:`elc.world.settlement`), the Scene
Planner's dossier chain (:mod:`elc.world.scene`), the POV Writer's
deterministic guards (:mod:`elc.world.writer`) and the Director's
crash/replay closure. The groups:

1. **the SEGMENT COMMIT's full chain** — one transaction lands the
   passage, the event (with its state settlement), the lineage row and
   the tick advance; ``is_last_segment`` flips the scene in the same
   transaction (the SCENE COMMIT alias); the chapter's first segment
   opens it with ``opened_at_tick`` from the transaction's own read of
   ``world.current_tick`` (#3 tick authority); a refused commit leaves
   zero rows (all-or-nothing);
2. **the replay law** — the same ``segment_key`` replays as a whole-group
   no-op (no second row, no tick re-advance), a different shape is a
   ``CONFLICT``, and a committed scene's stored segments still replay;
3. **the lineage read path** (the review's item 1 hard door) —
   ``story_time_of`` attributes a V3 event through the explicit row and
   answers ``Ok(None)`` for a legacy event;
4. **the exposure decoupling** (the review's item 2 hard door) — the
   commit transaction writes zero exposure rows, ``record_exposure`` is
   an independent idempotent face, and the module's SQL never names the
   actor-memory vocabulary (N-INV-005);
5. **the Writer's guards** — the must_hide leak refusal, the one-POV
   recheck, the empty-body/language refusals, the dossier prerequisite;
6. **the Scene Planner's chain** — the dossier's fields verbatim from
   the adopted Blueprint element, ``planned_start_tick`` from the
   canonical tick (not the element's), the retired-scene ban, the
   missing-plan / missing-element refusals;
7. **the Director's crash/replay closure** — the dangling chapter is
   reused, a matching ``PROPOSED`` revision is adopted, a differing one
   is rejected and the next revision minted;
8. **the transactionisation discharge** — ``activate_chapter`` judges
   inside its one ``BEGIN IMMEDIATE`` (the source pin) and does not
   bypass a held lock (the behaviour pin);
9. **the chain head and the scans** — the shared constants end at 0034
   (V3-5R's terminality ALTER), the three new modules build no SQL,
   import no package face and start from a cold interpreter, and the V2
   surfaces stay untouched.
"""

from __future__ import annotations

import ast
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import (
    RuntimeEpochFence,
    load_current_epoch,
    open_runtime_epoch,
)
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.director import Director
from elc.world.narrative import (
    ChapterStatus,
    PlanRevisionStatus,
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.scene import ScenePlanner
from elc.world.settlement import (
    CommitOutcome,
    commit_segment,
    record_exposure,
    story_time_of,
)
from elc.world.store import SqliteWorldStore
from elc.world.time import advance_current_tick, read_current_tick
from elc.world.types import StateEffect, WorldEvent
from elc.world.writer import PovWriter
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)

REPO = Path(__file__).resolve().parents[2]

NOW = "2026-10-12T00:00:00+00:00"
LATER = "2026-10-12T01:00:00+00:00"

TOWN = "world-town"
SCENE = "world-town-ch01-s01"

#: The town's durable identities (the V3-3R canonical vocabulary).
TOWN_NAMESPACE = frozenset({"actor-lia", "pc-you"})

# ---------------------------------------------------------------------------
# shared fixtures / helpers (the V3-4 suite's own shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db with the production profile's
    foreign-keys-ON posture (the dangling-reference refusals are the
    database's own)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def world_store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def cast_store(conn: sqlite3.Connection) -> SqliteCastStore:
    return SqliteCastStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def bible_store(conn: sqlite3.Connection) -> SqliteBibleStore:
    return SqliteBibleStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def narrative(conn: sqlite3.Connection) -> SqliteNarrativeStore:
    return SqliteNarrativeStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def director(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> Director:
    return Director(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


@pytest.fixture()
def planner(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> ScenePlanner:
    return ScenePlanner(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


@pytest.fixture()
def writer(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    narrative: SqliteNarrativeStore,
) -> PovWriter:
    return PovWriter(
        conn, narrative_store=narrative, world_store=world_store
    )


def _insert_card(conn: sqlite3.Connection, persona_id: str, name: str = "N") -> None:
    conn.execute(
        "INSERT INTO character_card ("
        " character_id, persona_id, name, identity, personality,"
        " background, speech_style, \"values\", boundaries, opening,"
        " scenario, generation_policy, lore_refs, revision, status,"
        " is_builtin, created_at, updated_at"
        ") VALUES (?, ?, ?, 'i', 'p', 'b', 's', 'v', 'bo', 'o',"
        " 'sc', 'auto', '', 1, 'active', 1, ?, ?)",
        (f"cpkg-{persona_id}", persona_id, name, NOW, NOW),
    )


def _seed_town(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """One hand-made world: the world row, one AI actor bound to a card
    with a POV-eligible profile, the reader's own durable character and
    the world's ``CURRENT`` Bible revision (the V3-4 fail-closed law's
    world authority)."""

    created = world_store.create_world(TOWN, "Town", None, NOW)
    assert isinstance(created, Ok)
    _insert_card(conn, "persona-lia", "Lia")
    conn.execute(
        "INSERT INTO world_actor (actor_id, world_id, persona_id,"
        " created_at) VALUES (?, ?, ?, ?)",
        ("actor-lia", TOWN, "persona-lia", NOW),
    )
    conn.commit()
    seeded = cast_store.seed_actor_profile(
        "actor-lia",
        TOWN,
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=1,
        long_term_drive="keep the shop open a winter longer",
        now=NOW,
    )
    assert isinstance(seeded, Ok)
    player = cast_store.seed_player_character(
        "pc-you",
        TOWN,
        name="You",
        background="a newcomer off the evening coach",
        location="the inn",
        state="tired",
        knowledge_refs="a rumour about the mill",
        now=NOW,
    )
    assert isinstance(player, Ok)
    seeded_bible = bible_store.seed_bible(
        f"{TOWN}-bible-r1",
        TOWN,
        BibleContent(premise="the town by the water"),
        NOW,
    )
    assert isinstance(seeded_bible, Ok)


def _scene(
    pov: str = "actor-lia",
    participants: tuple[str, ...] = ("actor-lia", "pc-you"),
    purpose: str = "first sight",
    must_hide: str = "the priced tools",
    **extras: Any,
) -> dict[str, Any]:
    """One Blueprint scene draft — the canonical ten keys."""

    return {
        "purpose": purpose,
        "place": "the bindery steps",
        "pov_actor_id": pov,
        "participants": list(participants),
        "planned_start_tick": 0,
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if you linger",
        "revealable": "the ledger's back page",
        "must_hide": must_hide,
        **extras,
    }


def _blueprint(
    scenes: list[dict[str, Any]] | None = None,
    goal: str = "the newcomer and the shopkeeper truly meet",
) -> dict[str, Any]:
    """One Blueprint-shaped payload — the nine chapter fields."""

    if scenes is None:
        scenes = [_scene()]
    return {
        "goal": goal,
        "dramatic_question": "Will the shop's silence open to a stranger?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the first hard frost presses the order book",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "a repair job, maybe",
        "chapter_questions_to_advance": "who is the letter from?",
        "scenes": scenes,
    }


def _chapter_fields(
    goal: str = "the newcomer and the shopkeeper truly meet",
) -> dict[str, Any]:
    """The eight chapter-side fields one plan revision carries (the
    payload minus ``scenes``) — the residue constructions below spell
    exactly what the Director's creation would write."""

    payload = _blueprint(goal=goal)
    return {
        key: payload[key]
        for key in (
            "goal",
            "dramatic_question",
            "planned_start_tick",
            "planned_end_tick",
            "closing_pressure",
            "desired_development",
            "soft_outcomes",
            "chapter_questions_to_advance",
        )
    }


def _opened_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    *,
    scenes: list[dict[str, Any]] | None = None,
) -> None:
    """Seed the town and plan chapter 1 (the Plan face in, the canon
    face empty — the Director's own posture)."""

    _seed_town(conn, world_store, cast_store, bible_store)
    opened = director.open_next_chapter(TOWN, _blueprint(scenes=scenes), NOW)
    assert isinstance(opened, Ok)


def _active_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    *,
    scenes: list[dict[str, Any]] | None = None,
) -> str:
    """The full pre-commit chain: town seeded, chapter planned, the scene
    opened (dossier adopted, scene ACTIVE)."""

    _opened_chapter(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        scenes=scenes,
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    return SCENE


def _commit(
    conn: sqlite3.Connection,
    narrative: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    *,
    scene_id: str = SCENE,
    segment_seq: int = 1,
    body: str = "The bell above the door answers before her voice does.",
    language: str = "en",
    participants: tuple[str, ...] = ("actor-lia", "pc-you"),
    effects: tuple[StateEffect, ...] = (),
    narration: str = "the two meet at the bindery steps",
    duration_ticks: int = 3,
    is_last_segment: bool = False,
    now: str = NOW,
):
    return commit_segment(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        scene_id=scene_id,
        segment_seq=segment_seq,
        body=body,
        language=language,
        participants=participants,
        effects=effects,
        narration=narration,
        duration_ticks=duration_ticks,
        is_last_segment=is_last_segment,
        now=now,
    )


def _row_counts(conn: sqlite3.Connection, tables: tuple[str, ...]) -> dict[str, int]:
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }


# ---------------------------------------------------------------------------
# 1. the SEGMENT COMMIT's full chain
# ---------------------------------------------------------------------------


def test_the_segment_commit_lands_the_full_chain(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """One commit: passage + event + state settlement + lineage row +
    tick advance, and the chapter opens with the transaction's own read
    of ``world.current_tick`` — every field pinned."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    result = _commit(
        conn,
        narrative,
        world_store,
        effects=(StateEffect(key="door.bell", statement="answered"),),
        narration="the bell answers",
        is_last_segment=True,
    )
    assert isinstance(result, Ok)
    outcome = result.value
    assert isinstance(outcome, CommitOutcome)
    assert outcome.passage_id == f"{SCENE}-p0001"
    assert outcome.event_id == f"{SCENE}-e0001"
    assert outcome.commit_id == f"sg:{SCENE}:0001"
    assert outcome.actual_start_tick == 0
    assert outcome.actual_end_tick == 3
    assert outcome.scene_committed is True
    assert outcome.chapter_activated is True

    passage = conn.execute(
        "SELECT passage_id, scene_id, segment_seq, body, language,"
        " outcome_ref, created_at_tick, state_version"
        " FROM narrative_passage WHERE passage_id = ?",
        (outcome.passage_id,),
    ).fetchone()
    assert passage is not None
    assert passage[0] == f"{SCENE}-p0001"
    assert passage[1] == SCENE
    assert passage[2] == 1
    assert passage[3] == (
        "The bell above the door answers before her voice does."
    )
    assert passage[4] == "en"
    assert passage[5] is None  # outcome_ref: V3-6's arm, NULL here
    assert passage[6] == 3  # created_at_tick = actual_end_tick
    assert passage[7] == 1

    event = conn.execute(
        "SELECT world_id, kind, narration, effects, occurred_at, source,"
        " participants, run_id FROM world_event WHERE event_id = ?",
        (outcome.event_id,),
    ).fetchone()
    assert event is not None
    assert event[0] == TOWN
    assert event[1] == "segment"
    assert event[2] == "the bell answers"
    assert event[3] == '[{"key":"door.bell","statement":"answered"}]'
    assert event[4] == NOW  # the legacy ISO stamp rides the caller's now
    assert event[5] == "v3-segment"
    assert event[6] == '["actor-lia","pc-you"]'
    assert event[7] is None

    fact = conn.execute(
        "SELECT fact_id, canonical_key, statement, status"
        " FROM world_state_fact"
    ).fetchall()
    assert fact == [
        (f"{outcome.event_id}:door.bell", "door.bell", "answered", "CURRENT")
    ]

    lineage = conn.execute(
        "SELECT commit_id, kind, scene_id, segment_seq, passage_id,"
        " actual_start_tick, actual_end_tick, event_id FROM segment_commit"
    ).fetchall()
    assert lineage == [
        (
            f"sg:{SCENE}:0001",
            "SEGMENT",
            SCENE,
            1,
            outcome.passage_id,
            0,
            3,
            outcome.event_id,
        )
    ]

    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 3
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.status is ChapterStatus.ACTIVE
    assert chapter.opened_at_tick == 0  # the transaction's own read
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.COMMITTED
    # V3-5R: the span arm wrote the scene's actual interval in the same
    # transaction — the last segment's own start/end (one UPDATE).
    assert scene.actual_start_tick == 0
    assert scene.actual_end_tick == 3


def test_the_commit_advances_the_tick_by_the_duration(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Segments chain: the second segment's ``actual_start_tick`` is the
    first's end — the tick advances exactly by each duration (STATE §26:
    start = the tick before the advance, end = after it)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    second = _commit(
        conn, narrative, world_store, segment_seq=2, duration_ticks=5
    )
    assert isinstance(second, Ok)
    assert second.value.actual_start_tick == 3
    assert second.value.actual_end_tick == 8
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 8


def test_the_chapter_opens_with_the_transactions_own_tick(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The #3 lifecycle tick authority: the world's tick, pre-advanced by
    a prior commit-shaped move, is what the opening stamps — the value
    rides from the transaction's own in-transaction read, never a
    caller's pre-computed number."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    advanced = advance_current_tick(conn, TOWN, 7)
    assert isinstance(advanced, Ok)
    conn.commit()
    result = _commit(conn, narrative, world_store)
    assert isinstance(result, Ok)
    assert result.value.actual_start_tick == 7
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.opened_at_tick == 7


def test_a_refused_commit_leaves_zero_rows(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """All-or-nothing (N-R-INV-004): a refused commit (a negative
    duration — the tick never moves backwards) writes nothing — zero
    passage / event / lineage rows, the tick unmoved, the scene still
    ACTIVE, the chapter still PLANNED."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    refused = _commit(conn, narrative, world_store, duration_ticks=-1)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "negative" in refused.error.message
    assert _row_counts(
        conn, ("narrative_passage", "world_event", "world_state_fact", "segment_commit")
    ) == {
        "narrative_passage": 0,
        "world_event": 0,
        "world_state_fact": 0,
        "segment_commit": 0,
    }
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 0
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.ACTIVE
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.status is ChapterStatus.PLANNED
    assert chapter.opened_at_tick is None


def test_a_non_participant_identity_is_refused(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-3R identity freeze at the commit: a participant word
    outside the canonical namespace (a persona id, a resident name) is
    refused ``VALIDATION_FAILED`` naming the word — and nothing lands."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    for word in ("persona-lia", "Old Tam"):
        refused = _commit(
            conn,
            narrative,
            world_store,
            participants=("actor-lia", "pc-you", word),
        )
        assert isinstance(refused, Err), word
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
        assert word in refused.error.message
    assert _row_counts(conn, ("narrative_passage", "segment_commit")) == {
        "narrative_passage": 0,
        "segment_commit": 0,
    }


def test_a_segment_on_a_non_active_scene_is_refused(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """Only an ACTIVE scene takes segment commits: the planned scene's
    commit refuses ``VALIDATION_FAILED`` before anything lands."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    refused = _commit(conn, narrative, world_store)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "ACTIVE" in refused.error.message
    assert conn.execute("SELECT COUNT(*) FROM narrative_passage").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 2. the replay law
# ---------------------------------------------------------------------------


def test_a_replayed_segment_key_is_a_whole_group_no_op(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The same segment_key replayed lands nothing new: the stored
    outcome rides back, row counts and the tick stay put, and the scene
    / chapter counters are untouched by the replay."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    tables = (
        "narrative_passage",
        "world_event",
        "world_state_fact",
        "segment_commit",
    )
    before = _row_counts(conn, tables)
    scene_before = narrative.get_scene(SCENE)
    chapter_before = narrative.get_chapter("world-town-ch01")

    replay = _commit(conn, narrative, world_store, duration_ticks=3, now=LATER)
    assert isinstance(replay, Ok)
    assert replay.value == first.value
    assert _row_counts(conn, tables) == before
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 3
    assert narrative.get_scene(SCENE) == scene_before
    assert narrative.get_chapter("world-town-ch01") == chapter_before


def test_a_replayed_segment_with_a_different_shape_conflicts(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay's shape law: a different body (or narration /
    participants / effects / duration) is a ``CONFLICT`` — committed
    segments are append-only and do not rewrite; the stored rows stay
    byte-identical."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    for override in (
        {"body": "A different telling entirely."},
        {"narration": "a different chronicle line"},
        {"duration_ticks": 4},
        {"participants": ("actor-lia",)},
        {"effects": (StateEffect(key="door.bell", statement="slammed"),)},
    ):
        refused = _commit(conn, narrative, world_store, **override)
        assert isinstance(refused, Err), override
        assert refused.error.code is DomainErrorCode.CONFLICT, override
        assert "append-only" in refused.error.message
    assert conn.execute(
        "SELECT body FROM narrative_passage WHERE passage_id = ?",
        (first.value.passage_id,),
    ).fetchone()[0] == (
        "The bell above the door answers before her voice does."
    )
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 3


def test_a_replay_after_the_scene_committed_is_still_answered(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay read runs before the fresh path's ACTIVE gate: the
    scene's last segment replayed after the scene is COMMITTED answers
    the stored outcome (armed with ``scene_committed = True``), not a
    status refusal."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(
        conn, narrative, world_store, duration_ticks=3, is_last_segment=True
    )
    assert isinstance(first, Ok)
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.COMMITTED

    replay = _commit(
        conn, narrative, world_store, duration_ticks=3, is_last_segment=True
    )
    assert isinstance(replay, Ok)
    assert replay.value.scene_committed is True
    assert replay.value.passage_id == first.value.passage_id
    # And a NEW segment on the committed scene is refused (the gate is
    # only bypassed for the stored key).
    refused = _commit(conn, narrative, world_store, segment_seq=2)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED


# ---------------------------------------------------------------------------
# 3. the lineage read path (the review's item 1 hard door)
# ---------------------------------------------------------------------------


def test_story_time_of_attributes_the_v3_event(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3 event's story time comes from the explicit lineage row —
    ``(actual_start_tick, actual_end_tick)`` — never from the id's
    naming and never from ``occurred_at`` (no legacy ISO ever answers
    here)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    result = _commit(conn, narrative, world_store, duration_ticks=4)
    assert isinstance(result, Ok)
    span = story_time_of(conn, result.value.event_id)
    assert isinstance(span, Ok)
    assert span.value == (0, 4)


def test_story_time_of_answers_none_for_a_legacy_event(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> None:
    """A legacy V2 event holds no lineage row — the honest ``Ok(None)``:
    its ``occurred_at`` is a V2 ISO moment and is deliberately not
    consulted as world time (the review's item 1)."""

    _seed_town(conn, world_store, cast_store, bible_store)
    legacy = world_store.record_event(
        WorldEvent(
            event_id="event-v2-1",
            world_id=TOWN,
            kind="beat",
            narration="the mill wheel turns",
            effects=(),
            occurred_at=NOW,
            source="test",
        )
    )
    assert isinstance(legacy, Ok)
    span = story_time_of(conn, "event-v2-1")
    assert isinstance(span, Ok)
    assert span.value is None
    missing = story_time_of(conn, "event-nowhere")
    assert isinstance(missing, Ok)
    assert missing.value is None


# ---------------------------------------------------------------------------
# 4. the exposure decoupling (the review's item 2 hard door)
# ---------------------------------------------------------------------------


def test_the_commit_writes_zero_exposure_rows(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """A passage commit is not a reading: the SEGMENT COMMIT transaction
    leaves the exposure table empty — exposure lands only through the
    independent face."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    result = _commit(conn, narrative, world_store, is_last_segment=True)
    assert isinstance(result, Ok)
    assert conn.execute("SELECT COUNT(*) FROM reader_exposure").fetchone()[0] == 0


def test_record_exposure_is_independent_and_idempotent(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The independent face: one row per (passage, reader) — first record
    wins (a replay answers the stored row, ``exposed_at`` untouched),
    while a second reader lands its own row; ``exposed_at`` is the
    caller's ISO stamp, not story time."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    result = _commit(conn, narrative, world_store)
    assert isinstance(result, Ok)
    passage_id = result.value.passage_id

    recorded = record_exposure(
        conn, passage_id=passage_id, reader_id="reader-one", now=NOW
    )
    assert isinstance(recorded, Ok)
    assert recorded.value.exposure_id == f"{passage_id}-xreader-one"
    assert recorded.value.passage_id == passage_id
    assert recorded.value.reader_id == "reader-one"
    assert recorded.value.exposed_at == NOW
    assert recorded.value.state_version == 1

    replay = record_exposure(
        conn, passage_id=passage_id, reader_id="reader-one", now=LATER
    )
    assert isinstance(replay, Ok)
    assert replay.value == recorded.value  # the first exposure stands
    assert conn.execute("SELECT COUNT(*) FROM reader_exposure").fetchone()[0] == 1

    second_reader = record_exposure(
        conn, passage_id=passage_id, reader_id="reader-two", now=NOW
    )
    assert isinstance(second_reader, Ok)
    assert conn.execute("SELECT COUNT(*) FROM reader_exposure").fetchone()[0] == 2


def test_record_exposure_refuses_a_dangling_passage(
    conn: sqlite3.Connection,
) -> None:
    """The table's own FK is the backstop: an exposure of a passage that
    does not exist refuses ``NOT_FOUND`` (the three-family mapping) and
    lands nothing."""

    refused = record_exposure(
        conn, passage_id="passage-nowhere", reader_id="reader-one", now=NOW
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert conn.execute("SELECT COUNT(*) FROM reader_exposure").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# the source scans (the hard doors' machine halves)
# ---------------------------------------------------------------------------

_SETTLEMENT_SOURCE = (SRC_ROOT / "world" / "settlement.py").read_text(
    encoding="utf-8"
)
_SETTLEMENT_TREE = ast.parse(_SETTLEMENT_SOURCE, filename="settlement.py")
_SCENE_SOURCE = (SRC_ROOT / "world" / "scene.py").read_text(encoding="utf-8")
_SCENE_TREE = ast.parse(_SCENE_SOURCE, filename="scene.py")
_WRITER_SOURCE = (SRC_ROOT / "world" / "writer.py").read_text(encoding="utf-8")
_WRITER_TREE = ast.parse(_WRITER_SOURCE, filename="writer.py")
_NARRATIVE_STORE_SOURCE = (
    SRC_ROOT / "world" / "narrative" / "store.py"
).read_text(encoding="utf-8")
_NARRATIVE_STORE_TREE = ast.parse(
    _NARRATIVE_STORE_SOURCE, filename="narrative_store.py"
)


def _sql_constants(tree: ast.AST) -> list[str]:
    """Every SQL-shaped string constant in one module — a constant that
    *starts* with a DML keyword (the v3_1/v3_4 scans'手法: prose that
    merely mentions a word cannot false-positive)."""

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.match(r"(?i)^\s*(select|insert|update|delete)\b", node.value):
                found.append(node.value)
    return found


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def test_the_exposure_sql_never_names_actor_memory_or_belief() -> None:
    """N-INV-005 / the review's item 2, machine-checked: no SQL constant
    in the settlement module names the actor-memory / belief vocabulary
    this cut deliberately does not ship."""

    statements = _sql_constants(_SETTLEMENT_TREE)
    assert statements, "settlement carries no SQL at all — wrong source?"
    for text in statements:
        assert "actor_memory" not in text, text
        assert "belief" not in text, text


def test_the_commit_body_never_touches_the_exposure_table() -> None:
    """The decoupling's structural half: neither the public commit face
    nor its in-transaction body mentions ``reader_exposure`` — the
    exposure writes live only on the independent face."""

    for name in ("commit_segment", "_commit_segment_tx"):
        fn = _function(_SETTLEMENT_TREE, name)
        for node in ast.walk(fn):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "reader_exposure" not in node.value, (name, node.value)
    exposure_fn = _function(_SETTLEMENT_TREE, "record_exposure")
    exposure_sql = [
        node.value
        for node in ast.walk(exposure_fn)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.strip().upper().startswith(
            ("SELECT", "INSERT", "UPDATE", "DELETE")
        )
    ]
    assert any("reader_exposure" in text for text in exposure_sql)


def _all_constants(tree: ast.AST) -> list[str]:
    """Every string constant in one node — the transaction-boundary
    scans' own collector (the V3-5 review's F2/F3: the DML-shaped
    filter of :func:`_sql_constants` cannot see a stray ``"COMMIT"`` /
    ``"BEGIN IMMEDIATE"`` constant, so the one-transaction pins below
    read the *unfiltered* constant set)."""

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def test_the_group_transaction_has_one_begin_and_one_commit() -> None:
    """NCP-3 is ONE short transaction (N-R-INV-004): the public
    ``commit_segment`` opens exactly one ``BEGIN IMMEDIATE`` and lands
    exactly one ``COMMIT``; its body (``_commit_segment_tx``) carries
    **no transaction-control constant at all** — the arms and every
    write ride inside the caller's transaction (the same owner/arm
    split the narrative store's flips spell). The body half reads the
    unfiltered constant set (the V3-5 review's F2: a DML-shaped scan
    cannot see a stray ``"COMMIT"``)."""

    public = _function(_SETTLEMENT_TREE, "commit_segment")
    constants = _all_constants(public)
    assert constants.count("BEGIN IMMEDIATE") == 1
    assert constants.count("COMMIT") == 1
    body = _function(_SETTLEMENT_TREE, "_commit_segment_tx")
    assert _sql_constants(body), "the body carries no SQL — wrong source?"
    for text in _all_constants(body):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text


def test_the_span_arm_and_the_chapter_opening_are_the_commits_own_arms() -> None:
    """The SCENE COMMIT alias, machine-checked (the V3-5R arm set):
    within the commit body the scene's write is the narrative store's
    **span arm** — ``_advance_scene_actual_span_tx`` (the actual
    interval and, on the scene's last segment, the ``ACTIVE →
    COMMITTED`` flip in one UPDATE; TASK-OPI-dc1bafdf…13) — and the
    chapter's opening is ``_flip_chapter_activated_tx``, both called
    inside the same one transaction, never as separate faces. The
    lifecycle-only ``_flip_scene_committed_tx`` is deliberately **not**
    the commit's arm any more (the explicit ``commit_scene`` face keeps
    it — it writes no span). The arms themselves carry no
    transaction-control constant (the unfiltered set — the V3-5 review's
    F3)."""

    body = _function(_SETTLEMENT_TREE, "_commit_segment_tx")
    called = {
        node.attr
        for node in ast.walk(body)
        if isinstance(node, ast.Attribute)
    }
    assert "_advance_scene_actual_span_tx" in called
    assert "_flip_chapter_activated_tx" in called
    assert "_flip_scene_committed_tx" not in called
    for name in (
        "_advance_scene_actual_span_tx",
        "_flip_chapter_activated_tx",
        "_flip_scene_committed_tx",
    ):
        arm = _function(_NARRATIVE_STORE_TREE, name)
        assert _sql_constants(arm), (name, "the arm carries no SQL")
        for text in _all_constants(arm):
            assert text != "BEGIN IMMEDIATE", (name, text)
            assert text != "COMMIT", (name, text)
            assert text != "ROLLBACK", (name, text)


def test_activate_chapter_judges_inside_its_transaction() -> None:
    """The 0029 race-free obligation's discharge (the V3-1 review's
    MEDIUM — DEC-OPI-be7b094f…32): ``activate_chapter`` opens its one
    ``BEGIN IMMEDIATE`` and the check-and-flip arm runs inside it — the
    checks are no longer a read-then-act outside the CAS (the V3-1
    staging's posture, kept as history in the docstring)."""

    fn = _function(_NARRATIVE_STORE_TREE, "activate_chapter")
    events: list[tuple[int, str]] = []
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value == "BEGIN IMMEDIATE"
        ):
            events.append((node.lineno, "begin"))
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "_flip_chapter_activated_tx"
        ):
            events.append((node.lineno, "arm"))
    assert [kind for _, kind in sorted(events)] == ["begin", "arm"]
    # And the prerequisites are the arm's own words — the checks moved
    # into the transaction with the flip.
    arm = _function(_NARRATIVE_STORE_TREE, "_flip_chapter_activated_tx")
    constants = [
        node.value
        for node in ast.walk(arm)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert any("ADOPTED Blueprint" in text for text in constants)
    assert any("one chapter at a time" in text for text in constants)


def test_the_three_new_modules_import_no_package_and_build_no_sql() -> None:
    """The scans: none of the three new modules imports the Package face
    (the durable rows are the runtime authority) and no SQL-shaped
    constant carries string interpolation (fixed literals and parameter
    binding only, the house posture)."""

    for tree, name in (
        (_SETTLEMENT_TREE, "settlement.py"),
        (_SCENE_TREE, "scene.py"),
        (_WRITER_TREE, "writer.py"),
    ):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("elc.world.package"), (
                        name,
                        alias.name,
                    )
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("elc.world.package"), (
                    name,
                    node.module,
                )
        for text in _sql_constants(tree):
            assert "{" not in text, (name, text)
            assert "}" not in text, (name, text)


def test_the_new_modules_import_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline): a fresh interpreter
    importing each new module first must succeed; no import cycle may
    hide behind a lucky test-session order."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    for module in (
        "elc.world.settlement",
        "elc.world.scene",
        "elc.world.writer",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, (module, proc.stderr)


# ---------------------------------------------------------------------------
# 5. the Writer's guards
# ---------------------------------------------------------------------------


def test_the_writer_writes_a_clean_segment(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    writer: PovWriter,
) -> None:
    """The clean path: the body rides to the passage verbatim, the
    event's participants are the dossier's own tuple, the narration is
    the baseline's prose (the segment's chronicle line is its text) and
    the effects are empty (the deterministic baseline produces none)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    result = writer.write_segment(
        SCENE,
        body="The bell answers; she looks up from the press.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=True,
        now=NOW,
    )
    assert isinstance(result, Ok)
    passage = conn.execute(
        "SELECT body FROM narrative_passage WHERE passage_id = ?",
        (result.value.passage_id,),
    ).fetchone()
    assert passage is not None
    assert passage[0] == "The bell answers; she looks up from the press."
    event = conn.execute(
        "SELECT narration, effects, participants FROM world_event"
        " WHERE event_id = ?",
        (result.value.event_id,),
    ).fetchone()
    assert event is not None
    assert event[0] == "The bell answers; she looks up from the press."
    assert event[1] == "[]"
    assert event[2] == '["actor-lia","pc-you"]'
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.COMMITTED


def test_the_writer_refuses_a_leaking_body(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    writer: PovWriter,
) -> None:
    """The secret-leak guard: a body carrying a non-empty ``must_hide``
    fragment (``"the priced tools"`` — the schema's own dossier words)
    is refused ``VALIDATION_FAILED`` naming the fragment, and nothing
    lands; a revealable phrase is no obligation (its absence is
    fine)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    leaked = writer.write_segment(
        SCENE,
        body="On the shelf behind her sit the priced tools, waiting.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(leaked, Err)
    assert leaked.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "priced tools" in leaked.error.message
    assert "must_hide" in leaked.error.message
    assert conn.execute("SELECT COUNT(*) FROM narrative_passage").fetchone()[0] == 0

    # The same must_hide split across a sentence break still refuses on
    # each non-empty fragment's own containment.
    partial = writer.write_segment(
        SCENE,
        body="The tools on the shelf are priced to sell.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(partial, Ok)  # "the priced tools" is not contained
    assert conn.execute("SELECT COUNT(*) FROM narrative_passage").fetchone()[0] == 1


def test_the_writer_refuses_an_empty_body_or_language(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    writer: PovWriter,
) -> None:
    """A segment carries prose and a declared language: an empty /
    blank body or language is refused ``VALIDATION_FAILED`` naming the
    field, with zero rows written."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    for body, language, needle in (
        ("", "en", "body"),
        ("   ", "en", "body"),
        ("The bell answers.", "", "language"),
        ("The bell answers.", "  ", "language"),
    ):
        refused = writer.write_segment(
            SCENE,
            body=body,
            language=language,
            segment_seq=1,
            duration_ticks=2,
            is_last_segment=False,
            now=NOW,
        )
        assert isinstance(refused, Err), (body, language)
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
        assert needle in refused.error.message, (body, language)
    assert conn.execute("SELECT COUNT(*) FROM narrative_passage").fetchone()[0] == 0


def test_the_writer_rechecks_one_pov_per_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    writer: PovWriter,
) -> None:
    """The recheck is load-bearing: a dossier whose ``pov_actor_id`` is
    not among its ``participants`` (a forged row the schema would never
    mint, constructed here through the store's own faces) is refused —
    one POV per scene, and the POV is present in her own scene."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    narrative.create_scene(SCENE, "world-town-ch01", 1, NOW)
    created = narrative.create_dossier(
        f"{SCENE}-d1",
        SCENE,
        1,
        pov_actor_id="pc-you",
        participants=("actor-lia",),
        place="the shop",
        planned_start_tick=0,
        revealable="the ledger",
        must_hide="the debt",
        entry_goals="greet",
        exit_condition="the greeting lands",
        elasticity="may run long",
        now=NOW,
    )
    assert isinstance(created, Ok)
    adopted = narrative.adopt_dossier(f"{SCENE}-d1", NOW, expected_state_version=1)
    assert isinstance(adopted, Ok)
    refused = writer.write_segment(
        SCENE,
        body="The bell answers.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "not among its participants" in refused.error.message
    assert "POV" in refused.error.message


def test_the_writer_refuses_a_scene_without_an_adopted_dossier(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    writer: PovWriter,
) -> None:
    """The Writer writes from the current plan: a scene holding no
    ``ADOPTED`` Dossier is refused ``VALIDATION_FAILED`` naming the
    Dossier, before any write."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    narrative.create_scene(SCENE, "world-town-ch01", 1, NOW)
    refused = writer.write_segment(
        SCENE,
        body="The bell answers.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "ADOPTED Dossier" in refused.error.message
    dangling = writer.write_segment(
        "scene-nowhere",
        body="The bell answers.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(dangling, Err)
    assert dangling.error.code is DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 6. the Scene Planner's chain
# ---------------------------------------------------------------------------


def test_open_scene_lands_the_dossier_chain(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The full deterministic chain: dossier revision 1 assembled from
    the adopted Blueprint element **verbatim** (every field — including
    the identity of the located element itself), adopted, and the scene
    activated (the #4 prerequisite satisfied by the dossier the planner
    just landed)."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    plan = narrative.adopted_plan("world-town-ch01")
    assert plan is not None
    element = plan.scenes[0]

    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    assert opened.value.element == element  # the plan row's own element
    assert opened.value.dossier.dossier_id == f"{SCENE}-d1"
    assert opened.value.dossier.scene_id == SCENE
    assert opened.value.dossier.dossier_revision == 1
    assert opened.value.dossier.status is PlanRevisionStatus.ADOPTED
    assert opened.value.dossier.pov_actor_id == element["pov_actor_id"]
    assert opened.value.dossier.participants == tuple(element["participants"])
    assert opened.value.dossier.place == element["place"]
    assert opened.value.dossier.entry_goals == element["entry_goals"]
    assert opened.value.dossier.exit_condition == element["exit_condition"]
    assert opened.value.dossier.elasticity == element["elasticity"]
    assert opened.value.dossier.revealable == element["revealable"]
    assert opened.value.dossier.must_hide == element["must_hide"]
    assert opened.value.dossier.planned_start_tick == 0  # the fresh tick
    assert opened.value.scene.status is SceneStatus.ACTIVE
    assert opened.value.scene.actual_start_tick is None  # the commits'
    assert opened.value.scene.actual_end_tick is None
    # The stores agree (the same facts read back).
    assert narrative.adopted_dossier(SCENE) == opened.value.dossier


def test_open_scene_plans_from_the_canonical_tick(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The dossier's ``planned_start_tick`` is the canonical story time
    the context reads — **not** the element's Blueprint guess (0 here):
    the world's reality, not the plan's older window."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    advanced = advance_current_tick(conn, TOWN, 7)
    assert isinstance(advanced, Ok)
    conn.commit()
    plan = narrative.adopted_plan("world-town-ch01")
    assert plan is not None
    assert plan.scenes[0]["planned_start_tick"] == 0  # the element's guess

    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    assert opened.value.dossier.planned_start_tick == 7


def test_open_scene_refuses_a_missing_blueprint(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    planner: ScenePlanner,
) -> None:
    """A chapter without an ``ADOPTED`` Blueprint cannot assemble a
    dossier — ``VALIDATION_FAILED`` naming the missing plan, nothing
    written."""

    _seed_town(conn, world_store, cast_store, bible_store)
    narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    narrative.create_scene(SCENE, "world-town-ch01", 1, NOW)
    refused = planner.open_scene(SCENE, NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "ADOPTED Blueprint" in refused.error.message
    assert narrative.dossiers_of(SCENE) == ()
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.PLANNED


def test_open_scene_refuses_a_plan_without_its_element(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The content source law: an adopted revision whose ``scenes``
    table carries no element for the scene (here: an empty table —
    constructible only through the store face, the Director's own schema
    refuses it) refuses ``VALIDATION_FAILED`` naming the plan, and the
    scene is not activated."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    # A revision with an empty scenes table cannot come from the
    # Director; construct it through the store (the honest corrupted-row
    # arm the planner must answer).
    created = narrative.create_plan(
        "world-town-ch01-bp-r2",
        "world-town-ch01",
        2,
        **_chapter_fields(),
        scenes=(),
        now=LATER,
    )
    assert isinstance(created, Ok)
    adopted = narrative.adopt_plan(
        "world-town-ch01-bp-r2", LATER, expected_state_version=1
    )
    assert isinstance(adopted, Ok)
    refused = planner.open_scene(SCENE, NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "carries no element" in refused.error.message
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.PLANNED


def test_open_scene_refuses_a_retired_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The consumption cut's ban: a ``DISCARDED`` anchor is retired —
    ``open_scene`` refuses ``VALIDATION_FAILED`` (never activates a
    retired plan's scene)."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    created = narrative.create_scene("world-town-ch01-s02", "world-town-ch01", 2, NOW)
    assert isinstance(created, Ok)
    discarded = narrative.discard_scene(
        "world-town-ch01-s02", NOW, expected_state_version=1
    )
    assert isinstance(discarded, Ok)
    refused = planner.open_scene("world-town-ch01-s02", NOW)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "DISCARDED" in refused.error.message
    assert narrative.dossiers_of("world-town-ch01-s02") == ()


# ---------------------------------------------------------------------------
# 7. the Director's crash/replay closure
# ---------------------------------------------------------------------------


def test_open_next_chapter_reuses_a_dangling_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The replay law: a crashed open (a ``PLANNED`` chapter with no plan
    revision — the V3-4 review's F1 residue) is **reused** — the retry
    mints plan revision 1 on that chapter and moves no new chapter
    beside it."""

    _seed_town(conn, world_store, cast_store, bible_store)
    created = narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    assert isinstance(created, Ok)
    assert narrative.plans_of("world-town-ch01") == ()

    opened = director.open_next_chapter(TOWN, _blueprint(), LATER)
    assert isinstance(opened, Ok)
    assert opened.value.chapter.chapter_id == "world-town-ch01"
    assert opened.value.chapter.chapter_index == 1
    assert opened.value.plan.chapter_plan_id == "world-town-ch01-bp-r1"
    assert opened.value.plan.status is PlanRevisionStatus.ADOPTED
    assert [row.scene_id for row in opened.value.scenes] == [SCENE]
    chapters = narrative.chapters_of(TOWN)
    assert [row.chapter_id for row in chapters] == ["world-town-ch01"]


def test_revise_blueprint_reuses_a_matching_proposed_revision(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The dangling ``PROPOSED`` revision (a crashed revise before its
    adoption) is reused when the retry's payload matches its shape: the
    residue is **adopted** and the reconciliation continues — no second
    revision lands beside it."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    payload = _blueprint(scenes=[_scene(purpose="the ledger")])
    # The residue: exactly what the crashed attempt's create+adopt pair
    # would have written for this payload (the targets' own elements —
    # the anchors exist, so the elements ride as given).
    residue = narrative.create_plan(
        "world-town-ch01-bp-r2",
        "world-town-ch01",
        2,
        **_chapter_fields(goal=payload["goal"]),
        scenes=tuple(payload["scenes"]),
        now=LATER,
    )
    assert isinstance(residue, Ok)

    revised = director.revise_blueprint("world-town-ch01", payload, LATER)
    assert isinstance(revised, Ok)
    assert revised.value.plan.chapter_plan_id == "world-town-ch01-bp-r2"
    assert revised.value.plan.status is PlanRevisionStatus.ADOPTED
    assert [row.scene_id for row in revised.value.scenes] == [SCENE]
    plans = narrative.plans_of("world-town-ch01")
    assert [plan.plan_revision for plan in plans] == [1, 2]
    assert [plan.status for plan in plans] == [
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.ADOPTED,
    ]


def test_revise_blueprint_rejects_a_different_proposed_revision(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The residue with a different shape: the retry rejects it
    (``REJECTED`` — the veto face) and mints the next revision beside
    it; the retry never silently adopts a revision it did not write."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    residue_payload = _blueprint(
        scenes=[_scene(purpose="the first draft")], goal="a different road"
    )
    residue = narrative.create_plan(
        "world-town-ch01-bp-r2",
        "world-town-ch01",
        2,
        **_chapter_fields(goal=residue_payload["goal"]),
        scenes=tuple(residue_payload["scenes"]),
        now=LATER,
    )
    assert isinstance(residue, Ok)

    retry_payload = _blueprint(
        scenes=[_scene(purpose="the second telling")], goal="the road taken"
    )
    revised = director.revise_blueprint(
        "world-town-ch01", retry_payload, LATER
    )
    assert isinstance(revised, Ok)
    assert revised.value.plan.chapter_plan_id == "world-town-ch01-bp-r3"
    assert revised.value.plan.plan_revision == 3
    assert revised.value.plan.status is PlanRevisionStatus.ADOPTED
    plans = narrative.plans_of("world-town-ch01")
    assert [plan.plan_revision for plan in plans] == [1, 2, 3]
    assert [plan.status for plan in plans] == [
        PlanRevisionStatus.SUPERSEDED,
        PlanRevisionStatus.REJECTED,
        PlanRevisionStatus.ADOPTED,
    ]


def test_open_reuses_a_proposed_residue_chapter_without_a_new_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The V3-5 review's F1, window 1: a crashed open between
    ``create_plan`` and ``adopt_plan`` leaves a ``PLANNED`` chapter whose
    revision 1 is still ``PROPOSED`` — the retried ``open_next_chapter``
    **reuses the chapter** (no ``ch02`` beside it), adopts the matching
    residue, and reconciles on."""

    _seed_town(conn, world_store, cast_store, bible_store)
    created = narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    assert isinstance(created, Ok)
    payload = _blueprint()
    stamped = [dict(payload["scenes"][0], scene_id=SCENE)]
    residue = narrative.create_plan(
        "world-town-ch01-bp-r1",
        "world-town-ch01",
        1,
        **_chapter_fields(),
        scenes=tuple(stamped),
        now=NOW,
    )
    assert isinstance(residue, Ok)

    opened = director.open_next_chapter(TOWN, payload, LATER)
    assert isinstance(opened, Ok)
    assert opened.value.chapter.chapter_id == "world-town-ch01"
    assert opened.value.plan.chapter_plan_id == "world-town-ch01-bp-r1"
    assert opened.value.plan.status is PlanRevisionStatus.ADOPTED
    assert [row.scene_id for row in opened.value.scenes] == [SCENE]
    assert [row.chapter_id for row in narrative.chapters_of(TOWN)] == [
        "world-town-ch01"
    ]
    assert [plan.plan_revision for plan in narrative.plans_of("world-town-ch01")] == [1]


def test_open_resumes_an_adopted_residue_with_missing_anchors(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The V3-5 review's F1, windows 2+3: a crashed open between
    ``adopt_plan`` and the reconciliation's end leaves an ``ADOPTED``
    revision whose anchors are partially (or never) landed — the retried
    ``open_next_chapter`` mints **no new revision and no new chapter**:
    the reconciliation resumes against the adopted plan's own content
    and lands the missing anchors."""

    _seed_town(conn, world_store, cast_store, bible_store)
    created = narrative.create_chapter("world-town-ch01", TOWN, 1, NOW)
    assert isinstance(created, Ok)
    scenes = [
        _scene(purpose="first sight"),
        _scene(purpose="the ledger"),
        _scene(purpose="the door"),
    ]
    payload = _blueprint(scenes=scenes)
    stamped = [
        dict(element, scene_id=f"world-town-ch01-s{index:02d}")
        for index, element in enumerate(scenes, start=1)
    ]
    created_plan = narrative.create_plan(
        "world-town-ch01-bp-r1",
        "world-town-ch01",
        1,
        **_chapter_fields(),
        scenes=tuple(stamped),
        now=NOW,
    )
    assert isinstance(created_plan, Ok)
    adopted = narrative.adopt_plan("world-town-ch01-bp-r1", NOW, 1)
    assert isinstance(adopted, Ok)
    # The crash landed one anchor of three (window 3; zero anchors is
    # window 2 — the same resume path).
    anchored = narrative.create_scene(
        "world-town-ch01-s01", "world-town-ch01", 1, NOW
    )
    assert isinstance(anchored, Ok)

    opened = director.open_next_chapter(TOWN, payload, LATER)
    assert isinstance(opened, Ok)
    assert opened.value.chapter.chapter_id == "world-town-ch01"
    assert opened.value.plan.chapter_plan_id == "world-town-ch01-bp-r1"
    assert [row.scene_id for row in opened.value.scenes] == [
        "world-town-ch01-s01",
        "world-town-ch01-s02",
        "world-town-ch01-s03",
    ]
    assert [row.chapter_id for row in narrative.chapters_of(TOWN)] == [
        "world-town-ch01"
    ]
    assert [plan.plan_revision for plan in narrative.plans_of("world-town-ch01")] == [1]
    assert [
        row.status for row in narrative.scenes_of("world-town-ch01")
    ] == [
        SceneStatus.PLANNED,
        SceneStatus.PLANNED,
        SceneStatus.PLANNED,
    ]


# ---------------------------------------------------------------------------
# 8. the transactionisation discharge
# ---------------------------------------------------------------------------


def test_activate_chapter_does_not_bypass_a_held_lock(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    tmp_path: Path,
) -> None:
    """The behaviour half: while another connection holds the write
    transaction, ``activate_chapter`` refuses
    ``DEPENDENCY_UNAVAILABLE`` (the database's own busy answer — the
    face's one ``BEGIN IMMEDIATE`` is the whole move, checks included);
    after the lock releases the same call goes through."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    conn_b = sqlite3.connect(tmp_path / "app.db")
    try:
        conn_b.execute("PRAGMA foreign_keys=ON")
        conn_b.execute("PRAGMA busy_timeout = 50")
        epoch_now = load_current_epoch(conn_b)
        assert epoch_now is not None
        writer_b = SqliteNarrativeStore(
            conn_b, RuntimeEpochFence(current=epoch_now)
        )
        conn.execute("BEGIN IMMEDIATE")  # the first writer holds the lock
        try:
            refused = writer_b.activate_chapter(
                "world-town-ch01", 0, NOW, expected_state_version=1
            )
        finally:
            conn.execute("ROLLBACK")
        assert isinstance(refused, Err)
        assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
        assert "locked" in refused.error.message

        retried = writer_b.activate_chapter(
            "world-town-ch01", 0, NOW, expected_state_version=1
        )
        assert isinstance(retried, Ok)
        assert retried.value.status is ChapterStatus.ACTIVE
        assert retried.value.opened_at_tick == 0
    finally:
        conn_b.close()


# ---------------------------------------------------------------------------
# 9. the V2 surfaces, the chain head, the legacy vocabulary
# ---------------------------------------------------------------------------


def test_the_v2_surfaces_and_vocabulary_stay_untouched(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    writer: PovWriter,
) -> None:
    """N-R-INV-008 and the V3-3R legacy freeze: the full V3-5 activity
    writes nothing into ``world_run`` / ``world_reveal_item``; a legacy
    event's participants vocabulary (a persona id, a user id) is never
    rewritten, and the V3 segment's own participants are the canonical
    identities."""

    _seed_town(conn, world_store, cast_store, bible_store)
    legacy = world_store.record_event(
        WorldEvent(
            event_id="event-v2-1",
            world_id=TOWN,
            kind="beat",
            narration="the mill wheel turns",
            effects=(),
            occurred_at=NOW,
            source="test",
            participants=("persona-lia", "you"),
        )
    )
    assert isinstance(legacy, Ok)
    opened_chapter = director.open_next_chapter(TOWN, _blueprint(), NOW)
    assert isinstance(opened_chapter, Ok)
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    written = writer.write_segment(
        SCENE,
        body="The bell answers.",
        language="en",
        segment_seq=1,
        duration_ticks=2,
        is_last_segment=True,
        now=NOW,
    )
    assert isinstance(written, Ok)

    assert _row_counts(conn, ("world_run", "world_reveal_item")) == {
        "world_run": 0,
        "world_reveal_item": 0,
    }
    legacy_row = conn.execute(
        "SELECT participants FROM world_event WHERE event_id = ?",
        ("event-v2-1",),
    ).fetchone()
    assert legacy_row is not None
    assert legacy_row[0] == '["persona-lia","you"]'  # zero back-fill
    v3_row = conn.execute(
        "SELECT participants FROM world_event WHERE event_id = ?",
        (written.value.event_id,),
    ).fetchone()
    assert v3_row is not None
    assert v3_row[0] == '["actor-lia","pc-you"]'


def test_the_chain_head_and_the_stamps_agree() -> None:
    """The migration self-pin: the shared constants and a fresh database
    end at V3-7's ``0037_actor_memory_chapter_settlement`` / ``37`` —
    behind it V3-6R's ``0036_action_replan``, V3-6's
    ``0035_user_gate_action``, V3-5R's ``0034_segment_terminality`` and
    V3-5's ``0033_segment_commit``, and V3-1's four tables and V3-5's
    three join the chain behind that."""

    assert MIGRATION_IDS[-1] == "0037_actor_memory_chapter_settlement"
    assert SCHEMA_HEAD_FILE == "0037_actor_memory_chapter_settlement.sql"
    assert SCHEMA_HEAD_VERSION == "37"
    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0037_actor_memory_chapter_settlement"
    assert applied[-2] == "0036_action_replan"
    assert applied[-3] == "0035_user_gate_action"
    assert applied[-4] == "0034_segment_terminality"
    assert applied[-5] == "0033_segment_commit"
    assert applied[-6] == "0032_actor_profile_world_fk"
    assert applied[-7] == "0031_world_cast"
    assert applied[-8] == "0030_world_bible"
    assert applied[-9] == "0029_narrative_v3_foundations"
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
    tables = {
        str(row[0])
        for row in fresh.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    for table in ("narrative_passage", "reader_exposure", "segment_commit"):
        assert table in tables, table
