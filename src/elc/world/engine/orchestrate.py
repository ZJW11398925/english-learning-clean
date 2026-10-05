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
no rendering, and no DIRECTION word (W-2-2 opens it). The world's own
time is the virtual calendar's (A2, DEC-…88/…90): with a package the
step stamps its events on ``calendar_start`` plus the story's spans —
the caller's ``now`` keeps only the run row's bookkeeping.

Layering note: this module imports the engine's execution face through
its direct module path (``elc.world.engine.engine``) — the same edge
discipline :mod:`elc.world.engine` documents — and the store; nothing
imports back.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.engine.engine import RunTrace, advance
from elc.world.engine.types import EngineConfig, PoolEvent, RunStatus
from elc.world.package import WorldPackage, story_days_of
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
    package: WorldPackage | None = None,
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

    A2 (DEC-…88/…90): with a ``package`` the step stamps its events on
    the **virtual world calendar** — the story's own time (spec §198:
    the world does not follow real time). The timestamp source answers
    per event: the event's moment is ``calendar_start`` plus every
    happened event's story span up to and including this one (落笔在
    跨度之末), so the same history replays to the same dates and a
    different story answers different dates at the same letter count.
    ``now`` (the caller's wall moment) keeps the run row's own
    bookkeeping stamps; it never reaches a world event. Every
    production caller passes the package (the web face's letter wiring,
    its streamed pre-step and its 「继续」 route alike); a caller
    without a package stamps the events with its own ``now`` exactly as
    before A2 — the engine-direct tests' shape, kept for them.
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

    moment_source: str | Callable[[str], str] = now
    if package is not None:
        moment_source = _calendar_source(package, store, world_id)
    stepped = advance(store, run, pool, config, moment_source)
    if isinstance(stepped, Err):
        return Err(stepped.error)

    # The reveal enqueue: one PENDING item per event the step wrote, the
    # whole batch in one short transaction. Only an Ok step reaches here,
    # so a refused path enqueues nothing (零撕裂); the items derive their
    # ids from the events, so a replayed step enqueues as the store's
    # idempotent no-op. The item's own stamp inherits **its own event's**
    # moment (the calendar's date when a package rides, DEC-…88 ③) —
    # read back from the chronicle the step just wrote, so a multi-beat
    # call stamps each item with its own beat, never the last one's
    # (A2R DEC-…99); the queue carries the story's time, never the wall
    # clock's.
    step_event_ids = {
        str(cycle.event_id)
        for cycle in stepped.value.cycles
        if cycle.event_id is not None
    }
    chronicle = store.chronicle_of(world_id)
    if isinstance(chronicle, Err):
        return Err(chronicle.error)
    moments = {
        str(event.event_id): str(event.occurred_at)
        for event in chronicle.value
        if str(event.event_id) in step_event_ids
    }
    items = tuple(
        WorldRevealItem(
            item_id=f"{cycle.event_id}:reveal",
            world_id=world_id,
            source_event_id=str(cycle.event_id),
            actor_id=cycle.actor,
            status="PENDING",
            revealed_at=None,
            created_at=moments.get(str(cycle.event_id), now),
        )
        for cycle in stepped.value.cycles
        if cycle.event_id is not None
    )
    enqueued = store.enqueue_reveals(items)
    if isinstance(enqueued, Err):
        return Err(enqueued.error)
    return Ok(stepped.value)


def _calendar_source(
    package: WorldPackage,
    store: SqliteWorldStore,
    world_id: str,
) -> Callable[[str], str]:
    """The virtual world calendar's timestamp source (A2, DEC-…88/…90):
    per event kind, the date ``calendar_start`` plus every happened
    event's story span **including this one** — the story writes its
    event at the end of its own span (落笔在跨度之末). The elapsed base
    is read once at step time from the durable chronicle
    (:func:`elc.world.package.story_days_of`), and each stamp advances
    the closure's running total, so a multi-event step (A2R DEC-…99's
    beat run) accumulates within the step exactly as it does across
    steps. Deterministic: the same chronicle answers the same dates."""

    start = date.fromisoformat(package.calendar_start)
    days_by_kind = {event.kind: event.days for event in package.event_pool}
    state = {"total": story_days_of(package, store, world_id)}

    def _stamp(kind: str) -> str:
        # An unknown kind ("" for the LIMIT ceiling's no-event exit)
        # carries no span of its own — the closure answers the running
        # date without advancing the story.
        state["total"] += days_by_kind.get(kind, 0)
        return (start + timedelta(days=state["total"])).isoformat()

    return _stamp
