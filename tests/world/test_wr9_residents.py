"""wr-9 — the world's residents and the people instruction (the
narrator's cast-of-the-town face; DEC-OPI-c73dbff3…50).

The user's fourth direction: the world is more than one or two
characters — a series of events happens around the principals too, and
the characters can meet, interact and befriend each other. The pin
groups:

1. **loading (package v5)** — the shipped Berrymoor file decodes with
   the cast vignette and the residents section (the v4 faces) and the
   v5 ``initial_storylines`` section; a v4-and-below
   stamp is refused with the number in the message (the version wall);
   an absent cast ``vignette`` and an absent (or empty) ``residents``
   section are both legal (an honest zero-resident world); a resident
   colliding with a cast name — case-insensitively — is refused, a
   duplicate resident name is refused, and a resident missing a field
   is refused;
2. **the prompt's material face** — a cast member with a vignette rides
   the cast line as ``Name — vignette`` (a bare name without one, the
   pre-v4 shape), the residents ride their own section one line each
   (``Name, role — vignette``), and the people instruction (encounters,
   errands, small kindnesses, frictions, gossip; one event refracting
   through several lives) is present when the package carries residents
   or more than one cast member — and absent for a lone bare-name cast
   world;
3. **WR-4 unchanged** — no letter ever enters the prompt even when the
   residents ride it, the world-autonomy instruction and the rhythm law
   stand verbatim;
4. **the content face** — every vignette's anchor words are real facts
   of the shipped setting and the twelve builtin lore facts (read live
   from ``elc.world_lore.content``), the resident names collide with
   nobody (the cast, nor the official companions), and a ``Resident``
   binds no actor (no persona field — prompt material, never a
   correspondence face).
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from elc.platform.types import Err, Ok
from elc.world.narrator import build_narrator_prompt
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WORLD_PACKAGE_VERSION,
    CastMember,
    Resident,
    SupplyDeclaration,
    WorldPackage,
    load_world_package,
)
from elc.world_lore.content import BERRYMOOR_WORLD_FACTS

PACKAGE_PATH = BUILTIN_WORLDS_DIR / "berrymoor.json"

# The WR-4 instrument: a letter with a unique marker that must never
# appear in the narrator's prompt, residents or no residents.
LETTER = (
    "Dear Berrymoor,\n"
    "The lighthouse keeper is my uncle — please look in on him.\n"
    "- Ada"
)


def _v5_payload() -> dict[str, object]:
    """One minimal valid v5 payload — the negative tests mutate a copy
    of this; the optional v4/v5 sections are absent."""

    return {
        "world_id": "world-x",
        "name": "X",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2025-09-14",
        "setting": ["one", "two", "three"],
        "cast": [{"persona_id": "persona-nell", "name": "Nell"}],
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


def _write_package(tmp_path: Path, payload: object, name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _bare_package() -> WorldPackage:
    """The pre-v4 shape: one bare-name cast member, no residents."""

    return WorldPackage(
        world_id="world-x",
        name="X",
        version=WORLD_PACKAGE_VERSION,
        calendar_start="2025-09-14",
        setting=("A small harbour town.",),
        cast=(CastMember(persona_id="persona-nell", name="Nell Alder"),),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="d-n-c"),
    )


def _peopled_package() -> WorldPackage:
    """The v4 shape under test: a vignette on the cast member and two
    residents."""

    return WorldPackage(
        world_id="world-x",
        name="X",
        version=WORLD_PACKAGE_VERSION,
        calendar_start="2025-09-14",
        setting=("A small harbour town.",),
        cast=(
            CastMember(
                persona_id="persona-nell",
                name="Nell Alder",
                vignette="mends the town's books behind the green door",
            ),
        ),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="d-n-c"),
        residents=(
            Resident(
                name="Old Tam",
                role="the fish counter",
                vignette="never says thank you in words",
            ),
            Resident(
                name="Mrs. Fenwick",
                role="the post office",
                vignette="reads the postmarks first",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# 1 — loading: package v5
# ---------------------------------------------------------------------------


def test_the_shipped_package_is_v5_with_vignette_and_residents() -> None:
    """The shipped Berrymoor file rides v5: the cast member carries a
    non-empty vignette, and the residents section carries four or five
    fully-drawn residents (name, role and vignette all non-empty)."""

    result = load_world_package(PACKAGE_PATH)
    assert isinstance(result, Ok), result.error.message
    package = result.value
    assert package.version == 5
    assert package.cast[0].vignette
    assert 4 <= len(package.residents) <= 5
    for resident in package.residents:
        assert resident.name.strip()
        assert resident.role.strip()
        assert resident.vignette.strip()


def test_earlier_versions_are_refused_with_the_number(tmp_path: Path) -> None:
    """The version wall: a v4 — and a fortiori a v3 or v2 — stamp is
    refused
    with the wall's own number and the offending one in the message (an
    old file cannot ride in half-read)."""

    for old in (4, 3, 2):
        payload = _v5_payload()
        payload["version"] = old
        result = load_world_package(
            _write_package(tmp_path, payload, f"w{old}.json")
        )
        assert isinstance(result, Err)
        assert "version must be 5" in result.error.message
        assert f"got {old}" in result.error.message


def test_absent_vignette_and_absent_residents_are_legal(
    tmp_path: Path,
) -> None:
    """The optional sections: a cast member without a vignette decodes
    to ``None`` and rides the prompt as a bare name; an absent (or
    empty) residents section decodes to the empty tuple — an honest
    zero-resident world."""

    plain = load_world_package(
        _write_package(tmp_path, _v5_payload(), "plain.json")
    )
    assert isinstance(plain, Ok), plain.error.message
    assert plain.value.cast[0].vignette is None
    assert plain.value.residents == ()
    payload = _v5_payload()
    payload["residents"] = []
    empty = load_world_package(
        _write_package(tmp_path, payload, "empty.json")
    )
    assert isinstance(empty, Ok), empty.error.message
    assert empty.value.residents == ()


def test_a_resident_colliding_with_the_cast_name_is_refused(
    tmp_path: Path,
) -> None:
    """One town, one name-space: a resident named like a cast member is
    refused naming the name — and the check is case-insensitive (prose
    does not distinguish case, and neither does the town)."""

    payload = _v5_payload()
    payload["residents"] = [
        {
            "name": "NELL",
            "role": "the bindery",
            "vignette": "a shadow of the cast member",
        }
    ]
    result = load_world_package(
        _write_package(tmp_path, payload, "collide.json")
    )
    assert isinstance(result, Err)
    assert "NELL" in result.error.message
    assert "collides" in result.error.message


def test_duplicate_resident_names_are_refused(tmp_path: Path) -> None:
    """Two residents sharing one name are refused naming the name — the
    prompt's residents section would present the same person twice."""

    payload = _v5_payload()
    payload["residents"] = [
        {"name": "Edie Marsh", "role": "the bakery", "vignette": "bakes"},
        {
            "name": "edie marsh",
            "role": "the shop",
            "vignette": "sells what she bakes",
        },
    ]
    result = load_world_package(
        _write_package(tmp_path, payload, "dup.json")
    )
    assert isinstance(result, Err)
    assert "edie marsh" in result.error.message
    assert "collides" in result.error.message


