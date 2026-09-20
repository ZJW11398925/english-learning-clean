"""VAL ③ — CP1: validation + commit in one short transaction, then the
durable watermark advances monotonically (RA §6 CP1 / §4 step 4).

Failure injection proves atomicity: a fault raised mid-unit leaves no
group / claim / commit / watermark residue (no half-committed window).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import elc.learning.store as learning_store_module
from elc.learning.store import SqliteLearningStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, Ok
from tests.phase2.conftest import (
    canonical_slice,
    commit_ok,
    make_claim,
    make_group,
)


def test_cp1_commits_group_claims_and_watermark_atomically(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-1", "I definitely know this word")
    claim = make_claim()
    result = learning.commit_evidence_group(
        make_group("eg-1", (claim,)),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Ok), result

    group_row = db.execute(
        "SELECT evidence_group_id, source_turn_id FROM evidence_group"
    ).fetchone()
    assert group_row[0] == "eg-1"
    assert group_row[1] == cp0.turn_id
    claim_row = db.execute(
        "SELECT target_type, target_id, performance_type, polarity,"
        " outcome, qualifiers, status FROM evidence_claim"
    ).fetchone()
    assert claim_row[0] == "RESOURCE"
    assert claim_row[1] == "res-1"
    assert claim_row[6] == "ACTIVE"
    assert learning.get_evidence_watermark() == 1
    commit_row = db.execute(
        "SELECT evidence_commit_id, evidence_group_id, watermark_after"
        " FROM evidence_commit"
    ).fetchone()
    assert commit_row[1] == "eg-1"
    assert commit_row[2] == 1


def test_watermark_monotonic_across_commits(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    assert learning.get_evidence_watermark() == 0
    watermarks = []
    for index in range(4):
        cp0 = commit_ok(store, conversation, f"cm-{index}", f"turn {index}")
        slice_ = canonical_slice(store, cp0)
        artifact = learning.record_learning_analysis(slice_)
        assert isinstance(artifact, Ok), artifact
        commit = learning.commit_learning_evidence(
            artifact.value, slice_, "persona-default"
        )
        assert isinstance(commit, Ok), commit
        watermarks.append(learning.get_evidence_watermark())
    assert watermarks == [1, 2, 3, 4]
    # The watermark is durable per scope and survives store re-binding.
    rebound = SqliteLearningStore(db, fence)
    assert rebound.get_evidence_watermark() == 4


def test_cp1_mid_transaction_failure_leaves_no_residue(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject a fault after the group INSERT but before the claim
    INSERTs: the whole unit rolls back (no group, no claim, no commit,
    no watermark move)."""

    cp0 = commit_ok(store, conversation, "cm-fail", "some utterance")
    original = SqliteLearningStore._insert_claim

    def exploding(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("injected mid-unit failure")

    monkeypatch.setattr(SqliteLearningStore, "_insert_claim", exploding)
    with pytest.raises(RuntimeError):
        learning.commit_evidence_group(
            make_group("eg-fail", (make_claim(),)),
            source_turn_id=cp0.turn_id,
            conversation_id=str(conversation),
        )
    monkeypatch.setattr(
        SqliteLearningStore, "_insert_claim", original
    )

    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_commit").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == 0
    assert not db.in_transaction


def test_stale_epoch_fences_cp1_writes(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    from elc.learning.store import StaleStoreEpochError
    from elc.platform.db import epoch as epoch_module

    cp0 = commit_ok(store, conversation, "cm-stale", "text")
    # A restart opens a newer epoch; the old store's fence is now stale
    # (P1 convention: the fence raises — the write never lands).
    epoch_module.open_runtime_epoch(db)
    with pytest.raises(StaleStoreEpochError):
        learning.commit_evidence_group(
            make_group("eg-stale", (make_claim(),)),
            source_turn_id=cp0.turn_id,
            conversation_id=str(conversation),
        )
    assert learning.get_evidence_watermark() == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
    assert not db.in_transaction
    # The module docstring names the fence discipline; keep the store
    # wired to the shared StaleEpochError hierarchy.
    assert issubclass(StaleStoreEpochError, learning_store_module.StaleEpochError)


def test_proposal_turn_binding_rejects_mismatched_artifact(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """An artifact whose utterance hash no longer matches the canonical
    turn never commits (artifact/turn binding)."""
    from elc.learning.analysis import LearningEvidenceProposal
    from elc.platform.types import AnalysisId

    cp0 = commit_ok(store, conversation, "cm-bind", "original text")
    slice_ = canonical_slice(store, cp0)
    artifact = learning.record_learning_analysis(slice_)
    assert isinstance(artifact, Ok), artifact

    tampered_payload = json.dumps(
        {
            "analysis_type": "LEARNING_EVIDENCE",
            "evidence_modality": "TEXT_PRODUCTION",
            "observable": True,
            "utterance_length": 99,
            "utterance_sha256": "0" * 64,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    tampered = LearningEvidenceProposal(
        analysis_id=AnalysisId(artifact.value.analysis_id),
        turn_id=artifact.value.turn_id,
        producer_id=artifact.value.producer_id,
        producer_version=artifact.value.producer_version,
        structured_proposal=tampered_payload,
        confidence=1.0,
    )
    result = learning.commit_learning_evidence(
        tampered, slice_, "persona-default"
    )
    assert isinstance(result, Err)
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == 0
    status = db.execute(
        "SELECT status FROM analysis_artifact WHERE analysis_id = ?",
        (artifact.value.analysis_id,),
    ).fetchone()[0]
    assert status == "PRODUCED"  # REJECTED is for unobservable proposals
