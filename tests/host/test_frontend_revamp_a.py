"""fr-A — 前端修订刀 A（五问题）的钉面：写作态收窄 / 会话窗三件 /
设置页完全体 / 排印体系化 / 墨选。

授权链：用户「前端修订刀 A（五问题）」任务书（分支 frontend-revamp）；
形态级修订登记 = docs/FRONTEND_SPEC.md ⑨-14（同刀改行 ②-4a ②-6 ③ ⑩
10.2 / ②-5 令牌行）。本文件按五问题分五组，逐组含**结构性钉**与**行为
钉**——删实现即红（变异证据见回执）。

组：
1. 写作态收窄（问题 1）——.dock--compose 内容自适应 + 50dvh 上限；
   composePenCap 全视口统一；520px 降级块退役；
2. 会话窗三件（问题 2a/2b）——回底墨点与轮次刻度的 DOM/CSS/接线；
3. token 计量数据面全链（问题 2c）——provider 提取（无 usage 如实
   None）→ 迁移 0021 三列 → 落库读回 → /api/history 轮级 + 会话累计
   → /api/turn 随行 → 案头计量条 → 设置开关（sessionStorage）；
4. 设置页完全体（问题 3）——分组 IA 五区 + 模式视觉读面（三档映射，
   mode 仍拒写）+ 披露规则编辑面（写面接通：读写回路 / 幂等 / 400
   人话 / 409 重读；「只读」句退役）；
5. 排印体系化 + 墨选（问题 4/5）——--t-* 配方九枚 + 四族规范在
   tokens 头注与 spec ②-4a；零相对行高字面；原生 <select> 全退役 +
   #27 契约（aria/键盘/点外关闭）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from elc.content.build import build_content_db
from elc.detection import DetectorRegistry
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.host import open_host
from elc.persona.openai_provider import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import CompiledPrompt, ProviderOutput, ProviderUsage
from elc.platform.types import ConversationId, Ok, PersonaId, SecretRef
from elc.teaching.rollout import RolloutStage
from elc.user_config.types import DisclosureLevel
from elc.web import DEFAULT_WEB_CONVERSATION_ID, _WebFace
from tests.conftest import SCHEMA_HEAD_VERSION
from tests.host.test_w1_web import _page_source, web_stack

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = REPO_ROOT / "src" / "elc" / "webui"
MIGRATIONS = REPO_ROOT / "migrations"
KEY = "sk-fr-a-secret"


def _webui(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _page_of(tmp_path: Path) -> str:
    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("fra-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


# ---------------------------------------------------------------------------
# 1 — 写作态收窄（问题 1）


def test_the_compose_face_is_content_sized_with_a_half_screen_cap() -> None:
    """fr-A 形态修订：写作态自近全屏收窄为「内容自适应 + 50dvh 上限」——
    底缘贴底（top: auto）、半屏封顶（信流上半始终可见）、稿纸 flex:none
    由内联 autosize 高驱动（flex:1 basis 0 会把内联高吃掉）；v3-a 的
    近全屏 top 账与 520px 降级块一并退役。"""

    screens = _webui("screens.css")
    compose = screens[screens.index(".dock.dock--compose {"):]
    compose = compose[: compose.index("}")]
    assert "bottom: 0;" in compose
    assert "top: auto;" in compose
    assert "max-height: 50dvh;" in compose
    assert "top: calc(var(--sp-8) + var(--sp-1));" not in compose
    # 稿纸：flex:none（内联高是高度真源）+ 四行下限 + 不设上限（封顶在
    # JS 的 composePenCap，CSS 侧面板 max-height 是最后一道闸）
    pen = screens[screens.index(".dock--compose .pen--open {"):]
    pen = pen[: pen.index("}")]
    assert "flex: none;" in pen
    assert "min-height: calc(var(--baseline) * 4);" in pen
    assert "max-height: none;" in pen
    row = screens[screens.index(".dock--compose .dock-row {"):]
    row = row[: row.index("}")]
    assert "flex: none;" in row
    # 降级双形态退役（基础形态本身即降级读法）
    assert "@media (max-height: 520px)" not in screens


def test_the_pen_cap_is_the_half_screen_minus_chrome() -> None:
    """composePenCap = 50dvh − 铬件账 148px，下限 4×baseline（128）——
    全视口档统一形态；写作态开着才量（收起态稿纸 hidden 不量）。"""

    app = _webui("app.js")
    assert "function composePenCap() {" in app
    assert "Math.floor(window.innerHeight / 2) - 148" in app
    assert "Math.max(128," in app
    assert "autosizeTo(pen, composePenCap())" in app
    assert "if (pen && composeOpen()) autosizeTo" in app
    # v3-a 的 matchMedia 双形态与 change 监听随降级块退役
    assert "SHORT_VIEWPORT" not in app
    # Esc 收起与触发条语义不动（v3-a 层序照旧）
    assert 'document.getElementById("dock-trigger").addEventListener(' in app
    assert '"click", openComposeFace);' in app
    assert 'if (event.key !== "Escape") return;' in app


# ---------------------------------------------------------------------------
# 2a — 一键回底（问题 2a）


def test_the_flow_bottom_dot_exists_and_follows_the_distance() -> None:
    """回底钮（veto-R 重铸随迁：墨点形态退役）：#24 契约块 + 屏级位置账
    + 工厂接线——离底阈值浮现、在底即藏、写作态藏、离案头藏；点击平滑
    回底（reduced-motion 直落）。形态 = 纸底+发丝线+图标+「回到底」
    字标（圆形与 aria-label 独挑语义随墨点退役——字标承担可读语义）。"""

    index = _webui("index.html")
    assert 'id="flow-bottom"' in index
    assert 'class="flow-bottom"' in index
    assert 'class="flow-bottom-word">回到底</span>' in index
    css = _webui("components.css")
    assert "24. flow-bottom" in css
    block = css[css.index("/* ── 24. flow-bottom"):
                css.index("/* ── 25. flow-ruler")]
    assert "状态矩阵：" in block and "使用规则：" in block
    assert "禁止变体：" in block
    assert "border-radius" not in block
    assert "background: var(--paper-high)" in block
    assert "border: 1px solid var(--rule)" in block
    screens = _webui("screens.css")
    assert ".flow-bottom { position: fixed; z-index: 5;" in screens
    assert "var(--navdock-h) + var(--dock-trigger-h)" in screens
    app = _webui("app.js")
    assert "const FLOW_BOTTOM_THRESHOLD = 240;" in app
    assert "function syncFlowBottom() {" in app
    assert "flowBottomBtn.hidden = Boolean(spaces.parlor.hidden) ||" in app
    assert "flowDistanceFromBottom() < FLOW_BOTTOM_THRESHOLD;" in app
    assert 'window.addEventListener("scroll", syncFlowBottom, ' \
        '{ passive: true });' in app
    assert 'behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });' in app


# ---------------------------------------------------------------------------
# 2b — 轮次刻度（问题 2b）


def test_the_turn_ruler_is_one_tick_per_turn_with_honest_paging() -> None:
    """轮次刻度：#25 契约块 + nav 骨架 + 轮锚（每轮一点）+ 视位高亮 +
    点击跳转；刻度只管已加载窗口——「加载更早」按 50 轮一档衔接，口径句
    写在信流顶部（主线-2 的显式宽度参数）。"""

    index = _webui("index.html")
    assert 'id="flow-ruler"' in index
    assert 'aria-label="轮次刻度"' in index
    css = _webui("components.css")
    assert "25. flow-ruler" in css
    assert ".flow-tick--on::before { width: 14px; background: var(--ink); }" \
        in css
    screens = _webui("screens.css")
    assert ".flow-ruler { position: fixed; z-index: 5;" in screens
    app = _webui("app.js")
    assert "let flowTurns = [];" in app
    assert "function buildFlowRuler() {" in app
    assert 'tick.setAttribute("aria-label", "第 " + (i + 1) + " 轮");' in app
    assert "tick.addEventListener(\"click\", () => scrollToFlowTurn(i));" in app
    assert "function flowSpyTick() {" in app
    # 视线与落点同一条线（点第 n 点即第 n 点亮）——同一常数两处消费
    assert "const FLOW_TURN_OFFSET = 72;" in app
    assert "const line = window.scrollY + FLOW_TURN_OFFSET;" in app
    assert "window.scrollY -\n    FLOW_TURN_OFFSET;" in app
    assert "if (flowDistanceFromBottom() <= 4) return flowTurns.length - 1;" \
        in app
    assert "function syncFlowRuler() {" in app
    assert "flowTurns.length >= 2;" in app
    # veto-R（面⑨）：刻度 ↔ 轮锚一一对应收紧——rAF 节流的被动 listener
    # 对账 + 高亮按真实锚点位置计算（视位线 = 顶栏之下一档呼吸，与点击
    # 跳转同一条线）。
    assert "function scheduleFlowRulerSync() {" in app
    assert "requestAnimationFrame(() => {" in app
    assert 'window.addEventListener("scroll", scheduleFlowRulerSync, ' \
        '{ passive: true });' in app
    # 口径句 + 加载更早（服务端 has_more 是诚实分页位；veto-R 数据优先
    # 收短——口径句尾句收成最短词）
    assert "刻度只管已加载的窗口——" in app
    assert " 往前翻。" in app
    assert "更早的信没有了。" in app
    assert "async function loadEarlierLetters() {" in app
    assert "parlorWindow = (lastHistoryWindow || before || 50) + 50;" in app
    assert "const shift = flowTurns.length - before;" in app
    assert "if (shift > 0 && flowTurns[shift]) scrollToFlowTurn(shift, true);" \
        in app
    # 新寄一轮即刻入刻度（usage 待响应回填）
    assert "flowTurns.push({ node: mine, usage: null });" in app


# ---------------------------------------------------------------------------
# 3 — token 计量数据面全链（问题 2c）


class _FixedSecret:
    """A one-value secret source (the protocol's shape) — the adapter's
    injectable seam, so no environment or file state rides the test."""

    def __init__(self, value: str) -> None:
        self._value = value

    def resolve(self, ref: SecretRef) -> str | None:
        del ref
        return self._value


def _provider(body: str) -> OpenAICompatibleProvider:
    def transport(
        url: str, headers: Any, body_bytes: bytes, timeout: float
    ) -> tuple[int, bytes]:
        del url, headers, body_bytes, timeout
        return (200, body.encode("utf-8"))

    return OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="http://127.0.0.1:9/v1",
            model="fra-model",
            secret_ref=SecretRef("fra-key"),
        ),
        _FixedSecret(KEY),
        transport=transport,
    )


def _call(provider: OpenAICompatibleProvider) -> ProviderOutput:
    return provider.call(
        CompiledPrompt(
            persona_id=PersonaId("persona-fra"),
            prompt_text="hello",
            generation_contract="gc",
        )
    )


def test_the_provider_extracts_the_standard_usage_and_never_fabricates() -> None:
    """提取层：OpenAI 兼容响应的标准 usage 三字段如实带出；无该字段的
    兼容端点答 None（不伪造）；非整数/布尔/负数逐字段归 None——绝不
    由分项求和补一个缺失的 total。"""

    with_usage = _call(_provider(
        '{"choices":[{"message":{"content":"hi"}}],'
        '"usage":{"prompt_tokens":11,"completion_tokens":7,'
        '"total_tokens":18}}'
    ))
    assert with_usage.error is None
    assert with_usage.usage is not None
    assert with_usage.usage.prompt_tokens == 11
    assert with_usage.usage.completion_tokens == 7
    assert with_usage.usage.total_tokens == 18

    without = _call(_provider('{"choices":[{"message":{"content":"hi"}}]}'))
    assert without.error is None
    assert without.usage is None

    # a counter that is not an honest count stays None — and the missing
    # total is never summed back from the parts
    partial = _call(_provider(
        '{"choices":[{"message":{"content":"hi"}}],'
        '"usage":{"prompt_tokens":3,"completion_tokens":"x",'
        '"total_tokens":true}}'
    ))
    assert partial.usage is not None
    assert partial.usage.prompt_tokens == 3
    assert partial.usage.completion_tokens is None
    assert partial.usage.total_tokens is None

    negative = _call(_provider(
        '{"choices":[{"message":{"content":"hi"}}],'
        '"usage":{"prompt_tokens":-4}}'
    ))
    assert negative.usage is not None
    assert negative.usage.prompt_tokens is None

    # a non-object usage is "reported nothing", not a shape error
    wrong_shape = _call(_provider(
        '{"choices":[{"message":{"content":"hi"}}],"usage":"n/a"}'
    ))
    assert wrong_shape.error is None
    assert wrong_shape.usage is None


def test_the_usage_columns_are_the_adjudicated_migration() -> None:
    """落库：迁移 0021 三列（NULLABLE + CHECK ≥ 0——无 usage 的端点留
    NULL，读面靠 SQL 的 SUM-ignores-NULL 只计已计量；交付时为 0020，
    合并时因 master 侧 0020_world_lore_facts 先合而重编号——先合侧为
    准）；§20 列集的原样性由 phase1 的钉承重（三列为 adjudicated
    扩列，owner_epoch 先例）。"""

    sql = (MIGRATIONS / "0021_provider_usage.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE provider_attempt ADD COLUMN prompt_tokens INTEGER" in sql
    assert "ALTER TABLE provider_attempt ADD COLUMN completion_tokens INTEGER" in sql
    assert "ALTER TABLE provider_attempt ADD COLUMN total_tokens INTEGER" in sql
    assert sql.count("CHECK (prompt_tokens >= 0)") == 1
    assert sql.count("CHECK (completion_tokens >= 0)") == 1
    assert sql.count("CHECK (total_tokens >= 0)") == 1
    assert "'schema_version', '21'" in sql
    assert "'runtime_schema_version', '21'" in sql

    conn = sqlite3.connect(":memory:")
    from elc.platform.db import migrations

    migrations.apply_migrations(conn)
    columns = [
        str(row[1])
        for row in conn.execute("PRAGMA table_info(provider_attempt)")
    ]
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        assert name in columns, name
    # W-1-1 随迁、W-1-2 再随迁、W-1-3 三随迁、C1-a 四随迁：chain head =
    # 0027（W-1-1 世界事件树两表，W-1-2 世界运转一行，W-1-3 揭示队列一表，
    # C1-a 编年史归属两列；veto-R 随迁至 0023 的先例同型）；0021 的三列
    # 本体与自带 stamp（'21'，上钉）不动。
    assert migrations.schema_version(conn) == SCHEMA_HEAD_VERSION
    conn.close()


def test_the_measured_usage_rides_the_whole_chain(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """全链（真装配，零手写 SQL 播种）：provider 报 usage → PersonaRuntime
    落 attempt 行（migration 0021 三列）→ store 读回 → /api/turn 随行
    → /api/history 轮级 + 会话累计。第二轮未报 usage：该轮 None，累计只
    吃报来的那一次（measured 1 / total 2）——不伪造 0。"""

    host = open_host(
        tmp_path / "app.db",
        provider=ScriptedPersonaProvider(script=(
            ProviderOutput(
                text="fra metered reply",
                usage=ProviderUsage(
                    prompt_tokens=5, completion_tokens=6, total_tokens=11
                ),
            ),
            ProviderOutput(text="fra unmetered reply"),
        )),
        content_db_path=pilot_content_db,
    )
    try:
        opened = host.open_conversation(
            ConversationId(DEFAULT_WEB_CONVERSATION_ID)
        )
        assert isinstance(opened, Ok), opened
        face = _WebFace(host, DEFAULT_WEB_CONVERSATION_ID)
        first = face.turn("A measured letter.")
        assert first["reply"] == "fra metered reply", first
        assert first["usage"] == {
            "prompt_tokens": 5,
            "completion_tokens": 6,
            "total_tokens": 11,
        }
        second = face.turn("An unmetered letter.")
        assert second["reply"] == "fra unmetered reply", second
        assert second["usage"] is None
        history = face.history()
        assert [turn["usage"] for turn in history["turns"]] == [
            {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
            None,
        ]
        assert history["usage"] == {
            "prompt_tokens": 5,
            "completion_tokens": 6,
            "total_tokens": 11,
            "measured_calls": 1,
            "total_calls": 2,
        }
        # 窗口无关：最窄窗口读回的累计与全窗一致
        assert face.history(limit=1)["usage"] == history["usage"]
    finally:
        host.close()


def test_the_history_and_turn_faces_carry_the_measured_usage(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """读面：/api/history 轮级 usage + 顶层会话累计（窗口无关）；脚本
    provider 未报 usage ⇒ 逐项 None 且累计 0/N 次计量——不伪造 0 当作
    真读数；/api/turn 随行本轮 usage。"""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        stage=RolloutStage.STUDY_FIRST,
    ) as stack:
        status, turn = stack.post("/api/turn", {"text": "One letter."})
        assert status == 200, turn
        assert turn["usage"] is None   # the scripted provider meters nothing
        status, history = stack.get_json("/api/history")
        assert status == 200, history
        assert history["turns"][0]["usage"] is None
        assert history["usage"] == {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "measured_calls": 0,
            "total_calls": 1,
        }
        # the window-independent claim: ?limit=1 reads the same totals
        status, narrow = stack.get_json("/api/history?limit=1")
        assert status == 200, narrow
        assert narrow["usage"] == history["usage"]


def test_the_page_meter_reads_the_face_and_holds_the_switch() -> None:
    """UI + 开关（veto-R 重铸随迁：紧凑计量粒）：dock 上沿内嵌读数钮
    （#26 契约 + 粒位置账）读 /api/history 的累计与逐轮；点按展开
    .tm-pop 逐轮明细浮层（浮层家族：Esc 关、点外关、⑩ 互斥收）；
    “显示 token 计量”开关存 sessionStorage（客户端侧，如实标注）；
    无读数不现位（空说明句退役），未计量字段在浮层里如实「—」。"""

    index = _webui("index.html")
    assert 'id="tokenmeter"' in index
    assert 'class="tokenmeter"' in index
    assert index.index('id="tokenmeter"') < index.index('id="dock-trigger"')
    css = _webui("components.css")
    assert "26. tokenmeter" in css
    assert ".tokenmeter .tm-num, .tm-pop .tm-num " \
        "{ font-variant-numeric: tabular-nums;" in css
    assert ".tm-pop { position: fixed; z-index: 10;" in css
    screens = _webui("screens.css")
    # veto-R：sticky 独立层退役——screens 的计量位置账只留退役登记注释
    # （pageback 的 sticky 是另一处既有规则，不涉计量）
    assert ".tokenmeter { position: sticky" not in screens
    assert "sticky 层位账退役" in screens
    app = _webui("app.js")
    assert 'const TOKEN_METER_KEY = "elc-token-meter";' in app
    assert "sessionStorage.setItem(TOKEN_METER_KEY, \"1\");" in app
    assert "sessionStorage.removeItem(TOKEN_METER_KEY);" in app
    assert "function syncFlowMeter(usage) {" in app
    assert "function renderTokenMeter() {" in app
    assert "function toggleTokenMeterPop() {" in app
    assert "function closeTokenMeterPop() {" in app
    # ⑩ 互斥收：开本浮层先收墨选/词卡/沓；反向同法（showSpace/开沓/
    # 升写作态收本浮层）
    assert "closeOpenSelects();" in app
    assert "closeTokenMeterPop();   // ⑩ 互斥：开沓先收计量明细浮层" in app
    # 主数据直出（累计总 token，toLocaleString 千分位 + tabular-nums）
    assert "Number(total).toLocaleString" in app
    assert 'pill.setAttribute("aria-expanded", "false");' in app
    # 无读数不现位：端点没报 usage = 粒不占位（空说明句退役）
    assert "还没有计量读数" not in app
    assert "async function refreshFlowMeter() {" in app
    assert "const data = await fetchHistory({ limit: 1 });" in app
    # 客户端不做本地加减：累计一律读回服务端
    assert "tokenMeterData.total_tokens +" not in app


def test_the_settings_display_group_carries_the_meter_toggle() -> None:
    """设置 · 显示与计量区：真开关（aria-pressed）+ 客户端侧如实标注。"""

    index = _webui("index.html")
    assert 'id="set-settings-display"' in index
    assert "<h3>显示与计量</h3>" in index
    # veto-R 数据优先收短：括号工程词退役，持久语义保留一句
    assert "只活在当前标签页，关掉就复位" in index
    app = _webui("app.js")
    assert "function renderSettingsMeter() {" in app
    assert 'toggle.setAttribute("aria-pressed", tokenMeterOn ? "true" : "false");' \
        in app
    assert "setTokenMeter(!tokenMeterOn);" in app
    assert "renderSettingsMeter();" in app


# ---------------------------------------------------------------------------
# 4 — 设置页完全体（问题 3）


def test_the_settings_page_is_five_groups_and_the_mode_face_is_visual() -> None:
    """分组 IA（模型与端点 / 教学模式 / 教学策略 / 隐私与披露 / 显示与
    计量；veto-R：panel-grid 两栏退役，节块；provider 刀：「如实说」节
    退役——接任 = 模型与端点真写面）+ 模式可改读面（veto-R 随迁）：四档
    墨选（#27），中文档名 + 分寸句一行，当前档 = 墨选现值——modeline
    三档参考块随只读读法退役（行为钉在 test_veto_response 的 mode 写面
    套件）。"""

    index = _webui("index.html")
    settings = index.split('id="drawer-settings"', 1)[1].split(
        "<nav id=\"navdock\"", 1)[0]
    for marker in ('id="set-settings-provider"', "<h3>模型与端点</h3>",
                   'id="set-settings-mode"', "<h3>教学模式</h3>",
                   'id="set-settings-knobs"', "<h3>教学策略</h3>",
                   'id="set-settings-disclosure"', "<h3>隐私与披露</h3>",
                   'id="set-settings-display"', "<h3>显示与计量</h3>"):
        assert marker in settings, marker
    assert "<h3>如实说</h3>" not in settings
    # veto-R 统一规格：panel-grid 两栏退役；模式节 = 墨选编辑器 + 分寸
    # 句 + 结果行
    assert "panel-grid" not in settings
    assert 'id="settings-mode-editor"' in settings
    assert 'id="settings-mode-note"' in settings
    assert 'id="settings-mode-result"' in settings
    app = _webui("app.js")
    assert "const MODE_CN = {" in app
    for line in (
        '"manual/user-initiated": "手动（用户发起）",',
        '"Study-first": "学习优先",',
        '"Balanced": "平衡",',
        '"Lounge": "娱乐 · 关系优先",',
    ):
        assert line in app, line
    # 分寸句一行（换档要懂的差别——数据优先原则的保留面）
    for hint in (
        "教学只在你开口要时发生。",
        "练句密度优先，批注递得勤，课程感更明显。",
        "聊天与练句并行，批注适度。",
        "聊得多，递得少，笔友以听和陪为主。",
    ):
        assert hint in app, hint
    assert "function renderSettingsMode() {" in app
    assert 'placeholder: "未声明——自动教学关着",' in app
    # modeline 读法整体退役（登记注释可提及其名，规则体不得在场）
    assert "const MODE_TIERS = [" not in app
    assert "modeline" not in app
    css = _webui("components.css")
    assert ".modeline {" not in css
    assert ".modeline--on" not in css


def test_the_disclosure_editor_reads_writes_and_refuses(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """披露编辑面：写面接通（GET 三面 → POST 全规则集 → 回读刷新）；
    幂等重放不churn；词表外层级/重复 persona 行/未知键都是 400 人话且
    零写入；空规则集合法（fail-closed 缺省）。"""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, before = stack.get_json("/api/settings")
        assert status == 200, before
        assert before["disclosure_levels"] == [
            "MINIMAL", "FUNCTIONAL", "RICH",
        ]
        assert [level.value for level in DisclosureLevel] == \
            before["disclosure_levels"]
        # 第一次写：建 policy 行（revision "1"）
        status, saved = stack.post(
            "/api/settings/disclosure",
            {"rules": [
                {"persona_id": None, "disclosure_level": "FUNCTIONAL"},
                {"persona_id": "persona-nell-alder",
                 "disclosure_level": "RICH"},
            ]},
        )
        assert status == 200, saved
        assert saved["accepted"] is True
        assert saved["idempotent"] is False
        assert saved["revision"] == "1"
        # 回读相等（读写合一）
        status, data = stack.get_json("/api/settings")
        assert data["disclosure"]["revision"] == "1"
        assert data["disclosure"]["rules"] == [
            {"persona_id": None, "disclosure_level": "FUNCTIONAL"},
            {"persona_id": "persona-nell-alder",
             "disclosure_level": "RICH"},
        ]
        # 幂等重放：同集合答 idempotent 且不 churn revision
        status, again = stack.post(
            "/api/settings/disclosure",
            {"rules": [
                {"persona_id": None, "disclosure_level": "FUNCTIONAL"},
                {"persona_id": "persona-nell-alder",
                 "disclosure_level": "RICH"},
            ]},
        )
        assert status == 200, again
        assert again["accepted"] is True
        assert again["idempotent"] is True
        assert again["revision"] == "1"
        # 改一层级：revision 前移，回读即新值
        status, moved = stack.post(
            "/api/settings/disclosure",
            {"rules": [
                {"persona_id": None, "disclosure_level": "MINIMAL"},
            ]},
        )
        assert status == 200, moved
        assert moved["idempotent"] is False
        assert moved["revision"] == "2"
        status, data = stack.get_json("/api/settings")
        assert data["disclosure"]["rules"] == [
            {"persona_id": None, "disclosure_level": "MINIMAL"},
        ]
        # 语法拒收：重复默认行 / 词表外层级 / 未知键 / 非对象 / 非列表
        refusals = (
            ({"rules": [
                {"persona_id": None, "disclosure_level": "MINIMAL"},
                {"persona_id": None, "disclosure_level": "RICH"},
            ]}, "默认规则出现了两条"),
            ({"rules": [
                {"persona_id": None, "disclosure_level": "EVERYTHING"},
            ]}, "disclosure_level 须是三词之一"),
            ({"rules": [
                {"persona_id": None, "disclosure_level": "MINIMAL",
                 "extra": 1},
            ]}, "不认识的键"),
            ({"rule": []}, "不认识的键：rule"),
            ({"rules": "nope"}, '"rules" must be a list'),
            ({"rules": [{"persona_id": "", "disclosure_level": "MINIMAL"}]},
             "persona_id 须是非空字符串或 null"),
            ([], 'need a JSON body with "rules"'),
        )
        for body, fragment in refusals:
            status, answer = stack.post("/api/settings/disclosure", body)
            assert status == 400, (body, answer)
            assert fragment in answer["error"], (body, answer)
        # 拒收零写入：durable 行仍是 revision 2 / MINIMAL
        status, data = stack.get_json("/api/settings")
        assert data["disclosure"]["revision"] == "2"
        assert data["disclosure"]["rules"] == [
            {"persona_id": None, "disclosure_level": "MINIMAL"},
        ]
        # 空规则集：合法（fail-closed 缺省），revision 照常前移
        status, emptied = stack.post(
            "/api/settings/disclosure", {"rules": []}
        )
        assert status == 200, emptied
        assert emptied["accepted"] is True
        assert emptied["revision"] == "3"
        status, data = stack.get_json("/api/settings")
        assert data["disclosure"]["rules"] == []


def test_the_settings_page_wires_the_disclosure_editor() -> None:
    """页面侧：编辑面工厂（层级墨选 + 增行/移出）+ 保存回路（409 重读
    臂）+ 「只读」句退役。"""

    app = _webui("app.js")
    assert "function editorFromDisclosure(data) {" in app
    assert "if (!data || data.available === false) return null;" in app
    assert "function renderSettingsDisclosure() {" in app
    assert "function disclosureRuleRow(rule, levels) {" in app
    assert "function disclosureAddRow(levels) {" in app
    assert "disclosureEditor.push({ persona_id: null, disclosure_level: first });" \
        in app
    assert "function renderDisclosureSave() {" in app
    assert "async function saveDisclosure(button) {" in app
    assert "data = await fetchSaveDisclosure({ rules: disclosureEditor });" in app
    assert "disclosureEditor = editorFromDisclosure(data);" in app
    assert 'disclosureResult("已保存——上面读回的就是它。", false);' in app
    assert 'settingsBox("settings-disclosure-result").hidden = true;' in app
    index = _webui("index.html")
    assert "规则在这里改" in index
    assert "规则经 profile 编辑，这里只读。" not in index
    api = _webui("api.js")
    assert '"/api/settings/disclosure"' in api
    assert "export function fetchSaveDisclosure(payload) {" in api


# ---------------------------------------------------------------------------
# 5 — 排印体系化 + 墨选（问题 4/5）


def test_the_typography_recipes_are_the_four_family_system() -> None:
    """排印：九档标度值不动（简报在册），补 --t-* 配方九枚 + 四族规范
    （tokens 头注 + spec ②-4a）；fr-A 前残留的相对行高字面全数清账。"""

    tokens = _webui("tokens.css")
    for recipe in (
        "--t-display: 400 var(--fs-display)/var(--lh-display) var(--f-display);",
        "--t-title: 400 var(--fs-title)/var(--lh-title) var(--f-display);",
        "--t-head: 400 var(--fs-head)/var(--lh-head) var(--f-display);",
        "--t-body: 400 var(--fs-body)/var(--lh-body) var(--f-serif);",
        "--t-small: 400 var(--fs-small)/var(--lh-small) var(--f-serif);",
        "--t-hand: 400 var(--fs-hand)/var(--lh-hand) var(--f-hand);",
        "--t-ui: 400 var(--fs-ui)/var(--lh-ui) var(--f-ui);",
        "--t-note: 400 var(--fs-small)/var(--lh-small) var(--f-ui);",
    ):
        assert recipe in tokens, recipe
    assert "--t-body-latin: 400 var(--fs-body-latin)/var(--lh-body-latin)" \
        in tokens
    # 四族读法写进 tokens 头注（哪个层级用哪档）
    assert "排印配方九枚（fr-A 体系化）" in tokens
    assert "① 标题层级" in tokens and "② 正文文档档" in tokens
    assert "③ 界面档" in tokens and "④ 微标签与 mono 数字档" in tokens
    # 标度值不动（逐值仍与简报一致——钉面在 r1v/v21 既有套件）
    assert "--fs-body: 17px;" in tokens
    assert "--lh-body: 32px;" in tokens
    # 零相对行高字面（全库清账）
    for name in ("tokens.css", "components.css", "screens.css"):
        css = _webui(name)
        assert "line-height: 1.7" not in css, name
        assert "line-height: 1.8" not in css, name
    # 消费面归配方（散写清账的代表位）
    components = _webui("components.css")
    assert ".note { color: var(--ink-faint); font: var(--t-note); }" \
        in components
    assert ".state-banner { color: var(--ink-faint); font: var(--t-note); }" \
        in components
    screens = _webui("screens.css")
    assert "font: var(--t-ui); color: var(--pencil);" in screens
    assert "pre { font: var(--meta-mono);" in screens


def test_the_typography_spec_section_carries_the_assignment() -> None:
    """spec ②-4a 的应用规范表 + ⑨-14 登记节在场。"""

    spec = (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    assert "#### ②-4a 排印配方与全局应用规范（fr-A 体系化）" in spec
    assert "| ① 标题层级（display 族，400" in spec
    assert "| ② 正文文档档（serif 族） |" in spec
    assert "| ③ 界面档（UI sans 族） |" in spec
    assert "| ④ 微标签与 mono 数字档 |" in spec
    assert "新规则一律 `font: var(--t-*)`" in spec
    assert "### 9.14 fr-A 修订登记" in spec
    # ②-6 的豁免集合在法则自己的家里登记（原始法则句一字保留；veto-R
    # 随迁：回底墨点豁免退役，登记句改写为退役记录）
    assert "圆角 v2 收窄一档：信纸物件 ≤2px，仅邮票/邮戳圆形" in spec
    assert "**fr-A 豁免新增一席（2026-10-05" in spec
    assert "veto-R 退役" in spec
    assert "回到「仅邮票/邮戳" in spec
    # ②-5 指向配方（不重列）
    assert "排印配方 `--t-*` 九枚与四族应用规范见 **②-4a**" in spec


def test_the_native_select_is_retired_and_the_ink_select_is_registered() -> None:
    """墨选：原生 <select> 全应用退役（零 createElement("select")）；#27
    契约块 + aria/键盘/点外关闭全链；消费面（fr-A 三面 + veto-R 扩面：
    教学模式四档 + 七钮档位化——自由文本框退役）。"""

    app = _webui("app.js")
    assert 'createElement("select")' not in app
    assert "selectField({" in app
    assert "name: \"目标 \" + (index + 1) + \" · 技能\"," in app
    assert 'onChange: (next) => { goal.goal_modality = next; },' in app
    assert 'onChange: (next) => { policyEditor[name] = next; },' in app
    assert 'onChange: (next) => { rule.disclosure_level = next; },' in app
    assert 'onChange: (next) => { saveMode(next); },' in app
    assert "select.root" in app
    # 工厂对象不是 Node——进 DOM 必须经 root（fr-A 活体自查抓到的
    # appendChild 类型错，此钉为该错类的结构守卫；veto-R 七钮直取
    # .root 同法）
    assert ".root;" in app
    assert "box.appendChild(fieldRow(label, node));" in app
    assert "edge.appendChild(fieldRow(\"目标 \" + (index + 1) + \" · 技能\"," in app
    components = _webui("components.js")
    assert "export function selectField(opts) {" in components
    assert 'button.setAttribute("aria-haspopup", "listbox");' in components
    assert 'list.setAttribute("role", "listbox");' in components
    assert 'optionEl.setAttribute("role", "option");' in components
    assert 'button.setAttribute("aria-activedescendant",' in components
    assert 'event.key === "Escape"' in components
    assert 'event.key === "ArrowDown" || event.key === "ArrowUp"' in components
    assert 'event.key === "Tab"' in components
    assert 'document.addEventListener("pointerdown", onOutside, true);' \
        in components
    assert 'check.textContent = "✓";' in components
    # ⑩ 10.3 互斥：换空间 / 升写作态 / 开沓都收开着的墨选（活体自查发
    # 现「切空间后浮层留着」——同一手势只产一个效果的纪律）
    assert "export function closeOpenSelects() {" in components
    assert "const openSelects = new Set();" in components
    assert "openSelects.add(api);" in components
    assert "openSelects.delete(api);" in components
    app = _webui("app.js")
    assert "  closeOpenSelects();" in app
    # fr-B 随迁：互斥收卡改 skipOut 直摘（词卡褪下半的动画路径只属
    # 用户三路径——Esc/收起/点卡外）
    assert "  closeWordCard({ skipOut: true });\n  closeOpenSelects();" in app
    css = _webui("components.css")
    assert "27. select（墨选，fr-A）" in css
    assert "color-mix(in srgb, var(--ink) 8%, transparent)" in css
    assert "scrollbar-gutter: stable; }" in css
    # provider 刀随迁——开单浮层化（用户否决「选项被遮挡」）：开单时列表
    # 过继 body + position: fixed 对齐锚钮（绝对定位原形态会被滚动祖先
    # 的 overflow 裁切框拦腰截断），关单归位；任何祖先滚动/窗口缩放即关。
    assert "function floatList() {" in components
    assert "function unfloatList() {" in components
    assert 'list.classList.add("select-list--float");' in components
    assert "document.body.appendChild(list);" in components
    assert 'list.classList.remove("select-list--float");' in components
    assert "root.appendChild(list);   // 归位" in components
    assert "window.addEventListener(\"scroll\", onAnyScroll, true);" \
        in components
    assert ".select-list--float { position: fixed; z-index: 10; }" in css
    # 选项双列层级（用户否决「选项层级不合理」）：中文主列 + 原词弱墨辅列
    assert "select-sub" in components
    assert ".select-option .select-sub" in css
    # 自查六：合起态恢复原词常显（双列改造曾挤掉）——主读法 + 弱墨等宽
    assert 'subSpan.className = "select-value-sub";' in components
    assert ".select-value-sub" in css
    spec = (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    assert "| 27 | select |" in spec
    assert "| 24 | flow-bottom |" in spec
    assert "| 25 | flow-ruler |" in spec
    assert "| 26 | tokenmeter |" in spec
