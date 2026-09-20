"""Content Library query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.content.types import ReadinessLevel, TeachingUnit
from elc.platform.types import ContentId, Result, ResourceId, TargetId


@runtime_checkable
class ContentQueries(Protocol):
    """Canonical resource reads + readiness gates."""

    def get_teaching_unit(self, target_id: TargetId) -> Result[TeachingUnit | None]:
        ...

    def get_readiness(self, target_id: TargetId) -> Result[ReadinessLevel | None]:
        ...

    def resolve_resource(self, resource_id: ResourceId) -> Result[ContentId | None]:
        ...
