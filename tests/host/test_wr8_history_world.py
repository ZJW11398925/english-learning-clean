"""WR-8 — the refresh-recovery interleave (DEC-OPI-c73dbff3…34).

The user's third report: 「只要一刷新页面，世界事件就会完全丢失，不再
显示」— the probe-proven two-sided hole: wr-6's frame-as-reveal made
the load arm's ``revealed_now`` read permanently zero for the current
turn, and ``/api/history`` never carried world data at all, so a reload
lost every story block. The fix is server-side interleave (the history
face carries each turn's revealed world events in the weave-in
position) plus a fixed load order (inbox first — the reveal trigger —
history second) and the tail top-up arm's retirement. The pin groups:

1. **the frame rides the history payload** — a real web stack, one
   letter, one world step: the streamed-era narration comes back inside
   the turn's ``world`` frame, verbatim (I1: what was shown is what the
   authority holds), with the frame's own shape (ui_language,
   date_localized, notes with the fallback bit);
2. **the weave-in positions** — two turns keep their own frames (the
   real moment buckets); the wr-2-era shape (an event revealed between
   two turns) lands on the later turn — before its letter, the true
   chronological spot; an event revealed after the last turn attaches
   to the last turn (the honest tail approximation); the conversation's
   first letter keeps its frame (nothing fell out of the window);
3. **the window's lower edge** — past a real lower edge an event
   belonging to an unserved turn stays out; a boundary turn's own step
   events still ride the first served frame; beyond 50 turns the
   sliding window holds and ``?full=1`` recovers the early frames;
4. **the red line** — the history faces never flip a reveal (AST over
   the three wr-8 faces) and never touch a ``PENDING`` row (behavior:
   the store state is identical before and after a history read); the
   leftover reaches the page only through the inbox read (the load
   order's first half) and then — once — through the interleave;
5. **the frontend order** — the load chain reads the inbox *before*
   history; the tail top-up arm (``revealed_now`` render) is retired;
   history frames render in the same shape as the live turn (transition
   sentence included, no typewriter) before the turn's own letter;
6. **the worldless history** — a conversation with no world events
   answers exactly the pre-wr-8 shape (no ``world`` key anywhere).
"""

from __future__ import annotations

import ast
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elc.persona.types import CompiledPrompt, ProviderOutput
from tests.host.test_w1_web import REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import (
    NARRATOR_MARK,
    BeatsProvider,
    _ro_rows,
)

WEBUI = Path(__file__).resolve().parents[2] / "src" / "elc" / "webui"

_STEP1 = json.dumps(
    {
        "beats": [
            {
                "kind": "fog-returns",
                "narration": "雾又漫上码头，镇子把它当作日常。",
                "days": 1,
            },
            {
                "kind": "tide-turns",
                "narration": "潮水在午后转向，滩涂重新露了出来。",
                "days": 0,
            },
        ],
        # lr-1：单步即停形（每轮信模型一步 letter_arrives——链一步出，
        # 多轮交错行为与 pre-lr-1 相同）。
        "stop": {"kind": "letter_arrives"},
    },
    ensure_ascii=False,
)

_STEP2 = json.dumps(
    {
        "beats": [
            {
                "kind": "market-day",
                "narration": "集市在广场上支起来了，鱼车天不亮就出了摊。",
                "days": 2,
            }
        ],
        "stop": {"kind": "letter_arrives"},
    },
    ensure_ascii=False,
)

_STEP3 = json.dumps(
    {
        "beats": [
            {
                "kind": "night-watch",
                "narration": "守夜人在灯塔上换了一班，灯芯剪得极短。",
                "days": 1,
            }
        ],
        "stop": {"kind": "letter_arrives"},
    },
    ensure_ascii=False,
)


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


