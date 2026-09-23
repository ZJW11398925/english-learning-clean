"""P7-3 ②③④⑤ — the PlanningLedger's pure core, and every number in it.

The core is one event vocabulary, two rules §20 states in prose, an
obligation's eleven columns and the three declared ladders/rates. Each part is
pinned against the document or the frozen asset it comes from, and the three
numbers **no** document carries are pinned as *declared* — with a probe that
shows the asset really does not carry them, so "declared" is a checked claim
rather than an excuse.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from elc.planner import kernel
from elc.planner.candidates import FACTOR_BAND_VALUES
from elc.planner.ledger import (
    DEBT_REPAID_PER_ENGAGEMENT,
    DEBT_REPAID_PER_SERVING,
    EVENT_EFFECTS,
    EXPOSURE_EVENTS,
    LEDGER_EVENTS,
    LEDGER_VALUE_RANGE,
    OVEREXPOSURE_RUNGS,
    OVEREXPOSURE_WINDOW_DAYS,
    PLANNING_LEDGER_MODEL_VERSION,
    PLANNING_LEDGER_STORAGE,
    PLANNING_LEDGER_STORAGE_REVISIT,
    SERVICE_STATE_RUNGS,
    SERVING_EVENTS,
    CoverageObligation,
    EventEffect,
    LedgerEvent,
    LedgerInputError,
    LedgerStorage,
    LedgerWindow,
    ObligationScope,
    PauseReason,
    PlanningLedger,
    TargetLedgerRow,
    accrue,
    apply_ledger_event,
    coverage_service_state_of,
    direct_obligation_of,
    engage,
    overexposure_band_of,
    overexposure_of,
    serve,
)
from elc.platform.types import GoalModality

from .conftest import (
    BASELINES,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    DOCS_ROOT,
    canonical_lines,
    source_text,
)

DATA_MODEL = "DATA_MODEL.md"
RUNTIME_ARCHITECTURE = "RUNTIME_ARCHITECTURE.md"
PLANNER_PROFILE = "planner/planner_reference_profile_v1_1.json"
GOLDEN_REFERENCE = "golden/planner_reference_v1_1.py"
MODALITY_REFERENCE = "modality/modality_scope_reference_v1.py"
MODALITY_POLICY = "modality/modality_scope_policy_v1.json"
TARGET = "res-hedge-i-think"
OTHER_TARGET = "cap-eval-hedged-opinion"
BEFORE_WINDOW = "2026-09-01T09:00:00+00:00"


def _load_reference(relative: str, name: str) -> Any:
    """One frozen baseline module, loaded from its pinned file."""

    path = BASELINES / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # keep the baseline tree byte-identical
    spec.loader.exec_module(module)
    return module


def _json(relative: str) -> dict:
    return json.loads((BASELINES / relative).read_text(encoding="utf-8"))


def obligation(
    key: str = "co-1",
    *,
    target: str = TARGET,
    debt: float = 1.0,
    paused: bool = False,
    reason: str | None = None,
    scope: str = "TARGET",
    goal_id: str | None = None,
    last_served_at: str | None = None,
    last_engaged_at: str | None = None,
) -> CoverageObligation:
    """One obligation; ``paused`` fills the canonical pause word."""

    return CoverageObligation(
        obligation_key=key,
        scope_type=scope,
        target_or_family_id=target,
        goal_id=goal_id,
        window_start=DAY_ONE,
        window_end=DAY_THREE,
        debt_value=debt,
        accrual_paused=paused,
        pause_reason=(
            PauseReason.UNAVAILABLE_IN_CURRENT_RUNTIME.value
            if paused and reason is None
            else reason
        ),
        last_served_at=last_served_at,
        last_engaged_at=last_engaged_at,
    )


def row(
    key: str = TARGET,
    *,
    events: tuple[tuple[LedgerEvent, str], ...] = (),
    window: LedgerWindow | None = None,
    probe_counts: int = 0,
    review_offers: int = 0,
) -> TargetLedgerRow:
    """One ledger row, built by recording its events in order."""

    built = TargetLedgerRow(
        target_key=key,
        overexposure_window=window,
        probe_counts=probe_counts,
        review_offers=review_offers,
    )
    for event, at in events:
        built = built.record(event, at=at)
    return built


# ---------------------------------------------------------------------------
# ② the five events, and the two rules as behaviour
# ---------------------------------------------------------------------------


def test_the_five_event_words_are_the_runtime_architecture_block() -> None:
    """RA §20's block, character for character."""

    block = list(canonical_lines(RUNTIME_ARCHITECTURE, "## 20. PlanningLedger"))
    assert block == [
        "candidate_selected",
        "teaching_presented",
        "hint_presented",
        "reveal_presented",
        "user_skip",
    ]
    assert [event.value for event in LEDGER_EVENTS] == block