def test_a_half_drawn_resident_is_refused(tmp_path: Path) -> None:
    """A resident missing a field — or carrying an empty one — is a
    refusal naming the key: a half-drawn person would ride the
    narrator's prompt as a half-drawn person."""

    missing = _v5_payload()
    missing["residents"] = [{"name": "A", "vignette": "b"}]
    result = load_world_package(
        _write_package(tmp_path, missing, "m.json")
    )
    assert isinstance(result, Err)
    assert "role" in result.error.message
    blank = _v5_payload()
    blank["residents"] = [
        {"name": "A", "role": "the role", "vignette": "   "}
    ]
    result = load_world_package(_write_package(tmp_path, blank, "b.json"))
    assert isinstance(result, Err)
    assert "vignette" in result.error.message


# ---------------------------------------------------------------------------
# 2 — the prompt's material face
# ---------------------------------------------------------------------------


def test_the_cast_line_carries_the_vignette_when_present() -> None:
    """A cast member with a vignette rides the cast line as
    ``Name — vignette``; without one the line stays the bare name (the
    pre-v4 shape, byte-unchanged)."""

    peopled = build_narrator_prompt(_peopled_package(), (), (), "zh")
    assert (
        "Cast: Nell Alder — mends the town's books behind the green door"
        in peopled
    )
    bare = build_narrator_prompt(_bare_package(), (), (), "zh")
    assert "Cast: Nell Alder" in bare
    assert "Cast: Nell Alder —" not in bare


def test_the_residents_ride_their_own_section() -> None:
    """The residents section: the header, then one line per resident in
    ``Name, role — vignette`` shape — prompt material read live from
    the package."""

    prompt = build_narrator_prompt(_peopled_package(), (), (), "zh")
    assert "== The town's residents ==" in prompt
    assert "Old Tam, the fish counter — never says thank you in words" in prompt
    assert (
        "Mrs. Fenwick, the post office — reads the postmarks first"
        in prompt
    )
    tam = prompt.index("Old Tam,")
    fenwick = prompt.index("Mrs. Fenwick,")
    assert tam < fenwick


