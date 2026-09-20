"""World/Lore domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import ConversationId, Result, WorldLoreFactId
from elc.world_lore.types import WorldLoreRecord, WorldLoreView


@runtime_checkable
class WorldLoreQueries(Protocol):
    """Reads for the resolved view Persona Runtime consumes
    (docs/DATA_MODEL.md §5.1; docs/RUNTIME_ARCHITECTURE.md
    GenerationContext)."""

    def resolve_world_lore_view(
        self, conversation_id: ConversationId
    ) -> Result[WorldLoreView]:
        ...

    def get_lore_fact(
        self, fact_id: WorldLoreFactId
    ) -> Result[WorldLoreRecord | None]:
        ...
