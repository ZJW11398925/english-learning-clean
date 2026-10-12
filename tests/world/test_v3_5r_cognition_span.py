"""V3-5R — the scope-limited correction cut (TASK-OPI-dc1bafdf…13 / the
opening ruling DEC-OPI-dc1bafdf…11; VAL-OPI-dc1bafdf…15): the V3
cognition read face, NCP-3 as the scene span's only writer, the fresh
segment's ordering law, persisted terminality, the ``max`` time law and
migration 0034. The groups:

1. **the cognition read face** — the lineage-only judgment, the
   actual-interval ordering, the public / witnessed layers over the
   canonical vocabulary, the persona-id and cross-POV arms, the
   ``viewer_id`` validation, and the Scene Planner's consumption of the
   POV's own view;
2. **the span** — NCP-3's one span writer (first segment writes the
   start, every segment advances the end, the last carries the flip),
   and the replay's zero re-write;
3. **the ordering law** — 0 / negative / skipped / out-of-order fresh
   sequences refused, the first segment is 1, and the replay arm's
   precedence;
4. **terminality** — the persisted ``is_last_segment`` and the replay
   shape comparison's two-way ``CONFLICT``;
5. **the time law** — ``planned_start_tick = max(current_tick,
   element's)`` both ways, and the corrupted-row refusal;
6. **migration 0034** — the column's shape (NOT NULL / DEFAULT 0 /
   CHECK), the exact back-fill (a temp-dir subset application), and the
   stamps;
7. **module discipline** — no package face, no interpolated SQL, no
   transaction control in the read; the commit's one-transaction shape
   and its transaction-free arms; the span arm's one-UPDATE form;
8. **the chain head** — the shared constants and a fresh database end
   at 0034.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.cognition import V3CognitionEvent, v3_cognition_view
from elc.world.director import Director
from elc.world.narrative import (
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.scene import SceneContext, ScenePlanner
from elc.world.settlement import commit_segment
from elc.world.store import SqliteWorldStore
from elc.world.time import advance_current_tick, read_current_tick
from elc.world.types import StateEffect, WorldEvent
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "migrations"

NOW = "2026-10-12T00:00:00+00:00"
LATER = "2026-10-12T01:00:00+00:00"

TOWN = "world-town"
SCENE = "world-town-ch01-s01"
SCENE_TWO = "world-town-ch01-s02"

# ---------------------------------------------------------------------------
# shared fixtures / helpers (the V3-5 suite's own shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db with the production profile's
    foreign-keys-ON posture."""

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
    the world's ``CURRENT`` Bible revision."""

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
    start_tick: int = 0,
    **extras: Any,
) -> dict[str, Any]:
    """One Blueprint scene draft — the canonical ten keys."""

    return {
        "purpose": purpose,
        "place": "the bindery steps",
        "pov_actor_id": pov,
        "participants": list(participants),
        "planned_start_tick": start_tick,
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
    """The eight chapter-side fields one plan revision carries."""

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


def _lineage_rows(conn: sqlite3.Connection) -> list[tuple[int, int]]:
    return [
        (int(row[0]), int(row[1]))
        for row in conn.execute(
            "SELECT segment_seq, is_last_segment FROM segment_commit"
            " ORDER BY segment_seq ASC"
        ).fetchall()
    ]


# ---------------------------------------------------------------------------
# 1. the cognition read face (HIGH-1)
# ---------------------------------------------------------------------------


def test_the_cognition_read_is_lineage_only(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The explicit-lineage law: a legacy event — one whose
    ``participants`` even carry the viewer's own canonical id — holds no
    ``segment_commit`` row and never enters the V3 read; the committed
    segment's event does."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    legacy = world_store.record_event(
        WorldEvent(
            event_id="event-v2-1",
            world_id=TOWN,
            kind="beat",
            narration="the mill wheel turns",
            effects=(),
            occurred_at=NOW,
            source="test",
            participants=("actor-lia", "persona-lia"),
        )
    )
    assert isinstance(legacy, Ok)
    result = _commit(conn, narrative, world_store)
    assert isinstance(result, Ok)
    view = v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(view, Ok)
    assert [event.event_id for event in view.value.witnessed] == [
        result.value.event_id
    ]
    assert view.value.public == ()
    assert "event-v2-1" not in {
        event.event_id
        for event in (*view.value.public, *view.value.witnessed)
    }


def test_the_cognition_read_orders_by_the_lineage_interval(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Ordering rides the lineage actual interval: the witnessed layer
    comes back in commit order with each event's own
    ``(actual_start_tick, actual_end_tick)`` — never ``occurred_at``."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    second = _commit(
        conn, narrative, world_store, segment_seq=2, duration_ticks=5
    )
    assert isinstance(second, Ok)
    view = v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(view, Ok)
    assert [event.event_id for event in view.value.witnessed] == [
        first.value.event_id,
        second.value.event_id,
    ]
    assert [
        (event.actual_start_tick, event.actual_end_tick)
        for event in view.value.witnessed
    ] == [(0, 3), (3, 8)]


def test_the_cognition_read_orders_by_the_lineage_ticks_not_the_ids(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The ordering key, not just its direction (the review's F2): the
    read orders by the lineage actual interval. Scene two commits first
    — the planner's opening order is its own — so the tick order and the
    id spelling disagree, and only the interval order answers the
    canonical chronology."""

    _opened_chapter(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        scenes=[_scene(purpose="first"), _scene(purpose="second")],
    )
    opened_two = planner.open_scene(SCENE_TWO, NOW)
    assert isinstance(opened_two, Ok)
    early = _commit(
        conn, narrative, world_store, scene_id=SCENE_TWO, duration_ticks=3
    )
    assert isinstance(early, Ok)
    opened_one = planner.open_scene(SCENE, NOW)
    assert isinstance(opened_one, Ok)
    late = _commit(
        conn, narrative, world_store, scene_id=SCENE, duration_ticks=5
    )
    assert isinstance(late, Ok)
    assert (
        early.value.actual_start_tick,
        early.value.actual_end_tick,
    ) == (0, 3)
    assert (
        late.value.actual_start_tick,
        late.value.actual_end_tick,
    ) == (3, 8)
    view = v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(view, Ok)
    # The ids sort the other way (``…-s01-…`` < ``…-s02-…``): the
    # interval order is the only answer that matches the chronology.
    assert [event.event_id for event in view.value.witnessed] == [
        early.value.event_id,
        late.value.event_id,
    ]


def test_the_cognition_read_layers_public_and_witnessed(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The layer judgment over canonical identity: an empty
    ``participants`` is public, the viewer among ``participants`` is
    witnessed, and an event naming some other cast only is neither (it
    is not this viewer's knowledge)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    public = _commit(
        conn, narrative, world_store, participants=(), narration="the frost"
    )
    assert isinstance(public, Ok)
    witnessed = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        participants=("actor-lia",),
        narration="the two meet",
    )
    assert isinstance(witnessed, Ok)
    other = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=3,
        participants=("pc-you",),
        narration="the coach arrives",
    )
    assert isinstance(other, Ok)
    view = v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(view, Ok)
    assert [event.event_id for event in view.value.public] == [public.value.event_id]
    assert [event.event_id for event in view.value.witnessed] == [
        witnessed.value.event_id
    ]
    assert view.value.viewer_id == "actor-lia"
    assert all(
        isinstance(event, V3CognitionEvent)
        for event in (*view.value.public, *view.value.witnessed)
    )


def test_a_persona_id_viewer_sees_only_the_public_layer(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """A persona id is a template identity, not a canonical world
    participant (the V3-3R freeze): as a viewer it reads the public
    layer and is witnessed by nothing."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    public = _commit(conn, narrative, world_store, participants=(), narration="x")
    assert isinstance(public, Ok)
    witnessed = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        participants=("actor-lia", "pc-you"),
        narration="y",
    )
    assert isinstance(witnessed, Ok)
    view = v3_cognition_view(conn, world_id=TOWN, viewer_id="persona-lia")
    assert isinstance(view, Ok)
    assert [event.event_id for event in view.value.public] == [public.value.event_id]
    assert view.value.witnessed == ()


def test_different_povs_read_different_views(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The viewer is the read's own address: the same world read as the
    player character and as the AI actor answers different witnessed
    layers."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    only_player = _commit(
        conn,
        narrative,
        world_store,
        participants=("pc-you",),
        narration="the letter under the door",
    )
    assert isinstance(only_player, Ok)
    as_player = v3_cognition_view(conn, world_id=TOWN, viewer_id="pc-you")
    as_actor = v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(as_player, Ok)
    assert isinstance(as_actor, Ok)
    assert [event.event_id for event in as_player.value.witnessed] == [
        only_player.value.event_id
    ]
    assert as_actor.value.witnessed == ()


def test_the_viewer_id_is_validated(
    conn: sqlite3.Connection,
) -> None:
    """The viewer is the read's own address: an empty, blank or non-string
    ``viewer_id`` is refused ``VALIDATION_FAILED`` with a human sentence —
    never a silent empty view."""

    for bad in ("", "   ", None):
        refused = v3_cognition_view(conn, world_id=TOWN, viewer_id=bad)
        assert isinstance(refused, Err), bad
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
        assert "viewer_id" in refused.error.message


def test_the_cognition_read_refuses_a_corrupted_participants_column(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The corrupted-row posture (the review's F4): the column is this
    suite's own encoder's output, so a payload the strict codec cannot
    decode is surfaced honestly (``ValueError``) rather than silently
    dropped from the view."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    conn.execute(
        "UPDATE world_event SET participants = ? WHERE event_id = ?",
        ('{"who": "lia"}', committed.value.event_id),
    )
    conn.commit()
    with pytest.raises(ValueError, match="undecodable participants"):
        v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")


def test_open_scene_feeds_the_pov_cognition_view(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The Scene Planner consumes the read (HIGH-1): after scene 1's
    commit, opening scene 2 carries a ``SceneContext`` whose cognition
    view — built for scene 2's POV — holds scene 1's event with its
    lineage interval."""

    _opened_chapter(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        scenes=[_scene(purpose="first sight"), _scene(purpose="the ledger")],
    )
    first_open = planner.open_scene(SCENE, NOW)
    assert isinstance(first_open, Ok)
    committed = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(committed, Ok)
    second_open = planner.open_scene(SCENE_TWO, NOW)
    assert isinstance(second_open, Ok)
    context = second_open.value.context
    assert isinstance(context, SceneContext)
    assert context.pov_actor_id == "actor-lia"
    assert context.current_tick == 3  # the commit advanced the world
    assert context.cognition.viewer_id == "actor-lia"
    assert [event.event_id for event in context.cognition.witnessed] == [
        committed.value.event_id
    ]
    assert (
        context.cognition.witnessed[0].actual_start_tick,
        context.cognition.witnessed[0].actual_end_tick,
    ) == (0, 3)


# ---------------------------------------------------------------------------
# 2. the span (HIGH-2 — NCP-3's one span writer)
# ---------------------------------------------------------------------------


def test_the_first_segment_writes_the_span(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The first committed segment writes both span ends in its own
    transaction (the scene stays ACTIVE — no flip without
    ``is_last_segment``), and the arm bumps the scene's version exactly
    once (mint 1 → activation 2 → this commit 3)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    result = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(result, Ok)
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.actual_start_tick == 0
    assert scene.actual_end_tick == 3
    assert scene.status is SceneStatus.ACTIVE
    assert scene.state_version == 3


def test_the_next_segment_advances_only_the_end(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The span's ``COALESCE`` law: the second segment advances
    ``actual_end_tick`` to its own end and leaves the start at the first
    segment's value — one version bump again."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    second = _commit(
        conn, narrative, world_store, segment_seq=2, duration_ticks=5
    )
    assert isinstance(second, Ok)
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.actual_start_tick == 0
    assert scene.actual_end_tick == 8
    assert scene.state_version == 4
    assert scene.status is SceneStatus.ACTIVE


def test_the_last_segment_commits_and_closes_the_span(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The alias law in the span arm: the last segment's UPDATE carries
    ``ACTIVE → COMMITTED``, and the scene's ``actual_end_tick`` equals
    that segment's own end."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    last = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        duration_ticks=5,
        is_last_segment=True,
    )
    assert isinstance(last, Ok)
    assert last.value.scene_committed is True
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.COMMITTED
    assert scene.actual_start_tick == 0
    assert scene.actual_end_tick == last.value.actual_end_tick == 8
    # One version advance per segment — the last one's carries the flip
    # too (the review's F5: the single-UPDATE shape pin is not the only
    # witness of the one-bump law).
    assert scene.state_version == 4


def test_a_replay_leaves_the_span_untouched(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay is a whole-group no-op — the span arm is not re-run:
    the scene row, the tick and the lineage rows stay exactly as the
    first write left them."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    last = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        duration_ticks=5,
        is_last_segment=True,
    )
    assert isinstance(last, Ok)
    scene_before = narrative.get_scene(SCENE)
    rows_before = _lineage_rows(conn)
    replay = _commit(conn, narrative, world_store, duration_ticks=3, now=LATER)
    assert isinstance(replay, Ok)
    assert replay.value == first.value
    assert narrative.get_scene(SCENE) == scene_before
    assert _lineage_rows(conn) == rows_before
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 8


def test_the_replay_answers_scene_committed_from_the_stored_flag(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-5R review's F1: the replay's ``scene_committed`` is the
    stored terminality flag — the durable witness the flip landed with
    this segment — never a read-time derivation over the scene's status
    and its max seq. A scene committed through the explicit
    ``commit_scene`` face (no terminality flag on its segments) answers
    ``False`` for each of its stored segments, and the flag itself stays
    the append-only zero it was."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, duration_ticks=3)
    assert isinstance(first, Ok)
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    flipped = narrative.commit_scene(
        SCENE, LATER, expected_state_version=scene.state_version
    )
    assert isinstance(flipped, Ok)
    assert flipped.value.status is SceneStatus.COMMITTED
    replayed = _commit(
        conn, narrative, world_store, duration_ticks=3, now=LATER
    )
    assert isinstance(replayed, Ok)
    assert replayed.value.scene_committed is False
    row = conn.execute(
        "SELECT is_last_segment FROM segment_commit"
        " WHERE scene_id = ? AND segment_seq = 1",
        (SCENE,),
    ).fetchone()
    assert row is not None and int(row[0]) == 0


# ---------------------------------------------------------------------------
# 3. the ordering law (MEDIUM-HIGH)
# ---------------------------------------------------------------------------


def test_a_zero_or_negative_sequence_is_refused(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """0 and negative fresh sequences are refused ``VALIDATION_FAILED``
    naming both the given and the expected values — and nothing lands."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    for given in (0, -1):
        refused = _commit(conn, narrative, world_store, segment_seq=given)
        assert isinstance(refused, Err), given
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
        assert f"given {given}" in refused.error.message
        assert "expected 1" in refused.error.message
    assert _row_counts(
        conn, ("narrative_passage", "world_event", "segment_commit")
    ) == {"narrative_passage": 0, "world_event": 0, "segment_commit": 0}


def test_a_skipped_sequence_is_refused(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """A skipped fresh sequence is refused on both sides of a landed
    segment: 2 on an empty scene (expected 1), then 3 once 1 is in
    (expected 2) — and the in-order 2 still lands afterwards."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    skipped_on_empty = _commit(conn, narrative, world_store, segment_seq=2)
    assert isinstance(skipped_on_empty, Err)
    assert skipped_on_empty.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "expected 1" in skipped_on_empty.error.message
    first = _commit(conn, narrative, world_store, segment_seq=1)
    assert isinstance(first, Ok)
    skipped_after_one = _commit(conn, narrative, world_store, segment_seq=3)
    assert isinstance(skipped_after_one, Err)
    assert skipped_after_one.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "expected 2" in skipped_after_one.error.message
    assert "given 3" in skipped_after_one.error.message
    assert _lineage_rows(conn) == [(1, 0)]
    second = _commit(conn, narrative, world_store, segment_seq=2, duration_ticks=5)
    assert isinstance(second, Ok)
    assert _lineage_rows(conn) == [(1, 0), (2, 0)]


def test_the_first_segment_must_be_one(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The out-of-order attempt (2 first) is refused, and the in-order
    first segment (1) then lands as the scene's true first — the law
    judges every fresh move against the store, not the caller's wish."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    out_of_order = _commit(conn, narrative, world_store, segment_seq=2)
    assert isinstance(out_of_order, Err)
    assert out_of_order.error.code is DomainErrorCode.VALIDATION_FAILED
    first = _commit(conn, narrative, world_store, segment_seq=1)
    assert isinstance(first, Ok)
    assert first.value.actual_start_tick == 0
    assert _lineage_rows(conn) == [(1, 0)]


def test_a_replay_precedes_the_ordering_law(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay arm runs before the law: an existing key's replay
    answers the stored outcome (here on a committed scene), while a
    fresh sequence is still judged — a jump to 4 on a one-segment scene
    is refused with ``expected 2`` before the status gate would speak."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(
        conn, narrative, world_store, segment_seq=1, is_last_segment=True
    )
    assert isinstance(first, Ok)
    replay = _commit(
        conn, narrative, world_store, segment_seq=1, is_last_segment=True,
        now=LATER,
    )
    assert isinstance(replay, Ok)
    assert replay.value == first.value
    jumped = _commit(conn, narrative, world_store, segment_seq=4)
    assert isinstance(jumped, Err)
    assert jumped.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "expected 2" in jumped.error.message
    assert "given 4" in jumped.error.message


# ---------------------------------------------------------------------------
# 4. terminality (persisted; migration 0034)
# ---------------------------------------------------------------------------


def test_terminality_lands_in_the_lineage_row(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The INSERT's own column: a non-last segment stores 0, the scene's
    last stores 1 — the persisted SCENE COMMIT identity."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, segment_seq=1)
    assert isinstance(first, Ok)
    second = _commit(
        conn, narrative, world_store, segment_seq=2, is_last_segment=True
    )
    assert isinstance(second, Ok)
    assert _lineage_rows(conn) == [(1, 0), (2, 1)]


def test_a_terminality_mismatch_conflicts_both_ways(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay shape comparison includes the terminality flag: stored
    0 replayed as 1 and stored 1 replayed as 0 are both an explicit
    ``CONFLICT`` naming terminality — never a silent "equivalent
    record" — and the stored rows do not move."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store, segment_seq=1)
    assert isinstance(first, Ok)
    stored_zero = _commit(
        conn, narrative, world_store, segment_seq=1, is_last_segment=True
    )
    assert isinstance(stored_zero, Err)
    assert stored_zero.error.code is DomainErrorCode.CONFLICT
    assert "terminality" in stored_zero.error.message
    second = _commit(
        conn, narrative, world_store, segment_seq=2, is_last_segment=True
    )
    assert isinstance(second, Ok)
    stored_one = _commit(
        conn, narrative, world_store, segment_seq=2, is_last_segment=False
    )
    assert isinstance(stored_one, Err)
    assert stored_one.error.code is DomainErrorCode.CONFLICT
    assert "terminality" in stored_one.error.message
    assert _lineage_rows(conn) == [(1, 0), (2, 1)]


# ---------------------------------------------------------------------------
# 5. the time law (DEC-OPI-dc1bafdf…11's item 4)
# ---------------------------------------------------------------------------


def test_the_dossier_start_tick_is_the_later_of_reality_and_the_plan(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Reality wins when it has run past the plan's guess: with the
    world tick at 7 and the element's guess 0, the dossier plans from
    7; the actual span still starts only at the commit."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    advanced = advance_current_tick(conn, TOWN, 7)
    assert isinstance(advanced, Ok)
    conn.commit()
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    assert opened.value.dossier.planned_start_tick == 7
    assert opened.value.context.current_tick == 7
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.actual_start_tick is None  # the commits own the span


def test_a_future_planned_start_is_kept(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The plan's future guess is not flattened onto the current tick:
    with the world at 0 and the element's start 9, the dossier keeps 9
    (the ``max`` both ways)."""

    _opened_chapter(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        scenes=[_scene(start_tick=9)],
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    assert opened.value.context.current_tick == 0
    assert opened.value.dossier.planned_start_tick == 9


def test_open_scene_refuses_a_corrupted_element_tick(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The tick is validated where it is read: an adopted revision whose
    element carries no ``planned_start_tick`` (constructible only
    through the store — the Director's schema refuses it) is refused
    ``VALIDATION_FAILED`` naming the field, and no dossier lands."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    corrupted = dict(_scene())
    del corrupted["planned_start_tick"]
    created = narrative.create_plan(
        "world-town-ch01-bp-r2",
        "world-town-ch01",
        2,
        **_chapter_fields(),
        scenes=(corrupted,),
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
    assert "planned_start_tick" in refused.error.message
    assert narrative.dossiers_of(SCENE) == ()
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.PLANNED


# ---------------------------------------------------------------------------
# 6. migration 0034
# ---------------------------------------------------------------------------


def test_the_terminality_column_carries_its_shape(
    conn: sqlite3.Connection,
) -> None:
    """The column's physical shape: INTEGER, NOT NULL, DEFAULT 0, and
    the CHECK vocabulary refuses a third word."""

    columns = {
        str(row[1]): (str(row[2]), int(row[3]), row[4])
        for row in conn.execute("PRAGMA table_info(segment_commit)").fetchall()
    }
    kind, not_null, default = columns["is_last_segment"]
    assert kind == "INTEGER"
    assert not_null == 1
    assert default == "0"


def test_the_terminality_check_refuses_a_third_word(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The CHECK's vocabulary is exactly ``(0, 1)`` — the database's own
    surface refuses a third word."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    landed = _commit(conn, narrative, world_store)
    assert isinstance(landed, Ok)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE segment_commit SET is_last_segment = 2 WHERE commit_id = ?",
            (landed.value.commit_id,),
        )
    assert _lineage_rows(conn) == [(1, 0)]


def test_the_back_fill_marks_the_committed_scenes_last_row(
    tmp_path: Path,
) -> None:
    """The migration's exact back-fill, on a temp-dir subset application:
    the chain applies to 0033, the V3-5 pipeline's product shape is
    hand-built (a COMMITTED and a CLOSED scene with two lineage rows
    each, a PLANNED scene with one — a scene no commit flipped), and
    0034 marks **only** the COMMITTED / CLOSED scenes' maximum
    ``segment_seq`` rows: the law is the ruling's (true only for the
    pipeline's own product; the derived re-read was rejected)."""

    partial = tmp_path / "migrations-to-0033"
    partial.mkdir()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name < "0034":
            shutil.copyfile(path, partial / path.name)
    db = sqlite3.connect(tmp_path / "partial.db")
    db.execute("PRAGMA foreign_keys=ON")
    applied = apply_migrations(db, partial)
    assert applied[-1] == "0033_segment_commit"

    db.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    db.execute(
        "INSERT INTO world_chapter ("
        " chapter_id, world_id, chapter_index, status, opened_at_tick,"
        " closed_at_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01', 'w', 1, 'ACTIVE', 0, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    for scene_id, status, index, seqs in (
        ("w-ch01-s01", "COMMITTED", 1, (1, 2)),
        ("w-ch01-s02", "CLOSED", 2, (1, 2)),
        ("w-ch01-s03", "PLANNED", 3, (1,)),
    ):
        db.execute(
            "INSERT INTO world_scene ("
            " scene_id, chapter_id, scene_index, status, actual_start_tick,"
            " actual_end_tick, created_at, updated_at, state_version"
            ") VALUES (?, 'w-ch01', ?, ?, 0, 4, ?, ?, 1)",
            (scene_id, index, status, NOW, NOW),
        )
        for seq in seqs:
            passage_id = f"{scene_id}-p{seq:04d}"
            event_id = f"{scene_id}-e{seq:04d}"
            db.execute(
                "INSERT INTO narrative_passage ("
                " passage_id, scene_id, segment_seq, body, language,"
                " outcome_ref, created_at_tick, created_at, updated_at,"
                " state_version"
                ") VALUES (?, ?, ?, 'b', 'en', NULL, ?, ?, ?, 1)",
                (passage_id, scene_id, seq, seq * 2, NOW, NOW),
            )
            db.execute(
                "INSERT INTO world_event ("
                " event_id, world_id, kind, narration, effects, occurred_at,"
                " source, participants, run_id"
                ") VALUES (?, 'w', 'segment', 'n', '[]', ?, 'v3-segment',"
                " '[]', NULL)",
                (event_id, NOW),
            )
            db.execute(
                "INSERT INTO segment_commit ("
                " commit_id, kind, scene_id, segment_seq, passage_id,"
                " actual_start_tick, actual_end_tick, event_id, created_at,"
                " updated_at, state_version"
                ") VALUES (?, 'SEGMENT', ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    f"sg:{scene_id}:{seq:04d}",
                    scene_id,
                    seq,
                    passage_id,
                    seq * 2 - 2,
                    seq * 2,
                    event_id,
                    NOW,
                    NOW,
                ),
            )
    db.commit()

    shutil.copyfile(
        MIGRATIONS / "0034_segment_terminality.sql",
        partial / "0034_segment_terminality.sql",
    )
    migrated = apply_migrations(db, partial)
    assert migrated == ["0034_segment_terminality"]
    assert [
        (str(row[0]), int(row[1]), int(row[2]))
        for row in db.execute(
            "SELECT scene_id, segment_seq, is_last_segment FROM segment_commit"
            " ORDER BY scene_id ASC, segment_seq ASC"
        ).fetchall()
    ] == [
        ("w-ch01-s01", 1, 0),
        ("w-ch01-s01", 2, 1),
        ("w-ch01-s02", 1, 0),
        ("w-ch01-s02", 2, 1),
        ("w-ch01-s03", 1, 0),
    ]
    assert db.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()[0] == "34"


# ---------------------------------------------------------------------------
# 7. module discipline (the scans)
# ---------------------------------------------------------------------------

_COGNITION_SOURCE = (SRC_ROOT / "world" / "cognition.py").read_text(
    encoding="utf-8"
)
_COGNITION_TREE = ast.parse(_COGNITION_SOURCE, filename="cognition.py")
_SETTLEMENT_SOURCE = (SRC_ROOT / "world" / "settlement.py").read_text(
    encoding="utf-8"
)
_SETTLEMENT_TREE = ast.parse(_SETTLEMENT_SOURCE, filename="settlement.py")
_STORE_SOURCE = (SRC_ROOT / "world" / "narrative" / "store.py").read_text(
    encoding="utf-8"
)
_STORE_TREE = ast.parse(_STORE_SOURCE, filename="narrative_store.py")


def _all_constants(tree: ast.AST) -> list[str]:
    """Every string constant in one node — the transaction-boundary pins'
    own collector (the V3-5 review's F2/F3: the DML-shaped filter cannot
    see a stray ``"COMMIT"``)."""

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _sql_constants(tree: ast.AST) -> list[str]:
    """Every SQL-shaped string constant in one module — a constant that
    *starts* with a DML keyword."""

    return [
        text
        for text in _all_constants(tree)
        if re.match(r"(?i)^\s*(select|insert|update|delete)\b", text)
    ]


def _function(tree: ast.AST, name: str) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def test_the_cognition_module_imports_no_package_and_builds_no_sql() -> None:
    """The read face's own discipline: no Package face (the durable rows
    are the runtime authority) and no SQL-shaped constant with string
    interpolation (fixed literals and parameter binding only)."""

    for node in ast.walk(_COGNITION_TREE):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("elc.world.package"), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("elc.world.package"), (
                node.module,
            )
    statements = _sql_constants(_COGNITION_TREE)
    assert statements, "cognition carries no SQL at all — wrong source?"
    for text in statements:
        assert "{" not in text, text
        assert "}" not in text, text
        assert text.lstrip().upper().startswith("SELECT"), text


def test_the_cognition_read_carries_no_transaction_control() -> None:
    """A pure read: the module's unfiltered constant set holds no
    ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK`` at all."""

    source = _COGNITION_SOURCE
    for forbidden in ("BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"):
        assert f'"{forbidden}"' not in source, forbidden
    for text in _all_constants(_COGNITION_TREE):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text


def test_the_cognition_module_starts_from_a_cold_interpreter() -> None:
    """The cold-start pin: a fresh interpreter importing the read face
    first must succeed (no import cycle behind a lucky session order)."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.world.cognition"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def test_the_commit_group_keeps_one_begin_and_one_commit() -> None:
    """NCP-3 is still ONE short transaction: the public
    ``commit_segment`` opens exactly one ``BEGIN IMMEDIATE`` and lands
    exactly one ``COMMIT``; its body carries no transaction-control
    constant at all (the unfiltered set — the V3-5 review's F2 form)."""

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


def test_the_commit_arms_carry_no_transaction_control() -> None:
    """The commit's own arms — the span arm, the chapter opening and
    the lifecycle-only scene flip — carry no transaction-control
    constant: the caller's transaction owns them all."""

    for name in (
        "_advance_scene_actual_span_tx",
        "_flip_chapter_activated_tx",
        "_flip_scene_committed_tx",
    ):
        arm = _function(_STORE_TREE, name)
        assert _sql_constants(arm), (name, "the arm carries no SQL")
        for text in _all_constants(arm):
            assert text != "BEGIN IMMEDIATE", (name, text)
            assert text != "COMMIT", (name, text)
            assert text != "ROLLBACK", (name, text)


def test_the_span_arm_is_one_update_with_the_span_and_the_flip() -> None:
    """The span law's machine half: the arm is exactly one UPDATE —
    ``COALESCE`` for the start, the end advanced, and the ``COMMITTED``
    flip in the same statement (one version bump)."""

    arm = _function(_STORE_TREE, "_advance_scene_actual_span_tx")
    updates = [
        text
        for text in _sql_constants(arm)
        if text.lstrip().upper().startswith("UPDATE")
    ]
    assert len(updates) == 1, updates
    statement = updates[0]
    for needle in (
        "COALESCE(actual_start_tick",
        "actual_end_tick = ?",
        "'COMMITTED'",
        "state_version = state_version + 1",
    ):
        assert needle in statement, needle


def test_the_terminality_column_is_spelled_in_the_insert_and_the_read() -> None:
    """The persistence's own spelling: the lineage INSERT and the replay
    read both name ``is_last_segment`` — the flag is stored and read,
    never derived."""

    statements = _sql_constants(_SETTLEMENT_TREE)
    inserts = [
        text
        for text in statements
        if text.lstrip().upper().startswith("INSERT")
        and "segment_commit" in text
    ]
    assert len(inserts) == 1
    assert "is_last_segment" in inserts[0]
    reads = [
        text
        for text in statements
        if text.lstrip().upper().startswith("SELECT")
        and "FROM segment_commit" in text
    ]
    assert reads, "no segment_commit read found"
    assert any("is_last_segment" in text for text in reads)


# ---------------------------------------------------------------------------
# 8. the chain head
# ---------------------------------------------------------------------------


def test_the_chain_head_and_the_stamps_agree() -> None:
    """The migration self-pin: the shared constants and a fresh database
    end at V3-5R's ``0034_segment_terminality`` / ``34``, immediately
    behind V3-5's ``0033_segment_commit``."""

    assert MIGRATION_IDS[-1] == "0034_segment_terminality"
    assert SCHEMA_HEAD_FILE == "0034_segment_terminality.sql"
    assert SCHEMA_HEAD_VERSION == "34"
    assert MIGRATION_IDS[-2] == "0033_segment_commit"
    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0034_segment_terminality"
    assert applied[-2] == "0033_segment_commit"
    stamps = dict(
        fresh.execute(
            "SELECT key, value FROM schema_meta"
            " WHERE key LIKE '%schema_version%'"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": "34",
        "runtime_schema_version": "34",
    }
    columns = {
        str(row[1])
        for row in fresh.execute("PRAGMA table_info(segment_commit)").fetchall()
    }
    assert "is_last_segment" in columns


def test_the_scene_context_is_the_opens_own_view(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """``SceneContext`` is the open's own view (frozen, carrying the read
    it made): a fresh scene's context answers the POV's own empty view
    and the current tick — the cognition read is the open's, never a
    second call with a different POV."""

    from dataclasses import FrozenInstanceError

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    context = opened.value.context
    assert isinstance(context, SceneContext)
    assert context.current_tick == 0
    assert context.pov_actor_id == opened.value.dossier.pov_actor_id
    assert context.cognition.viewer_id == "actor-lia"
    assert context.cognition.public == ()
    assert context.cognition.witnessed == ()
    with pytest.raises(FrozenInstanceError):
        context.current_tick = 5  # type: ignore[misc]
