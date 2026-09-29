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
   margin rule, the word-card's deckle underlay (paper shadow with no
   box-shadow — the F-1R form laws hold), the torn stitch, the pen's
   focus wash, the hover affordances.

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
    """⑨-1/9.2: the type scale (five serif, two sans), the line heights
    and letter spacings, the 4-based spacing ladder, the four paper
    washes plus the desk ground, the ochre depths, the motion tokens
    (three durations × three easings), the icon parameters and the
    shell width — every new token lives in tokens.css, the values of
    the eight legacy tokens untouched (the F-1 pin guards those)."""

    tokens = _text("tokens.css")
    for declaration in (
        # the type scale (five serif steps, two sans steps)
        "--fs-display: 27px;", "--fs-title: 21px;", "--fs-head: 17px;",
        "--fs-body: 16px;", "--fs-small: 14px;",
        "--fs-ui: 12px;", "--fs-micro: 11px;",
        # line heights and letter spacings
        "--lh-body: 1.55;", "--lh-letter: 1.75;", "--lh-ui: 1.7;",
        "--ls-title: 0.14em;", "--ls-caps: 0.18em;",
        "--ls-formhead: 0.3em;",
        # the paper washes and the desk ground
        "--paper-high: #fdfcf8;", "--paper-2: #f4efe4;",
        "--desk: #eae3d3;", "--ink-ghost: #aaa191;",
        # the ochre depths
        "--pencil-deep: #8a3f1f;", "--pencil-soft: #bb7a52;",
        # the motion tokens
        "--dur-1: 140ms;", "--dur-2: 260ms;", "--dur-3: 480ms;",
        "--ease-ink: cubic-bezier(0.22, 0.61, 0.36, 1);",
        "--ease-paper: cubic-bezier(0.16, 1, 0.3, 1);",
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
    """⑨-3: the washes are *layers* — four papers and two ochre depths,
    pairwise distinct (a flattened wash is not a layer)."""

    tokens = _text("tokens.css")
    papers = ("#fbf9f4", "#fdfcf8", "#f4efe4", "#eae3d3")
    ochres = ("#a8562f", "#8a3f1f", "#bb7a52")
    for value in papers + ochres:
        assert f": {value};" in tokens, value
    assert len(set(papers)) == 4
    assert len(set(ochres)) == 3
    # the washes sit between paper and ink — none of them is an ink
    for ink in ("#1b1a17", "#5c574e", "#726a5e"):
        assert ink not in papers + ochres


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
        "| `--dur-1` `--dur-2` `--dur-3` |",
        "| `--icon-size` `--icon-stroke` |", "| `--shell-w` |",
    ):
        assert row in spec, row
    assert "## ⑨ 视觉工艺规范" in spec
    for subsection in (
        "### 9.1 排版标度", "### 9.2 间距节奏", "### 9.3 质感与层次",
        "### 9.4 图标集契约", "### 9.5 动效注册表", "### 9.6 桌面构图",
        "### 9.7 本刀的 ③ 契约修订登记",
    ):
        assert subsection in spec, subsection
    # the motion registry names every motion with its degradation
    for word in ("ink-fade", "note-arrive", "paper-unfold",
                 "reduced-motion", "总降级块"):
        assert word in spec, word


# ---------------------------------------------------------------------------
# 2. the desktop composition


def test_the_desktop_composition_has_a_breakpoint_and_a_sheet() -> None:
    """⑨-6: ≥900px the page becomes a sheet on a desk — the breakpoint
    pin (900px exactly), the shell width rewritten to 1080px inside the
    query, the reading column at 640px, and the marginalia rail with
    its date slot and postmark watermark."""

    screens = _text("screens.css")
    assert "@media (min-width: 900px) {" in screens
    desktop = screens.split("@media (min-width: 900px) {", 1)[1]
    assert "--shell-w: 1080px;" in desktop
    assert "max-width: 1080px;" in desktop
    assert "max-width: 640px;" in desktop
    assert "background: var(--desk);" in desktop
    assert "outline: 1px solid var(--rule-soft); outline-offset: 5px;" \
        in desktop
    index = _text("index.html")
    assert '<aside class="marginalia" aria-hidden="true">' in index
    assert 'id="marginalia-date"' in index
    assert 'data-icon="postmark"' in index
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
    assert "--navdock-h: 54px;" in tokens
    screens = _text("screens.css")
    assert ".flow { padding: 18px var(--read-pad) 310px; }" in screens
    assert (
        "padding-bottom: calc(var(--navdock-h) + var(--safe-bottom));"
        in screens
    )
    assert "bottom: var(--navdock-h); z-index: 8;" in screens
    # the dock stands on the 430px column by default; 1080px only lives
    # behind the desktop media query
    assert screens.count("@media (min-width: 900px) {") == 1
    assert page.count("--shell-w: 1080px;") == 1


# ---------------------------------------------------------------------------
# 3. the icon set (#22)


def test_the_icon_set_is_registered_in_all_four_places() -> None:
    """The living-registry four steps, one cut (the word-card and
    disclosure precedents): the spec ③ row, the components.css contract
    block with its four clauses, the components.js factory pair and the
    COMPONENTS tuple."""

    from tests.host.test_fg1_architecture import COMPONENTS

    assert "icon-set" in COMPONENTS
    assert len(COMPONENTS) == 22
    assert "| 22 | icon-set" in _spec()
    css = _text("components.css")
    assert "22. icon-set" in css
    js = _text("components.js")
    assert "export function inkIcon(name) {" in js
    assert "export function installIcons() {" in js


