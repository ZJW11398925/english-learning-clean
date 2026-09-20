"""Conversation domain command face — the only canonical write path.

Authority: docs/DOMAIN_MODEL.md §2 — what the user actually said is owned by
Conversation. All writes flow through the Domain Controller, which returns
VALIDATE/COMMIT/REJECT/ABSTAIN outcomes (§18); proposals never write
directly.

Phase 1 P1A (TASK-OPI-091f35c3.11): the protocol is re-shaped around the
canonical commit units — CP0 (InputEnvelope dedupe + UserTurn + TurnRecord,
docs/RUNTIME_ARCHITECTURE.md §6), state_version CAS transitions
(docs/STATE_MACHINES.md §20), delivery-gated AssistantTurn
canonicalization, and the guard-external durable input queue
(docs/RUNTIME_ARCHITECTURE.md §17.1 / §24: 新 InputEnvelope /
InterruptRequest 可在 coordinator guard 外 durable).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.conversation.types import (
    AssistantTurnRecord,
    CanonicalTurnSlice,
    CommitUserTurn,
    Cp0Commit,
    TurnOutcome,
)
from elc.platform.types import (
    AssistantTurnId,
    ConversationId,
    InputId,
    PersonaId,
    Result,
    SceneId,
    TurnId,
    UserId,
)
from elc.runtime.types import (
    InputEnvelope,
    InterruptRequest,
    TurnRecordData,
    TurnStatus,
)


@runtime_checkable
class ConversationCommands(Protocol):
    """Canonical conversation writes (Phase 1 durable core)."""

    def open_conversation(
        self,
        conversation_id: ConversationId,
        user_id: UserId,
        persona_id: PersonaId | None,
        scene_id: SceneId | None,
    ) -> Result[ConversationId]:
        """Create the durable conversation aggregate (DATA_MODEL §3)."""
        ...

    def ingest_input(self, envelope: InputEnvelope) -> Result[InputEnvelope]:
        """Durable + dedupe outside the coordinator guard (RUNTIME §17.1).

        A repeat client_message_id returns the original input and writes
        nothing (DATA_MODEL §4 Unique: client_message_id where present).
        """
        ...

    def request_interrupt(self, interrupt: InterruptRequest) -> Result[InputId]:
        """Durable InterruptRequest while the guard is still held (§17.1)."""
        ...

    def commit_user_turn(self, command: CommitUserTurn) -> Result[Cp0Commit]:
        """CP0: one short transaction allocating both sequences and writing
        UserTurn + TurnRecord(USER_COMMITTED, owner_epoch) (RUNTIME §6,
        R-INV-001, DATA_MODEL §3)."""
        ...

    def transition_turn(
        self,
        turn_id: TurnId,
        expected_state_version: int,
        new_status: TurnStatus,
    ) -> Result[TurnRecordData]:
        """TurnRecord coordination transition under state_version CAS
        (STATE_MACHINES §10, §20)."""
        ...

    def canonicalize_assistant_turn(
        self, turn: AssistantTurnRecord
    ) -> Result[AssistantTurnId]:
        """Canonicalize delivered provider output once (idempotent by turn).

        Only SENT_* delivery states are admitted (DOMAIN_MODEL §3 key rule;
        STATE_MACHINES §13-derived vocabulary).
        """
        ...

    def terminalize_turn(
        self, turn_id: TurnId, outcome: TurnOutcome
    ) -> Result[TurnRecordData]:
        """Write the terminal CanonicalTurnSlice outcome (STATE_MACHINES §10)."""
        ...

    def claim_turn_for_recovery(self, turn_id: TurnId) -> Result[TurnRecordData]:
        """Adopt an old-epoch nonterminal TurnRecord for the current epoch
        (RUNTIME §24 restart ownership; SM §17.1 rule 3 — the recovery owner
        finishes old work; the committed UserTurn is never replayed, §22)."""
        ...

    def get_turn_record(self, turn_id: TurnId) -> Result[TurnRecordData | None]:
        """Durable TurnRecord read (RuntimeQueries.get_turn_record face)."""
        ...


def describe_slice(slice_: CanonicalTurnSlice) -> str:
    """One-line transcript rendering of a CanonicalTurnSlice (projection
    helper; the transcript itself stays the durable query face)."""
    turn = slice_.user_turn
    assistant = slice_.assistant_turn
    assistant_text = assistant.content if assistant is not None else "—"
    outcome = slice_.outcome.value if slice_.outcome is not None else "—"
    return (
        f"#{slice_.turn_sequence} [{slice_.turn_id}] "
        f"user: {turn.raw_content} | assistant: {assistant_text} "
        f"| outcome: {outcome}"
    )
