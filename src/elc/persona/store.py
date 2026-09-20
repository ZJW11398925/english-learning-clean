"""SQLite durable store for generation/provider records (Phase 1 P1B).

TASK-OPI-d7937fd7.9 deliverables ③/④: durable GenerationActionIntent /
ProviderAttempt persistence. The tables are runtime-owned coordination
records (docs/DOMAIN_MODEL.md §16), but their physical persistence lives in
this persona-domain package — never in ``elc.runtime`` (Gate item 2 keeps
the orchestrator SQL-free; D-INV-001), mirroring how P1A colocated the
TurnRecord persistence in the conversation store.

Discipline:
- every state advance is a compare-and-swap on the durable status column
  plus the owner_epoch fence (STATE_MACHINES §20 "state_version +
  compare-and-swap" realized on the §20 column set, which pins no
  state_version column — the guarded UPDATE refuses any out-of-order
  overwrite, which is the §20 intent);
- TERMINAL is immutable (STATE_MACHINES §14: a late result for a
  cancelled/superseded/terminal action must not produce a canonical side
  effect);
- one action, many ProviderAttempts, at most one canonical accepted result
  (§14; RUNTIME_ARCHITECTURE §16) — attempts only append;
- provider calls never happen inside these transactions (R-INV-004): the
  store only records attempt outcomes after the call returned.

All SQL is a fixed literal with bound parameters — no identifier assembly.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ActionId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    ProviderAttemptId,
    Result,
    RuntimeEpoch,
    TurnId,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    ProviderAttemptRecord,
)

__all__ = ["SqliteGenerationStore", "StaleStoreEpochError"]

T = TypeVar("T")


class StaleStoreEpochError(StaleEpochError):
    """A generation-store write was fenced by a newer runtime epoch."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


