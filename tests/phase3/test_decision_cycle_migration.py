"""VAL ① (migration half) — migration 0007 teaching lineage.

P3-0's ``decision_cycle`` table test, carried forward to P3-1A:

- the three new §14.1/§15 tables exist with their canonical column sets
  word for word;
- the §4 ``decision_cycle`` column set is unchanged, and its
  snapshot/version columns accept NULL after 0007 (the legacy export
  requires the honest all-NULL bindings — the migration header carries the
  full rationale);
- schema_version is 13 (0013_planner_constraint is the newest migration; it
  read 12 while 0012_schedule_review was the newest, 11 while
  0011_goal_policy_focus was, 10 while 0010_episode_and_user_config was, 9
  while 0009_relationship_contracts was, and 8 while 0008_attempt_records
  was);
- the decision_cycle / gate / moment write faces belong to their owning
  adapters only (AST-based scan, P3-0 review F3 — a substring scan is
  defeatable by multi-line SQL literals).
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.db import connection, migrations
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
    SRC_ROOT,
)
from tests.phase3.sql_write_scan import write_targets

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

# DATA_MODEL §14.1 gate_decision, word for word.
GATE_DECISION_COLUMNS = [
    "gate_decision_id",
    "decision_cycle_id",
    "candidate_id",
    "context",
    "decision",
    "reason_codes",
    "policy_version",
    "created_at",
]

# DATA_MODEL §14.1 gate_execution_status, word for word.
GATE_EXECUTION_STATUS_COLUMNS = [
    "gate_execution_status_id",
    "decision_cycle_id",
    "moment_id",
    "gate_context",
    "authorization_basis",
    "authorization_status",
    "status",
    "missing_or_unknown",
    "created_at",
]

# DATA_MODEL §15 teaching_moment, word for word (thirty columns).
TEACHING_MOMENT_COLUMNS = [
    "moment_id",
    "conversation_id",
    "persona_id",
    "source",
    "decision_cycle_id",
    "candidate_id",
    "gate_decision_id",
    "focus_target",
    "supporting_targets",
    "target_mode",
    "learning_intent",
    "evidence_modality",
    "evidence_goal",
    "preferred_support_ceiling",
    "learning_snapshot_id",
    "evidence_watermark",
    "curriculum_version",
    "content_version",
    "policy_version",
    "lifecycle_state",
    "presentation_phase",
    "attempt_index",
    "support_level",
    "completion_outcome",
    "abort_reason",
    "state_version",
    "created_at",
    "opened_at",
    "teaching_terminal_at",
    "closed_at",
]

#: The P3-1A tables and the only modules allowed to write them (the
#: Runtime-owned DecisionCycle adapter + the Teaching domain store).
P3_1A_WRITE_OWNERS: dict[str, set[str]] = {
    "platform/db/decision_cycle_store.py": {"decision_cycle"},
    "teaching/store.py": {
        "gate_decision",
        "gate_execution_status",
        "teaching_moment",
    },
}


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in db.execute(f"PRAGMA table_info({table})")]


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
    assert sorted(_columns(db, "decision_cycle")) == sorted(
        DECISION_CYCLE_COLUMNS
    )


def test_gate_and_moment_columns_match_canonical(db: sqlite3.Connection) -> None:
    assert sorted(_columns(db, "gate_decision")) == sorted(
        GATE_DECISION_COLUMNS
    )
    assert sorted(_columns(db, "gate_execution_status")) == sorted(
        GATE_EXECUTION_STATUS_COLUMNS
    )
    assert sorted(_columns(db, "teaching_moment")) == sorted(
        TEACHING_MOMENT_COLUMNS
    )
    # Column order is the §15 order, word for word.
    assert _columns(db, "teaching_moment") == TEACHING_MOMENT_COLUMNS
    assert _columns(db, "gate_decision") == GATE_DECISION_COLUMNS
    assert _columns(db, "gate_execution_status") == (
        GATE_EXECUTION_STATUS_COLUMNS
    )


def test_migration_list_and_schema_version(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT migration_id FROM schema_migrations ORDER BY migration_id"
    ).fetchall()
    # 0008_attempt_records joins in Phase 3 P3-1B (TASK-…2babb21e.2 ①): the
    # attempt / evaluation tables plus the F8 vocabularies;
    # 0009_relationship_contracts in Phase 4 P4-0 (TASK-…5ba74efc.84 ①③);
    # 0010_episode_and_user_config in Phase 4 P4-3 (TASK-OPI-4d516e4f.19 ⑥);
    # 0011_goal_policy_focus in Phase 6 P6-0 (TASK-OPI-a68fd9eb.48 ③);
    # 0012_schedule_review in Phase 6 P6-1 (TASK-OPI-6259f6fd.12 ②① — the
    # §5.2 schedule_item / review_event rows); 0013_planner_constraint in
    # Phase 6 P6-3 (TASK-OPI-5a0be06d.20 ③ — the §9 constraint row).
    # The ids are declared once in tests.conftest.
    assert [row[0] for row in rows] == list(MIGRATION_IDS)
    version = db.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    # The stamp is the newest migration's (this pin read "10" while 0010 was
    # the head, "11" with P6-0's 0011).
    assert version is not None and version[0] == SCHEMA_HEAD_VERSION


def test_snapshot_columns_accept_null_for_legacy_cycles(
    db: sqlite3.Connection,
) -> None:
    """Migration 0007 rebuilds decision_cycle so the snapshot/version
    columns accept NULL: the legacy export (and the Phase 3 cycles whose
    Curriculum/Goal/Schedule/Policy sources have not arrived) must be able
    to say "no source" honestly instead of fabricating a stamp. The §4
    '?' columns and the structural columns are unchanged; every other
    column still refuses NULL.

    (P3-0 asserted exactly the three §4 '?' columns; the 0007 relaxation
    is the semantic change this slice carries — adjudicated in the task
    book ①d and documented in the migration header.)
    """

    nullmap = {
        str(row[1]): bool(row[3])
        for row in db.execute("PRAGMA table_info(decision_cycle)")
    }
    nullable = sorted(name for name, notnull in nullmap.items() if not notnull)
    assert nullable == [
        "context_view_version",
        "curriculum_version",
        "decision_cycle_id",  # SQLite TEXT-PK quirk (notnull=0 in PRAGMA)
        "evidence_watermark",
        "gate_decision_id",
        "goal_version",
        "learning_snapshot_id",
        "planner_decision_id",
        "policy_version",
        "relationship_view_version",
        "schedule_version",
    ]
    _seed_turn(db)
    # The structural columns still refuse NULL: turn_id / cycle_index /
    # created_at.
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO decision_cycle (decision_cycle_id, cycle_index,"
            " created_at) VALUES ('dc-bad', 0, 'now')"
        )
    db.rollback()
    # The all-NULL legacy shape is legal now (and is what 0007 exported).
    db.execute(
        "INSERT INTO decision_cycle (decision_cycle_id, turn_id, cycle_index,"
        " created_at) VALUES ('dc-legacy', 't-dc', 0, 'now')"
    )
    db.commit()
    row = db.execute(
        "SELECT learning_snapshot_id, evidence_watermark, planner_decision_id"
        " FROM decision_cycle WHERE decision_cycle_id = 'dc-legacy'"
    ).fetchone()
    assert row is not None and tuple(row) == (None, None, None)


def test_unique_turn_cycle_index_enforced(db: sqlite3.Connection) -> None:
    """§4/§25 Unique (turn_id, cycle_index) survives the 0007 rebuild:
    one row per coordination slot; cycle_index 1 is a distinct row."""

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


def test_write_faces_belong_to_the_owning_adapters_only() -> None:
    """AST-based write-face pin (P3-0 review F3): the decision_cycle / gate
    / moment tables are written only by the Runtime-owned DecisionCycle
    adapter and the Teaching domain store — the multi-line-literal-proof
    replacement for P3-0's substring scan (that fence is retired: P3-1A is
    exactly the slice that lands the write faces)."""

    p3_1a_tables = {
        "decision_cycle",
        "gate_decision",
        "gate_execution_status",
        "teaching_moment",
    }
    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        relative = path.relative_to(SRC_ROOT).as_posix()
        written = write_targets(path) & p3_1a_tables
        allowed = P3_1A_WRITE_OWNERS.get(relative, set())
        for table in sorted(written - allowed):
            offenders.append(f"{relative} writes {table}")
    assert not offenders, offenders

    # Non-vacuous: the owning adapters really do write their tables (a
    # broken fold would otherwise pass silently).
    assert write_targets(SRC_ROOT / "platform" / "db" / "decision_cycle_store.py") >= {
        "decision_cycle"
    }
    teaching_writes = write_targets(SRC_ROOT / "teaching" / "store.py")
    assert {"gate_decision", "gate_execution_status", "teaching_moment"} <= (
        teaching_writes
    )


def test_migrations_directory_0013_is_newest() -> None:
    """0013 is the newest migration; nothing ahead of the P6-3 slice
    smuggles schema (the migration runner is filename-ordered). The pin
    moves with each slice's newest migration — it read 0008 while P3-1B was
    the head, then 0009 while P4-0/P4-1/P4-2 were, 0010 with P4-3 (the slice
    that added the episode projection and the profile rows), 0011 with P6-0
    (the goal / policy / focus rows), 0012 with P6-1 (the §5.2
    schedule_item / review_event rows), and 0013 with P6-3 (the §9
    planner_constraint row)."""

    names = sorted(
        path.name for path in (REPO_ROOT / "migrations").glob("*.sql")
    )
    assert names[-1] == SCHEMA_HEAD_FILE
