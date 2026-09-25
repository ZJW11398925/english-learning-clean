"""Empty Curriculum Domain Controller — a Phase 0 red-line skeleton, not a
pending implementation.

`tests/architecture/test_gate_1_domain_interfaces.py` requires every method
below to raise ``NotImplementedError`` (the Phase 0 red line). The live faces
are the pure ladder in ``elc.curriculum.readiness`` (R0–R4, required-fact
keys) and the production teaching-target provider in
``elc.curriculum.provider``; see
``tests/architecture/test_surface_census.py`` for ``elc.curriculum``'s row.
"""

from __future__ import annotations

from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumCandidateView,
    CurriculumEdgeRecord,
    CurriculumGraphRecord,
)
from elc.platform.types import (
    CurriculumNodeId,
    CurriculumVersion,
    Result,
    TargetId,
)


class CurriculumController:
    """Owns the curriculum graph + capability registry. Phase 0 red line: no logic."""

    def register_capability(
        self, node: CapabilityNodeRecord
    ) -> Result[CurriculumNodeId]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.curriculum: see SURFACE_CENSUS (capability registry)"
        )

    def add_curriculum_edge(self, edge: CurriculumEdgeRecord) -> Result[None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.curriculum: see SURFACE_CENSUS (graph edges, HARD subgraph"
            " DAG)"
        )

    def get_curriculum_graph(self) -> Result[CurriculumGraphRecord | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.curriculum: see SURFACE_CENSUS (graph projection)"
        )

    def get_curriculum_candidate_view(
        self, scope: str
    ) -> Result[CurriculumCandidateView]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; the Planner's"
            " candidate side is elc.planner (planner candidate view)"
        )

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.curriculum: see SURFACE_CENSUS (prerequisite lookup)"
        )

    def capability_of_target(
        self, target_id: TargetId
    ) -> Result[CapabilityNodeRecord | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.curriculum: see SURFACE_CENSUS (target→capability mapping)"
        )

    def curriculum_version(self) -> Result[CurriculumVersion | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.curriculum: see SURFACE_CENSUS (version metadata)"
        )
