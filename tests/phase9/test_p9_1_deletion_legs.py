"""P9-1 ③ — the five delivery tables are removal surface, in all three scopes.

Migration 0018 lands five tables whose five ``action_id`` foreign keys point
at ``generation_action_intent``, so BF-05's walks have to reach them before the
action row goes — "delete the action, keep its delivery fact" would be a
foreign-key refusal. The declaration half is asserted (three surfaces,
children-first, the three sets still partition the database), and the
behavioural half drives the **real** automatic opening (a real Moment, a real
action, a real turn) and then the real durable executor once per scope.

The orphan probe is the point of the third group: the one column outside these
five tables that names a delivery row is ``attempt_record.exposure_estimate_id``
(migration 0008, §17's '?', plain data), and after each sweep no row may still
name an estimate that is gone. One attempt row is placed for that probe; its
shipped writer (``TeachingStore.record_attempt``) records attempts in a
moment's EVALUATING slot, which needs the whole teaching-attempt chain, and the
property under test is the *postcondition* on removal — so the row goes in
directly with real foreign keys (the opening's moment and user turn), and the
table it lives in is one this cut does not otherwise touch.
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
from elc.persona.types import ValidatorDecision, ValidatorResult
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.types import ActionId, Ok
from elc.runtime.delivery_records import (
    ClientRenderAck,
    ExposureEstimate,
    PreDeliveryGuardResult,
    ServerDeliveryRecord,
)
from tests.phase7.conftest import CONV, TARGET_ID
from tests.phase8.p8_4_world import (
    acceptance_supply,
    begin_turn_ok,
    wiring,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator

TABLES = (
    "server_delivery_record",
    "client_render_ack",
    "exposure_estimate",
    "validator_result",
    "pre_delivery_guard_result",
)

#: §5.1 settings a conversation walk must not touch (§19 is about derived
#: state, and these are the user's own configuration).
KEPT_SETTINGS = ("user_profile", "goal_portfolio", "teaching_policy")

STARTED = "2026-09-24T09:00:00+00:00"
ACKED = "2026-09-24T09:00:02+00:00"
CREATED = "2026-09-24T09:00:01+00:00"
GUARDED = "2026-09-24T08:59:59+00:00"


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    }


def _counts(db: sqlite3.Connection, *tables: str) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


@pytest.fixture()
def opened(db: sqlite3.Connection, p8world) -> ActionId:
    """One real automatic opening in CONV: a Moment, a lock, an action."""

    begin_turn_ok(
        build_coordinator(
            p8world, automatic=wiring(p8world, supply=acceptance_supply())
        ),
        "cm-p9-1",
    )
    row = db.execute("SELECT action_id FROM generation_action_intent").fetchone()
    assert row is not None
    return ActionId(str(row[0]))


def _fill(db: sqlite3.Connection, fence, action_id: ActionId) -> None:
    """One row in each of the five tables, through the real store."""

    store = SqliteDeliveryRecordStore(db, fence)
    written = store.record_server_delivery(
        ServerDeliveryRecord(
            action_id=action_id,
            assistant_turn_id="at-p9-1",
            state="SENDING",
            sent_prefix="",
            last_chunk_seq=0,
            started_at=STARTED,
            terminal_at=None,
        )
    )
    assert isinstance(written, Ok), written
    ack = store.append_client_render_ack(
        ClientRenderAck(
            action_id=action_id,
            assistant_turn_id="at-p9-1",
            rendered_chunk_seq=0,
            rendered_text_hash="sha256:chunk-0",
            acked_at=ACKED,
            final_rendered=True,
        )
    )
    assert isinstance(ack, Ok), ack
    estimate = store.record_initial_exposure_estimate(
        ExposureEstimate(
            action_id=action_id,
            certainty="SERVER_SENT_UNCONFIRMED",
            exposure_level="PARTIAL",
            max_possible_exposure="PARTIAL",
            confirmed_exposure="NONE",
            derivation_reason="buffered delivery with no ACK yet",
        )
    )
    assert isinstance(estimate, Ok), estimate
    validator = store.append_validator_result(
        ValidatorResult(
            validator_result_id="vr-p9-1",
            action_id=action_id,
            attempt_no=1,
            decision=ValidatorDecision.ACCEPT,
            reason_codes=("STYLE_OK",),
            validator_version="validator-v1",
            created_at=CREATED,
        )
    )
    assert isinstance(validator, Ok), validator
    guard = store.append_pre_delivery_guard_result(
        PreDeliveryGuardResult(
            pre_delivery_guard_result_id="pg-p9-1",
            action_id=action_id,
            decision="VALID",
            reason_codes=(),
            checked_lineage_version="lineage-v1",
            created_at=GUARDED,
        )
    )
    assert isinstance(guard, Ok), guard
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 1)


def _attempt_against(db: sqlite3.Connection, action_id: ActionId) -> None:
    """One attempt_record naming this cut's estimate (the orphan probe's row).

    Real foreign keys (the opening's Moment and its user turn); the ``None``
    case is not written because the column is what the probe is about.
    """

    moment_id = str(
        db.execute("SELECT moment_id FROM teaching_moment").fetchone()[0]
    )
    user_turn_id = str(
        db.execute("SELECT user_turn_id FROM user_turn").fetchone()[0]
    )
    db.execute(
        "INSERT INTO attempt_record (attempt_id, moment_id, attempt_index,"
        " user_turn_id, support_level_before_attempt, answer_exposure_state,"
        " exposure_estimate_id, support_attribution_certainty,"
        " support_attribution_basis, created_at)"
        " VALUES (?, ?, ?, ?, 'NONE', 'NONE', ?,"
        " 'SERVER_SENT_UNCONFIRMED', ?, ?)",
        (
            "att-p9-1",
            moment_id,
            1,
            user_turn_id,
            str(action_id),
            "P9-1's estimate identity",
            CREATED,
        ),
    )
    db.commit()
    assert (
        db.execute(
            "SELECT COUNT(*) FROM attempt_record"
            " WHERE exposure_estimate_id IS NOT NULL"
        ).fetchone()[0]
        == 1
    )


def _execute(db: sqlite3.Connection, fence, request: DeletionRequest):
    result = SqliteDeletionStore(db, fence).execute(request)
    assert isinstance(result, Ok), result
    return {
        tally.table: tally.removed for tally in result.value.tallies
    }


def _orphans(db: sqlite3.Connection) -> int:
    return int(
        db.execute(
            "SELECT COUNT(*) FROM attempt_record"
            " WHERE exposure_estimate_id IS NOT NULL"
        ).fetchone()[0]
    )


# -- ① the declarations ------------------------------------------------------


def test_the_five_tables_are_in_the_three_scope_surfaces() -> None:
    for surface in (
        CONVERSATION_SWEPT_TABLES,
        LEARNING_HISTORY_SWEPT_TABLES,
        ALL_USER_DATA_SWEPT_TABLES,
    ):
        for table in TABLES:
            assert table in surface, table


def test_the_five_tables_are_not_in_the_narrower_scopes() -> None:
    """A target's, a pair's, a field's or a package's deletion has no business
    reaching a delivery fact — those rows hang off a conversation's turns."""

    for surface in (
        LEARNING_TARGET_SWEPT_TABLES,
        RELATIONSHIP_PAIR_SWEPT_TABLES,
        PROFILE_FIELD_SWEPT_TABLES,
        PERSONA_PACKAGE_SWEPT_TABLES,
    ):
        for table in TABLES:
            assert table not in surface, table


def test_the_retained_set_is_unchanged_and_the_sweep_grew_by_five() -> None:
    assert set(RETAINED_TABLES) == {
        "deletion_tombstone",
        "runtime_epoch",
        "schema_meta",
        "schema_migrations",
    }
    assert GLOBAL_CONTENT_TABLES == ()
    for table in TABLES:
        assert table in SWEPT_TABLES
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


@pytest.mark.parametrize("scope_index", [0, 1, 2])
def test_the_five_tables_are_children_first_in_every_surface(
    db: sqlite3.Connection, scope_index: int
) -> None:
    """Each delivery table is deleted before the action row it references,
    checked against the real foreign keys rather than by trying a delete."""

    surface = (
        CONVERSATION_SWEPT_TABLES,
        LEARNING_HISTORY_SWEPT_TABLES,
        ALL_USER_DATA_SWEPT_TABLES,
    )[scope_index]
    positions = {table: index for index, table in enumerate(surface)}
    for table in TABLES:
        assert positions[table] < positions["generation_action_intent"], table
        for row in db.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            parent = str(row[2])
            if parent in positions:
                assert positions[parent] > positions[table], (
                    f"{table} references {parent} too late"
                )


def test_the_deleter_is_the_module_that_deletes_them() -> None:
    from tests.conftest import REPO_ROOT
    from tests.phase3.sql_write_scan import write_statements

    deleter = write_statements(
        REPO_ROOT / "src" / "elc" / "deletion" / "store.py"
    )
    for table in TABLES:
        assert deleter[table] == ("DELETE",), table
    appender = write_statements(
        REPO_ROOT / "src" / "elc" / "platform" / "db" / "delivery_store.py"
    )
    assert appender["server_delivery_record"] == ("INSERT", "UPDATE")
    for table in TABLES[1:]:
        assert appender[table] == ("INSERT",), table


# -- ② the three scopes remove the rows --------------------------------------


def test_a_conversation_deletion_removes_the_delivery_rows(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    before = _counts(db, *KEPT_SETTINGS)
    tallies = _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV),
    )
    for table in TABLES:
        assert tallies.get(table) == 1, table
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 0)
    assert _counts(db, *KEPT_SETTINGS) == before
    assert db.execute("SELECT COUNT(*) FROM conversation").fetchone() == (0,)


