"""VAL ② — LearningController is a real authority face over the store
(P3-0 ②).

Pins: the controller satisfies the frozen protocol faces
(LearningCommands / LearningQueries), every operation through the
controller behaves identically to the store-direct path (same operation
→ same result, including Err shapes), and the read-time watermark gate
(①) rides through the controller unchanged.
"""

from __future__ import annotations

from elc.learning import LearningCommands, LearningController
from elc.learning.queries import LearningQueries
from elc.learning.store import SqliteLearningStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, Ok, TargetId, UserTurnId
from tests.phase2.conftest import commit_ok, make_claim, make_group


def _commit_via(
    face, store, conversation, client_message_id: str, group_id: str
):
    """One protocol-face commit (controller or store — same kwargs)."""

    cp0 = commit_ok(store, conversation, client_message_id, "utterance")
    group = make_group(group_id, (make_claim(),), target_id="res-ctl")
    return face.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )


def test_controller_satisfies_the_frozen_protocol_faces(
    learning: SqliteLearningStore,
) -> None:
    controller = LearningController(learning)
    assert isinstance(controller, LearningCommands)
    assert isinstance(controller, LearningQueries)


def test_controller_commit_matches_store_commit_result(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    """Same operation, same result: a controller commit and a store
    commit of the same group yield the SAME deterministic
    EvidenceCommitId (the store replay path proves both went through one
    durable semantics), and the watermark advanced exactly once."""

    controller = LearningController(learning)
    first = _commit_via(controller, store, conversation, "cm-ctl-1", "eg-ctl")
    assert isinstance(first, Ok), first
    assert learning.get_evidence_watermark() == 1

    # The store-direct call replays the same durable commit (idempotent
    # on the group) — controller and store are one semantics.
    replay = _commit_via(learning, store, conversation, "cm-ctl-2", "eg-ctl")
    assert isinstance(replay, Ok)
    assert replay.value == first.value
    assert learning.get_evidence_watermark() == 1  # no double count


def test_controller_refusal_matches_store_refusal(
    learning: SqliteLearningStore,
) -> None:
    """The store's §6-column-set Err flows through the controller
    unchanged (bare Phase 0 protocol shape, no kwargs)."""

    controller = LearningController(learning)
    group = make_group("eg-ctl-refused", (make_claim(),), target_id="res-r")
    refused = controller.commit_evidence_group(group)
    store_refused = learning.commit_evidence_group(group)
    assert isinstance(refused, Err) and isinstance(store_refused, Err)
    assert refused.error.code == store_refused.error.code
    assert refused.error.message == store_refused.error.message
    assert refused.error.code.value == "VALIDATION_FAILED"


def test_controller_projection_and_query_faces_match_the_store(
    learning: SqliteLearningStore,
    store,
    conversation,
    fence: RuntimeEpochFence,
) -> None:
    del fence  # same-epoch store throughout
    controller = LearningController(learning)
    committed = _commit_via(
        controller, store, conversation, "cm-ctl-3", "eg-ctl-3"
    )
    assert isinstance(committed, Ok)

    rebuilt = controller.rebuild_learner_state(
        TargetId("res-ctl"), "TEXT_PRODUCTION"
    )
    store_rebuilt = learning.rebuild_learner_state(
        TargetId("res-ctl"), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok) and isinstance(store_rebuilt, Ok)
    assert rebuilt.value.startswith("sv-")

    state = controller.get_learner_target_state(
        TargetId("res-ctl"), "TEXT_PRODUCTION"
    )
    store_state = learning.get_learner_target_state(
        TargetId("res-ctl"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and isinstance(store_state, Ok)
    assert state.value == store_state.value

    snapshot = controller.get_learning_snapshot()
    store_snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok) and isinstance(store_snapshot, Ok)
    assert (
        snapshot.value.learning_snapshot_id
        == store_snapshot.value.learning_snapshot_id
    )
    assert snapshot.value.targets == store_snapshot.value.targets
    assert snapshot.value.evidence_watermark == (
        store_snapshot.value.evidence_watermark
    )

    freshness = controller.get_freshness(TargetId("res-ctl"))
    store_freshness = learning.get_freshness(TargetId("res-ctl"))
    assert isinstance(freshness, Ok) and isinstance(store_freshness, Ok)
    assert freshness.value == store_freshness.value

    # A foreign snapshot id is NOT_FOUND through the controller too.
    missing = controller.get_learning_snapshot("lsnap-foreign")
    assert isinstance(missing, Err)
    assert missing.error.code.value == "NOT_FOUND"


def test_controller_self_report_and_watermark_gate_ride_through(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    """record_self_report semantics (§8 guard) and the ① read-time
    watermark refusal both surface unchanged on the controller face."""

    controller = LearningController(learning)
    cp0 = commit_ok(store, conversation, "cm-ctl-sr", "self report")
    bare = controller.record_self_report(
        "user-1", TargetId("res-ctl"), "CLAIMS_KNOWN"
    )
    assert isinstance(bare, Err)  # §8 column set requires user_turn_id
    assert bare.error.code.value == "VALIDATION_FAILED"

    reported = controller.record_self_report(
        "user-1",
        TargetId("res-ctl"),
        "CLAIMS_KNOWN",
        user_turn_id=UserTurnId(cp0.user_turn_id),
    )
    assert isinstance(reported, Ok)

    committed = _commit_via(
        controller, store, conversation, "cm-ctl-4", "eg-ctl-4"
    )
    assert isinstance(committed, Ok)
    assert isinstance(
        controller.rebuild_learner_state(
            TargetId("res-ctl"), "TEXT_PRODUCTION"
        ),
        Ok,
    )
    # Commit again without rebuild → the controller snapshot read refuses
    # exactly like the store read (① rides the delegation).
    more = _commit_via(controller, store, conversation, "cm-ctl-5", "eg-ctl-5")
    assert isinstance(more, Ok)
    refused = controller.get_learning_snapshot()
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"


def test_record_opportunity_is_exposed_on_the_controller_face(
    db,
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    """P3-1A ⑧: LearningOpportunityRecord (DATA_MODEL §7) through the
    authority face — the "genuine Opportunity" leg of the §6 negative
    evidence rule was store-only before this slice; it now returns the
    durable LearningOpportunityId and takes the moment link.

    Re-recording the same id is refused as CONFLICT (the durable row
    exists; the §7 write face is an insert, not an upsert) — pinned here
    so the behavior is a contract, not a surprise.
    """

    from elc.platform.types import LearningOpportunityId

    controller = LearningController(learning)
    cp0 = commit_ok(store, conversation, "cm-ctl-lor", "negative attempt")
    recorded = controller.record_opportunity(
        source_turn_id=cp0.turn_id,
        target_type="RESOURCE",
        target_id=TargetId("res-ctl-lor"),
        opportunity_type="ELICITED",
        target_explicitness="EXPLICIT_TARGET",
        attempt_observed=True,
        alternative_realizations_allowed=True,
    )
    assert isinstance(recorded, Ok), recorded
    assert isinstance(recorded.value, str)  # LearningOpportunityId (NewType)

    replay = controller.record_opportunity(
        source_turn_id=cp0.turn_id,
        target_type="RESOURCE",
        target_id=TargetId("res-ctl-lor"),
        opportunity_type="ELICITED",
        target_explicitness="EXPLICIT_TARGET",
        attempt_observed=True,
        alternative_realizations_allowed=True,
        learning_opportunity_id=LearningOpportunityId(recorded.value),
    )
    assert not isinstance(replay, Ok)  # duplicate durable id
    assert replay.error.code.value == "CONFLICT"

    row = db.execute(
        "SELECT target_type, target_id, opportunity_type,"
        " target_explicitness, attempt_observed,"
        " alternative_realizations_allowed, teaching_moment_id"
        " FROM learning_opportunity_record"
    ).fetchone()
    assert row == (
        "RESOURCE",
        "res-ctl-lor",
        "ELICITED",
        "EXPLICIT_TARGET",
        1,
        1,
        None,
    )

    # The opportunity vocabulary is rejected when malformed (the §7 words).
    refused = controller.record_opportunity(
        source_turn_id=cp0.turn_id,
        target_type="RESOURCE",
        target_id=TargetId("res-ctl-lor"),
        opportunity_type="NOT_A_TYPE",
        target_explicitness="IMPLICIT",
        attempt_observed=False,
        alternative_realizations_allowed=True,
    )
    assert not isinstance(refused, Ok)
