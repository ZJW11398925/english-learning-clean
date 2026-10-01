"""v2-1 内核铸刀的最低钉集（mature core brief 的可执行真值）。

设计权威源 = docs/research/2026-10-01-v2-mature-core-brief.md（铁胆墨
×真纸内核）。本文件钉住刀内八面（随迁钉在各族既有文件里，这里只钉
新增最低集）：

1. tokens v2 关键真值 — 14 色代表值 / 基线 32 / 正文 17/32 / 字体栈首名；
2. 品牌名单点 — 品牌字面值在 webui 七文件里恰 2 处物理点（app.js 的
   BRAND 常量 + index.html 的静态兜底），第三处即红；
3. 信件排印骨架结构类在场 — 日期/称呼/正文段/落款/又及五件与提取
   纪律（不虚构文本——提取函数在场）；
4. 邮戳事件绑定 — 寄出（在途封 JS 接线）/ 结课（教学卡 settled 臂）/
   归档开启（形态登记位）三类事件各有所绑，装饰水印缺位；
5. 零常驻循环 — 无 infinite 迭代、无循环 keyframes；
6. LF 行尾 — webui 七文件字节级全 LF（f1r 页源钉敏感）；
7. 信封/信纸分物 — 在途信封形与撕口信纸两类在场、读信 = 信纸；
8. 其余屏令牌级换肤未重排 — 设置/伙伴/观察/信档结构类逐字不变
   （诚实钉：本刀只换肤，结构重铸属 v2-2）。
"""

from __future__ import annotations

from pathlib import Path

import elc.web

WEBUI = Path(elc.web.__file__).parent / "webui"
SHELL_FILES = ("index.html", "tokens.css", "components.css", "screens.css",
               "api.js", "components.js", "app.js")


