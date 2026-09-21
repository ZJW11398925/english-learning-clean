"""Content Library — canonical teaching resources (supporting context).

Owns (docs/DOMAIN_MODEL.md §8): canonical content types (LEXICAL_ENTRY,
FORM, SENSE, EXPRESSION, CONSTRUCTION, EXAMPLE), expression subtypes,
important relations, readiness levels R0–R4, provenance.

content.db is a READ-ONLY, versioned build artifact (docs/DATA_MODEL.md §2);
the runtime consumes TeachingUnit aggregate DTOs — never a canonical
mega-table (docs/DATA_MODEL.md §24.13). V1: targets without R4 (or a formal
detector certification) never enter the automatic error-triggered path.

P5-0 adds the §24.1 entity column list and the §24.4/§24.5/§24.11/§11
vocabularies the authoring source (`content_src/*`, `curriculum/*`) is
validated against at build time (elc.content.build). The build rejects a
value outside a canonical word list; it never normalizes or skips.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import ContentId, ContentVersion, ResourceId, TargetId

#: docs/DATA_MODEL.md §24.1 ContentEntity — the seven columns, in order.
#: elc.content.queries.ContentResourceView carries exactly these fields.
CONTENT_ENTITY_COLUMNS = (
    "entity_id",
    "entity_type",
    "language",
    "lifecycle_status",
    "entity_revision",
    "created_in_version",
    "updated_in_version",
)

#: docs/DATA_MODEL.md §24.11 lifecycle vocabulary. The canonical text lists
#: two slash rows ("SENSE_RESOLVED / STRUCTURED", "DEPRECATED / REPLACED"):
#: each name on either side of the slash is a legal value, so they are
#: enumerated here as separate accepted spellings rather than invented
#: compounds.
LIFECYCLE_STATUSES = (
    "RAW_IMPORTED",
    "NORMALIZED",
    "SENSE_RESOLVED",
    "STRUCTURED",
    "ENRICHED",
    "CURRICULUM_MAPPED",
    "PEDAGOGICALLY_ANNOTATED",
    "REVIEW_REQUIRED",
    "CANONICAL_APPROVED",
    "DEPRECATED",
    "REPLACED",
)

#: docs/DOMAIN_MODEL.md §6 — the two claim target scopes. The Teaching Gate
#: port (elc.teaching.targets.TARGET_TYPES) pins the same two values for the
#: consumer side; this copy lets the content build validate its own source
#: without depending on a consumer domain.
TARGET_TYPES = ("RESOURCE", "CAPABILITY")

#: docs/DOMAIN_MODEL.md §11 target modes (the same values
#: elc.planner.types.TargetMode pins for the planner side).
TARGET_MODES = (
    "RESOURCE_PRACTICE",
    "CAPABILITY_PRACTICE",
    "PROBE",
    "REVIEW",
    "TRANSFER",
)

#: docs/DOMAIN_MODEL.md §11 learning intents (the same values
#: elc.planner.types.LearningIntent pins for the planner side).
LEARNING_INTENTS = (
    "ESTABLISH",
    "DEVELOP",
    "WITHDRAW_SUPPORT",
    "CONSOLIDATE",
    "PROBE",
    "TRANSFER",
    "EXPAND_REPERTOIRE",
)


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


class ExpressionFixedness(StrEnum):
    """docs/DATA_MODEL.md §24.4 fixedness."""

    FIXED = "FIXED"
    SEMI_FIXED = "SEMI_FIXED"
    SLOT_BASED = "SLOT_BASED"


class RecognitionPolicy(StrEnum):
    """docs/DATA_MODEL.md §24.4 ExpressionVariant / RecognitionPattern
    policies. "Recognition proposes a match；不等于 mastery.\""""

    EXACT = "EXACT"
    LEMMA_SEQUENCE = "LEMMA_SEQUENCE"
    SLOT_PATTERN = "SLOT_PATTERN"
    MODEL_ASSISTED = "MODEL_ASSISTED"


class ExampleLinkRole(StrEnum):
    """docs/DATA_MODEL.md §24.5 ExampleLink roles. The migrated corpus maps
    ``canonical_forms`` onto PRIMARY_TARGET and
    ``alternative_realizations`` onto SUPPORTING."""

    PRIMARY_TARGET = "PRIMARY_TARGET"
    SUPPORTING = "SUPPORTING"
    CONTRAST = "CONTRAST"
    ERROR_INSTANCE = "ERROR_INSTANCE"


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
