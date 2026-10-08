"""lr-2 — the generational presentation: one act at a time
(DEC-OPI-c73dbff3…114, the PLAN v2 first-value slice).

lr-1 made the world turn step by step (the stream shape
``world_delta＊ → world₁ → world_delta＊ → world₂ → … → delta＊ →
final``); the pre-lr-2 page could not bear more than one world frame
(a push after the seal was dropped, the second frame flashed away).
lr-2 re-casts ``startWorldStream`` as a **chain of generations**: each
single-block engine (wr-7R2's drain-then-settle semantics, verbatim)
is one act; a ``world`` frame seals the current act; deltas after a
seal open the next act **below** the sealed block; the serial law —
the next act never types until the previous one has drained and been
replaced by its authoritative render; the transition sentence (「这时，
她收到了你的来信。」 — the reply's seam) once rode the last generation
only, and is retired outright by lr-3T (DEC-OPI-09b3935b…13, the
zero-template law — the seam machinery went with it); ``world_failed``
attaches to the current act's block tail and
later acts keep working; the reply gate widens to "the whole chain has
settled". The refresh-recovery face mirrors the chain: ``/api/history``
regroups a round's revealed notes by reveal stamp (one reveal_all per
chain step) and carries the whole chain additively under
``world_steps`` (``world`` keeps the last frame — single-frame rounds
stay byte-identical). The pin groups:

1. **the serial act order, as source facts** — a generation opened
   after a seal is held (deltas buffer, the rAF loop never schedules
   while held), the hold releases only from the previous generation's
   authoritative-replacement callback, and each act replaces its own
   block in place;
2. **the seam retired, the close still gates (lr-3T)** — the settle
   renders without the transition sentence (no source carries one),
   ``closeChain`` keeps only the chain-closed mark and still fires at
   the reply's first delta and at the final (ahead of the seal), and
   the failure/interrupt posture closes the chain the same way;
3. **the failure note, multi-generation placement** — the note attaches
   to the **current** act's block tail (stop hands the current wrap
   back), the chain stop settles every not-yet-replaced generation,
   and the chain push drops after ``done`` (lr-1's mid-chain refusal
   semantics — the failure never poisons the machinery);
4. **the reply gate, chain-wide** — the chain-level ``settled`` reads
   closed ∧ every generation replaced-or-stopped ∧ none in flight;
   the reply's first-delta callback closes the chain before its first
   push, the final closes it before the seal;
5. **the refresh-recovery chain, E2E over the real stack** — a
   three-step round recovers as three ordered blocks under
   ``world_steps`` (``world`` holding the last), every frame's
   narrations the authoritative chronicle text verbatim (I1, cross
   face); a single-step round carries ``world`` and **no**
   ``world_steps`` key (byte-compat); a mid-chain refusal keeps the
   one landed frame and the round still completes (the reply goes
   out, the history face honest).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.host.test_a1_streaming import (
    A1_TEXT,
    WEBUI,
    _post,
    _sse_frames,
)
from tests.host.test_lr1_run_chain import (
    REPLY,
    STEP_ONE,
    STEP_THREE,
    STEP_TWO,
    ChainProvider,
    _batch,
    _beat,
)
from tests.host.test_w1_web import web_stack
from tests.host.test_wr2_post_turn_wiring import _ro_rows


def _app_source() -> str:
    return (WEBUI / "app.js").read_text(encoding="utf-8")


def _slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


# ---------------------------------------------------------------------------
# 1 — the serial act order (VAL ③'s 幕间串行, as source facts)


def test_the_serial_act_order_is_pinned_in_the_source() -> None:
    """串行事序（一幕一幕讲）：seal 后的增量开**新一代**；新一代在
    「尚有未定版前代」时按住（hold——增量照收、rAF 不排程）；按住只
    由上一代的权威替换落地回调（concluded）释放；每代替换自己的块
    （同位 insertBefore + 流式块摘除）。上一代排空定版前下一代不出
    字——判决点全在源序上。"""

    app = _app_source()
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    # The routing: a push after the current generation's seal opens a
    # new generation (the generational core — the pre-lr-2 engine
    # dropped it).
    push = stream[stream.index("push(piece, index) {") :]
    push = push[: push.index("seal(event) {")]
    assert "if (state.done) return;" in push
    assert "if (state.current === null || state.current.sealed) {" in push
    assert "openGeneration();" in push
    # The hold law: a new generation is held while any prior generation
    # has not been replaced (the deltas keep buffering, nothing types).
    open_gen = stream[stream.index("const openGeneration = () => {") :]
    open_gen = open_gen[: open_gen.index("};")]
    assert (
        "gen.hold(\n"
        "      state.generations.some((prior) => !prior.replaced"
        " && !prior.stopped)\n"
        "    );" in open_gen
    )
    # The hold's mechanical half: a held engine never schedules its
    # own loop; the release restarts it (both proven by the schedule
    # guards in the wr-7 pins — here the release point).
    assert "gen.release = () => {" in stream
    # The release point: only from the authoritative-replacement
    # callback, after the replaced mark and the current-generation
    # clearing — the previous act is on the page as its authoritative
    # block before the next act types a single character. The released
    # generation is the **oldest held one** (creation order = typing
    # order — ``current`` is always the newest open generation; in the
    # fast shape the acts after the next one are already open when an
    # earlier act settles, and releasing by ``current`` would skip the
    # middle act forever — the live probe caught exactly that shape).
    concluded = stream[stream.index("concluded(gen) {") :]
    concluded = concluded[: concluded.index("closeChain() {")]
    assert "gen.replaced = true;" in concluded
    assert "if (state.current === gen) state.current = null;" in concluded
    assert 'state.generations.find((g) => g.held);' in concluded
    assert "if (next) next.release();" in concluded
    # Each act replaces its own block (settleWorld, per generation).
    settle = _slice(app, "const settleWorld = (event) => {", "\n  };\n")
    assert "insertBefore(fresh, gen.wrap)" in settle
    assert "gen.wrap.remove()" in settle


# ---------------------------------------------------------------------------
# 2 — the seam retired, the close still gates (lr-3T's zero-template law)


def test_the_seam_mechanism_is_retired_and_the_close_still_gates() -> None:
    """lr-3T（DEC-OPI-09b3935b…13，呈现散文零模板律）：缝台机构随过渡句
    整体退役——点缝函数、单向缝标记、带参收口在源里零残留，页面上再无
    world-story-then 段与 thenLetter 句；closeChain 只保留收口语义
    （chainClosed 置位，wr-11/lr-2 的 settled 判据零变化），四触点同
    前——回信首增量（先于 typing.push）、final（先于 seal）、失败与
    中断走 stop 内部；缝参退役后停点形与回信形同收（chainClosed 本就
    两形同置）。"""

    app = _app_source()
    # Zero residue: no seam mechanism, no seam paragraph, no seam
    # sentence — anywhere in the page source.
    for gone in (
        "appendSeam",
        "seamWanted",
        "seamDone",
        "withSeam",
        "withTransition",
        "world-story-then",
        "thenLetter",
    ):
        assert gone not in app
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    closer = stream[stream.index("const closeChain = () => {") :]
    closer = closer[: closer.index("return {")]
    # The close keeps exactly one job: the chain-closed mark (the gate's
    # first half). Nothing renders at the touchpoint.
    assert "state.chainClosed = true;" in closer
    assert "createElement" not in closer
    assert "textContent" not in closer
    # The chain stop closes too (failWorld / interrupt arm).
    stop = stream[stream.index("stop() {") :]
    stop = stop[: stop.index("if (gen === null) return null;")]
    assert "closeChain();" in stop
    # The live touchpoints: the reply's first delta closes the chain
    # before the reply's first push; the final closes before the seal
    # (the parked conditional is gone with the seam — both final shapes
    # close identically).
    postturn = app[
        app.index("async function postTurn") :
        app.index("async function postTeachMe")
    ]
    delta_cb = postturn[postturn.index("(chunk) => {") :]
    delta_cb = delta_cb[: delta_cb.index("typing.push(chunk);")]
    assert "worldStream.closeChain();" in delta_cb
    assert "worldStream.closeChain();" in postturn
    first_close = postturn.index("worldStream.closeChain();")
    second_close = postturn.index(
        "worldStream.closeChain();", first_close + 1
    )
    assert second_close < postturn.index("await typing.seal(")


# ---------------------------------------------------------------------------
# 3 — the failure note, multi-generation placement (VAL ④)


def test_the_failure_note_attaches_to_the_current_generation() -> None:
    """失败注多代位：failWorld 的失败注附**当代**块尾（stop 交回当代
    块——链 stop 停循环保留已显）；已 seal 而未定版的在排代交回权威
    定版（wr-7R 姿态逐代成立）；链终后 push 丢弃（lr-1 链中拒收后续
    步语义——失败不毒化代际机构，后代照常）。"""

    app = _app_source()
    fail = _slice(app, "const failWorld = () => {", "\n  };\n")
    assert "const block = worldStream.stop();" in fail
    assert "block.appendChild(note);" in fail
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    # The chain stop: every not-yet-replaced generation stops (the
    # sealed draining ones hand back to their authoritative replace,
    # the held never-typed one keeps nothing), the current block rides
    # back for the failure note.
    stop = stream[stream.index("stop() {") :]
    stop = stop[: stop.index("return gen.wrap;")]
    assert "for (const prior of state.generations) {" in stop
    assert "if (prior !== gen && !prior.replaced) prior.stop();" in stop
    assert "gen.stop();" in stop
    # After the chain's terminal state the pushes are dropped — the
    # machinery survives a mid-chain refusal without half-open acts.
    push = stream[stream.index("push(piece, index) {") :]
    push = push[: push.index("seal(event) {")]
    assert "if (state.done) return;" in push


# ---------------------------------------------------------------------------
# 4 — the reply gate, chain-wide (VAL ③'s 末幕定版后回信首字)


def test_the_reply_gate_waits_for_the_whole_chain() -> None:
    """gate 升级：链级 settled = 链已收口 ∧ 全部代定版 ∧ 无在途代——
    回信等整条链讲完（wr-11 三臂保留：零世界 / done / 中断；判据三
    词原样在 postTurn 的 replyMayType 里）。"""

    app = _app_source()
    stream = _slice(app, "function startWorldStream() {", "\nfunction ")
    settled = stream[stream.index("get settled() {") :]
    settled = settled[: settled.index("get done() {")]
    assert "state.chainClosed &&" in settled
    assert "state.current === null &&" in settled
    assert "state.generations.every((gen) => gen.replaced || gen.stopped)" in settled
    postturn = app[
        app.index("async function postTurn") :
        app.index("async function postTeachMe")
    ]
    predicate = postturn[postturn.index("const replyMayType = () =>") :]
    predicate = predicate[: predicate.index(";") + 1]
    assert "worldStream.wrap === null" in predicate
    assert "worldStream.settled" in predicate
    assert "worldStream.done" in predicate


# ---------------------------------------------------------------------------
# 5 — the refresh-recovery chain, E2E over the real stack (VAL ⑤)


def test_a_three_step_round_recovers_as_three_blocks(tmp_path: Path) -> None:
    """三步轮刷新恢复 = 三块：/api/turn_stream 落一轮三步链 →
    /api/history 该轮带 world_steps 三帧（落库序），world == 末帧；
    每帧叙述 == 该步编年史逐字（I1 跨面——恢复的就是当轮显过的）；
    帧形齐全（ui_language / date_localized / notes 带 fallback 位）。"""

    app_db = tmp_path / "app.db"
    provider = ChainProvider(STEP_ONE, STEP_TWO, STEP_THREE)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        streamed = [f for f in frames if f.get("type") == "world"]
        assert len(streamed) == 3
        status, history = stack.get_json("/api/history?full=1")
        assert status == 200
        framed = [t for t in history["turns"] if "world" in t]
        assert len(framed) == 1
        turn = framed[0]
        steps = turn["world_steps"]
        assert len(steps) == 3
        # ``world`` holds the last frame; the chain rides additively.
        assert turn["world"] == steps[-1]
        # I1, cross face: every recovered frame is the streamed frame's
        # own narration set, verbatim, in landing order.
        for recovered, live in zip(steps, streamed):
            assert [n["narration"] for n in recovered["notes"]] == [
                n["narration"] for n in live["notes"]
            ]
        for frame in steps:
            assert frame["ui_language"] == "zh"
            assert frame["date_localized"]
            assert frame["world_name"]
            for note in frame["notes"]:
                assert note["fallback"] is False


def test_a_single_step_round_stays_keyless_one_block(tmp_path: Path) -> None:
    """单步回归（单代兼容，E2E 半）：单步轮（一步 letter_arrives 即停）
    历史载荷带 world 一帧、**零 world_steps 键**——pre-lr-2 形字节不
    动（可加性键的另一半）。"""

    app_db = tmp_path / "app.db"
    one_step = _batch(
        _beat("letter-arrives", "她拆开了那封等着的信。", 0),
        stop="letter_arrives",
    )
    provider = ChainProvider(one_step)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        assert [f["type"] for f in frames].count("world") == 1
        status, history = stack.get_json("/api/history?full=1")
        assert status == 200
        framed = [t for t in history["turns"] if "world" in t]
        assert len(framed) == 1
        turn = framed[0]
        assert "world_steps" not in turn
        narrations = [
            str(note["narration"]) for note in turn["world"]["notes"]
        ]
        assert narrations == ["她拆开了那封等着的信。"]


def test_a_mid_chain_failure_keeps_one_landed_frame_and_completes(
    tmp_path: Path,
) -> None:
    """链中拒收（后代照常，E2E 半）：step one lands（一步一帧），step
    two 拒收 ⇒ world_failed、编年史零新增——恢复面该轮恰一帧（step
    one 的叙述逐字）、零 world_steps；回信照常落（轮次完整——失败不
    毒化链务）。"""

    app_db = tmp_path / "app.db"
    refused = json.dumps(
        {
            "beats": [
                {
                    "kind": "BAD KIND",
                    "narration": "Refused after the first act.",
                    "days": 0,
                }
            ]
        }
    )
    provider = ChainProvider(STEP_ONE, refused)
    with web_stack(app_db, provider=provider) as stack:
        status, raw = _post(stack.port, "/api/turn_stream", {"text": A1_TEXT})
        assert status == 200
        frames = _sse_frames(raw)
        types = [f["type"] for f in frames]
        assert types.count("world") == 1
        assert "world_failed" in types
        assert types.index("world") < types.index("world_failed")
        assert types[-1] == "final"
        assert frames[-1]["reply"] == REPLY
        status, history = stack.get_json("/api/history?full=1")
        assert status == 200
        framed = [t for t in history["turns"] if "world" in t]
        assert len(framed) == 1
        turn = framed[0]
        assert "world_steps" not in turn
        assert [
            str(note["narration"]) for note in turn["world"]["notes"]
        ] == ["早市在广场上支起来了。"]
        # The refused step wrote nothing; the landed step stays landed.
        assert (
            _ro_rows(app_db, "SELECT COUNT(*) FROM world_event")[0][0] == 1
        )


# ---------------------------------------------------------------------------
# 6 — the history bucket regroup, as source facts


def test_history_buckets_regroup_by_reveal_stamp() -> None:
    """多帧桶形（源级）：一轮内按揭示时刻再分组（lr-1 链每步自己的
    reveal_all 盖一个时刻——一步一帧，帧序 = 时刻序 = world_steps 序；
    同刻并组 = 单步轮/legacy 批一字节不动的单块形）；载荷发射 = world
    持末帧、多帧才带 world_steps；红线继承不动（wr-8 的零 reveal_all
    AST 钉照旧管着本面）。"""

    web = (WEBUI.parent / "web.py").read_text(encoding="utf-8")
    body_start = web.index("def _world_frames_for_window(")
    body = web[body_start : web.index("def _world_payload(", body_start)]
    assert "groups.setdefault(moment, []).append(note)" in body
    assert "for moment in sorted(groups):" in body
    assert "turn_frames.append(" in body
    caller = web[web.index('turn: dict[str, Any] = {') :]
    caller = caller[: caller.index("turns.append(turn)")]
    assert 'turn["world"] = steps[-1]' in caller
    assert "if len(steps) > 1:" in caller
    assert 'turn["world_steps"] = steps' in caller


def test_the_story_block_orders_notes_then_direction_row() -> None:
    """lr-3T 块内序（缝台退役后的诚实空形态）：故事块 = 日期行、叙述段
    （含 fallback 小字）、走向行——再无过渡句位；走向行在场则随块尾
    渲染（wr-10 资产交互原序保留：走向行、回信）。零滚动劫持与
    textContent 纪律照旧。"""

    app = _app_source()
    renderer = app[app.index("function renderWorldStory") :]
    renderer = renderer[: renderer.index("async function loadWorldInbox")]
    date_at = renderer.index("world-story-date")
    notes_at = renderer.index("world-story-note")
    row_at = renderer.index("renderWorldDirectionRow(event.directions)")
    assert date_at < notes_at < row_at
    assert "world-story-then" not in renderer
    assert "window.scrollTo" not in renderer


def test_a_blocking_multi_step_round_rides_world_steps(
    tmp_path: Path,
) -> None:
    """阻塞形多步轮（finalize 臂的服务端半）：无流面 provider 的
    /api/turn 载荷 = world 持末帧 + world_steps 全链 + stop 链尾信号
    ——前端 finalize 臂的 world_steps 多块消费以此为准；历史交错同
    三帧（I1 跨传输）。"""

    from tests.host.test_lr1_run_chain import BlockingChainProvider

    app_db = tmp_path / "app.db"
    provider = BlockingChainProvider(STEP_ONE, STEP_TWO, STEP_THREE)
    with web_stack(app_db, provider=provider) as stack:
        status, payload = stack.post("/api/turn", {"text": A1_TEXT})
        assert status == 200
        steps = payload["world_steps"]
        assert [s["type"] for s in steps] == ["world", "world", "world"]
        assert payload["world"] == steps[-1]
        assert payload["stop"] == "letter_arrives"
        status, history = stack.get_json("/api/history?full=1")
        assert status == 200
        framed = [t for t in history["turns"] if "world" in t]
        assert len(framed) == 1
        recovered = framed[0]["world_steps"]
        assert len(recovered) == 3
        for live, fresh in zip(steps, recovered):
            assert [n["narration"] for n in live["notes"]] == [
                n["narration"] for n in fresh["notes"]
            ]
