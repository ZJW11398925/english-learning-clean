"""fr-B — 动画体系专项刀 B（过渡与衔接动画体系）的钉面。

授权链：用户「动画体系专项刀 B」任务书（分支 frontend-revamp，刀 A 之上
继续，绝不合并）；规范注册 = docs/FRONTEND_SPEC.md（②-5 令牌表 fr-B 行 /
③ #11 confirm-dialog 行重铸 / ⑨-5 动效注册表 fr-B 新行与抽屉开合改行 /
⑩ 10.2 z 序表与 10.4 Esc 阶梯改行）。本文件按任务书四面分组——结构性
钉（删实现即红；变异证据见回执）：

组：
1. 令牌体系——三档时长（微交互/面板/整屏转场）× 曲线族（进场减速长尾/
   退场加速/弹簧）全走令牌；
2. 空间转场——CSS 进入层 + app.js 交叉淡化退出编排（showSpace/showSection
   同构）+ nudge 保护负控（温故/抽屉 .spacebody 不走 keyframe）；
3. 弹窗三族——#11 自绘确认窗（原生 window.confirm 退役）/ 词卡褪下 /
   教学卡回应区首渲；
4. 列表错峰 + 微交互 + 性能/reduced-motion/spec 注册——stagger 28ms 档 /
   chip 反白过渡 / 弹簧 flip-tick / 新 keyframes 零布局属性负控 / ⑨-5 与
   ⑩ 同刀改行在册。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI = REPO_ROOT / "src" / "elc" / "webui"
SPEC = REPO_ROOT / "docs" / "FRONTEND_SPEC.md"


def _webui(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


def _spec() -> str:
    return SPEC.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1 — 令牌体系（三档时长 × 曲线族）


def test_the_transition_token_family_exists() -> None:
    """fr-B 令牌族：整屏转场档四值（space-in 340 / space-out 220 /
    dialog-in 300 / stagger 28——20–40ms 区间取中）+ 弹簧曲线一枚
    （cubic-bezier 近似 spring，overshoot 克制 1.25）；既有基底不动
    （rd-1/v2 旧值零改动）。"""

    tokens = _webui("tokens.css")
    for value in (
        "--dur-space-in: 340ms;",
        "--dur-space-out: 220ms;",
        "--dur-dialog-in: 300ms;",
        "--dur-stagger: 28ms;",
        "--ease-spring: cubic-bezier(0.34, 1.25, 0.4, 1);",
    ):
        assert value in tokens, value
    # 弹簧法则登记在令牌节（唯一 overshoot 的显式收窄修订）
    assert "--ease-spring 只许消费在指尖微件" in tokens
    # 既有基底零改动（抽查三枚旧值）
    assert "--dur-panel-in: 280ms;" in tokens
    assert "--ease-paper: cubic-bezier(0.16, 1, 0.3, 1);" in tokens


def test_the_token_table_registers_the_new_family() -> None:
    """spec ②-5 令牌表同刀改行：四值 + 弹簧族（含收窄修订句）在册。"""

    spec = _spec()
    for row in ("`--dur-space-in` `--dur-space-out`", "`--dur-dialog-in`",
                "`--dur-stagger`", "`--ease-spring`"):
        assert row in spec, row
    assert "对 rd-1「唯一 overshoot = 盖印收束」的显式收窄修订" in spec


# ---------------------------------------------------------------------------
# 2 — 空间转场（交叉淡化双向）


def test_the_space_enter_and_leave_rules() -> None:
    """进入层：全页纵深 .spacebody 走 paper-drop + ink-wash 双动画
    （--dur-space-in 整屏档 + 60ms 错峰），头部件（.top/.section-tabs）
    纯淡入先到位；退出层：.space--leave/.panel--leave = absolute 叠层 +
    纸底 + ink-wash reverse × --ease-exit，案头 fixed 家具帧即
    visibility 藏（opacity 改挂 fixed 包含块的 rd-1 坑）。
    负控（nudge 保护）：温故/抽屉的 .spacebody 不走 keyframe——
    keyframe fill 会压死 ux-1 滑动 nudge 的 transform（改走 tabpanel
    transition，其终态回落元素值）。"""

    screens = _webui("screens.css")
    assert ".dossier:not([hidden]) .spacebody {" in screens
    assert "paper-drop var(--dur-space-in) var(--ease-paper) both," in screens
    assert "animation-delay: 60ms, 60ms; }" in screens
    assert "#space-study:not([hidden]) :is(.top, .section-tabs)," in screens
    assert "#space-parlor:not([hidden]) .top {" in screens
    assert ".space--leave { position: absolute; top: 0; left: 0; right: 0;" \
        in screens
    assert "ink-wash var(--dur-space-out) var(--ease-exit)" in screens
    assert ".space--leave :is(.dock, .flow-bottom, .flow-ruler) {" \
        " visibility: hidden; }" in screens
    assert ".panel--leave { position: absolute;" in screens
    assert "ink-wash var(--dur-panel-out) var(--ease-exit)" in screens
    # nudge 保护负控：温故/抽屉 .spacebody 不得是 keyframe 载体
    assert "#space-study:not([hidden]) .spacebody" not in screens
    assert "#space-drawer:not([hidden]) .spacebody" not in screens
    # .spacebody 是节退出叠层的 relative 锚
    assert "position: relative;   /* fr-B：节退出叠层（.panel--leave）的锚 */" \
        in screens
    # 节面板进入：opacity + transform 双轨 + 60ms 错峰
    assert "transform: translateY(8px); }" in screens


def test_the_crossfade_orchestration_in_app_js() -> None:
    """退出编排（app.js）：leaving 查找 + cancelLeave（撤 fuse 摘类——
    快进快出安全）+ leaveLayer（落类 + animationend 对账 ink-wash +
    400 保险丝 + REDUCED_MOTION 直切）；showSpace 消费 space--leave、
    showSection 消费 panel--leave；hidden 账带 leaving 半。"""

    app = _webui("app.js")
    assert "function cancelLeave(node, cls) {" in app
    assert "function leaveLayer(node, cls) {" in app
    assert "if (REDUCED_MOTION.matches) {" in app
    assert 'event.animationName === "ink-wash" && event.target === node' in app
    assert "setTimeout(finish, 400);" in app
    assert 'if (leaving) leaveLayer(spaces[leaving], "space--leave");' in app
    assert 'if (leaving) leaveLayer(group[leaving], "panel--leave");' in app
    assert 'cancelLeave(spaces[name], "space--leave");' in app
    assert 'cancelLeave(group[name], "panel--leave");' in app
    assert "spaces[key].hidden = key !== name && key !== leaving;" in app
    assert "group[key].hidden = key !== name && key !== leaving;" in app


# ---------------------------------------------------------------------------
# 3 — 弹窗三族（确认窗 / 词卡 / 教学卡）


def test_the_native_confirm_is_retired() -> None:
    """#11 重铸：原生 window.confirm 全库退役；自绘窗 = cfrm-scrim
    （z 11 纸雾）+ cfrm（z 12，role=alertdialog + aria-modal）；
    消息一律 textContent（XSS 纪律）；异步 Promise；两臂 + 点雾 +
    Esc(capture + stopPropagation，只退本层) + Enter 四路径；开合
    对称（cfrm--out/scrim-out 褪下 + 480 保险丝）；焦点还回。"""

    js = _webui("components.js")
    # 调用级负控：window.confirm( 的调用形态全库绝迹（散文登记不算）
    assert "window.confirm(" not in js
    assert "window.confirm(" not in _webui("app.js")
    assert "export function confirmDialog(message) {" in js
    assert "return new Promise((resolve) => {" in js
    assert 'scrim.className = "cfrm-scrim";' in js
    assert 'box.className = "cfrm";' in js
    assert 'box.setAttribute("role", "alertdialog");' in js
    assert 'box.setAttribute("aria-modal", "true");' in js
    assert "text.textContent = String(message);" in js
    assert 'document.addEventListener("keydown", onKey, true);' in js
    assert "event.stopPropagation();" in js
    assert 'scrim.classList.add("cfrm-scrim--out");' in js
    assert 'box.classList.add("cfrm--out");' in js
    assert 'event.animationName === "paper-fold"' in js
    assert "setTimeout(settle, 480);" in js
    assert "restoreFocusTo.focus();" in js
    app = _webui("app.js")
    # 四个调用点全部 await 形态（runDelete 双层 ×2 + 搁批注切角色 +
    # 删笔友；reveal 臂在 components.js）
    assert app.count("await confirmDialog(") == 4
    assert 'button.addEventListener("click", async () => {' in js
    assert "!(await confirmDialog(\"看了答案" in js


def test_the_confirm_dialog_css() -> None:
    """#11 CSS：纸雾（--ink 降透明度 0.4，禁毛玻璃）scrim-in/out 同步；
    面板升起 --dur-dialog-in × --ease-paper + opacity ×1.3 恒慢；
    褪下 paper-fold + ink-wash reverse；层位 z 11/12（⑩ 同刀改行）。"""

    css = _webui("components.css")
    assert ".cfrm-scrim { position: fixed; inset: 0; z-index: 11;" in css
    assert ".cfrm { position: fixed; z-index: 12;" in css
    assert "paper-drop var(--dur-dialog-in) var(--ease-paper) both," in css
    assert ".cfrm--out { animation: paper-fold var(--dur-panel-out)" in css
    assert "@keyframes scrim-out { to { opacity: 0; } }" in css
    spec = _spec()
    assert "确认窗纸雾（fr-B） | 11 |" in spec
    assert "确认窗（fr-B） | 12 |" in spec
    assert "无 CSS（原生 confirm）" not in spec


def test_the_word_card_gains_a_settle_half() -> None:
    """词卡褪下：Esc/收起/点卡外三路径同一编排（word-card--out +
    word-scrim--out 落类，paper-fold | sheet-out 对账 + 480 保险丝）；
    换卡/互斥路径 opts.skipOut 直摘（showWordCard/showSpace/开沓/
    升写作态——残影不跟层走）；CSS 双形态（浮卡 fold / 触屏 sheet-out
    与入场对偶）。"""

    js = _webui("components.js")
    assert "export function closeWordCard(opts) {" in js
    assert 'scrim.classList.add("word-scrim--out");' in js
    assert 'card.classList.add("word-card--out");' in js
    assert 'event.animationName === "sheet-out"' in js
    assert "const instant = REDUCED_MOTION.matches || (opts && opts.skipOut);" \
        in js
    assert "closeWordCard({ skipOut: true });   // 换卡直摘" in js
    app = _webui("app.js")
    # veto-R 随迁 3 → 4：计量明细浮层的互斥开面（toggleTokenMeterPop）
    # 同法直摘。
    assert app.count("closeWordCard({ skipOut: true });") == 4
    css = _webui("components.css")
    assert ".word-card--out { animation: paper-fold var(--dur-panel-out)" \
        in css
    assert ".word-scrim--out { animation: scrim-out var(--dur-panel-out)" \
        in css
    assert "@keyframes sheet-out { to { transform: translateY(100%); } }" \
        in css


def test_the_teaching_card_reply_zone_fades_in() -> None:
    """教学卡回应区首渲：.guide/.replyrow/.skiprow 后插走 @starting-style
    （140ms × --ease-enter，位移 4px——渐进增强）。"""

    css = _webui("components.css")
    assert ".note-paper :is(.guide, .replyrow, .skiprow) {" in css
    assert "opacity: 0; transform: translateY(4px); }" in css


# ---------------------------------------------------------------------------
# 4 — 列表错峰 / 微交互 / 性能·降级·注册


def test_the_list_stagger_is_token_driven() -> None:
    """列表逐项错峰：.stagger-in + stagger-rise（140ms 淡入 + 4px 上移）
    × --dur-stagger 步长、前 8 项封顶（RESTAGGER_MAX）；restagger =
    摘类 + 强制重排 + 落类（可重触发）+ REDUCED_MOTION 直切；
    消费面 = familyGroupsBlock 与档案时间线两处搜索（restagger(shown)
    恰两处）。"""

    css = _webui("components.css")
    assert ".stagger-in { animation: stagger-rise var(--dur-1)" in css
    assert "animation-delay: calc(var(--i, 0) * var(--dur-stagger)); }" in css
    assert "@keyframes stagger-rise {" in css
    js = _webui("components.js")
    assert "export function restagger(nodes) {" in js
    assert "const RESTAGGER_MAX = 8;" in js
    assert 'node.style.setProperty("--i", String(index));' in js
    app = _webui("app.js")
    assert app.count("if (q) restagger(shown);") == 2


def test_the_micro_interactions() -> None:
    """微交互：chip --on 反白补 background-color 过渡（点选不硬闪）；
    开关拨动 = flip-tick（stamp-press 同形 × --ease-spring——弹簧族
    唯一现役消费面）由 meter toggle 重渲后落类。"""

    css = _webui("components.css")
    assert "background-color var(--dur-micro) var(--ease-press)," in css
    assert ".flip-tick { animation: stamp-press var(--dur-stamp)" \
        " var(--ease-spring)" in css
    app = _webui("app.js")
    assert 'fresh.classList.add("flip-tick");' in app


def test_the_new_keyframes_never_touch_layout() -> None:
    """性能负控：fr-B 三枚新 keyframes（stagger-rise / scrim-out /
    sheet-out）零 width/height/top/left——只动 transform/opacity；
    .space--leave/.panel--leave 的动画只引 ink-wash（opacity）。"""

    css = _webui("components.css") + _webui("screens.css")
    for name in ("stagger-rise", "scrim-out", "sheet-out"):
        start = css.index("@keyframes " + name)
        body = css[start: css.index("}", css.index("}", start) + 1) + 1]
        for banned in ("width", "height", "top:", "left:"):
            assert banned not in body, (name, banned)
    assert ".space--leave { position: absolute;" in css
    leave = css[css.index(".space--leave {"):]
    leave = leave[: leave.index("}\n") if "}\n" in leave else len(leave)]
    assert "animation: ink-wash" in leave


def test_the_registry_and_layer_charter_follow() -> None:
    """spec 注册：⑨-5 名册「全库十二枚」+ fr-B 新行（空间转场
    cross-fade / 确认窗升降 / 词卡褪下 / 列表逐项错峰 / 弹簧微件）；
    抽屉开合行的 Revisit 关闭句；⑩ Esc 阶梯的确认窗层。"""

    spec = _spec()
    assert "全库十二枚" in spec
    assert "空间转场 cross-fade（fr-B" in spec
    assert "确认窗升降（fr-B" in spec
    assert "词卡褪下（fr-B" in spec
    assert "列表逐项错峰 stagger（fr-B" in spec
    assert "弹簧微件 flip-tick（fr-B" in spec
    assert "Revisit 就此关闭" in spec
    assert "**确认窗答 false**（fr-B" in spec


# ---------------------------------------------------------------------------
# 5 — 处置刀（评审 frB-M5/M6/M7 三处 NOT-RED 钉缺口补强）：
#     reduced-motion JS 半区两处守卫 + 弹簧法则唯一消费面，各一行钉。


def test_the_restagger_reduced_motion_guard_is_pinned() -> None:
    """F-1 处置钉（评审 frB-M5）：restagger 的 reduced-motion 直切守卫
    ——spec ⑨-5 与交付回执⑥都声称「JS 半区 REDUCED_MOTION 直切」，
    守卫须在函数体内且承重（leaveLayer 同型 containment 钉法）。"""

    js = _webui("components.js")
    start = js.index("export function restagger(nodes) {")
    body = js[start: js.index("\n}", start)]
    assert "if (REDUCED_MOTION.matches) return;" in body


def test_the_flip_tick_reduced_motion_guard_is_pinned() -> None:
    """F-2 处置钉（评审 frB-M6）：设置计量开关拨动的 flip-tick 落类带
    !REDUCED_MOTION.matches 守卫（spec ⑨-5 弹簧行的「JS 半区不落类」）。"""

    app = _webui("app.js")
    assert "if (fresh && !REDUCED_MOTION.matches)" \
        " fresh.classList.add(\"flip-tick\");" in app


def test_the_spring_curve_has_exactly_one_consumer() -> None:
    """F-3 处置钉（评审 frB-M7）：弹簧法则的机器守卫——全 webui CSS 中
    var(--ease-spring) 恰一处消费（flip-tick 的 stamp-press 盖印形）；
    任何第二处消费（如位移 keyframes 配弹簧）即红。"""

    css = (_webui("components.css") + _webui("screens.css")
           + _webui("tokens.css"))
    assert css.count("var(--ease-spring)") == 1
    assert ".flip-tick { animation: stamp-press var(--dur-stamp)" \
        " var(--ease-spring)" in css
