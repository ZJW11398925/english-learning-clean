"""Curriculum domain command face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
)
from elc.platform.types import CurriculumNodeId, Result


@runtime_checkable
class CurriculumCommands(Protocol):
    """Canonical curriculum graph writes (HARD subgraph must stay a DAG)."""

    def register_capability(
        self, node: CapabilityNodeRecord
    ) -> Result[CurriculumNodeId]:
        ...

    def add_curriculum_edge(self, edge: CurriculumEdgeRecord) -> Result[None]:
        ...
