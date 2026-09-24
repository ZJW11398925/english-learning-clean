"""P8-4 ② — the log's provenance column, through the shipped store.

``SqliteLedgerStore`` gains one column and one parameter
(``moment_id``); what is pinned here is that the column is *written*, *read*
and *replayed* as part of the event's content:

- the row record carries it and its default is ``None`` (an event no Moment
  produced, and every row written before 0017);
- ``list_ledger_events`` reads it back, and a ``NULL`` is a value rather than
  a dirty row;
- the replay rule **includes it**: the same ``event_id`` with the same event,
  key and instant but a *different* Moment is a different fact under one id —
  ``CONFLICT``, not a silent overwrite and not a no-op;
- the projection invariant is untouched: the row is still a pure function of
  the log, obligations still land in the same short transaction, and
  ``read_ledger`` still answers the core's own defaults (the core's log record
  is still exactly ``(event, at)``).

The write path exercised is the runtime's own unit
(:func:`elc.runtime.exposure.record_event`), because that is the caller
migration 0017 was written for; the raw store face is exercised beside it so
the column is pinned on both sides of the seam.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from elc.planner.ledger import (
    CoverageObligation,
    LedgerEvent,
    LedgerKeyType,
    ObligationScope,
    PlanningLedger,
    TargetLedgerRow,
    apply_ledger_event,
)
from elc.planner.ledger_store import (
    LedgerEventRow,
    SqliteLedgerStore,
)
from elc.platform.types import DomainErrorCode, Err, Ok
from elc.runtime.exposure import (
    exposure_event_id,
    record_event,
    record_exposure,
    record_skip,
    skip_event_id,
)

TARGET = "res-hedge-i-think"
OTHER_TARGET = "res-other-target"
AT_ONE = "2026-09-24T09:00:00+00:00"
AT_TWO = "2026-09-24T09:10:00+00:00"
MOMENT = "tm-turn-1-automatic"
OTHER_MOMENT = "tm-turn-2-automatic"


def _store(db: sqlite3.Connection, fence) -> SqliteLedgerStore:
    return SqliteLedgerStore(db, fence)


def _event_count(db: sqlite3.Connection, key: str = TARGET) -> int:
    return int(
        db.execute(
            "SELECT COUNT(*) FROM planning_ledger_event WHERE ledger_key = ?",
            (key,),
        ).fetchone()[0]
    )


def test_the_row_record_carries_the_provenance_column() -> None:
    fields = [field.name for field in dataclasses.fields(LedgerEventRow)]
    assert fields == ["event_id", "ledger_key", "event", "as_of", "moment_id"]
    assert (
        dataclasses.fields(LedgerEventRow)[4].default is None
    ), "moment_id must default to None (pre-0017 rows and non-Moment events)"


def test_a_written_event_reads_its_moment_back(db, fence) -> None:
    store = _store(db, fence)
    written = record_exposure(
        writer=store,
        event_id=exposure_event_id("ga-turn-1-automatic-open"),
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(written, Ok), written
    events = store.list_ledger_events(TARGET)
    assert isinstance(events, Ok), events
    assert [(row.event, row.moment_id) for row in events.value] == [
        (LedgerEvent.TEACHING_PRESENTED, MOMENT)
    ]


def test_the_default_writes_a_null_reference(db, fence) -> None:
    store = _store(db, fence)
    row = TargetLedgerRow(target_key=TARGET).record(
        LedgerEvent.USER_SKIP, at=AT_ONE
    )
    written = store.record_ledger_event(
        event_id="ev-no-moment", event=LedgerEvent.USER_SKIP, row=row
    )
    assert isinstance(written, Ok), written
    assert written.value.moment_id is None
    assert db.execute(
        "SELECT moment_id FROM planning_ledger_event WHERE event_id ="
        " 'ev-no-moment'"
    ).fetchone() == (None,)


def test_the_same_event_with_the_same_moment_is_a_replay(db, fence) -> None:
    store = _store(db, fence)
    first = record_exposure(
        writer=store,
        event_id="ev-replay",
        event=LedgerEvent.HINT_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(first, Ok), first
    second = record_exposure(
        writer=store,
        event_id="ev-replay",
        event=LedgerEvent.HINT_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(second, Ok), second
    assert _event_count(db) == 1
    assert second.value.moment_id == MOMENT


def test_the_same_event_with_another_moment_is_a_conflict(db, fence) -> None:
    """The replay rule compares the provenance too: one id cannot name two
    presentations of one key at one instant."""

    store = _store(db, fence)
    first = record_exposure(
        writer=store,
        event_id="ev-conflict",
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(first, Ok), first
    second = record_exposure(
        writer=store,
        event_id="ev-conflict",
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=OTHER_MOMENT,
        at=AT_ONE,
    )
    assert isinstance(second, Err), second
    assert second.error.code is DomainErrorCode.CONFLICT
    assert _event_count(db) == 1
    assert db.execute(
        "SELECT moment_id FROM planning_ledger_event WHERE event_id ="
        " 'ev-conflict'"
    ).fetchone() == (MOMENT,)


def test_dropping_the_moment_is_a_conflict_too(db, fence) -> None:
    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-drop",
            event=LedgerEvent.REVEAL_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    existing = store.get_ledger_row(TARGET)
    assert isinstance(existing, Ok) and existing.value is not None
    row = existing.value.record(LedgerEvent.REVEAL_PRESENTED, at=AT_ONE)
    refused = store.record_ledger_event(
        event_id="ev-drop",
        event=LedgerEvent.REVEAL_PRESENTED,
        row=row,
        moment_id=None,
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT


def test_a_differing_instant_is_still_a_conflict(db, fence) -> None:
    """The column is *added* to the content comparison, not substituted for
    it."""

    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-instant",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    again = record_exposure(
        writer=store,
        event_id="ev-instant",
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_TWO,
    )
    assert isinstance(again, Err), again
    assert again.error.code is DomainErrorCode.CONFLICT


def test_a_differing_word_is_still_a_conflict(db, fence) -> None:
    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-word",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    again = record_exposure(
        writer=store,
        event_id="ev-word",
        event=LedgerEvent.HINT_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(again, Err), again
    assert again.error.code is DomainErrorCode.CONFLICT


def test_two_presentations_of_two_moments_are_two_facts(db, fence) -> None:
    """The column's whole reason: the same key presented twice is two events
    with two ids and two Moments."""

    store = _store(db, fence)
    for index, moment in ((1, MOMENT), (2, OTHER_MOMENT)):
        written = record_exposure(
            writer=store,
            event_id=f"ev-two-{index}",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=moment,
            at=AT_ONE,
        )
        assert isinstance(written, Ok), written
    events = store.list_ledger_events(TARGET)
    assert isinstance(events, Ok), events
    assert [row.moment_id for row in events.value] == [MOMENT, OTHER_MOMENT]


def test_the_projection_is_still_a_pure_function_of_the_log(db, fence) -> None:
    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-projection",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    read = store.get_ledger_row(TARGET)
    assert isinstance(read, Ok), read
    assert read.value is not None
    assert read.value.last_presented_at == AT_ONE
    assert read.value.teaching_exposure_counts == 1


def test_the_event_and_the_projection_land_together(db, fence) -> None:
    """One short transaction: the log row, the projection and the obligation
    the event produced are all durable when the call returns."""

    store = _store(db, fence)
    obligation = CoverageObligation(
        obligation_key="ob-p8-4",
        scope_type=ObligationScope.TARGET,
        target_or_family_id=TARGET,
        goal_id=None,
        window_start=AT_ONE,
        window_end=AT_TWO,
        debt_value=1.0,
        accrual_paused=False,
        pause_reason=None,
        last_served_at=None,
        last_engaged_at=None,
    )
    outcome = apply_ledger_event(
        obligation, LedgerEvent.TEACHING_PRESENTED, at=AT_ONE
    )
    assert outcome.changed
    row = TargetLedgerRow(target_key=TARGET).record(
        LedgerEvent.TEACHING_PRESENTED, at=AT_ONE
    )
    written = store.record_ledger_event(
        event_id="ev-obligation",
        event=LedgerEvent.TEACHING_PRESENTED,
        row=row,
        obligations=(outcome.obligation,),
        moment_id=MOMENT,
    )
    assert isinstance(written, Ok), written
    stored = store.get_obligation("ob-p8-4")
    assert isinstance(stored, Ok) and stored.value is not None
    assert stored.value.last_served_at == AT_ONE
    assert store.list_ledger_events(TARGET).value[0].moment_id == MOMENT


def test_the_core_view_still_carries_no_provenance(db, fence) -> None:
    """``read_ledger`` is the core's view: ``moment_id`` is not a field of the
    core's log record and does not become one."""

    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-core",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    view = store.read_ledger()
    assert isinstance(view, Ok), view
    assert isinstance(view.value, PlanningLedger)
    row = view.value.rows[TARGET]
    assert [record.event for record in row.events] == [
        LedgerEvent.TEACHING_PRESENTED
    ]
    assert not hasattr(row.events[0], "moment_id")
    assert view.value.coverage_debt_rollups == {}
    assert view.value.recent_target_families == ()