def test_the_two_original_rules_are_quoted_in_the_module() -> None:
    """The two sentences §20 writes after the block, verbatim in the module
    that makes them behaviour."""

    text = source_text("src/elc/planner/ledger.py")
    assert "SELECT != exposure" in text
    assert "CoverageDebt 不因 selection 自动偿还" in text


def test_the_effect_table_is_total_and_has_all_three_words() -> None:
    assert set(EVENT_EFFECTS) == set(LEDGER_EVENTS)
    assert set(EVENT_EFFECTS.values()) == set(EventEffect)
    assert EXPOSURE_EVENTS == (
        LedgerEvent.TEACHING_PRESENTED,
        LedgerEvent.HINT_PRESENTED,
        LedgerEvent.REVEAL_PRESENTED,
    )
    assert SERVING_EVENTS == (LedgerEvent.TEACHING_PRESENTED,)
    for event in LEDGER_EVENTS:
        if event not in EXPOSURE_EVENTS:
            assert EVENT_EFFECTS[event] is EventEffect.NEITHER, event


def test_a_selection_neither_exposes_nor_repays() -> None:
    """The first original rule, as a record: a selection moves no debt and
    stamps no presentation."""

    before = obligation(debt=1.0, last_served_at=None)
    outcome = apply_ledger_event(
        before, LedgerEvent.CANDIDATE_SELECTED, at=DAY_TWO
    )
    assert outcome.obligation == before
    assert outcome.changed is False
    assert "SELECT != exposure" in outcome.reason
    assert "repay" in outcome.reason


def test_only_a_teaching_presentation_serves_the_obligation() -> None:
    before = obligation(debt=1.0)
    outcome = apply_ledger_event(
        before, LedgerEvent.TEACHING_PRESENTED, at=DAY_TWO
    )
    assert outcome.changed is True
    assert outcome.obligation.last_served_at == DAY_TWO
    assert outcome.obligation.debt_value == 1.0 - DEBT_REPAID_PER_SERVING
    assert outcome.obligation.last_engaged_at is None


def test_a_hint_and_a_reveal_expose_without_serving() -> None:
    """What the two lighter words mean: a delivery that withholds part of the
    teaching does not repay a coverage obligation."""

    before = obligation(debt=1.0)
    for event in (LedgerEvent.HINT_PRESENTED, LedgerEvent.REVEAL_PRESENTED):
        outcome = apply_ledger_event(before, event, at=DAY_TWO)
        assert outcome.changed is False, event
        assert outcome.obligation.debt_value == 1.0, event
        assert outcome.obligation.last_served_at is None, event
        assert "exposure, not a service" in outcome.reason, event


def test_a_skip_is_a_rejection_and_not_engagement() -> None:
    before = obligation(debt=1.0)
    outcome = apply_ledger_event(before, LedgerEvent.USER_SKIP, at=DAY_TWO)
    assert outcome.changed is False
    assert outcome.obligation == before
    assert "rejection" in outcome.reason


def test_engagement_comes_as_a_fact_because_no_event_word_carries_it() -> None:
    """§20's five words have no engagement word, so engagement is a fact from
    outside the vocabulary — and this is the one place it stamps the column."""

    assert not any(
        "engage" in event.value for event in LEDGER_EVENTS
    )
    before = obligation(debt=0.5)
    engaged = engage(before, at=DAY_TWO)
    assert engaged.last_engaged_at == DAY_TWO
    assert engaged.debt_value == max(0.0, 0.5 - DEBT_REPAID_PER_ENGAGEMENT)
    assert engaged.debt_value == 0.0
    assert engaged.last_served_at is None


# ---------------------------------------------------------------------------
# ②③ the obligation's columns and the pause rule
# ---------------------------------------------------------------------------


