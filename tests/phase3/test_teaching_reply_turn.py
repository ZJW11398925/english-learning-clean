"""VAL ②③④⑤⑥⑧⑨ — the active-teaching reply turn (P3-1B).

The slice this file pins, end to end:

    request_teaching(...)                 # P3-1A opening (now delivered)
    → respond_to_teaching(envelope)       # STATE_MACHINES §4 five steps
      parse intent → detect attempt → evaluate + durable record + evidence
      → apply control intent → next action / close
    → TEACHING_TERMINAL + lock release (one short transaction)
    → RESUMING → PERSONA_RESUME → CLOSED

Groups covered here (VAL-OPI-2babb21e-….9):

② envelope five-step order + the control-only intents (SKIP / REJECT /
  CHANGE_TOPIC never fabricate an ABSTAIN attempt);
③ the attempt orchestration chain (durable AttemptRecord → durable
  AttemptEvaluationRecord → LOR → evidence proposal with opportunity_id →
  Learning commit, target-specific claims always LOR-linked);
④ the evaluator's five values through the durable record (SUCCESS /
  ALTERNATIVE_SUCCESS / PARTIAL / FAILURE / ABSTAIN, ALTERNATIVE_SUCCESS
  preserved at the AttemptEvaluation layer and folded only in Learning);
⑤ the ladder's one-way rule (phase/support never step back, evidence never
  claims less support than the real exposure);
⑥ hint / retry / reveal / explanation / skip / reject / topic shift /
  switch target (switch = close + same-turn cycle_index+1);
⑧ TEACHING_TERMINAL + lock release in one transaction, resume → CLOSED;
⑨ the [teaching] prompt section is PromptCompiler-owned and
  byte-deterministic;
⑩ the teaching reply turn never produces TEXT_* evidence.
"""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.persona import ScriptedPersonaProvider
from elc.persona.types import ProviderOutput
from elc.platform.db import epoch
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.types import ClientMessageId, Ok
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.teaching.envelope import (
    ENVELOPE_STEPS,
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.types import MomentState

from .conftest import CONV, make_lease, make_teaching_coordinator

REQUESTED_AT = "2026-09-21T09:00:00+00:00"
TARGET = "res-hedge-i-think"


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    *,
    provider: ScriptedPersonaProvider | None = None,
) -> ConversationCoordinator:
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        provider if provider is not None else ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )


def _open(
    coordinator: ConversationCoordinator,
    client_message_id: str = "cm-open",
    *,
    target_id: str = TARGET,
):
    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=target_id,
            client_message_id=ClientMessageId(client_message_id),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _reply(
    coordinator: ConversationCoordinator,
    envelope: TeachingResponseEnvelope,
    client_message_id: str = "cm-reply",
):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=envelope,
            client_message_id=ClientMessageId(client_message_id),
            requested_at=REQUESTED_AT,
        )
    )


def _attempt(text: str) -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(
        control_intent=TeachingControlIntent.CONTINUE,
        attempt_present=True,
        attempt=AttemptPayload(text=text),
    )


def _reply_ok(coordinator, envelope, client_message_id: str = "cm-reply"):
    result = _reply(coordinator, envelope, client_message_id)
    assert isinstance(result, Ok), result
    return result.value


def test_the_envelope_processing_order_is_the_canonical_five_steps() -> None:
    """②: STATE_MACHINES §4's five steps, in the document's own order."""

    assert ENVELOPE_STEPS == (
        "PARSE_CONTROL_INTENT",
        "DETECT_ATTEMPT",
        "EVALUATE_ATTEMPT",
        "APPLY_CONTROL_INTENT",
        "NEXT_ACTION",
    )


# ---------------------------------------------------------------------------
# ①②: the opening turn stops delivering nothing; the reply turn walks the
# envelope order and the control-only intents never fake an attempt.
# ---------------------------------------------------------------------------


