"""The §14 planner records — the CP2 durable half's port (P8-0).

docs/DATA_MODEL.md §14 "Planner Data" names four records, and
docs/RUNTIME_ARCHITECTURE.md §6 CP2 is the commit point that makes them
durable: a cycle's ``PlannerExecutionStatus`` (always), its
``PlannerEvaluation`` (always — the trace of what the run looked at), its
``PlannerDecision`` (only when the run succeeded), and the turn-level
``RuntimeDecisionOutcome`` (always; ``NORMAL`` for a successful run and
``DEGRADED_NO_AUTOMATIC_TEACHING`` for a degraded one). RA §6's failure path
is the rule the last pair serves: "不伪造 ``PlannerDecision``" — a degraded
run's durable answer is a *status*, never a decision.

This module is SQL-free and holds no clock: it declares the port
(:class:`PlannerRecordStore`), the record one commit returns
(:class:`PlannerCycleRecords`), and — below — the **one** place where §14's
column names are mapped to the implementation's field names. The durable
statements live in ``elc.platform.db.planner_store`` (Gate item 2's split: the
authority is a port, the SQL is in the platform db layer).

---------------------------------------------------------------------------
The column map (§14 ↔ implementation) — stated once, here
---------------------------------------------------------------------------

===========================  ==============================================
§14 column                   implementation
===========================  ==============================================
``planner_evaluation_id``    ``PlannerEvaluation.planner_evaluation_id``
``decision_cycle_id``        ``PlannerEvaluation.decision_cycle_id``
``frontier_candidate_ids[]`` ``PlannerEvaluation.frontier_candidate_ids``
``ranked_candidate_ids[]``   ``PlannerEvaluation.ranked_candidates`` —
                             the candidate ids, in the record's order
``factor_trace``             ``PlannerEvaluation.reason_trace``
``planner_version``          ``PlannerEvaluation.planner_version``
``policy_profile_version``   ``PlannerEvaluation.policy_version``
``created_at``               stamped by the store (no record field)
===========================  ==============================================

The right-hand names are P7's and are **not** renamed (the kernel, the
frontier and every phase-7 test speak them); §14's names are the durable
columns and are not renamed either. ``ranked_candidate_ids`` is ids-only on
purpose: §14 stores the ranking, not the candidates — a durable row cannot
rebuild ``TargetCandidate`` objects, which is why the read face here answers
:class:`~elc.platform.types.PlannerEvaluationRecord` (the id-shaped row) and
not :class:`~elc.planner.types.PlannerEvaluation`, and why
``PlannerService.get_planner_evaluation`` (whose declared answer *is* the
object shape) is still refused — see that method's docstring.

---------------------------------------------------------------------------
**Declared judgements.** Each entry is this cut's reading rather than a
quotation, and each names the condition that re-opens it.
---------------------------------------------------------------------------

1. **The write face takes a ``PlanningOutcome`` and the cycle's turn, and
   derives the outcome value.** §14's ``RuntimeDecisionOutcome.outcome`` is a
   function of the execution status (``SUCCEEDED`` ⟹ ``NORMAL``; the other
   three ⟹ ``DEGRADED_NO_AUTOMATIC_TEACHING``, BF-02 §5), and the function
   already exists — :func:`elc.planner.kernel.runtime_decision_outcome_of`.
   The store calls it rather than re-spelling the rule, so there is one
   implementation of the coupling; a caller supplies only §14's
   ``reason_codes`` (see judgement 4). Revisit: a third consumer needs the
   rule outside a kernel import, or canonical text makes the runtime outcome
   an *input* rather than a consequence.
2. **Same-cycle re-entry is a pure replay; a same-turn new cycle upserts.**
   ``planner_execution_status``'s key is the cycle, so a cycle that already
   has a status row is already decided: the unit reads its rows back and
   writes nothing (RA §23's "Crash after CP1 … 不重复 Evidence" extended to
   the Planner: no second evaluation, no second decision). The
   ``runtime_decision_outcome`` row is keyed by the **turn**, so a second CP2
   of the same turn under a new cycle moves that row to name the newest cycle
   — the row is the turn's current answer, not a history. Revisit: a
   canonical revision gives the outcome row a cycle-keyed identity, or a
   replay that disagrees with the durable status row has to be *accepted*
   rather than refused.
3. **A replay that disagrees is refused, not overwritten.** The replay path
   compares the submitted status (word and error code) against the durable
   row and answers ``CONFLICT`` on a difference — a durable row that can be
   contradicted in place would make every read a guess. Revisit: a caller
   legitimately wants to re-record a status (an execution that failed after a
   SUCCEEDED commit) — that becomes a transfer face of its own, not a
   silent update.
4. **``reason_codes`` is the caller's vocabulary.** §14 spells the column and
   the two outcome words; it pins no reason vocabulary, so this module mints
   none and the store writes what the caller declares (``()`` is the honest
   empty value). Revisit: canonical text (or BF-03) names reason words.
5. **The reverse reference stays plain data.** ``decision_cycle.
   planner_decision_id`` is written by this port's adapter and by nothing
   else, as an ``UPDATE`` only (never an INSERT or a DELETE); it carries no
   foreign key, because the pointer and the decision row are one transaction
   (migration 0015's header states the three reasons). Revisit: a second
   writer of that pointer appears, or a canonical revision asks the schema to
   refuse a dangling pointer.
6. **The read records carry what their types carry, and the stamps are the
   store's.** §14 lists ``created_at`` on all four blocks; the store stamps it
   on every row, and three of the four read records do not surface it:
   ``PlannerDecision`` and ``PlannerExecutionStatusRecord`` were minted in P7
   without a clock (P8-0 renames no field of theirs), and
   :class:`~elc.platform.types.RuntimeDecisionOutcome` keeps §14's four
   non-clock fields on purpose — the convention the sibling adapters follow
   ("created_at 由 store 盖，内存记录不带"). The one exception is
   :class:`~elc.platform.types.PlannerEvaluationRecord`, which P8-0 mints for
   §14's row and which carries the stamp (the ``DecisionCycleRecord``
   precedent). The stamps are all durable and are asserted at the row level.
   Revisit: a cut adds the stamp to the other three (a field-set change, not
   a rename) and the reads surface it.
7. **This cut is the Planner half of CP2.** RA §6's teaching half
   (``TeachingMoment`` / ``TeachingLockLease`` / ``active_teaching_lock`` /
   the first ``GenerationActionIntent``) belongs to the Gate's automatic face
   and is **not** written here — so RA §23's "Crash after CP2 … 不新建
   Moment" is served on the Planner side only, and this cut does not claim
   the whole clause. Revisit: p8-1 lands the Gate's automatic profile.
8. **No runtime handler calls this port yet.** The orchestrator that owns the
   CP2 unit (assembling the ``PlanningRequest``, running the kernel, handing
   the answer here) is a later cut's work item; until then the face is
   exercised by its own suite and by any caller that holds a cycle and an
   outcome. Revisit: the orchestrator lands and fixes this port's call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.planner.types import PlanningOutcome
from elc.platform.types import (
    DecisionCycleId,
    PlannerDecision,
    PlannerDecisionId,
    PlannerEvaluationId,
    PlannerEvaluationRecord,
    PlannerExecutionStatusRecord,
    Result,
    RuntimeDecisionOutcome,
    TurnId,
)

__all__ = [
    "PlannerCycleRecords",
    "PlannerRecordStore",
]


@dataclass(frozen=True)
class PlannerCycleRecords:
    """The four §14 records of one committed CP2 unit, as they are durable.

    ``decision`` is ``None`` exactly when the status is not ``SUCCEEDED``
    (RA §6: a degraded run persists no decision) — the same coupling
    :class:`~elc.planner.types.PlanningOutcome` enforces in memory, read back
    from the durable rows rather than restated by the caller.

    ``runtime_decision_outcome`` is ``None`` only if the turn has no durable
    outcome row — a state this port's own write face cannot produce (its unit
    always records one) but a read must not invent one for. A replay of a
    cycle that is no longer the turn's newest returns the turn's **current**
    row, whose ``decision_cycle_id`` names the newer cycle (judgement 2).
    """

    execution_status: PlannerExecutionStatusRecord
    evaluation: PlannerEvaluationRecord
    decision: PlannerDecision | None
    runtime_decision_outcome: RuntimeDecisionOutcome | None


@runtime_checkable
class PlannerRecordStore(Protocol):
    """The §14 durable face: one CP2 commit and the rows' reads.

    Implemented by ``elc.platform.db.planner_store.SqlitePlannerRecordStore``
    (keyword-only construction: connection + runtime epoch fence).

    :meth:`record_planner_cycle` is one short transaction over all four
    tables — the status row, the evaluation row, the decision row (SUCCEEDED
    only), the turn's outcome row, and the ``decision_cycle`` back-reference
    — so the unit is atomic in both directions: every row lands or none does.
    The five ``get_*`` reads answer ``Ok(None)`` for an unknown id (the
    ``SqliteDecisionCycleStore`` precedent: an absent row is a fact, not an
    error).
    """

    def record_planner_cycle(
        self,
        *,
        turn_id: TurnId,
        outcome: PlanningOutcome,
        reason_codes: tuple[str, ...] = (),
    ) -> Result[PlannerCycleRecords]:
        """Persist one cycle's §14 records in one short transaction.

        ``outcome`` is the kernel's own answer (``PlanningOutcome`` — the
        object a shadow run carries as ``ShadowRun.outcome``); the cycle is
        ``outcome.execution_status.decision_cycle_id`` and ``turn_id`` is the
        turn that cycle belongs to. ``reason_codes`` travels to
        ``runtime_decision_outcome.reason_codes`` (judgement 4).
        """
        ...

    def get_planner_execution_status(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[PlannerExecutionStatusRecord | None]:
        """The cycle's execution status row, or ``Ok(None)``."""
        ...

    def get_planner_evaluation(
        self, planner_evaluation_id: PlannerEvaluationId
    ) -> Result[PlannerEvaluationRecord | None]:
        """One §14 evaluation row (the id shape), or ``Ok(None)``."""
        ...

    def get_planner_decision(
        self, planner_decision_id: PlannerDecisionId
    ) -> Result[PlannerDecision | None]:
        """One §14 decision row by its own id, or ``Ok(None)``."""
        ...

    def get_planner_decision_for_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[PlannerDecision | None]:
        """The cycle's decision row (the write face records one per cycle),
        or ``Ok(None)`` for a cycle without one."""
        ...

    def get_runtime_decision_outcome(
        self, turn_id: TurnId
    ) -> Result[RuntimeDecisionOutcome | None]:
        """The turn's §14 outcome row, or ``Ok(None)``."""
        ...

    def get_planner_decision_id(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[str | None]:
        """The cycle's ``planner_decision_id`` back-reference, or ``Ok(None)``.

        ``None`` covers both "no such cycle" and "a cycle with no decision
        yet"; ``SqliteDecisionCycleStore.get_decision_cycle`` is the read that
        tells the two apart (the cycle row is that face's)."""
        ...
