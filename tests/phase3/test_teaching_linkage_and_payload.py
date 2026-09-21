"""F4 + F6 — the capability linkage gate and the canonical reply payload.

F4  A capability claim may only be recorded for a linkage the provider can
    actually resolve. The target fixture *declares* the capability a resource
    realizes; before the exemption in the LOR check (which lets the linkage
    claim carry a different target than the opportunity) is exercised, the
    declaration itself has to be checked — otherwise any capability id,
    declared or not, could be credited as positive evidence. The assembly
    verifies the linkage through the target provider, and a declared but
    unreachable linkage produces no capability claim (the refusal is traced
    on the proposal) instead of a claim about a capability that does not
    exist.

F6  The canonical TEACHING_RESPONSE payload carries
    ``interpretation_confidence`` as a JSON number and round-trips exactly;
    malformed payloads are parse errors (ValueError), never half-parsed
    envelopes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

import pytest

from elc.conversation import SqliteConversationStore
from elc.learning.controller import LearningController
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db.epoch import RuntimeEpochFence
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
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
    parse_teaching_response_payload,
    teaching_response_payload,
)
from elc.teaching.evaluator import AttemptEvaluation
from elc.teaching.evidence import build_evidence_proposal
from elc.teaching.request import TeachingRequest
from elc.teaching.types import AttemptOutcome
from tests.phase3.target_fixtures import (
    VALIDATED_TARGET_FIXTURES,
    FixtureTeachingTargetProvider,
)

from .conftest import CONV, make_lease, make_teaching_coordinator

REQUESTED_AT = "2026-09-21T14:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"
ALTERNATIVE = "It might rain."


class DeclaredLinkageProvider:
    """Serves one RESOURCE target whose declared capability the provider
    cannot resolve (the review F4 hole: a declared-but-unreachable id)."""

    def __init__(self, view, declared: str | None) -> None:
        self._view = replace(view, capability_linkage=declared)

    def resolve(self, target_type: str, target_id: str):
        if target_type == "RESOURCE" and target_id == self._view.target_id:
            return Ok(self._view)
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=f"no target {target_type}/{target_id}",
            )
        )


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    targets,
) -> ConversationCoordinator:
    persona = PersonaRuntime(
        actions=generation_store,
        provider=ScriptedPersonaProvider(),
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
        decision_cycles=decision_cycle_store,
        learning_controller=LearningController(learning),
        teaching=teaching_controller,
        targets=targets,
    )


def _open(coordinator):
    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=FOCUS_TARGET,
            client_message_id=ClientMessageId("cm-open"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def _alternative_reply(coordinator, cmid: str = "cm-alt"):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.CONTINUE,
                attempt_present=True,
                attempt=AttemptPayload(text=ALTERNATIVE),
            ),
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )


# ---------------------------------------------------------------------------
# F4 — the linkage is verified before it is credited
# ---------------------------------------------------------------------------


def test_f4_a_declared_but_unreachable_linkage_yields_no_capability_claim(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    del conversation
    base = next(
        view
        for view in VALIDATED_TARGET_FIXTURES
        if view.target_id == FOCUS_TARGET
    )
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        DeclaredLinkageProvider(base, "cap-never-declared"),
    )
    _open(coordinator)
    reply = _alternative_reply(coordinator)
    assert isinstance(reply, Ok), reply
    # The evaluation keeps the five-value outcome …
    assert reply.value.evaluation_outcome == "ALTERNATIVE_SUCCESS"
    assert reply.value.closure == "SUCCESS_ALTERNATIVE"
    # … and exactly one claim exists: the resource, neutral / not
    # demonstrated. No capability claim was invented for the undeclared id.
    claims = db.execute(
        "SELECT target_type, target_id, outcome, polarity FROM evidence_claim"
    ).fetchall()
    assert claims == [("RESOURCE", FOCUS_TARGET, "ABSTAIN", "NEUTRAL")]
    assert (
        db.execute(
            "SELECT COUNT(*) FROM evidence_claim WHERE target_type = 'CAPABILITY'"
        ).fetchone()[0]
        == 0
    )
    # The opportunity is still the resource's (the LOR is about the moment).
    assert db.execute(
        "SELECT target_type, target_id FROM learning_opportunity_record"
    ).fetchone() == ("RESOURCE", FOCUS_TARGET)


def test_f4_a_resolvable_linkage_is_unaffected(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """The control case: the fixture's own declaration resolves, so the
    capability IS credited (two claims, one behavior)."""

    del conversation
    _open(
        make_teaching_coordinator(
            store,
            generation_store,
            make_lease(fence),
            ScriptedPersonaProvider(),
            learning,
            decision_cycle_store,
            teaching_controller,
            FixtureTeachingTargetProvider(),
        )
    )
    coordinator = make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        FixtureTeachingTargetProvider(),
    )
    reply = _alternative_reply(coordinator)
    assert isinstance(reply, Ok), reply
    assert [
        row[0]
        for row in db.execute(
            "SELECT target_type FROM evidence_claim ORDER BY target_type DESC"
        ).fetchall()
    ] == ["RESOURCE", "CAPABILITY"]


def test_f4_the_dropped_linkage_is_traced_on_the_proposal() -> None:
    """The refusal is auditable: the proposal records the declared id it
    could not verify (the durable claim set simply has no capability claim)."""

    from elc.platform.types import EvidenceModality
    from elc.teaching.flow import attempt_record_for
    from elc.teaching.types import (
        AttemptRecord,
        MomentSource,
        MomentState,
        PresentationPhase,
        TeachingMomentRecord,
        TeachingSupportLevel,
        TeachingTargetRef,
    )

    base = next(
        view
        for view in VALIDATED_TARGET_FIXTURES
        if view.target_id == FOCUS_TARGET
    )
    view = replace(base, capability_linkage="cap-never-declared")
    moment = TeachingMomentRecord(
        moment_id="tm-1",
        conversation_id=CONV,
        persona_id=None,
        source=MomentSource.USER_INITIATED,
        decision_cycle_id="dcy-1",
        candidate_id="cand-1",
        gate_decision_id="gd-1",
        focus_target=TeachingTargetRef("RESOURCE", FOCUS_TARGET),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="ESTABLISH",
        evidence_modality=EvidenceModality.TEXT_PRODUCTION,
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MomentState.EVALUATING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.CONTEXT_ONLY,
        completion_outcome=None,
        abort_reason=None,
        state_version=3,
    )
    attempt: AttemptRecord = attempt_record_for(
        moment=moment,
        attempt_id="at-1",
        user_turn_id="ut-1",
        attempt_index=1,
    )
    evaluation = AttemptEvaluation(
        outcome=AttemptOutcome.ALTERNATIVE_SUCCESS,
        confidence=1.0,
        basis="ALTERNATIVE_REALIZATION_EXACT",
        matched_form=ALTERNATIVE,
    )
    proposal = build_evidence_proposal(
        moment=moment,
        attempt=attempt,
        evaluation=evaluation,
        target_view=view,
        opportunity_id="lo-1",
        capability_linkage=None,
    )
    assert proposal is not None
    assert proposal.capability_linkage_target_id is None
    assert proposal.dropped_linkage_target_id == "cap-never-declared"
    # With a verified linkage the same attempt carries it and drops nothing.
    verified = build_evidence_proposal(
        moment=moment,
        attempt=attempt,
        evaluation=evaluation,
        target_view=view,
        opportunity_id="lo-1",
        capability_linkage="cap-never-declared",
    )
    assert verified is not None
    assert verified.capability_linkage_target_id == "cap-never-declared"
    assert verified.dropped_linkage_target_id is None


# ---------------------------------------------------------------------------
# F6 — the canonical reply payload
# ---------------------------------------------------------------------------


def test_f6_the_payload_round_trips_every_field() -> None:
    envelope = TeachingResponseEnvelope(
        control_intent=TeachingControlIntent.ASK_HINT,
        attempt_present=True,
        attempt=AttemptPayload(text="I think it is going to rain."),
        clarification_request="which one?",
        user_preference_signal="slow down",
        interpretation_confidence=0.75,
    )
    payload = teaching_response_payload(envelope)
    # Confidence is a JSON number, not a string (review F6) …
    assert '"interpretation_confidence":0.75' in payload
    assert json.loads(payload)["interpretation_confidence"] == 0.75
    # … and the payload is byte-deterministic.
    assert teaching_response_payload(envelope) == payload

    parsed = parse_teaching_response_payload(payload)
    assert parsed.control_intent is TeachingControlIntent.ASK_HINT
    assert parsed.attempt_present is True
    assert parsed.attempt is not None
    assert parsed.attempt.text == "I think it is going to rain."
    assert parsed.clarification_request == "which one?"
    assert parsed.user_preference_signal == "slow down"
    assert parsed.target_switch_request is None
    assert parsed.interpretation_confidence == 0.75

    # The minimal reply round-trips too (absent optionals stay absent).
    minimal = TeachingResponseEnvelope(control_intent=TeachingControlIntent.SKIP)
    again = parse_teaching_response_payload(teaching_response_payload(minimal))
    assert again.control_intent is TeachingControlIntent.SKIP
    assert again.attempt_present is False
    assert again.attempt is None
    assert again.interpretation_confidence == 1.0


@pytest.mark.parametrize(
    "payload",
    (
        "not json at all",
        "[1, 2, 3]",
        '{"type":"TEACHING_REQUEST","focus_target_id":"res-1"}',
        '{"type":"TEACHING_RESPONSE"}',
        '{"type":"TEACHING_RESPONSE","control_intent":"NOT_AN_INTENT"}',
        '{"type":"TEACHING_RESPONSE","control_intent":"CONTINUE",'
        ' "interpretation_confidence":{}}',
        '{"type":"TEACHING_RESPONSE","control_intent":"CONTINUE",'
        ' "interpretation_confidence":""}',
        '{"type":"TEACHING_RESPONSE","control_intent":"CONTINUE",'
        ' "interpretation_confidence":true}',
    ),
)
def test_f6_malformed_payloads_are_parse_errors(payload: str) -> None:
    with pytest.raises(ValueError):
        parse_teaching_response_payload(payload)


def test_f6_a_legacy_numeric_string_confidence_still_parses() -> None:
    """Backward tolerance for a payload written before the numeric form: a
    numeric *string* parses, an empty or non-numeric one does not."""

    legacy = (
        '{"type":"TEACHING_RESPONSE","control_intent":"CONTINUE",'
        '"attempt_present":false,"interpretation_confidence":"0.5"}'
    )
    parsed = parse_teaching_response_payload(legacy)
    assert parsed.interpretation_confidence == 0.5
