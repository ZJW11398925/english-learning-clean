"""P9-5 A — the nine promises, **one named test each**.

Phase 9 is the Delivery / Exposure Hardening phase (``docs/IMPLEMENTATION_PLAN.
md`` §10) and its four canonical acceptances are:

- ``partial reveal 不被记为 full exposure``;
- ``no ACK 使用 conservative support``;
- ``barge-in 旧 tail 不进入 transcript``;
- ``late provider result 无副作用``.

The external review of Phase 8/9 read the whole cut and wrote the wider list
this file carries: nine promises, quoted verbatim at the top of each test, so
"the promise is covered" is a fact about a named test rather than a claim in a
report. Every test here drives the **real** chain — the shipped migrations into
a real app.db, the real conversation store, the real generation store, the real
persona runtime, the real §22 record face, the real ledger store and the real
teaching controller — and every test says in its docstring which durable rows
are its evidence. No ``_seed``-shaped helper exists here and the Phase 3
fixture target provider is never imported (the P5-1 red line, held by phases
6/7/8/9).

**What makes each of these a test rather than a restatement** is that a
mutation of the shipped code turns it red; five such mutations were run out of
tree and all five did (receipt ⑨): the sent-level table
(``exposure_reconciliation._sent_level`` / ``covers_the_whole_text``), the
acknowledgment entry (``controller.accept_render_ack``), the streamed
transcript's content (``controller.finalize_streamed_delivery``), the §20 event
id (``exposure.exposure_event_id``) and the buffered face's certainty
(``controller.finalize_delivery``).

Two promises are checked on more than one face on purpose — promise 8's "no
exposure" on the delivery that released nothing, on §15's invalidated delivery
and on the opening that never delivered, and promise 6's "conservative
reconciliation" through both faces the task names (the ordinary loop's
re-entry and the startup line in a new epoch) — because a promise that holds on
one face only is exactly what the review's question was about. Two arms carry a
**registered structural limit** rather than a measured zero (§20's silence on
an ordinary stream: this assembly wires no ledger port there), stated in the
arm's own docstring, because an unmeasurable zero is not evidence. What is not
provable today at all lives in the sibling honesty module
(``test_p9_5_honesty.py``), not in a weaker assertion here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import TurnOutcome
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db import epoch, migrations
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.types import (
    ActionId,
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    Ok,
    Result,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.delivery_records import ClientRenderAck
from elc.runtime.exposure import exposure_event_id
from elc.runtime.exposure_reconciliation import certainty_rank
from elc.runtime.guarded_stream import StreamStep
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    GenerationActionStatus,
    InterruptRequest,
    TurnStatus,
)
from tests.conftest import AssemblyGenerationStore
from tests.phase7.conftest import TARGET_ID, USER
from tests.phase8.conftest import CONV
from tests.phase8.p8_4_world import (
    World,
    acceptance_supply,
    count_events,
    wiring,
)
from tests.phase8.p8_4_world import (
    begin_turn_ok as p8_begin_turn_ok,
)
from tests.phase8.test_p8_4_turn_integration import FailingCommands
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    ScriptedSource,
    SourceFactory,
    StreamWorld,
    action_of,
    begin_turn_ok,
    command,
    coordinator_,
    persona_runtime,
    pieces,
    second_connection_row,
    stream_world,
)
from tests.phase9.test_p9_2_stream_turn import coordinator_ as stream_coordinator
from tests.phase9.test_p9_3_barge_in import (
    InterruptingFactory,
    coordinator_for,
    open_turn_with_action,
    persona_runtime_over,
    second_connection_rows,
    turn_outcome,
    turn_status,
)

__all__ = [
    "MASTERY_TABLES",
    "PROMISES",
    "all_rows",
    "estimate_row",
    "new_epoch_stream_coordinator",
    "rows_of",
    "stream_command",
    "stream_coordinator_with_commands",
    "table_counts",
    "render_ack",
    "teaching_coordinator",
]

#: The nine promises, verbatim, in the order the task states them. Each one is
#: the docstring line of its own test; the honesty module maps them back to the
#: test names and asserts every name resolves.
PROMISES: tuple[str, ...] = (
    "partial ≠ full exposure",
    "no ACK ⇒ SERVER_SENT_UNCONFIRMED",
    "late ACK 只升 certainty 不提 mastery",
    "barge-in 旧尾不入 transcript",
    "cancelled·superseded late callback 零 canonical side effect",
    "action TERMINAL + turn DELIVERING 可保守和解",
    "实际送出 ⇒ exactly one ledger exposure",
    "未送出 ⇒ no exposure",
    "duplicate reconciliation ⇒ 零重复",
)

#: The tables a "mastery" write would land in — the learner state, the Evidence
#: chain and the attempt records (0004/0005/0008) plus the two teaching-side
#: proposals. The full-table diff below covers every table; this list is the
#: *named* half so a reader can see which rows the promise is about without
#: reading the schema. All nine are empty in the teaching world this cut builds
#: (the shipped chain commits no Evidence on an opening delivery), which is why
#: the test's subject is the write set rather than a mastery value: the mutation
#: that makes the acknowledgment write a mastery row is what proves the pin is
#: load-bearing (receipt ⑨).
MASTERY_TABLES: tuple[str, ...] = (
    "learner_target_state",
    "evidence_claim",
    "evidence_group",
    "evidence_commit",
    "evidence_watermark",
    "attempt_record",
    "attempt_evaluation_record",
    "teaching_evidence_proposal",
    "learning_opportunity_record",
)

#: The second conversation promise 1's control arm needs (a full send beside a
#: partial one, in one world).
FULL_CONV = ConversationId("conv-p9-5-full")

#: The instant every acknowledgment in this file carries (§22's ``acked_at``).
ACKED_AT = "2026-09-24T11:00:00+00:00"


# -- the shared builders -------------------------------------------------------


def teaching_coordinator(
    p8world: World,
    *,
    commands: object | None = None,
    persona: object | None = None,
    records: object | None = None,
) -> ConversationCoordinator:
    """The P8-4 automatic-teaching assembly with the §22 face wired.

    The world's own builder wires no ``delivery_records`` port; every estimate
    and every acknowledgment assertion in this file needs one (the shape P9-3's
    and P9-4's teaching suites use). ``commands`` / ``persona`` / ``records``
    replace one face each, for the arms that need a refusal injected.
    """

    runtime = PersonaRuntime(
        actions=p8world.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=p8world.lease,
        conversation_commands=(
            p8world.store if commands is None else commands  # type: ignore[arg-type]
        ),
        conversation_queries=p8world.store,
        persona=runtime if persona is None else persona,  # type: ignore[arg-type]
        generation_actions=p8world.generation,
        decision_cycles=p8world.generation.decision_cycles,
        learning_controller=p8world.learning,
        teaching=p8world.teaching,
        targets=p8world.targets,
        automatic_teaching=wiring(p8world, supply=acceptance_supply()),
        delivery_records=(
            SqliteDeliveryRecordStore(p8world.db, p8world.fence)
            if records is None
            else records  # type: ignore[arg-type]
        ),
    )


def new_epoch_stream_coordinator(
    stream: StreamWorld,
) -> ConversationCoordinator:
    """The next epoch's coordinator over the same file (the startup face's
    shape: fresh stores on a fresh fence, a lease adopted on the new epoch)."""

    fence = epoch.open_runtime_epoch(stream.db)
    store = SqliteConversationStore(stream.db, fence)
    generation = AssemblyGenerationStore(stream.db, fence)
    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(fence.current)
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=store,
        conversation_queries=store,
        persona=PersonaRuntime(
            actions=generation,
            provider=ScriptedPersonaProvider(),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=generation,
        decision_cycles=generation.decision_cycles,
        delivery_records=SqliteDeliveryRecordStore(stream.db, fence),
    )


def stream_command(client_message_id: str):
    """The streamed world's own CP0 command (P9-2's builder)."""

    from tests.phase9.test_p9_2_stream_turn import command as stream_command_

    return stream_command_(client_message_id)


def stream_coordinator_with_commands(stream: StreamWorld, commands: object):
    """The P9-2 coordinator with its command face replaced (the crash harness:
    the first ``terminalize_turn`` is refused, everything else is the real
    chain)."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(stream.fence.current)
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=commands,  # type: ignore[arg-type]
        conversation_queries=stream.store,
        persona=persona_runtime(stream),
        generation_actions=stream.generation,
        decision_cycles=stream.generation.decision_cycles,
        delivery_records=stream.deliveries,
    )


