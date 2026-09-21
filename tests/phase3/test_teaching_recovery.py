"""F5 + F9 (DEC-OPI-2babb21e-….34) — the teaching turn's recovery face.

F5 — post-cycle DEGRADED crash re-entry. The P3-1A flow may degrade a cycle
on LEARNING_SNAPSHOT and then repair it once; a crash *between* the DEGRADED
fact and the successor cycle left the frozen cycle as the only durable
record, and the old re-entry replayed "no teaching" without finishing the
repair. The re-entry now recognises exactly that state (newest
GateExecutionStatus = DEGRADED, no ``cycle_index + 1`` successor, no repair
spent yet) and finishes the one repair — the same at-most-once semantics,
now expressed on the durable lineage instead of a call-frame flag.

F9 — the recovery dictionary must mesh with the teaching command turn. The
generic recovery path identifies a DECIDING turn as RESUME_DECISION; for a
teaching turn that resume is the teaching entry point (its durable payload
says so), never the normal persona loop — answering an empty utterance would
fabricate a reply to silence.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.learning.controller import LearningController
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db import epoch
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.recovery import StartupRecoveryScanner, recovery_disposition
from elc.runtime.types import InputEnvelope, TurnStatus
from elc.teaching.envelope import TeachingControlIntent, TeachingResponseEnvelope
from elc.teaching.request import TeachingRequest

from .conftest import CONV, make_lease, make_teaching_coordinator
from .test_snapshot_conflict_paths import CommittingTargetProvider, _commit_evidence

REQUESTED_AT = "2026-09-21T12:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"


class CrashingDecisionCycles:
    """The DecisionCycleStore with one crash: creating the turn's *repair*
    cycle fails, which is exactly the F5 window — the DEGRADED row is already
    durable, the successor cycle is not. Everything else delegates."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.crashed = False

    def record_decision_cycle(self, **kwargs):
        cycle_id = str(kwargs["decision_cycle_id"])
        if not self.crashed and cycle_id.endswith("-repair1"):
            self.crashed = True
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="simulated crash between DEGRADED and cycle+1",
                )
            )
        return self._inner.record_decision_cycle(**kwargs)

    def get_decision_cycle(self, decision_cycle_id):
        return self._inner.get_decision_cycle(decision_cycle_id)

    def get_active_decision_cycle(self, turn_id):
        return self._inner.get_active_decision_cycle(turn_id)

    def get_turn_cycle(self, turn_id, cycle_index):
        return self._inner.get_turn_cycle(turn_id, cycle_index)


def _coordinator_with(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycles,
    teaching_controller,
    target_provider,
    *,
    provider: ScriptedPersonaProvider | None = None,
) -> ConversationCoordinator:
    """The P3-1A assembly with an explicitly injected DecisionCycle store.

    ``make_teaching_coordinator`` borrows the generation fixture's own cycle
    store; these tests need the *wrapping* store (the crash), so the
    assembly is built here with that port passed straight through.
    """

    persona = PersonaRuntime(
        actions=generation_store,
        provider=provider if provider is not None else ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=make_lease(fence),
        conversation_commands=store,
        conversation_queries=store,
        persona=persona,
        generation_actions=generation_store,
        learning=learning,
        decision_cycles=decision_cycles,
        learning_controller=LearningController(learning),
        teaching=teaching_controller,
        targets=target_provider,
    )


def _request(client_message_id: str = "cm-f5") -> TeachingRequest:
    return TeachingRequest(
        conversation_id=CONV,
        focus_target_id=FOCUS_TARGET,
        client_message_id=ClientMessageId(client_message_id),
        requested_at=REQUESTED_AT,
    )


def _begin_turn_for(coordinator: ConversationCoordinator, client_message_id: str):
    return coordinator.begin_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{client_message_id}"),
                client_message_id=ClientMessageId(client_message_id),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw",
                received_at=REQUESTED_AT,
            ),
            raw_content="",
            runtime_version="runtime-v1",
        )
    )


def _seed_stale_snapshot(learning, store, suffix: str) -> None:
    _commit_evidence(learning, store, f"cm-seed-{suffix}", f"eg-seed-{suffix}")
    learning.rebuild_learner_state(TargetId(FOCUS_TARGET), "TEXT_PRODUCTION")


