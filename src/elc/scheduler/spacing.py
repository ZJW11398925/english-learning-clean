"""Scheduler spacing policy — the due/overdue decision, as pure functions.

**What this module owns.** docs/DOMAIN_MODEL.md §9 gives the Scheduler
``review_state`` / ``review_urgency`` / ``next_review_window`` /
``spacing_stage`` and makes the due decision its own end ("Learning 不能直接
输出 ``REVIEW_DUE``；Scheduler 才决定 due/overdue"); docs/IMPLEMENTATION_PLAN.md
§7 lists the inputs ("Scheduler 根据 Learning + history 决定 due", under
"Learning freshness != review_due"). This module *is* that decision, in one
place: every reading below is a function of ``(freshness, history, as_of)``
alone, so the same row can be recomputed on any machine at any later time and
answer identically.

**The rule (R3 — this repository's declaration).** The canonical documents pin
*no* spacing algorithm: they name the columns and the input authorities, and
DATA_MODEL §5.2 leaves ``spacing_stage`` a ``?`` column with no value range.
What follows is therefore an implementation-declared rule, stated once here and
pinned by test — never presented as canonical text:

1. **anchor** = the newest instant among the Learning freshness face's
   ``last_strong_retrieval_at`` (when it has one) and the row's own review
   events' ``created_at``. With no candidate at all there is nothing to space,
   so the row is ``NOT_SCHEDULED`` with **no window** and **no stage** — the
   honest reading of "never strongly retrieved, never reviewed";
2. **spacing_stage** = ``min(engaged event count, STAGE_4)`` — a pure count
   over the row's own history (§5.2's ``engaged`` is the typed column). It is
   derived on every recomputation from the durable events themselves, so no
   hidden cursor, no stored counter and no migration are involved: the ladder
   position is replayable from the append-first history alone;
3. **window**: ``next_review_window_start = anchor + INTERVAL_DAYS[stage]`` and
   ``next_review_window_end = start + GRACE_DAYS``;
4. **state**, at the caller's ``as_of`` (a *parameter* — this module reads no
   clock): ``as_of < start`` ⇒ ``UPCOMING``; ``start <= as_of <= end`` ⇒
   ``DUE`` (both edges inclusive); ``as_of > end`` ⇒ ``OVERDUE``.

**Implementation-declared constants (calibratable, not canonical).**
:data:`SCHEDULER_MODEL_VERSION` (``"sd1"``) is the model stamp that prefixes
every row version, :data:`INTERVAL_DAYS` is the expand-spacing ladder
(1 / 3 / 7 / 16 / 35 days for ``STAGE_0`` … ``STAGE_4``) and
:data:`GRACE_DAYS` (3) is the width of the ``DUE`` band. IP §7 asks for
"spacing history" and names no numbers; BF-02's Planner reference profile pins
numbers for the *Planner's* factor bands, not for a review ladder.
**Revisit condition**: calibration is the Phase 11 content-calibration face's
(IP §7 / §13; the same face that owns the corpus's pedagogical profiles), and a
calibration cut replaces :data:`INTERVAL_DAYS` / :data:`GRACE_DAYS` **with a new
:data:`SCHEDULER_MODEL_VERSION`** — the constants and the stamp move together,
because a row version that kept its stamp across a changed ladder would claim
two different windows are the same projection (§1.4's version discipline).

**What this module deliberately does not consume.** The Learning freshness face
also carries ``freshness_band``, ``days_since_strong_retrieval`` and
``stability_band`` (elc.learning.types.FreshnessView); none of the three enters
the decision:

- ``freshness_band`` / ``days_since_strong_retrieval`` are computed by the
  Learning **read clock** (``datetime.now`` inside
  ``SqliteLearningStore.get_freshness``), so relative to a caller's ``as_of``
  they are not a function of the durable rows — consuming them would make the
  same ``(freshness, history, as_of)`` answer differently on two machines or on
  two days, which is exactly the determinism this module exists to keep;
- ``stability_band`` is a real §23 signal, but modulating the ladder with it is
  a calibration question (above), not a reading this cut may invent. It stays
  recorded and unused — the way §9's "stability evidence" input is *available*
  without being interpreted here.

**Time is an instant here, not a byte order.** The timestamps this module reads
(``last_strong_retrieval_at`` / ``created_at`` / ``as_of``) are ISO-8601
strings, and they are parsed with ``datetime.fromisoformat`` and compared **as
instants** (the window is a real time window). This is the deliberate opposite
of the byte-order rule p6-1 pinned for ``created_at``'s immutable replay: that
rule answers "is this the same durable fact?", which must be a byte comparison
because two spellings of one instant are two different stored strings; here the
question is "has the moment arrived?", where only the instant can answer. A
naive timestamp (no UTC offset) is refused rather than assumed to be UTC: the
policy has no authority to pick a zone for a caller.

**Zero SQL, zero clock, zero I/O.** This module imports no database handle, no
``datetime.now``, no file and no network: it opens no connection, reads no
clock, and writes nothing. Every input arrives as an argument, so the decision
is testable without a store and reproducible without a world.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence, TypeVar

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    EvidenceModality,
    Ok,
    Result,
    ScheduleVersion,
    TargetId,
)
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    SpacingStage,
)

__all__ = [
    "GRACE_DAYS",
    "INTERVAL_DAYS",
    "SCHEDULER_MODEL_VERSION",
    "SPACING_STAGES",
    "URGENCY_ANCHORS",
    "FreshnessPort",
    "LearningReadPort",
    "ReviewEventRole",
    "anchor_of",
    "next_window",
    "parse_instant",
    "plan_schedule_item",
    "role_of",
    "row_version",
    "stage_from_history",
    "state_at",
    "urgency_of",
]

#: The model stamp every row version carries (R7): a version says *which
#: policy* produced a row as well as *what the row says*, so a calibration cut
#: changes the stamp and old rows stay readable as old rows.
SCHEDULER_MODEL_VERSION = "sd1"

#: The ladder in order, ``STAGE_0`` (one engaged event) … ``STAGE_4`` (the
#: top). :class:`elc.scheduler.types.SpacingStage` declares the words and
#: migration 0012 puts no CHECK on the column; this tuple is the *order* the
#: stage count clamps into, and it exists so the clamp has one spelling.
#: Revisit: the same cut that recalibrates :data:`INTERVAL_DAYS`.
SPACING_STAGES: tuple[SpacingStage, ...] = (
    SpacingStage.STAGE_0,
    SpacingStage.STAGE_1,
    SpacingStage.STAGE_2,
    SpacingStage.STAGE_3,
    SpacingStage.STAGE_4,
)

#: The expand-spacing ladder, in days from the anchor (R3 ③). Implementation
#: declared and calibratable — see the module docstring's revisit condition.
INTERVAL_DAYS: Mapping[SpacingStage, int] = {
    SpacingStage.STAGE_0: 1,
    SpacingStage.STAGE_1: 3,
    SpacingStage.STAGE_2: 7,
    SpacingStage.STAGE_3: 16,
    SpacingStage.STAGE_4: 35,
}

#: The width of the ``DUE`` band: a window that has opened stays ``DUE`` for
#: this many days before it becomes ``OVERDUE`` (R3 ③).
GRACE_DAYS = 3

#: The state → number anchors (R4), taken from BF-02 v1.1's reference profile
#: ``reference_factor_bands.schedule_urgency`` (NOT_SCHEDULED 0.0 / UPCOMING
#: 0.25 / DUE 0.75 / OVERDUE 1.0) — **not** by hand: the pin in
#: tests/phase6 extracts that graph from
#: ``behavioral_baselines/planner/planner_reference_profile_v1_1.json`` and
#: compares it with this table and with :func:`urgency_of`'s answers, so a
#: transcription slip fails a test rather than shipping.
#:
#: Reading the anchors is *not* BF-02 §6's feature assembly: the Planner's
#: benefit factor (Phase 7) multiplies a weight with this number inside a
#: PlanningContext, and BF-02 §5's "missing Scheduler ⇒ schedule_urgency = 0"
#: degradation path stays a Phase 7 behaviour this module does not implement.
#: What lands here is the state's own anchor value, so a row the Scheduler
#: wrote carries a number rather than an uninterpreted ``None``.
URGENCY_ANCHORS: Mapping[ReviewState, float] = {
    ReviewState.NOT_SCHEDULED: 0.0,
    ReviewState.UPCOMING: 0.25,
    ReviewState.DUE: 0.75,
    ReviewState.OVERDUE: 1.0,
}

#: How many hex characters of the content digest the row version carries
#: (R7): twelve is what an implementation version stamp needs here — the stamp
#: is compared for equality inside one row's history, never for order.
_VERSION_DIGEST_CHARS = 12

#: How the version payload spells an **absent** optional column. NUL cannot
#: appear in any of the values that reach the payload (ISO-8601 instants, §5.2
#: vocabulary words, watermark digits), so "absent" and "present but empty" can
#: never hash to the same stamp — the encoding the repo's ``_ABSENT_FIELD``
#: precedent uses for the same reason.
_ABSENT_FIELD = "\x00"


class FreshnessPort(Protocol):
    """The **one** Learning field the due decision reads (D-INV-009).

    The scheduler package imports no other domain (its own invariant, pinned by
    test): DOMAIN_MODEL §9's read input arrives through this narrow structural
    port, which ``elc.learning.types.FreshnessView`` satisfies as it stands —
    the same field name, the same ``str | None`` type, no adapter and no copied
    record. The other three ``FreshnessView`` fields are deliberately *not*
    declared here: a port that named them would invite a reader to consume
    them, and the module docstring says why none of them may enter the
    decision.
    """

    last_strong_retrieval_at: str | None


class LearningReadPort(Protocol):
    """The two Learning reads the due decision consumes (DOMAIN_MODEL §9
    "Reads"), as ``Result``s.

    Satisfied **structurally** by ``elc.learning.controller.
    LearningController`` as it stands — the scheduler package imports no other
    domain (its own invariant, pinned by test), so the port is the seam rather
    than an import. It is deliberately two methods wide: a caller wiring the
    Scheduler hands over the authority face, and the decision reaches nothing
    else on the Learning side.

    ``get_freshness`` is annotated ``Result[Any]`` and **not**
    ``Result[FreshnessPort]`` for a mechanical reason worth writing down:
    ``Ok`` is an *invariant* generic, so ``Result[FreshnessView]`` is not
    assignable to ``Result[FreshnessPort]`` under a static checker even though
    ``FreshnessView`` satisfies ``FreshnessPort`` field for field. Naming the
    concrete protocol there would make the real Learning controller
    unwireable. The structure is not lost by moving it: it is enforced where
    the value is *used* — :func:`anchor_of` takes a :class:`FreshnessPort`, so
    the only freshness field any code here can read is the one that port
    names (and the module docstring says why the other three must stay
    unread).
    """

    def get_freshness(self, target_id: TargetId) -> Result[Any]:
        """One target's freshness across its modality projections."""
        ...

    def get_learning_watermark(self) -> Result[int]:
        """The current Learning evidence watermark (a sequence number)."""
        ...