class TwoStepProvider:
    """The world-first double with a distinct batch per world step (the
    content-discriminated dial — NARRATOR_MARK — beats parity never
    enters it): the first narration dial answers step one's beats, the
    second answers step two's, later ones repeat the third. The letter
    itself always gets the plain reply."""

    def __init__(self) -> None:
        self._narrations = 0

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        if NARRATOR_MARK in prompt.prompt_text:
            self._narrations += 1
            if self._narrations == 1:
                beats = _STEP1
            elif self._narrations == 2:
                beats = _STEP2
            else:
                beats = _STEP3
            return ProviderOutput(text=beats, error=None)
        return ProviderOutput(text=REPLY, error=None)


class QuietWorldProvider:
    """The silent world leg (the wr-7 quiet idiom): the narrator's dial
    answers ``not-configured`` — the orchestrator's quiet arm — while
    the letter's dial answers the plain reply. Fifty-one turns' worth of
    world steps that write nothing."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        if NARRATOR_MARK in prompt.prompt_text:
            return ProviderOutput(text=None, error="not-configured")
        return ProviderOutput(text=REPLY, error=None)


class MuteProvider:
    """The pre-world double (wr-3's QuietProvider shape): every dial
    answers the plain reply, so the narrator's strict parse refuses and
    no world row is ever written."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        return ProviderOutput(text=REPLY, error=None)


def _frame_narrations(turn: dict[str, Any]) -> list[str]:
    # lr-2 multi-frame shape (DEC-OPI-c73dbff3…114): the round's whole
    # chain — world_steps (one frame per landed step) when present, else
    # the single world frame; narrations concatenate in frame order.
    steps = turn.get("world_steps")
    if not steps:
        frame = turn.get("world")
        if frame is None:
            return []
        steps = [frame]
    return [
        str(note["narration"])
        for frame in steps
        for note in frame["notes"]
    ]


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    narration: str,
    created_at: str,
    revealed_at: str | None,
) -> None:
    """One hand-written chronicle row plus its reveal queue row (the
    wr-3 injection posture — a direct write through a side connection,
    the store's own column order). ``revealed_at=None`` leaves the item
    PENDING; a stamp makes it REVEALED with that real moment."""

    world_id = conn.execute(
        "SELECT world_id FROM world_conversation LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO world_event (event_id, world_id, kind, narration,"
        " effects, occurred_at, source)"
        " VALUES (?, ?, 'keeper-visitor', ?, '[]', '2026-06-01',"
        " 'world_narrator')",
        (event_id, world_id, narration),
    )
    conn.execute(
        "INSERT INTO world_reveal_item (item_id, world_id,"
        " source_event_id, actor_id, status, revealed_at, created_at)"
        " VALUES (?, ?, ?, NULL, ?, ?, ?)",
        (
            f"{event_id}:reveal",
            world_id,
            event_id,
            "REVEALED" if revealed_at is not None else "PENDING",
            revealed_at,
            created_at,
        ),
    )


# ---------------------------------------------------------------------------
# 1 — the frame rides the history payload (the refresh-recovery verdict)


def test_the_frame_rides_the_history_payload(tmp_path: Path) -> None:
    """VAL ③ 判决钉：寄信 → 世界步落库（流内已显）→ 模拟刷新读
    /api/history → 该轮载荷带 world 帧，叙述逐字 == 阻塞响应 world 键
    （I1：已显 == 权威），帧形齐全（ui_language / date_localized /
    notes 带 fallback 位）；其余轮不带帧。"""

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db, provider=BeatsProvider(beats_json=_STEP1)
    ) as stack:
        status, payload = stack.post("/api/turn", {"text": "第一封信。"})
        assert status == 200
        shown = [str(n["narration"]) for n in payload["world"]["notes"]]
        assert shown == [
            "雾又漫上码头，镇子把它当作日常。",
            "潮水在午后转向，滩涂重新露了出来。",
        ]

        status, history = stack.get_json("/api/history")
        assert status == 200
        framed = [
            (index, turn)
            for index, turn in enumerate(history["turns"])
            if "world" in turn
        ]
        assert len(framed) == 1
        index, turn = framed[0]
        assert index == len(history["turns"]) - 1  # 本轮（唯一一轮）
        frame = turn["world"]
        # I1: the history frame is the authority — what the live turn
        # showed is what the refresh recovers, verbatim.
        assert _frame_narrations(turn) == shown
        assert frame["ui_language"] == "zh"
        assert frame["date_localized"]  # a story day line, localized
        assert frame["world_name"]
        for note in frame["notes"]:
            assert note["fallback"] is False


