"""veto-R — the user's dogfood first-verification veto, five feedback
groups plus two follow-up faces, over the real web server and the
production assembly.

Authorization: the veto adjudication ``DEC-OPI-b2e889bd-…11`` (R1–R9) + the
second-round revision (④ widened to the whole app + the two new faces) + the
slice ``VAL-…13`` + the task book ``TASK-…15``. The nine faces:

1. **mode becomes page-movable** (the only deep src change): migration
   0022's generic ``app_setting`` table + ``POST /api/settings/mode``
   (four-word whitelist, case-sensitive) → persist + hot-swap the live
   wiring via ``dataclasses.replace`` — the next turn decides under the new
   tier with no reassembly; ``open_host``'s read order is explicit launch
   argument > persisted word > ``None`` (fail-closed untouched); the gate
   functions are untouched. The E2E four states: no CLI no persisted ⇒
   DENY; POST Study-first ⇒ the next error text opens a moment; a reopen
   without CLI reads the persisted tier; an explicit CLI Lounge overrides
   the persisted Study-first for that process;
2. the seven unconsumed §5.1 knobs become ink-select tiers (the
   display-layer ``KNOB_TIERS`` vocabulary — the store stays a shelf:
   whatever string is picked is stored verbatim, ``null`` = 未配置 kept
   honest); the badge reads「暂不影响行为」;
3. user-facing words are Chinese-first (the frequency four, the disclosure
   ladder with no English suffix, the four mode tier names; machine ids
   never surface as display words);
4. the drawer pages (and, per the widened revision, the whole app) follow
   one display spec — spec ⑨-15's ten surface families + the data-first
   law (A-0);
5. the data-first copy trims (the meter, the flow calibre line, the obs
   summary, the letters calibre, the display toggle);
6. the token meter becomes a compact pill on the dock's top edge + a
   per-turn popup in the overlay family (no sticky layer, no empty-state
   sentence — no reading, no pill);
7. the envelope stack's exit animation is directional (``paper-retract``,
   no scale — the large-container law), ``paper-fold`` narrowed to small
   cards;
8. the flow-bottom button rejoins the button family (paper + hairline +
   glyph +「回到底」; the circle and its ②-6 exemption retire);
9. the turn ruler binds one-to-one to the flowTurns anchors (rAF-throttled
   passive scroll accounting; the click lands on the anchor).
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
from elc.persona.provider import ProviderOutput, ScriptedPersonaProvider
from elc.platform.db.app_settings import APP_SETTING_ROLLOUT_STAGE_KEY
from elc.teaching.rollout import ROLLOUT_STAGES, RolloutStage
from tests.host.test_w1_web import (
    ERROR_TEXT,
    _page_source,
    seed_online,
    web_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = REPO_ROOT / "src" / "elc" / "webui"
SPEC = REPO_ROOT / "docs" / "FRONTEND_SPEC.md"
MIGRATIONS = REPO_ROOT / "migrations"

#: The 0022 file itself names no stage and seeds no row (the P8-5 law —
#: this pin keeps the migration honest on that exact point).
MIGRATION_0022 = MIGRATIONS / "0022_app_settings.sql"


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("veto-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


# ---------------------------------------------------------------------------
# 1. the mode write end to end — the E2E four states + the grammar


def test_denied_without_stage_then_open_after_the_mode_write(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """E2E states 1+2: no CLI no persisted ⇒ DENY (the fail-closed default
    is untouched); POST Study-first ⇒ the very next turn opens the moment —
    the hot swap moved the live wiring, no restart."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db, seed=seed_online
    ) as stack:
        status, before = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200, before
        assert before["teaching_moments"] == []
        # the grammar's happy path: 200 + accepted + the word back
        status, saved = stack.post(
            "/api/settings/mode", {"stage": "Study-first"}
        )
        assert status == 200, saved
        assert saved["accepted"] is True and saved["idempotent"] is False
        assert saved["stage"] == "Study-first"
        # the read answers from the live wiring now
        status, read = stack.get_json("/api/settings")
        assert read["rollout_stage"] == "Study-first"
        # the next turn decides under the new tier — no reassembly
        status, after = stack.post("/api/turn", {"text": ERROR_TEXT})
        assert status == 200, after
        (moment,) = after["teaching_moments"]
        assert moment["focus_target_id"] == "res-discourse-anyway"