T = TypeVar("T")


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _encoded_optional(value: str | None) -> str:
    """One optional column of the version payload, with absence spelled.

    ``None`` becomes :data:`_ABSENT_FIELD` and a present value travels as
    itself, so the two cannot collide (see :func:`version_content`).
    """

    return _ABSENT_FIELD if value is None else value


def parse_instant(text: str, *, field: str) -> Result[datetime]:
    """One ISO-8601 timestamp of this domain's inputs, as an instant.

    ``field`` names the column in the message so a refusal says which input
    was unusable. The three refusals are ``VALIDATION_FAILED`` and are worded
    here — an exception's own text never travels (the store's one-vocabulary
    rule):

    - empty: an instant that was never written cannot be compared;
    - unparseable: not ISO-8601 in any spelling ``datetime`` accepts;
    - **naive**: no UTC offset. The policy will not assume a zone for a caller
      (module docstring: the same "no invented reading" rule the rest of this
      cut follows).

    Revisit: canonical text pins a timestamp form (or a default zone) for the
    window columns §5.2 declares TEXT, or another domain's instant reading
    appears that this one must agree with — the three refusals above are this
    cut's reading of a column canonical leaves open, and
    ``elc.user_config.store``'s ``_parse_instant`` restates it.
    """

    if not text:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} is empty; an instant must be an ISO-8601 timestamp"
            " carrying a UTC offset",
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} {text!r} is not an ISO-8601 timestamp",
        )
    if parsed.tzinfo is None:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{field} {text!r} carries no UTC offset; this policy will not"
            " assume a zone (write the offset, e.g. +00:00)",
        )
    return Ok(parsed)


