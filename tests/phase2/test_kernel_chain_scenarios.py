"""VAL ⑥ (VE face toward VAL-…17) — real-kernel chain scenarios:
commit_evidence_group → rebuild_learner_state → get_learning_snapshot
over the BF-01A/OQ behavioral semantics.

Pinned:
- idempotent replay does not double-count;
- supersede / invalidate rebuild correctly (F2: invalidate advances the
  watermark too);
- a zero-claim group contributes zero;
- default-fill claims estimate identically to explicit same-value
  claims (no hidden default effects);
- a pending PRODUCED artifact is never consumed by the estimator
  (rebuild reads ACTIVE claims only);
- ability ≠ confidence separation visible through the projection.
"""

from __future__ import annotations

import sqlite3

from elc.conversation.types import CanonicalTurnSlice
from elc.learning.estimator import EstimatorClaimView, estimate_target_state
from elc.learning.store import SqliteLearningStore
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidencePolarity,
    EvidenceQualifier,
    EvidenceStatus,
    ExposureLevel,
    PerformanceType,
    SupportLevel,
)
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    EvaluatorVersion,
    EvidenceClaimId,
    EvidenceGroupId,
    EvidenceModality,
    Ok,
    TargetId,
)
from tests.phase2.conftest import commit_ok, make_claim, make_group


def _commit(
    learning: SqliteLearningStore,
    store,
    conversation,
    client_message_id: str,
    group: EvidenceGroupRecord,
):
    cp0 = commit_ok(
        store, conversation, client_message_id, f"{client_message_id} body"
    )
    result = learning.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Ok), result
    return result.value


def _spontaneous_claim(
    claim_id: str = "ecl-sp", confidence: float = 0.95
) -> EvidenceClaimView:
    return EvidenceClaimView(
        evidence_claim_id=claim_id,
        claim_role="primary",
        scope="RESOURCE",
        performance_type=PerformanceType.SPONTANEOUS_PRODUCTION,
        evidence_modality=EvidenceModality.TEXT_PRODUCTION,
        qualifiers=(EvidenceQualifier.CROSS_CONTEXT,),
        polarity=EvidencePolarity.POSITIVE,
        outcome=AttemptOutcome.SUCCESS,
        support=SupportLevel.NONE,
        exposure=ExposureLevel.NONE,
        evaluator_confidence=confidence,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance="test",
    )


def _state(learning: SqliteLearningStore, target: str = "res-chain"):
    rebuilt = learning.rebuild_learner_state(
        TargetId(target), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok), rebuilt
    result = learning.get_learner_target_state(
        TargetId(target), "TEXT_PRODUCTION"
    )
    assert isinstance(result, Ok) and result.value is not None
    return result.value


# -- idempotent replay -------------------------------------------------------


