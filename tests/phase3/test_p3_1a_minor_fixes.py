"""VAL ⑦ — the six carried-over minor fixes from the P3-0 review.

DEC-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.58 bundled F1–F5 plus the 0002
comment cleanup into this slice; each item gets its own pin here (and the
F3 detector is proven against a multi-line literal that a substring scan
would miss).
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.learning.types import (
    AttemptOutcome,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidencePolarity,
    EvidenceQualifier,
    EvidenceStatus,
    PerformanceType,
)
from elc.platform.types import EvaluatorVersion, EvidenceGroupId, Ok, TargetId
from tests.conftest import REPO_ROOT, SRC_ROOT
from tests.phase2.conftest import commit_ok, make_claim, make_group
from tests.phase3.sql_write_scan import folded_strings, write_targets_from_source


def _claim_for_commit() -> EvidenceClaimView:
    return make_claim(
        polarity=EvidencePolarity.POSITIVE,
        performance_type=PerformanceType.RECOGNITION,
        outcome=AttemptOutcome.SUCCESS,
        qualifiers=(EvidenceQualifier.LOW_SUPPORT,),
        confidence=0.9,
    )


# ---------------------------------------------------------------------------
# F1 — evaluator_id passthrough + declared protocol scope
# ---------------------------------------------------------------------------


def test_f1_controller_passes_evaluator_id_through(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    learning: SqliteLearningStore,
    conversation,
) -> None:
    controller = LearningController(learning)
    cp0 = commit_ok(store, conversation, "cm-f1", "utterance")
    group = make_group("eg-f1", (_claim_for_commit(),), target_id="res-f1")
    committed = controller.commit_evidence_group(
        group,
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
        evaluator_id="custom-evaluator-v9",
    )
    assert isinstance(committed, Ok), committed
    row = db.execute(
        "SELECT evaluator_id, evaluator_version FROM evidence_claim"
    ).fetchone()
    assert row is not None
    assert row[0] == "custom-evaluator-v9"
    assert row[1] == "evaluator-test-v1"  # the group's version still rules


def test_f1_controller_declares_its_out_of_protocol_scope() -> None:
    from elc.learning import controller as controller_module

    doc = " ".join((controller_module.__doc__ or "").split())
    for name in (
        "supersede_claim",
        "invalidate_claim",
        "get_evidence_watermark",
    ):
        assert name in doc, f"undeclared out-of-protocol method: {name}"
    assert "NOT exposed yet" in doc
    assert "record_opportunity" in doc  # the newly exposed face is declared


# ---------------------------------------------------------------------------
# F2 — truthful fence attribution in the canonicalize docstring
# ---------------------------------------------------------------------------


def test_f2_canonicalize_docstring_drops_the_false_paradigm_claim() -> None:
    from elc.conversation.store import SqliteConversationStore

    doc = " ".join(
        (SqliteConversationStore.canonicalize_assistant_turn.__doc__ or "").split()
    )
    assert "withdrawn" in doc  # the false wording is retracted in place
    assert "combined" in doc  # the store-level + ownership fence together
    assert "weaker" in doc  # transition_turn / terminalize_turn attribution
    assert "open P3+" in doc  # the question is named, not silently closed


# ---------------------------------------------------------------------------
# F3 — the write-face scan is AST-based (multi-line literals cannot hide)
# ---------------------------------------------------------------------------


def test_f3_detector_catches_a_concatenated_write() -> None:
    source = (
        "def f(conn):\n"
        "    conn.execute(\n"
        "        'INSERT INTO '\n"
        "        'decision_cycle (decision_cycle_id)'\n"
        "        ' VALUES (?)',\n"
        "        ('x',),\n"
        "    )\n"
    )
    # The old substring probe misses it: no single line carries the verb
    # and the table name.
    assert "INSERT INTO decision_cycle" not in source
    assert write_targets_from_source(source) == {"decision_cycle"}


def test_f3_detector_folds_plus_concatenation() -> None:
    source = (
        "VERB = 'UPDATE '\n"
        "SQL = VERB + 'teaching_moment SET state_version = 2'\n"
    )
    # Only the literal parts fold; the silent part is the variable — the
    # detector reports what it can prove, never a guess.
    strings = folded_strings(source)
    assert "teaching_moment" in "".join(strings)
    assert write_targets_from_source(
        "SQL = 'DELETE FROM ' + 'gate_decision WHERE 1'\n"
    ) == {"gate_decision"}


def test_f3_detector_covers_every_p3_1a_table() -> None:
    for table in (
        "decision_cycle",
        "gate_decision",
        "gate_execution_status",
        "teaching_moment",
    ):
        source = f"SQL = 'insert into {table} (x) values (?)'\n"
        assert write_targets_from_source(source) == {table}


# ---------------------------------------------------------------------------
# F4 — the watermark gate is parameterized over invalidate / supersede
# ---------------------------------------------------------------------------


def _durable_claim_id(db: sqlite3.Connection) -> str:
    row = db.execute(
        "SELECT evidence_claim_id FROM evidence_claim"
        " ORDER BY created_at, evidence_claim_id"
    ).fetchone()
    assert row is not None
    return str(row[0])


def _guarded_commit(
    learning: SqliteLearningStore,
    store: SqliteConversationStore,
    conversation,
    client_message_id: str,
    group_id: str,
) -> None:
    cp0 = commit_ok(store, conversation, client_message_id, "utterance")
    committed = learning.commit_evidence_group(
        make_group(group_id, (_claim_for_commit(),), target_id="res-f4"),
        source_turn_id=cp0.turn_id,
        conversation_id=str(conversation),
    )
    assert isinstance(committed, Ok), committed


def test_f4_invalidate_advances_the_watermark_and_the_gate_refuses(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    learning: SqliteLearningStore,
    conversation,
) -> None:
    _guarded_commit(learning, store, conversation, "cm-f4-a", "eg-f4-a")
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-f4"), "TEXT_PRODUCTION"),
        Ok,
    )
    snapshot = learning.get_learning_snapshot()
    assert isinstance(snapshot, Ok)

    invalidated = learning.invalidate_claim(_durable_claim_id(db))  # type: ignore[arg-type]
    assert isinstance(invalidated, Ok)
    assert learning.get_evidence_watermark() == 2

    refused = learning.get_learning_snapshot()
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-f4"), "TEXT_PRODUCTION"),
        Ok,
    )
    healed = learning.get_learning_snapshot()
    assert isinstance(healed, Ok)
    assert healed.value.evidence_watermark == 2


def test_f4_supersede_advances_the_watermark_and_the_gate_refuses(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    learning: SqliteLearningStore,
    conversation,
) -> None:
    _guarded_commit(learning, store, conversation, "cm-f4-b", "eg-f4-b")
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-f4"), "TEXT_PRODUCTION"),
        Ok,
    )
    superseded = learning.supersede_claim(
        _durable_claim_id(db),  # type: ignore[arg-type]
        _claim_for_commit(),
        evaluator_version=EvaluatorVersion("evaluator-test-v2"),
    )
    assert isinstance(superseded, Ok)
    assert learning.get_evidence_watermark() == 2

    refused = learning.get_learning_snapshot()
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    stale = learning.stale_projection_targets()
    assert isinstance(stale, Ok)
    assert [(str(target), modality) for target, modality in stale.value] == [
        ("res-f4", "TEXT_PRODUCTION")
    ]
    assert isinstance(
        learning.rebuild_learner_state(TargetId("res-f4"), "TEXT_PRODUCTION"),
        Ok,
    )
    assert isinstance(learning.get_learning_snapshot(), Ok)


# ---------------------------------------------------------------------------
# F5 — the single-row read documents its exemption from the gate
# ---------------------------------------------------------------------------


def test_f5_single_row_read_carries_the_exemption_note() -> None:
    store_doc = " ".join(
        (SqliteLearningStore.get_learner_target_state.__doc__ or "").split()
    )
    assert "NOT subject to the snapshot read-time watermark gate" in store_doc
    assert "F5" in store_doc
    controller_doc = LearningController.get_learner_target_state.__doc__ or ""
    assert "gate" in controller_doc


# ---------------------------------------------------------------------------
# the 0002 comment cleanup
# ---------------------------------------------------------------------------


def test_0002_active_decision_cycle_comment_is_current() -> None:
    text = (REPO_ROOT / "migrations" / "0002_conversation_core.sql").read_text(
        encoding="utf-8"
    )
    assert "tightens in Phase 2" not in text
    assert "P3-1A" in text
    assert "migration 0007" in text


def test_src_teaching_never_writes_the_transcript_tables() -> None:
    """Epoch-fence support pin: the teaching package writes only its own
    tables (the turn/transcript stay behind the conversation store).

    Phase 3 P3-1B widens the teaching store's own write set by the two
    attempt tables (DATA_MODEL §17 — AttemptRecord / AttemptEvaluationRecord
    are Teaching-domain facts), so the pin names them explicitly: the point
    of the pin is that the *transcript* stays untouched, and a widening
    write set has to be a deliberate, reviewed edit here.
    """

    from tests.phase3.sql_write_scan import write_targets

    writes = write_targets(SRC_ROOT / "teaching" / "store.py")
    assert writes == {
        "gate_execution_status",
        "gate_decision",
        "teaching_moment",
        "generation_action_intent",
        "active_teaching_lock",
        "attempt_record",
        "attempt_evaluation_record",
    }
    assert not any(table.startswith("turn_record") for table in writes)
    assert "user_turn" not in writes
    assert "assistant_turn" not in writes


def test_evidence_group_record_fixture_shape_is_intact() -> None:
    """Guard the F-test fixtures themselves (no silent drift when the
    EvidenceGroupRecord shape changes)."""

    group = EvidenceGroupRecord(
        evidence_group_id=EvidenceGroupId("eg-shape"),
        moment_id=None,
        attempt_id=None,
        target_id=TargetId("res-shape"),
        evaluator_version=EvaluatorVersion("evaluator-test-v1"),
        claims=(),
    )
    assert group.claims == ()
    assert EvidenceStatus.ACTIVE.value == "ACTIVE"
