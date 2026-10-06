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
2. **the retirements** — the transition sentence
   (「这时，她收到了你的来信。」—— the world-answers-the-letter
   paradigm's copy) and the ``onWorld`` frame path (the third
   ``fetchTurnStream`` parameter and the ``{"type": "world"}`` parser
   branch) are **pinned gone**: the frame has had no producer since
   WR-2, and the sentence's meaning died with DEC-…58's two-layer law;
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
# 1 — the delayed reveal's wiring


def test_the_delayed_reveal_is_wired_with_a_named_constant() -> None:
    """WR-3 R1：finalize 之后恰一次 timer 驱动的世界读——命名常量
    WORLD_REVEAL_DELAY_MS（4000，Revisit 校准注在场）+ scheduleWorldReveal
    挂在 postTurn 成功尾 + 新信先清旧 timer（防重入）。"""

    app = _text("app.js")
    assert "const WORLD_REVEAL_DELAY_MS = 4000;" in app
    assert "a calibration replaces this constant" in app
    assert "function scheduleWorldReveal()" in app
    assert "scheduleWorldReveal();" in app
    # The timer is module-level and cleared both on schedule and on a
    # new letter (the re-entry hygiene).
    assert "let worldRevealTimer = 0;" in app
    assert "clearTimeout(worldRevealTimer);" in app
    # The timer callback is the read — the delayed arm dials the same
    # idempotent loadWorldInbox (zero reveal ⇒ zero block).
    schedule = app[app.index("function scheduleWorldReveal"):]
    needle = schedule.index("}, WORLD_REVEAL_DELAY_MS")
    schedule = schedule[: schedule.index("}", needle)]
    assert "loadWorldInbox();" in schedule


def test_the_turn_body_never_awaits_the_inbox() -> None:
    """The turn's own flow never awaits an inbox read (the reply is the
    page's substance); the delayed arm is the one legal re-read."""

    app = _text("app.js")
    turn_block = app[
        app.index("async function postTurn"):
        app.index("async function postTeachMe")
    ]
    assert "await loadWorldInbox" not in turn_block
    assert "scheduleWorldReveal();" in turn_block


# ---------------------------------------------------------------------------
# 2 — the retirements


def test_the_transition_sentence_is_retired() -> None:
    """WR-3 R3：过渡句（「这时，她收到了你的来信。」/ "Then, your letter
    arrives."）与 world-story-then 分支、thenLetter 键、withTransition
    形参——全部退役（「世界回应信」范式的文案，双层律下语义错误）。"""

    app = _text("app.js")
    for gone in (
        "这时，她收到了你的来信。",
        "Then, your letter arrives.",
        "thenLetter",
        "world-story-then",
        "withTransition",
    ):
        assert gone not in app, gone


def test_the_onworld_frame_path_is_retired() -> None:
    """WR-3 R4：onWorld 死路径退役——api.js 的 fetchTurnStream 回双参
    （第三参与 {"type":"world"} 帧解析分支不在），app.js 的调用点双参。"""

    api = _text("api.js")
    assert "export async function fetchTurnStream(text, onDelta) {" in api
    assert 'event.type === "world"' not in api
    assert "onWorld" not in api
    app = _text("app.js")
    assert "fetchTurnStream(" in app
    call = app[app.index("data = await fetchTurnStream(") :]
    call = call[: call.index(");")]
    assert "renderWorldStory" not in call


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
            if self._dial % 2 == 1:
                return ProviderOutput(text=REPLY, error=None)
            return ProviderOutput(text=BEATS_JSON, error=None)

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
