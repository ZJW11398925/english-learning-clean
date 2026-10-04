"""R-1 — the shell rebuilt: 门厅 + three spaces + the dock.

The R program's first cut (blueprint ⑧): the five screens re-form into a
vestibule plus three spaces, the dock (#18) is the only way between
spaces, and the study and the drawer each hold three sections behind
real tablists (#20) with space headers (#19). The old shell's remains
are pinned absent (the p-3 precedent): no toggles on the parlor bar, no
ways back, no setlinks row, no 仪表 screen. The migration is pure
regrouping — every panel id the older suites pin survives untouched.

Groups (the task book's own):

1. the shell — the vestibule and the three spaces exist, every old
   screen id and nav control is absent, and the panel-level ids survive;
2. the dock (#18) — three items with their data-space wiring, the fixed
   bottom form over the safe area, the active mark, the layout tokens
   (body padding, the composer's offset), and the z-order law (the
   word-card overlay floats above the dock);
3. the section tabs (#20) — two tablists with the full ARIA wiring
   (tablist/tab/tabpanel, aria-selected, aria-controls/labelledby), the
   roving tabindex and the left/right arrows, both wired in app.js;
4. the space headers (#19) — the two space-headers ride the .top base
   with a section-name slot; the parlor keeps its own bar, linkless;
5. the default-section law — entering the study lands 今日, entering
   the drawer lands 记忆, and each section's entry is its pull by name
   (settings pulls its own three-face read since 主线-1 — the absence
   pin's truth migrated, DEC-OPI-76a0a10a-….30);
6. the settings honesty — the drawer's settings section is a real
   control surface since 主线-1 (the placeholder era's negatives stay:
   no promise word anywhere);
7. the registration — the three shell components are pinned the
   word-card way (the R-1 review's disposition: spec rows, css contract
   blocks, js factories, single-source selectors, and the dock's
   aria-current that a mutation once deleted green).

Every page-source pin reads the served union (the F-G1 reading).
"""

from __future__ import annotations

from pathlib import Path

import elc.web
from tests.host.test_w1_web import _page_source, web_stack

WEBUI = Path(elc.web.__file__).parent / "webui"


