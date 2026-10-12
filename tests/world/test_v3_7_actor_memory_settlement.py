"""V3-7 — Actor Memory / Belief + Chapter Settlement + Narrative Memory
(TASK-OPI-d274a7fb…8 / the opening ruling DEC-OPI-d274a7fb…6; the
contract increments in DATA §26.2.1's "V3-7 落表形", STATE §25's "V3-7
落法", RA §28's NCP-4 note and §29's sixth family).

The Narrative V3 program's seventh cut: migration 0037's two tables
(``actor_memory`` / ``chapter_settlement``), the **memory arm** of both
commit transactions (the shared
:func:`elc.world.memory.record_experienced_in_transaction` — one
``EXPERIENCED`` row per event participant, fresh path only), the new
memory face (``record_belief`` for the four caller-supplied kinds and
``v3_memory_view`` for the dossier read), the **NCP-4** chapter
settlement orchestration
(:func:`elc.world.settlement.settle_chapter` — one short transaction:
one-version settlement row + ``SETTLING → CLOSED`` with the tick read
and never advanced, N-INV-004), the next-chapter read-only summary face
(:attr:`elc.world.director.DirectorContext.chapter_summaries`), the
dossier's memory reroute (:attr:`elc.world.scene.SceneContext.memory` —
the cognition view stays the compatibility / fallback arm) and the
recovery scan's sixth family (``settling_chapters``). The groups:

1. **migration 0037's shape** — both tables' columns, the five-word
   kind CHECK (all five insertable), the one-version-per-chapter PK,
   and the shared constants / stamps at the chain head;
2. **NCP-3's memory arm** — one ``EXPERIENCED`` row per participant
   with the derived identity, the event's narration and the commit's
   ``actual_end``; a replay lands zero new rows;
3. **NCP-2's memory arm** — the same for the ruling's participants and
   the action family's event identity; a replay lands zero new rows;
4. **``record_belief``** — the four caller-supplied kinds reachable,
   ``EXPERIENCED`` refused (the automatic arm's word), the replay
   shape law (same shape rides back, different shape ``CONFLICT``), and
   the dangling / cross-world / malformed refusals;
5. **``v3_memory_view``** — one viewer's rows layered by kind and
   ordered by ``learned_at_tick``, viewer isolation, an honest empty
   view, and the malformed ``viewer_id`` refusal;
6. **NCP-4** — a ``SETTLING`` chapter settles in one transaction (the
   settlement row, the ``CLOSED`` flip with ``closed_at_tick`` = the
   transaction's own tick read, the tick never advanced, zero new
   ``world_event`` / ``world_state_fact`` / ``actor_memory`` rows), the
   replay is a zero-write no-op, a shape-different replay is a
   ``CONFLICT``, and a ``PLANNED`` / ``ACTIVE`` / settlement-less
   ``CLOSED`` chapter is refused;
7. **the two read reroutes** — ``DirectorContext.chapter_summaries``
   carries the settled rows (and only the ``CLOSED`` ones);
   ``SceneContext.memory`` carries the POV's memory view beside the
   unchanged cognition field;
8. **the recovery scan's sixth family** — ``settling_chapters`` names
   the ``SETTLING`` subset while the ``chapters`` family stays intact;
9. **the module discipline** — one transaction per write face, no
   interpolated SQL, the N-INV-004 storage face (the settlement writes
   no facts), the cold start and the ledger drift pins' own family.
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

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.action import (
    Adjudication,
    GateStatus,
    ReplanScope,
    begin_resolving,
    commit_action,
    get_gate,
    open_gate,
    recovery_scan,
    submit_gate,
)
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.director import Director
from elc.world.memory import (
    MemoryKind,
    memory_id_for,
    record_belief,
    v3_memory_view,
)
from elc.world.narrative import (
    ChapterStatus,
    PlanRevisionStatus,
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.scene import ScenePlanner
from elc.world.settlement import (
    chapter_settlements_of,
    commit_segment,
    settle_chapter,
)
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import StateEffect
from tests.conftest import (
    MIGRATION_IDS,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)

REPO = Path(__file__).resolve().parents[2]

NOW = "2026-10-13T00:00:00+00:00"
LATER = "2026-10-13T01:00:00+00:00"
LATER2 = "2026-10-13T02:00:00+00:00"

TOWN = "world-town"
CH = "world-town-ch01"
SCENE = "world-town-ch01-s01"
SCENE2 = "world-town-ch01-s02"
GATE = "world-town-ch01-s01-g01"

MEMORY_SOURCE = (SRC_ROOT / "world" / "memory.py").read_text(encoding="utf-8")
MEMORY_TREE = ast.parse(MEMORY_SOURCE)
SETTLEMENT_SOURCE = (SRC_ROOT / "world" / "settlement.py").read_text(
    encoding="utf-8"
)
SETTLEMENT_TREE = ast.parse(SETTLEMENT_SOURCE)

# ---------------------------------------------------------------------------
# shared fixtures / helpers (the V3-6 suite's own shapes)
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
    """One hand-made world: the world row, one AI actor with a
    POV-eligible profile, the reader's own durable character and the
    world's ``CURRENT`` Bible revision."""

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


