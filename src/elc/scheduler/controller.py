"""Scheduler Domain Controller — the review-truth authority face (Phase 6
P6-1 graduation; TASK-OPI-6259f6fd-….12 ②④) and the due decision's home
(P6-2; TASK-OPI-5a0be06d-….6 ②).

The durable rows and every SQL statement live in :mod:`elc.scheduler.store`,
the pure policy lives in :mod:`elc.scheduler.spacing`, and this face is the
composition of the two: it reads, it asks the policy, it commits. It holds no
rule of its own and touches no table — the version discipline (a moved version
replaces; the same version with different content is refused) and the
append-first identity rule of :class:`elc.scheduler.types.ReviewEvent` are the
store's, stated once there. What this module owns is **the decision's shape**:
which inputs a recomputation reads, in which order, and that the same inputs
always answer the same way.

**DOMAIN_MODEL §9 is this face's charter** ("Learning 不能直接输出
``REVIEW_DUE``；Scheduler 才决定 due/overdue" — D-INV-009, spelled out in
docs/DOMAIN_MODEL.md §9): the due decision exists here and nowhere else, so no
Learning module emits a due flag and the Planner (§10) only ever *consumes* a
:class:`ScheduleView`.

**The one collaborator that cannot be imported.** The decision reads Learning
freshness and the Learning evidence watermark (DOMAIN_MODEL §9 "Reads";
DATA_MODEL §5.2's ``source_learning_watermark``), and this package imports no
other domain — so those two reads arrive through
:class:`LearningReadPort`, a narrow structural port the caller passes to the
constructor. Nothing else about Learning is reachable from here: the port
declares two methods, and the policy behind it reads exactly one field of one
of them (see :mod:`elc.scheduler.spacing`).

**Gone, not renamed** (all three were Phase 0 shapes written before §5.2
existed as a specification):

- ``record_review_outcome(target_id, retrieved, at)`` — the canonical column
  vocabulary is ``engaged`` / ``event_type`` (§5.2), and there is no
  ``retrieved`` word anywhere in the canonical set. Its successor is
  :meth:`record_review_event`;
- ``suspend_review(target_id, reason)`` — §5.2's ``review_state`` has four
  words and ``SUSPENDED`` is not one of them, and no column carries a
  ``reason``. A state the canonical vocabulary does not contain cannot be set
  by this face, so the method is deleted rather than re-pointed;
- ``get_review_state(target_id)`` — the skeleton's ``ReviewStateRecord`` is
  replaced by ``ScheduleItem``, whose key is the modality key, so the read is
  :meth:`get_schedule_item` (by target type, target, evidence modality)
  instead of a target-only lookup.

**Gone with the phase pointer.** P6-1 kept ``get_schedule_view`` and
``is_review_due`` declared and raising a P6-2 pointer; P6-2 implements both, so
that constant and every reference to it are deleted rather than left as a
stale marker (the teaching/user_config graduation precedent: a face whose
phase has arrived stops pointing at it).

Failure semantics: every implemented face returns a ``Result``; the only thing
that raises into a caller is a stale-epoch store (a programming error, the
repo-wide fence convention).
"""

from __future__ import annotations

import hashlib
from typing import Sequence

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
from elc.scheduler.authority import ScheduleCurrency, currency_of
from elc.scheduler.spacing import (
    SCHEDULER_MODEL_VERSION,
    LearningReadPort,
    plan_schedule_item,
    state_at,
)
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    ScheduleView,
)

__all__ = ["ScheduleCurrency", "SchedulerController", "schedule_item_id_for"]

#: The field separator the repo's derived-id convention uses (P4-1's
#: ``memory_id_for``, P4-2's ``projection_id_for``): ASCII 0x1f, chosen so it
#: can never appear inside a machine-minted id.
_ID_FIELD_SEPARATOR = "\x1f"

#: ``si-`` + 20 hex characters: the digest is long enough that a collision
#: between two modality keys is not a practical concern, and the prefix says
#: which object family the id belongs to.
_ID_PREFIX = "si-"
_ID_DIGEST_CHARS = 20


