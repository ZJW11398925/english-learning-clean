"""wr-11 — the reply holds until the world finishes speaking
(DEC-OPI-c73dbff3…76).

The user's fifth verdict (on record): 「信的发出不代表马上就得回复。目
前，世界事件尚未结束，角色的回信却已经开始输出，还明显表现出来」—
the root cause is the wr-7R R5 parallel ruling (「排空与回信打字机互不
阻塞」; its "the world normally drains first" tradeoff was wrong —
parallel is the norm: a hundred-odd characters at 35cps drain for 3-5s
while the reply's first delta lands in 1-2s). wr-11 serializes the
narrative rhythm, purely on the page (the server five and api.js stay
untouched): the reply pacer's emit loop consults a world-stream gate —
while the streamed world block is in flight (a wrap exists and is
neither settled nor done) the reply emits nothing and builds no line,
deltas keep filling the buffer (nothing is lost), and the moment the
world settles (drain handback; the settleWorld replacement — the
transition sentence landing — rides the microtask ahead of the next
frame) the reply resumes from the buffer at 35cps. Three arms never
gate: zero-world turns (no wrap), world_failed (done), stream
interruption (the A2 posture — stop ends the loop). The pin groups:

1. **the emit-loop verdict** — the gate arm stands inside the step,
   ahead of the emission block it guards, while the zero-word resolve
   (sealed ∧ empty buffer) stays ahead of the gate (finalize is never
   held hostage); the arm emits nothing, builds no line, touches no
   buffer, and resets the typing budget per frame (opening resumes at
   35cps — the held-back whole never bursts);
2. **the predicate and the three open arms** — ``replyMayType`` = no
   wrap ∨ settled ∨ done; the wiring is ``startTypewriter(replyMayType)``;
   the reply's delta callback stays gate-free (the data path never
   meets the gate); the catch keeps both stops;
3. **the opening point** — the world pacer flips ``settled`` exactly at
   the drain-complete handback, before the resolve is handed back; the
   ``settled``/``done`` getters exist; the fail posture keeps its stop;
4. **the data face** — push/seal stay pure carriers (collect through
   the gate, nothing dropped).
"""

from __future__ import annotations

from tests.host.test_a1_streaming import WEBUI


def _app_source() -> str:
    return (WEBUI / "app.js").read_text(encoding="utf-8")


def _slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


def _typewriter_source() -> str:
    app = _app_source()
    typewriter = app[app.index("function startTypewriter") :]
    return typewriter[: typewriter.index("\n}", typewriter.index("return {"))]


def _postturn_slice() -> str:
    app = _app_source()
    return app[
        app.index("async function postTurn") :
        app.index("async function postTeachMe")
    ]


# ---------------------------------------------------------------------------
# 1 — the emit-loop verdict


def test_the_emit_loop_judges_the_gate_every_frame() -> None:
    """判决钉（VAL ③ 前半）：gate 判决在出字循环内——emission 之前；
    零字回信（sealed∧空缓冲）又先于 gate（finalize 不因 gate 卡死）；
    gate 分支零出字零建行零触缓冲、预算随帧归零（开闸 35cps 接续，
    候场不折成爆发）（变异 m1 gate 拆 / m3 缓冲丢字 / m5 预算爆发）。"""

    tw = _typewriter_source()
    assert "function startTypewriter(gate)" in tw
    # Zero-word replies and the drain-finalize resolve stay ahead of the
    # gate: nothing to type is never held hostage by the world's pacer.
    assert tw.index("state.sealed && state.buffer.length === 0") < tw.index(
        "if (gate && !gate()) {"
    )
    # The gate arm itself: hold = no emission, no line, no buffer touch,
    # and the typing budget resets per frame (opening resumes at 35cps,
    # never one burst of the held-back whole).
    arm = tw[tw.index("if (gate && !gate()) {") :]
    arm = arm[: arm.index("\n    }")]
    assert "state.last = ts;" in arm
    assert "requestAnimationFrame(step)" in arm
    assert "return;" in arm
    assert "state.buffer" not in arm
    assert "ensureLine" not in arm
    # The gate stands before the emission block it guards.
    assert tw.index("if (gate && !gate()) {") < tw.index(
        "const budget = Math.floor(((ts - state.last) / 1000) * TYPING_CPS);"
    )


# ---------------------------------------------------------------------------
# 2 — the predicate and the three open arms


