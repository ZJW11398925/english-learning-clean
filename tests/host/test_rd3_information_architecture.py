"""rd-3 — the study space's information architecture (提案B, 温故三块化
+ 移走清单 + 档案面).

Authorization: ``DEC-OPI-dc0ba4b6-….9`` (rd-0 定案默认确认提案B) + 用户
令②（「大量信息并非用户需要看见的……设计了很多功能不代表都要显式表
达」）+ 调研B（``docs/research/2026-09-30-frontend-redesign-research.md``：
三分判据 / 移走清单 / NN/g 空态判据 / Wrapped 门槛）。Spec 面 = 8.2.3 /
8.2.5 重写 + 9.11 登记（条 22）。

Fourteen groups:

1. the default layer is exactly two blocks (今天的行动 / 你的成长) —
   the old three-block ids and the summary row retired, the ring block
   honestly omitted (no streak data source, no fabricated ring);
2. the action block pins one verb button — the three verbs, the N=0
   invitation, the open-moment line, and 开始复习 teaching the first
   due target (a real act, not navigation);
3. the growth block is word-level — three verdicts, at most three lines,
   the pull-revelation empty card with its path in;
4. the growth lines come from the latest verdict per target (claims
   newest-first, first sighting wins, 能做到 ranked ahead);
5. the diagnostics user face is gone — the five panels, the raw
   diagnostics payload, the renderer family and the fetch wrapper all
   retired (absence pins);
6. the diagnostics API survives in the API layer (归档读法) — web.py
   keeps the endpoint, the served page no longer references it;
7. the schedule table and the goals list live behind the 计划明细 fold —
   not on the default layer, the pull no longer reads diagnostics;
8. internal numbers never face the 温故 user — the four new renderers'
   bodies carry no scoreNode/confidence/urgency (the drawer's 把握 is
   the existing face, untouched by this cut);
9. the archive face has search, the aggregated timeline and its folds;
10. the archive loading and empty states are two shapes (进行时 vs 没有
    — NN/g: not-loaded must never read as no-records);
11. the Wrapped expectation reads the full count, not the served window;
12. spec 8.2.3 / 8.2.5 carry the new IA and 9.11 registers 条 22;
13. the tab reads 档案 display-only (internal ids and keys unchanged);
14. the gate-reason and teaching-action word faces left the front end
    with the diagnostics face (server codes never had Chinese here).
"""

from __future__ import annotations

from pathlib import Path

from tests.host.test_w1_web import (
    _page_source,
    web_stack,
)


def _page_of(tmp_path: Path) -> str:
    """The served page source over the plain offline stack (the F-G1
    union: index.html + every static asset it links)."""

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


def _section_of(index: str, section_id: str, next_id: str) -> str:
    """One top-level section's HTML slice, bounded by the next sibling."""

    return index.split(f'id="{section_id}"', 1)[1].split(
        f'id="{next_id}"', 1)[0]


def _spec_text() -> str:
    spec = (
        Path(__file__).resolve().parents[2]
        / "docs" / "FRONTEND_SPEC.md"
    ).read_text(encoding="utf-8")
    return spec


# ---------------------------------------------------------------------------
# 1. the default layer


def test_the_default_layer_is_exactly_two_blocks(tmp_path: Path) -> None:
    """今日节 = 恰两块（今天的行动 / 你的成长）：旧三块里 today-due /
    today-recent 与页首摘要行退役（缺位钉），today-practice 迁档案；
    环块诚实省略——无 ring/streak 词面，spec 8.2.3 带豁免句。"""

    index = _page_of(tmp_path)
    today = _section_of(index, "study-today", "study-goal")
    assert 'id="today-action"' in today
    assert 'id="growth-summary"' in today
    assert ">今天的行动</h3>" in today
    assert ">你的成长</h3>" in today
    assert 'id="today-due"' not in today
    assert 'id="today-recent"' not in today
    assert 'id="today-summary"' not in today
    assert 'id="today-practice"' not in today
    assert 'id="today-practice"' in index  # 迁档案，id 保留
    # the ring block is honestly omitted: no fabricated ring, no streak
    # word anywhere on the face
    assert "ring" not in today.lower()
    assert "streak" not in index.lower()
    assert "连续" not in today
    spec = _spec_text()
    assert "环块诚实省略" in spec