def _text(name: str) -> str:
    return (WEBUI / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. tokens v2 — the mature core's own truth


def test_tokens_carry_the_v2_representative_values() -> None:
    """① 14 色代表值（≥6）+ 基线 32 + 正文 17/32 + 字体栈首名 +
    动效关键令牌——tokens.css 是 v2 物理出处的钉。"""

    tokens = _text("tokens.css")
    # the iron-gall 14 (six representatives across the four tiers)
    for declaration in (
        "--paper: #f6f2e8;",       # 主纸（脱数码白）
        "--ink: #191b1e;",         # 冷墨正文
        "--accent: #2c476a;",      # 钢笔墨蓝强调
        "--accent-deep: #1c3049;",  # 深档
        "--seal: #9a392b;",        # 朱砂——只盖真实事件
        "--rule: #d9d3c5;",        # 发丝线
    ):
        assert declaration in tokens, declaration
    # the baseline grid and the letter body rung（字落线上）
    assert "--baseline: 32px;" in tokens
    assert "--measure: 34em;" in tokens
    assert "--fs-body: 17px;" in tokens
    assert "--lh-body: 32px;" in tokens
    # the font stacks' first families（简报 §3a）
    assert "--f-serif: 'Sitka Text', Constantia," in tokens
    assert "--f-display: 'Sitka Display', 'Sitka Banner'," in tokens
    assert "--f-hand: KaiTi," in tokens
    assert "--f-ui: 'Segoe UI Variable Text'," in tokens
    # the motion tokens（纸先落、墨后渗）
    assert "--dur-ink: 360ms;" in tokens   # opacity 恒慢 ≈1.3×
    assert "--dur-wet: 600ms;" in tokens   # 墨水物理一次性
    # the legacy aliases resolve into the v2 tiers（消费面平滑）
    assert "--pencil: var(--accent);" in tokens
    assert "--bg: var(--paper);" in tokens
    # the body/pen/annotation line heights lock the baseline（消费面）
    css = _text("components.css")
    assert (
        '.say { margin: 0; font-size: var(--fs-body);\n'
        "       line-height: var(--baseline);" in css
    )
    assert "line-height: var(--baseline); padding: 10px 2px;" in css  # .pen


# ---------------------------------------------------------------------------
# 2. the brand name's two physical points


def test_the_brand_literal_has_exactly_two_physical_points() -> None:
    """② 品牌字面值「展信佳」在 webui 七文件里恰 2 处物理点：app.js
    （BRAND 单点常量）与 index.html（<title> + 信头静态兜底）；第三处
    即红。中文品牌名不得与其它字符串混入第三文件。"""

    hits = []
    for name in SHELL_FILES:
        count = _text(name).count("展信佳")
        if count:
            hits.append((name, count))
    assert [name for name, _ in hits] == ["index.html", "app.js"], hits
    # app.js: exactly the BRAND constant (single point of rename)
    app = _text("app.js")
    assert (
        'const BRAND = { name: "展信佳",'
        ' tagline: "见字如晤，今日如何", en: "Dear You" };' in app
    )
    assert app.count("展信佳") == 1
    # index.html: the title and the header fallback (same values)
    index = _text("index.html")
    assert "<title>展信佳</title>" in index
    assert '<div class="who">展信佳</div>' in index
    # the old brand is gone from the whole face（用户令：连「英语客厅」
    # 也换掉——含 aria-label）
    whole = "".join(_text(name) for name in SHELL_FILES)
    assert "英语客厅" not in whole
    assert "展信佳印记" in whole  # the brand mark's aria-label rides v2


# ---------------------------------------------------------------------------
# 3. the letter skeleton's structural classes


def test_the_letter_skeleton_classes_exist() -> None:
    """③ 排印骨架五件的结构类在场（CSS 形 + JS 提取纪律）：日期行 /
    称呼 / 正文段（段距 0.75em 零缩进）/ 落款（楷体手迹位齐右）/
    又及；骨架件件来自真实数据——提取函数在场，不虚构问候/结束语文本。"""

    css = _text("components.css")
    for selector in (".letter-date {", ".letter-salut {", ".letter-sign {",
                     ".letter-ps {"):
        assert selector in css, selector
    # the body paragraph mode: 0.75em gaps, zero indent (craft law 6)
    assert ".letter .say + .say { margin-top: 0.75em; }" in css
    # the signature is the hand tier, right-aligned
    sign = css[css.index(".letter-sign {"):]
    sign = sign[:sign.index("}")]
    assert "font-family: var(--f-hand);" in sign
    assert "font-size: var(--fs-hand);" in sign
    assert "text-align: right;" in sign
    js = _text("components.js")
    # the extraction discipline: the skeleton's parts come from the
    # text itself, or the part is absent — no fabricated greetings
    for factory in ("function letterParagraphs(", "function salutationOf(",
                    "function signatureBlockOf(", "function isPostscript(",
                    "function letterDate("):
        assert factory in js, factory
    assert 'sign.textContent = "你";' in js  # 落款 = 第二人称（不虚构人名）


# ---------------------------------------------------------------------------
# 4. the postmark binds only real events


def test_the_postmark_binds_real_events_only() -> None:
    """④ 邮戳三真实事件各有所绑（简报 T2）：寄出 = 在途封（JS 接线）；
    结课 = 教学卡完成态邮票（readReplyAnswer 的 settled 臂）；归档
    开启 = 信档日期戳形态登记位（条目载体 v2-2——不虚构挂点）。装饰
    水印缺位。"""

    app = _text("app.js")
    # 寄出：en-route 挂载时盖 --sent 邮戳（120ms 盖印动画）
    assert 'postmark.className = "postmark postmark--sent stamp-press";' in app
    css = _text("components.css")
    assert ".postmark--sent" in css
    # 结课：settled 臂的邮票印记（真实事件 = 批注成功收场）
    components = _text("components.js")
    assert 'stamp.classList.add("card-stamp", "stamp-press");' in components
    # 归档开启：--archived 形态登记位（无 JS 消费者——不虚构挂点）
    assert "postmark--archived" in css
    assert "postmark--archived" not in app
    assert "postmark--archived" not in components
    # 装饰水印缺位（邮戳不再作纯装饰）
    assert "marginalia-mark" not in css
    assert 'data-icon="postmark"' not in _text("index.html")
    # 朱砂的用面纪律：结课戳与红笔圈走 --seal；品牌印记不是事件
    assert "color: var(--seal);" in css
    assert ".brandmark .bm-seal { fill: var(--accent); }" in css


# ---------------------------------------------------------------------------
# 5. zero standing loops


def test_zero_standing_loop_animations() -> None:
    """⑤ 零常驻循环（简报 §5 死刑清单）：无 infinite 迭代、无循环
    keyframes——呼吸循环件已退役，loading 尾点静态化。"""

    for name in ("tokens.css", "components.css", "screens.css"):
        css = _text(name)
        assert "infinite" not in css, name
    css = _text("components.css")
    for retired in ("@keyframes state-breathe {", "state-breathe",
                    "animation: none"):
        assert retired not in css, retired
    # the loading tail is static (the information never needed the loop)
    assert (
        '.state-banner--loading::after { content: "…";'
        " display: inline-block; }" in css
    )


# ---------------------------------------------------------------------------
# 6. LF line endings, byte-level


def test_the_webui_files_are_lf_terminated() -> None:
    """⑥ 七文件字节级全 LF（f1r 页源钉敏感；本环境 Edit 可能落
    CRLF——交付前自验义务的钉形）。"""

    for name in SHELL_FILES:
        data = (WEBUI / name).read_bytes()
        assert b"\r\n" not in data, name
        assert data.count(b"\n") > 0, name


# ---------------------------------------------------------------------------
# 7. the envelope / letter-paper split


def test_the_envelope_and_the_letter_paper_are_two_objects() -> None:
    """⑦ 封/信分物（简报 T1-4）：在途 = 信封形（矩形 + 封舌 + 折线，
    信文暂不可见）；读信 = 信纸（撕口保留——人手触碰过的件才有毛边）；
    无拆信演出（信封摘除 = 同一 DOM 类切换，零转场 keyframes）。"""

    css = _text("components.css")
    # the envelope: flap (clip-path) + fold line + hidden sheet
    assert ".letter.me.en-route::before {" in css
    assert "clip-path: polygon(0 0, 100% 0, 50% 96%, 50% 100%, 0 100%);" in css
    assert ".letter.me.en-route::after {" in css
    assert ".letter.me.en-route .paper { visibility: hidden; }" in css
    # the letter paper: the torn slip stays (the anchor's own polygon)
    assert (
        "clip-path: polygon(0 6px, 4% 2px, 11% 7px, 19% 1px, 27% 6px,"
        in css
    )
    # no unsealing transition: the swap is a bare class toggle
    for forbidden in ("@keyframes unseal", "@keyframes open-envelope",
                      "@keyframes unfold-envelope"):
        assert forbidden not in css, forbidden


# ---------------------------------------------------------------------------
# 8. the other screens ride the tokens only (no structural reflow)


def test_the_other_screens_keep_their_structure() -> None:
    """⑧ 诚实钉：本刀其余屏只承受令牌级换肤——设置 / 记忆 / 隐私 /
    搜索 / 观察读数的结构类与面板 id 逐字不变（结构重铸属 v2-2）。
    换肤声明 = 令牌引用在场 + 结构类不变双断言。"""

    index = _text("index.html")
    # the settings face keeps its two blocks and its honest sentences
    for marker in ('<section id="drawer-settings" role="tabpanel"',
                   "<h3>现在能如实说的</h3>", "<h3>三档教学模式（参考）</h3>",
                   'id="set-memory"', 'id="set-privacy"',
                   'id="study-progress"', 'id="letter-search"',
                   'id="obs-status"', 'id="raw-readings"'):
        assert marker in index, marker
    # the panels' ids are untouched (the JS reads the same ids)
    for panel in ("study-today", "study-goal", "study-progress",
                  "drawer-memory", "drawer-privacy", "drawer-settings"):
        assert f'id="{panel}"' in index, panel
    # the read face still rides the same state-banner family（换肤 =
    # 令牌，不是组件替换）
    components = _text("components.js")
    assert "export function stateBanner(kind, opts) {" in components
    assert "mountLetterSearch();" in _text("app.js")
    # the disclosure/family-groups factories unchanged（结构工厂零改，
    # 工厂在 app.js：family-groups 类由装配侧落）
    assert 'root.className = "family-groups";' in _text("app.js")
