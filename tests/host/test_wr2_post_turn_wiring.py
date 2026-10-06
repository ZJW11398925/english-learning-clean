"""WR-2 — the post-turn world letter wiring (the paradigm flip's web
half), served over the production assembly.

The same shape as the W-1/A1 suites: the real ``elc.web.run_web`` over
the real ``open_host`` (the builtin Berrymoor package binds at open),
reached with ``urllib`` over the loopback. The world's step is no
longer the pre-generation engine run — it is the narrator's generated
step, running **after** the turn commits (WR-2, DEC-OPI-5fc42174…49).
The pin groups:

1. **the blocking arm** — ``/api/turn`` runs the letter step inline
   after the payload is built: the beats land in the chronicle
   (``source = world_narrator``), the reveals wait ``PENDING``, the
   reply is untouched, and the narrator's prompt carries **this turn's
   letter text in full** (the wiring's own judgment face);
2. **the streamed arm** — the streamed turn's frames are delta＊ →
   final (no ``world`` frame anywhere — the A2 pre-step is retired),
   and the letter step runs **after** the final frame is out (the
   fire-and-forget job the handler enqueues; the durable rows are its
   receipt), carrying the committed turn's real id (the stash's
   honesty — the run row names its letter);
3. **the retirement, at the source** — the pre-step face, the world
   frame assembly, the additive payload key and the engine-step
   imports are gone from ``web.py``; the generated step is the one
   world face the turn wiring calls;
4. **the read faces stay green** — inbox, log and overview keep their
   shapes over generated notes (the signatures resolve to the world's
   own byline, the story days are the beats' own stamps, and the log
   groups them newest day first);
5. **fail-soft** — a narrator that raises costs the reply nothing:
   the turn answers whole, nothing is written, the sentence goes to
   stderr.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from elc.persona.types import CompiledPrompt, ProviderOutput
from tests.host.test_a1_streaming import (
    A1_TEXT,
    _FakeOpenAI,
    _openai_stack,
    _post,
    _sse_frames,
)
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack

#: The beats JSON the world letter steps answer with (two beats, spans
#: 0 and 2 — the presentation pins' own story days).
_BEATS_OBJ: dict[str, Any] = {
    "beats": [
        {
            "kind": "quiet-morning",
            "narration": "The harbour kept its silence through the morning.",
            "days": 0,
        },
        {
            "kind": "keeper-visitor",
            "narration": "A stranger walked the cliff path to the keeper's door.",
            "days": 2,
        },
    ]
}

#: The beats JSON string (the a2/w13 suites import this constant).
BEATS_TWO = json.dumps(_BEATS_OBJ)


class BeatsProvider:
    """The scripted double for the post-turn wiring: the odd calls (the
    persona round trips) answer the letter's reply, the even calls (the
    world letter steps) answer the beats JSON. No ``call_streaming``
    face — the streamed path runs its blocking shape, so the pins hold
    for both turn faces with one double. The prompts it saw are the
    wiring's own reading instrument."""

    def __init__(
        self,
        *,
        beats_json: str = BEATS_TWO,
        reply_text: str = REPLY,
    ) -> None:
        self._beats = beats_json
        self._reply = reply_text
        self.prompts: list[str] = []

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        if len(self.prompts) % 2 == 1:
            return ProviderOutput(text=self._reply, error=None)
        return ProviderOutput(text=self._beats, error=None)

    @property
    def reply_text(self) -> str:
        return self._reply

    @property
    def narrations(self) -> list[str]:
        return [
            str(beat["narration"]) for beat in _BEATS_OBJ["beats"]
        ]


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows off the serving database through a fresh
    read-only connection (the W-4 ro posture — the worker thread owns
    the writable one)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(ro.execute(sql).fetchall())
    finally:
        ro.close()


def _wait_for_world_rows(
    app_db: Path, sql: str, expected: int, *, timeout: float = 15.0
) -> list[tuple]:
    """Wait for the streamed arm's fire-and-forget world letter job to
    land (the job is enqueued once the final frame is out, so the test
    polls until the durable rows say it ran)."""

    deadline = time.monotonic() + timeout
    rows: list[tuple] = []
    while time.monotonic() < deadline:
        rows = _ro_rows(app_db, sql)
        if len(rows) >= expected:
            return rows
        time.sleep(0.05)
    raise AssertionError(
        f"the world letter job never landed: wanted {expected} rows for"
        f" {sql!r}, saw {len(rows)}"
    )


# ---------------------------------------------------------------------------
# 1 — the blocking arm
# ---------------------------------------------------------------------------


def test_the_blocking_turn_runs_the_world_letter_after_the_reply(
    tmp_path: Path,
) -> None:
    """/api/turn's letter step rides inline after the payload is built:
    the beats land (``world_narrator``), the reveals wait ``PENDING``,
    the reply is whole — and the narrator's prompt carries this turn's
    letter in full (the wiring hands the step the user's own text)."""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        letter = "Please tell the keeper Ada is coming on Thursday."
        status, turn = stack.post("/api/turn", {"text": letter})
        assert status == 200
        assert turn["reply"] == provider.reply_text
        assert "world_step_note" not in turn
        rows = _ro_rows(
            app_db,
            "SELECT source FROM world_event ORDER BY event_id ASC",
        )
        assert [str(row[0]) for row in rows] == [
            "world_narrator",
            "world_narrator",
        ]
        assert _ro_rows(
            app_db,
            "SELECT COUNT(*) FROM world_reveal_item WHERE status = 'PENDING'",
        )[0][0] == 2
        # The second dial was the narrator's — and the letter rode it
        # verbatim (the direction v1: the letter steers the story).
        narrator_prompt = provider.prompts[1]
        assert letter in narrator_prompt


