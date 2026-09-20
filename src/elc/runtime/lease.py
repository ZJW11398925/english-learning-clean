"""ConversationCoordinatorLease — Local V1 physical mapping.

docs/STATE_MACHINES.md §17: the lease is a *logical* coordination contract
("same conversation 只有一个 user-visible coordinator"). Local Runtime V1
maps it to

    per-conversation in-process keyed mutex
    + runtime_epoch restart fencing
    + durable TurnRecord / GenerationAction state

No durable coordinator lease table, no TTL, no heartbeat (also
docs/RUNTIME_ARCHITECTURE.md §24 / §24.1; docs/IMPLEMENTATION_PLAN.md §17:
do not install Redis/Kafka/distributed-lock infrastructure). New
InputEnvelopes / InterruptRequests stay durable *outside* the guard (§17.1;
§24); only the guard holder canonicalizes old partial output and
terminalizes the old turn.

This module carries no SQL and no sqlite3 — Gate item 2 keeps elc.runtime
DB-free; durability of the guarded writes lives in the conversation store.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from elc.platform.sync import KeyedMutex
from elc.platform.types import ConversationId, RuntimeEpoch

__all__ = [
    "ConversationCoordinatorLease",
    "LeaseGuard",
    "StaleCoordinatorEpoch",
]


class StaleCoordinatorEpoch(RuntimeError):
    """A guarded operation referenced an owner_epoch that is not the lease's
    adopted runtime epoch (restart fencing, RUNTIME_ARCHITECTURE §24)."""


@dataclass(frozen=True)
class LeaseGuard:
    """Handle proving the caller currently holds the conversation guard."""

    conversation_id: ConversationId
    epoch: RuntimeEpoch


class ConversationCoordinatorLease:
    """Keyed in-process coordinator guard with runtime_epoch fencing."""

    def __init__(self, mutex: KeyedMutex | None = None) -> None:
        self._mutex = mutex if mutex is not None else KeyedMutex()
        self._epoch: RuntimeEpoch | None = None

    # -- epoch adoption (startup fence) ------------------------------------

    def adopt_epoch(self, current: RuntimeEpoch) -> None:
        """Adopt the runtime epoch opened at process start
        (elc.platform.db.epoch.open_runtime_epoch)."""
        self._epoch = current

    @property
    def epoch(self) -> RuntimeEpoch | None:
        """Epoch adopted at startup; None before the startup fence ran."""
        return self._epoch

    def require_current_epoch(self, owner_epoch: RuntimeEpoch) -> None:
        """Fence check: ``owner_epoch`` must be this lease's adopted epoch."""
        if self._epoch is None:
            raise StaleCoordinatorEpoch(
                "lease has no adopted runtime_epoch — open the startup fence"
                " before guarded work"
            )
        if owner_epoch != self._epoch:
            raise StaleCoordinatorEpoch(
                f"owner_epoch={owner_epoch} fenced by current"
                f" epoch={self._epoch}"
            )

    # -- guard -------------------------------------------------------------

    @contextmanager
    def hold(
        self, conversation_id: ConversationId, blocking: bool = True
    ) -> Iterator[LeaseGuard]:
        """Hold the conversation's coordinator guard (STATE_MACHINES §17).

        ``blocking=False`` raises elc.platform.sync.CoordinatorBusyError when
        another worker already owns the conversation. The startup fence must
        have been adopted first — the guard is epoch-scoped by design.
        """
        if self._epoch is None:
            raise StaleCoordinatorEpoch(
                "lease has no adopted runtime_epoch — open the startup fence"
                " before holding the guard"
            )
        with self._mutex.hold(str(conversation_id), blocking=blocking):
            yield LeaseGuard(
                conversation_id=conversation_id, epoch=self._epoch
            )

    def is_held(self, conversation_id: ConversationId) -> bool:
        """True while some worker holds this conversation's guard."""
        return self._mutex.is_held(str(conversation_id))