def _page_of(tmp_path: Path) -> str:
    """The served page source over the plain offline stack."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. the shell


def test_the_shell_is_a_vestibule_and_three_spaces(tmp_path: Path) -> None:
    """门厅 + 客厅 + 温故 + 抽屉（rd-2 空间词，原学案/柜抽）exist; the
    four old screen ids are gone;
    and every panel-level id the older suites pin survived the regrouping
    untouched (纯重组零语义丢失)."""

    page = _page_of(tmp_path)
    for space in ("screen-onboard", "space-parlor", "space-study",
                  "space-drawer"):
        assert f'id="{space}"' in page, space
    for gone in ("screen-living", "screen-today", "screen-goal",
                 "screen-set"):
        assert f'id="{gone}"' not in page, gone
    for panel in (
        "today-action", "growth-summary", "today-practice",
        "goal-editor", "goal-weights", "goal-assessment",
        "goal-register", "goal-frequency", "goal-taxref", "goal-result",
        "record-book", "raw-readings", "obs-entry",
        "learn-schedule", "learn-goals", "learn-evidence",
        "archive-board", "plan-line", "plan-slot", "plan-detail",
        "book-slot", "book-detail",
        "mem-relationship", "mem-episode", "mem-states", "mem-evidence",
        "mem-tombstones", "del-targets", "del-result",
        "set-memory", "set-privacy",
        # v2-2 随迁：obsout/obs-status 随观察读数迁入专门面退役
        # （8.2.12 观察仪表屏——档案折叠内只留入口 obs-entry）；
        # 信档/观察两屏的骨架 id 在场（8.2.11/8.2.12 结构重铸件）
        "space-letters", "letters-board", "letters-datestamp",
        "space-obs", "obs-board", "obs-summary",
    ):
        assert f'id="{panel}"' in page, panel
    for retired_panel in ("obsout", "obs-status"):
        assert f'id="{retired_panel}"' not in page, retired_panel
    # rd-3 随迁（9.11-22 移走清单）：诊断五板与「为什么 · 原值」随
    # 用户面零渲染退役（缺位钉）；旧今日三块里 today-due / today-recent
    # 随收拢退役；today-summary 摘要行退役；set-diagnostics / set-
    # learning 两个节容器随之退役
    for gone in (
        "why-teach", "why-not-teach", "why-evidence", "why-support",
        "why-degraded", "diag-raw", "set-diagnostics", "set-learning",
        "today-due", "today-recent", "today-summary",
    ):
        assert f'id="{gone}"' not in page, gone
    # R-1R 退役（⑧ 8.2.4 读写合一 / 进节即拉取代刷新钮 / 观察读数第一
    # 次展开才拉）：三个面板 id 与六个拉取钮 id 的缺位钉
    for gone in (
        "goal-list", "target-list", "obs",
        "today-refresh", "learning-refresh", "diag-refresh",
        "mem-refresh", "goal-refresh",
    ):
        assert f'id="{gone}"' not in page, gone


def test_the_old_nav_controls_are_all_gone(tmp_path: Path) -> None:
    """The old shell's control face, pinned absent: the three toggles and
    the five ways back/over, the topactions slot, the setlinks row and
    its expansion loop."""

    page = _page_of(tmp_path)
    for gone in ("today-toggle", "goal-toggle", "meter-toggle",
                 "today-set", "goal-set", "back-from-today",
                 "back-from-goal", "back-to-living"):
        assert f'id="{gone}"' not in page, gone
    assert "topactions" not in page
    assert "toggleSetBlock" not in page
    assert "data-block" not in page
    assert "setlinks" not in (WEBUI / "index.html").read_text(
        encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. the dock (#18)


def test_the_navdock_is_the_only_way_between_spaces(tmp_path: Path) -> None:
    """The dock: exactly three items (案头/温故/抽屉——v2-1R 品牌更名后
    旧空间词「客厅」退役) with their data-space
    wiring, the app-side wiring, and the fixed bottom form — hairline top
    edge, paper ground, the safe area in its own padding."""

    index = _text("index.html")
    assert '<nav id="navdock" class="navdock" aria-label="空间">' in index
    for space in ("parlor", "study", "drawer"):
        assert f'class="navdock-item" data-space="{space}"' in index
    # v3-a 随迁（落墨页签）：每项 = 图标插槽 + 文字标签同钮——文字行
    # 语义由标签承担（图标永不单独承担语义），三条签行逐字在册。
    for label in (">案头</span></button>", ">温故</span></button>",
                  ">抽屉</span></button>"):
        assert label in index
    for glyph in ("data-icon=\"desk\"", "data-icon=\"revisit\"",
                  "data-icon=\"drawer\""):
        assert glyph in index
    app = _text("app.js")
    assert "wireNavdock((name) => showSpace(name));" in app
    assert "markNavdock(name);" in app
    # the vestibule stands the dock down (the door button is the way in)
    assert 'document.getElementById("navdock").hidden = name === "onboard";' \
        in app
    css = _text("components.css")
    assert css.count("\n.navdock {") == 1
    assert (
        ".navdock { position: fixed; left: 0; right: 0; bottom: 0;"
        " z-index: 6;" in css
    )
    assert "border-top: 1px solid var(--rule);" in css
    # v3-a 随迁（N-A 落墨页签 + 令牌账定谳）：垫条材质与写信区垫板同族
    # （--paper-high 顶纸）；上下 padding 从 --navdock-h 反推——实高恒
    # 等于令牌（历史 54/57 的 3px 账实差与 dock 盖线缺陷就此消亡）。
    assert "background: var(--paper-high);" in css
    assert "calc((var(--navdock-h) - 44px - 1px) / 2)" in css


def test_the_dock_clears_the_flow_and_the_overlays(tmp_path: Path) -> None:
    """The layout law: the body's bottom padding is the dock's height (so
    the last line always scrolls clear), the composer stands on the dock
    (not on top of it), and the word-card overlay (z 9) floats above the
    dock (z 6) — the teaching note lives in the flow and scrolls out."""

    tokens = _text("tokens.css")
    # v3-a 随迁：--navdock-h 语义 = navdock 实高（N-A 体量账 60），
    # 历史 54 与实高 57 的账实差消亡；新增笔搁触发条与写作态面板缘距
    # 两令牌（v3-a 报告 §4.0 新增令牌登记）。
    assert "--navdock-h: 60px;" in tokens
    assert "--dock-trigger-h: 44px;" in tokens
    assert "--dock-compose-inset: 16px;" in tokens
    screens = _text("screens.css")
    assert (
        "padding-bottom: calc(var(--navdock-h) + var(--safe-bottom));"
        in screens
    )
    assert "bottom: var(--navdock-h); z-index: 8;" in screens
    css = _text("components.css")
    assert ".word-card { position: absolute; z-index: 9;" in css
    # the flow's bottom padding grew by the dock's height (v3-2 随迁：
    # 算术升级为 --navdock-clearance 令牌账；v3-a 再随迁：手写 256px 余量
    # 退役——账 = navdock + 安全区 + 笔搁触发条 + 一档呼吸，O7 死区清账)
    assert ".flow { padding: 18px var(--read-pad)" in screens
    assert ("calc(var(--navdock-clearance) + var(--dock-trigger-h)"
            in screens)
    assert ("--navdock-clearance: calc(var(--navdock-h)"
            " + var(--safe-bottom));" in tokens)


# ---------------------------------------------------------------------------
# 3. the section tabs (#20)


def test_section_tabs_carry_the_full_aria_wiring(tmp_path: Path) -> None:
    """Two tablists, six tabs, six panels — every tab controls its panel,
    every panel is labelled by its tab, the selected tab is marked in the
    markup, and the roving tabindex + arrow keys live in components.js."""

    index = _text("index.html")
    assert index.count('role="tablist"') == 2
    assert index.count('role="tab"') == 6
    assert index.count('role="tabpanel"') == 6
    for space, sections in (
        ("study", ("today", "goal", "progress")),
        ("drawer", ("memory", "privacy", "settings")),
    ):
        assert f'id="{space}-tabs"' in index
        for sec in sections:
            assert f'id="tab-{space}-{sec}" data-section="{sec}"' in index
            assert f'aria-controls="{space}-{sec}"' in index
            assert f'id="{space}-{sec}" role="tabpanel"' in index
            assert f'aria-labelledby="tab-{space}-{sec}"' in index
    assert 'aria-selected="true"' in index
    js = _text("components.js")
    assert 'tab.setAttribute("aria-selected", on ? "true" : "false");' in js
    assert "tab.tabIndex = on ? 0 : -1;" in js
    assert "tabs[next].focus();" in js
    assert "if (event.key === \"ArrowRight\") next = (at + 1) % tabs.length;" \
        in js
    assert "next = (at - 1 + tabs.length) % tabs.length;" in js
    app = _text("app.js")
    assert 'wireSectionTabs(document.getElementById("study-tabs"),' in app
    assert 'wireSectionTabs(document.getElementById("drawer-tabs"),' in app
    assert "markSectionTabs(" in app


# ---------------------------------------------------------------------------
# 4. the space headers (#19)


def test_space_headers_and_the_linkless_parlor_bar(tmp_path: Path) -> None:
    """温故/抽屉 headers ride the .top base with a section-name slot; the
    parlor keeps its own bar — the brand form minus the toggles, not a
    single button left in it."""

    index = _text("index.html")
    assert '<header class="top space-header" id="study-head">' in index
    assert '<header class="top space-header" id="drawer-head">' in index
    assert '<div class="spacehead-sec">今日</div>' in index
    assert '<div class="spacehead-sec">记忆</div>' in index
    parlor = index.split('id="space-parlor"', 1)[1].split("</header>", 1)[0]
    # mc-1 随迁（主从条 = 当前角色名）：信头 = 端点驱动的空槽（.who =
    # 当前角色名，/api/characters 供给）；无 JS 兜底留空——不发明人名；
    # 品牌名与副题退居门厅封面（v21 套件钉）。v2-2 随迁（8.2.2①）：
    # who-sub 身份行长句族退役（身份介绍退入笔友档案全页）——缺位钉。
    assert '<div class="who"></div>' in parlor
    assert 'who-sub' not in parlor
    assert "英语客厅" not in parlor
    assert "<button" not in parlor
    app = _text("app.js")
    assert (
        'sectionLabel(document.getElementById(space + "-head"),' in app
    )


# ---------------------------------------------------------------------------
# 5. the default-section law


def test_entering_a_space_lands_its_default_section(tmp_path: Path) -> None:
    """进空间落默认节（温故=今日、抽屉=记忆），切节即拉——the pulls wired
    by section key; the goal entry still clears a leftover save line, the
    progress entry pulls the learning face（R-1R：可教目标面退役后剩一
    面）, and the settings entry pulls its own three-face read（主线-1
    随迁：缺位钉换真值钉——保存行同法在入节时隐藏）."""

    app = _text("app.js")
    assert 'const DEFAULT_SECTION = { study: "today", drawer: "memory" };' \
        in app
    assert (
        'if (name === "study") showSection("study", DEFAULT_SECTION.study);'
        in app
    )
    assert (
        'if (name === "drawer") showSection("drawer",'
        " DEFAULT_SECTION.drawer);" in app
    )
    assert '"study-today": loadToday' in app
    assert '"drawer-memory": loadMemory' in app
    # 主线-1 随迁：隐私节入节拉两面（按表达 + 按伙伴）
    assert '"drawer-privacy": () => { loadDelTargets(); loadDelPartner(); },' \
        in app
    # rd-3 随迁（9.11-22）：档案节只拉学习一面——诊断五板移出用户面后
    # loadDiagnostics 退役（缺位钉）
    assert '"study-progress": () => { loadLearning(); },' in app
    assert "loadDiagnostics" not in app
    assert 'goalBox("goal-result").hidden = true;' in app
    # 主线-1 随迁（DEC-OPI-76a0a10a-….30）：设置节入节即拉三面真值
    assert '"drawer-settings": () => {' in app
    assert 'settingsBox("settings-result").hidden = true;' in app
    assert "loadSettings();" in app


# ---------------------------------------------------------------------------
# 6. the settings honesty


def test_the_settings_node_is_an_honest_placeholder(tmp_path: Path) -> None:
    """The drawer's settings section（主线-1 随迁 + veto-R 随迁——8.2.8
    重铸②为真控制面，veto-R 起模式可改）: the two standing
    truths survive, the mode face is the ink select editor（只读 Law 句
    与换档句随只读读法退役）, the four tiers ride along as the select's
    words, and no promise word anywhere."""

    page = _page_of(tmp_path)
    # rd-4 缺位钉：旧两句退役，不回潮
    assert "设置面还没有铺开。" not in page
    assert "教学模式读面与端点说明（位次 R-3，不承诺时点）" not in page
    # 两真句保留 + 批注频率的指向句（IA 分层：不与方向节重复）
    assert "页面不读取，也不显示" in page
    assert "这台应用只服务你一个人（127.0.0.1，无账号无密码）。" in page
    assert "批注频率在 温故 · 方向 里调。" in page
    # veto-R 随迁：模式可改读面（墨选编辑器容器）；只读 Law 句与换档
    # 句退役；四档词随 MODE_CN 常量在 app.js（页面词面零拷贝）
    assert 'id="settings-mode-editor"' in page
    assert "由启动命令给定，这里读得到，但不能改。" not in page
    assert "换端点或换档 = 改启动命令再启动。" not in page
    assert "娱乐 · 关系优先" in page
    assert "平衡" in page
    assert "学习优先" in page
    # no promise words（含「即将」的旧钉保持）
    assert "即将" not in page
    assert "敬请" not in page


# ---------------------------------------------------------------------------
# 7. the registration (the disposition knife: LOW-1 + LOW-2)


def test_the_three_shell_components_are_pinned_registered() -> None:
    """The R-1 registration is pinned the word-card way (the p-1
    precedent, four pieces): the spec's numbered rows, the css contract
    blocks, the js wiring factories, and the selectors as single sources
    across the tree — plus the dock's aria-current pair, the one wiring
    line the review's m9 mutation deleted without a red."""

    from tests.host.test_fg1_architecture import (
        COMPONENT_NAMES,
        _webui_all_text,
        _webui_text,
    )

    for name in ("dock", "space-header", "section-tabs"):
        assert name in COMPONENT_NAMES, name
    spec = (
        Path(__file__).resolve().parents[2]
        / "docs" / "FRONTEND_SPEC.md"
    ).read_text(encoding="utf-8")
    for row in ("| 18 | dock", "| 19 | space-header",
                "| 20 | section-tabs"):
        assert row in spec, row
    css = _webui_text("components.css")
    for block in ("18. dock", "19. space-header", "20. section-tabs"):
        assert block in css, block
    js = _webui_text("components.js")
    for factory in (
        "export function wireNavdock(",
        "export function markNavdock(",
        "export function sectionLabel(",
        "export function wireSectionTabs(",
        "export function markSectionTabs(",
    ):
        assert factory in js, factory
    # the active-space semantics: the on-arm sets aria-current, the
    # off-arm clears it (m9 deleted both and stayed green)
    assert 'if (on) item.setAttribute("aria-current", "page");' in js
    assert 'else item.removeAttribute("aria-current");' in js
    whole = _webui_all_text()
    for selector in (
        ".navdock {",
        ".navdock-item {",
        ".navdock-item--on {",
        ".space-header .spacehead-sec {",
        ".section-tabs {",
        ".section-tab {",
        ".section-tab--on {",
    ):
        assert whole.count(selector) == 1, selector
