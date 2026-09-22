"""P7-1 ② — the numbers are BF-02's, the utility is §12's formula, and the
last steps of §10.1's order are §13's safeguard, §15's Pareto pruning and
§16's tie-break.

Every number is extracted from the frozen assets at test time rather than typed
twice: ``behavioral_baselines/planner/planner_reference_profile_v1_1.json`` for
the values, BF-02's own numbered sections for the prose that carries them. A
transcription slip in the kernel fails a test instead of shipping, and the
extraction doubles as the statement of where each number comes from.

The behavioural half pins what the numbers *mean*: the coverage-starvation
safeguard cannot break a scope word, a suppression or a hard prerequisite
(§13's own list), an explicit request is not gated by the automatic threshold
(§10.1's second hard rule), several explicit requests rank by
``request_priority`` and then by utility and never by name order (§8), origin
labels add no utility (§4), and the tie-break is a near-tie rule rather than a
substitute for utility (§16).

The tie-break tests are arithmetic on purpose: a candidate has to clear §14's
activation threshold *before* any tie-break runs, so each pair below is built
to be activated and to sit inside BF-02 §15's window, with the numbers written
into the test that depends on them.
"""

from __future__ import annotations

import ast
import json

import pytest

from elc.planner.kernel import (
    BENEFIT_FACTORS,
    BENEFIT_WEIGHTS,
    COST_FACTORS,
    COST_WEIGHTS,
    INITIATIVE_TIE_RANK,
    PLANNER_KERNEL_MODEL_VERSION,
    PLANNER_PROFILE_VERSION,
    POLICY_PROFILES,
    READINESS_RANK,
    SCAFFOLD_MIN_COGNITIVE_LOAD,
    SCAFFOLD_MIN_SUPPORT_COST,
    TIE_BREAK_ORDER,
    TIE_EPSILON,
    BenefitFactor,
    CoverageServiceState,
    NoTargetReason,
    PlannerInputError,
    PrerequisiteState,
    ReadinessLevel,
    plan,
)
from elc.planner.types import (
    InitiativeClass,
    PlannerDecisionOutcome,
    UserIntentScope,
)
from elc.platform.types import PlannerExecutionStatusValue
from elc.user_config.types import TeachingFrequency

from .conftest import (
    BASELINES,
    DOCS_ROOT,
    baseline_lines,
    benefit_vector,
    canonical_lines,
    complete_context,
    cost_vector,
    kernel_input,
    proposal,
    source_text,
    teaching_policy,
)

PROFILE = BASELINES / "planner" / "planner_reference_profile_v1_1.json"
BF_02 = "planner/BF-02_Planner_Decision_Spec_v1.1.md"
DOMAIN_MODEL = "DOMAIN_MODEL.md"

SECTION_6 = "## 6. Benefit factors v1.1"
SECTION_7 = "## 7. Cost factors"
SECTION_12 = "## 12. Utility v1.1"
SECTION_13 = "## 13. Coverage debt starvation safeguard"
SECTION_16 = "## 16. Tie-break"
SECTION_21 = "## 21. 仍可校准的内容"
CANDIDATE_MODEL = "## 11. Planner Candidate Model"

#: A vector whose utility is comfortably above BALANCED's 0.195 threshold
#: under every profile below: 0.17 × 1.0 + 0.13 × 1.0 + 0.08 × 0.75 = 0.36.
BASE_BENEFIT = benefit_vector(learning_need=1.0, context_fit=1.0)


def _reference() -> dict:
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def _document_line(prefix: str) -> str:
    for line in (
        (DOCS_ROOT / DOMAIN_MODEL).read_text(encoding="utf-8").splitlines()
    ):
        if line.startswith(prefix):
            return line
    raise AssertionError(f"{DOMAIN_MODEL}: no line starting with {prefix!r}")


def _backticked_list(line: str) -> tuple[str, ...]:
    inner = line.split("`", 2)[1]
    return tuple(part.strip() for part in inner.split("/") if part.strip())


