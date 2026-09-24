"""P8-5 ③ — the six observations, over real databases and real writes.

Every reading is exercised twice: on a database where the fact does not exist
(the honest zero) and after the shipped write face produced it (the reading
moves). Nothing is hand-inserted: deliveries go through the coordinator, skips
through ``elc.runtime.exposure``, Gate decisions through the teaching store's
own record faces, aborts through the moment lifecycle, and the Evidence count
through the Learning authority face.

The proxy declaration is pinned as behaviour, not as prose: exactly one
indicator is a proxy, and the two indicators that could double-count one act
(an automatic moment the user left vs. a skip) are shown to count it in
different halves of their breakdowns.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from elc.platform.types import (
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    GateDecisionId,
    MomentId,
    Ok,
    PersonaId,
    PlannerExecutionStatusValue,
    PolicyVersion,
)
from elc.runtime import exposure
from elc.runtime.automatic_turn import record_leg_failure
from elc.teaching.rollout import (
    NEUTRAL_OVEREXPOSURE_BANDS,
    OBSERVATION_INDICATORS,
    OBSERVATION_SPECS,
    ObservationReading,
    collect_observations,
    observations_of,
)
from elc.teaching.store import MomentTransition
from elc.teaching.types import (
    AbortReason,
    AuthorizationBasis,
    EvidenceModality,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from tests.phase2.conftest import make_claim, make_group
from tests.phase7.conftest import CONV, TARGET_ID
from tests.phase8.p8_4_world import (
    World,
    acceptance_supply,
    begin_turn_ok,
    build_content,
    counts,
    wiring,
    world,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator
from tests.phase8.p8_5_world import ObservationProbe, readings

AT = "2026-09-24T09:00:00+00:00"
AFTER = "2026-09-24T10:00:00+00:00"


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db: sqlite3.Connection, fence, content: Path) -> World:
    return world(db, fence, content)


def empty_readings(as_of: str = AFTER) -> tuple[ObservationReading, ...]:
    """The six readings over empty inputs (the honest zero case)."""

    from elc.planner.ledger import PlanningLedger

    return observations_of(
        moments=(),
        gate_decisions=(),
        planner_decisions=(),
        evidence_claim_count=0,
        ledger=PlanningLedger(),
        as_of=as_of,
    )


def reading_of(
    collected: tuple[ObservationReading, ...], indicator: str
) -> ObservationReading:
    for entry in collected:
        if entry.indicator == indicator:
            return entry
    raise AssertionError(f"no indicator {indicator!r}")


def _ledger_clock(db: sqlite3.Connection, fallback: str = AFTER) -> str:
    """The latest durable event instant, as an ``as_of`` that contains it.

    The delivery path stamps its events with the *store's* clock, so a fixed
    test instant can sit before them; reading the log's own latest instant is
    how a test asks "what is inside the window" without guessing the wall
    clock.
    """

    row = db.execute(
        "SELECT MAX(as_of) FROM planning_ledger_event"
    ).fetchone()
    if row is None or row[0] is None:
        return fallback
    return str(row[0])


def _open_automatic_moment(p8world: World, client_message_id: str) -> str:
    """One real ALLOW turn; the moment id it left behind."""

    begin_turn_ok(
        build_coordinator(
            p8world,
            automatic=wiring(p8world, supply=acceptance_supply()),
        ),
        client_message_id,
    )
    moment_id = p8world.db.execute(
        "SELECT moment_id FROM teaching_moment"
    ).fetchone()[0]
    return str(moment_id)


def _abort(p8world: World, moment_id: str, reason: str) -> None:
    """ABORTING then TEACHING_TERMINAL through the store's own two steps (the
    CAS expectation is the moment's *current* ``state_version``, read from the
    store — the delivery advanced it)."""

    current = p8world.teaching.get_moment(MomentId(moment_id))
    assert isinstance(current, Ok), current
    advanced = p8world.teaching.transition_moment(
        MomentId(moment_id),
        MomentTransition(lifecycle_state=MomentState.ABORTING),
        expected_state_version=current.value.state_version,
    )
    assert isinstance(advanced, Ok), advanced
    closed = p8world.teaching.terminalize_moment(
        MomentId(moment_id), abort_reason=reason
    )
    assert isinstance(closed, Ok), closed
    assert closed.value.abort_reason == reason


def _moment_record(*, source: MomentSource) -> TeachingMomentRecord:
    """One §15 record of the right shape (used only where no real moment
    exists — the source-filter pin below)."""

    return TeachingMomentRecord(
        moment_id=MomentId("m-p8-5"),
        conversation_id=ConversationId("c-p8-5"),
        persona_id=PersonaId("p-p8-5"),
        source=source,
        decision_cycle_id=DecisionCycleId("dc-p8-5"),
        candidate_id="cand-p8-5",
        gate_decision_id=GateDecisionId("gd-p8-5"),
        focus_target=TeachingTargetRef(
            target_type="RESOURCE", target_id=str(TARGET_ID)
        ),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="DEVELOP",
        evidence_modality=EvidenceModality.TEXT_PRODUCTION,
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MomentState.AWAITING_USER,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.NONE,
        completion_outcome=None,
        abort_reason=AbortReason.USER_TOPIC_SHIFT.value,
        state_version=1,
    )


def _gate_records(
    context: GateDecisionContext, decision: GateDecisionValue
) -> tuple[GateExecutionStatusRecord, GateDecisionRecord]:
    return (
        GateExecutionStatusRecord(
            gate_execution_status_id=f"ges-{context.value.lower()}",
            decision_cycle_id=DecisionCycleId("dc-p8-5-obs"),
            moment_id=None,
            gate_context=context,
            authorization_basis=AuthorizationBasis.ACTIVE_MOMENT,
            authorization_status="VALID",
            status=GateExecutionStatusValue.SUCCEEDED,
            missing_or_unknown=(),
        ),
        GateDecisionRecord(
            gate_decision_id=GateDecisionId(f"gd-{context.value.lower()}"),
            decision_cycle_id=DecisionCycleId("dc-p8-5-obs"),
            candidate_id="cand-p8-5",
            context=context,
            decision=decision,
            # An ALLOW carries no DENY reason codes (the store's own rule).
            reason_codes=(
                ("HARD_PROTECTED_FLOW",)
                if decision is GateDecisionValue.DENY
                else ()
            ),
            policy_version=PolicyVersion("pv-p8-5"),
        ),
    )


# -- ① the empty database ----------------------------------------------------


def test_an_empty_database_answers_all_six_zeros(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    collected = readings(db, fence, as_of=AFTER)
    assert [entry.value for entry in collected] == [0, 0, 0, 0, 0, 0]
    assert reading_of(collected, "skip/reject").breakdown == (
        ("ledger.user_skip", 0),
        ("moment.abort_reason", 0),
    )
    assert reading_of(collected, "Evidence gain").breakdown == (
        ("evidence_claim", 0),
    )
    assert reading_of(collected, "continuation").breakdown == ()
    assert reading_of(collected, "NO_TARGET appropriateness").breakdown == ()
    assert reading_of(collected, "overexposure").breakdown == ()


def test_the_six_indicators_are_the_documents_six() -> None:
    assert OBSERVATION_INDICATORS == (
        "unwanted interruption",
        "skip/reject",
        "continuation",
        "NO_TARGET appropriateness",
        "overexposure",
        "Evidence gain",
    )
    assert [spec.indicator for spec in OBSERVATION_SPECS] == list(
        OBSERVATION_INDICATORS
    )
    assert [entry.indicator for entry in empty_readings()] == list(
        OBSERVATION_INDICATORS
    )


def test_every_reading_carries_its_declaration() -> None:
    for entry in empty_readings():
        for text in (
            entry.spec.definition,
            entry.spec.carrier,
            entry.spec.honesty,
            entry.spec.revisit,
        ):
            assert text and len(text) > 20
        if entry.is_proxy:
            assert entry.spec.proxy_of and entry.spec.proxy_because


def test_exactly_one_reading_is_a_declared_proxy() -> None:
    """The direct signal that does not exist must not be faked anywhere else:
    ``unwanted interruption`` is the one proxy, and every other indicator
    declares a real carrier."""

    collected = empty_readings()
    proxies = [entry for entry in collected if entry.is_proxy]
    assert [entry.indicator for entry in proxies] == ["unwanted interruption"]
    assert proxies[0].spec.proxy_of == "a user-reported unwanted interruption"
    assert "lower bound" in (proxies[0].spec.proxy_because or "")
    for entry in collected:
        if entry.indicator != "unwanted interruption":
            assert entry.spec.proxy_of is None
            assert entry.spec.proxy_because is None


def test_the_honesty_declarations_name_their_limits() -> None:
    """The readings whose value is narrower than their name say so in the
    datum (a reader never has to fetch the module docstring)."""

    by_indicator = {spec.indicator: spec for spec in OBSERVATION_SPECS}
    assert "no carrier" in by_indicator["unwanted interruption"].honesty
    assert "denominator" in by_indicator["continuation"].honesty
    assert "no durable signal records" in (
        by_indicator["NO_TARGET appropriateness"].honesty
    )
    assert "registered limit" in by_indicator["Evidence gain"].honesty
    assert "planner_decision" in (
        by_indicator["NO_TARGET appropriateness"].honesty
    )


# -- ② the readings over real writes ----------------------------------------


def test_a_real_automatic_open_moves_the_decision_and_exposure_readings(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    _open_automatic_moment(p8world, "cm-open")
    collected = readings(db, fence, as_of=_ledger_clock(db))
    assert reading_of(collected, "NO_TARGET appropriateness").breakdown == (
        ("SELECT", 1),
    )
    assert reading_of(collected, "continuation").breakdown == (("OPEN", 1),)
    # The OPEN decision is not a continuation: the value counts AUTO_CONTINUE
    # only.
    assert reading_of(collected, "continuation").value == 0
    assert reading_of(collected, "overexposure").breakdown == (("LOW", 1),)
    assert reading_of(collected, "overexposure").value == 1
    assert reading_of(collected, "skip/reject").value == 0
    assert reading_of(collected, "Evidence gain").value == 0


def test_the_ledger_half_of_skip_reject_reads_the_real_log(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    moment_id = _open_automatic_moment(p8world, "cm-open")
    recorded = exposure.record_skip(
        writer=p8world.ledger,
        event_id=exposure.skip_event_id(MomentId(moment_id)),
        target_key=str(TARGET_ID),
        moment_id=MomentId(moment_id),
        at=AT,
    )
    assert isinstance(recorded, Ok), recorded
    reading = reading_of(readings(db, fence, as_of=AFTER), "skip/reject")
    assert reading.value == 1
    assert dict(reading.breakdown) == {
        "ledger.user_skip": 1,
        "moment.abort_reason": 0,
    }


def test_a_moment_abort_of_an_automatic_moment_is_the_interruption_proxy(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    moment_id = _open_automatic_moment(p8world, "cm-open")
    _abort(p8world, moment_id, AbortReason.USER_TOPIC_SHIFT.value)
    collected = readings(db, fence, as_of=AFTER)
    interruption = reading_of(collected, "unwanted interruption")
    assert interruption.value == 1
    assert interruption.breakdown == (("USER_TOPIC_SHIFT", 1),)
    # The proxy word is not a skip word, so the skip/reject halves stay zero.
    assert reading_of(collected, "skip/reject").breakdown == (
        ("ledger.user_skip", 0),
        ("moment.abort_reason", 0),
    )


def test_a_user_skip_abort_moves_skip_reject_and_not_the_proxy(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    moment_id = _open_automatic_moment(p8world, "cm-open")
    _abort(p8world, moment_id, AbortReason.USER_SKIP.value)
    collected = readings(db, fence, as_of=AFTER)
    assert reading_of(collected, "unwanted interruption").value == 0
    assert dict(reading_of(collected, "skip/reject").breakdown) == {
        "ledger.user_skip": 0,
        "moment.abort_reason": 1,
    }


def test_one_real_skip_is_two_records_and_never_their_sum(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """The one act that lands in **both** halves must still count once.

    A real skip leaves two durable records of one action — the §20 log's
    ``user_skip`` and the same moment's ``abort_reason`` (the coordinator's
    ``USER_SKIP`` path writes both for one moment) — and here both halves are
    non-zero at the same time. The reading's value is the ledger's count, so
    summing the halves would double-count exactly this action; the honesty
    sentence "the two are never summed into one number" is this assertion."""

    moment_id = _open_automatic_moment(p8world, "cm-open")
    _abort(p8world, moment_id, AbortReason.USER_SKIP.value)
    recorded = exposure.record_skip(
        writer=p8world.ledger,
        event_id=exposure.skip_event_id(MomentId(moment_id)),
        target_key=str(TARGET_ID),
        moment_id=MomentId(moment_id),
        at=AT,
    )
    assert isinstance(recorded, Ok), recorded

    reading = reading_of(readings(db, fence, as_of=AFTER), "skip/reject")
    assert dict(reading.breakdown) == {
        "ledger.user_skip": 1,
        "moment.abort_reason": 1,
    }
    assert reading.value == 1


def test_a_non_automatic_moment_is_not_the_interruption_proxy() -> None:
    """The source filter, as a pure-function pin: the same abort reason on a
    user-initiated moment is not the automatic path's friction."""

    from elc.planner.ledger import PlanningLedger

    def collect(moment: TeachingMomentRecord) -> ObservationReading:
        return reading_of(
            observations_of(
                moments=(moment,),
                gate_decisions=(),
                planner_decisions=(),
                evidence_claim_count=0,
                ledger=PlanningLedger(),
                as_of=AFTER,
            ),
            "unwanted interruption",
        )

    assert collect(_moment_record(source=MomentSource.USER_INITIATED)).value == 0
    assert collect(_moment_record(source=MomentSource.AUTOMATIC)).value == 1


