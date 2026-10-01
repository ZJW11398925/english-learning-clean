"""R-1W — the full-breakpoint responsive system + the cover redo, pinned.

The user's twin order: 「各个页面在不同屏幕大小中的显示效果差距很大，
完全没有做这方面的优化」 and 「欢迎页必须完全重做，高规格，不得敷衍」.
R-1W answers on two faces in one cut (spec ⑨-6 rewritten as a four-tier
breakpoint system; ⑧ 8.2.1 rewritten as the cover letter). This file pins:

1. **the breakpoint contract** — the three boundary queries (481 / 900 /
   1280) each spelled exactly once, in tier order; the tablet tier is a
   real composition (600px shell + the two-column panel containers), not
   a stretched 430;
2. **the wide tier extends the desk, not the line length** — the paper
   grows to 1240 and the rail to 240 while the 640 reading column and
   the composer stay untouched;
3. **the per-page adaptations** — the family groups (today + privacy)
   carry the grid class at the JS factory, the homogeneous panels pair
   up (memory / settings / today), the record page splits 账｜为什么;
4. **the keyboard face** — interactive-widget=resizes-content on the
   viewport, the cover's 100vh → 100dvh double declaration;
5. **the cover redo** — the complete letter structure (dateline + stamp
   / mark / wordmark / display title / salutation / indented body /
   postscript / door / version), the copy verbatim, the door semantics
   (localStorage gate, title, landing space) untouched;
6. **the cover craft** — typography rides the ② scale tokens, the two
   registered motions (paper-settle / seal-press) sit before the
   reduced-motion blanket, the stamp icon's four-step registration, the
   cover date is real client data;
7. **the spec carries the rewritten ⑨-6 and the revision register**
   (9.8's three entries, 8.2.1's revision marker).

The frozen lines hold elsewhere: every other page's 8.2 copy verbatim
(tested by the r1r suite untouched), web.py and all Python untouched,
ARIA/keyboard semantics with zero regression. Every page-source pin
reads the served union (the F-G1 reading).
"""

from __future__ import annotations

import re
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


def _tier(screens: str, boundary: str) -> str:
    """The rules of one tier: the slice from its query to the next one
    (or the end of the file)."""

    start = screens.index(f"@media (min-width: {boundary}) {{")
    later = [screens.find(f"@media (min-width: {b}) {{", start + 1)
             for b in ("481px", "900px", "1280px")
             if screens.find(f"@media (min-width: {b}) {{", start + 1) != -1]
    end = min(later) if later else len(screens)
    return screens[start:end]


# ---------------------------------------------------------------------------
# 1. the breakpoint contract


def test_the_three_boundaries_are_the_contract() -> None:
    """⑨-6: four tiers over three boundaries — 481 / 900 / 1280 each
    spelled exactly once in screens.css, in ascending order (the tier
    order is the cascade order); the base shell width stays the token's
    430 default and #stage now rides --shell-w (one width source for
    stage, navdock and composer)."""

    screens = _text("screens.css")
    at = {}
    for boundary in ("481px", "900px", "1280px"):
        assert screens.count(f"@media (min-width: {boundary}) {{") == 1, \
            boundary
        at[boundary] = screens.index(f"@media (min-width: {boundary}) {{")
    assert at["481px"] < at["900px"] < at["1280px"]
    # the base width is the token (no tier rewrite outside the queries)
    tokens = _text("tokens.css")
    assert "--shell-w: 430px;" in tokens
    assert screens.count("--shell-w:") == 3  # one rewrite per tier, no base
    assert "#stage { max-width: var(--shell-w);" in screens
    assert "max-width: 430px" not in screens


