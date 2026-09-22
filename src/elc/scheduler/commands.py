"""Scheduler domain command face.

Three writes, all §5.2 (docs/DATA_MODEL.md):

- :meth:`SchedulerCommands.recompute_schedule_item` — **the due decision's
  write**: it reads the target's Learning freshness, the store's watermark and
  the row's own review history, runs the pure policy
  (:mod:`elc.scheduler.spacing`) and commits the resulting current row. This is
  the §9 command ("Scheduler 才决定 due/overdue"): a caller asks for the
  schedule to be *recomputed*, not for a state to be set, so the state always
  comes from the same rule;
- :meth:`SchedulerCommands.upsert_schedule_item` — the current schedule row
  for one ``(target_type, target_id, evidence_modality)`` key, written as
  given. A versioned projection, so a moved ``version`` replaces and the same
  version with different content is refused (the store's rule, §1.4);
- :meth:`SchedulerCommands.record_review_event` — one appended review fact.
  §1.3's append-first: the same ``review_event_id`` with different content is
  refused rather than rewritten.

The Phase 0 spellings (``record_review_outcome`` / ``suspend_review``) are
gone with the Phase 0 vocabulary: §5.2 has no ``retrieved`` column and no
``SUSPENDED`` state (see :mod:`elc.scheduler.controller` and
:mod:`elc.scheduler.types`).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import EvidenceModality, Result, TargetId
from elc.scheduler.types import ReviewEvent, ScheduleItem


@runtime_checkable
class SchedulerCommands(Protocol):
    """Scheduler-owned review writes (fed by practice/review history)."""

    def recompute_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        as_of: str,
    ) -> Result[ScheduleItem]:
        """Recompute and commit the current row for one modality key.

        ``as_of`` is the instant the state is decided at — a parameter, never
        an internal clock, so two calls with the same inputs answer
        identically. A row is written **even when nothing is scheduled**:
        ``NOT_SCHEDULED`` with no window and no stage is the honest record of
        a target that has no review obligation yet.
        """
        ...

    def upsert_schedule_item(self, item: ScheduleItem) -> Result[ScheduleItem]:
        """Commit one schedule row; the durable (stamped) row comes back."""
        ...

    def record_review_event(self, event: ReviewEvent) -> Result[ReviewEvent]:
        """Append one review event; never a rewrite of an existing one."""
        ...
