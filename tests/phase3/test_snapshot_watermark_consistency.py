"""VAL ① — snapshot watermark consistency at read time (P3-0 ①,
DEC-…eaaa5a1d.48 F1 disposition).

The review counterexample, pinned: a commit that advances the durable
watermark N → N+1 without a rebuild must NEVER produce a snapshot whose
top-level evidence_watermark=N+1 rides targets computed at <=N. The read
deterministically refuses (CONFLICT) instead; a rebuild clears the
refusal and the snapshot is consistent again.
"""

from __future__ import annotations

from elc.learning.store import SqliteLearningStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, Ok, TargetId
from tests.phase2.conftest import commit_ok, make_claim, make_group


def _commit(
    learning: SqliteLearningStore,
    store,
    conversation,
    client_message_id: str,
    group_id: str,
    target_id: str = "res-p3",
):
    cp0 = commit_ok(store, conversation, client_message_id, "utterance")
    group = make_group(group_id, (make_claim(),), target_id=target_id)
    result = learning.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Ok), result
    return result.value


def test_snapshot_refuses_stale_projection_after_watermark_advance(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    """The counterexample: commit (wm 1) → rebuild → commit again
    (wm 2, no rebuild) → the snapshot read refuses instead of returning
    watermark=2 over targets stamped 1; rebuild → the read is consistent."""

    target = TargetId("res-p3")
    _commit(learning, store, conversation, "cm-p3-a", "eg-p3-a")
    assert learning.get_evidence_watermark() == 1
    assert isinstance(learning.rebuild_learner_state(target,
                                                     "TEXT_PRODUCTION"), Ok)

    # Second durable evidence change: watermark 1 → 2, projection NOT
    # rebuilt (the exact stale-projection window F1 flagged).
    _commit(learning, store, conversation, "cm-p3-b", "eg-p3-b")
    assert learning.get_evidence_watermark() == 2

    refused = learning.get_learning_snapshot()
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"
    message = refused.error.message
    assert "stale" in message
    assert "evidence_watermark=1" in message  # the row's lagging stamp
    assert "durable watermark is 2" in message
    assert "rebuild_learner_state" in message
    # Deterministic refusal: the same stale state refuses identically.
    again = learning.get_learning_snapshot()
    assert isinstance(again, Err)
    assert again.error.message == message

    # The projection read itself is unaffected (the row is readable; it
    # is the SNAPSHOT view that refuses to lie about the watermark).
    state = learning.get_learner_target_state(target, "TEXT_PRODUCTION")
    assert isinstance(state, Ok) and state.value is not None
    assert state.value.evidence_watermark == 1

    # Rebuild re-stamps: the refusal clears and the snapshot is
    # internally consistent (top watermark == every target stamp).
    assert isinstance(learning.rebuild_learner_state(target,
                                                     "TEXT_PRODUCTION"), Ok)
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)
    assert snapshot.value.evidence_watermark == 2
    assert len(snapshot.value.targets) == 1
    assert all(
        record.evidence_watermark == snapshot.value.evidence_watermark
        for record in snapshot.value.targets
    )


def test_snapshot_refusal_covers_a_not_yet_rebuilt_second_target(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    """Mixed freshness: target A rebuilt at wm 1, target B committed at
    wm 2 without a rebuild — the snapshot refuses on B's lagging row."""

    _commit(learning, store, conversation, "cm-p3-x", "eg-p3-x", "res-x")
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-x"), "TEXT_PRODUCTION"),
        Ok,
    )
    _commit(learning, store, conversation, "cm-p3-y", "eg-p3-y", "res-y")

    refused = learning.get_learning_snapshot()
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"
    # Both rows now lag wm 2; the deterministic first stale row (§11 key
    # order: target_type, target_id, modality) is named in the refusal.
    assert "res-x" in refused.error.message

    # Global consistency: EVERY lagging row must be rebuilt — res-x was
    # rebuilt at wm 1 and is stale at wm 2 too; after both rebuilds the
    # read clears.
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-x"), "TEXT_PRODUCTION"),
        Ok,
    )
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-y"), "TEXT_PRODUCTION"),
        Ok,
    )
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)
    assert snapshot.value.evidence_watermark == 2
    assert [str(record.target_id) for record in snapshot.value.targets] == [
        "res-x",
        "res-y",
    ]


def test_empty_projection_snapshot_still_reads_ok_after_commit(
    learning: SqliteLearningStore,
    store,
    conversation,
    fence: RuntimeEpochFence,
) -> None:
    """No §11 rows → nothing can be stale: the zero-target snapshot keeps
    reading Ok with the current watermark (the P2B zero-claim semantics,
    unchanged by the read-time gate)."""

    del fence  # same-epoch store; the gate under test is the read check
    _commit(learning, store, conversation, "cm-p3-none", "eg-p3-none",
            "res-none")
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)
    assert snapshot.value.targets == ()
    assert snapshot.value.evidence_watermark == 1
