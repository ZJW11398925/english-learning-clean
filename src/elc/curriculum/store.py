"""Curriculum-side read face over the §24 artifact (content.db).

docs/DATA_MODEL.md §2 fixes the physical profile: there is one artifact —
``content.db`` — and no ``curriculum.db``. The §24 authoring source is two
trees (`content_src/*` and `curriculum/*`) that one build step
(elc.content.build) writes into that single artifact, so the runtime read face
is shared: this module is the thin curriculum-side adapter over
:class:`elc.content.store.ContentStore`, and it makes two statements explicit
that were open until P5-1:

1. **content.db 是 §24 双树共用 artifact 读面；curriculum 侧权威未迁移.**
   What this adapter reads is the curriculum *slice* the build wrote
   (capability registry / §24.7 CurriculumLink / §7 prerequisite edges). The
   canonical curriculum authority — the graph as a versioned owner schema —
   has NOT been migrated into a runtime store, so nothing here may be read as
   "the curriculum domain's durable truth". The authoring authority stays in
   `curriculum/*`.
2. **One signature per method name, in curriculum-side vocabulary.** The
   Planner-facing reads take the domain's own types
   (:class:`elc.platform.types.CurriculumNodeId`, :class:`ResourceId`) and
   `curriculum_version` returns the domain's nullable result, exactly as
   `elc.curriculum.queries` declares them. The artifact reader spells ids as
   ``str`` (it is the content face); the conversion happens here, once, and
   the parity between this adapter and the port is pinned by
   tests/phase5/test_p5_1_curriculum_read_face.py (P5-0 review F-6: the same
   method name had two signatures and no place said which one a caller gets).

Local V1 supply rules (IMPLEMENTATION_PLAN §6 acceptance "candidate content
excluded" / "canonical/personal origin preserved"), stated once here and
applied through one shared predicate:

- **origin** — every row of the artifact is ``CANONICAL`` by construction
  (it is generated from the canonical tree only); the ``PERSONAL`` origin is a
  declared vocabulary member with no row producer in Local V1
  (elc.content.types.PERSONAL_CONTENT_WIRED is False). :meth:`content_origin`
  answers the first half and refuses nothing silently.
- **supply** — §24.11: an entity whose ``lifecycle_status`` is not
  ``CANONICAL_APPROVED`` never enters teaching/planner supply.
  :meth:`supply_entity_ids` is the curriculum face of that filter, and
  :meth:`is_supply_eligible` is the single-entity form; the teaching port
  (elc.curriculum.provider) applies the same predicate from
  elc.content.types so the two faces cannot drift.

Readiness is a *different* axis and is reported, never used as a supply filter
here (docs/PRODUCT_CONTRACT.md §8.1 defaults are the automatic-frontier
policy): :meth:`readiness_facts` / :meth:`readiness` assemble and judge the
§8.1 ladder through :mod:`elc.curriculum.readiness`.

Not re-exported from ``elc.curriculum.__init__`` — the reason is the import
cycle, not taste: ``elc.content.queries`` imports ``elc.curriculum.types``,
which runs the curriculum package ``__init__`` first, so an init-level
``from elc.curriculum.store import …`` re-enters a half-initialized
``elc.content.queries`` and raises ``ImportError`` (the P5-1 reviewer verified
it outside the repo; the edge is visible in elc/content/queries.py's imports).
Import this module by its full path.
"""

from __future__ import annotations

import sqlite3
from typing import Callable, Mapping, TypeVar

from elc.content.queries import (
    ContentExpressionView,
    ContentResourceView,
    ContentTargetView,
    ContentTeachingView,
)
from elc.content.store import ContentStore, ContentStoreError
from elc.content.types import (
    ARTIFACT_CONTENT_ORIGIN,
    ContentOrigin,
    ContentType,
    ExampleLinkRole,
    supply_eligible,
)
from elc.curriculum.readiness import (
    ReadinessAssessment,
    ReadinessFacts,
    judge_readiness,
)
from elc.curriculum.types import (
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
    CurriculumLinkRecord,
)
from elc.platform.types import (
    CapabilityId,
    ContentVersion,
    CurriculumNodeId,
    CurriculumVersion,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    ResourceId,
    Result,
)

