"""P8-0 ②④ — one short transaction, and a replay that is not a re-decision.

The unit is the CP2 commit point (RA §6): the status row, the evaluation row,
the decision row when the run succeeded, the turn's outcome row and the
``decision_cycle`` back-reference — all inside one ``short_transaction``.

The atomicity half is checked the only way that proves anything: a failure
that happens **after** earlier rows were written (an evaluation id already
durable under another cycle) must leave none of them, and a fenced epoch
must leave the world exactly as it was. The replay half is RA §23's two
Planner-side crash windows: a cycle already carrying a status row is
re-decided by nothing, and the honest answer to a re-entry is the durable
records.

The outcome values here are the kernel's own where a real run produces the
shape, and the builder's where it cannot (``FAILED`` / ``UNAVAILABLE``).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.planner.shadow import run_shadow
from elc.planner.types import (
    PlannerDecision,
    PlannerEvaluation,
    PlannerExecutionStatusValue,
    PlanningOutcome,
)
from elc.platform.db import epoch as epoch_module
from elc.platform.db.planner_store import (
    SqlitePlannerRecordStore,
    StalePlannerRecordStoreError,
)
from elc.platform.db.tx import TransactionStateError
from elc.platform.types import (
    DecisionCycleId,
    DomainErrorCode,
    Err,
    Ok,
    PlannerDecisionId,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerVersion,
    PolicyVersion,
    RuntimeDecisionOutcomeValue,
    TurnId,
)
from tests.phase7.conftest import proposal
from tests.phase8.conftest import (
    WATERMARK,
    failed_outcome,
    request_of,
    supply_of,
    table_counts,
)

PLANNER_TABLES = (
    "planner_evaluation",
    "planner_decision",
    "planner_execution_status",
    "runtime_decision_outcome",
)

EMPTY = dict.fromkeys(PLANNER_TABLES, 0)


def _select_run(cycle, **overrides):
    return run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id, **overrides),
        supply=supply_of(proposal("c-p8-0")),
        current_learning_watermark=WATERMARK,
    )


# -- ② one transaction -------------------------------------------------------


def test_one_unit_writes_all_four_records_and_the_back_reference(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    shadow = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    records = written.value

    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 1
    )
    # Every cross-reference the unit promised, read from the rows.
    row = db.execute(
        "SELECT planner_evaluation_id FROM planner_decision"
    ).fetchone()
    assert row == (str(records.evaluation.planner_evaluation_id),)
    pointer = db.execute(
        "SELECT planner_decision_id FROM decision_cycle"
        " WHERE decision_cycle_id = ?",
        (cycle.decision_cycle_id,),
    ).fetchone()
    assert pointer == (str(records.decision.planner_decision_id),)
    outcome = db.execute(
        "SELECT decision_cycle_id FROM runtime_decision_outcome"
        " WHERE turn_id = ?",
        (cycle.turn_id,),
    ).fetchone()
    assert outcome == (str(cycle.decision_cycle_id),)


def test_the_unit_refuses_to_nest(db: sqlite3.Connection, cycle, planner_store) -> None:
    """``short_transaction`` has one owner: a CP2 unit inside another
    transaction would be the long-transaction drift R-INV-004 forbids."""

    shadow = _select_run(cycle)
    db.execute("BEGIN IMMEDIATE")
    with pytest.raises(TransactionStateError):
        planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=shadow.outcome
        )
    db.execute("ROLLBACK")
    assert table_counts(db, *PLANNER_TABLES) == EMPTY


def test_a_unit_that_contradicts_itself_is_refused_before_any_write(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The three cross-reference checks the value types cannot see: the
    evaluation's cycle, the decision's cycle, and the decision's evaluation
    (``_record_refusal``). Each is refused with ``VALIDATION_FAILED`` and the
    world is untouched — the transaction never opens."""

    good = _select_run(cycle).outcome
    cycle_id = cycle.decision_cycle_id
    other_cycle = DecisionCycleId("dc-p8-0-elsewhere")
    status = PlannerExecutionStatusRecord(
        decision_cycle_id=cycle_id,
        status=PlannerExecutionStatusValue.SUCCEEDED,
        error_code=None,
    )
    elsewhere = PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId("pe-x"),
        decision_cycle_id=other_cycle,
        planner_version=good.evaluation.planner_version,
        policy_version=good.evaluation.policy_version,
        ranked_candidates=(),
        reason_trace=(),
    )
    here = PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId("pe-x"),
        decision_cycle_id=cycle_id,
        planner_version=good.evaluation.planner_version,
        policy_version=good.evaluation.policy_version,
        ranked_candidates=(),
        reason_trace=(),
    )
    for outcome in (
        PlanningOutcome(  # the evaluation names another cycle
            evaluation=elsewhere,
            execution_status=status,
            decision=PlannerDecision(
                planner_decision_id=PlannerDecisionId("pd-x"),
                decision_cycle_id=cycle_id,
                decision=PlannerDecisionOutcome.NO_TARGET,
                planner_evaluation_id=PlannerEvaluationId("pe-x"),
            ),
        ),
        PlanningOutcome(  # the decision names another cycle
            evaluation=here,
            execution_status=status,
            decision=PlannerDecision(
                planner_decision_id=PlannerDecisionId("pd-x"),
                decision_cycle_id=other_cycle,
                decision=PlannerDecisionOutcome.NO_TARGET,
                planner_evaluation_id=PlannerEvaluationId("pe-x"),
            ),
        ),
        PlanningOutcome(  # the decision names another evaluation
            evaluation=here,
            execution_status=status,
            decision=PlannerDecision(
                planner_decision_id=PlannerDecisionId("pd-x"),
                decision_cycle_id=cycle_id,
                decision=PlannerDecisionOutcome.NO_TARGET,
                planner_evaluation_id=PlannerEvaluationId("pe-not-this-one"),
            ),
        ),
    ):
        result = planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=outcome
        )
        assert isinstance(result, Err), result
        assert result.error.code is DomainErrorCode.VALIDATION_FAILED
    assert table_counts(db, *PLANNER_TABLES) == EMPTY


