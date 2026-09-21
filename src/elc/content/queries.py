"""Content Library read face.

Two layers live here:

- the Phase 0 domain boundary :class:`ContentQueries` (unchanged), and
- the P5-0 runtime read face over the built ``content.db`` artifact
  (TASK-OPI-4d516e4f-….38 ③): :class:`ContentResourceView` — exactly the
  docs/DATA_MODEL.md §24.1 seven columns, in order — plus the §24.4
  expression view, the migrated §11 target defaults and the §24.13-style
  teaching payload, and the curriculum registry views the runtime reads
  alongside them.

The implementation is :class:`elc.content.store.ContentStore`; the artifact
is opened read-only (`file:…?mode=ro`), so no read face here can mutate it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.content.types import ReadinessLevel, TeachingUnit
from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
    CurriculumLinkRecord,
)
from elc.platform.types import (
    ContentId,
    ContentVersion,
    CurriculumVersion,
    ResourceId,
    Result,
    TargetId,
)


@dataclass(frozen=True)
class ContentResourceView:
    """One canonical content entity — docs/DATA_MODEL.md §24.1's seven
    columns, word for word and in the canonical order.

    Exactly these seven fields: the column set is pinned by
    tests/phase5/test_content_views.py against the §24.1 code block of the
    canonical document, so an added or renamed field fails there rather than
    becoming an undeclared schema.
    """

    entity_id: str
    entity_type: str
    language: str
    lifecycle_status: str
    entity_revision: int
    created_in_version: str
    updated_in_version: str


@dataclass(frozen=True)
class ContentExpressionView:
    """The §24.4 expression payload of one entity (subtype / fixedness /
    recognition policy). "Recognition proposes a match；不等于 mastery" —
    nothing here carries mastery."""

    entity_id: str
    expression_type: str
    fixedness: str
    recognition_policy: str


@dataclass(frozen=True)
class ContentTargetView:
    """The §11 canonical defaults + §24.14 V1 evidence modality of one target
    (migrated verbatim from the Phase 3 validated corpus)."""

    entity_id: str
    target_type: str
    target_mode: str
    learning_intent: str
    evidence_modality: str


@dataclass(frozen=True)
class ContentTeachingView:
    """The P3-1B teaching payload of one target, field for field the
    ``elc.teaching.targets.TeachingTargetView`` shape (the canonical §24
    fixes no ladder/answer-key tables, so the migration keeps the validated
    Phase 3 shape instead of inventing one).

    ``capability_linkage`` is the resource's primary REALIZES node id (the
    Phase 3 fixture's ``capability_linkage``), read from the curriculum link
    table — it is never a second copy of the same fact. P5-R: the link must
    carry the approved §24.11 ``editorial_status``
    (elc.content.store.CAPABILITY_CREDIT_EDITORIAL_STATUS) before it becomes
    a linkage here, because this field is what the teaching chain credits on
    an ``ALTERNATIVE_SUCCESS`` attempt; an unapproved mapping reads ``None``
    and stays readable as a link row.
    """

    entity_id: str
    hint_ladder: tuple[str, ...]
    reveal_form: str
    canonical_forms: tuple[str, ...]
    alternative_realizations: tuple[str, ...]
    required_slots: tuple[tuple[str, ...], ...]
    capability_linkage: str | None


@runtime_checkable
class ContentQueries(Protocol):
    """Canonical resource reads + readiness gates."""

    def get_teaching_unit(self, target_id: TargetId) -> Result[TeachingUnit | None]:
        ...

    def get_readiness(self, target_id: TargetId) -> Result[ReadinessLevel | None]:
        ...

    def resolve_resource(self, resource_id: ResourceId) -> Result[ContentId | None]:
        ...


@runtime_checkable
class ContentRuntimeQueries(Protocol):
    """The P5-0 runtime read face over content.db (read-only).

    Every lookup that names an id rejects an id the registry does not declare
    with ``DomainErrorCode.NOT_FOUND`` (IMPLEMENTATION_PLAN §6 acceptance:
    "unknown capability ID rejected") — never a silent ``None``, so a caller
    cannot mistake "absent" for "present but empty".
    """

    def content_version(self) -> Result[ContentVersion]:
        ...

    def curriculum_version(self) -> Result[CurriculumVersion]:
        ...

    def entity_ids(self) -> Result[tuple[str, ...]]:
        ...

    def capability_ids(self) -> Result[tuple[str, ...]]:
        ...

    def get_resource(self, entity_id: str) -> Result[ContentResourceView]:
        ...

    def get_expression(self, entity_id: str) -> Result[ContentExpressionView]:
        ...

    def get_target(self, entity_id: str) -> Result[ContentTargetView]:
        ...

    def get_teaching_content(self, entity_id: str) -> Result[ContentTeachingView]:
        ...

    def get_capability(self, capability_id: str) -> Result[CapabilityNodeRecord]:
        ...

    def curriculum_links_of(
        self, resource_id: str
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        ...

    def curriculum_links_to(
        self, node_id: str
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        ...

    def prerequisites_of(
        self, node_id: str
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        ...