def test_the_tablet_tier_is_a_real_composition() -> None:
    """481–899 is not a stretched 430: the shell widens to 600, the cover
    letter centers as a 560 sheet, and the two-column containers take
    their grids (family groups with the filter spanning full width;
    the homogeneous panels). The walkthrough-killed form (.ledger-cols,
    账|为什么 hard-split — cramped at 768) leaves no rule behind."""

    tablet = _tier(_text("screens.css"), "481px")
    assert ":root { --shell-w: 600px; }" in tablet
    assert ".ob { display: flex; justify-content: center; }" in tablet
    assert ".ob-sheet { width: 560px; margin: auto 0; }" in tablet
    assert ".family-groups { display: grid;" in tablet
    assert "repeat(auto-fill, minmax(260px, 1fr));" in tablet
    assert (
        ".family-groups > .note, .family-groups > .field {\n"
        "                   grid-column: 1 / -1; }" in tablet
    )
    assert ".panel-grid { display: grid;" in tablet
    assert "repeat(auto-fill, minmax(264px, 1fr));" in tablet
    # the killed two-column form leaves nothing behind
    assert ".ledger-cols" not in _text("screens.css")


def test_the_tablet_two_columns_are_earned_inside_the_band() -> None:
    """The tier's own arithmetic, made executable (R-1W disposition):
    two columns must fit inside the tablet band's content ceiling
    (shell 600 − 2×read-pad 18 = 564px). The delivery's minmax(280px)
    needed 2×280+sp-6(32)=592 > 564 — a rule that could never fire on
    any tablet viewport (dead in its own band; caught only by live
    rendering). This pin reads the real token values so a future width
    edit that re-kills the tier goes RED arithmetically."""

    tablet = _tier(_text("screens.css"), "481px")
    tokens = _text("tokens.css")
    shell_w = int(re.search(r"--shell-w: (\d+)px", tablet).group(1))
    read_pad = int(
        re.search(r"--read-pad: (\d+)px", tokens).group(1))
    ceiling = shell_w - 2 * read_pad
    for rule in (".family-groups", ".panel-grid"):
        block = re.search(
            re.escape(rule) + r" \{[^}]*?minmax\((\d+)px, 1fr\)[^}]*\}",
            tablet, re.S)
        assert block is not None, rule
        gap_var = re.search(
            r"column-gap: var\(--sp-(\d)\)", block.group(0))
        assert gap_var is not None, rule
        gap = int(re.search(
            rf"--sp-{gap_var.group(1)}: (\d+)px", tokens).group(1))
        min_col = int(block.group(1))
        assert 2 * min_col + gap <= ceiling, (
            f"{rule}: 2×{min_col}+{gap}={2 * min_col + gap}"
            f" exceeds the tablet ceiling {ceiling}")


def test_the_wide_tier_extends_the_desk_not_the_line_length() -> None:
    """≥1280: the paper grows to 1240 and the rail to 240（v2 随迁：
    装饰邮戳水印撤除——宽档不再放大水印，只延展案头与边注）, while the
    reading column keeps its --measure ceiling — the wide tier never
    touches .flow/.spacebody/.dock-row."""

    screens = _text("screens.css")
    wide = _tier(screens, "1280px")
    assert ":root { --shell-w: 1240px; }" in wide
    assert "#stage { max-width: 1240px; }" in wide
    assert ".marginalia { width: 240px; }" in wide
    assert "marginalia-mark" not in wide
    for untouchable in (".flow", ".spacebody", ".dock-row"):
        assert untouchable not in wide, untouchable
    # the --measure ceiling is set once, in the desktop tier, inherited
    desktop = _tier(screens, "900px")
    assert "max-width: var(--measure);" in desktop


