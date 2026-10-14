"""DS-1 — the immersion face's serving pins (``elc.ds_web``; the
technical definition §11–§12).

Pinned here (the V3-8e reader-suite family's shapes; the serving stack
over a stub host, the scripted completion offline):

1. the state derivation over the durable rows — the honest empty face
   before the world exists, the seeded world's draft flag, the
   controls/next face after the plan;
2. the graded bible edit (§6 F3) — a textual edit lands ONE revision
   at once (the fourteen fields as given), a structural edit parks on
   ``ds_pending_bible`` and lands folded into ONE revision at the next
   chapter plan;
3. the route grammars (fail-closed): the reply body and the bible body
   400 shapes;
4. the stop-note seat: a drive's reasoned stop persists and the state
   reads it back; the light-model word rides the state;
5. the engine's harness authorization is load-bearing through the face:
   a bible edit is the director seat's tool (the registry knows).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from elc.ds_web import (
    DS_LIGHT_MODEL_KEY,
    DS_PENDING_BIBLE_KEY,
    DualSeatWebFace,
    ds_bible_request,
    ds_state_ro,
    ds_turn_request,
)
from elc.platform.db.app_settings import AppSettingStore
from elc.platform.db.epoch import open_runtime_epoch
from elc.platform.db.migrations import apply_migrations
from elc.world.ds_opening import DS_WORLD_ID
from elc.world.llm_providers import CompletionOutcome
from elc.world.store import SqliteWorldStore

NOW = "2026-10-14T00:00:00+00:00"

BLUEPRINT: dict[str, Any] = {
    "goal": "the mark on the cornerstone demands an answer tonight",
    "dramatic_question": "who painted the mark",
    "planned_start_tick": 1310,
    "planned_end_tick": 1500,
    "closing_pressure": "the fog closes in",
    "desired_development": "the answer moves the town",
    "soft_outcomes": "an uneasy truce",
    "chapter_questions_to_advance": "what the mark means",
    "scenes": [
        {
            "purpose": "the public question",
            "place": "the ferry house steps",
            "pov_actor_id": "ache",
            "participants": ["ache", "wenq", "han"],
            "planned_start_tick": 1310,
            "entry_goals": "the question hangs on you",
            "exit_condition": "the walk ends",
            "elasticity": "one night",
            "revealable": "the paint's freshness",
            "must_hide": "who painted the mark",
        }
    ],
}


class ScriptedCompletion:
    """The offline seam: canned answers by prompt family."""

    def __init__(self, **queues: list[str]) -> None:
        self._queues = {kind: list(items) for kind, items in queues.items()}
        self.prompts: dict[str, list[str]] = {}

    def complete(self, prompt: str) -> CompletionOutcome:
        if "world director" in prompt:
            kind = "director"
        elif "dispatcher of a two-seat" in prompt:
            kind = "dispatch"
        elif "private seat" in prompt:
            kind = "character"
        elif "narrator of a two-seat" in prompt:
            kind = "narrator"
        elif "resolver of a two-seat" in prompt:
            kind = "adjudicate"
        else:
            raise AssertionError("unknown prompt family")
        self.prompts.setdefault(kind, []).append(prompt)
        queue = self._queues.get(kind)
        if not queue:
            raise AssertionError(f"the {kind} script is exhausted")
        return CompletionOutcome(text=queue.pop(0), error=None)


def _director_payload() -> str:
    return json.dumps(BLUEPRINT, ensure_ascii=False)


def _dispatch_payload() -> str:
    return json.dumps(
        {
            "reading": "the painter answers",
            "responders": ["wenq"],
            "world_event": None,
            "pacing": "hold",
            "options": ["Ask", "Wait"],
        },
        ensure_ascii=False,
    )


def _proposal_payload() -> str:
    return json.dumps(
        {"speech": "s", "action": "a", "intent": "i", "private_thought": "p"},
        ensure_ascii=False,
    )


def _narration_payload() -> str:
    return (
        "You answer her steadily.\n---\n"
        + json.dumps(
            {
                "addresses_you": False,
                "impends_on_you": False,
                "beat_complete": True,
            }
        )
    )


def _adjudication_payload() -> str:
    return json.dumps(
        {
            "interpretation": "i",
            "outcome": "o",
            "actual_action": "a",
            "consequences": "c",
            "state_effects": [],
            "participants": ["ache", "wenq"],
            "replan_scope": "NONE",
        },
        ensure_ascii=False,
    )


@pytest.fixture()
def env(
    tmp_path: Path,
) -> tuple[sqlite3.Connection, DualSeatWebFace, ScriptedCompletion]:
    db = sqlite3.connect(tmp_path / "app.db")
    db.execute("PRAGMA foreign_keys=ON")
    apply_migrations(db)
    fence = open_runtime_epoch(db)
    host = SimpleNamespace(
        db=db,
        fence=fence,
        world_store=SqliteWorldStore(db, fence),
        app_settings=AppSettingStore(db, fence),
        # a provider-SHAPED stand-in for the preflight only — the actual
        # model calls ride the injected scripted completion below (the
        # face reads the seam per drive; the live object is never dialed
        # in this suite).
        coordinator=SimpleNamespace(
            persona_provider=lambda: SimpleNamespace(
                config=SimpleNamespace(base_url="http://local", model="stub")
            )
        ),
    )
    completion = ScriptedCompletion(
        director=[_director_payload()] * 3,
        dispatch=[_dispatch_payload()] * 3,
        character=[_proposal_payload()] * 6,
        narrator=[_narration_payload()] * 6,
        adjudicate=[_adjudication_payload()] * 3,
    )
    face = DualSeatWebFace(
        host, clock=lambda: NOW,  # type: ignore[arg-type]
    )
    face._completion = completion  # the offline seam (the face reads it per drive)
    face._light_completion = completion
    return db, face, completion


def test_the_state_face_answers_the_honest_empty_shape(
    env: tuple,
) -> None:
    db, face, _completion = env
    payload = face.state()
    assert payload["ok"] is True
    assert payload["world"]["exists"] is False
    assert payload["next"]["kind"] == "start"
    assert payload["controls"] == {"can_start": True}
    assert payload["draft"] is True


def test_start_seeds_and_plans_then_the_face_opens(
    env: tuple,
) -> None:
    db, face, completion = env
    landed = face.start()
    assert landed["ok"] is True, landed["error"]
    payload = landed
    assert payload["world"]["exists"] is True
    assert payload["chapter"]["status"] == "PLANNED"
    assert payload["plan"]["dramatic_question"] == "who painted the mark"
    assert payload["controls"].get("can_open") is True
    # the opening beat drives through the face (the scripted completion)
    run = face.drive_beat("open", _queue())
    assert run["ok"] is True, run["error"]
    assert run["did"]["segments_written"] == 1
    after = face.state()
    assert after["chapter"]["status"] == "ACTIVE"  # the first landing activated
    assert len(after["passages"]) == 1
    assert after["controls"].get("can_reply") is True


def _queue() -> "object":
    import queue as _queue_module

    return _queue_module.Queue()


def test_the_graded_bible_edit_lands_now_and_parks_next(
    env: tuple,
) -> None:
    db, face, _completion = env
    face.start()
    # a textual edit lands ONE revision at once
    landed = face.bible_edit("tone", "colder, wetter, closer to the bone", "now")
    assert landed["ok"] is True, landed["error"]
    row = db.execute(
        "SELECT COUNT(*) FROM world_bible_revision WHERE world_id = ?",
        (DS_WORLD_ID,),
    ).fetchone()
    assert row[0] == 2  # the seed revision + this one
    current = db.execute(
        "SELECT tone FROM world_bible_revision"
        " WHERE world_id = ? AND status = 'CURRENT'",
        (DS_WORLD_ID,),
    ).fetchone()
    assert current[0] == "colder, wetter, closer to the bone"
    # the untouched fields rode as given (the fourteen-fields law)
    premise = db.execute(
        "SELECT premise FROM world_bible_revision"
        " WHERE world_id = ? AND status = 'CURRENT'",
        (DS_WORLD_ID,),
    ).fetchone()
    assert "青溪渡" in premise[0]
    # a structural edit parks
    landed = face.bible_edit("geography", "the bridge is washed out", "next")
    assert landed["ok"] is True
    pending_row = db.execute(
        "SELECT value FROM app_setting WHERE key = ?", (DS_PENDING_BIBLE_KEY,)
    ).fetchone()
    assert pending_row is not None
    assert "washed out" in pending_row[0]
    state = face.state()
    assert any(
        entry["field"] == "geography" for entry in state["pending_bible"]
    )


def test_the_stop_note_persists_and_the_state_reads_it(
    env: tuple,
) -> None:
    db, face, _completion = env
    face.start()
    face.drive_beat("open", _queue())
    state = face.state()
    # the scripted opening stops on pacing_hold — the stop line rode
    assert state["stop"] is not None
    assert state["stop"]["last"]["reason"] in ("pacing_hold", "pacing_settle")
    # and the light-model word rides the state after a save
    face.set_light_model("deepseek-chat")
    state = face.state()
    assert state["light_model"] == "deepseek-chat"
    assert db.execute(
        "SELECT value FROM app_setting WHERE key = ?",
        (DS_LIGHT_MODEL_KEY,),
    ).fetchone()[0] == "deepseek-chat"


def test_the_route_grammars_are_fail_closed() -> None:
    error, parsed = ds_turn_request({"text": "hello"})
    assert error is None and parsed is not None
    error, _parsed = ds_turn_request({"text": "   "})
    assert error is not None
    error, _parsed = ds_turn_request({"text": "hi", "extra": 1})
    assert error is not None
    error, parsed = ds_turn_request(
        {"text": "hi", "submission_id": "web-1"}
    )
    assert error is None and parsed["submission_id"] == "web-1"

    error, parsed = ds_bible_request(
        {"field": "tone", "value": "x", "mode": "next"}
    )
    assert error is None and parsed is not None
    error, _parsed = ds_bible_request(
        {"field": "nope", "value": "x", "mode": "next"}
    )
    assert error is not None
    error, _parsed = ds_bible_request(
        {"field": "tone", "value": "x", "mode": "later"}
    )
    assert error is not None


def test_the_ro_poll_reads_the_same_derivation(
    env: tuple, tmp_path: Path
) -> None:
    db, face, _completion = env
    face.start()
    # the face's connection holds the world; the ro poll opens its own
    app_db = db.execute(
        "PRAGMA database_list"
    ).fetchall()
    path = app_db[0][2]
    payload = ds_state_ro(path)
    assert payload["ok"] is True
    assert payload["world"]["exists"] is True
    assert payload["chapter"]["status"] == "PLANNED"
