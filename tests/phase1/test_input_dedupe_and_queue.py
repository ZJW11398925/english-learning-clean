"""VAL ① + ⑤ — input dedupe idempotency and guard-external durability.

VAL ①: 重复 client_message_id 的 InputEnvelope 重投不产生第二个
UserTurn/TurnRecord（幂等）。
VAL ⑤: InterruptRequest/新 InputEnvelope 可在 coordinator guard 外 durable
(docs/RUNTIME_ARCHITECTURE.md §17.1 rule 1, §24).
"""

from __future__ import annotations

import pytest

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.platform.sync import CoordinatorBusyError
from elc.platform.types import ConversationId, Ok
from elc.runtime import ConversationCoordinatorLease
from elc.runtime.types import InterruptRequest
from tests.phase1.conftest import (
    CONV,
    commit_ok,
    make_envelope,
)


def test_duplicate_client_message_id_returns_original_input(
    store: SqliteConversationStore, conversation: ConversationId
) -> None:
    """VAL ① (envelope face): the replayed envelope returns the durable
    original and no second row appears (DATA_MODEL §4 Unique)."""
    first = store.ingest_input(make_envelope(CONV, "cm-dup", input_id="in-first"))
    replay = store.ingest_input(make_envelope(CONV, "cm-dup", input_id="in-second"))

    assert isinstance(first, Ok)
    assert isinstance(replay, Ok)
    assert replay.value.input_id == first.value.input_id
    count = store_count(store, "input_envelope")
    assert count == 1


def test_duplicate_client_message_id_yields_single_turn(
    store: SqliteConversationStore, conversation: ConversationId
) -> None:
    """VAL ① (CP0 face): re-committing the same client_message_id — even
    with a fresh input_id — replays the original commit and creates no
    second UserTurn/TurnRecord."""
    command = CommitUserTurn(
        conversation_id=CONV,
        envelope=make_envelope(CONV, "cm-once", input_id="in-a"),
        raw_content="hello",
        runtime_version="runtime-v1",
    )
    first = store.commit_user_turn(command)
    assert isinstance(first, Ok)

    replay_command = CommitUserTurn(
        conversation_id=CONV,
        envelope=make_envelope(CONV, "cm-once", input_id="in-b"),
        raw_content="hello",
        runtime_version="runtime-v1",
    )
    replay = store.commit_user_turn(replay_command)

    assert isinstance(replay, Ok)
    assert replay.value == first.value
    assert store_count(store, "user_turn") == 1
    assert store_count(store, "turn_record") == 1
    assert store_count(store, "input_envelope") == 1


def test_distinct_client_message_ids_yield_distinct_turns(
    store: SqliteConversationStore, conversation: ConversationId
) -> None:
    """VAL ① control: genuinely new inputs must still commit (dedupe must
    not swallow fresh work)."""
    first = commit_ok(store, CONV, "cm-1", "first")
    second = commit_ok(store, CONV, "cm-2", "second")

    assert first.turn_id != second.turn_id
    assert second.turn_sequence > first.turn_sequence
    assert second.message_sequence > first.message_sequence
    assert store_count(store, "user_turn") == 2
    assert store_count(store, "turn_record") == 2


def test_input_and_interrupt_durable_outside_coordinator_guard(
    store: SqliteConversationStore,
    conversation: ConversationId,
    lease: ConversationCoordinatorLease,
) -> None:
    """VAL ⑤: with the guard held, a new InputEnvelope and an
    InterruptRequest both become durable — the guard never blocks the input
    queue (RUNTIME §17.1 rule 1/2; §24)."""
    committed = commit_ok(store, CONV, "cm-active", "active turn input")

    with lease.hold(CONV):
        assert lease.is_held(CONV)

        ingested = store.ingest_input(make_envelope(CONV, "cm-queued"))
        assert isinstance(ingested, Ok)

        interrupt = InterruptRequest(
            input_id=ingested.value.input_id,
            conversation_id=str(CONV),
            active_turn_id=committed.turn_id,
            active_action_id=None,
            reason="user barge-in",
        )
        requested = store.request_interrupt(interrupt)
        assert isinstance(requested, Ok)

        # Both rows are durable while the old coordinator still holds the
        # guard.
        assert store_count(store, "input_envelope") == 2
        queued = store._conn.execute(  # noqa: SLF001 — test-side read
            "SELECT active_turn_id, reason FROM interrupt_request"
        ).fetchone()
        assert queued is not None
        assert queued[0] == committed.turn_id
        assert queued[1] == "user barge-in"

    # The guard is a real single-owner guard (STATE_MACHINES §17): a second
    # non-blocking holder is refused.
    with lease.hold(CONV):
        with pytest.raises(CoordinatorBusyError):
            with lease.hold(CONV, blocking=False):
                pass


_COUNT_SQL = {
    "conversation": "SELECT COUNT(*) FROM conversation",
    "input_envelope": "SELECT COUNT(*) FROM input_envelope",
    "user_turn": "SELECT COUNT(*) FROM user_turn",
    "assistant_turn": "SELECT COUNT(*) FROM assistant_turn",
    "turn_record": "SELECT COUNT(*) FROM turn_record",
    "interrupt_request": "SELECT COUNT(*) FROM interrupt_request",
}


def store_count(store: SqliteConversationStore, table: str) -> int:
    """Test-side row counter (tests may run SQL; every statement here is a
    full literal — the Mimosa rule allows no identifier assembly)."""
    row = store._conn.execute(_COUNT_SQL[table]).fetchone()  # noqa: SLF001
    assert row is not None
    return int(row[0])