def test_the_people_instruction_rides_with_people() -> None:
    """The people instruction — lives and how they touch, the five
    kinds of touching, one event refracting through several lives, not
    only weather and scenery — is present when the package carries
    residents **or** more than one cast member, and a lone bare-name
    cast world carries neither the residents section nor it."""

    peopled = build_narrator_prompt(_peopled_package(), (), (), "zh")
    for word in (
        "encounters",
        "errands",
        "small kindnesses",
        "frictions",
        "gossip",
        "refract",
        "not only the weather and the scenery",
    ):
        assert word in peopled, word
    twin_cast = WorldPackage(
        world_id="world-x",
        name="X",
        version=WORLD_PACKAGE_VERSION,
        calendar_start="2025-09-14",
        setting=("A small harbour town.",),
        cast=(
            CastMember(persona_id="persona-a", name="Ada Marsh"),
            CastMember(persona_id="persona-b", name="Nell Alder"),
        ),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="d-n-c"),
    )
    twins = build_narrator_prompt(twin_cast, (), (), "zh")
    assert "encounters" in twins
    bare = build_narrator_prompt(_bare_package(), (), (), "zh")
    assert "== The town's residents ==" not in bare
    assert "encounters" not in bare


def test_wr4_no_letter_enters_even_when_residents_ride() -> None:
    """WR-4 regression (the user's third direction, DEC-…58): no letter
    ever enters the prompt — the residents' material face changes
    nothing about the two-layer law; the world-autonomy instruction and
    the rhythm law stand verbatim."""

    prompt = build_narrator_prompt(_peopled_package(), (), (), "zh")
    for line in LETTER.splitlines():
        assert line not in prompt
    assert "The letter ==" not in prompt
    assert (
        "It does not react to any correspondence" in prompt
    )
    assert "Write exactly 1 or 2 beats." in prompt


# ---------------------------------------------------------------------------
# 3 — the content face: the vignettes are real facts of this town
# ---------------------------------------------------------------------------


def test_resident_vignettes_agree_with_setting_and_lore() -> None:
    """逐条互证（W-1-4 内容面钉形态，现读）：every vignette's anchor
    words are anchor words of the shipped setting prose or of the live
    lore facts — Old Tam and Mrs. Fenwick are the lore's own NPCs, the
    rest live on the setting's own fixtures (the quay, the Saturday
    bread, the fog). No anchor, no resident."""

    result = load_world_package(PACKAGE_PATH)
    assert isinstance(result, Ok), result.error.message
    package = result.value
    setting_text = "\n".join(package.setting)
    lore_text = "\n".join(
        fact.statement for fact in BERRYMOOR_WORLD_FACTS
    )
    # (resident name, anchor words that must sit in both the vignette
    # and its corroborating source text)
    cross_checks = [
        ("Old Tam", ["fish counter", "mackerel", "nets", "thank you"]),
        ("Mrs. Fenwick", ["postmarks", "fortnight"]),
        ("Silas Croft", ["fishing boats"]),
        ("Edie Marsh", ["bread"]),
        ("Hester Cowley", ["fog"]),
    ]
    residents = {resident.name: resident for resident in package.residents}
    for name, anchors in cross_checks:
        resident = residents[name]
        # The prompt line is ``Name, role — vignette``; the anchors may
        # sit on either half of it.
        line = f"{resident.role} — {resident.vignette}"
        source = lore_text if name in ("Old Tam", "Mrs. Fenwick") else (
            setting_text
        )
        for anchor in anchors:
            assert anchor in line, (name, anchor)
            assert anchor in source, (name, anchor)
    # Nell's vignette is the setting's own second paragraph: the green
    # door and the grandfather's burnisher, both real bindery facts.
    nell = package.cast[0]
    assert nell.vignette
    for anchor in ("green door", "burnisher"):
        assert anchor in nell.vignette, anchor
        assert anchor in setting_text, anchor
        assert anchor in lore_text, anchor


def test_resident_names_collide_with_nobody_and_bind_no_actor() -> None:
    """The name-space holds: no resident collides with the cast, nor
    with the official companions (Theo / Priya / Evelyn / Maya — the
    world's own people only), and a ``Resident`` carries no persona
    field — prompt material, never a correspondence face."""

    result = load_world_package(PACKAGE_PATH)
    assert isinstance(result, Ok), result.error.message
    package = result.value
    taken = {member.name.casefold() for member in package.cast}
    taken |= {"theo", "priya", "evelyn", "maya"}
    for resident in package.residents:
        assert resident.name.casefold() not in taken
    assert {field.name for field in fields(Resident)} == {
        "name",
        "role",
        "vignette",
    }
