"""P9-3 disposition ① — the teaching face's guard and the teaching entries'
reconciler (review MEDIUM-1).

Before this disposition the buffered teaching delivery ran **no** §15 check:
``finalize_delivery`` referenced no guard, ``guard_verdict`` /
``_record_guard_result`` / ``InterruptAwareTransport`` were called exactly once
each (all inside ``finalize_streamed_delivery``), and
``_reconcile_pending_interrupt`` had one caller (``_begin_turn_guarded``). Two
consequences were structural rather than incidental, and each has a test here:

- §15's three teaching legs (lock / target suppression / JUST_CHAT) were
  **unreachable** — a hard invalidation could not stop any teaching delivery
  (``test_a_suppressed_target_invalidates_the_teaching_opening_before_it_is_sent``,
  plus the healthy-path rows in
  ``test_the_teaching_legs_are_read_on_a_healthy_delivery``);
- a pending interrupt naming a teaching action or turn **did not stop
  teaching** — the teaching entries took the guard but never reconciled
  (``test_an_interrupt_that_names_a_teaching_action_stops_its_delivery`` plus the
  two entry tests at the bottom).

The world is P8-4's real-corpus world over a **file-backed** app.db (so a second
thread can own its connection while the main thread writes the interrupt and
reads the assertions), and nothing here is a fixture supply: the teaching
moments, the gate rows, the guard rows and the interrupt row are all written by
the shipped faces. (P8-4's candidate *supply* is still the one sanctioned
injection for an ALLOW — the corpus' readiness posture is what P8-5's rollout
gate HOLDs — and these tests do not need it: a user-initiated open is decided by
the shipped Gate facts alone.)

Registered (P9-3 disposition, review INFO-6): the review's budget figures
(tracked "1081" against three measured counts) are **not reproducible from the
tree as a single number** — "tracked diff lines", "diff lines including
untracked files" and "files touched" are three different rulers, and this file
registers that instead of picking one after the fact. The delivered count for
this disposition is the one printed in the cut's receipt, with its ruler named.

Two further findings this wiring exposed, and where their evidence lives:

- **a teaching continuation's lineage is its episode's** (``STATE_MACHINES
  §17``: "Continuation 由 ACTIVE_MOMENT authorization lineage 约束"), not its
  host turn's — the reply turn opens its own DecisionCycle for the attempt it
  decided, so the pre-disposition reading would have flagged **every**
  continuation. The assembly now compares a teaching action's cycle against
  its moment's; the real-chain evidence is
  ``tests/phase8/test_p8_4_exposure.py``'s hint chain (which failed under the
  old reading) plus this file's healthy-delivery row;
- **the episode's ``PERSONA_RESUME`` closing move is delivered after the
  terminal transition released its lock** (SM §1), so the lock condition has
  no subject for it and answers ``False``; without that reading every resume
  would be invalidated. The evidence is phase 3's three-assistant-row chain
  (``test_every_teaching_action_runs_the_full_p1_pipeline``), which failed
  under the released-lock reading and passes with it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from elc.conversation import (
    CommitUserTurn,
    SqliteConversationStore,
)
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
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
    DecisionCycleId,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    TurnId,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    TurnStatus,
)
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import MomentState
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
)
from tests.conftest import AssemblyGenerationStore
from tests.phase7.conftest import CONV, DAY_ONE, TARGET_ID
from tests.phase8.p8_4_world import World, build_content
from tests.phase8.p8_4_world import world as p8_world

REQUESTED_AT = "2026-09-21T08:00:00+00:00"

#: What the scripted provider answers when a test does not gate it — kept away
#: from §21's forbidden claims so the validator accepts it.
PROVIDER_TEXT = "Let us rehearse that once more, slowly and out loud."

TARGET = str(TARGET_ID)


# -- the file-backed P8-4 world ------------------------------------------------


@dataclass(frozen=True)
class FileWorld:
    """P8-4's world over a file db, plus the two paths a thread needs."""

    path: Path
    content_path: Path
    db: sqlite3.Connection
    fence: RuntimeEpochFence
    world: World


