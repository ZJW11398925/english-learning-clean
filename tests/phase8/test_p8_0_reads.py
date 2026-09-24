"""P8-0 ⑤ — the five reads, round-tripped and pinned against the rows.

Every read answers ``Ok(None)`` for an unknown id (the
``SqliteDecisionCycleStore`` precedent: an absent row is a fact, not an
error), every record's fields come back exactly as they went in, and the
TEXT list columns are checked **at the byte level**: the two id columns
against the deterministic JSON document ``elc/teaching/store.py``'s
``_array_document`` produces — one encoding, reused — and ``factor_trace``
against the versioned document P9-0 moved it to (its own test spells the
payload's keys and the per-candidate field set a second time, so the pin is
not the encoder asserting itself).
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3

import pytest

from elc.planner.kernel import CandidateTrace
from elc.planner.shadow import run_shadow
from elc.planner.trace_document import factor_trace_document
from elc.platform.types import (
    DecisionCycleId,
    FactorTraceDocument,
    Ok,
    PlannerDecisionId,
    PlannerEvaluationId,
    PlannerExecutionStatusValue,
    RuntimeDecisionOutcomeValue,
    TurnId,
)
from tests.phase7.conftest import proposal
from tests.phase8.conftest import (
    WATERMARK,
    failed_outcome,
    open_cycle,
    request_of,
    supply_of,
)


def _write_select(cycle, planner_store, *candidate_ids: str):
    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(*(proposal(cid) for cid in candidate_ids)),
        current_learning_watermark=WATERMARK,
    )
    assert shadow.would_have_selected == candidate_ids[0]
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    return written.value


# -- the unknown-id face -----------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda store, cycle: store.get_planner_execution_status(
            DecisionCycleId("dc-unknown")
        ),
        lambda store, cycle: store.get_planner_evaluation(
            PlannerEvaluationId("pe-unknown")
        ),
        lambda store, cycle: store.get_planner_decision(
            PlannerDecisionId("pd-unknown")
        ),
        lambda store, cycle: store.get_planner_decision_for_cycle(
            DecisionCycleId("dc-unknown")
        ),
        lambda store, cycle: store.get_runtime_decision_outcome(
            TurnId("turn-unknown")
        ),
        lambda store, cycle: store.get_planner_decision_id(
            DecisionCycleId("dc-unknown")
        ),
    ],
)
def test_every_read_answers_ok_none_for_an_unknown_id(
    cycle, planner_store, call
) -> None:
    result = call(planner_store, cycle)
    assert isinstance(result, Ok), result
    assert result.value is None


# -- the round trips ---------------------------------------------------------


def test_the_evaluation_round_trips_column_for_column(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    records = _write_select(cycle, planner_store, "c-p8-0")
    read = planner_store.get_planner_evaluation(
        records.evaluation.planner_evaluation_id
    )
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == records.evaluation
    assert read.value.created_at  # the store's stamp is on the row


def test_the_decision_reads_by_its_own_id_and_by_its_cycle(
    cycle, planner_store
) -> None:
    records = _write_select(cycle, planner_store, "c-p8-0")
    assert records.decision is not None
    by_id = planner_store.get_planner_decision(
        records.decision.planner_decision_id
    )
    by_cycle = planner_store.get_planner_decision_for_cycle(
        cycle.decision_cycle_id
    )
    for result in (by_id, by_cycle):
        assert isinstance(result, Ok) and result.value is not None
        assert result.value == records.decision
    assert by_id.value.planner_evaluation_id == (
        records.evaluation.planner_evaluation_id
    )


def test_the_status_round_trips_with_and_without_an_error_code(
    db: sqlite3.Connection, fence, cycle, planner_store
) -> None:
    """The two faces §14 gives ``error_code?``: absent for a run that
    succeeded, present for one that failed with a named code."""

    records = _write_select(cycle, planner_store, "c-p8-0")
    succeeded = planner_store.get_planner_execution_status(
        cycle.decision_cycle_id
    )
    assert isinstance(succeeded, Ok) and succeeded.value is not None
    assert succeeded.value.status is PlannerExecutionStatusValue.SUCCEEDED
    assert succeeded.value.error_code is None
    assert succeeded.value == records.execution_status

    opened = open_cycle(
        db,
        fence,
        decision_cycle_id=DecisionCycleId("dc-p8-0-error"),
        turn_id=cycle.turn_id,
        expected_turn_state_version=cycle.state_version,
    )
    failed = failed_outcome(
        opened.decision_cycle_id, PlannerExecutionStatusValue.FAILED
    )
    written = planner_store.record_planner_cycle(
        turn_id=opened.turn_id, outcome=failed
    )
    assert isinstance(written, Ok), written
    read = planner_store.get_planner_execution_status(
        opened.decision_cycle_id
    )
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == written.value.execution_status
    assert read.value.error_code == "STORE_UNREADABLE"


def test_the_outcome_round_trips_and_the_optional_cycle_column_is_honest(
    db: sqlite3.Connection, cycle, other_turn, planner_store
) -> None:
    """The turn-keyed row: written with the unit's own ``reason_codes``, read
    back verbatim — and a row for a turn with no cycle (the column is ``?``)
    decodes to ``None`` rather than to an invented word."""

    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(proposal("c-p8-0")),
        current_learning_watermark=WATERMARK,
    )
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id,
        outcome=shadow.outcome,
        reason_codes=("USER_REQUESTED_TEACHING", "CYCLE_FRESH"),
    )
    assert isinstance(written, Ok), written
    read = planner_store.get_runtime_decision_outcome(cycle.turn_id)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value == written.value.runtime_decision_outcome
    assert read.value.reason_codes == (
        "USER_REQUESTED_TEACHING",
        "CYCLE_FRESH",
    )
    assert read.value.decision_cycle_id == cycle.decision_cycle_id

    db.execute(
        "INSERT INTO runtime_decision_outcome ("
        " turn_id, decision_cycle_id, outcome, reason_codes, created_at"
        ") VALUES (?, NULL, 'NORMAL', '[]', 'now')",
        (other_turn,),
    )
    bare = planner_store.get_runtime_decision_outcome(other_turn)
    assert isinstance(bare, Ok) and bare.value is not None
    assert bare.value.decision_cycle_id is None
    assert bare.value.reason_codes == ()
    assert bare.value.outcome is RuntimeDecisionOutcomeValue.NORMAL


def test_the_empty_degraded_shapes_round_trip_as_empty_tuples(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """A degraded run has no ranking and no frontier; the columns carry ``[]``
    and the reads answer ``()`` — not ``None``, which would claim a missing
    authority where the honest value is "nothing was ranked"."""

    degraded = failed_outcome(
        cycle.decision_cycle_id, PlannerExecutionStatusValue.UNAVAILABLE
    )
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=degraded
    )
    assert isinstance(written, Ok), written
    read = planner_store.get_planner_evaluation(
        written.value.evaluation.planner_evaluation_id
    )
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.ranked_candidate_ids == ()
    assert read.value.frontier_candidate_ids == ()
    assert read.value.factor_trace == written.value.evaluation.factor_trace
    assert read.value.factor_trace


def test_the_back_reference_read_answers_the_three_shapes(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """Unknown cycle → ``None``; a cycle whose planner half has not run →
    ``None``; a decided cycle → the decision id. (The first two are told
    apart by the cycle's own read face, which is ``SqliteDecisionCycleStore``'s
    and is why this read does not raise.)"""

    unknown = planner_store.get_planner_decision_id(
        DecisionCycleId("dc-unknown")
    )
    assert isinstance(unknown, Ok) and unknown.value is None
    undecided = planner_store.get_planner_decision_id(cycle.decision_cycle_id)
    assert isinstance(undecided, Ok) and undecided.value is None
    records = _write_select(cycle, planner_store, "c-p8-0")
    assert records.decision is not None
    decided = planner_store.get_planner_decision_id(cycle.decision_cycle_id)
    assert isinstance(decided, Ok)
    assert decided.value == records.decision.planner_decision_id


# -- the encoding ------------------------------------------------------------


def test_the_list_columns_are_the_deterministic_array_documents(
    db: sqlite3.Connection, fence, cycle, planner_store
) -> None:
    """The JSON shape of the two **id** columns is ``elc/teaching/store.py``'s
    ``_array_document``, reused: ``json.dumps(list, sort_keys=True,
    separators=(",", ":"))`` — asserted at the byte level, on the rows
    themselves.

    P9-0 moved the third column this test used to pin beside them: the
    ``factor_trace`` bytes are no longer the array of lines (the old
    assertion) but the versioned document. Its storage shape is stated
    independently of ``elc.planner.trace_document`` at the **JSON** layer —
    the four-key object below is hand-written for the untraced row, and the
    traced row's payload is read back with ``json.loads`` and compared
    against the kernel's own field set — while the byte-level arms compare
    the row against the encoder's own bytes
    (``row[2] == factor_trace_document(…)``): the encoder is the thing whose
    determinism those arms witness, not a second spelling of the document.
    """

    records = _write_select(cycle, planner_store, "c-p8-0")
    row = db.execute(
        "SELECT frontier_candidate_ids, ranked_candidate_ids, factor_trace"
        " FROM planner_evaluation WHERE planner_evaluation_id = ?",
        (records.evaluation.planner_evaluation_id,),
    ).fetchone()
    assert row is not None
    expected_frontier = json.dumps(
        ["c-p8-0"], sort_keys=True, separators=(",", ":")
    )
    assert row[0] == expected_frontier
    assert row[1] == expected_frontier
    document = records.evaluation.factor_trace
    assert isinstance(document, FactorTraceDocument)
    assert row[2] == factor_trace_document(document)
    assert json.loads(row[2]) == {
        "version": "ft1",
        "provenance": "NOT_RECORDED",
        "reasons": list(document.reasons),
        "candidates": [],
    }
    outcome_row = db.execute(
        "SELECT reason_codes FROM runtime_decision_outcome WHERE turn_id = ?",
        (cycle.turn_id,),
    ).fetchone()
    assert outcome_row == ("[]",)

    # A one-member document cannot tell the compact spelling from the default
    # one — ``json.dumps(["c-p8-0"])`` is the same bytes either way — so the
    # id columns' encoding is pinned again on **two-member** documents. (A
    # second cycle on the same turn: re-submitting the first would be a
    # refused replay, and _write_select cannot carry reason_codes.)
    opened = open_cycle(
        db,
        fence,
        decision_cycle_id=DecisionCycleId("dc-p8-0-two"),
        turn_id=cycle.turn_id,
        expected_turn_state_version=cycle.state_version,
    )
    shadow = run_shadow(
        request_of(decision_cycle_id=opened.decision_cycle_id),
        supply=supply_of(proposal("c-a"), proposal("c-b")),
        current_learning_watermark=WATERMARK,
    )
    assert shadow.would_have_selected == "c-a"
    second = planner_store.record_planner_cycle(
        turn_id=opened.turn_id,
        outcome=shadow.outcome,
        reason_codes=("REASON_A", "REASON_B"),
        trace=shadow.trace,
    )
    assert isinstance(second, Ok), second
    compact_ids = json.dumps(
        ["c-a", "c-b"], sort_keys=True, separators=(",", ":")
    )
    compact_reasons = json.dumps(
        ["REASON_A", "REASON_B"], sort_keys=True, separators=(",", ":")
    )
    row = db.execute(
        "SELECT frontier_candidate_ids, ranked_candidate_ids, factor_trace"
        " FROM planner_evaluation WHERE planner_evaluation_id = ?",
        (second.value.evaluation.planner_evaluation_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == compact_ids
    assert row[1] == compact_ids
    traced = second.value.evaluation.factor_trace
    assert isinstance(traced, FactorTraceDocument)
    # The row is the encoder's own bytes, and the payload says what the
    # column carries at the JSON level: the four keys, the run's prose, and —
    # per candidate — exactly the kernel's own field set (the completeness
    # claim of P9-0's document, checked against `dataclasses.fields`).
    assert row[2] == factor_trace_document(traced)
    payload = json.loads(row[2])
    assert set(payload) == {"version", "provenance", "reasons", "candidates"}
    assert payload["version"] == "ft1"
    assert payload["provenance"] == "KERNEL_TRACE"
    assert payload["reasons"] == list(traced.reasons)
    assert [c["candidate_id"] for c in payload["candidates"]] == ["c-a", "c-b"]
    for candidate in payload["candidates"]:
        assert set(candidate) == {
            field.name for field in dataclasses.fields(CandidateTrace)
        }
    selected = next(
        c for c in payload["candidates"] if c["candidate_id"] == "c-a"
    )
    assert selected["selected"] is True
    assert selected["utility"] is not None
    assert selected["benefit"] and selected["cost"]
    outcome_row = db.execute(
        "SELECT reason_codes FROM runtime_decision_outcome WHERE turn_id = ?",
        (opened.turn_id,),
    ).fetchone()
    assert outcome_row == (compact_reasons,)


def test_the_reads_do_not_write(db: sqlite3.Connection, cycle, planner_store) -> None:
    """A read is a read: the five faces leave ``total_changes`` where they
    found it."""

    _write_select(cycle, planner_store, "c-p8-0")
    before = db.total_changes
    planner_store.get_planner_execution_status(cycle.decision_cycle_id)
    planner_store.get_planner_evaluation(PlannerEvaluationId("pe-unknown"))
    planner_store.get_planner_decision(PlannerDecisionId("pd-unknown"))
    planner_store.get_planner_decision_for_cycle(cycle.decision_cycle_id)
    planner_store.get_runtime_decision_outcome(cycle.turn_id)
    planner_store.get_planner_decision_id(cycle.decision_cycle_id)
    assert db.total_changes == before
