"""Relationship domain — Persona×User relationship memory.

Unit: Persona × User (docs/DOMAIN_MODEL.md §5). Memories never cross
Personas (§17). Persona subjective impressions never automatically become
Teaching Facts, and Relationship Memory never affects mastery (D-INV-005).

Write flow (§5): Relationship Recorder proposal → validate/dedupe by the
Domain Controller → canonical Relationship Memory.
Projection failure never rolls back the conversation turn.

Phase 4 P4-0 (TASK-OPI-5ba74efc-….84 ③): the durable column set of the
``relationship_memory`` table (migrations/0009) is mirrored here — both the
column *names* and the vocabularies follow the canonical text (canonical
outranks this module: the Phase 0 skeleton spellings ``memory_id`` /
``content`` / ``USER_STATED`` / ``SYSTEM_INFERRED`` were superseded by
docs/DATA_MODEL.md §23 and docs/DOMAIN_MODEL.md §5 in the P4-0 review
round). The write faces that fill the new columns are P4-1. The privacy
vocabulary follows
behavioral_baselines/security/security_privacy_policy_v1.json (BF-05,
read-only baseline) and docs/DOMAIN_MODEL.md §18.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import PersonaId, RelationshipMemoryId, TurnId, UserId


class RelationshipMemoryType(StrEnum):
    """docs/DOMAIN_MODEL.md §5 "Memory types", word for word (eight)."""

    USER_STATED_FACT = "USER_STATED_FACT"
    SHARED_EVENT = "SHARED_EVENT"
    PERSONA_IMPRESSION = "PERSONA_IMPRESSION"
    PROMISE = "PROMISE"
    OPEN_THREAD = "OPEN_THREAD"
    RUNNING_JOKE = "RUNNING_JOKE"
    RELATIONSHIP_EVENT = "RELATIONSHIP_EVENT"
    CONVERSATION_PREFERENCE = "CONVERSATION_PREFERENCE"


class MemoryProvenance(StrEnum):
    """docs/DOMAIN_MODEL.md §5 "Important distinction", word for word:

        USER_STATED_FACT
        SYSTEM_INFERRED_FACT
        PERSONA_IMPRESSION

    The Phase 0 skeleton spelled the first two ``USER_STATED`` /
    ``SYSTEM_INFERRED``; P4-0 F-B aligned them to the canonical words. The
    frozen BF-05 baseline corroborates that spelling independently
    (security_benchmark_v1.json ``proposal_kind`` =
    "USER_STATED_FACT" / "SYSTEM_INFERRED_FACT";
    SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md §289). Note that §5's
    distinction block reuses two of the §5 memory-type words — a stated fact
    and an inferred fact are also memory *types* — so the two enums overlap
    by canonical design, not by accident.
    """

    USER_STATED_FACT = "USER_STATED_FACT"
    SYSTEM_INFERRED_FACT = "SYSTEM_INFERRED_FACT"
    PERSONA_IMPRESSION = "PERSONA_IMPRESSION"


class MemoryStatus(StrEnum):
    """Append-first: corrections supersede, history is not erased."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class MemorySensitivityClass(StrEnum):
    """The BF-05 data class a relationship memory row carries.

    behavioral_baselines/security/security_privacy_policy_v1.json
    ``data_classes``: PERSONAL is the class whose examples include
    "relationship memories"; HIGH_SENSITIVITY is the class pinned to
    ``auto_promote_to_durable_memory = false`` and
    ``explicit_persistence_required = true``. Those are the only two classes
    legal for a relationship memory — the durable CHECK in migration 0009
    enforces the same pair.
    """

    PERSONAL = "PERSONAL"
    HIGH_SENSITIVITY = "HIGH_SENSITIVITY"


class PersistenceAuthorization(StrEnum):
    """The authorization one memory row was persisted under (BF-05
    ``trust_classes`` / ``sensitive_memory_policy`` + docs/DOMAIN_MODEL.md
    §18.1).

    VALIDATED_DOMAIN_WRITE is the ordinary path — a TRUSTED_AUTHORITY
    "domain-validated canonical write" through the §5 write flow
    (Recorder proposal → validate/dedupe → canonical memory).
    USER_EXPLICIT_CONSENT is the high-sensitivity path: §18.1 "高敏感
    Profile/Relationship persistence 需要显式用户许可", so a
    HIGH_SENSITIVITY row is only legal under this value (the cross-column
    CHECK in migration 0009).
    """

    VALIDATED_DOMAIN_WRITE = "VALIDATED_DOMAIN_WRITE"
    USER_EXPLICIT_CONSENT = "USER_EXPLICIT_CONSENT"


@dataclass(frozen=True)
class RelationshipMemoryRecord:
    """One canonical memory row (Persona×User scoped).

    Every field mirrors one durable column, and the names are
    docs/DATA_MODEL.md §23's: ``relationship_memory_id`` and
    ``canonical_content`` (the Phase 0 skeleton's ``memory_id`` / ``content``
    were superseded by the canonical text in the P4-0 review round; the
    columns DEC-…5ba74efc.68 authorizes beyond §23 are marked in the
    migration's trace). The last ten fields carry defaults so the Phase 0
    construction shape stays callable: the *write* faces that must fill them
    are P4-1, and no consumer exists before that.
    """

    relationship_memory_id: RelationshipMemoryId
    persona_id: PersonaId
    user_id: UserId
    memory_type: RelationshipMemoryType
    provenance: MemoryProvenance
    canonical_content: str
    source_turn_id: TurnId | None
    status: MemoryStatus
    #: §23 ``source_turn_ids[]`` — every turn the memory was read from, in
    #: durable order (``source_turn_id`` stays the single originating turn).
    source_turn_ids: tuple[TurnId, ...] = ()
    #: The durable refs the memory was derived from (turn / message ids):
    #: the BF-05 traceability requirement for relationship writes (§18.1).
    provenance_refs: tuple[str, ...] = ()
    #: §23 ``confidence?`` — NULL/None for a user-stated memory, a score for
    #: a validated inference (the §5 distinction).
    confidence: float | None = None
    #: Append-first supersede link: this row replaces that one (§1.3).
    supersedes_memory_id: RelationshipMemoryId | None = None
    #: §1.4 "version every derived model" — the Recorder that proposed it.
    recorder_version: str = ""
    #: The validator that committed it; None when the write came through a
    #: TRUSTED_AUTHORITY typed/validated command instead of a
    #: model-assisted validator (docs/DOMAIN_MODEL.md §18.1).
    validator_version: str | None = None
    sensitivity_class: MemorySensitivityClass = MemorySensitivityClass.PERSONAL
    persistence_authorization: PersistenceAuthorization = (
        PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
    )
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class RelationshipMemoryProposal:
    """Recorder proposal — not yet canonical; Controller validates/dedupes.

    A proposal is a §18 proposal-only value, not the durable row: its
    ``content`` field is the recorder's candidate text, which becomes the
    canonical row's ``canonical_content`` (§23) once the controller commits
    it. The field name is deliberately left as the recorder's own here —
    canonical names the *row*, and the row's type is
    :class:`RelationshipMemoryRecord`.
    """

    persona_id: PersonaId
    user_id: UserId
    memory_type: RelationshipMemoryType
    provenance: MemoryProvenance
    content: str
    source_turn_id: TurnId | None


@dataclass(frozen=True)
class RelationshipView:
    """Persona Runtime consumption view (docs/DOMAIN_MODEL.md §4)."""

    persona_id: PersonaId
    user_id: UserId
    active_memories: tuple[RelationshipMemoryRecord, ...]
