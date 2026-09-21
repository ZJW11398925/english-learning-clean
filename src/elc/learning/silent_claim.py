"""The silent-observation claim contract (P5-2, pure).

One resolved natural-conversation observation becomes one §6 claim — and
this module is the whole definition of that claim, so the producer (whose
durable proposal carries the observation facts) and the commit (which turns
those facts into a claim) cannot drift apart:

    ResolvedTarget(turn's utterance) → claim_for_silent_observation(…)

The claim is deliberately minimal (docs/DOMAIN_MODEL.md §6 primary
performance types + qualifiers):

- ``SPONTANEOUS_PRODUCTION`` — the learner used the form unprompted, in free
  conversation;
- ``SUCCESS`` / ``POSITIVE`` — the form literally occurred (the extraction is
  deterministic, so there is no uncertainty to express: confidence 1.0);
- ``SupportLevel.NONE`` / ``ExposureLevel.NONE`` — nothing was hinted and
  nothing was shown; the observation is independent by construction;
- ``claim_role=SILENT_OBSERVATION`` (DATA_MODEL §25 carries claim_role in the
  commit key) — neither the teaching FOCUS_TARGET nor a CAPABILITY_LINKAGE:
  no moment taught this, no attempt evaluated it;
- ``opportunity_id=None`` — a POSITIVE claim needs no genuine Opportunity
  (the §6 negative-evidence rule binds negatives only), and none was minted.

The evaluator identity is named and versioned so a later producer
(model-assisted resolution, another slice) can never inherit this
confidence by accident; ``accuracy`` / ``pragmatic_fit`` stay None — a
literal form occurrence is not a graded attempt.

Pure: no IO, no SQL, no model.

Not re-exported from ``elc.learning.__init__``: the durable store imports it
directly (the elc.learning.validation precedent — a pure policy module the
kernel consumes is imported by its full path), so this slice leaves the
package's public face unchanged.
"""

from __future__ import annotations

from elc.learning.target_resolution import ResolvedTarget
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
    "SILENT_EVIDENCE_CONFIDENCE",
    "SILENT_EVIDENCE_EVALUATOR_ID",
    "SILENT_EVIDENCE_EVALUATOR_VERSION",
    "SILENT_EVIDENCE_MODALITY",
    "SILENT_OBSERVATION_CLAIM_ROLE",
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

#: Confidence of a deterministic extraction: the form literally occurred in
#: the utterance — no model uncertainty exists to express (the P2A
#: producer's DETERMINISTIC_PRODUCER_CONFIDENCE precedent).
SILENT_EVIDENCE_CONFIDENCE = 1.0

#: V1 typed chat observes text production and nothing else (docs/DATA_MODEL.md
#: §24.14; P-INV-012 forbids claiming a spoken measurement from text). The
#: supply row's §11 ``evidence_modality`` is a teaching default, not the
#: modality of this observation, so it is deliberately not read.
SILENT_EVIDENCE_MODALITY = EvidenceModality.TEXT_PRODUCTION.value


def silent_observation_provenance(
    turn_id: str, resolution: ResolvedTarget
) -> str:
    """The claim's provenance refs: this turn, the matched form, the rule.

    One deterministic string, so a durable claim always says *why* it
    exists and which extraction produced it.
    """

    return (
        f"silent-observation:{turn_id}"
        f";form:{resolution.matched_form}"
        f";via:{resolution.matched_via.value}"
    )


def claim_for_silent_observation(
    *,
    turn_id: str,
    resolution: ResolvedTarget,
    evidence_modality: str = SILENT_EVIDENCE_MODALITY,
) -> EvidenceClaimView:
    """The one §6 claim of a resolved natural-conversation observation (an
    unknown ``evidence_modality`` word raises ``ValueError`` — the caller
    surfaces it as a refusal, never a silent default)."""

    return EvidenceClaimView(
        evidence_claim_id=f"ecl-silent-{turn_id}",
        claim_role=SILENT_OBSERVATION_CLAIM_ROLE,
        scope=resolution.target_type,
        performance_type=PerformanceType.SPONTANEOUS_PRODUCTION,
        evidence_modality=EvidenceModality(evidence_modality),
        qualifiers=(),
        polarity=EvidencePolarity.POSITIVE,
        outcome=AttemptOutcome.SUCCESS,
        support=SupportLevel.NONE,
        exposure=ExposureLevel.NONE,
        evaluator_confidence=SILENT_EVIDENCE_CONFIDENCE,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance=silent_observation_provenance(turn_id, resolution),
        opportunity_id=None,
        target_id=resolution.target_id,
    )
