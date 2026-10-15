"""DS-1 — the dual-seat turn spine, the harness registry, the three new
model arms and the opening seed (the technical definition §1–§5, §7,
§11; docs/design/2026-10-14-dual-seat-world-technical-definition.md).

Pinned here (every prompt pin rides the real provider execution arm —
the scripted stub records the prompt the arm actually built; no pin
reads a private function's return in place of the driven path, the
V3-8e F2 anti-vacuum law):

1. the harness permission table (§3): each tool's principal set, the
   loud violation arm, the registry's closed vocabulary;
2. the three arms' parsers (shape law): the dispatch decision's
   vocabulary checks, the proposal's optional-by-shape private
   thought, the narration's sentinel tail (missing tail refused, a
   non-bool marker refused);
3. the streaming tail gate (§12 F15): a sentinel split across chunks
   never reaches the wire; a streaming seam renders through
   ``complete_streaming`` on the real narrator arm;
4. the memory retrieval cap (§2 F5): the layered view's recency
   truncation;
5. the reply drive end to end on a real seeded world (§1 ①→⑧): the
   gate carries the dispatch options, the ruling commits through the
   existing chain, the private thoughts land as the character's OWN
   INFERRED rows, the narration lands with the ruling's ``outcome_ref``
   and the gate closes, the stop log rides;
6. the stop policy (§4): ``addresses_you`` stops at once;
   ``beat_complete`` + ``press`` continues into advance beats and stops
   at the beat ceiling with its reasoned sentence;
7. the durable face wins (§10 F8): a gate whose submission already
   landed re-drives the STORED submission with the STORED ruling (no
   second adjudication) and the owed continuation closes the gate;
8. the replay anchor (§10 F1): ``turn_steps_of`` reads the committed
   steps back in canonical order;
9. the offstage settlement (§7): the per-protagonist calls, the
   offstage δ's goal/mood facts, the memory consolidation, the flip to
   CLOSED and the NCP-4 row — and a settled chapter refuses a second
   settle;
10. the prompt pins (the arms' contracts, from the driven prompts): the
    dispatch prompt carries the identity vocabulary and the options
    key; the character prompt carries the private context and the
    memory pack; the narrator prompt is second-person with the
    proposals' public face only; the batch prompt carries the
    proposals and demands the player id among the participants;
11. the opening seed (§11): the draft flag, the seeded world's cast and
    the idempotent replay.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.platform.types import Err
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.director import Director
from elc.world.ds_opening import (
    BRYN,
    CORVIN,
    DS_OPENING_IS_DRAFT,
    DS_WORLD_ID,
    PLAYER,
    seed_ds_world,
)
from elc.world.harness import (
    Principal,
    Tool,
    ToolViolation,
    authorize,
    permissions_of,
)
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmBatchAdjudicatorProvider,
    LlmCharacterProvider,
    LlmDispatcherProvider,
    LlmNarratorProvider,
    NarrationResult,
    _parse_dispatch,
    _parse_narration,
    _parse_proposal,
    _TailGate,
    pack_memories,
)
from elc.world.memory import MemoryKind, v3_memory_view
from elc.world.narrative import SqliteNarrativeStore
from elc.world.store import SqliteWorldStore
from elc.world.turns import (
    DRIVE_BEAT_CEILING,
    DRIVE_CALL_CEILING,
    AdvanceBeat,
    OpenBeat,
    ReplyBeat,
    TurnEngine,
    turn_steps_of,
)

NOW = "2026-10-14T00:00:00+00:00"


# ---------------------------------------------------------------------------
# the scripted seam — one stub, four prompt families, per-kind queues
# ---------------------------------------------------------------------------


class ScriptedDSCompletion:
    """A deterministic ``TextCompletion`` stub routing by the prompt's
    own family words (the arms' prompt openers): per-kind answer
    queues, every prompt recorded, an exhausted queue is the loud
    script gap."""

    def __init__(self, **queues: list[str]) -> None:
        self._queues = {kind: list(items) for kind, items in queues.items()}
        self.prompts: dict[str, list[str]] = {}

    def complete(self, prompt: str) -> CompletionOutcome:
        kind = self._kind_of(prompt)
        self.prompts.setdefault(kind, []).append(prompt)
        queue = self._queues.get(kind)
        if not queue:
            raise AssertionError(f"the {kind} script is exhausted")
        return CompletionOutcome(text=queue.pop(0), error=None)

    def _kind_of(self, prompt: str) -> str:
        if "dispatcher of a two-seat" in prompt:
            return "dispatch"
        if "your own\nprivate seat" in prompt or (
            "private seat" in prompt and "propose how you respond" in prompt
        ):
            return "character"
        if "narrator of a two-seat" in prompt:
            return "narrator"
        if "resolver of a two-seat" in prompt:
            return "adjudicate"
        if "scene planner of an interactive story world" in prompt:
            return "planner"
        if "world director of an interactive story world" in prompt:
            return "director"
        raise AssertionError(
            "unknown prompt family: " + prompt[:120]
        )

    def count(self, kind: str) -> int:
        return len(self.prompts.get(kind, []))


def _dispatch_payload(
    responders: tuple[str, ...] = (BRYN, CORVIN),
    pacing: str = "press",
    options: tuple[str, ...] = ("Ask her again", "Hold your tongue"),
    world_event: str | None = None,
    reading: str = "the painter answers calmly and offers to walk the bridge",
) -> str:
    return json.dumps(
        {
            "reading": reading,
            "responders": list(responders),
            "world_event": world_event,
            "pacing": pacing,
            "options": list(options),
        },
        ensure_ascii=False,
    )


def _proposal_payload(
    speech: str = "Then take the lantern. We walk now.",
    action: str = "lifts the lantern and steps toward the bridge head",
    intent: str = "watch whether the painter flinches at the mark",
    private_thought: str = "the paint smelled fresh — under an hour",
) -> str:
    return json.dumps(
        {
            "speech": speech,
            "action": action,
            "intent": intent,
            "private_thought": private_thought,
        },
        ensure_ascii=False,
    )


def _narration_payload(
    prose: str = (
        "You hold the lantern steady while she studies the stone. The"
        " fog thickens behind you, and Old Han's punt knocks once"
        " against the pilings."
    ),
    addresses_you: bool = True,
    impends_on_you: bool = False,
    beat_complete: bool = False,
) -> str:
    return (
        prose
        + "\n---\n"
        + json.dumps(
            {
                "addresses_you": addresses_you,
                "impends_on_you": impends_on_you,
                "beat_complete": beat_complete,
            }
        )
    )


def _adjudication_payload(
    outcome: str = (
        "The steward accepts the offer; painter and steward walk the"
        " bridge together in lantern light while the fog closes in."
    ),
    effects: list[dict[str, str]] | None = None,
) -> str:
    return json.dumps(
        {
            "interpretation": (
                "the painter answers the public question with a calm"
                " offer of proof"
            ),
            "outcome": outcome,
            "actual_action": (
                "the painter walks the bridge beside the steward"
            ),
            "consequences": (
                "the accusation pauses; the mark remains unexplained"
            ),
            "state_effects": effects
            if effects is not None
            else [
                {
                    "key": "protagon.bryn.mood",
                    "statement": "publicly composed, privately shaken",
                },
                {
                    "key": "bridge.mark",
                    "statement": "the vermilion mark stays for now",
                },
            ],
            "participants": [PLAYER, BRYN, CORVIN],
            "replan_scope": "NONE",
        },
        ensure_ascii=False,
    )


def _default_queues() -> dict[str, list[str]]:
    return {
        "dispatch": [_dispatch_payload()],
        "character": [_proposal_payload(), _proposal_payload()],
        "narrator": [_narration_payload()],
        "adjudicate": [_adjudication_payload()],
    }


# ---------------------------------------------------------------------------
# fixtures (the V3-8 suites' own shapes)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    return db


@pytest.fixture()
def stores(conn: sqlite3.Connection) -> tuple[
    SqliteWorldStore, SqliteCastStore, SqliteBibleStore, SqliteNarrativeStore
]:
    fence = open_runtime_epoch(conn)
    return (
        SqliteWorldStore(conn, fence),
        SqliteCastStore(conn, fence),
        SqliteBibleStore(conn, fence),
        SqliteNarrativeStore(conn, fence),
    )


BLUEPRINT: dict[str, Any] = {
    "goal": "the mark on the cornerstone demands an answer tonight",
    "dramatic_question": "who painted the mark, and what does the water keep",
    "planned_start_tick": 1310,
    "planned_end_tick": 1500,
    "closing_pressure": "the fog and the county clerk both close in",
    "desired_development": "the painter's answer moves the town's suspicion",
    "soft_outcomes": "an uneasy truce of watching",
    "chapter_questions_to_advance": "what the mark means; what Han knows",
    "scenes": [
        {
            "purpose": "the public question and the painter's answer",
            "place": "the ferry house steps, lantern light",
            "pov_actor_id": PLAYER,
            "participants": [PLAYER, BRYN, CORVIN],
            "planned_start_tick": 1310,
            "entry_goals": "the steward's question hangs on you",
            "exit_condition": "the bridge walk ends or the fog turns all",
            "elasticity": "one night, one walk",
            "revealable": "the paint's freshness",
            "must_hide": "who painted the mark",
        }
    ],
}


@pytest.fixture()
def seeded(
    conn: sqlite3.Connection, stores: tuple
) -> sqlite3.Connection:
    world_store, cast_store, bible_store, _narrative = stores
    created = seed_ds_world(
        conn,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        now=NOW,
    )
    assert not isinstance(created, Err), (
        created.error if isinstance(created, Err) else ""
    )
    return conn


@pytest.fixture()
def planned(seeded: sqlite3.Connection, stores: tuple) -> sqlite3.Connection:
    """The seeded world with chapter 1 planned (one scene, legacy
    ten-key shape — the DS situation plan rides the blueprint form)."""

    conn = seeded
    world_store, cast_store, bible_store, narrative = stores
    director = Director(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
    )
    outcome = director.open_next_chapter(DS_WORLD_ID, BLUEPRINT, NOW)
    assert not isinstance(outcome, Err), outcome.error
    return conn


def _engine(
    conn: sqlite3.Connection,
    stores: tuple,
    completion: ScriptedDSCompletion,
    *,
    language: str = "en",
) -> TurnEngine:
    world_store, cast_store, bible_store, narrative = stores
    return TurnEngine(
        conn,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        dispatcher=LlmDispatcherProvider(completion, language=language),
        character=LlmCharacterProvider(completion, language=language),
        adjudicator=LlmBatchAdjudicatorProvider(completion, language=language),
        narrator=LlmNarratorProvider(completion, language=language),
        action_duration_ticks=5,
        language=language,
        clock=lambda: NOW,
    )


# ---------------------------------------------------------------------------
# 1 — the harness registry (§3)
# ---------------------------------------------------------------------------


def test_the_permission_table_is_the_designs_sentences() -> None:
    assert permissions_of(Tool.CANON_DELTA) == frozenset(
        {Principal.ADJUDICATOR}
    )
    assert permissions_of(Tool.MEMORY_WRITE) == frozenset(
        {Principal.CHARACTER}
    )
    assert permissions_of(Tool.BIBLE_EDIT) == frozenset(
        {Principal.DIRECTOR_SEAT}
    )
    assert permissions_of(Tool.DISPATCH_CHARACTER) == frozenset(
        {Principal.SPINE}
    )
    assert permissions_of(Tool.RENDER_NARRATION) == frozenset(
        {Principal.NARRATOR}
    )
    assert permissions_of(Tool.SETTLE_CHAPTER) == frozenset(
        {Principal.SPINE}
    )
    assert Principal.SPINE in permissions_of(Tool.MEMORY_READ)
    assert Principal.CHARACTER in permissions_of(Tool.CLOCK)


def test_a_violation_is_the_loud_programmer_error() -> None:
    authorize(Tool.CANON_DELTA, Principal.ADJUDICATOR)
    with pytest.raises(ToolViolation) as exc:
        authorize(Tool.CANON_DELTA, Principal.SPINE)
    assert "canon_delta" in str(exc.value)
    with pytest.raises(ToolViolation):
        authorize(Tool.BIBLE_EDIT, Principal.CHARACTER)


# ---------------------------------------------------------------------------
# 2 — the arms' parsers (the shape law)
# ---------------------------------------------------------------------------


def test_the_dispatch_parser_carries_the_decision() -> None:
    decision = _parse_dispatch(
        _dispatch_payload(world_event="a lantern gutters out"),
        (BRYN, CORVIN),
    )
    assert decision.reading.startswith("the painter")
    assert decision.responders == (BRYN, CORVIN)
    assert decision.world_event == "a lantern gutters out"
    assert decision.pacing == "press"
    assert decision.options == ("Ask her again", "Hold your tongue")


def test_the_dispatch_parser_refuses_outside_words() -> None:
    from elc.world.llm_providers import LlmProviderError

    with pytest.raises(LlmProviderError, match="bad-shape"):
        _parse_dispatch(
            _dispatch_payload(responders=(BRYN, "stranger")), (BRYN, CORVIN)
        )
    with pytest.raises(LlmProviderError, match="bad-shape"):
        _parse_dispatch(_dispatch_payload(pacing="rush"), (BRYN, CORVIN))


def test_the_proposal_parser_private_thought_is_optional_by_shape() -> None:
    proposal = _parse_proposal(
        json.dumps(
            {
                "speech": "s",
                "action": "a",
                "intent": "i",
                "private_thought": None,
            }
        ),
        BRYN,
    )
    assert proposal.private_thought == ""
    assert proposal.actor_id == BRYN


def test_the_narration_parser_demands_the_marker_tail() -> None:
    result = _parse_narration(_narration_payload())
    assert isinstance(result, NarrationResult)
    assert result.addresses_you is True
    assert result.impends_on_you is False
    assert result.beat_complete is False
    assert result.prose.startswith("You hold the lantern")

    from elc.world.llm_providers import LlmProviderError

    with pytest.raises(LlmProviderError, match="missing-field:markers"):
        _parse_narration("just prose, no tail at all")
    with pytest.raises(LlmProviderError, match="bad-shape"):
        _parse_narration(
            "prose\n---\n"
            + json.dumps(
                {"addresses_you": "yes", "impends_on_you": False,
                 "beat_complete": True}
            )
        )


# ---------------------------------------------------------------------------
# 3 — the streaming tail gate (§12 F15)
# ---------------------------------------------------------------------------


def test_the_tail_gate_never_releases_the_markers() -> None:
    seen: list[str] = []
    gate = _TailGate(seen.append)
    full = _narration_payload()
    # the sentinel split across three increments
    cut = full.index("\n---")
    for chunk in (full[: cut - 4], full[cut - 4 : cut + 3], full[cut + 3 :]):
        gate(chunk)
    emitted = "".join(seen)
    assert "---" not in emitted
    assert "addresses_you" not in emitted
    assert emitted.startswith("You hold the lantern")


class _StreamingCompletion(ScriptedDSCompletion):
    """The scripted stub with the re-opened streaming face: the answer
    flows as increments (split mid-sentinel), the outcome carries the
    honest whole."""

    def complete_streaming(
        self, prompt: str, on_chunk: Any
    ) -> CompletionOutcome:
        outcome = self.complete(prompt)
        assert outcome.text is not None
        step = max(1, len(outcome.text) // 5)
        for i in range(0, len(outcome.text), step):
            on_chunk(outcome.text[i : i + step])
        return outcome


def test_the_narrator_streams_through_the_real_arm(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    completion = _StreamingCompletion(**_default_queues())
    completion._queues["narrator"] = [_narration_payload()]
    engine = _engine(planned, stores, completion)
    seen: list[str] = []
    run = engine.drive(DS_WORLD_ID, OpenBeat(), NOW, on_chunk=seen.append)
    assert run.turns
    emitted = "".join(seen)
    assert "addresses_you" not in emitted  # the tail stayed off the wire
    assert emitted  # the prose reached the wire
    assert run.turns[0].narration.startswith(emitted[:20])


# ---------------------------------------------------------------------------
# 4 — the memory retrieval cap (§2 F5)
# ---------------------------------------------------------------------------


def test_pack_memories_truncates_to_the_recent_cap() -> None:
    from elc.world.memory import ActorMemoryRecord, V3MemoryView

    def row(ordinal: int, tick: int) -> ActorMemoryRecord:
        return ActorMemoryRecord(
            memory_id=f"mem:e{ordinal}:bryn:INFERRED",
            world_id=DS_WORLD_ID,
            participant_id=BRYN,
            kind=MemoryKind.INFERRED,
            content=f"memory {ordinal}",
            source_event_id=f"e{ordinal}",
            learned_at_tick=tick,
            salience=None,
            created_at=NOW,
            updated_at=NOW,
            state_version=1,
        )

    rows = tuple(row(i, i) for i in range(30))
    view = V3MemoryView(viewer_id=BRYN, memories=rows)
    packed = pack_memories(view, 24)
    assert len(packed.memories) == 24
    assert all(
        memory.learned_at_tick >= 6 for memory in packed.memories
    )  # the six oldest dropped
    # the layer order is preserved (INFERRED before nothing else here)
    ticks = [memory.learned_at_tick for memory in packed.memories]
    assert ticks == sorted(ticks)


# ---------------------------------------------------------------------------
# 5–6 — the reply drive end to end + the stop policy
# ---------------------------------------------------------------------------


def test_the_reply_drive_runs_the_whole_chain(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    completion = ScriptedDSCompletion(**_default_queues())
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="I did not paint it."),
        NOW,
    )
    # the chain landed: the ruling committed, the narration carries its
    # outcome_ref, the gate closed
    assert run.error is None
    assert run.stopped_on == "addresses_you"
    assert len(run.turns) == 1
    turn = run.turns[0]
    assert turn.gate_id is not None
    gate_row = planned.execute(
        "SELECT status, options_json FROM user_gate WHERE gate_id = ?",
        (turn.gate_id,),
    ).fetchone()
    assert gate_row is not None
    assert gate_row[0] == "CLOSED"
    assert "Ask her again" in str(gate_row[1])
    passage = planned.execute(
        "SELECT p.body FROM narrative_passage p WHERE p.outcome_ref = ?",
        (f"{turn.gate_id}-a",),
    ).fetchone()
    assert passage is not None
    assert passage[0] == turn.narration
    # the private thoughts landed as the characters' OWN memory rows
    for actor in (BRYN, CORVIN):
        read = v3_memory_view(planned, world_id=DS_WORLD_ID, viewer_id=actor)
        assert not isinstance(read, Err), read.error
        view = read.value
        assert isinstance(view.memories, tuple)
        assert any(
            memory.kind is MemoryKind.INFERRED
            and "fresh" in memory.content
            for memory in view.memories
        ), actor
    # the player reads nobody's private thought from their own view
    player_read = v3_memory_view(
        planned, world_id=DS_WORLD_ID, viewer_id=PLAYER
    )
    assert not isinstance(player_read, Err)
    assert all(
        memory.participant_id == PLAYER
        for memory in player_read.value.memories
    )
    # the stop log rode with the measurement face
    assert run.stop_log[0].reason == "addresses_you"
    assert run.calls_used == 5  # dispatch + 2 characters + adjudication + narration
    # the mood fact landed through the ruling's δ
    facts = planned.execute(
        "SELECT statement FROM world_state_fact"
        " WHERE canonical_key = 'protagon.bryn.mood' AND status = 'CURRENT'"
    ).fetchall()
    assert facts and facts[0][0] == "publicly composed, privately shaken"


def test_addresses_you_stops_the_drive_at_once(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    completion = ScriptedDSCompletion(**_default_queues())
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="…"),
        NOW,
    )
    assert run.stopped_on == "addresses_you"
    assert len(run.turns) == 1  # no auto-advance past an address


def test_press_continues_to_the_beat_ceiling(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    queues = _default_queues()
    queues["narrator"] = [
        _narration_payload(addresses_you=False, beat_complete=True)
    ] * 4
    completion = ScriptedDSCompletion(**queues)
    completion._queues["dispatch"] = [_dispatch_payload()] * 3
    completion._queues["character"] = [_proposal_payload()] * 6
    completion._queues["adjudicate"] = [_adjudication_payload()] * 3
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="…"),
        NOW,
    )
    assert DRIVE_BEAT_CEILING == 3
    # DS-3 评审 F1 处置：call cap must sit ABOVE the beat ceiling's
    # worst case (3 beats × ~6 calls = 18) or it silently shrinks the
    # beat ceiling — at 12 the k=3 drive quietly became a 2-beat one.
    assert DRIVE_CALL_CEILING == 20
    assert DRIVE_CALL_CEILING > DRIVE_BEAT_CEILING * 6
    assert run.stopped_on == "beat_ceiling"
    assert run.note is not None
    assert "3 拍" in run.note
    # the ceilings are PURE guardrails under the rhythm law: the stop
    # carries the anomaly signal (the normal path never touches one)
    assert any(
        "dispatch anomaly" in note and "beat" in note
        for note in run.notes
    )
    assert len(run.turns) == 3  # reply + two advances, the reasoned stop
    # every world beat ran the FULL chain (DS-3 跳①不跳④): the reply
    # and the two advances each spent dispatch + 2 characters +
    # adjudication + narration
    assert completion.count("character") == 6
    assert completion.count("adjudicate") == 3
    assert run.calls_used == 15


# ---------------------------------------------------------------------------
# 7 — the durable face wins (§10 F8)
# ---------------------------------------------------------------------------


def _precommit_ruling(conn: sqlite3.Connection) -> str:
    """Drive the reply chain up to the commit by hand (the crash
    window's durable shape): open → submit → begin → the scripted
    ruling → commit; the narration has NOT landed."""
    from elc.world.action import (
        begin_resolving,
        commit_action,
        open_gate,
        submit_gate,
    )

    scene_id = conn.execute(
        "SELECT scene_id FROM world_scene"
        " WHERE chapter_id = (SELECT MAX(chapter_id) FROM world_chapter)"
    ).fetchone()[0]
    fence0 = open_runtime_epoch(conn)
    from elc.world.scene import ScenePlanner

    planner = ScenePlanner(
        conn,
        world_store=SqliteWorldStore(conn, fence0),
        cast_store=SqliteCastStore(conn, fence0),
        bible_store=SqliteBibleStore(conn, fence0),
        narrative_store=SqliteNarrativeStore(conn, fence0),
    )
    opened_scene = planner.open_scene(scene_id, NOW)
    assert not isinstance(opened_scene, Err)
    opened = open_gate(
        conn,
        scene_id=scene_id,
        gate_seq=1,
        options=("Ask her again", "Hold your tongue"),
        now=NOW,
    )

    assert not isinstance(opened, Err)
    submitted = submit_gate(
        conn,
        gate_id=opened.value.gate_id,
        submission_id="crashed-sub",
        intent_text="the crashed words",
        now=NOW,
    )
    assert not isinstance(submitted, Err)
    begin_resolving(conn, gate_id=opened.value.gate_id, now=NOW)
    fence = open_runtime_epoch(conn)
    from elc.world.action import Adjudication, ReplanScope, StateEffect

    ruling = Adjudication(
        interpretation="i",
        outcome="o",
        actual_action="a",
        consequences="c",
        state_effects=(StateEffect(key="k", statement="s"),),
        participants=(PLAYER, BRYN, CORVIN),
        replan_scope=ReplanScope.NONE,
    )
    committed = commit_action(
        conn,
        world_store=SqliteWorldStore(conn, fence),
        narrative_store=SqliteNarrativeStore(conn, fence),
        gate_id=opened.value.gate_id,
        submission_id="crashed-sub",
        adjudication=ruling,
        duration_ticks=5,
        now=NOW,
    )
    assert not isinstance(committed, Err)
    return scene_id


def test_a_crashed_turn_reruns_the_stored_submission(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    scene_id = _precommit_ruling(planned)
    queues = _default_queues()
    # the owed continuation lands FIRST (one narration), then the user's
    # new words run as their own reply beat (dispatch + characters +
    # ONE fresh adjudication + narration).
    queues["narrator"] = [_narration_payload()] * 2
    queues["dispatch"] = [_dispatch_payload()] * 2
    queues["character"] = [_proposal_payload()] * 4
    completion = ScriptedDSCompletion(**queues)
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="fresh-sub", intent_text="brand new words"),
        NOW,
    )
    assert run.error is None
    # the stored ruling was NOT re-judged — the one fresh adjudication
    # is the NEW words' own (the second beat's)
    assert completion.count("adjudicate") == 1
    turn = run.turns[0]
    assert turn.gate_id is not None
    gate_row = planned.execute(
        "SELECT status FROM user_gate WHERE gate_id = ?", (turn.gate_id,)
    ).fetchone()
    assert gate_row[0] == "CLOSED"
    action_row = planned.execute(
        "SELECT submission_id FROM user_action WHERE gate_id = ?",
        (turn.gate_id,),
    ).fetchone()
    assert action_row[0] == "crashed-sub"  # the durable submission, not the fresh one
    # the user's new words landed as the SECOND beat's own ruling
    second = run.turns[1]
    assert second.beat_kind == "reply"
    second_action = planned.execute(
        "SELECT submission_id FROM user_action ORDER BY user_action_id DESC LIMIT 1"
    ).fetchone()
    assert second_action[0] == "fresh-sub"
    # the narration landed as the owed continuation carrying the ref
    lineage = planned.execute(
        "SELECT outcome_ref FROM narrative_passage WHERE scene_id = ?"
        " ORDER BY segment_seq ASC",
        (scene_id,),
    ).fetchall()
    assert lineage and lineage[0][0] == f"{turn.gate_id}-a"


def test_an_advance_first_lands_the_owed_continuation(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    _precommit_ruling(planned)
    queues = _default_queues()
    queues["narrator"] = [
        _narration_payload(addresses_you=False, beat_complete=True),
        _narration_payload(addresses_you=True),
    ]
    queues["dispatch"] = [_dispatch_payload()] * 2
    completion = ScriptedDSCompletion(**queues)
    engine = _engine(planned, stores, completion)
    run = engine.drive(DS_WORLD_ID, AdvanceBeat(), NOW)
    assert run.error is None
    # turn 1 IS the owed continuation (the gate closed in its commit)
    first = run.turns[0]
    assert first.gate_id is not None
    gate_row = planned.execute(
        "SELECT status FROM user_gate WHERE gate_id = ?", (first.gate_id,)
    ).fetchone()
    assert gate_row[0] == "CLOSED"
    # the requested advance followed as its own beat and stopped at
    # its own address marker
    assert run.turns[1].gate_id is None
    assert run.stopped_on == "addresses_you"


# ---------------------------------------------------------------------------
# 8 — the replay anchor (§10 F1)
# ---------------------------------------------------------------------------


def test_turn_steps_read_back_in_canonical_order(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    completion = ScriptedDSCompletion(**_default_queues())
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="…"),
        NOW,
    )
    chapter_id = run.chapter_id
    assert chapter_id is not None
    steps = turn_steps_of(planned, chapter_id)
    kinds = [step.kind for step in steps]
    assert kinds == ["ruling", "narration"]
    assert steps[0].outcome is not None
    assert steps[1].passage_id is not None
    assert steps[0].actual_end_tick <= steps[1].actual_start_tick


# ---------------------------------------------------------------------------
# 9 — the offstage settlement (§7)
# ---------------------------------------------------------------------------


def test_a_scene_scope_ruling_consumes_its_replan(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """§1b: the replan_scope three-word semantics ride unchanged — a
    ruling whose scope is SCENE leaves a PENDING obligation that the
    spine consumes through the same library protocol (the obligation
    lands APPLIED, the dossier revision moves; a chapter does not
    settle under an unfinished replan, so the consumption is the
    settle path's own precondition)."""

    world_store, cast_store, bible_store, narrative = stores
    from elc.world.llm_providers import (
        LlmDirectorProvider,
        LlmPlannerProvider,
        LlmResolverProvider,
        LlmWriterProvider,
    )
    from elc.world.pipeline import Pipeline

    queues = _default_queues()
    queues["adjudicate"] = [
        _adjudication_payload().replace(
            '"replan_scope": "NONE"', '"replan_scope": "SCENE"'
        )
    ]
    queues["narrator"] = [_narration_payload()] * 2
    _planner_answer = json.dumps(
        {
            "pov_actor_id": PLAYER,
            "participants": [PLAYER, BRYN, CORVIN],
            "planned_start_tick": 1320,
            "place": "the bridge head, lantern light",
            "entry_goals": "the walk tests the painter's story",
            "exit_condition": "the fog turns all",
            "elasticity": "one walk",
            "revealable": "the paint's freshness",
            "must_hide": "who painted the mark",
        },
        ensure_ascii=False,
    )
    queues["planner"] = [_planner_answer]
    completion = ScriptedDSCompletion(**queues)
    # the SAME scripted seam rides the engine AND the replan pipeline
    # (the consumption is one prompt family on one script)
    replan_pipeline = Pipeline(
        planned,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        writer_provider=LlmWriterProvider(completion),
        planner_provider=LlmPlannerProvider(completion),
        director_provider=LlmDirectorProvider(completion),
        resolver_provider=LlmResolverProvider(completion),
        action_duration_ticks=5,
    )
    engine = _engine(planned, stores, completion)
    engine._replan_pipeline = replan_pipeline
    scene_id = planned.execute(
        "SELECT scene_id FROM world_scene"
        " WHERE chapter_id = (SELECT MAX(chapter_id) FROM world_chapter)"
    ).fetchone()[0]
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-scene", intent_text="…"),
        NOW,
    )
    assert run.error is None
    obligation = planned.execute(
        "SELECT status FROM action_replan"
        " WHERE replan_request_id = 'rp:emberkeep-ds-01-ch01-s01-g01:sub-scene'"
    ).fetchone()
    assert obligation is not None
    assert obligation[0] == "APPLIED"  # consumed in the same drive
    dossier_after = narrative.adopted_dossier(scene_id)
    assert dossier_after is not None
    # rev 1 is open_scene's own; the SCENE replan's revised element is rev 2
    assert dossier_after.dossier_revision == 2
    assert dossier_after.place == "the bridge head, lantern light"
    assert any("replan consumed" in note for note in run.notes)


def test_the_settlement_lands_the_offstage_delta(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    completion = ScriptedDSCompletion(**_default_queues())
    engine = _engine(planned, stores, completion)
    engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="…"),
        NOW,
    )
    queues = {
        "narrator": [
            _narration_payload(
                prose="The lantern gutters out; the fog takes the bridge.",
                addresses_you=False,
                beat_complete=True,
            )
        ],
        "dispatch": [
            _dispatch_payload(
                responders=(),
                pacing="settle",
                options=(),
                world_event="The fog closes the crossing; the town goes to bed.",
            )
        ],
        "character": [
            _proposal_payload(
                speech="",
                action="counts the bridge ledger by lamplight",
                intent="see the mark scrubbed before the clerk comes",
                private_thought="she will watch the painter tomorrow",
            ),
            _proposal_payload(
                speech="",
                action="tarps the punt and says nothing",
                intent="keep the water's secret one more night",
                private_thought="",
            ),
        ],
    }
    settle_engine = _engine(
        planned, stores, ScriptedDSCompletion(**queues)
    )
    record = settle_engine.settle_chapter(DS_WORLD_ID, NOW)
    # the offstage event landed with the living goal / mood facts
    row = planned.execute(
        "SELECT narration, kind FROM world_event WHERE event_id = ?",
        (record.offstage_event_id,),
    ).fetchone()
    assert row is not None
    assert row[1] == "offstage"
    assert "fog closes" in row[0]
    for key in (
        "protagon.bryn.goal",
        "protagon.bryn.mood",
        "protagon.corvin.goal",
    ):
        fact = planned.execute(
            "SELECT statement FROM world_state_fact"
            " WHERE canonical_key = ? AND status = 'CURRENT'",
            (key,),
        ).fetchone()
        assert fact is not None, key
    # the consolidation anchored to the offstage event
    han_read = v3_memory_view(
        planned, world_id=DS_WORLD_ID, viewer_id=CORVIN
    )
    assert not isinstance(han_read, Err)
    assert any(
        memory.source_event_id == record.offstage_event_id
        for memory in han_read.value.memories
    )
    # the chapter closed through the NCP-4 compression
    chapter = planned.execute(
        "SELECT status FROM world_chapter ORDER BY chapter_index DESC LIMIT 1"
    ).fetchone()
    assert chapter[0] == "CLOSED"
    settlement = planned.execute(
        "SELECT summary FROM chapter_settlement WHERE chapter_id = ?",
        (record.chapter_id,),
    ).fetchone()
    assert settlement is not None
    # a settled chapter refuses a second settle
    from elc.world.turns import TurnRefusal

    with pytest.raises(TurnRefusal):
        settle_engine.settle_chapter(DS_WORLD_ID, NOW)


# ---------------------------------------------------------------------------
# 10 — the prompt pins (the arms' contracts, from the driven prompts)
# ---------------------------------------------------------------------------


def test_the_driven_prompts_carry_the_arms_contracts(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    queues = _default_queues()
    queues["dispatch"] = [_dispatch_payload()] * 2
    queues["character"] = [_proposal_payload()] * 4
    queues["narrator"] = [_narration_payload()] * 2
    queues["adjudicate"] = [_adjudication_payload()] * 2
    completion = ScriptedDSCompletion(**queues)
    engine = _engine(planned, stores, completion)
    engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="I did not paint it."),
        NOW,
    )
    engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-2", intent_text="Ask her again."),
        NOW,
    )
    dispatch_prompt = completion.prompts["dispatch"][0]
    assert f"- {BRYN} (布丽恩·灰隼)" in dispatch_prompt
    assert '"options"' in dispatch_prompt  # the 2–4 natural actions face
    assert '"reading"' in dispatch_prompt  # the intent reading rides the same answer
    assert "I did not paint it." in dispatch_prompt  # the user's own words

    character_prompt = completion.prompts["character"][0]
    assert "private seat" in character_prompt
    assert "private_context" in character_prompt  # the durable profile rides
    # the SECOND reply's pack carries the memory the first ruling landed
    second_pack = completion.prompts["character"][2]
    assert "(EXPERIENCED)" in second_pack

    narrator_prompt = completion.prompts["narrator"][0]
    assert "SECOND PERSON" in narrator_prompt
    # the body sovereignty law rides the prompt (DS-3 §12.8 — the
    # negative half the old clause carried, now with the perceptual
    # face and the 留白 half)
    assert "Body sovereignty" in narrator_prompt
    assert "PERCEIVES" in narrator_prompt
    # the proposals ride their PUBLIC face only
    assert "watch whether the painter flinches" not in narrator_prompt
    assert "lifts the lantern" in narrator_prompt
    # the committed ruling is the canon the prose resumes
    assert "committed ruling" in narrator_prompt

    adjudicate_prompt = completion.prompts["adjudicate"][0]
    assert f"- {BRYN}:" in adjudicate_prompt  # the k proposals block
    assert "private_thought" in adjudicate_prompt  # the judge weighs it all
    assert "MUST" in adjudicate_prompt  # the player id is demanded
    assert "I did not paint it." in adjudicate_prompt


