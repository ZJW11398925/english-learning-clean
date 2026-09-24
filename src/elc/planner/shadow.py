"""Shadow mode — the Planner decides and nothing is dispatched (P7-4).

docs/IMPLEMENTATION_PLAN.md §8 (lines 377–397), quoted verbatim:

    ### Shadow mode

    先运行：

    ```text
    Planner decides
    but UI does not auto-teach
    ```

    记录：

    ```text
    what would have been selected
    why
    ```

    人工/测试审查。

This module is that block, executable. "先运行" is the first half: the Planner
runs for real — over a cycle's own views, through the same
:func:`elc.planner.kernel.plan` every other consumer calls — and
:class:`ShadowRun` carries what §8's review needs to read: what it *would have*
selected, why, at which execution status, and what the Runtime's turn-level
outcome would be. "but UI does not auto-teach" is the second half and it is a
**boundary rather than a switch**: this module imports no teaching face, calls
no Gate, writes no store and builds no ``TeachingMoment``, so there is no
object here that *could* dispatch. Nothing about the run is deferred or stubbed
— the decision is complete and the dispatch is absent.

**The chain.** A :class:`~elc.planner.types.PlanningRequest`'s views are what
the run reads; P7-0's :func:`~elc.planner.feature_assembly.
assemble_feature_authority` turns them into the authority record BF-02 §5
names; the kernel runs §10.1's eleven steps over it; and the answer comes back
as a record instead of as a dispatched action. Every status word in that chain
is quoted rather than softened — docs/DOMAIN_MODEL.md line 559 and
docs/RUNTIME_ARCHITECTURE.md §4 step 9A (lines 99–103) say it in one sentence
each:

    `Planner failure/unavailable` 不伪装成 `PlannerDecision`；它由 Runtime 的
    `PlannerExecutionStatus` 表达。

    9A PlannerExecutionStatus = DEGRADED/FAILED/UNAVAILABLE
       → RuntimeDecisionOutcome = DEGRADED_NO_AUTOMATIC_TEACHING
       → no synthetic PlannerDecision
       → Normal Persona generation

So a shadow run that degrades answers a *status* and no decision, and
:attr:`ShadowRun.runtime_decision_outcome` is that status's implication
(``runtime_decision_outcome_of``) rather than an action anyone took. A
successful run answers ``NORMAL`` for the same reason: the value describes what
the Runtime *would* have done, and this cut dispatches neither.

**What a reviewer can hold the run to.** The four headline fields are the
kernel's own answers, not a second opinion: :attr:`ShadowRun.would_have_selected`
is the selected candidate of the run's own decision,
:attr:`ShadowRun.why` is the run's ``reason_trace``,
:attr:`ShadowRun.execution_status` is the run's status and
:attr:`ShadowRun.runtime_decision_outcome` is what that status implies. The
whole :class:`~elc.planner.kernel.PlannerTrace` and the canonical
:class:`~elc.planner.types.PlanningOutcome` are carried beside them, so §8's
"why" can be read down to a single candidate's partial sums without re-running
anything.

**Declared judgements.** Each entry is this cut's reading rather than a
quotation, and each names the condition that re-opens it:

1. **the supply seam is a keyword, not a request field.** §10's
   ``PlanningRequest`` carries *views* (eleven of them) and no proposals;
   P7-2's :class:`~elc.planner.candidates.CandidateSupply` is the record that
   pairs proposals with the §8.1 levels of exactly the targets that became
   candidates and with the §12 scope resolution it made. ``supply`` is
   therefore a keyword argument, and the request's own
   ``curriculum_candidate_view`` is deliberately **not** read as a supply: its
   landed record (:class:`elc.curriculum.types.CurriculumCandidateView`) is a
   curriculum-side node view — an *input* to the generators — and reading one
   record two ways would make two shapes mean one thing. Three further request
   fields are named here and **not read** either, as one group so that "the
   view travels in the request" cannot be mistaken for "the run read it":
   ``context_opportunity_set`` (no producer in this repository builds one),
   ``session_budget_view`` (this run derives no control fact from it — the
   runtime unit does that, and the view itself landed in P8-2) and
   ``planning_ledger`` (a run derives the three ledger readings from the
   supply side it is given; the request's field is not a second input. P8-3
   gave the ledger durable tables — migration 0016 behind
   ``elc.planner.ledger_store`` — and *this* run still reads none of them:
   building a view out of the store is the caller's act, and no shipped face
   does it yet). The fourth,
   ``conversation_priority_view``, is read for **exactly one field** —
   ``natural_break_available``, BF-02 §5's context field, which canonical
   text now names a source for (judgement 2) — and for nothing else: §13's
   ``flow_priority`` / ``interaction_phase`` stay the Gate's, and this
   module's whole boundary is that nothing here calls one. Revisit: the §10
   context assembly (the orchestrator's side of the chain) lands and fixes
   where the proposals travel, or one of the named fields becomes an input of
   this run — a V1 ledger table, a producer for the opportunity set, or
   ``request.session_budget_view`` reaching the run's authority assembly;
2. **one fact the request does not carry is declared, and one is now read
   from its canonical home.** The current Learning watermark
   (:func:`elc.learning.queries.get_learning_watermark` is the face that
   answers it) arrives as a keyword argument, and a caller who hands none
   gets the **fail-closed** reading: ``current_learning_watermark=None``
   cannot show a snapshot current, so P7-0's leg answers
   ``snapshot_status=INVALID`` and the run degrades.
   ``natural_break_available`` is **no longer a keyword argument**: canonical
   text names its home — docs/DOMAIN_MODEL.md §13's
   :class:`~elc.planner.scope.ConversationPriorityView`, whose field carries
   exactly BF-02 §5's name — so the value is derived from
   ``request.conversation_priority_view`` by
   :func:`_natural_break_available_of`, and a request with **no** §13 view
   gets ``False`` (fail-closed: "no view" cannot show a natural break, the
   reading P7-0's default declares — "a value, not a missing authority").
   Revisit: the §13 view gains a producer that answers it from the
   conversation's own state (RA §4 step 3's conversation leg), at which
   point the request's view is the field's *reading* rather than also its
   declaration;
3. **the readiness leg reads ``candidate_readiness``, not the full mapping.**
   P7-2 states the two readings and what each one means ("the full ``readiness``
   mapping ... makes the assembly INCOMPLETE whenever any read target is
   ungraded. That is not a bug: it is the coarse reading"). The §10 leg names
   *candidates*, so the shadow run hands in the subset the leg names. Revisit: a
   cut decides that the Planner must vouch for the whole world it looked at;
4. **the scope word comes from the request.** ``user_intent_scope`` is a
   ``PlanningRequest`` field, so it is the word the run uses; a supply's own
   ``ScopeResolution`` is the generator's answer to the same question and this
   cut does not compare them. Revisit: a cut makes the resolution the cycle's
   authority, or requires the two to agree before a run;
5. **the constraint leg reads the request's view, not a second face.**
   ``constraint_view_present`` is ``request.planner_constraint_view is not
   None``; a caller who hands a supply whose scope says otherwise gets the
   fail-closed reading (an absent view makes the assembly INCOMPLETE). Revisit:
   P7-2's ``ScopeResolution.constraint_view_present`` is made the authority for
   this leg, or an orchestrator lands that guarantees the two agree;
6. **no envelope.** :func:`run_shadow` answers with the record itself rather
   than ``Result[...]``: its two failure modes are a caller contract breach
   (:class:`~elc.planner.kernel.PlannerInputError`, raised exactly as the kernel
   raises it) and an unusable context (a DEGRADED *value*, which §10.1 requires
   to be answered rather than thrown), so a Result envelope would have no error
   arm to carry. Revisit: the cut that wires the dispatch entry
   (:meth:`elc.planner.controller.PlannerService.plan`) decides one envelope for
   both;
7. **``UNAVAILABLE`` is unreachable here.** P7-0's assembly is total — it always
   answers a record — so a run whose caller hands nothing is ``DEGRADED`` /
   ``FEATURE_ASSEMBLY_INCOMPLETE`` rather than ``UNAVAILABLE``; that word stays
   the kernel's for a caller who holds *no context at all*. Revisit: an
   orchestrator lands that can fail to assemble one and hands the kernel
   ``None``.

**Versioning.** :data:`SHADOW_MODE_MODEL_VERSION` stamps this module's own
readings (the seam in judgement 1 above all); it moves with them, and a
calibration of BF-02's numbers moves
:data:`~elc.planner.kernel.PLANNER_PROFILE_VERSION` instead. P8-2 moved one of
the stamped readings (``natural_break_available`` left this module's
declaration for §13's view — judgements 1 and 2) and the stamp moved with it:
``sh2`` is the value, because the constant's own rule is that it moves with
the readings it stamps. The two facts a reader needs — what changed and why
the stamp moved — are stated beside the constant rather than left to a diff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from elc.planner.feature_assembly import (
    GoalPortfolioPort,
    LearningSnapshotPort,
    ScheduleViewPort,
    TeachingPolicyPort,
    assemble_feature_authority,
)
from elc.planner.kernel import (
    KernelResult,
    PlannerTrace,
    PlanningInput,
    plan,
    runtime_decision_outcome_of,
)
from elc.planner.scope import (
    ConversationPriorityView,
    natural_break_available_of,
)
from elc.planner.types import PlanningOutcome, PlanningRequest
from elc.platform.types import (
    DecisionCycleId,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerExecutionStatusValue,
    RuntimeDecisionOutcomeValue,
)

if TYPE_CHECKING:
    from elc.planner.candidates import CandidateSupply

__all__ = [
    "SHADOW_MODE_MODEL_VERSION",
    "ShadowRun",
    "run_shadow",
]

#: Stamps this module's own readings (module docstring, "Declared judgements"):
#: the supply seam, the declared fact and the readiness scope. **P8-2 moved one
#: of those readings** — ``natural_break_available`` is no longer this module's
#: declaration but §13's view's (judgement 1's fourth field, judgement 2) — and
#: **the stamp moved with it to ``sh2``**: this constant's own rule is that it
#: moves with the readings it stamps, so the reading and the number do not
#: silently differ. tests/phase7's value pin was moved in the same cut, and the
#: comment beside that pin says why. **P8-4 did not move it again**: that cut
#: relocated the *reading* of §13's field to ``elc.planner.scope``
#: (:func:`~elc.planner.scope.natural_break_available_of`) so the shadow run and
#: the automatic turn share one answer, but it changed no semantics — what this
#: run reads, and what the value means, are exactly what ``sh2`` stamped.
SHADOW_MODE_MODEL_VERSION = "sh2"


class _ConversationPriorityPort(Protocol):
    """docs/DOMAIN_MODEL.md §13's view, narrowed to the one field this module
    reads.

    A local protocol rather than reading the view's type directly, and for a
    mechanical reason worth writing down: this module's *behaviour* is what the
    boundary is about — nothing here calls the view's ``flow_priority`` /
    ``interaction_phase``, which stay the Gate's — and "the one field any code
    here can read" is what the protocol names (the ``FreshnessPort`` rule:
    fields the module may not consume are not declared). ``PlanningRequest``
    types the field as ``object | None``, so :func:`_natural_break_available_of`
    casts to this port and reads exactly ``natural_break_available`` before
    handing it to the shared reader.

    (P8-4 note: this protocol is no longer what keeps ``elc.planner.scope`` out
    of the module's import set — the shared reading of §13's field is imported
    from there now, and the import-set pin gained that one name in the same
    cut. The protocol stays because the *read* it narrows did not move: this
    module still reads one field and delegates the answer.)
    """

    natural_break_available: bool


@dataclass(frozen=True)
class ShadowRun:
    """One shadow-mode run: what the Planner would have done, and why.

    The four §8 fields — ``would_have_selected`` (a candidate id, or ``None``
    when the run selected nothing), ``why`` (the run's own reason trace),
    ``execution_status`` and ``runtime_decision_outcome`` — are read off the
    kernel's answer rather than computed here, and the two canonical records
    (:class:`~elc.planner.types.PlanningOutcome` and
    :class:`~elc.planner.kernel.PlannerTrace`) are carried beside them so a
    reviewer can go past the headline to the per-candidate numbers.

    ``canonical_count`` is the number of canonical candidates the run actually
    planned over (BF-02 §4's merge already applied) and ``proposal_count`` what
    the supply offered; a degraded run's ``why`` does not carry either count,
    and "the run saw nothing" and "the run saw four candidates and refused all
    of them" are different facts about a cycle.
    """

    decision_cycle_id: DecisionCycleId
    would_have_selected: str | None
    why: tuple[str, ...]
    execution_status: PlannerExecutionStatusValue
    runtime_decision_outcome: RuntimeDecisionOutcomeValue
    decision: PlannerDecisionOutcome | None
    no_target_reason: str | None
    frontier_candidate_ids: tuple[str, ...]
    planner_evaluation_id: PlannerEvaluationId
    proposal_count: int
    canonical_count: int
    outcome: PlanningOutcome
    trace: PlannerTrace


def _natural_break_available_of(request: PlanningRequest) -> bool:
    """BF-02 §5's ``natural_break_available``, from its canonical home.

    docs/DOMAIN_MODEL.md §13's :class:`~elc.planner.scope.
    ConversationPriorityView` carries the field under BF-02 §5's own name, so
    the view the request already holds *is* the authority — this module no
    longer takes a hand-passed boolean (judgement 2). "§13's view expresses
    the protection level and authorizes nothing": reading this one field
    delegates no authorization, and the Gate keeps that (§12's ``PROTECTED``
    leg is the Gate's own read of ``flow_priority``, not this one).

    The reading itself is :func:`elc.planner.scope.natural_break_available_of`
    — one function, so the shadow run and P8-4's automatic turn (which builds
    the same view for every ordinary turn) cannot drift; this helper is only
    the request→view adapter, and it reads exactly one field of the view.

    A request with **no** view answers ``False`` — the fail-closed reading:
    a natural break one cannot see is not one the run may claim (P7-0's own
    default, and "a value, not a missing authority"); the shared reader owns
    that sentence. Revisit: the §13 view's producer moves, or a caller appears
    that must read this without a request.
    """

    view = cast(
        "_ConversationPriorityPort | None", request.conversation_priority_view
    )
    return natural_break_available_of(
        cast("ConversationPriorityView | None", view)
    )


def run_shadow(
    request: PlanningRequest,
    *,
    supply: CandidateSupply | None = None,
    current_learning_watermark: int | None = None,
) -> ShadowRun:
    """Run the Planner over one cycle's views and record the answer (§8).

    The chain is the module docstring's, in order: the request's views (plus
    the declared fact and the supply, judgements 1–5) → P7-0's
    :func:`~elc.planner.feature_assembly.assemble_feature_authority` → the
    kernel's eleven steps → this record. Nothing else runs: no teaching, no
    Gate, no store, no clock.

    ``natural_break_available`` is **not** a parameter any more (P8-2,
    judgement 2): it is read from ``request.conversation_priority_view`` by
    :func:`_natural_break_available_of`, the canonical home §13 names for it.

    ``PlannerInputError`` propagates exactly as the kernel raises it — a
    violated input contract is the caller's data, so a run that never started
    reports the breach rather than a status (module docstring, judgement 6).
    """

    authority = assemble_feature_authority(
        learning_snapshot=cast(
            "LearningSnapshotPort | None", request.learning_snapshot
        ),
        current_learning_watermark=current_learning_watermark,
        schedule_view=cast("ScheduleViewPort | None", request.schedule_view),
        teaching_policy=cast(
            "TeachingPolicyPort | None", request.teaching_policy_view
        ),
        goal_portfolio=cast("GoalPortfolioPort | None", request.goal_view),
        curriculum_readiness=(
            None if supply is None else supply.candidate_readiness
        ),
        constraint_view_present=request.planner_constraint_view is not None,
        natural_break_available=_natural_break_available_of(request),
    )
    proposals = () if supply is None else tuple(supply.proposals)
    result: KernelResult = plan(
        PlanningInput(
            decision_cycle_id=request.decision_cycle_id,
            planning_context=authority,
            user_intent_scope=request.user_intent_scope,
            proposals=proposals,
        )
    )
    decision = result.outcome.decision
    return ShadowRun(
        decision_cycle_id=request.decision_cycle_id,
        would_have_selected=(
            None
            if decision is None or decision.selected_candidate_id is None
            else str(decision.selected_candidate_id)
        ),
        why=result.outcome.evaluation.reason_trace,
        execution_status=result.outcome.execution_status.status,
        runtime_decision_outcome=runtime_decision_outcome_of(
            result.outcome.execution_status.status
        ),
        decision=None if decision is None else decision.decision,
        no_target_reason=None if decision is None else decision.no_target_reason,
        frontier_candidate_ids=(
            result.outcome.evaluation.frontier_candidate_ids
        ),
        planner_evaluation_id=result.outcome.evaluation.planner_evaluation_id,
        proposal_count=len(proposals),
        canonical_count=len(result.trace.candidates),
        outcome=result.outcome,
        trace=result.trace,
    )
