"""wr-10 — the direction channel's first production face
(DEC-OPI-c73dbff3…64: 契约顺带生成 — the candidates ride the narrator's
one answer; the pending choice rides its own prompt section).

The pin groups:

1. **the contract** — the strict parser accepts the directed shape
   (beats beside two through four candidates) and both immersive
   shapes (no key, an empty array); the whole-batch law covers the
   candidates with the beats (a count of 1, a count of 5, a blank
   label, a blank hint, an extra field, a non-array — each refuses the
   whole answer, the narration included);
2. **the prompt** — directed mode carries the candidates requirement
   and the widened JSON line; immersive mode carries neither (the
   pre-wr-10 text, byte for byte — the zero-change default); the
   pending choice rides its own section; **the letter still never
   enters** (WR-4's law with the director's input present);
3. **the extractor** — the streamed preview emits the narrations only:
   label and hint text never leave through it (the wr-7 machine reads
   one key, unchanged);
4. **the seam** — ``run_generated_step`` passes the mode and the
   pending choice through (the scripted prompt proves it) and hands
   the parsed candidates to ``on_directions`` only past the quiet
   arms; the defaults run the step exactly as before wr-10.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.persona.types import ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err, Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import (
    DIRECTION_DIRECTED,
    MAX_DIRECTIONS,
    MIN_DIRECTIONS,
    DirectionCandidate,
    NarrationExtractor,
    WorldNarrator,
    build_narrator_prompt,
)
from elc.world.store import SqliteWorldStore
from tests.world.test_wr2_narrator import (
    BEATS_ONE,
    NOW,
    WORLD,
    _beat,
    _beats,
    _package,
    _ScriptedNarrator,
    _seed_world,
)

#: The directed answer's candidate trio (the parser pins' own cargo).
_CANDIDATES = (
    {"label": "a storm rolls in", "hint": "The harbour braces for weather."},
    {"label": "the fair arrives", "hint": "Tents dot the cliff meadow."},
    {
        "label": "the keeper travels",
        "hint": "The lighthouse goes dark for a night.",
    },
)


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection (the wr2 fixture
    shape — spelled here because fixtures do not import)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _directed_answer(candidates: tuple[dict[str, str], ...]) -> str:
    """One directed answer: the beats batch plus the candidates."""

    return json.dumps(
        {
            "beats": [
                {
                    "kind": "quiet-morning",
                    "narration": "The harbour kept its silence.",
                    "days": 0,
                }
            ],
            "directions": list(candidates),
        }
    )


# ---------------------------------------------------------------------------
# 1 — the contract (the strict parser, whole batch or nothing)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", (2, 3, 4))
def test_a_directed_answer_parses_beats_and_candidates(count: int) -> None:
    """The directed shape parses: the beats ride value[0] and the
    candidates ride value[1] verbatim — at every legal count from the
    two-candidate floor through the four ceiling."""

    pool = list(_CANDIDATES) + [
        {"label": f"extra candidate {i}", "hint": f"The world might {i}."}
        for i in range(count)
    ]
    candidates = tuple(pool[:count])
    narrator = WorldNarrator(
        _ScriptedNarrator(ProviderOutput(text=_directed_answer(candidates)))
    )
    parsed = narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
        direction_mode=DIRECTION_DIRECTED,
    )
    assert isinstance(parsed, Ok)
    # lr-1（DEC-OPI-c73dbff3…95）：返回形扩 = (beats, directions, stop)
    # 三元组——无 stop 键的答案 stop 恒 None（继续）。
    beats, directions, stop = parsed.value
    assert stop is None
    assert [beat.kind for beat in beats] == ["quiet-morning"]
    assert directions == tuple(
        DirectionCandidate(label=c["label"], hint=c["hint"])
        for c in candidates
    )


@pytest.mark.parametrize("shape", ("no-key", "empty-array"))
def test_both_immersive_shapes_parse_with_no_candidates(shape: str) -> None:
    """The immersive shapes are legal with zero candidates: no
    ``directions`` key at all, or the explicit empty array — each
    answers ``(beats, ())``."""

    if shape == "no-key":
        text = BEATS_ONE
    else:
        text = json.dumps(
            {
                "beats": [
                    {
                        "kind": "lamp-relit",
                        "narration": "The lamp burned all night.",
                        "days": 1,
                    }
                ],
                "directions": [],
            }
        )
    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=text)))
    parsed = narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(parsed, Ok)
    assert parsed.value[1] == ()


@pytest.mark.parametrize(
    ("answer", "why"),
    (
        (
            _directed_answer(
                ({"label": "only one", "hint": "A single candidate."},)
            ),
            "count 1 is not a choice",
        ),
        (
            _directed_answer(
                tuple(
                    {
                        "label": f"candidate {i}",
                        "hint": f"The world might do {i}.",
                    }
                    for i in range(MAX_DIRECTIONS + 1)
                )
            ),
            "count 5 is a menu",
        ),
        (
            _directed_answer(
                ({"label": "   ", "hint": "The label is blank."},)
                + _CANDIDATES[:1]
            ),
            "a blank label",
        ),
        (
            _directed_answer(
                ({"label": "fine", "hint": "  "},) + _CANDIDATES[:1]
            ),
            "a blank hint",
        ),
        (
            _directed_answer(
                (
                    {
                        "label": "extra",
                        "hint": "One extra field.",
                        "mood": "wistful",
                    },
                )
                + _CANDIDATES[:1]
            ),
            "an extra field",
        ),
        (
            json.dumps(
                {
                    "beats": [
                        {
                            "kind": "lamp-relit",
                            "narration": "The lamp burned all night.",
                            "days": 1,
                        }
                    ],
                    "directions": "two labels, no array",
                }
            ),
            "directions is not an array",
        ),
    ),
)
def test_a_bad_directions_array_refuses_the_whole_batch(
    answer: str, why: str
) -> None:
    """The whole-batch law covers the candidates: a bad array refuses
    the narration it rode in on — no partial adoption, the beats die
    with their directions (one answer, one fate)."""

    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=answer)))
    parsed = narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )
    assert isinstance(parsed, Err), why
    assert parsed.error.message.startswith("narrator refused:")


# ---------------------------------------------------------------------------
# 2 — the prompt (the requirement, the zero-change default, the choice)
# ---------------------------------------------------------------------------


def test_the_directed_prompt_carries_the_candidates_requirement() -> None:
    """Directed mode asks for the 2-4 candidates under the
    ``directions`` key and widens the JSON shape line; the bounds are
    the module's own constants (one spelling, two doors). lr-4a
    (DEC-OPI-c73dbff3…128 R5) tightens the copy: a direction is **the
    immediate next step the world takes** — one concrete development,
    never a far horizon — and the label is a few words, never a
    sentence (the pre-lr-4a wording is the retired copy, named so a
    regression to it lands here)."""

    prompt = build_narrator_prompt(
        _package(), (), (), "zh", direction_mode=DIRECTION_DIRECTED
    )
    assert f"{MIN_DIRECTIONS} to {MAX_DIRECTIONS} directions" in prompt
    assert '"directions" key' in prompt
    assert '"directions": [{"label": "<short phrase>",' in prompt
    assert "the immediate" in prompt
    assert "next step the world takes" in prompt
    assert "a few words, never a sentence" in prompt
    assert "never a far horizon" in prompt
    assert "one the user may pick for it" not in prompt


def test_the_immersive_prompt_carries_no_direction_words() -> None:
    """Immersive mode is the pre-wr-10 prompt byte for byte: no
    candidates requirement, no widened shape line, no chosen-direction
    section — the zero-change default (the mutation that adds a
    requirement line to the immersive arm lands here)."""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    assert "direction" not in prompt.lower()
    assert '"directions"' not in prompt
    assert "chosen direction" not in prompt.lower()


def test_the_pending_direction_rides_its_own_section() -> None:
    """A pending choice adds its own section naming the label and the
    hint — the director's input, the direction channel's own door."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        direction_mode=DIRECTION_DIRECTED,
        pending_direction=("the fair arrives", "Tents dot the cliff meadow."),
    )
    assert "The user has chosen where the world goes next:" in prompt
    assert "the fair arrives — Tents dot the cliff meadow." in prompt
    assert "The world moves in this direction." in prompt


