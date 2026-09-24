"""P8-4 ③ — the BF-05 CONVERSATION walk's provenance leg (migration 0017).

0016's Revisit clause asked for the column **and** the conversation leg
together; this file checks the second half against the shipped walk rather
than the header's prose:

- a conversation's deletion **clears** the references its removed Moments can
  no longer resolve (``UPDATE planning_ledger_event SET moment_id = NULL``)
  and keeps every row — the ledger is learning history this scope was never
  given (BF-05 lines 87/747), and a removed event would leave a standing
  projection disagreeing with its own log;
- the count rides the §27 tally (``cleared_provenance_legs``) beside the
  ``planner_constraint`` leg's rows, and it counts *rows cleared*;
- a reference to a Moment of another conversation is untouched;
- the two scopes that **do** remove ledger history (LEARNING_TARGET /
  ALL_LEARNING_HISTORY) still remove it — the clearing leg is CONVERSATION's;
- the surface and the statement are pinned where they live
  (``CONVERSATION_SWEPT_TABLES`` stays a subsequence of ``SWEPT_TABLES``; the
  deleter is the only module naming the table with a write).

The events are produced the way production produces them — a real automatic
opening through the coordinator — so nothing here hand-writes a row the writer
does not write.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.deletion.types import (
    CONVERSATION_SWEPT_TABLES,
    SWEPT_TABLES,
    DeletionRequest,
    DeletionScope,
)
from elc.platform.types import ConversationId, DomainErrorCode, Err, Ok
from elc.scheduler.types import ReviewEvent
from tests.phase7.conftest import CONV, TARGET_ID
from tests.phase8.p8_4_world import (
    SCHEDULE_ITEM_ID,
    acceptance_supply,
    begin_turn_ok,
    build_content,
    count_events,
    deletion_controller,
    events,
    moments,
    open_conversation,
    wiring,
    world,
)
from tests.phase8.p8_4_world import coordinator as build_coordinator

SECOND = ConversationId("conv-p8-4-second")


def automatic(p8world):
    """The wiring with the ALLOW acceptance's injected candidate set."""

    return wiring(p8world, supply=acceptance_supply())


@pytest.fixture()
def content(tmp_path: Path) -> Path:
    return build_content(tmp_path / "content.db")


@pytest.fixture()
def p8world(db: sqlite3.Connection, fence, content: Path):
    return world(db, fence, content)


@pytest.fixture()
def opened(p8world) -> None:
    """One real automatic opening in CONV: a Moment, a lock and its event."""

    begin_turn_ok(
        build_coordinator(p8world, automatic=automatic(p8world)), "cm-open"
    )


def _conversation_moments(db: sqlite3.Connection, conversation) -> list[str]:
    return [
        str(row[0])
        for row in db.execute(
            "SELECT moment_id FROM teaching_moment WHERE conversation_id = ?",
            (str(conversation),),
        )
    ]


# -- ① the clearing leg ------------------------------------------------------


def test_a_conversation_deletion_keeps_the_ledger_row_and_clears_the_ref(
    db: sqlite3.Connection, p8world, opened
) -> None:
    del opened
    before = events(db)
    assert len(before) == 1
    [moment_id] = _conversation_moments(db, CONV)

    result = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(result, Ok), result

    after = events(db)
    assert len(after) == 1, "the ledger row must survive the conversation walk"
    assert after[0][0] == before[0][0]
    assert after[0][2] == "teaching_presented"
    assert after[0][4] is None, "the removed Moment's id must be cleared"
    assert moments(db) == []
    assert moment_id == before[0][4]


def test_the_clearing_rides_the_section27_tally(
    db: sqlite3.Connection, p8world, opened
) -> None:
    del opened
    execution = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(execution, Ok), execution
    assert execution.value.execution.cleared_provenance_legs == 1


def test_the_tally_counts_rows_not_statements(
    db: sqlite3.Connection, p8world
) -> None:
    """Two presentations from two conversations clear one row each."""

    coordinator_ = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(coordinator_, "cm-open-1")
    deletion = deletion_controller(p8world)
    first = deletion.execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(first, Ok), first
    assert first.value.execution.cleared_provenance_legs == 1

    open_conversation(p8world, SECOND)
    second_coordinator = build_coordinator(
        p8world, automatic=automatic(p8world)
    )
    begin_turn_ok(second_coordinator, "cm-open-2", conversation=SECOND)
    second = deletion.execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=SECOND)
    )
    assert isinstance(second, Ok), second
    assert second.value.execution.cleared_provenance_legs == 1
    assert count_events(db) == 2
    assert [row[4] for row in events(db)] == [None, None]


