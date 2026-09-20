"""Empty Pedagogy Planner service (Phase 7 shadow mode will implement)."""

from __future__ import annotations

from elc.planner.types import PlanningOutcome, PlanningRequest
from elc.platform.types import PlannerEvaluationId, Result


class PlannerService:
    """Application service only — owns no canonical truth (Phase 0)."""

    def plan(self, request: PlanningRequest) -> Result[PlanningOutcome]:
        raise NotImplementedError("Phase 7: planner kernel + shadow mode")

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlanningOutcome | None]:
        raise NotImplementedError("Phase 7: evaluation trace read")
