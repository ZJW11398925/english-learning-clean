"""v3-a — 前端升级刀（navdock 落墨页签 N-A + dock 信纸全幅写作态 D-B）。

Authorization: DEC-OPI-95287e92-…5（两入口分工预裁 + 用户首验否决面）
+ 研究报告 §4 推荐组合。四组钉（VAL 面的机检半区）：

A. **落墨页签**（#18 显式修订入 9.13）：三枚新图标 + 同钮结构 +
   paper-high 垫条 + 令牌账反推 padding（N5 实高恒等式）+ 落墨态
   fill-opacity 双侧曲线；
B. **笔搁触发条 + 写作态**（8.2.2⑤）：44px 触发条、textarea 唯一
   真源（双 textarea 永禁）、写作面骨架（dateline/称呼位/寄出链）、
   矮视口降级块、层序与互斥（置灰优先/开沓先收/进空间收）；
C. **草稿安全律**（10.3-6 同构独立桶）：draft- 桶键、input 随存、
   寄出即清、退出保稿、与 compose-draft- 桶互不覆写；
D. **登记面**：spec 9.13/8.2.2⑤+⑤.1/⑩/⑨-5 两行/②-5 两令牌在册，
   O7 死区清账与 goal-save 补差退役在册。
"""

from __future__ import annotations

from pathlib import Path

from tests.host.test_w1_web import (
    _page_source,
    web_stack,
)

REPO = Path(__file__).resolve().parents[2]


def _text(rel: str) -> str:
    return (REPO / "src" / "elc" / rel).read_text(encoding="utf-8")


def _block(source: str, head: str) -> str:
    after = source.split(head, 1)[1]
    return after[: after.index("}")]


def _page_of(tmp_path: Path) -> str:
    with web_stack(tmp_path / "app.db") as stack:
        return _page_source(stack)


# ---------------------------------------------------------------------------
# A. 落墨页签（#18）


def test_navdock_ink_tab_structure_and_material() -> None:
    """三枚签行 = 图标插槽 + 文字标签同钮（图标永不单独承担语义）；
    垫条材质与写信区垫板同族（--paper-high 顶纸）；上下 padding 从
    --navdock-h 反推——实高恒等于令牌（历史 54/57 账实差消亡），
    散写 6px 账退役。"""

    index = _text("webui/index.html")
    for glyph, word in (("desk", "案头"), ("revisit", "温故"),
                        ("drawer", "抽屉")):
        chunk = index.split(f'data-icon="{glyph}"', 1)[1][:200]
        assert f'>{word}</span></button>' in chunk, (glyph, word)
    css = _text("webui/components.css")
    block = css[css.index("\n.navdock {"):]
    block = block[: block.index("}")]
    assert "background: var(--paper-high);" in block
    assert "6px var(--read-pad)" not in block
    assert "calc((var(--navdock-h) - 44px - 1px) / 2)" in block
    tokens = _text("webui/tokens.css")
    assert "--navdock-h: 60px;" in tokens


def test_ink_fill_state_uses_two_sided_curves() -> None:
    """落墨当前态：--on 图标 fill-opacity .15 淡墨渍底（进入 260ms ×
    --ease-paper），非当前态过渡走退出侧（200ms × --ease-exit）——
    一褪一落同帧（⑨-5 v3-a 行；v3-aR 用户首验否决实墨填充后修订，
    裁决 DEC-OPI-76a0a10a-…9）；下划线语汇从导航当前态退役（--on 无
    text-decoration）。"""

    css = _text("webui/components.css")
    base = _block(css, ".navdock-item .inkicon {")
    assert "fill-opacity: 0;" in base
    assert "var(--dur-panel-out)" in base
    assert "var(--ease-exit)" in base
    on = _block(css, ".navdock-item--on .inkicon {")
    assert "fill-opacity: 0.15;" in on
    assert "var(--dur-note)" in on
    assert "var(--ease-paper)" in on
    on_item = _block(css, ".navdock-item--on {")
    assert "text-decoration" not in on_item
    assert "font-weight: 600;" in on_item


