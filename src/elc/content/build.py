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

C1 (Phase 11) adds the §8.1 readiness **evidence** face: thirteen tables
appended to the eleven above (`SCHEMA_STATEMENTS`, 11 → 24) plus the
`content_src/evidence/<entity_id>.json` authoring tree, declared by the index
like `entities` (no glob fallback, unlisted documents refused). Every §8.1
fact key the ladder reads now has a table that carries it, so
`elc.curriculum.store.readiness_facts` reads the eighteen row-backed keys
from these tables and proves ``entity_row`` by the entity's own §24.1 row
(the preceding ``get_resource`` success), instead of declaring any of them
absent. Where docs/DATA_MODEL.md §24 names a concept without
giving a field table, the column choice is a **declared reading** written
into the table's comment below (and into `content_src/README.md`) with a
Revisit — it never claims the canonical text lists those columns. The one
fact that is a *declaration about the source* rather than a row set (the
§24.9 need behind §8.1's "以及需要时的 TypicalError") is carried as a
declared-reading `content_meta` key: `elc.content.types.
typical_error_required_key`.

The runtime reads this file only through :mod:`elc.content.store` (read-only
URI connection); the write face of this module is build-time only.

C3-R1 (Phase 11) adds two authoring faces and one link column:

- **capability functional definitions** — `curriculum/capabilities/<id>.json`
  may carry an optional ``functional_definition`` block (statement /
  counts_as_realization / does_not_count / boundary_cases / basis). The block
  is read **strictly** (unknown key, missing key, empty string or empty list
  ⇒ BuildError) and carried on :class:`CapabilityDoc`, because it is an
  *authoring-side* standard: it is what the C3-R1 review of the §24.7 links
  cites (curriculum/README.md), and the build's own use of it is the rule
  that a ``CURRICULUM_MAPPING`` row may only name a capability that **has**
  such a definition — a mapping claim against a capability with no stated
  standard is refused rather than stored. It is not written into the
  artifact; no §24 table carries it (declared reading; Revisit: the first
  runtime consumer that needs the definition adds a table and bumps
  `CONTENT_DB_VERSION`, the C1 precedent).
- **`curriculum_link.mapping_class`** — the C3-R1 declared reading that
  separates a row that is a **curriculum mapping** (``CURRICULUM_MAPPING``:
  the resource's taught function meets at least one
  ``counts_as_realization`` entry of the node's functional definition and
  falls into none of its ``does_not_count`` entries) from a row that is a
  **coverage placement** (``COVERAGE_PLACEMENT``: the nearest-node choice a
  corpus of five nodes forces, carrying no claim of semantic mapping). The
  build enforces two shape rules over it: the value is one of the two words,
  and ``relation = REALIZES`` implies ``CURRICULUM_MAPPING`` (a realization
  claim is a mapping claim). Which rows are which is an editorial judgement
  recorded per row in the row's own ``rationale``; the build never infers it.
  docs/DATA_MODEL.md §24.7 lists seven columns and no such column: this is a
  declared reading (Revisit registered with the decision) and it is why
  `CONTENT_DB_VERSION` moves again.

C3-R2 (Phase 11) closes the external review's HIGH-2 at the specification
layer and stands up the provenance dimension:

- **POSITIVE_ERROR fixtures** — `DETECTION_FIXTURE_KINDS` grows a third word
  (``POSITIVE_ERROR``, a real learner-error production the declared rules
  must fire on, ``expected = MATCH``), and the kind↔expected pairing the
  tests pinned over the corpus becomes a **source contract**
  (:data:`elc.content.types.DETECTION_FIXTURE_EXPECTED_BY_KIND`; a fixture
  row whose ``expected`` disagrees with its own ``kind`` is refused). Every
  entity that declares a typical error must carry at least one
  POSITIVE_ERROR fixture **per declared error_type** (structure only — the
  build never judges the English); a detector stub that answers NO_MATCH to
  everything can no longer pass a full fixture set.
- **provenance, derived structurally** — `content_src/audits/*.json` is
  scanned (absent or empty directory ⇒ nothing); each record is read
  strictly (``audit_id`` / ``performed_by`` / ``basis`` /
  ``approved_entities``, plus optional format keys) and its entity
  references must resolve. An entity's level is ``EDITOR_REVIEWED`` when at
  least one audit approves it and ``AUTHOR_DECLARED`` otherwise (the
  baseline for every documented entity). The two stronger words
  (:data:`elc.content.types.PROVENANCE_LEVELS`) are vocabulary members only
  — no derivation produces them today (no detector executor, no real-run
  data; their reachability conditions are written on the constant). Levels
  land in the new ``content_provenance`` table and never touch the §8.1
  ladder; `CONTENT_DB_VERSION` moves to ``"4"`` for the new table.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, TypeVar

from elc.content.types import (
    CONTENT_ENTITY_COLUMNS,
    CONTENT_TEXT_ROLES,
    DETECTION_FIXTURE_EXPECTED_BY_KIND,
    DETECTION_FIXTURE_KINDS,
    LEARNING_INTENTS,
    LIFECYCLE_STATUSES,
    PROVENANCE_LEVELS,
    TARGET_MODES,
    TARGET_TYPES,
    ContentType,
    ExampleLinkRole,
    ExpressionFixedness,
    ExpressionSubtype,
    RecognitionPolicy,
    typical_error_required_key,
)
from elc.curriculum.types import (
    CapabilityFamily,
    CurriculumEdgeType,
    CurriculumLinkRelation,
    PrerequisiteStrength,
)
from elc.platform.types import EvidenceModality

_T = TypeVar("_T")

__all__ = [
    "AUDITS_DIRNAME",
    "CONTENT_DB_VERSION",
    "CONTENT_SRC_DIR",
    "COVERAGE_PLACEMENT_CLASS",
    "CURRICULUM_DIR",
    "CURRICULUM_MAPPING_CLASS",
    "DEFAULT_OUTPUT",
    "MAPPING_CLASSES",
    "AuditRecord",
    "BuildError",
    "BuildReport",
    "ContentSource",
    "EvidenceDoc",
    "FunctionalDefinition",
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
#: generation, owned by this module's DDL below. Bumped ``"1"`` → ``"2"`` by
#: the C1 disposition: C1 grew the table set 11 → 24 (``SCHEMA_STATEMENTS``),
#: and §26.1 requires the version to move explicitly, never guessed from the
#: schema ("数据库迁移必须显式更新版本，禁止依赖代码猜 schema"). Bumped
#: ``"2"`` → ``"3"`` by C3-R1: the table set is unchanged, but
#: ``curriculum_link`` gains the ``mapping_class`` column, i.e. the artifact's
#: shape moves even though no table appears or disappears — a reader keyed to
#: the shape (elc.content.store, elc.curriculum.store) must be able to tell
#: the two generations apart. Bumped ``"3"`` → ``"4"`` by C3-R2: the table
#: set grows again (``content_provenance``, 24 → 25), carrying the
#: structurally derived provenance level of every documented entity.
CONTENT_DB_VERSION = "4"

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

#: The C3-R1 `mapping_class` vocabulary (declared reading, §24.7 carries no
#: such column). ``CURRICULUM_MAPPING`` — the resource's taught function
#: meets at least one ``counts_as_realization`` entry of the node's
#: functional definition and no ``does_not_count`` entry.
#: ``COVERAGE_PLACEMENT`` — the nearest-node choice a five-node corpus
#: forces, with no semantic-mapping claim. The read face keeps its own
#: spelling of ``CURRICULUM_MAPPING`` (elc.content.store) rather than
#: importing this build module into the runtime read graph; a test pins the
#: two equal.
CURRICULUM_MAPPING_CLASS = "CURRICULUM_MAPPING"
COVERAGE_PLACEMENT_CLASS = "COVERAGE_PLACEMENT"
MAPPING_CLASSES = (CURRICULUM_MAPPING_CLASS, COVERAGE_PLACEMENT_CLASS)

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

#: The optional C3-R1 block a capability document may carry. **Optional**:
#: a capability with no functional definition is a legal registry node (the
#: five shipped nodes all carry one, because the C3-R1 review needed a stated
#: standard). Read strictly when present — the five keys below are exactly
#: the block, every string is non-empty, every list is non-empty and
#: ``boundary_cases`` names at least two cases, so a half-written standard
#: cannot pass for a standard.
_CAPABILITY_DEFINITION_KEY = "functional_definition"
_FUNCTIONAL_DEFINITION_KEYS = (
    "statement",
    "counts_as_realization",
    "does_not_count",
    "boundary_cases",
    "basis",
)

#: The least number of boundary cases a functional definition must state
#: (C3-R1: the task's "boundary_cases ≥2").
_MIN_BOUNDARY_CASES = 2
_LINK_KEYS = (
    "resource_id",
    "node_id",
    "relation",
    "strength",
    "primary_flag",
    "editorial_status",
    "mapping_class",
    "rationale",
)
_PREREQUISITE_KEYS = (
    "from_node",
    "to_node",
    "edge_type",
    "prerequisite_strength",
)

# ---------------------------------------------------------------------------
# C1: the readiness evidence document (content_src/evidence/<entity_id>.json)
# ---------------------------------------------------------------------------

#: Every block an evidence document may declare, in table-creation order. A
#: block is **optional** — a document states the evidence this source
#: carries, and a fact it does not state stays absent (elc.curriculum.
#: readiness reads absence as absence, never as False-by-default-satisfied).
#: A key outside this set is refused: the build may not ignore a block
#: silently (content_src/README.md "evidence 块").
_EVIDENCE_BLOCK_KEYS = (
    "assessment_membership",
    "lexical_entry",
    "senses",
    "texts",
    "forms",
    "pedagogical_profile",
    "pack_overlays",
    "resource_labels",
    "example_policy",
    "typical_error_required",
    "typical_errors",
    "detection_policy",
    "detection_rules",
    "detection_fixtures",
)

#: The per-block key sets, spelled out literally (no assembly). Each one is
#: the table's columns minus `entity_id` (which the document does not repeat:
#: the file name names the entity), in table order.
_ASSESSMENT_MEMBERSHIP_KEYS = ("assessment_id", "membership_status", "source")
_LEXICAL_ENTRY_KEYS = ("lemma", "pos")
_SENSE_KEYS = ("sense_id", "ordinal")
_TEXT_KEYS = ("sense_id", "language", "role", "ordinal", "text")
_FORM_KEYS = (
    "form_id",
    "written",
    "normalized",
    "form_type",
    "morph_features",
    "pronunciation",
)
_PEDAGOGICAL_PROFILE_KEYS = (
    "core_utility",
    "receptive_value",
    "productive_value",
    "receptive_difficulty",
    "productive_difficulty",
    "explanation_cost",
    "transfer_value",
    "naturalness_value",
    "default_target_mode",
    "editorial_status",
    "rationale",
)
_PACK_OVERLAY_KEYS = ("pack_id", "weight", "rationale")
_RESOURCE_LABEL_KEYS = (
    "ordinal",
    "register",
    "usage_modality",
    "genre",
    "context",
    "style",
    "domain",
    "variety",
)
_EXAMPLE_POLICY_KEYS = ("policy_version", "policy")
_TYPICAL_ERROR_KEYS = (
    "ordinal",
    "learner_l1",
    "error_type",
    "error_pattern",
    "corrected_pattern",
    "explanation",
    "severity",
    "detection_policy",
)
_DETECTION_POLICY_KEYS = ("policy_version", "policy")
_DETECTION_RULE_KEYS = ("ordinal", "rule")
_DETECTION_FIXTURE_KEYS = ("ordinal", "kind", "text", "expected")


@dataclass(frozen=True)
class AssessmentMembershipRow:
    assessment_id: str
    membership_status: str
    source: str


@dataclass(frozen=True)
class LexicalEntryRow:
    lemma: str
    pos: str


@dataclass(frozen=True)
class SenseRow:
    sense_id: str
    ordinal: int


@dataclass(frozen=True)
class TextRow:
    sense_id: str | None
    language: str
    role: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class FormRow:
    form_id: str
    written: str
    normalized: str
    form_type: str
    morph_features: str | None
    pronunciation: str | None


@dataclass(frozen=True)
class PedagogicalProfileRow:
    core_utility: str
    receptive_value: str
    productive_value: str
    receptive_difficulty: str
    productive_difficulty: str
    explanation_cost: str
    transfer_value: str
    naturalness_value: str
    default_target_mode: str
    editorial_status: str
    rationale: str


@dataclass(frozen=True)
class PackOverlayRow:
    pack_id: str
    weight: str
    rationale: str


@dataclass(frozen=True)
class ResourceLabelRow:
    ordinal: int
    register: str | None
    usage_modality: str | None
    genre: str | None
    context: str | None
    style: str | None
    domain: str | None
    variety: str | None


@dataclass(frozen=True)
class ExamplePolicyRow:
    policy_version: str
    policy: str


@dataclass(frozen=True)
class TypicalErrorRow:
    ordinal: int
    learner_l1: str | None
    error_type: str
    error_pattern: str
    corrected_pattern: str
    explanation: str
    severity: str
    detection_policy: str


@dataclass(frozen=True)
class DetectionPolicyRow:
    policy_version: str
    policy: str


@dataclass(frozen=True)
class DetectionRuleRow:
    ordinal: int
    rule: str


@dataclass(frozen=True)
class DetectionFixtureRow:
    ordinal: int
    kind: str
    text: str
    expected: str


@dataclass(frozen=True)
class EvidenceDoc:
    """One entity's readiness evidence, as the authoring source states it.

    Every block is optional and every tuple is empty when its block is absent:
    "the source did not state this fact" and "the source stated it empty" are
    the same thing here (an empty list block is refused), so no fact is ever
    present by default. ``typical_error_required`` is the one block that is a
    *declaration about the source* rather than a row set: ``None`` means the
    source declared nothing (the §8.1 "需要时" condition is not triggered),
    ``True``/``False`` is recorded verbatim in ``content_meta``.
    """

    entity_id: str
    assessment_membership: tuple[AssessmentMembershipRow, ...]
    lexical_entry: LexicalEntryRow | None
    senses: tuple[SenseRow, ...]
    texts: tuple[TextRow, ...]
    forms: tuple[FormRow, ...]
    pedagogical_profile: PedagogicalProfileRow | None
    pack_overlays: tuple[PackOverlayRow, ...]
    resource_labels: tuple[ResourceLabelRow, ...]
    example_policy: ExamplePolicyRow | None
    typical_error_required: bool | None
    typical_errors: tuple[TypicalErrorRow, ...]
    detection_policy: DetectionPolicyRow | None
    detection_rules: tuple[DetectionRuleRow, ...]
    detection_fixtures: tuple[DetectionFixtureRow, ...]

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
    # C3-R1's declared-reading column (the two words are validated by the
    # build, not by a CHECK: the table is generated, and the error must name
    # the legal set — the build's own vocabulary rule).
    "mapping_class TEXT NOT NULL,"
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
    # -- C1 (Phase 11): the §8.1 readiness evidence face -------------------
    # Thirteen tables, appended after the eleven above (11 → 24, creation
    # order is part of the artifact's bytes). Every one of them carries the
    # evidence exactly ONE §8.1 fact key needs (elc.curriculum.readiness),
    # and every FK points at content_entity(entity_id). Where §24 names the
    # concept without giving a field table, the column choice is a **declared
    # reading** (spelled out per table below and in content_src/README.md)
    # with a Revisit — never a claim that the canonical text lists columns.
    #
    # §24.8 AssessmentMembership ("保存 source fact"). §24.8 gives no field
    # table: the four columns below are the declared reading (the assessment
    # id the source names, the membership status it states, and where the
    # fact came from). No word list is invented for membership_status/source
    # — the source's own strings are recorded verbatim. Revisit: when §24.8
    # gains a canonical field table or word lists, migrate these columns
    # onto it.
    "CREATE TABLE content_assessment_membership ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "assessment_id TEXT NOT NULL,"
    "membership_status TEXT NOT NULL,"
    "source TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, assessment_id)"
    ")",
    # §24.2 LexicalEntry: "以 lemma/POS/morphological paradigm 区分" — the two
    # named fields; POS is the source's own string (no §24 word list).
    # Declared reading (C1 disposition): §24.2 names a **third** differentiator
    # (morphological paradigm) and this table builds no column for it — the
    # entry's paradigmatic shape is carried by its §24.2 Form rows
    # (`content_form`, the R1 `forms` evidence), not by the entry row.
    # Revisit: the first source that needs a paradigm field on the entry
    # itself adds the column (and bumps CONTENT_DB_VERSION).
    "CREATE TABLE content_lexical_entry ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "lemma TEXT NOT NULL,"
    "pos TEXT NOT NULL"
    ")",
    # §24.3 Sense: "Sense 是主要可学习语义单位". §24.3 gives no field table:
    # sense_id is the source's id, ordinal its authored order (declared
    # reading).
    "CREATE TABLE content_sense ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "sense_id TEXT NOT NULL,"
    "ordinal INTEGER NOT NULL,"
    "PRIMARY KEY (entity_id, sense_id)"
    ")",
    # §24.3 ContentText. `role` is the §24.3 six-word list verbatim; the text
    # may hang off a sense (nullable) and carries its own language (a
    # translation is a text in another language, so the index language is
    # not imposed here). Declared reading (C1 disposition): the PRIMARY KEY
    # is (entity_id, role, ordinal) and does **not** carry `language` — the
    # minimal column set for a single-language corpus; a second language on
    # the same (role, ordinal) would collide on the PK. Revisit: the first
    # multi-language source widens the PK (and bumps CONTENT_DB_VERSION).
    "CREATE TABLE content_text ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "sense_id TEXT,"
    "language TEXT NOT NULL,"
    "role TEXT NOT NULL,"
    "ordinal INTEGER NOT NULL,"
    "text TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, role, ordinal)"
    ")",
    # §24.2 Form, its five columns verbatim: written / normalized / form_type
    # / morph_features? / pronunciation?. form_id is the source's row id.
    "CREATE TABLE content_form ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "form_id TEXT NOT NULL,"
    "written TEXT NOT NULL,"
    "normalized TEXT NOT NULL,"
    "form_type TEXT NOT NULL,"
    "morph_features TEXT,"
    "pronunciation TEXT,"
    "PRIMARY KEY (entity_id, form_id)"
    ")",
    # §24.7 PedagogicalProfile — its eleven columns verbatim. The two columns
    # whose value domain another canonical list owns are validated against it
    # (default_target_mode → §11 target modes, editorial_status → §24.11).
    "CREATE TABLE content_pedagogical_profile ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "core_utility TEXT NOT NULL,"
    "receptive_value TEXT NOT NULL,"
    "productive_value TEXT NOT NULL,"
    "receptive_difficulty TEXT NOT NULL,"
    "productive_difficulty TEXT NOT NULL,"
    "explanation_cost TEXT NOT NULL,"
    "transfer_value TEXT NOT NULL,"
    "naturalness_value TEXT NOT NULL,"
    "default_target_mode TEXT NOT NULL,"
    "editorial_status TEXT NOT NULL,"
    "rationale TEXT NOT NULL"
    ")",
    # §24.8 PackOverlay ("保存内部教学策略/权重"). §24.8 gives no field table:
    # pack_id / weight / rationale are the declared reading (a pack's weight
    # is the source's own string — §24 declares no numeric domain here).
    # Revisit: when §24.8's overlay field table lands, retype `weight` onto
    # the canonical domain.
    "CREATE TABLE content_pack_overlay ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "pack_id TEXT NOT NULL,"
    "weight TEXT NOT NULL,"
    "rationale TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, pack_id)"
    ")",
    # §24.7 ResourceLabel — its seven columns verbatim, all nullable (a label
    # states the facets it knows; an unstated facet is NULL, never ""). The
    # seven columns are canonical; the **row layout** is the declared reading:
    # §24.7 names no row identity, so rows are ordered by an authored
    # `ordinal` and keyed (entity_id, ordinal). Revisit: when §24.7 states a
    # row identity, replace the ordinal key with it.
    "CREATE TABLE content_resource_label ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "ordinal INTEGER NOT NULL,"
    "register TEXT,"
    "usage_modality TEXT,"
    "genre TEXT,"
    "context TEXT,"
    "style TEXT,"
    "domain TEXT,"
    "variety TEXT,"
    "PRIMARY KEY (entity_id, ordinal)"
    ")",
    # §8.1 R3 "可用 example policy" — which examples to present, when. §24
    # gives no field table: policy_version + policy are the declared reading
    # (a versioned declarative text, like elc.persona's versioned policies).
    # Revisit: a canonical policy carrier (e.g. a §24 field table) replaces
    # this shape.
    "CREATE TABLE content_example_policy ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "policy_version TEXT NOT NULL,"
    "policy TEXT NOT NULL"
    ")",
    # §24.9 TypicalError — its seven columns verbatim (learner_l1 optional,
    # the other six required). severity is the §24.9 column with no §24 word
    # list; detection_policy here is the §24.9 per-error column (the entity-
    # level R4 policy lives in content_detection_policy).
    "CREATE TABLE content_typical_error ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "ordinal INTEGER NOT NULL,"
    "learner_l1 TEXT,"
    "error_type TEXT NOT NULL,"
    "error_pattern TEXT NOT NULL,"
    "corrected_pattern TEXT NOT NULL,"
    "explanation TEXT NOT NULL,"
    "severity TEXT NOT NULL,"
    "detection_policy TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, ordinal)"
    ")",
    # §8.1 R4 "detection policy". §24.10 names the requirement and no field
    # table: policy_version + policy are the declared reading — the versioned
    # declarative half of "可测试 detection policy", with the testable half
    # in content_detection_rule / content_detection_fixture below. Revisit:
    # a canonical detection-policy carrier replaces this shape.
    "CREATE TABLE content_detection_policy ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "policy_version TEXT NOT NULL,"
    "policy TEXT NOT NULL"
    ")",
    # §8.1 R4 "recognition rules" — the testable rules themselves, one row
    # per rule, ordinal preserving the authored order.
    "CREATE TABLE content_detection_rule ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "ordinal INTEGER NOT NULL,"
    "rule TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, ordinal)"
    ")",
    # §8.1 R4 "negative fixtures / false-positive boundaries". kind is the
    # two-word reading (elc.content.types.DETECTION_FIXTURE_KINDS): the
    # example an expected reading must NOT match (NEGATIVE), or the example
    # sitting on the declared boundary (FALSE_POSITIVE_BOUNDARY). `expected`
    # is the declared expected reading of that fixture, so a fixture is a
    # checkable pair rather than a sentence.
    "CREATE TABLE content_detection_fixture ("
    "entity_id TEXT NOT NULL REFERENCES content_entity(entity_id),"
    "ordinal INTEGER NOT NULL,"
    "kind TEXT NOT NULL,"
    "text TEXT NOT NULL,"
    "expected TEXT NOT NULL,"
    "PRIMARY KEY (entity_id, ordinal)"
    ")",
    # -- C3-R2: the structurally derived provenance face --------------------
    # One row per documented entity (the §8.1 evidence document's entity —
    # elc.content.build._provenance_rows), carrying the level the structure
    # derives: AUTHOR_DECLARED for the bare evidence baseline,
    # EDITOR_REVIEWED once an audit record in content_src/audits/ approves
    # the entity. The two stronger words of elc.content.types.
    # PROVENANCE_LEVELS are derivable today by nothing, so no CHECK is
    # invented for them here — the word list lives on the constant and the
    # derivation is the only writer. This is an independent dimension: the
    # §8.1 readiness ladder reads none of it.
    "CREATE TABLE content_provenance ("
    "entity_id TEXT PRIMARY KEY REFERENCES content_entity(entity_id),"
    "provenance_level TEXT NOT NULL"
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
class FunctionalDefinition:
    """One capability's C3-R1 functional definition (an authoring standard).

    Every list is non-empty and ``boundary_cases`` carries at least two
    cases (the build refuses a thinner block). The definition is the
    standard the §24.7 links into this node were reviewed against; it states
    its own basis honestly (this repository's authoring judgement over the
    canonical family/subtype vocabulary, never an external psychometric
    source) and it is **not** written into content.db.
    """

    statement: str
    counts_as_realization: tuple[str, ...]
    does_not_count: tuple[str, ...]
    boundary_cases: tuple[str, ...]
    basis: str


@dataclass(frozen=True)
class CapabilityDoc:
    """One capability registry node (docs/DOMAIN_MODEL.md §7)."""

    curriculum_node_id: str
    capability_id: str
    family: CapabilityFamily
    level: int
    #: The optional C3-R1 functional definition (absent → ``None``). Carried
    #: so the build can hold the mapping-vs-placement rule on the link side
    #: ("a CURRICULUM_MAPPING row names a capability with a definition") and
    #: so a caller of :func:`load_source` can read the standard that was
    #: applied, without a table being invented for it.
    functional_definition: FunctionalDefinition | None = None


@dataclass(frozen=True)
class LinkRow:
    """One CurriculumLink (docs/DATA_MODEL.md §24.7's seven columns plus the
    C3-R1 declared-reading ``mapping_class`` column)."""

    resource_id: str
    node_id: str
    relation: CurriculumLinkRelation
    strength: str | None
    primary_flag: bool
    editorial_status: str
    mapping_class: str
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
    evidence: tuple[EvidenceDoc, ...] = ()
    #: C3-R2: the provenance audit records, in file-name order. Empty for a
    #: corpus with no (or an empty) `content_src/audits/` directory.
    audits: tuple[AuditRecord, ...] = ()

    def entity_ids(self) -> tuple[str, ...]:
        return tuple(entity.entity_id for entity in self.entities)

    def capability_ids(self) -> tuple[str, ...]:
        return tuple(capability.capability_id for capability in self.capabilities)

    def evidence_of(self, entity_id: str) -> EvidenceDoc | None:
        """The evidence document declared for one entity, if any."""

        for document in self.evidence:
            if document.entity_id == entity_id:
                return document
        return None


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
    evidence_count: int


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
    mapping: Mapping[str, Any],
    expected: Sequence[str],
    where: str,
    optional: Sequence[str] = (),
) -> None:
    """The mapping carries exactly ``expected`` (plus, optionally, ``optional``).

    ``optional`` names keys a document **may** carry — an absent optional key
    is not a missing key, and the caller reads the value only when it is
    present. There is deliberately no "ignore extra keys" switch: every key a
    document states is either declared here or refused, so a typo (or a
    hand-written key the build does not know) never passes silently.
    """

    expected_set = set(expected) | set(optional)
    actual = set(mapping)
    missing = sorted(set(expected) - actual)
    unknown = sorted(actual - expected_set)
    if missing or unknown:
        raise BuildError(
            f"{where}: key mismatch (missing={missing}, unknown={unknown}); "
            f"declared keys are {list(expected)}"
            + (f" (optional: {list(optional)})" if optional else "")
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


def _ordinal(mapping: Mapping[str, Any], key: str, where: str) -> int:
    value = _integer(mapping, key, where)
    if value < 0:
        raise BuildError(f"{where}.{key}: must be >= 0")
    return value


def _object_list(
    mapping: Mapping[str, Any], key: str, item_keys: Sequence[str], where: str
) -> tuple[Mapping[str, Any], ...]:
    """One list-of-objects block, strictly read.

    A non-empty JSON array whose every item is an object carrying exactly
    ``item_keys``. An empty array is refused: "this source states no row" is
    expressed by *omitting* the block, so an empty array can never be read as
    a stated fact.
    """

    value = mapping[key]
    if not isinstance(value, list) or not value:
        raise BuildError(
            f"{where}.{key}: expected a non-empty JSON array (omit the block "
            "instead of stating it empty)"
        )
    items: list[Mapping[str, Any]] = []
    for index, raw in enumerate(value):
        item_where = f"{where}.{key}[{index}]"
        item = _mapping(raw, item_where)
        _exact_keys(item, item_keys, item_where)
        items.append(item)
    return tuple(items)


def _rows(
    mapping: Mapping[str, Any],
    key: str,
    item_keys: Sequence[str],
    where: str,
    build: Callable[[Mapping[str, Any], str], _T],
) -> tuple[_T, ...]:
    """One optional list block, read into typed rows in authored order.

    The caller checks its own primary key afterwards (``_refuse_duplicate_
    keys``): a duplicate is an authoring error, never a silent overwrite.
    """

    if key not in mapping:
        return ()
    return tuple(
        build(item, f"{where}.{key}")
        for item in _object_list(mapping, key, item_keys, where)
    )


def _refuse_duplicate_keys(
    keys: Sequence[object], where: str, primary_key: str
) -> None:
    """The table's PRIMARY KEY, checked at the source: a duplicate key would
    have to be silently dropped or overwritten by the INSERT, and this build
    does neither."""

    seen: set[object] = set()
    for key in keys:
        if key in seen:
            raise BuildError(
                f"{where}: duplicate value {key!r} for {primary_key} — the "
                "artifact's primary key refuses it"
            )
        seen.add(key)


def _document_list(
    index_path: Path,
    index: Mapping[str, Any],
    key: str,
    base_dir: Path,
    directory: Path,
    *,
    allow_empty: bool = False,
) -> list[Path]:
    """The document list an index declares, with the no-silent-skip checks.

    Index entries are relative to the authoring tree root (``base_dir``);
    ``directory`` is that tree's document directory. Every listed path must
    exist, no path may repeat, and any ``*.json`` present in ``directory`` but
    unlisted is an error — a file the build would otherwise ignore silently.

    ``allow_empty`` exists for one key (``evidence``): a corpus that states no
    readiness evidence declares ``[]`` and is a legal source — "no evidence"
    is a state this build must build, not refuse. The no-silent-skip half is
    unchanged: the directory is still scanned, so a document that exists but
    is not listed is still an error.
    """

    raw = index[key]
    if not isinstance(raw, list) or (not raw and not allow_empty):
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


def _functional_definition_from_document(
    mapping: Mapping[str, Any], where: str
) -> FunctionalDefinition:
    """C3-R1: read one capability's optional functional-definition block.

    Strict on every key and every list: the block is the standard the link
    review cites, so a block that states nothing (or states one boundary
    case, or an empty ``counts_as_realization``) is refused rather than
    stored as a standard that judges nothing.
    """

    _exact_keys(mapping, _FUNCTIONAL_DEFINITION_KEYS, where)
    boundary_cases = _string_list(mapping, "boundary_cases", where)
    if len(boundary_cases) < _MIN_BOUNDARY_CASES:
        raise BuildError(
            f"{where}.boundary_cases: a functional definition states at least"
            f" {_MIN_BOUNDARY_CASES} boundary cases; got {len(boundary_cases)}"
        )
    # An empty list is not "no criteria": a definition that states none judges
    # nothing, so it is refused rather than stored as a standard. (A block the
    # source omits entirely is the legal "no definition yet" state.)
    for key in ("counts_as_realization", "does_not_count"):
        if not _string_list(mapping, key, where):
            raise BuildError(
                f"{where}.{key}: a functional definition states at least one"
                " entry; an empty list is not a standard"
            )
    return FunctionalDefinition(
        statement=_string(mapping, "statement", where),
        counts_as_realization=_string_list(
            mapping, "counts_as_realization", where
        ),
        does_not_count=_string_list(mapping, "does_not_count", where),
        boundary_cases=boundary_cases,
        basis=_string(mapping, "basis", where),
    )


def _capability_from_document(
    path: Path, document: Mapping[str, Any]
) -> CapabilityDoc:
    where = str(path)
    _exact_keys(
        document,
        _CAPABILITY_KEYS,
        where,
        optional=(_CAPABILITY_DEFINITION_KEY,),
    )
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
    definition = None
    if _CAPABILITY_DEFINITION_KEY in document:
        definition = _functional_definition_from_document(
            _mapping(
                document[_CAPABILITY_DEFINITION_KEY],
                f"{where}.{_CAPABILITY_DEFINITION_KEY}",
            ),
            f"{where}.{_CAPABILITY_DEFINITION_KEY}",
        )
    return CapabilityDoc(
        curriculum_node_id=curriculum_node_id,
        capability_id=capability_id,
        family=family,
        level=level,
        functional_definition=definition,
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
        # C3-R1: the declared-reading mapping/placement split. The word is
        # validated against the vocabulary like every other word; which word
        # a row carries is the author's judgement, recorded in the row's
        # ``rationale`` and never inferred here.
        mapping_class = _vocabulary(
            _string(row, "mapping_class", item_where),
            MAPPING_CLASSES,
            f"{item_where}.mapping_class",
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
                mapping_class=mapping_class,
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


def _evidence_from_document(
    path: Path, document: Mapping[str, Any], entity_ids: frozenset[str]
) -> EvidenceDoc:
    """One readiness evidence document (`content_src/evidence/<entity_id>.json`).

    The file name names the entity — the document does not repeat it, and the
    entity must be declared by the index (an evidence document for an unknown
    id is a dangling reference and is refused). Every block is optional; a
    block that is present is read strictly: unknown blocks, wrong JSON types,
    empty strings, unknown vocabulary words, negative ordinals and duplicate
    primary keys all raise :class:`BuildError`. Nothing is defaulted and
    nothing is skipped — a source that states no evidence produces an artifact
    that carries none.
    """

    where = str(path)
    entity_id = path.name.removesuffix(".json")
    if entity_id not in entity_ids:
        raise BuildError(
            f"{where}: the file name names {entity_id!r}, which is not a "
            "declared content entity (an evidence document may not dangle)"
        )
    unknown = sorted(set(document) - set(_EVIDENCE_BLOCK_KEYS))
    if unknown:
        raise BuildError(
            f"{where}: unknown evidence block(s) {unknown}; declared blocks "
            f"are {list(_EVIDENCE_BLOCK_KEYS)}"
        )

    assessment_membership = _rows(
        document,
        "assessment_membership",
        _ASSESSMENT_MEMBERSHIP_KEYS,
        where,
        lambda item, item_where: AssessmentMembershipRow(
            assessment_id=_string(item, "assessment_id", item_where),
            membership_status=_string(item, "membership_status", item_where),
            source=_string(item, "source", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.assessment_id for row in assessment_membership],
        f"{where}.assessment_membership",
        "content_assessment_membership (assessment_id)",
    )

    lexical_entry: LexicalEntryRow | None = None
    if "lexical_entry" in document:
        block_where = f"{where}.lexical_entry"
        block = _mapping(document["lexical_entry"], block_where)
        _exact_keys(block, _LEXICAL_ENTRY_KEYS, block_where)
        lexical_entry = LexicalEntryRow(
            lemma=_string(block, "lemma", block_where),
            pos=_string(block, "pos", block_where),
        )

    senses = _rows(
        document,
        "senses",
        _SENSE_KEYS,
        where,
        lambda item, item_where: SenseRow(
            sense_id=_string(item, "sense_id", item_where),
            ordinal=_ordinal(item, "ordinal", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.sense_id for row in senses],
        f"{where}.senses",
        "content_sense (sense_id)",
    )

    texts = _rows(
        document,
        "texts",
        _TEXT_KEYS,
        where,
        lambda item, item_where: TextRow(
            sense_id=_optional_string(item, "sense_id", item_where),
            language=_string(item, "language", item_where),
            role=_vocabulary(
                _string(item, "role", item_where),
                CONTENT_TEXT_ROLES,
                f"{item_where}.role",
            ),
            ordinal=_ordinal(item, "ordinal", item_where),
            text=_string(item, "text", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [(row.role, row.ordinal) for row in texts],
        f"{where}.texts",
        "content_text (role, ordinal)",
    )

    forms = _rows(
        document,
        "forms",
        _FORM_KEYS,
        where,
        lambda item, item_where: FormRow(
            form_id=_string(item, "form_id", item_where),
            written=_string(item, "written", item_where),
            normalized=_string(item, "normalized", item_where),
            form_type=_string(item, "form_type", item_where),
            morph_features=_optional_string(item, "morph_features", item_where),
            pronunciation=_optional_string(item, "pronunciation", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.form_id for row in forms],
        f"{where}.forms",
        "content_form (form_id)",
    )

    pedagogical_profile: PedagogicalProfileRow | None = None
    if "pedagogical_profile" in document:
        profile_where = f"{where}.pedagogical_profile"
        block = _mapping(document["pedagogical_profile"], profile_where)
        _exact_keys(block, _PEDAGOGICAL_PROFILE_KEYS, profile_where)
        pedagogical_profile = PedagogicalProfileRow(
            core_utility=_string(block, "core_utility", profile_where),
            receptive_value=_string(block, "receptive_value", profile_where),
            productive_value=_string(block, "productive_value", profile_where),
            receptive_difficulty=_string(
                block, "receptive_difficulty", profile_where
            ),
            productive_difficulty=_string(
                block, "productive_difficulty", profile_where
            ),
            explanation_cost=_string(block, "explanation_cost", profile_where),
            transfer_value=_string(block, "transfer_value", profile_where),
            naturalness_value=_string(block, "naturalness_value", profile_where),
            default_target_mode=_vocabulary(
                _string(block, "default_target_mode", profile_where),
                TARGET_MODES,
                f"{profile_where}.default_target_mode",
            ),
            editorial_status=_vocabulary(
                _string(block, "editorial_status", profile_where),
                LIFECYCLE_STATUSES,
                f"{profile_where}.editorial_status",
            ),
            rationale=_string(block, "rationale", profile_where),
        )

    pack_overlays = _rows(
        document,
        "pack_overlays",
        _PACK_OVERLAY_KEYS,
        where,
        lambda item, item_where: PackOverlayRow(
            pack_id=_string(item, "pack_id", item_where),
            weight=_string(item, "weight", item_where),
            rationale=_string(item, "rationale", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.pack_id for row in pack_overlays],
        f"{where}.pack_overlays",
        "content_pack_overlay (pack_id)",
    )

    resource_labels = _rows(
        document,
        "resource_labels",
        _RESOURCE_LABEL_KEYS,
        where,
        lambda item, item_where: ResourceLabelRow(
            ordinal=_ordinal(item, "ordinal", item_where),
            register=_optional_string(item, "register", item_where),
            usage_modality=_optional_string(
                item, "usage_modality", item_where
            ),
            genre=_optional_string(item, "genre", item_where),
            context=_optional_string(item, "context", item_where),
            style=_optional_string(item, "style", item_where),
            domain=_optional_string(item, "domain", item_where),
            variety=_optional_string(item, "variety", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.ordinal for row in resource_labels],
        f"{where}.resource_labels",
        "content_resource_label (ordinal)",
    )

    example_policy: ExamplePolicyRow | None = None
    if "example_policy" in document:
        policy_where = f"{where}.example_policy"
        block = _mapping(document["example_policy"], policy_where)
        _exact_keys(block, _EXAMPLE_POLICY_KEYS, policy_where)
        example_policy = ExamplePolicyRow(
            policy_version=_string(block, "policy_version", policy_where),
            policy=_string(block, "policy", policy_where),
        )

    typical_error_required: bool | None = None
    if "typical_error_required" in document:
        typical_error_required = _boolean(
            document, "typical_error_required", where
        )

    typical_errors = _rows(
        document,
        "typical_errors",
        _TYPICAL_ERROR_KEYS,
        where,
        lambda item, item_where: TypicalErrorRow(
            ordinal=_ordinal(item, "ordinal", item_where),
            learner_l1=_optional_string(item, "learner_l1", item_where),
            error_type=_string(item, "error_type", item_where),
            error_pattern=_string(item, "error_pattern", item_where),
            corrected_pattern=_string(item, "corrected_pattern", item_where),
            explanation=_string(item, "explanation", item_where),
            severity=_string(item, "severity", item_where),
            detection_policy=_string(item, "detection_policy", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.ordinal for row in typical_errors],
        f"{where}.typical_errors",
        "content_typical_error (ordinal)",
    )

    detection_policy: DetectionPolicyRow | None = None
    if "detection_policy" in document:
        policy_where = f"{where}.detection_policy"
        block = _mapping(document["detection_policy"], policy_where)
        _exact_keys(block, _DETECTION_POLICY_KEYS, policy_where)
        detection_policy = DetectionPolicyRow(
            policy_version=_string(block, "policy_version", policy_where),
            policy=_string(block, "policy", policy_where),
        )

    detection_rules = _rows(
        document,
        "detection_rules",
        _DETECTION_RULE_KEYS,
        where,
        lambda item, item_where: DetectionRuleRow(
            ordinal=_ordinal(item, "ordinal", item_where),
            rule=_string(item, "rule", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.ordinal for row in detection_rules],
        f"{where}.detection_rules",
        "content_detection_rule (ordinal)",
    )

    detection_fixtures = _rows(
        document,
        "detection_fixtures",
        _DETECTION_FIXTURE_KEYS,
        where,
        lambda item, item_where: DetectionFixtureRow(
            ordinal=_ordinal(item, "ordinal", item_where),
            kind=_vocabulary(
                _string(item, "kind", item_where),
                DETECTION_FIXTURE_KINDS,
                f"{item_where}.kind",
            ),
            text=_string(item, "text", item_where),
            expected=_string(item, "expected", item_where),
        ),
    )
    _refuse_duplicate_keys(
        [row.ordinal for row in detection_fixtures],
        f"{where}.detection_fixtures",
        "content_detection_fixture (ordinal)",
    )
    # C3-R2: a fixture is a checkable pair — the kind decides the expected
    # reading (elc.content.types.DETECTION_FIXTURE_EXPECTED_BY_KIND), so a
    # row whose ``expected`` disagrees with its own ``kind`` is refused. This
    # is the pairing tests/phase5 pinned over the corpus (the c2-a review F4
    # rule), now a source contract that covers the pre-existing rows too.
    for row in detection_fixtures:
        legal = DETECTION_FIXTURE_EXPECTED_BY_KIND[row.kind]
        if row.expected != legal:
            raise BuildError(
                f"{where}.detection_fixtures[{row.ordinal}]: kind "
                f"{row.kind!r} expects {legal!r}, got {row.expected!r}"
            )
    # C3-R2: every declared error_type must be instantiated by at least one
    # POSITIVE_ERROR fixture — a structure check only, never a judgement of
    # the English. Without a positive row per declared type a detector stub
    # answering NO_MATCH to everything would still pass the whole fixture
    # set, which is exactly the gap the third kind closes. The fixture row
    # carries no error_type column, so the check is the per-entity positive
    # row count against the distinct declared types (the corpus authors one
    # positive row per type).
    error_types = {row.error_type for row in typical_errors}
    positives = [row for row in detection_fixtures if row.kind == "POSITIVE_ERROR"]
    if len(positives) < len(error_types):
        raise BuildError(
            f"{where}.detection_fixtures: {len(error_types)} declared "
            "error_type(s) need at least one POSITIVE_ERROR fixture each; "
            f"the document declares {len(positives)}"
        )

    return EvidenceDoc(
        entity_id=entity_id,
        assessment_membership=assessment_membership,
        lexical_entry=lexical_entry,
        senses=senses,
        texts=texts,
        forms=forms,
        pedagogical_profile=pedagogical_profile,
        pack_overlays=pack_overlays,
        resource_labels=resource_labels,
        example_policy=example_policy,
        typical_error_required=typical_error_required,
        typical_errors=typical_errors,
        detection_policy=detection_policy,
        detection_rules=detection_rules,
        detection_fixtures=detection_fixtures,
    )


# ---------------------------------------------------------------------------
# C3-R2: the provenance audit records (content_src/audits/*.json)
# ---------------------------------------------------------------------------

#: The directory scanned for provenance audit records. Unlike the entity and
#: evidence trees the audits are **not** declared by the index: the directory
#: is scanned in file-name order, and an absent or empty directory is the
#: legal "no audits yet" state (every entity then stays at its
#: AUTHOR_DECLARED baseline). A non-``*.json`` file in the directory is not
#: a document the build reads, so it is not accounted for.
AUDITS_DIRNAME = "audits"

#: The strict key set of one audit record — the minimum a provenance claim
#: must state: which review it is (``audit_id``), who performed it
#: (``performed_by``), against what standard (``basis``), and which entities
#: it approves (``approved_entities``). ``format`` / ``format_version`` are
#: optional source-format declarations (validated when present, like every
#: other authoring document).
_AUDIT_KEYS = ("audit_id", "performed_by", "basis", "approved_entities")
_AUDIT_OPTIONAL_KEYS = ("format", "format_version")


@dataclass(frozen=True)
class AuditRecord:
    """One provenance audit record (`content_src/audits/<name>.json`, C3-R2).

    A record is a **third-party fact**, which is the whole point of the
    provenance dimension: an entity's level rises above AUTHOR_DECLARED only
    when a record outside the entity's own evidence document names it. The
    record states its own basis honestly (which review, by whom, against
    what); the build validates shape and references, never the review's
    judgement.
    """

    audit_id: str
    performed_by: str
    basis: str
    approved_entities: tuple[str, ...]


def _audits_from_directory(
    audits_dir: Path, entity_ids: frozenset[str]
) -> tuple[AuditRecord, ...]:
    """Scan `content_src/audits/*.json` in file-name order (C3-R2).

    An absent or empty directory answers no records — the legal "nothing has
    been audited yet" state, not an error. Every record that does exist is
    read strictly: unknown keys, missing keys, empty strings, a dangling
    entity reference in ``approved_entities`` or a repeated ``audit_id`` all
    raise :class:`BuildError`. Two records approving the same entity are
    fine (an entity is EDITOR_REVIEWED if **any** record approves it); two
    records with the same ``audit_id`` are not (the id is the record's
    identity, and a duplicate would make "which review was this?"
    ambiguous).
    """

    if not audits_dir.is_dir():
        return ()
    records: list[AuditRecord] = []
    seen_ids: set[str] = set()
    for path in sorted(audits_dir.glob("*.json")):
        where = str(path)
        document = _mapping(_read_json(path), where)
        _exact_keys(document, _AUDIT_KEYS, where, optional=_AUDIT_OPTIONAL_KEYS)
        if "format" in document:
            _format_declaration(document, CONTENT_SRC_FORMAT, where)
        elif "format_version" in document:
            raise BuildError(
                f"{where}: format_version without format (the declaration is "
                "one block, not two loose keys)"
            )
        audit_id = _string(document, "audit_id", where)
        if audit_id in seen_ids:
            raise BuildError(
                f"{where}: duplicate audit_id {audit_id!r} — the id is the "
                "record's identity and is already claimed by an earlier "
                "record"
            )
        seen_ids.add(audit_id)
        approved = _string_list(document, "approved_entities", where)
        for entity_id in approved:
            if entity_id not in entity_ids:
                raise BuildError(
                    f"{where}: approved_entities names {entity_id!r}, which "
                    "is not a declared content entity (a provenance approval "
                    "may not dangle)"
                )
        records.append(
            AuditRecord(
                audit_id=audit_id,
                performed_by=_string(document, "performed_by", where),
                basis=_string(document, "basis", where),
                approved_entities=tuple(approved),
            )
        )
    return tuple(records)


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
    "evidence",
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

    # C1: the readiness evidence tree. Declared by the index like `entities`
    # (no glob fallback), read through the same no-silent-skip guard, and
    # allowed to be empty — "this corpus states no readiness evidence" is a
    # legal source, and the artifact then carries none.
    evidence_paths = _document_list(
        content_index_path,
        content_index,
        "evidence",
        content_src_dir,
        content_src_dir / "evidence",
        allow_empty=True,
    )
    evidence = tuple(
        sorted(
            (
                _evidence_from_document(
                    path,
                    _mapping(_read_json(path), str(path)),
                    frozenset(entity.entity_id for entity in entities),
                )
                for path in evidence_paths
            ),
            key=lambda document: document.entity_id,
        )
    )
    if len({document.entity_id for document in evidence}) != len(evidence):
        raise BuildError(
            f"{content_src_dir}: two evidence documents declare the same entity"
        )

    # C3-R2: the provenance audit records. Scanned, not index-declared: the
    # directory's absence is the legal "nothing audited yet" state.
    audits = _audits_from_directory(
        content_src_dir / AUDITS_DIRNAME,
        frozenset(entity.entity_id for entity in entities),
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
        evidence=evidence,
        audits=audits,
    )
    _check_references(source, links_path, prerequisites_path)
    return source


#: The two provenance words the build's derivation can produce today, taken
#: from the vocabulary by position (the derivation may never invent a word).
_BASELINE_PROVENANCE = PROVENANCE_LEVELS[0]
_REVIEWED_PROVENANCE = PROVENANCE_LEVELS[1]


def _provenance_rows(source: ContentSource) -> tuple[tuple[str, str], ...]:
    """C3-R2: derive one provenance level per **documented** entity.

    The derivation is structural, never self-declared: the authoring source
    states no level anywhere. Baseline — an entity with an authoring evidence
    document is ``AUTHOR_DECLARED`` (the author states the facts, nothing has
    checked them). One step up — an entity named in ``approved_entities`` of
    at least one audit record is ``EDITOR_REVIEWED`` (the record is a
    third-party fact, so an author cannot promote their own work). No
    derivation produces ``EXECUTABLY_VERIFIED`` or
    ``EMPIRICALLY_CALIBRATED`` today: no detector executor exists to pass
    the fixtures (the N21 registration) and no real teaching run exists to
    calibrate against (rollout HOLD) — the words stay reachable-only, with
    their conditions written on
    :data:`elc.content.types.PROVENANCE_LEVELS`.

    Only documented entities get a row: a capability with no evidence
    document makes no provenance claim for the table to carry, and the
    ``entity_id`` primary key keeps one row per entity.
    """

    documented = sorted(document.entity_id for document in source.evidence)
    approved = {
        entity_id
        for record in source.audits
        for entity_id in record.approved_entities
    }
    return tuple(
        (
            entity_id,
            _REVIEWED_PROVENANCE if entity_id in approved else _BASELINE_PROVENANCE,
        )
        for entity_id in documented
    )


def _check_references(
    source: ContentSource, links_path: Path, prerequisites_path: Path
) -> None:
    """Referential integrity: nothing may point outside the declared sets.

    C3-R1 adds two rules over the declared-reading ``mapping_class`` column —
    both are *shape* rules, never semantic ones:

    - ``relation = REALIZES`` implies ``CURRICULUM_MAPPING``: a realization
      claim is a mapping claim, so a row may not say "this resource realizes
      the node" while declaring itself a coverage placement (the pair would
      make the artifact read as two contradictory claims);
    - ``CURRICULUM_MAPPING`` implies the node's capability **has** a
      functional definition: a mapping is only meaningful against a stated
      standard, so a mapping row naming a definition-less capability is
      refused at build time rather than stored as an audit that could not
      have been performed.

    The reverse directions stay legal on purpose: a placement row may name
    any declared capability (that is what "nearest available node" means),
    and a capability may carry a definition with no link at all.
    """

    entity_ids = set(source.entity_ids())
    capability_ids = set(source.capability_ids())
    defined_capabilities = {
        capability.capability_id
        for capability in source.capabilities
        if capability.functional_definition is not None
    }
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
        if (
            link.relation is CurriculumLinkRelation.REALIZES
            and link.mapping_class != CURRICULUM_MAPPING_CLASS
        ):
            raise BuildError(
                f"{links_path}: {link.resource_id!r} -> {link.node_id!r} "
                f"declares relation=REALIZES with mapping_class="
                f"{link.mapping_class!r}; a REALIZES row is a mapping claim "
                f"(C3-R1: REALIZES implies {CURRICULUM_MAPPING_CLASS})"
            )
        if (
            link.mapping_class == CURRICULUM_MAPPING_CLASS
            and link.node_id not in defined_capabilities
        ):
            raise BuildError(
                f"{links_path}: {link.resource_id!r} -> {link.node_id!r} "
                f"claims {CURRICULUM_MAPPING_CLASS}, but "
                f"{link.node_id!r} carries no functional_definition in "
                "curriculum/capabilities/ — a mapping cannot be a mapping of "
                "a capability with no stated standard"
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
        "editorial_status, mapping_class, rationale"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                link.resource_id,
                link.node_id,
                str(link.relation),
                link.strength,
                1 if link.primary_flag else 0,
                link.editorial_status,
                link.mapping_class,
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
    _write_evidence_rows(conn, source)


def _one(row: _T | None) -> tuple[_T, ...]:
    """Zero rows for an unstated single-row block, one row for a stated one."""

    return () if row is None else (row,)


def _write_evidence_rows(
    conn: sqlite3.Connection, source: ContentSource
) -> None:
    """C1: the readiness evidence rows, in table-creation order.

    Row order is a pure function of the source (the entity id, then the
    block's own declared order — ordinal-sorted where the table carries one,
    id-sorted where it is keyed by a source id), so reordering an authoring
    array cannot change the artifact's bytes. A row is written only for a
    block the source states: no table is padded, and an entity with no
    evidence document contributes nothing.
    """

    evidence = tuple(
        document
        for document in (
            source.evidence_of(entity.entity_id) for entity in source.entities
        )
        if document is not None
    )

    conn.executemany(
        "INSERT INTO content_assessment_membership ("
        "entity_id, assessment_id, membership_status, source"
        ") VALUES (?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.assessment_id,
                row.membership_status,
                row.source,
            )
            for document in evidence
            for row in sorted(
                document.assessment_membership, key=lambda row: row.assessment_id
            )
        ),
    )
    conn.executemany(
        "INSERT INTO content_lexical_entry (entity_id, lemma, pos) "
        "VALUES (?, ?, ?)",
        (
            (document.entity_id, row.lemma, row.pos)
            for document in evidence
            for row in _one(document.lexical_entry)
        ),
    )
    conn.executemany(
        "INSERT INTO content_sense (entity_id, sense_id, ordinal) "
        "VALUES (?, ?, ?)",
        (
            (document.entity_id, row.sense_id, row.ordinal)
            for document in evidence
            for row in sorted(document.senses, key=lambda row: row.sense_id)
        ),
    )
    conn.executemany(
        "INSERT INTO content_text ("
        "entity_id, sense_id, language, role, ordinal, text"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.sense_id,
                row.language,
                row.role,
                row.ordinal,
                row.text,
            )
            for document in evidence
            for row in sorted(
                document.texts, key=lambda row: (row.role, row.ordinal)
            )
        ),
    )
    conn.executemany(
        "INSERT INTO content_form ("
        "entity_id, form_id, written, normalized, form_type, morph_features, "
        "pronunciation"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.form_id,
                row.written,
                row.normalized,
                row.form_type,
                row.morph_features,
                row.pronunciation,
            )
            for document in evidence
            for row in sorted(document.forms, key=lambda row: row.form_id)
        ),
    )
    conn.executemany(
        "INSERT INTO content_pedagogical_profile ("
        "entity_id, core_utility, receptive_value, productive_value, "
        "receptive_difficulty, productive_difficulty, explanation_cost, "
        "transfer_value, naturalness_value, default_target_mode, "
        "editorial_status, rationale"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.core_utility,
                row.receptive_value,
                row.productive_value,
                row.receptive_difficulty,
                row.productive_difficulty,
                row.explanation_cost,
                row.transfer_value,
                row.naturalness_value,
                row.default_target_mode,
                row.editorial_status,
                row.rationale,
            )
            for document in evidence
            for row in _one(document.pedagogical_profile)
        ),
    )
    conn.executemany(
        "INSERT INTO content_pack_overlay ("
        "entity_id, pack_id, weight, rationale"
        ") VALUES (?, ?, ?, ?)",
        (
            (document.entity_id, row.pack_id, row.weight, row.rationale)
            for document in evidence
            for row in sorted(document.pack_overlays, key=lambda row: row.pack_id)
        ),
    )
    conn.executemany(
        "INSERT INTO content_resource_label ("
        "entity_id, ordinal, register, usage_modality, genre, context, style, "
        "domain, variety"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.ordinal,
                row.register,
                row.usage_modality,
                row.genre,
                row.context,
                row.style,
                row.domain,
                row.variety,
            )
            for document in evidence
            for row in sorted(document.resource_labels, key=lambda row: row.ordinal)
        ),
    )
    conn.executemany(
        "INSERT INTO content_example_policy ("
        "entity_id, policy_version, policy"
        ") VALUES (?, ?, ?)",
        (
            (document.entity_id, row.policy_version, row.policy)
            for document in evidence
            for row in _one(document.example_policy)
        ),
    )
    conn.executemany(
        "INSERT INTO content_typical_error ("
        "entity_id, ordinal, learner_l1, error_type, error_pattern, "
        "corrected_pattern, explanation, severity, detection_policy"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.ordinal,
                row.learner_l1,
                row.error_type,
                row.error_pattern,
                row.corrected_pattern,
                row.explanation,
                row.severity,
                row.detection_policy,
            )
            for document in evidence
            for row in sorted(document.typical_errors, key=lambda row: row.ordinal)
        ),
    )
    conn.executemany(
        "INSERT INTO content_detection_policy ("
        "entity_id, policy_version, policy"
        ") VALUES (?, ?, ?)",
        (
            (document.entity_id, row.policy_version, row.policy)
            for document in evidence
            for row in _one(document.detection_policy)
        ),
    )
    conn.executemany(
        "INSERT INTO content_detection_rule (entity_id, ordinal, rule) "
        "VALUES (?, ?, ?)",
        (
            (document.entity_id, row.ordinal, row.rule)
            for document in evidence
            for row in sorted(document.detection_rules, key=lambda row: row.ordinal)
        ),
    )
    conn.executemany(
        "INSERT INTO content_detection_fixture ("
        "entity_id, ordinal, kind, text, expected"
        ") VALUES (?, ?, ?, ?, ?)",
        (
            (
                document.entity_id,
                row.ordinal,
                row.kind,
                row.text,
                row.expected,
            )
            for document in evidence
            for row in sorted(
                document.detection_fixtures, key=lambda row: row.ordinal
            )
        ),
    )
    # The one §8.1 declaration that is not a row set: "this target needs a
    # TypicalError" (§24.9's need, carried as a declared-reading content_meta
    # key — elc.content.types.typical_error_required_key). Written only when
    # the source declares it, so "declared false" and "declared nothing" stay
    # distinguishable in the source even though both satisfy §8.1's
    # conditional fact.
    conn.executemany(
        "INSERT INTO content_meta (key, value) VALUES (?, ?)",
        (
            (
                typical_error_required_key(document.entity_id),
                "true" if document.typical_error_required else "false",
            )
            for document in evidence
            if document.typical_error_required is not None
        ),
    )
    # C3-R2: the derived provenance rows (one per documented entity, in the
    # derivation's sorted-entity-id order — deterministic by construction).
    conn.executemany(
        "INSERT INTO content_provenance (entity_id, provenance_level) "
        "VALUES (?, ?)",
        _provenance_rows(source),
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
        evidence_count=len(source.evidence),
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
        f"links={report.link_count}, prerequisites={report.prerequisite_count}, "
        f"evidence={report.evidence_count})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
