"""VAL ① — migration 0008: the two attempt tables + the F8 vocabularies.

docs/DATA_MODEL.md §17 gives the two column sets word for word;
docs/STATE_MACHINES.md §5 gives the five evaluation outcomes, §6 the seven
completion outcomes and §7 the fourteen abort reasons. Review F8's landing
point is here: the completion / abort vocabularies must be enforced by the
*schema*, not only by the writer — before 0008 those two columns were bare
TEXT, so a typo would have been durable.

The rebuild also has to preserve history: ``teaching_moment``'s children
(``generation_action_intent`` with its own child ``provider_attempt``, and
``gate_execution_status``) are copied aside, re-created verbatim and
refilled inside the migration runner's single transaction.

The pre/post split is "everything before 0008" vs "0008 and everything
after it" (the 0007 test's filename-order rule), so the later migrations
(0009_relationship_contracts, 0010_episode_and_user_config) ride the post
stage and the version pins below name the newest migration of the tree.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations
from elc.teaching.types import (
    ABORT_REASONS,
    ATTEMPT_OUTCOMES,
    COMPLETION_OUTCOMES,
)
from tests.conftest import REPO_ROOT, SCHEMA_HEAD_VERSION

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0008 = "0008_attempt_records.sql"

ATTEMPT_COLUMNS = (
    "attempt_id",
    "moment_id",
    "attempt_index",
    "user_turn_id",
    "support_level_before_attempt",
    "answer_exposure_state",
    "exposure_estimate_id",
    "support_attribution_certainty",
    "support_attribution_basis",
    "created_at",
)

EVALUATION_COLUMNS = (
    "attempt_evaluation_id",
    "moment_id",
    "attempt_id",
    "evaluator_id",
    "evaluator_version",
    "outcome",
    "confidence",
    "evidence_proposal_refs",
    "created_at",
)


@pytest.fixture()
def staged_dirs(tmp_path: Path) -> tuple[Path, Path]:
    pre = tmp_path / "pre"
    post = tmp_path / "post"
    pre.mkdir()
    post.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        target = post if path.name >= PRE_0008 else pre
        shutil.copy(path, target / path.name)
    return pre, post


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _seed_pre_0008_data(conn: sqlite3.Connection) -> None:
    """A full pre-0008 teaching lineage: gate facts, a moment, an action and
    a provider attempt — everything the rebuild has to carry over."""

    conn.execute(
        "INSERT INTO runtime_epoch (epoch, opened_at) VALUES (1, 'now')"
    )
    conn.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', 'now', 'ACTIVE', 2, 2)"
    )
    conn.execute(
        "INSERT INTO input_envelope (input_id, conversation_id,"
        " interaction_channel, raw_payload, received_at)"
        " VALUES ('i1', 'c1', 'TEXT', 'p', 'now')"
    )
    conn.execute(
        "INSERT INTO turn_record (turn_id, conversation_id, turn_sequence,"
        " input_id, status, runtime_version, started_at, updated_at,"
        " owner_epoch, state_version)"
        " VALUES ('t1', 'c1', 1, 'i1', 'DECIDING', 'rv', 'now', 'now', 1, 3)"
    )
    conn.execute(
        "INSERT INTO user_turn (user_turn_id, turn_id, conversation_id,"
        " turn_sequence, message_sequence, input_id, interaction_channel,"
        " raw_content, created_at)"
        " VALUES ('ut-1', 't1', 'c1', 1, 1, 'i1', 'TEXT', '', 'now')"
    )
    conn.execute(
        "INSERT INTO decision_cycle (decision_cycle_id, turn_id,"
        " cycle_index, created_at) VALUES ('dcy-t1', 't1', 0, 'now')"
    )
    conn.execute(
        "UPDATE turn_record SET active_decision_cycle_id = 'dcy-t1'"
        " WHERE turn_id = 't1'"
    )
    conn.execute(
        "INSERT INTO gate_execution_status (gate_execution_status_id,"
        " decision_cycle_id, moment_id, gate_context, authorization_basis,"
        " authorization_status, status, missing_or_unknown, created_at)"
        " VALUES ('ges-1', 'dcy-t1', NULL, 'OPEN', 'DECISION_CYCLE', 'VALID',"
        " 'SUCCEEDED', '[]', 'now')"
    )
    conn.execute(
        "INSERT INTO gate_decision (gate_decision_id, decision_cycle_id,"
        " candidate_id, context, decision, reason_codes, policy_version,"
        " created_at) VALUES ('gd-1', 'dcy-t1', 'cand-1', 'OPEN', 'ALLOW',"
        " '[]', 'bf03-v1.1', 'now')"
    )
    conn.execute(
        "INSERT INTO teaching_moment (moment_id, conversation_id, persona_id,"
        " source, decision_cycle_id, candidate_id, gate_decision_id,"
        " focus_target, supporting_targets, target_mode, learning_intent,"
        " evidence_modality, lifecycle_state, presentation_phase,"
        " attempt_index, support_level, state_version, created_at)"
        " VALUES ('tm-1', 'c1', NULL, 'USER_INITIATED', 'dcy-t1', 'cand-1',"
        " 'gd-1', '{\"target_id\":\"res-1\",\"target_type\":\"RESOURCE\"}',"
        " '[]', 'RESOURCE_PRACTICE', 'ESTABLISH', 'TEXT_PRODUCTION',"
        " 'OPENING', 'INITIAL_PROMPT', 0, 'NONE', 1, 'now')"
    )
    conn.execute(
        "INSERT INTO generation_action_intent (action_id, turn_id,"
        " decision_cycle_id, moment_id, assistant_turn_id, action_type,"
        " generation_contract_id, status, attempt_count, owner_epoch,"
        " created_at) VALUES ('ga-1', 't1', 'dcy-t1', 'tm-1', 'aturn-1',"
        " 'TEACHING_OPEN', 'gc-teaching-open', 'PREPARED', 0, 1, 'now')"
    )
    conn.execute(
        "INSERT INTO provider_attempt (provider_attempt_id, action_id,"
        " attempt_no, provider_request_id, request_hash, status, result_hash,"
        " created_at, terminal_at)"
        " VALUES ('pa-1', 'ga-1', 1, NULL, 'hash', 'SUCCEEDED', 'rh', 'now',"
        " 'now')"
    )
    conn.commit()


def test_0008_creates_the_two_tables_with_the_canonical_column_sets(
    db: sqlite3.Connection,
) -> None:
    migrations.apply_migrations(db)
    assert "0008_attempt_records" in migrations.applied_migrations(db)
    # P6-1/P6-3/Gate-2 semantic sync: the version stamp is the newest
    # migration's, and 0014_deletion_tombstone is now the head (this pin read
    # "13" with P6-3's 0013_planner_constraint, "12" with P6-1's
    # 0012_schedule_review, "11" with P6-0's 0011_goal_policy_focus, "10"
    # while P4-3's 0010 was, and "9" while P4-0's 0009 was).
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION
    assert (
        db.execute(
            "SELECT value FROM schema_meta WHERE key = 'runtime_schema_version'"
        ).fetchone()[0]
        == SCHEMA_HEAD_VERSION
    )
    assert _columns(db, "attempt_record") == list(ATTEMPT_COLUMNS)
    assert _columns(db, "attempt_evaluation_record") == list(EVALUATION_COLUMNS)


def test_0008_enforces_the_canonical_vocabularies(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    assert migrations.schema_version(conn) == "7"
    _seed_pre_0008_data(conn)
    migrations.apply_migrations(conn, post)
    # P6-1/P6-3/Gate-2 semantic sync: the post stage applies every migration
    # from 0008 on, so the stamp is the newest one (0014), not P6-3's 0013,
    # P6-1's 0012, P6-0's 11 nor P4-3's 10.
    assert migrations.schema_version(conn) == SCHEMA_HEAD_VERSION

    # §5 five outcomes, word for word.
    assert ATTEMPT_OUTCOMES == (
        "SUCCESS",
        "PARTIAL",
        "FAILURE",
        "ALTERNATIVE_SUCCESS",
        "ABSTAIN",
    )
    # §6 seven completion outcomes / §7 fourteen abort reasons, word for word.
    assert COMPLETION_OUTCOMES == (
        "SUCCESS_UNSUPPORTED",
        "SUCCESS_SUPPORTED",
        "SUCCESS_ALTERNATIVE",
        "PARTIAL_PROGRESS",
        "REVEALED",
        "USER_SATISFIED",
        "NO_FURTHER_VALUE",
    )
    assert len(ABORT_REASONS) == 14
    assert ABORT_REASONS[0] == "USER_SKIP"
    assert ABORT_REASONS[-1] == "SYSTEM_RECOVERY_ABORT"

    for good, bad in (
        ("SUCCESS_UNSUPPORTED", "SUCCESS"),
        ("NO_FURTHER_VALUE", "REVEALEDD"),
    ):
        conn.execute(
            "UPDATE teaching_moment SET completion_outcome = ?"
            " WHERE moment_id = 'tm-1'",
            (good,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE teaching_moment SET completion_outcome = ?"
                " WHERE moment_id = 'tm-1'",
                (bad,),
            )
        conn.rollback()
    for reason in ("USER_SKIP", "SYSTEM_RECOVERY_ABORT"):
        conn.execute(
            "UPDATE teaching_moment SET abort_reason = ? WHERE moment_id = 'tm-1'",
            (reason,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE teaching_moment SET abort_reason = 'NOT_A_REASON'"
                " WHERE moment_id = 'tm-1'"
            )
        conn.rollback()
    conn.close()


def test_0008_preserves_the_teaching_lineage_through_the_rebuild(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    _seed_pre_0008_data(conn)
    migrations.apply_migrations(conn, post)

    assert conn.execute(
        "SELECT moment_id, lifecycle_state, support_level, attempt_index"
        " FROM teaching_moment"
    ).fetchall() == [("tm-1", "OPENING", "NONE", 0)]
    assert conn.execute(
        "SELECT action_id, moment_id, decision_cycle_id, action_type, status"
        " FROM generation_action_intent"
    ).fetchall() == [
        ("ga-1", "tm-1", "dcy-t1", "TEACHING_OPEN", "PREPARED")
    ]
    assert conn.execute(
        "SELECT provider_attempt_id, action_id, attempt_no, status"
        " FROM provider_attempt"
    ).fetchall() == [("pa-1", "ga-1", 1, "SUCCEEDED")]
    assert conn.execute(
        "SELECT gate_execution_status_id, gate_context, status"
        " FROM gate_execution_status"
    ).fetchall() == [("ges-1", "OPEN", "SUCCEEDED")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert not {name for name in tables if name.endswith(("_v8", "_backup"))}

    # The two new identity constraints are real.
    conn.execute(
        "INSERT INTO attempt_record (attempt_id, moment_id, attempt_index,"
        " user_turn_id, support_level_before_attempt, answer_exposure_state,"
        " exposure_estimate_id, support_attribution_certainty,"
        " support_attribution_basis, created_at)"
        " VALUES ('at-1', 'tm-1', 1,"
        " (SELECT user_turn_id FROM user_turn LIMIT 1), 'CONTEXT_ONLY',"
        " 'NONE', NULL, 'SERVER_SENT_UNCONFIRMED', 'basis', 'now')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        # UNIQUE(moment_id, attempt_index) is the §25 attempt identity.
        conn.execute(
            "INSERT INTO attempt_record (attempt_id, moment_id,"
            " attempt_index, user_turn_id, support_level_before_attempt,"
            " answer_exposure_state, exposure_estimate_id,"
            " support_attribution_certainty, support_attribution_basis,"
            " created_at) VALUES ('at-2', 'tm-1', 1,"
            " (SELECT user_turn_id FROM user_turn LIMIT 1), 'NONE', 'NONE',"
            " NULL, 'UNKNOWN', 'basis', 'now')"
        )
    conn.rollback()
    conn.execute(
        "INSERT INTO attempt_evaluation_record (attempt_evaluation_id,"
        " moment_id, attempt_id, evaluator_id, evaluator_version, outcome,"
        " confidence, evidence_proposal_refs, created_at)"
        " VALUES ('ae-1', 'tm-1', 'at-1', 'attempt-evaluator-v0', 'v0',"
        " 'ALTERNATIVE_SUCCESS', 1.0, '[\"eg-teaching-at-1\"]', 'now')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        # One evaluation per attempt: a re-evaluation is an explicit
        # supersede, never a silent second row.
        conn.execute(
            "INSERT INTO attempt_evaluation_record (attempt_evaluation_id,"
            " moment_id, attempt_id, evaluator_id, evaluator_version,"
            " outcome, confidence, evidence_proposal_refs, created_at)"
            " VALUES ('ae-2', 'tm-1', 'at-1', 'attempt-evaluator-v0', 'v0',"
            " 'SUCCESS', 1.0, '[]', 'now')"
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO attempt_evaluation_record (attempt_evaluation_id,"
            " moment_id, attempt_id, evaluator_id, evaluator_version,"
            " outcome, confidence, evidence_proposal_refs, created_at)"
            " VALUES ('ae-3', 'tm-1', 'at-1', 'attempt-evaluator-v0', 'v0',"
            " 'NOT_AN_OUTCOME', 1.0, '[]', 'now')"
        )
    conn.rollback()
    conn.close()


def test_0008_is_idempotent(db: sqlite3.Connection) -> None:
    migrations.apply_migrations(db)
    before = migrations.applied_migrations(db)
    assert migrations.apply_migrations(db) == []
    assert migrations.applied_migrations(db) == before
