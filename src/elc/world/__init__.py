"""The World bounded context (W-1-0) — identity binding skeleton.

What ships here: the three migration-0023 identity tables' SQL face
(:class:`~elc.world.store.SqliteWorldStore` — worlds, actors,
conversation bindings, idempotent writes, value-semantics refusals) and
the frozen record shapes (:mod:`elc.world.types`).

What does **not** ship here, declared rather than implied: no world
events, no world engine, no reveal face, no world behaviour of any kind —
W-1-0 is the living-world program's identity cut only (the adjudication
chain DEC-OPI-7e3744ee…2 / DEC-OPI-7e3744ee…4 / DEC-OPI-d96fd92d…7;
conservative overlay, AD-1). A world this store binds exists as rows and
nothing more; the cuts that make it live are registered, not simulated.

Deletion: none. The migration spells no ON DELETE (the RESTRICT posture
is SQLite's default); the deletion face is W-1-3's registered cut.
"""

from __future__ import annotations

from elc.world.store import SqliteWorldStore
from elc.world.types import (
    WorldActorRecord,
    WorldConversationRecord,
    WorldRecord,
)

__all__ = [
    "SqliteWorldStore",
    "WorldRecord",
    "WorldActorRecord",
    "WorldConversationRecord",
]