def test_the_letter_never_enters_even_with_a_pending_direction() -> None:
    """WR-4's law with the director's input present: the letter's text
    is nowhere in the prompt — the pending direction rides in, the
    correspondence never does (the two-layer law, judgment face)."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        direction_mode=DIRECTION_DIRECTED,
        pending_direction=("the fair arrives", "Tents dot the cliff meadow."),
    )
    assert "lighthouse keeper is my uncle" not in prompt
    assert "please look in on him" not in prompt


def test_a_mode_outside_the_vocabulary_refuses() -> None:
    """The mode word is one of the two: anything else is a ValueError
    naming the vocabulary (the ui_language posture, restated)."""

    with pytest.raises(ValueError, match="directed"):
        build_narrator_prompt(_package(), (), (), "zh", direction_mode="god")


# ---------------------------------------------------------------------------
# 3 — the extractor (the preview never leaks the candidates)
# ---------------------------------------------------------------------------


def test_the_extractor_emits_the_narrations_only() -> None:
    """The streamed preview emits the beats' narrations and nothing
    else: label and hint text never leave through the wr-7 machine —
    whole-fed and character-fed agree (the machine reads one key, and
    wr-10 changed it not at all)."""

    text = _directed_answer(_CANDIDATES)
    expected = {
        0: "The harbour kept its silence.",
    }
    whole = _join(NarrationExtractor().feed(text))
    assert whole == expected
    charwise = _join(_feed_all(NarrationExtractor(), text, 1))
    assert charwise == expected
    # Every label and hint word stayed inside the machine.
    joined_text = "".join(piece for _, piece in whole.items())
    for candidate in _CANDIDATES:
        assert candidate["label"] not in joined_text
        assert candidate["hint"] not in joined_text


def _join(pieces: tuple[tuple[int, str], ...]) -> dict[int, str]:
    joined: dict[int, str] = {}
    for index, piece in pieces:
        joined[index] = joined.get(index, "") + piece
    return joined


def _feed_all(
    extractor: NarrationExtractor, text: str, cut: int
) -> tuple[tuple[int, str], ...]:
    out: list[tuple[int, str]] = []
    for start in range(0, len(text), cut):
        out.extend(extractor.feed(text[start : start + cut]))
    return tuple(out)


# ---------------------------------------------------------------------------
# 4 — the seam (the pass-through and the callback, defaults unchanged)
# ---------------------------------------------------------------------------


def test_the_step_passes_mode_and_pending_through(store: SqliteWorldStore) -> None:
    """The seam: ``direction_mode`` / ``pending_direction`` reach the
    narrator's prompt (the requirement line and the chosen-direction
    section in the scripted prompt), and the answer's candidates ride
    ``on_directions`` — the beats land as before."""

    _seed_world(store)
    provider = _ScriptedNarrator(
        ProviderOutput(text=_directed_answer(_CANDIDATES))
    )
    seen: list[tuple[DirectionCandidate, ...]] = []
    stepped = run_generated_step(
        store,
        WORLD,
        _package(),
        provider,
        "turn-wr10-1",
        NOW,
        direction_mode=DIRECTION_DIRECTED,
        pending_direction=("the fair arrives", "Tents dot the cliff meadow."),
        on_directions=seen.append,
    )
    assert isinstance(stepped, Ok)
    assert len(stepped.value) == 1
    prompt = provider.prompts[0]
    assert f"{MIN_DIRECTIONS} to {MAX_DIRECTIONS} directions" in prompt
    assert "the fair arrives — Tents dot the cliff meadow." in prompt
    assert seen == [
        tuple(
            DirectionCandidate(label=c["label"], hint=c["hint"])
            for c in _CANDIDATES
        )
    ]


def test_the_defaults_run_the_step_as_before_wr10(
    store: SqliteWorldStore,
) -> None:
    """The defaults (immersive, no pending, no callback) run the step
    byte for byte as before wr-10: the prompt carries no direction
    words, the events land unchanged."""

    _seed_world(store)
    provider = _ScriptedNarrator(ProviderOutput(text=_beats(_beat(days=1))))
    stepped = run_generated_step(
        store, WORLD, _package(), provider, "turn-wr10-2", NOW
    )
    assert isinstance(stepped, Ok)
    assert len(stepped.value) == 1
    prompt = provider.prompts[0]
    assert "direction" not in prompt.lower()


def test_the_quiet_arms_never_fire_the_direction_callback(
    store: SqliteWorldStore,
) -> None:
    """A silent world offers no choices: the no-provider arm and the
    ``not-configured`` arm each answer ``Ok(())`` and the callback
    never fires — 拒收/安静不清's seam half."""

    seen: list[tuple[DirectionCandidate, ...]] = []
    quiet = run_generated_step(
        store,
        WORLD,
        _package(),
        None,
        "turn-wr10-3",
        NOW,
        direction_mode=DIRECTION_DIRECTED,
        on_directions=seen.append,
    )
    assert isinstance(quiet, Ok)
    assert quiet.value == ()
    assert seen == []
    bare = _ScriptedNarrator(
        ProviderOutput(text=None, error="not-configured")
    )
    unconfigured = run_generated_step(
        store,
        WORLD,
        _package(),
        bare,
        "turn-wr10-4",
        NOW,
        direction_mode=DIRECTION_DIRECTED,
        on_directions=seen.append,
    )
    assert isinstance(unconfigured, Ok)
    assert unconfigured.value == ()
    assert seen == []
