"""P3-2 三项留痕（DEC-OPI-5ba74efc-9f26-483b-a7de-c833834275a4.20 必带）。

P3-1B 独立评审留下的三项未覆盖面，本刀（P3-2，TASK-…5ba74efc.24 ②）逐项落地：

(a) 孤儿锁恢复入口挂启动扫描——`StartupRecoveryScanner` 现经可选
    `TeachingLockRecoverySource` port 在计划里点名死 epoch 的
    TeachingLockLease 残锁（kind=LOCK / action=RELEASE_ORPHAN_TEACHING_LOCK），
    使 `ConversationCoordinator.recover_orphan_teaching` 在恢复路径可达；
    扫描仍是纯读（计划=读，apply=协调者的写），当前 epoch 的活锁不误收
    （STATE_MACHINES §9 / §24.1：epoch 是活性事实，无 TTL/heartbeat）。

(b) DELIVERING 槽 reply turn 重入——`respond_to_teaching` 对 DELIVERING 状态
    turn 的行为钉死：以 durable 记录为准完成交付腿（RA §23 CP3「canonicalized
    assistant turn is the truth」/ RUNTIME §24.1 CONSERVATIVE_DELIVERY_
    RECONCILIATION）。已落 transcript → 补完 action/终态化/梯级对账，绝不重发；
    未落 transcript → 交付确实失败，§7 DELIVERY_FAILURE 收尾并释放锁（不再
    让一个回合作废的回复把 moment 永久钉在 DECIDING_NEXT_ACTION 持有锁）。
    该槽的另两个半窗口同样钉死（修复刀 F4）：action 仍 DELIVERING 但
    transcript 已落（从记录补完 action，不重派发）；新 epoch 重入旧 epoch
    的 mid-flight action（CONFLICT + 指路 orphan-lock sweep，零部分写入）。

(c) continuation Gate 跨 turn 冲突防护——同 id 双写的 durable 语义钉死：
    完全相同的 (status, decision) 重写=回首条 durable 事实（幂等回放，零新行）；
    相同 status id 但不同 decision 的第二个写者=CONFLICT 拒绝、零残留、首条
    事实不被替换（"the durable facts are the authority"，`_replay_continuation_
    gate` 的文档语义获得防护测试）。

红线自查：本文件全部经 Write/Edit 通道落盘；未触碰 migrations / behavioral_
baselines / docs 六 canonical；测试内 SQL 全参数绑定。
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.learning.controller import LearningController
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db import epoch
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ClientMessageId,
    DomainErrorCode,
    Err,
    MomentId,
    Ok,
    PolicyVersion,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.recovery import (
    TEACHING_LOCK_RECOVERY_ACTION,
    StartupRecoveryScanner,
)
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import (
    AuthorizationBasis,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentState,
    PresentationPhase,
)

from .conftest import CONV, make_lease

REQUESTED_AT = "2026-09-21T14:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"


def _coordinator(
    store,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycles,
    teaching,
    targets,
) -> ConversationCoordinator:
    """The P3-1A/P3-1B assembly with every port passed straight through
    (the crash-window helpers' shape, reused here so a wrapped port can be
    injected)."""

    persona = PersonaRuntime(
        actions=generation_store,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=make_lease(fence),
        conversation_commands=store,
        conversation_queries=store,
        persona=persona,
        generation_actions=generation_store,
        learning=learning,
        decision_cycles=decision_cycles,
        learning_controller=LearningController(learning),
        teaching=teaching,
        targets=targets,
    )


def _open(coordinator: ConversationCoordinator, cmid: str = "cm-open"):
    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=FOCUS_TARGET,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _reply(coordinator: ConversationCoordinator, envelope, cmid: str):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=envelope,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )


def _hint_envelope() -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(control_intent=TeachingControlIntent.ASK_HINT)


def _moment(teaching, moment_id):
    result = teaching.get_moment(moment_id)
    assert isinstance(result, Ok) and result.value is not None
    return result.value


def _lock_count(db: sqlite3.Connection) -> int:
    return int(
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
    )


# ---------------------------------------------------------------------------
# (a) the orphan-lock scan wiring
# ---------------------------------------------------------------------------


def test_carryover_a_the_startup_scan_names_the_orphan_teaching_lock(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """The plan of a new epoch names the dead epoch's lock, the scan is a
    pure read, and the sweep releases exactly what the plan named."""

    del conversation
    old = _open(
        _coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        ),
        cmid="cm-scan-orphan",
    )
    assert _lock_count(db) == 1

    # A restart: a new epoch adopts the world.
    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)
    new_teaching = TeachingController(SqliteTeachingStore(db, new_fence))
    new_coordinator = _coordinator(
        new_store,
        SqliteGenerationStore(db, new_fence),
        new_fence,
        learning,
        SqliteDecisionCycleStore(db, new_fence),
        new_teaching,
        target_provider,
    )

    scanner = StartupRecoveryScanner(
        new_store, make_lease(new_fence), new_teaching
    )
    plan = scanner.scan()
    assert isinstance(plan, Ok), plan
    lock_items = [item for item in plan.value if item.kind == "LOCK"]
    assert [item.id for item in lock_items] == [str(old.moment_id)]
    assert lock_items[0].action == TEACHING_LOCK_RECOVERY_ACTION

    # Pure read: the scan changed nothing — the lock is still there and the
    # moment still awaits its user.
    assert _lock_count(db) == 1
    assert (
        _moment(new_teaching, old.moment_id).lifecycle_state
        is MomentState.AWAITING_USER
    )
    # Repeating the scan yields the same plan (§22 idempotence).
    again = scanner.scan()
    assert isinstance(again, Ok)
    assert [item.id for item in again.value if item.kind == "LOCK"] == [
        str(old.moment_id)
    ]

    # The apply face is the coordinator's, and it releases exactly the lock
    # the plan named — which is what unseals the conversation.
    recovered = new_coordinator.recover_orphan_teaching()
    assert isinstance(recovered, Ok), recovered
    assert recovered.value == tuple(item.id for item in lock_items)
    assert _lock_count(db) == 0
    closed = _moment(new_teaching, old.moment_id)
    assert closed.lifecycle_state is MomentState.CLOSED
    assert closed.abort_reason == "SYSTEM_RECOVERY_ABORT"
    unsealed = _open(new_coordinator, cmid="cm-scan-reopen")
    assert unsealed.gate_decision == "ALLOW"


def test_carryover_a_a_live_epoch_lock_is_never_scanned(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """活锁不误收回归：a lock owned by the current epoch is a real
    mutual-exclusion fact — not in the plan, not in the sweep."""

    del conversation
    opened = _open(
        _coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        ),
        cmid="cm-scan-live",
    )
    scanner = StartupRecoveryScanner(
        store, make_lease(fence), teaching_controller
    )
    plan = scanner.scan()
    assert isinstance(plan, Ok), plan
    assert [item for item in plan.value if item.kind == "LOCK"] == []

    recovered = teaching_controller.recover_orphan_locks()
    assert isinstance(recovered, Ok)
    assert recovered.value == ()
    assert _lock_count(db) == 1
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.AWAITING_USER
    assert moment.abort_reason is None


def test_carryover_a_an_assembly_without_teaching_keeps_the_old_plan_shape(
    store: SqliteConversationStore, fence: RuntimeEpochFence
) -> None:
    """The teaching source is optional: a P1/P2 assembly's plan carries no
    LOCK items at all (the shape its own tests pin)."""

    scanner = StartupRecoveryScanner(store, make_lease(fence))
    plan = scanner.scan()
    assert isinstance(plan, Ok), plan
    assert all(item.kind == "TURN" for item in plan.value)


# ---------------------------------------------------------------------------
# (b) the DELIVERING slot of a reply turn
# ---------------------------------------------------------------------------


def _drive_hint_until_delivering(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    *,
    cmid: str,
):
    """One open + one delivered hint reply, then force the durable
    *DELIVERING* crash shape: the message and the action are durable, the
    turn was never terminalized, and — because a crash inside
    ``finalize_delivery`` dies before the ladder landing (review F1) — the
    moment is still where it was before the delivery."""

    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator, cmid=f"{cmid}-open")
    delivered = _reply(coordinator, _hint_envelope(), f"{cmid}-hint")
    assert isinstance(delivered, Ok), delivered
    assert delivered.value.delivery_kind == "HINT"
    db.execute(
        "UPDATE turn_record SET status = 'DELIVERING' WHERE turn_id = ?",
        (delivered.value.turn_id,),
    )
    db.execute(
        "UPDATE teaching_moment SET lifecycle_state = 'DECIDING_NEXT_ACTION',"
        " presentation_phase = 'INITIAL_PROMPT', support_level = 'CONTEXT_ONLY'"
        " WHERE moment_id = ?",
        (str(opened.moment_id),),
    )
    db.commit()
    assert (
        db.execute(
            "SELECT status FROM turn_record WHERE turn_id = ?",
            (delivered.value.turn_id,),
        ).fetchone()[0]
        == "DELIVERING"
    )
    rewound = _moment(teaching_controller, opened.moment_id)
    assert rewound.lifecycle_state is MomentState.DECIDING_NEXT_ACTION
    assert rewound.presentation_phase is PresentationPhase.INITIAL_PROMPT
    return coordinator, opened, delivered


def test_carryover_b_a_won_delivery_is_finished_from_the_durable_record(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """The assistant turn was canonicalized before the crash: the re-entry
    completes the whole leg from it — no second message, no re-generation,
    turn terminal, ladder reconciled."""

    del conversation
    coordinator, opened, delivered = _drive_hint_until_delivering(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-delivering-lost",
    )
    assistant_before = db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0]
    assert assistant_before == 2  # the opening + the hint

    replayed = _reply(coordinator, _hint_envelope(), "cm-delivering-lost-hint")
    assert isinstance(replayed, Ok), replayed
    assert replayed.value.turn_id == delivered.value.turn_id
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == (
        assistant_before
    )
    turn = db.execute(
        "SELECT status, turn_outcome FROM turn_record WHERE turn_id = ?",
        (delivered.value.turn_id,),
    ).fetchone()
    assert turn == ("COMPLETED", "REPLIED_FULL")
    action = db.execute(
        "SELECT status FROM generation_action_intent WHERE action_id = ?",
        (str(delivered.value.action_id),),
    ).fetchone()
    assert action == ("TERMINAL",)
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.AWAITING_USER
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC
    # Idempotent: the same re-entry again changes nothing.
    once_more = _reply(
        coordinator, _hint_envelope(), "cm-delivering-lost-hint"
    )
    assert isinstance(once_more, Ok), once_more
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == (
        assistant_before
    )


def test_carryover_b_a_lost_delivery_closes_with_delivery_failure(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """The message never became canonical: the re-entry says so honestly —
    the turn terminalizes NO_ASSISTANT_OUTPUT, the episode aborts with the
    §7 DELIVERY_FAILURE word, the lock is released, and no rung is claimed
    for a message nobody saw."""

    del conversation
    coordinator, opened, delivered = _drive_hint_until_delivering(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-delivering-lost2",
    )
    # The pre-canonicalization shape: the action never left DELIVERING and
    # no assistant turn for it exists.
    db.execute(
        "UPDATE generation_action_intent SET status = 'DELIVERING'"
        " WHERE action_id = ?",
        (str(delivered.value.action_id),),
    )
    db.execute(
        "DELETE FROM assistant_turn WHERE action_id = ?",
        (str(delivered.value.action_id),),
    )
    db.commit()

    replayed = _reply(coordinator, _hint_envelope(), "cm-delivering-lost2-hint")
    assert isinstance(replayed, Ok), replayed
    assert replayed.value.closure == "DELIVERY_FAILURE"
    assert replayed.value.moment_state is MomentState.CLOSED
    turn = db.execute(
        "SELECT status, turn_outcome FROM turn_record WHERE turn_id = ?",
        (delivered.value.turn_id,),
    ).fetchone()
    assert turn == ("COMPLETED", "NO_ASSISTANT_OUTPUT")
    action = db.execute(
        "SELECT status FROM generation_action_intent WHERE action_id = ?",
        (str(delivered.value.action_id),),
    ).fetchone()
    assert action == ("TERMINAL",)
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.CLOSED
    assert moment.abort_reason == "DELIVERY_FAILURE"
    # Nothing was shown, so nothing is claimed: the rung never moved.
    assert moment.presentation_phase is PresentationPhase.INITIAL_PROMPT
    assert moment.support_level.value == "CONTEXT_ONLY"
    assert _lock_count(db) == 0


def test_carryover_b_the_mid_flight_action_completes_from_the_record(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """The crash landed after canonicalization but before the action left
    DELIVERING: the assistant turn is the truth, so the action is completed
    from it (never re-dispatched) and the whole leg finishes."""

    del conversation
    coordinator, opened, delivered = _drive_hint_until_delivering(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-delivering-midflight",
    )
    # The other half of the finalize_delivery window: the transcript row
    # exists, the action never reached TERMINAL, the turn never terminalized.
    db.execute(
        "UPDATE generation_action_intent SET status = 'DELIVERING'"
        " WHERE action_id = ?",
        (str(delivered.value.action_id),),
    )
    db.commit()
    assert db.execute(
        "SELECT status FROM generation_action_intent WHERE action_id = ?",
        (str(delivered.value.action_id),),
    ).fetchone() == ("DELIVERING",)
    assistant_before = db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0]

    replayed = _reply(
        coordinator, _hint_envelope(), "cm-delivering-midflight-hint"
    )
    assert isinstance(replayed, Ok), replayed
    assert replayed.value.turn_id == delivered.value.turn_id
    # The action was completed from the canonical record, not re-run.
    assert db.execute(
        "SELECT status FROM generation_action_intent WHERE action_id = ?",
        (str(delivered.value.action_id),),
    ).fetchone() == ("TERMINAL",)
    assert db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == assistant_before
    turn = db.execute(
        "SELECT status, turn_outcome FROM turn_record WHERE turn_id = ?",
        (delivered.value.turn_id,),
    ).fetchone()
    assert turn == ("COMPLETED", "REPLIED_FULL")
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.AWAITING_USER
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC


def test_carryover_b_a_foreign_epoch_delivery_action_is_fenced(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """A new epoch may not advance an old-epoch delivery action: the
    re-entry is refused with the pointer to the orphan-lock sweep, and it
    writes nothing on the way out."""

    del conversation
    coordinator, opened, delivered = _drive_hint_until_delivering(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-delivering-epoch",
    )
    db.execute(
        "UPDATE generation_action_intent SET status = 'DELIVERING'"
        " WHERE action_id = ?",
        (str(delivered.value.action_id),),
    )
    db.commit()
    assistant_before = db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0]

    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)
    new_coordinator = _coordinator(
        new_store,
        SqliteGenerationStore(db, new_fence),
        new_fence,
        learning,
        SqliteDecisionCycleStore(db, new_fence),
        TeachingController(SqliteTeachingStore(db, new_fence)),
        target_provider,
    )
    refused = _reply(
        new_coordinator, _hint_envelope(), "cm-delivering-epoch-hint"
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "orphan" in refused.error.message
    # No partial advance: the action is still mid-flight, no message was
    # added, the turn keeps its DELIVERING coordination state, and the
    # moment is exactly where the crash left it.
    assert db.execute(
        "SELECT status FROM generation_action_intent WHERE action_id = ?",
        (str(delivered.value.action_id),),
    ).fetchone() == ("DELIVERING",)
    assert db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == assistant_before
    assert db.execute(
        "SELECT status FROM turn_record WHERE turn_id = ?",
        (delivered.value.turn_id,),
    ).fetchone() == ("DELIVERING",)
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.DECIDING_NEXT_ACTION
    assert moment.presentation_phase is PresentationPhase.INITIAL_PROMPT


# ---------------------------------------------------------------------------
# (c) the continuation Gate's cross-writer protection
# ---------------------------------------------------------------------------


def test_carryover_c_a_second_writer_can_never_replace_the_recorded_verdict(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """同 id 双写的 durable 语义：完全相同的重写=回首条（幂等）；同 status id
    但不同 decision 的第二个写者=CONFLICT、零残留、首条不被替换。"""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    _open(coordinator, cmid="cm-carryover-c")
    delivered = _reply(coordinator, _hint_envelope(), "cm-carryover-c-hint")
    assert isinstance(delivered, Ok), delivered
    assert delivered.value.gate_decision == "ALLOW"

    turn_id = delivered.value.turn_id
    status_id = f"ges-{turn_id}-continuation"
    decision_id = f"gd-{turn_id}-continuation"
    durable_status = db.execute(
        "SELECT decision_cycle_id, gate_context, authorization_basis,"
        " authorization_status, status, missing_or_unknown"
        " FROM gate_execution_status WHERE gate_execution_status_id = ?",
        (status_id,),
    ).fetchone()
    assert durable_status is not None
    assert durable_status[2] == "ACTIVE_MOMENT"  # §12.1 continuation basis
    assert durable_status[3:5] == ("VALID", "SUCCEEDED")

    # (1) The identical write — the retry shape — hits the recorded fact and
    # replays it: Ok, one row, nothing rewritten.
    identical = teaching_controller.record_gate_allow(
        teaching_controller._store.get_gate_execution_statuses(
            durable_status[0]
        ).value[-1],
        GateDecisionRecord(
            gate_decision_id=decision_id,
            decision_cycle_id=durable_status[0],
            candidate_id="cand-explicit-probe",
            context=GateDecisionContext.USER_REQUESTED_CONTINUE,
            decision=GateDecisionValue.ALLOW,
            reason_codes=(),
            policy_version=PolicyVersion("bf03-v1.1"),
        ),
    )
    assert isinstance(identical, Ok), identical
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status"
            " WHERE gate_execution_status_id = ?",
            (status_id,),
        ).fetchone()[0]
        == 1
    )

    # (2) A conflicting writer asserting the SAME status id with its own
    # decision: the first durable write wins; the second is refused with no
    # residue and no rewrite of the recorded verdict.
    statuses_before = db.execute(
        "SELECT COUNT(*) FROM gate_execution_status"
    ).fetchone()[0]
    decisions_before = db.execute(
        "SELECT COUNT(*) FROM gate_decision"
    ).fetchone()[0]
    conflicting = teaching_controller.record_gate_denial(
        teaching_controller._store.get_gate_execution_statuses(
            durable_status[0]
        ).value[-1],
        GateDecisionRecord(
            gate_decision_id=f"gd-{turn_id}-continuation-other",
            decision_cycle_id=durable_status[0],
            candidate_id="cand-other-writer",
            context=GateDecisionContext.USER_REQUESTED_CONTINUE,
            decision=GateDecisionValue.DENY,
            reason_codes=("HARD_ATTEMPT_LIMIT",),
            policy_version=PolicyVersion("bf03-v1.1"),
        ),
    )
    assert isinstance(conflicting, Err), conflicting
    assert conflicting.error.code is DomainErrorCode.CONFLICT
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status"
        ).fetchone()[0]
        == statuses_before
    )
    assert (
        db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0]
        == decisions_before
    )
    recorded = db.execute(
        "SELECT decision FROM gate_decision WHERE gate_decision_id = ?",
        (decision_id,),
    ).fetchone()
    assert recorded == ("ALLOW",)

    # A third writer carrying a DEGRADED row under the *same status id*: the
    # F1 replay guard reads the existing status row as the terminal fact, so
    # the call replays (Ok) and — the invariant that matters — writes
    # nothing: the recorded SUCCEEDED row is not rewritten, and no row is
    # added. The first durable write always wins.
    degraded = teaching_controller.record_gate_degraded(
        GateExecutionStatusRecord(
            gate_execution_status_id=status_id,
            decision_cycle_id=durable_status[0],
            moment_id=None,
            gate_context=GateDecisionContext.USER_REQUESTED_CONTINUE,
            authorization_basis=AuthorizationBasis.ACTIVE_MOMENT,
            authorization_status="VALID",
            status=GateExecutionStatusValue.DEGRADED,
            missing_or_unknown=("LEARNING_SNAPSHOT",),
        )
    )
    assert isinstance(degraded, Ok), degraded
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status"
            " WHERE gate_execution_status_id = ?",
            (status_id,),
        ).fetchone()[0]
        == 1
    )
    assert db.execute(
        "SELECT status FROM gate_execution_status"
        " WHERE gate_execution_status_id = ?",
        (status_id,),
    ).fetchone() == ("SUCCEEDED",)
    # The durable outcome is still the one the Gate decided: the next move
    # replays it instead of re-running the Gate, and the recorded status row
    # was never rewritten.
    replay = _reply(coordinator, _hint_envelope(), "cm-carryover-c-hint")
    assert isinstance(replay, Ok), replay
    assert replay.value.turn_id == turn_id
    assert replay.value.outcome == "REPLIED_FULL"
    assert replay.value.moment_state is MomentState.AWAITING_USER
    assert db.execute(
        "SELECT status, decision FROM gate_execution_status s"
        " JOIN gate_decision d ON d.decision_cycle_id = s.decision_cycle_id"
        " WHERE s.gate_execution_status_id = ?",
        (status_id,),
    ).fetchone() == ("SUCCEEDED", "ALLOW")
    moment = _moment(
        teaching_controller, MomentId(str(delivered.value.moment_id))
    )
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC
    assert moment.support_level.value == "SEMANTIC_HINT"
