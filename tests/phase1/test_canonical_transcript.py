"""VAL ⑥ — canonical transcript contains only canonicalized output.

VAL ⑥: canonical transcript 查询只含已 canonicalize 的 AssistantTurn，未
delivery 的输出不入 transcript (docs/DOMAIN_MODEL.md §3 key rule;
RUNTIME_ARCHITECTURE.md R-INV-006).
"""

from __future__ import annotations

import sqlite3

from elc.conversation import AssistantTurnRecord, SqliteConversationStore
from elc.conversation.types import DeliveryState, TurnOutcome
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ConversationId,
    DecisionCycleId,
    Err,
    MessageSequence,
    Ok,
    TurnSequence,
)
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
)
from tests.phase1.conftest import CONV, commit_ok


def make_action(
    generation_store: SqliteGenerationStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    action_id: str,
    turn,
) -> None:
    """cs-0 随迁（测试助手，不是放宽）：person-visible 窗口只保留
    §20 action 为普通回信的 assistant 行（fail-closed）——运行时写下的每
    个 canonical 行本就带着自己的 action 行，手工构造的 canonical 行也照
    真实形状补上（cycle 行 + NORMAL_PERSONA_REPLY action 行）。"""

    cycle = decision_cycle_store.record_decision_cycle(
        decision_cycle_id=DecisionCycleId(f"dcy-{action_id}"),
        turn_id=turn.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=turn.state_version,
    )
    assert isinstance(cycle, Ok), cycle
    created = generation_store.create_action(
        GenerationActionIntentRecord(
            action_id=ActionId(action_id),
            turn_id=turn.turn_id,
            decision_cycle_id=cycle.value.decision_cycle_id,
            moment_id=None,
            assistant_turn_id=f"aturn-{action_id}",
            action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
            generation_contract_id="gc-p1-normal",
            status=GenerationActionStatus.PREPARED,
            attempt_count=0,
            created_at=None,
            owner_epoch=None,
        )
    )
    assert isinstance(created, Ok), created


def make_assistant(
    turn_id: object,
    assistant_turn_id: str,
    content: str,
    delivery_state: DeliveryState,
) -> AssistantTurnRecord:
    """Build an AssistantTurnRecord (DATA_MODEL §3); message_sequence is
    store-allocated, so the input value here is a placeholder."""
    return AssistantTurnRecord(
        assistant_turn_id=AssistantTurnId(assistant_turn_id),
        turn_id=turn_id,  # type: ignore[arg-type]
        conversation_id=CONV,
        turn_sequence=TurnSequence(0),
        message_sequence=MessageSequence(0),
        action_id=ActionId(f"act-{assistant_turn_id}"),
        content=content,
        delivery_state=delivery_state,
        delivery_certainty="SERVER_SENT_UNCONFIRMED",
    )


