"""The pure steps of one active-teaching turn (Phase 3 P3-1B).

Authority: docs/STATE_MACHINES.md §4 (the envelope's five-step processing
order), §1 (the lifecycle / branch table), docs/RUNTIME_ARCHITECTURE.md §5
(the active-teaching turn pipeline) and docs/DATA_MODEL.md §17 (the
attempt / evaluation records), with the design authority of
DEC-OPI-2babb21e-….5 Q4 and the review carry-over DEC-….34 (F5/F9).

Sequencing belongs to the Conversation Orchestrator (docs/DOMAIN_MODEL.md
§16: "owns sequencing, not truth"); this module owns the *pure* values one
sequencing step needs, so the coordinator stays free of table shapes and
every assembly rule is unit-testable without a database:

- :func:`attempt_record_for` — the §17 AttemptRecord of one attempt, with
  the exposure facts taken from the moment's real presentation state (the
  conservative direction of §13);
- :func:`evaluation_record_for` — the §17 AttemptEvaluationRecord, carrying
  the evaluation's five-value §5 outcome verbatim;
- :func:`continuation_index_for` — the moment's next ``attempt_index``
  (UNIQUE(moment_id, attempt_index) is the §25 attempt identity);
- :func:`continuation_facts_for` — the BF-03 v1.1 continuation fact bundle
  (``authorization_basis = ACTIVE_MOMENT``), including the two §8 hard-cap
  facts the frozen reference evaluates;
- :func:`closing_reason_for_gate_denial` — the §7 abort reason a Gate
  refusal of a continuation maps onto, so a refused teaching action is
  never silently dropped.

Nothing here writes: the store's short transactions execute what these
functions describe.
"""

from __future__ import annotations

import json

from elc.platform.types import MomentId, UserTurnId
from elc.teaching.evaluator import (
    ATTEMPT_EVALUATOR_ID,
    ATTEMPT_EVALUATOR_VERSION,
    AttemptEvaluation,
)
from elc.teaching.evidence import answer_exposure_default
from elc.teaching.gate import (
    SAFETY_PRIVACY_NO_SOURCE,
    TARGET_SUPPRESSED_NO_SOURCE,
    ContinuationFacts,
)
from elc.teaching.limits import TeachingLimits, TeachingLoad
from elc.teaching.targets import TeachingTargetView
from elc.teaching.types import (
    AttemptEvaluationId,
    AttemptEvaluationRecord,
    AttemptId,
    AttemptOutcome,
    AttemptRecord,
    ExposureEstimateCertainty,
    PresentationPhase,
    TeachingMomentRecord,
)

__all__ = [
    "ATTEMPT_OPPORTUNITY_TYPE",
    "ATTEMPT_TARGET_EXPLICITNESS",
    "DEGRADED_ABORT_REASON",
    "DEFAULT_GATE_DENIAL_REASON",
    "GATE_DENIAL_ABORT_REASONS",
    "answer_key_for",
    "attempt_record_for",
    "closing_reason_for_gate_denial",
    "continuation_facts_for",
    "continuation_index_for",
    "evaluation_record_for",
    "evidence_proposal_refs_for",
    "opportunity_id_for",
]

#: The §7 words a Gate refusal of a continuation can close with, by the
#: refusal code that names the precise reason. Everything else is a policy
#: stop: the moment may not continue executing teaching actions, and the
#: episode says so honestly instead of silently dropping the move.
GATE_DENIAL_ABORT_REASONS = {
    "CONTENT_INVALID": "CONTENT_INVALID",
    "SNAPSHOT_INVALIDATED": "SNAPSHOT_INVALIDATED",
    "PRE_DELIVERY_INVALIDATED": "PRE_DELIVERY_INVALIDATED",
}

#: The §7 reason for every other continuation refusal (a policy stop).
DEFAULT_GATE_DENIAL_REASON = "POLICY_STOP"

#: The §7 reason a DEGRADED continuation closes with (RUNTIME §21 "Teaching
#: state failure → abort/no-open teaching + normal persona").
DEGRADED_ABORT_REASON = "SYSTEM_FAILURE"