def test_an_all_learning_history_deletion_removes_the_delivery_rows(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    tallies = _execute(
        db, fence, DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY)
    )
    for table in TABLES:
        assert tallies.get(table) == 1, table
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 0)
    # §20 keeps the transcript: the conversation row survives its history.
    assert db.execute("SELECT COUNT(*) FROM conversation").fetchone() == (1,)


def test_an_all_user_data_sweep_removes_the_delivery_rows(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    tallies = _execute(
        db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA)
    )
    for table in TABLES:
        assert tallies.get(table) == 1, table
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 0)
    assert _counts(db, "conversation", "turn_record", "generation_action_intent") == {
        "conversation": 0,
        "turn_record": 0,
        "generation_action_intent": 0,
    }


# -- ③ the orphan probe ------------------------------------------------------


def test_no_estimate_reference_survives_a_conversation_walk(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    _attempt_against(db, opened)
    _execute(
        db,
        fence,
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV),
    )
    assert _orphans(db) == 0
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone() == (0,)


def test_no_estimate_reference_survives_the_learning_history_walk(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    _attempt_against(db, opened)
    _execute(
        db, fence, DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY)
    )
    assert _orphans(db) == 0


def test_no_estimate_reference_survives_the_whole_user_sweep(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    _attempt_against(db, opened)
    _execute(db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA))
    assert _orphans(db) == 0


