"""P8-3 ③④ — the durable ledger store: one unit, four reads, and the refusals.

Everything here drives the shipped faces: the real app.db with migration 0016
applied, the real epoch fence, the pure core's own answers as the store's
inputs, and ``SqliteLedgerStore``'s statements. Nothing is hand-written into a
table except the two things a probe needs to *be* hand-written (a dirty row the
decoder must refuse, and a trigger that fails a write mid-unit to show the
rollback) — both are called out where they happen.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from elc.planner.ledger import (
    PLANNING_LEDGER_MODEL_VERSION,
    CoverageObligation,
    LedgerEvent,
    LedgerKeyType,
    LedgerWindow,
    ObligationScope,
    PlanningLedger,
    TargetLedgerRow,
    accrue,
    apply_ledger_event,
)
from elc.planner.ledger_store import (
    PLANNING_LEDGER_STORE_SOURCES,
    LedgerEventRow,
    SqliteLedgerStore,
    StaleLedgerStoreError,
)
from elc.platform.db import epoch
from elc.platform.db.tx import in_transaction
from elc.platform.types import Err, Ok

DAY = "2026-09-23T09:00:00+00:00"
LATER = "2026-09-23T09:05:00+00:00"
KEY = "t-p8-3"
OTHER_KEY = "t-p8-3-other"
FAMILY = "family-p8-3"


@pytest.fixture()
def store(db: sqlite3.Connection, fence) -> SqliteLedgerStore:
    return SqliteLedgerStore(db, fence)


def obligation(
    *,
    key: str = "ob-1",
    target: str = KEY,
    scope: str = ObligationScope.TARGET.value,
    debt: float = 0.5,
    paused: bool = False,
    pause_reason: str | None = None,
    served: str | None = None,
    engaged: str | None = None,
) -> CoverageObligation:
    return CoverageObligation(
        obligation_key=key,
        scope_type=scope,
        target_or_family_id=target,
        goal_id=None,
        window_start="2026-09-01T00:00:00+00:00",
        window_end="2026-09-30T00:00:00+00:00",
        debt_value=debt,
        accrual_paused=paused,
        pause_reason=pause_reason,
        last_served_at=served,
        last_engaged_at=engaged,
    )


def append(
    store: SqliteLedgerStore,
    event: LedgerEvent,
    *,
    event_id: str | None = None,
    at: str = DAY,
    key: str = KEY,
    base: TargetLedgerRow | None = None,
    obligations: tuple[CoverageObligation, ...] = (),
    key_type: LedgerKeyType = LedgerKeyType.TARGET,
):
    """One real unit: read the row, record the event, hand the pair in."""

    row = base if base is not None else TargetLedgerRow(target_key=key)
    return store.record_ledger_event(
        event_id=event_id or f"ev-{len(row.events)}-{event.value}",
        event=event,
        row=row.record(event, at=at),
        key_type=key_type,
        obligations=obligations,
    )


def _count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# -- ③ the unit --------------------------------------------------------------


def test_the_three_tables_are_the_declared_sources(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert PLANNING_LEDGER_STORE_SOURCES == (
        "planning_ledger",
        "coverage_obligation",
        "planning_ledger_event",
    )
    tables = {
        str(row[0])
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for table in PLANNING_LEDGER_STORE_SOURCES:
        assert table in tables, table


def test_one_event_lands_in_the_row_and_in_the_log(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    written = append(store, LedgerEvent.TEACHING_PRESENTED)
    assert isinstance(written, Ok), written
    assert written.value == LedgerEventRow(
        event_id="ev-0-teaching_presented",
        ledger_key=KEY,
        event=LedgerEvent.TEACHING_PRESENTED,
        as_of=DAY,
    )
    assert _count(db, "planning_ledger_event") == 1
    assert _count(db, "planning_ledger") == 1


def test_the_projection_is_the_cores_own_answers(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """Every derived column equals the core's property on the same log — the
    store re-derives nothing and the two cannot disagree."""

    row = TargetLedgerRow(target_key=KEY)
    for event, at in (
        (LedgerEvent.CANDIDATE_SELECTED, DAY),
        (LedgerEvent.HINT_PRESENTED, LATER),
        (LedgerEvent.USER_SKIP, LATER),
    ):
        written = append(store, event, at=at, base=row, event_id=f"ev-{at}-{event}")
        assert isinstance(written, Ok), written
        row = row.record(event, at=at)
    stored = store.get_ledger_projection(KEY)
    assert isinstance(stored, Ok) and stored.value is not None
    assert stored.value.last_selected_at == row.last_selected_at
    assert stored.value.last_presented_at == row.last_presented_at
    assert stored.value.teaching_exposure_counts == row.teaching_exposure_counts
    assert stored.value.recent_skips == row.recent_skips
    assert stored.value.teaching_exposure_counts == 0
    assert stored.value.recent_skips == 1
    assert stored.value.last_presented_at == LATER


def test_a_selection_alone_stamps_no_presentation(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """§20's first rule as durable data: SELECT != exposure."""

    assert isinstance(append(store, LedgerEvent.CANDIDATE_SELECTED), Ok)
    stored = store.get_ledger_projection(KEY)
    assert stored.value is not None
    assert stored.value.last_selected_at == DAY
    assert stored.value.last_presented_at is None
    assert stored.value.teaching_exposure_counts == 0