def test_the_action_block_pins_one_verb_button(tmp_path: Path) -> None:
    """块① 的一个动词按钮 = 当前第一优先的行动：批注在场 →「去回应」；
    到期在场 →「开始复习」开第一句到期句（真动作，不是导航）；全空 →
    邀请句 +「去聊一句」。到期行仍带「教我这一句」行内钮。"""

    page = _page_of(tmp_path)
    assert "有一张批注等着你回应。" in page
    assert 'parlorButton("去回应")' in page
    assert 'parlorButton("去聊一句")' in page
    assert 'start.textContent = "开始复习";' in page
    assert "postTeachMe(due[0].target_id)" in page
    assert "今天不用复习，要不要聊一句？" in page
    assert 'button.textContent = "教我这一句";' in page
    # the due filter is exactly DUE/OVERDUE（现役语义随迁）
    assert (
        'it.review_state === "DUE" || it.review_state === "OVERDUE"'
        in page
    )


def test_the_growth_block_is_word_level(tmp_path: Path) -> None:
    """块② 恰 3 条词级结论：三档词（能做到 / 还在练 / 暂时不能）、
    上限 3、pull-revelation 空态卡带学习线索与直达路径；不显示数值 /
    档位 / 置信度。"""

    page = _page_of(tmp_path)
    assert "const GROWTH_LINES = 3;" in page
    assert 'outcomes: ["SUCCESS", "ALTERNATIVE_SUCCESS"], word: "能做到"' \
        in page
    assert 'outcomes: ["PARTIAL", "ABSTAIN"], word: "还在练"' in page
    assert 'outcomes: ["FAILURE"], word: "暂时不能"' in page
    assert "rows.slice(0, GROWTH_LINES)" in page
    assert "学过一次之后，这里会出现你掌握的技能。" in page
    assert "先去案头聊一句，批注会自己来找你。" in page
    # the empty card's path in is the same parlor button
    growth = _fn_body(page, "renderGrowth")
    assert 'parlorButton("去聊一句")' in growth


def test_growth_lines_come_from_latest_verdicts(tmp_path: Path) -> None:
    """聚合语义：每表达取最新一次判分（claims 最新在前，首次出现即
    最近）；能做到档优先于还在练、暂时不能（映射序 = 渲染序）。"""

    page = _page_of(tmp_path)
    growth = _fn_body(page, "renderGrowth")
    assert "latest.has(claim.target_id)" in growth
    # the verdict buckets render in GROWTH_VERDICTS order (能做到 first):
    # the loop walks the map per bucket, not per target
    assert "for (const verdict of GROWTH_VERDICTS) {" in growth
    assert "verdict.outcomes.includes(claim.outcome)" in growth


# ---------------------------------------------------------------------------
# 2. the moved-away list


def test_the_diagnostics_user_face_is_gone(tmp_path: Path) -> None:
    """诊断五板与「为什么 · 原值」用户面零渲染：五板 id、diag-raw、
    set-diagnostics / set-learning 容器、渲染函数族、拉取函数全部退役
    （缺位钉）。"""

    index = _page_of(tmp_path)
    for gone in ("why-teach", "why-not-teach", "why-evidence",
                 "why-support", "why-degraded", "diag-raw",
                 "set-diagnostics", "set-learning"):
        assert f'id="{gone}"' not in index, gone
    for gone in (">为什么留了这张批注</h3>", ">为什么没有递</h3>",
                 ">判分有什么变化</h3>", ">你收到了哪些帮助</h3>",
                 ">有没有从简处理的轮次</h3>", "为什么 · 原值"):
        assert gone not in index, gone
    app = index  # the served union covers app.js
    for gone in ("function renderWhyTeach", "function renderWhyNot",
                 "function renderEvidence", "function renderSupport",
                 "function renderDegraded", "loadDiagnostics",
                 "DIAG_PANEL_IDS", "GATE_REASON_CN", "GATE_DECISION_CN",
                 "ACTION_CN", "reasonsNode"):
        assert gone not in app, gone
    api = app  # the union covers api.js
    assert "fetchDiagnostics" not in api


