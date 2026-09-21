"""F1–F3 + F5 — the crash windows of the active-teaching turn.

Each test drives a real, durable half-finished state and then re-enters
through the *same* entry point with the same ``client_message_id`` — the way
a retry after a crash actually arrives. What is pinned here:

F1  the continuation Gate facts are deterministic per turn, so a re-entry
    replays the recorded verdict instead of colliding with its own rows
    (before: a PRIMARY KEY conflict turned the retry into a hard failure and
    the hint was never delivered); the ladder phase is landed only *after* a
    successful delivery, so a crash between the two leaves the ladder where
    it was and the re-entry continues from there;
F2  an opening that was authorized but never delivered is re-dispatched on
    re-entry (RA §23 "CP2 crash → 继续同 action_id"), and a TeachingLockLease
    left behind by a dead runtime epoch is released by the epoch-based
    recovery sweep instead of sealing the conversation forever;
F3  an attempt is identified by (moment, user turn), so a re-entry after a
    crash between the attempt and its evaluation replays the durable attempt
    instead of recording a second one (which would inflate the §8 budget and
    orphan the first evaluation's evidence_proposal_refs);
F5  the §4 five-step order is witnessed — nothing may create the next
    teaching action while this turn's evaluation is not durable yet.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.learning.controller import LearningController
from elc.persona import ScriptedPersonaProvider
from elc.platform.db import epoch
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.types import GenerationActionIntentRecord
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import MomentState, PresentationPhase

from .conftest import CONV, make_lease, make_teaching_coordinator

REQUESTED_AT = "2026-09-21T13:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"
CANONICAL = "I think it is going to rain."


# ---------------------------------------------------------------------------
# injection doubles
# ---------------------------------------------------------------------------


class FailOnceGenerationStore:
    """The generation store with one injected failure: the next
    ``create_action`` whose action id ends in ``slot`` fails.

    Every other member delegates, so the assembly under test is the real one
    — only the one durable write the crash window is about is withheld.
    """

    def __init__(self, inner, slot: str) -> None:
        self._inner = inner
        self._slot = slot
        self.failures = 0

    def create_action(self, intent: GenerationActionIntentRecord):
        if self.failures == 0 and str(intent.action_id).endswith(self._slot):
            self.failures += 1
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="simulated outage before the action was created",
                )
            )
        return self._inner.create_action(intent)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class CrashingLearningController(LearningController):
    """The Learning authority face whose opportunity mint *raises*: the
    process dies between the durable evaluation and the evidence commit
    (F3's window) — a crash, not a handled degradation."""

    def __init__(self, store) -> None:
        super().__init__(store)
        self.crash_armed = True

    def record_opportunity(self, **kwargs):
        if self.crash_armed:
            self.crash_armed = False
            raise RuntimeError("simulated crash before the evidence commit")
        return super().record_opportunity(**kwargs)


class FailingEvaluationController(TeachingController):
    """The teaching face that refuses to record an evaluation (F5a): the
    flow must stop there, before any teaching action is planned."""

    def __init__(self, store) -> None:
        super().__init__(store)
        self.fail_next_evaluation = True

    def record_attempt_evaluation(self, evaluation):
        if self.fail_next_evaluation:
            self.fail_next_evaluation = False
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="injected: evaluation not durable",
                )
            )
        return super().record_attempt_evaluation(evaluation)


class TracingTeachingController(TeachingController):
    """Teaching face that appends its durable calls to a shared trace."""

    def __init__(self, store, trace: list[str]) -> None:
        super().__init__(store)
        self._trace = trace

    def record_attempt(self, attempt):
        self._trace.append("attempt")
        return super().record_attempt(attempt)

    def record_attempt_evaluation(self, evaluation):
        self._trace.append("evaluation")
        return super().record_attempt_evaluation(evaluation)

    def transition_moment(self, moment_id, transition, expected_state_version):
        if transition.lifecycle_state is not None:
            self._trace.append(f"moment:{transition.lifecycle_state.value}")
        return super().transition_moment(
            moment_id, transition, expected_state_version
        )

    def record_gate_allow(self, status, decision):
        self._trace.append("gate-allow")
        return super().record_gate_allow(status, decision)


