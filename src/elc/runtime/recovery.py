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

P3-2 carry-over (DEC-OPI-5ba74efc-….20 ①): the scan also *names* the
TeachingLockLease residue of a dead runtime epoch. Before this, an orphan
teaching lock was only reachable through an explicit
``ConversationCoordinator.recover_orphan_teaching()`` call that no startup
path made, so a conversation whose teaching process died stayed sealed
until something happened to call the apply face. The scanner now reports
one :data:`TEACHING_LOCK_RECOVERY_ACTION` item per orphan lock (kind
``LOCK``, id = the moment id) through the optional
:class:`TeachingLockRecoverySource` port — the same pure-read bargain as
the TurnRecord list (STARTS nothing, writes nothing; the apply face is the
coordinator's), so the plan and the sweep can never disagree about which
lock is residue. A lock owned by the *current* epoch is a real
mutual-exclusion fact and is deliberately not part of the plan
(STATE_MACHINES §9/§24.1: epoch-based liveness, never TTL/heartbeat).

P3-3 review F6 (DEC-OPI-5ba74efc-….43): the plan now has a startup *entry*
— ``ConversationCoordinator.run_startup_recovery`` builds this scanner from
its own injected ports, scans once, and then applies what a new epoch may
apply (the lock sweep, plus the turn-level reconciliation of the delivery
residue that sweep just unsealed). This module stays the read half; the
coordinator stays the only writer.
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
    "RECOVERY_KIND_LOCK",
    "RECOVERY_KIND_TURN",
    "TEACHING_LOCK_RECOVERY_ACTION",
    "StartupRecoveryScanner",
    "TeachingLockRecoverySource",
    "TurnRecordRecoverySource",
    "recovery_disposition",
]

#: The two plan-item kinds the scan produces (``RecoveryAction.kind``).
#: ``TURN`` names one old-epoch nonterminal TurnRecord; ``LOCK`` names one
#: orphan TeachingLockLease. Named here because the *apply* face
#: (``ConversationCoordinator.run_startup_recovery``) reads the same
#: vocabulary the scan writes — one definition, two faces.
RECOVERY_KIND_TURN = "TURN"
RECOVERY_KIND_LOCK = "LOCK"

#: The recovery action word of the TeachingLockLease sweep (P3-2 carry-over
#: ①): the orphan lock named by the scan is released — and with it its
#: moment closed with ``SYSTEM_RECOVERY_ABORT`` — by
#: ``ConversationCoordinator.recover_orphan_teaching`` (STATE_MACHINES §9).
TEACHING_LOCK_RECOVERY_ACTION = "RELEASE_ORPHAN_TEACHING_LOCK"


@runtime_checkable
class TurnRecordRecoverySource(Protocol):
    """Durable read face for the recovery scan (implemented by the
    conversation store; RUNTIME §22 scans nonterminal records)."""

    def recoverable_turn_records(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[TurnRecordData, ...]:
        ...


@runtime_checkable
class TeachingLockRecoverySource(Protocol):
    """Durable read face for the teaching-lock scan (implemented by the
    Teaching domain store / its controller face — the runtime package
    stays SQL-free, Gate item 2).

    Returns the moment ids whose ``active_teaching_lock`` row is owned by
    a turn of an *older* runtime epoch: residue of a dead process, never a
    live mutual-exclusion fact (STATE_MACHINES §9 "startup recovery 通过
    durable Moment state + runtime_epoch revalidate/release orphan lock";
    §24.1: no TTL/heartbeat in Local V1).
    """

    def orphan_teaching_lock_moments(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[str, ...]:
        ...


def recovery_disposition(status: TurnStatus) -> str:
    """RUNTIME_ARCHITECTURE §24.1 checkpoint → disposition mapping.

    P1A only ever produces CP0-committed turns (USER_COMMITTED); the other
    mappings exist so the scan speaks the full §24.1 vocabulary as soon as
    later phases advance TurnRecords past CP0.

    Review F3 (DEC-…5ba74efc.43, P3-3 carry-over): ``DELIVERING`` is the
    CP3-uncertain slot — the action was dispatched and the process died
    before the delivery leg was canonicalized, which is exactly §24.1's
    "CP3 uncertain → CONSERVATIVE_DELIVERY_RECONCILIATION" (RA §23: "若
    delivery uncertain，保守 canonicalize，不盲目重放"). The P1A
    placeholder mapped it together with ``GENERATING`` onto
    ``RESUME_ACTION_BY_STABLE_ACTION_ID``; that is the CP2 rule (the
    action is stable and still undelivered) and it is what the coordinator
    does for a ``GENERATING`` turn. A ``DELIVERING`` turn gets the
    conservative reconciliation instead: the durable transcript decides
    whether the message went out, and the leg is completed from that
    record — never re-dispatched onto a user who may already have seen it.
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
    if status == TurnStatus.GENERATING:
        return "RESUME_ACTION_BY_STABLE_ACTION_ID"  # CP2 done
    return "CONSERVATIVE_DELIVERY_RECONCILIATION"  # CP3 uncertain


class StartupRecoveryScanner:
    """Identify old-epoch nonterminal TurnRecords as recovery work.

    The scan never rewrites anything: repeated ``scan()`` calls are
    idempotent, and already-committed CP0 UserTurns are only *referenced*,
    never replayed (§22; VAL ④).

    P3-2 carry-over ①: with a ``teaching_locks`` source the plan also names
    one ``LOCK`` item per orphan TeachingLockLease (see the module
    docstring). The teaching source is optional so every P1/P2 assembly
    keeps the exact plan shape its tests pin.
    """

    def __init__(
        self,
        source: TurnRecordRecoverySource,
        lease: ConversationCoordinatorLease,
        teaching_locks: TeachingLockRecoverySource | None = None,
    ) -> None:
        self._source = source
        self._lease = lease
        self._teaching_locks = teaching_locks

    def scan(self) -> Result[tuple[RecoveryAction, ...]]:
        """Return the recovery plan for old-epoch nonterminal work."""
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
        actions = [
            RecoveryAction(
                kind=RECOVERY_KIND_TURN,
                id=record.turn_id,
                action=recovery_disposition(record.status),
            )
            for record in records
            if record.status not in TERMINAL_TURN_STATUSES
        ]
        if self._teaching_locks is not None:
            # Deterministic order (the source returns the durable ORDER BY):
            # turn work first, then the lock residue it may unseal.
            actions.extend(
                RecoveryAction(
                    kind=RECOVERY_KIND_LOCK,
                    id=moment_id,
                    action=TEACHING_LOCK_RECOVERY_ACTION,
                )
                for moment_id in self._teaching_locks.orphan_teaching_lock_moments(
                    epoch
                )
            )
        return Ok(tuple(actions))
