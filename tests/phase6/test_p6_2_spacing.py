"""P6-2 ① — the spacing policy, as a pure module.

Everything here runs without a database, a store or a clock: the decision is a
function of ``(freshness, history, as_of)``, so it is pinned as one. What the
tests assert is the *rule* this repository declared (R3 / R4 / R7) — the
canonical documents pin the columns and no algorithm, so the numbers below are
read from ``elc.scheduler.spacing``'s own declarations and from arithmetic
written out here (never by calling the function under test to build its own
expectation).

The freshness input is the **real** ``elc.learning.types.FreshnessView``: it
satisfies ``FreshnessPort`` structurally, and using it here is what makes that
claim checkable rather than asserted.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timedelta

import pytest

from elc.learning.types import FreshnessView
from elc.platform.types import EvidenceModality, Ok, TargetId
from elc.scheduler import spacing
from elc.scheduler.spacing import (
    GRACE_DAYS,
    INTERVAL_DAYS,
    SCHEDULER_MODEL_VERSION,
    SPACING_STAGES,
    URGENCY_ANCHORS,
    FreshnessPort,
    anchor_of,
    next_window,
    parse_instant,
    plan_schedule_item,
    row_version,
    stage_from_history,
    state_at,
    urgency_of,
    version_content,
)
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    SpacingStage,
)

ANCHOR = "2026-09-22T10:00:00+00:00"
MODALITY = EvidenceModality.TEXT_PRODUCTION
TARGET = TargetId("res-hedge-i-think")


def freshness(last_strong_retrieval_at: str | None) -> FreshnessView:
    """The real Learning freshness record, with the fields the decision does
    *not* read filled with values a read clock would produce — so the tests
    below can prove they are not consumed."""

    return FreshnessView(
        target_id=TARGET,
        last_strong_retrieval_at=last_strong_retrieval_at,
        days_since_strong_retrieval=(
            None if last_strong_retrieval_at is None else 0.5
        ),
        freshness_band="UNKNOWN" if last_strong_retrieval_at is None else "FRESH",
        stability_band="HIGH",
    )


def event(
    name: str,
    *,
    engaged: bool = True,
    created_at: str = ANCHOR,
    event_type: str = "RECALL_ATTEMPT",
) -> ReviewEvent:
    return ReviewEvent(
        review_event_id=name,
        schedule_item_id="si-1",
        event_type=event_type,
        engaged=engaged,
        created_at=created_at,
    )


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text)


def window_of(anchor: str, stage: SpacingStage) -> tuple[str, str]:
    """The window the declared ladder implies, computed here in plain
    arithmetic — the expectation is never taken from the function under
    test."""

    start = instant(anchor) + timedelta(days=INTERVAL_DAYS[stage])
    return start.isoformat(), (start + timedelta(days=GRACE_DAYS)).isoformat()


# -- the declared constants --------------------------------------------------


def test_the_ladder_is_the_declared_expand_spacing_one() -> None:
    """R3's implementation declaration, value for value: 1 / 3 / 7 / 16 / 35
    days over ``STAGE_0`` … ``STAGE_4``, with a three-day grace band."""

    assert INTERVAL_DAYS == {
        SpacingStage.STAGE_0: 1,
        SpacingStage.STAGE_1: 3,
        SpacingStage.STAGE_2: 7,
        SpacingStage.STAGE_3: 16,
        SpacingStage.STAGE_4: 35,
    }
    assert GRACE_DAYS == 3
    assert SCHEDULER_MODEL_VERSION == "sd1"


def test_the_ladder_covers_every_declared_stage() -> None:
    assert set(INTERVAL_DAYS) == set(SpacingStage)
    assert set(SPACING_STAGES) == set(SpacingStage)


def test_the_stage_order_is_the_enums_declaration_order() -> None:
    """The clamp needs one order; the enum declares one, and the policy's
    tuple is that order rather than a second list that could drift."""

    assert SPACING_STAGES == tuple(SpacingStage)
    assert SPACING_STAGES[0] is SpacingStage.STAGE_0
    assert SPACING_STAGES[-1] is SpacingStage.STAGE_4


def test_the_ladder_expands_strictly() -> None:
    intervals = [INTERVAL_DAYS[stage] for stage in SPACING_STAGES]
    assert intervals == sorted(intervals)
    assert len(set(intervals)) == len(intervals)


def test_the_module_docstring_declares_what_it_owns_and_what_it_avoids() -> None:
    """A policy a consumer cannot read is a rule nobody can check: the module
    says which decision it holds, that the canonical documents pin no
    algorithm, where calibration lives, and that it opens no connection, reads
    no clock and writes nothing."""

    docstring = spacing.__doc__ or ""
    for phrase in (
        "R3",
        "Phase 11",
        "zero SQL, zero clock, zero I/O",
        "calibration",
        "revisit condition",
    ):
        assert phrase.lower() in docstring.lower(), phrase


def test_the_module_docstring_names_the_freshness_fields_it_refuses() -> None:
    """The three fields that must not enter the decision, each with its
    reason: the two derived from the Learning read clock cannot be a function
    of ``as_of``, and the stability signal is a calibration question."""

    docstring = spacing.__doc__ or ""
    for phrase in (
        "freshness_band",
        "days_since_strong_retrieval",
        "stability_band",
        "read clock",
    ):
        assert phrase in docstring, phrase


def test_the_module_docstring_separates_instants_from_byte_order() -> None:
    """p6-1 pinned ``created_at``'s replay question as a byte comparison; this
    module answers a different question and says so."""

    docstring = spacing.__doc__ or ""
    assert "fromisoformat" in docstring
    assert "byte order" in docstring
    assert "instant" in docstring


# -- parse_instant -----------------------------------------------------------


def test_a_well_formed_instant_parses_to_that_moment() -> None:
    parsed = parse_instant(ANCHOR, field="as_of")
    assert isinstance(parsed, Ok), parsed
    assert parsed.value == instant(ANCHOR)
    assert parsed.value.tzinfo is not None


@pytest.mark.parametrize(
    "text",
    [
        "2026-09-22T10:00:00Z",
        "2026-09-22T10:00:00+00:00",
        "2026-09-22T18:00:00+08:00",
        "2026-09-22T10:00:00.500+00:00",
    ],
)
def test_every_iso_8601_spelling_the_inputs_can_carry_parses(text: str) -> None:
    parsed = parse_instant(text, field="as_of")
    assert isinstance(parsed, Ok), parsed


def test_an_empty_instant_is_refused_in_this_domains_words() -> None:
    refused = parse_instant("", field="next_review_window_start")
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "next_review_window_start" in refused.error.message
    assert "ISO-8601" in refused.error.message


@pytest.mark.parametrize(
    "text",
    ["nope", "2026-13-01T00:00:00+00:00", "22-09-2026 10:00", "10:00:00"],
)
def test_an_unparseable_instant_is_refused_without_quoting_an_exception(
    text: str,
) -> None:
    refused = parse_instant(text, field="as_of")
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "as_of" in refused.error.message
    # The message is this domain's wording: no exception class name, no
    # library phrasing (the store's one-vocabulary rule).
    for leak in ("ValueError", "Traceback", "datetime.", "Invalid isoformat"):
        assert leak not in refused.error.message, leak


def test_a_naive_instant_is_refused_rather_than_assumed_utc() -> None:
    refused = parse_instant("2026-09-22T10:00:00", field="created_at")
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "offset" in refused.error.message
    assert "created_at" in refused.error.message


def test_parsing_is_deterministic() -> None:
    first = parse_instant(ANCHOR, field="as_of")
    second = parse_instant(ANCHOR, field="as_of")
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first == second


# -- stage_from_history ------------------------------------------------------


@pytest.mark.parametrize(
    ("engaged", "expected"),
    [
        (0, SpacingStage.STAGE_0),
        (1, SpacingStage.STAGE_1),
        (2, SpacingStage.STAGE_2),
        (3, SpacingStage.STAGE_3),
        (4, SpacingStage.STAGE_4),
    ],
)
def test_the_stage_is_the_engaged_count_over_the_declared_ladder(
    engaged: int, expected: SpacingStage
) -> None:
    events = tuple(event(f"re-{index}") for index in range(engaged))
    assert stage_from_history(events) is expected


def test_the_stage_clamps_at_the_top_of_the_ladder() -> None:
    """Eleven engaged reviews are still ``STAGE_4``: the ladder has five rungs
    and the count does not invent a sixth."""

    events = tuple(event(f"re-{index}") for index in range(11))
    assert stage_from_history(events) is SpacingStage.STAGE_4


@pytest.mark.parametrize("engaged", [0, 3, 9])
def test_a_silent_event_does_not_advance_the_ladder(engaged: int) -> None:
    """``engaged`` is §5.2's typed column: a review that did not engage the
    target is history but not progress."""

    events = tuple(event(f"re-{index}") for index in range(engaged)) + (
        event("re-silent", engaged=False),
    )
    assert stage_from_history(events) is SPACING_STAGES[min(engaged, 4)]


def test_an_empty_history_is_the_first_rung() -> None:
    assert stage_from_history(()) is SpacingStage.STAGE_0


def test_the_stage_of_a_long_history_stays_the_top_rung() -> None:
    assert stage_from_history(tuple(event(f"re-{i}") for i in range(40))) is (
        SpacingStage.STAGE_4
    )


# -- anchor_of ---------------------------------------------------------------


def test_no_strong_retrieval_and_no_event_means_no_anchor() -> None:
    """The ``NOT_SCHEDULED`` case: nothing has ever touched this target, which
    is an answer and not an error."""

    anchor = anchor_of(freshness(None), ())
    assert isinstance(anchor, Ok), anchor
    assert anchor.value is None


def test_a_strong_retrieval_alone_anchors_the_row() -> None:
    anchor = anchor_of(freshness(ANCHOR), ())
    assert isinstance(anchor, Ok)
    assert anchor.value == ANCHOR


def test_a_review_event_alone_anchors_the_row() -> None:
    """A target can be reviewed before it is ever "strongly retrieved" — the
    history is the second source, not a fallback that needs the first."""

    anchor = anchor_of(freshness(None), (event("re-1", created_at=ANCHOR),))
    assert isinstance(anchor, Ok)
    assert anchor.value == ANCHOR


def test_the_newest_of_the_two_sources_wins() -> None:
    newer = "2026-09-22T12:00:00+00:00"
    anchor = anchor_of(freshness(ANCHOR), (event("re-1", created_at=newer),))
    assert isinstance(anchor, Ok)
    assert anchor.value == newer


def test_the_strong_retrieval_wins_when_it_is_newer() -> None:
    newer = "2026-09-22T12:00:00+00:00"
    anchor = anchor_of(freshness(newer), (event("re-1", created_at=ANCHOR),))
    assert isinstance(anchor, Ok)
    assert anchor.value == newer


def test_the_newest_event_of_several_wins() -> None:
    events = (
        event("re-1", created_at="2026-09-20T10:00:00+00:00"),
        event("re-2", created_at="2026-09-21T10:00:00+00:00"),
        event("re-3", created_at="2026-09-19T10:00:00+00:00"),
    )
    anchor = anchor_of(freshness(None), events)
    assert isinstance(anchor, Ok)
    assert anchor.value == "2026-09-21T10:00:00+00:00"


def test_a_silent_event_still_anchors_the_window() -> None:
    """Engagement moves the *ladder*; recency moves the *window*. A review
    that did not engage the target was still a review of it."""

    anchor = anchor_of(
        freshness(None), (event("re-1", engaged=False, created_at=ANCHOR),)
    )
    assert isinstance(anchor, Ok)
    assert anchor.value == ANCHOR


def test_an_undeclared_event_time_is_skipped() -> None:
    """The store stamps ``created_at`` on the way in, so an empty one never
    reached the database: it names no moment and cannot anchor anything."""

    anchor = anchor_of(
        freshness(ANCHOR),
        (event("re-1", created_at=""), event("re-2", created_at="")),
    )
    assert isinstance(anchor, Ok)
    assert anchor.value == ANCHOR


def test_only_undeclared_event_times_means_no_anchor() -> None:
    anchor = anchor_of(freshness(None), (event("re-1", created_at=""),))
    assert isinstance(anchor, Ok)
    assert anchor.value is None


def test_an_unusable_strong_retrieval_refuses_the_whole_anchor() -> None:
    refused = anchor_of(freshness("not-a-time"), ())
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "last_strong_retrieval_at" in refused.error.message


def test_an_unusable_event_time_names_the_event_it_came_from() -> None:
    refused = anchor_of(freshness(None), (event("re-7", created_at="nope"),))
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "re-7" in refused.error.message


def test_a_naive_event_time_refuses_the_anchor() -> None:
    refused = anchor_of(
        freshness(None), (event("re-1", created_at="2026-09-22T10:00:00"),)
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


def test_one_unusable_candidate_refuses_even_with_a_usable_newer_one() -> None:
    """No silent skipping of a *declared* time: a row whose history cannot be
    read is not a row to guess about."""

    refused = anchor_of(
        freshness(ANCHOR),
        (event("re-1", created_at="yesterday"),),
    )
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


def test_the_same_instant_in_two_spellings_ties_deterministically() -> None:
    """Two candidates naming one instant are one moment; the winner is stable
    across calls (the tie-break is the string, and only has to be total)."""

    events = (
        event("re-1", created_at="2026-09-22T18:00:00+08:00"),
        event("re-2", created_at="2026-09-22T10:00:00+00:00"),
    )
    first = anchor_of(freshness(None), events)
    second = anchor_of(freshness(None), events)
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value == second.value
    assert instant(str(first.value)) == instant(ANCHOR)


def test_the_anchor_is_returned_in_the_callers_own_spelling() -> None:
    """The winner's *raw* string comes back, so the window it produces keeps
    that offset instead of a normalized one."""

    anchor = anchor_of(freshness("2026-09-22T18:00:00+08:00"), ())
    assert isinstance(anchor, Ok)
    assert anchor.value == "2026-09-22T18:00:00+08:00"


def test_anchoring_is_deterministic() -> None:
    events = (event("re-1"), event("re-2", created_at="2026-09-21T00:00:00+00:00"))
    assert anchor_of(freshness(ANCHOR), events) == anchor_of(
        freshness(ANCHOR), events
    )


def test_the_real_freshness_view_satisfies_the_port() -> None:
    """``FreshnessPort`` is structural on purpose: the Learning record is
    handed over as it is, with no adapter and no copied field."""

    record = freshness(ANCHOR)
    port: FreshnessPort = record
    assert port.last_strong_retrieval_at == ANCHOR
    assert dataclasses.is_dataclass(port)  # it *is* the record, not a copy


# -- next_window -------------------------------------------------------------


@pytest.mark.parametrize("stage", list(SpacingStage))
def test_the_window_is_the_anchor_plus_the_stage_interval(
    stage: SpacingStage,
) -> None:
    expected = window_of(ANCHOR, stage)
    window = next_window(ANCHOR, stage)
    assert isinstance(window, Ok), window
    assert window.value == expected


@pytest.mark.parametrize("stage", list(SpacingStage))
def test_the_grace_band_separates_the_two_ends(stage: SpacingStage) -> None:
    window = next_window(ANCHOR, stage)
    assert isinstance(window, Ok)
    start, end = window.value
    assert instant(end) - instant(start) == timedelta(days=GRACE_DAYS)


def test_the_window_keeps_the_anchors_offset() -> None:
    window = next_window("2026-09-22T18:00:00+08:00", SpacingStage.STAGE_0)
    assert isinstance(window, Ok)
    assert window.value == (
        "2026-09-23T18:00:00+08:00",
        "2026-09-26T18:00:00+08:00",
    )


def test_a_zulu_anchor_comes_back_spelled_the_way_datetime_spells_it() -> None:
    """Documented spelling, not a semantics change: the instant is the same
    and the offset is still zero — the emitted form is ``isoformat``'s."""

    window = next_window("2026-09-22T10:00:00Z", SpacingStage.STAGE_0)
    assert isinstance(window, Ok)
    assert window.value == (
        "2026-09-23T10:00:00+00:00",
        "2026-09-26T10:00:00+00:00",
    )
    assert instant(window.value[0]) == instant("2026-09-23T10:00:00Z")