def test_a_row_without_a_moment_is_not_a_dirty_row(db, fence) -> None:
    """The read face treats ``NULL`` as a value: the column is nullable by
    design, so ``_optional_text`` is the only reading that can be right."""

    db.execute(
        "INSERT INTO planning_ledger (ledger_key, ledger_key_type,"
        " teaching_exposure_counts, probe_counts, review_offers, recent_skips,"
        " version) VALUES (?, 'TARGET', 0, 0, 0, 0, 'pl1')",
        (OTHER_TARGET,),
    )
    db.execute(
        "INSERT INTO planning_ledger_event (event_id, ledger_key, event, as_of,"
        " moment_id) VALUES ('ev-legacy', ?, 'user_skip', ?, NULL)",
        (OTHER_TARGET, AT_ONE),
    )
    store = _store(db, fence)
    events = store.list_ledger_events(OTHER_TARGET)
    assert isinstance(events, Ok), events
    assert events.value[0].moment_id is None
    assert store.get_ledger_projection(OTHER_TARGET).value is not None


def test_the_event_statements_carry_the_column() -> None:
    from elc.planner import ledger_store

    assert "moment_id" in ledger_store._SELECT_EVENTS
    assert "moment_id" in ledger_store._SELECT_EVENT
    assert "moment_id" in ledger_store._INSERT_EVENT
    assert ledger_store._INSERT_EVENT.count("?") == 5


