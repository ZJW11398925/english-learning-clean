"""P8-0 ③ — decision/status coupling, read off the durable rows.

Every outcome persisted here comes from a **real kernel run**: P7-0's
assembly over a request built from this suite's inputs, P7-1's eleven steps,
and the answer P7-4's shadow face carries. The two shapes the assembly
cannot produce (``FAILED`` / ``UNAVAILABLE`` — "the execution's own
failures", per ``execution_status_of``) are constructed records, and the
builder that makes them says so.

What is asserted is RA §6's coupling as a property of the data:

- ``SUCCEEDED`` + ``SELECT`` ⟹ a decision row naming the selected candidate;
- ``SUCCEEDED`` + ``NO_TARGET`` ⟹ a decision row with a reason and no
  candidate;
- ``DEGRADED`` / ``FAILED`` / ``UNAVAILABLE`` ⟹ **no** decision row, a
  ``runtime_decision_outcome`` of ``DEGRADED_NO_AUTOMATIC_TEACHING``, and a
  NULL back-reference (§14 line 889: degradation is not a decision).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.planner.shadow import run_shadow
from elc.planner.trace_document import (
    FACTOR_TRACE_PROVENANCE_NONE,
    FACTOR_TRACE_VERSION,
)
from elc.planner.types import PlannerExecutionStatusValue
from elc.platform.types import (
    DecisionCycleId,
    DomainErrorCode,
    Err,
    FactorTraceDocument,
    Ok,
    RuntimeDecisionOutcomeValue,
)
from elc.scheduler.types import ReviewState
from tests.phase7.conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    USER,
    WATERMARK,
    constraint,
    learning_snapshot,
    portfolio,
    proposal,
    schedule_item,
    teaching_policy,
)
from tests.phase8.conftest import (
    failed_outcome,
    open_cycle,
    request_of,
    supply_of,
    table_counts,
)


def _decision_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT planner_decision_id, decision, selected_candidate_id,"
        " no_target_reason FROM planner_decision ORDER BY planner_decision_id"
    ).fetchall()


# -- the real chain ----------------------------------------------------------


def test_a_real_select_run_lands_the_four_records(
    db: sqlite3.Connection,
    cycle,
    planner_store,
    user_config_store,
    user_config_controller,
    learning_controller,
    scheduler_store,
    wired_scheduler,
) -> None:
    """The whole chain, once: real durable §5.1/§5.2 rows read through the
    real faces, a real §5.2 row in the run's schedule view, the real kernel,
    and then the CP2 unit. The kernel's own answer — not a hand-built record
    — is what the durable rows are compared against."""

    assert isinstance(
        user_config_store.upsert_teaching_policy(teaching_policy()), Ok
    )
    assert isinstance(
        user_config_store.upsert_goal_portfolio(
            portfolio(assessment_targets=())
        ),
        Ok,
    )
    assert isinstance(
        user_config_store.record_planner_constraint(constraint()), Ok
    )
    watermark = learning_controller.get_learning_watermark()
    assert isinstance(watermark, Ok)
    row = schedule_item(
        "si-p8-0",
        review_state=ReviewState.DUE,
        urgency=0.75,
        window_start=DAY_ONE,
        window_end=DAY_THREE,
        watermark=str(watermark.value),
        version="sv-p8-0",
    )
    assert isinstance(scheduler_store.upsert_schedule_item(row), Ok)

    policy = user_config_controller.get_teaching_policy(USER)
    goals = user_config_controller.get_goal_portfolio(USER)
    constraints = user_config_controller.get_planner_constraint_view(
        DAY_TWO, CONV
    )
    schedule = wired_scheduler.get_schedule_view(DAY_TWO)
    for result in (policy, goals, constraints, schedule):
        assert isinstance(result, Ok), result
    assert schedule.value.due_items, "the §5.2 row did not reach the view"

    shadow = run_shadow(
        request_of(
            decision_cycle_id=cycle.decision_cycle_id,
            learning_snapshot=learning_snapshot(watermark.value),
            schedule_view=schedule.value,
            teaching_policy_view=policy.value,
            goal_view=goals.value,
            planner_constraint_view=constraints.value,
        ),
        supply=supply_of(
            proposal(
                "c-p8-0",
                schedule_row=row,
                schedule_urgency=row.review_urgency,
            )
        ),
        current_learning_watermark=watermark.value,
    )
    assert shadow.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    assert shadow.decision is not None
    assert shadow.would_have_selected == "c-p8-0"

    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    records = written.value

    assert records.execution_status.status is (
        PlannerExecutionStatusValue.SUCCEEDED
    )
    assert records.decision is not None
    assert str(records.decision.selected_candidate_id) == "c-p8-0"
    assert records.decision.no_target_reason is None
    assert records.evaluation.ranked_candidate_ids == ("c-p8-0",)
    assert records.evaluation.frontier_candidate_ids == ("c-p8-0",)
    # P9-0 moved this column from the bare prose array to the versioned
    # document (elc/planner/records.py judgement 9). The old assertion —
    # ``factor_trace == shadow.why`` — pinned "the column *is* the prose";
    # this one pins "the column is the structured document whose ``reasons``
    # are the prose", which is the same claim about the prose plus the
    # provenance word and the candidates array beside it. This call passes no
    # trace, so the honest document says NOT_RECORDED (P9-0's own suite drives
    # the traced case: tests/phase9/test_p9_0_factor_trace_document.py).
    document = records.evaluation.factor_trace
    assert isinstance(document, FactorTraceDocument)
    assert document.version == FACTOR_TRACE_VERSION
    assert document.provenance == FACTOR_TRACE_PROVENANCE_NONE
    assert document.reasons == shadow.why
    assert document.candidates == ()
    assert records.runtime_decision_outcome is not None
    assert records.runtime_decision_outcome.outcome is (
        RuntimeDecisionOutcomeValue.NORMAL
    )
    assert records.runtime_decision_outcome.decision_cycle_id == (
        cycle.decision_cycle_id
    )
    pointer = planner_store.get_planner_decision_id(cycle.decision_cycle_id)
    assert isinstance(pointer, Ok)
    assert pointer.value == records.decision.planner_decision_id


def test_a_real_no_target_run_lands_no_target_with_its_reason(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """A successful run that found nothing to select is a *decision*
    (``NO_TARGET`` with its reason) and a ``NORMAL`` turn — not a second
    spelling of degradation."""

    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(),
        current_learning_watermark=WATERMARK,
    )
    assert shadow.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    assert shadow.decision is not None and shadow.decision.value == "NO_TARGET"

    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    decision = written.value.decision
    assert decision is not None
    assert decision.decision.value == "NO_TARGET"
    assert decision.selected_candidate_id is None
    assert decision.no_target_reason is not None
    assert written.value.evaluation.ranked_candidate_ids == ()
    assert written.value.runtime_decision_outcome.outcome is (
        RuntimeDecisionOutcomeValue.NORMAL
    )


def test_a_real_degraded_run_lands_a_status_and_no_decision(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The assembly's degraded word, persisted: a status row, an evaluation
    row (the trace of what it could not read), **no** decision row, a
    ``DEGRADED_NO_AUTOMATIC_TEACHING`` outcome, and a NULL pointer."""

    shadow = run_shadow(
        request_of(
            decision_cycle_id=cycle.decision_cycle_id,
            learning_snapshot=None,
        ),
        supply=supply_of(proposal("c-p8-0")),
        current_learning_watermark=None,
    )
    assert shadow.execution_status is PlannerExecutionStatusValue.DEGRADED
    assert shadow.decision is None

    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    assert written.value.decision is None
    assert written.value.runtime_decision_outcome.outcome is (
        RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING
    )
    assert _decision_rows(db) == []
    pointer = planner_store.get_planner_decision_id(cycle.decision_cycle_id)
    assert isinstance(pointer, Ok) and pointer.value is None
    counts = table_counts(db, "planner_evaluation", "planner_execution_status")
    assert counts == {"planner_evaluation": 1, "planner_execution_status": 1}


