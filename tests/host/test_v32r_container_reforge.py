"""v3-2R — the container reforge redo cut（容器重铸重做刀），pinned.

施工面 = 两项核心的零裁量重铸 + 三条硬伤收编（授权：用户判词「必须
实现我说的效果，只高不低」+ DEC-OPI-5033857a-…7 零裁量纪律）：

1. **起笔 = 容器向下延展【成为写信工作界面】**——用户原话「直接起草
   编辑时，面板应当自动向下延伸拉开，是整个容器的变化，而不是多一
   个滚动条」。上一刀的降级实现（起笔 = 建卡表单 + 收沓回案头）被
   判词整刀否定；新建角色的表单归「完整编辑」，不占「起笔」语义。
2. **翻看 = 角色卡整体展开为下拉大窗口，过渡全程零跳变**——内容先
   装满 → 再量高 → 一次拉开（上一刀量高在内容填入前，「长到一半 →
   跳到全高」的 snap 伪影除名）；主入口 = 点沓本体与滚到底，「翻开
   全沓 ↓」文字链只作触屏辅入口。
3. 三条硬伤：A 沓开时底坞淡化置灰且明确不可点（视觉可点性 = 实际
   可点性）；B 触屏档沓改单卡纵排（390px 可读性）；C 起笔延展落定
   后笔尖聚焦（视口跟随）。

钉组（13 例）：
1. the compose face is a container face — 第四形态在态机与 DOM 在册；
2. the compose face carries the full letter flow — 收件人/稿纸/寄出；
3. the compose send walks the real pipeline — 同一 sending/postTurn/
   回执一拍/收拢守卫；
4. the compose entry switches first — 每封动作 + 选定角色先切换 +
   窗口同入口；
5. no low-config — 建卡表单形态不占起笔入口（负控钉）；
6. fill → measure → transition — 翻看零跳变次序钉（含 from/to 次序）；
7. the pad body is the main entry — 点沓本体 + 文字链触屏辅入口；
8. the navdock stills — 硬伤 A（开沓置灰/收沓即解/disabled 形态复用）；
9. the touch deck is single-column — 硬伤 B（单卡纵排 + 邮票不压简介）；
10. the viewport follows — 硬伤 C（延展落定聚焦 + 视口守卫）；
11. the esc ladder covers compose — 单层退栈不破坏；
12. the spec carries the v3-2R truth — 8.2.2a/⑨-5/⑩ 回填对账；
13. the design language census stands — 动效/圆角/阴影/色值四 census
    与 reduced-motion 纪律不降级。
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


def _fn(source: str, head: str) -> str:
    """One function's own slice (head → the next top-level ``}``)."""

    at = source.index(head)
    return source[at:source.index("\n}", at)]


# ---------------------------------------------------------------------------
# 1 — the compose face is a container face (核心一：态机第四形态)
# ---------------------------------------------------------------------------


def test_the_compose_face_is_a_container_face() -> None:
    """写信工作区 = 沓容器的第四形态（⑩ 10.1）：.envsel-compose 由
    openEnvelopeSelector 装配为容器子节点（初始 hidden——同一批 DOM
    子节点 hidden 翻转，零子页面零新页面切换）；setEnvelopeFace 的
    合法面含 "compose"；换装臂的 hidden 翻转、静默链让位（编辑/写信
    两态都有各自回沓行）、容器类切换三处点名 compose。"""

    app = _text("app.js")
    assert 'composeFace.className = "envsel-compose";' in app
    assert "composeFace.hidden = true;" in app
    assert "panel.appendChild(composeFace);" in app
    assert "async function setEnvelopeFace(face) {" in app
    machine = _fn(app, "async function setEnvelopeFace(face) {")
    assert 'face !== "compose") return;' in machine
    assert 'composeFace.hidden = face !== "compose";' in machine
    assert 'browse.hidden = face === "editor" || face === "compose";' \
        in machine
    assert 'panel.classList.toggle("envsel--compose", face === "compose");' \
        in machine
    # the face rides the container extension like its siblings (⑩ 10.5)
    assert "extendContainer(panel, () => {" in machine
    screens = _text("screens.css")
    face = _block(screens, ".envsel-compose {")
    assert "overflow-y: auto; overscroll-behavior: contain;" in face
    assert "max-width: var(--measure);" in face
    assert "flex: 1;" in face
    # 占据主屏（起笔原义；延展必须长开）：面 min-height 与容器上限同
    # 式再让一档铬件账——且落在**面**上（落容器会把 --panel-h 过渡夹
    # 成直跳）；触屏档 sheet 同式
    assert "min-height: calc(100dvh - var(--sp-8) - var(--sp-6)" in face
    assert "- var(--sp-8) - var(--sp-1));" in face
    tier = screens[screens.index("@media (hover: none) {"):]
    assert ".envsel-compose { min-height: calc(100dvh - var(--sp-8)" in tier
    assert ".envsel--compose { min-height" not in screens
    # the workspace widens to the measure in the 481+ tier (editor 同例)
    tablet = screens[screens.index("@media (min-width: 481px) {"):]
    tablet = tablet[: tablet.index("@media (min-width: 900px) {")]
    assert ".envsel--compose { max-width: var(--measure); }" in tablet