def test_the_obligation_fields_are_the_canonical_sub_block() -> None:
    """§13's eleven field lines, in the document's order, with the ``?`` marks
    read as optional columns — under the section's own opening rule, which is
    prose before the block and is quoted by the module that implements it."""

    section = (DOCS_ROOT / DATA_MODEL).read_text(encoding="utf-8")
    assert "### PlanningLedger\n\n不记录 mastery。" in section
    block = list(canonical_lines(DATA_MODEL, "### PlanningLedger"))
    assert block[0] == "target/family last_selected_at"
    at = block.index("coverage_obligations[]")
    sub_block = block[at + 1 : at + 12]
    canonical = [line.removesuffix("?") for line in sub_block]
    assert canonical == [
        "obligation_key",
        "scope_type",
        "target_or_family_id",
        "goal_id",
        "window_start",
        "window_end",
        "debt_value",
        "accrual_paused",
        "pause_reason",
        "last_served_at",
        "last_engaged_at",
    ]
    assert [entry.name for entry in fields(CoverageObligation)] == canonical
    assert len(canonical) == 11


def test_the_row_columns_are_the_canonical_block_read_off_one_log() -> None:
    """Every row-level column §13 names exists as a *read face*, and the four
    that are functions of the event log are read from it."""

    block = list(canonical_lines(DATA_MODEL, "### PlanningLedger"))
    at = block.index("coverage_obligations[]")
    row_lines = block[:at]
    assert row_lines == [
        "target/family last_selected_at",
        "last_presented_at",
        "teaching_exposure_counts",
        "probe_counts",
        "review_offers",
        "recent_skips/rejections",
        "overexposure_window",
    ]
    built = row(
        events=(
            (LedgerEvent.CANDIDATE_SELECTED, DAY_ONE),
            (LedgerEvent.TEACHING_PRESENTED, DAY_TWO),
            (LedgerEvent.HINT_PRESENTED, DAY_TWO),
            (LedgerEvent.USER_SKIP, DAY_THREE),
            (LedgerEvent.USER_SKIP, DAY_THREE),
        ),
        probe_counts=2,
        review_offers=3,
    )
    assert built.last_selected_at == DAY_ONE
    assert built.last_presented_at == DAY_TWO
    assert built.teaching_exposure_counts == 1
    assert built.recent_skips == 2
    assert built.probe_counts == 2 and built.review_offers == 3
    assert len(built.presentations) == 2
    # one read face per canonical line, in the document's order (the first line
    # spells its key space in front of the column, and the sixth names two
    # words for one column)
    columns = [
        "last_selected_at",
        "last_presented_at",
        "teaching_exposure_counts",
        "probe_counts",
        "review_offers",
        "recent_skips",
        "overexposure_window",
    ]
    assert len(columns) == len(row_lines)
    for column in columns:
        assert hasattr(built, column), column
    assert "recent_skips/rejections".startswith(columns[5])


def test_a_log_with_only_a_selection_has_no_presentation_instant() -> None:
    built = row(events=((LedgerEvent.CANDIDATE_SELECTED, DAY_ONE),))
    assert built.last_selected_at == DAY_ONE
    assert built.last_presented_at is None
    assert built.teaching_exposure_counts == 0


def test_the_ledger_carries_the_three_row_independent_columns() -> None:
    block = list(canonical_lines(DATA_MODEL, "### PlanningLedger"))
    at = block.index("coverage_obligations[]")
    tail = block[at + 12 :]
    assert tail == [
        "coverage_debt_rollups",
        "recent_target_families",
        "version",
    ]
    empty = PlanningLedger()
    assert empty.version == PLANNING_LEDGER_MODEL_VERSION
    assert empty.coverage_debt_rollups == {}
    assert empty.recent_target_families == ()
    assert empty.rows == {} and empty.obligations == ()


def test_the_pause_word_is_the_canonical_one() -> None:
    """DATA_MODEL §24.14's word, and the one BF-06 §14 marks obligations with."""

    assert [reason.value for reason in PauseReason] == [
        "UNAVAILABLE_IN_CURRENT_RUNTIME"
    ]
    word_block = list(
        canonical_lines(DATA_MODEL, "### Planner Candidate Additions", 1)
    )
    assert word_block == ["UNAVAILABLE_IN_CURRENT_RUNTIME"]
    additions = (DOCS_ROOT / DATA_MODEL).read_text(encoding="utf-8")
    assert "不累计 impossible direct CoverageDebt" in additions
    assert "对应 text target 可以有 PREPARATORY goal relevance" in additions
    register = (DOCS_ROOT / "DECISION_REGISTER.md").read_text(
        encoding="utf-8"
    )
    assert "不累计 impossible direct CoverageDebt" in register
    bf06 = (
        BASELINES / "modality/BF-06_V1_Operational_Modality_Scope.md"
    ).read_text(encoding="utf-8")
    assert "SPEAKING direct-modality obligation" in bf06
    assert "do not accrue direct CoverageDebt" in bf06
    assert "UNAVAILABLE_IN_CURRENT_RUNTIME" in bf06


