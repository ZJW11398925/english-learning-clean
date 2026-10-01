"""F-G2 — the entry face made product, the state suite, and the living
registry.

Four groups (the task book's own):

1. **brand-mark** — the mark is an inline SVG whose *geometry* lives in
   index.html's ``<template>`` (the HTML parser reads ``svg`` natively, so
   the source never spells the SVG namespace string and the per-file
   zero-external pins hold untouched); the factory clones it and lands
   the size variants; the ink line and the wax-seal dot ride the tokens;
   the brand bar (mark + serif wordmark + the mono right slot) graces
   both the parlor and the set screen, hairline-clamped top and bottom.
2. **state-banner** — the three variants (loading with the one breathing
   ellipsis and its reduced-motion static arm / empty / error with the
   injected retry link) are registered once, and the panels' three faces
   all ride it: the loaders show loading first, the empty and error arms
   delegate through diagEmpty/diagError, and every retry re-pulls only
   its own panel.
3. **the cover** — R-1W 重做后的封面信笺（称呼 / 两段缩进正文 / 又及 /
   拆开这封信 →）与诚实的版本落款（``elc · web`` — no fabricated
   version digits）.
4. **the living registry** — spec ⑤ carries the user's doctrine (the
   library grows with the product; check-then-reuse-then-build-then-
   register in the same cut) and the ③ table rows for both new
   components; AGENTS.md carries the growth clause.

Every page-source pin reads the served union (the F-G1 reading), so
what is pinned is what the browser actually gets.
"""

from __future__ import annotations

from pathlib import Path

import elc.web
from tests.host.test_fg1_architecture import (
    COMPONENTS,
    _webui_all_text,
    _webui_text,
)
from tests.host.test_w1_web import _page_source, web_stack

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = Path(elc.web.__file__).parent / "webui"