def test_no_row_points_at_a_removed_action_after_a_sweep(
    db: sqlite3.Connection, fence, opened
) -> None:
    """The zero-orphan shape stated over the foreign keys this cut landed:
    after the sweep, no row of the five tables names an action that is gone —
    they are empty, and the action row is empty with them."""

    _fill(db, fence, opened)
    _execute(db, fence, DeletionRequest(scope=DeletionScope.ALL_USER_DATA))
    alive = {
        str(row[0])
        for row in db.execute("SELECT action_id FROM generation_action_intent")
    }
    referencing = 0
    for table in TABLES:
        referencing += int(
            db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE action_id IS NOT NULL"
            ).fetchone()[0]
        )
    assert referencing == 0
    assert alive == set()


# -- ④ the scopes that must not touch them -----------------------------------


def test_the_learning_target_scope_leaves_the_delivery_rows_alone(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    tallies = _execute(
        db,
        fence,
        DeletionRequest(
            scope=DeletionScope.LEARNING_TARGET,
            target_id=TARGET_ID,
            target_type="RESOURCE",
        ),
    )
    for table in TABLES:
        assert tallies.get(table) is None, table
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 1)


def test_the_relationship_pair_scope_leaves_the_delivery_rows_alone(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    tallies = _execute(
        db,
        fence,
        DeletionRequest(
            scope=DeletionScope.RELATIONSHIP_PAIR, persona_id="persona-p9-1"
        ),
    )
    for table in TABLES:
        assert tallies.get(table) is None, table
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 1)


def test_the_profile_field_scope_leaves_the_delivery_rows_alone(
    db: sqlite3.Connection, fence, opened
) -> None:
    _fill(db, fence, opened)
    result = SqliteDeletionStore(db, fence).execute(
        DeletionRequest(
            scope=DeletionScope.PROFILE_FIELD, field_key="profile_city"
        )
    )
    # The S44 scope is fail-closed in V1 (registered in the package's own
    # notes): whether it refuses or clears facts, the delivery tables are not
    # part of its surface.
    if isinstance(result, Ok):
        for tally in result.value.tallies:
            assert tally.table not in TABLES, tally.table
    else:
        assert result.error.code is not None
    assert _counts(db, *TABLES) == dict.fromkeys(TABLES, 1)
