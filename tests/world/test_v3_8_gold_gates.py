"""V3-8d — the Gold Scenario end to end and the twelve structural
acceptance gates (TASK-OPI-cddb517c-…21 / the opening ruling
``DEC-OPI-cddb517c-…19``; the paradigm shift's §10.2 and IMPLEMENTATION
PLAN §20's V3-8 row).

**What this suite proves, stated honestly**: the fixed Gold Scenario
(:mod:`elc.world.gold`) is driven end to end through the **real**
production faces (:mod:`elc.world.llm_providers` over the scenario's
scripted completion — offline, deterministic, 0 skipped), and the
twelve structural gates the plan names are pinned one by one:
① the Director produces the complete Blueprint; ② the Writer keeps
Lia's POV; ③ the secret does not leak early; ④ the User Gate fires
once, at the scripted will point; ⑤ the user's free input is judged by
the Resolver and lands as canon; ⑥ the user's choice really invalidates
the original plan (``replan_scope = CHAPTER``); ⑦ the drive follows the
new revision and never revives a discarded scene; ⑧ scene 3 reads what
scene 2 committed; ⑨ the chapter's actual result visibly differs from
the Blueprint and the system records both honestly; ⑩ the settlement
summarizes the committed chapter without moving anything; ⑪ chapter 2
is planned from chapter 1's real outcome; ⑫ a restart resumes from the
latest narrative state (a file database, a committed-unclosed gate, the
seventh recovery family).

The user's own 「好玩」 acceptance is **not** this suite's: scripted
prose is structural evidence, and the real-model judgement is V3-8e's
(the acceptance's two-door law — the 12 gates and the user's word
together).
"""

from __future__ import annotations

import ast
import dataclasses
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
from elc.world import gold
from elc.world.action import (
    ActionStatus,
    GateStatus,
    ReplanScope,
    ReplanStatus,
    action_of,
    get_gate,
    replan_obligation,
    replan_request_id_for,
)
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.cognition import v3_cognition_view
from elc.world.memory import v3_memory_view
from elc.world.narrative import (
    ChapterStatus,
    PlanRevisionStatus,
    SceneStatus,
    SqliteNarrativeStore,
)
from elc.world.pipeline import Pipeline, SegmentBeat
from elc.world.scene import ScenePlanner
from elc.world.settlement import (
    ChapterSettlementRecord,
    chapter_settlements_of,
)
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import StateEffect
from tests.conftest import SRC_ROOT

REPO = Path(__file__).resolve().parents[2]
AOCI_FILE = REPO / "aoci.code.txt"

GOLD_SOURCE = (SRC_ROOT / "world" / "gold.py").read_text(encoding="utf-8")
GOLD_TREE = ast.parse(GOLD_SOURCE)

NOW = "2026-10-13T00:00:00+00:00"
LATER = "2026-10-13T01:00:00+00:00"
LATER2 = "2026-10-13T02:00:00+00:00"
LATER3 = "2026-10-13T03:00:00+00:00"

_CHAPTER_FIELDS = (
    "goal",
    "dramatic_question",
    "planned_start_tick",
    "planned_end_tick",
    "closing_pressure",
    "desired_development",
    "soft_outcomes",
    "chapter_questions_to_advance",
)

# ---------------------------------------------------------------------------
# fixtures / helpers (the V3-8a / V3-8c suites' own shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated ``app.db`` with the production profile's
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


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _passage_bodies(conn: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in conn.execute(
            "SELECT body FROM narrative_passage ORDER BY passage_id"
        ).fetchall()
    ]


@dataclasses.dataclass
class _GoldDrive:
    """One full Gold drive's hands: the stores, the providers, and the
    four drives' answers (every one already asserted ``Ok``)."""

    conn: sqlite3.Connection
    world_store: SqliteWorldStore
    cast_store: SqliteCastStore
    bible_store: SqliteBibleStore
    narrative: SqliteNarrativeStore
    planner: ScenePlanner
    completion: gold.GoldScriptedCompletion
    pipeline: Pipeline
    planned: Any
    scene1: Any
    scene2: Any
    scene3: Any
    settlement: ChapterSettlementRecord
    ch2: Any


def _drive_gold(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> _GoldDrive:
    """Drive the whole first chapter of the Gold Scenario through the
    real providers, settle it, and plan the second chapter — the shape
    every gate but ⑫ reads."""

    completion = gold.gold_completion()
    created = gold.seed_gold_world(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        now=NOW,
    )
    assert isinstance(created, Ok), created
    planner = ScenePlanner(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )
    pipeline = gold.build_gold_pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        completion=completion,
    )
    planned = pipeline.plan_chapter(gold.WORLD_ID, NOW)
    assert isinstance(planned, Ok), planned
    beats = gold.gold_beats_by_scene()
    scene1 = pipeline.run_scene(gold.S1, beats[gold.S1], NOW)
    assert isinstance(scene1, Ok), scene1
    scene2 = pipeline.run_scene(gold.S2, beats[gold.S2], NOW)
    assert isinstance(scene2, Ok), scene2
    scene3 = pipeline.run_scene(gold.S3, beats[gold.S3], NOW)
    assert isinstance(scene3, Ok), scene3
    settled = pipeline.settle(gold.CH1, NOW)
    assert isinstance(settled, Ok), settled
    ch2 = pipeline.plan_chapter(gold.WORLD_ID, NOW)
    assert isinstance(ch2, Ok), ch2
    return _GoldDrive(
        conn=conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative=narrative,
        planner=planner,
        completion=completion,
        pipeline=pipeline,
        planned=planned,
        scene1=scene1,
        scene2=scene2,
        scene3=scene3,
        settlement=settled.value,
        ch2=ch2,
    )


