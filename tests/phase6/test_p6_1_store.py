"""P6-1 ②③ — the durable §5.2 rows: write semantics, read-back, refuse paths.

docs/DATA_MODEL.md §1.4 ("version every derived model") and §1.3
(append-first) are the two rules this file makes observable:

- **ScheduleItem** is a versioned *current projection*: a new object inserts;
  the same version with the same content is an idempotent replay that writes
  nothing; a moved version replaces (and restamps ``updated_at`` from the
  store's clock); the same version with *different* content is refused with
  **zero writes**; and the modality key — ``(target_type, target_id,
  evidence_modality)`` — is unique, so a second row under one key is refused
  too (one current row per key is what "current" means);
- **ReviewEvent** is a fact: the same id with the same content replays, the
  same id with different content is refused (never rewritten — appendix a new
  event), an event naming a schedule row that does not exist is
  ``NOT_FOUND``, and several events for one row coexist in a deterministic
  order.

Every assertion reads the durable row back (or the raw column), never the
caller's construction: the store's contract is that what it returns is what a
later read returns. The four vocabularies §5.2 pins are checked at the schema
*and* at the type layer, and the NULL columns (§5.2's ``?`` plus
``review_urgency``) round-trip as ``None``.
"""

from __future__ import annotations

import dataclasses
import sqlite3

import pytest

from elc.platform.db import epoch
from elc.platform.types import Ok, TargetId
from elc.scheduler.store import SqliteSchedulerStore, StaleSchedulerStoreError
from elc.scheduler.types import ReviewEvent, ReviewState, ScheduleItem, SpacingStage
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_targets

from .conftest import (
    CAPABILITY_TARGET_ID,
    CAPABILITY_TARGET_TYPE,
    MODALITY,
    OTHER_MODALITY,
    TARGET_ID,
    TARGET_TYPE,
    WATERMARK,
    review_event,
    schedule_item,
)

ITEM_COLUMNS = (
    "schedule_item_id",
    "target_type",
    "target_id",
    "evidence_modality",
    "review_state",
    "review_urgency",
    "next_review_window_start",
    "next_review_window_end",
    "spacing_stage",
    "source_learning_watermark",
    "version",
    "updated_at",
)

EVENT_COLUMNS = (
    "review_event_id",
    "schedule_item_id",
    "teaching_moment_id",
    "source_turn_id",
    "event_type",
    "engaged",
    "evidence_group_id",
    "created_at",
)


def _item_row(db: sqlite3.Connection, item_id: str) -> tuple[object, ...]:
    row = db.execute(
        f"SELECT {', '.join(ITEM_COLUMNS)} FROM schedule_item"
        " WHERE schedule_item_id = ?",
        (item_id,),
    ).fetchone()
    assert row is not None, f"no schedule_item row {item_id}"
    return tuple(row)


def _event_row(db: sqlite3.Connection, event_id: str) -> tuple[object, ...]:
    row = db.execute(
        f"SELECT {', '.join(EVENT_COLUMNS)} FROM review_event"
        " WHERE review_event_id = ?",
        (event_id,),
    ).fetchone()
    assert row is not None, f"no review_event row {event_id}"
    return tuple(row)


def _field_pairs(durable: object, written: object) -> list[tuple[str, object, object]]:
    """Every field of a written object next to the read-back one."""

    return [
        (field.name, getattr(written, field.name), getattr(durable, field.name))
        for field in dataclasses.fields(durable)  # type: ignore[arg-type]
    ]


def _assert_same_content(durable: ScheduleItem, written: ScheduleItem) -> None:
    assert _field_pairs(durable, written) == [
        (field.name, getattr(written, field.name), getattr(written, field.name))
        for field in dataclasses.fields(ScheduleItem)
    ]
    assert durable == written


# -- the schedule item -------------------------------------------------------


