"""D-1 — the reader's own character in the world (DEC-OPI-a4cf2d0e…40,
v7): the design supplement's first engineering meaning
(``docs/IMPLEMENTATION_PLAN.md`` §19, living-world-spec §3.2 v2.2).

The user is a resident of the town, not an outside observer: the world
package declares her (id / name / anchor / home), the narrator's prompt
carries her line right after the roster and teaches her posture, a
beat's ``participants`` may name her declared id, and the character's
cognitive view remembers the events she lived through with her. The pin
groups:

1. **the package face** — the shipped Berrymoor file decodes its
   ``user_character`` section with the four exact values, an absent
   section is the honest ``None``, every shape violation is an ``Err``
   naming the offending key, and the v7 wall refuses a v6 stamp;
2. **the narrator's conditional line** — the shipped prompt carries
   ``Your character: …`` right after the cast-id roster (her id joins
   the roster's vocabulary), teaches the resident-not-a-bystander
   posture and the existence statement, and splice-the-section-out
   recovers the pre-v7 bytes exactly (the conditional-section law);
3. **the participants vocabulary** — a beat naming her declared id
   parses (the reader's action is chronicle-worthy), a stranger id
   still refuses the whole batch, and a package without the section
   refuses her id too (the vocabulary is the package's own);
4. **the cognitive view's user layer** — an event naming her id is a
   memory of the character who lived it (kept beside the public and the
   witnessed), an others'-only event stays out, and the filter still
   runs before the window;
5. **the package-declared law** — a host over a package with the
   section stripped keeps exactly the pre-D-1 filter (the co-presence
   arm is declared by the package, never guessed by the assembly);
6. **prompt material, nothing more** — the seed binds no actor for her
   id and the shipped four values are the design's own (no persona, no
   card, no store row).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from elc.host import open_host
from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import ConversationId, Err, Ok
from elc.world.narrator import (
    GeneratedBeat,
    WorldNarrator,
    build_narrator_prompt,
)
from elc.world.package import (
    BUILTIN_WORLDS_DIR,
    WORLD_PACKAGE_VERSION,
    UserCharacter,
    WorldPackage,
    load_world_package,
)
from elc.world.types import WorldEvent
from elc.world_lore.types import RECENT_WORLD_EVENT_WINDOW

PACKAGE_PATH = BUILTIN_WORLDS_DIR / "berrymoor.json"
NOW = "2026-10-11T08:00:00+00:00"
CONV = "d1-conv-nell"
STRANGER_ID = "persona-stranger"
#: The builtin cast's bound actor (the seed's derivation).
NELL_ACTOR_ID = "actor-berrymoor-nell"

#: The shipped user character — the design's own four values (D-1 R1).
SHIPPED_ID = "actor-berrymoor-you"
SHIPPED_NAME = "你"
SHIPPED_ANCHOR = "你是镇上的人，住在装订铺楼上的小房间"
SHIPPED_HOME = "装订铺楼上"

#: The cast area's two added paragraphs, word for word (R2's line and
#: the R2/R3/R5 teaching — pinned so a re-wording is a conscious
#: re-cast). The block is contiguous: splice it out and the pre-v7
#: bytes come back exactly.
SHIPPED_LINE = f"Your character: {SHIPPED_NAME} — {SHIPPED_ANCHOR}"
SHIPPED_TEACHING = (
    f"Your character ({SHIPPED_ID}) is a resident of the town, not a"
    " bystander: you may write her into your beats — a beat that"
    " carries her names her id in its ``participants``, beside the"
    " cast ids — and she lives her days here even while she is not"
    " writing right now."
)


# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


def _shipped() -> WorldPackage:
    loaded = load_world_package(PACKAGE_PATH)
    assert isinstance(loaded, Ok), loaded.error.message
    return loaded.value


def _user_section(**overrides: object) -> dict[str, object]:
    section: dict[str, object] = {
        "id": SHIPPED_ID,
        "name": SHIPPED_NAME,
        "anchor": SHIPPED_ANCHOR,
        "home": SHIPPED_HOME,
    }
    section.update(overrides)
    return section


def _payload(with_user: bool = True) -> dict[str, object]:
    """One minimal valid v7 payload — the negative tests mutate a copy
    of this; the user_character section rides only when asked for."""

    payload: dict[str, object] = {
        "world_id": "world-x",
        "name": "X",
        "version": WORLD_PACKAGE_VERSION,
        "calendar_start": "2025-09-14",
        "setting": ["one"],
        "cast": [
            {"persona_id": "persona-nell", "name": "Nell Alder"},
            {"persona_id": "persona-silas", "name": "Silas Grey"},
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
    if with_user:
        payload["user_character"] = _user_section()
    return payload


def _write_package(
    tmp_path: Path, payload: object, name: str = "w.json"
) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return path


def _load(tmp_path: Path, payload: object, name: str = "w.json"):
    return load_world_package(_write_package(tmp_path, payload, name))


class _ScriptedNarrator:
    """A provider double: one scripted output per call (the last
    repeats), and the prompts it saw (the C1-b fixture shape)."""

    def __init__(self, *outputs: ProviderOutput) -> None:
        self._outputs = outputs
        self._cursor = 0

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        entry = self._outputs[min(self._cursor, len(self._outputs) - 1)]
        self._cursor += 1
        return entry


def _beats(*beats: dict[str, object]) -> str:
    return json.dumps({"beats": list(beats)})


def _beat(
    kind: str = "shared-errand", participants: object = None
) -> dict[str, object]:
    beat: dict[str, object] = {
        "kind": kind,
        "narration": "The slates went up the bindery steps.",
        "days": 0,
    }
    if participants is not None:
        beat["participants"] = participants
    return beat


def _generate(text: str, package: WorldPackage):
    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=text)))
    return narrator.generate(
        package=package,
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )


class _UnusedProvider:
    """A provider double: the host-level pins never run a turn, so a
    dial is a test bug — fail loudly rather than fabricate an answer."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:  # noqa: ARG002
        raise AssertionError("no turn may run in these pins")


