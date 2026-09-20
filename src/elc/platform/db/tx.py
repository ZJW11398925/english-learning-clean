"""Short-transaction helper (docs/IMPLEMENTATION_PLAN.md §17-02).

Canonical commit points (CP0/CP2/terminalization/CP3, docs/DATA_MODEL.md §2)
are short atomic units. This helper makes the shortness a property of the
code shape: BEGIN IMMEDIATE → work → COMMIT, with rollback on any error and
a hard refusal to nest (a transaction inside a transaction is exactly the
long-transaction drift docs/RUNTIME_ARCHITECTURE.md R-INV-004 forbids).

All SQL here is a fixed literal; the helper carries no parameters at all.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator


class TransactionStateError(RuntimeError):
    """Transaction discipline violated (nesting, or provider call inside tx)."""


def in_transaction(conn: sqlite3.Connection) -> bool:
    return bool(conn.in_transaction)


@contextmanager
def short_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run one short atomic unit; commit on success, rollback on any error."""
    if in_transaction(conn):
        raise TransactionStateError(
            "short_transaction must not nest — keep provider calls outside"
        )
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def require_no_active_transaction(conn: sqlite3.Connection, op: str) -> None:
    """Guard for external side effects (provider calls, projections).

    docs/RUNTIME_ARCHITECTURE.md R-INV-004: provider call 不在长 DB
    transaction 内。
    """
    if in_transaction(conn):
        raise TransactionStateError(f"{op} 必须运行在 DB transaction 之外")
