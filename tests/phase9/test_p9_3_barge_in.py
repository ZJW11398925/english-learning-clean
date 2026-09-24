"""P9-3 ② — barge-in on the real chain.

RA §17.1 and §18 as behaviour, over the shipped faces and nothing else: a
file-backed app.db, a real runtime epoch, the real conversation store's own
CP0/interrupt writes, the real generation store's §14 action machine, the §22
record adapter and the coordinator with its two P9-3 injections
(``InterruptAwareTransport`` and the PreDeliveryGuard's facts).

Four things only a real chain can show, and what each is here for:

- **the entry works while the old worker still holds the guard.** A worker
  thread holds the conversation's keyed mutex while the interrupting request is
  made; the entry must answer without waiting for it (§17.1's whole point), and
  the same mutex must still refuse a *second* turn until the guard is released
  (R-INV-011: one user-visible runtime per conversation);
- **the stream stops before the next release, not after it.** The source writes
  its own interrupt row mid-run — the in-process shape of the user typing while
  the answer was being sent — and the durable prefix is then exactly the chunks
  the client received before the barge-in;
- **the only actor allowed to cancel is the guard holder** (§17.1 rule 3). The
  reconciler runs inside the guard, before anything is generated, and the write
  log proves the old turn is terminal before the new turn's first delivery row
  and before its canonicalization (§17.1 rule 5);
- **a hard invalidation is not a delivery.** A guard that answers
  ``INVALIDATE_ACTION`` writes no transcript row at all, and the §22 row freezes
  ``CANCELLED`` with an empty prefix — undelivered provider output never enters
  the transcript (DOMAIN_MODEL §3).

The world, the scripted source and the §22 second-connection read are
``tests.phase9.test_p9_2_stream_turn``'s, imported rather than copied (that
module's ``stream_world`` docstring says a sibling suite may ask for it by
name).
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import TurnOutcome
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.persona.runtime import action_intent_for_turn
from elc.persona.types import ProviderOutput
from elc.platform.db import connection, epoch
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ActionId,
    DecisionCycleId,
    InputId,
    Ok,
    Result,
    TurnId,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.delivery_records import (
    PreDeliveryGuardResult,
    ServerDeliveryRecord,
)
from elc.runtime.guarded_stream import StreamStep, StreamStepKind, StreamTransport
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    GenerationActionStatus,
    GenerationActionType,
    InterruptRequest,
    TurnStatus,
)
from tests.conftest import AssemblyGenerationStore
from tests.phase8.conftest import CONV
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    StreamWorld,
    action_of,
    begin_turn_ok,
    command,
    count,
    persona_runtime,
    pieces,
    second_connection_row,
    slice_of,
    stream_world,
)

#: The instant every hand-built §22 row carries, so an assertion about a row's
#: ``started_at`` is an equality with a literal the test owns.
STARTED_AT = "2026-09-24T00:00:00+00:00"


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


# -- the write log: ordering across two faces --------------------------------


@dataclass
class WriteLog:
    """Durable writes, in the order the two faces made them.

    One list, because the handoff order (§17.1 rule 5) is a statement *across*
    faces: the old turn's terminalization is the conversation store's and the
    new turn's first delivery row is the record face's, so a log per face could
    not witness it. Nothing here changes a write — every entry is appended
    after the inner face answered ``Ok``.
    """

    entries: list[tuple[str, ...]] = field(default_factory=list)

    def index_of(self, entry: tuple[str, ...]) -> int:
        assert entry in self.entries, f"{entry} not in {self.entries}"
        return self.entries.index(entry)

    def states_of(self, action_id: str) -> list[str]:
        return [
            entry[2]
            for entry in self.entries
            if entry[0] == "record_server_delivery" and entry[1] == action_id
        ]


class LoggingCommands:
    """The conversation command face with the three writes the log needs."""

    def __init__(self, inner, log: WriteLog) -> None:
        self._inner = inner
        self._log = log

    def commit_user_turn(self, command_):
        result = self._inner.commit_user_turn(command_)
        if isinstance(result, Ok):
            self._log.entries.append(
                ("commit_user_turn", str(result.value.turn_id))
            )
        return result

    def terminalize_turn(self, turn_id: TurnId, outcome: TurnOutcome):
        result = self._inner.terminalize_turn(turn_id, outcome)
        if isinstance(result, Ok):
            self._log.entries.append(
                ("terminalize_turn", str(turn_id), outcome.value)
            )
        return result

    def canonicalize_assistant_turn(self, turn):
        result = self._inner.canonicalize_assistant_turn(turn)
        if isinstance(result, Ok):
            self._log.entries.append(
                ("canonicalize_assistant_turn", str(turn.turn_id))
            )
        return result

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


class LoggingRecords:
    """The §22/§21.1 face with the same log."""

    def __init__(self, inner, log: WriteLog) -> None:
        self._inner = inner
        self._log = log

    def record_server_delivery(self, record: ServerDeliveryRecord):
        result = self._inner.record_server_delivery(record)
        if isinstance(result, Ok):
            self._log.entries.append(
                ("record_server_delivery", str(record.action_id), record.state)
            )
        return result

    def append_pre_delivery_guard_result(self, result: PreDeliveryGuardResult):
        written = self._inner.append_pre_delivery_guard_result(result)
        if isinstance(written, Ok):
            self._log.entries.append(
                (
                    "append_pre_delivery_guard_result",
                    str(result.action_id),
                    result.decision,
                )
            )
        return written

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


# -- the world the tests assemble ---------------------------------------------


def fresh_lease(world: StreamWorld) -> ConversationCoordinatorLease:
    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    return lease


@dataclass
class BoundWorld:
    """A second set of stores over the same file, in the calling thread.

    sqlite3 connections are thread-bound, so a test that runs a coordinator on
    another thread needs its own connection: this is the same world (same file,
    same epoch number, same stores), bound to whichever thread asks. The main
    thread keeps the fixture's stores for its own reads.
    """

    db: sqlite3.Connection
    store: SqliteConversationStore
    generation: AssemblyGenerationStore
    deliveries: SqliteDeliveryRecordStore


def bind(world: StreamWorld) -> BoundWorld:
    db = connection.connect(world.path)
    fence = RuntimeEpochFence(current=world.fence.current)
    return BoundWorld(
        db=db,
        store=SqliteConversationStore(db, fence),
        generation=AssemblyGenerationStore(db, fence),
        deliveries=SqliteDeliveryRecordStore(db, fence),
    )


def persona_runtime_over(generation: object) -> PersonaRuntime:
    """The scripted persona runtime over one generation store (the epoch-bound
    assembly needs its own, or its writes are fenced)."""

    return PersonaRuntime(
        actions=generation,  # type: ignore[arg-type]
        provider=ScriptedPersonaProvider(script=(ProviderOutput(text=REPLY),)),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )


def coordinator_over(
    bound: BoundWorld,
    *,
    lease: ConversationCoordinatorLease,
    transport: Callable[..., StreamTransport] | None = None,
) -> ConversationCoordinator:
    """One coordinator over a thread-bound world (the same lease object is
    passed in, so "the guard" is provably one guard)."""

    return ConversationCoordinator(
        lease=lease,
        conversation_commands=bound.store,
        conversation_queries=bound.store,
        persona=persona_runtime_over(bound.generation),
        generation_actions=bound.generation,
        decision_cycles=bound.generation.decision_cycles,
        delivery_records=bound.deliveries,
        stream_transport=transport,
    )


def coordinator_for(
    world: StreamWorld,
    *,
    lease: ConversationCoordinatorLease | None = None,
    commands: object | None = None,
    records: object | None = None,
    transport: Callable[..., StreamTransport] | None = None,
    teaching: object | None = None,
    constraint_views: object | None = None,
) -> ConversationCoordinator:
    """One coordinator over the fixture's own stores (the P9-2 assembly).

    ``commands``/``records`` exist so a test can hand over a logging proxy —
    the port is what the coordinator writes through, so a proxy is the only
    place the write order is observable. ``teaching``/``constraint_views`` are
    the P9-3 guard's two optional authorities, passed through so the carrier
    arms can be driven.
    """

    return ConversationCoordinator(
        lease=lease if lease is not None else fresh_lease(world),
        conversation_commands=(
            world.store if commands is None else commands  # type: ignore[arg-type]
        ),
        conversation_queries=world.store,
        persona=persona_runtime(world),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=(
            world.deliveries if records is None else records  # type: ignore[arg-type]
        ),
        stream_transport=transport,
        teaching=teaching,  # type: ignore[arg-type]
        constraint_views=constraint_views,  # type: ignore[arg-type]
    )


def second_connection_rows(
    world: StreamWorld, sql: str, params: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    """Rows as a **second** connection reads them (never the writer)."""

    second = connection.connect(world.path)
    try:
        return [tuple(row) for row in second.execute(sql, params).fetchall()]
    finally:
        second.close()


def interrupt_row(world: StreamWorld, input_id: str) -> tuple[object, ...] | None:
    rows = second_connection_rows(
        world,
        "SELECT input_id, conversation_id, active_turn_id, active_action_id,"
        " reason, created_at FROM interrupt_request WHERE input_id = ?",
        (input_id,),
    )
    return None if not rows else rows[0]


def envelope_exists(world: StreamWorld, input_id: str) -> bool:
    rows = second_connection_rows(
        world,
        "SELECT 1 FROM input_envelope WHERE input_id = ?",
        (input_id,),
    )
    return bool(rows)


def pending_for_action(world: StreamWorld, action_id: ActionId) -> tuple[object, ...]:
    result = world.store.list_pending_interrupts_for_action(action_id)
    assert isinstance(result, Ok), result
    return result.value


def turn_status(world: StreamWorld, turn_id: str) -> str:
    rows = second_connection_rows(
        world,
        "SELECT status FROM turn_record WHERE turn_id = ?",
        (turn_id,),
    )
    assert rows, "no turn_record row"
    return str(rows[0][0])


def turn_outcome(world: StreamWorld, turn_id: str) -> str | None:
    rows = second_connection_rows(
        world,
        "SELECT turn_outcome FROM turn_record WHERE turn_id = ?",
        (turn_id,),
    )
    assert rows, "no turn_record row"
    return None if rows[0][0] is None else str(rows[0][0])


# -- the source that interrupts itself ----------------------------------------


class InterruptingSource:
    """A source that writes the barge-in itself, mid-stream.

    The write goes through the conversation store's own durable face — the same
    row the entry writes — and it happens inside ``take``, so the wrapper asks
    its "is this still wanted?" question on the *next* step and the driver
    stops before the following release. ``after_chunks`` counts served chunks:
    ``0`` writes before the first one is handed over, ``n`` once ``n`` of them
    were.
    """

    def __init__(
        self,
        *,
        world: StreamWorld,
        steps: tuple[StreamStep, ...],
        action_id: ActionId,
        after_chunks: int,
        reason: str,
    ) -> None:
        self._world = world
        self._steps = steps
        self._action_id = action_id
        self._after_chunks = after_chunks
        self._reason = reason
        self._index = 0
        self._served = 0
        self.emitted: list[str] = []
        self.requested = False

    def take(self) -> StreamStep:
        if self._index >= len(self._steps):
            return StreamStep.end()
        step = self._steps[self._index]
        self._index += 1
        if step.kind is StreamStepKind.CHUNK:
            self._maybe_request()  # after_chunks == 0: before the first chunk
            self._served += 1
            self._maybe_request()  # after_chunks == n: once n chunks were served
        return step

    def _maybe_request(self) -> None:
        """Write the request the moment the served count reaches the target."""

        if self.requested or self._served != self._after_chunks:
            return
        write_interrupt(
            self._world,
            action_id=self._action_id,
            reason=self._reason,
        )
        self.requested = True

    def emit(self, text: str) -> Result[None]:
        self.emitted.append(text)
        return Ok(None)


def write_interrupt(
    world: StreamWorld, *, action_id: ActionId, reason: str
) -> None:
    """The durable request one of these sources writes (a real entry write)."""

    written = world.store.request_interrupt(
        InterruptRequest(
            input_id=InputId(f"in-{action_id}"),
            conversation_id=str(CONV),
            active_turn_id=None,
            active_action_id=action_id,
            reason=reason,
        )
    )
    assert isinstance(written, Ok), written


class InterruptingFactory:
    """Builds an :class:`InterruptingSource` for whatever action it is asked
    about (the factory receives the action id, which is what the request has to
    name).

    ``after_chunks=None`` writes the request **at construction time** — the
    window between the guard's check and the first release — which is the only
    way a barge-in can stop a stream before it released anything (an earlier
    request is the guard's to catch, a later one leaves the first chunk
    already sent).
    """

    def __init__(
        self,
        *,
        world: StreamWorld,
        chunks: list[str],
        after_chunks: int | None,
        reason: str = "the user typed something else",
    ) -> None:
        self._world = world
        self._chunks = chunks
        self._after_chunks = after_chunks
        self._reason = reason
        self.source: InterruptingSource | None = None
        self.requested = False

    def __call__(
        self, *, validated_text: str, action_id: ActionId
    ) -> StreamTransport:
        if self._after_chunks is None:
            write_interrupt(self._world, action_id=action_id, reason=self._reason)
            self.requested = True
            self.source = InterruptingSource(
                world=self._world,
                steps=tuple(StreamStep.chunk(piece) for piece in self._chunks),
                action_id=action_id,
                after_chunks=len(self._chunks),  # never reached again
                reason=self._reason,
            )
            return self.source
        self.source = InterruptingSource(
            world=self._world,
            steps=tuple(StreamStep.chunk(piece) for piece in self._chunks),
            action_id=action_id,
            after_chunks=self._after_chunks,
            reason=self._reason,
        )
        return self.source


# -- ① the entry: durable, and outside the guard ------------------------------


def test_the_interrupt_entry_answers_while_the_old_worker_holds_the_guard(
    world: StreamWorld,
) -> None:
    """§17.1 rules 1-2 as the thing they are for: the request does not wait.

    This thread holds the conversation's guard (the coordinator's own lease —
    the same object the entry could have taken) and the entry runs on another
    thread over a connection of its own; the assertion is made while the guard
    is **still** held. An entry that took the mutex would block on this
    thread's key: the worker would still be alive when the join times out, so
    the failure is "the entry waited for the guard" rather than a hang.
    """

    lease = fresh_lease(world)
    interrupt = InterruptRequest(
        input_id=InputId("in-p9-3-while-held"),
        conversation_id=str(CONV),
        active_turn_id=TurnId("turn-p9-3-old"),
        active_action_id=ActionId("ga-p9-3-old"),
        reason="the user typed something else",
    )
    answers: list[Result[InputId]] = []
    errors: list[BaseException] = []

    def entry() -> None:
        bound = bind(world)
        try:
            coordinator = coordinator_over(bound, lease=lease)
            answers.append(coordinator.request_interrupt(interrupt))
        except BaseException as exc:  # noqa: BLE001 — reported, not hidden
            errors.append(exc)
        finally:
            bound.db.close()

    asker = threading.Thread(target=entry, name="p9-3-entry")
    with lease.hold(CONV):
        asker.start()
        asker.join(timeout=15)
        answered_while_held = not asker.is_alive() and bool(answers)
        guard_still_held = lease.is_held(CONV)

    assert guard_still_held
    assert answered_while_held, "the interrupt entry waited for the guard"
    assert errors == []
    assert isinstance(answers[0], Ok), answers[0]
    assert answers[0].value == interrupt.input_id
    # and the two rows are durable by the time it answered
    assert interrupt_row(world, "in-p9-3-while-held") is not None
    assert envelope_exists(world, "in-p9-3-while-held")


def test_the_entry_writes_both_rows_and_a_second_connection_sees_them(
    world: StreamWorld,
) -> None:
    """§17.1 rule 1's queue entry plus rule 2's request: two rows, in the order
    the entry's docstring declares, both durable the moment the call returns —
    read back here through a connection that is not the writer."""

    coordinator = coordinator_for(world)
    interrupt = InterruptRequest(
        input_id=InputId("in-p9-3-rows"),
        conversation_id=str(CONV),
        active_turn_id=None,
        active_action_id=ActionId("ga-p9-3-rows"),
        reason="stop this answer please",
    )
    result = coordinator.request_interrupt(interrupt)
    assert isinstance(result, Ok), result
    assert result.value == interrupt.input_id

    row = interrupt_row(world, "in-p9-3-rows")
    assert row is not None
    assert (row[0], row[1], row[2], row[3]) == (
        "in-p9-3-rows",
        str(CONV),
        None,
        "ga-p9-3-rows",
    )
    assert row[4] == "stop this answer please"
    assert str(row[5]) != ""
    assert envelope_exists(world, "in-p9-3-rows")


def test_the_queue_entry_carries_the_reason_and_the_v1_channel(
    world: StreamWorld,
) -> None:
    """The two readings the entry declares, pinned: the interrupting input's
    payload is the request's own reason verbatim and its channel is V1's TEXT
    (the `InterruptRequest` shape carries neither field)."""

    coordinator = coordinator_for(world)
    result = coordinator.request_interrupt(
        InterruptRequest(
            input_id=InputId("in-p9-3-payload"),
            conversation_id=str(CONV),
            active_turn_id=None,
            active_action_id=None,
            reason="not this, thanks",
        )
    )
    assert isinstance(result, Ok), result
    rows = second_connection_rows(
        world,
        "SELECT raw_payload, interaction_channel, client_message_id"
        " FROM input_envelope WHERE input_id = ?",
        ("in-p9-3-payload",),
    )
    assert rows == [("not this, thanks", "TEXT", None)]


def test_a_replayed_interrupt_returns_the_same_identity_and_writes_nothing(
    world: StreamWorld,
) -> None:
    """R-INV-012 for the new entry: the request's identity is its input id, so
    a second call is a replay — same answer, and the two tables keep exactly
    the rows the first call wrote."""

    coordinator = coordinator_for(world)
    interrupt = InterruptRequest(
        input_id=InputId("in-p9-3-replay"),
        conversation_id=str(CONV),
        active_turn_id=None,
        active_action_id=None,
        reason="again",
    )
    first = coordinator.request_interrupt(interrupt)
    assert isinstance(first, Ok), first
    before = (
        count(world.db, "interrupt_request"),
        count(world.db, "input_envelope"),
    )
    second = coordinator.request_interrupt(interrupt)
    assert isinstance(second, Ok), second
    assert second.value == first.value
    assert (
        count(world.db, "interrupt_request"),
        count(world.db, "input_envelope"),
    ) == before


def test_a_turn_still_waits_for_the_guard_while_a_request_does_not(
    world: StreamWorld,
) -> None:
    """R-INV-011's other half: the *turn* path is the serialized one. This
    thread holds the guard, a `begin_turn` on another thread is still waiting,
    no assistant row exists while it waits, and only after the release does the
    turn finish — which is what makes §17.1's "cancel from outside, hand off
    inside" consistent rather than a race."""

    lease = fresh_lease(world)
    outcomes: list[Result[object]] = []
    errors: list[BaseException] = []

    def new_turn() -> None:
        bound = bind(world)
        try:
            coordinator = coordinator_over(bound, lease=lease)
            outcomes.append(coordinator.begin_turn(command("cmid-p9-3-blocked")))
        except BaseException as exc:  # noqa: BLE001 — reported, not hidden
            errors.append(exc)
        finally:
            bound.db.close()

    turn = threading.Thread(target=new_turn, name="p9-3-new-turn")
    with lease.hold(CONV):
        turn.start()
        turn.join(timeout=1.0)
        blocked = turn.is_alive()
        no_rows_while_blocked = count(world.db, "assistant_turn") == 0
        assert lease.is_held(CONV) is True

    turn.join(timeout=20)
    assert blocked, "the turn entered the guard while it was held"
    assert no_rows_while_blocked
    assert not turn.is_alive()
    assert errors == []
    assert isinstance(outcomes[0], Ok), outcomes[0]
    assert count(world.db, "assistant_turn") == 1


