"""Learning domain command face — evidence kernel writes.

Authority: docs/DOMAIN_MODEL.md §2 — whether user behavior forms Learning
Evidence is decided by Learning. Negative evidence requires a genuine
Opportunity or attempted use (§6). Planner never writes Learner State
(D-INV-004); Relationship Memory never affects mastery (D-INV-005).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.learning.types import EvidenceGroupRecord
from elc.platform.types import (
    EvidenceCommitId,
    EvidenceGroupId,
    EvidenceModality,
    Result,
    StateVersion,
    TargetId,
)


@runtime_checkable
class LearningCommands(Protocol):
    """Canonical evidence writes (append-first, idempotent commit keys)."""

    def commit_evidence_group(
        self, group: EvidenceGroupRecord
    ) -> Result[EvidenceCommitId]:
        """Idempotency: moment_id + attempt_id + target_id + claim_role
        + evaluator_version (docs/DATA_MODEL.md §25)."""
        ...

    def record_self_report(
        self,
        user_id: str,
        target_id: TargetId,
        claim: str,
    ) -> Result[EvidenceGroupId]:
        """SelfReport/ExpressionNeed never enter ability mass (BF-01)."""
        ...

    def rebuild_learner_state(
        self,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[StateVersion]:
        """Recompute the projection from append-only evidence."""
        ...
