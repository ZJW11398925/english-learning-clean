"""v2-2R — the soft-radius knife (柔和化刀: zero sharp corners webui-wide).

The user ruling (2026-10-02, verbatim): 「尽量不要使用强硬锐利的边缘，
不要留直角，学习 apple 的圆角」— the Apple-like soft radius vocabulary
replaces the brief §6 「≤2px 收窄」 clause and lifts the T3 「大圆角卡片」
ban (the other T3 bans stand). The scale was pre-fixed by the principal
(DEC-OPI-10bbc3c8-…22 ②) and is pinned here as five ``--r-*`` tokens:

====================  ======  =============================================
token                 value   faces
====================  ======  =============================================
``--r-paper``         6px     in-flow paper (letters/notes/annotation cards)
``--r-raise``         14px    raised faces (word card float/envelopes/…)
``--r-sheet-top``     16px    bottom sheet top corners (bottom edge 0)
``--r-ctl``           8px     inputs/textarea/form controls/selects
``--r-pill``          999px   chips/inline marks/solid buttons
====================  ======  =============================================

Groups (the task book's own):

1. the token seat — the five constants exist in tokens.css with the
   ruled values and the ruling annotation;
2. the single-source sweep — every ``border-radius`` declaration in the
   seven webui files consumes a ``--r-*`` token or one of the two exempt
   geometries (the postmark/red-pen ``50%`` circles and the stamp
   graphic's arch) — no literal pixel radius anywhere else;
3. the face pins — sheet top corners / float card / paper faces /
   controls / chip each consume their tier (≥1 consumer each);
4. the sharp-corner clearance — fourteen named container faces each carry
   a non-zero radius in their own rule block; the scrim stays bare and
   the text-link buttons stay bare;
5. the spec revision — ② carries the five token rows and the ruling
   note; the §6/⑨/T3 sites carry the revision annotation; the ③ rows
   for pen/note-paper/letter/word-card/field/chip note their tiers.
"""

from __future__ import annotations

import re

from tests.host.test_fg1_architecture import REPO_ROOT, _webui_all_text, _webui_text

TOKENS = "tokens.css"
COMPONENTS = "components.css"
SCREENS = "screens.css"

#: The five soft-radius tokens, name → the exact ruled value (the scale
#: is the principal's pre-fixed ruling — an executor may not retune it).
RADIUS_TOKENS: dict[str, str] = {
    "--r-paper": "6px",
    "--r-raise": "14px",
    "--r-sheet-top": "16px",
    "--r-ctl": "8px",
    "--r-pill": "999px",
}

#: The exempt geometries: the postmark / red-pen-circle / stamp-graphic
#: seats (v2's 手迹/盖印豁免位 — circles and the arch are not panel
#: radii and live outside the scale).
EXEMPT_RADIUS_VALUES = frozenset({"50%", "9px 9px 0 0"})

#: The token-consuming declaration forms lawful across the webui
#: (the dock and the flap faces round only their top corners — their
#: bottom edges sit on another surface or are clipped by a tear).
TOKEN_FORMS = frozenset(
    {"var(--r-paper)", "var(--r-raise)", "var(--r-ctl)", "var(--r-pill)",
     "var(--r-sheet-top) var(--r-sheet-top) 0 0",
     "var(--r-raise) var(--r-raise) 0 0",
     "var(--r-paper) var(--r-paper) 0 0"}
)


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


def _radius_of(block: str) -> str:
    """The block's single border-radius value (normalized whitespace)."""

    found = re.findall(r"border-radius:\s*([^;]+);", block)
    assert len(found) == 1, f"expected one radius, got {found}"
    return " ".join(found[0].split())


