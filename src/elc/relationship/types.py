"""Relationship domain — Persona×User relationship memory.

Unit: Persona × User (docs/DOMAIN_MODEL.md §5). Memories never cross
Personas (§17). Persona subjective impressions never automatically become
Teaching Facts, and Relationship Memory never affects mastery (D-INV-005).

Write flow (§5): Relationship Recorder proposal → validate/dedupe by the
Domain Controller → canonical Relationship Memory.
Projection failure never rolls back the conversation turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import PersonaId, RelationshipMemoryId, TurnId, UserId


class RelationshipMemoryType(StrEnum):
    """docs/DOMAIN_MODEL.md §5 memory types."""

    USER_STATED_FACT = "USER_STATED_FACT"
    SHARED_EVENT = "SHARED_EVENT"
    PERSONA_IMPRESSION = "PERSONA_IMPRESSION"
    PROMISE = "PROMISE"
    OPEN_THREAD = "OPEN_THREAD"
    RUNNING_JOKE = "RUNNING_JOKE"
    RELATIONSHIP_EVENT = "RELATIONSHIP_EVENT"
    CONVERSATION_PREFERENCE = "CONVERSATION_PREFERENCE"


class MemoryProvenance(StrEnum):
    """§5 important distinction: stated facts vs system inference vs opinion."""

    USER_STATED = "USER_STATED"
    SYSTEM_INFERRED = "SYSTEM_INFERRED"
    PERSONA_IMPRESSION = "PERSONA_IMPRESSION"


class MemoryStatus(StrEnum):
    """Append-first: corrections supersede, history is not erased."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


@dataclass(frozen=True)
class RelationshipMemoryRecord:
    """One canonical memory row (Persona×User scoped)."""

    memory_id: RelationshipMemoryId
    persona_id: PersonaId
    user_id: UserId
    memory_type: RelationshipMemoryType
    provenance: MemoryProvenance
    content: str
    source_turn_id: TurnId | None
    status: MemoryStatus


@dataclass(frozen=True)
class RelationshipMemoryProposal:
    """Recorder proposal — not yet canonical; Controller validates/dedupes."""

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
