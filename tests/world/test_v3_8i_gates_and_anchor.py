"""V3-8i — the gate-production face, the player-character anchoring and
the gateless floor's pure faces (the paradigm shift §10.6; the reading
face's serving-stack pins ride ``tests/host/test_v3_8i_reader_floor.py``).

Pinned here (every prompt pin rides the real provider execution arm —
the stub records the prompt the provider actually built; no pin reads a
private function's return in place of the driven path, the V3-8e F2
anti-vacuum law):

1. the Director prompt states the gate-production law (§10.6 item 1) —
   ``required_beats`` with at least one gate beat (a §2.5 stop reason
   and 2–4 natural options) and ``user_present``, en at the default and
   zh at the switch, once per prompt;
2. the parser carries the declared gate face verbatim (shape-checked:
   a non-list ``required_beats`` and a non-bool ``user_present`` are
   ``bad-shape``) and rides ten-key answers through unchanged;
3. the judge (:func:`elc.world.director.blueprint_gate_refusal`) names
   the first scene that declares the shape without carrying a gate;
4. the judge's scope is the declared shape — a pure ten-key payload
   answers ``None`` (the canonical freeze; the deterministic baselines
   ride), one declared scene flips the whole payload into judgment;
5. the seat refuses (``open_next_chapter`` at ``require_gates``,
   nothing written) and the production planner re-casts **once**
   (``require_plan_gates``: two drafts consumed, the second landing;
   two refusals answered as the honest ``VALIDATION_FAILED``; the
   default pipeline single-drafts exactly as before);
6. the player anchor (§10.6 item 2) on all three participant-rendering
   arms — Writer / Scene Planner / Resolver — en and zh, **pure
   addition** (the prompt without an id equals the anchored prompt
   minus the one anchor line; the participants lines stay byte for
   byte);
7. the plan's gate beats become the scene's script (the derivation
   laws: plan order, ``gate_seq`` 1..k, the open-scene tick, the
   closing-segment terminal law, the gold author script winning first)
   — the walk reads a real adopted plan and stops at its gate beat;
8. the floor's constant and sentence (§10.6 item 3 — the reasoned
   stop's own words).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err, Ok
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.bootstrap import ActorSeed, PlayerSeed, create_world_with_bible
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.director import Director, blueprint_gate_refusal
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmDirectorProvider,
    LlmPlannerProvider,
    LlmProviderError,
    LlmResolverProvider,
    LlmWriterProvider,
)
from elc.world.narrative import SqliteNarrativeStore
from elc.world.pipeline import GateBeat, Pipeline, SegmentBeat
from elc.world.providers import (
    DeterministicFakeProvider,
    PovContext,
    ResolverContext,
    ScenePlanContext,
)
from elc.world.scene import ScenePlanner
from elc.world.store import SqliteWorldStore

NOW = "2026-10-14T00:00:00+00:00"

TOWN = "world-town"
CH = "world-town-ch01"
SCENE = "world-town-ch01-s01"
SCENE2 = "world-town-ch01-s02"
ACTOR = "actor-lia"
PARTNER = "actor-bram"
PLAYER = "pc-you"

EN_ANCHOR = (
    "- the player character: pc-you — the reader's own character;"
    " never make decisions, speak or act with intent for them:"
    " their significant acts of will enter the story only through"
    " a User Gate."
)
ZH_ANCHOR = (
    "- 玩家角色：pc-you——读者自己的角色；绝不替他们做决定、说话或行动："
    "他们显著的意志行为只会经用户意志门（User Gate）进入故事。"
)


class _ScriptedCompletion:
    """A deterministic :class:`TextCompletion` stub: answers its
    scripted outcomes in call order, records every prompt it received,
    and raises when called past its script — the fake's scripted-gap
    posture, at the seam."""

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


# ---------------------------------------------------------------------------
# fixtures / helpers (the V3-8c suites' own shapes)
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


def _create_town(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> Ok[Any]:
    """The town seed: two AI actors and the reader's character (the
    anchoring pins need a player the namespace names)."""

    _insert_card(conn, "persona-lia", "Lia")
    _insert_card(conn, "persona-bram", "Bram")
    conn.commit()
    return create_world_with_bible(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=TOWN,
        name="Town",
        bible_revision_id=f"{TOWN}-bible-r1",
        bible=BibleContent(
            premise="the town by the water",
            hard_rules="steel is never drawn indoors",
        ),
        actors=(
            ActorSeed(
                actor_id=ACTOR,
                persona_id="persona-lia",
                story_role=StoryRole.PROTAGONIST,
                pov_eligible=True,
                pov_weight=1,
                long_term_drive="keep the shop open a winter longer",
                private_context="LIA_PRIVATE",
            ),
            ActorSeed(
                actor_id=PARTNER,
                persona_id="persona-bram",
                story_role=StoryRole.SUPPORTING,
                pov_eligible=True,
                pov_weight=2,
                long_term_drive="hold the tide schedule",
                private_context="BRAM_PRIVATE",
            ),
        ),
        player=PlayerSeed(
            player_character_id=PLAYER,
            name="You",
            background="a newcomer off the evening coach",
            abilities="steady hands",
            limits="no training with steel",
            location="the inn",
            state="tired",
        ),
        now=NOW,
    )


def _scene_draft(
    *,
    pov: str = ACTOR,
    participants: tuple[str, ...] = (ACTOR, PLAYER),
    purpose: str = "first sight",
    place: str = "the bindery steps",
    **extra: Any,
) -> dict[str, Any]:
    element: dict[str, Any] = {
        "purpose": purpose,
        "place": place,
        "pov_actor_id": pov,
        "participants": list(participants),
        "planned_start_tick": 0,
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "the greeting may fail",
        "revealable": "the ledger's back page",
        "must_hide": "the priced tools",
    }
    element.update(extra)
    return element


def _beats(*beats: dict[str, Any]) -> list[dict[str, Any]]:
    return list(beats)


def _segment_beat() -> dict[str, Any]:
    return {"kind": "segment"}


def _gate_beat(
    *,
    reason: str = "whether she takes the stranger in is the reader's own"
    " will",
    options: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "gate",
        "reason": reason,
        "options": options
        if options is not None
        else ["take the stranger in", "turn them away", "ask a price"],
    }


def _gated_scene(**kwargs: Any) -> dict[str, Any]:
    """One scene element carrying the declared, compliant gate face."""

    return _scene_draft(
        required_beats=_beats(
            _segment_beat(), _gate_beat(), _segment_beat()
        ),
        user_present=True,
        **kwargs,
    )


def _blueprint(scenes: list[dict[str, Any]]) -> dict[str, Any]:
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


def _ten_key_payload() -> dict[str, Any]:
    """The pure legacy shape — no V3-8i key anywhere."""

    return _blueprint([_scene_draft()])


# ---------------------------------------------------------------------------
# 1 + 2 — the prompt's gate law and the parser's verbatim ride
# ---------------------------------------------------------------------------


def test_the_director_prompt_states_the_gate_production_law() -> None:
    """The initial plan prompt carries the §10.6 gate-production
    sentence — the beat shapes, the at-least-one-gate rule, the §2.5
    criteria and the ``user_present`` marker — exactly once, en at the
    default and its Chinese counterpart at ``zh`` (never both)."""

    en_stub = _ScriptedCompletion(_answer(_ten_key_payload()))
    LlmDirectorProvider(en_stub).draft_blueprint(_plan_context_for_prompt())
    zh_stub = _ScriptedCompletion(_answer(_ten_key_payload()))
    LlmDirectorProvider(zh_stub, language="zh").draft_blueprint(
        _plan_context_for_prompt()
    )
    for stub, sentence in (
        (en_stub, 'each {"kind": "segment"} for one planned segment'),
        (en_stub, "with AT LEAST ONE gate beat in every scene"),
        (en_stub, '"user_present": one JSON boolean'),
        (zh_stub, "每场还必须为读者自己的意志做规划"),
        (zh_stub, "每场至少一个门拍"),
        (zh_stub, "一个 JSON 布尔值"),
    ):
        assert sentence in stub.prompts[0], sentence
    assert "每场还必须为读者自己的意志做规划" not in en_stub.prompts[0]
    assert "AT LEAST ONE gate beat" not in zh_stub.prompts[0]
    for stub in (en_stub, zh_stub):
        assert stub.prompts[0].count("required_beats") >= 1


def _plan_context_for_prompt() -> Any:
    """A minimal initial-planning context for the prompt pins (the
    prompt is a pure function of the context; the world's faces ride
    empty — the law's sentence does not depend on them)."""

    from elc.world.director import DirectorCastInput, DirectorContext
    from elc.world.providers import DirectorPlanContext

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
        author_direction=None,
    )


