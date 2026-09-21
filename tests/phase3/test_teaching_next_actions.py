"""VAL ④⑤⑥⑦ — evaluator v0, the presentation ladder, the next-action
branches and the §8 limits (P3-1B).

④ the evaluator's five STATE_MACHINES §5 values are a fixed function of the
  attempt and the target's validated key — no general substring rule can
  ever produce SUCCESS, and ALTERNATIVE_SUCCESS survives the durable record;
⑤ the ladder is one-way: phase and support never step back inside a moment,
  and an attempt's evidence never claims less support than the material
  actually shown;
⑥ hint / retry / reveal / explanation / skip / reject / topic shift /
  explicit target switch (the last closes the moment and opens the same
  turn's cycle_index + 1);
⑦ limits v0 (2 / 3 / 3 / 5): the soft caps need an explicit request, the
  hard caps convert to the closing move instead of dead-ending.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.persona import ScriptedPersonaProvider
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import ClientMessageId, Ok
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.types import MomentState, PresentationPhase, TeachingSupportLevel

from .conftest import CONV, make_lease, make_teaching_coordinator

REQUESTED_AT = "2026-09-21T10:00:00+00:00"
TARGET = "res-hedge-i-think"
CANONICAL = "I think it is going to rain."
ALTERNATIVE = "It might rain."
WRONG = "The cat sat on the mat."


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


def _open(coordinator: ConversationCoordinator, client_message_id: str = "cm-open"):
    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=TARGET,
            client_message_id=ClientMessageId(client_message_id),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _respond(
    coordinator: ConversationCoordinator,
    envelope: TeachingResponseEnvelope,
    client_message_id: str,
):
    result = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=envelope,
            client_message_id=ClientMessageId(client_message_id),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _answer(
    coordinator: ConversationCoordinator,
    text: str,
    client_message_id: str,
    intent: TeachingControlIntent = TeachingControlIntent.CONTINUE,
):
    return _respond(
        coordinator,
        TeachingResponseEnvelope(
            control_intent=intent,
            attempt_present=True,
            attempt=AttemptPayload(text=text),
        ),
        client_message_id,
    )


def _control(
    coordinator: ConversationCoordinator,
    intent: TeachingControlIntent,
    client_message_id: str,
    **extra,
):
    return _respond(
        coordinator,
        TeachingResponseEnvelope(
            control_intent=intent, attempt_present=False, **extra
        ),
        client_message_id,
    )


def _moment(teaching_controller, moment_id):
    result = teaching_controller.get_moment(moment_id)
    assert isinstance(result, Ok) and result.value is not None
    return result.value


def _action_types(db: sqlite3.Connection, moment_id: str) -> list[str]:
    return [
        str(row[0])
        for row in db.execute(
            "SELECT action_type FROM generation_action_intent"
            " WHERE moment_id = ? ORDER BY created_at, action_id",
            (moment_id,),
        ).fetchall()
    ]


# ---------------------------------------------------------------------------
# ⑥ + ⑤: hint / retry / reveal / explanation ladders
# ---------------------------------------------------------------------------


def test_ask_hint_walks_the_fixture_ladder_one_rung_at_a_time(
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

    first = _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint-1")
    assert first.delivery_kind == "HINT"
    assert first.action_type == "TEACHING_HINT"
    assert first.moment_state is MomentState.AWAITING_USER
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC
    assert moment.support_level is TeachingSupportLevel.SEMANTIC_HINT

    second = _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint-2")
    assert second.delivery_kind == "HINT"
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.presentation_phase is PresentationPhase.HINT_STRUCTURAL
    assert moment.support_level is TeachingSupportLevel.STRUCTURAL_HINT

    third = _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint-3")
    assert third.delivery_kind == "HINT"
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.presentation_phase is PresentationPhase.HINT_PARTIAL_FORM

    # The fixture's ladder is exhausted: the next hint request reveals (there
    # is no rung left to show without repeating one), and the moment stays
    # open at FULL_REVEAL for the optional post-reveal attempt.
    fourth = _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint-4")
    assert fourth.delivery_kind == "REVEAL"
    assert fourth.action_type == "TEACHING_REVEAL"
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.presentation_phase is PresentationPhase.FULL_REVEAL
    assert moment.support_level is TeachingSupportLevel.FULL_FORM_SHOWN
    assert moment.lifecycle_state is MomentState.AWAITING_USER

    assert _action_types(db, opened.moment_id) == [
        "TEACHING_OPEN",
        "TEACHING_HINT",
        "TEACHING_HINT",
        "TEACHING_HINT",
        "TEACHING_REVEAL",
    ]


def test_a_retry_continuation_keeps_the_current_rung(
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
    """⑥: HINT / RETRY → AWAITING_USER — a failed attempt without a hint
    request re-prompts at the same rung (no unauthorized ladder move)."""

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
    _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint")
    reply = _answer(coordinator, WRONG, "cm-try")
    assert reply.delivery_kind == "RETRY"  # the retry re-prompts
    assert reply.action_type == "TEACHING_HINT"
    assert reply.moment_state is MomentState.AWAITING_USER
    moment = _moment(teaching_controller, opened.moment_id)
    # The rung did not move backwards or forwards on a retry.
    assert moment.presentation_phase is PresentationPhase.HINT_SEMANTIC
    assert moment.support_level is TeachingSupportLevel.SEMANTIC_HINT
    assert reply.evaluation_outcome == "FAILURE"


def test_a_post_reveal_attempt_is_capped_to_imitative_evidence(
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
    """⑤: after the full form was shown the moment yields no *independent*
    evidence — the claim is an IMITATIVE_PRODUCTION at FULL exposure."""

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
    _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint")
    _control(coordinator, TeachingControlIntent.ASK_ANSWER, "cm-reveal")

    reply = _answer(coordinator, CANONICAL, "cm-post-reveal")
    assert reply.evaluation_outcome == "SUCCESS"
    claim = db.execute(
        "SELECT performance_type, support_level, answer_exposure_state,"
        " outcome, polarity FROM evidence_claim"
    ).fetchall()
    assert len(claim) == 1
    assert claim[0][0] == "IMITATIVE_PRODUCTION"
    assert claim[0][1] == "FULL_FORM_SHOWN"
    assert claim[0][2] == "FULL"
    # The completion outcome says the success was supported.
    assert reply.closure == "SUCCESS_SUPPORTED"
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.completion_outcome == "SUCCESS_SUPPORTED"
    # §3: the moment recorded that the attempt happened after the reveal.
    assert moment.presentation_phase is (
        PresentationPhase.POST_REVEAL_OPTIONAL_ATTEMPT
    )


def test_an_attempt_after_a_hint_never_claims_less_support_than_it_had(
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
    """⑤ backward direction: the evidence support is the real exposure peak
    of the moment, not the attempt's own guess."""

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
    _open(coordinator)
    _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-hint")
    reply = _answer(coordinator, WRONG, "cm-try")
    assert reply.evaluation_outcome == "FAILURE"
    claim = db.execute(
        "SELECT support_level, performance_type, outcome, polarity"
        " FROM evidence_claim"
    ).fetchall()
    # A failed attempt is an *attempted use* (FAILED_ATTEMPT), and it never
    # claims less support than the moment really gave.
    assert claim == [("SEMANTIC_HINT", "FAILED_ATTEMPT", "FAILURE", "NEGATIVE")]
    attempt = db.execute(
        "SELECT support_level_before_attempt FROM attempt_record"
    ).fetchall()
    assert attempt == [("SEMANTIC_HINT",)]


