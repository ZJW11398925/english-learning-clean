"""Scheduler domain query face.

Reads of §5.2's two objects, plus the two decisions P6-2 landed:

- :meth:`SchedulerQueries.get_schedule_item` — the current row for a modality
  key (``None`` = never written);
- :meth:`SchedulerQueries.list_review_events` — one row's history, in the
  deterministic order ``(created_at, review_event_id)``;
- :meth:`SchedulerQueries.get_schedule_view` — the Planner's input view
  (docs/DOMAIN_MODEL.md §10): every current row classified at one ``as_of``
  into the DUE / OVERDUE / UPCOMING buckets, with the model version and the
  instant carried on the view itself;
- :meth:`SchedulerQueries.is_review_due` — the due question, answered here and
  only here (D-INV-009 "Scheduler 决定 review due；Learning 只提供
  freshness"). It reads the durable row's window through the same pure
  function the recomputation uses, so the two faces can never disagree.

``get_schedule_view`` replaced a Phase 0 ``scope`` parameter rather than
honouring it: §5.2's ScheduleItem carries **no owner and no scope column**, so
a scope filter would have had nothing to filter — a signature promising a
selection the data cannot make. ``as_of`` is the parameter that actually
decides bucket membership, and it is what the view now takes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import EvidenceModality, Result, TargetId
from elc.scheduler.types import ReviewEvent, ScheduleItem, ScheduleView


@runtime_checkable
class SchedulerQueries(Protocol):
    """Review due/overdue decisions live here — and only here (D-INV-009)."""

    def get_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[ScheduleItem | None]:
        """The current schedule row for this modality key."""
        ...

    def list_review_events(
        self, schedule_item_id: str
    ) -> Result[tuple[ReviewEvent, ...]]:
        """One schedule row's review history, in durable order."""
        ...

    def get_schedule_view(self, as_of: str) -> Result[ScheduleView]:
        """The Planner's input view (DOMAIN_MODEL §10), classified at ``as_of``.

        The Planner consumes this; §9 keeps the due decision on this side, so
        the classification is the Scheduler's and the view is the one place it
        is handed over. ``NOT_SCHEDULED`` rows appear in no bucket, and each
        bucket is ordered ``(next_review_window_start, schedule_item_id)``.
        """
        ...

    def is_review_due(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        as_of: str,
    ) -> Result[bool]:
        """Whether this target is due at ``as_of`` (D-INV-009).

        Keyed by the modality key, because that is ScheduleItem's key: the
        Phase 0 spelling took ``target_id`` alone, and a schedule row cannot
        be found without the evidence modality its key carries. A row that was
        never written, and a row with no window, both answer ``False`` — no
        window is not a due window.
        """
        ...
