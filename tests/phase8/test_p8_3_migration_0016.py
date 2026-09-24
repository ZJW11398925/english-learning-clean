"""P8-3 ①② — migration 0016: the PlanningLedger's three tables.

What is pinned here is what the migration claims:

- the three tables exist with §14's column set read **out of the document at
  test time** — the per-key row, the eleven ``coverage_obligations[]`` fields
  (indented in the block, read as the sub-table they are) and the event log —
  and the two columns §14 names that this cut does **not** materialize are
  absent, which is the migration's registered reading rather than an omission;
- the CHECK vocabularies are the canonical words: RA §20's five event words,
  verbatim, and §14's two key faces (the first line's ``target/family``);
- the foreign keys are the ones the header states, and
  ``coverage_obligation`` has none (a debt is not a row's child);
- the migration is DDL only — it creates no row — and applying it leaves
  ``0001–0015`` byte-identical (per-file SHA-256, CRLF-normalized);
- applying the chain is idempotent and the stamps move to the shared head.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from elc.planner.ledger import (
    LEDGER_EVENTS,
    LEDGER_KEY_TYPES,
    PLANNING_LEDGER_MODEL_VERSION,
    ObligationScope,
)
from elc.platform.db import migrations
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)
from tests.phase8.conftest import canonical_blocks_verbatim

MIGRATIONS_DIR = REPO_ROOT / "migrations"
HEAD_0016 = "0016_planning_ledger.sql"

#: 0015's blob, **recorded by this cut** and unchanged by it — 0001–0014 are
#: held by the two records that already carry them (tests/phase6's
#: ``PRE_0013_DIGESTS`` for 0001–0012 and tests/phase8's ``PRE_0015_DIGESTS``
#: for 0013–0014), so the whole 0001–0015 lineage is pinned from the original
#: records plus this one value.
PRE_0016_DIGESTS = {
    "0015_planner_records.sql": (
        "42ad02956345b12b1163911f18ab0860b317e81bbd716872eaa8ceab636beac2"
    ),
}

#: §14's key line, verbatim: the row is keyed by a ``target`` **or** a
#: ``family`` and the first column is ``last_selected_at``.
KEY_LINE = "target/family last_selected_at"

#: The two columns §14 names that this cut deliberately does not materialize
#: (migration 0016's header: DATA_MODEL §26 lists "some PlanningLedger rollups"
#: among the rebuildable projections, and a ledger-level aggregate carried on a
#: per-key row would be a stored copy nothing reconciles).
NOT_MATERIALIZED = ("coverage_debt_rollups", "recent_target_families")


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


def _parents(db: sqlite3.Connection, table: str) -> list[tuple[str, str, str]]:
    return [
        (str(row[3]), str(row[2]), str(row[4]))
        for row in db.execute(f"PRAGMA foreign_key_list({table})")
    ]


def _table_sql(db: sqlite3.Connection, table: str) -> str:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    assert row is not None, table
    return " ".join(str(row[0]).split())


def _block() -> tuple[str, ...]:
    return canonical_blocks_verbatim("DATA_MODEL.md", "### PlanningLedger")[0]


def _flat_and_indented() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The block's flat lines (§14's ledger-level columns) and its indented ones
    (the ``coverage_obligations[]`` sub-block)."""

    block = _block()
    flat = tuple(line.strip() for line in block if not line[:1].isspace())
    indented = tuple(line.strip() for line in block if line[:1].isspace())
    return flat, indented


# -- ① the lineage -----------------------------------------------------------


def test_0016_is_the_head_and_0015s_successor() -> None:
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[-1] == SCHEMA_HEAD_FILE == HEAD_0016
    assert names[names.index("0015_planner_records.sql") + 1] == HEAD_0016
    assert [name[:4] for name in names] == [
        f"{index:04d}" for index in range(1, len(MIGRATION_IDS) + 1)
    ]
    assert MIGRATION_IDS[-1] == "0016_planning_ledger"


