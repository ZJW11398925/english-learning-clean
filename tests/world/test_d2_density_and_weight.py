"""D-2 — the density-and-weight calibration (DEC-OPI-a4cf2d0e…57): the
user's dogfood report (「故事短而无力／平铺直叙／选项后发展极简单」)
answered as spec §4.7's first标定 (「运转密度不做先验定值——
calibratable，用户实测亲调」).

The cut this file pins, no more:

1. **the density constants** — the rhythm law's numbers moved one notch
   up (``MIN_BEATS``/``MAX_BEATS`` 1/2 → 2/3, ``MIN_DAYS``/``MAX_DAYS``
   0/2 → 0/3) and the prompt's own sentences move with them (the task
   region asks for exactly two or three beats spanning 0, 1, 2 or 3
   story days; the old ask is gone, not merely joined); the parser's
   bounds are the same constants — one beat is a refusal now, three is
   inside, four is not; three story days is inside, four is not;
2. **the dramatic-weight teaching** (§4.3 直迁, R2) — the sentence
   verbatim, immediately after the beat-count clause (the adjacency
   pin), unconditional: bare package and the shipped Berrymoor
   package, immersive and directed, each exactly once;
3. **the direction-consequence teaching** (§4.4, R3) — the sentence
   verbatim inside the chosen-direction section, **conditional**: no
   pending row, no bytes (the splice arm recovers the no-pending
   assembly exactly — the conditional-section law's own testable
   form);
4. **the goldens' load-bearing face** — the weight sentence rides the
   very prompt the C1-a golden hashes (the D-2 re-cast is coherent
   across the two faces; the full reverse proof — withdrawing the
   sentence reddens the C1-a hash pin and this pin together — lives in
   the delivery report's mutation arm);
5. **the standing word laws** — both sentences carry no letter word
   (WR-4), no mechanism or pedagogy word (the cs-0 / cs-1 unknowing-
   prose posture), and the immersive prompt still carries no direction
   word at all (the consequence sentence rides the conditional region
   only — wr-10's judgment face is not broken by this cut).

The constants are the calibration's dial: a later calibration moves
them and this file's literals together (the re-cast is conscious — the
judgment face; D-2 is the first version, calibrated off one dogfood
signal).
"""

from __future__ import annotations

from elc.persona.types import ProviderOutput
from elc.platform.types import Err, Ok
from elc.world.narrator import (
    MAX_BEATS,
    MAX_DAYS,
    MIN_BEATS,
    MIN_DAYS,
    WorldNarrator,
    build_narrator_prompt,
)
from elc.world.package import BUILTIN_WORLDS_DIR, load_world_package
from tests.host.test_c1a_chronicle_attribution import _minimal_package
from tests.host.test_cs0_teaching_isolation import MECHANISM_WORDS
from tests.host.test_cs1_character_activation import PEDAGOGY_WORDS
from tests.world.test_wr2_narrator import (
    _beat,
    _beats,
    _package,
    _ScriptedNarrator,
)

#: R2's sentence (§4.3 直迁), as the module constant composes it — this
#: file's own literal, copied by hand, never spliced in from the source:
#: a weakened teaching turns these pins red instead of following along.
WEIGHT_SENTENCE = (
    "Each beat must carry dramatic weight: it must be able to enter"
    " memory and earn an echo — the random may start it, but"
    " continuity must make it feel like fate. Weather and errands"
    " alone are not enough: something must actually happen, change,"
    " or be at stake."
)

#: R3's sentence (§4.4), the same posture.
CONSEQUENCE_SENTENCE = (
    "Honor it as a development, not a mention — the consequences of"
    " that direction land with weight in your beats: a thing that"
    " actually happens because of it, never a one-line footnote."
)

#: The pending choice the conditional pins ride (the wr-10 fixture's
#: own words, so the section's bytes are comparable across files).
_CHOSEN = ("the fair arrives", "Tents dot the cliff meadow.")

