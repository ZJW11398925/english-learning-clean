"""v2-2 — the fullscreen recast cut（全屏重铸刀），pinned.

施工图 = docs/FRONTEND_SPEC.md 8.2 目标设计块（8.2.2①-④ / 8.2.2a 三
目标块 / 8.2.5 / 8.2.8① / 8.2.11 / 8.2.12 / ⑨-5 两目标行）；完工后
spec 内对应块回填为现役描述。十组钉：

1. **the masthead slim-down** — the .who is the roster's current name
   alone (the identity sub-slot retired, the greeting pool NOT invented
   client-side — the corpus face on the live endpoints has no
   scenario/opening, the cut stood down and said so);
2. **the dock/flow paper stack** — the flow is the paper pile on the
   desk (no panel feel of its own), the dock is the front-edge pad
   (paper-high face + soft shadow thrown UP onto the pile);
3. **the word-card bottom sheet** — one component, two tiers split by
   the input-form query (not a breakpoint): the touch tier is a fixed
   bottom panel with the paper curve entry (@starting-style), an
   ink scrim (no glassmorphism), Esc to close, and the pointer tier
   keeps the clamped float via custom props;
4. **the wavy underline is gone** — the standing dotted line in the
   (hover: none) half is retired at the root (the 8.2.2④ negative);
5. **the page-turn browser** — the envelope selector's browsing layer:
   2D turn geometry (translate + rotateY ≤8° + skew trapezoid, zero
   preserve-3d), the swipe guard in the ux-1 discipline, chevron
   clicks on the same animation, the honest five-face summary;
6. **the unfold-to-parlor** — the fold class (paper-fold 200ms +
   ink-wash reverse) and the start-writing success path that lands in
   the conversation view in the same frame;
7. **the letters archive** — envelope thumbnails, the archive
   datestamp (exactly one, a real event), the shared letterNode (no
   second letter implementation), the caliber sentence;
8. **the observations face** — the dedicated screen behind the
   archive-fold entry, six folded tables, the honest summary;
9. **the renamed sentences** — the penpal self-address lands on the
   three named faces and their pins (the pins live in r1r/r1w/rd4);
10. **the craft trio** — the .who head-rung metrics, the doc-line
    document typography (settings/privacy), the retired tokens
    placeholder note, and the font-stack consumption discipline.

预算刀内义务：新钉 15–30 例（本文件 14 例；台账口径以收集数为准）。
"""

from __future__ import annotations

from pathlib import Path

import elc.web

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = Path(elc.web.__file__).parent / "webui"
SHELL_FILES = ("index.html", "tokens.css", "components.css", "screens.css",
               "api.js", "components.js", "app.js")


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _page() -> str:
    return "".join(_text(name) for name in SHELL_FILES)


def _block(css: str, head: str) -> str:
    at = css.index(head)
    return css[at:css.index("}", at)]


# ---------------------------------------------------------------------------
# 1. the masthead slim-down (8.2.2①)


def test_the_masthead_is_the_name_alone_and_invents_no_greetings() -> None:
    """主从条瘦身的两面：肯定面 = .who 一行 + head 档读法；否定面 =
    问候语句池不落 webui（语料面缺口呈报在案：/api/characters 与
    /api/partner 都不回 scenario/opening——webui 不发明句库的纪律
    以「无任何问候语常量/句库字面」钉死，防有人后补造句）。"""

    index = _text("index.html")
    parlor = index.split('id="space-parlor"', 1)[1].split("</header>", 1)[0]
    assert '<div class="who"></div>' in parlor
    screens = _text("screens.css")
    who = _block(screens, ".who {")
    # the head rung (9.1): 18/26 + 0.03em — the metrics, verbatim
    assert "font-size: var(--fs-head);" in who
    assert "line-height: var(--lh-head);" in who
    assert "letter-spacing: var(--ls-head);" in who
    # the greeting pool is not invented client-side: no greeting
    # constant, no sentence bank, anywhere on the served face
    whole = _page()
    for marker in ("greeting", "GREETING", "问候句池", "greetPool"):
        assert marker not in whole, marker


# ---------------------------------------------------------------------------
# 2. the dock/flow paper stack (8.2.2②)


