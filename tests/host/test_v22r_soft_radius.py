"""v2-2X — the radius-revert knife (圆角回退刀: the v2-2R scale undone).

The user ruling (2026-10-02, verbatim): 「改回去吧，不要用圆角了，
因为你根本把握不住」— the v2-2R soft-radius knife (commit 52aa84a) is
reverted whole. Authorization chain: DEC-OPI-5033857a-…1 (the revert
ruling) → this knife. The restored truth is the v2-2 terminal corner
state (commit 517da30), i.e. the brief §6 original law back in force:
零大圆角面板（圆角收窄一档：信纸物件 ≤2px，仅邮票/邮戳圆形豁免）.

Groups (this file's own):

1. the token clearance — none of the five ``--r-*`` names appears
   anywhere in the seven webui files or the spec; tokens.css carries no
   ``border-radius`` declarations;
2. the sharp-corner restoration — eight key container faces carry no
   large radius again: their rule blocks either declare no
   border-radius at all (word-card / note-paper / pen / chip / dock /
   char-editor) or the literal ≤2px letter-object radius
   (.envsel / .env — the brief §6 增补档);
3. the counting truth — the border-radius census is back at the v2-2
   terminal values (screens 4 / components 7——veto-R 随迁：fr-A 墨点两
   声明随 #24 形态退役), the 手迹/盖印 exempt geometries survive verbatim
   (six ``50%`` seats + one ``9px 9px 0 0`` arch), and every
   literal value left is lawful (≤2px or exempt);
4. the spec revert note — ②-6 carries the revert record naming the
   user's date and the ruling verbatim; the five-tier table and the
   three revision annotations are gone; the ⑨ preamble states the
   original law again; the tokens.css headnote restores the
   zero-large-radius clause.

What the revert keeps (non-radius v2-2R work, not touched here): the
rd4 keyframes count migration 9→10 (the ``scrim-in`` keyframe added by
the v2-2 blackout fix — pinned in test_rd4_full_face.py) and the
b34a561 disposition edits.
"""

from __future__ import annotations

import re

from tests.host.test_fg1_architecture import REPO_ROOT, _webui_all_text, _webui_text

TOKENS = "tokens.css"
COMPONENTS = "components.css"
SCREENS = "screens.css"

#: The five v2-2R soft-radius token names — all of them must be gone
#: from the webui and the spec.
RETIRED_TOKEN_NAMES: tuple[str, ...] = (
    "--r-paper",
    "--r-raise",
    "--r-sheet-top",
    "--r-ctl",
    "--r-pill",
)

#: The exempt geometries: the postmark / red-pen-circle / stamp-graphic
#: seats (v2's 手迹/盖印豁免位 — circles and the arch are not panel
#: radii and live outside the ≤2px letter-object scale).
EXEMPT_RADIUS_VALUES = frozenset({"50%", "9px 9px 0 0"})

#: The lawful literal radius values after the revert: the brief §6
#: letter-object scale (≤2px; 0 forms included for normalization) or an
#: exempt geometry. Anything else — above all any --r-* var() form — is
#: a violation of the revert ruling.
LAWFUL_RADIUS_VALUES = frozenset({"0", "0px", "2px"}) | EXEMPT_RADIUS_VALUES


