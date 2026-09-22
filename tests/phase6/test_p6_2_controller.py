"""P6-2 ②③④ — the recomputation over the real chain.

The world here is the shipped one (the phase 6 conftest: a real app.db from the
migrations, the real Learning store and authority face, the real scheduler
store and its face). Nothing is seeded and no snapshot is hand-edited: the
learning rows come from the silent chain
(``ConversationCoordinator`` → evidence → projection → freshness), and the
schedule rows come from the recomputation under test.

Two facts about that chain shape these tests, and both are pinned rather than
worked around:

- a silent turn writes **evidence** (the watermark advances) but is **not a
  strong retrieval** — its claim carries ``evaluator_confidence`` 0.60, below
  the estimator's 0.70 strong-retrieval gate — so the recomputation's *window*
  is anchored by the row's review events in these tests, and the freshness leg
  is exercised through the port (which is the seam by design);
- the watermark is the durable evidence sequence, so "a row computed before the
  turn" and "a row computed after it" are two different rows.

Three properties are the point, each asserted from both sides: **determinism**
(the same ``(freshness, history, as_of)`` answers the same row, and the store's
clock is not an input), the **version discipline** (identical content replays
with zero writes, changed content replaces), and the **watermark** (a row
carries the Learning evidence watermark it was computed at, as a decimal
string, which is what lets a consumer recognise a stale row — the comparison is
the consumer's; the store performs none).
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from elc.learning.controller import LearningController
from elc.learning.types import FreshnessView
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    EvidenceModality,
    Ok,
    Result,
    TargetId,
)
from elc.scheduler import spacing as spacing_module
from elc.scheduler import store as scheduler_store_module
from elc.scheduler.controller import SchedulerController, schedule_item_id_for
from elc.scheduler.spacing import GRACE_DAYS, INTERVAL_DAYS, SPACING_STAGES
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState, SpacingStage

from .conftest import (
    MODALITY,
    REQUESTED_AT,
    SILENT_UTTERANCE,
    TARGET_ID,
    TARGET_TYPE,
    commit_chat_turn,
    review_event,
    schedule_item,
)

#: The instants this file uses. ``REQUESTED_AT`` is the corpus turn's own
#: moment; the others are deliberately far apart so a window edge cannot be hit
#: by accident (the edges are computed from the anchor, never assumed).
LATER = "2026-09-25T09:00:00+00:00"
SILENT_AT = "2026-09-26T09:00:00+00:00"

SPACING_SOURCE = Path(spacing_module.__file__).read_text(encoding="utf-8")


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


def window_start(anchor: str, stage: SpacingStage) -> str:
    """The opening instant the declared ladder implies for ``anchor`` — plain
    arithmetic here, never a call to the function under test."""

    return (instant(anchor) + timedelta(days=INTERVAL_DAYS[stage])).isoformat()


class StubLearning:
    """A Learning read face with the caller's freshness and watermark.

    Two of this file's subjects need it, and neither is a faked world: the
    *refusal* paths (a read that fails) need a read that fails, and the
    freshness leg needs a strong retrieval — which the silent chain cannot
    produce (its claim's 0.60 confidence is below the estimator's 0.70 gate,
    pinned below). The store, the rows and the decision are the shipped ones in
    every test that uses this port; only the reading is supplied.
    """

    def __init__(
        self,
        *,
        last_strong_retrieval_at: str | None = None,
        watermark: int = 0,
        refuse_freshness: bool = False,
        refuse_watermark: bool = False,
    ) -> None:
        self._freshness = FreshnessView(
            target_id=TARGET_ID,
            last_strong_retrieval_at=last_strong_retrieval_at,
            days_since_strong_retrieval=(
                None if last_strong_retrieval_at is None else 0.25
            ),
            freshness_band=(
                "UNKNOWN" if last_strong_retrieval_at is None else "FRESH"
            ),
            stability_band="UNTESTED",
        )
        self._watermark = watermark
        self._refuse_freshness = refuse_freshness
        self._refuse_watermark = refuse_watermark

    def get_freshness(self, target_id: TargetId) -> Result[object]:
        if self._refuse_freshness:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="freshness unavailable in this test",
                )
            )
        assert target_id == TARGET_ID, target_id
        return Ok(self._freshness)

    def get_learning_watermark(self) -> Result[int]:
        if self._refuse_watermark:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="watermark unavailable in this test",
                )
            )
        return Ok(self._watermark)


def controller_with(
    store: SqliteSchedulerStore, learning: object
) -> SchedulerController:
    return SchedulerController(store, learning=learning)  # type: ignore[arg-type]


# -- the recomputation's inputs and outputs ----------------------------------


def test_the_controller_reads_the_real_learning_face(
    due_controller: SchedulerController,
    learning_controller: LearningController,
) -> None:
    """The port is satisfied structurally by the shipped authority face: what
    the recomputation reads is what ``LearningController`` answers."""

    read = learning_controller.get_learning_watermark()
    assert isinstance(read, Ok), read
    assert read.value == 0


def test_a_real_turn_writes_evidence_but_is_not_a_strong_retrieval(
    due_controller: SchedulerController,
    learning_controller: LearningController,
    conversation,
    silent_coordinator,
) -> None:
    """The chain fact the window tests rest on, pinned where it happens: the
    silent claim's ``evaluator_confidence`` is 0.60, below the estimator's 0.70
    strong-retrieval gate, so the target gains evidence and a watermark but no
    strong retrieval — and the decision therefore writes a ``NOT_SCHEDULED``
    row even though a review *will* be able to schedule it."""

    del conversation
    completion = commit_chat_turn(
        silent_coordinator, "cm-p6-2-strong", SILENT_UTTERANCE, 1
    )
    assert completion.outcome == "REPLIED_FULL"
    watermark = learning_controller.get_learning_watermark()
    assert isinstance(watermark, Ok) and watermark.value == 1
    freshness = learning_controller.get_freshness(TARGET_ID)
    assert isinstance(freshness, Ok)
    assert freshness.value.last_strong_retrieval_at is None
    assert freshness.value.freshness_band == "UNKNOWN"

    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(written, Ok), written
    assert written.value.review_state is ReviewState.NOT_SCHEDULED
    assert written.value.source_learning_watermark == "1"


def test_an_empty_world_recomputes_to_a_not_scheduled_row(
    due_controller: SchedulerController,
) -> None:
    """No strong retrieval and no review: the row is written with
    ``NOT_SCHEDULED``, no window, no stage, and the urgency anchor of that
    state — never "no row at all"."""

    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(written, Ok), written
    row = written.value
    assert row.review_state is ReviewState.NOT_SCHEDULED
    assert row.next_review_window_start is None
    assert row.next_review_window_end is None
    assert row.spacing_stage is None
    assert row.review_urgency == 0.0
    assert row.source_learning_watermark == "0"


def test_the_row_lands_under_the_derived_id(
    due_controller: SchedulerController,
) -> None:
    """No row exists yet, so the id is derived from the modality key: a retry
    of the same recomputation addresses the same row instead of minting a
    second one under a key §5.2 declares unique."""

    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(written, Ok)
    expected = schedule_item_id_for(TARGET_TYPE, TARGET_ID, MODALITY)
    assert written.value.schedule_item_id == expected
    read = due_controller.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.schedule_item_id == expected


def test_the_derived_id_is_stable_and_key_specific() -> None:
    first = schedule_item_id_for(TARGET_TYPE, TARGET_ID, MODALITY)
    assert first == schedule_item_id_for(TARGET_TYPE, TARGET_ID, MODALITY)
    other_modality = schedule_item_id_for(
        TARGET_TYPE, TARGET_ID, EvidenceModality.TEXT_COMPREHENSION
    )
    other_target = schedule_item_id_for(
        TARGET_TYPE, TargetId("res-something-else"), MODALITY
    )
    assert first != other_modality != other_target
    assert first.startswith("si-") and len(first) == len("si-") + 20
    assert first.isascii()


def test_the_freshness_leg_schedules_a_window(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """The first anchor source end to end: a strong retrieval with no review
    history spaces the target from that retrieval."""

    controller = controller_with(
        scheduler_store, StubLearning(last_strong_retrieval_at=REQUESTED_AT)
    )
    written = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(written, Ok), written
    row = written.value
    assert row.spacing_stage is SpacingStage.STAGE_0
    assert row.next_review_window_start == window_start(
        REQUESTED_AT, SpacingStage.STAGE_0
    )
    assert row.next_review_window_end == (
        instant(row.next_review_window_start) + timedelta(days=GRACE_DAYS)
    ).isoformat()
    assert row.review_state is ReviewState.UPCOMING  # REQUESTED_AT < start
    assert row.review_urgency == 0.25


def test_a_review_event_moves_the_anchor_and_the_ladder(
    due_controller: SchedulerController,
) -> None:
    """The second anchor source, and the ladder: an engaged review is a newer
    anchor *and* a higher rung, so the window moves out from the review rather
    than from anything earlier."""

    first = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    row_id = first.value.schedule_item_id
    recorded = due_controller.record_review_event(
        review_event("re-1", schedule_item_id=row_id, created_at=LATER)
    )
    assert isinstance(recorded, Ok), recorded
    second = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, LATER
    )
    assert isinstance(second, Ok), second
    assert second.value.spacing_stage is SpacingStage.STAGE_1
    assert second.value.next_review_window_start == window_start(
        LATER, SpacingStage.STAGE_1
    )
    assert second.value.version != first.value.version


def test_a_silent_review_moves_the_window_but_not_the_ladder(
    due_controller: SchedulerController,
) -> None:
    wrote = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(wrote, Ok)
    row_id = wrote.value.schedule_item_id
    assert isinstance(
        due_controller.record_review_event(
            review_event(
                "re-silent",
                schedule_item_id=row_id,
                engaged=False,
                created_at=SILENT_AT,
            )
        ),
        Ok,
    )
    second = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, SILENT_AT
    )
    assert isinstance(second, Ok)
    assert second.value.spacing_stage is SpacingStage.STAGE_0
    assert second.value.next_review_window_start == window_start(
        SILENT_AT, SpacingStage.STAGE_0
    )


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 8])
def test_the_ladder_position_is_the_engaged_history_of_the_row(
    due_controller: SchedulerController, count: int
) -> None:
    """``min(engaged events, STAGE_4)``, read back from the store — nothing is
    carried in memory between calls."""

    wrote = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(wrote, Ok)
    row_id = wrote.value.schedule_item_id
    for index in range(count):
        created = (
            instant(REQUESTED_AT) + timedelta(days=index + 1)
        ).isoformat()
        assert isinstance(
            due_controller.record_review_event(
                review_event(
                    f"re-{index}", schedule_item_id=row_id, created_at=created
                )
            ),
            Ok,
        )
    as_of = (instant(REQUESTED_AT) + timedelta(days=count)).isoformat()
    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, as_of
    )
    assert isinstance(written, Ok)
    assert written.value.spacing_stage is SPACING_STAGES[min(count, 4)]


@pytest.mark.parametrize(
    ("offset_days", "expected"),
    [
        (-1.0, ReviewState.UPCOMING),
        (0.0, ReviewState.UPCOMING),
        (1.0, ReviewState.DUE),
        (2.0, ReviewState.DUE),
        (4.0, ReviewState.DUE),
        (4.5, ReviewState.OVERDUE),
        (30.0, ReviewState.OVERDUE),
    ],
)
def test_the_row_state_follows_the_as_of_it_was_asked_about(
    scheduler_store: SqliteSchedulerStore,
    offset_days: float,
    expected: ReviewState,
) -> None:
    """One anchor, seven instants: the window stays where the anchor put it
    (``STAGE_0`` opens one day later and closes three days after that) and the
    state moves through it."""

    anchor = REQUESTED_AT
    as_of = (instant(anchor) + timedelta(days=offset_days)).isoformat()
    controller = controller_with(
        scheduler_store, StubLearning(last_strong_retrieval_at=anchor)
    )
    written = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, as_of
    )
    assert isinstance(written, Ok), written
    assert written.value.review_state is expected
    assert written.value.next_review_window_start == window_start(
        anchor, SpacingStage.STAGE_0
    )
    assert written.value.review_urgency == {
        ReviewState.UPCOMING: 0.25,
        ReviewState.DUE: 0.75,
        ReviewState.OVERDUE: 1.0,
    }[expected]


def test_a_caller_written_row_is_recomputed_in_place(
    due_controller: SchedulerController,
) -> None:
    """A row already under the modality key keeps its id: §5.2's key is unique,
    so a recomputation that minted a second id would be refused rather than
    update the row it was asked about."""

    assert isinstance(
        due_controller.upsert_schedule_item(schedule_item("si-manual")), Ok
    )
    assert isinstance(
        due_controller.record_review_event(
            review_event("re-1", schedule_item_id="si-manual", created_at=LATER)
        ),
        Ok,
    )
    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, LATER
    )
    assert isinstance(written, Ok), written
    assert written.value.schedule_item_id == "si-manual"
    assert written.value.spacing_stage is SpacingStage.STAGE_1
    read = due_controller.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.schedule_item_id == "si-manual"
    assert read.value.version == written.value.version


def test_the_history_read_is_the_rows_own(
    due_controller: SchedulerController,
) -> None:
    """Events hang off the row's id: a recomputation reads the row it is about
    (the durable id it found), not the derived one it would have minted."""

    assert isinstance(
        due_controller.upsert_schedule_item(schedule_item("si-elsewhere")), Ok
    )
    assert isinstance(
        due_controller.record_review_event(
            review_event(
                "re-1", schedule_item_id="si-elsewhere", created_at=LATER
            )
        ),
        Ok,
    )
    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, LATER
    )
    assert isinstance(written, Ok)
    assert written.value.spacing_stage is SpacingStage.STAGE_1
    assert written.value.next_review_window_start == window_start(
        LATER, SpacingStage.STAGE_1
    )


def test_a_recomputation_needs_the_learning_face(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """A controller wired for the durable faces only refuses the decision in
    this domain's words — it never invents a freshness reading."""

    bare = SchedulerController(scheduler_store)
    refused = bare.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "DEPENDENCY_UNAVAILABLE"
    assert "Learning" in refused.error.message
    read = bare.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is None


