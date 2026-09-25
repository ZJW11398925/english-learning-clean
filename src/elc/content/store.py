"""Read-only runtime reader over the built content.db artifact.

docs/DATA_MODEL.md §2: `content.db — read-only, versioned canonical content
runtime build`. The runtime never writes it (the only writer is the build
step, elc.content.build), so this module opens the artifact through a
read-only SQLite URI (`file:…?mode=ro`) — an attempted write fails at the
SQLite layer with ``sqlite3.OperationalError: attempt to write a readonly
database`` (probe: tests/phase5/test_content_store_readonly.py), not by
convention.

Scope (P5-0, TASK-OPI-4d516e4f-….38 ③):

- the content face: :class:`elc.content.queries.ContentResourceView` (§24.1
  seven columns), the §24.4 expression payload, the migrated §11 target
  defaults and the P3-1B teaching payload;
- the curriculum registry face: the §7 capability registry, §24.7
  CurriculumLink and §7 prerequisite edges — both faces read the one §2
  artifact (there is no curriculum.db).

Every id lookup rejects an id the registry does not declare (NOT_FOUND);
no method silently answers "nothing" for an unknown id. This module carries
no readiness judgment, no candidate assembly and no production provider —
those are p5-1.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from elc.content.queries import (
    ContentExpressionView,
    ContentResourceView,
    ContentTargetView,
    ContentTeachingView,
)
from elc.content.types import ExampleLinkRole, typical_error_required_key
from elc.curriculum.types import (
    CapabilityFamily,
    CapabilityNodeRecord,
    CurriculumEdgeRecord,
    CurriculumEdgeType,
    CurriculumLinkRecord,
    CurriculumLinkRelation,
    PrerequisiteStrength,
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
    "CAPABILITY_CREDIT_EDITORIAL_STATUS",
    "ContentEvidenceCounts",
    "ContentStore",
    "ContentStoreError",
    "open_read_only",
]

#: docs/DATA_MODEL.md §26.1 metadata keys carried by the artifact.
_CONTENT_VERSION_KEY = "content_version"
_CURRICULUM_VERSION_KEY = "curriculum_version"

#: The §24.11 ``editorial_status`` a §24.7 CurriculumLink must carry before it
#: may become a *capability credit* (P5-R). A link the author's review has not
#: approved is a curriculum *mapping*, not a claim about the learner's
#: capability: the chat/teaching chain credits ``ALTERNATIVE_SUCCESS`` to the
#: capability a link names, so an unapproved link would mint
#: CAPABILITY / POSITIVE learner evidence out of a test-corpus convenience
#: mapping. One constant, used by the one read that feeds that credit path.
#:
#: C1 disposition note (approval kept): the one ``CANONICAL_APPROVED`` row
#: this gate admits (``res-colloc-make-a-decision`` →
#: ``cap-eval-hedged-opinion``) was approved by the C1 editorial review with
#: stated limits — no capability-semantics audit was possible (the capability
#: has no functional definition in this repository), and this admission is
#: what lets that target's ``ALTERNATIVE_SUCCESS`` mint CAPABILITY/POSITIVE
#: evidence (a known, accepted behavior change, bounded by the real rollout
#: HOLD). curriculum/README.md C2 carries the full coverage/limits wording;
#: Revisit when the capability's functional definition lands (live risk
#: ``R-C1-credit``).
CAPABILITY_CREDIT_EDITORIAL_STATUS = "CANONICAL_APPROVED"


class ContentStoreError(RuntimeError):
    """The artifact is missing, or does not carry the built content schema.

    Raised instead of degrading: a content.db without the canonical tables is
    not a content.db the runtime may read a partial answer out of.
    """


def open_read_only(db_path: str | Path) -> sqlite3.Connection:
    """Open one content.db through the §2 read-only profile.

    `mode=ro` is enforced by SQLite itself: the connection can read and can
    never write, whatever a caller does with it (`PRAGMA query_only` would be
    a second, weaker belt on the same braces; the probe pins the real one).
    """

    path = Path(db_path)
    if not path.is_file():
        raise ContentStoreError(f"content.db not found: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


_REQUIRED_TABLES = (
    "content_meta",
    "content_entity",
    "content_expression",
    "content_target",
    "content_teaching",
    "content_hint_rung",
    "content_example",
    "content_slot",
    "curriculum_capability",
    "curriculum_link",
    "curriculum_prerequisite",
    # C1's §8.1 evidence face (elc.content.build.SCHEMA_STATEMENTS, 11 → 24).
    # Required, not optional: an artifact built before this face would answer
    # every readiness fact with "absent" — a silent skip of the whole ladder
    # — so a stale artifact is refused at open instead ("not a content.db the
    # runtime may read a partial answer out of").
    "content_assessment_membership",
    "content_lexical_entry",
    "content_sense",
    "content_text",
    "content_form",
    "content_pedagogical_profile",
    "content_pack_overlay",
    "content_resource_label",
    "content_example_policy",
    "content_typical_error",
    "content_detection_policy",
    "content_detection_rule",
    "content_detection_fixture",
)


@dataclass(frozen=True)
class ContentEvidenceCounts:
    """How much §8.1 evidence one entity carries, one count per table/word.

    docs/PRODUCT_CONTRACT.md §8.1's ladder asks *whether* a fact's evidence
    exists, so this read face answers presence rather than row contents: one
    ``COUNT(*)`` per evidence kind, no joins, no second interpretation of the
    rows. A ``0`` is "the artifact carries no such row" — it is never "could
    not read": an unreadable artifact raises out of the store and the caller
    maps it to ``DEPENDENCY_UNAVAILABLE`` (elc.curriculum.store._read), so
    absence and unreadability stay distinguishable.

    The three fields whose *value* §8.1 names carry the value test rather than
    a bare row count, and say so:

    - ``lexical_entries`` — §24.2's Lemma/POS row. The build refuses an empty
      ``pos`` (``build._string``), so one row *is* "POS is present";
    - ``definitions`` / ``teaching_notes`` — §24.3 text rows in the two roles
      §8.1's R1/R3 sentences name (``definition`` / ``teaching_note``);
    - ``labelled_usage_modalities`` — §24.7 ResourceLabel rows that state a
      ``usage_modality``, which is the usage face §8.1 R3's "contrast/usage"
      reads (a label row with the facet NULL is a legal row and does not
      count here).
    """

    assessment_memberships: int
    lexical_entries: int
    senses: int
    definitions: int
    forms: int
    pedagogical_profiles: int
    pack_overlays: int
    resource_labels: int
    labelled_usage_modalities: int
    example_policies: int
    teaching_notes: int
    typical_errors: int
    detection_policies: int
    detection_rules: int
    negative_fixtures: int
    false_positive_boundaries: int


def _count_one(conn: sqlite3.Connection, statement: str, entity_id: str) -> int:
    row = conn.execute(statement, (entity_id,)).fetchone()
    if row is None:  # pragma: no cover - COUNT(*) always answers one row
        raise ContentStoreError(f"count query returned no row: {statement}")
    return int(row[0])


def _not_found(kind: str, identifier: str) -> Err[object]:
    return Err(
        DomainError(
            code=DomainErrorCode.NOT_FOUND,
            message=f"no {kind} {identifier!r} in content.db",
        )
    )


class ContentStore:
    """The runtime read face over one built content.db (read-only).

    The instance owns the only connection it ever uses and that connection is
    opened through :func:`open_read_only`: a ContentStore cannot be handed a
    writable connection, so "任何写入尝试必须被拒" holds for every instance
    rather than for the callers who remember to open it read-only.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn = open_read_only(self._db_path)
        try:
            self._check_schema()
        except BaseException:
            self._conn.close()
            raise

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ContentStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _check_schema(self) -> None:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        present = {row[0] for row in rows}
        missing = [table for table in _REQUIRED_TABLES if table not in present]
        if missing:
            raise ContentStoreError(
                f"content.db lacks the built schema (missing tables: {missing}); "
                "rebuild it with elc.content.build"
            )

    # -- artifact metadata (docs/DATA_MODEL.md §26.1) ----------------------

    def content_version(self) -> Result[ContentVersion]:
        version = self._meta(_CONTENT_VERSION_KEY)
        if isinstance(version, Err):
            return version
        return Ok(ContentVersion(version.value))

    def curriculum_version(self) -> Result[CurriculumVersion]:
        version = self._meta(_CURRICULUM_VERSION_KEY)
        if isinstance(version, Err):
            return version
        return Ok(CurriculumVersion(version.value))

    def _meta(self, key: str) -> Result[str]:
        row = self._conn.execute(
            "SELECT value FROM content_meta WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return _not_found("metadata key", key)
        return Ok(str(row[0]))

    # -- identity sets (stable across rebuilds) ----------------------------

    def entity_ids(self) -> Result[tuple[str, ...]]:
        return Ok(self._ids("SELECT entity_id FROM content_entity"))

    def capability_ids(self) -> Result[tuple[str, ...]]:
        return Ok(self._ids("SELECT capability_id FROM curriculum_capability"))

    def _ids(self, statement: str) -> tuple[str, ...]:
        rows = self._conn.execute(statement).fetchall()
        return tuple(str(row[0]) for row in rows)

    def _exists(self, statement: str, identifier: str) -> bool:
        return self._conn.execute(statement, (identifier,)).fetchone() is not None

    # -- content face ------------------------------------------------------

    def get_resource(self, entity_id: str) -> Result[ContentResourceView]:
        """One §24.1 entity row (the seven canonical columns)."""

        # §24.1's seven columns, spelled out literally (no identifier assembly).
        row = self._conn.execute(
            "SELECT entity_id, entity_type, language, lifecycle_status, "
            "entity_revision, created_in_version, updated_in_version "
            "FROM content_entity WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return _not_found("content entity", entity_id)
        return Ok(
            ContentResourceView(
                entity_id=str(row[0]),
                entity_type=str(row[1]),
                language=str(row[2]),
                lifecycle_status=str(row[3]),
                entity_revision=int(row[4]),
                created_in_version=str(row[5]),
                updated_in_version=str(row[6]),
            )
        )

    def get_expression(self, entity_id: str) -> Result[ContentExpressionView]:
        row = self._conn.execute(
            "SELECT entity_id, expression_type, fixedness, recognition_policy "
            "FROM content_expression WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return _not_found("content expression", entity_id)
        return Ok(
            ContentExpressionView(
                entity_id=str(row[0]),
                expression_type=str(row[1]),
                fixedness=str(row[2]),
                recognition_policy=str(row[3]),
            )
        )

    def get_target(self, entity_id: str) -> Result[ContentTargetView]:
        row = self._conn.execute(
            "SELECT entity_id, target_type, target_mode, learning_intent, "
            "evidence_modality FROM content_target WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            return _not_found("content target", entity_id)
        return Ok(
            ContentTargetView(
                entity_id=str(row[0]),
                target_type=str(row[1]),
                target_mode=str(row[2]),
                learning_intent=str(row[3]),
                evidence_modality=str(row[4]),
            )
        )

    def get_teaching_content(self, entity_id: str) -> Result[ContentTeachingView]:
        """The migrated P3-1B payload, reassembled in authored order."""

        reveal_row = self._conn.execute(
            "SELECT reveal_form FROM content_teaching WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        if reveal_row is None:
            return _not_found("content teaching payload", entity_id)
        hint_ladder = tuple(
            str(row[0])
            for row in self._conn.execute(
                "SELECT rung FROM content_hint_rung WHERE entity_id = ? "
                "ORDER BY ordinal",
                (entity_id,),
            ).fetchall()
        )
        canonical_forms = self._forms(entity_id, ExampleLinkRole.PRIMARY_TARGET)
        alternative_realizations = self._forms(
            entity_id, ExampleLinkRole.SUPPORTING
        )
        required_slots = self._slots(entity_id)
        linkage = self._primary_realization_node(entity_id)
        return Ok(
            ContentTeachingView(
                entity_id=entity_id,
                hint_ladder=hint_ladder,
                reveal_form=str(reveal_row[0]),
                canonical_forms=canonical_forms,
                alternative_realizations=alternative_realizations,
                required_slots=required_slots,
                capability_linkage=linkage,
            )
        )

    def _forms(self, entity_id: str, role: ExampleLinkRole) -> tuple[str, ...]:
        """The §24.5 example rows in one role, in authored order."""

        rows = self._conn.execute(
            "SELECT form FROM content_example WHERE entity_id = ? AND role = ? "
            "ORDER BY ordinal",
            (entity_id, str(role)),
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def get_examples(
        self, entity_id: str, role: ExampleLinkRole | str
    ) -> Result[tuple[str, ...]]:
        """The §24.5 example rows of one entity in one role, in authored order.

        Added by P5-1 so the readiness ladder can read the §24.5 ``CONTRAST``
        role directly instead of deriving "the target declares a contrast"
        from a constant. An unknown entity id is NOT_FOUND, and a role outside
        the §24.5 vocabulary is VALIDATION_FAILED — never a silent empty
        answer.
        """

        if not self._exists(
            "SELECT 1 FROM content_entity WHERE entity_id = ?", entity_id
        ):
            return _not_found("content entity", entity_id)
        try:
            link_role = ExampleLinkRole(role)
        except ValueError:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"unknown §24.5 example role {role!r}; declared roles "
                        f"are {[str(member) for member in ExampleLinkRole]}"
                    ),
                )
            )
        return Ok(self._forms(entity_id, link_role))

    def _slots(self, entity_id: str) -> tuple[tuple[str, ...], ...]:
        rows = self._conn.execute(
            "SELECT group_ordinal, token FROM content_slot WHERE entity_id = ? "
            "ORDER BY group_ordinal, token_ordinal",
            (entity_id,),
        ).fetchall()
        groups: list[list[str]] = []
        current = -1
        for group_ordinal, token in rows:
            if int(group_ordinal) != current:
                groups.append([])
                current = int(group_ordinal)
            groups[-1].append(str(token))
        return tuple(tuple(group) for group in groups)

    def _primary_realization_node(self, entity_id: str) -> str | None:
        """The primary REALIZES node this entity's teaching payload may
        credit — **only when the §24.7 link is author-approved** (P5-R).

        The returned id is what the teaching chain turns into a
        CAPABILITY/POSITIVE claim on an ``ALTERNATIVE_SUCCESS`` attempt
        (elc.learning.teaching_evidence §5 fold), so the read is gated on
        :data:`CAPABILITY_CREDIT_EDITORIAL_STATUS`: **an unapproved link never
        enters capability credit**. A ``CURRICULUM_MAPPED`` (or otherwise
        unapproved) row stays fully readable through
        :meth:`curriculum_links_of` — excluded from credit, never deleted —
        and this method answers ``None`` for it, exactly as it does for an
        entity with no link at all.
        """

        rows = self._conn.execute(
            "SELECT node_id FROM curriculum_link WHERE resource_id = ? "
            "AND relation = ? AND primary_flag = 1 AND editorial_status = ? "
            "ORDER BY node_id",
            (
                entity_id,
                str(CurriculumLinkRelation.REALIZES),
                CAPABILITY_CREDIT_EDITORIAL_STATUS,
            ),
        ).fetchall()
        if len(rows) > 1:
            # The build refuses this source; a stored copy that has it is not a
            # content.db this reader answers from (reject, never pick one).
            raise ContentStoreError(
                f"{entity_id!r} declares more than one primary REALIZES link"
            )
        return None if not rows else str(rows[0][0])

    # -- the §8.1 readiness evidence face (C1) ------------------------------

    def evidence_counts(self, entity_id: str) -> Result[ContentEvidenceCounts]:
        """The §8.1 evidence this entity carries (C1).

        An unknown entity id is NOT_FOUND — readiness is judged for declared
        entities, and "not in the registry" is never reported as "no
        evidence". A known entity with no evidence document answers zeros.
        """

        if not self._exists(
            "SELECT 1 FROM content_entity WHERE entity_id = ?", entity_id
        ):
            return _not_found("content entity", entity_id)
        conn = self._conn
        return Ok(
            ContentEvidenceCounts(
                assessment_memberships=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_assessment_membership "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                lexical_entries=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_lexical_entry "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                senses=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_sense WHERE entity_id = ?",
                    entity_id,
                ),
                definitions=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_text WHERE entity_id = ? "
                    "AND role = 'definition'",
                    entity_id,
                ),
                forms=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_form WHERE entity_id = ?",
                    entity_id,
                ),
                pedagogical_profiles=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_pedagogical_profile "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                pack_overlays=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_pack_overlay "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                resource_labels=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_resource_label "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                labelled_usage_modalities=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_resource_label "
                    "WHERE entity_id = ? "
                    "AND usage_modality IS NOT NULL AND usage_modality <> ''",
                    entity_id,
                ),
                example_policies=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_example_policy "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                teaching_notes=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_text WHERE entity_id = ? "
                    "AND role = 'teaching_note'",
                    entity_id,
                ),
                typical_errors=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_typical_error "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                detection_policies=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_detection_policy "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                detection_rules=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_detection_rule "
                    "WHERE entity_id = ?",
                    entity_id,
                ),
                negative_fixtures=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_detection_fixture "
                    "WHERE entity_id = ? AND kind = 'NEGATIVE'",
                    entity_id,
                ),
                false_positive_boundaries=_count_one(
                    conn,
                    "SELECT COUNT(*) FROM content_detection_fixture "
                    "WHERE entity_id = ? AND kind = 'FALSE_POSITIVE_BOUNDARY'",
                    entity_id,
                ),
            )
        )

    def typical_error_required(self, entity_id: str) -> Result[bool]:
        """Did the source declare that this entity needs a §24.9 TypicalError?

        This is §8.1 R3's "以及需要时" condition: the *need* is an authoring
        declaration, so it is carried as a declared-reading ``content_meta``
        key (:func:`elc.content.types.typical_error_required_key`) written by
        the build from the source's own words — a source that declares the
        need before the error is written is built, and the ladder reports the
        gap (readiness is a report, never a build-time refusal).

        **Absent means False**: a source that declares nothing has not
        triggered §8.1's condition, which is what the ladder's
        ``ReadinessFacts.typical_error_required`` default reads. The key is
        per entity and carries no FK, so the entity is checked here the way
        every other read checks it (an undeclared id is NOT_FOUND, never a
        silent False), and a value the build cannot write is refused rather
        than guessed.
        """

        if not self._exists(
            "SELECT 1 FROM content_entity WHERE entity_id = ?", entity_id
        ):
            return _not_found("content entity", entity_id)
        key = typical_error_required_key(entity_id)
        stored = self._meta(key)
        if isinstance(stored, Err):
            return Ok(False)
        if stored.value == "true":
            return Ok(True)
        if stored.value == "false":
            return Ok(False)
        raise ContentStoreError(
            f"content_meta[{key!r}] carries {stored.value!r}; the build writes"
            " only 'true' or 'false'"
        )

    # -- curriculum registry face ------------------------------------------

    def get_capability(self, capability_id: str) -> Result[CapabilityNodeRecord]:
        """One §7 capability registry node."""

        row = self._conn.execute(
            "SELECT curriculum_node_id, capability_id, family, level "
            "FROM curriculum_capability WHERE capability_id = ?",
            (capability_id,),
        ).fetchone()
        if row is None:
            return _not_found("capability", capability_id)
        return Ok(
            CapabilityNodeRecord(
                curriculum_node_id=CurriculumNodeId(str(row[0])),
                capability_id=CapabilityId(str(row[1])),
                family=CapabilityFamily(str(row[2])),
                level=int(row[3]),
            )
        )

    def curriculum_links_of(
        self, resource_id: str
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        """Every CurriculumLink whose ``resource_id`` is this entity.

        An unknown resource id is rejected; a known resource with no link
        answers the empty tuple (that is a declared state, not an error).
        """

        if not self._exists(
            "SELECT 1 FROM content_entity WHERE entity_id = ?", resource_id
        ):
            return _not_found("content entity", resource_id)
        return Ok(self._links("resource_id", resource_id))

    def curriculum_links_to(
        self, node_id: str
    ) -> Result[tuple[CurriculumLinkRecord, ...]]:
        """Every CurriculumLink pointing at this curriculum node."""

        if not self._exists(
            "SELECT 1 FROM curriculum_capability WHERE capability_id = ?", node_id
        ):
            return _not_found("capability", node_id)
        return Ok(self._links("node_id", node_id))

    def _links(self, column: str, identifier: str) -> tuple[CurriculumLinkRecord, ...]:
        # `column` is one of two literals chosen by the caller's method, never
        # caller input: the two statements are written out below.
        if column == "resource_id":
            rows = self._conn.execute(
                "SELECT resource_id, node_id, relation, strength, primary_flag, "
                "editorial_status, rationale FROM curriculum_link "
                "WHERE resource_id = ? "
                "ORDER BY node_id, relation",
                (identifier,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT resource_id, node_id, relation, strength, primary_flag, "
                "editorial_status, rationale FROM curriculum_link WHERE node_id = ? "
                "ORDER BY resource_id, relation",
                (identifier,),
            ).fetchall()
        return tuple(self._link(row) for row in rows)

    @staticmethod
    def _link(row: tuple[object, ...]) -> CurriculumLinkRecord:
        return CurriculumLinkRecord(
            resource_id=ResourceId(str(row[0])),
            node_id=CurriculumNodeId(str(row[1])),
            relation=CurriculumLinkRelation(str(row[2])),
            strength=None if row[3] is None else str(row[3]),
            primary_flag=bool(row[4]),
            editorial_status=str(row[5]),
            rationale=str(row[6]),
        )

    def prerequisites_of(
        self, node_id: str
    ) -> Result[tuple[CurriculumEdgeRecord, ...]]:
        """The prerequisite edges declared for this curriculum node."""

        if not self._exists(
            "SELECT 1 FROM curriculum_capability WHERE capability_id = ?", node_id
        ):
            return _not_found("capability", node_id)
        rows = self._conn.execute(
            "SELECT from_node, to_node, edge_type, prerequisite_strength "
            "FROM curriculum_prerequisite WHERE from_node = ? OR to_node = ? "
            "ORDER BY from_node, to_node, edge_type",
            (node_id, node_id),
        ).fetchall()
        edges: list[CurriculumEdgeRecord] = []
        for row in rows:
            edges.append(
                CurriculumEdgeRecord(
                    from_node=CurriculumNodeId(str(row[0])),
                    to_node=CurriculumNodeId(str(row[1])),
                    edge_type=CurriculumEdgeType(str(row[2])),
                    prerequisite_strength=(
                        None
                        if row[3] is None
                        else PrerequisiteStrength(str(row[3]))
                    ),
                )
            )
        return Ok(tuple(edges))
