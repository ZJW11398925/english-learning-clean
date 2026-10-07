"""WR-3 — the world narration's presentation face (the paradigm's
presentation close-out; DEC-OPI-5fc42174…63).

The living-world paradigm's last half (the first half was WR-2's
generation face): the world steps **after** the reply on the server,
and the page presents what it left behind. The pin groups:

1. **the delayed reveal** — the finalize tail schedules exactly one
   timer-driven world read (``WORLD_REVEAL_DELAY_MS``, a named
   calibration constant with its Revisit note); a new letter clears the
   old timer first; the turn body itself never awaits an inbox read
   (the reply is the page's substance);
2. **the retirements, recut by WR-5** — the ``onWorld`` frame path
   (the third ``fetchTurnStream`` parameter and the
   ``{"type": "world"}`` parser branch) stays **pinned gone** (no
   producer since WR-2); the transition sentence, retired by wr-3, is
   **restored** by WR-5 (DEC-OPI-8a4f980b…7: the chronicle's own
   record of a world-internal letter arriving — a presentation seam,
   not the world reacting; the block lands **before the reply** with
   the sentence at its tail, and the renderer never scrolls);
3. **the fallback bit, recut** (the server's two-face fix) — an event
   whose source is ``world_narrator`` passes its stored narration
   through verbatim with ``fallback: False`` (the narrator already
   wrote it in the interface language — the bit never lies); a pool
   event keeps the zh-mapping arm and a legacy English row keeps its
   honest ``True``;
4. **the end-to-end seam** — a real web stack with a scripted provider:
   a letter lands, the server's post-turn step writes generated beats,
   and the inbox's read answers them without a fallback bit.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from elc.persona.types import CompiledPrompt, ProviderOutput
from tests.host.test_w1_web import REPLY, web_stack

WEBUI = Path(__file__).resolve().parents[2] / "src" / "elc" / "webui"

BEATS_JSON = json.dumps(
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
        ]
    },
    ensure_ascii=False,
)


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 — the world-first wiring (WR-6 recut: the delayed reveal is retired)


def test_the_delayed_reveal_is_fully_retired() -> None:
    """WR-6（DEC-OPI-8a4f980b…13）：延时揭示臂整体退役——世界步已回到
    回信之前（流内 world 帧先讲），无需事后 timer 重读。常量、timer
    句柄、schedule 函数与 turn 体内的清 timer 臂全部缺位（负控）。"""

    app = _text("app.js")
    assert "WORLD_REVEAL_DELAY_MS" not in app
    assert "worldRevealTimer" not in app
    assert "scheduleWorldReveal" not in app
    assert "setTimeout" not in app[
        app.index("async function postTurn"):
        app.index("async function postTeachMe")
    ]


def test_the_world_frame_renders_inline_before_the_reply() -> None:
    """WR-6：世界帧当场渲染——onWorld 回调带过渡句、零滚动；turn 体零
    inbox 读（帧即呈现，load 臂只管页面装载遗留）。"""

    app = _text("app.js")
    turn_block = app[
        app.index("async function postTurn"):
        app.index("async function postTeachMe")
    ]
    assert "loadWorldInbox(" not in turn_block
    assert (
        "renderWorldStory(event, { withTransition: true })" in turn_block
    )
    # The blocking fallback renders the payload's world key first.
    assert "renderWorldStory(data.world, { withTransition: true });" in app
    # The renderer never scrolls (wr-5's law survives).
    renderer = app[
        app.index("function renderWorldStory"):
        app.index("async function loadWorldInbox")
    ]
    assert "window.scrollTo" not in renderer


# ---------------------------------------------------------------------------
# 2 — the retirements (WR-5 flips the transition retirement back)


def test_the_transition_sentence_is_restored() -> None:
    """WR-5（DEC-OPI-8a4f980b…7，用户定向第四击）：过渡句恢复（wr-3
    曾误退）——「这时，她收到了你的来信。」是世界编年史对一封世界内
    信件的如实记录（信是用户角色寄入世界的事件；呈现层缝合句，非
    「世界回应信」的剧情反应）。thenLetter 双语句、world-story-then
    分支与 CSS 规则全部回到位。"""

    app = _text("app.js")
    assert "这时，她收到了你的来信。" in app
    assert "Then, your letter arrives." in app
    assert "thenLetter" in app
    assert "world-story-then" in app
    components = (WEBUI / "components.css").read_text(encoding="utf-8")
    assert ".world-story .world-story-then {" in components


def test_the_onworld_frame_path_is_restored() -> None:
    """WR-6：onWorld 帧路径恢复；wr-7：fetchTurnStream 五参——
    world_delta（叙述增量）/world_failed（拒收诚实句柄）分支回来，
    app.js 的调用点把世界帧交给 settleWorld（wr-7R 排空后定版——权
    威渲染替换流式块）。帧有生产者了（世界先行步 + 叙述流式增量）。"""

    api = _text("api.js")
    assert (
        "export async function fetchTurnStream(text, onDelta, onWorld,"
        in api
    )
    assert "onWorldDelta, onWorldFailed) {" in api
    assert 'event.type === "world"' in api
    assert 'event.type === "world_delta"' in api
    assert 'event.type === "world_failed"' in api
    app = _text("app.js")
    call = app[app.index("data = await fetchTurnStream(") :]
    call = call[: call.index("\n    );")]
    assert "settleWorld(event)" in call
    assert "worldStream.push(piece, index)" in call
    assert "failWorld()" in call


# ---------------------------------------------------------------------------
# 3 — the fallback bit, recut (the server's two-face fix)


def _face_rows(app_db: Path) -> sqlite3.Connection:
    """Read committed rows off the serving database (a fresh read-only
    connection — the serving one stays with the host thread)."""

    conn = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_generated_narrations_carry_no_fallback_bit(
    tmp_path: Path,
) -> None:
    """WR-3 R5 E2E：真 web 栈 + scripted provider——寄信 → 服务端后置步
    落两条生成 beats → GET /api/world/inbox 读即揭示：叙述逐字在场且
    **无 fallback 位**（生成叙述本就是界面语言，位不撒谎）。"""

    app_db = tmp_path / "app.db"

    class BeatsProvider:
        def __init__(self) -> None:
            self._dial = 0

        def call(self, prompt: CompiledPrompt) -> ProviderOutput:
            self._dial += 1
            # WR-6 世界先行：叙事拨号在前（答 beats JSON）。
            if self._dial == 1:
                return ProviderOutput(text=BEATS_JSON, error=None)
            return ProviderOutput(text=REPLY, error=None)

    with web_stack(app_db, provider=BeatsProvider()) as stack:
        status, _ = stack.post("/api/turn", {"text": "Any letter."})
        assert status == 200
        status, inbox = stack.get_json("/api/world/inbox")
        assert status == 200
        narrations = [str(item["narration"]) for item in inbox["items"]]
        assert "雾又漫上码头，镇子把它当作日常。" in narrations
        for item in inbox["items"]:
            assert not item.get("fallback")


def test_the_pool_and_legacy_fallback_arms_are_unchanged(
    tmp_path: Path,
) -> None:
    """R5 的不变半：池事件（zh 映射在）渲染包中文不标 fallback；遗留
    英文行（kind 无映射）回退英文并诚实标注 fallback:true——生成臂只
    是新增，旧行为字节不变（wf-0 注入形先例——直接写编年史行再读）。
    """

    app_db = tmp_path / "app.db"

    class QuietProvider:
        def call(self, prompt: CompiledPrompt) -> ProviderOutput:
            return ProviderOutput(
                text=REPLY, error=None
            )

    with web_stack(app_db, provider=QuietProvider()) as stack:
        conn = sqlite3.connect(app_db)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO world_event (event_id, world_id, kind,"
            " narration, effects, occurred_at, source)"
            " VALUES ('seed-pool', (SELECT world_id FROM"
            " world_conversation LIMIT 1), 'market_day',"
            " 'It is Saturday on the quay.', '[]',"
            " '2025-09-20', 'world_engine')"
        )
        conn.execute(
            "INSERT INTO world_event (event_id, world_id, kind,"
            " narration, effects, occurred_at, source)"
            " VALUES ('seed-legacy', (SELECT world_id FROM"
            " world_conversation LIMIT 1), 'retired_kind',"
            " 'A v1 event the package never carried.', '[]',"
            " '2026-09-01T07:30:00+00:00', 'world_engine')"
        )
        conn.execute(
            "INSERT INTO world_reveal_item (item_id, world_id,"
            " source_event_id, actor_id, status, revealed_at, created_at)"
            " VALUES ('seed-pool:reveal', (SELECT world_id FROM"
            " world_conversation LIMIT 1), 'seed-pool', NULL,"
            " 'PENDING', NULL, '2025-09-20')"
        )
        conn.execute(
            "INSERT INTO world_reveal_item (item_id, world_id,"
            " source_event_id, actor_id, status, revealed_at, created_at)"
            " VALUES ('seed-legacy:reveal', (SELECT world_id FROM"
            " world_conversation LIMIT 1), 'seed-legacy', NULL,"
            " 'PENDING', NULL, '2026-09-01T07:30:00+00:00')"
        )
        conn.commit()
        conn.close()
        status, inbox = stack.get_json("/api/world/inbox")
        assert status == 200
        by_narration = {
            str(item["narration"]): item for item in inbox["items"]
        }
        # The pool event: the package's own Chinese prose, no fallback.
        pool = by_narration.get(
            "今天是码头上的星期六：鱼车天不亮就出了摊，毛线和面包摊做"
            "到半上午的生意，半个镇子回家路上都会经过那扇绿门，隔着玻"
            "璃窗点个头。"
        )
        assert pool is not None
        assert not pool.get("fallback")
        # The legacy English row: honest English with the bit set.
        legacy = by_narration.get("A v1 event the package never carried.")
        assert legacy is not None
        assert legacy.get("fallback") is True