@pytest.mark.parametrize(
    "status",
    [
        PlannerExecutionStatusValue.DEGRADED,
        PlannerExecutionStatusValue.FAILED,
        PlannerExecutionStatusValue.UNAVAILABLE,
    ],
)
def test_every_failure_word_persists_a_status_and_no_decision(
    db: sqlite3.Connection,
    fence,
    cycle,
    planner_store,
    status: PlannerExecutionStatusValue,
) -> None:
    """The three words RA §6 names, one by one: each lands a status row, a
    ``DEGRADED_NO_AUTOMATIC_TEACHING`` outcome and a NULL pointer — and no
    decision row anywhere. (``FAILED`` / ``UNAVAILABLE`` are constructed
    records: the assembly does not produce them.)"""

    opened = open_cycle(
        db,
        fence,
        decision_cycle_id=DecisionCycleId(f"dc-p8-0-{status.value.lower()}"),
        turn_id=cycle.turn_id,
        expected_turn_state_version=cycle.state_version,
    )
    outcome = failed_outcome(opened.decision_cycle_id, status)
    written = planner_store.record_planner_cycle(
        turn_id=opened.turn_id, outcome=outcome
    )
    assert isinstance(written, Ok), written
    assert written.value.execution_status.status is status
    assert written.value.execution_status.error_code == "STORE_UNREADABLE"
    assert written.value.decision is None
    assert written.value.runtime_decision_outcome.outcome is (
        RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING
    )
    assert _decision_rows(db) == []
    assert db.execute(
        "SELECT planner_decision_id FROM decision_cycle"
        " WHERE decision_cycle_id = ?",
        (opened.decision_cycle_id,),
    ).fetchone() == (None,)


def test_success_and_failure_are_one_word_apart_in_the_data(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """One successful run and one constructed failure over **one** cycle's
    world: the same status table, two rows; the same outcome table, two
    values; and the decision table holding exactly the success's row."""

    select = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(proposal("c-p8-0")),
        current_learning_watermark=WATERMARK,
    )
    assert isinstance(
        planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=select.outcome
        ),
        Ok,
    )
    degraded = failed_outcome(
        cycle.decision_cycle_id, PlannerExecutionStatusValue.FAILED
    )
    replay = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=degraded
    )
    # A second submission of one cycle cannot switch it to a failure: the
    # durable status row is the decision's, and the refusal is a CONFLICT
    # rather than a rewrite (elc/planner/records.py judgement 3).
    assert isinstance(replay, Err)
    assert replay.error.code is DomainErrorCode.CONFLICT
    rows = _decision_rows(db)
    assert len(rows) == 1 and rows[0][1] == "SELECT"
    outcomes = db.execute(
        "SELECT outcome FROM runtime_decision_outcome"
    ).fetchall()
    assert outcomes == [("NORMAL",)]
