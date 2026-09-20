"""runtime_epoch startup fence (docs/IMPLEMENTATION_PLAN.md §17-02).

Restart ownership boundary (docs/RUNTIME_ARCHITECTURE.md §24, §24.1):
Local V1 does not guess an owner is dead by expiry — instead every process
start opens a NEW runtime epoch, and durable work stamped with an older
`owner_epoch` becomes recoverable nonterminal work for the new epoch's
startup/opportunistic recovery. No TTL, no heartbeat, no distributed lease
table.

Interface first (Phase 0): the fence and its failure type are canonical
infrastructure; wiring them into TurnRecord/GenerationAction writes happens
with those records' own phases.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


class StaleEpochError(RuntimeError):
    """A write was fenced: its owner_epoch is not the current epoch."""


@dataclass(frozen=True)
class RuntimeEpochFence:
    """Validates epoch-stamped writes against the current epoch."""

    current: int

    def is_stale(self, owner_epoch: int) -> bool:
        return owner_epoch != self.current

    def require_current(self, owner_epoch: int) -> None:
        if self.is_stale(owner_epoch):
            raise StaleEpochError(
                f"owner_epoch={owner_epoch} fenced by current epoch={self.current}"
            )


def open_runtime_epoch(conn: sqlite3.Connection) -> RuntimeEpochFence:
    """Open a new epoch row and return the fence for this process run.

    Call once per process start (startup fence). `runtime_epoch` only grows;
    the new epoch is always max(epoch)+1.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "INSERT INTO runtime_epoch (opened_at) "
            "VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
        )
        row = conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    current = int(row[0])
    return RuntimeEpochFence(current=current)


def load_current_epoch(conn: sqlite3.Connection) -> int | None:
    """Read the newest epoch without opening one (recovery/inspection)."""
    row = conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
    return None if row is None or row[0] is None else int(row[0])