class SqliteGenerationStore:
    """Durable generation action intent + provider attempt log."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> RuntimeEpoch:
        return RuntimeEpoch(self._fence.current)

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"generation store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- writes ------------------------------------------------------------

    def create_action(
        self, intent: GenerationActionIntentRecord
    ) -> Result[ActionId]:
        """Durable PREPARED action (STATE_MACHINES §14 first state).

        Idempotent on action_id: re-creating an existing action replays the
        durable row without writing (stable action identity, DATA_MODEL
        §1.2 — recovery re-dispatch reuses the same action_id, §23 "继续同
        action_id").
        """

        try:
            with short_transaction(self._conn):
                existing = self._action_row(intent.action_id)
                if existing is not None:
                    return Ok(intent.action_id)
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO generation_action_intent ("
                    " action_id, turn_id, decision_cycle_id, moment_id,"
                    " assistant_turn_id, action_type, generation_contract_id,"
                    " status, attempt_count, owner_epoch, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        intent.action_id,
                        intent.turn_id,
                        intent.decision_cycle_id,
                        intent.moment_id,
                        intent.assistant_turn_id,
                        intent.action_type.value,
                        intent.generation_contract_id,
                        intent.status.value,
                        intent.attempt_count,
                        self._fence.current,
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return Err(DomainError(code=DomainErrorCode.CONFLICT, message=str(exc)))
        return Ok(intent.action_id)

    def transition_action(
        self,
        action_id: ActionId,
        expected: GenerationActionStatus,
        new: GenerationActionStatus,
    ) -> Result[GenerationActionIntentRecord]:
        """Advance the §14 state machine under status CAS + epoch fence.

        TERMINAL is immutable: no transition ever leaves it (§14 late-result
        rule). A mismatched expected status or a fenced owner_epoch is a
        conflict, never a silent overwrite (§20).
        """

        if expected == GenerationActionStatus.TERMINAL:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"action {action_id} is TERMINAL — late results never"
                " overwrite a terminal action (STATE_MACHINES §14)",
            )
        with short_transaction(self._conn):
            # Fence inside the write transaction: the adopted epoch must
            # still be the newest in app.db (RUNTIME §24 restart fencing —
            # an old-epoch worker must not advance any action).
            self._require_current_epoch()
            row = self._action_row(action_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"generation action not found: {action_id}",
                )
            if row[9] != self._fence.current:
                return _err(
                    DomainErrorCode.AUTHORITY_VIOLATION,
                    f"owner_epoch={row[9]} fenced by current"
                    f" epoch={self._fence.current}",
                )
            durable = GenerationActionStatus(str(row[7]))
            if durable == GenerationActionStatus.TERMINAL:
                return _err(
                    DomainErrorCode.VALIDATION_FAILED,
                    f"action {action_id} is TERMINAL ({durable}) — no"
                    " canonical side effect from late work",
                )
            if durable != expected:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"status CAS mismatch on {action_id}: expected"
                    f" {expected.value}, durable {durable.value}",
                )
            self._conn.execute(
                "UPDATE generation_action_intent SET status = ?"
                " WHERE action_id = ? AND status = ? AND owner_epoch = ?",
                (new.value, action_id, expected.value, self._fence.current),
            )
            updated = self._action_row(action_id)
            assert updated is not None  # row existed above, same tx
            return Ok(self._record(updated))

    def record_attempt(
        self, attempt: ProviderAttemptRecord
    ) -> Result[ProviderAttemptRecord]:
        """Append one durable ProviderAttempt (RUNTIME §6 CP2.5) and bump
        attempt_count in the same short transaction. The provider call
        itself already happened outside the transaction; this only logs the
        outcome (R-INV-004)."""

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO provider_attempt ("
                    " provider_attempt_id, action_id, attempt_no,"
                    " provider_request_id, request_hash, status, result_hash,"
                    " created_at, terminal_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        attempt.provider_attempt_id,
                        attempt.action_id,
                        attempt.attempt_no,
                        attempt.provider_request_id,
                        attempt.request_hash,
                        attempt.status,
                        attempt.result_hash,
                        attempt.created_at if attempt.created_at else _now(),
                        attempt.terminal_at if attempt.terminal_at else _now(),
                    ),
                )
                self._conn.execute(
                    "UPDATE generation_action_intent SET attempt_count = ?"
                    " WHERE action_id = ?",
                    (attempt.attempt_no, attempt.action_id),
                )
        except sqlite3.IntegrityError as exc:
            return Err(DomainError(code=DomainErrorCode.CONFLICT, message=str(exc)))
        return Ok(attempt)

    def claim_action_for_recovery(
        self, action_id: ActionId
    ) -> Result[GenerationActionIntentRecord]:
        """Startup-recovery adoption: the new runtime epoch takes over an
        old-epoch nonterminal action (RUNTIME §22/§24; SM §17.1 rule 3 —
        the recovery owner may cancel/supersede/finish old work).

        Re-arms the action at REQUESTED under the current epoch so
        re-dispatch retries at the action level (same stable action_id,
        §23 "Crash after CP2: 继续同 action_id"); TERMINAL actions are
        returned unchanged (nothing to recover)."""

        with short_transaction(self._conn):
            row = self._action_row(action_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"generation action not found: {action_id}",
                )
            if GenerationActionStatus(str(row[7])) == GenerationActionStatus.TERMINAL:
                return Ok(self._record(row))
            self._require_current_epoch()
            self._conn.execute(
                "UPDATE generation_action_intent SET status = ?,"
                " owner_epoch = ? WHERE action_id = ? AND status != 'TERMINAL'",
                (
                    GenerationActionStatus.REQUESTED.value,
                    self._fence.current,
                    action_id,
                ),
            )
            updated = self._action_row(action_id)
            assert updated is not None  # row existed above, same tx
            return Ok(self._record(updated))

    # -- reads -------------------------------------------------------------

    def get_action(
        self, action_id: ActionId
    ) -> Result[GenerationActionIntentRecord | None]:
        row = self._action_row(action_id)
        return Ok(None if row is None else self._record(row))

    def get_action_for_turn(
        self, turn_id: TurnId
    ) -> Result[GenerationActionIntentRecord | None]:
        row = self._conn.execute(
            "SELECT action_id, turn_id, decision_cycle_id, moment_id,"
            " assistant_turn_id, action_type, generation_contract_id,"
            " status, attempt_count, owner_epoch, created_at"
            " FROM generation_action_intent WHERE turn_id = ?"
            " ORDER BY created_at, action_id LIMIT 1",
            (turn_id,),
        ).fetchone()
        return Ok(None if row is None else self._record(row))

    def attempts_for(
        self, action_id: ActionId
    ) -> Result[tuple[ProviderAttemptRecord, ...]]:
        rows = self._conn.execute(
            "SELECT provider_attempt_id, action_id, attempt_no,"
            " provider_request_id, request_hash, status, result_hash,"
            " created_at, terminal_at"
            " FROM provider_attempt WHERE action_id = ?"
            " ORDER BY attempt_no",
            (action_id,),
        ).fetchall()
        return Ok(
            tuple(
                ProviderAttemptRecord(
                    provider_attempt_id=ProviderAttemptId(str(row[0])),
                    action_id=ActionId(str(row[1])),
                    attempt_no=int(row[2]),
                    provider_request_id=None if row[3] is None else str(row[3]),
                    request_hash=str(row[4]),
                    status=str(row[5]),
                    result_hash=None if row[6] is None else str(row[6]),
                    created_at=None if row[7] is None else str(row[7]),
                    terminal_at=None if row[8] is None else str(row[8]),
                )
                for row in rows
            )
        )

    def recoverable_generation_actions(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[GenerationActionIntentRecord, ...]:
        """Old-epoch nonterminal actions (RUNTIME §22 recovery scan list
        includes GenerationActionIntent)."""

        rows = self._conn.execute(
            "SELECT action_id, turn_id, decision_cycle_id, moment_id,"
            " assistant_turn_id, action_type, generation_contract_id,"
            " status, attempt_count, owner_epoch, created_at"
            " FROM generation_action_intent"
            " WHERE owner_epoch != ? AND status != 'TERMINAL'"
            " ORDER BY created_at, action_id",
            (current_epoch,),
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    # -- internals -----------------------------------------------------------

    def _action_row(self, action_id: ActionId) -> sqlite3.Row | None:
        # Column order: action_id, turn_id, decision_cycle_id, moment_id,
        # assistant_turn_id, action_type, generation_contract_id, status,
        # attempt_count, owner_epoch, created_at.
        return self._conn.execute(
            "SELECT action_id, turn_id, decision_cycle_id, moment_id,"
            " assistant_turn_id, action_type, generation_contract_id,"
            " status, attempt_count, owner_epoch, created_at"
            " FROM generation_action_intent WHERE action_id = ?",
            (action_id,),
        ).fetchone()

    def _record(self, row: sqlite3.Row) -> GenerationActionIntentRecord:
        return GenerationActionIntentRecord(
            action_id=ActionId(str(row[0])),
            turn_id=TurnId(str(row[1])),
            decision_cycle_id=(
                DecisionCycleId(str(row[2])) if row[2] is not None else None
            ),
            moment_id=None if row[3] is None else str(row[3]),
            assistant_turn_id=str(row[4]),
            action_type=GenerationActionType(str(row[5])),
            generation_contract_id=str(row[6]),
            status=GenerationActionStatus(str(row[7])),
            attempt_count=int(row[8]),
            owner_epoch=RuntimeEpoch(int(row[9])),
            created_at=None if row[10] is None else str(row[10]),
        )