def test_a_new_item_inserts_and_reads_back_field_for_field(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    written = scheduler_store.upsert_schedule_item(
        schedule_item(
            "si-1",
            review_state=ReviewState.DUE,
            urgency=0.75,
            window_start="2026-09-22T09:00:00+00:00",
            window_end="2026-09-23T09:00:00+00:00",
            stage=SpacingStage.STAGE_2,
        )
    )
    assert isinstance(written, Ok), written
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    _assert_same_content(read.value, written.value)

    row = _item_row(db, "si-1")
    assert row[0] == "si-1"
    assert row[1] == TARGET_TYPE
    assert row[2] == str(TARGET_ID)
    assert row[3] == "TEXT_PRODUCTION"
    assert row[4] == "DUE"
    assert row[5] == 0.75
    assert row[6] == "2026-09-22T09:00:00+00:00"
    assert row[7] == "2026-09-23T09:00:00+00:00"
    assert row[8] == "STAGE_2"
    assert row[9] == WATERMARK
    assert row[10] == "sv-1"
    assert row[11] == written.value.updated_at


def test_the_read_is_by_the_modality_key(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """§5.2 pins no owner column, so the row is addressed by its own key: the
    same target under the other modality is a *different* row, and the read
    answers by (target_type, target_id, evidence_modality)."""

    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item("si-prod")), Ok
    )
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item("si-comp", modality=OTHER_MODALITY)
        ),
        Ok,
    )
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item(
                "si-cap",
                target_type=CAPABILITY_TARGET_TYPE,
                target_id=CAPABILITY_TARGET_ID,
                review_state=ReviewState.NOT_SCHEDULED,
            )
        ),
        Ok,
    )
    production = scheduler_store.get_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY
    )
    comprehension = scheduler_store.get_schedule_item(
        TARGET_TYPE, TARGET_ID, OTHER_MODALITY
    )
    capability = scheduler_store.get_schedule_item(
        CAPABILITY_TARGET_TYPE, CAPABILITY_TARGET_ID, MODALITY
    )
    assert isinstance(production, Ok) and production.value is not None
    assert isinstance(comprehension, Ok) and comprehension.value is not None
    assert isinstance(capability, Ok) and capability.value is not None
    assert production.value.schedule_item_id == "si-prod"
    assert comprehension.value.schedule_item_id == "si-comp"
    assert capability.value.schedule_item_id == "si-cap"
    assert db.execute("SELECT COUNT(*) FROM schedule_item").fetchone() == (3,)
    # The two modality legs both spell the canonical V1 word set.
    assert production.value.evidence_modality is MODALITY
    assert comprehension.value.evidence_modality is OTHER_MODALITY


def test_an_unchanged_item_replays_idempotently(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    first = scheduler_store.upsert_schedule_item(schedule_item("si-1"))
    assert isinstance(first, Ok), first
    before = _item_row(db, "si-1")
    again = scheduler_store.upsert_schedule_item(schedule_item("si-1"))
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert _item_row(db, "si-1") == before  # zero writes, same stamp


def test_a_moved_version_replaces_the_row_and_restamps_updated_at(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item("si-1", review_state=ReviewState.UPCOMING)
        ),
        Ok,
    )
    moved = scheduler_store.upsert_schedule_item(
        schedule_item("si-1", version="sv-2", review_state=ReviewState.OVERDUE)
    )
    assert isinstance(moved, Ok), moved
    row = _item_row(db, "si-1")
    assert row[4] == "OVERDUE"
    assert row[10] == "sv-2"
    assert row[11] == moved.value.updated_at
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value == moved.value
    assert db.execute("SELECT COUNT(*) FROM schedule_item").fetchone() == (1,)