def schedule_item_id_for(
    target_type: str,
    target_id: TargetId,
    evidence_modality: EvidenceModality,
) -> str:
    """The deterministic id of one modality key's current row.

    Derived, never minted (the repo-wide stable-id convention, DATA_MODEL
    §1.2): the encoding is
    ``si-{sha256(target_type + US + target_id + US + evidence_modality)[:20]}``,
    so a recomputation that finds no durable row still addresses the same id a
    later recomputation of the same key will use — two calls cannot create two
    current rows for one key. US is :data:`_ID_FIELD_SEPARATOR`.

    The id is also what ``review_event.schedule_item_id`` is read by, which is
    why deriving it (rather than minting it with a counter or a clock) keeps a
    first recomputation and its retry on one history: events appended under
    the derived id are the events a later recomputation reads.
    """

    digest = hashlib.sha256(
        _ID_FIELD_SEPARATOR.join(
            (target_type, str(target_id), evidence_modality.value)
        ).encode("utf-8")
    ).hexdigest()
    return f"{_ID_PREFIX}{digest[:_ID_DIGEST_CHARS]}"


class SchedulerController:
    """Owns review truth over :class:`SqliteSchedulerStore`, and the due
    decision over the pure policy.

    Two collaborators, and the second is optional only because a world with no
    Learning face cannot recompute anything (the durable §5.2 writes and reads
    need no Learning): the store carries the connection, the epoch fence and
    every statement, and ``learning`` is the narrow read face DOMAIN_MODEL §9
    names as the decision's input. A controller constructed without it answers
    every durable face and refuses :meth:`recompute_schedule_item` with
    ``DEPENDENCY_UNAVAILABLE`` instead of inventing a freshness reading.
    """

    def __init__(
        self,
        store: SqliteSchedulerStore,
        *,
        learning: LearningReadPort | None = None,
    ) -> None:
        self._store = store
        self._learning = learning

    # -- the write faces (§5.2) --------------------------------------------

    def recompute_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        as_of: str,
    ) -> Result[ScheduleItem]:
        """Recompute and commit the current row for one modality key.

        The three inputs the decision needs, in this order:

        1. **Learning freshness** — ``last_strong_retrieval_at``, the one
           freshness field the policy reads (the port is structural precisely
           so the other three fields cannot be reached);
        2. **the Learning evidence watermark** — stored on the row as
           ``str(watermark)`` (R6), so a consumer can tell a stale row from a
           current one;
        3. **this row's own review history** — every event under the row's id,
           read in the store's durable order, from which the anchor and the
           ladder position are derived.

        Then the pure policy runs (:func:`elc.scheduler.spacing.
        plan_schedule_item`) and its row is committed. Nothing is computed
        twice: the row that comes back is the store's durable row, stamped by
        the store's clock, and an identical recomputation writes nothing at all
        (the content-addressed version replays).

        A row is written **even with no anchor**: ``NOT_SCHEDULED``, both
        window columns ``None``, ``spacing_stage`` ``None``,
        ``review_urgency`` 0.0. "This target has no review obligation yet" is a
        fact the Planner needs, and refusing to write it would leave the
        Planner unable to distinguish "no review debt" from "the Scheduler was
        never asked" — the distinction BF-02 §5's degradation rule depends on.

        An unusable timestamp (unparseable, or naive) is the policy's
        ``VALIDATION_FAILED`` and nothing is written: a row never carries a
        window this face could not verify.
        """

        if self._learning is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "recompute_schedule_item needs the Learning freshness"
                        " / watermark read face (DOMAIN_MODEL §9 Reads): this"
                        " controller was constructed without one, and the"
                        " Scheduler will not invent a freshness reading"
                    ),
                )
            )
        freshness = self._learning.get_freshness(target_id)
        if isinstance(freshness, Err):
            return freshness
        watermark = self._learning.get_learning_watermark()
        if isinstance(watermark, Err):
            return watermark
        current = self._store.get_schedule_item(
            target_type, target_id, evidence_modality
        )
        if isinstance(current, Err):
            return current
        item_id = (
            schedule_item_id_for(target_type, target_id, evidence_modality)
            if current.value is None
            else current.value.schedule_item_id
        )
        events = self._store.list_review_events(item_id)
        if isinstance(events, Err):
            return events
        planned = plan_schedule_item(
            schedule_item_id=item_id,
            target_type=target_type,
            target_id=target_id,
            evidence_modality=evidence_modality,
            freshness=freshness.value,
            events=events.value,
            source_learning_watermark=str(watermark.value),
            as_of=as_of,
        )
        if isinstance(planned, Err):
            return planned
        return self._store.upsert_schedule_item(planned.value)

    def upsert_schedule_item(self, item: ScheduleItem) -> Result[ScheduleItem]:
        """Commit one schedule row as given (§5.2).

        The durable row comes back — stamped with this store's clock, and
        identical to what :meth:`get_schedule_item` reads. The four rules of
        the write (replay / a moved version replaces / the same version with
        different content refuses / the modality key is unique) are the
        store's, stated once in :mod:`elc.scheduler.store`.

        No gate here: a schedule row is the Scheduler's own projection, not
        personal content, and no consent-style gate belongs on it. Nothing
        about ``review_state`` is computed either — this face stores a row a
        caller computed. A caller who wants the *decision* asks
        :meth:`recompute_schedule_item`; a caller who has already decided (a
        migration, a repair, a test) writes here.
        """

        return self._store.upsert_schedule_item(item)

    def record_review_event(self, event: ReviewEvent) -> Result[ReviewEvent]:
        """Append one review event (§5.2, §1.3).

        The successor of the Phase 0 ``record_review_outcome``: the canonical
        vocabulary is ``engaged`` / ``event_type`` (§5.2), so a caller states
        what happened rather than the skeleton's ``retrieved`` boolean. The
        event is a fact — the same id with different content is refused, never
        rewritten — and its ``created_at`` is the caller's when declared and
        the store's clock otherwise.
        """

        return self._store.record_review_event(event)

    # -- the read faces (§5.2) ----------------------------------------------

    def get_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[ScheduleItem | None]:
        """The current row for one modality key (``None`` = never written).

        Keyed by the §5.2 key — ``(target_type, target_id,
        evidence_modality)`` — rather than by ``schedule_item_id``. §5.2 pins
        no owner column, so the modality key is also what makes a row
        addressable by target (the modality leg is the same one the learning
        projection keys on), which is what a deletion by target needs.
        """

        return self._store.get_schedule_item(
            target_type, target_id, evidence_modality
        )

    def list_review_events(
        self, schedule_item_id: str
    ) -> Result[tuple[ReviewEvent, ...]]:
        """One schedule row's history, in the deterministic durable order
        ``(created_at, review_event_id)`` — append-first, because §5.2 lands
        no unique index on ``schedule_item_id`` and several events for one row
        over time are the history."""

        return self._store.list_review_events(schedule_item_id)

    # -- the due decision (§9 / D-INV-009) ----------------------------------

    def get_schedule_view(self, as_of: str) -> Result[ScheduleView]:
        """The Planner's input view (docs/DOMAIN_MODEL.md §10) at ``as_of``.

        Every current §5.2 row is classified by :func:`elc.scheduler.spacing.
        state_at` — the same function a recomputation uses, so a view and the
        rows it holds can never disagree — and lands in the bucket its state
        names. ``NOT_SCHEDULED`` rows land in **no** bucket (see
        :class:`ScheduleView`): no review obligation is not an obligation, and
        a bucket filled with unscheduled targets would hand the Planner a
        review debt the Scheduler never declared.

        ``as_of`` is an argument rather than a clock read for the same reason
        the policy takes it: a view is reproducible, so two consumers asking
        about the same instant see the same picture and a test can pin it.
        A row whose window cannot be parsed refuses the whole view
        (``VALIDATION_FAILED``) instead of being silently dropped — a view that
        hides a row would understate the Planner's input.
        """

        rows = self._store.list_schedule_items()
        if isinstance(rows, Err):
            return rows
        buckets: dict[ReviewState, list[ScheduleItem]] = {
            ReviewState.DUE: [],
            ReviewState.OVERDUE: [],
            ReviewState.UPCOMING: [],
        }
        for row in rows.value:
            window_start = row.next_review_window_start
            window_end = row.next_review_window_end
            if window_start is None or window_end is None:
                continue
            state = state_at(as_of, window_start, window_end)
            if isinstance(state, Err):
                return state
            bucket = buckets.get(state.value)
            if bucket is not None:
                bucket.append(row)
        return Ok(
            ScheduleView(
                schedule_version=ScheduleVersion(SCHEDULER_MODEL_VERSION),
                as_of=as_of,
                due_items=_in_window_order(buckets[ReviewState.DUE]),
                overdue_items=_in_window_order(buckets[ReviewState.OVERDUE]),
                upcoming=_in_window_order(buckets[ReviewState.UPCOMING]),
            )
        )

    def is_review_due(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        as_of: str,
    ) -> Result[bool]:
        """Whether a target is due at ``as_of`` — the Scheduler's own decision
        (D-INV-009: "Scheduler 决定 review due；Learning 只提供 freshness").

        The answer is read off the **durable row's window** through
        :func:`elc.scheduler.spacing.state_at`, the same pure function
        :meth:`recompute_schedule_item` classified with — one ruler, never two:
        an answer computed by a second rule could contradict the state stored
        on the row it just read.

        ``False`` for a row that was never written and for a row with no window
        (either end missing): "not scheduled" is not "due now". ``True`` for
        ``DUE`` **and** ``OVERDUE`` — both are windows that have opened, and a
        caller asking "should this be reviewed now?" is asking about the open
        window, not about which side of the grace band it is on.
        """

        current = self._store.get_schedule_item(
            target_type, target_id, evidence_modality
        )
        if isinstance(current, Err):
            return current
        row = current.value
        if row is None:
            return Ok(False)
        window_start = row.next_review_window_start
        window_end = row.next_review_window_end
        if window_start is None or window_end is None:
            return Ok(False)
        state = state_at(as_of, window_start, window_end)
        if isinstance(state, Err):
            return state
        return Ok(
            state.value is ReviewState.DUE or state.value is ReviewState.OVERDUE
        )

    # -- the authority handshake (P7-0) -------------------------------------

    def schedule_currency(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[ScheduleCurrency | None]:
        """Whether this target's row was computed at the current Learning
        watermark (``None`` = no row written for this modality key).

        The two reads DOMAIN_MODEL §9 asks for, composed: the durable §5.2 row
        (the recorded ``source_learning_watermark``) and the Learning face's
        current evidence watermark. The comparison itself is
        :func:`elc.scheduler.authority.currency_of`, a pure function, so the
        Planner's assembly reaches the same answer by the same rule.

        ``Ok(None)`` is "the Scheduler has no row for this key", and it is
        **not** BF-02 §5's missing-Scheduler case: that case is about a
        consumer holding no schedule authority at all (no view, no rows), and
        a target nothing has been scheduled for is a state the §10 view
        reports as empty buckets. ``STALE`` is the third answer, and it says
        only what :mod:`elc.scheduler.authority` says: the row describes an
        earlier evidence set.

        Without the Learning read face this answers
        ``DEPENDENCY_UNAVAILABLE`` — the Scheduler will not invent a watermark
        to compare against, the same refusal
        :meth:`recompute_schedule_item` gives (one constructor, one rule).

        **The port is checked before the row, on purpose.** A controller built
        without a Learning face refuses with ``DEPENDENCY_UNAVAILABLE`` even
        for a key that holds no row: the missing collaborator is a fact about
        this object, not about the key, and answering ``Ok(None)`` first would
        report "nothing scheduled" for a question this face was never able to
        ask. :meth:`recompute_schedule_item` applies the same order (its first
        refusal is that same missing face), so both faces of the handshake
        give one rule rather than one rule per method.
        """

        if self._learning is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "schedule_currency needs the Learning watermark read"
                        " face (DOMAIN_MODEL §9 Reads): this controller was"
                        " constructed without one, and the Scheduler will not"
                        " invent a watermark to compare a row against"
                    ),
                )
            )
        current = self._store.get_schedule_item(
            target_type, target_id, evidence_modality
        )
        if isinstance(current, Err):
            return current
        if current.value is None:
            return Ok(None)
        watermark = self._learning.get_learning_watermark()
        if isinstance(watermark, Err):
            return watermark
        return Ok(currency_of(current.value, watermark.value))


def _in_window_order(
    items: Sequence[ScheduleItem],
) -> tuple[ScheduleItem, ...]:
    """One bucket, ordered ``(next_review_window_start, schedule_item_id)``.

    The key is the **stored column value**, the same convention the store's
    history read uses for ``created_at`` (p6-1's F-3 byte-order note): the
    order of a durable row set has to be a property of the rows, and the rows
    carry strings. The tie-break on the id is what makes it total — two rows
    may legitimately share a window.
    """

    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.next_review_window_start or "",
                item.schedule_item_id,
            ),
        )
    )