def test_the_parser_carries_the_declared_gate_face_verbatim() -> None:
    """An answer that declares the gate face parses with the beats and
    the marker riding verbatim into the plan payload; a malformed face
    (a string beat list, a non-bool marker, a non-object beat) is the
    honest ``bad-shape``; a ten-key answer parses exactly as before and
    carries neither key."""

    gated = _gated_scene()
    other = _gated_scene(
        pov=PARTNER,
        participants=(PARTNER, PLAYER),
        purpose="the tide watch",
    )
    stub = _ScriptedCompletion(_answer(_blueprint([gated, other])))
    parsed = LlmDirectorProvider(stub).draft_blueprint(
        _plan_context_for_prompt()
    )
    first = parsed["scenes"][0]
    assert first["required_beats"] == gated["required_beats"]
    assert first["user_present"] is True
    assert parsed["scenes"][1]["user_present"] is True

    for payload in (
        _blueprint([_scene_draft(required_beats="two segments and a gate")]),
        _blueprint([_scene_draft(required_beats=[_segment_beat(), "gate"])]),
        _blueprint([_scene_draft(user_present="yes")]),
    ):
        with pytest.raises(LlmProviderError) as refused:
            LlmDirectorProvider(
                _ScriptedCompletion(_answer(payload))
            ).draft_blueprint(_plan_context_for_prompt())
        assert refused.value.reason == "bad-shape"

    plain = LlmDirectorProvider(
        _ScriptedCompletion(_answer(_ten_key_payload()))
    ).draft_blueprint(_plan_context_for_prompt())
    assert "required_beats" not in plain["scenes"][0]
    assert "user_present" not in plain["scenes"][0]