def test_undelivered_output_never_enters_transcript(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """VAL ⑥: a NOT_SENT provider output is refused at canonicalization and
    the transcript shows the turn with no AssistantTurn."""
    turn = commit_ok(store, CONV, "cm-1", "question")

    refused = store.canonicalize_assistant_turn(
        make_assistant(
            turn.turn_id, "at-refused", "secret draft", DeliveryState.NOT_SENT
        )
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"

    assert _count(db, "assistant_turn") == 0
    window = store.get_conversation_window(CONV, 10)
    assert isinstance(window, Ok)
    assert len(window.value.slices) == 1
    assert window.value.slices[0].assistant_turn is None
    assert window.value.slices[0].user_turn.raw_content == "question"


def test_delivered_output_canonicalizes_once_and_appears(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
    generation_store: SqliteGenerationStore,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    """VAL ⑥: SENT_COMPLETE output is canonicalized exactly once (idempotent
    by turn) and is the only assistant content the transcript exposes."""
    turn = commit_ok(store, CONV, "cm-1", "question")
    make_action(generation_store, decision_cycle_store, "act-at-1", turn)

    first = store.canonicalize_assistant_turn(
        make_assistant(
            turn.turn_id, "at-1", "Hello!", DeliveryState.SENT_COMPLETE
        )
    )
    assert isinstance(first, Ok)

    replay = store.canonicalize_assistant_turn(
        make_assistant(
            turn.turn_id, "at-1-duplicate", "Hello!", DeliveryState.SENT_COMPLETE
        )
    )
    assert isinstance(replay, Ok)
    assert replay.value == first.value
    assert _count(db, "assistant_turn") == 1

    window = store.get_conversation_window(CONV, 10)
    assert isinstance(window, Ok)
    slice_ = window.value.slices[0]
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.content == "Hello!"
    assert slice_.assistant_turn.assistant_turn_id == first.value
    # The assistant turn shares the coordination turn's turn_sequence and
    # carries its own message_sequence (DATA_MODEL §3).
    assert slice_.assistant_turn.turn_sequence == slice_.user_turn.turn_sequence
    assert slice_.assistant_turn.message_sequence > slice_.user_turn.message_sequence


def test_partial_delivery_canonicalizes_marked_partial(
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """Partial delivery canonicalizes the sent boundary with SENT_PARTIAL
    (RUNTIME §17 partial delivery: 不自动从头重放)."""
    turn = commit_ok(store, CONV, "cm-1", "question")
    partial = store.canonicalize_assistant_turn(
        make_assistant(
            turn.turn_id, "at-p", "partial answer", DeliveryState.SENT_PARTIAL
        )
    )
    assert isinstance(partial, Ok)

    slice_result = store.get_canonical_turn_slice(turn.turn_id)
    assert isinstance(slice_result, Ok)
    assert slice_result.value is not None
    assert slice_result.value.assistant_turn is not None
    assert (
        slice_result.value.assistant_turn.delivery_state == DeliveryState.SENT_PARTIAL
    )


def test_window_orders_by_turn_sequence_and_slices(
    store: SqliteConversationStore,
    conversation: ConversationId,
    generation_store: SqliteGenerationStore,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    """The transcript window returns the latest ``max_turns`` slices in
    ascending turn_sequence order; undelivered drafts appear nowhere."""
    t1 = commit_ok(store, CONV, "cm-1", "one")
    t2 = commit_ok(store, CONV, "cm-2", "two")
    t3 = commit_ok(store, CONV, "cm-3", "three")
    assert t1.turn_sequence < t2.turn_sequence < t3.turn_sequence

    make_action(generation_store, decision_cycle_store, "act-at-2", t2)
    canonical = store.canonicalize_assistant_turn(
        make_assistant(t2.turn_id, "at-2", "answer two", DeliveryState.SENT_COMPLETE)
    )
    assert isinstance(canonical, Ok)

    window = store.get_conversation_window(CONV, 2)
    assert isinstance(window, Ok)
    assert [s.turn_sequence for s in window.value.slices] == [2, 3]
    assert window.value.slices[0].assistant_turn is not None
    assert window.value.slices[0].assistant_turn.content == "answer two"
    assert window.value.slices[1].assistant_turn is None

    full = store.get_conversation_window(CONV, 10)
    assert isinstance(full, Ok)
    assert [s.turn_sequence for s in full.value.slices] == [1, 2, 3]


def test_slice_outcome_after_terminalize(
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """The CanonicalTurnSlice outcome comes from the TurnRecord's terminal
    turn_outcome (STATE_MACHINES §10: Turn outcome 单独记录)."""
    turn = commit_ok(store, CONV, "cm-1", "one")
    before = store.get_canonical_turn_slice(turn.turn_id)
    assert isinstance(before, Ok)
    assert before.value is not None
    assert before.value.outcome is None

    terminal = store.terminalize_turn(turn.turn_id, TurnOutcome.REPLIED_FULL)
    assert isinstance(terminal, Ok)

    after = store.get_canonical_turn_slice(turn.turn_id)
    assert isinstance(after, Ok)
    assert after.value is not None
    assert after.value.outcome == TurnOutcome.REPLIED_FULL


def _count(db: sqlite3.Connection, table: str) -> int:
    row = db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()
    assert row is not None
    return int(row[0])