def test_another_conversations_reference_is_untouched(
    db: sqlite3.Connection, p8world
) -> None:
    """The clearing is scoped by *this* conversation's moments: the other
    conversation's presentation keeps its provenance."""

    open_conversation(p8world, SECOND)
    first = build_coordinator(p8world, automatic=automatic(p8world))
    second = build_coordinator(p8world, automatic=automatic(p8world))
    begin_turn_ok(first, "cm-a")
    begin_turn_ok(second, "cm-b", conversation=SECOND)

    kept = _conversation_moments(db, SECOND)
    assert len(kept) == 1
    assert {row[4] for row in events(db)} == set(kept) | set(
        _conversation_moments(db, CONV)
    )

    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(executed, Ok), executed
    assert executed.value.execution.cleared_provenance_legs == 1
    assert {row[4] for row in events(db)} == {None, kept[0]}


def test_the_clearing_is_idempotent(db: sqlite3.Connection, p8world, opened) -> None:
    """A second deletion of the same conversation has nothing left to clear:
    the row is already NULL and the tally does not move."""

    del opened
    deletion = deletion_controller(p8world)
    first = deletion.execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(first, Ok), first
    second = deletion.execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(second, Ok), second
    assert second.value.execution.cleared_provenance_legs == 0
    assert count_events(db) == 1


def test_the_projection_survives_the_clearing(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """The row's own columns are untouched: a cleared reference is not a
    rewritten projection (the header's whole invariant)."""

    del opened
    before = db.execute(
        "SELECT ledger_key, teaching_exposure_counts, last_presented_at"
        " FROM planning_ledger"
    ).fetchall()
    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(executed, Ok), executed
    after = db.execute(
        "SELECT ledger_key, teaching_exposure_counts, last_presented_at"
        " FROM planning_ledger"
    ).fetchall()
    assert after == before
    assert before


# -- ② the scopes that remove rows still remove them -------------------------


def test_the_learning_target_scope_still_removes_the_rows(
    db: sqlite3.Connection, p8world, opened
) -> None:
    del opened
    executed = deletion_controller(p8world).execute(
        DeletionRequest(
            scope=DeletionScope.LEARNING_TARGET,
            target_id=TARGET_ID,
            target_type="RESOURCE",
        )
    )
    assert isinstance(executed, Ok), executed
    assert count_events(db) == 0
    assert db.execute("SELECT COUNT(*) FROM planning_ledger").fetchone()[0] == 0


def test_all_learning_history_still_removes_the_rows(
    db: sqlite3.Connection, p8world, opened
) -> None:
    del opened
    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY)
    )
    assert isinstance(executed, Ok), executed
    assert count_events(db) == 0


def test_the_clearing_leg_does_not_fire_for_other_scopes(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """A reference that is *removed with its row* is not a cleared leg: the
    tally stays at zero for the two ledger-removing scopes."""

    del opened
    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.ALL_LEARNING_HISTORY)
    )
    assert isinstance(executed, Ok), executed
    assert executed.value.execution.cleared_provenance_legs == 0


# -- ③ the surface and the statement -----------------------------------------


def test_the_conversation_surface_names_the_log_last() -> None:
    assert "planning_ledger_event" in CONVERSATION_SWEPT_TABLES
    assert CONVERSATION_SWEPT_TABLES[-1] == "planning_ledger_event"
    positions = {table: index for index, table in enumerate(SWEPT_TABLES)}
    indexes = [positions[table] for table in CONVERSATION_SWEPT_TABLES]
    assert indexes == sorted(indexes)


def test_the_walk_writes_the_log_and_never_removes_a_logged_fact() -> None:
    from tests.conftest import REPO_ROOT
    from tests.phase3.sql_write_scan import write_statements

    deleter = write_statements(
        REPO_ROOT / "src" / "elc" / "deletion" / "store.py"
    )
    assert deleter["planning_ledger_event"] == ("DELETE", "UPDATE")


def test_the_clearing_statement_is_the_one_this_leg_reads() -> None:
    from tests.conftest import SRC_ROOT

    text = " ".join(
        (SRC_ROOT / "deletion" / "store.py").read_text(encoding="utf-8").split()
    )
    assert "UPDATE planning_ledger_event SET moment_id = NULL" in text
    assert "WHERE moment_id IN (" in text
    assert text.count("UPDATE planning_ledger_event") == 1


