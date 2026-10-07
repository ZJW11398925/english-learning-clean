"""lr-1 — the narrator's stop contract and the letter-on-its-way fact
(DEC-OPI-c73dbff3…95, the natural-run chain's generation face).

The user's seventh direction retired the mechanical pipeline (one
letter, one world step, one immediate reply): the world keeps turning
and the *narrator* decides, in its own narrative terms, when the round
ends. The contract pins:

1. **the stop vocabulary** — the answer may carry
   ``{"stop": {"kind": <word>}}`` beside the beats: the three narrative
   signals (``letter_arrives`` — the letter arrived and was read, the
   round's natural end; ``she_thinks_of_you`` — a checkpoint;
   ``awaits_you`` — the world waits on the user) plus ``none`` (= keep
   going, normalized to ``None`` — the same as no key at all); a word
   outside the vocabulary, a non-object stop, a stop with extra or
   missing keys — each refuses the **whole batch** (the same-batch law:
   a bad stop refuses the narration it rode in on);
2. **the letter-on-its-way section** — with ``letter_elapsed_days`` the
   prompt names the letter's **journey only** (its existence, its
   elapsed days — 0 days, 1 day, 2 days) and **never one word of its
   contents** (WR-4's iron negative-control, DEC-…58, zero compromise);
   the arrival guidance is narrative, not a rule (no step count, no
   deadline anywhere in the prompt); ``None`` keeps the prompt byte for
   byte the pre-lr-1 text;
3. **the return shape** — the parsed value is now a three-tuple
   ``(beats, directions, stop)``; ``stop`` is ``None`` unless the
   answer declared a signal; the extractor stays untouched (the stop
   key is structure it never emits);
4. **the orchestration seam** — ``run_generated_step`` rides
   ``letter_elapsed_days`` into the prompt and hands the parsed signal
   to the caller through the ``on_stop`` seam (the verdict belongs to
   the chain loop, never to the step itself).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import (
    STOP_AWAITS_YOU,
    STOP_LETTER_ARRIVES,
    STOP_NONE,
    STOP_SHE_THINKS_OF_YOU,
    STOP_WORDS,
    StopSignal,
    WorldNarrator,
    build_narrator_prompt,
)
from elc.world.package import (
    WORLD_PACKAGE_VERSION,
    CastMember,
    SupplyDeclaration,
    WorldPackage,
)
from elc.world.store import SqliteWorldStore

NOW = "2026-10-08T00:00:00+00:00"
WORLD = "world-main"
CALENDAR_START = "2025-09-14"

#: The negative-control's own letter (WR-4): every line here must stay
#: out of every prompt this suite builds — the journey is narrated, the
#: contents never are.
LETTER = (
    "Dear Berrymoor,\n"
    "The lighthouse keeper is my uncle — please look in on him.\n"
    "- Ada"
)


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _package(world_id: str = WORLD) -> WorldPackage:
    return WorldPackage(
        world_id=world_id,
        name="Calendar",
        version=WORLD_PACKAGE_VERSION,
        calendar_start=CALENDAR_START,
        setting=(
            "Calendar is a small harbour town on a cold coast.",
            "The boats come in with the morning tide.",
        ),
        cast=(CastMember(persona_id="persona-nell", name="Nell Alder"),),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="declared-not-consumed"),
    )


def _seed_world(store: SqliteWorldStore, world_id: str = WORLD) -> None:
    assert store.create_world(world_id, "Calendar", None, NOW).value is not None


class _ScriptedNarrator:
    """A provider double: scripted outputs, one per call (the last
    repeats); the prompt texts it saw are the composition pins'
    reading instrument."""

    def __init__(self, *outputs: ProviderOutput | BaseException) -> None:
        self._outputs = outputs
        self._cursor = 0
        self.prompts: list[str] = []

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        entry = self._outputs[min(self._cursor, len(self._outputs) - 1)]
        self._cursor += 1
        if isinstance(entry, BaseException):
            raise entry
        return entry


def _beats_with(
    stop: str | None = None,
    **extra: object,
) -> str:
    """One legal batch, optionally carrying a stop object (and any
    extra top-level keys the shape law should refuse)."""

    payload: dict[str, object] = {
        "beats": [
            {
                "kind": "lamp-relit",
                "narration": "The lamp burned all night.",
                "days": 1,
            }
        ]
    }
    if stop is not None:
        payload["stop"] = {"kind": stop}
    payload.update(extra)
    return json.dumps(payload)


def _generate(text: str) -> object:
    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=text)))
    return narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )


def _refused(text: str) -> str:
    parsed = _generate(text)
    assert not isinstance(parsed, Ok), text
    assert isinstance(parsed.error.message, str)
    assert parsed.error.message.startswith("narrator refused:")
    return parsed.error.message


# ---------------------------------------------------------------------------
# 1 — the stop vocabulary (VAL ③'s contract face)
# ---------------------------------------------------------------------------


def test_the_three_signals_and_none_parse() -> None:
    """The vocabulary: the three narrative signals parse to their
    :class:`StopSignal`; an explicit ``none`` normalizes to ``None`` —
    keep going and no key at all are the same answer."""

    assert STOP_WORDS == (
        STOP_LETTER_ARRIVES,
        STOP_SHE_THINKS_OF_YOU,
        STOP_AWAITS_YOU,
        STOP_NONE,
    )
    for word in (STOP_LETTER_ARRIVES, STOP_SHE_THINKS_OF_YOU, STOP_AWAITS_YOU):
        parsed = _generate(_beats_with(stop=word))
        assert isinstance(parsed, Ok)
        beats, directions, stop = parsed.value
        assert isinstance(stop, StopSignal) and stop.kind == word
        assert directions == ()
        assert [beat.kind for beat in beats] == ["lamp-relit"]
    for shape in (_beats_with(stop=STOP_NONE), _beats_with()):
        parsed = _generate(shape)
        assert isinstance(parsed, Ok)
        _, _, stop = parsed.value
        assert stop is None


def test_a_stop_word_outside_the_vocabulary_refuses_the_whole_batch() -> None:
    """A stop word that is not one of the four refuses the **whole**
    batch — the well-formed beats it rode in on die with it (one
    answer, one fate)."""

    for word in ("she_leaves", "LETTER_ARRIVES", "letter_arrived", "", "停止"):
        message = _refused(_beats_with(stop=word))
        assert str(word) in message or word == "", word


def test_a_malformed_stop_object_refuses_the_whole_batch() -> None:
    """The stop must be exactly ``{"kind": <word>}``: a non-object, an
    extra key, a missing key, a non-string kind — each refuses the
    whole batch (the same-batch verification law wr-10 gave the
    candidates, lr-1 gives the signal)."""

    assert "not a JSON object" in _refused(
        json.dumps(
            {
                "beats": [
                    {
                        "kind": "lamp-relit",
                        "narration": "The lamp burned all night.",
                        "days": 1,
                    }
                ],
                "stop": "letter_arrives",
            }
        )
    )
    assert "exactly 'kind'" in _refused(
        json.dumps(
            {
                "beats": [
                    {
                        "kind": "lamp-relit",
                        "narration": "The lamp burned all night.",
                        "days": 1,
                    }
                ],
                "stop": {"kind": "letter_arrives", "when": "now"},
            }
        )
    )
    assert "exactly 'kind'" in _refused(
        json.dumps(
            {
                "beats": [
                    {
                        "kind": "lamp-relit",
                        "narration": "The lamp burned all night.",
                        "days": 1,
                    }
                ],
                "stop": {},
            }
        )
    )
    assert "not one of" in _refused(
        '{"beats": [{"kind": "a", "narration": "b", "days": 0}],'
        ' "stop": {"kind": 7}}'
    )


# ---------------------------------------------------------------------------
# 2 — the letter-on-its-way section (VAL ③'s world-inbound fact face)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "phrase"),
    ((0, "0 days ago"), (1, "1 day ago"), (3, "3 days ago")),
)
def test_the_section_names_the_journey_and_the_days_only(
    days: int, phrase: str
) -> None:
    """The prompt's letter section is a **world-inbound fact of the
    journey**: it states the letter exists and was sent ``n`` days ago
    — and never one word of what it says (WR-4's iron negative-control:
    every line of the letter is absent, and the section says so in its
    own sentence)."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        letter_elapsed_days=days,
    )
    assert "== A letter on its way ==" in prompt
    assert (
        "A letter from the user's character is on its way to the cast"
        in prompt
    )
    assert f"it was sent {phrase}" in prompt
    assert "mark that beat's stop as letter_arrives" in prompt
    # The boundary sentence: the journey is the world's fact, the
    # contents never are.
    assert "never knows what the letter says" in prompt
    for line in LETTER.splitlines():
        assert line not in prompt
    assert "The letter ==" not in prompt
    assert "please look in on him" not in prompt