def stage_from_history(events: Sequence[ReviewEvent]) -> SpacingStage:
    """The ladder position of one row's history (R3 ②).

    ``min(engaged events, STAGE_4)``: a pure count of the events whose
    ``engaged`` column is true, clamped to the top of the ladder. A silent
    (``engaged=False``) event records a review that did not engage the target
    and therefore does not advance the ladder — but it is still history, and
    its ``created_at`` still anchors the window
    (:func:`anchor_of` counts *all* events for the anchor, because "when did
    we last touch this row" is not a question about engagement).
    """

    engaged = sum(1 for event in events if event.engaged)
    return SPACING_STAGES[min(engaged, len(SPACING_STAGES) - 1)]


class ReviewEventRole(StrEnum):
    """What one :class:`~elc.scheduler.types.ReviewEvent` does to a row.

    **The P7-0 freeze table.** Two §5.2 columns decide everything this ladder
    reads about an event — ``engaged`` and ``created_at`` — and every
    combination of them is one of four roles:

    ==========  ==============  =====================  ========  =======
    ``engaged`` ``created_at``  role                   anchors   advances
    ==========  ==============  =====================  ========  =======
    True        non-empty       ANCHOR_AND_ADVANCE     yes       yes
    False       non-empty       ANCHOR_ONLY            yes       no
    True        empty           ADVANCE_ONLY           no        yes
    False       empty           HISTORY_ONLY           no        no
    ==========  ==============  =====================  ========  =======

    Read the rows as the two answers
    :func:`~elc.scheduler.spacing.anchor_of` and
    :func:`~elc.scheduler.spacing.stage_from_history` give:

    - **anchors** — the event's ``created_at`` is a candidate for "when did we
      last touch this row" (the newest candidate wins). Engagement is *not*
      asked: a review that did not engage still happened, and the window a
      silent review opens is the same window (``anchor_of``'s own docstring);
    - **advances** — the event counts toward the ladder position (``+1``, the
      count clamped to the top). A silent event does **not** advance: the
      ladder is a count of *engaged* reviews;
    - **empty ``created_at``** is not a value but an unwritten timestamp: the
      store stamps that column on the way in (0007's ``created_at or _now()``
      precedent), so an empty one is a row that has not reached the database.
      It anchors nothing (``anchor_of`` skips it) while it still counts if it
      is engaged — which is why ``ADVANCE_ONLY`` exists as a shape rather
      than being folded into another row: the pure policy is reachable with
      hand-built event lists, and this table has to say what it does with
      one.

    **A failed review has no column of its own.** §5.2 gives the event no
    outcome column and pins no vocabulary for ``event_type``, so nothing here
    branches on that string — a producer that wants to record "the review
    happened and did not engage" says ``engaged=False`` (the ``ANCHOR_ONLY``
    row above), and there is no other way to say it. This is the frozen
    reading the next cut must build on, and it is frozen *here*, in the
    ladder's own module: **the first ReviewEvent producer (the review-outcome
    flow) must cite this table before it writes an event** — the words it puts
    in ``event_type`` will not be read back, and the two columns it *must* get
    right are the two this table keys on.

    **The four role words are this cut's declaration** (no canonical block
    names them): what is canonical is the pair of columns they are derived
    from, plus the two answers :func:`anchor_of` and
    :func:`stage_from_history` give. A cut that changes what an event does
    changes this table with it.

    **A failed review's window, referred rather than decided (P9-0).** The
    ``ANCHOR_ONLY`` row above has a consequence worth stating where the row
    is: a review that happened and did **not** engage still anchors, so it
    opens a fresh window and the next due date moves one full spacing
    interval further out — a failure earns the same delay an engagement
    does, and repeated failures never shorten the loop. The alternative
    reading (a failure anchors nothing, so the row stays as due as it was
    and the flow can retry sooner) is equally faithful to §5.2, which gives
    the event no outcome column to decide it with. **This cut changes
    nothing** — the freeze table and every assertion about it stand — and
    refers the question: the trigger is the first real ReviewEvent producer
    (the review-outcome flow, whose writer contract
    :mod:`elc.scheduler.review_record` declares), and changing the reading
    must go through a version entry in ``docs/DECISION_REGISTER.md``, the
    same route this docstring's last sentence implies. ``review_record``'s
    own docstring holds the two arms' full consequence analysis.
    """

    ANCHOR_AND_ADVANCE = "ANCHOR_AND_ADVANCE"
    ANCHOR_ONLY = "ANCHOR_ONLY"
    ADVANCE_ONLY = "ADVANCE_ONLY"
    HISTORY_ONLY = "HISTORY_ONLY"


