"""P8-3 ⑤ — migration 0016's three tables are removal surface, in two scopes.

BF-05's contract names the ledger twice — "PlanningLedger user history" under
``LEARNING_PRIVATE`` (line 87) and "related PlanningLedger history" under the
``LEARNING_TARGET`` scope (line 747) — and
``elc.planner.ledger.PLANNING_LEDGER_STORAGE_REVISIT`` names the condition this
cut satisfies: **the tables and their deletion statements land in one change**.
The declaration half is asserted (the sets, their order, the per-table literals
and the import-time guard), and the behavioural half runs the real durable
executor once per scope with real rows in all three tables.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.deletion.plan import assert_known_tables
from elc.deletion.store import (
    _DELETE_BY_ROWID,
    _SURFACE_SELECT,
    SqliteDeletionStore,
)
from elc.deletion.types import (
    ALL_USER_DATA_SWEPT_TABLES,
    GLOBAL_CONTENT_TABLES,
    LEARNING_HISTORY_SWEPT_TABLES,
    LEARNING_TARGET_SWEPT_TABLES,
    PERSONA_PACKAGE_SWEPT_TABLES,
    PROFILE_FIELD_SWEPT_TABLES,
    RELATIONSHIP_PAIR_SWEPT_TABLES,
    RETAINED_TABLES,
    SWEPT_TABLES,
    DeletionRequest,
    DeletionScope,
)
from elc.planner.ledger import (
    CoverageObligation,
    LedgerEvent,
    LedgerKeyType,
    ObligationScope,
    TargetLedgerRow,
)
from elc.planner.ledger_store import (
    PLANNING_LEDGER_STORE_SOURCES,
    SqliteLedgerStore,
)
from elc.platform.types import Ok
from tests.conftest import REPO_ROOT, SRC_ROOT

LEDGER_TABLES = (
    "planning_ledger_event",
    "planning_ledger",
    "coverage_obligation",
)

TARGET = "t-p8-3-del"
OTHER_TARGET = "t-p8-3-keep"
FAMILY = "family-p8-3"
DAY = "2026-09-23T09:00:00+00:00"


@pytest.fixture()
def ledger_store(db: sqlite3.Connection, fence) -> SqliteLedgerStore:
    return SqliteLedgerStore(db, fence)


def seed(
    db: sqlite3.Connection, store: SqliteLedgerStore, key: str, *,
    key_type: LedgerKeyType = LedgerKeyType.TARGET,
    obligation_keys: tuple[str, ...] = (),
) -> None:
    """One real row, one event and (optionally) obligations,"""

    written = store.record_ledger_event(
        event_id=f"ev-{key_type.value}-{key}",
        event=LedgerEvent.TEACHING_PRESENTED,
        row=TargetLedgerRow(target_key=key).record(
            LedgerEvent.TEACHING_PRESENTED, at=DAY
        ),
        key_type=key_type,
    )
    assert isinstance(written, Ok), written
    for index, obligation_key in enumerate(obligation_keys):
        assert isinstance(
            store.upsert_obligation(
                CoverageObligation(
                    obligation_key=obligation_key,
                    scope_type=ObligationScope.TARGET.value,
                    target_or_family_id=key,
                    goal_id=None,
                    window_start="2026-09-01T00:00:00+00:00",
                    window_end="2026-09-30T00:00:00+00:00",
                    debt_value=0.5 + index / 100,
                    accrual_paused=False,
                    pause_reason=None,
                    last_served_at=None,
                    last_engaged_at=None,
                )
            ),
            Ok,
        )


def _count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _execute(db: sqlite3.Connection, fence, request: DeletionRequest):
    result = SqliteDeletionStore(db, fence).execute(request)
    assert isinstance(result, Ok), result
    return {tally.table: tally.removed for tally in result.value.tallies}


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }


# -- the declarations --------------------------------------------------------


@pytest.mark.parametrize("table", LEDGER_TABLES)
def test_every_ledger_table_is_in_the_two_scopes_the_contract_names(
    table: str,
) -> None:
    assert table in LEARNING_TARGET_SWEPT_TABLES, table
    assert table in LEARNING_HISTORY_SWEPT_TABLES, table
    assert table in SWEPT_TABLES, table
    assert table in ALL_USER_DATA_SWEPT_TABLES, table


@pytest.mark.parametrize("table", LEDGER_TABLES)
def test_no_narrower_scope_reaches_a_ledger_table(table: str) -> None:
    """SEC-026/027's shape: a pair's, a field's or a persona package's deletion
    has no business in the ledger — and a ledger row is not a profile fact."""

    for surface in (
        RELATIONSHIP_PAIR_SWEPT_TABLES,
        PROFILE_FIELD_SWEPT_TABLES,
        PERSONA_PACKAGE_SWEPT_TABLES,
        # CONVERSATION is the one scope the contract names *third*: §19 deletes
        # "Review / Planning history solely derived from deleted Evidence",
        # and this cut registers that the ledger has no row-level carrier for
        # that rule (no conversation column; a row aggregates across
        # conversations), so the scope does not name these tables — asserted
        # here so the boundary is a decision rather than an omission.
        ("conversation",),
    ):
        assert table not in surface, table


def test_the_retained_set_is_unchanged() -> None:
    assert set(RETAINED_TABLES) == {
        "deletion_tombstone",
        "runtime_epoch",
        "schema_meta",
        "schema_migrations",
    }
    assert GLOBAL_CONTENT_TABLES == ()
    for table in LEDGER_TABLES:
        assert table not in RETAINED_TABLES
        assert table not in GLOBAL_CONTENT_TABLES


def test_the_three_sets_still_partition_the_real_database(
    db: sqlite3.Connection,
) -> None:
    declared = (
        set(SWEPT_TABLES) | set(RETAINED_TABLES) | set(GLOBAL_CONTENT_TABLES)
    )
    assert declared == _tables(db)
    assert_known_tables(sorted(_tables(db)))
    assert len(SWEPT_TABLES) + len(RETAINED_TABLES) == len(declared)


def test_the_sweep_order_still_satisfies_every_foreign_key(
    db: sqlite3.Connection,
) -> None:
    positions = {table: index for index, table in enumerate(SWEPT_TABLES)}
    for table in SWEPT_TABLES:
        for row in db.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            parent = str(row[2])
            if parent == table or parent not in positions:
                continue
            assert positions[parent] > positions[table], (table, parent)
    assert positions["planning_ledger_event"] < positions["planning_ledger"]


def test_the_scoped_surfaces_are_subsequences_of_the_global_order() -> None:
    global_positions = {
        table: index for index, table in enumerate(SWEPT_TABLES)
    }
    for surface in (LEARNING_TARGET_SWEPT_TABLES, LEARNING_HISTORY_SWEPT_TABLES):
        positions = [global_positions[table] for table in surface]
        assert positions == sorted(positions)


def test_the_statement_maps_carry_one_select_and_one_delete_per_table() -> None:
    """The import-time guard has already run (the module imported); this is the
    literal half: one SELECT and one DELETE per ledger table, each naming it."""

    for table in LEDGER_TABLES:
        select = _SURFACE_SELECT[table]
        assert select.startswith("SELECT rowid, "), select
        assert f"FROM {table}" in select, select
        assert _DELETE_BY_ROWID[table] == f"DELETE FROM {table} WHERE rowid IN ("


def test_the_deleter_is_the_only_module_that_names_the_tables_with_a_delete() -> None:
    """One home for removals, and none for rewrites: the store that appends
    events carries no UPDATE and no DELETE statement.

    The one writer that is not a removal is P8-4's CONVERSATION leg on the
    event log: ``UPDATE … SET moment_id = NULL`` clears a provenance reference
    (migration 0017's column) without touching a row or a logged fact — which
    is why ``planning_ledger_event`` is the one pair of statements here and
    ``ledger_store.py`` (the appender) still carries ``INSERT`` alone."""

    from tests.phase3.sql_write_scan import write_statements

    appender = write_statements(
        REPO_ROOT / "src" / "elc" / "planner" / "ledger_store.py"
    )
    assert appender["planning_ledger"] == ("INSERT",)
    assert appender["planning_ledger_event"] == ("INSERT",)
    assert appender["coverage_obligation"] == ("INSERT",)
    deleter = write_statements(
        REPO_ROOT / "src" / "elc" / "deletion" / "store.py"
    )
    assert deleter["planning_ledger"] == ("DELETE",)
    assert deleter["planning_ledger_event"] == ("DELETE", "UPDATE")
    assert deleter["coverage_obligation"] == ("DELETE",)


def test_the_package_registration_no_longer_denies_the_table() -> None:
    """The package's own "what this does **not** claim" bullet moved with the
    tables (p8-3 disposal F1): the S43/S46/S48 ledger legs are real rows now,
    and the one leg still answered by registration is S41's CONVERSATION
    clause — the sentence the walks below and
    ``test_a_conversation_deletion_does_not_reach_the_ledger`` execute."""

    text = " ".join(
        (SRC_ROOT / "deletion" / "__init__.py")
        .read_text(encoding="utf-8")
        .split()
    )
    assert "has no table in app.db" not in text
    assert "PLANNING_LEDGER_ENTRY" in text
    assert "``ledger1``" in text
    assert "S41 is the one leg still answered by registration" in text
    for case_id in ("S41", "S43", "S46", "S48"):
        assert case_id in text, case_id
    assert "no row-level carrier" in text


def test_the_store_sources_are_the_three_tables() -> None:
    assert set(LEDGER_TABLES) == set(PLANNING_LEDGER_STORE_SOURCES)
    for table in LEDGER_TABLES:
        assert table in SWEPT_TABLES


def test_the_ledger_store_module_is_not_the_deleter() -> None:
    """The appending store carries no ``DELETE``/``UPDATE`` text at all — the
    log is append-only and its removal belongs to the walk above."""

    text = (
        Path(REPO_ROOT) / "src" / "elc" / "planner" / "ledger_store.py"
    ).read_text(encoding="utf-8")
    assert "DELETE FROM" not in text
    assert "UPDATE " not in text.replace(
        "ON CONFLICT(ledger_key) DO UPDATE SET", ""
    ).replace("ON CONFLICT(obligation_key) DO UPDATE SET", "")


# -- the walks ---------------------------------------------------------------


def test_a_target_deletion_removes_its_ledger_history(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    seed(db, ledger_store, TARGET, obligation_keys=("ob-del",))
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.LEARNING_TARGET, target_id=TARGET),
    )
    for table in LEDGER_TABLES:
        assert tallies.get(table) == 1, table
        assert _count(db, table) == 0, table


def test_a_target_deletion_is_scoped_by_the_key_face(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    """The sharpest case the key-face column exists for: the only row under the
    deleted target's spelling is a **family** row, and a target's deletion does
    not reach a family's history."""

    seed(db, ledger_store, TARGET, key_type=LedgerKeyType.TARGET_FAMILY)
    seed(db, ledger_store, OTHER_TARGET)
    before = {table: _count(db, table) for table in LEDGER_TABLES}
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.LEARNING_TARGET, target_id=TARGET),
    )
    assert [name for name in tallies if name in LEDGER_TABLES] == []
    assert {table: _count(db, table) for table in LEDGER_TABLES} == before
    assert ledger_store.get_ledger_row(TARGET).value is not None
    assert (
        ledger_store.get_ledger_projection(TARGET).value.ledger_key_type
        is LedgerKeyType.TARGET_FAMILY
    )