def test_the_natural_arrival_guidance_is_narrative_not_a_rule() -> None:
    """The guidance invites the letter to arrive **naturally** — and
    the negative-control holds: no step count, no deadline, no
    mechanical rule anywhere in the prompt (「必须在 N 步内」族零在场)."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        letter_elapsed_days=0,
    )
    assert "The world moves naturally" in prompt
    for banned in (
        "must arrive within",
        "within one step",
        "within two steps",
        "no more than",
        "exactly one step",
        "MAX_CHAIN_STEPS",
        "step limit",
        "steps",
    ):
        assert banned not in prompt


def test_none_elapsed_days_keeps_the_prompt_byte_identical() -> None:
    """The zero-change default: without ``letter_elapsed_days`` the
    prompt is byte for byte the pre-lr-1 text (the regression judgment
    face — the old call shapes compose the old prompt exactly).

    处置刀（评审 F-H1）：原钉是模块内自比——两侧同错恒绿，接不住
    形状行坏形；真对照与良构由下方两钉承担。"""

    old = build_narrator_prompt(_package(), (), (), "zh")
    new = build_narrator_prompt(
        _package(), (), (), "zh", letter_elapsed_days=None
    )
    assert old == new
    assert '"stop"' not in old
    directed_old = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        "directed",
    )
    directed_new = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        "directed",
        None,
        None,
    )
    assert directed_old == directed_new
    assert '"stop"' not in directed_old


def _shape_line(prompt: str) -> str:
    for line in prompt.split("\n\n"):
        if line.startswith("Answer with strict JSON"):
            return line
    raise AssertionError("shape line not found")


#: pre-lr-1 父提交（29bdf61）的形状行字面——真对照源（处置刀 F-H1）。
PARENT_IMMERSIVE_SHAPE = (
    "Answer with strict JSON only — no prose outside it:"
    ' {"beats": [{"kind": "<slug>", "narration": "<...>", "days": 0}]}'
    " The ``kind`` is a short slug: lowercase letters, digits and"
    " hyphens only, at most 32 characters."
)
PARENT_DIRECTED_SHAPE = (
    "Answer with strict JSON only — no prose outside it:"
    ' {"beats": [{"kind": "<slug>", "narration": "<...>",'
    ' "days": 0}], "directions": [{"label": "<short phrase>",'
    ' "hint": "<one sentence>"}]}'
    " The ``kind`` is a short slug: lowercase letters, digits"
    " and hyphens only, at most 32 characters."
)


def test_the_none_elapsed_shape_lines_match_the_parent_literals() -> None:
    """elapsed=None 两态的形状行 == 父提交字面（处置刀 F-H1 真对照——
    原自比钉对形状行坏形零捕获，本钉逐字对照父版良形）。"""

    immersive = _shape_line(
        build_narrator_prompt(_package(), (), (), "zh", letter_elapsed_days=None)
    )
    assert immersive == PARENT_IMMERSIVE_SHAPE
    directed = _shape_line(
        build_narrator_prompt(
            _package(), (), (), "zh", "directed", None, None
        )
    )
    assert directed == PARENT_DIRECTED_SHAPE


@pytest.mark.parametrize(
    "mode,elapsed",
    [
        ("immersive", None),
        ("immersive", 0),
        ("directed", None),
        ("directed", 0),
    ],
)
def test_every_shape_line_is_wellformed_json(
    mode: str, elapsed: int | None
) -> None:
    """四态良构（处置刀 F-H1）：形状行的 JSON 部分在占位符替换后
    ``json.loads`` 可解析——模板教形状，模板自身必须良构（三态坏形
    曾静默存活于自比钉之下）。"""

    prompt = build_narrator_prompt(
        _package(), (), (), "zh", mode, None, elapsed
    )
    line = _shape_line(prompt)
    depth = 0
    end: int | None = None
    for index, char in enumerate(line):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    assert end is not None, line
    filled = (
        line[line.index("{"):end]
        .replace("<slug>", "k")
        .replace("<...>", "t")
        .replace("<short phrase>", "L")
        .replace("<one sentence>", "H")
        .replace(
            "<letter_arrives|she_thinks_of_you|awaits_you|none>", "none"
        )
    )
    json.loads(filled)  # 坏形在此抛 ValueError


def test_letter_elapsed_days_validates() -> None:
    """The parameter's own grammar: a negative or non-int elapsed is a
    construction refusal (the journey cannot be negative; a float is
    not a day count)."""

    for bad in (-1, 1.5, "2", True):
        with pytest.raises(ValueError):
            build_narrator_prompt(
                _package(),
                (),
                (),
                "zh",
                letter_elapsed_days=bad,  # type: ignore[arg-type]
            )


def test_the_json_shape_line_widens_with_stop_only_when_a_letter_rides() -> None:
    """The shape line tells the model about the ``stop`` key — and its
    vocabulary — only when a letter is on its way; without one the
    shape line never mentions it."""

    with_letter = build_narrator_prompt(
        _package(), (), (), "zh", letter_elapsed_days=1
    )
    without = build_narrator_prompt(_package(), (), (), "zh")
    assert '"stop": {"kind": "<letter_arrives|she_thinks_of_you|awaits_you|none>"}' in (
        with_letter.replace(" , ", ', ')
    )
    assert '"stop"' not in without
    assert "keep going" in with_letter


def test_directed_and_the_letter_ride_together() -> None:
    """The directed shape composes with the letter-on-its-way shape:
    the candidates requirement and the stop vocabulary share the one
    answer's shape line."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        "directed",
        letter_elapsed_days=2,
    )
    assert '"directions"' in prompt
    assert '"stop"' in prompt
    assert "it was sent 2 days ago" in prompt
    # The old arms stay: the chosen-direction section is the director's
    # input, never a letter's.
    chosen = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        "directed",
        ("a storm rolls in", "The harbour braces for weather."),
        1,
    )
    assert "The user has chosen where the world goes next" in chosen
    assert "it was sent 1 day ago" in chosen


