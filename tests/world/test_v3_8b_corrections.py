"""V3-8b — the scope-restricted correction cut (TASK-OPI-06b954e0…16 /
the opening ruling ``DEC-OPI-06b954e0-…15``; the external review's
3 HIGH + 1 HARD GATE + 1 MEDIUM-HIGH, on HEAD ``10b4489``; the contract
increments in STATE §21's 「SETTLING 前置律」 + §25's V3-8b 修订,
DOMAIN §20.2's rewritten authority rows, DATA §26.2.1's hooks clause,
RA §27's V3-8b 修订 block and REGISTER v1.7.2).

The groups, one per face:

1. **HIGH-1 — the SETTLING precondition gate** (STATE §21): the
   ``ACTIVE → SETTLING`` flip refuses ``VALIDATION_FAILED`` — zero
   state change, the chapter at the same ``state_version`` — while the
   chapter's world holds a running story: an ``ACTIVE`` scene, a gate
   short of ``CLOSED`` (``OPEN`` / ``ANSWERED`` / ``RESOLVING`` /
   ``COMMITTED``-unresumed), or a ``PENDING`` ``action_replan``
   obligation; a ``PLANNED`` scene does **not** block, and the flip
   lands once the story is closed. The check runs inside the flip's own
   transaction (the structural pin);
2. **HIGH-2 — the world-authoritative ``ResolverContext``**
   (:mod:`elc.world.providers`): the provider input carries the CURRENT
   Bible, the settled facts, the player's durable row and the scene's
   counterpart profiles beside the user's own submission — the intent
   comes from the durable row (never an invention), and the POV's
   cognition / memory ride for *what the player character knows*;
3. **HIGH-3 — the DirectorProvider** (RA §27's division re-freeze): the
   initial Chapter Blueprint and the CHAPTER replan are produced from
   the full ``DirectorContext`` plus the triggering ruling; the SCENE
   level stays the PlannerProvider's. The split is pinned **physically**
   — two distinct fake instances, each recording only its own arm;
4. **the HARD GATE — the continuation obligation**: ``recovery_scan``
   lists ``COMMITTED``-unclosed gates with no passage carrying their
   action, its ``next_segment_seq`` derives from the durable
   ``segment_commit`` rows, and ``resume`` drives the first
   continuation passage (the committed action as the forced
   ``outcome_ref``; the gate closes in that same commit) with nothing
   re-supplied from the caller's process memory;
5. **MEDIUM-HIGH — the settlement's hooks never upgrade from the
   Blueprint**: ``chapter_settlement.hooks`` is the honest empty string
   (``chapter_questions_to_advance`` does not become Narrative Memory),
   ``created_at_revision`` keeps the plan's provenance number only.

The migration of the affected V3-7 / V3-8a families rode this cut's
delivery (the ``_settling_chapter`` fixture commits its terminal
segment first; the CHAPTER-replan pins read the Director path; the
crashed-walk pins expect the continuation).
"""

from __future__ import annotations