def test_the_two_counters_with_no_event_are_never_invented(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """§20's five words carry no probe and no review offer, so the two columns
    are written as the row's own values (zero) and moved by no event."""

    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    stored = store.get_ledger_projection(KEY)
    assert stored.value.probe_counts == 0
    assert stored.value.review_offers == 0


def test_the_window_round_trips_as_one_json_object(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    window = LedgerWindow(start=DAY, end=LATER)
    row = TargetLedgerRow(target_key=KEY, overexposure_window=window)
    written = append(store, LedgerEvent.TEACHING_PRESENTED, base=row)
    assert isinstance(written, Ok), written
    document = db.execute(
        "SELECT overexposure_window FROM planning_ledger"
    ).fetchone()[0]
    assert json.loads(document) == {"start": DAY, "end": LATER}
    assert document == json.dumps(
        {"start": DAY, "end": LATER}, sort_keys=True, separators=(",", ":")
    )
    assert store.get_ledger_projection(KEY).value.overexposure_window == window
    assert store.get_ledger_row(KEY).value.overexposure_window == window


def test_the_version_column_is_the_model_constant(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    assert store.get_ledger_projection(KEY).value.version == (
        PLANNING_LEDGER_MODEL_VERSION
    )


def test_the_key_face_is_declared_and_stored(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(
        append(
            store,
            LedgerEvent.CANDIDATE_SELECTED,
            key=FAMILY,
            key_type=LedgerKeyType.TARGET_FAMILY,
        ),
        Ok,
    )
    assert store.get_ledger_projection(FAMILY).value.ledger_key_type is (
        LedgerKeyType.TARGET_FAMILY
    )


def test_the_obligations_ride_the_same_unit(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """A serving event and the obligation it repaid are one transaction."""

    served = apply_ledger_event(
        obligation(debt=1.0), LedgerEvent.TEACHING_PRESENTED, at=DAY
    )
    written = append(
        store,
        LedgerEvent.TEACHING_PRESENTED,
        obligations=(served.obligation,),
    )
    assert isinstance(written, Ok), written
    assert served.changed is True
    assert _count(db, "coverage_obligation") == 1
    assert store.get_obligation("ob-1").value == served.obligation
    assert store.get_obligation("ob-1").value.debt_value == 0.0


def test_a_selection_repays_nothing_durably(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """§20's second rule: CoverageDebt 不因 selection 自动偿还 — the event's own
    outcome says nothing moved, and the durable obligation agrees."""

    before = obligation(debt=0.8)
    outcome = apply_ledger_event(
        before, LedgerEvent.CANDIDATE_SELECTED, at=DAY
    )
    assert outcome.changed is False
    assert isinstance(
        append(
            store,
            LedgerEvent.CANDIDATE_SELECTED,
            obligations=(outcome.obligation,),
        ),
        Ok,
    )
    assert store.get_obligation("ob-1").value.debt_value == 0.8


def test_a_unit_with_no_obligations_writes_none(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(append(store, LedgerEvent.USER_SKIP), Ok)
    assert _count(db, "coverage_obligation") == 0


def test_an_accrual_has_its_own_face_and_no_event(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """BF-06 §14's accrual is about *not* serving, so no §20 word produces it:
    the obligation's own write face exists for exactly that."""

    outcome = accrue(obligation(debt=0.0), amount=0.25, at=DAY)
    assert outcome.changed is True
    written = store.upsert_obligation(outcome.obligation)
    assert isinstance(written, Ok), written
    assert _count(db, "coverage_obligation") == 1
    assert _count(db, "planning_ledger_event") == 0
    assert _count(db, "planning_ledger") == 0
    assert store.get_obligation("ob-1").value.debt_value == 0.25


def test_a_paused_obligation_keeps_its_reason(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    paused = obligation(
        paused=True,
        pause_reason="UNAVAILABLE_IN_CURRENT_RUNTIME",
        debt=0.0,
    )
    assert isinstance(store.upsert_obligation(paused), Ok)
    assert store.get_obligation("ob-1").value == paused
    assert store.get_obligation("ob-1").value.accrual_paused is True


def test_an_obligation_upsert_replaces_the_rows_values(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(store.upsert_obligation(obligation(debt=0.4)), Ok)
    assert isinstance(store.upsert_obligation(obligation(debt=0.9)), Ok)
    assert _count(db, "coverage_obligation") == 1
    assert store.get_obligation("ob-1").value.debt_value == 0.9


def test_the_unit_is_a_short_transaction(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert in_transaction(db) is False
    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    assert in_transaction(db) is False


def test_a_stale_fence_refuses_the_write_and_writes_nothing(
    db: sqlite3.Connection, store: SqliteLedgerStore, fence
) -> None:
    stale = SqliteLedgerStore(db, epoch.RuntimeEpochFence(current=fence.current - 1))
    with pytest.raises(StaleLedgerStoreError):
        append(stale, LedgerEvent.TEACHING_PRESENTED)
    assert _count(db, "planning_ledger") == 0
    assert _count(db, "planning_ledger_event") == 0
    with pytest.raises(StaleLedgerStoreError):
        stale.upsert_obligation(obligation())
    assert _count(db, "coverage_obligation") == 0


def test_a_write_that_fails_mid_unit_leaves_nothing(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """All-or-nothing, shown by failing the *second* statement of the unit.

    The trigger is probe scaffolding (the only raw DDL in this file): the
    projection row is written first, the event insert then aborts, and the
    rollback has to take the row with it — otherwise the store would leave a
    projection whose log does not carry its own event."""

    db.execute(
        "CREATE TRIGGER probe_refuse_event BEFORE INSERT ON"
        " planning_ledger_event WHEN NEW.event_id = 'ev-refused'"
        " BEGIN SELECT RAISE(ABORT, 'probe'); END"
    )
    refused = store.record_ledger_event(
        event_id="ev-refused",
        event=LedgerEvent.TEACHING_PRESENTED,
        row=TargetLedgerRow(target_key=KEY).record(
            LedgerEvent.TEACHING_PRESENTED, at=DAY
        ),
        obligations=(obligation(),),
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"
    assert _count(db, "planning_ledger") == 0
    assert _count(db, "planning_ledger_event") == 0
    assert _count(db, "coverage_obligation") == 0
    assert in_transaction(db) is False
    db.execute("DROP TRIGGER probe_refuse_event")


# -- ④ replay, and the three refusals ---------------------------------------


def test_a_replay_returns_the_durable_row_and_writes_nothing(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    first = append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1")
    assert isinstance(first, Ok), first
    again = append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1")
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert _count(db, "planning_ledger_event") == 1
    assert _count(db, "planning_ledger") == 1


def test_a_replay_is_answered_before_the_base_log_is_compared(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """A retry need not reconstruct the base: the id decides first, so a retry
    that hands in a row whose *last* record is the same event replays even
    when the rest of that row is not the durable log."""

    row = TargetLedgerRow(target_key=KEY).record(
        LedgerEvent.TEACHING_PRESENTED, at=DAY
    )
    first = store.record_ledger_event(
        event_id="ev-1", event=LedgerEvent.TEACHING_PRESENTED, row=row
    )
    assert isinstance(first, Ok), first
    second = store.record_ledger_event(
        event_id="ev-1",
        event=LedgerEvent.TEACHING_PRESENTED,
        row=TargetLedgerRow(target_key=KEY)
        .record(LedgerEvent.USER_SKIP, at=LATER)
        .record(LedgerEvent.TEACHING_PRESENTED, at=DAY),
    )
    assert isinstance(second, Ok), second
    assert second.value == first.value
    assert _count(db, "planning_ledger_event") == 1


@pytest.mark.parametrize(
    "other",
    [
        LedgerEvent.USER_SKIP,
        LedgerEvent.HINT_PRESENTED,
        LedgerEvent.REVEAL_PRESENTED,
        LedgerEvent.CANDIDATE_SELECTED,
    ],
)
def test_the_same_id_with_a_different_word_is_a_conflict(
    db: sqlite3.Connection, store: SqliteLedgerStore, other: LedgerEvent
) -> None:
    base = TargetLedgerRow(target_key=KEY)
    assert isinstance(
        append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1"), Ok
    )
    conflicted = append(
        store,
        other,
        event_id="ev-1",
        at=LATER,
        base=base.record(LedgerEvent.TEACHING_PRESENTED, at=DAY),
    )
    assert isinstance(conflicted, Err)
    assert conflicted.error.code.value == "CONFLICT"
    assert "never rewritten" in conflicted.error.message
    assert _count(db, "planning_ledger_event") == 1


def test_the_same_id_at_a_different_instant_is_a_conflict(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(
        append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1"), Ok
    )
    conflicted = append(
        store,
        LedgerEvent.TEACHING_PRESENTED,
        event_id="ev-1",
        at=LATER,
        base=TargetLedgerRow(target_key=KEY).record(
            LedgerEvent.TEACHING_PRESENTED, at=DAY
        ),
    )
    assert isinstance(conflicted, Err)
    assert conflicted.error.code.value == "CONFLICT"


def test_the_same_id_on_another_key_is_a_conflict(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(
        append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1"), Ok
    )
    conflicted = append(
        store,
        LedgerEvent.TEACHING_PRESENTED,
        event_id="ev-1",
        key=OTHER_KEY,
    )
    assert isinstance(conflicted, Err)
    assert conflicted.error.code.value == "CONFLICT"
    assert _count(db, "planning_ledger") == 1


def test_a_repeat_is_two_presentations_not_a_collapsed_one(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """The core's own sentence: the log does not collapse a repeat, which is
    why the durable identity is a caller-minted id rather than the content."""

    first = append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1")
    assert isinstance(first, Ok), first
    second = append(
        store,
        LedgerEvent.TEACHING_PRESENTED,
        event_id="ev-2",
        base=store.get_ledger_row(KEY).value,
    )
    assert isinstance(second, Ok), second
    assert _count(db, "planning_ledger_event") == 2
    assert [row.event_id for row in store.list_ledger_events(KEY).value] == [
        "ev-1",
        "ev-2",
    ]
    assert store.get_ledger_projection(KEY).value.teaching_exposure_counts == 2


def test_a_stale_base_is_refused_rather_than_re_based(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """Two events, the second offered against a base the first already moved."""

    first = append(store, LedgerEvent.TEACHING_PRESENTED, event_id="ev-1")
    assert isinstance(first, Ok)
    stale = append(store, LedgerEvent.HINT_PRESENTED, event_id="ev-2")
    assert isinstance(stale, Err)
    assert stale.error.code.value == "CONFLICT"
    assert "re-read the row" in stale.error.message
    assert _count(db, "planning_ledger_event") == 1
    # and the honest way succeeds
    fresh = append(
        store,
        LedgerEvent.HINT_PRESENTED,
        event_id="ev-3",
        at=LATER,
        base=store.get_ledger_row(KEY).value,
    )
    assert isinstance(fresh, Ok), fresh
    assert _count(db, "planning_ledger_event") == 2


def test_a_row_whose_log_does_not_end_with_the_event_is_refused(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    row = TargetLedgerRow(target_key=KEY).record(
        LedgerEvent.USER_SKIP, at=DAY
    )
    refused = store.record_ledger_event(
        event_id="ev-1", event=LedgerEvent.TEACHING_PRESENTED, row=row
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "does not end with it" in refused.error.message
    assert _count(db, "planning_ledger") == 0


def test_a_row_with_no_log_cannot_be_appended_to(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    refused = store.record_ledger_event(
        event_id="ev-1",
        event=LedgerEvent.TEACHING_PRESENTED,
        row=TargetLedgerRow(target_key=KEY),
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "no event" in refused.error.message


# -- ④ the reads -------------------------------------------------------------


def test_an_unknown_key_answers_none_from_every_read(
    store: SqliteLedgerStore,
) -> None:
    assert store.get_ledger_projection("nope") == Ok(None)
    assert store.get_ledger_row("nope") == Ok(None)
    assert store.get_obligation("nope") == Ok(None)
    assert store.list_ledger_events("nope") == Ok(())
    assert store.list_obligations(target_or_family_id="nope") == Ok(())


def test_the_row_read_is_the_cores_object(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    row = TargetLedgerRow(target_key=KEY, probe_counts=2, review_offers=1)
    assert isinstance(
        append(store, LedgerEvent.TEACHING_PRESENTED, base=row), Ok
    )
    read = store.get_ledger_row(KEY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.target_key == KEY
    assert read.value.probe_counts == 2 and read.value.review_offers == 1
    assert [record.event for record in read.value.events] == [
        LedgerEvent.TEACHING_PRESENTED
    ]
    assert read.value.teaching_exposure_counts == 1


def test_the_event_stream_is_ordered_by_instant_then_id(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """The append order and the read order are different facts: a log appended
    out of instant order still reads back by ``(as_of, event_id)``."""

    row = TargetLedgerRow(target_key=KEY)
    for index, (event, at) in enumerate(
        (
            (LedgerEvent.CANDIDATE_SELECTED, LATER),
            (LedgerEvent.TEACHING_PRESENTED, DAY),
            (LedgerEvent.USER_SKIP, DAY),
        )
    ):
        written = append(
            store, event, at=at, base=row, event_id=f"ev-{index}"
        )
        assert isinstance(written, Ok), written
        row = row.record(event, at=at)
    stream = store.list_ledger_events(KEY)
    assert [item.event for item in stream.value] == [
        LedgerEvent.TEACHING_PRESENTED,
        LedgerEvent.USER_SKIP,
        LedgerEvent.CANDIDATE_SELECTED,
    ]
    assert [item.event_id for item in stream.value] == ["ev-1", "ev-2", "ev-0"]
    assert [item.event for item in row.events] == [
        LedgerEvent.CANDIDATE_SELECTED,
        LedgerEvent.TEACHING_PRESENTED,
        LedgerEvent.USER_SKIP,
    ]


def test_the_obligation_read_includes_unserved_and_paused_ones(
    store: SqliteLedgerStore,
) -> None:
    """The read has no service filter: "which debts are waiting" must be
    answerable without the ladder having decided for the caller."""

    assert isinstance(store.upsert_obligation(obligation(key="ob-live")), Ok)
    assert isinstance(
        store.upsert_obligation(
            obligation(
                key="ob-paused",
                paused=True,
                pause_reason="UNAVAILABLE_IN_CURRENT_RUNTIME",
                debt=0.0,
            )
        ),
        Ok,
    )
    assert isinstance(
        store.upsert_obligation(obligation(key="ob-unserved", debt=1.0)), Ok
    )
    listed = store.list_obligations()
    assert [item.obligation_key for item in listed.value] == [
        "ob-live",
        "ob-paused",
        "ob-unserved",
    ]


def test_the_obligation_read_narrows_by_the_key_as_spelled(
    store: SqliteLedgerStore,
) -> None:
    """The core's own match: a family- or goal-scoped row whose id spells the
    key lands here exactly as ``PlanningLedger.obligations_for`` puts it."""

    assert isinstance(
        store.upsert_obligation(
            obligation(key="ob-a", scope=ObligationScope.TARGET.value)
        ),
        Ok,
    )
    assert isinstance(
        store.upsert_obligation(
            obligation(
                key="ob-b",
                target=KEY,
                scope=ObligationScope.TARGET_FAMILY.value,
            )
        ),
        Ok,
    )
    assert isinstance(
        store.upsert_obligation(
            obligation(key="ob-c", target=OTHER_KEY, scope=ObligationScope.GOAL.value)
        ),
        Ok,
    )
    listed = store.list_obligations(target_or_family_id=KEY).value
    assert [item.obligation_key for item in listed] == ["ob-a", "ob-b"]
    assert store.list_obligations(target_or_family_id="family-other") == Ok(())


def test_the_whole_ledger_read_is_the_cores_view(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    row = TargetLedgerRow(target_key=KEY)
    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED, base=row), Ok)
    assert isinstance(append(store, LedgerEvent.USER_SKIP, key=FAMILY), Ok)
    assert isinstance(store.upsert_obligation(obligation()), Ok)
    ledger = store.read_ledger()
    assert isinstance(ledger, Ok), ledger
    assert isinstance(ledger.value, PlanningLedger)
    assert sorted(ledger.value.rows) == sorted([KEY, FAMILY])
    assert ledger.value.rows[KEY].teaching_exposure_counts == 1
    assert ledger.value.rows[FAMILY].recent_skips == 1
    assert [item.obligation_key for item in ledger.value.obligations] == ["ob-1"]
    assert ledger.value.version == PLANNING_LEDGER_MODEL_VERSION


def test_the_two_non_materialized_columns_answer_the_cores_defaults(
    store: SqliteLedgerStore,
) -> None:
    """§26 lists "some PlanningLedger rollups" among the rebuildable
    projections, and migration 0016 materializes neither rollup-shaped column:
    the read answers the core's empty values rather than a computed one."""

    ledger = store.read_ledger()
    assert ledger.value.coverage_debt_rollups == {}
    assert ledger.value.recent_target_families == ()


def test_an_empty_ledger_reads_as_the_cores_empty_ledger(
    store: SqliteLedgerStore,
) -> None:
    assert store.read_ledger() == Ok(PlanningLedger())


# -- ④ the refusals on the way out -------------------------------------------


def test_a_projection_that_disagrees_with_its_log_is_refused(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """The core's sentence — "no stored copy can disagree with the log" — as a
    read refusal rather than a silently chosen answer."""

    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    db.execute(
        "UPDATE planning_ledger SET teaching_exposure_counts = 7"
        " WHERE ledger_key = ?",
        (KEY,),
    )
    refused = store.get_ledger_row(KEY)
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "teaching_exposure_counts" in refused.error.message
    # the projection read itself is still a plain read of what is stored
    assert store.get_ledger_projection(KEY).value.teaching_exposure_counts == 7
    # and the whole-ledger read refuses too (it goes through the row read)
    assert isinstance(store.read_ledger(), Err)


@pytest.mark.parametrize(
    "column, value, expected",
    [
        ("last_selected_at", sqlite3.Binary(b"nope"), "last_selected_at"),
        ("teaching_exposure_counts", "many", "teaching_exposure_counts"),
        ("recent_skips", 1.5, "recent_skips"),
        ("overexposure_window", "not json", "overexposure_window"),
        ("ledger_key_type", "GOAL", "ledger_key_type"),
    ],
)
def test_a_row_the_column_set_cannot_describe_is_refused(
    db: sqlite3.Connection,
    store: SqliteLedgerStore,
    column: str,
    value: object,
    expected: str,
) -> None:
    """SQLite's type affinity is not enforcement, so a column can hold what
    §14 cannot describe (a BLOB where a timestamp belongs, a float where a
    count belongs); the decoder refuses and names it instead of coercing (the
    scheduler store's dirty-row contract). The ``GOAL`` case needs the pragma
    that turns the CHECK off — which is the point: a value the *schema* would
    refuse can still reach a reader, and a reader must answer, not crash."""

    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    db.execute("PRAGMA ignore_check_constraints = ON")
    db.execute(
        f"UPDATE planning_ledger SET {column} = ? WHERE ledger_key = ?",
        (value, KEY),
    )
    refused = store.get_ledger_projection(KEY)
    assert isinstance(refused, Err), refused
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert expected in refused.error.message
    db.execute("PRAGMA ignore_check_constraints = OFF")


def test_a_window_document_with_the_wrong_shape_is_refused(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    db.execute(
        "UPDATE planning_ledger SET overexposure_window = ?"
        " WHERE ledger_key = ?",
        (json.dumps({"start": DAY}), KEY),
    )
    refused = store.get_ledger_projection(KEY)
    assert isinstance(refused, Err)
    assert "start and end" in refused.error.message


def test_an_obligation_outside_the_declared_range_is_refused_not_raised(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """The core's constructor is the range's gate, and the read must answer a
    ``Result`` rather than let the constructor's exception escape (the P6-2
    F-2 lesson: a reader never meets a raw exception from a row it reads)."""

    assert isinstance(store.upsert_obligation(obligation()), Ok)
    db.execute("UPDATE coverage_obligation SET debt_value = 5.0")
    refused = store.get_obligation("ob-1")
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "debt_value" in refused.error.message or "valid obligation" in (
        refused.error.message
    )


def test_a_half_declared_pause_in_a_row_is_refused_not_raised(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """Reached with the pragma that turns the CHECK off, because the point is
    the *decoder*: a row the schema would refuse can still exist on a disk
    written by another tool, and this read must answer, not crash."""

    assert isinstance(store.upsert_obligation(obligation()), Ok)
    db.execute("PRAGMA ignore_check_constraints = ON")
    db.execute("UPDATE coverage_obligation SET accrual_paused = 1, pause_reason = NULL")
    refused = store.get_obligation("ob-1")
    assert isinstance(refused, Err), refused
    assert refused.error.code.value == "VALIDATION_FAILED"
    db.execute("PRAGMA ignore_check_constraints = OFF")


def test_an_event_word_outside_the_five_in_a_row_is_refused_not_raised(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    db.execute("PRAGMA ignore_check_constraints = ON")
    db.execute("UPDATE planning_ledger_event SET event = 'elsewhere'")
    refused = store.list_ledger_events(KEY)
    assert isinstance(refused, Err), refused
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "five words" in refused.error.message
    db.execute("PRAGMA ignore_check_constraints = OFF")


def test_the_decoders_answer_results_and_never_raise(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """One more shape through each decoder, asserted as ``Result`` values: the
    object channel is the store's whole error contract."""

    assert isinstance(append(store, LedgerEvent.TEACHING_PRESENTED), Ok)
    assert isinstance(store.upsert_obligation(obligation()), Ok)
    db.execute("PRAGMA ignore_check_constraints = ON")
    db.execute(
        "UPDATE planning_ledger_event SET as_of = ?",
        (sqlite3.Binary(b"nope"),),
    )
    db.execute(
        "UPDATE coverage_obligation SET scope_type = ?",
        (sqlite3.Binary(b"nope"),),
    )
    for result in (
        store.list_ledger_events(KEY),
        store.get_obligation("ob-1"),
        store.list_obligations(),
        store.get_ledger_row(KEY),
        store.read_ledger(),
    ):
        assert isinstance(result, (Ok, Err))
        assert isinstance(result, Err), result
    db.execute("PRAGMA ignore_check_constraints = OFF")


def test_a_unit_touches_only_the_three_ledger_tables(
    db: sqlite3.Connection, store: SqliteLedgerStore
) -> None:
    """The whole surface of the write face, read off the database: no planner
    record, no teaching row and no decision cycle moves because a ledger event
    was appended."""

    tables = sorted(
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        )
    )

    def counts() -> dict[str, int]:
        return {
            name: int(
                db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            )
            for name in tables
        }

    before = counts()
    assert isinstance(
        append(
            store,
            LedgerEvent.TEACHING_PRESENTED,
            obligations=(obligation(),),
        ),
        Ok,
    )
    after = counts()
    assert {name for name in tables if before[name] != after[name]} == set(
        PLANNING_LEDGER_STORE_SOURCES
    )
