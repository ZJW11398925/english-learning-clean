"""P9-2 ② — the streamed ordinary turn on the real chain.

One ordinary conversation turn over the shipped faces and nothing else:
migrations into a **file-backed** app.db (so a second connection can read the
committed rows), an opened runtime epoch, the conversation store's real CP0
commit, the real DecisionCycle unit, the real generation store with its §14
action machine, the §22 delivery-record adapter, and the coordinator with its
two new optional injections (``delivery_records`` + ``stream_transport``). No
``_seed``-shaped helper exists here and no fixture target provider is imported
(the P5-1 red line, held by phases 6/7/8/9).

What only a real chain can show, and what each test is for:

- the row the caller's face advances **is durable and frozen**: its states are
  asserted as the *submission sequence* through a spy store (SENDING, one
  SENT_PARTIAL per accepted chunk, the terminal word), and its final columns are
  read back through a second connection, not from the object that wrote it;
- the transcript's content is the durable ``sent_prefix`` **verbatim** — the
  assertion is an equality between two independently read rows (the §22 row and
  the assistant_turn row), and the partial cases add the negative half (the
  unsent tail is nowhere in the transcript);
- a delivery that could not be delivered writes **no** assistant_turn row and
  fails the turn ``FAILED_USER_VISIBLE`` (undelivered provider output never
  enters the transcript);
- the two edges where the run value and the record disagree are pinned rather
  than smoothed: a first chunk the record refuses (released, yet the durable
  prefix is empty) writes no transcript row while its §22 row is still frozen
  at ``SENT_PARTIAL`` — empty prefix, sequence zero — and an exception raised
  *across* the transport boundary leaves the row exactly as the record face
  holds it (never rewritten backwards, never claimed away), with the reason
  naming that durable half;
- the two faces §22 tells apart are the only ones written: zero
  ``client_render_ack`` rows (the main turn does not wait for an ACK, RA §6),
  zero ``exposure_estimate`` rows (P9-4's face) and zero §21.1 rows (this cut
  writes none — the module's reading 8).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import CommitUserTurn
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.persona.types import ProviderOutput
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    Result,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.delivery_records import ServerDeliveryRecord
from elc.runtime.guarded_stream import StreamStep, StreamTransport
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    GenerationActionStatus,
    InputEnvelope,
    TurnStatus,
)
from tests.conftest import AssemblyGenerationStore
from tests.phase7.conftest import USER
from tests.phase8.conftest import CONV, RECEIVED_AT

#: The reply the scripted provider produces — long enough for three chunks and
#: for a prefix that is unambiguously shorter than the whole.
REPLY = (
    "Let's keep going: rehearse the sentence once, then say it aloud"
    " yourself — slowly, and out loud."
)

#: The §21 forbidden claim the shipped contract already carries (word for word
#: from ``elc.persona.types.DEFAULT_FORBIDDEN_CLAIMS``): the source below offers
#: it although the provider never produced it, which is the untrusted-source
#: case the guard exists for.
FORBIDDEN_TEXT = "你已经完全掌握"


# -- the world -----------------------------------------------------------------


@dataclass(frozen=True)
class StreamWorld:
    """A file-backed app.db, its epoch, and the three stores one turn needs."""

    path: Path
    db: sqlite3.Connection
    fence: RuntimeEpochFence
    store: SqliteConversationStore
    generation: AssemblyGenerationStore
    deliveries: SqliteDeliveryRecordStore


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


def stream_world(tmp_path: Path) -> StreamWorld:
    """One file-backed app.db with its conversation — the shape both P9-2
    suites build (a plain function so a sibling suite can ask for it without
    importing this module's fixture)."""

    path = tmp_path / "app.db"
    db = connection.connect(path)
    migrations.apply_migrations(db)
    fence = epoch.open_runtime_epoch(db)
    store = SqliteConversationStore(db, fence)
    opened = store.open_conversation(
        CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    return StreamWorld(
        path=path,
        db=db,
        fence=fence,
        store=store,
        generation=AssemblyGenerationStore(db, fence),
        deliveries=SqliteDeliveryRecordStore(db, fence),
    )


def persona_runtime(
    world: StreamWorld, *, text: str = REPLY
) -> PersonaRuntime:
    return PersonaRuntime(
        actions=world.generation,
        provider=ScriptedPersonaProvider(
            script=(ProviderOutput(text=text),)
        ),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )


#: ``coordinator_``'s "the real §22 face" default (a caller passes ``False``
#: for "no record face at all", which is a different fact from a wired face
#: that refuses a write).
REAL_RECORD_FACE = object()


def coordinator_(
    world: StreamWorld,
    *,
    transport: Callable[..., StreamTransport] | None = None,
    records: object = REAL_RECORD_FACE,
) -> ConversationCoordinator:
    """The coordinator this cut's two injections build — with the real §22 face,
    with a spy over it, or with none at all (``records=False``)."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    delivery_records = world.deliveries if records is REAL_RECORD_FACE else records
    if delivery_records is False:  # "no record face at all"
        delivery_records = None
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=world.store,
        conversation_queries=world.store,
        persona=persona_runtime(world),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=delivery_records,  # type: ignore[arg-type]
        stream_transport=transport,
    )


def command(
    client_message_id: str, *, conversation: ConversationId = CONV
) -> CommitUserTurn:
    return CommitUserTurn(
        conversation_id=conversation,
        envelope=InputEnvelope(
            input_id=InputId(f"in-{client_message_id}"),
            client_message_id=ClientMessageId(client_message_id),
            conversation_id=str(conversation),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=f"raw-{client_message_id}",
            received_at=RECEIVED_AT,
        ),
        raw_content="I would like to rehearse the sentence again.",
        runtime_version="runtime-p9-2",
    )


def begin_turn_ok(
    coordinator: ConversationCoordinator, client_message_id: str
) -> object:
    result = coordinator.begin_turn(command(client_message_id))
    assert isinstance(result, Ok), result
    return result.value


# -- the source, the spies -----------------------------------------------------


@dataclass
class ScriptedSource:
    """The stream a test scripts: the steps, and (optionally) the *n*-th
    release refused so a broken client boundary can be driven.

    ``refuse_emit_at`` is the boundary answering ``Err`` (a value the driver
    reports itself); ``raise_emit_at`` is the boundary **raising** — the shape
    where the exception leaves the driver and the caller must reconstruct the
    run value (the *second* call, so the run has a durable half by then)."""

    steps: tuple[StreamStep, ...]
    refuse_emit_at: int | None = None
    raise_emit_at: int | None = None

    def __post_init__(self) -> None:
        self._index = 0
        self._emit_calls = 0
        self.emitted: list[str] = []

    def take(self) -> StreamStep:
        if self._index >= len(self.steps):
            return StreamStep.end()
        step = self.steps[self._index]
        self._index += 1
        return step

    def emit(self, text: str) -> Result[None]:
        self._emit_calls += 1
        if (
            self.raise_emit_at is not None
            and self._emit_calls == self.raise_emit_at
        ):
            raise RuntimeError("the client boundary died mid-release")
        if (
            self.refuse_emit_at is not None
            and self._emit_calls == self.refuse_emit_at
        ):
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="the client boundary is gone",
                )
            )
        self.emitted.append(text)
        return Ok(None)


class SourceFactory:
    """The ``StreamTransportFactory`` a test injects: it records that it was
    asked (a refused delivery must never reach it) and answers the one scripted
    source."""

    def __init__(self, source: ScriptedSource) -> None:
        self.source = source
        self.calls: list[tuple[str, ActionId]] = []

    def __call__(
        self, *, validated_text: str, action_id: ActionId
    ) -> StreamTransport:
        self.calls.append((validated_text, action_id))
        return self.source


class RecordingStore:
    """The delivery-record face a test watches: every submission goes through
    to the real adapter, and is kept in order (the spy's log is the evidence
    for the row's *transition sequence*, which the durable row no longer shows
    once it has advanced)."""

    def __init__(
        self,
        inner: SqliteDeliveryRecordStore,
        *,
        refuse_at: int | None = None,
    ) -> None:
        self._inner = inner
        self._refuse_at = refuse_at
        self.submitted: list[ServerDeliveryRecord] = []

    def record_server_delivery(
        self, record: ServerDeliveryRecord
    ) -> Result[ServerDeliveryRecord]:
        self.submitted.append(record)
        if (
            self._refuse_at is not None
            and len(self.submitted) == self._refuse_at
        ):
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message="the record face refused this write",
                )
            )
        return self._inner.record_server_delivery(record)

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


def pieces(text: str, count: int) -> list[str]:
    """``text`` cut into ``count`` roughly equal pieces (the last one takes the
    remainder)."""

    size = max(1, len(text) // count)
    return [text[index : index + size] for index in range(0, len(text), size)]


def second_connection_row(
    world: StreamWorld, action_id: ActionId
) -> tuple[str, str, int, str, str | None]:
    """The §22 row as a **second** connection reads it (never the writer)."""

    second = connection.connect(world.path)
    try:
        row = second.execute(
            "SELECT state, sent_prefix, last_chunk_seq, started_at,"
            " terminal_at FROM server_delivery_record WHERE action_id = ?",
            (str(action_id),),
        ).fetchone()
    finally:
        second.close()
    assert row is not None, "no server_delivery_record row for this action"
    return (
        str(row[0]),
        str(row[1]),
        int(row[2]),
        str(row[3]),
        None if row[4] is None else str(row[4]),
    )


def count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def action_of(world: StreamWorld, turn_id: str) -> ActionId:
    result = world.generation.get_action_for_turn(turn_id)
    assert isinstance(result, Ok), result
    assert result.value is not None
    return result.value.action_id


def slice_of(world: StreamWorld, turn_id: str):
    result = world.store.get_canonical_turn_slice(turn_id)
    assert isinstance(result, Ok), result
    assert result.value is not None
    return result.value


# -- ① the healthy streamed turn ----------------------------------------------


def test_a_streamed_turn_advances_the_delivery_row_through_its_states(
    world: StreamWorld,
) -> None:
    """The row's whole life, as the submissions the caller made: it opens at
    ``SENDING`` with nothing sent, advances to ``SENT_PARTIAL`` once per
    accepted chunk (each one carrying the prefix that far), and freezes at
    ``SENT_COMPLETE`` with the terminal instant set."""

    spy = RecordingStore(world.deliveries)
    source = ScriptedSource(
        steps=tuple(
            StreamStep.chunk(piece) for piece in pieces(REPLY, 3)
        )
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-2-states",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    assert [
        (row.state, row.sent_prefix, row.last_chunk_seq, row.terminal_at)
        for row in spy.submitted
    ] == [
        ("SENDING", "", 0, None),
        ("SENT_PARTIAL", pieces(REPLY, 3)[0], 1, None),
        ("SENT_PARTIAL", "".join(pieces(REPLY, 3)[:2]), 2, None),
        ("SENT_PARTIAL", REPLY, 3, None),
        ("SENT_COMPLETE", REPLY, 3, spy.submitted[-1].terminal_at),
    ]
    assert spy.submitted[-1].terminal_at is not None
    # every instant of the row is the same delivery's: started once, frozen once
    assert {row.started_at for row in spy.submitted} == {
        spy.submitted[0].started_at
    }

    state, prefix, sequence, started_at, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_COMPLETE", REPLY, 3)
    assert started_at == spy.submitted[0].started_at
    assert terminal_at == spy.submitted[-1].terminal_at

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    # the transcript's content is the durable boundary, byte for byte
    assert canonical.assistant_turn.content == prefix
    assert canonical.assistant_turn.delivery_state.value == "SENT_COMPLETE"
    assert canonical.assistant_turn.delivery_certainty == "SERVER_SENT_UNCONFIRMED"
    assert canonical.outcome is not None
    assert canonical.outcome.value == "REPLIED_FULL"

    action = world.generation.get_action(action_id)
    assert isinstance(action, Ok) and action.value is not None
    assert action.value.status is GenerationActionStatus.TERMINAL

    assert completion.turn_status is TurnStatus.COMPLETED
    assert completion.outcome == "REPLIED_FULL"
    assert completion.delivery_state == "SENT_COMPLETE"
    assert completion.delivery_failure_reason is None
    assert completion.reply_text == prefix
    assert source.emitted == pieces(REPLY, 3)


def test_the_frozen_row_cannot_be_moved_after_the_turn(world: StreamWorld) -> None:
    """The turn's own last write is what freezes the row: a later attempt to
    send it back to ``SENT_PARTIAL`` is refused by the §22 invariants, so the
    terminal fact the turn wrote is the row's last word."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-2-freeze")
    action_id = action_of(world, str(completion.turn_id))
    state, prefix, sequence, started_at, terminal_at = second_connection_row(
        world, action_id
    )

    refused = world.deliveries.record_server_delivery(
        ServerDeliveryRecord(
            action_id=action_id,
            assistant_turn_id=world.generation.get_action(action_id).value.assistant_turn_id,  # type: ignore[union-attr]
            state="SENT_PARTIAL",
            sent_prefix=prefix,
            last_chunk_seq=sequence,
            started_at=started_at,
            terminal_at=None,
        )
    )
    assert isinstance(refused, Err)
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert second_connection_row(world, action_id)[0] == state == "SENT_COMPLETE"
    assert terminal_at is not None


@pytest.mark.parametrize("cuts", [1, 2, 5, 7])
def test_the_content_is_exactly_what_the_source_released(
    world: StreamWorld, cuts: int
) -> None:
    """The chunking is the source's business and the transcript's content does
    not depend on it: whatever the cut, the durable prefix is the whole reply
    and the recorded chunk sequence is the number of releases."""

    wanted = pieces(REPLY, cuts)
    source = ScriptedSource(
        steps=tuple(StreamStep.chunk(piece) for piece in wanted)
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source)),
        f"cmid-p9-2-cuts-{cuts}",
    )
    action_id = action_of(world, str(completion.turn_id))

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_COMPLETE", REPLY, len(wanted))
    assert terminal_at is not None
    canonical = slice_of(world, str(completion.turn_id))
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == prefix == REPLY


