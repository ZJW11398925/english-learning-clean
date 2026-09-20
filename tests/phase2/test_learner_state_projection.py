"""VAL ② ③ ④ — LearnerTargetState projection, LearningSnapshot, and the
F2 watermark-semantics upgrade, through the real SqliteLearningStore.

DATA_MODEL §11: eight dimensions each estimate?/confidence/
last_relevant_evidence_at, eight coverage counts, freshness, projection
bands, meta (estimator_version / evidence_watermark / updated_at);
materialized and rebuildable ("可删后重建" — pinned by delete→rebuild).
DATA_MODEL §12: snapshot carries snapshot_id/user_scope_id/as_of/
estimator_version/evidence_watermark/targets[] and is evidence-derived
ONLY — goal importance / review due / teaching priority / exam
importance are structurally absent (§12 red line, pinned by key scan).
F2: the watermark is the durable evidence-change sequence — commit /
supersede / invalidate all advance it.
"""

from __future__ import annotations

import json
import sqlite3

from elc.learning.estimator import ESTIMATOR_PROFILE_ID
from elc.learning.store import SqliteLearningStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    Err,
    EvaluatorVersion,
    EvidenceClaimId,
    Ok,
    TargetId,
)
from tests.phase2.conftest import (
    commit_ok,
    make_claim,
    make_group,
)

#: §12 red-line fields that must never appear anywhere in the snapshot.
FORBIDDEN_SNAPSHOT_KEYS = {
    "goal_importance",
    "review_due",
    "teaching_priority",
    "exam_importance",
    "REVIEW_DUE",
    "TEACH_NOW",
    "HIGH_PRIORITY",
    "TRANSFER_NEEDED",
}


def _commit_one(
    learning: SqliteLearningStore,
    store,
    conversation,
    client_message_id: str,
    group_id: str = "eg-p2b",
    target_id: str = "res-1",
    claim=None,
):
    cp0 = commit_ok(store, conversation, client_message_id, "utterance")
    group = make_group(
        group_id,
        (claim if claim is not None else make_claim(),),
        target_id=target_id,
    )
    result = learning.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Ok), result
    return result.value


def _first_claim_id(db: sqlite3.Connection, group_id: str) -> str:
    row = db.execute(
        "SELECT evidence_claim_id FROM evidence_claim"
        " WHERE evidence_group_id = ? ORDER BY created_at",
        (group_id,),
    ).fetchone()
    return str(row[0])


# -- §11 projection shape + rebuild ----------------------------------------