def _page_of(tmp_path: Path) -> str:
    """The served page source over the plain offline stack — the shell
    plus every static asset it links."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


# ---------------------------------------------------------------------------
# 1. brand-mark


def test_the_brand_mark_is_an_inline_svg_with_no_resource_hole(
    tmp_path: Path,
) -> None:
    """The mark's geometry is the shell's own template (one inline svg:
    the envelope outline, the flap and the wax-seal dot), the factory
    clones it — no namespace string anywhere, no ``data:`` URI anywhere,
    and the ink line / seal dot ride the tokens, not literal hex."""

    index = _webui_text("index.html")
    assert '<template id="brand-mark-source">' in index
    assert '<svg class="brandmark" viewBox="0 0 48 48"' in index
    assert '<rect class="bm-line" x="7" y="13" width="34" height="24"/>' in index
    assert '<path class="bm-line" d="M7 15 L24 28 L41 15"/>' in index
    assert '<circle class="bm-seal" cx="24" cy="28" r="4.6"/>' in index
    js = _webui_text("components.js")
    assert "export function brandMark(variant) {" in js
    assert ".content.firstElementChild.cloneNode(true)" in js
    # the namespace-string shape is not how the mark is built: cloning the
    # template is (the per-file "http://" pins then hold untouched)
    assert "createElementNS" not in js
    css = _webui_text("components.css")
    assert ".brandmark { width: 30px; height: 30px; }" in css
    assert ".brandmark--sm { width: 20px; height: 20px; }" in css
    assert ".brandmark--lg { width: 64px; height: 64px; }" in css
    assert (
        ".brandmark .bm-line { fill: none; stroke: var(--ink);"
        " stroke-width: 2;" in css
    )
    # v2 随迁（简报 §2 纪律：朱砂只盖真实事件——品牌印记不是事件）：
    # 封缄点色 = 墨蓝强调（--accent；--pencil 别名同源）
    assert ".brandmark .bm-seal { fill: var(--accent); }" in css
    for name in ("index.html", "components.js", "components.css"):
        assert "data:" not in _webui_text(name), name
    # single source (spec ⑤): the component's own base definition, once
    # in the tree (the screens.css placement rules are descendant
    # selectors — `.top .brandmark {` — and not redefinitions)
    whole = _webui_all_text()
    assert whole.count("\n.brandmark {") == 1


def test_the_brand_bar_graces_both_screens(tmp_path: Path) -> None:
    """The brand bar — mark (sm) + serif wordmark — graces every space
    header (the parlor's own bar and the two space-headers), each clamped
    by a top and a bottom hairline; the marks land before the first
    screen shows. R-1 随迁：品牌条不再挂链接（导航归 dock），旧「回
    客厅」钮与 sethead 变体退役（缺位钉）；空间头的节名槽由
    space-header（#19）承担。"""

    index = _webui_text("index.html")
    # R-1 随迁：空间头三枚 --sm（客厅 / 温故 / 抽屉【rd-2 前称学案/柜
    # 抽】；今日/目标/仪表的品牌条随五屏退役——空间头部唯一）
    assert index.count('data-brand-mark="sm"') == 3
    assert index.count('data-brand-mark="lg"') == 1
    # R-1 随迁：温故/抽屉头部走 space-header（.top 基形 + 节名槽）；
    # 旧 sethead 变体与「回客厅」钮退役（缺位钉）
    assert '<header class="top space-header" id="study-head">' in index
    assert '<header class="top space-header" id="drawer-head">' in index
    assert '<header class="top sethead">' not in index
    assert 'id="back-to-living"' not in index
    assert "← 回客厅" not in index
    # v2 命名随迁（简报 §1）：信头静态兜底 = BRAND 同值
    assert '<div class="who">展信佳</div>' in index
    assert "英语客厅" not in index
    app = _webui_text("app.js")
    assert "installBrandMarks();" in app
    assert app.index("installBrandMarks();") < app.index("loadHistory();")
    screens = _webui_text("screens.css")
    assert (
        "border-top: 1px solid var(--rule);\n"
        "       border-bottom: 1px solid var(--rule);" in screens
    )
    assert ".top .brandmark { align-self: center; flex: none; }" in screens
    # R-1W 随迁（门厅重做）：印记居中法由「.ob .brandmark display:block
    # + auto 边距」迁为 flex 容器 .ob-mark（旧串：.ob .brandmark
    # { display: block; margin: 0 auto 18px; }）
    assert ".ob-mark { display: flex; justify-content: center;" in screens


# ---------------------------------------------------------------------------
# 2. state-banner


def test_the_state_banner_family_is_registered(tmp_path: Path) -> None:
    """The three variants, registered once. v2 随迁（简报 §5 零常驻循环
    铁律）：loading 尾点静态化——原 state-breathe 1.6s infinite 呼吸
    动画退役（页面现在零循环动画），reduced-motion 专项降级臂随之无
    对象；「取信中…」的信息由文字本身承担（信息本就不得只有动画一个
    载体）。error's retry is the link-btn pencil variant with the
    caller's callback; the empty face is the faint honest sentence."""

    page = _page_of(tmp_path)
    css = page  # the union covers components.css
    # the breathing loop is gone — and no loop of any kind may return
    assert "state-breathe" not in css
    assert "infinite" not in css
    # the ellipsis tail stays, static (the loading face keeps its shape)
    assert '.state-banner--loading::after { content: "…";' in css
    js = _webui_text("components.js")
    assert "export function stateBanner(kind, opts) {" in js
    assert 'loading: "取信中…"' in js
    assert 'empty: "暂无数据"' in js
    assert 'error: "读取失败"' in js
    assert 'retry.className = "btn btn--pencil";' in js
    assert 'retry.textContent = "重试";' in js
    assert 'typeof options.retry === "function"' in js
    whole = _webui_all_text()
    assert whole.count("\n.state-banner {") == 1
    assert ".state-banner--error { color: var(--pencil); }" in whole


def test_the_panel_faces_ride_the_state_banner(tmp_path: Path) -> None:
    """The consolidation: every loader shows the loading banner first, the
    empty and error arms delegate through diagEmpty/diagError (both now
    wrappers — no panel builds its own note or error line any more), and
    each retry link re-pulls exactly its own panel. The shell's static
    placeholder notes stay .note (empty-state #10's narrowed face)."""

    js = _webui_text("components.js")
    assert 'box.appendChild(stateBanner("empty", { text: word || "暂无数据" }));' in js
    assert 'box.appendChild(stateBanner("error",' in js
    assert 'className = "note"' not in js
    # R-1R（⑧ 8.2.2）：信流的空态横幅退役——空态是读数块的答法，不是
    # 信流的；无短笺的轮次在信流里什么都不挂（缺位钉）
    assert "本轮没有打开教学时刻" not in js
    app = _webui_text("app.js")
    assert "本轮没有打开教学时刻" not in app
    assert "function showLoading(ids) {" in app
    assert "box.appendChild(stateBanner(\"loading\"));" in app
    # rd-3 随迁（9.11-22 移走清单）：诊断五问移出用户面——DIAG_PANEL_IDS
    # 与 loadDiagnostics 整体退役（缺位钉）；档案板自带进行时占位句，
    # 其余面板走统一 loading banner
    assert "showLoading(DIAG_PANEL_IDS);" not in app
    assert "loadDiagnostics" not in app
    assert "showLoading(LEARN_PANEL_IDS);" in app
    assert 'diagError(diagBox(id), "诊断读数拉取失败", loadDiagnostics);' \
        not in app
    assert 'diagError(diagBox(id), "学习读数拉取失败", loadLearning);' in app
    # R-1R 随迁：目标清单的读取面只剩隐私页的按表达忘掉（档案 · 可以练
    # 的表达经 loadLearning 读 targets，失败行在面板槽内同形）
    assert 'diagError(box, "目标清单拉取失败", loadDelTargets);' in app
    # rd-3 随迁：诊断渲染函数族随五板退役；排程照旧由 loadLearning 拉取
    # （降入档案的「计划明细」折叠）
    assert "renderWhyTeach" not in app
    assert "renderSchedule(data.schedule, loadLearning);" in app
    index = _webui_text("index.html")
    assert '<p class="note">暂无数据</p>' in index


# ---------------------------------------------------------------------------
# 3. the cover


def test_the_cover_is_a_complete_letter(tmp_path: Path) -> None:
    """R-1W 重做（⑧ 8.2.1 修订版）：封面是一张完整的信笺——称呼、两段
    缩进正文、又及、进门钮「拆开这封信 →」与诚实的 mono 落款（无编造
    版本数字）；旧三步白板版（一 / 二步题与旧进门词）退役。localStorage
    门语义不动（f1r 套件钉）。"""

    page = _page_of(tmp_path)
    # R-1W 随迁（旧串 → 新串）：一 · 这是什么 → 致 明日之我：（rd-2
    # 豪放档，原「致 来到门前的人：」）；二 · 短笺怎么来 + 三句步文 →
    # 两段缩进正文；就这么定 → → 拆开这封信 →；hint → 又及（进信体）
    assert "致 明日之我：" in page
    # rd-2 随迁：封面定稿段改「致明日之我」两重收信人段（豪放档）
    assert "今日落笔，明日展信。" in page
    assert "写着写着，客厅在旁听着。" in page
    assert "又及：进门以后，底部三个词随时可走" in page
    assert "拆开这封信 →</button>" in page
    # the honest version line: the product's own name, no invented semver
    assert '<p class="ob-version">elc · web</p>' in page
    # 旧形缺位钉：三步结构与旧进门词不再出现
    assert "一 · 这是什么" not in page
    assert "二 · 短笺怎么来" not in page
    assert "就这么定" not in page
    # f1r 旧负控随迁复钉（R-1W 处置：交付迁移退役了它，评审 INFO-2
    # 登记——防回潮面零真空要求下复钉）
    assert "✉ 第一步，也是唯一步" not in page
    screens = _webui_text("screens.css")
    # R-1W 随迁：.ob-step { → .ob-sheet {（封面信笺对象）
    assert ".ob-sheet {" in screens
    assert ".ob-step" not in screens


# ---------------------------------------------------------------------------
# 4. the living registry


def test_the_spec_carries_the_living_registry() -> None:
    """Spec ⑤: the library is a living registry by the user's ruling —
    the four-step induction flow, the same-cut registration rule, and the
    ③ table rows for both new components; AGENTS.md carries the growth
    clause. The registry's length is the components tuple's length."""

    spec = (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    assert "**库是活注册表**" in spec
    assert "用户裁决 2026-09-28" in spec
    assert "1. **先查库**" in spec
    assert "2. **已有则复用**" in spec
    assert "3. **无则新建**" in spec
    assert "4. **同刀登记**" in spec
    assert "| 13 | brand-mark" in spec
    assert "| 14 | state-banner" in spec
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "库随产品增长" in agents
    # p-3 随迁：活注册表随 field/chip 入库生长两格（15 → 17）；
    # R-1 随迁：壳导航三件再长三格（17 → 20）；
    # R-1R 随迁：折叠组 disclosure 再长一格（20 → 21）——同刀登记；
    # R-1V 随迁：icon-set 入库再长一格（21 → 22）——同刀登记；
    # rd-4 随迁：partner-card 入库再长一格（22 → 23）——同刀登记
    assert len(COMPONENTS) == 23
