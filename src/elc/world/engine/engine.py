"""The world-run engine's advance face (W-1-2) — deterministic,
replayable, durable.

WR-2（DEC-OPI-5fc42174…49）起非生产面——生产世界步走 narrator 生成面
（:mod:`elc.world.narrator` 经 orchestrate.run_generated_step）；本模块
留库为确定性引擎面（W-1-2 测试在册）。

What this cut claims, no more: the seven-step body's deterministic half
(steps 2–5 of :mod:`elc.world.engine.steps`), one ``advance`` call per
stop-or-ceiling (A2R, DEC-…99: a ``NOTICE`` event is a **beat, not a
pause** — the loop continues past it; only a ``RESPONSE`` event or the
``max_cycles`` ceiling ends the call), every cycle's draws seeded from
``(seed, cursor)`` — the same seed and the same cursor always draw the
same selection, so a run resumed across restarts continues exactly the
sequence a single sitting would have produced (M0.1 AD-6: 跨重启不重新
撰骰 — the PRNG is never re-authored, it is re-played). The trace is a
deterministic structural record: step names, the mature set, the
selection, the chronicle entry and the actor decision, cycle by cycle.

What is deliberately absent: no rendering, no waiting, no letters, no
reveal, no DIRECTION word, no mechanical calendar, no narration
generation, no model face, no provider — the pool's narration arrives
pre-authored (AD-2's continuity) and the engine invents nothing.

The clock: there is none. ``advance`` takes the caller's ``now`` and
stamps it on the events this call writes; nothing in the engine reads a
clock of its own (the chronicle stays derived from caller moments — the
0024 convention), and the docstrings say so rather than imply it. A2
(DEC-…88/…90): ``now`` may also be a **timestamp source** — a callable
that answers one event's moment from its kind (the virtual world
calendar's per-event stamp, the story's own span) — and the engine asks
it once per written event; a plain string keeps the exact pre-A2
behavior, one moment for the whole call. The engine itself never
computes a date.

Layering note: this module imports the store (the engine is the run
face's only mover) while the store imports only the engine's *record
shapes* (:mod:`elc.world.engine.types`) — which is why the package's
``__init__`` re-exports the shapes and the steps but not this module:
importing the execution face goes through ``elc.world.engine.engine``
directly, and the store → shapes / engine → store edges never meet in a
cycle.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.engine.steps import STEP_COMMS, STEP_EVENTS, STEP_MOMENT, STEP_TIME
from elc.world.engine.types import (
    EngineConfig,
    MomentKind,
    PoolEvent,
    RunStatus,
    WorldRunRecord,
)
from elc.world.store import SqliteWorldStore
from elc.world.types import WorldEvent, WorldStateFact

__all__ = [
    "CycleTrace",
    "ENGINE_SOURCE",
    "OUTCOME_CHECKPOINT",
    "OUTCOME_LIMIT",
    "OUTCOME_TERMINAL",
    "RunTrace",
    "advance",
]

#: The exit word of the checkpoint outcome (the run stays
#: ``AT_CHECKPOINT`` until something moves it). The engine itself no
#: longer returns it (A2R, DEC-…99: a NOTICE event is a beat, not a
#: pause); the word stays exported because the store's checkpoint face
#: remains a legal mover for any future consumer.
OUTCOME_CHECKPOINT = "CHECKPOINT"

#: The exit word when the call reached the RESPONSE terminal stop (the
#: run is ``TERMINAL``; the world waits for the next reply).
OUTCOME_TERMINAL = "TERMINAL"

#: The exit word 上限终止: the call burned ``max_cycles`` cycles without
#: one ``RESPONSE`` event and failed closed to the terminal stop — the
#: trace says LIMIT, never a fake RESPONSE moment. (A2R, DEC-…99: the
#: burned cycles may well carry NOTICE events — the ceiling is about
#: never reaching a stop, not about an empty chronicle.)
OUTCOME_LIMIT = "LIMIT"

#: The chronicle ``source`` word engine-written events carry (a free
#: word — the source vocabulary is unregistered, the 0024 convention).
ENGINE_SOURCE = "world_engine"


@dataclass(frozen=True)
class CycleTrace:
    """One cycle's deterministic record — trace, not prose.

    ``steps`` names the steps the cycle executed, in order (steps 2–5;
    a pure time-advance cycle runs 2–3 and finds nothing mature).
    ``mature_kinds`` is the mature candidates' kind words in pool order;
    ``selected`` the chosen event's kind word; ``event_id`` the
    chronicle entry the cycle wrote (``<run_id>:<cursor>``); ``actor``
    the correspondent the comms step chose (``None`` = silent); and
    ``moment`` the exit word when the cycle reached step 5.
    """

    cursor: int
    steps: tuple[str, ...]
    days_advanced: int
    mature_kinds: tuple[str, ...]
    selected: str | None
    event_id: str | None
    actor: str | None
    moment: str | None


@dataclass(frozen=True)
class RunTrace:
    """One ``advance`` call's deterministic record.

    ``outcome`` is the call's exit word — :data:`OUTCOME_CHECKPOINT`,
    :data:`OUTCOME_TERMINAL` or :data:`OUTCOME_LIMIT` (上限终止). The
    run's own persisted state is readable through the store's ``get_run``
    — the trace carries the run's identity, not a copy of its row.
    """

    run_id: str
    world_id: str
    seed: int
    cycles: tuple[CycleTrace, ...]
    outcome: str


def _cycle_rng(seed: int, cursor: int) -> random.Random:
    """One cycle's RNG, seeded from the pair ``(seed, cursor)``.

    ``random.Random`` seeds from an int / str / bytes — not from a tuple
    — so the pair folds into one deterministic token. String seeding
    never touches ``hash()``, so the fold carries no
    ``PYTHONHASHSEED`` dependence: the same pair draws the same stream
    in every process, which is what makes the replay pin hold across
    restarts and not merely across calls.
    """

    return random.Random(f"world-run:{seed}:{cursor}")


def _is_mature(event: PoolEvent, facts: tuple[WorldStateFact, ...]) -> bool:
    """Whether one pool event is mature against the projection's CURRENT
    half: every condition's ``(canonical_key, statement)`` pair must
    appear among the live facts, byte-equal (empty conditions = always
    mature)."""

    live = {(fact.canonical_key, fact.statement) for fact in facts}
    return all(
        (condition.canonical_key, condition.statement) in live
        for condition in event.conditions
    )


def _moment_of(
    now: str | Callable[[str], str], kind: str | None
) -> str:
    """The cycle's moment, from the caller's ``now`` (the clock seam).

    A plain string is the call's one moment — the pre-A2 shape, byte for
    byte. A timestamp source (A2, DEC-…88/…90 — the virtual world
    calendar) answers per event: ``kind`` names the event being stamped
    (the source sums the story's spans); ``None`` marks a no-event exit
    (the LIMIT ceiling), which the source answers without advancing
    anything. The engine never computes a date itself."""

    return now(kind or "") if callable(now) else now


def advance(
    store: SqliteWorldStore,
    run: WorldRunRecord,
    pool: tuple[PoolEvent, ...],
    config: EngineConfig,
    now: str | Callable[[str], str],
) -> Result[RunTrace]:
    """Advance one world run by cycles until its stop or its ceiling.

    The loop per cycle — steps 2–5, in the spec's order:

    1. *(step 1, the winch, is the caller's — this call only continues a
       run that exists; pass the run's current row, re-read through
       ``get_run`` after a pause.)*
    2. **Time advance**: ``config.days_per_cycle`` days are recorded in
       the trace — an internal bookkeeping count, not a calendar (the
       world's own days are the story's, DEC-…88/…90: the events' spans
       summed by the orchestrator's timestamp source).
    3. **Event maturity**: the pool events whose conditions all
       CURRENT-match the world's state projection are the candidates, in
       pool order; when there are any, the per-cycle RNG — seeded
       ``(seed, cursor)`` — picks one, and the event lands in the
       chronicle through the store's ``record_event`` (its effects settle
       atomically; the id derives as ``<run_id>:<cursor>``; the
       ``occurred_at`` comes from the caller's ``now`` — a plain string
       for the whole call, or the timestamp source asked once for this
       event's kind — never a hidden clock).
    4. **Communication (v1)**: one further draw from the same per-cycle
       RNG picks at most one actor of the world to write — or silence.
       The decision is recorded in the trace only; no letter is
       generated.
    5. **Moment (the exit)**: the selected event's moment decides — a
       ``NOTICE`` event is a **beat, not a pause** (A2R, DEC-…99: the
       cycle is traced and the loop continues immediately; the run row
       is not moved), a ``RESPONSE`` event terminates the run (the store
       marks it ``TERMINAL`` and the call returns). A pool whose NOTICE
       events stay mature forever repeats them beat by beat until a
       RESPONSE is drawn or the ceiling cuts in — the candidates are
       never thinned by what already happened, so a pool's composition
       is its own pacing.

    A cycle with no mature event is a pure time-advance cycle (steps 2–3
    only; the pool's conditions cannot change mid-call because nothing
    else writes) — and a call that never draws a RESPONSE burns its
    cycles to ``config.max_cycles`` and then fails closed: the run is
    terminalized and the trace's exit word is :data:`OUTCOME_LIMIT`
    (上限终止), never an infinite loop and never a faked moment.

    Refusals: advancing a ``TERMINAL`` run is a ``VALIDATION_FAILED``
    (a finished run does not advance); the store's own refusals — a
    dangling world, a refused event write — pass through unchanged. The
    caller owns the run row's freshness: a stale record re-draws a cycle
    whose chronicle entry already exists, and the store's append-only
    idempotence answers the conflict.
    """

    if run.status == RunStatus.TERMINAL:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"run {run.run_id!r} is TERMINAL; a finished run does"
                    " not advance — the world waits for the next reply"
                ),
            )
        )

    actors = store.actors_of(run.world_id)
    cursor = run.cursor
    cycles: list[CycleTrace] = []

    for _ in range(config.max_cycles):
        # Step 2 — the time advance: days per cycle, recorded, no clock.
        days = config.days_per_cycle
        # Step 3 — event maturity: the CURRENT-matching candidates, in
        # pool order; the per-cycle RNG picks one.
        facts = store.current_facts(run.world_id)
        mature = tuple(
            event for event in pool if _is_mature(event, facts)
        )
        if not mature:
            cycles.append(
                CycleTrace(
                    cursor=cursor,
                    steps=(STEP_TIME, STEP_EVENTS),
                    days_advanced=days,
                    mature_kinds=(),
                    selected=None,
                    event_id=None,
                    actor=None,
                    moment=None,
                )
            )
            cursor += 1
            continue

        rng = _cycle_rng(run.seed, cursor)
        selected = mature[rng.randrange(len(mature))]

        # Step 4 — communication (v1): one further draw from the same
        # RNG; index len(actors) means silence. Only recorded.
        if actors:
            draw = rng.randint(0, len(actors))
            actor = actors[draw].actor_id if draw < len(actors) else None
        else:
            actor = None

        event_id = f"{run.run_id}:{cursor}"
        moment = _moment_of(now, selected.kind)
        written = store.record_event(
            WorldEvent(
                event_id=event_id,
                world_id=run.world_id,
                kind=selected.kind,
                narration=selected.narration,
                effects=selected.effects,
                occurred_at=moment,
                source=ENGINE_SOURCE,
                # C1-a: the chronicle row carries the run it rode
                # (migration 0027's attribution column — the same run
                # in, the same id on every cycle's row).
                run_id=run.run_id,
            )
        )
        if isinstance(written, Err):
            return Err(written.error)

        # Step 5 — the moment: the selected event's exit word.
        # A2R (DEC-…99): a NOTICE event is a **beat, not a pause** — the
        # run keeps going (the next cycle starts immediately). The old
        # behavior (checkpoint on NOTICE, wait for a UI「继续」click)
        # was retired by the user's verdict: the concept is an internal
        # rhythm mechanism with no product meaning when surfaced as a
        # button. The checkpoint state machine stays in the store (any
        # future consumer can still use it); the engine simply does not
        # pause on NOTICE any more. Only a RESPONSE event or the cycle
        # ceiling ends the run.
        if selected.moment == MomentKind.NOTICE:
            cycles.append(
                CycleTrace(
                    cursor=cursor,
                    steps=(STEP_TIME, STEP_EVENTS, STEP_COMMS, STEP_MOMENT),
                    days_advanced=days,
                    mature_kinds=tuple(event.kind for event in mature),
                    selected=selected.kind,
                    event_id=event_id,
                    actor=actor,
                    moment=MomentKind.NOTICE.value,
                )
            )
            # The beat's cursor advances locally (the old code's store
            # side went through ``checkpoint_run``, which is retired
            # here): without it every later cycle in the call would
            # re-derive the same event id and either conflict or
            # idempotently rewrite the chronicle entry.
            cursor += 1
            continue

        terminalized = store.terminalize_run(run.run_id, moment)
        if isinstance(terminalized, Err):
            return Err(terminalized.error)
        cycles.append(
            CycleTrace(
                cursor=cursor,
                steps=(STEP_TIME, STEP_EVENTS, STEP_COMMS, STEP_MOMENT),
                days_advanced=days,
                mature_kinds=tuple(event.kind for event in mature),
                selected=selected.kind,
                event_id=event_id,
                actor=actor,
                moment=MomentKind.RESPONSE.value,
            )
        )
        return Ok(
            RunTrace(
                run_id=run.run_id,
                world_id=run.world_id,
                seed=run.seed,
                cycles=tuple(cycles),
                outcome=OUTCOME_TERMINAL,
            )
        )

    # The ceiling: max_cycles cycles without one RESPONSE event — fail
    # closed to the terminal stop, the trace saying LIMIT (上限终止),
    # the run never looping forever. The burned cycles may carry NOTICE
    # beats (an always-mature pool keeps writing them); the ceiling is
    # about never reaching a stop, not an empty chronicle.
    exhausted = store.terminalize_run(run.run_id, _moment_of(now, None))
    if isinstance(exhausted, Err):
        return Err(exhausted.error)
    return Ok(
        RunTrace(
            run_id=run.run_id,
            world_id=run.world_id,
            seed=run.seed,
            cycles=tuple(cycles),
            outcome=OUTCOME_LIMIT,
        )
    )