def _weight_rows(rows: tuple[str, ...]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for row in rows:
        name, value = row.split()
        parsed[name] = float(value)
    return parsed


def _rows_by_id(result) -> dict:
    return {row.candidate_id: row for row in result.trace.candidates}


# -- ① the factor names are §10.1's and BF-02's ------------------------------


def test_the_benefit_names_are_section_10_1s_line() -> None:
    """docs/DOMAIN_MODEL.md line 621's list, split on ``/``, compared with the
    eleven-factor vocabulary — and §11's own ten-name block recorded as the
    document's short list rather than quietly followed."""

    line = _document_line("Benefit factors 包括：")
    assert _backticked_list(line) == tuple(
        factor.value for factor in BENEFIT_FACTORS
    )
    assert len(BENEFIT_FACTORS) == 11

    section_11 = canonical_lines(DOMAIN_MODEL, CANDIDATE_MODEL, 3)
    assert section_11 == tuple(
        factor.value
        for factor in BENEFIT_FACTORS
        if factor is not BenefitFactor.COMMUNICATIVE_IMPACT
    )
    assert "communicative_impact" not in section_11


def test_the_cost_names_are_section_10_1s_line() -> None:
    line = _document_line("Cost factors：")
    assert _backticked_list(line) == tuple(factor.value for factor in COST_FACTORS)
    assert canonical_lines(DOMAIN_MODEL, CANDIDATE_MODEL, 4) == tuple(
        factor.value for factor in COST_FACTORS
    )


def test_the_names_are_bf_02s_two_blocks() -> None:
    assert baseline_lines(BF_02, SECTION_6, 0) == tuple(
        factor.value for factor in BENEFIT_FACTORS
    )
    assert baseline_lines(BF_02, SECTION_7, 0) == tuple(
        factor.value for factor in COST_FACTORS
    )
    assert "v1.0 遗漏的 `communicative_impact` 已恢复。" in (
        (BASELINES / BF_02).read_text(encoding="utf-8")
    )


# -- ② the numbers -----------------------------------------------------------


def test_the_benefit_weights_are_bf_02_section_12s() -> None:
    """§12's own rows, the JSON's ``benefit_weights`` and the kernel's table
    are three readers of one number set."""

    rows = _weight_rows(baseline_lines(BF_02, SECTION_12, 0))
    expected = {factor.value: value for factor, value in BENEFIT_WEIGHTS.items()}
    assert rows == expected
    assert _reference()["benefit_weights"] == expected
    assert set(BENEFIT_WEIGHTS) == set(BENEFIT_FACTORS)
    assert sum(BENEFIT_WEIGHTS.values()) == pytest.approx(1.0)


def test_the_cost_weights_are_bf_02_section_12s() -> None:
    rows = _weight_rows(baseline_lines(BF_02, SECTION_12, 1))
    expected = {factor.value: value for factor, value in COST_WEIGHTS.items()}
    assert rows == expected
    assert _reference()["cost_weights"] == expected
    assert set(COST_WEIGHTS) == set(COST_FACTORS)
    assert sum(COST_WEIGHTS.values()) == pytest.approx(1.0)


def test_the_profile_parameters_are_the_reference_profiles() -> None:
    profile = _reference()
    assert set(POLICY_PROFILES) == set(profile["policy_profiles"])
    for name, parameters in POLICY_PROFILES.items():
        reference = profile["policy_profiles"][name]
        assert parameters.profile.value == name
        assert {
            lane.value: value
            for lane, value in parameters.initiative_multiplier.items()
        } == reference["initiative_multiplier"]
        assert parameters.cost_multiplier == reference["cost_multiplier"]
        assert parameters.automatic_activation_threshold == (
            reference["automatic_activation_threshold"]
        )
    assert {
        name: parameters.coverage_service_bonus
        for name, parameters in POLICY_PROFILES.items()
    } == profile["coverage_service_bonus"]
    assert TIE_EPSILON == profile["tie_epsilon"]
    ladder = list(ReadinessLevel)
    assert list(profile["readiness_rank"]) == [
        f"R{index}" for index in range(len(ladder))
    ]
    assert READINESS_RANK == {
        level: profile["readiness_rank"][f"R{index}"]
        for index, level in enumerate(ladder)
    }
    assert INITIATIVE_TIE_RANK == {
        InitiativeClass(name): value
        for name, value in profile["initiative_rank"].items()
    }
    assert SCAFFOLD_MIN_SUPPORT_COST == (
        profile["scaffold_min_cost"]["support_cost"]
    )
    assert SCAFFOLD_MIN_COGNITIVE_LOAD == (
        profile["scaffold_min_cost"]["cognitive_load"]
    )
    assert PLANNER_PROFILE_VERSION == profile["profile_id"]
    assert PLANNER_KERNEL_MODEL_VERSION == "pk1"
    assert profile["status"] == "REFERENCE_DEFAULT_CALIBRATABLE"


def test_the_coverage_bonus_rows_are_bf_02_section_13s() -> None:
    rows = _weight_rows(baseline_lines(BF_02, SECTION_13, 2))
    assert rows == {"BALANCED": 0.08, "STUDY_FIRST": 0.10, "LOUNGE": 0.0}
    assert {
        name: parameters.coverage_service_bonus
        for name, parameters in POLICY_PROFILES.items()
    } == rows


def test_the_tie_break_order_is_bf_02_section_16s_block() -> None:
    rows = baseline_lines(BF_02, SECTION_16, 0)
    assert [row.split(" ", 1)[1] for row in rows] == [
        criterion.value for criterion in TIE_BREAK_ORDER
    ]
    assert len(TIE_BREAK_ORDER) == 8


def test_the_numbers_are_reference_values_and_say_so() -> None:
    """§21: the 92/92 regression validates none of these numbers — the module
    says so where the tables live, and names the change process."""

    source = source_text("src/elc/planner/kernel.py")
    assert "Reference values, not frozen ones" in source
    assert "REFERENCE_DEFAULT_CALIBRATABLE" in source
    text = (BASELINES / BF_02).read_text(encoding="utf-8")
    for phrase in (
        "planner_profile_version++",
        "full benchmark regression",
        "decision diff review",
    ):
        assert phrase in text, phrase


# -- ③ the utility itself ----------------------------------------------------


def test_the_utility_is_section_12s_formula() -> None:
    """Hand-computed: ``initiative_multiplier × Σ(w_b b) − cost_multiplier ×
    Σ(w_c c) + bonus`` with the reference weights."""

    result = plan(
        kernel_input(
            (
                proposal(
                    "c1",
                    benefit=benefit_vector(learning_need=0.75, context_fit=1.0),
                    cost=cost_vector(interruption_cost=0.2),
                    schedule_urgency=0.75,
                ),
            )
        )
    )
    row = result.trace.candidates[0]
    expected_benefit = 0.17 * 0.75 + 0.13 * 1.0 + 0.08 * 0.75
    expected_cost = 0.40 * 0.2
    assert row.benefit_score == pytest.approx(expected_benefit)
    assert row.cost_score == pytest.approx(expected_cost)
    assert row.utility == pytest.approx(
        1.0 * expected_benefit - 0.8 * expected_cost
    )
    assert row.coverage_service_bonus == 0.0
    assert row.activation_threshold == 0.195
    assert row.activated is True


def test_the_three_profiles_price_one_candidate_differently() -> None:
    """The profile is the policy: the same vector and the same lane price
    differently under LOUNGE / BALANCED / STUDY_FIRST."""

    utilities: dict[str, float] = {}
    for frequency, name in (
        (TeachingFrequency.MINIMAL, "LOUNGE"),
        (TeachingFrequency.BALANCED, "BALANCED"),
        (TeachingFrequency.EAGER, "STUDY_FIRST"),
    ):
        context = complete_context(
            teaching_policy=teaching_policy(frequency=frequency)
        )
        result = plan(
            kernel_input(
                (
                    proposal(
                        "c1",
                        benefit=benefit_vector(learning_need=0.5),
                        cost=cost_vector(cognitive_load=0.5),
                    ),
                ),
                context=context,
            )
        )
        assert result.trace.context.planner_profile.value == name
        utilities[name] = result.trace.candidates[0].utility
    assert utilities["LOUNGE"] < utilities["BALANCED"] < utilities["STUDY_FIRST"]


@pytest.mark.parametrize(
    ("state", "natural_break", "frequency", "expected"),
    [
        pytest.param(
            CoverageServiceState.CRITICAL,
            True,
            TeachingFrequency.BALANCED,
            0.08,
            id="balanced",
        ),
        pytest.param(
            CoverageServiceState.CRITICAL,
            True,
            TeachingFrequency.EAGER,
            0.10,
            id="study-first",
        ),
        pytest.param(
            CoverageServiceState.CRITICAL,
            True,
            TeachingFrequency.MINIMAL,
            0.0,
            id="lounge",
        ),
        pytest.param(
            CoverageServiceState.CRITICAL,
            False,
            TeachingFrequency.BALANCED,
            0.0,
            id="no-natural-break",
        ),
        pytest.param(
            CoverageServiceState.DUE,
            True,
            TeachingFrequency.BALANCED,
            0.0,
            id="not-critical",
        ),
    ],
)
def test_the_coverage_bonus_needs_all_three_conditions(
    state: CoverageServiceState,
    natural_break: bool,
    frequency: TeachingFrequency,
    expected: float,
) -> None:
    """§13's two-layer safeguard: CRITICAL **and** a natural break **and** a
    profile that carries a bonus at all."""

    context = complete_context(
        teaching_policy=teaching_policy(frequency=frequency),
        natural_break_available=natural_break,
    )
    result = plan(
        kernel_input(
            (proposal("c1", coverage_service_state=state),), context=context
        )
    )
    row = result.trace.candidates[0]
    assert row.coverage_service_bonus == pytest.approx(expected)


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"suppressed": True}, id="suppression"),
        pytest.param(
            {"prerequisite_state": PrerequisiteState.BLOCKED},
            id="hard-prerequisite",
        ),
    ],
)
def test_the_coverage_bonus_cannot_break_its_exclusions(fields: dict) -> None:
    """§13's list of what the service bonus "仍不能突破": a suppression and a
    hard prerequisite are step-4 exclusions, so no bonus ever sees them."""

    context = complete_context(natural_break_available=True)
    result = plan(
        kernel_input(
            (
                proposal(
                    "debt",
                    coverage_service_state=CoverageServiceState.CRITICAL,
                    **fields,
                ),
            ),
            context=context,
        )
    )
    row = result.trace.candidates[0]
    assert row.excluded is not None
    assert row.coverage_service_bonus is None