def test_navdock_fold_yields_and_restores() -> None:
    """让位与归位：--fold 收半（paper-fold 200 × --ease-exit）在册；
    app.js 的 yieldNavdock/restoreNavdock 双面在（fold → [hidden]、
    归位按当前空间还可见性、fuse 内查写作态仍在场）。"""

    screens = _text("webui/screens.css")
    assert ".navdock--fold { animation: paper-fold var(--dur-panel-out)" \
        in screens
    app = _text("webui/app.js")
    for mark in ("function yieldNavdock() {", "function restoreNavdock() {"):
        assert mark in app
    body = app[app.index("function yieldNavdock() {"):]
    body = body[: body.index("function restoreNavdock() {")]
    assert 'navdock.classList.add("navdock--fold");' in body
    assert 'if (composeOpen()) navdock.hidden = true;' in body
    restore = app[app.index("function restoreNavdock() {"):]
    restore = restore[: restore.index("\n}", restore.index("navdock.hidden"))]
    assert 'navdock.classList.remove("navdock--fold");' in restore
    assert 'current === "letters" || current === "obs";' in restore


# ---------------------------------------------------------------------------
# B. 笔搁触发条 + 写作态


def test_trigger_strip_is_the_only_standing_tax() -> None:
    """收起态 = 44px 触发条（--dock-trigger-h）；投影文案两态（提笔/
    批注指路行原文）；触发条在册、aria-expanded 在；flow 尾距走触发条
    账（O7 死区清账——手写余量退役）。"""

    index = _text("webui/index.html")
    assert 'id="dock-trigger"' in index
    assert 'aria-expanded="false"' in index
    assert 'class="dock-trigger-idle">提笔 · 今日如何？</span>' \
        in index
    note = index[index.index('id="dock-trigger-note"'):]
    note = note[: note.index("</span>")]
    assert "批注开着——回应写在上面那张；也可以直接写一封新信。" in note
    screens = _text("webui/screens.css")
    trigger = _block(screens, ".dock-trigger {")
    assert "height: var(--dock-trigger-h);" in trigger
    flow = _block(screens, ".flow {")
    assert "var(--dock-trigger-h)" in flow
    assert "256px" not in flow


def test_compose_face_single_truth_and_anatomy() -> None:
    """写作面骨架：dateline + 称呼位 + form#send（textarea 唯一真源——
    页面恰一枚 #text，双 textarea 永禁）+ 底行寄出链；--open 尺寸
    修饰类在 textarea 上（#2 变体，字面唯一出处不动）。"""

    index = _text("webui/index.html")
    assert index.count('<textarea id="text"') == 1
    assert 'class="pen pen--open"' in index
    for mark in ('id="compose-dateline"', 'id="compose-salut"',
                 'id="compose-close"', 'class="compose-sendrow"',
                 'id="reply-guide"'):
        assert mark in index
    screens = _text("webui/screens.css")
    open_pen = _block(screens, ".dock--compose .pen--open {")
    assert "max-height: none;" in open_pen
    sendrow = _block(screens, ".compose-sendrow {")
    assert "justify-content: flex-end;" in sendrow


def test_compose_adaptive_state_and_unified_autosize() -> None:
    """写作态 = ⑩ 全页成员（fr-A 收窄：底缘贴底 + 高度随稿纸内容自适应
    + 上限 50dvh——v3-a 的近全屏（fixed 全高）与 520px 降级双形态随本刀
    退役）；聚焦微起只在非写作态（写作态臂归零）；稿纸 autosize 统一
    封顶（composePenCap = 50dvh − 铬件账，下限 4×baseline）。"""

    screens = _text("webui/screens.css")
    compose = _block(screens, ".dock.dock--compose {")
    assert "bottom: 0;" in compose
    assert "top: auto;" in compose
    assert "max-height: 50dvh;" in compose
    lift = _block(screens, ".dock.dock--compose:focus-within {")
    assert "transform: none;" in lift
    # fr-A：近全屏形态与 520px 降级块一并退役（统一内容自适应形态）
    assert "top: calc(var(--sp-8) + var(--sp-1));" not in compose
    assert "@media (max-height: 520px)" not in screens
    app = _text("webui/app.js")
    assert 'dock.classList.add("dock--compose");' in app
    assert "function composePenCap() {" in app
    assert "Math.floor(window.innerHeight / 2) - 148" in app
    assert "autosizeTo(pen, composePenCap())" in app
    assert "SHORT_VIEWPORT" not in app