def test_the_first_letter_keeps_its_frame(tmp_path: Path) -> None:
    """首信位（种子→刷新场景）：窗口覆盖全部转录时，首轮自身的世界步
    事件挂首轮（下沿为空——没有更早的轮可以把事件藏进去）。?limit=1
    同答。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=BeatsProvider(beats_json=_STEP1)) as stack:
        status, _ = stack.post("/api/turn", {"text": "第一封信。"})
        assert status == 200
        for query in ("/api/history", "/api/history?limit=1"):
            status, history = stack.get_json(query)
            assert status == 200
            assert len(history["turns"]) == 1
            narrations = _frame_narrations(history["turns"][0])
            assert "雾又漫上码头，镇子把它当作日常。" in narrations


# ---------------------------------------------------------------------------
# 2 — the weave-in positions


def test_each_turn_keeps_its_own_frame(tmp_path: Path) -> None:
    """VAL ④ 交错位：三轮各自的世界步事件挂各自轮（真实时刻分桶），
    叙述互不串轮——三轮是判别形（两轮时「全挂末轮」变异与正确桶恰好
    重合，三轮才分得开）。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=TwoStepProvider()) as stack:
        for text in ("第一封信。", "第二封信。", "第三封信。"):
            status, _ = stack.post("/api/turn", {"text": text})
            assert status == 200
        status, history = stack.get_json("/api/history")
        assert status == 200
        first, second, third = history["turns"]
        assert _frame_narrations(first) == [
            "雾又漫上码头，镇子把它当作日常。",
            "潮水在午后转向，滩涂重新露了出来。",
        ]
        assert _frame_narrations(second) == [
            "集市在广场上支起来了，鱼车天不亮就出了摊。"
        ]
        assert _frame_narrations(third) == [
            "守夜人在灯塔上换了一班，灯芯剪得极短。"
        ]