# -- ② the stream that stops ---------------------------------------------------


@pytest.mark.parametrize("kept_chunks", [1, 2])
def test_a_barge_in_mid_stream_stops_it_and_keeps_the_durable_prefix(
    world: StreamWorld, kept_chunks: int
) -> None:
    """§18's sequence on the real path: the interrupt lands while the stream is
    running, the run stops before the next release, and every durable word is
    §1-C②'s — the §22 row freezes ``CANCELLED`` with its prefix kept, the
    transcript is that prefix verbatim as ``SENT_PARTIAL``, and the turn is
    ``CANCELLED_BY_USER``. Two cut points, so "the prefix" cannot be a
    coincidence of one chunk."""

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(
        world=world, chunks=chunks, after_chunks=kept_chunks
    )
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-3-midstream"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)
    kept = "".join(chunks[:kept_chunks])

    assert factory.source is not None
    assert factory.source.requested, "the source never wrote its interrupt"

    state, prefix, sequence, started_at, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("CANCELLED", kept, kept_chunks)
    assert terminal_at is not None
    assert started_at != ""

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == prefix == kept
    assert canonical.assistant_turn.delivery_state.value == "SENT_PARTIAL"
    assert canonical.assistant_turn.delivery_certainty == "SERVER_SENT_UNCONFIRMED"
    assert canonical.outcome is TurnOutcome.CANCELLED_BY_USER

    assert completion.outcome == TurnOutcome.CANCELLED_BY_USER.value
    assert completion.delivery_state == "CANCELLED"
    assert completion.reply_text == kept
    assert completion.failure_reason is None  # a barge-in is not a failure
    assert completion.delivery_failure_reason is not None
    assert "interrupt" in completion.delivery_failure_reason
    assert action_of(world, turn_id).startswith("ga-")