def _bound_host(tmp_path: Path, worlds_dir: Path | None = None):
    """A prep-1-tier host over the builtin world, one conversation bound
    through the cast's own actor (the C1-c fixture shape). The host is
    the caller's to close."""

    host = open_host(
        tmp_path / "app.db", provider=_UnusedProvider(), worlds_dir=worlds_dir
    )
    opened = host.open_conversation(ConversationId(CONV))
    assert isinstance(opened, Ok), opened
    world = host.world_store.list_worlds()[0]
    world_id = str(world.world_id)
    actor = host.world_store.actors_of(world_id)[0]
    bound = host.world_store.bind_conversation(
        "wcb-d1", world_id, str(actor.actor_id), CONV, NOW
    )
    assert isinstance(bound, Ok), bound
    return host, world_id


def _event(
    world_id: str,
    event_id: str,
    narration: str,
    participants: tuple[str, ...],
    index: int,
) -> WorldEvent:
    return WorldEvent(
        event_id=event_id,
        world_id=world_id,
        kind="d1-beat",
        narration=narration,
        effects=(),
        occurred_at=f"0025-05-{10 + index:02d}",
        source="d1-test",
        participants=participants,
    )


def _record(host, world_id: str, event: WorldEvent) -> None:
    answered = host.world_store.record_event(event)
    assert isinstance(answered, Ok), answered


def _view(host) -> tuple[str, ...]:
    port = host.coordinator._world_chronicle  # type: ignore[attr-defined]
    answered = port.resolve_world_chronicle_view(ConversationId(CONV))
    assert isinstance(answered, Ok), answered
    return tuple(entry.narration for entry in answered.value.events)


# ---------------------------------------------------------------------------
# 1 — the package face (v7)
# ---------------------------------------------------------------------------


def test_the_shipped_section_decodes_with_the_designs_values() -> None:
    """The shipped Berrymoor file carries the four exact values — the
    reader is a townsperson with a name, an anchor and a home."""

    package = _shipped()
    assert package.version == WORLD_PACKAGE_VERSION == 7
    assert package.user_character == UserCharacter(
        id=SHIPPED_ID,
        name=SHIPPED_NAME,
        anchor=SHIPPED_ANCHOR,
        home=SHIPPED_HOME,
    )