@pytest.fixture()
def file_world(tmp_path: Path) -> FileWorld:
    path = tmp_path / "app.db"
    db = connection.connect(path)
    migrations.apply_migrations(db)
    fence = epoch.open_runtime_epoch(db)
    content_path = build_content(tmp_path / "content.db")
    built = FileWorld(
        path=path,
        content_path=content_path,
        db=db,
        fence=fence,
        world=p8_world(db, fence, content_path),
    )
    yield built
    db.close()


def coordinator_over(
    world_: World,
    *,
    provider: object | None = None,
    constraint_views: object | None = None,
    delivery_records: object | None = None,
) -> ConversationCoordinator:
    """The coordinator the fixture's own stores build (the P8-4 assembly plus
    the two P9-3 authorities a test asks for)."""

    return ConversationCoordinator(
        lease=world_.lease,
        conversation_commands=world_.store,
        conversation_queries=world_.store,
        persona=PersonaRuntime(
            actions=world_.generation,
            provider=(
                ScriptedPersonaProvider(
                    script=(ProviderOutput(text=PROVIDER_TEXT),)
                )
                if provider is None
                else provider  # type: ignore[arg-type]
            ),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=world_.generation,
        decision_cycles=world_.generation.decision_cycles,
        learning_controller=world_.learning,
        teaching=world_.teaching,
        targets=world_.targets,
        delivery_records=delivery_records,  # type: ignore[arg-type]
        constraint_views=constraint_views,  # type: ignore[arg-type]
    )


@dataclass
class BoundCoordinator:
    """The same world, bound to the asking thread's own connection."""

    db: sqlite3.Connection
    coordinator: ConversationCoordinator


def thread_coordinator(
    file_world_: FileWorld,
    *,
    provider: object,
    constraint_views: bool,
    delivery_records: bool = True,
) -> BoundCoordinator:
    """One coordinator over a second connection (sqlite3 connections are
    thread-bound, so the worker thread needs its own — the P9-3 barge-in
    suite's ``bind`` pattern)."""

    db = connection.connect(file_world_.path)
    fence = RuntimeEpochFence(current=file_world_.fence.current)
    store = SqliteConversationStore(db, fence)
    generation = AssemblyGenerationStore(db, fence)
    teaching = TeachingController(SqliteTeachingStore(db, fence))
    learning = LearningController(SqliteLearningStore(db, fence))
    user_config = UserConfigController(SqliteUserConfigStore(db, fence))
    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(fence.current)
    return BoundCoordinator(
        db=db,
        coordinator=ConversationCoordinator(
            lease=lease,
            conversation_commands=store,
            conversation_queries=store,
            persona=PersonaRuntime(
                actions=generation,
                provider=provider,  # type: ignore[arg-type]
                compiler=PromptCompiler(),
                validator=ResponseValidator(),
                max_provider_attempts=3,
            ),
            generation_actions=generation,
            decision_cycles=generation.decision_cycles,
            learning_controller=learning,
            teaching=teaching,
            targets=ContentBackedTeachingTargetProvider(
                file_world_.content_path
            ),
            delivery_records=(
                SqliteDeliveryRecordStore(db, fence)
                if delivery_records
                else None
            ),
            constraint_views=user_config if constraint_views else None,
        ),
    )


class GatedProvider:
    """A provider that parks inside ``call`` until the test releases it.

    The in-process shape of "the answer was being generated while the user
    typed something else": the worker thread is inside the provider call (no
    transaction is held — R-INV-004), so the main thread can write a durable
    interrupt / constraint row and then let the generation finish. The guard
    still reads that row *before* the delivery, which is the point: both
    scenarios below are races that the shipped order (read facts → judge →
    deliver) resolves in the user's favour.
    """

    def __init__(self, *, text: str = PROVIDER_TEXT) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self._text = text

    def call(self, prompt: object) -> ProviderOutput:
        del prompt
        self.calls += 1
        if self.calls == 1:
            self.entered.set()
            if not self.release.wait(timeout=30):
                raise RuntimeError("the gate was never released")
        return ProviderOutput(text=self._text)


def teaching_request(
    client_message_id: str, *, focus_target_id: str = TARGET
) -> TeachingRequest:
    return TeachingRequest(
        conversation_id=CONV,
        focus_target_id=focus_target_id,
        target_type="RESOURCE",
        client_message_id=ClientMessageId(client_message_id),
        requested_at=REQUESTED_AT,
    )


# -- durable reads (the fixture's own connection, never the worker's) ----------


def scalar(world_: FileWorld, sql: str, params: tuple[object, ...] = ()):
    rows = world_.db.execute(sql, params).fetchall()
    assert rows, f"no row for {sql!r}"
    return rows[0][0]


def count(world_: FileWorld, table: str) -> int:
    return int(
        world_.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    )


def guard_rows(world_: FileWorld, action_id: str) -> list[tuple[str, list[str]]]:
    rows = world_.db.execute(
        "SELECT decision, reason_codes FROM pre_delivery_guard_result"
        " WHERE action_id = ?",
        (action_id,),
    ).fetchall()
    return [(str(row[0]), list(json.loads(str(row[1])))) for row in rows]


def live_teaching_action(world_: FileWorld) -> tuple[str, str]:
    """The (turn, action) pair of the one live teaching action — read while the
    worker is parked inside the provider."""

    row = world_.db.execute(
        "SELECT action_id, turn_id FROM generation_action_intent"
    ).fetchall()
    assert len(row) == 1, row
    return str(row[0][1]), str(row[0][0])


def interrupt_teaching(world_: FileWorld, *, turn_id: str, action_id: str, tag: str):
    """The user's `stop that` — the durable row the entry writes (§17.1 rules
    1-2), written from the main thread while the worker holds the guard."""

    written = world_.world.store.request_interrupt(
        InterruptRequest(
            input_id=InputId(f"in-p9-3-tg-{tag}"),
            conversation_id=str(CONV),
            active_turn_id=TurnId(turn_id),
            active_action_id=ActionId(action_id),
            reason="the user typed something else",
        )
    )
    assert isinstance(written, Ok), written


def run_worker(work: object) -> tuple[
    list[object], list[BaseException], threading.Thread
]:
    """Run one callable on its own thread and collect what it answered."""

    assert callable(work)
    answers: list[object] = []
    errors: list[BaseException] = []

    def entry() -> None:
        try:
            answers.append(work())
        except BaseException as exc:  # noqa: BLE001 — reported, not hidden
            errors.append(exc)

    thread = threading.Thread(target=entry, name="p9-3-teaching-guard")
    thread.start()
    return answers, errors, thread


# -- ① the interrupt stops a teaching delivery (MEDIUM-1(a)) -------------------


def test_an_interrupt_that_names_a_teaching_action_stops_its_delivery(
    file_world: FileWorld,
) -> None:
    """`Stop that` on a live teaching action, while it is being generated.

    The worker is parked inside the provider; the interrupt row is written from
    another thread; the guard then reads ``action_cancelled`` as ``True`` and
    the opening is **not sent**: the action terminalizes undelivered, no
    assistant row is written, the moment aborts through the existing §7
    ``DELIVERY_FAILURE`` move, and the turn ends ``CANCELLED_BY_USER`` — §1-C③'s
    cancellation word, because a cancellation is what happened.

    This is also the guard's teaching-face reachability on the sharpest
    scenario: without the dispatched guard the delivery would simply finish
    (the interrupt is not consulted by the buffered face anywhere else), and
    without the entry's reconciler the row would stay pending forever.
    """

    provider = GatedProvider()

    def work() -> object:
        # the connection must be created *inside* the worker's thread
        # (sqlite3 connections are thread-bound)
        bound = thread_coordinator(
            file_world, provider=provider, constraint_views=True
        )
        try:
            return bound.coordinator.request_teaching(
                teaching_request("cmid-p9-3-tg-interrupt")
            )
        finally:
            bound.db.close()

    answers, errors, worker = run_worker(work)
    try:
        entered = provider.entered.wait(timeout=30)
        assert entered, f"the provider was never called; errors={errors!r}"
        turn_id, action_id = live_teaching_action(file_world)
        interrupt_teaching(
            file_world, turn_id=turn_id, action_id=action_id, tag="teach"
        )
        provider.release.set()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the worker did not finish"
        assert errors == [], errors
        assert len(answers) == 1
        answered = answers[0]
        assert isinstance(answered, Ok), answered
        result = answered.value
        assert result.turn_status is TurnStatus.CANCELLED_BY_USER
        assert result.outcome == "CANCELLED_BY_USER"
        assert result.moment_state is MomentState.CLOSED
        assert result.action_status is GenerationActionStatus.TERMINAL

        # nothing was sent
        assert count(file_world, "assistant_turn") == 0
        assert (
            scalar(
                file_world,
                "SELECT status FROM turn_record WHERE turn_id = ?",
                (turn_id,),
            )
            == "CANCELLED_BY_USER"
        )
        assert (
            scalar(
                file_world,
                "SELECT turn_outcome FROM turn_record WHERE turn_id = ?",
                (turn_id,),
            )
            == "CANCELLED_BY_USER"
        )
        assert (
            scalar(
                file_world,
                "SELECT status FROM generation_action_intent"
                " WHERE action_id = ?",
                (action_id,),
            )
            == "TERMINAL"
        )
        # the guard's own row: the one cut this disposition added
        assert guard_rows(file_world, action_id) == [
            ("INVALIDATE_ACTION", ["ACTION_CANCELLED"])
        ]
        # the episode aborted through the existing §7 word
        row = file_world.db.execute(
            "SELECT lifecycle_state, abort_reason FROM teaching_moment"
        ).fetchone()
        assert row is not None
        assert str(row[0]) == "CLOSED"
        assert str(row[1]) == "DELIVERY_FAILURE"
        # the request row stays durable (the entry answers nothing about it)
        # and it stops being *pending*: the face reads "pending" as "naming a
        # row that is still live", and the guard's refusal made the action
        # terminal — the same reading the reconciler's skip arm uses
        assert (
            scalar(
                file_world,
                "SELECT active_action_id FROM interrupt_request"
                " WHERE input_id = ?",
                ("in-p9-3-tg-teach",),
            )
            == action_id
        )
        pending = file_world.world.store.list_pending_interrupts_for_action(
            ActionId(action_id)
        )
        assert isinstance(pending, Ok) and pending.value == ()
    finally:
        provider.release.set()


# -- ② a suppressed target is a hard invalidation before the send (MEDIUM-1(b)) -


def test_a_suppressed_target_invalidates_the_teaching_opening_before_it_is_sent(
    file_world: FileWorld,
) -> None:
    """§15's ``NEW_TARGET_SUPPRESSED`` on the real chain — the teaching leg
    that had no consumer before this disposition.

    A ``SUPPRESS_REVIEW`` constraint for the opening's own focus target is
    written while the worker is parked inside the provider (the shipped §9
    write face); the guard then answers ``INVALIDATE_ACTION`` and the delivery
    is refused: no assistant row, the action terminal undelivered, the moment
    aborted with §7's ``DELIVERY_FAILURE``, and the turn takes §1-C③'s
    **non**-cancellation word (``NO_ASSISTANT_OUTPUT`` — no user act asked for
    this stop).

    The guard row's single code is the proof of coverage: ``TEACHING_LOCK_INVALID``
    and ``JUST_CHAT_HARD_SWITCH`` were read and answered ``False`` (a ``True``
    would appear among the codes), ``NEW_TARGET_SUPPRESSED`` is the one that
    held, and no other condition could be read as unread (an unread one would
    spell ``UNCHECKED_*``).
    """

    provider = GatedProvider()

    def work() -> object:
        # the connection must be created *inside* the worker's thread
        # (sqlite3 connections are thread-bound)
        bound = thread_coordinator(
            file_world, provider=provider, constraint_views=True
        )
        try:
            return bound.coordinator.request_teaching(
                teaching_request("cmid-p9-3-tg-suppressed")
            )
        finally:
            bound.db.close()

    answers, errors, worker = run_worker(work)
    try:
        entered = provider.entered.wait(timeout=30)
        assert entered, f"the provider was never called; errors={errors!r}"
        turn_id, action_id = live_teaching_action(file_world)
        written = file_world.world.user_config.record_planner_constraint(
            PlannerConstraint(
                constraint_id="pc-p9-3-tg-suppress",
                target_type="RESOURCE",
                target_id=TARGET,
                constraint_type=PlannerConstraintType.SUPPRESS_REVIEW,
                scope=PlannerConstraintScope.UNTIL_DATE,
                starts_at=DAY_ONE,
                active=True,
            )
        )
        assert isinstance(written, Ok), written
        provider.release.set()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the worker did not finish"
        assert errors == [], errors
        assert len(answers) == 1
        answered = answers[0]
        assert isinstance(answered, Ok), answered
        result = answered.value
        # §10: the no-output outcome keeps its own word in ``turn_outcome``
        # and ends the coordination state COMPLETED
        assert result.outcome == "NO_ASSISTANT_OUTPUT"
        assert result.turn_status is TurnStatus.COMPLETED
        assert result.moment_state is MomentState.CLOSED

        assert count(file_world, "assistant_turn") == 0
        assert (
            scalar(
                file_world,
                "SELECT status FROM generation_action_intent"
                " WHERE action_id = ?",
                (action_id,),
            )
            == "TERMINAL"
        )
        assert guard_rows(file_world, action_id) == [
            ("INVALIDATE_ACTION", ["NEW_TARGET_SUPPRESSED"])
        ]
        row = file_world.db.execute(
            "SELECT lifecycle_state, abort_reason FROM teaching_moment"
        ).fetchone()
        assert row is not None
        assert (str(row[0]), str(row[1])) == ("CLOSED", "DELIVERY_FAILURE")
    finally:
        provider.release.set()


# -- ③ the healthy path: the legs are read, and nothing else moved (MEDIUM-1(d)) --


def test_the_teaching_legs_are_read_on_a_healthy_delivery(
    file_world: FileWorld,
) -> None:
    """The zero-relaxation half, on the real ALLOW chain a user-initiated open
    produces end to end.

    Two claims in one walk:

    - **the legs are read**. The guard row carries
      ``UNCHECKED_NEW_TARGET_SUPPRESSED`` and ``UNCHECKED_JUST_CHAT_HARD_SWITCH``
      — the two "no §9 authority wired" spellings — and **no** other code. That
      pair is only produced for a *teaching* action (an ordinary reply answers
      those two facts ``False`` and would spell no code at all), and it is only
      produced at all if ``_pre_delivery_guard_facts`` ran for this delivery.
      ``TEACHING_LOCK_INVALID`` did not invalidate — if the leg had answered
      ``True`` the verdict would be ``INVALIDATE_ACTION`` and the code would
      appear — so the **False** arm (``OWNED_BY_THIS_MOMENT``) is covered here
      on a real moment (the review LOW-6 gap);
    - **the delivery itself did not move**. The opening is sent, the moment
      reaches ``AWAITING_USER``, the action is TERMINAL, the turn is
      ``COMPLETED``, the transcript carries the one assistant row with the
      buffered face's own two words — and the delivery's dispatch is still
      ``BUFFERED_VALIDATED`` (§13's default table for all five teaching types).

    ``delivery_records`` is wired because the guard's §21.1 row is the thing
    being asserted; the coordinator's buffers are the world's own.
    """

    world_ = file_world.world
    records = SqliteDeliveryRecordStore(file_world.db, file_world.fence)
    coordinator = coordinator_over(world_, delivery_records=records)
    result = coordinator.request_teaching(
        teaching_request("cmid-p9-3-tg-healthy")
    )
    assert isinstance(result, Ok), result
    value = result.value

    assert value.gate_decision == "ALLOW"
    assert value.turn_status is TurnStatus.COMPLETED
    assert value.outcome == "REPLIED_FULL"
    assert value.moment_state is MomentState.AWAITING_USER
    assert value.action_status is GenerationActionStatus.TERMINAL
    action_id = str(value.action_id)

    assert count(file_world, "assistant_turn") == 1
    row = file_world.db.execute(
        "SELECT delivery_state, delivery_certainty, content FROM assistant_turn"
    ).fetchone()
    assert row is not None
    assert (str(row[0]), str(row[1])) == (
        "SENT_COMPLETE",
        "SERVER_SENT_UNCONFIRMED",
    )
    assert str(row[2]) == PROVIDER_TEXT
    assert (
        scalar(
            file_world,
            "SELECT lifecycle_state FROM teaching_moment WHERE moment_id = ?",
            (str(value.moment_id),),
        )
        == "AWAITING_USER"
    )

    # the guard ran, for this teaching action, and read the teaching legs
    assert guard_rows(file_world, action_id) == [
        (
            "VALID",
            [
                "UNCHECKED_NEW_TARGET_SUPPRESSED",
                "UNCHECKED_JUST_CHAT_HARD_SWITCH",
            ],
        )
    ]
    # ... and the delivery mode did not move for any teaching type
    from elc.runtime.guarded_stream import DeliveryMode, delivery_mode_of

    for action_type in (
        GenerationActionType.TEACHING_OPEN,
        GenerationActionType.TEACHING_HINT,
        GenerationActionType.TEACHING_REVEAL,
        GenerationActionType.TEACHING_EXPLANATION,
        GenerationActionType.PERSONA_RESUME,
    ):
        assert (
            delivery_mode_of(action_type) is DeliveryMode.BUFFERED_VALIDATED
        ), action_type


# -- ④ the two teaching entries reconcile (MEDIUM-1(a2)) -----------------------


def plant_hanging_teaching_action(
    world_: World, client_message_id: str
) -> tuple[str, str]:
    """One durable teaching *turn* with a **live** PREPARED teaching action.

    This is the shape a crash between CP2 and the delivery leaves (P3-1B's F2
    window): the turn is nonterminal, the action names the teaching slot and
    nothing has been sent. It is built through the production write faces —
    the conversation store's own CP0 and transition, the real DecisionCycle
    unit, the real §14 action store — never through a fixture supply.
    """

    committed = world_.store.commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{client_message_id}"),
                client_message_id=ClientMessageId(client_message_id),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{client_message_id}",
                received_at=REQUESTED_AT,
            ),
            raw_content="",
            normalized_content=None,
            runtime_version="runtime-p9-3-tg",
        )
    )
    assert isinstance(committed, Ok), committed
    cp0 = committed.value
    advanced = world_.store.transition_turn(
        cp0.turn_id, cp0.state_version, TurnStatus.DECIDING
    )
    assert isinstance(advanced, Ok), advanced
    cycle = world_.generation.decision_cycles.record_decision_cycle(
        decision_cycle_id=DecisionCycleId(f"dcy-{cp0.turn_id}-hanging"),
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=advanced.value.state_version,
    )
    assert isinstance(cycle, Ok), cycle
    created = world_.generation.create_action(
        GenerationActionIntentRecord(
            action_id=ActionId(f"ga-{cp0.turn_id}-teaching-hint"),
            turn_id=cp0.turn_id,
            decision_cycle_id=cycle.value.decision_cycle_id,
            moment_id=None,
            assistant_turn_id=f"aturn-{cp0.turn_id}-teaching-hint",
            action_type=GenerationActionType.TEACHING_HINT,
            generation_contract_id="gc-teaching-hint",
            status=GenerationActionStatus.PREPARED,
            attempt_count=0,
            owner_epoch=world_.lease.epoch,
        )
    )
    assert isinstance(created, Ok), created
    return str(cp0.turn_id), str(created.value)


