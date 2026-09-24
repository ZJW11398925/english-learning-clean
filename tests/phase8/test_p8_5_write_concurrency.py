"""P8-5 ⑤ — two writers on one real app.db: replay, conflict, waiting.

The evidence this cut owes p8-0/p8-4's registered gap ("concurrent double
writers never measured"). Every test here runs on a **file-backed** database
with **two connections joined to the same runtime epoch** — two ``:memory:``
connections would be two different databases, which is the one thing a
concurrency probe must not do.

What each writer gets, and why the durable state cannot lose a row:

- a second writer re-submitting the *same* fact (one decision cycle, one
  ledger event id) gets a **replay**: ``Ok``, no new row, the durable content
  still the first writer's;
- a second writer re-submitting a *differing* fact under the same identity
  gets ``CONFLICT``: the first fact is never rewritten (§1.3 append-first /
  "a status is a fact, not a mutable label");
- a writer that arrives while the first holds the write transaction **waits
  or fails on the lock** — with a short ``busy_timeout`` it raises
  ``sqlite3.OperationalError`` and nothing partial is written; after the
  first commits, its retry replays;
- two *different* facts both land (no lost update), and both connections read
  the same two rows afterwards.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.planner.ledger import LedgerEvent
from elc.planner.ledger_store import SqliteLedgerStore
from elc.planner.types import (
    PlannerDecision,
    PlannerEvaluation,
    PlanningOutcome,
)
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    DecisionCycleId,
    Err,
    GateDecisionId,
    InputId,
    InteractionChannel,
    MomentId,
    Ok,
    PlannerDecisionId,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
    TurnId,
)
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.types import InputEnvelope
from elc.teaching.store import (
    CP2OpenRequest,
    SqliteTeachingStore,
    cp2_action_intent,
)
from elc.teaching.types import (
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
from tests.phase7.conftest import CONV, TARGET_ID, USER
from tests.phase8.p8_5_world import join_epoch, open_file_db

RECEIVED_AT = "2026-09-24T09:00:00+00:00"
TURN_ID = TurnId("turn-p8-5")
CYCLE_ID = DecisionCycleId("dc-p8-5")
RUNTIME_VERSION = "runtime-p8-5"
MOMENT_ID = MomentId("m-p8-5")


@pytest.fixture()
def app_db(tmp_path: Path) -> Path:
    return tmp_path / "app.db"


@pytest.fixture()
def first(app_db: Path):
    conn, fence = open_file_db(app_db)
    yield conn, fence
    conn.close()


@pytest.fixture()
def second(app_db: Path):
    conn, fence = join_epoch(app_db)
    yield conn, fence
    conn.close()


def _seed_turn(conn: sqlite3.Connection, fence: RuntimeEpochFence) -> int:
    """One conversation → CP0 turn → decision cycle, through the real units.

    Returns the turn's ``state_version`` after the cycle opened (the CAS the
    next cycle of that turn has to pass).
    """

    opened = SqliteConversationStore(conn, fence).open_conversation(
        CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    commit = SqliteConversationStore(conn, fence).commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId("in-p8-5"),
                client_message_id=ClientMessageId("cmid-p8-5"),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-p8-5",
                received_at=RECEIVED_AT,
            ),
            raw_content="One turn for the concurrency probe.",
            runtime_version=RUNTIME_VERSION,
            turn_id=TURN_ID,
        )
    )
    assert isinstance(commit, Ok), commit
    recorded = SqliteDecisionCycleStore(conn, fence).record_decision_cycle(
        decision_cycle_id=CYCLE_ID,
        turn_id=commit.value.turn_id,
        bindings=DecisionCycleBindings(
            learning_snapshot_id=None,
            evidence_watermark=None,
            curriculum_version=None,
            goal_version=None,
            schedule_version=None,
            policy_version=None,
            context_view_version=None,
            relationship_view_version=None,
        ),
        expected_turn_state_version=commit.value.state_version,
    )
    assert isinstance(recorded, Ok), recorded
    return commit.value.state_version + 1


def _outcome(
    cycle_id: DecisionCycleId,
    *,
    planner: str = "planner-p8-5",
    decision: PlannerDecisionOutcome = PlannerDecisionOutcome.NO_TARGET,
) -> PlanningOutcome:
    """One SUCCEEDED outcome with its decision (a successful run always has
    one — ``PlanningOutcome`` refuses the gap)."""

    return PlanningOutcome(
        evaluation=PlannerEvaluation(
            planner_evaluation_id=PlannerEvaluationId(
                f"pe-{cycle_id}-{planner}"
            ),
            decision_cycle_id=cycle_id,
            planner_version=PlannerVersion(planner),
            policy_version=PolicyVersion("pv-p8-5"),
            ranked_candidates=(),
            reason_trace=(f"p8-5 concurrency probe ({planner})",),
            frontier_candidate_ids=(),
        ),
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=cycle_id,
            status=PlannerExecutionStatusValue.SUCCEEDED,
            error_code=None,
        ),
        decision=PlannerDecision(
            planner_decision_id=PlannerDecisionId(f"pd-{cycle_id}-{planner}"),
            decision_cycle_id=cycle_id,
            decision=decision,
            planner_evaluation_id=PlannerEvaluationId(
                f"pe-{cycle_id}-{planner}"
            ),
            selected_candidate_id=None,
            no_target_reason="BELOW_ACTIVATION_THRESHOLD",
        ),
    )


def _degraded(cycle_id: DecisionCycleId, *, planner: str) -> PlanningOutcome:
    """The DEGRADED shape of the same cycle: a status, and **no** decision
    (§14's separation) — what a second writer's relabel would look like."""

    return PlanningOutcome(
        evaluation=PlannerEvaluation(
            planner_evaluation_id=PlannerEvaluationId(f"pe-{planner}"),
            decision_cycle_id=cycle_id,
            planner_version=PlannerVersion(planner),
            policy_version=PolicyVersion("pv-p8-5"),
            ranked_candidates=(),
            reason_trace=(f"p8-5 concurrency probe ({planner})",),
            frontier_candidate_ids=(),
        ),
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=cycle_id,
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code="P8_5_PROBE",
        ),
        decision=None,
    )


def _planner_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in (
            "planner_execution_status",
            "planner_evaluation",
            "planner_decision",
        )
    }


def _event(
    conn: sqlite3.Connection,
    fence: RuntimeEpochFence,
    *,
    event_id: str,
    word: LedgerEvent,
    at: str,
):
    """One §20 event through the shipped writer (the same face p8-4's delivery
    path calls, so the row/log agreement rule is the product's, not a test's)."""

    from elc.runtime import exposure

    return exposure.record_event(
        writer=SqliteLedgerStore(conn, fence),
        event_id=event_id,
        event=word,
        target_key=str(TARGET_ID),
        moment_id=MOMENT_ID,
        at=at,
    )


# -- the planner half --------------------------------------------------------


def test_a_second_writer_replays_an_identical_cycle(first, second) -> None:
    conn_a, fence_a = first
    conn_b, fence_b = second
    _seed_turn(conn_a, fence_a)
    outcome = _outcome(CYCLE_ID, decision=PlannerDecisionOutcome.NO_TARGET)
    written = SqlitePlannerRecordStore(conn_a, fence_a).record_planner_cycle(
        turn_id=TURN_ID, outcome=outcome
    )
    assert isinstance(written, Ok), written
    replayed = SqlitePlannerRecordStore(conn_b, fence_b).record_planner_cycle(
        turn_id=TURN_ID, outcome=outcome
    )
    assert isinstance(replayed, Ok), replayed
    assert replayed.value == written.value
    counts = _planner_counts(conn_b)
    assert counts == dict.fromkeys(counts, 1)
    # The second connection sees the first writer's durable content.
    assert conn_b.execute(
        "SELECT status FROM planner_execution_status"
    ).fetchone() == ("SUCCEEDED",)


def test_a_second_writer_cannot_relabel_a_cycle(first, second) -> None:
    conn_a, fence_a = first
    conn_b, fence_b = second
    _seed_turn(conn_a, fence_a)
    written = SqlitePlannerRecordStore(conn_a, fence_a).record_planner_cycle(
        turn_id=TURN_ID, outcome=_outcome(CYCLE_ID)
    )
    assert isinstance(written, Ok), written
    differing = _degraded(CYCLE_ID, planner="planner-other")
    refused = SqlitePlannerRecordStore(conn_b, fence_b).record_planner_cycle(
        turn_id=TURN_ID, outcome=differing
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code.value == "CONFLICT"
    assert conn_b.execute(
        "SELECT status FROM planner_execution_status"
    ).fetchone() == ("SUCCEEDED",)
    counts = _planner_counts(conn_b)
    assert counts == dict.fromkeys(counts, 1)


def test_a_differing_decision_under_one_cycle_is_a_conflict(first, second) -> None:
    conn_a, fence_a = first
    conn_b, fence_b = second
    _seed_turn(conn_a, fence_a)
    written = SqlitePlannerRecordStore(conn_a, fence_a).record_planner_cycle(
        turn_id=TURN_ID,
        outcome=_outcome(CYCLE_ID, decision=PlannerDecisionOutcome.NO_TARGET),
    )
    assert isinstance(written, Ok), written
    other = _outcome(CYCLE_ID, decision=PlannerDecisionOutcome.SELECT)
    refused = SqlitePlannerRecordStore(conn_b, fence_b).record_planner_cycle(
        turn_id=TURN_ID, outcome=other
    )
    assert isinstance(refused, Err), refused
    assert conn_b.execute(
        "SELECT decision FROM planner_decision"
    ).fetchone() == ("NO_TARGET",)


def test_a_held_write_lock_stops_the_second_writer_without_partial_state(
    first, second,
) -> None:
    """The lock probe: while the first writer's transaction is open, the
    second's write cannot slip in. With a short ``busy_timeout`` it raises
    ``OperationalError`` (the SQLite lock), nothing is written, and the retry
    after the commit replays."""

    conn_a, fence_a = first
    conn_b, fence_b = second
    _seed_turn(conn_a, fence_a)
    conn_b.execute("PRAGMA busy_timeout = 50")
    conn_a.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            SqlitePlannerRecordStore(conn_b, fence_b).record_planner_cycle(
                turn_id=TURN_ID, outcome=_outcome(CYCLE_ID)
            )
    finally:
        conn_a.execute("COMMIT")
    counts = _planner_counts(conn_b)
    assert counts == dict.fromkeys(counts, 0)
    retried = SqlitePlannerRecordStore(conn_b, fence_b).record_planner_cycle(
        turn_id=TURN_ID, outcome=_outcome(CYCLE_ID)
    )
    assert isinstance(retried, Ok), retried
    counts = _planner_counts(conn_b)
    assert counts == dict.fromkeys(counts, 1)


# -- the ledger --------------------------------------------------------------


def test_two_writers_with_one_event_id_get_one_row(first, second) -> None:
    conn_a, fence_a = first
    conn_b, fence_b = second
    written = _event(
        conn_a,
        fence_a,
        event_id="ev-race",
        word=LedgerEvent.TEACHING_PRESENTED,
        at=RECEIVED_AT,
    )
    assert isinstance(written, Ok), written
    replayed = _event(
        conn_b,
        fence_b,
        event_id="ev-race",
        word=LedgerEvent.TEACHING_PRESENTED,
        at=RECEIVED_AT,
    )
    assert isinstance(replayed, Ok), replayed
    assert conn_b.execute(
        "SELECT COUNT(*) FROM planning_ledger_event"
    ).fetchone()[0] == 1
    assert conn_b.execute(
        "SELECT event FROM planning_ledger_event"
    ).fetchone() == ("teaching_presented",)


def test_a_differing_word_under_one_event_id_is_a_conflict(first, second) -> None:
    conn_a, fence_a = first
    conn_b, fence_b = second
    written = _event(
        conn_a,
        fence_a,
        event_id="ev-race",
        word=LedgerEvent.TEACHING_PRESENTED,
        at=RECEIVED_AT,
    )
    assert isinstance(written, Ok), written
    refused = _event(
        conn_b,
        fence_b,
        event_id="ev-race",
        word=LedgerEvent.HINT_PRESENTED,
        at=RECEIVED_AT,
    )
    assert isinstance(refused, Err), refused
    assert conn_b.execute(
        "SELECT event FROM planning_ledger_event"
    ).fetchone() == ("teaching_presented",)


def test_a_differing_instant_under_one_event_id_is_a_conflict(
    first, second,
) -> None:
    conn_a, fence_a = first
    conn_b, fence_b = second
    written = _event(
        conn_a,
        fence_a,
        event_id="ev-race",
        word=LedgerEvent.TEACHING_PRESENTED,
        at=RECEIVED_AT,
    )
    assert isinstance(written, Ok), written
    refused = _event(
        conn_b,
        fence_b,
        event_id="ev-race",
        word=LedgerEvent.TEACHING_PRESENTED,
        at="2026-09-24T09:00:01+00:00",
    )
    assert isinstance(refused, Err), refused


def test_two_different_events_both_land_and_both_connections_see_them(
    first, second,
) -> None:
    """No lost update: A appends one event, B appends another, and both
    connections read both rows — the projection is the log's, and the store's
    own read holds the two against each other."""

    conn_a, fence_a = first
    conn_b, fence_b = second
    written_a = _event(
        conn_a,
        fence_a,
        event_id="ev-a",
        word=LedgerEvent.TEACHING_PRESENTED,
        at=RECEIVED_AT,
    )
    assert isinstance(written_a, Ok), written_a
    written_b = _event(
        conn_b,
        fence_b,
        event_id="ev-b",
        word=LedgerEvent.HINT_PRESENTED,
        at="2026-09-24T09:01:00+00:00",
    )
    assert isinstance(written_b, Ok), written_b
    for conn, fence in ((conn_a, fence_a), (conn_b, fence_b)):
        events = SqliteLedgerStore(conn, fence).list_ledger_events(
            str(TARGET_ID)
        )
        assert isinstance(events, Ok), events
        assert [row.event_id for row in events.value] == ["ev-a", "ev-b"]
        ledger = SqliteLedgerStore(conn, fence).read_ledger()
        assert isinstance(ledger, Ok), ledger
        row = ledger.value.rows[str(TARGET_ID)]
        assert row.teaching_exposure_counts == 1
        assert len(row.events) == 2


# -- the teaching half -------------------------------------------------------


def _cp2_request(
    *,
    fence: RuntimeEpochFence,
    moment_id: str,
    cycle_id: DecisionCycleId = CYCLE_ID,
) -> CP2OpenRequest:
    """The CP2 five-fact request of one ALLOW (the test's own declarations —
    the unit's caller is whoever holds the facts)."""

    return CP2OpenRequest(
        gate_execution_status=GateExecutionStatusRecord(
            gate_execution_status_id=f"ges-{moment_id}",
            decision_cycle_id=cycle_id,
            moment_id=None,
            gate_context=GateDecisionContext.OPEN,
            authorization_basis=AuthorizationBasis.DECISION_CYCLE,
            authorization_status="VALID",
            status=GateExecutionStatusValue.SUCCEEDED,
            missing_or_unknown=(),
        ),
        gate_decision=GateDecisionRecord(
            gate_decision_id=GateDecisionId(f"gd-{moment_id}"),
            decision_cycle_id=cycle_id,
            candidate_id="cand-p8-5",
            context=GateDecisionContext.OPEN,
            decision=GateDecisionValue.ALLOW,
            reason_codes=(),
            policy_version=PolicyVersion("pv-p8-5"),
        ),
        moment=TeachingMomentRecord(
            moment_id=MomentId(moment_id),
            conversation_id=CONV,
            persona_id=None,
            source=MomentSource.AUTOMATIC,
            decision_cycle_id=cycle_id,
            candidate_id="cand-p8-5",
            gate_decision_id=GateDecisionId(f"gd-{moment_id}"),
            focus_target=TeachingTargetRef("RESOURCE", str(TARGET_ID)),
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
            lifecycle_state=MomentState.OPENING,
            presentation_phase=PresentationPhase.INITIAL_PROMPT,
            attempt_index=0,
            support_level=TeachingSupportLevel.NONE,
            completion_outcome=None,
            abort_reason=None,
            state_version=1,
        ),
        action=cp2_action_intent(
            turn_id=TURN_ID,
            moment_id=MomentId(moment_id),
            decision_cycle_id=cycle_id,
            action_id=ActionId(f"ga-{moment_id}"),
            assistant_turn_id=f"aturn-{moment_id}",
            generation_contract_id="gc-teaching-open",
            owner_epoch=fence.current,
        ),
        owner_epoch=fence.current,
    )


def test_a_replayed_open_returns_the_canonical_moment(first, second) -> None:
    """The same CP2 five facts from a second connection are a **replay**: the
    store answers with the cycle's existing moment and writes nothing (the
    crash-after-CP2 resume path, RA §23), so no second episode can exist."""

    conn_a, fence_a = first
    conn_b, fence_b = second
    _seed_turn(conn_a, fence_a)
    opened = SqliteTeachingStore(conn_a, fence_a).open_teaching_moment(
        _cp2_request(fence=fence_a, moment_id="m-race")
    )
    assert isinstance(opened, Ok), opened
    replayed = SqliteTeachingStore(conn_b, fence_b).open_teaching_moment(
        _cp2_request(fence=fence_b, moment_id="m-race")
    )
    assert isinstance(replayed, Ok), replayed
    assert replayed.value == opened.value == MomentId("m-race")
    for table in ("teaching_moment", "gate_decision", "active_teaching_lock"):
        assert conn_b.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0] == 1, table


def test_a_second_live_moment_in_one_conversation_is_refused(first, second) -> None:
    """The one-focus guarantee under two connections: a second cycle's open
    races the live lock, the whole unit rolls back (the store's own
    "lost lock race" branch), and the conversation keeps exactly the first
    episode — no second moment, no second lock, and not even the losing
    cycle's Gate facts."""

    conn_a, fence_a = first
    conn_b, fence_b = second
    state_version = _seed_turn(conn_a, fence_a)
    opened = SqliteTeachingStore(conn_a, fence_a).open_teaching_moment(
        _cp2_request(fence=fence_a, moment_id="m-first")
    )
    assert isinstance(opened, Ok), opened
    second_cycle = SqliteDecisionCycleStore(
        conn_b, fence_b
    ).record_decision_cycle(
        decision_cycle_id=DecisionCycleId("dc-p8-5-b"),
        turn_id=TURN_ID,
        bindings=DecisionCycleBindings(
            learning_snapshot_id=None,
            evidence_watermark=None,
            curriculum_version=None,
            goal_version=None,
            schedule_version=None,
            policy_version=None,
            context_view_version=None,
            relationship_view_version=None,
        ),
        expected_turn_state_version=state_version,
    )
    assert isinstance(second_cycle, Ok), second_cycle
    refused = SqliteTeachingStore(conn_b, fence_b).open_teaching_moment(
        _cp2_request(
            fence=fence_b,
            moment_id="m-second",
            cycle_id=DecisionCycleId("dc-p8-5-b"),
        )
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code.value == "CONFLICT"
    assert conn_b.execute(
        "SELECT COUNT(*) FROM teaching_moment"
    ).fetchone()[0] == 1
    assert conn_b.execute(
        "SELECT moment_id FROM active_teaching_lock"
    ).fetchone()[0] == "m-first"
    assert conn_b.execute(
        "SELECT COUNT(*) FROM gate_decision"
    ).fetchone()[0] == 1


def test_the_runtime_outcome_row_moves_with_the_newest_cycle(first, second) -> None:
    """One turn, two cycles (a replan): the ``runtime_decision_outcome`` row is
    the declared ``ON CONFLICT(turn_id) DO UPDATE`` move — and the two cycles'
    status rows both stay, so the move is not a loss."""

    conn_a, fence_a = first
    conn_b, fence_b = second
    state_version = _seed_turn(conn_a, fence_a)
    second_cycle = SqliteDecisionCycleStore(
        conn_a, fence_a
    ).record_decision_cycle(
        decision_cycle_id=DecisionCycleId("dc-p8-5-b"),
        turn_id=TURN_ID,
        bindings=DecisionCycleBindings(
            learning_snapshot_id=None,
            evidence_watermark=None,
            curriculum_version=None,
            goal_version=None,
            schedule_version=None,
            policy_version=None,
            context_view_version=None,
            relationship_view_version=None,
        ),
        expected_turn_state_version=state_version,
    )
    assert isinstance(second_cycle, Ok), second_cycle
    a = SqlitePlannerRecordStore(conn_a, fence_a).record_planner_cycle(
        turn_id=TURN_ID, outcome=_outcome(CYCLE_ID)
    )
    assert isinstance(a, Ok), a
    b = SqlitePlannerRecordStore(conn_b, fence_b).record_planner_cycle(
        turn_id=TURN_ID, outcome=_outcome(DecisionCycleId("dc-p8-5-b"))
    )
    assert isinstance(b, Ok), b
    assert conn_b.execute(
        "SELECT decision_cycle_id FROM runtime_decision_outcome"
    ).fetchone()[0] == "dc-p8-5-b"
    assert conn_b.execute(
        "SELECT COUNT(*) FROM planner_execution_status"
    ).fetchone()[0] == 2