def test_the_interrupted_action_is_terminal_and_its_request_is_answered(
    world: StreamWorld,
) -> None:
    """§17.1 rule 4: once the old delivery is cancelled the request is
    *answered* — the action is TERMINAL and the action-keyed read comes back
    empty — while the row itself stays exactly where it was (§17.1's audit
    trail; nothing deletes an interrupt)."""

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=1)
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-3-answered"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    assert (
        world.generation.get_action(action_id).value.status  # type: ignore[union-attr]
        is GenerationActionStatus.TERMINAL
    )
    assert pending_for_action(world, action_id) == ()
    assert interrupt_row(world, f"in-{action_id}") is not None
    assert count(world.db, "interrupt_request") == 1


def test_the_guard_row_of_an_interrupted_delivery_is_valid(
    world: StreamWorld,
) -> None:
    """The honest contrast: the guard ran *before* the first release, when
    nothing had been cancelled yet, and it says so (``VALID``). The
    cancellation is the §22 row's and the turn's word, not the guard's — a
    guard verdict is a point-in-time gate (§15), not a subscription."""

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=1)
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-3-valid"
    )
    action_id = action_of(world, str(completion.turn_id))

    rows = world.deliveries.list_pre_delivery_guard_results(action_id)
    assert isinstance(rows, Ok), rows
    assert len(rows.value) == 1
    assert rows.value[0].decision == "VALID"
    assert rows.value[0].reason_codes == ()


