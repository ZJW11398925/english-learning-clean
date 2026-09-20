"""Conversation domain command face — the only canonical write path.

Authority: docs/DOMAIN_MODEL.md §2 — what the user actually said is owned by
Conversation. All writes flow through the Domain Controller, which returns
VALIDATE/COMMIT/REJECT/ABSTAIN outcomes (§18); proposals never write
directly. Phase 0: interfaces + empty controller only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.conversation.types import (
    AssistantTurnRecord,
    CanonicalTurnSlice,
    TurnOutcome,
    UserTurnRecord,
)
from elc.platform.types import (
    AssistantTurnId,
    ConversationId,
    PersonaId,
    Result,
    SceneId,
    TurnId,
    UserId,
)


@runtime_checkable
class ConversationCommands(Protocol):
    """Canonical conversation writes."""

    def open_conversation(
        self,
        conversation_id: ConversationId,
        user_id: UserId,
        persona_id: PersonaId | None,
        scene_id: SceneId | None,
    ) -> Result[ConversationId]:
        """Create the durable conversation aggregate."""
        ...

    def commit_user_turn(self, turn: UserTurnRecord) -> Result[TurnId]:
        """Canonicalize one user turn (CP0 unit with the runtime TurnRecord)."""
        ...

    def canonicalize_assistant_turn(
        self, turn: AssistantTurnRecord
    ) -> Result[AssistantTurnId]:
        """Canonicalize delivered provider output once (idempotent by delivery)."""
        ...

    def terminalize_turn(
        self, turn_id: TurnId, outcome: TurnOutcome
    ) -> Result[TurnId]:
        """Write the terminal CanonicalTurnSlice outcome."""
        ...


def describe_slice(slice_: CanonicalTurnSlice) -> str:
    """Skeleton helper showing the owned aggregate shape (no logic yet)."""
    raise NotImplementedError("Phase 1: canonical transcript projection")
