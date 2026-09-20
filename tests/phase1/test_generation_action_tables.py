"""P1B VAL ① — generation/provider durable tables match DATA_MODEL §20
word for word, and the GenerationActionStatus vocabulary matches
STATE_MACHINES §14 word for word (correcting the Phase 0 six-value
deviation, DEC-OPI-091f35c3.7)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations
from elc.runtime.types import GenerationActionStatus

#: docs/STATE_MACHINES.md §14 code block, lines 465-472, word for word.
SM14_GENERATION_ACTION_STATUS = (
    "PREPARED",
    "REQUESTED",
    "GENERATING",
    "VALIDATING",
    "READY_TO_DELIVER",
    "DELIVERING",
    "TERMINAL",
)

#: docs/DATA_MODEL.md §20 GenerationActionIntent column block, in order.
DM20_GENERATION_ACTION_INTENT_COLUMNS = (
    "action_id",
    "turn_id",
    "decision_cycle_id",
    "moment_id",
    "assistant_turn_id",
    "action_type",
    "generation_contract_id",
    "status",
    "attempt_count",
    "owner_epoch",  # DATA_MODEL §19 lease physical mapping (adjudicated)
    "created_at",
)

#: docs/DATA_MODEL.md §20 ProviderAttempt column block, in order.
DM20_PROVIDER_ATTEMPT_COLUMNS = (
    "provider_attempt_id",
    "action_id",
    "attempt_no",
    "provider_request_id",
    "request_hash",
    "status",
    "result_hash",
    "created_at",
    "terminal_at",
)

#: docs/DATA_MODEL.md §20 action types block, word for word.
DM20_ACTION_TYPES = (
    "NORMAL_PERSONA_REPLY",
    "TEACHING_OPEN",
    "TEACHING_HINT",
    "TEACHING_REVEAL",
    "TEACHING_EXPLANATION",
    "PERSONA_RESUME",
)


#: Full-literal introspection statements (no identifier assembly).
_PRAGMA_SQL = {
    "generation_action_intent": "PRAGMA table_info(generation_action_intent)",
    "provider_attempt": "PRAGMA table_info(provider_attempt)",
}

_INSERT_ACTION_SQL = (
    "INSERT INTO generation_action_intent (action_id, turn_id,"
    " assistant_turn_id, action_type, generation_contract_id,"
    " status, attempt_count, owner_epoch, created_at)"
    " VALUES (?, 't1', ?, ?, 'gc', ?, 0, 1,"
    " '2026-09-20T00:00:00+00:00')"
)

_INSERT_ATTEMPT_SQL = (
    "INSERT INTO provider_attempt (provider_attempt_id, action_id,"
    " attempt_no, request_hash, status, created_at, terminal_at)"
    " VALUES (?, 'ga1', ?, 'h', 'FAILED', '2026-09-20T00:00:00+00:00',"
    " '2026-09-20T00:00:00+00:00')"
)


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


def _seed_turn(db: sqlite3.Connection) -> None:
    """Seed one conversation + input + USER_COMMITTED turn (parents of a
    generation action); all values bound."""

    db.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c', '2026-09-20T00:00:00+00:00', 'ACTIVE', 1, 1)"
    )
    db.execute(
        "INSERT INTO input_envelope (input_id, conversation_id,"
        " interaction_channel, raw_payload, received_at)"
        " VALUES ('i1', 'c', 'TEXT', 'p', '2026-09-20T00:00:00+00:00')"
    )
    db.execute(
        "INSERT INTO turn_record (turn_id, conversation_id, turn_sequence,"
        " input_id, status, runtime_version, started_at, updated_at,"
        " owner_epoch, state_version)"
        " VALUES ('t1', 'c', 1, 'i1', 'USER_COMMITTED', 'v',"
        " '2026-09-20T00:00:00+00:00', '2026-09-20T00:00:00+00:00', 1, 1)"
    )


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    rows = db.execute(_PRAGMA_SQL[table]).fetchall()
    return [str(row[1]) for row in rows]


def test_generation_action_status_is_sm14_seven_values() -> None:
    """VAL ①: the enum is §14 word for word — seven values, same order, no
    Phase 0 leftovers (PENDING/IN_FLIGHT/ACCEPTED/SUPERSEDED/CANCELLED/
    FAILED are gone)."""

    assert [status.value for status in GenerationActionStatus] == list(
        SM14_GENERATION_ACTION_STATUS
    )
    for legacy in ("PENDING", "IN_FLIGHT", "ACCEPTED", "SUPERSEDED",
                   "CANCELLED", "FAILED"):
        assert not hasattr(GenerationActionStatus, legacy)


def test_generation_action_intent_columns_are_dm20(
    db: sqlite3.Connection,
) -> None:
    """VAL ①: durable column set = §20 GenerationActionIntent verbatim
    (+ owner_epoch, DATA_MODEL §19 "GenerationAction owner/action state")."""

    assert _columns(db, "generation_action_intent") == list(
        DM20_GENERATION_ACTION_INTENT_COLUMNS
    )


def test_provider_attempt_columns_are_dm20(db: sqlite3.Connection) -> None:
    """VAL ①: durable column set = §20 ProviderAttempt verbatim."""

    assert _columns(db, "provider_attempt") == list(DM20_PROVIDER_ATTEMPT_COLUMNS)


def test_status_check_vocabulary_is_sm14(db: sqlite3.Connection) -> None:
    """VAL ①: the durable CHECK enforces exactly the §14 seven values."""

    _seed_turn(db)
    for status in SM14_GENERATION_ACTION_STATUS:
        db.execute(
            _INSERT_ACTION_SQL,
            (f"ga-{status}", f"at-{status}", "NORMAL_PERSONA_REPLY", status),
        )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            _INSERT_ACTION_SQL,
            ("ga-legacy", "at-legacy", "NORMAL_PERSONA_REPLY", "IN_FLIGHT"),
        )


def test_action_type_check_vocabulary_is_dm20(db: sqlite3.Connection) -> None:
    """VAL ①: the durable CHECK enforces the §20 action types verbatim."""

    _seed_turn(db)
    for action_type in DM20_ACTION_TYPES:
        db.execute(
            _INSERT_ACTION_SQL,
            (f"ga-{action_type}", f"at-{action_type}", action_type, "PREPARED"),
        )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            _INSERT_ACTION_SQL,
            ("ga-bad", "at-bad", "CHAT_REPLY", "PREPARED"),
        )


def test_attempt_no_unique_per_action_dm25(db: sqlite3.Connection) -> None:
    """DATA_MODEL §25: UNIQUE(action_id, provider_attempt attempt_no) —
    the durable shape of action-level retry (one stable action, one row per
    attempt)."""

    _seed_turn(db)
    db.execute(
        "INSERT INTO generation_action_intent (action_id, turn_id,"
        " assistant_turn_id, action_type, generation_contract_id,"
        " status, attempt_count, owner_epoch, created_at)"
        " VALUES ('ga1', 't1', 'at1', 'NORMAL_PERSONA_REPLY', 'gc',"
        " 'TERMINAL', 2, 1, '2026-09-20T00:00:00+00:00')"
    )
    for attempt_no in (1, 2):
        db.execute(_INSERT_ATTEMPT_SQL, (f"pa{attempt_no}", attempt_no))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(_INSERT_ATTEMPT_SQL, ("pa3", 1))