# ---------------------------------------------------------------------------
# 3 — the orchestration seam (VAL ⑥'s step-level face)
# ---------------------------------------------------------------------------


def test_the_step_rides_elapsed_days_and_hands_over_the_signal(
    store: SqliteWorldStore,
) -> None:
    """``run_generated_step`` passes ``letter_elapsed_days`` into the
    prompt (the section is there, the letter is not) and hands the
    parsed stop signal to the caller through ``on_stop`` — the step
    itself never branches on it (the chain loop's verdict, lr-4's full
    semantics)."""

    _seed_world(store)
    seen_stops: list[object] = []
    answer = _beats_with(stop=STOP_LETTER_ARRIVES)
    provider = _ScriptedNarrator(ProviderOutput(text=answer))
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        provider,
        "turn-lr1-1",
        NOW,
        letter_elapsed_days=1,
        on_stop=seen_stops.append,
    )
    assert isinstance(stepped, Ok)
    assert len(seen_stops) == 1
    signal = seen_stops[0]
    assert isinstance(signal, StopSignal) and signal.kind == STOP_LETTER_ARRIVES
    prompt = provider.prompts[0]
    assert "it was sent 1 day ago" in prompt
    for line in LETTER.splitlines():
        assert line not in prompt


def test_the_step_answers_none_signal_without_a_stop_key(
    store: SqliteWorldStore,
) -> None:
    """No stop key in the answer, no signal at the seam: the callback
    fires (the step landed beats) and carries ``None`` — keep going."""

    _seed_world(store)
    seen_stops: list[object] = []
    provider = _ScriptedNarrator(ProviderOutput(text=_beats_with()))
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        provider,
        "turn-lr1-2",
        NOW,
        letter_elapsed_days=0,
        on_stop=seen_stops.append,
    )
    assert isinstance(stepped, Ok)
    assert seen_stops == [None]
    assert "it was sent 0 days ago" in provider.prompts[0]