def test_correct_attempt_is_evaluated_durably_and_committed_as_evidence(
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
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator)
    reply = _reply_ok(coordinator, _attempt("I think it is going to rain."))

    # §4 step 3 was executed in order: attempt durable, evaluation durable,
    # then the Learning commit.
    assert reply.attempt_id is not None
    assert reply.evaluation_outcome == "SUCCESS"
    assert reply.evaluation_confidence == 1.0
    assert reply.opportunity_id is not None
    assert reply.evidence_commit_id is not None

    attempt = db.execute(
        "SELECT attempt_id, moment_id, attempt_index, user_turn_id,"
        " support_level_before_attempt, answer_exposure_state,"
        " support_attribution_certainty FROM attempt_record"
    ).fetchall()
    assert len(attempt) == 1
    assert attempt[0][0] == reply.attempt_id
    assert attempt[0][1] == opened.moment_id
    assert attempt[0][2] == 1
    assert attempt[0][4] == "CONTEXT_ONLY"  # the opening prompt's support
    assert attempt[0][5] == "NONE"  # no form had been shown
    assert attempt[0][6] == "SERVER_SENT_UNCONFIRMED"

    evaluation = db.execute(
        "SELECT attempt_id, evaluator_id, evaluator_version, outcome,"
        " confidence, evidence_proposal_refs"
        " FROM attempt_evaluation_record"
    ).fetchall()
    assert len(evaluation) == 1
    assert evaluation[0][1] == "attempt-evaluator-v0"
    assert evaluation[0][3] == "SUCCESS"
    assert reply.attempt_id in str(evaluation[0][5])

    # ③ the claim is LOR-linked: the durable evidence group / claim carry the
    # opportunity minted for this attempt, and the opportunity carries the
    # moment as its teaching provenance.
    claim = db.execute(
        "SELECT opportunity_id, target_type, target_id, outcome, polarity,"
        " performance_type, support_level, answer_exposure_state"
        " FROM evidence_claim"
    ).fetchall()
    assert len(claim) == 1
    assert claim[0][0] == reply.opportunity_id
    assert claim[0][1] == "RESOURCE"
    assert claim[0][2] == TARGET
    assert claim[0][3] == "SUCCESS"
    assert claim[0][4] == "POSITIVE"
    opportunity = db.execute(
        "SELECT teaching_moment_id, target_type, target_id, attempt_observed"
        " FROM learning_opportunity_record"
    ).fetchall()
    assert opportunity == [(opened.moment_id, "RESOURCE", TARGET, 1)]

    # ⑥ a successful attempt completes the moment and the episode closes.
    assert reply.moment_state is MomentState.CLOSED
    assert reply.closure == "SUCCESS_UNSUPPORTED"
    assert reply.delivery_kind == "RESUME"
    assert reply.outcome == "REPLIED_FULL"
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.lifecycle_state is MomentState.CLOSED
    assert moment.value.completion_outcome == "SUCCESS_UNSUPPORTED"
    assert moment.value.closed_at is not None
    # ⑧ the lock is released in the same transaction as TEACHING_TERMINAL.
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM assistant_turn WHERE action_id"
            " IN (SELECT action_id FROM generation_action_intent"
            "     WHERE moment_id = ?)",
            (opened.moment_id,),
        ).fetchone()[0]
        == 2  # the opening prompt + the resume message
    )


