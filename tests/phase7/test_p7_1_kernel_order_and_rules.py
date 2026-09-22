"""P7-1 ① — the decision order as a contract, and BF-02 §5's three hard rules.

docs/DOMAIN_MODEL.md §10.1 fixes an **order** (canonicalize → authoritative
feature assembly → planning-context validity → hard eligibility → policy
utility → coverage-starvation safeguard → per-candidate activation →
explicit-request priority → Pareto prune → near-tie deterministic tie-break →
SELECT / NO_TARGET) and three rules that are not magnitudes but refusals:

- **hard exclusion is not a penalty** — an excluded candidate is never scored,
  and `NO_TARGET` is a decision a *successful* run makes;
- **a missing authoritative view or an invalid snapshot is
  DEGRADED/FAILED/UNAVAILABLE**, never a fabricated `NO_TARGET` — and never a
  `0` standing in for an authority that did not answer;
- **an explicit request is not gated by the automatic threshold**, and §8
  ranks several of them by `request_priority` instead of by name order.

The order is pinned twice: against the canonical block, line for line, and
behaviourally, through the `steps` prefix a stopped run records. A reordering
satisfies neither.
"""

from __future__ import annotations

import ast
import re
from dataclasses import replace

import pytest

from elc.curriculum.readiness import READINESS_LEVELS
from elc.planner.feature_assembly import (
    AuthorityName,
    ScheduleAuthority,
    SnapshotStatus,
)
from elc.planner.kernel import (
    ELIGIBLE_AUTOMATIC_READINESS,
    ELIGIBLE_CURRENT_USER_ERROR_READINESS,
    ELIGIBLE_PROBE_READINESS,
    ELIGIBLE_USER_INITIATED_READINESS,
    KERNEL_STEP_ORDER,
    MODE_ALLOWED_INTENTS,
    READINESS_RANK,
    BenefitFactor,
    CostFactor,
    DegradedReason,
    ExclusionReason,
    FactorSource,
    NoTargetReason,
    PlannerInputError,
    PrerequisiteState,
    ReadinessLevel,
    RuntimeDecisionOutcomeValue,
    plan,
)
from elc.planner.types import (
    LearningIntent,
    PlannerDecision,
    PlannerDecisionOutcome,
    PlanningOutcome,
    TargetMode,
    UserIntentScope,
)
from elc.platform.types import (
    DecisionCycleId,
    PlannerDecisionId,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
)
from elc.scheduler.types import ReviewState

from .conftest import (
    WATERMARK,
    baseline_lines,
    benefit_vector,
    canonical_lines,
    complete_context,
    cost_vector,
    kernel_input,
    kernel_row,
    learning_snapshot,
    portfolio,
    proposal,
    rowless_proposal,
    schedule_view,
    source_text,
)

DOMAIN_MODEL = "DOMAIN_MODEL.md"
BF_02 = "planner/BF-02_Planner_Decision_Spec_v1.1.md"
SECTION_10_1 = "## 10.1 Planner Decision Kernel — Behavioral Baseline V1"
SECTION_10 = "## 10. Readiness 与 runtime-generated content"


def _incomplete_context():
    """BF-02 §5's first condition, through P7-0's real assembly: an authority
    the assembly cannot use makes ``feature_assembly_status`` INCOMPLETE."""

    return complete_context(curriculum_readiness=None)


def _invalid_snapshot_context():
    """The second condition, as P7-0's record can spell it.

    A snapshot whose watermark is older makes P7-0 report **both** INCOMPLETE
    (the LEARNING_SNAPSHOT entry) and INVALID, and the kernel's step 3 reads
    the assembly status first — so the ``snapshot_status = INVALID`` branch is
    reached by a record that only that field says so (the reference suite's
    ``COMPLETE`` + stale-snapshot shape, which P7-0's single verdict folds
    into one). :func:`test_a_real_invalid_snapshot_degrades_for_both_reasons`
    covers the folded case.
    """

    return replace(
        complete_context(), snapshot_status=SnapshotStatus.INVALID
    )


# -- ① the order --------------------------------------------------------------


def test_the_step_order_is_the_canonical_block_line_for_line() -> None:
    """§10.1's fenced block, one value per line, ``→`` dropped and nothing
    else — the pin that makes a reordering a test failure."""

    block = canonical_lines(DOMAIN_MODEL, SECTION_10_1, 0)
    assert len(block) == len(KERNEL_STEP_ORDER) == 11
    assert [line.removeprefix("→ ") for line in block] == [
        step.value for step in KERNEL_STEP_ORDER
    ]
    # Ten of the eleven lines carry the list marker; the first opens the list.
    # Asserted so a document edit that dropped the arrows could not make the
    # comparison above pass by accident.
    assert sum(1 for line in block if line.startswith("→ ")) == 10