def _rule_block(css: str, selector: str) -> str:
    """The first rule block whose selector line starts with ``selector``
    (newline-anchored — ``.env`` must not catch ``.envsel``), braces
    balanced."""

    at = css.index("\n" + selector)
    open_brace = css.index("{", at)
    depth = 0
    for i in range(open_brace, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[open_brace : i + 1]
    raise AssertionError(f"unbalanced braces after {selector!r}")


def _radius_values_of(block: str) -> list[str]:
    """The block's border-radius values (normalized whitespace)."""

    found = re.findall(r"border-radius:\s*([^;]+);", block)
    return [" ".join(v.split()) for v in found]


def _spec() -> str:
    return (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. the token clearance


def test_the_five_soft_radius_tokens_are_gone() -> None:
    """Token clearance: none of the five --r-* names appears anywhere in
    the seven webui files (tokens.css first of all — the scale's physical
    seat is deleted), and tokens.css carries no border-radius property at
    all (it declares custom properties, not rules)."""

    tokens = _webui_text(TOKENS)
    for name in RETIRED_TOKEN_NAMES:
        assert name not in tokens
    assert "border-radius" not in tokens
    everything = _webui_all_text()
    for name in RETIRED_TOKEN_NAMES:
        assert name not in everything, f"{name} survived the revert"


def test_no_radius_declaration_consumes_a_token() -> None:
    """The consumer-side sweep: every border-radius value left in the
    webui is a literal lawful value — no var(--r-*) form survives."""

    values = _radius_values_of(_webui_all_text())
    assert values != []  # the census below pins the exact count
    for value in values:
        assert "--r-" not in value, f"token consumer survived: {value}"


# ---------------------------------------------------------------------------
# 2. the sharp-corner restoration (the eight key faces)


def test_eight_key_container_faces_carry_no_large_radius() -> None:
    """直角恢复: the eight key container faces named by the revert knife
    are back at the v2-2 terminal state — six bare (no border-radius at
    all) and two letter-object seats at the literal ≤2px scale."""

    components = _webui_text(COMPONENTS)
    screens = _webui_text(SCREENS)
    bare_in_components = [
        (".word-card {", "词卡浮卡"),
        (".note-paper {", "批注卡"),
        (".pen {", "稿纸 textarea"),
        (".chip {", "词表片"),
    ]
    for selector, label in bare_in_components:
        block = _rule_block(components, selector)
        assert _radius_values_of(block) == [], (
            f"{label} ({selector}) must be bare after the revert"
        )
    bare_in_screens = [
        (".dock {", "写信区垫板"),
    ]
    # v3-2 随迁：.char-editor 独立全页随编辑台容器化退役（同刀除名）
    # ——编辑台的新居所是沓容器（.envsel，下行 2px 信纸物件档照钉）；
    # 本名单不再有「编辑台容器」这一独立面。
    assert ".char-editor" not in screens
    for selector, label in bare_in_screens:
        block = _rule_block(screens, selector)
        assert _radius_values_of(block) == [], (
            f"{label} ({selector}) must be bare after the revert"
        )
    # the two letter-object seats: the brief §6 增补档 (≤2px), verbatim
    assert _radius_values_of(_rule_block(screens, ".envsel {")) == ["2px"]
    assert _radius_values_of(_rule_block(screens, ".env {")) == ["2px"]


def test_the_sheet_tier_and_dock_pad_stay_bare() -> None:
    """The two v2-2R signature faces are fully undone: the bottom-sheet
    form of .word-card (inside @media (hover: none)) declares no radius
    and .dock carries no top-corner padding — 底缘平接恢复原状."""

    components = _webui_text(COMPONENTS)
    at = components.index("\n@media (hover: none) {")
    open_brace = components.index("{", at)
    depth = 0
    end = open_brace
    for i in range(open_brace, len(components)):
        if components[i] == "{":
            depth += 1
        elif components[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    sheet_block = components[open_brace:end]
    assert _radius_values_of(sheet_block) == []


# ---------------------------------------------------------------------------
# 3. the counting truth


def test_the_radius_census_is_back_at_the_v22_terminal_truth() -> None:
    """The census: components 7 + screens 4 = the v2-2 terminal state
    again（veto-R 随迁：fr-A 的墨点两枚豁免随 #24 形态退役——用户否决
    圆形墨点，豁免集合回到「仅邮票/邮戳圆形」，9 → 7）。The exempt
    geometries survive verbatim: the six
    50% seats (the red-pen ellipse, the postmark pair, the 「当前」 mark
    pair, the stamp ring) plus the stamp-v5
    arch. Every literal value left is ≤2px or exempt."""

    components = _webui_text(COMPONENTS)
    screens = _webui_text(SCREENS)
    assert components.count("border-radius") == 7
    assert screens.count("border-radius") == 4
    assert components.count("border-radius: 50%") == 6
    assert "border-radius: 9px 9px 0 0;" in components
    values = _radius_values_of(_webui_all_text())
    strangers = [v for v in values if v not in LAWFUL_RADIUS_VALUES]
    assert strangers == []


# ---------------------------------------------------------------------------
# 4. the spec revert note


def test_spec_carries_the_revert_record_and_the_restored_law() -> None:
    """②-6 is the revert record: it names the user's date and the ruling
    verbatim and states the restored brief §6 law. The five-tier table
    and every --r-* mention are gone; the ⑨ preamble states the original
    law again."""

    spec = _spec()
    assert "### ②-6 圆角法则（2026-10-02 回退记录）" in spec
    assert "被用户否决回退" in spec
    assert "改回去吧，不要用圆角了" in spec
    assert "零大圆角面板" in spec
    assert "### ②-6 圆角五档" not in spec
    for name in RETIRED_TOKEN_NAMES:
        assert name not in spec
    assert "圆角 v2 收窄一档：信纸物件 ≤2px，仅邮票/邮戳圆形" in spec


def test_tokens_headnote_restores_the_zero_large_radius_law() -> None:
    """tokens.css's header asserts the zero-large-radius clause as law
    again (not as retired) and carries the revert note — a header still
    framing the clause as retired would contradict the sheet below it."""

    tokens = _webui_text(TOKENS)
    assert "零大圆角面板（圆角收窄一档：信纸物件 ≤2px，仅邮票/邮戳圆形）" in tokens
    assert "2026-10-02 回退记录" in tokens
    assert "圆角五档尝试被用户否决回退" in tokens
    assert "柔和圆角" not in tokens