def role_of(event: ReviewEvent) -> ReviewEventRole:
    """One event's role in the ladder (the freeze table on :class:`ReviewEventRole`).

    Derived from the same two fields :func:`anchor_of` and
    :func:`stage_from_history` read, in the same reading, so the table cannot
    drift from the policy it describes: a change to either function that
    changed what an event does would have to change this function too (the
    phase-7 pin drives one event of each role through all three).
    """

    if event.engaged:
        return (
            ReviewEventRole.ANCHOR_AND_ADVANCE
            if event.created_at
            else ReviewEventRole.ADVANCE_ONLY
        )
    return (
        ReviewEventRole.ANCHOR_ONLY
        if event.created_at
        else ReviewEventRole.HISTORY_ONLY
    )


def _newest_instant(
    candidates: Sequence[tuple[str, str]],
) -> Result[tuple[str, datetime] | None]:
    """The newest ``(raw, instant)`` pair, or ``None`` for no candidate.

    Every candidate is parsed (so an unusable one refuses the whole
    computation instead of being silently skipped) and the winner is the
    newest instant, tie-broken by the raw string — the tie-break only has to be
    deterministic, because two candidates that name the same instant are the
    same moment whatever the caller wrote.
    """

    best: tuple[str, datetime] | None = None
    for raw, field in candidates:
        parsed = parse_instant(raw, field=field)
        if isinstance(parsed, Err):
            return parsed
        if best is None or (parsed.value, raw) > (best[1], best[0]):
            best = (raw, parsed.value)
    return Ok(best)