class TracingGenerationStore:
    """Generation port that appends every action creation to the trace."""

    def __init__(self, inner, trace: list[str]) -> None:
        self._inner = inner
        self._trace = trace

    def create_action(self, intent: GenerationActionIntentRecord):
        self._trace.append(f"action:{intent.action_type.value}")
        return self._inner.create_action(intent)

    def __getattr__(self, name):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# assembly helpers
# ---------------------------------------------------------------------------


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycles,
    teaching,
    targets,
    *,
    provider=None,
    learning_controller=None,
) -> ConversationCoordinator:
    """The P3-1A/P3-1B assembly with every port passed straight through (the
    fixtures' helper borrows ports; the crash windows need the wrapped
    ones)."""

    from elc.persona import PersonaRuntime, PromptCompiler, ResponseValidator

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
        learning_controller=(
            learning_controller
            if learning_controller is not None
            else LearningController(learning)
        ),
        teaching=teaching,
        targets=targets,
    )


def _plain_coordinator(
    store, generation_store, fence, learning, decision_cycles, teaching, targets
) -> ConversationCoordinator:
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycles,
        teaching,
        targets,
    )


def _request(client_message_id: str) -> TeachingRequest:
    return TeachingRequest(
        conversation_id=CONV,
        focus_target_id=FOCUS_TARGET,
        client_message_id=ClientMessageId(client_message_id),
        requested_at=REQUESTED_AT,
    )


def _reply(coordinator, envelope, client_message_id: str):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=envelope,
            client_message_id=ClientMessageId(client_message_id),
            requested_at=REQUESTED_AT,
        )
    )


def _attempt_reply(cmid: str, text: str = CANONICAL):
    return (
        TeachingResponseEnvelope(
            control_intent=TeachingControlIntent.CONTINUE,
            attempt_present=True,
            attempt=AttemptPayload(text=text),
        ),
        cmid,
    )


def _hint_reply(cmid: str):
    return (
        TeachingResponseEnvelope(control_intent=TeachingControlIntent.ASK_HINT),
        cmid,
    )


def _open(coordinator, cmid: str = "cm-open"):
    result = coordinator.request_teaching(_request(cmid))
    assert isinstance(result, Ok), result
    return result.value


def _moment(teaching_controller, moment_id):
    result = teaching_controller.get_moment(moment_id)
    assert isinstance(result, Ok) and result.value is not None
    return result.value


# ---------------------------------------------------------------------------
# F1: the continuation Gate replays, and the phase lands after delivery
# ---------------------------------------------------------------------------


def test_f1_a_retry_replays_the_continuation_gate_and_delivers_the_hint(
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
    """The crash lands after the continuation ALLOW facts and before the hint
    action exists. The retry (same client_message_id) must read the recorded
    verdict back — not collide with its own rows — and deliver."""

    del conversation
    opening = _open(
        _plain_coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        )
    )
    flaky = FailOnceGenerationStore(generation_store, "hint")
    coordinator = _coordinator(
        store,
        flaky,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    envelope, cmid = _hint_reply("cm-hint-crash")
    crashed = _reply(coordinator, envelope, cmid)
    assert not isinstance(crashed, Ok)
    assert flaky.failures == 1
    # Durably: the Gate allowed the continuation, the ladder has not moved.
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_decision WHERE context ="
            " 'USER_REQUESTED_CONTINUE' AND decision = 'ALLOW'"
        ).fetchone()[0]
        == 1
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM generation_action_intent"
            " WHERE action_id LIKE '%-hint'"
        ).fetchone()[0]
        == 0
    )
    moment = _moment(teaching_controller, opening.moment_id)
    assert moment.lifecycle_state is MomentState.DECIDING_NEXT_ACTION
    assert moment.presentation_phase is PresentationPhase.INITIAL_PROMPT

    retried = _reply(coordinator, envelope, cmid)
    assert isinstance(retried, Ok), retried
    assert retried.value.delivery_kind == "HINT"
    assert retried.value.action_type == "TEACHING_HINT"
    assert retried.value.gate_decision == "ALLOW"
    # The durable fact replayed (one continuation decision, not two), one
    # hint action exists, and the ladder moved exactly one rung.
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_execution_status WHERE gate_context ="
            " 'USER_REQUESTED_CONTINUE'"
        ).fetchone()[0]
        == 1
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM generation_action_intent"
            " WHERE action_id LIKE '%-hint'"
        ).fetchone()[0]
        == 1
    )
    moment = _moment(teaching_controller, opening.moment_id)
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC
    assert moment.lifecycle_state is MomentState.AWAITING_USER