# ---------------------------------------------------------------------------
# 3 + 4 — the judge and its declared-shape scope
# ---------------------------------------------------------------------------


def test_the_judge_names_the_first_scene_that_plans_no_gate() -> None:
    """A payload that declares the shape but leaves a scene without the
    reader's own will is refused with the scene named in a human
    sentence; a compliant payload answers ``None``; a gate beat without
    its reason or options is not a gate."""

    mixed = _blueprint([_gated_scene(), _scene_draft(pov=PARTNER)])
    refusal = blueprint_gate_refusal(mixed)
    assert refusal is not None
    assert "scenes[2]" in refusal
    assert "User Gate" in refusal

    compliant = _blueprint(
        [_gated_scene(), _gated_scene(pov=PARTNER, participants=(PARTNER, PLAYER))]
    )
    assert blueprint_gate_refusal(compliant) is None

    reasonless = _blueprint(
        [
            _scene_draft(
                required_beats=_beats(
                    _gate_beat(reason="  "),
                ),
                user_present=True,
            )
        ]
    )
    refusal = blueprint_gate_refusal(reasonless)
    assert refusal is not None and "scenes[1]" in refusal
    optionless = _blueprint(
        [
            _scene_draft(
                required_beats=_beats(_gate_beat(options=[])),
                user_present=True,
            )
        ]
    )
    refusal = blueprint_gate_refusal(optionless)
    assert refusal is not None and "scenes[1]" in refusal
    marked_absent = _blueprint(
        [
            _scene_draft(
                required_beats=_beats(_gate_beat()),
                user_present="true",
            )
        ]
    )
    refusal = blueprint_gate_refusal(marked_absent)
    assert refusal is not None and "scenes[1]" in refusal