def test_the_dock_is_the_front_edge_pad_and_the_flow_stays_the_pile() -> None:
    """垫板层：顶纸 --paper-high + 上缘发丝线 + --stack-shadow-soft
    向上承影（soft 的 y 分量 -3px 即向上——落在前一封信的纸尾上）；
    聚焦微起保留（垫板被手压起）。信纸堆：flow 无面板感（零 box-shadow
    零 border——承托是 #stage 桌面档的 deep，不重复落）。"""

    screens = _text("screens.css")
    dock = _block(screens, ".dock {")
    assert "background: var(--paper-high);" in dock
    assert "border-top: 1px solid var(--rule);" in dock
    assert "box-shadow: var(--stack-shadow-soft);" in dock
    assert ".dock:focus-within { transform: translateY(-2px);" in screens
    flow = _block(screens, ".flow {")
    assert "box-shadow" not in flow
    assert "border" not in flow


# ---------------------------------------------------------------------------
# 3. the word-card bottom sheet (8.2.2③)


def test_the_word_card_sheet_tier_is_the_touch_layout() -> None:
    """sheet 档 = 输入形态查询分档（hover:none——与触屏纪律同族，不是
    断点边界）：fixed 底部、左右拉满、贴底、安全区垫层、垫纸错位层与
    浮卡双动画让位、@starting-style 纸面曲线入场（--dur-note ×
    --ease-paper + opacity ×1.3 恒慢）；墨色遮罩 = --ink 元素透明度
    （禁毛玻璃——backdrop-filter 永禁）。"""

    css = _text("components.css")
    at = css.index("@media (hover: none) {")
    tier = css[at:css.index("@media (hover: none) {", at + 20)]
    assert ".word-card { position: fixed; left: 0; right: 0; bottom: 0;" \
        in tier
    assert "max-width: none;" in tier
    assert "padding-bottom: calc(14px + var(--safe-bottom));" in tier
    assert "animation-name: none;" in tier
    assert "@starting-style {" in tier
    assert ".word-card { opacity: 0; transform: translateY(100%); }" in tier
    assert ("transition: transform var(--dur-note) var(--ease-paper),"
            in tier)
    assert "backdrop-filter" not in css
    scrim = _block(css, ".word-scrim {")
    assert "background: var(--ink);" in scrim
    assert "opacity: 0.4;" in scrim
    # 遮罩动画终态必须回落元素值 0.4（scrim-in from-only）：ink-wash 的
    # to{opacity:1} 在 both 填充下会永久覆盖 0.4 ⇒ 全屏不透明墨黑
    # （用户实测黑屏缺陷根因，2026-10-02 修复）
    hover_none = css[css.index("@media (hover: none) {"):]
    assert "animation: scrim-in var(--dur-note)" in hover_none
    kf = css[css.index("@keyframes scrim-in {"):][:200]
    assert "from { opacity: 0;" in kf
    assert "to" not in kf, "scrim-in 不得有 to——终态须回落元素 opacity 0.4"


def test_the_sheet_semantics_are_one_component_two_tiers() -> None:
    """关闭语义两档同源（R3）：遮罩 = 独立节点、同一 cardCloser 机制
    （点遮罩即「点卡外」）+ Esc 臂（v2-2 增）+ DOM 移除语义；定位 =
    --wc-x/--wc-y custom props（JS 零档位感知——媒体查询消费差异）。"""

    js = _text("components.js")
    assert 'scrim.className = "word-scrim";' in js
    assert "document.body.appendChild(scrim);" in js
    assert 'card.style.setProperty("--wc-x",' in js
    assert 'card.style.setProperty("--wc-y",' in js
    assert "card.offsetWidth" in js      # the clamp still measures the card
    assert 'if (event.key === "Escape") closeWordCard();' in js
    assert "openScrim.remove();" in js
    css = _text("components.css")
    # the pointer tier consumes the props; the sheet tier overrides them
    assert "left: var(--wc-x, 0px); top: var(--wc-y, 0px);" in css


# ---------------------------------------------------------------------------
# 4. the wavy underline stays dead (8.2.2④ negative — redundant with the
# ux-1 migrated pin, pinned here against regression of the root cause)