def test_the_pre_0016_lineage_did_not_move() -> None:
    """0001–0015 are byte-identical at the blob level (CRLF-normalized)."""

    from tests.phase6.test_p6_3_migration_0013 import PRE_0013_DIGESTS
    from tests.phase8.test_p8_0_migration_0015 import PRE_0015_DIGESTS

    recorded = {**PRE_0013_DIGESTS, **PRE_0015_DIGESTS, **PRE_0016_DIGESTS}
    names = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert names[: len(recorded)] == list(recorded)
    for name, digest in recorded.items():
        assert _digest(MIGRATIONS_DIR / name) == digest, name


def test_applying_the_chain_is_idempotent(db: sqlite3.Connection) -> None:
    assert migrations.apply_migrations(db) == []
    assert "0016_planning_ledger" in migrations.applied_migrations(db)


def test_the_stamps_move_to_the_shared_head(db: sqlite3.Connection) -> None:
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION == "16"
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


def test_0016_is_ddl_only() -> None:
    """Every statement the file carries is a ``CREATE TABLE`` or one of the two
    ``schema_meta`` version stamps — no row of any table this cut lands, no
    rebuild, no ALTER/DROP."""

    text = (MIGRATIONS_DIR / HEAD_0016).read_text(encoding="utf-8")
    body = "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("--")
    )
    statements = [part.strip() for part in body.split(";") if part.strip()]
    creates = [part for part in statements if part.upper().startswith("CREATE TABLE")]
    stamps = [
        part for part in statements if part.startswith("INSERT INTO schema_meta")
    ]
    assert len(creates) == 3
    assert len(stamps) == 2
    assert len(creates) + len(stamps) == len(statements)
    for create in creates:
        # No statement head other than CREATE TABLE — the three tables carry
        # only DDL, and the two stamps are the only rows the file writes (the
        # words inside a CHECK are vocabulary, not statements: one of §20's is
        # ``candidate_selected``).
        assert create.upper().startswith("CREATE TABLE IF NOT EXISTS")
    assert "DROP" not in body.upper()
    assert "ALTER" not in body.upper()
    assert body.upper().count("INSERT") == 2


# -- ② the three tables, against §14 read at test time -----------------------


def test_the_key_line_is_the_documents(db: sqlite3.Connection) -> None:
    """§14's first line names the row: a ``target`` or a ``family`` key, and
    ``last_selected_at`` as the first column. The declared key faces are the
    enum migration 0016 CHECKs, word for word."""

    flat, _ = _flat_and_indented()
    assert flat[0] == KEY_LINE
    key_spelling, first_column = KEY_LINE.split(" ")
    assert key_spelling == "target/family"
    assert [face.value for face in LEDGER_KEY_TYPES] == ["TARGET", "TARGET_FAMILY"]
    assert first_column == "last_selected_at"
    columns = _columns(db, "planning_ledger")
    assert columns[:2] == ["ledger_key", "ledger_key_type"]
    assert columns[2] == first_column
    ddl = _table_sql(db, "planning_ledger")
    assert (
        "ledger_key_type TEXT NOT NULL CHECK (ledger_key_type IN"
        " ('TARGET', 'TARGET_FAMILY'))" in ddl
    )


def test_the_row_columns_are_the_documents(db: sqlite3.Connection) -> None:
    """§14's flat per-key group, in the document's order.

    The slash pair ``recent_skips/rejections`` is **one** column named
    ``recent_skips`` — the migration's registered reading (a skip *is* a
    rejection in the core's own event-effect registration, so two columns would
    be one count stored twice) — and the three ledger-level lines are not on
    this table (below)."""

    flat, _ = _flat_and_indented()
    per_key = flat[1 : flat.index("coverage_obligations[]")]
    assert per_key == (
        "last_presented_at",
        "teaching_exposure_counts",
        "probe_counts",
        "review_offers",
        "recent_skips/rejections",
        "overexposure_window",
    )
    expected = ["ledger_key", "ledger_key_type", "last_selected_at"]
    for line in per_key:
        expected.append(line.split("/")[0])
    # ``version`` is §14's last line (a ledger-level column) and this cut
    # carries it on every row — the next test asserts exactly that.
    expected.append("version")
    assert _columns(db, "planning_ledger") == expected
    assert "recent_rejections" not in _table_sql(db, "planning_ledger")


