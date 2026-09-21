"""The silent-observation claim contract (P5-2; two-layer split, P5-R).

One natural-conversation observation becomes one §6 claim — and this module is
the whole definition of that claim, so the producer (whose durable proposal
carries the observation facts) and the commit (which turns those facts into a
claim) cannot drift apart:

    TargetMatchObservation  → claim_for_silent_observation(…)

**Two layers (P5-R).** A *match* is not evidence. The matcher
(elc.learning.target_resolution) answers "does this string occur?", its
observation contract (elc.learning.target_match) says where and how certainly,
and only a match that passes the V1 admission set is converted here:

- admitted (RESOURCE + a form class + the whole utterance + no open moment for
  the target + a readable supply) → the claim below, as P5-2 defined it;
- everything else — an embedded span, a quotation, a paraphrase, a negation,
  a meta-linguistic mention, a slot-only hit, any CAPABILITY hit — is
  observation-only: zero claim, zero LearnerState change.

The claim is deliberately minimal (docs/DOMAIN_MODEL.md §6 primary
performance types + qualifiers):

- ``SPONTANEOUS_PRODUCTION`` — the learner used the form unprompted, in free
  conversation;
- ``SUCCESS`` / ``POSITIVE`` — the form occurred and the turn *was* the form;
- ``SupportLevel.NONE`` / ``ExposureLevel.NONE`` — nothing was hinted and
  nothing was shown; the observation is independent by construction;
- ``claim_role=SILENT_OBSERVATION`` (DATA_MODEL §25 carries claim_role in the
  commit key) — neither the teaching FOCUS_TARGET nor a CAPABILITY_LINKAGE:
  no moment taught this, no attempt evaluated it;
- ``opportunity_id=None`` — a POSITIVE claim needs no genuine Opportunity
  (the §6 negative-evidence rule binds negatives only), and none was minted.

**Confidence (P5-R).** ``evaluator_confidence`` is the estimator's input
fact about how much this observation is worth, and it is
:data:`USE_JUDGMENT_CONFIDENCE` (0.60) — a *judgement* about the learner's
performance, not the matcher's certainty (which stays on the observation as
``match_certainty``, where 1.0 is true). The value is placed deliberately
against the frozen estimator spec
(behavioral_baselines/estimator/BF-01_Estimator_V1_Operational_Spec_v1.1.md):

- §10 Evaluator confidence: ``evaluator_confidence >= 0.50`` for any state
  mass at all ("低于阈值: no state mass") — 0.60 clears it, so an admitted
  whole-sentence use still moves the learner state. A rule-based matcher that
  produced *no* state mass would make silent evidence meaningless;
- §17 Transfer, strong retrieval: ``evaluator_confidence >= 0.70`` — 0.60
  **fails it**. A string rule must not, on its own, constitute strong
  retrieval (freshness / transfer / stability): that would let one lexical
  occurrence certify independent retrieval. Only a producer with a real
  judgement behind it may carry ≥0.70.

The evaluator identity is named and versioned so a later producer
(model-assisted resolution, another slice) can never inherit this confidence
by accident; ``accuracy`` / ``pragmatic_fit`` stay None — a literal form
occurrence is not a graded attempt.

**V1 deliberately closes (with its revisit condition).**

- capability-from-chat: closed until a use-validator and capability
  functional definitions exist (elc.learning.target_match, admission rule 1);
- slot-only and embedded/quoted classes: closed until an **approved** §8.1 R4
  detection policy with negative fixtures and a measured false-positive rate
  exists — the same content work the §8.1 R4 ladder waits on, whose fixtures
  are also the only way to measure the slot rule's false-positive face;
- the admission set itself is a V1 policy: widening it is a new acceptance
  with its own fixtures, never a constant bump here.

Pure: no IO, no SQL, no model.

Not re-exported from ``elc.learning.__init__``: the durable store imports it
directly (the elc.learning.validation precedent — a pure policy module the
kernel consumes is imported by its full path), so this slice leaves the
package's public face unchanged.
"""

from __future__ import annotations