def _spec() -> str:
    return (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. the token seat


def test_tokens_declare_the_five_soft_radius_constants() -> None:
    """The five --r-* constants exist in tokens.css with the ruled values,
    and the block carries the user ruling that retires the brief's
    「≤2px 收窄」 clause (the annotation is the provenance of the scale)."""

    tokens = _webui_text(TOKENS)
    for name, value in RADIUS_TOKENS.items():
        assert f"{name}: {value};" in tokens
    assert "2026-10-02" in tokens
    assert "apple" in tokens
    assert "≤2px" in tokens  # the retired clause is named as retired
    assert "柔和圆角" in tokens


def test_tokens_css_stays_free_of_literal_radius_declarations() -> None:
    """tokens.css declares custom properties, not rules — the literal
    ``border-radius`` property appears nowhere in it (the scale's values
    are consumed via var() in the component files only)."""

    assert "border-radius" not in _webui_text(TOKENS)


# ---------------------------------------------------------------------------
# 2. the single-source sweep


def test_every_radius_declaration_consumes_the_tokens_or_exempts() -> None:
    """The sweep: every border-radius value across the seven webui files
    is one of the five token forms (including the top-corner-only forms)
    or one of the two exempt geometries — a literal pixel radius outside
    the scale is a violation of the ruling's own single-source law."""

    values = re.findall(
        r"border-radius:\s*([^;]+);", _webui_all_text()
    )
    normalized = [" ".join(v.split()) for v in values]
    lawful = TOKEN_FORMS | EXEMPT_RADIUS_VALUES
    strangers = [v for v in normalized if v not in lawful]
    assert strangers == []
    # and the knife's own census: 33 declarations = components 23 +
    # screens 10 (the migrated counting truth of the v2-2R cut)
    assert len(normalized) == 33


def test_exempt_geometry_seats_survive_verbatim() -> None:
    """The 手迹/盖印 exemptions keep their exact literals: the red-pen
    ellipse, the postmark pair, the 「当前」 mark pair and the stamp
    graphic's ring (six 50% seats) plus the one arch — seven exempt
    seats in total, outside the scale."""

    components = _webui_text(COMPONENTS)
    assert components.count("border-radius: 50%") == 6
    assert "border-radius: 9px 9px 0 0;" in components


# ---------------------------------------------------------------------------
# 3. the face pins (one consumer assertion per tier, minimum)


def test_bottom_sheet_rounds_its_top_corners_only() -> None:
    """The sheet face: inside @media (hover: none), .word-card carries
    --r-sheet-top on the top two corners and 0 at the bottom (贴屏)."""

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
    assert (
        "border-radius: var(--r-sheet-top) var(--r-sheet-top) 0 0;"
        in sheet_block
    )
    assert sheet_block.count("border-radius") == 1


def test_floating_card_and_underlay_use_the_raise_tier() -> None:
    """The float face: .word-card and its deckle underlay both consume
    --r-raise (the raised-paper pair rounds together)."""

    components = _webui_text(COMPONENTS)
    assert _radius_of(_rule_block(components, ".word-card {")) == (
        "var(--r-raise)"
    )
    assert _radius_of(_rule_block(components, ".word-card::after {")) == (
        "var(--r-raise)"
    )


def test_in_flow_paper_faces_use_the_paper_tier() -> None:
    """--r-paper consumers: the annotation card, the torn reply paper,
    the cover sheet and the editor's opening-letter preview (文档流
    纸件的柔边，不是卡)."""

    components = _webui_text(COMPONENTS)
    screens = _webui_text(SCREENS)
    assert _radius_of(_rule_block(components, ".note-paper {")) == (
        "var(--r-paper)"
    )
    assert _radius_of(_rule_block(components, ".letter.me .paper {")) == (
        "var(--r-paper)"
    )
    assert _radius_of(_rule_block(screens, ".ob-sheet {")) == (
        "var(--r-paper)"
    )
    assert _radius_of(
        _rule_block(screens, ".editor-openprev-paper {")
    ) == "var(--r-paper)"


def test_form_controls_use_the_ctl_tier() -> None:
    """--r-ctl consumers: the writing textarea, the field row's input and
    select, and the annotation reply input."""

    components = _webui_text(COMPONENTS)
    assert _radius_of(_rule_block(components, ".pen {")) == "var(--r-ctl)"
    assert _radius_of(
        _rule_block(components, ".field input, .field select {")
    ) == "var(--r-ctl)"
    assert _radius_of(_rule_block(components, ".replytext {")) == (
        "var(--r-ctl)"
    )


def test_chip_is_a_pill() -> None:
    """--r-pill consumer: the word-picker chip (999px full-soft)."""

    components = _webui_text(COMPONENTS)
    assert _radius_of(_rule_block(components, ".chip {")) == "var(--r-pill)"


# ---------------------------------------------------------------------------
# 4. the sharp-corner clearance (negative controls, ≥8 faces)


def test_fourteen_named_container_faces_carry_a_nonzero_radius() -> None:
    """直角清零负控: each named container face's own rule block declares
    a border-radius that is present and not 0 — the audit face of the
    user ruling, one entry per known sharp-corner survivor."""

    components = _webui_text(COMPONENTS)
    screens = _webui_text(SCREENS)
    faces: list[tuple[str, str, str]] = [
        (COMPONENTS, ".note-paper {", "批注卡"),
        (COMPONENTS, ".letter.me .paper {", "撕边信纸"),
        (COMPONENTS, ".letter.me.en-route { position: relative;", "在途信封"),
        (COMPONENTS, ".word-card {", "词卡浮卡"),
        (COMPONENTS, ".pen {", "稿纸 textarea"),
        (COMPONENTS, ".chip {", "词表片"),
        (SCREENS, ".ob-sheet {", "门厅封面"),
        (SCREENS, ".dock {", "写信区垫板"),
        (SCREENS, ".env-mini {", "信档缩略封"),
        (SCREENS, ".envsel {", "沓面板"),
        (SCREENS, ".env {", "沓封卡"),
        (SCREENS, ".envpage {", "翻页页卡"),
        (SCREENS, ".char-editor {", "编辑台容器"),
        (SCREENS, ".editor-openprev-paper {", "开场信预览短笺"),
    ]
    bare: list[str] = []
    for file_name, selector, label in faces:
        css = components if file_name == COMPONENTS else screens
        block = _rule_block(css, selector)
        value = _radius_of(block)
        if value in ("0", "0px", "none"):
            bare.append(label)
    assert bare == []


def test_the_scrim_and_the_text_links_stay_bare() -> None:
    """The two lawful bare faces: the ink scrim is a mask (无圆角) and
    the .btn family is underlined text without a box (圆角不适用)."""

    components = _webui_text(COMPONENTS)
    assert "border-radius" not in _rule_block(components, ".word-scrim {")
    assert "border-radius" not in _rule_block(components, ".btn {")


def test_flap_faces_follow_their_envelope_silhouette() -> None:
    """The flap faces (en-route 封舌 / env-mini 封舌) round their top
    corners with the paper tier so the V-clip silhouette matches the
    rounded envelope body (a square flap would poke past the corners)."""

    components = _webui_text(COMPONENTS)
    screens = _webui_text(SCREENS)
    assert _radius_of(
        _rule_block(components, ".letter.me.en-route::before {")
    ) == "var(--r-paper) var(--r-paper) 0 0"
    assert _radius_of(
        _rule_block(screens, ".env-mini::before {")
    ) == "var(--r-paper) var(--r-paper) 0 0"


def test_the_dock_pads_top_corners_and_keeps_its_base_flush() -> None:
    """The writing dock is a raised pad whose base sits on the navdock:
    top corners take --r-raise, the bottom edge stays 0 (底角不圆，
    露底防)."""

    screens = _webui_text(SCREENS)
    assert _radius_of(_rule_block(screens, ".dock {")) == (
        "var(--r-raise) var(--r-raise) 0 0"
    )


# ---------------------------------------------------------------------------
# 5. the spec revision


def test_spec_token_table_carries_the_five_rows_and_the_ruling() -> None:
    """② gains the 圆角五档 table: five --r-* rows with the ruled values
    and the ruling annotation naming the user's date and the retired
    clauses (§6 ≤2px / T3 大圆角卡片 — the other T3 bans stand)."""

    spec = _spec()
    assert "### ②-6 圆角五档" in spec
    for name, value in RADIUS_TOKENS.items():
        assert f"`{name}` | `{value}`" in spec
    assert "用户裁决 2026-10-02" in spec
    assert "Apple 式柔和圆角" in spec
    assert "「大圆角卡片」禁令废止，其余禁令不动" in spec


def test_spec_revision_notes_reach_the_six_and_nine_and_t3_sites() -> None:
    """The revision annotation is present at the §6-shaped sentence
    (8.2.2②), the ⑨ preamble's retired ≤2px clause, and the T3 citation
    in 8.1.4 — the three sites the task book names."""

    spec = _spec()
    assert "取代「零圆角面板/\n≤2px 收窄」" in spec
    assert "取代「信纸物件 ≤2px 收窄」" in spec
    assert "「大圆角\n卡片」禁令废止" in spec


def test_spec_contract_rows_note_their_radius_tiers() -> None:
    """The ③ rows for pen/note-paper/letter/word-card/field/chip carry
    their tier tokens (the shape descriptions follow the radii)."""

    spec = _spec()
    assert "--r-ctl" in spec.split("| 2 | pen |", 1)[1].split("\n", 1)[0]
    assert "--r-paper" in spec.split("| 3 | note-paper |", 1)[1].split(
        "\n", 1
    )[0]
    assert "--r-paper" in spec.split("| 4 | letter |", 1)[1].split(
        "\n", 1
    )[0]
    row15 = spec.split("| 15 | word-card |", 1)[1].split("\n", 1)[0]
    assert "--r-raise" in row15
    assert "--r-sheet-top" in row15
    assert "--r-ctl" in spec.split("| 16 | field |", 1)[1].split("\n", 1)[0]
    assert "--r-pill" in spec.split("| 17 | chip |", 1)[1].split("\n", 1)[0]


def test_tokens_headnote_retracks_the_retired_clause() -> None:
    """tokens.css's header frames the zero-large-radius law as retired,
    not current: the v2-2R note marks the old clause 退役 with the user
    ruling's date (a header still asserting 「零大圆角面板」 as law would
    contradict the tokens below it)."""

    tokens = _webui_text(TOKENS)
    assert "条款\n   由用户裁决 2026-10-02 退役" in tokens
    assert "柔和圆角" in tokens