def test_no_standing_decoration_on_letter_words_anywhere() -> None:
    """负控：「全文常显点线」永禁——全 webui 无 .say .word 的静态
    text-decoration 声明（hover 半区与 :active/:latest 的替代形态
    除外；.word 基块只带命中带与过渡）。"""

    whole = _page()
    assert ".say .word { text-decoration" not in whole
    css = _text("components.css")
    word = _block(css, ".word {")
    assert "padding: 5px 2px; margin: -5px -2px;" in word
    assert "text-decoration" not in word


# ---------------------------------------------------------------------------
# 5. the page-turn browser (8.2.2a 翻页全览 + ⑨-5 page-turn)


def test_the_page_turn_is_two_d_and_shared() -> None:
    """2D 翻页感（⑨-5 落库行）：位移 + rotateY ≤8° + skewY 梯形——
    方向由 --pt-* 变量落；**零 preserve-3d**（3D 书本仿真永禁——简报
    T3 收窄注记的负控）；两消费面共用（沓翻页全览 + 面板横滑切换的
    同一动效语汇）。"""

    css = _text("components.css")
    assert "@keyframes page-turn {" in css
    turn = css[css.index("@keyframes page-turn {"):]
    turn = turn[:turn.index("}", turn.index("to {"))]
    assert "translateX(var(--pt-x, 14px))" in turn
    assert "rotateY(var(--pt-ry, 8deg))" in turn
    assert "skewY(var(--pt-sk, -1.2deg))" in turn
    whole = _page()
    # the negative rides the declaration form, not the word (the
    # contract comments name the ban; the ban is on the declaration)
    assert "preserve-3d;" not in whole
    assert "transform-style" not in whole
    assert "perspective(" not in whole
    # the two direction seats stay inside the ≤8° budget
    screens = _text("screens.css")
    assert "--pt-x: 14px; --pt-ry: 8deg; --pt-sk: -1.2deg;" in screens
    assert "--pt-x: -14px; --pt-ry: -8deg; --pt-sk: 1.2deg;" in screens


def test_the_browser_layer_lives_inside_the_selector() -> None:
    """沓内的浏览层：入口一钮两态（翻看/回沓）、翻页态不替换档案页
    （页卡上的「档案」动作仍进全页）、横滑守卫 = ux-1 纪律的第二
    工厂（wirePageTurn）、页序计数 mono、页卡诚实注记（读不回的四面
    如实说，开场信预览位缺席）。"""

    app = _text("app.js")
    js = _text("components.js")
    assert "function buildEnvelopeBrowser(box)" in app
    assert 'browse.textContent = envselBrowser ? "回沓" : "翻看";' in app
    assert "wirePageTurn(page, () => envselPageAt > 0," in app
    assert "if (next < 0 || next >= roster.length) return;" in app
    assert "openPartnerDossier(item.character_id);" in app
    assert 'veil.textContent = "性情、边界、开场信与场景四面读不回——她收在"' in app
    # the guard is the ux-1 discipline in a second factory
    assert "export function wirePageTurn(page, current, onTurn)" in js
    assert "Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)" in js
    assert 'event.target.closest("button, a, input, textarea, select, pre")' in js
    # 严格判定必须钉在 wirePageTurn 自己的函数体内（评审 F-M1）：全文件
    # 断言会被 wirePanelSwipe 的同字面兜底——弱化本工厂的 |dx|<=|dy|
    # 判定（斜滑误触翻页）时，仅工厂切片断言能红
    factory = js[js.index("export function wirePageTurn"):]
    factory = factory[: factory.index("\nexport function", 1)]
    assert "Math.abs(dx) < SWIPE_MIN_PX || Math.abs(dx) <= Math.abs(dy)" \
        in factory, "wirePageTurn 横滑严格判定被弱化（斜滑会误触翻页）"


# ---------------------------------------------------------------------------
# 6. the unfold-to-parlor (8.2.2a 起笔向下展开 + ⑨-5 注册行)