#: The chosen-direction section's bytes, hand-copied (the splice arm
#: removes exactly this block to recover the no-pending assembly; the
#: ``meadow..`` double period is the template's own — hint plus the
#: joining period).
_CHOSEN_SECTION = (
    "== The user's chosen direction ==\n\n"
    "The user has chosen where the world goes next: the fair arrives"
    " — Tents dot the cliff meadow.. The world moves in this"
    " direction. Honor it as a development, not a mention — the"
    " consequences of that direction land with weight in your"
    " beats: a thing that actually happens because of it, never a"
    " one-line footnote.\n\n"
)


def _parsed(count: int, days: int) -> Ok | Err:
    """One batch of ``count`` beats, every beat spanning ``days`` —
    the boundary table's own material."""

    narrator = WorldNarrator(
        _ScriptedNarrator(
            ProviderOutput(
                text=_beats(
                    *(
                        _beat(
                            kind=f"beat-{index}",
                            narration=f"Something happened, act {index}.",
                            days=days,
                        )
                        for index in range(count)
                    )
                )
            )
        )
    )
    return narrator.generate(
        package=_package(),
        lore_facts=(),
        recent_narrations=(),
        ui_language="zh",
    )


# ---------------------------------------------------------------------------
# 1 — the density constants, the prompt's sentences, the parser's bounds
# ---------------------------------------------------------------------------


def test_the_density_constants_are_the_calibration() -> None:
    """① 常量新值钉（R1）：2/3 则与 0/3 天——旧值 1/2 与 0/2 全退役。"""

    assert (MIN_BEATS, MAX_BEATS) == (2, 3)
    assert (MIN_DAYS, MAX_DAYS) == (0, 3)


def test_the_prompts_own_sentences_move_with_the_constants() -> None:
    """① prompt 面：任务段改说「恰 2 或 3 则」「跨 0、1、2 或 3 故事日」
    ——旧句不在（不是并存），且两句都与常量同源。评审 F1 处置后：days
    断言不再用手抄字面，改为现场按常量拼装——源回硬编码或常量与句脱钩
    时此钉变红（旧形态在 MAX_DAYS 变异下恒绿，正是 F1 缺口）。"""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    assert "Write exactly 2 or 3 beats." in prompt
    expected_days = (
        "spans "
        + ", ".join(str(day) for day in range(MIN_DAYS, MAX_DAYS))
        + f" or {MAX_DAYS} story days (its ``days``)."
    )
    assert expected_days in prompt
    assert (
        f"Write exactly {MIN_BEATS} or {MAX_BEATS} beats." in prompt
    )
    assert "Write exactly 1 or 2 beats." not in prompt
    assert "spans 0, 1 or 2 story days" not in prompt


def test_the_parser_bounds_are_the_same_constants() -> None:
    """① 解析面边界表（R6 ⑤ 的新边界）：2 与 3 则过、1 与 4 则拒；
    days 3 过、4 拒——拒绝句点名新界（2-3）。"""

    assert isinstance(_parsed(2, 0), Ok)
    assert isinstance(_parsed(3, 3), Ok)
    one = _parsed(1, 0)
    assert isinstance(one, Err)
    assert "2-3" in one.error.message
    four = _parsed(4, 0)
    assert isinstance(four, Err)
    assert "2-3" in four.error.message
    span_over = _parsed(2, 4)
    assert isinstance(span_over, Err)
    assert "days" in span_over.error.message


# ---------------------------------------------------------------------------
# 2 — the dramatic-weight teaching (§4.3 直迁, R2)
# ---------------------------------------------------------------------------


def test_the_weight_teaching_rides_the_task_region_verbatim() -> None:
    """② 逐字 + 位置（R2 的「beats 数句附近」位置钉）：重量句紧随天数短句
    之后、任务区内（== Your task == 与 == The craft laws == 之间），
    且恰一次。"""

    prompt = build_narrator_prompt(_package(), (), (), "zh")
    assert prompt.count(WEIGHT_SENTENCE) == 1
    task_at = prompt.index("== Your task ==")
    weight_at = prompt.index(WEIGHT_SENTENCE)
    craft_at = prompt.index("== The craft laws ==")
    assert task_at < weight_at < craft_at
    # 邻接：数量句的 days 短句与重量句之间零插入。
    assert (
        "or 3 story days (its ``days``). Each beat must carry"
        " dramatic weight:"
    ) in prompt


