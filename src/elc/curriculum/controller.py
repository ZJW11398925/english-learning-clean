"""Empty Curriculum Domain Controller (Phase 5 will implement)."""

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
    """Owns the curriculum graph + capability registry. Phase 0: no logic."""

    def register_capability(
        self, node: CapabilityNodeRecord
    ) -> Result[CurriculumNodeId]:
        raise NotImplementedError("Phase 5: capability registry")

    def add_curriculum_edge(self, edge: CurriculumEdgeRecord) -> Result[None]:
        raise NotImplementedError("Phase 5: graph edges (HARD subgraph DAG)")

    def get_curriculum_graph(self) -> Result[CurriculumGraphRecord | None]:
        raise NotImplementedError("Phase 5: graph projection")

    def get_curriculum_candidate_view(
        self, scope: str
    ) -> Result[CurriculumCandidateView]:
        raise NotImplementedError("Phase 7: planner candidate view")

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        raise NotImplementedError("Phase 5: prerequisite lookup")

    def capability_of_target(
        self, target_id: TargetId
    ) -> Result[CapabilityNodeRecord | None]:
        raise NotImplementedError("Phase 5: target→capability mapping")

    def curriculum_version(self) -> Result[CurriculumVersion | None]:
        raise NotImplementedError("Phase 5: version metadata")
