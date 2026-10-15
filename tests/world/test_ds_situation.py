"""DS-3 面 A — the situation plan machine's own pins (the technical
definition §6: the four questions + the minimal field set; the old
blueprint machine retired from the /ds product path).

Pinned here:

1. the situation planner's prompt carries the four questions verbatim,
   the minimal fields and the structural ban (no 门拍 / user_present /
   literary structure) — 拔 ban 句即钉红（评审变异组「拔句」型的自证）;
2. the parser demands concrete answers: an empty answer, an unknown
   first speaker, a goalless protagonist or no world-event candidate is
   ``bad-shape`` — the machine-checkable 非空且具体 face;
3. ``plan_situation_chapter`` lands the document as the adopted plan
   (goal = ②, the element carrying the canonical ten beside the
   situation keys) and the scene anchor — the read face
   (:func:`elc.world.ds_situation.situation_face_of`) reads it back;
4. the landing is idempotent (a re-ask is the zero-write answer) and
   the residue law reuses a crashed open's chapter.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.director import Director
from elc.world.ds_opening import DS_WORLD_ID, seed_ds_world
from elc.world.ds_situation import (
    SITUATION_DOC_KEYS,
    plan_situation_chapter,
    situation_face_of,
)
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmProviderError,
    LlmSituationPlannerProvider,
    SituationPlanContext,
    _parse_situation_plan,
    _situation_plan_prompt,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.store import SqliteWorldStore

NOW = "2026-10-15T00:00:00+00:00"


def _situation_payload() -> str:
    return json.dumps(
        {
            "where_you_stand": (
                "the ferry house steps at lantern light, the town's"
                " question hanging on you"
            ),
            "place": "the ferry house steps",
            "what_presses_on_you": (
                "the county clerk arrives at dawn and the mark must"
                " have an answer — yours"
            ),
            "first_speaker": "bryn",
            "first_words": "The clerk comes at dawn. Was it there when"
                " you crossed?",
            "open_question": (
                "will your answer keep you out of the water gate"
            ),
            "world_event_candidates": [
                "the fog closes the crossing before dawn",
                "the clerk's boat is sighted an hour early",
            ],
            "protagonist_goals": {
                "bryn": "keep the ledger clean through the dawn",
                "corvin": "keep the water's secret one more night",
            },
            "pacing": "the pressure tightens with every hour of fog",
            "settlement_expectation": (
                "where the mark's answer has left you standing"
            ),
        },
        ensure_ascii=False,
    )


class ScriptedCompletion:
    """The offline seam, routed by the prompt's own family word."""

    def __init__(self, **queues: list[str]) -> None:
        self._queues = {kind: list(items) for kind, items in queues.items()}
        self.prompts: dict[str, list[str]] = {}

    def complete(self, prompt: str) -> CompletionOutcome:
        if "situation planner of a two-seat" in prompt:
            kind = "situation"
        elif "world director" in prompt:
            kind = "director"
        else:
            raise AssertionError("unknown prompt family")
        self.prompts.setdefault(kind, []).append(prompt)
        queue = self._queues.get(kind)
        if not queue:
            raise AssertionError(f"the {kind} script is exhausted")
        return CompletionOutcome(text=queue.pop(0), error=None)

    def count(self, kind: str) -> int:
        return len(self.prompts.get(kind, []))


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def stores(conn: sqlite3.Connection) -> tuple[
    SqliteWorldStore, SqliteCastStore, SqliteBibleStore, SqliteNarrativeStore
]:
    fence = open_runtime_epoch(conn)
    return (
        SqliteWorldStore(conn, fence),
        SqliteCastStore(conn, fence),
        SqliteBibleStore(conn, fence),
        SqliteNarrativeStore(conn, fence),
    )


@pytest.fixture()
def seeded(conn: sqlite3.Connection, stores: tuple) -> sqlite3.Connection:
    world_store, cast_store, bible_store, _narrative = stores
    created = seed_ds_world(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        now=NOW,
    )
    assert not isinstance(created, Err), (
        created.error if isinstance(created, Err) else ""
    )
    return conn


def _plan(
    conn: sqlite3.Connection,
    stores: tuple,
    completion: ScriptedCompletion,
):
    world_store, cast_store, bible_store, narrative = stores
    outcome = plan_situation_chapter(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        planner=LlmSituationPlannerProvider(completion),
        world_id=DS_WORLD_ID,
        now=NOW,
    )
    assert not isinstance(outcome, Err), (
        outcome.error if isinstance(outcome, Err) else ""
    )
    return outcome.value


