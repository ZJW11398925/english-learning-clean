"""P9-3 ① — the PreDeliveryGuard's pure face.

§15's seven conditions, the §16/§21.1 two-word decision, the reason-code
vocabulary and the module's own declarations, driven as values. Nothing here
touches a database: the guard is a pure function of seven facts and this file
is what makes that a checkable claim rather than a hope (the AST pins at the
bottom are the other half — the module imports no DB machinery and reads no
clock).

The naming rule the whole file leans on: §15's condition names **are** the
reason codes and the fact fields are those names lower-cased, so a condition
cannot exist without its field, its code, or its unchecked spelling — three
lists that would otherwise drift are one declaration read three ways
(``CONDITION_ATTRIBUTES``).
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

from elc.runtime.pre_delivery_guard import (
    CONDITION_ATTRIBUTES,
    UNCHECKED_PREFIX,
    GuardCondition,
    PlannerConstraintSource,
    PreDeliveryDecision,
    PreDeliveryGuardFacts,
    checked_lineage_version_of,
    guard_result_id_of,
    guard_verdict,
    unchecked_code_of,
)
from tests.conftest import REPO_ROOT, SRC_ROOT

MODULE = SRC_ROOT / "runtime" / "pre_delivery_guard.py"
MIGRATION = REPO_ROOT / "migrations" / "0018_delivery_records.sql"

#: §15's seven conditions in the module's reading order. Pinned as a literal so
#: a cut that renames, reorders, drops or adds one has to change this line too
#: (the enum's own order is derived from the declaration and cannot witness a
#: move).
CONDITION_ORDER = (
    "CONVERSATION_INACTIVE",
    "ACTION_CANCELLED",
    "ACTION_SUPERSEDED",
    "TEACHING_LOCK_INVALID",
    "NEW_TARGET_SUPPRESSED",
    "JUST_CHAT_HARD_SWITCH",
    "LINEAGE_MISMATCH",
)


def facts(**overrides: bool | None) -> PreDeliveryGuardFacts:
    """The seven facts, all ``False`` unless named — the clean read."""

    bag: dict[str, bool | None] = {
        condition.value.lower(): False for condition in GuardCondition
    }
    bag.update(overrides)
    return PreDeliveryGuardFacts(**bag)  # type: ignore[arg-type]


def guard_source() -> str:
    return MODULE.read_text(encoding="utf-8")


# -- ① the vocabulary ----------------------------------------------------------


def test_the_seven_conditions_are_the_seven_facts_and_nothing_else() -> None:
    """Exactly seven, in §15's reading order, one field per condition.

    Three declarations are checked against each other: the enum, the fact
    dataclass's fields (in declaration order) and the derived attribute map. A
    cut that adds a condition without its field — or a field with no condition
    — fails here rather than at the first delivery.
    """

    assert [condition.value for condition in GuardCondition] == list(
        CONDITION_ORDER
    )
    assert len(GuardCondition) == 7
    assert [field.name for field in dataclasses.fields(PreDeliveryGuardFacts)] == [
        condition.value.lower() for condition in GuardCondition
    ]
    assert {
        condition: condition.value.lower() for condition in GuardCondition
    } == CONDITION_ATTRIBUTES


def test_unchecked_code_of_prefixes_the_condition_it_cannot_answer() -> None:
    for condition in GuardCondition:
        assert (
            unchecked_code_of(condition)
            == f"{UNCHECKED_PREFIX}{condition.value}"
        )
    assert UNCHECKED_PREFIX == "UNCHECKED_"


# -- ② the three-way verdict ---------------------------------------------------


def test_all_false_is_valid_with_no_reason_codes() -> None:
    """Every fact read and none holding: the clean answer, and — deliberately —
    an empty code list. "Nothing was wrong" is not a code."""

    verdict = guard_verdict(facts())
    assert verdict.decision == PreDeliveryDecision.VALID.value
    assert verdict.reason_codes == ()
    assert verdict.invalidating_conditions == ()
    assert verdict.unchecked_conditions == ()


@pytest.mark.parametrize("condition", list(CONDITION_ORDER))
def test_any_true_invalidates_and_its_own_name_is_the_reason_code(
    condition: str,
) -> None:
    """Each condition, one at a time: the decision flips, the code is the
    condition's name, and no other code appears — so a rename has to reach the
    row's content, not just the enum."""

    verdict = guard_verdict(facts(**{condition.lower(): True}))
    assert verdict.decision == PreDeliveryDecision.INVALIDATE_ACTION.value
    assert verdict.reason_codes == (condition,)
    assert verdict.invalidating_conditions == (condition,)
    assert verdict.unchecked_conditions == ()