def test_f5_reentry_finishes_the_repair_the_crash_interrupted(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    _seed_stale_snapshot(learning, store, "f5")
    crashing = CrashingDecisionCycles(decision_cycle_store)
    coordinator = _coordinator_with(
        store,
        generation_store,
        fence,
        learning,
        crashing,
        teaching_controller,
        CommittingTargetProvider(learning, store, commits=1),
    )

    # The crash: the DEGRADED row is durable, the repair cycle is not.
    first = coordinator.request_teaching(_request())
    assert not isinstance(first, Ok)
    assert crashing.crashed
    statuses = db.execute(
        "SELECT status, missing_or_unknown FROM gate_execution_status"
        " ORDER BY created_at, gate_execution_status_id"
    ).fetchall()
    assert statuses == [("DEGRADED", '["LEARNING_SNAPSHOT"]')]
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 0

    # The re-entry: same turn (same client_message_id), and the repair the
    # crash interrupted is finished exactly once.
    second = coordinator.request_teaching(_request())
    assert isinstance(second, Ok), second
    assert second.value.gate_decision == "ALLOW"
    assert second.value.moment_id is not None
    cycles = db.execute(
        "SELECT cycle_index FROM decision_cycle WHERE turn_id = ?"
        " ORDER BY cycle_index",
        (second.value.turn_id,),
    ).fetchall()
    assert [row[0] for row in cycles] == [0, 1]
    statuses = db.execute(
        "SELECT status FROM gate_execution_status ORDER BY created_at,"
        " gate_execution_status_id"
    ).fetchall()
    assert [row[0] for row in statuses] == ["DEGRADED", "SUCCEEDED"]

    # A third call replays the durable outcome: no third cycle, no re-run.
    third = coordinator.request_teaching(_request())
    assert isinstance(third, Ok), third
    assert third.value.moment_id == second.value.moment_id
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 1


def test_f5_a_repair_cycle_that_degrades_does_not_spawn_a_third_cycle(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """At most one repair stays true on re-entry: a repair cycle that itself
    degrades is the trace, not the start of another cycle."""

    del conversation
    _seed_stale_snapshot(learning, store, "f5b")
    coordinator = _coordinator_with(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        CommittingTargetProvider(learning, store, commits=2),
    )
    result = coordinator.request_teaching(_request("cm-f5-twice"))
    assert isinstance(result, Ok), result
    assert result.value.moment_id is None
    assert result.value.gate_execution_status == "DEGRADED"
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 2
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status WHERE status = 'DEGRADED'"
        ).fetchone()[0]
        == 2
    )
    # The re-entry replays the frozen trace instead of burning cycle 2.
    again = coordinator.request_teaching(_request("cm-f5-twice"))
    assert isinstance(again, Ok), again
    assert again.value.moment_id is None
    assert db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0] == 2


def test_f5_reentry_through_the_persona_loop_is_refused_while_the_turn_is_live(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """F9: a live (nonterminal) teaching command turn belongs to the
    teaching entry points — the generic persona loop must refuse it."""

    del conversation
    _seed_stale_snapshot(learning, store, "f9")
    crashing = CrashingDecisionCycles(decision_cycle_store)
    coordinator = _coordinator_with(
        store,
        generation_store,
        fence,
        learning,
        crashing,
        teaching_controller,
        CommittingTargetProvider(learning, store, commits=1),
    )
    crashed = coordinator.request_teaching(_request("cm-f9-crash"))
    assert not isinstance(crashed, Ok)
    # The teaching turn is the one left at DECIDING (the side-commit turns of
    # the seeded evidence are separate, terminal-agnostic turns).
    rows = db.execute(
        "SELECT status FROM turn_record WHERE status = 'DECIDING'"
    ).fetchall()
    assert [row[0] for row in rows] == ["DECIDING"]

    begin = _begin_turn_for(coordinator, "cm-f9-crash")
    assert not isinstance(begin, Ok)
    assert begin.error.code is DomainErrorCode.CONFLICT
    assert "teaching command turn" in begin.error.message


def test_f9_the_recovery_dictionary_names_the_teaching_resume(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """F9: the §24.1 dictionary maps a DECIDING teaching turn to
    RESUME_DECISION — the teaching entry point — and a *terminal* teaching
    turn is not recoverable work at all."""

    del conversation
    assert recovery_disposition(TurnStatus.DECIDING) == "RESUME_DECISION"
    assert (
        recovery_disposition(TurnStatus.GENERATING)
        == "RESUME_ACTION_BY_STABLE_ACTION_ID"
    )

    coordinator = make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = coordinator.request_teaching(_request("cm-f9-done"))
    assert isinstance(opened, Ok), opened
    turn_id = opened.value.turn_id

    # A new epoch adopts the world; the completed teaching turn is not
    # recoverable work, so the scanner reports nothing for it (the terminal
    # outcome IS the recovery).
    new_fence = epoch.open_runtime_epoch(db)
    scanner = StartupRecoveryScanner(source=store, lease=make_lease(new_fence))
    scanned = scanner.scan()
    assert isinstance(scanned, Ok)
    assert all(plan.id != turn_id for plan in scanned.value)


def test_f9_a_teaching_reply_turn_reentered_through_its_own_entry_point_replays(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    coordinator = make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = coordinator.request_teaching(_request("cm-f9-replay"))
    assert isinstance(opened, Ok)
    reply = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.SKIP
            ),
            client_message_id=ClientMessageId("cm-f9-reply"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(reply, Ok), reply
    before = db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0]

    replay = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.SKIP
            ),
            client_message_id=ClientMessageId("cm-f9-reply"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(replay, Ok), replay
    assert replay.value.turn_id == reply.value.turn_id
    assert replay.value.outcome == reply.value.outcome
    assert db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0] == before
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 0
