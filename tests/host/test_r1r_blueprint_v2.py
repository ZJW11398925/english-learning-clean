"""R-1R — the ⑧ design blueprint v2, landed (十页方案的实现钉).

The R-1 shell (spaces + dock + section tabs) was accepted mechanically; the
user's first inspection rejected the *inside* of the pages (information
organization, expression, character continuity). R-1A re-designed every page
(docs/FRONTEND_SPEC.md ⑧ v2); this file pins the implementation of that
blueprint — the copy is 8.2's, word for word:

1. the shell-level moves — the page-internal ``<h2>`` is gone from all six
   sections (the space header's section slot is the one page title), the
   section tabs' display names are 方向/记录 with zero internal-id renames,
   the cover's ``<title>`` is the product name alone;
2. component #21 (disclosure) — the four-step registration (spec row, css
   contract block, js factory, COMPONENTS tuple) and the collapsed-by-default
   semantics, no accordion;
3. the 52-row answer — family grouping (the key is the target id's second
   dash segment, derived client-side), default-collapsed groups with
   two-example headers, the filter that expands hit groups and answers the
   honest no-hit sentence;
4. the expression faces — the translation tables (outcome / review_state /
   frequency / modality / gate reasons in full), the human time helper with
   the ISO tooltip, the 12-character fingerprint, the bilingual word forms;
5. the parlor faces — the empty-hall sentence, the retired empty banner, the
   two blocked-line forms with the 原委在 link, the teach-me success/failure
   lines, the waiting placeholder;
6. the teaching note — 批注： header（rd-2 批注家族，原「短笺」）, the
   status line from the server's own
   word, the kind line through the Chinese map (unknown kinds omit the row),
   the guide line, the three help arms and their busy/seen words, the skip,
   the reveal confirm, the verdict strip with the Chinese verdict first;
7. the 方向 write face — read-write合一 (no read card), 技能 over 模态, the
   save receipts with 第 {n} 版, the conflict sentence, the folded taxonomy
   reference, the frequency block's 现在：适度（BALANCED） form;
8. the 隐私 face — 忘掉 language throughout, the two-layer confirms word for
   word, the result sentences, the folded + filtered 按表达忘掉 list.

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
# 1. the shell-level moves


def test_no_page_internal_h2_and_the_guide_sentences_open_the_sections(
    tmp_path: Path,
) -> None:
    """⑧ 8.2.9: the page title is said once (the space header's slot), so
    no section carries an h2; each section opens with its 8.2 guide
    sentence, word for word."""

    index = _text("index.html")
    assert "<h2>" not in index
    assert "<h2 " not in index
    # the guide sentences (⑧ 8.2 各页定稿，逐字；rd-3 随迁：档案节
    # 引导句接任——旧账页句退役)。v2-2 随迁（换名句对齐，spec 8.2.4/
    # 8.2.6/8.2.7 定稿）：自称主语改「笔友」——记着方向、记着事、
    # 被请求忘掉的都是与你通信的笔友。
    assert "客厅在今天的样子" not in index  # 今日的旧引导句退役（摘要行接任）
    assert (
        "你想把英语用在哪里——这是笔友记着的长期方向。" in index
    )
    assert "每次保存都前移版本；上一版找不回来。" in index
    assert "批注留过的痕迹与接下来的计划——要的时候来翻。" in index
    assert "客厅的账页——只读，如实。" not in index
    # cs-2 随迁：记忆页引导句接三摞重组后的口径（分三摞收纳）
    assert "笔友记住的事都在这里——一条条如实，分三摞收纳。" in index
    assert "请笔友忘掉一些事——走出去就找不回来。" in index
    for retired_line in (
        "你想把英语用在哪里——这是客厅记着的长期方向。",
        "客厅记住的事都在这里——一条条如实，分三摞收纳。",
        "请客厅忘掉一些事——走出去就找不回来。",
    ):
        assert retired_line not in index
    # rd-4 随迁（9.12-23）：设置节升真面——旧「还没铺开」句退役不回潮
    assert "设置面还没有铺开。" not in index
    assert "当前这一档由启动命令给定——页面读不到，也不改它。" in index


def test_the_section_tabs_renamed_display_only(tmp_path: Path) -> None:
    """⑧ 8.1.2 + rd-3（9.11-22）: the study tabs read 今日 / 方向 / 档案
    （记录→档案，收藏档语义）— the display names moved, the internal ids
    and keys did not (data-section, panel ids, DEFAULT_SECTION,
    SECTION_BODIES keys all survive)."""

    index = _text("index.html")
    assert 'data-section="goal"' in index
    assert 'data-section="progress"' in index
    assert ">方向</button>" in index
    assert ">档案</button>" in index
    assert ">记录</button>" not in index
    assert ">目标</button>" not in index
    assert ">进步</button>" not in index
    assert 'id="study-goal"' in index
    assert 'id="study-progress"' in index
    app = _text("app.js")
    assert 'goal: "方向"' in app
    assert 'progress: "档案"' in app
    assert 'progress: "记录"' not in app
    assert 'goal: "目标"' not in app
    assert 'progress: "进步"' not in app
    assert 'const DEFAULT_SECTION = { study: "today", drawer: "memory" };' \
        in app


def test_the_browser_title_is_the_product_name(tmp_path: Path) -> None:
    """⑧ 8.2.1: the browser tab is the product's face — no engineering
    stage word on it. v2 命名随迁（简报 §1）：题 = 展信佳（app.js 的
    BRAND.name 同值驱动，<title> 为静态兜底）。"""

    index = _text("index.html")
    assert "<title>展信佳</title>" in index
    assert "dogfood" not in index
    assert "英语客厅" not in index


# ---------------------------------------------------------------------------
# 2. component #21 — the disclosure group, registered the four-step way


def test_disclosure_is_registered_in_all_four_places() -> None:
    """The living-registry four steps, one cut (the word-card precedent):
    the spec ③ row, the components.css contract block with its four
    clauses, the components.js factory, the COMPONENTS tuple — and the
    selectors are single-source across the tree."""

    from tests.host.test_fg1_architecture import (
        COMPONENTS,
        _webui_all_text,
        _webui_text,
    )

    assert "disclosure" in COMPONENTS
    # R-1V 随迁：icon-set 入库再长一格（21 → 22）——同刀登记；
    # rd-4 曾随迁长到 23；cs-2 随迁：浮层伙伴卡退役再缩回（23 → 22）
    assert len(COMPONENTS) == 22
    spec = (
        Path(__file__).resolve().parents[2]
        / "docs" / "FRONTEND_SPEC.md"
    ).read_text(encoding="utf-8")
    assert "| 21 | disclosure" in spec
    css = _webui_text("components.css")
    assert "21. disclosure" in css
    js = _webui_text("components.js")
    assert "export function disclosure(" in js
    whole = _webui_all_text()
    for selector in (
        ".disclosure {",
        ".disclosure-head {",
        ".disclosure-body {",
        ".disclosure-examples {",
    ):
        assert whole.count(selector) == 1, selector


def test_the_disclosure_is_collapsed_by_default_and_no_accordion(
    tmp_path: Path,
) -> None:
    """The state matrix, in the factory's own source: collapsed is the
    default (body hidden, ▸, aria-expanded false), the count stays in the
    head when expanded, the marker flips to ▾, and nothing in the factory
    closes a sibling (no accordion)."""

    page = _page_of(tmp_path)
    assert "export function disclosure(opts) {" in page
    assert "body.hidden = true;" in page
    assert 'head.setAttribute("aria-expanded", "false");' in page
    # R-1V 随迁（spec ⑨-7.9）：▸/▾ 字符标记退役，换 #22 自绘墨线
    # chevron——展开态不再换字符，由 --open 类驱动 SVG 旋转 90°
    assert 'marker.appendChild(inkIcon("chevron"));' in page
    assert 'marker.textContent = "▸";' not in page
    assert 'marker.textContent = open ? "▾" : "▸";' not in page
    assert 'root.classList.toggle("disclosure--open", open);' in page
    assert '"（" + options.count + "）"' in page
    # no accordion: the factory never reaches outside its own root
    js = _text("components.js")
    factory = js.split("export function disclosure(opts) {", 1)[1]
    assert "querySelectorAll" not in factory
    assert "parentElement" not in factory


def test_the_raw_tag_form_lives_in_the_component_library() -> None:
    """⑧ 8.3 / spec ⑤: the .rawtag form (the monospace raw value) is worn
    by two library components (#15 word-card's .wc-en and #17 chip's
    bilingual shape) and by every page-level raw value — so its style
    belongs to the library's one physical source, components.css, exactly
    once; screens.css rules the screen-level forms only (.sumline)."""

    from tests.host.test_fg1_architecture import (
        _webui_all_text,
        _webui_text,
    )

    css = _webui_text("components.css")
    assert ".rawtag {" in css
    assert ".rawtag {" not in _webui_text("screens.css")
    assert _webui_all_text().count(".rawtag {") == 1
    # both library wearers ride it
    assert 'en.className = "rawtag";' in _webui_text("components.js")
    assert "rawTag(String(hash).slice(0, 12))" in _webui_text("app.js")
    # the screen-level summary digit form stayed where it belongs
    assert ".sumline .sumnum {" in _webui_text("screens.css")
    assert ".sumline .sumnum {" not in css


# ---------------------------------------------------------------------------
# 3. the 52-row answer — family groups, folded, filterable


def test_the_family_grouping_and_the_filter(tmp_path: Path) -> None:
    """⑧ 8.2.3/8.2.7: the group key is the target id's second dash
    segment; the family names are the 8.3 table's four; an unknown family
    is never disguised (the raw word serves); the filter expands the hit
    groups, hides the misses' rows, and a no-hit answers the one honest
    sentence."""

    app = _text("app.js")
    # the family table (⑧ 8.3, the four live families)
    assert 'discourse: "接话与转题"' in app
    assert 'hedge: "留有余地"' in app
    assert 'pragmatic: "应对与表态"' in app
    assert 'softener: "委婉说法"' in app
    # the group key: the id's second dash segment, derived client-side
    assert "return parts.length > 2 ? parts[1] : " in app
    # the group head: name + count + two examples, via #21
    assert "examples: rows.slice(0, 2).map(" in app
    # the filter: input expands the hit groups and filters the rows; the
    # honest no-hit sentence; an emptied filter restores the default fold
    assert 'input.placeholder = "找一个表达……";' in app
    assert 'noHit.textContent = "没有叫这个的表达。";' in app
    assert "g.disc.setOpen(hit);" in app
    assert "r.probe.includes(q)" in app
    # both homes ride the one builder (今日 · 可以练的表达 and
    # 抽屉 · 隐私 · 按表达忘掉)
    assert "familyGroupsBlock(list," in app
    assert "function renderTodayPractice(" in app
    assert "function loadDelTargets(" in app
    practice = app.split("function renderTodayPractice(", 1)[1]
    assert "familyGroupsBlock" in practice.split("function ", 1)[0]
    dele = app.split("function loadDelTargets(", 1)[1]
    assert "familyGroupsBlock" in dele.split("async function", 1)[0]
    assert "还没有可忘的表达——语料还没有铺到这里。" in app


def test_an_unknown_family_is_never_disguised_as_a_translation() -> None:
    """⑧ 8.3 总则 / 8.2.3: only the four live families have客厅 words; any
    other家族 shows its own raw word (small, mono) — the client map is
    consulted with a fallback to the raw key, and the four translated
    families are exactly the four 8.3 names rows."""

    app = _text("app.js")
    # the head name: the Chinese word when the family is known, else the
    # raw key itself — never a fabricated translation
    assert "name: FAMILY_CN[family] || family || " in app
    # the four translated keys are exactly 8.3's four rows
    block = app.split("const FAMILY_CN = {", 1)[1].split("};", 1)[0]
    keys = [line.split(":")[0].strip() for line in block.splitlines()
            if ":" in line]
    assert keys == ["discourse", "hedge", "pragmatic", "softener"]
    # …and the families 8.3 says are 出现再定 are absent from the map
    for untranslated in ("colloc", "phrasal", "idiom", "frame"):
        assert f"{untranslated}:" not in block, untranslated
    # the display order puts the known four first, the rest sorted after
    assert 'const FAMILY_ORDER = ["discourse", "hedge", "pragmatic", ' \
        '"softener"];' in app
    assert "const ra = ia < 0 ? FAMILY_ORDER.length : ia;" in app


# ---------------------------------------------------------------------------
# 4. the expression faces — translation tables, human time, fingerprints


def test_the_translation_tables_carry_the_blueprint_words() -> None:
    """⑧ 8.3's rows, spot-checked where the page actually renders them:
    the verdicts, the review states, the frequency four, the modality
    four, and the gate reasons' full set (the unknown codes stay raw and
    small — never a disguised translation)."""

    app = _text("app.js")
    for word in (
        # rd-2 随迁：判词豪放档（答得漂亮 / 答了一半）；rd-3 随迁
        # （9.11-22）：批注动作四词（ACTION_CN）与门规理由二十码
        # （GATE_REASON_CN）随诊断五板退役——词面归服务端与 web.py
        # （前端缺位钉移到 test_rd3_information_architecture.py）
        'SUCCESS: "答得漂亮"',
        'PARTIAL: "答了一半"',
        'FAILURE: "没答中"',
        'ABSTAIN: "这次没法判"',
        'NOT_SCHEDULED: "还没排上"',
        'UPCOMING: "排上了"',
        'DUE: "今天到期"',
        'OVERDUE: "过期了"',
        'OFF: "不递"',
        'MINIMAL: "少递"',
        'BALANCED: "适度"',
        'EAGER: "勤递"',
        'SPEAKING: "口语"',
        'LISTENING: "听力"',
        'READING: "阅读"',
        'WRITING: "写作"',
    ):
        assert word in app, word
    # the gate reason map is the full set (gate.py's DENY_PRECEDENCE
    # seventeen + the D-5R assembly three), unknown codes raw —
    # rd-3 随迁：前端 GATE_REASON_CN 随诊断面退役，二十码的缺位由
    # test_rd3_information_architecture.py 钉住（服务端词面不动）


def test_the_human_time_and_the_fingerprint_helpers() -> None:
    """⑧ 8.3: 时间 = 今天 14:05 / 昨天 / 9 月 21 日 (the full ISO rides the
    title attribute, only ever); 指纹 = the first 12 characters, mono,
    with the full value on the title."""

    app = _text("app.js")
    assert 'return "今天 " + hh + ":" + mm;' in app
    assert 'return "昨天";' in app
    assert '+ " 月 "' in app
    assert 'return "去年";' in app
    assert "span.title = String(iso);" in app
    assert 'span.textContent = humanTime(iso);' in app
    # the three branches in their order (today before yesterday before the
    # same-year date form)
    helper = app.split("function humanTime(iso) {", 1)[1].split(
        "\nfunction whenNode", 1)[0]
    order = [helper.index(word) for word in (
        '"今天 " + hh', '"昨天"', '" 月 "', '"去年"')]
    assert order == sorted(order)
    # an unparseable value is shown as-is (a time is never invented)
    assert "if (Number.isNaN(then.getTime())) return String(iso);" in helper
    # the fingerprint: 12 characters, the full hash on the tooltip
    assert "rawTag(String(hash).slice(0, 12))" in app
    assert "span.title = String(hash);" in app
    # bilingual storage-word form: 中文在前 + 英文等宽小字在后
    assert 'frag.appendChild(document.createTextNode(String(cn) + " "));' in app
    assert 'function rawTag(text) {' in app


def test_the_version_number_left_the_standing_faces() -> None:
    """⑧ 8.2.4: the version number is a save-receipt word, never a
    standing label — the frequency block reads 现在：适度（BALANCED）."""

    app = _text("app.js")
    assert "（版本 " not in app
    assert '已保存（第 "' in app
    assert 'b.textContent = "现在：";' in app


# ---------------------------------------------------------------------------
# 5. the parlor faces


def test_the_parlor_speaks_the_new_copy(tmp_path: Path) -> None:
    """⑧ 8.2.2, word for word: the empty-hall sentence (a client-static
    system line, removed by the first letter), the retired empty banner,
    the placeholder, the waiting line, the failure line, the teach-me
    pair."""

    page = _page_of(tmp_path)
    # the empty hall — and the banner is gone from the flow（rd-2 随迁：
    # 空厅句升豪放档——语义底线①③由本句承载）
    assert (
        "信还没开始写——想从哪句起，就从哪句起。中文英文都行；"
        "写错了，笔友接得住。"
        in page
    )
    assert "showEmptyHall();" in page
    assert "dismissEmptyHall();" in page
    assert "本轮没有打开教学时刻" not in page
    # the writing face and the waiting face（rd-2 随迁：placeholder 占
    # 锚例二「今日如何？」；发送后状态行升「信已寄出——」收尾。
    # v2-1 锚屏措辞精修随迁：在途/寄出措辞的「客厅」→「笔友」——回信
    # 者是笔友（锚屏授权面；语义底线不变））
    assert 'placeholder="今日如何？"' in page
    assert "信已寄出，等回信——笔友把灯留着。" in page
    assert "用英语说点什么" not in page
    assert "（生成中…）" not in page
    # the failure line: 人话主句 + 括号工程词（v2-1 措辞随迁同上）
    assert "这封信没有回音——笔友没能联系上模型端点" in page
    # teach-me: success / refusal / network (⑧ 8.2.2 + rd-2 批注家族)
    assert "批注来了——就在下面的信流里。" in page
    assert "没能开始这张批注——" in page
    assert "请求没送到——再试一次。" in page
    assert "教学已开始" not in page
    assert "无法开始这节课" not in page
    assert "请求失败，请重试" not in page


def test_the_blocked_line_is_retired_from_the_flow(tmp_path: Path) -> None:
    """W-8（信流尾注搬出用户面）：blocked 行（⑧ 8.2.2 的两形）从信流
    退役——没递批注的一轮（rd-2 前称短笺）在信流里静默，「为什么」的
    原委留在 温故 · 记录 的 why_not 面（数据面另有钉）。"""

    page = _page_of(tmp_path)
    assert "这一轮没有递短笺" not in page
    assert "showBlockedNote" not in page
    assert "blockedline" not in page


# ---------------------------------------------------------------------------
# 6. the teaching note


def test_the_teaching_note_faces_the_blueprint(tmp_path: Path) -> None:
    """⑧ 8.2.10: the header is 批注：{功能句}（rd-2 批注家族）; the
    status line is the server's own status_cn; the kind rides the client
    map and an unknown kind omits the row; the guide line appears with
    the answer face; the three help arms with their busy/seen words;
    先搁着（rd-2 搁置族）; the reveal confirm; the verdict strip leads
    with the Chinese verdict."""

    page = _page_of(tmp_path)
    assert '"批注："' in page
    assert "MOMENT_KIND_CN[m.kind]" in page
    assert 'CURRENT_USER_ERROR: "你信里的句子"' in page
    assert "m.status_cn || m.lifecycle_state" in page
    assert "回应写在这张批注上（不是下面的信纸）。" in page
    assert 'helpButton("提示", "hint", "取提示中……", "已看提示", card)' in page
    assert 'helpButton("答案", "reveal", "取答案中……", "已看答案", card)' in page
    assert 'helpButton("讲解", "explanation", "取讲解中……", "已看讲解", card)' in page
    assert 'skip.textContent = "先搁着";' in page
    assert "看了答案，完整说法就摆在眼前——看过之后仍可回应。要看吗？" in page
    # the verdict strip: the Chinese verdict first, the runtime's own
    # words after (the symbol is display-only)
    assert 'FAILURE: "✗ 没答中"' in page
    assert 'PARTIAL: "◐ 答了一半"' in page
    assert 'SUCCESS: "✓ 答得漂亮"' in page
    assert 'head + " · " + feedback' in page
    assert "判分反馈：" not in page
    # the retired words stay retired（「已看提示」含「看提示」子串——缺位
    # 钉钉可执行调用形）
    assert "跳过这一题" not in page
    assert 'helpButton("看提示"' not in page
    assert "取提示中…\"" not in page


# ---------------------------------------------------------------------------
# 7. the 方向 write face


def test_the_direction_face_is_read_write_one(tmp_path: Path) -> None:
    """⑧ 8.2.4: the read card is gone (the editor carries the current
    values), 技能 replaces 模态, the receipts name 第 {n} 版, the conflict
    sentence and its 重新读过 action, the frequency block's 现在 form, the
    taxonomy reference folds into #21, 临时侧重（有才出现）."""

    page = _page_of(tmp_path)
    assert 'id="goal-list"' not in page
    assert "renderGoalList" not in page
    assert '"目标 " + (index + 1) + " · 技能"' in page
    assert "· 内容" in page
    assert 'save.textContent = "保存方向";' in page
    assert 'save.textContent = "保存批注频率";' in page
    assert "已保存（第 " in page
    assert "内容没有变化——没有写新版本。" in page
    assert "这份方向刚在别处被改过——重新读过再改。" in page
    assert 'again.textContent = "重新读过";' in page
    assert "临时侧重（有才出现）" in page
    assert 'name: "词表原文（三面 · 本版只作参考）"' in page
    # the bilingual pickers: the client maps, never a client word copy
    assert "MODALITY_CN[word]" in page
    assert "FREQUENCY_CN[word]" in page
    assert "REGISTER_CN" in page