def test_a_continuation_decision_is_counted_by_its_own_context(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    _open_automatic_moment(p8world, "cm-open")
    cycle = DecisionCycleId(
        p8world.db.execute(
            "SELECT decision_cycle_id FROM teaching_moment"
        ).fetchone()[0]
    )
    status, decision = _gate_records(
        GateDecisionContext.AUTO_CONTINUE, GateDecisionValue.DENY
    )
    recorded = p8world.teaching.record_gate_denial(
        replace(status, decision_cycle_id=cycle),
        replace(decision, decision_cycle_id=cycle),
    )
    assert isinstance(recorded, Ok), recorded
    reading = reading_of(readings(db, fence, as_of=AFTER), "continuation")
    assert reading.value == 1
    assert dict(reading.breakdown) == {"AUTO_CONTINUE": 1, "OPEN": 1}


def test_a_user_requested_continuation_has_its_own_word(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    _open_automatic_moment(p8world, "cm-open")
    cycle = DecisionCycleId(
        p8world.db.execute(
            "SELECT decision_cycle_id FROM teaching_moment"
        ).fetchone()[0]
    )
    status, decision = _gate_records(
        GateDecisionContext.USER_REQUESTED_CONTINUE, GateDecisionValue.ALLOW
    )
    recorded = p8world.teaching.record_gate_allow(
        replace(status, decision_cycle_id=cycle),
        replace(decision, decision_cycle_id=cycle),
    )
    assert isinstance(recorded, Ok), recorded
    reading = reading_of(readings(db, fence, as_of=AFTER), "continuation")
    assert reading.value == 0  # not an automatic continuation
    assert dict(reading.breakdown) == {
        "USER_REQUESTED_CONTINUE": 1,
        "OPEN": 1,
    }


def test_a_degraded_run_is_not_a_no_target_decision(
    db: sqlite3.Connection,
    fence,
    p8world: World,
    cycle,
) -> None:
    """§14.1's separation, read off the observations: a DEGRADED status row is
    a *failure* and the NO_TARGET reading counts decisions — the two tables
    are asked separately, and this reading never launders one into the
    other."""

    recorded = record_leg_failure(
        wiring=wiring(p8world),
        turn_id=cycle.turn_id,
        decision_cycle_id=cycle.decision_cycle_id,
        reason="p8-5 probe: a leg that could not run",
    )
    assert isinstance(recorded, Ok), recorded
    assert db.execute(
        "SELECT status FROM planner_execution_status"
    ).fetchone() == (PlannerExecutionStatusValue.DEGRADED.value,)
    assert counts(db, "planner_decision") == {"planner_decision": 0}
    collected = readings(db, fence, as_of=AFTER)
    assert reading_of(collected, "NO_TARGET appropriateness").breakdown == ()
    assert reading_of(collected, "NO_TARGET appropriateness").value == 0


def test_a_real_no_target_run_is_counted(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    begin_turn_ok(
        build_coordinator(p8world, automatic=wiring(p8world, supply=None)),
        "cm-real",
    )
    reading = reading_of(
        readings(db, fence, as_of=AFTER), "NO_TARGET appropriateness"
    )
    assert reading.value == 1
    assert reading.breakdown == (("NO_TARGET", 1),)


def test_overexposure_counts_by_the_ledgers_own_bands(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    moment_id = MomentId(_open_automatic_moment(p8world, "cm-open"))
    for index in (2, 3):
        recorded = exposure.record_exposure(
            writer=p8world.ledger,
            event_id=f"ev-p8-5-{index}",
            event=exposure.LedgerEvent.TEACHING_PRESENTED,
            target_key=str(TARGET_ID),
            moment_id=moment_id,
            at=AT,
        )
        assert isinstance(recorded, Ok), recorded
    reading = reading_of(readings(db, fence, as_of=AFTER), "overexposure")
    assert reading.value == 1
    assert dict(reading.breakdown) == {"MEDIUM": 1}
    assert "MEDIUM" not in NEUTRAL_OVEREXPOSURE_BANDS


def test_a_row_without_presentations_is_neutral(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """A row that exists but was never *presented* is the neutral band: the
    ledger records a rejection, not an exposure, and the reading says so
    instead of counting it."""

    recorded = exposure.record_skip(
        writer=p8world.ledger,
        event_id="ev-skip-untouched",
        target_key="res-untouched",
        moment_id=MomentId("m-untouched"),
        at=AT,
    )
    assert isinstance(recorded, Ok), recorded
    assert counts(db, "planning_ledger") == {"planning_ledger": 1}
    reading = reading_of(readings(db, fence, as_of=AFTER), "overexposure")
    assert reading.value == 0
    assert reading.breakdown == (("NONE", 1),)


def test_evidence_gain_counts_real_claims(
    db: sqlite3.Connection, fence, p8world: World, cycle
) -> None:
    """The count moves when the Learning authority face really commits a §6
    claim (no fixture row is inserted)."""

    committed = p8world.learning.commit_evidence_group(
        make_group("eg-p8-5", (make_claim(),)),
        source_turn_id=cycle.turn_id,
        conversation_id=str(CONV),
    )
    assert isinstance(committed, Ok), committed
    assert counts(db, "evidence_claim") == {"evidence_claim": 1}
    assert (
        reading_of(readings(db, fence, as_of=AFTER), "Evidence gain").value == 1
    )


def test_an_empty_database_keeps_the_evidence_count_at_zero(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    assert counts(db, "evidence_claim") == {"evidence_claim": 0}
    assert reading_of(
        readings(db, fence, as_of=AFTER), "Evidence gain"
    ).breakdown == (("evidence_claim", 0),)


# -- ③ the collector ---------------------------------------------------------


class _CountingPort:
    """A port that records how many times each face was asked."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_moments(self):
        self.calls.append("list_moments")
        return Ok(())

    def list_gate_decisions(self):
        self.calls.append("list_gate_decisions")
        return Ok(())

    def list_planner_decisions(self):
        self.calls.append("list_planner_decisions")
        return Ok(())

    def count_evidence_claims(self):
        self.calls.append("count_evidence_claims")
        return Ok(0)

    def read_ledger(self):
        self.calls.append("read_ledger")
        from elc.planner.ledger import PlanningLedger

        return Ok(PlanningLedger())


def test_the_collector_asks_each_face_once() -> None:
    port = _CountingPort()
    collected = collect_observations(port, as_of=AFTER)
    assert isinstance(collected, Ok), collected
    assert port.calls == [
        "list_moments",
        "list_gate_decisions",
        "list_planner_decisions",
        "count_evidence_claims",
        "read_ledger",
    ]


@pytest.mark.parametrize(
    "face",
    [
        "list_moments",
        "list_gate_decisions",
        "list_planner_decisions",
        "count_evidence_claims",
        "read_ledger",
    ],
)
def test_a_failed_read_is_returned_untouched(face: str) -> None:
    error = DomainError(
        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE, message=f"{face} broke"
    )
    port = _CountingPort()
    setattr(port, face, lambda: Err(error))
    answer = collect_observations(port, as_of=AFTER)
    assert isinstance(answer, Err)
    assert answer.error is error


def test_the_probe_reads_a_real_database_through_the_real_stores(
    db: sqlite3.Connection, fence, p8world: World
) -> None:
    """The adapter's shapes are the stores' own: a probe over the shipped
    tables answers the same zeros the empty-input path does."""

    probe = ObservationProbe(db, fence)
    assert probe.list_moments() == Ok(())
    assert probe.list_gate_decisions() == Ok(())
    assert probe.list_planner_decisions() == Ok(())
    assert probe.count_evidence_claims() == Ok(0)
    ledger = probe.read_ledger()
    assert isinstance(ledger, Ok), ledger
    assert ledger.value.rows == {}
