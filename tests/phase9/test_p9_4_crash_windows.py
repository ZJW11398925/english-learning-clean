"""P9-4 ③ — the two crash windows, conservatively reconciled.

Two durable residues the shipped faces could not finish, each built through the
real chain (a file-backed app.db so a *new epoch* can take over, no
``_seed``-shaped helper), and each asserted on the durable rows rather than on
the returned objects:

**① the CP3 under-record** — the delivery leg finished (the action is
``TERMINAL``, the transcript is canonical for a teaching opening) and the crash
ate the turn's terminalization, so the turn sits at ``DELIVERING``. Two faces
are exercised, because the task fixes both:

- the ordinary loop's re-entry (a duplicate ``client_message_id``): it used to
  answer ``CONFLICT``. On a *streamed* turn everything the repair owes is
  already durable, so the reconciliation writes nothing but the turn's
  terminalization — the count diff around the call is empty, and the transcript
  and estimate rows are byte-identical. On a *teaching* turn the §20 event is
  what the cut-short leg never wrote, and the repair writes it exactly once;
- the startup face in a **new epoch**: the same residue, finished from the
  plan's own TURN item, with ``reconciled_turns`` naming it. A second pass
  writes nothing at all;
- the *repaired transcript* arm: a streamed residue whose CP3a half is missing
  (no ``assistant_turn`` row and no estimate) is rebuilt from the durable §22
  row — the prefix verbatim as ``SENT_PARTIAL``, the estimate from that row's
  own word — and repeating the pass changes nothing.

**② the CP2 ``OPENING`` residue** — the authorized opening ($\\S9$'s ``OPENING``
slot, its lock held) whose delivery never happened: the crash between CP2 and
the delivery, and the degraded leg P8-4 registered. The startup line closes it
through the §7 abort walk with ``DELIVERY_FAILURE`` (the word the live faces use
for an opening that was never presented), releases the lock, and writes **no**
estimate and **no** §20 event (nothing was sent). The control beside it is the
delivered opening: the line must leave it alone, and the sweep closes it with
its own word — so "the delivered case is not stolen" is asserted, not assumed.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from elc.conversation import SqliteConversationStore
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.planner.ledger_store import SqliteLedgerStore
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import ActionId, Ok
from elc.runtime import ConversationCoordinator
from elc.runtime.automatic_turn import AutomaticTurnWiring
from elc.runtime.guarded_stream import StreamStep
from elc.runtime.lease import ConversationCoordinatorLease
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from tests.conftest import AssemblyGenerationStore
from tests.phase8.p8_4_world import (
    World,
    acceptance_supply,
    build_content,
    count_events,
    wiring,
)
from tests.phase8.p8_4_world import world as p8_world
from tests.phase8.test_p8_4_turn_integration import (
    FailingCommands,
    RefusingPersona,
)
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    ScriptedSource,
    SourceFactory,
    StreamWorld,
    action_of,
    begin_turn_ok,
    pieces,
    stream_world,
)
from tests.phase9.test_p9_2_stream_turn import (
    coordinator_ as stream_coordinator,
)

# -- the shared worlds ---------------------------------------------------------


@dataclass(frozen=True)
class CrashWorld:
    """A file-backed app.db plus the P8-4 world over it (the p9-3 shape)."""

    path: Path
    content_path: Path
    db: sqlite3.Connection
    fence: RuntimeEpochFence
    world: World


@pytest.fixture()
def crash_world(tmp_path: Path) -> CrashWorld:
    path = tmp_path / "app.db"
    db = connection.connect(path)
    migrations.apply_migrations(db)
    fence = epoch.open_runtime_epoch(db)
    content_path = build_content(tmp_path / "content.db")
    built = CrashWorld(
        path=path,
        content_path=content_path,
        db=db,
        fence=fence,
        world=p8_world(db, fence, content_path),
    )
    yield built
    db.close()


@pytest.fixture()
def stream(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


def teaching_coordinator(
    cw: CrashWorld,
    *,
    persona: object | None = None,
    commands: object | None = None,
    records: object | None = None,
) -> ConversationCoordinator:
    """The P8-4 assembly over the fixture's own stores, with the ledger wired
    (the wiring's other faces absent on purpose: the reconciliation reads the
    ledger and the §22 face, nothing else)."""

    runtime = PersonaRuntime(
        actions=cw.world.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=cw.world.lease,
        conversation_commands=(
            cw.world.store if commands is None else commands
        ),
        conversation_queries=cw.world.store,
        persona=runtime if persona is None else persona,
        generation_actions=cw.world.generation,
        decision_cycles=cw.world.generation.decision_cycles,
        learning_controller=cw.world.learning,
        teaching=cw.world.teaching,
        targets=cw.world.targets,
        automatic_teaching=wiring(cw.world, supply=acceptance_supply()),
        delivery_records=(
            SqliteDeliveryRecordStore(cw.db, cw.fence)
            if records is None
            else records  # type: ignore[arg-type]
        ),
    )


def new_epoch_coordinator(cw: CrashWorld) -> ConversationCoordinator:
    """The next epoch's coordinator over the same file: fresh stores on a fresh
    fence, a lease adopted on the new epoch, and the minimal ledger wiring the
    reconciliation reads (the startup face's own shape)."""

    fence = epoch.open_runtime_epoch(cw.db)
    store = SqliteConversationStore(cw.db, fence)
    generation = AssemblyGenerationStore(cw.db, fence)
    teaching = TeachingController(SqliteTeachingStore(cw.db, fence))
    learning = LearningController(SqliteLearningStore(cw.db, fence))
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
        learning_controller=learning,
        teaching=teaching,
        targets=cw.world.targets,
        automatic_teaching=AutomaticTurnWiring(
            planner_store=SqlitePlannerRecordStore(cw.db, fence),
            teaching=teaching,
            ledger=SqliteLedgerStore(cw.db, fence),
        ),
        delivery_records=SqliteDeliveryRecordStore(cw.db, fence),
    )