def test_the_compose_face_carries_the_full_letter_flow() -> None:
    """工作区内完成「写一封信并寄出」全流程（任务书逐件）：收件人 =
    角色名与一句身份（复用信封面的 env-to-word 致 / env-name /
    env-line——**只读** textContent，建卡表单形态禁入）；多行写信输
    入 = .pen compose-pen（稿纸家族，三行起笔 3×--baseline，占位句
    在场）；寄出动作 = btn--send「寄出 →」；手感与案头同一（Enter
    寄出 / Shift+Enter 换行）；回沓与「先搁着」同门（容器退一层）。"""

    app = _text("app.js")
    face = _fn(app, "function buildComposeFace(item) {")
    # the recipient: name + one-line identity, inert text, never a form
    assert 'toWord.textContent = "致";' in face
    assert 'name.className = "env-name";' in face
    assert 'name.textContent = String(item.name || "");' in face
    assert 'line.className = "env-line compose-line";' in face
    assert 'line.textContent = String(item.identity_line || "");' in face
    # the multiline pen (the .pen family — the parlor's own paper)
    assert 'pen.className = "pen compose-pen";' in face
    assert "pen.maxLength = 2000;" in face
    assert 'pen.placeholder = "今日如何？想从哪句起，就从哪句起。";' in face
    # the send action + the two retreat doors
    assert 'send.className = "btn btn--send";' in face
    assert 'send.textContent = "寄出 →";' in face
    assert 'shelve.textContent = "先搁着";' in face
    assert 'backBtn.textContent = "← 回沓";' in face
    assert face.count('setEnvelopeFace("deck")') == 2
    # the parlor's own touch: Enter posts, Shift+Enter breaks the line
    assert 'pen.addEventListener("keydown", (event) => {\n' \
        '    if (event.key === "Enter" && !event.shiftKey) {' in face
    # the honest refusal lines (empty letter / one letter en route)
    assert "空白的信寄不出去——写一句再寄。" in face
    assert "上一封还在路上——落地了再寄。" in face
    # 容器内动作件一律 stopPropagation（沓家同例——回执换装会把事件
    # 目标摘出 DOM，冒泡到 document 时 envselCloser 的 contains 判定
    # 反咬；根因钉：三颗钮缺一颗即倒回「寄出即被点外关闭」）
    assert face.count("event.stopPropagation();") == 3
    screens = _text("screens.css")
    pen = _block(screens, ".compose-pen {")
    # v3-2R 处置刀随迁（复测可6）：5→10 行且不吃家族 160 上限
    assert "min-height: calc(var(--baseline) * 10);" in pen
    assert "max-height: none;" in pen
    actions = _block(screens, ".compose-actions {")
    assert "display: flex; justify-content: space-between;" in actions


