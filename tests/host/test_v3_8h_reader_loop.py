"""V3-8h — the drive loop over the real serving stack and the author
layer's route wiring (TASK-OPI-c0f4d9b4…34 / the opening ruling
``DEC-OPI-c0f4d9b4…32``; the paradigm shift §10.5).

**What this suite proves, stated honestly.** The loop is exercised over
the real ``run_web`` chain (the V3-8e suite's own posture: an injected
transport answering the Gold screenplay — no socket, no real
credential), with the screenplay extended the fixture's own documented
way (its writer arm keys on ``(place, segment_seq)``). The ceiling
exercised here is the **production constant** (12): chapter two's open
scene is scripted for exactly twelve passages, so one plain continue
runs into the reasoned stop on the true arm — no patched constants.

Pinned here:

1. the ceiling stop — one continue writes twelve fresh segments and
   stops with the sentence in ``did.note`` and in the state's ``note``
   (the reasoned stop the polls keep carrying); the next drive clears
   the note at entry (the old explanation is obsolete the moment the
   reader acts again);
2. the mid-drive failure — a scripted gap inside the loop stops the
   drive **where it stands**: the segments already written are durable
   and counted in the answer (「本次已先写下 N 段」), the retry replays
   them from canon (one fresh writing per fresh segment — the failed
   beat is attempted again, the written ones never re-generated);
3. the author layer's route wiring — ``POST /api/v3/next_chapter`` with
   ``{"direction": …}``` rides the real Director prompt (the direction
   quoted, the soft-expectation law in it), a bad body is the 400
   人话, and the written plan stays the only face the direction
   touches;
4. the page half — the direction input inside the controls band (the
   「下一章」 button's own area), the note-first status line, and the
   main UI untouched.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from elc.world import gold
from tests.host.test_v3_8e_reader import (
    WEBUI,
    _count,
    _GoldPost,
    _open_request,
    _post_empty,
    _post_json,
    _read,
    v3_stack,
)

REPO = Path(__file__).resolve().parents[2]

_DIRECTION = "让莉亚主动追查信件"


def _ch2_script(yard_keys: tuple[int, ...]) -> gold.GoldScriptedCompletion:
    """The default screenplay with chapter two's yard scene scripted for
    exactly the given segment numbers (the fixture's own key law)."""

    prose = dict(gold.GOLD_PROSE)
    bodies = {
        1: "The yard is cold; the cart waits.",
        2: "The pack goes up; the gate shuts.",
        3: "The cart rolls out at dawn.",
        4: "The storehouse ledger's last page is copied.",
        5: "The cousin watches from the gate-stone.",
        6: "Mother counts the sacks twice.",
        7: "The axle creaks under the load.",
        8: "Lia bolts the yard gate behind them.",
        9: "The lane down to the ford is muddy.",
        10: "The ford's water is higher than yesterday.",
        11: "The capital road climbs away from the river.",
        12: "By noon the town is a line behind them.",
    }
    for key in yard_keys:
        prose[(gold.PLACE_CH2_YARD, key)] = bodies[key]
    return gold.GoldScriptedCompletion(
        prose=prose,
        adjudications={gold.GOLD_INTENT: gold.GOLD_ADJUDICATION_PAYLOAD},
        blueprints=(
            (gold.CH1, gold.CH2_BLUEPRINT),
            (None, gold.CH1_BLUEPRINT),
        ),
        replan_blueprints={gold.REPLAN_REQUEST_ID: gold.CH1_REPLAN_BLUEPRINT},
        elements={},
    )


def _to_chapter_two(stack: Any) -> dict[str, Any]:
    """The shared approach: ch1 driven to its plan exhaustion, settled,
    and the next chapter planned — the loop law carries each drive."""

    assert stack.start()["ok"] is True
    at_gate = stack.advance()[1]
    assert at_gate["ok"] is True, at_gate["error"]
    assert at_gate["did"]["stopped_on"] == "gate"
    landed = stack.submit(
        {
            "submission_id": gold.SUBMISSION_ID,
            "intent_text": gold.GOLD_INTENT,
        }
    )[1]
    assert landed["ok"] is True, landed["error"]
    assert landed["did"]["stopped_on"] == "plan_exhausted"
    settled = _post_empty(stack.port, "/api/v3/settle")[1]
    assert settled["ok"] is True, settled["error"]
    nexted = _post_empty(stack.port, "/api/v3/next_chapter")[1]
    assert nexted["ok"] is True, nexted["error"]
    return nexted


# ---------------------------------------------------------------------------
# 1. the ceiling stop (the production constant, on the true arm)
# ---------------------------------------------------------------------------


def test_one_drive_presses_through_twelve_segments_and_stops_reasoned(
    tmp_path: Path,
) -> None:
    """One continue runs the open scene's twelve scripted segments and
    stops at the ceiling — the sentence rides ``did.note`` and the
    state's ``note`` (the polls keep it), the tick moved twelve steps,
    and each segment cost exactly one real writing."""

    app_db = tmp_path / "app.db"
    with v3_stack(
        app_db, post=_GoldPost(script=_ch2_script(tuple(range(1, 13))))
    ) as stack:
        opened = _to_chapter_two(stack)
        first_scene = opened["roster"][0]["scene_id"]
        tick_before = opened["world"]["current_tick"]

        driven = stack.advance()[1]
        assert driven["ok"] is True, driven["error"]
        assert driven["did"] == {
            "kind": "drive",
            "stopped_on": "ceiling",
            "note": (
                "本次已连写 12 段（一次驱动最多 12 段）——点「继续」接上。"
            ),
            "scene_id": first_scene,
            "gate_id": None,
            "closed_gates": [],
            "segments_written": 12,
            "passage_ids": [
                f"{first_scene}-p{seq:04d}" for seq in range(1, 13)
            ],
        }
        # the reasoned stop's sentence survives the page's own polling:
        # the state carries it in ``note``.
        state = stack.state()
        assert state["note"] == driven["did"]["note"]
        assert state["world"]["current_tick"] == tick_before + 12
        assert len(state["passages"]) == 12  # the state is the chapter face
        yard = [
            prompt
            for prompt in stack.post.prompts("writer")
            if f"- place: {gold.PLACE_CH2_YARD}" in prompt
        ]
        assert len(yard) == 12
        for seq in range(1, 13):
            assert f"- segment_seq: {seq}" in yard[seq - 1]

        # the next drive clears the stale note at entry (the reader has
        # acted again — the old explanation is obsolete) and answers the
        # honest failure for the unscripted thirteenth segment.
        retry = stack.advance()[1]
        assert retry["ok"] is False
        assert "transport-error" in retry["error"]
        assert stack.state()["note"] is None


# ---------------------------------------------------------------------------
# 2. the mid-drive failure stops where the drive stands
# ---------------------------------------------------------------------------


def test_a_mid_drive_failure_stops_and_the_landed_segments_stand(
    tmp_path: Path,
) -> None:
    """A scripted gap inside the loop (segment seven is missing) stops
    the drive after six written segments: the answer counts them
    (「本次已先写下 6 段，已落库不丢」) and names them; the retry replays
    the six from canon — no re-generation, only the failed beat is
    attempted again — and lands nothing new."""

    app_db = tmp_path / "app.db"
    with v3_stack(
        app_db, post=_GoldPost(script=_ch2_script(tuple(range(1, 7))))
    ) as stack:
        opened = _to_chapter_two(stack)
        first_scene = opened["roster"][0]["scene_id"]
        before = _count(app_db, "narrative_passage")

        driven = stack.advance()[1]
        assert driven["ok"] is False
        assert driven["did"] == {
            "kind": "drive",
            "stopped_on": "failure",
            "note": None,
            "scene_id": None,
            "gate_id": None,
            "closed_gates": [],
            "segments_written": 6,
            "passage_ids": [
                f"{first_scene}-p{seq:04d}" for seq in range(1, 7)
            ],
        }
        assert driven["error"].endswith(
            "（本次已先写下 6 段，已落库不丢——再点一次从当下续跑。）"
        )
        assert _count(app_db, "narrative_passage") == before + 6

        # the retry: the six committed segments replay from canon (one
        # writer call per seq, still exactly one), the failed seventh is
        # attempted again — and nothing new lands.
        writer_before = stack.post.prompts("writer")
        retry = stack.advance()[1]
        assert retry["ok"] is False
        assert _count(app_db, "narrative_passage") == before + 6
        writer_after = stack.post.prompts("writer")
        assert len(writer_after) == len(writer_before) + 1
        assert "- segment_seq: 7" in writer_after[-1]
        for seq in range(1, 7):
            hits = [
                prompt
                for prompt in writer_after
                if f"- place: {gold.PLACE_CH2_YARD}" in prompt
                and f"- segment_seq: {seq}" in prompt
            ]
            assert len(hits) == 1, seq


# ---------------------------------------------------------------------------
# 3. the author layer's route wiring
# ---------------------------------------------------------------------------


def test_the_direction_rides_the_route_and_the_real_director_prompt(
    tmp_path: Path,
) -> None:
    """``POST /api/v3/next_chapter`` with ``{"direction": …}`` plans the
    next chapter through the real Director provider, and the recorded
    draft prompt quotes the direction beside the soft-expectation law —
    the author layer touching the plan face only. A malformed body is
    the route's own 400 人话."""

    app_db = tmp_path / "app.db"
    with v3_stack(app_db) as stack:
        assert stack.start()["ok"] is True
        assert stack.advance()[1]["ok"] is True
        assert stack.submit(
            {
                "submission_id": gold.SUBMISSION_ID,
                "intent_text": gold.GOLD_INTENT,
            }
        )[1]["ok"] is True
        assert _post_empty(stack.port, "/api/v3/settle")[1]["ok"] is True

        status, payload = _post_json(
            stack.port, "/api/v3/next_chapter", {"direction": _DIRECTION}
        )
        assert status == 200
        assert payload["ok"] is True, payload["error"]
        assert payload["chapter"]["chapter_index"] == 2
        drafts = [
            prompt
            for prompt in stack.post.prompts("director")
            if "The replan's own faces:" not in prompt
        ]
        assert len(drafts) == 2  # ch1's plan + ch2's directed plan
        assert _DIRECTION in drafts[1]
        assert "author-layer" in drafts[1]
        assert "never as a postcondition" in drafts[1]
        # the direction touched the plan face only: no canon row of its
        # own — the chapter's passages are still empty.
        assert payload["passages"] == []

        # a malformed body is the fail-closed 400 (the human sentence).
        request = urllib.request.Request(
            f"http://127.0.0.1:{stack.port}/api/v3/next_chapter",
            data=json.dumps({"direction": 7}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        status, body = _open_request(request)
        assert status == 400
        assert "direction" in body["error"]


# ---------------------------------------------------------------------------
# 4. the page half
# ---------------------------------------------------------------------------


def test_the_page_carries_the_author_layer_and_the_note_face() -> None:
    """reader.html: the direction input inside the controls band (the
    「下一章」 button's own area) with its full-sentence placeholder;
    reader.js: the note-first status line, the direction carried only
    when non-empty, and the box cleared on success; reader.css: the
    row's own layout class. The main UI files carry none of it."""

    page = (WEBUI / "reader.html").read_text(encoding="utf-8")
    assert 'id="reader-direction"' in page
    assert "给下一章一个方向（可留空=让世界自行发展）" in page
    assert "下一章方向" in page
    assert 'class="field reader-author"' in page
    # same band as the 下一章 button: the input sits after it, inside
    # the controls section.
    assert page.index('id="reader-next"') < page.index('id="reader-direction"')
    assert page.index('id="reader-direction"') < page.index(
        "</section>", page.index('id="reader-direction"')
    )

    script = (WEBUI / "reader.js").read_text(encoding="utf-8")
    assert "payload.note ||" in script
    assert "reader-direction" in script
    assert "direction ? { direction } : undefined" in script
    assert "http://" not in script and "https://" not in script

    styles = (WEBUI / "reader.css").read_text(encoding="utf-8")
    assert ".reader-author" in styles
    assert "http://" not in styles and "https://" not in styles

    index = (WEBUI / "index.html").read_text(encoding="utf-8")
    app_js = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "reader-direction" not in index
    assert "reader-direction" not in app_js
    assert "下一章方向" not in index and "下一章方向" not in app_js


def test_the_state_note_reads_from_the_durable_seat(tmp_path: Path) -> None:
    """The note's seat is the host's generic settings table: the drive
    writes it, the off-queue poll reads it (the same derivation the
    drive answer used), and no narrative table carries it."""

    from elc.narrative_web import V3_DRIVE_NOTE_KEY, narrative_state_ro

    app_db = tmp_path / "app.db"
    with v3_stack(
        app_db, post=_GoldPost(script=_ch2_script(tuple(range(1, 13))))
    ) as stack:
        _to_chapter_two(stack)
        driven = stack.advance()[1]
        assert driven["did"]["stopped_on"] == "ceiling"
        # the poll's own short read-only connection answers the note.
        polled = narrative_state_ro(str(app_db))
        assert polled["note"] == driven["did"]["note"]
        assert _read(
            app_db,
            "SELECT value FROM app_setting WHERE key = ?",
            (V3_DRIVE_NOTE_KEY,),
        ) == (driven["did"]["note"],)
