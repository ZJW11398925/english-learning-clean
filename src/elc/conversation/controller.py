"""Empty Conversation Domain Controller — a Phase 0 red-line skeleton, not a
pending implementation.

`tests/architecture/test_gate_1_domain_interfaces.py` requires every method
below to raise ``NotImplementedError`` (the Phase 0 red line). The live faces
are ``elc.conversation.store:SqliteConversationStore`` (all durable truth,
CP0 included) plus the orchestrator in ``elc.runtime``; see
``tests/architecture/test_surface_census.py`` for ``elc.conversation``'s row.

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
    """Owns canonical conversation truth. Phase 0 red line: no logic."""

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
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.conversation: see SURFACE_CENSUS (conversation"
            " canonicalization)"
        )

    def commit_user_turn(self, turn: object) -> Result[TurnId]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.conversation: see SURFACE_CENSUS (CP0 user turn"
            " canonicalization)"
        )

    def canonicalize_assistant_turn(self, turn: object) -> Result[AssistantTurnId]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.conversation: see SURFACE_CENSUS (delivery-gated"
            " canonicalization)"
        )

    def terminalize_turn(self, turn_id: TurnId, outcome: TurnOutcome) -> Result[TurnId]:
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.conversation: see SURFACE_CENSUS (terminalization)"
        )
