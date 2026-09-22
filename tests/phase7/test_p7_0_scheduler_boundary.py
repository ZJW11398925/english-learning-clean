"""P7-0 ① — the Scheduler → Planner boundary.

Two claims, both from the P6-2 F-2 registration's trigger firing and from
BF-02 §5 (lines 128–166):

- **a dirty row is a typed refusal, and both read faces answer it the same
  way.** The pre-fix behaviour is measured, not remembered: a row whose stored
  ``evidence_modality`` is not a §5.2 word came back as ``Ok(None)`` from the
  by-key read (a silent "never written") and as a bare ``ValueError`` from the
  list read, so one durable row had two answers depending on which face was
  asked. The P7-0 disposition added the second shape the first probe missed: a
  **key** column holding a non-TEXT value (``target_type`` / ``target_id`` as
  a BLOB) was still answered ``Ok(None)`` by the by-key face and ``Ok(False)``
  by ``is_review_due``, while the list faces refused over the same row. The
  pins below drive every dirty shape through both faces and assert one
  ``Err(DomainError)`` shape;
- **a row's currency is a judgement, not a number.** ``schedule_currency``
  compares the recorded ``source_learning_watermark`` with the current
  Learning watermark and answers CURRENT / STALE / no-row, and there is no
  path by which a missing or stale authority becomes a ``0`` — that is
  ``elc.planner.feature_assembly``'s rule (its own suite) and this face only
  supplies the fact it reads.
"""

from __future__ import annotations

import ast
import sqlite3

import pytest

from elc.platform.types import (
    DomainErrorCode,
    Err,
    Ok,
)
from elc.scheduler.authority import ScheduleCurrency, currency_of
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState, SpacingStage

from .conftest import (
    MODALITY,
    OTHER_MODALITY,
    TARGET_ID,
    TARGET_TYPE,
    schedule_item,
    source_text,
)

#: The six columns P7-0 names, each with a value the §5.2 set cannot describe.
#: The last two are the **key** columns, and their dirt is a non-TEXT storage
#: class: the row still *spells* the key asked about — which is what the
#: by-key probe's ``CAST(… AS TEXT)`` match reaches — while the lookup's own
#: ``=`` steps over it. That is the F1 shape: before the probe was widened the
#: by-key face answered ``Ok(None)`` and ``is_review_due`` ``Ok(False)`` over
#: such a row while the list faces refused it.
DIRTY_VALUES = {
    "review_state": "LEARNING",
    "spacing_stage": "STAGE_9",
    "evidence_modality": "SINGING",
    "review_urgency": "not-a-number",
    "target_type": b"RESOURCE",
    "target_id": b"res-hedge-i-think",
}

_ITEM_COLUMNS = (
    "schedule_item_id, target_type, target_id, evidence_modality,"
    " review_state, review_urgency, next_review_window_start,"
    " next_review_window_end, spacing_stage, source_learning_watermark,"
    " version, updated_at"
)


def _write_dirty_row(
    db: sqlite3.Connection,
    *,
    column: str,
    value: object,
    item_id: str = "si-p7-0",
) -> None:
    """Put one §5.2 row on disk and then break one column of it.

    The CHECK constraints 0012 declares (``target_type`` /
    ``evidence_modality`` / ``review_state``) are real, so the dirt is injected
    the only way a durable row can carry it: ``PRAGMA
    ignore_check_constraints`` — the same route a corrupt row would take into a
    database, and the route the pre-fix probe used. A non-TEXT value needs no
    such route (SQLite stores a BLOB in a TEXT column as a BLOB), which is why
    the ``target_id`` shape below is written the same way as the rest.
    """

    base = {
        "schedule_item_id": item_id,
        "target_type": TARGET_TYPE,
        "target_id": str(TARGET_ID),
        "evidence_modality": MODALITY.value,
        "review_state": ReviewState.DUE.value,
        "review_urgency": 0.75,
        "next_review_window_start": "2026-09-22T00:00:00+00:00",
        "next_review_window_end": "2026-09-25T00:00:00+00:00",
        "spacing_stage": SpacingStage.STAGE_1.value,
        "source_learning_watermark": "0",
        "version": "sv-1",
        "updated_at": "2026-09-22T00:00:00+00:00",
    }
    db.execute("PRAGMA ignore_check_constraints = ON")
    try:
        db.execute("DELETE FROM schedule_item")
        db.execute(
            "INSERT INTO schedule_item ("
            " schedule_item_id, target_type, target_id, evidence_modality,"
            " review_state, review_urgency, next_review_window_start,"
            " next_review_window_end, spacing_stage,"
            " source_learning_watermark, version, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(base.values()),
        )
        db.execute(
            f"UPDATE schedule_item SET {column} = ? WHERE schedule_item_id = ?",
            (value, item_id),
        )
    finally:
        db.execute("PRAGMA ignore_check_constraints = OFF")
    db.commit()