def test_a_window_across_a_dst_boundary_is_still_the_same_wall_offset() -> None:
    """The arithmetic adds days to the instant; the offset travels unchanged
    (no conversion happens anywhere in this module)."""

    window = next_window("2026-03-27T12:00:00+02:00", SpacingStage.STAGE_2)
    assert isinstance(window, Ok)
    assert window.value[0] == "2026-04-03T12:00:00+02:00"
    assert window.value[1] == "2026-04-06T12:00:00+02:00"


def test_an_unusable_anchor_refuses_the_window() -> None:
    refused = next_window("nope", SpacingStage.STAGE_0)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "anchor" in refused.error.message


def test_a_naive_anchor_refuses_the_window() -> None:
    refused = next_window("2026-09-22T10:00:00", SpacingStage.STAGE_0)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


@pytest.mark.parametrize("stage", list(SpacingStage))
def test_the_window_ends_after_it_starts(stage: SpacingStage) -> None:
    window = next_window(ANCHOR, stage)
    assert isinstance(window, Ok)
    assert instant(window.value[1]) > instant(window.value[0])


# -- state_at ----------------------------------------------------------------


def test_the_instant_before_the_window_is_upcoming() -> None:
    start, end = window_of(ANCHOR, SpacingStage.STAGE_2)
    before = (instant(start) - timedelta(microseconds=1)).isoformat()
    state = state_at(before, start, end)
    assert isinstance(state, Ok)
    assert state.value is ReviewState.UPCOMING