def test_f1_a_retry_after_a_gate_denial_replays_the_denial(
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
    """The replay guard is not ALLOW-only: a recorded DENY is replayed too,
    so a capped episode cannot be reopened by retrying the same turn."""

    del conversation
    opening = _open(
        _plain_coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        )
    )
    coordinator = _plain_coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    for index in range(3):
        failed = _reply(
            coordinator, *_attempt_reply(f"cm-fail-{index}", "not the answer")
        )
        assert isinstance(failed, Ok), failed
    # The third failure exhausted the hard attempt cap: the episode closed
    # with the closing reveal.
    assert failed.value.closure == "REVEALED"
    assert failed.value.limit_reason == "HARD_ATTEMPT_LIMIT"
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_decision WHERE context ="
            " 'USER_REQUESTED_CONTINUE' AND decision = 'DENY'"
        ).fetchone()[0]
        == 1
    )
    moment = _moment(teaching_controller, opening.moment_id)
    assert moment.lifecycle_state is MomentState.CLOSED
    # Retrying the same turn replays; nothing new is written and the moment
    # stays closed.
    replay = _reply(
        coordinator, *_attempt_reply("cm-fail-2", "not the answer")
    )
    assert isinstance(replay, Ok), replay
    assert replay.value.moment_state is MomentState.CLOSED
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_decision WHERE context ="
            " 'USER_REQUESTED_CONTINUE' AND decision = 'DENY'"
        ).fetchone()[0]
        == 1
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM gate_decision WHERE context ="
            " 'USER_REQUESTED_CONTINUE'"
        ).fetchone()[0]
        == 3
    )
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 3


