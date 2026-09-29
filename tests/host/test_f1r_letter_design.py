"""F-1R — the page re-typeset onto the VS1 letter design (信笺版式).

The user's first inspection rejected the F-1/F-2 visual face: it had
migrated the archived repo's 9/17-18 write/dialogue token line, while the
accepted anchor is the 9/19 VS1 「对话客厅」 chat parlor. This file pins
the rework onto that one visual anchor (its ``chat.css`` values adopted,
never its code):

1. the letter form laws, as absolute negatives — no tab bar, no teal, no
   border-radius, no box-shadow, no dark-theme switch, no bubble classes;
2. the three screens — 开张 (the first-visit cover, remembered in
   localStorage, honest about there being no persona-authoring face),
   客厅 (the parlor: the partner card, the letter flow, the borderless
   pen line with the 寄出 link) and 仪表 (the honest set screen: the
   endpoint and the model name have no page-side source and are not
   shown, 学习/诊断 expand in place, 回客厅 leads back) — R-1 随迁后：
   屏迁空间（客厅=space-parlor），仪表的诚实句与四块归位（进步/柜抽），
   缺位钉保证旧壳不回流;
3. the teaching note keeps every semantic string the behavior suites
   pin (the W-6 arms and their confirm, the busy strip, the verdict
   strip in ochre/ink — never a green/red wash), and the letters keep
   the torn-edge reply slip shape.

The backend is untouched: the six endpoints answer byte-identical, and
the untouched W-1 behavior suite stays the proof.
"""

from __future__ import annotations

from pathlib import Path

from tests.host.test_w1_web import _page_source, web_stack