def test_legacy_and_tail_reveals_lands_honestly(tmp_path: Path) -> None:
    """VAL ④ 诚实近似位：wr-2 形态（事件在两轮之间被揭示——当年回信
    后生成、下次开页才揭示）挂后一轮（其真实时序位：上一轮回信之后、
    这轮用户信之前）；晚于末轮的事件挂末轮（裁决 R1 的尾部近似族）。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=TwoStepProvider()) as stack:
        stack.post("/api/turn", {"text": "第一封信。"})
        # the wr-2 shape's reveal moment: after turn one, before turn two
        between = datetime.now(tz=UTC).isoformat()
        stack.post("/api/turn", {"text": "第二封信。"})
        conn = sqlite3.connect(app_db)
        conn.execute("PRAGMA foreign_keys = ON")
        _insert_event(
            conn,
            event_id="legacy-mid",
            narration="旧年的一页：灯塔的油在黄昏前添满了。",
            created_at="2025-09-16",
            revealed_at=between,
        )
        _insert_event(
            conn,
            event_id="tail-note",
            narration="末尾的一笔：渡船的汽笛在雾里拖长。",
            created_at="2025-09-18",
            revealed_at="2099-01-01T00:00:00+00:00",
        )
        conn.commit()
        conn.close()
        status, history = stack.get_json("/api/history")
        assert status == 200
        first, second = history["turns"]
        assert "旧年的一页：灯塔的油在黄昏前添满了。" in _frame_narrations(second)
        assert "旧年的一页：灯塔的油在黄昏前添满了。" not in _frame_narrations(first)
        # the tail approximation: the last turn carries it
        assert "末尾的一笔：渡船的汽笛在雾里拖长。" in _frame_narrations(second)
        # the frame's notes keep the story order (created_at, item_id)
        notes = _frame_narrations(second)
        assert notes.index("旧年的一页：灯塔的油在黄昏前添满了。") < notes.index(
            "集市在广场上支起来了，鱼车天不亮就出了摊。"
        )


# ---------------------------------------------------------------------------
# 3 — the window's lower edge


def test_an_event_revealed_exactly_at_a_turn_moment_rides_that_turn(
    tmp_path: Path,
) -> None:
    """处置刀（评审 LOW-1 钉缺口闭合）：bisect 边界的确定性——事件
    revealed_at **恰等于**某轮 turn 的提交时刻时挂该轮（交错区间
    (前轮, 本轮] 的闭上沿，docstring 声明与实现同一；评审 m7b
    NOT-RED 探针收编——bisect_right 形态会把等值事件挪到下一轮）。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=TwoStepProvider()) as stack:
        for text in ("第一封信。", "第二封信。", "第三封信。"):
            assert stack.post("/api/turn", {"text": text})[0] == 200
        conn = sqlite3.connect(app_db)
        moments = [
            row[0]
            for row in conn.execute(
                "SELECT created_at FROM user_turn ORDER BY rowid"
            ).fetchall()
        ]
        assert len(moments) == 3 and len(set(moments)) == 3
        _insert_event(
            conn,
            event_id="probe-eq",
            narration="边界的一行：正午的钟声恰好停在此刻。",
            created_at="2026-06-03",
            revealed_at=moments[1],  # exactly turn two's commit moment
        )
        conn.commit()
        conn.close()
        status, history = stack.get_json("/api/history?full=1")
        assert status == 200
        first, second, third = history["turns"]
        narrations = [_frame_narrations(t) for t in (first, second, third)]
        assert "边界的一行：正午的钟声恰好停在此刻。" in narrations[1]
        assert "边界的一行：正午的钟声恰好停在此刻。" not in narrations[0]
        assert "边界的一行：正午的钟声恰好停在此刻。" not in narrations[2]


def test_events_before_a_real_lower_edge_stay_outside(tmp_path: Path) -> None:
    """VAL ④ 窗口边界（窄窗形）：?limit=1 的滑窗里，下沿时刻**之前**
    被揭示的事件不入（轮 1 自己的世界步事件——属于未服务的轮，加载
    更早信件时随真轮归来）；边界轮自身世界步的事件（下沿与本轮之间）
    仍挂首轮服务帧；两轮之间揭示的遗留挂本轮信前（真实时序位）。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=TwoStepProvider()) as stack:
        stack.post("/api/turn", {"text": "第一封信。"})
        stack.post("/api/turn", {"text": "第二封信。"})
        status, narrow = stack.get_json("/api/history?limit=1")
        assert status == 200
        assert len(narrow["turns"]) == 1
        narrations = _frame_narrations(narrow["turns"][0])
        # the boundary turn's own step events still ride its frame
        assert "集市在广场上支起来了，鱼车天不亮就出了摊。" in narrations
        # the pre-window reveals (turn one's own step) stay out
        assert "雾又漫上码头，镇子把它当作日常。" not in narrations
        assert "潮水在午后转向，滩涂重新露了出来。" not in narrations
        # the full read recovers them at their true turn
        status, full = stack.get_json("/api/history?full=1")
        assert status == 200
        first, second = full["turns"]
        assert "雾又漫上码头，镇子把它当作日常。" in _frame_narrations(first)
        assert "集市在广场上支起来了，鱼车天不亮就出了摊。" in _frame_narrations(second)


def test_beyond_50_turns_the_sliding_window_holds(tmp_path: Path) -> None:
    """VAL ④ 窗口边界（任务书场景）：>50 轮后默认窗口外的事件不入，
    ?full=1 随真轮归来。世界腿全程安静（not-configured——51 轮零世界
    行），事件手工注入，揭示时刻钉在首轮提交之前（属于未服务的轮一）。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=QuietWorldProvider()) as stack:
        stack.post("/api/turn", {"text": "第一封信。"})
        stack.post("/api/turn", {"text": "第二封信。"})
        conn = sqlite3.connect(app_db)
        conn.execute("PRAGMA foreign_keys = ON")
        _insert_event(
            conn,
            event_id="early-note",
            narration="早期的一行：面包炉的火比天亮得还早。",
            created_at="2026-05-28",
            # revealed before the conversation's first turn committed —
            # it belongs to turn one, which the default window leaves out
            revealed_at="2020-01-01T00:00:00+00:00",
        )
        conn.commit()
        conn.close()
        for index in range(3, 52):
            status, _ = stack.post("/api/turn", {"text": f"第{index}封信。"})
            assert status == 200
        status, windowed = stack.get_json("/api/history")
        assert status == 200
        assert windowed["has_more"] is True
        assert len(windowed["turns"]) == 50
        assert "早期的一行：面包炉的火比天亮得还早。" not in [
            note
            for turn in windowed["turns"]
            for note in _frame_narrations(turn)
        ]
        status, full = stack.get_json("/api/history?full=1")
        assert status == 200
        framed_first = _frame_narrations(full["turns"][0])
        assert "早期的一行：面包炉的火比天亮得还早。" in framed_first