def test_the_diagnostics_api_survives_in_the_api_layer(
    tmp_path: Path,
) -> None:
    """归档读法（9.11-22）：web.py 的 /api/diagnostics 端点不动（零
    diff），页面源不再引用它——API 与其数据面钉保留在测试层（
    test_f1_product_shell.py 第 3 节直打端点）。"""

    web = (
        Path(__file__).resolve().parents[2]
        / "src" / "elc" / "web.py"
    ).read_text(encoding="utf-8")
    assert '"/api/diagnostics"' in web
    assert "def diagnostics(" in web
    page = _page_of(tmp_path)
    assert '"/api/diagnostics"' not in page


def test_schedule_and_goals_are_not_on_the_default_layer(
    tmp_path: Path,
) -> None:
    """全量排程与目标清单降入「计划明细」折叠：两个原值面板的 id 静态
    落在 plan-detail 内（默认收），今日节不含它们；档案节的拉取只读
    学习一面（loadDiagnostics 缺位）。"""

    index = _page_of(tmp_path)
    plan = index.split('id="plan-detail"', 1)[1].split(
        'id="book-slot"', 1)[0]
    assert 'id="learn-schedule"' in plan
    assert 'id="learn-goals"' in plan
    today = _section_of(index, "study-today", "study-goal")
    assert 'id="learn-schedule"' not in today
    assert 'id="learn-goals"' not in today
    app = index
    assert 'name: "计划明细（复习排程 · 目标）"' in app
    assert '"study-progress": () => { loadLearning(); },' in app
    assert "loadDiagnostics" not in app


def test_internal_numbers_never_face_the_user(tmp_path: Path) -> None:
    """内部数值永不面向温故用户：四个新渲染函数体内无 scoreNode /
    confidence / urgency / priority（词级表达替代）；「把握」的既有
    形态只在抽屉记忆面（本刀不触碰——豁免登记 9.11-22）。"""

    page = _page_of(tmp_path)
    for fn in ("renderGrowth", "renderTodayAction", "renderArchive",
               "renderPlanLine"):
        body = _fn_body(page, fn)
        for word in ("scoreNode", "confidence", "urgency", "priority"):
            assert word not in body, (fn, word)
    # the word-level replacements are on the face; the drawer's 把握
    # stays where it was (untouched face)
    assert "能做到" in page
    memory = _fn_body(page, "renderMemRelationship")
    assert "把握" in memory


# ---------------------------------------------------------------------------
# 3. the archive face


def test_the_archive_face_has_search_timeline_and_folds(
    tmp_path: Path,
) -> None:
    """档案节 = 搜索 + 聚合时间线 + 折叠：搜索框与无命中句、时间桶
    （本周 / 上周 / {m} 月 / 去年 / 更早）、桶行拼接、三个折叠名。"""

    page = _page_of(tmp_path)
    assert 'input.placeholder = "搜一句痕迹……";' in page
    assert 'noHit.textContent = "没搜到这一句的痕迹。";' in page
    assert 'return "本周";' in page
    assert 'return "上周";' in page
    assert 'return "去年";' in page
    assert 'return "更早";' in page
    assert '(then.getMonth() + 1) + " 月"' in page
    assert '次批注，主题 ' in page
    assert 'name: "按表达看：在学的表达"' in page
    assert 'name: "原始读数（给排查用）"' in page
    # v2-2 随迁（8.2.12）：观察读数迁入专门面——折叠内只留入口行
    assert '"翻开原始读数 →"' in page
    index = page  # the union covers index.html
    assert ">痕迹</h3>" in index
    assert ">计划</h3>" in index
    assert "未来 7 天：今天 " in page