def test_an_interrupt_that_lands_before_the_first_chunk_writes_no_transcript_row(
    world: StreamWorld,
) -> None:
    """§1-C②'s empty arm: a barge-in that lands between the guard's check and
    the first release stops the stream with nothing sent — the row is still
    ``CANCELLED`` (terminal instant set, empty prefix, sequence zero), and it
    writes **no** assistant row: undelivered provider output never enters the
    transcript (DOMAIN_MODEL §3). The guard, which ran a moment earlier, says
    ``VALID`` — the honest record of a check that was true when it ran."""

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=None)
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-3-early"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    assert factory.requested
    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("CANCELLED", "", 0)
    assert terminal_at is not None
    assert slice_of(world, turn_id).assistant_turn is None
    assert turn_status(world, turn_id) == TurnStatus.CANCELLED_BY_USER.value
    assert turn_outcome(world, turn_id) == TurnOutcome.CANCELLED_BY_USER.value
    assert completion.assistant_turn_id is None
    assert completion.reply_text is None
    guards = world.deliveries.list_pre_delivery_guard_results(action_id)
    assert isinstance(guards, Ok), guards
    assert [row.decision for row in guards.value] == ["VALID"]


# -- ③ the guard invalidation arms --------------------------------------------


def drive_to_delivering(world: StreamWorld, action_id: ActionId) -> None:
    path = (
        (GenerationActionStatus.PREPARED, GenerationActionStatus.REQUESTED),
        (GenerationActionStatus.REQUESTED, GenerationActionStatus.GENERATING),
        (GenerationActionStatus.GENERATING, GenerationActionStatus.VALIDATING),
        (
            GenerationActionStatus.VALIDATING,
            GenerationActionStatus.READY_TO_DELIVER,
        ),
        (
            GenerationActionStatus.READY_TO_DELIVER,
            GenerationActionStatus.DELIVERING,
        ),
    )
    for expected, new in path:
        stepped = world.generation.transition_action(action_id, expected, new)
        assert isinstance(stepped, Ok), stepped