def test_the_instant_the_window_opens_is_due() -> None:
    """``as_of == start`` is ``DUE``: the boundary is inclusive on both ends
    (R3 ④), and a strict comparison would call the opening moment "upcoming"."""

    start, end = window_of(ANCHOR, SpacingStage.STAGE_2)
    state = state_at(start, start, end)
    assert isinstance(state, Ok)
    assert state.value is ReviewState.DUE


def test_an_instant_inside_the_window_is_due() -> None:
    start, end = window_of(ANCHOR, SpacingStage.STAGE_2)
    middle = (instant(start) + timedelta(days=1)).isoformat()
    state = state_at(middle, start, end)
    assert isinstance(state, Ok)
    assert state.value is ReviewState.DUE


def test_the_instant_the_window_closes_is_due() -> None:
    start, end = window_of(ANCHOR, SpacingStage.STAGE_2)
    state = state_at(end, start, end)
    assert isinstance(state, Ok)
    assert state.value is ReviewState.DUE


def test_the_instant_after_the_window_is_overdue() -> None:
    start, end = window_of(ANCHOR, SpacingStage.STAGE_2)
    after = (instant(end) + timedelta(microseconds=1)).isoformat()
    state = state_at(after, start, end)
    assert isinstance(state, Ok)
    assert state.value is ReviewState.OVERDUE


