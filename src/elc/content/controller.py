"""Empty Content Library controller (Phase 5 integration will implement)."""

from __future__ import annotations

from elc.content.types import ReadinessLevel, TeachingUnit
from elc.platform.types import ContentId, ContentVersion, ResourceId, Result, TargetId


class ContentController:
    """Owns canonical teaching resources. Phase 0: no logic."""

    def load_content_release(self, release_manifest: str) -> Result[ContentVersion]:
        raise NotImplementedError("Phase 5: versioned content.db load")

    def get_teaching_unit(self, target_id: TargetId) -> Result[TeachingUnit | None]:
        raise NotImplementedError("Phase 5: TeachingUnit assembly")

    def get_readiness(self, target_id: TargetId) -> Result[ReadinessLevel | None]:
        raise NotImplementedError("Phase 5: readiness gate")

    def resolve_resource(self, resource_id: ResourceId) -> Result[ContentId | None]:
        raise NotImplementedError("Phase 5: resource resolution")
