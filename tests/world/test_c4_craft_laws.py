"""C4 — 叙事工艺护栏（域四「叙事工艺指引」的护栏级注入,
DEC-OPI-a4cf2d0e…18）.

Canon (``docs/design/2026-10-08-cognition-and-narrative-quality.md`` 域四):
「叙事者三铁律」（动作不许干打 / 台词分诊 / 详略主次——**语言无关直接
迁移**）+ 「反 AI 味核心负例」（裁断点⑤：注入 ≤10 条最高频，全量 36 条挂
参考位不进 prompt）+ 「护栏 ≤15 行进叙事者节律段」+ 裁断点⑥（英文套语表
v1 先空，待 dogfood 信号）。This cut injects the extracted guardrail into
``build_narrator_prompt``'s task region, **unconditionally** — the one
explicit exception to the conditional-section law every earlier section
obeyed. The pin groups:

1. **unconditional presence and placement** — the guardrail rides every
   prompt (a bare package and the shipped Berrymoor package alike, both
   modes, every parameter combination), exactly once, at the task
   paragraph's tail, before the technical contract (the candidates
   requirement, the shape line, the optional-keys paragraph) — whose
   order never moves;
2. **the laws and the habits, line by line** — the lead-in, the three
   iron laws and the eight anti-AI habits each pinned literally, and the
   eight pinned as exactly eight (≤10 is the canon's bound; eight is the
   canon's own list, no padding);
3. **the fifteen-line bound** — the guardrail's own extent in the built
   prompt is at most 15 lines (machine-checked on the prompt, not only on
   the constants);
4. **the P3 record** — the English stock-phrase blacklist's deferral is
   on the books (the source comment and the module docstring), and the
   guardrail carries no blacklist of its own (v1 is empty by ruling);
5. **the only difference this cut makes** — splice the guardrail out of
   the default prompt and the parent commit's absolute baseline comes
   back byte for byte. This is the in-suite arm of the delivery
   report's reverse proof (withdraw the guardrail ⇒ the lr-3 baseline
   pin and the C1-a golden hash pin both go red);
6. **the guardrail's own words honor the standing prompt laws** — zero
   direction words (wr-10's immersive law), zero letter talk (WR-4's
   two-layer law), zero mechanism words and zero pedagogy words (the
   cs-0 / cs-1 unknowing-prose posture).
"""

from __future__ import annotations

from pathlib import Path

from elc.platform.types import Ok
from elc.world import narrator as narrator_module
from elc.world.narrator import (
    _CRAFT_LAWS_BODY,
    _CRAFT_LAWS_HEADER,
    _CRAFT_SECTION,
    DIRECTION_DIRECTED,
    build_narrator_prompt,
)
from elc.world.package import BUILTIN_WORLDS_DIR, load_world_package
from tests.host.test_cs0_teaching_isolation import MECHANISM_WORDS
from tests.host.test_cs1_character_activation import PEDAGOGY_WORDS
from tests.world.test_wr2_narrator import _package

REPO = Path(__file__).resolve().parents[2]

CRAFT_HEADER = "== The craft laws =="

#: The guardrail's own bytes as this file pins them — the test's own
#: literal, copied from the module constant by hand, never imported: a
#: weakened guardrail in ``src/`` turns these pins red instead of
#: following along.
_CRAFT_SECTION_PINNED = (
    '== The craft laws ==\n\n'
    'Hold every beat of the prose to these three laws:\n\n'
    '1. An action never stands bare: beside what was done, carry at'
    ' least two of — a modifier, a state, a mind, an aftermath.\n\n'
    '2. Triage the short quoted line: keep it when it is character;'
    ' when it is only shorthand, drop the line and carry the beat in'
    ' posture and aftermath.\n\n'
    "3. Keep the weight uneven: ornament at the paragraph's stress"
    ' point alone, and let the rest run plain — when every line is'
    ' dressed, none of them carries.\n\n'
    'Do not fall into these habits: empty grandiosity; an elevating'
    ' formula where the beat should simply end; inflation through'
    ' degree adverbs; more than one metaphor in a single paragraph; an'
    ' emotion named outright where a body would show it; scenery that'
    ' no one in the beat notices; every paragraph cut to the same'
    ' length; a log that keeps order but never emphasis.\n\n'
)

