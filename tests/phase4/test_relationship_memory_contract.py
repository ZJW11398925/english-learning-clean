"""P4-0 ③ — the relationship_memory contract (schema ↔ record type).

The table is DDL in this slice: the Recorder / validate-dedupe / append-first
supersede write faces are P4-1 (docs/DOMAIN_MODEL.md §5 write flow; the task
book's forbidden_changes). What is pinned here is the contract those faces
will have to satisfy:

- the record type and the durable column set cannot drift (every field of
  ``RelationshipMemoryRecord`` is a column, every column a field — the
  migration's per-column trace is the authority for the extra ones);
- the vocabularies are the canonical ones: the eight §5 memory types word
  for word, the §5 provenance distinction, and the two BF-05 sensitivity
  classes / persistence authorizations;
- the personas never cross (§17): the scope key is (persona_id, user_id);
- the write face is deliberately still unimplemented (no pretend P4-1).
"""

from __future__ import annotations

import dataclasses
import sqlite3

import pytest

from elc.platform.db import migrations
from elc.platform.types import PersonaId, RelationshipMemoryId, UserId
from elc.relationship.controller import RelationshipController
from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    MemoryStatus,
    PersistenceAuthorization,
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipMemoryType,
)

#: docs/DOMAIN_MODEL.md §5 "Memory types", word for word (the same eight
#: words the migration's CHECK pins).
CANONICAL_MEMORY_TYPES = (
    "USER_STATED_FACT",
    "SHARED_EVENT",
    "PERSONA_IMPRESSION",
    "PROMISE",
    "OPEN_THREAD",
    "RUNNING_JOKE",
    "RELATIONSHIP_EVENT",
    "CONVERSATION_PREFERENCE",
)

#: docs/DATA_MODEL.md §23's column names, verbatim (P4-0 F-A: the canonical
#: text is the naming authority — the Phase 0 skeleton's ``memory_id`` /
#: ``content`` were superseded by ``relationship_memory_id`` /
#: ``canonical_content``). Listed in §23's own order.
SECTION_23_COLUMNS = (
    "relationship_memory_id",
    "user_id",
    "persona_id",
    "memory_type",
    "canonical_content",
    "source_turn_ids",
    "confidence",
    "status",
    "created_at",
    "updated_at",
)

#: The 增列 the P4-0 review authorized (DEC-…5ba74efc.68 C/F): §23 carries
#: none of them, each is required by the cited rule (the migration's trace
#: carries the reason per column).
DEC_68_ADDED_COLUMNS = (
    "provenance",
    "source_turn_id",
    "provenance_refs",
    "supersedes_memory_id",
    "recorder_version",
    "validator_version",
    "sensitivity_class",
    "persistence_authorization",
)

#: The physical table/record order (implementation-defined, DATA_MODEL §27):
#: identity → scope → type/provenance → content → source → status → additions
#: → timestamps. Both the durable columns and the record fields must be
#: exactly this.
P4_0_FIELDS = (
    "relationship_memory_id",
    "persona_id",
    "user_id",
    "memory_type",
    "provenance",
    "canonical_content",
    "source_turn_id",
    "status",
    "source_turn_ids",
    "provenance_refs",
    "confidence",
    "supersedes_memory_id",
    "recorder_version",
    "validator_version",
    "sensitivity_class",
    "persistence_authorization",
    "created_at",
    "updated_at",
)


def test_the_record_type_mirrors_the_durable_column_set(
    db: sqlite3.Connection,
) -> None:
    migrations.apply_migrations(db)
    columns = [
        str(row[1])
        for row in db.execute("PRAGMA table_info(relationship_memory)").fetchall()
    ]
    fields = tuple(field.name for field in dataclasses.fields(
        RelationshipMemoryRecord
    ))
    assert columns == list(P4_0_FIELDS)
    assert fields == P4_0_FIELDS
    # The set is exactly §23 + the authorized additions — no third source of
    # column names, and no §23 column silently dropped.
    assert set(P4_0_FIELDS) == set(SECTION_23_COLUMNS) | set(
        DEC_68_ADDED_COLUMNS
    )
    assert len(P4_0_FIELDS) == len(SECTION_23_COLUMNS) + len(
        DEC_68_ADDED_COLUMNS
    )
    # The Phase 0 construction shape stays callable (the additions carry
    # defaults: the P4-1 write faces are the ones that must fill them).
    record = RelationshipMemoryRecord(
        relationship_memory_id=RelationshipMemoryId("rm-1"),
        persona_id=PersonaId("persona-1"),
        user_id=UserId("user-1"),
        memory_type=RelationshipMemoryType.USER_STATED_FACT,
        provenance=MemoryProvenance.USER_STATED_FACT,
        canonical_content="I work as a nurse.",
        source_turn_id=None,
        status=MemoryStatus.ACTIVE,
    )
    assert record.sensitivity_class is MemorySensitivityClass.PERSONAL
    assert (
        record.persistence_authorization
        is PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
    )
    assert record.validator_version is None
    assert record.confidence is None


