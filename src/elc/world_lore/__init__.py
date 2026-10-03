"""World/Lore — canonical world facts (scenes, NPCs, places, rules).

docs/DOMAIN_MODEL.md §2 Authority Matrix; docs/DATA_MODEL.md §5.1;
docs/PRODUCT_CONTRACT.md §World/Lore. Persona Runtime consumes the
resolved WorldLoreView; lore content is untrusted (P-INV-013). 主线-3
(DEC-OPI-32409938…36): the live face is the controller over
:mod:`elc.world_lore.store` (migration 0020); the shipped world-fact
batch seeds from :mod:`elc.world_lore.content`.
"""

from elc.world_lore.commands import WorldLoreCommands
from elc.world_lore.controller import WorldLoreController
from elc.world_lore.queries import WorldLoreQueries
from elc.world_lore.store import SqliteWorldLoreStore
from elc.world_lore.types import (
    NullWorldLoreView,
    WorldLoreFactKind,
    WorldLoreProposal,
    WorldLoreRecord,
    WorldLoreView,
)

__all__ = [
    "NullWorldLoreView",
    "SqliteWorldLoreStore",
    "WorldLoreCommands",
    "WorldLoreController",
    "WorldLoreFactKind",
    "WorldLoreProposal",
    "WorldLoreQueries",
    "WorldLoreRecord",
    "WorldLoreView",
]
