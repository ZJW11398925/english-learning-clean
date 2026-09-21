"""③④ — the p5-2 chain: resolution → durable proposal → validate/commit →
rebuild.

Everything below runs on the real durable kernel (the app.db fixture) and the
real content.db (the session artifact). The chain under test is the shipped
one:

    CP0 turn → resolve_turn (content.db supply + pure resolver)
      → produce/record the durable LEARNING_EVIDENCE proposal carrying the
        observation facts (the "target" document)
      → commit_learning_evidence: validate → group + the §6 claim → watermark
        (ONE group — the group's (turn, modality) unique key is the DATA_MODEL
        §6 "one observable behavior, one group" rule)
      → rebuild_learner_state: the §11 projection moves

The probes are grouped by what they establish:

- the proposal document: target-bearing only when a resolution is handed
  over, byte-shape identical otherwise (the zero-regression pin);
- the commit: one claim in the turn's own group, with the silent evaluator
  identity, no teaching-owned row anywhere;
- re-entry: idempotent per turn, and the durable document wins;
- refusals: an unreadable target document is Learning's REJECT;
- estimator consistency: a silent claim and an ordinary claim with the same
  facts move the projection identically.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from elc.conversation import CommitUserTurn
from elc.conversation.types import CanonicalTurnSlice
from elc.learning.analysis import (
    DETERMINISTIC_ANALYSIS_PRODUCER_ID,
    DETERMINISTIC_ANALYSIS_PRODUCER_VERSION,
    LearningEvidenceProposal,
    deterministic_analysis_id,
    deterministic_evidence_group_id,
    produce_learning_evidence_proposal,
)
from elc.learning.controller import LearningController
from elc.learning.silent_claim import (
    SILENT_EVIDENCE_EVALUATOR_ID,
    SILENT_EVIDENCE_EVALUATOR_VERSION,
    SILENT_EVIDENCE_MODALITY,
    SILENT_OBSERVATION_CLAIM_ROLE,
)
from elc.learning.silent_evidence import ContentBackedTargetSupply
from elc.learning.store import SqliteLearningStore
from elc.learning.target_resolution import (
    NO_TARGET,
    MatchVia,
    ResolvedTarget,
    resolution_document,
    resolution_from_document,
    resolve_target,
)
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidenceModality,
    EvidencePolarity,
    EvidenceStatus,
    ExposureLevel,
    PerformanceType,
    SupportLevel,
)
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    DomainErrorCode,
    Err,
    EvaluatorVersion,
    EvidenceGroupId,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
    TurnId,
)
from elc.runtime.types import InputEnvelope
from tests.conftest import REPO_ROOT
from tests.phase5.conftest import REQUESTED_AT, RUNTIME_VERSION

HEDGE = "res-hedge-i-think"
HEDGE_FORM = "I think it is going to rain."

_CLAIM_ROW_COLUMNS = (
    "evidence_claim_id",
    "evidence_group_id",
    "target_type",
    "target_id",
    "evidence_modality",
    "performance_type",
    "polarity",
    "outcome",
    "support_level",
    "answer_exposure_state",
    "elicitation_type",
    "spontaneity",
    "evaluator_id",
    "evaluator_version",
    "evaluator_confidence",
    "error_attribution",
    "status",
    "claim_role",
    "source_turn_id",
    "conversation_id",
    "teaching_moment_id",
    "attempt_id",
    "opportunity_id",
)


def _turn_slice(
    conversation_store: Any,
    conversation: ConversationId,
    cmid: str,
    text: str,
) -> CanonicalTurnSlice:
    """One CP0 turn through the real conversation store (no coordinator)."""

    committed = conversation_store.commit_user_turn(
        CommitUserTurn(
            conversation_id=conversation,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{cmid}"),
                client_message_id=ClientMessageId(cmid),
                conversation_id=str(conversation),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{cmid}",
                received_at=REQUESTED_AT,
            ),
            raw_content=text,
            runtime_version=RUNTIME_VERSION,
        )
    )
    assert isinstance(committed, Ok), committed
    slice_result = conversation_store.get_canonical_turn_slice(
        committed.value.turn_id
    )
    assert isinstance(slice_result, Ok) and slice_result.value is not None
    return slice_result.value


def _resolution(
    supply: ContentBackedTargetSupply, utterance: str
) -> ResolvedTarget:
    facts = supply.facts()
    assert isinstance(facts, Ok), facts
    resolution = resolve_target(utterance, facts.value)
    assert resolution is not NO_TARGET
    return resolution


def _count(db: sqlite3.Connection, statement: str) -> int:
    row = db.execute(statement).fetchone()
    assert row is not None
    return int(row[0])


def _claims(db: sqlite3.Connection) -> tuple[dict[str, Any], ...]:
    rows = db.execute(
        f"SELECT {', '.join(_CLAIM_ROW_COLUMNS)} FROM evidence_claim"
    ).fetchall()
    return tuple(dict(zip(_CLAIM_ROW_COLUMNS, row)) for row in rows)


def _state(
    db: sqlite3.Connection, target_id: str
) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT state_json FROM learner_target_state WHERE target_id = ?"
        " AND evidence_modality = ?",
        (target_id, EvidenceModality.TEXT_PRODUCTION.value),
    ).fetchone()
    return None if row is None else json.loads(str(row[0]))


def _commit_slice(
    learning: SqliteLearningStore,
    slice_: CanonicalTurnSlice,
    resolution: ResolvedTarget | None,
    *,
    persona_id: str | None = None,
):
    """The RA §4 steps 3-4 pair, store-direct (the coordinator's own call
    shapes, so the probes exercise exactly what the shipping path calls)."""

    artifact = learning.record_learning_analysis(slice_, resolution=resolution)
    assert isinstance(artifact, Ok), artifact
    committed = learning.commit_learning_evidence(
        artifact.value, slice_, persona_id
    )
    return artifact.value, committed


# ---------------------------------------------------------------------------
# ① the proposal document
# ---------------------------------------------------------------------------


def test_a_resolution_less_proposal_is_byte_identical_to_phase_2(
    conversation_store: Any, conversation: ConversationId
) -> None:
    """The zero-regression pin: no resolution → no target key, same five
    keys, same canonical JSON."""

    turn = _turn_slice(conversation_store, conversation, "cm-p52-doc-0", HEDGE_FORM)
    proposal = produce_learning_evidence_proposal(turn)
    document = json.loads(proposal.structured_proposal)
    assert sorted(document) == [
        "analysis_type",
        "evidence_modality",
        "observable",
        "utterance_length",
        "utterance_sha256",
    ]
    assert "target" not in document


def test_a_target_bearing_proposal_carries_the_observation_facts(
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-doc-1", HEDGE_FORM)
    resolution = _resolution(silent_supply, HEDGE_FORM)
    document = json.loads(
        produce_learning_evidence_proposal(
            turn, resolution=resolution
        ).structured_proposal
    )
    assert document["target"] == {
        "target_type": "RESOURCE",
        "target_id": HEDGE,
        "matched_form": HEDGE_FORM,
        "matched_via": "CANONICAL_FORM",
    }
    assert document["evidence_modality"] == SILENT_EVIDENCE_MODALITY
    assert document["observable"] is True


def test_the_document_is_deterministic(
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-doc-2", HEDGE_FORM)
    resolution = _resolution(silent_supply, HEDGE_FORM)
    first = produce_learning_evidence_proposal(turn, resolution=resolution)
    second = produce_learning_evidence_proposal(turn, resolution=resolution)
    assert first.structured_proposal == second.structured_proposal
    assert first.analysis_id == second.analysis_id


def test_the_resolution_document_round_trips() -> None:
    resolution = ResolvedTarget(
        target_type="CAPABILITY",
        target_id="cap-disc-topic-shift",
        matched_form="On that note, how was the meeting?",
        matched_via=MatchVia.ALTERNATIVE_REALIZATION,
    )
    document = resolution_document(resolution)
    assert resolution_from_document(document) == resolution


@pytest.mark.parametrize(
    "document",
    (
        {
            "target_type": "SENSE",
            "target_id": "x",
            "matched_form": "f",
            "matched_via": "CANONICAL_FORM",
        },
        {
            "target_type": "RESOURCE",
            "target_id": "x",
            "matched_form": "f",
            "matched_via": "FUZZY",
        },
        {
            "target_type": "RESOURCE",
            "target_id": "",
            "matched_form": "f",
            "matched_via": "CANONICAL_FORM",
        },
        {"target_type": "RESOURCE", "matched_form": "f"},
    ),
)
def test_an_unreadable_resolution_document_raises(document: dict) -> None:
    with pytest.raises((ValueError, KeyError)):
        resolution_from_document(document)


# ---------------------------------------------------------------------------
# ② the commit: one group, one claim
# ---------------------------------------------------------------------------


def test_the_commit_lands_the_claim_in_the_turns_own_group(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-hit", HEDGE_FORM)
    _, committed = _commit_slice(
        learning,
        turn,
        _resolution(silent_supply, HEDGE_FORM),
        persona_id="persona-default",
    )
    assert isinstance(committed, Ok), committed

    group_id = deterministic_evidence_group_id(
        turn.turn_id, EvidenceModality.TEXT_PRODUCTION.value
    )
    group_rows = db.execute(
        "SELECT evidence_group_id, teaching_moment_id, evidence_modality"
        " FROM evidence_group"
    ).fetchall()
    assert len(group_rows) == 1, "one observable behavior, one group"
    assert str(group_rows[0][0]) == str(group_id)
    assert group_rows[0][1] is None
    assert str(group_rows[0][2]) == SILENT_EVIDENCE_MODALITY

    claims = _claims(db)
    assert len(claims) == 1
    claim = claims[0]
    assert claim["evidence_group_id"] == str(group_id)
    assert claim["evidence_claim_id"] == f"ecl-silent-{turn.turn_id}"
    assert claim["target_id"] == HEDGE
    assert claim["target_type"] == "RESOURCE"
    assert claim["claim_role"] == SILENT_OBSERVATION_CLAIM_ROLE
    assert claim["status"] == "ACTIVE"
    assert claim["polarity"] == "POSITIVE"
    assert claim["outcome"] == "SUCCESS"
    assert claim["performance_type"] == "SPONTANEOUS_PRODUCTION"
    assert claim["support_level"] == "NONE"
    assert claim["answer_exposure_state"] == "NONE"
    assert claim["elicitation_type"] == "NATURAL"
    assert claim["spontaneity"] == "SPONTANEOUS"
    assert claim["evaluator_id"] == SILENT_EVIDENCE_EVALUATOR_ID
    assert claim["evaluator_version"] == SILENT_EVIDENCE_EVALUATOR_VERSION
    assert claim["evaluator_confidence"] == 1.0
    assert claim["error_attribution"] == "UNKNOWN"
    assert claim["evidence_modality"] == SILENT_EVIDENCE_MODALITY
    assert claim["source_turn_id"] == str(turn.turn_id)
    assert claim["conversation_id"] == str(conversation)
    assert claim["teaching_moment_id"] is None
    assert claim["attempt_id"] is None
    assert claim["opportunity_id"] is None

    commit_rows = db.execute(
        "SELECT evidence_commit_id, evidence_group_id, analysis_id,"
        " watermark_after FROM evidence_commit"
    ).fetchall()
    assert len(commit_rows) == 1
    assert str(commit_rows[0][1]) == str(group_id)
    assert str(commit_rows[0][2]) == str(deterministic_analysis_id(turn.turn_id))
    assert int(commit_rows[0][3]) >= 1


def test_a_target_less_commit_stays_claim_free(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
) -> None:
    """The Phase 2 shape, unchanged: the same group, no claim."""

    turn = _turn_slice(conversation_store, conversation, "cm-p52-plain", HEDGE_FORM)
    _, committed = _commit_slice(learning, turn, None)
    assert isinstance(committed, Ok), committed
    assert _count(db, "SELECT COUNT(*) FROM evidence_group") == 1
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM evidence_commit") == 1


def test_no_teaching_owned_row_is_created(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-clean", HEDGE_FORM)
    _, committed = _commit_slice(
        learning, turn, _resolution(silent_supply, HEDGE_FORM)
    )
    assert isinstance(committed, Ok), committed
    assert _count(db, "SELECT COUNT(*) FROM teaching_moment") == 0
    assert _count(db, "SELECT COUNT(*) FROM gate_decision") == 0
    assert _count(db, "SELECT COUNT(*) FROM active_teaching_lock") == 0
    assert _count(db, "SELECT COUNT(*) FROM learning_opportunity_record") == 0
    assert _count(db, "SELECT COUNT(*) FROM attempt_record") == 0


def test_the_rebuild_moves_the_state(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-state", HEDGE_FORM)
    assert _state(db, HEDGE) is None, "the before state is the leg's"
    _, committed = _commit_slice(
        learning, turn, _resolution(silent_supply, HEDGE_FORM)
    )
    assert isinstance(committed, Ok), committed
    controller = LearningController(learning)
    rebuilt = controller.rebuild_learner_state(
        TargetId(HEDGE), EvidenceModality.TEXT_PRODUCTION
    )
    assert isinstance(rebuilt, Ok), rebuilt
    state = _state(db, HEDGE)
    assert state is not None
    dimensions = state["dimensions"]
    assert dimensions["spontaneous_production"]["estimate"] not in (None, 0.0)
    assert dimensions["independent_production"]["estimate"] not in (None, 0.0)
    assert dimensions["recognition"]["estimate"] not in (None, 0.0)
    assert dimensions["guided_production"]["estimate"] not in (None, 0.0)
    assert state["coverage"]["evidence_groups"] == 1
    row = db.execute(
        "SELECT evidence_watermark FROM learner_target_state"
        " WHERE target_id = ? AND evidence_modality = ?",
        (HEDGE, EvidenceModality.TEXT_PRODUCTION.value),
    ).fetchone()
    assert row is not None and int(row[0]) >= 1


# ---------------------------------------------------------------------------
# ③ re-entry: idempotent, and the durable document wins
# ---------------------------------------------------------------------------


def test_re_entry_replays_instead_of_double_writing(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-twice", HEDGE_FORM)
    resolution = _resolution(silent_supply, HEDGE_FORM)
    _, first = _commit_slice(learning, turn, resolution)
    _, second = _commit_slice(learning, turn, resolution)
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value == second.value
    assert _count(db, "SELECT COUNT(*) FROM evidence_group") == 1
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 1
    assert _count(db, "SELECT COUNT(*) FROM evidence_commit") == 1
    assert _count(db, "SELECT COUNT(*) FROM evidence_watermark") == 1
    assert _count(db, "SELECT COUNT(*) FROM analysis_artifact") == 1


def test_the_durable_document_wins_on_re_entry(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """A re-entry that hands a different resolution cannot swap the facts:
    the replay returns the recorded proposal, and the commit reads only the
    durable document."""

    turn = _turn_slice(conversation_store, conversation, "cm-p52-wins", HEDGE_FORM)
    other = ResolvedTarget(
        target_type="CAPABILITY",
        target_id="cap-disc-topic-shift",
        matched_form="Speaking of which, how was the meeting?",
        matched_via=MatchVia.CANONICAL_FORM,
    )
    artifact, first = _commit_slice(
        learning, turn, _resolution(silent_supply, HEDGE_FORM)
    )
    replayed, second = _commit_slice(learning, turn, other)
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value == second.value
    assert replayed.structured_proposal == artifact.structured_proposal
    assert "cap-disc-topic-shift" not in replayed.structured_proposal
    claims = _claims(db)
    assert len(claims) == 1 and claims[0]["target_id"] == HEDGE


# ---------------------------------------------------------------------------
# ④ refusals: an unreadable target document is Learning's REJECT
# ---------------------------------------------------------------------------


def test_a_hand_edited_target_document_is_rejected(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """The defense for a foreign/hand-edited artifact row: the commit parses
    the *durable* document, and a document that is not a resolution refuses
    as VALIDATION_FAILED with the artifact flipped REJECTED — never a
    silent skip, never a claim."""

    turn = _turn_slice(conversation_store, conversation, "cm-p52-corrupt", HEDGE_FORM)
    artifact = produce_learning_evidence_proposal(
        turn, resolution=_resolution(silent_supply, HEDGE_FORM)
    )
    db.execute(
        "INSERT INTO analysis_artifact (analysis_id, turn_id, analysis_type,"
        " producer_id, producer_version, structured_proposal, confidence,"
        " status, created_at) VALUES (?, ?, 'LEARNING_EVIDENCE', ?, ?, ?, ?,"
        " 'PRODUCED', ?)",
        (
            artifact.analysis_id,
            turn.turn_id,
            artifact.producer_id,
            artifact.producer_version,
            artifact.structured_proposal,
            artifact.confidence,
            REQUESTED_AT,
        ),
    )
    db.commit()
    corrupt_document = {
        "analysis_type": "LEARNING_EVIDENCE",
        "evidence_modality": "TEXT_PRODUCTION",
        "observable": True,
        "utterance_sha256": json.loads(
            artifact.structured_proposal
        )["utterance_sha256"],
        "utterance_length": len(turn.user_turn.raw_content),
        "target": {"target_type": "SENSE", "target_id": "lex-1"},
    }
    corrupt = LearningEvidenceProposal(
        analysis_id=artifact.analysis_id,
        turn_id=turn.turn_id,
        producer_id=artifact.producer_id,
        producer_version=artifact.producer_version,
        structured_proposal=json.dumps(
            corrupt_document, sort_keys=True, separators=(",", ":")
        ),
        confidence=artifact.confidence,
    )
    db.execute(
        "UPDATE analysis_artifact SET structured_proposal = ?"
        " WHERE analysis_id = ?",
        (corrupt.structured_proposal, artifact.analysis_id),
    )
    db.commit()
    committed = learning.commit_learning_evidence(corrupt, turn)
    assert isinstance(committed, Err), committed
    assert committed.error.code is DomainErrorCode.VALIDATION_FAILED
    status = db.execute(
        "SELECT status FROM analysis_artifact WHERE analysis_id = ?",
        (artifact.analysis_id,),
    ).fetchone()
    assert status is not None and str(status[0]) == "REJECTED"
    assert _count(db, "SELECT COUNT(*) FROM evidence_claim") == 0
    assert _count(db, "SELECT COUNT(*) FROM evidence_group") == 0


# ---------------------------------------------------------------------------
# ⑦ the trust boundary (F-3, declared and pinned)
# ---------------------------------------------------------------------------


def test_the_supply_assumption_is_declared_in_the_source() -> None:
    """The port carries its trust assumption in its own docstring: the
    resolution must come from the supply read face, and the learning side
    neither re-checks supply nor reads content.db."""

    source = (
        REPO_ROOT / "src" / "elc" / "learning" / "silent_evidence.py"
    ).read_text(encoding="utf-8")
    assert "Trust boundary" in source
    assert "does not re-check supply" in source
    print("[probe] silent_evidence.py declares the trust boundary")


def test_the_kernel_trusts_the_document_and_never_checks_supply(
    db: sqlite3.Connection,
    conversation_store: Any,
    conversation: ConversationId,
    learning: SqliteLearningStore,
) -> None:
    """The boundary is where the doc says it is: a resolution document
    naming an id the corpus does not carry still commits (the read face is
    the supply gate, not the kernel — the teaching-provider division of
    labour). This pin fails the day the kernel starts validating supply,
    which is a contract change, not a silent tightening."""

    turn = _turn_slice(conversation_store, conversation, "cm-p52-trust", HEDGE_FORM)
    fabricated = ResolvedTarget(
        target_type="RESOURCE",
        target_id="res-not-in-any-supply",
        matched_form="a form no corpus carries",
        matched_via=MatchVia.REQUIRED_SLOTS,
    )
    artifact, committed = _commit_slice(learning, turn, fabricated)
    assert isinstance(committed, Ok), committed
    claims = _claims(db)
    print(f"[probe] fabricated-target claim -> {claims[0]['target_id']}")
    assert len(claims) == 1
    assert claims[0]["target_id"] == "res-not-in-any-supply"
    assert "res-not-in-any-supply" in artifact.structured_proposal


# ---------------------------------------------------------------------------
# ⑤ estimator consistency: the same facts move the state the same way
# ---------------------------------------------------------------------------


def _control_claim(target_id: str) -> EvidenceClaimView:
    """The silent claim's facts, dressed as an ordinary kernel claim."""

    return EvidenceClaimView(
        evidence_claim_id=f"ecl-control-{target_id}",
        claim_role="FOCUS_TARGET",
        scope="RESOURCE",
        performance_type=PerformanceType.SPONTANEOUS_PRODUCTION,
        evidence_modality=EvidenceModality.TEXT_PRODUCTION,
        qualifiers=(),
        polarity=EvidencePolarity.POSITIVE,
        outcome=AttemptOutcome.SUCCESS,
        support=SupportLevel.NONE,
        exposure=ExposureLevel.NONE,
        evaluator_confidence=1.0,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance="control:synthetic",
        opportunity_id=None,
        target_id=target_id,
    )


