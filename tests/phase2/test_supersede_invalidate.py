"""VAL ⑤ — supersede / invalidate lifecycle with a traceable chain.

STATE_MACHINES §18: evidence is append-only; corrections move a claim to
SUPERSEDED (via a replacement carrying supersedes_claim_id) or
INVALIDATED. Learner State rebuilds from ACTIVE evidence only. The old
rows stay fully traceable (the chain walks newest → root).
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
from elc.platform.types import (
    Err,
    EvaluatorVersion,
    EvidenceClaimId,
    Ok,
)
from tests.phase2.conftest import (
    commit_ok,
    make_claim,
    make_group,
)


def _committed_positive_claim(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> str:
    cp0 = commit_ok(store, conversation, "cm-sup", "supersede source")
    result = learning.commit_evidence_group(
        make_group("eg-sup", (make_claim(claim_role="primary"),)),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(result, Ok), result
    row = db.execute(
        "SELECT evidence_claim_id FROM evidence_claim"
        " WHERE claim_role = 'primary'"
    ).fetchone()
    return str(row[0])


def test_supersede_links_chain_and_flips_old_status(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    original_id = _committed_positive_claim(
        db, learning, store, fence, conversation
    )
    watermark_before = learning.get_evidence_watermark()

    replacement = make_claim(
        claim_role="primary",
        performance_type=PerformanceType.SELF_REPAIR,
        outcome=AttemptOutcome.SUCCESS,
        polarity=EvidencePolarity.POSITIVE,
    )
    superseded = learning.supersede_claim(
        EvidenceClaimId(original_id),
        replacement,
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(superseded, Ok), superseded
    new_id = superseded.value

    # New claim: ACTIVE, points at the old claim.
    new_row = learning.get_claim(new_id)
    assert isinstance(new_row, Ok) and new_row.value is not None
    assert new_row.value.status == "ACTIVE"
    assert new_row.value.supersedes_claim_id == original_id
    assert new_row.value.performance_type == "SELF_REPAIR"
    # Old claim: SUPERSEDED, still durable and traceable.
    old_row = learning.get_claim(EvidenceClaimId(original_id))
    assert isinstance(old_row, Ok) and old_row.value is not None
    assert old_row.value.status == "SUPERSEDED"

    chain = learning.supersede_chain(new_id)
    assert isinstance(chain, Ok)
    ids = [claim.evidence_claim_id for claim in chain.value]
    assert ids == [new_id, original_id]

    # The replacement is a new ACTIVE evidence row: the watermark moved.
    assert learning.get_evidence_watermark() == watermark_before + 1


def test_double_supersede_extends_the_chain(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    original_id = _committed_positive_claim(
        db, learning, store, fence, conversation
    )
    second = learning.supersede_claim(
        EvidenceClaimId(original_id),
        make_claim(claim_role="primary"),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(second, Ok)
    third = learning.supersede_claim(
        second.value,
        make_claim(claim_role="primary"),
        evaluator_version=EvaluatorVersion("evaluator-test-v3"),
    )
    assert isinstance(third, Ok)
    chain = learning.supersede_chain(third.value)
    assert isinstance(chain, Ok)
    assert [c.evidence_claim_id for c in chain.value] == [
        third.value,
        second.value,
        original_id,
    ]
    statuses = {c.status for c in chain.value}
    assert statuses == {"ACTIVE", "SUPERSEDED"}


def test_superseding_a_non_active_claim_is_refused(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    original_id = _committed_positive_claim(
        db, learning, store, fence, conversation
    )
    first = learning.supersede_claim(
        EvidenceClaimId(original_id),
        make_claim(claim_role="primary"),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(first, Ok)
    # The already-SUPERSEDED root cannot be superseded again.
    second = learning.supersede_claim(
        EvidenceClaimId(original_id),
        make_claim(claim_role="primary"),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(second, Err)


def test_invalidate_flips_active_claim_only(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    original_id = _committed_positive_claim(
        db, learning, store, fence, conversation
    )
    watermark_before = learning.get_evidence_watermark()
    invalidated = learning.invalidate_claim(EvidenceClaimId(original_id))
    assert isinstance(invalidated, Ok)
    row = learning.get_claim(EvidenceClaimId(original_id))
    assert isinstance(row, Ok) and row.value is not None
    assert row.value.status == "INVALIDATED"
    # Status correction adds no evidence row: no watermark move.
    assert learning.get_evidence_watermark() == watermark_before

    again = learning.invalidate_claim(EvidenceClaimId(original_id))
    assert isinstance(again, Err)

    missing = learning.invalidate_claim(EvidenceClaimId("ecl-nope"))
    assert isinstance(missing, Err)