def test_esc_layering_and_mutual_exclusion() -> None:
    """层序与互斥（⑩ 10.4/10.3-5）：composeEsc 让位浮层（wordCardOpen
    裁决）；升写作态先收浮层；开沓先收写作态（保稿，置灰优先——
    openComposeFace 的 stilled 守卫是第二道机械闸）；进任何空间收
    写作态。触发条点击接线在。"""

    app = _text("webui/app.js")
    esc = app[app.index("function composeEsc(event) {"):]
    esc = esc[: esc.index("function openComposeFace() {")]
    assert 'if (wordCardOpen()) return;' in esc
    opener = app[app.index("function openComposeFace() {"):]
    opener = opener[: opener.index("function closeComposeFace(opts) {")]
    assert 'if (dock.classList.contains("dock--stilled")) return;' in opener
    assert "closeWordCard({ skipOut: true });" in opener
    assert "closeComposeFace();" in app[
        app.index("async function openEnvelopeSelector() {"):
        app.index("setNavdockStilled(true);   // 硬伤 A")]
    show = app[app.index("function showSpace(name) {"):]
    show = show[: show.index("markNavdock(name);")]
    assert "closeComposeFace();" in show
    assert 'document.getElementById("dock-trigger").addEventListener(' in app
    assert '"click", openComposeFace);' in app


def test_guide_sentence_rides_both_faces_from_one_beat() -> None:
    """批注开着：触发条文案态与 #reply-guide 同拍同源（components.js
    的 showMoments/noteDelivery 两处既有行原样保留 + syncDockTriggerNote
    同步半）；同步函数在库、两处落点在。"""

    components = _text("webui/components.js")
    assert ('guide.hidden = !list.some((m) => m.lifecycle_state '
            '=== "AWAITING_USER");' in components)
    assert ('guide.hidden = data.moment_state !== "AWAITING_USER";'
            in components)
    assert components.count("syncDockTriggerNote(") == 3   # 定义 + 两落点
    assert "function syncDockTriggerNote(awaiting) {" in components
    # 处置刀（评审 F-1）：文案态 = 双向切换——idle 与 note 互斥；只显
    # note 不藏 idle 会让两文案拼接被 ellipsis 截断（活体实拍缺陷）
    assert 'if (note) note.hidden = !awaiting;' in components
    assert 'if (idle) idle.hidden = !!awaiting;' in components
    assert 'const idle = document.querySelector(".dock-trigger-idle");' \
        in components


# ---------------------------------------------------------------------------
# C. 草稿安全律（10.3-6 同构独立桶）


def test_draft_bucket_is_structurally_independent() -> None:
    """桶键：draft-<character_id>（无角色落 draft-local）——与起笔桶
    compose-draft-<character_id> 同构独立 key（两桶互不覆写）；两桶
    函数同 file 在册。"""

    app = _text("webui/app.js")
    assert 'return "draft-" + (cid || "local");' in app
    assert 'return `compose-draft-${characterId}`;' in app
    assert app.count("sessionStorage.getItem") >= 2
    assert app.count("sessionStorage.removeItem") >= 2


def test_draft_law_save_clear_and_keep() -> None:
    """安全律三面：input 随写随存（存不上不打断）；寄出是唯一清稿
    时机（submit 半区 removeItem + 收起/Esc 不清）；退出保稿（close
    半区零 removeItem、重开 restore）。"""

    app = _text("webui/app.js")
    input_arm = app[app.index('document.getElementById("text")'
                              '.addEventListener("input"'):]
    input_arm = input_arm[: input_arm.index("autosizePen();")]
    assert 'sessionStorage.setItem(dockDraftKey(), pen.value);' in input_arm
    submit_arm = app[app.index('document.getElementById("send")'
                               '.addEventListener("submit"'):]
    submit_arm = submit_arm[: submit_arm.index("postTurn(text)")]
    assert "sessionStorage.removeItem(dockDraftKey());" in submit_arm
    closer = app[app.index("function closeComposeFace(opts) {"):]
    closer = closer[: closer.index("\n}", closer.index("restoreNavdock"))]
    assert "sessionStorage.removeItem" not in closer
    opener = app[app.index("function openComposeFace() {"):]
    opener = opener[: opener.index("function closeComposeFace(opts) {")]
    assert "sessionStorage.getItem(dockDraftKey());" in opener


def test_focus_returns_to_the_pen_rest() -> None:
    """写信焦点流不丢（两源一收口）：寄出路径 = composeFocusPending 落旗
    先于收场（fold finish 时触发条接笔——直接 focus 与 fold 竞态落空，
    活体实证过的时序）；显式退出 = opts.refocus；条态寄出 → 焦点留
    textarea（现役续写手感）。"""

    app = _text("webui/app.js")
    submit_arm = app[app.index('document.getElementById("send")'
                               '.addEventListener("submit"'):]
    submit_arm = submit_arm[: submit_arm.index("postTurn(text)")]
    assert "composeFocusPending = true;" in submit_arm
    fin = app[app.index("postTurn(text).finally(() => {"):]
    fin = fin[: fin.index("});", fin.index("if (!wasComposing)"))]
    assert "if (!wasComposing) input.focus();" in fin
    finish = app[app.index("function closeComposeFace(opts) {"):]
    finish = finish[: finish.index("if (REDUCED_MOTION.matches) {")]
    assert "composeFocusPending = false;" in finish
    assert "trigger.focus();" in finish
    assert "opts && opts.refocus" in finish