def render_ack(
    action_id: ActionId,
    *,
    seq: int = 1,
    final: bool = True,
    acked_at: str = ACKED_AT,
) -> ClientRenderAck:
    """One §22 acknowledgment for an action (the caller's own act)."""

    return ClientRenderAck(
        action_id=action_id,
        assistant_turn_id=f"aturn-{action_id}",
        rendered_chunk_seq=seq,
        rendered_text_hash=f"hash-{seq}",
        acked_at=acked_at,
        final_rendered=final,
    )


# -- the durable reads ---------------------------------------------------------


def table_counts(db: sqlite3.Connection) -> dict[str, int]:
    """Every table's row count — the diff around a call is how "this wrote
    nothing else" is measured (never predicted from the code)."""

    names = [
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    return {
        name: int(db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        for name in names
    }


def all_rows(
    db: sqlite3.Connection, table: str
) -> tuple[tuple[object, ...], ...]:
    """Every row of one table, in rowid order — content comparison, not a
    count, so an UPDATE is as visible as an INSERT."""

    return tuple(
        tuple(row)
        for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    )


def count_rows(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def rows_of(
    conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    """Rows through the connection given (the phase-8 ``db`` fixture is
    in-memory, so the streamed arms use a real second connection instead —
    ``tests.phase9.test_p9_3_barge_in.second_connection_rows``)."""

    return [tuple(row) for row in conn.execute(sql, params).fetchall()]


def estimate_row(
    conn: sqlite3.Connection, action_id: ActionId
) -> tuple[object, ...]:
    """The §22 estimate's five value columns for one action."""

    rows = rows_of(
        conn,
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure, derivation_reason FROM exposure_estimate"
        " WHERE action_id = ?",
        (str(action_id),),
    )
    assert rows, f"no exposure_estimate row for action {action_id}"
    return rows[0]


# -- promise 1 -----------------------------------------------------------------


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


@pytest.mark.parametrize("kept_cuts", [1, 2])
def test_promise_1_a_partial_send_is_never_recorded_as_full_exposure(
    world: StreamWorld, kept_cuts: int
) -> None:
    """**partial ≠ full exposure** (IP §10 acceptance row 1; RA §14's
    ``宁可低估，不高估``).

    Evidence: two §22 ``exposure_estimate`` rows over one real world — the
    partial arm's (a stream the source stopped after ``kept_cuts`` chunks, its
    ``sent_prefix`` shorter than the validated text) and the full arm's (a
    second conversation, the whole reply released) — plus the two
    ``server_delivery_record`` prefixes they were derived from, read back
    through a connection that is not the writer. The inequality is asserted
    twice: at the derivation, and again after a **final** acknowledgment,
    because a refinement that could reach ``FULL`` on a partial send would put
    the over-claim back one event later. Two cut points, so "partial" cannot be
    a coincidence of one boundary.
    """

    chunks = pieces(REPLY, 3)
    kept = "".join(chunks[:kept_cuts])
    source = ScriptedSource(
        steps=(
            *(StreamStep.chunk(piece) for piece in chunks[:kept_cuts]),
            StreamStep.stopped("the window closed"),
        )
    )
    partial = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source)),
        "cmid-p9-5-partial",
    )
    partial_action = action_of(world, str(partial.turn_id))

    opened = world.store.open_conversation(
        FULL_CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    full_source = ScriptedSource(
        steps=tuple(StreamStep.chunk(piece) for piece in chunks)
    )
    full_result = coordinator_(
        world, transport=SourceFactory(full_source)
    ).begin_turn(command("cmid-p9-5-full", conversation=FULL_CONV))
    assert isinstance(full_result, Ok), full_result
    full_action = action_of(world, str(full_result.value.turn_id))

    # the boundary the two estimates were derived from (second connection)
    partial_state, partial_prefix, partial_seq, _, _ = second_connection_row(
        world, partial_action
    )
    full_state, full_prefix, full_seq, _, _ = second_connection_row(
        world, full_action
    )
    assert (partial_state, partial_seq) == ("SENT_PARTIAL", kept_cuts)
    assert (full_state, full_seq) == ("SENT_COMPLETE", len(chunks))
    assert partial_prefix == kept
    assert len(partial_prefix) < len(full_prefix) == len(REPLY)

    partial_row = estimate_row(world.db, partial_action)
    full_row = estimate_row(world.db, full_action)
    assert partial_row[:4] == (
        "SERVER_SENT_UNCONFIRMED",
        "PARTIAL",
        "PARTIAL",
        "NONE",
    )
    assert full_row[:4] == ("SERVER_SENT_UNCONFIRMED", "FULL", "FULL", "NONE")
    assert "FULL" not in partial_row
    assert partial_row != full_row

    # the transcript of the partial arm follows the same boundary, verbatim
    transcript = second_connection_rows(
        world,
        "SELECT content FROM assistant_turn WHERE turn_id = ?",
        (str(partial.turn_id),),
    )
    assert transcript == [(partial_prefix,)]

    # and a *final* acknowledgment cannot put the over-claim back
    receipt = coordinator_(world).accept_render_ack(
        render_ack(partial_action, seq=partial_seq, final=True)
    )
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is True
    refined_row = estimate_row(world.db, partial_action)
    assert refined_row[0] == "CONFIRMED_RENDERED"
    assert refined_row[1] == "PARTIAL"  # exposure_level, unmoved
    assert refined_row[2] == "PARTIAL"  # max_possible_exposure, unmoved
    assert refined_row[3] == "PARTIAL"  # the sent level, confirmed
    assert "FULL" not in refined_row


# -- promise 2 -----------------------------------------------------------------


@pytest.mark.parametrize("cuts", [1, 3])
def test_promise_2_without_an_ack_the_certainty_stays_server_sent_unconfirmed(
    world: StreamWorld, cuts: int
) -> None:
    """**no ACK ⇒ SERVER_SENT_UNCONFIRMED** (IP §10 acceptance row 2; RA §6's
    "主 Turn 不等待 ClientRenderAck"; RA §14's conservative support).

    Evidence: ``client_render_ack`` holds **no row at all** for the healthy
    turn; ``assistant_turn.delivery_certainty`` spells the unconfirmed word
    (read through a second connection); and the ``exposure_estimate`` row
    carries both halves RA §14's rule reads — ``confirmed_exposure = NONE``
    (nothing was confirmed, so the support must fall back) and
    ``max_possible_exposure`` = the ceiling the derivation reads: the durable
    level, or the released boundary's level when that is higher (reading 11 of
    ``exposure_reconciliation``; this healthy turn releases and records
    everything, so the two agree). The last
    lines are the control that keeps the pin from being vacuous: the same
    column moves the moment one real acknowledgment arrives. Two transports
    (V1's one-chunk default and a three-chunk source), so the pin is about the
    chain rather than about one chunking.
    """

    if cuts == 1:
        coordinator = coordinator_(world)
    else:
        source = ScriptedSource(
            steps=tuple(StreamStep.chunk(piece) for piece in pieces(REPLY, cuts))
        )
        coordinator = coordinator_(world, transport=SourceFactory(source))
    completion = begin_turn_ok(coordinator, "cmid-p9-5-noack")
    action_id = action_of(world, str(completion.turn_id))

    assert count_rows(world.db, "client_render_ack") == 0
    transcript = second_connection_rows(
        world,
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn",
    )
    assert transcript == [(REPLY, "SENT_COMPLETE", "SERVER_SENT_UNCONFIRMED")]

    row = estimate_row(world.db, action_id)
    assert row[0] == "SERVER_SENT_UNCONFIRMED"
    assert row[3] == "NONE"
    assert row[1] == row[2] == "FULL"
    assert row[4] == f"sent {len(REPLY)} of {len(REPLY)} chars; no render ack"

    # the control: the certainty column is movable, so the pin above is a fact
    receipt = coordinator_(world).accept_render_ack(render_ack(action_id))
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is True
    ref = estimate_row(world.db, action_id)
    assert certainty_rank(ref[0]) > certainty_rank(row[0])
    assert (ref[0], ref[3]) == ("CONFIRMED_RENDERED", "FULL")


# -- promise 3 -----------------------------------------------------------------


@pytest.mark.parametrize("final", [True, False])
def test_promise_3_a_late_ack_raises_certainty_only_and_writes_no_mastery(
    db: sqlite3.Connection, p8world: World, final: bool
) -> None:
    """**late ACK 只升 certainty 不提 mastery** (RA §14: "Late ClientRenderAck
    只作为 certainty refinement；V1 默认不 retroactively upgrade committed
    Evidence").

    Evidence: the real ALLOW teaching chain delivers an opening (so the action
    has a §22 estimate and a durable moment), then one acknowledgment is
    accepted. The whole-database count diff around that call is asserted to be
    **exactly one row** (``client_render_ack``); the nine mastery/evidence/
    attempt tables, the transcript, the §20 log and the moment row are compared
    row by row before and after; and the estimate's own columns are read to show
    what *did* move (``certainty`` upward, and ``confirmed_exposure`` to the
    sent level **only** for a final acknowledgment — the two cases below) and
    what did not (``exposure_level``, ``max_possible_exposure``). The nine
    tables are empty in this world — the mutation that makes the acknowledgment
    write a mastery row is what proves the diff is load-bearing (receipt ⑨).
    Reads go through the same connection because the phase-8 fixture's app.db is
    in-memory; the diff, not the connection, is the evidence.
    """

    coordinator = teaching_coordinator(p8world)
    completion = p8_begin_turn_ok(coordinator, "cmid-p9-5-mastery")
    assert completion.action_id is not None
    action_id = completion.action_id

    before_estimate = estimate_row(db, action_id)
    before_counts = table_counts(db)
    before_mastery = {table: all_rows(db, table) for table in MASTERY_TABLES}
    before_transcript = all_rows(db, "assistant_turn")
    before_events = all_rows(db, "planning_ledger_event")
    before_moment = all_rows(db, "teaching_moment")

    receipt = coordinator.accept_render_ack(
        render_ack(action_id, seq=1, final=final)
    )
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is True
    assert receipt.value.note is None
    assert receipt.value.estimate is not None

    after_estimate = estimate_row(db, action_id)
    assert certainty_rank(after_estimate[0]) > certainty_rank(before_estimate[0])
    assert (before_estimate[0], after_estimate[0]) == (
        "SERVER_SENT_UNCONFIRMED",
        "CONFIRMED_RENDERED",
    )
    assert after_estimate[1] == before_estimate[1]  # exposure_level
    assert after_estimate[2] == before_estimate[2]  # max_possible_exposure
    assert before_estimate[3] == "NONE"
    # only a final acknowledgment reaches the sent level; a non-final one
    # confirms the render without confirming the send
    assert after_estimate[3] == ("FULL" if final else "NONE")

    # exactly one row appeared in the whole database, and it is the ACK itself
    diff = {
        table: count_after
        for table, count_after in table_counts(db).items()
        if count_after != before_counts[table]
    }
    assert diff == {"client_render_ack": before_counts["client_render_ack"] + 1}
    assert before_counts["client_render_ack"] == 0

    for table in MASTERY_TABLES:
        assert all_rows(db, table) == before_mastery[table], table
    assert all_rows(db, "assistant_turn") == before_transcript
    assert all_rows(db, "planning_ledger_event") == before_events
    assert all_rows(db, "teaching_moment") == before_moment
    assert count_events(db) == 1  # the delivery's own, unmoved

    # and the row that did appear is the acknowledgment's own key
    assert rows_of(
        db,
        "SELECT action_id, rendered_chunk_seq, final_rendered"
        " FROM client_render_ack",
    ) == [(str(action_id), 1, int(final))]


# -- promise 4 -----------------------------------------------------------------


@pytest.mark.parametrize("kept_chunks", [1, 2])
def test_promise_4_the_unsent_tail_of_a_barge_in_is_nowhere_in_the_transcript(
    world: StreamWorld, kept_chunks: int
) -> None:
    """**barge-in 旧尾不入 transcript** (IP §10 acceptance row 3; RA §17 "不自动
    从头重放" + §18's sequence).

    Evidence: ``server_delivery_record`` (``CANCELLED`` with the kept prefix and
    the chunk sequence), ``assistant_turn``'s single ``content`` — equal to that
    prefix **verbatim** — and, the load-bearing half, a scan of **every**
    ``assistant_turn`` row in the table with ``instr(content, ?)`` for the
    unsent tail (and for the whole validated reply): both answer zero, so "the
    tail is nowhere" is a statement about the table rather than about one row.
    Two cut points, so "the prefix" cannot be a coincidence of one chunk.
    """

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(
        world=world, chunks=chunks, after_chunks=kept_chunks
    )
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-5-barge"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)
    kept = "".join(chunks[:kept_chunks])
    tail = REPLY[len(kept) :]
    assert tail and tail != REPLY

    assert factory.source is not None
    assert factory.source.requested, "the source never wrote its interrupt"
    assert factory.source.emitted == list(chunks[:kept_chunks])

    state, prefix, sequence, _, _ = second_connection_row(world, action_id)
    assert (state, prefix, sequence) == ("CANCELLED", kept, kept_chunks)
    assert completion.outcome == "CANCELLED_BY_USER"

    transcript = second_connection_rows(world, "SELECT content FROM assistant_turn")
    assert transcript == [(prefix,)]
    assert tail not in prefix
    # the tail of the old stream is in no row of the transcript
    assert second_connection_rows(
        world,
        "SELECT COUNT(*) FROM assistant_turn WHERE instr(content, ?) > 0",
        (tail,),
    ) == [(0,)]
    assert second_connection_rows(
        world,
        "SELECT COUNT(*) FROM assistant_turn WHERE instr(content, ?) > 0",
        (REPLY,),
    ) == [(0,)]
    assert completion.reply_text == prefix == kept
    assert turn_status(world, turn_id) == TurnStatus.CANCELLED_BY_USER.value


# -- promise 5 -----------------------------------------------------------------


@pytest.mark.parametrize("late_kind", ["provider_result", "render_ack"])
def test_promise_5_a_late_callback_after_cancellation_leaves_no_canonical_side_effect(
    world: StreamWorld, late_kind: str
) -> None:
    """**cancelled·superseded late callback 零 canonical side effect** (IP §10
    acceptance row 4 "late provider result 无副作用"; §22's "cancelled/
    superseded late callback ignore").

    Two terminal shapes in one world, both reached by the shipped faces: a
    **cancelled** delivery (a barge-in stopped the stream after one chunk) and a
    **superseded** one (a stale turn re-entered after a newer reply, which §15
    invalidates). Evidence: a snapshot of ``assistant_turn`` / ``turn_record`` /
    ``generation_action_intent`` / ``server_delivery_record`` /
    ``exposure_estimate`` / ``pre_delivery_guard_result`` / the §20 log, taken
    before and after the late callbacks, each read through a connection that is
    not the writer. The snapshot is equal, and the two entries are told apart by
    their own write set: a late **provider result** writes *nothing at all*
    (the count diff is empty), while a late **render acknowledgment** lands its
    own row and refinable estimate — and neither touches a canonical row, and
    no estimate is minted for an action whose delivery never reached CP3a.
    """

    chunks = pieces(REPLY, 3)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=1)
    cancelled = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p9-5-late-cancelled"
    )
    cancelled_action = action_of(world, str(cancelled.turn_id))

    stale_turn, stale_action = open_turn_with_action(world, "cmid-p9-5-stale")
    later = begin_turn_ok(coordinator_for(world), "cmid-p9-5-later")
    superseded = begin_turn_ok(coordinator_for(world), "cmid-p9-5-stale")
    assert str(superseded.turn_id) == str(stale_turn)
    assert str(later.turn_id) != str(stale_turn)

    # both shapes are terminal, and neither reached the transcript
    assert (
        turn_status(world, str(cancelled.turn_id))
        == TurnStatus.CANCELLED_BY_USER.value
    )
    assert turn_status(world, str(stale_turn)) == TurnStatus.CANCELLED_BY_USER.value
    assert second_connection_row(world, stale_action)[0:3] == (
        "CANCELLED",
        "",
        0,
    )
    # the superseded turn never reached the transcript …
    assert second_connection_rows(
        world,
        "SELECT content FROM assistant_turn WHERE turn_id = ?",
        (str(stale_turn),),
    ) == []
    # … and the cancelled one reached it only as its durable prefix
    kept = pieces(REPLY, 3)[0]
    assert second_connection_rows(
        world,
        "SELECT content FROM assistant_turn WHERE turn_id = ?",
        (str(cancelled.turn_id),),
    ) == [(kept,)]
    for action_id in (cancelled_action, stale_action):
        # neither cancellation reached CP3a, so neither has an estimate at all
        assert second_connection_rows(
            world,
            "SELECT COUNT(*) FROM exposure_estimate WHERE action_id = ?",
            (str(action_id),),
        ) == [(0,)]

    before = canonical_snapshot(world)
    before_counts = table_counts(world.db)

    coordinator = coordinator_for(world)

    def late_result(action_id: ActionId) -> Result[str]:
        return coordinator.accept_late_result(
            action_id, "the tail that never came"
        )

    def late_ack(action_id: ActionId) -> Result[object]:
        return coordinator.accept_render_ack(render_ack(action_id))

    for action_id in (cancelled_action, stale_action):
        # a provider result for a terminal action: an audit verdict, no more
        verdict = late_result(action_id)
        assert isinstance(verdict, Ok), verdict
        assert verdict.value == "DISCARDED_TERMINAL_ACTION"
        if late_kind == "render_ack":
            # an acknowledgment whose delivery never reached CP3a refines
            # nothing and mints no estimate (the entry never invents one)
            receipt = late_ack(action_id)
            assert isinstance(receipt, Ok), receipt
            assert receipt.value.refined is False
            assert receipt.value.estimate is None
            assert "no exposure estimate" in (receipt.value.note or "")

    assert canonical_snapshot(world) == before
    diff = {
        table: after
        for table, after in table_counts(world.db).items()
        if after != before_counts[table]
    }
    assert diff == ({} if late_kind == "provider_result" else {"client_render_ack": 2})
    assert before_counts["client_render_ack"] == 0
    # both turns keep the word their cancellation gave them, unmoved by the
    # late callbacks (the snapshot above already says the rows are identical)
    for turn_id in (str(cancelled.turn_id), str(stale_turn)):
        assert turn_outcome(world, turn_id) == TurnOutcome.CANCELLED_BY_USER.value


