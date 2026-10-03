"""World/Lore Domain Controller — the domain's authority face (主线-3).

The Phase 0 red line is retired for this class: the controller graduated the
way learning/teaching/planner did before it (pure authority over the durable
face — every SQL statement lives in :mod:`elc.world_lore.store`, migration
0020), and the census row names it the package's live face. What each method
answers, and what it deliberately does not:

- :meth:`propose_lore_fact` — the P-INV-013 half, minimal form: an untrusted
  proposal lands as a ``status='PENDING'`` row carrying its declared
  ``source``, and **no view ever serves a PENDING row**, so untrusted text
  cannot reach a prompt by proposing. The VALIDATE/COMMIT/REJECT/ABSTAIN
  decision and the approval face that flips PENDING→ACTIVE are the
  registered next cut (DEC-OPI-32409938…36 R2's trade-off line) — this
  method neither approves nor rejects today.
- :meth:`resolve_world_lore_view` — the view Persona Runtime consumes: the
  conversation's own scope (world facts + its persona's character facts).
  A conversation the store has never heard of is a ``NOT_FOUND`` answer,
  never a guessed world; an unbound conversation gets the common world.
- :meth:`get_lore_fact` — the canonical fact read, the store's answer
  verbatim.
- :meth:`supersede_lore_fact` — still unimplemented, with its pointer:
  append-first supersede is durable-row surgery the minimal face does not
  carry (facts are append-first; a correction is a later cut's decision
  about status transitions, not an in-place rewrite).
"""

from __future__ import annotations

import uuid

from elc.conversation.queries import ConversationQueries
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
    WorldLoreFactId,
)
from elc.world_lore.store import SqliteWorldLoreStore, WorldLoreFactRow
from elc.world_lore.types import (
    WorldLoreProposal,
    WorldLoreRecord,
    WorldLoreView,
)

__all__ = ["WorldLoreController"]


class WorldLoreController:
    """Owns canonical world facts — the authority face over
    :class:`~elc.world_lore.store.SqliteWorldLoreStore`, scoped through the
    conversation domain's own binding (the persona a conversation carries
    decides which character facts are in its world; this controller never
    guesses one)."""

    def __init__(
        self,
        world_lore: SqliteWorldLoreStore,
        conversations: ConversationQueries,
    ) -> None:
        self._world_lore = world_lore
        self._conversations = conversations

    def propose_lore_fact(
        self, proposal: WorldLoreProposal
    ) -> Result[WorldLoreFactId]:
        """Land one untrusted proposal as a PENDING row (P-INV-013).

        The proposal's own words are the row's columns — kind, key,
        statement and the declared ``source`` verbatim — and the status is
        the whole safety story: a PENDING row is visible to no view, so a
        proposal can be durable without being canonical. The scope of a
        proposal is the common world by default today; the approval cut
        (registered) owns the decision to promote, and with it the scope
        question.
        """

        row = WorldLoreFactRow(
            world_lore_fact_id=f"wlf-{uuid.uuid4().hex}",
            scope="world",
            persona_id=None,
            fact_kind=proposal.fact_kind,
            canonical_key=proposal.canonical_key,
            statement=proposal.statement,
            source=proposal.source,
            status="PENDING",
        )
        return self._world_lore.add_fact(row)

    def supersede_lore_fact(
        self, fact_id: WorldLoreFactId, replacement: WorldLoreRecord
    ) -> Result[WorldLoreFactId]:
        raise NotImplementedError(
            "append-first supersede is the registered next face (主线-3"
            " minimal: direct fact rows + reads; status transitions belong"
            " to the approval cut) — see SURFACE_CENSUS"
        )

    def resolve_world_lore_view(
        self, conversation_id: ConversationId
    ) -> Result[WorldLoreView]:
        """The resolved view for one conversation: the common world plus
        its own persona's character facts."""

        record = self._conversations.get_conversation(conversation_id)
        if isinstance(record, Err):
            return record
        if record.value is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=f"conversation not found: {conversation_id}",
                )
            )
        persona_id = record.value.persona_id
        return Ok(
            self._world_lore.view_for(
                str(persona_id) if persona_id is not None else None
            )
        )

    def get_lore_fact(
        self, fact_id: WorldLoreFactId
    ) -> Result[WorldLoreRecord | None]:
        """One canonical fact (the store's answer verbatim)."""

        return self._world_lore.get_fact(fact_id)