def test_f1_a_crash_after_delivery_reconciles_the_ladder_on_re_entry(
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
    """The other half of the window: the hint went out and the crash landed
    before the rung did. The re-entry must reconcile the ladder from the
    *delivered* action (STATE_MACHINES §3: evidence may never claim less
    support than the material really shown) without sending a second
    message."""

    del conversation
    coordinator = _plain_coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opening = _open(coordinator)
    envelope, cmid = _hint_reply("cm-hint-landed")
    delivered = _reply(coordinator, envelope, cmid)
    assert isinstance(delivered, Ok), delivered
    assert delivered.value.delivery_kind == "HINT"

    # The crash state: the message and the action are durable, the phase is
    # still where it was before the landing.
    db.execute(
        "UPDATE teaching_moment SET presentation_phase = ?, support_level = ?"
        " WHERE moment_id = ?",
        ("INITIAL_PROMPT", "CONTEXT_ONLY", opening.moment_id),
    )
    db.commit()
    rewound = _moment(teaching_controller, opening.moment_id)
    assert rewound.presentation_phase is PresentationPhase.INITIAL_PROMPT
    assert rewound.support_level.value == "CONTEXT_ONLY"

    replay = _reply(coordinator, envelope, cmid)
    assert isinstance(replay, Ok), replay
    assert replay.value.turn_id == delivered.value.turn_id
    # No second message was sent; the transcript is unchanged.
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 2
    moment = _moment(teaching_controller, opening.moment_id)
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC
    assert moment.support_level.value == "SEMANTIC_HINT"
    assert moment.lifecycle_state is MomentState.AWAITING_USER

    # Idempotent: another re-entry changes nothing (the ladder is one-way).
    again = _reply(coordinator, envelope, cmid)
    assert isinstance(again, Ok), again
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 2
    moment = _moment(teaching_controller, opening.moment_id)
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC

    # And the reconciled rung is the one a real attempt is recorded against:
    # a later attempt claims that support, not the pre-hint support.
    later = _reply(coordinator, *_attempt_reply("cm-after-reconcile", "wrong"))
    assert isinstance(later, Ok), later
    attempt = db.execute(
        "SELECT support_level_before_attempt FROM attempt_record"
    ).fetchone()
    assert attempt == ("SEMANTIC_HINT",)


def test_f1_a_failed_continuation_delivery_aborts_without_advancing_the_ladder(
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
    """The other side of "land after delivery": when the hint could not be
    produced, the rung must NOT move — the episode aborts with the §7
    delivery-failure word and releases its lock (RA §21), rather than
    pretending support that was never shown or sitting live forever."""

    del conversation
    from elc.persona import ScriptedPersonaProvider
    from elc.persona.types import ProviderOutput

    provider = ScriptedPersonaProvider(
        (ProviderOutput(text="hello", error=None),)
        + (ProviderOutput(text=None, error="provider down"),) * 6
    )
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        provider=provider,
    )
    opening = _open(coordinator)
    assert opening.outcome == "REPLIED_FULL"
    envelope, cmid = _hint_reply("cm-hint-down")
    result = _reply(coordinator, envelope, cmid)
    assert isinstance(result, Ok), result
    assert result.value.moment_state is MomentState.CLOSED
    assert result.value.closure == "DELIVERY_FAILURE"
    assert result.value.outcome == "NO_ASSISTANT_OUTPUT"
    moment = _moment(teaching_controller, opening.moment_id)
    assert moment.abort_reason == "DELIVERY_FAILURE"
    # The rung never moved: nothing was shown, so nothing is claimed.
    assert moment.presentation_phase is PresentationPhase.INITIAL_PROMPT
    assert moment.support_level.value == "CONTEXT_ONLY"
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    )
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# F2: the opening re-dispatch and the orphan lock
# ---------------------------------------------------------------------------

def test_f2_re_entry_redispays_the_same_opening_action(
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
    """CP2 committed but the opening delivery never happened: the re-entry
    continues the *same* action id instead of replaying a stale PREPARED row,
    and the moment reaches AWAITING_USER."""

    del conversation
    flaky = FailOnceGenerationStore(generation_store, "teaching-open")
    coordinator = _coordinator(
        store,
        flaky,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    crashed = coordinator.request_teaching(_request("cm-open-crash"))
    assert not isinstance(crashed, Ok)
    assert flaky.failures == 1
    rows = db.execute(
        "SELECT action_id, status FROM generation_action_intent"
    ).fetchall()
    assert len(rows) == 1
    action_id, status = rows[0]
    assert status == "PREPARED"
    assert (
        db.execute("SELECT lifecycle_state FROM teaching_moment").fetchone()[0]
        == "OPENING"
    )
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
        == 1
    )

    resumed = coordinator.request_teaching(_request("cm-open-crash"))
    assert isinstance(resumed, Ok), resumed
    assert resumed.value.moment_id is not None
    assert str(resumed.value.action_id) == str(action_id)
    assert resumed.value.moment_state is MomentState.AWAITING_USER
    assert resumed.value.outcome == "REPLIED_FULL"
    # One action row, one message, terminal turn — the same action continued.
    assert (
        db.execute("SELECT COUNT(*) FROM generation_action_intent").fetchone()[0]
        == 1
    )
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    turn = db.execute(
        "SELECT status, turn_outcome FROM turn_record WHERE turn_id = ?",
        (resumed.value.turn_id,),
    ).fetchone()
    assert turn == ("COMPLETED", "REPLIED_FULL")


def test_f2_an_orphan_lock_from_a_dead_epoch_is_released(
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
    """A lock whose owning turn belongs to an older runtime epoch is residue:
    the sweep releases it and closes the moment with SYSTEM_RECOVERY_ABORT,
    which is what lets a later request open again."""

    del conversation
    old = _open(
        _plain_coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        ),
        cmid="cm-orphan-open",
    )
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 1
    )

    new_fence = epoch.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)
    new_coordinator = _coordinator(
        new_store,
        SqliteGenerationStore(db, new_fence),
        new_fence,
        learning,
        SqliteDecisionCycleStore(db, new_fence),
        TeachingController(SqliteTeachingStore(db, new_fence)),
        target_provider,
    )
    recovered = new_coordinator.recover_orphan_teaching()
    assert isinstance(recovered, Ok), recovered
    assert recovered.value == (str(old.moment_id),)
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    )
    assert db.execute(
        "SELECT lifecycle_state, abort_reason FROM teaching_moment"
        " WHERE moment_id = ?",
        (old.moment_id,),
    ).fetchone() == ("CLOSED", "SYSTEM_RECOVERY_ABORT")

    # The conversation is unsealed: a new request opens a new moment.
    reopened = new_coordinator.request_teaching(_request("cm-orphan-reopen"))
    assert isinstance(reopened, Ok), reopened
    assert reopened.value.gate_decision == "ALLOW"
    assert reopened.value.moment_id is not None
    assert reopened.value.moment_id != old.moment_id
    assert (
        db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 2
    )


