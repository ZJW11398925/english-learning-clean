"""Curriculum domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


@runtime_checkable
class CurriculumQueries(Protocol):
    """Curriculum reads for Planner candidate assembly."""

    def get_curriculum_graph(self) -> Result[CurriculumGraphRecord | None]:
        ...

    def get_curriculum_candidate_view(
        self, scope: str
    ) -> Result[CurriculumCandidateView]:
        ...

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        ...

    def capability_of_target(
        self, target_id: TargetId
    ) -> Result[CapabilityNodeRecord | None]:
        ...

    def curriculum_version(self) -> Result[CurriculumVersion | None]:
        ...
