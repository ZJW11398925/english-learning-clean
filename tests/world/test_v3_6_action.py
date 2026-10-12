"""V3-6 — User Gate + ``user_action`` + Action Resolver + OUTCOME COMMIT
(TASK-OPI-dc1bafdf…23 / the opening ruling DEC-OPI-dc1bafdf…5, re-run
revision …21; VAL-OPI-dc1bafdf…25; the V3-6R correction
TASK-OPI-dc1bafdf…33 / the opening ruling …31).

The Narrative V3 program's sixth cut: migration 0035's two tables
(``user_gate`` / ``user_action``) plus ``segment_commit``'s rebuild (the
``'ACTION_OUTCOME'`` kind and its ``action_id``), the NCP-1 and NCP-2
transactions (:mod:`elc.world.action`), the SEGMENT COMMIT's two
interlock arms (:mod:`elc.world.settlement`) and the SCENE replan arm
(:meth:`elc.world.scene.ScenePlanner.replan_scene`). The V3-6R
correction re-keys the replan arm through the durable obligation
(``action_replan``) and tightens the commit doors — this suite carries
the migrated pins, and ``test_v3_6r_replan_outcome.py`` carries the
correction's own new pins. The groups:

1. **migration 0035's shape** — the two tables' columns, the CHECK
   vocabularies, the terminal-integrity composite CHECK, the
   ``UNIQUE (gate_id, submission_id)`` anchor, the rebuilt
   ``segment_commit``'s two kind-consistency CHECKs with
   ``is_last_segment`` and its UNIQUE carried through, the stamps;
2. **NCP-1** — one short transaction lands the gate's flip and the
   action row's birth, the replay rides back, a claimed gate refuses a
   second submission, the option and the scene's status are judged;
3. **NCP-2** — one short transaction lands the eight terminal columns,
   the behaviour event, the state settlement, the tick, the scene's
   extended span, the ACTION_OUTCOME lineage row, the gate's flip and
   the chapter arm; the participants discipline refuses; a deep
   injection rolls the whole group back; the replay is a whole-group
   no-op or a CONFLICT;
4. **``begin_resolving``** — both rows in one transaction, idempotent
   from ``RESOLVING``, the terminal words refused;
5. **the adjudication's sole writership (intent ≠ world fact)** — the
   submission's own words never reach ``world_event`` /
   ``world_state_fact``;
6. **the replan verdicts** — ``NONE`` moves no plan row (and births no
   obligation), ``SCENE`` mints the scene's next adopted dossier
   revision through the obligation (and the Writer reads it),
   ``CHAPTER`` lands a new adopted Blueprint revision through
   ``apply_action_replan`` whose content the next scene's open reads;
7. **the interlock** — a non-terminal gate refuses a fresh segment
   (the replay is still answered), and the resuming segment carrying
   the gate's action as its ``outcome_ref`` closes that gate atomically;
8. **the recovery scan, the module discipline and the chain head** —
   RA §29's five families, the post-NCP-1 re-adjudication's unique
   outcome, no Package face / no interpolated SQL / one transaction per
   face / the cold start, and the shared constants ending at V3-7's
   ``0037_actor_memory_chapter_settlement`` / ``37`` (``0036_action_replan``
   / ``36`` was the head when this cut landed; the head literal migrated
   the P9-1 way).
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
    ActionStatus,
    Adjudication,
    GateStatus,
    ReplanScope,
    ReplanStatus,
    UserActionRecord,
    UserGateRecord,
    action_of,
    begin_resolving,
    commit_action,
    gates_of,
    get_gate,
    open_gate,
    pending_replans,
    recovery_scan,
    replan_obligation,
    replan_request_id_for,
    submit_gate,
)
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
from elc.world.settlement import commit_segment, story_time_of
from elc.world.store import SqliteWorldStore
from elc.world.types import StateEffect
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
SCENE2 = "world-town-ch01-s02"
GATE = "world-town-ch01-s01-g01"

ACTION_TREE = ast.parse(
    (SRC_ROOT / "world" / "action.py").read_text(encoding="utf-8")
)
SETTLEMENT_TREE = ast.parse(
    (SRC_ROOT / "world" / "settlement.py").read_text(encoding="utf-8")
)
NARRATIVE_STORE_TREE = ast.parse(
    (SRC_ROOT / "world" / "narrative" / "store.py").read_text(
        encoding="utf-8"
    )
)

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


@pytest.fixture()
def writer(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    narrative: SqliteNarrativeStore,
) -> PovWriter:
    return PovWriter(conn, narrative_store=narrative, world_store=world_store)


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
    narrative: SqliteNarrativeStore,
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
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        scenes=scenes,
    )
    opened = planner.open_scene(scene_id, NOW)
    assert isinstance(opened, Ok)
    return scene_id


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


def _gate(
    conn: sqlite3.Connection,
    *,
    scene_id: str = SCENE,
    gate_seq: int = 1,
    options: tuple[str, ...] = (
        "offer the repair job",
        "ask about the letter",
        "walk away",
    ),
    now: str = NOW,
):
    return open_gate(
        conn, scene_id=scene_id, gate_seq=gate_seq, options=options, now=now
    )


def _submitted(
    conn: sqlite3.Connection,
    *,
    gate_id: str = GATE,
    submission_id: str = "sub-1",
    intent_text: str = "I offer to help with the ledger.",
    selected_option: str | None = "offer the repair job",
    now: str = NOW,
):
    return submit_gate(
        conn,
        gate_id=gate_id,
        submission_id=submission_id,
        intent_text=intent_text,
        selected_option=selected_option,
        now=now,
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
    # gate already RESOLVING rides; a dangling gate or a stored replay is
    # left to the face's own refusals and answers).
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


def _chain(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    *,
    adjudication: Adjudication | None = None,
) -> None:
    """A gate through its ruling: scene active, gate open, submission in,
    ruling landed (tick 0 → 7)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    assert isinstance(
        _committed_action(
            conn, world_store, narrative, adjudication=adjudication
        ),
        Ok,
    )


def _row_counts(conn: sqlite3.Connection, tables: tuple[str, ...]) -> dict[str, int]:
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()):
    return conn.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# 1. migration 0035's shape
# ---------------------------------------------------------------------------


