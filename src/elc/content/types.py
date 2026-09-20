"""Content Library — canonical teaching resources (supporting context).

Owns (docs/DOMAIN_MODEL.md §8): canonical content types (LEXICAL_ENTRY,
FORM, SENSE, EXPRESSION, CONSTRUCTION, EXAMPLE), expression subtypes,
important relations, readiness levels R0–R4, provenance.

content.db is a READ-ONLY, versioned build artifact (docs/DATA_MODEL.md §2);
the runtime consumes TeachingUnit aggregate DTOs — never a canonical
mega-table (docs/DATA_MODEL.md §24.13). V1: targets without R4 (or a formal
detector certification) never enter the automatic error-triggered path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import ContentId, ContentVersion, ResourceId, TargetId


class ContentType(StrEnum):
    """docs/DOMAIN_MODEL.md §8 canonical content types."""

    LEXICAL_ENTRY = "LEXICAL_ENTRY"
    FORM = "FORM"
    SENSE = "SENSE"
    EXPRESSION = "EXPRESSION"
    CONSTRUCTION = "CONSTRUCTION"
    EXAMPLE = "EXAMPLE"


class ExpressionSubtype(StrEnum):
    """docs/DOMAIN_MODEL.md §8 expression subtypes."""

    COLLOCATION = "COLLOCATION"
    LEXICAL_CHUNK = "LEXICAL_CHUNK"
    PHRASAL_VERB = "PHRASAL_VERB"
    IDIOM = "IDIOM"
    DISCOURSE_MARKER = "DISCOURSE_MARKER"
    FUNCTIONAL_EXPRESSION = "FUNCTIONAL_EXPRESSION"
    PRAGMATIC_FORMULA = "PRAGMATIC_FORMULA"
    SENTENCE_FRAME = "SENTENCE_FRAME"


class ReadinessLevel(StrEnum):
    """docs/DOMAIN_MODEL.md §8 Content Readiness (normative)."""

    R0_INDEXED = "R0_INDEXED"
    R1_LEXICALLY_RESOLVED = "R1_LEXICALLY_RESOLVED"
    R2_PLANNER_READY = "R2_PLANNER_READY"
    R3_TEACHING_READY = "R3_TEACHING_READY"
    R4_DETECTION_READY = "R4_DETECTION_READY"


@dataclass(frozen=True)
class ContentResourceRecord:
    """One canonical resource with traceable provenance."""

    content_id: ContentId
    resource_id: ResourceId
    content_type: ContentType
    expression_subtype: ExpressionSubtype | None
    readiness: ReadinessLevel
    source_snapshot_ref: str


@dataclass(frozen=True)
class TeachingUnit:
    """Runtime aggregate DTO (docs/DATA_MODEL.md §24.13) — planner/teaching
    consumption view assembled from canonical content, not canonical truth."""

    target_id: TargetId
    content_version: ContentVersion
    resources: tuple[ContentResourceRecord, ...]
    readiness: ReadinessLevel
    pedagogical_profile: str | None
    typical_errors: tuple[str, ...]
