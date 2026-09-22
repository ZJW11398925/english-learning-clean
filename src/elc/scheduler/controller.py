"""Scheduler Domain Controller — the review-truth authority face (Phase 6
P6-1 graduation; TASK-OPI-6259f6fd-….12 ②④).

The Phase 0 skeleton raised a phase pointer from every method. P6-1 graduates
it the way P3-0/P3-1A/P4-1/P4-3/P6-0 graduated LearningController /
TeachingController / RelationshipController / UserConfigController: the
durable rows and every SQL statement live in :mod:`elc.scheduler.store`, and
this face **delegates** — it holds no rule of its own and touches no table.
The version discipline (a moved version replaces; the same version with
different content is refused) and the append-first identity rule of
:class:`elc.scheduler.types.ReviewEvent` are the store's, stated once there.

**Two methods stay declared and raising, deliberately**: ``get_schedule_view``
and ``is_review_due``. docs/DOMAIN_MODEL.md §9 makes the due/overdue decision
the Scheduler's ("Learning 不能直接输出 `REVIEW_DUE`；Scheduler 才决定
due/overdue" — D-INV-009), and §10 makes ScheduleView the Planner's input
authority; both are p6-2's work, so they raise with a **P6-2 pointer** rather
than being dropped (the teaching graduation precedent: a face whose phase has
not arrived keeps its declaration and says which phase owns it). What P6-1
owes — and what this face now answers — is the durable review *truth* those
two methods will read.

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

Failure semantics: every implemented face returns a ``Result``; nothing
raises into a caller except a stale-epoch store (a programming error, the
repo-wide fence convention) and the two P6-2 declarations above.
"""

from __future__ import annotations

from elc.platform.types import EvidenceModality, Result, TargetId
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewEvent, ScheduleItem, ScheduleView

__all__ = ["P6_2_DUE_DECISION_POINTER", "SchedulerController"]

#: The pointer the two not-yet-owned declarations raise with: one string, so
#: a caller (and a pin) can recognise the phase that owns the reading without
#: parsing a sentence.
P6_2_DUE_DECISION_POINTER = (
    "P6-2: due/overdue decision (docs/DOMAIN_MODEL.md §9 — the Scheduler"
    " decides due/overdue; §10 — ScheduleView is the Planner input)"
)


class SchedulerController:
    """Owns review truth over :class:`SqliteSchedulerStore`.

    One collaborator, exactly as ``UserConfigController``: the store carries
    the connection, the epoch fence (every write checks it before anything is
    written) and every statement, so a second constructor argument would have
    nothing to do here. The face is pure delegation — which is what a
    schema-owning boundary looks like once its domain has no decision to make
    about a write whose shape is already the canonical one.
    """

    def __init__(self, store: SqliteSchedulerStore) -> None:
        self._store = store

    # -- the write faces (§5.2) --------------------------------------------

    def upsert_schedule_item(self, item: ScheduleItem) -> Result[ScheduleItem]:
        """Commit one schedule row (§5.2).

        The durable row comes back — stamped with this store's clock, and
        identical to what :meth:`get_schedule_item` reads. The four rules of
        the write (replay / a moved version replaces / the same version with
        different content refuses / the modality key is unique) are the
        store's, stated once in :mod:`elc.scheduler.store`.

        No gate here: a schedule row is the Scheduler's own projection, not
        personal content, and no consent-style gate belongs on it. Nothing
        about ``review_state`` is computed either — the caller's state is
        stored as given, because the state *transitions* (and the due decision
        behind them) are p6-2's spacing-history work.
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

    # -- the p6-2 declarations (kept, and pointed) --------------------------

    def get_schedule_view(self, scope: str) -> Result[ScheduleView]:
        """The Planner's input view (docs/DOMAIN_MODEL.md §10).

        **Not this slice's.** The view is produced by the due/overdue cut, so
        it raises the P6-2 pointer instead of answering a bucket membership
        nothing here can decide.
        """

        raise NotImplementedError(P6_2_DUE_DECISION_POINTER)

    def is_review_due(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        at: str,
    ) -> Result[bool]:
        """Whether a target is due at ``at`` — the Scheduler's own decision
        (D-INV-009: "Scheduler 决定 review due；Learning 只提供 freshness").

        **Not this slice's.** The signature is keyed by the modality key
        because that is ``ScheduleItem``'s key (and the shape the row can
        actually be found by); the decision itself — how
        ``source_learning_watermark``, the window columns and the state become
        one answer — is p6-2's, so this raises the P6-2 pointer.
        """

        raise NotImplementedError(P6_2_DUE_DECISION_POINTER)
