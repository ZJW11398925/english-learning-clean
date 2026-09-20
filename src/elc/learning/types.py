"""Learning domain — evidence truth and the Learner State projection.

Source of truth (docs/DOMAIN_MODEL.md §6): EvidenceGroup, EvidenceClaim,
LearningOpportunityRecord, LearnerSelfReport. Learner State is a
materialized, rebuildable projection (append-only evidence; state carries
estimator_version + evidence_watermark).

Does NOT own: review due decisions (D-INV-009 — Scheduler decides;
Learning only provides freshness), transfer need decisions (D-INV-010),
relationship memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    AttemptId,
    EstimatorVersion,
    EvaluatorVersion,
    EvidenceGroupId,
    EvidenceModality,
    LearningSnapshotId,
    MomentId,
    StateVersion,
    TargetId,
)


class PerformanceType(StrEnum):
    """docs/DOMAIN_MODEL.md §6 primary performance types."""

    RECOGNITION = "RECOGNITION"
    IMITATIVE_PRODUCTION = "IMITATIVE_PRODUCTION"
    GUIDED_PRODUCTION = "GUIDED_PRODUCTION"
    INDEPENDENT_PRODUCTION = "INDEPENDENT_PRODUCTION"
    SPONTANEOUS_PRODUCTION = "SPONTANEOUS_PRODUCTION"
    SELF_REPAIR = "SELF_REPAIR"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"
    MISUSE = "MISUSE"


class EvidenceQualifier(StrEnum):
    """docs/DOMAIN_MODEL.md §6 qualifiers (delay/transfer are not extra wins)."""

    DELAYED = "DELAYED"
    CROSS_CONTEXT = "CROSS_CONTEXT"
    CROSS_PERSONA = "CROSS_PERSONA"
    CROSS_MODALITY = "CROSS_MODALITY"
    NOVEL_REALIZATION = "NOVEL_REALIZATION"
    LOW_SUPPORT = "LOW_SUPPORT"
    HIGH_CONTEXT_NOVELTY = "HIGH_CONTEXT_NOVELTY"


class LearnerDimension(StrEnum):
    """docs/DOMAIN_MODEL.md §6 Learner State dimensions (base + derived)."""

    RECOGNITION = "recognition"
    GUIDED_PRODUCTION = "guided_production"
    INDEPENDENT_PRODUCTION = "independent_production"
    SPONTANEOUS_PRODUCTION = "spontaneous_production"
    ACCURACY = "accuracy"
    PRAGMATIC_CONTROL = "pragmatic_control"
    TRANSFER = "transfer"
    SUPPORT_DEPENDENCY = "support_dependency"


class EvidencePolarity(StrEnum):
    """BF-01A claim polarity (behavioral_baselines/estimator/
    BF-01_Estimator_V1_Operational_Spec_v1.1.md; negative-evidence rule
    docs/DOMAIN_MODEL.md §6)."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class AttemptOutcome(StrEnum):
    """Attempt evaluation outcomes, word for word, from
    docs/STATE_MACHINES.md §5 lines 152-157."""

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILURE = "FAILURE"
    ALTERNATIVE_SUCCESS = "ALTERNATIVE_SUCCESS"
    ABSTAIN = "ABSTAIN"


class SupportLevel(StrEnum):
    """Teaching support levels, word for word, from
    docs/STATE_MACHINES.md §3 lines 91-98."""

    NONE = "NONE"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    SEMANTIC_HINT = "SEMANTIC_HINT"
    STRUCTURAL_HINT = "STRUCTURAL_HINT"
    PARTIAL_FORM = "PARTIAL_FORM"
    FULL_FORM_SHOWN = "FULL_FORM_SHOWN"


class ExposureLevel(StrEnum):
    """ExposureEstimate exposure_level, word for word, from
    docs/STATE_MACHINES.md §13 lines 434-438."""

    NONE = "NONE"
    PARTIAL = "PARTIAL"
    FULL = "FULL"


class ErrorAttribution(StrEnum):
    """BF-01A error attribution vocabulary — the calibration keys of
    estimator_reference_profile_v1_1.json error_attribution_multiplier."""

    LIKELY_SLIP = "LIKELY_SLIP"
    UNKNOWN = "UNKNOWN"
    LIKELY_KNOWLEDGE_GAP = "LIKELY_KNOWLEDGE_GAP"
    SYSTEMATIC_PATTERN = "SYSTEMATIC_PATTERN"


class EvidenceStatus(StrEnum):
    """Evidence correction states, word for word, from
    docs/STATE_MACHINES.md §18 lines 571-575. Append-only: only ACTIVE
    evidence enters estimation (BF-01 §29)."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class EvidenceClaimView:
    """One claim inside a group; independently targets RESOURCE or CAPABILITY.

    Field set mirrors the BF-01A canonical claim
    (behavioral_baselines/estimator/BF-01_Estimator_V1_Operational_Spec_
    v1.1.md §7-§9, §27, §29; stress-case claim dicts): polarity, outcome,
    support, exposure, evaluator_confidence, error_attribution, accuracy,
    pragmatic_fit, status, provenance.
    """

    evidence_claim_id: str
    claim_role: str
    scope: str  # "RESOURCE" | "CAPABILITY"
    performance_type: PerformanceType
    evidence_modality: EvidenceModality
    qualifiers: tuple[EvidenceQualifier, ...]
    polarity: EvidencePolarity
    outcome: AttemptOutcome
    support: SupportLevel
    exposure: ExposureLevel
    evaluator_confidence: float  # [0,1]; below claim_min_confidence → ignored
    error_attribution: ErrorAttribution
    accuracy: float | None  # [0,1] quality input (BF-01 §27)
    pragmatic_fit: float | None  # [0,1] quality input (BF-01 §27)
    status: EvidenceStatus
    provenance: str  # source refs (turn/moment/persona), BF-01A provenance


@dataclass(frozen=True)
class EvidenceGroupRecord:
    """docs/DOMAIN_MODEL.md §6 Learning Evidence kernel aggregate."""

    evidence_group_id: EvidenceGroupId
    moment_id: MomentId | None
    attempt_id: AttemptId | None
    target_id: TargetId
    evaluator_version: EvaluatorVersion
    claims: tuple[EvidenceClaimView, ...]


@dataclass(frozen=True)
class LearnerTargetStateRecord:
    """Keyed by target_type + target_id + evidence_modality (DATA_MODEL §24.14).

    UNKNOWN is expressed as estimate=None — never 0 (docs/DOMAIN_MODEL.md §6).
    """

    target_id: TargetId
    evidence_modality: EvidenceModality
    estimator_version: EstimatorVersion
    evidence_watermark: str
    state_version: StateVersion
    estimates: dict[str, float | None]
    confidences: dict[str, float]


@dataclass(frozen=True)
class LearningSnapshot:
    """Planner input authority view (docs/DOMAIN_MODEL.md §10)."""

    learning_snapshot_id: LearningSnapshotId
    evidence_watermark: str
    estimator_version: EstimatorVersion
    states: tuple[LearnerTargetStateRecord, ...]


@dataclass(frozen=True)
class FreshnessView:
    """What Learning may hand the Scheduler: freshness only (D-INV-009)."""

    target_id: TargetId
    last_strong_retrieval_seq: int | None
    stability_signal: float | None
