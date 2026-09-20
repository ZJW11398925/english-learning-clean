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
    EvidenceModality,
    EvaluatorVersion,
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


@dataclass(frozen=True)
class EvidenceClaimView:
    """One claim inside a group; independently targets RESOURCE or CAPABILITY."""

    evidence_claim_id: str
    claim_role: str
    scope: str  # "RESOURCE" | "CAPABILITY"
    performance_type: PerformanceType
    evidence_modality: EvidenceModality
    qualifiers: tuple[EvidenceQualifier, ...]


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
