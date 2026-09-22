"""P4-0 ①③ schema — migration 0009: the two new tables + their vocabularies.

The tables are DDL-only in this slice (the runtime faces that write them are
P4-1 / P4-2), so what is pinned here is exactly that:

- both tables exist with the documented column sets, in order, and nothing
  else lands with them (no backfill, no rebuild);
- the durable CHECKs really refuse the words outside the canonical
  vocabularies (DOMAIN_MODEL §5 memory types / the provenance distinction,
  BF-05 sensitivity classes and persistence authorizations, the RA §21
  three-state proposal status) and the cross-column high-sensitivity rule
  (HIGH_SENSITIVITY ⇒ USER_EXPLICIT_CONSENT, DOMAIN_MODEL §18.1);
- the FKs of ``teaching_evidence_proposal`` bind it to the attempt,
  evaluation and moment it was produced from;
- applying 0009 on top of a database that already carries a full teaching
  lineage changes none of it (the migration touches only its own tables);
- the schema version stamp is the tree's newest (P4-3 sync: 0010 is the head,
  so the post stage — which runs 0009 *and* everything after it — ends at
  10; while 0009 was the newest this pin read 9).
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations
from tests.conftest import REPO_ROOT, SCHEMA_HEAD_VERSION

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0009 = "0009_relationship_contracts.sql"

PROPOSAL_COLUMNS = (
    "proposal_id",
    "source_attempt_id",
    "source_evaluation_id",
    "moment_id",
    "provenance",
    "payload",
    "status",
    "attempt_count",
    "created_at",
    "updated_at",
    "committed_at",
)

#: The physical column order of relationship_memory (implementation-defined,
#: DATA_MODEL §27): the *names* follow §23 verbatim (relationship_memory_id /
#: canonical_content / source_turn_ids / confidence? / status / created_at /
#: updated_at + user_id / persona_id / memory_type) and the columns marked
#: 增列 are the DEC-…5ba74efc.68-authorized additions.
MEMORY_COLUMNS = (
    "relationship_memory_id",
    "persona_id",
    "user_id",
    "memory_type",
    "provenance",
    "canonical_content",
    "source_turn_id",
    "status",
    "source_turn_ids",
    "provenance_refs",
    "confidence",
    "supersedes_memory_id",
    "recorder_version",
    "validator_version",
    "sensitivity_class",
    "persistence_authorization",
    "created_at",
    "updated_at",
)

#: docs/DOMAIN_MODEL.md §5 "Memory types", word for word.
MEMORY_TYPES = (
    "USER_STATED_FACT",
    "SHARED_EVENT",
    "PERSONA_IMPRESSION",
    "PROMISE",
    "OPEN_THREAD",
    "RUNNING_JOKE",
    "RELATIONSHIP_EVENT",
    "CONVERSATION_PREFERENCE",
)


@pytest.fixture()
def staged_dirs(tmp_path: Path) -> tuple[Path, Path]:
    pre = tmp_path / "pre"
    post = tmp_path / "post"
    pre.mkdir()
    post.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        target = post if path.name >= PRE_0009 else pre
        shutil.copy(path, target / path.name)
    return pre, post


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _seed_pre_0009_lineage(conn: sqlite3.Connection) -> None:
    """A durable teaching lineage that 0009 must leave untouched: epoch,
    conversation, turn, cycle, gate facts, moment, action and the §17
    attempt/evaluation pair the proposal FKs point at."""

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
        " 'AWAITING_USER', 'INITIAL_PROMPT', 1, 'NONE', 3, 'now')"
    )
    conn.execute(
        "INSERT INTO attempt_record (attempt_id, moment_id, attempt_index,"
        " user_turn_id, support_level_before_attempt, answer_exposure_state,"
        " exposure_estimate_id, support_attribution_certainty,"
        " support_attribution_basis, created_at)"
        " VALUES ('at-1', 'tm-1', 1, 'ut-1', 'NONE', 'NONE', NULL,"
        " 'SERVER_SENT_UNCONFIRMED', 'basis', 'now')"
    )
    conn.execute(
        "INSERT INTO attempt_evaluation_record (attempt_evaluation_id,"
        " moment_id, attempt_id, evaluator_id, evaluator_version, outcome,"
        " confidence, evidence_proposal_refs, created_at)"
        " VALUES ('ae-1', 'tm-1', 'at-1', 'attempt-evaluator-v0', 'v0',"
        " 'SUCCESS', 1.0, '[\"tep-at-1\"]', 'now')"
    )
    conn.commit()


def _insert_proposal(conn: sqlite3.Connection, **overrides: object) -> None:
    values: dict[str, object] = {
        "proposal_id": "tep-at-1",
        "source_attempt_id": "at-1",
        "source_evaluation_id": "ae-1",
        "moment_id": "tm-1",
        "provenance": "{}",
        "payload": "{}",
        "status": "PENDING",
        "attempt_count": 0,
        "created_at": "now",
        "updated_at": "now",
        "committed_at": None,
    }
    values.update(overrides)
    conn.execute(
        "INSERT INTO teaching_evidence_proposal ("
        " proposal_id, source_attempt_id, source_evaluation_id, moment_id,"
        " provenance, payload, status, attempt_count, created_at,"
        " updated_at, committed_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(values[column] for column in PROPOSAL_COLUMNS),
    )


def _insert_memory(conn: sqlite3.Connection, **overrides: object) -> None:
    values: dict[str, object] = {
        "relationship_memory_id": "rm-1",
        "persona_id": "persona-1",
        "user_id": "user-1",
        "memory_type": "USER_STATED_FACT",
        "provenance": "USER_STATED_FACT",
        "canonical_content": "I work as a nurse.",
        "source_turn_id": "t1",
        "status": "ACTIVE",
        "source_turn_ids": '["t1"]',
        "provenance_refs": '["t1"]',
        "confidence": None,
        "supersedes_memory_id": None,
        "recorder_version": "recorder-v1",
        "validator_version": "validator-v1",
        "sensitivity_class": "PERSONAL",
        "persistence_authorization": "VALIDATED_DOMAIN_WRITE",
        "created_at": "now",
        "updated_at": "now",
    }
    values.update(overrides)
    conn.execute(
        "INSERT INTO relationship_memory ("
        " relationship_memory_id, persona_id, user_id, memory_type,"
        " provenance, canonical_content, source_turn_id, status,"
        " source_turn_ids, provenance_refs, confidence,"
        " supersedes_memory_id, recorder_version, validator_version,"
        " sensitivity_class, persistence_authorization, created_at,"
        " updated_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(values[column] for column in MEMORY_COLUMNS),
    )


def test_0009_creates_the_two_tables_with_the_documented_column_sets(
    db: sqlite3.Connection,
) -> None:
    migrations.apply_migrations(db)
    assert "0009_relationship_contracts" in migrations.applied_migrations(db)
    # P6-1/P6-3/Gate-2 semantic sync: the stamp is the newest migration's, and
    # 0014_deletion_tombstone is now the head (this pin read "13" with
    # P6-3's 0013_planner_constraint, "12" with P6-1's 0012_schedule_review,
    # "11" with P6-0's 0011_goal_policy_focus, "10" while
    # 0010_episode_and_user_config was, and "9" while 0009 was).
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION
    assert (
        db.execute(
            "SELECT value FROM schema_meta WHERE key = 'runtime_schema_version'"
        ).fetchone()[0]
        == SCHEMA_HEAD_VERSION
    )
    assert _columns(db, "teaching_evidence_proposal") == list(PROPOSAL_COLUMNS)
    assert _columns(db, "relationship_memory") == list(MEMORY_COLUMNS)
    # Both tables are empty: 0009 is DDL only, no backfill, no seed.
    assert db.execute(
        "SELECT COUNT(*) FROM teaching_evidence_proposal"
    ).fetchone() == (0,)
    assert db.execute("SELECT COUNT(*) FROM relationship_memory").fetchone() == (
        0,
    )


def test_0009_enforces_the_proposal_and_memory_vocabularies(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    assert migrations.schema_version(conn) == "8"
    _seed_pre_0009_lineage(conn)
    migrations.apply_migrations(conn, post)
    # P6-1/P6-3/Gate-2 semantic sync: the post stage applies every migration
    # from 0009 on (0010_episode_and_user_config, 0011_goal_policy_focus,
    # 0012_schedule_review, 0013_planner_constraint and 0014_deletion_tombstone
    # included), so the stamp is 14.
    assert migrations.schema_version(conn) == SCHEMA_HEAD_VERSION

    # -- RA §21 proposal status: exactly three words (and a real row to
    # move through them — the FK-bound proposal of the seeded lineage).
    _insert_proposal(conn)
    conn.commit()
    for status in ("COMMITTED", "REJECTED"):
        conn.execute(
            "UPDATE teaching_evidence_proposal SET status = ?"
            " WHERE proposal_id = 'tep-at-1'",
            (status,),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE teaching_evidence_proposal SET status = ?"
                " WHERE proposal_id = 'tep-at-1'",
                (f"{status}_BAD",),
            )
        conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_proposal(conn, proposal_id="tep-neg", attempt_count=-1)
    conn.rollback()
    # The FKs bind the proposal to its durable lineage.
    for column, bad in (
        ("source_attempt_id", "at-missing"),
        ("source_evaluation_id", "ae-missing"),
        ("moment_id", "tm-missing"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_proposal(
                conn, proposal_id=f"tep-fk-{column}", **{column: bad}
            )
        conn.rollback()

    # -- DOMAIN_MODEL §5 memory types, word for word.
    for word in MEMORY_TYPES:
        _insert_memory(conn, relationship_memory_id=f"rm-{word}", memory_type=word)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_memory(
            conn, relationship_memory_id="rm-bad", memory_type="USER_FACT"
        )
    conn.rollback()
    # -- DOMAIN_MODEL §5 "Important distinction" provenance, word for word:
    # the canonical three are accepted, the Phase 0 skeleton spelling
    # (SYSTEM_INFERRED) is refused — canonical outranks it (P4-0 F-B).
    for word in ("USER_STATED_FACT", "SYSTEM_INFERRED_FACT", "PERSONA_IMPRESSION"):
        _insert_memory(
            conn, relationship_memory_id=f"rm-prov-{word}", provenance=word
        )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_memory(
            conn,
            relationship_memory_id="rm-prov-bad",
            provenance="SYSTEM_INFERRED",
        )
    conn.rollback()
    for column, word, bad in (
        ("status", "ACTIVE", "DELETED"),
        ("sensitivity_class", "PERSONAL", "PUBLIC"),
        ("persistence_authorization", "VALIDATED_DOMAIN_WRITE", "AUTO"),
    ):
        _insert_memory(conn, relationship_memory_id=f"rm-{column}", **{column: word})
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            _insert_memory(
                conn,
                relationship_memory_id=f"rm-{column}-bad",
                **{column: bad},
            )
        conn.rollback()

    # -- DOMAIN_MODEL §18.1 / BF-05: high sensitivity needs explicit consent.
    _insert_memory(
        conn,
        relationship_memory_id="rm-high-consent",
        sensitivity_class="HIGH_SENSITIVITY",
        persistence_authorization="USER_EXPLICIT_CONSENT",
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_memory(
            conn,
            relationship_memory_id="rm-high-inferred",
            sensitivity_class="HIGH_SENSITIVITY",
            persistence_authorization="VALIDATED_DOMAIN_WRITE",
        )
    conn.rollback()

    # -- confidence is optional, but its range is real.
    _insert_memory(conn, relationship_memory_id="rm-conf", confidence=0.5)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_memory(
            conn, relationship_memory_id="rm-conf-bad", confidence=1.5
        )
    conn.rollback()

    # -- append-first supersede: the FK must resolve.
    _insert_memory(
        conn,
        relationship_memory_id="rm-replacement",
        supersedes_memory_id="rm-USER_STATED_FACT",
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_memory(
            conn,
            relationship_memory_id="rm-orphan",
            supersedes_memory_id="rm-missing",
        )
    conn.rollback()
    conn.close()


def test_0009_leaves_the_existing_lineage_untouched(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    _seed_pre_0009_lineage(conn)
    migrations.apply_migrations(conn, post)

    assert conn.execute(
        "SELECT moment_id, lifecycle_state, attempt_index FROM teaching_moment"
    ).fetchall() == [("tm-1", "AWAITING_USER", 1)]
    assert conn.execute(
        "SELECT attempt_id, attempt_index, answer_exposure_state"
        " FROM attempt_record"
    ).fetchall() == [("at-1", 1, "NONE")]
    assert conn.execute(
        "SELECT attempt_evaluation_id, outcome, evidence_proposal_refs"
        " FROM attempt_evaluation_record"
    ).fetchall() == [("ae-1", "SUCCESS", '["tep-at-1"]')]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert not {name for name in tables if name.endswith(("_v9", "_backup"))}
    conn.close()


def test_0009_is_idempotent(db: sqlite3.Connection) -> None:
    migrations.apply_migrations(db)
    before = migrations.applied_migrations(db)
    assert migrations.apply_migrations(db) == []
    assert migrations.applied_migrations(db) == before
