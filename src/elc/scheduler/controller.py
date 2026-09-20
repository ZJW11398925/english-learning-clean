"""Empty Scheduler Domain Controller (Phase 6 will implement)."""

from __future__ import annotations

from elc.platform.types import Result, TargetId
from elc.scheduler.types import ReviewStateRecord, ScheduleView


class SchedulerController:
    """Owns review_state / urgency / windows / spacing. Phase 0: no logic."""

    def record_review_outcome(
        self, target_id: TargetId, retrieved: bool, at: str
    ) -> Result[ReviewStateRecord]:
        raise NotImplementedError("Phase 6: spacing progression")

    def suspend_review(self, target_id: TargetId, reason: str) -> Result[None]:
        raise NotImplementedError("Phase 6: suspension")

    def get_schedule_view(self, scope: str) -> Result[ScheduleView]:
        raise NotImplementedError("Phase 6: ScheduleView projection")

    def get_review_state(
        self, target_id: TargetId
    ) -> Result[ReviewStateRecord | None]:
        raise NotImplementedError("Phase 6: review state read")

    def is_review_due(self, target_id: TargetId, at: str) -> Result[bool]:
        raise NotImplementedError("Phase 6: due decision (scheduler-only)")