def test_the_weight_teaching_is_unconditional() -> None:
    """② 无条件在场：裸包与出厂 Berrymoor 包、沉浸与 directed 两模式各
    恰一次。评审 F3 措辞勘正：它**不是**条件区律的例外——它是无条件任务
    段内部的一句（例外的是段本身/整段的无条件注入〔C4 护栏〕，不是区内
    句子）；本钉测的是「无论何形恰一次」。"""

    loaded = load_world_package(BUILTIN_WORLDS_DIR / "berrymoor.json")
    assert isinstance(loaded, Ok), loaded.error.message
    berrymoor = loaded.value
    prompts = (
        build_narrator_prompt(_package(), (), (), "zh"),
        build_narrator_prompt(berrymoor, (), (), "en"),
        build_narrator_prompt(_package(), (), (), "zh", "directed"),
        build_narrator_prompt(berrymoor, (), (), "en", "directed"),
    )
    for prompt in prompts:
        assert prompt.count(WEIGHT_SENTENCE) == 1


# ---------------------------------------------------------------------------
# 3 — the direction-consequence teaching (§4.4, R3, the conditional region)
# ---------------------------------------------------------------------------


def test_the_consequence_teaching_is_conditional() -> None:
    """③ 条件区双向钉：pending 在场 ⇒ 逐字且恰一次（紧接「The world
    moves in this direction.」）；缺席 ⇒ 零字节——撤掉整段恰回无 pending
    的全 prompt 字节（拼接臂）。"""

    without = build_narrator_prompt(_package(), (), (), "zh", "directed")
    assert CONSEQUENCE_SENTENCE not in without
    with_pending = build_narrator_prompt(
        _package(), (), (), "zh", "directed", _CHOSEN
    )
    assert with_pending.count(CONSEQUENCE_SENTENCE) == 1
    assert (
        "The world moves in this direction. Honor it as a development,"
        " not a mention —"
    ) in with_pending
    assert with_pending.replace(_CHOSEN_SECTION, "") == without


def test_the_immersive_default_carries_neither_sentence_of_the_choice() -> None:
    """③ 沉浸形（无 pending）零方向词汇仍成立——后果句只在条件区，
    wr-10 的判决面不被本刀碰坏（重量句在场亦不引入方向词）。"""

    immersive = build_narrator_prompt(_package(), (), (), "zh")
    assert WEIGHT_SENTENCE in immersive
    assert CONSEQUENCE_SENTENCE not in immersive
    assert "direction" not in immersive.lower()
    assert "chosen" not in immersive.lower()


# ---------------------------------------------------------------------------
# 4 — the goldens' load-bearing face
# ---------------------------------------------------------------------------


def test_the_weight_sentence_rides_the_goldens_face() -> None:
    """④ 金针链的 D-2 面：C1-a 金针所哈希的那一形 prompt 逐字带重量句与
    新数量句（句子在哈希之内——撤句即 C1-a 金针与本钉同红；完整反向变异
    由交付报告的变异组承载）。"""

    prompt = build_narrator_prompt(
        _minimal_package(),
        (("loom-key", "The loom sings at dusk."),),
        ("An older line of the story.",),
        "zh",
    )
    assert WEIGHT_SENTENCE in prompt
    assert "Write exactly 2 or 3 beats." in prompt


# ---------------------------------------------------------------------------
# 5 — the standing word laws
# ---------------------------------------------------------------------------


def test_both_sentences_honor_the_standing_word_laws() -> None:
    """⑤ 词面守律：两句零信谈（WR-4）、零机制词、零教学词（cs-0/cs-1 的
    不自知散文姿态）——它们是注入 prompt 的素材，须过全部在册负控。"""

    for lowered in (WEIGHT_SENTENCE.lower(), CONSEQUENCE_SENTENCE.lower()):
        assert "letter" not in lowered
        for word in MECHANISM_WORDS:
            assert word.lower() not in lowered, word
        for word in PEDAGOGY_WORDS:
            assert word.lower() not in lowered, word