def test_user_gate_carries_its_columns_and_vocabulary(
    conn: sqlite3.Connection,
) -> None:
    """``user_gate``'s physical column set, in order, and the five-word
    CHECK (STATE §23 verbatim — a sixth word refuses)."""

    columns = [
        (str(row[1]), str(row[2]), int(row[3]), row[4], int(row[5]))
        for row in conn.execute("PRAGMA table_info(user_gate)").fetchall()
    ]
    assert [(name, kind) for name, kind, *_ in columns] == [
        ("gate_id", "TEXT"),
        ("scene_id", "TEXT"),
        ("status", "TEXT"),
        ("opened_at_tick", "INTEGER"),
        ("options_json", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
        ("state_version", "INTEGER"),
    ]
    assert columns[0][4] == 1  # gate_id is the primary key
    # SQLite's notnull flag reads 0 on the TEXT primary key (the
    # sibling suites' own note); every other column is NOT NULL. The
    # CHECKs are behavioural below (a PRAGMA cannot see them).
    for name, _, not_null, _, _ in columns[1:5]:
        assert not_null == 1, name

    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO world_chapter ("
        " chapter_id, world_id, chapter_index, status, opened_at_tick,"
        " closed_at_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01', 'w', 1, 'ACTIVE', 0, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO world_scene ("
        " scene_id, chapter_id, scene_index, status, actual_start_tick,"
        " actual_end_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01-s01', 'w-ch01', 1, 'ACTIVE', NULL, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_gate ("
        " gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version"
        ") VALUES ('g', 'w-ch01-s01', 'OPEN', 0, '[\"a\",\"b\"]', ?, ?, 1)",
        (NOW, NOW),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE user_gate SET status = 'PONDERING' WHERE gate_id = 'g'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE user_gate SET state_version = 0 WHERE gate_id = 'g'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO user_gate ("
            " gate_id, scene_id, status, opened_at_tick, options_json,"
            " created_at, updated_at, state_version"
            ") VALUES ('g2', 'nope', 'OPEN', 0, '[]', ?, ?, 1)",
            (NOW, NOW),
        )


def test_user_action_carries_its_terminal_integrity_check(
    conn: sqlite3.Connection,
) -> None:
    """``user_action``: the three-word status (no ``OPEN``), the
    composite CHECK that a ``COMMITTED`` row carries all eight terminal
    columns, the ``replan_scope`` vocabulary and the
    ``UNIQUE (gate_id, submission_id)`` anchor."""

    columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(user_action)")
    }
    assert columns == {
        "user_action_id",
        "gate_id",
        "submission_id",
        "intent_text",
        "selected_option",
        "status",
        "interpretation",
        "outcome",
        "actual_action",
        "consequences",
        "state_effects",
        "participants",
        "replan_scope",
        "actual_tick",
        "created_at",
        "updated_at",
        "state_version",
    }
    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO world_chapter ("
        " chapter_id, world_id, chapter_index, status, opened_at_tick,"
        " closed_at_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01', 'w', 1, 'ACTIVE', 0, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO world_scene ("
        " scene_id, chapter_id, scene_index, status, actual_start_tick,"
        " actual_end_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01-s01', 'w-ch01', 1, 'ACTIVE', NULL, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_gate ("
        " gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version"
        ") VALUES ('g', 'w-ch01-s01', 'OPEN', 0, '[\"a\",\"b\"]', ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_action ("
        " user_action_id, gate_id, submission_id, intent_text,"
        " selected_option, status, created_at, updated_at, state_version"
        ") VALUES ('g-a', 'g', 'sub-1', 'intent', NULL, 'ANSWERED', ?, ?, 1)",
        (NOW, NOW),
    )
    # The UNIQUE anchor: the same submission again refuses.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO user_action ("
            " user_action_id, gate_id, submission_id, intent_text,"
            " selected_option, status, created_at, updated_at,"
            " state_version"
            ") VALUES ('g-a2', 'g', 'sub-1', 'again', NULL, 'ANSWERED',"
            " ?, ?, 1)",
            (NOW, NOW),
        )
    # A COMMITTED row with a NULL terminal column refuses (the composite
    # CHECK's whole point).
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE user_action SET status = 'COMMITTED'"
            " WHERE user_action_id = 'g-a'"
        )
    # The three-word status: no OPEN word exists.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE user_action SET status = 'OPEN'"
            " WHERE user_action_id = 'g-a'"
        )
    # The replan vocabulary's third word refuses.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE user_action SET replan_scope = 'SAGA'"
            " WHERE user_action_id = 'g-a'"
        )
    # The full terminal face is admissible.
    conn.execute(
        "UPDATE user_action SET status = 'COMMITTED',"
        " interpretation = 'i', outcome = 'o', actual_action = 'a',"
        " consequences = 'c', state_effects = '[]', participants = '[]',"
        " replan_scope = 'NONE', actual_tick = 3 WHERE user_action_id = 'g-a'"
    )
    row = conn.execute(
        "SELECT status, replan_scope FROM user_action WHERE user_action_id = 'g-a'"
    ).fetchone()
    assert (row[0], row[1]) == ("COMMITTED", "NONE")


def test_the_rebuilt_segment_commit_carries_both_kinds(
    conn: sqlite3.Connection,
) -> None:
    """The rebuild's face: ``action_id`` arrives, ``segment_seq`` /
    ``passage_id`` go NULLable, the two kind-consistency CHECKs hold,
    and V3-5R's ``is_last_segment`` plus ``UNIQUE (scene_id,
    segment_seq)`` survive verbatim."""

    info = {
        str(row[1]): (str(row[2]), int(row[3]), int(row[5]))
        for row in conn.execute("PRAGMA table_info(segment_commit)").fetchall()
    }
    assert set(info) == {
        "commit_id",
        "kind",
        "scene_id",
        "segment_seq",
        "passage_id",
        "action_id",
        "actual_start_tick",
        "actual_end_tick",
        "event_id",
        "is_last_segment",
        "created_at",
        "updated_at",
        "state_version",
    }
    assert info["segment_seq"][1] == 0  # nullable now
    assert info["passage_id"][1] == 0
    assert info["is_last_segment"] == ("INTEGER", 1, 0)
    indexes = [
        str(row[1])
        for row in conn.execute("PRAGMA index_list(segment_commit)").fetchall()
    ]
    keys: list[list[str]] = []
    for name in indexes:
        keys.append(
            [
                str(row[2])
                for row in conn.execute(f"PRAGMA index_info({name})").fetchall()
            ]
        )
    assert ["scene_id", "segment_seq"] in keys

    conn.execute(
        "INSERT INTO world (world_id, name, template_world_id, created_at)"
        " VALUES ('w', 'W', NULL, ?)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO world_chapter ("
        " chapter_id, world_id, chapter_index, status, opened_at_tick,"
        " closed_at_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01', 'w', 1, 'ACTIVE', 0, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO world_scene ("
        " scene_id, chapter_id, scene_index, status, actual_start_tick,"
        " actual_end_tick, created_at, updated_at, state_version"
        ") VALUES ('w-ch01-s01', 'w-ch01', 1, 'ACTIVE', NULL, NULL, ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_gate ("
        " gate_id, scene_id, status, opened_at_tick, options_json,"
        " created_at, updated_at, state_version"
        ") VALUES ('g', 'w-ch01-s01', 'COMMITTED', 0, '[\"a\",\"b\"]', ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO user_action ("
        " user_action_id, gate_id, submission_id, intent_text, status,"
        " created_at, updated_at, state_version"
        ") VALUES ('g-a', 'g', 'sub-1', 'intent', 'ANSWERED', ?, ?, 1)",
        (NOW, NOW),
    )
    conn.execute(
        "INSERT INTO world_event ("
        " event_id, world_id, kind, narration, effects, occurred_at,"
        " source, participants, run_id"
        ") VALUES ('e', 'w', 'action', 'n', '[]', ?, 'v3-action', '[]', NULL)",
        (NOW,),
    )
    conn.execute(
        "INSERT INTO segment_commit ("
        " commit_id, kind, scene_id, segment_seq, passage_id, action_id,"
        " actual_start_tick, actual_end_tick, event_id, is_last_segment,"
        " created_at, updated_at, state_version"
        ") VALUES ('ac:g:sub-1', 'ACTION_OUTCOME', 'w-ch01-s01', NULL, NULL,"
        " 'g-a', 0, 3, 'e', 0, ?, ?, 1)",
        (NOW, NOW),
    )
    # A third kind refuses; an ACTION_OUTCOME with a flipped scene
    # refuses; a SEGMENT carrying an action_id refuses.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE segment_commit SET kind = 'CHAPTER_SETTLEMENT'"
            " WHERE commit_id = 'ac:g:sub-1'"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE segment_commit SET is_last_segment = 1"
            " WHERE commit_id = 'ac:g:sub-1'"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO segment_commit ("
            " commit_id, kind, scene_id, segment_seq, passage_id, action_id,"
            " actual_start_tick, actual_end_tick, event_id, is_last_segment,"
            " created_at, updated_at, state_version"
            ") VALUES ('sg:x', 'SEGMENT', 'w-ch01-s01', 1, NULL, 'g-a',"
            " 0, 3, 'e', 0, ?, ?, 1)",
            (NOW, NOW),
        )


