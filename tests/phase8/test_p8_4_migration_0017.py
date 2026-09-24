"""P8-4 ① — migration 0017: the exposure event's provenance column.

What is pinned here is what the migration claims:

- **one** statement lands a column and nothing else: ``ALTER TABLE
  planning_ledger_event ADD COLUMN moment_id TEXT`` — no ``CREATE``, no
  ``DROP``, no ``UPDATE``/``DELETE``, no row touched (the "pure ALTER" claim);
- the column is the fifth one, ``TEXT``, **nullable**, with no default and no
  foreign key — and adding it moved nothing else about the table (the four
  §20 columns keep their own shapes, the CHECK keeps its five words);
- the two stamps move with the shared head (``18`` as of P9-1's 0018; the
  suite asserts the shared constant, not a literal), applying the chain is
  idempotent, and the previous head is immediately behind 0017 in filename
  order;
- ``0001–0016`` are byte-identical (per-file SHA-256, CRLF-normalized).
  0015's digest and 0013–0014's are the ones the earlier cuts recorded
  (``tests.phase8.test_p8_3_migration_0016.PRE_0016_DIGESTS`` /
  ``tests.phase8.test_p8_0_migration_0015.PRE_0015_DIGESTS`` /
  ``tests.phase6.test_p6_3_migration_0013.PRE_0013_DIGESTS``); this cut records
  **0016's** own blob, and the file lives here rather than in a later one
  because 0017 is the migration that reads it.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from elc.platform.db import migrations
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_VERSION,
)

MIGRATIONS_DIR = REPO_ROOT / "migrations"
HEAD_0017 = "0017_ledger_event_provenance.sql"
PRE_0017 = "0016_planning_ledger.sql"

#: 0016's blob, **recorded by this cut** and unchanged by it. The whole
#: ``0001–0016`` lineage is then pinned from the original records (0001–0012 in
#: tests/phase6, 0013–0014 in tests/phase8's P8-0 suite, 0015 in the P8-3
#: suite) plus this one value.
PRE_0017_DIGESTS = {
    "0016_planning_ledger.sql": (
        "25a09af9481c250aec58f98510d33be9fcca0871208975a202f4184353a34aa8"
    ),
}

#: The one statement this migration lands, verbatim (trailing ``;`` included).
THE_ALTER = "ALTER TABLE planning_ledger_event ADD COLUMN moment_id TEXT;"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _statements() -> list[str]:
    """The file's non-comment statements, each with its ``;``."""

    text = (MIGRATIONS_DIR / HEAD_0017).read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )
    return [part.strip() + ";" for part in body.split(";") if part.strip()]


def _columns(db: sqlite3.Connection) -> list[str]:
    return [
        str(row[1])
        for row in db.execute("PRAGMA table_info(planning_ledger_event)")
    ]


def _notnull(db: sqlite3.Connection) -> dict[str, int]:
    return {
        str(row[1]): int(row[3])
        for row in db.execute("PRAGMA table_info(planning_ledger_event)")
    }


def _types(db: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row[1]): str(row[2])
        for row in db.execute("PRAGMA table_info(planning_ledger_event)")
    }


# -- ① the lineage -----------------------------------------------------------


def test_0017_is_registered_and_0018_follows_it() -> None:
    """0017 is in the chain, 0016 is immediately behind it, and its successor
    is the literal the newest slice landed: P9-1's
    ``0018_delivery_records.sql``. The head assertion moved there with that
    migration (this pin read ``names[-1] == SCHEMA_HEAD_FILE == HEAD_0017``
    while 0017 was the head), and the successor is a **literal** — a
    ``SCHEMA_HEAD_FILE`` reference here would silently become false at the
    next migration (the pin's own rule, restated by the 0016 suite)."""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert MIGRATION_IDS[-1] == "0018_delivery_records"
    assert names[names.index(HEAD_0017) + 1] == "0018_delivery_records.sql"
    assert names[names.index(PRE_0017) + 1] == HEAD_0017
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]


def test_the_pre_0017_lineage_did_not_move() -> None:
    """0001–0016 are byte-identical at the blob level (CRLF-normalized)."""

    from tests.phase6.test_p6_3_migration_0013 import PRE_0013_DIGESTS
    from tests.phase8.test_p8_0_migration_0015 import PRE_0015_DIGESTS
    from tests.phase8.test_p8_3_migration_0016 import PRE_0016_DIGESTS

    recorded = {**PRE_0013_DIGESTS, **PRE_0015_DIGESTS, **PRE_0016_DIGESTS}
    recorded.update(PRE_0017_DIGESTS)
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[: len(recorded)] == list(recorded)
    for name, digest in recorded.items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name


def test_applying_the_chain_is_idempotent(db: sqlite3.Connection) -> None:
    assert migrations.apply_migrations(db) == []
    assert "0017_ledger_event_provenance" in migrations.applied_migrations(db)


def test_the_stamps_move_to_the_shared_head(db: sqlite3.Connection) -> None:
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION == "18"
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


# -- ② pure ALTER ------------------------------------------------------------


def test_the_file_is_one_alter_and_two_stamps() -> None:
    statements = _statements()
    assert len(statements) == 3
    assert statements[0] == THE_ALTER
    assert statements[1].startswith("INSERT INTO schema_meta")
    assert statements[2].startswith("INSERT INTO schema_meta")
    for statement in statements:
        upper = statement.upper()
        assert not upper.startswith("CREATE"), statement
        assert not upper.startswith("DROP"), statement
        assert not upper.startswith("UPDATE"), statement
        assert not upper.startswith("DELETE"), statement
        assert "INSERT INTO " not in statement or "schema_meta" in statement