def test_a_late_failure_rolls_the_whole_unit_back(
    db: sqlite3.Connection, cycle, second_cycle, planner_store
) -> None:
    """A cycle whose evaluation id is already durable under another cycle:
    the status row is written first and the evaluation insert then fails on
    the primary key, so the rollback has real work to undo.

    What must remain is the *first* cycle's world, unchanged — no status row
    for the second, no evaluation, no decision, and its pointer still NULL.
    """

    first = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=first.outcome
    )
    assert isinstance(written, Ok), written
    before = table_counts(db, *PLANNER_TABLES)
    before_pointers = db.execute(
        "SELECT decision_cycle_id, planner_decision_id FROM decision_cycle"
        " ORDER BY decision_cycle_id"
    ).fetchall()

    colliding_id = written.value.evaluation.planner_evaluation_id
    doomed = PlanningOutcome(
        evaluation=PlannerEvaluation(
            planner_evaluation_id=colliding_id,
            decision_cycle_id=second_cycle.decision_cycle_id,
            planner_version=PlannerVersion("planner-p8-0"),
            policy_version=PolicyVersion("policy-p8-0"),
            ranked_candidates=(),
            reason_trace=(),
        ),
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=second_cycle.decision_cycle_id,
            status=PlannerExecutionStatusValue.SUCCEEDED,
            error_code=None,
        ),
        decision=PlannerDecision(
            planner_decision_id=PlannerDecisionId(
                f"pd-{second_cycle.decision_cycle_id}"
            ),
            decision_cycle_id=second_cycle.decision_cycle_id,
            decision=PlannerDecisionOutcome.NO_TARGET,
            planner_evaluation_id=colliding_id,
            no_target_reason="NO_ELIGIBLE_CANDIDATE",
        ),
    )
    result = planner_store.record_planner_cycle(
        turn_id=second_cycle.turn_id, outcome=doomed
    )
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.CONFLICT
    assert table_counts(db, *PLANNER_TABLES) == before
    assert db.execute(
        "SELECT decision_cycle_id, planner_decision_id FROM decision_cycle"
        " ORDER BY decision_cycle_id"
    ).fetchall() == before_pointers
    unknown = planner_store.get_planner_execution_status(
        second_cycle.decision_cycle_id
    )
    assert isinstance(unknown, Ok) and unknown.value is None