def test_the_chain_head_and_the_stamps_agree() -> None:
    """The migration self-pin: the shared constants and a fresh database
    end at V3-7's ``0037_actor_memory_chapter_settlement`` / ``37`` —
    behind it V3-6R's ``0036_action_replan``, V3-6's
    ``0035_user_gate_action``, V3-5R's ``0034_segment_terminality`` and
    the chain's own V3 tables behind those."""

    assert MIGRATION_IDS[-1] == "0037_actor_memory_chapter_settlement"
    assert SCHEMA_HEAD_FILE == "0037_actor_memory_chapter_settlement.sql"
    assert SCHEMA_HEAD_VERSION == "37"
    assert MIGRATION_IDS[-2] == "0036_action_replan"
    assert MIGRATION_IDS[-3] == "0035_user_gate_action"
    assert MIGRATION_IDS[-4] == "0034_segment_terminality"
    fresh = sqlite3.connect(":memory:")
    applied = apply_migrations(fresh)
    assert applied[-1] == "0037_actor_memory_chapter_settlement"
    assert applied[-2] == "0036_action_replan"
    assert applied[-3] == "0035_user_gate_action"
    assert applied[-4] == "0034_segment_terminality"
    assert applied[-5] == "0033_segment_commit"
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
    for table in ("user_gate", "user_action", "segment_commit", "action_replan"):
        assert table in tables, table


# ---------------------------------------------------------------------------
# 2. NCP-1
# ---------------------------------------------------------------------------


