"""Learning Domain Controller — the authority face over the evidence
kernel (Phase 3 P3-0, TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.55 ②).

docs/DOMAIN_MODEL.md §18: the Domain Controller decides VALIDATE / COMMIT
/ REJECT / ABSTAIN. For Learning those decisions live in the durable
kernel (``SqliteLearningStore`` — the §6 negative-evidence gate, the CP1
commit unit, the §7-contract rebuild refusal), so this controller is a
real authority *face* that delegates to the store: Phase 3 consumers
(DecisionCycle assembly, P3-1) go through the controller instead of
binding to the store directly. The frozen Phase 0 protocol semantics are
unchanged — ``LearningCommands`` / ``LearningQueries`` (elc.learning.
commands / elc.learning.queries) — and the store stays the only writer,
so every store-direct test keeps passing against the same behavior.

The store's keyword-only extension points (``source_turn_id`` /
``conversation_id`` for the §6 column set, ``user_turn_id`` for the §8
column set) surface as optional keyword arguments with identical
defaults: calling the controller with the bare Phase 0 protocol shape
reaches the store's documented Err exactly as a store-direct call would.
"""

from __future__ import annotations

from elc.learning.store import SqliteLearningStore
from elc.learning.types import (
    EvidenceGroupRecord,
    FreshnessView,
    LearnerTargetStateRecord,
    LearningSnapshot,
)
from elc.platform.types import (
    EvidenceCommitId,
    EvidenceGroupId,
    EvidenceModality,
    LearningSnapshotId,
    Ok,
    Result,
    StateVersion,
    TargetId,
    TurnId,
    UserTurnId,
)

__all__ = ["LearningController"]


class LearningController:
    """Owns evidence truth + Learner State projection.

    Delegates to ``SqliteLearningStore`` (constructor-injected; the store
    carries the epoch fence and all SQL). Phase 3 consumers use this face.
    """

    def __init__(self, store: SqliteLearningStore) -> None:
        self._store = store

    # -- LearningCommands ----------------------------------------------------

    def commit_evidence_group(
        self,
        group: EvidenceGroupRecord,
        *,
        source_turn_id: TurnId | None = None,
        conversation_id: str | None = None,
        persona_id: str | None = None,
    ) -> Result[EvidenceCommitId]:
        """CP1 through the authority face — same validation, idempotency,
        and watermark semantics as the store (the store decides)."""

        return self._store.commit_evidence_group(
            group,
            source_turn_id=source_turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
        )

    def record_self_report(
        self,
        user_id: str,
        target_id: TargetId,
        claim: str,
        *,
        user_turn_id: UserTurnId | None = None,
        target_type: str = "RESOURCE",
        scope: str | None = None,
    ) -> Result[EvidenceGroupId]:
        """Self reports never enter the evidence kernel (§8) — the store's
        guard applies unchanged."""

        return self._store.record_self_report(
            user_id,
            target_id,
            claim,
            user_turn_id=user_turn_id,
            target_type=target_type,
            scope=scope,
        )

    def rebuild_learner_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[StateVersion]:
        """Recompute the projection from append-only evidence."""

        rebuilt = self._store.rebuild_learner_state(
            target_id, evidence_modality
        )
        if isinstance(rebuilt, Ok):
            # The store's frozen face returns the opaque version str;
            # the protocol face names it StateVersion (the same value).
            return Ok(StateVersion(rebuilt.value))
        return rebuilt

    # -- LearningQueries -----------------------------------------------------

    def get_learner_target_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[LearnerTargetStateRecord | None]:
        """UNKNOWN is estimate=None — never 0 (docs/DOMAIN_MODEL.md §6)."""

        return self._store.get_learner_target_state(
            target_id, evidence_modality
        )

    def get_learning_snapshot(
        self, learning_snapshot_id: LearningSnapshotId | None = None
    ) -> Result[LearningSnapshot]:
        """Planner input authority (docs/DOMAIN_MODEL.md §10). Read-time
        watermark-consistency refusal rides the store (TASK-…55 ①)."""

        return self._store.get_learning_snapshot(learning_snapshot_id)

    def get_freshness(self, target_id: TargetId) -> Result[FreshnessView]:
        """The only thing Learning owes the Scheduler (D-INV-009)."""

        return self._store.get_freshness(target_id)