# ---------------------------------------------------------------------------
# 1 — the prompt pins (the four questions + the ban)
# ---------------------------------------------------------------------------


def _context() -> SituationPlanContext:
    return SituationPlanContext(
        world_id=DS_WORLD_ID,
        chapter_index=1,
        current_tick=1310,
        premise="a ferry town in fog season",
        hard_rules="no boat crosses in fog",
        place="",
        recent_narration="",
        cast_members=(("bryn", "布丽恩·灰隼"), ("corvin", "科尔文")),
        player_id="chenyu",
        player_name="陈屿",
    )


def test_the_prompt_carries_the_four_questions_and_the_ban() -> None:
    prompt = _situation_plan_prompt(_context())
    # ①–④ verbatim keys + the minimal field set
    for key in (
        '"where_you_stand"',
        '"place"',
        '"what_presses_on_you"',
        '"first_speaker"',
        '"first_words"',
        '"open_question"',
        '"world_event_candidates"',
        '"protagonist_goals"',
        '"pacing"',
        '"settlement_expectation"',
    ):
        assert key in prompt, key
    # the identity vocabulary renders with display names
    assert "bryn (布丽恩·灰隼)" in prompt
    assert "chenyu" in prompt
    # the structural ban: no 门拍 / user_present / literary 章法
    assert "NO literary structure" in prompt
    assert "dramatic question" in prompt
    assert "user_present" in prompt
    # the author direction line rides only when present
    assert "author-layer" not in prompt
    with_direction = _situation_plan_prompt(
        SituationPlanContext(
            world_id=DS_WORLD_ID,
            chapter_index=2,
            current_tick=1400,
            premise="p",
            hard_rules="r",
            place="the steps",
            recent_narration="tail",
            cast_members=(("bryn", "布丽恩·灰隼"),),
            player_id="chenyu",
            player_name="陈屿",
            author_direction="let the mark fade",
        )
    )
    assert "let the mark fade" in with_direction
    assert "soft" in with_direction


def test_the_ban_sentence_is_load_bearing_mutation_preview() -> None:
    """变异预演（拔句→红）：the structural ban rides ONE constant —
    removing it redds the pin above; this test is the restore-side
    witness that the pin reads the constant, not a literal copy."""

    from elc.world.llm_providers import _SITUATION_BAN_SENTENCE

    assert "NO literary structure" in _SITUATION_BAN_SENTENCE["en"]
    assert "文学结构" in _SITUATION_BAN_SENTENCE["zh"]


# ---------------------------------------------------------------------------
# 2 — the parser's shape law (非空且具体)
# ---------------------------------------------------------------------------


def test_the_situation_parser_demands_concrete_answers() -> None:
    vocabulary = (("bryn", "布丽恩·灰隼"), ("corvin", "科尔文"))
    plan = _parse_situation_plan(_situation_payload(), vocabulary)
    assert plan.first_speaker == "bryn"
    assert plan.first_words.startswith("The clerk")
    assert len(plan.world_event_candidates) == 2
    assert dict(plan.protagonist_goals)["corvin"]

    # a rendered composite first_speaker normalizes to its bare id
    composite = _situation_payload().replace(
        '"first_speaker": "bryn"', '"first_speaker": "bryn (布丽恩·灰隼)"'
    )
    assert _parse_situation_plan(composite, vocabulary).first_speaker == (
        "bryn"
    )

    def _refused(payload: str) -> None:
        with pytest.raises(LlmProviderError, match="bad-shape"):
            _parse_situation_plan(payload, vocabulary)

    # an empty four-question answer is not a plan
    _refused(_situation_payload().replace(
        "will your answer keep you out of the water gate", "  "
    ))
    # an unknown first speaker is outside the vocabulary
    _refused(_situation_payload().replace('"bryn"', '"stranger"'))
    # a goalless protagonist is a hole in the plan
    _refused(_situation_payload().replace(
        '"corvin": "keep the water\'s secret one more night"',
        '"corvin": ""',
    ))
    # a candidate list with no live entry carries no pressure
    _refused(_situation_payload().replace(
        '"world_event_candidates": [',
        '"world_event_candidates": [""] , "_old": [',
    ))


