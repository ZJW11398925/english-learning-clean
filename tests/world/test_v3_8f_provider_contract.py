"""V3-8f — the provider-contract fixes behind the real-model wiring
baseline (TASK-OPI-c0f4d9b4…12 / the opening ruling
``DEC-OPI-c0f4d9b4…10``; the paradigm shift §10.4).

**Why these pins exist, stated honestly.** The V3-8e acceptance run with
a real credential failed before it could even flow: the Director arm's
answer carried JSON **arrays** in fields the schema names as single
strings (``chapter_questions_to_advance``, a scene's ``entry_goals`` /
``revealable`` / ``must_hide``), and the strict parser refused
``bad-shape``. The two-sided fix this suite pins:

1. the **value-type contract** — the three JSON-answering arms
   (Director / Planner / Resolver) state the per-field JSON value types
   verbatim (one shared ``_PROSE_TYPE_SENTENCE`` plus the per-field
   lines); the Writer arm answers prose, not JSON, and does not carry
   it;
2. the **tolerance arm** — a text field answered as a JSON array of
   strings is joined deterministically (``"\\n".join``, the same
   newline the ``must_hide`` fragment law splits on), an empty array is
   the honest empty string, and nothing else about the strictness moves
   (a non-string item, a number, an object, an array tick, an int
   participant stay ``bad-shape``);
3. the **relayed seam codes** — ``_seam_code`` passes the persona
   adapter's short vocabulary through (``timeout`` / ``http-<status>``
   / ``missing-secret`` / …) and flattens free text (spaces, newlines,
   case, length) to ``transport-error``; the arm-level refusal carries
   the relayed code and never the prompt;
4. the **real-model products** — two trimmed fixtures excerpted
   verbatim from the V3-8f probe run (one real credential,
   2026-10-13; ``tests/world/data/v3_8f_director_resp_*.json``): the
   array form parses through the tolerant join, the typed form passes
   strictly (every text field is a string in the fixture itself, so the
   strict path is demonstrably the one taken).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from elc.world.action import ReplanScope
from elc.world.cognition import V3CognitionView
from elc.world.director import DirectorCastInput, DirectorContext
from elc.world.llm_providers import (
    _IDENTITY_SENTENCE,
    _PROSE_TYPE_SENTENCE,
    CompletionOutcome,
    LlmDirectorProvider,
    LlmPlannerProvider,
    LlmProviderError,
    LlmResolverProvider,
    LlmWriterProvider,
    _parse_blueprint,
    _seam_code,
    _text,
    _tick,
    _words,
)
from elc.world.memory import V3MemoryView
from elc.world.providers import (
    DirectorPlanContext,
    PovContext,
    ResolverContext,
    ScenePlanContext,
)
from elc.world.types import StateEffect

FIXTURE_DIR = Path(__file__).resolve().parent / "data"

TOWN = "world-town"
SCENE = "world-town-ch01-s01"
GATE = "world-town-ch01-s01-g01"
ACTOR = "lia"
INTENT = "I hold the ledger and say nothing."


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


def _empty_cognition(viewer: str = ACTOR) -> V3CognitionView:
    return V3CognitionView(viewer_id=viewer, public=(), witnessed=())


def _empty_memory(viewer: str = ACTOR) -> V3MemoryView:
    return V3MemoryView(viewer_id=viewer, memories=())


def _pov_context() -> PovContext:
    return PovContext(
        scene_id=SCENE,
        segment_seq=1,
        pov_actor_id=ACTOR,
        participants=(ACTOR,),
        place="the doorway",
        entry_goals="greet the newcomer",
        exit_condition="the greeting lands or breaks",
        revealable="the ledger's back page",
        must_hide="the priced tools",
        current_tick=0,
        cognition=_empty_cognition(),
        memory=_empty_memory(),
    )


def _planner_context() -> ScenePlanContext:
    return ScenePlanContext(
        world_id=TOWN,
        scene_id=SCENE,
        pov_actor_id=ACTOR,
        current_tick=3,
        element=None,
        cognition=_empty_cognition(),
        memory=_empty_memory(),
    )


def _director_context() -> DirectorPlanContext:
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
    )


def _resolver_context() -> ResolverContext:
    return ResolverContext(
        gate_id=GATE,
        scene_id=SCENE,
        submission_id="sub-1",
        intent_text=INTENT,
        selected_option=None,
        options=("hold the ledger", "step back"),
        bible=None,
        current_facts=(),
        player_character=None,
        place="the doorway",
        participants=(ACTOR,),
        counterparts=(),
        player_cognition=None,
        player_memory=None,
        pov_actor_id=ACTOR,
        cognition=_empty_cognition(),
        memory=_empty_memory(),
        current_tick=3,
    )


def _element_payload() -> dict[str, Any]:
    return {
        "pov_actor_id": ACTOR,
        "participants": [ACTOR],
        "planned_start_tick": 0,
        "place": "the doorway",
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "short",
        "revealable": "the ledger's back page",
        "must_hide": "the priced tools",
    }


def _blueprint_payload() -> dict[str, Any]:
    scene = dict(_element_payload())
    scene["purpose"] = "first sight"
    return {
        "goal": "the newcomer and the shopkeeper truly meet",
        "dramatic_question": "Will the shop's silence open to a stranger?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the first hard frost presses the order book",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "a repair job, maybe",
        "chapter_questions_to_advance": "who is the letter from?",
        "scenes": [scene],
    }


def _adjudication_payload() -> dict[str, Any]:
    return {
        "interpretation": "You mean to help rather than to buy.",
        "outcome": "Lia lets you hold the ledger; the ice thins.",
        "actual_action": "you carry the ledger to the counter",
        "consequences": "the shop's silence opens one notch",
        "state_effects": [
            {"key": "trust:lia", "statement": "warmed by one notch"}
        ],
        "participants": [ACTOR],
        "replan_scope": "NONE",
    }


# ---------------------------------------------------------------------------
# 1. the value-type contract (prompt face)
# ---------------------------------------------------------------------------


def test_the_three_json_arms_state_the_value_type_contract() -> None:
    """Director / Planner / Resolver each carry the module's one
    ``_PROSE_TYPE_SENTENCE`` verbatim (once) and name the JSON type of
    every field the strict parser checks — ``participants`` as an array,
    ticks as integers, the prose fields as ONE string."""

    planner_stub = _ScriptedCompletion(_answer(_element_payload()))
    LlmPlannerProvider(planner_stub).plan_scene(_planner_context())
    director_stub = _ScriptedCompletion(_answer(_blueprint_payload()))
    LlmDirectorProvider(director_stub).draft_blueprint(_director_context())
    resolver_stub = _ScriptedCompletion(_answer(_adjudication_payload()))
    LlmResolverProvider(resolver_stub).adjudicate(_resolver_context())

    for stub in (planner_stub, director_stub, resolver_stub):
        prompt = stub.prompts[0]
        assert prompt.count(_PROSE_TYPE_SENTENCE) == 1
        for expected in (
            "ONE JSON string",
            "never an array",
            "write them into that one string separated by newlines",
            "JSON arrays",
            "JSON integers",
        ):
            assert expected in prompt, (expected, prompt[:200])

    planner_prompt = planner_stub.prompts[0]
    for expected in (
        '"pov_actor_id": one JSON string',
        '"participants": a JSON array of participant identity strings',
        '"planned_start_tick": one JSON integer',
        '"must_hide": one JSON string',
    ):
        assert expected in planner_prompt, expected

    director_prompt = director_stub.prompts[0]
    for expected in (
        '"goal": one JSON string',
        '"soft_outcomes": one JSON string',
        '"scenes": a non-empty array of scene elements',
        "participants is a JSON array of participant identity strings;",
        "planned_start_tick is one JSON integer.",
    ):
        assert expected in director_prompt, expected

    resolver_prompt = resolver_stub.prompts[0]
    for expected in (
        '"interpretation": one JSON string',
        '"consequences": one JSON string',
        '"state_effects": a JSON array',
        '"replan_scope": exactly one of "NONE" | "SCENE" | "CHAPTER"',
    ):
        assert expected in resolver_prompt, expected


def test_the_writer_arm_does_not_carry_the_json_type_contract() -> None:
    """The Writer arm answers prose, not JSON: it carries neither the
    type sentence nor any JSON-value wording — and its own face (the
    POV discretion rules) rides untouched."""

    stub = _ScriptedCompletion(
        CompletionOutcome(text="The bell above the door answers first.")
    )
    body = LlmWriterProvider(stub).write_segment(_pov_context())
    assert body == "The bell above the door answers first."
    prompt = stub.prompts[0]
    assert _PROSE_TYPE_SENTENCE not in prompt
    assert "Value types:" not in prompt
    assert "ONE JSON string" not in prompt
    assert "one JSON object" not in prompt
    assert "Write the segment's prose in English" in prompt
    assert "the user's own will is not yours to invent" in prompt


def test_the_three_json_arms_state_the_identity_vocabulary_contract() -> None:
    """The fifth face the V3-8f smoke run exposed (same family as the
    type contract): the prompts render a participant as ``id (name)``,
    and a real Resolver answered the rendered composite straight back.
    The three JSON arms state the bare-id rule verbatim (once each); the
    Writer arm does not carry it."""

    planner_stub = _ScriptedCompletion(_answer(_element_payload()))
    LlmPlannerProvider(planner_stub).plan_scene(_planner_context())
    director_stub = _ScriptedCompletion(_answer(_blueprint_payload()))
    LlmDirectorProvider(director_stub).draft_blueprint(_director_context())
    resolver_stub = _ScriptedCompletion(_answer(_adjudication_payload()))
    LlmResolverProvider(resolver_stub).adjudicate(_resolver_context())

    for stub in (planner_stub, director_stub, resolver_stub):
        prompt = stub.prompts[0]
        assert prompt.count(_IDENTITY_SENTENCE) == 1
        for expected in (
            "bare id token",
            "the part before any parenthesis",
            "Never answer the rendered display form",
            "the identity string is the id alone",
        ):
            assert expected in prompt, (expected, prompt[:200])

    writer_stub = _ScriptedCompletion(CompletionOutcome(text="prose."))
    LlmWriterProvider(writer_stub).write_segment(_pov_context())
    assert _IDENTITY_SENTENCE not in writer_stub.prompts[0]


def test_the_live_composite_identity_parses_but_the_prompt_warns() -> None:
    """The smoke run's own product, pinned: the real Resolver answered
    ``"cousin (Renn)"`` — the rendered composite of the player's bare id
    (``cousin``) and the display name (``Renn``). The parse layer
    blesses only the shape (the string stays; the namespace refusal is
    the drive's, the V3-3R freeze), so the fix belongs to the prompt —
    where the identity contract now rides out."""

    payload = _adjudication_payload()
    payload["participants"] = ["cousin (Renn)"]
    stub = _ScriptedCompletion(_answer(payload))
    ruling = LlmResolverProvider(stub).adjudicate(_resolver_context())
    assert ruling.participants == ("cousin (Renn)",)
    assert _IDENTITY_SENTENCE in stub.prompts[0]


# ---------------------------------------------------------------------------
# 2. the tolerance arm (the deterministic join, and nothing more)
# ---------------------------------------------------------------------------


def test_the_text_tolerance_joins_string_arrays_and_only_those() -> None:
    """``_text``: a string is itself; an array of strings joins with the
    newline the ``must_hide`` fragment law splits on; an empty array is
    the honest empty string; anything else is still ``bad-shape``."""

    assert _text({"f": "one"}, "f") == "one"
    assert _text({"f": ["a", "b", "c"]}, "f") == "a\nb\nc"
    assert _text({"f": []}, "f") == ""
    for bad in (
        ["a", 7],
        [1, 2],
        [{"k": "v"}],
        [None],
        [["nested"]],
        7,
        {"k": "v"},
        True,
        None,
    ):
        with pytest.raises(LlmProviderError) as refused:
            _text({"f": bad}, "f")
        assert refused.value.reason == "bad-shape", bad
    with pytest.raises(LlmProviderError) as refused:
        _text({}, "f")
    assert refused.value.reason == "missing-field:f"


def test_the_tolerance_stops_at_the_non_text_fields() -> None:
    """The words and tick readers are untouched by the tolerance: an
    array of identities is an array (never a joined string), a string
    where an array belongs is ``bad-shape``, and a tick stays an
    integer (an array tick, a word or a bool all refuse)."""

    assert _words({"p": ["a", "b"]}, "p") == ("a", "b")
    assert _words({"p": []}, "p") == ()
    for bad in ("a", b"a", [1], [["a"]], {"a": 1}, 7, None):
        with pytest.raises(LlmProviderError) as refused:
            _words({"p": bad}, "p")
        assert refused.value.reason == "bad-shape", bad
    assert _tick({"t": 7}, "t") == 7
    for bad in ([1, 2], "soon", True, None):
        with pytest.raises(LlmProviderError) as refused:
            _tick({"t": bad}, "t")
        assert refused.value.reason == "bad-shape", bad


def test_the_element_parse_joins_prose_arrays_and_keeps_the_rest_strict() -> None:
    """The Planner arm end to end: a prose field answered as an array of
    strings lands joined in the canonical nine-key shape; the same
    payload's typed fields keep the strict refusal."""

    payload = _element_payload()
    payload["must_hide"] = ["the priced tools", "the second secret"]
    payload["entry_goals"] = []
    payload["participants"] = [ACTOR]
    parsed = LlmPlannerProvider(
        _ScriptedCompletion(_answer(payload))
    ).plan_scene(_planner_context())
    assert parsed["must_hide"] == "the priced tools\nthe second secret"
    assert parsed["entry_goals"] == ""
    assert parsed["participants"] == (ACTOR,)

    bad_tick = _element_payload()
    bad_tick["planned_start_tick"] = [0, 300]
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(_answer(bad_tick))
        ).plan_scene(_planner_context())
    assert refused.value.reason == "bad-shape"

    bad_words = _element_payload()
    bad_words["participants"] = ["a", 3]
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(_answer(bad_words))
        ).plan_scene(_planner_context())
    assert refused.value.reason == "bad-shape"


