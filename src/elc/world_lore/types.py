"""World/Lore bounded context — canonical world facts authority.

Owns (docs/DOMAIN_MODEL.md §2 Authority Matrix: "World/Lore canonical
facts → World/Lore"): canonical records for scenes, NPCs, places and
rules (docs/PRODUCT_CONTRACT.md §World/Lore).

Boundaries:
- Persona Runtime consumes the resolved WorldLoreView but never owns lore
  truth (docs/DATA_MODEL.md §5.1: "World/Lore canonical records are owned
  by World/Lore authority；Persona Runtime receives resolved
  WorldLoreView。"; docs/RUNTIME_ARCHITECTURE.md GenerationContext).
- Lore content is UNTRUSTED_CONTENT (docs/DOMAIN_MODEL.md §18.1;
  P-INV-013): user free text / Persona card / Lore never gains canonical
  memory write authority — writes enter as proposals validated by the
  Domain Controller (VALIDATE/COMMIT/REJECT/ABSTAIN, §18).

Phase 0: schema + interface skeleton only, no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import WorldLoreFactId


class WorldLoreFactKind(StrEnum):
    """docs/PRODUCT_CONTRACT.md §World/Lore: 场景、NPC、地点、规则."""

    SCENE = "SCENE"
    NPC = "NPC"
    PLACE = "PLACE"
    RULE = "RULE"


@dataclass(frozen=True)
class WorldLoreRecord:
    """One canonical world fact (schema stub, docs/DATA_MODEL.md §5.1)."""

    world_lore_fact_id: WorldLoreFactId
    fact_kind: WorldLoreFactKind
    canonical_key: str
    statement: str


@dataclass(frozen=True)
class WorldLoreProposal:
    """Untrusted-content proposal (P-INV-013): the Controller decides
    VALIDATE/COMMIT/REJECT/ABSTAIN before anything becomes canonical."""

    fact_kind: WorldLoreFactKind
    canonical_key: str
    statement: str
    source: str  # free text / persona card / model output — never a write authority


@dataclass(frozen=True)
class WorldLoreView:
    """The resolved view handed to Persona Runtime
    (docs/RUNTIME_ARCHITECTURE.md GenerationContext: WorldLoreView)."""

    facts: tuple[WorldLoreRecord, ...] = ()


@dataclass(frozen=True)
class NullWorldLoreView(WorldLoreView):
    """Explicit provider boundary for `world_lore_view` consumers.

    Persona's PromptCompilationRequest already carries a
    `world_lore_view` slot; this null object makes "no lore resolution
    available yet" an explicit, typed state instead of an ambiguous
    None. World/Lore resolution is deferred to a later phase
    (docs/DECISION_REGISTER.md Explicitly Deferred: multi-character Scene
    Runtime)."""

    deferred_reason: str = "WORLD_LORE_RESOLUTION_DEFERRED"
