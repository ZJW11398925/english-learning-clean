"""Empty Pedagogy Planner service — the kernel, the supply side and the ledger
landed (P7-1/P7-2/P7-3); the assembly and the shadow-mode run are still owed.

The decision kernel is :mod:`elc.planner.kernel` (P7-1: §10.1's eleven steps
over P7-0's :class:`~elc.planner.feature_assembly.FeatureAuthority`, with a
trace), the Track A / Track B generators are
:mod:`elc.planner.candidates` (P7-2, with the §12 scope and the BF-02 §11
prerequisite resolver beside them), and the ledger and frontier are
:mod:`elc.planner.ledger` / :mod:`elc.planner.frontier` (P7-3). What is **not**
wired yet, and is why this skeleton still raises:

- assembling a PlanningContext from a
  :class:`~elc.planner.types.PlanningRequest`'s twelve view fields (the
  orchestrator's side of §10) — the call that would hand the generators their
  inputs and hand their proposals to the kernel;
- the shadow-mode run (IMPLEMENTATION_PLAN §8: run the Planner, auto-teach
  nothing, review the trace) and the durable trace read behind
  :meth:`PlannerService.get_planner_evaluation`. Shadow mode is p7-4's work
  item; the trace read needs a store, and the PlanningLedger is deliberately
  table-less (``NO_TABLE_V1``, elc.planner.ledger).

Until then this class stays an empty skeleton: a service that answered would
have to invent the two things above.
"""

from __future__ import annotations

from elc.planner.types import PlanningOutcome, PlanningRequest
from elc.platform.types import PlannerEvaluationId, Result


class PlannerService:
    """Application service only — owns no canonical truth (Phase 0)."""

    def plan(self, request: PlanningRequest) -> Result[PlanningOutcome]:
        raise NotImplementedError(
            "P7-1/P7-2/P7-3 landed the kernel, the Track A/B candidate"
            " generators and the ledger + frontier; the context assembly from"
            " PlanningRequest and shadow mode (p7-4) are the remaining wiring"
        )

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlanningOutcome | None]:
        raise NotImplementedError(
            "P7-1 landed the kernel (elc.planner.kernel.plan); a durable trace"
            " read needs a store, which no cut has landed"
        )