def test_an_absent_section_is_the_honest_none(tmp_path: Path) -> None:
    """The conditional law's package half: no section, no user
    character — ``None``, never a guessed one."""

    loaded = _load(tmp_path, _payload(with_user=False))
    assert isinstance(loaded, Ok), loaded.error.message
    assert loaded.value.user_character is None


@pytest.mark.parametrize("stamp", [8, 9, 6, 5])
def test_a_foreign_stamp_is_refused_by_the_v7_wall(
    tmp_path: Path, stamp: int
) -> None:
    """The version wall is an equality, not a floor (review LOW-2): a
    stamp other than 7 — a future v8+ guessed at, or an old v6-and-below
    read half-way — is refused naming both numbers, never silently
    accepted by a floor-shaped check."""

    payload = _payload()
    payload["version"] = stamp
    refused = _load(tmp_path, payload)
    assert isinstance(refused, Err)
    assert f"version must be {WORLD_PACKAGE_VERSION}" in refused.error.message
    assert f"got {stamp}" in refused.error.message


@pytest.mark.parametrize("missing", ["id", "name", "anchor", "home"])
def test_a_missing_key_is_refused_with_its_name(
    tmp_path: Path, missing: str
) -> None:
    """All four keys are required: a missing one is an ``Err`` naming
    the key and the section (a half-drawn resident never rides)."""

    payload = _payload()
    del payload["user_character"][missing]  # type: ignore[index]
    refused = _load(tmp_path, payload)
    assert isinstance(refused, Err)
    assert "user_character" in refused.error.message
    assert f"key {missing!r} is missing" in refused.error.message


def test_an_unexpected_key_is_refused(tmp_path: Path) -> None:
    """The exact four-key shape: a stray key is refused naming it."""

    payload = _payload()
    payload["user_character"]["age"] = 30  # type: ignore[index]
    refused = _load(tmp_path, payload)
    assert isinstance(refused, Err)
    assert "unexpected key 'age'" in refused.error.message


@pytest.mark.parametrize(
    "bad_section",
    [
        "not-an-object",
        7,
        ["id", "name", "anchor", "home"],
        None,
    ],
)
def test_a_non_object_section_is_refused(
    tmp_path: Path, bad_section: object
) -> None:
    """A section that is not a JSON object is refused — an explicit
    ``null`` included (present-but-wrong-shape, the residents / voice
    siblings' own posture), never silently read as absent."""

    payload = _payload()
    payload["user_character"] = bad_section
    refused = _load(tmp_path, payload)
    assert isinstance(refused, Err)
    assert "user_character" in refused.error.message
    assert "not a JSON object" in refused.error.message


@pytest.mark.parametrize(
    ("key", "bad"),
    [
        ("id", 7),
        ("name", ""),
        ("anchor", "   "),
        ("home", None),
    ],
)
def test_a_blank_or_non_string_value_is_refused(
    tmp_path: Path, key: str, bad: object
) -> None:
    """Every value is a required non-empty string: a blank or non-string
    one is refused naming the key."""

    payload = _payload()
    payload["user_character"][key] = bad  # type: ignore[index]
    refused = _load(tmp_path, payload)
    assert isinstance(refused, Err)
    assert f"{key!r} must be a non-empty string" in refused.error.message


def test_a_v6_stamp_is_refused_by_the_v7_wall(tmp_path: Path) -> None:
    """The version wall moved with the version: a v6 stamp is refused
    with both numbers in the message (an old file cannot ride in
    half-read)."""

    payload = _payload(with_user=False)
    payload["version"] = 6
    refused = _load(tmp_path, payload)
    assert isinstance(refused, Err)
    assert "version must be 7" in refused.error.message
    assert "got 6" in refused.error.message


# ---------------------------------------------------------------------------
# 2 — the narrator's conditional line
# ---------------------------------------------------------------------------


def test_the_prompt_carries_her_line_right_after_the_roster() -> None:
    """The cast area's D-1 block: the ``Your character`` line follows the
    roster verbatim, the teaching states the posture, the participants
    extension (her id) and the existence clause, and the whole sits
    before the residents section (the cast area's own order)."""

    prompt = build_narrator_prompt(_shipped(), (), (), "zh")
    assert SHIPPED_LINE in prompt
    assert SHIPPED_TEACHING in prompt
    # The id the parser admits rides the teaching itself (the roster
    # line's own words are untouched).
    assert SHIPPED_ID in prompt
    roster_at = prompt.index("Cast ids (")
    assert roster_at < prompt.index(SHIPPED_LINE)
    # The line sits after the cast row and its roster, before the
    # residents section.
    assert prompt.index("Cast: ") < roster_at < prompt.index(SHIPPED_LINE)
    assert prompt.index(SHIPPED_LINE) < prompt.index(SHIPPED_TEACHING)
    assert prompt.index(SHIPPED_TEACHING) < prompt.index(
        "== The town's residents =="
    )