def canonical_snapshot(world: StreamWorld) -> dict[str, object]:
    """Every canonical fact a late callback could move, in one place.

    ``client_render_ack`` is deliberately **not** in here: an acknowledgment
    is the client's own act and lands as its own row, so it is measured by the
    table-count diff beside the snapshot rather than being smuggled into the
    "nothing moved" comparison.
    """

    return {
        "transcript": second_connection_rows(
            world,
            "SELECT turn_id, content, delivery_state, delivery_certainty"
            " FROM assistant_turn ORDER BY turn_id",
        ),
        "turns": second_connection_rows(
            world,
            "SELECT turn_id, status, turn_outcome FROM turn_record"
            " ORDER BY turn_id",
        ),
        "actions": second_connection_rows(
            world,
            "SELECT action_id, status FROM generation_action_intent"
            " ORDER BY action_id",
        ),
        "delivery_rows": second_connection_rows(
            world,
            "SELECT action_id, state, sent_prefix, last_chunk_seq"
            " FROM server_delivery_record ORDER BY action_id",
        ),
        "estimates": second_connection_rows(
            world,
            "SELECT action_id, certainty, exposure_level,"
            " max_possible_exposure, confirmed_exposure, derivation_reason"
            " FROM exposure_estimate ORDER BY action_id",
        ),
        "guard_rows": second_connection_rows(
            world,
            "SELECT action_id, decision, reason_codes FROM"
            " pre_delivery_guard_result ORDER BY action_id, created_at",
        ),
        "events": second_connection_rows(
            world,
            "SELECT event_id, event, moment_id FROM planning_ledger_event"
            " ORDER BY event_id",
        ),
    }


