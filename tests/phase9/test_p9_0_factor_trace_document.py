"""P9-0 (A) — the durable ``factor_trace`` document, end to end.

docs/DATA_MODEL.md §14's ``factor_trace`` carried the run's prose reasons and
none of what the kernel looked at (the P8 review's carryover finding, MEDIUM).
This cut's A ruling: the column carries the versioned structured document
``elc.planner.trace_document`` defines, the writer takes the run's
``PlannerTrace`` and puts its candidates in, and the read face answers the
decoded document — while a row written before this cut is still answered as
the bare lines it was.

What is pinned here, module by module:

- **the document** — its four keys, its version word, and the **completeness**
  claim (every field of the kernel's ``CandidateTrace`` has a field of the
  document's, name for name, so a kernel field added later fails this file);
- **determinism** — same input, same bytes; the canonicalization rules
  (candidates by id, readings by factor name) and the orders that are kept
  (the prose, ``merged_from``, ``dominated_by``);
- **the round trip** — decode(encode(document)) is the document, and
  encode(decode(bytes)) is the bytes;
- **the durable column** — a real shadow run's trace lands in the row, the
  read face parses it back, and a row written without a trace says so;
- **the legacy arm** — a pre-cut row (a JSON array of lines) is read as the
  tuple it always was, and it cannot be replayed by a post-cut document;
- **the automatic path** — the shipped turn wiring hands its trace in, so the
  production row is a real trace and not ``NOT_RECORDED``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields, replace

import pytest

from elc.planner import kernel as kernel_module
from elc.planner.shadow import run_shadow
from elc.planner.trace_document import (
    FACTOR_TRACE_PROVENANCE_KERNEL,
    FACTOR_TRACE_PROVENANCE_NONE,
    FACTOR_TRACE_VERSION,
    decode_factor_trace,
    factor_trace_document,
    factor_trace_of,
)
from elc.planner.types import PlannerExecutionStatusValue
from elc.platform.types import (
    CandidateTraceDocument,
    DomainErrorCode,
    FactorTraceDocument,
    Ok,
)
from tests.phase7.conftest import kernel_row, proposal, rowless_proposal
from tests.phase8.conftest import (
    WATERMARK,
    failed_outcome,
    request_of,
    supply_of,
)
from tests.phase8.p8_4_world import TURN_TEXT, acceptance_supply, begin_turn_ok
from tests.phase8.p8_4_world import coordinator as build_coordinator
from tests.phase8.p8_4_world import wiring as build_wiring


def _select_run(cycle, *proposals: object, **overrides: object):
    """One real shadow run over a cycle (the P8-0 world's own chain)."""

    built = proposals or (proposal("c-p9-0", schedule_row=kernel_row()),)
    bag: dict[str, object] = {"decision_cycle_id": cycle.decision_cycle_id}
    bag.update(overrides)
    return run_shadow(
        request_of(**bag),
        supply=supply_of(*built),
        current_learning_watermark=WATERMARK,
    )


def _row(db: sqlite3.Connection) -> str:
    row = db.execute("SELECT factor_trace FROM planner_evaluation").fetchone()
    assert row is not None
    return str(row[0])


# -- ① the document's shape --------------------------------------------------


def test_the_document_carries_the_four_keys_and_the_version_word() -> None:
    assert [
        field.name for field in fields(FactorTraceDocument)
    ] == ["version", "provenance", "reasons", "candidates"]
    document = factor_trace_of(
        reasons=("r",), candidates=(), traced=False
    )
    assert document.version == FACTOR_TRACE_VERSION == "ft1"
    assert document.provenance in (
        FACTOR_TRACE_PROVENANCE_KERNEL,
        FACTOR_TRACE_PROVENANCE_NONE,
    )


def test_every_kernel_candidate_field_has_a_document_field() -> None:
    """The completeness claim, made checkable: the document mirrors the
    kernel's ``CandidateTrace`` field for field, in the same order, with the
    same names. A field added to the kernel fails here until the document
    carries it — which is the shape the P9-0 finding asked for."""

    assert [
        field.name for field in fields(CandidateTraceDocument)
    ] == [field.name for field in fields(kernel_module.CandidateTrace)]


def test_the_provenance_words_are_two_and_distinct() -> None:
    assert FACTOR_TRACE_PROVENANCE_KERNEL == "KERNEL_TRACE"
    assert FACTOR_TRACE_PROVENANCE_NONE == "NOT_RECORDED"
    assert FACTOR_TRACE_PROVENANCE_KERNEL != FACTOR_TRACE_PROVENANCE_NONE


# -- ② determinism -----------------------------------------------------------


def _two_candidate_run(cycle):
    return _select_run(
        cycle, proposal("c-b", schedule_row=kernel_row()), proposal("c-a")
    )


def test_the_same_trace_is_encoded_to_the_same_bytes(cycle) -> None:
    first = factor_trace_document(
        factor_trace_of(
            reasons=("a", "b"),
            candidates=_two_candidate_run(cycle).trace.candidates,
            traced=True,
        )
    )
    second = factor_trace_document(
        factor_trace_of(
            reasons=("a", "b"),
            candidates=_two_candidate_run(cycle).trace.candidates,
            traced=True,
        )
    )
    assert first == second
    assert "\n" not in first  # one line: the repository's document spelling


def test_the_encoding_is_the_repositorys_compact_sorted_document(cycle) -> None:
    """The bytes are ``json.dumps(..., sort_keys=True, separators=(",", ":"))``
    of the payload — the ``_array_document`` spelling, reused rather than
    re-invented, asserted by decoding and re-encoding."""

    text = factor_trace_document(
        factor_trace_of(
            reasons=("only reason",),
            candidates=_two_candidate_run(cycle).trace.candidates,
            traced=True,
        )
    )
    assert (
        json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
        == text
    )


def test_the_candidates_are_canonicalized_by_candidate_id(cycle) -> None:
    """The document is a function of the trace's *content*: two traces whose
    candidate tuples are built in different orders encode to the same bytes
    (the kernel's own canonical order is ``canonical_key`` order, and every
    candidate carries its key, so nothing is lost)."""

    run = _two_candidate_run(cycle)
    forward = factor_trace_of(
        reasons=(), candidates=run.trace.candidates, traced=True
    )
    reversed_ = factor_trace_of(
        reasons=(),
        candidates=tuple(reversed(run.trace.candidates)),
        traced=True,
    )
    assert factor_trace_document(forward) == factor_trace_document(reversed_)
    assert [c.candidate_id for c in forward.candidates] == ["c-a", "c-b"]


def test_the_readings_are_canonicalized_by_factor_name(cycle) -> None:
    run = _two_candidate_run(cycle)
    (candidate,) = run.trace.candidates[:1]
    permuted = replace(
        candidate,
        benefit=tuple(reversed(candidate.benefit)),
        cost=tuple(reversed(candidate.cost)),
    )
    plain = factor_trace_of(
        reasons=(), candidates=(candidate,), traced=True
    )
    shuffled = factor_trace_of(reasons=(), candidates=(permuted,), traced=True)
    assert factor_trace_document(plain) == factor_trace_document(shuffled)
    factors = [reading.factor for reading in plain.candidates[0].benefit]
    assert factors == sorted(factors)


def test_the_prose_keeps_the_runs_own_order() -> None:
    """``reasons`` is a datum, not an artifact: the run's order is kept, so
    two traces that differ only in the prose's order encode differently."""

    first = factor_trace_of(reasons=("one", "two"), candidates=(), traced=False)
    second = factor_trace_of(reasons=("two", "one"), candidates=(), traced=False)
    assert factor_trace_document(first) != factor_trace_document(second)
    assert first.reasons == ("one", "two")


# -- ③ the round trip and the legacy arm -------------------------------------


def test_the_round_trip_is_the_document_and_the_bytes(cycle) -> None:
    document = factor_trace_of(
        reasons=("r1",),
        candidates=_two_candidate_run(cycle).trace.candidates,
        traced=True,
    )
    text = factor_trace_document(document)
    assert decode_factor_trace(text) == document
    assert factor_trace_document(decode_factor_trace(text)) == text


def test_the_legacy_array_is_answered_as_the_lines_it_always_was() -> None:
    legacy = json.dumps(
        ["p8-0: a prose line", "p8-0: another"],
        sort_keys=True,
        separators=(",", ":"),
    )
    decoded = decode_factor_trace(legacy)
    assert decoded == ("p8-0: a prose line", "p8-0: another")
    assert not isinstance(decoded, FactorTraceDocument)


def test_a_foreign_version_is_refused_rather_than_guessed() -> None:
    text = factor_trace_document(
        factor_trace_of(reasons=(), candidates=(), traced=False)
    )
    foreign = text.replace(
        f'"version":"{FACTOR_TRACE_VERSION}"', '"version":"ft9"'
    )
    with pytest.raises(ValueError) as refused:
        decode_factor_trace(foreign)
    assert "ft9" in str(refused.value)


def test_a_value_that_is_neither_shape_is_refused() -> None:
    with pytest.raises(ValueError):
        decode_factor_trace('"just a string"')
    with pytest.raises(ValueError):
        decode_factor_trace("{\"version\":\"ft1\"}")  # no reasons/candidates


def test_a_non_string_list_element_is_refused_rather_than_washed(cycle) -> None:
    """The list keys are strict like the scalars: an element that is not a
    string is refused, not spelled with ``str()``. The washed spelling this
    pins against answered the first row below with ``("1",)`` — a prose line
    the row never carried (judgement 3)."""

    given = (
        '{"version":"ft1","provenance":"KERNEL_TRACE","reasons":[1],'
        '"candidates":[]}'
    )
    with pytest.raises(ValueError) as refused:
        decode_factor_trace(given)
    assert str(refused.value) == "factor_trace.reasons is not a string: 1"

    # The same rule on the two list keys a candidate carries.
    run = _select_run(cycle)
    text = factor_trace_document(
        factor_trace_of(reasons=(), candidates=run.trace.candidates, traced=True)
    )
    for key in ("merged_from", "dominated_by"):
        payload = json.loads(text)
        payload["candidates"][0][key] = [1]
        with pytest.raises(ValueError) as refused:
            decode_factor_trace(json.dumps(payload))
        assert str(refused.value) == f"factor_trace.{key} is not a string: 1"


def test_a_trace_without_candidates_still_carries_the_prose() -> None:
    document = factor_trace_of(
        reasons=("the leg failed",), candidates=(), traced=False
    )
    text = factor_trace_document(document)
    assert '"provenance":"NOT_RECORDED"' in text
    assert '"reasons":["the leg failed"]' in text
    assert '"candidates":[]' in text
    assert decode_factor_trace(text) == document


# -- ④ the durable column ----------------------------------------------------


def test_a_real_run_lands_its_whole_trace_in_the_column(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The finding's fix, asserted on the row: every scored candidate, its
    readings with their sources, its scores, its utility, its activation
    verdict, the tie facts — all of it, decoded back and compared against the
    kernel's own trace."""

    run = _two_candidate_run(cycle)
    assert run.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(written, Ok), written
    document = decode_factor_trace(_row(db))
    assert isinstance(document, FactorTraceDocument)
    assert document.provenance == FACTOR_TRACE_PROVENANCE_KERNEL
    assert document.reasons == run.why
    assert document == factor_trace_of(
        reasons=run.why, candidates=run.trace.candidates, traced=True
    )
    by_id = {c.candidate_id: c for c in document.candidates}
    assert set(by_id) == {"c-a", "c-b"}
    selected = by_id["c-a"]
    assert selected.selected is True
    assert selected.utility == pytest.approx(selected.benefit_score)
    assert [r.factor for r in selected.benefit] == sorted(
        r.factor for r in selected.benefit
    )
    for reading in selected.benefit:
        assert reading.source in ("AUTHORITY", "DECLARED")
        assert (reading.authority is not None) == (
            reading.source == "AUTHORITY"
        )
    assert selected.activation_path is not None
    assert selected.activated is not None
    assert selected.in_tie_set is True  # the near-tie the run recorded
    assert by_id["c-b"].selected is False


def test_the_read_face_parses_the_column_back_to_the_document(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    run = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(written, Ok), written
    read = planner_store.get_planner_evaluation(
        written.value.evaluation.planner_evaluation_id
    )
    assert isinstance(read, Ok) and read.value is not None
    assert isinstance(read.value.factor_trace, FactorTraceDocument)
    assert read.value.factor_trace == written.value.evaluation.factor_trace
    assert read.value.ranked_candidate_ids == ("c-p9-0",)
    assert read.value.frontier_candidate_ids == ("c-p9-0",)


def test_a_gap_candidate_records_its_gap_and_no_scores(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """A candidate whose ``schedule_urgency`` has no authority is a *gap*, and
    the degraded run carries it: the document says which factor, which
    authority and why — the trace the finding asked for, on the path where it
    matters most (BF-02 §5 forbids answering a gap with ``0``)."""

    run = _select_run(cycle, rowless_proposal("c-gap"))
    assert run.execution_status is not PlannerExecutionStatusValue.SUCCEEDED
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(written, Ok), written
    document = decode_factor_trace(_row(db))
    assert isinstance(document, FactorTraceDocument)
    (candidate,) = document.candidates
    assert candidate.candidate_id == "c-gap"
    assert [gap.factor for gap in candidate.gaps] == ["schedule_urgency"]
    assert candidate.gaps[0].authority == "SCHEDULE"
    assert candidate.benefit_score is None and candidate.utility is None
    assert candidate.selected is False


def test_an_excluded_candidate_records_its_reason_and_no_score(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    run = _select_run(
        cycle, proposal("c-dead", expired=True), proposal("c-live")
    )
    assert run.execution_status is PlannerExecutionStatusValue.SUCCEEDED
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(written, Ok), written
    document = decode_factor_trace(_row(db))
    assert isinstance(document, FactorTraceDocument)
    by_id = {c.candidate_id: c for c in document.candidates}
    assert by_id["c-dead"].excluded == "EXPIRED"
    assert by_id["c-dead"].utility is None
    assert by_id["c-live"].selected is True


def test_a_write_without_a_trace_says_so_instead_of_claiming_an_empty_run(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    run = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome
    )
    assert isinstance(written, Ok), written
    document = decode_factor_trace(_row(db))
    assert isinstance(document, FactorTraceDocument)
    assert document.provenance == FACTOR_TRACE_PROVENANCE_NONE
    assert document.candidates == ()
    assert document.reasons == run.why  # the prose is still durable


def test_the_degraded_leg_shape_keeps_its_reason_durable(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    degraded = failed_outcome(
        cycle.decision_cycle_id, PlannerExecutionStatusValue.UNAVAILABLE
    )
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=degraded
    )
    assert isinstance(written, Ok), written
    document = decode_factor_trace(_row(db))
    assert isinstance(document, FactorTraceDocument)
    assert document.candidates == ()
    assert document.reasons == degraded.evaluation.reason_trace


# -- ⑤ replay and the legacy row ---------------------------------------------


def test_a_replay_with_the_same_trace_agrees_and_writes_nothing(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    run = _two_candidate_run(cycle)
    first = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(first, Ok), first
    before = db.total_changes
    again = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert db.total_changes == before


def test_a_replay_whose_trace_differs_is_refused(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """The arm the prose used to carry, kept and widened: a re-entry whose
    *candidate trace* differs is a ``CONFLICT``, because the document is what
    the evaluation's agreement is compared through."""

    run = _two_candidate_run(cycle)
    first = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(first, Ok), first
    (candidate,) = run.trace.candidates[:1]
    altered_trace = replace(
        run.trace,
        candidates=(replace(candidate, utility=0.0, selected=False),),
    )
    refused = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=altered_trace
    )
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "different evaluation" in refused.error.message


def test_a_replay_of_a_legacy_row_is_refused_rather_than_guessed(
    db: sqlite3.Connection, cycle, planner_store
) -> None:
    """A row written before this cut cannot be vouched for by a post-cut
    submission: the document and the lines are not the same shape, and the
    replay path refuses instead of comparing them best-effort (the legacy
    arm's revisit in elc/planner/records.py judgement 9)."""

    run = _select_run(cycle)
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert isinstance(written, Ok), written
    legacy = json.dumps(
        list(run.why), sort_keys=True, separators=(",", ":")
    )
    db.execute(
        "UPDATE planner_evaluation SET factor_trace = ?",
        (legacy,),
    )
    db.commit()  # the raw write is the test's own: close it before the unit runs
    refused = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=run.outcome, trace=run.trace
    )
    assert refused.error is not None
    assert refused.error.code is DomainErrorCode.CONFLICT
    # … and the read face still answers the legacy row as its lines.
    read = planner_store.get_planner_evaluation(
        written.value.evaluation.planner_evaluation_id
    )
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.factor_trace == run.why


# -- ⑥ the shipped automatic path --------------------------------------------


def test_the_shipped_turn_wiring_hands_its_trace_in(
    db: sqlite3.Connection, p8world
) -> None:
    """The production row is a real trace, not ``NOT_RECORDED``: the P8-4
    coordinator's automatic leg passes ``plan.run.trace`` to the CP2 unit, so
    the durable column carries the candidates the run really looked at."""

    automatic = build_wiring(p8world, supply=acceptance_supply())
    completion = begin_turn_ok(
        build_coordinator(p8world, automatic=automatic), "cm-p9-trace"
    )
    assert completion.outcome == "REPLIED_FULL"
    document = decode_factor_trace(_row(db))
    assert isinstance(document, FactorTraceDocument)
    assert document.provenance == FACTOR_TRACE_PROVENANCE_KERNEL
    assert document.candidates, document
    assert any(candidate.selected for candidate in document.candidates)
    assert document.reasons
    assert TURN_TEXT  # the turn this row belongs to really ran