def test_the_judge_scope_is_the_declared_shape() -> None:
    """A pure ten-key payload answers ``None`` — the canonical freeze
    stands and the deterministic baselines ride; one scene declaring
    either V3-8i key flips the WHOLE payload into judgment (a plan that
    plans the reader's will in one scene and leaves them nothing in the
    next is the ch02 failure in miniature)."""

    assert blueprint_gate_refusal(_ten_key_payload()) is None
    assert blueprint_gate_refusal({"goal": 7}) is None  # canonical arms'
    # scope — the judge answers None for a payload that never cleared it.
    declared_marker_only = _blueprint([_scene_draft(), _scene_draft()])
    declared_marker_only["scenes"][1]["user_present"] = True
    refusal = blueprint_gate_refusal(declared_marker_only)
    assert refusal is not None
    assert "scenes[1]" in refusal  # the undeclared first scene is judged too
    declared_beats_only = _blueprint([_scene_draft(), _scene_draft()])
    declared_beats_only["scenes"][0]["required_beats"] = _beats(
        _gate_beat()
    )
    declared_beats_only["scenes"][0]["user_present"] = True
    refusal = blueprint_gate_refusal(declared_beats_only)
    assert refusal is not None
    assert "scenes[2]" in refusal


# ---------------------------------------------------------------------------
# 5 — the seat refuses; the production planner re-casts once
# ---------------------------------------------------------------------------


def _partner_scene(**extra: Any) -> dict[str, Any]:
    """The second scene's shape: Bram's POV with his own participants
    (the canonical schema's POV-invariant holds)."""

    return _scene_draft(
        pov=PARTNER, participants=(PARTNER, PLAYER), **extra
    )


def test_the_seat_refuses_the_declared_gateless_plan(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """``open_next_chapter`` at ``require_gates`` refuses a declared
    gateless plan ``VALIDATION_FAILED`` with the judge's sentence —
    before a single row is written — and answers a compliant plan
    ``Ok``; the default call keeps the legacy semantics byte for byte
    (the same gateless payload lands)."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    gateless = _blueprint([_gated_scene(), _partner_scene()])
    refused = director.open_next_chapter(
        TOWN, gateless, NOW, require_gates=True
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "scenes[2]" in refused.error.message
    assert "User Gate" in refused.error.message
    assert narrative.chapters_of(TOWN) == ()  # nothing was written

    compliant = _blueprint(
        [_gated_scene(), _gated_scene(pov=PARTNER, participants=(PARTNER, PLAYER))]
    )
    opened = director.open_next_chapter(
        TOWN, compliant, NOW, require_gates=True
    )
    assert isinstance(opened, Ok)
    assert len(opened.value.scenes) == 2

    # the default call on the same world: the same gateless payload
    # lands as always (the canonical schema alone judges — the
    # pre-V3-8i semantics; the runtime floor bounds what it can do).
    landed = director.open_next_chapter(TOWN, gateless, NOW)
    assert isinstance(landed, Ok)
    assert landed.value.chapter.chapter_index == 2


def test_the_production_planner_recasts_once_and_reports_the_second_refusal(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """``require_plan_gates``: a gateless first draft is re-drafted
    exactly once (the §10.6 bounded re-cast — two drafts consumed), the
    compliant second draft lands; two gateless drafts answer the honest
    ``VALIDATION_FAILED`` (the sentence rides, nothing is written); the
    default pipeline single-drafts a gateless draft and lands it — the
    deterministic baselines' choreography, byte for byte."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    compliant = _blueprint(
        [_gated_scene(), _gated_scene(pov=PARTNER, participants=(PARTNER, PLAYER))]
    )
    gateless = _blueprint([_gated_scene(), _partner_scene()])
    kwargs = dict(
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=DeterministicFakeProvider(),
        planner_provider=DeterministicFakeProvider(),
        resolver_provider=DeterministicFakeProvider(),
    )

    # the re-cast: bad draft → one more → lands (two drafts consumed).
    recast_fake = DeterministicFakeProvider(blueprints=(gateless, compliant))
    pipeline = Pipeline(
        conn,
        director_provider=recast_fake,
        action_duration_ticks=1,
        require_plan_gates=True,
        **kwargs,
    )
    planned = pipeline.plan_chapter(TOWN, NOW)
    assert isinstance(planned, Ok)
    assert len(recast_fake.blueprint_contexts) == 2

    # the honest second refusal: bad → re-cast → bad → Err, nothing
    # written, the judge's sentence naming the scene rides the message.
    stubborn_fake = DeterministicFakeProvider(blueprints=(gateless, gateless))
    pipeline = Pipeline(
        conn,
        director_provider=stubborn_fake,
        action_duration_ticks=1,
        require_plan_gates=True,
        **kwargs,
    )
    refused = pipeline.plan_chapter(TOWN, NOW)
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "scenes[2]" in refused.error.message
    assert "re-drafted once" in refused.error.message
    # still nothing beyond the re-cast's own landing (no second
    # chapter was written by the refused plan).
    assert len(narrative.chapters_of(TOWN)) == 1

    # the default pipeline: one draft, gateless, lands (the baselines'
    # single-draft choreography untouched — the judge never fires).
    legacy_fake = DeterministicFakeProvider(blueprints=(gateless,))
    pipeline = Pipeline(
        conn,
        director_provider=legacy_fake,
        action_duration_ticks=1,
        **kwargs,
    )
    planned = pipeline.plan_chapter(TOWN, NOW)
    assert isinstance(planned, Ok)
    assert len(legacy_fake.blueprint_contexts) == 1