def test_the_direct_obligation_rule_replays_the_frozen_reference() -> None:
    """Every modality × capability combination, compared key for key with
    ``modality_scope_reference_v1.coverage_obligation``.

    The reference takes a capability dict and nothing else; this cut's
    ``runtime=None`` arm is its own addition and is pinned separately below.
    """

    reference = _load_reference(MODALITY_REFERENCE, "modality_scope_reference_v1")
    capability_maps: list[dict[str, bool]] = [
        {},
        {"voice_input": True},
        {"listening_comprehension_evaluator": True},
        {"voice_input": True, "listening_comprehension_evaluator": True},
        _json(MODALITY_POLICY)["v1_runtime_capabilities"],
    ]
    for capabilities in capability_maps:
        for modality in GoalModality:
            mine = direct_obligation_of(modality, capabilities)
            theirs = reference.coverage_obligation(modality.value, capabilities)
            assert mine.direct_obligation == theirs["direct_obligation"], (
                modality,
                capabilities,
            )
            assert mine.accrue_direct_coverage_debt == (
                theirs["accrue_direct_coverage_debt"]
            ), (modality, capabilities)
            assert mine.preparatory_training_allowed == (
                theirs["preparatory_training_allowed"]
            ), (modality, capabilities)


def test_the_v1_runtime_policy_marks_speaking_and_listening_unavailable() -> None:
    capabilities = _json(MODALITY_POLICY)["v1_runtime_capabilities"]
    assert capabilities["voice_input"] is False
    assert capabilities["listening_comprehension_evaluator"] is False
    for modality in (GoalModality.SPEAKING, GoalModality.LISTENING):
        rule = direct_obligation_of(modality, capabilities)
        assert rule.direct_obligation == "UNAVAILABLE_IN_CURRENT_RUNTIME"
        assert rule.accrue_direct_coverage_debt is False
        assert rule.preparatory_training_allowed is True
    for modality in (GoalModality.READING, GoalModality.WRITING):
        rule = direct_obligation_of(modality, capabilities)
        assert rule.direct_obligation == "AVAILABLE"
        assert rule.accrue_direct_coverage_debt is True


def test_an_unknown_runtime_is_paused_rather_than_assumed() -> None:
    """This cut's own fail-closed arm: no capability map at all is not "the
    runtime supports it"."""

    for modality in GoalModality:
        rule = direct_obligation_of(modality, None)
        assert rule.direct_obligation == "UNAVAILABLE_IN_CURRENT_RUNTIME"
        assert rule.accrue_direct_coverage_debt is False


def test_the_two_half_declared_pauses_are_refused() -> None:
    with pytest.raises(LedgerInputError) as no_reason:
        obligation(paused=True, reason="")
    assert "accrual_paused with no pause_reason" in str(no_reason.value)
    with pytest.raises(LedgerInputError) as stray_reason:
        CoverageObligation(
            obligation_key="co-1",
            scope_type="TARGET",
            target_or_family_id=TARGET,
            goal_id=None,
            window_start=DAY_ONE,
            window_end=DAY_THREE,
            debt_value=0.5,
            accrual_paused=False,
            pause_reason=PauseReason.UNAVAILABLE_IN_CURRENT_RUNTIME.value,
            last_served_at=None,
            last_engaged_at=None,
        )
    assert "not paused" in str(stray_reason.value)


