"""Conversation domain — owns canonical transcript + conversation sequences.

docs/DOMAIN_MODEL.md §3. Interfaces here are the only sanctioned boundary;
other packages must depend on these names, not on internal records.
"""

from elc.conversation.commands import (
    CommitUserTurn,
    ConversationCommands,
    Cp0Commit,
)
from elc.conversation.controller import ConversationController
from elc.conversation.queries import ConversationQueries
from elc.conversation.store import SqliteConversationStore
from elc.conversation.types import (
    CANONICAL_DELIVERY_STATES,
    AssistantTurnRecord,
    CanonicalTurnSlice,
    ConversationRecord,
    DeliveryState,
    SequenceAllocator,
    TurnOutcome,
    UserTurnRecord,
)

__all__ = [
    "CANONICAL_DELIVERY_STATES",
    "AssistantTurnRecord",
    "CanonicalTurnSlice",
    "CommitUserTurn",
    "ConversationCommands",
    "ConversationController",
    "ConversationQueries",
    "ConversationRecord",
    "Cp0Commit",
    "DeliveryState",
    "SequenceAllocator",
    "SqliteConversationStore",
    "TurnOutcome",
    "UserTurnRecord",
]
