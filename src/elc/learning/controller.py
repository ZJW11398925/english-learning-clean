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
so every store-direct test still passes against the same behavior.

The store's keyword-only extension points (``source_turn_id`` /
``conversation_id`` for the §6 column set, ``user_turn_id`` for the §8
column set, ``evaluator_id`` for §6's evaluator provenance) surface as
optional keyword arguments with identical defaults: calling the controller
with the bare Phase 0 protocol shape reaches the store's documented Err
exactly as a store-direct call would.

Exposed face vs store-only methods (P3-0 review F1, DEC-…eaaa5a1d.58 —
declared so no consumer has to guess): the controller exposes the Phase 0
protocol quartet (``commit_evidence_group`` / ``record_self_report`` /
``rebuild_learner_state`` / ``record_opportunity``) plus the read faces
(``get_learner_target_state`` / ``get_learning_snapshot`` /
``get_freshness``) and the P3-1A coordination extension
``stale_projection_targets``. The following store methods are deliberately
NOT exposed yet — a consumer needing them must go to the store directly
and that is a known, named gap, not an oversight: ``supersede_claim`` /
``invalidate_claim`` (STATE_MACHINES §18 correction faces: their Phase 3+
consumer is the explicit re-evaluation path), ``get_evidence_watermark``
(the raw sequence number: consumers that need freshness semantics use
``get_freshness`` / the snapshot), and the store's internal analysis
helpers.
"""

from __future__ import annotations

from elc.learning.store import SqliteLearningStore
from elc.learning.teaching_evidence import TeachingEvidenceSource
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
    LearningOpportunityId,
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
        evaluator_id: str = "learning-store-v1",
    ) -> Result[EvidenceCommitId]:
        """CP1 through the authority face — same validation, idempotency,
        and watermark semantics as the store (the store decides).

        ``evaluator_id`` rides through unchanged (P3-0 review F1): the
        §6 column is the evaluator provenance of the committed claims, so
        an evaluator-specific consumer stays on the authority face instead
        of being pushed to the store."""

        return self._store.commit_evidence_group(
            group,
            source_turn_id=source_turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
            evaluator_id=evaluator_id,
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

    def record_opportunity(
        self,
        *,
        source_turn_id: TurnId | None,
        target_type: str,
        target_id: TargetId,
        opportunity_type: str,
        target_explicitness: str,
        attempt_observed: bool,
        alternative_realizations_allowed: bool,
        teaching_moment_id: str | None = None,
        learning_opportunity_id: LearningOpportunityId | None = None,
    ) -> Result[LearningOpportunityId]:
        """Durable LearningOpportunityRecord (DATA_MODEL §7) through the
        authority face — the "genuine Opportunity" leg of the §6 negative
        evidence rule, same keywords and semantics as the store.

        Phase 3 P3-1A lift (TASK-…17 ⑧): the method existed on the store
        only, so the opportunity provenance — the thing a later
        ``claim.opportunity_id`` links to — had no authority-face entry;
        it now returns the minted/replayed ``LearningOpportunityId``.
        ``teaching_moment_id`` is the moment link when the opportunity was
        created inside a teaching moment (the P3-1B teaching flow)."""

        return self._store.record_opportunity(
            source_turn_id=source_turn_id,
            target_type=target_type,
            target_id=target_id,
            opportunity_type=opportunity_type,
            target_explicitness=target_explicitness,
            attempt_observed=attempt_observed,
            alternative_realizations_allowed=alternative_realizations_allowed,
            teaching_moment_id=teaching_moment_id,
            learning_opportunity_id=learning_opportunity_id,
        )

    # -- Phase 3 P3-1B: the teaching evidence face ---------------------------

    def commit_teaching_evidence(
        self,
        proposal: TeachingEvidenceSource,
        *,
        source_turn_id: TurnId,
        conversation_id: str,
        persona_id: str | None = None,
    ) -> Result[EvidenceCommitId]:
        """CP1 for one teaching attempt (TASK-…2.2 ③④).

        The proposal is the teaching-side record
        (``elc.teaching.evidence.TeachingEvidenceProposal``), consumed
        structurally: Learning owns the §5 → §6 conversion — including the
        capability-positive / resource-neutral mapping of an
        ALTERNATIVE_SUCCESS — and the durable LOR association checks. The
        caller (the orchestrator) hands the facts over; Learning decides.
        """

        return self._store.commit_teaching_evidence(
            proposal,
            source_turn_id=source_turn_id,
            conversation_id=conversation_id,
            persona_id=persona_id,
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
        """UNKNOWN is estimate=None — never 0 (docs/DOMAIN_MODEL.md §6).

        Deliberately outside the snapshot read-time watermark gate: a
        single row reports its own stored stamp (the store docstring
        carries the F5 note)."""

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

    # -- Phase 3 extension (declared; not part of the Phase 0 protocols) -----

    def stale_projection_targets(
        self,
    ) -> Result[tuple[tuple[TargetId, EvidenceModality], ...]]:
        """The lagging §11 rows a refused snapshot read must be repaired
        on (P3-1A: the DecisionCycle coordinator rebuilds these, re-reads,
        and only then opens a cycle). Same order and staleness rule as the
        refusal itself — the store computes both from one query."""

        stale = self._store.stale_projection_targets()
        if isinstance(stale, Ok):
            return Ok(
                tuple(
                    (target_id, EvidenceModality(modality))
                    for target_id, modality in stale.value
                )
            )
        return stale