def test_the_homogeneous_panels_pair_up() -> None:
    """The per-page wrappers: today's 行动 + 成长 (rd-3 重排——同位网格
    从诊断五板挪到今日两块，总数不变), memory's five panels and
    settings' two blocks all ride .panel-grid. rd-3 随迁（9.11-22）：
    the five whys' grid retired with the diagnostics face (缺位钉);
    the archive face is a vertical flow (搜索/时间线/折叠不配网格).
    Id arithmetic unchanged (the JS reads the same panel ids)."""

    index = _text("index.html")
    # 旧 4（今日 + 诊断五板 + 记忆 + 设置）→ 3：诊断五板的网格随移走
    # 清单退役，今日两块的网格原本就在（rd-3 重排不变总数减一）
    assert index.count('class="panel-grid"') == 3
    # the today blocks pair up (行动 + 成长)
    today = index.split('id="study-today"', 1)[1].split(
        'id="study-goal"', 1)[0]
    assert 'class="panel-grid">' in today
    for panel in ("today-action", "growth-summary"):
        assert f'id="{panel}"' in today, panel
    assert "<h3>今天的行动</h3>" in index
    assert "<h3>你的成长</h3>" in index
    assert 'class="ledger-cols"' not in index
    # rd-3 缺位钉：诊断节容器与五板不回潮
    assert 'id="set-diagnostics"' not in index
    for panel in ("why-teach", "why-not-teach", "why-evidence",
                  "why-support", "why-degraded"):
        assert f'id="{panel}"' not in index, panel
    assert "study-progress" in index  # the panel itself survives


def test_the_family_groups_carry_the_grid_class() -> None:
    """Both family-group faces (today's practice list and privacy's
    per-expression forget list) are built by the one JS factory, and the
    factory stamps the grid class — the tablet composition reaches both
    pages through one line."""

    app = _text("app.js")
    assert 'root.className = "family-groups";' in app
    # both call sites keep their rows (the definition itself is the
    # third occurrence of the bare name; the r1r suite pins the rest)
    assert app.count("appendChild(familyGroupsBlock(list,") == 2


def test_the_keyboard_face_resizes_content() -> None:
    """The composer must not sit under the soft keyboard: the viewport
    meta asks resizes-content (engines that don't know the key ignore
    it — no fallback face), and the cover's min-height carries the
    100vh → 100dvh double declaration."""

    index = _text("index.html")
    assert (
        'content="width=device-width, initial-scale=1, viewport-fit=cover,'
        ' interactive-widget=resizes-content"' in index
    )
    screens = _text("screens.css")
    assert ".ob { min-height: 100vh; min-height: 100dvh;" in screens


# ---------------------------------------------------------------------------
# 2. the cover redo


def test_the_cover_is_a_complete_letter() -> None:
    """The cover's anatomy, top to bottom: the sheet object (paper-high
    + double hairline edge) carrying the dateline (date slot + stamp
    slot), the mark wrapper, the English wordmark, the display title,
    the short divider, the letter body (salutation / indented
    paragraphs / postscript / the door / the version line). The old
    three-step skeleton is gone."""

    page = _text("index.html")
    for marker in (
        '<section id="screen-onboard" class="ob">',
        '<div class="ob-sheet paper-settle">',
        '<p class="ob-dateline"><span class="ob-date"></span>'
        '<span class="ob-stamp" data-icon="stamp"></span></p>',
        '<div class="ob-mark seal-press">',
        # v2 命名随迁（简报 §1）：wordmark = 英文并写 Dear You 大写
        # 微标签档；display 题 = 展信佳
        '<p class="ob-wordmark">DEAR YOU</p>',
        '<h1>展信佳</h1>',
        '<span class="ob-divider" aria-hidden="true"></span>',
        '<p class="ob-salut">致 明日之我：</p>',
        'id="ob-go"',
        '<p class="ob-version">elc · web</p>',
    ):
        assert marker in page, marker
    # the old skeleton is gone — and the old brand with it
    for gone in ("ob-steps", "ob-step", "就这么定", "把英语请进客厅",
                 "THE ENGLISH PARLOUR"):
        assert gone not in page, gone


