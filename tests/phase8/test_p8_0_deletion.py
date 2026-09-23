"""P8-0 ⑥ — the four §14 tables are removal surface, in all three scopes.

Migration 0015 lands tables that hold a cycle's decision trail, so BF-05's
removal has to reach them: they are children of ``decision_cycle`` (and
``runtime_decision_outcome`` of ``turn_record``), which means "delete the
cycle, keep its decision" would be a foreign-key refusal if the sweep missed
them. The declaration half is asserted (three surfaces, children-first), and
the behavioural half runs the real durable executor once per scope.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.deletion.plan import assert_known_tables
from elc.deletion.store import SqliteDeletionStore
from elc.deletion.types import (
    ALL_USER_DATA_SWEPT_TABLES,
    CONVERSATION_SWEPT_TABLES,
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
from elc.platform.types import Ok
from tests.phase7.conftest import CONV, proposal
from tests.phase8.conftest import (
    WATERMARK,
    request_of,
    supply_of,
    table_counts,
)

PLANNER_TABLES = (
    "planner_decision",
    "planner_evaluation",
    "planner_execution_status",
    "runtime_decision_outcome",
)

SCOPES = (
    DeletionScope.CONVERSATION,
    DeletionScope.ALL_LEARNING_HISTORY,
    DeletionScope.ALL_USER_DATA,
)


def _write_unit(db: sqlite3.Connection, cycle, planner_store) -> None:
    """One real SELECT run, persisted — the rows a deletion must reach."""

    from elc.planner.shadow import run_shadow

    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(proposal("c-p8-0")),
        current_learning_watermark=WATERMARK,
    )
    written = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=shadow.outcome
    )
    assert isinstance(written, Ok), written
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 1
    )


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }


# -- the declarations --------------------------------------------------------


def test_the_four_tables_are_in_the_three_scope_surfaces() -> None:
    for scope in SCOPES:
        surface = {
            DeletionScope.CONVERSATION: CONVERSATION_SWEPT_TABLES,
            DeletionScope.ALL_LEARNING_HISTORY: LEARNING_HISTORY_SWEPT_TABLES,
            DeletionScope.ALL_USER_DATA: ALL_USER_DATA_SWEPT_TABLES,
        }[scope]
        for table in PLANNER_TABLES:
            assert table in surface, f"{scope.value}: {table}"


def test_the_four_tables_are_not_in_the_narrower_scopes() -> None:
    """SEC-026/027's shape: a target's, a pair's or a field's deletion has no
    business reaching a decision trail — and a planner record is not a
    learning-target row."""

    for surface in (
        LEARNING_TARGET_SWEPT_TABLES,
        RELATIONSHIP_PAIR_SWEPT_TABLES,
        PROFILE_FIELD_SWEPT_TABLES,
        PERSONA_PACKAGE_SWEPT_TABLES,
    ):
        for table in PLANNER_TABLES:
            assert table not in surface, table


def test_the_retained_set_is_unchanged_and_the_sweep_grew_by_four() -> None:
    assert set(RETAINED_TABLES) == {
        "deletion_tombstone",
        "runtime_epoch",
        "schema_meta",
        "schema_migrations",
    }
    assert GLOBAL_CONTENT_TABLES == ()
    for table in PLANNER_TABLES:
        assert table in SWEPT_TABLES
        assert table not in RETAINED_TABLES
        assert table not in GLOBAL_CONTENT_TABLES


def test_the_three_sets_still_partition_the_real_database(
    db: sqlite3.Connection,
) -> None:
    """The pin that makes the closure real: the migrated database has no
    unclassified table, and the deployed guard agrees."""

    declared = (
        set(SWEPT_TABLES) | set(RETAINED_TABLES) | set(GLOBAL_CONTENT_TABLES)
    )
    assert declared == _tables(db)
    assert_known_tables(sorted(_tables(db)))


@pytest.mark.parametrize("scope_index", [0, 1, 2])
def test_the_four_tables_are_children_first_in_every_surface(
    db: sqlite3.Connection, scope_index: int
) -> None:
    """The order the sweep deletes in: each planner table before
    ``decision_cycle`` (and the outcome row before ``turn_record``), checked
    against the real foreign keys rather than by trying a delete."""

    surface = (
        CONVERSATION_SWEPT_TABLES,
        LEARNING_HISTORY_SWEPT_TABLES,
        ALL_USER_DATA_SWEPT_TABLES,
    )[scope_index]
    positions = {table: index for index, table in enumerate(surface)}
    for table in PLANNER_TABLES:
        assert positions[table] < positions["decision_cycle"], table
        for row in db.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            parent = str(row[2])
            if parent in positions:
                assert positions[parent] > positions[table], (
                    f"{table} references {parent} too late"
                )
    assert positions["planner_decision"] < positions["planner_evaluation"]
    if "turn_record" in positions:
        # §20's learning-history surface keeps the transcript, so this leg
        # only exists in the two whole-conversation walks — where the
        # outcome row (a turn's) must go before its turn.
        assert positions["runtime_decision_outcome"] < positions["turn_record"]


# -- the walks ---------------------------------------------------------------


def _execute(db: sqlite3.Connection, fence, request: DeletionRequest):
    store = SqliteDeletionStore(db, fence)
    result = store.execute(request)
    assert isinstance(result, Ok), result
    tallies = {tally.table: tally.removed for tally in result.value.tallies}
    return tallies


def test_a_conversation_deletion_removes_the_planner_records(
    db: sqlite3.Connection, fence, cycle, planner_store
) -> None:
    _write_unit(db, cycle, planner_store)
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV),
    )
    for table in PLANNER_TABLES:
        assert tallies.get(table) == 1, table
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 0
    )
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone() == (0,)
    assert db.execute("SELECT COUNT(*) FROM turn_record").fetchone() == (0,)


def test_an_all_learning_history_deletion_removes_the_planner_records(
    db: sqlite3.Connection, fence, cycle, planner_store
) -> None:
    _write_unit(db, cycle, planner_store)
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY),
    )
    for table in PLANNER_TABLES:
        assert tallies.get(table) == 1, table
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 0
    )
    # §20 keeps the transcript: the turn row survives its learning history.
    assert db.execute("SELECT COUNT(*) FROM turn_record").fetchone() == (1,)


def test_an_all_user_data_sweep_removes_the_planner_records(
    db: sqlite3.Connection, fence, cycle, planner_store
) -> None:
    _write_unit(db, cycle, planner_store)
    tallies = _execute(
        db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    for table in PLANNER_TABLES:
        assert tallies.get(table) == 1, table
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 0
    )
    assert table_counts(
        db, "decision_cycle", "turn_record", "conversation"
    ) == {"decision_cycle": 0, "turn_record": 0, "conversation": 0}


def test_a_degraded_cycles_rows_are_removed_too(
    db: sqlite3.Connection, fence, cycle, planner_store
) -> None:
    """The failure path leaves three rows and no decision; a sweep that only
    reached decisions would leak the status and the outcome."""

    from elc.planner.types import PlannerExecutionStatusValue
    from tests.phase8.conftest import failed_outcome

    outcome = failed_outcome(
        cycle.decision_cycle_id, PlannerExecutionStatusValue.DEGRADED
    )
    assert isinstance(
        planner_store.record_planner_cycle(
            turn_id=cycle.turn_id, outcome=outcome
        ),
        Ok,
    )
    tallies = _execute(
        db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    assert tallies.get("planner_decision") is None  # never written
    for table in (
        "planner_evaluation",
        "planner_execution_status",
        "runtime_decision_outcome",
    ):
        assert tallies.get(table) == 1, table
    assert table_counts(db, *PLANNER_TABLES) == dict.fromkeys(
        PLANNER_TABLES, 0
    )