def test_the_compose_send_walks_the_real_pipeline() -> None:
    """寄出 = 信落案头信流（postTurn 同一发送管线——在途信封与「寄出」
    邮戳是它的事，写信工作区不造第二发送路径）；在途守卫与案头同一枚
    sending；盖印 = 同一枚 stamp-press（animationend 自摘）；回执 =
    sysline 读法的一拍人话（邮戳留在案头那封上——同屏 ≤1 枚不在
    容器里再盖）；收拢 = 回执一拍后 closeEnvelopeSelector（envsel--
    fold 与延展同曲线反向），人已 Esc/先搁着回沓即不追着关（收拢守
    卫）；reduced-motion 回执零拍直落。"""

    app = _text("app.js")
    face = _fn(app, "function buildComposeFace(item) {")
    assert "if (sending) {" in face           # 在途只此一封（与案头同一枚）
    assert 'send.classList.add("stamp-press");' in face
    assert "() => send.classList.remove(\"stamp-press\"), { once: true });" \
        in face
    assert "postTurn(text).finally(() => {" in face
    assert "sending = false;" in face
    # the receipt: one human beat, then the fold — never a second stamp
    assert 'receipt.className = "sysline compose-receipt";' in face
    assert "寄出了——回信落在案头的信流里。" in face
    assert "postmark" not in face
    assert "const beat = REDUCED_MOTION.matches ? 0 : 1000;" in face
    assert 'if (envselPanel && envselFace === "compose") {\n' \
        "        closeEnvelopeSelector();" in face
    # the receipt modifier rides the sysline family (components.css 同例)
    components = _text("components.css")
    assert ".sysline.compose-receipt {" in components


def test_the_compose_entry_switches_first_when_needed() -> None:
    """起笔入口 = 每封动作行的第一词（components.js 工厂，--pencil
    形）；app.js 装配把 onCompose 接到 startComposing；选定角色 ≠ 当前
    通信时**先切换再延展**（既有确认与失败姿态原样），沓缓存的
    current 同步改真（Esc 回沓再点起笔不重复切换）；全览窗口的页卡
    同词同路（窗口里也能直接落笔）；容器没开就不起笔。"""

    js = _text("components.js")
    assert 'act("起笔", "env-act-compose", () => {\n' \
        "    if (typeof options.onCompose === \"function\")" \
        " options.onCompose();\n  });" in js
    app = _text("app.js")
    assert "onCompose: () =>\n        startComposing(item)," in app
    entry = _fn(app, "async function startComposing(item) {")
    assert "if (!envselPanel) return;" in entry
    assert "const done = await switchToCharacter(item.character_id);" \
        in entry
    assert "if (!done || !envselPanel) return;" in entry
    assert "charactersCache.current_character_id = item.character_id;" \
        in entry
    assert "buildComposeFace(item);" in entry
    assert 'setEnvelopeFace("compose");' in entry
    # 切换在建面之前（先切后展的次序钉——extendContainer 量的是工作区
    # 实高，不是切换前通信的残影）
    assert entry.index("await switchToCharacter") < \
        entry.index("buildComposeFace(item);")
    # the window's page card speaks the same word
    assert 'act("起笔", () => {\n    startComposing(item);' in app


# ---------------------------------------------------------------------------
# 2 — no low-config（零低配负控：建卡表单形态不占起笔入口）
# ---------------------------------------------------------------------------


def test_no_low_config_the_create_form_never_occupies_compose() -> None:
    """② 零低配（负控钉）：上一刀「起笔 = 建卡表单 + 收沓回案头」的
    降级形态整件退役——buildCreateForm / .env-create / .env-err /
    空白封的「起笔」钮与「开笔 / 先不起」文案全库缺位；空白封只剩
    「完整编辑」（建卡归编辑台，名字必填在编辑面）；写信工作区切片
    内零建卡写面（fetchCreateCharacter 不进 buildComposeFace——它的
    唯一消费面是编辑台）。"""

    whole = _page()
    assert "buildCreateForm" not in whole
    assert "env-create" not in whole
    assert "env-err" not in whole
    assert 'start.textContent = "起笔";' not in whole
    assert 'go.textContent = "开笔";' not in whole
    assert "先不起" not in whole
    assert "起个名字就能开笔" not in whole
    app = _text("app.js")
    face = _fn(app, "function buildComposeFace(item) {")
    assert "fetchCreateCharacter" not in face
    # the blank envelope keeps the one honest door (完整编辑) — and the
    # hint now points at it, then at 起笔 on the built card
    assert 'full.textContent = "完整编辑";' in app
    assert "名字加九面，点「完整编辑」一次写全——建好了，她就躺在沓里等你起笔。" \
        in app
    # the creation write face still has exactly one consumer (the editor)
    assert app.count("fetchCreateCharacter(fields)") == 1
    # the retired "起笔确认后收沓让位" rationale is out of the spec too
    # (spec 散文按 68 列换行——钉不跨折行的连续子串)
    spec = _spec()
    assert "新建角色的表单归「完整编" in spec
    assert "辑」（编辑台既有），不得占用「起笔」语义" in spec
    assert "起笔确认（新建" not in spec