def test_f2_recovery_leaves_a_live_epoch_lock_alone(
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
    """The sweep is epoch-based, not age-based: a lock owned by the current
    epoch is a real mutual-exclusion fact and must survive."""

    del conversation
    opened = _open(
        _plain_coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        ),
        cmid="cm-live-open",
    )
    recovered = teaching_controller.recover_orphan_locks()
    assert isinstance(recovered, Ok), recovered
    assert recovered.value == ()
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 1
    )
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.lifecycle_state is MomentState.AWAITING_USER
    assert moment.abort_reason is None


# ---------------------------------------------------------------------------
# F3: one user turn contributes at most one attempt
# ---------------------------------------------------------------------------


def test_f3_re_entry_after_the_evaluation_does_not_double_count_the_attempt(
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
    """The crash sits between the durable evaluation and the evidence commit.
    The re-entry must reuse the attempt (one row, index 1), replay the
    evaluation and complete the evidence chain — the first evaluation's
    proposal ref must not dangle."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        learning_controller=CrashingLearningController(learning),
    )
    opening = _open(coordinator)
    envelope, cmid = _attempt_reply("cm-attempt-crash")
    try:
        _reply(coordinator, envelope, cmid)
    except RuntimeError:
        pass  # the simulated process death
    else:  # pragma: no cover - the injection always raises
        raise AssertionError("the injected crash did not fire")

    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM attempt_evaluation_record").fetchone()[0]
        == 1
    )
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    attempt_id = db.execute("SELECT attempt_id FROM attempt_record").fetchone()[0]
    refs = db.execute(
        "SELECT evidence_proposal_refs FROM attempt_evaluation_record"
    ).fetchone()
    assert refs is not None and attempt_id in str(refs[0])

    retried = _reply(coordinator, envelope, cmid)
    assert isinstance(retried, Ok), retried
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM attempt_evaluation_record").fetchone()[0]
        == 1
    )
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 1
    assert db.execute(
        "SELECT attempt_id, attempt_index FROM attempt_record"
    ).fetchone() == (attempt_id, 1)
    claim = db.execute(
        "SELECT evidence_group_id FROM evidence_claim"
    ).fetchone()
    assert claim is not None and claim[0] == f"eg-teaching-{attempt_id}"
    assert str(retried.value.attempt_id) == str(attempt_id)
    # The successful attempt completes the episode as usual.
    assert retried.value.moment_state is MomentState.CLOSED
    assert retried.value.closure == "SUCCESS_UNSUPPORTED"
    assert _moment(teaching_controller, opening.moment_id).attempt_index == 1


def test_f3_a_second_reply_turn_is_a_second_attempt(
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
    """The idempotency key is the *user turn*, not the moment: a genuinely
    new reply turn still records its own attempt."""

    del conversation
    coordinator = _plain_coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opening = _open(coordinator)
    first = _reply(coordinator, *_attempt_reply("cm-attempt-1", "nope"))
    assert isinstance(first, Ok), first
    assert first.value.evaluation_outcome == "FAILURE"
    assert first.value.moment_state is MomentState.AWAITING_USER

    second = _reply(coordinator, *_attempt_reply("cm-attempt-2", "still nope"))
    assert isinstance(second, Ok), second
    assert second.value.evaluation_outcome == "FAILURE"
    assert [
        row[0]
        for row in db.execute(
            "SELECT attempt_index FROM attempt_record ORDER BY attempt_index"
        ).fetchall()
    ] == [1, 2]
    assert (
        db.execute(
            "SELECT COUNT(*) FROM attempt_record WHERE moment_id = ?",
            (opening.moment_id,),
        ).fetchone()[0]
        == 2
    )


# ---------------------------------------------------------------------------
# F5: order witnesses
# ---------------------------------------------------------------------------


def test_f5_no_teaching_action_is_created_before_the_evaluation_is_durable(
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
    """Failure injection on the evaluation write: the turn must stop there —
    no next teaching action, no second message."""

    del conversation
    failing = FailingEvaluationController(teaching_controller._store)
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        failing,
        target_provider,
    )
    _open(coordinator)
    result = _reply(coordinator, *_attempt_reply("cm-eval-fails"))
    assert not isinstance(result, Ok)
    assert result.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    # The attempt landed (the first half of §4 step 3), the evaluation did
    # not — and nothing was planned or delivered on top of that.
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM attempt_evaluation_record").fetchone()[0]
        == 0
    )
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert (
        db.execute(
            "SELECT COUNT(*) FROM generation_action_intent WHERE action_id NOT"
            " LIKE '%-teaching-open'"
        ).fetchone()[0]
        == 0
    )
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1


def test_f5_the_envelope_five_steps_are_witnessed_in_order(
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
    """STATE_MACHINES §4's order, witnessed on the durable calls: parse →
    detect attempt → evaluate + durable record → apply the control intent →
    next action. The evaluation is durable before the moment leaves its
    evaluating slot, and the action is created last."""

    del conversation
    trace: list[str] = []
    coordinator = _coordinator(
        store,
        TracingGenerationStore(generation_store, trace),
        fence,
        learning,
        decision_cycle_store,
        TracingTeachingController(teaching_controller._store, trace),
        target_provider,
    )
    _open(coordinator)

    # A control-only reply: steps 1-2 detect no attempt (no attempt and no
    # evaluation call), step 4 walks the §1 reply path, step 5 authorizes
    # (Gate) and then dispatches — and the ladder lands only after the
    # message really went out (review F1).
    trace.clear()
    hint_result = _reply(coordinator, *_hint_reply("cm-order-hint"))
    assert isinstance(hint_result, Ok), hint_result
    assert "attempt" not in trace
    assert "evaluation" not in trace
    assert trace.index("moment:EVALUATING") < trace.index(
        "moment:DECIDING_NEXT_ACTION"
    )
    assert trace.index("moment:DECIDING_NEXT_ACTION") < trace.index("gate-allow")
    assert trace.index("gate-allow") < trace.index("action:TEACHING_HINT")
    assert trace.index("action:TEACHING_HINT") < trace.index(
        "moment:AWAITING_USER"
    )
    assert trace.count("action:TEACHING_HINT") == 1

    # An attempt reply: step 3 records the attempt and then its evaluation
    # (in that order) before the Gate and before the next action.
    trace.clear()
    attempt_result = _reply(coordinator, *_attempt_reply("cm-order-attempt", "wrong"))
    assert isinstance(attempt_result, Ok), attempt_result
    assert trace.index("attempt") < trace.index("evaluation")
    assert trace.index("evaluation") < trace.index("gate-allow")
    assert trace.index("gate-allow") < trace.index("action:TEACHING_HINT")
    # The evaluation is durable while the moment is still evaluating: the
    # DECIDING transition comes after it.
    assert trace.index("evaluation") < trace.index("moment:DECIDING_NEXT_ACTION")