def test_a_successful_run_walks_every_step_in_order() -> None:
    result = plan(kernel_input((proposal("c1"),)))
    assert result.trace.steps == KERNEL_STEP_ORDER
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.SUCCEEDED
    )
    assert result.trace.decision is PlannerDecisionOutcome.SELECT
    assert result.trace.selected_candidate_id == "c1"


@pytest.mark.parametrize(
    "context",
    [
        pytest.param(_incomplete_context(), id="incomplete-assembly"),
        pytest.param(_invalid_snapshot_context(), id="invalid-snapshot"),
    ],
)
def test_a_degraded_run_stops_at_context_validity(context) -> None:
    """The prefix a degraded run records is steps 1–3 and no more: hard
    eligibility, utility and everything after it never ran, because scoring a
    vector the assembly could not complete is what §5 forbids."""

    result = plan(kernel_input((proposal("c1"),), context=context))
    assert result.trace.steps == KERNEL_STEP_ORDER[:3]
    assert result.outcome.decision is None
    assert result.trace.decision is None


def test_a_candidate_level_gap_also_stops_at_context_validity() -> None:
    """The reachable candidate-level gap — a target the Scheduler was never
    asked about — is a step-3 verdict too, so the prefix is the same one."""

    result = plan(kernel_input((rowless_proposal("c1"),)))
    assert result.trace.steps == KERNEL_STEP_ORDER[:3]
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FACTOR_AUTHORITY_UNKNOWN.value
    )


# -- ② hard exclusion is not a penalty ---------------------------------------


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        pytest.param({"expired": True}, ExclusionReason.EXPIRED, id="expired"),
        pytest.param(
            {"deprecated": True}, ExclusionReason.DEPRECATED, id="deprecated"
        ),
        pytest.param(
            {"suppressed": True}, ExclusionReason.SUPPRESSED, id="suppressed"
        ),
        pytest.param(
            {"modality_available": False},
            ExclusionReason.MODALITY_UNAVAILABLE,
            id="modality-unavailable",
        ),
        pytest.param(
            {"prerequisite_state": PrerequisiteState.BLOCKED},
            ExclusionReason.HARD_PREREQUISITE_BLOCKED,
            id="hard-prerequisite",
        ),
        pytest.param(
            {"prerequisite_state": PrerequisiteState.UNKNOWN},
            ExclusionReason.PREREQUISITE_UNKNOWN_UNRESOLVED,
            id="prerequisite-unknown",
        ),
        pytest.param(
            {"content_readiness": ReadinessLevel.R1_LEXICALLY_RESOLVED},
            ExclusionReason.CONTENT_NOT_READY,
            id="content-not-ready",
        ),
    ],
)
def test_a_hard_rule_excludes_with_its_own_reason(
    fields: dict, reason: ExclusionReason
) -> None:
    """Per rule: the candidate leaves the set with a name, and it carries **no
    score at all** — a utility would make an exclusion look like a penalty,
    and a penalty is the one thing §10.1 says it is not."""

    result = plan(kernel_input((proposal("c1", **fields),)))
    (row,) = result.trace.candidates
    assert row.excluded is reason
    assert row.benefit_score is None
    assert row.cost_score is None
    assert row.utility is None
    assert row.activation_path is None
    assert row.activated is None
    assert result.trace.decision is PlannerDecisionOutcome.NO_TARGET
    assert result.trace.no_target_reason is (
        NoTargetReason.NO_ELIGIBLE_CANDIDATE
    )
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.SUCCEEDED
    )


@pytest.mark.parametrize(
    ("scope", "reason"),
    [
        pytest.param(
            UserIntentScope.JUST_CHAT,
            ExclusionReason.JUST_CHAT,
            id="just-chat",
        ),
        pytest.param(
            UserIntentScope.TARGETED_LEARNING_REQUEST,
            ExclusionReason.OUTSIDE_TARGETED_SCOPE,
            id="outside-targeted-scope",
        ),
        pytest.param(
            UserIntentScope.NON_LEARNING_TASK,
            ExclusionReason.NON_LEARNING_TASK_SCOPE,
            id="non-learning-task",
        ),
    ],
)
def test_the_scope_words_exclude_rather_than_penalise(
    scope: UserIntentScope, reason: ExclusionReason
) -> None:
    """§12: ``TARGETED_LEARNING_REQUEST`` is "candidate-scope constraint,
    不是普通 bonus" — a constraint the candidate either satisfies or does not."""

    result = plan(kernel_input((proposal("c1"),), scope=scope))
    (row,) = result.trace.candidates
    assert row.excluded is reason
    assert row.utility is None


