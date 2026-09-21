"""Phase 0 app.db infrastructure checks (docs/IMPLEMENTATION_PLAN.md §17-02).

Not part of the §2 Gate list, but pins the §17-02 deliverables: idempotent
migrations with a version table, short-transaction discipline, and the
runtime_epoch restart fence.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.platform.db import connection, epoch, migrations, tx


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = connection.connect(":memory:")
    yield conn
    conn.close()


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
    # attempt / evaluation tables + the F8 completion/abort CHECKs).
    # DATA_MODEL §26.1: migrations bump schema_version explicitly.
    assert applied == [
        "0001_bootstrap",
        "0002_conversation_core",
        "0003_generation_provider",
        "0004_learning_evidence",
        "0005_learner_target_state",
        "0006_decision_cycle",
        "0007_teaching_lineage",
        "0008_attempt_records",
    ]
    # Second run is a no-op.
    assert migrations.apply_migrations(db) == []
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
        "0007_teaching_lineage",
        "0008_attempt_records",
    ]
    assert migrations.schema_version(db) == "8"


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
