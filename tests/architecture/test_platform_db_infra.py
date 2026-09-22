"""Phase 0 app.db infrastructure checks (docs/IMPLEMENTATION_PLAN.md §17-02).

Not part of the §2 Gate list, but pins the §17-02 deliverables: idempotent
migrations with a version table, short-transaction discipline, and the
runtime_epoch restart fence.

This file additionally pins the three migration-lineage constants every
suite's version pin reads (``tests.conftest``): the declared id list is the
real ``migrations/`` directory, the declared head is that directory's last
entry, and applying the chain stamps the declared version. Without that pin a
constant could drift from the tree it claims to describe and every pin using
it would keep passing.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.db import connection, epoch, migrations, tx
from tests.conftest import (
    MIGRATION_IDS,
    REPO_ROOT,
    SCHEMA_HEAD_FILE,
    SCHEMA_HEAD_VERSION,
)


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    yield conn
    conn.close()


def test_the_migration_lineage_constants_are_the_real_ones() -> None:
    """The shared constants describe this repository, not themselves.

    Three facts, each checked against the tree rather than against the
    constants: the ids are exactly the ``migrations/*.sql`` stems (in order),
    ``SCHEMA_HEAD_FILE`` is that directory's last entry, and
    ``SCHEMA_HEAD_VERSION`` is the two-digit number the head's own file name
    starts with. A new migration that is not registered here fails this test
    -- which is what keeps the dozen version pins above honest.
    """

    names = sorted(path.name for path in (REPO_ROOT / "migrations").glob("*.sql"))
    assert [name.removesuffix(".sql") for name in names] == list(MIGRATION_IDS)
    assert names[-1] == SCHEMA_HEAD_FILE
    assert SCHEMA_HEAD_FILE[:4] == f"{int(SCHEMA_HEAD_VERSION):04d}"


def test_migrations_apply_idempotently(db: sqlite3.Connection) -> None:
    applied = migrations.apply_migrations(db)
    # 0002_conversation_core joins in Phase 1 P1A (TASK-OPI-091f35c3.11);
    # 0003_generation_provider joins in Phase 1 P1B (TASK-OPI-d7937fd7.9);
    # 0004_learning_evidence joins in Phase 2 P2A (TASK-OPI-eaaa5a1d-30);
    # 0005_learner_target_state joins in Phase 2 P2B (TASK-…44 — the
    # materialized §11 projection consumed by the Estimator rebuild);
    # 0006_decision_cycle joins in Phase 3 P3-0 (TASK-…55 ④ — §4 table
    # only, no write face until P3-1 lineage semantics);
    # 0007_teaching_lineage joins in Phase 3 P3-1A (TASK-…2babb21e.17 ① —
    # Gate/Moment tables + legacy cycle export + the §20 tighten);
    # 0008_attempt_records joins in Phase 3 P3-1B (TASK-…2babb21e.2 ① —
    # attempt / evaluation tables + the F8 completion/abort CHECKs);
    # 0009_relationship_contracts joins in Phase 4 P4-0 (TASK-…5ba74efc.84
    # ①③ — the durable pending teaching-evidence proposal + the
    # relationship_memory table).
    # 0010_episode_and_user_config joins in Phase 4 P4-3 (TASK-OPI-4d516e4f
    # -….19 ⑥ — the episode projection table + the user_profile /
    # disclosure_policy rows).
    # 0011_goal_policy_focus joins in Phase 6 P6-0 (TASK-OPI-a68fd9eb-….48 ③
    # — the §5.1 goal_portfolio / teaching_policy / session_focus rows).
    # 0012_schedule_review joins in Phase 6 P6-1 (TASK-OPI-6259f6fd-….12 ②①
    # — the §5.2 schedule_item / review_event rows).
    # 0013_planner_constraint joins in Phase 6 P6-3 (TASK-OPI-5a0be06d-….20 ③
    # — the §9 planner_constraint row);
    # 0014_deletion_tombstone joins in Gate 2 (TASK-OPI-b99560d4-….19 ① —
    # the BF-05 §24 deletion ledger; IP §16 DoD #25).
    # The ids live in tests.conftest so the per-phase version pins share one
    # declaration (and test_the_migration_lineage_constants_are_the_real_ones
    # holds it against the directory).
    # DATA_MODEL §26.1: migrations bump schema_version explicitly.
    assert applied == list(MIGRATION_IDS)
    # Second run is a no-op.
    assert migrations.apply_migrations(db) == []
    rows = db.execute(
        "SELECT migration_id FROM schema_migrations ORDER BY migration_id"
    ).fetchall()
    assert [row[0] for row in rows] == list(MIGRATION_IDS)
    # The stamp is the newest migration's (this pin read "10" while 0010 was
    # the head, "11" with P6-0's 0011_goal_policy_focus; P6-1 added
    # 0012_schedule_review, P6-3 the 0013_planner_constraint above, Gate 2
    # the 0014_deletion_tombstone).
    assert migrations.schema_version(db) == SCHEMA_HEAD_VERSION


def test_runtime_epoch_fence_restarts_and_stales(db: sqlite3.Connection) -> None:
    migrations.apply_migrations(db)

    first = epoch.open_runtime_epoch(db)
    second = epoch.open_runtime_epoch(db)
    assert second.current == first.current + 1
    assert epoch.load_current_epoch(db) == second.current

    # Old-epoch writes are fenced; current-epoch writes pass.
    with pytest.raises(epoch.StaleEpochError):
        second.require_current(first.current)
    second.require_current(second.current)
    assert first.is_stale(first.current) is False
    assert first.is_stale(first.current + 99) is True


def test_short_transaction_commits_and_nesting_is_refused(
    db: sqlite3.Connection,
) -> None:
    with tx.short_transaction(db):
        db.execute("CREATE TABLE t_short (x TEXT)")
    assert not tx.in_transaction(db)

    with pytest.raises(tx.TransactionStateError):
        with tx.short_transaction(db):
            with tx.short_transaction(db):
                pass
    # After the failed nested unit the outer transaction rolled back cleanly.
    assert not tx.in_transaction(db)


def test_provider_style_side_effect_refused_inside_transaction(
    db: sqlite3.Connection,
) -> None:
    with tx.short_transaction(db):
        with pytest.raises(tx.TransactionStateError):
            tx.require_no_active_transaction(db, "provider_call")
