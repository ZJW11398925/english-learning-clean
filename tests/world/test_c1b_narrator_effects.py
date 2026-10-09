"""C1-b — the narrator's state-effect proposals and the cast naming
(DEC-OPI-b290799a…17), the external review HIGH-1's root fix.

Before this cut the generated chronicle was 「有日志的故事生成器」: every
narrator-written event landed ``effects=()`` and unnamed, so the
projection never moved and the story's long coherence rode the last
eight narrations alone. The pin groups:

1. **the widened contract** — a beat may carry the two optional keys:
   ``effects`` (an array of exactly ``key`` / ``statement`` non-blank
   pairs — the state claims the beat settles) and ``participants``
   (an array of cast ids — roster-verified, fail-closed on a stranger);
   a malformed anything refuses the **whole batch** (the pre-C1-b law,
   now covering the new keys), and a missing key answers the empty
   tuple (the pre-C1-b three-key shape parses exactly as before);
2. **the prompt's teaching face** — the cast-id roster (the only
   vocabulary ``participants`` may draw from), the current-state
   section (present exactly when the caller carries facts), and the
   optional-keys paragraph (both modes) — while the shape lines of
   every earlier cut stay byte-true (the extension teaches beside
   them, never over them);
3. **the pipeline** — a stub-answered beat with proposals and a named
   cast lands them verbatim (the projection's CURRENT row settles, the
   attribution column reads back), the next step's prompt carries the
   settled claim (the feed-forward loop closed), a second proposal for
   the same key supersedes (the store's atomic settlement through the
   generated path), a pure-narration beat lands exactly as before, and
   the replay of an effects-bearing letter stays the store's no-op.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from elc.persona.types import ProviderOutput
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err, Ok
from elc.world.engine.orchestrate import run_generated_step
from elc.world.narrator import (
    DIRECTION_DIRECTED,
    NARRATOR_SOURCE,
    GeneratedBeat,
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
from elc.world.types import StateEffect
from tests.world.test_lr1_stop_contract import (
    PARENT_DIRECTED_SHAPE,
    PARENT_IMMERSIVE_SHAPE,
)
from tests.world.test_wr2_narrator import CALENDAR_START, NOW, WORLD

# ---------------------------------------------------------------------------
# shared fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A fresh, fully migrated app.db connection with the production
    foreign-keys-ON profile (the wr-2 fixture shape)."""

    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


def _cast_package(world_id: str = WORLD) -> WorldPackage:
    """One minimal package with a **two-member** cast — the roster law
    needs more than one id to be a vocabulary (the wr-2 single-member
    shape cannot tell a roster from a constant)."""

    return WorldPackage(
        world_id=world_id,
        name="Calendar",
        version=WORLD_PACKAGE_VERSION,
        calendar_start=CALENDAR_START,
        setting=(
            "Calendar is a small harbour town on a cold coast.",
            "The boats come in with the morning tide.",
        ),
        cast=(
            CastMember(persona_id="persona-nell", name="Nell Alder"),
            CastMember(persona_id="persona-silas", name="Silas Grey"),
        ),
        event_pool=(),
        supply=SupplyDeclaration(families=("DISC",), note="declared-not-consumed"),
    )


class _ScriptedNarrator:
    """A provider double: scripted outputs, one per call (the last
    repeats), and the prompt texts it saw (the wr-2 shape — the
    narrator dials ``call`` once per round)."""

    def __init__(self, *outputs: ProviderOutput | BaseException) -> None:
        self._outputs = outputs
        self._cursor = 0
        self.prompts: list[str] = []

    def call(self, prompt) -> ProviderOutput:  # noqa: ANN001 — the protocol shape
        self.prompts.append(prompt.prompt_text)
        entry = self._outputs[min(self._cursor, len(self._outputs) - 1)]
        self._cursor += 1
        if isinstance(entry, BaseException):
            raise entry
        return entry


def _beat(
    kind: str = "loom-sings",
    narration: str = "The loom sang at dusk.",
    days: object = 1,
    effects: object = None,
    participants: object = None,
) -> dict[str, object]:
    beat: dict[str, object] = {"kind": kind, "narration": narration, "days": days}
    if effects is not None:
        beat["effects"] = effects
    if participants is not None:
        beat["participants"] = participants
    return beat


def _beats(*beats: dict[str, object]) -> str:
    return json.dumps({"beats": list(beats)})


def _generate(
    text: str,
    package: WorldPackage | None = None,
) -> Ok | Err:
    narrator = WorldNarrator(_ScriptedNarrator(ProviderOutput(text=text)))
    return narrator.generate(
        package=package or _cast_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )


def _refused(text: str, package: WorldPackage | None = None) -> Err:
    parsed = _generate(text, package)
    assert isinstance(parsed, Err), text
    assert parsed.error.message.startswith("narrator refused:")
    return parsed


# ---------------------------------------------------------------------------
# 1 — the widened contract (the parse)
# ---------------------------------------------------------------------------


def test_a_beat_with_effects_and_participants_parses() -> None:
    """The widened shape parses: the beat comes out carrying its
    proposals as StateEffect tuples and its named cast verbatim."""

    parsed = _generate(
        _beats(
            _beat(
                effects=[
                    {"key": "loom-key", "statement": "The loom sings."},
                ],
                participants=["persona-nell", "persona-silas"],
            )
        )
    )
    assert isinstance(parsed, Ok)
    assert parsed.value[0] == (
        GeneratedBeat(
            kind="loom-sings",
            narration="The loom sang at dusk.",
            days=1,
            effects=(StateEffect(key="loom-key", statement="The loom sings."),),
            participants=("persona-nell", "persona-silas"),
        ),
    )


def test_missing_optional_keys_answer_empty_tuples() -> None:
    """The pre-C1-b three-key shape parses exactly as before: no keys,
    no proposals, no names — the empty tuples."""

    parsed = _generate(_beats(_beat()))
    assert isinstance(parsed, Ok)
    assert parsed.value[0] == (
        GeneratedBeat(
            kind="loom-sings",
            narration="The loom sang at dusk.",
            days=1,
        ),
    )
    # Explicit empty arrays are the same answer.
    emptied = _generate(
        _beats(_beat(effects=[], participants=[])),
    )
    assert isinstance(emptied, Ok)
    assert emptied.value[0][0].effects == ()
    assert emptied.value[0][0].participants == ()


@pytest.mark.parametrize(
    "effects",
    [
        "not-an-array",
        [{"key": "k", "statement": "s", "extra": 1}],
        [{"statement": "missing the key"}],
        [{"key": "missing the statement"}],
        [{"key": "", "statement": "blank key"}],
        [{"key": "   ", "statement": "blank key"}],
        [{"key": "k", "statement": ""}],
        [{"key": "k", "statement": "  \n "}],
        [{"key": 7, "statement": "s"}],
        [{"no": "shape"}],
        ["not-an-object"],
    ],
)
def test_a_malformed_effects_array_refuses_the_whole_batch(
    effects: object,
) -> None:
    """The effects array's shape law: a non-array, an element that is
    not exactly the two non-blank strings — each refuses the **whole**
    batch (mixed: the first beat is well-formed and dies with its
    companion — no partial adoption)."""

    text = _beats(
        _beat(kind="a-good-beat", narration="The tide turned."),
        _beat(kind="proposing", effects=effects),
    )
    _refused(text)


@pytest.mark.parametrize(
    "participants",
    [
        "not-an-array",
        [7],
        [""],
        ["   "],
        ["persona-stranger"],
        ["persona-nell", "persona-stranger"],
    ],
)
def test_bad_participants_refuse_the_whole_batch(participants: object) -> None:
    """The roster law, fail-closed: an unknown cast id — alone or riding
    beside a good one — refuses the whole batch, as does any element
    that is not a non-blank string."""

    text = _beats(
        _beat(kind="a-good-beat", narration="The tide turned."),
        _beat(kind="peopled", participants=participants),
    )
    refused = _refused(text)
    if any(p == "persona-stranger" for p in participants if isinstance(p, str)):
        assert "persona-stranger" in refused.error.message
        assert "roster" in refused.error.message


def test_the_roster_is_the_calling_package_cast() -> None:
    """The vocabulary is the **calling** package's cast: an id legal for
    one world refuses for a package that does not carry it (the parser
    gets its roster from the caller's package, never a global)."""

    text = _beats(_beat(participants=["persona-nell"]))
    assert isinstance(_generate(text), Ok)
    lonely = _cast_package()
    object.__setattr__(  # noqa: SLF001 — test-side package surgery
        lonely,
        "cast",
        (CastMember(persona_id="persona-ada", name="Ada Marsh"),),
    )
    _refused(text, lonely)


# ---------------------------------------------------------------------------
# 2 — the prompt's teaching face
# ---------------------------------------------------------------------------