def test_a_stale_epoch_fences_the_unit_and_writes_nothing(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """A newer runtime start makes this store's epoch stale; the fence raises
    inside the transaction, and the unit leaves no row behind."""

    shadow = _select_run(cycle)
    epoch_module.open_runtime_epoch(db)  # a newer start owns the world now
    with pytest.raises(StalePlannerRecordStoreError):
        planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=shadow.outcome
        )
    assert table_counts(db, *PLANNER_TABLES) == EMPTY
    assert db.execute(
        "SELECT planner_decision_id FROM decision_cycle"
        " WHERE decision_cycle_id = ?",
        (cycle.decision_cycle_id,),
    ).fetchone() == (None,)


def test_a_cycle_that_does_not_exist_is_refused(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The four tables hang off a cycle; a unit for a cycle nobody opened is
    a ``NOT_FOUND``, not a row that invents its parent."""

    shadow = _select_run(cycle)
    ghost = PlanningOutcome(
        evaluation=PlannerEvaluation(
            planner_evaluation_id=PlannerEvaluationId("pe-ghost"),
            decision_cycle_id=DecisionCycleId("dc-ghost"),
            planner_version=shadow.outcome.evaluation.planner_version,
            policy_version=shadow.outcome.evaluation.policy_version,
            ranked_candidates=(),
            reason_trace=(),
        ),
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=DecisionCycleId("dc-ghost"),
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code=None,
        ),
        decision=None,
    )
    result = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=ghost
    )
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.NOT_FOUND
    assert table_counts(db, *PLANNER_TABLES) == EMPTY


def test_a_cycle_of_another_turn_is_refused(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The outcome row belongs to the cycle's own turn: a unit that pairs one
    turn with another turn's cycle is refused (the row-level FK would catch
    the reverse order, but the refusal has to name the reason)."""

    shadow = _select_run(cycle)
    result = planner_store.record_planner_cycle(
        turn_id=TurnId("turn-somebody-else"), outcome=shadow.outcome
    )
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.VALIDATION_FAILED
    assert table_counts(db, *PLANNER_TABLES) == EMPTY


# -- ④ the crash windows -----------------------------------------------------


def test_a_second_submission_of_one_cycle_writes_nothing(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """RA §23 "Crash after CP1 … 不重复 Evidence", on the Planner side: a
    re-entry of a decided cycle reads its records back and writes no second
    row."""

    shadow = _select_run(cycle)
    first = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(first, Ok), first
    before_changes = db.total_changes
    before_rows = db.execute(
        "SELECT decision_cycle_id, status, created_at"
        " FROM planner_execution_status"
    ).fetchall()

    second = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(second, Ok), second
    assert second.value == first.value
    assert db.total_changes == before_changes
    assert db.execute(
        "SELECT decision_cycle_id, status, created_at"
        " FROM planner_execution_status"
    ).fetchall() == before_rows
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 1
    )


def test_a_replay_that_differs_in_the_evaluation_or_decision_is_refused(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The three arms of the replay's agreement check: a status word is not
    enough — the evaluation's derived values and the decision are compared
    too, and any difference is a ``CONFLICT`` rather than someone else's row
    returned as if it were the submission's."""

    from dataclasses import replace

    shadow = _select_run(cycle)
    good = shadow.outcome
    assert isinstance(
        planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=good
        ),
        Ok,
    )
    assert good.decision is not None
    for altered in (
        PlanningOutcome(  # same status, different trace
            evaluation=replace(
                good.evaluation, reason_trace=("p8-0: a different trace",)
            ),
            execution_status=good.execution_status,
            decision=good.decision,
        ),
        PlanningOutcome(  # same evaluation, different decision
            evaluation=good.evaluation,
            execution_status=good.execution_status,
            decision=replace(good.decision, no_target_reason="DIFFERENT"),
        ),
    ):
        result = planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=altered
        )
        assert isinstance(result, Err), result
        assert result.error.code is DomainErrorCode.CONFLICT
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 1
    )
    durable = planner_store.get_planner_decision_for_cycle(
        cycle.decision_cycle_id
    )
    assert isinstance(durable, Ok) and durable.value is not None
    assert durable.value == good.decision
    assert durable.value.no_target_reason is None