def test_rebuild_projects_the_eleven_section_state(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    _commit_one(learning, store, conversation, "cm-p2b-1")
    rebuilt = learning.rebuild_learner_state(
        TargetId("res-1"), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok)
    state = learning.get_learner_target_state(
        TargetId("res-1"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is not None
    record = state.value

    # §11 scope.
    assert record.target_type == "RESOURCE"
    assert str(record.target_id) == "res-1"
    assert record.evidence_modality == "TEXT_PRODUCTION"

    # §11 dimensions: the eight, each estimate?/confidence/
    # last_relevant_evidence_at (UNKNOWN is None, never 0).
    assert set(record.dimensions) == {
        "recognition",
        "guided_production",
        "independent_production",
        "spontaneous_production",
        "transfer",
        "accuracy",
        "pragmatic_control",
        "support_dependency",
    }
    recognition = record.dimensions["recognition"]
    assert recognition.estimate == 1.0  # one RECOGNITION SUCCESS claim
    assert 0.0 < recognition.confidence <= 1.0
    assert recognition.last_relevant_evidence_at is not None
    assert record.dimensions["guided_production"].estimate is None
    assert (
        record.dimensions["support_dependency"].last_relevant_evidence_at
        is None
    )

    # §11 coverage: the eight counts.
    assert record.coverage.evidence_groups == 1
    assert record.coverage.independent_clusters == 1
    assert record.coverage.sessions == 1
    assert record.coverage.days == 1
    assert record.coverage.contexts == 1
    assert record.coverage.personas == 1
    assert record.coverage.realizations == 1
    assert record.coverage.modalities == 1

    # §11 freshness / projection / meta.
    assert record.freshness.freshness_band == "UNKNOWN"  # no strong retrieval
    # Recognition-only evidence: no production tier estimated yet, so the
    # ability band is UNKNOWN (BF-01 §24 EARLY needs a production dim).
    assert record.projection.ability_band == "UNKNOWN"
    assert "INSUFFICIENT_EVIDENCE" not in record.projection.learning_flags
    assert record.estimator_version == ESTIMATOR_PROFILE_ID
    assert record.evidence_watermark == learning.get_evidence_watermark()
    assert record.updated_at


def test_unknown_target_reads_none(
    learning: SqliteLearningStore,
) -> None:
    state = learning.get_learner_target_state(
        TargetId("never-seen"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is None


def test_projection_is_deletable_and_rebuildable(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """§11 "可删后重建": delete the projection rows → rebuild → the same
    §11 state (freshness re-evaluates at rebuild time; the historical
    mass/estimate/bands are identical)."""

    target = TargetId("res-1")
    _commit_one(learning, store, conversation, "cm-rb-1")
    assert isinstance(learning.rebuild_learner_state(target,
                                                     "TEXT_PRODUCTION"), Ok)
    first = learning.get_learner_target_state(target, "TEXT_PRODUCTION")
    assert isinstance(first, Ok) and first.value is not None

    deleted = db.execute("DELETE FROM learner_target_state").rowcount
    assert deleted == 1
    db.commit()  # close the implicit tx before the store's own unit
    gone = learning.get_learner_target_state(target, "TEXT_PRODUCTION")
    assert isinstance(gone, Ok) and gone.value is None

    assert isinstance(learning.rebuild_learner_state(target,
                                                     "TEXT_PRODUCTION"), Ok)
    second = learning.get_learner_target_state(target, "TEXT_PRODUCTION")
    assert isinstance(second, Ok) and second.value is not None

    assert second.value.dimensions == first.value.dimensions
    assert second.value.coverage == first.value.coverage
    assert second.value.projection == first.value.projection
    assert second.value.evidence_watermark == first.value.evidence_watermark
    assert second.value.estimator_version == first.value.estimator_version
    # updated_at is the rebuild stamp, not the state content.


def test_rebuild_refuses_seven_section_contract_violations_loudly(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """A committed claim set that violates the BF-01 §7 contract (the
    Phase 0 protocol face does not yet run §7 checks) makes the rebuild
    fail VALIDATION_FAILED instead of silently computing corrupted
    canon — and leaves the previous projection intact."""

    from elc.learning.types import PerformanceType

    target = TargetId("res-7")
    _commit_one(
        learning,
        store,
        conversation,
        "cm-7-1",
        group_id="eg-7",
        target_id="res-7",
        claim=make_claim(performance_type=PerformanceType.RECOGNITION),
    )
    assert isinstance(
        learning.rebuild_learner_state(target, "TEXT_PRODUCTION"), Ok
    )
    before = learning.get_learner_target_state(target, "TEXT_PRODUCTION")
    assert isinstance(before, Ok) and before.value is not None

    # Corrupt the canon directly: turn the ACTIVE claim into an
    # INDEPENDENT_PRODUCTION with assistance (§7.1 violation that the
    # current commit face cannot produce but the estimator must still
    # refuse).
    db.execute(
        "UPDATE evidence_claim SET performance_type ="
        " 'INDEPENDENT_PRODUCTION', support_level = 'SEMANTIC_HINT'"
        " WHERE evidence_group_id = 'eg-7'"
    )
    db.commit()
    result = learning.rebuild_learner_state(target, "TEXT_PRODUCTION")
    assert isinstance(result, Err)
    assert "INDEPENDENT_WITH_ASSISTANCE" in str(result)
    after = learning.get_learner_target_state(target, "TEXT_PRODUCTION")
    assert isinstance(after, Ok)
    assert after.value == before.value  # untouched by the refusal


# -- §12 LearningSnapshot ----------------------------------------------------


def test_snapshot_shape_and_evidence_derived_only_red_line(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    _commit_one(learning, store, conversation, "cm-snap-1")
    assert isinstance(
        learning.rebuild_learner_state(
            TargetId("res-1"), "TEXT_PRODUCTION"
        ),
        Ok,
    )
    result = learning.get_learning_snapshot()
    assert isinstance(result, Ok)
    snapshot = result.value

    # §12 column set.
    assert str(snapshot.learning_snapshot_id).startswith("lsnap-")
    assert snapshot.user_scope_id == "user-local-v1"
    assert snapshot.as_of
    assert snapshot.estimator_version == ESTIMATOR_PROFILE_ID
    assert snapshot.evidence_watermark == learning.get_evidence_watermark()
    assert len(snapshot.targets) == 1

    # §12 red line: the serialized snapshot (and every nested document)
    # contains none of the forbidden Planner/Teaching/Scheduler fields.
    payload = json.dumps(
        {
            "snapshot_id": str(snapshot.learning_snapshot_id),
            "user_scope_id": snapshot.user_scope_id,
            "as_of": snapshot.as_of,
            "estimator_version": snapshot.estimator_version,
            "evidence_watermark": snapshot.evidence_watermark,
            "targets": [
                {
                    "target_type": t.target_type,
                    "target_id": str(t.target_id),
                    "evidence_modality": t.evidence_modality,
                    "dimensions": {
                        name: [d.estimate, d.confidence]
                        for name, d in t.dimensions.items()
                    },
                    "coverage": vars(t.coverage),
                    "freshness": vars(t.freshness),
                    "projection": {
                        **vars(t.projection),
                        "learning_flags": list(t.projection.learning_flags),
                    },
                }
                for t in snapshot.targets
            ],
        }
    )
    for key in FORBIDDEN_SNAPSHOT_KEYS:
        assert key not in payload, key

    # Same evidence state → same snapshot id on re-read.
    again = learning.get_learning_snapshot()
    assert isinstance(again, Ok)
    assert (
        again.value.learning_snapshot_id == snapshot.learning_snapshot_id
    )
    # A stale/foreign snapshot id is NOT_FOUND (Local V1 keeps no
    # snapshot archive — implementation-defined narrowing, §27).
    missing = learning.get_learning_snapshot("lsnap-foreign")
    assert isinstance(missing, Err)


# -- F2: watermark = durable evidence-change sequence -------------------------


def test_commit_supersede_invalidate_all_advance_the_watermark(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    _commit_one(learning, store, conversation, "cm-f2-1", group_id="eg-f2")
    assert learning.get_evidence_watermark() == 1

    claim_id = _first_claim_id(db, "eg-f2")
    superseded = learning.supersede_claim(
        EvidenceClaimId(claim_id),
        make_claim(claim_role="primary"),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(superseded, Ok)
    assert learning.get_evidence_watermark() == 2

    invalidated = learning.invalidate_claim(superseded.value)
    assert isinstance(invalidated, Ok)
    assert learning.get_evidence_watermark() == 3

    # The projection's watermark stamp rides the sequence.
    assert isinstance(
        learning.rebuild_learner_state(
            TargetId("res-1"), "TEXT_PRODUCTION"
        ),
        Ok,
    )
    state = learning.get_learner_target_state(
        TargetId("res-1"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is not None
    assert state.value.evidence_watermark == 3


# -- freshness face -------------------------------------------------------------


def test_get_freshness_unknown_without_state(
    learning: SqliteLearningStore,
) -> None:
    result = learning.get_freshness(TargetId("no-state"))
    assert isinstance(result, Ok)
    view = result.value
    assert view.last_strong_retrieval_at is None
    assert view.days_since_strong_retrieval is None
    assert view.freshness_band == "UNKNOWN"
    assert view.stability_band is None


def test_get_freshness_tracks_strong_retrieval_and_bands(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    _commit_one(
        learning,
        store,
        conversation,
        "cm-fresh-1",
        group_id="eg-fresh",
        target_id="res-fresh",
    )
    assert isinstance(
        learning.rebuild_learner_state(
            TargetId("res-fresh"), "TEXT_PRODUCTION"
        ),
        Ok,
    )
    # A RECOGNITION claim is not strong retrieval: UNKNOWN.
    view = learning.get_freshness(TargetId("res-fresh"))
    assert isinstance(view, Ok)
    assert view.value.freshness_band == "UNKNOWN"

    # Backdate a spontaneous success and rebuild: FRESH → AGING → STALE
    # as read time moves (BF-01 §22; D-INV-009 — freshness only).
    db.execute(
        "UPDATE evidence_claim SET performance_type ="
        " 'SPONTANEOUS_PRODUCTION', elicitation_type = 'NATURAL',"
        " created_at = '2026-09-19T10:00:00+00:00'"
        " WHERE evidence_group_id = 'eg-fresh'"
    )
    db.commit()
    assert isinstance(
        learning.rebuild_learner_state(
            TargetId("res-fresh"), "TEXT_PRODUCTION"
        ),
        Ok,
    )
    view = learning.get_freshness(TargetId("res-fresh"))
    assert isinstance(view, Ok)
    assert view.value.last_strong_retrieval_at is not None
    assert view.value.freshness_band == "FRESH"
    assert view.value.stability_band in {"FRAGILE", "FRESH"}

    db.execute(
        "UPDATE evidence_claim SET created_at = '2026-08-01T10:00:00+00:00'"
        " WHERE evidence_group_id = 'eg-fresh'"
    )
    db.commit()
    assert isinstance(
        learning.rebuild_learner_state(
            TargetId("res-fresh"), "TEXT_PRODUCTION"
        ),
        Ok,
    )
    view = learning.get_freshness(TargetId("res-fresh"))
    assert isinstance(view, Ok)
    assert view.value.freshness_band == "STALE"
