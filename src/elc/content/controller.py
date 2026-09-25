"""Empty Content Library controller — a Phase 0 red-line skeleton, not a
pending implementation.

`tests/architecture/test_gate_1_domain_interfaces.py` requires every method
below to raise ``NotImplementedError`` (the Phase 0 red line). The work this
package actually runs through lives elsewhere: see
``tests/architecture/test_surface_census.py`` for ``elc.content``'s row of the
live-face census (``elc.content.store:SqliteContentStore``, with the
deterministic build face in ``elc.content.build``). Revisit: the decision face
(VALIDATE / COMMIT / REJECT / ABSTAIN) lands here — then this banner's claim
moves into the census table.
"""

from __future__ import annotations

from elc.content.types import ReadinessLevel, TeachingUnit
from elc.platform.types import ContentId, ContentVersion, ResourceId, Result, TargetId


class ContentController:
    """Owns canonical teaching resources. Phase 0 red line: no logic."""

    def load_content_release(self, release_manifest: str) -> Result[ContentVersion]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.content: see SURFACE_CENSUS (versioned content.db load)"
        )

    def get_teaching_unit(self, target_id: TargetId) -> Result[TeachingUnit | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.content: see SURFACE_CENSUS (TeachingUnit assembly)"
        )

    def get_readiness(self, target_id: TargetId) -> Result[ReadinessLevel | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; the readiness"
            " ladder is elc.curriculum.readiness (readiness gate)"
        )

    def resolve_resource(self, resource_id: ResourceId) -> Result[ContentId | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.content: see SURFACE_CENSUS (resource resolution)"
        )