def anchor_of(
    freshness: FreshnessPort, events: Sequence[ReviewEvent]
) -> Result[str | None]:
    """The anchor of one row (R3 ①): the newest strong retrieval or review.

    Two sources, one answer: the Learning freshness face's
    ``last_strong_retrieval_at`` when it has one, and every review event's
    ``created_at``. An event whose ``created_at`` is empty is skipped — the
    store stamps that column on the way in (0007's precedent), so an empty one
    is a row that has not been written yet and names no moment; skipping it is
    not a wildcard, because an event that never reached the database cannot be
    part of history.

    ``Ok(None)`` means *no anchor at all*: no strong retrieval and no review
    has ever happened. That is the ``NOT_SCHEDULED`` case, and it is a normal
    answer, not a failure. The raw string of the winner is returned rather than
    the parsed instant, so the emitted window keeps the caller's own offset
    spelling (see :func:`next_window`).
    """

    candidates: list[tuple[str, str]] = []
    strong = freshness.last_strong_retrieval_at
    if strong is not None and strong != "":
        candidates.append((strong, "last_strong_retrieval_at"))
    candidates.extend(
        (event.created_at, f"review_event {event.review_event_id} created_at")
        for event in events
        if event.created_at
    )
    newest = _newest_instant(candidates)
    if isinstance(newest, Err):
        return newest
    return Ok(None if newest.value is None else newest.value[0])


