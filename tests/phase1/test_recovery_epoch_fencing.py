"""VAL ④ — crash-after-CP0 recovery under runtime_epoch fencing.

VAL ④: crash-after-CP0 后新 runtime_epoch 启动恢复将旧 epoch 的 nonterminal
TurnRecord 识别为可恢复且不重放已提交 UserTurn
(docs/RUNTIME_ARCHITECTURE.md §22/§23/§24/§24.1).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import TurnOutcome
from elc.platform.db import epoch
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.types import ConversationId, Err, Ok, RuntimeEpoch
from elc.runtime import (
    ConversationCoordinatorLease,
    StartupRecoveryScanner,
    TurnRecordRecoverySource,
)
from tests.phase1.conftest import CONV, commit_ok


def _scanner_for(
    store: SqliteConversationStore, current: RuntimeEpoch
) -> StartupRecoveryScanner:
    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(current)
    return StartupRecoveryScanner(store, lease)


def _store_on(db: sqlite3.Connection, current: RuntimeEpoch) -> SqliteConversationStore:
    return SqliteConversationStore(db, RuntimeEpochFence(current=current))


def test_crash_after_cp0_is_identified_and_not_replayed(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """VAL ④: the new epoch's startup scan identifies the old-epoch
    USER_COMMITTED TurnRecord as recoverable work (RESUME_ANALYSIS), and the
    committed UserTurn is neither replayed nor altered — repeated scans are
    idempotent (RUNTIME §22: 不重跑整个 user turn; §23 Crash after CP0)."""
    committed = commit_ok(store, CONV, "cm-crash", "committed before the crash")

    # The process "crashes" and restarts: a NEW runtime epoch opens.
    fence2 = epoch.open_runtime_epoch(db)
    scanner = _scanner_for(store, fence2.current)

    plan = scanner.scan()
    assert isinstance(plan, Ok)
    assert len(plan.value) == 1
    action = plan.value[0]
    assert action.kind == "TURN"
    assert action.id == committed.turn_id
    assert action.action == "RESUME_ANALYSIS"  # §24.1: CP0 → RESUME_ANALYSIS

    # 已提交 UserTurn 不重放：rows and allocated sequences are untouched.
    assert _count(db, "user_turn") == 1
    assert _count(db, "turn_record") == 1
    user_row = db.execute(
        "SELECT turn_sequence, message_sequence FROM user_turn"
        " WHERE input_id = ?",
        (committed.input_id,),
    ).fetchone()
    assert user_row == (1, 1)
    status_row = db.execute(
        "SELECT status FROM turn_record WHERE turn_id = ?",
        (committed.turn_id,),
    ).fetchone()
    assert status_row == ("USER_COMMITTED",)

    # Idempotent: rescanning yields the identical plan.
    again = scanner.scan()
    assert isinstance(again, Ok)
    assert again.value == plan.value


def test_current_epoch_work_is_not_in_the_plan(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """Only old-epoch nonterminal work is recoverable; the new epoch's own
    committed turns are owned by the live coordinator (RUNTIME §24)."""
    old_turn = commit_ok(store, CONV, "cm-old", "old epoch turn")

    fence2 = epoch.open_runtime_epoch(db)
    scanner = _scanner_for(store, fence2.current)
    new_store = _store_on(db, fence2.current)

    new_turn = commit_ok(new_store, CONV, "cm-new", "new epoch turn")
    plan = scanner.scan()

    assert isinstance(plan, Ok)
    assert [action.id for action in plan.value] == [old_turn.turn_id]
    assert all(action.id != new_turn.turn_id for action in plan.value)


def test_terminal_old_epoch_turn_is_excluded(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """Recovery 扫描非 terminal (RUNTIME §22): a turn that reached a
    terminal coordination state before the crash is not recovery work."""
    finished = commit_ok(store, CONV, "cm-done", "finished before crash")
    pending = commit_ok(store, CONV, "cm-pending", "still nonterminal")

    terminal = store.terminalize_turn(finished.turn_id, TurnOutcome.REPLIED_FULL)
    assert isinstance(terminal, Ok)

    fence2 = epoch.open_runtime_epoch(db)
    plan = _scanner_for(store, fence2.current).scan()

    assert isinstance(plan, Ok)
    assert [action.id for action in plan.value] == [pending.turn_id]


def test_scan_requires_adopted_startup_fence(
    store: SqliteConversationStore, conversation: ConversationId
) -> None:
    """The scan is epoch-scoped: without an adopted runtime_epoch it refuses
    to run rather than guessing ownership (RUNTIME §24)."""
    commit_ok(store, CONV, "cm-1", "turn")
    un_fenced_lease = ConversationCoordinatorLease()
    plan = StartupRecoveryScanner(store, un_fenced_lease).scan()

    assert isinstance(plan, Err)
    assert plan.error.code.value == "DEPENDENCY_UNAVAILABLE"


def test_stale_epoch_store_is_fenced(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """DATA_MODEL §19 / RUNTIME §24: writes stamped by an old epoch are
    refused once a newer epoch exists — the restart ownership boundary."""
    commit_ok(store, CONV, "cm-1", "old epoch turn")

    fence2 = epoch.open_runtime_epoch(db)
    assert store.current_epoch != fence2.current

    with pytest.raises(StaleEpochError):
        commit_ok(store, CONV, "cm-2", "must be fenced")

    # The fenced write left nothing behind.
    assert _count(db, "user_turn") == 1


def test_recovery_source_protocol_is_structural(
    store: SqliteConversationStore,
) -> None:
    """The runtime scan consumes the durable read behind a protocol; the
    conversation store satisfies it structurally (Gate item 2: runtime
    stays SQL-free)."""
    assert isinstance(store, TurnRecordRecoverySource)


def _count(db: sqlite3.Connection, table: str) -> int:
    sql = {
        "user_turn": "SELECT COUNT(*) FROM user_turn",
        "turn_record": "SELECT COUNT(*) FROM turn_record",
    }[table]
    row = db.execute(sql).fetchone()
    assert row is not None
    return int(row[0])
