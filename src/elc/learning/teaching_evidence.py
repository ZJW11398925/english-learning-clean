"""Teaching evidence conversion — Learning's side of the P3-1B boundary.

Authority: DEC-OPI-2babb21e-….5 Q4 (the five-value attempt outcome is
preserved down to the AttemptEvaluationRecord; the capability-positive /
resource-neutral mapping happens HERE, at the evidence conversion), plus
docs/STATE_MACHINES.md §5 (Capability Practice / Resource Practice),
docs/DATA_MODEL.md §6 (the claim's own four-value outcome vocabulary) and
docs/DOMAIN_MODEL.md §6 (negative-evidence rule).

The boundary, in one sentence: **Teaching reports the facts of an attempt;
Learning decides what those facts are worth as evidence.** The source
value is a *teaching-owned* record (``elc.teaching.evidence.
TeachingEvidenceProposal``); Learning reads it structurally through the
:class:`TeachingEvidenceSource` Protocol below, so neither domain imports
the other (the two-way AST pin of this slice).

The conversion (STATE_MACHINES §5):

```text
SUCCESS             → the focus target's claim: SUCCESS / POSITIVE
PARTIAL             → the focus target's claim: PARTIAL / POSITIVE
FAILURE             → the focus target's claim: FAILURE / NEGATIVE
ABSTAIN             → the focus target's claim: ABSTAIN / NEUTRAL
ALTERNATIVE_SUCCESS → capability claim:    SUCCESS / POSITIVE  (only with a
                      verified capability linkage)
                      focus claim:         ABSTAIN / NEUTRAL
```

"不能把 communication success 粗暴标成整体失败" (§5): an alternative
realization is a *real* capability success, and the RESOURCE it bypassed is
recorded as neutral/not-demonstrated rather than as a failure. That is the
whole reason the five-value outcome survives into the durable record and
dies here, not earlier.

Review F4 closes the one hole that mapping had: without a *verified*
capability linkage (the caller resolves the declared capability through the
provider before building the proposal) there is a real communication success
but no capability to credit and no demonstrated resource, so the single
claim is ABSTAIN / NEUTRAL — never a POSITIVE claim on the resource, and
never a claim about a capability id nobody declared.

The mapping is driven by the capability linkage the target fixture
declares and the caller verified (``capability_linkage_target_id``):
without one there is nothing to credit, so the attempt stays a single
neutral claim on the focus target — an alternative realization of *that*
target, which is never read as a failure and never as a demonstrated
resource.

Every vocabulary word the source carries is validated against Learning's
own §5/§6/§3 enums; an unknown word is a refusal, never a silent default
(DOMAIN_MODEL §18: Learning decides VALIDATE / COMMIT / REJECT / ABSTAIN).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    LearningOpportunityId,
    Ok,
    Result,
)

__all__ = [
    "CAPABILITY_LINKAGE_CLAIM_ROLE",
    "FOCUS_CLAIM_ROLE",
    "TeachingEvidenceSource",
    "claims_for_teaching_evidence",
    "focus_claim_role",
]

#: The two claim roles of a teaching attempt (DATA_MODEL §25 includes
#: ``claim_role`` in the evidence-commit key). ``FOCUS_TARGET`` speaks about
#: the target the moment taught; ``CAPABILITY_LINKAGE`` speaks about the
#: CAPABILITY that target realizes (the §5 Resource Practice mapping).
FOCUS_CLAIM_ROLE = "FOCUS_TARGET"
CAPABILITY_LINKAGE_CLAIM_ROLE = "CAPABILITY_LINKAGE"

#: The role of the claim that speaks about the moment's focus target.
_FOCUS_ROLE = FOCUS_CLAIM_ROLE


def focus_claim_role() -> str:
    return _FOCUS_ROLE


@runtime_checkable
class TeachingEvidenceSource(Protocol):
    """The teaching-side facts Learning consumes (structural, no import).

    Deliberately primitives-only, so the two packages never share a type:
    the teaching record satisfies this Protocol by shape, and the compiler
    checks that at the coordinator's call site. The members are declared as
    read-only properties on purpose — the teaching side hands over a frozen
    value, and a settable-attribute declaration would reject it while
    claiming to describe the same facts.
    """

    @property
    def moment_id(self) -> str: ...

    @property
    def attempt_id(self) -> str: ...

    @property
    def target_type(self) -> str: ...

    @property
    def target_id(self) -> str: ...

    @property
    def capability_linkage_target_id(self) -> str | None: ...

    @property
    def attempt_outcome(self) -> str: ...

    @property
    def performance_type(self) -> str: ...

    @property
    def support_level(self) -> str: ...

    @property
    def answer_exposure_state(self) -> str: ...

    @property
    def evidence_modality(self) -> str: ...

    @property
    def exposure_estimate_id(self) -> str | None: ...

    @property
    def support_attribution_certainty(self) -> str: ...

    @property
    def support_attribution_basis(self) -> str: ...

    @property
    def evaluator_confidence(self) -> float: ...

    @property
    def evaluator_id(self) -> str: ...

    @property
    def evaluator_version(self) -> str: ...

    @property
    def opportunity_id(self) -> str | None: ...

    @property
    def post_reveal(self) -> bool: ...

    @property
    def provenance(self) -> str: ...


def _refuse(message: str) -> Err[tuple[EvidenceClaimView, ...]]:
    return Err(DomainError(code=DomainErrorCode.VALIDATION_FAILED, message=message))


def _claim(
    *,
    source: TeachingEvidenceSource,
    role: str,
    target_type: str,
    target_id: str,
    polarity: EvidencePolarity,
    outcome: AttemptOutcome,
    performance_type: PerformanceType,
    support: SupportLevel,
    exposure: ExposureLevel,
    modality: EvidenceModality,
) -> EvidenceClaimView:
    return EvidenceClaimView(
        evidence_claim_id=f"ecl-teaching-{source.attempt_id}-{role.lower()}",
        claim_role=role,
        scope=target_type,
        performance_type=performance_type,
        evidence_modality=modality,
        qualifiers=(),
        polarity=polarity,
        outcome=outcome,
        support=support,
        exposure=exposure,
        evaluator_confidence=source.evaluator_confidence,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance=source.provenance,
        opportunity_id=(
            None
            if source.opportunity_id is None
            else LearningOpportunityId(source.opportunity_id)
        ),
        target_id=target_id,
    )


#: §5 five-value attempt outcome → §6 four-value claim outcome, for the
#: claim about the target the attempt was about.
_CLAIM_OUTCOME = {
    AttemptOutcome.SUCCESS.value: AttemptOutcome.SUCCESS,
    AttemptOutcome.PARTIAL.value: AttemptOutcome.PARTIAL,
    AttemptOutcome.FAILURE.value: AttemptOutcome.FAILURE,
    AttemptOutcome.ABSTAIN.value: AttemptOutcome.ABSTAIN,
    AttemptOutcome.ALTERNATIVE_SUCCESS.value: AttemptOutcome.SUCCESS,
}

_CLAIM_POLARITY = {
    AttemptOutcome.SUCCESS.value: EvidencePolarity.POSITIVE,
    AttemptOutcome.PARTIAL.value: EvidencePolarity.POSITIVE,
    AttemptOutcome.FAILURE.value: EvidencePolarity.NEGATIVE,
    AttemptOutcome.ABSTAIN.value: EvidencePolarity.NEUTRAL,
    AttemptOutcome.ALTERNATIVE_SUCCESS.value: EvidencePolarity.POSITIVE,
}


def claims_for_teaching_evidence(
    source: TeachingEvidenceSource,
) -> Result[tuple[EvidenceClaimView, ...]]:
    """Convert one teaching proposal into §6 claims (see module docstring).

    Returns Err(VALIDATION_FAILED) when the source carries a word outside
    the canonical vocabularies — the caller (LearningController) surfaces
    that as Learning's REJECT decision; nothing is written.
    """

    try:
        outcome = AttemptOutcome(source.attempt_outcome)
        performance = PerformanceType(source.performance_type)
        support = SupportLevel(source.support_level)
        exposure = ExposureLevel(source.answer_exposure_state)
        modality = EvidenceModality(source.evidence_modality)
    except ValueError as exc:
        return _refuse(
            "teaching evidence proposal carries a word outside the canonical"
            f" vocabularies: {exc}"
        )
    if source.target_type not in ("RESOURCE", "CAPABILITY"):
        return _refuse(
            f"unknown target_type in teaching evidence: {source.target_type!r}"
        )

    if (
        outcome is AttemptOutcome.ALTERNATIVE_SUCCESS
        and source.capability_linkage_target_id
    ):
        # STATE_MACHINES §5 Resource Practice: capability positive, resource
        # neutral / not demonstrated. Two claims, one observable behavior —
        # the group keeps them together (one behavior, one group, §6).
        capability = _claim(
            source=source,
            role=CAPABILITY_LINKAGE_CLAIM_ROLE,
            target_type="CAPABILITY",
            target_id=source.capability_linkage_target_id,
            polarity=EvidencePolarity.POSITIVE,
            outcome=AttemptOutcome.SUCCESS,
            performance_type=performance,
            support=support,
            exposure=exposure,
            modality=modality,
        )
        if source.target_type == "CAPABILITY":
            # The focus target IS the capability the alternative realized:
            # credit it directly and do not invent a second claim.
            return Ok((capability,))
        resource = _claim(
            source=source,
            role=_FOCUS_ROLE,
            target_type=source.target_type,
            target_id=source.target_id,
            polarity=EvidencePolarity.NEUTRAL,
            outcome=AttemptOutcome.ABSTAIN,
            performance_type=performance,
            support=support,
            exposure=exposure,
            modality=modality,
        )
        return Ok((capability, resource))

    if outcome is AttemptOutcome.ALTERNATIVE_SUCCESS:
        # An alternative realization with no *verified* capability linkage
        # (review F4): the learner really did communicate, so this is never a
        # failure — but the target the moment taught was not demonstrated,
        # and there is no capability to credit. One honest claim: neutral /
        # not demonstrated.
        return Ok(
            (
                _claim(
                    source=source,
                    role=_FOCUS_ROLE,
                    target_type=source.target_type,
                    target_id=source.target_id,
                    polarity=EvidencePolarity.NEUTRAL,
                    outcome=AttemptOutcome.ABSTAIN,
                    performance_type=performance,
                    support=support,
                    exposure=exposure,
                    modality=modality,
                ),
            )
        )

    claim = _claim(
        source=source,
        role=_FOCUS_ROLE,
        target_type=source.target_type,
        target_id=source.target_id,
        polarity=_CLAIM_POLARITY[outcome.value],
        outcome=_CLAIM_OUTCOME[outcome.value],
        performance_type=performance,
        support=support,
        exposure=exposure,
        modality=modality,
    )
    return Ok((claim,))