def test_the_resolver_parse_joins_prose_arrays_and_keeps_the_rest_strict() -> None:
    """The Resolver arm: prose answers (including a nested
    ``state_effects`` field) join; the verdict's typed fields — the
    participants table and the three-word ``replan_scope`` — keep every
    strict refusal."""

    payload = _adjudication_payload()
    payload["consequences"] = ["the ice thins", "the door clicks shut"]
    payload["state_effects"] = [
        {"key": "trust:lia", "statement": ["warmed", "once"]}
    ]
    ruling = LlmResolverProvider(
        _ScriptedCompletion(_answer(payload))
    ).adjudicate(_resolver_context())
    assert ruling.consequences == "the ice thins\nthe door clicks shut"
    assert ruling.state_effects == (
        StateEffect(key="trust:lia", statement="warmed\nonce"),
    )
    assert ruling.replan_scope is ReplanScope.NONE

    bad_words = _adjudication_payload()
    bad_words["participants"] = [1, 2]
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(
            _ScriptedCompletion(_answer(bad_words))
        ).adjudicate(_resolver_context())
    assert refused.value.reason == "bad-shape"

    bad_scope = _adjudication_payload()
    bad_scope["replan_scope"] = "LATER"
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(
            _ScriptedCompletion(_answer(bad_scope))
        ).adjudicate(_resolver_context())
    assert refused.value.reason == "bad-shape"


