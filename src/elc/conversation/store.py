"""SQLite durable store for the conversation core (Phase 1 P1A).

TASK-OPI-091f35c3.11 deliverable ②: the durable implementation behind
``ConversationCommands`` / ``ConversationQueries``. Persistence lives in the
conversation domain package (never in ``elc.runtime`` — Gate item 2 keeps the
orchestrator SQL-free; docs/DOMAIN_MODEL.md §16 D-INV-001).

Commit-unit discipline:
- CP0 (docs/RUNTIME_ARCHITECTURE.md §6): InputEnvelope dedupe + UserTurn +
  TurnRecord commit inside ONE ``short_transaction``
  (elc.platform.db.tx.short_transaction); turn_sequence / message_sequence
  are allocated in that same transaction from conversation.next_* columns
  (docs/DATA_MODEL.md §3 Sequence Semantics) and are durable at commit.
- provider calls never run inside the transaction (R-INV-004) — the store
  only ever runs short units.
- epoch fencing: writes carry ``owner_epoch`` = the adopted runtime epoch;
  a store whose fence went stale refuses to write (docs/DATA_MODEL.md §19,
  docs/RUNTIME_ARCHITECTURE.md §24).

All SQL is a fixed literal with bound parameters — no identifier assembly.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from typing import TypeVar

from elc.conversation.commands import CommitUserTurn, Cp0Commit
from elc.conversation.queries import ConversationWindow, SequencePositions
from elc.conversation.types import (
    CANONICAL_DELIVERY_STATES,
    AssistantTurnRecord,
    CanonicalTurnSlice,
    ClientMessageId,
    ConversationId,
    ConversationRecord,
    ConversationStatus,
    DeliveryState,
    InteractionChannel,
    TurnOutcome,
    UserTurnRecord,
)
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    MessageSequence,
    Ok,
    PersonaId,
    Result,
    RuntimeEpoch,
    RuntimeVersion,
    SceneId,
    TurnId,
    TurnSequence,
    UserId,
    UserTurnId,
)
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    InputEnvelope,
    InterruptRequest,
    TurnRecordData,
    TurnStatus,
)

__all__ = [
    "SqliteConversationStore",
    "StaleStoreEpochError",
]

T = TypeVar("T")


class StaleStoreEpochError(StaleEpochError):
    """A store write was fenced: the adopted runtime epoch is no longer the
    newest epoch in app.db (docs/RUNTIME_ARCHITECTURE.md §24)."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


