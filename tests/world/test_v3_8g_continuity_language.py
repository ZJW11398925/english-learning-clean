"""V3-8g — the continuity law and the prose-language face on the real
providers (TASK-OPI-c0f4d9b4…24 / the opening ruling
``DEC-OPI-c0f4d9b4…22``; the paradigm shift §10.4 items 5 and 6).

**What this suite proves, stated honestly.**

1. **The continuity law** — the writer prompt carries
   :data:`~elc.world.llm_providers._CONTINUITY_SENTENCE` exactly once:
   the event lists are what has already happened *and has already been
   narrated*, the segment advances the story, never re-tells it, and a
   continuation resuming a ruling does the same. The behavioral arm
   builds a cognition view that already holds a narrated event and
   asserts the prompt carries both the event (the model sees the past)
   and the prohibition (the model is told not to transcribe it).
2. **The prose-language face** — all four arms render their language
   line from the ``language`` constructor word over the two-word
   vocabulary: ``en`` is the default and renders exactly today's
   sentences (the writer's line byte for byte), ``zh`` renders the
   Chinese line, and the JSON arms' keys / identities / enum are not
   language. An out-of-vocabulary word stays on the default face
   (documented: the reading face normalizes before constructing).

The real-model evidence (the continuation-similarity reading and the
zh body's non-ASCII share) is the V3-8g smoke run's own log
(``D:\\elc-scratch\\v38g\\smoke.log``), cited in the delivery report —
never in this suite (the V3-8f suite's own posture).
"""

from __future__ import annotations

import dataclasses

from elc.world.director import DirectorCastInput, DirectorContext
from elc.world.llm_providers import (
    _CONTINUITY_SENTENCE,
    _JSON_PROSE_LINE,
    _WRITER_PROSE_LINE,
    PROSE_LANGUAGE_DEFAULT,
    PROSE_LANGUAGE_WORDS,
    CompletionOutcome,
    LlmDirectorProvider,
    LlmPlannerProvider,
    LlmResolverProvider,
    LlmWriterProvider,
)
from elc.world.providers import DirectorPlanContext
from tests.world.test_v3_8c_llm_providers import (
    TOWN,
    _answer,
    _blueprint,
    _cognition,
    _element_payload,
    _pov_context,
    _resolver_context,
    _scene_plan_context,
    _ScriptedCompletion,
)

#: The writer's existing English sentence (V3-8c, byte for byte) — the
#: default face this cut must not move.
_WRITER_EN = "Write the segment's prose in English."


def _director_context() -> DirectorPlanContext:
    """A minimal world-authoritative Director input — the language
    line is the only face this suite reads, so an empty cast, no
    Bible and no facts are honest."""

    return DirectorPlanContext(
        director_context=DirectorContext(
            world_id=TOWN,
            bible=None,
            cast=DirectorCastInput(
                members=(), player_character=None, namespace=frozenset()
            ),
            storylines=(),
            current_facts=(),
            current_tick=3,
            chapter_summaries=(),
        ),
        chapter_id=None,
        replan_request_id=None,
        trigger=None,
        blueprint=None,
    )


# ---------------------------------------------------------------------------
# 1. the continuity law (V3-8g, §10.4 item 6)
# ---------------------------------------------------------------------------


def test_the_writer_prompt_carries_the_continuity_law_exactly_once() -> None:
    """The writer prompt states the continuity law verbatim, once: the
    event lists are already-narrated facts, the segment advances the
    story and never re-tells them, and a continuation does the same.
    The V3-8c faces ride untouched beside it (the POV rule, the
    user-will rule, the no-future rule, the ``must_hide``
    prohibitions)."""

    stub = _ScriptedCompletion(CompletionOutcome(text="Fresh prose."))
    LlmWriterProvider(stub).write_segment(_pov_context())
    prompt = stub.prompts[0]
    assert prompt.count(_CONTINUITY_SENTENCE) == 1
    # the law's own clauses ride the sentence (each one load-bearing:
    # the past is already-narrated fact, the segment advances, a
    # continuation obeys the same law).
    for clause in (
        "have already happened",
        "already been narrated",
        "never repeat, restate or transcribe",
        "Write what happens next",
        "for a continuation, the",
    ):
        assert clause in _CONTINUITY_SENTENCE, clause
        assert clause in prompt, clause
    # the existing faces are not weakened by the addition.
    for expected in (
        "One main point of view",
        "the user's own will is not yours to invent",
        "never narrate the",
        "  - the priced tools",
    ):
        assert expected in prompt, expected


def test_the_continuity_law_rides_the_prompt_that_carries_the_past() -> None:
    """The behavioral arm: a POV whose cognition already holds a
    narrated event gets a prompt that both shows the event (the model
    must know the past) and forbids transcribing it (the law) — the
    field failure was a model copying that very line back out."""

    past = "The bell above the door answers first; she looks up."
    stub = _ScriptedCompletion(CompletionOutcome(text="The glass steadies."))
    LlmWriterProvider(stub).write_segment(
        _pov_context(cognition=_cognition(past))
    )
    prompt = stub.prompts[0]
    assert f"(witnessed) {past}" in prompt  # the past is on the list
    assert _CONTINUITY_SENTENCE in prompt  # and the law governs it
    assert prompt.count(_CONTINUITY_SENTENCE) == 1


# ---------------------------------------------------------------------------
# 2. the prose-language face (V3-8g, §10.4 item 5)
# ---------------------------------------------------------------------------


