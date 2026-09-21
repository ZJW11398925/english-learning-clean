"""P4-3 ⑥ schema — migration 0010: episode + profile/disclosure rows.

The three tables are DDL only in this slice, so what is pinned here is
exactly that:

- each table exists with its canonical column set **in canonical order** —
  docs/DATA_MODEL.md §5.3's ten episode columns, §5.1's six UserProfile
  columns and §5.1's four DisclosurePolicy columns, verbatim;
- the episode status vocabulary is the conversation's own (§3:
  ACTIVE / CLOSED) and is enforced by the schema;
- one conversation holds one episode (the Local V1 stance the projection
  declares, made structural by the unique index);
- applying the migration on a database that already carries a full Phase-4
  lineage changes none of it (the migration touches only its own tables);
- schema_version / runtime_schema_version move to 10, and 0001–0009 are
  byte-identical to what they were (the earlier tables keep their shapes).
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations
from tests.conftest import REPO_ROOT

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0010 = "0010_episode_and_user_config.sql"

EPISODE_COLUMNS = (
    "episode_id",
    "conversation_id",
    "version",
    "source_turn_sequence_start",
    "source_turn_sequence_end",
    "summary",
    "open_threads",
    "recent_events",
    "status",
    "updated_at",
)

PROFILE_COLUMNS = (
    "user_profile_id",
    "revision",
    "profile_facts",
    "preferences",
    "settings",
    "updated_at",
)

DISCLOSURE_COLUMNS = (
    "disclosure_policy_id",
    "revision",
    "rules",
    "updated_at",
)


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture()
def staged_dirs(tmp_path: Path) -> tuple[Path, Path]:
    pre = tmp_path / "pre"
    post = tmp_path / "post"
    pre.mkdir()
    post.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        target = post if path.name >= PRE_0010 else pre
        shutil.copy(path, target / path.name)
    return pre, post


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _seed_pre_0010_lineage(conn: sqlite3.Connection) -> None:
    """A durable Phase-4 lineage that 0010 must leave untouched: an epoch, a
    conversation, a turn and a relationship memory row."""

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
        " VALUES ('t1', 'c1', 1, 'i1', 'COMPLETED', 'rv', 'now', 'now', 1, 3)"
    )
    conn.execute(
        "INSERT INTO relationship_memory (relationship_memory_id, persona_id,"
        " user_id, memory_type, provenance, canonical_content, source_turn_id,"
        " status, source_turn_ids, provenance_refs, confidence,"
        " supersedes_memory_id, recorder_version, validator_version,"
        " sensitivity_class, persistence_authorization, created_at, updated_at)"
        " VALUES ('rm-1', 'persona-a', 'user-1', 'USER_STATED_FACT',"
        " 'USER_STATED_FACT', 'I live in Berlin.', NULL, 'ACTIVE', '[]',"
        " '[]', NULL, NULL, 'v0', NULL, 'PERSONAL', 'VALIDATED_DOMAIN_WRITE',"
        " 'now', 'now')"
    )
    conn.commit()


def test_0010_creates_the_three_tables_with_the_canonical_column_sets(
    db: sqlite3.Connection,
) -> None:
    assert "0010_episode_and_user_config" in migrations.applied_migrations(db)
    assert migrations.schema_version(db) == "10"
    assert (
        db.execute(
            "SELECT value FROM schema_meta WHERE key = 'runtime_schema_version'"
        ).fetchone()[0]
        == "10"
    )
    # Column order is the canonical order (§5.3 / §5.1), word for word.
    assert _columns(db, "episode") == list(EPISODE_COLUMNS)
    assert _columns(db, "user_profile") == list(PROFILE_COLUMNS)
    assert _columns(db, "disclosure_policy") == list(DISCLOSURE_COLUMNS)
    # All three land empty: 0010 is DDL only, no backfill, no seed.
    for table in ("episode", "user_profile", "disclosure_policy"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)


def test_0010_enforces_the_episode_status_vocabulary(
    db: sqlite3.Connection,
) -> None:
    """§5.3 pins the column, §3 pins the words: an episode's status is its
    conversation's own (ACTIVE / CLOSED)."""

    db.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', 'now', 'ACTIVE', 2, 2)"
    )
    db.execute(
        "INSERT INTO episode (episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at)"
        " VALUES ('ep-1', 'c1', 'epv-1', 1, 1, 'hello', '[]', '[]', 'ACTIVE',"
        " 'now')"
    )
    db.commit()
    # Both conversation words are legal.
    for good in ("CLOSED", "ACTIVE"):
        db.execute(
            "UPDATE episode SET status = ? WHERE episode_id = 'ep-1'", (good,)
        )
        db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE episode SET status = 'PAUSED' WHERE episode_id = 'ep-1'"
        )
    db.rollback()


def test_one_conversation_holds_one_episode(db: sqlite3.Connection) -> None:
    """The Local V1 stance is structural: the conversation key is unique, so
    "the episode of a conversation" is decidable."""

    db.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', 'now', 'ACTIVE', 2, 2)"
    )
    db.execute(
        "INSERT INTO episode (episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at)"
        " VALUES ('ep-1', 'c1', 'epv-1', 1, 1, 'hello', '[]', '[]', 'ACTIVE',"
        " 'now')"
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO episode (episode_id, conversation_id, version,"
            " source_turn_sequence_start, source_turn_sequence_end, summary,"
            " open_threads, recent_events, status, updated_at)"
            " VALUES ('ep-2', 'c1', 'epv-2', 2, 2, 'again', '[]', '[]',"
            " 'ACTIVE', 'now')"
        )
    db.rollback()


def test_0010_leaves_the_existing_lineage_untouched(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    assert migrations.schema_version(conn) == "9"
    _seed_pre_0010_lineage(conn)
    migrations.apply_migrations(conn, post)
    assert migrations.schema_version(conn) == "10"

    assert conn.execute(
        "SELECT relationship_memory_id, canonical_content, status"
        " FROM relationship_memory"
    ).fetchall() == [("rm-1", "I live in Berlin.", "ACTIVE")]
    assert conn.execute(
        "SELECT turn_id, status FROM turn_record"
    ).fetchall() == [("t1", "COMPLETED")]
    assert conn.execute(
        "SELECT conversation_id, status FROM conversation"
    ).fetchall() == [("c1", "ACTIVE")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    # The three new tables arrived empty, and no shadow table was left behind.
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"episode", "user_profile", "disclosure_policy"} <= tables
    assert not {name for name in tables if name.endswith(("_v9", "_v10", "_backup"))}
    conn.close()


def test_the_earlier_migrations_are_untouched() -> None:
    """0001–0009 are byte-identical: this slice adds one file and edits
    none."""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[-1] == PRE_0010
    assert len(names) == 10
    # Every earlier file keeps its own name (a rename would be a different
    # migration as far as the runner and the schema_migrations table are
    # concerned).
    assert names[:9] == [
        "0001_bootstrap.sql",
        "0002_conversation_core.sql",
        "0003_generation_provider.sql",
        "0004_learning_evidence.sql",
        "0005_learner_target_state.sql",
        "0006_decision_cycle.sql",
        "0007_teaching_lineage.sql",
        "0008_attempt_records.sql",
        "0009_relationship_contracts.sql",
    ]


def test_0010_is_idempotent(db: sqlite3.Connection) -> None:
    before = migrations.applied_migrations(db)
    assert migrations.apply_migrations(db) == []
    assert migrations.applied_migrations(db) == before