# -- promise 6 -----------------------------------------------------------------


@pytest.mark.parametrize("face", ["loop", "startup"])
def test_promise_6_a_terminal_action_over_a_delivering_turn_reconciles_conservatively(
    tmp_path: Path, face: str
) -> None:
    """**action TERMINAL + turn DELIVERING 可保守和解** (RA §23's CP3 window;
    RA §22's "idempotent" scan).

    The residue is built by the shipped harness (the first ``terminalize_turn``
    is refused), and both halves of the promise are asserted on the durable rows
    before anything reconciles: ``generation_action_intent.status = TERMINAL``
    **and** ``turn_record.status = DELIVERING`` with the §22 row frozen and the
    transcript already canonical. Evidence: the crash window's own rows read
    through a second connection, plus the whole-database count diff around each
    reconciliation, the transcript's rows and the estimate's rows. Two faces
    then finish it — the ordinary
    loop's re-entry (a duplicate ``client_message_id``) and the startup line in
    a **new epoch** — and "conservatively" is measured, not claimed: the
    whole-database count diff around the call is empty, the transcript and the
    estimate are byte-identical, and the outcome the turn takes is the
    transcript's own. Each arm takes its count baseline **after** its own
    coordinator exists, so the new epoch's own row is not counted as a diff.
    """

    stream = stream_world(tmp_path)
    failing = FailingCommands(stream.store)
    crashed = stream_coordinator_with_commands(stream, failing).begin_turn(
        stream_command("cmid-p9-5-cp3")
    )
    assert not isinstance(crashed, Ok), crashed
    assert failing.failed is True

    found = second_connection_rows(
        stream,
        "SELECT turn_id FROM turn_record WHERE status = 'DELIVERING'",
    )
    assert len(found) == 1
    turn_id = str(found[0][0])
    action_id = action_of(stream, turn_id)
    action = stream.generation.get_action(action_id)
    assert isinstance(action, Ok) and action.value is not None
    assert action.value.status is GenerationActionStatus.TERMINAL
    assert turn_status(stream, turn_id) == TurnStatus.DELIVERING.value
    assert turn_outcome(stream, turn_id) is None
    assert second_connection_row(stream, action_id)[0] == "SENT_COMPLETE"
    assert second_connection_rows(
        stream,
        "SELECT COUNT(*) FROM assistant_turn WHERE turn_id = ?",
        (turn_id,),
    ) == [(1,)]

    transcript_before = all_rows(stream.db, "assistant_turn")
    estimate_before = all_rows(stream.db, "exposure_estimate")

    if face == "loop":
        coordinator = stream_coordinator(stream)
    else:
        coordinator = new_epoch_stream_coordinator(stream)
    counts_before = table_counts(stream.db)

    if face == "loop":
        reconciled = begin_turn_ok(coordinator, "cmid-p9-5-cp3")
        assert str(reconciled.turn_id) == turn_id
        assert reconciled.outcome == "REPLIED_FULL"
        assert reconciled.delivery_state == "SENT_COMPLETE"
        assert reconciled.ledger_event is None  # an ordinary turn owes no §20 word
        assert reconciled.ledger_failure is None
    else:
        outcome = coordinator.run_startup_recovery()
        assert isinstance(outcome, Ok), outcome
        assert len(outcome.value.reconciled_turns) == 1
        record = outcome.value.reconciled_turns[0]
        assert record.turn_id == turn_id
        assert record.outcome == "REPLIED_FULL"
        assert record.repaired_transcript is False
        assert record.wrote_exposure is False  # nothing teaching was presented
        assert record.failure_reason is None

    assert (turn_status(stream, turn_id), turn_outcome(stream, turn_id)) == (
        TurnStatus.COMPLETED.value,
        "REPLIED_FULL",
    )
    assert table_counts(stream.db) == counts_before  # not one new row
    assert all_rows(stream.db, "assistant_turn") == transcript_before
    assert all_rows(stream.db, "exposure_estimate") == estimate_before

    # and a duplicate reconciliation over the same finished turn writes nothing
    again = coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.reconciled_turns == ()
    assert table_counts(stream.db) == counts_before