def test_the_coverage_bonus_cannot_break_a_targeted_scope() -> None:
    """§13's first entry on that list: a CRITICAL coverage debt does not
    re-open a scope the user's own request narrowed."""

    context = complete_context(natural_break_available=True)
    result = plan(
        kernel_input(
            (
                proposal(
                    "debt",
                    coverage_service_state=CoverageServiceState.CRITICAL,
                ),
            ),
            context=context,
            scope=UserIntentScope.TARGETED_LEARNING_REQUEST,
        )
    )
    assert result.trace.candidates[0].excluded is not None
    assert result.trace.decision is PlannerDecisionOutcome.NO_TARGET


def test_origin_labels_add_no_utility() -> None:
    """§4: "origin count != utility bonus" — one vector, two origin sets, one
    price."""

    result = plan(
        kernel_input(
            (
                proposal("one", origins=("A",)),
                proposal(
                    "three", canonical_key="three", origins=("A", "B", "C")
                ),
            )
        )
    )
    rows = _rows_by_id(result)
    assert rows["one"].utility == pytest.approx(rows["three"].utility)
    assert rows["one"].merged_from == ("one",)


# -- ④ activation and §8's request priority ----------------------------------


def test_an_explicit_request_is_not_gated_by_the_automatic_threshold() -> None:
    """§10.1's second hard rule and §14's per-candidate threshold: the user
    path carries no threshold at all — asserted on the trace, not inferred."""

    context = complete_context(
        teaching_policy=teaching_policy(frequency=TeachingFrequency.MINIMAL)
    )
    tiny = benefit_vector(learning_need=0.1)
    automatic = plan(
        kernel_input((proposal("auto", benefit=tiny),), context=context)
    )
    auto_row = automatic.trace.candidates[0]
    assert auto_row.activation_threshold == 0.36
    assert auto_row.activated is False
    assert automatic.trace.no_target_reason is (
        NoTargetReason.BELOW_ACTIVATION_THRESHOLD
    )

    requested = plan(
        kernel_input(
            (proposal("asked", benefit=tiny, user_initiated=True),),
            context=context,
            scope=UserIntentScope.LEARNING_REQUEST,
        )
    )
    asked_row = requested.trace.candidates[0]
    assert asked_row.activation_threshold is None
    assert asked_row.activated is True
    assert requested.trace.decision is PlannerDecisionOutcome.SELECT


