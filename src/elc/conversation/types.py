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
from typing import TYPE_CHECKING

from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    MessageSequence,
    PersonaId,
    RuntimeEpoch,
    SceneId,
    TurnId,
    TurnSequence,
    UserTurnId,
)

if TYPE_CHECKING:
    # Annotation-only (dataclasses never evaluate these at runtime); a
    # runtime import here would make elc.conversation.types ↔ elc.runtime
    # import-cyclic, because elc.runtime.commands imports this module for
    # CommitUserTurn.
    from elc.runtime.types import InputEnvelope


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
    """AssistantTurn.delivery_state vocabulary.

    docs/DATA_MODEL.md §3 names the ``delivery_state`` column but pins no
    value list (adjudicated open point, DEC-…091f35c3.7). The members below
    are derived from docs/STATE_MACHINES.md §13 ServerDeliveryRecord
    (NOT_SENT / SENDING / SENT_PARTIAL / SENT_COMPLETE / FAILED / CANCELLED)
    with docs/DATA_MODEL.md §22 Delivery Data as the record-level semantics;
    only the SENT_* states may appear on a canonical AssistantTurn, because
    undelivered provider output never enters the transcript
    (docs/DOMAIN_MODEL.md §3 key rule).
    """

    NOT_SENT = "NOT_SENT"
    SENDING = "SENDING"
    SENT_PARTIAL = "SENT_PARTIAL"
    SENT_COMPLETE = "SENT_COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


#: delivery states that admit an AssistantTurn into the canonical transcript.
CANONICAL_DELIVERY_STATES: frozenset[DeliveryState] = frozenset(
    {DeliveryState.SENT_PARTIAL, DeliveryState.SENT_COMPLETE}
)


@dataclass(frozen=True)
class ConversationRecord:
    """docs/DATA_MODEL.md §3 Conversation (column set verbatim)."""

    conversation_id: ConversationId
    persona_id: PersonaId | None
    scene_id: SceneId | None
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
    """docs/DATA_MODEL.md §3 AssistantTurn (column set verbatim)."""

    assistant_turn_id: AssistantTurnId
    turn_id: TurnId
    conversation_id: ConversationId
    turn_sequence: TurnSequence
    message_sequence: MessageSequence
    action_id: ActionId
    content: str
    delivery_state: DeliveryState
    delivery_certainty: str


@dataclass(frozen=True)
class CanonicalTurnSlice:
    """docs/DATA_MODEL.md §3 CanonicalTurnSlice DTO."""

    turn_id: TurnId
    conversation_id: ConversationId
    turn_sequence: TurnSequence
    user_turn: UserTurnRecord
    assistant_turn: AssistantTurnRecord | None
    outcome: TurnOutcome | None


@dataclass(frozen=True)
class CommitUserTurn:
    """One CP0 write unit (docs/RUNTIME_ARCHITECTURE.md §6 CP0).

    ``envelope`` is deduped/durable inside the same short transaction;
    ``raw_content`` / ``normalized_content`` are the conversation-domain view
    of what the user said (docs/DATA_MODEL.md §3 UserTurn). ``turn_id`` /
    ``user_turn_id`` may be supplied by the orchestrator as stable opaque IDs
    (docs/DATA_MODEL.md §1.2) or left None for the store to mint.

    Lives in elc.conversation.types (not commands) so the runtime command
    face can import it without an import cycle — commands re-exports it."""

    conversation_id: ConversationId
    envelope: "InputEnvelope"
    raw_content: str
    runtime_version: str
    normalized_content: str | None = None
    turn_id: TurnId | None = None
    user_turn_id: UserTurnId | None = None


@dataclass(frozen=True)
class Cp0Commit:
    """The durable result of one CP0 unit.

    turn_sequence / message_sequence are allocated inside the CP0 short
    transaction from conversation.next_turn_sequence /
    next_message_sequence (docs/DATA_MODEL.md §3 Sequence Semantics) and are
    therefore durable the moment CP0 commits."""

    turn_id: TurnId
    input_id: InputId
    user_turn_id: UserTurnId
    turn_sequence: TurnSequence
    message_sequence: MessageSequence
    owner_epoch: RuntimeEpoch
    state_version: int


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
