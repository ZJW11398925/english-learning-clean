"""R-1V — the visual craft pass (视觉工艺刀), pinned.

The user's first inspection of the R-1R face rejected the *craft* layer
(「整体不够协调，留白过分，不高级。设计简陋，如同白板模版……组件、
图标、动效简陋」). R-1V re-works the presentation layer only — the ⑧ v2
copy, the shell's ARIA/keyboard semantics, the twelve endpoints and every
Python side stay frozen. This file pins the craft deliverables (spec ⑨):

1. **the design system** — the token sheet's new scales (the five-step
   serif / two-step sans type scale, line heights, letter spacings, the
   4-based spacing ladder, the four paper washes, the ochre depths, the
   motion tokens, the icon parameters) and the spec's ② expansion plus
   the new ⑨ craft section;
2. **the desktop composition** — the 900px breakpoint, the staged sheet
   (desk ground + 1080px paper + 640px reading column), the marginalia
   rail (date / rule / postmark watermark), and the narrow-screen
   non-regression (the base values stay byte-pinned);
3. **the icon set (#22)** — the four-step registration, the seven ink
   icons on one 20×20 grid with one stroke weight, and every icon's
   live anchor;
4. **the motion registry** — the three keyframe motions with their
   class toggles, the chevron's open-class rotation, and the
   reduced-motion blanket that degrades every one of them;
5. **the component refinements** — the note-paper's paper wash and
   margin rule, the word-card's deckle underlay (paper shadow; since
   rd-1 the underlay carries the registered two-tier stack shadow —
   DEC-OPI-dc0ba4b6-…13 lifted the zero-shadow ban), the torn stitch,
   the pen's focus wash, the hover affordances.

Every page-source pin reads the served union (the F-G1 reading).
"""

from __future__ import annotations

from pathlib import Path

import elc.web
from tests.host.test_w1_web import _page_source, web_stack

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = Path(elc.web.__file__).parent / "webui"


