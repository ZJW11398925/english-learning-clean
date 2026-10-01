"""ux-1 — the usability cut（可用性刀）, pinned.

用户原话（最高权威）两则：① 返回按钮等重要按钮未常显在可快捷定位的
位置（不因页面滚动被遮挡），温故/抽屉顶部的节签同病，且移动端最好
支持左右滑动切换面板；② 移动端单词卡无法触发。六组钉：

1. **the sticky faces** — the two back rows (the dossier's 「回案头」
   and the character editor's 「回沓」) and the section-tab bars stick
   (the dossier bar and the tab bars right under the 46px brand bar —
   the arithmetic lives in the same source; the editor bar at the top
   of its own scroll well), and the goal save rides a sticky bottom
   dock-height bar (the one survey-confirmed scroll-lost action button
   in 温故/抽屉);
2. **the swipe switcher** — the touch recognition lives in one factory
   (wirePanelSwipe) with the 48px threshold constant, the strict
   |dx| > |dy| discrimination, the tab-DOM panel order, the adjacent
   switch with boundary guards, zero preventDefault (passive listeners
   only — vertical scroll is untouched) and the two app.js wirings;
   the tabs stay the primary face (the r1_shell lines still stand);
3. **the paper nudge** — the 12px (--sp-3) directional offset with the
   140ms (--dur-1) return transition on the spacebody base, classes
   landed/removed by the factory;
4. **the word card trio** — the hit-area widening with the negative
   margin compensation in the SAME block (the p1 single-source shape,
   zero reflow), the (hover: none) touch mirror of the dotted
   affordance (no :hover selector — the rd1 discipline), and the
   nearest-word caret fallback wired behind the exact fast path with
   the silent-miss contract kept;
5. **the who-block press** — the opacity half-key on :active (outside
   the hover wrapper, per the touch discipline);
6. **the migration ledger + the design law** — the p1 ".word {"
   exactly-once pin re-read as exactly-two-in-one-file (base + touch
   mirror), and the sticky faces carry zero new color values (no hex
   literal exists outside tokens.css — unchanged).
"""

from __future__ import annotations

import re
from pathlib import Path

import elc.web

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = Path(elc.web.__file__).parent / "webui"


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _block(css: str, head: str) -> str:
    """One declaration block: from the selector head to its closing
    brace (the shape-source pins read the block, not the whole file)."""

    at = css.index(head)
    return css[at:css.index("}", at)]


#: The 46px arithmetic, verbatim in both sources that consume it —
#: the brand bar's height (10 top pad + 26 head line + 8 bottom pad
#: + 2 hairline borders) that the tab bars and the dossier back row
#: stick under.
BAR_ARITHMETIC = "10 上距 + 26 行高 + 8 下距 + 2 发丝边"


# ---------------------------------------------------------------------------
# 1. the sticky faces


def test_the_tab_bars_stick_under_the_brand_bar() -> None:
    """The section-tab bar (one definition, components.css) is a sticky
    face: paper ground, bottom hairline, pinned right under the brand
    bar with the height arithmetic stated in the same source; the z
    order sits under the bar (5) and over the body."""

    css = _text("components.css")
    block = _block(css, ".section-tabs {")
    assert "position: sticky; top: 46px; z-index: 4;" in block
    assert "background: var(--bg);" in block
    assert "border-bottom: 1px solid var(--rule-soft);" in block
    assert BAR_ARITHMETIC in css


def test_the_dossier_back_row_sticks() -> None:
    """The dossier's 「← 回案头」 row (screens.css) sticks right under
    the brand bar on the full-page view — the only way back never
    scrolls away; paper ground, arithmetic in the same source."""

    screens = _text("screens.css")
    block = _block(screens, ".dossier-back {")
    assert "position: sticky; top: 46px; z-index: 4;" in block
    assert "background: var(--bg);" in block
    assert BAR_ARITHMETIC in screens