# ---------------------------------------------------------------------------
# 3 — fill → measure → transition（翻看零跳变次序钉，含 from/to 次序）
# ---------------------------------------------------------------------------


def test_the_window_upgrade_fills_then_measures_then_transitions() -> None:
    """③ 翻看一次拉开零跳变（次序钉——上一刀 F-1 缺口）：窗口臂 =
    **内容先装满**（隐藏层里 await renderEnvelopePageInto，含异步卡
    面）→ **再量高**（extendContainer 的 from → mutate → to 发生在
    换装点）→ **一次拉开**；装满先于延展的次序钉（函数体内 index
    对账）；过渡中的二次点名由 envselFacePending 忽略；页卡渲染返回
    灌完的 Promise（翻页臂同法 await 再播 page-turn）；旧的面守卫
    （face !== "window" 早退——它正是「装满不能发生在隐藏层」的元
    凶）退役，代次守卫 page.dataset.fill 保证只有最新一次渲染落笔。"""

    app = _text("app.js")
    machine = _fn(app, "async function setEnvelopeFace(face) {")
    assert "if (envselFacePending) return;" in machine
    assert "envselFacePending = face;" in machine
    assert "if (page) await renderEnvelopePageInto(page);" in machine
    assert machine.index("await renderEnvelopePageInto(page);") < \
        machine.index("extendContainer(panel, () => {")
    assert 'if (!envselPanel || envselPanel !== panel) return;' in machine
    render = _fn(app, "function renderEnvelopePageInto(page) {")
    assert "return envelopePageCard(item.character_id).then((data) => {" \
        in render
    assert "page.dataset.fill = fill;" in render
    assert "if (page.dataset.fill !== fill) return;" in render
    assert 'if (envselFace !== "window") return;' not in render
    # the page turn awaits the fill before the animation rides
    turn = _fn(app, "async function turnEnvelopePage(step) {")
    assert "await renderEnvelopePageInto(page);" in turn
    assert turn.index("await renderEnvelopePageInto(page);") < \
        turn.index("playPageTurn(page, step > 0);")
    # from → mutate → to：量高的两次读数夹着换装点（extendContainer
    # 自身的次序钉——连续三行缺一不可，缺一即倒回「先定高后填内容」；
    # 注意 reduced-motion 臂的 mutate() 先于主路径，故钉连续三行而非
    # 裸 index）
    js = _text("components.js")
    factory = _fn(js, "export function extendContainer(panel, mutate) {")
    assert "const from = panel.offsetHeight;\n  mutate();\n" \
        "  const to = panel.offsetHeight;" in factory


def test_the_pad_body_is_the_main_entry_and_the_link_is_touch_only() -> None:
    """翻看主入口 = 点沓本体与滚到底（任务书主入口定谳）：容器纸面
    （面板留白/沓叠背景——信封、动作行、底行各有己任）的点击升级成
    窗口；滚底升级臂原样保留；「翻开全沓 ↓」文字链只作触屏辅入口
    （JS 装配原样——桌面档 CSS display:none，hover:none 档现位），
    不得成为桌面的第一入口形态。"""

    app = _text("app.js")
    assert 'panel.addEventListener("click", (event) => {\n' \
        '    if (envselFace !== "deck") return;\n' \
        "    if (event.target !== panel && event.target !== stack) return;\n" \
        '    setEnvelopeFace("window");\n  });' in app
    # the scroll-to-bottom upgrade rides on (一次守卫，既有)
    assert 'stack.addEventListener("scroll", () => {' in app
    assert 'face === "window" ? "回扇叠 ↑" : "翻开全沓 ↓";' in app
    screens = _text("screens.css")
    assert ".env-browse { display: none; }" in screens
    tier = screens[screens.index("@media (hover: none) {"):]
    assert ".env-browse { display: inline; }" in tier


