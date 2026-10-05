"""The World bounded context (W-1-0 + W-1-1) — identity binding and the
event tree with its minimal state projection.

What ships here: the three migration-0023 identity tables' SQL face
(:class:`~elc.world.store.SqliteWorldStore` — worlds, actors,
conversation bindings, idempotent writes, value-semantics refusals), the
frozen record shapes (:mod:`elc.world.types`), and W-1-1's event face —
migration 0024's two tables (``world_event``, the append-only chronicle;
``world_state_fact``, the minimal projection with its ``CURRENT`` /
``SUPERSEDED`` lifecycle) written only through the store's
``record_event`` (one atomic settlement), read through the chronicle /
current-facts / fact-history faces.

What does **not** ship here, declared rather than implied: no world
engine, no reveal face, no narration generation, no world behaviour of
any kind — W-1-1 lands the event tree and its minimal projection only
(the adjudication chain DEC-OPI-7e3744ee…2 / DEC-OPI-7e3744ee…4 /
DEC-OPI-d96fd92d…7 / DEC-OPI-7e3744ee…17; conservative overlay, AD-1).
A world this store binds exists as rows and an event log; the cuts that
make it live are registered, not simulated.

Deletion: none. The migrations spell no ON DELETE (the RESTRICT posture
is SQLite's default); the deletion face is W-1-3's registered cut.
"""

from __future__ import annotations

from elc.world.store import SqliteWorldStore
from elc.world.types import (
    StateEffect,
    WorldActorRecord,
    WorldConversationRecord,
    WorldEvent,
    WorldRecord,
    WorldStateFact,
    decode_effects,
    encode_effects,
)

__all__ = [
    "SqliteWorldStore",
    "WorldRecord",
    "WorldActorRecord",
    "WorldConversationRecord",
    "StateEffect",
    "WorldEvent",
    "WorldStateFact",
    "encode_effects",
    "decode_effects",
]
