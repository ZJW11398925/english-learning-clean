"""VAL ④ — CP2: the five-fact atomic open (+ the two other Gate outputs).

docs/RUNTIME_ARCHITECTURE.md §6 CP2 / §4 step 10B: ALLOW commits

    GateExecutionStatus(SUCCEEDED)
    GateDecision(ALLOW)
    TeachingMoment(OPENING)
    active_teaching_lock(conversation_id UNIQUE, moment_id, state_version=1)
    GenerationActionIntent(TEACHING_OPEN, PREPARED)

in ONE short transaction — five facts or none. DENY commits two facts
(GateExecutionStatus(SUCCEEDED) + GateDecision(DENY)) and creates no
Moment / Lock / Action; DEGRADED commits one fact (GateExecutionStatus
(DEGRADED)) and **no** GateDecision (never a synthetic DENY).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.types import Err, Ok
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.teaching.gate import GATE_POLICY_VERSION
from elc.teaching.store import CP2OpenRequest, cp2_action_intent
from elc.teaching.types import (
    AuthorizationBasis,
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
from tests.phase2.conftest import commit_ok

TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        )
        for table in TABLES
    }


@pytest.fixture()
def cp2_world(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> tuple[str, str]:
    """A conversation + one GENERATING turn + its cycle (the CP2 parents)."""

    cp0 = commit_ok(store, conversation, "cm-cp2", "hello")
    cycle = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-cp2",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(
            learning_snapshot_id="lsnap-cp2", evidence_watermark=1
        ),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(cycle, Ok), cycle
    return str(cp0.turn_id), str(conversation)


def _status(
    *,
    cycle_id: str,
    status: GateExecutionStatusValue = GateExecutionStatusValue.SUCCEEDED,
    missing: tuple[str, ...] = (),
) -> GateExecutionStatusRecord:
    return GateExecutionStatusRecord(
        gate_execution_status_id=f"ges-{status.value.lower()}",
        decision_cycle_id=cycle_id,
        moment_id=None,
        gate_context=GateDecisionContext.OPEN,
        authorization_basis=AuthorizationBasis.DECISION_CYCLE,
        authorization_status="VALID",
        status=status,
        missing_or_unknown=missing,
    )


def _decision(cycle_id: str, value: GateDecisionValue) -> GateDecisionRecord:
    return GateDecisionRecord(
        gate_decision_id=f"gd-{value.value.lower()}",
        decision_cycle_id=cycle_id,
        candidate_id="cand-explicit-1",
        context=GateDecisionContext.OPEN,
        decision=value,
        reason_codes=() if value is GateDecisionValue.ALLOW else ("TARGET_INVALID",),
        policy_version=GATE_POLICY_VERSION,
    )


def _moment(cycle_id: str, conversation_id: str) -> TeachingMomentRecord:
    return TeachingMomentRecord(
        moment_id="tm-cp2",
        conversation_id=conversation_id,
        persona_id=None,
        source=MomentSource.USER_INITIATED,
        decision_cycle_id=cycle_id,
        candidate_id="cand-explicit-1",
        gate_decision_id="gd-allow",
        focus_target=TeachingTargetRef("RESOURCE", "res-hedge-i-think"),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="ESTABLISH",
        evidence_modality="TEXT_PRODUCTION",
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id="lsnap-cp2",
        evidence_watermark=1,
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
    )


def _cp2(
    cycle_id: str,
    conversation_id: str,
    turn_id: str,
    *,
    action_id: str = "ga-cp2",
) -> CP2OpenRequest:
    return CP2OpenRequest(
        gate_execution_status=_status(cycle_id=cycle_id),
        gate_decision=_decision(cycle_id, GateDecisionValue.ALLOW),
        moment=_moment(cycle_id, conversation_id),
        action=cp2_action_intent(
            turn_id=turn_id,  # type: ignore[arg-type]
            moment_id="tm-cp2",  # type: ignore[arg-type]
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            action_id=action_id,  # type: ignore[arg-type]
            assistant_turn_id="aturn-cp2",
            generation_contract_id="gc-teaching-open",
            owner_epoch=1,
        ),
        owner_epoch=1,
    )


def test_allow_commits_five_facts_in_one_short_transaction(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    del db
    turn_id, conversation_id = cp2_world
    result = teaching_controller.commit_cp2_open(
        _cp2("dcy-cp2", conversation_id, turn_id)
    )
    assert isinstance(result, Ok), result
    moment = teaching_controller.get_moment("tm-cp2")
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.lifecycle_state is MomentState.OPENING
    assert moment.value.source is MomentSource.USER_INITIATED
    assert moment.value.presentation_phase is PresentationPhase.INITIAL_PROMPT
    assert moment.value.attempt_index == 0
    assert moment.value.state_version == 1
    assert moment.value.learning_snapshot_id == "lsnap-cp2"
    assert moment.value.opened_at is not None


def test_five_facts_land_together_and_are_durable(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    turn_id, conversation_id = cp2_world
    assert teaching_controller.commit_cp2_open(
        _cp2("dcy-cp2", conversation_id, turn_id)
    )
    counts = _counts(db)
    assert counts["gate_execution_status"] == 1
    assert counts["gate_decision"] == 1
    assert counts["teaching_moment"] == 1
    assert counts["active_teaching_lock"] == 1
    assert counts["generation_action_intent"] == 1

    lock = db.execute(
        "SELECT conversation_id, moment_id, state_version"
        " FROM active_teaching_lock"
    ).fetchone()
    assert lock == (conversation_id, "tm-cp2", 1)
    status = db.execute(
        "SELECT status, authorization_basis, decision_cycle_id, moment_id,"
        " missing_or_unknown FROM gate_execution_status"
    ).fetchone()
    assert status == (
        "SUCCEEDED",
        "DECISION_CYCLE",
        "dcy-cp2",
        None,  # OPEN binds the cycle; the moment link is NULL
        "[]",
    )
    decision = db.execute(
        "SELECT decision, context, reason_codes, policy_version"
        " FROM gate_decision"
    ).fetchone()
    assert decision == ("ALLOW", "OPEN", "[]", "bf-03-gate-v1.1")
    action = db.execute(
        "SELECT action_type, status, moment_id, decision_cycle_id,"
        " attempt_count, owner_epoch FROM generation_action_intent"
    ).fetchone()
    assert action == ("TEACHING_OPEN", "PREPARED", "tm-cp2", "dcy-cp2", 0, 1)
    assert not db.in_transaction


def test_interrupted_unit_leaves_no_residue(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    """The DP ④ injection: another moment already holds the conversation's
    lock, so the LAST insert of the unit fails — the whole unit rolls back
    and no half-open moment is reachable (STATE_MACHINES §9)."""

    turn_id, conversation_id = cp2_world
    db.execute(
        "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
        " state_version) VALUES (?, 'tm-other', 1)",
        (conversation_id,),
    )
    db.commit()
    before = _counts(db)

    refused = teaching_controller.commit_cp2_open(
        _cp2("dcy-cp2", conversation_id, turn_id)
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"
    after = _counts(db)
    assert after == before  # nothing landed: no gate rows, moment or action
    assert after["generation_action_intent"] == 0
    assert not db.in_transaction
    lock = db.execute(
        "SELECT moment_id FROM active_teaching_lock"
    ).fetchall()
    assert lock == [("tm-other",)]  # the occupant is untouched


def test_deny_commits_two_facts_and_no_moment(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    turn_id, conversation_id = cp2_world
    del turn_id, conversation_id
    recorded = teaching_controller.record_gate_denial(
        _status(cycle_id="dcy-cp2"),
        _decision("dcy-cp2", GateDecisionValue.DENY),
    )
    assert isinstance(recorded, Ok)
    counts = _counts(db)
    assert counts["gate_execution_status"] == 1
    assert counts["gate_decision"] == 1
    assert counts["teaching_moment"] == 0
    assert counts["active_teaching_lock"] == 0
    assert counts["generation_action_intent"] == 0
    decision = db.execute(
        "SELECT decision, reason_codes FROM gate_decision"
    ).fetchone()
    assert decision == ("DENY", '["TARGET_INVALID"]')


def test_degraded_commits_one_fact_and_never_a_decision(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    turn_id, conversation_id = cp2_world
    del turn_id, conversation_id
    recorded = teaching_controller.record_gate_degraded(
        _status(
            cycle_id="dcy-cp2",
            status=GateExecutionStatusValue.DEGRADED,
            missing=("LEARNING_SNAPSHOT",),
        )
    )
    assert isinstance(recorded, Ok)
    counts = _counts(db)
    assert counts["gate_execution_status"] == 1
    assert counts["gate_decision"] == 0  # no synthetic DENY, ever
    assert counts["teaching_moment"] == 0
    row = db.execute(
        "SELECT status, missing_or_unknown FROM gate_execution_status"
    ).fetchone()
    assert row == ("DEGRADED", '["LEARNING_SNAPSHOT"]')


def test_allow_face_refuses_other_gate_outputs(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    turn_id, conversation_id = cp2_world
    deny_decision = _decision("dcy-cp2", GateDecisionValue.DENY)
    request = CP2OpenRequest(
        gate_execution_status=_status(cycle_id="dcy-cp2"),
        gate_decision=deny_decision,
        moment=_moment("dcy-cp2", conversation_id),
        action=_cp2("dcy-cp2", conversation_id, turn_id).action,
        owner_epoch=1,
    )
    refused = teaching_controller.commit_cp2_open(request)
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"

    degraded = CP2OpenRequest(
        gate_execution_status=_status(
            cycle_id="dcy-cp2", status=GateExecutionStatusValue.DEGRADED
        ),
        gate_decision=_decision("dcy-cp2", GateDecisionValue.ALLOW),
        moment=_moment("dcy-cp2", conversation_id),
        action=_cp2("dcy-cp2", conversation_id, turn_id).action,
        owner_epoch=1,
    )
    refused_again = teaching_controller.commit_cp2_open(degraded)
    assert isinstance(refused_again, Err)
    assert refused_again.error.code.value == "VALIDATION_FAILED"
    assert _counts(db)["teaching_moment"] == 0


def test_commit_replays_without_a_second_moment(
    db: sqlite3.Connection, teaching_controller, cp2_world
) -> None:
    """Crash-after-CP2 re-dispatch: the same cycle's moment is returned
    and nothing is written twice (RUNTIME §23). Review F6 pinned here: the
    durable moment/first-action pair is canonical — a re-dispatch carrying
    a freshly minted action_id is discarded, so no second action row for
    the cycle can exist (the caller reads the canonical action back via
    the generation store)."""

    turn_id, conversation_id = cp2_world
    first = teaching_controller.commit_cp2_open(
        _cp2("dcy-cp2", conversation_id, turn_id, action_id="ga-first")
    )
    assert isinstance(first, Ok)
    second = teaching_controller.commit_cp2_open(
        _cp2("dcy-cp2", conversation_id, turn_id, action_id="ga-second")
    )
    assert isinstance(second, Ok)
    assert second.value == first.value
    counts = _counts(db)
    assert counts["teaching_moment"] == 1
    assert counts["generation_action_intent"] == 1
    actions = [
        str(row[0])
        for row in db.execute(
            "SELECT action_id FROM generation_action_intent"
            " WHERE moment_id = 'tm-cp2' ORDER BY action_id"
        )
    ]
    assert actions == ["ga-first"]  # the canonical action, not the re-dispatch


def test_lock_is_one_per_conversation(
    db: sqlite3.Connection, store: SqliteConversationStore, teaching_controller
) -> None:
    """DATA_MODEL §18/§25: active_teaching_lock is UNIQUE per conversation —
    a second moment for the same conversation cannot take the lock."""

    first_conv = store.open_conversation(
        "conv-lock-a", user_id="u", persona_id=None, scene_id=None
    )
    second_conv = store.open_conversation(
        "conv-lock-b", user_id="u", persona_id=None, scene_id=None
    )
    assert isinstance(first_conv, Ok) and isinstance(second_conv, Ok)
    db.execute(
        "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
        " state_version) VALUES ('conv-lock-a', 'tm-1', 1)"
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
            " state_version) VALUES ('conv-lock-a', 'tm-2', 1)"
        )
    db.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
            " state_version) VALUES ('conv-lock-b', 'tm-1', 1)"
        )
    db.rollback()