def test_no_accrual_entry_moves_a_paused_obligation_s_debt() -> None:
    """The BF-06 §14 rule, checked at every entry point the core has: the
    accrual, all five events, and the two repayment calls."""

    paused = obligation(debt=0.0, paused=True)
    for amount in (0.25, 0.5, 1.0):
        outcome = accrue(paused, amount=amount, at=DAY_TWO)
        assert outcome.changed is False, amount
        assert outcome.obligation.debt_value == 0.0, amount
        assert PauseReason.UNAVAILABLE_IN_CURRENT_RUNTIME.value in outcome.reason
    for event in LEDGER_EVENTS:
        if event in SERVING_EVENTS:
            with pytest.raises(LedgerInputError):
                apply_ledger_event(paused, event, at=DAY_TWO)
            continue
        outcome = apply_ledger_event(paused, event, at=DAY_TWO)
        assert outcome.obligation.debt_value == 0.0, event
    with pytest.raises(LedgerInputError):
        serve(paused, at=DAY_TWO)
    with pytest.raises(LedgerInputError):
        engage(paused, at=DAY_TWO)


def test_a_paused_obligation_answers_no_service_state() -> None:
    """It cannot accrue, so it cannot be starved: ``CRITICAL`` here would let
    §13's safeguard spend a slot on an obligation the runtime cannot serve."""

    paused = obligation(debt=1.0, paused=True)
    assert coverage_service_state_of(paused) is kernel.CoverageServiceState.NONE
    live = obligation(debt=1.0)
    assert coverage_service_state_of(live) is (
        kernel.CoverageServiceState.CRITICAL
    )


# ---------------------------------------------------------------------------
# ⑤ the service ladder
# ---------------------------------------------------------------------------


def test_the_service_ladder_words_are_the_frozen_golden_reference_s() -> None:
    """The four words come from the frozen golden reference's own set, through
    the kernel's enum — one vocabulary, reused and never re-spelled."""

    reference = _load_reference(GOLDEN_REFERENCE, "planner_reference_v1_1")
    assert {state.value for state in kernel.CoverageServiceState} == (
        reference.COVERAGE_SERVICE_STATES
    )
    assert {state.value for state in kernel.CoverageServiceState} == {
        "NONE",
        "WATCH",
        "DUE",
        "CRITICAL",
    }
    assert {state for _, state in SERVICE_STATE_RUNGS} == set(
        kernel.CoverageServiceState
    )
    assert OVEREXPOSURE_RUNGS[0][1] == "SATURATED"


def test_the_service_rungs_are_the_declared_values_and_are_ordered() -> None:
    rungs = [value for value, _ in SERVICE_STATE_RUNGS]
    assert rungs == sorted(rungs, reverse=True)
    assert rungs == [0.75, 0.50, 0.25, 0.00]
    for debt, expected in (
        (1.0, "CRITICAL"),
        (0.75, "CRITICAL"),
        (0.74, "DUE"),
        (0.50, "DUE"),
        (0.49, "WATCH"),
        (0.25, "WATCH"),
        (0.24, "NONE"),
        (0.0, "NONE"),
    ):
        assert coverage_service_state_of(obligation(debt=debt)).value == (
            expected
        ), debt


def test_the_debt_range_is_declared_and_refused_rather_than_clamped() -> None:
    low, high = LEDGER_VALUE_RANGE
    assert (low, high) == (0.0, 1.0)
    with pytest.raises(LedgerInputError) as outside:
        obligation(debt=1.5)
    assert "outside the declared range" in str(outside.value)
    with pytest.raises(LedgerInputError) as past_the_top:
        accrue(obligation(debt=0.75), amount=0.5, at=DAY_TWO)
    assert "leaves the declared range" in str(past_the_top.value)


def test_accrual_refuses_a_negative_amount_and_a_zero_is_a_no_op() -> None:
    live = obligation(debt=0.5)
    with pytest.raises(LedgerInputError) as negative:
        accrue(live, amount=-0.25, at=DAY_TWO)
    assert "negative" in str(negative.value)
    assert "serve/engage" in str(negative.value)
    zero = accrue(live, amount=0.0, at=DAY_TWO)
    assert zero.changed is False
    assert zero.obligation == live


def test_a_serving_or_an_engagement_repays_and_neither_goes_below_zero() -> None:
    served = serve(obligation(debt=0.25), at=DAY_TWO)
    assert served.debt_value == 0.0
    assert served.last_served_at == DAY_TWO
    engaged = engage(obligation(debt=0.25), at=DAY_TWO)
    assert engaged.debt_value == 0.0
    assert engaged.last_engaged_at == DAY_TWO
    assert (
        DEBT_REPAID_PER_SERVING,
        DEBT_REPAID_PER_ENGAGEMENT,
    ) == (1.0, 1.0)


# ---------------------------------------------------------------------------
# ④ the overexposure reading
# ---------------------------------------------------------------------------