def test_the_selector_folds_and_the_start_writes_unfold() -> None:
    """起笔向下展开：fold 类 = paper-fold 200 × --ease-exit +
    ink-wash reverse 恒慢（transform/opacity 拆开）；三条切换路径
    （onTalk / 二次点选 / 起笔成功）都经 unfoldToParlor；reduced-motion
    直切（REDUCED_MOTION 归宿 + 480ms 保险丝）。"""

    app = _text("app.js")
    screens = _text("screens.css")
    assert "function unfoldToParlor(after)" in app
    assert "function closeEnvelopeSelector(opts)" in app
    assert 'panel.classList.add("envsel--fold");' in app
    assert 'event.animationName === "paper-fold"' in app
    assert "setTimeout(finish, 480);" in app
    assert "if (REDUCED_MOTION.matches || (opts && opts.skipFold))" in app
    # the start-writing success path lands in the conversation view
    assert ("const created = await switchToCharacter("
            "data.character.character_id);" in app)
    assert "if (created) unfoldToParlor();" in app
    fold = screens[screens.index(".envsel--fold {"):]
    fold = fold[:fold.index("}") + 1]
    assert "paper-fold var(--dur-panel-out) var(--ease-exit)" in fold
    assert "ink-wash calc(var(--dur-panel-out) * 1.3)" in fold
    assert "both reverse;" in fold
    # Esc steps back through the browser layer before folding the pad
    assert "setEnvelopeBrowser(false);" in app


# ---------------------------------------------------------------------------
# 7. the letters archive (8.2.11)


def test_the_letters_archive_is_enveloped_and_honest() -> None:
    """信封形接线：条目 = 信封缩略（矩形 + 封舌 polygon + 中央折线，
    4b 的缩略读法）；归档戳 = 打开信档盖一枚（真实事件、同屏 ≤1、
    日期 = 客户端当天）；展开读 = letterNode 复用（#4 单一出处——
    无第二份信件实现）；口径句写在脸上（50 轮窗口 + 第 n 封顺序数）。"""

    screens = _text("screens.css")
    mini = _block(screens, ".env-mini {")
    assert "width: 64px; height: 42px;" in mini
    assert "box-shadow: var(--stack-shadow-soft);" in mini
    before = _block(screens, ".env-mini::before {")
    assert "clip-path: polygon(0 0, 100% 0, 50% 96%, 50% 100%," in before
    after = _block(screens, ".env-mini::after {")
    assert "top: 50%; border-top: 1px solid var(--rule);" in after
    app = _text("app.js")
    assert 'stamp.className = "postmark postmark--archived";' in app
    assert 'diagBox("letters-datestamp")' in app
    assert "word.textContent = (now.getMonth() + 1) + \"·\" + now.getDate()" \
        in app
    assert "body.appendChild(letterNode(\"user\", turn.user));" in app
    assert "body.appendChild(letterNode(\"assistant\", turn.assistant));" in app
    index = _text("index.html")
    assert "只摊开已加载的最近 50 轮——第 n 封按窗口里的顺序数。" in index
    # the entry rides the flow's tail, the back row is the only way home
    assert 'id="letters-go"' in index
    assert 'id="letters-back"' in index
    # the shared factory is exported once — no hand-built letter anywhere
    js = _text("components.js")
    assert "function letterNode(cls, text, opts)" in js
    assert "export function addLine(cls, text, opts)" in js
    assert "const node = letterNode(cls, text, opts);" in js


# ---------------------------------------------------------------------------
# 8. the observations face (8.2.12)


def test_the_observations_have_a_dedicated_face() -> None:
    """专门面：档案折叠内一行入口（零数据拉取）、专门面 = 人话摘要一
    行 + 六表逐表 #21 折叠（默认全收）+ 指标定义折叠（英文原文）；
    摘要诚实（可得计数，不硬凑 spec 语汇的无源三数）。"""

    index = _text("index.html")
    app = _text("app.js")
    assert 'id="obs-entry"' in index
    assert 'id="obs-board"' in index
    assert 'id="obs-summary"' in index
    assert '"翻开原始读数 →"' in app
    assert "async function loadObservationsFace()" in app
    assert 'disclosure({ name: s.title, content }).root' in app
    assert '{ name: "指标定义（原文）", content: defs }).root' in app
    assert "门规漂移信号 " in app
    # the pre block is gone with the dedicated face (rows are .kv,账页)
    assert 'id="obsout"' not in index
    assert "<pre" not in index


