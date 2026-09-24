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
``factor_trace``             the versioned document built from
                             ``PlannerTrace.candidates`` (the kernel's
                             per-candidate trace) with the evaluation's
                             ``reason_trace`` under its ``reasons`` key —
                             ``elc.planner.trace_document`` is the one
                             encoder/decoder
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

``factor_trace`` is this map's one physical reading, and P9-0 **moved it**:
§14 spells the column without brackets while the value is a sequence of lines
(P8-0's reading), and this cut reads it as the structured document instead —
see judgement 9, which is also where the legacy encoding and its discriminant
are registered.


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
4. **``reason_codes`` is the caller's vocabulary — and a replay leaves the
   durable row's reasons where they are.** §14 spells the column and the two
   outcome words; it pins no reason vocabulary, so this module mints none and
   the store writes what the caller declares (``()`` is the honest empty
   value). The replay path is **asymmetric on purpose**, and the asymmetry is
   registered here rather than left as an accident: a re-entry's status word
   and its ``error_code`` are compared against the durable row and a
   difference is refused (judgement 3), while ``reason_codes`` is neither
   compared nor stored — the durable row keeps the reasons of the submission
   that committed it. The leniency is the crash-window contract's: a re-entry
   must be able to reach the durable records with whatever reasons it holds on
   hand (free text about why the turn went as it did, not part of the unit's
   identity), where a differing ``error_code`` names a *different execution
   outcome* and is therefore a contradiction. Revisit: a cut asks for the
   reasons to be compared (or carried over) too — a stricter replay contract —
   or canonical text (or BF-03) names reason words and the column joins
   identity.
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
9. **``factor_trace`` is a versioned structured document, and the legacy
   array is read as what it was.** §14 spells the column without brackets and
   pins no shape, so P8-0 read it as the same deterministic JSON array the
   bracketed columns carry — the run's prose ``reason_trace``, lines only.
   P9-0 moves the column: it now carries
   :class:`~elc.platform.types.FactorTraceDocument`, the versioned object
   ``elc.planner.trace_document`` encodes and decodes, whose ``candidates``
   array holds **every** field of the kernel's ``CandidateTrace`` (the
   readings, the gaps, the partial sums, the coverage-service adjustment, the
   utility, the activation verdict, the dominance/tie facts) and whose
   ``reasons`` key holds the prose the column used to *be*. The split is
   stated rather than implied: ``PlannerEvaluation.reason_trace`` is still
   the prose decision reason (its content and every reader of it are
   unchanged), and it is no longer the column's whole content. Two more keys
   carry the rest of the reading: ``version`` (the ``ft1`` word, also the
   discriminant below) and ``provenance`` (``KERNEL_TRACE`` when the writer
   held the kernel's trace, ``NOT_RECORDED`` when it did not — a leg that
   could not run records a degraded shape of its own). **A row written
   before this cut** carries the legacy bare array; the decoder answers it
   as the tuple of lines it always was, and the discriminant is exactly the
   ``version`` key's absence (no heuristic on the array's contents) — the
   same rule the legacy arm's reader needs, and the one the tests pin.
   ``_replay`` compares the decoded document (candidates, prose and
   provenance together), so the agreement check keeps its old arm and gains
   the new ones: a re-entry whose prose differs is still a ``CONFLICT``, and
   a re-entry whose candidate trace differs is one too. Revisit: canonical
   text gives the prose a column of its own (then the ``reasons`` key retires
   and this map gains a second row), a canonical revision pins the column's
   shape (``factor_trace[]``, or a form that is not this document), or a
   shipped deployment needs a legacy row re-encoded (then the migration that
   rewrites old rows is named, and this decoder's legacy arm retires with
   it). **The frozen header's sentence is now historical.** The 0015
   migration's header (``migrations/0015_planner_records.sql``) still says, in
   the present tense, that ``factor_trace`` "is written in that same array
   form" — that statement is superseded from this cut on (the column carries
   the versioned structured document above), it stays in the frozen migration
   as history, and the Revisit the header itself names ("a form that is not an
   array of lines") is the one this cut triggered. The map above, not the
   header, is the current spelling.
10. **The trace rides an optional port keyword, and its absence is a stated
   fact.** ``record_planner_cycle`` takes ``trace`` — the kernel's own
   :class:`~elc.planner.kernel.PlannerTrace`, the object a shadow run carries
   as ``ShadowRun.trace`` — as a keyword with the honest default ``None``: a
   caller that holds no trace (the leg-failure path, whose run never
   happened) records one all the same, and the difference is the
   ``provenance`` word inside the document rather than a second method or a
   required argument. The port's semantics do not move: one CP2 unit, the
   same replay rule, the same refusal vocabulary — the keyword only decides
   what the evaluation's document says about its candidates. Revisit: a
   caller appears that must be *refused* when it holds no trace (then ``None``
   becomes invalid for it and the refusal gets a code), or the trace becomes
   a field of ``PlanningOutcome`` (then the keyword retires into the record).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.planner.kernel import PlannerTrace
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
        trace: PlannerTrace | None = None,
    ) -> Result[PlannerCycleRecords]:
        """Persist one cycle's §14 records in one short transaction.

        ``outcome`` is the kernel's own answer (``PlanningOutcome`` — the
        object a shadow run carries as ``ShadowRun.outcome``); the cycle is
        ``outcome.execution_status.decision_cycle_id`` and ``turn_id`` is the
        turn that cycle belongs to. ``reason_codes`` travels to
        ``runtime_decision_outcome.reason_codes`` (judgement 4).

        ``trace`` is the same run's :class:`~elc.planner.kernel.PlannerTrace`
        (``ShadowRun.trace``), and it is what makes the durable
        ``factor_trace`` a *trace*: the column carries the versioned document
        ``elc.planner.trace_document`` builds from ``trace.candidates`` plus
        ``outcome.evaluation.reason_trace``. A caller that holds no trace
        (the leg-failure path, whose run never happened) passes none, and the
        document then says so in its ``provenance`` word rather than claiming
        an empty run (judgement 10).
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