def _page_of(tmp_path: Path) -> str:
    """The served page source, over the plain offline stack — the F-G1
    union: the shell plus every static asset it links (the pins used to
    read the embedded ``_PAGE``; same semantics, stronger negatives)."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


# ---------------------------------------------------------------------------
# 1. the letter form laws — absolute negatives


def test_the_page_keeps_the_letter_form_laws(tmp_path: Path) -> None:
    """The clauses the user rejected the previous face over, pinned so
    they cannot come back: no bottom tab bar, no teal from the old
    two-theme sheet, no radius, no shadow, no dark switch, and the old
    bubble classes are gone (the letters replaced them)."""

    page = _page_of(tmp_path)
    assert "tabbar" not in page
    assert "#0f766e" not in page
    assert "#4fd1c5" not in page
    assert "border-radius" not in page
    assert "box-shadow" not in page
    assert "@media (prefers-color-scheme: dark)" not in page
    # the old bubbles: the accent-filled .user / the sunken .assistant
    assert ".user {" not in page
    assert ".assistant {" not in page
    # the letter actions are pencil underlined text links
    assert "var(--pencil)" in page
    assert "text-underline-offset" in page


# ---------------------------------------------------------------------------
# 2. the three screens


def test_the_page_has_the_first_visit_cover(tmp_path: Path) -> None:
    """The 开张屏: the brand mark over the serif title, the three-step
    letter (F-G2 migrated the single ✉ line to the step formheads —
    1:1, the honesty faces kept), the serif ink 就这么定 link — and no
    persona authoring (the runtime has no such face; the cover invents
    none)."""

    page = _page_of(tmp_path)
    assert 'id="screen-onboard"' in page
    # F-G2 随迁：旧钉「✉ 第一步，也是唯一步」随开张屏三步升维退役，
    # 语义由三段 formhead（第一步 · 是什么 / 第二步 · 教学怎么发生）
    # 与顶部 brand-mark（--lg）继承。
    assert "✉ 第一步，也是唯一步" not in page
    assert "第一步 · 是什么" in page
    assert 'data-brand-mark="lg"' in page
    assert "把英语请进客厅" in page
    assert "跟一位固定伙伴用英语闲聊" in page
    assert "就这么定 →</button>" in page
    # the cover never returns once localStorage says so; a refusing
    # storage answers "seen" (nobody is trapped on the cover)
    assert 'ONBOARD_KEY = "elp.parlor.onboarded.v1"' in page
    # R-1 随迁：进门落客厅空间（space-parlor 取代 screen-living）
    assert 'seenOnboard() ? "parlor" : "onboard"' in page
    # honesty: no persona-authoring form exists on the cover
    assert "生成人设" not in page
    assert "人设卡" not in page


def test_the_page_has_the_parlor_screen(tmp_path: Path) -> None:
    """The 客厅空间: the partner card (the fixed name — the host exposes no
    readable persona identity, so none is shown), the letter flow, and the
    borderless pen line with the 寄出 link. R-1 随迁：屏迁空间
    （space-parlor），品牌条减三 toggle（导航归 dock，缺位钉）。"""

    page = _page_of(tmp_path)
    assert 'id="space-parlor"' in page
    assert 'id="screen-living"' not in page
    assert '<div class="who">英语客厅</div>' in page
    assert "固定伙伴" in page
    assert 'id="meter-toggle"' not in page
    assert 'id="topactions"' not in page
    assert "topactions" not in page
    assert 'id="messages"' in page
    assert 'id="moments"' in page
    assert '<textarea id="text" class="pen"' in page
    assert "寄出 →</button>" in page
    # the flow's two letter shapes: the plain sheet and the torn-edge
    # reply slip (clip-path, the anchor's own polygon)
    assert 'node.className = "letter me"' in page
    assert 'node.className = "letter may"' in page
    assert (
        "clip-path: polygon(0 6px, 4% 2px, 11% 7px, 19% 1px, 27% 6px,"
        in page
    )


def test_the_honest_faces_split_into_drawer_and_progress(
    tmp_path: Path,
) -> None:
    """The honest faces of the old 仪表 screen, R-1 归位后仍在：
    the model endpoint and the model name have no page-side source — the
    absence is said, not faked (the sentence moved to the drawer's
    settings section); 学习/诊断 live as always-mounted blocks in
    学案·进步（证据/为什么/观察 三组），记忆/隐私 in the drawer; the
    old setlinks/toggleSetBlock expansion retired (absence pins), the
    one-visible-section semantics rides the section loop."""

    page = _page_of(tmp_path)
    assert 'id="screen-set"' not in page
    assert "页面不读取、不显示（宁缺勿假）" in page
    # the two always-mounted read blocks and the three group headings
    assert 'id="set-learning"' in page
    assert 'id="set-diagnostics"' in page
    for group in (">证据</h3>", ">为什么</h3>", ">观察</h3>"):
        assert group in page
    # the setlinks row and its data-block links retired (absence pins)
    assert 'data-block=' not in page
    assert ">学习</button>" not in page
    assert ">诊断</button>" not in page
    assert 'id="back-to-living"' not in page
    # the in-place expansion loop retired with the screen; the same
    # one-visible semantics rides the section switch's comparison
    assert "function toggleSetBlock(" not in page
    assert 'document.getElementById("set-" + block).hidden' not in page
    assert '"learning", "diagnostics", "memory", "privacy"' not in page
    assert "group[key].hidden = key !== name;" in page
    # the six section panels exist (three per space)
    for panel in ("study-today", "study-goal", "study-progress",
                  "drawer-memory", "drawer-privacy", "drawer-settings"):
        assert f'id="{panel}"' in page


# ---------------------------------------------------------------------------
# 3. the teaching note keeps the behavior faces


def test_the_teaching_note_keeps_the_w6_faces(tmp_path: Path) -> None:
    """The teaching moment is a short note in the letter flow: the
    target's words under the 教学时刻 label, the underline answer box,
    the 寄出作答 link, the three help arms with their confirm, the faint
    skip link, the busy strip and the verdict strip in ochre/ink — every
    semantic string the W suites pin, restyled but never renamed away."""

    page = _page_of(tmp_path)
    # the note itself (the old accent-wash .moment card is gone)
    assert 'card.className = "note-paper"' in page
    assert ".note-paper {" in page
    assert "教学时刻：" in page
    # the underline answer box and its link
    assert "用英语试着造个句子…" in page
    assert "寄出作答" in page
    # the three help arms, the confirm, the skip
    assert 'helpButton("看提示", "hint"' in page
    assert 'helpButton("看答案", "reveal"' in page
    assert 'helpButton("解释", "explanation"' in page
    assert "看答案将显示完整目标表达，之后你仍可作答，确定？" in page
    assert "跳过这一题" in page
    # the busy strip and the verdict strip (ochre/ink, never washes)
    assert "批改中…" in page
    assert ".resultstrip.ok { color: var(--pencil); }" in page
    assert ".resultstrip.miss { color: var(--ink); }" in page
    # the W-4 immediacy face, unchanged
    assert '"/api/teaching/current"' in page
    assert "MOMENT_POLL_MS = 400" in page
    assert "MOMENT_POLL_MAX_MS = 90000" in page
    # every word inert: textContent, never innerHTML
    assert "textContent" in page
    assert ".innerHTML" not in page


# ---------------------------------------------------------------------------
# 6. disposition fidelity pins (review LOW-1/LOW-2 + the teach-me poll gap)


def test_the_pen_is_the_anchors_lined_paper(tmp_path: Path) -> None:
    """LOW-1: the writing area is the anchor's own lined-paper textarea —
    the repeating rule-soft lines that scroll with the text, the
    min/max-height bounds, and Enter posts / Shift+Enter breaks."""

    page = _page_of(tmp_path)
    assert "repeating-linear-gradient(" in page
    assert "background-attachment: local" in page
    assert "min-height: 64px" in page
    assert 'document.getElementById("text").addEventListener("keydown"' in page
    assert 'if (event.key === "Enter" && !event.shiftKey)' in page


def test_primary_actions_are_ink_secondary_stay_pencil(tmp_path: Path) -> None:
    """LOW-2: the anchor's color semantics — the primary serif actions
    (就这么定 / 寄出 / 寄出作答) carry ink underlines; the pencil color
    belongs to the secondary links (help arms, set links, skip)."""

    page = _page_of(tmp_path)
    # the two primary selectors spell ink
    assert (
        ".ob .go { display: block; margin: 26px auto 0;"
        " font-family: var(--f-serif);" in page
    )
    assert "font-weight: 700; color: var(--ink);" in page
    # and pencil still lives on the secondary faces
    assert ".setlink {" in page
    assert ".linklike { font-family: var(--f-sans);" in page


def test_teach_me_starts_the_moment_poll(tmp_path: Path) -> None:
    """The F-2-era gap the review registered: a successful teach-me used
    to leave the card invisible until the next turn or a refresh — the
    reply now starts the W-4 poll in the same breath."""

    page = _page_of(tmp_path)
    # R-1 随迁：教学开在空间切换后照常可见（showSpace("parlor") 同形两行）
    assert (
        'showSpace("parlor");\n      startMomentPolling();' in page
    )
