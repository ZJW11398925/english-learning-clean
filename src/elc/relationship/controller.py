"""Empty Relationship Domain Controller (Post-BF Phase 4 will implement)."""

from __future__ import annotations

from elc.platform.types import (
    PersonaId,
    RelationshipMemoryId,
    Result,
    UserId,
)
from elc.relationship.types import (
    RelationshipMemoryProposal,
    RelationshipMemoryRecord,
    RelationshipView,
)


class RelationshipController:
    """Owns Persona×User memory truth. Phase 0: no logic."""

    def propose_memory(
        self, proposal: RelationshipMemoryProposal
    ) -> Result[RelationshipMemoryId]:
        raise NotImplementedError("Phase 4: recorder proposal validation")

    def supersede_memory(
        self, memory_id: RelationshipMemoryId, replacement: str
    ) -> Result[RelationshipMemoryId]:
        raise NotImplementedError("Phase 4: append-first supersede")

    def get_relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView]:
        raise NotImplementedError("Phase 4: RelationshipView projection")

    def get_memory(
        self, memory_id: RelationshipMemoryId
    ) -> Result[RelationshipMemoryRecord | None]:
        raise NotImplementedError("Phase 4: memory read")