from elc.learning.target_match import TargetMatchObservation
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceModality,
    EvidencePolarity,
    EvidenceStatus,
    ExposureLevel,
    PerformanceType,
    SupportLevel,
)

__all__ = [
    "SILENT_EVIDENCE_EVALUATOR_ID",
    "SILENT_EVIDENCE_EVALUATOR_VERSION",
    "SILENT_EVIDENCE_MODALITY",
    "SILENT_OBSERVATION_CLAIM_ROLE",
    "USE_JUDGMENT_CONFIDENCE",
    "claim_for_silent_observation",
    "silent_observation_provenance",
]

#: The evaluator identity stamped on silent claims (DATA_MODEL §6 evaluator
#: provenance). Versioned: a different extraction slice is a different
#: evaluator version, never a silent redefinition of this one.
SILENT_EVIDENCE_EVALUATOR_ID = "deterministic-target-resolution"
SILENT_EVIDENCE_EVALUATOR_VERSION = "deterministic-target-resolution-v1"

#: The claim role of a natural-conversation observation (DATA_MODEL §25).
SILENT_OBSERVATION_CLAIM_ROLE = "SILENT_OBSERVATION"

#: The confidence of an admitted silent observation: a use-judgement, not the
#: matcher's certainty. Above BF-01 §10's 0.50 state-mass floor and below §17's
#: 0.70 strong-retrieval floor — a rule-based match may move state mass and may
#: not, by itself, certify independent retrieval (module docstring).
USE_JUDGMENT_CONFIDENCE = 0.60

#: V1 typed chat observes text production and nothing else (docs/DATA_MODEL.md
#: §24.14; P-INV-012 forbids claiming a spoken measurement from text). The
#: supply row's §11 ``evidence_modality`` is a teaching default, not the
#: modality of this observation, so it is deliberately not read.
SILENT_EVIDENCE_MODALITY = EvidenceModality.TEXT_PRODUCTION.value


def silent_observation_provenance(observation: TargetMatchObservation) -> str:
    """The claim's provenance refs: this turn, the matched form, the rule.

    One deterministic string, so a durable claim always says *why* it
    exists and which extraction produced it.
    """

    return (
        f"silent-observation:{observation.turn_id}"
        f";form:{observation.matched_form}"
        f";via:{observation.matched_via.value}"
    )


def claim_for_silent_observation(
    observation: TargetMatchObservation,
    *,
    evidence_modality: str = SILENT_EVIDENCE_MODALITY,
) -> EvidenceClaimView:
    """The one §6 claim of an **admitted** natural-conversation observation
    (an unknown ``evidence_modality`` word raises ``ValueError`` — the caller
    surfaces it as a refusal, never a silent default).

    The caller must already have applied admission **rules 1-3** — a
    ``RESOURCE`` target, a form-class hit, a whole-sentence span
    (elc.learning.target_match.admitted_for_evidence) — so the input here is
    an observation the caller has already judged against those three rules.
    Rules 4 (no open TeachingMoment for the target) and 5 (a readable
    supply) are **live-leg guards**: they need the teaching and the supply
    port, so neither this pure function nor the commit-side caller
    (elc.learning.store._silent_claim_for_proposal, which re-applies rules
    1-3 only) re-checks them. This function is the conversion, not the gate.
    """

    return EvidenceClaimView(
        evidence_claim_id=f"ecl-silent-{observation.turn_id}",
        claim_role=SILENT_OBSERVATION_CLAIM_ROLE,
        scope=observation.target_type,
        performance_type=PerformanceType.SPONTANEOUS_PRODUCTION,
        evidence_modality=EvidenceModality(evidence_modality),
        qualifiers=(),
        polarity=EvidencePolarity.POSITIVE,
        outcome=AttemptOutcome.SUCCESS,
        support=SupportLevel.NONE,
        exposure=ExposureLevel.NONE,
        evaluator_confidence=USE_JUDGMENT_CONFIDENCE,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance=silent_observation_provenance(observation),
        opportunity_id=None,
        target_id=observation.target_id,
    )