def test_the_section_is_the_only_difference_it_makes() -> None:
    """The conditional-section law, mechanically: build the shipped
    package with and without its user character and splice the two added
    paragraphs out of the bearing prompt — the pre-v7 bytes come back
    exactly (the golden pins' immovability, restated at this section's
    own boundary)."""

    bearer = _shipped()
    bare = dataclasses.replace(bearer, user_character=None)
    voiced = build_narrator_prompt(bearer, (), (), "zh")
    without = build_narrator_prompt(bare, (), (), "zh")
    assert SHIPPED_LINE not in without
    assert SHIPPED_TEACHING not in without
    assert SHIPPED_ID not in without
    start = voiced.index(SHIPPED_LINE)
    teaching_end = voiced.index(SHIPPED_TEACHING) + len(SHIPPED_TEACHING)
    assert voiced[:start] + voiced[teaching_end + 2 :] == without


def test_a_lone_world_without_the_section_adds_nothing(tmp_path: Path) -> None:
    """A package without the section renders without any of the added
    material — the honest no-player world."""

    package = _load(tmp_path, _payload(with_user=False))
    assert isinstance(package, Ok), package.error.message
    prompt = build_narrator_prompt(package.value, (), (), "zh")
    assert "Your character" not in prompt
    assert SHIPPED_ID not in prompt


# ---------------------------------------------------------------------------
# 3 — the participants vocabulary
# ---------------------------------------------------------------------------


def test_a_beat_may_name_the_user_character() -> None:
    """R3's own arm: a beat whose ``participants`` names the declared
    user id parses — the reader's part in the story is chronicle-worthy
    beside the cast's, alone or riding with a cast id (D-2: every
    positive script is the legal two-beat batch)."""

    parsed = _generate(
        _beats(
            _beat(participants=[SHIPPED_ID]),
            _beat(kind="work-continues"),
        ),
        _shipped(),
    )
    assert isinstance(parsed, Ok), parsed.error
    assert parsed.value[0][0].participants == (SHIPPED_ID,)
    both = _generate(
        _beats(
            _beat(participants=["persona-nell-alder", SHIPPED_ID]),
            _beat(kind="work-continues"),
        ),
        _shipped(),
    )
    assert isinstance(both, Ok), both.error
    assert both.value[0][0] == GeneratedBeat(
        kind="shared-errand",
        narration="The slates went up the bindery steps.",
        days=0,
        participants=("persona-nell-alder", SHIPPED_ID),
    )


def test_a_package_without_the_section_refuses_her_id(
    tmp_path: Path,
) -> None:
    """The vocabulary is the calling package's own: the same id refuses
    for a package that does not declare her (never a global seat)."""

    payload = _payload(with_user=False)
    loaded = _load(tmp_path, payload)
    assert isinstance(loaded, Ok), loaded.error.message
    refused = _generate(
        _beats(
            _beat(participants=[SHIPPED_ID]),
            _beat(kind="work-continues"),
        ),
        loaded.value,
    )
    assert isinstance(refused, Err)
    assert refused.error.message.startswith("narrator refused:")
    assert SHIPPED_ID in refused.error.message
    assert "roster" in refused.error.message


def test_a_stranger_id_still_refuses_the_whole_batch() -> None:
    """The C1-b fail-closed law is untouched: a stranger id refuses the
    whole batch even when a legal user id rides beside it."""

    refused = _generate(
        _beats(
            _beat(kind="a-good-beat"),
            _beat(participants=[SHIPPED_ID, STRANGER_ID]),
        ),
        _shipped(),
    )
    assert isinstance(refused, Err)
    assert STRANGER_ID in refused.error.message


# ---------------------------------------------------------------------------
# 4 — the cognitive view's user layer
# ---------------------------------------------------------------------------