# ---------------------------------------------------------------------------
# D. 登记面（spec 与令牌账）


def test_tokens_and_spec_registrations_are_in_place() -> None:
    """②-5 两新令牌 + --navdock-h 实高语义；③ #18/#2/#22 行、⑨-4
    名册、⑨-5 两新行、⑩ 三处、8.2.2⑤+⑤.1 定谳段、9.13 修订登记——
    登记不是归档，缺一处即红。"""

    spec = (REPO / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    tokens = _text("webui/tokens.css")
    assert "--dock-trigger-h: 44px;" in tokens
    assert "--dock-compose-inset: 16px;" in tokens
    for mark in (
        "### 9.13 v3-a 修订登记",
        "⑤ 【案头写信区两态化——现役（v3-a 落地",
        "⑤.1 【两入口分工定谳（v3-a）】",
        "（8.2.2a）= 沓容器内的仪式写信",
        "案头笔搁/写作态（本条）= 日常快聊",
        "案头写作态（`.dock--compose`，v3-a",
        "| 落墨页签（v3-a——⑨-5 新行",
        "| 写作态升落（v3-a——⑨-5 新行",
        "现役十枚与锚位",
        "「禁止变体——图标」条款显式修订",
    ):
        assert mark in spec, mark
    # ⑩ 10.3-6 的同构独立桶句在册
    assert "draft-<character_id>" in spec
    assert "同构但独立 key" in spec


def test_desktop_compose_inset_consumes_the_token() -> None:
    """--dock-compose-inset 有现役消费面（桌面档面板两侧让缘——
    注册的令牌是使用的令牌）：≥900px 块内消费，非死档。"""

    screens = _text("webui/screens.css")
    desktop = screens[screens.index("@media (min-width: 900px) {"):]
    desktop = desktop[: desktop.index("@media (min-width: 1280px) {")]
    assert "var(--dock-compose-inset)" in desktop


def test_state_layer_covers_the_trigger_family() -> None:
    """触感层第七族：触发条 ::after 三臂在库（press/focus 臂在包裹外、
    hover 臂在 hover 半区内——screens.css 零 hover 的纪律不破）。"""

    css = _text("webui/components.css")
    assert ".dock-trigger::after {" in css
    assert ".dock-trigger:active::after { opacity: var(--state-press); }" \
        in css
    assert ".dock-trigger:focus-visible::after" in css
    assert ".dock-trigger:hover::after { opacity: var(--state-hover); }" \
        in css
    screens = _text("webui/screens.css")
    assert ":hover" not in screens


def test_touch_sheet_enters_from_above_the_edge() -> None:
    """O2 定谳修（活体实测驱动）：触屏 sheet 入场方向原语 =
    paper-drop-down（从上方 8px 落到底缘——paper-drop 的 +8px 起步让
    sheet 连底部垫层在入场 320ms 内沉到缘下，报告 §2 读数的根因）；
    新原语入册（keyframes 在库 + spec ⑨-5 名册八枚）。"""

    css = _text("webui/components.css")
    assert "@keyframes paper-drop-down {" in css
    assert "from { transform: translateY(-8px); }" in css
    screens = _text("webui/screens.css")
    touch = screens[screens.index("@media (hover: none) {"):]
    touch = touch[: touch.index(".envsel { top: auto;")]
    assert "animation: paper-drop-down var(--dur-settle)" in touch
    spec = (REPO / "docs" / "FRONTEND_SPEC.md").read_text(encoding="utf-8")
    assert "全库八枚" in spec
    assert "paper-drop-down" in spec


def test_served_page_carries_the_two_faces(tmp_path: Path) -> None:
    """活体半区（真 HTTP 面）：触发条与写作面同页在册、navdock 三签
    带图标插槽、旧常驻全形退役（页面上不再有裸 rows=2 直挂 form 的
    旧形态）。"""

    page = _page_of(tmp_path)
    assert 'id="dock-trigger"' in page
    assert 'id="compose-face"' in page
    assert 'data-icon="desk"' in page
    assert 'data-icon="revisit"' in page
    assert 'data-icon="drawer"' in page
    assert 'aria-controls="compose-face"' in page
