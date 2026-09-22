"""Empty Pedagogy Planner service — the kernel landed in P7-1; the wiring is
still owed.

The decision kernel is :mod:`elc.planner.kernel` (P7-1: §10.1's eleven steps
over P7-0's :class:`~elc.planner.feature_assembly.FeatureAuthority`, with a
trace). What is **not** wired yet, and is why this skeleton still raises:

- assembling a PlanningContext from a
  :class:`~elc.planner.types.PlanningRequest`'s twelve view fields (the
  orchestrator's side of §10);
- the Track A / Track B candidate generators, which turn those views into
  :class:`~elc.planner.kernel.CandidateProposal` records;
- the shadow-mode run (IMPLEMENTATION_PLAN §8: run the Planner, auto-teach
  nothing, review the trace) and the durable trace read behind
  :meth:`PlannerService.get_planner_evaluation`.

Until then this class stays an empty skeleton: a service that answered would
have to invent the three things above.
"""

from __future__ import annotations

from elc.planner.types import PlanningOutcome, PlanningRequest
from elc.platform.types import PlannerEvaluationId, Result


class PlannerService:
    """Application service only — owns no canonical truth (Phase 0)."""

    def plan(self, request: PlanningRequest) -> Result[PlanningOutcome]:
        raise NotImplementedError(
            "P7-1 landed the kernel (elc.planner.kernel.plan); the context"
            " assembly from PlanningRequest, the Track A/B candidate"
            " generators and shadow mode are the remaining wiring"
        )

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlanningOutcome | None]:
        raise NotImplementedError(
            "P7-1 landed the kernel (elc.planner.kernel.plan); a durable trace"
            " read needs a store, which no cut has landed"
        )