def test_the_gate_predicate_and_the_three_open_arms() -> None:
    """判据与三臂（VAL ④）：replyMayType = 无 wrap（零世界轮次）∨
    settled（定版）∨ done（world_failed/中断）——三臂皆开闸；接线
    startTypewriter(replyMayType)；回信 delta 回调零 gate 依赖（数据
    流不动——入缓冲即不丢）；catch 双 stop 在（A2 中断姿态不因 gate
    卡死）（变异 m2 零世界臂误 gate）。"""

    postturn = _postturn_slice()
    predicate = postturn[postturn.index("const replyMayType = () =>") :]
    predicate = predicate[: predicate.index(";") + 1]
    assert "worldStream.wrap === null" in predicate
    assert "worldStream.settled" in predicate
    assert "worldStream.done" in predicate
    assert "typing = startTypewriter(replyMayType)" in postturn
    # The reply's own data path is gate-free: the delta callback feeds
    # the buffer exactly as before (the gate never sees a delta), and
    # the placeholder row still retires on the first frame (wr-7 时序).
    delta_cb = postturn[postturn.index("(chunk) => {") :]
    delta_cb = delta_cb[: delta_cb.index("typing.push(chunk);")]
    assert "retireWorldPending();" in delta_cb
    assert "gate" not in delta_cb
    # The interruption posture keeps both stops — the A2 shape ends the
    # loop regardless of any gate state.
    assert "typing.stop();" in postturn
    assert "worldStream.stop();" in postturn


# ---------------------------------------------------------------------------
# 3 — the placeholder and the stream wiring keep their own timing


def test_the_placeholder_and_stream_wiring_keep_their_own_timing() -> None:
    """占位行与流面接线不因 gate 改动（VAL ⑤ 后半）：「世界运转中…」
    占位行照旧首帧让位（gate 只管回信出字——让位时序不动）；四回调
    原序原形（onDelta/onWorld/onWorldDelta/onWorldFailed）。"""

    postturn = _postturn_slice()
    assert 'addLine("typing", worldInboxText().worldRunning)' in postturn
    # The gate lives only inside the emit loop — the placeholder keeps
    # its own first-frame retirement (the wr-7 timing is untouched).
    world_delta_cb = postturn[postturn.index("(piece, index) => {") :]
    world_delta_cb = world_delta_cb[: world_delta_cb.index("worldStream.push(")]
    assert "retireWorldPending();" in world_delta_cb
    assert "gate" not in world_delta_cb
    # The stream call keeps its four callbacks in their original order.
    stream_call = postturn[postturn.index("fetchTurnStream(") :]
    stream_call = stream_call[: stream_call.index("\n    );")]
    assert stream_call.index("(chunk) => {") < stream_call.index(
        "(event) => settleWorld(event)"
    )
    assert stream_call.index("(event) => settleWorld(event)") < (
        stream_call.index("(piece, index) => {")
    )
    assert stream_call.index("(piece, index) => {") < (
        stream_call.index("() => failWorld()")
    )


# ---------------------------------------------------------------------------
# 4 — the opening point (the world's drain handback)


def test_the_gate_opens_at_the_world_drain_handback() -> None:
    """开闸点（VAL ③ 后半）：世界打字机排空交回处置 settled（先于
    resolve 交回；settleWorld 的 .then 同位替换落在微任务先行——替换
    必先于回信首字）；settled/done 两 getter 在（gate 判据的状态读
    数）；failWorld 的 stop 即 done 即开闸（world_failed 臂）（变异
    m4 settled 不置位——gate 永不开）。lr-2 随迁（DEC-OPI-c73dbff3
    …114）：排空交回活在每台单代引擎里（gen.settled 于 resolve 处置
    位），链级 settled getter = 链已收口 ∧ 全部代定版 ∧ 无在途代——
    回信等整条链讲完（一幕一幕，回信殿后）。"""

    app = _app_source()
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    assert "settled: false," in stream
    # The flag flips exactly at the drain-complete handback — after the
    # sealed-and-all-spent verdict, before the resolve is handed back
    # (per generation: the engine is the wr-7R one, verbatim).
    verdict = "gen.sealed && gen.active >= gen.order.length"
    assert verdict in stream
    settled_at = stream.index("gen.settled = true;")
    assert settled_at > stream.index(verdict)
    assert settled_at < stream.index("const settled = gen.resolve;")
    # The state readouts the reply's predicate consumes — the chain
    # level: closed ∧ every generation replaced-or-stopped ∧ none in
    # flight (the lr-2 gate upgrade: the reply waits for the whole
    # chain, one act at a time).
    assert "get settled() {" in stream
    assert "state.chainClosed &&" in stream
    assert "state.current === null &&" in stream
    assert "gen.replaced || gen.stopped" in stream
    assert "get done() {" in stream
    # world_failed rides stop ⇒ done ⇒ open (the fail posture keeps its
    # own stop — never swallowed by the settle semantics).
    fail = _slice(app, "const failWorld = () => {", "\n  };\n")
    assert "worldStream.stop()" in fail


# ---------------------------------------------------------------------------
# 5 — the data face (collect through the gate)


def test_the_data_path_keeps_collecting_through_the_gate() -> None:
    """数据面（VAL ③「delta 不丢」的构造性半）：push/seal 数据载体
    原样——gate 不触碰任何入口（回信 delta 世界打字期照收，开闸全文
    完整；变异 m3 的另一半）。"""

    tw = _typewriter_source()
    push = tw[tw.index("push(chunk) {") :]
    push = push[: push.index("seal(fullText)")]
    assert "state.buffer += chunk;" in push
    assert "gate" not in push
    seal = tw[tw.index("seal(fullText)") :]
    seal = seal[: seal.index("stop()")]
    assert (
        "fullText.slice(state.shown.length + state.buffer.length)" in seal
    )
