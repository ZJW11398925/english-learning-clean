"""P6-3 ③.1 — migration 0013: the one §9 table.

What is pinned here is exactly what the migration claims:

- the table exists with §9's nine columns **in the document's order** — the
  block is read out of docs/DATA_MODEL.md at test time (``canonical_lines``)
  and compared with ``PRAGMA table_info``, ``?`` suffixes stripped;
- the two vocabularies canonical text pins are enforced by the schema
  (``constraint_type``'s four words and ``scope``'s three, each extracted from
  the document), while the columns §9 leaves unpinned carry no CHECK beyond
  the target pair's own word list — and there is **no** UNIQUE index and no
  index at all (§9 gives the object no second key);
- the foreign key is ``turn_record(turn_id)`` and the ``active`` column is the
  0004 ``attempt_observed`` boolean form (INTEGER 0/1);
- the migration is DDL only: it creates no row, applying it on a database that
  already carries a full pre-0013 lineage changes none of it, and 0001–0012
  are byte-identical (per-file SHA-256, CRLF-normalized — the repo's Windows
  convention);
- the table is written by one *creating* module only (elc.user_config.store —
  Gate 2's elc.deletion.store clears one provenance leg and never creates or
  rewrites the row; the pin near the end of this file holds the two faces
  apart).
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
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)
from tests.phase3.sql_write_scan import write_statements, write_targets

from .conftest import canonical_lines

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0013 = "0013_planner_constraint.sql"

#: docs/DATA_MODEL.md §9's heading.
SECTION_9 = "## 9. TeachingPreference / PlannerConstraint"

#: The columns §9 spells with a ``?``: the nullable non-key columns, and the
#: whole of what may be NULL.
NULLABLE_COLUMNS = (
    "target_type",
    "target_id",
    "expires_at",
    "created_from_turn_id",
)

#: The two CHECK vocabularies §9's own text pins, and the column each guards.
PINNED_VOCABULARIES = {
    "constraint_type": (SECTION_9, 1, ("DO_NOT_AUTO_TEACH", "SUPPRESS_REVIEW",
                                       "JUST_CHAT", "MANUAL_FOCUS")),
    "scope": (SECTION_9, 2, ("THIS_SESSION", "UNTIL_DATE",
                             "UNTIL_USER_REENABLES")),
}

#: 0001–0012, SHA-256 of their **CRLF-normalized** bytes at the P6-3 base
#: commit. The normalization is the repository's own Windows convention (a
#: checkout's working tree may carry CRLF while the blob carries LF); with it,
#: a digest here equals the blob's digest, so a changed byte anywhere fails
#: this pin (the P6-1 table, re-verified when this one was written).
PRE_0013_DIGESTS = {
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
    "0012_schedule_review.sql": (
        "e0e18264bfd0d5da9adf7e1896bb34e233a92591af91b9eba837c1b67830aba1"
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
        target = post if path.name >= PRE_0013 else pre
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


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# -- ① the table and its column set ------------------------------------------


def test_0013_is_present_and_not_the_head() -> None:
    """The claim that outlives P6-3's headship: 0013 is in the lineage and
    0014 — the migration Gate 2 added — is immediately behind it, so the
    runner is still filename-ordered and 0013's effect is still in the chain.
    (The pin read ``names[-1] == SCHEMA_HEAD_FILE == PRE_0013`` while P6-3 was
    the head; the head assertion now lives with the newest slice, and this one
    asserts what remains true of 0013 rather than being deleted — since P8-3
    the head literal below is 0016, and the 0013→0014 successor pin keeps its
    own literal untouched.)

    The lineage is still contiguous, and the shared constants are still the
    ones tests/architecture/test_platform_db_infra.py holds against the real
    directory."""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert PRE_0013 in names
    assert names[names.index(PRE_0013) + 1] == "0014_deletion_tombstone.sql"
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]
    assert SCHEMA_HEAD_FILE == "0016_planning_ledger.sql"


def test_the_table_exists_with_the_canonical_column_set(
    db: sqlite3.Connection,
) -> None:
    assert "0013_planner_constraint" in migrations.applied_migrations(db)
    block = canonical_lines("DATA_MODEL.md", SECTION_9, 0)
    assert _columns(db, "planner_constraint") == [
        line.rstrip("?") for line in block
    ]


def test_the_nine_column_counts_are_the_canonical_one(db: sqlite3.Connection) -> None:
    assert len(_columns(db, "planner_constraint")) == 9


def test_the_table_lands_empty(db: sqlite3.Connection) -> None:
    """DDL only: 0013 creates no row (no backfill, no seed)."""

    assert db.execute("SELECT COUNT(*) FROM planner_constraint").fetchone() == (
        0,
    )


def test_schema_version_moves_to_fourteen(db: sqlite3.Connection) -> None:
    """This pin read "13" while 0013 was the head and now reads the newest
    migration's stamp ("14" with Gate 2's 0014_deletion_tombstone); the name
    moved with the value so the test still says what it asserts."""

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
    """0001–0012 are untouched at the *blob* level: this slice adds one file
    and edits none — 0012's header comment included (it carries a prediction
    about the ``event_type`` vocabulary that has expired; not editing it is
    the point of the pin, not an oversight)."""

    for name, digest in PRE_0013_DIGESTS.items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[:12] == list(PRE_0013_DIGESTS)


def test_only_the_user_config_store_writes_the_table() -> None:
    """Authority is structural: the §9 durable row has exactly one *creating*
    writer in the source tree (the AST write-target scan the P3/P4
    architecture pins use), and it is this context's own store.

    Gate 2 added one more module, and the two faces are asserted apart rather
    than merged: ``elc.deletion.store`` may **clear a provenance leg** (§19
    removes the turn a constraint was written from, and §9 spells
    ``created_from_turn_id?`` nullable for exactly that), and it must never
    create a constraint, rewrite its content, or touch its ``active`` flag.
    That is the one exception in the deletion face's statement classes, so it
    is **listed** rather than allowed wholesale: ``write_statements`` must
    report exactly ``("DELETE", "UPDATE")`` for this table — one delete, one
    update, no insert — and the update's shape is pinned below (Gate 2 review
    F5).
    """

    writers: dict[str, set[str]] = {}
    for path in sorted(SRC_ROOT.rglob("*.py")):
        targets = write_targets(path) & {"planner_constraint"}
        if targets:
            writers[path.relative_to(SRC_ROOT).as_posix()] = targets
    assert set(writers) == {"deletion/store.py", "user_config/store.py"}

    statements = write_statements(SRC_ROOT / "deletion" / "store.py")
    assert statements.get("planner_constraint") == ("DELETE", "UPDATE")

    source = (SRC_ROOT / "deletion" / "store.py").read_text(encoding="utf-8")
    assert source.count("UPDATE planner_constraint") == 1
    assert (
        "UPDATE planner_constraint SET created_from_turn_id = NULL" in source
    )
    # The one update moves a provenance pointer, never the user's setting.
    for column in ("active", "constraint_type", "scope", "starts_at"):
        assert f"SET {column}" not in source, column
        assert f"{column} =" not in source.split("UPDATE planner_constraint")[1]


# -- ② what the schema deliberately does (and does not) say ------------------


@pytest.mark.parametrize("column", sorted(PINNED_VOCABULARIES))
def test_the_pinned_vocabularies_are_the_document_blocks(
    db: sqlite3.Connection, column: str
) -> None:
    """Both vocabularies §9 pins, read out of the document and compared with
    the CHECK the schema carries — in the block's own order."""

    heading, block_index, expected = PINNED_VOCABULARIES[column]
    block = canonical_lines("DATA_MODEL.md", heading, block_index)
    assert block == expected
    ddl = _normalized(_table_sql(db, "planner_constraint"))
    assert "CHECK (" + column + " IN (" + ", ".join(
        f"'{word}'" for word in block
    ) + "))" in ddl


