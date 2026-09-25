"""P10-4 交付 C —— D1 fence 修复的新钉：三个 coordination unit 现在同保。

背景（裁决 `DEC-OPI-8f27d1de-…9`）：`canonicalize_assistant_turn` 一直带**双箍** ——
写事务内先 `_require_current_epoch()`（重读 `MAX(epoch) FROM runtime_epoch`，本实例
自持 epoch 必须仍是全库最新）再查 ownership（行属于本 epoch）；而
`transition_turn` / `terminalize_turn` 只有 ownership 箍。p10-2 按 as-found 把这一
缺口钉在 `tests/phase10/test_p10_2_failure_scenarios_b.py` 的
`epoch-race-turn-canonicalize` 类里并挂了 Revisit；本刀按该 Revisit 给两个 unit 在
**写事务内、首次读行之前**各加一行 store 级检查（与
`conversation/store.py` 的 `canonicalize_assistant_turn` 同位同形），并把那条 as-found
臂改写为拒绝形态（**在 p10-2 文件内改，本文件不重复**）。

本文件的五组（§4 (i)–(v)）：

(i) **三 unit 同被拒**：陈旧 store 在自己的 turn 上调用
    `canonicalize_assistant_turn` / `transition_turn` / `terminalize_turn`，三者皆
    `raise StaleEpochError`、**零写入**、`db.in_transaction is False`（fence 抛在
    `short_transaction` 内 ⇒ 回滚不留打开事务，`platform/db/tx.py:28-41`）；
(ii) **正控**：current-epoch store 的同一三 unit 皆成（同一世界的正面半边）；
(iii) **桥接**：`claim_turn_for_recovery` 之后，新 epoch 的三 unit 皆成 —— 证修复**不
    阻碍恢复路径**（恢复纪律是「先 claim 再动」：`_close_residual_turns` 在
    `record.owner_epoch != epoch` 时先 claim，controller.py:4340-4346）；
(iv) **跨连接**：第二条连接 `epoch.open_runtime_epoch` 开新 epoch 后，第一条连接的
    旧 store 三 unit 皆拒 —— fence 读的是**全库**最新 epoch，不是本实例的记忆；
(v) **错误码矩阵四格**（口径钉）：(current×own) ⇒ `Ok`；(current×foreign) ⇒
    `AUTHORITY_VIOLATION`（**不变**）；(stale×own) ⇒ `StaleEpochError`（新）；
    (stale×foreign) ⇒ 从 `AUTHORITY_VIOLATION` **变为** `StaleEpochError`（fence 在
    ownership 之前）—— 两格拒绝的结论都不放松，只是理由码更早、更准。

纪律：真库真面（真 store / 真 `user_turn` / 真 `turn_record`），零 `_seed()` 零
fixture 供给，外壳零处（本文件不需要外壳）；构造走 A 半的 `_commit_chat_turn`
（同一世界构造，导入复用而非重写）。零迁移；未触碰 `migrations/`、`docs/`、
`behavioral_baselines/`、`tests/architecture/`、`tests/conftest.py`、`registry.py`、
`tests/phase9/`；**未改 A 半文件**。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.conversation import AssistantTurnRecord, SqliteConversationStore
from elc.conversation.types import DeliveryState, TurnOutcome
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import StaleEpochError
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ConversationId,
    DomainErrorCode,
    Err,
    MessageSequence,
    Ok,
    TurnId,
    TurnSequence,
    UserId,
)
from elc.runtime.types import TurnStatus
from tests.phase3.conftest import CONV
from tests.phase10.test_p10_1_failure_scenarios_a import _commit_chat_turn


def _assistant_record(
    db: sqlite3.Connection, turn_id: str, content: str
) -> AssistantTurnRecord:
    """One transcript row candidate for a durable turn, with the turn's own
    sequences (the phase-3 fence test's ``make_assistant`` shape, read off the
    ``user_turn`` row instead of hand-built)."""

    row = db.execute(
        "SELECT conversation_id, turn_sequence, message_sequence"
        " FROM user_turn WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert row is not None, f"no user_turn row: {turn_id}"
    return AssistantTurnRecord(
        assistant_turn_id=AssistantTurnId(f"at-{turn_id}"),
        turn_id=TurnId(turn_id),
        conversation_id=ConversationId(str(row[0])),
        turn_sequence=TurnSequence(int(row[1])),
        message_sequence=MessageSequence(int(row[2])),
        action_id=ActionId(f"act-{turn_id}"),
        content=content,
        delivery_state=DeliveryState.SENT_COMPLETE,
        delivery_certainty="SERVER_SENT_UNCONFIRMED",
    )


def _turn_snapshot(
    db: sqlite3.Connection, turn_id: str
) -> tuple[str, str | None, int, int]:
    """(status, outcome, owner_epoch, state_version) as the durable row has it."""

    row = db.execute(
        "SELECT status, turn_outcome, owner_epoch, state_version FROM turn_record"
        " WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert row is not None, f"no turn_record row: {turn_id}"
    return (
        str(row[0]),
        None if row[1] is None else str(row[1]),
        int(row[2]),
        int(row[3]),
    )


def _counts(db: sqlite3.Connection, *tables: str) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


# (i) the three units, all refused on a stale store ---------------------------


def test_all_three_units_refuse_a_stale_store_before_anything_writes(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """(i) 一个陈旧 store（本实例 epoch=1，而全库最新 epoch=2）在**自己的** turn 上
    调用三个 unit：三者皆 `StaleEpochError`，`turn_record`/transcript 逐字不动，
    事务不留在打开状态。

    这是修复的直接产物：修复前 `transition_turn` / `terminalize_turn` 只比 row 的
    `owner_epoch` 与 store 自持 epoch —— 两者都等于 1 ⇒ 它们会**照写**（陈旧进程改写
    协调状态）。三者各自的断言分开写，避免「一个 unit 抛了就算」的合并掩盖。
    """

    del conversation  # requested for its side effect (the conversation row)
    turn_id = _commit_chat_turn(store, "cm-p10-4-d1-three")
    before = _turn_snapshot(db, turn_id)
    counted_before = _counts(db, "assistant_turn", "user_turn", "turn_record")

    epoch.open_runtime_epoch(db)  # the store in hand is stale from here on

    with pytest.raises(StaleEpochError):
        store.canonicalize_assistant_turn(
            _assistant_record(db, turn_id, "stale draft")
        )
    with pytest.raises(StaleEpochError):
        store.transition_turn(TurnId(turn_id), before[3], TurnStatus.GENERATING)
    with pytest.raises(StaleEpochError):
        store.terminalize_turn(TurnId(turn_id), TurnOutcome.REPLIED_FULL)

    assert db.in_transaction is False
    assert _turn_snapshot(db, turn_id) == before
    assert _counts(db, "assistant_turn", "user_turn", "turn_record") == counted_before


# (ii) the positive control ---------------------------------------------------


def test_the_current_epoch_store_runs_the_same_three_units(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """(ii) 正控：同一世界、同一 epoch 的 store，三个 unit 皆成 —— 修复不是把这三个
    unit 变成一律拒绝，只在「本实例不再是全库最新」时拦。"""

    del conversation
    turn_id = _commit_chat_turn(store, "cm-p10-4-d1-current")

    canonical = store.canonicalize_assistant_turn(
        _assistant_record(db, turn_id, "the reply")
    )
    assert isinstance(canonical, Ok), canonical
    advanced = store.transition_turn(
        TurnId(turn_id), _turn_snapshot(db, turn_id)[3], TurnStatus.GENERATING
    )
    assert isinstance(advanced, Ok), advanced
    terminal = store.terminalize_turn(TurnId(turn_id), TurnOutcome.REPLIED_FULL)
    assert isinstance(terminal, Ok), terminal

    assert _turn_snapshot(db, turn_id)[:2] == ("COMPLETED", "REPLIED_FULL")
    assert _counts(db, "assistant_turn") == {"assistant_turn": 1}
    assert db.in_transaction is False


# (iii) the recovery bridge ---------------------------------------------------


def test_the_new_epoch_reaches_the_same_three_units_after_claiming(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """(iii) 桥接：陈旧 turn 的正规出口是**先 claim 再动**。新 epoch 的 store
    `claim_turn_for_recovery`（owner_epoch → 新 epoch）之后，三个 unit 依次皆成 ——
    修复不阻碍恢复路径；且**未 claim 之前**新 store 也拒（ownership 箍，独立于本刀）。
    """

    del conversation
    turn_id = _commit_chat_turn(store, "cm-p10-4-d1-bridge")
    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)

    # before the claim, the new epoch's store owns nothing here its own
    refused = new_store.transition_turn(
        TurnId(turn_id), _turn_snapshot(db, turn_id)[3], TurnStatus.GENERATING
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.AUTHORITY_VIOLATION

    claimed = new_store.claim_turn_for_recovery(TurnId(turn_id))
    assert isinstance(claimed, Ok), claimed
    assert int(claimed.value.owner_epoch) == new_fence.current

    canonical = new_store.canonicalize_assistant_turn(
        _assistant_record(db, turn_id, "the recovered reply")
    )
    assert isinstance(canonical, Ok), canonical
    advanced = new_store.transition_turn(
        TurnId(turn_id), _turn_snapshot(db, turn_id)[3], TurnStatus.GENERATING
    )
    assert isinstance(advanced, Ok), advanced
    terminal = new_store.terminalize_turn(TurnId(turn_id), TurnOutcome.REPLIED_FULL)
    assert isinstance(terminal, Ok), terminal
    assert _turn_snapshot(db, turn_id)[:2] == ("COMPLETED", "REPLIED_FULL")


# (iv) across two connections -------------------------------------------------


def test_a_second_connection_opening_an_epoch_fences_the_first_connections_store(
    tmp_path: Path,
) -> None:
    """(iv) 跨连接：文件库上开第二条连接并 `open_runtime_epoch`，第一条连接的
    current store 立刻陈旧（fence 读的是全库 `MAX(epoch)`）⇒ 三 unit 皆拒、零写入。

    这条是 §24「Local V1 不以 expiry 猜 owner 已死，而由新 `runtime_epoch` 对旧 epoch
    nonterminal work 做恢复」的**机制**面：跨连接可见性是它的前提。"""

    path = tmp_path / "app.db"
    first = connection.connect(path)
    migrations.apply_migrations(first)
    fence = epoch.open_runtime_epoch(first)
    store = SqliteConversationStore(first, fence)
    opened = store.open_conversation(
        CONV, user_id=UserId("user-1"), persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    turn_id = _commit_chat_turn(store, "cm-p10-4-d1-cross")
    before = _turn_snapshot(first, turn_id)

    second = connection.connect(path)
    new_fence = epoch.open_runtime_epoch(second)
    assert new_fence.current != fence.current

    with pytest.raises(StaleEpochError):
        store.canonicalize_assistant_turn(_assistant_record(first, turn_id, "draft"))
    with pytest.raises(StaleEpochError):
        store.transition_turn(TurnId(turn_id), before[3], TurnStatus.GENERATING)
    with pytest.raises(StaleEpochError):
        store.terminalize_turn(TurnId(turn_id), TurnOutcome.REPLIED_FULL)

    assert first.in_transaction is False
    assert _turn_snapshot(first, turn_id) == before
    second.close()
    first.close()


# (v) the four-cell error-code matrix ----------------------------------------


def test_the_error_code_matrix_has_four_cells(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """(v) 口径钉：四格实测 —— (current×own) `Ok`；(current×foreign)
    `AUTHORITY_VIOLATION`（**不变**）；(stale×own) `StaleEpochError`（新）；
    (stale×foreign) `StaleEpochError`（**原为 `AUTHORITY_VIOLATION`**：fence 在
    ownership 之前，两格都是「拒」，只是理由码更早）。

    四格在同一个世界里都能构出：epoch 1 提交一个 turn；epoch 2 开（epoch 1 的 store
    变陈旧）；epoch 2 的 store claim 该 turn（owner → 2）⇒ 此时 epoch 1 的 store 面对
    的正是「陈旧 × 外来」，而 epoch 2 的 store 面对「当前 × 自己」。
    """

    del conversation
    turn_id = _commit_chat_turn(store, "cm-p10-4-d1-matrix")
    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)

    # (stale × own) — epoch 1's store, the turn is still its own
    with pytest.raises(StaleEpochError):
        store.transition_turn(
            TurnId(turn_id), _turn_snapshot(db, turn_id)[3], TurnStatus.GENERATING
        )

    # (current × foreign) — epoch 2's store, the turn belongs to epoch 1
    foreign = new_store.transition_turn(
        TurnId(turn_id), _turn_snapshot(db, turn_id)[3], TurnStatus.GENERATING
    )
    assert isinstance(foreign, Err), foreign
    assert foreign.error.code is DomainErrorCode.AUTHORITY_VIOLATION
    foreign_terminal = new_store.terminalize_turn(
        TurnId(turn_id), TurnOutcome.REPLIED_FULL
    )
    assert isinstance(foreign_terminal, Err), foreign_terminal
    assert foreign_terminal.error.code is DomainErrorCode.AUTHORITY_VIOLATION

    # the recovery claim flips ownership to epoch 2
    claimed = new_store.claim_turn_for_recovery(TurnId(turn_id))
    assert isinstance(claimed, Ok), claimed

    # (stale × foreign) — epoch 1's store, the turn now belongs to epoch 2:
    # refused as *stale* (the fence moved ahead of the ownership read) ...
    with pytest.raises(StaleEpochError):
        store.transition_turn(
            TurnId(turn_id), _turn_snapshot(db, turn_id)[3], TurnStatus.GENERATING
        )
    with pytest.raises(StaleEpochError):
        store.terminalize_turn(TurnId(turn_id), TurnOutcome.REPLIED_FULL)
    with pytest.raises(StaleEpochError):
        store.canonicalize_assistant_turn(
            _assistant_record(db, turn_id, "stale after the claim")
        )

    # (current × own) — epoch 2's store now owns the turn: both successors land
    own_version = _turn_snapshot(db, turn_id)[3]
    advanced = new_store.transition_turn(
        TurnId(turn_id), own_version, TurnStatus.GENERATING
    )
    assert isinstance(advanced, Ok), advanced
    terminal = new_store.terminalize_turn(TurnId(turn_id), TurnOutcome.REPLIED_FULL)
    assert isinstance(terminal, Ok), terminal
    assert _turn_snapshot(db, turn_id)[:2] == ("COMPLETED", "REPLIED_FULL")

    # ... and neither refused call left a transaction open
    assert db.in_transaction is False