def test_the_archive_loading_and_empty_are_two_shapes(
    tmp_path: Path,
) -> None:
    """加载态两形（NN/g：未加载不得显示无记录）：进行时占位句挂
    loading 横幅、空态句走 diagEmpty——两种形态、两句话、不同答复。"""

    page = _page_of(tmp_path)
    assert 'stateBanner("loading",\n    { text: "批注正在来的路上……" })' \
        in page
    assert 'diagEmpty(board, "还没有批注留痕——聊起来才会有。")' in page
    learn = _fn_body(page, "loadLearning")
    assert "批注正在来的路上……" in learn
    assert "diagEmpty" not in learn.split("try {", 1)[0]
    # 处置二（OCR 独有捕获 #1/#2）：archive-board 不得在通用横幅列表里
    # ——通用 loading/错误循环会整板覆盖它的定制进行时占位并重复清板
    ids = page.split("const LEARN_PANEL_IDS = [", 1)[1].split("];", 1)[0]
    assert '"archive-board"' not in ids
    # 处置二（OCR 独有捕获 #4）：空态分支必须保留期待句——0 条时
    # 「攒够 30 次……现在有 0 条」与「还没有批注留痕」同屏可读
    empty_branch = page.split('diagEmpty(board, "还没有批注留痕', 1)[1] \
                           .split("return;", 1)[0]
    assert "这里会讲一个学期的故事" in empty_branch


def test_the_wrapped_expectation_reads_the_full_count(
    tmp_path: Path,
) -> None:
    """Wrapped 期待态读全量计数（evidence_claim_count），不读服务端
    已加载的明细窗口；门槛 30；不足时讲期待不讲遗憾。"""

    page = _page_of(tmp_path)
    assert "const ARCHIVE_STORY_GATE = 30;" in page
    archive = _fn_body(page, "renderArchive")
    assert "evidence.evidence_claim_count || 0" in archive
    assert "total < ARCHIVE_STORY_GATE" in archive
    assert "这里会讲一个学期的故事" in archive
    spec = _spec_text()
    assert "不足门槛讲期待不讲遗憾" in spec


# ---------------------------------------------------------------------------
# 4. spec + naming + retired word faces


def test_spec_carries_the_new_ia_and_the_registration() -> None:
    """spec 8.2.3 / 8.2.5 重写为新 IA（线框 + 定稿双形态），9.11 登记
    条 22 引 DEC-…9 + 调研B + 移走清单。"""

    spec = _spec_text()
    assert "#### 8.2.3 温故 · 今日（rd-3 修订版——默认层两块）" in spec
    assert "#### 8.2.5 温故 · 档案（rd-3 修订版——收藏档）" in spec
    assert "环块诚实省略：无可靠的连续天数数据源" in spec
    assert "批注正在来的路上……" in spec
    assert "攒够 30 次批注，这里会讲一个学期的故事" in spec
    assert "### 9.11 rd-3 修订登记（信息架构重构——提案B，2026-09-30）" \
        in spec
    assert "22. **温故信息架构重构（提案B「今日 + 一行成长」）**" in spec
    assert "DEC-OPI-dc0ba4b6-…9" in spec
    assert "2026-09-30-frontend-redesign-research.md" in spec
    assert "用户面零渲染" in spec
    assert "归档读法" in spec


def test_the_record_tab_reads_archive_display_only(tmp_path: Path) -> None:
    """节签 记录→档案：显示名迁移、内部 id 与键零改名（data-section、
    panel id、SECTION_NAMES 键、DEFAULT_SECTION 全部保持）。"""

    index = _page_of(tmp_path)
    assert ">档案</button>" in index
    assert ">记录</button>" not in index
    assert 'data-section="progress"' in index
    assert 'id="study-progress"' in index
    app = index
    assert 'progress: "档案"' in app
    assert 'progress: "记录"' not in app
    assert 'const DEFAULT_SECTION = { study: "today", drawer: "memory" };' \
        in app


def test_the_gate_words_left_the_front_end_with_diagnostics(
    tmp_path: Path,
) -> None:
    """门规理由二十码与批注动作四词的中文映射随诊断面退役（词面归
    web.py 的码词与教学卡自身的词面——服务端从未有这些中文映射）；缺位
    钉钉住前端不回潮。"""

    page = _page_of(tmp_path)
    for gone in ("TEACHING_OPEN", "TEACHING_HINT", "TEACHING_REVEAL",
                 "TEACHING_EXPLANATION", "另一张批注还在进行",
                 "批注锁不成立", "这张批注走不下去",
                 "AUTO_SESSION_BUDGET_UNREADABLE:"):
        assert gone not in page, gone