def test_the_constraint_type_check_carries_the_four_types(
    db: sqlite3.Connection,
) -> None:
    ddl = _normalized(_table_sql(db, "planner_constraint"))
    assert "constraint_type TEXT NOT NULL CHECK" in ddl


def test_the_scope_check_carries_the_three_scopes(db: sqlite3.Connection) -> None:
    ddl = _normalized(_table_sql(db, "planner_constraint"))
    assert "scope TEXT NOT NULL CHECK" in ddl


def test_the_checked_columns_are_exactly_the_pinned_ones(
    db: sqlite3.Connection,
) -> None:
    """Three CHECKs and no fourth: the two §9 vocabularies plus the target
    pair's own word list (the 0004/0005/0012 spelling). Everything §9 leaves
    unpinned — ``starts_at`` / ``expires_at`` / ``target_id`` /
    ``created_from_turn_id`` — carries no value range here."""

    assert _checked_columns(_table_sql(db, "planner_constraint")) == [
        "target_type",
        "constraint_type",
        "scope",
        "active",
    ]


def test_the_target_type_check_is_the_two_canonical_words(
    db: sqlite3.Connection,
) -> None:
    ddl = _normalized(_table_sql(db, "planner_constraint"))
    assert "CHECK (target_type IN ('RESOURCE', 'CAPABILITY'))" in ddl