def test_several_explicit_requests_rank_by_priority_not_by_name() -> None:
    """§8, verbatim: "eligible user-initiated candidates exist → restrict to
    minimum request_priority → then utility/tie-break", and a multiple request
    must not degrade into "candidate_id alphabetical order"."""

    scope = UserIntentScope.TARGETED_LEARNING_REQUEST
    primary = proposal(
        "z_primary",
        benefit=benefit_vector(learning_need=0.3),
        user_initiated=True,
        request_aligned=True,
        request_priority=0,
    )
    secondary = proposal(
        "a_secondary",
        canonical_key="a_secondary",
        benefit=BASE_BENEFIT,
        user_initiated=True,
        request_aligned=True,
        request_priority=1,
    )
    result = plan(kernel_input((primary, secondary), scope=scope))
    rows = _rows_by_id(result)
    assert rows["z_primary"].utility < rows["a_secondary"].utility
    assert result.trace.selected_candidate_id == "z_primary"


def test_equal_priority_requests_rank_by_utility() -> None:
    """§8's closing rule: "如果多个请求同级 ... 则正常 utility 决定"."""

    scope = UserIntentScope.TARGETED_LEARNING_REQUEST
    weak = proposal(
        "u1",
        benefit=benefit_vector(learning_need=0.3),
        user_initiated=True,
        request_aligned=True,
    )
    strong = proposal(
        "u2",
        canonical_key="u2",
        benefit=BASE_BENEFIT,
        user_initiated=True,
        request_aligned=True,
    )
    result = plan(kernel_input((weak, strong), scope=scope))
    assert result.trace.selected_candidate_id == "u2"


# -- ⑤ §15's Pareto pruning --------------------------------------------------


def test_a_strictly_dominated_candidate_leaves_before_the_tie_break() -> None:
    """§15: inside one dominance class, all benefits ≥, all costs ≤ and one
    strict comparison removes the worse candidate — so the stable id can only
    settle candidates that are genuinely indistinguishable.

    Both candidates are activated (0.328 and 0.286 against BALANCED's 0.195),
    which is what puts them in the same pruned set at all: §15 runs over the
    **active** set, one step after activation.
    """

    dominating = proposal(
        "better",
        benefit=benefit_vector(learning_need=1.0, context_fit=1.0),
        cost=cost_vector(cognitive_load=0.2),
    )
    dominated = proposal(
        "worse",
        canonical_key="worse",
        benefit=benefit_vector(learning_need=1.0, context_fit=0.8),
        cost=cost_vector(cognitive_load=0.3),
    )
    result = plan(kernel_input((dominating, dominated)))
    rows = _rows_by_id(result)
    assert rows["worse"].activated is True
    assert rows["better"].activated is True
    assert rows["worse"].dominated_by == ("better",)
    assert rows["better"].dominated_by == ()
    assert result.trace.selected_candidate_id == "better"
    text = "\n".join(result.outcome.evaluation.reason_trace)
    assert "pareto removed worse (dominated by better)" in text


