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
  Domain Controller (VALIDATE/COMMIT/REJECT/ABSTAIN, §18). The durable
  form of that boundary since 主线-3 (DEC-OPI-32409938…36): a proposal
  lands as a PENDING row no view ever serves; the controller is the
  authority face over :mod:`elc.world_lore.store` (migration 0020).

These type shapes are the implementation contract the table columns were
derived from; the table reading itself is implementation-defined (the
declared Revisit: canonical grows a table definition — this reading
aligns to it).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from elc.platform.types import ConversationId, Result, WorldLoreFactId


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


#: How many recent chronicle events the view carries (wr-12,
#: DEC-OPI-c73dbff3…84 R1: "近 5 条" — restraint: her recent past is not
#: the whole history). The composition root slices the world's chronicle
#: to this window; the view itself is shaped, not enforced, so a test
#: hand-building a wider view still compiles — the window is the
#: assembly's duty, pinned where the slicing lives.
RECENT_WORLD_EVENT_WINDOW = 5


@dataclass(frozen=True)
class WorldChronicleEntry:
    """One recent world event as Persona Runtime sees it (wr-12,
    DEC-OPI-c73dbff3…84 R1).

    ``occurred_at`` is the chronicle entry's own moment word (the durable
    ``world_event.occurred_at`` verbatim — the view is a reading, never a
    re-stamp); ``narration`` is the event's prose verbatim. Both are
    **non-empty** by construction (an event with no moment or no prose is
    not a fact anyone could read — a ValueError at construction, the
    PoolEvent ``__post_init__`` precedent in :mod:`elc.world.types`).
    """

    occurred_at: str
    narration: str

    def __post_init__(self) -> None:
        if not self.occurred_at:
            raise ValueError(
                "WorldChronicleEntry.occurred_at must be non-empty"
            )
        if not self.narration:
            raise ValueError(
                "WorldChronicleEntry.narration must be non-empty"
            )


@dataclass(frozen=True)
class WorldChronicleView:
    """The resolved recent-events view handed to Persona Runtime (wr-12,
    DEC-OPI-c73dbff3…84 R1) — the conversation's world's recent
    chronicle, **oldest first**, at most
    :data:`RECENT_WORLD_EVENT_WINDOW` entries.

    The worlddynamic half of the lore pairing: ``WorldLoreView`` is the
    static setting (the town's shape), ``WorldChronicleView`` is what has
    just been happening in it (the durable ``world_event`` narrations —
    wr-2's per-turn chronicle, now readable by the role it happens
    around). An empty ``events`` tuple is legal — the honest "world
    resolved, nothing has happened yet"; the compiler renders no section
    for it, exactly like an empty ``WorldLoreView``.
    """

    events: tuple[WorldChronicleEntry, ...] = ()


@runtime_checkable
class WorldChronicleQueries(Protocol):
    """The conversation→world-chronicle read (wr-12, DEC-OPI-c73dbff3…84
    R2) — the port the composition root wires so each turn's reply prompt
    carries the world's recent events.

    Declared beside the view shape it resolves, in this module's family;
    its ``WorldLoreQueries`` sibling lives in :mod:`elc.world_lore.queries`
    (the domain's query face). Registered Revisit: the next cut that
    touches that module moves this declaration next to the sibling — the
    protocol is structural, so the composition root's implementation and
    the coordinator's port annotation need no import of it either way.
    """

    def resolve_world_chronicle_view(
        self, conversation_id: ConversationId
    ) -> Result[WorldChronicleView]:
        ...