def test_the_active_check_is_the_boolean_form(db: sqlite3.Connection) -> None:
    """The 0004 ``attempt_observed`` precedent: a canonical boolean column is
    INTEGER 0/1 and the schema says so."""

    ddl = _normalized(_table_sql(db, "planner_constraint"))
    assert "active INTEGER NOT NULL CHECK (active IN (0, 1))" in ddl


def test_the_unpinned_columns_carry_no_vocabulary(db: sqlite3.Connection) -> None:
    """No CHECK names them, and no timestamp format is frozen into the
    column types (both are TEXT, carried verbatim)."""

    ddl = _normalized(_table_sql(db, "planner_constraint"))
    for column in ("starts_at", "expires_at", "target_id", "created_from_turn_id"):
        assert f"{column} TEXT" in ddl, column


def test_the_optional_columns_are_the_nullable_ones(
    db: sqlite3.Connection,
) -> None:
    """Every ``?`` column is nullable and nothing else is. The primary key is
    skipped: SQLite reports a rowid table's ``TEXT PRIMARY KEY`` as nullable
    (no redundant NOT NULL) — the repo-wide convention every table here
    follows, identity being enforced by the uniqueness index."""

    info = {
        str(row[1]): (bool(row[3]), int(row[5]))
        for row in db.execute("PRAGMA table_info(planner_constraint)")
    }
    assert [
        name for name, (required, pk) in info.items() if not required and not pk
    ] == list(NULLABLE_COLUMNS)


def test_the_table_declares_no_unique_index(db: sqlite3.Connection) -> None:
    """§9 gives the object no second key: one row per ``constraint_id`` and
    nothing says a target may hold only one constraint (a user may hold
    DO_NOT_AUTO_TEACH and SUPPRESS_REVIEW on the same target at once)."""

    declared = [
        [str(info[2]) for info in db.execute(f"PRAGMA index_info({row[1]})")]
        for row in db.execute("PRAGMA index_list(planner_constraint)")
        if str(row[3]) == "u"
    ]
    assert declared == []


def test_the_table_declares_no_index_at_all(db: sqlite3.Connection) -> None:
    """No unique index, no secondary index: canonical text names none, and a
    redundant index would be a DDL object beside the canonical shape. The one
    entry a rowid table always reports is the primary key's own
    ``sqlite_autoindex_*`` (origin ``'pk'``) — the identity index, not a rule
    this migration declares (0011's test skips the same index by name)."""

    origins = {
        str(row[3])
        for row in db.execute("PRAGMA index_list(planner_constraint)")
    }
    assert origins <= {"pk"}
    assert "c" not in origins
    assert "u" not in origins


def test_the_turn_foreign_key_is_the_canonical_one(
    db: sqlite3.Connection,
) -> None:
    """§9's ``created_from_turn_id?`` is a real foreign key — the one leg this
    row has to another canonical object's identity column (0007/0012's
    spelling)."""

    references = [
        (str(row[2]), str(row[3]), str(row[4]))
        for row in db.execute("PRAGMA foreign_key_list(planner_constraint)")
    ]
    assert references == [("turn_record", "created_from_turn_id", "turn_id")]


