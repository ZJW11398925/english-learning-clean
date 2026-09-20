"""Pedagogy Planner command face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.planner.types import PlanningOutcome, PlanningRequest
from elc.platform.types import Result


@runtime_checkable
class PlannerCommands(Protocol):
    """Plan one decision cycle. Output carries decision XOR degraded status."""

    def plan(self, request: PlanningRequest) -> Result[PlanningOutcome]:
        """Fixed kernel order (docs/DOMAIN_MODEL.md §10.1): canonicalize →
        feature assembly → context validity → hard eligibility → policy
        utility → coverage safeguard → activation → explicit-request
        priority → Pareto prune → deterministic tie-break → SELECT/NO_TARGET.
        """
        ...
