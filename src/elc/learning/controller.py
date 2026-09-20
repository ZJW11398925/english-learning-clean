"""Empty Learning Domain Controller (Phase 2 will implement)."""

from __future__ import annotations

from elc.learning.types import FreshnessView, LearningSnapshot
from elc.platform.types import (
    EvidenceCommitId,
    EvidenceGroupId,
    EvidenceModality,
    Result,
    StateVersion,
    TargetId,
)


class LearningController:
    """Owns evidence truth + Learner State projection. Phase 0: no logic."""

    def commit_evidence_group(self, group: object) -> Result[EvidenceCommitId]:
        raise NotImplementedError("Phase 2: Learning Evidence kernel")

    def record_self_report(
        self, user_id: str, target_id: TargetId, claim: str
    ) -> Result[EvidenceGroupId]:
        raise NotImplementedError("Phase 2: LearnerSelfReport")

    def rebuild_learner_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[StateVersion]:
        raise NotImplementedError("Phase 2: estimator projection rebuild")

    def get_learning_snapshot(
        self, learning_snapshot_id: str | None = None
    ) -> Result[LearningSnapshot]:
        raise NotImplementedError("Phase 2: LearningSnapshot view")

    def get_freshness(self, target_id: TargetId) -> Result[FreshnessView]:
        raise NotImplementedError("Phase 2: freshness projection")
