"""V3-8c — the real LLM providers behind the V3 provider protocol face
(TASK-OPI-cddb517c…7 / the opening ruling ``DEC-OPI-cddb517c-…5``) and
the F4 ruling's landing (DOMAIN §20.2's precise row, RA §27's F4 补注,
REGISTER v1.7.4).

The groups:

1. **the seam and the four implementations** —
   :class:`~elc.world.llm_providers.TextCompletion`'s value shape,
   structural conformance against the four frozen Protocols, and the
   failure semantics (a seam ``error`` and an empty answer refuse with
   body-free codes);
2. **the Writer arm** — the POV-safe prompt carries the plan face (the
   ``must_hide`` prohibitions itemized) and the POV's own cognition /
   memory only (the dual-viewer contrast: another viewer's private
   event and context are absent while his own view holds them); the
   prose rides :class:`~elc.world.writer.PovWriter`'s guards and the
   SEGMENT COMMIT;
3. **the parsing law** — the element / Blueprint / Adjudication
   payloads parse in their canonical shapes; the fence wrapper is
   stripped once and only once; malformed JSON, missing keys and wrong
   types refuse with the named codes; keys beyond the canonical set are
   ignored;
4. **the end-to-end wiring** — a minimal Gold-shaped chain through the
   LLM providers (plan_chapter → run_scene with writer / gate /
   resolver → settle), the canonical rows and numbers asserted;
5. **the discipline pins** — the module holds no transaction, no SQL,
   no clock and no ``elc.persona`` edge (the seam is where the egress
   adapter plugs in); it starts cold and is not re-exported; the ledger
   carries the V3-8c entries;
6. **F4** — the resolver context carries the player character's own
   knowledge arms (``viewer_id == player_character_id``, material from
   the user's own memories) beside the POV's narrative face, and keeps
   both ``None`` for a world that declares no player.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err, Ok
from elc.world.action import (
    Adjudication,
    GateStatus,
    ReplanScope,
    action_by_id,
    action_of,
    begin_resolving,
    commit_action,
    get_gate,
    open_gate,
    replan_request_id_for,
    submit_gate,
)
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.bootstrap import ActorSeed, PlayerSeed, create_world_with_bible
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.cognition import (
    V3CognitionEvent,
    V3CognitionView,
    v3_cognition_view,
)
from elc.world.director import Director
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmDirectorProvider,
    LlmPlannerProvider,
    LlmProviderError,
    LlmResolverProvider,
    LlmWriterProvider,
)
from elc.world.memory import (
    ActorMemoryRecord,
    MemoryKind,
    V3MemoryView,
    v3_memory_view,
)
from elc.world.narrative import SqliteNarrativeStore
from elc.world.pipeline import GateBeat, Pipeline, SegmentBeat
from elc.world.providers import (
    DeterministicFakeProvider,
    DirectorPlanContext,
    DirectorProvider,
    PlannerProvider,
    PovContext,
    ResolverContext,
    ResolverProvider,
    ScenePlanContext,
    WriterProvider,
)
from elc.world.scene import ScenePlanner
from elc.world.settlement import commit_segment
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import StateEffect
from tests.conftest import SRC_ROOT

REPO = Path(__file__).resolve().parents[2]
AOCI_FILE = REPO / "aoci.code.txt"

LLM_SOURCE = (SRC_ROOT / "world" / "llm_providers.py").read_text(
    encoding="utf-8"
)
LLM_TREE = ast.parse(LLM_SOURCE)

NOW = "2026-10-13T00:00:00+00:00"
LATER = "2026-10-13T01:00:00+00:00"

TOWN = "world-town"
CH = "world-town-ch01"
SCENE = "world-town-ch01-s01"
SCENE2 = "world-town-ch01-s02"
GATE = "world-town-ch01-s01-g01"
ACTOR = "actor-lia"
PARTNER = "actor-bram"
PLAYER = "pc-you"

HARD_RULE = "NO HARD RULE VIOLATED: steel is never drawn indoors"
LIA_PRIVATE = "LIA_PRIVATE: she priced the tools herself"
BRAM_PRIVATE = "BRAM_PRIVATE: he watches the tide alone"
BRAM_SECRET_EVENT = "Bram turns the quiet page nobody else sees."
PLAYER_EVENT = "the newcomer steps in alone and the door clicks shut"

PROSE_1 = "The bell above the door answers before her voice does."
PROSE_2 = "She sets the ledger down, and the ice thins by a notch."
INTENT = "I hold the ledger and say nothing."


class _ScriptedCompletion:
    """A deterministic :class:`TextCompletion` stub: answers its
    scripted outcomes in call order, records every prompt it received
    (the pins read the recordings), and raises when called past its
    script — the fake's scripted-gap posture, at the seam."""

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


def _prose(text: str) -> CompletionOutcome:
    return CompletionOutcome(text=text, error=None)


# ---------------------------------------------------------------------------
# fixtures / helpers (the V3-8a / V3-8b suites' own shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def world_store(conn: sqlite3.Connection) -> SqliteWorldStore:
    return SqliteWorldStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def cast_store(conn: sqlite3.Connection) -> SqliteCastStore:
    return SqliteCastStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def bible_store(conn: sqlite3.Connection) -> SqliteBibleStore:
    return SqliteBibleStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def narrative(conn: sqlite3.Connection) -> SqliteNarrativeStore:
    return SqliteNarrativeStore(conn, open_runtime_epoch(conn))