# ---------------------------------------------------------------------------
# 4 — the three hard wounds (A 底坞 / B 390px / C 视口)
# ---------------------------------------------------------------------------


def test_the_navdock_stills_while_the_pad_is_open() -> None:
    """硬伤 A（视觉可点性 = 实际可点性）：开沓 = 底坞各项落 disabled
    （既有 disabled 形态复用——opacity .4 + pointer-events 无，置灰
    即不可点，两义合一）；收沓即解（开关对称——开/收两处点名）；定
    谳与二选一理由在 ⑩ 10.3-5 在册。"""

    app = _text("app.js")
    assert "function setNavdockStilled(still) {" in app
    helper = _fn(app, "function setNavdockStilled(still) {")
    assert "item.disabled = still;" in helper
    opener = _fn(app, "async function openEnvelopeSelector() {")
    assert "setNavdockStilled(true);" in opener
    closer = _fn(app, "function closeEnvelopeSelector(opts) {")
    assert "setNavdockStilled(false);" in closer
    components = _text("components.css")
    assert ".navdock-item[disabled] { opacity: 0.4; pointer-events: none; }" \
        in components
    spec = _spec()
    assert "**开下拉容器时常驻 dock 静置**" in spec
    assert "视觉可点性与实际可点性必须一致" in spec


def test_the_touch_deck_is_a_single_column_of_full_cards() -> None:
    """硬伤 B（390px 沓叠态可读性）：触屏档（hover:none 输入形态查
    询——四档断点契约零新增边界）沓改**单卡纵排**——微扇让位
    （--env-fan 0）、每封在文档流独占一行（position 归位、top 归
    auto、flex 纵排 + 间隙）、完整保住头部；邮票不压简介（卡右垫
    --sp-8 = 64px ≥ 邮票 44 + 右缘 10 的占用）；简介整句可读（换行
    不省略）；沓自身仍滚（60dvh 上限），滚底升级照常。"""

    screens = _text("screens.css")
    tier = screens[screens.index("@media (hover: none) {"):]
    assert ".envsel-stack { --env-fan: 0; height: auto; max-height: 60dvh;" \
        in tier
    assert "display: flex; flex-direction: column;" in tier
    assert ".env { position: relative; left: 0; right: 0; top: auto;" in tier
    assert "flex: none;\n" in tier   # 纵排卡保自然高，超高由沓滚（不压扁）
    assert "min-height: 0; padding-right: var(--sp-8); }" in tier
    assert ".env--new { top: auto; }" in tier
    assert ".env-to { padding-right: 0; }" in tier
    assert ".env-line { white-space: normal; overflow: visible;" in tier
    assert "text-overflow: clip; }" in tier
    # the desktop deck (base tier) is untouched — the fan stack stands
    assert "top: calc(12px + var(--env-i, 0) * var(--env-step));" in screens
    # no new breakpoint boundary sneaks in with the fix
    for boundary in ("481px", "900px", "1280px"):
        assert screens.count(f"@media (min-width: {boundary}) {{") == 1


def test_the_viewport_follows_the_compose_workspace() -> None:
    """硬伤 C（视口跟随）：起笔延展落定（--dur-settle 320 + 余量 = 与
    回沓重排同款的 360 窗）后笔尖聚焦——焦点即跟随；容器本体在视口
    外（极端档）先把窗口滚到它；reduced-motion 直落（0ms）；跟随只
    在写信工作区态发（compose 臂点名），已收沓即弃权。"""

    app = _text("app.js")
    assert "function followComposeWorkspace(panel, face) {" in app
    follow = _fn(app, "function followComposeWorkspace(panel, face) {")
    assert "if (!envselPanel || envselPanel !== panel) return;" in follow
    assert "panel.getBoundingClientRect();" in follow
    assert "panel.scrollIntoView({ block: \"nearest\"," in follow
    assert 'if (pen) pen.focus();' in follow
    assert "setTimeout(run, 360);" in follow
    assert "REDUCED_MOTION.matches" in follow
    machine = _fn(app, "async function setEnvelopeFace(face) {")
    assert 'if (face === "compose") {\n' \
        "    followComposeWorkspace(panel, composeFace);" in machine


