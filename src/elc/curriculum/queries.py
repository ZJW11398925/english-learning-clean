"""Curriculum domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.content.types import ContentOrigin
from elc.curriculum.readiness import ReadinessAssessment, ReadinessFacts
from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumCandidateView,
    CurriculumEdgeRecord,
    CurriculumGraphRecord,
    CurriculumLinkRecord,
)
from elc.platform.types import (
    CapabilityId,
    ContentVersion,
    CurriculumNodeId,
    CurriculumVersion,
    ResourceId,
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


@runtime_checkable
class CurriculumSupplyQueries(Protocol):
    """The curriculum-side read face the Planner and the teaching supply
    consume (P5-1, TASK-OPI-4d516e4f-….46 ③).

    One signature per method name, in curriculum-side vocabulary:

    - ids are curriculum/content ids (:class:`CurriculumNodeId`,
      :class:`ResourceId`, :class:`CapabilityId`), not bare ``str`` — the
      artifact reader (elc.content.store) spells them as ``str`` and the
      conversion happens once, in the adapter
      (elc.curriculum.store.CurriculumContentStore), whose signatures are
      pinned equal to this protocol's by
      tests/phase5/test_p5_1_curriculum_read_face.py;
    - ``curriculum_version`` returns the nullable result the domain already
      declared in :class:`CurriculumQueries` ("no curriculum graph declared"
      is a legal state; the curriculum authority is not migrated, see
      elc.curriculum.store).

    Scope of the pin: **only the twelve names declared here are pinned**. The
    one same-named method outside it is ``get_examples``, whose role
    annotation is *deliberately wider* on the artifact reader
    (``ExampleLinkRole | str`` — a variant-artifact probe may pass the raw
    §24.5 spelling) than on the adapter (``ExampleLinkRole``); that width is
    declared and pinned by
    tests/phase5/test_p5_1_curriculum_read_face.py, not left to drift.

    ``supply_entity_ids`` / ``is_supply_eligible`` are the §24.11 supply gate
    (IMPLEMENTATION_PLAN §6 "candidate content excluded"), and
    ``content_origin`` is the canonical/personal origin face
    (IMPLEMENTATION_PLAN §6 "Personal Content origin separation"). Neither is
    the readiness ladder: ``readiness`` / ``readiness_facts`` report the §8.1
    level and its supporting fact keys without filtering anything.
    """

    def content_version(self) -> Result[ContentVersion]:
        ...

    def curriculum_version(self) -> Result[CurriculumVersion | None]:
        ...

    def capability_ids(self) -> Result[tuple[CapabilityId, ...]]:
        ...

    def get_capability(
        self, capability_id: CapabilityId
    ) -> Result[CapabilityNodeRecord]:
        ...

    def curriculum_links_of(
        self, resource_id: ResourceId
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        ...

    def curriculum_links_to(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        ...

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        ...

    def content_origin(self, entity_id: str) -> Result[ContentOrigin]:
        ...

    def is_supply_eligible(self, entity_id: str) -> Result[bool]:
        ...

    def supply_entity_ids(self) -> Result[tuple[ResourceId, ...]]:
        ...

    def readiness_facts(self, entity_id: str) -> Result[ReadinessFacts]:
        ...

    def readiness(self, entity_id: str) -> Result[ReadinessAssessment]:
        ...