def test_an_excluded_candidate_cannot_be_selected_however_large_its_factors() -> None:
    """Every factor at its maximum cannot outbid a hard rule — which is the
    whole difference between an exclusion and a very large cost."""

    result = plan(
        kernel_input(
            (
                proposal(
                    "excluded",
                    benefit=benefit_vector(
                        **{factor.value: 1.0 for factor in BenefitFactor}
                    ),
                    cost=cost_vector(
                        **{factor.value: 0.0 for factor in CostFactor}
                    ),
                    suppressed=True,
                ),
            )
        )
    )
    assert result.trace.candidates[0].excluded is ExclusionReason.SUPPRESSED
    assert result.trace.decision is PlannerDecisionOutcome.NO_TARGET


# -- ③ §10's readiness floors -------------------------------------------------


def test_the_readiness_floors_are_bf_02s_four_rows() -> None:
    """§10's table, extracted from the document and compared with the four
    constants the kernel floors on — one ladder, one reading."""

    rows = baseline_lines(BF_02, SECTION_10, 0)
    parsed: dict[str, str] = {}
    for line in rows:
        match = re.match(r"^(.*?)\s+(R\d\+?)$", line)
        assert match, line
        parsed[match.group(1).strip()] = match.group(2)
    assert parsed == {
        "PROBE": "R2+",
        "user-initiated teaching": "R3+",
        "automatic general/review": "R3+",
        "automatic CURRENT_USER_ERROR": "R4",
    }
    assert ELIGIBLE_PROBE_READINESS.startswith("R2")
    assert ELIGIBLE_USER_INITIATED_READINESS.startswith("R3")
    assert ELIGIBLE_AUTOMATIC_READINESS.startswith("R3")
    assert ELIGIBLE_CURRENT_USER_ERROR_READINESS.startswith("R4")
    assert tuple(ReadinessLevel.__members__) == READINESS_LEVELS
    assert [READINESS_RANK[level] for level in ReadinessLevel] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize(
    ("fields", "scope", "readiness", "excluded"),
    [
        pytest.param(
            {"target_mode": TargetMode.PROBE, "learning_intent": LearningIntent.PROBE},
            UserIntentScope.OPEN,
            ReadinessLevel.R1_LEXICALLY_RESOLVED,
            True,
            id="probe-below-r2",
        ),
        pytest.param(
            {"target_mode": TargetMode.PROBE, "learning_intent": LearningIntent.PROBE},
            UserIntentScope.OPEN,
            ReadinessLevel.R2_PLANNER_READY,
            False,
            id="probe-at-r2",
        ),
        pytest.param(
            {"user_initiated": True},
            UserIntentScope.LEARNING_REQUEST,
            ReadinessLevel.R2_PLANNER_READY,
            True,
            id="user-initiated-below-r3",
        ),
        pytest.param(
            {"user_initiated": True},
            UserIntentScope.LEARNING_REQUEST,
            ReadinessLevel.R3_TEACHING_READY,
            False,
            id="user-initiated-at-r3",
        ),
        pytest.param(
            {"origins": ("CURRENT_USER_ERROR",)},
            UserIntentScope.OPEN,
            ReadinessLevel.R3_TEACHING_READY,
            True,
            id="current-user-error-below-r4",
        ),
        pytest.param(
            {"origins": ("CURRENT_USER_ERROR",)},
            UserIntentScope.OPEN,
            ReadinessLevel.R4_DETECTION_READY,
            False,
            id="current-user-error-at-r4",
        ),
    ],
)
def test_each_path_gets_its_own_floor(
    fields: dict, scope: UserIntentScope, readiness: ReadinessLevel, excluded: bool
) -> None:
    result = plan(
        kernel_input(
            (proposal("c1", content_readiness=readiness, **fields),),
            scope=scope,
        )
    )
    (row,) = result.trace.candidates
    assert (row.excluded is ExclusionReason.CONTENT_NOT_READY) is excluded