# -- promise 7 -----------------------------------------------------------------


def test_promise_7_a_presented_teaching_action_owes_exactly_one_exposure_event(
    db: sqlite3.Connection, p8world: World
) -> None:
    """**实际送出 ⇒ exactly one ledger exposure** (RA §20's
    ``teaching_presented``; §20's "``SELECT != exposure``").

    Evidence: the real ALLOW teaching chain presents one opening, and the
    ``planning_ledger_event`` table holds **one** row — with the deterministic
    id ``ev-<action_id>`` (the §20 write's own id function), the word
    ``teaching_presented``, the moment in the 0017 provenance column and the
    moment's own target as the ledger key. The count is asserted both as the
    table's whole population and as a keyed lookup, so "exactly one" is a fact
    about that event id rather than about a total.
    """

    coordinator = teaching_coordinator(p8world)
    completion = p8_begin_turn_ok(coordinator, "cmid-p9-5-exactly-one")
    assert completion.action_id is not None
    action_id = completion.action_id
    assert completion.ledger_event == "teaching_presented"
    assert completion.ledger_failure is None

    assert count_rows(db, "planning_ledger_event") == 1
    events = all_rows(db, "planning_ledger_event")
    assert len(events[0]) == 5  # 0016's four columns + 0017's provenance
    # the id is the **deterministic spelling**, asserted as a literal, not only
    # through the function that mints it (mutation M4 in receipt ⑨)
    assert exposure_event_id(action_id) == f"ev-{action_id}"
    assert events[0][0] == f"ev-{action_id}"
    assert events[0][2] == "teaching_presented"

    moment_id, focus_document = db.execute(
        "SELECT moment_id, focus_target FROM teaching_moment"
    ).fetchone()
    assert events[0][4] == str(moment_id)  # the provenance column
    focus = json.loads(str(focus_document))
    assert focus["target_id"] == str(TARGET_ID)
    assert events[0][1] == focus["target_id"]  # the ledger key is that target
    assert rows_of(
        db,
        "SELECT COUNT(*) FROM planning_ledger_event WHERE event_id = ?",
        (exposure_event_id(action_id),),
    ) == [(1,)]