def test_the_cover_copy_is_the_new_final(tmp_path: Path) -> None:
    """The letter's copy, word for word (⑧ 8.2.1 修订版 + rd-2「致明日
    之我」豪放档), over the served union — and the retired sentences
    never leak back from any asset."""

    page = _page_of(tmp_path)
    assert "致 明日之我：" in page
    assert "致明日之我" in "".join(page.split())
    assert "今日落笔，明日展信。" in page
    assert (
        "今日落笔，明日展信。这张案头前，你同一位固定笔友通信，也在给"
        "明日之自己写信——两重收信人，同一张信纸。想写什么就写什么，"
        "中文英文都行；写错了，正是回信要讲给你听的地方。" in page
    )
    assert (
        "写着写着，它在旁听着。发现值得练的表达，它随信递来一条英文"
        "批注——答对答错都有回音，也可以先搁着。" in page
    )
    assert (
        "又及：进门以后，底部三个词随时可走。温故摊着今天的复习与方向，"
        "抽屉收着它记住的事。" in page
    )
    assert "拆开这封信 →</button>" in page
    for retired in ("一 · 这是什么", "二 · 短笺怎么来",
                    "就这么定", "跟一位固定笔友用英语通信——想写什么，"
                    "就写什么。"):
        assert retired not in page, retired


def test_the_cover_door_keeps_its_semantics(tmp_path: Path) -> None:
    """The redo never touches the door's machinery: the ob-go id, the
    localStorage gate (a refusing storage answers "seen"), the landing
    in the parlor, and the browser title staying the product name."""

    page = _page_of(tmp_path)
    assert 'id="ob-go" class="btn btn--ink" type="button"' in page
    assert 'ONBOARD_KEY = "elp.parlor.onboarded.v1"' in page
    assert 'seenOnboard() ? "parlor" : "onboard"' in page
    # v2 命名随迁（简报 §1）：题 = 展信佳
    assert "<title>展信佳</title>" in page


def test_the_cover_typography_rides_the_scale() -> None:
    """The cover is the display rung's first real customer（v2 随迁：
    display 档 34/42、宋体 400 禁合成粗体——工艺法则 2；题字距走
    --ls-display；信体行高锁 --baseline 基线网格）: the title rides
    --fs-display with --lh-display, the wordmark rides ls-caps, the
    letter rides --baseline with the 2em indents, and the sheet is the
    paper-high wash behind a double hairline edge."""

    screens = _text("screens.css")
    assert (
        ".ob h1 { margin: var(--sp-2) 0 0; text-align: center;" in screens
    )
    assert "font-family: var(--f-display);" in screens
    assert (
        "font-size: var(--fs-display); line-height: var(--lh-display);"
        in screens
    )
    assert "font-weight: 400;" in screens
    assert "letter-spacing: var(--ls-display); }" in screens
    # rd-1 随迁：wordmark 的字距走微标签配方（--meta-track 归
    # --ls-caps——链路保「西文大写微标签走 caps 字距标度」的出处）
    wordmark = screens[screens.index(".ob-wordmark {"):]
    wordmark = wordmark[:wordmark.index("}")]
    assert "letter-spacing: var(--meta-track);" in wordmark
    assert (
        ".ob-para { margin: 0 0 var(--sp-3); line-height: var(--baseline);\n"
        "           text-indent: 2em;" in screens
    )
    assert ".ob-sheet { max-width: 100%; background: var(--paper-high);" \
        in screens
    assert "outline: 1px solid var(--rule-soft); outline-offset: 4px;" \
        in screens


def test_the_cover_motions_are_registered_and_degrade() -> None:
    """The two cover motions live in the motion registry (the keyframes'
    one source) with their class toggles. v2 随迁（简报 §5）：封面双
    动画 = paper-drop + ink-wash（--dur-settle 320 封顶 + 1.3× wash）；
    印记走 ink-wash 档；旧 paper-settle/seal-press keyframes 退役，
    类名保留（消费面平滑）。both sit before the reduced-motion
    blanket — the blanket zeroing them is the only degradation they
    need."""

    css = _text("components.css")
    assert (
        ".paper-settle { animation: paper-drop var(--dur-settle)"
        " var(--ease-paper)" in css
    )
    assert ".seal-press { animation: ink-wash var(--dur-ink)" in css
    blanket_at = css.index("@media (prefers-reduced-motion: reduce) {\n"
                           "  *, *::before, *::after {")
    for keyframes in ("@keyframes paper-drop {", "@keyframes ink-wash {"):
        assert css.index(keyframes) < blanket_at, keyframes
    for retired in ("@keyframes paper-settle {", "@keyframes seal-press {"):
        assert retired not in css, retired
    # the classes are on the sheet and the mark (the one-shot entrance)
    index = _text("index.html")
    assert 'class="ob-sheet paper-settle"' in index
    assert 'class="ob-mark seal-press"' in index


