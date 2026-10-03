"""p-1 — the 今日 screen and the word cards (今日面 + 点词卡).

Four groups (the task book's own):

1. the 今日 screen — a fourth page behind the parlor's brand bar (今日
   beside 仪表, its own way back and its own 仪表 link), entering is the
   pull, and its three blocks (到期复习 / 最近在学 / 可以练的表达——R-1R
   自「想练一把」改名并家族分组折叠) re-serve
   the learning readout and the teachable list — the due block filters to
   DUE/OVERDUE and puts an inline 教我这一句 on every row, every block
   answers through the state-banner family, and no daily activity is
   invented (the empty faces say so);
2. ``GET /api/word`` — one read-only lookup over content.db's word list:
   single-word and multi-word lemmas (whole-word aligned containment, the
   longest hit wins), case/edge-punctuation insensitivity, the honest miss
   (``{"found": false}``, a 200 fact), the 400 grammar arm, the
   no-content-leg miss, the parameterized-injection probe and the
   read-only pin (content.db's bytes unchanged across lookups);
3. the word-card interaction — the letters' text fragments into inert
   ``.word`` spans (the served source's pins), the clicked word's 1–3-word
   windows go out longest-first, and the #15 word-card overlay carries the
   lemma/pos/forms/senses/examples;
4. the living-registry registration — word-card in all four places (the
   spec ③ row, the components.css contract block, the components.js
   factory, the COMPONENTS tuple), one cut.

Migrations of existing pins (1:1, this cut): the F-G2 registry length
14 → 15 and the brand-bar ``--sm`` count 2 → 3 (the 今日 screen's third
brand bar); both live in ``test_fg2_entry_and_states.py``.
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

from elc.web import _WebFace
from tests.host import test_w1_web
from tests.host.test_w1_web import (
    CONV,
    _page_source,
    web_stack,
)

#: The W-1 suite's module-scoped pilot ``content.db`` fixture, bound under
#: the same name so pytest resolves it for this module's tests too.
pilot_content_db = test_w1_web.pilot_content_db


def _seed_due(host: Any) -> None:
    """One DUE schedule row plus one learner-target state row, written
    directly — the 今日 screen's two data faces read durable rows, and the
    prep-1 tier's controllers are not needed to place them."""

    host.db.execute(
        "INSERT INTO schedule_item (schedule_item_id, target_type,"
        " target_id, evidence_modality, review_state, review_urgency,"
        " next_review_window_start, next_review_window_end,"
        " spacing_stage, source_learning_watermark, version, updated_at)"
        " VALUES ('si-p1', 'RESOURCE', 'res-discourse-anyway',"
        " 'TEXT_PRODUCTION', 'DUE', 0.5, '2026-09-29T08:00:00+00:00',"
        " '2026-09-29T09:00:00+00:00', NULL, 'wm-p1', 'v1',"
        " '2026-09-28T08:00:00+00:00')"
    )
    host.db.execute(
        "INSERT INTO learner_target_state (user_scope_id, target_type,"
        " target_id, evidence_modality, estimator_version,"
        " evidence_watermark, state_json, updated_at)"
        " VALUES ('user-local-v1', 'RESOURCE', 'res-discourse-anyway',"
        " 'TEXT_PRODUCTION', 'p1', 1, '{}',"
        " '2026-09-28T08:00:00+00:00')"
    )
    host.db.commit()


def _page_of(tmp_path: Path) -> str:
    """The served page source over the plain offline stack."""

    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


def _fn_body(source: str, name: str) -> str:
    """One JS function's body from the served union — cut at the next
    ``function``/``async function`` head, whichever comes first."""

    after = source.split(f"function {name}(", 1)[1]
    cut = len(after)
    for marker in ("\nfunction ", "\nasync function "):
        index = after.find(marker)
        if index != -1:
            cut = min(cut, index)
    return after[:cut]


# ---------------------------------------------------------------------------
# 1. the 今日 screen