def next_window(anchor: str, stage: SpacingStage) -> Result[tuple[str, str]]:
    """The window an anchor and a stage imply (R3 ③), as ``(start, end)``.

    Both ends are ISO-8601 and carry the **anchor's own offset**: the
    arithmetic adds days to the parsed instant, so no conversion happens and a
    ``+08:00`` anchor yields ``+08:00`` bounds. (An anchor spelled with a ``Z``
    suffix comes back spelled ``+00:00`` — the same offset, in the spelling
    ``datetime.isoformat`` emits. That is a *spelling* difference, not the
    byte-order question p6-1's F-3 raised: nothing here compares strings.)

    An unusable anchor is ``VALIDATION_FAILED`` (see :func:`parse_instant`).
    """

    parsed = parse_instant(anchor, field="next_review_window anchor")
    if isinstance(parsed, Err):
        return parsed
    start = parsed.value + timedelta(days=INTERVAL_DAYS[stage])
    end = start + timedelta(days=GRACE_DAYS)
    return Ok((start.isoformat(), end.isoformat()))


def state_at(
    as_of: str, window_start: str, window_end: str
) -> Result[ReviewState]:
    """The review state of a windowed row at ``as_of`` (R3 ④).

    Boundaries are inclusive on both ends: ``as_of == window_start`` is the
    instant the window *opens* and ``as_of == window_end`` the instant it
    closes, so both are ``DUE`` — a comparison with strict inequality on either
    side would answer ``UPCOMING`` or ``OVERDUE`` for a moment the row's own
    window covers.

    This is the **single** state computation: :meth:`SchedulerQueries.
    is_review_due` reads the durable row's window through this same function,
    so a "is it due" answer and the state recomputation can never disagree.
    """

    start = parse_instant(window_start, field="next_review_window_start")
    if isinstance(start, Err):
        return start
    end = parse_instant(window_end, field="next_review_window_end")
    if isinstance(end, Err):
        return end
    now = parse_instant(as_of, field="as_of")
    if isinstance(now, Err):
        return now
    if now.value < start.value:
        return Ok(ReviewState.UPCOMING)
    if now.value > end.value:
        return Ok(ReviewState.OVERDUE)
    return Ok(ReviewState.DUE)


def urgency_of(state: ReviewState) -> float:
    """The state's anchor value (R4) — :data:`URGENCY_ANCHORS`, nothing else.

    No sub-state interpolation, no elapsed-time scaling, no band arithmetic: a
    caller that wants a curve is assembling a Planner feature (Phase 7), and
    the Scheduler's column carries the anchor. ``NOT_SCHEDULED`` has an anchor
    too (0.0), because a row the Scheduler wrote is never "missing Scheduler" —
    BF-02 §5's degradation is about a Planner holding no schedule authority at
    all, which is a different situation from a target with no review
    obligation yet.
    """

    return URGENCY_ANCHORS[state]


def version_content(
    *,
    target_type: str,
    target_id: TargetId,
    evidence_modality: EvidenceModality,
    review_state: ReviewState,
    review_urgency: float,
    next_review_window_start: str | None,
    next_review_window_end: str | None,
    spacing_stage: SpacingStage | None,
    source_learning_watermark: str,
) -> dict[str, str]:
    """The computed columns of one row, as the version payload (R7).

    Every §5.2 column the durable writer compares for the "same content"
    question is here, encoded as a string, and the two that are *not* content
    are absent: ``updated_at`` is the store's clock, and ``version`` is what
    this payload derives. ``schedule_item_id`` is absent too — it is the row's
    identity, derived from the modality key that is already in the payload, so
    including a minted id would make the stamp depend on an id convention
    rather than on what the row says.

    The three ``?`` columns go through :func:`_encoded_optional`, which gives
    *absent* a spelling of its own rather than the empty string: a window
    column holding ``""`` and one holding nothing are two different durable
    values (§5.2's ``?`` is not "empty"), and a payload that folded them
    together would let one content be hashed as another — exactly the
    false-replay/false-conflict pair R7 exists to prevent.
    """

    return {
        "target_type": target_type,
        "target_id": str(target_id),
        "evidence_modality": evidence_modality.value,
        "review_state": review_state.value,
        "review_urgency": str(float(review_urgency)),
        "next_review_window_start": _encoded_optional(
            next_review_window_start
        ),
        "next_review_window_end": _encoded_optional(next_review_window_end),
        "spacing_stage": _encoded_optional(
            None if spacing_stage is None else spacing_stage.value
        ),
        "source_learning_watermark": source_learning_watermark,
    }