# ---------------------------------------------------------------------------
# 9. the craft trio (⑨ 工艺三件 + 排印重铸)


def test_the_document_pages_read_like_documents() -> None:
    """中文文档页排印（9.1 工艺法则 6 落位）：设置/隐私两节的段落走
    .doc-line（正文 17/32 锁基线 + 首行缩进 2em + 零段距）；micro 标签
    已走 --meta-* 配方（rd-1 现役——.sec h3 在场即可）。"""

    screens = _text("screens.css")
    doc = _block(screens, ".doc-line {")
    assert "font-size: var(--fs-body);" in doc
    assert "line-height: var(--baseline);" in doc
    assert "text-indent: 2em;" in doc
    index = _text("index.html")
    for marker in (
        '<p class="doc-line">请笔友忘掉一些事——走出去就找不回来。</p>',
        '<p class="doc-line">这台应用只服务你一个人（127.0.0.1，无账号无密码）。</p>',
        '<p class="doc-line">娱乐 · 关系优先：聊得多，递得少，笔友以听和陪为主。</p>',
    ):
        assert marker in index, marker
    # the form rows lock the ui/small line-heights (8.2.4 基线重排)
    css = _text("components.css")
    field = _block(css, ".field .fieldname {")
    assert "line-height: var(--lh-ui);" in field
    inputs = _block(css, ".field input, .field select {")
    assert "line-height: var(--lh-small);" in inputs


def test_the_tokens_placeholder_note_is_retired() -> None:
    """工艺件：tokens.css 的「--dur-note 240ms 旧档」占位注释退役
    （其前提已由 v2-s 兑现——注释不再描述真实的落差；v2-s 处置刀的
    F-8 登记在此销账）。"""

    tokens = _text("tokens.css")
    assert "240ms" not in tokens
    assert "本注释即留痕" not in tokens
    # the note that replaced it states the retirement, not the gap
    assert "占位注释退役" in tokens


def test_the_font_stacks_are_consumed_by_var_only() -> None:
    """字体栈钉补均（spec INFO-3 面）：font-family 的声明值只走
    var()/inherit——五栈的字面不进任何声明（注释里的工艺引述不在
    禁列）；关键消费面对照 spec 3a/9.1（信笺正文 serif / 落款与案头
    日期 hand / 数据行 mono / 卡题与组头 ui 真粗 / 大题 display）。"""

    import re

    declaration = re.compile(r'font-family:\s*(?!var\(|inherit)[\w\'"]')
    for name in ("index.html", "tokens.css", "components.css",
                 "screens.css", "api.js", "components.js", "app.js"):
        body = _text(name)
        assert declaration.search(body) is None, name
    css = _text("components.css")
    assert "font-family: var(--f-serif);" in css    # .say 的栈（字面对照）
    assert "font-family: var(--f-hand);" in css     # 落款手迹位
    assert "font-family: var(--f-mono);" in css     # 数据行
    assert "font-family: var(--f-ui); font-weight: 600;" in css  # 卡题真粗
    screens = _text("screens.css")
    assert "font-family: var(--f-display);" in screens  # 大题/信头
    assert "font-family: var(--f-hand);" in screens     # 案头日期手迹位


# ---------------------------------------------------------------------------
# 10. the registry stays honest (⑤ 同刀登记)


def test_the_new_motions_are_registered_in_the_spec() -> None:
    """⑨-5 落库的回填面：page-turn 与 paper-fold 两枚新原语在 spec 的
    动效注册表达现役描述（目标行已回填），fold/unfold 的消费面在
    8.2.2a 的现役句里。"""

    spec = (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(
        encoding="utf-8")
    assert "| `page-turn`" in spec or "| page-turn " in spec
    assert "paper-fold" in spec
    assert "实施在 v2-2" not in spec.split("#### 8.2.2")[1].split(
        "#### 8.2.3")[0]
    assert "目标设计（实施在 v2-2）" not in spec.split("### 8.2")[1].split(
        "### 8.3")[0]
