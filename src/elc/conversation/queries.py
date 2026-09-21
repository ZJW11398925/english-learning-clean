"""Conversation domain query face — read projections of canonical state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.conversation.types import CanonicalTurnSlice, ConversationRecord
from elc.platform.types import (
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