@pytest.mark.parametrize("condition", list(CONDITION_ORDER))
def test_none_is_recorded_and_never_invalidates(condition: str) -> None:
    """The distinction the tri-state exists for: an unread fact is *not* a
    failure and *not* a pass — the row says which check could not run, and the
    delivery still goes out."""

    verdict = guard_verdict(facts(**{condition.lower(): None}))
    assert verdict.decision == PreDeliveryDecision.VALID.value
    assert verdict.reason_codes == (unchecked_code_of(GuardCondition(condition)),)
    assert verdict.invalidating_conditions == ()
    assert verdict.unchecked_conditions == (condition,)


def test_all_none_is_valid_and_names_every_unchecked_condition() -> None:
    """A delivery whose seven facts could none be read: still valid, and the
    row carries all seven unchecked codes in reading order — an audit reader
    sees an uncovered check, never an error and never a silent pass."""

    verdict = guard_verdict(facts(**{name.lower(): None for name in CONDITION_ORDER}))
    assert verdict.decision == PreDeliveryDecision.VALID.value
    assert verdict.reason_codes == tuple(
        f"{UNCHECKED_PREFIX}{name}" for name in CONDITION_ORDER
    )
    assert verdict.unchecked_conditions == CONDITION_ORDER


def test_the_codes_come_out_in_condition_order_not_grouped_by_kind() -> None:
    """Interleaving pin: the codes follow the condition order, so a reader can
    diff two rows as a sentence. A grouping-by-kind implementation (all codes
    first, then all unchecked) fails here."""

    verdict = guard_verdict(
        facts(
            conversation_inactive=True,
            action_cancelled=None,
            action_superseded=True,
            teaching_lock_invalid=None,
            lineage_mismatch=True,
        )
    )
    assert verdict.reason_codes == (
        "CONVERSATION_INACTIVE",
        "UNCHECKED_ACTION_CANCELLED",
        "ACTION_SUPERSEDED",
        "UNCHECKED_TEACHING_LOCK_INVALID",
        "LINEAGE_MISMATCH",
    )
    assert verdict.invalidating_conditions == (
        "CONVERSATION_INACTIVE",
        "ACTION_SUPERSEDED",
        "LINEAGE_MISMATCH",
    )
    assert verdict.unchecked_conditions == (
        "ACTION_CANCELLED",
        "TEACHING_LOCK_INVALID",
    )


def test_unchecked_never_decides_even_beside_a_true_fact() -> None:
    """One true fact and six unread ones: the decision is the true fact's, and
    the six are still recorded — neither half swallows the other."""

    verdict = guard_verdict(
        facts(
            action_cancelled=True,
            conversation_inactive=None,
            action_superseded=None,
            teaching_lock_invalid=None,
            new_target_suppressed=None,
            just_chat_hard_switch=None,
            lineage_mismatch=None,
        )
    )
    assert verdict.decision == PreDeliveryDecision.INVALIDATE_ACTION.value
    assert verdict.reason_codes == (
        "UNCHECKED_CONVERSATION_INACTIVE",
        "ACTION_CANCELLED",
        "UNCHECKED_ACTION_SUPERSEDED",
        "UNCHECKED_TEACHING_LOCK_INVALID",
        "UNCHECKED_NEW_TARGET_SUPPRESSED",
        "UNCHECKED_JUST_CHAT_HARD_SWITCH",
        "UNCHECKED_LINEAGE_MISMATCH",
    )


# -- ③ the decision vocabulary -------------------------------------------------