# ---------------------------------------------------------------------------
# 3. the relayed seam codes
# ---------------------------------------------------------------------------


def test_the_seam_code_relays_the_vocabulary_and_flattens_free_text() -> None:
    """``_seam_code``: the persona adapter's short vocabulary passes
    through unchanged; anything that could echo a prompt (spaces,
    newlines, case, an over-long word, an empty string) is flattened to
    ``transport-error``."""

    for code in (
        "timeout",
        "http-401",
        "http-429",
        "http-500",
        "missing-secret",
        "not-configured",
        "no-egress",
        "key-echo",
        "cleartext-http",
        "bad-json",
        "response-too-large",
        "transport-error",
        "bad-shape",
    ):
        assert _seam_code(code) == code, code
    for text in (
        "stub exploded while reading the prompt",
        "line\nbreak",
        "UPPER-CASE",
        "x" * 65,
        "",
        " leading",
        "trailing ",
        "http 500",
        "401",
        "http_500",
        "有中文",
    ):
        assert _seam_code(text) == "transport-error", text


def test_the_arm_refusal_carries_the_relayed_code_and_not_the_prompt() -> None:
    """The arm-level posture: a seam ``error`` reaches
    ``LlmProviderError.reason`` as the relayed code (a timeout is a
    timeout), the message stays the code alone, and a free-text seam
    error — the hostile-double case — flattens so the prompt never
    rides into a reason."""

    sentinel = "SENTINEL-PROMPT-CONTENT"
    stub = _ScriptedCompletion(CompletionOutcome(text=None, error="timeout"))
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(stub).adjudicate(_resolver_context())
    assert refused.value.reason == "timeout"
    assert str(refused.value) == "timeout"
    assert len(stub.prompts) == 1  # the prompt went out; the refusal silent
    assert sentinel not in str(refused.value)

    noisy = _ScriptedCompletion(
        CompletionOutcome(text=None, error=f"boom {sentinel}")
    )
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(noisy).adjudicate(_resolver_context())
    assert refused.value.reason == "transport-error"
    assert sentinel not in str(refused.value)

    http_refusal = _ScriptedCompletion(
        CompletionOutcome(text=None, error="http-503")
    )
    with pytest.raises(LlmProviderError) as refused:
        LlmWriterProvider(http_refusal).write_segment(_pov_context())
    assert refused.value.reason == "http-503"


