"""P8-0 ① — migration 0015: the four §14 planner records.

What is pinned here is exactly what the migration claims:

- the four tables exist with §14's columns **in the document's order** (each
  block is read out of docs/DATA_MODEL.md at test time; the two blocks that
  interleave their vocabulary with the column list are filtered explicitly,
  and the filter itself is pinned);
- the three CHECK vocabularies are the document's words, verbatim — and the
  schema **refuses** a word outside them (a decision word offered as an
  ``outcome`` is the sharpest case: §14 line 889 in DDL form);
- the foreign keys are the ones the header states, and
  ``decision_cycle.planner_decision_id`` is still plain data (no FK, same
  column);
- the migration is DDL only — it creates no row, and applying it leaves
  ``0001–0014`` byte-identical (per-file SHA-256, CRLF-normalized);
- applying the chain is idempotent and the stamps move to the shared head.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import migrations
from elc.platform.types import (
    PlannerDecisionOutcome,
    PlannerExecutionStatusValue,
    RuntimeDecisionOutcomeValue,
)
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.phase8.conftest import (
    canonical_blocks_verbatim,
    columns_and_vocabulary,
)

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0015 = "0015_planner_records.sql"

#: The four §14 headings this migration turns into tables, and the table each
#: one became.
SECTION_TABLES = {
    "### PlannerEvaluation": "planner_evaluation",
    "### PlannerDecision": "planner_decision",
    "### PlannerExecutionStatus": "planner_execution_status",
    "### RuntimeDecisionOutcome": "runtime_decision_outcome",
}

#: 0013 and 0014's blobs, **recorded by this cut** and unchanged by it — the
#: 0001–0012 half is read from tests/phase6's ``PRE_0013_DIGESTS`` table (the
#: record that already holds it), so the whole 0001–0014 lineage is pinned
#: from the original record plus these two values.
PRE_0015_DIGESTS = {
    "0013_planner_constraint.sql": (
        "067343f97cc49aa699def0c84b9323cdfce698ccbfadffebe437c69f5009eb62"
    ),
    "0014_deletion_tombstone.sql": (
        "f1dc1594be3ec1a1fe3c5df7c2c025d906b90c3e2f04312debeb2982420c0237"
    ),
}

STATUS_WORDS = ("SUCCEEDED", "DEGRADED", "FAILED", "UNAVAILABLE")
OUTCOME_WORDS = ("NORMAL", "DEGRADED_NO_AUTOMATIC_TEACHING")
DECISION_WORDS = ("SELECT", "NO_TARGET")


def _digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")]


def _notnull(db: sqlite3.Connection, table: str) -> dict[str, int]:
    return {
        str(row[1]): int(row[3])
        for row in db.execute(f"PRAGMA table_info({table})")
    }


def _block(heading: str, block: int = 0) -> tuple[str, ...]:
    return canonical_blocks_verbatim("DATA_MODEL.md", heading)[block]


def _column_name(line: str) -> str:
    """§14's spelling → the durable column name.

    §14 marks an optional column with a trailing ``?`` and a list column with
    a trailing ``[]`` (``frontier_candidate_ids[]``, ``ranked_candidate_ids[]``,
    ``reason_codes[]``). Both are the document's markers, not part of a name a
    table can carry, so both are stripped — and the strip itself is pinned
    below, because a reader that quietly renamed a column would otherwise pass.
    """

    return line.rstrip("?").removesuffix("[]")


def _parents(db: sqlite3.Connection, table: str) -> list[tuple[str, str, str]]:
    return [
        (str(row[3]), str(row[2]), str(row[4]))
        for row in db.execute(f"PRAGMA foreign_key_list({table})")
    ]


# -- ① the lineage -----------------------------------------------------------


def test_0015_is_registered_and_0014s_successor() -> None:
    """This slice's lineage, registered in the shared constants (which
    tests/architecture/test_platform_db_infra.py holds against the real
    directory), and the literal successor relation to 0014.

    P8-3 moved the *head* off 0015 (0016_planning_ledger), so the two
    assertions that named 0015 the newest migration now read the shared
    constants instead of a literal; the successor relation to 0014 is
    unchanged and is still pinned literally."""

    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[-1] == SCHEMA_HEAD_FILE
    assert names[names.index("0014_deletion_tombstone.sql") + 1] == PRE_0015
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]
    assert "0015_planner_records" in MIGRATION_IDS


def test_the_pre_0015_lineage_did_not_move() -> None:
    """0001–0014 are byte-identical at the *blob* level (CRLF-normalized).

    0001–0012 are read from the record tests/phase6 holds; 0013 and 0014 are
    the two values this cut records (0013 had no literal anywhere, and 0014
    was that cut's own file). A cut that edited one of them would move both
    the file and this table — which is why the other direction (re-typed
    copies) would be the weaker pin.
    """

    from tests.phase6.test_p6_3_migration_0013 import PRE_0013_DIGESTS

    for name, digest in {**PRE_0013_DIGESTS, **PRE_0015_DIGESTS}.items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[: len(PRE_0013_DIGESTS) + len(PRE_0015_DIGESTS)] == [
        *PRE_0013_DIGESTS,
        *PRE_0015_DIGESTS,
    ]


def test_applying_the_chain_is_idempotent(db: sqlite3.Connection) -> None:
    assert migrations.apply_migrations(db) == []
    assert "0015_planner_records" in migrations.applied_migrations(db)


def test_schema_version_moves_to_the_head(db: sqlite3.Connection) -> None:
    """The stamp is the head's — the shared constant, which the infra pin
    holds against the newest file (P8-3: the head literal moved to 0016)."""

    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION
    assert SCHEMA_HEAD_VERSION == SCHEMA_HEAD_FILE[:4].lstrip("0")
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


# -- ② the columns -----------------------------------------------------------


@pytest.mark.parametrize("heading,table", sorted(SECTION_TABLES.items()))
def test_the_table_exists_with_the_canonical_column_set(
    db: sqlite3.Connection, heading: str, table: str
) -> None:
    """§14's block, read out of the document and compared positionally.

    The ``?``-suffixed names are compared with the marker stripped: the
    marker is §14's, the column name is what a table carries.
    """

    columns, _vocabulary = columns_and_vocabulary(_block(heading))
    assert _columns(db, table) == [_column_name(line) for line in columns]


def test_the_two_column_markers_are_stripped_and_the_strip_is_pinned() -> None:
    """The ``?`` / ``[]`` strips are this suite's spelling rule, asserted
    directly and held against the document: three list columns carry ``[]``
    (§14's three bracketed names) and ``factor_trace`` — which §14 writes
    without brackets — does not."""

    assert _column_name("error_code?") == "error_code"
    assert _column_name("frontier_candidate_ids[]") == (
        "frontier_candidate_ids"
    )
    assert _column_name("factor_trace") == "factor_trace"
    bracketed = {
        _column_name(line)
        for heading in SECTION_TABLES
        for line in columns_and_vocabulary(_block(heading))[0]
        if line.endswith("[]")
    }
    assert bracketed == {
        "frontier_candidate_ids",
        "ranked_candidate_ids",
        "reason_codes",
    }


@pytest.mark.parametrize("heading,table", sorted(SECTION_TABLES.items()))
def test_the_optional_columns_are_the_ones_the_document_marks_optional(
    db: sqlite3.Connection, heading: str, table: str
) -> None:
    """Every ``?`` is nullable and every other non-key column is NOT NULL.

    (A ``TEXT PRIMARY KEY`` column in a rowid table reports ``notnull=0``
    whatever the DDL says — SQLite's own quirk — so the key column is read
    through ``PRAGMA table_info``'s ``pk`` flag instead: the two keys are
    checked to be keys here, and their nullability is SQLite's business.)
    """

    columns, _vocabulary = columns_and_vocabulary(_block(heading))
    notnull = _notnull(db, table)
    primary = {
        str(row[1])
        for row in db.execute(f"PRAGMA table_info({table})")
        if int(row[5]) > 0
    }
    assert primary, table
    for line in columns:
        name = _column_name(line)
        if name in primary:
            continue
        expected = 0 if line.endswith("?") else 1
        assert notnull[name] == expected, f"{table}.{name}"


def test_the_decision_block_vocabulary_is_the_documents_two_words() -> None:
    block = _block("### PlannerDecision", 1)
    assert tuple(block) == DECISION_WORDS
    assert tuple(
        member.value for member in PlannerDecisionOutcome
    ) == DECISION_WORDS


def test_the_column_vocabulary_filter_is_pinned_for_the_status_block() -> None:
    """§14 interleaves the status words with the column list; the filter that
    separates them is asserted, not assumed.

    If the document indented a column (or flushed a word), this test fails
    here rather than producing a plausible-looking column list somewhere
    else — which is the whole reason this suite re-declares the reader.
    """

    columns, vocabulary = columns_and_vocabulary(
        _block("### PlannerExecutionStatus")
    )
    assert columns == ("decision_cycle_id", "status", "error_code?", "created_at")
    assert vocabulary == STATUS_WORDS
    assert tuple(
        member.value for member in PlannerExecutionStatusValue
    ) == STATUS_WORDS


def test_the_column_vocabulary_filter_is_pinned_for_the_outcome_block() -> None:
    columns, vocabulary = columns_and_vocabulary(
        _block("### RuntimeDecisionOutcome")
    )
    assert columns == (
        "turn_id",
        "decision_cycle_id?",
        "outcome",
        "reason_codes[]",
        "created_at",
    )
    assert vocabulary == OUTCOME_WORDS
    assert tuple(
        member.value for member in RuntimeDecisionOutcomeValue
    ) == OUTCOME_WORDS


# -- ③ the CHECK vocabularies, behaviourally ---------------------------------


def test_the_status_check_freezes_the_four_words(
    db: sqlite3.Connection, cycle
) -> None:
    """A word outside the document is refused **by the CHECK** — the cycle
    exists, so the refusal cannot be the foreign key."""

    for word in ("SKIPPED", "SELECT", "NORMAL"):
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            db.execute(
                "INSERT INTO planner_execution_status"
                " (decision_cycle_id, status, error_code, created_at)"
                " VALUES (?, ?, NULL, 'now')",
                (cycle.decision_cycle_id, word),
            )
        assert "CHECK" in str(excinfo.value), excinfo.value


def test_the_status_check_admits_every_frozen_word(
    db: sqlite3.Connection, cycle
) -> None:
    """The CHECK is a *set* of four: each word it names is insertable, so a
    typo in the DDL could not pass by refusing everything."""

    for index, word in enumerate(STATUS_WORDS):
        cycle_id = f"{cycle.decision_cycle_id}-{index}"
        db.execute(
            "INSERT INTO decision_cycle ("
            " decision_cycle_id, turn_id, cycle_index, learning_snapshot_id,"
            " evidence_watermark, curriculum_version, goal_version,"
            " schedule_version, policy_version, context_view_version,"
            " relationship_view_version, planner_decision_id,"
            " gate_decision_id, created_at"
            ") VALUES (?, ?, ?, 'ls', 1, 'c', 'g', 's', 'p', 'x', NULL,"
            " NULL, NULL, 'now')",
            (cycle_id, cycle.turn_id, 10 + index),
        )
        db.execute(
            "INSERT INTO planner_execution_status"
            " (decision_cycle_id, status, error_code, created_at)"
            " VALUES (?, ?, NULL, 'now')",
            (cycle_id, word),
        )
        assert db.execute(
            "SELECT status FROM planner_execution_status"
            " WHERE decision_cycle_id = ?",
            (cycle_id,),
        ).fetchone() == (word,)


def test_a_second_status_for_one_cycle_is_refused(
    db: sqlite3.Connection, cycle
) -> None:
    """One cycle, one status row — §14's PlannerExecutionStatus has no
    independent id, and the primary key is the cycle."""

    db.execute(
        "INSERT INTO planner_execution_status"
        " (decision_cycle_id, status, error_code, created_at)"
        " VALUES (?, 'SUCCEEDED', NULL, 'now')",
        (cycle.decision_cycle_id,),
    )
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        db.execute(
            "INSERT INTO planner_execution_status"
            " (decision_cycle_id, status, error_code, created_at)"
            " VALUES (?, 'SUCCEEDED', NULL, 'now')",
            (cycle.decision_cycle_id,),
        )
    assert "UNIQUE" in str(excinfo.value) or "PRIMARY" in str(excinfo.value), (
        excinfo.value
    )


def test_the_decision_check_freezes_the_two_words(
    db: sqlite3.Connection, cycle
) -> None:
    """A ``MAYBE`` decision is refused, and so is a status word: the two
    vocabularies are frozen separately (§14's two blocks). The evaluation the
    decision names exists, so the refusal is the CHECK and not the key."""

    db.execute(
        "INSERT INTO planner_evaluation ("
        " planner_evaluation_id, decision_cycle_id, frontier_candidate_ids,"
        " ranked_candidate_ids, factor_trace, planner_version,"
        " policy_profile_version, created_at"
        ") VALUES ('pe-mig', ?, '[]', '[]', '[]', 'v', 'v', 'now')",
        (cycle.decision_cycle_id,),
    )
    for index, word in enumerate(("MAYBE", "DEGRADED")):
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            db.execute(
                "INSERT INTO planner_decision ("
                " planner_decision_id, decision_cycle_id, decision,"
                " planner_evaluation_id, created_at"
                ") VALUES (?, ?, ?, 'pe-mig', 'now')",
                (f"pd-mig-{index}", cycle.decision_cycle_id, word),
            )
        assert "CHECK" in str(excinfo.value), excinfo.value


def test_the_outcome_check_refuses_a_decision_word(
    db: sqlite3.Connection, cycle
) -> None:
    """§14 line 889 as a CHECK: "Runtime degradation is not a PlannerDecision."
    — and, symmetrically, a decision is not an outcome. ``NO_TARGET`` is a
    legitimate ``decision`` word and an illegitimate ``outcome``."""

    for word in ("NO_TARGET", "SELECT", "FAILED"):
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            db.execute(
                "INSERT INTO runtime_decision_outcome ("
                " turn_id, decision_cycle_id, outcome, reason_codes,"
                " created_at"
                ") VALUES (?, ?, ?, '[]', 'now')",
                (cycle.turn_id, cycle.decision_cycle_id, word),
            )
        assert "CHECK" in str(excinfo.value), excinfo.value


def test_the_three_check_word_sets_are_disjoint_where_they_must_be() -> None:
    """The Gate-6 separation, restated over the DDL's own words: the decision
    set and the status set are disjoint, and the outcome set overlaps
    neither."""

    assert set(DECISION_WORDS) & set(STATUS_WORDS) == set()
    assert set(OUTCOME_WORDS) & set(STATUS_WORDS) == set()
    assert set(OUTCOME_WORDS) & set(DECISION_WORDS) == set()


# -- ④ the foreign keys ------------------------------------------------------


@pytest.mark.parametrize(
    "table,expected",
    [
        (
            "planner_evaluation",
            [("decision_cycle_id", "decision_cycle", "decision_cycle_id")],
        ),
        (
            "planner_decision",
            [
                ("decision_cycle_id", "decision_cycle", "decision_cycle_id"),
                (
                    "planner_evaluation_id",
                    "planner_evaluation",
                    "planner_evaluation_id",
                ),
            ],
        ),
        (
            "planner_execution_status",
            [("decision_cycle_id", "decision_cycle", "decision_cycle_id")],
        ),
        (
            "runtime_decision_outcome",
            [
                ("turn_id", "turn_record", "turn_id"),
                ("decision_cycle_id", "decision_cycle", "decision_cycle_id"),
            ],
        ),
    ],
)
def test_the_foreign_keys_are_the_ones_the_header_states(
    db: sqlite3.Connection, table: str, expected: list[tuple[str, str, str]]
) -> None:
    assert sorted(_parents(db, table)) == sorted(expected)


def test_a_row_with_an_unknown_parent_is_refused(
    db: sqlite3.Connection, cycle
) -> None:
    """The keys are enforced, not decorative (``PRAGMA foreign_keys=ON`` on
    every connection this repository opens)."""

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO planner_evaluation ("
            " planner_evaluation_id, decision_cycle_id,"
            " frontier_candidate_ids, ranked_candidate_ids, factor_trace,"
            " planner_version, policy_profile_version, created_at"
            ") VALUES ('pe-x', 'dc-nope', '[]', '[]', '[]', 'v', 'v', 'now')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO runtime_decision_outcome ("
            " turn_id, decision_cycle_id, outcome, reason_codes, created_at"
            ") VALUES ('turn-nope', ?, 'NORMAL', '[]', 'now')",
            (cycle.decision_cycle_id,),
        )


def test_the_back_reference_stays_plain_data(db: sqlite3.Connection) -> None:
    """Decision B: no FK on ``decision_cycle.planner_decision_id``, and the
    column is the one 0006 declared (the table is not rebuilt).

    The table's whole FK list is pinned — not just "no entry for
    ``planner_decision_id``" — so a future cut cannot add a key here under
    another name and still pass.
    """

    assert _parents(db, "decision_cycle") == [
        ("turn_id", "turn_record", "turn_id")
    ]
    assert "planner_decision_id" in _columns(db, "decision_cycle")


# -- ⑤ DDL only --------------------------------------------------------------


def test_the_four_tables_land_empty(db: sqlite3.Connection) -> None:
    """No backfill, no seed: 0015 creates the schema and no row."""

    for table in SECTION_TABLES.values():
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)


def test_no_planner_row_existed_before_this_cut(db: sqlite3.Connection) -> None:
    """The pre-0015 world is untouched by the migration: the tables it adds
    are the only new ones and the cycle they hang off is still empty."""

    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert set(SECTION_TABLES.values()) <= tables
    assert tables - set(SECTION_TABLES.values())  # the rest of the schema
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone() == (0,)