#: DATA_MODEL §7 LearningOpportunityRecord ``opportunity_type``: a teaching
#: attempt is an opportunity the runtime *elicited* — the learner was asked
#: to produce the target, which is exactly what makes a claim about it
#: observable ("Target-specific negative evidence 需要 Opportunity 或
#: attempted use").
ATTEMPT_OPPORTUNITY_TYPE = "ELICITED"

#: The §7 ``target_explicitness`` of an attempt made inside a moment: the
#: focus target is named by the episode itself, so the target is explicit.
ATTEMPT_TARGET_EXPLICITNESS = "EXPLICIT_TARGET"

#: The exposure certainty recorded with an attempt: Local V1 delivers
#: server-side without a ClientRenderAck yet, so the honest value is
#: ``SERVER_SENT_UNCONFIRMED`` (STATE_MACHINES §13) — never
#: ``CONFIRMED_RENDERED`` before an ACK exists.
SERVER_SENT_UNCONFIRMED = ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED


def continuation_index_for(moment: TeachingMomentRecord) -> int:
    """The ``attempt_index`` the moment's next attempt records (1-based)."""

    return moment.attempt_index + 1


def attempt_record_for(
    *,
    moment: TeachingMomentRecord,
    attempt_id: str,
    user_turn_id: str,
    attempt_index: int,
    created_at: str | None = None,
    exposure_estimate_id: str | None = None,
) -> AttemptRecord:
    """§17 AttemptRecord of one attempt against the moment's real state.

    ``support_level_before_attempt`` is the support the learner had *before*
    answering (the moment's ladder position), and the exposure facts follow
    the conservative §13 direction: once the full form is on screen (or the
    ladder has reached FULL_FORM_SHOWN) the attempt is at least
    FULL-exposed, no matter what a weaker claim would say.
    """

    return AttemptRecord(
        attempt_id=AttemptId(attempt_id),
        moment_id=MomentId(moment.moment_id),
        attempt_index=attempt_index,
        user_turn_id=UserTurnId(user_turn_id),
        support_level_before_attempt=moment.support_level,
        answer_exposure_state=answer_exposure_default(
            moment.support_level.value,
            revealed=moment.presentation_phase is PresentationPhase.FULL_REVEAL,
        ),
        exposure_estimate_id=exposure_estimate_id,
        support_attribution_certainty=SERVER_SENT_UNCONFIRMED,
        support_attribution_basis=_attribution_basis(moment),
        created_at=created_at,
    )


