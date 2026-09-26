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

#: docs/PRODUCT_CONTRACT.md §8.1 fact keys whose evidence no table of the
#: artifact carries, with the evidence that would have to exist for the fact
#: to become readable. **Empty since C1**: the thirteen evidence tables
#: (elc.content.build.SCHEMA_STATEMENTS, 11 → 24) carry every §8.1 fact key,
#: so :meth:`CurriculumContentStore.readiness_facts` reads the eighteen
#: row-backed keys and proves ``entity_row`` from the entity's own §24.1 row,
#: and has nothing left to declare absent.
#:
#: The mechanism is kept, not deleted: a fact added to §8.1 without a table
#: belongs here again, and the artifact's table set is exactly
#: `SCHEMA_STATEMENTS` (pinned by tests/phase5/test_p5_1_readiness.py), so a
#: build that removes one of those tables fails that pin first. The P5-R /
#: P5-0 history this mapping recorded (four §8.1 R1 keys and R0's third item
#: with no carrier at all) is preserved in
#: elc.curriculum.readiness.DECLARED_ABSENT_FACT_KEYS' own history and in
#: tests/phase5/test_p5_r_readiness_fail_closed.py.
#:
#: Registration guard (C1 disposition, F10): the per-entry loop that used to
#: pin this mapping's shape went silent when the set emptied, so it lives on
#: as a test over whatever is registered here — every entry must carry a
#: non-empty evidence description and a key the ladder actually declares
#: (tests/phase5/test_c1_evidence_face.py).
UNREAD_FACT_EVIDENCE: Mapping[str, str] = {}


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

        C1 (Phase 11): every §8.1 fact key is **read**, none hardcoded False.
        Eighteen of the nineteen keys are read from a table of the artifact
        (no fact is derived from another fact's presence — P5-R removed the
        ``entity_type == EXPRESSION ⇒ lexical_resolution`` equivalence, and
        no §24.4 recognition-policy label is promoted into an R4 detection
        fact); the nineteenth, ``entity_row``, is the one literal ``True`` in
        the assembly and is *proven* rather than read: reaching this point
        means the preceding :meth:`get_resource` succeeded, so the §24.1 row
        exists. The eighteen table-backed keys read a *row count* sourced
        from the thirteen evidence tables C1 adds to the build
        (:meth:`elc.content.store.ContentStore.evidence_counts` names the
        table and the column test behind each count); the remaining keys read
        the tables the earlier cuts already carried.

        Absence is read as absence: a target whose source states no evidence
        answers ``False`` per key, which is the artifact's answer, not a
        default the code supplies.
        """

        resource = self.get_resource(entity_id)
        if isinstance(resource, Err):
            return resource
        teaching = self.get_teaching_content(entity_id)
        if isinstance(teaching, Err):
            return teaching
        mapping = self._store.has_approved_curriculum_mapping(entity_id)
        if isinstance(mapping, Err):
            # Unreachable in practice (an unknown id already answered
            # NOT_FOUND above); propagated rather than swallowed, so a
            # failure here can never read as "no mapping".
            return mapping
        contrasts = self.get_examples(entity_id, ExampleLinkRole.CONTRAST)
        if isinstance(contrasts, Err):
            return contrasts
        canonical = self.get_examples(entity_id, ExampleLinkRole.PRIMARY_TARGET)
        if isinstance(canonical, Err):
            return canonical
        counts = self._store.evidence_counts(entity_id)
        if isinstance(counts, Err):
            return counts
        error_need = self._store.typical_error_required(entity_id)
        if isinstance(error_need, Err):
            return error_need
        evidence = counts.value

        return Ok(
            ReadinessFacts(
                target_id=entity_id,
                # R0: the §24.1 row is the source trace this artifact carries;
                # the §24.5 PRIMARY_TARGET example is the canonical surface;
                # assessment membership is its own §24.8 table (C1). All three
                # named things are read (the P5-R strict conjunction), so a
                # target whose source states no membership still reaches no
                # level — reported, never exempted.
                entity_row=True,
                canonical_form=bool(canonical.value),
                assessment_membership=evidence.assessment_memberships >= 1,
                # R1: the four §8.1-named things, each read from its own
                # §24.2 LexicalEntry / §24.3 Sense / §24.3 ContentText(role =
                # definition) / §24.2 Form evidence. `lexical_entries >= 1` is
                # exactly "POS is present": the build refuses an empty `pos`.
                pos=evidence.lexical_entries >= 1,
                sense=evidence.senses >= 1,
                basic_definition=evidence.definitions >= 1,
                forms=evidence.forms >= 1,
                # R2: §24.7 CurriculumLink — and since C3-R1 only an approved
                # **mapping**, not an approved row: a coverage placement
                # satisfies "there is a link row" while carrying no claim that
                # the resource has anything to do with the node's capability,
                # and R2 asks for a curriculum link, not for a nearest-node
                # bookkeeping entry (declared reading; the corpus's five nodes
                # against sixty-four resources is what makes the distinction
                # load-bearing). The read itself — one query over the §24.7
                # ``mapping_class`` column, gated on the same §24.11 approval
                # the supply read keeps as its own gate — lives in
                # :meth:`elc.content.store.ContentStore.
                # has_approved_curriculum_mapping`. A row that is unapproved
                # or a placement stays readable through ``curriculum_links_of``
                # and does not satisfy this fact.
                curriculum_link=mapping.value,
                # R2's remaining three: §24.7 PedagogicalProfile, §24.8
                # PackOverlay and §24.7 ResourceLabel rows.
                pedagogical_profile=evidence.pedagogical_profiles >= 1,
                goal_pack_overlay=evidence.pack_overlays >= 1,
                resource_labels=evidence.resource_labels >= 1,
                # R3: a reviewed explanation/note, a usable example policy
                # (§8.1's policy, not the §24.5 example inventory — those
                # rows are already an R0/R1 fact), and "必要 contrast/usage":
                # a §24.5 CONTRAST row **or** the usage face of a §24.7
                # ResourceLabel.
                #
                # "reviewed" has no dedicated §24 marker today; the C1
                # disposition reads it through the entity's own §24.11
                # editorial discipline: a `teaching_note` row exists **and**
                # the entity's lifecycle_status is "CANONICAL_APPROVED" (the
                # same editorial word the approved curriculum_link carries).
                # Revisit: if §24 gains a reviewed marker on the note itself,
                # the read moves to it.
                reviewed_explanation=(
                    evidence.teaching_notes >= 1
                    and resource.value.lifecycle_status == "CANONICAL_APPROVED"
                ),
                example_policy=evidence.example_policies >= 1,
                contrast_or_usage=(
                    bool(contrasts.value)
                    or evidence.labelled_usage_modalities >= 1
                ),
                # §8.1 R3's "以及需要时的 TypicalError": the *need* is the
                # source's declaration (read from the artifact's own key, not
                # from a code default), the row set is §24.9's.
                typical_error=evidence.typical_errors >= 1,
                typical_error_required=error_need.value,
                # R4: §24.10's "可测试 detection policy/fixtures/
                # false-positive boundary" — four separate facts, each read
                # from its own table (policy / rules / the two fixture kinds).
                detection_policy=evidence.detection_policies >= 1,
                recognition_rules=evidence.detection_rules >= 1,
                negative_fixtures=evidence.negative_fixtures >= 1,
                false_positive_boundaries=(
                    evidence.false_positive_boundaries >= 1
                ),
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
