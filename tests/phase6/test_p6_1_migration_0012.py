"""P6-1 ②① — migration 0012: the two §5.2 tables.

What is pinned here is exactly what the migration claims:

- each table exists with its canonical column set **in canonical order** —
  docs/DATA_MODEL.md §5.2's twelve ScheduleItem columns and eight ReviewEvent
  columns, read out of the document at test time (never typed twice), with the
  ``?`` suffixes stripped;
- the migration is DDL + vocabulary only: it creates no row, and applying it
  on a database that already carries a full pre-0012 lineage changes none of
  it;
- the four vocabularies canonical text pins are enforced by the schema
  (``target_type`` / ``evidence_modality`` / ``review_state`` / ``engaged``)
  and the unpinned columns carry **no** CHECK at all — §5.2 pins no value
  range for ``review_urgency`` / the two window columns / ``spacing_stage`` /
  ``event_type``, and freezing an implementation word list into a canonical
  column is not this slice's to do;
- the keys: ``schedule_item`` carries the modality key's UNIQUE index (one
  current row per target × modality) and ``review_event`` carries **no**
  unique index on ``schedule_item_id`` (append-first, §1.3);
- schema_version / runtime_schema_version move to 12, 0001–0011 are
  byte-identical (per-file SHA-256, CRLF-normalized — the repo's Windows
  convention), and the two tables are written by one *creating* module only
  (elc.scheduler.store — Gate 2's elc.deletion.store removes them and never
  creates or rewrites one; the pin near the end of this file holds the two
  faces apart).
"""

from __future__ import annotations

import hashlib
import re
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
from tests.phase3.sql_write_scan import write_targets

from .conftest import canonical_lines

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0012 = "0012_schedule_review.sql"

#: docs/DATA_MODEL.md §5.2's two blocks, in canonical order.
CANONICAL_BLOCKS = {
    "schedule_item": ("### ScheduleItem", 12),
    "review_event": ("### ReviewEvent", 8),
}

#: The columns §5.2 spells with a ``?`` — plus ``review_urgency``, which the
#: canonical block names without a range and this slice carries as
#: ``float | None`` (``None`` = not configured; the R4 reading in
#: elc/scheduler/types.py).
NULLABLE_COLUMNS = {
    "schedule_item": (
        "review_urgency",
        "next_review_window_start",
        "next_review_window_end",
        "spacing_stage",
    ),
    "review_event": (
        "teaching_moment_id",
        "source_turn_id",
        "evidence_group_id",
    ),
}

#: The four CHECK vocabularies the canonical text pins, and the column each
#: one guards.
CHECKED_COLUMNS = {
    "schedule_item": ("target_type", "evidence_modality", "review_state"),
    "review_event": ("engaged",),
}

#: 0001–0011, SHA-256 of their **CRLF-normalized** bytes at the P6-1 base
#: commit. The normalization is the repository's own Windows convention (the
#: working tree of a checkout may carry CRLF while the blob carries LF); with
#: it, a digest here equals the blob's digest, so a changed byte anywhere
#: fails this pin (verified against ``git cat-file`` when the table was
#: written).
PRE_0012_DIGESTS = {
    "0001_bootstrap.sql": (
        "61640944f2af299e91728111291822b49fc07eba9622ead1bbeb0029056f2503"
    ),
    "0002_conversation_core.sql": (
        "2ac3c0c23f98495d1d3d1624f64b0a519e2f4a24aba0a73003c035155857ace5"
    ),
    "0003_generation_provider.sql": (
        "be7832032294cb721430e5aab67949f331692918766778b73ae70a4631cf3923"
    ),
    "0004_learning_evidence.sql": (
        "96fc966efb7f5eb10a02ac4a33c1176e1527ae194a6ad7d1e3a01bf1277d378c"
    ),
    "0005_learner_target_state.sql": (
        "8bfabbaf94820b6f7afd286019245d5d7df5f4cac47886a36422983e94d17a0d"
    ),
    "0006_decision_cycle.sql": (
        "f03ce722ad73d9573e5b17021d9d204f7c7121fc8253de3eb39c04c8a76dc62f"
    ),
    "0007_teaching_lineage.sql": (
        "2ebff98db85acb21a87ebfa83ba65317a1533aec75f3c98b46d971bde6da8842"
    ),
    "0008_attempt_records.sql": (
        "da14ade03cbdd22d63d2d238ee523e29e90ed16b315c167e10015454ed89d57e"
    ),
    "0009_relationship_contracts.sql": (
        "5e2e38d1cfc4fe0e338e7155eff0e069dca19520f1ef54264093603bbaf96a56"
    ),
    "0010_episode_and_user_config.sql": (
        "5267a506b1ff9f4582b0e4059474cce1580a841528a24a9737f0ebc8286e4fb8"
    ),
    "0011_goal_policy_focus.sql": (
        "f501a303d37c94b18f07f0e2b1c96381a6633c0cdfd6cafe262ef31dbfcac0ca"
    ),
}

