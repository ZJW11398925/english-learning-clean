"""VAL ② + ③ — CP0 single short transaction and dual-sequence discipline.

VAL ②: CP0 为单一短事务：UserTurn+TurnRecord 原子提交且 provider 调用前
durable（R-INV-001）。
VAL ③: turn_sequence 与 message_sequence 双序列独立严格递增且在同一 CP0
事务内持久分配（docs/DATA_MODEL.md §3 Sequence Semantics；DecisionCycle
不占 message_sequence 的负例同验）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from elc.conversation import (
    AssistantTurnRecord,
    CommitUserTurn,
    SqliteConversationStore,
)
from elc.conversation.types import DeliveryState
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.tx import require_no_active_transaction
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ConversationId,
    MessageSequence,
    Ok,
    TurnSequence,
)
from elc.runtime.types import TurnStatus
from tests.phase1.conftest import (
    CONV,
    RUNTIME_VERSION,
    commit_ok,
    make_envelope,
)


def test_cp0_midway_failure_leaves_no_window(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """VAL ②: a crash simulated mid-unit (turn_record insert aborted) rolls
    back the whole CP0 — no UserTurn row, no sequence drift, and the same
    input can commit cleanly afterwards (R-INV-001, no half-window)."""
    db.execute(
        "CREATE TRIGGER fail_turn_record BEFORE INSERT ON turn_record"
        " BEGIN SELECT RAISE(ABORT, 'simulated-crash'); END"
    )
    command = CommitUserTurn(
        conversation_id=CONV,
        envelope=make_envelope(CONV, "cm-crash"),
        raw_content="doomed input",
        runtime_version=RUNTIME_VERSION,
    )
    result = store.commit_user_turn(command)

    assert not isinstance(result, Ok)
    assert store_count(db, "user_turn") == 0
    assert store_count(db, "turn_record") == 0
    assert store_count(db, "input_envelope") == 0
    positions = store.get_sequence_positions(CONV)
    assert isinstance(positions, Ok)
    assert positions.value.next_turn_sequence == TurnSequence(1)
    assert positions.value.next_message_sequence == MessageSequence(1)

    # Repair the "crash" and retry the same input: CP0 succeeds at (1, 1).
    db.execute("DROP TRIGGER fail_turn_record")
    retry = store.commit_user_turn(command)
    assert isinstance(retry, Ok)
    assert retry.value.turn_sequence == TurnSequence(1)
    assert retry.value.message_sequence == MessageSequence(1)


def test_cp0_is_durable_before_provider_call(tmp_path: Path) -> None:
    """VAL ② (R-INV-001): CP0 commits a real file-backed app.db before any
    provider call could run — a second connection sees UserTurn+TurnRecord,
    and no transaction is left open (R-INV-004 discipline)."""
    conn = connection.connect(tmp_path / "app.db")
    try:
        migrations.apply_migrations(conn)
        fence = epoch.open_runtime_epoch(conn)
        store = SqliteConversationStore(conn, fence)
        conv = ConversationId("conv-file")
        opened = store.open_conversation(
            conv, user_id=None, persona_id=None, scene_id=None
        )
        assert isinstance(opened, Ok)

        committed = commit_ok(store, conv, "cm-file", "durable before provider")
        require_no_active_transaction(conn, "provider_call")

        witness = sqlite3.connect(str(tmp_path / "app.db"))
        try:
            assert witness.execute("SELECT COUNT(*) FROM user_turn").fetchone()[0] == 1
            assert (
                witness.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0] == 1
            )
            user_row = witness.execute(
                "SELECT turn_sequence, message_sequence FROM user_turn"
                " WHERE turn_id = ?",
                (committed.turn_id,),
            ).fetchone()
            assert user_row == (1, 1)
            status_row = witness.execute(
                "SELECT status FROM turn_record WHERE turn_id = ?",
                (committed.turn_id,),
            ).fetchone()
            assert status_row == ("USER_COMMITTED",)
        finally:
            witness.close()
    finally:
        conn.close()


def test_double_sequence_independent_and_strictly_increasing(
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """VAL ③: turn_sequence advances per coordination turn only;
    message_sequence advances per canonical UserTurn/AssistantTurn only;
    both are allocated inside their CP0 transaction and persisted in
    conversation.next_* (DATA_MODEL §3 Sequence Semantics)."""
    turn1 = commit_ok(store, CONV, "cm-1", "first")
    turn2 = commit_ok(store, CONV, "cm-2", "second")

    assert (turn1.turn_sequence, turn1.message_sequence) == (1, 1)
    assert (turn2.turn_sequence, turn2.message_sequence) == (2, 2)

    # The turn's AssistantTurn shares turn_sequence and takes the next
    # message_sequence (3) — turn_sequence does NOT move for it.
    assistant = AssistantTurnRecord(
        assistant_turn_id=AssistantTurnId("at-1"),
        turn_id=turn1.turn_id,
        conversation_id=CONV,
        turn_sequence=turn1.turn_sequence,
        message_sequence=MessageSequence(0),  # store-allocated; input ignored
        action_id=ActionId("act-1"),
        content="Hello!",
        delivery_state=DeliveryState.SENT_COMPLETE,
        delivery_certainty="SERVER_SENT_UNCONFIRMED",
    )
    canonical = store.canonicalize_assistant_turn(assistant)
    assert isinstance(canonical, Ok)

    row = store._conn.execute(  # noqa: SLF001 — test-side read
        "SELECT turn_sequence, message_sequence FROM assistant_turn"
        " WHERE assistant_turn_id = ?",
        ("at-1",),
    ).fetchone()
    assert row == (1, 3)

    positions = store.get_sequence_positions(CONV)
    assert isinstance(positions, Ok)
    assert positions.value.next_turn_sequence == TurnSequence(3)
    assert positions.value.next_message_sequence == MessageSequence(4)

    # Third coordination turn: turn 3, message 4 — the two counters moved
    # independently (turn moved twice for 3 turns; message moved once more
    # for the assistant entry).
    turn3 = commit_ok(store, CONV, "cm-3", "third")
    assert (turn3.turn_sequence, turn3.message_sequence) == (3, 4)


def test_turn_record_events_occupy_no_message_sequence(
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """VAL ③ negative: coordination-only events (TurnRecord CAS transitions;
    in Phase 2+, DecisionCycle work) allocate no message_sequence — only
    UserTurn/AssistantTurn rows do (DATA_MODEL §3: DecisionCycle 不占
    message sequence)."""
    turn = commit_ok(store, CONV, "cm-1", "only turn")
    before = store.get_sequence_positions(CONV)
    assert isinstance(before, Ok)

    advanced = store.transition_turn(turn.turn_id, 1, TurnStatus.ANALYZING)
    assert isinstance(advanced, Ok)
    after = store.get_sequence_positions(CONV)

    assert isinstance(after, Ok)
    assert after.value == before.value


def store_count(db: sqlite3.Connection, table: str) -> int:
    """Full-literal row counters (no identifier assembly)."""
    sql = {
        "user_turn": "SELECT COUNT(*) FROM user_turn",
        "turn_record": "SELECT COUNT(*) FROM turn_record",
        "input_envelope": "SELECT COUNT(*) FROM input_envelope",
    }[table]
    row = db.execute(sql).fetchone()
    assert row is not None
    return int(row[0])