def _scene_draft(
    pov: str = "actor-lia",
    participants: tuple[str, ...] = ("actor-lia", "pc-you"),
    purpose: str = "first sight",
    must_hide: str = "the priced tools",
    **extras: Any,
) -> dict[str, Any]:
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
    if scenes is None:
        scenes = [_scene_draft()]
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


def _opened_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    director: Director,
    *,
    scenes: list[dict[str, Any]] | None = None,
) -> None:
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
    scene_id: str = SCENE,
) -> str:
    """The full pre-commit chain: town seeded, chapter planned, the scene
    opened (dossier adopted, scene ACTIVE)."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, director, scenes=scenes
    )
    opened = planner.open_scene(scene_id, NOW)
    assert isinstance(opened, Ok)
    return scene_id


def _two_scene_chain(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The chain with two scene anchors, the first one ACTIVE."""

    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        scenes=[
            _scene_draft(purpose="first sight"),
            _scene_draft(purpose="the ledger"),
        ],
    )


def _commit(
    conn: sqlite3.Connection,
    narrative: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    *,
    scene_id: str = SCENE,
    segment_seq: int = 1,
    body: str = "The bell above the door answers before her voice does.",
    participants: tuple[str, ...] = ("actor-lia", "pc-you"),
    narration: str = "the two meet at the bindery steps",
    duration_ticks: int = 3,
    is_last_segment: bool = False,
    now: str = NOW,
    outcome_ref: str | None = None,
):
    return commit_segment(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        scene_id=scene_id,
        segment_seq=segment_seq,
        body=body,
        language="en",
        participants=participants,
        effects=(),
        narration=narration,
        duration_ticks=duration_ticks,
        is_last_segment=is_last_segment,
        now=now,
        outcome_ref=outcome_ref,
    )


def _ruling(
    *,
    interpretation: str = "You mean to help rather than to buy.",
    outcome: str = "Lia lets you hold the ledger; the ice thins.",
    actual_action: str = "you carry the ledger to the counter",
    consequences: str = "the shop's silence opens one notch",
    state_effects: tuple[StateEffect, ...] = (
        StateEffect(key="trust:lia", statement="warmed by one notch"),
    ),
    participants: tuple[str, ...] = ("pc-you", "actor-lia"),
    replan_scope: ReplanScope = ReplanScope.NONE,
) -> Adjudication:
    return Adjudication(
        interpretation=interpretation,
        outcome=outcome,
        actual_action=actual_action,
        consequences=consequences,
        state_effects=state_effects,
        participants=participants,
        replan_scope=replan_scope,
    )


def _committed_action(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    narrative: SqliteNarrativeStore,
    *,
    gate_id: str = GATE,
    submission_id: str = "sub-1",
    adjudication: Adjudication | None = None,
    duration_ticks: int = 7,
    now: str = LATER,
):
    # The V3-6R door: the ruling enters COMMITTED only from RESOLVING —
    # the helper steps an ANSWERED pair into the durable stop first (a
    # gate already RESOLVING rides; a stored replay is left to the face's
    # own replay arm and answers zero-write).
    gate = get_gate(conn, gate_id)
    if gate is not None and gate.status is GateStatus.ANSWERED:
        moved = begin_resolving(conn, gate_id=gate_id, now=now)
        assert isinstance(moved, Ok)
    return commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=gate_id,
        submission_id=submission_id,
        adjudication=adjudication or _ruling(),
        duration_ticks=duration_ticks,
        now=now,
    )


def _memory_rows(conn: sqlite3.Connection) -> list[tuple[Any, ...]]:
    return conn.execute(
        "SELECT memory_id, world_id, participant_id, kind, content,"
        " source_event_id, learned_at_tick, salience, created_at,"
        " updated_at, state_version FROM actor_memory"
        " ORDER BY memory_id ASC"
    ).fetchall()


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# ---------------------------------------------------------------------------
# 1. migration 0037's shape
# ---------------------------------------------------------------------------