def test_ask_explanation_delivers_the_explanation_phase(
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
    reply = _control(
        coordinator, TeachingControlIntent.ASK_EXPLANATION, "cm-explain"
    )
    assert reply.delivery_kind == "EXPLANATION"
    assert reply.action_type == "TEACHING_EXPLANATION"
    assert reply.moment_state is MomentState.AWAITING_USER
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.presentation_phase is PresentationPhase.EXPLANATION


# ---------------------------------------------------------------------------
# ⑥ + ④: alternative realization and the abstain path
# ---------------------------------------------------------------------------


def test_an_allowed_alternative_realization_stays_alternative_success(
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
    """④: the five-value outcome is preserved at the AttemptEvaluation layer;
    the capability-positive / resource-neutral fold happens in Learning."""

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
    reply = _answer(coordinator, ALTERNATIVE, "cm-alt")

    assert reply.evaluation_outcome == "ALTERNATIVE_SUCCESS"
    durable = db.execute(
        "SELECT outcome FROM attempt_evaluation_record"
    ).fetchall()
    assert durable == [("ALTERNATIVE_SUCCESS",)]
    assert reply.closure == "SUCCESS_ALTERNATIVE"

    claims = db.execute(
        "SELECT target_type, target_id, outcome, polarity, performance_type"
        " FROM evidence_claim ORDER BY target_type DESC"
    ).fetchall()
    # Two claims, one observable behavior: the CAPABILITY is credited, the
    # RESOURCE the moment taught is neutral / not demonstrated.
    assert [row[0] for row in claims] == ["RESOURCE", "CAPABILITY"]
    resource, capability = claims
    assert resource[1] == TARGET
    assert resource[2:] == ("ABSTAIN", "NEUTRAL", "INDEPENDENT_PRODUCTION")
    assert capability[1] == "cap-eval-hedged-opinion"
    assert capability[2:] == ("SUCCESS", "POSITIVE", "INDEPENDENT_PRODUCTION")
    assert opened is not None


def test_an_empty_or_unjudgeable_attempt_is_abstain_and_writes_no_evidence(
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
    """④: ABSTAIN is the honest "cannot judge" value — it never produces a
    claim (and so never a negative one)."""

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
    _open(coordinator)
    reply = _answer(coordinator, "   ", "cm-empty")
    assert reply.evaluation_outcome == "ABSTAIN"
    assert reply.opportunity_id is None
    assert reply.evidence_commit_id is None
    assert db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()[0] == 0
    assert (
        db.execute(
            "SELECT COUNT(*) FROM attempt_evaluation_record"
            " WHERE outcome = 'ABSTAIN'"
        ).fetchone()[0]
        == 1
    )
    # An unjudgeable attempt is a retry-like continuation, not a closure.
    assert reply.moment_state is MomentState.AWAITING_USER


# ---------------------------------------------------------------------------
# ⑥: leaving intents and the explicit target switch
# ---------------------------------------------------------------------------


def test_each_leaving_intent_closes_with_its_own_abort_reason(
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
    for index, (intent, reason) in enumerate(
        (
            (TeachingControlIntent.REJECT_TARGET, "USER_REJECTED_TARGET"),
            (TeachingControlIntent.CHANGE_TOPIC, "USER_TOPIC_SHIFT"),
        )
    ):
        coordinator = _coordinator(
            store,
            generation_store,
            fence,
            learning,
            decision_cycle_store,
            teaching_controller,
            target_provider,
        )
        opened = _open(coordinator, client_message_id=f"cm-open-{index}")
        reply = _control(coordinator, intent, f"cm-leave-{index}")
        assert reply.closure == reason
        assert reply.moment_state is MomentState.CLOSED
        moment = _moment(teaching_controller, opened.moment_id)
        assert moment.abort_reason == reason
        assert moment.completion_outcome is None
        assert (
            db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0]
            == 0
        )


def test_switch_target_closes_the_moment_and_opens_the_next_cycle_same_turn(
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
    """⑥ / SM §2: 先关闭当前 Moment，再同 turn 新 DecisionCycle."""

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
    reply = _control(
        coordinator,
        TeachingControlIntent.SWITCH_TARGET,
        "cm-switch",
        target_switch_request="RESOURCE/res-colloc-make-a-decision",
    )
    assert reply.closure == "USER_SWITCH_TARGET"
    assert reply.moment_state is MomentState.CLOSED
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.abort_reason == "USER_SWITCH_TARGET"

    cycles = db.execute(
        "SELECT cycle_index FROM decision_cycle WHERE turn_id = ?"
        " ORDER BY cycle_index",
        (reply.turn_id,),
    ).fetchall()
    assert [row[0] for row in cycles] == [0, 1]
    assert reply.next_cycle_id is not None
    assert reply.next_cycle_id != moment.decision_cycle_id
    # The pointer moved to the same turn's NEW cycle (the A-slice mechanism).
    pointer = db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (reply.turn_id,),
    ).fetchone()
    assert pointer == (str(reply.next_cycle_id),)
    # No second moment was opened, and the lock is free.
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 1
    assert (
        db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    )


def test_switch_target_without_a_requested_target_is_refused(
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
    _open(coordinator)
    result = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.SWITCH_TARGET
            ),
            client_message_id=ClientMessageId("cm-switch-empty"),
            requested_at=REQUESTED_AT,
        )
    )
    assert not isinstance(result, Ok)
    assert result.error.code.value == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# ⑦: limits v0
# ---------------------------------------------------------------------------


def test_soft_attempt_cap_requires_an_explicit_request_and_hard_cap_closes(
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
    """⑦: 2 / 3 — past the soft cap only an explicit request continues; past
    the hard cap the hint is converted into the closing reveal."""

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

    # Attempt 1 and 2: the soft attempt cap (2) is reached after the second.
    _answer(coordinator, WRONG, "cm-t1")
    _answer(coordinator, WRONG, "cm-t2")

    # Past the soft cap an explicit request still continues…
    hinted = _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-h1")
    assert hinted.delivery_kind == "HINT"
    assert hinted.limit_reason is None

    # …but a non-request move (META_DISCUSSION) does not: the episode closes
    # with the progress it has and shows no answer the user did not ask for.
    closed = _control(
        coordinator, TeachingControlIntent.META_DISCUSSION, "cm-meta"
    )
    assert closed.closure == "PARTIAL_PROGRESS"
    assert closed.moment_state is MomentState.CLOSED
    assert closed.delivery_kind == "RESUME"
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.completion_outcome == "PARTIAL_PROGRESS"


def test_hard_attempt_cap_converts_the_continuation_into_the_closing_reveal(
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
    """⑦ hard_attempt_limit = 3: the attempt itself is always recorded and
    evaluated, but the *retry* it would trigger is refused — the frozen
    reference's ``hard_attempt_limit_exhausted and retry_like`` — and the
    episode closes with the answer shown instead of dead-ending."""

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
    _answer(coordinator, WRONG, "cm-t1")
    _answer(coordinator, WRONG, "cm-t2")

    reply = _answer(coordinator, WRONG, "cm-t3")
    assert reply.evaluation_outcome == "FAILURE"
    assert reply.moment_state is MomentState.CLOSED
    assert reply.closure == "REVEALED"
    assert reply.limit_reason == "HARD_ATTEMPT_LIMIT"
    assert reply.delivery_kind == "RESUME"
    moment = _moment(teaching_controller, opened.moment_id)
    assert moment.completion_outcome == "REVEALED"
    # All three attempts are durable evidence of an attempted use.
    assert db.execute("SELECT COUNT(*) FROM attempt_record").fetchone()[0] == 3
    assert (
        db.execute(
            "SELECT COUNT(*) FROM attempt_evaluation_record"
        ).fetchone()[0]
        == 3
    )
    # The refusal is durable: the continuation Gate recorded a DENY with the
    # frozen BF-03 reason word.
    denials = db.execute(
        "SELECT reason_codes FROM gate_decision WHERE context ="
        " 'USER_REQUESTED_CONTINUE' AND decision = 'DENY'"
    ).fetchall()
    assert any("HARD_ATTEMPT_LIMIT" in str(row[0]) for row in denials)


def test_hard_teaching_turn_cap_closes_instead_of_dead_ending(
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
    """⑦: 5 delivered teaching turns (opening + 4 continuations) exhaust the
    hard teaching-turn cap; a fifth continuation is converted, not dropped."""

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
    for index in range(1, 4):
        _control(
            coordinator, TeachingControlIntent.ASK_HINT, f"cm-hint-{index}"
        )
    assert (
        db.execute(
            "SELECT COUNT(*) FROM generation_action_intent WHERE moment_id = ?"
            " AND action_type IN ('TEACHING_OPEN', 'TEACHING_HINT',"
            " 'TEACHING_REVEAL', 'TEACHING_EXPLANATION')",
            (opened.moment_id,),
        ).fetchone()[0]
        == 4
    )
    # The 5th teaching turn (a reveal) is delivered; the cap is checked
    # against the count *before* the new action.
    revealed = _control(coordinator, TeachingControlIntent.ASK_ANSWER, "cm-ans")
    assert revealed.delivery_kind == "REVEAL"
    assert revealed.moment_state is MomentState.AWAITING_USER

    closed = _control(coordinator, TeachingControlIntent.ASK_HINT, "cm-h-cap")
    assert closed.moment_state is MomentState.CLOSED
    assert closed.closure == "REVEALED"
    assert closed.limit_reason == "HARD_TEACHING_TURN_LIMIT"
