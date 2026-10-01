"""W-8 — 用户思维三修的钉（对话语言跟随用户 + markdown 前端兜底 +
信流尾注退役）。

用户立场原话：「我从没有说过这个应用只能用英语交流」「前端所有显示必须
从用户角度，使用用户思维思考」。三面：

1. 语言立场：PromptCompiler 输出新增固定可信节 ``[response]``（在
   ``[channel]`` 之后、零插值、字节确定）；runtime controller 的四处
   ``language_policy`` 从 ``"default"`` 改 ``"follow-user"``；五处 live
   文案（封面 / who-sub / placeholder / 空厅 / spec 8.1.2 原则句）；
   旧英语限定句全仓退役（唯一登记例外 = 作答框「用英语写一句试试……」
   ——教学表达练习面，本刀范围外）。
2. markdown 兜底：``letterWords`` 三记号（**粗** / *斜* / ``码``）——
   正则分段、记号内照旧 span.word 分片外包 strong/em/code、纯节点拼装、
   无记号路径与旧输出逐字节同、未配对原样；.say 纸系样式三行。
3. 信流尾注退役：``blockedline`` / ``showBlockedNote`` / 调用点全删
   零残留（spec ③ 的类名行同刀清扫）；没递短笺的一轮在信流里静默，
   why_not 数据面不动。

钉形随仓内先例：源码串钉（fg1 ``_webui_text`` 同法）+ 编译级钉
（PromptCompiler 真跑，phase1 同法）。JS 行为的活体验证以仓外 Node
单跑承担（回执记录），仓内只落源码结构钉。
"""

from __future__ import annotations

from pathlib import Path

from elc.persona import (
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
    PromptCompiler,
)
from elc.platform.types import (
    ConversationId,
    InteractionChannel,
    Ok,
    PersonaId,
)
from elc.runtime.types import GenerationActionType

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "elc"
SPEC = REPO / "docs" / "FRONTEND_SPEC.md"

#: The response-stance block, verbatim (W-8 任务书 ①; cs-0 reworded the
#: second row — the mechanism word is gone, the semantics stay verbatim) —
#: the section header plus three key:value rows, zero interpolation.
RESPONSE_LINES = (
    "[response]",
    "language: follow the user — reply in the language the user writes in"
    " (simplified Chinese by default)",
    "english expressions: keep an expression itself in English,"
    " exactly as given",
    "format: plain prose, no markdown markers (**, *, #, `, _)",
)


def _text(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def _contract() -> GenerationContract:
    return GenerationContract(
        generation_contract_id="gc-w8",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=PersonaId("persona-w8"),
        allowed_disclosures=(),
        language_policy="follow-user",
        style_constraints=(),
    )


def _compile_prompt() -> str:
    context = GenerationContext(
        character_package=None,
        relationship_view=None,
        episode_view=None,
        world_lore_view=None,
        disclosed_user_profile=None,
        conversation_window=None,
        language_policy="follow-user",
        generation_policy="default",
        generation_contract=_contract(),
        ephemeral_teaching_directive=None,
    )
    request = PromptCompilationRequest(
        conversation_id=ConversationId("conv-w8"),
        persona_id=PersonaId("persona-w8"),
        interaction_channel=InteractionChannel.TEXT,
        generation_context=context,
        generation_contract=_contract(),
    )
    compiled = PromptCompiler().compile(request)
    assert isinstance(compiled, Ok), compiled
    return compiled.value.prompt_text


# ---------------------------------------------------------------------------
# 1. [response] — the fixed trusted section in the compiled prompt


def test_the_response_section_lands_after_the_channel() -> None:
    """The section exists, carries the three stance lines verbatim, and
    stands after ``[channel]`` — the last word the model reads before the
    stance is the system's own response contract."""

    text = _compile_prompt()
    block = "\n".join(RESPONSE_LINES)
    assert block in text
    assert text.index("[response]") > text.index("[channel]")
    # one header, one section; the tail is exactly the constant's bytes
    assert text.count("[response]") == 1
    assert text[text.index("[response]"):].startswith(block)


def test_the_response_section_is_byte_deterministic() -> None:
    """Same request in, byte-identical prompt out — the fixed section
    rides the same determinism the compiler already guarantees."""

    assert _compile_prompt() == _compile_prompt()


def test_the_controller_follows_the_user_language() -> None:
    """The four request/contract sites carry ``follow-user`` and no
    ``language_policy="default"`` kwarg survives in the controller."""

    controller = _text("runtime/controller.py")
    assert controller.count('language_policy="follow-user"') == 4
    assert 'language_policy="default"' not in controller


# ---------------------------------------------------------------------------
# 2. the five live copy faces


def test_the_cover_copy_follows_the_user_language() -> None:
    """index.html: the cover paragraph, who-sub and the dock placeholder
    speak the user's language stance, word for word. rd-2 升豪放档：
    封面信重写为「致明日之我」（锚例一），placeholder 占「今日如何？」
    （锚例二，逐字）；v2-1 随迁（简报 §1）：who-sub 升副题「见字如晤，
    今日如何」——语言立场句面由封面段（「中文英文都行」）与空厅句承载，
    断言语义不变（三处 live 面仍各自说清：给明日之自己写信 / 中文英文
    都行 / 真问句占位）。"""

    index = _text("webui/index.html")
    assert "今日落笔，明日展信。" in index
    # 锚例一：称呼/题眼含「致明日之我」（界面排版「致 明日之我：」带
    # 空格——去空白后逐字比对）
    assert "致 明日之我：" in index
    assert "致明日之我" in "".join(index.split())
    assert "两重收信人，同一张信纸" in index
    # v2 副题（简报 §1：名 + 副题小字；「中英不拘」立场句面由封面段
    # 「中文英文都行」承载——下一断言钉住不缺位）
    assert "见字如晤，今日如何" in index
    assert "中文英文都行" in index
    assert 'placeholder="今日如何？"' in index
    # W-8 中档句缺位（防回潮，rd-2 起——见 test_rd2_copy_bolding 的
    # 全仓形；此处就 file 面再钉一道）
    assert "固定笔友 · 中文英文都行" not in index
    assert "写一句……中文英文都行" not in index


def test_the_empty_hall_copy_follows_the_user_language() -> None:
    """app.js: the empty-hall system line invites either language and
    keeps floor ③ (a mistake gets answered) — rd-2 豪放句
    「笔友接得住」（v2-1R 随更名自「客厅接得住」随迁）承接 placeholder
    让位后的底线①③承载义务。"""

    app = _text("webui/app.js")
    assert (
        "信还没开始写——想从哪句起，就从哪句起。中文英文都行；"
        "写错了，笔友接得住。" in app
    )
    assert "用英语给笔友写" not in app
    # W-8 中档句缺位（防回潮）
    assert (
        "信还没开始写——想说什么就写什么，中文或英文都行；客厅正听着。"
        not in app
    )


def test_the_spec_carries_the_language_principle() -> None:
    """8.1.2 gains the principle sentence: conversation follows the user
    (Chinese by default); 『学习内容本身』 is the taught-expression face,
    not a conversation-language restriction. (Whitespace-normalized —
    the spec line-wraps the sentence.)"""

    normalized = "".join(_spec_text().split())
    assert (
        "对话语言跟随用户（默认中文）——『学习内容本身』指教学表达/例句/词卡，"
        "非对话语言的限定。" in normalized
    )


def test_the_english_only_sentences_are_retired_repo_wide() -> None:
    """The English-only sentence families are gone from src/elc and the
    spec. The one registered exception is the attempt box's
    「用英语写一句试试……」（components.js 作答框 + spec 8.2.10）——教学
    表达练习面，本刀范围外：钉先剥掉该登记形再断言缺位。rd-2 起 spec 面
    取现役区（8.1–8.6）——9.7–9.9 历史登记的旧词指称（9.8-17 指称式
    先例）不在缺位断言范围。"""

    spec_zone = _spec_text().split("### 8.7 实现注记", 1)[0]
    corpus = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(SRC.rglob("*"))
        if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"}
    ) + "\n" + spec_zone

    for retired in ("用英语通信", "来信去信都用英语", "用英语给笔友写",
                    # W-8 中档句全整句入缺位清单（rd-2 防回潮；「中文英文
                    # 都行」子串被新空厅句合法使用，故钉整句形而非子串）
                    "这间客厅只做一件事——你和一位固定笔友以通信学英语",
                    "固定笔友 · 中文英文都行",
                    "写一句……中文英文都行",
                    "信还没开始写——想说什么就写什么，中文或英文都行；"
                    "客厅正听着。"):
        assert retired not in corpus, retired
    carve = corpus.replace("用英语写一句试试", "")
    assert "用英语写一句" not in carve