def test_the_store_still_writes_one_insert_per_table() -> None:
    from tests.conftest import REPO_ROOT
    from tests.phase3.sql_write_scan import write_statements

    statements = write_statements(
        REPO_ROOT / "src" / "elc" / "planner" / "ledger_store.py"
    )
    assert statements == {
        "coverage_obligation": ("INSERT",),
        "planning_ledger": ("INSERT",),
        "planning_ledger_event": ("INSERT",),
    }


def test_the_skip_unit_carries_the_moment_as_provenance(db, fence) -> None:
    store = _store(db, fence)
    written = record_skip(
        writer=store,
        event_id=skip_event_id("tm-turn-3-automatic"),
        target_key=TARGET,
        moment_id="tm-turn-3-automatic",
        at=AT_TWO,
    )
    assert isinstance(written, Ok), written
    assert written.value.event is LedgerEvent.USER_SKIP
    assert written.value.moment_id == "tm-turn-3-automatic"
    assert written.value.as_of == AT_TWO


def test_the_writer_port_names_the_parameter() -> None:
    """The port ``elc.runtime.exposure`` declares — and the store that
    satisfies it — spell the same keyword, so a wiring cannot pass the
    provenance positionally into something else."""

    import inspect

    from elc.runtime.exposure import LedgerExposureWriter

    port = inspect.signature(LedgerExposureWriter.record_ledger_event)
    store = inspect.signature(SqliteLedgerStore.record_ledger_event)
    for signature in (port, store):
        assert "moment_id" in signature.parameters
        assert signature.parameters["moment_id"].default is None


