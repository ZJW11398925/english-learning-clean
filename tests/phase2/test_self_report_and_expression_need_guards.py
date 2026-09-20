"""VAL ⑥ (part 2) — semantic guards for SelfReport / ExpressionNeed.

- LearnerSelfReport "不直接改 Ability" (DATA_MODEL §8): P2A has no
  Ability entity, so the guard is that a self report never touches the
  evidence kernel — no group, no claim, no watermark move.
- ExpressionNeed is Personal Expression Frontier, "不是 negative mastery
  evidence" (DATA_MODEL §10): its write face is fully separate from the
  evidence kernel and the negative-evidence gate never consults it.
"""

from __future__ import annotations

import sqlite3

from elc.learning import LearningCommands
from elc.learning.store import SqliteLearningStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, Ok, TargetId, UserTurnId
from tests.phase2.conftest import commit_ok


def test_store_satisfies_the_frozen_protocol_faces(
    learning: SqliteLearningStore,
) -> None:
    """The Phase 0 protocol signatures stay callable (Gate 1 face).
    P2B (TASK-…44) implemented the projection faces — the four former
    NotImplementedError pins were revised to real-callable reads (the
    P2A boundary note they carried is superseded)."""

    assert isinstance(learning, LearningCommands)
    from elc.learning.queries import LearningQueries

    assert isinstance(learning, LearningQueries)
    from elc.learning.analysis import LearningTurnAnalysis

    assert isinstance(learning, LearningTurnAnalysis)

    rebuilt = learning.rebuild_learner_state(
        TargetId("res-1"), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok) and rebuilt.value.startswith("sv-")
    state = learning.get_learner_target_state(
        TargetId("res-1"), "TEXT_PRODUCTION"
    )
    assert isinstance(state, Ok) and state.value is None
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)
    freshness = learning.get_freshness(TargetId("res-1"))
    assert isinstance(freshness, Ok)
    assert freshness.value.freshness_band == "UNKNOWN"


def test_self_report_never_enters_the_evidence_kernel(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-sr", "I already know this")
    watermark_before = learning.get_evidence_watermark()
    result = learning.record_self_report(
        "user-1",
        TargetId("res-1"),
        "CLAIMS_KNOWN",
        user_turn_id=UserTurnId(cp0.user_turn_id),
    )
    assert isinstance(result, Ok), result

    row = db.execute(
        "SELECT self_report_id, user_turn_id, target_type, target_id,"
        " report_type FROM learner_self_report"
    ).fetchone()
    assert row[1] == cp0.user_turn_id
    assert row[2] == "RESOURCE"
    assert row[3] == "res-1"
    assert row[4] == "CLAIMS_KNOWN"
    # The durable handle wraps the self_report_id (protocol return type
    # is frozen; a self report is deliberately NOT an evidence group).
    assert result.value == row[0]

    # No ability-mutation surface: nothing entered the evidence kernel.
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == watermark_before


def test_self_report_requires_turn_and_canonical_report_word(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-sr2", "typo!")
    missing_turn = learning.record_self_report(
        "user-1", TargetId("res-1"), "TYPO_DECLARED"
    )
    assert isinstance(missing_turn, Err)
    bad_word = learning.record_self_report(
        "user-1",
        TargetId("res-1"),
        "i think i know it",
        user_turn_id=UserTurnId(cp0.user_turn_id),
    )
    assert isinstance(bad_word, Err)
    assert db.execute("SELECT COUNT(*) FROM learner_self_report").fetchone()[0] == 0


def test_expression_need_write_face_and_non_negative_semantics(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-xn", "how to say this...")
    watermark_before = learning.get_evidence_watermark()
    result = learning.record_expression_need(
        source_turn_id=cp0.turn_id,
        intended_meaning="describe a sunset without repeating 'beautiful'",
        context_summary="evening chat",
        recurrence_count=1,
    )
    assert isinstance(result, Ok), result
    row = db.execute(
        "SELECT intended_meaning, recurrence_count, status"
        " FROM expression_need"
    ).fetchone()
    assert row[0] == "describe a sunset without repeating 'beautiful'"
    assert row[1] == 1
    assert row[2] == "OPEN"

    # Not negative mastery evidence: nothing entered the kernel and the
    # watermark did not move.
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == watermark_before

    # The negative-evidence gate never consults ExpressionNeed: a
    # RECOGNITION negative claim for the same target stays rejected even
    # with a dozen open expression needs.
    from elc.learning.types import (
        AttemptOutcome,
        EvidencePolarity,
        PerformanceType,
    )
    from tests.phase2.conftest import make_claim, make_group

    for index in range(3):
        learning.record_expression_need(
            source_turn_id=cp0.turn_id,
            intended_meaning=f"need {index}",
        )
    rejected = learning.commit_evidence_group(
        make_group(
            "eg-xn",
            (
                make_claim(
                    polarity=EvidencePolarity.NEGATIVE,
                    outcome=AttemptOutcome.FAILURE,
                    performance_type=PerformanceType.RECOGNITION,
                ),
            ),
        ),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(rejected, Err)
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