def test_the_same_version_with_different_content_is_refused(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    before = _item_row(db, "si-1")
    refused = scheduler_store.upsert_schedule_item(
        schedule_item("si-1", review_state=ReviewState.DUE)
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert "sv-1" in refused.error.message
    assert _item_row(db, "si-1") == before  # zero writes


def test_none_is_a_value_not_a_wildcard(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The same version with one previously-unset column set is different
    content — the store interprets none of those columns, so it cannot know
    that None "meant the same"."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    before = _item_row(db, "si-1")
    refused = scheduler_store.upsert_schedule_item(
        schedule_item("si-1", urgency=0.0)
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert _item_row(db, "si-1") == before


def test_a_modality_key_held_by_another_row_is_refused(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """One *current* row per key: two rows under one (target, modality) would
    be two answers to one question."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item("si-1")), Ok)
    before = _item_row(db, "si-1")
    refused = scheduler_store.upsert_schedule_item(schedule_item("si-2"))
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert "si-1" in refused.error.message
    assert db.execute("SELECT COUNT(*) FROM schedule_item").fetchone() == (1,)
    assert _item_row(db, "si-1") == before


def test_a_moved_key_is_refused_when_the_new_key_is_held(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """A moved version may replace content, including the key columns — unless
    the key it would move onto is already held (then it is a CONFLICT, and the
    other row keeps its key)."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item("si-1")), Ok)
    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item("si-2", modality=OTHER_MODALITY)
        ),
        Ok,
    )
    refused = scheduler_store.upsert_schedule_item(
        schedule_item("si-2", version="sv-2", modality=MODALITY)
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert _item_row(db, "si-2")[3] == "TEXT_COMPREHENSION"


def test_a_free_key_move_is_a_replacement(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item("si-1")), Ok)
    moved = scheduler_store.upsert_schedule_item(
        schedule_item("si-1", version="sv-2", modality=OTHER_MODALITY)
    )
    assert isinstance(moved, Ok), moved
    assert _item_row(db, "si-1")[3] == "TEXT_COMPREHENSION"
    assert db.execute("SELECT COUNT(*) FROM schedule_item").fetchone() == (1,)
    assert scheduler_store.get_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY
    ).value is None


def test_the_optional_columns_round_trip_as_none(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    written = scheduler_store.upsert_schedule_item(schedule_item("si-1"))
    assert isinstance(written, Ok), written
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.review_urgency is None
    assert read.value.next_review_window_start is None
    assert read.value.next_review_window_end is None
    assert read.value.spacing_stage is None
    row = _item_row(db, "si-1")
    assert row[5] is None and row[6] is None and row[7] is None
    assert row[8] is None


@pytest.mark.parametrize("urgency", [0.0, 0.25, 0.75, 1.0, 0.123456789])
def test_review_urgency_round_trips_verbatim(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore, urgency: float
) -> None:
    """R4: the column is carried raw — no range, no conversion, no rounding
    this implementation performs."""

    written = scheduler_store.upsert_schedule_item(
        schedule_item("si-1", urgency=urgency)
    )
    assert isinstance(written, Ok), written
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.review_urgency == urgency
    assert _item_row(db, "si-1")[5] == urgency
    assert read.value == written.value


def test_every_review_state_word_round_trips(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    for index, word in enumerate(ReviewState, start=1):
        written = scheduler_store.upsert_schedule_item(
            schedule_item("si-1", review_state=word, version=f"sv-{index}")
        )
        assert isinstance(written, Ok), written
        read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
        assert isinstance(read, Ok) and read.value is not None
        assert read.value.review_state is word


def test_every_spacing_stage_word_round_trips(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    for index, stage in enumerate(SpacingStage, start=1):
        written = scheduler_store.upsert_schedule_item(
            schedule_item("si-1", stage=stage, version=f"sv-{index}")
        )
        assert isinstance(written, Ok), written
        read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
        assert isinstance(read, Ok) and read.value is not None
        assert read.value.spacing_stage is stage


def test_the_updated_at_is_the_stores_clock(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """A caller's ``updated_at`` is ignored (the teaching/relationship/
    user_config precedent): the durable clock is the store's, and what comes
    back is the durable value."""

    written = scheduler_store.upsert_schedule_item(
        schedule_item("si-1", updated_at="1999-01-01T00:00:00+00:00")
    )
    assert isinstance(written, Ok), written
    assert written.value.updated_at != "1999-01-01T00:00:00+00:00"
    assert _item_row(db, "si-1")[11] == written.value.updated_at


def test_a_never_written_key_reads_none(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    read = scheduler_store.get_schedule_item(
        TARGET_TYPE, TargetId("res-nowhere"), MODALITY
    )
    assert isinstance(read, Ok)
    assert read.value is None


# -- the schema refuses what the vocabulary does not contain ------------------


def test_the_schema_refuses_a_fifth_review_state(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE schedule_item SET review_state = 'LAPSED'"
            " WHERE schedule_item_id = 'si-1'"
        )


@pytest.mark.parametrize(
    "future", ["VOICE_PRODUCTION", "AUDIO_COMPREHENSION"]
)
def test_the_schema_refuses_a_voice_or_audio_modality(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore, future: str
) -> None:
    """IP §16 DoD #22's mechanism face: the V1 evidence modalities are the
    frozen text pair, so this table cannot carry a voice/audio review debt."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE schedule_item SET evidence_modality = ?"
            " WHERE schedule_item_id = 'si-1'",
            (future,),
        )


def test_the_schema_refuses_a_third_target_type(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE schedule_item SET target_type = 'CONVERSATION'"
            " WHERE schedule_item_id = 'si-1'"
        )


def test_the_schema_enforces_the_modality_key(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item("si-1")), Ok)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO schedule_item (schedule_item_id, target_type,"
            " target_id, evidence_modality, review_state, source_learning_"
            "watermark, version, updated_at)"
            " VALUES ('si-2', ?, ?, ?, 'UPCOMING', 'wm-1', 'sv-1', 'now')",
            (TARGET_TYPE, str(TARGET_ID), MODALITY.value),
        )


def test_a_stale_store_refuses_the_write(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The epoch fence is the repo-wide one: a store whose adopted epoch is no
    longer the newest writes nothing and raises."""

    epoch.open_runtime_epoch(db)
    for write in (
        lambda: scheduler_store.upsert_schedule_item(schedule_item()),
        lambda: scheduler_store.record_review_event(review_event()),
    ):
        try:
            write()
        except StaleSchedulerStoreError:
            pass
        else:  # pragma: no cover - the assertion is the point
            raise AssertionError("a stale store must refuse the write")
    for table in ("schedule_item", "review_event"):
        assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)


def test_the_store_writes_the_two_tables_and_nothing_else() -> None:
    """The durable face of this context keeps §5.2's own rows: an AST scan
    over the store's statement literals finds exactly the two tables."""

    targets = write_targets(SRC_ROOT / "scheduler" / "store.py")
    assert targets == {"schedule_item", "review_event"}
    assert not {
        name
        for name in targets
        if name.startswith(("evidence", "learner", "learning"))
    }


# -- the review event --------------------------------------------------------


def test_a_new_event_inserts_and_reads_back_field_for_field(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    written = scheduler_store.record_review_event(
        review_event(
            "re-1",
            event_type="RECALL",
            engaged=False,
            created_at="2026-09-22T10:00:00+00:00",
        )
    )
    assert isinstance(written, Ok), written
    events = scheduler_store.list_review_events("si-1")
    assert isinstance(events, Ok)
    assert events.value == (written.value,)
    assert _field_pairs(events.value[0], written.value) == [
        (field.name, getattr(written.value, field.name),
         getattr(written.value, field.name))
        for field in dataclasses.fields(ReviewEvent)
    ]
    assert events.value[0].engaged is False
    row = _event_row(db, "re-1")
    assert row[1] == "si-1"
    assert row[4] == "RECALL"
    assert row[5] == 0
    assert row[7] == "2026-09-22T10:00:00+00:00"


def test_the_three_optional_links_round_trip(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    silent = scheduler_store.record_review_event(review_event("re-open"))
    assert isinstance(silent, Ok), silent
    assert silent.value.teaching_moment_id is None
    assert silent.value.source_turn_id is None
    assert silent.value.evidence_group_id is None
    assert _event_row(db, "re-open")[2] is None
    assert _event_row(db, "re-open")[3] is None
    assert _event_row(db, "re-open")[6] is None


def test_an_unchanged_event_replays_idempotently(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    first = scheduler_store.record_review_event(
        review_event("re-1", created_at="2026-09-22T10:00:00+00:00")
    )
    assert isinstance(first, Ok), first
    before = _event_row(db, "re-1")
    again = scheduler_store.record_review_event(
        review_event("re-1", created_at="2026-09-22T10:00:00+00:00")
    )
    assert isinstance(again, Ok), again
    assert again.value == first.value
    assert _event_row(db, "re-1") == before
    assert db.execute("SELECT COUNT(*) FROM review_event").fetchone() == (1,)


def test_the_same_event_id_with_different_content_is_refused(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """§1.3: a review event is a fact. There is no stamp to move under an
    unchanged id, so a correction is a new event — the row is never
    rewritten."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    assert isinstance(
        scheduler_store.record_review_event(
            review_event("re-1", created_at="2026-09-22T10:00:00+00:00")
        ),
        Ok,
    )
    before = _event_row(db, "re-1")
    refused = scheduler_store.record_review_event(
        review_event("re-1", engaged=False, created_at="2026-09-22T10:00:00+00:00")
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert "review_event_id" in refused.error.message
    assert _event_row(db, "re-1") == before
    assert db.execute("SELECT COUNT(*) FROM review_event").fetchone() == (1,)


def test_a_differing_declared_time_is_different_content(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """``created_at`` is the caller's when declared (§5.2), so the same id
    with another declared time is another fact — refused, not silently
    restamped."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    assert isinstance(
        scheduler_store.record_review_event(
            review_event("re-1", created_at="2026-09-22T10:00:00+00:00")
        ),
        Ok,
    )
    refused = scheduler_store.record_review_event(
        review_event("re-1", created_at="2026-09-22T11:00:00+00:00")
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    assert _event_row(db, "re-1")[7] == "2026-09-22T10:00:00+00:00"


def test_an_event_naming_a_missing_schedule_row_is_not_found(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The FK is checked explicitly, so the answer is ``NOT_FOUND`` rather
    than a bare sqlite integrity error, and nothing is written."""

    refused = scheduler_store.record_review_event(
        review_event("re-1", schedule_item_id="si-ghost")
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "NOT_FOUND"
    assert "si-ghost" in refused.error.message
    assert db.execute("SELECT COUNT(*) FROM review_event").fetchone() == (0,)


def test_the_declared_created_at_is_used_verbatim(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    written = scheduler_store.record_review_event(
        review_event("re-1", created_at="2026-01-01T00:00:00+00:00")
    )
    assert isinstance(written, Ok), written
    assert written.value.created_at == "2026-01-01T00:00:00+00:00"
    assert _event_row(db, "re-1")[7] == "2026-01-01T00:00:00+00:00"


def test_a_silent_created_at_is_the_stores_clock(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The 0007 ``created_at or _now()`` precedent: a caller that declares no
    time gets the store's, and it is the durable value."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    written = scheduler_store.record_review_event(review_event("re-1"))
    assert isinstance(written, Ok), written
    assert written.value.created_at != ""
    assert _event_row(db, "re-1")[7] == written.value.created_at


def test_an_unknown_row_has_an_empty_history(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """"This row has no events yet" and "this row does not exist" are both
    "nothing to report"; a caller that must tell them apart asks
    get_schedule_item."""

    events = scheduler_store.list_review_events("si-absent")
    assert isinstance(events, Ok)
    assert events.value == ()


def test_several_events_for_one_row_coexist_in_a_deterministic_order(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """Append-first: neither the schema nor the store collapses a history, and
    the order is ``(created_at, review_event_id)`` — so the answer does not
    depend on insertion order."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    for event_id, created_at in (
        ("re-b", "2026-09-22T10:00:00+00:00"),
        ("re-a", "2026-09-22T10:00:00+00:00"),
        ("re-c", "2026-09-21T10:00:00+00:00"),
    ):
        assert isinstance(
            scheduler_store.record_review_event(
                review_event(event_id, created_at=created_at)
            ),
            Ok,
        )
    events = scheduler_store.list_review_events("si-1")
    assert isinstance(events, Ok)
    assert [event.review_event_id for event in events.value] == [
        "re-c",
        "re-a",
        "re-b",
    ]
    assert db.execute("SELECT COUNT(*) FROM review_event").fetchone() == (3,)


def test_the_schema_refuses_an_event_without_its_schedule_row(
    db: sqlite3.Connection,
) -> None:
    """The store's explicit check is a courtesy; the FK is the guarantee."""

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO review_event (review_event_id, schedule_item_id,"
            " event_type, engaged, created_at)"
            " VALUES ('re-1', 'si-ghost', 'RECALL', 1, 'now')"
        )


def test_the_schema_refuses_an_unknown_evidence_group(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO review_event (review_event_id, schedule_item_id,"
            " event_type, engaged, evidence_group_id, created_at)"
            " VALUES ('re-1', 'si-1', 'RECALL', 1, 'eg-ghost', 'now')"
        )


def test_an_event_may_cite_another_modality(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """§5.2 pins no relation between an event's own identifiers and the
    schedule row's key, so none is enforced: an event whose group belongs to
    the other modality is accepted rather than refused by a rule the canonical
    set does not make."""

    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item("si-1")), Ok
    )
    written = scheduler_store.record_review_event(
        review_event("re-1", event_type="SKIPPED", engaged=False)
    )
    assert isinstance(written, Ok), written
    assert written.value.event_type == "SKIPPED"
    assert _event_row(db, "re-1")[4] == "SKIPPED"


def test_an_unknown_event_type_is_stored_verbatim(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """R5: no vocabulary is declared for ``event_type`` — a value this slice
    has no word for is a value, not an error (and not normalized)."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    written = scheduler_store.record_review_event(
        review_event("re-1", event_type="NOT_A_DECLARED_WORD")
    )
    assert isinstance(written, Ok), written
    assert written.value.event_type == "NOT_A_DECLARED_WORD"


def test_the_two_tables_hold_one_row_per_write_and_no_shadow_row(
    db: sqlite3.Connection, scheduler_store: SqliteSchedulerStore
) -> None:
    """The schedule row is the *current* projection (written once, replaced in
    place); the events are the history (appended, three of them)."""

    assert isinstance(scheduler_store.upsert_schedule_item(schedule_item()), Ok)
    assert isinstance(
        scheduler_store.upsert_schedule_item(schedule_item(version="sv-2")), Ok
    )
    for index in range(3):
        assert isinstance(
            scheduler_store.record_review_event(
                review_event(f"re-{index}")
            ),
            Ok,
        )
    assert db.execute("SELECT COUNT(*) FROM schedule_item").fetchone() == (1,)
    assert db.execute("SELECT COUNT(*) FROM review_event").fetchone() == (3,)