def test_the_default_transport_lands_one_chunk_and_the_whole_reply(
    world: StreamWorld,
) -> None:
    """No ``stream_transport`` injected: V1's in-process placeholder releases
    the validated text as one chunk, which is why the default assembly's
    delivery faces are the buffered face's (the equivalence suite's subject)."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-2-default")
    action_id = action_of(world, str(completion.turn_id))

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_COMPLETE", REPLY, 1)
    assert terminal_at is not None
    assert completion.reply_text == REPLY
    assert completion.delivery_state == "SENT_COMPLETE"


def test_a_healthy_streamed_turn_writes_no_ack_estimate_or_guard_row(
    world: StreamWorld,
) -> None:
    """RA §6 and this cut's reach — and the one truth P9-3 moved.

    The main turn does not wait for a ``ClientRenderAck`` (no row), the exposure
    estimate is P9-4's face (no row), and the ``validator_result`` rows belong
    to the validator's own attempt face (still no row here). The §21.1
    ``pre_delivery_guard_result`` row is a **different** case: P9-2 wrote none
    because no face ran §15's check, and §21.1's guard writer landed with P9-3
    — so a healthy streamed turn now carries exactly one ``VALID`` row, and the
    assertion is stronger than "no row" was: the row names the action, carries
    no reason code (all seven facts were read and none held), and spells a
    non-empty lineage version. The name keeps P9-2's shape on purpose (this is
    that cut's test, with its truth updated); a reader who wants the guard's own
    suite reads ``test_p9_3_pre_delivery_guard.py``."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-2-clean")

    for table in (
        "client_render_ack",
        "exposure_estimate",
        "validator_result",
    ):
        assert count(world.db, table) == 0, table
    assert count(world.db, "server_delivery_record") == 1
    assert count(world.db, "assistant_turn") == 1

    action_id = action_of(world, str(completion.turn_id))
    rows = world.deliveries.list_pre_delivery_guard_results(action_id)
    assert isinstance(rows, Ok), rows
    assert len(rows.value) == 1
    guard = rows.value[0]
    assert guard.action_id == action_id
    assert (guard.decision, guard.reason_codes) == ("VALID", ())
    assert guard.checked_lineage_version, (
        "the §21.1 row must carry the lineage it was checked against"
    )
    assert guard.created_at


