"""VAL ① — six migration-0004 tables exist with the canonical column
sets, checked column-by-column against docs/DATA_MODEL.md §5/§6/§7/§8/§10
(verbatim lists maintained below; any drift in either direction fails).

Physical additions beyond the canonical sets are asserted explicitly and
each cites its justification (migration 0002 owner_epoch precedent):
- evidence_claim.attempt_id / .claim_role — DATA_MODEL §25 Evidence
  commit key members.
- evidence_watermark / evidence_commit tables — the CP1 watermark
  storage face + commit fact (RA §4 step 4 / §6 CP1; P2B LearnerTargetState
  §11 / LearningSnapshot §12 consume the watermark).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.db import connection, migrations


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")]


def _table_sql(db: sqlite3.Connection, table: str) -> str:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    assert row is not None, table
    return str(row[0])


# DATA_MODEL §5:194-232 verbatim column list.
ANALYSIS_ARTIFACT_COLUMNS = [
    "analysis_id",
    "turn_id",
    "analysis_type",
    "producer_id",
    "producer_version",
    "structured_proposal",
    "confidence",
    "status",
    "created_at",
]

# DATA_MODEL §6:411-424 verbatim.
EVIDENCE_GROUP_COLUMNS = [
    "evidence_group_id",
    "source_turn_id",
    "conversation_id",
    "persona_id",
    "teaching_moment_id",
    "evidence_modality",
    "created_at",
]

# DATA_MODEL §6:425-474 verbatim, plus §25 commit-key members
# attempt_id / claim_role.
EVIDENCE_CLAIM_COLUMNS = [
    "evidence_claim_id",
    "evidence_group_id",
    "opportunity_id",
    "target_type",
    "target_id",
    "performance_type",
    "polarity",
    "outcome",
    "qualifiers",
    "evidence_modality",
    "elicitation_type",
    "spontaneity",
    "support_level",
    "answer_exposure_state",
    "exposure_estimate_id",
    "support_attribution_certainty",
    "support_attribution_basis",
    "accuracy",
    "pragmatic_fit",
    "fluency",
    "error_attribution",
    "delay_seconds",
    "context_novelty",
    "persona_novelty",
    "evidence_modality_novelty",
    "capability_evidence_basis",
    "source_turn_id",
    "conversation_id",
    "persona_id",
    "teaching_moment_id",
    "evaluator_id",
    "evaluator_version",
    "evaluator_confidence",
    "status",
    "supersedes_claim_id",
    "created_at",
    # §25 Evidence commit key members (physical additions).
    "attempt_id",
    "claim_role",
]

# DATA_MODEL §7:520-545 verbatim.
OPPORTUNITY_COLUMNS = [
    "learning_opportunity_id",
    "source_turn_id",
    "teaching_moment_id",
    "target_type",
    "target_id",
    "opportunity_type",
    "target_explicitness",
    "attempt_observed",
    "alternative_realizations_allowed",
    "created_at",
]

# DATA_MODEL §8:548-568 verbatim.
SELF_REPORT_COLUMNS = [
    "self_report_id",
    "user_turn_id",
    "target_type",
    "target_id",
    "report_type",
    "scope",
    "created_at",
]

# DATA_MODEL §10:619-635 verbatim.
EXPRESSION_NEED_COLUMNS = [
    "expression_need_id",
    "source_turn_id",
    "intended_meaning",
    "context_summary",
    "recurrence_count",
    "personal_relevance",
    "last_seen_at",
    "resolved_resources",
    "status",
]


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("analysis_artifact", ANALYSIS_ARTIFACT_COLUMNS),
        ("evidence_group", EVIDENCE_GROUP_COLUMNS),
        ("evidence_claim", EVIDENCE_CLAIM_COLUMNS),
        ("learning_opportunity_record", OPPORTUNITY_COLUMNS),
        ("learner_self_report", SELF_REPORT_COLUMNS),
        ("expression_need", EXPRESSION_NEED_COLUMNS),
    ],
)
def test_table_columns_match_canonical(
    db: sqlite3.Connection, table: str, expected: list[str]
) -> None:
    actual = _columns(db, table)
    assert sorted(actual) == sorted(expected), (
        f"{table}: canonical-only columns missing="
        f"{sorted(set(expected) - set(actual))},"
        f" unexpected={sorted(set(actual) - set(expected))}"
    )


def test_migration_and_schema_version(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT migration_id FROM schema_migrations ORDER BY migration_id"
    ).fetchall()
    assert [row[0] for row in rows] == [
        "0001_bootstrap",
        "0002_conversation_core",
        "0003_generation_provider",
        "0004_learning_evidence",
        "0005_learner_target_state",
        # 0006_decision_cycle joins in Phase 3 P3-0 (TASK-…55 ④);
        # 0007_teaching_lineage in Phase 3 P3-1A (TASK-…2babb21e.17 ①);
        # 0008_attempt_records in Phase 3 P3-1B (TASK-…2babb21e.2 ①);
        # 0009_relationship_contracts in Phase 4 P4-0 (TASK-…5ba74efc.84 ①③);
        # 0010_episode_and_user_config in Phase 4 P4-3 (TASK-OPI-4d516e4f.19
        # ⑥ — the episode projection + user_profile / disclosure_policy);
        # 0011_goal_policy_focus in Phase 6 P6-0 (TASK-OPI-a68fd9eb.48 ③ —
        # the §5.1 goal_portfolio / teaching_policy / session_focus rows).
        "0006_decision_cycle",
        "0007_teaching_lineage",
        "0008_attempt_records",
        "0009_relationship_contracts",
        "0010_episode_and_user_config",
        "0011_goal_policy_focus",
    ]
    # The stamp is the newest migration's (this pin read "10" while
    # 0010_episode_and_user_config was the head).
    assert (
        db.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        == "11"
    )


def test_analysis_type_and_status_vocabularies(db: sqlite3.Connection) -> None:
    """DATA_MODEL §5 lists, word for word."""
    sql = _table_sql(db, "analysis_artifact")
    for word in (
        "LEARNING_EVIDENCE",
        "TEACHING_OBSERVER",
        "USER_INTENT",
        "CONVERSATION_PRIORITY",
    ):
        assert f"'{word}'" in sql, word
    for word in (
        "PRODUCED",
        "COMMIT_PENDING",
        "COMMITTED",
        "REJECTED",
        "SUPERSEDED",
    ):
        assert f"'{word}'" in sql, word


def test_evidence_claim_vocabularies(db: sqlite3.Connection) -> None:
    """DATA_MODEL §6 lists, word for word; claim status is the
    STATE_MACHINES §18 three-value list; evidence modality is the §24.14
    V1 frozen pair; claim targets are RESOURCE/CAPABILITY (DOMAIN_MODEL
    §6)."""
    sql = _table_sql(db, "evidence_claim")
    for word in (
        "RECOGNITION",
        "IMITATIVE_PRODUCTION",
        "GUIDED_PRODUCTION",
        "INDEPENDENT_PRODUCTION",
        "SPONTANEOUS_PRODUCTION",
        "SELF_REPAIR",
        "FAILED_ATTEMPT",
        "MISUSE",
    ):
        assert f"'{word}'" in sql, word
    for word in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
        assert f"'{word}'" in sql, word
    for word in ("SUCCESS", "PARTIAL", "FAILURE", "ABSTAIN"):
        assert f"'{word}'" in sql, word
    for word in ("TEXT_PRODUCTION", "TEXT_COMPREHENSION"):
        assert f"'{word}'" in sql, word
    for word in ("ACTIVE", "SUPERSEDED", "INVALIDATED"):
        assert f"'{word}'" in sql, word
    for word in ("RESOURCE", "CAPABILITY"):
        assert f"'{word}'" in sql, word


def test_python_qualifier_vocabulary_covers_canonical() -> None:
    """The §6 qualifier list is stored as JSON text (storage form is
    implementation-defined, DATA_MODEL §27); the Python vocabulary is
    pinned to the canonical seven words."""
    from elc.learning.types import EvidenceQualifier

    assert {q.value for q in EvidenceQualifier} == {
        "DELAYED",
        "CROSS_CONTEXT",
        "CROSS_PERSONA",
        "CROSS_MODALITY",
        "NOVEL_REALIZATION",
        "LOW_SUPPORT",
        "HIGH_CONTEXT_NOVELTY",
    }


def test_opportunity_vocabularies(db: sqlite3.Connection) -> None:
    """DATA_MODEL §7 lists, word for word."""
    sql = _table_sql(db, "learning_opportunity_record")
    for word in ("NATURAL", "ELICITED", "CONTROLLED_TASK", "DIRECT_TEST"):
        assert f"'{word}'" in sql, word
    for word in (
        "IMPLICIT",
        "SEMANTICALLY_CONSTRAINED",
        "FORM_CONSTRAINED",
        "EXPLICIT_TARGET",
    ):
        assert f"'{word}'" in sql, word


def test_self_report_vocabulary(db: sqlite3.Connection) -> None:
    """DATA_MODEL §8 list, word for word."""
    sql = _table_sql(db, "learner_self_report")
    for word in (
        "CLAIMS_KNOWN",
        "CLAIMS_UNKNOWN",
        "TYPO_DECLARED",
        "TOO_EASY",
        "TOO_HARD",
    ):
        assert f"'{word}'" in sql, word


def test_watermark_storage_face(db: sqlite3.Connection) -> None:
    """RA §4 step 4 / §6 CP1: the watermark is durable, per user scope,
    and monotonically constrained (>= 0)."""
    columns = _columns(db, "evidence_watermark")
    assert columns == ["user_scope_id", "watermark", "updated_at"]
    commit_columns = _columns(db, "evidence_commit")
    assert commit_columns == [
        "evidence_commit_id",
        "evidence_group_id",
        "analysis_id",
        "user_scope_id",
        "watermark_after",
        "committed_at",
    ]


def test_analysis_artifact_unique_idempotency_key(
    db: sqlite3.Connection,
) -> None:
    """RA §22/§23: re-entering analysis must replay, not double-produce —
    the (turn_id, analysis_type, producer_id) unique key backs it
    (asserted behaviorally; SQLite auto-indexes carry no SQL text)."""
    db.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c-ux', 'now', 'ACTIVE', 2, 2)"
    )
    db.execute(
        "INSERT INTO input_envelope (input_id, conversation_id,"
        " interaction_channel, raw_payload, received_at)"
        " VALUES ('i-ux', 'c-ux', 'TEXT', 'p', 'now')"
    )
    db.execute(
        "INSERT INTO turn_record (turn_id, conversation_id,"
        " turn_sequence, input_id, status, runtime_version, started_at,"
        " updated_at, owner_epoch, state_version)"
        " VALUES ('t-ux', 'c-ux', 1, 'i-ux', 'USER_COMMITTED', 'rv',"
        " 'now', 'now', 1, 1)"
    )
    insert = (
        "INSERT INTO analysis_artifact (analysis_id, turn_id,"
        " analysis_type, producer_id, producer_version,"
        " structured_proposal, confidence, status, created_at)"
        " VALUES ('an-a', 't-ux', 'LEARNING_EVIDENCE',"
        " 'deterministic-learning-evidence', 'deterministic-v1', '{}',"
        " 1.0, 'PRODUCED', 'now')"
    )
    db.execute(insert)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert.replace("'an-a'", "'an-b'", 1))

    # DATA_MODEL §6: one observable behavior → one group per
    # (source_turn_id, evidence_modality).
    db.execute(
        "INSERT INTO evidence_group (evidence_group_id, source_turn_id,"
        " conversation_id, evidence_modality, created_at)"
        " VALUES ('eg-a', 't-ux', 'c-ux', 'TEXT_PRODUCTION', 'now')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO evidence_group (evidence_group_id,"
            " source_turn_id, conversation_id, evidence_modality,"
            " created_at)"
            " VALUES ('eg-b', 't-ux', 'c-ux', 'TEXT_PRODUCTION', 'now')"
        )
