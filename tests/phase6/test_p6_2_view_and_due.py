"""P6-2 ⑥⑦ — the two faces the Planner and the runtime ask: the view and the
due question.

Both read the **durable** rows and classify them with the same pure function,
so the tests here drive them with rows written through the store's own write
face (a caller that has already decided — a Repair, a later consumer) *and*
with rows the recomputation produced. The membership rule is the one under
test: a row's state at ``as_of`` decides its bucket, ``NOT_SCHEDULED`` belongs
to none, and ``is_review_due`` may never contradict the state the same instant
produced.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from elc.platform.types import EvidenceModality, Ok, TargetId
from elc.scheduler.controller import SchedulerController
from elc.scheduler.spacing import (
    GRACE_DAYS,
    INTERVAL_DAYS,
    SCHEDULER_MODEL_VERSION,
    SPACING_STAGES,
)
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState, ScheduleItem, ScheduleView, SpacingStage

from .conftest import (
    MODALITY,
    OTHER_MODALITY,
    REQUESTED_AT,
    TARGET_ID,
    TARGET_TYPE,
    review_event,
    schedule_item,
)

#: Three windows and one instant: at ``AS_OF`` the first is due, the second has
#: not opened, the third has closed.
AS_OF = "2026-09-22T00:00:00+00:00"
DUE_WINDOW = ("2026-09-20T00:00:00+00:00", "2026-09-25T00:00:00+00:00")
UPCOMING_WINDOW = ("2026-09-24T00:00:00+00:00", "2026-09-27T00:00:00+00:00")
OVERDUE_WINDOW = ("2026-09-10T00:00:00+00:00", "2026-09-15T00:00:00+00:00")
AS_OF_AFTER_THE_GRACE = "2026-09-30T00:00:00+00:00"


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


def windowed(
    item_id: str,
    window: tuple[str, str],
    *,
    target: str = "res-hedge-i-think",
    modality: EvidenceModality = MODALITY,
    state: ReviewState = ReviewState.DUE,
    stage: SpacingStage = SpacingStage.STAGE_1,
    urgency: float = 0.75,
    version: str | None = None,
) -> ScheduleItem:
    """One row a caller decided (the write face takes it as given), used to
    drive the two read faces over a world the store really holds."""

    return schedule_item(
        item_id,
        target_id=TargetId(target),
        modality=modality,
        review_state=state,
        urgency=urgency,
        window_start=window[0],
        window_end=window[1],
        stage=stage,
        version=f"sv-{item_id}" if version is None else version,
    )


def seed(scheduler_store: SqliteSchedulerStore, *items: ScheduleItem) -> None:
    for item in items:
        written = scheduler_store.upsert_schedule_item(item)
        assert isinstance(written, Ok), written


# -- the view -----------------------------------------------------------------


def test_the_empty_world_is_three_empty_buckets(
    scheduler_controller: SchedulerController,
) -> None:
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok), view
    assert view.value.due_items == ()
    assert view.value.overdue_items == ()
    assert view.value.upcoming == ()
    assert view.value.schedule_version == SCHEDULER_MODEL_VERSION
    assert view.value.as_of == AS_OF


def test_the_view_is_stamped_with_the_model_not_a_row_version(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """One view holds many rows and therefore many row versions, so its stamp
    says which policy classified them — and a row's own stamp is a different
    value (its content's), never the view's."""

    seed(scheduler_store, windowed("si-due", DUE_WINDOW))
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    assert view.value.schedule_version == SCHEDULER_MODEL_VERSION
    assert str(view.value.due_items[0].version) != view.value.schedule_version
    assert not str(view.value.due_items[0].version).startswith(
        f"{view.value.schedule_version}-"
    )


def test_each_row_lands_in_the_bucket_its_state_names(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(
        scheduler_store,
        windowed("si-due", DUE_WINDOW, state=ReviewState.DUE, target="res-due"),
        windowed(
            "si-upcoming",
            UPCOMING_WINDOW,
            state=ReviewState.UPCOMING,
            target="res-soon",
            urgency=0.25,
        ),
        windowed(
            "si-overdue",
            OVERDUE_WINDOW,
            state=ReviewState.OVERDUE,
            target="res-late",
            urgency=1.0,
        ),
    )
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    assert [row.schedule_item_id for row in view.value.due_items] == ["si-due"]
    assert [row.schedule_item_id for row in view.value.upcoming] == [
        "si-upcoming"
    ]
    assert [row.schedule_item_id for row in view.value.overdue_items] == [
        "si-overdue"
    ]


def test_a_not_scheduled_row_is_in_no_bucket(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """The membership rule worth stating: a target with no review obligation
    is not "upcoming" — putting it in a bucket would hand the Planner a review
    debt the Scheduler never declared."""

    seed(
        scheduler_store,
        schedule_item(
            "si-unscheduled",
            review_state=ReviewState.NOT_SCHEDULED,
            urgency=0.0,
            version="sv-unscheduled",
        ),
        windowed("si-due", DUE_WINDOW, target="res-due"),
    )
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    members = [
        row.schedule_item_id
        for bucket in (
            view.value.due_items,
            view.value.overdue_items,
            view.value.upcoming,
        )
        for row in bucket
    ]
    assert members == ["si-due"]
    assert "si-unscheduled" not in members


def test_a_row_with_an_incomplete_window_is_in_no_bucket(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Half a window is no window: the row is not scheduled *at that instant*
    and has nothing to be classified by (the same rule ``is_review_due``
    applies)."""

    seed(
        scheduler_store,
        schedule_item(
            "si-half-open",
            target_id=TargetId("res-half-open"),
            window_start=DUE_WINDOW[0],
            window_end=None,
            version="sv-half-open",
        ),
        schedule_item(
            "si-half-closed",
            target_id=TargetId("res-half-closed"),
            window_start=None,
            window_end=DUE_WINDOW[1],
            version="sv-half-closed",
        ),
    )
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    assert (
        view.value.due_items,
        view.value.overdue_items,
        view.value.upcoming,
    ) == ((), (), ())


def test_the_buckets_follow_the_as_of(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """One world, two instants: the rows do not move, the classification
    does."""

    seed(scheduler_store, windowed("si-one", DUE_WINDOW, target="res-one"))
    early = scheduler_controller.get_schedule_view("2026-09-19T00:00:00+00:00")
    late = scheduler_controller.get_schedule_view(AS_OF_AFTER_THE_GRACE)
    assert isinstance(early, Ok) and isinstance(late, Ok)
    assert [row.schedule_item_id for row in early.value.upcoming] == ["si-one"]
    assert early.value.due_items == () and early.value.overdue_items == ()
    assert [row.schedule_item_id for row in late.value.overdue_items] == ["si-one"]
    assert late.value.due_items == () and late.value.upcoming == ()


def test_the_as_of_is_carried_verbatim(
    scheduler_controller: SchedulerController,
) -> None:
    for as_of in (
        "2026-09-22T00:00:00+00:00",
        "2026-09-22T08:00:00+08:00",
        "2026-09-22T00:00:00.123456+00:00",
    ):
        view = scheduler_controller.get_schedule_view(as_of)
        assert isinstance(view, Ok)
        assert view.value.as_of == as_of


def test_the_two_faces_agree_on_the_offset_spelling(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(scheduler_store, windowed("si-one", DUE_WINDOW, target="res-one"))
    shifted = "2026-09-22T08:00:00+08:00"
    view = scheduler_controller.get_schedule_view(shifted)
    due = scheduler_controller.is_review_due(
        TARGET_TYPE, TargetId("res-one"), MODALITY, shifted
    )
    assert isinstance(view, Ok) and isinstance(due, Ok)
    assert [row.schedule_item_id for row in view.value.due_items] == ["si-one"]
    assert due.value is True


@pytest.mark.parametrize("swap", [False, True])
def test_the_bucket_order_is_deterministic(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
    swap: bool,
) -> None:
    """``(next_review_window_start, schedule_item_id)`` ascending: two rows
    sharing a window are ordered by their ids, so two reads of one world answer
    alike regardless of the order the rows arrived in."""

    shared = ("2026-09-21T00:00:00+00:00", "2026-09-24T00:00:00+00:00")
    items = [
        windowed("si-b", shared, target="res-b"),
        windowed("si-a", shared, target="res-a"),
    ]
    if swap:
        items.reverse()
    seed(scheduler_store, *items)
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    assert [row.schedule_item_id for row in view.value.due_items] == [
        "si-a",
        "si-b",
    ]


def test_the_bucket_order_is_by_window_first(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    later = ("2026-09-22T00:00:00+00:00", "2026-09-25T00:00:00+00:00")
    earlier = ("2026-09-20T00:00:00+00:00", "2026-09-23T00:00:00+00:00")
    seed(
        scheduler_store,
        windowed("si-zzz", later, target="res-z"),
        windowed("si-aaa", earlier, target="res-a"),
    )
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    assert [row.schedule_item_id for row in view.value.due_items] == [
        "si-aaa",
        "si-zzz",
    ]


def test_the_view_reads_the_durable_rows_not_a_parameter(
    due_controller: SchedulerController,
    learning_controller,
    conversation,
    silent_coordinator,
) -> None:
    """A row the recomputation wrote appears in the view the read face
    produces — the two faces share the store, not a snapshot."""

    del conversation, learning_controller
    from .conftest import SILENT_UTTERANCE, commit_chat_turn

    assert due_controller is not None
    commit_chat_turn(silent_coordinator, "cm-p6-2-view", SILENT_UTTERANCE, 1)
    first = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    row_id = first.value.schedule_item_id
    reviewed_at = "2026-09-25T09:00:00+00:00"
    assert isinstance(
        due_controller.record_review_event(
            review_event("re-1", schedule_item_id=row_id, created_at=reviewed_at)
        ),
        Ok,
    )
    # One engaged review puts the row on STAGE_1, whose window opens three days
    # after the review; ``inside`` is the instant after that edge.
    inside = "2026-09-28T09:00:00+00:00"
    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, inside
    )
    assert isinstance(written, Ok)
    assert written.value.review_state is ReviewState.DUE
    view = due_controller.get_schedule_view(inside)
    assert isinstance(view, Ok)
    assert [row.schedule_item_id for row in view.value.due_items] == [row_id]
    assert view.value.due_items[0] == written.value
    assert view.value.schedule_version == SCHEDULER_MODEL_VERSION


def test_the_view_refuses_when_a_window_cannot_be_read(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """A view that silently dropped an unreadable row would understate the
    Planner's input, so the read refuses instead."""

    seed(
        scheduler_store,
        schedule_item(
            "si-broken",
            window_start="whenever",
            window_end=DUE_WINDOW[1],
            version="sv-broken",
        ),
    )
    refused = scheduler_controller.get_schedule_view(AS_OF)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "next_review_window_start" in refused.error.message


def test_the_view_refuses_an_unusable_as_of(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(scheduler_store, windowed("si-one", DUE_WINDOW, target="res-one"))
    refused = scheduler_controller.get_schedule_view("not-a-time")
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


def test_a_view_needs_no_as_of_to_be_empty(
    scheduler_controller: SchedulerController,
) -> None:
    """The world with no rows is the one case an unusable ``as_of`` cannot
    reach — there is nothing to classify, so nothing is parsed."""

    view = scheduler_controller.get_schedule_view("")
    assert isinstance(view, Ok)
    assert view.value.as_of == ""


def test_reading_the_view_writes_nothing(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
    db: sqlite3.Connection,
) -> None:
    seed(scheduler_store, windowed("si-one", DUE_WINDOW, target="res-one"))
    before = db.execute("SELECT COUNT(*) FROM schedule_item").fetchone()
    for _ in range(3):
        assert isinstance(scheduler_controller.get_schedule_view(AS_OF), Ok)
    after = db.execute("SELECT COUNT(*) FROM schedule_item").fetchone()
    assert before == after == (1,)
    events = db.execute("SELECT COUNT(*) FROM review_event").fetchone()
    assert events == (0,)


def test_the_three_buckets_partition_the_windowed_rows(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Disjoint and exhaustive over the rows that have a window: every
    windowed row is in exactly one bucket."""

    seed(
        scheduler_store,
        windowed("si-due", DUE_WINDOW, target="res-due"),
        windowed("si-soon", UPCOMING_WINDOW, target="res-soon"),
        windowed("si-late", OVERDUE_WINDOW, target="res-late"),
        schedule_item("si-none", review_state=ReviewState.NOT_SCHEDULED),
    )
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    buckets = {
        "due": {row.schedule_item_id for row in view.value.due_items},
        "overdue": {row.schedule_item_id for row in view.value.overdue_items},
        "upcoming": {row.schedule_item_id for row in view.value.upcoming},
    }
    assert buckets == {
        "due": {"si-due"},
        "overdue": {"si-late"},
        "upcoming": {"si-soon"},
    }
    assert not (buckets["due"] & buckets["overdue"])
    assert not (buckets["due"] & buckets["upcoming"])
    assert not (buckets["overdue"] & buckets["upcoming"])


def test_the_view_is_a_schedule_view_of_schedule_items(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(scheduler_store, windowed("si-one", DUE_WINDOW, target="res-one"))
    view = scheduler_controller.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    assert isinstance(view.value, ScheduleView)
    assert all(
        isinstance(row, ScheduleItem)
        for bucket in (
            view.value.due_items,
            view.value.overdue_items,
            view.value.upcoming,
        )
        for row in bucket
    )


# -- is_review_due ------------------------------------------------------------


def test_a_target_with_no_row_is_not_due(
    scheduler_controller: SchedulerController,
) -> None:
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TargetId("res-nowhere"), MODALITY, AS_OF
    ) == Ok(False)


def test_a_row_with_no_window_is_not_due(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(
        scheduler_store,
        schedule_item("si-1", review_state=ReviewState.NOT_SCHEDULED),
    )
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    ) == Ok(False)


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        (DUE_WINDOW, True),
        (OVERDUE_WINDOW, True),
        (UPCOMING_WINDOW, False),
    ],
)
def test_the_due_answer_is_the_window_opening(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
    window: tuple[str, str],
    expected: bool,
) -> None:
    """``DUE`` and ``OVERDUE`` are both "the window has opened": a caller
    asking whether to review now is not asking which side of the grace band the
    row is on."""

    seed(scheduler_store, windowed("si-1", window))
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    ) == Ok(expected)


def test_the_opening_edge_is_due(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """R3 ④'s inclusive edge, seen from the due question: the instant the
    window opens is already an open window."""

    seed(scheduler_store, windowed("si-1", DUE_WINDOW))
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, DUE_WINDOW[0]
    ) == Ok(True)
    before = (instant(DUE_WINDOW[0]) - timedelta(microseconds=1)).isoformat()
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, before
    ) == Ok(False)


def test_the_closing_edge_is_due_and_the_moment_after_is_still_due(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(scheduler_store, windowed("si-1", DUE_WINDOW))
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, DUE_WINDOW[1]
    ) == Ok(True)
    after = (instant(DUE_WINDOW[1]) + timedelta(days=1)).isoformat()
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, after
    ) == Ok(True)


def test_the_due_answer_is_keyed_by_the_modality(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """§5.2's key: one target may be due in one modality and untouched in the
    other."""

    seed(
        scheduler_store,
        windowed("si-prod", DUE_WINDOW, modality=MODALITY),
        schedule_item(
            "si-comp",
            modality=OTHER_MODALITY,
            review_state=ReviewState.NOT_SCHEDULED,
            version="sv-comp",
        ),
    )
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    ) == Ok(True)
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, OTHER_MODALITY, AS_OF
    ) == Ok(False)


def test_the_due_answer_refuses_an_unusable_as_of(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(scheduler_store, windowed("si-1", DUE_WINDOW))
    refused = scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, "not-a-time"
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


def test_the_due_answer_refuses_an_unreadable_window(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(
        scheduler_store,
        schedule_item(
            "si-broken",
            window_start="whenever",
            window_end="whenever",
            version="sv-broken",
        ),
    )
    refused = scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


@pytest.mark.parametrize(
    "as_of",
    [
        "2026-09-19T00:00:00+00:00",
        "2026-09-20T00:00:00+00:00",
        "2026-09-22T00:00:00+00:00",
        "2026-09-25T00:00:00+00:00",
        "2026-09-26T00:00:00+00:00",
        "2026-11-01T00:00:00+00:00",
    ],
)
def test_the_two_faces_never_disagree(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
    as_of: str,
) -> None:
    """One ruler: the due question and the state the recomputation would
    install are the same function of the same instant, so they cannot
    contradict each other."""

    seed(scheduler_store, windowed("si-1", DUE_WINDOW))
    view = scheduler_controller.get_schedule_view(as_of)
    due = scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, as_of
    )
    assert isinstance(view, Ok) and isinstance(due, Ok)
    due_or_late = [*view.value.due_items, *view.value.overdue_items]
    assert due.value is (len(due_or_late) == 1)
    everything = [
        *due_or_late,
        *view.value.upcoming,
    ]
    assert len(everything) == 1
    assert everything[0].schedule_item_id == "si-1"


@pytest.mark.parametrize("stage_index", [0, 1, 2, 3, 4])
def test_the_due_question_agrees_with_the_policy_ladder(
    scheduler_store: SqliteSchedulerStore,
    stage_index: int,
) -> None:
    """A window built from the declared ladder, asked about at its own edges:
    the answering function is the ladder's, so the edges are the ladder's."""

    anchor = "2026-09-22T10:00:00+00:00"
    stage = SPACING_STAGES[stage_index]
    start = instant(anchor) + timedelta(days=INTERVAL_DAYS[stage])
    end = start + timedelta(days=GRACE_DAYS)
    seed(
        scheduler_store,
        windowed("si-1", (start.isoformat(), end.isoformat())),
    )
    controller = SchedulerController(scheduler_store)
    assert controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, (start - timedelta(seconds=1)).isoformat()
    ) == Ok(False)
    assert controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, start.isoformat()
    ) == Ok(True)
    assert controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, end.isoformat()
    ) == Ok(True)
    assert controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, (end + timedelta(seconds=1)).isoformat()
    ) == Ok(True)


def test_the_due_question_reads_the_durable_row_not_a_cache(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """The answer follows the row: after the window is replaced under a moved
    version, the same question answers differently."""

    seed(scheduler_store, windowed("si-1", UPCOMING_WINDOW))
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    ) == Ok(False)
    moved = windowed("si-1", DUE_WINDOW, version="sv-moved")
    assert isinstance(scheduler_store.upsert_schedule_item(moved), Ok)
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    ) == Ok(True)


def test_a_row_with_only_one_window_end_is_not_due(
    scheduler_controller: SchedulerController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    seed(
        scheduler_store,
        schedule_item(
            "si-1",
            window_start=DUE_WINDOW[0],
            window_end=None,
            version="sv-half",
        ),
    )
    assert scheduler_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, AS_OF
    ) == Ok(False)


@pytest.mark.parametrize(
    "as_of",
    [
        REQUESTED_AT,
        "2026-09-26T09:00:00+00:00",
        "2026-09-28T09:00:00+00:00",
        "2026-09-29T09:00:00+00:00",
        "2026-10-05T09:00:00+00:00",
    ],
)
def test_the_due_question_agrees_with_the_recomputed_state(
    due_controller: SchedulerController,
    as_of: str,
) -> None:
    """The "one ruler" claim over the *recomputation* path (not just a
    hand-written row): the row is anchored by one real review event, the
    recomputation decides its state at ``as_of``, and the due question — read
    off the durable row through the same pure function — answers the same
    thing."""

    first = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    row_id = first.value.schedule_item_id
    reviewed_at = "2026-09-25T09:00:00+00:00"
    assert isinstance(
        due_controller.record_review_event(
            review_event("re-1", schedule_item_id=row_id, created_at=reviewed_at)
        ),
        Ok,
    )
    # STAGE_1: the window opens three days after the review and stays open for
    # GRACE_DAYS more. The ``as_of`` values below fall before, on, and after
    # both edges, so the claim is checked from every side.
    start = instant(reviewed_at) + timedelta(days=INTERVAL_DAYS[SpacingStage.STAGE_1])
    end = start + timedelta(days=GRACE_DAYS)
    assert start.isoformat() != end.isoformat()
    recomputed = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, as_of
    )
    due = due_controller.is_review_due(
        TARGET_TYPE, TARGET_ID, MODALITY, as_of
    )
    assert isinstance(recomputed, Ok) and isinstance(due, Ok)
    expected = recomputed.value.review_state in (
        ReviewState.DUE,
        ReviewState.OVERDUE,
    )
    assert due.value is expected
    read = due_controller.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.review_state is recomputed.value.review_state
