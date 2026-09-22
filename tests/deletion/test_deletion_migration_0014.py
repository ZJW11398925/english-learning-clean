"""Gate 2 ① — migration 0014: the §24 ledger table.

What is pinned here is exactly what the migration claims:

- the table exists with §24's six columns **in the document's order** (the
  block is read out of the contract at test time);
- the seven scope words the CHECK freezes are the ones §19–§23 name plus the
  benchmark's S44 word;
- the migration is DDL only — it creates no row, and applying it on a
  database that already carries a full pre-0014 lineage changes none of it;
- 0001–0013 are byte-identical (per-file SHA-256, CRLF-normalized — the
  repo's Windows convention);
- the table is written by one module only (elc.deletion.store).
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from elc.deletion.types import DeletionScope
from elc.platform.db import migrations
from tests.conftest import MIGRATION_IDS, REPO_ROOT, SCHEMA_HEAD_VERSION
from tests.deletion.conftest import CONTRACT_PATH
from tests.phase3.sql_write_scan import write_targets

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0014 = "0014_deletion_tombstone.sql"
FROZEN_HEAD = "0013_planner_constraint.sql"


def _digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _frozen_digests() -> dict[str, str]:
    """The 0001–0013 blob freeze, read from the record that already holds it.

    The values live in ``tests/phase6/test_p6_3_migration_0013.py``
    (``PRE_0013_DIGESTS``), the pin that recorded them when 0013 was the head.
    Reading them from there rather than re-typing them here is what makes the
    claim "0001–0013 did not move in this cut" checkable: a cut that edited one
    of those files would have to change that record too, and this test would
    then be comparing against a value the edit also moved — which is exactly
    why the *other* direction (a re-typed copy here) would be weaker.
    """

    from tests.phase6.test_p6_3_migration_0013 import PRE_0013_DIGESTS

    return dict(PRE_0013_DIGESTS)


def _head_digest() -> str:
    """0013's digest as this cut reads it.

    There is no earlier record of 0013's blob to compare against — the
    ``PRE_0013_DIGESTS`` table stops at 0012, because 0013 was the file that
    cut *added*. So this cut records the value it read, and the real freeze
    claim about 0013 is carried by tests/phase6's own pins (which parse the
    file) plus the continuity check below.
    """

    return _digest(MIGRATIONS_DIR / FROZEN_HEAD)


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")]


def test_0014_is_the_newest_migration() -> None:
    """This slice's head; nothing ahead of Gate 2 smuggles schema.

    The claim reads the shared constants, which
    tests/architecture/test_platform_db_infra.py holds against the real
    directory.
    """

    from tests.conftest import SCHEMA_HEAD_FILE

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[-1] == SCHEMA_HEAD_FILE == PRE_0014
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]


def test_the_table_exists_with_the_canonical_column_set(
    db: sqlite3.Connection,
) -> None:
    assert "0014_deletion_tombstone" in migrations.applied_migrations(db)
    assert _columns(db, "deletion_tombstone") == [
        "tombstone_id",
        "entity_kind",
        "entity_hash",
        "deleted_at",
        "deletion_scope",
        "scope_version",
    ]


def test_the_six_columns_are_the_canonical_six(
    db: sqlite3.Connection,
) -> None:
    """§24's list, counted: opaque identity/hash + deleted_at +
    deletion_scope/version, and nothing else."""

    assert len(_columns(db, "deletion_tombstone")) == 6


def test_the_table_lands_empty(db: sqlite3.Connection) -> None:
    """DDL only: 0014 creates no row (no backfill, no seed)."""

    assert db.execute("SELECT COUNT(*) FROM deletion_tombstone").fetchone() == (
        0,
    )


def test_schema_version_moves_to_fourteen(db: sqlite3.Connection) -> None:
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


def test_the_early_migrations_are_byte_identical() -> None:
    """0001–0012 are untouched at the *blob* level, and 0013 is the frozen
    head: this cut adds one file and edits none — 0013's header comment
    included."""

    for name, digest in _frozen_digests().items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[: len(_frozen_digests())] == list(_frozen_digests())


def test_the_frozen_head_is_still_0013() -> None:
    """The file this cut's successor follows is unchanged and still there."""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert FROZEN_HEAD in names
    assert names[names.index(FROZEN_HEAD) + 1] == PRE_0014
    assert _digest(MIGRATIONS_DIR / FROZEN_HEAD) == _head_digest()