def test_a_co_lived_event_is_the_characters_memory(
    tmp_path: Path,
) -> None:
    """域一 v1.2's user layer: an event naming her declared id is kept in
    the bound actor's view — 「你上周帮她修了书架」是她的记忆."""

    host, world_id = _bound_host(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-d1-together",
                "You helped Nell carry the slates up the bindery steps.",
                (SHIPPED_ID,),
                0,
            ),
        )
        assert _view(host) == (
            "You helped Nell carry the slates up the bindery steps.",
        )
    finally:
        host.close()


def test_an_others_only_event_stays_out_of_her_view(
    tmp_path: Path,
) -> None:
    """The cognitive boundary holds: an event naming neither her persona
    nor the user character is not her memory — the fourth arm widens
    the witnessed half, it does not open the view."""

    host, world_id = _bound_host(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-d1-strange",
                "A stranger mended a sail at the far quay.",
                (STRANGER_ID,),
                0,
            ),
        )
        assert _view(host) == ()
    finally:
        host.close()


def test_the_user_arm_feeds_the_filter_before_the_window(
    tmp_path: Path,
) -> None:
    """Order law: the kept set is public ∪ witnessed ∪ co-lived and the
    window slices **after** it (review LOW-3 — the discriminating
    construction). Ten events: six kept (one old public one, five naming
    her), then four others-only ones at the newest positions. The
    newest window of five therefore *starts* inside the dropped tail —
    slice-then-filter answers exactly one event (the last others-only
    one's kept neighbour), filter-then-slice answers the five co-lived
    ones. The result set itself is the discriminator, not the length
    alone."""

    host, world_id = _bound_host(tmp_path)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-d1-w0",
                "The harbour clock struck eight.",
                (),
                0,
            ),
        )
        for index in range(1, 6):
            _record(
                host,
                world_id,
                _event(
                    world_id,
                    f"we-d1-w{index}",
                    f"Together at the bindery, day {index}.",
                    (SHIPPED_ID,),
                    index,
                ),
            )
        for index in range(6, 10):
            _record(
                host,
                world_id,
                _event(
                    world_id,
                    f"we-d1-x{index}",
                    f"A stranger mended a sail, day {index}.",
                    (STRANGER_ID,),
                    index,
                ),
            )
        view = _view(host)
        assert len(view) == RECENT_WORLD_EVENT_WINDOW
        assert view == tuple(
            f"Together at the bindery, day {index}." for index in range(1, 6)
        )
        assert "The harbour clock struck eight." not in view
        assert not any("A stranger mended" in line for line in view)
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 5 — the package-declared law
# ---------------------------------------------------------------------------


def test_a_stripped_package_keeps_the_pre_d1_filter(
    tmp_path: Path,
) -> None:
    """The co-presence arm is declared by the package, never guessed by
    the assembly: the same event over a package whose section was
    stripped stays out of the view (the mapping has no entry)."""

    source = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
    del source["user_character"]
    worlds_dir = tmp_path / "worlds"
    worlds_dir.mkdir()
    (worlds_dir / "berrymoor.json").write_text(
        json.dumps(source, ensure_ascii=False), encoding="utf-8"
    )
    host, world_id = _bound_host(tmp_path, worlds_dir=worlds_dir)
    try:
        _record(
            host,
            world_id,
            _event(
                world_id,
                "we-d1-unmapped",
                "You helped Nell carry the slates up the bindery steps.",
                (SHIPPED_ID,),
                0,
            ),
        )
        assert _view(host) == ()
    finally:
        host.close()


# ---------------------------------------------------------------------------
# 6 — prompt material, nothing more
# ---------------------------------------------------------------------------


def test_the_seed_binds_no_actor_for_her(tmp_path: Path) -> None:
    """The section is prompt material end to end: the shipped seed binds
    the cast's one actor and no actor for her id — no persona, no card,
    no store row (the reader is not a correspondence face)."""

    host, world_id = _bound_host(tmp_path)
    try:
        actor_ids = {
            str(actor.actor_id)
            for actor in host.world_store.actors_of(world_id)
        }
        assert actor_ids == {NELL_ACTOR_ID}
        assert SHIPPED_ID not in actor_ids
    finally:
        host.close()