def test_the_grace_band_is_the_due_band() -> None:
    """Every day inside the window is ``DUE`` and the first instant of the day
    after it is ``OVERDUE`` — the grace in ``window_of`` is the three days
    ``GRACE_DAYS`` declares, not an extra tolerance."""

    start, end = window_of(ANCHOR, SpacingStage.STAGE_0)
    assert state_at(start, start, end).value is ReviewState.DUE
    assert state_at(end, start, end).value is ReviewState.DUE
    beyond = (instant(end) + timedelta(days=1)).isoformat()
    assert state_at(beyond, start, end).value is ReviewState.OVERDUE


def test_the_comparison_is_by_instant_not_by_string() -> None:
    """``09:00-08:00`` is ``17:00+00:00``: inside a window that opened at
    ``10:00+00:00``. Compared as strings the same value sorts *before* the
    window start and would be called upcoming."""

    start, end = window_of(ANCHOR, SpacingStage.STAGE_2)
    as_of = "2026-09-29T09:00:00-08:00"
    assert as_of < start  # the byte comparison the policy does *not* make
    assert instant(as_of) > instant(start)
    assert instant(as_of) < instant(end)
    state = state_at(as_of, start, end)
    assert isinstance(state, Ok)
    assert state.value is ReviewState.DUE


