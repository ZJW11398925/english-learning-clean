"""V3-8h — the author layer between chapters (the paradigm shift
§10.5 item 2) and the drive loop's pure faces (§10.5 item 1)
(TASK-OPI-c0f4d9b4…34 / the opening ruling ``DEC-OPI-c0f4d9b4…32``).

Pinned here (the reading-face behavior rides
``tests/host/test_v3_8h_reader_loop.py``; this module holds the pure
contract):

1. the ``next_chapter`` grammar — an absent / empty body is the old
   meaning (``None``), a non-empty string rides, anything else (a
   non-object, a blank or non-string word, an extra key) is the 400
   人话;
2. the soft-expectation prompt block — the direction is quoted into
   the Director's **initial** plan prompt with the wording law stated
   verbatim (「朝哪里压」 pressure, never a postcondition, never an
   invented story fact), in the prompt's own language (en and zh
   each); the CHAPTER replan arm never carries it; a blank direction
   carries nothing;
3. the no-direction path is byte for byte today's prompt (the
   空方向路径与今日逐字等义 pin — a rendered initial prompt with
   ``author_direction=None`` equals the pre-V3-8h rendering);
4. ``Pipeline.plan_chapter`` passes ``author_direction`` through to
   the ``DirectorPlanContext`` the Director provider actually
   receives (the recorded fake context carries the word), and the
   default ``None`` leaves every existing call site's shape;
5. the ceiling sentence — the reasoned stop's own words
   (「本次已连写 N 段……点「继续」接上」) with both numbers in place.

Every prompt pin rides the real ``LlmDirectorProvider.draft_blueprint``
execution arm (the stub records the prompt the provider actually
built) — no pin reads a private function's return in place of the
driven path (the V3-8e F2 anti-vacuum law).
"""

from __future__ import annotations

import json
from typing import Any

from elc.narrative_web import (
    V3_NEXT_CHAPTER_GRAMMAR,
    _ceiling_sentence,
    v3_next_chapter_request,
)
from elc.world.director import DirectorCastInput, DirectorContext
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmDirectorProvider,
)
from elc.world.providers import DirectorPlanContext

TOWN = "world-town"
ACTOR = "lia"
DIRECTION = "让莉亚主动追查信件"


class _ScriptedCompletion:
    """A deterministic ``TextCompletion`` stub: answers its scripted
    outcomes in call order and records every prompt it received."""

    def __init__(self, *answers: CompletionOutcome) -> None:
        self._answers = list(answers)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> CompletionOutcome:
        self.prompts.append(prompt)
        if not self._answers:
            raise AssertionError("the completion script is exhausted")
        return self._answers.pop(0)


def _answer(payload: dict[str, Any]) -> CompletionOutcome:
    return CompletionOutcome(
        text=json.dumps(payload, ensure_ascii=False), error=None
    )


def _blueprint_payload() -> dict[str, Any]:
    return {
        "goal": "the newcomer and the shopkeeper truly meet",
        "dramatic_question": "Will the shop's silence open to a stranger?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the first hard frost presses the order book",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "a repair job, maybe",
        "chapter_questions_to_advance": "who is the letter from?",
        "scenes": [
            {
                "purpose": "first sight",
                "place": "the doorway",
                "pov_actor_id": ACTOR,
                "participants": [ACTOR],
                "planned_start_tick": 0,
                "entry_goals": "greet the newcomer",
                "exit_condition": "the greeting lands or breaks",
                "elasticity": "the greeting may fail",
                "revealable": "the ledger's back page",
                "must_hide": "the priced tools",
            }
        ],
    }


def _plan_context(
    *, author_direction: str | None = None
) -> DirectorPlanContext:
    """The initial planning arm's context — no chapter, no trigger, the
    optional author-layer word."""

    return DirectorPlanContext(
        director_context=DirectorContext(
            world_id=TOWN,
            bible=None,
            cast=DirectorCastInput(
                members=(),
                player_character=None,
                namespace=frozenset(),
            ),
            storylines=(),
            current_facts=(),
            current_tick=0,
            chapter_summaries=(),
        ),
        chapter_id=None,
        replan_request_id=None,
        trigger=None,
        blueprint=None,
        author_direction=author_direction,
    )


def _replan_context(
    *, author_direction: str | None = None
) -> DirectorPlanContext:
    """The CHAPTER replan arm's context — the direction is present (as
    a caller could mistakenly hand it) and the arm must still ignore
    it."""

    return DirectorPlanContext(
        director_context=_plan_context().director_context,
        chapter_id=f"{TOWN}-ch01",
        replan_request_id=f"rp:{TOWN}-ch01-s01-g01:a",
        trigger=None,
        blueprint={"goal": "current"},
        author_direction=author_direction,
    )