# ---------------------------------------------------------------------------
# 4. the real-model products (trimmed verbatim fixtures)
# ---------------------------------------------------------------------------


def _fixture(name: str) -> tuple[str, dict[str, Any]]:
    text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    return text, json.loads(text)


#: Every prose field of a chapter payload, then every prose field of one
#: scene element (the typed form's own shape).
CHAPTER_TEXT_KEYS = (
    "goal",
    "dramatic_question",
    "closing_pressure",
    "desired_development",
    "soft_outcomes",
    "chapter_questions_to_advance",
)
ELEMENT_TEXT_KEYS = (
    "purpose",
    "place",
    "pov_actor_id",
    "entry_goals",
    "exit_condition",
    "elasticity",
    "revealable",
    "must_hide",
)


def test_the_real_array_form_blueprint_parses_through_the_tolerant_join() -> None:
    """The first real Director answer (array form): the fixture itself
    carries the plural prose fields as JSON arrays — the shape the
    strict parser refused — and the parse now lands every field in the
    canonical string form, joined on the newline the fragment law
    splits on."""

    text, fixture = _fixture("v3_8f_director_resp_array.json")
    assert isinstance(fixture["chapter_questions_to_advance"], list)
    for scene in fixture["scenes"]:
        assert isinstance(scene["entry_goals"], list)
        assert isinstance(scene["revealable"], list)
        assert isinstance(scene["must_hide"], list)
    parsed = _parse_blueprint(text)
    joined = "\n".join(fixture["chapter_questions_to_advance"])
    assert parsed["chapter_questions_to_advance"] == joined
    assert "\n" in joined
    for key in CHAPTER_TEXT_KEYS[:-1]:
        assert parsed[key] == fixture[key], key
    assert parsed["planned_start_tick"] == fixture["planned_start_tick"]
    assert parsed["planned_end_tick"] == fixture["planned_end_tick"]
    for index, scene in enumerate(fixture["scenes"]):
        element = parsed["scenes"][index]
        for key in ELEMENT_TEXT_KEYS:
            value = scene[key]
            expected = value if isinstance(value, str) else "\n".join(value)
            assert element[key] == expected, (index, key)
        assert element["participants"] == tuple(scene["participants"])
        assert element["planned_start_tick"] == scene["planned_start_tick"]
    # the joined prose splits back into the model's own items — the
    # writer's prohibition list reads the fragments one by one.
    joined_hidden = parsed["scenes"][1]["must_hide"]
    assert joined_hidden.split("\n") == fixture["scenes"][1]["must_hide"]