# -- ② the stops ---------------------------------------------------------------


@pytest.mark.parametrize("kept_cuts", [1, 2])
def test_a_stopped_source_delivers_a_partial_reply_without_the_unsent_tail(
    world: StreamWorld, kept_cuts: int
) -> None:
    """The whole point of §17's boundary: the prefix that was released is the
    transcript's content, the tail the source never produced is nowhere, the
    row says ``SENT_PARTIAL``, and the turn is a real (partial) reply — at two
    different cut points, so "the prefix" cannot be a coincidence of one."""

    kept = "".join(pieces(REPLY, 3)[:kept_cuts])
    source = ScriptedSource(
        steps=(
            *(StreamStep.chunk(piece) for piece in pieces(REPLY, 3)[:kept_cuts]),
            StreamStep.stopped("the client window closed"),
        )
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source)),
        f"cmid-p9-2-stopped-{kept_cuts}",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_PARTIAL", kept, kept_cuts)
    assert terminal_at is not None

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == kept
    assert canonical.assistant_turn.delivery_state.value == "SENT_PARTIAL"
    assert REPLY not in canonical.assistant_turn.content
    assert REPLY[len(kept) :] not in canonical.assistant_turn.content
    assert canonical.outcome is not None
    assert canonical.outcome.value == "REPLIED_PARTIAL"

    action = world.generation.get_action(action_id)
    assert action.value is not None
    assert action.value.status is GenerationActionStatus.TERMINAL
    assert completion.turn_status is TurnStatus.COMPLETED
    assert completion.outcome == "REPLIED_PARTIAL"
    assert completion.delivery_state == "SENT_PARTIAL"
    assert completion.delivery_failure_reason is not None
    assert "the client window closed" in completion.delivery_failure_reason
    assert completion.reply_text == kept