# ---------------------------------------------------------------------------
# 5 — the esc ladder stays single-step with the fourth face
# ---------------------------------------------------------------------------


def test_the_esc_ladder_covers_compose_and_stays_single_step() -> None:
    """⑤ 层级宪法（spec ⑩）与新形态一致 + Esc 退栈不破坏：写信工作
    区与编辑面/全览窗口同层退一层回扇叠（`envselFace !== "deck"` 一
    式三面——新形态不加新分支）；扇叠才收沓；级联关闭永禁（阶梯体
    里没有第二处收沓调用）；浮层让路裁决原样。"""

    app = _text("app.js")
    ladder = _fn(app, "function envselEsc(event) {")
    assert 'if (event.key !== "Escape") return;' in ladder
    assert "if (wordCardOpen()) return;" in ladder
    assert 'if (envselFace !== "deck") {\n    setEnvelopeFace("deck");\n' \
        "    return;\n  }" in ladder
    assert ladder.count("closeEnvelopeSelector();") == 1
    spec = _spec()
    assert "写信工作区 → 扇叠" in spec
    assert "写信工作区 compose" in spec


# ---------------------------------------------------------------------------
# 6 — the spec carries the v3-2R truth (回填对账)
# ---------------------------------------------------------------------------


def test_the_spec_carries_the_v32r_truth() -> None:
    """spec 回填（8.2.2a + ⑨-5 + ⑩）：起笔工作区节 = 用户原话 + 全
    流程四件（收件人/多行输入/寄出/回执与收拢）+ 三禁（建卡表单占
    起笔/新页面切换/容器外滚动区）；翻看节 = 零跳变次序句（内容先
    装满 → 再量高 → 一次拉开）+ 主入口定谳；⑨-5 容器延展行吃进写
    信工作区、起笔行重写为「起笔写信工作区」；⑩ 10.1 第四形态 /
    10.3-5 底坞静置 / 10.5 零跳变次序在册。"""

    spec = _spec()
    # 8.2.2a — the compose workspace bullet
    assert "【起笔 = 容器向下延展成为写信工作界面——现役（v3-2R 重铸；" \
        in spec
    assert "整个容器的变化" in spec
    assert "**收件人**" in spec
    assert "**多行写信输" in spec
    assert "**寄出后回执**" in spec
    assert "【禁】起笔 = 建卡表单 + 收沓回案头（上一刀形态，判词" in spec
    # 8.2.2a — the zero-jump window + the entry adjudication
    assert "**内容先装满**" in spec
    assert "长到一半→跳到全高" in spec
    assert "升级**主入口 = 点沓本体**" in spec
    assert "触屏辅入口" in spec
    # ⑨-5 — the two registry rows (表行是单行——次序句钉在这里不折行)
    assert "扇叠↔写信工作区（v3-2R 起笔重铸）" in spec
    assert "起笔写信工作区（现役——v3-2R 重铸" in spec
    assert "全览窗口升级 = 内容先装满 → 再量高 → 一次拉开（零跳变）" in spec
    # ⑩ — the constitution arms
    assert "写信工作区 compose（v3-2R 第四形态" in spec
    assert "**零跳变次序**（v3-2R 定谳" in spec
    assert "一律**内容先装满" in spec


# ---------------------------------------------------------------------------
# 7 — the design language census stands (零降级对账)
# ---------------------------------------------------------------------------