#: The canon's three iron laws, one literal each (域四·叙事者三铁律 —
#: 动作不许干打 / 台词分诊 / 详略主次, stated as operative instructions).
_LAW_A_BARE = (
    "1. An action never stands bare: beside what was done, carry at"
    " least two of — a modifier, a state, a mind, an aftermath."
)
_LAW_B_TRIAGE = (
    "2. Triage the short quoted line: keep it when it is character;"
    " when it is only shorthand, drop the line and carry the beat in"
    " posture and aftermath."
)
_LAW_C_WEIGHT = (
    "3. Keep the weight uneven: ornament at the paragraph's stress"
    " point alone, and let the rest run plain — when every line is"
    " dressed, none of them carries."
)

#: The eight anti-AI habits (裁断点⑤：≤10 条最高频；八条即规范抽提的全部，
#: 不加垫）。Pinned item by item so a silent drop or a rewording lands red.
_HABIT_ITEMS = (
    "empty grandiosity",
    "an elevating formula where the beat should simply end",
    "inflation through degree adverbs",
    "more than one metaphor in a single paragraph",
    "an emotion named outright where a body would show it",
    "scenery that no one in the beat notices",
    "every paragraph cut to the same length",
    "a log that keeps order but never emphasis",
)

_HABITS_LEAD = "Do not fall into these habits: "

#: The parent commit's (c670d5d) absolute default prompt, machine-read
#: off that commit's own ``_A_BASELINE`` — the pre-C4 bytes the splice
#: arm recovers. An absolute literal on purpose: no part of it follows a
#: weakening of this cut's source change.
_PRE_C4_BASELINE = (
    'You are the narrator of a small fictional world.\n\n'
    'Write what happens there next, as a novel would.\n\n'
    "The world moves on its own — weather, seasons, the town's"
    " rhythms, the cast's lives off-stage. It does not react to any"
    " correspondence: letters belong to the penpal layer, not to the"
    " world's narration.\n\n"
    '== The world ==\n\n'
    'Calendar is a small harbour town on a cold coast.\n\n'
    'The boats come in with the morning tide.\n\n'
    'Cast: Nell Alder\n\n'
    "Cast ids (a beat's ``participants`` names these ids and no"
    ' others): persona-nell = Nell Alder\n\n'
    "== The world's established facts ==\n\n"
    '- (Nothing is settled yet.)\n\n'
    '== The story so far ==\n\n'
    '- (The chronicle is empty — this is where the story begins.)\n\n'
    '== Your task ==\n\n'
    "Write the world's next beats — whatever happens next in the"
    " world's own life. Novel prose, small-town voice. Stay"
    " consistent with everything above; never repeat what already"
    " happened. Write exactly 1 or 2 beats. Each beat is one to three"
    " sentences of narration and spans 0, 1 or 2 story days (its"
    " ``days``).\n\n"
    'The narration is written in Chinese (中文).\n\n'
    'Answer with strict JSON only — no prose outside it: {"beats":'
    ' [{"kind": "<slug>", "narration": "<...>", "days": 0}]} The'
    ' ``kind`` is a short slug: lowercase letters, digits and hyphens'
    ' only, at most 32 characters.\n\n'
    'Beside the required ``kind``, ``narration`` and ``days``, each'
    " beat may carry two optional keys. ``effects`` is the beat's"
    ' state-effect proposals — an array, each element exactly {"key":'
    ' <the state key>, "statement": <what becomes true>}; include it'
    ' only when the beat genuinely changes what is true, and leave it'
    ' out when the beat settles nothing. ``participants`` is an array'
    ' of the cast ids present in or taking part in the beat — drawn'
    ' from the roster above and nothing else; leave it out when none'
    ' do.'
)