def test_the_stamp_icon_is_registered_the_four_step_way() -> None:
    """The ink icon, registered everywhere the set is spelled:
    the template geometry (one 20×20 grid, no stroke of its own), the
    live anchor on the cover's dateline, the contract block's roster
    and the spec's ③ row + ⑨-4 roster. The set stays one component
    (the icons are its members; rd-4 随迁：partner-card 入库 → 23；
    v2 随迁：水印圆戳出集，八枚 → 七枚)."""

    from tests.host.test_fg1_architecture import COMPONENTS

    assert len(COMPONENTS) == 23
    index = _text("index.html")
    assert (
        '<svg id="icon-stamp" class="inkicon" viewBox="0 0 20 20" '
        'aria-hidden="true"><rect x="4" y="4" width="12" height="12"/>' in
        index
    )
    assert 'data-icon="stamp"' in index
    css = _text("components.css")
    assert "现役七枚" in css
    assert "stamp（门厅封面邮票角标 + 教学卡结课邮票）" in css
    spec = _spec()
    assert 'postmark\\|stamp"' in spec   # the ③ row's template id list
    assert "现役八枚与锚位" in spec     # ⑨-4's roster（冻结面，v2 集内
    # 收缩由 components.css 契约块承载——spec 更新属下一程序）


def test_the_cover_date_is_real_client_data() -> None:
    """The dateline is the same mechanical fact the marginalia carries:
    the client's own date, landed as textContent — zero fabricated
    data, zero copy."""

    app = _text("app.js")
    assert 'document.querySelector(".ob-date")' in app
    assert "coverDate.textContent = coverToday.getFullYear()" in app


def test_the_spec_carries_the_breakpoint_system_and_revisions() -> None:
    """The rewritten ⑨-6 (four tiers over the pinned boundaries, the
    revoked mid-tier registration) and the 9.8 revision register's
    three entries; 8.2.1 carries the R-1W revision marker."""

    spec = _spec()
    assert "### 9.6 断点系统（R-1W 重写版：全断点响应式）" in spec
    for tier_word in ("手机", "平板", "桌面", "宽屏"):
        assert tier_word in spec, tier_word
    assert "延展的是案头与边注，不是行长" in spec
    assert "### 9.8 R-1W 修订登记" in spec
    assert "16. **⑨-6 重写为四档断点系统**" in spec
    assert "17. **门厅完全重做（⑧ 8.2.1 修订版）**" in spec
    assert "18. **#22 增枚 stamp（邮票角标）**" in spec
    assert "#### 8.2.1 门厅（R-1W 修订版——封面信笺）" in spec
    # 9.5's registry grew the two cover motions
    assert "| paper-settle 信笺落座 |" in spec
    assert "| seal-press 印记按落 |" in spec


def test_the_frozen_copy_outside_the_cover_is_verbatim(
    tmp_path: Path,
) -> None:
    """The freeze line: three of the other pages' 8.2 guide sentences,
    word for word over the served union (the r1r suite pins the rest) —
    the responsive wrappers moved divs, not words."""

    page = _page_of(tmp_path)
    for sentence in (
        "你想把英语用在哪里——这是客厅记着的长期方向。",
        # rd-3 随迁（9.11-22）：档案节引导句接任——旧账页句退役
        "批注留过的痕迹与接下来的计划——要的时候来翻。",
        "请客厅忘掉一些事——走出去就找不回来。",
        "客厅记住的事都在这里——一条条如实。",
        # rd-4 随迁（9.12-23）：设置节升真面——冻结句换诚实读法句
        "当前这一档由启动命令给定——页面读不到，也不改它。",
    ):
        assert sentence in page, sentence