def test_the_ledger_level_columns_the_cut_materializes(db: sqlite3.Connection) -> None:
    """Of §14's three row-independent lines, ``version`` is carried on every row
    (the §5.2 ``schedule_item.version`` precedent, stamped with the core's
    constant) and the two rollup-shaped ones are not materialized."""

    flat, _ = _flat_and_indented()
    ledger_level = flat[flat.index("coverage_debt_rollups") :]
    assert ledger_level == (
        "coverage_debt_rollups",
        "recent_target_families",
        "version",
    )
    columns = _columns(db, "planning_ledger")
    assert columns[-1] == "version"
    for column in NOT_MATERIALIZED:
        assert column not in columns, column


def test_the_obligation_columns_are_the_canonical_sub_block(
    db: sqlite3.Connection,
) -> None:
    """``coverage_obligations[]``'s eleven fields, verbatim and in order."""

    _, indented = _flat_and_indented()
    assert len(indented) == 11
    expected = [line.rstrip("?").removesuffix("[]") for line in indented]
    assert expected == [
        "obligation_key",
        "scope_type",
        "target_or_family_id",
        "goal_id",
        "window_start",
        "window_end",
        "debt_value",
        "accrual_paused",
        "pause_reason",
        "last_served_at",
        "last_engaged_at",
    ]
    assert _columns(db, "coverage_obligation") == expected


def test_the_four_question_columns_are_the_nullable_ones(
    db: sqlite3.Connection,
) -> None:
    """§14 marks four obligation fields ``?``; every other column of the three
    tables is NOT NULL (keys excepted — a ``TEXT PRIMARY KEY`` reports
    ``notnull=0`` whatever the DDL says)."""

    _, indented = _flat_and_indented()
    optional = {
        line.rstrip("?").removesuffix("[]")
        for line in indented
        if line.endswith("?")
    }
    assert optional == {
        "goal_id",
        "pause_reason",
        "last_served_at",
        "last_engaged_at",
    }
    for table, key in (
        ("coverage_obligation", "obligation_key"),
        ("planning_ledger", "ledger_key"),
        ("planning_ledger_event", "event_id"),
    ):
        flags = _notnull(db, table)
        for column, flag in flags.items():
            if column == key:
                continue
            if table == "coverage_obligation":
                expected = 0 if column in optional else 1
            elif table == "planning_ledger":
                # the two leave-the-log timestamps and the row's own window are
                # NULL when the log has nothing to say (the core's own answer)
                expected = (
                    0
                    if column
                    in (
                        "last_selected_at",
                        "last_presented_at",
                        "overexposure_window",
                    )
                    else 1
                )
            else:
                expected = 1
            assert flag == expected, (table, column)


def test_the_event_log_is_four_columns_with_the_five_words(
    db: sqlite3.Connection,
) -> None:
    """RA §20's block is the CHECK, character for character — and the words are
    the core's own event vocabulary, in the document's order."""

    assert _columns(db, "planning_ledger_event") == [
        "event_id",
        "ledger_key",
        "event",
        "as_of",
    ]
    ddl = _table_sql(db, "planning_ledger_event")
    words = ", ".join(f"'{event.value}'" for event in LEDGER_EVENTS)
    assert f"event TEXT NOT NULL CHECK (event IN ({words}))" in ddl
    assert [event.value for event in LEDGER_EVENTS] == [
        "candidate_selected",
        "teaching_presented",
        "hint_presented",
        "reveal_presented",
        "user_skip",
    ]


