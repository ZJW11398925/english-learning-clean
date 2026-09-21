"""P3-3 三项必带（DEC-OPI-5ba74efc-9f26-483b-a7de-c833834275a4.43）。

P3-2 独立评审留下的三项未覆盖面，本刀（P3-3，TASK-OPI-5ba74efc-….47 ②）
逐项落地。全链验收的 a-f 场景在 test_p3_3_full_chain.py；本文件是恢复面：

(a) F3 ``recovery_disposition`` 的 DELIVERING 映射修正——从 P1A 占位
    ``RESUME_ACTION_BY_STABLE_ACTION_ID`` 改为 canonical CP3-uncertain 的
    ``CONSERVATIVE_DELIVERY_RECONCILIATION``（RUNTIME_ARCHITECTURE §24.1:766
    "CP3 uncertain → CONSERVATIVE_DELIVERY_RECONCILIATION"；RA §23
    "若 delivery uncertain，保守 canonicalize，不盲目重放"）。CP2 的
    ``GENERATING`` 原文不动。既有测试兼容逐条自裁：P1 场景测试钉的是
    GENERATING（tests/phase1/test_generation_scenarios.py:483），P3-2 恢复
    测试钉的是 DECIDING/GENERATING
    （tests/phase3/test_teaching_recovery.py:325-328）——两处都在本修正的
    影响面之外，全量回归零修订。映射表本身钉在 ``test_f3_*``。

(b) F6 启动扫描装配接线——``ConversationCoordinator.run_startup_recovery``
    把 RUNTIME §22 的 scan 接进启动恢复路径：纯读计划 → 孤儿锁 sweep
    （apply 面）→ sweep 解封后的 turn 级残余对账（F7）。装配测试：孤儿锁
    端到端释放+会话解封、活锁不误收、无 teaching 源时 P1/P2 计划形状不变。

(c) F7 跨 epoch turn 残余对账——旧 epoch 的 DELIVERING turn 在 sweep 之后的
    终态对账路径（turn 级收口 ``_close_residual_turns``），以及与
    ``respond_to_teaching`` 的 claim 行为交互：leg 不可完成的残余不得被提前
    收编（收编会让它从启动扫描的 ``owner_epoch != current`` 视图里消失，
    却不给任何人完成它的权利），只有真正可完成的 leg 才
    adopt → terminalize。

红线自查：本文件全部经 Write/Edit 通道落盘；未触碰 migrations /
behavioral_baselines / docs 六 canonical；测试内 SQL 全参数绑定。
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import CommitUserTurn, SqliteConversationStore
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
    InputId,
    InteractionChannel,
    Ok,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.recovery import (
    RECOVERY_KIND_LOCK,
    RECOVERY_KIND_TURN,
    TEACHING_LOCK_RECOVERY_ACTION,
    StartupRecoveryScanner,
    recovery_disposition,
)
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    InputEnvelope,
    TurnStatus,
)
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import (
    MomentState,
    PresentationPhase,
    TeachingSupportLevel,
)
from tests.conftest import AssemblyGenerationStore

from .conftest import CONV, make_coordinator, make_lease

REQUESTED_AT = "2026-09-21T15:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"


# ---------------------------------------------------------------------------
# helpers (the P3-2 carryover shapes, reused so the residues are identical)
# ---------------------------------------------------------------------------


def _coordinator(
    store,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycles,
    teaching,
    targets,
) -> ConversationCoordinator:
    """The P3-1A/P3-1B assembly with every port passed straight through."""

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


def _open(coordinator: ConversationCoordinator, cmid: str):
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


def _assistant_count(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0])


def _turn_row(db: sqlite3.Connection, turn_id) -> tuple:
    row = db.execute(
        "SELECT status, turn_outcome, owner_epoch FROM turn_record"
        " WHERE turn_id = ?",
        (str(turn_id),),
    ).fetchone()
    assert row is not None
    return (str(row[0]), None if row[1] is None else str(row[1]), int(row[2]))


def _new_epoch_world(
    db: sqlite3.Connection,
    learning,
    target_provider,
) -> tuple[
    RuntimeEpochFence,
    SqliteConversationStore,
    TeachingController,
    ConversationCoordinator,
]:
    """The restart: a new runtime epoch adopting the same app.db."""

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
    return new_fence, new_store, new_teaching, new_coordinator


def _drive_delivering_residue(
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
    """One delivered hint reply, then the durable *DELIVERING* crash shape.

    The message and the action are durable, the action never reached
    TERMINAL, the turn was never terminalized, and — because a crash inside
    ``finalize_delivery`` dies before the ladder landing (review F1) — the
    moment is still where it was before the delivery.
    """

    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator, f"{cmid}-open")
    delivered = _reply(coordinator, _hint_envelope(), f"{cmid}-hint")
    assert isinstance(delivered, Ok), delivered
    assert delivered.value.delivery_kind == "HINT"
    db.execute(
        "UPDATE turn_record SET status = 'DELIVERING' WHERE turn_id = ?",
        (delivered.value.turn_id,),
    )
    db.execute(
        "UPDATE generation_action_intent SET status = 'DELIVERING'"
        " WHERE action_id = ?",
        (str(delivered.value.action_id),),
    )
    db.execute(
        "UPDATE teaching_moment SET lifecycle_state = 'DECIDING_NEXT_ACTION',"
        " presentation_phase = 'INITIAL_PROMPT', support_level = 'CONTEXT_ONLY'"
        " WHERE moment_id = ?",
        (str(opened.moment_id),),
    )
    db.commit()
    assert _turn_row(db, delivered.value.turn_id)[0] == "DELIVERING"
    return opened, delivered


# ---------------------------------------------------------------------------
# (a) F3 — the §24.1 disposition table, DELIVERING corrected
# ---------------------------------------------------------------------------

#: RUNTIME_ARCHITECTURE §24.1's four-word vocabulary, status by status.
#: CP0-committed statuses resume at analysis; DECIDING resumes the decision;
#: GENERATING is the CP2 rule (stable action, still undelivered); DELIVERING
#: is the CP3-uncertain slot and gets the conservative reconciliation. The
#: two post-delivery coordination states have no §24.1 row of their own, so
#: they keep the same conservative word they carried before this review
#: (delivery already happened once — reconcile from the record, never
#: re-dispatch) — pinning them here keeps the table total.
_EXPECTED_DISPOSITION = {
    TurnStatus.RECEIVED: "RESUME_ANALYSIS",
    TurnStatus.USER_COMMITTED: "RESUME_ANALYSIS",
    TurnStatus.ANALYZING: "RESUME_ANALYSIS",
    TurnStatus.FAILED_RECOVERABLE: "RESUME_ANALYSIS",
    TurnStatus.DECIDING: "RESUME_DECISION",
    TurnStatus.GENERATING: "RESUME_ACTION_BY_STABLE_ACTION_ID",
    TurnStatus.DELIVERING: "CONSERVATIVE_DELIVERY_RECONCILIATION",
    TurnStatus.DELIVERY_TERMINAL: "CONSERVATIVE_DELIVERY_RECONCILIATION",
    TurnStatus.POSTPROCESSING: "CONSERVATIVE_DELIVERY_RECONCILIATION",
}


def test_f3_the_delivering_slot_maps_to_the_cp3_reconciliation_word() -> None:
    """F3: DELIVERING is the CP3-uncertain slot (RA §24.1:766), not the CP2
    rule — and the table is total over the nonterminal vocabulary."""

    for status, expected in _EXPECTED_DISPOSITION.items():
        assert recovery_disposition(status) == expected, status

    # Totality: every nonterminal coordination state has a row (a new
    # status must be classified here, never fall through un-noticed).
    nonterminal = {s for s in TurnStatus if s not in TERMINAL_TURN_STATUSES}
    assert nonterminal == set(_EXPECTED_DISPOSITION)

    # Terminal statuses are not recoverable work at all.
    for status in TERMINAL_TURN_STATUSES:
        with pytest.raises(ValueError):
            recovery_disposition(status)

    # The correction moved exactly one slot: GENERATING keeps the CP2 word
    # (the P1A pin), DELIVERING gets the CP3 one.
    assert (
        _EXPECTED_DISPOSITION[TurnStatus.GENERATING]
        == "RESUME_ACTION_BY_STABLE_ACTION_ID"
    )
    assert (
        _EXPECTED_DISPOSITION[TurnStatus.DELIVERING]
        != _EXPECTED_DISPOSITION[TurnStatus.GENERATING]
    )


# ---------------------------------------------------------------------------
# (b) F6 — the startup entry: scan → sweep → turn reconciliation
# ---------------------------------------------------------------------------


def test_f6_the_startup_entry_applies_the_plan_and_unseals_the_conversation(
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
    """The orphan lock is released end-to-end by the startup entry: the plan
    names it, the entry sweeps it (moment CLOSED + SYSTEM_RECOVERY_ABORT),
    the conversation is unsealed, and a second pass finds nothing."""

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
        "cm-f6-orphan",
    )
    assert _lock_count(db) == 1
    # Epoch 1's own turn is terminal (the opening delivery completed), so the
    # new epoch's plan has exactly the lock residue.
    old_epoch = fence.current

    new_fence, new_store, new_teaching, new_coordinator = _new_epoch_world(
        db, learning, target_provider
    )
    outcome = new_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    plan = outcome.value.plan
    assert [item.kind for item in plan] == [RECOVERY_KIND_LOCK]
    assert plan[0].id == str(opened.moment_id)
    assert plan[0].action == TEACHING_LOCK_RECOVERY_ACTION
    # The apply face released exactly what the plan named.
    assert outcome.value.recovered_moments == (str(opened.moment_id),)
    assert outcome.value.closed_turns == ()
    assert _lock_count(db) == 0
    closed = _moment(new_teaching, opened.moment_id)
    assert closed.lifecycle_state is MomentState.CLOSED
    assert closed.abort_reason == "SYSTEM_RECOVERY_ABORT"
    # End-to-end: the conversation is unsealed — a new request is ALLOW and
    # opens a genuinely new moment.
    unsealed = _open(new_coordinator, "cm-f6-reopen")
    assert unsealed.gate_decision == "ALLOW"
    assert unsealed.moment_id != opened.moment_id

    # Idempotent: the next pass has nothing left to name or to apply.
    again = new_coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.plan == ()
    assert again.value.recovered_moments == ()
    assert again.value.closed_turns == ()
    assert new_fence.current != old_epoch


def test_f6_a_live_lock_is_never_swept_by_the_startup_entry(
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
    """活锁不误收回归（经启动入口）：a lock owned by the *current* epoch is a
    real mutual-exclusion fact — not in the plan, not swept, and the
    conversation stays sealed for a second request."""

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
    opened = _open(coordinator, "cm-f6-live")

    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.plan == ()
    assert outcome.value.recovered_moments == ()
    assert outcome.value.closed_turns == ()
    assert _lock_count(db) == 1
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.AWAITING_USER
    assert moment.abort_reason is None

    # The live lock still seals the conversation: a second request is denied
    # by the Gate, not silently let through (STATE_MACHINES §9).
    second = _open(coordinator, "cm-f6-live-2")
    assert second.gate_decision == "DENY"
    assert second.reason_codes == ("TEACHING_LOCK_CONFLICT",)


def test_f6_an_assembly_without_teaching_keeps_the_plan_shape_and_closes_nothing(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
) -> None:
    """The teaching source is optional: a P1/P2 assembly's plan keeps its old
    TURN shape, the startup entry applies nothing, and the named turn keeps
    its own §23 re-entry semantics (no teaching world to close for)."""

    del conversation, generation_store
    # One old-epoch turn parked at the CP2 slot (the crash-after-CP2 shape).
    cp0 = store.commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId("in-cm-f6-p1"),
                client_message_id=ClientMessageId("cm-f6-p1"),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-payload",
                received_at=REQUESTED_AT,
            ),
            raw_content="hello",
            runtime_version="runtime-v1",
        )
    )
    assert isinstance(cp0, Ok), cp0
    advanced = store.transition_turn(
        cp0.value.turn_id, cp0.value.state_version, TurnStatus.GENERATING
    )
    assert isinstance(advanced, Ok), advanced
    del fence

    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)
    p1 = make_coordinator(
        new_store,
        AssemblyGenerationStore(db, new_fence),
        make_lease(new_fence),
        ScriptedPersonaProvider(),
    )
    outcome = p1.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert [
        (item.kind, item.id, item.action) for item in outcome.value.plan
    ] == [(RECOVERY_KIND_TURN, cp0.value.turn_id, "RESUME_ACTION_BY_STABLE_ACTION_ID")]
    # Nothing is applied: no teaching port, so no closure and no sweep.
    assert outcome.value.recovered_moments == ()
    assert outcome.value.closed_turns == ()
    assert _turn_row(db, cp0.value.turn_id)[0] == "GENERATING"

    # The plan is exactly the bare scan's shape (the P1 tests' pin).
    bare = StartupRecoveryScanner(new_store, make_lease(new_fence)).scan()
    assert isinstance(bare, Ok), bare
    assert bare.value == outcome.value.plan


# ---------------------------------------------------------------------------
# (c) F7 — the cross-epoch DELIVERING residue
# ---------------------------------------------------------------------------


def test_f7_the_sweep_unseals_the_delivery_residue_and_the_turn_reconciles(
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
    """F7主线：旧 epoch 的 DELIVERING turn + 孤儿锁。sweep 关掉 moment 之后，
    这条 turn 在新 epoch 里既不能重放（RA §23 禁止盲目重放不确定交付）也不能
    被旧 epoch 推进（fence）——启动入口把它按 durable transcript 收口：消息
    真的发出去了 → REPLIED_FULL，被 fence 的动作原样留证，turn 收编进新
    epoch；再扫为空，同 id 回复按 durable 结果回放，会话解封。"""

    del conversation
    opened, delivered = _drive_delivering_residue(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-f7-residue",
    )
    assistant_before = _assistant_count(db)
    assert assistant_before == 2  # the opening + the hint
    old_epoch = _turn_row(db, delivered.value.turn_id)[2]

    new_fence, new_store, new_teaching, new_coordinator = _new_epoch_world(
        db, learning, target_provider
    )

    # The residue is visible to the startup scan *before* anything is applied
    # (this is what the pre-F7 early adoption used to hide).
    pre_plan = StartupRecoveryScanner(
        new_store, make_lease(new_fence), new_teaching
    ).scan()
    assert isinstance(pre_plan, Ok), pre_plan
    assert [(item.kind, item.id, item.action) for item in pre_plan.value] == [
        (
            RECOVERY_KIND_TURN,
            delivered.value.turn_id,
            "CONSERVATIVE_DELIVERY_RECONCILIATION",
        ),
        (
            RECOVERY_KIND_LOCK,
            str(opened.moment_id),
            TEACHING_LOCK_RECOVERY_ACTION,
        ),
    ]

    outcome = new_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.recovered_moments == (str(opened.moment_id),)
    closures = outcome.value.closed_turns
    assert len(closures) == 1
    closure = closures[0]
    assert closure.turn_id == delivered.value.turn_id
    assert closure.moment_id == str(opened.moment_id)
    # The outcome is read from the transcript, not invented: the message went
    # out, so the turn is REPLIED_FULL (RA §23 "the canonicalized assistant
    # turn is the truth"); the fenced action is recorded where it stopped.
    assert closure.outcome == "REPLIED_FULL"
    assert closure.action_status == "DELIVERING"

    status, turn_outcome, owner_epoch = _turn_row(db, delivered.value.turn_id)
    assert status == "COMPLETED" and turn_outcome == "REPLIED_FULL"
    assert owner_epoch != old_epoch  # adopted into the new epoch
    assert db.execute(
        "SELECT status FROM generation_action_intent WHERE action_id = ?",
        (str(delivered.value.action_id),),
    ).fetchone() == ("DELIVERING",)  # the fenced action is never advanced
    assert _assistant_count(db) == assistant_before  # never re-sent
    moment = _moment(new_teaching, opened.moment_id)
    assert moment.lifecycle_state is MomentState.CLOSED
    assert moment.abort_reason == "SYSTEM_RECOVERY_ABORT"
    assert _lock_count(db) == 0

    # Reconciled means gone from the plan: nothing left for later passes.
    again = new_coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.plan == ()
    assert again.value.closed_turns == ()

    # And the residue is no longer a dead end for its own re-entry: the same
    # client_message_id replays the durable outcome (no new message).
    replayed = _reply(new_coordinator, _hint_envelope(), "cm-f7-residue-hint")
    assert isinstance(replayed, Ok), replayed
    assert replayed.value.turn_id == delivered.value.turn_id
    assert replayed.value.turn_status is TurnStatus.COMPLETED
    assert _assistant_count(db) == assistant_before

    # The conversation is unsealed end-to-end: a new request is ALLOW.
    unsealed = _open(new_coordinator, "cm-f7-residue-reopen")
    assert unsealed.gate_decision == "ALLOW"
    assert unsealed.moment_id != opened.moment_id


def test_f7_a_lost_delivery_residue_closes_with_no_assistant_output(
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
    """F7 降级臂：transcript 里没有这条消息（交付确实没发生）→ 收口
    NO_ASSISTANT_OUTPUT（不假装用户看到了什么），且绝不补发。"""

    del conversation
    opened, delivered = _drive_delivering_residue(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-f7-lost",
    )
    # The pre-canonicalization shape: no assistant turn for this action.
    db.execute(
        "DELETE FROM assistant_turn WHERE action_id = ?",
        (str(delivered.value.action_id),),
    )
    db.commit()
    assistant_before = _assistant_count(db)
    assert assistant_before == 1  # the opening only

    new_fence, new_store, new_teaching, new_coordinator = _new_epoch_world(
        db, learning, target_provider
    )
    outcome = new_coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    closures = outcome.value.closed_turns
    assert len(closures) == 1
    assert closures[0].turn_id == delivered.value.turn_id
    assert closures[0].outcome == "NO_ASSISTANT_OUTPUT"
    assert _turn_row(db, delivered.value.turn_id)[:2] == (
        "COMPLETED",
        "NO_ASSISTANT_OUTPUT",
    )
    assert _assistant_count(db) == assistant_before
    moment = _moment(new_teaching, opened.moment_id)
    assert moment.lifecycle_state is MomentState.CLOSED
    assert moment.abort_reason == "SYSTEM_RECOVERY_ABORT"
    assert _lock_count(db) == 0
    # Nothing was shown, so nothing was claimed: the rung never moved.
    assert moment.presentation_phase is PresentationPhase.INITIAL_PROMPT
    assert moment.support_level is TeachingSupportLevel.CONTEXT_ONLY


def test_f7_the_fenced_reply_leaves_the_residue_visible_to_the_startup_scan(
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
    """F7 与 respond_to_teaching 的 claim 行为交互（收编时机）：leg 不可完成
    （action 属旧 epoch、非 TERMINAL）时，回复入口拒绝且**不收编** turn——
    残余对启动扫描保持可见；只有可完成的 leg 才在收口路径里 adopt。"""

    del conversation
    opened, delivered = _drive_delivering_residue(
        db,
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        cmid="cm-f7-claim",
    )
    old_epoch = _turn_row(db, delivered.value.turn_id)[2]
    assistant_before = _assistant_count(db)

    new_fence, new_store, new_teaching, new_coordinator = _new_epoch_world(
        db, learning, target_provider
    )
    refused = _reply(new_coordinator, _hint_envelope(), "cm-f7-claim-hint")
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "orphan" in refused.error.message
    # Zero partial writes, and — the F7 point — no early adoption: the turn
    # still belongs to the old epoch, so the startup scan can still name it.
    # (``turn_outcome`` is left over from the harness's forced rewind of the
    # coordination status; only status and owner are the facts under test.)
    residue = _turn_row(db, delivered.value.turn_id)
    assert residue[0] == "DELIVERING"
    assert residue[2] == old_epoch
    assert _assistant_count(db) == assistant_before
    moment = _moment(new_teaching, opened.moment_id)
    assert moment.lifecycle_state is MomentState.DECIDING_NEXT_ACTION
    assert moment.presentation_phase is PresentationPhase.INITIAL_PROMPT

    planned = new_coordinator.run_startup_recovery()
    assert isinstance(planned, Ok), planned
    assert [
        (item.kind, item.id) for item in planned.value.plan
    ] == [
        (RECOVERY_KIND_TURN, delivered.value.turn_id),
        (RECOVERY_KIND_LOCK, str(opened.moment_id)),
    ]
    assert planned.value.closed_turns[0].turn_id == delivered.value.turn_id