def _decode_error(result: object) -> Err:
    """The refusal inside a ``Result``, with the failure spelled out when the
    face answered something else (a bare exception never reaches here: the
    caller's own ``Result`` typing is what this suite asserts)."""

    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.VALIDATION_FAILED, result.error
    return result


# -- ① the dirty row, from both faces ----------------------------------------


@pytest.mark.parametrize("column", sorted(DIRTY_VALUES))
def test_a_dirty_row_is_the_same_typed_refusal_from_both_read_faces(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore, column: str
) -> None:
    """One dirty row, two read faces, one ``Err(VALIDATION_FAILED)`` — and the
    message names the row and the column rather than quoting sqlite."""

    _write_dirty_row(db, column=column, value=DIRTY_VALUES[column])
    by_key = _decode_error(
        scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    )
    by_list = _decode_error(scheduler_store.list_schedule_items())
    assert by_key.error.code == by_list.error.code
    for error in (by_key.error, by_list.error):
        assert "si-p7-0" in error.message
        assert column in error.message


def test_a_dirty_evidence_modality_is_not_hidden_as_never_written(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The pre-fix divergence, pinned as gone.

    A row whose stored modality is not a §5.2 word used to answer
    ``Ok(None)`` ("never written") from the by-key read while the list read
    refused over it. The by-key read now probes the target's rows before it
    answers a miss, so both faces refuse — and a *legal* sibling row still
    leaves the miss a miss (the second half of the pin).
    """

    _write_dirty_row(
        db, column="evidence_modality", value="SINGING", item_id="si-dirty"
    )
    refusal = _decode_error(
        scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    )
    assert "si-dirty" in refusal.error.message
    assert "evidence_modality" in refusal.error.message

    # non-vacuity: with the dirt replaced by a legal word, the same call
    # answers the miss it is supposed to answer.
    db.execute("PRAGMA ignore_check_constraints = ON")
    db.execute(
        "UPDATE schedule_item SET evidence_modality = ? WHERE schedule_item_id = ?",
        (OTHER_MODALITY.value, "si-dirty"),
    )
    db.execute("PRAGMA ignore_check_constraints = OFF")
    assert scheduler_store.get_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY
    ) == Ok(None)


def test_a_dirty_review_event_is_refused_by_the_history_read(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item(watermark="0")), Ok
    )
    db.execute("PRAGMA ignore_check_constraints = ON")
    db.execute(
        "INSERT INTO review_event (review_event_id, schedule_item_id,"
        " teaching_moment_id, source_turn_id, event_type, engaged,"
        " evidence_group_id, created_at)"
        " VALUES ('re-dirty', 'si-p7-0', NULL, NULL, 'RECALL', 5, NULL,"
        " '2026-09-22T00:00:00+00:00')"
    )
    db.execute("PRAGMA ignore_check_constraints = OFF")
    db.commit()
    refusal = _decode_error(scheduler_store.list_review_events("si-p7-0"))
    assert "re-dirty" in refusal.error.message
    assert "engaged" in refusal.error.message


def test_no_read_face_lets_a_bare_exception_escape(
    db: sqlite3.Connection,
    scheduler_store: SqliteSchedulerStore,
    scheduler_controller: SchedulerController,
) -> None:
    """The sweep: for every dirty shape, every public read answers a
    ``Result``. This is the assertion the F-2 registration asked for — "no
    bare exception from a decode" — and it is written as a sweep so a new face
    that forgets the decoder is caught here."""

    faces = (
        lambda: scheduler_store.get_schedule_item(
            TARGET_TYPE, TARGET_ID, MODALITY
        ),
        lambda: scheduler_store.list_schedule_items(),
        lambda: scheduler_store.list_review_events("si-p7-0"),
        lambda: scheduler_controller.get_schedule_item(
            TARGET_TYPE, TARGET_ID, MODALITY
        ),
        lambda: scheduler_controller.get_schedule_view("2026-09-23T00:00:00+00:00"),
        lambda: scheduler_controller.is_review_due(
            TARGET_TYPE,
            TARGET_ID,
            MODALITY,
            "2026-09-23T00:00:00+00:00",
        ),
    )
    for column, value in sorted(DIRTY_VALUES.items()):
        _write_dirty_row(db, column=column, value=value)
        for face in faces:
            outcome = face()  # must not raise
            assert isinstance(outcome, (Ok, Err)), (column, outcome)


def test_a_numeric_spelling_of_the_urgency_is_still_one_number(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The decoder's one permissive path, pinned so it is a decision rather
    than an accident: a REAL column holding the text ``"0.75"`` is the same
    number, and a row written before this cut stays readable."""

    _write_dirty_row(db, column="review_urgency", value="0.75")
    row = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(row, Ok) and row.value is not None
    assert row.value.review_urgency == 0.75


def test_a_write_refuses_to_decide_a_conflict_against_a_row_it_cannot_read(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The write faces read the durable row before they decide anything, so a
    row the §5.2 column set cannot describe is a refusal — not a silent
    "no such row", and not a rewrite beside it."""

    _write_dirty_row(db, column="review_state", value="LEARNING")
    refusal = _decode_error(
        scheduler_store.upsert_schedule_item(
            schedule_item(watermark="0", version="sv-2")
        )
    )
    assert "review_state" in refusal.error.message
    durable = db.execute(
        "SELECT review_state, version FROM schedule_item"
    ).fetchone()
    assert durable == ("LEARNING", "sv-1")


def test_a_clean_row_reads_exactly_as_it_was_written(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Non-vacuity for the whole file: the refusals above are about dirt, and
    a clean row is still returned untouched by both faces."""

    written = schedule_item(
        urgency=0.75,
        window_start="2026-09-22T00:00:00+00:00",
        window_end="2026-09-25T00:00:00+00:00",
        stage=SpacingStage.STAGE_1,
        watermark="0",
    )
    assert isinstance(scheduler_store.upsert_schedule_item(written), Ok)
    by_key = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    listed = scheduler_store.list_schedule_items()
    assert isinstance(by_key, Ok) and isinstance(listed, Ok)
    assert by_key.value is not None
    assert listed.value == (by_key.value,)
    assert by_key.value.source_learning_watermark == "0"
    assert by_key.value.review_urgency == 0.75


# -- ② the currency handshake -------------------------------------------------


def test_currency_is_current_when_the_recorded_watermark_is_the_current_one(
    scheduler_store: SqliteSchedulerStore,
    wired_scheduler: SchedulerController,
    learning_controller,
) -> None:
    watermark = learning_controller.get_learning_watermark()
    assert isinstance(watermark, Ok)
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item(watermark=str(watermark.value))
        ),
        Ok,
    )
    assert wired_scheduler.schedule_currency(
        TARGET_TYPE, TARGET_ID, MODALITY
    ) == Ok(ScheduleCurrency.CURRENT)