# ---------------------------------------------------------------------------
# 8. the 隐私 face


def test_the_privacy_face_speaks_忘掉(tmp_path: Path) -> None:
    """⑧ 8.2.7: 忘掉 language throughout (删除 survives only inside the
    engineering rawtags), the two-layer confirms word for word, the
    result sentences, the grouped + filtered target list."""

    page = _page_of(tmp_path)
    # v2-2 随迁（换名句对齐，spec 8.2.7 定稿）：自称主语改「笔友」
    assert "请笔友忘掉一些事——走出去就找不回来。" in page
    assert "忘掉这段通信的全部记录" in page
    assert "忘掉这项的痕迹" in page
    assert "按表达忘掉" in page
    assert "这版做不了——页面不知道伙伴的角色编号。" in page
    # the two sub-copy sentences render contiguously — a source line-wrap
    # inside a sentence shows up as an intra-sentence space (the review's
    # L-1: 「信件 本身保留」); the contiguous pins refuse that form
    assert (
        "把这段通信的全部记录请出抽屉——信件、批注痕迹与它留下的证据行，"
        "一并忘掉。" in page
    )
    assert "忘掉某个表达的学习痕迹、学习状态与复习安排；信件本身保留。" in page
    # the two layers, each saying one thing (范围 / 不可逆)
    assert "请出抽屉，找不回来。确定继续？" in page
    assert "再确认一次：忘掉之后无法恢复。" in page
    # the result sentences
    assert "已忘掉：" in page
    assert "没有什么可忘——它之前就不在抽屉里。" in page
    assert "这次忘掉留下的存根，在 抽屉 · 记忆 里能看到。" in page
    # the dangerous 52-row wall is the grouped + filtered disclosure list
    app = _text("app.js")
    assert "function deleteTargetRow(" in app
    assert "familyGroupsBlock" in app.split("function loadDelTargets(", 1)[1]
    # the old language is gone from the face
    assert "删除这项目标数据" not in page
    assert "确定继续？再次确认" not in page


