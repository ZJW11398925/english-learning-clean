"""The World bounded context (W-1-0 + W-1-1 + W-1-2 + W-1-4 + W-1-3) —
identity binding, the event tree with its minimal state projection, the
run engine, the world package face, and the reveal/inbox half.

What ships here: the three migration-0023 identity tables' SQL face
(:class:`~elc.world.store.SqliteWorldStore` — worlds, actors,
conversation bindings, idempotent writes, value-semantics refusals), the
frozen record shapes (:mod:`elc.world.types`), and W-1-1's event face —
migration 0024's two tables (``world_event``, the append-only chronicle;
``world_state_fact``, the minimal projection with its ``CURRENT`` /
``SUPERSEDED`` lifecycle) written only through the store's
``record_event`` (one atomic settlement), read through the chronicle /
current-facts / fact-history faces — W-1-2's run face: migration
0025's ``world_run`` row plus the deterministic engine
(:mod:`elc.world.engine` — replayable sequencing from ``(seed,
cursor)``, NOTICE checkpoints pause the run, RESPONSE terminates it,
M0.1 AD-6: a restart does not re-roll the dice) — and W-1-3's reveal
face: migration 0026's ``world_reveal_item`` queue (one ``PENDING``
item per event a step wrote, the inbox's atomic
``PENDING`` → ``REVEALED`` flip when the user next looks — the spec
§4.1 presentation trigger, never run fuel) plus the communication
orchestration (:mod:`elc.world.engine.orchestrate` — the
winch and the light action as one callable).

W-1-4 adds the package face: the repository's builtin worlds ship as
JSON files under ``worlds/``, and a builtin world is born at open —
:mod:`elc.world.package` loads them strictly and seeds them through this
store's idempotent create/bind faces (fail-closed: a bad package, a
missing directory or a cast persona with no character card fails the
open). User-created worlds are still bound only by a caller through
``create_world`` / ``bind_actor`` — the builtin worlds' birth at open
does not change who binds anything else. W-1-3's web face binds the web
conversation into the builtin world (idempotent, fail-soft); the CLI
binds nothing.

What does **not** ship here, declared rather than implied: no narration
generation (the engine's pool arrives pre-authored), no presentation
rendering, no ``DIRECTION`` word (W-2-2 opens it) — those are W-2-x
registered cuts, and this package ships none of them rather than a stub
that pretends to. A world this store binds exists as rows, an event
log, its runs and its reveal queue; the cuts that make it live further
are registered, not simulated.

Deletion: the migrations spell no ON DELETE (the RESTRICT posture is
SQLite's default); W-1-3's deletion face moves the conversation binding
(``world_conversation``) into the conversation scope's sweep
(:mod:`elc.deletion`) while the world-owned half stays global.
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