class SqliteConversationStore:
    """Durable conversation aggregate + CP0 commit unit + input queue."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> RuntimeEpoch:
        return RuntimeEpoch(self._fence.current)

    def _require_current_epoch(self) -> None:
        """Fence inside the write transaction: the adopted epoch must still
        be the newest epoch row in app.db (§24 restart ownership)."""
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"store epoch={self._fence.current} fenced by db epoch={newest}"
            )

    # -- ConversationCommands ---------------------------------------------

    def open_conversation(
        self,
        conversation_id: ConversationId,
        user_id: UserId,
        persona_id: PersonaId | None,
        scene_id: SceneId | None,
    ) -> Result[ConversationId]:
        """Create the durable conversation aggregate (DATA_MODEL §3).

        ``user_id`` is part of the Phase 0 interface signature but the §3
        Conversation column set carries no user_id, so nothing is persisted
        for it. Idempotent on conversation_id.
        """
        del user_id  # DATA_MODEL §3 Conversation has no user_id column.
        with short_transaction(self._conn):
            row = self._conn.execute(
                "SELECT conversation_id FROM conversation WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO conversation ("
                    " conversation_id, persona_id, scene_id, created_at,"
                    " status, next_turn_sequence, next_message_sequence"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        conversation_id,
                        persona_id,
                        scene_id,
                        _now(),
                        ConversationStatus.ACTIVE.value,
                        1,
                        1,
                    ),
                )
        return Ok(conversation_id)

    def ingest_input(self, envelope: InputEnvelope) -> Result[InputEnvelope]:
        """Durable + dedupe outside the coordinator guard (RUNTIME §17.1)."""
        if envelope.client_message_id is not None:
            existing = self._envelope_by_client_message_id(
                envelope.client_message_id
            )
            if existing is not None:
                return Ok(existing)  # 幂等返回原 input
        try:
            with short_transaction(self._conn):
                self._conn.execute(
                    "INSERT INTO input_envelope ("
                    " input_id, client_message_id, conversation_id, persona_id,"
                    " scene_id, interaction_channel, raw_payload, received_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        envelope.input_id,
                        envelope.client_message_id,
                        envelope.conversation_id,
                        envelope.persona_id,
                        envelope.scene_id,
                        envelope.interaction_channel,
                        envelope.raw_payload,
                        envelope.received_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return Err(DomainError(code=DomainErrorCode.CONFLICT, message=str(exc)))
        return Ok(envelope)

    def request_interrupt(self, interrupt: InterruptRequest) -> Result[InputId]:
        """Durable InterruptRequest — legal while the guard is still held
        (docs/RUNTIME_ARCHITECTURE.md §17.1 rule 1/2)."""
        try:
            with short_transaction(self._conn):
                self._conn.execute(
                    "INSERT INTO interrupt_request ("
                    " input_id, conversation_id, active_turn_id,"
                    " active_action_id, reason, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        interrupt.input_id,
                        interrupt.conversation_id,
                        interrupt.active_turn_id,
                        interrupt.active_action_id,
                        interrupt.reason,
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return Err(DomainError(code=DomainErrorCode.CONFLICT, message=str(exc)))
        return Ok(interrupt.input_id)

    def commit_user_turn(self, command: CommitUserTurn) -> Result[Cp0Commit]:
        """CP0: one short transaction — InputEnvelope dedupe, sequence
        allocation, UserTurn insert, TurnRecord(USER_COMMITTED, owner_epoch)
        insert, conversation.next_* bump (RUNTIME §6; R-INV-001).

        A repeat client_message_id whose CP0 already committed replays the
        original commit and writes nothing (idempotent; §17.1 rule 1).
        """
        envelope = command.envelope
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                conv_row = self._conn.execute(
                    "SELECT status, next_turn_sequence, next_message_sequence"
                    " FROM conversation WHERE conversation_id = ?",
                    (command.conversation_id,),
                ).fetchone()
                if conv_row is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"conversation not found: {command.conversation_id}",
                    )
                if conv_row[0] == ConversationStatus.CLOSED.value:
                    # STATE_MACHINES §20: CLOSED → active 直接拒绝。
                    return _err(
                        DomainErrorCode.VALIDATION_FAILED,
                        "conversation is CLOSED",
                    )

                # InputEnvelope dedupe (§4 Unique: client_message_id where
                # present). The winning input_id is the durable original.
                input_id = envelope.input_id
                if envelope.client_message_id is not None:
                    prior = self._conn.execute(
                        "SELECT input_id FROM input_envelope"
                        " WHERE client_message_id = ?",
                        (envelope.client_message_id,),
                    ).fetchone()
                    if prior is not None:
                        input_id = InputId(str(prior[0]))

                replay = self._cp0_commit_for_input(input_id)
                if replay is not None:
                    return Ok(replay)  # 已提交者不重放（幂等）

                self._ensure_input_envelope(command, input_id)

                turn_sequence = TurnSequence(int(conv_row[1]))
                message_sequence = MessageSequence(int(conv_row[2]))
                turn_id = (
                    command.turn_id
                    if command.turn_id is not None
                    else TurnId(_new_id("turn"))
                )
                user_turn_id = (
                    command.user_turn_id
                    if command.user_turn_id is not None
                    else UserTurnId(_new_id("uturn"))
                )
                now = _now()
                self._conn.execute(
                    "INSERT INTO user_turn ("
                    " user_turn_id, turn_id, conversation_id, turn_sequence,"
                    " message_sequence, input_id, client_message_id,"
                    " interaction_channel, raw_content, normalized_content,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_turn_id,
                        turn_id,
                        command.conversation_id,
                        turn_sequence,
                        message_sequence,
                        input_id,
                        envelope.client_message_id,
                        envelope.interaction_channel,
                        command.raw_content,
                        command.normalized_content,
                        now,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO turn_record ("
                    " turn_id, conversation_id, turn_sequence, input_id,"
                    " status, active_decision_cycle_id, failure_class,"
                    " failure_reason, runtime_version, started_at, updated_at,"
                    " terminal_at, turn_outcome, owner_epoch, state_version"
                    ") VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?,"
                    " NULL, NULL, ?, ?)",
                    (
                        turn_id,
                        command.conversation_id,
                        turn_sequence,
                        input_id,
                        TurnStatus.USER_COMMITTED.value,
                        command.runtime_version,
                        now,
                        now,
                        self._fence.current,
                        1,
                    ),
                )
                self._conn.execute(
                    "UPDATE conversation SET"
                    " next_turn_sequence = next_turn_sequence + 1,"
                    " next_message_sequence = next_message_sequence + 1"
                    " WHERE conversation_id = ?",
                    (command.conversation_id,),
                )
                return Ok(
                    Cp0Commit(
                        turn_id=turn_id,
                        input_id=input_id,
                        user_turn_id=user_turn_id,
                        turn_sequence=turn_sequence,
                        message_sequence=message_sequence,
                        owner_epoch=RuntimeEpoch(self._fence.current),
                        state_version=1,
                    )
                )
        except sqlite3.IntegrityError as exc:
            # Constraint failure anywhere in the unit: short_transaction has
            # already rolled back — no half-committed window (R-INV-001).
            return Err(DomainError(code=DomainErrorCode.CONFLICT, message=str(exc)))

    def transition_turn(
        self,
        turn_id: TurnId,
        expected_state_version: int,
        new_status: TurnStatus,
    ) -> Result[TurnRecordData]:
        """TurnRecord coordination transition under state_version CAS
        (STATE_MACHINES §20). Terminal coordination states are immutable;
        terminalization goes through ``terminalize_turn``."""
        if new_status in TERMINAL_TURN_STATUSES:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "terminal status requires terminalize_turn",
            )
        with short_transaction(self._conn):
            row = self._turn_row(turn_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND, f"turn record not found: {turn_id}"
                )
            if row[8] != self._fence.current:
                # DATA_MODEL §19: stale-epoch work is fenced; only the
                # current epoch's owner advances coordination state.
                return _err(
                    DomainErrorCode.AUTHORITY_VIOLATION,
                    f"owner_epoch={row[8]} fenced by"
                    f" current epoch={self._fence.current}",
                )
            current_status = TurnStatus(str(row[4]))
            if current_status in TERMINAL_TURN_STATUSES:
                return _err(
                    DomainErrorCode.VALIDATION_FAILED,
                    f"turn {turn_id} is terminal ({current_status})",
                )
            if int(row[9]) != expected_state_version:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"state_version CAS mismatch on {turn_id}: expected"
                    f" {expected_state_version}, durable {row[9]}",
                )
            self._conn.execute(
                "UPDATE turn_record SET status = ?,"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE turn_id = ? AND state_version = ? AND owner_epoch = ?",
                (
                    new_status.value,
                    _now(),
                    turn_id,
                    expected_state_version,
                    self._fence.current,
                ),
            )
            updated = self._turn_row(turn_id)
            assert updated is not None  # row existed above, same tx
            return Ok(self._turn_record_data(updated))

    def canonicalize_assistant_turn(
        self, turn: AssistantTurnRecord
    ) -> Result[AssistantTurnId]:
        """Canonicalize delivered provider output once (idempotent by turn).

        Gate: only SENT_* delivery states enter the transcript
        (docs/DOMAIN_MODEL.md §3 key rule; vocabulary derived from
        docs/STATE_MACHINES.md §13 — see DeliveryState). The assistant turn
        shares the coordination turn's turn_sequence (DATA_MODEL §3) and
        takes the next message_sequence in the same short transaction.
        """
        if turn.delivery_state not in CANONICAL_DELIVERY_STATES:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"delivery_state={turn.delivery_state.value} is not delivered;"
                " undelivered provider output never enters the transcript"
                " (DOMAIN_MODEL §3)",
            )
        try:
            with short_transaction(self._conn):
                existing = self._conn.execute(
                    "SELECT assistant_turn_id FROM assistant_turn"
                    " WHERE turn_id = ?",
                    (turn.turn_id,),
                ).fetchone()
                if existing is not None:
                    return Ok(AssistantTurnId(str(existing[0])))
                user_row = self._conn.execute(
                    "SELECT conversation_id, turn_sequence FROM user_turn"
                    " WHERE turn_id = ?",
                    (turn.turn_id,),
                ).fetchone()
                if user_row is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"user turn not found: {turn.turn_id}",
                    )
                conversation_id = ConversationId(str(user_row[0]))
                turn_sequence = TurnSequence(int(user_row[1]))
                msg_row = self._conn.execute(
                    "SELECT next_message_sequence FROM conversation"
                    " WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()
                assert msg_row is not None  # FK guarantees the parent row
                message_sequence = MessageSequence(int(msg_row[0]))
                self._conn.execute(
                    "INSERT INTO assistant_turn ("
                    " assistant_turn_id, turn_id, conversation_id,"
                    " turn_sequence, message_sequence, action_id, content,"
                    " delivery_state, delivery_certainty, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        turn.assistant_turn_id,
                        turn.turn_id,
                        conversation_id,
                        turn_sequence,
                        message_sequence,
                        turn.action_id,
                        turn.content,
                        turn.delivery_state.value,
                        turn.delivery_certainty,
                        _now(),
                    ),
                )
                self._conn.execute(
                    "UPDATE conversation SET"
                    " next_message_sequence = next_message_sequence + 1"
                    " WHERE conversation_id = ?",
                    (conversation_id,),
                )
                return Ok(turn.assistant_turn_id)
        except sqlite3.IntegrityError as exc:
            return Err(DomainError(code=DomainErrorCode.CONFLICT, message=str(exc)))

    def terminalize_turn(
        self, turn_id: TurnId, outcome: TurnOutcome
    ) -> Result[TurnRecordData]:
        """Terminal CanonicalTurnSlice outcome under state_version CAS.

        Status mapping from docs/STATE_MACHINES.md §10: CANCELLED_BY_USER
        keeps its coordination state; FAILED_USER_VISIBLE ends FAILED_FINAL;
        the replied/no-output outcomes end COMPLETED
        (DELIVERY_TERMINAL → POSTPROCESSING/COMPLETED).
        """
        if outcome == TurnOutcome.CANCELLED_BY_USER:
            status = TurnStatus.CANCELLED_BY_USER
        elif outcome == TurnOutcome.FAILED_USER_VISIBLE:
            status = TurnStatus.FAILED_FINAL
        else:
            status = TurnStatus.COMPLETED
        with short_transaction(self._conn):
            row = self._turn_row(turn_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND, f"turn record not found: {turn_id}"
                )
            if row[8] != self._fence.current:
                return _err(
                    DomainErrorCode.AUTHORITY_VIOLATION,
                    f"owner_epoch={row[8]} fenced by"
                    f" current epoch={self._fence.current}",
                )
            if TurnStatus(str(row[4])) in TERMINAL_TURN_STATUSES:
                return _err(
                    DomainErrorCode.VALIDATION_FAILED,
                    f"turn {turn_id} is already terminal",
                )
            expected = int(row[9])
            self._conn.execute(
                "UPDATE turn_record SET status = ?, turn_outcome = ?,"
                " terminal_at = ?, updated_at = ?,"
                " state_version = state_version + 1"
                " WHERE turn_id = ? AND state_version = ? AND owner_epoch = ?",
                (
                    status.value,
                    outcome.value,
                    _now(),
                    _now(),
                    turn_id,
                    expected,
                    self._fence.current,
                ),
            )
            updated = self._turn_row(turn_id)
            assert updated is not None  # row existed above, same tx
            return Ok(self._turn_record_data(updated))

    # -- ConversationQueries -----------------------------------------------

    def get_turn_record(self, turn_id: TurnId) -> Result[TurnRecordData | None]:
        """Durable TurnRecord read (RuntimeQueries.get_turn_record face)."""
        row = self._turn_row(turn_id)
        return Ok(None if row is None else self._turn_record_data(row))

    def claim_turn_for_recovery(self, turn_id: TurnId) -> Result[TurnRecordData]:
        """Startup-recovery adoption: the new runtime epoch takes over an
        old-epoch nonterminal TurnRecord (RUNTIME §24 restart ownership; SM
        §17.1 rule 3 — the recovery owner may finish/terminalize old work).

        Advances owner_epoch to the current epoch under state_version CAS;
        terminal turns are returned unchanged. The committed UserTurn is
        only referenced, never replayed (§22; VAL ④ of the P1A slice)."""

        with short_transaction(self._conn):
            row = self._turn_row(turn_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND, f"turn record not found: {turn_id}"
                )
            if TurnStatus(str(row[4])) in TERMINAL_TURN_STATUSES:
                return Ok(self._turn_record_data(row))
            if row[8] == self._fence.current:
                return Ok(self._turn_record_data(row))  # already ours
            self._require_current_epoch()
            expected = int(row[9])
            self._conn.execute(
                "UPDATE turn_record SET owner_epoch = ?,"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE turn_id = ? AND state_version = ?"
                " AND status NOT IN"
                "  ('COMPLETED', 'CANCELLED_BY_USER', 'FAILED_FINAL')",
                (self._fence.current, _now(), turn_id, expected),
            )
            updated = self._turn_row(turn_id)
            assert updated is not None  # row existed above, same tx
            return Ok(self._turn_record_data(updated))

    def get_conversation(
        self, conversation_id: ConversationId
    ) -> Result[ConversationRecord | None]:
        row = self._conn.execute(
            "SELECT conversation_id, persona_id, scene_id, status,"
            " next_turn_sequence, next_message_sequence"
            " FROM conversation WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return Ok(None)
        return Ok(
            ConversationRecord(
                conversation_id=ConversationId(str(row[0])),
                persona_id=PersonaId(str(row[1])) if row[1] is not None else None,
                scene_id=SceneId(str(row[2])) if row[2] is not None else None,
                status=ConversationStatus(str(row[3])),
                next_turn_sequence=TurnSequence(int(row[4])),
                next_message_sequence=MessageSequence(int(row[5])),
            )
        )

    def get_canonical_turn_slice(
        self, turn_id: TurnId
    ) -> Result[CanonicalTurnSlice | None]:
        """One CanonicalTurnSlice: UserTurn + canonicalized AssistantTurn? +
        TurnOutcome. An AssistantTurn appears only if canonicalized."""
        user_row = self._conn.execute(
            "SELECT user_turn_id, turn_id, conversation_id, turn_sequence,"
            " message_sequence, input_id, client_message_id,"
            " interaction_channel, raw_content, normalized_content"
            " FROM user_turn WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        if user_row is None:
            return Ok(None)
        return Ok(
            CanonicalTurnSlice(
                turn_id=turn_id,
                conversation_id=ConversationId(str(user_row[2])),
                turn_sequence=TurnSequence(int(user_row[3])),
                user_turn=self._user_turn_record(user_row),
                assistant_turn=self._assistant_for_turn(turn_id),
                outcome=self._turn_outcome(turn_id),
            )
        )

    def get_conversation_window(
        self, conversation_id: ConversationId, max_turns: int
    ) -> Result[ConversationWindow]:
        """Canonical transcript window (docs/DOMAIN_MODEL.md §3 key rule:
        only canonicalized, delivered assistant output appears; undelivered
        provider output is never stored as an AssistantTurn)."""
        rows = self._conn.execute(
            "SELECT user_turn_id, turn_id, conversation_id, turn_sequence,"
            " message_sequence, input_id, client_message_id,"
            " interaction_channel, raw_content, normalized_content"
            " FROM user_turn WHERE conversation_id = ?"
            " ORDER BY turn_sequence DESC LIMIT ?",
            (conversation_id, max_turns),
        ).fetchall()
        slices = [
            CanonicalTurnSlice(
                turn_id=TurnId(str(row[1])),
                conversation_id=ConversationId(str(row[2])),
                turn_sequence=TurnSequence(int(row[3])),
                user_turn=self._user_turn_record(row),
                assistant_turn=self._assistant_for_turn(TurnId(str(row[1]))),
                outcome=self._turn_outcome(TurnId(str(row[1]))),
            )
            for row in rows
        ]
        slices.reverse()
        return Ok(
            ConversationWindow(
                conversation_id=conversation_id,
                slices=tuple(slices),
            )
        )

    def get_sequence_positions(
        self, conversation_id: ConversationId
    ) -> Result[SequencePositions]:
        row = self._conn.execute(
            "SELECT next_turn_sequence, next_message_sequence"
            " FROM conversation WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return _err(
                DomainErrorCode.NOT_FOUND,
                f"conversation not found: {conversation_id}",
            )
        return Ok(
            SequencePositions(
                next_turn_sequence=TurnSequence(int(row[0])),
                next_message_sequence=MessageSequence(int(row[1])),
            )
        )

    # -- runtime coordination reads (TurnRecordRecoverySource) --------------

    def recoverable_turn_records(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[TurnRecordData, ...]:
        """Old-epoch nonterminal TurnRecords (RUNTIME_ARCHITECTURE §22: 扫描
        非 terminal; §24: the new epoch fences old-epoch work)."""
        rows = self._conn.execute(
            "SELECT turn_id, conversation_id, turn_sequence, input_id,"
            " status, active_decision_cycle_id, failure_class,"
            " runtime_version, owner_epoch, state_version"
            " FROM turn_record"
            " WHERE owner_epoch != ?"
            "  AND status NOT IN"
            "   ('COMPLETED', 'CANCELLED_BY_USER', 'FAILED_FINAL')"
            " ORDER BY started_at, turn_id",
            (current_epoch,),
        ).fetchall()
        return tuple(self._turn_record_data(row) for row in rows)

    # -- internals -----------------------------------------------------------

    def _ensure_input_envelope(
        self, command: CommitUserTurn, input_id: InputId
    ) -> None:
        """Insert the envelope if this CP0 unit is not replaying one that is
        already durable (RUNTIME §6 CP0 lists InputEnvelope dedupe)."""
        row = self._conn.execute(
            "SELECT input_id FROM input_envelope WHERE input_id = ?",
            (input_id,),
        ).fetchone()
        if row is not None:
            return
        envelope = command.envelope
        self._conn.execute(
            "INSERT INTO input_envelope ("
            " input_id, client_message_id, conversation_id, persona_id,"
            " scene_id, interaction_channel, raw_payload, received_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                input_id,
                envelope.client_message_id,
                command.conversation_id,
                envelope.persona_id,
                envelope.scene_id,
                envelope.interaction_channel,
                envelope.raw_payload,
                envelope.received_at,
            ),
        )

    def _cp0_commit_for_input(self, input_id: InputId) -> Cp0Commit | None:
        row = self._conn.execute(
            "SELECT u.turn_id, u.user_turn_id, u.turn_sequence,"
            " u.message_sequence, t.owner_epoch, t.state_version"
            " FROM user_turn u JOIN turn_record t ON t.turn_id = u.turn_id"
            " WHERE u.input_id = ?",
            (input_id,),
        ).fetchone()
        if row is None:
            return None
        return Cp0Commit(
            turn_id=TurnId(str(row[0])),
            input_id=input_id,
            user_turn_id=UserTurnId(str(row[1])),
            turn_sequence=TurnSequence(int(row[2])),
            message_sequence=MessageSequence(int(row[3])),
            owner_epoch=RuntimeEpoch(int(row[4])),
            state_version=int(row[5]),
        )

    def _envelope_by_client_message_id(
        self, client_message_id: str
    ) -> InputEnvelope | None:
        row = self._conn.execute(
            "SELECT input_id, client_message_id, conversation_id, persona_id,"
            " scene_id, interaction_channel, raw_payload, received_at"
            " FROM input_envelope WHERE client_message_id = ?",
            (client_message_id,),
        ).fetchone()
        if row is None:
            return None
        return InputEnvelope(
            input_id=InputId(str(row[0])),
            client_message_id=(
                ClientMessageId(str(row[1])) if row[1] is not None else None
            ),
            conversation_id=str(row[2]),
            persona_id=None if row[3] is None else str(row[3]),
            scene_id=None if row[4] is None else str(row[4]),
            interaction_channel=InteractionChannel(str(row[5])),
            raw_payload=str(row[6]),
            received_at=str(row[7]),
        )

    def _turn_row(self, turn_id: TurnId) -> sqlite3.Row | None:
        # Column order: turn_id, conversation_id, turn_sequence, input_id,
        # status, active_decision_cycle_id, failure_class, runtime_version,
        # owner_epoch, state_version. Default tuple rows (no row_factory).
        return self._conn.execute(
            "SELECT turn_id, conversation_id, turn_sequence, input_id,"
            " status, active_decision_cycle_id, failure_class,"
            " runtime_version, owner_epoch, state_version"
            " FROM turn_record WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()

    def _turn_record_data(self, row: sqlite3.Row) -> TurnRecordData:
        return TurnRecordData(
            turn_id=TurnId(str(row[0])),
            conversation_id=str(row[1]),
            turn_sequence=TurnSequence(int(row[2])),
            input_id=InputId(str(row[3])),
            status=TurnStatus(str(row[4])),
            active_decision_cycle_id=(
                DecisionCycleId(str(row[5])) if row[5] is not None else None
            ),
            failure_class=str(row[6]) if row[6] is not None else None,
            runtime_version=RuntimeVersion(str(row[7])),
            owner_epoch=RuntimeEpoch(int(row[8])),
            state_version=int(row[9]),
        )

    def _assistant_for_turn(self, turn_id: TurnId) -> AssistantTurnRecord | None:
        row = self._conn.execute(
            "SELECT assistant_turn_id, turn_id, conversation_id,"
            " turn_sequence, message_sequence, action_id, content,"
            " delivery_state, delivery_certainty"
            " FROM assistant_turn WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        if row is None:
            return None
        return AssistantTurnRecord(
            assistant_turn_id=AssistantTurnId(str(row[0])),
            turn_id=TurnId(str(row[1])),
            conversation_id=ConversationId(str(row[2])),
            turn_sequence=TurnSequence(int(row[3])),
            message_sequence=MessageSequence(int(row[4])),
            action_id=ActionId(str(row[5])),
            content=str(row[6]),
            delivery_state=DeliveryState(str(row[7])),
            delivery_certainty=str(row[8]),
        )

    def _user_turn_record(self, row: sqlite3.Row) -> UserTurnRecord:
        return UserTurnRecord(
            user_turn_id=UserTurnId(str(row[0])),
            turn_id=TurnId(str(row[1])),
            conversation_id=ConversationId(str(row[2])),
            turn_sequence=TurnSequence(int(row[3])),
            message_sequence=MessageSequence(int(row[4])),
            input_id=InputId(str(row[5])),
            client_message_id=(
                ClientMessageId(str(row[6])) if row[6] is not None else None
            ),
            interaction_channel=InteractionChannel(str(row[7])),
            raw_content=str(row[8]),
            normalized_content=str(row[9]) if row[9] is not None else None,
        )

    def _turn_outcome(self, turn_id: TurnId) -> TurnOutcome | None:
        row = self._conn.execute(
            "SELECT turn_outcome FROM turn_record WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return TurnOutcome(str(row[0]))