def test_a_trade_off_is_not_dominance() -> None:
    """Better on one factor and worse on another is not domination — §15
    requires *every* comparison to go one way."""

    result = plan(
        kernel_input(
            (
                proposal(
                    "cheap",
                    benefit=benefit_vector(learning_need=1.0),
                    cost=cost_vector(cognitive_load=1.0),
                ),
                proposal(
                    "deep",
                    canonical_key="deep",
                    benefit=benefit_vector(context_fit=1.0),
                    cost=cost_vector(cognitive_load=0.0),
                ),
            )
        )
    )
    for row in result.trace.candidates:
        assert row.dominated_by == ()


def test_dominance_is_read_inside_one_class_only() -> None:
    """§15's four class members: a REACTIVE and a PROACTIVE candidate are never
    compared, however their vectors look."""

    result = plan(
        kernel_input(
            (
                proposal(
                    "reactive",
                    benefit=BASE_BENEFIT,
                    initiative_class=InitiativeClass.REACTIVE,
                ),
                proposal(
                    "proactive",
                    canonical_key="proactive",
                    benefit=benefit_vector(learning_need=0.4),
                    cost=cost_vector(interruption_cost=0.9),
                    initiative_class=InitiativeClass.PROACTIVE,
                ),
            )
        )
    )
    for row in result.trace.candidates:
        assert row.dominated_by == ()


# -- ⑥ §16's tie-break --------------------------------------------------------
#
# Every pair below is activated (utility ≥ 0.195) and inside §15's window, so
# the tie-break actually runs; the arithmetic is written into the comment of
# each test, because a pair that drifts out of the window tests the utility
# instead.


def test_the_tie_break_is_only_for_a_near_tie() -> None:
    """§16's closing line: the tie-break "不代替 utility" — outside the window
    the higher utility wins even against a better tie key."""

    # winner 0.36 (BASE_BENEFIT), keyed 0.21: both activated, 0.15 apart.
    winner = proposal("plain", benefit=BASE_BENEFIT)
    keyed = proposal(
        "keyed",
        canonical_key="keyed",
        benefit=benefit_vector(learning_need=0.6, context_fit=0.6),
        user_initiated=True,
        request_aligned=True,
    )
    result = plan(kernel_input((winner, keyed)))
    rows = _rows_by_id(result)
    assert rows["keyed"].activated is True
    assert rows["plain"].utility - rows["keyed"].utility > TIE_EPSILON
    assert rows["keyed"].in_tie_set is False
    assert result.trace.selected_candidate_id == "plain"


def test_inside_the_window_the_tie_key_decides() -> None:
    """Within ``tie_epsilon`` the §16 key wins: the worse-id candidate with the
    better key takes it, even though its utility is marginally lower.

    The two are kept incomparable on purpose (each carries a *different* cost
    the §16 key does not read as a criterion — ``support_cost`` for one,
    ``overexposure`` for the other), because a pair that dominates would never
    reach the tie-break at all. Utilities: 0.36 − 0.8 × 0.005 = 0.356 against
    0.36 − 0.8 × 0.01 = 0.352.
    """

    higher = proposal(
        "a_higher",
        benefit=BASE_BENEFIT,
        cost=cost_vector(support_cost=0.05),
    )
    keyed = proposal(
        "z_keyed",
        canonical_key="z_keyed",
        benefit=BASE_BENEFIT,
        cost=cost_vector(overexposure=0.05),
        request_aligned=True,
    )
    result = plan(kernel_input((higher, keyed)))
    rows = _rows_by_id(result)
    assert rows["a_higher"].utility > rows["z_keyed"].utility
    assert rows["a_higher"].utility - rows["z_keyed"].utility <= TIE_EPSILON
    assert rows["a_higher"].dominated_by == ()
    assert rows["z_keyed"].dominated_by == ()
    assert rows["z_keyed"].in_tie_set is True
    assert result.trace.selected_candidate_id == "z_keyed"


def test_request_alignment_outranks_every_other_criterion() -> None:
    """§16's first criterion: equal vectors, and the request-aligned candidate
    wins despite the larger id."""

    aligned = proposal(
        "z_aligned", benefit=BASE_BENEFIT, request_aligned=True
    )
    plain = proposal("a_plain", canonical_key="a_plain", benefit=BASE_BENEFIT)
    result = plan(kernel_input((aligned, plain)))
    assert result.trace.selected_candidate_id == "z_aligned"


