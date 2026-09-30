"""rd-4 — the full-face knife (the redesign program's last cut).

Authorization: ``DEC-OPI-dc0ba4b6-….9`` + the rd-4 survey brief (the five
hard constraints C-1..C-5). Four faces land together, each frontend-first
and honest about it:

A. **the partner face** (R-2 frontend-first stub state) — the who block
   is the trigger (the bar grows no button element), the #23 partner-card
   floats with the four honest items (the placeholder name, the
   relationship and episode reads off the existing /api/memory face, the
   three-card preview roster, the goto line); the pick rides localStorage
   with zero effect claims;
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

Eight groups (the slice VAL's own): the partner card opens and closes
with honest placeholders and no effect claims; the settings old sentences
are gone with the three modes present; the handwriting is on the card
with no data URI and one mark per card; stamps hit successes only, the
en-route badge comes off, the Chinese probe hits, the window wording
stands; the component is registered in all four places; the freeze lines
hold (web.py gains no endpoint, the static allowlist is still seven).
"""

from __future__ import annotations

from pathlib import Path

from tests.host.test_fg1_architecture import COMPONENTS, FILES
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
# 1. the partner face: the trigger, the card, the honest placeholders


def test_the_who_block_is_the_trigger_and_the_bar_grows_no_button(
    tmp_path: Path,
) -> None:
    """身份条原地的可点手感：who 块整体可点（app.js 接线 #space-parlor
    .top > div + 键盘可达），品牌条不增长按钮元（r1_shell 的品牌条
    无钮钉随迁保留）；.who/.who-sub 逐字不动（四处钉不动）。"""

    index = _page_of(tmp_path)
    parlor = index.split('id="space-parlor"', 1)[1].split("</header>", 1)[0]
    assert '<div class="who">英语客厅</div>' in parlor
    assert "一位固定笔友 · 中英不拘" in parlor
    assert "<button" not in parlor
    app = index
    assert 'document.querySelector("#space-parlor .top > div")' in app
    assert 'whoBlock.setAttribute("tabindex", "0");' in app
    assert 'whoBlock.setAttribute("role", "button");' in app
    assert 'whoBlock.setAttribute("aria-label", "笔友是谁？");' in app
    # the click wiring itself (a deleted call goes red, not just the
    # helper's name surviving elsewhere)
    assert (
        'whoBlock.addEventListener("click", (event) => {\n'
        "    event.stopPropagation();\n"
        "    openPartnerFace();\n"
        "  });" in app
    )
    assert "event.stopPropagation();" in app
    # the hover affordance lives in components.css's hover media (rd-1:
    # screens carries zero hover rules), never as a button
    css = index
    assert "#space-parlor .top > div:hover .who {" in css


def test_the_partner_card_factory_and_overlay_law(tmp_path: Path) -> None:
    """#23 工厂三件与 #15 同法（挂 body、点卡外关闭、DOM 移除语义）；
    工厂尾部纪律同 #21（querySelectorAll / parentElement 缺位——读本
    文件本体，union 的 app.js 半区不属本件）。"""

    page = _page_of(tmp_path)
    assert "export function partnerCard() {" in page
    assert "export function showPartnerCard(card) {" in page
    assert "export function closePartnerCard() {" in page
    assert "document.body.appendChild(card);" in page
    assert "openPartner.remove();" in page
    js = (REPO_ROOT / "src" / "elc" / "webui" / "components.js"
          ).read_text(encoding="utf-8")
    tail = js.split("export function partnerCard() {", 1)[1]
    assert "querySelectorAll" not in tail
    assert "parentElement" not in tail


def test_the_partner_card_carries_the_four_honest_items(
    tmp_path: Path,
) -> None:
    """卡内四件：诚实占位名（现役 character_package=None）、关系/近况
    只读 /api/memory（空态各说各的实话）、名册（前端静态临时副本 +
    「预览」徽标）、去向句直达抽屉记忆节。"""

    page = _page_of(tmp_path)
    assert '"一位还没取名字的笔友"' in page
    assert "名字还没处取——先这么叫着。" in page
    assert "还没有留下关于你们关系的记忆。" in page
    assert "还没有留下你们的近况。" in page
    assert "还没有留下关于你们关系的记忆" in _spec_text()
    # the reads come from the existing memory face only
    build = _fn_body(page, "buildPartnerCard")
    assert "stateBanner(\"loading\")" in build
    fill = _fn_body(page, "fillPartnerReads")
    assert "panel.relationship_memory" in fill
    assert "panel.episode" in fill
    assert 'relRows.slice(-2).reverse()' in fill
    assert "firstSentence(latest.summary)" in fill
    # the slots' own key shape (the walkthrough's live-render catch: a
    # slots.rel/relSlot mismatch is a silent TypeError in the browser)
    assert "const relSlot = slots.relSlot;" in fill
    assert "const epiSlot = slots.epiSlot;" in fill
    assert "slots.rel." not in fill
    assert "slots.epi." not in fill
    # the goto line lands the drawer's memory section
    assert 'gotoBtn.textContent = "抽屉 · 记忆";' in page
    assert "closePartnerCard();" in page
    assert 'showSpace("drawer");' in page