# ---------------------------------------------------------------------------
# 4 — the red line


def test_history_never_flips_and_leftover_arrives_via_inbox(
    tmp_path: Path,
) -> None:
    """VAL ⑤ 红线（行为半）+ 遗留恢复闭环：GET /api/history 前后
    PENDING 行状态逐字不变（零翻面、载荷零帧）；遗留只经 inbox 读
    （加载序前半）翻开，再经交错载荷唯一到达。"""

    app_db = tmp_path / "app.db"
    pending_sql = (
        "SELECT status, revealed_at FROM world_reveal_item"
        " WHERE item_id = 'hand-left:reveal'"
    )
    with web_stack(
        app_db, provider=BeatsProvider(beats_json=_STEP1)
    ) as stack:
        stack.post("/api/turn", {"text": "第一封信。"})
        conn = sqlite3.connect(app_db)
        conn.execute("PRAGMA foreign_keys = ON")
        _insert_event(
            conn,
            event_id="hand-left",
            narration="遗留的一行：码头尽头有人把灯挂了回去。",
            created_at="2026-06-02",
            revealed_at=None,
        )
        conn.commit()
        conn.close()

        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "遗留的一行：码头尽头有人把灯挂了回去。" not in [
            note
            for turn in history["turns"]
            for note in _frame_narrations(turn)
        ]
        # the store state is byte-identical: still PENDING, still unstamped
        assert _ro_rows(app_db, pending_sql) == [("PENDING", None)]

        # the load order's first half flips it; the interleave carries it
        status, _ = stack.get_json("/api/world/inbox")
        assert status == 200
        assert _ro_rows(app_db, pending_sql)[0][0] == "REVEALED"
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert "遗留的一行：码头尽头有人把灯挂了回去。" in [
            note
            for turn in history["turns"]
            for note in _frame_narrations(turn)
        ]


def test_the_history_faces_never_call_reveal_all() -> None:
    """VAL ⑤ 红线（结构半）：history 读面与 wr-8 两个帮手零
    ``reveal_all`` 调用（调用级 AST——docstring 提及不算）。"""

    tree = ast.parse((WEBUI.parent / "web.py").read_text(encoding="utf-8"))
    faces = {"history", "_world_frames_for_window", "_turn_created_at_of"}
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name not in faces:
                continue
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "reveal_all"
                ):
                    offenders.append(node.name)
    assert offenders == []


# ---------------------------------------------------------------------------
# 5 — the frontend order


