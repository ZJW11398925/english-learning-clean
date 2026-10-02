"""rd-4 — the full-face knife (the redesign program's last cut).

Authorization: ``DEC-OPI-dc0ba4b6-….9`` + the rd-4 survey brief (the five
hard constraints C-1..C-5). Four faces land together, each frontend-first
and honest about it:

A. **the partner face** — RETIRED by cs-2 (the dossier knife): the #23
   overlay card, its roster stub and the localStorage pick were dismantled
   in the same cut that opened the full-page dossier (``#space-partner``);
   the who block stays the trigger and the bar still grows no button
   element (below), and the retirement's absence pins live in
   ``tests/host/test_cs2_dossier_and_memory.py``;
B. **the settings face** (R-3 frontend-first) — the two placeholder
   sentences retire, the two standing truths survive, the teaching-mode
   reference block carries the fail-closed reading sentence;
C. **the handwriting layer** — the red-pencil circle (one static
   pseudo-element ellipse, no new animation) and the settled/skipped
   split (the two closing arms no longer share .skipped);
D. **the mechanism batch** — stamps only on verified rows, the en-route
   corner that comes off when the reply lands, the letter search over the
   loaded 50-turn window with the honest wording, the Chinese probe
   folded into the archive search string.

Eight groups (the slice VAL's own): the who-block trigger survives the
cs-2 retirement with the honest placeholders gone; the settings old
sentences are gone with the three modes present; the handwriting is on the
card with no data URI and one mark per card; stamps hit successes only, the
en-route badge comes off, the Chinese probe hits, the window wording
stands; the freeze lines hold (the static allowlist is still seven; the
one endpoint cs-2 adds is ``/api/partner``, by design).
"""

from __future__ import annotations

from pathlib import Path

