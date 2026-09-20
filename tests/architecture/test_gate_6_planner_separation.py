"""Gate item 6 — PlannerDecision(NO_TARGET) and PlannerExecutionStatus are
completely separated.

docs/IMPLEMENTATION_PLAN.md §2 Gate; docs/DOMAIN_MODEL.md §10 ("Planner
failure/unavailable 不伪装成 PlannerDecision"); docs/DATA_MODEL.md §14
("Runtime degradation is not a PlannerDecision"). Verified structurally:
separate enum types with disjoint members/values, record dataclasses with
disjoint fields, and PlanningOutcome enforcing decision XOR status.
"""

from __future__ import annotations

import pytest

from elc.planner import (
    PlanningOutcome,
    PlannerEvaluation,
    PlannerDecisionOutcome,
    PlannerExecutionStatusValue,
)
from elc.planner.types import PlannerDecision, PlannerExecutionStatusRecord
from elc.platform.types import (
    DecisionCycleId,
    PlannerDecisionId,
    PlannerEvaluationId,
    PlannerVersion,
    PolicyVersion,
    RuntimeDecisionOutcomeValue,
)


def _decision() -> PlannerDecision:
    return PlannerDecision(
        planner_decision_id=PlannerDecisionId("pd-1"),
        decision_cycle_id=DecisionCycleId("dc-1"),
        decision=PlannerDecisionOutcome.NO_TARGET,
        planner_evaluation_id=PlannerEvaluationId("pe-1"),
    )


def test_decision_and_status_enums_are_distinct_types() -> None:
    assert PlannerDecisionOutcome is not PlannerExecutionStatusValue
    assert type(PlannerDecisionOutcome.NO_TARGET).__name__ == "PlannerDecisionOutcome"
    assert (
        type(PlannerExecutionStatusValue.DEGRADED).__name__
        == "PlannerExecutionStatusValue"
    )
    assert not isinstance(PlannerDecisionOutcome.NO_TARGET, PlannerExecutionStatusValue)
    assert not isinstance(
        PlannerExecutionStatusValue.DEGRADED, PlannerDecisionOutcome
    )


def test_decision_and_status_vocabularies_are_disjoint() -> None:
    decision_names = set(PlannerDecisionOutcome.__members__)
    status_names = set(PlannerExecutionStatusValue.__members__)
    assert decision_names == {"SELECT", "NO_TARGET"}
    assert status_names == {"SUCCEEDED", "DEGRADED", "FAILED", "UNAVAILABLE"}
    assert decision_names & status_names == set()
    decision_values = {member.value for member in PlannerDecisionOutcome}
    status_values = {member.value for member in PlannerExecutionStatusValue}
    assert decision_values & status_values == set()


def test_decision_and_status_records_are_structurally_incompatible() -> None:
    decision = _decision()
    assert not hasattr(decision, "status")
    assert not hasattr(decision, "error_code")
    status = PlannerExecutionStatusRecord(
        decision_cycle_id=DecisionCycleId("dc-1"),
        status=PlannerExecutionStatusValue.DEGRADED,
        error_code="SNAPSHOT_INVALID",
    )
    assert not hasattr(status, "no_target_reason")
    assert not hasattr(status, "selected_candidate_id")
    assert not hasattr(status, "decision")


def test_degraded_status_cannot_masquerade_as_decision_record() -> None:
    """PlannerExecutionStatusValue members are not accepted as a decision."""
    for status in PlannerExecutionStatusValue:
        assert status not in set(PlannerDecisionOutcome)


def test_runtime_degradation_is_not_a_planner_decision() -> None:
    assert RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING not in (
        set(PlannerDecisionOutcome)
    )
    assert RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING not in (
        set(PlannerExecutionStatusValue)
    )


def _evaluation() -> PlannerEvaluation:
    return PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId("pe-1"),
        decision_cycle_id=DecisionCycleId("dc-1"),
        planner_version=PlannerVersion("planner-v1"),
        policy_version=PolicyVersion("policy-v1"),
        ranked_candidates=(),
        reason_trace=(),
    )


def test_planning_outcome_enforces_decision_xor_status() -> None:
    with pytest.raises(ValueError):
        PlanningOutcome(
            evaluation=_evaluation(),
            decision=_decision(),
            execution_status=PlannerExecutionStatusRecord(
                decision_cycle_id=DecisionCycleId("dc-1"),
                status=PlannerExecutionStatusValue.DEGRADED,
            ),
        )
    with pytest.raises(ValueError):
        PlanningOutcome(evaluation=_evaluation(), decision=None, execution_status=None)

    decision_only = PlanningOutcome(
        evaluation=_evaluation(), decision=_decision(), execution_status=None
    )
    degraded_only = PlanningOutcome(
        evaluation=_evaluation(),
        decision=None,
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=DecisionCycleId("dc-1"),
            status=PlannerExecutionStatusValue.UNAVAILABLE,
        ),
    )
    assert decision_only.decision is not None and decision_only.execution_status is None
    assert degraded_only.decision is None and degraded_only.execution_status is not None