def test_a_chunk_the_guard_refuses_never_reaches_the_reply(
    world: StreamWorld,
) -> None:
    """The source offers text the provider never produced (the §21 forbidden
    claim the shipped contract carries): the guard refuses it before the
    release, so the transcript holds the accepted prefix and neither the claim
    nor anything after it."""

    kept = pieces(REPLY, 3)[0]
    source = ScriptedSource(
        steps=(
            StreamStep.chunk(kept),
            StreamStep.chunk(FORBIDDEN_TEXT),
            StreamStep.chunk("and here is more"),
        )
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source)),
        "cmid-p9-2-refused",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    state, prefix, sequence, _, _ = second_connection_row(world, action_id)
    assert (state, prefix, sequence) == ("SENT_PARTIAL", kept, 1)
    assert source.emitted == [kept]  # neither later chunk was released

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == kept
    assert FORBIDDEN_TEXT not in canonical.assistant_turn.content
    assert completion.delivery_state == "SENT_PARTIAL"
    assert completion.delivery_failure_reason is not None
    assert "FORBIDDEN_CLAIM" in completion.delivery_failure_reason
    assert completion.outcome == "REPLIED_PARTIAL"


def test_a_transport_that_refuses_a_chunk_delivers_what_it_kept(
    world: StreamWorld,
) -> None:
    kept, lost = pieces(REPLY, 3)[:2]
    source = ScriptedSource(
        steps=(StreamStep.chunk(kept), StreamStep.chunk(lost)),
        refuse_emit_at=2,
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source)),
        "cmid-p9-2-transport",
    )
    action_id = action_of(world, str(completion.turn_id))

    state, prefix, sequence, _, _ = second_connection_row(world, action_id)
    assert (state, prefix, sequence) == ("SENT_PARTIAL", kept, 1)
    assert source.emitted == [kept]
    canonical = slice_of(world, str(completion.turn_id))
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == kept
    assert lost not in canonical.assistant_turn.content
    assert completion.delivery_failure_reason is not None
    assert "the client boundary is gone" in completion.delivery_failure_reason


