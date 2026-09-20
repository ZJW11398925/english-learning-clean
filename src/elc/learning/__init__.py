"""Learning domain — Evidence kernel truth + Learner State projection.

docs/DOMAIN_MODEL.md §6, §6.1. Estimator behavioral baseline V1 lives in
behavioral_baselines/estimator (regressed via tests/behavioral).

Phase 2 P2A (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.30): the
durable evidence kernel lives in elc.learning.store (SqliteLearningStore
— conversation-store precedent), the deterministic LEARNING_EVIDENCE
producer in elc.learning.analysis, the negative-evidence policy in
elc.learning.validation.

Phase 2 P2B (TASK-…44): the Evidence-Mass Estimator V1 (BF-01 v1.1
semantics, zero behavioral_baselines imports — the frozen reference is
test-oracle only) lives in elc.learning.estimator; the LearnerTargetState
projection / LearningSnapshot / freshness faces are implemented on
SqliteLearningStore (migration 0005).
"""

from elc.learning.analysis import (
    DETERMINISTIC_ANALYSIS_PRODUCER_ID,
    DETERMINISTIC_ANALYSIS_PRODUCER_VERSION,
    LearningEvidenceProposal,
    LearningTurnAnalysis,
    produce_learning_evidence_proposal,
)
from elc.learning.commands import LearningCommands
from elc.learning.controller import LearningController
from elc.learning.estimator import (
    ABILITY_DIMENSIONS,
    ALLOWED_LEARNING_FLAGS,
    ESTIMATOR_PROFILE_ID,
    ContractViolation,
    Coverage,
    EstimatorClaimView,
    EstimatorContractError,
    Freshness,
    MassDimensionState,
    Projection,
    SupportDependencyState,
    TargetStateEstimate,
    estimate_target_state,
    validate_claims,
)
from elc.learning.queries import LearningQueries
from elc.learning.store import (
    LOCAL_V1_DEFAULT_USER_SCOPE,
    AnalysisArtifactRecord,
    ClaimRecord,
    GroupRecord,
    SqliteLearningStore,
)
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidencePolarity,
    EvidenceQualifier,
    EvidenceStatus,
    ExposureLevel,
    FreshnessView,
    LearnerCoverage,
    LearnerDimension,
    LearnerDimensionState,
    LearnerFreshness,
    LearnerProjection,
    LearnerTargetStateRecord,
    LearningSnapshot,
    PerformanceType,
    SupportLevel,
)
from elc.learning.validation import (
    ATTEMPTED_USE_PERFORMANCE_TYPES,
    negative_evidence_refusal,
)

__all__ = [
    "ABILITY_DIMENSIONS",
    "ALLOWED_LEARNING_FLAGS",
    "ATTEMPTED_USE_PERFORMANCE_TYPES",
    "AttemptOutcome",
    "AnalysisArtifactRecord",
    "ClaimRecord",
    "ContractViolation",
    "Coverage",
    "DETERMINISTIC_ANALYSIS_PRODUCER_ID",
    "DETERMINISTIC_ANALYSIS_PRODUCER_VERSION",
    "ESTIMATOR_PROFILE_ID",
    "ErrorAttribution",
    "EstimatorClaimView",
    "EstimatorContractError",
    "EvidenceClaimView",
    "EvidenceGroupRecord",
    "EvidencePolarity",
    "EvidenceQualifier",
    "EvidenceStatus",
    "ExposureLevel",
    "Freshness",
    "FreshnessView",
    "GroupRecord",
    "LOCAL_V1_DEFAULT_USER_SCOPE",
    "LearnerCoverage",
    "LearnerDimension",
    "LearnerDimensionState",
    "LearnerFreshness",
    "LearnerProjection",
    "LearnerTargetStateRecord",
    "LearningCommands",
    "LearningController",
    "LearningEvidenceProposal",
    "LearningQueries",
    "LearningSnapshot",
    "LearningTurnAnalysis",
    "MassDimensionState",
    "PerformanceType",
    "Projection",
    "SqliteLearningStore",
    "SupportDependencyState",
    "SupportLevel",
    "TargetStateEstimate",
    "estimate_target_state",
    "negative_evidence_refusal",
    "produce_learning_evidence_proposal",
    "validate_claims",
]
