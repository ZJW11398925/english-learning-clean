"""Empty Conversation Domain Controller (Phase 1 will implement).

docs/DOMAIN_MODEL.md §18: the Domain Controller decides
VALIDATE / COMMIT / REJECT / ABSTAIN — proposals (observers, recorders,
model-assisted interpreters) never write canonical state themselves.
"""

from __future__ import annotations

from elc.conversation.types import SequenceAllocator, TurnOutcome
from elc.platform.types import (
    AssistantTurnId,
    ConversationId,
    PersonaId,
    Result,
    SceneId,
    TurnId,
    UserId,
)


class ConversationController:
    """Owns canonical conversation truth. No implementation in Phase 0."""

    def __init__(self) -> None:
        # Reference allocator for the turn/message sequence independence
        # tests; durable allocation moves into the CP0 short transaction.
        self.sequences = SequenceAllocator()

    def open_conversation(
        self,
        conversation_id: ConversationId,
        user_id: UserId,
        persona_id: PersonaId | None,
        scene_id: SceneId | None,
    ) -> Result[ConversationId]:
        raise NotImplementedError("Phase 1: conversation canonicalization")

    def commit_user_turn(self, turn: object) -> Result[TurnId]:
        raise NotImplementedError("Phase 1: CP0 user turn canonicalization")

    def canonicalize_assistant_turn(self, turn: object) -> Result[AssistantTurnId]:
        raise NotImplementedError("Phase 1: delivery-gated canonicalization")

    def terminalize_turn(self, turn_id: TurnId, outcome: TurnOutcome) -> Result[TurnId]:
        raise NotImplementedError("Phase 1: terminalization")