def _draft_prompt(
    context: DirectorPlanContext, *, language: str = "en"
) -> str:
    """One real ``draft_blueprint`` execution over the stub — the prompt
    the provider actually built (the pin's execution arm)."""

    stub = _ScriptedCompletion(_answer(_blueprint_payload()))
    LlmDirectorProvider(stub, language=language).draft_blueprint(context)
    assert len(stub.prompts) == 1
    return stub.prompts[0]


def _replan_prompt(
    context: DirectorPlanContext, *, language: str = "en"
) -> str:
    """One real ``replan_blueprint`` execution over the stub — the
    CHAPTER replan arm's own prompt."""

    stub = _ScriptedCompletion(_answer(_blueprint_payload()))
    LlmDirectorProvider(stub, language=language).replan_blueprint(context)
    assert len(stub.prompts) == 1
    return stub.prompts[0]


# ---------------------------------------------------------------------------
# 1. the next_chapter grammar (fail-closed, old meaning compatible)
# ---------------------------------------------------------------------------


def test_the_next_chapter_grammar_keeps_the_old_meaning_and_is_fail_closed() -> (
    None
):
    """No body / ``{}`` answers ``(None, None)`` — the world develops on
    its own, byte for byte yesterday's call; exactly one non-empty
    string ``direction`` rides; every other shape is the 400 人话."""

    assert v3_next_chapter_request(None) == (None, None)
    assert v3_next_chapter_request({}) == (None, None)
    assert v3_next_chapter_request({"direction": DIRECTION}) == (
        None,
        DIRECTION,
    )
    for bad in (
        "direction",
        42,
        [],
        {"direction": ""},
        {"direction": "   "},
        {"direction": 7},
        {"direction": None},
        {"direction": DIRECTION, "extra": 1},
        {"text": DIRECTION},
    ):
        error, word = v3_next_chapter_request(bad)
        assert error == V3_NEXT_CHAPTER_GRAMMAR, bad
        assert word is None, bad
    assert "direction" in V3_NEXT_CHAPTER_GRAMMAR


# ---------------------------------------------------------------------------
# 2. the soft-expectation prompt block (en / zh, initial arm only)
# ---------------------------------------------------------------------------


def test_the_direction_rides_the_initial_prompt_with_the_wording_law() -> (
    None
):
    """The direction is quoted verbatim beside the wording law's three
    clauses — pressure (「朝哪里压」), never a postcondition, never an
    invented story fact — and the law rides in the prompt's own
    language."""

    en = _draft_prompt(_plan_context(author_direction=DIRECTION))
    assert DIRECTION in en
    assert "soft" in en and "expectation" in en
    assert "PRESS toward" in en
    assert "never as a postcondition" in en
    assert "never invent story facts on the reader's behalf" in en
    # the block sits on the initial arm with the world reading after it.
    assert en.index(DIRECTION) < en.index("The world you plan for:")


def test_the_direction_block_has_its_zh_wording() -> None:
    """At ``zh`` the same block speaks Chinese — the wording law's own
    words (「朝哪里压」/ postcondition / 发明剧情事实) and the quoted
    direction."""

    zh = _draft_prompt(
        _plan_context(author_direction=DIRECTION), language="zh"
    )
    assert DIRECTION in zh
    assert "软期望" in zh
    assert "朝哪里压" in zh
    assert "postcondition" in zh
    assert "不得替读者发明剧情事实" in zh
    assert "The reader's author-layer direction" not in zh


def test_the_replan_arm_never_carries_the_direction() -> None:
    """A CHAPTER replan's reason is the committed ruling alone: the
    direction field rides the context (a caller's mistake at worst) and
    the replan prompt stays free of it — no soft-expectation block at
    all."""

    prompt = _replan_prompt(_replan_context(author_direction=DIRECTION))
    assert DIRECTION not in prompt
    assert "author-layer" not in prompt
    # the replan's own faces are still there.
    assert "The replan's own faces:" in prompt


def test_a_blank_direction_carries_no_block() -> None:
    """A blank (whitespace-only) direction is no direction: the prompt
    carries no block — and a padded word is stripped to its text."""

    blank = _draft_prompt(_plan_context(author_direction="   "))
    assert "author-layer" not in blank
    padded = _draft_prompt(_plan_context(author_direction=f"  {DIRECTION} "))
    assert DIRECTION in padded


# ---------------------------------------------------------------------------
# 3. the no-direction prompt is byte for byte today's
# ---------------------------------------------------------------------------