def test_currency_is_stale_when_the_row_was_computed_at_an_older_watermark(
    scheduler_store: SqliteSchedulerStore,
    wired_scheduler: SchedulerController,
    learning_controller,
) -> None:
    current = learning_controller.get_learning_watermark()
    assert isinstance(current, Ok)
    older = str(current.value + 1)
    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item(watermark=older)), Ok
    )
    assert wired_scheduler.schedule_currency(
        TARGET_TYPE, TARGET_ID, MODALITY
    ) == Ok(ScheduleCurrency.STALE)


def test_a_non_numeric_recorded_watermark_is_stale_rather_than_an_error(
    scheduler_store: SqliteSchedulerStore,
    wired_scheduler: SchedulerController,
) -> None:
    """§5.2 declares the column TEXT and this package carries it verbatim, so
    the comparison is a comparison of spellings: a value that cannot equal the
    current watermark's spelling is STALE (the module docstring's reading),
    and it is never parsed, so it can never raise."""

    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item(watermark="not-a-watermark")
        ),
        Ok,
    )
    assert wired_scheduler.schedule_currency(
        TARGET_TYPE, TARGET_ID, MODALITY
    ) == Ok(ScheduleCurrency.STALE)


def test_a_target_with_no_row_is_not_stale(
    wired_scheduler: SchedulerController,
) -> None:
    """``Ok(None)`` = "the Scheduler has nothing to say about this key", which
    is neither CURRENT nor STALE and is emphatically not BF-02 §5's
    missing-Scheduler case (that one is about holding no authority at all)."""

    assert wired_scheduler.schedule_currency(
        TARGET_TYPE, TARGET_ID, MODALITY
    ) == Ok(None)