def test_the_persisted_tier_survives_a_reopen_without_cli(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """E2E state 3: the word is durable — a reopen that declares nothing
    reads the page's tier (and the live wiring carries it)."""

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db, content_db=pilot_content_db, seed=seed_online
    ) as stack:
        status, saved = stack.post(
            "/api/settings/mode", {"stage": "Study-first"}
        )
        assert status == 200 and saved["accepted"] is True, saved
    with web_stack(app_db, content_db=pilot_content_db) as stack:
        status, read = stack.get_json("/api/settings")
        assert status == 200, read
        assert read["rollout_stage"] == "Study-first"
        host = stack.box["host"]
        wiring = host.coordinator.automatic_teaching_wiring()
        assert wiring is not None
        assert wiring.rollout_stage == RolloutStage.STUDY_FIRST
        # the Host field is the open-time snapshot of the same read order
        assert host.rollout_stage == RolloutStage.STUDY_FIRST


def test_the_explicit_cli_stage_overrides_the_persisted_word(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """E2E state 4: the launch declaration wins for its own process — and
    the persisted word is untouched by merely opening (only the page's
    write moves it), so the next bare reopen reads Study-first again."""

    app_db = tmp_path / "app.db"
    with web_stack(
        app_db, content_db=pilot_content_db, seed=seed_online
    ) as stack:
        status, saved = stack.post(
            "/api/settings/mode", {"stage": "Study-first"}
        )
        assert status == 200 and saved["accepted"] is True, saved
    with web_stack(
        app_db,
        content_db=pilot_content_db,
        stage=RolloutStage.LOUNGE,
    ) as stack:
        status, read = stack.get_json("/api/settings")
        assert read["rollout_stage"] == "Lounge"
        host = stack.box["host"]
        wiring = host.coordinator.automatic_teaching_wiring()
        assert wiring is not None
        assert wiring.rollout_stage == RolloutStage.LOUNGE
        assert host.rollout_stage == RolloutStage.LOUNGE
    with web_stack(app_db, content_db=pilot_content_db) as stack:
        _, read = stack.get_json("/api/settings")
        assert read["rollout_stage"] == "Study-first"


def test_the_mode_grammar_is_fail_closed(tmp_path: Path) -> None:
    """The four §12 words, case-sensitive; a body that is not the one-key
    shape is a refusal — and nothing is persisted by any refused body."""

    with web_stack(tmp_path / "app.db") as stack:
        refusals: list[Any] = [
            {"stage": "study-first"},      # case
            {"stage": "study_first"},      # spelling
            {"stage": "Study-First"},      # case again
            {"stage": "Balanced "},        # no trimming
            {"stage": "manual"},           # not the word (the slash form is)
            {},                            # missing key
            {"stage": "Study-first", "x": 1},   # extra key
            {"mode": "Study-first"},       # the old body shape
            "not an object",
        ]
        for body in refusals:
            status, answer = stack.post("/api/settings/mode", body)
            assert status == 400, (body, answer)
            assert "need a JSON body" in answer["error"], (body, answer)
        # nothing was written by any refused body
        status, read = stack.get_json("/api/settings")
        assert read["rollout_stage"] is None


def test_the_same_word_twice_is_an_honest_replay(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The replay (the persisted word already equals the request, and the
    live wiring already carries it) answers ``idempotent`` and writes
    nothing — the version-churn posture the other writes keep."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_online,
    ) as stack:
        status, first = stack.post(
            "/api/settings/mode", {"stage": "Balanced"}
        )
        assert status == 200 and first["accepted"] is True, first
        assert first["idempotent"] is False
        status, second = stack.post(
            "/api/settings/mode", {"stage": "Balanced"}
        )
        assert status == 200, second
        assert second["accepted"] is True
        assert second["idempotent"] is True


def test_the_prep1_tier_refuses_the_mode_write_honestly(
    tmp_path: Path,
) -> None:
    """No automatic leg ⇒ 200 + accepted false (the honest sentence), and
    nothing persisted — a write with nothing to move would only fork the
    next open's tier from this process's truth."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, answer = stack.post(
            "/api/settings/mode", {"stage": "Study-first"}
        )
        assert status == 200, answer
        assert answer["accepted"] is False
        assert "没装配自动教学腿" in answer["error"]
    with web_stack(app_db) as stack:
        _, read = stack.get_json("/api/settings")
        assert read["rollout_stage"] is None


def test_the_mode_words_ride_server_declared(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The GET carries the four §12 words (the page copies no word list) —
    read from the enum, not copied."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        _, read = stack.get_json("/api/settings")
        assert read["mode_words"] == [stage.value for stage in ROLLOUT_STAGES]


def test_the_reader_ignores_an_unparseable_persisted_word(
    tmp_path: Path,
) -> None:
    """Fail-closed degradation: a corrupt stored word reads as absent —
    the reader never guesses a stage into being, never crashes the open."""

    db_path = tmp_path / "app.db"
    provider = ScriptedPersonaProvider(
        script=(ProviderOutput(text="ok"),)
    )
    host = open_host(db_path, provider=provider)
    host.app_settings.set(APP_SETTING_ROLLOUT_STAGE_KEY, "Study~First")
    host.close()
    reopened = open_host(db_path, provider=provider)
    try:
        assert reopened.rollout_stage is None
        assert (
            reopened.app_settings.get(APP_SETTING_ROLLOUT_STAGE_KEY)
            == "Study~First"
        )
    finally:
        reopened.close()


def test_the_setting_store_upserts_one_row_per_key(tmp_path: Path) -> None:
    """The store's two faces: absence is ``None``; a second ``set`` leaves
    exactly one row with the newest word (upsert, not append)."""

    db_path = tmp_path / "app.db"
    provider = ScriptedPersonaProvider(script=(ProviderOutput(text="ok"),))
    host = open_host(db_path, provider=provider)
    try:
        store = host.app_settings
        assert store.get(APP_SETTING_ROLLOUT_STAGE_KEY) is None
        store.set(APP_SETTING_ROLLOUT_STAGE_KEY, "Balanced")
        store.set(APP_SETTING_ROLLOUT_STAGE_KEY, "Lounge")
        assert store.get(APP_SETTING_ROLLOUT_STAGE_KEY) == "Lounge"
        rows = host.db.execute(
            "SELECT COUNT(*) FROM app_setting"
        ).fetchone()
        assert rows is not None and int(rows[0]) == 1
    finally:
        host.close()


def test_the_migration_names_no_stage_and_seeds_no_row() -> None:
    """The P8-5 law holds at the new head: 0022 carries no stage word and
    no seed row — absence is the honest "not chosen yet"."""

    text = MIGRATION_0022.read_text(encoding="utf-8")
    assert "CREATE TABLE app_setting" in text
    assert "INSERT INTO app_setting" not in text
    for word in ("Study-first", "Balanced", "Lounge", "manual/user"):
        assert word not in text, word
    conn = sqlite3.connect(":memory:")
    from elc.platform.db import migrations as migrations_mod

    migrations_mod.apply_migrations(conn)
    count = conn.execute("SELECT COUNT(*) FROM app_setting").fetchone()
    assert count is not None and int(count[0]) == 0
    conn.close()


# ---------------------------------------------------------------------------
# 2. the seven knobs become tiers (the display layer declares, the store
#    stays a shelf)


def test_the_knob_tiers_are_a_display_layer_declaration() -> None:
    """``KNOB_TIERS`` covers the seven unpinned knobs with 2–4 tiers each,
    declared display-layer (the comment says so) — and the served page
    renders them through the ink select with 未配置 (null) kept honest."""

    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "const KNOB_TIERS = {" in app
    assert "display-layer" in app
    for name in (
        "interruption_budget",
        "curriculum_initiative",
        "correction_strictness",
        "hint_policy",
        "assessment_visibility",
        "practice_density",
        "persona_freedom",
    ):
        assert f"{name}: [" in app, name
    # the select takes an explicit 未配置 option (null = the column's own
    # honesty) and the free-text box is gone
    assert '{ value: null, label: "未配置" },' in app
    assert "未配置（留空 = 清除）" not in app
    # the badge says what the seven knobs honestly are now
    assert 'badge.textContent = "暂不影响行为";' in app


def test_a_picked_tier_is_stored_verbatim(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The store is a shelf: whatever the display layer handed over (a
    Chinese tier phrase) comes back byte-equal through the same GET — no
    vocabulary lives server-side for these columns."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=seed_online,
    ) as stack:
        _, before = stack.get_json("/api/settings")
        knobs = {
            name: ("密" if name == "practice_density" else None)
            for name in before["writable_knobs"]
        }
        knobs["teaching_frequency"] = "EAGER"
        status, saved = stack.post(
            "/api/settings/teaching_policy", knobs
        )
        assert status == 200 and saved["accepted"] is True, saved
        _, after = stack.get_json("/api/settings")
        assert after["teaching_policy"]["practice_density"] == "密"


# ---------------------------------------------------------------------------
# 3. the words are Chinese-first


def test_the_frequency_and_disclosure_words_are_chinese_first() -> None:
    """存值枚举词不变、显示面中文：the frequency four wear the veto's
    words (关/偶尔/适度/勤快), the disclosure select drops the English
    suffix, and the chip factory demotes the raw word to a title."""

    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert 'OFF: "关",' in app
    assert 'MINIMAL: "偶尔",' in app
    assert 'BALANCED: "适度",' in app
    assert 'EAGER: "勤快",' in app
    # the settings select shows the Chinese reading only (unknown words
    # pass through raw — no invented fallback)
    assert "label: FREQUENCY_CN[word] || word," in app
    # the disclosure select lost its " · "+word suffix
    assert "label: DISCLOSURE_CN[word] || word," in app
    assert '(DISCLOSURE_CN[word] ? DISCLOSURE_CN[word] + " · " : "")' not in app
    # the mode select wears the Chinese tier names; the enum words are the
    # stored values
    assert '"manual/user-initiated": "手动（用户发起）",' in app
    assert '"Study-first": "学习优先",' in app
    assert '"Balanced": "平衡",' in app
    assert '"Lounge": "娱乐 · 关系优先",' in app
    # the chip factory: Chinese only on the face, the raw word in title
    components = (WEBUI / "components.js").read_text(encoding="utf-8")
    assert 'el.textContent = String(options.cn);' in components
    assert 'el.title = String(word);' in components
    assert 'en.className = "rawtag";' not in components


def test_the_machine_ids_never_surface_as_display_words(tmp_path: Path) -> None:
    """The disclosure rule row prefers the roster's name; the raw id rides
    as the meta tag, never as the main word (the roster-less fallback is
    the honest last resort, unchanged)."""

    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "const name = personaNameOf(rule.persona_id);" in app
    assert 'tag.textContent = rule.persona_id;' in app


# ---------------------------------------------------------------------------
# 4. the drawer pages follow the one display spec (the widened ④)


def test_the_drawer_pages_follow_the_unified_template() -> None:
    """每 tabpanel = 一行导语（.doc-line）+ 节块（h3 + .doc-line + 控件
    + 空态 .note）：记忆页的四条 .sub 导语全部换 .doc-line；设置页
    panel-grid 取消、导语升节前一行；隐私页已合规（模板出处）。"""

    index = (WEBUI / "index.html").read_text(encoding="utf-8")
    memory = index.split('id="drawer-memory"', 1)[1].split(
        'id="drawer-privacy"', 1)[0]
    assert '<p class="doc-line">笔友记住的事都在这里——分三摞收纳。</p>' in memory
    assert memory.count('class="doc-line"') == 4
    assert 'class="sub">笔友记住的' not in memory
    settings = index.split('id="drawer-settings"', 1)[1].split(
        "<nav id=\"navdock\"", 1)[0]
    assert "panel-grid" not in settings
    assert ('<p class="doc-line">这台应用只服务你一个人'
            "（127.0.0.1，无账号无密码）。</p>") in settings
    assert "<h3>如实说</h3>" in settings
    privacy = index.split('id="drawer-privacy"', 1)[1].split(
        'id="del-result"', 1)[0]
    assert '<p class="doc-line">请笔友忘掉一些事——走出去就找不回来。</p>' \
        in privacy
    # the today grid is the one survivor (「两块并列同权」)
    assert index.count('class="panel-grid"') == 1


def test_the_spec_carries_the_unified_display_chapter() -> None:
    """spec ⑨-15：A 全应用统一规范（数据优先原则 A-0 + 十表面族 A-1）
    + B 本刀九面登记；⑩ 10.2 的计量粒行随迁。"""

    spec = SPEC.read_text(encoding="utf-8")
    assert "### 9.15 veto-R 修订登记" in spec
    assert "#### A. 全应用文字显示与组件统一规范（现役法则）" in spec
    assert "**A-0 数据优先原则" in spec
    assert "**A-1 十表面族统一模板**" in spec
    for family in ("**门厅**", "**案头**", "**温故 / 抽屉**", "**信封沓四脸**",
                   "**词卡**", "**教学卡**", "**确认窗**", "**全页纵深**",
                   "**浮层家族**", "**按钮族**"):
        assert family in spec, family
    assert "W-1-0 世界设置复用\n   同表，其迁移号顺延 0023" in spec


def test_the_data_first_trims_hold() -> None:
    """面⑤的逐面排查（读数自明的面砍成数据或最短词）：计量条空态句
    退役、信流口径行尾收短、观察摘要收短、信档口径句收短、显示开关句
    收短、记忆页导语收短。"""

    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    index = (WEBUI / "index.html").read_text(encoding="utf-8")
    assert "还没有计量读数" not in app
    assert " 往前翻。" in app
    assert "翻到头为止" not in app
    assert "更早的信没有了。" in app
    assert "行读数摊在下面" not in app
    assert "门规漂移 " in app
    assert "第 n 封按窗口顺序数。" in index
    assert "只活在当前标签页，关掉就复位" in index
    assert "sessionStorage 客户端侧" not in index
    assert "一条条如实" not in index


# ---------------------------------------------------------------------------
# 5./6. the meter pill + its popup


def test_the_meter_pill_lives_on_the_dock_top_edge() -> None:
    """#26 重铸：dock 上沿内嵌（DOM 序在触发条之前、absolute 贴上沿）；
    sticky 独立层退役（screens 只留登记注释）；明细浮层 = fixed z 10 +
    gutter（⑨-6a 纪律清单同刀入册）。"""

    index = (WEBUI / "index.html").read_text(encoding="utf-8")
    assert index.index('id="tokenmeter"') < index.index('id="dock-trigger"')
    assert 'class="tokenmeter" type="button"' in index
    components = (WEBUI / "components.css").read_text(encoding="utf-8")
    assert ".tokenmeter { position: absolute; top: -13px;" in components
    assert ".tm-pop { position: fixed; z-index: 10;" in components
    assert "scrollbar-gutter: stable" in components[
        components.index(".tm-pop {"):components.index(".tm-pop .tm-pop-head")
    ]
    screens = (WEBUI / "screens.css").read_text(encoding="utf-8")
    assert ".tokenmeter { position: sticky" not in screens
    assert "sticky 层位账退役" in screens


def test_the_meter_popup_joins_the_overlay_family() -> None:
    """⑩ 互斥收：开本浮层先收墨选/词卡/沓；反向（showSpace / 开沓 /
    升写作态）收本浮层；Esc + 点外双路在册。无读数不现位。"""

    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "function toggleTokenMeterPop() {" in app
    assert "function closeTokenMeterPop() {" in app
    block = app[app.index("function toggleTokenMeterPop()"):app.index(
        "function syncFlowMeter")]
    assert "closeOpenSelects();" in block
    assert "closeWordCard({ skipOut: true });" in block
    assert "closeEnvelopeSelector();" in block
    # the reverse directions close the popup
    assert "closeTokenMeterPop();   // ⑩ 互斥：开沓先收计量明细浮层" in app
    show_space = app[app.index("function showSpace(name)"):app.index(
        "wireNavdock((name)")]
    assert "closeTokenMeterPop();" in show_space
    # Esc + outside click, the envsel-family shape
    assert "function tokenMeterEsc(event) {" in app
    assert 'event.key === "Escape"' in app
    assert "function tokenMeterOutside(event) {" in app
    # no reading, no pill (the empty-state sentence retired with the strip)
    assert "tokenMeterTotal()" in app
    # F-1 处置钉（评审 m8 NOT-RED）：show 条件必须由 total !== null 把门——
    # 无读数时粒隐藏（显示 "0" 不算隐藏）；删此条件即红。
    assert "total !== null" in app
    assert "还没有计量读数" not in app


# ---------------------------------------------------------------------------
# 7. the stack's exit is directional


def test_the_large_container_exit_never_scales() -> None:
    """面⑦：.envsel--fold = paper-retract（方向性位移+淡化，无缩放）；
    paper-fold 收窄为小卡专用（词卡/确认窗/dock 落半/navdock 让位保留）；
    法则句入 ⑨-5；animationend 对账随名。"""

    screens = (WEBUI / "screens.css").read_text(encoding="utf-8")
    fold = screens[screens.index(".envsel--fold {"):]
    fold = fold[:fold.index("}") + 1]
    assert "paper-retract var(--dur-panel-out) var(--ease-exit)" in fold
    assert "scale" not in fold
    assert "ink-wash calc(var(--dur-panel-out) * 1.3)" in fold
    components = (WEBUI / "components.css").read_text(encoding="utf-8")
    assert "@keyframes paper-retract {" in components
    retract = components[components.index("@keyframes paper-retract {"):
                         components.index("@keyframes page-turn")]
    assert "translateY(-8px)" in retract
    assert "scale" not in retract
    # the small cards keep the fold (the narrowed consumer face)
    assert ".word-card--out { animation: paper-fold var(--dur-panel-out)" \
        in components
    assert ".cfrm--out { animation: paper-fold var(--dur-panel-out)" \
        in components
    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    close_body = app[app.index("function closeEnvelopeSelector(opts)"):]
    close_body = close_body[:close_body.index("function unfoldToParlor")]
    assert 'event.animationName === "paper-retract"' in close_body
    spec = SPEC.read_text(encoding="utf-8")
    assert "大容器退场禁整体缩放" in spec
    assert "`paper-retract`" in spec


# ---------------------------------------------------------------------------
# 8. the flow-bottom button rejoins the button family


def test_the_flow_bottom_button_is_a_paper_button() -> None:
    """面⑧：纸底 + 发丝线 + 墨线图标 +「回到底」字标；圆角豁免退役
    （豁免集合回到「仅邮票/邮戳圆形」，普查 13 → 11）；显隐语义与
    平滑回底、reduced-motion 全保留。"""

    index = (WEBUI / "index.html").read_text(encoding="utf-8")
    assert 'class="flow-bottom-word">回到底</span>' in index
    assert 'aria-label="回到最新一封"' not in index
    components = (WEBUI / "components.css").read_text(encoding="utf-8")
    block = components[components.index("/* ── 24. flow-bottom"):
                       components.index("/* ── 25. flow-ruler")]
    assert "background: var(--paper-high)" in block
    assert "border: 1px solid var(--rule)" in block
    assert "border-radius" not in block
    assert "圆形豁免退役" in block
    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "const FLOW_BOTTOM_THRESHOLD = 240;" in app
    assert 'behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });' in app
    spec = SPEC.read_text(encoding="utf-8")
    assert "回到「仅邮票/邮戳" in spec


def test_the_radius_census_sits_at_the_new_terminal() -> None:
    """圆角普查：components 7 + screens 4（fr-A 墨点两枚随形态退役）；
    spec ②-6 的退役登记在法则自己的家里。"""

    components = (WEBUI / "components.css").read_text(encoding="utf-8")
    screens = (WEBUI / "screens.css").read_text(encoding="utf-8")
    assert components.count("border-radius") == 7
    assert screens.count("border-radius") == 4
    assert components.count("border-radius: 50%") == 6
    spec = SPEC.read_text(encoding="utf-8")
    assert "veto-R 退役" in spec


# ---------------------------------------------------------------------------
# 9. the ruler binds to the anchors one-to-one


def test_the_ruler_binds_one_tick_per_turn_anchor() -> None:
    """面⑨：刻度点 ↔ flowTurns 一一绑定（buildFlowRuler 逐一生成）；
    高亮按真实锚点位置计算（rect 量位 + 视位线 = 顶栏之下一档呼吸，
    与点击落点同一条线）；scroll 对账 = rAF 节流的被动 listener；点击
    精确滚到该轮锚点。"""

    app = (WEBUI / "app.js").read_text(encoding="utf-8")
    assert "function buildFlowRuler() {" in app
    build = app[app.index("function buildFlowRuler()"):app.index(
        "function renderFlowCalibre")]
    assert "flowTurns.forEach((turn, i) => {" in build
    assert 'tick.setAttribute("aria-label", "第 " + (i + 1) + " 轮");' in build
    assert 'tick.addEventListener("click", () => scrollToFlowTurn(i));' in build
    # the highlight is anchor-measured, on the same line the click lands
    spy = app[app.index("function flowSpyTick()"):app.index(
        "function scrollToFlowTurn")]
    assert "getBoundingClientRect().top" in spy
    assert "const line = window.scrollY + FLOW_TURN_OFFSET;" in spy
    assert "const FLOW_TURN_OFFSET = 72;" in app
    # the scroll accounting is throttled (one measurement per frame) and
    # the listener stays passive
    assert "function scheduleFlowRulerSync() {" in app
    sched = app[app.index("function scheduleFlowRulerSync()"):app.index(
        "function flowSpyTick()")]
    assert "requestAnimationFrame(() => {" in sched
    assert ('window.addEventListener("scroll", scheduleFlowRulerSync, '
            "{ passive: true });") in app
    # the click alignment: the anchor's top lands on the sight line
    jump = app[app.index("function scrollToFlowTurn"):app.index(
        "function syncFlowRuler()")]
    assert "window.scrollY -\n    FLOW_TURN_OFFSET;" in jump


def test_the_served_page_carries_the_new_faces(tmp_path: Path) -> None:
    """The served union (the shell over real HTTP) carries the nine faces'
    load-bearing words — one page, one truth."""

    with web_stack(tmp_path / "app.db") as stack:
        page = _page_source(stack)
    assert "回到底" in page
    assert "const MODE_CN = {" in page
    assert "const KNOB_TIERS = {" in page
    assert "暂不影响行为" in page
    assert "未声明——自动教学关着" in page
    assert "/api/settings/mode" in page
    assert "paper-retract" in page
    # the vetoed forms are gone from the whole served union
    assert "存面（暂无消费）" not in page
    assert "由启动命令给定，这里读得到，但不能改。" not in page