def test_a_refused_freshness_read_stops_the_recomputation(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    controller = controller_with(
        scheduler_store, StubLearning(refuse_freshness=True)
    )
    refused = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert not isinstance(refused, Ok)
    assert "freshness unavailable" in refused.error.message
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is None


def test_a_refused_watermark_read_stops_the_recomputation(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    controller = controller_with(
        scheduler_store, StubLearning(refuse_watermark=True)
    )
    refused = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert not isinstance(refused, Ok)
    assert "watermark unavailable" in refused.error.message
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is None


def test_an_unusable_as_of_refuses_and_writes_nothing(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """A window the decision could not verify is never written: the policy's
    ``VALIDATION_FAILED`` travels out and the durable world is untouched."""

    controller = controller_with(
        scheduler_store, StubLearning(last_strong_retrieval_at=REQUESTED_AT)
    )
    refused = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, "not-a-time"
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is None


def test_an_unusable_anchor_refuses_and_writes_nothing(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    controller = controller_with(
        scheduler_store, StubLearning(last_strong_retrieval_at="yesterday")
    )
    refused = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "last_strong_retrieval_at" in refused.error.message
    listed = scheduler_store.list_schedule_items()
    assert isinstance(listed, Ok) and listed.value == ()


def test_an_unknown_target_type_is_refused_by_the_durable_vocabulary(
    due_controller: SchedulerController,
) -> None:
    """§5.2's ``target_type`` is one of two canonical words and migration 0012
    enforces it: the recomputation does not re-implement that check, and it
    does not write a row the schema refuses either."""

    refused = due_controller.recompute_schedule_item(
        "PSEUDO_TARGET", TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    listed = due_controller.get_schedule_view(REQUESTED_AT)
    assert isinstance(listed, Ok)
    assert (
        listed.value.due_items,
        listed.value.overdue_items,
        listed.value.upcoming,
    ) == ((), (), ())


# -- determinism -------------------------------------------------------------


def test_the_same_inputs_replay_without_writing(
    due_controller: SchedulerController,
) -> None:
    first = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    second = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(second, Ok)
    assert second.value == first.value
    assert second.value.updated_at == first.value.updated_at
    assert second.value.version == first.value.version


def test_a_later_as_of_inside_the_same_state_writes_nothing(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Content addressing pays off here: a second recomputation at another
    instant with the same state is *the same content*, so it replays instead of
    restamping the row on every read."""

    controller = controller_with(
        scheduler_store, StubLearning(last_strong_retrieval_at=REQUESTED_AT)
    )
    first = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    assert first.value.review_state is ReviewState.UPCOMING
    second = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY,
        (instant(REQUESTED_AT) + timedelta(hours=6)).isoformat(),
    )
    assert isinstance(second, Ok)
    assert second.value.review_state is ReviewState.UPCOMING
    assert second.value.version == first.value.version
    assert second.value.updated_at == first.value.updated_at


def test_a_moved_state_is_a_new_version_and_replaces(
    scheduler_store: SqliteSchedulerStore,
    db: sqlite3.Connection,
) -> None:
    """Different content is a different version, and a moved version replaces
    (the store's §1.4 rule) — the row's ``updated_at`` moves with it and no
    second row appears."""

    controller = controller_with(
        scheduler_store, StubLearning(last_strong_retrieval_at=REQUESTED_AT)
    )
    first = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    assert first.value.review_state is ReviewState.UPCOMING
    moved = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY,
        (instant(REQUESTED_AT) + timedelta(days=2)).isoformat(),
    )
    assert isinstance(moved, Ok), moved
    assert moved.value.review_state is ReviewState.DUE
    assert moved.value.version != first.value.version
    assert moved.value.updated_at != first.value.updated_at
    assert moved.value.next_review_window_start == (
        first.value.next_review_window_start
    )
    rows = db.execute("SELECT COUNT(*) FROM schedule_item").fetchone()
    assert rows is not None and int(rows[0]) == 1


def test_a_new_event_is_a_new_version_and_replaces(
    due_controller: SchedulerController,
) -> None:
    first = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    assert isinstance(
        due_controller.record_review_event(
            review_event(
                "re-1",
                schedule_item_id=first.value.schedule_item_id,
                created_at=LATER,
            )
        ),
        Ok,
    )
    second = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, LATER
    )
    assert isinstance(second, Ok), second
    assert second.value.version != first.value.version
    assert second.value.updated_at != first.value.updated_at


def test_the_stores_clock_is_not_an_input(
    due_controller: SchedulerController, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The version and the window are functions of the decision's own inputs:
    two recomputations of one row under two different store clocks answer the
    same version — the clock only ever stamps ``updated_at``."""

    first = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(first, Ok)
    monkeypatch.setattr(
        scheduler_store_module, "_now", lambda: "1999-01-01T00:00:00+00:00"
    )
    second = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(second, Ok)
    assert second.value.version == first.value.version
    assert second.value.next_review_window_start == (
        first.value.next_review_window_start
    )
    assert second.value.review_urgency == first.value.review_urgency
    assert second.value.updated_at == first.value.updated_at


def test_the_policy_takes_the_instant_and_reads_no_clock() -> None:
    """The pure half of the same claim, checked structurally: no clock call
    anywhere in the policy's module (the docstring may *name* the Learning read
    clock, which is why this is an AST scan and not a text scan)."""

    assert "as_of" in inspect.signature(
        spacing_module.plan_schedule_item
    ).parameters
    calls = [
        node.func.attr
        for node in ast.walk(ast.parse(SPACING_SOURCE))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    for forbidden in ("now", "utcnow", "today", "time", "monotonic", "perf_counter"):
        assert forbidden not in calls, forbidden


def test_the_policy_declares_its_constants_and_holds_nothing_else() -> None:
    """A cache, a memo or a counter would make the answer depend on *when* the
    call happened. The module's top level is its declarations, its functions
    and its one protocol — nothing mutable that a call could write to."""

    tree = ast.parse(SPACING_SOURCE)
    declared = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            declared.update(
                target.id
                for target in targets
                if isinstance(target, ast.Name)
            )
    assert declared == {
        "__all__",
        "GRACE_DAYS",
        "SCHEDULER_MODEL_VERSION",
        "SPACING_STAGES",
        "INTERVAL_DAYS",
        "URGENCY_ANCHORS",
        "T",
        "_ABSENT_FIELD",
        "_VERSION_DIGEST_CHARS",
    }
    assert not [
        node
        for node in tree.body
        if isinstance(node, (ast.Global, ast.Nonlocal))
    ]


# -- the watermark (R6) ------------------------------------------------------


def test_the_row_carries_the_learning_watermark_as_a_decimal_string(
    due_controller: SchedulerController,
    learning_controller: LearningController,
) -> None:
    read = learning_controller.get_learning_watermark()
    assert isinstance(read, Ok)
    written = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(written, Ok)
    assert written.value.source_learning_watermark == str(read.value)


def test_the_watermark_advances_with_real_evidence(
    due_controller: SchedulerController,
    learning_controller: LearningController,
    conversation,
    silent_coordinator,
) -> None:
    """The column is the watermark of the evidence the row was computed from,
    so a row computed after a turn carries a *different* value than one
    computed before it — and the difference is the evidence's own sequence."""

    before = learning_controller.get_learning_watermark()
    assert isinstance(before, Ok) and before.value == 0
    early = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(early, Ok)
    assert early.value.source_learning_watermark == "0"

    del conversation
    commit_chat_turn(silent_coordinator, "cm-p6-2-watermark", SILENT_UTTERANCE, 1)
    after = learning_controller.get_learning_watermark()
    assert isinstance(after, Ok) and after.value > before.value

    late = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(late, Ok)
    assert late.value.source_learning_watermark == str(after.value)
    assert late.value.source_learning_watermark != (
        early.value.source_learning_watermark
    )


def test_a_stale_row_is_detectable_by_the_consumer_comparison(
    due_controller: SchedulerController,
    learning_controller: LearningController,
    conversation,
    silent_coordinator,
) -> None:
    """BF-02 §5's stale-snapshot check, demonstrated where it belongs — in the
    consumer: the row keeps the watermark it was computed at, Learning moves
    on, and the comparison is what notices. The store compares nothing, which
    is why both readings below are accepted."""

    stale = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(stale, Ok)
    assert stale.value.source_learning_watermark == "0"
    del conversation
    commit_chat_turn(silent_coordinator, "cm-p6-2-stale", SILENT_UTTERANCE, 1)
    current = learning_controller.get_learning_watermark()
    assert isinstance(current, Ok) and current.value == 1
    read = due_controller.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.source_learning_watermark != str(current.value)
    assert int(read.value.source_learning_watermark) < current.value
    fresh = due_controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(fresh, Ok)
    assert fresh.value.source_learning_watermark == str(current.value)


def test_the_store_does_not_compare_the_watermark(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """No interpretation below the decision: the store stores whatever string
    it is handed (and a caller's odd one is not a refusal)."""

    assert isinstance(
        scheduler_store.upsert_schedule_item(
            schedule_item("si-1", watermark="not-a-number", version="sv-1")
        ),
        Ok,
    )
    read = scheduler_store.get_schedule_item(TARGET_TYPE, TARGET_ID, MODALITY)
    assert isinstance(read, Ok) and read.value is not None
    assert read.value.source_learning_watermark == "not-a-number"


def test_the_recomputation_carries_the_watermark_verbatim(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    controller = controller_with(
        scheduler_store,
        StubLearning(last_strong_retrieval_at=REQUESTED_AT, watermark=42),
    )
    written = controller.recompute_schedule_item(
        TARGET_TYPE, TARGET_ID, MODALITY, REQUESTED_AT
    )
    assert isinstance(written, Ok)
    assert written.value.source_learning_watermark == "42"
    assert isinstance(written.value.source_learning_watermark, str)


# -- the durable list read the view is built from ----------------------------


def test_the_list_read_answers_the_empty_world(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    listed = scheduler_store.list_schedule_items()
    assert isinstance(listed, Ok)
    assert listed.value == ()


def test_the_list_read_returns_every_row_in_id_order(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Insertion order is deliberately not the answer: the read orders by the
    row's own identity, so two reads of one world answer alike."""

    for name, target in (("si-c", "res-c"), ("si-a", "res-a"), ("si-b", "res-b")):
        assert isinstance(
            scheduler_store.upsert_schedule_item(
                schedule_item(name, target_id=TargetId(target), version=name)
            ),
            Ok,
        )
    listed = scheduler_store.list_schedule_items()
    assert isinstance(listed, Ok)
    assert [row.schedule_item_id for row in listed.value] == [
        "si-a",
        "si-b",
        "si-c",
    ]
    assert [str(row.target_id) for row in listed.value] == [
        "res-a",
        "res-b",
        "res-c",
    ]


def test_the_list_read_returns_rows_verbatim(
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """No filtering, no classification, no derivation: the store hands back
    what it holds (the caller's ``updated_at`` is still ignored — the durable
    clock is the store's), and the due decision is the controller's."""

    written = schedule_item(
        "si-1",
        review_state=ReviewState.OVERDUE,
        urgency=0.123456789,
        window_start="2030-01-01T00:00:00+00:00",
        window_end="2030-01-04T00:00:00+00:00",
        stage=SpacingStage.STAGE_3,
    )
    assert isinstance(scheduler_store.upsert_schedule_item(written), Ok)
    listed = scheduler_store.list_schedule_items()
    assert isinstance(listed, Ok)
    assert listed.value == (
        replace(written, updated_at=listed.value[0].updated_at),
    )
    assert listed.value[0].review_state is ReviewState.OVERDUE
    assert listed.value[0].review_urgency == 0.123456789
    assert listed.value[0].spacing_stage is SpacingStage.STAGE_3


def test_the_list_read_is_not_a_scheduler_face() -> None:
    """The store lists rows; it does not decide. ``get_schedule_view`` and
    ``is_review_due`` stay the controller's (D-INV-009)."""

    assert hasattr(SqliteSchedulerStore, "list_schedule_items")
    for name in ("get_schedule_view", "is_review_due", "recompute_schedule_item"):
        assert not hasattr(SqliteSchedulerStore, name), name