CHECK_RE = re.compile(
    r"CHECK\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s+IN\s*\(", re.IGNORECASE
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
        target = post if path.name >= PRE_0012 else pre
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


def _normalized(ddl: str) -> str:
    return " ".join(ddl.split())


def _checked_columns(ddl: str) -> list[str]:
    return CHECK_RE.findall(ddl)


def _canonical_columns(table: str) -> list[str]:
    heading, count = CANONICAL_BLOCKS[table]
    block = canonical_lines("DATA_MODEL.md", heading, 0)
    assert len(block) == count, f"{heading} yielded {len(block)} lines"
    return [line.rstrip("?") for line in block]


def _digest(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


# -- ① the tables and their column sets --------------------------------------


def test_0012_is_present_and_not_the_head() -> None:
    """The claim that outlives P6-1's headship: 0012 is in the lineage and
    0013 — the migration P6-3 added — is immediately behind it, so the runner
    is still filename-ordered and 0012's effect is still in the chain. (The
    pin read ``names[-1] == 0012`` while P6-1 was the head; the head
    assertion now lives with the newest slice, and this one asserts what
    remains true of 0012 rather than being deleted. The successor is spelled
    as a literal on purpose: this claim is about 0012 and the file that
    follows *it*, which stayed true when Gate 2's 0014 landed.)"""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert PRE_0012 in names
    assert names[names.index(PRE_0012) + 1] == "0013_planner_constraint.sql"
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]


@pytest.mark.parametrize("table", sorted(CANONICAL_BLOCKS))
def test_the_table_exists_with_the_canonical_column_set(
    db: sqlite3.Connection, table: str
) -> None:
    assert "0012_schedule_review" in migrations.applied_migrations(db)
    assert _columns(db, table) == _canonical_columns(table)


def test_the_two_column_counts_are_the_canonical_ones(
    db: sqlite3.Connection,
) -> None:
    assert len(_columns(db, "schedule_item")) == 12
    assert len(_columns(db, "review_event")) == 8


def test_the_two_tables_land_empty(db: sqlite3.Connection) -> None:
    """DDL only: 0012 creates no row (no backfill, no seed)."""

    for table in CANONICAL_BLOCKS:
        row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert row is not None and int(row[0]) == 0


def test_schema_version_moves_to_fourteen(db: sqlite3.Connection) -> None:
    """This pin read "12" while 0012 was the head, then "13" with P6-3's
    0013_planner_constraint, and now reads the newest migration's stamp
    ("14" with Gate 2's 0014_deletion_tombstone); the name moved with the
    value so the test still says what it asserts."""

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


def test_the_earlier_migrations_are_byte_identical() -> None:
    """0001–0011 are untouched at the *blob* level: this slice adds one file
    and edits none, and a digest is what says so (the name-list pins in the
    earlier suites say the files are still there; this one says their bytes
    did not move)."""

    for name, digest in PRE_0012_DIGESTS.items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[:11] == list(PRE_0012_DIGESTS)


def test_only_the_scheduler_store_writes_the_two_tables() -> None:
    """Authority is structural: the §5.2 durable rows have exactly one
    *creating* writer in the source tree (the AST write-target scan the P3/P4
    architecture pins use), and it writes nothing else.

    Gate 2 widened the answer by one module, compensated rather than relaxed:
    ``elc.deletion.store`` deletes a target's schedule rows and a
    conversation's review events (§19/§20/§23) and must never create or
    rewrite one.
    """

    writers: dict[str, set[str]] = {}
    for path in sorted(SRC_ROOT.rglob("*.py")):
        targets = write_targets(path) & set(CANONICAL_BLOCKS)
        if targets:
            writers[path.relative_to(SRC_ROOT).as_posix()] = targets
    assert set(writers) == {
        "deletion/store.py",
        "scheduler/store.py",
    }
    assert writers["scheduler/store.py"] == set(CANONICAL_BLOCKS)
    assert writers["deletion/store.py"] == set(CANONICAL_BLOCKS)

    source = (SRC_ROOT / "deletion" / "store.py").read_text(encoding="utf-8")
    for table in CANONICAL_BLOCKS:
        assert f"DELETE FROM {table}" in source, table
        assert f"INSERT INTO {table}" not in source, table
        assert f"UPDATE {table}" not in source, table


# -- ② what the schema deliberately does (and does not) say ------------------


@pytest.mark.parametrize("table", sorted(CHECKED_COLUMNS))
def test_the_pinned_vocabularies_are_enforced_by_the_schema(
    db: sqlite3.Connection, table: str
) -> None:
    """Only the columns whose value range canonical text pins carry a CHECK."""

    assert _checked_columns(_table_sql(db, table)) == list(CHECKED_COLUMNS[table])


def test_the_review_state_check_is_the_canonical_block(db: sqlite3.Connection) -> None:
    """§5.2's four words, read out of the document: the CHECK holds exactly
    them, in exactly that order."""

    words = canonical_lines("DATA_MODEL.md", "### ScheduleItem", 1)
    assert words == ("NOT_SCHEDULED", "UPCOMING", "DUE", "OVERDUE")
    ddl = _normalized(_table_sql(db, "schedule_item"))
    assert "CHECK (review_state IN (" + ", ".join(
        f"'{word}'" for word in words
    ) + "))" in ddl


def test_the_modality_check_is_the_v1_text_pair(db: sqlite3.Connection) -> None:
    """§24.14's frozen V1 values — the mechanism face of IP §16 DoD #22: the
    two columns of this table cannot carry a voice/audio debt."""

    ddl = _normalized(_table_sql(db, "schedule_item"))
    assert "CHECK (evidence_modality IN ('TEXT_PRODUCTION'," in ddl
    assert "'TEXT_COMPREHENSION'))" in ddl
    for future in ("VOICE_PRODUCTION", "AUDIO_COMPREHENSION"):
        assert future not in ddl, future


def test_the_unpinned_columns_carry_no_vocabulary(db: sqlite3.Connection) -> None:
    """The columns §5.2 names without a value range are carried raw: no CHECK
    names them, and the implementation's own spacing words are not frozen
    into the schema (the 0002:78 / 0011:156 precedent)."""

    schedule_ddl = _normalized(_table_sql(db, "schedule_item"))
    review_ddl = _normalized(_table_sql(db, "review_event"))
    assert "review_urgency REAL" in schedule_ddl
    for column in ("next_review_window_start", "next_review_window_end",
                   "spacing_stage"):
        assert f"{column} TEXT" in schedule_ddl, column
    assert "event_type TEXT NOT NULL" in review_ddl
    for word in ("STAGE_0", "STAGE_4"):
        assert word not in schedule_ddl, word


@pytest.mark.parametrize("table", sorted(NULLABLE_COLUMNS))
def test_the_optional_columns_are_the_nullable_ones(
    db: sqlite3.Connection, table: str
) -> None:
    """Every ``?`` column (plus ``review_urgency``) is nullable and nothing
    else is. The primary key is skipped: SQLite reports a rowid table's
    ``TEXT PRIMARY KEY`` as nullable (no redundant NOT NULL) — the repo-wide
    convention every table here follows, identity being enforced by the
    uniqueness index."""

    info = {
        str(row[1]): (bool(row[3]), int(row[5]))
        for row in db.execute(f"PRAGMA table_info({table})")
    }
    assert [
        name
        for name, (required, pk) in info.items()
        if not required and not pk
    ] == list(NULLABLE_COLUMNS[table])


def _unique_indexes(db: sqlite3.Connection, table: str) -> list[list[str]]:
    """The table's **declared** UNIQUE indexes, as their column lists.

    ``origin == 'u'`` selects what this migration wrote: SQLite also mints a
    ``sqlite_autoindex_*`` of origin ``'pk'`` for a rowid table's
    ``TEXT PRIMARY KEY``, which is the identity index rather than a uniqueness
    rule this slice declares (the 0011 test skips the same index by name).
    """

    return [
        [str(info[2]) for info in db.execute(f"PRAGMA index_info({row[1]})")]
        for row in db.execute(f"PRAGMA index_list({table})")
        if str(row[3]) == "u"
    ]


def test_the_modality_key_is_unique(db: sqlite3.Connection) -> None:
    """One *current* schedule row per (target, evidence modality): the key is
    the definition of the projection, and it is the leg the learning
    projection keys on too (learner_target_state, migration 0005)."""

    assert _unique_indexes(db, "schedule_item") == [
        ["target_type", "target_id", "evidence_modality"]
    ]


def test_the_review_event_is_append_first(db: sqlite3.Connection) -> None:
    """§1.3: no unique index on ``schedule_item_id`` and none anywhere else —
    several review events for one row over time are the history."""

    assert _unique_indexes(db, "review_event") == []


def test_the_review_event_foreign_keys_are_the_four_canonical_ones(
    db: sqlite3.Connection,
) -> None:
    references = sorted(
        (str(row[2]), str(row[3]), str(row[4]))
        for row in db.execute("PRAGMA foreign_key_list(review_event)")
    )
    assert references == [
        ("evidence_group", "evidence_group_id", "evidence_group_id"),
        ("schedule_item", "schedule_item_id", "schedule_item_id"),
        ("teaching_moment", "teaching_moment_id", "moment_id"),
        ("turn_record", "source_turn_id", "turn_id"),
    ]


def test_the_schedule_item_names_no_foreign_table(db: sqlite3.Connection) -> None:
    """``target_id`` points at the content/curriculum side, which is not
    foreign-keyed to a table here (the 0004/0005 precedent: the learning
    projection is not FK-bound to the target corpus either)."""

    assert db.execute("PRAGMA foreign_key_list(schedule_item)").fetchall() == []


# -- ③ the migration's own guarantees ----------------------------------------


def test_the_migration_is_idempotent_on_a_current_database(
    db: sqlite3.Connection,
) -> None:
    assert migrations.apply_migrations(db) == []
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION


def test_0012_leaves_a_full_pre_0012_lineage_untouched(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    assert migrations.schema_version(conn) == "11"
    conn.execute(
        "INSERT INTO conversation (conversation_id, persona_id, scene_id,"
        " created_at, status, next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', NULL, NULL, 'now', 'ACTIVE', 1, 1)"
    )
    conn.execute(
        "INSERT INTO goal_portfolio (goal_portfolio_id, goal_version, goals,"
        " modality_weights, assessment_targets, register_style_goals,"
        " effective_from, updated_at)"
        " VALUES ('u1', 'gv-1', '[]', '{}', '[]', '[]', 'now', 'now')"
    )
    conn.execute(
        "INSERT INTO session_focus (session_focus_id, conversation_id,"
        " base_goal_portfolio_version, temporary_goal_weights,"
        " manual_focus_target, starts_at, expires_at)"
        " VALUES ('sf-1', 'c1', 'gv-1', '{}', NULL, 'now', NULL)"
    )
    conn.commit()
    migrations.apply_migrations(conn, post)
    assert migrations.schema_version(conn) == SCHEMA_HEAD_VERSION

    assert conn.execute(
        "SELECT conversation_id, status FROM conversation"
    ).fetchall() == [("c1", "ACTIVE")]
    assert conn.execute(
        "SELECT goal_portfolio_id, goal_version FROM goal_portfolio"
    ).fetchall() == [("u1", "gv-1")]
    assert conn.execute(
        "SELECT session_focus_id, starts_at FROM session_focus"
    ).fetchall() == [("sf-1", "now")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"schedule_item", "review_event"} <= tables
    assert not {
        name for name in tables if name.endswith(("_v11", "_v12", "_backup"))
    }
    conn.close()


def test_0012_is_ddl_only() -> None:
    """The file creates two tables and stamps the version; it moves no row
    (no INSERT…SELECT, no UPDATE, no DELETE) and does not rebuild anything."""

    source = (MIGRATIONS_DIR / PRE_0012).read_text(encoding="utf-8")
    statements = [
        line.strip().upper()
        for line in source.splitlines()
        if not line.strip().startswith("--")
    ]
    body = " ".join(statements)
    for verb in ("INSERT INTO SCHEDULE_ITEM", "INSERT INTO REVIEW_EVENT",
                 "DELETE FROM", "DROP TABLE", "ALTER TABLE"):
        assert verb not in body, verb
    # The only INSERTs are the two stamps (§26.1).
    assert body.count("INSERT INTO SCHEMA_META") == 2