def test_not_scheduled_is_decided_by_the_absence_of_an_anchor() -> None:
    """``state_at`` answers about a window and nothing else: the fourth state
    is not a comparison result, it is what "no anchor" means (rule ① of the
    module docstring, and the plan tests below pin that this is where it comes
    from)."""

    docstring = spacing.__doc__ or ""
    assert "NOT_SCHEDULED" in docstring
    assert "no window" in docstring
    planned = plan_schedule_item.__doc__ or ""
    assert "NOT_SCHEDULED" in planned
    assert "no anchor" in planned


def test_an_unusable_as_of_refuses_the_state() -> None:
    start, end = window_of(ANCHOR, SpacingStage.STAGE_0)
    refused = state_at("nope", start, end)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "as_of" in refused.error.message


def test_an_unusable_window_start_refuses_the_state() -> None:
    refused = state_at(ANCHOR, "nope", ANCHOR)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "next_review_window_start" in refused.error.message


def test_an_unusable_window_end_refuses_the_state() -> None:
    refused = state_at(ANCHOR, ANCHOR, "nope")
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert "next_review_window_end" in refused.error.message


def test_a_naive_as_of_refuses_the_state() -> None:
    refused = state_at("2026-09-22T10:00:00", ANCHOR, ANCHOR)
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "VALIDATION_FAILED"


