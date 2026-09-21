"""content.db build step — `content_src/*` + `curriculum/*` → content.db.

docs/DATA_MODEL.md §1.1: `content_src → content.db build artifact`;
§2: `content.db` is a read-only, versioned canonical content runtime build;
§24: `content_src/*` and `curriculum/*` are the authoring source of truth,
"`content.db` 是 generated runtime artifact，不手改".

Contract of this module (P5-0, TASK-OPI-4d516e4f-….38 ②):

- deterministic: rows are written in id order, never in filesystem or index
  order; no wall clock, random or environment value reaches the artifact, so
  two builds from one source produce the same id set and the same bytes;
- idempotent: rebuilding over an existing file replaces it atomically
  (temp file + os.replace); a second run is a byte-for-byte replay;
- reject, never degrade: a missing index entry, an unlisted file, an unknown
  vocabulary value, a dangling reference or a malformed document raises
  :class:`BuildError` and no output is produced — nothing is skipped
  silently (the source-layout rules are declared in `content_src/README.md`
  and `curriculum/README.md`).

The artifact's own schema is owned here (`content_db_version`, §26.1); it is
NOT a migration: app.db migrations live in `migrations/` and content.db is a
generated artifact, so no migration is needed or added by P5-0.

The runtime reads this file only through :mod:`elc.content.store` (read-only
URI connection); the write face of this module is build-time only.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from elc.content.types import (
    CONTENT_ENTITY_COLUMNS,
    LEARNING_INTENTS,
    LIFECYCLE_STATUSES,
    TARGET_MODES,
    TARGET_TYPES,
    ContentType,
    ExampleLinkRole,
    ExpressionFixedness,
    ExpressionSubtype,
    RecognitionPolicy,
)
from elc.curriculum.types import (
    CapabilityFamily,
    CurriculumEdgeType,
    CurriculumLinkRelation,
    PrerequisiteStrength,
)
from elc.platform.types import EvidenceModality

__all__ = [
    "CONTENT_DB_VERSION",
    "CONTENT_SRC_DIR",
    "CURRICULUM_DIR",
    "DEFAULT_OUTPUT",
    "BuildError",
    "BuildReport",
    "ContentSource",
    "build_content_db",
    "load_source",
    "main",
]

#: Repository root (this file lives at src/elc/content/build.py).
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Authoring source of truth (docs/DATA_MODEL.md §24).
CONTENT_SRC_DIR = REPO_ROOT / "content_src"
CURRICULUM_DIR = REPO_ROOT / "curriculum"

#: Default build target. `*.db` is gitignored: content.db is a generated
#: artifact, never a committed file (docs/DATA_MODEL.md §2).
DEFAULT_OUTPUT = REPO_ROOT / "build" / "content.db"

#: docs/DATA_MODEL.md §26.1 `content_db_version` — the artifact's own schema
#: generation, owned by this module's DDL below.
CONTENT_DB_VERSION = "1"

#: The authoring-source formats this build reads. A document that declares a
#: different `format` / `format_version` is refused: the build may only read a
#: source layout it was written against, never guess at one.
CONTENT_SRC_FORMAT = "elc.content_src"
CURRICULUM_SRC_FORMAT = "elc.curriculum_src"
CURRICULUM_LINKS_FORMAT = "elc.curriculum_links"
CURRICULUM_PREREQUISITES_FORMAT = "elc.curriculum_prerequisites"
SOURCE_FORMAT_VERSION = 1

#: §24.7 / §13 link relations accepted by the build (from the canonical
#: enum, listed here so a bad value names the legal set in the error).
_LINK_RELATIONS = tuple(CurriculumLinkRelation)

_ENTITY_KEYS = ("entity", "expression", "target", "teaching_content")
_ENTITY_BLOCK_KEYS = CONTENT_ENTITY_COLUMNS
_EXPRESSION_KEYS = ("expression_type", "fixedness", "recognition_policy")
_TARGET_KEYS = (
    "target_type",
    "target_mode",
    "learning_intent",
    "evidence_modality",
)
_TEACHING_KEYS = (
    "hint_ladder",
    "reveal_form",
    "canonical_forms",
    "alternative_realizations",
    "required_slots",
)
_CAPABILITY_KEYS = ("curriculum_node_id", "capability_id", "family", "level")
_LINK_KEYS = (
    "resource_id",
    "node_id",
    "relation",
    "strength",
    "primary_flag",
    "editorial_status",
    "rationale",
)
_PREREQUISITE_KEYS = (
    "from_node",
    "to_node",
    "edge_type",
    "prerequisite_strength",
)

#: Deterministic DDL: creation order is part of the artifact's bytes.
SCHEMA_STATEMENTS: tuple[str, ...] = (
    "CREATE TABLE content_meta ("
    "key TEXT PRIMARY KEY,"
    "value TEXT NOT NULL"
    ")",
    "CREATE TABLE content_entity ("
    "entity_id TEXT PRIMARY KEY,"
    "entity_type TEXT NOT NULL,"
    "language TEXT NOT NULL,"
    "lifecycle_status TEXT NOT NULL,"
    "entity_revision INTEGER NOT NULL,"
    "created_in_version TEXT NOT NULL,"
    "updated_in_version TEXT NOT NULL"
    ")",
    "CREATE TABLE content_expression ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "expression_type TEXT NOT NULL,"
    "fixedness TEXT NOT NULL,"
    "recognition_policy TEXT NOT NULL"
    ")",
    "CREATE TABLE content_target ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "target_type TEXT NOT NULL,"
    "target_mode TEXT NOT NULL,"
    "learning_intent TEXT NOT NULL,"
    "evidence_modality TEXT NOT NULL"
    ")",
    "CREATE TABLE content_teaching ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "reveal_form TEXT NOT NULL"
    ")",
    "CREATE TABLE content_hint_rung ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "ordinal INTEGER NOT NULL,"
    "rung TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, ordinal)"
    ")",
    # §24.5 Example/ExampleLink: the target's example sentences, linked with
    # the canonical role vocabulary. Deliberately not named `content_form` —
    # §24.2's `Form` is a different canonical concept (word forms).
    "CREATE TABLE content_example ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "role TEXT NOT NULL,"
    "ordinal INTEGER NOT NULL,"
    "form TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, role, ordinal)"
    ")",
    "CREATE TABLE content_slot ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "group_ordinal INTEGER NOT NULL,"
    "token_ordinal INTEGER NOT NULL,"
    "token TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, group_ordinal, token_ordinal)"
    ")",
    "CREATE TABLE curriculum_capability ("
    "capability_id TEXT PRIMARY KEY,"
    "curriculum_node_id TEXT NOT NULL,"
    "family TEXT NOT NULL,"
    "level INTEGER NOT NULL"
    ")",
    "CREATE TABLE curriculum_link ("
    "resource_id TEXT NOT NULL,"
    "node_id TEXT NOT NULL,"
    "relation TEXT NOT NULL,"
    "strength TEXT,"
    "primary_flag INTEGER NOT NULL,"
    "editorial_status TEXT NOT NULL,"
    "rationale TEXT NOT NULL,"
    "PRIMARY KEY (resource_id, node_id, relation)"
    ")",
    "CREATE TABLE curriculum_prerequisite ("
    "from_node TEXT NOT NULL,"
    "to_node TEXT NOT NULL,"
    "edge_type TEXT NOT NULL,"
    "prerequisite_strength TEXT,"
    "PRIMARY KEY (from_node, to_node, edge_type)"
    ")",
)


class BuildError(RuntimeError):
    """The authoring source is missing, malformed or internally inconsistent.

    Raised for every rejection path; the build never degrades into a partial
    artifact (no silent skip, no defaulted vocabulary)."""


# ---------------------------------------------------------------------------
# Source documents
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityDoc:
    """One authoring entity document, validated against §24 vocabularies."""

    entity_id: str
    entity_type: ContentType
    language: str
    lifecycle_status: str
    entity_revision: int
    created_in_version: str
    updated_in_version: str
    expression_type: ExpressionSubtype
    fixedness: ExpressionFixedness
    recognition_policy: RecognitionPolicy
    target_type: str
    target_mode: str
    learning_intent: str
    evidence_modality: str
    hint_ladder: tuple[str, ...]
    reveal_form: str
    canonical_forms: tuple[str, ...]
    alternative_realizations: tuple[str, ...]
    required_slots: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class CapabilityDoc:
    """One capability registry node (docs/DOMAIN_MODEL.md §7)."""

    curriculum_node_id: str
    capability_id: str
    family: CapabilityFamily
    level: int


@dataclass(frozen=True)
class LinkRow:
    """One CurriculumLink (docs/DATA_MODEL.md §24.7 seven columns)."""

    resource_id: str
    node_id: str
    relation: CurriculumLinkRelation
    strength: str | None
    primary_flag: bool
    editorial_status: str
    rationale: str


@dataclass(frozen=True)
class PrerequisiteRow:
    """One prerequisite edge (docs/DOMAIN_MODEL.md §7)."""

    from_node: str
    to_node: str
    edge_type: CurriculumEdgeType
    prerequisite_strength: str | None


@dataclass(frozen=True)
class ContentSource:
    """The validated authoring source: both domains, ready to be written."""

    content_version: str
    curriculum_version: str
    language: str
    entities: tuple[EntityDoc, ...]
    capabilities: tuple[CapabilityDoc, ...]
    links: tuple[LinkRow, ...]
    prerequisites: tuple[PrerequisiteRow, ...]

    def entity_ids(self) -> tuple[str, ...]:
        return tuple(entity.entity_id for entity in self.entities)

    def capability_ids(self) -> tuple[str, ...]:
        return tuple(capability.capability_id for capability in self.capabilities)


@dataclass(frozen=True)
class BuildReport:
    """What one build wrote (counts are post-validation, not attempted)."""

    output_path: Path
    content_version: str
    curriculum_version: str
    entity_count: int
    capability_count: int
    link_count: int
    prerequisite_count: int


# ---------------------------------------------------------------------------
# Strict document readers (every rejection path raises BuildError)
# ---------------------------------------------------------------------------


def _format_declaration(
    document: Mapping[str, Any], expected_format: str, where: str
) -> None:
    """The document must declare the exact format and version this build reads."""

    declared = _string(document, "format", where)
    if declared != expected_format:
        raise BuildError(
            f"{where}: unexpected format {declared!r} "
            f"(this build reads {expected_format!r})"
        )
    declared_version = document["format_version"]
    if (
        isinstance(declared_version, bool)
        or not isinstance(declared_version, int)
        or declared_version != SOURCE_FORMAT_VERSION
    ):
        raise BuildError(
            f"{where}: unexpected format_version {declared_version!r} "
            f"(this build reads {SOURCE_FORMAT_VERSION})"
        )


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise BuildError(f"source document missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(
            f"source document is not valid JSON: {path}: {exc}"
        ) from exc


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise BuildError(f"{where}: expected a JSON object")
    for key in value:
        if not isinstance(key, str):
            raise BuildError(f"{where}: non-string key in JSON object")
    return value


def _exact_keys(
    mapping: Mapping[str, Any], expected: Sequence[str], where: str
) -> None:
    expected_set = set(expected)
    actual = set(mapping)
    missing = sorted(expected_set - actual)
    unknown = sorted(actual - expected_set)
    if missing or unknown:
        raise BuildError(
            f"{where}: key mismatch (missing={missing}, unknown={unknown}); "
            f"declared keys are {list(expected)}"
        )


def _string(mapping: Mapping[str, Any], key: str, where: str) -> str:
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise BuildError(f"{where}.{key}: expected a non-empty string")
    return value


def _string_list(
    mapping: Mapping[str, Any], key: str, where: str
) -> tuple[str, ...]:
    value = mapping[key]
    if not isinstance(value, list):
        raise BuildError(f"{where}.{key}: expected a JSON array")
    return tuple(
        _list_string(item, f"{where}.{key}[{index}]")
        for index, item in enumerate(value)
    )


def _list_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise BuildError(f"{where}: expected a non-empty string")
    return value


def _slot_groups(
    mapping: Mapping[str, Any], key: str, where: str
) -> tuple[tuple[str, ...], ...]:
    value = mapping[key]
    if not isinstance(value, list) or not value:
        raise BuildError(
            f"{where}.{key}: expected a non-empty JSON array of groups"
        )
    groups: list[tuple[str, ...]] = []
    for index, group in enumerate(value):
        if not isinstance(group, list) or not group:
            raise BuildError(
                f"{where}.{key}[{index}]: expected a non-empty array of tokens"
            )
        groups.append(
            tuple(
                _list_string(token, f"{where}.{key}[{index}][{token_index}]")
                for token_index, token in enumerate(group)
            )
        )
    return tuple(groups)


def _vocabulary(value: str, allowed: Sequence[str], where: str) -> str:
    if value not in allowed:
        raise BuildError(
            f"{where}: {value!r} is outside the canonical set {list(allowed)}"
        )
    return value


def _integer(mapping: Mapping[str, Any], key: str, where: str) -> int:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise BuildError(f"{where}.{key}: expected an integer")
    return value


def _boolean(mapping: Mapping[str, Any], key: str, where: str) -> bool:
    value = mapping[key]
    if not isinstance(value, bool):
        raise BuildError(f"{where}.{key}: expected a JSON boolean")
    return value


def _optional_string(
    mapping: Mapping[str, Any], key: str, where: str
) -> str | None:
    value = mapping[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise BuildError(f"{where}.{key}: expected null or a non-empty string")
    return value


def _document_list(
    index_path: Path,
    index: Mapping[str, Any],
    key: str,
    base_dir: Path,
    directory: Path,
) -> list[Path]:
    """The document list an index declares, with the no-silent-skip checks.

    Index entries are relative to the authoring tree root (``base_dir``);
    ``directory`` is that tree's document directory. Every listed path must
    exist, no path may repeat, and any ``*.json`` present in ``directory`` but
    unlisted is an error — a file the build would otherwise ignore silently.
    """

    raw = index[key]
    if not isinstance(raw, list) or not raw:
        raise BuildError(f"{index_path}: {key!r} must be a non-empty JSON array")
    listed: list[Path] = []
    for entry in raw:
        if not isinstance(entry, str) or not entry:
            raise BuildError(
                f"{index_path}: {key!r} entries must be non-empty strings"
            )
        path = base_dir / entry
        if not path.is_file():
            raise BuildError(f"{index_path}: listed document does not exist: {path}")
        listed.append(path)
    if len(set(listed)) != len(listed):
        raise BuildError(f"{index_path}: {key!r} lists the same document twice")
    on_disk = sorted(directory.rglob("*.json"))
    unlisted = sorted(set(on_disk) - set(listed))
    if unlisted:
        raise BuildError(
            f"{index_path}: documents present but not listed in {key!r} "
            f"(refusing to skip silently): {[str(path) for path in unlisted]}"
        )
    return listed


def _check_tree_root(tree: Path, allowed: Sequence[str], index_path: Path) -> None:
    """No document may sit in the authoring tree root unaccounted for.

    The index names every document the build reads; a stray ``*.json`` in the
    tree root would be read by nobody, so it is refused rather than ignored.
    """

    present = {path.name for path in tree.glob("*.json")}
    unlisted = sorted(present - set(allowed))
    if unlisted:
        raise BuildError(
            f"{index_path}: documents present in {tree} but not declared by the "
            f"index (refusing to skip silently): {unlisted}"
        )


def _entity_from_document(path: Path, document: Mapping[str, Any]) -> EntityDoc:
    where = str(path)
    _exact_keys(document, _ENTITY_KEYS, where)

    entity = _mapping(document["entity"], f"{where}.entity")
    _exact_keys(entity, _ENTITY_BLOCK_KEYS, f"{where}.entity")
    entity_id = _string(entity, "entity_id", f"{where}.entity")
    if path.name != f"{entity_id}.json":
        raise BuildError(
            f"{where}: file name must be '{entity_id}.json' (entity_id and "
            "document name drifted)"
        )
    entity_type = ContentType(
        _vocabulary(
            _string(entity, "entity_type", f"{where}.entity"),
            tuple(str(member) for member in ContentType),
            f"{where}.entity.entity_type",
        )
    )
    language = _string(entity, "language", f"{where}.entity")
    lifecycle_status = _vocabulary(
        _string(entity, "lifecycle_status", f"{where}.entity"),
        LIFECYCLE_STATUSES,
        f"{where}.entity.lifecycle_status",
    )
    entity_revision = _integer(entity, "entity_revision", f"{where}.entity")
    if entity_revision < 1:
        raise BuildError(f"{where}.entity.entity_revision: must be >= 1")
    created_in_version = _string(entity, "created_in_version", f"{where}.entity")
    updated_in_version = _string(entity, "updated_in_version", f"{where}.entity")

    expression = _mapping(document["expression"], f"{where}.expression")
    _exact_keys(expression, _EXPRESSION_KEYS, f"{where}.expression")
    expression_type = ExpressionSubtype(
        _vocabulary(
            _string(expression, "expression_type", f"{where}.expression"),
            tuple(str(member) for member in ExpressionSubtype),
            f"{where}.expression.expression_type",
        )
    )
    fixedness = ExpressionFixedness(
        _vocabulary(
            _string(expression, "fixedness", f"{where}.expression"),
            tuple(str(member) for member in ExpressionFixedness),
            f"{where}.expression.fixedness",
        )
    )
    recognition_policy = RecognitionPolicy(
        _vocabulary(
            _string(expression, "recognition_policy", f"{where}.expression"),
            tuple(str(member) for member in RecognitionPolicy),
            f"{where}.expression.recognition_policy",
        )
    )

    target = _mapping(document["target"], f"{where}.target")
    _exact_keys(target, _TARGET_KEYS, f"{where}.target")
    target_type = _vocabulary(
        _string(target, "target_type", f"{where}.target"),
        TARGET_TYPES,
        f"{where}.target.target_type",
    )
    target_mode = _vocabulary(
        _string(target, "target_mode", f"{where}.target"),
        TARGET_MODES,
        f"{where}.target.target_mode",
    )
    learning_intent = _vocabulary(
        _string(target, "learning_intent", f"{where}.target"),
        LEARNING_INTENTS,
        f"{where}.target.learning_intent",
    )
    evidence_modality = _vocabulary(
        _string(target, "evidence_modality", f"{where}.target"),
        tuple(str(member) for member in EvidenceModality),
        f"{where}.target.evidence_modality",
    )

    teaching = _mapping(document["teaching_content"], f"{where}.teaching_content")
    _exact_keys(teaching, _TEACHING_KEYS, f"{where}.teaching_content")
    hint_ladder = _string_list(teaching, "hint_ladder", f"{where}.teaching_content")
    reveal_form = _string(teaching, "reveal_form", f"{where}.teaching_content")
    canonical_forms = _string_list(
        teaching, "canonical_forms", f"{where}.teaching_content"
    )
    alternative_realizations = _string_list(
        teaching, "alternative_realizations", f"{where}.teaching_content"
    )
    required_slots = _slot_groups(
        teaching, "required_slots", f"{where}.teaching_content"
    )
    if reveal_form not in canonical_forms:
        raise BuildError(
            f"{where}.teaching_content.reveal_form: {reveal_form!r} is not one of "
            "the canonical_forms"
        )

    return EntityDoc(
        entity_id=entity_id,
        entity_type=entity_type,
        language=language,
        lifecycle_status=lifecycle_status,
        entity_revision=entity_revision,
        created_in_version=created_in_version,
        updated_in_version=updated_in_version,
        expression_type=expression_type,
        fixedness=fixedness,
        recognition_policy=recognition_policy,
        target_type=target_type,
        target_mode=target_mode,
        learning_intent=learning_intent,
        evidence_modality=evidence_modality,
        hint_ladder=hint_ladder,
        reveal_form=reveal_form,
        canonical_forms=canonical_forms,
        alternative_realizations=alternative_realizations,
        required_slots=required_slots,
    )


def _capability_from_document(
    path: Path, document: Mapping[str, Any]
) -> CapabilityDoc:
    where = str(path)
    _exact_keys(document, _CAPABILITY_KEYS, where)
    curriculum_node_id = _string(document, "curriculum_node_id", where)
    capability_id = _string(document, "capability_id", where)
    if path.name != f"{capability_id}.json":
        raise BuildError(
            f"{where}: file name must be '{capability_id}.json' (capability_id "
            "and document name drifted)"
        )
    if curriculum_node_id != capability_id:
        raise BuildError(
            f"{where}: the V1 registry is one capability = one node and the node "
            "id is the capability id (declared in curriculum/README.md); got "
            f"curriculum_node_id={curriculum_node_id!r} capability_id="
            f"{capability_id!r}"
        )
    family = CapabilityFamily(
        _vocabulary(
            _string(document, "family", where),
            tuple(str(member) for member in CapabilityFamily),
            f"{where}.family",
        )
    )
    level = _integer(document, "level", where)
    if level < 1:
        raise BuildError(f"{where}.level: must be >= 1")
    return CapabilityDoc(
        curriculum_node_id=curriculum_node_id,
        capability_id=capability_id,
        family=family,
        level=level,
    )


def _links_from_document(
    path: Path, document: Mapping[str, Any]
) -> tuple[LinkRow, ...]:
    where = str(path)
    _exact_keys(document, ("format", "format_version", "links"), where)
    _format_declaration(document, CURRICULUM_LINKS_FORMAT, where)
    raw = document["links"]
    if not isinstance(raw, list):
        raise BuildError(f"{where}.links: expected a JSON array")
    rows: list[LinkRow] = []
    for index, item in enumerate(raw):
        item_where = f"{where}.links[{index}]"
        row = _mapping(item, item_where)
        _exact_keys(row, _LINK_KEYS, item_where)
        relation = CurriculumLinkRelation(
            _vocabulary(
                _string(row, "relation", item_where),
                [str(member) for member in _LINK_RELATIONS],
                f"{item_where}.relation",
            )
        )
        strength = _optional_string(row, "strength", item_where)
        if strength is not None:
            _vocabulary(
                strength,
                tuple(str(member) for member in PrerequisiteStrength),
                f"{item_where}.strength",
            )
        rows.append(
            LinkRow(
                resource_id=_string(row, "resource_id", item_where),
                node_id=_string(row, "node_id", item_where),
                relation=relation,
                strength=strength,
                primary_flag=_boolean(row, "primary_flag", item_where),
                editorial_status=_vocabulary(
                    _string(row, "editorial_status", item_where),
                    LIFECYCLE_STATUSES,
                    f"{item_where}.editorial_status",
                ),
                rationale=_string(row, "rationale", item_where),
            )
        )
    return tuple(rows)


def _prerequisites_from_document(
    path: Path, document: Mapping[str, Any]
) -> tuple[PrerequisiteRow, ...]:
    where = str(path)
    _exact_keys(document, ("format", "format_version", "edges"), where)
    _format_declaration(document, CURRICULUM_PREREQUISITES_FORMAT, where)
    raw = document["edges"]
    if not isinstance(raw, list):
        raise BuildError(f"{where}.edges: expected a JSON array")
    rows: list[PrerequisiteRow] = []
    for index, item in enumerate(raw):
        item_where = f"{where}.edges[{index}]"
        row = _mapping(item, item_where)
        _exact_keys(row, _PREREQUISITE_KEYS, item_where)
        edge_type = CurriculumEdgeType(
            _vocabulary(
                _string(row, "edge_type", item_where),
                tuple(str(member) for member in CurriculumEdgeType),
                f"{item_where}.edge_type",
            )
        )
        strength = _optional_string(row, "prerequisite_strength", item_where)
        if strength is not None:
            _vocabulary(
                strength,
                tuple(str(member) for member in PrerequisiteStrength),
                f"{item_where}.prerequisite_strength",
            )
        rows.append(
            PrerequisiteRow(
                from_node=_string(row, "from_node", item_where),
                to_node=_string(row, "to_node", item_where),
                edge_type=edge_type,
                prerequisite_strength=strength,
            )
        )
    return tuple(rows)


# ---------------------------------------------------------------------------
# Source loading (deterministic order + referential integrity)
# ---------------------------------------------------------------------------

_CONTENT_INDEX_KEYS = (
    "format",
    "format_version",
    "content_version",
    "language",
    "mapping_rules",
    "entities",
)
_CURRICULUM_INDEX_KEYS = (
    "format",
    "format_version",
    "curriculum_version",
    "mapping_rules",
    "capabilities",
    "links",
    "prerequisites",
)


def load_source(
    content_src_dir: Path = CONTENT_SRC_DIR, curriculum_dir: Path = CURRICULUM_DIR
) -> ContentSource:
    """Read and validate both authoring trees into one sorted source."""

    content_index_path = content_src_dir / "index.json"
    content_index = _mapping(_read_json(content_index_path), str(content_index_path))
    _exact_keys(content_index, _CONTENT_INDEX_KEYS, str(content_index_path))
    _format_declaration(
        content_index, CONTENT_SRC_FORMAT, str(content_index_path)
    )
    content_version = _string(
        content_index, "content_version", str(content_index_path)
    )
    language = _string(content_index, "language", str(content_index_path))
    _check_tree_root(content_src_dir, ("index.json",), content_index_path)
    entity_paths = _document_list(
        content_index_path,
        content_index,
        "entities",
        content_src_dir,
        content_src_dir / "entities",
    )
    entities = tuple(
        sorted(
            (
                _entity_from_document(path, _mapping(_read_json(path), str(path)))
                for path in entity_paths
            ),
            key=lambda entity: entity.entity_id,
        )
    )
    if len({entity.entity_id for entity in entities}) != len(entities):
        raise BuildError(f"{content_src_dir}: duplicate entity_id in the source")
    for entity in entities:
        if entity.language != language:
            raise BuildError(
                f"{content_src_dir}: entity {entity.entity_id!r} declares "
                f"language {entity.language!r} but the index declares "
                f"{language!r}"
            )

    curriculum_index_path = curriculum_dir / "index.json"
    curriculum_index = _mapping(
        _read_json(curriculum_index_path), str(curriculum_index_path)
    )
    _exact_keys(
        curriculum_index, _CURRICULUM_INDEX_KEYS, str(curriculum_index_path)
    )
    _format_declaration(
        curriculum_index, CURRICULUM_SRC_FORMAT, str(curriculum_index_path)
    )
    curriculum_version = _string(
        curriculum_index, "curriculum_version", str(curriculum_index_path)
    )
    _check_tree_root(
        curriculum_dir,
        (
            "index.json",
            str(curriculum_index["links"]),
            str(curriculum_index["prerequisites"]),
        ),
        curriculum_index_path,
    )
    capability_paths = _document_list(
        curriculum_index_path,
        curriculum_index,
        "capabilities",
        curriculum_dir,
        curriculum_dir / "capabilities",
    )
    capabilities = tuple(
        sorted(
            (
                _capability_from_document(
                    path, _mapping(_read_json(path), str(path))
                )
                for path in capability_paths
            ),
            key=lambda capability: capability.capability_id,
        )
    )
    if len({capability.capability_id for capability in capabilities}) != len(
        capabilities
    ):
        raise BuildError(f"{curriculum_dir}: duplicate capability_id in the source")

    links_path = curriculum_dir / str(curriculum_index["links"])
    links_document = _mapping(_read_json(links_path), str(links_path))
    links = tuple(
        sorted(
            _links_from_document(links_path, links_document),
            key=lambda link: (link.resource_id, link.node_id, str(link.relation)),
        )
    )
    link_keys = {
        (link.resource_id, link.node_id, str(link.relation)) for link in links
    }
    if len(link_keys) != len(links):
        raise BuildError(
            f"{links_path}: duplicate (resource_id, node_id, relation) row"
        )

    prerequisites_path = curriculum_dir / str(curriculum_index["prerequisites"])
    prerequisites_document = _mapping(
        _read_json(prerequisites_path), str(prerequisites_path)
    )
    prerequisites = tuple(
        sorted(
            _prerequisites_from_document(
                prerequisites_path, prerequisites_document
            ),
            key=lambda edge: (edge.from_node, edge.to_node, str(edge.edge_type)),
        )
    )

    source = ContentSource(
        content_version=content_version,
        curriculum_version=curriculum_version,
        language=language,
        entities=entities,
        capabilities=capabilities,
        links=links,
        prerequisites=prerequisites,
    )
    _check_references(source, links_path, prerequisites_path)
    return source


def _check_references(
    source: ContentSource, links_path: Path, prerequisites_path: Path
) -> None:
    """Referential integrity: nothing may point outside the declared sets."""

    entity_ids = set(source.entity_ids())
    capability_ids = set(source.capability_ids())
    for link in source.links:
        if link.resource_id not in entity_ids:
            raise BuildError(
                f"{links_path}: resource_id {link.resource_id!r} is not a "
                "declared content entity"
            )
        if link.node_id not in capability_ids:
            raise BuildError(
                f"{links_path}: node_id {link.node_id!r} is not a declared "
                "capability"
            )
    primaries: dict[str, list[str]] = {}
    for link in source.links:
        if link.relation is CurriculumLinkRelation.REALIZES and link.primary_flag:
            primaries.setdefault(link.resource_id, []).append(link.node_id)
    multiple = {key: value for key, value in primaries.items() if len(value) > 1}
    if multiple:
        raise BuildError(
            f"{links_path}: a resource may declare at most one primary REALIZES "
            f"link (content_src/README.md R5); got {multiple}"
        )
    for edge in source.prerequisites:
        for node in (edge.from_node, edge.to_node):
            if node not in capability_ids:
                raise BuildError(
                    f"{prerequisites_path}: node {node!r} is not a declared "
                    "capability"
                )


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------


def _write_rows(conn: sqlite3.Connection, source: ContentSource) -> None:
    conn.executemany(
        "INSERT INTO content_meta (key, value) VALUES (?, ?)",
        (
            ("content_version", source.content_version),
            ("curriculum_version", source.curriculum_version),
            ("content_db_version", CONTENT_DB_VERSION),
        ),
    )
    conn.executemany(
        # §24.1's seven columns, spelled out literally — no identifier assembly.
        "INSERT INTO content_entity ("
        "entity_id, entity_type, language, lifecycle_status, entity_revision, "
        "created_in_version, updated_in_version"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                entity.entity_id,
                str(entity.entity_type),
                entity.language,
                entity.lifecycle_status,
                entity.entity_revision,
                entity.created_in_version,
                entity.updated_in_version,
            )
            for entity in source.entities
        ),
    )
    conn.executemany(
        "INSERT INTO content_expression ("
        "entity_id, expression_type, fixedness, recognition_policy"
        ") VALUES (?, ?, ?, ?)",
        (
            (
                entity.entity_id,
                str(entity.expression_type),
                str(entity.fixedness),
                str(entity.recognition_policy),
            )
            for entity in source.entities
        ),
    )
    conn.executemany(
        "INSERT INTO content_target ("
        "entity_id, target_type, target_mode, learning_intent, evidence_modality"
        ") VALUES (?, ?, ?, ?, ?)",
        (
            (
                entity.entity_id,
                entity.target_type,
                entity.target_mode,
                entity.learning_intent,
                entity.evidence_modality,
            )
            for entity in source.entities
        ),
    )
    conn.executemany(
        "INSERT INTO content_teaching (entity_id, reveal_form) VALUES (?, ?)",
        ((entity.entity_id, entity.reveal_form) for entity in source.entities),
    )
    conn.executemany(
        "INSERT INTO content_hint_rung (entity_id, ordinal, rung) "
        "VALUES (?, ?, ?)",
        (
            (entity.entity_id, ordinal, rung)
            for entity in source.entities
            for ordinal, rung in enumerate(entity.hint_ladder)
        ),
    )
    conn.executemany(
        "INSERT INTO content_example (entity_id, role, ordinal, form) "
        "VALUES (?, ?, ?, ?)",
        (
            (entity.entity_id, role, ordinal, form)
            for entity in source.entities
            for role, forms in (
                (str(ExampleLinkRole.PRIMARY_TARGET), entity.canonical_forms),
                (str(ExampleLinkRole.SUPPORTING), entity.alternative_realizations),
            )
            for ordinal, form in enumerate(forms)
        ),
    )
    conn.executemany(
        "INSERT INTO content_slot ("
        "entity_id, group_ordinal, token_ordinal, token"
        ") VALUES (?, ?, ?, ?)",
        (
            (entity.entity_id, group_ordinal, token_ordinal, token)
            for entity in source.entities
            for group_ordinal, group in enumerate(entity.required_slots)
            for token_ordinal, token in enumerate(group)
        ),
    )
    conn.executemany(
        "INSERT INTO curriculum_capability ("
        "capability_id, curriculum_node_id, family, level"
        ") VALUES (?, ?, ?, ?)",
        (
            (
                capability.capability_id,
                capability.curriculum_node_id,
                str(capability.family),
                capability.level,
            )
            for capability in source.capabilities
        ),
    )
    conn.executemany(
        "INSERT INTO curriculum_link ("
        "resource_id, node_id, relation, strength, primary_flag, "
        "editorial_status, rationale"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                link.resource_id,
                link.node_id,
                str(link.relation),
                link.strength,
                1 if link.primary_flag else 0,
                link.editorial_status,
                link.rationale,
            )
            for link in source.links
        ),
    )
    conn.executemany(
        "INSERT INTO curriculum_prerequisite ("
        "from_node, to_node, edge_type, prerequisite_strength"
        ") VALUES (?, ?, ?, ?)",
        (
            (
                edge.from_node,
                edge.to_node,
                str(edge.edge_type),
                edge.prerequisite_strength,
            )
            for edge in source.prerequisites
        ),
    )


def build_content_db(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    content_src_dir: Path = CONTENT_SRC_DIR,
    curriculum_dir: Path = CURRICULUM_DIR,
) -> BuildReport:
    """Build (or rebuild) content.db from the authoring source.

    Deterministic and idempotent: same source → same rows in the same order →
    same bytes. The artifact is written to a temporary sibling and moved into
    place, so a failed build never leaves a half-written content.db.
    """

    source = load_source(content_src_dir, curriculum_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    conn = sqlite3.connect(str(temp_path), isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        _write_rows(conn, source)
        conn.execute("COMMIT")
    except BaseException:
        conn.close()
        if temp_path.exists():
            temp_path.unlink()
        raise
    else:
        conn.close()
    os.replace(temp_path, output_path)

    return BuildReport(
        output_path=output_path,
        content_version=source.content_version,
        curriculum_version=source.curriculum_version,
        entity_count=len(source.entities),
        capability_count=len(source.capabilities),
        link_count=len(source.links),
        prerequisite_count=len(source.prerequisites),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Rebuild content.db from the command line (see content_src/README.md)."""

    parser = argparse.ArgumentParser(
        prog="python -m elc.content.build",
        description="Build content.db from the authoring source trees.",
    )
    parser.add_argument(
        "--out", default=str(DEFAULT_OUTPUT), help="output content.db path"
    )
    parser.add_argument(
        "--content-src",
        default=str(CONTENT_SRC_DIR),
        help="authoring content tree",
    )
    parser.add_argument(
        "--curriculum",
        default=str(CURRICULUM_DIR),
        help="authoring curriculum tree",
    )
    args = parser.parse_args(argv)

    try:
        report = build_content_db(
            Path(args.out),
            content_src_dir=Path(args.content_src),
            curriculum_dir=Path(args.curriculum),
        )
    except BuildError as error:
        print(f"content.db build refused: {error}", file=sys.stderr)
        return 2
    print(
        f"content.db built: {report.output_path} "
        f"(content_version={report.content_version}, "
        f"curriculum_version={report.curriculum_version}, "
        f"entities={report.entity_count}, capabilities={report.capability_count}, "
        f"links={report.link_count}, prerequisites={report.prerequisite_count})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