def test_the_page_has_the_today_screen(tmp_path: Path) -> None:
    """The 今日 face: R-1 随迁——今日屏迁入**温故空间 · 今日节**（旧屏
    id 与三枚 toggle/返回钮退役，缺位钉）；进空间落默认节（温故=今日），
    进节即拉；rd-3 随迁（9.11-22）：默认层恰两块（今天的行动 / 你的
    成长），旧三块 id 中 today-due / today-recent 随收拢退役（缺位钉），
    today-practice 迁档案（id 保留）。"""

    index = _page_of(tmp_path)
    # the old screen and its three toggles/way back are gone (absence
    # pins — the p-3 precedent)
    assert 'id="screen-today"' not in index
    assert 'id="today-toggle"' not in index
    assert 'id="today-set"' not in index
    assert 'id="back-from-today"' not in index
    # the section panel and its tab (the nav lives in the dock/tabs now)
    assert 'id="study-today"' in index
    assert 'id="tab-study-today"' in index
    assert ">今日</button>" in index
    # R-1R（⑧ 8.2.3/8.2.9）：刷新钮全退（进节即拉为唯一拉取点），页内
    # h2 取消（页题只念一遍——节名槽承担「我在哪」）
    assert 'id="today-refresh"' not in index
    assert "<h2>" not in index
    # rd-3 随迁（⑧ 8.2.3 修订版）：两块 = today-action / growth-summary；
    # 旧三块里 today-due / today-recent 退役、today-practice 迁档案
    for block in ("today-action", "growth-summary"):
        assert f'id="{block}"' in index
    assert 'id="today-due"' not in index
    assert 'id="today-recent"' not in index
    assert 'id="today-practice"' in index
    assert ">今天的行动</h3>" in index
    assert ">你的成长</h3>" in index
    app = index  # the served union covers app.js
    # entering the study space lands 今日 and the entry is the pull
    assert 'DEFAULT_SECTION = { study: "today", drawer: "memory" }' in app
    assert '"study-today": loadToday' in app
    assert 'showSection("study"' in app
    assert 'showSpace("parlor")' in app
    # the pull rides the read-only learning face (rd-3: 今日不再读
    # targets——可以练的表达迁档案，由档案节自己拉)
    assert "fetchLearning()" in app
    assert "fetchCurrentMoment()" in app


def test_the_today_blocks_pin_their_data_faces(tmp_path: Path) -> None:
    """The two blocks' data grammar, in the served source: the due
    filter is exactly DUE/OVERDUE with an inline 教我这一句 per row
    (R-1R 钮词定稿), the invitation empty face and the three verbs are
    the honest sentences, every block answers through the state-banner
    family (loading first, diagError with the re-pull), and the growth
    block is the three-verdict word-level conclusion (rd-3，⑧ 8.2.3
    修订版)."""

    page = _page_of(tmp_path)
    # the due filter and its inline act
    assert 'it.review_state === "DUE" || it.review_state === "OVERDUE"' in page
    assert "function teachRow(" in page
    assert 'button.className = "teach-me"' in page
    # the action block: one verb button = the first-priority act; the
    # N=0 invitation says so and offers the parlor
    assert "今天不用复习，要不要聊一句？" in page
    assert '"去聊一句"' in page
    assert '"去回应"' in page
    assert '"开始复习"' in page
    assert "有一张批注等着你回应。" in page
    assert "今天没有到期的复习。" not in page
    # the growth block: three word-level verdicts, at most three lines,
    # no numbers anywhere — the pull-revelation empty card offers the
    # path in
    assert "能做到" in page
    assert "还在练" in page
    assert "暂时不能" in page
    assert "学过一次之后，这里会出现你掌握的技能。" in page
    assert "先去案头聊一句，批注会自己来找你。" in page
    assert "const GROWTH_LINES = 3;" in page
    assert "showLoading(TODAY_PANEL_IDS)" in page
    assert 'diagError(box, (schedule && schedule.error) || "空响应", retry)' in page
    # no invented daily activity: the screen names no challenge/任务 block
    assert "每日挑战" not in page
    assert "每日活动" not in page
    # rd-3 缺位钉：温故面四个新渲染函数体内无内部数值面（scoreNode/
    # confidence/urgency）——抽屉记忆页的「把握」是既有面，本刀不触碰
    # （豁免登记 9.11-22：内部数值永不面向温故用户）
    for fn in ("renderGrowth", "renderTodayAction", "renderArchive",
               "renderPlanLine"):
        body = _fn_body(page, fn)
        assert "scoreNode" not in body, fn
        assert "confidence" not in body, fn
        assert "urgency" not in body, fn
    # rd-3 缺位钉：旧摘要行不回潮
    assert 'id="today-summary"' not in page
    assert '"今天：到期"' not in page