def test_state_is_deterministic_across_calls() -> None:
    start, end = window_of(ANCHOR, SpacingStage.STAGE_1)
    assert state_at(start, start, end) == state_at(start, start, end)
    assert state_at(end, start, end) == state_at(end, start, end)


# -- urgency_of --------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ReviewState.NOT_SCHEDULED, 0.0),
        (ReviewState.UPCOMING, 0.25),
        (ReviewState.DUE, 0.75),
        (ReviewState.OVERDUE, 1.0),
    ],
)
def test_the_urgency_is_the_states_anchor_value(
    state: ReviewState, expected: float
) -> None:
    assert urgency_of(state) == expected


def test_the_urgency_table_is_exactly_the_four_states() -> None:
    assert set(URGENCY_ANCHORS) == set(ReviewState)
    assert len(URGENCY_ANCHORS) == 4


def test_the_urgency_reads_the_table_rather_than_a_second_copy() -> None:
    """One declaration: every answer comes from ``URGENCY_ANCHORS``."""

    for state in ReviewState:
        assert urgency_of(state) == URGENCY_ANCHORS[state]


def test_no_sub_state_interpolation_exists() -> None:
    """One state, one anchor (R4): the function takes a state and nothing
    else, so there is no elapsed time to interpolate over."""

    import inspect

    assert list(inspect.signature(urgency_of).parameters) == ["state"]


# -- version_content / row_version -------------------------------------------


def content(**overrides: object) -> dict[str, str]:
    base: dict[str, object] = {
        "target_type": "RESOURCE",
        "target_id": TARGET,
        "evidence_modality": MODALITY,
        "review_state": ReviewState.DUE,
        "review_urgency": 0.75,
        "next_review_window_start": "2026-09-23T10:00:00+00:00",
        "next_review_window_end": "2026-09-26T10:00:00+00:00",
        "spacing_stage": SpacingStage.STAGE_0,
        "source_learning_watermark": "1",
    }
    base.update(overrides)
    return version_content(**base)  # type: ignore[arg-type]


def test_the_version_is_the_model_stamp_plus_a_twelve_character_digest() -> None:
    version = str(row_version(content()))
    prefix, _, digest = version.partition("-")
    assert prefix == SCHEDULER_MODEL_VERSION
    assert len(digest) == 12
    assert all(character in "0123456789abcdef" for character in digest)


def test_the_version_is_the_sha256_of_the_canonical_json() -> None:
    """The stamp is checkable by hand: sorted keys, no whitespace,
    ``ensure_ascii=False`` over the payload this policy builds."""

    payload = content()
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    assert str(row_version(payload)) == f"{SCHEDULER_MODEL_VERSION}-{expected}"


def test_the_same_content_stamps_the_same_version() -> None:
    assert row_version(content()) == row_version(content())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_type", "CAPABILITY"),
        ("target_id", TargetId("res-something-else")),
        ("evidence_modality", EvidenceModality.TEXT_COMPREHENSION),
        ("review_state", ReviewState.OVERDUE),
        ("review_urgency", 1.0),
        ("next_review_window_start", "2026-09-24T10:00:00+00:00"),
        ("next_review_window_end", "2026-09-27T10:00:00+00:00"),
        ("spacing_stage", SpacingStage.STAGE_4),
        ("source_learning_watermark", "2"),
    ],
)
def test_every_computed_column_moves_the_version(field: str, value: object) -> None:
    """The digest covers every column the durable writer compares for
    content — so "different content under one stamp" cannot reach the store
    through this policy."""

    assert row_version(content(**{field: value})) != row_version(content())