__all__ = [
    "UNREAD_FACT_EVIDENCE",
    "CurriculumContentStore",
]

_T = TypeVar("_T")

#: docs/PRODUCT_CONTRACT.md §8.1 fact keys whose evidence **no table of the
#: P5-0 artifact carries**, with the evidence that would have to exist for the
#: fact to become readable. The mapping answers "why is this fact absent?" — it
#: is not an invented column list: the artifact's table set is exactly
#: elc.content.build.SCHEMA_STATEMENTS (pinned by
#: tests/phase5/test_p5_1_readiness.py), so a build that adds such a table
#: fails that pin first and this mapping is revisited.
UNREAD_FACT_EVIDENCE: Mapping[str, str] = {
    "pedagogical_profile": "a §24.7 PedagogicalProfile row",
    "goal_pack_overlay": "a §24.8 PackOverlay (goal/pack overlay) row",
    "resource_labels": "a §24.7 ResourceLabel row (register/usage-modality)",
    "reviewed_explanation": "a reviewed explanation/note for the target",
    "example_policy": "an example policy (which examples to present, when)",
    "typical_error": "a §24.9 TypicalError row",
    "detection_policy": "a testable §24.9 detection_policy with fixtures",
    "recognition_rules": (
        "detection-grade recognition rules (§24.4's recognition_policy is"
        " the R1 lexical payload, not this)"
    ),
    "negative_fixtures": "negative fixtures for the detection rules",
    "false_positive_boundaries": "declared false-positive boundaries",
    # The two keys that are *entity-type scoped*: this corpus satisfies the
    # first (all 14 entities are EXPRESSION) and cannot satisfy the second.
    "lexical_resolution": (
        "POS / sense / basic definition / forms rows (§24.2 Form / §24.3"
        " Sense) — required for any entity_type other than EXPRESSION"
    ),
    "assessment_membership": (
        "a §24.8 AssessmentMembership row (the R0 sentence's third item)"
    ),
}


def _unavailable(message: str) -> Err[object]:
    return Err(
        DomainError(
            code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
            message=message,
        )
    )