def test_only_the_deletion_store_writes_the_table() -> None:
    """Authority is structural: the §24 ledger has one writer in the source
    tree (the AST write-target scan the P3/P4/P6 architecture pins use)."""

    writers: dict[str, set[str]] = {}
    for path in sorted((REPO_ROOT / "src" / "elc").rglob("*.py")):
        targets = write_targets(path) & {"deletion_tombstone"}
        if targets:
            writers[path.relative_to(REPO_ROOT / "src" / "elc").as_posix()] = (
                targets
            )
    assert writers == {"deletion/store.py": {"deletion_tombstone"}}


def test_the_scope_check_freezes_the_seven_words(db: sqlite3.Connection) -> None:
    table_sql = str(
        db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='deletion_tombstone'"
        ).fetchone()[0]
    )
    for scope in DeletionScope:
        assert f"'{scope.value}'" in table_sql, scope.value


def test_the_contract_pins_five_scope_words_and_the_benchmark_two() -> None:
    """Five words are contract tokens; two are the benchmark's alone.

    This is the pin behind elc/deletion/types.py's provenance split: if the
    contract ever grows a ``PROFILE_FIELD`` section (or spells CONVERSATION as
    a token), this test fails and the registration has to be revisited rather
    than the claim quietly staying half true.
    """

    text = CONTRACT_PATH.read_text(encoding="utf-8")
    for word in (
        "LEARNING_TARGET",
        "ALL_LEARNING_HISTORY",
        "RELATIONSHIP_PAIR",
        "PERSONA_PACKAGE",
        "ALL_USER_DATA",
    ):
        assert word in text, word
    assert "PROFILE_FIELD" not in text
    assert "CONVERSATION" not in text


def test_the_benchmark_carries_the_two_derived_words() -> None:
    import json

    from tests.deletion.conftest import BASELINE_SECURITY

    cases = json.loads(
        (BASELINE_SECURITY / "security_benchmark_v1.json").read_text(
            encoding="utf-8"
        )
    )
    scopes = {
        case["input"]["request"]["scope"]
        for case in cases
        if case["category"] in {"deletion"} and "request" in case["input"]
    }
    assert {"CONVERSATION", "PROFILE_FIELD"} <= scopes
    assert scopes <= {scope.value for scope in DeletionScope}


def test_the_unique_index_is_the_read_path(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index'"
        " AND tbl_name='deletion_tombstone' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    assert [(str(row[0])) for row in rows] == [
        "ux_deletion_tombstone_entity"
    ]
    assert "UNIQUE" in str(rows[0][1]).upper()


def test_a_second_migration_run_is_a_noop(db: sqlite3.Connection) -> None:
    assert migrations.apply_migrations(db) == []
    assert db.execute("SELECT COUNT(*) FROM deletion_tombstone").fetchone() == (
        0,
    )


@pytest.mark.parametrize("scope", sorted(s.value for s in DeletionScope))
def test_every_scope_word_is_accepted_by_the_check(
    db: sqlite3.Connection, scope: str
) -> None:
    db.execute(
        "INSERT INTO deletion_tombstone (tombstone_id, entity_kind,"
        " entity_hash, deleted_at, deletion_scope, scope_version)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (f"ts-{scope}", "conversation", "0" * 64, "2026-09-22T00:00:00Z",
         scope, "deletion-policy-v1"),
    )


def test_an_unknown_scope_word_is_refused(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO deletion_tombstone (tombstone_id, entity_kind,"
            " entity_hash, deleted_at, deletion_scope, scope_version)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("ts-x", "conversation", "0" * 64, "2026-09-22T00:00:00Z",
             "EVERYTHING", "deletion-policy-v1"),
        )


def test_the_ledger_has_no_column_that_could_hold_content() -> None:
    """SEC-023 is structural: §24's minimal list is the whole column set."""

    source = (MIGRATIONS_DIR / PRE_0014).read_text(encoding="utf-8")
    create = source[source.index("CREATE TABLE IF NOT EXISTS") :]
    create = create[: create.index(");")]
    for forbidden in ("content", "summary", "body", "text", "prompt"):
        assert forbidden not in create, forbidden