def test_the_raw_store_face_accepts_the_keyword(db, fence) -> None:
    """Both the port and the raw face take ``moment_id`` by keyword only —
    the call that would pass it positionally is a TypeError, not a wrong
    write."""

    store = _store(db, fence)
    row = TargetLedgerRow(target_key=TARGET).record(
        LedgerEvent.HINT_PRESENTED, at=AT_ONE
    )
    try:
        store.record_ledger_event(  # type: ignore[misc]
            "ev-positional",
            LedgerEvent.HINT_PRESENTED,
            row,
            LedgerKeyType.TARGET,
            (),
            MOMENT,
        )
    except TypeError:
        pass
    else:  # pragma: no cover — the face is keyword-only by declaration
        raise AssertionError("record_ledger_event accepted arguments by position")
    assert _event_count(db) == 0


def test_record_event_reports_the_store_refusal_untouched(db, fence) -> None:
    """A refusal is the caller's to report: the unit returns the store's Err
    and writes nothing else."""

    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-untouched",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    refused = record_exposure(
        writer=store,
        event_id="ev-untouched",
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=OTHER_MOMENT,
        at=AT_ONE,
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert _event_count(db) == 1


def test_record_event_writes_a_row_that_had_none(db, fence) -> None:
    store = _store(db, fence)
    written = record_event(
        writer=store,
        event_id="ev-fresh",
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(written, Ok), written
    assert db.execute(
        "SELECT COUNT(*) FROM planning_ledger WHERE ledger_key = ?", (TARGET,)
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT ledger_key_type FROM planning_ledger WHERE ledger_key = ?",
        (TARGET,),
    ).fetchone() == ("TARGET",)


def test_record_event_reads_the_existing_row_first(db, fence) -> None:
    """The log the unit appends to is the durable one: a second, different
    event for the same key extends the log instead of replacing it."""

    store = _store(db, fence)
    first = record_event(
        writer=store,
        event_id="ev-first",
        event=LedgerEvent.TEACHING_PRESENTED,
        target_key=TARGET,
        moment_id=MOMENT,
        at=AT_ONE,
    )
    assert isinstance(first, Ok), first
    second = record_event(
        writer=store,
        event_id="ev-second",
        event=LedgerEvent.USER_SKIP,
        target_key=TARGET,
        moment_id=OTHER_MOMENT,
        at=AT_TWO,
    )
    assert isinstance(second, Ok), second
    events = store.list_ledger_events(TARGET)
    assert [row.event for row in events.value] == [
        LedgerEvent.TEACHING_PRESENTED,
        LedgerEvent.USER_SKIP,
    ]


def test_an_unreadable_row_is_reported_not_swallowed(db, fence) -> None:
    """A row the store cannot describe is a reported dirty row (the P7-0
    reading), and the new column does not change that: a non-text value lands
    in the same refusal shape."""

    store = _store(db, fence)
    assert isinstance(
        record_exposure(
            writer=store,
            event_id="ev-clean",
            event=LedgerEvent.TEACHING_PRESENTED,
            target_key=TARGET,
            moment_id=MOMENT,
            at=AT_ONE,
        ),
        Ok,
    )
    db.execute(
        "UPDATE planning_ledger_event SET moment_id = x'00ff' WHERE event_id ="
        " 'ev-clean'"
    )
    events = store.list_ledger_events(TARGET)
    assert isinstance(events, Err), events
    assert events.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "moment_id" in events.error.message