class CurriculumContentStore:
    """The curriculum/planner read face over one built content.db.

    Constructed over an already-open :class:`elc.content.store.ContentStore`
    (which is itself read-only by construction), so this adapter inherits the
    §2 read-only profile and adds no second connection. Every read maps a
    failure to an ``Err`` — an unreadable artifact never raises out of here,
    so a caller cannot mistake "could not answer" for "answered nothing"
    (``DomainErrorCode.NOT_FOUND`` stays reserved for ids the registry does
    not declare).
    """

    def __init__(self, store: ContentStore) -> None:
        self._store = store

    # -- plumbing ----------------------------------------------------------

    def close(self) -> None:
        """Close the underlying artifact connection (the adapter opened it
        nowhere else, so this is the only connection it owns)."""

        self._store.close()

    def _read(self, reader: Callable[[], Result[_T]]) -> Result[_T]:
        """Run one artifact read, mapping an unusable artifact to
        DEPENDENCY_UNAVAILABLE (never a NOT_FOUND, never a raise)."""

        try:
            return reader()
        except (ContentStoreError, sqlite3.Error) as exc:
            return _unavailable(f"content.db is not readable: {exc!r}")

    # -- §26.1 artifact metadata -------------------------------------------

    def content_version(self) -> Result[ContentVersion]:
        return self._read(self._store.content_version)

    def curriculum_version(self) -> Result[CurriculumVersion | None]:
        """The curriculum version the artifact declares.

        The nullable return is the curriculum domain's vocabulary
        (`elc.curriculum.queries.CurriculumQueries.curriculum_version`): "no
        curriculum graph declared" is a legal state while the curriculum
        authority is unmigrated. This adapter never invents that state — a
        built artifact always declares a version (asserted in
        tests/phase5/test_p5_1_curriculum_read_face.py), and an artifact that
        does not is an ``Err``, not a ``None``.
        """

        version: Result[CurriculumVersion] = self._read(
            self._store.curriculum_version
        )
        if isinstance(version, Err):
            return version
        return Ok(CurriculumVersion(version.value))

    # -- content-face reads the teaching port needs ------------------------

    def get_resource(self, entity_id: str) -> Result[ContentResourceView]:
        return self._read(lambda: self._store.get_resource(entity_id))

    def get_expression(self, entity_id: str) -> Result[ContentExpressionView]:
        return self._read(lambda: self._store.get_expression(entity_id))

    def get_target(self, entity_id: str) -> Result[ContentTargetView]:
        return self._read(lambda: self._store.get_target(entity_id))

    def get_teaching_content(self, entity_id: str) -> Result[ContentTeachingView]:
        return self._read(lambda: self._store.get_teaching_content(entity_id))

    def get_examples(
        self, entity_id: str, role: ExampleLinkRole
    ) -> Result[tuple[str, ...]]:
        """The §24.5 example rows of one entity in one role."""

        return self._read(lambda: self._store.get_examples(entity_id, role))

    # -- curriculum registry face ------------------------------------------

    def capability_ids(self) -> Result[tuple[CapabilityId, ...]]:
        ids = self._read(self._store.capability_ids)
        if isinstance(ids, Err):
            return ids
        return Ok(tuple(CapabilityId(capability_id) for capability_id in ids.value))

    def get_capability(
        self, capability_id: CapabilityId
    ) -> Result[CapabilityNodeRecord]:
        return self._read(lambda: self._store.get_capability(str(capability_id)))

    def curriculum_links_of(
        self, resource_id: ResourceId
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        return self._read(
            lambda: self._store.curriculum_links_of(str(resource_id))
        )

    def curriculum_links_to(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        return self._read(lambda: self._store.curriculum_links_to(str(node_id)))

    def prerequisites_of(
        self, node_id: CurriculumNodeId
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        """The prerequisite edges declared for this curriculum node.

        Curriculum-node vocabulary in, curriculum-node vocabulary out — the
        artifact reader's ``str`` signature stops here (P5-0 review F-6).
        """

        return self._read(lambda: self._store.prerequisites_of(str(node_id)))

    # -- origin separation + candidate exclusion (Local V1) ----------------

    def content_origin(self, entity_id: str) -> Result[ContentOrigin]:
        """The origin of one artifact entity.

        The entity must exist (an id the registry does not declare is
        NOT_FOUND, like every other id lookup). A row that exists is
        ``CANONICAL``: content.db is generated from the canonical authoring
        tree, and the personal origin has no producer in Local V1
        (elc.content.types.PERSONAL_CONTENT_WIRED is False) — so this method
        has exactly one possible answer today, and it is the truthful one.
        """

        resource = self.get_resource(entity_id)
        if isinstance(resource, Err):
            return resource
        return Ok(ARTIFACT_CONTENT_ORIGIN)

    def is_supply_eligible(self, entity_id: str) -> Result[bool]:
        """Whether this entity may enter teaching/planner supply (§24.11).

        An unknown id is NOT_FOUND (never ``False``: "not in the registry" and
        "in the registry but not approved" are different facts).
        """

        resource = self.get_resource(entity_id)
        if isinstance(resource, Err):
            return resource
        return Ok(supply_eligible(resource.value.lifecycle_status))

    def supply_entity_ids(self) -> Result[tuple[ResourceId, ...]]:
        """Every artifact entity that may enter teaching/planner supply.

        This is the curriculum face of IMPLEMENTATION_PLAN §6 "candidate
        content excluded": §24.11 entities whose ``lifecycle_status`` is not
        ``CANONICAL_APPROVED`` are absent from this set while remaining
        readable everywhere else (excluded ≠ deleted — the same entity is
        still an ``R0``-indexable row, and the teaching port still reports its
        deterministic non-validity instead of pretending it does not exist).
        """

        eligible: list[ResourceId] = []
        ids = self._read(self._store.entity_ids)
        if isinstance(ids, Err):
            return ids
        for entity_id in ids.value:
            resource = self.get_resource(entity_id)
            if isinstance(resource, Err):
                return resource
            if supply_eligible(resource.value.lifecycle_status):
                eligible.append(ResourceId(entity_id))
        return Ok(tuple(eligible))

    # -- readiness (docs/PRODUCT_CONTRACT.md §8.1) -------------------------

    def readiness_facts(self, entity_id: str) -> Result[ReadinessFacts]:
        """Assemble the §8.1 fact bundle of one target from the artifact.

        Present facts are read; absent facts stay absent (the dataclass
        default), each one named in :data:`UNREAD_FACT_EVIDENCE` — no fact is
        defaulted to True, and no §24.4 recognition-policy label is promoted
        into an R4 detection fact.
        """

        resource = self.get_resource(entity_id)
        if isinstance(resource, Err):
            return resource
        expression = self.get_expression(entity_id)
        teaching = self.get_teaching_content(entity_id)
        if isinstance(expression, Err):
            return expression
        if isinstance(teaching, Err):
            return teaching
        links = self.curriculum_links_of(ResourceId(entity_id))
        if isinstance(links, Err):
            return links
        contrasts = self.get_examples(entity_id, ExampleLinkRole.CONTRAST)
        if isinstance(contrasts, Err):
            return contrasts
        canonical = self.get_examples(entity_id, ExampleLinkRole.PRIMARY_TARGET)
        if isinstance(canonical, Err):
            return canonical

        return Ok(
            ReadinessFacts(
                target_id=entity_id,
                # R0: the §24.1 row is the source trace this artifact carries;
                # the §24.5 PRIMARY_TARGET example is the canonical surface.
                entity_row=True,
                canonical_form=bool(canonical.value),
                # R0's third item (§24.8 AssessmentMembership) is read here as
                # an explicit absence — no V1 table carries it, and no level
                # requires it (elc.curriculum.readiness
                # DECLARED_ABSENT_FACT_KEYS). A strict three-item reading of
                # R0 would leave this corpus with no level at all; that is an
                # interpretation of this implementation, declared, not hidden.
                assessment_membership=False,
                # R1: the §24.4 expression payload — and only for an entity
                # whose §24.1 entity_type is EXPRESSION, which is the type the
                # reading is declared for. Any other entity type would need
                # POS/sense/definition/forms rows this artifact does not carry,
                # so it reads R0 (F-1 guard).
                lexical_resolution=(
                    resource.value.entity_type
                    == str(ContentType.EXPRESSION)
                ),
                # R2: §24.7 CurriculumLink — and only an approved mapping, the
                # same discipline the supply gate keeps.
                curriculum_link=any(
                    link.editorial_status == "CANONICAL_APPROVED"
                    for link in links.value
                ),
                # R3: a §24.5 CONTRAST example or the usage face of a §24.7
                # ResourceLabel (the label rows do not exist, so today this is
                # exactly "the target has a declared contrast").
                contrast_or_usage=bool(contrasts.value),
                # R3's "usable example policy" is not the example inventory
                # (those rows are already R0/R1 facts) — see
                # UNREAD_FACT_EVIDENCE. The example inventory itself is
                # present for every target of this corpus and stays readable
                # through get_teaching_content.
                #
                # R2/R3/R4 facts the artifact carries no table for, plus
                # typical_error_required (a source-side declaration no V1
                # source makes), keep their False defaults.
            )
        )

    def readiness(self, entity_id: str) -> Result[ReadinessAssessment]:
        """The judged §8.1 level of one target, with its per-level evidence."""

        facts = self.readiness_facts(entity_id)
        if isinstance(facts, Err):
            return facts
        return Ok(judge_readiness(facts.value))

    def readiness_by_target(self) -> Result[tuple[ReadinessAssessment, ...]]:
        """Every artifact target's assessment, in id order (the corpus table)."""

        assessments: list[ReadinessAssessment] = []
        ids = self._read(self._store.entity_ids)
        if isinstance(ids, Err):
            return ids
        for entity_id in ids.value:
            assessment = self.readiness(entity_id)
            if isinstance(assessment, Err):
                return assessment
            assessments.append(assessment.value)
        return Ok(tuple(assessments))