def test_the_editor_back_row_sticks_in_its_own_well() -> None:
    """The character editor's 「← 回沓」 row sticks at the top of the
    editor's own scroll well (the fixed page is the scroller), on the
    editor's paper — the row app.js builds stays the anchor."""

    screens = _text("screens.css")
    block = _block(screens, ".editor-back {")
    assert "position: sticky; top: 0; z-index: 2;" in block
    assert "background: var(--paper);" in block
    app = _text("app.js")
    assert 'back.className = "editor-back";' in app


def test_the_goal_save_is_the_one_sticky_action_dock() -> None:
    """保存方向 — the survey's one scroll-lost action button in
    温故/抽屉 — rides a sticky bottom bar held above the standing nav
    dock; paper ground, the .sec's own top hairline separates."""

    screens = _text("screens.css")
    block = _block(screens, "#goal-save {")
    assert "position: sticky; bottom: var(--navdock-h); z-index: 3;" in block
    assert "background: var(--bg);" in block


# ---------------------------------------------------------------------------
# 2. the swipe switcher


def _swipe_factory() -> str:
    js = _text("components.js")
    return js.split("export function wirePanelSwipe(space, onSelect) {", 1)[1]


def test_the_swipe_threshold_and_discrimination_are_one_source() -> None:
    """The 48px threshold is a named constant next to the factory, and
    the release verdict requires it AND a strictly greater horizontal
    displacement (the `<=` rejection form pins the strict law — a tie
    belongs to the vertical scroll)."""

    js = _text("components.js")
    assert "const SWIPE_MIN_PX = 48;" in js
    factory = _swipe_factory()
    assert (
        "if (Math.abs(dx) < SWIPE_MIN_PX "
        "|| Math.abs(dx) <= Math.abs(dy)) {" in factory
    )


def test_the_swipe_switches_the_adjacent_panel_with_guards() -> None:
    """The panel order is read from the tab DOM (single source), the
    direction maps left→next / right→prev, the boundary guards keep the
    ends quiet, and the switch lands on the caller's onSelect — the
    same showSection the tabs drive."""

    factory = _swipe_factory()
    assert 'const order = tabs.map((tab) => tab.dataset.section);' in factory
    assert "const next = at + (dx < 0 ? 1 : -1);" in factory
    assert "if (at < 0 || next < 0 || next >= order.length) return;" in factory
    assert "onSelect(order[next]);" in factory


def test_the_swipe_never_hijacks_the_scroll() -> None:
    """Zero preventDefault anywhere in the factory, every listener
    passive, and the recognition stands down on interactive starts and
    the one horizontal scroll surface (pre) — vertical scrolling and
    button taps keep their default lives."""

    factory = _swipe_factory()
    assert ".preventDefault(" not in factory
    assert factory.count("{ passive: true }") == 3
    assert (
        '!event.target.closest("button, a, input, textarea, select, pre")'
        in factory
    )


def test_the_swipe_is_wired_for_both_spaces_as_a_supplement() -> None:
    """app.js wires the swipe for 温故 and 抽屉 onto the same
    showSection — and the tab wirings (the primary face) still stand,
    so the swipe only ever adds a second way to do the same thing."""

    app = _text("app.js")
    assert 'wirePanelSwipe("study", (name) => showSection("study", name));' \
        in app
    assert 'wirePanelSwipe("drawer", (name) => showSection("drawer", name));' \
        in app
    assert 'wireSectionTabs(document.getElementById("study-tabs"),' in app
    assert 'wireSectionTabs(document.getElementById("drawer-tabs"),' in app


# ---------------------------------------------------------------------------
# 3. the paper nudge


def test_the_nudge_is_paper_physics_on_the_spacebody() -> None:
    """The directional offset is 12px (--sp-3) and the return rides the
    base transition (--dur-1, --ease-paper — the 100–200ms band, zero
    new keyframes); the factory lands exactly one directional class and
    removes both on the matching transitionend."""

    screens = _text("screens.css")
    base = _block(screens, ".spacebody {")
    assert "transition: transform var(--dur-1) var(--ease-paper);" in base
    assert (
        ".spacebody.panel-nudge--next "
        "{ transform: translateX(calc(var(--sp-3) * -1)); }" in screens
    )
    assert (
        ".spacebody.panel-nudge--prev "
        "{ transform: translateX(var(--sp-3)); }" in screens
    )
    factory = _swipe_factory()
    assert (
        'body.classList.add(dx < 0 ? "panel-nudge--next" '
        ': "panel-nudge--prev");' in factory
    )
    assert (
        'body.classList.remove("panel-nudge--next", "panel-nudge--prev");'
        in factory
    )
    assert 'fe.propertyName !== "transform"' in factory


