"""In-process keyed mutex — live ConversationCoordinator guard.

docs/RUNTIME_ARCHITECTURE.md §24: Local Runtime V1 maps
`ConversationCoordinatorLease` to an in-process keyed mutex + runtime_epoch +
durable Turn/Action state. No distributed lock service, no TTL/heartbeat
(docs/IMPLEMENTATION_PLAN.md §17: do not install Redis/Kafka/distributed-lock
infrastructure in bootstrap).
"""

from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Iterator


class CoordinatorBusyError(RuntimeError):
    """Raised when a non-blocking acquire finds the key already held."""


class KeyedMutex:
    """Single-owner guard per key, within one process."""

    def __init__(self) -> None:
        self._guard = Lock()
        self._locks: dict[str, Lock] = {}
        self._held: set[str] = set()

    def _lock_for(self, key: str) -> Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = Lock()
                self._locks[key] = lock
            return lock

    @contextmanager
    def hold(self, key: str, blocking: bool = True) -> Iterator[None]:
        lock = self._lock_for(key)
        if not lock.acquire(blocking=blocking):
            raise CoordinatorBusyError(f"coordinator busy: {key}")
        with self._guard:
            self._held.add(key)
        try:
            yield
        finally:
            with self._guard:
                self._held.discard(key)
            lock.release()

    def is_held(self, key: str) -> bool:
        with self._guard:
            return key in self._held