def test_no_event_references_a_removed_moment_afterwards(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """Zero orphans, stated as the checkable postcondition: after the walk, no
    surviving event points at a Moment that is gone."""

    del opened
    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(executed, Ok), executed
    alive = {str(row[0]) for row in moments(db)}
    referenced = {str(row[4]) for row in events(db) if row[4] is not None}
    assert referenced <= alive


def test_the_leg_is_registered_where_the_package_says_it_is(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """The row the walk writes is the row the package's registration names
    (``deletion/__init__.py``'s "clearing rather than a removal" bullet): the
    cleared leg is the §27 move, executed."""

    del opened
    from tests.conftest import SRC_ROOT

    text = " ".join(
        (SRC_ROOT / "deletion" / "__init__.py")
        .read_text(encoding="utf-8")
        .split()
    )
    assert "_clear_ledger_provenance_legs" in text
    assert "drop the content ref, keep the non-body state" in text
    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(executed, Ok), executed
    assert executed.value.execution.cleared_provenance_legs == 1


# -- ④ the walk's OPEN-status repair (a pre-existing hole P8-4 found) --------


def test_an_open_status_row_binds_the_cycle_not_a_moment(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """The declared reading the repair rests on, read off the durable row:
    an OPEN carries ``moment_id = NULL`` (``ConversationCoordinator.
    _gate_status_record`` for the user-initiated path, the automatic unit for
    this one), so a sweep by ``moment_id`` cannot see it."""

    del opened
    rows = db.execute(
        "SELECT moment_id, gate_context, authorization_basis"
        " FROM gate_execution_status"
    ).fetchall()
    assert rows == [(None, "OPEN", "DECISION_CYCLE")]


def test_a_conversation_that_opened_teaching_can_be_deleted(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """P8-4's repair of a pre-existing hole: before it, the FK from
    ``gate_execution_status`` to the cycle refused the cycle's removal, so no
    conversation that ever opened teaching could be deleted at all (the
    user-initiated path's own rows trip it too — this cut's probe drove
    ``request_teaching`` on an assembly with no automatic wiring and hit the
    same refusal)."""

    del opened
    executed = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(executed, Ok), executed
    tallies = {
        tally.table: tally.removed
        for tally in executed.value.execution.tallies
    }
    assert tallies["gate_execution_status"] == 1
    assert tallies["decision_cycle"] == 1
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 0
    assert (
        db.execute("SELECT COUNT(*) FROM gate_execution_status").fetchone()[0] == 0
    )


def test_the_cycle_keyed_sweep_is_the_one_that_catches_it(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """The removal is *the cycle-keyed* one: the row survives a moment-keyed
    sweep (its moment is NULL) and is gone after the cycle-keyed one — which
    is what makes the repair a coverage statement rather than a second,
    redundant statement."""

    del opened
    moment_ids = _conversation_moments(db, CONV)
    cycle_ids = [
        str(row[0])
        for row in db.execute("SELECT decision_cycle_id FROM decision_cycle")
    ]
    assert moment_ids and cycle_ids
    rowid = db.execute("SELECT rowid FROM gate_execution_status").fetchone()[0]
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status WHERE moment_id IN (?)",
            moment_ids,
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status"
            " WHERE decision_cycle_id IN (?)",
            cycle_ids,
        ).fetchone()[0]
        == 1
    )
    assert rowid == 1


# -- ⑤ the registered same-family missed row (pinned as-is, not endorsed) ----


def test_a_moment_bound_review_event_is_the_walks_registered_missed_row(
    db: sqlite3.Connection, p8world, opened
) -> None:
    """Registered, not endorsed — **this case pins today's behaviour so the
    repair is a visible change**.

    A ``review_event`` whose only reference is its Moment (``source_turn_id``
    and ``evidence_group_id`` both ``NULL``) is not reachable by either of the
    walk's ``review_event`` sweeps, and the Moment it names cannot be removed:
    the walk refuses as one unit — ``Err(CONFLICT)``, the message naming the
    durable constraint (``FOREIGN KEY``) — and nothing at all is removed. The
    shape has no shipped writer today (``SchedulerController.
    record_review_event`` has no caller in ``src/``); it is written here
    through that real face, which is the writer the review-outcome path will
    use. Whether such an event should be removed with its Moment or keep the
    reference is the semantics the landing cut must settle first
    (``elc.deletion``'s package docstring registers it); the leg then belongs
    beside the two sweeps in ``_conversation``.
    """

    del opened
    [moment_id] = _conversation_moments(db, CONV)
    recorded = p8world.scheduler.record_review_event(
        ReviewEvent(
            review_event_id="re-moment-bound",
            schedule_item_id=SCHEDULE_ITEM_ID,
            teaching_moment_id=moment_id,
            source_turn_id=None,
            event_type="registered-shape",
            engaged=True,
        )
    )
    assert isinstance(recorded, Ok), recorded
    assert db.execute(
        "SELECT teaching_moment_id, source_turn_id, evidence_group_id"
        " FROM review_event"
    ).fetchone() == (moment_id, None, None)

    refused = deletion_controller(p8world).execute(
        DeletionRequest(scope=DeletionScope.CONVERSATION, conversation_id=CONV)
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "FOREIGN KEY" in refused.error.message
    # The refusal is the whole walk's: neither the event nor the Moment went.
    assert db.execute(
        "SELECT COUNT(*) FROM review_event"
    ).fetchone()[0] == 1
    assert moments(db) == [(moment_id, str(CONV), "AWAITING_USER")]