def test_the_decision_vocabulary_is_the_two_words_the_schema_freezes() -> None:
    """§16's output words and §21.1's inline block, against migration 0018's
    CHECK: the enum, the schema and the module's carrier text are the same two
    words, so a third word would have to change the migration to exist."""

    assert [member.value for member in PreDeliveryDecision] == [
        "VALID",
        "INVALIDATE_ACTION",
    ]
    migration = MIGRATION.read_text(encoding="utf-8")
    block = migration.split(
        "CREATE TABLE IF NOT EXISTS pre_delivery_guard_result (", 1
    )[1].split(");", 1)[0]
    assert "CHECK (decision IN ('VALID', 'INVALIDATE_ACTION'))" in block
    for member in PreDeliveryDecision:
        assert member.value in block


def test_every_verdict_spells_one_of_the_two_words() -> None:
    """A sweep over the fact space's corners (4 782 969 combinations is the
    whole space; the corners are what can break a decision rule): the decision
    is always one of the two words and the codes never contain a bare
    decision word."""

    words = {member.value for member in PreDeliveryDecision}
    answers: tuple[bool | None, ...] = (True, False, None)
    for first in answers:
        for second in answers:
            for third in answers:
                verdict = guard_verdict(
                    facts(
                        conversation_inactive=first,
                        action_cancelled=second,
                        action_superseded=third,
                        teaching_lock_invalid=first,
                        new_target_suppressed=second,
                        just_chat_hard_switch=third,
                        lineage_mismatch=first,
                    )
                )
                assert verdict.decision in words
                assert "VALID" not in verdict.reason_codes


# -- ④ the row's identity and the lineage version ------------------------------


def test_the_guard_row_id_is_keyed_by_the_action_and_stable() -> None:
    """One check per action: the same action spells the same id (the §23
    re-entry re-submits the same identity), and two actions never collide."""

    assert guard_result_id_of("ga-a") == guard_result_id_of("ga-a")
    assert guard_result_id_of("ga-a") != guard_result_id_of("ga-b")
    assert guard_result_id_of("ga-a").startswith("pdg-")
    assert "ga-a" in guard_result_id_of("ga-a")


def test_the_lineage_version_names_the_cycle_and_the_turn_state_version() -> None:
    assert (
        checked_lineage_version_of(
            decision_cycle_id="dcy-turn-1", turn_state_version=4
        )
        == "dcy-turn-1@4"
    )
    assert (
        checked_lineage_version_of(decision_cycle_id=None, turn_state_version=1)
        == "no-cycle@1"
    )
    assert checked_lineage_version_of(
        decision_cycle_id="dcy-turn-1", turn_state_version=4
    ) == checked_lineage_version_of(
        decision_cycle_id="dcy-turn-1", turn_state_version=4
    )


# -- ⑤ the values are values ---------------------------------------------------