# ---------------------------------------------------------------------------
# 2 — the streamed arm
# ---------------------------------------------------------------------------


def test_the_stream_runs_the_world_letter_after_the_final(
    tmp_path: Path,
) -> None:
    """The streamed turn's frames are exactly one final (the blocking
    shape for a provider without a streaming face), and the letter step
    runs **after** the response is complete — the durable rows are the
    fire-and-forget job's receipt, and the run row names the committed
    turn (the stash's honesty: no anonymous letter)."""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": A1_TEXT}
        )
        assert status == 200
        assert [f["type"] for f in _sse_frames(raw)] == ["final"]
        rows = _wait_for_world_rows(
            app_db, "SELECT trigger_turn_id FROM world_run", 1
        )
        # The stash carried the committed turn's real id.
        assert rows[0][0] is not None
        assert _ro_rows(
            app_db, "SELECT COUNT(*) FROM world_event"
        )[0][0] == 2


def test_the_stream_frame_order_is_deltas_then_final(tmp_path: Path) -> None:
    """The streamed order is delta＊ → final, nothing else — no
    ``world`` frame lands before the first delta even on a world-bound
    stack (the A2 pre-step is retired with the engine step it carried;
    the streaming provider's own narrator dial happens after the final
    and refuses the endpoint's prose honestly, off this stream's
    clock)."""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            frames = _sse_frames(raw)
            others = [
                f for f in frames if f["type"] not in ("delta", "final")
            ]
            assert others == []
            assert frames[0]["type"] == "delta"
            assert frames[-1]["type"] == "final"
            assert [f["type"] for f in frames][:-1] == ["delta"] * len(REPLY)
    finally:
        endpoint.stop()


# ---------------------------------------------------------------------------
# 3 — the retirement, at the source
# ---------------------------------------------------------------------------


def test_the_pre_step_is_retired_at_the_source() -> None:
    """The pre-step's whole apparatus is gone from ``web.py``: no
    ``_world_step_face``, no ``world_step_note`` payload literal, no
    engine-step imports — the generated step is the one world face the
    turn wiring calls."""

    source = (
        (Path(__file__).resolve().parents[2] / "src" / "elc" / "web.py")
        .read_text(encoding="utf-8")
    )
    assert "_world_step_face" not in source
    assert '"world_step_note"' not in source
    assert "skip_world_step" not in source
    assert "TRIGGER_LETTER" not in source
    assert "EngineConfig" not in source
    assert "run_generated_step" in source
    assert "def world_step_for_stream" in source


# ---------------------------------------------------------------------------
# 4 — the read faces stay green over generated notes
# ---------------------------------------------------------------------------


def test_the_read_faces_stay_green_over_generated_notes(
    tmp_path: Path,
) -> None:
    """Inbox and log keep their shapes over the generated notes: the
    signatures resolve to the world's own byline (the narrator signs
    nothing), the story days are the beats' own stamps, the log groups
    them newest day first, and the reading never flips what still waits
    (only the inbox's read is the reveal)."""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        status, _ = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        status, log = stack.get_json("/api/world/log")
        assert status == 200
        # The log never reveals: both notes still wait, unseen.
        assert log["days"] == []
        status, inbox = stack.get_json("/api/world/inbox")
        assert status == 200
        assert inbox["revealed_now"] == 2
        assert [note["narration"] for note in inbox["items"]] == (
            provider.narrations
        )
        assert all(note["actor_name"] == "世界" for note in inbox["items"])
        assert [note["story_date"] for note in inbox["items"]] == [
            "9月14日",
            "9月16日",
        ]
        status, log = stack.get_json("/api/world/log")
        assert status == 200
        days = log["days"]
        assert [day["date_localized"] for day in days] == [
            "9月16日",
            "9月14日",
        ]
        newest, older = days
        assert [item["narration"] for item in newest["items"]] == [
            provider.narrations[1]
        ]
        assert all(item["signature"] is None for item in newest["items"])
        assert [item["narration"] for item in older["items"]] == [
            provider.narrations[0]
        ]


# ---------------------------------------------------------------------------
# 5 — fail-soft
# ---------------------------------------------------------------------------


def test_the_narrator_failure_leaves_the_turn_whole(
    tmp_path: Path,
) -> None:
    """A narrator that raises costs the reply nothing: the turn answers
    whole, nothing is written (no run, no event, no reveal), and the
    failure is the face's own stderr sentence — the page's substance
    never waits on the world's bookkeeping."""

    app_db = tmp_path / "app.db"

    class _BoomOnWorld:
        """The letter's reply works; the world's dial explodes."""

        def __init__(self) -> None:
            self.calls = 0

        def call(self, prompt: CompiledPrompt) -> ProviderOutput:
            self.calls += 1
            if self.calls % 2 == 0:
                raise RuntimeError("the narrator is down")
            return ProviderOutput(text=REPLY, error=None)

    provider = _BoomOnWorld()
    with web_stack(app_db, provider=provider) as stack:  # type: ignore[arg-type]
        status, turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        assert turn["reply"] == REPLY
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_run")[0][0] == 0
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 0
        assert (
            _ro_rows(
                app_db, "SELECT COUNT(*) FROM world_reveal_item"
            )[0][0]
            == 0
        )