# ---------------------------------------------------------------------------
# 9. the 记录 page — 账 / 因 / 底


def test_the_record_page_is_account_why_raw(tmp_path: Path) -> None:
    """⑧ 8.2.5（rd-3 修订版）: the 档案 face — the raw fold 原始读数
    （给排查用）holding the evidence panel and the observations (the
    lazy pull survives), the account table and the schedule/goals
    原值 demoted into their own folds, and the five whys gone from the
    user face entirely (rd-3 移走清单，9.11-22)."""

    page = _page_of(tmp_path)
    # rd-3 缺位钉：诊断五问与「为什么 · 原值」用户面零渲染
    assert ">为什么留了这张批注</h3>" not in page
    assert ">为什么没有递</h3>" not in page
    assert ">判分有什么变化</h3>" not in page
    assert ">你收到了哪些帮助</h3>" not in page
    assert ">有没有从简处理的轮次</h3>" not in page
    assert ">为什么</h3>" not in page
    assert ">为什么 · 原值</h3>" not in page
    # the raw fold: name, the adopted content. v2-2 随迁（8.2.12）：
    # 观察读数迁入专门面（观察仪表屏）——折叠内只留入口行
    # （obs-entry 的「翻开原始读数 →」，obsout/obs-status 退役）
    assert 'name: "原始读数（给排查用）"' in page
    assert 'id="raw-readings"' in page
    assert 'id="obs-entry"' in page
    assert '"翻开原始读数 →"' in page
    assert 'id="obsout"' not in page
    assert "loadObservations()" not in page
    # rd-3：账表与排程/目标降入各自的折叠（收养法同 raw-readings）
    assert 'name: "计划明细（复习排程 · 目标）"' in page
    assert 'name: "按表达看：在学的表达"' in page
    assert 'id="plan-detail"' in page
    assert 'id="book-detail"' in page
    assert ">在学的表达</h3>" in page
    assert ">复习日程</h3>" in page
    assert ">学习目标</h3>" in page
    assert ">痕迹</h3>" in page
    assert ">计划</h3>" in page
    # the account table's merge and its columns
    app = _text("app.js")
    assert "function renderRecordBook(" in app
    assert "byTarget.set(item.target_id" in app
    assert "byTarget.get(claim.target_id)" in app
    assert '"痕迹 "' in app
    assert "还没有在学任何表达——批注来过才会有账。" in app
    # the 52-row teachable list is gone from this page
    assert 'id="target-list"' not in page


def test_the_summary_rows_carry_mono_numbers(tmp_path: Path) -> None:
    """⑧ 8.2.6 + rd-3 随迁: the page-head summary row lives only on the
    drawer's 记忆 face now — the 今日 summary row retired with the
    移走清单（计数是副产品，9.11-22）."""

    index = _text("index.html")
    assert 'id="today-summary"' not in index
    assert 'id="mem-summary"' in index
    app = _text("app.js")
    assert '"今天：到期"' not in app
    assert 'renderSummaryLine("today-summary"' not in app
    assert '["记住：关系"' in app
    assert 'className = "sumnum"' in app
    screens = _text("screens.css")
    assert ".sumline .sumnum {" in screens