def test_the_overexposure_band_words_are_the_frozen_asset_s() -> None:
    """The five words and their numbers, from the reference profile; the ledger
    answers words and the factor table keeps the numbers — one home each."""

    bands = _json(PLANNER_PROFILE)["reference_factor_bands"]["overexposure"]
    assert bands == {
        "NONE": 0.0,
        "LOW": 0.25,
        "MEDIUM": 0.5,
        "HIGH": 0.75,
        "SATURATED": 1.0,
    }
    assert [word for _, word in OVEREXPOSURE_RUNGS] == list(reversed(bands))
    assert FACTOR_BAND_VALUES["overexposure"] == bands


def test_the_count_ladder_is_declared_and_no_asset_carries_one() -> None:
    """The probe that makes "declared" a checked claim: neither the planner
    profile nor the modality policy carries a count ladder or a window length,
    so the two constants below are this cut's own and say so."""

    for relative in (PLANNER_PROFILE, MODALITY_POLICY):
        text = (BASELINES / relative).read_text(encoding="utf-8")
        assert "overexposure_window" not in text, relative
        assert "window_days" not in text, relative
    assert OVEREXPOSURE_WINDOW_DAYS == 7
    assert OVEREXPOSURE_RUNGS == (
        (4, "SATURATED"),
        (3, "HIGH"),
        (2, "MEDIUM"),
        (1, "LOW"),
        (0, "NONE"),
    )
    for count, expected in (
        (0, "NONE"),
        (1, "LOW"),
        (2, "MEDIUM"),
        (3, "HIGH"),
        (4, "SATURATED"),
        (9, "SATURATED"),
    ):
        assert overexposure_band_of(count) == expected, count
    with pytest.raises(LedgerInputError):
        overexposure_band_of(-1)


def test_the_window_is_half_open_and_compared_as_an_instant() -> None:
    window = LedgerWindow(start=DAY_ONE, end=DAY_TWO)
    assert window.contains(DAY_TWO) is True
    assert window.contains(DAY_ONE) is False
    assert window.contains(BEFORE_WINDOW) is False
    # one instant, two spellings: the comparison is the moment, not the bytes
    assert window.contains("2026-09-23T17:00:00+08:00") is True


def test_a_naive_or_empty_or_broken_timestamp_is_refused() -> None:
    for broken in ("", "2026-09-23T09:00:00", "not-a-timestamp"):
        with pytest.raises(LedgerInputError):
            LedgerWindow(start=DAY_ONE, end=DAY_TWO).contains(broken)
    with pytest.raises(LedgerInputError) as naive:
        TargetLedgerRow(target_key=TARGET).record(
            LedgerEvent.TEACHING_PRESENTED, at="2026-09-23T09:00:00"
        )
    assert "no UTC offset" in str(naive.value)


def test_the_overexposure_reading_counts_inside_the_fallback_window() -> None:
    built = row(
        events=(
            (LedgerEvent.TEACHING_PRESENTED, DAY_ONE),
            (LedgerEvent.HINT_PRESENTED, DAY_ONE),
            (LedgerEvent.TEACHING_PRESENTED, BEFORE_WINDOW),
        )
    )
    reading = overexposure_of(built, as_of=DAY_TWO)
    assert reading.count == 2
    assert reading.band == "MEDIUM"
    assert reading.last_presented_at == DAY_ONE
    assert reading.window.start < DAY_ONE <= reading.window.end
    assert "declared fallback of 7 days" in " ".join(reading.reasons)


def test_a_row_that_names_its_own_window_uses_it() -> None:
    own = LedgerWindow(start="2026-09-23T00:00:00+00:00", end=DAY_TWO)
    built = row(
        events=(
            (LedgerEvent.TEACHING_PRESENTED, DAY_ONE),
            (LedgerEvent.TEACHING_PRESENTED, "2026-09-23T08:00:00+00:00"),
        ),
        window=own,
    )
    reading = overexposure_of(built, as_of=DAY_TWO)
    assert reading.count == 1
    assert reading.band == "LOW"
    assert reading.window == own
    assert "the row's own" in " ".join(reading.reasons)
    assert reading.last_presented_at == "2026-09-23T08:00:00+00:00"


