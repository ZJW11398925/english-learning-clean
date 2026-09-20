"""Learning domain — Evidence kernel truth + Learner State projection.

docs/DOMAIN_MODEL.md §6, §6.1. Estimator behavioral baseline V1 lives in
behavioral_baselines/estimator (regressed via tests/behavioral).
"""

from elc.learning.commands import LearningCommands
from elc.learning.controller import LearningController
from elc.learning.queries import LearningQueries
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

__all__ = [
    "AttemptOutcome",
    "ErrorAttribution",
    "EvidenceClaimView",
    "EvidenceGroupRecord",
    "EvidencePolarity",
    "EvidenceQualifier",
    "EvidenceStatus",
    "ExposureLevel",
    "FreshnessView",
    "LearnerDimension",
    "LearnerTargetStateRecord",
    "LearningCommands",
    "LearningController",
    "LearningQueries",
    "LearningSnapshot",
    "PerformanceType",
    "SupportLevel",
]
