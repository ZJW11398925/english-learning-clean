"""WR-2 — the world letter wiring (the paradigm flip's web half; WR-6
recut to world-first), served over the production assembly.

The same shape as the W-1/A1 suites: the real ``elc.web.run_web`` over
the real ``open_host`` (the builtin Berrymoor package binds at open),
reached with ``urllib`` over the loopback. WR-6 (DEC-OPI-8a4f980b…15):
the world's step runs **before the reply is generated** — the narrator
narrates first, her reply arrives second (spec §4.2's own order). The
pin groups:

1. **the blocking arm** — ``/api/turn`` answers the world frame under
   its own ``world`` key (rendered before the reply line): the beats
   land in the chronicle (``source = world_narrator``) and arrive
   **already revealed** (the frame was the look), the reply is
   untouched, and the narrator's prompt carries **no letter at all**
   (WR-4's judgment face, DEC-…58: the turn is the mechanical wind-up;
   the world narrates its own life);
2. **the streamed arm** — the streamed turn's frames are **world →
   final** on a provider without the streaming face (and world →
   delta＊ → final with one — see the a1/a2 suites): the frame rides
   the stream before the reply's first delta, the beats are revealed
   with it, and the step runs under the count-derived id arm (the
   turn is not yet committed — the docstring's honest no-replay
   protection);
3. **the retirement, at the source** — the post-step face, the stash,
   the additive payload key of the old paradigm and the engine-step
   imports are gone from ``web.py``; the world-first frame face
   (``_world_step_frame``) is the one world face the turn wiring
   calls;
4. **the read faces stay green** — inbox, log and overview keep their
   shapes over generated notes (the signatures resolve to the world's
   own byline, the story days are the beats' own stamps, and the log
   groups them newest day first);
5. **fail-soft** — a narrator that fails costs the reply nothing:
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
#: 0 and 2 — the presentation pins' own story days). lr-1
#: (DEC-OPI-c73dbff3…95): the answer carries the narrator's own stop
#: signal — ``letter_arrives`` — so the single-step shape (模型一步停)
#: is the compatibility shape these pins hold: the chain stops after
#: one landed step, byte for byte the pre-lr-1 behavior.
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
    ],
    "stop": {"kind": "letter_arrives"},
}

#: The beats JSON string (the a2/w13 suites import this constant).
BEATS_TWO = json.dumps(_BEATS_OBJ)


#: WR-6 世界先行：叙事者拨号的判别标记（prompt 内容级——比奇偶更稳，
#: 事后步被 patch 掉时回信是唯一拨号，奇偶会错位）。
NARRATOR_MARK = "You are the narrator of a small fictional world"


class BeatsProvider:
    """The scripted double for the world-first wiring (WR-6): a call
    whose prompt carries the narrator's opening line answers the beats
    JSON (the world's pre-reply narration), every other call answers
    the letter's reply. No ``call_streaming`` face — the streamed path
    runs its blocking shape, so the pins hold for both turn faces with
    one double. The prompts it saw are the wiring's own reading
    instrument."""

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
        if NARRATOR_MARK in prompt.prompt_text:
            return ProviderOutput(text=self._beats, error=None)
        return ProviderOutput(text=self._reply, error=None)

    @property
    def reply_text(self) -> str:
        return self._reply

    @property
    def beats_text(self) -> str:
        return self._beats

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
    """Wait for the world-first step's durable rows to be visible to a
    fresh read-only connection (the step runs before the reply on the
    work queue, so by the time the turn answers they are already
    committed — the poll is SQLite's cross-connection visibility
    handshake, kept from the post-step era because it costs
    nothing)."""

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


def test_the_blocking_turn_runs_the_world_before_the_reply(
    tmp_path: Path,
) -> None:
    """WR-6（DEC-OPI-8a4f980b…13）：世界步先于回信生成——阻塞载荷带
    ``world`` 键（世界块数据），beats 已落库并**当场揭示**（帧即看），
    回信在后；WR-4：叙事者的 prompt 零信文（世界自主，不回应通信）。"""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        letter = "Please tell the keeper Ada is coming on Thursday."
        status, turn = stack.post("/api/turn", {"text": letter})
        assert status == 200
        assert turn["reply"] == provider.reply_text
        assert "world_step_note" not in turn
        # The world-first frame rides the payload (rendered before the
        # reply line on the page), narrations verbatim, no fallback bit.
        assert turn["world"]["notes"][0]["fallback"] is False
        assert (
            turn["world"]["notes"][0]["narration"] in provider.beats_text
        )
        rows = _ro_rows(
            app_db,
            "SELECT source FROM world_event ORDER BY event_id ASC",
        )
        assert [str(row[0]) for row in rows] == [
            "world_narrator",
            "world_narrator",
        ]
        # WR-6: the frame was the look — the beats arrive already revealed.
        assert _ro_rows(
            app_db, "SELECT COUNT(*) FROM world_reveal_item"
            " WHERE status = 'PENDING'"
        )[0][0] == 0
        # WR-4（DEC-…58）：信永不进入世界层——第一次拨号（叙事者的，
        # WR-6 起在最前）的 prompt 零信文（负控），且带世界自主指令
        # （正控）。信只属于笔友层（回信面），发条只是机械触发。
        narrator_prompt = provider.prompts[0]
        assert letter not in narrator_prompt
        assert "It does not react to any correspondence" in narrator_prompt


def test_the_narrator_language_follows_the_interface_setting(
    tmp_path: Path,
) -> None:
    """WR-2 处置（评审 LOW-2/LOW-3，变异 m10 的钉缺口）；WR-6 随迁
    （叙事拨号升至第一次）：ui_language 的端到端缝——设置页切 en 后，
    世界步的 narrator prompt 带英文叙述指令。"""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        status, _ = stack.post(
            "/api/settings/ui_language", {"ui_language": "en"}
        )
        assert status == 200
        status, _ = stack.post("/api/turn", {"text": "Any letter."})
        assert status == 200
        narrator_prompt = provider.prompts[0]
        assert "The narration is written in English." in narrator_prompt
        assert "Chinese (中文)" not in narrator_prompt


# ---------------------------------------------------------------------------
# 2 — the streamed arm
# ---------------------------------------------------------------------------


def test_the_stream_runs_the_world_before_the_reply(
    tmp_path: Path,
) -> None:
    """WR-6：世界步先于回信——流式面（无流形 provider 走阻塞形）的第
    一帧是 ``world`` 帧（世界块数据），final 随后；beats 当场揭示（帧
    即看），run 行由计数派生 id 落库（步先于 commit——WR-2 的 turn-id
    派生需要已提交的 turn，docstring 自认无重放保护的诚实臂）。"""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(
            stack.port, "/api/turn_stream", {"text": A1_TEXT}
        )
        assert status == 200
        frames = _sse_frames(raw)
        # The world frame lands first — before the (here absent) deltas
        # and the final: the world narrates, her reply arrives second.
        assert [f["type"] for f in frames] == ["world", "final"]
        assert frames[0]["notes"][0]["narration"] == provider.narrations[0]
        assert _ro_rows(
            app_db, "SELECT COUNT(*) FROM world_event"
        )[0][0] == 2
        # The frame was the look: nothing waits behind it.
        assert _ro_rows(
            app_db, "SELECT COUNT(*) FROM world_reveal_item"
            " WHERE status = 'PENDING'"
        )[0][0] == 0


def test_the_stream_frame_order_is_world_then_deltas_then_final(
    tmp_path: Path,
) -> None:
    """WR-6：流式帧序世界半场先于回信（世界运转在前，她的回信是运转
    的落点——spec §4.2 的正典顺序，用户的判词：信不得先于世界事件显
    示）；wr-7：世界半场自身也流式化——恰序 **world_delta＊ → world →
    delta＊ → final**。"""

    endpoint = _FakeOpenAI()
    endpoint.start()
    try:
        with _openai_stack(tmp_path / "app.db", endpoint) as stack:
            status, raw = _post(
                stack.port, "/api/turn_stream", {"text": A1_TEXT}
            )
            assert status == 200
            frames = _sse_frames(raw)
            types = [f["type"] for f in frames]
            world_pos = types.index("world")
            assert types[0] == "world_delta"
            assert all(t == "world_delta" for t in types[:world_pos])
            assert types[world_pos + 1] == "delta"
            assert types[-1] == "final"
            assert types[world_pos + 1 : -1] == ["delta"] * len(REPLY)
    finally:
        endpoint.stop()


# ---------------------------------------------------------------------------
# 3 — the retirement, at the source (WR-6 recut)
# ---------------------------------------------------------------------------


def test_the_post_step_is_retired_at_the_source() -> None:
    """WR-6：事后步的整套机具退役——无 ``world_step_for_stream``、无
    ``_stream_world_turn`` stash、无 handler 的 fire-and-forget 入队；
    世界面是唯一的 ``_world_step_frame``（回信之前的先行步）。旧
    A2 前置步的退役钉（WR-2 时代）随 WR-6 翻转——先行步回来了，但
    走的是生成面，不是引擎步。"""

    source = (
        (Path(__file__).resolve().parents[2] / "src" / "elc" / "web.py")
        .read_text(encoding="utf-8")
    )
    assert "def world_step_for_stream" not in source
    assert "_stream_world_turn" not in source
    assert '"world_step_note"' not in source
    assert "skip_world_step" not in source
    assert "TRIGGER_LETTER" not in source
    assert "EngineConfig" not in source
    assert "def _world_step_frame" in source
    assert "run_generated_step" in source


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
        # WR-6: the turn's own frame already revealed both notes — the
        # log (which never reveals) shows them whole; a fresh inbox read
        # flips nothing (revealed_now == 0).
        status, inbox = stack.get_json("/api/world/inbox")
        assert status == 200
        assert inbox["revealed_now"] == 0
        assert [note["narration"] for note in inbox["items"]] == (
            provider.narrations
        )
        assert all(note["actor_name"] == "世界" for note in inbox["items"])
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
        """The letter's reply works; the world's dial explodes (WR-6:
        the world's dial is the first — content-judged, so the reply
        dial never trips the raise)."""

        def __init__(self) -> None:
            self.calls = 0

        def call(self, prompt: CompiledPrompt) -> ProviderOutput:
            self.calls += 1
            if NARRATOR_MARK in prompt.prompt_text:
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