def hanging_is_cancelled(file_world: FileWorld, turn_id: str, action_id: str) -> None:
    """The reconciler's own durable answer for one hanging pair."""

    assert count(file_world, "assistant_turn") == 0
    assert (
        scalar(
            file_world,
            "SELECT status FROM generation_action_intent WHERE action_id = ?",
            (action_id,),
        )
        == "TERMINAL"
    )
    assert (
        scalar(
            file_world,
            "SELECT status FROM turn_record WHERE turn_id = ?",
            (turn_id,),
        )
        == "CANCELLED_BY_USER"
    )
    assert (
        scalar(
            file_world,
            "SELECT turn_outcome FROM turn_record WHERE turn_id = ?",
            (turn_id,),
        )
        == "CANCELLED_BY_USER"
    )


def test_the_opening_entry_reconciles_a_pending_interrupt_before_its_gate(
    file_world: FileWorld,
) -> None:
    """``request_teaching`` takes the guard and now also reconciles: a pending
    interrupt naming a hanging teaching action and its turn is answered by
    this entry (the action terminal undelivered, the turn
    ``CANCELLED_BY_USER``), *before* the command turn and before the Gate.

    The unknown target keeps the entry's own outcome deterministic (BF-03's
    ``TARGET_INVALID`` DENY) so the assertion is about the hanging pair, not
    about a second teaching episode; without the reconciler call the hanging
    action would stay ``PREPARED`` and its turn ``DECIDING`` forever.
    """

    turn_id, action_id = plant_hanging_teaching_action(
        file_world.world, "cmid-p9-3-tg-hanging-open"
    )
    interrupt_teaching(
        file_world, turn_id=turn_id, action_id=action_id, tag="hanging-open"
    )
    coordinator = coordinator_over(file_world.world)
    result = coordinator.request_teaching(
        teaching_request(
            "cmid-p9-3-tg-open-after",
            focus_target_id="res-p9-3-tg-does-not-exist",
        )
    )
    assert isinstance(result, Ok), result
    assert result.value.gate_decision == "DENY"
    hanging_is_cancelled(file_world, turn_id, action_id)


def test_the_reply_entry_reconciles_a_pending_interrupt_before_it_looks_for_a_moment(
    file_world: FileWorld,
) -> None:
    """``respond_to_teaching`` takes the guard and now also reconciles — in the
    same position (after the guard, before CP0): the hanging pair is cancelled
    even though the entry then refuses its own turn for the ordinary reason
    ("no active teaching moment"). Without the reconciler call this refusal
    would be the *only* thing that happened and the hanging rows would stay
    live.
    """

    turn_id, action_id = plant_hanging_teaching_action(
        file_world.world, "cmid-p9-3-tg-hanging-reply"
    )
    interrupt_teaching(
        file_world, turn_id=turn_id, action_id=action_id, tag="hanging-reply"
    )
    coordinator = coordinator_over(file_world.world)
    result = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.CONTINUE,
                attempt_present=True,
                attempt=AttemptPayload(text="I think so"),
            ),
            client_message_id=ClientMessageId("cmid-p9-3-tg-reply-after"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.CONFLICT
    hanging_is_cancelled(file_world, turn_id, action_id)
