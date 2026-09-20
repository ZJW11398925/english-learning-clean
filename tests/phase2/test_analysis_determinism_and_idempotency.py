"""VAL ② + ④ — the deterministic LEARNING_EVIDENCE producer and the
idempotency of repeated analysis / turn replay.

VAL ②: zero model calls, zero randomness, zero clock reads — the
producer is a pure function of the canonical turn slice; ids and the
proposal JSON are byte-stable across runs.

VAL ④: re-running analysis after a crash replays the durable artifact;
re-entering CP1 after a committed CP1 returns the original commit and
writes nothing (RA §22/§23 two crash states, at the store face; the
coordinator-level two states live in test_coordinator_integration.py).
"""

from __future__ import annotations

import sqlite3

from elc.learning.analysis import (
    DETERMINISTIC_ANALYSIS_PRODUCER_ID,
    produce_learning_evidence_proposal,
)
from elc.learning.store import SqliteLearningStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Ok
from tests.phase2.conftest import canonical_slice, commit_ok


def test_producer_is_pure_and_byte_stable(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-det", "hello deterministic")
    slice_ = canonical_slice(store, cp0)
    first = produce_learning_evidence_proposal(slice_)
    second = produce_learning_evidence_proposal(slice_)
    assert first == second
    assert first.producer_id == DETERMINISTIC_ANALYSIS_PRODUCER_ID
    assert first.producer_version == "deterministic-v1"
    assert first.confidence == 1.0
    # Canonical JSON: sorted keys, fixed separators, turn-derived only.
    assert first.structured_proposal == second.structured_proposal


def test_producer_varies_with_utterance(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0_a = commit_ok(store, conversation, "cm-a", "alpha")
    cp0_b = commit_ok(store, conversation, "cm-b", "beta")
    proposal_a = produce_learning_evidence_proposal(
        canonical_slice(store, cp0_a)
    )
    proposal_b = produce_learning_evidence_proposal(
        canonical_slice(store, cp0_b)
    )
    assert proposal_a.analysis_id != proposal_b.analysis_id
    assert (
        proposal_a.structured_proposal != proposal_b.structured_proposal
    )


def test_repeated_analysis_replays_single_artifact(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Crash-after-CP0 store-face semantics: analysis re-entry replays
    the durable PRODUCED row (unique turn/type/producer) — one row, no
    double production, same analysis_id."""
    cp0 = commit_ok(store, conversation, "cm-idem", "replay me")
    slice_ = canonical_slice(store, cp0)

    first = learning.record_learning_analysis(slice_)
    second = learning.record_learning_analysis(slice_)
    third = learning.record_learning_analysis(slice_)
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert isinstance(third, Ok)
    assert first.value == second.value == third.value

    assert (
        db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0]
        == 1
    )
    row = db.execute(
        "SELECT analysis_id, status FROM analysis_artifact"
    ).fetchone()
    assert row[0] == first.value.analysis_id
    assert row[1] == "PRODUCED"


def test_cp1_replay_returns_original_commit_and_writes_nothing(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Crash-after-CP1 store-face semantics: re-entering CP1 on a
    COMMITTED artifact returns the original EvidenceCommitId; group /
    commit / watermark all stay singletons."""
    cp0 = commit_ok(store, conversation, "cm-cp1", "commit once")
    slice_ = canonical_slice(store, cp0)

    artifact = learning.record_learning_analysis(slice_)
    assert isinstance(artifact, Ok)
    first = learning.commit_learning_evidence(
        artifact.value, slice_, "persona-default"
    )
    assert isinstance(first, Ok)
    replay = learning.commit_learning_evidence(
        artifact.value, slice_, "persona-default"
    )
    replay_again = learning.commit_learning_evidence(
        artifact.value, slice_, "persona-default"
    )
    assert isinstance(replay, Ok) and isinstance(replay_again, Ok)
    assert replay.value == first.value == replay_again.value

    assert (
        db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1
    )
    assert (
        db.execute("SELECT COUNT(*) FROM evidence_commit").fetchone()[0] == 1
    )
    assert learning.get_evidence_watermark() == 1


def test_protocol_face_group_commit_is_idempotent(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """VAL ④ (protocol face): replaying the same EvidenceGroupRecord
    returns the original EvidenceCommitId; DATA_MODEL §25 commit
    identity holds at the group level."""
    from tests.phase2.conftest import make_claim, make_group

    cp0 = commit_ok(store, conversation, "cm-proto", "protocol replay")
    group = make_group("eg-proto", (make_claim(),))
    first = learning.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    replay = learning.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(first, Ok) and isinstance(replay, Ok)
    assert replay.value == first.value
    assert (
        db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 1
    )
    assert learning.get_evidence_watermark() == 1


def test_artifact_status_moves_produced_to_committed(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-status", "status path")
    slice_ = canonical_slice(store, cp0)
    artifact = learning.record_learning_analysis(slice_)
    assert isinstance(artifact, Ok)
    assert (
        db.execute("SELECT status FROM analysis_artifact").fetchone()[0]
        == "PRODUCED"
    )
    commit = learning.commit_learning_evidence(
        artifact.value, slice_, "persona-default"
    )
    assert isinstance(commit, Ok)
    assert (
        db.execute("SELECT status FROM analysis_artifact").fetchone()[0]
        == "COMMITTED"
    )