def test_the_today_faces_answer_the_durable_rows(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Over a chain that holds a DUE row and a learner-target state, the
    two reads the 今日 screen is built on answer them: the schedule row is
    due, the states count is one, and the teachable list is the corpus
    truth (the readiness R3+ source word)."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
        seed=_seed_due,
    ) as stack:
        status, learning = stack.get_json("/api/learning")
        assert status == 200
        schedule = learning["schedule"]
        assert not schedule.get("error")
        due = [
            item
            for item in schedule["items"]
            if item["review_state"] in ("DUE", "OVERDUE")
        ]
        assert [item["target_id"] for item in due] == [
            "res-discourse-anyway"
        ]
        evidence = learning["evidence"]
        assert evidence["learner_target_state_count"] == 1
        assert evidence["claims"] == []
        status, targets = stack.get_json("/api/targets")
        assert status == 200
        assert targets["source"] == "readiness>=R3"
        assert targets["targets"], "the pilot corpus teaches something"


def test_the_today_screen_is_honest_when_empty(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The face-level empty shapes behind the three blocks: no schedule
    rows means the due filter has nothing to show, and the practice list
    still comes from the corpus — the page renders both through the
    state-banner empty face (pinned in the source), never a fabricated
    activity."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, learning = stack.get_json("/api/learning")
        assert status == 200
        assert learning["schedule"]["items"] == []
        assert learning["evidence"]["claims"] == []


# ---------------------------------------------------------------------------
# 2. GET /api/word


def test_the_word_endpoint_answers_single_word_lemmas(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """A click on "Anyway," is a click on "anyway": case and edge
    punctuation do not matter, the card carries the lemma's own words —
    pos, the forms (BASE first by form_id), the bilingual sense (zh =
    the translation text, en = the definition text), the pass-through
    roles under their own words, and ≤2 primary-target-first examples."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote('"Anyway,')
        )
        assert status == 200
        assert data["found"] is True
        assert data["lemma"] == "anyway"
        assert data["pos"] == "ADV"
        assert data["entity_id"] == "res-discourse-anyway"
        assert any(
            form["form_type"] == "BASE" and form["written"] == "anyway"
            for form in data["forms"]
        )
        sense = data["senses"][0]
        assert sense["zh"] == "总之；不管怎样（结束题外话或回到正题的标记词）"
        assert sense["en"].startswith("A marker used to leave a digression")
        assert 1 <= len(sense["examples"]) <= 2
        assert "Anyway, let's get back to the topic." in sense["examples"]
        # the surveyed roles pass through verbatim, under their own words
        assert "usage" in sense and "teaching_note" in sense
        assert "disambiguation" in sense


def test_the_word_endpoint_answers_multi_word_lemmas(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Whole-word aligned containment, longest hit wins: the four-word
    query carries its lemma; a lemma with a trailing comma token ("I hear
    you, but") matches the same words unpunctuated; "a bit of luck" picks
    "a bit", the longest lemma the query contains — never a substring
    accident ("make senses" contains "make sense" as a substring and
    still misses)."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote("come to a conclusion")
        )
        assert status == 200
        assert data["found"] is True
        assert data["lemma"] == "come to a conclusion"
        assert data["entity_id"] == "res-colloc-come-to-a-conclusion"
        assert [
            form["form_type"] for form in data["forms"]
        ] == ["BASE", "PAST", "THIRD_PERSON_SINGULAR"]
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote("well, I hear you, but okay")
        )
        assert status == 200
        assert data["found"] is True
        assert data["lemma"] == "I hear you, but"
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote("a bit of luck")
        )
        assert status == 200
        assert data["found"] is True
        assert data["lemma"] == "a bit"


def test_the_word_endpoint_prefers_the_longest_nested_lemma(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Review LOW-1: the corpus's real nested pair — "I see your point,
    but" contains "I see" — had no in-suite competition pin, so a
    shortest-first ordering mutation passed green. The 5-word lemma must
    win both when q carries the whole phrase and when it carries the
    phrase inside a longer sentence."""

    with web_stack(
        tmp_path / "app.db",
        content_db=pilot_content_db,
    ) as stack:
        for q in ("I see your point, but", "maybe I see your point, but later"):
            status, data = stack.get_json(
                "/api/word?q=" + urllib.parse.quote(q)
            )
            assert status == 200
            assert data["found"] is True
            assert data["lemma"] == "I see your point, but", q


def test_the_word_endpoint_misses_honestly(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """The miss is a 200 fact, never a 404: an unknown word, the
    whole-word alignment's refusal of a substring accident, and a q that
    strips to nothing all answer ``{"found": false}``; a request without
    the q parameter is a 400 with one human sentence."""

    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        for query in ("zzznotaword", "make senses"):
            status, data = stack.get_json(
                "/api/word?q=" + urllib.parse.quote(query)
            )
            assert status == 200, query
            assert data == {"found": False}, query
        # a q that strips to nothing is a miss too — and the missing-q 400
        # rides urllib's error channel, read like the fail-closed pins do
        from tests.host.test_fg1_architecture import _get_any

        status, _, body = _get_any(
            stack, "/api/word?q=" + urllib.parse.quote("   ")
        )
        assert status == 200
        assert json.loads(body.decode("utf-8")) == {"found": False}
        status, _, body = _get_any(stack, "/api/word")
        assert status == 400
        assert json.loads(body.decode("utf-8"))["error"]


def test_the_word_endpoint_without_a_content_leg_misses(
    tmp_path: Path,
) -> None:
    """The prep-1 tier holds no word list: every lookup honestly misses —
    the card never opens, and nothing pretends otherwise."""

    with web_stack(tmp_path / "app.db") as stack:
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote("anyway")
        )
        assert status == 200
        assert data == {"found": False}


def test_the_word_endpoint_is_read_only_and_parameterized(
    tmp_path: Path, pilot_content_db: Path
) -> None:
    """Lookups write nothing (the artifact's bytes are the pin) and the
    hostile q rides the parameterized SELECT: a quote-and-comment string
    answers the ordinary miss, with no 500 and no engine text."""

    content_bytes = pilot_content_db.read_bytes()
    with web_stack(
        tmp_path / "app.db", content_db=pilot_content_db
    ) as stack:
        hostile = "x' OR 1=1 --"
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote(hostile)
        )
        assert status == 200
        assert data == {"found": False}
        status, data = stack.get_json(
            "/api/word?q=" + urllib.parse.quote("anyway")
        )
        assert status == 200
        assert data["found"] is True
    assert pilot_content_db.read_bytes() == content_bytes


class _FaceHost:
    """No content leg, no db — just enough host for the word face."""

    app_db_path = "stub-app.db"

    @property
    def content_store(self) -> None:
        return None


def test_the_word_face_unit_answers_over_a_store(tmp_path: Path) -> None:
    """The face method over the probe tier: without a content store the
    face answers the miss at the seam too (the route and the face agree)."""

    face = _WebFace(_FaceHost(), str(CONV))  # type: ignore[arg-type]
    assert face.word("anyway") == {"found": False}


# ---------------------------------------------------------------------------
# 3. the word-card interaction


def test_the_letters_fragment_into_clickable_words(tmp_path: Path) -> None:
    """The fragmentation is inert and letter-only: the user and assistant
    arms split their text into .word spans plus verbatim whitespace (the
    letter structure pins keep their exact strings; v2 骨架随迁——assistant
    臂按段分片，每段同一分片形), the typing/system
    arms do not fragment, and the words stay textContent."""

    page = _page_of(tmp_path)
    # the user arm fragments its single paragraph; the assistant arm
    # fragments every paragraph through the same sharding call
    # （v3-d 随迁：letterWords 增第二参 hits——本段命中位图行，缺省
    # 全供性；word--off = 位图判 0 的无供性词，仍占 .word 索引空间）
    assert (
        "say.appendChild(letterWords(text, rows ? rows[0] || null : null));"
        in page
    )
    assert (
        "say.appendChild(letterWords(para, rows ? rows[cursor] || null : null));"
        in page
    )
    assert 'node.className = "letter me"' in page
    assert 'node.className = "letter may"' in page
    assert (
        page.count("say.appendChild(letterWords(") == 2
    ), "only the two letter arms fragment"
    assert (
        'hits && hits[counter.index] === 0 ? "word word--off" : "word"'
        in page
    )
    assert ".innerHTML" not in page


def test_the_word_windows_go_out_longest_first(tmp_path: Path) -> None:
    """The window grammar, in the served source: 1–3-word windows centred
    on the clicked word (every alignment that contains it), longest first,
    edge-stripped and lowercased with the same character set the server
    strips, deduplicated — and the first found answer opens the card."""

    page = _page_of(tmp_path)
    assert "export function wordWindows(words, index) {" in page
    assert "for (const size of [3, 2, 1]) {" in page
    assert "export function normalizeWordQuery(text) {" in page
    assert ".toLowerCase()" in page
    assert "const WORD_EDGE_CHARS = " in page
    app = page  # the served union covers app.js
    assert "wordWindows(spans.map((span) => span.textContent || \"\"), index)" in app
    assert "fetchWord(query)" in app
    assert "showWordCard(event, data)" in app
    assert "event.stopPropagation()" in app


def test_the_word_card_overlay_is_the_letter_language(
    tmp_path: Path,
) -> None:
    """The card itself: lemma + pos + forms + zh-first senses + examples,
    the 收起 link, the outside-click closer — zero radius; rd-1 随迁
    （面6 解除零阴影，DEC-OPI-dc0ba4b6-…13）：垫纸层承两级注册阴影，
    全黑阴影仍永禁（正面契约钉在 rd1 套件）。"""

    page = _page_of(tmp_path)
    assert "export function wordCard(data) {" in page
    assert 'card.className = "word-card"' in page
    assert '"wc-lemma"' in page
    assert '"wc-pos"' in page
    assert '"wc-forms"' in page
    assert '"wc-zh"' in page
    assert '"wc-en"' in page
    assert '"wc-example"' in page
    assert 'close.textContent = "收起"' in page
    assert "export function closeWordCard() {" in page
    assert "export function showWordCard(at, data) {" in page
    assert "document.addEventListener" in page
    # rd-4 随迁（9.12-23）+ v2 随迁（简报 §6「仅邮票/邮戳允许圆形；
    # 信纸物件圆角收窄一档 ≤2px」）：零大圆角面板法则的豁免位 =
    # 手迹/盖印/邮票几何 + 信纸物件 2px——红笔圈线椭圆 + 邮戳双圈圆
    # 两处（.postmark 与信封沓的 .env-mark 各含本体与 ::before）+
    # 邮票图形两枚（.stamp-v0/.stamp-v5）+ 信封沓的 2px 两处
    # （.envsel/.env，简报 §6 增补档；mc-2 起加编辑台的开场信预览
    # 短笺——同 ≤2px 信纸物件档；v2-2 起加翻页全览页卡 .envpage）。
    # 面板大圆角仍一处即红。
    assert page.count("border-radius") == 11
    assert "border-radius: 50%" in page
    assert "rgba(0, 0, 0" not in page


# ---------------------------------------------------------------------------
# 4. the living-registry registration


def test_word_card_is_registered_in_all_four_places() -> None:
    """The four-step induction, one cut: the spec ③ row, the components.css
    contract block (with its four clauses), the components.js factory and
    the COMPONENTS tuple — and the class is defined exactly once in the
    tree (the single-source clause over the new classes too)."""

    from tests.host.test_fg1_architecture import (
        COMPONENTS,
        _webui_all_text,
        _webui_text,
    )

    assert "word-card" in COMPONENTS
    # p-3 随迁：活注册表随 field/chip 入库生长两格（15 → 17）；
    # R-1 随迁：壳导航三件再长三格（17 → 20）；
    # R-1R 随迁：折叠组 disclosure 再长一格（20 → 21）；
    # R-1V 随迁：icon-set 入库再长一格（21 → 22）；
    # rd-4 曾随迁长到 23；cs-2 随迁：浮层伙伴卡退役再缩回（23 → 22）
    assert len(COMPONENTS) == 22
    spec = (
        Path(__file__).resolve().parents[2]
        / "docs" / "FRONTEND_SPEC.md"
    ).read_text(encoding="utf-8")
    assert "| 15 | word-card" in spec
    css = _webui_text("components.css")
    assert "15. word-card" in css
    js = _webui_text("components.js")
    assert "export function wordCard(data) {" in js
    # the factory is the only builder: the overlay assembly goes through
    # wordCard (a hand-built div in showWordCard would bypass the registry)
    assert "const card = wordCard(data);" in js
    whole = _webui_all_text()
    for selector in (
        ".wc-lemma {",
        ".wc-pos {",
        ".wc-forms {",
        ".wc-zh {",
        ".wc-en {",
        ".wc-example {",
    ):
        assert whole.count(selector) == 1, selector
    # v2-2 随迁（8.2.2③ 双形态）：".word-card {" 在 components.css 恰
    # 三处——浮卡基形、触屏 (hover: none) 档的 sheet 覆写、
    # @starting-style 的入场初值（全部同文件 = 单一物理出处不变；
    # 两档布局是同一组件的媒体查询分档，非第二实现）。
    assert whole.count(".word-card {") == 3
    assert css.count(".word-card {") == 3
    # ux-1 随迁：.word 的触屏镜像块已随 v2-2 波浪线修复退役
    # （8.2.2④——「全文常显点线」永禁）；".word {" 子串仍恰 2——
    # 基形 + (a) 最新信弱底纹块（.letter--latest .say .word）。
    assert whole.count(".word {") == 2
    assert css.count(".word {") == 2
