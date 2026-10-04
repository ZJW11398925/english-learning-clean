"""rd-2 — 文案洒脱豪放档的钉（致明日之我 + 今日如何 + 批注家族 +
温故/抽屉 + 语气宪法）。

授权链：用户裁定 ``DEC-OPI-dc0ba4b6-….13`` 之②（原话「文案越洒脱豪放
越好」+ 两锚例必采）；调研底稿 = ``docs/research/2026-09-30-frontend-
redesign-research.md`` 调研E。语义底线三条（调研E 宪法第 4 条）任何豪放
不得丢：①中文也可以写 ②教学发生在英文 ③写错会被看见且被回应。

钉形随仓内先例：源码串钉（w8/fg1 ``_webui_text`` 同法——JS 行为的活体
验证以仓外 Node 单跑承担，仓内只落源码结构钉）。豁免清单（指称式历史
句循 spec 9.8-17 先例）：8.0 逐页剖析、8.7 实现注记、9.7–9.9 历史登记、
css 注释（rd-1 冻结面）与服务端 status_cn/kind_cn（web.py 冻结）不在本
钉缺位断言范围。
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "elc"
SPEC = REPO / "docs" / "FRONTEND_SPEC.md"


def _text(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def _squashed(text: str) -> str:
    return "".join(text.split())


# ⑧ 8.1–8.6 = 现役定稿区（8.0 诊断史与 8.7 实现注记按指称式先例豁免）
def _spec_current_zone() -> str:
    spec = _spec_text()
    return spec.split("### 8.1 信息架构总纲", 1)[1].split(
        "### 8.7 实现注记", 1)[0]


# ---------------------------------------------------------------------------
# 1. the two user anchors, verbatim


def test_anchor_one_the_cover_is_a_letter_to_tomorrow() -> None:
    """锚例一：封面开篇「致明日之我」——称呼/题眼含「致明日之我」；
    两重收信人叙事与「今日落笔，明日展信」时序意象在场；结构锚
    （称呼体例 / 又及 / 进门钮 / h1 / title）不动。v2-1 命名随迁
    （简报 §1，品牌换名是用户令）：英文并写 Dear You、题 = 展信佳；
    旧品牌字面缺位。"""

    index = _text("webui/index.html")
    assert "致 明日之我：" in index          # 称呼（排版带空格）
    assert "致明日之我" in _squashed(index)  # 题眼逐字（去空白）
    assert "今日落笔，明日展信。" in index
    assert "两重收信人，同一张信纸" in index
    # 结构与视觉锚不动；v2 命名随迁（wordmark = Dear You、题 = 展信佳）
    assert "DEAR YOU" in index
    assert "<h1>展信佳</h1>" in index
    assert "<title>展信佳</title>" in index
    assert ">拆开这封信 →</button>" in index
    assert 'class="ob-para ob-ps"' in index  # 又及段结构保留
    # 旧称呼缺位（防回潮）+ 旧品牌缺位（v2 用户令：连「英语客厅」也换）
    assert "致 来到门前的人：" not in index
    assert "把英语请进客厅" not in index
    assert "英语客厅" not in index


def test_anchor_two_the_placeholder_asks_about_today() -> None:
    """锚例二：输入框 placeholder = 「今日如何？」（逐字）；旧 placeholder
    缺位。"""

    index = _text("webui/index.html")
    assert 'placeholder="今日如何？"' in index
    assert "写一句……中文英文都行" not in index


# ---------------------------------------------------------------------------
# 2. the three semantic floors stay discoverable（宪法第 4 条）


def test_the_three_semantic_floors_survive_the_boldness() -> None:
    """底线①中文也可以写（封面 + 空厅两处在场）②教学发生在英文（封面
    「英文批注」）③写错被看见且被回应（封面「回信要讲给你听」+ 空厅
    「笔友接得住」）——placeholder 让位锚例后，不读封面也能从空厅句得知
    中文可写。"""

    index = _text("webui/index.html")
    app = _text("webui/app.js")
    # ① 中文也可以写
    assert "中文英文都行" in index            # 封面段
    assert "中文英文都行" in app              # 空厅句（不读封面也得知）
    # ② 教学发生在英文
    assert "英文批注" in index                # 封面段二
    # ③ 写错会被看见且被回应
    assert "写错了，正是回信要讲给你听的地方" in index
    assert "写错了，笔友接得住" in app


def test_the_who_sub_carries_the_new_boldness() -> None:
    """who-sub 升 v2 副题（简报 §1：见字如晤，今日如何——与用户锚例
    「今日如何」同族）；旧中档句缺位。语言立场「中英不拘」由封面段与
    空厅句承载（test_the_three_semantic_floors…钉不缺位）。"""

    index = _text("webui/index.html")
    assert "见字如晤，今日如何" in index
    assert "一位固定笔友 · 中英不拘" not in index
    assert "固定笔友 · 中文英文都行" not in index


def test_the_empty_hall_line_is_the_bold_form() -> None:
    """空厅句豪放重写；W-8 中档句缺位（防回潮）。"""

    app = _text("webui/app.js")
    assert (
        "信还没开始写——想从哪句起，就从哪句起。中文英文都行；"
        "写错了，笔友接得住。" in app
    )
    assert (
        "信还没开始写——想说什么就写什么，中文或英文都行；客厅正听着。"
        not in app
    )


# ---------------------------------------------------------------------------
# 3. the nav words（面 3）


def test_the_nav_words_are_wengu_and_drawer() -> None:
    """dock 三词 = 案头 / 温故 / 抽屉（v2-1R：品牌更名「展信佳」后旧
    空间词「客厅」退役，信件案头语域归位）；空间头与 aria-label 同
    步；写信动作词不动（寄出 → 保留）。「信匣」经功能核实名不副实
    （抽屉装记忆/隐私/设置，无信件收藏），退「抽屉」——核实结论见回执。"""

    index = _text("webui/index.html")
    # v3-a 随迁（落墨页签）：文字标签同钮在册（标签行收尾，非按钮行）
    for label in (">案头</span></button>", ">温故</span></button>",
                  ">抽屉</span></button>"):
        assert label in index, label
    assert '<div class="who">温故</div>' in index
    assert '<div class="who">抽屉</div>' in index
    assert 'aria-label="温故的节"' in index
    assert 'aria-label="抽屉的节"' in index
    assert "寄出 →</button>" in index
    assert ">学案</button>" not in index
    assert ">柜抽</button>" not in index


def test_the_old_space_words_are_retired_from_live_faces() -> None:
    """「学案」「柜抽」从现役 live 面退役：index.html / app.js /
    components.js / api.js 全文缺位；spec 8.1–8.6 现役区缺位（豁免：
    8.0 诊断史、8.7 实现注记、9.7–9.9 历史登记、css 注释——指称式
    先例，豁免清单在模块 docstring）。"""

    for rel in ("webui/index.html", "webui/app.js", "webui/components.js",
                "webui/api.js"):
        body = _text(rel)
        assert "学案" not in body, rel
        assert "柜抽" not in body, rel
    zone = _spec_current_zone()
    for retired in ("学案 ·", "柜抽 ·", "客厅 / 学案 / 柜抽", "学案节名",
                    "柜抽节名", "请出柜抽", "不在柜抽", "短笺频率",
                    "保存短笺频率", "短笺：{功能句}", "寄出作答",
                    "这次跳过", "✓ 答对了"):
        assert retired not in zone, retired


# ---------------------------------------------------------------------------
# 4. the annotation family（面 4 批注家族）


def test_the_annotation_family_heads_the_card() -> None:
    """批注家族：卡头「批注：」、指路行回应族、寄出回应、先搁着（含
    busy 与回音）、批注来了/没能开始、批注频率、批注来过才会有账、
    批注痕迹；rd-3 随迁（9.11-22 移走清单）：「留了批注」（ACTION_CN）、
    门规三词（GATE_REASON_CN）与「为什么留了这张批注」面板随诊断五板
    移出用户面——服务端词面（web.py）不动，前端缺位由
    test_rd3_information_architecture.py 钉住。"""

    components = _text("webui/components.js")
    app = _text("webui/app.js")
    index = _text("webui/index.html")
    assert '"批注："' in components
    assert "回应写在这张批注上（不是下面的信纸）。" in components
    assert '"寄出回应"' in components
    assert 'skip.textContent = "先搁着";' in components
    assert "搁置中……" in components
    assert "先搁着了——回头再拾。" in components
    assert "回应已寄出。" in components
    assert "再试一回？" in components
    assert "批注来了——就在下面的信流里。" in app
    assert "没能开始这张批注——" in app
    assert 'TEACHING_OPEN: "留了批注"' not in app
    assert "批注来过才会有账" in app
    assert "另一张批注还在进行" not in app
    assert "批注锁不成立" not in app
    assert "这张批注走不下去" not in app
    # provider 刀随迁：批注频率保存钮随温故第二编辑面退役（设置节唯一
    # 编辑点）；词面不回潮
    assert "保存批注频率" not in app
    assert ">为什么留了这张批注</h3>" not in index
    assert "批注痕迹" in index
    # 旧家族词缺位（live 面）
    assert '"短笺："' not in components
    assert "寄出作答" not in components
    assert "这次跳过" not in components
    assert "作答写在这张短笺上" not in components
    assert "短笺来了" not in app


def test_the_verdict_and_kind_words_follow_the_family() -> None:
    """判词豪放档（✓ 答得漂亮 / ◐ 答了一半；✗ 没答中与「这次没法判」
    不动）双面一致（卡面 OUTCOME_VERDICT_CN 与账页 OUTCOME_CN）；
    kind 映射 CURRENT_USER_ERROR → 你信里的句子；lifecycle 读法
    等你回应。"""

    components = _text("webui/components.js")
    app = _text("webui/app.js")
    assert 'SUCCESS: "✓ 答得漂亮"' in components
    assert 'PARTIAL: "◐ 答了一半"' in components
    assert 'FAILURE: "✗ 没答中"' in components
    assert 'ABSTAIN: "这次没法判"' in components
    assert 'SUCCESS: "答得漂亮"' in app
    assert 'PARTIAL: "答了一半"' in app
    assert "你信里的句子" in components
    assert "来自你的句子" not in components
    assert 'AWAITING_USER: "等你回应"' in components
    assert "等你作答" not in components


def test_the_sent_line_replaces_the_en_route_placeholder() -> None:
    """发送后状态行「信已寄出，等回信——笔友把灯留着。」（v2-1 锚屏
    措辞精修：客厅→笔友——回信者是笔友）；旧占位缺位
    （app.js live 面；spec 8.5 的指称式「原『（回信在途中……）』」豁免）。"""

    app = _text("webui/app.js")
    assert "信已寄出，等回信——笔友把灯留着。" in app
    assert "回信在途中" not in app


def test_the_registered_exceptions_stay_untouched() -> None:
    """两处登记例外不动（防误伤）：作答框「用英语写一句试试……」
    （W-8 已裁，用户未推翻）与「批改中……」（批注家族词面自洽）。"""

    components = _text("webui/components.js")
    assert "用英语写一句试试……" in components
    assert "批改中……" in components


def test_no_emoji_in_the_teaching_card_domain() -> None:
    """教学卡域去 emoji：components.js 全文无 💡（「💡 教学时刻」族已在
    W-8 退役，rd-2 批注家族不得回流 emoji）。"""

    components = _text("webui/components.js")
    assert "💡" not in components
    assert "教学时刻" not in components


# ---------------------------------------------------------------------------
# 5. the tone constitution lands in the spec（面 5）


def test_the_tone_constitution_lands_in_the_spec() -> None:
    """语气宪法 7 条入 spec 8.4.1 新节：节标题 + 七条关键句逐字 + 动作
    词表；授权句引 DEC-….13。"""

    zone = _spec_current_zone()
    assert "#### 8.4.1 语气宪法（rd-2 定稿 · 2026-09-30）" in zone
    for line in (
        "一句一事，主句 12–22 字；30 字长句只许铺陈画面，一屏最多一句",
        "破折号一屏 ≤2 处；全站不用感叹号（教学反馈例外且最多一个）；问号",
        "自造诗性",
        "**功能语义优先（不可牺牲）**",
        "禁用：喊话祈使（立即 / 马上 / 快来）、网络热词、机械对仗假古风、",
        # v2-s 换名随迁：第 6 条自称改「笔友」（原自称词随品牌换名
        # 退役），人称纪律逐字强度不变
        "对用户称「你」（不用「您」）；自称「笔友」",
        "错误反馈写具体改法（「这个词换成 X 更自然」）；不写「错误 / 失败」",
        "动作词表：寄出、收起、回信、留一句、搁一搁、翻看",
    ):
        assert line in zone, line
    spec = _spec_text()
    assert "DEC-OPI-dc0ba4b6-…13" in spec


def test_the_spec_carries_the_rd2_registration() -> None:
    """9.10 rd-2 修订登记在场：条号 21、两锚例名目、信匣核实结论、
    批注家族、钉随迁与新钉名。"""

    spec = _spec_text()
    assert "### 9.10 rd-2 修订登记（文案洒脱豪放档，2026-09-30）" in spec
    for fact in ("致明日之我", "placeholder「今日如何？」",
                 "「信匣」经功能核实名不副实",
                 "批注家族", "test_rd2_copy_bolding.py"):
        assert fact in spec, fact


# ---------------------------------------------------------------------------
# 6. the middle-register sentences stay retired（W-8 防回潮，全仓形）


def test_the_w8_middle_register_sentences_stay_retired() -> None:
    """W-8 中档句整句缺位（子串「中文英文都行」被新句合法使用，故钉
    整句形）；范围 = src/elc + spec 现役区。"""

    corpus = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(SRC.rglob("*"))
        if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"}
    ) + "\n" + _spec_current_zone()
    for retired in (
        "这间客厅只做一件事——你和一位固定笔友以通信学英语",
        "固定笔友 · 中文英文都行",
        "写一句……中文英文都行",
        "信还没开始写——想说什么就写什么，中文或英文都行；客厅正听着。",
        "致 来到门前的人：",
    ):
        assert retired not in corpus, retired
