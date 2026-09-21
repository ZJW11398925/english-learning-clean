"""P4-0 ② — the Teaching owner-lineage fence (DEC-…5ba74efc.68 C2).

Before P4-0 the two *normal* moment-mutation faces (``transition_moment`` /
``terminalize_moment``) only checked the store-epoch fence, so a live epoch
could advance or terminalize a dead epoch's episode without ever passing
through recovery. The fence is now the durable lineage

    Moment → decision_cycle_id → decision_cycle.turn_id →
    turn_record.owner_epoch

and a foreign-epoch moment is refused with AUTHORITY_VIOLATION that names the
explicit recovery channel. Exactly two exits exist for foreign-epoch residue,
and both are asserted here: the recovery sweep
(``recover_orphan_teaching_locks`` / ``ConversationCoordinator.
recover_orphan_teaching``) and the recovery adoption of the owning turn
(``claim_turn_for_recovery``), which moves the lineage on purpose.

Same-epoch behavior is pinned unchanged: the whole P3 suite runs against the
same fence, and the last test drives a real same-epoch transition +
terminalize through the live coordinator.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.platform.db import epoch
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import DomainErrorCode, Err, MomentId, Ok, TurnId
from elc.runtime.controller import ConversationCoordinator
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import TeachingControlIntent
from elc.teaching.store import (
    CP2OpenRequest,
    MomentTransition,
    SqliteTeachingStore,
    cp2_action_intent,
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

from .conftest import (
    FOCUS_TARGET,
    control,
    open_moment,
    reply_ok,
)

MOMENT_OPENING = MomentState.OPENING
TRANSITION_TO_AWAITING = MomentTransition(
    lifecycle_state=MomentState.AWAITING_USER
)


def _moment(cycle_id: str, conversation_id: str) -> TeachingMomentRecord:
    return TeachingMomentRecord(
        moment_id="tm-lineage",
        conversation_id=conversation_id,  # type: ignore[arg-type]
        persona_id=None,
        source=MomentSource.USER_INITIATED,
        decision_cycle_id=cycle_id,  # type: ignore[arg-type]
        candidate_id="cand-lineage",
        gate_decision_id="gd-lineage",
        focus_target=TeachingTargetRef("RESOURCE", FOCUS_TARGET),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="ESTABLISH",
        evidence_modality="TEXT_PRODUCTION",
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MOMENT_OPENING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.NONE,
        completion_outcome=None,
        abort_reason=None,
        state_version=1,
    )


def _cp2(cycle_id: str, conversation_id: str, turn_id: str, owner_epoch: int):
    return CP2OpenRequest(
        gate_execution_status=GateExecutionStatusRecord(
            gate_execution_status_id="ges-lineage",
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            moment_id=None,
            gate_context=GateDecisionContext.OPEN,
            authorization_basis=AuthorizationBasis.DECISION_CYCLE,
            authorization_status="VALID",
            status=GateExecutionStatusValue.SUCCEEDED,
            missing_or_unknown=(),
        ),
        gate_decision=GateDecisionRecord(
            gate_decision_id="gd-lineage",
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            candidate_id="cand-lineage",
            context=GateDecisionContext.OPEN,
            decision=GateDecisionValue.ALLOW,
            reason_codes=(),
            policy_version="bf-03-gate-v1.1",
        ),
        moment=_moment(cycle_id, conversation_id),
        action=cp2_action_intent(
            turn_id=turn_id,  # type: ignore[arg-type]
            moment_id="tm-lineage",  # type: ignore[arg-type]
            decision_cycle_id=cycle_id,  # type: ignore[arg-type]
            action_id="ga-lineage",  # type: ignore[arg-type]
            assistant_turn_id="aturn-lineage",
            generation_contract_id="gc-teaching-open",
            owner_epoch=owner_epoch,
        ),
        owner_epoch=owner_epoch,
    )


def _open_via_cp2(
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_store: SqliteTeachingStore,
    cmid: str,
) -> TurnId:
    """A durable moment whose owning turn is *nonterminal* (CP0 only): the
    shape that lets the recovery-adoption exit be exercised."""

    cp0 = commit_ok(store, conversation, cmid, "hello")
    cycle = decision_cycle_store.record_decision_cycle(
        decision_cycle_id=f"dcy-{cmid}",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(cycle, Ok), cycle
    opened = teaching_store.open_teaching_moment(
        _cp2(
            f"dcy-{cmid}",
            str(conversation),
            str(cp0.turn_id),
            int(store.current_epoch),
        )
    )
    assert isinstance(opened, Ok), opened
    return cp0.turn_id


def _moment_row(db: sqlite3.Connection, moment_id: str) -> tuple[object, ...]:
    row = db.execute(
        "SELECT lifecycle_state, abort_reason, state_version"
        " FROM teaching_moment WHERE moment_id = ?",
        (moment_id,),
    ).fetchone()
    assert row is not None
    return tuple(row)


def _lock_count(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0])


def test_normal_mutations_refuse_a_foreign_epoch_moment(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_store: SqliteTeachingStore,
) -> None:
    """transition_moment / terminalize_moment on another epoch's moment:
    AUTHORITY_VIOLATION, a message that names the recovery channel, and no
    residue at all (the moment row and its lock are exactly as they were)."""

    turn_id = _open_via_cp2(
        store, conversation, decision_cycle_store, teaching_store, "cm-c2-refuse"
    )
    before = _moment_row(db, "tm-lineage")
    assert before[0] == MOMENT_OPENING.value
    assert _lock_count(db) == 1

    new_fence = epoch.open_runtime_epoch(db)
    current = SqliteTeachingStore(db, new_fence)

    transitioned = current.transition_moment(
        MomentId("tm-lineage"), TRANSITION_TO_AWAITING, 1
    )
    assert isinstance(transitioned, Err), transitioned
    assert transitioned.error.code is DomainErrorCode.AUTHORITY_VIOLATION
    message = transitioned.error.message
    assert "recover_orphan_teaching" in message
    assert "epoch" in message

    terminalized = current.terminalize_moment(
        MomentId("tm-lineage"), abort_reason="USER_SKIP"
    )
    assert isinstance(terminalized, Err), terminalized
    assert terminalized.error.code is DomainErrorCode.AUTHORITY_VIOLATION
    assert "recover_orphan_teaching" in terminalized.error.message

    # No partial write: the moment and its lock are untouched.
    assert _moment_row(db, "tm-lineage") == before
    assert _lock_count(db) == 1
    assert _moment_row(db, "tm-lineage")[1] is None
    del turn_id


def test_the_recovery_sweep_is_the_sanctioned_exit_for_the_residue(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_store: SqliteTeachingStore,
) -> None:
    """The explicit recovery channel still does exactly what the refusal
    points at: it closes the foreign-epoch episode and releases its lock —
    which is what unseals the conversation for the new epoch."""

    _open_via_cp2(
        store, conversation, decision_cycle_store, teaching_store, "cm-c2-sweep"
    )
    new_fence = epoch.open_runtime_epoch(db)
    current = TeachingController(SqliteTeachingStore(db, new_fence))

    refused = current.transition_moment(
        MomentId("tm-lineage"), TRANSITION_TO_AWAITING, 1
    )
    assert isinstance(refused, Err)

    recovered = current.recover_orphan_locks()
    assert isinstance(recovered, Ok), recovered
    assert recovered.value == ("tm-lineage",)
    assert _moment_row(db, "tm-lineage") == (
        MomentState.CLOSED.value,
        "SYSTEM_RECOVERY_ABORT",
        2,
    )
    assert _lock_count(db) == 0


def test_claiming_the_owning_turn_restores_the_normal_path(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    fence: RuntimeEpochFence,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_store: SqliteTeachingStore,
) -> None:
    """The second sanctioned exit (RUNTIME §24 restart ownership): adopting
    the owning turn moves ``owner_epoch`` to the current epoch, and the
    lineage fence — which is exactly what it checks — lets the mutation
    through. The fence is a lineage check, not a blanket lock."""

    turn_id = _open_via_cp2(
        store, conversation, decision_cycle_store, teaching_store, "cm-c2-claim"
    )
    new_fence = epoch.open_runtime_epoch(db)
    current = SqliteTeachingStore(db, new_fence)
    new_conversation = SqliteConversationStore(db, new_fence)

    refused = current.transition_moment(
        MomentId("tm-lineage"), TRANSITION_TO_AWAITING, 1
    )
    assert isinstance(refused, Err)

    claimed = new_conversation.claim_turn_for_recovery(turn_id)
    assert isinstance(claimed, Ok), claimed
    assert int(claimed.value.owner_epoch) == int(new_fence.current)

    allowed = current.transition_moment(
        MomentId("tm-lineage"), TRANSITION_TO_AWAITING, 1
    )
    assert isinstance(allowed, Ok), allowed
    assert allowed.value.lifecycle_state is MomentState.AWAITING_USER
    assert _lock_count(db) == 1


def test_the_same_epoch_path_is_untouched(
    db: sqlite3.Connection,
    coordinator: ConversationCoordinator,
    teaching_controller: TeachingController,
) -> None:
    """Zero same-epoch regression: a real moment opened, advanced and closed
    by the live coordinator keeps behaving exactly as before the fence (the
    rest of the evidence is the whole P3 suite running against it)."""

    opened = open_moment(coordinator, "cm-c2-same-open")
    assert opened.moment_state is MomentState.AWAITING_USER

    hinted = reply_ok(
        coordinator, control(TeachingControlIntent.ASK_HINT), "cm-c2-hint"
    )
    assert hinted.moment_state is MomentState.AWAITING_USER
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    # The first hint rung the ladder lands on (the P3-1B behavior, unchanged
    # by the fence).
    assert moment.value.support_level is TeachingSupportLevel.SEMANTIC_HINT

    revealed = reply_ok(
        coordinator, control(TeachingControlIntent.ASK_ANSWER), "cm-c2-reveal"
    )
    assert revealed.moment_state is MomentState.AWAITING_USER
    revealed_moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(revealed_moment, Ok) and revealed_moment.value is not None
    assert (
        revealed_moment.value.presentation_phase
        is PresentationPhase.FULL_REVEAL
    )

    skipped = reply_ok(
        coordinator, control(TeachingControlIntent.SKIP), "cm-c2-skip"
    )
    assert skipped.closure == "USER_SKIP"
    closed = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(closed, Ok) and closed.value is not None
    assert closed.value.lifecycle_state is MomentState.CLOSED
    assert _lock_count(db) == 0