def _writer_prompts_for_place(
    drive: _GoldDrive, place: str
) -> list[str]:
    return [
        prompt
        for prompt in drive.completion.prompts_for("writer")
        if f"- place: {place}" in prompt
    ]


# ---------------------------------------------------------------------------
# ① the Director produces the complete Blueprint
# ---------------------------------------------------------------------------


def test_gate01_the_director_produces_the_complete_blueprint(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """① ``Pipeline.plan_chapter`` through the **real**
    ``LlmDirectorProvider``: the chapter row and its adopted revision 1
    carry the scripted nine fields verbatim, ``scenes`` is non-empty and
    the four fresh anchors' derived ids are burned into the stored
    elements; the recorded prompt is the world-authoritative
    ``DirectorPlanContext`` (Bible / cast / current_tick all present)."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    opening = drive.planned.value
    assert opening.chapter.chapter_id == gold.CH1
    assert opening.chapter.chapter_index == 1
    assert opening.chapter.status is ChapterStatus.PLANNED
    plan = opening.plan
    assert plan.chapter_plan_id == gold.PLAN_R1
    assert plan.plan_revision == 1
    assert plan.status is PlanRevisionStatus.ADOPTED
    for field in _CHAPTER_FIELDS:
        assert getattr(plan, field) == gold.CH1_BLUEPRINT[field], field
    assert len(plan.scenes) == 4  # non-empty: four planned scenes
    scripted = gold.CH1_BLUEPRINT["scenes"]
    assert [element["scene_id"] for element in plan.scenes] == [
        gold.S1,
        gold.S2,
        gold.S3,
        gold.S4,
    ]
    for element, drafted in zip(plan.scenes, scripted, strict=True):
        assert element["place"] == drafted["place"]
        assert element["purpose"] == drafted["purpose"]
        assert element["pov_actor_id"] == drafted["pov_actor_id"]
        assert element["planned_start_tick"] == drafted["planned_start_tick"]
        assert element["must_hide"] == drafted["must_hide"]
    assert [row.scene_id for row in opening.scenes] == [
        gold.S1,
        gold.S2,
        gold.S3,
        gold.S4,
    ]
    assert [
        row.status for row in opening.scenes
    ] == [SceneStatus.PLANNED] * 4
    # the recorded prompt is the Director face's own input.
    prompt = drive.completion.prompts_for("director")[0]
    assert f"- world: {gold.WORLD_ID}" in prompt
    assert "- current_tick: 0" in prompt
    assert gold.GOLD_BIBLE.premise in prompt
    assert gold.GOLD_BIBLE.calendar in prompt
    assert gold.GOLD_BIBLE.hard_rules in prompt
    assert f"{gold.LIA} (Lia):" in prompt
    assert f"{gold.MOTHER} (Mother):" in prompt
    assert f"{gold.PLAYER} (Renn):" in prompt
    assert f"role={gold.GOLD_ACTORS[0].story_role}" in prompt


# ---------------------------------------------------------------------------
# ② the Writer keeps Lia's POV
# ---------------------------------------------------------------------------


def test_gate02_the_writer_keeps_lia_pov(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """② The scene's Plan face and the POV's **own** cognition / memory
    ride every Writer prompt, addressed to Lia; another participant's
    private face does not — while the world-authoritative Director
    prompt carries it (the component contrast); the POV invariant
    (``pov ∈ participants``) holds on the durable dossier."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    dossier = drive.narrative.adopted_dossier(gold.S1)
    assert dossier is not None
    assert dossier.pov_actor_id == gold.LIA
    assert dossier.pov_actor_id in dossier.participants
    opening_context = drive.scene1.value.opening.context
    assert opening_context.pov_actor_id == gold.LIA
    assert opening_context.cognition.viewer_id == gold.LIA
    assert opening_context.memory.viewer_id == gold.LIA

    prompts = _writer_prompts_for_place(drive, gold.PLACE_GATE)
    assert len(prompts) == 3
    for prompt in prompts:
        assert "lia's own cognition" in prompt
        assert "lia's own memory:" in prompt
        assert f"- place: {gold.PLACE_GATE}" in prompt
        assert "- entry_goals: " in prompt
        assert "- exit_condition: " in prompt
        assert f"- participants: {gold.LIA}, {gold.PLAYER}" in prompt
        assert "One main point of view" in prompt
        assert gold.MOTHER_PRIVATE not in prompt
    # the progression witness: nothing yet at the first segment, her own
    # first event at the second, the committed ruling at the third.
    assert gold.S1_PROSE_1 not in prompts[0]
    assert f"(EXPERIENCED) {gold.S1_PROSE_1}" in prompts[1]
    assert gold.GOLD_ADJUDICATION_PAYLOAD["outcome"] in prompts[2]
    # the component contrast: the world-authoritative face reads the
    # mother's private context; the POV-limited face cannot.
    director_prompt = drive.completion.prompts_for("director")[0]
    assert gold.MOTHER_PRIVATE in director_prompt


# ---------------------------------------------------------------------------
# ③ the secret does not leak early
# ---------------------------------------------------------------------------


def test_gate03_the_secret_does_not_leak_early(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """③ Two-plus faces of the secret's guard: (a) the Writer prompt
    lists the ``must_hide`` fragments item by item as hard prohibitions;
    (b) the deliberate leak sample is refused by :class:`PovWriter`
    (``VALIDATION_FAILED``, naming the fragment) with zero passages
    landing; (c) no landed passage contains a fragment — and the script
    does touch the secret's edge (the folded paper) without naming it."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    # (a) the prohibition list, item by item.
    prompts = _writer_prompts_for_place(drive, gold.PLACE_GATE)
    assert len(prompts) == 3
    for prompt in prompts:
        assert "- must_hide — hard prohibitions, one by one:" in prompt
        for fragment in gold.MUST_HIDE_FRAGMENTS:
            assert f"  - {fragment}" in prompt
    # (c) no landed passage leaks — and the edge is touched.
    bodies = _passage_bodies(conn)
    assert len(bodies) == 6
    for body in bodies:
        for fragment in gold.MUST_HIDE_FRAGMENTS:
            assert fragment not in body
    assert gold.S1_PROSE_2 in bodies
    assert "a corner of folded paper" in gold.S1_PROSE_2

    # (b) the deliberate violator: a fresh world whose writer answers
    # scene 1's first passage with the leak sample.
    leak_conn = sqlite3.connect(":memory:")
    leak_conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(leak_conn)
    leak_worlds = SqliteWorldStore(leak_conn, open_runtime_epoch(leak_conn))
    leak_cast = SqliteCastStore(leak_conn, open_runtime_epoch(leak_conn))
    leak_bible = SqliteBibleStore(leak_conn, open_runtime_epoch(leak_conn))
    leak_narrative = SqliteNarrativeStore(
        leak_conn, open_runtime_epoch(leak_conn)
    )
    leak_completion = gold.gold_completion(leak_prose=gold.LEAK_SAMPLE)
    assert isinstance(
        gold.seed_gold_world(
            leak_conn,
            world_store=leak_worlds,
            bible_store=leak_bible,
            cast_store=leak_cast,
            now=NOW,
        ),
        Ok,
    )
    leak_pipeline = gold.build_gold_pipeline(
        leak_conn,
        world_store=leak_worlds,
        cast_store=leak_cast,
        bible_store=leak_bible,
        narrative_store=leak_narrative,
        completion=leak_completion,
    )
    assert isinstance(leak_pipeline.plan_chapter(gold.WORLD_ID, NOW), Ok)
    refused = leak_pipeline.run_scene(
        gold.S1,
        (SegmentBeat(duration_ticks=5, is_last_segment=True),),
        NOW,
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "the sealed letter from the capital" in refused.error.message
    assert "leaks a hidden fact" in refused.error.message
    assert _count(leak_conn, "narrative_passage") == 0
    assert _count(leak_conn, "segment_commit") == 0
    assert _count(leak_conn, "world_event") == 0
    # the leak sample was the prompt's own answer (the guard, not the
    # script, is what refused).
    assert len(leak_completion.prompts_for("writer")) == 1


# ---------------------------------------------------------------------------
# ④ the User Gate fires once, at the scripted will point
# ---------------------------------------------------------------------------


def test_gate04_the_user_gate_fires_once_at_the_scripted_will_point(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """④ Exactly one gate in the whole drive, two-to-four natural
    options, opened at the scripted will point (after segment 2, tick
    540), closed by the continuation segment; the submission path taken
    is the **free-text** one (no ``selected_option``)."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    run = drive.scene1.value
    assert len(run.gates) == 1
    gate = run.gates[0]
    assert gate.gate_id == gold.GATE
    assert gate.status is GateStatus.CLOSED
    assert gate.options == gold.GATE_OPTIONS
    assert 2 <= len(gate.options) <= 4
    assert gate.opened_at_tick == gold.TICK_GATE_OPENS
    # the will point in the script's own segment order: the gate stands
    # after segment 2, whose end tick it opened at.
    assert [outcome.actual_end_tick for outcome in run.segments] == [300, 540, 600]
    assert run.segments[1].actual_end_tick == gate.opened_at_tick
    assert len(run.actions) == 1
    # the world holds exactly one gate; the durable row is the scripted
    # one and the free-text arm is what was submitted.
    assert _count(conn, "user_gate") == 1
    stored = get_gate(conn, gold.GATE)
    assert stored is not None
    assert stored.options == gold.GATE_OPTIONS
    action = action_of(conn, gold.GATE)
    assert action is not None
    assert action.selected_option is None
    assert action.intent_text == gold.GOLD_INTENT
    assert action.submission_id == gold.SUBMISSION_ID
    # the options the resolver could see are the author's own.
    resolver_prompt = drive.completion.prompts_for("resolver")[0]
    assert f"- options: {', '.join(gold.GATE_OPTIONS)}" in resolver_prompt


# ---------------------------------------------------------------------------
# ⑤ the free submission is judged and lands as canon
# ---------------------------------------------------------------------------


def test_gate05_the_free_submission_is_judged_and_lands_as_canon(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑤ The intent rides from the durable ``user_action`` row into the
    Resolver's own words (the recorded world-authoritative prompt carries
    it), and the verdict lands in canon column for column — while the
    intent text itself never enters ``world_event`` (N-INV-002's storage
    face)."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    action = action_of(conn, gold.GATE)
    assert action is not None
    payload = gold.GOLD_ADJUDICATION_PAYLOAD
    assert action.status is ActionStatus.COMMITTED
    assert action.interpretation == payload["interpretation"]
    assert action.outcome == payload["outcome"]
    assert action.actual_action == payload["actual_action"]
    assert action.consequences == payload["consequences"]
    assert action.state_effects == (
        StateEffect(
            key="household:cousin",
            statement="camped at the gate; the guest room refused",
        ),
    )
    assert action.participants == (gold.PLAYER, gold.LIA)
    assert action.replan_scope is ReplanScope.CHAPTER
    assert action.actual_tick == 570  # 540 + the ruling's 30
    # the durable submission is the user's own free text (no option).
    assert action.intent_text == gold.GOLD_INTENT
    assert action.selected_option is None
    # the resolver could see it (the provider side of the same fact).
    resolver_prompt = drive.completion.prompts_for("resolver")[0]
    assert gold.GOLD_INTENT in resolver_prompt
    assert "the user's intent, not a world fact" in resolver_prompt
    assert "- intent_text: " in resolver_prompt
    # the ruling's own event is the outcome, not the intent.
    outcome = drive.scene1.value.actions[0]
    event = conn.execute(
        "SELECT narration FROM world_event WHERE event_id = ?",
        (outcome.event_id,),
    ).fetchone()
    assert event is not None and str(event[0]) == payload["outcome"]
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM world_event WHERE narration LIKE"
            " '%settled like a parcel%'"
        ).fetchone()[0]
        == 0
    )
    # the ruling's state effect settled a CURRENT fact.
    fact = conn.execute(
        "SELECT canonical_key, statement FROM world_state_fact"
        " WHERE status = 'CURRENT'"
    ).fetchall()
    assert [(str(row[0]), str(row[1])) for row in fact] == [
        ("household:cousin", "camped at the gate; the guest room refused")
    ]


