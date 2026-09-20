"""VAL ④ — migration 0006 decision_cycle: the canonical §4 table, the
UNIQUE key, and the P3-1 no-write-face fence (P3-0 ④).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.db import connection, migrations
from tests.conftest import REPO_ROOT, SRC_ROOT

# DATA_MODEL §4:165-192 verbatim column list (the thirteen §4 columns
# plus created_at; relationship_view_version / planner_decision_id /
# gate_decision_id carry the §4 trailing '?').
DECISION_CYCLE_COLUMNS = [
    "decision_cycle_id",
    "turn_id",
    "cycle_index",
    "learning_snapshot_id",
    "evidence_watermark",
    "curriculum_version",
    "goal_version",
    "schedule_version",
    "policy_version",
    "context_view_version",
    "relationship_view_version",
    "planner_decision_id",
    "gate_decision_id",
    "created_at",
]


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


def _columns(db: sqlite3.Connection) -> list[str]:
    return [str(row[1]) for row in db.execute("PRAGMA table_info(decision_cycle)")]


def _seed_turn(db: sqlite3.Connection) -> None:
    db.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c-dc', 'now', 'ACTIVE', 2, 2)"
    )
    db.execute(
        "INSERT INTO input_envelope (input_id, conversation_id,"
        " interaction_channel, raw_payload, received_at)"
        " VALUES ('i-dc', 'c-dc', 'TEXT', 'p', 'now')"
    )
    db.execute(
        "INSERT INTO turn_record (turn_id, conversation_id,"
        " turn_sequence, input_id, status, runtime_version, started_at,"
        " updated_at, owner_epoch, state_version)"
        " VALUES ('t-dc', 'c-dc', 1, 'i-dc', 'USER_COMMITTED', 'rv',"
        " 'now', 'now', 1, 1)"
    )
    db.commit()


def test_decision_cycle_columns_match_canonical(db: sqlite3.Connection) -> None:
    assert sorted(_columns(db)) == sorted(DECISION_CYCLE_COLUMNS)


def test_migration_list_and_schema_version(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT migration_id FROM schema_migrations ORDER BY migration_id"
    ).fetchall()
    assert [row[0] for row in rows] == [
        "0001_bootstrap",
        "0002_conversation_core",
        "0003_generation_provider",
        "0004_learning_evidence",
        "0005_learner_target_state",
        "0006_decision_cycle",
    ]
    version = db.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert version is not None and version[0] == "6"


def test_optional_columns_are_exactly_the_three_marked(
    db: sqlite3.Connection,
) -> None:
    """§4 marks exactly relationship_view_version / planner_decision_id /
    gate_decision_id with '?': those three accept NULL, every other
    column refuses it. (decision_cycle_id also shows notnull=0 in PRAGMA
    table_info — the SQLite TEXT-PRIMARY-KEY quirk shared by every
    migration in this repo; a NULL id is still rejected behaviorally by
    the PRIMARY KEY uniqueness on first duplicate, and ids are minted,
    never null, by every caller.)"""

    nullmap = {
        str(row[1]): bool(row[3])
        for row in db.execute("PRAGMA table_info(decision_cycle)")
    }
    nullable = sorted(name for name, notnull in nullmap.items() if not notnull)
    assert nullable == [
        "decision_cycle_id",  # SQLite TEXT-PK quirk (notnull=0 in PRAGMA)
        "gate_decision_id",
        "planner_decision_id",
        "relationship_view_version",
    ]
    _seed_turn(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO decision_cycle (decision_cycle_id, turn_id,"
            " cycle_index, learning_snapshot_id, evidence_watermark,"
            " curriculum_version, created_at)"
            " VALUES ('dc-bad', 't-dc', 0, 'lsnap-x', 1, 'cv-1', 'now')"
        )
    db.rollback()


def test_unique_turn_cycle_index_enforced(db: sqlite3.Connection) -> None:
    """§4 Unique (turn_id, cycle_index): one row per coordination slot;
    the next cycle_index of the same turn is a distinct row."""

    _seed_turn(db)
    insert = (
        "INSERT INTO decision_cycle (decision_cycle_id, turn_id,"
        " cycle_index, learning_snapshot_id, evidence_watermark,"
        " curriculum_version, goal_version, schedule_version,"
        " policy_version, context_view_version, relationship_view_version,"
        " planner_decision_id, gate_decision_id, created_at)"
        " VALUES (?, 't-dc', ?, 'lsnap-1', 3, 'cv-1', 'gv-1', 'sv-1',"
        " 'pv-1', 'cxv-1', NULL, NULL, NULL, 'now')"
    )
    db.execute(insert, ("dc-1", 0))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, ("dc-2", 0))
    db.execute(insert, ("dc-3", 1))
    db.commit()
    rows = db.execute(
        "SELECT decision_cycle_id FROM decision_cycle"
        " WHERE turn_id = 't-dc' ORDER BY cycle_index"
    ).fetchall()
    assert [row[0] for row in rows] == ["dc-1", "dc-3"]


def test_no_write_face_until_p3_1() -> None:
    """P3-0 scope fence: no src code writes decision_cycle rows — the
    write face lands with P3-1 lineage semantics (plain-source scan;
    comments may mention the table, INSERT/UPDATE/DELETE may not)."""

    offenders: list[str] = []
    verbs = (
        "INSERT INTO decision_cycle",
        "UPDATE decision_cycle",
        "DELETE FROM decision_cycle",
    )
    for path in sorted(SRC_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for verb in verbs:
            if verb in text:
                offenders.append(f"{path}:{verb}")
    assert not offenders, offenders


def test_migrations_directory_0006_is_newest() -> None:
    """0006 is the newest migration; nothing ahead of the P3-0 slice
    smuggles schema (the migration runner is filename-ordered)."""

    names = sorted(
        path.name for path in (REPO_ROOT / "migrations").glob("*.sql")
    )
    assert names[-1] == "0006_decision_cycle.sql"