# -- promise 8 -----------------------------------------------------------------


class RefusingPersona:
    """The real persona runtime over one world, with its first ``run_action``
    refused — the delivery never happened while CP2 already did."""

    def __init__(self, p8world: World) -> None:
        self._inner = PersonaRuntime(
            actions=p8world.generation,
            provider=ScriptedPersonaProvider(),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        )
        self.refused = False

    def run_action(self, *args: object, **kwargs: object):
        if not self.refused:
            self.refused = True
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="injected delivery crash",
                )
            )
        return self._inner.run_action(*args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


def crash_world(tmp_path: Path):
    """A file-backed app.db plus the P8-4 world over it (the p9-4 shape, built
    as a plain function so a parametrized body can ask for it)."""

    from elc.platform.db import connection
    from tests.phase8.p8_4_world import build_content
    from tests.phase8.p8_4_world import world as p8_world
    from tests.phase9.test_p9_4_crash_windows import CrashWorld

    path = tmp_path / "app.db"
    db = connection.connect(path)
    migrations.apply_migrations(db)
    fence = epoch.open_runtime_epoch(db)
    content_path = build_content(tmp_path / "content.db")
    return CrashWorld(
        path=path,
        content_path=content_path,
        db=db,
        fence=fence,
        world=p8_world(db, fence, content_path),
    )


@pytest.mark.parametrize(
    "arm", ["released_nothing", "invalidated", "never_delivered"]
)
def test_promise_8_a_delivery_that_sent_nothing_claims_no_exposure(
    tmp_path: Path, arm: str
) -> None:
    """**未送出 ⇒ no exposure** (RA §14's floor; §20's "CoverageDebt 不因
    selection 自动偿还").

    "No exposure" in the durable spelling is stated by the rows, not by their
    absence: an estimate row whose three level columns are all ``NONE`` — or,
    where the cancellation faces never reached CP3a at all, **no** estimate row
    — and a §20 log with no row naming the action. Evidence: the §22 row's own
    state and prefix, the estimate's five columns, the §21.1 verdict, the §20
    log's count and the transcript's count, each read through a connection that
    is not the writer. Three arms, each reached by a shipped face:

    - ``released_nothing`` — a source that ends before its first chunk; CP3a
      still records the attempt (``NONE``/``NONE``/``NONE``), the §22 row
      freezes ``FAILED`` and no transcript row exists;
    - ``invalidated`` — §15's guard refuses the delivery before the first
      release; the §22 row freezes ``CANCELLED`` with an empty prefix and
      neither an estimate nor a transcript row is written;
    - ``never_delivered`` — an authorized opening (CP2 ``OPENING``, its lock
      held) whose delivery never happened; the startup line closes it through
      §7's abort walk with no estimate and **no §20 event** — and that last
      zero is measured, not structural: this arm's assembly does wire the
      ledger port (``crash_teaching_coordinator``'s bundle), so a write would
      have landed. The two streamed arms' §20 silence is structural instead —
      ``coordinator_for`` wires no ledger port — and is registered here rather
      than dressed up as a measurement.
    """

    if arm == "never_delivered":
        from tests.phase9.test_p9_4_crash_windows import (
            _command,
            _moment_state,
            new_epoch_coordinator,
        )
        from tests.phase9.test_p9_4_crash_windows import (
            teaching_coordinator as crash_teaching_coordinator,
        )

        world_ = crash_world(tmp_path)
        refusing = RefusingPersona(world_.world)
        crashed = crash_teaching_coordinator(world_, persona=refusing).begin_turn(
            _command("cmid-p9-5-never")
        )
        assert not isinstance(crashed, Ok), crashed
        assert refusing.refused is True
        assert _moment_state(world_) == ("OPENING", None)
        assert count_rows(world_.db, "active_teaching_lock") == 1
        assert count_rows(world_.db, "assistant_turn") == 0
        assert count_rows(world_.db, "exposure_estimate") == 0
        assert count_events(world_.db) == 0

        outcome = new_epoch_coordinator(world_).run_startup_recovery()
        assert isinstance(outcome, Ok), outcome
        assert len(outcome.value.aborted_openings) == 1
        assert _moment_state(world_) == ("CLOSED", "DELIVERY_FAILURE")
        assert count_rows(world_.db, "active_teaching_lock") == 0
        assert count_rows(world_.db, "exposure_estimate") == 0
        assert count_events(world_.db) == 0
        return

    stream = stream_world(tmp_path)
    if arm == "released_nothing":
        source = ScriptedSource(steps=(StreamStep.stopped("the window closed"),))
        completion = begin_turn_ok(
            coordinator_(stream, transport=SourceFactory(source)),
            "cmid-p9-5-nothing",
        )
        action_id = action_of(stream, str(completion.turn_id))
        assert completion.assistant_turn_id is None
        assert second_connection_row(stream, action_id)[0:3] == (
            "FAILED",
            "",
            0,
        )
        row = estimate_row(stream.db, action_id)
        assert row[:4] == (
            "SERVER_SENT_UNCONFIRMED",
            "NONE",
            "NONE",
            "NONE",
        )
        assert row[4] == "nothing was sent; the delivery failed; no render ack"
    else:
        # §15's ``action cancelled`` carrier: a nonterminal action named by a
        # durable interrupt, a new epoch adopting the work, and the guard — not
        # the stream — is what stops it (P9-3's own recipe).
        turn_id, action_id = open_turn_with_action(
            stream, "cmid-p9-5-invalidated"
        )
        fence2 = epoch.open_runtime_epoch(stream.db)
        lease2 = ConversationCoordinatorLease()
        lease2.adopt_epoch(fence2)
        store2 = SqliteConversationStore(stream.db, fence2)
        generation2 = AssemblyGenerationStore(stream.db, fence2)
        coordinator2 = ConversationCoordinator(
            lease=lease2,
            conversation_commands=store2,
            conversation_queries=store2,
            persona=persona_runtime_over(generation2),
            generation_actions=generation2,
            decision_cycles=generation2.decision_cycles,
            delivery_records=SqliteDeliveryRecordStore(stream.db, fence2),
        )
        requested = coordinator2.request_interrupt(
            InterruptRequest(
                input_id=InputId("in-p9-5-invalidated"),
                conversation_id=str(CONV),
                active_turn_id=turn_id,
                active_action_id=action_id,
                reason="cancel this one",
            )
        )
        assert isinstance(requested, Ok), requested

        completion = begin_turn_ok(coordinator2, "cmid-p9-5-invalidated")
        assert completion.turn_id == turn_id
        assert completion.assistant_turn_id is None
        # the guard's own row says the delivery was refused before any release
        assert second_connection_rows(
            stream,
            "SELECT decision FROM pre_delivery_guard_result WHERE action_id = ?",
            (str(action_id),),
        ) == [("INVALIDATE_ACTION",)]
        assert second_connection_row(stream, action_id)[0:3] == (
            "CANCELLED",
            "",
            0,
        )
        # the cancellation face never reached CP3a: no estimate row at all
        assert second_connection_rows(
            stream,
            "SELECT COUNT(*) FROM exposure_estimate WHERE action_id = ?",
            (str(action_id),),
        ) == [(0,)]

    assert count_rows(stream.db, "assistant_turn") == 0


# -- promise 9 -----------------------------------------------------------------


def test_promise_9_duplicate_reconciliation_writes_no_duplicate(
    tmp_path: Path,
) -> None:
    """**duplicate reconciliation ⇒ 零重复** (RA §22's idempotent scan; §20's
    deterministic event id).

    Evidence: a CP3 residue whose §20 event the cut-short leg never wrote (the
    delivered opening, ``action TERMINAL``, ``moment OPENING``, event count
    zero). The loop's re-entry writes it **once**; a **second** re-entry over
    the same finished turn appends nothing at all; and the startup line in a
    new epoch finds no turn left to name. The event row's id is asserted at
    every pass — as the row's own column, asserted against the literal, on the
    first one, and as the same literal ``ev-<action_id>`` in a keyed
    ``COUNT(*)`` on each replay after it — so "no duplicate" is a statement
    about the deterministic id the store replays against rather than about a
    count alone.
    """

    from tests.phase9.test_p9_4_crash_windows import (
        _command,
        _moment_state,
        _turn,
        new_epoch_coordinator,
    )
    from tests.phase9.test_p9_4_crash_windows import (
        teaching_coordinator as crash_teaching_coordinator,
    )

    world_ = crash_world(tmp_path)
    commands = FailingCommands(world_.world.store)
    crashed = crash_teaching_coordinator(world_, commands=commands).begin_turn(
        _command("cmid-p9-5-duplicate")
    )
    assert not isinstance(crashed, Ok), crashed
    assert commands.failed is True
    turn_id = str(
        world_.db.execute(
            "SELECT turn_id FROM turn_record WHERE status = 'DELIVERING'"
        ).fetchone()[0]
    )
    action = world_.db.execute(
        "SELECT action_id, moment_id FROM generation_action_intent"
    ).fetchone()
    assert action is not None
    action_id = ActionId(str(action[0]))
    moment_id = str(action[1])
    assert count_events(world_.db) == 0  # the leg never wrote it
    assert _moment_state(world_) == ("OPENING", None)
    assert count_rows(world_.db, "exposure_estimate") == 1

    counts_before = table_counts(world_.db)
    first = crash_teaching_coordinator(world_).begin_turn(
        _command("cmid-p9-5-duplicate")
    )
    assert isinstance(first, Ok), first
    assert str(first.value.turn_id) == turn_id
    assert first.value.ledger_event == "teaching_presented"
    assert first.value.ledger_failure is None
    assert count_events(world_.db) == 1
    event = all_rows(world_.db, "planning_ledger_event")
    # the deterministic spelling, as a literal (mutation M4 in receipt ⑨)
    assert exposure_event_id(action_id) == f"ev-{action_id}"
    assert event[0][0] == f"ev-{action_id}"
    assert event[0][2] == "teaching_presented"
    assert event[0][4] == moment_id
    assert _turn(world_.db, turn_id) == ("COMPLETED", "REPLIED_FULL")
    counts_after_first = table_counts(world_.db)
    assert count_rows(world_.db, "planning_ledger_event") == 1
    assert (
        counts_after_first["planning_ledger"]
        == counts_before["planning_ledger"] + 1
    )

    # the duplicate reconciliation: the same re-entry, the same turn, no write
    again = crash_teaching_coordinator(world_).begin_turn(
        _command("cmid-p9-5-duplicate")
    )
    assert isinstance(again, Ok), again
    assert str(again.value.turn_id) == turn_id
    # the replay claims no new §20 event (nothing was written) and the log
    # still holds the one the first pass wrote
    assert again.value.ledger_event is None
    assert table_counts(world_.db) == counts_after_first
    assert count_events(world_.db) == 1
    # looked up by the same literal key, not only counted: exactly one row,
    # so the second pass checks the deterministic spelling too
    assert rows_of(
        world_.db,
        "SELECT COUNT(*) FROM planning_ledger_event WHERE event_id = ?",
        (f"ev-{action_id}",),
    ) == [(1,)]

    # the startup line in a new epoch: the turn is already reconciled, so the
    # only residue left is the delivered opening's own lock — the sweep's, not
    # this line's (the exposure event is *not* re-attempted by either)
    startup = new_epoch_coordinator(world_)
    first_pass = startup.run_startup_recovery()
    assert isinstance(first_pass, Ok), first_pass
    assert first_pass.value.reconciled_turns == ()
    assert first_pass.value.aborted_openings == ()
    assert _moment_state(world_) == ("CLOSED", "SYSTEM_RECOVERY_ABORT")
    assert count_rows(world_.db, "active_teaching_lock") == 0
    assert count_rows(world_.db, "planning_ledger_event") == 1
    # the startup pass names no turn and touches no §20 event — and the one
    # event the loop's first pass wrote is still there under its literal key
    assert rows_of(
        world_.db,
        "SELECT COUNT(*) FROM planning_ledger_event WHERE event_id = ?",
        (f"ev-{action_id}",),
    ) == [(1,)]
    counts_after_startup = table_counts(world_.db)

    # the duplicate pass has an empty plan and writes nothing at all
    second = startup.run_startup_recovery()
    assert isinstance(second, Ok), second
    assert second.value.reconciled_turns == ()
    assert second.value.aborted_openings == ()
    assert second.value.plan == ()
    assert table_counts(world_.db) == counts_after_startup
    assert count_rows(world_.db, "planning_ledger_event") == 1
    assert rows_of(
        world_.db,
        "SELECT COUNT(*) FROM planning_ledger_event WHERE event_id = ?",
        (f"ev-{action_id}",),
    ) == [(1,)]
    assert count_rows(world_.db, "assistant_turn") == 1
    assert count_rows(world_.db, "exposure_estimate") == 1
    assert count_rows(world_.db, "client_render_ack") == 0