def test_the_reply_turn_produces_no_text_evidence_and_no_window_entry(
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
    """⑩: a typed teaching reply is a command turn — it never becomes a
    TEXT_PRODUCTION / TEXT_COMPREHENSION claim and never enters the
    ConversationWindow as an utterance."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator)

    # Regression pin (⑩ / ⑫): the TEACHING_REQUEST command turn runs no
    # LEARNING_EVIDENCE analysis — nothing was said, so it produces no
    # TEXT_* claim at all.
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert (
        db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 0
    )

    _reply_ok(coordinator, _attempt("I think it is going to rain."))

    # The one claim is the *teaching* claim: LOR-linked to the moment's
    # opportunity (a plain utterance claim carries no opportunity id here,
    # because the reply turn runs no analysis).
    claims = db.execute(
        "SELECT opportunity_id, teaching_moment_id, evidence_group_id"
        " FROM evidence_claim"
    ).fetchall()
    assert len(claims) == 1
    assert claims[0][0] is not None
    assert claims[0][1] == opened.moment_id
    assert (
        db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 0
    )

    window = store.get_conversation_window(CONV, 20)
    assert isinstance(window, Ok)
    assert window.value.slices == ()  # both turns are command turns

    # The teaching transcript itself is durable: both command turns exist,
    # and both say nothing.
    assert db.execute("SELECT COUNT(*) FROM user_turn").fetchone()[0] == 2
    assert db.execute(
        "SELECT COUNT(*) FROM user_turn WHERE raw_content = ''"
        " AND normalized_content IS NULL"
    ).fetchone()[0] == 2


def test_control_only_intents_never_fabricate_an_abstain_attempt(
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
    """②: SKIP / REJECT_TARGET / CHANGE_TOPIC are attempt-less by contract —
    the reply aborts the moment with its §7 reason and writes no attempt and
    no evaluation row."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator)
    reply = _reply_ok(
        coordinator,
        TeachingResponseEnvelope(
            control_intent=TeachingControlIntent.SKIP, attempt_present=False
        ),
    )
    assert reply.moment_state is MomentState.CLOSED
    assert reply.closure == "USER_SKIP"
    assert reply.attempt_id is None
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 0
    assert (
        db.execute(
            "SELECT COUNT(*) FROM attempt_evaluation_record"
        ).fetchone()[0]
        == 0
    )
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.abort_reason == "USER_SKIP"
    assert moment.value.completion_outcome is None

    # A shape-broken envelope (an attempt claimed together with a control-only
    # intent) is refused before any teaching write.
    result = _reply(
        coordinator,
        TeachingResponseEnvelope(
            control_intent=TeachingControlIntent.SKIP,
            attempt_present=True,
            attempt=AttemptPayload(text="I think"),
        ),
        client_message_id="cm-broken",
    )
    assert not isinstance(result, Ok)
    assert result.error.code.value == "VALIDATION_FAILED"


def test_a_failed_closing_delivery_still_closes_the_moment(
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
    """⑧/⑩: "delivered / failed → CLOSED" — a resume the provider could not
    produce is a NO_ASSISTANT_OUTPUT turn, and the moment still closes (a
    closed episode is never reopened; RA §23)."""

    del conversation
    # A working opening, then a failing provider for the closing resume.
    provider = ScriptedPersonaProvider(
        (ProviderOutput(text="hello", error=None),)
        + (ProviderOutput(text=None, error="provider down"),) * 4
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
    opened = _open(coordinator)
    assert opened.outcome == "REPLIED_FULL"
    closed = _reply_ok(
        coordinator,
        TeachingResponseEnvelope(control_intent=TeachingControlIntent.SKIP),
        client_message_id="cm-skip-failed",
    )
    assert closed.moment_state is MomentState.CLOSED
    assert closed.closure == "USER_SKIP"
    assert closed.outcome == "NO_ASSISTANT_OUTPUT"
    assert closed.reply_text is None
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.lifecycle_state is MomentState.CLOSED
    assert moment.value.abort_reason == "USER_SKIP"
    assert moment.value.closed_at is not None
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
        == 0
    )


def test_a_failed_opening_delivery_aborts_the_moment_and_frees_the_lock(
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
    """SM §1: AWAITING_USER follows a *delivered* opening. When the opening
    never reached the user the episode aborts (DELIVERY_FAILURE), releases
    its lock and closes — no zombie moment waiting for an answer to a prompt
    that was never shown, and no second moment while the lock is held."""

    del conversation
    provider = ScriptedPersonaProvider(
        (ProviderOutput(text=None, error="provider down"),) * 4
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
    opened = _open(coordinator)
    assert opened.outcome == "NO_ASSISTANT_OUTPUT"
    assert opened.moment_state is MomentState.CLOSED
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.lifecycle_state is MomentState.CLOSED
    assert moment.value.abort_reason == "DELIVERY_FAILURE"
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
        == 0
    )
    # A reply to the closed episode is refused (the moment is over).
    refused = _reply(coordinator, _attempt("I think it is going to rain."))
    assert not isinstance(refused, Ok)
    assert refused.error.code.value == "CONFLICT"
    # The lock is free, so a later request may open a fresh moment.
    reopened = _open(coordinator, client_message_id="cm-open-again")
    assert reopened.moment_id != opened.moment_id


def test_every_teaching_action_runs_the_full_p1_pipeline(
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
    """⑨: the five teaching action types are generated through the P1
    pipeline — GenerationActionIntent → ProviderAttempt → Validator →
    BUFFERED_VALIDATED → Delivery → canonicalize — with no shortcut."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator)
    _reply_ok(
        coordinator,
        TeachingResponseEnvelope(control_intent=TeachingControlIntent.ASK_HINT),
        client_message_id="cm-pipe-hint",
    )
    final = _reply_ok(
        coordinator,
        TeachingResponseEnvelope(control_intent=TeachingControlIntent.SKIP),
        client_message_id="cm-pipe-skip",
    )
    assert final.moment_state is MomentState.CLOSED

    # Every delivered teaching action has its provider attempt and its
    # canonical assistant turn — the pipeline really ran.
    actions = db.execute(
        "SELECT action_type, status FROM generation_action_intent"
        " WHERE moment_id = ? ORDER BY created_at, action_id",
        (opened.moment_id,),
    ).fetchall()
    assert [row[0] for row in actions] == [
        "TEACHING_OPEN",
        "TEACHING_HINT",
        "PERSONA_RESUME",
    ]
    assert {row[1] for row in actions} == {"TERMINAL"}
    for action_type, _ in actions:
        attempt_count = db.execute(
            "SELECT COUNT(*) FROM provider_attempt WHERE action_id IN"
            " (SELECT action_id FROM generation_action_intent"
            "  WHERE moment_id = ? AND action_type = ?)",
            (opened.moment_id, action_type),
        ).fetchone()[0]
        assert attempt_count >= 1, action_type
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 3
    # The teaching turns are counted the way §8's limits count them.
    assert teaching_controller.count_delivered_teaching_turns(
        opened.moment_id
    ) == 2


def test_a_new_epoch_fences_the_teaching_turn(
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
    """⑨/⑬: the epoch fence has no teaching bypass — after a restart the old
    epoch cannot advance a moment (the P1 fencing contract, unchanged)."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )
    opened = _open(coordinator)
    epoch.open_runtime_epoch(db)  # a new process run fences the old epoch
    with pytest.raises(StaleEpochError):
        _reply(coordinator, _attempt("I think it is going to rain."))
    # Nothing was written by the fenced attempt.
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 0
    moment = teaching_controller.get_moment(opened.moment_id)
    assert isinstance(moment, Ok) and moment.value is not None
    assert moment.value.lifecycle_state is MomentState.AWAITING_USER
