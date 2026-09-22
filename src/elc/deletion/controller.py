"""BF-05 source-aware deletion — the authority face.

docs/DOMAIN_MODEL.md §18: a domain's controller decides, and its store
persists. Here the decision is what a scope *means* — which rows a scope
removes, what gets tombstoned, what is cancelled, and what is rebuilt
afterwards — and the rebuild half is the part this module owns:

**Rebuild goes through the faces that already exist, and only those.**

    LearnerState     elc.learning.LearningController.rebuild_learner_state
    schedule row     elc.scheduler.SchedulerController.recompute_schedule_item
    episode row      the CP4 EPISODE executor, reached by re-enqueueing its
                     deterministic job (CP4ProjectionRuntime.ensure_projection_jobs
                     + run_pending) — the same path the post-turn line uses

That is TASK-OPI-b99560d4-….19's "重建一律调用既有面…不得另建平行机制" held
structurally: this module computes no projection of its own, and it could not
— the three ports below are narrow enough that the only thing it can ask for
is "recompute this key".

**The rebuilds run after the deletion transaction, not inside it.** They have
to: each rebuild opens its own short transaction, and `short_transaction`
refuses to nest by design (docs/RUNTIME_ARCHITECTURE.md R-INV-004). The
consequence is registered rather than hidden — between the two transactions
the derived view is stale, and a rebuild that fails leaves it stale for the
caller to see in the outcome. Nothing about the deletion itself is
provisional: the removals, the tombstones and SEC-028's cancellation are one
atomic unit.

**A missing port is a reported gap, not a silent skip.** A controller built
without a Learning face cannot rebuild LearnerState, and each affected key
says so in its own :class:`RebuildAttempt` (``ok=False``) instead of vanishing
from the result. Assemblies that can rebuild pass the port; the probe suite
does, and the V1 app assembly does too.

**Scope surfaces are declarations, and the two isolation invariants are
structural.** §21's RELATIONSHIP_PAIR and §20's learning scopes name disjoint
table sets in elc/deletion/types.py, so SEC-026 ("learning deletion does not
silently delete unrelated Relationship data") and SEC-027 (its converse) are
checkable facts about the declaration rather than promises about behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Protocol, Sequence, runtime_checkable

from elc.deletion.plan import (
    apply_tombstone_guard,
    plan_external_deletion,
)
from elc.deletion.plan import (
    is_tombstoned as _is_tombstoned,
)
from elc.deletion.store import SqliteDeletionStore
from elc.deletion.types import (
    DeletionExecution,
    DeletionOutcome,
    DeletionRequest,
    DeletionScope,
    EpisodeRebuildKey,
    ExternalDeletionPlan,
    ExternalDisclosure,
    RebuildAttempt,
    TargetKey,
    TombstoneRecord,
)
from elc.platform.types import (
    ConversationId,
    Err,
    EvidenceModality,
    Ok,
    ProjectionJobId,
    Result,
    StateVersion,
    TargetId,
    TurnId,
)

if TYPE_CHECKING:
    # Annotations only (the repository's cold-start rule): importing these at
    # runtime would deepen elc.deletion's import graph for no behavioural
    # benefit — every port below is structural and the runtime never needs
    # the class objects.
    from elc.runtime.projections import ProjectionRunResult
    from elc.scheduler.types import ScheduleItem

__all__ = [
    "DeletionController",
    "LearnerStateRebuildPort",
    "ProjectionRebuildPort",
    "ScheduleRecomputePort",
]


@runtime_checkable
class LearnerStateRebuildPort(Protocol):
    """The one Learning face a deletion needs (elc.learning.controller)."""

    def rebuild_learner_state(
        self, target_id: TargetId, evidence_modality: EvidenceModality
    ) -> Result[StateVersion]:
        """Recompute the §11 projection for one target × modality from the
        surviving ACTIVE claims — the shipped rebuild, never a second one."""
        ...


@runtime_checkable
class ScheduleRecomputePort(Protocol):
    """The two Scheduler faces a deletion needs (elc.scheduler.controller)."""

    def get_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[ScheduleItem | None]:
        """The current row for a modality key (``None`` = never written).

        Read only to decide *whether* there is a row to recompute: a
        recomputation writes a row even when nothing is scheduled (its own
        documented face), and a deletion must not mint schedule rows for
        targets that never had one.
        """
        ...

    def recompute_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
        as_of: str,
    ) -> Result[ScheduleItem]:
        """Recompute and commit the current row for one modality key."""
        ...


@runtime_checkable
class ProjectionRebuildPort(Protocol):
    """The CP4 faces used to re-derive an episode projection.

    Deliberately the *runtime's* own two calls rather than the executor's
    ``project``: the executor expects a claimed job, and hand-building one
    would be a fake claim. Re-enqueueing the deterministic id and draining
    the conversation's queue is the shipped path — the same one the post-turn
    line takes.
    """

    def ensure_projection_jobs(
        self, turn_id: TurnId
    ) -> Result[tuple[ProjectionJobId, ...]]:
        """Make this turn's CP4 jobs exist (idempotent)."""
        ...

    def run_pending(
        self, conversation_id: ConversationId
    ) -> Result[tuple[ProjectionRunResult, ...]]:
        """Drain the conversation's pending queue."""
        ...


