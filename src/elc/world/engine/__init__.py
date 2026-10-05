"""elc.world.engine — the living world's run engine (W-1-2).

**What this package claims** — and only this: deterministic run
orchestration (the seven-step body's steps 2–5: time advance, event
maturity, communication v1, the moment's double exit), replayable
sequencing (every cycle's draws seeded from ``(seed, cursor)`` — the
same seed replays the same run; a resume continues it, never re-rolls
it, M0.1 AD-6), durable run state (migration 0025's ``world_run`` row,
advanced only through the store's run face), and the double exit
(``NOTICE`` checkpoints pause the run, ``RESPONSE`` terminates it).

**What this package does not simulate, declared rather than implied**:
no presentation rendering (step 6 is declared in
:mod:`elc.world.engine.steps`, not performed), no waiting behaviour
(step 7 — the TERMINAL row itself is the waiting), no real letters (the
communication step records a decision in the trace and generates
nothing), no reveal face, no ``DIRECTION`` word (W-2-2 opens it), no
world clock (the caller's ``now`` is the only moment), and no model
generation of any kind — the pool's narration arrives pre-authored and
the engine invents nothing.

Module map: :mod:`elc.world.engine.types` — the run record, the moment
and status vocabularies, the config, the pool and condition shapes;
:mod:`elc.world.engine.steps` — the seven steps, declared;
:mod:`elc.world.engine.engine` — the ``advance`` face and the trace
shapes (imported directly, not re-exported here: the store imports this
package's record shapes and the engine imports the store, so the
execution face stays a direct-module import and the two edges never
form a cycle).
"""

from __future__ import annotations

from elc.world.engine.steps import (
    STEP_COMMS,
    STEP_EVENTS,
    STEP_MOMENT,
    STEP_RENDER,
    STEP_TIME,
    STEP_WAIT,
    STEP_WINCH,
    STEPS,
)
from elc.world.engine.types import (
    Condition,
    EngineConfig,
    MomentKind,
    PoolEvent,
    RunStatus,
    WorldRunRecord,
)

__all__ = [
    "STEPS",
    "STEP_COMMS",
    "STEP_EVENTS",
    "STEP_MOMENT",
    "STEP_RENDER",
    "STEP_TIME",
    "STEP_WAIT",
    "STEP_WINCH",
    "Condition",
    "EngineConfig",
    "MomentKind",
    "PoolEvent",
    "RunStatus",
    "WorldRunRecord",
]
