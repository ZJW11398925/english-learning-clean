"""Conversation domain — canonical conversation state.

Owns (docs/DOMAIN_MODEL.md §3): Conversation, UserTurn, AssistantTurn,
CanonicalTurnSlice, episode source events, conversation sequence
(turn_sequence + message_sequence, docs/DATA_MODEL.md §3).

Key rule: the canonical transcript is the system-confirmed conversation
state; undelivered provider output never enters it.
Does NOT own: learning mastery, relationship memory truth, teaching
selection, persona identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ClientMessageId,
    ConversationId,
    DeliveryId,
    InputId,
    InteractionChannel,
    MessageSequence,
    PersonaId,
    SceneId,
    TurnId,
    TurnSequence,
    UserId,
    UserTurnId,
)


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class TurnOutcome(StrEnum):
    """Turn outcome vocabulary, word for word, from docs/STATE_MACHINES.md
    §10 lines 296-301 ("Turn outcome 单独记录"). Terminal, recorded
    separately from the TurnRecord coordination status."""

    REPLIED_FULL = "REPLIED_FULL"
    REPLIED_PARTIAL = "REPLIED_PARTIAL"
    NO_ASSISTANT_OUTPUT = "NO_ASSISTANT_OUTPUT"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    FAILED_USER_VISIBLE = "FAILED_USER_VISIBLE"


class DeliveryState(StrEnum):
    """docs/STATE_MACHINES.md assistant turn delivery progression."""

    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FULL = "FULL"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ConversationRecord:
    """docs/DATA_MODEL.md §3 Conversation."""

    conversation_id: ConversationId
    persona_id: PersonaId | None
    scene_id: SceneId | None
    user_id: UserId
    status: ConversationStatus
    next_turn_sequence: TurnSequence
    next_message_sequence: MessageSequence


@dataclass(frozen=True)
class UserTurnRecord:
    """docs/DATA_MODEL.md §3 UserTurn."""

    user_turn_id: UserTurnId
    turn_id: TurnId
    conversation_id: ConversationId
    turn_sequence: TurnSequence
    message_sequence: MessageSequence
    input_id: InputId
    client_message_id: ClientMessageId | None
    interaction_channel: InteractionChannel
    raw_content: str
    normalized_content: str | None


@dataclass(frozen=True)
class AssistantTurnRecord:
    """docs/DATA_MODEL.md §3 AssistantTurn."""

    assistant_turn_id: AssistantTurnId
    turn_id: TurnId
    conversation_id: ConversationId
    turn_sequence: TurnSequence
    message_sequence: MessageSequence
    action_id: ActionId
    content: str
    delivery_state: DeliveryState
    delivery_certainty: str
    delivery_id: DeliveryId | None


@dataclass(frozen=True)
class CanonicalTurnSlice:
    """docs/DATA_MODEL.md §3 CanonicalTurnSlice DTO."""

    turn_id: TurnId
    conversation_id: ConversationId
    turn_sequence: TurnSequence
    user_turn: UserTurnRecord
    assistant_turn: AssistantTurnRecord | None
    outcome: TurnOutcome | None


class SequenceAllocator:
    """Independent turn/message sequence counters per conversation.

    docs/DATA_MODEL.md §3 Sequence Semantics:
    - turn_sequence: strictly increasing per user-input coordination turn;
      the turn's AssistantTurn? shares turn_id/turn_sequence.
    - message_sequence: strict order of every UserTurn / AssistantTurn in the
      canonical transcript. DecisionCycle occupies no message sequence.

    The two counters advance independently and are distinct types; Phase 1
    replaces this reference allocator with durable DB-backed allocation
    inside the CP0 short transaction (same semantics).
    """

    def __init__(self) -> None:
        self._next_turn: dict[ConversationId, int] = {}
        self._next_message: dict[ConversationId, int] = {}

    def allocate_turn(self, conversation_id: ConversationId) -> TurnSequence:
        value = self._next_turn.get(conversation_id, 0) + 1
        self._next_turn[conversation_id] = value
        return TurnSequence(value)

    def allocate_message(self, conversation_id: ConversationId) -> MessageSequence:
        value = self._next_message.get(conversation_id, 0) + 1
        self._next_message[conversation_id] = value
        return MessageSequence(value)

    def peek_turn(self, conversation_id: ConversationId) -> TurnSequence:
        return TurnSequence(self._next_turn.get(conversation_id, 0) + 1)

    def peek_message(self, conversation_id: ConversationId) -> MessageSequence:
        return MessageSequence(self._next_message.get(conversation_id, 0) + 1)