# ---------------------------------------------------------------------------
# 3. letterWords — the markdown fallback (source-structure pins; the
# behavior itself is verified by the out-of-repo Node run)


def test_letterwords_renders_the_three_marks() -> None:
    """The three markdown marks segment by one alternation regex, wrap
    the same span.word slicing in strong/em/code, and never touch
    innerHTML; the paper-system styles land once in the letter block."""

    js = _text("webui/components.js")
    assert "const LETTER_MARKS =" in js
    assert (
        r"/(\*\*[^*\s](?:[^*]*[^*\s])?\*\*"
        r"|\*[^*\s](?:[^*]*[^*\s])?\*|`[^`]+`)/;" in js
    )
    assert 'let tag = "em";' in js
    assert 'tag = "strong";' in js
    assert 'tag = "code";' in js
    assert "const el = document.createElement(tag);" in js
    assert "appendWordSpans(el, inner);" in js
    # pure node assembly — the XSS face stays inert
    assert ".innerHTML" not in js
    css = _text("webui/components.css")
    assert ".say strong {" in css
    assert ".say em {" in css
    assert ".say code {" in css


def test_letterwords_plain_path_is_untouched() -> None:
    """Marker-free text rides the same appender as before (the
    even-index path is the old loop body verbatim), and #15's trigger
    face — the edge charset and query normalization — keeps its shape."""

    js = _text("webui/components.js")
    assert "appendWordSpans(frag, seg);" in js
    assert 'span.className = "word";' in js
    assert "span.textContent = part;" in js
    word_edge = next(
        line for line in js.splitlines()
        if line.startswith("const WORD_EDGE_CHARS")
    )
    assert r"*_/\\|=+~^%$#@&" in word_edge
    assert "export function normalizeWordQuery(text) {" in js


# ---------------------------------------------------------------------------
# 4. the letter-flow footnote retirement


def test_the_blocked_line_is_gone_from_the_user_faces() -> None:
    """No ``blockedline`` class, no ``showBlockedNote`` function or call
    site, anywhere in the webui sources, the web server module or the
    spec (the ③ registry row swept in the same knife); a turn that
    teaches nothing leaves the flow silent."""

    for rel in (
        "webui/app.js",
        "webui/screens.css",
        "webui/components.js",
        "webui/components.css",
        "webui/index.html",
        "webui/tokens.css",
        "web.py",
    ):
        body = _text(rel)
        assert "blockedline" not in body, rel
        assert "showBlockedNote" not in body, rel
    spec = _spec_text()
    assert ".blockedline" not in spec
    assert "这一轮没有递短笺" not in spec
