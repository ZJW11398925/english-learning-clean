"""C3 — the characters' own voices (DEC-OPI-a4cf2d0e…6, 域三).

Canon (``docs/design/2026-10-08-cognition-and-narrative-quality.md`` 域三
「角色声音库（语言去 AI 味的核心杠杆）」): 「模仿具体语样远胜遵循抽象
描述」 — a model follows "她说话简洁" far worse than it imitates three
passages she actually wrote. This cut gives the world package a ``voice``
section (v6) and renders it into the narrator prompt's cast section. The
pin groups:

1. **the loader** — the shipped Berrymoor file decodes with six voice
   entries (the cast's Nell Alder plus the five residents; one
   name-space, the residents law continued), the lookup is
   case-insensitive, an absent section and an empty object are the same
   honest zero, and the version wall now stands at v7;
2. **the strict refusals** — a name outside the town, a name colliding
   case-insensitively with another entry's, a missing / unexpected key, a
   wrong scalar shape, the quirks ceiling, a duplicated taboo or quirk, a
   ``samples`` pair whose side is not the canon's three passages (or
   whose shape is wrong at all), and a blank ``motivation`` are each an
   ``Err`` naming the offending key or word (a typo never rides in);
3. **the narrator's section** — present with a library, absent without
   one, and the *only* difference the library makes (the conditional-
   section law: splice the section out and the pre-v6 prompt is back,
   byte for byte);
4. **the material discipline (machine-checked)** — the shipped library
   carries zero mechanism or pedagogy words (the cs-0 / cs-1 blacklists,
   read live from those suites), every character's ``never_says`` words
   do not appear in her own samples, every ``speech_habits`` is at most
   three sentences, and every sample pair is the canon's 3 + 3.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from elc.platform.types import Err, Ok
from elc.world.narrator import _CAST_VOICES_HEADER, build_narrator_prompt
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WORLD_PACKAGE_VERSION,
    WorldPackage,
    load_world_package,
)
from elc.world.voice import (
    VOICE_MAX_QUIRKS,
    VOICE_SAMPLE_COUNT,
    CharacterVoice,
)
from tests.host.test_cs0_teaching_isolation import MECHANISM_WORDS
from tests.host.test_cs1_character_activation import PEDAGOGY_WORDS

PACKAGE_PATH = BUILTIN_WORLDS_DIR / "berrymoor.json"

#: The shipped library's six characters, by the names the package's own
#: cast and residents spell (cast ∪ residents — one name-space).
SHIPPED_NAMES = (
    "Nell Alder",
    "Old Tam",
    "Mrs. Fenwick",
    "Silas Croft",
    "Edie Marsh",
    "Hester Cowley",
)

#: The full mechanism / pedagogy blacklist the cs-1 card-text law uses,
#: read live from those suites (a local copy could agree with a mutation).
VOICE_BLACKLIST = MECHANISM_WORDS + PEDAGOGY_WORDS

_MOTIVATION = "To hold the harbour path steady."


def _shipped() -> WorldPackage:
    result = load_world_package(PACKAGE_PATH)
    assert isinstance(result, Ok), result.error.message
    return result.value


def _minimal_payload() -> dict[str, object]:
    """One minimal valid v7 payload — the negative tests mutate a copy of
    this; the optional sections are absent."""

    return {
        "world_id": "world-x",
        "name": "X",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2025-09-14",
        "setting": ["one"],
        "cast": [
            {"persona_id": "persona-nell", "name": "Nell Alder"},
            {"persona_id": "persona-tam", "name": "Tam Reed"},
        ],
        "residents": [
            {"name": "Old Tam", "role": "the fish counter", "vignette": "v"},
        ],
        "event_pool": [
            {
                "kind": "k",
                "narration": "n",
                "narration_zh": "n-中文",
                "days": 1,
            }
        ],
        "supply": {"note": "declared-not-consumed", "families": ["DISC"]},
    }


def _entry(**overrides: object) -> dict[str, object]:
    """One valid voice entry — the negative tests mutate a copy."""

    entry: dict[str, object] = {
        "speech_habits": "Short, dry, one clause at a time.",
        "never_says": ["sorry"],
        "quirks": ["taps the counter"],
        "register": "Harbour plain.",
        "samples": {
            "en": ["One.", "Two.", "Three."],
            "zh": ["一。", "二。", "三。"],
        },
    }
    entry.update(overrides)
    return entry


def _write_package(tmp_path: Path, payload: object, name: str = "w.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _refusal(tmp_path: Path, voice: object) -> str:
    payload = _minimal_payload()
    payload["voice"] = voice
    result = load_world_package(_write_package(tmp_path, payload))
    assert isinstance(result, Err), result
    return result.error.message


# ---------------------------------------------------------------------------
# 1 — the loader
# ---------------------------------------------------------------------------


def test_the_shipped_package_carries_the_six_characters_voices() -> None:
    """Berrymoor's v6 voice library: one voice entry per character the
    town names — the
    cast's Nell Alder plus the five residents — each with the five canon
    faces, the bilingual 3 + 3 pair, and the optional motivation."""

    package = _shipped()
    assert [name for name, _ in package.voice] == list(SHIPPED_NAMES)
    town = {member.name for member in package.cast} | {
        resident.name for resident in package.residents
    }
    assert set(SHIPPED_NAMES) == town
    for name, voice in package.voice:
        assert voice.speech_habits.strip(), name
        assert voice.register.strip(), name
        assert 1 <= len(voice.quirks) <= VOICE_MAX_QUIRKS, name
        assert voice.never_says, name
        assert len(voice.samples_en) == VOICE_SAMPLE_COUNT, name
        assert len(voice.samples_zh) == VOICE_SAMPLE_COUNT, name
        assert voice.motivation, name


def test_the_lookup_is_case_insensitive_and_honest_about_a_stranger() -> None:
    """``voice_for`` resolves the town's own casing and answers ``None``
    for a name the library does not carry — never a guessed entry."""

    package = _shipped()
    assert package.voice_for("Nell Alder") is not None
    assert package.voice_for("nell alder") is not None
    assert package.voice_for("NELL ALDER") is not None
    assert package.voice_for("Nobody At All") is None


def test_an_absent_or_empty_library_is_the_same_honest_zero(
    tmp_path: Path,
) -> None:
    """The v6 section is optional two ways: absent decodes to the empty
    tuple, and an empty object decodes to the same — a world with no
    authored voices is not a refusal."""

    payload = _minimal_payload()
    absent = load_world_package(_write_package(tmp_path, payload, "a.json"))
    assert isinstance(absent, Ok), absent.error.message
    assert absent.value.voice == ()

    payload["voice"] = {}
    empty = load_world_package(_write_package(tmp_path, payload, "b.json"))
    assert isinstance(empty, Ok), empty.error.message
    assert empty.value.voice == ()


def test_a_v6_stamp_is_refused_by_the_v8_wall(tmp_path: Path) -> None:
    """The version wall moved with the version: v6 — and a fortiori every
    below-version — is refused with both numbers in the message."""

    payload = _minimal_payload()
    payload["version"] = 6
    result = load_world_package(_write_package(tmp_path, payload))
    assert isinstance(result, Err)
    assert "version must be 8" in result.error.message
    assert "got 6" in result.error.message


# ---------------------------------------------------------------------------
# 2 — the strict refusals
# ---------------------------------------------------------------------------


def test_an_unknown_character_name_is_refused(tmp_path: Path) -> None:
    message = _refusal(tmp_path, {"Nobody At All": _entry()})
    assert "Nobody At All" in message
    assert "neither a cast member nor a resident" in message


def test_a_case_insensitive_name_collision_is_refused(tmp_path: Path) -> None:
    message = _refusal(
        tmp_path, {"Old Tam": _entry(), "old tam": _entry()}
    )
    assert "old tam" in message
    assert "collides" in message


def test_the_entry_shape_is_refused_key_by_key(tmp_path: Path) -> None:
    """Missing key, unexpected key, wrong scalar shape and the quirks
    ceiling — each a refusal naming the offending key."""

    missing = _entry()
    del missing["register"]
    assert "register" in _refusal(tmp_path, {"Old Tam": missing})

    unexpected = _entry()
    unexpected["temperament"] = "sunny"
    assert "temperament" in _refusal(tmp_path, {"Old Tam": unexpected})

    blank = _entry(speech_habits="   ")
    assert "speech_habits" in _refusal(tmp_path, {"Old Tam": blank})

    not_a_list = _entry(never_says="sorry")
    assert "never_says" in _refusal(tmp_path, {"Old Tam": not_a_list})

    over = _entry(
        quirks=[f"quirk {index}" for index in range(VOICE_MAX_QUIRKS + 1)]
    )
    message = _refusal(tmp_path, {"Old Tam": over})
    assert "quirks" in message
    assert str(VOICE_MAX_QUIRKS) in message

    blank_motivation = _entry(motivation="  ")
    assert "motivation" in _refusal(tmp_path, {"Old Tam": blank_motivation})

    not_an_object = _refusal(tmp_path, {"Old Tam": ["short and flat"]})
    assert "not a JSON object" in not_an_object


def test_a_duplicated_taboo_or_quirk_is_refused(tmp_path: Path) -> None:
    twice = _entry(never_says=["sorry", "sorry"])
    message = _refusal(tmp_path, {"Old Tam": twice})
    assert "sorry" in message
    assert "twice" in message


@pytest.mark.parametrize(
    "samples",
    (
        {"en": ["One.", "Two."], "zh": ["一。", "二。", "三。"]},
        {"en": ["One.", "Two.", "Three."], "zh": ["一。", "二。"]},
        {"en": ["One.", "Two.", "Three.", "Four."], "zh": ["一。"]},
        {"en": ["One.", "Two.", "Three."]},
        {"en": ["One.", "Two.", "Three."], "zh": ["一。", "二。", "三。"], "fr": []},
        {"en": "One.", "zh": ["一。", "二。", "三。"]},
        {"en": ["One.", "", "Three."], "zh": ["一。", "二。", "三。"]},
    ),
    ids=(
        "en-short",
        "zh-short",
        "uneven",
        "zh-missing",
        "unknown-side",
        "side-not-array",
        "blank-passage",
    ),
)
def test_the_sample_pair_is_refused_side_by_side(
    tmp_path: Path, samples: object
) -> None:
    """Every ``samples`` violation — an uneven pair, a side that is not
    the canon's three, a missing or unexpected side, a blank passage — is
    a refusal naming the offending part (裁断点五: bilingual 3 + 3)."""

    message = _refusal(tmp_path, {"Old Tam": _entry(samples=samples)})
    assert "samples" in message


def test_the_voice_section_must_be_an_object(tmp_path: Path) -> None:
    message = _refusal(tmp_path, ["Old Tam"])
    assert "object mapping character names" in message


# ---------------------------------------------------------------------------
# 3 — the narrator's section
# ---------------------------------------------------------------------------


def test_the_narrator_renders_the_library_when_the_package_carries_one() -> None:
    """The cast's-own-voices section: header, one summary line per
    character in the package's order, each character's own passages in
    both languages, and the closing instruction that a speaking character
    sounds like her passages — never like an abstract description."""

    package = _shipped()
    prompt = build_narrator_prompt(package, (), (), "zh")
    assert _CAST_VOICES_HEADER in prompt.splitlines()
    for name, voice in package.voice:
        assert f"{name} — {voice.speech_habits}" in prompt
        assert f"Register: {voice.register}." in prompt
        for quirk in voice.quirks:
            assert quirk in prompt
        for word in voice.never_says:
            assert word in prompt
        assert f"In {name}'s own hand, in English:" in prompt
        assert f"In {name}'s own hand, in Chinese:" in prompt
        for passage in voice.samples_en + voice.samples_zh:
            assert f"- {passage}" in prompt
    assert (
        "she sounds like her own passages above: their voice is the model"
        in prompt
    )
    # the section sits with the people material, before the world's facts
    assert prompt.index(_CAST_VOICES_HEADER) < prompt.index(
        "== The world's established facts =="
    )
    assert prompt.index("== The town's residents ==") < prompt.index(
        _CAST_VOICES_HEADER
    )


def test_the_library_is_the_only_difference_it_makes() -> None:
    """The conditional-section law, mechanically: build the same package
    with and without its library, and splice the section out of the
    voice-bearing prompt — the pre-v6 bytes come back exactly (the golden
    pins' immovability, restated at the section's own boundary)."""

    with_library = _shipped()
    without = dataclasses.replace(with_library, voice=())
    voiced = build_narrator_prompt(with_library, (), (), "zh")
    bare = build_narrator_prompt(without, (), (), "zh")
    assert _CAST_VOICES_HEADER not in bare
    assert voiced != bare
    start = voiced.index(_CAST_VOICES_HEADER)
    end = voiced.index("== The world's established facts ==")
    assert voiced[:start] + voiced[end:] == bare


def test_a_lone_bare_world_adds_no_section(tmp_path: Path) -> None:
    """A package with neither a library nor residents renders without the
    section (the conditional law's second arm — an honest no-voice
    world)."""

    payload = _minimal_payload()
    del payload["residents"]
    package = load_world_package(_write_package(tmp_path, payload))
    assert isinstance(package, Ok), package.error.message
    prompt = build_narrator_prompt(package.value, (), (), "zh")
    assert _CAST_VOICES_HEADER not in prompt


# ---------------------------------------------------------------------------
# 4 — the material discipline (machine-checked)
# ---------------------------------------------------------------------------


def _voice_strings(voice: CharacterVoice) -> list[str]:
    return [
        voice.speech_habits,
        voice.register,
        *voice.quirks,
        *voice.never_says,
        *voice.samples_en,
        *voice.samples_zh,
        *([voice.motivation] if voice.motivation else []),
    ]


def test_the_shipped_library_carries_zero_mechanism_words() -> None:
    """The cs-0 / cs-1 blacklist, read live: no string of the shipped
    library carries a runtime mechanism word or a pedagogy word (the role
    does not know a teaching system exists — and neither does her voice
    library)."""

    for name, voice in _shipped().voice:
        for text in _voice_strings(voice):
            lowered = text.lower()
            for word in VOICE_BLACKLIST:
                assert word.lower() not in lowered, (name, word, text)


def test_no_characters_taboo_appears_in_her_own_passages() -> None:
    """R5's second machine check: 凡禁忌词收编，该角色语样零命中 — a
    character who never says a word must not say it in her own three
    passages (the library's internal consistency, checked per character
    so a taboo cannot ride in against the material)."""

    for name, voice in _shipped().voice:
        passages = " ".join(voice.samples_en + voice.samples_zh).lower()
        for word in voice.never_says:
            assert word.lower() not in passages, (name, word)


def test_every_speech_habits_stays_within_three_sentences() -> None:
    """The canon's bound (域三: 「句长/语气/节奏——三句以内描述」): a
    habits line longer than three sentences is a description growing back
    into the thing this cut replaces."""

    for name, voice in _shipped().voice:
        sentences = [
            part
            for part in re.split(r"(?<=[.!?])\s+", voice.speech_habits.strip())
            if part
        ]
        assert len(sentences) <= 3, (name, voice.speech_habits)


def test_the_librarys_own_shape_is_the_canons() -> None:
    """The shipped material's counts, restated as the canon's own numbers
    (the loader enforces them; this pin reads the shipped file against
    the constants so a weakened loader cannot quietly widen them)."""

    from elc.world.package import _VOICE_KEYS, _VOICE_OPTIONAL_KEYS

    assert VOICE_SAMPLE_COUNT == 3
    assert VOICE_MAX_QUIRKS == 3
    assert set(_VOICE_OPTIONAL_KEYS) == {"motivation"}
    assert set(_VOICE_KEYS) == {
        "speech_habits",
        "never_says",
        "quirks",
        "samples",
        "register",
    }
    for name, voice in _shipped().voice:
        assert len(voice.samples_en) == len(voice.samples_zh) == 3, name
        assert len(voice.quirks) <= 3, name
