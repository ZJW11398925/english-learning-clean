"""Empty World/Lore Domain Controller (later phase will implement)."""

from __future__ import annotations

from elc.platform.types import ConversationId, Result, WorldLoreFactId
from elc.world_lore.types import WorldLoreProposal, WorldLoreRecord, WorldLoreView


class WorldLoreController:
    """Owns canonical world facts. Phase 0: no logic."""

    def propose_lore_fact(
        self, proposal: WorldLoreProposal
    ) -> Result[WorldLoreFactId]:
        raise NotImplementedError("World/Lore proposal validation")

    def supersede_lore_fact(
        self, fact_id: WorldLoreFactId, replacement: WorldLoreRecord
    ) -> Result[WorldLoreFactId]:
        raise NotImplementedError("World/Lore append-first supersede")

    def resolve_world_lore_view(
        self, conversation_id: ConversationId
    ) -> Result[WorldLoreView]:
        raise NotImplementedError("World/Lore view resolution")

    def get_lore_fact(
        self, fact_id: WorldLoreFactId
    ) -> Result[WorldLoreRecord | None]:
        raise NotImplementedError("World/Lore fact read")