def test_the_runtime_generated_escape_hatch_is_user_initiated_only() -> None:
    """§10: ``runtime_generated_ready`` is a *user-initiated* escape hatch —
    it can never carry an automatic candidate past its floor ("它**不能**让
    automatic CURRENT_USER_ERROR R1/R2/R3 绕过 R4")."""

    automatic = plan(
        kernel_input(
            (
                proposal(
                    "auto",
                    content_readiness=ReadinessLevel.R1_LEXICALLY_RESOLVED,
                    runtime_generated_ready=True,
                ),
            )
        )
    )
    assert automatic.trace.candidates[0].excluded is (
        ExclusionReason.CONTENT_NOT_READY
    )

    requested = plan(
        kernel_input(
            (
                proposal(
                    "asked",
                    content_readiness=ReadinessLevel.R1_LEXICALLY_RESOLVED,
                    runtime_generated_ready=True,
                    user_initiated=True,
                ),
            ),
            scope=UserIntentScope.LEARNING_REQUEST,
        )
    )
    assert requested.trace.candidates[0].excluded is None
    assert requested.trace.decision is PlannerDecisionOutcome.SELECT


def test_an_explicit_request_is_not_exempt_from_scope_or_readiness() -> None:
    """§10.1's second hard rule exempts an explicit request from the
    *automatic interruption threshold* and from nothing else: "显式 user
    learning request **通过 scope/readiness/prerequisite 后**不使用
    automatic interruption threshold"."""

    result = plan(
        kernel_input(
            (
                proposal(
                    "asked",
                    user_initiated=True,
                    request_aligned=True,
                    content_readiness=ReadinessLevel.R1_LEXICALLY_RESOLVED,
                ),
            ),
            scope=UserIntentScope.TARGETED_LEARNING_REQUEST,
        )
    )
    assert result.trace.candidates[0].excluded is (
        ExclusionReason.CONTENT_NOT_READY
    )
    assert result.trace.decision is PlannerDecisionOutcome.NO_TARGET


# -- ④ §5's degradation rule, and the three-way separation -------------------


def test_a_missing_authority_is_neither_a_zero_nor_a_no_target() -> None:
    """§5's first forbidden case: with the assembly incomplete, a candidate
    whose vector declares ``schedule_urgency = 0.0`` is not scored — the run
    degrades and carries no decision."""

    result = plan(
        kernel_input(
            (proposal("c1", schedule_urgency=0.0),),
            context=_incomplete_context(),
        )
    )
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.DEGRADED
    )
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )
    assert result.outcome.decision is None
    assert result.trace.decision is None
    assert result.trace.no_target_reason is None
    assert result.trace.runtime_outcome is (
        RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING
    )
    assert result.outcome.evaluation.ranked_candidates == ()
    for row in result.trace.candidates:
        assert row.utility is None
        assert row.activated is None


def test_an_invalid_snapshot_is_degraded_and_named() -> None:
    """§5's second forbidden case, with the reference suite's own error code."""

    result = plan(
        kernel_input((proposal("c1"),), context=_invalid_snapshot_context())
    )
    assert result.trace.context.snapshot_status is SnapshotStatus.INVALID
    assert result.outcome.execution_status.error_code == (
        DegradedReason.SNAPSHOT_INVALID.value
    )
    assert result.outcome.decision is None


def test_a_real_invalid_snapshot_degrades_for_both_reasons() -> None:
    """P7-0's own record for a snapshot computed at an older watermark: the
    status is INCOMPLETE *and* the snapshot INVALID, and step 3 reports the
    assembly status while the trace carries both facts."""

    context = complete_context(
        learning_snapshot=learning_snapshot(WATERMARK - 1)
    )
    assert context.snapshot_status is SnapshotStatus.INVALID
    result = plan(kernel_input((proposal("c1"),), context=context))
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )
    assert result.trace.context.snapshot_status is SnapshotStatus.INVALID
    assert result.trace.context.reasons


def test_the_context_verdict_is_read_before_the_candidate_gap() -> None:
    """Both facts can hold at once; the context verdict is read first, so the
    error code names the context condition rather than the per-candidate one."""

    result = plan(
        kernel_input((rowless_proposal("c1"),), context=_invalid_snapshot_context())
    )
    assert result.outcome.execution_status.error_code == (
        DegradedReason.SNAPSHOT_INVALID.value
    )


def test_no_context_at_all_is_unavailable_not_no_target() -> None:
    """A caller who holds no PlanningContext has not found "nothing worth
    teaching" — the run never had what it needs to look."""

    result = plan(kernel_input((proposal("c1"),), context=None))
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.UNAVAILABLE
    )
    assert result.outcome.execution_status.error_code == (
        DegradedReason.PLANNING_CONTEXT_UNAVAILABLE.value
    )
    assert result.outcome.decision is None
    assert result.trace.context.feature_assembly_status is None
    assert result.trace.context.reasons == ()
    assert result.trace.runtime_outcome is (
        RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING
    )