def _berrymoor():
    """The shipped world package (voice library, residents, initial
    lines — the rich face the guardrail must ride too)."""

    loaded = load_world_package(BUILTIN_WORLDS_DIR / "berrymoor.json")
    assert isinstance(loaded, Ok), loaded.error.message
    return loaded.value


def _rich_prompt() -> str:
    """One call shape carrying every conditional section at once (the
    widest prompt the builder can compose)."""

    return build_narrator_prompt(
        _berrymoor(),
        (("loom-key", "The loom sings at dusk."),),
        ("An older line of the story.",),
        "zh",
        DIRECTION_DIRECTED,
        ("the fair arrives", "Tents dot the cliff meadow."),
        2,
        "a storm rolls in from the west",
        (("loom-key", "The loom sings at dusk."),),
        ("persona-nell-alder", "She read the letter."),
        (("line-1", "The harbour debt", "the debt is settled"),),
    )


# ---------------------------------------------------------------------------
# 1 — unconditional presence and placement
# ---------------------------------------------------------------------------


def test_the_guardrail_rides_a_bare_package_and_the_shipped_one() -> None:
    """① 无条件在场：裸包（wr-2 的 _package）与 Berrymoor 包两态都带护栏
    节，且各恰一次——本节不依赖任何包素材（与 C3 声区的条件纪律相反的
    一处，规范裁定的显式例外）。"""

    bare = build_narrator_prompt(_package(), (), (), "zh")
    assert bare.count(CRAFT_HEADER) == 1
    rich = _rich_prompt()
    assert rich.count(CRAFT_HEADER) == 1


def test_the_guardrail_sits_at_the_task_tail_before_the_contract() -> None:
    """位置不变量（R1）：护栏节在任务段尾（任务段文本之后）、技术契约之前
    ——「Direction candidates:」要求段、JSON 形状行、可选键段三者恒在护栏
    之后，顺序不动。"""

    rich = _rich_prompt()
    task_at = rich.index("== Your task ==")
    craft_at = rich.index(CRAFT_HEADER)
    task_tail_at = rich.index(" ``days``).")
    candidates_at = rich.index("Direction candidates:")
    chosen_at = rich.index("== The user's chosen direction ==")
    written_at = rich.index("== The user's written direction ==")
    shape_at = rich.index("Answer with strict JSON only")
    optional_at = rich.index("Beside the required ``kind``")
    assert task_at < task_tail_at < craft_at
    assert craft_at < candidates_at < chosen_at < written_at
    assert craft_at < shape_at < optional_at
    # The guardrail is the task region's last instruction before the
    # contract: nothing but blank-line joins sits between them.
    assert rich[task_tail_at:craft_at].endswith("``days``).\n\n")


# ---------------------------------------------------------------------------
# 2 — the laws and the habits, line by line
# ---------------------------------------------------------------------------


def test_the_guardrail_is_byte_for_byte_the_pinned_section() -> None:
    """常量字节同一：模块常量与本节钉的逐字副本相等（护栏节是把关面的
    唯一付款人——任一句改动即此处红）。"""

    assert _CRAFT_SECTION == _CRAFT_SECTION_PINNED
    assert _CRAFT_LAWS_HEADER == CRAFT_HEADER
    assert _CRAFT_SECTION == (
        _CRAFT_LAWS_HEADER
        + "\n\n"
        + "\n\n".join(_CRAFT_LAWS_BODY)
        + "\n\n"
    )


def test_the_three_iron_laws_ride_verbatim() -> None:
    """② 三铁律逐条字面：引导句与三条铁律各按规范抽提的措辞在场
    （动作不许干打 / 台词分诊 / 详略主次）。"""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    assert "Hold every beat of the prose to these three laws:" in prompt
    assert _LAW_A_BARE in prompt
    assert _LAW_B_TRIAGE in prompt
    assert _LAW_C_WEIGHT in prompt


