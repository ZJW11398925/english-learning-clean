"""v3-2 — the container & hierarchy recast cut（容器与层级重铸刀），pinned.

施工面 = docs/FRONTEND_SPEC.md ⑩ 层级宪法（新节）+ 8.2.2a 三块重铸
（翻看 = 容器升级为全览窗口 / 起笔·编辑 = 容器向下延展 / 移动端沓
bottom sheet）+ P1-1 底坞遮挡全局清 + P1-4 编辑器三出口一致化 +
⑨-5 注册表两行（容器延展 / 起笔让位案头；editor-zoom 对枚退役）。
用户两项核心误读纠正（本刀的存在理由，原话在案）：
1. 「直接起草编辑时，面板应当自动向下延伸拉开，是整个容器的变化，
   而不是多一个滚动条」；
2. 「信封应当可以翻看……而是整个角色卡的下拉窗口页面的完全升级」。

钉组（12 例）：
1. **the layer constitution** — spec ⑩ 在册 + z 序表与实现对账
   （四类层 / 互斥 / Esc 退栈条款）；
2. **the z-order table** — css 现值逐格对表（词卡 9 / 遮罩 8 /
   容器 7（触屏 sheet 9）/ 垫板 8 / navdock 6）；
3. **the mutual exclusion wiring** — 进空间收一切浮层与容器、开容器
   关浮层、浮层唯一；
4. **the esc ladder** — 容器阶梯（editor/window → deck → 收沓）+
   全页层（档案/信档 → 案头、观察 → 温故·档案）+ 浮层让路；
5. **the container extend** — extendContainer 的量高→落差→height
   过渡编排（custom props 只在 components.js 落）+ .envsel--grow 类
   与 height: var(--panel-h) 的 auto 回退；
6. **the editor lives in the pad** — 编辑面在容器内、开台先装表单再
   延展、独立全页编辑台与 zoom 对枚退役（负控）；
7. **the window is the container upgraded** — 全览窗口 = 容器升级态
   （同一批 DOM 子节点 hidden 翻转，零子页面）+ 滚底升级 + 静默链
   两态 + 翻看/回沓旧模式退役（负控）；
8. **the scroll tails carry the clearance**（P1-1）— .flow /
   .spacebody 的尾距账 = --navdock-clearance + 呼吸；
9. **the mobile deck is a bottom sheet**（P1-5）— hover:none 档贴底
   sheet + 遮罩 + 安全区 + 圆角/阴影/断点三 census 不动；
10. **the three editor exits speak with one voice**（P1-4）— Esc /
    「← 回沓」/「不改了」全部回沓、浏览上下文保留；
11. **reduced-motion 直切**与 **P1-2 四查登记**（词卡链完整、
    miss×覆盖率根因、不硬修裁量）。

预算刀内义务：新钉 12–25 例（本文件 12 例）。
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


def _spec() -> str:
    return (REPO_ROOT / "docs" / "FRONTEND_SPEC.md").read_text(
        encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 — the layer constitution (⑩)
# ---------------------------------------------------------------------------


def test_the_layer_constitution_is_registered_in_the_spec() -> None:
    """⑩ 在册：四类层（内联件/浮层/下拉容器/全页）、互斥规则三条、
    Esc 逐层退栈、容器延展档；两项用户原话定向由「下拉容器」类型承
    载（容器延展、容器升级），并以负句写明禁子页面/禁新增页面级滚动
    条。"""

    spec = _spec()
    assert "## ⑩ 层级宪法" in spec
    for clause in (
        "**内联件**",
        "**浮层**",
        "**下拉容器**",
        "**全页**",
        "**同屏至多一个浮层**",
        "**开下拉容器自动关浮层**",
        "**进任何空间收一切浮层与下拉**",
        "Esc 永远只退**一层**",
    ):
        assert clause in spec, clause
    assert "零子页面、零新增页面级滚动条" in spec
    # the two user directives name the recast (the cut's reason to be)
    assert "整个容器的变化" in spec
    assert "完全升级" in spec
    # the navigation model carries the same law (8.1.3)
    assert "**Esc 逐层退栈（v3-2，⑩ 层级宪法的统一关闭语义）**" in spec


def test_the_z_order_table_matches_the_css_values() -> None:
    """z 序表逐格对账（⑩ 10.2）：词卡 9 / 词卡遮罩 8 / 容器 7（触屏
    sheet 半区升 9）/ 垫板 8 / navdock 6 / 顶栏 5——表值与 css 现值
    一致，改动须同刀改表。"""

    spec = _spec()
    assert "| 浮层卡 | 9 |" in spec
    assert "| 遮罩 | 8 |" in spec
    assert "| 下拉容器（桌面档） | 7 |" in spec
    assert "| 写信区垫板 | 8 |" in spec
    assert "| 常驻 dock | 6 |" in spec
    components = _text("components.css")
    screens = _text("screens.css")
    assert ".word-card { position: absolute; z-index: 9;" in components
    assert ".word-scrim { display: none; position: fixed; inset: 0;" \
        " z-index: 8;" in components
    assert ".envsel { position: fixed; top: calc(var(--sp-8)" \
        " + var(--sp-1));\n          left: 0; right: 0; z-index: 7;" \
        in screens
    assert ".dock { position: fixed; left: 0; right: 0;\n" \
        "        bottom: var(--navdock-h); z-index: 8;" in screens
    assert ".navdock { position: fixed; left: 0; right: 0; bottom: 0;" \
        " z-index: 6;" in components
    assert ".top { position: sticky; top: 0; z-index: 5;" in screens
    # the touch tier lifts the sheet above the composer pad (z 9)
    hover = screens[screens.index("@media (hover: none) {", ):]
    assert ".envsel { top: auto; bottom: 0; z-index: 9;" in hover
    # and the mobile scrim sits at 8 (below the sheet, above the pad)
    assert ".envsel-scrim { display: none; position: fixed; inset: 0;" \
        " z-index: 8;" in screens


# ---------------------------------------------------------------------------
# 2 — the mutual exclusion + esc ladder wiring
# ---------------------------------------------------------------------------


def test_the_mutual_exclusion_wiring_is_pinned() -> None:
    """互斥三半（⑩ 10.3）：进空间收一切（showSpace 先收词卡与沓）、
    开容器关浮层（openEnvelopeSelector 先 closeWordCard）、浮层唯一
    （showWordCard 开新先收旧——既有语义的钉面化）。"""

    app = _text("app.js")
    js = _text("components.js")
    assert "function showSpace(name) {" in app
    body = app[app.index("function showSpace(name) {"):]
    body = body[: body.index("for (const key of Object.keys(spaces))")]
    assert "closeWordCard();" in body
    assert "closeEnvelopeSelector();" in body
    open_body = app[app.index("async function openEnvelopeSelector() {"):]
    open_body = open_body[: open_body.index("const panel =")]
    assert "closeWordCard();" in open_body
    # one floating layer at a time: opening closes the previous first
    assert "export function showWordCard(at, data) {\n  closeWordCard();" \
        in js


def test_the_esc_ladder_steps_one_layer_at_a_time() -> None:
    """Esc 退栈（⑩ 10.4；v3-2R 随迁）：容器阶梯 = 浮层让路
    （wordCardOpen 裁决，同一拍只退一层）→ 编辑面/全览窗口/写信工
    作区退一层回扇叠（`!== "deck"` 一式三面——第四形态不加新分支）
    → 扇叠收沓；全页层 = 档案/信档 Esc 回案头、观察 Esc 回温故·档
    案（与各自返回钮同效）。级联关闭（一拍退三层）永禁——阶梯体
    里没有第二处收沓调用。"""

    app = _text("app.js")
    ladder = app[app.index("function envselEsc(event) {"):]
    ladder = ladder[: ladder.index("\n}", ladder.index("closeEnvelopeSelector();"))]
    assert 'if (event.key !== "Escape") return;' in ladder
    assert "if (wordCardOpen()) return;" in ladder
    assert 'if (envselFace !== "deck") {' in ladder
    assert 'setEnvelopeFace("deck");' in ladder
    assert ladder.count("closeEnvelopeSelector();") == 1
    # the full pages: Esc returns to the entry, same as the back buttons
    assert "document.addEventListener(\"keydown\", (event) => {" in app
    full = app[app.index("if (event.key !== \"Escape\") return;\n  const current"):]
    full = full[: full.index("});")]
    assert 'if (current === "partner" || current === "letters") {' in full
    assert 'showSpace("parlor");' in full
    assert 'else if (current === "obs") {' in full
    assert 'showSection("study", "progress");' in full
    # the single-source guard: wordCardOpen reads components.js's own
    # openCard — no state copy in app.js
    js = _text("components.js")
    assert "export function wordCardOpen() {" in js
    assert "return openCard !== null;" in js


# ---------------------------------------------------------------------------
# 3 — the container extend (face 2: 起笔/编辑 = 容器向下延展)
# ---------------------------------------------------------------------------


def test_the_container_extend_is_a_height_transition() -> None:
    """容器延展档（⑩ 10.5）：extendContainer = 换装前后量高 →
    --panel-h custom prop 落差 → height 一次过渡（--dur-settle 大件
    档 × --ease-paper）→ transitionend 摘 prop 回 auto；动画期
    overflow hidden（纸的拉开感）；reduced-motion 直切 + 480ms 保险
    丝。custom props 只在 components.js 落（app.js 禁 .style 的同一
    规矩——负控：app.js 不落 --panel-h）。"""

    js = _text("components.js")
    assert "export function extendContainer(panel, mutate) {" in js
    body = js[js.index("export function extendContainer(panel, mutate) {"):]
    body = body[: body.index("\nexport function", 1)]
    assert "if (REDUCED_MOTION.matches) {" in body
    assert "const from = panel.offsetHeight;" in body
    assert "mutate();" in body
    assert "const to = panel.offsetHeight;" in body
    assert 'panel.style.setProperty("--panel-h", from + "px");' in body
    assert 'panel.classList.add("envsel--grow");' in body
    assert 'panel.style.setProperty("--panel-h", to + "px");' in body
    assert 'if (event && event.propertyName !== "height") return;' in body
    assert 'panel.style.removeProperty("--panel-h");' in body
    assert "setTimeout(done, 480);" in body   # 保险丝
    app = _text("app.js")
    assert '"--panel-h"' not in app           # app.js 禁 .style：只经工厂
    screens = _text("screens.css")
    assert "height: var(--panel-h);" in screens   # prop 缺省 = auto
    grow = _block(screens, ".envsel--grow {")
    assert "transition: height var(--dur-settle) var(--ease-paper);" \
        in grow
    assert "overflow: hidden;" in grow


def test_the_editor_face_lives_in_the_pad_container() -> None:
    """编辑面在容器内（face 2 编辑半）：.envsel-editor 是容器的子节
    点（openEnvelopeSelector 装配），开台 = 先装表单再延展（容器带
    着实际高度一次拉开，两段跳变不发生）；编辑面是唯一滚动井
    （overflow-y auto + overscroll contain + sticky 回沓行）；v2-2 的
    独立全页编辑台随容器化退役（负控：char-editor 类与 zoom 对枚
    全库缺位）。"""

    app = _text("app.js")
    screens = _text("screens.css")
    assert 'editorFace.className = "envsel-editor";' in app
    assert 'editorFace.hidden = true;' in app
    # one continuous pull: the form is built first, the face switch
    # comes after (extendContainer measures the real height)
    create_arm = app[app.index("if (mode === \"create\") {\n"
                               "    buildEditorForm(form,"):]
    create_arm = create_arm[: create_arm.index("}\n  form.appendChild")]
    assert 'setEnvelopeFace("editor");' in create_arm
    # the only scroll well: the editor face scrolls itself
    editor = _block(screens, ".envsel-editor {")
    assert "overflow-y: auto; overscroll-behavior: contain;" in editor
    assert "min-height: 0;" in editor
    back = _block(screens, ".editor-back {")
    assert "position: sticky; top: 0; z-index: 2;" in back
    # the retired standalone form is gone at the root
    whole = _page()
    assert "char-editor" not in whole
    assert "editor-zoom" not in whole
    assert "placeEditorOrigin" not in whole
    # the editor widens to the measure in the 481+ tier (nine faces
    # do not squeeze into the 420px deck)
    tablet = screens[screen_index_481(screens):]
    tablet = tablet[: tablet.index("@media (min-width: 900px) {")]
    assert ".envsel--editor { max-width: var(--measure); }" in tablet


def screen_index_481(screens: str) -> int:
    return screens.index("@media (min-width: 481px) {")


# ---------------------------------------------------------------------------
# 4 — the window is the container upgraded (face 3: 翻看)
# ---------------------------------------------------------------------------


def test_the_window_is_the_container_upgraded_not_a_subpage() -> None:
    """全览窗口 = 容器升级态（face 3，用户原话「整个角色卡的下拉窗口
    页面的完全升级」）：.envsel-browser 是容器的子节点（同一批 DOM
    子节点 hidden 翻转 + 容器高度延展——setEnvelopeFace 经
    extendContainer），**零子页面**；升级入口（v3-2R 随迁）= 点沓本
    体与滚到沓底再往下滚（触屏主入口，一次守卫）+「翻开全沓 ↓/
    回扇叠 ↑」静默链两态（触屏辅入口，桌面档不显示）；v2-2 的
    「翻看/回沓一钮两态 + 子页面层」模式退役（负控）；零跳变次序
    （内容先装满 → 再量高 → 一次拉开）由 v3-2r 套件钉住。"""

    app = _text("app.js")
    screens = _text("screens.css")
    assert 'browser.className = "envsel-browser";' in app
    assert "function setEnvelopeFace(face)" in app
    body = app[app.index("function setEnvelopeFace(face)"):]
    body = body[: body.index("\n}", body.index("extendContainer(panel,"))]
    # one container, three faces, swapped in place — no subpage swap
    assert "extendContainer(panel, () => {" in body
    assert 'stack.hidden = face !== "deck";' in body
    assert 'browser.hidden = face !== "window";' in body
    assert 'editorFace.hidden = face !== "editor";' in body
    assert 'face === "window" ? "回扇叠 ↑" : "翻开全沓 ↓";' in body
    # the scroll-to-end upgrade with its reset-on-return re-arm
    assert "stack.addEventListener(\"scroll\", () => {" in app
    scroll_arm = app[app.index("stack.addEventListener(\"scroll\", () => {"):]
    scroll_arm = scroll_arm[: scroll_arm.index("});")]
    assert 'if (envselFace !== "deck") return;' in scroll_arm
    assert "stack.scrollTop + stack.clientHeight >=" in scroll_arm
    assert 'setEnvelopeFace("window");' in scroll_arm
    assert "if (face === \"deck\") {\n    stack.scrollTop = 0;" in app
    # the retired pattern: the 翻看/回沓 two-state button pair is gone
    assert '"翻看"' not in app
    assert '"回沓"' not in app
    # the window rides inside the pad (the container section pins it)
    browser = _block(screens, ".envsel-browser {")
    assert "position: relative;" in browser   # 容器内文档流，非浮层


# ---------------------------------------------------------------------------
# 5 — the scroll tails carry the clearance (face 4: P1-1)
# ---------------------------------------------------------------------------


def test_the_scroll_tails_carry_the_navdock_clearance() -> None:
    """P1-1 底坞遮挡全局清：一切滚动容器的尾距账 = 固定底具的真实高
    度——.flow（navdock + 安全区 + 写信区自身高度带 256）与 .spacebody
    （navdock + 安全区 + 一档呼吸 --sp-6）都以 --navdock-clearance 为
    底（令牌出处 tokens.css，零第三处手写 54px）。三处点名（教学卡
    「寄出回应」/ 温故·档案末行 / 案头「翻看以前的信 →」）都在这两
    个滚动容器的尾距账内。"""

    tokens = _text("tokens.css")
    assert ("--navdock-clearance: calc(var(--navdock-h)"
            " + var(--safe-bottom));" in tokens)
    screens = _text("screens.css")
    flow = _block(screens, ".flow {")
    # v3-a 随迁：手写 256px 余量退役（D-B 笔搁触发条账——navdock +
    # 安全区 + 触发条 + 一档呼吸，O7 死区清账）
    assert ("calc(var(--navdock-clearance) + var(--dock-trigger-h)"
            in flow)
    space = _block(screens, ".spacebody {")
    assert "calc(var(--navdock-clearance) + var(--sp-6));" in space
    # the magic numbers are retired (negative)
    whole = _page()
    assert "310px" not in whole
    # the body's own padding keeps the original law (r1_shell 的既有钉
    # 同源，此处对账；html, body 复合选择器不算——取独立 body 块)
    body = _block(screens, "\nbody {")
    assert "padding-bottom: calc(var(--navdock-h) + var(--safe-bottom));" \
        in body


# ---------------------------------------------------------------------------
# 6 — the mobile deck is a bottom sheet (face 5: P1-5)
# ---------------------------------------------------------------------------


def test_the_mobile_deck_is_a_bottom_sheet() -> None:
    """P1-5 移动端沓：触屏档（hover:none 输入形态查询——与词卡 sheet
    同法的分档纪律，四档断点契约零新增边界）整沓贴底 bottom sheet：
    全宽（left/right 0 + max-width none）、贴底（top auto bottom 0）、
    安全区垫层、上缘发丝线沿容器基形（顶缘 ≤2px，不另发覆盖声明）、
    z 9 盖过写信区垫板；遮罩 = --ink 0.4（禁毛玻璃），点遮罩 = 点容
    器外（同一 envselCloser 机制）；圆角/阴影/断点三 census 不动。"""

    screens = _text("screens.css")
    at = screens.index("@media (hover: none) {", )
    tier = screens[at:]
    assert ".envsel { top: auto; bottom: 0; z-index: 9;" in tier
    assert "max-width: none; left: 0; right: 0;" in tier
    assert "padding-bottom: calc(var(--sp-2) + var(--safe-bottom));" \
        in tier
    assert ".envsel-scrim { display: block;" in tier
    scrim = _block(screens, ".envsel-scrim {")
    assert "background: var(--ink); opacity: 0.4;" in scrim
    whole = _page()
    assert "backdrop-filter" not in whole           # 禁毛玻璃
    # the four-tier breakpoint contract stands untouched: three
    # min-width boundaries, each exactly once, in screens.css
    for boundary in ("481px", "900px", "1280px"):
        assert screens.count(f"@media (min-width: {boundary}) {{") == 1
    # the radius/shadow censuses ride the same values as v22r/mc1
    assert screens.count("border-radius") == 4
    assert screens.count("box-shadow") == 4
    # the scrim is appended and removed with the container (one click-
    # outside mechanism)
    app = _text("app.js")
    assert 'scrim.className = "envsel-scrim";' in app
    assert 'document.querySelector(".envsel-scrim");' in app
    assert "if (scrim) scrim.remove();" in app


# ---------------------------------------------------------------------------
# 7 — the three editor exits speak with one voice (face 6: P1-4)
# ---------------------------------------------------------------------------


def test_the_three_editor_exits_speak_with_one_voice() -> None:
    """P1-4 出口一致化：Esc（容器阶梯的第一层）/「← 回沓」/「不改了」
    语义统一 = 全部回沓（closeCharacterEditor → setEnvelopeFace
    ("deck")，浏览上下文 envselPreviewId 不动）；存/删成功同走此门
    （after 半区在回沓后跑沓重排）。按钮与 Esc 同效的钉面。"""

    app = _text("app.js")
    assert "function closeCharacterEditor(after)" in app
    body = app[app.index("function closeCharacterEditor(after)"):]
    body = body[: body.index("\n}", body.index("setEnvelopeFace(\"deck\");"))]
    assert 'if (!envselPanel || envselFace !== "editor") return;' in body
    assert 'setEnvelopeFace("deck");' in body
    # the preview context survives the return (保留浏览上下文)
    assert "envselPreviewId = null;" not in body
    # the two buttons ride the same closer
    assert 'backBtn.addEventListener("click", () => closeCharacterEditor());' \
        in app
    assert 'cancel.addEventListener("click", () => closeCharacterEditor());' \
        in app
    # and the Esc ladder routes the editor face to the same function
    # family (envselEsc steps the face back to the deck)
    ladder = app[app.index("function envselEsc(event) {"):]
    assert 'setEnvelopeFace("deck");' in ladder[:ladder.index("\n}")]


# ---------------------------------------------------------------------------
# 8 — reduced motion + the P1-2 registration
# ---------------------------------------------------------------------------


def test_the_extend_cuts_straight_on_reduced_motion() -> None:
    """reduced-motion 双面：extendContainer 的 JS 半区直切（REDUCED_
    MOTION 单一归宿——matchMedia 字面不进 app.js）+ 库尾总降级块（
    0.01ms 即终，transitionend 照发——摘 prop 的清理不失效）。"""

    js = _text("components.js")
    body = js[js.index("export function extendContainer(panel, mutate) {"):]
    body = body[: body.index("\nexport function", 1)]
    assert "if (REDUCED_MOTION.matches) {\n    mutate();" in body
    app = _text("app.js")
    assert "prefers-reduced-motion" not in app   # matchMedia 字面不进 app.js
    css = _text("components.css")
    assert "@media (prefers-reduced-motion: reduce) {" in css
    assert "transition-duration: 0.01ms !important;" in css


def test_the_word_card_four_check_is_registered_in_the_spec() -> None:
    """P1-2 四查登记（⑩ 10.6）：活体取证结论在册——事件链完整（双档
    真击开卡）、根因 = 词表覆盖率 × miss 静默契约、不硬修的裁量与
    Revisit 归属（v3-3）。登记数字 = 实测读数（36 去重词 1 命中）。"""

    spec = _spec()
    assert "**P1-2「词卡全端不可达」四查结论" in spec
    assert "活体取证（真浏览器双档" in spec
    assert "36 个去重词仅 1 个命中词表" in spec
    assert "登记 v3-3" in spec
