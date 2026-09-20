"""Conversation domain — owns canonical transcript + conversation sequences.

docs/DOMAIN_MODEL.md §3. Interfaces here are the only sanctioned boundary;
other packages must depend on these names, not on internal records.
"""

from elc.conversation.commands import ConversationCommands
from elc.conversation.controller import ConversationController
from elc.conversation.queries import ConversationQueries
from elc.conversation.types import (
    AssistantTurnRecord,
    CanonicalTurnSlice,
    ConversationRecord,
    DeliveryState,
    SequenceAllocator,
    TurnOutcome,
    UserTurnRecord,
)

__all__ = [
    "AssistantTurnRecord",
    "CanonicalTurnSlice",
    "ConversationCommands",
    "ConversationController",
    "ConversationQueries",
    "ConversationRecord",
    "DeliveryState",
    "SequenceAllocator",
    "TurnOutcome",
    "UserTurnRecord",
]