def test_a_rowless_target_answers_the_neutral_band_with_its_reason() -> None:
    reading = overexposure_of(None, as_of=DAY_TWO)
    assert reading.band == "NONE"
    assert reading.count == 0
    assert reading.last_presented_at is None
    assert "no row for this target" in " ".join(reading.reasons)


# ---------------------------------------------------------------------------
# ④⑤ the ledger's own reads
# ---------------------------------------------------------------------------


def test_the_governing_obligation_is_the_worst_live_target_scoped_one() -> None:
    ledger = PlanningLedger(
        obligations=(
            obligation("co-paused", debt=1.0, paused=True),
            obligation(
                "co-family",
                debt=1.0,
                scope=ObligationScope.TARGET_FAMILY.value,
            ),
            obligation("co-shallow", debt=0.25),
            obligation("co-second", debt=0.5),
            obligation("co-other", target=OTHER_TARGET, debt=0.9),
        )
    )
    governing = ledger.governing_obligation_of(TARGET)
    assert governing is not None
    assert governing.obligation_key == "co-second"
    assert ledger.governing_obligation_of(OTHER_TARGET).obligation_key == (
        "co-other"
    )
    assert ledger.governing_obligation_of("no-such-target") is None
    assert [entry.obligation_key for entry in ledger.obligations_for(TARGET)] == [
        "co-family",
        "co-paused",
        "co-second",
        "co-shallow",
    ]
    assert [
        entry.obligation_key
        for entry in ledger.target_scoped_obligations_for(TARGET)
    ] == ["co-paused", "co-second", "co-shallow"]


def test_governing_breaks_a_tie_on_the_key_and_not_on_the_order() -> None:
    forward = PlanningLedger(
        obligations=(obligation("co-b", debt=0.5), obligation("co-a", debt=0.5))
    )
    backward = PlanningLedger(
        obligations=(obligation("co-a", debt=0.5), obligation("co-b", debt=0.5))
    )
    assert forward.governing_obligation_of(TARGET).obligation_key == "co-a"
    assert backward.governing_obligation_of(TARGET).obligation_key == "co-a"


def test_serviceable_targets_skip_paused_and_family_scoped_obligations() -> None:
    ledger = PlanningLedger(
        obligations=(
            obligation("co-paused", debt=1.0, paused=True),
            obligation(
                "co-family", debt=1.0, scope=ObligationScope.TARGET_FAMILY.value
            ),
            obligation("co-goal", debt=1.0, goal_id="goal-1", scope="GOAL"),
            obligation("co-paid", debt=0.0),
            obligation("co-live", debt=0.5),
            obligation("co-live-2", debt=0.25, target=OTHER_TARGET),
        )
    )
    assert ledger.serviceable_targets() == (TARGET, OTHER_TARGET)
    assert [entry.obligation_key for entry in ledger.serviceable_obligations()] == [
        "co-live",
        "co-live-2",
    ]


def test_readings_for_says_which_case_it_answered() -> None:
    with_obligation = PlanningLedger(
        obligations=(obligation("co-live", debt=0.5),)
    )
    reading = with_obligation.readings_for(TARGET, as_of=DAY_TWO)
    assert reading.obligation is not None
    assert reading.service_state is kernel.CoverageServiceState.DUE
    assert "governing obligation co-live" in " ".join(reading.reasons)
    assert reading.target_id == TARGET

    paused_only = PlanningLedger(
        obligations=(obligation("co-live", debt=1.0, paused=True),)
    )
    paused_reading = paused_only.readings_for(TARGET, as_of=DAY_TWO)
    assert paused_reading.obligation is None
    assert paused_reading.service_state is kernel.CoverageServiceState.NONE
    assert "every one is paused" in " ".join(paused_reading.reasons)

    family_only = PlanningLedger(
        obligations=(
            obligation(
                "co-family", debt=1.0, scope=ObligationScope.TARGET_FAMILY.value
            ),
        )
    )
    family_reading = family_only.readings_for(TARGET, as_of=DAY_TWO)
    assert family_reading.obligation is None
    assert "not a target's debt" in " ".join(family_reading.reasons)

    empty = PlanningLedger().readings_for(TARGET, as_of=DAY_TWO)
    assert empty.obligation is None
    assert "no coverage obligation names this target" in " ".join(
        empty.reasons
    )