def test_the_design_language_census_stands() -> None:
    """v2 内核纪律不降级：动效注册表 census（v3-a 随迁 8→9：
    paper-drop-down 落底入册——O2 定谳修的新方向原语；**fr-B 随迁
    9→12：stagger-rise / scrim-out / sheet-out 三枚——动画体系专项
    刀 B 的错峰与词卡褪下原语，⑨-5 名册同刀改行「全库十二枚」**）；
    圆角
    census（screens 4 / components 9——v2-2 的 7 + fr-A 墨点两声明，
    全 ≤2px 信纸物件档 + 邮票邮戳圆形豁免 + fr-A 用户明示墨点豁免席）；
    阴影 census（screens 4 / components 8——fr-A 的 7 + fr-B #11 确认
    窗面板一座 deep，仍恰两级 --stack-shadow-* 之内、令牌引用零手写）；
    零毛玻璃；
    reduced-motion 字面不进 app.js（REDUCED_MOTION 单一归宿）；写
    信工作区样式块零色值字面（全 var()——v2 语言对账）。"""

    components = _text("components.css")
    screens = _text("screens.css")
    assert components.count("@keyframes ") == 12
    assert screens.count("border-radius") == 4
    assert components.count("border-radius") == 9
    assert screens.count("box-shadow") == 4
    assert components.count("box-shadow") == 8
    whole = _page()
    assert "backdrop-filter" not in whole
    app = _text("app.js")
    assert "prefers-reduced-motion" not in app
    import re as _re

    compose_css = screens[screens.index(".envsel-compose {"):]
    compose_css = compose_css[: compose_css.index("/* ── v2 动效基建")]
    assert _re.search(r"#[0-9a-fA-F]{3,8}\b", compose_css) is None
    assert "border-radius" not in compose_css
    assert "box-shadow" not in compose_css


def test_the_desk_dock_yields_while_the_container_is_open() -> None:
    """v3-2R 处置刀（复测坏1/差4，⑩ 10.3-5 扩面）：沓开着时案头
    写信区同步让路——否则其「寄出」浮在容器上（z8>z7），误触即容器
    关闭 + 草稿无声丢弃；新建表单「存」也被咬。开/收双点位对称。"""
    app = _text("app.js")
    assert "function setDockStilled(still)" in app
    assert 'dock.classList.toggle("dock--stilled", still)' in app
    # 开沓与收沓两处都必须带上 dock（与 navdock 同批对称）
    assert app.count("setDockStilled(true);") == 1
    assert app.count("setDockStilled(false);") == 1
    assert app.index("setNavdockStilled(true);") < \
        app.index("setDockStilled(true);")
    assert app.index("setNavdockStilled(false);") < \
        app.index("setDockStilled(false);")
    screens = _text("screens.css")
    rule = screens[screens.index(".dock.dock--stilled {"):]
    rule = rule[: rule.index("}")]
    assert "opacity: 0.4" in rule
    assert "pointer-events: none" in rule


def test_compose_drafts_survive_every_exit_except_sending() -> None:
    """v3-2R 处置刀（复测坏2/坏3，⑩ 10.3-6）：草稿按角色分桶，重开
    恢复；唯一清稿时机 = 寄出成功（postTurn 后 removeItem）——Esc/
    回沓/先搁着/点外一律保稿。"""
    app = _text("app.js")
    assert "function composeDraftKey(characterId)" in app
    assert 'return `compose-draft-${characterId}`;' in app
    # 恢复：buildComposeFace 里 pen 创建后读草稿
    assert 'sessionStorage.getItem(composeDraftKey(item.character_id))' in app
    # 存稿：input 事件
    assert 'sessionStorage.setItem(composeDraftKey(item.character_id)' in app
    # 清稿恰一处 = 寄出（postTurn 之后、回执之前）
    assert app.count("sessionStorage.removeItem(composeDraftKey") == 1
    assert app.index("postTurn(text)") < \
        app.index("sessionStorage.removeItem(composeDraftKey")


def test_the_compose_pen_grows_past_the_pen_family_cap() -> None:
    """v3-2R 处置刀（复测可6）：写信稿纸起步 10 行且不吃 .pen 家族
    160 上限——长信不留小窗。"""
    screens = _text("screens.css")
    rule = screens[screens.index(".compose-pen {"):]
    rule = rule[: rule.index("}")]
    assert "min-height: calc(var(--baseline) * 10)" in rule
    assert "max-height: none" in rule