def open_turn_with_action(
    world: StreamWorld, client_message_id: str
) -> tuple[TurnId, ActionId]:
    """Commit one turn, record its cycle and pre-create its action — the shape
    a crash leaves behind (a nonterminal turn whose action never finished).

    The cycle id is the coordinator's own deterministic spelling
    (``dcy-<turn_id>``) and the action names it, so the lineage leg the
    coordinator's re-entry re-reads is the same one this helper declared.
    """

    cp0 = world.store.commit_user_turn(command(client_message_id))
    assert isinstance(cp0, Ok), cp0
    turn_id = cp0.value.turn_id
    turn = world.store.get_turn_record(turn_id)
    assert isinstance(turn, Ok) and turn.value is not None
    cycle_id = DecisionCycleId(f"dcy-{turn_id}")
    cycle = world.generation.decision_cycles.record_decision_cycle(
        decision_cycle_id=cycle_id,
        turn_id=turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=turn.value.state_version,
    )
    assert isinstance(cycle, Ok), cycle
    intent = action_intent_for_turn(
        turn_id=turn_id,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-normal-persona-reply",
        decision_cycle_id=str(cycle_id),
    )
    created = world.generation.create_action(intent)
    assert isinstance(created, Ok), created
    return turn_id, created.value


def test_the_guard_invalidates_a_delivery_whose_action_is_still_interrupted(
    world: StreamWorld,
) -> None:
    """§15's ``action cancelled`` carrier, at the guard, on a real chain.

    The shape is the crash-recovery barge-in: epoch 1 left a nonterminal turn
    and its action behind, the user's interrupt named that action, and epoch 2
    adopts the work. The reconciler cannot cancel it (the row belongs to the
    old epoch — the fence is the honest answer), so the delivery runs and §15's
    check is what stops it: ``INVALIDATE_ACTION``, no transcript row, the row
    frozen ``CANCELLED``, and §1-C③'s ``CANCELLED_BY_USER`` because the
    invalidating condition is a cancellation.
    """

    turn_id, action_id = open_turn_with_action(world, "cmid-p9-3-guard")
    interrupt = InterruptRequest(
        input_id=InputId("in-p9-3-guard"),
        conversation_id=str(CONV),
        active_turn_id=turn_id,
        active_action_id=action_id,
        reason="cancel this one",
    )

    # epoch 2: a new runtime opens over the same file, as a restart does.
    fence2 = epoch.open_runtime_epoch(world.db)
    lease2 = ConversationCoordinatorLease()
    lease2.adopt_epoch(fence2)
    store2 = SqliteConversationStore(world.db, fence2)
    generation2 = AssemblyGenerationStore(world.db, fence2)
    coordinator2 = ConversationCoordinator(
        lease=lease2,
        conversation_commands=store2,
        conversation_queries=store2,
        persona=persona_runtime_over(generation2),
        generation_actions=generation2,
        decision_cycles=generation2.decision_cycles,
        delivery_records=SqliteDeliveryRecordStore(world.db, fence2),
    )
    assert isinstance(coordinator2.request_interrupt(interrupt), Ok)

    completion = begin_turn_ok(coordinator2, "cmid-p9-3-guard")

    rows = second_connection_rows(
        world,
        "SELECT decision, reason_codes FROM pre_delivery_guard_result"
        " WHERE action_id = ?",
        (str(action_id),),
    )
    assert len(rows) == 1
    assert rows[0][0] == "INVALIDATE_ACTION"
    assert "ACTION_CANCELLED" in str(rows[0][1])

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("CANCELLED", "", 0)
    assert terminal_at is not None
    assert slice_of(world, str(turn_id)).assistant_turn is None
    assert turn_status(world, str(turn_id)) == TurnStatus.CANCELLED_BY_USER.value
    assert completion.assistant_turn_id is None
    assert completion.outcome == TurnOutcome.CANCELLED_BY_USER.value
    assert "ACTION_CANCELLED" in (completion.delivery_failure_reason or "")