import ast
import dataclasses
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.world.action import (
    ActionStatus,
    Adjudication,
    ContinuationObligation,
    GateStatus,
    ReplanScope,
    ReplanStatus,
    action_by_id,
    action_of,
    begin_resolving,
    commit_action,
    get_gate,
    open_gate,
    recovery_scan,
    replan_obligation,
    replan_request_id_for,
    submit_gate,
)
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.bootstrap import PlayerSeed, create_world_with_bible
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.director import Director
from elc.world.narrative import (
    ChapterStatus,
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.pipeline import GateBeat, Pipeline, SegmentBeat
from elc.world.providers import (
    DeterministicFakeProvider,
    DirectorProvider,
    PlannerProvider,
    ResolverContext,
    WriterProvider,
)
from elc.world.scene import ScenePlanner
from elc.world.settlement import commit_segment, settle_chapter
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import StateEffect
from tests.conftest import SRC_ROOT

REPO = Path(__file__).resolve().parents[2]

STORE_SOURCE = (
    SRC_ROOT / "world" / "narrative" / "store.py"
).read_text(encoding="utf-8")
STORE_TREE = ast.parse(STORE_SOURCE)
PIPELINE_SOURCE = (SRC_ROOT / "world" / "pipeline.py").read_text(
    encoding="utf-8"
)
SETTLEMENT_SOURCE = (SRC_ROOT / "world" / "settlement.py").read_text(
    encoding="utf-8"
)
SETTLEMENT_TREE = ast.parse(SETTLEMENT_SOURCE)

NOW = "2026-10-13T00:00:00+00:00"
LATER = "2026-10-13T01:00:00+00:00"
LATER2 = "2026-10-13T02:00:00+00:00"

TOWN = "world-town"
CH = "world-town-ch01"
SCENE = "world-town-ch01-s01"
SCENE2 = "world-town-ch01-s02"
GATE = "world-town-ch01-s01-g01"
ACTOR = "actor-lia"
PARTNER = "actor-bram"
PLAYER = "pc-you"

LIA_PRIVATE = "LIA_PRIVATE: she priced the tools herself"
HARD_RULE = "NO HARD RULE VIOLATED: steel is never drawn indoors"
QUESTION = "who is the letter from?"

# ---------------------------------------------------------------------------
# fixtures / helpers (the V3-7 / V3-8a suites' own shapes)
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


def _insert_card(conn: sqlite3.Connection, persona_id: str, name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO character_card ("
        " character_id, persona_id, name, identity, personality,"
        " background, speech_style, \"values\", boundaries, opening,"
        " scenario, generation_policy, lore_refs, revision, status,"
        " is_builtin, created_at, updated_at"
        ") VALUES (?, ?, ?, 'i', 'p', 'b', 's', 'v', 'bo', 'o',"
        " 'sc', 'auto', '', 1, 'active', 1, ?, ?)",
        (f"cpkg-{persona_id}", persona_id, name, NOW, NOW),
    )


def _create_town(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    *,
    hard_rules: str = HARD_RULE,
    player: PlayerSeed | None = None,
    player_private: str = LIA_PRIVATE,
):
    """The atomic creation service's own seed: two AI actors (the POV
    one carrying a private context) and the reader's character with a
    declared profile."""

    _insert_card(conn, "persona-lia", "Lia")
    _insert_card(conn, "persona-bram", "Bram")
    conn.commit()
    return create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=TOWN,
        name="Town",
        bible_revision_id=f"{TOWN}-bible-r1",
        bible=BibleContent(
            premise="the town by the water",
            hard_rules=hard_rules,
        ),
        actors=(
            _actor_seed(ACTOR, "persona-lia", player_private),
            _actor_seed(PARTNER, "persona-bram", "BRAM_PRIVATE"),
        ),
        player=(
            player
            if player is not None
            else PlayerSeed(
                player_character_id=PLAYER,
                name="You",
                background="a newcomer off the evening coach",
                abilities="steady hands",
                limits="no training with steel",
                location="the inn",
                state="tired",
            )
        ),
        now=NOW,
    )


def _actor_seed(actor_id: str, persona_id: str, private: str) -> Any:
    from elc.world.bootstrap import ActorSeed

    return ActorSeed(
        actor_id=actor_id,
        persona_id=persona_id,
        story_role=StoryRole.PROTAGONIST,
        pov_eligible=True,
        pov_weight=1,
        long_term_drive="keep the shop open a winter longer",
        private_context=private,
    )


def _scene_draft(
    *,
    pov: str = ACTOR,
    participants: tuple[str, ...] = (ACTOR, PLAYER),
    purpose: str = "first sight",
    must_hide: str = "the priced tools",
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
    }


def _blueprint(
    scenes: list[dict[str, Any]] | None = None,
    question: str = QUESTION,
) -> dict[str, Any]:
    if scenes is None:
        scenes = [_scene_draft()]
    return {
        "goal": "the newcomer and the shopkeeper truly meet",
        "dramatic_question": "Will the shop's silence open to a stranger?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the first hard frost presses the order book",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "a repair job, maybe",
        "chapter_questions_to_advance": question,
        "scenes": scenes,
    }


def _active_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    director: Director,
    planner: ScenePlanner,
    *,
    scenes: list[dict[str, Any]] | None = None,
) -> None:
    """Town seeded, chapter planned, its first scene opened (``ACTIVE``)
    — no segment committed yet."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(TOWN, _blueprint(scenes=scenes), NOW), Ok
    )
    opened = planner.open_scene(SCENE, NOW)
    assert isinstance(opened, Ok)


def _commit(
    conn: sqlite3.Connection,
    narrative: SqliteNarrativeStore,
    world_store: SqliteWorldStore,
    *,
    scene_id: str = SCENE,
    segment_seq: int = 1,
    body: str = "The bell above the door answers before her voice does.",
    participants: tuple[str, ...] = (ACTOR, PLAYER),
    narration: str = "the two meet at the bindery steps",
    effects: tuple[StateEffect, ...] = (),
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
        effects=effects,
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
    state_effects: tuple[StateEffect, ...] = (),
    participants: tuple[str, ...] = (PLAYER, ACTOR),
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
    submission_id: str = "sub-1",
    intent_text: str = "I hold the ledger and say nothing.",
    adjudication: Adjudication | None = None,
    duration_ticks: int = 7,
    now: str = LATER,
):
    gate = get_gate(conn, GATE)
    if gate is not None and gate.status is GateStatus.ANSWERED:
        assert isinstance(begin_resolving(conn, gate_id=GATE, now=now), Ok)
    return commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id=submission_id,
        adjudication=adjudication or _ruling(),
        duration_ticks=duration_ticks,
        now=now,
    )


def _open_gate(conn: sqlite3.Connection) -> None:
    assert isinstance(
        open_gate(
            conn,
            scene_id=SCENE,
            gate_seq=1,
            options=("hold the ledger", "step back"),
            now=NOW,
        ),
        Ok,
    )


def _submit_gate(
    conn: sqlite3.Connection,
    *,
    submission_id: str = "sub-1",
    intent_text: str = "I hold the ledger and say nothing.",
) -> None:
    assert isinstance(
        submit_gate(
            conn,
            gate_id=GATE,
            submission_id=submission_id,
            intent_text=intent_text,
            now=NOW,
        ),
        Ok,
    )


def _fake(**kwargs: Any) -> DeterministicFakeProvider:
    return DeterministicFakeProvider(**kwargs)


def _pipeline(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    *,
    provider: DeterministicFakeProvider,
    planner_provider: DeterministicFakeProvider | None = None,
    director_provider: DeterministicFakeProvider | None = None,
    action_duration_ticks: int = 7,
) -> Pipeline:
    return Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=provider,
        planner_provider=planner_provider or provider,
        director_provider=director_provider or provider,
        resolver_provider=provider,
        action_duration_ticks=action_duration_ticks,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(
        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    )


def _all_constants(tree: ast.AST) -> list[str]:
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _sql_constants(tree: ast.AST) -> list[str]:
    return [
        text
        for text in _all_constants(tree)
        if re.match(r"(?i)^\s*(select|insert|update|delete)\b", text)
    ]


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


# ---------------------------------------------------------------------------
# 1. HIGH-1 — the SETTLING precondition gate (STATE §21)
# ---------------------------------------------------------------------------


def test_settle_refuses_a_chapter_with_an_active_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """An ``ACTIVE`` scene is a running story: the flip refuses
    ``VALIDATION_FAILED`` naming the scene, and the chapter's row is
    untouched — same status, same ``state_version``, zero settlement
    rows (the whole transaction rolled back)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    committed = _commit(conn, narrative, world_store)  # non-terminal
    assert isinstance(committed, Ok)
    before = narrative.get_chapter(CH)
    assert before is not None
    assert before.status is ChapterStatus.ACTIVE

    refused = narrative.settle_chapter(
        CH, now=LATER, expected_state_version=before.state_version
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert SCENE in refused.error.message
    assert "ACTIVE" in refused.error.message
    after = narrative.get_chapter(CH)
    assert after == before  # zero state change, byte for byte
    assert _count(conn, "chapter_settlement") == 0


@pytest.mark.parametrize("stage", ["OPEN", "ANSWERED", "RESOLVING", "COMMITTED"])
def test_settle_refuses_a_chapter_with_a_gate_short_of_closed(
    stage: str,
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Every gate word short of ``CLOSED`` blocks the settle — the
    ``OPEN`` / ``ANSWERED`` / ``RESOLVING`` stop and the
    ``COMMITTED``-unresumed ruling alike (STATE §21's four checks name
    the gate and its status, and the chapter row stays untouched).

    The scene's story is closed through the store's **explicit**
    lifecycle face (``commit_scene``, which spells no span and judges
    no gate — the commit *transactions* are the gate judges): the state
    pinned here is exactly what the precondition guards, and no
    reachable commit path can produce it."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    _open_gate(conn)
    if stage != "OPEN":
        _submit_gate(conn)
    if stage in ("RESOLVING", "COMMITTED"):
        assert isinstance(
            begin_resolving(conn, gate_id=GATE, now=NOW), Ok
        )
    if stage == "COMMITTED":
        action = _committed_action(conn, world_store, narrative)
        assert isinstance(action, Ok)
    gate = get_gate(conn, GATE)
    assert gate is not None and gate.status.value == stage
    scene = narrative.get_scene(SCENE)
    assert scene is not None and scene.status is SceneStatus.ACTIVE
    moved = narrative.commit_scene(
        SCENE, now=LATER, expected_state_version=scene.state_version
    )
    assert isinstance(moved, Ok)
    assert moved.value.status is SceneStatus.COMMITTED
    before = narrative.get_chapter(CH)
    assert before is not None

    refused = narrative.settle_chapter(
        CH, now=LATER, expected_state_version=before.state_version
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert GATE in refused.error.message
    assert stage in refused.error.message
    assert narrative.get_chapter(CH) == before
    assert _count(conn, "chapter_settlement") == 0


def test_settle_refuses_a_chapter_with_a_pending_replan_obligation(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The ruling's plan change is not consumed yet: a ``PENDING``
    ``action_replan`` obligation blocks the settle even though the
    story itself came to rest (the scene's terminal segment closed the
    scene, the continuation passage closed the gate) — the plan face
    still owes work and a chapter does not settle over it."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    _open_gate(conn)
    _submit_gate(conn)
    assert isinstance(begin_resolving(conn, gate_id=GATE, now=NOW), Ok)
    action = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    assert isinstance(action, Ok)
    request = replan_request_id_for(GATE, "sub-1")
    obligation = replan_obligation(conn, request)
    assert obligation is not None
    assert obligation.status is ReplanStatus.PENDING
    # the continuation closes the gate and the scene (the story is at
    # rest) — the obligation still stands.
    continuation = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        body="You set the ledger down, and the room exhales.",
        narration="the ledger is set down",
        duration_ticks=2,
        is_last_segment=True,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(continuation, Ok)
    gate = get_gate(conn, GATE)
    assert gate is not None and gate.status is GateStatus.CLOSED
    scene = narrative.get_scene(SCENE)
    assert scene is not None and scene.status is SceneStatus.COMMITTED
    before = narrative.get_chapter(CH)
    assert before is not None

    refused = narrative.settle_chapter(
        CH, now=LATER, expected_state_version=before.state_version
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert request in refused.error.message
    assert "PENDING" in refused.error.message
    assert narrative.get_chapter(CH) == before

    # the plan face is consumed through its own protocol (the CHAPTER
    # arm answers on the standing chapter); the flip then lands — the
    # chapter was never in a legal SETTLING state before.
    revised = director.apply_action_replan(request, _blueprint(), LATER2)
    assert isinstance(revised, Ok)
    applied = replan_obligation(conn, request)
    assert applied is not None and applied.status is ReplanStatus.APPLIED
    moved = narrative.settle_chapter(
        CH, now=LATER2, expected_state_version=before.state_version
    )
    assert isinstance(moved, Ok)
    assert moved.value.status is ChapterStatus.SETTLING


def test_a_planned_scene_does_not_block_the_settle(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The remaining story never happened: a ``PLANNED`` scene is the
    plan's own history and the chapter ends without it (the contract's
    「不得要求所有计划场都必须发生」)."""

    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        director,
        planner,
        scenes=[_scene_draft(), _scene_draft(purpose="the ledger")],
    )
    committed = _commit(conn, narrative, world_store, is_last_segment=True)
    assert isinstance(committed, Ok)
    second = narrative.get_scene(SCENE2)
    assert second is not None and second.status is SceneStatus.PLANNED

    moved = narrative.settle_chapter(CH, now=LATER, expected_state_version=2)
    assert isinstance(moved, Ok)
    assert moved.value.status is ChapterStatus.SETTLING
    # the planned anchor is untouched — the settlement moves the chapter
    # row alone.
    still = narrative.get_scene(SCENE2)
    assert still == second


def test_a_settled_chapter_opens_no_new_scene(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The HIGH-1 family's flip-side door (the review's F1): the two-step
    合成 — settle the chapter, then activate a remaining PLANNED scene —
    must NOT construct the "chapter CLOSED / scene ACTIVE" state the
    SETTLING precondition guards at the flip. ``activate_scene`` refuses
    a SETTLING or CLOSED chapter ``VALIDATION_FAILED`` and the scene
    stays PLANNED (zero state change)."""

    _active_scene(
        conn,
        world_store,
        cast_store,
        bible_store,
        director,
        planner,
        scenes=[_scene_draft(), _scene_draft(purpose="the ledger")],
    )
    committed = _commit(conn, narrative, world_store, is_last_segment=True)
    assert isinstance(committed, Ok)
    second = narrative.get_scene(SCENE2)
    assert second is not None and second.status is SceneStatus.PLANNED

    moved = narrative.settle_chapter(CH, now=LATER, expected_state_version=2)
    assert isinstance(moved, Ok)
    assert moved.value.status is ChapterStatus.SETTLING
    # the flip-side door, on the SETTLING chapter: the remaining PLANNED
    # scene refuses to activate.
    refused = narrative.activate_scene(SCENE2, LATER, second.state_version)
    assert isinstance(refused, Err)
    assert refused.error.code == DomainErrorCode.VALIDATION_FAILED
    assert "settling/closed chapter opens no new scene" in (
        refused.error.message or ""
    )
    assert narrative.get_scene(SCENE2) == second

    # and on the CLOSED chapter after NCP-4.
    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    chapter = narrative.get_chapter(CH)
    assert chapter is not None and chapter.status is ChapterStatus.CLOSED
    refused_closed = narrative.activate_scene(SCENE2, LATER, second.state_version)
    assert isinstance(refused_closed, Err)
    assert refused_closed.error.code == DomainErrorCode.VALIDATION_FAILED
    assert narrative.get_scene(SCENE2) == second


def test_the_settling_precondition_rides_the_flip_transaction() -> None:
    """The structural face of HIGH-1: the public ``settle_chapter``
    owns exactly one ``BEGIN IMMEDIATE`` … ``COMMIT`` and spells no SQL
    of its own — the arm inside that transaction runs the three checks
    (scene / gate / obligation) and the guarded CAS update, and the
    check helper opens no transaction of its own."""

    public = _function(STORE_TREE, "settle_chapter")
    constants = _all_constants(public)
    assert constants.count("BEGIN IMMEDIATE") == 1
    assert constants.count("COMMIT") == 1
    assert _sql_constants(public) == []
    arm = _function(STORE_TREE, "_settle_chapter_tx")
    for text in _all_constants(arm):
        assert text not in {"BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"}, text
    updates = [
        text
        for text in _sql_constants(arm)
        if text.lstrip().upper().startswith("UPDATE")
    ]
    assert len(updates) == 1
    assert "state_version = state_version + 1" in updates[0]
    assert "AND state_version = ?" in updates[0]
    checks = _function(STORE_TREE, "_running_story_blocker")
    literals = _sql_constants(checks)
    assert any("world_scene" in text and "ACTIVE" in text for text in literals)
    assert any("user_gate" in text and "CLOSED" in text for text in literals)
    assert any(
        "action_replan" in text and "PENDING" in text for text in literals
    )
    for text in _all_constants(checks):
        assert text not in {"BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"}, text


# ---------------------------------------------------------------------------
# 2. HIGH-2 — the world-authoritative ResolverContext
# ---------------------------------------------------------------------------


def test_the_resolver_context_field_set_is_frozen() -> None:
    """The shape pin: the Resolver's input names the world-authoritative
    faces (Bible / facts / player / scene cast / counterparts) beside
    the user's submission and the POV's knowledge read — the
    POV-limited ``AdjudicationContext`` is gone."""

    names = tuple(field.name for field in dataclasses.fields(ResolverContext))
    assert names == (
        "gate_id",
        "scene_id",
        "submission_id",
        "intent_text",
        "selected_option",
        "options",
        "bible",
        "current_facts",
        "player_character",
        "place",
        "participants",
        "counterparts",
        "pov_actor_id",
        "cognition",
        "memory",
        "current_tick",
    )
    assert not hasattr(ResolverContext, "private")
    # the V3-8a name is replaced, not aliased.
    import elc.world.providers as providers

    assert not hasattr(providers, "AdjudicationContext")


def test_the_resolver_context_carries_the_world_authoritative_faces(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The provider input a real drive compiles: the CURRENT Bible's
    hard rules, the settled fact half (an inventory claim among it),
    the player's profile row, the scene's canonical facts and the
    counterpart's profile — beside the user's own submission. The
    intent rides from the durable ``user_action`` row; the resolver
    never sees a fabricated one, and the POV's cognition / memory ride
    for what the player character knows."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director := Director(
            conn,
            world_store=world_store,
            cast_store=cast_store,
            bible_store=bible_store,
            narrative_store=narrative,
        ),
        Director,
    )
    assert isinstance(director.open_next_chapter(TOWN, _blueprint(), NOW), Ok)
    planner = ScenePlanner(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    first = _commit(
        conn,
        narrative,
        world_store,
        effects=(
            StateEffect(key="inventory:pc-you", statement="a borrowed ledger"),
        ),
    )
    assert isinstance(first, Ok)

    fake = _fake(adjudications={GATE: _ruling()})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, provider=fake
    )
    driven = pipeline.run_scene(
        SCENE,
        (
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text="I hold the ledger and say nothing.",
            ),
        ),
        NOW,
    )
    assert isinstance(driven, Ok)
    context = fake.resolver_contexts[0]
    # the world's authority.
    assert context.bible is not None
    assert context.bible.hard_rules == HARD_RULE
    assert [
        (fact.canonical_key, fact.statement) for fact in context.current_facts
    ] == [("inventory:pc-you", "a borrowed ledger")]
    assert context.player_character is not None
    assert context.player_character.abilities == "steady hands"
    assert context.player_character.limits == "no training with steel"
    assert context.place == "the bindery steps"
    assert context.participants == (ACTOR, PLAYER)
    assert [profile.actor_id for profile in context.counterparts] == [ACTOR]
    assert context.counterparts[0].private_context == LIA_PRIVATE
    # the user's own submission — durable, never an invention.
    stored = action_of(conn, GATE)
    assert stored is not None
    assert context.intent_text == stored.intent_text
    assert context.intent_text == "I hold the ledger and say nothing."
    assert context.submission_id == stored.submission_id
    assert context.gate_id == GATE and context.scene_id == SCENE
    assert context.options == ("hold the ledger", "step back")
    assert "I draw my sword" not in str(context)
    # the POV's knowledge read rides for what the player character knows.
    assert context.pov_actor_id == ACTOR
    assert context.cognition.viewer_id == ACTOR
    assert context.memory.viewer_id == ACTOR
    assert context.current_tick == 3


def test_the_resolver_context_reads_the_durable_action_row() -> None:
    """The compilation's source pin: the pipeline reads the submission's
    action through :func:`elc.world.action.action_by_id` (the V3-8b
    sibling read) and never spells an intent of its own — a source-level
    face of 「用户意图来自 submission」."""

    source = PIPELINE_SOURCE
    assert "action_by_id(" in source
    assert "intent_text=action.intent_text" in source


# ---------------------------------------------------------------------------
# 3. HIGH-3 — the DirectorProvider and the division freeze
# ---------------------------------------------------------------------------


def test_the_split_is_physical_two_providers(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The division freeze, behaviorally: a SCENE replan reaches the
    **PlannerProvider** (the POV-safe scene context — its primary
    input) and the DirectorProvider records nothing; the chapter level
    never travels through the planner."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    writer = _fake(
        prose={(SCENE, 1): "The bell answers first."},
    )
    planner_fake = _fake(adjudications={GATE: _ruling(replan_scope=ReplanScope.SCENE)})
    director_fake = _fake()
    pipeline = Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=writer,
        planner_provider=planner_fake,
        director_provider=director_fake,
        resolver_provider=planner_fake,
        action_duration_ticks=7,
    )
    assert isinstance(pipeline.open_chapter(TOWN, _blueprint(), NOW), Ok)
    driven = pipeline.run_scene(
        SCENE,
        (
            SegmentBeat(duration_ticks=3),
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text="I hold the ledger and say nothing.",
            ),
            SegmentBeat(duration_ticks=2, is_last_segment=True),
        ),
        NOW,
    )
    assert isinstance(driven, Ok)
    assert driven.value.replans[0].scope is ReplanScope.SCENE
    assert len(planner_fake.replan_contexts) == 1
    replan_context = planner_fake.replan_contexts[0]
    assert replan_context.scene_id == SCENE
    assert replan_context.pov_actor_id == ACTOR
    assert replan_context.cognition.viewer_id == ACTOR
    assert replan_context.memory.viewer_id == ACTOR
    # the chapter level was never the planner's.
    assert director_fake.blueprint_contexts == []
    assert planner_fake.blueprint_contexts == []


def test_a_chapter_replan_is_produced_by_the_director_provider(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The CHAPTER arm's production face: the provider receives the
    full ``DirectorContext`` (Bible / facts / cast / storylines /
    summaries / tick) plus the committed ruling that triggered the
    replan — and the POV-limited PlannerProvider records nothing of
    it."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(director.open_next_chapter(TOWN, _blueprint(), NOW), Ok)
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    _open_gate(conn)
    _submit_gate(conn)
    assert isinstance(begin_resolving(conn, gate_id=GATE, now=LATER), Ok)
    committed = _committed_action(
        conn,
        world_store,
        narrative,
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
    )
    assert isinstance(committed, Ok)
    request = replan_request_id_for(GATE, "sub-1")

    writer = _fake(prose={(SCENE, 1): "Something answers."})
    planner_fake = _fake()
    director_fake = _fake()
    pipeline = Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=writer,
        planner_provider=planner_fake,
        director_provider=director_fake,
        resolver_provider=director_fake,
        action_duration_ticks=7,
    )
    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert walk.value.replans_consumed[0].scope is ReplanScope.CHAPTER
    context = director_fake.blueprint_contexts[0]
    # the DirectorContext's own faces.
    assert context.director_context.world_id == TOWN
    assert context.director_context.bible is not None
    assert context.director_context.bible.hard_rules == HARD_RULE
    assert context.director_context.current_tick == 7
    assert context.director_context.cast.player_character is not None
    # the cast input's durable order is actor_id ascending.
    assert [m.actor_id for m in context.director_context.cast.members] == [
        PARTNER,
        ACTOR,
    ]
    assert context.director_context.storylines == ()
    assert context.director_context.chapter_summaries == ()
    # the trigger's own words, and the current Blueprint to start from.
    assert context.chapter_id == CH
    assert context.replan_request_id == request
    assert context.trigger is not None
    assert context.trigger.user_action_id == f"{GATE}-a"
    assert context.trigger.intent_text == "I hold the ledger and say nothing."
    assert context.trigger.outcome == (
        "Lia lets you hold the ledger; the ice thins."
    )
    assert context.blueprint is not None
    assert "scenes" in context.blueprint
    # the POV-limited planner saw none of it.
    assert planner_fake.blueprint_contexts == []
    assert planner_fake.replan_contexts == []
    # the payload landed through the Director's own face and completed.
    applied = replan_obligation(conn, request)
    assert applied is not None and applied.status is ReplanStatus.APPLIED
    plans = narrative.plans_of(CH)
    assert [plan.plan_revision for plan in plans] == [1, 2]


def test_the_initial_blueprint_is_produced_by_the_director_provider(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """The Director face's other arm: ``plan_chapter`` drafts the
    initial Blueprint through the provider (the no-trigger context —
    no chapter exists yet) and lands it through the Director's own
    face; a dangling world is answered before the provider is asked,
    and an unscripted draft is the fake's honest ``ValueError``."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    writer = _fake()
    planner_fake = _fake()
    director_fake = _fake(blueprints=(_blueprint(),))
    pipeline = Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=writer,
        planner_provider=planner_fake,
        director_provider=director_fake,
        resolver_provider=writer,
        action_duration_ticks=7,
    )
    missing = pipeline.plan_chapter("no-such-world", NOW)
    assert isinstance(missing, Err)
    assert missing.error.code is DomainErrorCode.NOT_FOUND

    planned = pipeline.plan_chapter(TOWN, NOW)
    assert isinstance(planned, Ok)
    assert planned.value.chapter.chapter_id == CH
    context = director_fake.blueprint_contexts[0]
    assert context.director_context.world_id == TOWN
    assert context.director_context.bible is not None
    assert context.chapter_id is None
    assert context.replan_request_id is None
    assert context.trigger is None
    assert context.blueprint is None
    assert planner_fake.blueprint_contexts == []
    assert planner_fake.plan_contexts == []

    # an unscripted draft is the script's gap, never an invented plan.
    empty = _fake()
    pipeline_two = _pipeline(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        provider=empty,
        director_provider=empty,
    )
    with pytest.raises(ValueError):
        pipeline_two.plan_chapter(TOWN, LATER)
    assert narrative.get_chapter("world-town-ch02") is None


def test_the_planner_protocol_carries_no_blueprint_arm() -> None:
    """The protocol split, structurally: ``PlannerProvider`` answers the
    SCENE level only and ``DirectorProvider`` carries both chapter
    arms; the old ``ChapterPlanContext`` is gone, not aliased."""

    assert hasattr(PlannerProvider, "plan_scene")
    assert hasattr(PlannerProvider, "replan_element")
    assert not hasattr(PlannerProvider, "replan_blueprint")
    assert hasattr(DirectorProvider, "draft_blueprint")
    assert hasattr(DirectorProvider, "replan_blueprint")
    import elc.world.providers as providers

    assert not hasattr(providers, "ChapterPlanContext")
    fake = _fake()
    assert isinstance(fake, DirectorProvider)
    assert isinstance(fake, PlannerProvider)
    assert isinstance(fake, WriterProvider)


# ---------------------------------------------------------------------------
# 4. the HARD GATE — the continuation obligation
# ---------------------------------------------------------------------------


def _crashed_after_the_ruling(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The NCP-2 aftermath: one committed segment, the gate's ruling
    committed and nobody resumed past it (no continuation passage —
    the crash window the HARD GATE closes)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    committed = _commit(conn, narrative, world_store)
    assert isinstance(committed, Ok)
    _open_gate(conn)
    _submit_gate(conn)
    assert isinstance(begin_resolving(conn, gate_id=GATE, now=NOW), Ok)
    action = _committed_action(conn, world_store, narrative)
    assert isinstance(action, Ok)


def test_recovery_scan_lists_the_committed_unclosed_gate(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """RA §29's seventh family: a ``COMMITTED`` gate whose scene holds
    no passage carrying its action is listed with the four durable
    anchors (scene / gate / committed action / next sequence), and the
    row leaves the family the moment a passage resumes it."""

    _crashed_after_the_ruling(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    scan = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(scan, Ok)
    assert scan.value.continuations == (
        ContinuationObligation(
            scene_id=SCENE,
            gate_id=GATE,
            user_action_id=f"{GATE}-a",
            next_segment_seq=2,
        ),
    )
    assert scan.value.gates == ()  # the pre-existing families are intact
    assert scan.value.actions == ()
    assert [s.scene_id for s in scan.value.scenes] == [SCENE]
    assert scan.value.replans == ()

    resumed = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        body="You set the ledger down.",
        narration="the ledger is set down",
        duration_ticks=2,
        now=LATER,
        outcome_ref=f"{GATE}-a",
    )
    assert isinstance(resumed, Ok)
    after = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(after, Ok)
    assert after.value.continuations == ()


def test_next_segment_seq_derives_from_the_segment_commit_rows(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The derivation is durable, not positional: with **two** segments
    committed before the ruling, the family's ``next_segment_seq`` is 3
    — ``max(committed seq) + 1`` read from ``segment_commit`` — and the
    resume drives the continuation there (the commit face's ordering
    law would refuse any other value)."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    first = _commit(conn, narrative, world_store, segment_seq=1)
    assert isinstance(first, Ok)
    second = _commit(
        conn,
        narrative,
        world_store,
        segment_seq=2,
        body="She turns the page, unhurried.",
        narration="the page turns",
        duration_ticks=2,
        now=LATER,
    )
    assert isinstance(second, Ok)
    _open_gate(conn)
    _submit_gate(conn)
    assert isinstance(begin_resolving(conn, gate_id=GATE, now=LATER2), Ok)
    action = _committed_action(conn, world_store, narrative, now=LATER2)
    assert isinstance(action, Ok)

    scan = recovery_scan(conn, narrative_store=narrative)
    assert isinstance(scan, Ok)
    assert scan.value.continuations[0].next_segment_seq == 3

    writer = _fake(prose={(SCENE, 3): "The continuation lands."})
    pipeline = _pipeline(
        conn, world_store, cast_store, bible_store, narrative, provider=writer
    )
    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert walk.value.continuations_driven == (GATE,)
    row = conn.execute(
        "SELECT passage_id, segment_seq, outcome_ref, body"
        " FROM narrative_passage WHERE segment_seq = 3"
    ).fetchone()
    assert row is not None
    assert str(row[0]) == f"{SCENE}-p0003"
    assert int(row[1]) == 3
    assert str(row[2]) == f"{GATE}-a"
    assert str(row[3]) == "The continuation lands."


def test_resume_drives_the_first_continuation_passage(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The HARD GATE's behavioral face: ``resume`` drives the first
    continuation passage from durable state alone — no GateBeat is
    re-supplied, the ruling is not re-adjudicated (one outcome), the
    passage carries the committed action as its forced ``outcome_ref``
    (which closes the gate in that same commit), and the walk converges
    on a second run."""

    _crashed_after_the_ruling(
        conn, world_store, cast_store, bible_store, narrative, director, planner
    )
    tick_before = read_current_tick(conn, TOWN)
    assert isinstance(tick_before, Ok)
    assert tick_before.value == 10  # 3 + the ruling's 7

    writer = _fake(prose={(SCENE, 2): "The room exhales around the ledger."})
    resolver = _fake()
    pipeline = Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=writer,
        planner_provider=writer,
        director_provider=writer,
        resolver_provider=resolver,
        action_duration_ticks=7,
    )
    walk = pipeline.resume(TOWN, LATER2)
    assert isinstance(walk, Ok)
    assert walk.value.gates_committed == ()
    assert walk.value.replans_consumed == ()
    assert walk.value.continuations_driven == (GATE,)
    # the ruling was not re-adjudicated: the resolver was never asked,
    # and the action row still holds the one outcome. The continuation
    # is the only new canon (the segment + the ruling + it).
    assert resolver.resolver_contexts == []
    assert _count(conn, "user_action") == 1
    assert _count(conn, "world_event") == 3
    # the passage names the committed action and closes its gate in the
    # same commit.
    row = conn.execute(
        "SELECT passage_id, segment_seq, outcome_ref FROM narrative_passage"
        " WHERE segment_seq = 2"
    ).fetchone()
    assert row is not None
    assert str(row[0]) == f"{SCENE}-p0002"
    assert int(row[1]) == 2
    assert str(row[2]) == f"{GATE}-a"
    gate = get_gate(conn, GATE)
    assert gate is not None and gate.status is GateStatus.CLOSED
    action = action_by_id(conn, f"{GATE}-a")
    assert action is not None and action.status is ActionStatus.COMMITTED
    tick_after = read_current_tick(conn, TOWN)
    assert isinstance(tick_after, Ok)
    assert tick_after.value == 11  # the continuation's one-tick beat

    again = pipeline.resume(TOWN, LATER2)
    assert isinstance(again, Ok)
    assert again.value.continuations_driven == ()
    assert _count(conn, "narrative_passage") == 2
    tick_again = read_current_tick(conn, TOWN)
    assert isinstance(tick_again, Ok)
    assert tick_again.value == 11


def test_the_pipeline_state_carries_no_external_starting_sequence() -> None:
    """The contract's 「取消/降级外部 ``first_segment_seq`` 状态」,
    structurally: no function of the drive face takes a starting-sequence
    argument any more — the continuation's sequence is the recovery
    scan's durable derivation (``next_segment_seq``), and the drive's
    own segments are the script's ordinals. The module docstring keeps
    the removal's own record — this pin reads the signatures."""

    tree = ast.parse(PIPELINE_SOURCE)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for argument in node.args.args + node.args.kwonlyargs:
            assert argument.arg != "first_segment_seq", node.name
    assert "next_segment_seq" in PIPELINE_SOURCE
    run_scene = _function(tree, "run_scene")
    arguments = {
        argument.arg for argument in run_scene.args.args
    } | {argument.arg for argument in run_scene.args.kwonlyargs}
    assert arguments == {"self", "scene_id", "beats", "now"}


# ---------------------------------------------------------------------------
# 5. MEDIUM-HIGH — the settlement's hooks never upgrade from the Blueprint
# ---------------------------------------------------------------------------


def test_the_settlement_hooks_never_upgrade_from_the_blueprint(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """Plan content does not become Narrative Memory at the settlement:
    the Blueprint's ``chapter_questions_to_advance`` is not copied into
    ``chapter_settlement.hooks`` (the honest empty string), while
    ``created_at_revision`` keeps the plan's provenance number — and
    the revision counter follows the latest revision, not the one the
    question was first written in."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    committed = _commit(conn, narrative, world_store, is_last_segment=True)
    assert isinstance(committed, Ok)
    # a second plan revision: the question's Plan face moves on; the
    # settlement must not carry its content either way.
    revised = director.revise_blueprint(
        CH, _blueprint(question="a different question entirely"), LATER
    )
    assert isinstance(revised, Ok)
    assert revised.value.plan.plan_revision == 2
    plan = narrative.adopted_plan(CH)
    assert plan is not None
    assert plan.chapter_questions_to_advance == "a different question entirely"

    moved = narrative.settle_chapter(CH, now=LATER, expected_state_version=2)
    assert isinstance(moved, Ok)
    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    record = settled.value
    assert record.hooks == ""
    assert record.created_at_revision == 2
    assert QUESTION not in record.hooks
    assert "a different question entirely" not in record.hooks
    # the provenance number rides alone: no Blueprint text anywhere in
    # the settlement row's content fields.
    for field in ("summary", "storyline_updates", "resolved_lines"):
        assert QUESTION not in getattr(record, field)


def test_the_settlement_draft_carries_no_plan_content() -> None:
    """The draft's source-level face: ``chapter_questions_to_advance``
    is never read, the ``plan_revision`` provenance number is the only
    ``latest`` Plan-face attribute the draft touches, and the two
    honest-empty slots (``hooks`` / ``resolved_lines``) are spelled as
    the empty string."""

    draft = _function(SETTLEMENT_TREE, "_settlement_draft")
    attributes = [
        node.attr
        for node in ast.walk(draft)
        if isinstance(node, ast.Attribute)
    ]
    assert "chapter_questions_to_advance" not in attributes
    assert "plan_revision" in attributes
    latest = {
        node.attr
        for node in ast.walk(draft)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "latest"
    }
    assert latest == {"plan_revision"}
    string_constants = _all_constants(draft)
    assert string_constants.count("") == 2


def test_the_settled_question_text_stays_out_of_every_settlement_field(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The storage face of the same law: whatever the settlement row
    holds, the Blueprint's question is in none of it — the row is
    compress-only (N-INV-004) and the Plan→Memory upgrade is refused
    physically."""

    _active_scene(
        conn, world_store, cast_store, bible_store, director, planner
    )
    committed = _commit(conn, narrative, world_store, is_last_segment=True)
    assert isinstance(committed, Ok)
    moved = narrative.settle_chapter(CH, now=LATER, expected_state_version=2)
    assert isinstance(moved, Ok)
    settled = settle_chapter(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        chapter_id=CH,
        now=LATER,
    )
    assert isinstance(settled, Ok)
    row = conn.execute(
        "SELECT summary, storyline_updates, hooks, resolved_lines,"
        " salience_notes FROM chapter_settlement WHERE chapter_id = ?",
        (CH,),
    ).fetchone()
    assert row is not None
    assert all(QUESTION not in str(cell) for cell in row)
    assert str(row[2]) == ""
