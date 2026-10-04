"""The World bounded context — identity binding skeleton (W-1-0).

W-1-0 is the living-world program's first cut (direction
DEC-OPI-7e3744ee…2, the user's living-world mainline; the program's
opening ruling DEC-OPI-7e3744ee…4; M0.1 DEC-OPI-d96fd92d…7): it lands
**identity only** — the three migration-0023 tables
(:mod:`elc.world.store` is their SQL face) and the frozen record shapes
below. Nothing else: no events, no engine, no reveal face, no world
behaviour — those are W-1-1+ / W-1-2 / W-1-3 registered cuts, and this
package ships none of them rather than a stub that pretends to.

Value semantics: a world is a named root or fork (``template_world_id``
names the fork parent, NULL is a root — the fork lineage is W-3-2's
consumption, recorded here and built nowhere); an actor binds one world
to one character card (migration 0019's ``character_card.persona_id``);
a conversation binding puts one conversation inside one world through an
actor of that world (the composite FK keeps the actor and the world a
real pair — the migration spells it, the store refuses around it).
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.platform.types import ConversationId, PersonaId

__all__ = [
    "WorldRecord",
    "WorldActorRecord",
    "WorldConversationRecord",
]


@dataclass(frozen=True)
class WorldRecord:
    """One world's identity row (migration 0023's ``world`` table).

    ``template_world_id`` is the fork's parent (``None`` = a root world);
    the referenced world may be created later only by another row's own
    write — the FK refuses a dangling template at insert time.
    """

    world_id: str
    name: str
    template_world_id: str | None
    created_at: str


@dataclass(frozen=True)
class WorldActorRecord:
    """One actor's identity row (migration 0023's ``world_actor`` table).

    An actor is the join of one world and one character card: the card
    must exist (the FK target MC-0's migration 0019 provides), and one
    card speaks as at most one actor per world (the
    ``UNIQUE (world_id, persona_id)``).
    """

    actor_id: str
    world_id: str
    persona_id: PersonaId
    created_at: str


@dataclass(frozen=True)
class WorldConversationRecord:
    """One conversation's world binding (migration 0023's
    ``world_conversation`` table).

    ``conversation_id`` is UNIQUE — a conversation binds to at most one
    world — and the composite FK (actor, world) keeps the bound actor a
    member of the bound world; a binding that pairs an actor with a world
    it does not belong to is refused, never stored.
    """

    binding_id: str
    world_id: str
    actor_id: str
    conversation_id: ConversationId
    created_at: str