@pytest.fixture()
def director(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> Director:
    return Director(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


@pytest.fixture()
def planner(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> ScenePlanner:
    return ScenePlanner(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )


def _insert_card(conn: sqlite3.Connection, persona_id: str, name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO character_card ("
        " character_id, persona_id, name, identity, personality,"
        " background, speech_style, \"values\", boundaries, opening,"
        " scenario, generation_policy, lore_refs, revision, status,"
        " is_builtin, created_at, updated_at"
        ") VALUES (?, ?, ?, 'i', 'p', 'b', 's', 'v', 'bo', 'o',"
        " 'sc', 'auto', '', 1, 'active', 1, ?, ?)",
        (f"cpkg-{persona_id}", persona_id, name, NOW, NOW),
    )


_UNSET = object()


def _create_town(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    *,
    player: PlayerSeed | None | object = _UNSET,
):
    """The town seed (V3-8b's shape): two AI actors — Lia carrying her
    private context, Bram his — and, unless ``player=None`` is passed
    explicitly, the reader's character with a declared profile."""

    _insert_card(conn, "persona-lia", "Lia")
    _insert_card(conn, "persona-bram", "Bram")
    conn.commit()
    resolved_player = (
        PlayerSeed(
            player_character_id=PLAYER,
            name="You",
            background="a newcomer off the evening coach",
            abilities="steady hands",
            limits="no training with steel",
            location="the inn",
            state="tired",
        )
        if player is _UNSET
        else player
    )
    return create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=TOWN,
        name="Town",
        bible_revision_id=f"{TOWN}-bible-r1",
        bible=BibleContent(
            premise="the town by the water", hard_rules=HARD_RULE
        ),
        actors=(
            ActorSeed(
                actor_id=ACTOR,
                persona_id="persona-lia",
                story_role=StoryRole.PROTAGONIST,
                pov_eligible=True,
                pov_weight=1,
                long_term_drive="keep the shop open a winter longer",
                private_context=LIA_PRIVATE,
            ),
            ActorSeed(
                actor_id=PARTNER,
                persona_id="persona-bram",
                story_role=StoryRole.SUPPORTING,
                pov_eligible=True,
                pov_weight=2,
                long_term_drive="hold the tide schedule",
                private_context=BRAM_PRIVATE,
            ),
        ),
        player=resolved_player,
        now=NOW,
    )


def _scene_draft(
    *,
    pov: str = ACTOR,
    participants: tuple[str, ...] = (ACTOR, PLAYER),
    purpose: str = "first sight",
    must_hide: str = "the priced tools",
) -> dict[str, Any]:
    return {
        "purpose": purpose,
        "place": "the bindery steps",
        "pov_actor_id": pov,
        "participants": list(participants),
        "planned_start_tick": 0,
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if you linger",
        "revealable": "the ledger's back page",
        "must_hide": must_hide,
    }


def _blueprint(
    scenes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if scenes is None:
        scenes = [_scene_draft()]
    return {
        "goal": "the newcomer and the shopkeeper truly meet",
        "dramatic_question": "Will the shop's silence open to a stranger?",
        "planned_start_tick": 0,
        "planned_end_tick": 600,
        "closing_pressure": "the first hard frost presses the order book",
        "desired_development": "trust grows by inches",
        "soft_outcomes": "a repair job, maybe",
        "chapter_questions_to_advance": "who is the letter from?",
        "scenes": scenes,
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
        "participants": [PLAYER, ACTOR],
        "replan_scope": "NONE",
    }


def _ruling(
    *,
    participants: tuple[str, ...] = (PLAYER, ACTOR),
    replan_scope: ReplanScope = ReplanScope.NONE,
) -> Adjudication:
    return Adjudication(
        interpretation="You mean to help rather than to buy.",
        outcome="Lia lets you hold the ledger; the ice thins.",
        actual_action="you carry the ledger to the counter",
        consequences="the shop's silence opens one notch",
        state_effects=(
            StateEffect(key="trust:lia", statement="warmed by one notch"),
        ),
        participants=participants,
        replan_scope=replan_scope,
    )


def _pipeline(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    *,
    writer_provider: Any,
    planner_provider: Any,
    director_provider: Any,
    resolver_provider: Any,
    action_duration_ticks: int = 7,
) -> Pipeline:
    return Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=writer_provider,
        planner_provider=planner_provider,
        director_provider=director_provider,
        resolver_provider=resolver_provider,
        action_duration_ticks=action_duration_ticks,
    )


def _cognition(*narration: str, viewer: str = ACTOR) -> V3CognitionView:
    return V3CognitionView(
        viewer_id=viewer,
        public=(),
        witnessed=tuple(
            V3CognitionEvent(
                event_id=f"e{index}",
                kind="SEGMENT",
                narration=text,
                participants=(viewer,),
                actual_start_tick=index,
                actual_end_tick=index,
            )
            for index, text in enumerate(narration, start=1)
        ),
    )


def _memory(*content: str, viewer: str = ACTOR) -> V3MemoryView:
    return V3MemoryView(
        viewer_id=viewer,
        memories=tuple(
            ActorMemoryRecord(
                memory_id=f"mem:{index}",
                world_id=TOWN,
                participant_id=viewer,
                kind=MemoryKind.EXPERIENCED,
                content=text,
                source_event_id=f"e{index}",
                learned_at_tick=index,
                salience=None,
                created_at=NOW,
                updated_at=NOW,
                state_version=1,
            )
            for index, text in enumerate(content, start=1)
        ),
    )


def _pov_context(
    *,
    must_hide: str = "the priced tools",
    cognition: V3CognitionView | None = None,
    memory: V3MemoryView | None = None,
) -> PovContext:
    return PovContext(
        scene_id=SCENE,
        segment_seq=2,
        pov_actor_id=ACTOR,
        participants=(ACTOR, PLAYER),
        place="the bindery steps",
        entry_goals="greet the newcomer",
        exit_condition="the greeting lands or breaks",
        revealable="the ledger's back page",
        must_hide=must_hide,
        current_tick=3,
        cognition=cognition or _cognition("the door opens"),
        memory=memory or _memory("she kept the ledger close"),
    )


def _scene_plan_context() -> ScenePlanContext:
    return ScenePlanContext(
        world_id=TOWN,
        scene_id=SCENE,
        pov_actor_id=ACTOR,
        current_tick=3,
        element=None,
        cognition=_cognition("the door opens"),
        memory=_memory("she kept the ledger close"),
    )


def _resolver_context(
    *,
    player: Any = None,
    player_cognition: V3CognitionView | None = None,
    player_memory: V3MemoryView | None = None,
    counterparts: tuple[Any, ...] = (),
    current_facts: tuple[Any, ...] = (),
    bible: Any = None,
) -> ResolverContext:
    return ResolverContext(
        gate_id=GATE,
        scene_id=SCENE,
        submission_id="sub-1",
        intent_text=INTENT,
        selected_option=None,
        options=("hold the ledger", "step back"),
        bible=bible,
        current_facts=current_facts,
        player_character=player,
        place="the bindery steps",
        participants=(ACTOR, PLAYER),
        counterparts=counterparts,
        player_cognition=player_cognition,
        player_memory=player_memory,
        pov_actor_id=ACTOR,
        cognition=_cognition("the door opens"),
        memory=_memory("she kept the ledger close"),
        current_tick=3,
    )


# ---------------------------------------------------------------------------
# 1. the seam and the four implementations
# ---------------------------------------------------------------------------


def test_the_seam_outcome_is_a_frozen_value() -> None:
    """The seam's answer shape: ``text`` plus the body-free ``error``,
    frozen, ``error`` defaulting to ``None`` — the persona
    ``ProviderOutput`` posture re-cut without the body."""

    assert dataclasses.is_dataclass(CompletionOutcome)
    names = tuple(field.name for field in dataclasses.fields(CompletionOutcome))
    assert names == ("text", "error")
    outcome = CompletionOutcome(text="prose")
    assert outcome.error is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.text = "rewritten"  # type: ignore[misc]


def test_the_four_llm_providers_satisfy_the_protocols() -> None:
    """Structural conformance against the frozen Protocols — one seam
    instance, four faces, no inheritance (the Protocol is the
    contract)."""

    stub = _ScriptedCompletion()
    assert isinstance(LlmWriterProvider(stub), WriterProvider)
    assert isinstance(LlmPlannerProvider(stub), PlannerProvider)
    assert isinstance(LlmDirectorProvider(stub), DirectorProvider)
    assert isinstance(LlmResolverProvider(stub), ResolverProvider)


def test_the_writer_refuses_an_empty_answer_with_no_output() -> None:
    """An empty (whitespace-only) answer is the honest ``no-output``
    refusal — the writer arm never hands a blank body down."""

    stub = _ScriptedCompletion(CompletionOutcome(text="  \n "))
    provider = LlmWriterProvider(stub)
    with pytest.raises(LlmProviderError) as refused:
        provider.write_segment(_pov_context())
    assert refused.value.reason == "no-output"


def test_the_seam_error_raises_transport_error_without_the_prompt() -> None:
    """A seam ``error`` value becomes the ``transport-error`` refusal;
    the message is the code alone — the prompt (or anything the
    transport echoed) never rides through."""

    prompt_marker = "SENTINEL-PROMPT-CONTENT"
    stub = _ScriptedCompletion(
        CompletionOutcome(
            text=None, error=f"stub exploded while reading {prompt_marker}"
        )
    )
    provider = LlmResolverProvider(stub)
    with pytest.raises(LlmProviderError) as refused:
        provider.adjudicate(_resolver_context())
    assert refused.value.reason == "transport-error"
    assert str(refused.value) == "transport-error"
    assert prompt_marker not in str(refused.value)
    # the seam was called with the full prompt, which the refusal does
    # not echo (the prompt itself works as the sentinel's carrier).
    assert len(stub.prompts) == 1


# ---------------------------------------------------------------------------
# 2. the Writer arm
# ---------------------------------------------------------------------------


def test_the_writer_prompt_lists_the_plan_face_and_the_knowledge() -> None:
    """The Writer prompt: the system instructions (one POV, no decisions
    for the user, no future, English), the plan face with ``must_hide``
    itemized as hard prohibitions, and the POV's own cognition / memory
    — plus the segment's own numbers; the answer is cleaned prose."""

    stub = _ScriptedCompletion(
        CompletionOutcome(text="```\nThe bell answers first.\n```")
    )
    provider = LlmWriterProvider(stub)
    body = provider.write_segment(
        _pov_context(
            must_hide="the priced tools。the second secret",
            memory=_memory("she kept the ledger close", "MEMENTO-TEXT"),
        )
    )
    assert body == "The bell answers first."  # fence + whitespace stripped
    prompt = stub.prompts[0]
    for expected in (
        "Write the segment's prose in English",
        "One main point of view",
        "the user's own will is not yours to invent",
        "never narrate the",
        "the bindery steps",
        "greet the newcomer",
        "the greeting lands or breaks",
        "the ledger's back page",
        "  - the priced tools",
        "  - the second secret",
        "segment_seq: 2",
        "current_tick: 3",
        f"participants: {ACTOR}, {PLAYER}",
        "(witnessed) the door opens",
        "(EXPERIENCED) MEMENTO-TEXT",
    ):
        assert expected in prompt, expected


def test_the_writer_prompt_cannot_carry_another_viewers_private_faces(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The POV-safe hard door, behaviorally, at the prompt: Bram's scene
    commits an event his memory alone holds; Lia's scene is then driven
    through the LLM writer, and the prompts her provider received carry
    nothing of Bram's — while Bram's own memory view does hold the
    event (the contrast witness)."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(
        director.open_next_chapter(
            TOWN,
            _blueprint(
                scenes=[
                    _scene_draft(),
                    _scene_draft(
                        pov=PARTNER,
                        participants=(PARTNER,),
                        purpose="the tide watch",
                    ),
                ]
            ),
            NOW,
        ),
        Ok,
    )
    stub = _ScriptedCompletion(
        _prose(BRAM_SECRET_EVENT), _prose(PROSE_1), _prose(PROSE_2)
    )
    writer = LlmWriterProvider(stub)
    pipeline = _pipeline(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        writer_provider=writer,
        planner_provider=DeterministicFakeProvider(),
        director_provider=DeterministicFakeProvider(),
        resolver_provider=DeterministicFakeProvider(),
    )
    bram_drive = pipeline.run_scene(
        SCENE2, (SegmentBeat(duration_ticks=1, is_last_segment=True),), NOW
    )
    assert isinstance(bram_drive, Ok)
    lia_drive = pipeline.run_scene(
        SCENE,
        (
            SegmentBeat(duration_ticks=3),
            SegmentBeat(duration_ticks=2, is_last_segment=True),
        ),
        LATER,
    )
    assert isinstance(lia_drive, Ok)
    bram_prompt, first_prompt, second_prompt = stub.prompts
    # Bram's own prompt addresses him and lists his scene's plan.
    assert PARTNER in bram_prompt
    # Lia's prompts: the plan face's prohibitions ride, her own first
    # event comes back as her memory — and none of Bram's faces do.
    assert "  - the priced tools" in first_prompt
    assert "  - the priced tools" in second_prompt
    assert "(EXPERIENCED) " + PROSE_1 in second_prompt
    assert PROSE_1 not in first_prompt  # nothing yet at the first segment
    for context_prompt in (first_prompt, second_prompt):
        assert BRAM_SECRET_EVENT not in context_prompt
        assert BRAM_PRIVATE not in context_prompt
        assert LIA_PRIVATE not in context_prompt
    # the contrast witness: Bram's own memory does hold his event — the
    # record exists; Lia's compiled input simply cannot carry it.
    bram_view = v3_memory_view(conn, world_id=TOWN, viewer_id=PARTNER)
    assert isinstance(bram_view, Ok)
    assert [row.content for row in bram_view.value.memories] == [
        BRAM_SECRET_EVENT
    ]


# ---------------------------------------------------------------------------
# 3. the parsing law
# ---------------------------------------------------------------------------


def _element_payload() -> dict[str, Any]:
    element = _scene_draft()
    del element["purpose"]
    return element


def test_the_planner_parses_the_element_payload_in_its_shape() -> None:
    """A well-formed element answer comes back in the canonical shape
    (the nine keys; participants a tuple of strings) — and the prompt
    asked for exactly the JSON object it got."""

    stub = _ScriptedCompletion(_answer(_element_payload()))
    provider = LlmPlannerProvider(stub)
    parsed = provider.plan_scene(_scene_plan_context())
    assert dict(parsed) == {
        "pov_actor_id": ACTOR,
        "participants": (ACTOR, PLAYER),
        "planned_start_tick": 0,
        "place": "the bindery steps",
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "may run long if you linger",
        "revealable": "the ledger's back page",
        "must_hide": "the priced tools",
    }
    prompt = stub.prompts[0]
    for expected in (
        "one JSON object",
        '"pov_actor_id"',
        '"must_hide"',
        f"Scene: {SCENE}",
        f"POV: {ACTOR}",
        "(EXPERIENCED) she kept the ledger close",
    ):
        assert expected in prompt, expected


def test_the_planner_refusals_name_the_reason() -> None:
    """Malformed planner answers refuse with the named body-free codes —
    bad JSON, a non-object, a missing key, a wrong type and emptiness."""

    cases = (
        ("not json at all", "bad-payload"),
        ("[]", "bad-payload"),
        ('"just a string"', "bad-payload"),
        ("", "no-output"),
    )
    for text, reason in cases:
        provider = LlmPlannerProvider(
            _ScriptedCompletion(CompletionOutcome(text=text))
        )
        with pytest.raises(LlmProviderError) as refused:
            provider.plan_scene(_scene_plan_context())
        assert refused.value.reason == reason, text
    missing = _element_payload()
    del missing["place"]
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(_answer(missing))
        ).plan_scene(_scene_plan_context())
    assert refused.value.reason == "missing-field:place"
    wrong = _element_payload()
    wrong["planned_start_tick"] = "soon"
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(_answer(wrong))
        ).plan_scene(_scene_plan_context())
    assert refused.value.reason == "bad-shape"
    words = _element_payload()
    words["participants"] = [ACTOR, 7]
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(_answer(words))
        ).plan_scene(_scene_plan_context())
    assert refused.value.reason == "bad-shape"


