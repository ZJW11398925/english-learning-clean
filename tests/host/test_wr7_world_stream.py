"""wr-7 — the world's narration streams to the page (DEC-OPI-c73dbff3…4)
/ wr-7R — the settle waits for the drain (DEC-OPI-c73dbff3…23).

The user's verdict that closed the handover block: 「事件没有及时以流式
慢慢显现，而是在较长等待后突然全部闪现出来」— wr-6 fixed the *order*
(the world's step runs before the reply is generated); wr-7 fixes the
*time grain*: the narrator's streamed face feeds the incremental
extractor, the page receives ``world_delta`` pieces as they decode, and
a refusal after shown pieces answers the honest ``world_failed`` handle
(渲染先行，持久殿后，拒收不撒谎 — the chronicle still takes the whole
batch or nothing). wr-7R fixes the *settle*: the whole ``world`` frame
no longer stops the typewriter and swaps the block on arrival — it
seals the authoritative remainder into the same pacer and replaces only
after every paragraph has drained (整批到达不再闪现). The pin groups:

1. **the streamed order over the real web stack** — a fake streaming
   provider (``call_streaming`` slicing the beats JSON through an
   escape boundary) answers ``world_delta＊ → world → delta＊ → final``
   in exactly that order, the pieces join to the authoritative
   narrations, and the durable rows land before the final;
2. **the blocking shape** — a provider without the streamed face keeps
   the WR-6 shape byte for byte (zero ``world_delta``, the whole frame,
   the final);
3. **the refusal and fault arms** — pieces shown and the whole frame
   never coming (a strict-parse refusal, a mid-stream provider fault)
   answer one ``world_failed`` frame with the chronicle untouched;
4. **the quiet arm** — ``not-configured`` streams zero pieces, so zero
   world frames of any kind and the reply at once;
5. **the page wiring, as source facts** — the 「世界运转中…」 placeholder
   row (shown at send, retired by the first world_delta/world/delta,
   the finally safety), the world typewriter (an independent buffer at
   the same TYPING_CPS law, index changes open a new paragraph, the
   streaming block invents no date), the wr-7R drain-then-settle (the
   whole frame seals the authoritative remainder in beat-index order,
   the handback fires only when sealed and every paragraph is spent,
   the replace rides the post-drain callback, late pushes after the
   seal are dropped) and the failure note with the three postures kept
   (fail = stop + note, interrupt = stop keeps shown) — textContent
   throughout. lr-2 (DEC-OPI-c73dbff3…114): the wiring reads the
   generational source — every pin above holds per generation inside
   the chain (makeGeneration), and the settle carries the chain-level
   handback (concluded) the serial act order and the last-generation
   seam both ride.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

from elc.persona.types import CompiledPrompt, ProviderOutput
from tests.host.test_a1_streaming import (
    A1_TEXT,
    NARRATOR_MARK,
    WEBUI,
    _post,
    _sse_frames,
)
from tests.host.test_w1_web import REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import (
    BEATS_TWO,
    BeatsProvider,
)

REPO = Path(__file__).resolve().parents[2]

#: The streamed beats' own material: two beats, the first carrying an
#: escaped newline and the second non-ASCII prose (``ensure_ascii`` makes
#: the JSON text carry real ``\uXXXX`` escapes — the extractor decodes
#: them over the real stack). lr-1: the stop signal rides the same
#: answer — the single-step shape (模型一步停) these pins hold.
WR7_BEATS = json.dumps(
    {
        "beats": [
            {
                "kind": "rain-tap",
                "narration": "Rain tapped.\\nIt kept on.",
                "days": 1,
            },
            {
                "kind": "lamp-relit",
                "narration": "The lamp stayed lit — 灯亮着。",
                "days": 0,
            },
        ],
        "stop": {"kind": "letter_arrives"},
    }
)

#: A well-formed shape whose ``days`` breaks the range law — the strict
#: parse refuses it whole while the streamed pieces are already shown.
WR7_REFUSED = json.dumps(
    {
        "beats": [
            {
                "kind": "shown-anyway",
                "narration": "Shown before the verdict.",
                "days": 5,
            }
        ]
    }
)


def _slices(text: str) -> list[str]:
    """Scripted emit slices that cut **through** the first ``\\n`` escape
    (between the backslash and the ``n``) — the hold-back buffer's
    decisive boundary, exercised over the real stack."""

    marker = "\\n"
    if marker in text:
        cut = text.index(marker)
        return [text[: cut + 1], text[cut + 1 : cut + 3], text[cut + 3 :]]
    third = max(1, len(text) // 3)
    return [text[0:third], text[third : 2 * third], text[2 * third :]]


class StreamingBeatsProvider:
    """BeatsProvider 的流式形变体（TASK §7③）：``call`` 照旧整批答，
    ``call_streaming`` 把文本按脚本切片逐段 emit——叙事者 prompt 切在
    转义中缝，回信 prompt 三等分。``stream_error`` 非空时切片照吐、终
    值答故障（诚实部分流）；``emit`` 记录在案作读数仪器。"""

    def __init__(
        self,
        *,
        beats_json: str = WR7_BEATS,
        reply_text: str = REPLY,
        stream_error: str | None = None,
        quiet: bool = False,
    ) -> None:
        self._beats = beats_json
        self._reply = reply_text
        self._stream_error = stream_error
        self._quiet = quiet
        self.emitted: list[str] = []
        self.streamed: list[str] = []

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        text = (
            self._beats if NARRATOR_MARK in prompt.prompt_text else self._reply
        )
        return ProviderOutput(text=text, error=None)

    def call_streaming(
        self, prompt: CompiledPrompt, emit: Callable[[str], None]
    ) -> ProviderOutput:
        self.streamed.append(prompt.prompt_text)
        if self._quiet and NARRATOR_MARK in prompt.prompt_text:
            # The real adapter's prelude refusal: no coordinates, no
            # increments — the world leg's quiet arm, the reply's face
            # untouched (it still streams).
            return ProviderOutput(text=None, error="not-configured")
        text = (
            self._beats if NARRATOR_MARK in prompt.prompt_text else self._reply
        )
        for piece in _slices(text):
            self.emitted.append(piece)
            emit(piece)
        if self._stream_error is not None:
            return ProviderOutput(text=None, error=self._stream_error)
        return ProviderOutput(text=text, error=None)


def _ro_rows(app_db: Path, sql: str) -> list[tuple]:
    """Read committed rows through a fresh read-only connection (the W-4
    ro posture — the worker thread owns the writable one)."""

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(ro.execute(sql).fetchall())
    finally:
        ro.close()


# ---------------------------------------------------------------------------
# 1 — the streamed order over the real web stack
# ---------------------------------------------------------------------------


def test_the_stream_order_is_world_delta_then_world_then_reply(
    tmp_path: Path,
) -> None:
    """VAL ⑤ 恰序：真 web 栈 + fake 流式 provider——**world_delta＊ →
    world → delta＊ → final**；增量按 index 拼接 == 权威 narration
    （含跨转义切割还原与 \\uXXXX 解码）；帧即揭示律不动（beats 落库
    且 PENDING 零残留——生成序不动）。"""

    app_db = tmp_path / "app.db"
    provider = StreamingBeatsProvider()
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        world_pos = types.index("world")
        pieces = frames[:world_pos]
        assert types[0] == "world_delta"
        assert all(f["type"] == "world_delta" for f in pieces)
        # The reply arrives as the scripted three slices (the fake's own
        # cuts), each one a delta, joining to the whole reply.
        assert types[world_pos + 1 : -1] == ["delta"] * 3
        assert types[-1] == "final"
        # The pieces join to the authoritative narrations, per beat —
        # the escape cut mid-\\n and the \\uXXXX decode happened here.
        joined: dict[int, str] = {}
        for frame in pieces:
            joined[frame["index"]] = joined.get(frame["index"], "") + str(
                frame["text"]
            )
        narrations = [
            beat["narration"] for beat in json.loads(WR7_BEATS)["beats"]
        ]
        assert joined == {0: narrations[0], 1: narrations[1]}
        # The whole frame settles with the same authoritative text.
        world = frames[world_pos]
        assert [note["narration"] for note in world["notes"]] == narrations
        # The reply streamed through the proxy, untouched.
        deltas = [f for f in frames if f["type"] == "delta"]
        assert "".join(str(f["text"]) for f in deltas) == REPLY
        # 生成序不动：世界步仍先于回信——final 落地时编年史已在库，
        # 帧即揭示（无 PENDING 残留）。
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 2
        assert (
            _ro_rows(
                app_db,
                "SELECT COUNT(*) FROM world_reveal_item"
                " WHERE status = 'PENDING'",
            )[0][0]
            == 0
        )


def test_the_blocking_shape_keeps_zero_world_delta(tmp_path: Path) -> None:
    """VAL ⑤ 阻塞臂：provider 无流面 ⇒ 零 world_delta 直 world 帧
    （WR-6 现状形字节不变）。"""

    app_db = tmp_path / "app.db"
    provider = BeatsProvider(beats_json=BEATS_TWO)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        assert [f["type"] for f in frames] == ["world", "final"]
        assert frames[0]["notes"][0]["narration"] == provider.narrations[0]


# ---------------------------------------------------------------------------
# 2 — the refusal and fault arms (拒收不撒谎)
# ---------------------------------------------------------------------------


def test_a_refusal_after_shown_pieces_answers_world_failed_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """VAL ⑤ 拒收臂：增量已显示而整批被严格解析拒收 ⇒ world_failed 帧
    + 编年史零写入（SQL 计数钉——事件/揭示/run 全零）。"""

    app_db = tmp_path / "app.db"
    provider = StreamingBeatsProvider(beats_json=WR7_REFUSED)
    assert provider.emitted == []
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert "world" not in types
        failed_pos = types.index("world_failed")
        assert failed_pos > 0
        assert all(t == "world_delta" for t in types[:failed_pos])
        assert types[failed_pos + 1 : -1] == ["delta"] * 3
        assert types[-1] == "final"
        # The shown piece was real — the extractor decoded it before the
        # strict parse refused the batch.
        joined = "".join(
            str(f["text"]) for f in frames[:failed_pos] if f["index"] == 0
        )
        assert "Shown before the verdict." in joined
        # 编年史零写入：整批拒收零部分采纳。
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 0
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_reveal_item")[0][0]
            == 0
        )
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_run")[0][0] == 0


def test_a_stream_fault_after_shown_pieces_answers_world_failed(
    tmp_path: Path,
) -> None:
    """流中途故障（已吐增量后终值答故障词）：world_failed + 零 world
    整帧 + 编年史零写入——已显示的诚实可见。"""

    app_db = tmp_path / "app.db"
    provider = StreamingBeatsProvider(stream_error="http-500")
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert "world" not in types
        assert "world_failed" in types
        assert types[-1] == "final"
        assert _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 0


# ---------------------------------------------------------------------------
# 3 — the quiet arm (zero pieces, zero world frames)
# ---------------------------------------------------------------------------


def test_the_quiet_arm_streams_zero_world_frames(tmp_path: Path) -> None:
    """VAL ⑤ 安静臂：``not-configured``（无坐标先拒，零增量）⇒ 零
    world 帧直入回信流——fail-soft 现状不动。"""

    app_db = tmp_path / "app.db"
    provider = StreamingBeatsProvider(quiet=True)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert "world" not in types
        assert "world_delta" not in types
        assert "world_failed" not in types
        assert types[0] == "delta"
        assert types[-1] == "final"
        # The world leg emitted nothing — every recorded emit is one of
        # the reply's own scripted slices.
        assert provider.emitted == _slices(REPLY)


# ---------------------------------------------------------------------------
# 4 — the page wiring, as source facts (DOM behavior rides the live
#     reviewer's probes; these pins hold the source's own shape)
# ---------------------------------------------------------------------------


def _app_source() -> str:
    return (WEBUI / "app.js").read_text(encoding="utf-8")


def _slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


def test_the_world_running_placeholder_shows_at_send_and_retires() -> None:
    """占位行：发信即现（双语词随 ui_language），首个 world_delta/
    world/delta 到达即让位，finally 安全退役——零帧轮次不留尾巴
    （VAL ⑥；变异 m5：占位行不退役）。"""

    app = _app_source()
    assert 'worldRunning: "世界运转中…"' in app
    assert 'worldRunning: "The world is turning…"' in app
    assert 'addLine("typing", worldInboxText().worldRunning)' in app
    assert 'worldPending.classList.add("world-pending")' in app
    # The retirement: idempotent, and wired to every first-frame arm.
    retire_def = _slice(
        app, "const retireWorldPending = () => {", "\n  };\n"
    )
    assert "worldPending.remove()" in retire_def
    postturn = app[
        app.index("async function postTurn") :
        app.index("async function postTeachMe")
    ]
    assert postturn.count("retireWorldPending()") >= 6
    delta_cb = postturn[postturn.index("(chunk) => {") :]
    delta_cb = delta_cb[: delta_cb.index("typing.push(chunk);")]
    assert "retireWorldPending();" in delta_cb
    world_delta_cb = postturn[postturn.index("(piece, index) => {") :]
    world_delta_cb = world_delta_cb[: world_delta_cb.index("worldStream.push(")]
    assert "retireWorldPending();" in world_delta_cb


def test_the_world_typewriter_is_an_independent_buffer_at_the_same_law() -> None:
    """世界打字机：独立缓冲（paras Map 与回信节奏器各自缓冲），同
    TYPING_CPS 定速律，index 变化开新段；流式块不发明日期（date 只
    属于整帧定版的权威渲染）；文字一律 textContent（VAL ⑥）。lr-2
    代际随迁：缓冲与定速律活在每台单代引擎里（makeGeneration——
    代际链的每一代是一台完整的 wr-7R2 排空定版引擎）。"""

    app = _app_source()
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    assert "new Map()" in stream
    assert "TYPING_CPS" in stream
    assert "requestAnimationFrame" in stream
    assert "gen.order.push(index)" in stream
    # The generational chain: every generation is a full engine of its
    # own (lr-2), the buffer and the pacer law per generation.
    assert "const makeGeneration = () => {" in stream
    # The streaming block invents no date: the pacer neither reads the
    # frame's localized date nor builds the date row — both carriers
    # belong to the authoritative render only (变异 m6：日期行提前发明).
    assert "date_localized" not in stream
    assert "world-story-date" not in stream
    assert "innerHTML" not in stream
    assert "textContent" in stream


def test_the_whole_frame_settles_only_after_the_stream_drains() -> None:
    """定版（wr-7R）：world 整帧不再 stop 不再立即替换——seal 把权威
    余量补进当代打字机缓冲，**排空之后**才权威渲染同位替换流式块
    （日期行/fallback 注记此时才补齐；**过渡句不在此臂**——缝台句属
    链尾末代，closeChain 在回信首增量/final 落定），world_failed = 当
    代块尾人话一行（已显示的那段没记进编年史），三姿态不变（fail =
    stop + 注；中断 = stop 保留已显）（DEC-OPI-c73dbff3…23 + lr-2
    DEC-OPI-c73dbff3…114；变异 m1：settle 退回立即替换——整批到达闪
    现回归 / m3：fail/中断姿态被 seal 语义破坏）。"""

    app = _app_source()
    assert 'worldFailed: "世界的这段没能留住——这一轮没记进编年史。"' in app
    settle = _slice(app, "const settleWorld = (event) => {", "\n  };\n")
    # The whole frame seals the authoritative text into the typewriter:
    # never stop, never an immediate replace (变异 m1 的回归形态).
    assert "worldStream.seal(event)" in settle
    assert "worldStream.stop()" not in settle
    # The replace path is live only AFTER the drain — it rides the
    # post-drain callback: the exact conditional, the same-position
    # insert and the streaming block's removal (变异 m7：打字机不定版
    # ——流式残留与权威渲染并立)。lr-2：替换带链级定版回调（concluded
    # ——串行事序的释放点与末代缝台的判定点）。
    assert ".then((gen) => {" in settle
    assert "renderWorldStory(event, { withTransition: false })" in settle
    assert (
        "if (gen !== null && gen.wrap && gen.wrap.parentNode === messages) {"
        in settle
    )
    assert "insertBefore(fresh, gen.wrap)" in settle
    assert "gen.wrap.remove()" in settle
    assert "worldStream.concluded(gen, fresh)" in settle
    fail = _slice(app, "const failWorld = () => {", "\n  };\n")
    assert "world-story-failed" in fail
    assert "worldInboxText().worldFailed" in fail
    assert "textContent" in fail
    # The fail posture keeps its own stop (seal never rides this path;
    # 变异 m3：failWorld 的 stop 被 seal 语义挤掉)。lr-2：失败注落
    # **当代**块尾（stop 交回当代块——多代位）。
    assert "worldStream.stop()" in fail
    assert "const block = worldStream.stop();" in fail
    # The interrupt posture keeps stop-keeps-shown in the catch arm.
    postturn = app[
        app.index("async function postTurn") :
        app.index("async function postTeachMe")
    ]
    assert "worldStream.stop();" in postturn


def test_the_seal_feeds_the_remainder_and_drops_late_pushes() -> None:
    """seal/settle 语义（wr-7R + wr-7R2，逐代原样）：seal(整帧) 把每段
    权威 narration 的未显余量（按**已显+已缓冲**切——缓冲里未打出的
    增量已被权威覆盖，仅按已显切会把排空期双打全文）以段（beat index）
    为序补进缓冲；push 在 seal 后丢弃（本代内——代际链上 seal 后的增
    量由链开新一代承接）；排空交回只在 sealed 且全段排空时发生（变异
    m2：seal 不补权威余量 / m6：退回仅已显切——双打回归）。lr-2 串行
    律同钉：按住代不排程 rAF（增量照收不出字），释放后才开打。"""

    app = _app_source()
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    assert "gen.seal = (event) => {" in stream
    # wr-7R2 HIGH-1: the remainder is cut by shown PLUS buffered — the
    # pieces sitting in the buffer are already covered by the
    # authoritative text (仅按已显切 = the drained text doubles).
    assert (
        'String(note.narration ?? "").slice(\n'
        "            para.el.textContent.length + para.buffer.length\n"
        "          )" in stream
    )
    assert "para.buffer += rest" in stream
    # Late pushes after the seal are dropped: the authoritative text is
    # in, the stream has nothing more to say (per generation).
    assert "if (gen.done || gen.sealed) return;" in stream
    # The drain hands back to settle only when sealed AND every
    # paragraph is spent — the exact negation of the flash.
    assert "gen.sealed && gen.active >= gen.order.length" in stream
    # The paragraph pointer's law (wr-7R): an empty paragraph is no
    # longer skipped unconditionally — the advance waits for the seal
    # or for a later paragraph holding typed content (the wr-7 defect
    # let a mid-beat gap freeze the rest of that beat's pieces until
    # the settle swapped the whole block in — the flash's amplifier).
    assert "gen.sealed || laterParaHasContent()" in stream
    assert "para.buffer.length === 0 &&" in stream
    # The lr-2 serial law: a held generation never schedules its loop
    # (the deltas keep buffering, nothing types) — both entry points
    # guard the schedule on the hold.
    assert (
        "if (!gen.held && !gen.raf) gen.raf = requestAnimationFrame(step);"
        in stream
    )
    assert stream.count("if (!gen.held && !gen.raf)") == 2


def test_the_seal_never_fabricates_a_stream_block() -> None:
    """零增量臂（wr-7R2 MEDIUM-1，conform-R4）：seal 只对曾有增量到
    达的段补余量——seal 块内零 ensurePara（凭空造段的唯一通道），
    缺段即跳过；零 push 到达时当代不存在（链 seal 交回 null），替换
    条件臂让 renderWorldStory 原样整块落位（wr-6 形，无打字机参与）
    （变异 m7：seal 恢复 ensurePara——零增量被拉进打字机）。"""

    app = _app_source()
    seal_block = app[app.index("gen.seal = (event) => {") : app.index("gen.stop")]
    assert "ensurePara" not in seal_block
    assert "const para = gen.paras.get(index);" in seal_block
    assert "if (!para) return;" in seal_block
    # The zero-increment chain arm: no current generation ⇒ seal hands
    # back null and the settle's whole-block arm stays the wr-6 shape.
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    assert "if (state.current === null) return Promise.resolve(null);" in stream
    settle = _slice(app, "const settleWorld = (event) => {", "\n  };\n")
    assert (
        "if (gen !== null && gen.wrap && gen.wrap.parentNode === messages) {"
        in settle
    )
