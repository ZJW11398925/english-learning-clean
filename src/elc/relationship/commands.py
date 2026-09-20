"""Relationship domain command face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import RelationshipMemoryId, Result
from elc.relationship.types import RelationshipMemoryProposal


@runtime_checkable
class RelationshipCommands(Protocol):
    """Proposal → validate/dedupe → canonical memory (docs/DOMAIN_MODEL.md §5)."""

    def propose_memory(
        self, proposal: RelationshipMemoryProposal
    ) -> Result[RelationshipMemoryId]:
        """Controller decides VALIDATE/COMMIT/REJECT/ABSTAIN (§18)."""
        ...

    def supersede_memory(
        self, memory_id: RelationshipMemoryId, replacement: str
    ) -> Result[RelationshipMemoryId]:
        ...