def test_recording_an_event_is_a_new_ledger_and_opens_a_row() -> None:
    ledger = PlanningLedger().record_event(
        TARGET, LedgerEvent.TEACHING_PRESENTED, at=DAY_TWO
    )
    assert ledger.row_of(TARGET).teaching_exposure_counts == 1
    assert ledger.row_of(OTHER_TARGET) is None
    assert PlanningLedger().row_of(TARGET) is None


# ---------------------------------------------------------------------------
# ② the carrier: no table, and what that costs
# ---------------------------------------------------------------------------


def test_the_ledger_declares_no_table_and_says_why() -> None:
    assert PLANNING_LEDGER_STORAGE is LedgerStorage.NO_TABLE_V1
    assert "Phase 8" in PLANNING_LEDGER_STORAGE_REVISIT
    assert "deletion" in PLANNING_LEDGER_STORAGE_REVISIT
    text = source_text("src/elc/planner/ledger.py")
    assert "create table" not in text.lower()
    assert "PlanningLedger user history" in text.replace("\n", " ")
    tree = ast.parse(text)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert "sqlite3" not in modules
    assert not any(module.startswith("elc.platform.db") for module in modules)
    assert not any(module.endswith(".store") for module in modules)
    spawned = {
        node.attr if isinstance(node, ast.Attribute) else node.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Attribute, ast.Name))
    }
    for forbidden in ("now", "utcnow", "today", "monotonic", "uuid4", "getenv"):
        assert forbidden not in spawned, forbidden


def test_the_two_columns_with_no_writer_are_carried_and_never_invented() -> None:
    """``probe_counts`` / ``review_offers``: none of §20's five words is a probe
    or a review offer, so they are stored counters nothing writes."""

    built = row(probe_counts=4, review_offers=2)
    for event in LEDGER_EVENTS:
        moved = built.record(event, at=DAY_TWO)
        assert moved.probe_counts == 4 and moved.review_offers == 2, event
    prose = " ".join((source_text("src/elc/planner/ledger.py"),))
    assert "no writer" in prose


def test_the_module_states_which_numbers_are_declared() -> None:
    """The three declared readings are named as declared in the module that
    carries them, and the calibratable-list citation is the one that makes a
    rate a parameter rather than an invention."""

    text = source_text("src/elc/planner/ledger.py")
    assert "CoverageDebt rates / service bonus" in text
    assert PLANNING_LEDGER_MODEL_VERSION == "pl1"
    for constant in (
        "DEBT_REPAID_PER_SERVING",
        "DEBT_REPAID_PER_ENGAGEMENT",
        "SERVICE_STATE_RUNGS",
        "OVEREXPOSURE_WINDOW_DAYS",
        "OVEREXPOSURE_RUNGS",
    ):
        assert constant in text, constant
        assert text.count(constant) > 1, constant


def test_the_ledger_reuses_the_kernel_s_vocabulary_only() -> None:
    """``CoverageServiceState`` is reused, never re-spelled — and that one name
    is the only thing this module takes from the kernel."""

    tree = ast.parse(source_text("src/elc/planner/ledger.py"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == (
            "elc.planner.kernel"
        ):
            imported.extend(alias.name for alias in node.names)
    assert imported == ["CoverageServiceState"]
    source = source_text("src/elc/planner/ledger.py")
    assert "class CoverageServiceState" not in source
    assert "def _score" not in source


def test_the_docstring_quotes_the_column_set_the_events_and_the_two_rules() -> None:
    """The module's own prose carries the three canonical blocks it implements,
    so a reader who opens the file meets the documents rather than a summary."""

    docstring = ast.get_docstring(
        ast.parse(source_text("src/elc/planner/ledger.py"))
    )
    assert docstring is not None
    for phrase in (
        "### PlanningLedger",
        "不记录 mastery。",
        "coverage_obligations[]",
        "last_engaged_at?",
        "candidate_selected",
        "user_skip",
        "SELECT != exposure",
        "CoverageDebt 不因 selection 自动偿还",
        "UNAVAILABLE_IN_CURRENT_RUNTIME",
        "PlanningLedger actual exposure/outcome",
        "some PlanningLedger rollups",
    ):
        assert phrase in docstring, phrase


def test_the_module_is_pure_by_construction(tmp_path: Path) -> None:
    """No I/O: every input arrives as an argument, and the only filesystem name
    in the module is in prose."""

    tree = ast.parse(source_text("src/elc/planner/ledger.py"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for forbidden in ("open", "write", "read_text", "connect", "execute"):
        assert forbidden not in calls, forbidden