def test_the_user_initiated_flag_outranks_the_lane() -> None:
    """§16's second criterion, read under a scope where the flag alone does not
    move the candidate onto the user path (OPEN) — so criterion 2, and not §8's
    restriction, is what decides.

    The lanes differ too (PROACTIVE against REACTIVE), and the utilities are
    held together by the profile's own pricing: 1.0 × 0.36 against
    0.8 × 0.45 = 0.36 — criterion 2 is what has to win, because criterion 3
    would pick the other candidate.
    """

    flagged = proposal(
        "z_flagged",
        benefit=benefit_vector(
            learning_need=1.0, context_fit=1.0, communicative_impact=0.75
        ),
        user_initiated=True,
        initiative_class=InitiativeClass.PROACTIVE,
    )
    plain = proposal(
        "a_plain",
        canonical_key="a_plain",
        benefit=BASE_BENEFIT,
        initiative_class=InitiativeClass.REACTIVE,
    )
    result = plan(kernel_input((flagged, plain)))
    rows = _rows_by_id(result)
    assert rows["z_flagged"].utility == pytest.approx(rows["a_plain"].utility)
    assert rows["z_flagged"].activation_path.value == "AUTOMATIC"
    assert result.trace.selected_candidate_id == "z_flagged"


def test_the_immediate_lane_outranks_the_factor_criteria() -> None:
    """§16's third criterion, "REACTIVE > OPPORTUNISTIC > PROACTIVE", with the
    two utilities inside the window by construction: the profile prices the
    lane (0.8 for PROACTIVE), so the PROACTIVE candidate carries more benefit
    for the same utility. 0.36 versus 0.8 × 0.45 = 0.36."""

    reactive = proposal(
        "z_reactive",
        benefit=BASE_BENEFIT,
        initiative_class=InitiativeClass.REACTIVE,
    )
    proactive = proposal(
        "a_proactive",
        canonical_key="a_proactive",
        benefit=benefit_vector(
            learning_need=1.0, context_fit=1.0, communicative_impact=0.75
        ),
        initiative_class=InitiativeClass.PROACTIVE,
    )
    result = plan(kernel_input((reactive, proactive)))
    rows = _rows_by_id(result)
    assert rows["z_reactive"].utility == pytest.approx(
        rows["a_proactive"].utility
    )
    assert result.trace.selected_candidate_id == "z_reactive"
    assert INITIATIVE_TIE_RANK[InitiativeClass.REACTIVE] > (
        INITIATIVE_TIE_RANK[InitiativeClass.PROACTIVE]
    )


def test_opportunity_expiry_outranks_cost_criteria() -> None:
    """§16's fourth criterion — and the arithmetic it needs: the weight is
    0.02, so the criterion can only be decisive for an expiry gap of at most
    0.75 inside a window of 0.015 (0.02 × 0.5 = 0.01 here)."""

    expiring = proposal(
        "z_expiring",
        benefit=benefit_vector(
            learning_need=1.0, context_fit=1.0, opportunity_expiry=0.5
        ),
    )
    persistent = proposal("a_persistent", canonical_key="a_persistent",
                          benefit=BASE_BENEFIT)
    result = plan(kernel_input((expiring, persistent)))
    assert result.trace.selected_candidate_id == "z_expiring"


def test_lower_interruption_cost_outranks_lower_overexposure() -> None:
    """§16's fifth against its sixth: equal total cost, so equal utility, and
    the cheaper interruption wins although its overexposure is the worse one
    (0.40 × 0.125 + 0.20 × 0.25 = 0.40 × 0.25 + 0.20 × 0.0 = 0.10)."""

    quiet = proposal(
        "z_quiet",
        benefit=BASE_BENEFIT,
        cost=cost_vector(interruption_cost=0.125, overexposure=0.25),
    )
    loud = proposal(
        "a_loud",
        canonical_key="a_loud",
        benefit=BASE_BENEFIT,
        cost=cost_vector(interruption_cost=0.25, overexposure=0.0),
    )
    result = plan(kernel_input((quiet, loud)))
    rows = _rows_by_id(result)
    assert rows["z_quiet"].cost_score == pytest.approx(rows["a_loud"].cost_score)
    assert result.trace.selected_candidate_id == "z_quiet"


def test_lower_overexposure_outranks_lower_cognitive_load() -> None:
    """§16's sixth against its seventh, the same construction one criterion on
    (0.20 × 0.25 + 0.20 × 0.25 = 0.20 × 0.5 + 0.20 × 0.0 = 0.10)."""

    fresh = proposal(
        "z_fresh",
        benefit=BASE_BENEFIT,
        cost=cost_vector(overexposure=0.25, cognitive_load=0.25),
    )
    stale = proposal(
        "a_stale",
        canonical_key="a_stale",
        benefit=BASE_BENEFIT,
        cost=cost_vector(overexposure=0.5, cognitive_load=0.0),
    )
    result = plan(kernel_input((fresh, stale)))
    rows = _rows_by_id(result)
    assert rows["z_fresh"].cost_score == pytest.approx(rows["a_stale"].cost_score)
    assert result.trace.selected_candidate_id == "z_fresh"


