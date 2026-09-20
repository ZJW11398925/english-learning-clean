"""World/Lore domain command face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import Result, WorldLoreFactId
from elc.world_lore.types import WorldLoreProposal, WorldLoreRecord


@runtime_checkable
class WorldLoreCommands(Protocol):
    """Untrusted lore proposals → validated canonical world facts
    (docs/DOMAIN_MODEL.md §18 proposal-only; P-INV-013)."""

    def propose_lore_fact(
        self, proposal: WorldLoreProposal
    ) -> Result[WorldLoreFactId]:
        """Controller decides VALIDATE/COMMIT/REJECT/ABSTAIN (§18)."""
        ...

    def supersede_lore_fact(
        self, fact_id: WorldLoreFactId, replacement: WorldLoreRecord
    ) -> Result[WorldLoreFactId]:
        ...
