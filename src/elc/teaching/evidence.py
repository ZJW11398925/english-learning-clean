"""Teaching evidence proposal — the facts one attempt contributes.

Authority: docs/DOMAIN_MODEL.md §6 (the Learning Evidence kernel keeps the
truth) and §14/§15 (Teaching owns the attempt and the ladder, not learner
state). Phase 3 P3-1B, TASK-…2.2 ③④.

The boundary in one sentence: **Teaching reports facts, Learning decides
claims.** This module assembles the *facts* of one attempt — which target,
which five-value §5 outcome, under which real exposure, in which ladder
position, linked to which durable LearningOpportunityRecord — and stops
there. The mapping from a five-value attempt outcome to §6 claim
polarity/outcome (including the ALTERNATIVE_SUCCESS → capability positive
+ resource neutral fold) belongs to Learning's evidence conversion and is
NOT done here.

Why a separate record instead of handing a Learning record over: the AST
pin of this slice forbids ``teaching`` from importing ``elc.learning`` and
vice versa. :class:`TeachingEvidenceProposal` is a teaching-owned frozen
value of primitives; Learning consumes it structurally through its own
Protocol (``elc.learning.teaching_evidence.TeachingEvidenceSource``), so
neither package ever imports the other.

Two ladder rules are applied here, before the facts leave Teaching
(docs/STATE_MACHINES.md §3; the second half of the "same moment" rule):

- the recorded support is the *real* exposure peak of the moment
  (:func:`elc.teaching.ladder.evidence_support_level`) — an attempt can
  never be reported as less supported than the material actually shown;
- once the full form has been revealed, the attempt is a post-reveal
  attempt: its performance type is capped at IMITATIVE_PRODUCTION and
  ``post_reveal`` is set, so Learning never reads it as fresh independent
  evidence (docs/DOMAIN_MODEL.md §15: "完整答案曝光后，当前 Moment 后续不再
  产生 independent evidence").

An ABSTAIN evaluation produces NO proposal: nothing was judged, so nothing
is asserted (the durable AttemptEvaluationRecord is the trace). Aborts and
unjudgeable attempts therefore never contribute negative mastery evidence
(docs/STATE_MACHINES.md §7).
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.teaching.evaluator import (
    ATTEMPT_EVALUATOR_ID,
    ATTEMPT_EVALUATOR_VERSION,
    AttemptEvaluation,
)
from elc.teaching.ladder import (
    POST_REVEAL_PERFORMANCE_TYPE,
    evidence_answer_exposure,
    evidence_support_level,
    is_post_reveal_attempt,
)
from elc.teaching.targets import TeachingTargetView
from elc.teaching.types import (
    AnswerExposureState,
    AttemptOutcome,
    AttemptRecord,
    ExposureEstimateCertainty,
    TeachingMomentRecord,
    TeachingSupportLevel,
)

__all__ = [
    "CAPABILITY_LINKAGE_CLAIM_ROLE",
    "FOCUS_CLAIM_ROLE",
    "TeachingEvidenceProposal",
    "build_evidence_proposal",
    "performance_type_for",
]
#: Claim roles (the §25 evidence-commit key includes ``claim_role``).
FOCUS_CLAIM_ROLE = "FOCUS_TARGET"
CAPABILITY_LINKAGE_CLAIM_ROLE = "CAPABILITY_LINKAGE"

#: Support levels at/above which the learner was shown part of the target
#: form, so a production is a guided — not an independent — realization.
_GUIDED_FROM = TeachingSupportLevel.PARTIAL_FORM.value


@dataclass(frozen=True)
class TeachingEvidenceProposal:
    """The facts of one attempt (see the module docstring).

    ``attempt_outcome`` keeps the full STATE_MACHINES §5 five-value set:
    ALTERNATIVE_SUCCESS travels verbatim into Learning, which owns the
    capability-positive / resource-neutral fold.
    """

    moment_id: str
    attempt_id: str
    target_type: str
    target_id: str
    capability_linkage_target_id: str | None
    attempt_outcome: str
    performance_type: str
    support_level: str
    answer_exposure_state: str
    evidence_modality: str
    exposure_estimate_id: str | None
    support_attribution_certainty: str
    support_attribution_basis: str
    evaluator_confidence: float
    evaluator_id: str = ATTEMPT_EVALUATOR_ID
    evaluator_version: str = ATTEMPT_EVALUATOR_VERSION
    evaluator_basis: str = ""
    opportunity_id: str | None = None
    post_reveal: bool = False
    provenance: str = ""
    #: Review F4: the linkage the target *declared* but the provider could
    #: not resolve. Recorded so the refusal is auditable (no capability
    #: claim was emitted for it), never as a claim target itself.
    dropped_linkage_target_id: str | None = None

    def as_facts(self) -> dict[str, object]:
        """The proposal as a plain mapping — the deterministic shape the
        tests and the Learning boundary both read."""

        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }


def performance_type_for(
    *,
    outcome: str,
    support_level: str,
    post_reveal: bool,
) -> str:
    """The performance type one attempt honestly realizes.

    Post-reveal attempts are imitative reproductions of the form just
    shown; a failed attempt is a FAILED_ATTEMPT (an attempted use, so the
    §6 negative-evidence rule is satisfied by the behavior itself); a
    production made with a partly shown form is guided; without support it
    is independent.
    """

    if post_reveal:
        return POST_REVEAL_PERFORMANCE_TYPE
    if outcome == AttemptOutcome.FAILURE.value:
        return "FAILED_ATTEMPT"
    if support_level >= _GUIDED_FROM or support_level in (
        TeachingSupportLevel.SEMANTIC_HINT.value,
        TeachingSupportLevel.STRUCTURAL_HINT.value,
    ):
        return "GUIDED_PRODUCTION"
    return "INDEPENDENT_PRODUCTION"


def build_evidence_proposal(
    *,
    moment: TeachingMomentRecord,
    attempt: AttemptRecord,
    evaluation: AttemptEvaluation,
    target_view: TeachingTargetView | None,
    opportunity_id: str | None,
    capability_linkage: str | None = None,
    provenance: str | None = None,
    exposure_estimate_id: str | None = None,
) -> TeachingEvidenceProposal | None:
    """Assemble the facts of one evaluated attempt (None for ABSTAIN).

    ``target_view`` supplies the target's own content facts; ``linkage`` is
    the *verified* capability linkage (review F4): the caller resolves the
    declared capability through the provider and passes it only when it is
    reachable, so a claim can never name an undeclared capability. When the
    target declares a linkage the provider cannot resolve, the declared id
    is recorded on ``dropped_linkage_target_id`` and no capability claim is
    produced. ``opportunity_id`` is the durable LearningOpportunityRecord
    minted for this attempt — always non-NULL on this path (a teaching
    attempt is an elicited opportunity, so its target-specific claims never
    lack provenance).
    """

    if evaluation.outcome is AttemptOutcome.ABSTAIN:
        return None
    support = evidence_support_level(
        moment.support_level.value, attempt.support_level_before_attempt.value
    )
    exposure = evidence_answer_exposure(
        attempt.answer_exposure_state.value, support.value
    )
    post_reveal = is_post_reveal_attempt(moment.presentation_phase.value)
    declared = None if target_view is None else target_view.capability_linkage
    dropped = (
        declared
        if declared is not None and capability_linkage != declared
        else None
    )
    return TeachingEvidenceProposal(
        moment_id=str(moment.moment_id),
        attempt_id=str(attempt.attempt_id),
        target_type=moment.focus_target.target_type,
        target_id=moment.focus_target.target_id,
        capability_linkage_target_id=capability_linkage,
        attempt_outcome=evaluation.outcome.value,
        performance_type=performance_type_for(
            outcome=evaluation.outcome.value,
            support_level=support.value,
            post_reveal=post_reveal,
        ),
        support_level=support.value,
        answer_exposure_state=exposure.value,
        evidence_modality=moment.evidence_modality.value,
        exposure_estimate_id=exposure_estimate_id,
        support_attribution_certainty=(
            ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED.value
        ),
        support_attribution_basis=attempt.support_attribution_basis,
        evaluator_confidence=evaluation.confidence,
        evaluator_basis=evaluation.basis,
        opportunity_id=opportunity_id,
        post_reveal=post_reveal,
        provenance=(
            provenance
            if provenance is not None
            else f"teaching:{moment.moment_id}/{attempt.attempt_id}"
        ),
        dropped_linkage_target_id=dropped,
    )


def answer_exposure_default(
    support_level: str, *, revealed: bool
) -> AnswerExposureState:
    """The exposure state stamped on an attempt that happens while nothing
    of the answer form has been shown yet (NONE), or after a reveal
    (FULL)."""

    if revealed:
        return AnswerExposureState.FULL
    if support_level == TeachingSupportLevel.FULL_FORM_SHOWN.value:
        return AnswerExposureState.FULL
    return AnswerExposureState.NONE