def _attribution_basis(moment: TeachingMomentRecord) -> str:
    """The durable trace of WHICH exposure fact the attribution rests on."""

    return json.dumps(
        {
            "presentation_phase": moment.presentation_phase.value,
            "support_level": moment.support_level.value,
            "source": "moment_state_at_attempt",
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def evidence_proposal_refs_for(
    *, evaluation: AttemptEvaluation, attempt_id: str
) -> tuple[str, ...]:
    """The §17 ``evidence_proposal_refs[]`` of one evaluation.

    The refs name the durable evidence *proposal* the evaluation produced —
    the deterministic evidence-group id Learning uses (and replays) when
    the proposal is committed. An ABSTAIN produced no proposal, so it
    carries no ref: nothing was judged, so nothing is asserted.
    """

    if evaluation.outcome is AttemptOutcome.ABSTAIN:
        return ()
    return (f"eg-teaching-{attempt_id}",)


def evaluation_record_for(
    *,
    moment: TeachingMomentRecord,
    attempt: AttemptRecord,
    evaluation: AttemptEvaluation,
    evaluation_id: str,
    created_at: str | None = None,
) -> AttemptEvaluationRecord:
    """§17 AttemptEvaluationRecord of one evaluated attempt.

    The §5 five-value outcome travels verbatim (ALTERNATIVE_SUCCESS is not
    folded here — that fold is the Learning evidence conversion), and the
    confidence is the evaluator's fixed confidence for the rule that fired.
    """

    return AttemptEvaluationRecord(
        attempt_evaluation_id=AttemptEvaluationId(evaluation_id),
        moment_id=moment.moment_id,
        attempt_id=attempt.attempt_id,
        evaluator_id=ATTEMPT_EVALUATOR_ID,
        evaluator_version=ATTEMPT_EVALUATOR_VERSION,
        outcome=evaluation.outcome.value,
        confidence=evaluation.confidence,
        evidence_proposal_refs=evidence_proposal_refs_for(
            evaluation=evaluation, attempt_id=str(attempt.attempt_id)
        ),
        created_at=created_at,
    )


def opportunity_id_for(attempt_id: str) -> str:
    """The deterministic LearningOpportunityRecord id of one attempt.

    Deterministic on purpose: a crash between the opportunity mint and the
    evidence commit re-derives the same id, so ``record_opportunity``
    replays the durable row instead of minting a second opportunity for
    the same observable behavior (DATA_MODEL §7).
    """

    return f"lo-teaching-{attempt_id}"


def answer_key_for(view: TeachingTargetView | None):
    """The evaluator's key for one resolved target view.

    ``None`` means the target could not be resolved: there is no key at
    all, which is *unjudgeable* — the caller records an ABSTAIN, never a
    FAILURE (a resolver outage must not become a negative claim).
    """

    return None if view is None else view.answer_key()


def continuation_facts_for(
    *,
    moment: TeachingMomentRecord,
    decision_cycle_id: str | None,
    proposed_action: str,
    lock_state: str,
    load: TeachingLoad,
    limits: TeachingLimits,
    target_status: str = "VALID",
    content_status: str = "VALID",
    candidate_id: str = "",
    user_intent_scope: str = "ACTIVE_TEACHING_CONTINUATION",
    continuation_requested: bool = True,
) -> ContinuationFacts:
    """The BF-03 v1.1 continuation fact bundle of one proposed move.

    ``authorization_basis = ACTIVE_MOMENT`` (the frozen cross-layer v1.1
    rule: a live moment's continuation is authorized by the moment itself,
    never by a new PlannerDecision), ``moment_state`` is the live lifecycle
    state (a continuation only exists while the moment is
    DECIDING_NEXT_ACTION), and the two §8 hard-cap facts are computed from
    the *durable* counts (elc.teaching.limits.TeachingLoad) — nothing the
    caller merely asserts. The Learning snapshot is deliberately not among
    the facts this profile can degrade on: a moment's own newly committed
    evidence must not invalidate its own continuation (STATE_MACHINES §9 /
    the frozen v1.1 cross-layer note).
    """

    return ContinuationFacts(
        moment_id=str(moment.moment_id),
        decision_cycle_id=decision_cycle_id,
        candidate_id=candidate_id,
        proposed_action=proposed_action,
        gate_context="USER_REQUESTED_CONTINUE",
        authorization_path="USER_INITIATED",
        authorization_basis="ACTIVE_MOMENT",
        user_intent_scope=user_intent_scope,
        continuation_requested=continuation_requested,
        authorization_status="VALID",
        subject_status="ACTIVE",
        target_status=target_status,
        content_status=content_status,
        lock_state=lock_state,
        moment_state=moment.lifecycle_state.value,
        learning_snapshot_status="VALID",
        gate_state_status="COMPLETE",
        safety_privacy_status=SAFETY_PRIVACY_NO_SOURCE,
        target_suppressed=TARGET_SUPPRESSED_NO_SOURCE,
        hard_attempt_limit_exhausted=(
            load.attempt_count >= limits.hard_attempt_limit
        ),
        hard_teaching_turn_limit_exhausted=(
            load.teaching_turn_count >= limits.hard_teaching_turn_limit
        ),
    )


def closing_reason_for_gate_denial(reason_codes: tuple[str, ...]) -> str:
    """The §7 abort reason a continuation refusal closes with.

    The two §8 hard caps are deliberately absent from this mapping: they
    are a *conversion* (a closing reveal), never an abort. A caller that
    reaches this function is refusing on policy grounds and gets
    POLICY_STOP unless a more precise §7 word exists.
    """

    for code in reason_codes:
        exact = GATE_DENIAL_ABORT_REASONS.get(code)
        if exact is not None:
            return exact
    return DEFAULT_GATE_DENIAL_REASON
