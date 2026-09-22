"""P6-0 ③ — migration 0011: the three §5.1 tables.

What is pinned here is exactly what the migration claims:

- each table exists with its canonical column set **in canonical order** —
  docs/DATA_MODEL.md §5.1's eight portfolio columns, thirteen policy columns
  and seven focus columns, verbatim (the version columns under the qualified
  spelling elc/user_config/types.py declares);
- the migration is DDL only: it creates no row, and applying it on a database
  that already carries a full pre-0011 lineage changes none of it;
- the three tables are written by one *creating* module only —
  elc.user_config.store (Gate 2's elc.deletion.store removes these rows and
  never creates or rewrites one; the pin near the end of this file holds the
  two faces apart) —
  and the eight unpinned policy columns carry no vocabulary at all (no CHECK:
  §5.1 pins no value range, and freezing an implementation word list into a
  canonical column is not this slice's to do);
- ``session_focus`` is append-first: the conversation FK is there (the
  repo-wide convention for a canonical object that names a conversation) and
  the *unique* index 0010 put on the episode's conversation is deliberately
  **not** repeated here;
- schema_version / runtime_schema_version moved to 11 with this slice, and
  0001–0010 are byte-identical to what they were. (P6-1 later added
  0012_schedule_review, P6-3 0013_planner_constraint and Gate 2
  0014_deletion_tombstone, so the *current* head is 0014 — the assertions
  below are about 0011's own effect and its place in the lineage, and the head
  pin moved to tests/phase6/test_p6_1_migration_0012.py.)
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)
from tests.phase3.sql_write_scan import write_statements, write_targets

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0011 = "0011_goal_policy_focus.sql"

PORTFOLIO_COLUMNS = (
    "goal_portfolio_id",
    "goal_version",
    "goals",
    "modality_weights",
    "assessment_targets",
    "register_style_goals",
    "effective_from",
    "updated_at",
)

POLICY_COLUMNS = (
    "teaching_policy_profile_id",
    "policy_version",
    "mode",
    "teaching_frequency",
    "interruption_budget",
    "curriculum_initiative",
    "correction_strictness",
    "hint_policy",
    "assessment_visibility",
    "practice_density",
    "persona_freedom",
    "effective_from",
    "updated_at",
)

FOCUS_COLUMNS = (
    "session_focus_id",
    "conversation_id",
    "base_goal_portfolio_version",
    "temporary_goal_weights",
    "manual_focus_target",
    "starts_at",
    "expires_at",
)

#: The eight §5.1 policy columns whose value range the canonical set does not
#: pin — the columns the schema must leave bare.
UNPINNED_POLICY_COLUMNS = (
    "mode",
    "interruption_budget",
    "curriculum_initiative",
    "correction_strictness",
    "hint_policy",
    "assessment_visibility",
    "practice_density",
    "persona_freedom",
)

TABLE_COLUMNS = {
    "goal_portfolio": PORTFOLIO_COLUMNS,
    "teaching_policy": POLICY_COLUMNS,
    "session_focus": FOCUS_COLUMNS,
}


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
        target = post if path.name >= PRE_0011 else pre
        shutil.copy(path, target / path.name)
    return pre, post


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")]


def _table_sql(db: sqlite3.Connection, table: str) -> str:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    assert row is not None, f"table {table} is missing"
    return str(row[0])


# -- ① the tables and their column sets --------------------------------------


def test_0011_is_present_and_not_the_head() -> None:
    """This slice's own claim, restated for the world P6-1 made: 0011 is in
    the lineage and 0012 — the migration P6-1 added — is immediately behind
    it, so the runner is still filename-ordered and 0011's effect is still in
    the chain. (The pin read ``names[-1] == 0011`` while P6-0 was the head;
    the head assertion now lives in tests/phase6/test_p6_1_migration_0012.py,
    and this one asserts what remains true of 0011 rather than being
    deleted.)"""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert PRE_0011 in names
    assert names[names.index(PRE_0011) + 1] == "0012_schedule_review.sql"
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]


@pytest.mark.parametrize("table", sorted(TABLE_COLUMNS))
def test_the_table_exists_with_the_canonical_column_set(
    db: sqlite3.Connection, table: str
) -> None:
    assert "0011_goal_policy_focus" in migrations.applied_migrations(db)
    assert _columns(db, table) == list(TABLE_COLUMNS[table])


def test_the_three_tables_land_empty(db: sqlite3.Connection) -> None:
    """DDL only: 0011 creates no row (no backfill, no seed)."""

    for table in TABLE_COLUMNS:
        row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert row is not None and int(row[0]) == 0


def test_schema_version_moves_to_fourteen(db: sqlite3.Connection) -> None:
    """The stamp is the newest migration's — this pin read "11" while 0011
    was the head, then "12" with P6-1's 0012_schedule_review, "13" with P6-3's
    0013_planner_constraint, and now "14" with Gate 2's
    0014_deletion_tombstone (the same 1:1 move every version pin in this
    repository makes; the name moved with the value so the test still says
    what it asserts)."""

    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION
    stamps = dict(
        db.execute(
            "SELECT key, value FROM schema_meta WHERE key IN"
            " ('schema_version', 'runtime_schema_version')"
        ).fetchall()
    )
    assert stamps == {
        "schema_version": SCHEMA_HEAD_VERSION,
        "runtime_schema_version": SCHEMA_HEAD_VERSION,
    }


def test_the_earlier_migrations_are_untouched() -> None:
    """0001–0010 are byte-identical: this slice adds one file and edits none
    (the version pin above is what a moved migration would contradict)."""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[:10] == [
        "0001_bootstrap.sql",
        "0002_conversation_core.sql",
        "0003_generation_provider.sql",
        "0004_learning_evidence.sql",
        "0005_learner_target_state.sql",
        "0006_decision_cycle.sql",
        "0007_teaching_lineage.sql",
        "0008_attempt_records.sql",
        "0009_relationship_contracts.sql",
        "0010_episode_and_user_config.sql",
    ]
    # The 0010 tables keep their shapes verbatim (the §5.1 profile/disclosure
    # column sets and the §5.3 episode set), so the new tables arrived
    # beside them rather than through them.
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    assert _columns(conn, "episode") == [
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
    ]
    assert _columns(conn, "user_profile") == [
        "user_profile_id",
        "revision",
        "profile_facts",
        "preferences",
        "settings",
        "updated_at",
    ]
    assert _columns(conn, "disclosure_policy") == [
        "disclosure_policy_id",
        "revision",
        "rules",
        "updated_at",
    ]
    conn.close()


# -- ② what the schema deliberately does not say -----------------------------


def test_the_unpinned_policy_columns_carry_no_vocabulary(
    db: sqlite3.Connection,
) -> None:
    """No CHECK anywhere on teaching_policy: §5.1 pins no value range for any
    of its columns, and the one word list this repo declares
    (TeachingFrequency) is explicitly an implementation declaration — putting
    it in the schema would freeze it there."""

    ddl = _table_sql(db, "teaching_policy")
    assert "CHECK" not in ddl
    for column in UNPINNED_POLICY_COLUMNS:
        assert column in _columns(db, "teaching_policy")


def test_the_version_columns_are_not_null_and_the_optional_ones_are(
    db: sqlite3.Connection,
) -> None:
    not_null = {
        str(row[1]): bool(row[3])
        for row in db.execute("PRAGMA table_info(goal_portfolio)")
    }
    assert not_null["goal_version"] is True
    assert not_null["effective_from"] is True
    policy = {
        str(row[1]): bool(row[3])
        for row in db.execute("PRAGMA table_info(teaching_policy)")
    }
    assert policy["policy_version"] is True
    assert policy["teaching_frequency"] is True
    for column in UNPINNED_POLICY_COLUMNS:
        assert policy[column] is False, column
    focus = {
        str(row[1]): (bool(row[3]), int(row[5]))
        for row in db.execute("PRAGMA table_info(session_focus)")
    }
    # §5.1's two ``?`` columns are the nullable ones (an open-ended window,
    # no manual focus) — and nothing else in the focus row is. The primary
    # key is skipped: SQLite reports a rowid table's ``TEXT PRIMARY KEY`` as
    # nullable (no redundant NOT NULL), the repo-wide convention every table
    # here follows; identity is enforced by the uniqueness index.
    assert focus["manual_focus_target"][0] is False
    assert focus["expires_at"][0] is False
    assert [
        name for name, (required, pk) in focus.items() if not required and not pk
    ] == ["manual_focus_target", "expires_at"]


def test_the_focus_conversation_is_foreign_keyed_and_not_unique(
    db: sqlite3.Connection,
) -> None:
    """The FK follows 0004/0008/0010 (a canonical object that names a
    conversation points at the conversation table); the unique index 0010 put
    on the episode is deliberately absent here — several focuses for one
    conversation over time are the append-first history §1.3 asks to keep."""

    references = [
        (str(row[2]), str(row[3]))
        for row in db.execute("PRAGMA foreign_key_list(session_focus)")
    ]
    assert references == [("conversation", "conversation_id")]
    conversation_unique = [
        str(row[1])
        for row in db.execute("PRAGMA index_list(session_focus)")
        if int(row[2]) == 1
        and [
            str(info[2])
            for info in db.execute(f"PRAGMA index_info({row[1]})")
        ]
        == ["conversation_id"]
    ]
    assert conversation_unique == []
    episode_unique = [
        str(row[1])
        for row in db.execute("PRAGMA index_list(episode)")
        if int(row[2]) == 1
        and [
            str(info[2])
            for info in db.execute(f"PRAGMA index_info({row[1]})")
        ]
        == ["conversation_id"]
    ]
    assert episode_unique == ["idx_episode_conversation"]


# -- ③ the migration's own guarantees ----------------------------------------


def test_the_migration_is_idempotent_on_a_current_database(
    db: sqlite3.Connection,
) -> None:
    assert migrations.apply_migrations(db) == []
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION


def test_0011_leaves_a_full_pre_0011_lineage_untouched(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    assert migrations.schema_version(conn) == "10"
    conn.execute(
        "INSERT INTO conversation (conversation_id, persona_id, scene_id,"
        " created_at, status, next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', NULL, NULL, 'now', 'ACTIVE', 1, 1)"
    )
    conn.execute(
        "INSERT INTO user_profile (user_profile_id, revision, profile_facts,"
        " preferences, settings, updated_at)"
        " VALUES ('u1', 'rev-1', '[]', '[]', '[]', 'now')"
    )
    conn.execute(
        "INSERT INTO episode (episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at)"
        " VALUES ('ep-1', 'c1', 'epv-1', 1, 1, 'hello', '[]', '[]',"
        " 'ACTIVE', 'now')"
    )
    conn.commit()
    migrations.apply_migrations(conn, post)
    assert migrations.schema_version(conn) == SCHEMA_HEAD_VERSION

    assert conn.execute(
        "SELECT conversation_id, status FROM conversation"
    ).fetchall() == [("c1", "ACTIVE")]
    assert conn.execute(
        "SELECT user_profile_id, revision FROM user_profile"
    ).fetchall() == [("u1", "rev-1")]
    assert conn.execute(
        "SELECT episode_id, summary FROM episode"
    ).fetchall() == [("ep-1", "hello")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"goal_portfolio", "teaching_policy", "session_focus"} <= tables
    assert not {
        name for name in tables if name.endswith(("_v10", "_v11", "_backup"))
    }
    conn.close()


def test_only_the_user_config_store_writes_the_three_tables() -> None:
    """Authority is structural: the P6-0 durable rows have exactly one
    *creating* writer in the source tree (the AST write-target scan the
    P3/P4 architecture pins use), and it writes nothing else.

    Gate 2 widened the scan's answer by one module, and the widening is
    compensated rather than relaxed: ``elc.deletion.store`` removes these rows
    (a conversation's closure, an ALL_USER_DATA sweep) and must never create
    or rewrite one. The deletion face is therefore asserted to carry exactly
    the statement class ``("DELETE",)`` for each table, read off the AST
    (``write_statements``) rather than by substring, so a folded statement
    and a minting deletion store are both caught here (Gate 2 review F5).
    """

    writers: dict[str, set[str]] = {}
    for path in sorted(SRC_ROOT.rglob("*.py")):
        targets = write_targets(path) & set(TABLE_COLUMNS)
        if targets:
            writers[path.relative_to(SRC_ROOT).as_posix()] = targets
    assert set(writers) == {
        "deletion/store.py",
        "user_config/store.py",
    }
    assert writers["user_config/store.py"] == set(TABLE_COLUMNS)
    assert writers["deletion/store.py"] == set(TABLE_COLUMNS)

    statements = write_statements(SRC_ROOT / "deletion" / "store.py")
    for table in TABLE_COLUMNS:
        assert statements.get(table) == ("DELETE",), table