def test_the_estimator_treats_a_silent_claim_like_any_other(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    turn = _turn_slice(conversation_store, conversation, "cm-p52-est", HEDGE_FORM)
    _, committed = _commit_slice(
        learning, turn, _resolution(silent_supply, HEDGE_FORM)
    )
    assert isinstance(committed, Ok), committed

    # The control rides a *different* turn: the group key is (turn,
    # modality), so one turn carries exactly one group (DATA_MODEL §6).
    control_turn = _turn_slice(
        conversation_store, conversation, "cm-p52-est-control", "a plain turn"
    )
    control_id = "res-control-target"
    controller = LearningController(learning)
    control_group = EvidenceGroupRecord(
        evidence_group_id=EvidenceGroupId("eg-control-estimator"),
        moment_id=None,
        attempt_id=None,
        target_id=TargetId(control_id),
        evaluator_version=EvaluatorVersion("control-evaluator-v1"),
        claims=(_control_claim(control_id),),
    )
    control_commit = controller.commit_evidence_group(
        control_group,
        source_turn_id=TurnId(str(control_turn.turn_id)),
        conversation_id=str(conversation),
        persona_id=None,
        evaluator_id="control-evaluator",
    )
    assert isinstance(control_commit, Ok), control_commit
    for target_id in (HEDGE, control_id):
        rebuilt = controller.rebuild_learner_state(
            TargetId(target_id), EvidenceModality.TEXT_PRODUCTION
        )
        assert isinstance(rebuilt, Ok), rebuilt

    silent_state = controller.get_learner_target_state(
        TargetId(HEDGE), EvidenceModality.TEXT_PRODUCTION
    )
    control_state = controller.get_learner_target_state(
        TargetId(control_id), EvidenceModality.TEXT_PRODUCTION
    )
    assert isinstance(silent_state, Ok) and silent_state.value is not None
    assert isinstance(control_state, Ok) and control_state.value is not None

    def _mass(dimensions):
        # estimate + confidence are the estimator's mass surface;
        # last_relevant_evidence_at is a wall-clock stamp and differs by
        # construction (two commits, two instants).
        return {
            name: (state.estimate, state.confidence)
            for name, state in dimensions.items()
        }

    assert _mass(silent_state.value.dimensions) == _mass(
        control_state.value.dimensions
    )
    assert silent_state.value.projection == control_state.value.projection
    assert silent_state.value.coverage == control_state.value.coverage
    assert silent_state.value.estimator_version == (
        control_state.value.estimator_version
    )


def test_the_silent_modality_constant_matches_the_v1_evidence_modality() -> None:
    """The port's rebuild key and the claim's modality cannot drift."""

    assert SILENT_EVIDENCE_MODALITY == EvidenceModality.TEXT_PRODUCTION.value


def test_the_producer_identity_is_unchanged_by_the_extension(
    conversation_store: Any,
    conversation: ConversationId,
    silent_supply: ContentBackedTargetSupply,
) -> None:
    """The target-bearing document is the same deterministic producer (the
    claim's evaluator identity is versioned separately, silent_claim)."""

    turn = _turn_slice(conversation_store, conversation, "cm-p52-prod", HEDGE_FORM)
    proposal = produce_learning_evidence_proposal(
        turn, resolution=_resolution(silent_supply, HEDGE_FORM)
    )
    assert proposal.producer_id == DETERMINISTIC_ANALYSIS_PRODUCER_ID
    assert proposal.producer_version == DETERMINISTIC_ANALYSIS_PRODUCER_VERSION
    assert proposal.confidence == 1.0