def test_the_eight_habits_ride_as_exactly_eight() -> None:
    """② 八条负例：逐条在场，且**恰八条**（裁断点⑤的 ≤10 上限内按规范
    抽提落定——规范八条已够，不加垫；钉一个「变成九条/少一条」都红）。"""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    for item in _HABIT_ITEMS:
        assert item in prompt, item
    habits = prompt.split(_HABITS_LEAD, 1)[1].split("\n\n", 1)[0]
    items = habits.rstrip(".").split("; ")
    assert len(items) == 8, items
    assert tuple(items) == _HABIT_ITEMS
    assert len(set(items)) == 8


# ---------------------------------------------------------------------------
# 3 — the fifteen-line bound
# ---------------------------------------------------------------------------


def test_the_guardrail_fits_the_fifteen_line_bound() -> None:
    """③ 行数 ≤15 机检（域四「护栏 ≤15 行进叙事者节律段」）：在**真
    prompt** 上读护栏节的本体（头 + 其后的行，至八条负例句末），行数
    ≤15；常量口径同检。"""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    start = prompt.index(CRAFT_HEADER)
    end = prompt.index(_HABIT_ITEMS[-1]) + len(_HABIT_ITEMS[-1]) + 1
    extent = prompt[start:end]
    assert extent == _CRAFT_SECTION.rstrip("\n\n")
    lines = extent.count("\n\n") + 1
    assert lines <= 15, lines
    assert len(_CRAFT_LAWS_BODY) + 1 <= 15


# ---------------------------------------------------------------------------
# 4 — the P3 record
# ---------------------------------------------------------------------------


def test_the_english_stock_phrase_blacklist_is_deferred_on_the_books() -> None:
    """④ P3 留痕：英文套语表 v1 先空（域四裁断点⑥）——源码注释与模块
    docstring 各有一句后置声明；护栏节自身零套语表（v1 无内容，不写）。"""

    source = (
        REPO / "src" / "elc" / "world" / "narrator.py"
    ).read_text(encoding="utf-8")
    assert "英文套语表 v1 先空——待英文 dogfood 信号补（P3" in source
    doc = narrator_module.__doc__ or ""
    assert "English stock-phrase" in doc and "P3" in doc
    assert "blacklist" not in _CRAFT_SECTION.lower()


# ---------------------------------------------------------------------------
# 5 — the only difference this cut makes
# ---------------------------------------------------------------------------


def test_the_guardrail_is_the_only_difference_this_cut_makes() -> None:
    """⑤ 本刀唯一之差（库内承重臂）：默认 prompt 去掉护栏节（恰一次出现）
    即父提交（c670d5d）的绝对基线逐字回来——护栏之外一字未动；rich 形
    拼接后，任务段尾紧接候选要求段（无第三插入点）。"""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    assert prompt.count(_CRAFT_SECTION) == 1
    assert prompt.replace(_CRAFT_SECTION, "") == _PRE_C4_BASELINE
    rich = _rich_prompt()
    assert rich.count(_CRAFT_SECTION) == 1
    spliced = rich.replace(_CRAFT_SECTION, "")
    assert "``days``).\n\nDirection candidates:" in spliced
    assert spliced.count(CRAFT_HEADER) == 0


# ---------------------------------------------------------------------------
# 6 — the guardrail's own words honor the standing prompt laws
# ---------------------------------------------------------------------------


def test_the_guardrail_honors_every_standing_word_law() -> None:
    """⑥ 词面守律：护栏节是无条件注入的 prompt 素材，故它自己必须过全部
    在册负控——零 direction 词（wr-10 沉浸律）、零信谈（WR-4 双层律）、
    零机制词与零教学词（cs-0/cs-1 的不自知散文姿态）。"""

    lowered = _CRAFT_SECTION.lower()
    assert "direction" not in lowered
    assert "letter" not in lowered
    assert "step" not in lowered
    assert '"stop"' not in _CRAFT_SECTION
    assert "The letter ==" not in _CRAFT_SECTION
    for word in MECHANISM_WORDS:
        assert word.lower() not in lowered, word
    for word in PEDAGOGY_WORDS:
        assert word.lower() not in lowered, word