def test_the_prompt_carries_the_cast_id_roster() -> None:
    """The roster line names every cast member's id beside the name the
    prose knows — the only ids ``participants`` may draw from."""

    prompt = build_narrator_prompt(_cast_package(), (), (), "zh")
    assert (
        "Cast ids (a beat's ``participants`` names these ids and no"
        " others): persona-nell = Nell Alder, persona-silas = Silas Grey"
    ) in prompt


def test_the_state_section_appears_exactly_when_facts_ride() -> None:
    """The current-state section: present with the caller's facts as
    ``key: statement`` lines plus the effects invitation; absent (the
    old shape) when the caller carries none."""

    carried = build_narrator_prompt(
        _cast_package(),
        (),
        (),
        "zh",
        state_facts=(
            ("loom-key", "The loom sings at dusk."),
            ("fog_lifted", "The fog lifted by noon."),
        ),
    )
    assert "== The world's current state ==" in carried
    assert "- loom-key: The loom sings at dusk." in carried
    assert "- fog_lifted: The fog lifted by noon." in carried
    assert "``effects``" in carried
    empty = build_narrator_prompt(_cast_package(), (), (), "zh")
    assert "== The world's current state ==" not in empty


def test_the_optional_keys_paragraph_rides_both_modes() -> None:
    """The contract teaching is unconditional: the widened beat shape
    and the filling rules ride the immersive default and the directed
    mode alike — after the shape line, never over it."""

    immersive = build_narrator_prompt(_cast_package(), (), (), "zh")
    directed = build_narrator_prompt(
        _cast_package(), (), (), "zh", DIRECTION_DIRECTED
    )
    for prompt in (immersive, directed):
        assert "Beside the required ``kind``" in prompt
        assert (
            '{"key": <the state key>, "statement": <what becomes true>}'
            in prompt
        )
        assert "Cast ids (a beat's ``participants``" in prompt


def test_the_earlier_cuts_shape_lines_stay_byte_true() -> None:
    """The extension teaches beside the shape lines, never over them:
    both modes' ``Answer with strict JSON`` paragraphs still equal the
    parent-commit literals (lr-1's disposal-cast control, held through
    the C1-b widening)."""

    immersive = build_narrator_prompt(_cast_package(), (), (), "zh")
    shape = next(
        line
        for line in immersive.split("\n\n")
        if line.startswith("Answer with strict JSON")
    )
    assert shape == PARENT_IMMERSIVE_SHAPE
    directed = build_narrator_prompt(
        _cast_package(), (), (), "zh", DIRECTION_DIRECTED
    )
    directed_shape = next(
        line
        for line in directed.split("\n\n")
        if line.startswith("Answer with strict JSON")
    )
    assert directed_shape == PARENT_DIRECTED_SHAPE


# ---------------------------------------------------------------------------
# 3 — the pipeline (the generated step to the projection)
# ---------------------------------------------------------------------------


def test_a_proposing_beat_lands_its_effects_and_cast(store: SqliteWorldStore) -> None:
    """The root fix, end to end: a stub-answered beat with a proposal
    and a named cast lands verbatim — the chronicle row carries both,
    the projection settles a CURRENT row sourced by the event, and the
    attribution column reads back the named cast."""

    assert store.create_world(WORLD, "Calendar", None, NOW).value is not None
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(
                    kind="loom-sings",
                    narration="The loom sang and the town heard it.",
                    days=1,
                    effects=[
                        {
                            "key": "loom-key",
                            "statement": "The loom sings at dusk.",
                        },
                    ],
                    participants=["persona-nell"],
                )
            )
        )
    )
    stepped = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-1", NOW
    )
    assert isinstance(stepped, Ok)
    (event,) = stepped.value
    assert event.source == NARRATOR_SOURCE
    assert event.effects == (
        StateEffect(key="loom-key", statement="The loom sings at dusk."),
    )
    assert event.participants == ("persona-nell",)
    facts = store.current_facts(WORLD)
    assert [(fact.canonical_key, fact.statement) for fact in facts] == [
        ("loom-key", "The loom sings at dusk.")
    ]
    assert facts[0].source_event_id == event.event_id
    assert facts[0].status == "CURRENT"
    stored = store.chronicle_of(WORLD).value[0]
    assert stored.participants == ("persona-nell",)


