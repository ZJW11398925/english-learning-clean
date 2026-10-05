"""The world's communication orchestration (W-1-3) — the winch and the
light action, as one callable.

What this module claims, no more: :func:`run_step` is the living
world's first production caller of the engine (:func:`elc.world.engine.
engine.advance` — the engine stays the only mover of a run row; this
module only decides *whether* and *with what* a step begins, then
hands the fresh run row over). The two triggers spell the spec §4.1
dual-start design's two user actions:

- ``letter`` (发条, the winch): the user's reply is the only run
  starter. When the world's latest run is absent or ``TERMINAL``, a
  new run is wound — its seed is the world's run count (deterministic:
  the same count always draws the same sequence, AD-6) and the
  triggering turn rides the row as ``trigger_turn_id``. When the
  latest run sits ``AT_CHECKPOINT``, the letter *resumes that run*
  (the letter is the light action's superset — the world is mid-run
  and the reply keeps it moving; it is never a second winch).
- ``continue`` (轻继续): only a run paused at its checkpoint resumes.
  Anything else is a refusal in plain words — a world that is not
  waiting has nothing to continue, and saying so beats silently
  starting one.

Reveal enqueue rides the same step: every event the step's ``advance``
wrote leaves exactly one :class:`~elc.world.store.WorldRevealItem`
behind — id derived ``<event_id>:reveal``, signed by that cycle's
comms actor (``None`` = the world's own narration), stamped
``PENDING`` — and the store lands the step's items in **one short
transaction** (:meth:`elc.world.store.SqliteWorldStore.enqueue_reveals`).
A step that refuses enqueues nothing: the trace is read only after
``advance`` answers ``Ok``, so a refused path leaves the queue exactly
as it found it (零撕裂). Revealing is not this module's act — the
inbox's atomic flip (:meth:`elc.world.store.SqliteWorldStore.
reveal_all`) is the presentation half, called when the user next
looks.

What is deliberately absent: no model face, no provider, no narration
generation (the pool's prose arrives pre-authored, AD-2), no waiting,
no rendering, no world clock (the caller's ``now`` is the only
moment), and no DIRECTION word (W-2-2 opens it).

Layering note: this module imports the engine's execution face through
its direct module path (``elc.world.engine.engine``) — the same edge
discipline :mod:`elc.world.engine` documents — and the store; nothing
imports back.
"""

from __future__ import annotations

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.engine.engine import RunTrace, advance
from elc.world.engine.types import EngineConfig, PoolEvent, RunStatus
from elc.world.store import SqliteWorldStore, WorldRevealItem

__all__ = [
    "TRIGGER_CONTINUE",
    "TRIGGER_LETTER",
    "run_step",
]

#: The winch trigger (发条): the user's reply — the only run starter
#: (spec §4.1). Starts a run from nothing or from a TERMINAL stop, and
#: resumes a checkpointed run (the light action's superset).
TRIGGER_LETTER = "letter"

#: The light-continue trigger: resumes a run paused at its checkpoint —
#: and nothing else.
TRIGGER_CONTINUE = "continue"


def _run_id_for(world_id: str, seed: int) -> str:
    """The derived run id: ``run-<world token>-<seed, zero-padded>`` —
    ``world-berrymoor`` plus the run's ordinal derives
    ``run-berrymoor-0000``. The seed is the world's run count at winding
    time, so a replayed letter derives the same id and lands as the
    idempotent no-op :meth:`elc.world.store.SqliteWorldStore.create_run`
    spells; zero-padding keeps the ids and the durable order legible
    past ten runs."""

    token = world_id.removeprefix("world-")
    return f"run-{token}-{seed:04d}"


def run_step(
    store: SqliteWorldStore,
    world_id: str,
    pool: tuple[PoolEvent, ...],
    config: EngineConfig,
    trigger: str,
    now: str,
    trigger_turn_id: str | None = None,
) -> Result[RunTrace]:
    """One world step: the trigger's act, then the engine's advance,
    then the step's reveal enqueue — in that order, refusals short-
    circuiting each.

    ``trigger`` is exactly one of :data:`TRIGGER_LETTER` /
    :data:`TRIGGER_CONTINUE`; anything else is a ``VALIDATION_FAILED``
    naming the two words (a typo must not silently mean either).

    The step is deterministic end to end: the seed is the world's run
    count, the run id derives from it, and the engine replays its
    ``(seed, cursor)`` draws — the same world history always produces
    the same step. The caller owns ``now`` (no hidden clock) and, for a
    letter from nothing, ``trigger_turn_id`` (the reply that wound the
    spring, when the caller knows it).
    """

    if trigger not in (TRIGGER_LETTER, TRIGGER_CONTINUE):
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"world step for {world_id!r} refused: unknown"
                    f" trigger {trigger!r} (the vocabulary is"
                    f" {TRIGGER_LETTER!r} / {TRIGGER_CONTINUE!r})"
                ),
            )
        )

    runs = store.list_runs(world_id)
    latest = runs[-1] if runs else None

    if trigger == TRIGGER_CONTINUE:
        if latest is None or latest.status is not RunStatus.AT_CHECKPOINT:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"world {world_id!r} is not waiting at a"
                        " checkpoint — there is nothing to continue;"
                        " the world moves when your reply winds it"
                    ),
                )
            )
        run = latest
    else:
        if latest is None or latest.status is RunStatus.TERMINAL:
            seed = len(runs)
            created = store.create_run(
                _run_id_for(world_id, seed),
                world_id,
                trigger_turn_id,
                seed,
                now,
            )
            if isinstance(created, Err):
                return Err(created.error)
            run = created.value
        else:
            # The world is mid-run (paused at its checkpoint): the letter
            # resumes it — the light action's superset, never a second
            # winch (spec §4.2's 收口).
            run = latest

    stepped = advance(store, run, pool, config, now)
    if isinstance(stepped, Err):
        return Err(stepped.error)

    # The reveal enqueue: one PENDING item per event the step wrote, the
    # whole batch in one short transaction. Only an Ok step reaches here,
    # so a refused path enqueues nothing (零撕裂); the items derive their
    # ids from the events, so a replayed step enqueues as the store's
    # idempotent no-op.
    items = tuple(
        WorldRevealItem(
            item_id=f"{cycle.event_id}:reveal",
            world_id=world_id,
            source_event_id=str(cycle.event_id),
            actor_id=cycle.actor,
            status="PENDING",
            revealed_at=None,
            created_at=now,
        )
        for cycle in stepped.value.cycles
        if cycle.event_id is not None
    )
    enqueued = store.enqueue_reveals(items)
    if isinstance(enqueued, Err):
        return Err(enqueued.error)
    return Ok(stepped.value)