def test_the_fence_wrapper_is_stripped_once_and_only_once() -> None:
    """The deterministic minimal cleaning: one surrounding fence (bare
    or ``json``-tagged, with newlines) comes off; a fence that does not
    fit the rule rides on to fail, and extra keys in the payload are
    ignored (tolerance, never a second schema)."""

    fenced = f"```json\n{json.dumps(_element_payload())}\n```"
    parsed = LlmPlannerProvider(
        _ScriptedCompletion(CompletionOutcome(text=fenced))
    ).plan_scene(_scene_plan_context())
    assert parsed["place"] == "the bindery steps"
    one_line = f"```json {json.dumps(_element_payload())}```"
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(CompletionOutcome(text=one_line))
        ).plan_scene(_scene_plan_context())
    assert refused.value.reason == "bad-payload"
    prefaced = f"Here you go: {json.dumps(_element_payload())}"
    with pytest.raises(LlmProviderError) as refused:
        LlmPlannerProvider(
            _ScriptedCompletion(CompletionOutcome(text=prefaced))
        ).plan_scene(_scene_plan_context())
    assert refused.value.reason == "bad-payload"
    extra = _element_payload()
    extra["scene_ref"] = 1
    parsed = LlmPlannerProvider(
        _ScriptedCompletion(_answer(extra))
    ).plan_scene(_scene_plan_context())
    assert "scene_ref" not in parsed  # keys beyond the set are ignored