def _page_of(tmp_path: Path) -> str:
    """The served page source over the plain offline stack."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _spec() -> str:
    return (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(
        encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. the design system — tokens and the spec's ②/⑨


def test_the_token_sheet_carries_the_r1v_scales() -> None:
    """⑨-1/9.2 → v2 随迁（简报 §2/§3）：the v2 mature core's 14-colour
    iron-gall sheet, the nine-step type scale（行高写整 px）, the
    letter spacings, the 4-based spacing ladder, the motion tokens
    （opacity 恒慢于 transform 的 --dur-ink 与墨水物理 --dur-wet）,
    the icon parameters and the shell width — every token lives in
    tokens.css; the legacy names survive as aliases resolving into the
    v2 tiers（--pencil 系 = --accent 系、--f-sans = --f-ui、--bg =
    --paper——消费面平滑，值全换）。"""

    tokens = _text("tokens.css")
    for declaration in (
        # the v2 14-colour sheet (the iron-gall core)
        "--paper: #f6f2e8;", "--paper-high: #fdfbf6;",
        "--paper-2: #efe9dc;", "--desk: #e3dccb;",
        "--ink: #191b1e;", "--ink-soft: #4a4d52;",
        "--ink-faint: #6b6e72;", "--rule: #d9d3c5;",
        "--rule-soft: #e7e1d3;", "--accent: #2c476a;",
        "--accent-deep: #1c3049;", "--accent-soft: #8ba0b8;",
        "--seal: #9a392b;", "--touch: #ece6d9;",
        # the watermark ink and the legacy aliases
        "--ink-ghost: #a8a496;",
        "--bg: var(--paper);", "--pencil: var(--accent);",
        # the nine-step scale (whole-px line heights, 4-based)
        "--fs-display: 34px;", "--lh-display: 42px;",
        "--fs-title: 24px;", "--lh-title: 32px;",
        "--fs-head: 18px;", "--lh-head: 26px;",
        "--fs-body: 17px;", "--lh-body: 32px;",
        "--fs-body-latin: 17px;", "--lh-body-latin: 28px;",
        "--fs-small: 14.5px;", "--lh-small: 24px;",
        "--fs-hand: 19px;", "--lh-hand: 30px;",
        "--fs-ui: 12.5px;", "--lh-ui: 20px;",
        "--fs-micro: 11.5px;", "--lh-micro: 18px;",
        # the measure and the baseline grid（字落线上）
        "--measure: 34em;", "--baseline: 32px;",
        # the motion tokens（纸先落、墨后渗）
        "--dur-micro: 100ms;", "--dur-stamp: 120ms;",
        "--dur-1: 140ms;", "--dur-note: 260ms;",
        "--dur-panel-in: 280ms;", "--dur-ink: 360ms;",
        "--dur-wet: 600ms;", "--dur-panel-out: 200ms;",
        "--dur-settle: 320ms;",
        "--ease-paper: cubic-bezier(0.16, 1, 0.3, 1);",
        "--ease-enter: cubic-bezier(0.05, 0.7, 0.1, 1);",
        "--ease-exit: cubic-bezier(0.3, 0, 1, 1);",
        "--ease-press: cubic-bezier(0.4, 0, 0.2, 1);",
        # the icon parameters and the shell width
        "--icon-size: 18px;", "--icon-stroke: 1.5;",
        "--shell-w: 430px;",
    ):
        assert declaration in tokens, declaration
    # the spacing ladder, all eight rungs
    for rung, value in enumerate(
            (4, 8, 12, 16, 24, 32, 48, 64), start=1):
        assert f"--sp-{rung}: {value}px;" in tokens, rung


def test_the_paper_and_ochre_layers_are_not_flattened() -> None:
    """⑨-3 → v2 随迁：the washes are *layers* — four papers and the
    ink-blue accent tier（--pencil 系 = --accent 系旧名别名），pairwise
    distinct (a flattened wash is not a layer)."""

    tokens = _text("tokens.css")
    papers = ("#f6f2e8", "#fdfbf6", "#efe9dc", "#e3dccb")
    inks = ("#191b1e", "#4a4d52", "#6b6e72")
    accents = ("#2c476a", "#1c3049", "#8ba0b8")
    for value in papers + inks + accents:
        assert f": {value};" in tokens, value
    assert len(set(papers)) == 4
    assert len(set(accents)) == 3
    # the washes sit between paper and ink — none of them is an ink
    # or an accent（三档互不重合）
    assert not (set(papers) & set(inks + accents))


def test_the_spec_registers_the_tokens_and_the_craft_section() -> None:
    """② grew the new token rows and ⑨ is the craft section — the
    typographic scale, the spacing rhythm, the paper layers, the icon
    contract, the motion registry and the desktop composition, plus
    the ③ revision register (9.7)."""

    spec = _spec()
    for row in (
        "| `--paper-high` |", "| `--paper-2` |", "| `--desk` |",
        "| `--ink-ghost` |", "| `--pencil-deep` |", "| `--pencil-soft` |",
        "`--fs-display` `--fs-title`", "| `--sp-1` … `--sp-8` |",
        # v2-s 随迁：旧三时长行（--dur-1/2/3）随 v2 动效档重定退役，
        # 改钉现役进/出对行（280/200，值真仍在）
        "| `--dur-panel-in` `--dur-panel-out` |",
        "| `--icon-size` `--icon-stroke` |", "| `--shell-w` |",
    ):
        assert row in spec, row
    assert "## ⑨ 视觉工艺规范" in spec
    for subsection in (
        "### 9.1 排版标度", "### 9.2 间距节奏", "### 9.3 质感与层次",
        "### 9.4 图标集契约", "### 9.5 动效注册表",
        # R-1W 随迁：9.6 由「桌面构图」（单一 900px 断点）重写为四档
        # 断点系统——旧串「### 9.6 桌面构图」就此退役
        "### 9.6 断点系统（R-1W 重写版：全断点响应式）",
        "### 9.7 本刀的 ③ 契约修订登记",
    ):
        assert subsection in spec, subsection
    # the motion registry names every motion with its degradation
    # （v2-s 随迁：ink-fade 由 v2 的 ink-wash 渗墨原语取代——注册表
    # 五 keyframes：paper-drop/ink-wash/ink-set/paper-unfold/stamp-press）
    for word in ("ink-wash", "note-arrive", "paper-unfold",
                 "reduced-motion", "总降级块"):
        assert word in spec, word


# ---------------------------------------------------------------------------
# 2. the desktop composition


def test_the_desktop_composition_has_a_breakpoint_and_a_sheet() -> None:
    """⑨-6 → v2 随迁：≥900px the page becomes a sheet on a desk — the
    breakpoint pin (900px exactly), the shell width rewritten to 1080px
    inside the query, the reading column at --measure（34em 版心，
    简报 §3b）, and the marginalia rail with its date slot（楷体手迹位，
    T1 三合法面之一）; the decorative postmark watermark is gone
    （邮戳只落真实事件——T2）."""

    screens = _text("screens.css")
    assert "@media (min-width: 900px) {" in screens
    desktop = screens.split("@media (min-width: 900px) {", 1)[1]
    assert "--shell-w: 1080px;" in desktop
    assert "max-width: 1080px;" in desktop
    assert "max-width: var(--measure);" in desktop
    assert "background: var(--desk);" in desktop
    assert "outline: 1px solid var(--rule-soft); outline-offset: 5px;" \
        in desktop
    index = _text("index.html")
    assert '<aside class="marginalia" aria-hidden="true">' in index
    assert 'id="marginalia-date"' in index
    # the decorative watermark is gone (the rail keeps date + rule only)
    assert "marginalia-mark" not in index
    assert "postmark" not in index
    # the rail hides by default (the narrow screens never see it)
    assert ".marginalia { display: none; }" in screens


def test_the_narrow_screen_base_values_are_untouched(tmp_path: Path) -> None:
    """≤480px non-regression: the mobile base rules stay byte-pinned —
    the 430px shell width is the token's default (the desktop rewrite
    lives only inside the ≥900px query), the dock/navdock/flow rules
    keep their pinned forms."""

    page = _page_of(tmp_path)
    tokens = _text("tokens.css")
    assert "--shell-w: 430px;" in tokens
    # v3-a 随迁：--navdock-h = navdock 实高（N-A 体量账 60，历史 54
    # 与实高 57 的账实差消亡）。
    assert "--navdock-h: 60px;" in tokens
    screens = _text("screens.css")
    # v3-2 随迁：flow 尾距升级 --navdock-clearance 令牌账；v3-a 再随迁：
    # 手写 256px 余量退役（账 = navdock + 安全区 + 笔搁触发条 + 呼吸，
    # O7 死区清账）。
    assert ".flow { padding: 18px var(--read-pad)" in screens
    assert ("calc(var(--navdock-clearance) + var(--dock-trigger-h)"
            in screens)
    assert (
        "padding-bottom: calc(var(--navdock-h) + var(--safe-bottom));"
        in screens
    )
    assert "bottom: var(--navdock-h); z-index: 8;" in screens
    # R-1W 随迁：断点系统落地——「恰一个 ≥900 媒体查询」计数钉迁为三
    # 边界各恰一次（481 / 900 / 1280 是 ⑨-6 的档位契约；新档语义由
    # test_r1w_responsive_redo.py 钉）。430 基线值 = token 默认不动。
    for boundary in ("481px", "900px", "1280px"):
        assert screens.count(f"@media (min-width: {boundary}) {{") == 1, \
            boundary
    # the dock stands on the 430px column by default; the tier rewrites
    # live only behind the media queries
    assert page.count("--shell-w: 1080px;") == 1


# ---------------------------------------------------------------------------
# 3. the icon set (#22)


def test_the_icon_set_is_registered_in_all_four_places() -> None:
    """The living-registry four steps, one cut (the word-card and
    disclosure precedents): the spec ③ row, the components.css contract
    block with its four clauses, the components.js factory pair and the
    COMPONENTS tuple."""

    from tests.host.test_fg1_architecture import (
        COMPONENT_NAMES,
        COMPONENTS,
    )

    assert "icon-set" in COMPONENT_NAMES
    # rd-4 曾随迁长到 23；cs-2 随迁：浮层伙伴卡退役再缩回（23 → 22）；
    # fr-A 随迁：会话窗三件 + 墨选四格入库（22 → 26）
    assert len(COMPONENTS) == 26
    assert "| 22 | icon-set" in _spec()
    css = _text("components.css")
    assert "22. icon-set" in css
    js = _text("components.js")
    assert "export function inkIcon(name) {" in js
    assert "export function installIcons() {" in js


def test_the_seven_icons_share_one_grid_and_one_stroke() -> None:
    """⑨-4: the ink icons live in the shell's template on one 20×20 grid,
    all aria-hidden (their hosts' words carry the meaning); the stroke
    weight is the token, spelled once in components.css — no per-icon
    stroke drift, no external geometry. v2 随迁：postmark 随边注栏水印
    撤除退役（注册的图标是使用的图标，注册表不做阁楼）——八枚 → 七枚。
    v3-a 随迁：#18 落墨页签的导航三枚入集（desk/revisit/drawer，
    「禁止变体：图标」显式修订）——七枚 → 十枚。"""

    index = _text("index.html")
    assert '<template id="icon-set-source">' in index
    for name in ("search", "chevron", "note", "write",
                 "inbox", "lamp", "stamp",
                 "desk", "revisit", "drawer"):
        assert f'<svg id="icon-{name}" class="inkicon" ' \
            f'viewBox="0 0 20 20" aria-hidden="true">' in index, name
    # the retired watermark icon is gone with its anchor
    assert 'id="icon-postmark"' not in index
    # the grid is uniform: ten icons, ten identical viewBoxes
    assert index.count('viewBox="0 0 20 20"') == 10
    css = _text("components.css")
    assert (
        ".inkicon { width: var(--icon-size); height: var(--icon-size);"
        in css
    )
    assert "stroke-width: var(--icon-stroke);" in css
    assert "stroke-linecap: round; stroke-linejoin: round;" in css
    # the icons carry no stroke literals of their own (one weight, one
    # source — the token)
    for name in ("search", "chevron", "note", "write",
                 "inbox", "lamp", "stamp",
                 "desk", "revisit", "drawer"):
        svg = index.split(f'<svg id="icon-{name}"', 1)[1].split(
            "</svg>", 1)[0]
        assert "stroke" not in svg, name


def test_every_icon_has_a_live_anchor() -> None:
    """A registered icon is a used icon (the registry is not an attic):
    search rides the filter field's label, chevron the disclosure
    marker, note the moment card's head, write the waiting line, inbox
    the empty hall, lamp the empty state, stamp the cover's dateline
    and the settled teaching card（结课邮票——真实事件位）; the v3-a
    navigation trio rides the #18 tabs（desk/revisit/drawer——图标与
    文字标签同钮）. The postmark watermark icon is retired with its
    anchor (v2 随迁)."""

    js = _text("components.js")
    assert 'inkIcon("chevron")' in js  # disclosure's marker
    assert 'inkIcon("note")' in js  # the moment card's head
    assert 'inkIcon("lamp")' in js  # the empty state-banner
    assert 'inkIcon("write")' in js  # the sent-line（rd-2 词面「信已寄出……」）
    app = _text("app.js")
    assert 'inkIcon("search")' in app  # the filter field's label
    assert 'inkIcon("inbox")' in app  # the empty hall
    index = _text("index.html")
    assert 'data-icon="stamp"' in index  # the cover's dateline corner
    for glyph in ("data-icon=\"desk\"", "data-icon=\"revisit\"",
                  "data-icon=\"drawer\""):
        assert glyph in index  # the #18 ink tabs (v3-a)
    # no decorative postmark watermark anywhere
    assert "postmark" not in index


# ---------------------------------------------------------------------------
# 4. the motion registry


def test_the_motion_registry_and_its_class_toggles() -> None:
    """⑨-5 → v2 随迁（简报 §5「纸先落、墨后渗」）：the keyframes carry
    the drop/wash pair — paper-drop（transform）+ ink-wash（opacity，
    calc(var(--dur-*) * 1.3) 表达「opacity 恒慢于 transform ≈1.3×」的
    法则）; the class toggles keep their JS gating（history backfill
    stays still, the poll's re-renders do not replay）; the chevron's
    open-class rotation. 退役名单：ink-fade / note-arrive（被双动画
    取代）/ paper-settle / seal-press（被 wash 档取代）/ state-breathe
    （零常驻循环）。"""

    css = _text("components.css")
    for motion in ("@keyframes paper-drop {", "@keyframes ink-wash {",
                   "@keyframes ink-set {", "@keyframes paper-unfold {",
                   "@keyframes stamp-press {"):
        assert motion in css, motion
    for retired in ("@keyframes ink-fade {", "@keyframes note-arrive {",
                    "@keyframes paper-settle {", "@keyframes seal-press {",
                    "@keyframes state-breathe {"):
        assert retired not in css, retired
    # the new-letter entrance: transform 280 + opacity 360（1.3× 慢）,
    # plus the ink wash（墨水物理 T1-3：ink-ghost → ink ≈600ms）
    assert (
        ".flow-enter { animation: paper-drop var(--dur-panel-in)"
        " var(--ease-paper)\n               both, ink-wash"
        " var(--dur-ink) var(--ease-paper) both; }" in css
    )
    assert (
        ".ink-wet .say { animation: ink-set var(--dur-wet)"
        " var(--ease-paper) both; }" in css
    )
    # the note arrival rides the note tier with the same 1.3× wash
    assert (
        ".note-paper--enter { animation: paper-drop var(--dur-note)"
        in css
    )
    assert (
        ".disclosure-body:not([hidden]) {\n"
        "            animation: paper-unfold var(--dur-note)"
        " var(--ease-enter) both," in css
    )
    # the toggles, JS side: new letters only (history never enters)
    js = _text("components.js")
    assert 'if (options.enter) node.classList.add("flow-enter", "ink-wet");' in js
    assert '" note-paper--enter"' in js
    app = _text("app.js")
    assert 'addLine("user", text, { enter: true, when: sentAt });' in app
    # the chevron rotates on the host's open class, not a glyph swap
    assert ".disclosure--open .disclosure-marker .inkicon {" in css
    assert "transform: rotate(90deg);" in css
    assert (
        "transition: transform var(--dur-note) var(--ease-paper);" in css
    )


def test_every_motion_degrades_under_reduced_motion() -> None:
    """The reduced-motion law: the blanket block at the library's tail
    zeroes every animation and transition, and it comes *after* every
    keyframes block. v2 随迁：keyframes 清单 = 五枚（drop/wash/ink-set/
    unfold/stamp-press）——循环件 state-breathe 已退役（零常驻循环，
    专项降级臂随之无对象）。rd-1 的 0.01ms 技巧保留（animationend/
    transitionend 照发——JS 一次性清理不失效）。"""

    css = _text("components.css")
    blanket = (
        "@media (prefers-reduced-motion: reduce) {\n"
        "  *, *::before, *::after {\n"
        "    animation-duration: 0.01ms !important;\n"
        "    animation-delay: 0s !important;\n"
        "    animation-iteration-count: 1 !important;\n"
        "    transition-duration: 0.01ms !important;\n"
        "    transition-delay: 0s !important;\n"
        "  }\n"
        "}"
    )
    assert blanket in css
    blanket_at = css.index(blanket)
    for motion in ("@keyframes paper-drop {", "@keyframes ink-wash {",
                   "@keyframes ink-set {", "@keyframes paper-unfold {",
                   "@keyframes stamp-press {"):
        assert css.index(motion) < blanket_at, motion
    # zero standing loops: no infinite iteration anywhere
    assert "infinite" not in css


# ---------------------------------------------------------------------------
# 5. the component refinements


def test_the_note_paper_is_a_distinct_wash_with_a_margin_rule() -> None:
    """#3 (⑨-7.3): the note-paper reads as its own paper — the paper-2
    wash (the letter's and the note's washes now differ), the 2px margin
    rule on the left edge, and the note icon in its head."""

    css = _text("components.css")
    assert (
        ".note-paper { margin: 0 0 18px; background: var(--paper-2);\n"
        "              border-left: 2px solid var(--rule);" in css
    )
    assert ".note-head .inkicon {" in css
    js = _text("components.js")
    assert 'head.className = "note-head";' in js


def test_the_word_card_wears_a_deckle_not_a_shadow(tmp_path: Path) -> None:
    """#15 (⑨-7.7): the overlay floats as stacked paper — the paper-high
    face, a hairline edge and the deckle underlay 3px offset. rd-1 随迁
    （面6 解除零阴影，DEC-OPI-dc0ba4b6-…13）：垫纸层承注册的
    --stack-shadow-soft（两级之内、墨色同源）；契约反面不变式照旧
    （radius 无、全黑 rgba(0,0,0) 无——正面契约钉在 rd1 套件）。"""

    page = _page_of(tmp_path)
    # rd-4 随迁（9.12-23）+ v2 随迁（简报 §6「仅邮票/邮戳允许圆形；
    # 信纸物件圆角收窄一档 ≤2px」）：零大圆角面板法则的豁免位 =
    # 手迹/盖印/邮票几何 + 信纸物件 2px——红笔圈线椭圆 + 邮戳双圈圆
    # 两处（.postmark 与信封沓的 .env-mark 各含本体与 ::before）+
    # 邮票图形两枚（.stamp-v0/.stamp-v5）+ 信封沓的 2px 两处
    # （.envsel/.env，简报 §6 增补档；mc-2 起加编辑台的开场信预览
    # 短笺——同 ≤2px 信纸物件档；v2-2 起加翻页全览页卡 .envpage）；
    # fr-A 随迁（+2 = 13）：#24 回底墨点本体与其纸白薄雾圆——用户
    # 明示的墨点样式族，②-6 的 fr-A 豁免登记在册。
    # 面板大圆角仍一处即红。
    assert page.count("border-radius") == 13
    assert "border-radius: 50%" in page
    assert "rgba(0, 0, 0" not in page
    css = _text("components.css")
    # v2-2 随迁（8.2.2③ 双形态）：浮卡基形加 --wc-x/--wc-y 定位
    # （custom props 承 clamp 值——触屏 sheet 档不消费坐标，媒体查询
    # 分档）；纸面与发丝边不变。
    assert (
        ".word-card { position: absolute; z-index: 9; max-width: 300px;\n"
        "             left: var(--wc-x, 0px); top: var(--wc-y, 0px);\n"
        "             background: var(--paper-high);"
        " border: 1px solid var(--rule);" in css
    )
    assert ".word-card::after {" in css
    assert "transform: translate(3px, 3px);" in css
    # the deckle underlay carries the registered two-tier shadow, not a
    # hand-written one (the tier tokens are the only shadow sources)
    deckle = css.split(".word-card::after {", 1)[1].split("}", 1)[0]
    assert "box-shadow: var(--stack-shadow-soft);" in deckle


def test_the_small_craft_touches_land(tmp_path: Path) -> None:
    """The per-component craft touches (⑨-7): the result strip's torn
    stitch, the pen's focus wash, the word hover's ochre affordance,
    the section label's margin-rule ornament, the focus ring's two
    missing controls covered, and the cover's ruled formheads."""

    css = _text("components.css")
    assert (
        ".resultstrip { margin-top: 10px; border-top: 1px dashed"
        " var(--rule);" in css
    )
    assert ".pen:focus { background-color: var(--paper-high); }" in css
    assert ".word:hover { text-decoration: underline dotted;" in css
    assert "text-decoration-color: var(--pencil-soft);" in css
    assert ".sec h3::before {" in css
    assert "border-top: 1px solid var(--ink-ghost);" in css
    assert (
        "textarea:focus-visible, select:focus-visible {\n"
        "  outline: 1px solid var(--pencil); outline-offset: 2px; }" in css
    )
    screens = _text("screens.css")
    # R-1W 随迁：门厅重做后步题界尺小标（.ob .formhead::before/::after）
    # 退役，封面工艺钉迁为 .ob-divider（标题与信体之间的短界尺分饰）
    assert ".ob-divider { display: block; width: 3em;" in screens


def test_the_marginalia_date_is_real_client_data() -> None:
    """⑨-6: the rail's only words are the date — a client-derived
    mechanical fact (zero fabricated data), landed as textContent."""

    app = _text("app.js")
    assert 'document.getElementById("marginalia-date")' in app
    assert "dateSlot.textContent = today.getFullYear()" in app
    assert "installIcons();" in app
    # the brand-mark install order pin's neighborhood stays intact
    assert app.index("installBrandMarks();") < app.index("loadHistory();")


# ---------------------------------------------------------------------------
# 6. the walkthrough repairs and their craft kin (the disposition knife:
#    the review's F-2 — registered in spec 9.7-14 but unpinned)


def test_the_walkthrough_repairs_and_craft_kin_are_pinned() -> None:
    """9.7-14②③④ + the same-family craft forms the review found without
    regression cover: the probe-key truncation (the pipe-five-segment
    engineering key never leaks into the letter flow), the short-flow
    scroll discipline, the empty-hall seat, the desktop dock collapse,
    the chip hover, the teach-me re-cut."""

    app = _text("app.js")
    # ② spokenOf reads only the first segment of a probe key
    assert 'const text = String(keyOrId).split("|")[0];' in app
    js = _text("components.js")
    # ③ the scroll keeps the last line clear of the composer, clamped
    # to the document bottom (long flows scroll exactly as before)
    assert "const clearance = 150;" in js
    assert (
        "window.scrollTo(0, Math.max(0, Math.min(target,"
        "\n    document.body.scrollHeight - window.innerHeight)));"
        in js
    )
    css = _text("components.css")
    # ④ the empty-hall line takes its seat below the brand bar
    assert ".sysline.emptyhall { margin-top: var(--sp-6); }" in css
    # the desktop dock collapses onto the paper (⑨-6, component side)
    assert (
        ".navdock[aria-label] { justify-content: center;"
        " gap: var(--sp-7); }" in css
    )
    assert (
        ".navdock-item[data-space] { flex: 0 1 auto; min-width: 132px; }"
        in css
    )
    # the chip's hover answer and the teach-me re-cut（v2 随迁：字号
    # 字面收编入 ui 档 token——tokens 是唯一物理出处）
    assert ".chip:not(.chip--on):hover { border-color: var(--ink-soft);" in css
    assert (
        ".teach-me { font-family: var(--f-sans);"
        " font-size: var(--fs-ui); position: relative;" in css
    )
    assert ".teach-me:hover { color: var(--pencil-deep); }" in css
