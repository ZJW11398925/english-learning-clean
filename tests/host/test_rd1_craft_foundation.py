"""rd-1 — the craft-foundation deepening (视觉工艺地基深化), pinned.

The redesign program's first implementation cut, ahead of any taste
call: it lays the *mechanics* the taste layers will spend. Six faces,
each pinned here over the served union (the F-G1 reading) and the
files on disk:

1. **the micro-label recipe** — the meta positions (timestamps, status
   words, counts, ids, the version line, dates) wear one token recipe
   (small size + tracking + warm gray; the mono role for time/id/count)
   instead of restated literals; colored badges stay retired;
2. **the motion foundation** — Material state layers (hover .08 /
   focus .12 / press .12, pseudo-element washes that never move
   layout) over the six interactive families; the enter/exit easing
   split; the 100ms feedback law (every feedback transition on
   --dur-micro); @starting-style for the transient inserts; the
   pointer-only hover discipline (@media (hover: hover));
3. **the four paper-motion families** — the letter settling onto the
   desk (view switch, 320), the note handed over (240), the stamp
   press (120, a transform snap — not a projection), the drawer
   opening/closing (280 in / 200 out) — registered in spec ⑨-5;
4. **the reveal choreography** — data-reveal + an observer that only
   adds a class, the --i stagger (step 40ms, first 8 items only —
   the 320ms cap), backwards fill;
5. **the two-sided reduced-motion law** — the CSS blanket now uses the
   0.01ms trick (events still fire; delays zeroed) and the JS side
   listens to matchMedia itself and settles everything in flight;
6. **the mark randomization + the stack shadows** — the deterministic
   nth-child ladder driving the one per-screen tilted mark (the cover's
   stamp), and the ink-derived two-tier stack shadows (DEC-OPI-
   dc0ba4b6-…13 lifted the zero-shadow ban): rgba(0,0,0) never, no
   hand-written shadow literals, directions disagree.
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


def _block(css: str, head: str) -> str:
    """One declaration block: from the selector head to its closing
    brace (the recipe pins read the block, not the whole file)."""

    at = css.index(head)
    return css[at:css.index("}", at)]


def _strip_hover_blocks(css: str) -> str:
    """The css with every `@media (hover: hover)` block removed — the
    corpus over which the pointer-only law is asserted (no :hover may
    live outside the wrapper)."""

    marker = "@media (hover: hover) {"
    out = []
    i = 0
    while True:
        at = css.find(marker, i)
        if at < 0:
            out.append(css[i:])
            break
        out.append(css[i:at])
        depth = 0
        j = at + len(marker) - 1
        while j < len(css):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        i = j + 1
    return "".join(out)


# ---------------------------------------------------------------------------
# 1. the micro-label recipe


def test_the_micro_label_recipe_is_the_one_source() -> None:
    """The recipe lives in tokens.css (the ② one-source discipline) and
    is registered in the spec's ② table: the sans role (size + weight
    + line height), the mono role, the tracking and the warm gray —
    every one referencing the existing scales, none self-valued."""

    tokens = _text("tokens.css")
    for declaration in (
        "--meta-font: 500 var(--fs-micro)/var(--lh-ui) var(--f-sans);",
        "--meta-mono: var(--fs-micro)/var(--lh-ui) var(--f-mono);",
        "--meta-track: var(--ls-caps);",
        "--meta-ink: var(--ink-faint);",
    ):
        assert declaration in tokens, declaration
    spec = _spec()
    for row in ("| `--meta-font` |", "| `--meta-mono` |",
                "| `--meta-track` |", "| `--meta-ink` |"):
        assert row in spec, row


def test_the_meta_positions_wear_the_recipe() -> None:
    """Every meta position wears the recipe instead of restating the
    literals: the sans role for status words / section labels / part
    of speech / the section slot / the wordmark, the mono role for the
    raw values / the examples / the dates / the version line."""

    sans = (
        ("components.css", ".noteline {"),
        ("components.css", ".sysline {"),
        ("components.css", ".wc-pos {"),
        ("components.css", ".sec h3 {"),
        ("components.css", ".space-header .spacehead-sec {"),
        ("screens.css", ".ob-wordmark {"),
    )
    mono = (
        ("components.css", ".rawtag {"),
        ("components.css", ".disclosure-examples {"),
        ("screens.css", ".ob-date {"),
        ("screens.css", ".ob-version {"),
    )
    for name, head in sans:
        assert "font: var(--meta-font);" in _block(_text(name), head), head
    for name, head in mono:
        assert "font: var(--meta-mono);" in _block(_text(name), head), head
    # v2 随迁（简报 T1 楷体边界）：案头日期 = 楷体手迹位（三合法面之
    # 一）——从 mono 配方位迁为 hand 位（真实日期不变，载体换手迹）
    date_block = _block(_text("screens.css"), ".marginalia-date {")
    assert "font-family: var(--f-hand);" in date_block
    assert "font-size: var(--fs-hand);" in date_block


def test_colored_badges_stay_retired(tmp_path: Path) -> None:
    """The badge retirement holds: status differences are said in words
    first and color second — no ochre-filled pill background anywhere
    in the served union (the chip's --on ink fill is the single
    registered exception to the no-fill law, and it is ink, not
    ochre)."""

    page = _page_of(tmp_path)
    for shade in ("--pencil", "--pencil-deep", "--pencil-soft"):
        assert f"background: var({shade}" not in page, shade


# ---------------------------------------------------------------------------
# 2. the motion foundation


def test_the_state_layers_cover_the_interactive_families() -> None:
    """The Material state layers, paper-read: the three values in the
    token sheet, the ::after wash group covering the six interactive
    families (link-btn, chip, navdock, section tabs, disclosure head,
    teach-me), the press and focus arms outside the hover wrapper and
    the hover arm inside it."""

    tokens = _text("tokens.css")
    for value in ("--state-hover: 0.08;", "--state-focus: 0.12;",
                  "--state-press: 0.12;"):
        assert value in tokens, value
    css = _text("components.css")
    wash = (
        ".btn::after, .chip::after, .navdock-item::after, "
        ".section-tab::after,\n.disclosure-head::after, "
        ".teach-me::after {"
    )
    assert wash in css
    for arm in (".btn:active::after,", ".btn:focus-visible::after,",
                ".btn:hover::after,"):
        assert arm in css, arm
    assert "transition: opacity var(--dur-micro) var(--ease-press); }" \
        in css


def test_hover_affordances_are_pointer_only() -> None:
    """The touch discipline: every :hover rule lives inside a
    `@media (hover: hover)` wrapper — strip the wrappers and no
    :hover selector survives (the press/focus arms stay outside,
    where touch needs them). The screen sheet owns no hover face at
    all; the library carries the one set of wrappers."""

    css = _text("components.css")
    assert "@media (hover: hover) {" in css
    assert ":hover" not in _strip_hover_blocks(css)
    screens = _text("screens.css")
    assert ":hover" not in screens
    # the classic affordances are all wrapped (spot the six families)
    for head in (".btn--ink:hover,", ".teach-me:hover {",
                 ".chip:not(.chip--on):hover {", ".navdock-item:hover {",
                 ".section-tab:hover {", ".disclosure-head:hover {",
                 ".word:hover {"):
        assert head in css, head


def test_the_enter_exit_tiers_exist() -> None:
    """Enter and exit are separate curves and durations (enter is
    longer): the tokens exist（v2 随迁，简报 §5：--dur-note 260 /
    --dur-panel-in 280 / --dur-ink 360 = opacity 恒慢 ≈1.3× /
    --dur-wet 600 墨水物理 / --dur-settle 320 封顶）, and the drawer
    family consumes the enter tier through @starting-style. The exit
    tier stays registered but deliberately unwired at the container:
    the live walkthrough wedged the opacity at 0 whenever the
    allow-discrete display transition shared a frame with an ancestor's
    display toggle — the guard below keeps that poison form out of the
    panel rules."""

    tokens = _text("tokens.css")
    for value in ("--dur-micro: 100ms;", "--dur-stamp: 120ms;",
                  "--dur-note: 260ms;", "--dur-panel-in: 280ms;",
                  "--dur-ink: 360ms;", "--dur-wet: 600ms;",
                  "--dur-panel-out: 200ms;", "--dur-settle: 320ms;",
                  "--ease-enter: cubic-bezier(0.05, 0.7, 0.1, 1);",
                  "--ease-exit: cubic-bezier(0.3, 0, 1, 1);"):
        assert value in tokens, value
    # the entry law: opacity rides its own, slower token family and the
    # 1.3× rule is expressed where it is consumed
    assert "--dur-ink: 360ms;" in tokens  # 280 × ≈1.3
    screens = _text("screens.css")
    panel = screens[screens.index('[role="tabpanel"]'):]
    panel = panel[:panel.index("@starting-style")]
    assert (
        "transition: opacity var(--dur-panel-in) var(--ease-enter);"
        in panel
    )
    assert "allow-discrete" not in panel
    assert "display" not in panel
    # the exit tier stays registered in the spec (unwired, revisited)
    assert "--dur-panel-out" in _spec()


def test_the_transient_receipts_transition_on_first_render(
    tmp_path: Path,
) -> None:
    """@starting-style gives the dynamically inserted receipts their
    first-render transition (typing / system / failure lines and the
    two strips inside the parlor) — engines without it just show them
    (the progressive-enhancement law). The letters and notes do NOT
    ride it: their entrances are the JS-gated classes that keep the
    history backfill still."""

    screens = _text("screens.css")
    group = ("#space-parlor :is(.typing, .sysline, .errline, "
             ".busystrip,\n                  .resultstrip)")
    assert group in screens
    assert screens.count("@starting-style {") == 2  # receipts + panels
    # the gated entrances stay exactly where the r1v suite pins them
    #（v2 随迁：新信入场 = 双动画类 + 墨水物理类一起挂）
    js = _text("components.js")
    assert 'node.classList.add("flow-enter", "ink-wet");' in js
    assert '" note-paper--enter"' in js


# ---------------------------------------------------------------------------
# 3. the four paper-motion families


def test_the_paper_motion_families_are_wired() -> None:
    """The families land on real surfaces（v2 随迁，简报 §5）：the
    parlor's flow washes in（容器只走透明度——settle 的 transform 会
    让 fixed 写信区改挂本节的坑在册）, the note arrival rides the
    --dur-note tier, the stamp press has its class and keyframes (a
    transform snap, no blur), and the JS drops the class once with an
    animationend cleanup."""

    screens = _text("screens.css")
    assert "#space-parlor:not([hidden]) .flow {" in screens
    assert (
        "animation: ink-wash var(--dur-settle) var(--ease-enter)"
        " both;" in screens
    )
    css = _text("components.css")
    assert (
        ".note-paper--enter { animation: paper-drop var(--dur-note)"
        in css
    )
    assert (
        ".stamp-press { animation: stamp-press var(--dur-stamp)"
        " var(--ease-press)" in css
    )
    assert "@keyframes stamp-press {" in css
    assert "from { transform: scale(0.96); }" in css
    app = _text("app.js")
    assert 'stamp.classList.add("stamp-press");' in app
    assert 'stamp.classList.remove("stamp-press")' in app


def test_the_reveal_choreography_caps_the_stagger() -> None:
    """The entrance choreography: the shell carries data-reveal on the
    six tabpanels; the observer lives in components.js and only adds
    the class plus the --i indexes (step 40ms, first 8 items only —
    the 320ms cap); the CSS formula consumes --i with a backwards
    fill; app.js wires it once at startup."""

    index = _text("index.html")
    assert index.count("data-reveal") == 6
    screens = _text("screens.css")
    assert "[data-reveal].is-revealed > .sec," in screens
    assert "animation-delay: calc(var(--i, 0) * 40ms);" in screens
    js = _text("components.js")
    assert "const REVEAL_STAGGER_MS = 40;" in js
    assert "const REVEAL_STAGGER_MAX = 8;" in js
    assert "new IntersectionObserver(" in js
    assert 'container.classList.add("is-revealed");' in js
    assert 'item.style.setProperty("--i", String(index));' in js
    app = _text("app.js")
    assert "wireReveal(document);" in app


def test_reduced_motion_is_enforced_on_both_sides() -> None:
    """The two-sided law: the CSS blanket uses the 0.01ms trick (the
    r1v suite pins its exact text) and the JS side listens to the
    media query itself — reduce settles every container and stops the
    in-flight orchestration (CSS media queries cannot reach JS)."""

    js = _text("components.js")
    assert 'window.matchMedia(\n  "(prefers-reduced-motion: reduce)")' \
        in js
    assert 'REDUCED_MOTION.addEventListener("change"' in js
    assert "observer.disconnect();" in js
    app = _text("app.js")
    assert "prefers-reduced-motion" not in app  # one listener, one home


# ---------------------------------------------------------------------------
# 4. the registry, the marks and the stack shadows


def test_the_spec_registers_the_families_and_the_tokens() -> None:
    """The ⑨-5 registry grew the rd-1 rows (each with its trigger,
    duration × curve and reduced-motion degradation) and ② grew the
    token rows; the note-arrive row carries the re-tiered duration."""

    spec = _spec()
    for row in ("| state-layer 触感层 |", "| 信纸落桌（视图切换档） |",
                "| 邮戳盖下 stamp-press |", "| 抽屉开合 drawer |",
                "| 逐行落墨 reveal stagger |",
                "| 回执首渲 @starting-style |"):
        assert row in spec, row
    arrive = spec.split("| note-arrive 批注递出 |", 1)[1].split("\n", 1)[0]
    assert "--dur-note" in arrive
    # disposition F-2 (review): the registered durations are pinned by
    # number, not just by token name — spec-global so the row header's
    # copy can be re-worded (rd-2) without breaking the pin
    assert "`--dur-note`（240ms）" in spec
    assert "总封顶 320ms" in spec
    assert "`--dur-stamp` `--dur-note` | `120ms` `240ms`" in spec
    for token in ("`--dur-micro`", "`--ease-enter` `--ease-exit`",
                  "`--state-hover`", "`--stack-shadow-soft`"):
        assert token in spec, token


def test_the_mark_randomization_is_deterministic_and_single() -> None:
    """The hand-stamped marks: the tilt/drift ride CSS custom
    properties picked from the nth-child ladder (deterministic, no JS
    re-rolls — nth-child because the icon factory swaps the tag), and
    exactly one live site per screen — the cover's stamp. v2 随迁：
    边注栏邮戳水印已撤（邮戳只落真实事件，T2）——水印不入计数的
    旧随迁句随之消失。"""

    screens = _text("screens.css")
    assert "--mark-tilt" in screens
    assert ".ob-dateline > *:nth-child(2) {" in screens
    rd1 = screens[screens.index(".ob-dateline > *:nth-child(2) {"):]
    assert "translate(var(--mark-dx, 0px), var(--mark-dy, 0px))" in rd1
    assert "rotate(var(--mark-tilt, 0deg));" in rd1
    # the watermark is gone — no un-transformed mark face survives
    assert "marginalia-mark" not in screens


def test_the_stack_shadows_are_ink_derived_and_two_tiered(
    tmp_path: Path,
) -> None:
    """The stack shadows (rd-1 face 6, DEC-OPI-dc0ba4b6-…13 lifted the
    zero-shadow ban): exactly two tiers in the token sheet, both
    ink-derived（v2 随迁：--ink 新值 #191b1e 的 rgb = 25, 27, 30——
    rgba(0,0,0) 永禁）, with disagreeing directions (soft up-right,
    deep down-left), consumed only as var() (no hand-written shadow
    literals anywhere), paired with the hairline edges; the spec
    carries the lifting registration. v2 envelope 在途信封 = soft 档
    第五处应用（#4b 信封是纸物件——与短笺同层）。"""

    tokens = _text("tokens.css")
    soft = tokens.index("--stack-shadow-soft:")
    deep = tokens.index("--stack-shadow-deep:")
    assert soft < deep
    assert tokens.count("box-shadow") == 0  # tokens declare, rules use
    assert tokens.count("rgba(25, 27, 30") == 2
    assert "rgba(27, 26, 23" not in tokens
    page = _page_of(tmp_path)
    assert "rgba(0, 0, 0" not in page
    assert "rgba(0,0,0" not in page
    css = _text("components.css")
    screens = _text("screens.css")
    # the two tiers: the stage on the desk (deep), the note on the
    # letter, the deckle underlay and the en-route envelope (soft)；
    # cs-2 随迁（4 → 3）：浮层伙伴卡的垫纸阴影随退役消失——层级值仍
    # 恰两级；mc-1 随迁（3 → 4）：信封沓的每一封带 soft 档纸叠影
    # （信封是纸物件，与在途信封同层——沓形靠它读出「一叠」）。
    assert "box-shadow: var(--stack-shadow-deep);" in screens
    assert screens.count("box-shadow: var(--stack-shadow-") == 1
    assert css.count("box-shadow: var(--stack-shadow-soft);") == 4
    assert "box-shadow: var(--stack-shadow-" in css
    # directions disagree: soft's x is positive, deep's is negative
    soft_xy = tokens[soft:].split(";", 1)[0].split(":", 1)[1].strip()
    deep_xy = tokens[deep:].split(";", 1)[0].split(":", 1)[1].strip()
    assert soft_xy.startswith("3px -3px")
    assert deep_xy.startswith("-5px 6px")
    # disposition F-1 (review): totals, not just var() forms — a
    # hand-written shadow literal (ink-coloured or not) trips these
    # （cs-2 随迁 4 → 3：浮层伙伴卡的垫纸阴影随退役消失；mc-1 随迁
    # 3 → 5：信封沓的每封 soft 档 + 空白封的 none 抵消臂——仍零手写
    # 阴影字面，两级令牌之外零自造）
    assert screens.count("box-shadow") == 1
    assert css.count("box-shadow") == 5
    spec = _spec()
    assert "「零阴影」解除登记" in spec
    assert "DEC-OPI-dc0ba4b6-…13" in spec