def test_the_vocabularies_are_the_canonical_ones() -> None:
    assert tuple(item.value for item in RelationshipMemoryType) == (
        CANONICAL_MEMORY_TYPES
    )
    # DOMAIN_MODEL §5 "Important distinction", word for word (P4-0 F-B: the
    # Phase 0 skeleton spelled the first two USER_STATED / SYSTEM_INFERRED;
    # the canonical words are the _FACT ones — the frozen BF-05 baseline
    # spells proposal_kind the same way).
    assert tuple(item.value for item in MemoryProvenance) == (
        "USER_STATED_FACT",
        "SYSTEM_INFERRED_FACT",
        "PERSONA_IMPRESSION",
    )
    # §5's distinction block reuses two of the memory-type words by canonical
    # design (a stated fact / an impression are also memory types); the third
    # word — SYSTEM_INFERRED_FACT — exists only as a provenance word.
    provenance_words = {item.value for item in MemoryProvenance}
    assert provenance_words & set(CANONICAL_MEMORY_TYPES) == {
        "USER_STATED_FACT",
        "PERSONA_IMPRESSION",
    }
    assert "SYSTEM_INFERRED_FACT" not in CANONICAL_MEMORY_TYPES
    # §23 pins no status vocabulary; these three words are the
    # implementation-defined spelling kept from the Phase 0 record.
    assert tuple(item.value for item in MemoryStatus) == (
        "ACTIVE",
        "SUPERSEDED",
        "WITHDRAWN",
    )
    # BF-05 data_classes applicable to relationship memory + the two
    # authorizations (sensitive_memory_policy / trust_classes).
    assert tuple(item.value for item in MemorySensitivityClass) == (
        "PERSONAL",
        "HIGH_SENSITIVITY",
    )
    assert tuple(item.value for item in PersistenceAuthorization) == (
        "VALIDATED_DOMAIN_WRITE",
        "USER_EXPLICIT_CONSENT",
    )


def test_the_scope_key_is_the_persona_user_pair(db: sqlite3.Connection) -> None:
    """§17: "Relationship 不跨 Persona 泄漏" — one memory row is always one
    (persona, user) pair, spelled out in the schema's NOT NULLs."""

    migrations.apply_migrations(db)
    info = {
        str(row[1]): (int(row[3]), int(row[5]))
        for row in db.execute("PRAGMA table_info(relationship_memory)").fetchall()
    }
    # NOT NULL for persona_id / user_id (the §5 unit's two legs)...
    assert info["persona_id"][0] == 1
    assert info["user_id"][0] == 1
    # ... and relationship_memory_id as the primary key (the pk ordinal,
    # matching every other table in this repository: `TEXT PRIMARY KEY`, no
    # redundant NOT NULL, the sqlite uniqueness index is what enforces the
    # identity).
    assert info["relationship_memory_id"][1] == 1


def test_the_recorder_write_face_is_still_unimplemented() -> None:
    """No pretend P4-1: the Recorder/validate/supersede faces still refuse to
    run, and the P4-G1 gate skeleton (tests/phase4/test_p4_g1_recorder_gate)
    is what P4-1 must satisfy when it lands."""

    controller = RelationshipController()
    with pytest.raises(NotImplementedError):
        controller.propose_memory(
            RelationshipMemoryProposal(
                persona_id=PersonaId("persona-1"),
                user_id=UserId("user-1"),
                memory_type=RelationshipMemoryType.USER_STATED_FACT,
                provenance=MemoryProvenance.USER_STATED_FACT,
                # The proposal carries the recorder's candidate text; the
                # canonical row names it canonical_content (§23).
                content="I work as a nurse.",
                source_turn_id=None,
            )
        )
    with pytest.raises(NotImplementedError):
        controller.get_memory(RelationshipMemoryId("rm-1"))