def test_lower_cognitive_load_outranks_a_cost_that_is_not_a_criterion() -> None:
    """§16's seventh criterion, with the compensation carried by
    ``support_cost`` — a cost the tie-break does not read, which is what makes
    this pair test criterion 7 rather than criterion 6
    (0.20 × 0.25 + 0.10 × 0.5 = 0.20 × 0.5 + 0.10 × 0.0 = 0.10)."""

    light = proposal(
        "z_light",
        benefit=BASE_BENEFIT,
        cost=cost_vector(cognitive_load=0.25, support_cost=0.5),
    )
    heavy = proposal(
        "a_heavy",
        canonical_key="a_heavy",
        benefit=BASE_BENEFIT,
        cost=cost_vector(cognitive_load=0.5, support_cost=0.0),
    )
    result = plan(kernel_input((light, heavy)))
    rows = _rows_by_id(result)
    assert rows["z_light"].cost_score == pytest.approx(rows["a_heavy"].cost_score)
    assert result.trace.selected_candidate_id == "z_light"


def test_the_stable_candidate_id_is_the_last_criterion() -> None:
    """§16's eighth criterion: two indistinguishable candidates are settled by
    the id — the deterministic floor beneath every other rule."""

    zulu = proposal("z_candidate", benefit=BASE_BENEFIT)
    alpha = proposal(
        "a_candidate", canonical_key="a_candidate", benefit=BASE_BENEFIT
    )
    forward = plan(kernel_input((zulu, alpha)))
    backward = plan(kernel_input((alpha, zulu)))
    assert forward.trace.selected_candidate_id == "a_candidate"
    assert backward.trace.selected_candidate_id == "a_candidate"


# -- ⑦ determinism -----------------------------------------------------------


def test_the_same_input_twice_gives_the_same_result() -> None:
    planning = kernel_input(
        (proposal("c1"), proposal("c2", canonical_key="c2"))
    )
    first = plan(planning)
    second = plan(planning)
    assert first.trace == second.trace
    assert first.outcome.evaluation == second.outcome.evaluation
    assert first.outcome.decision == second.outcome.decision


def test_the_arrival_order_of_proposals_cannot_change_the_decision() -> None:
    """§4 orders the canonical set by key, so two arrivals agree on the
    decision, on the trace's candidate order and on every utility."""

    one = proposal("c1", benefit=benefit_vector(learning_need=0.5))
    two = proposal(
        "c2", canonical_key="c2", benefit=benefit_vector(learning_need=0.5)
    )
    forward = plan(kernel_input((one, two)))
    backward = plan(kernel_input((two, one)))
    assert forward.trace.selected_candidate_id == (
        backward.trace.selected_candidate_id
    )
    assert [row.candidate_id for row in forward.trace.candidates] == [
        row.candidate_id for row in backward.trace.candidates
    ]
    assert [row.utility for row in forward.trace.candidates] == [
        row.utility for row in backward.trace.candidates
    ]


def test_the_insertion_order_of_a_factor_mapping_cannot_change_the_result() -> None:
    """The folds walk the factors' declaration order, not the mapping's, so a
    caller's dict order cannot reach the arithmetic."""

    forward = {factor: 0.125 for factor in BENEFIT_FACTORS}
    forward[BenefitFactor.SCHEDULE_URGENCY] = 0.75
    backward = dict(reversed(list(forward.items())))
    first = plan(kernel_input((proposal("c1", benefit=forward),)))
    second = plan(kernel_input((proposal("c1", benefit=backward),)))
    assert first.trace.candidates[0].utility == (
        second.trace.candidates[0].utility
    )
    assert first.trace == second.trace


def test_merging_two_arrivals_leaves_the_vector_and_the_utility_alone() -> None:
    """§4's merge: origins union, the two flags OR, the minimum priority — and
    the utility unchanged, because the vector is not merged."""

    scope = UserIntentScope.LEARNING_REQUEST
    alone = plan(
        kernel_input((proposal("one", benefit=BASE_BENEFIT),), scope=scope)
    )
    merged = plan(
        kernel_input(
            (
                proposal("one", benefit=BASE_BENEFIT, origins=("A",)),
                proposal(
                    "two",
                    canonical_key="one",
                    benefit=BASE_BENEFIT,
                    origins=("B",),
                    request_priority=2,
                    user_initiated=True,
                ),
            ),
            scope=scope,
        )
    )
    (row,) = merged.trace.candidates
    assert row.merged_from == ("one", "two")
    assert row.candidate_id == "one"
    assert row.request_priority == 0
    assert row.utility == pytest.approx(alone.trace.candidates[0].utility)
    assert row.activation_path.value == "USER_INITIATED"
    assert alone.trace.candidates[0].activation_path.value == "AUTOMATIC"