def test_the_seven_icons_share_one_grid_and_one_stroke() -> None:
    """⑨-4: the seven ink icons live in the shell's template on one
    20×20 grid, all aria-hidden (their hosts' words carry the meaning);
    the stroke weight is the token, spelled once in components.css —
    no per-icon stroke drift, no external geometry."""

    index = _text("index.html")
    assert '<template id="icon-set-source">' in index
    for name in ("search", "chevron", "note", "write",
                 "inbox", "lamp", "postmark"):
        assert f'<svg id="icon-{name}" class="inkicon" ' \
            f'viewBox="0 0 20 20" aria-hidden="true">' in index, name
    # the grid is uniform: seven icons, seven identical viewBoxes
    assert index.count('viewBox="0 0 20 20"') == 7
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
                 "inbox", "lamp", "postmark"):
        svg = index.split(f'<svg id="icon-{name}"', 1)[1].split(
            "</svg>", 1)[0]
        assert "stroke" not in svg, name


def test_every_icon_has_a_live_anchor() -> None:
    """A registered icon is a used icon (the registry is not an attic):
    search rides the filter field's label, chevron the disclosure
    marker, note the moment card's head, write the waiting line, inbox
    the empty hall, lamp the empty state, postmark the marginalia."""

    js = _text("components.js")
    assert 'inkIcon("chevron")' in js  # disclosure's marker
    assert 'inkIcon("note")' in js  # the moment card's head
    assert 'inkIcon("lamp")' in js  # the empty state-banner
    assert 'inkIcon("write")' in js  # the （回信在途中……）line
    app = _text("app.js")
    assert 'inkIcon("search")' in app  # the filter field's label
    assert 'inkIcon("inbox")' in app  # the empty hall
    index = _text("index.html")
    assert 'data-icon="postmark"' in index  # the marginalia watermark


# ---------------------------------------------------------------------------
# 4. the motion registry


def test_the_motion_registry_and_its_class_toggles() -> None:
    """⑨-5: three keyframe motions with their class toggles — ink-fade
    on new letters (history backfill stays still), note-arrive on a new
    moment group (the poll's re-renders do not replay it), paper-unfold
    on the disclosure body — and the chevron's open-class rotation."""

    css = _text("components.css")
    for motion in ("@keyframes ink-fade {", "@keyframes note-arrive {",
                   "@keyframes paper-unfold {"):
        assert motion in css, motion
    assert (
        ".flow-enter { animation: ink-fade var(--dur-3) var(--ease-ink)"
        " both; }" in css
    )
    assert ".note-paper--enter { animation: note-arrive var(--dur-2)" in css
    assert (
        ".disclosure-body:not([hidden]) {\n"
        "            animation: paper-unfold var(--dur-2)"
        " var(--ease-paper) both; }" in css
    )
    # the toggles, JS side: new letters only (history never enters)
    js = _text("components.js")
    assert 'if (options.enter) node.classList.add("flow-enter");' in js
    assert '" note-paper--enter"' in js
    app = _text("app.js")
    assert 'addLine("user", text, { enter: true });' in app
    assert 'addLine("assistant", data.reply, { enter: true });' in app
    # the chevron rotates on the host's open class, not a glyph swap
    assert ".disclosure--open .disclosure-marker .inkicon {" in css
    assert "transform: rotate(90deg);" in css
    assert "transition: transform var(--dur-2) var(--ease-paper);" in css


def test_every_motion_degrades_under_reduced_motion() -> None:
    """The reduced-motion law: the blanket block at the library's tail
    zeroes every animation and transition, and it comes *after* every
    keyframes block (the #14 dedicated breathe arm stays as the first,
    dedicated one — double insurance)."""

    css = _text("components.css")
    blanket = (
        "@media (prefers-reduced-motion: reduce) {\n"
        "  *, *::before, *::after {\n"
        "    animation: none !important;\n"
        "    transition: none !important;\n"
        "  }\n"
        "}"
    )
    assert blanket in css
    blanket_at = css.index(blanket)
    for motion in ("@keyframes ink-fade {", "@keyframes note-arrive {",
                   "@keyframes paper-unfold {",
                   "@keyframes state-breathe {"):
        assert css.index(motion) < blanket_at, motion
    # the dedicated arm survives untouched (its own pin keeps guarding it)
    assert ".state-banner--loading::after { animation: none; }" in css


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
    face, a hairline edge and the deckle underlay 3px offset — while
    the F-1R form laws hold over the whole served union: no box-shadow,
    no border-radius, anywhere."""

    page = _page_of(tmp_path)
    assert "box-shadow" not in page
    assert "border-radius" not in page
    css = _text("components.css")
    assert (
        ".word-card { position: absolute; z-index: 9; max-width: 300px;\n"
        "             background: var(--paper-high);"
        " border: 1px solid var(--rule);" in css
    )
    assert ".word-card::after {" in css
    assert "transform: translate(3px, 3px);" in css


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
    assert ".ob .formhead::before, .ob .formhead::after {" in screens


def test_the_marginalia_date_is_real_client_data() -> None:
    """⑨-6: the rail's only words are the date — a client-derived
    mechanical fact (zero fabricated data), landed as textContent."""

    app = _text("app.js")
    assert 'document.getElementById("marginalia-date")' in app
    assert "dateSlot.textContent = today.getFullYear()" in app
    assert "installIcons();" in app
    # the brand-mark install order pin's neighborhood stays intact
    assert app.index("installBrandMarks();") < app.index("loadHistory();")