def test_the_guard_invalidates_a_stale_turns_delivery_as_superseded(
    world: StreamWorld,
) -> None:
    """§15's ``action superseded`` carrier — the re-entry shape §3's table
    names ("旧/重入场景可达") and nothing else can produce in one epoch: a turn
    left nonterminal while a later turn was delivered, then re-entered. Its
    delivery must not reach the transcript; the §22 row freezes ``CANCELLED``
    and the turn ends ``CANCELLED_BY_USER`` (§1-C③)."""

    coordinator = coordinator_for(world)
    stale_turn, _ = open_turn_with_action(world, "cmid-p9-3-stale")
    newer = begin_turn_ok(coordinator, "cmid-p9-3-later")
    assert count(world.db, "assistant_turn") == 1

    replayed = begin_turn_ok(coordinator, "cmid-p9-3-stale")

    assert str(replayed.turn_id) == str(stale_turn)
    stale_action = action_of(world, str(stale_turn))
    rows = second_connection_rows(
        world,
        "SELECT decision, reason_codes FROM pre_delivery_guard_result"
        " WHERE action_id = ?",
        (str(stale_action),),
    )
    assert len(rows) == 1
    assert rows[0][0] == "INVALIDATE_ACTION"
    assert "ACTION_SUPERSEDED" in str(rows[0][1])
    assert (
        second_connection_row(world, stale_action)[0:3]
        == ("CANCELLED", "", 0)
    )
    assert slice_of(world, str(stale_turn)).assistant_turn is None
    assert (
        turn_status(world, str(stale_turn))
        == TurnStatus.CANCELLED_BY_USER.value
    )
    # the newer turn's own reply is untouched: one user-visible stream
    assert count(world.db, "assistant_turn") == 1
    newer_action = action_of(world, str(newer.turn_id))
    assert second_connection_row(world, newer_action)[0] == "SENT_COMPLETE"


# -- ④ the reconciler: the guard holder cancels, then hands off ----------------


def test_a_pending_request_ends_a_live_turn_before_the_new_turn_delivers(
    world: StreamWorld,
) -> None:
    """§17.1 rules 3-5 with no delivery in play: the request names a live turn
    (the worker died before producing anything), and the next turn's guard
    holder cancels it — ``CANCELLED_BY_USER``, no transcript row — and only
    then delivers its own reply."""

    log = WriteLog()
    coordinator = coordinator_for(
        world,
        commands=LoggingCommands(world.store, log),
        records=LoggingRecords(world.deliveries, log),
    )
    abandoned, _ = open_turn_with_action(world, "cmid-p9-3-abandoned")
    assert isinstance(
        coordinator.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-abandoned"),
                conversation_id=str(CONV),
                active_turn_id=abandoned,
                active_action_id=None,
                reason="forget that one",
            )
        ),
        Ok,
    )

    completion = begin_turn_ok(coordinator, "cmid-p9-3-after-abandon")

    assert turn_status(world, str(abandoned)) == TurnStatus.CANCELLED_BY_USER.value
    assert turn_outcome(world, str(abandoned)) == TurnOutcome.CANCELLED_BY_USER.value
    assert slice_of(world, str(abandoned)).assistant_turn is None
    assert completion.outcome == TurnOutcome.REPLIED_FULL.value
    assert count(world.db, "assistant_turn") == 1
    # §17.1 rule 5, in the write log: the old turn is terminal before the new
    # turn's first delivery row and before its canonicalization.
    old_terminal = log.index_of(
        ("terminalize_turn", str(abandoned), TurnOutcome.CANCELLED_BY_USER.value)
    )
    new_action = str(action_of(world, str(completion.turn_id)))
    assert old_terminal < log.index_of(
        ("record_server_delivery", new_action, "SENDING")
    )
    assert old_terminal < log.index_of(
        ("canonicalize_assistant_turn", str(completion.turn_id))
    )


def test_the_reconciler_cancels_a_live_delivery_at_its_durable_prefix(
    world: StreamWorld,
) -> None:
    """§18's conservative cancellation for a delivery that had already sent
    something: the §22 row freezes ``CANCELLED`` with the prefix and sequence
    **kept** (no replay, no truncation), the transcript is canonicalized from
    that prefix verbatim as ``SENT_PARTIAL``, and the turn ends
    ``CANCELLED_BY_USER`` — all before the new turn's own reply."""

    log = WriteLog()
    records = LoggingRecords(world.deliveries, log)
    coordinator = coordinator_for(
        world,
        commands=LoggingCommands(world.store, log),
        records=records,
    )
    turn_id, action_id = open_turn_with_action(world, "cmid-p9-3-half")
    drive_to_delivering(world, action_id)
    intent = world.generation.get_action(action_id)
    assert isinstance(intent, Ok) and intent.value is not None
    half = "half a reply"
    opened = records.record_server_delivery(
        ServerDeliveryRecord(
            action_id=action_id,
            assistant_turn_id=intent.value.assistant_turn_id,
            state="SENT_PARTIAL",
            sent_prefix=half,
            last_chunk_seq=1,
            started_at=STARTED_AT,
            terminal_at=None,
        )
    )
    assert isinstance(opened, Ok), opened
    assert isinstance(
        coordinator.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-half"),
                conversation_id=str(CONV),
                active_turn_id=None,
                active_action_id=action_id,
                reason="that is enough",
            )
        ),
        Ok,
    )

    completion = begin_turn_ok(coordinator, "cmid-p9-3-after-half")

    state, prefix, sequence, started_at, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("CANCELLED", half, 1)
    assert started_at == STARTED_AT  # the row's own instant, never restamped
    assert terminal_at is not None

    slice_ = slice_of(world, str(turn_id))
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.content == half
    assert slice_.assistant_turn.delivery_state.value == "SENT_PARTIAL"
    assert slice_.outcome is TurnOutcome.CANCELLED_BY_USER

    assert completion.outcome == TurnOutcome.REPLIED_FULL.value
    assert count(world.db, "assistant_turn") == 2  # the cancelled half + the new reply
    assert log.index_of(
        ("terminalize_turn", str(turn_id), TurnOutcome.CANCELLED_BY_USER.value)
    ) < log.index_of(
        ("record_server_delivery", str(completion.action_id), "SENDING")
    )
    assert log.states_of(str(action_id)) == ["SENT_PARTIAL", "CANCELLED"]


