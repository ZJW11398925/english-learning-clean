"""Conversation domain query face — read projections of canonical state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.conversation.types import (
    CanonicalTurnSlice,
    ConversationRecord,
    InterruptRequestRecord,
)
from elc.platform.types import (
    ActionId,
    ConversationId,
    MessageSequence,
    Result,
    TurnId,
    TurnSequence,
)


@dataclass(frozen=True)
class SequencePositions:
    """docs/DATA_MODEL.md §3 Conversation.next_turn_sequence / next_message_sequence."""

    next_turn_sequence: TurnSequence
    next_message_sequence: MessageSequence


@dataclass(frozen=True)
class ConversationWindow:
    """Persona Runtime consumption view (docs/DOMAIN_MODEL.md §4)."""

    conversation_id: ConversationId
    slices: tuple[CanonicalTurnSlice, ...]


@runtime_checkable
class ConversationQueries(Protocol):
    """Canonical conversation reads."""

    def get_conversation(
        self, conversation_id: ConversationId
    ) -> Result[ConversationRecord | None]:
        ...

    def get_canonical_turn_slice(
        self, turn_id: TurnId
    ) -> Result[CanonicalTurnSlice | None]:
        ...

    def get_conversation_window(
        self, conversation_id: ConversationId, max_turns: int
    ) -> Result[ConversationWindow]:
        ...

    def get_sequence_positions(
        self, conversation_id: ConversationId
    ) -> Result[SequencePositions]:
        ...

    def is_command_payload_turn(self, turn_id: TurnId) -> Result[bool]:
        """True for a *command* turn: an empty utterance whose meaning
        travels through a typed InputEnvelope payload (TEACHING_REQUEST /
        TEACHING_RESPONSE).

        Phase 3 P3-1B (review F9): the recovery path must never run a
        teaching turn through the normal persona loop — an empty utterance
        would be answered as if the user had said nothing. This read is the
        durable truth of "this turn is a command", so the orchestrator can
        refuse to mis-handle it (the SQL stays in the conversation domain).
        """
        ...

    # -- the §17.1 interrupt face (P9-3) -----------------------------------
    #
    # One definition, three entry points: a *pending* interrupt is a row in
    # ``interrupt_request`` whose named leg (turn, action, or both) is still
    # nonterminal. The row is never removed by these reads — §17.1 makes the
    # request an audit record, and the outcome it produced (a cancelled
    # delivery, a fenced action) is what a later reader asks about.
    #
    # Why the pending predicate lives here rather than in the runtime: it is a
    # fact about two durable rows, so exactly one face may own it, or the
    # stream loop and the recovery reconciler would each grow their own
    # spelling and drift. Revisit: a cut gives the conversation domain its own
    # action projection (then this read stops joining the runtime-owned table
    # named in the store method's own note).

    def list_pending_interrupts_for_action(
        self, action_id: ActionId
    ) -> Result[tuple[InterruptRequestRecord, ...]]:
        """The pending interrupts naming this action, oldest request first."""
        ...

    def list_pending_interrupts_for_turn(
        self, turn_id: TurnId
    ) -> Result[tuple[InterruptRequestRecord, ...]]:
        """The pending interrupts naming this turn, oldest request first."""
        ...

    def list_pending_interrupts_for_conversation(
        self, conversation_id: ConversationId
    ) -> Result[tuple[InterruptRequestRecord, ...]]:
        """Every pending interrupt of one conversation, oldest first.

        The reconciler's read (RA §17.1 rule 3): the guard holder asks what
        the conversation is still waiting to have cancelled, without knowing
        which action or turn a request named.
        """
        ...
