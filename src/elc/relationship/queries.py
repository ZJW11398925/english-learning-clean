"""Relationship domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import PersonaId, RelationshipMemoryId, Result, UserId
from elc.relationship.types import RelationshipMemoryRecord, RelationshipView


@runtime_checkable
class RelationshipQueries(Protocol):
    """Persona×User scoped reads; never cross-Persona (docs/DOMAIN_MODEL.md §17)."""

    def get_relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView]:
        ...

    def get_memory(
        self, memory_id: RelationshipMemoryId
    ) -> Result[RelationshipMemoryRecord | None]:
        ...