def test_idempotent_replay_does_not_double_count(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    group = make_group(
        "eg-replay",
        (_spontaneous_claim(),),
        target_id="res-chain",
    )
    first = _commit(learning, store, conversation, "cm-replay", group)
    second = _commit(learning, store, conversation, "cm-replay-2", group)
    assert first == second  # §25 group-key replay returns the same commit
    assert learning.get_evidence_watermark() == 1
    state = _state(learning)
    assert state.coverage.evidence_groups == 1
    # Exactly one claim's worth: estimate is the P/(P+N) ratio of ONE
    # spontaneous success (single-cluster mass, LOW confidence — the
    # ratio cannot distinguish one success from three; the coverage and
    # confidence can).
    assert state.dimensions["independent_production"].estimate == 1.0
    assert state.projection.confidence_band == "LOW"


# -- supersede / invalidate rebuild ------------------------------------------


def test_supersede_and_invalidate_rebuild_correctly(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    _commit(
        learning,
        store,
        conversation,
        "cm-sup-1",
        make_group(
            "eg-ch-sup", (make_claim(),), target_id="res-chain"
        ),
    )
    _commit(
        learning,
        store,
        conversation,
        "cm-sup-2",
        make_group(
            "eg-ch-sup2",
            (_spontaneous_claim("ecl-sp2"),),
            target_id="res-chain",
        ),
    )
    before = _state(learning)
    assert before.dimensions["spontaneous_production"].estimate == 1.0

    # Supersede the spontaneous claim with a weaker RECOGNITION claim:
    # the replacement enters the estimating set, the old one leaves.
    claim_id = db.execute(
        "SELECT evidence_claim_id FROM evidence_claim"
        " WHERE evidence_group_id = 'eg-ch-sup2'"
    ).fetchone()[0]
    superseded = learning.supersede_claim(
        EvidenceClaimId(str(claim_id)),
        make_claim(claim_role="primary"),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(superseded, Ok)
    after_supersede = _state(learning)
    assert (
        after_supersede.dimensions["spontaneous_production"].estimate
        is None
    )
    assert after_supersede.dimensions["recognition"].estimate is not None

    # F2 path: invalidate the replacement — the watermark advances and
    # the rebuild drops its mass entirely.
    watermark_before = learning.get_evidence_watermark()
    invalidated = learning.invalidate_claim(superseded.value)
    assert isinstance(invalidated, Ok)
    assert learning.get_evidence_watermark() == watermark_before + 1
    after_invalidate = _state(learning)
    assert (
        after_invalidate.dimensions["recognition"].estimate
        == before.dimensions["recognition"].estimate
    )
    # And invalidating EVERYTHING collapses the state to UNKNOWN evidence.
    remaining = db.execute(
        "SELECT evidence_claim_id FROM evidence_claim"
        " WHERE target_id = 'res-chain' AND status = 'ACTIVE'"
    ).fetchall()
    for row in remaining:
        assert isinstance(
            learning.invalidate_claim(EvidenceClaimId(str(row[0]))), Ok
        )
    emptied = _state(learning)
    assert emptied.projection.ability_band == "UNKNOWN"
    assert "INSUFFICIENT_EVIDENCE" in emptied.projection.learning_flags


# -- zero-claim groups ---------------------------------------------------------


def test_zero_claim_group_contributes_zero(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    group = EvidenceGroupRecord(
        evidence_group_id=EvidenceGroupId("eg-empty"),
        moment_id=None,
        attempt_id=None,
        target_id=TargetId("res-none"),
        evaluator_version=EvaluatorVersion("evaluator-test-v1"),
        claims=(),
    )
    _commit(learning, store, conversation, "cm-empty", group)
    assert learning.get_evidence_watermark() == 1

    # No target ever received a claim: no projection row, and the
    # snapshot carries no targets for it.
    rebuilt = learning.rebuild_learner_state(
        TargetId("res-none"), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok)
    state = learning.get_learner_target_state(
        TargetId("res-none"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is None
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)
    assert snapshot.value.targets == ()


# -- default fills vs explicit same values --------------------------------------


def test_default_fill_claims_estimate_identically_to_explicit_values(
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """The store's documented default fills (elicitation 'NATURAL',
    spontaneity 'SPONTANEOUS', novelty 0.0) have no hidden estimator
    effect: the projection equals a hand-built estimator run over views
    with those values spelled out explicitly."""

    _commit(
        learning,
        store,
        conversation,
        "cm-default",
        make_group(
            "eg-default",
            (_spontaneous_claim("ecl-dflt"),),
            target_id="res-chain",
        ),
    )
    record = _state(learning)

    # Reconstruct the exact view the adapter produced — with the default
    # fill values explicit.
    row = learning.get_evidence_group(EvidenceGroupId("eg-default"))
    assert isinstance(row, Ok) and row.value is not None
    _, claims = row.value
    assert len(claims) == 1
    stored = claims[0]
    assert stored.elicitation_type == "NATURAL"  # default fill
    assert stored.spontaneity == "SPONTANEOUS"  # default fill
    assert stored.support_level == "NONE"
    assert stored.answer_exposure_state == "NONE"

    explicit = estimate_target_state(
        [
            EstimatorClaimView(
                group_id=stored.evidence_group_id,
                timestamp=stored.created_at,
                performance_type="SPONTANEOUS_PRODUCTION",
                polarity="POSITIVE",
                outcome="SUCCESS",
                evaluator_confidence=stored.evaluator_confidence,
                support_level="NONE",
                exposure_level="NONE",
                opportunity_type="NATURAL",
                qualifiers=stored.qualifiers,
                error_attribution="UNKNOWN",
                accuracy=None,
                pragmatic_fit=None,
                conversation_id=stored.conversation_id,
                teaching_moment_id=None,
                persona_id=None,
                context_key=None,
                realization_key=None,
                target_type="RESOURCE",
                target_id="res-chain",
                modality="TEXT_PRODUCTION",
                status="ACTIVE",
                spontaneity="SPONTANEOUS",
            )
        ],
        target_type="RESOURCE",
        target_id="res-chain",
        modality="TEXT_PRODUCTION",
        as_of=record.updated_at,
    )
    for name, dimension in explicit.dimensions.items():
        assert record.dimensions[name].estimate == dimension.estimate, name
        assert record.dimensions[name].confidence == dimension.confidence, (
            name
        )
    assert (
        record.projection.ability_band == explicit.projection.ability_band
    )
    assert (
        record.projection.confidence_band
        == explicit.projection.confidence_band
    )
    assert (
        record.projection.stability_band == explicit.projection.stability_band
    )
    assert (
        record.projection.learning_flags
        == explicit.projection.learning_flags
    )


# -- pending PRODUCED artifacts are never consumed -------------------------------


def test_pending_produced_artifact_is_not_estimator_input(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """record_learning_analysis leaves a PRODUCED artifact (proposal).
    Without CP1 there is no claim, no watermark move, and the rebuild
    has nothing to consume; after CP1 (which commits zero claims for
    this deterministic producer) the estimator still reads zero ACTIVE
    claims — pending/committed artifacts are audit facts, not evidence."""

    cp0 = commit_ok(store, conversation, "cm-prod", "an observable turn")
    slice_result = store.get_canonical_turn_slice(cp0.turn_id)
    assert isinstance(slice_result, Ok) and slice_result.value is not None
    turn: CanonicalTurnSlice = slice_result.value

    watermark_before = learning.get_evidence_watermark()
    proposal = learning.record_learning_analysis(turn)
    assert isinstance(proposal, Ok)
    artifact = learning.get_analysis_for_turn(turn.turn_id)
    assert isinstance(artifact, Ok) and artifact.value is not None
    assert artifact.value.status == "PRODUCED"
    assert learning.get_evidence_watermark() == watermark_before

    # No target claims exist: the rebuild projects nothing.
    rebuilt = learning.rebuild_learner_state(
        TargetId("expr.anything"), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok)
    state = learning.get_learner_target_state(
        TargetId("expr.anything"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is None
    rows = db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0]
    assert rows == 0

    committed = learning.commit_learning_evidence(proposal.value, turn)
    assert isinstance(committed, Ok)
    assert learning.get_evidence_watermark() == watermark_before + 1
    # The deterministic producer commits a group with ZERO claims: the
    # estimator's input stays empty (PRODUCED/COMMITTED artifacts are
    # never claim sources).
    rows = db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0]
    assert rows == 0
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)
    assert snapshot.value.targets == ()
    assert snapshot.value.evidence_watermark == watermark_before + 1


# -- ability ≠ confidence through the projection ---------------------------------


def test_ability_and_confidence_separation_is_visible(
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    _commit(
        learning,
        store,
        conversation,
        "cm-sep",
        make_group(
            "eg-sep",
            (_spontaneous_claim("ecl-sep"),),
            target_id="res-chain",
        ),
    )
    record = _state(learning)
    independent = record.dimensions["independent_production"]
    # §11 estimate and confidence are independent fields: one strong
    # success → high estimate, LOW confidence band (BF-01 §14 example).
    assert independent.estimate is not None and independent.estimate >= 0.95
    assert record.projection.confidence_band == "LOW"
    assert record.projection.ability_band == "SPONTANEOUS"
    assert "STRONG_SPONTANEOUS_CONTROL" not in (
        record.projection.learning_flags
    )


# -- §7 contract through the protocol face ----------------------------------------


def test_protocol_face_cannot_create_contract_clean_claims_only(
    learning: SqliteLearningStore,
    store,
    conversation,
) -> None:
    """The §7 check itself lives in the estimator (strict rebuild); the
    protocol face can still persist a violating claim today (reported
    boundary) — but the rebuild then refuses loudly, which the
    projection suite pins. Here: legal spontaneous claims (the default
    fills keep them §7-clean) rebuild without error."""

    group = make_group(
        "eg-clean",
        (_spontaneous_claim("ecl-clean"),),
        target_id="res-clean",
    )
    _commit(learning, store, conversation, "cm-clean", group)
    rebuilt = learning.rebuild_learner_state(
        TargetId("res-clean"), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok), rebuilt
    state = learning.get_learner_target_state(
        TargetId("res-clean"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is not None
    assert state.value.projection.ability_band == "SPONTANEOUS"
