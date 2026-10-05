"""The World bounded context (W-1-0 + W-1-1 + W-1-2) — identity binding,
the event tree with its minimal state projection, and the run engine.

What ships here: the three migration-0023 identity tables' SQL face
(:class:`~elc.world.store.SqliteWorldStore` — worlds, actors,
conversation bindings, idempotent writes, value-semantics refusals), the
frozen record shapes (:mod:`elc.world.types`), and W-1-1's event face —
migration 0024's two tables (``world_event``, the append-only chronicle;
``world_state_fact``, the minimal projection with its ``CURRENT`` /
``SUPERSEDED`` lifecycle) written only through the store's
``record_event`` (one atomic settlement), read through the chronicle /
current-facts / fact-history faces — and W-1-2's run face: migration
0025's ``world_run`` row plus the deterministic engine
(:mod:`elc.world.engine` — replayable sequencing from ``(seed,
cursor)``, NOTICE checkpoints pause the run, RESPONSE terminates it,
M0.1 AD-6: a restart does not re-roll the dice).

What does **not** ship here, declared rather than implied: no reveal
face, no narration generation (the engine's pool arrives pre-authored),
no presentation rendering, no ``DIRECTION`` word (W-2-2 opens it), no
deletion face — those are W-1-3 / W-2-x registered cuts, and this
package ships none of them rather than a stub that pretends to. A world
this store binds exists as rows, an event log and its runs; the cuts
that make it live further are registered, not simulated.

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
