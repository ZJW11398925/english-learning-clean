"""Learning domain — Evidence kernel truth + Learner State projection.

docs/DOMAIN_MODEL.md §6, §6.1. Estimator behavioral baseline V1 lives in
behavioral_baselines/estimator (regressed via tests/behavioral).

Phase 2 P2A (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.30): the
durable evidence kernel lives in elc.learning.store (SqliteLearningStore
— conversation-store precedent), the deterministic LEARNING_EVIDENCE
producer in elc.learning.analysis, the negative-evidence policy in
elc.learning.validation. Estimator / LearnerTargetState / LearningSnapshot
entities are P2B.
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
    LearnerDimension,
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
    "ATTEMPTED_USE_PERFORMANCE_TYPES",
    "AttemptOutcome",
    "AnalysisArtifactRecord",
    "ClaimRecord",
    "DETERMINISTIC_ANALYSIS_PRODUCER_ID",
    "DETERMINISTIC_ANALYSIS_PRODUCER_VERSION",
    "ErrorAttribution",
    "EvidenceClaimView",
    "EvidenceGroupRecord",
    "EvidencePolarity",
    "EvidenceQualifier",
    "EvidenceStatus",
    "ExposureLevel",
    "FreshnessView",
    "GroupRecord",
    "LOCAL_V1_DEFAULT_USER_SCOPE",
    "LearnerDimension",
    "LearnerTargetStateRecord",
    "LearningCommands",
    "LearningController",
    "LearningEvidenceProposal",
    "LearningQueries",
    "LearningSnapshot",
    "LearningTurnAnalysis",
    "PerformanceType",
    "SqliteLearningStore",
    "SupportLevel",
    "negative_evidence_refusal",
    "produce_learning_evidence_proposal",
]