def test_the_merge_takes_the_most_immediate_lane() -> None:
    """§4: "initiative = most immediate lane" — REACTIVE is the most immediate
    of the three (docs/DOMAIN_MODEL.md §11's order)."""

    result = plan(
        kernel_input(
            (
                proposal(
                    "one",
                    benefit=BASE_BENEFIT,
                    initiative_class=InitiativeClass.PROACTIVE,
                ),
                proposal(
                    "two",
                    canonical_key="one",
                    benefit=BASE_BENEFIT,
                    initiative_class=InitiativeClass.REACTIVE,
                ),
            )
        )
    )
    (row,) = result.trace.candidates
    assert row.initiative_class is InitiativeClass.REACTIVE


def test_two_arrivals_of_one_candidate_may_not_disagree_about_the_vector() -> None:
    """§4's "最终 factor vector 不在 merge 时相加或取 max": a disagreement is
    refused rather than resolved."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (
                    proposal("one", benefit=benefit_vector(learning_need=0.5)),
                    proposal(
                        "two",
                        canonical_key="one",
                        benefit=benefit_vector(learning_need=0.9),
                    ),
                )
            )
        )
    assert "factor vector" in str(raised.value)


def test_the_ids_are_content_addressed_from_the_cycle() -> None:
    planning = kernel_input((proposal("c1"),))
    first = plan(planning)
    second = plan(planning)
    assert first.outcome.evaluation.planner_evaluation_id == "pe-dc-p7-1"
    assert first.outcome.decision.planner_decision_id == "pd-dc-p7-1"
    assert first.outcome.evaluation.planner_evaluation_id == (
        second.outcome.evaluation.planner_evaluation_id
    )
    other = plan(kernel_input((proposal("c1"),), cycle="dc-other"))
    assert other.outcome.evaluation.planner_evaluation_id == "pe-dc-other"


def test_the_module_reads_no_clock_and_no_random_source() -> None:
    """The kernel's purity, structurally: no import of a clock, a random
    source, an environment or a database, and no *code* that reaches for one.

    The scan is over the syntax tree rather than the text, because the module's
    docstring is allowed — required, in fact — to say the word "random" when it
    states that nothing here consumes one.
    """

    tree = ast.parse(source_text("src/elc/planner/kernel.py"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported == {"__future__", "dataclasses", "enum", "typing", "elc"}
    for forbidden in ("datetime", "time", "random", "uuid", "os", "sqlite3"):
        assert forbidden not in imported

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    for forbidden in (
        "uuid4",
        "environ",
        "getenv",
        "now",
        "utcnow",
        "today",
        "monotonic",
    ):
        assert forbidden not in names, forbidden


def test_the_losers_readings_are_readable_too() -> None:
    """§20 lists a "utility trace" among the things two implementations must
    agree on, and §8's shadow-mode review needs the same thing from the other
    side of the decision: every candidate the run *did not* select still
    carries its factor readings and its score, so "why not that one" is
    answerable from the record."""

    selected = proposal("chosen", benefit=BASE_BENEFIT)
    runner_up = proposal(
        "runner_up",
        canonical_key="runner_up",
        benefit=benefit_vector(learning_need=0.5, context_fit=0.5),
        cost=cost_vector(cognitive_load=0.5),
    )
    excluded = proposal("excluded", canonical_key="excluded", expired=True)
    result = plan(kernel_input((selected, runner_up, excluded)))
    rows = _rows_by_id(result)

    assert rows["chosen"].selected is True
    assert rows["runner_up"].selected is False
    assert rows["runner_up"].utility is not None
    assert rows["runner_up"].benefit_score is not None
    assert len(rows["runner_up"].benefit) == len(BENEFIT_FACTORS)
    assert len(rows["runner_up"].cost) == len(COST_FACTORS)
    for reading in rows["runner_up"].benefit:
        assert reading.value >= 0.0
        assert reading.source.value in ("AUTHORITY", "DECLARED")
    assert rows["excluded"].excluded is not None
    assert result.trace.decision is PlannerDecisionOutcome.SELECT
    assert result.trace.selected_candidate_id == "chosen"


def test_the_utility_trace_carries_the_partial_sums_and_the_path() -> None:
    """§20's "utility trace": the two weighted sums, the adjustment, the
    utility, the activation path and the threshold are readable, so a reviewer
    can recompute the decision instead of trusting it."""

    result = plan(kernel_input((proposal("c1"),)))
    row = result.trace.candidates[0]
    assert row.benefit_score is not None
    assert row.cost_score is not None
    assert row.coverage_service_bonus is not None
    assert row.utility == pytest.approx(
        row.benefit_score - 0.8 * row.cost_score + row.coverage_service_bonus
    )
    assert row.activation_path is not None
    assert row.activation_threshold is not None
    assert row.activated is (row.utility >= row.activation_threshold)
    assert row.selected is True
    assert result.trace.context.execution_status is (
        PlannerExecutionStatusValue.SUCCEEDED
    )
    assert row.excluded is None
    assert row.gaps == ()