# ---------------------------------------------------------------------------
# 3 — the landing (the adopted plan carries the document)
# ---------------------------------------------------------------------------


def test_plan_situation_chapter_lands_the_four_questions(
    seeded: sqlite3.Connection, stores: tuple
) -> None:
    completion = ScriptedCompletion(situation=[_situation_payload()])
    opening = _plan(seeded, stores, completion)
    chapter = opening.chapter
    assert chapter.status.value == "PLANNED"
    assert chapter.chapter_index == 1
    plan = opening.plan
    assert plan.status.value == "ADOPTED"
    # goal = ② (the chapter's pressure)
    assert plan.goal.startswith("the county clerk arrives")
    # the literary columns landed empty — the 章法 is not in storage
    assert plan.dramatic_question == ""
    assert plan.closing_pressure == ""
    # the element carries the canonical ten beside the situation keys
    element = plan.scenes[0]
    for key in (
        "purpose",
        "place",
        "pov_actor_id",
        "participants",
        "planned_start_tick",
        "entry_goals",
        "exit_condition",
        "elasticity",
    ):
        assert key in element, key
    for key in SITUATION_DOC_KEYS:
        assert key in element, key
    assert element["pov_actor_id"] == "chenyu"
    assert element["participants"] == ["chenyu", "bryn", "corvin"]
    # the read face reads the document back — 四问字段非空且具体
    doc = situation_face_of(plan)
    assert doc is not None
    for key in (
        "where_you_stand",
        "what_presses_on_you",
        "first_words",
        "open_question",
    ):
        assert isinstance(doc[key], str) and doc[key].strip(), key
    assert doc["first_speaker"] in {"bryn", "corvin"}
    assert opening.scene.status.value == "PLANNED"
    # the prompt asked the four questions of the scripted arm
    prompt = completion.prompts["situation"][0]
    assert '"what_presses_on_you"' in prompt


def test_the_landing_is_idempotent_and_reuses_residue(
    seeded: sqlite3.Connection, stores: tuple
) -> None:
    completion = ScriptedCompletion(
        situation=[_situation_payload()] * 2
    )
    first = _plan(seeded, stores, completion)
    assert not isinstance(first, Err)
    # a re-ask is the zero-write answer — no second call, no second plan
    second = _plan(seeded, stores, completion)
    assert not isinstance(second, Err)
    assert second.fresh_plan is False
    assert completion.count("situation") == 1
    assert second.plan.chapter_plan_id == first.plan.chapter_plan_id
    chapters = seeded.execute(
        "SELECT COUNT(*) FROM world_chapter WHERE world_id = ?",
        (DS_WORLD_ID,),
    ).fetchone()
    assert chapters[0] == 1

    # the residue law: a crashed open (PLANNED chapter, no plan) is
    # REUSED — the retry never skips the index
    seeded.execute(
        "DELETE FROM world_chapter_plan"
        " WHERE chapter_id = ?", (first.chapter.chapter_id,)
    )
    seeded.commit()
    third = _plan(seeded, stores, completion)
    assert not isinstance(third, Err)
    assert third.fresh_plan is True
    assert third.chapter.chapter_id == first.chapter.chapter_id
    assert completion.count("situation") == 2


# ---------------------------------------------------------------------------
# 4 — the engine still reads a situation-planned world (the seam)
# ---------------------------------------------------------------------------


def test_the_situation_plan_feeds_the_dispatch_chapter_goal(
    seeded: sqlite3.Connection, stores: tuple
) -> None:
    """§6's 验收面's storage half: the adopted plan's ``goal`` IS ②'s
    answer, so the drive half's ``chapter_goal`` read carries the
    pressure without any blueprint machine in the loop (面 B pins the
    dispatch prompt's plan block itself)."""

    completion = ScriptedCompletion(situation=[_situation_payload()])
    outcome = _plan(seeded, stores, completion)
    assert not isinstance(outcome, Err)
    world_store, cast_store, bible_store, narrative = stores
    director = Director(
        seeded,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )
    context = director.context(DS_WORLD_ID)
    assert context.bible is not None
    plan = narrative.adopted_plan(outcome.chapter.chapter_id)
    assert plan is not None
    assert plan.goal.startswith("the county clerk arrives")
    assert situation_face_of(plan) is not None