def _table_counts(db: sqlite3.Connection) -> dict[str, int]:
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


def _turn(db: sqlite3.Connection, turn_id: str) -> tuple[str, str | None]:
    row = db.execute(
        "SELECT status, turn_outcome FROM turn_record WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert row is not None
    return (str(row[0]), None if row[1] is None else str(row[1]))


def _moment_state(cw: CrashWorld) -> tuple[str, str | None]:
    row = cw.db.execute(
        "SELECT lifecycle_state, abort_reason FROM teaching_moment"
    ).fetchone()
    assert row is not None
    return (str(row[0]), None if row[1] is None else str(row[1]))


def _crash_after_cp3(cw: CrashWorld) -> tuple[str, ActionId, str]:
    """One automatic opening delivered, the turn left at ``DELIVERING``.

    The refusal is the shipped p8-4 harness (the first ``terminalize_turn`` is
    refused), so the residue is the real one: the assistant turn is canonical
    (a teaching opening's own action), the action is ``TERMINAL``, the estimate
    is written (the buffered face writes it before the terminalization), the
    moment is still ``OPENING`` with its lock, and the §20 event the leg owed
    was never written. Returns ``(turn_id, action_id, moment_id)``.
    """

    commands = FailingCommands(cw.world.store)
    crashed = teaching_coordinator(cw, commands=commands).begin_turn(
        _command("cmid-p9-4-cp3")
    )
    assert not isinstance(crashed, Ok), crashed
    assert commands.failed is True
    row = cw.db.execute(
        "SELECT turn_id FROM turn_record WHERE status = 'DELIVERING'"
    ).fetchone()
    assert row is not None
    turn_id = str(row[0])
    action = cw.db.execute(
        "SELECT action_id, moment_id FROM generation_action_intent"
    ).fetchone()
    assert action is not None
    assert cw.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 1
    assert count_events(cw.db) == 0
    assert _moment_state(cw) == ("OPENING", None)
    return (turn_id, ActionId(str(action[0])), str(action[1]))


def _command(client_message_id: str):
    from tests.phase8.p8_4_world import command

    return command(client_message_id)


# -- ① the CP3 under-record: the ordinary loop's re-entry ---------------------


def test_the_ordinary_loop_reconciles_a_streamed_delivery_it_left_hanging(
    stream: StreamWorld,
) -> None:
    """The streamed arm of D①: everything the repair owes is already durable,
    so the reconciliation writes **nothing but the turn's terminalization** —
    the count diff around the call is empty, and the transcript and the
    estimate are byte-identical to what the delivery left."""

    failing = FailingCommands(stream.store)
    crashed = stream_coordinator_with_commands(stream, failing).begin_turn(
        _stream_command("cmid-p9-4-loop")
    )
    assert not isinstance(crashed, Ok), crashed
    assert failing.failed is True
    turn_id = str(
        stream.db.execute(
            "SELECT turn_id FROM turn_record WHERE status = 'DELIVERING'"
        ).fetchone()[0]
    )
    action_id = action_of(stream, turn_id)
    assert stream.db.execute(
        "SELECT state FROM server_delivery_record WHERE action_id = ?",
        (str(action_id),),
    ).fetchone() == ("SENT_COMPLETE",)
    transcript_before = stream.db.execute(
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone()
    estimate_before = stream.db.execute(
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure, derivation_reason FROM exposure_estimate"
    ).fetchone()
    counts_before = _table_counts(stream.db)

    reconciled = begin_turn_ok(
        stream_coordinator(stream), "cmid-p9-4-loop"
    )
    assert reconciled.turn_id == turn_id
    assert reconciled.outcome == "REPLIED_FULL"
    assert reconciled.delivery_state == "SENT_COMPLETE"
    assert reconciled.ledger_event is None  # an ordinary turn owes no §20 word
    assert reconciled.ledger_failure is None
    assert _turn(stream.db, turn_id) == ("COMPLETED", "REPLIED_FULL")
    assert _table_counts(stream.db) == counts_before  # not one new row
    assert stream.db.execute(
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone() == transcript_before
    assert stream.db.execute(
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure, derivation_reason FROM exposure_estimate"
    ).fetchone() == estimate_before

    # and the third re-entry is a plain replay of the durable terminal result
    replayed = begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-loop")
    assert replayed.turn_id == turn_id
    assert _table_counts(stream.db) == counts_before


def test_the_repair_rebuilds_a_missing_cp3a_half_from_the_durable_row(
    stream: StreamWorld,
) -> None:
    """The transcript arm of D①: a residue whose CP3a half never landed (no
    ``assistant_turn`` row, no estimate) is rebuilt from the §22 row — the
    prefix **verbatim** as ``SENT_PARTIAL``, the estimate derived from that
    row's own word (``SENT_COMPLETE``: the whole reply was sent) — and the
    row's word, not the transcript's, decides the turn outcome."""

    begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-repair")
    turn_id = str(
        stream.db.execute("SELECT turn_id FROM turn_record").fetchone()[0]
    )
    action_id = action_of(stream, turn_id)
    row = stream.db.execute(
        "SELECT state, sent_prefix FROM server_delivery_record"
        " WHERE action_id = ?",
        (str(action_id),),
    ).fetchone()
    assert row is not None and str(row[0]) == "SENT_COMPLETE"
    prefix = str(row[1])
    # the crash shape: the transcript and the estimate never landed
    stream.db.execute("DELETE FROM assistant_turn WHERE turn_id = ?", (turn_id,))
    stream.db.execute(
        "DELETE FROM exposure_estimate WHERE action_id = ?", (str(action_id),)
    )
    stream.db.execute(
        "UPDATE turn_record SET status = 'DELIVERING', turn_outcome = NULL"
        " WHERE turn_id = ?",
        (turn_id,),
    )
    stream.db.commit()

    repaired = begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-repair")
    assert repaired.turn_id == turn_id
    assert repaired.outcome == "REPLIED_FULL"  # the row's own word
    transcript = stream.db.execute(
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone()
    assert transcript == (prefix, "SENT_PARTIAL", "SERVER_SENT_UNCONFIRMED")
    assert transcript[0] == REPLY  # the durable prefix, byte for byte
    estimate = stream.db.execute(
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure, derivation_reason FROM exposure_estimate"
    ).fetchone()
    assert estimate == (
        "SERVER_SENT_UNCONFIRMED",
        "FULL",
        "FULL",
        "NONE",
        f"sent {len(REPLY)} chars; no render ack",
    )

    # repeating the pass writes nothing new (the transcript and the estimate are
    # durable, and the turn is terminal)
    counts = _table_counts(stream.db)
    again = begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-repair")
    assert again.turn_id == turn_id
    assert _table_counts(stream.db) == counts


def test_the_loop_reconciles_a_delivery_that_released_nothing(
    stream: StreamWorld,
) -> None:
    """D①'s empty-prefix arm: the run released nothing (the source stopped
    before its first chunk), so the §22 row froze ``FAILED`` with an empty
    prefix and no transcript exists. A crash leaves the turn at ``DELIVERING``;
    the reconciliation finishes it ``NO_ASSISTANT_OUTPUT`` — the transcript's
    own word for "nothing was shown" — writes no §20 event, and leaves the
    estimate the delivery already wrote alone."""

    source = ScriptedSource(
        steps=(StreamStep.stopped("nothing came back yet"),)
    )
    completion = begin_turn_ok(
        stream_coordinator(stream, transport=SourceFactory(source)),
        "cmid-p9-4-nothing",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(stream, turn_id)
    assert completion.outcome == "FAILED_USER_VISIBLE"
    assert stream.db.execute(
        "SELECT state, sent_prefix FROM server_delivery_record"
        " WHERE action_id = ?",
        (str(action_id),),
    ).fetchone() == ("FAILED", "")
    assert stream.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 0
    assert stream.db.execute(
        "SELECT certainty, exposure_level FROM exposure_estimate"
        " WHERE action_id = ?",
        (str(action_id),),
    ).fetchone() == ("SERVER_SENT_UNCONFIRMED", "NONE")
    # the crash shape: the turn is nonterminal again, everything else durable
    stream.db.execute(
        "UPDATE turn_record SET status = 'DELIVERING', turn_outcome = NULL"
        " WHERE turn_id = ?",
        (turn_id,),
    )
    stream.db.commit()
    counts = _table_counts(stream.db)

    reconciled = begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-nothing")
    assert reconciled.turn_id == turn_id
    assert reconciled.outcome == "NO_ASSISTANT_OUTPUT"
    assert reconciled.reply_text is None
    assert reconciled.ledger_event is None
    assert _turn(stream.db, turn_id) == ("COMPLETED", "NO_ASSISTANT_OUTPUT")
    assert stream.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 0
    assert stream.db.execute(
        "SELECT COUNT(*) FROM planning_ledger_event"
    ).fetchone()[0] == 0
    assert _table_counts(stream.db) == counts


def test_the_repaired_estimate_of_a_partial_residue_is_derived_from_the_row(
    stream: StreamWorld,
) -> None:
    """The partial arm of D① (and of the estimate leg): the source stopped
    early, so the row is ``SENT_PARTIAL`` with the released prefix. The repair
    writes the transcript as ``SENT_PARTIAL`` and the estimate from that row —
    ``PARTIAL``, ``confirmed`` ``NONE`` — and the turn ends ``REPLIED_PARTIAL``,
    never ``REPLIED_FULL``: the buffered text is not the boundary."""

    kept = pieces(REPLY, 3)[0]
    source = ScriptedSource(
        steps=(StreamStep.chunk(kept), StreamStep.stopped("the window closed"))
    )
    completion = begin_turn_ok(
        stream_coordinator(stream, transport=SourceFactory(source)),
        "cmid-p9-4-partial-residue",
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(stream, turn_id)
    stream.db.execute("DELETE FROM assistant_turn WHERE turn_id = ?", (turn_id,))
    stream.db.execute(
        "DELETE FROM exposure_estimate WHERE action_id = ?", (str(action_id),)
    )
    stream.db.execute(
        "UPDATE turn_record SET status = 'DELIVERING', turn_outcome = NULL"
        " WHERE turn_id = ?",
        (turn_id,),
    )
    stream.db.commit()

    repaired = begin_turn_ok(
        stream_coordinator(stream), "cmid-p9-4-partial-residue"
    )
    assert repaired.outcome == "REPLIED_PARTIAL"
    assert stream.db.execute(
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone() == (kept, "SENT_PARTIAL", "SERVER_SENT_UNCONFIRMED")
    assert stream.db.execute(
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure, derivation_reason FROM exposure_estimate"
    ).fetchone() == (
        "SERVER_SENT_UNCONFIRMED",
        "PARTIAL",
        "PARTIAL",
        "NONE",
        f"sent {len(kept)} chars; partial send; no render ack",
    )


def test_the_repaired_turn_of_a_cancelled_row_is_cancelled_by_user(
    stream: StreamWorld,
) -> None:
    """The cancellation arm: the row was frozen ``CANCELLED`` with the prefix
    the client had already received (the P9-3 shape) and the transcript never
    landed. The repair takes §1-C②'s word — ``CANCELLED_BY_USER``, the live
    cancellation's own — writes the prefix verbatim as ``SENT_PARTIAL``, and
    derives the estimate from the row (``PARTIAL``: what was sent, no more)."""

    begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-cancelled")
    turn_id = str(
        stream.db.execute("SELECT turn_id FROM turn_record").fetchone()[0]
    )
    action_id = action_of(stream, turn_id)
    # the forced world: the row the cancel face would have frozen, the
    # transcript and the estimate gone, the turn back at DELIVERING
    stream.db.execute(
        "UPDATE server_delivery_record SET state = 'CANCELLED'"
        " WHERE action_id = ?",
        (str(action_id),),
    )
    stream.db.execute("DELETE FROM assistant_turn WHERE turn_id = ?", (turn_id,))
    stream.db.execute(
        "DELETE FROM exposure_estimate WHERE action_id = ?", (str(action_id),)
    )
    stream.db.execute(
        "UPDATE turn_record SET status = 'DELIVERING', turn_outcome = NULL"
        " WHERE turn_id = ?",
        (turn_id,),
    )
    stream.db.commit()

    repaired = begin_turn_ok(stream_coordinator(stream), "cmid-p9-4-cancelled")
    assert repaired.outcome == "CANCELLED_BY_USER"
    assert repaired.delivery_state == "CANCELLED"
    assert stream.db.execute(
        "SELECT content, delivery_state FROM assistant_turn"
    ).fetchone() == (REPLY, "SENT_PARTIAL")
    assert stream.db.execute(
        "SELECT exposure_level, max_possible_exposure, confirmed_exposure,"
        " derivation_reason FROM exposure_estimate"
    ).fetchone() == (
        "PARTIAL",
        "PARTIAL",
        "NONE",
        f"sent {len(REPLY)} chars; the send was cancelled; no render ack",
    )
    assert _turn(stream.db, turn_id) == (
        "CANCELLED_BY_USER",
        "CANCELLED_BY_USER",
    )


# -- ① the CP3 under-record: the startup face ---------------------------------


def test_the_startup_face_reconciles_the_cp3_residue_and_writes_the_event_once(
    crash_world: CrashWorld,
) -> None:
    """The teaching arm of D①, on the face the task names second: the §20
    event the cut-short leg owed is written exactly once, the turn takes the
    transcript's outcome, and the moment's own residue is left to the sweep
    (the delivered opening is *not* an undelivered one)."""

    turn_id, action_id, moment_id = _crash_after_cp3(crash_world)
    assert count_events(crash_world.db) == 0
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 1

    coordinator = new_epoch_coordinator(crash_world)
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    reconciled = outcome.value.reconciled_turns
    assert len(reconciled) == 1
    record = reconciled[0]
    assert record.turn_id == turn_id
    assert record.outcome == "REPLIED_FULL"
    assert record.repaired_transcript is False
    assert record.exposure_event == "teaching_presented"
    assert record.wrote_exposure is True
    assert record.failure_reason is None

    # the durable facts the record claims
    assert _turn(crash_world.db, turn_id) == ("COMPLETED", "REPLIED_FULL")
    assert count_events(crash_world.db) == 1
    event = crash_world.db.execute(
        "SELECT event_id, event, moment_id, ledger_key"
        " FROM planning_ledger_event"
    ).fetchone()
    assert event is not None
    assert event[1] == "teaching_presented"
    assert event[2] == moment_id  # the provenance column
    assert event[0].endswith(str(action_id))
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 1
    # the moment was a *delivered* opening: the sweep owns it, not the new line
    assert outcome.value.aborted_openings == ()
    assert _moment_state(crash_world) == ("CLOSED", "SYSTEM_RECOVERY_ABORT")
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 0

    # a second pass finds nothing left and writes nothing
    counts = _table_counts(crash_world.db)
    again = coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.reconciled_turns == ()
    assert again.value.plan == ()
    assert _table_counts(crash_world.db) == counts


def test_the_repair_leaves_a_durable_exposure_event_alone(
    crash_world: CrashWorld,
) -> None:
    """The "有则不动" arm of the exactly-once rule: the delivery's own §20
    event is durable (the leg wrote it) and only the terminalization was lost.
    The repair finds the deterministic id, appends **nothing** — one event
    before, one after, no second row and no ``CONFLICT`` note — and the record
    says which of the two it did (``wrote_exposure`` false)."""

    delivered = teaching_coordinator(crash_world).begin_turn(
        _command("cmid-p9-4-event-present")
    )
    assert isinstance(delivered, Ok), delivered
    assert count_events(crash_world.db) == 1
    turn_id = str(
        crash_world.db.execute(
            "SELECT turn_id FROM turn_record"
        ).fetchone()[0]
    )
    crash_world.db.execute(
        "UPDATE turn_record SET status = 'DELIVERING', turn_outcome = NULL"
        " WHERE turn_id = ?",
        (turn_id,),
    )
    crash_world.db.commit()

    coordinator = new_epoch_coordinator(crash_world)
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert len(outcome.value.reconciled_turns) == 1
    record = outcome.value.reconciled_turns[0]
    assert record.turn_id == turn_id
    assert record.outcome == "REPLIED_FULL"
    assert record.exposure_event == "teaching_presented"
    assert record.wrote_exposure is False  # it found the event, did not write one
    assert record.failure_reason is None
    assert count_events(crash_world.db) == 1
    assert _turn(crash_world.db, turn_id) == ("COMPLETED", "REPLIED_FULL")


def test_a_teaching_residue_that_presented_nothing_owes_no_exposure_event(
    crash_world: CrashWorld,
) -> None:
    """The §20 predicate's neglected arm (review F3): the event follows a
    **presentation**, and a teaching action whose transcript is absent is not
    one — the repair writes nothing.

    The world is forced, and the test says so: no shipped writer leaves a
    teaching action ``TERMINAL`` with its transcript gone (the teaching leg is
    ``BUFFERED_VALIDATED``, so it canonicalizes before ``complete_delivery``),
    and this face holds no §22 row either. The shape is exactly the one the
    predicate is defined over — a teaching kind, a durable moment, an empty
    prefix and no transcript — so this pins the predicate
    (``_ensure_exposure_once(presented=…)``) where the neighboring tests pin
    its producers: the delivered opening owes ``teaching_presented``, this one
    owes none, and the two together are what makes the flag load-bearing.
    """

    turn_id, _action_id, _moment_id = _crash_after_cp3(crash_world)
    assert count_events(crash_world.db) == 0
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM server_delivery_record"
    ).fetchone()[0] == 0  # the buffered face keeps no §22 row (empty prefix)
    # the forced world: the transcript the §20 rule keys on is gone
    crash_world.db.execute(
        "DELETE FROM assistant_turn WHERE turn_id = ?", (turn_id,)
    )
    crash_world.db.commit()

    result = teaching_coordinator(crash_world).begin_turn(
        _command("cmid-p9-4-cp3")
    )
    assert isinstance(result, Ok), result
    reconciled = result.value
    assert reconciled.turn_id == turn_id
    assert reconciled.outcome == "NO_ASSISTANT_OUTPUT"
    assert reconciled.reply_text is None
    assert reconciled.ledger_event is None
    assert reconciled.ledger_failure is None
    assert _turn(crash_world.db, turn_id) == (
        "COMPLETED",
        "NO_ASSISTANT_OUTPUT",
    )
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 0
    assert count_events(crash_world.db) == 0  # no presentation, no §20 event


# -- ② the CP2 OPENING residue ------------------------------------------------


def test_the_startup_face_aborts_an_opening_that_never_delivered(
    crash_world: CrashWorld,
) -> None:
    """D②: the CP2 slot stayed ``OPENING`` with its lock and no delivery ever
    happened (the persona leg refused before it could deliver). The new line
    closes it through §7's abort walk with ``DELIVERY_FAILURE``, releases the
    lock, and leaves **no** estimate and **no** §20 event — nothing was sent."""

    refusing = RefusingPersona(
        PersonaRuntime(
            actions=crash_world.world.generation,
            provider=ScriptedPersonaProvider(),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        )
    )
    crashed = teaching_coordinator(crash_world, persona=refusing).begin_turn(
        _command("cmid-p9-4-cp2")
    )
    assert not isinstance(crashed, Ok), crashed
    assert _moment_state(crash_world) == ("OPENING", None)
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 1
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 0
    assert count_events(crash_world.db) == 0
    row = crash_world.db.execute(
        "SELECT turn_id, status FROM turn_record"
    ).fetchone()
    assert row is not None and str(row[1]) != "COMPLETED"
    turn_id = str(row[0])

    coordinator = new_epoch_coordinator(crash_world)
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert len(outcome.value.aborted_openings) == 1
    moment_id = outcome.value.aborted_openings[0]
    assert _moment_state(crash_world) == ("CLOSED", "DELIVERY_FAILURE")
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 0
    # nothing was sent: no estimate, no §20 event (the derivation's own reading)
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 0
    assert count_events(crash_world.db) == 0
    # the turn of the abandoned opening is finished by the turn-level closure
    assert _turn(crash_world.db, turn_id)[0] == "COMPLETED"
    assert _turn(crash_world.db, turn_id)[1] == "NO_ASSISTANT_OUTPUT"

    counts = _table_counts(crash_world.db)
    again = coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.aborted_openings == ()
    assert _table_counts(crash_world.db) == counts
    assert moment_id  # the id the plan named is the one that closed


def test_the_startup_face_leaves_a_delivered_opening_to_the_sweep(
    crash_world: CrashWorld,
) -> None:
    """The control for D②: an opening that *was* delivered (the moment is
    ``AWAITING_USER``) is not an undelivered one — the new line names nothing,
    and the sweep closes it with its own generic word. Without this arm the
    line's "nothing sent" predicate would be indistinguishable from "every
    ``OPENING`` moment, everywhere"."""

    delivered = teaching_coordinator(crash_world).begin_turn(
        _command("cmid-p9-4-delivered")
    )
    assert isinstance(delivered, Ok), delivered
    assert _moment_state(crash_world) == ("AWAITING_USER", None)
    assert count_events(crash_world.db) == 1

    coordinator = new_epoch_coordinator(crash_world)
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.aborted_openings == ()
    assert _moment_state(crash_world) == ("CLOSED", "SYSTEM_RECOVERY_ABORT")
    assert crash_world.db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 0
    # its §20 event is the delivery's own and stays exactly one
    assert count_events(crash_world.db) == 1
    assert outcome.value.reconciled_turns == ()


def test_the_aborting_line_needs_a_live_teaching_port(
    crash_world: CrashWorld,
) -> None:
    """The port's absence is registered, not simulated: an assembly without the
    teaching controller answers no aborted opening and no reconciled turn (the
    P1/P2 shape's own reading)."""

    coordinator = ConversationCoordinator(
        lease=crash_world.world.lease,
        conversation_commands=crash_world.world.store,
        conversation_queries=crash_world.world.store,
        persona=PersonaRuntime(
            actions=crash_world.world.generation,
            provider=ScriptedPersonaProvider(),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=crash_world.world.generation,
        decision_cycles=crash_world.world.generation.decision_cycles,
    )
    assert coordinator.abort_undelivered_openings() == ()
    assert coordinator.reconcile_delivering_residue(()) == ()


def _stream_command(client_message_id: str):
    from tests.phase9.test_p9_2_stream_turn import command

    return command(client_message_id)


def stream_coordinator_with_commands(stream: StreamWorld, commands: object):
    """The P9-2 coordinator with its command face replaced (the crash harness:
    the first ``terminalize_turn`` is refused, everything else is the real
    chain)."""

    from tests.phase9.test_p9_2_stream_turn import persona_runtime

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
