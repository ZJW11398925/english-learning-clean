"""V3-8i — the gateless floor and the plan's gates over the real
serving stack (the paradigm shift §10.6; the pure faces ride
``tests/world/test_v3_8i_gates_and_anchor.py``).

**What this suite proves, stated honestly.** The loop is exercised over
the real ``run_web`` chain (the V3-8e suite's own posture: an injected
transport answering the Gold screenplay — no socket, no real
credential). Chapter one rides the gold author scripts exactly as the
suite family always drove it; chapter two's plan is the cut's own
scripted Blueprint — one gateless variant (the floor's domain) and one
gate-declaring variant whose ``required_beats`` become the scenes'
scripts.

Pinned here:

1. the floor (§10.6 item 3, the production constant 4) — a continue in
   the open scene writes four fresh segments and stops with the
   reasoned sentence riding ``did.note`` and the state's ``note`` (the
   ceiling's own mechanism); 「结束本场」 is offered (the scene is
   open), and the next drive clears the stale note at entry;
2. the floor never preempts a gate (the reverse pin) — a scene whose
   plan carries a gate BEYOND the floor's four segments drives straight
   past them and stops at the gate: the ``user_gate`` row opens with
   the PLAN's own options, and no floor sentence exists;
3. the plan's gates run end to end — the submission's ruling commits,
   the continuation lands with the gate closed, the drive presses on
   into the next planned scene, and its gate again — the planned will
   points are the reader's stops (§10.6 item 1's production face, on
   the serving stack).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elc.world import gold
from tests.host.test_v3_8e_reader import (
    _GoldPost,
    _read,
    v3_stack,
)
from tests.host.test_v3_8h_reader_loop import _to_chapter_two

#: The floor is never patched in this suite — these are the production
#: constant's own pins.
_YARD_PROSE = {
    1: "The yard is cold; the cart waits.",
    2: "The pack goes up; the gate shuts.",
    3: "The cart rolls out at dawn.",
    4: "The storehouse ledger's last page is copied.",
    5: "The cousin watches from the gate-stone.",
    6: "Mother counts the sacks twice.",
    7: "The axle creaks under the load.",
    8: "Lia bolts the yard gate behind them.",
}

_ROAD_PROSE = {
    1: "The lane down to the ford is muddy.",
    2: "The ford's water is higher than yesterday.",
}

_YARD_GATE_OPTIONS = (
    "load the cousin's pack first",
    "leave the carved horse behind",
    "ask Mother to decide",
)
_ROAD_GATE_OPTIONS = ("take the crossroads turn", "refuse the turn")

#: The plan-gate pins' own submission and ruling: the gold payload's
#: ``replan_scope`` is CHAPTER (the ch1 gate's pinned face — the
#: anti-railway move), which would drag the CHAPTER replan arm into
#: these pins with a per-gate obligation id no script answers. The
#: plan-gate end-to-end is about the gates the PLAN opened, so its
#: ruling keeps the plan standing (scope NONE — the honest word for a
#: move the plan survives).
_MY_INTENT = "I point at the crossroads and ask which road we take."
_MY_ADJUDICATION: dict[str, Any] = {
    "interpretation": (
        "The reader asks the household to take the road they can all"
        " walk, and to say so plainly."
    ),
    "outcome": (
        "The household takes the reader's question as the plan for the"
        " morning: the cart is loaded with the cousin's pack on it, and"
        " the road gets chosen at the crossroads, together."
    ),
    "actual_action": "the reader points and the household loads the cart",
    "consequences": "the morning's plan stands, with the reader's word in it",
    "state_effects": [
        {
            "key": "household:cart",
            "statement": "loaded; the cousin's pack rides on it",
        }
    ],
    "participants": [gold.PLAYER, gold.LIA],
    "replan_scope": "NONE",
}


def _gated_scene(
    place: str,
    tick: int,
    beats: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "purpose": "the planned scene",
        "place": place,
        "pov_actor_id": gold.LIA,
        "participants": [gold.LIA, gold.PLAYER],
        "planned_start_tick": tick,
        "entry_goals": "carry the household toward the capital",
        "exit_condition": "the scene's own question is settled",
        "elasticity": "short",
        "revealable": "",
        "must_hide": "",
        "required_beats": beats,
        "user_present": True,
    }


def _segment() -> dict[str, Any]:
    return {"kind": "segment"}


def _gate(options: list[str]) -> dict[str, Any]:
    return {
        "kind": "gate",
        "reason": (
            "what the cousin takes onto the cart is the reader's own will"
        ),
        "options": options,
    }


def _gated_ch2() -> dict[str, Any]:
    """Chapter two's Blueprint with the gate face declared and
    compliant: the yard scene plans five segments before its gate (past
    the floor — the reverse pin's own shape) and the road scene one;
    both scripts close with a segment (the derivation marks/appends
    it)."""

    return {
        "goal": (
            "Follow the carved wooden horse: get the household onto the"
            " capital road before the second frost."
        ),
        "dramatic_question": (
            "Will Lia carry the household's silence all the way to the"
            " capital, or set it down at the crossroads?"
        ),
        "planned_start_tick": 690,
        "planned_end_tick": 1200,
        "closing_pressure": (
            "the cart to the capital leaves at first light and the house"
            " is not ready"
        ),
        "desired_development": (
            "the cousin's stubbornness turns from an obstacle into a"
            " compass"
        ),
        "soft_outcomes": "a place on the cart, maybe",
        "chapter_questions_to_advance": (
            "what is waiting for this household in the capital?"
        ),
        "scenes": [
            _gated_scene(
                gold.PLACE_CH2_YARD,
                690,
                [_segment()] * 5 + [_gate(list(_YARD_GATE_OPTIONS))],
            ),
            _gated_scene(
                gold.PLACE_CH2_ROAD,
                900,
                [_segment(), _gate(list(_ROAD_GATE_OPTIONS))],
            ),
        ],
    }


def _gateless_ch2() -> dict[str, Any]:
    """Chapter two's Blueprint in the pure legacy shape — no V3-8i key
    anywhere (the judge's declared-shape scope leaves it to the floor)."""

    return {
        "goal": "the household approaches the capital road",
        "dramatic_question": "Will the cart leave on time?",
        "planned_start_tick": 690,
        "planned_end_tick": 1200,
        "closing_pressure": "the cart leaves at first light",
        "desired_development": "the packing gets done",
        "soft_outcomes": "a place on the cart, maybe",
        "chapter_questions_to_advance": "what waits in the capital?",
        "scenes": [
            {
                "purpose": "the yard at first light",
                "place": gold.PLACE_CH2_YARD,
                "pov_actor_id": gold.LIA,
                "participants": [gold.LIA, gold.PLAYER],
                "planned_start_tick": 690,
                "entry_goals": "settle whose pack goes on the cart",
                "exit_condition": "the cart is loaded, or left standing",
                "elasticity": "short",
                "revealable": "",
                "must_hide": "",
            }
        ],
    }


def _script(
    *,
    yard_keys: tuple[int, ...],
    road_keys: tuple[int, ...] = (),
    ch2: dict[str, Any],
) -> _GoldPost:
    prose = dict(gold.GOLD_PROSE)
    for key in yard_keys:
        prose[(gold.PLACE_CH2_YARD, key)] = _YARD_PROSE[key]
    for key in road_keys:
        prose[(gold.PLACE_CH2_ROAD, key)] = _ROAD_PROSE[key]
    return _GoldPost(
        script=gold.GoldScriptedCompletion(
            prose=prose,
            adjudications={
                gold.GOLD_INTENT: gold.GOLD_ADJUDICATION_PAYLOAD,
                _MY_INTENT: _MY_ADJUDICATION,
            },
            blueprints=(
                (gold.CH1, ch2),
                (None, gold.CH1_BLUEPRINT),
            ),
            replan_blueprints={
                gold.REPLAN_REQUEST_ID: gold.CH1_REPLAN_BLUEPRINT
            },
            elements={},
        )
    )


# ---------------------------------------------------------------------------
# 1 — the floor, on the production constant
# ---------------------------------------------------------------------------


def test_the_floor_stops_an_open_scene_reasoned(tmp_path: Path) -> None:
    """One continue in the open scene writes four fresh segments and
    stops with the floor's sentence riding ``did.note`` and the state's
    ``note``; 「结束本场」 is offered; the next drive clears the stale
    note at entry and walks four more (the floor is a recurring reasoned
    pause, never a wall)."""

    from elc.narrative_web import (
        V3_DRIVE_NOTE_KEY,
        V3_GATELESS_SEGMENT_FLOOR,
        _gateless_sentence,
    )

    app_db = tmp_path / "app.db"
    with v3_stack(
        app_db,
        post=_script(
            yard_keys=(1, 2, 3, 4, 5, 6, 7, 8), ch2=_gateless_ch2()
        ),
    ) as stack:
        opened = _to_chapter_two(stack)
        first_scene = opened["roster"][0]["scene_id"]
        assert opened["controls"]["can_end_scene"] is True

        driven = stack.advance()[1]
        assert driven["ok"] is True, driven["error"]
        assert driven["did"]["stopped_on"] == "gateless_floor"
        assert driven["did"]["note"] == _gateless_sentence(
            V3_GATELESS_SEGMENT_FLOOR, V3_GATELESS_SEGMENT_FLOOR
        )
        assert "这一幕还没轮到你" in driven["did"]["note"]
        assert driven["did"]["scene_id"] == first_scene
        assert driven["did"]["segments_written"] == 4
        assert driven["did"]["passage_ids"] == [
            f"{first_scene}-p{seq:04d}" for seq in range(1, 5)
        ]
        # the reasoned stop's sentence survives the page's polling, and
        # the durable seat carries it.
        state = stack.state()
        assert state["note"] == driven["did"]["note"]
        assert _read(
            app_db,
            "SELECT value FROM app_setting WHERE key = ?",
            (V3_DRIVE_NOTE_KEY,),
        ) == (driven["did"]["note"],)

        # the next drive clears the stale note at entry and writes four
        # more — the floor is a reasoned pause, the reader drives on.
        second = stack.advance()[1]
        assert second["ok"] is True
        assert second["did"]["stopped_on"] == "gateless_floor"
        assert second["did"]["segments_written"] == 4
        assert second["did"]["passage_ids"][0] == f"{first_scene}-p0005"
        assert stack.state()["note"] == second["did"]["note"]


# ---------------------------------------------------------------------------
# 2 + 3 — the plan's gates: the floor never preempts, the will points run
# ---------------------------------------------------------------------------


def test_the_floor_never_preempts_a_gate_ahead(tmp_path: Path) -> None:
    """A scene whose plan carries a gate beyond the floor's four
    segments drives straight past them and stops at the gate — the
    ``user_gate`` row opens with the PLAN's own options and no floor
    sentence exists anywhere in the answer."""

    app_db = tmp_path / "app.db"
    with v3_stack(
        app_db,
        post=_script(
            yard_keys=(1, 2, 3, 4, 5), ch2=_gated_ch2()
        ),
    ) as stack:
        opened = _to_chapter_two(stack)
        first_scene = opened["roster"][0]["scene_id"]
        assert opened["roster"][0]["anchored"] is True  # the plan's script

        driven = stack.advance()[1]
        assert driven["ok"] is True, driven["error"]
        # five fresh segments — past the floor — and the stop is the
        # gate, never the floor: a gate ahead is never preempted.
        assert driven["did"]["stopped_on"] == "gate"
        assert driven["did"]["segments_written"] == 5
        assert driven["did"]["note"] is None
        gate_id = driven["did"]["gate_id"]
        assert gate_id == f"{first_scene}-g01"
        state = stack.state()
        assert state["gates"][0]["options"] == list(_YARD_GATE_OPTIONS)
        assert state["gates"][0]["status"] == "OPEN"
        assert _read(
            app_db,
            "SELECT gate_id, status FROM user_gate WHERE scene_id = ?",
            (first_scene,),
        ) == (gate_id, "OPEN")


def test_the_plan_gate_runs_end_to_end(tmp_path: Path) -> None:
    """The planned will points run the chapter end to end: the
    submission's ruling commits and its continuation lands (the gate
    closes), the drive presses on into the next planned scene and stops
    at ITS gate, and the second submission walks the plan out to its
    exhaustion — the reader decided twice, exactly where the plan said
    the story must stop for them."""

    app_db = tmp_path / "app.db"
    with v3_stack(
        app_db,
        post=_script(
            yard_keys=(1, 2, 3, 4, 5, 6),
            road_keys=(1, 2),
            ch2=_gated_ch2(),
        ),
    ) as stack:
        opened = _to_chapter_two(stack)

        at_gate = stack.advance()[1]
        assert at_gate["did"]["stopped_on"] == "gate"
        yard_gate = at_gate["did"]["gate_id"]

        landed = stack.submit(
            {
                "submission_id": gold.SUBMISSION_ID,
                "intent_text": _MY_INTENT,
            }
        )[1]
        assert landed["ok"] is True, landed["error"]
        # the ruling is not a stop: the same call pressed on through the
        # yard scene's closing segment and into the road scene's gate.
        assert landed["did"]["stopped_on"] == "gate"
        road_gate = landed["did"]["gate_id"]
        assert road_gate != yard_gate
        assert yard_gate in landed["did"]["closed_gates"]
        assert landed["did"]["scene_id"] == opened["roster"][1]["scene_id"]

        exhausted = stack.submit(
            {
                "submission_id": f"{gold.SUBMISSION_ID}-2",
                "intent_text": _MY_INTENT,
            }
        )[1]
        assert exhausted["ok"] is True, exhausted["error"]
        assert exhausted["did"]["stopped_on"] == "plan_exhausted"
        assert road_gate in exhausted["did"]["closed_gates"]

        # the durable face: both gates CLOSED, both rulings committed,
        # and the chapter's passages are the plans' own eight segments.
        assert _read(
            app_db,
            "SELECT status FROM user_gate WHERE gate_id = ?",
            (yard_gate,),
        ) == ("CLOSED",)
        assert _read(
            app_db,
            "SELECT status FROM user_gate WHERE gate_id = ?",
            (road_gate,),
        ) == ("CLOSED",)
        assert _read(
            app_db,
            "SELECT COUNT(*) FROM user_action",
            (),
        ) == (3,)  # ch1's gold gate + the plan's two gates
        state = stack.state()
        assert len(state["passages"]) == 8
        assert state["controls"]["can_settle"] is True
        assert state["controls"]["can_continue"] is False
