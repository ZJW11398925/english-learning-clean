"""wf-3 — 门厅世界化的钉（封面信世界优先第一句话 + 又及四词全点名 +
零字面 + 「唯一形态」散文同族扫全 + 既有锚存活）。

授权链：``DEC-OPI-5fc42174-….5`` R5（门厅世界化 + 全局收口——wf 程序
收段刀）。读法：门厅封面信第二段从「固定笔友」改写为世界优先——案头
安在一座小镇里，通信对象是镇上的人（零字面：不提名任何世界名）；又及
四词全部点名（wf-2 起 navdock 为四项，旧句只点名温故/抽屉）；DEC-…92
句义修订（「随信呈现的唯一形态 = 内联故事块；世界日志屏是历史回看面
不随信，两者并存」）同族扫全——app.js 三处旧句形与 components.css 一
处随刀迁净。

钉形随仓内先例：源码串钉（rd-2/w8 ``_text`` 同法——JS 行为的活体验证
以仓外承担，仓内只落源码结构钉）。
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "elc"

WEBUI_FILES = (
    "webui/api.js",
    "webui/app.js",
    "webui/components.css",
    "webui/components.js",
    "webui/index.html",
    "webui/screens.css",
    "webui/tokens.css",
)


def _text(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _squashed(text: str) -> str:
    return "".join(text.split())


# ---------------------------------------------------------------------------
# 1. the cover letter opens with the world
# ---------------------------------------------------------------------------

def test_the_cover_letter_opens_with_the_world() -> None:
    """封面信第二段：世界优先第一句话，逐字（DEC-…5 R5 的改写靶）；
    「给明日之自己写信」双重收信人意象保留。"""

    index = _text("webui/index.html")
    assert (
        "今日落笔，明日展信。这张案头安在一座小镇里：你住进镇上，同镇"
        "上的人一封封通信，也在给明日之自己写信——两重收信人，同一张信"
        "纸。想写什么就写什么，中文英文都行；写错了，正是回信要讲给你"
        "听的地方。" in index
    )
    # 世界优先意象的三个承重词（小镇 / 住进 / 镇上的人）全部在场
    for word in ("一座小镇", "住进镇上", "镇上的人"):
        assert word in index, word


def test_the_fixed_penfriend_leaves_the_cover() -> None:
    """旧句「固定笔友」在 index.html 全文缺位（改写前唯一出现在封面
    第二段；比 w8/rd-2 的整句缺位钉更紧一档——单向收紧）。"""

    index = _text("webui/index.html")
    assert "固定笔友" not in index
    assert "固定笔友" not in _squashed(index)


# ---------------------------------------------------------------------------
# 2. the postscript names all four dock words, world included
# ---------------------------------------------------------------------------

def test_the_postscript_names_all_three_words_with_the_world() -> None:
    """WR-5 随迁（世界日志屏退役，navdock 回三项）：又及句回「三个词」
    且按现役次序点名（案头/温故/抽屉）；世界不再是底部词，但其从句
    改读「世界就在那里过日子」——案头即世界自然发展之地（DEC-OPI-
    8a4f980b…7）。"""

    index = _text("webui/index.html")
    ob_ps = ""
    for line in index.splitlines():
        if 'class="ob-para ob-ps"' in line:
            ob_ps = line
            break
    assert ob_ps, "ob-ps paragraph not found"
    assert "又及：进门以后，底部三个词随时可走。" in ob_ps
    assert "世界就在那里过日子" in ob_ps
    # 三词点名 + navdock 现役次序（WR-5 起三项）
    order = [ob_ps.index(w) for w in ("案头", "温故", "抽屉")]
    assert order == sorted(order), order


# ---------------------------------------------------------------------------
# 3. zero place-name literal in the webui face
# ---------------------------------------------------------------------------

def test_no_place_name_literal_in_webui() -> None:
    """零字面：webui 七文件无任何世界名字面（门厅静态文案不提名——
    小镇意象通用，世界名由端点驱动）。"""

    for rel in WEBUI_FILES:
        body = _text(rel)
        assert "Berrymoor" not in body, rel
        assert "berrymoor" not in body.lower(), rel


# ---------------------------------------------------------------------------
# 4. the DEC-…92 revised reading, swept across the prose
# ---------------------------------------------------------------------------

def test_stale_unique_form_prose_swept() -> None:
    """散文扫全：旧句形「世界呈现唯一形态 / 世界呈现的唯一形态」在
    app.js / components.css / index.html 缺位；修订句形「随信呈现的
    唯一形态」在场——app.js 三处（语言态节 + DEC-…92 节头 + 故事块
    节；WR-5：世界日志屏节随屏退役），components.css 一处；
    「历史回看面…并存」语义句随屏退役（WR-5：屏不存在，无并存读法）。"""

    stale_forms = ("世界呈现唯一形态", "世界呈现的唯一形态")
    for rel in ("webui/app.js", "webui/components.css", "webui/index.html"):
        body = _text(rel)
        for form in stale_forms:
            assert form not in body, (rel, form)
    app = _text("webui/app.js")
    # 三处 = :语言态节 / :DEC-…92 节头 / :故事块节（WR-5：世界日志屏
    # 节随屏退役，其第四处计数随迁）。
    assert app.count("随信呈现的唯一形态") == 3
    assert _text("webui/components.css").count("随信呈现的唯一形态") == 1
    # WR-5：index.html 的第四处（世界日志屏注释）随屏退役归零。
    assert _text("webui/index.html").count("随信呈现的唯一形态") == 0
    # WR-5：世界日志屏已退役，「历史回看面…并存」句随之缺位。
    assert "历史回看面" not in app
    assert "两者并存" not in app


# ---------------------------------------------------------------------------
# 5. the prior cover anchors survive the rewrite
# ---------------------------------------------------------------------------

def test_prior_cover_anchors_survive_the_rewrite() -> None:
    """既有门厅钉族逐条判真随迁的存证（rd-2 / fg2 / w8 / f1r 的锚全部
    被改写保留——那四个文件因此零改动）：称呼、时序题眼、两重收信人、
    副题、语言立场句、进门钮。"""

    index = _text("webui/index.html")
    assert "致 明日之我：" in index                     # rd-2/w8/r1w
    assert "致明日之我" in _squashed(index)             # rd-2:57（去空白）
    assert "今日落笔，明日展信。" in index              # w8:152/f1r:104
    assert "两重收信人，同一张信纸" in index            # w8:157/rd-2:59
    assert "见字如晤，今日如何" in index                # w8:162
    assert "中文英文都行" in index                      # w8:163
    assert "拆开这封信 →</button>" in index             # r1w/fg2


def test_the_teaching_paragraph_is_untouched() -> None:
    """教学旁听段（封面第三段）逐字不动——本刀靶只有第二段与又及。"""

    index = _text("webui/index.html")
    assert (
        "写着写着，它在旁听着。发现值得练的表达，它随信递来一条英文"
        "批注——答对答错都有回音，也可以先搁着。" in index
    )
