"""VAL ① (backfill half) — migration 0007's legacy DecisionCycle export.

The 0007 script is applied to a database that already carries pre-lineage
data (a DB that ran migrations 0001–0006 and produced turns/actions), which
is exactly how the migration meets a real app.db:

- every turn that owns at least one GenerationActionIntent gets exactly one
  deterministic legacy cycle (cycle_index 0, 'dcy-legacy-' || turn_id,
  created_at = turn_record.started_at, all snapshot/version/planner/gate
  fields NULL);
- historical actions are re-pointed at that cycle;
- only NONTERMINAL turns get their active_decision_cycle_id set (a
  terminal historical turn keeps NULL — the active pointer is not an audit
  pointer);
- re-running the export statements is a no-op (idempotent by construction);
- the generation_action_intent rebuild preserves every row (including
  historical NULL moment_id values) and tightens decision_cycle_id to
  NOT NULL + FK(decision_cycle);
- provider_attempt rows survive the parent rebuild untouched.

The pre/post split is built by copying migration files into ``tmp_path``:
``apply_migrations`` is filename-ordered and idempotent per directory, so
the test can seed data between the two stages. Phase 3 P3-1B's 0008 is a
*post* stage too (it rebuilds ``teaching_moment``'s children and needs the
0007 tables), so the split is "everything up to and including 0006" vs
"0007 and everything after it".
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from elc.platform.db import connection, migrations
from tests.conftest import REPO_ROOT

MIGRATIONS_DIR = REPO_ROOT / "migrations"
PRE_0007 = "0007_teaching_lineage.sql"


@pytest.fixture()
def staged_dirs(tmp_path: Path) -> tuple[Path, Path]:
    pre = tmp_path / "pre"
    post = tmp_path / "post"
    pre.mkdir()
    post.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        target = post if path.name >= PRE_0007 else pre
        shutil.copy(path, target / path.name)
    return pre, post


def _seed_pre_lineage_data(conn: sqlite3.Connection) -> None:
    """One terminal turn and one nonterminal turn, each with an action; the
    terminal action carries a provider attempt."""

    conn.execute(
        "INSERT INTO runtime_epoch (epoch, opened_at) VALUES (1, 'now')"
    )
    conn.execute(
        "INSERT INTO conversation (conversation_id, created_at, status,"
        " next_turn_sequence, next_message_sequence)"
        " VALUES ('c1', 'now', 'ACTIVE', 3, 3)"
    )
    conn.execute(
        "INSERT INTO input_envelope (input_id, conversation_id,"
        " interaction_channel, raw_payload, received_at)"
        " VALUES ('i1', 'c1', 'TEXT', 'p', 'now')"
    )
    conn.execute(
        "INSERT INTO input_envelope (input_id, conversation_id,"
        " interaction_channel, raw_payload, received_at)"
        " VALUES ('i2', 'c1', 'TEXT', 'p', 'now')"
    )
    conn.execute(
        "INSERT INTO turn_record (turn_id, conversation_id, turn_sequence,"
        " input_id, status, runtime_version, started_at, updated_at,"
        " owner_epoch, state_version)"
        " VALUES ('t-done', 'c1', 1, 'i1', 'COMPLETED', 'rv',"
        " '2026-01-01T00:00:00+00:00', 'now', 1, 4)"
    )
    conn.execute(
        "INSERT INTO turn_record (turn_id, conversation_id, turn_sequence,"
        " input_id, status, runtime_version, started_at, updated_at,"
        " owner_epoch, state_version)"
        " VALUES ('t-live', 'c1', 2, 'i2', 'GENERATING', 'rv',"
        " '2026-01-02T00:00:00+00:00', 'now', 1, 2)"
    )
    for action_id, turn_id, created in (
        ("a-done", "t-done", "2026-01-01T00:00:01+00:00"),
        ("a-live", "t-live", "2026-01-02T00:00:01+00:00"),
    ):
        conn.execute(
            "INSERT INTO generation_action_intent (action_id, turn_id,"
            " decision_cycle_id, moment_id, assistant_turn_id, action_type,"
            " generation_contract_id, status, attempt_count, owner_epoch,"
            " created_at) VALUES (?, ?, NULL, NULL, ?,"
            " 'NORMAL_PERSONA_REPLY', 'gc', 'PREPARED', 0, 1, ?)",
            (action_id, turn_id, f"at-{action_id}", created),
        )
    conn.execute(
        "INSERT INTO provider_attempt (provider_attempt_id, action_id,"
        " attempt_no, provider_request_id, request_hash, status, result_hash,"
        " created_at, terminal_at)"
        " VALUES ('pa-1', 'a-done', 1, NULL, 'hash', 'SUCCEEDED', 'rh',"
        " 'now', 'now')"
    )
    conn.commit()


def _apply(conn: sqlite3.Connection, stage: Path) -> None:
    migrations.apply_migrations(conn, stage)


def test_backfill_is_deterministic_and_preserves_history(
    staged_dirs: tuple[Path, Path],
) -> None:
    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    _apply(conn, pre)
    _seed_pre_lineage_data(conn)
    _apply(conn, post)

    cycles = conn.execute(
        "SELECT decision_cycle_id, turn_id, cycle_index, learning_snapshot_id,"
        " evidence_watermark, curriculum_version, goal_version,"
        " schedule_version, policy_version, context_view_version,"
        " relationship_view_version, planner_decision_id, gate_decision_id,"
        " created_at FROM decision_cycle ORDER BY turn_id"
    ).fetchall()
    assert len(cycles) == 2
    done, live = cycles
    assert done[0] == "dcy-legacy-t-done"
    assert done[1] == "t-done"
    assert done[2] == 0
    assert done[3:13] == (None,) * 10  # all bindings NULL
    assert done[13] == "2026-01-01T00:00:00+00:00"  # turn_record.started_at
    assert live[0] == "dcy-legacy-t-live"
    assert live[13] == "2026-01-02T00:00:00+00:00"

    # Historical actions re-pointed; historical NULL moments stay NULL —
    # before this migration no writer ever set a non-NULL moment_id (the
    # teaching tables did not exist), and the new nullable FK admits the
    # honest historical state.
    actions = conn.execute(
        "SELECT action_id, decision_cycle_id, moment_id"
        " FROM generation_action_intent ORDER BY action_id"
    ).fetchall()
    assert actions == [
        ("a-done", "dcy-legacy-t-done", None),
        ("a-live", "dcy-legacy-t-live", None),
    ]

    # Active pointer: only the nonterminal turn.
    pointers = conn.execute(
        "SELECT turn_id, active_decision_cycle_id FROM turn_record"
        " ORDER BY turn_id"
    ).fetchall()
    assert pointers == [
        ("t-done", None),
        ("t-live", "dcy-legacy-t-live"),
    ]

    # The child table survived the parent rebuild.
    attempts = conn.execute(
        "SELECT provider_attempt_id, action_id, attempt_no, status,"
        " result_hash FROM provider_attempt"
    ).fetchall()
    assert attempts == [("pa-1", "a-done", 1, "SUCCEEDED", "rh")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert not {name for name in tables if name.endswith(("_v7", "_backup"))}
    # The post stage runs every migration from 0007 on, so the version after
    # it is the newest one (P6-0's 0011_goal_policy_focus: this pin read 10
    # while P4-3's 0010_episode_and_user_config was the head).
    assert migrations.schema_version(conn) == "11"
    conn.close()


def test_backfill_export_statements_are_idempotent(
    staged_dirs: tuple[Path, Path],
) -> None:
    """Re-running the export statements (the 0007 body's INSERT…SELECT /
    UPDATE…WHERE) changes nothing: the guards are structural, not one-shot.
    """

    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    _apply(conn, pre)
    _seed_pre_lineage_data(conn)
    _apply(conn, post)

    script = (MIGRATIONS_DIR / PRE_0007).read_text(encoding="utf-8")
    # Only the export statements (section 5) are re-runnable after 0007:
    # the rebuild sections carry DDL that must not run twice. Both markers
    # are taken at line starts (splitting mid-comment would leave prose
    # outside a comment, which is a syntax error).
    start = script.index("-- 5. Legacy cycle backfill")
    start = script.rindex("\n", 0, start) + 1
    end = script.index("-- 6. generation_action_intent rebuild", start)
    end = script.rindex("\n", 0, end) + 1
    export_sql = script[start:end]
    snapshot = conn.execute(
        "SELECT decision_cycle_id, turn_id, cycle_index, created_at"
        " FROM decision_cycle ORDER BY decision_cycle_id"
    ).fetchall()
    pointers = conn.execute(
        "SELECT turn_id, active_decision_cycle_id FROM turn_record"
        " ORDER BY turn_id"
    ).fetchall()
    conn.executescript("BEGIN IMMEDIATE;\n" + export_sql + "\nCOMMIT;")
    assert conn.execute(
        "SELECT decision_cycle_id, turn_id, cycle_index, created_at"
        " FROM decision_cycle ORDER BY decision_cycle_id"
    ).fetchall() == snapshot
    assert conn.execute(
        "SELECT turn_id, active_decision_cycle_id FROM turn_record"
        " ORDER BY turn_id"
    ).fetchall() == pointers
    # Re-running the legacy-cycle INSERT specifically must not add a row.
    conn.executescript(
        "BEGIN IMMEDIATE;\n"
        "INSERT INTO decision_cycle (decision_cycle_id, turn_id,"
        " cycle_index, created_at)"
        " SELECT 'dcy-legacy-' || t.turn_id, t.turn_id, 0, t.started_at"
        " FROM turn_record t"
        " WHERE EXISTS (SELECT 1 FROM generation_action_intent g"
        "               WHERE g.turn_id = t.turn_id)"
        "   AND NOT EXISTS (SELECT 1 FROM decision_cycle d"
        "                   WHERE d.turn_id = t.turn_id AND d.cycle_index = 0);\n"
        "COMMIT;"
    )
    assert conn.execute(
        "SELECT decision_cycle_id, turn_id, cycle_index, created_at"
        " FROM decision_cycle ORDER BY decision_cycle_id"
    ).fetchall() == snapshot
    conn.close()


def test_actions_created_after_0007_require_a_cycle(
    staged_dirs: tuple[Path, Path],
) -> None:
    """The tightened §20 column: a new action without a decision cycle is
    refused by the schema (the lineage is not optional any more)."""

    pre, post = staged_dirs
    conn = connection.connect(":memory:")
    _apply(conn, pre)
    _seed_pre_lineage_data(conn)
    _apply(conn, post)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO generation_action_intent (action_id, turn_id,"
            " decision_cycle_id, moment_id, assistant_turn_id, action_type,"
            " generation_contract_id, status, attempt_count, owner_epoch,"
            " created_at) VALUES ('a-new', 't-live', NULL, NULL, 'at-new',"
            " 'NORMAL_PERSONA_REPLY', 'gc', 'PREPARED', 0, 1, 'now')"
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO generation_action_intent (action_id, turn_id,"
            " decision_cycle_id, moment_id, assistant_turn_id, action_type,"
            " generation_contract_id, status, attempt_count, owner_epoch,"
            " created_at) VALUES ('a-new', 't-live', 'dcy-missing', NULL,"
            " 'at-new', 'NORMAL_PERSONA_REPLY', 'gc', 'PREPARED', 0, 1,"
            " 'now')"
        )
    conn.rollback()
    conn.execute(
        "INSERT INTO generation_action_intent (action_id, turn_id,"
        " decision_cycle_id, moment_id, assistant_turn_id, action_type,"
        " generation_contract_id, status, attempt_count, owner_epoch,"
        " created_at) VALUES ('a-new', 't-live', 'dcy-legacy-t-live', NULL,"
        " 'at-new', 'NORMAL_PERSONA_REPLY', 'gc', 'PREPARED', 0, 1, 'now')"
    )
    conn.commit()
    conn.close()
