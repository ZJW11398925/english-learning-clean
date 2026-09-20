"""VAL ⑥ (part 1) — the DOMAIN_MODEL §6 negative-evidence rule.

"只有 genuine Opportunity 或 attempted use 才能形成 target-specific
negative evidence."

Three store-face outcomes, all asserted for residue:
- NEGATIVE + RECOGNITION with no opportunity on record → REJECTED,
  nothing durable;
- NEGATIVE + RECOGNITION with a genuine LearningOpportunityRecord →
  COMMITTED;
- NEGATIVE + production-side performance type (attempted use) with no
  opportunity → COMMITTED.
"""

from __future__ import annotations

import sqlite3

from elc.learning.store import SqliteLearningStore
from elc.learning.types import (
    AttemptOutcome,
    EvidencePolarity,
    PerformanceType,
)
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, EvaluatorVersion, Ok
from tests.phase2.conftest import (
    commit_ok,
    make_claim,
    make_group,
)


def _negative_claim(
    performance_type: PerformanceType = PerformanceType.RECOGNITION,
):
    return make_claim(
        polarity=EvidencePolarity.NEGATIVE,
        outcome=AttemptOutcome.FAILURE,
        performance_type=performance_type,
    )


def test_negative_recognition_without_opportunity_is_rejected(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-neg1", "hmm")
    result = learning.commit_evidence_group(
        make_group("eg-neg1", (_negative_claim(),)),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Err)
    assert "negative evidence" in result.error.message
    # No residue: the validation failure rolled the whole unit back.
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == 0


def test_negative_with_genuine_opportunity_is_committed(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-neg2", "hmm again")
    opportunity = learning.record_opportunity(
        source_turn_id=cp0.turn_id,
        target_type="RESOURCE",
        target_id="res-1",
        opportunity_type="ELICITED",
        target_explicitness="SEMANTICALLY_CONSTRAINED",
        attempt_observed=True,
        alternative_realizations_allowed=False,
    )
    assert isinstance(opportunity, Ok), opportunity

    result = learning.commit_evidence_group(
        make_group("eg-neg2", (_negative_claim(),)),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Ok), result
    row = db.execute(
        "SELECT polarity, outcome, status FROM evidence_claim"
    ).fetchone()
    assert row[0] == "NEGATIVE"
    assert row[2] == "ACTIVE"
    # The claim can link its opportunity (canonical opportunity_id?).
    assert (
        db.execute("SELECT COUNT(*) FROM learning_opportunity_record").fetchone()[0]
        == 1
    )


def test_opportunity_must_match_the_target(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """A genuine opportunity for a DIFFERENT target does not open the
    gate for this target's negative claim."""
    cp0 = commit_ok(store, conversation, "cm-neg3", "hmm")
    other_target = learning.record_opportunity(
        source_turn_id=cp0.turn_id,
        target_type="RESOURCE",
        target_id="res-OTHER",
        opportunity_type="NATURAL",
        target_explicitness="IMPLICIT",
        attempt_observed=False,
        alternative_realizations_allowed=True,
    )
    assert isinstance(other_target, Ok)
    result = learning.commit_evidence_group(
        make_group("eg-neg3", (_negative_claim(),), target_id="res-1"),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Err)
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0


def test_negative_attempted_use_without_opportunity_is_committed(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Attempted use (production-side performance types) is itself a
    legitimate negative-evidence leg — no opportunity needed."""
    for performance in (
        PerformanceType.FAILED_ATTEMPT,
        PerformanceType.MISUSE,
        PerformanceType.INDEPENDENT_PRODUCTION,
        PerformanceType.SPONTANEOUS_PRODUCTION,
    ):
        cp0 = commit_ok(store, conversation, f"cm-attempt-{performance}", "x")
        result = learning.commit_evidence_group(
            make_group(f"eg-{performance}", (_negative_claim(performance),)),
            source_turn_id=cp0.turn_id,
            conversation_id=str(conversation),
        )
        assert isinstance(result, Ok), (performance, result)


def test_supersede_applies_the_negative_gate_to_the_replacement(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """A correction may not smuggle in a rule-violating negative claim."""
    from elc.platform.types import EvidenceClaimId

    cp0 = commit_ok(store, conversation, "cm-neg-sup", "source")
    committed = learning.commit_evidence_group(
        make_group("eg-neg-sup", (make_claim(claim_role="primary"),)),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(committed, Ok)
    original_id = db.execute(
        "SELECT evidence_claim_id FROM evidence_claim"
        " WHERE claim_role = 'primary'"
    ).fetchone()[0]

    result = learning.supersede_claim(
        EvidenceClaimId(str(original_id)),
        _negative_claim(),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(result, Err)
    row = learning.get_claim(EvidenceClaimId(str(original_id)))
    assert isinstance(row, Ok) and row.value is not None
    assert row.value.status == "ACTIVE"  # untouched by the refused fix


def test_outcome_vocabulary_boundary_is_enforced(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """STATE_MACHINES §5 ALTERNATIVE_SUCCESS is an attempt word, not a
    DATA_MODEL §6 claim outcome — refused at the store face."""
    cp0 = commit_ok(store, conversation, "cm-outcome", "x")
    result = learning.commit_evidence_group(
        make_group(
            "eg-outcome",
            (make_claim(outcome=AttemptOutcome.ALTERNATIVE_SUCCESS),),
        ),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Err)
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