def test_a_boundary_that_raises_leaves_the_row_as_the_record_face_holds_it(
    world: StreamWorld,
) -> None:
    """An exception *across* the transport boundary, one release in — the other
    half of "the record is the boundary authority".

    ``emit`` raising is not ``emit`` answering ``Err``: the exception leaves
    the driver, so the run value is lost and the caller rebuilds the
    conservative one (``FAILED``, nothing claimed). The record face is then
    the only authority for what was sent, and it already holds the first
    chunk: the reconstructed terminal write would move the row backwards
    (prefix ``kept`` → ``""``, sequence ``1`` → ``0``), so it is **refused**
    and the row stays exactly as that face holds it — ``SENT_PARTIAL`` with
    the released prefix and its sequence, **never frozen**. The reason must
    admit that durable half (it is the one readable fact left) instead of
    claiming nothing can be proven; the transcript stays empty and the turn
    fails ``FAILED_USER_VISIBLE``."""

    kept, lost = pieces(REPLY, 3)[:2]
    spy = RecordingStore(world.deliveries)
    source = ScriptedSource(
        steps=(StreamStep.chunk(kept), StreamStep.chunk(lost)),
        raise_emit_at=2,  # the first release landed; the second raised
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-2-boundary-raise",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    # the last submission the face ever saw is the reconstructed FAILED — no
    # later SENT_PARTIAL write follows it
    assert [(row.state, row.sent_prefix) for row in spy.submitted] == [
        ("SENDING", ""),
        ("SENT_PARTIAL", kept),
        ("FAILED", ""),
    ]
    assert spy.submitted[-1].terminal_at is not None
    assert source.emitted == [kept]

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_PARTIAL", kept, 1)
    assert terminal_at is None  # the row was never frozen

    reason = completion.delivery_failure_reason
    assert reason is not None
    assert "the stream boundary raised" in reason
    assert "durable prefix" in reason
    assert "can be proven" not in reason

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is None
    assert canonical.outcome is not None
    assert canonical.outcome.value == "FAILED_USER_VISIBLE"
    assert completion.turn_status is TurnStatus.FAILED_FINAL
    assert completion.delivery_state == "FAILED"
    assert completion.reply_text is None
    assert count(world.db, "assistant_turn") == 0


def test_a_run_that_released_nothing_writes_no_assistant_turn(
    world: StreamWorld,
) -> None:
    """The negative half of DOMAIN_MODEL §3: a delivery that sent nothing is
    ``FAILED`` (terminal, with its instant), the action is TERMINAL undelivered,
    no assistant_turn row exists, and the turn fails ``FAILED_USER_VISIBLE``."""

    source = ScriptedSource(
        steps=(StreamStep.stopped("nothing came back yet"),)
    )
    factory = SourceFactory(source)
    completion = begin_turn_ok(
        coordinator_(world, transport=factory), "cmid-p9-2-nothing"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("FAILED", "", 0)
    assert terminal_at is not None
    assert source.emitted == []

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is None
    assert canonical.outcome is not None
    assert canonical.outcome.value == "FAILED_USER_VISIBLE"

    action = world.generation.get_action(action_id)
    assert action.value is not None
    assert action.value.status is GenerationActionStatus.TERMINAL
    assert completion.assistant_turn_id is None
    assert completion.reply_text is None
    assert completion.delivery_state == "FAILED"
    assert completion.delivery_failure_reason is not None
    assert "nothing came back yet" in completion.delivery_failure_reason


def test_a_refused_opening_write_stops_before_anything_is_sent(
    world: StreamWorld,
) -> None:
    """A wired record face that refuses the ``SENDING`` write ends the delivery
    before the source is even built: nothing is sent (the transport was never
    asked for a chunk), nothing is claimed, and the turn fails
    ``FAILED_USER_VISIBLE`` — the honest shape of "the send never started"."""

    spy = RecordingStore(world.deliveries, refuse_at=1)
    source = ScriptedSource(steps=(StreamStep.chunk(REPLY),))
    factory = SourceFactory(source)
    completion = begin_turn_ok(
        coordinator_(world, transport=factory, records=spy),
        "cmid-p9-2-opening",
    )
    turn_id = str(completion.turn_id)

    assert factory.calls == []  # the stream never started
    assert source.emitted == []
    assert count(world.db, "server_delivery_record") == 0
    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is None
    assert canonical.outcome is not None
    assert canonical.outcome.value == "FAILED_USER_VISIBLE"
    assert completion.delivery_state == "FAILED"
    assert completion.delivery_failure_reason is not None
    assert "could not be opened" in completion.delivery_failure_reason


def test_a_refused_chunk_record_stops_the_stream_at_the_durable_prefix(
    world: StreamWorld,
) -> None:
    """The record is the boundary authority: when its write for the second
    chunk is refused, the delivery stops *there* — the transcript carries the
    first chunk (already released and already recorded), never the second —
    and the reason is reported rather than swallowed."""

    kept, second = pieces(REPLY, 3)[:2]
    spy = RecordingStore(world.deliveries, refuse_at=3)  # 1 opening, 2 chunk-1
    source = ScriptedSource(
        steps=(StreamStep.chunk(kept), StreamStep.chunk(second))
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-2-record-fail",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_PARTIAL", kept, 1)
    assert terminal_at is not None
    assert source.emitted == [kept, second]  # the second *was* released

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == kept
    assert second not in canonical.assistant_turn.content
    assert canonical.outcome is not None
    assert canonical.outcome.value == "REPLIED_PARTIAL"
    assert completion.delivery_state == "SENT_PARTIAL"
    assert completion.delivery_failure_reason is not None
    assert "record refused the chunk" in completion.delivery_failure_reason


def test_a_first_chunk_the_record_refuses_leaves_an_empty_partial_row(
    world: StreamWorld,
) -> None:
    """The fourth shape, registered rather than smoothed: the first chunk *was*
    released (the boundary received it) but the record face refused its write,
    so the durable prefix is empty *while* the run released a chunk — a
    different fact from a run that released nothing, and the one shape §17's
    boundary leaves with no honest transcript.

    The three submissions tell the story: the opening ``SENDING``, the refused
    advance for the released chunk (prefix and sequence as sent), and the
    terminal write that **freezes the row at ``SENT_PARTIAL``** with the empty
    durable prefix and sequence zero. Nothing enters the transcript, and the
    turn fails ``FAILED_USER_VISIBLE`` (``FAILED_FINAL``) with the reason
    readable."""

    first, second = pieces(REPLY, 3)[:2]
    spy = RecordingStore(world.deliveries, refuse_at=2)  # 1 opening, 2 chunk-1
    source = ScriptedSource(
        steps=(StreamStep.chunk(first), StreamStep.chunk(second))
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source), records=spy),
        "cmid-p9-2-first-chunk-refused",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    assert [
        (row.state, row.sent_prefix, row.last_chunk_seq, row.terminal_at is None)
        for row in spy.submitted
    ] == [
        ("SENDING", "", 0, True),
        ("SENT_PARTIAL", first, 1, True),  # the released chunk, refused
        ("SENT_PARTIAL", "", 0, False),  # the freeze, on the empty durable half
    ]
    assert source.emitted == [first]  # the chunk left for the client

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_PARTIAL", "", 0)
    assert terminal_at is not None  # frozen, not left open

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is None
    assert canonical.outcome is not None
    assert canonical.outcome.value == "FAILED_USER_VISIBLE"

    assert completion.turn_status is TurnStatus.FAILED_FINAL
    assert completion.assistant_turn_id is None
    assert completion.reply_text is None
    assert completion.delivery_state == "SENT_PARTIAL"
    assert completion.delivery_failure_reason is not None
    assert "record refused the chunk" in completion.delivery_failure_reason
    assert count(world.db, "assistant_turn") == 0


def test_an_ordinary_turn_without_the_record_face_still_streams_and_writes_no_row(
    world: StreamWorld,
) -> None:
    """The port's absence is registered, not simulated: the same turn, the same
    transcript, and **no** §22 row (``delivery_records=None``) — the assembly
    every suite before this cut builds."""

    completion = begin_turn_ok(
        coordinator_(world, records=False), "cmid-p9-2-unwired"
    )
    turn_id = str(completion.turn_id)

    assert count(world.db, "server_delivery_record") == 0
    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == REPLY
    assert canonical.assistant_turn.delivery_state.value == "SENT_COMPLETE"
    assert canonical.outcome is not None
    assert canonical.outcome.value == "REPLIED_FULL"
    assert completion.delivery_state == "SENT_COMPLETE"
    assert completion.delivery_failure_reason is None


def test_a_refused_terminal_write_leaves_the_row_open_and_reports_it(
    world: StreamWorld,
) -> None:
    """The registered divergence, pinned: if the face refuses the **freeze**
    (the last write), the transcript still carries the run's word — the whole
    reply was sent, ``SENT_COMPLETE`` — while the §22 row stays unfrozen at
    ``SENT_PARTIAL`` with no ``terminal_at``. Both facts are true; the
    delivery-failure field is what says so instead of hiding either."""

    spy = RecordingStore(world.deliveries, refuse_at=3)  # opening, chunk-1, freeze
    completion = begin_turn_ok(
        coordinator_(world, records=spy), "cmid-p9-2-freeze-refused"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)

    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_PARTIAL", REPLY, 1)
    assert terminal_at is None  # the row was never frozen

    canonical = slice_of(world, turn_id)
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == REPLY
    assert canonical.assistant_turn.delivery_state.value == "SENT_COMPLETE"
    assert canonical.outcome is not None
    assert canonical.outcome.value == "REPLIED_FULL"
    assert completion.outcome == "REPLIED_FULL"
    assert completion.delivery_state == "SENT_COMPLETE"
    assert completion.delivery_failure_reason is not None
    assert "could not be frozen" in completion.delivery_failure_reason


def test_two_streamed_turns_in_one_conversation_each_get_their_own_row(
    world: StreamWorld,
) -> None:
    """The row is per action, not per conversation: two ordinary turns in the
    same conversation write two rows, each frozen with its own prefix and its
    own chunk count, and each transcript carries its own content."""

    first = begin_turn_ok(coordinator_(world), "cmid-p9-2-first")
    second = begin_turn_ok(coordinator_(world), "cmid-p9-2-second")

    rows = world.db.execute(
        "SELECT action_id, state, sent_prefix, last_chunk_seq FROM"
        " server_delivery_record ORDER BY action_id"
    ).fetchall()
    assert len(rows) == 2
    assert [row[1] for row in rows] == ["SENT_COMPLETE", "SENT_COMPLETE"]
    assert {row[2] for row in rows} == {REPLY}
    assert {row[3] for row in rows} == {1}

    for completion in (first, second):
        canonical = slice_of(world, str(completion.turn_id))
        assert canonical.assistant_turn is not None
        assert canonical.assistant_turn.content == REPLY
    assert first.action_id != second.action_id


def test_a_generation_that_produced_no_reply_writes_no_delivery_row(
    world: StreamWorld,
) -> None:
    """The stream is a *delivery* face: when the provider never produced a
    validated reply, the action ends TERMINAL undelivered and the turn fails
    before any delivery exists — no §22 row, no assistant turn (the boundary
    this cut did not move)."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    coordinator = ConversationCoordinator(
        lease=lease,
        conversation_commands=world.store,
        conversation_queries=world.store,
        persona=PersonaRuntime(
            actions=world.generation,
            provider=ScriptedPersonaProvider(
                script=(ProviderOutput(text=""),)
            ),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=2,
        ),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=world.deliveries,
    )
    completion = begin_turn_ok(coordinator, "cmid-p9-2-no-reply")

    assert completion.reply_text is None
    assert completion.outcome == "FAILED_USER_VISIBLE"
    assert completion.delivery_state is None
    assert count(world.db, "server_delivery_record") == 0
    assert count(world.db, "assistant_turn") == 0