from tests.host.test_fg1_architecture import FILES
from tests.host.test_w1_web import (
    _page_source,
    web_stack,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "src" / "elc" / "web.py"


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


def _spec_text() -> str:
    return (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 1. the partner face: the trigger survives the cs-2 retirement


def test_the_who_block_is_the_trigger_and_the_bar_grows_no_button(
    tmp_path: Path,
) -> None:
    """身份条原地的可点手感（cs-2 后仍在；mc-1 随迁改指信封沓）：who 块
    整体可点（app.js 接线 #space-parlor .top > div + 键盘可达——点开的
    是信封沓，mc-1 的选择器；再点一次收沓），品牌条不增长按钮元
    （r1_shell 的品牌条无钮钉随迁保留）；.who = 端点驱动的空槽
    （当前角色名，webui 零角色名字面）；v2-2 起 who-sub 退役
    （8.2.2① 主从条瘦身——身份介绍退入笔友档案全页）。"""

    index = _page_of(tmp_path)
    parlor = index.split('id="space-parlor"', 1)[1].split("</header>", 1)[0]
    # mc-1 随迁：信头 = 端点驱动的空槽（品牌名与副题退居门厅封面）
    assert '<div class="who"></div>' in parlor
    assert 'who-sub' not in parlor
    assert "<button" not in parlor
    app = index
    assert 'document.querySelector("#space-parlor .top > div")' in app
    assert 'whoBlock.setAttribute("tabindex", "0");' in app
    assert 'whoBlock.setAttribute("role", "button");' in app
    assert 'whoBlock.setAttribute("aria-label", "信封沓——挑一位笔友");' in app
    # the click wiring itself (a deleted call goes red, not just the
    # helper's name surviving elsewhere) — mc-1 随迁：点开信封沓
    assert (
        'whoBlock.addEventListener("click", (event) => {\n'
        "    event.stopPropagation();\n"
        "    if (envselPanel) {\n"
        "      closeEnvelopeSelector();\n"
        "      return;\n"
        "    }\n"
        "    openEnvelopeSelector();\n"
        "  });" in app
    )
    assert "event.stopPropagation();" in app
    # the hover affordance lives in components.css's hover media (rd-1:
    # screens carries zero hover rules), never as a button
    css = index
    assert "#space-parlor .top > div:hover .who {" in css


# cs-2 退役注记：rd-4 的伙伴卡四钉（工厂与浮层法 / 卡内四件 / 名册零
# 生效声称 / 四处同刀注册）随浮层卡与名册桩整体退役——缺位钉（浮层类
# 与名册桩零出现）与档案全页视图的正面钉整体落在
# tests/host/test_cs2_dossier_and_memory.py（退役同一刀出钉，不降强度：
# 触发钉上移保留，缺位面比四件存在钉更强）。


# ---------------------------------------------------------------------------
# 2. the settings face


def test_the_settings_face_replaces_the_placeholder(tmp_path: Path) -> None:
    """设置节真面（r1_shell/r1r/r1w 已随迁缺位钉；本钉补正面的结构）：
    两真句 + 指向句 + 诚实读法句 + 换档句 + 三档参考；纯静态——
    SECTION_PULLS 不拉本节（缺位钉保持）。"""

    index = _page_of(tmp_path)
    settings = index.split('id="drawer-settings"', 1)[1].split(
        'id="del-result"', 1)[0]
    assert "这台应用只服务你一个人（127.0.0.1，无账号无密码）。" in settings
    assert "模型端点与模型名由启动命令给定——页面不读取，也不显示。" in settings
    assert "批注频率在 温故 · 方向 里调。" in settings
    assert "当前这一档由启动命令给定——页面读不到，也不改它。" in settings
    assert "换端点或换档 = 改启动命令再启动。" in settings
    assert "娱乐 · 关系优先：聊得多，递得少，笔友以听和陪为主。" in settings
    assert "客厅以听和陪为主" not in settings
    assert "平衡：聊天与练句并行，批注适度。" in settings
    assert "学习优先：练句密度优先，批注递得勤，课程感更明显。" in settings
    assert "设置面还没有铺开。" not in settings
    assert "将来这里会有" not in settings
    app = index
    assert '"drawer-settings":' not in app
    spec = _spec_text()
    assert "#### 8.2.8 抽屉 · 设置（rd-4 修订版——R-3 前端先行真面）" in spec


# ---------------------------------------------------------------------------
# 3. the handwriting layer


def test_the_red_pencil_circle_is_one_static_mark(tmp_path: Path) -> None:
    """主形 = 红笔圈线：等回应的卡带 circled 类，锚行外包伪元素椭圆
    （v2 随简报 T2：色 = --seal 朱砂——待回应的批注是真实事件）+
    圆角椭圆 + rotate -2.5deg；静态形——零新 keyframes（v2 注册集 =
    五枚：paper-drop / ink-wash / ink-set / paper-unfold / stamp-press），
    零 data URI。"""

    page = _page_of(tmp_path)
    assert 'card.classList.add("circled");' in page
    css = page
    assert (
        ".note-paper.circled .note-head::after {" in css
    )
    assert "border: 2px solid var(--seal);" in css
    assert "border-radius: 50%; transform: rotate(-2.5deg);" in css
    # the mark rides pure geometry: no data URI anywhere on the face
    assert "data:" not in css.split("SHELL_ASSETS")[0]
    # keyframes: the v2 five registered set + paper-fold 沓收拢 /
    # page-turn 2D 翻页 + scrim-in（from-only 遮罩——v22 黑屏修复刀）。
    # v3-2 随迁 10→8：mc-2 zoom 对枚（2 枚）随编辑台容器化退役（同刀
    # 除名，⑩ 容器延展档取代——extendContainer 是 height 过渡，零新
    # keyframes）；历史：v2-2 加两枚 9.5 表落库 / v2-2R 随迁 9→10
    # （基线 517da30 实测本钉已红留痕）。
    assert css.count("@keyframes ") == 8
    assert "editor-zoom" not in css


def test_the_closing_arms_split_settled_from_skipped(tmp_path: Path) -> None:
    """两态可分：成功族 → 盖戳完成态（圈线摘下、#22 stamp 同枚印记、
    stamp-press 复用）；搁置/负值 → 淡出态（skipped 原样）。守恒律：
    一卡至多一处手迹——盖戳落地时 circled 已摘。"""

    page = _page_of(tmp_path)
    reply = _fn_body(page, "readReplyAnswer")
    assert 'const word = String(data.feedback || "").split("（")[0];' in reply
    assert 'card.classList.remove("circled");' in reply
    assert 'card.classList.add("settled");' in reply
    assert 'stamp.classList.add("card-stamp", "stamp-press");' in reply
    assert 'card.classList.add("skipped");' in reply
    assert 'word === "SUCCESS" || word === "ALTERNATIVE_SUCCESS"' in reply
    # the composer guide line rides with the moment's state
    assert "批注开着——回应写在上面那张；也可以直接写一封新信。" in page
    assert (
        'guide.hidden = !list.some((m) => m.lifecycle_state '
        '=== "AWAITING_USER");' in page
    )
    assert (
        "guide.hidden = data.moment_state !== \"AWAITING_USER\";" in page
    )


# ---------------------------------------------------------------------------
# 4. the mechanism batch


def test_stamps_land_on_verified_rows_only(tmp_path: Path) -> None:
    """盖戳只挂真实事件（v2 随简报 T2 换真值，强度升格）：档案明细行
    整族不再盖章——邮戳三真实事件 = 寄出（在途封）/ 结课（教学卡
    settled）/ 归档开启（信档日期戳），判分行不在其中（判词文字已是
    完整信息；旧 .arc-stamp 判分戳撤除，负控钉升格为全族缺位钉）。"""

    page = _page_of(tmp_path)
    archive = _fn_body(page, "renderArchive")
    # the whole verdict-stamp arm is gone from the archive renderer
    assert "arc-stamp" not in archive
    assert 'inkIcon("stamp")' not in archive
    css = page
    assert ".arc-stamp" not in css
    # the verdict row keeps its mono kv form (the stamp's information
    # successor is the human verdict word itself)
    assert 'line.className = "kv";' in archive
    assert "(OUTCOME_CN[claim.outcome] || claim.outcome)" in archive


def test_the_en_route_badge_comes_off_when_the_reply_lands(
    tmp_path: Path,
) -> None:
    """在途信封（v2 封/信分物，简报 T1-4）：刚寄出的信挂 .en-route
    信封形（矩形 + 封舌 + 折线，信文暂不可见）并盖「寄出」邮戳
    （邮戳三真实事件之一），回信落地或失败即摘封见信
    （finally 的落点就是这两个时刻）；「笔友把灯留着」的 typing 行
    随 v2-1 锚屏措辞。旧虚发丝角标退役。"""

    page = _page_of(tmp_path)
    turn = _fn_body(page, "postTurn")
    assert 'mine.classList.add("en-route");' in turn
    assert 'mine.classList.remove("en-route");' in turn
    assert (
        "const mine = addLine(\"user\", text,"
        " { enter: true, when: sentAt });" in turn
    )
    # the sent postmark rides the envelope and leaves with it
    assert 'postmark.className = "postmark postmark--sent stamp-press";' \
        in turn
    assert 'mine.querySelector(".postmark--sent")' in turn
    assert "信已寄出，等回信——笔友把灯留着。" in turn
    css = page
    # the envelope shape: the flap, the fold line, the hidden sheet
    assert ".letter.me.en-route::before {" in css
    assert ".letter.me.en-route::after {" in css
    assert ".letter.me.en-route .paper { visibility: hidden; }" in css
    # the old dashed corner badge is retired
    assert ".letter--en-route" not in css


def test_the_letter_search_is_window_honest(tmp_path: Path) -> None:
    """搜信里的句子：fetchHistory 的 50 轮窗口，口径写在脸上（只搜
    已加载的）；命中列「第 n 封（你/客厅）」+ 片段——历史轮次无
    时间戳，一个日期都不造；无命中一句实话。"""

    page = _page_of(tmp_path)
    index = page
    assert ">搜信里的句子</h3>" in index
    assert "只搜已加载的最近 50 轮。" in index
    search = _fn_body(page, "mountLetterSearch")
    assert "fetchHistory()" in search
    assert '"第 " + (i + 1) + " 封（" + who + "）"' in search
    assert 'input.placeholder = "搜信里的一句话……";' in search
    assert "这五十轮里没有这一句。" in search
    # 处置三 #4/#5：单飞（并发按键共用一次在途请求）+ 失败不谎报
    # 「没有」——读失败给失败态一句，不落到空窗结论
    assert "historyPending" in search
    assert "信箱这会儿没翻开——稍后再搜一次。" in search
    assert "history = { turns: [] };" not in search  # 失败≠空窗
    # the window has a freshness TTL — a cached empty pull must not wall
    # off letters that arrive later in the same session (the walkthrough's
    # live-render catch)
    assert "const LETTER_SEARCH_TTL = 10000;" in page
    assert "Date.now() - historyAt > LETTER_SEARCH_TTL" in search
    # no fabricated dates: the hit rows carry no timestamp call at all
    assert "whenNode" not in search
    assert "humanTime" not in search


def test_the_chinese_probe_rides_the_archive_search(tmp_path: Path) -> None:
    """中文 probe（rd-3 INFO-4 收口）：族名与判词的中文读法并入痕迹
    检索串——「接话」「答得漂亮」也搜得到。"""

    page = _page_of(tmp_path)
    archive = _fn_body(page, "renderArchive")
    assert "FAMILY_CN[familyOf(claim.target_id)] || \"\"" in archive
    assert "(OUTCOME_CN[claim.outcome] || \"\")" in archive
    assert "rd-3 INFO-4" in _spec_text()


# ---------------------------------------------------------------------------
# 5. the registration (four places, one cut) and the freeze lines
#
# cs-2 退役注记：rd-4 的「四处同刀注册」钉随浮层伙伴卡退役（注册行、
# 契约块、工厂、COMPONENTS 元组四处同刀清出，len 回 22）——退役的
# 四处缺位钉落在 tests/host/test_cs2_dossier_and_memory.py。docs/ 冻结
# 面零触碰：spec 的历史登记行保留原文（登记注记见 components.css 的
# 退役注记与 fg1 元组注记）。


def test_the_freeze_lines_hold(tmp_path: Path) -> None:
    """冻结线：静态白名单仍是七文件（C-2）；既有端点的 turn 面原句
    仍在；⑨-5 零新行（静态圈线与在途角标不入动效注册表）。
    cs-2 随迁：/api/partner 由本刀按设计新增（档案页的唯一读面），
    rd-4 的「无 /api/partner」禁令随之解除；/api/settings 的禁令保留
    （C-1 的其余半边不受退役影响）。"""

    web = WEB.read_text(encoding="utf-8")
    assert '"/api/settings"' not in web
    assert '"/api/turn"' in web
    assert '"/api/memory"' in web
    assert len(FILES) == 7
    spec = _spec_text()
    registry = spec.split("### 9.5 动效注册表", 1)[1].split("### 9.6", 1)[0]
    assert "红笔圈线" not in registry
    assert "在途角标" not in registry
    assert "### 9.12 rd-4 修订登记" in spec
    assert (
        "23. **伙伴面 + 设置真面 + 手写批注层 + 机制物化首批（rd-4 全面面，"
        in spec
    )
    for preview in ("模式真读面", "作答期聊天路由", "名册后端缝",
                    "跨信重现数据缝", "成长条目不可点"):
        assert preview in spec