def test_the_planner_replan_prompt_carries_the_current_element() -> None:
    """The SCENE replan arm's prompt starts from the current plan
    content (the derived element mapping's own nine keys) and says the
    revision follows what already happened."""

    element = {
        "pov_actor_id": ACTOR,
        "participants": [ACTOR, PLAYER],
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
    provider = LlmPlannerProvider(stub)
    parsed = provider.replan_element(context)
    assert parsed["place"] == "the counter"
    prompt = stub.prompts[0]
    assert "must be revised" in prompt
    assert '"place":"the counter"' in prompt  # the current content rides
    assert "the names on the last page" in prompt


# ---------------------------------------------------------------------------
# 4. the Director arm
# ---------------------------------------------------------------------------


def test_the_director_parses_and_refuses_the_blueprint_payload(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    director: Director,
) -> None:
    """The Director arm: a well-formed Blueprint answer parses in the
    chapter's nine-field shape with ten-key scene elements; malformed
    answers refuse with the nested coordinates named."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    context = DirectorPlanContext(
        director_context=director.context(TOWN),
        chapter_id=None,
        replan_request_id=None,
        trigger=None,
        blueprint=None,
    )
    stub = _ScriptedCompletion(_answer(_blueprint()))
    parsed = LlmDirectorProvider(stub).draft_blueprint(context)
    assert parsed == {
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
                "pov_actor_id": ACTOR,
                "participants": (ACTOR, PLAYER),
                "planned_start_tick": 0,
                "place": "the bindery steps",
                "entry_goals": "greet the newcomer",
                "exit_condition": "the greeting lands or breaks",
                "elasticity": "may run long if you linger",
                "revealable": "the ledger's back page",
                "must_hide": "the priced tools",
                "purpose": "first sight",
            }
        ],
    }
    prompt = stub.prompts[0]
    for expected in (
        "a non-empty array of scene elements",
        "exactly these ten keys",
        "a soft expectation, never a postcondition",
        "No soft expectation may be written as a hard condition",
        f"- world: {TOWN}",
        HARD_RULE,
        "a newcomer off the evening coach",
        "steady hands",
        "no training with steel",
        "keep the shop open a winter longer",
    ):
        assert expected in prompt, expected
    assert "(no player character is declared for this world)" not in prompt
    # malformed: a missing chapter field, an empty scene table, a scene
    # element missing its purpose, a wrong tick type.
    missing = _blueprint()
    del missing["goal"]
    with pytest.raises(LlmProviderError) as refused:
        LlmDirectorProvider(
            _ScriptedCompletion(_answer(missing))
        ).draft_blueprint(context)
    assert refused.value.reason == "missing-field:goal"
    empty = _blueprint(scenes=[])
    with pytest.raises(LlmProviderError) as refused:
        LlmDirectorProvider(
            _ScriptedCompletion(_answer(empty))
        ).draft_blueprint(context)
    assert refused.value.reason == "bad-shape"
    no_purpose = _blueprint()
    del no_purpose["scenes"][0]["purpose"]
    with pytest.raises(LlmProviderError) as refused:
        LlmDirectorProvider(
            _ScriptedCompletion(_answer(no_purpose))
        ).draft_blueprint(context)
    assert refused.value.reason == "missing-field:scenes[0].purpose"
    bad_tick = _blueprint()
    bad_tick["planned_end_tick"] = True
    with pytest.raises(LlmProviderError) as refused:
        LlmDirectorProvider(
            _ScriptedCompletion(_answer(bad_tick))
        ).draft_blueprint(context)
    assert refused.value.reason == "bad-shape"


def test_the_director_replan_prompt_carries_the_trigger_and_blueprint(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The CHAPTER replan arm's prompt: the committed ruling's own words
    (intent / outcome / consequences — read from the durable row, never
    an invention) and the current Blueprint the revision starts from."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(director.open_next_chapter(TOWN, _blueprint(), NOW), Ok)
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    assert isinstance(
        open_gate(
            conn,
            scene_id=SCENE,
            gate_seq=1,
            options=("hold the ledger", "step back"),
            now=NOW,
        ),
        Ok,
    )
    assert isinstance(
        submit_gate(
            conn,
            gate_id=GATE,
            submission_id="sub-1",
            intent_text=INTENT,
            now=NOW,
        ),
        Ok,
    )
    assert isinstance(begin_resolving(conn, gate_id=GATE, now=LATER), Ok)
    committed = commit_action(
        conn,
        world_store=world_store,
        narrative_store=narrative,
        gate_id=GATE,
        submission_id="sub-1",
        adjudication=_ruling(replan_scope=ReplanScope.CHAPTER),
        duration_ticks=7,
        now=LATER,
    )
    assert isinstance(committed, Ok)
    trigger = action_by_id(conn, f"{GATE}-a")
    assert trigger is not None
    request = replan_request_id_for(GATE, "sub-1")
    context = DirectorPlanContext(
        director_context=director.context(TOWN),
        chapter_id=CH,
        replan_request_id=request,
        trigger=trigger,
        blueprint=_blueprint(),
    )
    stub = _ScriptedCompletion(_answer(_blueprint()))
    parsed = LlmDirectorProvider(stub).replan_blueprint(context)
    assert parsed["goal"] == "the newcomer and the shopkeeper truly meet"
    prompt = stub.prompts[0]
    for expected in (
        f"- chapter: {CH}",
        f"- replan_request_id: {request}",
        "the committed ruling that invalidated the plan",
        INTENT,
        "Lia lets you hold the ledger; the ice thins.",
        "the shop's silence opens one notch",
        "the chapter's current Blueprint",
        '"goal":"the newcomer and the shopkeeper truly meet"',
    ):
        assert expected in prompt, expected


# ---------------------------------------------------------------------------
# 5. the Resolver arm
# ---------------------------------------------------------------------------


def test_the_resolver_prompt_carries_the_world_authority_and_the_knowledge(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The world-authoritative prompt a real drive compiles: the Bible's
    hard rules, the settled facts, the player's abilities / limits, the
    counterpart's profile, the player character's own knowledge arm
    (the user's EXPERIENCED memory), the POV's narrative face and the
    submission's full intent — and the answer lands as the ruling."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(director.open_next_chapter(TOWN, _blueprint(), NOW), Ok)
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    # the user's own event: the player alone lived it (the POV did not)
    # — settled with an inventory claim so the fact half is non-empty.
    first = commit_segment(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        scene_id=SCENE,
        segment_seq=1,
        body=PLAYER_EVENT,
        language="en",
        participants=(PLAYER,),
        effects=(
            StateEffect(key="inventory:pc-you", statement="a borrowed ledger"),
        ),
        narration=PLAYER_EVENT,
        duration_ticks=3,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(first, Ok)
    stub = _ScriptedCompletion(_answer(_adjudication_payload()))
    pipeline = _pipeline(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        writer_provider=DeterministicFakeProvider(),
        planner_provider=DeterministicFakeProvider(),
        director_provider=DeterministicFakeProvider(),
        resolver_provider=LlmResolverProvider(stub),
    )
    driven = pipeline.run_scene(
        SCENE,
        (
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text=INTENT,
            ),
        ),
        LATER,
    )
    assert isinstance(driven, Ok)
    action = action_of(conn, GATE)
    assert action is not None
    assert action.interpretation == "You mean to help rather than to buy."
    assert action.outcome == "Lia lets you hold the ledger; the ice thins."
    assert action.actual_action == "you carry the ledger to the counter"
    assert action.consequences == "the shop's silence opens one notch"
    assert action.state_effects == (
        StateEffect(key="trust:lia", statement="warmed by one notch"),
    )
    assert action.participants == (PLAYER, ACTOR)
    assert action.replan_scope is ReplanScope.NONE
    prompt = stub.prompts[0]
    for expected in (
        "the user's intent, not a world fact",
        HARD_RULE,
        "inventory:pc-you: a borrowed ledger",
        "steady hands",
        "no training with steel",
        LIA_PRIVATE,
        "what the user's character knows",
        "(EXPERIENCED) " + PLAYER_EVENT,
        f"the scene's narrative POV ({ACTOR})",
        INTENT,
        "hold the ledger, step back",
    ):
        assert expected in prompt, expected


def test_the_resolver_refusals_name_the_reason() -> None:
    """Malformed verdicts refuse with the named codes: missing keys,
    wrong types, a bad nested effect and an out-of-vocabulary
    ``replan_scope``."""

    provider = LlmResolverProvider(_ScriptedCompletion(_answer({})))
    with pytest.raises(LlmProviderError) as refused:
        provider.adjudicate(_resolver_context())
    assert refused.value.reason == "missing-field:interpretation"
    missing = _adjudication_payload()
    del missing["outcome"]
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(
            _ScriptedCompletion(_answer(missing))
        ).adjudicate(_resolver_context())
    assert refused.value.reason == "missing-field:outcome"
    bad_effects = _adjudication_payload()
    bad_effects["state_effects"] = {"key": "k", "statement": "s"}
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(
            _ScriptedCompletion(_answer(bad_effects))
        ).adjudicate(_resolver_context())
    assert refused.value.reason == "bad-shape"
    bad_effect = _adjudication_payload()
    bad_effect["state_effects"] = [{"key": "k"}]
    with pytest.raises(LlmProviderError) as refused:
        LlmResolverProvider(
            _ScriptedCompletion(_answer(bad_effect))
        ).adjudicate(_resolver_context())
    assert refused.value.reason == "missing-field:state_effects[0].statement"
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
    # the three words that DO stand parse to their enum.
    for word, expected in (
        ("NONE", ReplanScope.NONE),
        ("SCENE", ReplanScope.SCENE),
        ("CHAPTER", ReplanScope.CHAPTER),
    ):
        payload = _adjudication_payload()
        payload["replan_scope"] = word
        ruling = LlmResolverProvider(
            _ScriptedCompletion(_answer(payload))
        ).adjudicate(_resolver_context())
        assert ruling.replan_scope is expected
        assert ruling.state_effects == (
            StateEffect(key="trust:lia", statement="warmed by one notch"),
        )
        assert ruling.participants == (PLAYER, ACTOR)


# ---------------------------------------------------------------------------
# 6. the end-to-end wiring: a minimal Gold-shaped chain
# ---------------------------------------------------------------------------


def test_the_minimal_gold_chain_runs_through_the_llm_providers(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
) -> None:
    """create → plan_chapter (the Director stub's Blueprint) → run_scene
    (the Writer stub's prose, the Resolver stub's verdict) → settle:
    the canonical rows and numbers of the deterministic chain, with
    every production face behind the real LLM providers."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    writer_stub = _ScriptedCompletion(_prose(PROSE_1), _prose(PROSE_2))
    resolver_stub = _ScriptedCompletion(_answer(_adjudication_payload()))
    director_stub = _ScriptedCompletion(_answer(_blueprint()))
    pipeline = _pipeline(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        writer_provider=LlmWriterProvider(writer_stub),
        planner_provider=LlmPlannerProvider(_ScriptedCompletion()),
        director_provider=LlmDirectorProvider(director_stub),
        resolver_provider=LlmResolverProvider(resolver_stub),
    )
    planned = pipeline.plan_chapter(TOWN, NOW)
    assert isinstance(planned, Ok)
    assert planned.value.chapter.chapter_id == CH
    driven = pipeline.run_scene(
        SCENE,
        (
            SegmentBeat(duration_ticks=3),
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text=INTENT,
            ),
            SegmentBeat(duration_ticks=2, is_last_segment=True),
        ),
        NOW,
    )
    assert isinstance(driven, Ok)
    run = driven.value
    assert [outcome.actual_end_tick for outcome in run.segments] == [3, 12]
    assert len(run.gates) == 1
    assert run.gates[0].gate_id == GATE
    assert run.gates[0].status is GateStatus.CLOSED
    assert run.replans == ()
    assert [outcome.actual_end_tick for outcome in run.actions] == [10]
    # the stub prose is what the lineage carries.
    bodies = [
        str(row[0])
        for row in conn.execute(
            "SELECT body FROM narrative_passage ORDER BY passage_id"
        ).fetchall()
    ]
    assert bodies == [PROSE_1, PROSE_2]
    assert (
        conn.execute("SELECT COUNT(*) FROM segment_commit").fetchone()[0] == 3
    )
    assert conn.execute("SELECT COUNT(*) FROM world_event").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM actor_memory").fetchone()[0] == 6
    fact = conn.execute(
        "SELECT statement FROM world_state_fact WHERE status = 'CURRENT'"
    ).fetchone()
    assert fact is not None and str(fact[0]) == "warmed by one notch"
    tick = read_current_tick(conn, TOWN)
    assert isinstance(tick, Ok)
    assert tick.value == 12
    settled = pipeline.settle(CH, LATER)
    assert isinstance(settled, Ok)
    chapter = narrative.get_chapter(CH)
    assert chapter is not None and chapter.status.value == "CLOSED"
    # the three stubs each received their arm's prompts.
    assert len(director_stub.prompts) == 1
    assert "- current_tick: 0" in director_stub.prompts[0]
    assert len(writer_stub.prompts) == 2
    assert len(resolver_stub.prompts) == 1
    assert INTENT in resolver_stub.prompts[0]


# ---------------------------------------------------------------------------
# 7. F4 — the player character's own knowledge arms
# ---------------------------------------------------------------------------


def test_the_resolver_context_f4_carries_the_users_own_memories(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """F4, materially: the player alone lived an event; the compiled
    resolver context's ``player_cognition`` / ``player_memory`` are
    addressed to the player character and carry it — while the POV's
    read stays the scene's own (Lia's)."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    assert isinstance(director.open_next_chapter(TOWN, _blueprint(), NOW), Ok)
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    first = commit_segment(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        scene_id=SCENE,
        segment_seq=1,
        body=PLAYER_EVENT,
        language="en",
        participants=(PLAYER,),
        effects=(),
        narration=PLAYER_EVENT,
        duration_ticks=3,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(first, Ok)
    # the read faces as they stand when the drive compiles the context
    # (the segment is the only event so far — the ruling lands later).
    cognition_view = v3_cognition_view(
        conn, world_id=TOWN, viewer_id=PLAYER
    )
    assert isinstance(cognition_view, Ok)
    memory_view = v3_memory_view(conn, world_id=TOWN, viewer_id=PLAYER)
    assert isinstance(memory_view, Ok)
    fake = DeterministicFakeProvider(adjudications={GATE: _ruling()})
    pipeline = _pipeline(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        writer_provider=fake,
        planner_provider=fake,
        director_provider=fake,
        resolver_provider=fake,
    )
    driven = pipeline.run_scene(
        SCENE,
        (
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text=INTENT,
            ),
        ),
        LATER,
    )
    assert isinstance(driven, Ok)
    context = fake.resolver_contexts[0]
    assert context.player_character is not None
    assert context.player_cognition is not None
    assert context.player_cognition.viewer_id == PLAYER
    assert context.player_memory is not None
    assert context.player_memory.viewer_id == PLAYER
    assert [row.content for row in context.player_memory.memories] == [
        PLAYER_EVENT
    ]
    # the compiled arm is exactly the read face of the player's identity
    # (as it stood when the drive compiled the context).
    assert context.player_cognition == cognition_view.value
    assert context.player_memory == memory_view.value
    # the POV's arm is separately addressed — the narrative face.
    assert context.pov_actor_id == ACTOR
    assert context.cognition.viewer_id == ACTOR
    assert context.memory.viewer_id == ACTOR
    assert [row.content for row in context.memory.memories] == []


def test_the_resolver_context_keeps_the_player_arms_none_without_a_player(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
    planner: ScenePlanner,
) -> None:
    """The F4 conditional law: a world that declares no player compiles
    both knowledge arms ``None`` (the same law the ``player_character``
    arm keeps) — and the drive's told refusal is the world's own (a
    user action fact carries the user; there is none to carry)."""

    assert isinstance(
        _create_town(
            conn, world_store, cast_store, bible_store, player=None
        ),
        Ok,
    )
    assert isinstance(
        director.open_next_chapter(
            TOWN,
            _blueprint(
                scenes=[_scene_draft(participants=(ACTOR,))]
            ),
            NOW,
        ),
        Ok,
    )
    assert isinstance(planner.open_scene(SCENE, NOW), Ok)
    fake = DeterministicFakeProvider(
        adjudications={
            GATE: _ruling(participants=(ACTOR,), replan_scope=ReplanScope.NONE)
        }
    )
    pipeline = _pipeline(
        conn,
        world_store,
        cast_store,
        bible_store,
        narrative,
        writer_provider=fake,
        planner_provider=fake,
        director_provider=fake,
        resolver_provider=fake,
    )
    driven = pipeline.run_scene(
        SCENE,
        (
            GateBeat(
                gate_seq=1,
                options=("hold the ledger", "step back"),
                submission_id="sub-1",
                intent_text=INTENT,
            ),
        ),
        LATER,
    )
    assert isinstance(driven, Err)
    assert "declares no user role" in driven.error.message
    context = fake.resolver_contexts[0]
    assert context.player_character is None
    assert context.player_cognition is None
    assert context.player_memory is None
    # the POV face still rides (the scene's own read).
    assert context.pov_actor_id == ACTOR
    assert context.memory.viewer_id == ACTOR
    assert get_gate(conn, GATE) is not None  # the rows are the honest record


# ---------------------------------------------------------------------------
# 8. the discipline pins
# ---------------------------------------------------------------------------


def _all_constants(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def _sql_constants(tree: ast.AST) -> list[str]:
    return [
        text
        for text in _all_constants(tree)
        if re.match(r"(?i)^\s*(select|insert|update|delete)\b", text)
    ]


def test_the_llm_module_holds_no_transaction_sql_or_clock() -> None:
    """The discipline at rest: no ``sqlite3``, no transaction constant,
    no SQL-shaped constant, no ``execute`` / commit / rollback call and
    no clock — and no ``elc.persona`` edge in any form (the seam is
    where the assembly face adapts the BYOK egress)."""

    for text in _all_constants(LLM_TREE):
        assert text not in {"BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"}, text
    assert _sql_constants(LLM_TREE) == []
    for node in ast.walk(LLM_TREE):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
                "now",
                "time",
            }, ast.dump(node)
    plain_imports = {
        alias.name.split(".")[0]
        for node in ast.walk(LLM_TREE)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert plain_imports <= {"json", "re"}, plain_imports
    modules = [
        node.module or ""
        for node in ast.walk(LLM_TREE)
        if isinstance(node, ast.ImportFrom)
    ]
    for module in modules:
        assert not module.startswith("elc.persona"), module
        if module.startswith("elc."):
            assert module.startswith("elc.world."), module


def test_the_llm_module_starts_cold_and_is_not_re_exported() -> None:
    """The P4-3 cold-start discipline and the narrow-module precedent:
    the module imports in a fresh interpreter, and the package root does
    not re-export it."""

    source = (SRC_ROOT / "world" / "__init__.py").read_text(encoding="utf-8")
    for keyword in (
        "llm_providers",
        "LlmWriterProvider",
        "LlmPlannerProvider",
        "LlmDirectorProvider",
        "LlmResolverProvider",
    ):
        assert keyword not in source, keyword
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO / "src"),
    )
    proc = subprocess.run(
        [sys.executable, "-c", "import elc.world.llm_providers"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr


def test_the_ledger_carries_the_v3_8c_entries() -> None:
    """AOCI maintenance, pinned: the new module rides its own entry and
    the two touched entries (``providers.py`` / ``pipeline.py``) carry
    the F4 faces this cut owns."""

    lines = AOCI_FILE.read_text(encoding="utf-8").split("\n")
    for tag, keywords in (
        (
            "llm_providers.py[",
            (
                "TextCompletion",
                "CompletionOutcome",
                "LlmWriterProvider",
                "LlmPlannerProvider",
                "LlmDirectorProvider",
                "LlmResolverProvider",
                "POV-safe",
                "V3-8c",
            ),
        ),
        (
            "providers.py[PV8T]",
            ("player_cognition", "player_memory", "V3-8c"),
        ),
        (
            "pipeline.py[PL8T]",
            ("player_cognition", "player_memory", "V3-8c"),
        ),
    ):
        hits = [line for line in lines if line.startswith(tag)]
        assert len(hits) == 1, (tag, len(hits))
        for keyword in keywords:
            assert keyword in hits[0], (tag, keyword)