def test_the_language_vocabulary_and_the_default_face() -> None:
    """The vocabulary is the two words; the default is ``en``; the
    default constructor renders the existing English sentences — the
    writer's byte for byte — and the zh word renders the Chinese
    line, never both."""

    assert PROSE_LANGUAGE_WORDS == ("en", "zh")
    assert PROSE_LANGUAGE_DEFAULT == "en"
    assert _WRITER_PROSE_LINE["en"] == _WRITER_EN
    assert "中文" in _WRITER_PROSE_LINE["zh"]
    assert "中文" in _JSON_PROSE_LINE["zh"]
    assert "English" in _JSON_PROSE_LINE["en"]

    default_stub = _ScriptedCompletion(CompletionOutcome(text="prose"))
    LlmWriterProvider(default_stub).write_segment(_pov_context())
    en_stub = _ScriptedCompletion(CompletionOutcome(text="prose"))
    LlmWriterProvider(en_stub, language="en").write_segment(_pov_context())
    # the default path is byte-identical to the explicit en path.
    assert default_stub.prompts[0] == en_stub.prompts[0]
    en_prompt = default_stub.prompts[0]
    assert _WRITER_EN in en_prompt
    assert _WRITER_PROSE_LINE["zh"] not in en_prompt

    zh_stub = _ScriptedCompletion(CompletionOutcome(text="正文"))
    LlmWriterProvider(zh_stub, language="zh").write_segment(_pov_context())
    zh_prompt = zh_stub.prompts[0]
    assert _WRITER_PROSE_LINE["zh"] in zh_prompt
    assert _WRITER_EN not in zh_prompt
    # the instruction frame and the continuity law ride both languages.
    assert "One main point of view" in zh_prompt
    assert _CONTINUITY_SENTENCE in zh_prompt


def test_the_json_arms_render_their_language_line_from_the_word() -> None:
    """Planner / Director / Resolver: the language line follows the
    constructor word (en at the default, zh at the switch), exactly
    once per prompt; the schema's own sentences, the identity contract
    and the enum stay put."""

    planner_en = _ScriptedCompletion(_answer(_element_payload()))
    LlmPlannerProvider(planner_en).plan_scene(_scene_plan_context())
    planner_zh = _ScriptedCompletion(_answer(_element_payload()))
    LlmPlannerProvider(planner_zh, language="zh").plan_scene(
        _scene_plan_context()
    )

    director_en = _ScriptedCompletion(_answer(_blueprint()))
    LlmDirectorProvider(director_en).draft_blueprint(_director_context())
    director_zh = _ScriptedCompletion(_answer(_blueprint()))
    LlmDirectorProvider(director_zh, language="zh").draft_blueprint(
        _director_context()
    )

    resolver_en = _ScriptedCompletion(
        _answer(
            {
                "interpretation": "i",
                "outcome": "o",
                "actual_action": "a",
                "consequences": "c",
                "state_effects": [],
                "participants": [],
                "replan_scope": "NONE",
            }
        )
    )
    LlmResolverProvider(resolver_en).adjudicate(_resolver_context())
    resolver_zh = _ScriptedCompletion(
        _answer(
            {
                "interpretation": "i",
                "outcome": "o",
                "actual_action": "a",
                "consequences": "c",
                "state_effects": [],
                "participants": [],
                "replan_scope": "NONE",
            }
        )
    )
    LlmResolverProvider(resolver_zh, language="zh").adjudicate(
        _resolver_context()
    )

    for en_stub, zh_stub in (
        (planner_en, planner_zh),
        (director_en, director_zh),
        (resolver_en, resolver_zh),
    ):
        en_prompt = en_stub.prompts[0]
        zh_prompt = zh_stub.prompts[0]
        assert en_prompt.count(_JSON_PROSE_LINE["en"]) == 1
        assert _JSON_PROSE_LINE["zh"] not in en_prompt
        assert zh_prompt.count(_JSON_PROSE_LINE["zh"]) == 1
        assert _JSON_PROSE_LINE["en"] not in zh_prompt
        # the schema stays language-free: the type sentence and the
        # identity contract ride both words untouched.
        assert "ONE JSON string" in en_prompt and "ONE JSON string" in zh_prompt
        assert "Identity strings:" in en_prompt and "Identity strings:" in zh_prompt


def test_a_word_outside_the_vocabulary_stays_on_the_default_face() -> None:
    """The documented fallback: an unknown word is a caller's bug (the
    reading face normalizes before constructing) and renders the
    default face — never a crash, never a third dialect."""

    stub = _ScriptedCompletion(CompletionOutcome(text="prose"))
    LlmWriterProvider(stub, language="fr").write_segment(_pov_context())
    assert _WRITER_EN in stub.prompts[0]
    assert _WRITER_PROSE_LINE["zh"] not in stub.prompts[0]


def test_the_writer_replan_and_replan_arms_keep_their_language_word() -> None:
    """The replan arms of the planner ride the same word (the shared
    prompt bodies take ``language``), so a replan written mid-switch
    stays in the switched language."""

    element = {
        "pov_actor_id": "actor-lia",
        "participants": ["actor-lia", "pc-you"],
        "planned_start_tick": 0,
        "place": "the counter",
        "entry_goals": "let the ledger speak",
        "exit_condition": "the ledger is set down",
        "elasticity": "short",
        "revealable": "the ledger's back page",
        "must_hide": "the names on the last page",
    }
    context = dataclasses.replace(_scene_plan_context(), element=element)
    stub = _ScriptedCompletion(_answer(element))
    LlmPlannerProvider(stub, language="zh").replan_element(context)
    prompt = stub.prompts[0]
    assert _JSON_PROSE_LINE["zh"] in prompt
    assert "must be revised" in prompt  # the replan face rides too