def test_a_frozen_row_is_not_rewritten_by_the_reconciler(
    world: StreamWorld,
) -> None:
    """The edge §1-C②'s reading registers: a row that had already frozen keeps
    its own word and instants (the record is the sent boundary, §17), while the
    transcript still takes the prefix and the turn still ends cancelled. The
    reconciler writes nothing to that row — the spy proves it."""

    log = WriteLog()
    records = LoggingRecords(world.deliveries, log)
    coordinator = coordinator_for(
        world,
        commands=LoggingCommands(world.store, log),
        records=records,
    )
    turn_id, action_id = open_turn_with_action(world, "cmid-p9-3-frozen")
    drive_to_delivering(world, action_id)
    intent = world.generation.get_action(action_id)
    assert isinstance(intent, Ok) and intent.value is not None
    frozen_at = "2026-09-24T00:00:05+00:00"
    assert isinstance(
        records.record_server_delivery(
            ServerDeliveryRecord(
                action_id=action_id,
                assistant_turn_id=intent.value.assistant_turn_id,
                state="SENT_PARTIAL",
                sent_prefix="sent before the crash",
                last_chunk_seq=1,
                started_at=STARTED_AT,
                terminal_at=frozen_at,
            )
        ),
        Ok,
    )
    assert isinstance(
        coordinator.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-frozen"),
                conversation_id=str(CONV),
                active_turn_id=None,
                active_action_id=action_id,
                reason="stop",
            )
        ),
        Ok,
    )
    begin_turn_ok(coordinator, "cmid-p9-3-after-frozen")

    state, prefix, sequence, started_at, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence, started_at, terminal_at) == (
        "SENT_PARTIAL",
        "sent before the crash",
        1,
        STARTED_AT,
        frozen_at,
    )
    assert log.states_of(str(action_id)) == ["SENT_PARTIAL"]
    assert slice_of(world, str(turn_id)).assistant_turn is not None
    assert turn_status(world, str(turn_id)) == TurnStatus.CANCELLED_BY_USER.value


def test_a_request_naming_a_foreign_epoch_row_is_skipped_not_refused(
    world: StreamWorld,
) -> None:
    """The fence reading: §17.1's actor is the guard holder *of the epoch that
    owns the row*, so a request naming another epoch's turn is left pending —
    the new turn proceeds (RA §21's degradation, not blockage) and the request
    stays visible as unanswered."""

    abandoned, _ = open_turn_with_action(world, "cmid-p9-3-fenced")
    fence2 = epoch.open_runtime_epoch(world.db)
    lease2 = ConversationCoordinatorLease()
    lease2.adopt_epoch(fence2)
    store2 = SqliteConversationStore(world.db, fence2)
    generation2 = AssemblyGenerationStore(world.db, fence2)
    coordinator2 = ConversationCoordinator(
        lease=lease2,
        conversation_commands=store2,
        conversation_queries=store2,
        persona=persona_runtime_over(generation2),
        generation_actions=generation2,
        decision_cycles=generation2.decision_cycles,
        delivery_records=SqliteDeliveryRecordStore(world.db, fence2),
    )
    assert isinstance(
        coordinator2.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-fenced"),
                conversation_id=str(CONV),
                active_turn_id=abandoned,
                active_action_id=None,
                reason="old work",
            )
        ),
        Ok,
    )

    completion = begin_turn_ok(coordinator2, "cmid-p9-3-epoch-two")

    assert completion.outcome == TurnOutcome.REPLIED_FULL.value
    # the cancelled-by-nobody turn is still nonterminal, and its request is
    # still pending: the recovery owner's work, not this epoch's.
    assert turn_status(world, str(abandoned)) == TurnStatus.USER_COMMITTED.value
    pending = store2.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(pending, Ok), pending
    assert [str(request.input_id) for request in pending.value] == [
        "in-p9-3-fenced"
    ]


def test_the_reconciler_is_a_no_op_when_nothing_is_pending(
    world: StreamWorld,
) -> None:
    """The guard holder asks every turn (§17.1 rule 3) and an empty answer
    writes nothing: the read comes back empty, the cancelled ids are empty, and
    the durable rows a reconcile would have touched are untouched."""

    completion = begin_turn_ok(coordinator_for(world), "cmid-p9-3-noop")
    turn_id = str(completion.turn_id)
    coordinator = coordinator_for(world)
    before = (
        count(world.db, "assistant_turn"),
        turn_status(world, turn_id),
    )
    result = coordinator._reconcile_pending_interrupt(CONV)  # noqa: SLF001
    assert isinstance(result, Ok), result
    assert result.value == ()
    assert (
        count(world.db, "assistant_turn"),
        turn_status(world, turn_id),
    ) == before


def test_a_turn_only_request_is_pending_and_the_action_keyed_read_is_empty(
    world: StreamWorld,
) -> None:
    """The three reads answer different questions about the same row: with a
    request that names only the turn, the conversation- and turn-keyed reads
    see it and the action-keyed read (asked about an action the request never
    named) does not."""

    turn_id, action_id = open_turn_with_action(world, "cmid-p9-3-turn-only")
    assert isinstance(
        world.store.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-turn-only"),
                conversation_id=str(CONV),
                active_turn_id=turn_id,
                active_action_id=None,
                reason="only the turn",
            )
        ),
        Ok,
    )
    by_turn = world.store.list_pending_interrupts_for_turn(turn_id)
    by_action = world.store.list_pending_interrupts_for_action(action_id)
    by_conversation = world.store.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(by_turn, Ok) and isinstance(by_action, Ok)
    assert isinstance(by_conversation, Ok)
    assert [str(row.input_id) for row in by_turn.value] == ["in-p9-3-turn-only"]
    assert by_action.value == ()
    assert by_conversation.value == by_turn.value
    assert by_turn.value[0].active_action_id is None


def test_two_pending_requests_are_cancelled_in_the_order_they_were_made(
    world: StreamWorld,
) -> None:
    """§17.1 rule 3's ordering, observed through the cancellations: two requests
    naming two live turns are answered oldest-first (``created_at`` then
    ``input_id``), which is what the report's ordering claim rests on."""

    first, _ = open_turn_with_action(world, "cmid-p9-3-first")
    second, _ = open_turn_with_action(world, "cmid-p9-3-second")
    for order, turn_id in ((1, first), (2, second)):
        assert isinstance(
            world.store.request_interrupt(
                InterruptRequest(
                    input_id=InputId(f"in-p9-3-order-{order}"),
                    conversation_id=str(CONV),
                    active_turn_id=turn_id,
                    active_action_id=None,
                    reason=f"request {order}",
                )
            ),
            Ok,
        )
    coordinator = coordinator_for(world)
    cancelled = coordinator._reconcile_pending_interrupt(CONV)  # noqa: SLF001
    assert isinstance(cancelled, Ok), cancelled
    assert list(cancelled.value) == [str(first), str(second)]
    for turn_id in (first, second):
        assert turn_status(world, str(turn_id)) == "CANCELLED_BY_USER"