def test_the_target_columns_name_no_foreign_table(db: sqlite3.Connection) -> None:
    """``target_id`` points at the content/curriculum side, which is not
    foreign-keyed to a table here (the 0004/0005/0012 precedent)."""

    references = {
        str(row[3])
        for row in db.execute("PRAGMA foreign_key_list(planner_constraint)")
    }
    assert "target_id" not in references
    assert "target_type" not in references


def test_the_vocabularies_are_enforced_at_the_schema_level(
    db: sqlite3.Connection,
) -> None:
    """The CHECKs are the mechanism, not decoration: a value outside either
    vocabulary is refused by sqlite itself, even if a caller bypasses the
    store's own pre-checks."""

    db.execute(
        "INSERT INTO planner_constraint (constraint_id, constraint_type,"
        " scope, starts_at, active)"
        " VALUES ('pc-1', 'DO_NOT_AUTO_TEACH', 'UNTIL_DATE',"
        " '2026-09-22T09:00:00+00:00', 1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE planner_constraint SET constraint_type = 'DO_NOT_TEACH'"
            " WHERE constraint_id = 'pc-1'"
        )
    db.rollback()


def test_the_scope_check_refuses_a_fourth_word(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO planner_constraint (constraint_id, constraint_type,"
        " scope, starts_at, active)"
        " VALUES ('pc-1', 'JUST_CHAT', 'UNTIL_DATE',"
        " '2026-09-22T09:00:00+00:00', 1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE planner_constraint SET scope = 'FOREVER'"
            " WHERE constraint_id = 'pc-1'"
        )
    db.rollback()


def test_the_active_check_refuses_a_third_value(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO planner_constraint (constraint_id, constraint_type,"
        " scope, starts_at, active)"
        " VALUES ('pc-1', 'JUST_CHAT', 'UNTIL_DATE',"
        " '2026-09-22T09:00:00+00:00', 1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE planner_constraint SET active = 2"
            " WHERE constraint_id = 'pc-1'"
        )
    db.rollback()


def test_the_target_type_check_refuses_a_third_word(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO planner_constraint (constraint_id, constraint_type,"
        " scope, starts_at, active)"
        " VALUES ('pc-1', 'JUST_CHAT', 'UNTIL_DATE',"
        " '2026-09-22T09:00:00+00:00', 1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE planner_constraint SET target_type = 'GOAL'"
            " WHERE constraint_id = 'pc-1'"
        )
    db.rollback()


def test_a_null_target_type_passes_the_check(db: sqlite3.Connection) -> None:
    """A NULL operand makes the comparison NULL, which is not a violation:
    §9's ``target_type?`` really may be absent."""

    db.execute(
        "INSERT INTO planner_constraint (constraint_id, target_type,"
        " constraint_type, scope, starts_at, active)"
        " VALUES ('pc-1', NULL, 'JUST_CHAT', 'THIS_SESSION',"
        " '2026-09-22T09:00:00+00:00', 0)"
    )
    row = db.execute(
        "SELECT target_type, active FROM planner_constraint"
    ).fetchone()
    assert row == (None, 0)
    db.rollback()


# -- ③ the migration's own guarantees ----------------------------------------


def test_the_migration_is_idempotent_on_a_current_database(
    db: sqlite3.Connection,
) -> None:
    assert migrations.apply_migrations(db) == []
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION


def test_0013_leaves_a_full_pre_0013_lineage_untouched(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn, pre)
    assert migrations.schema_version(conn) == "12"
    conn.execute(
        "INSERT INTO conversation (conversation_id, persona_id, scene_id,"
        " created_at, status, next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', NULL, NULL, 'now', 'ACTIVE', 1, 1)"
    )
    conn.execute(
        "INSERT INTO schedule_item (schedule_item_id, target_type, target_id,"
        " evidence_modality, review_state, review_urgency,"
        " next_review_window_start, next_review_window_end, spacing_stage,"
        " source_learning_watermark, version, updated_at)"
        " VALUES ('si-1', 'RESOURCE', 'res-1', 'TEXT_PRODUCTION', 'DUE',"
        " 0.75, 'now', 'later', NULL, 'wm-1', 'sv-1', 'now')"
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
        "SELECT schedule_item_id, review_state FROM schedule_item"
    ).fetchall() == [("si-1", "DUE")]
    assert conn.execute(
        "SELECT session_focus_id, starts_at FROM session_focus"
    ).fetchall() == [("sf-1", "now")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "planner_constraint" in tables
    assert not {
        name for name in tables if name.endswith(("_v12", "_v13", "_backup"))
    }
    conn.close()


def test_0013_is_ddl_only() -> None:
    """The file creates one table and stamps the version; it moves no row (no
    INSERT…SELECT, no UPDATE, no DELETE) and rebuilds nothing."""

    source = (MIGRATIONS_DIR / PRE_0013).read_text(encoding="utf-8")
    statements = [
        line.strip().upper()
        for line in source.splitlines()
        if not line.strip().startswith("--")
    ]
    body = " ".join(statements)
    for verb in (
        "INSERT INTO PLANNER_CONSTRAINT",
        "DELETE FROM",
        "DROP TABLE",
        "ALTER TABLE",
    ):
        assert verb not in body, verb
    # The only INSERTs are the two stamps (§26.1).
    assert body.count("INSERT INTO SCHEMA_META") == 2


def _header_text(source: str) -> str:
    """The file's text with comment markers and wrapping removed, so a phrase
    pin does not fail on where the header happens to break a line (the p6-1
    lesson: a scan must look for the claim, not for one editor's line
    breaks)."""

    return " ".join(source.replace("--", " ").split())


def test_the_migration_header_names_its_authority_and_its_derivations() -> None:
    """The header is where the placement (R1) and the one movable column (R6)
    are registered, so a reader of the schema meets both without leaving the
    file — and it states the 0001–0012 freeze."""

    source = (MIGRATIONS_DIR / PRE_0013).read_text(encoding="utf-8")
    flat = _header_text(source)
    for phrase in (
        "docs/DATA_MODEL.md §9",
        # INFO-1: the cited range covers the Scope block too (586 is the
        # heading, 615 the last line of its fenced list) — the earlier
        # "586–607" pointed at the column and Types blocks alone.
        "586–615",
        "DO_NOT_AUTO_TEACH",
        "UNTIL_USER_REENABLES",
        "Ownership (R1)",
        "derived placement",
        "the one column an update may move (R6)",
        "BF-03",
        "0001–0012 are byte-identical",
        "DDL + vocabulary only",
        "schema_version', '13",
    ):
        assert phrase in flat, phrase


def test_the_migration_header_keeps_the_scope_closure_a_cut_choice() -> None:
    """L-1: §9 writes ``Scope 例如``, so the three Scope words are the
    document's *example* while **closing** the set is this migration's schema
    choice — not a canonical claim, and the price of extending it is a change
    to this file's CHECK.

    The pin is two-sided on purpose: the accurate sentences must be there, and
    the flattened sentence that used to call both vocabularies "canonical text
    pinned by §9" must never come back. A future edit that re-flattens the
    distinction (or deletes the extension sentence) fails here rather than
    quietly re-advertising a claim §9 does not make.
    """

    source = (MIGRATIONS_DIR / PRE_0013).read_text(encoding="utf-8")
    flat = _header_text(source)
    for phrase in (
        "Scope 例如",
        "the set is this migration's schema choice, not a canonical claim",
        "a fourth scope word is a change to this file's CHECK",
    ):
        assert phrase in flat, phrase
    assert "Both vocabularies are canonical text pinned by" not in flat


def test_the_migration_header_says_what_it_does_not_decide() -> None:
    """No Planner reads the table in this cut: the header says so, because the
    next reader will ask."""

    source = (MIGRATIONS_DIR / PRE_0013).read_text(encoding="utf-8")
    flat = _header_text(source)
    for phrase in (
        "This migration decides nothing about the constraint's effect",
        "PlannerConstraintView in Phase 7",
        "TARGET_SUPPRESSED in Phase 8",
    ):
        assert phrase in flat, phrase
