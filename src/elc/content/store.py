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
from pathlib import Path

from elc.content.queries import (
    ContentExpressionView,
    ContentResourceView,
    ContentTargetView,
    ContentTeachingView,
)
from elc.content.types import ExampleLinkRole
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

__all__ = ["ContentStore", "ContentStoreError", "open_read_only"]

#: docs/DATA_MODEL.md §26.1 metadata keys carried by the artifact.
_CONTENT_VERSION_KEY = "content_version"
_CURRICULUM_VERSION_KEY = "curriculum_version"


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
)


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
        rows = self._conn.execute(
            "SELECT node_id FROM curriculum_link WHERE resource_id = ? "
            "AND relation = ? AND primary_flag = 1 ORDER BY node_id",
            (entity_id, str(CurriculumLinkRelation.REALIZES)),
        ).fetchall()
        if len(rows) > 1:
            # The build refuses this source; a stored copy that has it is not a
            # content.db this reader answers from (reject, never pick one).
            raise ContentStoreError(
                f"{entity_id!r} declares more than one primary REALIZES link"
            )
        return None if not rows else str(rows[0][0])

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
