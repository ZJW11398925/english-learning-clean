"""Learning evidence validation policy (pure).

DOMAIN_MODEL §6 Negative evidence rule, word for word:

    只有：
    genuine Opportunity
    or attempted use
    才能形成 target-specific negative evidence。

The decision point is Learning's validation face (TASK-…30 deliverable
⑤): a proposed EvidenceClaim with polarity=NEGATIVE is rejected unless
(a) a genuine LearningOpportunityRecord exists for the same target, or
(b) the claim's own performance type is an attempted use.

"Attempted use" reading (adjudicated here, reported as a deviation-note):
every production-side performance type is itself an attempted use of the
target — IMITATIVE/GUIDED/INDEPENDENT/SPONTANEOUS_PRODUCTION, SELF_REPAIR,
FAILED_ATTEMPT and MISUSE are all behaviors where the learner tried to
produce/repair the target. RECOGNITION is passive (comprehension-side)
and is not an attempt, so a RECOGNITION negative claim needs a genuine
Opportunity on record. ExpressionNeed is NOT negative mastery evidence
(DATA_MODEL §10) and never satisfies this gate.

Pure module: no sqlite3, no SQL, no DB call surface.
"""

from __future__ import annotations

from elc.learning.types import EvidenceClaimView, PerformanceType
from elc.platform.types import DomainError, DomainErrorCode

__all__ = [
    "ATTEMPTED_USE_PERFORMANCE_TYPES",
    "negative_evidence_refusal",
]

#: Performance types that constitute an attempted use of the target
#: (DOMAIN_MODEL §6 negative-evidence rule, second leg). Everything
#: except RECOGNITION — see the module docstring.
ATTEMPTED_USE_PERFORMANCE_TYPES: frozenset[PerformanceType] = frozenset(
    performance
    for performance in PerformanceType
    if performance != PerformanceType.RECOGNITION
)


def negative_evidence_refusal(
    claim: EvidenceClaimView, has_genuine_opportunity: bool
) -> DomainError | None:
    """Pure DOMAIN_MODEL §6 decision for one proposed claim: the refusal
    when a target-specific negative claim lacks both a genuine
    Opportunity and attempted use; None when the claim may pass.

    ``has_genuine_opportunity`` is the durable fact the store looks up
    (a LearningOpportunityRecord row for the same target_type/target_id);
    this function stays pure.
    """

    if claim.polarity.value != "NEGATIVE":
        return None
    if has_genuine_opportunity:
        return None
    if claim.performance_type in ATTEMPTED_USE_PERFORMANCE_TYPES:
        return None
    return DomainError(
        code=DomainErrorCode.VALIDATION_FAILED,
        message=(
            "target-specific negative evidence requires a genuine"
            " Opportunity or an attempted use (DOMAIN_MODEL §6 negative"
            " evidence rule): polarity=NEGATIVE, performance_type="
            f"{claim.performance_type.value}, no"
            " LearningOpportunityRecord for the target"
        ),
    )