def test_migration_0037_carries_the_two_tables_and_the_head_stamps() -> None:
    """Both tables exist with the contract's column sets, and the shared
    constants / a fresh database end at 0037 / 37."""

    assert MIGRATION_IDS[-1] == "0037_actor_memory_chapter_settlement"
    assert MIGRATION_IDS[-2] == "0036_action_replan"
    assert SCHEMA_HEAD_FILE == "0037_actor_memory_chapter_settlement.sql"
    assert SCHEMA_HEAD_VERSION == "37"

    fresh = sqlite3.connect(":memory:")
    apply_migrations(fresh)
    tables = {
        str(row[0])
        for row in fresh.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    for table in ("actor_memory", "chapter_settlement"):
        assert table in tables, table

    memory_columns = [
        (str(row[1]), str(row[2]), int(row[3]), row[4])
        for row in fresh.execute("PRAGMA table_info(actor_memory)").fetchall()
    ]
    assert [name for name, *_ in memory_columns] == [
        "memory_id",
        "world_id",
        "participant_id",
        "kind",
        "content",
        "source_event_id",
        "learned_at_tick",
        "salience",
        "created_at",
        "updated_at",
        "state_version",
    ]
    settlement_columns = [
        (str(row[1]), str(row[2]), int(row[3]), row[4])
        for row in fresh.execute(
            "PRAGMA table_info(chapter_settlement)"
        ).fetchall()
    ]
    assert [name for name, *_ in settlement_columns] == [
        "chapter_id",
        "summary",
        "storyline_updates",
        "hooks",
        "resolved_lines",
        "salience_notes",
        "created_at_revision",
        "created_at",
        "updated_at",
        "state_version",
    ]
    # chapter_settlement.chapter_id is the one-version PK (NOT NULL
    # implied by PRIMARY KEY: the pragmatic column reads notnull=0 for
    # rowid-aliased TEXT PKs, so the PK-ness is pinned by behavior in
    # the one-version test below).
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


def test_the_kind_check_admits_all_five_words_and_refuses_a_sixth(
    conn: sqlite3.Connection,
) -> None:
    """The five-word vocabulary is the table's own: every word insertable,
    a sixth refused by the CHECK (the dead-word law's storage half)."""

    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('world-probe', 'Probe', NULL, ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO world_event ("
        " event_id, world_id, kind, narration, effects, occurred_at,"
        " source, participants, run_id"
        ") VALUES ('ev-probe', 'world-probe', 'segment', 'n', '[]', ?,"
        " 'probe', '[]', NULL)",
        (NOW,),
    )
    for index, kind in enumerate(MemoryKind):
        conn.execute(
            "INSERT INTO actor_memory ("
            " memory_id, world_id, participant_id, kind, content,"
            " source_event_id, learned_at_tick, salience,"
            " created_at, updated_at, state_version"
            ") VALUES (?, 'world-probe', 'actor-a', ?, 'c', 'ev-probe',"
            " ?, NULL, ?, ?, 1)",
            (f"mem:ev-probe:actor-a:{kind.value}", kind.value, index, NOW, NOW),
        )
    conn.commit()
    assert _count(conn, "actor_memory") == 5
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO actor_memory ("
            " memory_id, world_id, participant_id, kind, content,"
            " source_event_id, learned_at_tick, salience,"
            " created_at, updated_at, state_version"
            ") VALUES ('mem:ev-probe:actor-a:FORGOTTEN', 'world-probe',"
            " 'actor-a', 'FORGOTTEN', 'c', 'ev-probe', 0, NULL, ?, ?, 1)",
            (NOW, NOW),
        )
    conn.rollback()
    assert _count(conn, "actor_memory") == 5


def test_the_settlement_table_is_one_version_per_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    director: Director,
) -> None:
    """``chapter_settlement``'s PK is the chapter id: a second version for
    the same chapter is refused at the database's own surface."""

    _opened_chapter(conn, world_store, cast_store, bible_store, director)
    conn.execute(
        "INSERT INTO chapter_settlement ("
        " chapter_id, summary, storyline_updates, hooks, resolved_lines,"
        " salience_notes, created_at_revision, created_at, updated_at,"
        " state_version) VALUES (?, 's', 'su', 'h', 'r', 'n', 1, ?, ?, 1)",
        (CH, NOW, NOW),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO chapter_settlement ("
            " chapter_id, summary, storyline_updates, hooks,"
            " resolved_lines, salience_notes, created_at_revision,"
            " created_at, updated_at, state_version"
            ") VALUES (?, 'second', 'su', 'h', 'r', 'n', 1, ?, ?, 1)",
            (CH, NOW, NOW),
        )
    conn.rollback()
    assert _count(conn, "chapter_settlement") == 1


# ---------------------------------------------------------------------------
# 2. NCP-3's memory arm
# ---------------------------------------------------------------------------


def test_ncp3_lands_one_experienced_row_per_participant(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Every canonical participant of the segment's event gets one
    ``EXPERIENCED`` row in the same transaction — the derived identity,
    the event's narration, the commit's ``actual_end_tick``."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    outcome = committed.value
    assert outcome.actual_start_tick == 0
    assert outcome.actual_end_tick == 3

    rows = _memory_rows(conn)
    assert len(rows) == 2
    by_id = {str(row[0]): row for row in rows}
    for participant in ("actor-lia", "pc-you"):
        memory_id = memory_id_for(
            outcome.event_id, participant, MemoryKind.EXPERIENCED
        )
        assert memory_id in by_id, memory_id
        row = by_id[memory_id]
        assert str(row[1]) == TOWN
        assert str(row[2]) == participant
        assert str(row[3]) == "EXPERIENCED"
        assert str(row[4]) == "the two meet at the bindery steps"
        assert str(row[5]) == outcome.event_id
        assert int(row[6]) == 3
        assert row[7] is None
        assert int(row[10]) == 1


def test_the_replayed_segment_lands_zero_new_memory_rows(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The arm is on the fresh path only: a replayed ``segment_key``
    answers the stored outcome and touches no memory row (the replay arm
    answers first)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store)
    assert isinstance(first, Ok)
    rows_before = _memory_rows(conn)
    assert len(rows_before) == 2

    again = _commit(
        conn, narrative, world_store, now="2026-10-13T06:00:00+00:00"
    )
    assert isinstance(again, Ok)
    assert again.value == first.value
    assert _memory_rows(conn) == rows_before  # byte-identical rows, zero write


# ---------------------------------------------------------------------------
# 3. NCP-2's memory arm
# ---------------------------------------------------------------------------


def test_ncp2_lands_the_actions_memory_and_replays_zero(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The ruling's participants each get one ``EXPERIENCED`` row inside
    NCP-2 — content = the event's narration (the ruling's ``outcome``),
    learned_at_tick = the post-advance ``actual_end``; a replayed ruling
    lands zero new rows."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    opened = open_gate(
        conn,
        scene_id=SCENE,
        gate_seq=1,
        options=("offer the repair job", "ask about the letter", "walk away"),
        now=NOW,
    )
    assert isinstance(opened, Ok)
    submitted = submit_gate(
        conn,
        gate_id=GATE,
        submission_id="sub-1",
        intent_text="I offer to help with the ledger.",
        selected_option=None,
        now=NOW,
    )
    assert isinstance(submitted, Ok)
    committed = _committed_action(conn, world_store, narrative)
    assert isinstance(committed, Ok)
    assert committed.value.actual_end_tick == 7

    rows = _memory_rows(conn)
    assert len(rows) == 2
    by_id = {str(row[0]): row for row in rows}
    for participant in ("pc-you", "actor-lia"):
        memory_id = memory_id_for(
            committed.value.event_id, participant, MemoryKind.EXPERIENCED
        )
        assert memory_id in by_id, memory_id
        row = by_id[memory_id]
        assert str(row[2]) == participant
        assert str(row[3]) == "EXPERIENCED"
        assert str(row[4]) == "Lia lets you hold the ledger; the ice thins."
        assert str(row[5]) == f"ac:{GATE}:sub-1:event"
        assert int(row[6]) == 7

    again = _committed_action(
        conn, world_store, narrative, now="2026-10-13T07:00:00+00:00"
    )
    assert isinstance(again, Ok)
    assert _memory_rows(conn) == rows
    assert _count(conn, "actor_memory") == 2


# ---------------------------------------------------------------------------
# 4. record_belief — the four caller-supplied kinds
# ---------------------------------------------------------------------------


def _belief(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    kind: MemoryKind,
    participant: str = "actor-lia",
    content: str = "the rumour of a letter",
    learned_at_tick: int = 4,
    now: str = LATER,
    salience: float | None = None,
    world_id: str = TOWN,
):
    return record_belief(
        conn,
        world_id=world_id,
        event_id=event_id,
        participant_id=participant,
        kind=kind,
        content=content,
        learned_at_tick=learned_at_tick,
        now=now,
        salience=salience,
    )


def test_record_belief_writes_the_four_caller_kinds_and_refuses_experienced(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """HEARD / BELIEVED / INFERRED / MISTAKEN are all reachable through
    this face (the five-word reachability law: no dead kind), and
    ``EXPERIENCED`` is refused — the witnessed kind is the commits' own
    automatic arm."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    event_id = committed.value.event_id

    for kind in (
        MemoryKind.HEARD,
        MemoryKind.BELIEVED,
        MemoryKind.INFERRED,
        MemoryKind.MISTAKEN,
    ):
        written = _belief(conn, event_id=event_id, kind=kind)
        assert isinstance(written, Ok), kind
        assert written.value.kind is kind
        assert written.value.memory_id == memory_id_for(
            event_id, "actor-lia", kind
        )
        assert written.value.content == "the rumour of a letter"
        assert written.value.learned_at_tick == 4
        assert written.value.salience is None
        assert written.value.state_version == 1

    # four caller kinds + the two automatic EXPERIENCED rows.
    assert _count(conn, "actor_memory") == 6

    witnessed = _belief(
        conn, event_id=event_id, kind=MemoryKind.EXPERIENCED
    )
    assert isinstance(witnessed, Err)
    assert witnessed.error.code == DomainErrorCode.VALIDATION_FAILED
    assert "automatic arm" in (witnessed.error.message or "")


def test_record_belief_replay_and_shape_conflict(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The same derived identity with the same shape rides back as the
    stored row (zero write); a different shape is a ``CONFLICT`` —
    memories are append-only and do not rewrite (N-INV-003)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    event_id = committed.value.event_id

    first = _belief(conn, event_id=event_id, kind=MemoryKind.HEARD)
    assert isinstance(first, Ok)
    replay = _belief(
        conn,
        event_id=event_id,
        kind=MemoryKind.HEARD,
        now="2026-10-13T09:00:00+00:00",
    )
    assert isinstance(replay, Ok)
    assert replay.value == first.value  # the stored row, stamps unchanged

    changed = _belief(
        conn,
        event_id=event_id,
        kind=MemoryKind.HEARD,
        content="a different telling",
    )
    assert isinstance(changed, Err)
    assert changed.error.code == DomainErrorCode.CONFLICT

    with_salience = _belief(
        conn,
        event_id=event_id,
        kind=MemoryKind.HEARD,
        salience=0.5,
    )
    assert isinstance(with_salience, Err)
    assert with_salience.error.code == DomainErrorCode.CONFLICT


def test_record_belief_refuses_the_malformed_and_the_dangling(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The caller's own payload answers ``VALIDATION_FAILED``; a dangling
    event answers ``NOT_FOUND``; an event of another world is refused —
    a memory names its own world's event."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    event_id = committed.value.event_id

    empty = _belief(
        conn, event_id=event_id, kind=MemoryKind.HEARD, participant="   "
    )
    assert isinstance(empty, Err)
    assert empty.error.code == DomainErrorCode.VALIDATION_FAILED

    dangling = _belief(conn, event_id="no-such-event", kind=MemoryKind.HEARD)
    assert isinstance(dangling, Err)
    assert dangling.error.code == DomainErrorCode.NOT_FOUND

    negative = _belief(
        conn, event_id=event_id, kind=MemoryKind.HEARD, learned_at_tick=-1
    )
    assert isinstance(negative, Err)
    assert negative.error.code == DomainErrorCode.VALIDATION_FAILED

    bad_kind = _belief(conn, event_id=event_id, kind="HEARD")  # type: ignore[arg-type]
    assert isinstance(bad_kind, Err)
    assert bad_kind.error.code == DomainErrorCode.VALIDATION_FAILED

    # another world's event is not this memory's source.
    assert isinstance(
        world_store.create_world("world-else", "Else", None, NOW), Ok
    )
    conn.execute(
        "INSERT INTO world_event ("
        " event_id, world_id, kind, narration, effects, occurred_at,"
        " source, participants, run_id"
        ") VALUES ('ev-else', 'world-else', 'segment', 'n', '[]', ?,"
        " 'probe', '[]', NULL)",
        (NOW,),
    )
    conn.commit()
    cross = _belief(
        conn, event_id="ev-else", kind=MemoryKind.HEARD, world_id=TOWN
    )
    assert isinstance(cross, Err)
    assert cross.error.code == DomainErrorCode.VALIDATION_FAILED


# ---------------------------------------------------------------------------
# 5. v3_memory_view — the viewer's read
# ---------------------------------------------------------------------------


def test_v3_memory_view_layers_by_kind_and_orders_by_tick(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """One viewer's memory: layered by the five-word kind order, then by
    ``learned_at_tick`` — a deterministic walk; another viewer sees only
    its own rows, and a stranger answers the honest empty view."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store)
    assert isinstance(first, Ok)
    second = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        body="She turns the ledger toward the lamp.",
        narration="the ledger opens",
        duration_ticks=2,
        now=LATER,
    )
    assert isinstance(second, Ok)
    assert second.value.actual_end_tick == 5

    # two HEARD rows on different events with different ticks: inside the
    # HEARD layer the tick orders them.
    heard_late = _belief(
        conn,
        event_id=first.value.event_id,
        kind=MemoryKind.HEARD,
        content="heard late",
        learned_at_tick=9,
    )
    assert isinstance(heard_late, Ok)
    heard_early = _belief(
        conn,
        event_id=second.value.event_id,
        kind=MemoryKind.HEARD,
        content="heard early",
        learned_at_tick=7,
    )
    assert isinstance(heard_early, Ok)

    view = v3_memory_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(view, Ok)
    assert view.value.viewer_id == "actor-lia"
    assert [(m.kind, m.learned_at_tick) for m in view.value.memories] == [
        (MemoryKind.EXPERIENCED, 3),
        (MemoryKind.EXPERIENCED, 5),
        (MemoryKind.HEARD, 7),
        (MemoryKind.HEARD, 9),
    ]
    assert [m.content for m in view.value.memories[2:]] == [
        "heard early",
        "heard late",
    ]

    as_player = v3_memory_view(conn, world_id=TOWN, viewer_id="pc-you")
    assert isinstance(as_player, Ok)
    assert [m.kind for m in as_player.value.memories] == [
        MemoryKind.EXPERIENCED,
        MemoryKind.EXPERIENCED,
    ]

    stranger = v3_memory_view(conn, world_id=TOWN, viewer_id="actor-stranger")
    assert isinstance(stranger, Ok)
    assert stranger.value.memories == ()


def test_v3_memory_view_refuses_a_malformed_viewer(
    conn: sqlite3.Connection,
) -> None:
    """The viewer is the read's own address: an empty or malformed one is
    refused ``VALIDATION_FAILED`` (the cognition face's own posture)."""

    for viewer in ("", "   ", 123, None):
        refused = v3_memory_view(conn, world_id=TOWN, viewer_id=viewer)  # type: ignore[arg-type]
        assert isinstance(refused, Err)
        assert refused.error.code == DomainErrorCode.VALIDATION_FAILED


# ---------------------------------------------------------------------------
# 6. NCP-4 — the chapter settlement
# ---------------------------------------------------------------------------


def _settling_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The full chain up to a ``SETTLING`` chapter with one committed
    segment (tick 3)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    settled = narrative.settle_chapter(CH, now=LATER, expected_state_version=2)
    assert isinstance(settled, Ok)
    assert settled.value.status is ChapterStatus.SETTLING


def test_ncp4_settles_in_one_transaction_and_replays_as_a_no_op(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """One short transaction lands the settlement row and flips
    ``SETTLING → CLOSED`` with ``closed_at_tick`` = the transaction's own
    tick read; the tick is **not** advanced; no ``world_event`` /
    ``world_state_fact`` / ``actor_memory`` row is written (N-INV-004);
    a replay rides the stored row back, zero write."""

    _settling_chapter(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    counts_before = {
        table: _count(conn, table)
        for table in ("world_event", "world_state_fact", "actor_memory")
    }
    chapter_before = narrative.get_chapter(CH)
    assert chapter_before is not None

    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    record = settled.value
    assert record.chapter_id == CH
    assert record.summary == (
        f"sg:{SCENE}:0001: the two meet at the bindery steps"
    )
    assert record.storyline_updates == ""  # no active lines seeded
    assert record.hooks == "who is the letter from?"
    assert record.resolved_lines == ""
    assert "salience" in record.salience_notes
    assert record.created_at_revision == 1
    assert record.state_version == 1

    chapter = narrative.get_chapter(CH)
    assert chapter is not None
    assert chapter.status is ChapterStatus.CLOSED
    assert chapter.closed_at_tick == 3
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 3  # the settlement has no duration
    assert _count(conn, "chapter_settlement") == 1
    for table, count in counts_before.items():
        assert _count(conn, table) == count, table

    # the replay: the stored row, stamps and all — zero write.
    replay = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER2,
    )
    assert isinstance(replay, Ok)
    assert replay.value == record
    assert _count(conn, "chapter_settlement") == 1


def test_ncp4_shape_different_replay_is_a_conflict(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """One version per chapter: a stored row whose shape differs from the
    freshly derived one is a ``CONFLICT`` — the settlement does not
    rewrite."""

    _settling_chapter(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)

    # the derived shape moved (the test's own tampering stands in for any
    # divergence): the stored version does not follow.
    conn.execute(
        "UPDATE chapter_settlement SET summary = 'a different telling'"
        " WHERE chapter_id = ?",
        (CH,),
    )
    conn.commit()
    replay = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER2,
    )
    assert isinstance(replay, Err)
    assert replay.error.code == DomainErrorCode.CONFLICT
    stored = conn.execute(
        "SELECT summary FROM chapter_settlement WHERE chapter_id = ?",
        (CH,),
    ).fetchone()
    assert stored is not None and str(stored[0]) == "a different telling"


def test_ncp4_refuses_the_planned_active_and_settlementless_closed_chapters(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Only a ``SETTLING`` chapter settles: a ``PLANNED`` one (nothing
    committed to compress), an ``ACTIVE`` one (the story has not stopped)
    and a ``CLOSED`` one without a settlement row are all refused
    ``VALIDATION_FAILED``, nothing written."""

    # PLANNED.
    _opened_chapter(conn, world_store, cast_store, bible_store, director)
    planned = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=NOW,
    )
    assert isinstance(planned, Err)
    assert planned.error.code == DomainErrorCode.VALIDATION_FAILED
    assert _count(conn, "chapter_settlement") == 0

    # ACTIVE.
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    active = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(active, Err)
    assert active.error.code == DomainErrorCode.VALIDATION_FAILED
    assert _count(conn, "chapter_settlement") == 0

    # CLOSED through the store's own flip faces, without NCP-4.
    moved = narrative.settle_chapter(CH, now=LATER, expected_state_version=2)
    assert isinstance(moved, Ok)
    closed = narrative.close_chapter(
        CH, closed_at_tick=0, now=LATER, expected_state_version=3
    )
    assert isinstance(closed, Ok)
    settledless = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER2,
    )
    assert isinstance(settledless, Err)
    assert settledless.error.code == DomainErrorCode.VALIDATION_FAILED
    assert _count(conn, "chapter_settlement") == 0

    # a dangling chapter.
    dangling = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id="no-such-chapter",
        now=LATER2,
    )
    assert isinstance(dangling, Err)
    assert dangling.error.code == DomainErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# 7. the two read reroutes
# ---------------------------------------------------------------------------


def test_director_context_carries_the_chapter_summaries(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The next-chapter read-only summary face: only ``CLOSED`` chapters'
    settlements ride ``DirectorContext.chapter_summaries``, in
    ``chapter_index`` order."""

    _settling_chapter(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    before = director.context(TOWN)
    assert before.chapter_summaries == ()
    assert chapter_settlements_of(conn, TOWN) == ()

    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    after = director.context(TOWN)
    assert after.chapter_summaries == (settled.value,)
    assert chapter_settlements_of(conn, TOWN) == (settled.value,)
    # the five pre-existing arms stay intact.
    assert after.world_id == TOWN
    assert after.bible is not None
    assert after.cast.player_character is not None
    assert after.current_tick == 3


def test_open_scene_carries_the_povs_memory_view(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The dossier's memory reroute: ``SceneContext.memory`` carries the
    POV's ``v3_memory_view`` beside the still-present cognition view —
    the second scene's POV has witnessed the first scene's event."""

    _two_scene_chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)

    opened = planner.open_scene(SCENE2, NOW)
    assert isinstance(opened, Ok)
    context = opened.value.context
    assert context.pov_actor_id == "actor-lia"
    assert context.memory.viewer_id == "actor-lia"
    assert [m.kind for m in context.memory.memories] == [
        MemoryKind.EXPERIENCED
    ]
    memory = context.memory.memories[0]
    assert memory.participant_id == "actor-lia"
    assert memory.source_event_id == committed.value.event_id
    assert memory.learned_at_tick == committed.value.actual_end_tick
    # the compatibility / fallback arm still rides beside it.
    assert [event.event_id for event in context.cognition.witnessed] == [
        committed.value.event_id
    ]


# ---------------------------------------------------------------------------
# 8. the recovery scan's sixth family
# ---------------------------------------------------------------------------


def test_recovery_scan_surfaces_the_settling_family(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """RA §29's "V3-7 落法": the ``SETTLING`` chapters are their own
    deterministically-ordered family, and the ``chapters`` family keeps
    its ``ACTIVE`` / ``SETTLING`` rows intact (a subset, not a
    replacement)."""

    _settling_chapter(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    scan = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(scan, Ok)
    assert [c.chapter_id for c in scan.value.settling_chapters] == [CH]
    assert [c.status for c in scan.value.settling_chapters] == [
        ChapterStatus.SETTLING
    ]
    # the pre-existing family is untouched: the same chapter, both views.
    assert [c.chapter_id for c in scan.value.chapters] == [CH]
    assert [c.status for c in scan.value.chapters] == [ChapterStatus.SETTLING]
    assert [
        s.scene_id for s in scan.value.scenes
    ] == [SCENE]
    assert scan.value.gates == ()
    assert scan.value.actions == ()
    assert scan.value.replans == ()

    # after NCP-4 the chapter is CLOSED: neither family lists it.
    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    after = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(after, Ok)
    assert after.value.settling_chapters == ()
    assert after.value.chapters == ()


# ---------------------------------------------------------------------------
# 9. the module discipline
# ---------------------------------------------------------------------------


def _sql_constants(tree: ast.AST) -> list[str]:
    """Every SQL-shaped string constant in one module (a constant that
    *starts* with a DML keyword)."""

    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.match(r"(?i)^\s*(select|insert|update|delete)\b", node.value):
                found.append(node.value)
    return found


def _all_constants(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def test_every_memory_write_face_is_one_transaction() -> None:
    """``record_belief`` opens exactly one ``BEGIN IMMEDIATE`` and lands
    exactly one ``COMMIT``; the shared commit arm opens none (it rides
    the caller's transaction); the read face opens none. No attribute
    call may be named commit / rollback (the constants are the only
    spelling)."""

    public = _function(MEMORY_TREE, "record_belief")
    constants = _all_constants(public)
    assert constants.count("BEGIN IMMEDIATE") == 1
    assert constants.count("COMMIT") == 1

    arm = _function(MEMORY_TREE, "record_experienced_in_transaction")
    assert _sql_constants(arm), "the arm carries no SQL"
    for text in _all_constants(arm):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text

    read = _function(MEMORY_TREE, "v3_memory_view")
    for text in _all_constants(read):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text

    for node in ast.walk(MEMORY_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"commit", "rollback"}, node.func.attr


def test_the_memory_module_builds_no_sql_and_reads_no_package() -> None:
    """Fixed literals and parameter binding only (no interpolated SQL),
    and the Package is not consulted — the durable rows are the
    authority."""

    for node in ast.walk(MEMORY_TREE):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("elc.world.package"), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("elc.world.package"), (
                node.module
            )
    for text in _sql_constants(MEMORY_TREE):
        assert "{" not in text, text
        assert "}" not in text, text
    # every execute() call's statement is a plain constant — an f-string
    # argument would be interpolation.
    for node in ast.walk(MEMORY_TREE):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ):
            assert node.args, "execute() with no statement"
            assert isinstance(node.args[0], ast.Constant), ast.dump(node)


def test_settle_chapter_is_one_transaction_and_writes_no_new_facts() -> None:
    """NCP-4: the public face owns one ``BEGIN IMMEDIATE`` / ``COMMIT``;
    its body carries no transaction control; the only writes it makes
    are the one-version ``chapter_settlement`` row (N-INV-004's storage
    face: no ``world_event`` / ``world_state_fact`` / ``actor_memory``
    write anywhere in the settlement's machinery), and its derivation is
    pure reads."""

    public = _function(SETTLEMENT_TREE, "settle_chapter")
    constants = _all_constants(public)
    assert constants.count("BEGIN IMMEDIATE") == 1
    assert constants.count("COMMIT") == 1
    assert _sql_constants(public) == []

    body = _function(SETTLEMENT_TREE, "_settle_chapter_tx")
    for text in _all_constants(body):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text
    writes = [
        text
        for text in _sql_constants(body)
        if re.match(r"(?i)^\s*(insert|update|delete)", text)
    ]
    assert len(writes) == 1
    assert re.match(r"(?i)^\s*INSERT INTO chapter_settlement", writes[0])
    for text in writes:
        for forbidden in ("world_event", "world_state_fact", "actor_memory"):
            assert forbidden not in text, (forbidden, text)

    draft = _function(SETTLEMENT_TREE, "_settlement_draft")
    for text in _sql_constants(draft):
        assert re.match(r"(?i)^\s*select", text), text

    read = _function(SETTLEMENT_TREE, "chapter_settlements_of")
    for text in _all_constants(read):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text


def test_the_commit_transactions_carry_the_memory_arm() -> None:
    """One truth, two callers: both commit bodies invoke the shared
    ``record_experienced_in_transaction`` arm (the V3-7 memory arm is in
    the commit transactions, not a side face)."""

    for tree, name in (
        (SETTLEMENT_TREE, "_commit_segment_tx"),
    ):
        body = _function(tree, name)
        called = {
            node.func.id
            for node in ast.walk(body)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "record_experienced_in_transaction" in called
    action_tree = ast.parse(
        (SRC_ROOT / "world" / "action.py").read_text(encoding="utf-8")
    )
    body = _function(action_tree, "_commit_action_tx")
    called = {
        node.func.id
        for node in ast.walk(body)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "record_experienced_in_transaction" in called


def test_the_memory_module_imports_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline): the leaf module and its
    importer both start clean."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    for module in ("elc.world.memory", "elc.world.settlement"):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, (module, proc.stderr)


def test_memory_is_not_re_exported_from_the_world_package() -> None:
    """The new module stays narrow (the V3-1..V3-6 precedent): it is not
    widened through the package root."""

    source = (SRC_ROOT / "world" / "__init__.py").read_text(encoding="utf-8")
    assert "from elc.world.memory" not in source
    assert "V3MemoryView" not in source
    assert "MemoryKind" not in source


def test_the_settlement_record_is_exported_beside_its_face() -> None:
    """The settlement's public surface: the record shape and the two
    faces ride ``__all__`` (the read face the Director context calls,
    the orchestration the recovery calls)."""

    from elc.world import settlement

    assert "settle_chapter" in settlement.__all__
    assert "chapter_settlements_of" in settlement.__all__
    assert "ChapterSettlementRecord" in settlement.__all__


def test_cognition_and_memory_views_coexist_on_the_opening(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The descent is a reroute, not a removal: the opened context
    carries both views, and a listener who witnessed the event appears
    in each under the same canonical identity."""

    _two_scene_chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    opened = planner.open_scene(SCENE2, LATER)
    assert isinstance(opened, Ok)
    context = opened.value.context
    assert context.pov_actor_id == context.memory.viewer_id
    assert context.pov_actor_id == context.cognition.viewer_id
    assert context.memory.memories[0].source_event_id == (
        context.cognition.witnessed[0].event_id
    )
    assert context.memory.memories[0].learned_at_tick == (
        context.cognition.witnessed[0].actual_end_tick
    )


def test_the_settled_scene_rows_survive_the_settlement(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """N-INV-004's other half, behaviourally: the settlement changes the
    chapter row only — the scene's status and actual span, the passage,
    the lineage row and the memory rows are untouched."""

    _settling_chapter(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    scene_before = narrative.get_scene(SCENE)
    assert scene_before is not None
    passage_before = conn.execute(
        "SELECT body, created_at_tick FROM narrative_passage"
    ).fetchall()
    lineage_before = conn.execute(
        "SELECT commit_id, actual_start_tick, actual_end_tick, event_id"
        " FROM segment_commit"
    ).fetchall()
    memory_before = _memory_rows(conn)

    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    scene_after = narrative.get_scene(SCENE)
    assert scene_after == scene_before
    assert scene_after.status is SceneStatus.ACTIVE
    assert scene_after.actual_start_tick == 0
    assert scene_after.actual_end_tick == 3
    assert (
        conn.execute(
            "SELECT body, created_at_tick FROM narrative_passage"
        ).fetchall()
        == passage_before
    )
    assert (
        conn.execute(
            "SELECT commit_id, actual_start_tick, actual_end_tick, event_id"
            " FROM segment_commit"
        ).fetchall()
        == lineage_before
    )
    assert _memory_rows(conn) == memory_before
    # the dossier revision's plan face is untouched too.
    dossiers = narrative.dossiers_of(SCENE)
    assert [d.status for d in dossiers] == [PlanRevisionStatus.ADOPTED]