def test_a_target_deletion_removes_only_that_target(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    seed(db, ledger_store, TARGET, obligation_keys=("ob-del",))
    seed(db, ledger_store, OTHER_TARGET, obligation_keys=("ob-keep",))
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.LEARNING_TARGET, target_id=TARGET),
    )
    assert tallies.get("planning_ledger") == 1
    assert tallies.get("planning_ledger_event") == 1
    assert tallies.get("coverage_obligation") == 1
    remaining = {
        str(row[0])
        for row in db.execute(
            "SELECT ledger_key FROM planning_ledger ORDER BY ledger_key"
        )
    }
    assert remaining == {OTHER_TARGET}
    assert _count(db, "planning_ledger_event") == 1
    assert _count(db, "coverage_obligation") == 1
    assert ledger_store.get_obligation("ob-keep").value is not None


def test_a_target_deletion_leaves_a_goal_scoped_obligation_alone(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    assert isinstance(
        ledger_store.upsert_obligation(
            CoverageObligation(
                obligation_key="ob-goal",
                scope_type=ObligationScope.GOAL.value,
                target_or_family_id=TARGET,
                goal_id="goal-1",
                window_start="2026-09-01T00:00:00+00:00",
                window_end="2026-09-30T00:00:00+00:00",
                debt_value=0.2,
                accrual_paused=False,
                pause_reason=None,
                last_served_at=None,
                last_engaged_at=None,
            )
        ),
        Ok,
    )
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.LEARNING_TARGET, target_id=TARGET),
    )
    assert tallies.get("coverage_obligation") is None
    assert _count(db, "coverage_obligation") == 1