def test_absent_and_empty_are_two_different_stamps() -> None:
    """A ``?`` column that is absent and one that holds ``""`` are different
    durable values, so the payload must not fold them together."""

    absent = row_version(content(next_review_window_start=None))
    empty = row_version(content(next_review_window_start=""))
    present = row_version(content())
    assert absent != empty != present
    assert absent != present


def test_the_version_is_a_schedule_version_not_a_bare_string() -> None:
    from elc.platform.types import ScheduleVersion

    assert isinstance(row_version(content()), str)
    assert ScheduleVersion(str(row_version(content()))) == row_version(content())


def test_two_payloads_that_differ_only_in_ordering_stamp_alike() -> None:
    """``sort_keys`` is what makes the canonical form canonical: a mapping
    built in another order is the same content."""

    first = content()
    reordered = dict(reversed(list(first.items())))
    assert list(first) != list(reordered)
    assert row_version(first) == row_version(reordered)


# -- plan_schedule_item ------------------------------------------------------


def plan(**overrides: object) -> ScheduleItem:
    base: dict[str, object] = {
        "schedule_item_id": "si-derived",
        "target_type": "RESOURCE",
        "target_id": TARGET,
        "evidence_modality": MODALITY,
        "freshness": freshness(ANCHOR),
        "events": (),
        "source_learning_watermark": "1",
        "as_of": ANCHOR,
    }
    base.update(overrides)
    planned = plan_schedule_item(**base)  # type: ignore[arg-type]
    assert isinstance(planned, Ok), planned
    return planned.value


def test_a_row_without_an_anchor_is_not_scheduled() -> None:
    """No strong retrieval and no review: ``NOT_SCHEDULED`` with no window and
    no stage, and the urgency anchor that belongs to that state."""

    row = plan(freshness=freshness(None))
    assert row.review_state is ReviewState.NOT_SCHEDULED
    assert row.next_review_window_start is None
    assert row.next_review_window_end is None
    assert row.spacing_stage is None
    assert row.review_urgency == 0.0


def test_a_row_without_an_anchor_is_still_written() -> None:
    """The row exists: "this target has no review obligation yet" is a fact
    the Planner needs, not an absent answer."""

    row = plan(freshness=freshness(None))
    assert row.schedule_item_id == "si-derived"
    assert row.target_id == TARGET
    assert row.source_learning_watermark == "1"


@pytest.mark.parametrize("stage_index", [0, 1, 2, 3, 4, 5, 9])
def test_an_anchored_row_carries_the_window_its_history_implies(
    stage_index: int,
) -> None:
    events = tuple(event(f"re-{index}") for index in range(stage_index))
    stage = SPACING_STAGES[min(stage_index, 4)]
    row = plan(events=events, as_of=ANCHOR)
    assert row.spacing_stage is stage
    assert (row.next_review_window_start, row.next_review_window_end) == (
        window_of(ANCHOR, stage)
    )


@pytest.mark.parametrize(
    ("as_of_offset_days", "expected"),
    [
        (-1.0, ReviewState.UPCOMING),
        (0.0, ReviewState.UPCOMING),
        (0.5, ReviewState.UPCOMING),
        (1.0, ReviewState.DUE),
        (2.0, ReviewState.DUE),
        (4.0, ReviewState.DUE),
        (4.5, ReviewState.OVERDUE),
        (30.0, ReviewState.OVERDUE),
    ],
)
def test_the_state_is_decided_at_the_callers_as_of(
    as_of_offset_days: float, expected: ReviewState
) -> None:
    """A ``STAGE_0`` window opens one day after the anchor (``INTERVAL_DAYS``)
    and closes three days later (``GRACE_DAYS``); the offsets below walk from
    before the opening edge to well past the closing one."""

    as_of = (instant(ANCHOR) + timedelta(days=as_of_offset_days)).isoformat()
    row = plan(as_of=as_of)
    assert row.review_state is expected


def test_the_urgency_follows_the_state_it_decided() -> None:
    upcoming = plan(as_of=(instant(ANCHOR) - timedelta(days=1)).isoformat())
    due = plan(as_of=(instant(ANCHOR) + timedelta(days=2)).isoformat())
    overdue = plan(as_of=(instant(ANCHOR) + timedelta(days=10)).isoformat())
    assert upcoming.review_urgency == 0.25
    assert due.review_urgency == 0.75
    assert overdue.review_urgency == 1.0
    assert upcoming.review_state is ReviewState.UPCOMING
    assert due.review_state is ReviewState.DUE
    assert overdue.review_state is ReviewState.OVERDUE


