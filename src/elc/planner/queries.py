"""Pedagogy Planner query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.planner.types import PlanningOutcome
from elc.platform.types import PlannerEvaluationId, Result


@runtime_checkable
class PlannerQueries(Protocol):
    """Trace reads for audit/debugging; never mastery truth."""

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlanningOutcome | None]:
        ...
