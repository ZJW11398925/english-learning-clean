"""VAL ⑧ — epoch fencing on the teaching path (no bypass) + the existing
fence regressions.

The P3-1A stores follow the P1/P3-0 paradigm: a write whose adopted epoch
is no longer the newest durable epoch refuses BEFORE anything lands
(``StaleStoreEpochError``), and a current-epoch store also refuses work
owned by another epoch (``AUTHORITY_VIOLATION`` for CP2 on a foreign turn).
Neither the DecisionCycle write face nor the CP2 unit offers a path around
that fence — the coordinator calls the same fenced methods as any other
consumer.

The P1/P3-0 fence regressions (transition_turn / terminalize_turn /
canonicalize_assistant_turn / claim_turn_for_recovery) stay in
tests/phase1/test_recovery_epoch_fencing.py and
tests/phase3/test_canonicalize_epoch_fence.py; this file adds the teaching
side.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.platform.db import epoch
from elc.platform.db.decision_cycle_store import (
    SqliteDecisionCycleStore,
)
from elc.platform.db.decision_cycle_store import (
    StaleStoreEpochError as DecisionCycleStaleError,
)
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, Ok
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.teaching.store import (
    CP2OpenRequest,
    SqliteTeachingStore,
    cp2_action_intent,
)
from elc.teaching.store import (
    StaleStoreEpochError as TeachingStaleError,
)
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

TEACHING_TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in TEACHING_TABLES
    }


def _moment(cycle_id: str, conversation_id: str, turn_id: str) -> TeachingMomentRecord:
    del turn_id
    return TeachingMomentRecord(
        moment_id="tm-fence",
        conversation_id=conversation_id,  # type: ignore[arg-type]
        persona_id=None,
        source=MomentSource.USER_INITIATED,
        decision_cycle_id=cycle_id,  # type: ignore[arg-type]
        candidate_id="cand-fence",
        gate_decision_id="gd-fence",
        focus_target=TeachingTargetRef("RESOURCE", "res-hedge-i-think"),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="ESTABLISH",
        evidence_modality="TEXT_PRODUCTION",
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id="lsnap-fence",
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
    cycle_id: str, conversation_id: str, turn_id: str, owner_epoch: int
) -> CP2OpenRequest:
    return CP2OpenRequest(
        gate_execution_status=GateExecutionStatusRecord(
            gate_execution_status_id="ges-fence",
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            moment_id=None,
            gate_context=GateDecisionContext.OPEN,
            authorization_basis=AuthorizationBasis.DECISION_CYCLE,
            authorization_status="VALID",
            status=GateExecutionStatusValue.SUCCEEDED,
            missing_or_unknown=(),
        ),
        gate_decision=GateDecisionRecord(
            gate_decision_id="gd-fence",
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            candidate_id="cand-fence",
            context=GateDecisionContext.OPEN,
            decision=GateDecisionValue.ALLOW,
            reason_codes=(),
            policy_version="bf-03-gate-v1.1",
        ),
        moment=_moment(cycle_id, conversation_id, turn_id),
        action=cp2_action_intent(
            turn_id=turn_id,  # type: ignore[arg-type]
            moment_id="tm-fence",  # type: ignore[arg-type]
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            action_id="ga-fence",  # type: ignore[arg-type]
            assistant_turn_id="aturn-fence",
            generation_contract_id="gc-teaching-open",
            owner_epoch=owner_epoch,
        ),
        owner_epoch=owner_epoch,
    )


def test_stale_decision_cycle_store_refuses_before_writing(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
) -> None:
    cycle_store = SqliteDecisionCycleStore(db, fence)
    cp0 = commit_ok(store, conversation, "cm-fence-dc", "hello")

    epoch.open_runtime_epoch(db)  # a newer runtime epoch now exists
    with pytest.raises(DecisionCycleStaleError):
        cycle_store.record_decision_cycle(
            decision_cycle_id="dcy-fenced",
            turn_id=cp0.turn_id,
            bindings=DecisionCycleBindings(),
            expected_turn_state_version=cp0.state_version,
        )
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 0
    pointer = db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (cp0.turn_id,),
    ).fetchone()
    assert pointer is not None and pointer[0] is None
    assert not db.in_transaction


def test_current_epoch_store_still_writes_after_a_restart(
    db: sqlite3.Connection, store: SqliteConversationStore, conversation
) -> None:
    """Regression half: the fence bounds the old epoch, not the new one."""

    cp0 = commit_ok(store, conversation, "cm-fence-dc-2", "hello")
    new_fence = epoch.open_runtime_epoch(db)
    fresh = SqliteDecisionCycleStore(db, new_fence)
    new_store = SqliteConversationStore(db, new_fence)
    claimed = new_store.claim_turn_for_recovery(cp0.turn_id)
    assert isinstance(claimed, Ok)
    wrote = fresh.record_decision_cycle(
        decision_cycle_id="dcy-fresh",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=claimed.value.state_version,
    )
    assert isinstance(wrote, Ok), wrote
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 1


def test_stale_teaching_store_refuses_cp2_without_residue(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-fence-cp2", "hello")
    cycle = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-fence-cp2",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(cycle, Ok)
    teaching = SqliteTeachingStore(db, fence)

    epoch.open_runtime_epoch(db)
    with pytest.raises(TeachingStaleError):
        teaching.open_teaching_moment(
            _cp2("dcy-fence-cp2", str(conversation), str(cp0.turn_id), 1)
        )
    assert _counts(db) == {table: 0 for table in TEACHING_TABLES}
    assert not db.in_transaction


def test_cp2_refuses_a_foreign_epoch_turn(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    """The current epoch cannot open a moment for a turn nobody claimed:
    AUTHORITY_VIOLATION, no residue (the canonicalize precedent)."""

    cp0 = commit_ok(store, conversation, "cm-fence-cp2-2", "hello")
    cycle = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-fence-cp2-2",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(cycle, Ok)
    new_fence = epoch.open_runtime_epoch(db)
    teaching = SqliteTeachingStore(db, new_fence)
    refused = teaching.open_teaching_moment(
        _cp2(
            "dcy-fence-cp2-2",
            str(conversation),
            str(cp0.turn_id),
            new_fence.current,
        )
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "AUTHORITY_VIOLATION"
    assert "fenced by" in refused.error.message
    assert _counts(db) == {table: 0 for table in TEACHING_TABLES}

    # After the recovery claim adopts the turn, the same CP2 succeeds.
    new_store = SqliteConversationStore(db, new_fence)
    claimed = new_store.claim_turn_for_recovery(cp0.turn_id)
    assert isinstance(claimed, Ok)
    opened = teaching.open_teaching_moment(
        _cp2(
            "dcy-fence-cp2-2",
            str(conversation),
            str(cp0.turn_id),
            new_fence.current,
        )
    )
    assert isinstance(opened, Ok), opened


def test_gate_reads_are_never_fenced_away(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    """Reads stay readable (the P1A/P3-0 rule: the fence bounds writes);
    the same read through a stale store returns the durable truth."""

    cp0 = commit_ok(store, conversation, "cm-fence-read", "hello")
    cycle = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-fence-read",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(cycle, Ok)
    stale_teaching = SqliteTeachingStore(db, fence)
    epoch.open_runtime_epoch(db)
    active = stale_teaching.get_active_moment(conversation)
    assert isinstance(active, Ok) and active.value is None
    statuses = stale_teaching.get_gate_execution_statuses("dcy-fence-read")
    assert isinstance(statuses, Ok) and statuses.value == ()