def test_no_target_and_a_degraded_status_are_different_records() -> None:
    """The separation the gate asks for, from the kernel's own output: a
    successful run's NO_TARGET is a ``PlannerDecision``, a degraded run's is
    no record at all, and a FAILED status cannot carry one either."""

    success = plan(kernel_input((proposal("c1", suppressed=True),)))
    assert success.trace.decision is PlannerDecisionOutcome.NO_TARGET
    assert success.outcome.decision is not None
    assert success.outcome.decision.decision is (
        PlannerDecisionOutcome.NO_TARGET
    )

    degraded = plan(
        kernel_input((proposal("c1"),), context=_incomplete_context())
    )
    assert degraded.outcome.decision is None
    assert PlannerDecisionOutcome.NO_TARGET not in set(
        PlannerExecutionStatusValue
    )
    assert PlannerExecutionStatusValue.DEGRADED not in set(
        PlannerDecisionOutcome
    )

    with pytest.raises(ValueError):
        PlanningOutcome(
            evaluation=degraded.outcome.evaluation,
            execution_status=PlannerExecutionStatusRecord(
                decision_cycle_id=DecisionCycleId("dc-p7-1"),
                status=PlannerExecutionStatusValue.FAILED,
            ),
            decision=PlannerDecision(
                planner_decision_id=PlannerDecisionId("pd-p7-1"),
                decision_cycle_id=DecisionCycleId("dc-p7-1"),
                decision=PlannerDecisionOutcome.NO_TARGET,
                planner_evaluation_id=PlannerEvaluationId("pe-p7-1"),
            ),
        )


def test_the_evaluation_record_is_still_built_for_a_degraded_run() -> None:
    """The why of a degraded run lives in its evaluation's ``reason_trace``:
    no ranked candidate, no decision, and the two facts a reader needs."""

    result = plan(
        kernel_input((proposal("c1"),), context=_incomplete_context())
    )
    evaluation = result.outcome.evaluation
    assert evaluation.ranked_candidates == ()
    assert evaluation.planner_version == "pk1"
    assert evaluation.policy_version == (
        "planner-v1.1-reference-2026-09-stress-tested"
    )
    assert evaluation.planner_evaluation_id == "pe-dc-p7-1"
    text = "\n".join(evaluation.reason_trace)
    assert "FEATURE_ASSEMBLY_INCOMPLETE" in text
    assert "no PlannerDecision" in text
    assert "missing_authorities=" in text


# -- ⑤ P7-0's legs, as the kernel consumes them ------------------------------


def _reading_of(result, candidate_id: str, factor: BenefitFactor):
    for row in result.trace.candidates:
        if row.candidate_id == candidate_id:
            for reading in row.benefit:
                if reading.factor is factor:
                    return reading
    raise AssertionError(f"{candidate_id}/{factor} has no reading")


def test_the_schedule_leg_is_the_rows_answer_and_says_so() -> None:
    """``schedule_urgency`` is read through P7-0's conversion: the reading is
    ``AUTHORITY``-sourced and names the Scheduler. A row the Scheduler
    configured no urgency on falls back to BF-02 §6's reference band, and the
    two agree for a row it did configure."""

    stored = plan(kernel_input((proposal("c1", schedule_urgency=0.75),)))
    reading = _reading_of(stored, "c1", BenefitFactor.SCHEDULE_URGENCY)
    assert reading.value == 0.75
    assert reading.source is FactorSource.AUTHORITY
    assert reading.authority is AuthorityName.SCHEDULE

    banded = plan(
        kernel_input(
            (
                proposal(
                    "c1",
                    schedule_urgency=0.75,
                    schedule_row=kernel_row(
                        state=ReviewState.DUE, urgency=None
                    ),
                ),
            )
        )
    )
    assert _reading_of(
        banded, "c1", BenefitFactor.SCHEDULE_URGENCY
    ).value == 0.75


