"""Scheduler domain command face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import Result, TargetId
from elc.scheduler.types import ReviewStateRecord


@runtime_checkable
class SchedulerCommands(Protocol):
    """Scheduler-owned review state writes (fed by practice/review history)."""

    def record_review_outcome(
        self,
        target_id: TargetId,
        retrieved: bool,
        at: str,
    ) -> Result[ReviewStateRecord]:
        """Advance spacing stage from an actual retrieval outcome."""
        ...

    def suspend_review(self, target_id: TargetId, reason: str) -> Result[None]:
        ...
