"""The world's communication orchestration (W-1-3) — the winch and the
light action, as one callable.

WR-2 (DEC-OPI-5fc42174…49), the paradigm flip: the **production** world
step is now :func:`run_generated_step` — the world's beats are model-
generated novel prose (the narrator's face,
:mod:`elc.world.narrator`), one letter in, one or two beats out. The
fixed-pool engine step below (:func:`run_step`) is **retired out of the
production path**: it stays the deterministic engine's orchestration
face for the engine-direct callers (the W-1-2/W-1-3 test families run
on it), and nothing in ``src/`` calls it any more.

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

What is deliberately absent from :func:`run_step`: no model face, no
provider, no narration generation (the pool's prose arrives
pre-authored, AD-2), no waiting, no rendering, and no DIRECTION word
(W-2-2 opens it). The world's own time is the virtual calendar's (A2,
DEC-…88/…90): with a package the step stamps its events on
``calendar_start`` plus the story's spans — the caller's ``now`` keeps
only the run row's bookkeeping. :func:`run_generated_step` carries the
model face instead: the provider is the caller's injection, the beats
are the narrator's, and an unconfigured provider is the world's quiet —
never a fallback to the retired pool.

Layering note: this module imports the engine's execution face through
its direct module path (``elc.world.engine.engine``) — the same edge
discipline :mod:`elc.world.engine` documents — and the store; nothing
imports back.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from elc.persona.openai_provider import REASON_NOT_CONFIGURED
from elc.persona.provider import PersonaProvider
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.engine.engine import RunTrace, advance
from elc.world.engine.types import EngineConfig, PoolEvent, RunStatus
from elc.world.narrator import (
    NARRATOR_SOURCE,
    RECENT_CHRONICLE_LIMIT,
    WorldNarrator,
)
from elc.world.package import WorldPackage, story_days_of, story_elapsed_days_of
from elc.world.store import SqliteWorldStore, WorldRevealItem
from elc.world.types import WorldEvent

__all__ = [
    "TRIGGER_CONTINUE",
    "TRIGGER_LETTER",
    "run_generated_step",
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


def run_generated_step(
    store: SqliteWorldStore,
    world_id: str,
    package: WorldPackage,
    provider: PersonaProvider | None,
    letter_text: str,
    trigger_turn_id: str | None,
    now: str,
    *,
    ui_language: str = "zh",
) -> Result[tuple[WorldEvent, ...]]:
    """The production world step (WR-2, DEC-OPI-5fc42174…49): one
    letter in, the narrator's beats out, the chronicle and the reveal
    queue written — and **no pool sampling anywhere** (the fixed pool
    is retired out of the production path; a step that cannot narrate
    goes quiet, never back to the engine).

    The order: the narrator first (compose, one blocking provider call,
    strict parse), the winch second — a letter that narrates nothing
    winds no run row (an empty run is litter, not history). The winch
    arm is :func:`run_step`'s letter arm: the latest run absent or
    ``TERMINAL`` winds a fresh one (seed = the world's run count, the
    id derived by :func:`_run_id_for`, the triggering turn riding the
    row when the caller knows it), a run paused at its checkpoint is
    resumed (the letter is the light action's superset). The generated
    step **never terminalizes its run** — the row stays the world's
    anchor at its checkpoint, every later letter resumes it, and that
    is what makes a replayed call land as a no-op: the beats' event ids
    derive from the anchor run plus the triggering turn
    (``<run_id>:<trigger_turn_id>:<index>`` — the turn is the step's
    identity), and the step pre-reads the chronicle's own ids and
    writes **only the beats that are not already durable** — the
    calendar base and the spans are pure functions of the durable
    chronicle, so a replay recomputes the same stamps, skips the whole
    batch and enqueues nothing (the events and their reveals stay
    exactly as the first call left them). A caller without a turn id
    derives count-based ids instead and carries **no** replay
    protection (the docstring says so rather than pretending).

    The beats land verbatim (untrusted-as-is): the narrator's ``kind``
    and ``narration`` are the chronicle row's own words, ``effects`` is
    empty (the generated story settles no state claim — the projection
    only moves when a future cut says so), ``source`` is
    :data:`~elc.world.narrator.NARRATOR_SOURCE`. The timestamps are the
    virtual calendar's, and the base is the story's **furthest stamped
    day** (:func:`elc.world.package.story_elapsed_days_of` — WR-2's
    disposition): each beat advances the running total by its own
    generated span and stamps at the end of it (落笔在跨度之末), so a
    later letter's beats land **after** every earlier one — the
    calendar is monotonic across letters, and the world's today
    (:func:`elc.world.package.world_date_of`) follows the same furthest
    stamp (the pool-keyed sum froze at day zero once the pool left the
    production path; that defect was the disposition's fix). Every
    reveal item inherits its own event's moment.

    The quiet arms, in order: no provider, or the provider answering
    ``not-configured``, returns ``Ok(())`` — the world's honest silence
    (nothing to say until the settings page fills the pair), never a
    fallback to the retired pool. Any other narrator refusal or fault
    is an ``Err`` passthrough (the caller's fail-soft log is the
    observer); a store refusal on the way down is an ``Err`` too — the
    beats already landed stay (the chronicle is append-only and every
    write was atomic; there is no tearing claim across beats, and the
    pre-read makes a replay of the same letter write nothing).

    ``ui_language`` rides to the narrator (the narration language law,
    W-L's two words). ``now`` is the caller's wall moment for the run
    row's bookkeeping stamps — it never reaches a world event.
    """

    if provider is None:
        # The honest quiet: no provider, no narration, no fallback to
        # the retired pool. The world says nothing this letter.
        return Ok(())
    chronicle = store.chronicle_of(world_id)
    if isinstance(chronicle, Err):
        return Err(chronicle.error)
    narrator = WorldNarrator(provider)
    generated = narrator.generate(
        package=package,
        lore_facts=tuple(
            (fact.canonical_key, fact.statement)
            for fact in store.current_facts(world_id)
        ),
        recent_narrations=tuple(
            event.narration
            for event in chronicle.value[-RECENT_CHRONICLE_LIMIT:]
        ),
        letter_text=letter_text,
        ui_language=ui_language,
    )
    if isinstance(generated, Err):
        if generated.error.message == REASON_NOT_CONFIGURED:
            # The bare web start's honest silence: the narrator's
            # provider has no coordinates yet — the world waits, the
            # letter's reader does not.
            return Ok(())
        return Err(generated.error)
    beats = generated.value
    if not beats:
        # The strict narrator never produces an empty batch (that is a
        # refusal upstream); this arm is the contract's own quiet.
        return Ok(())

    runs = store.list_runs(world_id)
    latest = runs[-1] if runs else None
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
        run = latest

    if trigger_turn_id is not None:
        # The turn is the step's identity: the same letter replayed
        # re-derives the same ids and lands as the store's no-op.
        id_prefix = f"{run.run_id}:{trigger_turn_id}:"
        first_ordinal = 0
    else:
        # No turn to name: the durable count derives the ids —
        # deterministic, collision-free, and honestly without replay
        # protection (the docstring says so).
        id_prefix = f"{run.run_id}:g"
        first_ordinal = sum(
            1
            for event in chronicle.value
            if str(event.event_id).startswith(f"{run.run_id}:")
        )
    existing_event_ids = {
        str(event.event_id) for event in chronicle.value
    }
    start = date.fromisoformat(package.calendar_start)
    # WR-2's disposition base: the story's furthest stamped day — a
    # later letter stamps after every earlier one (monotonic by
    # construction; the pool-keyed sum froze at day zero).
    total = story_elapsed_days_of(package, store, world_id)
    written: list[WorldEvent] = []
    for index, beat in enumerate(beats):
        # 落笔在跨度之末: the beat advances the story by its own span,
        # then stamps at its end — the calendar accumulates within the
        # step exactly as it does across steps (A2R DEC-…99's law, the
        # generated span in the pool's old seat).
        total += beat.days
        event_id = f"{id_prefix}{first_ordinal + index}"
        if event_id in existing_event_ids:
            # The replayed letter's own beats: the durable rows stand,
            # this call writes nothing of them (the step's replay
            # protection — the derived ids plus this pre-read — keeps
            # the whole step a no-op, reveals included).
            continue
        recorded = store.record_event(
            WorldEvent(
                event_id=event_id,
                world_id=world_id,
                kind=beat.kind,
                narration=beat.narration,
                effects=(),
                occurred_at=(start + timedelta(days=total)).isoformat(),
                source=NARRATOR_SOURCE,
            )
        )
        if isinstance(recorded, Err):
            return Err(recorded.error)
        written.append(recorded.value)
    enqueued = store.enqueue_reveals(
        tuple(
            WorldRevealItem(
                item_id=f"{event.event_id}:reveal",
                world_id=world_id,
                source_event_id=event.event_id,
                actor_id=None,
                status="PENDING",
                revealed_at=None,
                created_at=event.occurred_at,
            )
            for event in written
        )
    )
    if isinstance(enqueued, Err):
        return Err(enqueued.error)
    return Ok(tuple(written))


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