# ---------------------------------------------------------------------------
# 11 — the opening seed (§11)
# ---------------------------------------------------------------------------


def test_the_opening_seed_is_a_draft_and_replays_idempotent(
    seeded: sqlite3.Connection, stores: tuple
) -> None:
    assert DS_OPENING_IS_DRAFT is True
    world_store, cast_store, bible_store, _narrative = stores
    row = seeded.execute(
        "SELECT name FROM world WHERE world_id = ?", (DS_WORLD_ID,)
    ).fetchone()
    assert row is not None and row[0] == "灰隼要塞 · 龙焰夜"
    actors = {
        actor.actor_id for actor in world_store.actors_of(DS_WORLD_ID)
    }
    assert actors == {BRYN, CORVIN}
    player = cast_store.player_character(DS_WORLD_ID)
    assert player is not None and player.player_character_id == PLAYER
    # a same-shape replay is the zero-write no-op
    outcome = seed_ds_world(
        seeded,
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        now=NOW,
    )

    assert not isinstance(outcome, Err)


# ---------------------------------------------------------------------------
# 12 — the world beats' own minds (DS-3, §1 跳①不跳④ / ③不退化)
# ---------------------------------------------------------------------------


def test_an_advance_beat_runs_the_character_arms(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """§1's world beat skips ① only: the dispatch decides, EVERY
    responding protagonist's own model proposes (④ does not skip), ONE
    world adjudication synthesizes the δ (⑤), the δ lands as a
    chronicle event (⑥), the private thoughts anchor to it, and the
    narration renders the outcome beside the proposals' public face —
    with the proposal-fidelity law stated in the prompt itself."""

    queues = _default_queues()
    queues["narrator"] = [_narration_payload()]
    completion = ScriptedDSCompletion(**queues)
    engine = _engine(planned, stores, completion)
    run = engine.drive(DS_WORLD_ID, AdvanceBeat(), NOW)
    assert run.error is None
    assert run.stopped_on == "addresses_you"
    turn = run.turns[0]
    assert turn.beat_kind == "advance"
    # the proposals ride the turn record — the traceability face
    assert [p.actor_id for p in turn.proposals] == [BRYN, CORVIN]
    # ⑤⑥: the δ landed as a world chronicle event with its effects
    event = planned.execute(
        "SELECT kind, narration, source FROM world_event"
        " WHERE event_id = ?",
        (f"{turn_event_scene_id(planned)}:beat-1",),
    ).fetchone()
    assert event is not None
    assert event[0] == "world"
    assert "steward accepts" in event[1]
    assert event[2] == "ds-world"
    fact = planned.execute(
        "SELECT statement FROM world_state_fact"
        " WHERE canonical_key = 'bridge.mark' AND status = 'CURRENT'"
    ).fetchone()
    assert fact is not None and "vermilion" in fact[0]
    # the private thoughts anchor to the world event (the characters'
    # OWN memory rows)
    for actor in (BRYN, CORVIN):
        read = v3_memory_view(planned, world_id=DS_WORLD_ID, viewer_id=actor)
        assert not isinstance(read, Err)
        assert any(
            memory.kind is MemoryKind.INFERRED
            and "fresh" in memory.content
            for memory in read.value.memories
        ), actor
    # the prompts: the world adjudicator carries NO user submission; the
    # narrator carries the outcome, the public proposals and the
    # fidelity law
    world_prompt = completion.prompts["adjudicate"][0]
    assert "NO user action" in world_prompt
    assert "user's own submission" not in world_prompt
    assert "nothing in the outcome may" in world_prompt
    assert "decide, speak or act for them" in world_prompt
    narrator_prompt = completion.prompts["narrator"][0]
    assert "What actually happens this beat" in narrator_prompt
    assert "steward accepts" in narrator_prompt
    assert "lifts the lantern" in narrator_prompt
    assert "never invent further words" in narrator_prompt
    assert (
        "watch whether the painter flinches" not in narrator_prompt
    )  # the private face never rides
    # the whole chain: dispatch + 2 characters + adjudication + narration
    assert run.calls_used == 5


def turn_event_scene_id(conn: sqlite3.Connection) -> str:
    """The planned world's one scene id (the world event's id prefix)."""

    return str(
        conn.execute(
            "SELECT scene_id FROM world_scene"
            " WHERE chapter_id = (SELECT MAX(chapter_id) FROM world_chapter)"
        ).fetchone()[0]
    )


def test_a_world_beat_replays_from_its_stored_delta(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """§10 F8 for the world beats: a crash after the δ landed but before
    the segment committed re-runs the beat from the stored δ — the
    adjudication is NOT re-judged (the replay read answers the stored
    outcome) and the honest note rides the answer."""

    queues = _default_queues()
    queues["narrator"] = [
        _narration_payload(),
        _narration_payload(),
    ]
    completion = ScriptedDSCompletion(**queues)
    engine = _engine(planned, stores, completion)
    first = engine.drive(DS_WORLD_ID, AdvanceBeat(), NOW)
    assert first.error is None
    assert len(first.turns) == 1
    scene_id = turn_event_scene_id(planned)
    # the crash window: the segment never committed (its passage, its
    # commit row and the SEGMENT COMMIT's own chronicle line are gone;
    # the world δ's event row stays — the replay anchor)
    planned.execute(
        "DELETE FROM segment_commit WHERE scene_id = ? AND kind = 'SEGMENT'",
        (scene_id,),
    )
    planned.execute(
        "DELETE FROM narrative_passage WHERE scene_id = ?", (scene_id,)
    )
    planned.execute(
        "DELETE FROM actor_memory WHERE source_event_id LIKE ?",
        (f"{scene_id}-e%",),
    )
    planned.execute(
        "DELETE FROM world_event WHERE event_id LIKE ?",
        (f"{scene_id}-e%",),
    )
    planned.commit()
    rerun = engine.drive(DS_WORLD_ID, AdvanceBeat(), NOW)
    assert rerun.error is None
    # the stored δ was NOT re-judged — one adjudication total
    assert completion.count("adjudicate") == 1
    assert any(
        "replayed from its stored δ" in note for note in rerun.notes
    )
    # the beat still landed its prose
    assert len(rerun.turns) == 1
    assert rerun.turns[0].proposals == ()


def test_the_dispatch_input_carries_the_situation_plan(
    seeded: sqlite3.Connection, stores: tuple
) -> None:
    """③不退化 (DS-3 §6): the scheduling input carries the chapter's
    situation plan and the prompt demands the decision move it — the
    登场 / 逼近 choices stay cross-checkable against the plan's own
    fields. 拔 plan 块（变异预演「拔臂」型）：a legacy blueprint row
    carries no plan, and the prompt renders no block — the block is
    load-bearing, not decoration."""

    from elc.world.ds_situation import plan_situation_chapter
    from elc.world.llm_providers import LlmSituationPlannerProvider

    class _SituationCompletion(ScriptedDSCompletion):
        def complete(self, prompt: str) -> CompletionOutcome:
            if "situation planner of a two-seat" in prompt:
                self.prompts.setdefault("situation", []).append(prompt)
                return CompletionOutcome(
                    text=json.dumps(
                        {
                            "where_you_stand": "the bridge head, lantern"
                                " light, the town's question on you",
                            "place": "the bridge head",
                            "what_presses_on_you": "the county clerk"
                                " arrives at dawn",
                            "first_speaker": BRYN,
                            "first_words": "Was it there when you"
                                " crossed?",
                            "open_question": "will your answer keep you"
                                " out of the water gate",
                            "world_event_candidates": [
                                "the fog closes the crossing before"
                                " dawn",
                            ],
                            "protagonist_goals": {
                                BRYN: "keep the ledger clean",
                                CORVIN: "keep the water's secret",
                            },
                            "pacing": "tighter every hour",
                            "settlement_expectation": "where the answer"
                                " left you",
                        },
                        ensure_ascii=False,
                    ),
                    error=None,
                )
            return super().complete(prompt)

    completion = _SituationCompletion(**_default_queues())
    world_store, cast_store, bible_store, narrative = stores
    outcome = plan_situation_chapter(
        seeded,
        world_store=world_store,
        cast_store=cast_store,
        bible_store=bible_store,
        narrative_store=narrative,
        planner=LlmSituationPlannerProvider(completion),
        world_id=DS_WORLD_ID,
        now=NOW,
    )
    assert not isinstance(outcome, Err), outcome.error
    assert outcome.value.fresh_plan is True
    engine = _engine(seeded, stores, completion)
    run = engine.drive(DS_WORLD_ID, AdvanceBeat(), NOW)
    assert run.error is None
    dispatch_prompt = completion.prompts["dispatch"][0]
    # the plan rides the input, field for field
    assert "The chapter's situation plan" in dispatch_prompt
    assert "the county clerk arrives at dawn" in dispatch_prompt
    assert "the fog closes the crossing before dawn" in dispatch_prompt
    assert "will your answer keep you" in dispatch_prompt
    # the decision must move it
    assert "must move this plan" in dispatch_prompt


def test_a_legacy_blueprint_plan_renders_no_plan_block(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """变异预演（拔臂→红）：the plan block rides the situation document
    — a legacy blueprint row (the retired test face's own storage)
    carries no document, and the prompt renders no block. The block is
    load-bearing, not decoration."""

    queues = _default_queues()
    queues["narrator"] = [_narration_payload()]
    legacy_completion = ScriptedDSCompletion(**queues)
    legacy_engine = _engine(planned, stores, legacy_completion)
    legacy_run = legacy_engine.drive(DS_WORLD_ID, AdvanceBeat(), NOW)
    assert legacy_run.error is None
    legacy_prompt = legacy_completion.prompts["dispatch"][0]
    assert "The chapter's situation plan" not in legacy_prompt
    assert "must move this plan" not in legacy_prompt


# ---------------------------------------------------------------------------
# 13 — the body sovereignty law (DS-3, §12.8)
# ---------------------------------------------------------------------------


def test_the_narration_prompt_carries_the_sovereignty_contract(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """§12.8 in the prompt itself, both wording faces (V3-8g 措辞律):
    the perceptual face only (看到/听到/感觉到/被作用), the world's own
    actions allowed, the reader's spontaneous acts entering only
    through their typed words or staying unwritten, and the definition's
    own violation/compliance example pair. 拔句→红（评审变异组「主权拔
    除」型的自证面）：the contract rides ONE constant — the driven
    prompt pin above redds the moment the prompt stops carrying it; this
    test pins the constant's both faces and the load-bearing example."""

    from elc.world.llm_providers import _SOVEREIGNTY_SENTENCE

    en = _SOVEREIGNTY_SENTENCE["en"]
    zh = _SOVEREIGNTY_SENTENCE["zh"]
    # the three halves of the law, en
    assert "PERCEIVES" in en
    assert "the world's own action" in en
    assert "stay unwritten, awaiting them" in en
    # the definition's own violation / compliance pair
    assert "you hold your breath" in en
    assert "the lamp moved over" in en
    # the zh face
    assert "身体主权" in zh
    assert "感知面" in zh
    assert "留白待你" in zh
    assert "你屏住呼吸" in zh
    assert "灯移了过去" in zh

    # the zh wording face rides the driven prompt at language="zh"
    queues = _default_queues()
    queues["narrator"] = [_narration_payload()]
    completion = ScriptedDSCompletion(**queues)
    engine = _engine(planned, stores, completion, language="zh")
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-zh", intent_text="…"),
        NOW,
    )
    assert run.error is None
    zh_prompt = completion.prompts["narrator"][0]
    assert "身体主权" in zh_prompt
    assert "留白待你" in zh_prompt
    assert "Body sovereignty" not in zh_prompt


# ---------------------------------------------------------------------------
# 14 — the rhythm law (DS-3, §4: the ceilings are pure guardrails)
# ---------------------------------------------------------------------------


def test_the_rhythm_law_drives_to_a_natural_stop(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """§4's default: the drive continues past ``beat_complete`` beats
    and stops at the natural hanging point — 「轮到你了」 is the ONLY
    routine stop. Two complete beats, then an address: three turns,
    stopped on the marker, no ceiling touched."""

    queues = _default_queues()
    queues["narrator"] = [
        _narration_payload(addresses_you=False, beat_complete=True),
        _narration_payload(addresses_you=False, beat_complete=True),
        _narration_payload(),
    ]
    completion = ScriptedDSCompletion(**queues)
    completion._queues["dispatch"] = [_dispatch_payload()] * 3
    completion._queues["character"] = [_proposal_payload()] * 6
    completion._queues["adjudicate"] = [_adjudication_payload()] * 3
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="…"),
        NOW,
    )
    assert run.error is None
    assert run.stopped_on == "addresses_you"
    assert len(run.turns) == 3
    assert run.note is None  # a natural stop carries no guardrail note
    assert run.stop_log[0].reason == "beat_complete"
    assert run.stop_log[0].stopped is False
    assert run.stop_log[-1].reason == "addresses_you"


def test_a_hold_pacing_no_longer_stops(
    planned: sqlite3.Connection, stores: tuple
) -> None:
    """变异预演（回退修复→红）：under the old law a ``hold`` dispatch
    word stopped the drive (「三段一停」's sibling) — under the rhythm
    law the pacing word is a scheduling signal only: the hold beat
    continues and the drive stops at the NEXT natural hanging point."""

    queues = _default_queues()
    queues["narrator"] = [
        _narration_payload(addresses_you=False, beat_complete=True),
        _narration_payload(),
    ]
    completion = ScriptedDSCompletion(**queues)
    completion._queues["dispatch"] = [
        _dispatch_payload(pacing="hold"),
        _dispatch_payload(),
    ]
    completion._queues["character"] = [_proposal_payload()] * 4
    completion._queues["adjudicate"] = [_adjudication_payload()] * 2
    engine = _engine(planned, stores, completion)
    run = engine.drive(
        DS_WORLD_ID,
        ReplyBeat(submission_id="sub-1", intent_text="…"),
        NOW,
    )
    assert run.error is None
    # the hold beat continued — the stop is the next address, not the
    # pacing word
    assert run.stopped_on == "addresses_you"
    assert len(run.turns) == 2
    assert run.stop_log[0].pacing == "hold"
    assert run.stop_log[0].reason == "beat_complete"