def test_the_minted_ids_are_the_kernels_deterministic_ones(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """P7-1 mints ``pe-<cycle>`` / ``pd-<cycle>`` with no clock, which is what
    makes the replay above a *replay* rather than a second decision."""

    shadow = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    assert str(written.value.evaluation.planner_evaluation_id) == (
        f"pe-{cycle.decision_cycle_id}"
    )
    assert str(written.value.decision.planner_decision_id) == (
        f"pd-{cycle.decision_cycle_id}"
    )
    assert shadow.planner_evaluation_id == (
        written.value.evaluation.planner_evaluation_id
    )
    pointer = planner_store.get_planner_decision_id(cycle.decision_cycle_id)
    assert isinstance(pointer, Ok)
    assert pointer.value == f"pd-{cycle.decision_cycle_id}"


def test_a_restart_reads_the_durable_decision_and_decides_nothing_again(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The restart shape: a new runtime epoch, a new store over the same
    database, the decision read off the durable row — and a re-entry through
    the new store that writes nothing."""

    shadow = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written

    new_epoch = epoch_module.open_runtime_epoch(db)
    restarted = SqlitePlannerRecordStore(db, new_epoch)
    decision = restarted.get_planner_decision_for_cycle(
        cycle.decision_cycle_id
    )
    assert isinstance(decision, Ok) and decision.value is not None
    assert decision.value.planner_decision_id == (
        written.value.decision.planner_decision_id
    )
    assert decision.value.selected_candidate_id is not None

    before_changes = db.total_changes
    replayed = restarted.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(replayed, Ok), replayed
    assert replayed.value == written.value
    assert db.total_changes == before_changes


def test_a_second_cycle_of_one_turn_moves_the_turns_outcome_row(
    db: sqlite3.Connection, cycle, second_cycle, planner_store
) -> None:
    """A replan is a new cycle on the same turn: the cycle-keyed rows accrete
    (one status / evaluation / decision each), while the turn-keyed outcome
    row moves to the newest cycle — it is the turn's current answer, not a
    history (``elc/planner/records.py`` judgement 2)."""

    first = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=_select_run(cycle).outcome
    )
    assert isinstance(first, Ok), first
    second_shadow = run_shadow(
        request_of(decision_cycle_id=second_cycle.decision_cycle_id),
        supply=supply_of(),
        current_learning_watermark=WATERMARK,
    )
    assert second_shadow.decision is not None  # NO_TARGET is still a decision
    second = planner_store.record_planner_cycle(
        turn_id=second_cycle.turn_id, outcome=second_shadow.outcome
    )
    assert isinstance(second, Ok), second

    assert table_counts(db, *PLANNER_TABLES) == {
        "planner_evaluation": 2,
        "planner_decision": 2,
        "planner_execution_status": 2,
        "runtime_decision_outcome": 1,
    }
    outcome = db.execute(
        "SELECT decision_cycle_id, outcome FROM runtime_decision_outcome"
    ).fetchone()
    assert outcome == (str(second_cycle.decision_cycle_id), "NORMAL")
    # Both cycles keep their own decision and pointer.
    for opened in (cycle, second_cycle):
        pointer = planner_store.get_planner_decision_id(
            opened.decision_cycle_id
        )
        assert isinstance(pointer, Ok)
        assert pointer.value == f"pd-{opened.decision_cycle_id}"


def test_a_degraded_first_cycle_can_still_be_replayed_after_a_newer_one(
    db: sqlite3.Connection, cycle, second_cycle, planner_store
) -> None:
    """The replay of an *older* cycle returns the turn's current outcome row
    (the newest cycle's) — the honest durable state, stated in the record's
    docstring rather than hidden behind a reconstruction."""

    degraded = failed_outcome(
        cycle.decision_cycle_id, PlannerExecutionStatusValue.UNAVAILABLE
    )
    assert isinstance(
        planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=degraded
        ),
        Ok,
    )
    newer = planner_store.record_planner_cycle(
        turn_id=second_cycle.turn_id,
        outcome=run_shadow(
            request_of(decision_cycle_id=second_cycle.decision_cycle_id),
            supply=supply_of(proposal("c-p8-0")),
            current_learning_watermark=WATERMARK,
        ).outcome,
    )
    assert isinstance(newer, Ok), newer

    replay = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=degraded
    )
    assert isinstance(replay, Ok), replay
    assert replay.value.decision is None
    assert replay.value.runtime_decision_outcome is not None
    assert replay.value.runtime_decision_outcome.decision_cycle_id == (
        second_cycle.decision_cycle_id
    )
    assert replay.value.runtime_decision_outcome.outcome is (
        RuntimeDecisionOutcomeValue.NORMAL
    )