class DeletionController:
    """The authority face: run a scope, then rebuild what still has a source."""

    def __init__(
        self,
        store: SqliteDeletionStore,
        *,
        learning: LearnerStateRebuildPort | None = None,
        scheduler: ScheduleRecomputePort | None = None,
        projections: ProjectionRebuildPort | None = None,
    ) -> None:
        self._store = store
        self._learning = learning
        self._scheduler = scheduler
        self._projections = projections

    # -- DeletionCommands ---------------------------------------------------

    def execute(self, request: DeletionRequest) -> Result[DeletionOutcome]:
        """Remove the request's scope, then rebuild what survived it (§18).

        Reporting rule: a rebuild failure never rolls the deletion back — the
        canonical source is gone and pretending otherwise would resurrect it —
        so the failure travels in the outcome, one attempt per key.
        """

        result = self._store.execute(request)
        if isinstance(result, Err):
            return result
        execution = result.value
        rebuilds = (
            *self._rebuild_learner_states(execution),
            *self._rebuild_schedules(execution),
            *self._rebuild_episodes(execution),
        )
        return Ok(
            DeletionOutcome(
                scope=execution.scope,
                execution=execution,
                rebuilds=tuple(rebuilds),
                notes=execution.notes,
            )
        )

    # -- DeletionQueries ----------------------------------------------------

    def list_tombstones(
        self, scope: DeletionScope | None = None
    ) -> Result[tuple[TombstoneRecord, ...]]:
        return self._store.list_tombstones(scope)

    def is_tombstoned(self, *, entity_kind: str, entity_id: str) -> Result[bool]:
        ledger = self._store.tombstone_ledger()
        if isinstance(ledger, Err):
            return ledger
        return Ok(
            _is_tombstoned(
                ledger.value, entity_kind=entity_kind, entity_id=entity_id
            )
        )

    def filter_tombstoned(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        entity_kind: str,
        id_field: str = "id",
    ) -> Result[tuple[Mapping[str, object], ...]]:
        ledger = self._store.tombstone_ledger()
        if isinstance(ledger, Err):
            return ledger
        return Ok(
            apply_tombstone_guard(
                records,
                ledger=ledger.value,
                entity_kind=entity_kind,
                id_field=id_field,
            )
        )

    def plan_external_delete(
        self, disclosure: ExternalDisclosure
    ) -> Result[ExternalDeletionPlan]:
        return Ok(plan_external_deletion(disclosure))

    # -- rebuilds -----------------------------------------------------------

    def _rebuild_learner_states(
        self, execution: DeletionExecution
    ) -> tuple[RebuildAttempt, ...]:
        attempts: list[RebuildAttempt] = []
        for key in execution.affected_targets:
            attempts.append(self._rebuild_learner_state(key))
        return tuple(attempts)

    def _rebuild_learner_state(self, key: TargetKey) -> RebuildAttempt:
        if self._learning is None:
            return RebuildAttempt(
                kind="LEARNER_STATE",
                key=_key_text(key),
                ok=False,
                detail=(
                    "no Learning face is wired into this controller, so the"
                    " materialized LearnerState of this key was removed"
                    " without a rebuild (§18's rebuild clause is unmet for it)"
                ),
            )
        result = self._learning.rebuild_learner_state(
            TargetId(key.target_id), EvidenceModality(key.evidence_modality)
        )
        if isinstance(result, Err):
            return RebuildAttempt(
                kind="LEARNER_STATE",
                key=_key_text(key),
                ok=False,
                detail=result.error.message,
            )
        return RebuildAttempt(
            kind="LEARNER_STATE",
            key=_key_text(key),
            ok=True,
            detail=f"state version {result.value}",
        )

    def _rebuild_schedules(
        self, execution: DeletionExecution
    ) -> tuple[RebuildAttempt, ...]:
        attempts: list[RebuildAttempt] = []
        for key in execution.affected_targets:
            attempts.append(self._rebuild_schedule(key, execution.deleted_at))
        return tuple(attempts)

    def _rebuild_schedule(
        self, key: TargetKey, as_of: str
    ) -> RebuildAttempt:
        if self._scheduler is None:
            return RebuildAttempt(
                kind="SCHEDULE_ITEM",
                key=_key_text(key),
                ok=False,
                detail=(
                    "no Scheduler face is wired into this controller, so the"
                    " schedule row of this key is whatever the deletion left"
                ),
            )
        modality = EvidenceModality(key.evidence_modality)
        target_id = TargetId(key.target_id)
        existing = self._scheduler.get_schedule_item(
            key.target_type, target_id, modality
        )
        if isinstance(existing, Err):
            return RebuildAttempt(
                kind="SCHEDULE_ITEM",
                key=_key_text(key),
                ok=False,
                detail=existing.error.message,
            )
        if existing.value is None:
            return RebuildAttempt(
                kind="SCHEDULE_ITEM",
                key=_key_text(key),
                ok=True,
                detail=(
                    "no schedule row existed for this key, and a deletion"
                    " does not mint one"
                ),
            )
        recomputed = self._scheduler.recompute_schedule_item(
            key.target_type, target_id, modality, as_of
        )
        if isinstance(recomputed, Err):
            return RebuildAttempt(
                kind="SCHEDULE_ITEM",
                key=_key_text(key),
                ok=False,
                detail=recomputed.error.message,
            )
        return RebuildAttempt(
            kind="SCHEDULE_ITEM",
            key=_key_text(key),
            ok=True,
            detail=f"review state {recomputed.value.review_state.value}",
        )

    def _rebuild_episodes(
        self, execution: DeletionExecution
    ) -> tuple[RebuildAttempt, ...]:
        attempts: list[RebuildAttempt] = []
        for key in execution.affected_episodes:
            attempts.append(self._rebuild_episode(key))
        return tuple(attempts)

    def _rebuild_episode(self, key: EpisodeRebuildKey) -> RebuildAttempt:
        conversation_id = key.conversation_id
        anchor_turn_id = key.anchor_turn_id
        label = f"episode of {conversation_id}"
        if self._projections is None:
            return RebuildAttempt(
                kind="EPISODE",
                key=label,
                ok=False,
                detail=(
                    "no CP4 projection runtime is wired into this controller,"
                    " so this conversation's episode projection was"
                    " invalidated without being re-derived"
                ),
            )
        ensured = self._projections.ensure_projection_jobs(
            TurnId(anchor_turn_id)
        )
        if isinstance(ensured, Err):
            return RebuildAttempt(
                kind="EPISODE", key=label, ok=False,
                detail=ensured.error.message,
            )
        ran = self._projections.run_pending(ConversationId(conversation_id))
        if isinstance(ran, Err):
            return RebuildAttempt(
                kind="EPISODE", key=label, ok=False, detail=ran.error.message
            )
        return RebuildAttempt(
            kind="EPISODE",
            key=label,
            ok=True,
            detail=f"{len(ran.value)} projection run(s) reported",
        )


def _key_text(key: TargetKey) -> str:
    return f"{key.target_type}/{key.target_id}/{key.evidence_modality}"