def test_the_next_step_prompt_carries_the_settled_claim(
    store: SqliteWorldStore,
) -> None:
    """The feed-forward loop (HIGH-1's ask): the second step's prompt
    carries the settled claim under the current-state header — the
    story's own state rides into the next composition, not just the
    last eight narrations."""

    assert store.create_world(WORLD, "Calendar", None, NOW).value is not None
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(
                    effects=[
                        {"key": "loom-key", "statement": "The loom sings."},
                    ],
                )
            )
        ),
        ProviderOutput(
            text=_beats(
                _beat(kind="market-day", narration="The stalls went up.", days=1),
            )
        ),
    )
    first = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-2", NOW
    )
    assert isinstance(first, Ok)
    second = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-3", NOW
    )
    assert isinstance(second, Ok)
    follow_up = provider.prompts[1]
    assert "== The world's current state ==" in follow_up
    assert "- loom-key: The loom sings." in follow_up


def test_a_second_proposal_supersedes_through_the_generated_path(
    store: SqliteWorldStore,
) -> None:
    """The store's atomic settlement, through the generated path: a
    later beat proposing the same key flips the older CURRENT fact to
    SUPERSEDED and lands its own claim as the one CURRENT row."""

    assert store.create_world(WORLD, "Calendar", None, NOW).value is not None
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(effects=[{"key": "loom-key", "statement": "It sings."}]),
            )
        ),
        ProviderOutput(
            text=_beats(
                _beat(
                    kind="loom-falls-silent",
                    narration="The loom went quiet.",
                    effects=[
                        {
                            "key": "loom-key",
                            "statement": "The loom is silent.",
                        },
                    ],
                )
            )
        ),
    )
    for turn in ("turn-c1b-4", "turn-c1b-5"):
        stepped = run_generated_step(
            store, WORLD, _cast_package(), provider, turn, NOW
        )
        assert isinstance(stepped, Ok)
    facts = store.current_facts(WORLD)
    assert [(fact.canonical_key, fact.statement) for fact in facts] == [
        ("loom-key", "The loom is silent.")
    ]
    history = store.fact_history(WORLD, "loom-key")
    assert [fact.status for fact in history] == ["SUPERSEDED", "CURRENT"]


def test_a_pure_narration_beat_lands_exactly_as_before(
    store: SqliteWorldStore,
) -> None:
    """The defensive face: a beat without the optional keys is the legal
    pure-narration event — zero settlement rows, empty attribution —
    the pre-C1-b durable shape, byte for byte."""

    assert store.create_world(WORLD, "Calendar", None, NOW).value is not None
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(_beat(kind="quiet-morning", narration="Quiet.", days=0)),
        )
    )
    stepped = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-6", NOW
    )
    assert isinstance(stepped, Ok)
    (event,) = stepped.value
    assert event.effects == ()
    assert event.participants == ()
    assert store.current_facts(WORLD) == ()


def test_an_effects_bearing_replay_stays_a_no_op(
    store: SqliteWorldStore,
) -> None:
    """The replay contract survives the widened shape: the same letter
    re-derives the same event ids (shape includes effects and
    participants), the pre-read skips the whole batch and the durable
    state never grows."""

    assert store.create_world(WORLD, "Calendar", None, NOW).value is not None
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(
                    effects=[{"key": "loom-key", "statement": "It sings."}],
                    participants=["persona-silas"],
                )
            )
        ),
    )
    first = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-7", NOW
    )
    assert isinstance(first, Ok)
    before_events = store.chronicle_of(WORLD).value
    before_facts = store.current_facts(WORLD)
    replay = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-7", NOW
    )
    assert isinstance(replay, Ok)
    assert replay.value == ()
    assert store.chronicle_of(WORLD).value == before_events
    assert store.current_facts(WORLD) == before_facts


def test_the_generated_calendar_law_is_untouched_by_effects(
    store: SqliteWorldStore,
) -> None:
    """The proposals ride beside the calendar, not in its seat: a
    two-beat batch with spans 1 and 2 still stamps S+1 and S+3 (落笔在
    跨度之末) exactly as the wr-2 pin holds."""

    assert store.create_world(WORLD, "Calendar", None, NOW).value is not None
    provider = _ScriptedNarrator(
        ProviderOutput(
            text=_beats(
                _beat(
                    kind="one-day",
                    narration="The tide turned.",
                    days=1,
                    effects=[{"key": "tide", "statement": "The tide turned."}],
                ),
                _beat(kind="two-days", narration="The fog stayed.", days=2),
            )
        ),
    )
    stepped = run_generated_step(
        store, WORLD, _cast_package(), provider, "turn-c1b-8", NOW
    )
    assert isinstance(stepped, Ok)
    assert [str(event.occurred_at) for event in stepped.value] == [
        (date.fromisoformat(CALENDAR_START) + timedelta(days=1)).isoformat(),
        (date.fromisoformat(CALENDAR_START) + timedelta(days=3)).isoformat(),
    ]