def test_the_no_direction_prompt_is_byte_for_byte_today_s() -> None:
    """``author_direction=None`` renders exactly the prompt this face
    always rendered — the empty-direction path (the route's old
    meaning) is a byte-equal no-op on the prompt face. The equality is
    structural: the prompt with the field absent equals the same
    prompt built by the pre-V3-8h construction (five fields, no
    direction), and neither carries the block."""

    absent = _draft_prompt(_plan_context())
    explicit_none = _draft_prompt(
        DirectorPlanContext(
            director_context=_plan_context().director_context,
            chapter_id=None,
            replan_request_id=None,
            trigger=None,
            blueprint=None,
        )
    )
    assert absent == explicit_none
    assert "author-layer" not in absent
    assert DIRECTION not in absent


# ---------------------------------------------------------------------------
# 4. the pipeline pass-through
# ---------------------------------------------------------------------------


def test_the_pipeline_passes_the_direction_to_the_director_prompt(
    tmp_path: Any,
) -> None:
    """``Pipeline.plan_chapter(…, author_direction=…)`` rides the real
    chain: the Director prompt the gold pipeline actually builds carries
    the direction (the soft-expectation block) — and, on a fresh gold
    world planned without a direction, the prompt carries none (the
    default call's shape is unchanged). The gold completion records
    every prompt the real ``LlmDirectorProvider`` built, so the pin sits
    on the true execution arm."""

    import sqlite3

    from elc.platform.db.epoch import RuntimeEpochFence
    from elc.platform.db.migrations import apply_migrations
    from elc.world import gold
    from elc.world.bible import SqliteBibleStore
    from elc.world.cast import SqliteCastStore
    from elc.world.narrative import SqliteNarrativeStore
    from elc.world.store import SqliteWorldStore

    def _fresh_gold(app_db: Any) -> tuple[Any, Any]:
        """One seeded gold world and its real pipeline over the
        recording completion (the pass-through pin's execution arm)."""

        connection = sqlite3.connect(app_db)
        apply_migrations(connection)
        fence = RuntimeEpochFence(current=0)
        worlds = SqliteWorldStore(connection, fence)
        casts = SqliteCastStore(connection, fence)
        bibles = SqliteBibleStore(connection, fence)
        narrative = SqliteNarrativeStore(connection, fence)
        created = gold.seed_gold_world(
            connection,
            world_store=worlds,
            bible_store=bibles,
            cast_store=casts,
            now="2026-10-13T00:00:00+00:00",
        )
        assert created.__class__.__name__ == "Ok"
        completion = gold.gold_completion()
        pipeline = gold.build_gold_pipeline(
            connection,
            world_store=worlds,
            cast_store=casts,
            bible_store=bibles,
            narrative_store=narrative,
            completion=completion,
        )
        return pipeline, completion

    # with the direction: the initial plan prompt quotes it.
    pipeline, completion = _fresh_gold(tmp_path / "directed.db")
    planned = pipeline.plan_chapter(
        gold.WORLD_ID,
        "2026-10-13T00:00:00+00:00",
        author_direction=DIRECTION,
    )
    assert planned.__class__.__name__ == "Ok"
    drafts = [
        prompt
        for prompt in completion.prompts_by_arm.get("director", [])
        if "The replan's own faces:" not in prompt
    ]
    assert len(drafts) == 1
    assert DIRECTION in drafts[0]
    assert "author-layer" in drafts[0]

    # without one: the prompt carries no block (yesterday's shape).
    pipeline_two, completion_two = _fresh_gold(tmp_path / "plain.db")
    planned_two = pipeline_two.plan_chapter(
        gold.WORLD_ID, "2026-10-13T00:00:00+00:00"
    )
    assert planned_two.__class__.__name__ == "Ok"
    drafts_two = [
        prompt
        for prompt in completion_two.prompts_by_arm.get("director", [])
        if "The replan's own faces:" not in prompt
    ]
    assert len(drafts_two) == 1
    assert "author-layer" not in drafts_two[0]
    assert DIRECTION not in drafts_two[0]


# ---------------------------------------------------------------------------
# 5. the ceiling sentence
# ---------------------------------------------------------------------------


def test_the_ceiling_sentence_carries_both_numbers_and_the_continuation() -> (
    None
):
    """The reasoned stop's own words: 「本次已连写 N 段（一次驱动最多
    M 段）——点「继续」接上。」 — the written count, the ceiling and the
    one-click continuation, verbatim."""

    sentence = _ceiling_sentence(12, 12)
    assert sentence == (
        "本次已连写 12 段（一次驱动最多 12 段）——点「继续」接上。"
    )
    assert "本次已连写 3 段" in _ceiling_sentence(3, 12)
