"""World/Lore durable face — :class:`SqliteWorldLoreStore` (migration 0020).

主线-3 (DEC-OPI-32409938…36 R2): the bounded context's write and read face.
The store is the SQL home and keeps all truth; the controller is the
authority face over it (the learning/scheduler graduation shape).

The declared minimal semantics (R2): **direct fact rows + reads**. The
shipped batch is seeded by the composition root (:mod:`elc.world_lore.content`)
through :meth:`SqliteWorldLoreStore.add_fact`, whose append is idempotent by
primary key — an open re-seeds the same rows into a no-op. The proposal→
approval editing flow (``propose_lore_fact``'s VALIDATE/COMMIT/REJECT/ABSTAIN
decision, P-INV-013) is **registered, not simulated**: proposals land as
``status='PENDING'`` rows through the controller, and no view ever serves a
PENDING row — the approval cut that flips PENDING→ACTIVE is the registered
next face.

Row shapes: the durable row (:class:`WorldLoreFactRow`) carries the table's
full column set; the canonical shape handed to consumers is the Phase 0
:class:`~elc.world_lore.types.WorldLoreRecord` word for word — the view and
the fact read never expose scope/persona/status bookkeeping, so a consumer
cannot grow a dependency on storage metadata it should not read.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
    WorldLoreFactId,
)
from elc.world_lore.types import WorldLoreFactKind, WorldLoreRecord, WorldLoreView

__all__ = [
    "WorldLoreFactRow",
    "WorldLoreStoreError",
    "SqliteWorldLoreStore",
]

#: The two statuses a row can carry (the migration's CHECK): ACTIVE is
#: canonical and view-visible, PENDING is a proposal nobody serves.
FACT_STATUSES: tuple[str, ...] = ("ACTIVE", "PENDING")


class WorldLoreStoreError(RuntimeError):
    """A fact write failed at the composition boundary (the seed raises it
    so a failed open is loud, never a half-seeded world)."""


@dataclass(frozen=True)
class WorldLoreFactRow:
    """One durable fact row — the migration 0020 column set.

    ``write_epoch`` and ``created_at`` are storage stamps the store fills at
    write time (the fence's epoch; the house clock), so content modules
    declare the eight semantic columns only.
    """

    world_lore_fact_id: str
    scope: str
    persona_id: str | None
    fact_kind: WorldLoreFactKind
    canonical_key: str
    statement: str
    source: str
    status: str = "ACTIVE"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


class SqliteWorldLoreStore:
    """The World/Lore write and read face over migration 0020's table.

    Every statement is fixed literal text with bound parameters. Writes go
    through one short transaction each; reads are plain queries (the
    controller guards the turn-facing call, the store does not pretend a
    SELECT needs fencing).
    """

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- write face ----------------------------------------------------------

    def add_fact(self, fact: WorldLoreFactRow) -> Result[WorldLoreFactId]:
        """Append one canonical fact row, idempotently by id.

        Append-first (R2): a repeated id is a no-op — the seed re-runs every
        open and must stay silent — while a shape refusal (unknown scope or
        status, a character fact without its persona, a world fact with one)
        is a ``VALIDATION_FAILED`` answer, never a guessed row.
        """

        if fact.scope not in ("world", "character"):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=f"unknown lore scope: {fact.scope!r}",
                )
            )
        if (fact.scope == "character") != (fact.persona_id is not None):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        "a character fact needs its persona_id and a world"
                        " fact must not carry one"
                    ),
                )
            )
        if fact.status not in FACT_STATUSES:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=f"unknown lore status: {fact.status!r}",
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT OR IGNORE INTO world_lore_fact ("
                " world_lore_fact_id, scope, persona_id, fact_kind,"
                " canonical_key, statement, source, status,"
                " write_epoch, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fact.world_lore_fact_id,
                    fact.scope,
                    fact.persona_id,
                    fact.fact_kind.value,
                    fact.canonical_key,
                    fact.statement,
                    fact.source,
                    fact.status,
                    self._fence.current,
                    _now(),
                ),
            )
        except sqlite3.Error as exc:
            # ml3R LOW-1: when BEGIN itself failed (a pending transaction,
            # a lock), nothing of ours began — in_transaction then belongs
            # to the caller and must not be rolled back here; and a failing
            # ROLLBACK of our own must not break the Result contract.
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"world lore write failed: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(WorldLoreFactId(fact.world_lore_fact_id))

    # -- read face -----------------------------------------------------------

    def facts_for_view(self, persona_id: str | None) -> tuple[WorldLoreRecord, ...]:
        """The resolved view's facts: every ACTIVE world fact plus the
        ACTIVE character facts of one persona, in the store's durable order
        (``canonical_key`` ascending, id as the tiebreak — the order the
        prompt renders, so it is content, not an implementation detail).

        A ``persona_id`` of ``None`` is the unbound-conversation shape: the
        common world only. SQL errors propagate — the turn-facing caller
        guards this read.
        """

        rows = self._conn.execute(
            "SELECT world_lore_fact_id, fact_kind, canonical_key, statement"
            " FROM world_lore_fact"
            " WHERE status = 'ACTIVE'"
            " AND (scope = 'world' OR (scope = 'character' AND persona_id = ?))"
            " ORDER BY canonical_key ASC, world_lore_fact_id ASC",
            (persona_id,),
        ).fetchall()
        return tuple(
            WorldLoreRecord(
                world_lore_fact_id=WorldLoreFactId(str(row[0])),
                fact_kind=WorldLoreFactKind(str(row[1])),
                canonical_key=str(row[2]),
                statement=str(row[3]),
            )
            for row in rows
        )

    def view_for(self, persona_id: str | None) -> WorldLoreView:
        """The resolved :class:`WorldLoreView` for one scope (the shape the
        controller hands the coordinator)."""

        return WorldLoreView(facts=self.facts_for_view(persona_id))

    def get_fact(self, fact_id: WorldLoreFactId) -> Result[WorldLoreRecord | None]:
        """One fact by id, canonical shape; ``None`` when the id is unknown."""

        row = self._conn.execute(
            "SELECT world_lore_fact_id, fact_kind, canonical_key, statement"
            " FROM world_lore_fact WHERE world_lore_fact_id = ?",
            (str(fact_id),),
        ).fetchone()
        if row is None:
            return Ok(None)
        return Ok(
            WorldLoreRecord(
                world_lore_fact_id=WorldLoreFactId(str(row[0])),
                fact_kind=WorldLoreFactKind(str(row[1])),
                canonical_key=str(row[2]),
                statement=str(row[3]),
            )
        )

    def count(self, status: str = "ACTIVE") -> int:
        """Row count at one status (the seed pin's arithmetic; not a domain
        face — diagnostics for the assembly and the tests)."""

        row = self._conn.execute(
            "SELECT COUNT(*) FROM world_lore_fact WHERE status = ?", (status,)
        ).fetchone()
        return int(row[0])