# ---------------------------------------------------------------------------
# 4. the word card trio


def test_the_word_hit_area_widens_with_zero_reflow_in_one_block() -> None:
    """The .word block (the p1 single-source shape) carries the 5px/2px
    padding with the exact negative margin compensation in the SAME
    block — the inline-box identity (vertical padding outside the line
    box, horizontal padding cancelled by margin) is the zero-reflow
    proof; splitting the block or dropping either half is red."""

    css = _text("components.css")
    block = _block(css, ".word {")
    assert "padding: 5px 2px; margin: -5px -2px;" in block
    assert "cursor: pointer;" in block


def test_the_touch_affordance_mirrors_the_hover_dots() -> None:
    """The (hover: none) half carries the same dotted affordance for the
    letter words — no :hover selector (the rd1 pointer-only law is
    untouched), same pencil-soft color and offset as the hover face."""

    css = _text("components.css")
    at = css.index("@media (hover: none) {")
    mirror = css[at:css.index("}", at)]
    assert ".say .word { text-decoration: underline dotted;" in mirror
    assert "text-decoration-color: var(--pencil-soft);" in mirror
    assert "text-underline-offset: 0.24em;" in mirror
    assert ":hover" not in mirror


def test_the_nearest_word_fallback_wires_behind_the_fast_path() -> None:
    """The caret fallback (both APIs, standard last) resolves the tap
    into the letter's .say and takes the nearest word centre; it only
    engages when the precise path missed, and the silent-miss contract
    stands (no caret, no letter say, no word → quiet return)."""

    app = _text("app.js")
    assert "function wordFromCaret(event) {" in app
    assert 'doc.caretRangeFromPoint(event.clientX, event.clientY)' in app
    assert 'doc.caretPositionFromPoint(event.clientX, event.clientY)' in app
    assert 'holder.closest(".letter .say")' in app
    assert "const d = dx * dx + dy * dy;" in app
    # the fallback sits behind the exact fast path
    assert 'if (!target.classList.contains("word")) {' in app
    assert "target = wordFromCaret(event);   // 兜底：点在字身框之外" in app
    assert "if (!target) return;" in app


# ---------------------------------------------------------------------------
# 5. the who-block press


def test_the_who_block_presses_like_the_text_links() -> None:
    """The clickable who block answers :active with the text-link opacity
    half-key, outside the hover wrapper (the touch discipline)."""

    css = _text("components.css")
    assert "#space-parlor .top > div:active { opacity: 0.55; }" in css


# ---------------------------------------------------------------------------
# 6. the migration ledger + the design law


def test_the_p1_word_single_source_pin_reads_two_in_one_file() -> None:
    """The ux-1 migration of the p1 exactly-once pin: ".word {" now
    occurs exactly twice — the base block and the touch mirror — and
    both live in components.css (the one physical source survives;
    test_p1_today_wordcards carries the same re-read)."""

    css = _text("components.css")
    assert css.count(".word {") == 2
    whole = "\n".join(
        _text(name) for name in (
            "index.html", "tokens.css", "components.css", "screens.css",
            "api.js", "components.js", "app.js",
        )
    )
    assert whole.count(".word {") == 2


def test_the_sticky_faces_carry_zero_new_color_values() -> None:
    """The design law, mechanical: no hex color literal exists anywhere
    in the two style sheets — the sticky faces (and everything else)
    speak only in var(); tokens.css stays the one physical source."""

    for name in ("components.css", "screens.css"):
        body = _text(name)
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", body) is None, name
