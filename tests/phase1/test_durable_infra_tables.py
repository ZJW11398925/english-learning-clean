"""VAL ⑦ — durable infrastructure tables exist with canonical shapes.

VAL ⑦: active_teaching_lock / projection_job 有 durable 表结构
(docs/DATA_MODEL.md §18 三列 durable unique; §22.1), plus the P1A schema
guards: turn_record CAS columns (§19/STATE_MACHINES §20) and the
input_envelope unique-where-present constraint (§4).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


# Full-literal introspection statements (no identifier assembly).
_PRAGMA_SQL = {
    "active_teaching_lock": "PRAGMA table_info(active_teaching_lock)",
    "projection_job": "PRAGMA table_info(projection_job)",
    "turn_record": "PRAGMA table_info(turn_record)",
    "interrupt_request": "PRAGMA table_info(interrupt_request)",
}


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    rows = db.execute(_PRAGMA_SQL[table]).fetchall()
    return [str(row[1]) for row in rows]


def _pk_columns(db: sqlite3.Connection, table: str) -> list[str]:
    rows = db.execute(_PRAGMA_SQL[table]).fetchall()
    return [str(row[1]) for row in sorted(rows, key=lambda r: r[5]) if row[5]]


def test_active_teaching_lock_three_column_durable_unique(
    db: sqlite3.Connection,
) -> None:
    """VAL ⑦: DATA_MODEL §18 Local V1 canonical durable representation —
    exactly conversation_id (UNIQUE/PK), moment_id (UNIQUE), state_version;
    no expiry/heartbeat column (§18: Local V1 不需要)."""
    assert _columns(db, "active_teaching_lock") == [
        "conversation_id",
        "moment_id",
        "state_version",
    ]
    assert _pk_columns(db, "active_teaching_lock") == ["conversation_id"]

    db.execute(
        "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
        " state_version) VALUES ('c1', 'm1', 1)"
    )
    # moment_id is UNIQUE across conversations…
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
            " state_version) VALUES ('c2', 'm1', 1)"
        )
    # …and conversation_id is the PK: one active focus per conversation.
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
            " state_version) VALUES ('c1', 'm2', 1)"
        )
    db.execute(
        "INSERT INTO active_teaching_lock (conversation_id, moment_id,"
        " state_version) VALUES ('c2', 'm2', 1)"
    )


def test_projection_job_section_22_1_shape(db: sqlite3.Connection) -> None:
    """VAL ⑦: DATA_MODEL §22.1 ProjectionJob columns verbatim, with the
    §22.1 status vocabulary enforced durably."""
    assert _columns(db, "projection_job") == [
        "projection_id",
        "projection_type",
        "source_turn_id",
        "source_turn_slice_hash",
        "base_domain_version",
        "status",
        "attempt_count",
        "created_at",
        "updated_at",
    ]
    assert _pk_columns(db, "projection_job") == ["projection_id"]

    db.execute(
        "INSERT INTO projection_job (projection_id, projection_type,"
        " source_turn_id, source_turn_slice_hash, base_domain_version,"
        " status, attempt_count, created_at, updated_at)"
        " VALUES ('p1', 'RELATIONSHIP_MEMORY', 't1', 'hash-1', 'dv-1',"
        " 'PENDING', 0, '2026-09-20', '2026-09-20')"
    )
    # Status is pinned to the §22.1 vocabulary.
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO projection_job (projection_id, projection_type,"
            " source_turn_id, source_turn_slice_hash, base_domain_version,"
            " status, attempt_count, created_at, updated_at)"
            " VALUES ('p2', 'RELATIONSHIP_MEMORY', 't1', 'hash-1', NULL,"
            " 'NOPE', 0, '2026-09-20', '2026-09-20')"
        )
    # Duplicate projection_id (PK) is rejected; revalidation is
    # source-aware + version-aware, never blind replay (§22.1).
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO projection_job (projection_id, projection_type,"
            " source_turn_id, source_turn_slice_hash, base_domain_version,"
            " status, attempt_count, created_at, updated_at)"
            " VALUES ('p1', 'RELATIONSHIP_MEMORY', 't1', 'hash-1', NULL,"
            " 'PENDING', 0, '2026-09-20', '2026-09-20')"
        )


def test_turn_record_carries_cas_and_epoch_columns(
    db: sqlite3.Connection,
) -> None:
    """turn_record exposes owner_epoch (DATA_MODEL §19) and state_version
    (STATE_MACHINES §20 CAS) as NOT NULL columns; status/turn_outcome are
    pinned to the STATE_MACHINES §10 vocabularies."""
    columns = {row[1]: row for row in db.execute(_PRAGMA_SQL["turn_record"])}
    assert columns["owner_epoch"][3] == 1  # notnull
    assert columns["state_version"][3] == 1  # notnull

    db.execute(
        "INSERT INTO conversation (conversation_id, persona_id, scene_id,"
        " created_at, status, next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', NULL, NULL, 'now', 'ACTIVE', 1, 1)"
    )
    db.execute(
        "INSERT INTO input_envelope (input_id, client_message_id,"
        " conversation_id, persona_id, scene_id, interaction_channel,"
        " raw_payload, received_at)"
        " VALUES ('i1', NULL, 'c1', NULL, NULL, 'TEXT', 'p', 'r')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO turn_record (turn_id, conversation_id,"
            " turn_sequence, input_id, status, runtime_version, started_at,"
            " updated_at, owner_epoch, state_version)"
            " VALUES ('t1', 'c1', 1, 'i1', 'NOT_A_STATUS', 'rv', 'now',"
            " 'now', 1, 1)"
        )


def test_input_envelope_unique_where_present(db: sqlite3.Connection) -> None:
    """DATA_MODEL §4 Unique: "client_message_id where present" — absent
    values never dedupe, present values do (partial unique index)."""
    base = (
        "INSERT INTO input_envelope (input_id, client_message_id,"
        " conversation_id, persona_id, scene_id, interaction_channel,"
        " raw_payload, received_at)"
    )
    conversation_row = (
        "INSERT INTO conversation (conversation_id, persona_id, scene_id,"
        " created_at, status, next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', NULL, NULL, 'now', 'ACTIVE', 1, 1)"
    )
    db.execute(conversation_row)
    db.execute(
        base + " VALUES ('i1', NULL, 'c1', NULL, NULL, 'TEXT', 'p', 'r')"
    )
    db.execute(
        base + " VALUES ('i2', NULL, 'c1', NULL, NULL, 'TEXT', 'p', 'r')"
    )
    db.execute(
        base
        + " VALUES ('i3', 'cm-1', 'c1', NULL, NULL, 'TEXT', 'p', 'r')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            base
            + " VALUES ('i4', 'cm-1', 'c1', NULL, NULL, 'TEXT', 'p', 'r')"
        )


def test_interrupt_request_table_shape(db: sqlite3.Connection) -> None:
    """RUNTIME_ARCHITECTURE §17.1: the interrupt rides the input queue
    (input_id PK) and points at the active turn/action."""
    assert _columns(db, "interrupt_request") == [
        "input_id",
        "conversation_id",
        "active_turn_id",
        "active_action_id",
        "reason",
        "created_at",
    ]