def test_the_window_does_not_move_while_the_state_does() -> None:
    """``as_of`` decides the state only: the window is absolute, so two plans
    of one history differ in state and version but never in the window."""

    first = plan(as_of=ANCHOR)
    later = plan(as_of=(instant(ANCHOR) + timedelta(days=10)).isoformat())
    assert first.next_review_window_start == later.next_review_window_start
    assert first.next_review_window_end == later.next_review_window_end
    assert first.review_state is not later.review_state
    assert first.version != later.version


def test_the_same_inputs_plan_the_same_row() -> None:
    assert plan() == plan()


def test_a_longer_history_plans_a_different_row() -> None:
    """Different content, different stamp: the store's "a moved version
    replaces" branch is reachable and the rule is the content's."""

    quiet = plan()
    busy = plan(events=(event("re-1"), event("re-2")))
    assert quiet.version != busy.version
    assert quiet.spacing_stage is not busy.spacing_stage


def test_a_newer_anchor_plans_a_later_window() -> None:
    later_anchor = "2026-09-25T10:00:00+00:00"
    first = plan()
    moved = plan(freshness=freshness(later_anchor))
    assert instant(str(moved.next_review_window_start)) > instant(
        str(first.next_review_window_start)
    )
    assert first.version != moved.version


def test_the_planned_row_keeps_the_watermark_it_was_given() -> None:
    row = plan(source_learning_watermark="17")
    assert row.source_learning_watermark == "17"


def test_the_planned_row_leaves_the_store_clock_alone() -> None:
    assert plan().updated_at == ""


def test_the_planned_row_carries_the_key_it_was_asked_for() -> None:
    row = plan(
        schedule_item_id="si-1",
        target_type="CAPABILITY",
        evidence_modality=EvidenceModality.TEXT_COMPREHENSION,
    )
    assert row.schedule_item_id == "si-1"
    assert row.target_type == "CAPABILITY"
    assert row.evidence_modality is EvidenceModality.TEXT_COMPREHENSION


def test_the_planned_version_is_the_version_of_its_own_content() -> None:
    row = plan()
    assert row.version == row_version(
        version_content(
            target_type=row.target_type,
            target_id=row.target_id,
            evidence_modality=row.evidence_modality,
            review_state=row.review_state,
            review_urgency=float(row.review_urgency or 0.0),
            next_review_window_start=row.next_review_window_start,
            next_review_window_end=row.next_review_window_end,
            spacing_stage=row.spacing_stage,
            source_learning_watermark=row.source_learning_watermark,
        )
    )


def test_an_unschedulable_freshness_refuses_the_plan() -> None:
    planned = plan_schedule_item(
        schedule_item_id="si-1",
        target_type="RESOURCE",
        target_id=TARGET,
        evidence_modality=MODALITY,
        freshness=freshness("nope"),
        events=(),
        source_learning_watermark="1",
        as_of=ANCHOR,
    )
    assert not isinstance(planned, Ok)
    assert planned.error.code.value == "VALIDATION_FAILED"


def test_an_unschedulable_as_of_refuses_the_plan() -> None:
    planned = plan_schedule_item(
        schedule_item_id="si-1",
        target_type="RESOURCE",
        target_id=TARGET,
        evidence_modality=MODALITY,
        freshness=freshness(ANCHOR),
        events=(),
        source_learning_watermark="1",
        as_of="nope",
    )
    assert not isinstance(planned, Ok)
    assert planned.error.code.value == "VALIDATION_FAILED"


def test_an_unschedulable_as_of_is_not_reached_without_an_anchor() -> None:
    """A row with no anchor has no state to decide, so an unusable ``as_of``
    cannot matter for it — and the plan says so by succeeding."""

    planned = plan_schedule_item(
        schedule_item_id="si-1",
        target_type="RESOURCE",
        target_id=TARGET,
        evidence_modality=MODALITY,
        freshness=freshness(None),
        events=(),
        source_learning_watermark="1",
        as_of="",
    )
    assert isinstance(planned, Ok), planned
    assert planned.value.review_state is ReviewState.NOT_SCHEDULED