def test_the_load_chain_reads_inbox_before_history() -> None:
    """VAL ⑤ 加载序钉：页面装载 inbox 先（触发揭示、零渲染）→
    history 后（交错含刚翻开的遗留）；旧序（history 先、inbox 尾随）
    负控。"""

    app = _text("app.js")
    chain = app[app.index("loadMasthead().catch(() => {});") :]
    assert (
        "loadWorldInbox()\n    .then(() => loadHistory())" in chain
    )
    assert "loadHistory()\n    .then(() => loadWorldInbox())" not in app


def test_the_tail_top_up_arm_is_retired() -> None:
    """VAL ⑤ 尾部补显臂退役钉：loadWorldInbox 体零渲染（无
    renderWorldStory、无 revealed_now 触发），退役句在场；语言切换臂
    改走 history 重渲染（世界块已入交错）。"""

    app = _text("app.js")
    body = app[
        app.index("async function loadWorldInbox"):
        app.index("// WR-6（DEC-OPI-8a4f980b…13）：延时揭示臂整体退役")
    ]
    assert "renderWorldStory" not in body
    assert "revealed_now" not in body
    after = app[
        app.index("// WR-6（DEC-OPI-8a4f980b…13）：延时揭示臂整体退役"):
        app.index("const TYPING_CPS")
    ]
    assert "加载补显臂" in after and "退役" in after
    save = app[
        app.index("async function saveUiLanguage"):
        app.index("async function saveReplyLanguage")
    ]
    assert "await loadHistory();" in save
    assert "loadWorldInbox" not in save


def test_history_frames_render_after_the_letter_same_shape() -> None:
    """VAL ⑥ 前端恢复钉（wr-8R 正序织入，DEC-OPI-41a4df20…16）：历史
    轮的世界帧落在该轮用户信**之后**渲染（用户互动=世界史事件——刷
    新序=实况序 [信][世界帧][回信]，回信 addLine 在帧后）；lr-2 交错
    面多帧（DEC-OPI-c73dbff3…114）：一轮多块按 world_steps 序逐块渲
    染（world_steps 缺席 = 单帧轮原形）；用户行先建、世界块信后落、
    回信行最后——次序由源序钉死；零打字机（历史恢复是已完成事实）；
    负控：beforeEl 织入形在 renderFlowHistory 切片内零残留。"""

    app = _text("app.js")
    flow = app[
        app.index("async function renderFlowHistory"):
        app.index("async function loadHistory()")
    ]
    assert "const steps = Array.isArray(turn.world_steps" in flow
    assert ": [turn.world];" in flow
    # Multi-block loop: every frame renders after the letter, the
    # world_steps order preserved (wr-8R: the refresh order equals the
    # live order — the beforeEl weave is gone from the flow slice).
    assert "steps.forEach((frame) => {" in flow
    assert "withTransition" not in flow
    assert "renderWorldStory(frame);" in flow
    assert "beforeEl" not in flow
    user_add = flow.index('addLine("user"')
    world_add = flow.index("const steps = Array.isArray(turn.world_steps")
    assistant_add = flow.index('addLine("assistant"')
    assert user_add < world_add < assistant_add
    # the live-turn arm keeps its own shape (the wr-7 regression anchor,
    # lr-2/lr-3T truth: the settle renders without the seam — the
    # transition sentence is retired; closeChain keeps the gate duty)
    turn_body = app[
        app.index("async function postTurn"):
        app.index("async function postTeachMe")
    ]
    assert "renderWorldStory(event)" in turn_body
    assert "startWorldStream" not in flow


# ---------------------------------------------------------------------------
# 6 — the worldless history


def test_worldless_history_stays_unkeyed(tmp_path: Path) -> None:
    """VAL ⑥ 零迁移半 + 载荷形状：无世界事件的通信，历史载荷逐轮不
    带 world 键——pre-wr-8 形分毫不动（可加性键的另一半）。"""

    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=MuteProvider()) as stack:
        stack.post("/api/turn", {"text": "第一封信。"})
        stack.post("/api/turn", {"text": "第二封信。"})
        status, history = stack.get_json("/api/history")
        assert status == 200
        assert len(history["turns"]) == 2
        for turn in history["turns"]:
            assert "world" not in turn