def test_the_schema_refuses_a_word_outside_the_five(db: sqlite3.Connection) -> None:
    """A sixth word is refused by the table, not by a convention."""

    import pytest

    db.execute(
        "INSERT INTO planning_ledger (ledger_key, ledger_key_type,"
        " teaching_exposure_counts, probe_counts, review_offers, recent_skips,"
        " version) VALUES ('t-x', 'TARGET', 0, 0, 0, 0, 'pl1')"
    )
    for word in ("skipped", "SELECTED", "candidate_selected "):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO planning_ledger_event (event_id, ledger_key,"
                " event, as_of) VALUES (?, 't-x', ?, 'now')",
                (f"ev-{word}", word),
            )


def test_the_schema_refuses_a_key_face_outside_the_two(
    db: sqlite3.Connection,
) -> None:
    import pytest

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO planning_ledger (ledger_key, ledger_key_type,"
            " teaching_exposure_counts, probe_counts, review_offers,"
            " recent_skips, version)"
            " VALUES ('t-x', 'GOAL', 0, 0, 0, 0, 'pl1')"
        )


def test_the_schema_refuses_a_half_declared_pause(db: sqlite3.Connection) -> None:
    """The core's constructor sentence, in DDL: a pause has a reason and a
    reason has a pause."""

    import pytest

    insert = (
        "INSERT INTO coverage_obligation (obligation_key, scope_type,"
        " target_or_family_id, goal_id, window_start, window_end, debt_value,"
        " accrual_paused, pause_reason, last_served_at, last_engaged_at)"
        " VALUES (?, ?, 't-1', NULL, 'a', 'b', 0.5, ?, ?, NULL, NULL)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, ("ob-1", "TARGET", 1, None))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, ("ob-2", "TARGET", 0, "UNAVAILABLE_IN_CURRENT_RUNTIME"))
    # the two legal halves
    db.execute(insert, ("ob-3", "TARGET", 0, None))
    db.execute(
        insert, ("ob-4", "TARGET", 1, "UNAVAILABLE_IN_CURRENT_RUNTIME")
    )


def test_scope_type_is_carried_raw(db: sqlite3.Connection) -> None:
    """No canonical document lists ``scope_type``'s vocabulary, so the schema
    freezes none (the 0012 ``event_type`` / R5 precedent) — the implementation
    words stay in the core's ``ObligationScope``."""

    ddl = _table_sql(db, "coverage_obligation")
    assert "scope_type TEXT NOT NULL" in ddl
    for scope in ObligationScope:
        assert scope.value not in ddl, scope.value
    assert "debt_value REAL NOT NULL" in ddl


def test_the_log_references_the_row_and_the_obligations_reference_nothing(
    db: sqlite3.Connection,
) -> None:
    assert _parents(db, "planning_ledger_event") == [
        ("ledger_key", "planning_ledger", "ledger_key")
    ]
    assert _parents(db, "coverage_obligation") == []
    assert _parents(db, "planning_ledger") == []


def test_the_window_column_is_one_deterministic_json_object(
    db: sqlite3.Connection,
) -> None:
    """§14 names **one** ``overexposure_window`` column; it lands as one TEXT
    column carrying a JSON object, not as two invented column names."""

    ddl = _table_sql(db, "planning_ledger")
    assert "overexposure_window TEXT" in ddl
    assert "overexposure_window_start" not in ddl
    assert "overexposure_window_end" not in ddl


def test_the_version_column_is_the_core_constant_not_a_second_one(
    db: sqlite3.Connection,
) -> None:
    """The stored version is the core's model version, so one number has one
    source (nothing in the migration spells a version string)."""

    text = (MIGRATIONS_DIR / HEAD_0016).read_text(encoding="utf-8")
    assert PLANNING_LEDGER_MODEL_VERSION not in text
    assert "version                  TEXT NOT NULL" in text


def test_the_three_tables_are_the_cuts_whole_schema_addition(
    db: sqlite3.Connection,
) -> None:
    """0016 creates the three tables it declares and nothing else — checked
    against the real database rather than against the file's prose."""

    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {
        "planning_ledger",
        "coverage_obligation",
        "planning_ledger_event",
    } <= tables
    assert not [
        name
        for name in tables
        if name.endswith(("_v15", "_v16", "_backup"))
    ]
