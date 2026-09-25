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


class ContentOrigin(StrEnum):
    """Where a content entity came from (P5-1, IMPLEMENTATION_PLAN §6
    "Personal Content origin separation" / acceptance "canonical/personal
    origin preserved").

    docs/DATA_MODEL.md §24 declares no Personal Content entity and no origin
    column, so Local V1 states the two-member vocabulary here and states the
    artifact's own origin as a fact (:data:`ARTIFACT_CONTENT_ORIGIN`) instead
    of inventing a column — the §24.1 seven-column pin is exactly what an
    eighth column would break.

    - ``CANONICAL`` — built from the canonical authoring tree (`content_src/*`
      + `curriculum/*`, docs/DATA_MODEL.md §24). Every row of the content.db
      artifact is this origin, by construction.
    - ``PERSONAL`` — learner-owned content. Local V1 ships the vocabulary
      member and the check that reads it, and produces **no row**: the
      personal source is not wired (:data:`PERSONAL_CONTENT_WIRED` is False),
      which is the "interface only" half of the same declaration.
    """

    CANONICAL = "CANONICAL"
    PERSONAL = "PERSONAL"


#: The two origins, as an ordered tuple (the declared vocabulary).
CONTENT_ORIGINS = tuple(str(origin) for origin in ContentOrigin)

#: The origin of every row of the content.db artifact. Not a stored column:
#: the artifact is generated from the canonical tree only
#: (elc.content.build.load_source reads `content_src/*` + `curriculum/*` and
#: refuses any document outside the indexed set), so a build-derived origin
#: is the only truthful answer the read face can give.
ARTIFACT_CONTENT_ORIGIN = ContentOrigin.CANONICAL

#: Local V1 posture: a personal-content source is *not* wired. The read face
#: therefore never answers ``PERSONAL`` today — a declared absence, not a
#: silent one (the constant is asserted by tests/phase5).
PERSONAL_CONTENT_WIRED = False

#: docs/DATA_MODEL.md §24.11 — the only lifecycle status a content entity may
#: carry and still enter teaching/planner supply. "Model-generated candidate
#: 默认不是 ``CANONICAL_APPROVED``", so a candidate (or any other unapproved
#: status) is excluded from supply (IMPLEMENTATION_PLAN §6 acceptance
#: "candidate content excluded"). Readiness is a different axis and never
#: substitutes for this gate (docs/PRODUCT_CONTRACT.md §8.1).
SUPPLY_LIFECYCLE_STATUS = "CANONICAL_APPROVED"

#: docs/DATA_MODEL.md §24.11 retired statuses. They are *deterministic*
#: non-supply states (the entity still exists and still says what it is),
#: which is why the teaching port reports them instead of hiding them behind
#: "no such target" (elc.curriculum.provider).
RETIRED_LIFECYCLE_STATUSES = ("DEPRECATED", "REPLACED")

#: docs/DATA_MODEL.md §24.3 ContentText roles — the six words, verbatim. A
#: text row carries one of them; a role outside the set is refused by the
#: build (reject, never normalize).
CONTENT_TEXT_ROLES = (
    "gloss",
    "definition",
    "translation",
    "usage",
    "teaching_note",
    "disambiguation",
)

#: docs/DATA_MODEL.md §24.10 R4 — "R4 必须包含可测试 detection
#: policy/fixtures/false-positive boundary". A detection fixture is either a
#: **negative** example (the detector must not fire on it) or a declared
#: **false-positive boundary** (the example sits exactly on the edge the
#: boundary names). §24.10 names the two concepts and gives no word list, so
#: the two words are C1's declared reading of that split (Revisit = a
#: canonical fixture vocabulary); the build refuses any other value.
DETECTION_FIXTURE_KINDS = ("NEGATIVE", "FALSE_POSITIVE_BOUNDARY")

#: docs/DATA_MODEL.md §24.9 TypicalError — a *source-level declaration* that
#: this target needs a TypicalError, which §8.1 R3 turns into the conditional
#: fact "以及需要时的 TypicalError". No §24 table carries a per-entity source
#: declaration (§24.6's ContentSource/SourceSnapshot/Assertion trio is the
#: canonical home and is NOT carried by V1), so it is recorded as a
#: `content_meta` key: **declared reading**, Revisit = when §24.6 lands,
#: migrate this key into the assertion carrier it describes. The declaration
#: is durable on purpose — a source may declare the need before the authoring
#: has written the error, and §8.1 readiness is a *report* of that gap, never
#: a build-time refusal of it.
TYPICAL_ERROR_REQUIRED_KEY_PREFIX = "typical_error_required:"


def typical_error_required_key(entity_id: str) -> str:
    """The ``content_meta`` key carrying one entity's TypicalError need.

    One function, used by the writer (elc.content.build) and the reader
    (elc.content.store), so the key format cannot drift between them.
    """

    return f"{TYPICAL_ERROR_REQUIRED_KEY_PREFIX}{entity_id}"


def supply_eligible(lifecycle_status: str) -> bool:
    """May an entity with this §24.11 ``lifecycle_status`` enter
    teaching/planner supply?

    One predicate, used by both supply faces (the curriculum read adapter and
    the teaching target provider) so the two cannot drift. It answers only the
    §24.11 supply question: it is not a readiness judgement (docs/
    PRODUCT_CONTRACT.md §8.1) and it never decides a Gate outcome.
    """

    return lifecycle_status == SUPPLY_LIFECYCLE_STATUS


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
