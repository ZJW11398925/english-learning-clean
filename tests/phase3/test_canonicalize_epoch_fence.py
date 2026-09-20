"""VAL ⑤ — canonicalize_assistant_turn is epoch-fenced (P3-0 ⑤,
DEC-…d7937fd7.19 F4 disposition after two deferrals).

Pins (transition_turn / terminalize_turn paradigm):
- a store whose adopted epoch is no longer the newest runtime epoch is
  fenced BEFORE anything writes: canonicalization raises the
  StaleEpochError family and the transcript stays unpolluted;
- a current-epoch store cannot canonicalize a turn owned by an older
  epoch without claiming it first (AUTHORITY_VIOLATION); after
  claim_turn_for_recovery the canonicalization succeeds exactly once.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import AssistantTurnRecord, SqliteConversationStore
from elc.conversation.types import DeliveryState
from elc.platform.db import epoch
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ConversationId,
    Err,
    MessageSequence,
    Ok,
    TurnSequence,
)
from tests.phase1.conftest import commit_ok


def make_assistant(
    turn_id: object, assistant_turn_id: str, content: str
) -> AssistantTurnRecord:
    return AssistantTurnRecord(
        assistant_turn_id=AssistantTurnId(assistant_turn_id),
        turn_id=turn_id,  # type: ignore[arg-type]
        conversation_id=ConversationId("conv-fence"),
        turn_sequence=TurnSequence(0),
        message_sequence=MessageSequence(0),
        action_id=ActionId(f"act-{assistant_turn_id}"),
        content=content,
        delivery_state=DeliveryState.SENT_COMPLETE,
        delivery_certainty="SERVER_SENT_UNCONFIRMED",
    )


def _transcript_state(
    db: sqlite3.Connection, conversation: ConversationId
) -> tuple[int, int]:
    assistants = db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()
    sequence = db.execute(
        "SELECT next_message_sequence FROM conversation"
        " WHERE conversation_id = ?",
        (str(conversation),),
    ).fetchone()
    assert assistants is not None and sequence is not None
    return int(assistants[0]), int(sequence[0])


def test_stale_epoch_canonicalize_is_refused_and_transcript_unpolluted(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """The DEC.19 F4 counterexample: after a new epoch opens, the old
    epoch's canonicalization raises the StaleEpochError family and no
    assistant content, no sequence bump, no residue lands."""

    turn = commit_ok(store, conversation, "cm-fence-1", "old epoch question")
    before = _transcript_state(db, conversation)

    epoch.open_runtime_epoch(db)  # a newer runtime epoch now exists

    with pytest.raises(StaleEpochError):
        store.canonicalize_assistant_turn(
            make_assistant(turn.turn_id, "at-stale", "stale epoch draft")
        )

    # The fenced unit left nothing behind (rollback + nothing written).
    assert _transcript_state(db, conversation) == before
    assert db.execute(
        "SELECT COUNT(*) FROM assistant_turn WHERE turn_id = ?",
        (turn.turn_id,),
    ).fetchone()[0] == 0
    assert not db.in_transaction


def test_owner_epoch_mismatch_is_authority_violation_until_claimed(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """Paradigm parity with transition_turn / terminalize_turn: a
    current-epoch store refuses to canonicalize an old-epoch turn
    (AUTHORITY_VIOLATION); the recovery claim adopts the turn, and the
    canonicalization then succeeds exactly once."""

    turn = commit_ok(store, conversation, "cm-fence-2", "crash after CP0")
    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)

    refused = new_store.canonicalize_assistant_turn(
        make_assistant(turn.turn_id, "at-claim", "recovered reply")
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "AUTHORITY_VIOLATION"
    assert "owner_epoch=" in refused.error.message
    assert "fenced by" in refused.error.message
    assert _transcript_state(db, conversation)[0] == 0

    claimed = new_store.claim_turn_for_recovery(turn.turn_id)
    assert isinstance(claimed, Ok)

    canonical = new_store.canonicalize_assistant_turn(
        make_assistant(turn.turn_id, "at-claim", "recovered reply")
    )
    assert isinstance(canonical, Ok)

    # Idempotent replay through the owning epoch returns the same turn.
    replay = new_store.canonicalize_assistant_turn(
        make_assistant(turn.turn_id, "at-claim-dup", "recovered reply")
    )
    assert isinstance(replay, Ok)
    assert replay.value == canonical.value
    assert _transcript_state(db, conversation)[0] == 1


def test_current_epoch_canonicalization_is_unchanged(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation: ConversationId,
) -> None:
    """Regression: the same-epoch normal path (no newer epoch, owner is
    current) canonicalizes exactly as before the fence landed."""

    turn = commit_ok(store, conversation, "cm-fence-3", "normal path")
    result = store.canonicalize_assistant_turn(
        make_assistant(turn.turn_id, "at-normal", "normal reply")
    )
    assert isinstance(result, Ok)
    assert _transcript_state(db, conversation)[0] == 1
    # The fence itself is inert on reads.
    assert RuntimeEpochFence(current=store.current_epoch).is_stale(
        store.current_epoch
    ) is False