def test_the_real_typed_form_passes_strictly() -> None:
    """The second real Director answer (typed form): every prose field
    is a string in the fixture itself, so the parse demonstrably takes
    the strict path — and lands byte-equal to what the model answered."""

    text, fixture = _fixture("v3_8f_director_resp_typed.json")
    for key in CHAPTER_TEXT_KEYS:
        assert isinstance(fixture[key], str), key
    for scene in fixture["scenes"]:
        for key in ELEMENT_TEXT_KEYS:
            assert isinstance(scene[key], str), (key, scene[key])
        assert isinstance(scene["participants"], list)
        assert not isinstance(scene["planned_start_tick"], bool)
        assert isinstance(scene["planned_start_tick"], int)
    parsed = _parse_blueprint(text)
    for key in CHAPTER_TEXT_KEYS:
        assert parsed[key] == fixture[key], key
    assert parsed["planned_start_tick"] == fixture["planned_start_tick"]
    assert parsed["planned_end_tick"] == fixture["planned_end_tick"]
    for index, scene in enumerate(fixture["scenes"]):
        element = parsed["scenes"][index]
        for key in ELEMENT_TEXT_KEYS:
            assert element[key] == scene[key], (index, key)
        assert element["participants"] == tuple(scene["participants"])
    # the typed multi-item string really is the newline-joined form (the
    # contract's own shape, not two schemas).
    assert "\n" in parsed["chapter_questions_to_advance"]
    assert parsed["chapter_questions_to_advance"].count("\n") == 2