def test_all_learning_history_removes_every_ledger_row(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    seed(db, ledger_store, TARGET, obligation_keys=("ob-del",))
    seed(db, ledger_store, OTHER_TARGET)
    seed(db, ledger_store, FAMILY, key_type=LedgerKeyType.TARGET_FAMILY)
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY),
    )
    for table in LEDGER_TABLES:
        assert _count(db, table) == 0, table
    assert tallies.get("planning_ledger") == 3
    assert tallies.get("planning_ledger_event") == 3


def test_all_user_data_sweeps_the_ledger(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    seed(db, ledger_store, TARGET, obligation_keys=("ob-del", "ob-two"))
    tallies = _execute(
        db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    for table in LEDGER_TABLES:
        assert _count(db, table) == 0, table
    assert tallies.get("planning_ledger") == 1
    assert tallies.get("coverage_obligation") == 2


def test_the_removed_ledger_rows_are_tombstoned(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    """§24's ledger: a removal that claims to have happened is recorded, and
    the walk's tally is what the record is made of."""

    seed(db, ledger_store, TARGET, obligation_keys=("ob-del",))
    result = SqliteDeletionStore(db, fence).execute(
        DeletionRequest(scope=DeletionScope.LEARNING_TARGET, target_id=TARGET)
    )
    assert isinstance(result, Ok), result
    assert result.value.tombstoned >= 3
    assert _count(db, "deletion_tombstone") >= 3


def test_a_conversation_deletion_does_not_reach_the_ledger(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    """The registered boundary: §19's clause has no row-level carrier here, so
    the scope does not name these tables — and a ledger row survives a
    conversation's deletion (its own removal is the two scopes above)."""

    seed(db, ledger_store, TARGET, obligation_keys=("ob-del",))
    before = {table: _count(db, table) for table in LEDGER_TABLES}
    tallies = _execute(
        db,
        fence,
        DeletionRequest(
            scope=DeletionScope.CONVERSATION, conversation_id="c-p8-3"
        ),
    )
    assert all(not name.startswith("planning_") for name in tallies)
    assert {table: _count(db, table) for table in LEDGER_TABLES} == before


def test_the_ledger_rows_are_addressable_by_key_after_a_partial_deletion(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    """A target's deletion is not a table-wide truncation: the surviving keys
    still read back through the store's own faces."""

    seed(db, ledger_store, TARGET)
    seed(db, ledger_store, OTHER_TARGET)
    _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.LEARNING_TARGET, target_id=TARGET),
    )
    assert ledger_store.get_ledger_row(OTHER_TARGET).value is not None
    assert ledger_store.get_ledger_row(TARGET).value is None
    assert ledger_store.list_ledger_events(TARGET).value == ()
    assert sorted(ledger_store.read_ledger().value.rows) == [OTHER_TARGET]


def test_the_ledger_tables_are_absent_from_the_content_db_sweep(
    db: sqlite3.Connection, fence, ledger_store: SqliteLedgerStore
) -> None:
    """SEC-025's other half, in this cut's shape: the sweep never opens another
    database, and no content table exists in app.db to be reached."""

    seed(db, ledger_store, TARGET)
    _execute(db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA))
    assert GLOBAL_CONTENT_TABLES == ()
    assert _tables(db) == (
        set(SWEPT_TABLES) | set(RETAINED_TABLES)
    )