def test_the_facts_are_frozen_and_a_verdict_is_a_function_of_them() -> None:
    """Reading 6 as a check: facts cannot move under a verdict (the dataclass is
    frozen), and judging the same facts twice gives the same verdict — the
    property that makes the §21.1 re-submission a replay rather than a
    conflict."""

    given = facts(action_superseded=True, just_chat_hard_switch=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        given.action_superseded = False  # type: ignore[misc]
    assert guard_verdict(given) == guard_verdict(given)
    assert guard_verdict(given).facts is given


def test_all_seven_facts_are_required() -> None:
    """§15's list is the fact set: a caller that cannot read one says ``None``
    rather than omitting it, and the dataclass enforces that (no defaults, so a
    six-fact construction is a ``TypeError``)."""

    with pytest.raises(TypeError):
        PreDeliveryGuardFacts(  # type: ignore[call-arg]
            conversation_inactive=False,
            action_cancelled=False,
            action_superseded=False,
            teaching_lock_invalid=False,
            new_target_suppressed=False,
            just_chat_hard_switch=False,
        )


def test_the_verdict_is_a_value_and_its_properties_are_the_facts_derived() -> None:
    """The verdict object itself is comparable by value and its two properties
    are *derivations* of the facts, not a second answer: a reader that flips a
    fact gets a different verdict, and two readings of the same facts compare
    equal (no hidden state, no clock)."""

    first = guard_verdict(facts(lineage_mismatch=True))
    second = guard_verdict(facts(lineage_mismatch=True))
    third = guard_verdict(facts(lineage_mismatch=None))
    assert first == second
    assert first != third
    assert first.invalidating_conditions == ("LINEAGE_MISMATCH",)
    assert third.invalidating_conditions == ()
    assert third.unchecked_conditions == ("LINEAGE_MISMATCH",)


def test_the_decision_is_invalidate_if_and_only_if_some_fact_is_true() -> None:
    """A sampled sweep over the whole fact space's shape (all three answers on
    every condition is 3**7 = 2187 readings): the decision is exactly "some
    fact is True", and the code list is exactly the True and None ones — no
    reading slips between the rule and the verdict."""

    answers: tuple[bool | None, ...] = (True, False, None)
    for index in range(len(answers) ** 7):
        digits = []
        value = index
        for _ in range(7):
            digits.append(answers[value % len(answers)])
            value //= len(answers)
        given = facts(
            **{
                name.lower(): answer
                for name, answer in zip(CONDITION_ORDER, digits, strict=True)
            }
        )
        verdict = guard_verdict(given)
        expected_codes = tuple(
            name if answer is True else f"{UNCHECKED_PREFIX}{name}"
            for name, answer in zip(CONDITION_ORDER, digits, strict=True)
            if answer is not False
        )
        assert verdict.reason_codes == expected_codes
        assert verdict.decision == (
            PreDeliveryDecision.INVALIDATE_ACTION.value
            if any(answer is True for answer in digits)
            else PreDeliveryDecision.VALID.value
        )


# -- ⑥ the port and the module's declared posture ------------------------------


def test_the_constraint_source_asks_for_exactly_the_two_reads() -> None:
    """The guard's two constraint legs read §9 through one narrow port, and the
    real authority satisfies it — so a wiring that hands over something else
    fails the protocol check rather than the first delivery."""

    from elc.user_config.controller import UserConfigController

    methods = {
        name
        for name, value in vars(PlannerConstraintSource).items()
        if not name.startswith("_") and callable(value)
    }
    assert methods == {
        "get_planner_constraint_view",
        "active_constraints_for_target",
    }
    for name in methods:
        assert callable(getattr(UserConfigController, name, None)), name


def test_the_module_registers_its_carriers_and_its_readings() -> None:
    """Registration-style pin: the seven conditions, the carrier table and the
    declared readings are in the module's own text. This is what makes the
    controller's assembly and this module's claims one declaration instead of
    two (the docstrings' Revisit lines are the re-open conditions)."""

    text = guard_source()
    for condition in CONDITION_ORDER:
        assert condition in text, condition
    assert "V1 carrier" in text
    assert text.count("Revisit:") >= 7
    flat = " ".join(text.split())
    assert "只检查 hard invalidation" in flat
    assert "不重新跑 Planner utility" in flat


def test_the_module_reads_no_database_and_no_clock() -> None:
    """The AST half of "pure": no sqlite3 / elc.platform.db import, no
    execute-family call surface, no SQL statement literal and no clock read.
    (tests/architecture Gate 2 makes the same argument for the whole runtime
    package; this pin keeps the guard's own module from being the exception the
    package-level scan would have to be relaxed for.)"""

    tree = ast.parse(guard_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "sqlite3"
                assert not alias.name.startswith("elc.platform.db")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module != "sqlite3"
            assert not module.startswith("elc.platform.db")
            assert module not in {"time", "datetime"}
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            }
            assert node.func.attr not in {"now", "time", "utcnow", "monotonic"}
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            for marker in ("insert into", "update ", "delete from", "create table"):
                assert marker not in lowered, marker


def test_the_module_declares_which_face_is_wired_and_which_is_not() -> None:
    """Reading 7 registered rather than implied: the streamed path is wired and
    the buffered face is named as not yet wired, in the module's own words."""

    text = " ".join(guard_source().split())
    assert "the buffered path does **not** run it yet" in text
    assert "GUARDED_STREAM" in text
    assert "BUFFERED_VALIDATED" in text