def test_a_row_that_contradicts_the_declared_reading_is_refused() -> None:
    """The factor belongs to the Scheduler: a declared number is accepted only
    when a §5.2 row spells the same one."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (
                    proposal(
                        "c1",
                        schedule_urgency=0.25,
                        schedule_row=kernel_row(urgency=0.75),
                    ),
                )
            )
        )
    assert "schedule_urgency" in str(raised.value)
    assert "Scheduler" in str(raised.value)


def test_a_rowless_candidate_is_a_gap_and_names_the_scheduler() -> None:
    result = plan(kernel_input((rowless_proposal("c1"),)))
    (row,) = result.trace.candidates
    (gap,) = row.gaps
    assert gap.factor is BenefitFactor.SCHEDULE_URGENCY
    assert gap.authority is AuthorityName.SCHEDULE
    assert "never asked" in gap.reason
    assert row.utility is None


def test_a_stale_schedule_authority_refuses_the_declared_reading() -> None:
    """The stale case is a gap at the candidate level *and* an incomplete
    assembly at the context level — two closures of §5, one spelling each."""

    context = complete_context(
        schedule_view=schedule_view(kernel_row(watermark=str(WATERMARK - 1)))
    )
    assert context.schedule_authority is ScheduleAuthority.STALE
    assert AuthorityName.SCHEDULE in context.missing_authorities
    result = plan(kernel_input((proposal("c1"),), context=context))
    (row,) = result.trace.candidates
    (gap,) = row.gaps
    assert gap.authority is AuthorityName.SCHEDULE
    assert "stale" in gap.reason
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )
    assert result.outcome.decision is None


def test_goal_relevance_is_declared_while_its_mapping_is_not_landed() -> None:
    """The second P7-0 leg answers UNKNOWN in this repository, so the declared
    reading is the input §20 names — and the trace labels it as declared."""

    result = plan(kernel_input((proposal("c1"),)))
    reading = _reading_of(result, "c1", BenefitFactor.GOAL_RELEVANCE)
    assert reading.source is FactorSource.DECLARED
    assert reading.authority is None


def test_a_named_missing_goal_mapping_refuses_a_declared_number() -> None:
    """And when the context names that mapping missing, the number is refused
    rather than used — §5's rule, read through P7-0's own entry."""

    context = complete_context(
        goal_portfolio=portfolio(assessment_targets=("ielts-speaking",))
    )
    assert AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING in (
        context.missing_authorities
    )
    result = plan(kernel_input((proposal("c1"),), context=context))
    (row,) = result.trace.candidates
    (gap,) = row.gaps
    assert gap.factor is BenefitFactor.GOAL_RELEVANCE
    assert gap.authority is AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING
    assert result.outcome.decision is None


# -- ⑥ the input contract ----------------------------------------------------


def test_a_duplicate_canonical_key_over_different_candidates_is_refused() -> None:
    """§4's last line: "Kernel 接收到重复 canonical_key 属于 input contract
    error" — under §10.1's step 1 the reachable shape is a duplicate whose
    proposals describe *different* candidates."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (
                    proposal("a", canonical_key="same"),
                    proposal(
                        "b",
                        canonical_key="same",
                        learning_intent=LearningIntent.CONSOLIDATE,
                    ),
                )
            )
        )
    assert "conflicting proposal identity field" in str(raised.value)


def test_a_duplicate_candidate_id_across_two_keys_is_refused() -> None:
    with pytest.raises(PlannerInputError):
        plan(
            kernel_input(
                (
                    proposal("same-id", canonical_key="k1"),
                    proposal("same-id", canonical_key="k2"),
                )
            )
        )


def test_a_mode_intent_pair_outside_bf_02s_table_is_refused() -> None:
    """BF-02's suite: PROBE carries PROBE, REVIEW carries CONSOLIDATE — a pair
    outside the table is an input contract error, not a low score."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (
                    proposal(
                        "inv",
                        target_mode=TargetMode.PROBE,
                        learning_intent=LearningIntent.DEVELOP,
                    ),
                )
            )
        )
    assert "PROBE" in str(raised.value)
    assert set(MODE_ALLOWED_INTENTS) == set(TargetMode)
    for allowed in MODE_ALLOWED_INTENTS.values():
        assert allowed
        assert set(allowed) <= set(LearningIntent)


def test_an_incomplete_factor_vector_is_refused() -> None:
    """§20's contract: the vector is complete or it is not a vector."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (
                    proposal(
                        "short",
                        benefit={
                            BenefitFactor.LEARNING_NEED: 1.0,
                            BenefitFactor.SCHEDULE_URGENCY: 0.75,
                        },
                    ),
                )
            )
        )
    assert "not declared" in str(raised.value)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_a_factor_outside_the_unit_interval_is_refused(value: float) -> None:
    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (proposal("range", benefit=benefit_vector(learning_need=value)),)
            )
        )
    assert "outside" in str(raised.value)


