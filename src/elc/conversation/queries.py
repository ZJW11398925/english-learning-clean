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