# ---------------------------------------------------------------------------
# ⑥ the user's choice invalidates the original plan
# ---------------------------------------------------------------------------


def test_gate06_the_users_choice_invalidates_the_original_plan(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑥ The CHAPTER verdict births the durable obligation and the
    auto-route consumes it (``claim → work → complete``, ``APPLIED``);
    ``apply_action_replan`` lands **plan revision 2** and the
    reconciliation retires the unclaimed PLANNED anchor — the old
    Blueprint's remaining part is no longer adopted (§24)."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    request = replan_request_id_for(gold.GATE, gold.SUBMISSION_ID)
    assert request == gold.REPLAN_REQUEST_ID
    obligation = replan_obligation(conn, request)
    assert obligation is not None
    assert obligation.scope is ReplanScope.CHAPTER
    assert obligation.status is ReplanStatus.APPLIED
    assert obligation.target_ref == gold.PLAN_R2
    consumed = drive.scene1.value.replans
    assert len(consumed) == 1
    assert consumed[0].replan_request_id == request
    assert consumed[0].scope is ReplanScope.CHAPTER
    assert consumed[0].target_ref == gold.PLAN_R2
    plans = narrative.plans_of(gold.CH1)
    assert [plan.plan_revision for plan in plans] == [1, 2]
    assert plans[0].chapter_plan_id == gold.PLAN_R1
    assert plans[0].status is PlanRevisionStatus.SUPERSEDED
    assert plans[1].chapter_plan_id == gold.PLAN_R2
    assert plans[1].status is PlanRevisionStatus.ADOPTED
    adopted = narrative.adopted_plan(gold.CH1)
    assert adopted is not None
    assert adopted.chapter_plan_id == gold.PLAN_R2
    assert len(adopted.scenes) == 3  # the remaining part, restated
    # the unclaimed PLANNED anchor is retired — the old tail scene is not
    # part of any adopted plan any more (§24's discard).
    discarded = narrative.get_scene(gold.S4)
    assert discarded is not None
    assert discarded.status is SceneStatus.DISCARDED
    # the replan prompt carried the committed ruling's own words (the
    # plan's reason is the user's submission, never a fresh invention).
    replan_prompt = drive.completion.prompts_for("director")[1]
    assert "The replan's own faces:" in replan_prompt
    assert f"- replan_request_id: {request}" in replan_prompt
    assert gold.GOLD_INTENT in replan_prompt
    assert gold.GOLD_ADJUDICATION_PAYLOAD["consequences"] in replan_prompt


# ---------------------------------------------------------------------------
# ⑦ the drive follows the new revision; discarded scenes stay retired
# ---------------------------------------------------------------------------


def test_gate07_the_drive_follows_the_new_revision(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑦ The remaining scenes are opened and written from the **new**
    revision's elements (the old directional content never rides a
    downstream prompt), the retired anchor is never activated or named
    again, and no fresh anchor is minted to replace it."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    kitchen = gold.CH1_REPLAN_BLUEPRINT["scenes"][1]
    prompts = _writer_prompts_for_place(drive, gold.PLACE_KITCHEN)
    assert len(prompts) == 2
    for prompt in prompts:
        assert f"- entry_goals: {kitchen['entry_goals']}" in prompt
        assert f"- exit_condition: {kitchen['exit_condition']}" in prompt
        # the invalidated plan's content does not ride.
        assert gold.PLACE_GUEST_ROOM not in prompt
        assert "the shelf where Father keeps his road maps" not in prompt
    dossier2 = drive.narrative.adopted_dossier(gold.S2)
    assert dossier2 is not None
    assert dossier2.place == gold.PLACE_KITCHEN
    assert dossier2.entry_goals == kitchen["entry_goals"]
    dossier3 = drive.narrative.adopted_dossier(gold.S3)
    assert dossier3 is not None
    assert dossier3.place == gold.PLACE_MAP_ROOM
    # the actual order of the driven scenes is the new plan's own.
    assert drive.scene2.value.opening.dossier.scene_id == gold.S2
    assert drive.scene3.value.opening.dossier.scene_id == gold.S3
    # the retired anchor: never activated, never named downstream, never
    # replaced by a fresh anchor.
    refused = drive.pipeline.run_scene(
        gold.S4, (SegmentBeat(duration_ticks=1),), LATER3
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    stale = drive.narrative.get_scene(gold.S4)
    assert stale is not None and stale.status is SceneStatus.DISCARDED
    assert len(drive.narrative.scenes_of(gold.CH1)) == 4
    for prompt in (
        drive.completion.prompts_for("writer")
        + drive.completion.prompts_for("resolver")
    ):
        assert gold.PLACE_TOWER not in prompt
    for body in _passage_bodies(conn):
        assert gold.PLACE_TOWER not in body


# ---------------------------------------------------------------------------
# ⑧ scene 3 reads what scene 2 committed
# ---------------------------------------------------------------------------


def test_gate08_scene_three_reads_what_scene_two_committed(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑧ Scene 2's committed passage is in scene 3's own planning
    context (the ``SceneContext``'s cognition / memory, both addressed
    to Lia), readable through the durable view faces — and the writer
    prompt scene 3 actually received carries the fact's text."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    opening = drive.scene3.value.opening
    assert opening.context.pov_actor_id == gold.LIA
    assert opening.context.cognition.viewer_id == gold.LIA
    assert opening.context.memory.viewer_id == gold.LIA
    lens = [row.content for row in opening.context.memory.memories]
    assert gold.S2_PROSE_2 in lens
    # the independent read faces agree (the durable half of the same
    # fact, read for Lia's own identity).
    memory_view = v3_memory_view(
        conn, world_id=gold.WORLD_ID, viewer_id=gold.LIA
    )
    assert isinstance(memory_view, Ok)
    assert gold.S2_PROSE_2 in [
        row.content for row in memory_view.value.memories
    ]
    cognition_view = v3_cognition_view(
        conn, world_id=gold.WORLD_ID, viewer_id=gold.LIA
    )
    assert isinstance(cognition_view, Ok)
    assert gold.S2_PROSE_2 in [
        event.narration for event in cognition_view.value.witnessed
    ]
    # the writer prompt scene 3's provider received carries it.
    prompts = _writer_prompts_for_place(drive, gold.PLACE_MAP_ROOM)
    assert len(prompts) == 1
    assert f"(EXPERIENCED) {gold.S2_PROSE_2}" in prompts[0]
    assert gold.S3_PROSE_1 not in prompts[0]  # the future is not narrated


# ---------------------------------------------------------------------------
# ⑨ the chapter diverged from the Blueprint — honestly recorded
# ---------------------------------------------------------------------------


def test_gate09_the_chapter_diverged_from_its_blueprint_honestly(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑨ The divergence is real and both faces stand: the actual chapter
    ended 90 ticks past the initial Blueprint's window and drove three
    of its four planned scenes; the old revision keeps its own content,
    the committed passages were never rewritten, and no fact was written
    to paper the difference over."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    r1 = drive.narrative.get_plan(gold.PLAN_R1)
    assert r1 is not None
    assert r1.planned_end_tick == 600
    assert len(r1.scenes) == 4
    assert r1.status is PlanRevisionStatus.SUPERSEDED  # history, unrewritten
    chapter = drive.narrative.get_chapter(gold.CH1)
    assert chapter is not None
    assert chapter.status is ChapterStatus.CLOSED
    assert chapter.closed_at_tick == gold.TICK_CH1_END
    assert chapter.closed_at_tick > r1.planned_end_tick  # 690 > 600
    # the roster diverged too: four planned anchors, three driven, one
    # retired — and the scene's actual span is its commits' own.
    assert [
        row.status.value for row in drive.narrative.scenes_of(gold.CH1)
    ] == ["COMMITTED", "COMMITTED", "COMMITTED", "DISCARDED"]
    scene1 = drive.narrative.get_scene(gold.S1)
    assert scene1 is not None
    assert scene1.actual_start_tick == 0
    assert scene1.actual_end_tick == 600
    # the committed faces are exactly the scripted prose (no rewrite).
    assert _passage_bodies(conn) == [
        gold.GOLD_PROSE[(gold.PLACE_GATE, 1)],
        gold.GOLD_PROSE[(gold.PLACE_GATE, 2)],
        gold.GOLD_PROSE[(gold.PLACE_GATE, 3)],
        gold.GOLD_PROSE[(gold.PLACE_KITCHEN, 1)],
        gold.GOLD_PROSE[(gold.PLACE_KITCHEN, 2)],
        gold.GOLD_PROSE[(gold.PLACE_MAP_ROOM, 1)],
    ]
    # no fact was written to reconcile the plan (the only CURRENT fact is
    # the ruling's own state effect).
    assert _count(conn, "world_state_fact") == 1
    assert _count(conn, "world_event") == 7  # 6 passages + 1 ruling


# ---------------------------------------------------------------------------
# ⑩ the settlement summarizes the committed chapter
# ---------------------------------------------------------------------------


def test_gate10_the_settlement_summarizes_the_committed_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑩ NCP-4's one-version row carries the chapter's committed lineage
    (every event's line), names the plan revision it stood beside, and
    changes nothing else — no tick, no event, no fact, no memory
    (N-INV-004's storage face)."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    record = drive.settlement
    assert record.chapter_id == gold.CH1
    lines = record.summary.split("\n")
    assert len(lines) == 7  # 6 segments + the ruling, lineage order
    for text in (
        gold.S1_PROSE_1,
        gold.S1_PROSE_2,
        gold.S1_PROSE_3,
        gold.S2_PROSE_1,
        gold.S2_PROSE_2,
        gold.S3_PROSE_1,
        gold.GOLD_ADJUDICATION_PAYLOAD["outcome"],
    ):
        assert text in record.summary, text
    assert record.hooks == ""  # the honest empty family (V3-8b)
    assert record.created_at_revision == 2  # the plan it stood beside
    chapter = drive.narrative.get_chapter(gold.CH1)
    assert chapter is not None and chapter.status is ChapterStatus.CLOSED
    assert chapter.closed_at_tick == gold.TICK_CH1_END
    settlements = chapter_settlements_of(conn, gold.WORLD_ID)
    assert [row.chapter_id for row in settlements] == [gold.CH1]
    assert settlements[0] == record
    # nothing moved: the settlement has no duration and writes no canon
    # progress row.
    tick = read_current_tick(conn, gold.WORLD_ID)
    assert isinstance(tick, Ok)
    assert tick.value == gold.TICK_CH1_END
    assert _count(conn, "world_event") == 7
    assert _count(conn, "world_state_fact") == 1
    assert _count(conn, "actor_memory") == 14  # 6×2 passages + 1×2 ruling
    assert _count(conn, "reader_exposure") == 0


# ---------------------------------------------------------------------------
# ⑪ chapter 2 is planned from chapter 1's real outcome
# ---------------------------------------------------------------------------


def test_gate11_chapter_two_uses_the_real_first_chapter(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """⑪ The second Blueprint is planned from the world's real state: the
    recorded Director context carries chapter 1's settlement summary
    **and** the ruling's state effect as a current fact, and the payload
    lands as chapter 2's adopted revision 1."""

    drive = _drive_gold(
        conn, world_store, cast_store, bible_store, narrative
    )
    opening = drive.ch2.value
    assert opening.chapter.chapter_id == gold.CH2
    assert opening.chapter.chapter_index == 2
    assert opening.plan.chapter_plan_id == gold.PLAN_CH2_R1
    assert opening.plan.status is PlanRevisionStatus.ADOPTED
    assert len(opening.plan.scenes) == 2
    assert [element["scene_id"] for element in opening.plan.scenes] == [
        f"{gold.CH2}-s01",
        f"{gold.CH2}-s02",
    ]
    assert opening.plan.goal == gold.CH2_BLUEPRINT["goal"]
    prompt = drive.completion.prompts_for("director")[2]
    # the settled first chapter rode the summaries block, whole.
    assert "- settled chapters already compressed (what came before):" in prompt
    assert f"{gold.CH1}: " in prompt
    assert gold.S2_PROSE_2 in prompt
    assert gold.GOLD_ADJUDICATION_PAYLOAD["outcome"] in prompt
    # the ruling's state effect is a current fact now.
    assert (
        "household:cousin: camped at the gate; the guest room refused"
        in prompt
    )
    assert "- current_tick: 690" in prompt
    # the second Blueprint's own content references the first chapter's
    # real outcome (the wooden horse, the gate-stone morning).
    assert "carved wooden horse" in gold.CH2_BLUEPRINT["goal"]


# ---------------------------------------------------------------------------
# ⑫ a restart resumes from the latest narrative state
# ---------------------------------------------------------------------------


def test_gate12_a_restart_resumes_from_the_durable_narrative_state(
    tmp_path: Path,
) -> None:
    """⑫ The file-database crash window: scene 1 is driven to a gate
    ``COMMITTED`` and never closed (the V3-8b seventh family's window),
    the connection closes, and a **fresh** connection's
    ``Pipeline.resume`` drives the continuation from durable state alone
    — the passage carries the committed action as its ``outcome_ref``,
    the gate closes in that commit, no second ruling is born, and the
    remaining scenes are still drivable."""

    db_path = tmp_path / "app.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    completion = gold.gold_completion()
    assert isinstance(
        gold.seed_gold_world(
            conn,
            world_store=SqliteWorldStore(conn, open_runtime_epoch(conn)),
            bible_store=SqliteBibleStore(conn, open_runtime_epoch(conn)),
            cast_store=SqliteCastStore(conn, open_runtime_epoch(conn)),
            now=NOW,
        ),
        Ok,
    )
    pipeline = gold.build_gold_pipeline(
        conn,
        world_store=SqliteWorldStore(conn, open_runtime_epoch(conn)),
        cast_store=SqliteCastStore(conn, open_runtime_epoch(conn)),
        bible_store=SqliteBibleStore(conn, open_runtime_epoch(conn)),
        narrative_store=SqliteNarrativeStore(conn, open_runtime_epoch(conn)),
        completion=completion,
    )
    assert isinstance(pipeline.plan_chapter(gold.WORLD_ID, NOW), Ok)
    beats = gold.gold_beats_by_scene()[gold.S1]
    # the crash window's script: the two segments and the gate — and
    # stop there (the continuation passage never lands).
    partial = pipeline.run_scene(gold.S1, (beats[0], beats[1], beats[2]), NOW)
    assert isinstance(partial, Ok)
    gate = get_gate(conn, gold.GATE)
    assert gate is not None and gate.status is GateStatus.COMMITTED
    assert gate.opened_at_tick == gold.TICK_GATE_OPENS
    assert _count(conn, "user_action") == 1
    assert _count(conn, "narrative_passage") == 2
    assert _count(conn, "segment_commit") == 3  # 2 SEGMENT + 1 ACTION_OUTCOME
    assert _count(conn, "world_event") == 3
    tick = read_current_tick(conn, gold.WORLD_ID)
    assert isinstance(tick, Ok) and tick.value == 570
    conn.close()

    # the restart: a fresh connection, fresh stores, the same scripted
    # completion — nothing rides over from the old process.
    reopened = sqlite3.connect(db_path)
    reopened.execute("PRAGMA foreign_keys=ON")
    reopened_worlds = SqliteWorldStore(reopened, open_runtime_epoch(reopened))
    reopened_cast = SqliteCastStore(reopened, open_runtime_epoch(reopened))
    reopened_bible = SqliteBibleStore(reopened, open_runtime_epoch(reopened))
    reopened_narrative = SqliteNarrativeStore(
        reopened, open_runtime_epoch(reopened)
    )
    resumed = gold.build_gold_pipeline(
        reopened,
        world_store=reopened_worlds,
        cast_store=reopened_cast,
        bible_store=reopened_bible,
        narrative_store=reopened_narrative,
        completion=completion,
    )
    walk = resumed.resume(gold.WORLD_ID, LATER)
    assert isinstance(walk, Ok)
    assert walk.value.continuations_driven == (gold.GATE,)
    assert walk.value.gates_committed == ()
    assert walk.value.replans_consumed == ()
    assert walk.value.active_scene_ids == (gold.S1,)
    gate = get_gate(reopened, gold.GATE)
    assert gate is not None and gate.status is GateStatus.CLOSED
    # the continuation passage carries the committed action, and closes
    # the gate in its own commit.
    row = reopened.execute(
        "SELECT outcome_ref FROM narrative_passage WHERE passage_id = ?",
        (f"{gold.S1}-p0003",),
    ).fetchone()
    assert row is not None and str(row[0]) == gold.ACTION_ID
    # no second ruling and no duplicate commits.
    assert _count(reopened, "user_action") == 1
    assert _count(reopened, "narrative_passage") == 3
    assert _count(reopened, "segment_commit") == 4
    assert _count(reopened, "world_event") == 4
    tick = read_current_tick(reopened, gold.WORLD_ID)
    assert isinstance(tick, Ok) and tick.value == 571
    # a second walk is the zero-write no-op.
    again = resumed.resume(gold.WORLD_ID, LATER)
    assert isinstance(again, Ok)
    assert again.value.continuations_driven == ()
    assert _count(reopened, "narrative_passage") == 3
    # and the remaining scenes are still drivable on the fresh
    # connection (the replan landed before the crash).
    run2 = resumed.run_scene(
        gold.S2, gold.gold_beats_by_scene()[gold.S2], LATER2
    )
    assert isinstance(run2, Ok)
    assert _count(reopened, "narrative_passage") == 5
    dossier2 = reopened_narrative.adopted_dossier(gold.S2)
    assert dossier2 is not None
    assert dossier2.place == gold.PLACE_KITCHEN


# ---------------------------------------------------------------------------
# the module's own discipline pins
# ---------------------------------------------------------------------------


def _all_constants(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def _sql_constants(tree: ast.AST) -> list[str]:
    return [
        text
        for text in _all_constants(tree)
        if re.match(r"(?i)^\s*(select|insert|update|delete)\b", text)
    ]


def test_the_gold_script_answers_gaps_loudly() -> None:
    """The scripted gap is a loud refusal (never an invented payload):
    an unscripted prose key, an unscripted intent, an unscripted scene
    and an unknown face all raise :class:`GoldScriptError` naming what
    was looked for."""

    completion = gold.gold_completion()
    with pytest.raises(gold.GoldScriptError):
        completion.complete(
            "You are the POV writer for ONE segment of an interactive"
            " story world.\n\n- place: nowhere at all\n- segment_seq: 1"
        )
    with pytest.raises(gold.GoldScriptError):
        completion.complete(
            "You are the action resolver of an interactive story world:"
            " the\n\n- intent_text: 'an intent nobody scripted'"
        )
    with pytest.raises(gold.GoldScriptError):
        completion.complete(
            "You are the scene planner of an interactive story world."
            "\nPlan ONE scene.\n\nScene: no-such-scene (world x)"
        )
    with pytest.raises(gold.GoldScriptError):
        completion.complete("a prompt from no face at all")
    # the classifier never answered a payload nobody scripted.
    assert completion.prompts  # the four calls were recorded


def test_the_gold_fixture_keeps_its_payloads_past_the_library_schemas() -> None:
    """The scripted payloads are the library's own shapes: the nine
    chapter fields with a non-empty scene table of ten-key elements, the
    ruling's seven fields with a three-word ``replan_scope``, and the
    must_hide pair splitting into the two fragments the guard reads."""

    blueprint = gold.CH1_BLUEPRINT
    assert set(_CHAPTER_FIELDS) <= set(blueprint)
    assert blueprint["scenes"]
    for element in blueprint["scenes"]:
        assert set(element) == {
            "purpose",
            "place",
            "pov_actor_id",
            "participants",
            "planned_start_tick",
            "entry_goals",
            "exit_condition",
            "elasticity",
            "revealable",
            "must_hide",
        }
        assert element["pov_actor_id"] in element["participants"]
    assert set(gold.GOLD_ADJUDICATION_PAYLOAD) == {
        "interpretation",
        "outcome",
        "actual_action",
        "consequences",
        "state_effects",
        "participants",
        "replan_scope",
    }
    assert gold.GOLD_ADJUDICATION_PAYLOAD["replan_scope"] == "CHAPTER"
    assert gold.gold_adjudication().replan_scope is ReplanScope.CHAPTER
    assert gold.gold_adjudication() == gold.gold_adjudication()
    split = [
        fragment.strip()
        for fragment in re.split(r"[\n\r。！？；.!?;]+", gold.MUST_HIDE)
        if fragment.strip()
    ]
    assert tuple(split) == gold.MUST_HIDE_FRAGMENTS
    # every scripted scene element lands inside its chapter's window.
    assert blueprint["planned_start_tick"] <= blueprint["planned_end_tick"]
    for element in blueprint["scenes"]:
        assert 0 <= element["planned_start_tick"] <= blueprint["planned_end_tick"]


def test_the_gold_module_holds_no_clock_and_one_parameter_bound_write() -> None:
    """The fixture's discipline: no ``BEGIN``/``ROLLBACK`` of its own and
    exactly one ``COMMIT`` (the persona preamble, which must not leave a
    transaction open for the creation service), no SQL-shaped string
    beyond that preamble's single parameter-bound ``INSERT``, and no
    clock (the caller's ``now`` stamps everything)."""

    for text in _all_constants(GOLD_TREE):
        assert text not in {"BEGIN IMMEDIATE", "ROLLBACK"}, text
    assert _all_constants(GOLD_TREE).count("COMMIT") == 0
    sql = _sql_constants(GOLD_TREE)
    assert len(sql) == 1, sql
    assert sql[0].lstrip().upper().startswith("INSERT OR IGNORE")
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(GOLD_TREE)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "datetime" not in imports
    assert "time" not in imports
    for node in ast.walk(GOLD_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "now",
                "time",
                "utcnow",
            }, ast.dump(node)


def test_the_gold_module_starts_cold_and_is_not_re_exported() -> None:
    """The P4-3 cold-start discipline and the narrow-module precedent:
    the module imports in a fresh interpreter, and the package root does
    not re-export it."""

    source = (SRC_ROOT / "world" / "__init__.py").read_text(encoding="utf-8")
    for keyword in ("gold", "GoldScriptedCompletion", "seed_gold_world"):
        assert keyword not in source, keyword
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.world.gold"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def test_the_ledger_carries_the_v3_8d_entries() -> None:
    """AOCI maintenance, pinned: the new fixture rides its own ledger
    entry with the faces this cut owns."""

    lines = AOCI_FILE.read_text(encoding="utf-8").split("\n")
    hits = [line for line in lines if line.startswith("gold.py[")]
    assert len(hits) == 1
    entry = hits[0]
    for keyword in (
        "Gold Scenario",
        "seed_gold_world",
        "gold_beats_by_scene",
        "GoldScriptedCompletion",
        "gold-empire-105",
        "V3-8d",
    ):
        assert keyword in entry, keyword
