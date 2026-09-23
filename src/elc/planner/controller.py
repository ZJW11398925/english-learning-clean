"""Pedagogy Planner service — the shadow-mode face landed (P7-4).

The decision kernel is :mod:`elc.planner.kernel` (P7-1: §10.1's eleven steps
over P7-0's :class:`~elc.planner.feature_assembly.FeatureAuthority`, with a
trace), the Track A / Track B generators are :mod:`elc.planner.candidates`
(P7-2, with the §12 scope and the BF-02 §11 prerequisite resolver beside them),
the ledger and frontier are :mod:`elc.planner.ledger` /
:mod:`elc.planner.frontier` (P7-3), and the shadow-mode run is
:mod:`elc.planner.shadow` (P7-4) — this class forwards to it and computes
nothing of its own.

Two faces stay unwired, and this module says why rather than answering with an
invented record:

- :meth:`PlannerService.plan` is the **dispatch** entry — the outcome a runtime
  handler would act on. §8's shadow mode is the opposite of that step ("先只输出
  trace，不真正自动教学"), and the orchestrator that would call this one is a
  later cut's work item, so it keeps the skeleton's refusal while the shadow
  face beside it runs;
- :meth:`PlannerService.get_planner_evaluation` is the durable trace read, and
  the store it needs does not exist: P7-3's PlanningLedger is deliberately
  table-less (``NO_TABLE_V1``, :mod:`elc.planner.ledger`). A service that
  answered would have to invent the row it claims to have read.
"""

from __future__ import annotations

from elc.planner.candidates import CandidateSupply
from elc.planner.shadow import ShadowRun, run_shadow
from elc.planner.types import PlanningOutcome, PlanningRequest
from elc.platform.types import PlannerEvaluationId, Result


class PlannerService:
    """Application service only — owns no canonical truth (Phase 0)."""

    def run_shadow(
        self,
        request: PlanningRequest,
        *,
        supply: CandidateSupply | None = None,
        current_learning_watermark: int | None = None,
        natural_break_available: bool = False,
    ) -> ShadowRun:
        """P7-4's shadow run, forwarded to :mod:`elc.planner.shadow`.

        IMPLEMENTATION_PLAN §8: run the Planner, auto-teach nothing, and keep
        the record of what it would have selected and why. The service adds no
        behaviour to that run — the chain (the request's views → P7-0's
        assembly → the kernel) and the record are the module's, and this method
        exists so a caller reaches the shadow face through the Planner's own
        service rather than through a module import.
        """

        return run_shadow(
            request,
            supply=supply,
            current_learning_watermark=current_learning_watermark,
            natural_break_available=natural_break_available,
        )

    def plan(self, request: PlanningRequest) -> Result[PlanningOutcome]:
        raise NotImplementedError(
            "P7-1/P7-2/P7-3 landed the kernel, the Track A/B candidate"
            " generators and the ledger + frontier, and P7-4 landed shadow"
            " mode (run_shadow) — releasing a PlannerDecision for a runtime to"
            " act on is the dispatch half, which the orchestrator's"
            " PlanningRequest assembly owns and no cut has landed"
        )

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlanningOutcome | None]:
        raise NotImplementedError(
            "the kernel answers an evaluation for one cycle"
            " (elc.planner.kernel.plan) and P7-4 records shadow runs, but a"
            " durable trace read needs a store: P7-3's PlanningLedger is"
            " deliberately table-less (NO_TABLE_V1), so there is no row this"
            " face could read"
        )