def test_the_currency_face_refuses_without_the_learning_read_port(
    scheduler_store: SqliteSchedulerStore,
    scheduler_controller: SchedulerController,
) -> None:
    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item(watermark="0")), Ok
    )
    result = scheduler_controller.schedule_currency(
        TARGET_TYPE, TARGET_ID, MODALITY
    )
    assert isinstance(result, Err)
    assert result.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE


def test_the_currency_rule_is_one_pure_function() -> None:
    """The comparison itself is declared once, in
    :mod:`elc.scheduler.authority`, and both call shapes (an ``int`` from the
    Learning face, its already-spelled form) answer the same word."""

    row = schedule_item(watermark="7")
    assert currency_of(row, 7) is ScheduleCurrency.CURRENT
    assert currency_of(row, "7") is ScheduleCurrency.CURRENT
    assert currency_of(row, 8) is ScheduleCurrency.STALE
    assert currency_of(row, "07") is ScheduleCurrency.STALE


def test_the_review_state_of_a_row_is_not_part_of_the_handshake(
    scheduler_store: SqliteSchedulerStore,
    wired_scheduler: SchedulerController,
    learning_controller,
) -> None:
    """Currency is about the *evidence set the row was computed from*, never
    about what the row concluded: a DUE row and a NOT_SCHEDULED row written at
    the same watermark are both CURRENT."""

    watermark = learning_controller.get_learning_watermark()
    assert isinstance(watermark, Ok)
    spelling = str(watermark.value)
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item(
                item_id="si-due",
                review_state=ReviewState.DUE,
                urgency=0.75,
                watermark=spelling,
            )
        ),
        Ok,
    )
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item(
                item_id="si-unscheduled",
                modality=OTHER_MODALITY,
                review_state=ReviewState.NOT_SCHEDULED,
                urgency=0.0,
                watermark=spelling,
            )
        ),
        Ok,
    )
    assert wired_scheduler.schedule_currency(
        TARGET_TYPE, TARGET_ID, MODALITY
    ) == Ok(ScheduleCurrency.CURRENT)
    assert wired_scheduler.schedule_currency(
        TARGET_TYPE, TARGET_ID, OTHER_MODALITY
    ) == Ok(ScheduleCurrency.CURRENT)


def test_the_handshake_module_imports_no_store_and_no_clock() -> None:
    """Structural half: the handshake answers one of two words, so its import
    set is the whole story — no sqlite3, no datetime, no other domain, and no
    Planner type (a module that decided something would need one)."""

    imported: set[str] = set()
    for node in ast.walk(ast.parse(source_text("src/elc/scheduler/authority.py"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported == {"__future__", "enum", "elc.scheduler.types"}
    source = source_text("src/elc/scheduler/authority.py")
    assert "ScheduleCurrency" in source
    assert "PlannerDecision(" not in source
    assert "SchedulerController" not in source
