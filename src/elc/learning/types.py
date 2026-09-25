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

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    AttemptId,
    EvaluatorVersion,
    EvidenceGroupId,
    EvidenceModality,
    LearningOpportunityId,
    LearningSnapshotId,
    MomentId,
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
    docs/DOMAIN_MODEL.md §6).

    Three values, word for word, from docs/DATA_MODEL.md §6 Polarity
    (POSITIVE / NEGATIVE / NEUTRAL — review F3: NEUTRAL was missing).
    The migration CHECK constraint (0004_learning_evidence.sql,
    evidence_claim.polarity) already admits all three."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


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
    # Phase 3 P3-1B (teaching flow): the two §6 columns the Phase 0 view
    # could not carry. ``opportunity_id`` is the genuine
    # LearningOpportunityRecord the claim is an observation of (the §6
    # negative-evidence rule's first leg); ``target_id`` is the claim's own
    # target when it differs from the group's (the capability-linkage claim
    # of an alternative realization points at the CAPABILITY, not at the
    # RESOURCE the moment was about). ``None`` keeps every pre-P3-1B
    # claim's behavior byte-identical: opportunity_id stays NULL and the
    # claim targets the group's target.
    opportunity_id: LearningOpportunityId | None = None
    target_id: str | None = None
    #: P9-R3 provenance pointer: the §22 ``exposure_estimate`` row this
    #: claim's exposure is attributed to, carried as that delivery's
    #: ``action_id`` (migration 0018 keys the estimate by ``action_id``; no
    #: second id is minted). It is **not** the ``exposure`` field above:
    #: ``exposure`` is the answer-exposure ladder's fact (WHAT was shown —
    #: FULL = the target's answer form was fully exposed), while this id says
    #: *which delivery* the attribution points at (HOW CERTAINLY it reached —
    #: that estimate's own ``exposure_level`` FULL means the whole message
    #: reached the client). Same word, two facts. Declared last with a
    #: default so every existing construction site (silent evidence, the
    #: analysis path, fixtures) keeps its meaning and writes NULL;
    #: ``None`` is the honest "not attributed" value for a producer that
    #: holds no §22 fact.
    exposure_estimate_id: str | None = None


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
class LearnerDimensionState:
    """DATA_MODEL §11 per-dimension block.

    UNKNOWN is expressed as estimate=None — never 0 (docs/DOMAIN_MODEL.md
    §6). ``last_relevant_evidence_at`` is the newest claim timestamp whose
    contribution touched the dimension (implementation-defined per
    DATA_MODEL §27; BF-01 does not track it).
    """

    estimate: float | None
    confidence: float
    last_relevant_evidence_at: str | None


@dataclass(frozen=True)
class LearnerCoverage:
    """DATA_MODEL §11 coverage counts (BF-01 §12/§15 diversity basis).
    ``sessions`` counts distinct conversations (Local V1: one session ≡
    one conversation — implementation-defined, DATA_MODEL §27)."""

    evidence_groups: int
    independent_clusters: int
    sessions: int
    days: int
    contexts: int
    personas: int
    realizations: int
    modalities: int


@dataclass(frozen=True)
class LearnerFreshness:
    """DATA_MODEL §11 freshness block (BF-01 §22: strong-retrieval
    only; time never changes historical ability mass)."""

    last_strong_retrieval_at: str | None
    elapsed_since_strong_retrieval_days: float | None
    freshness_band: str


@dataclass(frozen=True)
class LearnerProjection:
    """DATA_MODEL §11 projection block (BF-01 §24 bands + §25 flags)."""

    ability_band: str
    confidence_band: str
    transfer_band: str
    support_band: str
    stability_band: str
    learning_flags: tuple[str, ...]


@dataclass(frozen=True)
class LearnerTargetStateRecord:
    """Keyed by target_type + target_id + evidence_modality (DATA_MODEL
    §11; the Phase 0 sketch lacked target_type — §11 lists it in the
    base scope). Materialized projection: deletable and rebuildable from
    append-only ACTIVE evidence (§11 "可删后重建").

    The eight §11 dimensions are recognition / guided_production /
    independent_production / spontaneous_production / transfer /
    accuracy / pragmatic_control / support_dependency (BF-01 §4).
    """

    target_type: str
    target_id: TargetId
    evidence_modality: str
    dimensions: Mapping[str, LearnerDimensionState]
    coverage: LearnerCoverage
    freshness: LearnerFreshness
    projection: LearnerProjection
    estimator_version: str
    evidence_watermark: int
    updated_at: str


@dataclass(frozen=True)
class LearningSnapshot:
    """Planner input authority view (docs/DOMAIN_MODEL.md §10; DATA_MODEL
    §12). TargetLearningView is evidence-derived ONLY — goal importance /
    review due / teaching priority / exam importance are structurally
    absent (§12 red line; pinned by test)."""

    learning_snapshot_id: LearningSnapshotId
    user_scope_id: str
    as_of: str
    estimator_version: str
    evidence_watermark: int
    targets: tuple[LearnerTargetStateRecord, ...]


@dataclass(frozen=True)
class FreshnessView:
    """What Learning may hand the Scheduler: freshness only (D-INV-009).
    The Phase 0 sketch carried a sequence number placeholder; the §11
    freshness face is timestamp + elapsed + band (implementation-defined
    field set, DATA_MODEL §27). ``stability_band`` is the strongest
    modality's §23 stability signal (None when no state exists)."""

    target_id: TargetId
    last_strong_retrieval_at: str | None
    days_since_strong_retrieval: float | None
    freshness_band: str
    stability_band: str | None