# ---------------------------------------------------------------------------
# 6 — the player anchor on the three participant-rendering arms
# ---------------------------------------------------------------------------


def _cognition(*narration: str, viewer: str = ACTOR) -> Any:
    from elc.world.cognition import V3CognitionEvent, V3CognitionView

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


def test_the_writer_prompt_anchors_the_player_pure_addition_en_and_zh() -> (
    None
):
    """The Writer arm: with the player id the prompt carries the anchor
    line (en at the default, zh at the switch) and the participants
    line stays byte for byte; without the id the prompt equals the
    anchored prompt minus exactly the one anchor line — pure addition
    (every pre-V3-8i prompt pin's bytes ride untouched)."""

    def _context(player: str | None) -> PovContext:
        from elc.world.memory import (
            ActorMemoryRecord,
            MemoryKind,
            V3MemoryView,
        )

        memory = V3MemoryView(
            viewer_id=ACTOR,
            memories=(
                ActorMemoryRecord(
                    memory_id="m1",
                    world_id=TOWN,
                    participant_id=ACTOR,
                    kind=MemoryKind.EXPERIENCED,
                    content="she kept the ledger close",
                    source_event_id="e1",
                    learned_at_tick=1,
                    salience=None,
                    created_at=NOW,
                    updated_at=NOW,
                    state_version=1,
                ),
            ),
        )
        return PovContext(
            scene_id=SCENE,
            segment_seq=2,
            pov_actor_id=ACTOR,
            participants=(ACTOR, PLAYER),
            place="the bindery steps",
            entry_goals="greet the newcomer",
            exit_condition="the greeting lands or breaks",
            revealable="the ledger's back page",
            must_hide="the priced tools",
            current_tick=3,
            cognition=_cognition(),
            memory=memory,
            player_character_id=player,
        )

    en_stub = _ScriptedCompletion(CompletionOutcome(text="prose"))
    LlmWriterProvider(en_stub).write_segment(_context(PLAYER))
    bare_stub = _ScriptedCompletion(CompletionOutcome(text="prose"))
    LlmWriterProvider(bare_stub).write_segment(_context(None))
    en_prompt = en_stub.prompts[0]
    bare_prompt = bare_stub.prompts[0]
    assert EN_ANCHOR in en_prompt
    assert "- participants: actor-lia, pc-you" in en_prompt
    assert "- participants: actor-lia, pc-you" in bare_prompt
    assert EN_ANCHOR not in bare_prompt
    # pure addition: removing the one anchor line restores yesterday's
    # prompt byte for byte.
    assert bare_prompt == en_prompt.replace(f"{EN_ANCHOR}\n", "")

    zh_stub = _ScriptedCompletion(CompletionOutcome(text="正文"))
    LlmWriterProvider(zh_stub, language="zh").write_segment(_context(PLAYER))
    assert ZH_ANCHOR in zh_stub.prompts[0]
    assert EN_ANCHOR not in zh_stub.prompts[0]