def test_the_column_lands_on_one_more_table(db: sqlite3.Connection) -> None:
    """``moment_id`` is a column many teaching tables carry (it is their link
    to the §15 Moment); 0017 adds the event log to that set and no other table
    moves. The carrier set is pinned as the literal list, so a migration that
    quietly added the column elsewhere is RED here."""

    tables = [
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    ]
    carrying = sorted(
        table
        for table in tables
        if any(
            str(row[1]) == "moment_id"
            for row in db.execute(f"PRAGMA table_info({table})")
        )
    )
    assert carrying == [
        "active_teaching_lock",
        "attempt_evaluation_record",
        "attempt_record",
        "gate_execution_status",
        "generation_action_intent",
        "planning_ledger_event",
        "teaching_evidence_proposal",
        "teaching_moment",
    ]


def test_the_column_is_the_fifth_and_typed_text(db: sqlite3.Connection) -> None:
    assert _columns(db) == [
        "event_id",
        "ledger_key",
        "event",
        "as_of",
        "moment_id",
    ]
    assert _types(db)["moment_id"] == "TEXT"


def test_the_column_is_nullable_with_no_default(db: sqlite3.Connection) -> None:
    assert _notnull(db)["moment_id"] == 0
    row = db.execute(
        "SELECT dflt_value FROM pragma_table_info('planning_ledger_event')"
        " WHERE name = 'moment_id'"
    ).fetchone()
    assert row is not None and row[0] is None


def test_the_four_section20_columns_are_unchanged(db: sqlite3.Connection) -> None:
    notnull = _notnull(db)
    assert notnull["event_id"] == 0  # a TEXT PRIMARY KEY reports 0
    assert notnull["ledger_key"] == 1
    assert notnull["event"] == 1
    assert notnull["as_of"] == 1


def test_no_foreign_key_names_the_provenance_column(db: sqlite3.Connection) -> None:
    """The table's one foreign key is 0016's (``ledger_key`` → the row); the
    new column adds none — the header's whole argument for keeping the BF-05
    CONVERSATION walk raisable."""

    keys = [
        (str(row[2]), str(row[3]), str(row[4]))
        for row in db.execute("PRAGMA foreign_key_list(planning_ledger_event)")
    ]
    assert keys == [("planning_ledger", "ledger_key", "ledger_key")]
    assert all(column != "moment_id" for _, column, _ in keys)


def test_a_row_can_carry_no_reference(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO planning_ledger (ledger_key, ledger_key_type,"
        " teaching_exposure_counts, probe_counts, review_offers, recent_skips,"
        " version) VALUES ('res-hedge-i-think', 'TARGET', 0, 0, 0, 0, 'pl1')"
    )
    db.execute(
        "INSERT INTO planning_ledger_event (event_id, ledger_key, event, as_of)"
        " VALUES ('ev-null', 'res-hedge-i-think', 'user_skip',"
        " '2026-09-24T09:00:00+00:00')"
    )
    row = db.execute(
        "SELECT moment_id FROM planning_ledger_event WHERE event_id = 'ev-null'"
    ).fetchone()
    assert row == (None,)


def test_the_check_vocabulary_is_still_the_five_words(db: sqlite3.Connection) -> None:
    ddl = " ".join(
        str(
            db.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name ="
                " 'planning_ledger_event'"
            ).fetchone()[0]
        ).split()
    )
    assert "event TEXT NOT NULL CHECK (event IN (" in ddl
    for word in (
        "candidate_selected",
        "teaching_presented",
        "hint_presented",
        "reveal_presented",
        "user_skip",
    ):
        assert f"'{word}'" in ddl, word
    assert ddl.count("CHECK") == 1


# -- ③ the header's registered readings --------------------------------------


def _header() -> str:
    return (MIGRATIONS_DIR / HEAD_0017).read_text(encoding="utf-8")


def test_the_header_quotes_0016s_revisit_clause() -> None:
    text = _header()
    assert "Revisit: the delivery path (p8-4) records the Moment a presentation" in text
    assert "then the ref column" in text
    assert "and the conversation leg land together" in text


def test_the_header_states_both_halves_land_together() -> None:
    text = _header()
    assert "elc/deletion/types.py names planning_ledger_event in" in text
    assert "CONVERSATION_SWEPT_TABLES" in text
    assert "clears the reference" in text


def test_the_header_states_why_the_column_carries_no_foreign_key() -> None:
    text = _header()
    assert "nullable and carries no foreign key" in text
    assert "would break the CONVERSATION walk" in text
    assert "BF-05 lines 747/87" in text


def test_the_header_registers_that_the_projection_invariant_is_untouched() -> None:
    text = _header()
    assert '"row = the log\'s projection" invariant is not affected' in text
    assert "elc/planner/ledger.py" in text
    assert "pure functions of that log" in text


def test_the_header_names_the_canonical_authorities() -> None:
    text = _header()
    for citation in (
        "docs/DATA_MODEL.md §15",
        "docs/RUNTIME_ARCHITECTURE.md §20",
        "docs/DATA_MODEL.md §1.3",
        "docs/DATA_MODEL.md §27",
        "docs/DATA_MODEL.md §26.1",
    ):
        assert citation in text, citation


def test_the_header_claims_0001_to_0016_are_byte_identical() -> None:
    assert "0001–0016 are byte-identical" in _header()


def test_the_migration_file_uses_lf_line_endings() -> None:
    """Every migration is LF (the lineage's own byte discipline); this cut's
    file was re-normalized before delivery, and the claim is cheap to keep
    checkable."""

    raw = (MIGRATIONS_DIR / HEAD_0017).read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
