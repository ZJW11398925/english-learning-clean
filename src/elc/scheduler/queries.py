"""Scheduler domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import Result, TargetId
from elc.scheduler.types import ReviewStateRecord, ScheduleView


@runtime_checkable
class SchedulerQueries(Protocol):
    """Review due/overdue decisions live here — and only here (D-INV-009)."""

    def get_schedule_view(self, scope: str) -> Result[ScheduleView]:
        ...

    def get_review_state(
        self, target_id: TargetId
    ) -> Result[ReviewStateRecord | None]:
        ...

    def is_review_due(self, target_id: TargetId, at: str) -> Result[bool]:
        ...
