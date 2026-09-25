"""Empty World/Lore Domain Controller — a Phase 0 red-line skeleton, and this
package has **no live face yet**.

`tests/architecture/test_gate_1_domain_interfaces.py` requires every method
below to raise ``NotImplementedError`` (the Phase 0 red line), and
``tests/architecture/test_surface_census.py`` records ``elc.world_lore``
honestly: the package holds two Protocols (``WorldLoreCommands`` /
``WorldLoreQueries``), the type shapes, and this skeleton — nothing implements
them, and the view Persona consumes is injected. Revisit: an implementation
lands — then the census row gains a live face and this banner's claim moves
into that table.
"""

from __future__ import annotations

from elc.platform.types import ConversationId, Result, WorldLoreFactId
from elc.world_lore.types import WorldLoreProposal, WorldLoreRecord, WorldLoreView


class WorldLoreController:
    """Owns canonical world facts. Phase 0 red line: no logic."""

    def propose_lore_fact(
        self, proposal: WorldLoreProposal
    ) -> Result[WorldLoreFactId]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — and elc.world_lore has no live"
            " face yet; see SURFACE_CENSUS (proposal validation)"
        )

    def supersede_lore_fact(
        self, fact_id: WorldLoreFactId, replacement: WorldLoreRecord
    ) -> Result[WorldLoreFactId]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — and elc.world_lore has no live"
            " face yet; see SURFACE_CENSUS (append-first supersede)"
        )

    def resolve_world_lore_view(
        self, conversation_id: ConversationId
    ) -> Result[WorldLoreView]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — and elc.world_lore has no live"
            " face yet; the view Persona consumes is injected (view"
            " resolution)"
        )

    def get_lore_fact(
        self, fact_id: WorldLoreFactId
    ) -> Result[WorldLoreRecord | None]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — and elc.world_lore has no live"
            " face yet; see SURFACE_CENSUS (fact read)"
        )
