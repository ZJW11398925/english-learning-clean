"""Scheduler domain command face.

Two writes, both §5.2 (docs/DATA_MODEL.md):

- :meth:`SchedulerCommands.upsert_schedule_item` — the current schedule row
  for one ``(target_type, target_id, evidence_modality)`` key. A versioned
  projection, so a moved ``version`` replaces and the same version with
  different content is refused (the store's rule, §1.4);
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

from elc.platform.types import Result
from elc.scheduler.types import ReviewEvent, ScheduleItem


@runtime_checkable
class SchedulerCommands(Protocol):
    """Scheduler-owned review writes (fed by practice/review history)."""

    def upsert_schedule_item(self, item: ScheduleItem) -> Result[ScheduleItem]:
        """Commit one schedule row; the durable (stamped) row comes back."""
        ...

    def record_review_event(self, event: ReviewEvent) -> Result[ReviewEvent]:
        """Append one review event; never a rewrite of an existing one."""
        ...