def test_the_roster_is_a_preview_with_zero_effect_claims(
    tmp_path: Path,
) -> None:
    """名册 = persona 域内容的前端静态临时副本（三位，各带「预览」
    只读徽标）；选中只落 localStorage；零生效声称——「重启后」全页
    缺位，注记句是唯一的意思句。"""

    page = _page_of(tmp_path)
    assert 'const PARTNER_PICK_KEY = "elp.partner.pick.v1";' in page
    for name in ("Maya", "Nadia", "Sam"):
        assert f'name: "{name}",' in page
    assert 'chip("预览", { badge: true })' in page
    assert "先记下你的意思——等伙伴的门真开了，这一位才会上场。" in page
    assert "记下了" in page and "先记下这一位" in page
    # zero effect claims: the promise word family is absent from the
    # app-facing script (the css contract's own forbidding comment is
    # not the face); the standing copy is the one meaning-sentence
    app = (REPO_ROOT / "src" / "elc" / "webui" / "app.js"
           ).read_text(encoding="utf-8")
    assert "重启后" not in app
    pick = _fn_body(page, "rosterCard")
    assert "writePartnerPick(sample.name)" in pick
    # the pick button, not the badge chip (the badge is the card's first
    # button — a bare "button" selector would rewrite 预览 to 记下了)
    assert 'other.querySelector("button.btn--pencil")' in pick
    # the refused write answers one honest line and never breaks the chat
    write = _fn_body(page, "writePartnerPick")
    assert "localStorage.setItem(PARTNER_PICK_KEY, name);" in write
    assert "return false;" in write
    read = _fn_body(page, "readPartnerPick")
    assert "return null;" in read
    assert "这一句没能记下——这版先不带它走，通信不受影响。" in page


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
    assert "娱乐 · 关系优先：聊得多，递得少，客厅以听和陪为主。" in settings
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
    （border 2px --pencil + 圆角椭圆 + rotate -2.5deg）；静态形——
    零新 keyframes（⑨-5 零新行的实现面），零 data URI。"""

    page = _page_of(tmp_path)
    assert 'card.classList.add("circled");' in page
    css = page
    assert (
        ".note-paper.circled .note-head::after {" in css
    )
    assert "border: 2px solid var(--pencil);" in css
    assert "border-radius: 50%; transform: rotate(-2.5deg);" in css
    # the mark rides pure geometry: no data URI anywhere on the face
    assert "data:" not in css.split("SHELL_ASSETS")[0]
    # zero new keyframes: the registered set is exactly the pre-existing
    # seven (ink-fade / note-arrive / paper-unfold / stamp-press /
    # paper-settle / seal-press / state-breathe)
    assert css.count("@keyframes ") == 7


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
    """盖戳只挂被验证面：档案明细行 outcome ∈ {SUCCESS,
    ALTERNATIVE_SUCCESS} 落 #22 stamp 水印小图；负值与半中不盖
    （负控钉——条件式逐字）。"""

    page = _page_of(tmp_path)
    archive = _fn_body(page, "renderArchive")
    assert "claim.outcome === \"SUCCESS\" ||" in archive
    assert 'claim.outcome === "ALTERNATIVE_SUCCESS"' in archive
    assert 'stamp.classList.add("arc-stamp");' in archive
    # the negative family never matches the stamp arm
    for word in ("PARTIAL", "FAILURE", "ABSTAIN"):
        assert f'claim.outcome === "{word}"' not in archive
    css = page
    assert ".arc-stamp { flex: none; width: 14px; height: 14px;" in css


def test_the_en_route_badge_comes_off_when_the_reply_lands(
    tmp_path: Path,
) -> None:
    """在途角标：刚寄出的信别上 .letter--en-route，回信落地或失败即摘
    （finally 的落点就是这两个时刻）；「客厅把灯留着」的 typing 行
    现役不动。"""

    page = _page_of(tmp_path)
    turn = _fn_body(page, "postTurn")
    assert 'mine.classList.add("letter--en-route");' in turn
    assert 'mine.classList.remove("letter--en-route");' in turn
    assert "const mine = addLine(\"user\", text, { enter: true });" in turn
    assert "信已寄出，等回信——客厅把灯留着。" in turn
    css = page
    assert ".letter--en-route::after {" in css
    assert "border-top: 1px dashed var(--pencil-soft);" in css


def test_the_letter_search_is_window_honest(tmp_path: Path) -> None:
    """搜信里的句子：fetchHistory 的 50 轮窗口，口径写在脸上（只搜
    已加载的）；命中列「第 n 封（你/客厅）」+ 片段——历史轮次无
    时间戳，一个日期都不造；无命中一句实话。"""

    page = _page_of(tmp_path)
    index = page
    assert ">搜信里的句子</h3>" in index
    assert "只搜已加载的最近 50 轮。" in index
    search = _fn_body(page, "mountLetterSearch")
    assert "history = await fetchHistory();" in search
    assert '"第 " + (i + 1) + " 封（" + who + "）"' in search
    assert 'input.placeholder = "搜信里的一句话……";' in search
    assert "这五十轮里没有这一句。" in search
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


def test_partner_card_is_registered_in_all_four_places() -> None:
    """#23 的四处同刀（word-card / disclosure / icon-set 先例）：③ 表
    行、components.css 契约块、components.js 工厂、COMPONENTS 元组；
    fg1 的三计数钉经元组自动抬到 23。"""

    assert "partner-card" in COMPONENTS
    assert len(COMPONENTS) == 23
    spec = _spec_text()
    assert "| 23 | partner-card" in spec
    css = (REPO_ROOT / "src" / "elc" / "webui" / "components.css"
           ).read_text(encoding="utf-8")
    assert "23. partner-card" in css
    js = (REPO_ROOT / "src" / "elc" / "webui" / "components.js"
          ).read_text(encoding="utf-8")
    assert "export function partnerCard() {" in js


def test_the_freeze_lines_hold(tmp_path: Path) -> None:
    """冻结线：web.py 零新端点（无 /api/partner、无 /api/settings——
    C-1）；静态白名单仍是七文件（C-2）；既有十二端点的 turn 面原句
    仍在；⑨-5 零新行（静态圈线与在途角标不入动效注册表）。"""

    web = WEB.read_text(encoding="utf-8")
    assert '"/api/partner"' not in web
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