def test_the_planner_prompt_anchors_the_player_en_and_zh() -> None:
    """The Scene Planner arm: the anchor rides the scene-plan prompt
    when the context carries the player id (en and zh), never
    otherwise; the plan never writes the player's choices — their will
    is the scene's gate beats."""

    def _context(player: str | None) -> ScenePlanContext:
        return ScenePlanContext(
            world_id=TOWN,
            scene_id=SCENE,
            pov_actor_id=ACTOR,
            current_tick=3,
            element=None,
            cognition=_cognition(),
            memory=_memory_of(ACTOR),
            player_character_id=player,
        )

    en_stub = _ScriptedCompletion(_answer(_scene_element_payload()))
    LlmPlannerProvider(en_stub).plan_scene(_context(PLAYER))
    assert "- the player character: pc-you" in en_stub.prompts[0]
    assert "the scene's User Gate beats" in en_stub.prompts[0]
    zh_stub = _ScriptedCompletion(_answer(_scene_element_payload()))
    LlmPlannerProvider(zh_stub, language="zh").plan_scene(_context(PLAYER))
    assert "玩家角色：pc-you" in zh_stub.prompts[0]
    assert "只落为本场的用户意志门（User Gate）拍" in zh_stub.prompts[0]
    bare_stub = _ScriptedCompletion(_answer(_scene_element_payload()))
    LlmPlannerProvider(bare_stub).plan_scene(_context(None))
    assert "pc-you — the reader's own character" not in bare_stub.prompts[0]
    assert "玩家角色" not in bare_stub.prompts[0]


def _memory_of(viewer: str) -> Any:
    from elc.world.memory import (
        ActorMemoryRecord,
        MemoryKind,
        V3MemoryView,
    )

    return V3MemoryView(
        viewer_id=viewer,
        memories=(
            ActorMemoryRecord(
                memory_id="m1",
                world_id=TOWN,
                participant_id=viewer,
                kind=MemoryKind.EXPERIENCED,
                content="the door opens",
                source_event_id="e1",
                learned_at_tick=1,
                salience=None,
                created_at=NOW,
                updated_at=NOW,
                state_version=1,
            ),
        ),
    )


def _scene_element_payload() -> dict[str, Any]:
    return {
        "pov_actor_id": ACTOR,
        "participants": [ACTOR, PLAYER],
        "planned_start_tick": 0,
        "place": "the bindery steps",
        "entry_goals": "greet the newcomer",
        "exit_condition": "the greeting lands or breaks",
        "elasticity": "the greeting may fail",
        "revealable": "the ledger's back page",
        "must_hide": "the priced tools",
    }


class _PlayerRow:
    """The resolver pin's duck for the durable player row (the prompt
    reads the record's profile face only)."""

    player_character_id = PLAYER
    name = "You"
    abilities = "steady hands"
    limits = "no training with steel"


def test_the_resolver_prompt_anchors_the_player_en_and_zh() -> None:
    """The Resolver arm: the anchor rides the world-authoritative
    prompt when the context carries the player row (en and zh) — the
    player's will rides the submission, never an invention of the
    resolver's; the participants line stays byte for byte."""

    def _context(player: Any) -> ResolverContext:
        return ResolverContext(
            gate_id=f"{SCENE}-g01",
            scene_id=SCENE,
            submission_id="sub-1",
            intent_text="I hold the ledger and say nothing.",
            selected_option=None,
            options=("hold the ledger", "step back"),
            bible=None,
            current_facts=(),
            player_character=player,
            place="the bindery steps",
            participants=(ACTOR, PLAYER),
            counterparts=(),
            player_cognition=None,
            player_memory=None,
            pov_actor_id=ACTOR,
            cognition=_cognition(),
            memory=_memory_of(ACTOR),
            current_tick=3,
        )

    verdict = {
        "interpretation": "You mean to help rather than to buy.",
        "outcome": "Lia lets you hold the ledger.",
        "actual_action": "you carry the ledger to the counter",
        "consequences": "the shop's silence opens one notch",
        "state_effects": [],
        "participants": [PLAYER, ACTOR],
        "replan_scope": "NONE",
    }
    en_stub = _ScriptedCompletion(_answer(verdict))
    LlmResolverProvider(en_stub).adjudicate(_context(_PlayerRow()))
    en_prompt = en_stub.prompts[0]
    assert "- the player character: pc-you" in en_prompt
    assert "their will rides the submission below" in en_prompt
    assert "- participants: actor-lia, pc-you" in en_prompt

    zh_stub = _ScriptedCompletion(_answer(verdict))
    LlmResolverProvider(zh_stub, language="zh").adjudicate(
        _context(_PlayerRow())
    )
    zh_prompt = zh_stub.prompts[0]
    assert "玩家角色：pc-you" in zh_prompt
    assert "只来自下方那份提交本身" in zh_prompt

    bare_stub = _ScriptedCompletion(_answer(verdict))
    LlmResolverProvider(bare_stub).adjudicate(_context(None))
    assert "their will rides the submission below" not in (
        bare_stub.prompts[0]
    )