def test_the_wrapper_answers_the_drivers_own_stop_word_and_delegates_emit(
    world: StreamWorld,
) -> None:
    """The wrapper as a value: with nothing pending it is the inner transport
    (same steps, same emissions), and with a request pending it stops *before*
    the next take — the driver then reports the wrapper's own reason verbatim
    in ``stop_reason`` (P9-2's reading 6 stays true: the word is data)."""

    from elc.runtime.guarded_stream import run_guarded_stream
    from elc.runtime.interrupt_transport import (
        INTERRUPT_STOP_REASON,
        InterruptAwareTransport,
    )

    inner = LocalProbeSource(["one", "two"])
    quiet = InterruptAwareTransport(inner, pending=lambda: False)
    run = run_guarded_stream(transport=quiet, contract=None)
    assert run.state == "SENT_COMPLETE"
    assert run.sent_prefix == "onetwo"
    assert inner.emitted == ["one", "two"]

    stopping = InterruptAwareTransport(
        LocalProbeSource(["one", "two"]), pending=lambda: True
    )
    run = run_guarded_stream(transport=stopping, contract=None)
    assert run.state == "FAILED"
    assert run.stop_reason == INTERRUPT_STOP_REASON == "interrupt"
    assert run.durable_prefix == ""
    assert "interrupt" in (run.failure_reason or "")


class LocalProbeSource:
    """The smallest transport the wrapper can wrap (chunks, then end)."""

    def __init__(self, chunks: list[str]) -> None:
        self._steps = [
            *(StreamStep.chunk(chunk) for chunk in chunks),
            StreamStep.end(),
        ]
        self._index = 0
        self.emitted: list[str] = []

    def take(self) -> StreamStep:
        if self._index >= len(self._steps):
            return StreamStep.end()
        step = self._steps[self._index]
        self._index += 1
        return step

    def emit(self, text: str) -> Result[None]:
        self.emitted.append(text)
        return Ok(None)


# -- ⑤ the read face -----------------------------------------------------------


def test_a_request_naming_a_terminal_action_is_not_pending(
    world: StreamWorld,
) -> None:
    """The predicate's negative arm: an interrupt that still names an action
    the delivery already finished is answered history, not work — and the row
    is still there (the audit trail §17.1 makes durable)."""

    completion = begin_turn_ok(coordinator_for(world), "cmid-p9-3-done")
    action_id = action_of(world, str(completion.turn_id))
    assert isinstance(
        world.store.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-too-late"),
                conversation_id=str(CONV),
                active_turn_id=None,
                active_action_id=action_id,
                reason="too late",
            )
        ),
        Ok,
    )

    assert pending_for_action(world, action_id) == ()
    assert interrupt_row(world, "in-p9-3-too-late") is not None
    conversation = world.store.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(conversation, Ok), conversation
    assert conversation.value == ()


def test_a_request_naming_nothing_or_a_missing_row_is_not_pending(
    world: StreamWorld,
) -> None:
    """A request that names no leg, or names rows that do not exist, has
    nothing live to cancel: pending requires a *named nonterminal row*, so a
    reconciler never chases a ghost."""

    assert isinstance(
        world.store.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-nothing"),
                conversation_id=str(CONV),
                active_turn_id=None,
                active_action_id=None,
                reason="nothing named",
            )
        ),
        Ok,
    )
    assert isinstance(
        world.store.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-3-ghost"),
                conversation_id=str(CONV),
                active_turn_id=TurnId("turn-p9-3-ghost"),
                active_action_id=ActionId("ga-p9-3-ghost"),
                reason="ghost",
            )
        ),
        Ok,
    )

    for method, argument in (
        (world.store.list_pending_interrupts_for_action, ActionId("ga-p9-3-ghost")),
        (world.store.list_pending_interrupts_for_turn, TurnId("turn-p9-3-ghost")),
    ):
        result = method(argument)
        assert isinstance(result, Ok), result
        assert result.value == ()
    conversation = world.store.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(conversation, Ok), conversation
    assert conversation.value == ()


def test_the_three_reads_agree_and_a_tie_breaks_by_input_id(
    world: StreamWorld,
) -> None:
    """One definition, three entry points: the action-, turn- and
    conversation-keyed reads answer the same row. The order is ``created_at``
    then ``input_id`` — pinned here with two rows written at the *same* instant
    through a direct insert (setup, not a canonical write: the audit row has no
    domain command that can forge an instant), where only the id can decide."""

    turn_id, action_id = open_turn_with_action(world, "cmid-p9-3-order")
    for input_id, stamp in (
        ("in-p9-3-b", "2026-09-24T00:00:00+00:00"),
        ("in-p9-3-a", "2026-09-24T00:00:00+00:00"),
    ):
        world.db.execute(
            "INSERT INTO interrupt_request (input_id, conversation_id,"
            " active_turn_id, active_action_id, reason, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (input_id, str(CONV), str(turn_id), str(action_id), "tie", stamp),
        )

    by_action = world.store.list_pending_interrupts_for_action(action_id)
    by_turn = world.store.list_pending_interrupts_for_turn(turn_id)
    by_conversation = world.store.list_pending_interrupts_for_conversation(CONV)
    for result in (by_action, by_turn, by_conversation):
        assert isinstance(result, Ok), result
    assert [str(row.input_id) for row in by_action.value] == [
        "in-p9-3-a",
        "in-p9-3-b",
    ]
    assert by_turn.value == by_action.value
    assert by_conversation.value == by_action.value
    assert str(by_action.value[0].active_turn_id) == str(turn_id)
    assert str(by_action.value[0].active_action_id) == str(action_id)