def test_ncp1_lands_the_gate_flip_and_the_actions_birth(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """One transaction: ``OPEN → ANSWERED`` and the ``ANSWERED`` action
    row (``f"{gate_id}-a"``, the eight terminal columns NULL), with the
    gate's ``opened_at_tick`` read inside the opening face's own
    transaction (the tick is not advanced)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    opened = _gate(conn)
    assert isinstance(opened, Ok)
    assert isinstance(opened.value, UserGateRecord)
    assert opened.value.gate_id == GATE
    assert opened.value.scene_id == SCENE
    assert opened.value.status is GateStatus.OPEN
    assert opened.value.opened_at_tick == 0
    assert opened.value.options == (
        "offer the repair job",
        "ask about the letter",
        "walk away",
    )
    assert opened.value.state_version == 1

    submitted = _submitted(conn)
    assert isinstance(submitted, Ok)
    assert isinstance(submitted.value, UserActionRecord)
    assert submitted.value.user_action_id == f"{GATE}-a"
    assert submitted.value.gate_id == GATE
    assert submitted.value.submission_id == "sub-1"
    assert submitted.value.intent_text == "I offer to help with the ledger."
    assert submitted.value.selected_option == "offer the repair job"
    assert submitted.value.status is ActionStatus.ANSWERED
    for field in (
        "interpretation",
        "outcome",
        "actual_action",
        "consequences",
        "state_effects",
        "participants",
        "replan_scope",
        "actual_tick",
    ):
        assert getattr(submitted.value, field) is None, field
    assert get_gate(conn, GATE).status is GateStatus.ANSWERED  # type: ignore[union-attr]
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 0


def test_ncp1_replays_are_shape_keyed(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The same submission rides back (zero write — even after the
    ruling); a different shape is a ``CONFLICT``; a second submission on
    a claimed gate is ``VALIDATION_FAILED``."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    first = _submitted(conn)
    assert isinstance(first, Ok)
    assert isinstance(_committed_action(conn, world_store, narrative), Ok)

    replayed = _submitted(conn, now="2026-10-12T03:00:00+00:00")
    assert isinstance(replayed, Ok)
    assert replayed.value.created_at == first.value.created_at  # zero write
    assert replayed.value.status is ActionStatus.COMMITTED

    conflicted = _submitted(conn, intent_text="I do something else.")
    assert isinstance(conflicted, Err)
    assert conflicted.error.code is DomainErrorCode.CONFLICT
    assert "different shape" in conflicted.error.message

    claimed = _submitted(conn, submission_id="sub-2", now=LATER)
    assert isinstance(claimed, Err)
    assert claimed.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "one submission" in claimed.error.message
    assert _row_counts(conn, ("user_action",)) == {"user_action": 1}


def test_ncp1_judges_the_option_and_the_scenes_status(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The option must be one of the gate's recorded ones (refused with
    both lists named), a dangling gate is ``NOT_FOUND``, a non-``ACTIVE``
    scene and a malformed payload refuse, and a second gate on a standing
    scene refuses — all before anything is written."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    dangling = _gate(conn, scene_id="world-town-ch01-s99")
    assert isinstance(dangling, Err)
    assert dangling.error.code is DomainErrorCode.NOT_FOUND

    # a second gate on the same scene refuses (one stop at a time)
    assert isinstance(_gate(conn), Ok)
    second = _gate(conn, gate_seq=2, now=LATER)
    assert isinstance(second, Err)
    assert second.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "standing gate" in second.error.message

    bad_option = _submitted(conn, selected_option="buy the shop")
    assert isinstance(bad_option, Err)
    assert bad_option.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "recorded options" in bad_option.error.message

    blank_intent = _submitted(conn, intent_text="   ")
    assert isinstance(blank_intent, Err)
    assert blank_intent.error.code is DomainErrorCode.VALIDATION_FAILED
    assert _row_counts(conn, ("user_action",)) == {"user_action": 0}

    # the opening face's own payload checks
    for bad in (0, -1, True):
        refused = _gate(conn, gate_seq=bad, now=LATER)
        assert isinstance(refused, Err)
        assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    too_few = open_gate(
        conn, scene_id=SCENE, gate_seq=4, options=("only one",), now=LATER
    )
    assert isinstance(too_few, Err)
    assert "two to four" in too_few.error.message
    # The upper bound too (the review's F3): five options are no gate —
    # the face judges both edges of the 2–4 window.
    too_many = open_gate(
        conn,
        scene_id=SCENE,
        gate_seq=4,
        options=("one", "two", "three", "four", "five"),
        now=LATER,
    )
    assert isinstance(too_many, Err)
    assert "two to four" in too_many.error.message


def test_open_gate_replays_and_conflicts(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The opening face's idempotency: the same ``gate_id`` with the same
    shape rides back (zero write, the stored ``opened_at_tick`` stands);
    a different shape is a ``CONFLICT``; a corrupted ``options_json``
    raises ``ValueError`` (the store family's corrupted-row posture)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _gate(conn)
    assert isinstance(first, Ok)
    replayed = _gate(conn, now="2026-10-12T08:00:00+00:00")
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value
    assert replayed.value.created_at == first.value.created_at

    conflicted = _gate(conn, options=("a different road", "stay"), now=LATER)
    assert isinstance(conflicted, Err)
    assert conflicted.error.code is DomainErrorCode.CONFLICT
    assert "does not rewrite" in conflicted.error.message

    conn.execute(
        "UPDATE user_gate SET options_json = 'not json' WHERE gate_id = ?",
        (GATE,),
    )
    conn.commit()
    with pytest.raises(ValueError, match="undecodable options_json"):
        get_gate(conn, GATE)


def test_a_gate_refuses_on_a_non_active_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Only an ``ACTIVE`` scene takes a gate: a ``PLANNED`` one (and a
    ``COMMITTED`` one, after the last segment) refuses
    ``VALIDATION_FAILED``."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    planned = _gate(conn)
    assert isinstance(planned, Err)
    assert planned.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "only an ACTIVE scene" in planned.error.message

    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    landed = _commit(
        conn, narrative, world_store, is_last_segment=True, now=LATER
    )
    assert isinstance(landed, Ok)
    assert landed.value.scene_committed is True
    committed = _gate(conn, scene_id=SCENE, now=LATER)
    assert isinstance(committed, Err)
    assert committed.error.code is DomainErrorCode.VALIDATION_FAILED


# ---------------------------------------------------------------------------
# 3. NCP-2
# ---------------------------------------------------------------------------


def test_ncp2_lands_the_whole_group(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The arm list, field for field: the eight terminal columns
    (``actual_tick`` = the post-advance end), the behaviour event, the
    state settlement, the tick, the ACTION_OUTCOME lineage row, the
    gate's flip — and the chapter arm when the chapter is still
    ``PLANNED``."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None and chapter.status is ChapterStatus.PLANNED
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    assert isinstance(
        begin_resolving(conn, gate_id=GATE, now=LATER), Ok
    )
    outcome = _committed_action(conn, world_store, narrative, duration_ticks=7)
    assert isinstance(outcome, Ok)
    assert outcome.value.user_action_id == f"{GATE}-a"
    assert outcome.value.commit_id == f"ac:{GATE}:sub-1"
    assert outcome.value.event_id == f"ac:{GATE}:sub-1:event"
    assert outcome.value.actual_start_tick == 0
    assert outcome.value.actual_end_tick == 7
    assert outcome.value.replan_scope is ReplanScope.NONE
    assert outcome.value.chapter_activated is True

    action = action_of(conn, GATE)
    assert action is not None
    assert action.status is ActionStatus.COMMITTED
    assert action.interpretation == "You mean to help rather than to buy."
    assert action.outcome == "Lia lets you hold the ledger; the ice thins."
    assert action.actual_action == "you carry the ledger to the counter"
    assert action.consequences == "the shop's silence opens one notch"
    assert action.state_effects == (
        StateEffect(key="trust:lia", statement="warmed by one notch"),
    )
    assert action.participants == ("pc-you", "actor-lia")
    assert action.replan_scope is ReplanScope.NONE
    assert action.actual_tick == 7
    assert action.state_version == 3  # birth → RESOLVING → COMMITTED

    event = _rows(
        conn,
        "SELECT world_id, kind, narration, effects, occurred_at, source,"
        " participants FROM world_event WHERE event_id = ?",
        (outcome.value.event_id,),
    )
    assert event == [
        (
            TOWN,
            "action",
            "Lia lets you hold the ledger; the ice thins.",
            '[{"key":"trust:lia","statement":"warmed by one notch"}]',
            LATER,
            "v3-action",
            '["pc-you","actor-lia"]',
        )
    ]
    facts = _rows(
        conn,
        "SELECT canonical_key, statement, status, source_event_id"
        " FROM world_state_fact",
    )
    assert facts == [
        ("trust:lia", "warmed by one notch", "CURRENT", outcome.value.event_id)
    ]
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 7

    lineage = _rows(
        conn,
        "SELECT commit_id, kind, scene_id, segment_seq, passage_id,"
        " action_id, actual_start_tick, actual_end_tick, event_id,"
        " is_last_segment FROM segment_commit WHERE commit_id = ?",
        (outcome.value.commit_id,),
    )
    assert lineage == [
        (
            f"ac:{GATE}:sub-1",
            "ACTION_OUTCOME",
            SCENE,
            None,
            None,
            f"{GATE}-a",
            0,
            7,
            outcome.value.event_id,
            0,
        )
    ]
    time_of = story_time_of(conn, outcome.value.event_id)
    assert time_of == Ok((0, 7))
    assert get_gate(conn, GATE).status is GateStatus.COMMITTED  # type: ignore[union-attr]
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.status is ChapterStatus.ACTIVE
    assert chapter.opened_at_tick == 0

    # The scene's span IS the action's V3-6R move (the two-caller span
    # arm with close_scene=False): the interval extends 0 → 7 and the
    # scene stays ACTIVE (the flip stays the last SEGMENT's).
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert scene.status is SceneStatus.ACTIVE
    assert (scene.actual_start_tick, scene.actual_end_tick) == (0, 7)
    assert scene.state_version == 3  # mint 1 → activation 2 → span 3


def test_ncp2_refuses_a_ruling_without_the_user_role(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The participants discipline: a world without a user role refuses,
    a ruling missing the user, a foreign identity, a negative duration,
    a non-Adjudication, a bad ``replan_scope`` and a doubled effect key —
    each ``VALIDATION_FAILED`` with nothing written."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)

    missing_user = _committed_action(
        conn, world_store, narrative, adjudication=_ruling(participants=("actor-lia",))
    )
    assert isinstance(missing_user, Err)
    assert missing_user.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "user role" in missing_user.error.message

    foreign = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(participants=("persona-lia", "pc-you")),
    )
    assert isinstance(foreign, Err)
    assert foreign.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "canonical participant identity" in foreign.error.message

    negative = _committed_action(conn, world_store, narrative, duration_ticks=-1)
    assert isinstance(negative, Err)
    assert negative.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "never moves backwards" in negative.error.message

    not_a_ruling = commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id="sub-1",
        adjudication={"interpretation": "no"},  # type: ignore[arg-type]
        duration_ticks=1,
        now=LATER,
    )
    assert isinstance(not_a_ruling, Err)
    assert not_a_ruling.error.code is DomainErrorCode.VALIDATION_FAILED

    bad_scope = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope="LATER"),  # type: ignore[arg-type]
    )
    assert isinstance(bad_scope, Err)
    assert bad_scope.error.code is DomainErrorCode.VALIDATION_FAILED

    doubled = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(
            state_effects=(
                StateEffect(key="k", statement="one"),
                StateEffect(key="k", statement="two"),
            )
        ),
    )
    assert isinstance(doubled, Err)
    assert doubled.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "twice" in doubled.error.message

    no_submission = _committed_action(
        conn, world_store, narrative, submission_id="sub-9"
    )
    assert isinstance(no_submission, Err)
    assert no_submission.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "stored submission" in no_submission.error.message

    dangling_gate = _committed_action(
        conn, world_store, narrative, gate_id="world-town-ch01-s01-g99"
    )
    assert isinstance(dangling_gate, Err)
    assert dangling_gate.error.code is DomainErrorCode.NOT_FOUND

    assert _row_counts(
        conn,
        (
            "world_event",
            "world_state_fact",
            "segment_commit",
            "user_action",
        ),
    ) == {
        "world_event": 0,
        "world_state_fact": 0,
        "segment_commit": 0,
        "user_action": 1,
    }
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 0
    action = action_of(conn, GATE)
    # The V3-6R door: the pair sits at the resolver's durable stop — the
    # refusals prove the payload checks, never a COMMITTED write.
    assert action is not None and action.status is ActionStatus.RESOLVING
    assert get_gate(conn, GATE).status is GateStatus.RESOLVING  # type: ignore[union-attr]


def test_ncp2_refuses_a_world_without_a_user_role(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The honest no-player arm: with the ``world_player_character`` row
    gone, no ruling can carry the user, and the commit refuses naming the
    missing role (nothing written)."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    # Re-open a gate and submit, then remove the world's user role. The
    # V3-6R one-gate law: the first gate closes by a continuing segment
    # carrying its action before the next gate opens.
    unclosed = _gate(conn, gate_seq=2, now=LATER)
    assert isinstance(unclosed, Err)
    assert unclosed.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "close the previous gate" in unclosed.error.message
    resumed = _commit(
        conn, narrative, world_store, now=LATER, outcome_ref=f"{GATE}-a"
    )
    assert isinstance(resumed, Ok)
    assert get_gate(conn, GATE).status is GateStatus.CLOSED  # type: ignore[union-attr]
    assert isinstance(_gate(conn, gate_seq=2, now=LATER), Ok)
    assert isinstance(
        _submitted(conn, gate_id=f"{SCENE}-g02", submission_id="sub-2", now=LATER),
        Ok,
    )
    conn.execute("DELETE FROM world_player_character WHERE world_id = ?", (TOWN,))
    conn.commit()  # close the implicit transaction the DML opened
    refused = _committed_action(
        conn,
        world_store,
        narrative,
        gate_id=f"{SCENE}-g02",
        submission_id="sub-2",
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "declares no user role" in refused.error.message


def test_ncp2_replay_answers_the_stored_outcome(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The replay law: shape-equal rides back as a whole-group no-op (no
    second event, no tick re-advance, no second lineage row), shape-
    different is a ``CONFLICT``."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _committed_action(conn, world_store, narrative)
    assert isinstance(first, Ok)
    replayed = _committed_action(
        conn, world_store, narrative, now="2026-10-12T04:00:00+00:00"
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value
    assert _row_counts(
        conn, ("world_event", "segment_commit", "world_state_fact")
    ) == {
        "world_event": 1,
        "segment_commit": 1,
        "world_state_fact": 1,
    }
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 7

    conflicted = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(outcome="a different ending"),
    )
    assert isinstance(conflicted, Err)
    assert conflicted.error.code is DomainErrorCode.CONFLICT
    assert "does not rewrite" in conflicted.error.message
    # The chapter's replay answer is a read-time derivation (V3-5R's
    # twin-field posture, registered).
    assert replayed.value.chapter_activated is True


def test_ncp2_rolls_the_whole_group_back_on_a_deep_failure(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N-R-INV-004 at the deepest point: with the state settlement
    injected to fail mid-transaction, the action's terminal columns, the
    event, the state fact, the tick, the lineage row and the gate's flip
    are all untouched — the group is one transaction."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise sqlite3.OperationalError("injected failure")

    import elc.world.action as action_module

    monkeypatch.setattr(action_module, "_settle_effects_in_transaction", _explode)
    refused = _committed_action(conn, world_store, narrative)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert "injected failure" in refused.error.message

    action = action_of(conn, GATE)
    assert action is not None
    assert action.status is ActionStatus.RESOLVING
    assert action.outcome is None
    assert get_gate(conn, GATE).status is GateStatus.RESOLVING  # type: ignore[union-attr]
    assert _row_counts(
        conn, ("world_event", "world_state_fact", "segment_commit")
    ) == {"world_event": 0, "world_state_fact": 0, "segment_commit": 0}
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == 0
    # The span arm ④b is inside the group too: the injected failure
    # leaves the scene's actual interval untouched.
    scene = narrative.get_scene(SCENE)
    assert scene is not None
    assert (scene.actual_start_tick, scene.actual_end_tick) == (None, None)
    assert scene.state_version == 2  # mint 1 → activation 2; the arm rolled back

    monkeypatch.undo()
    retried = _committed_action(conn, world_store, narrative)
    assert isinstance(retried, Ok)
    assert retried.value.actual_start_tick == 0


def test_ncp1_rolls_the_whole_group_back_on_a_deep_failure(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N-R-INV-004 at NCP-1's deepest point (the review's F1): with the
    row read injected to fail after both writes, the gate stays ``OPEN``
    and no action row survives — the flip and the birth are one
    transaction, and the retry lands cleanly."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise sqlite3.OperationalError("injected failure")

    import elc.world.action as action_module

    monkeypatch.setattr(action_module, "_action_row", _explode)
    refused = _submitted(conn)
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert "injected failure" in refused.error.message

    monkeypatch.undo()
    gate = get_gate(conn, GATE)
    assert gate is not None and gate.status is GateStatus.OPEN
    assert action_of(conn, GATE) is None
    assert _row_counts(conn, ("user_action",)) == {"user_action": 0}
    landed = _submitted(conn)
    assert isinstance(landed, Ok)
    assert landed.value.status is ActionStatus.ANSWERED


def test_a_first_action_opens_the_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The #3 chapter arm: with no segment yet, the first ruling opens
    the chapter (``opened_at_tick`` = the transaction's own pre-advance
    read)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    # push the world's tick forward first, to prove the stamp is the
    # transaction's own read (not zero).
    conn.execute("UPDATE world SET current_tick = 11 WHERE world_id = ?", (TOWN,))
    conn.commit()  # close the implicit transaction the DML opened
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    outcome = _committed_action(conn, world_store, narrative, duration_ticks=4)
    assert isinstance(outcome, Ok)
    assert outcome.value.replan_scope is ReplanScope.NONE
    assert outcome.value.actual_start_tick == 11
    assert outcome.value.actual_end_tick == 15
    assert outcome.value.chapter_activated is True
    chapter = narrative.get_chapter("world-town-ch01")
    assert chapter is not None
    assert chapter.status is ChapterStatus.ACTIVE
    assert chapter.opened_at_tick == 11


# ---------------------------------------------------------------------------
# 4. begin_resolving
# ---------------------------------------------------------------------------


def test_begin_resolving_moves_both_rows_and_is_idempotent(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """``ANSWERED → RESOLVING`` on both rows in one transaction; a
    re-call rides back unchanged; ``OPEN`` (nothing submitted) and the
    terminal words refuse; a dangling gate is ``NOT_FOUND``."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)

    open_arm = begin_resolving(conn, gate_id=GATE, now=LATER)
    assert isinstance(open_arm, Err)
    assert open_arm.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "nothing has been submitted" in open_arm.error.message

    dangling = begin_resolving(conn, gate_id="no-such-gate", now=LATER)
    assert isinstance(dangling, Err)
    assert dangling.error.code is DomainErrorCode.NOT_FOUND

    assert isinstance(_submitted(conn), Ok)
    moved = begin_resolving(conn, gate_id=GATE, now=LATER)
    assert isinstance(moved, Ok)
    gate, action = moved.value
    assert gate.status is GateStatus.RESOLVING
    assert action.status is ActionStatus.RESOLVING
    assert gate.state_version == 3
    assert action.state_version == 2

    again = begin_resolving(conn, gate_id=GATE, now="2026-10-12T05:00:00+00:00")
    assert isinstance(again, Ok)
    assert again.value == moved.value  # zero write

    assert isinstance(_committed_action(conn, world_store, narrative), Ok)
    past = begin_resolving(conn, gate_id=GATE, now=LATER)
    assert isinstance(past, Err)
    assert past.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "does not step back" in past.error.message


# ---------------------------------------------------------------------------
# 5. the adjudication's sole writership (intent ≠ world fact)
# ---------------------------------------------------------------------------


def test_the_submissions_words_never_reach_canon(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """DOMAIN §20.3-1's physical form: the intent text and the selected
    option are durable on the ``user_action`` row and appear in **no**
    ``world_event`` / ``world_state_fact`` column — the ruling's own
    words are what the chronicle carries."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    intent = "I draw the blade and strike the guard."
    option = "walk away"
    assert isinstance(
        _submitted(conn, intent_text=intent, selected_option=option), Ok
    )
    landed = _committed_action(conn, world_store, narrative)
    assert isinstance(landed, Ok)

    for table, columns in (
        (
            "world_event",
            (
                "event_id",
                "world_id",
                "kind",
                "narration",
                "effects",
                "occurred_at",
                "source",
                "participants",
                "run_id",
            ),
        ),
        (
            "world_state_fact",
            (
                "fact_id",
                "world_id",
                "source_event_id",
                "canonical_key",
                "statement",
                "status",
                "recorded_at",
            ),
        ),
    ):
        for column in columns:
            needle = _rows(
                conn,
                f"SELECT COUNT(*) FROM {table}"
                f" WHERE CAST({column} AS TEXT) LIKE ?",
                ("%draw the blade%",),
            )[0][0]
            assert needle == 0, (table, column)
    row = _rows(
        conn,
        "SELECT COUNT(*) FROM world_event WHERE narration = ?",
        ("Lia lets you hold the ledger; the ice thins.",),
    )
    assert row[0][0] == 1


def test_the_module_writes_the_event_only_from_the_ruling() -> None:
    """The structural half: ``commit_action``'s body names
    ``intent_text`` / ``selected_option`` only in the submission's own
    faces — the event and settlement arms read the adjudication."""

    def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        raise AssertionError(f"function {name!r} not found")

    body = _function(ACTION_TREE, "_commit_action_tx")
    literals = [
        node.value
        for node in ast.walk(body)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    for text in literals:
        assert "intent_text" not in text or "UPDATE user_action" in text, text
        assert "selected_option" not in text, text
        source_sql = [
            text
            for text in literals
            if text.lstrip().upper().startswith("INSERT INTO WORLD_EVENT")
        ]
    assert len(source_sql) == 1
    assert "v3-action" in source_sql[0]
    assert "'action'" in source_sql[0]


# ---------------------------------------------------------------------------
# 6. the replan verdicts
# ---------------------------------------------------------------------------


def test_a_none_ruling_moves_no_plan_row(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """``replan_scope = NONE``: the ruling lands and the plan face keeps
    its revision count — one dossier, one adopted plan, untouched, and
    **zero obligations** (V3-6R: "no obligation" is zero rows)."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert [d.dossier_revision for d in narrative.dossiers_of(SCENE)] == [1]
    assert len(narrative.plans_of("world-town-ch01")) == 1
    assert _row_counts(conn, ("action_replan",)) == {"action_replan": 0}
    assert pending_replans(conn) == ()


def test_a_scene_ruling_replans_the_dossier_and_the_writer_reads_it(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    writer: PovWriter,
) -> None:
    """``replan_scope = SCENE``: NCP-2 births the obligation ``PENDING``,
    and ``replan_scene(replan_request_id, …)`` consumes it through
    ``claim → work → complete`` — ``max + 1`` minted, created and adopted
    (the old revision superseded), the scene's status kept, the
    ``max(current_tick, element)`` time law read — and the next segment's
    Writer reads the new dossier (the new ``must_hide`` is the one that
    leaks; the resuming segment carries the ruling's ``outcome_ref`` and
    closes the gate)."""

    _chain(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    request_id = replan_request_id_for(GATE, "sub-1")
    born = replan_obligation(conn, request_id)
    assert born is not None
    assert born.user_action_id == f"{GATE}-a"
    assert born.scope is ReplanScope.SCENE
    assert born.status is ReplanStatus.PENDING
    assert born.target_ref is None

    element = _scene_draft(purpose="the ledger turns", must_hide="the iron key")
    replanned = planner.replan_scene(request_id, element, LATER)
    assert isinstance(replanned, Ok)
    assert replanned.value.dossier_id == f"{SCENE}-d2"
    assert replanned.value.dossier_revision == 2
    assert replanned.value.status is PlanRevisionStatus.ADOPTED
    assert replanned.value.must_hide == "the iron key"
    assert replanned.value.planned_start_tick == 7  # max(current, 0)
    dossiers = narrative.dossiers_of(SCENE)
    assert [(d.dossier_revision, d.status) for d in dossiers] == [
        (1, PlanRevisionStatus.SUPERSEDED),
        (2, PlanRevisionStatus.ADOPTED),
    ]
    scene = narrative.get_scene(SCENE)
    assert scene is not None and scene.status is SceneStatus.ACTIVE
    applied = replan_obligation(conn, request_id)
    assert applied is not None
    assert applied.status is ReplanStatus.APPLIED
    assert applied.target_ref == f"{SCENE}-d2"

    leaked = writer.write_segment(
        SCENE,
        body="She keeps the iron key under the counter.",
        language="en",
        segment_seq=1,
        duration_ticks=1,
        is_last_segment=False,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(leaked, Err)
    assert leaked.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "iron key" in leaked.error.message
    allowed = writer.write_segment(
        SCENE,
        body="She sets the priced tools down between you.",
        language="en",
        segment_seq=1,
        duration_ticks=1,
        is_last_segment=False,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(allowed, Ok)
    assert get_gate(conn, GATE).status is GateStatus.CLOSED  # type: ignore[union-attr]


def test_the_scene_replan_face_refuses_by_its_own_obligation(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-6R entry: a missing obligation is ``NOT_FOUND``; a
    corrupted element refuses in the family's own coordinate language
    **before the claim** (no dossier, no target written); 「只重规划剩余
    部分」 refuses a settled scene the obligation names."""

    _opened_chapter(
        conn, world_store, cast_store, bible_store, narrative, director
    )
    missing = planner.replan_scene(f"rp:{SCENE}-g99:sub-0", _scene_draft(), LATER)
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND
    assert narrative.dossiers_of(SCENE) == ()

    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    landed = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.SCENE),
    )
    assert isinstance(landed, Ok)
    request_id = replan_request_id_for(GATE, "sub-1")

    broken = _scene_draft()
    broken["planned_start_tick"] = "soon"
    corrupted = planner.replan_scene(request_id, broken, LATER)
    assert isinstance(corrupted, Err)
    assert corrupted.error.code is DomainErrorCode.VALIDATION_FAILED
    assert f"scene {SCENE!r}.planned_start_tick" in corrupted.error.message
    assert [d.dossier_revision for d in narrative.dossiers_of(SCENE)] == [1]
    unclaimed = replan_obligation(conn, request_id)
    assert unclaimed is not None
    assert unclaimed.status is ReplanStatus.PENDING
    assert unclaimed.target_ref is None

    # A settled scene is past this door too (the last segment flipped
    # it): the obligation stands PENDING, the replanning refuses.
    landed_segment = _commit(
        conn,
        narrative,
        world_store,
        is_last_segment=True,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(landed_segment, Ok)
    assert landed_segment.value.scene_committed is True
    settled = planner.replan_scene(request_id, _scene_draft(), LATER)
    assert isinstance(settled, Err)
    assert settled.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "remaining part" in settled.error.message
    assert [d.dossier_revision for d in narrative.dossiers_of(SCENE)] == [1]


def test_a_chapter_ruling_lands_through_apply_action_replan(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """``replan_scope = CHAPTER``: the obligation is consumed by
    ``Director.apply_action_replan`` (the V3-6R entry — a bare chapter id
    no longer serves) — a new revision adopted, the obligation discharged
    ``APPLIED`` with its claimed target, and the next scene's open reads
    the newest adopted revision's element (no rounding back to the
    invalidated plan)."""

    scenes = [
        _scene_draft(purpose="first sight"),
        _scene_draft(purpose="the ledger", place="the counter"),
    ]
    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        scenes=scenes,
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    revised_payload = _blueprint(
        scenes=[
            _scene_draft(purpose="first sight"),
            dict(_scene_draft(purpose="the ledger", place="the counter"),
                 **{"scene_ref": 2}),
        ]
    )
    revised_payload["scenes"][1]["place"] = "the flooded mill floor"
    landed = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    assert isinstance(landed, Ok)
    assert landed.value.replan_scope is ReplanScope.CHAPTER

    request_id = replan_request_id_for(GATE, "sub-1")
    revised = director.apply_action_replan(request_id, revised_payload, LATER)
    assert isinstance(revised, Ok)
    assert revised.value.plan.plan_revision == 2
    assert revised.value.plan.status is PlanRevisionStatus.ADOPTED
    applied = replan_obligation(conn, request_id)
    assert applied is not None
    assert applied.status is ReplanStatus.APPLIED
    assert applied.target_ref == "world-town-ch01-bp-r2"

    opened = planner.open_scene(SCENE2, LATER)
    assert isinstance(opened, Ok)
    assert opened.value.dossier.place == "the flooded mill floor"
    assert opened.value.dossier.planned_start_tick == 7


def test_the_ruling_scope_is_persisted_and_its_replay_is_a_no_op(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The persisted ``replan_scope`` (the review's F2): the terminal
    column carries the adjudicated word — read back through ``action_of``
    — and the same-shape replay answers the stored outcome instead of
    re-landing the group (no second event, no second tick advance)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    landed = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    assert isinstance(landed, Ok)
    action = action_of(conn, GATE)
    assert action is not None
    assert action.status is ActionStatus.COMMITTED
    assert action.replan_scope is ReplanScope.CHAPTER
    request_id = replan_request_id_for(GATE, "sub-1")
    born = replan_obligation(conn, request_id)
    assert born is not None and born.status is ReplanStatus.PENDING
    events_before = _rows(conn, "SELECT COUNT(*) FROM world_event")[0][0]
    tick_before = _rows(conn, "SELECT current_tick FROM world")[0][0]
    replayed = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    assert isinstance(replayed, Ok)
    assert replayed.value == landed.value
    assert _rows(conn, "SELECT COUNT(*) FROM world_event")[0][0] == events_before
    assert _rows(conn, "SELECT current_tick FROM world")[0][0] == tick_before
    still = action_of(conn, GATE)
    assert still is not None and still.replan_scope is ReplanScope.CHAPTER
    # The replay touches the obligation never (the replay arm answers
    # first): exactly one PENDING row, no second birth.
    assert _row_counts(conn, ("action_replan",)) == {"action_replan": 1}
    after_replay = replan_obligation(conn, request_id)
    assert after_replay == born


# ---------------------------------------------------------------------------
# 7. the interlock
# ---------------------------------------------------------------------------


def test_a_standing_gate_stops_the_story_and_a_replay_still_answers(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """STATE §22/§23's physical form: a fresh segment on a scene with a
    non-terminal gate refuses ``VALIDATION_FAILED`` naming the gate — and
    the stored segment's own replay still rides back (the replay arm
    answers first, touching nothing)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    first = _commit(conn, narrative, world_store)
    assert isinstance(first, Ok)
    assert isinstance(_gate(conn), Ok)

    stopped = _commit(conn, narrative, world_store, segment_seq=2, now=LATER)
    assert isinstance(stopped, Err)
    assert stopped.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "User Gate" in stopped.error.message
    assert get_gate(conn, GATE).status is GateStatus.OPEN  # type: ignore[union-attr]

    replayed = _commit(conn, narrative, world_store, now="2026-10-12T06:00:00+00:00")
    assert isinstance(replayed, Ok)
    assert replayed.value == first.value
    assert get_gate(conn, GATE).status is GateStatus.OPEN  # type: ignore[union-attr]
    assert _rows(conn, "SELECT MIN(opened_at_tick) FROM user_gate")[0][0] == 3


def test_the_resume_closes_committed_gates_atomically(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-6R ``COMMITTED → CLOSED`` move is the resuming segment's
    own transaction, **targeted by the ``outcome_ref``**: the forced law
    refuses a fresh segment that does not carry the standing gate's
    action, and the segment that does carry it closes that gate (version
    bumped) — a segment that fails along the way leaves the gate
    ``COMMITTED``, never half-moved."""

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert get_gate(conn, GATE).status is GateStatus.COMMITTED  # type: ignore[union-attr]

    # The forced law: no reference, no fresh segment.
    missing_ref = _commit(conn, narrative, world_store, now=LATER)
    assert isinstance(missing_ref, Err)
    assert missing_ref.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "outcome_ref" in missing_ref.error.message
    assert get_gate(conn, GATE).status is GateStatus.COMMITTED  # type: ignore[union-attr]

    # A failing fresh segment (a skipped sequence) leaves the gate alone.
    failed = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=5,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(failed, Err)
    assert get_gate(conn, GATE).status is GateStatus.COMMITTED  # type: ignore[union-attr]

    landed = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=1,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(landed, Ok)
    closed = get_gate(conn, GATE)
    assert closed is not None
    assert closed.status is GateStatus.CLOSED
    assert closed.state_version == 5
    assert [g.status for g in gates_of(conn, SCENE)] == [GateStatus.CLOSED]
    passage = _rows(
        conn,
        "SELECT outcome_ref FROM narrative_passage WHERE scene_id = ?",
        (SCENE,),
    )
    assert passage == [(f"{GATE}-a",)]


def test_the_writer_respects_the_gate_interlock(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    writer: PovWriter,
) -> None:
    """The interlock through the Writer's own path: a clean segment with
    a standing gate is refused at the settlement (the Writer's guards pass
    and the commit refuses) — the stop is the canon's, not the prose
    guard's lying."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    refused = writer.write_segment(
        SCENE,
        body="She sets the ledger down between you.",
        language="en",
        segment_seq=1,
        duration_ticks=1,
        is_last_segment=False,
        now=LATER,
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "User Gate" in refused.error.message
    assert _row_counts(conn, ("narrative_passage", "segment_commit")) == {
        "narrative_passage": 0,
        "segment_commit": 0,
    }


def test_the_write_faces_do_not_bypass_a_held_lock(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
    tmp_path: Path,
) -> None:
    """The behaviour half of "one short transaction": while another
    connection holds the write transaction, ``commit_action`` refuses
    ``DEPENDENCY_UNAVAILABLE`` (the database's own busy answer — the
    face's one ``BEGIN IMMEDIATE`` is the whole move); after the lock
    releases the same call goes through."""

    _active_scene(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    # The V3-6R door: step into the durable stop first — the lock probe
    # is about the one BEGIN IMMEDIATE, not about the door.
    assert isinstance(begin_resolving(conn, gate_id=GATE, now=LATER), Ok)
    conn_b = sqlite3.connect(tmp_path / "app.db")
    try:
        conn_b.execute("PRAGMA foreign_keys=ON")
        conn_b.execute("PRAGMA busy_timeout = 50")
        epoch_now = open_runtime_epoch(conn_b)
        store_b = SqliteWorldStore(conn_b, epoch_now)
        narrative_b = SqliteNarrativeStore(conn_b, epoch_now)
        conn.execute("BEGIN IMMEDIATE")  # the first writer holds the lock
        try:
            refused = commit_action(
                conn_b,
                world_store=store_b,
                narrative_store=narrative_b,
                gate_id=GATE,
                submission_id="sub-1",
                adjudication=_ruling(),
                duration_ticks=7,
                now=LATER,
            )
        finally:
            conn.execute("ROLLBACK")
        assert isinstance(refused, Err)
        assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
        assert "locked" in refused.error.message

        retried = commit_action(
            conn_b,
            world_store=store_b,
            narrative_store=narrative_b,
            gate_id=GATE,
            submission_id="sub-1",
            adjudication=_ruling(),
            duration_ticks=7,
            now=LATER,
        )
        assert isinstance(retried, Ok)
        assert retried.value.actual_end_tick == 7
    finally:
        conn_b.close()


# ---------------------------------------------------------------------------
# 8. the recovery scan, the module discipline, the chain head
# ---------------------------------------------------------------------------


def test_recovery_scan_reads_the_five_families(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """RA §29: gates ``ANSWERED`` / ``RESOLVING``, actions
    ``RESOLVING``, scenes ``ACTIVE``, chapters ``ACTIVE`` / ``SETTLING``
    and — since V3-6R — replan obligations ``PENDING`` — each
    deterministically ordered; and the NCP-1 aftermath's unique
    outcome: re-adjudicating the same submission lands exactly one
    COMMITTED word. (This walk's rulings are all ``NONE`` — zero
    obligations; the PENDING family's own pin lives in the V3-6R
    suite.)"""

    scenes = [
        _scene_draft(purpose="first sight"),
        _scene_draft(purpose="the ledger"),
    ]
    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        director,
        planner,
        scenes=scenes,
    )
    assert isinstance(planner.open_scene(SCENE2, NOW), Ok)
    first = _commit(conn, narrative, world_store)
    assert isinstance(first, Ok)

    # scene 1: a submitted gate (ANSWERED); scene 2: a resolving one.
    assert isinstance(_gate(conn), Ok)
    assert isinstance(_submitted(conn), Ok)
    assert isinstance(_gate(conn, scene_id=SCENE2), Ok)
    assert isinstance(
        _submitted(conn, gate_id=f"{SCENE2}-g01", submission_id="sub-2"), Ok
    )
    assert isinstance(begin_resolving(conn, gate_id=f"{SCENE2}-g01", now=LATER), Ok)

    scan = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(scan, Ok)
    assert [g.gate_id for g in scan.value.gates] == [
        f"{SCENE}-g01",
        f"{SCENE2}-g01",
    ]
    assert [g.status for g in scan.value.gates] == [
        GateStatus.ANSWERED,
        GateStatus.RESOLVING,
    ]
    assert [a.user_action_id for a in scan.value.actions] == [f"{SCENE2}-g01-a"]
    assert [a.status for a in scan.value.actions] == [ActionStatus.RESOLVING]
    assert [s.scene_id for s in scan.value.scenes] == [SCENE, SCENE2]
    assert [(c.world_id, c.chapter_index) for c in scan.value.chapters] == [
        (TOWN, 1)
    ]
    assert [c.status for c in scan.value.chapters] == [ChapterStatus.ACTIVE]
    assert scan.value.replans == ()
    assert pending_replans(conn) == ()

    # the crash window: NCP-1 landed, the adjudication did not — the
    # retry adjudicates the same submission and the outcome is unique.
    retried = _committed_action(conn, world_store, narrative)
    assert isinstance(retried, Ok)
    again = _committed_action(
        conn, world_store, narrative, now="2026-10-12T07:00:00+00:00"
    )
    assert isinstance(again, Ok)
    # two lineage rows (the segment and the action) and two events, and
    # exactly one ACTION_OUTCOME row for the one submitted key.
    assert _row_counts(conn, ("segment_commit", "world_event")) == {
        "segment_commit": 2,
        "world_event": 2,
    }
    assert _rows(
        conn,
        "SELECT COUNT(*) FROM segment_commit WHERE kind = 'ACTION_OUTCOME'",
    )[0][0] == 1
    assert _rows(
        conn, "SELECT COUNT(*) FROM world_event WHERE kind = 'action'"
    )[0][0] == 1
    assert get_gate(conn, GATE).status is GateStatus.COMMITTED  # type: ignore[union-attr]
    after = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(after, Ok)
    assert [g.gate_id for g in after.value.gates] == [f"{SCENE2}-g01"]


def test_the_cognition_view_sees_the_action_outcome(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The V3-5R read face's own linkage (DATA §26.2.1's note): the
    cognition view's lineage JOIN is kind-agnostic, so an
    ACTION_OUTCOME event is visible — and its participants obey the
    canonical layers (a viewer among them witnesses the ruling)."""

    from elc.world.cognition import v3_cognition_view

    _chain(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    view = v3_cognition_view(conn, world_id=TOWN, viewer_id="actor-lia")
    assert isinstance(view, Ok)
    assert view.value.public == ()
    assert [event.kind for event in view.value.witnessed] == ["action"]
    assert view.value.witnessed[0].narration == (
        "Lia lets you hold the ledger; the ice thins."
    )
    assert view.value.witnessed[0].actual_start_tick == 0
    assert view.value.witnessed[0].actual_end_tick == 7


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


def test_every_write_face_is_one_transaction() -> None:
    """N-R-INV-004: each public write face opens exactly one
    ``BEGIN IMMEDIATE`` and lands exactly one ``COMMIT``; its in-
    transaction body carries **no transaction-control constant at all**
    (the owner/arm split the settlement spells)."""

    for name in ("open_gate", "submit_gate", "begin_resolving", "commit_action"):
        public = _function(ACTION_TREE, name)
        constants = _all_constants(public)
        assert constants.count("BEGIN IMMEDIATE") == 1, name
        assert constants.count("COMMIT") == 1, name
    for name in (
        "_open_gate_tx",
        "_submit_gate_tx",
        "_begin_resolving_tx",
        "_commit_action_tx",
    ):
        body = _function(ACTION_TREE, name)
        assert _sql_constants(body), (name, "the body carries no SQL")
        for text in _all_constants(body):
            assert text != "BEGIN IMMEDIATE", (name, text)
            assert text != "COMMIT", (name, text)
            assert text != "ROLLBACK", (name, text)
    # The method-call spelling is the review's F1 blind spot
    # (``conn.commit()`` splits the group without touching a constant):
    # transaction control must ride the literal ``execute("…")``
    # spelling, so no attribute call may be named commit / rollback.
    for node in ast.walk(ACTION_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"commit", "rollback"}, node.func.attr


def test_the_module_builds_no_sql_and_reads_no_package() -> None:
    """The scans: no Package import (the durable rows are the runtime
    authority), no interpolated SQL (fixed literals and parameter
    binding only), and the recovery read carries no transaction control
    of its own."""

    for node in ast.walk(ACTION_TREE):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("elc.world.package"), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("elc.world.package"), (
                node.module
            )
    for text in _sql_constants(ACTION_TREE):
        assert "{" not in text, text
        assert "}" not in text, text
    scan = _function(ACTION_TREE, "recovery_scan")
    for text in _all_constants(scan):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text


def test_the_interlock_arms_are_the_commits_own() -> None:
    """The interlock's two arms ride the SEGMENT COMMIT's own body
    (``_commit_segment_tx``): the stop query and the closing UPDATE are
    inside it, and neither the public face nor its body names a nested
    transaction — the arms are the settlement's own SQL, no second
    face."""

    body = _function(SETTLEMENT_TREE, "_commit_segment_tx")
    literals = _all_constants(body)
    assert any(
        "FROM user_gate" in text and "ANSWERED" in text for text in literals
    )
    assert any(
        text.lstrip().upper().startswith("UPDATE USER_GATE")
        and "CLOSED" in text
        for text in literals
    )
    for text in literals:
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text


def test_the_module_imports_from_a_cold_interpreter() -> None:
    """The cold-start pin (the P4-3 discipline)."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    for module in ("elc.world.action",):
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, (module, proc.stderr)


def test_the_promoted_namespace_face_is_the_one_truth() -> None:
    """The settlement's promoted face: ``participant_namespace_of`` is
    public and the action module calls it (one recipe, two callers), and
    the internal name is gone."""

    from elc.world import settlement

    assert "participant_namespace_of" in settlement.__all__
    assert "player_character_id_of" in settlement.__all__
    source = (SRC_ROOT / "world" / "settlement.py").read_text(encoding="utf-8")
    assert "_participant_namespace(" not in source
    action_source = (SRC_ROOT / "world" / "action.py").read_text(
        encoding="utf-8"
    )
    assert "participant_namespace_of" in action_source
    assert "player_character_id_of" in action_source


def test_the_chapter_arm_is_the_stores_own() -> None:
    """NCP-2's chapter arm is the narrative store's
    ``_flip_chapter_activated_tx`` — the same move and prerequisites
    NCP-3 keeps, never a second spelling; the action module carries no
    chapter-flip SQL of its own."""

    body = _function(ACTION_TREE, "_commit_action_tx")
    called = {
        node.attr for node in ast.walk(body) if isinstance(node, ast.Attribute)
    }
    assert "_flip_chapter_activated_tx" in called
    literals = _all_constants(body)
    for text in literals:
        assert not text.lstrip().upper().startswith("UPDATE world_chapter"), text
    arm = _function(NARRATIVE_STORE_TREE, "_flip_chapter_activated_tx")
    assert _sql_constants(arm)
    for text in _all_constants(arm):
        assert text != "BEGIN IMMEDIATE", text
        assert text != "COMMIT", text
        assert text != "ROLLBACK", text