def test_the_compiled_pov_context_carries_the_player_id(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The door's one widened keyword rides through the real
    compilation: ``pov_context_of`` answers a context whose
    ``player_character_id`` is the id the caller passed — and the
    default ``None`` keeps every pre-V3-8i call site's shape."""

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    opened = director.open_next_chapter(
        TOWN, _blueprint([_scene_draft()]), NOW
    )
    assert isinstance(opened, Ok)
    # the pipeline's own compilation (the writer arm's production path)
    # is pinned in tests/world/test_v3_8a_pipeline_providers.py's
    # door pins; here the keyword's shape is pinned at the seam.
    from elc.world.providers import PovContext as Context

    fields = [f.name for f in Context.__dataclass_fields__.values()]
    assert fields[-1] == "player_character_id"
    fake_writer = DeterministicFakeProvider()
    pipeline = Pipeline(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=fake_writer,
        planner_provider=DeterministicFakeProvider(),
        director_provider=DeterministicFakeProvider(),
        resolver_provider=DeterministicFakeProvider(),
        action_duration_ticks=1,
    )
    driven = pipeline.run_scene(
        SCENE, (SegmentBeat(duration_ticks=1, is_last_segment=True),), NOW
    )
    assert isinstance(driven, Ok)
    compiled = fake_writer.segment_contexts[0]
    assert compiled.player_character_id == PLAYER


# ---------------------------------------------------------------------------
# 7 — the plan's gate beats become the scene's script
# ---------------------------------------------------------------------------


def test_plan_gate_beats_become_the_scene_script(
    conn: sqlite3.Connection,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative: SqliteNarrativeStore,
    director: Director,
) -> None:
    """The derivation laws over a REAL adopted plan: the gated scene's
    beats ride plan order (gate_seq 1..k, the planned options), the
    walk reads the derived script and stops at its gate beat, the
    beat-less scene stays open (the floor's domain), a script ending on
    a gate gets its closing segment appended, and the gold author
    script wins first — byte for byte unchanged."""

    from elc.narrative_web import _DurableReads

    assert isinstance(
        _create_town(conn, world_store, cast_store, bible_store), Ok
    )
    gate_options = ["take the stranger in", "turn them away"]
    gated_tail = _scene_draft(
        pov=PARTNER,
        participants=(PARTNER, PLAYER),
        purpose="the tide watch",
        required_beats=_beats(_gate_beat(options=gate_options)),
        user_present=True,
    )
    opened = director.open_next_chapter(
        TOWN,
        _blueprint([_gated_scene(), gated_tail]),
        NOW,
        require_gates=True,
    )
    assert isinstance(opened, Ok)
    reads = _DurableReads(conn, open_runtime_epoch(conn))

    # scene 1: [seg, gate, seg] — the terminal law marks the last beat.
    script = reads._script_of(SCENE, CH)
    assert script is not None
    assert isinstance(script[0], SegmentBeat)
    assert script[0].duration_ticks == 1
    assert isinstance(script[1], GateBeat)
    assert script[1].gate_seq == 1
    assert script[1].options == tuple(_gate_beat()["options"])
    assert isinstance(script[2], SegmentBeat)
    assert script[2].is_last_segment is True

    # scene 2's beats END on the gate: the derivation appends the
    # closing segment (the author scripts' own shape).
    tail_script = reads._script_of(SCENE2, CH)
    assert tail_script is not None
    assert isinstance(tail_script[0], GateBeat)
    assert isinstance(tail_script[-1], SegmentBeat)
    assert tail_script[-1].is_last_segment is True

    # the walk reads the derived script: one committed segment and the
    # gate beat is the action point — the plan's own stop. (The scene
    # opens first — only an ACTIVE scene takes segment commits.)
    from elc.world.settlement import commit_segment

    opened_scene = ScenePlanner(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    ).open_scene(SCENE, NOW)
    assert isinstance(opened_scene, Ok)
    outcome = commit_segment(
        conn,
        narrative_store=narrative,
        world_store=world_store,
        scene_id=SCENE,
        segment_seq=1,
        body="The bindery steps take the morning sun.",
        language="en",
        participants=(ACTOR, PLAYER),
        effects=(),
        narration="The bindery steps take the morning sun.",
        duration_ticks=1,
        is_last_segment=False,
        now=NOW,
    )
    assert isinstance(outcome, Ok)
    at_gate = reads.walk(SCENE, CH)
    assert at_gate.kind == "gate_open"
    assert isinstance(at_gate.beat, GateBeat)
    assert at_gate.beat.options == tuple(_gate_beat()["options"])
    # the gate lies ahead: the floor's own exception holds.
    assert reads._gate_ahead(SCENE, CH) is True

    # a scene whose beats plan no gate derives no script (open scene).
    ungated = director.open_next_chapter(
        TOWN, _blueprint([_scene_draft()]), NOW
    )
    assert isinstance(ungated, Ok)
    next_chapter = ungated.value.chapter.chapter_id
    next_scene = ungated.value.scenes[0].scene_id
    fresh_reads = _DurableReads(conn, open_runtime_epoch(conn))
    assert fresh_reads._script_of(next_scene, next_chapter) is None
    assert fresh_reads._gate_ahead(next_scene, next_chapter) is False

    # the gold author script wins first, byte for byte unchanged.
    from elc.world.gold import gold_beats_by_scene

    gold_reads = _DurableReads(conn, open_runtime_epoch(conn))
    gold_script = gold_reads._script_of(
        "gold-empire-105-ch01-s01", "gold-empire-105-ch01"
    )
    assert gold_script == gold_beats_by_scene()[
        "gold-empire-105-ch01-s01"
    ]


def test_the_derivation_terminal_law_and_malformed_beats() -> None:
    """The pure derivation: a gate-ending script gains its closing
    segment; malformed beat entries are not beats; a beat list with no
    gate derives nothing (the open scene, the floor's domain)."""

    from elc.narrative_web import _plan_script_beats

    gate_ending = _plan_script_beats(
        {
            "required_beats": _beats(
                _segment_beat(),
                _gate_beat(),
            ),
            "user_present": True,
        }
    )
    assert gate_ending is not None
    assert len(gate_ending) == 3
    assert isinstance(gate_ending[1], GateBeat)
    assert gate_ending[1].gate_seq == 1
    assert isinstance(gate_ending[-1], SegmentBeat)
    assert gate_ending[-1].is_last_segment is True

    assert (
        _plan_script_beats(
            {"required_beats": _beats(_segment_beat(), "a gate")}
        )
        is None
    )
    assert (
        _plan_script_beats(
            {
                "required_beats": _beats(
                    _segment_beat(), _gate_beat(options=[])
                )
            }
        )
        is None
    )
    assert _plan_script_beats({"required_beats": _beats(_segment_beat())}) is None
    assert _plan_script_beats({}) is None


# ---------------------------------------------------------------------------
# 8 — the floor's constant and sentence
# ---------------------------------------------------------------------------


def test_the_floor_constant_and_its_reasoned_sentence() -> None:
    """The production constant is 4 (the ch02 runaway's own calibration)
    and the sentence says what the reader can do — the reasoned stop
    the drive's ``did`` and the state's ``note`` both carry."""

    from elc.narrative_web import (
        V3_GATELESS_SEGMENT_FLOOR,
        _gateless_sentence,
    )

    assert V3_GATELESS_SEGMENT_FLOOR == 4
    sentence = _gateless_sentence(4, V3_GATELESS_SEGMENT_FLOOR)
    assert "这一幕还没轮到你" in sentence
    assert "结束本场" in sentence
    assert "继续" in sentence
    assert "4 段" in sentence
