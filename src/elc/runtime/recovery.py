"""Startup recovery scan — old-epoch nonterminal work (Phase 1 P1A slice).

docs/RUNTIME_ARCHITECTURE.md:
- §22: recovery 扫描非 terminal 记录；只恢复未完成 action/projection，不重跑
  整个 user turn。
- §23 / §23 "Crash after CP0": 从 analysis 继续 — 已提交的 UserTurn 不重放。
- §24 "Crash recovery": Local V1 不以 expiry 猜 owner 已死，而由新的
  runtime_epoch 对旧 epoch nonterminal work 做 startup/opportunistic
  recovery。
- §24.1 disposition vocabulary:
    CP0 → RESUME_ANALYSIS
    CP1 → RESUME_DECISION
    CP2 → RESUME_ACTION_BY_STABLE_ACTION_ID
    CP3 uncertain → CONSERVATIVE_DELIVERY_RECONCILIATION

P1A scope (TASK-OPI-091f35c3.11 deliverable ③): *identify* recoverable
TurnRecords only. The scan is a pure durable read — invoking it twice yields
the same plan, and committed UserTurns are never re-created. The read
itself is executed by the durable conversation store (Gate item 2 keeps
this package SQL-free) behind :class:`TurnRecordRecoverySource`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
    RuntimeEpoch,
)
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    RecoveryAction,
    TurnRecordData,
    TurnStatus,
)

__all__ = [
    "StartupRecoveryScanner",
    "TurnRecordRecoverySource",
    "recovery_disposition",
]


@runtime_checkable
class TurnRecordRecoverySource(Protocol):
    """Durable read face for the recovery scan (implemented by the
    conversation store; RUNTIME §22 scans nonterminal records)."""

    def recoverable_turn_records(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[TurnRecordData, ...]:
        ...


def recovery_disposition(status: TurnStatus) -> str:
    """RUNTIME_ARCHITECTURE §24.1 checkpoint → disposition mapping.

    P1A only ever produces CP0-committed turns (USER_COMMITTED); the other
    mappings exist so the scan speaks the full §24.1 vocabulary as soon as
    later phases advance TurnRecords past CP0.
    """
    if status in TERMINAL_TURN_STATUSES:
        raise ValueError(f"terminal status {status} is not recoverable work")
    if status in (
        TurnStatus.RECEIVED,
        TurnStatus.USER_COMMITTED,
        TurnStatus.ANALYZING,
        TurnStatus.FAILED_RECOVERABLE,
    ):
        return "RESUME_ANALYSIS"  # CP0 committed → resume at analysis (§23)
    if status == TurnStatus.DECIDING:
        return "RESUME_DECISION"  # CP1 done, decision pending
    if status in (TurnStatus.GENERATING, TurnStatus.DELIVERING):
        return "RESUME_ACTION_BY_STABLE_ACTION_ID"  # CP2 done
    return "CONSERVATIVE_DELIVERY_RECONCILIATION"  # CP3 uncertain


class StartupRecoveryScanner:
    """Identify old-epoch nonterminal TurnRecords as recovery work.

    The scan never rewrites anything: repeated ``scan()`` calls are
    idempotent, and already-committed CP0 UserTurns are only *referenced*,
    never replayed (§22; VAL ④).
    """

    def __init__(
        self,
        source: TurnRecordRecoverySource,
        lease: ConversationCoordinatorLease,
    ) -> None:
        self._source = source
        self._lease = lease

    def scan(self) -> Result[tuple[RecoveryAction, ...]]:
        """Return the recovery plan for old-epoch nonterminal turns."""
        epoch = self._lease.epoch
        if epoch is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "startup fence not opened — adopt a runtime_epoch"
                        " first"
                    ),
                )
            )
        records = self._source.recoverable_turn_records(epoch)
        actions = tuple(
            RecoveryAction(
                kind="TURN",
                id=record.turn_id,
                action=recovery_disposition(record.status),
            )
            for record in records
            if record.status not in TERMINAL_TURN_STATUSES
        )
        return Ok(actions)
