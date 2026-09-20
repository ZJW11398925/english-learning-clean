"""Learning domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.learning.types import (
    FreshnessView,
    LearnerTargetStateRecord,
    LearningSnapshot,
)
from elc.platform.types import (
    EvidenceModality,
    LearningSnapshotId,
    Result,
    TargetId,
)


@runtime_checkable
class LearningQueries(Protocol):
    """Learner State projection + freshness reads."""

    def get_learner_target_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[LearnerTargetStateRecord | None]:
        """UNKNOWN is estimate=None — never 0 (docs/DOMAIN_MODEL.md §6)."""
        ...

    def get_learning_snapshot(
        self, learning_snapshot_id: LearningSnapshotId | None = None
    ) -> Result[LearningSnapshot]:
        """Planner input authority (docs/DOMAIN_MODEL.md §10)."""
        ...

    def get_freshness(self, target_id: TargetId) -> Result[FreshnessView]:
        """The only thing Learning owes the Scheduler (D-INV-009)."""
        ...