def row_version(content: Mapping[str, str]) -> ScheduleVersion:
    """The content-addressed row version (R7).

    ``"{SCHEDULER_MODEL_VERSION}-{sha256(canonical json)[:12]}"``, where the
    canonical JSON is
    ``json.dumps(dict(content), sort_keys=True, separators=(",", ":"),
    ensure_ascii=False)`` — so the stamp is a function of the row's content and
    of nothing else (no clock, no call order, no id).

    **Why content-addressed rather than time-addressed.** The store's discipline
    is "the same version with different content is refused" (§1.4): a stamp
    that said only *when* the row was computed would refuse a row whose history
    moved between two recomputations at one instant, and would rewrite a row
    whose content did not move at all. Addressing the content makes both halves
    true at once — identical content replays with zero writes, different
    content is a different version and replaces — and hands determinism for
    free: the same ``(freshness, history, as_of)`` yields the same version.
    """

    canonical = json.dumps(
        dict(content),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ScheduleVersion(
        f"{SCHEDULER_MODEL_VERSION}-{digest[:_VERSION_DIGEST_CHARS]}"
    )


def plan_schedule_item(
    *,
    schedule_item_id: str,
    target_type: str,
    target_id: TargetId,
    evidence_modality: EvidenceModality,
    freshness: FreshnessPort,
    events: Sequence[ReviewEvent],
    source_learning_watermark: str,
    as_of: str,
) -> Result[ScheduleItem]:
    """The whole §5.2 row for one modality key — the decision in one call.

    The four steps of the module docstring, composed: anchor ⇒ stage ⇒ window
    ⇒ state, then the version stamp (:func:`row_version`) and the urgency
    anchor (:func:`urgency_of`). ``as_of`` decides the *state* only; the
    window is absolute, so a row planned today and re-planned next week with
    the same history and the same ``as_of`` is byte-identical, and re-planned
    with a later ``as_of`` differs only where the state (and therefore the
    version) legitimately moved.

    A row with **no anchor** is still produced: ``NOT_SCHEDULED``, both window
    columns ``None``, ``spacing_stage`` ``None``, ``review_urgency`` 0.0. The
    Scheduler schedules the target — "this target exists and has no review
    obligation yet" is a fact the Planner needs to see (and BF-02 §5's
    degradation is about a Planner with *no* Scheduler authority, not about a
    target with no review obligation).

    ``updated_at`` is left empty on purpose: the durable writer stamps it, and
    a value computed here would be a second clock.
    """

    anchor = anchor_of(freshness, events)
    if isinstance(anchor, Err):
        return anchor
    stage = stage_from_history(events)
    window: tuple[str, str] | None = None
    if anchor.value is None:
        state = ReviewState.NOT_SCHEDULED
        stage_for_row: SpacingStage | None = None
    else:
        windowed = next_window(anchor.value, stage)
        if isinstance(windowed, Err):
            return windowed
        window = windowed.value
        checked = state_at(as_of, window[0], window[1])
        if isinstance(checked, Err):
            return checked
        state = checked.value
        stage_for_row = stage
    version = row_version(
        version_content(
            target_type=target_type,
            target_id=target_id,
            evidence_modality=evidence_modality,
            review_state=state,
            review_urgency=urgency_of(state),
            next_review_window_start=None if window is None else window[0],
            next_review_window_end=None if window is None else window[1],
            spacing_stage=stage_for_row,
            source_learning_watermark=source_learning_watermark,
        )
    )
    return Ok(
        ScheduleItem(
            schedule_item_id=schedule_item_id,
            target_type=target_type,
            target_id=target_id,
            evidence_modality=evidence_modality,
            review_state=state,
            review_urgency=urgency_of(state),
            next_review_window_start=None if window is None else window[0],
            next_review_window_end=None if window is None else window[1],
            spacing_stage=stage_for_row,
            source_learning_watermark=source_learning_watermark,
            version=version,
        )
    )