def test_a_scaffolded_candidate_may_not_look_free() -> None:
    """§11: "scaffold 不能被当成'免费 prerequisite'" — the reference floors,
    and the shape that satisfies them."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (
                    proposal(
                        "sc",
                        prerequisite_state=(
                            PrerequisiteState.READY_WITH_SCAFFOLD
                        ),
                        cost=cost_vector(),
                    ),
                )
            )
        )
    assert "support_cost" in str(raised.value)

    paid = plan(
        kernel_input(
            (
                proposal(
                    "sc",
                    prerequisite_state=PrerequisiteState.UNKNOWN,
                    prerequisite_scaffoldable=True,
                    cost=cost_vector(support_cost=0.25, cognitive_load=0.2),
                ),
            )
        )
    )
    assert paid.trace.candidates[0].excluded is None


def test_a_negative_request_priority_is_refused() -> None:
    with pytest.raises(PlannerInputError):
        plan(kernel_input((proposal("c1", request_priority=-1),)))


def test_the_just_chat_contradiction_is_an_upstream_contract_error() -> None:
    """§9, which the kernel quotes: a user-initiated candidate under JUST_CHAT
    is an upstream contract error, and the Planner may not guess which side is
    right."""

    with pytest.raises(PlannerInputError) as raised:
        plan(
            kernel_input(
                (proposal("c1", user_initiated=True),),
                scope=UserIntentScope.JUST_CHAT,
            )
        )
    assert "JUST_CHAT" in str(raised.value)
    assert "upstream contract error" in str(raised.value)


# -- ⑦ the module says what it is -------------------------------------------


#: The first line of one entry of the module's judgement list.
_JUDGEMENT_LINE = re.compile(r"^\d+\. ")


def _declared_judgements() -> tuple[str, ...]:
    """Every numbered entry of the module's "Declared judgements" list, with
    the prose that belongs to it and nothing else.

    The list is read as prose, so an entry ends where the next one begins or
    where a paragraph returns to the margin — which is what makes "each
    judgement carries its own revisit" checkable per entry rather than as one
    substring of the module.
    """

    docstring = ast.get_docstring(
        ast.parse(source_text("src/elc/planner/kernel.py"))
    )
    assert docstring is not None
    entries: list[list[str]] = []
    current: list[str] | None = None
    for line in docstring.splitlines():
        if _JUDGEMENT_LINE.match(line):
            current = [line]
            entries.append(current)
        elif current is not None:
            if line and not line[0].isspace():
                current = None
            else:
                current.append(line)
    return tuple("\n".join(entry) for entry in entries)


def test_the_module_quotes_section_10_1_and_registers_its_judgements() -> None:
    source = source_text("src/elc/planner/kernel.py")
    for line in canonical_lines(DOMAIN_MODEL, SECTION_10_1, 0):
        assert line.removeprefix("→ ") in source, line
    assert "Declared judgements" in source


def test_every_declared_judgement_carries_its_own_revisit() -> None:
    """The module's own claim — "each carries the condition that re-opens it" —
    read one entry at a time, and **per entry**: a whole-file "the word
    ``Revisit:`` appears somewhere" check cannot fail, and an entry without a
    revisit is exactly the thing the claim forbids.

    The floor is the fourteen entries this cut registers; an entry may be added
    with a revisit, and none may be added without one.
    """

    judgements = _declared_judgements()
    assert len(judgements) >= 14
    for judgement in judgements:
        assert "Revisit:" in judgement, judgement


def test_the_module_claims_no_shadow_mode_and_the_service_stays_a_skeleton() -> None:
    """The scope claim, in the module the kernel lives in: no shadow mode, no
    writing, no candidate generation — and the service is still a skeleton."""

    source = source_text("src/elc/planner/kernel.py")
    assert "no shadow mode, no persistence, no UI" in source
    assert "no candidate generation" in source
    service = source_text("src/elc/planner/controller.py")
    assert "NotImplementedError" in service
    assert "shadow mode" in service


# -- ⑧ the canonicalization contract's registered readings -------------------
#
# Three shapes BF-02's frozen 43-case suite answers differently from this
# kernel. They are registered in the module's judgements 8–10 rather than
# decided — and the pins below hold the implementation to the reading it
# registered, so the shadow-mode cut that reproduces the suite meets a recorded
# difference and not a silent one. Each pin carries the note that reproduction
# needs: **p7-4, reproducing the frozen 43 cases, has to model this divergence
# explicitly.**


def test_a_same_key_duplicate_identity_merges_instead_of_raising() -> None:
    """S04's and S42's shape: one ``canonical_key`` carried by two proposals
    that describe the same candidate — same five identity fields, one vector.
    §4's last line makes a duplicate ``canonical_key`` an input contract error,
    and BF-02's suite spells both of these as ``error: true``; this kernel reads
    §4's *merge* as the answer, so the two arrivals become one canonical
    candidate and the trace shows the ids it came from (the repeated id
    included).

    p7-4, reproducing the frozen 43 cases, has to model this divergence
    explicitly (S04: ``d1``/``d2``; S42: ``x`` twice).
    """

    distinct_ids = plan(
        kernel_input(
            (
                proposal("d1", canonical_key="same"),
                proposal("d2", canonical_key="same"),
            )
        )
    )
    (row,) = distinct_ids.trace.candidates
    assert row.candidate_id == "d1"
    assert row.merged_from == ("d1", "d2")
    assert distinct_ids.trace.selected_candidate_id == "d1"

    one_id_twice = plan(
        kernel_input(
            (
                proposal("x", canonical_key="x"),
                proposal("x", canonical_key="x"),
            )
        )
    )
    (row,) = one_id_twice.trace.candidates
    assert row.candidate_id == "x"
    assert row.merged_from == ("x", "x")
    assert one_id_twice.trace.selected_candidate_id == "x"


def test_a_malformed_vector_is_refused_before_the_context_verdict() -> None:
    """S20's shape: a vector that omits a factor **and** an INCOMPLETE context.
    §20's completeness is a contract over the input, and step 2 walks the
    proposals before step 3 reads the context, so the caller hears the contract
    error even where the run would have degraded anyway. The same context with
    a complete vector is ``DEGRADED``, which is what makes this an ordering
    fact rather than a missing degradation rule.

    p7-4, reproducing the frozen 43 cases, has to model this divergence
    explicitly (S20's own ``expected`` is ``error: false`` with
    ``custom: "DEGRADED"``).
    """

    declared = dict(proposal("x").benefit)
    del declared[BenefitFactor.SCHEDULE_URGENCY]
    short = replace(proposal("x"), benefit=declared)
    incomplete = _incomplete_context()

    with pytest.raises(PlannerInputError) as raised:
        plan(kernel_input((short,), context=incomplete))
    assert "schedule_urgency" in str(raised.value)
    assert "not declared" in str(raised.value)

    degraded = plan(kernel_input((proposal("x"),), context=incomplete))
    assert degraded.outcome.execution_status.status is (
        PlannerExecutionStatusValue.DEGRADED
    )
    assert degraded.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )


def test_the_canonicalization_contract_raises_for_four_shapes_only() -> None:
    """The registered reading (judgement 10): a proposal with no key, one key
    with conflicting identity fields, one key with two vectors, and one id
    under two keys — and, crucially, **not** the fourth shape a reader might
    expect on the list, two proposals of one key that agree about everything
    (that is §4's merge, the pin above).

    p7-4, reproducing the frozen 43 cases, has to model this divergence
    explicitly: S04 and S42 are the suite's two ``error: true`` cases this
    kernel reads as merges.
    """

    with pytest.raises(PlannerInputError) as no_key:
        plan(kernel_input((proposal("c1", canonical_key=""),)))
    assert "canonical_key" in str(no_key.value)

    with pytest.raises(PlannerInputError) as identity:
        plan(
            kernel_input(
                (
                    proposal("a", canonical_key="same"),
                    proposal(
                        "b",
                        canonical_key="same",
                        learning_intent=LearningIntent.CONSOLIDATE,
                    ),
                )
            )
        )
    assert "conflicting proposal identity field" in str(identity.value)

    with pytest.raises(PlannerInputError) as vectors:
        plan(
            kernel_input(
                (
                    proposal(
                        "one",
                        canonical_key="one",
                        benefit=benefit_vector(learning_need=0.5),
                    ),
                    proposal(
                        "two",
                        canonical_key="one",
                        benefit=benefit_vector(learning_need=0.9),
                    ),
                )
            )
        )
    assert "factor vector" in str(vectors.value)

    with pytest.raises(PlannerInputError) as shared_id:
        plan(
            kernel_input(
                (
                    proposal("same-id", canonical_key="k1"),
                    proposal("same-id", canonical_key="k2"),
                )
            )
        )
    assert "share a candidate_id" in str(shared_id.value)

    agreed = plan(
        kernel_input((proposal("k"), proposal("k", canonical_key="k")))
    )
    assert len(agreed.trace.candidates) == 1
