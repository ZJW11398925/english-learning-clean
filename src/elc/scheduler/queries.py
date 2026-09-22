"""Scheduler domain query face.

Reads of §5.2's two objects, plus the two declarations p6-2 fills:

- :meth:`SchedulerQueries.get_schedule_item` — the current row for a modality
  key (``None`` = never written);
- :meth:`SchedulerQueries.list_review_events` — one row's history, in the
  deterministic order ``(created_at, review_event_id)``;
- :meth:`SchedulerQueries.get_schedule_view` — **declared, P6-2-owned**:
  docs/DOMAIN_MODEL.md §10 makes ScheduleView the Planner's input authority,
  and producing it is the due/overdue cut's work;
- :meth:`SchedulerQueries.is_review_due` — **declared, P6-2-owned**: the due
  question lives here and only here (D-INV-009 "Scheduler 决定 review due；
  Learning 只提供 freshness"), and its answer is p6-2's.

Keeping the two declarations while the slice that fills them has not run is
the teaching graduation precedent: a face a consumer cannot find is worse
than a face that says which phase owns it.
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

    def get_schedule_view(self, scope: str) -> Result[ScheduleView]:
        """The Planner's input view (DOMAIN_MODEL §10) — produced in P6-2."""
        ...

    def is_review_due(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        at: str,
    ) -> Result[bool]:
        """Whether this target is due at ``at`` — decided in P6-2.

        Keyed by the modality key, because that is ScheduleItem's key: the
        Phase 0 spelling took ``target_id`` alone, and a schedule row cannot
        be found without the evidence modality its key carries.
        """
        ...
