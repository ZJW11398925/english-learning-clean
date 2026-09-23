"""Planner decision kernel (P7-1, TASK-OPI-fc9d8ca7-7c6c-4c91-b1e6-9d75c6a6ce6b.4)
— docs/DOMAIN_MODEL.md §10.1, executable.

docs/DOMAIN_MODEL.md §10.1 (lines 603–627) fixes one order and two
vocabularies. Quoted verbatim, in three parts.

**The order** (the fenced block, lines 607–619):

    CandidateProposal canonicalize
    → authoritative feature assembly
    → planning-context validity
    → hard eligibility
    → policy utility
    → coverage-starvation safeguard
    → per-candidate activation
    → explicit-request priority
    → Pareto prune
    → near-tie deterministic tie-break
    → SELECT / NO_TARGET

**The factor names** (line 621 / line 623):

    Benefit factors 包括：learning_need / uncertainty_reduction /
    curriculum_value / goal_relevance / schedule_urgency / context_fit /
    personal_relevance / transfer_value / coverage_debt /
    opportunity_expiry / communicative_impact
    Cost factors：interruption_cost / cognitive_load / overexposure /
    support_cost / user_resistance

**The three hard rules** (line 625 / line 627), read as three sentences:

    硬规则一：Hard exclusion 不是 penalty；缺失 authoritative view 或
    invalid snapshot 进入 PlannerExecutionStatus=DEGRADED/FAILED/UNAVAILABLE，
    不得伪造 NO_TARGET。
    硬规则二：显式 user learning request 通过 scope/readiness/prerequisite 后
    不使用 automatic interruption threshold；多重显式请求用 request_priority
    约束。
    硬规则三：Origin labels 不能重复加 utility。

What this module is: that order, as eleven executable steps, over BF-02's
frozen input contract — a canonical candidate set carrying complete normalized
factor vectors, a UserIntentScope, a PlanningContext and a TeachingPolicyProfile
(BF-02 §20 lines 603–627: given those six things, independent implementations
must agree on eligibility exclusions, the degraded state, the utility trace,
the activation set, the request-priority class, the Pareto-pruned set, the tie
set and SELECT / NO_TARGET). Nothing here reads a store, a clock or a random
source, and nothing writes anything: :func:`plan` is a pure function of its
:class:`PlanningInput`.

What this module is **not**, and each absence is a later cut's work item
rather than an oversight:

- **no candidate generation** (Track A / Track B, the prerequisite resolver,
  the readiness supply, the ConversationPriorityView) — IMPLEMENTATION_PLAN §8
  gives those to the candidate-generator cut, which is what feeds
  :class:`CandidateProposal`;
- **no PlanningLedger / CoverageDebt / overexposure accumulator** — the factor
  *names* ``coverage_debt`` and ``overexposure`` are scored here, but their
  numbers come from upstream;
- **no shadow mode, no persistence, no UI** — IMPLEMENTATION_PLAN §8's shadow
  mode (run the Planner, auto-teach nothing, review what it would have
  selected) is the cut that owns it, and this kernel claims nothing about it;
- **no Gate state** — BF-02 §17 (lines 525–558): the Planner may SELECT even
  when a later Gate hard state will DENY, and reading Gate state here would
  rebuild a second pedagogy ranking. ``interruption_cost = PROTECTED`` is a
  cost, never an exclusion.

**Consuming P7-0 instead of working around it.** The PlanningContext arrives
as P7-0's :class:`~elc.planner.feature_assembly.FeatureAuthority` record —
``feature_assembly_status`` / ``snapshot_status`` / ``missing_authorities[]`` /
``natural_break_available`` are BF-02 §5's own four names, and that record is
what decides step 3. The kernel never re-derives those statuses, never
overrides them, and never turns an unreadable authority into a number:

- ``schedule_urgency`` is **assembled** from the candidate's §5.2 row through
  :func:`elc.planner.feature_assembly.schedule_urgency_of` — the factor is the
  Scheduler's answer, so a declared number is accepted only when a row spells
  the same one, and refused (a gap, then DEGRADED) when the authority is not
  ``CURRENT`` or the Scheduler was never asked about the target (P7-0: "a
  target with no row is a target the Scheduler was never asked about, and its
  factor is unknown rather than zero");
- ``goal_relevance`` is read through
  :func:`elc.planner.feature_assembly.goal_relevance_of`, and a declared
  number is refused while the record names ``GOAL_ASSESSMENT_PACK_MAPPING``
  missing. That leg answers UNKNOWN in this repository (the mapping
  IMPLEMENTATION_PLAN §7 line 340 lists is not built), so today the declared
  reading stands as :attr:`FactorSource.DECLARED` — the input BF-02 §20 names
  — and the revisit below closes the gap when the mapping lands;
- every other factor is the candidate's own reading (:attr:`FactorSource.
  DECLARED`), which is what makes the trace able to answer "which numbers did
  an authority answer, and which did a generator supply?".

**Declared judgements.** Each of the following is this cut's reading rather
than a quotation, and each carries the condition that re-opens it. Entries 8
to 14 register rather than decide: 8–10 spell the canonicalization contract's
reachable shapes, three of which BF-02's frozen 43-case suite answers
differently; 11 narrows §20's input contract by asking a §5.2 row to spell a
declared ``schedule_urgency``; 12–14 name known gaps and inherited drifts a
later cut owns. A registration changes no behaviour:

1. **the step names.** :class:`KernelStep`'s values are §10.1's eleven lines
   with the ``→`` list marker removed and nothing else changed, so a
   reordering of the canonical block fails a test instead of shipping
   silently. Revisit: §10.1's block is edited — a step added, renamed,
   reordered or dropped — or a second canonical document states the order;
2. **the candidate-level gap is DEGRADED.** BF-02 §5 states the degradation
   rule for the *context*; this cut closes it for the *candidate*: a factor
   whose authority cannot answer is a gap, and a gap is
   ``DEGRADED``/``FACTOR_AUTHORITY_UNKNOWN`` — never a ``0`` and never a
   ``NO_TARGET``. Revisit: canonical text says what a candidate-level gap is
   (today only the context-level case is spelled out), or a landed authority
   makes one of the two legs total;
3. **merging may not move utility.** BF-02 §4 (lines 92–124) merges duplicate
   generator proposals by unioning origins and taking the most immediate lane,
   and says the factor vector is *not* merged ("最终 factor vector 不在 merge
   时相加或取 max" / "origin count != utility bonus"). Two proposals sharing a
   canonical_key that declare different factor vectors are therefore an input
   contract error: merging them would be the addition §4 forbids, and picking
   one silently would make the decision depend on proposal arrival order.
   Revisit: §4 says what to do with two vectors under one key, or the generator
   contract changes so a key cannot arrive twice;
4. **the stable id of a merged candidate.** §16 item 8 says "stable
   candidate_id"; a merge leaves several, so the spelling is the
   lexicographically smallest of them — the deterministic choice. Revisit: §16
   names a different spelling for the surviving id, or canonical text says
   which arrival's id is the stable one;
5. **the readiness floor precedence.** §10's four rows are not stated to be
   ordered; they are read as PROBE before user-initiated before
   ``CURRENT_USER_ERROR`` before general, so a probe of an explicitly
   requested target is a probe (R2+). Revisit: canonical text orders them;
6. **the identity spellings.** :class:`GoalRelation` is §24.14's verbatim
   vocabulary; :class:`CoverageServiceState` and :class:`PrerequisiteState`
   are BF-02's (no canonical document lists either), and
   :class:`ReadinessLevel` is ``elc.curriculum.readiness.READINESS_LEVELS``
   itself rather than a second spelling of the same five levels. Revisit: a
   canonical document lists the coverage-service or prerequisite vocabulary
   (§24.14 names those columns and not their words), or the readiness ladder is
   re-spelled;
7. **the ids this cut mints.** ``pe-<decision_cycle_id>`` /
   ``pd-<decision_cycle_id>``: content-addressed, so two runs of one cycle
   agree and no clock is read. Revisit: a durable store assigns the ids;
8. **a duplicate identity inside one ``canonical_key`` merges rather than
   raises.** §4's last line makes a duplicate ``canonical_key`` an input
   contract error, and §4's merge is a merge of *proposals*: two arrivals that
   describe one candidate — the same five identity fields and one factor
   vector — become one canonical candidate, duplicate ``candidate_id`` values
   included (the trace then shows the repeated id in ``merged_from``). What
   raises is the shape the merge cannot resolve: two arrivals of one key that
   disagree. BF-02's frozen suite spells the two merge shapes as
   ``error: true`` (S04's ``d1``/``d2`` and S42's ``x`` twice), so this is a
   **registered divergence**, and the shadow-mode cut that reproduces the 43
   cases has to model it explicitly instead of tuning it away. Revisit: §4 says
   which of the two shapes raises, or the reproduction lands and one of the two
   readings is retired;
9. **step 2's contract validation precedes step 3's context verdict.** A
   malformed vector raises even when the context is INCOMPLETE and the run
   would have degraded anyway, because §20's completeness is a contract over
   the *input* and the proposals are walked before the context is adjudicated.
   BF-02's suite reads the same input as ``DEGRADED`` (S20's own ``expected``),
   so this is a **registered divergence** too. Revisit: the reproduction lands
   and the order is settled explicitly (a context verdict read before step 2's
   validation is the other reachable reading);
10. **which input shapes raise at all.** The canonicalization step's list is
    closed and short: a proposal with no ``canonical_key``, one key whose
    proposals disagree about an identity field, one key carrying two factor
    vectors, and two keys whose canonical candidates would share a
    ``candidate_id`` (the cross-key collision §16's eighth criterion would
    otherwise settle arbitrarily). Nothing else *about a proposal* raises here:
    a lane, a scope word, a readiness, a suppression and a severity are read as
    facts and answered with an exclusion or a number, while §9's contradictory
    scope and §11/§20's other contract checks are quoted from those sections
    rather than read here. Revisit: canonical text enumerates the input
    contract errors (§4's is one sentence), or a generator reaches the kernel
    with a shape this list has no answer for;
11. **a declared ``schedule_urgency`` must be spelled by a §5.2 row.** P7-0's
    :func:`~elc.planner.feature_assembly.schedule_urgency_of` owns the number,
    so a declared reading is accepted only when the candidate's row answers the
    same one, a disagreeing pair is an input contract error, and a leg that
    answers nothing (no row, or a schedule authority that is not ``CURRENT``)
    is a gap. That is a **narrowing of BF-02 §20's frozen input contract**: the
    reference suite supplies complete vectors and no §5.2 rows at all, so it
    never exercises the check. Revisit: canonical text says whether the factor
    vector is an *input* to the assembly or its *output* (§20 lists it among
    the frozen inputs, while §5's missing-Scheduler rule reads it as the
    assembly's own product);
12. **the evaluation record's shape is not §14's column set — and most of it
    has since landed.** docs/DATA_MODEL.md §14 lists
    ``frontier_candidate_ids[]``, ``factor_trace`` and a ``created_at`` for the
    evaluation record; this kernel emits
    :class:`~elc.planner.types.PlannerEvaluation` as the type module carries it
    (``ranked_candidates`` as records rather than ids, ``reason_trace`` as
    lines, ``policy_version`` under that name, no clock). p7-3 appended
    ``frontier_candidate_ids`` — §14's first column — filled from step 4's
    survivors through :mod:`elc.planner.frontier`, so that one column is now
    read from the document. **Superseded in part (P8-0).** This entry's claim
    that §14's ``RuntimeDecisionOutcome`` had no record implementation
    anywhere in this repository, and the inherited-drift sentence beside it,
    are no longer true: P8-0 landed
    :class:`~elc.platform.types.RuntimeDecisionOutcome` and
    :class:`~elc.platform.types.PlannerEvaluationRecord` in
    ``src/elc/platform/types.py``, the four §14 tables in
    ``migrations/0015_planner_records.sql``, and the **one** column map
    between this box's computed record and the durable rows in
    :mod:`elc.planner.records`. So the durable shape is read from the
    document now; what stays here is this module's in-memory spelling of the
    evaluation (``reason_trace`` as lines, ``policy_version`` under that
    name, no clock read), which the durable face **maps** rather than
    documents. :func:`runtime_decision_outcome_of` still answers BF-02 §5's
    *value* and nothing more, and the durable record is where that value
    becomes a row. Revisit: canonical rewrites one of these columns or the
    ``RuntimeDecisionOutcome`` record's spelling and the mapping in
    :mod:`elc.planner.records` has to follow, or a cut gives the kernel's
    ``PlannerEvaluation`` §14's names directly (the record reshaped rather
    than mapped);
13. **a target the Scheduler never scheduled is a gap, not the reference
    band's ``0.0``.** BF-02 §6 gives ``NOT_SCHEDULED`` the legal band ``0.0``
    (:data:`~elc.planner.feature_assembly.SCHEDULE_URGENCY_BANDS`), but the
    three-bucket §10 view the assembly reads does not carry ``NOT_SCHEDULED``
    rows (P6-2 keeps them out of ``due_items`` / ``overdue_items`` /
    ``upcoming``), so a caller that resolves the row through that view finds
    none, and this kernel answers a gap where the band has a number. The gap is
    the honest reading — "asked and answered NOT_SCHEDULED" is not "never
    asked" — and it is registered as a **known gap**: the cut that next touches
    the Scheduler's views or P7-0's assembly has to make the two
    distinguishable (a fourth bucket, a direct §5.2 lookup, or an assembly that
    says which of the two it saw). Revisit: that cut lands (the trigger is by
    construction: ``elc/scheduler``'s views or ``elc/planner/
    feature_assembly``), or canonical text says a NOT_SCHEDULED target's factor
    is unknown rather than ``0.0``;
14. **five registered readings with no behaviour of their own.** (a) a context
    whose ``planner_profile`` is ``None`` degrades as
    ``FEATURE_ASSEMBLY_INCOMPLETE`` — P7-0 leaves the profile ``None`` exactly
    when it could not map the policy, so there is no BF-02 profile to price
    with. Revisit: P7-0's mapping table gains the word that was missing.
    (b) §13's condition is restated as ``coverage_service_bonus > 0.0`` rather
    than by naming profiles: a profile whose reference bonus is ``0`` cannot
    carry the safeguard whichever profile it is, and a profile that gains a
    bonus gains the safeguard with it. Revisit: §13 names the profiles instead
    of their numbers. (c) ``ranked_candidates``'s ordering (utility descending,
    then §16's key, then the stable id) is not among the numbered judgements:
    it is the ranking the decision used, and §20 fixes no order for the record.
    Revisit: §14 or §20 fixes the record's order. (d) a row's currency is a
    property of the §10 **view**
    (:func:`~elc.planner.feature_assembly.schedule_authority_of`), so a caller
    who hands this kernel a §5.2 row the view does not carry gets that row's
    number without a currency check of its own — the kernel does not re-read
    the Scheduler's store. Revisit: the caller hands rows that carry their own
    currency, or the assembly reports per-row currency. (e) the §4 merge
    compares factor vectors with a missing name read as ``0.0``
    (:func:`_vector_of`), which is the *comparison* and never a score: a
    proposal that omits a factor still fails §20's completeness check when it
    is assembled, so no number is silently invented. Revisit: the merge's
    comparison gets a contract of its own, or the completeness check moves
    before the merge.

**Versioning.** :data:`PLANNER_KERNEL_MODEL_VERSION` stamps this module's own
readings and :data:`PLANNER_PROFILE_VERSION` is the frozen reference profile's
identity — the value BF-02 §21 calls ``planner_profile_version``, which moves
with the numbers in :data:`BENEFIT_WEIGHTS` / :data:`COST_WEIGHTS` /
:data:`POLICY_PROFILES` (a parameter change is ``planner_profile_version++``
plus a full benchmark regression and a decision diff review, never an edit).
The numbers themselves are pinned at test time against
``behavioral_baselines/planner/planner_reference_profile_v1_1.json`` and
against BF-02 §12/§13's text, so one number has one source and a transcription
slip fails a test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Sequence

from elc.planner.feature_assembly import (
    AuthorityName,
    FeatureAssemblyStatus,
    FeatureAuthority,
    PlannerProfile,
    ScheduleAuthority,
    ScheduleRowPort,
    SnapshotStatus,
    goal_relevance_of,
    schedule_urgency_of,
)
from elc.planner.frontier import frontier_of
from elc.planner.types import (
    InitiativeClass,
    LearningIntent,
    PlannerEvaluation,
    PlanningOutcome,
    TargetCandidate,
    TargetMode,
    UserIntentScope,
)
from elc.platform.types import (
    DecisionCycleId,
    EvidenceModality,
    PlannerDecision,
    PlannerDecisionId,
    PlannerDecisionOutcome,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
    RuntimeDecisionOutcomeValue,
    TargetId,
)

__all__ = [
    "AUTHORITY_ASSEMBLED_FACTORS",
    "BENEFIT_FACTORS",
    "BENEFIT_WEIGHTS",
    "COST_FACTORS",
    "COST_WEIGHTS",
    "ELIGIBLE_AUTOMATIC_READINESS",
    "ELIGIBLE_CURRENT_USER_ERROR_READINESS",
    "ELIGIBLE_PROBE_READINESS",
    "ELIGIBLE_USER_INITIATED_READINESS",
    "INITIATIVE_TIE_RANK",
    "KERNEL_STEP_ORDER",
    "MODE_ALLOWED_INTENTS",
    "PLANNER_KERNEL_MODEL_VERSION",
    "PLANNER_PROFILE_VERSION",
    "POLICY_PROFILES",
    "READINESS_RANK",
    "SCAFFOLD_MIN_COGNITIVE_LOAD",
    "SCAFFOLD_MIN_SUPPORT_COST",
    "TIE_BREAK_ORDER",
    "TIE_EPSILON",
    "ActivationPath",
    "BenefitFactor",
    "CandidateProposal",
    "CandidateTrace",
    "CanonicalCandidate",
    "ContextTrace",
    "CostFactor",
    "CoverageServiceState",
    "DegradedReason",
    "ExclusionReason",
    "FactorAssembly",
    "FactorGap",
    "FactorReading",
    "FactorSource",
    "GoalRelation",
    "KernelResult",
    "KernelStep",
    "NoTargetReason",
    "PlannerInputError",
    "PlannerTrace",
    "PlanningInput",
    "PolicyProfileParameters",
    "PrerequisiteState",
    "ReadinessLevel",
    "TieBreakCriterion",
    "assemble_candidate_factors",
    "canonicalize_proposals",
    "plan",
    "runtime_decision_outcome_of",
]

#: Stamps this module's own readings (module docstring, "Versioning").
PLANNER_KERNEL_MODEL_VERSION = "pk1"

#: The frozen reference profile's identity — BF-02 §21's
#: ``planner_profile_version``: the parameter set that
#: ``behavioral_baselines/planner/planner_reference_profile_v1_1.json``
#: carries. Pinned at test time against that asset's ``profile_id``.
PLANNER_PROFILE_VERSION = "planner-v1.1-reference-2026-09-stress-tested"


# -- the factor vocabularies -------------------------------------------------


class BenefitFactor(StrEnum):
    """§10.1 line 621 / §11 / BF-02 §6 — eleven benefit factors, by name.

    The declaration order is §10.1's order. A reader should know that
    docs/DOMAIN_MODEL.md §11's own fenced list (lines 663–674) carries ten of
    them: ``communicative_impact`` is missing there and present in §10.1's
    line 621 and in BF-02 §6, whose note says v1.0's omission was restored.
    The eleven-name reading is the one implemented — §10.1 is the decision
    kernel's section, BF-02 §12's weight table has eleven rows, and a ten-name
    vector cannot consume it — and this cut's suite pins the discrepancy
    rather than papering over it.
    """

    LEARNING_NEED = "learning_need"
    UNCERTAINTY_REDUCTION = "uncertainty_reduction"
    CURRICULUM_VALUE = "curriculum_value"
    GOAL_RELEVANCE = "goal_relevance"
    SCHEDULE_URGENCY = "schedule_urgency"
    CONTEXT_FIT = "context_fit"
    PERSONAL_RELEVANCE = "personal_relevance"
    TRANSFER_VALUE = "transfer_value"
    COVERAGE_DEBT = "coverage_debt"
    OPPORTUNITY_EXPIRY = "opportunity_expiry"
    COMMUNICATIVE_IMPACT = "communicative_impact"


class CostFactor(StrEnum):
    """§10.1 line 623 / §11 / BF-02 §7 — five cost factors, by name."""

    INTERRUPTION_COST = "interruption_cost"
    COGNITIVE_LOAD = "cognitive_load"
    OVEREXPOSURE = "overexposure"
    SUPPORT_COST = "support_cost"
    USER_RESISTANCE = "user_resistance"


#: The benefit factors in §10.1's order — the fold order of every weighted sum.
BENEFIT_FACTORS: tuple[BenefitFactor, ...] = tuple(BenefitFactor)

#: The cost factors in §10.1's order.
COST_FACTORS: tuple[CostFactor, ...] = tuple(CostFactor)

#: The two factors P7-0 assembles
#: (:func:`…feature_assembly.schedule_urgency_of` /
#: :func:`…feature_assembly.goal_relevance_of`) — the two whose declared
#: reading is checked against an authority rather than trusted (module
#: docstring, "Consuming P7-0").
AUTHORITY_ASSEMBLED_FACTORS: tuple[BenefitFactor, ...] = (
    BenefitFactor.SCHEDULE_URGENCY,
    BenefitFactor.GOAL_RELEVANCE,
)


# -- BF-02 §12/§13's reference numbers ---------------------------------------
#
# Reference values, not frozen ones: BF-02 §21 (lines 631–662) says the 92/92
# regression validates none of them, and the profile JSON's own ``status`` is
# REFERENCE_DEFAULT_CALIBRATABLE. This cut's suite extracts every number below
# from that frozen asset and from BF-02 §12's fenced blocks and compares them
# here, so a transcription slip fails a test instead of shipping, and a
# calibration moves the number together with PLANNER_PROFILE_VERSION.

#: BF-02 §12 lines 357–368, "Reference Benefit weights", by name.
BENEFIT_WEIGHTS: Mapping[BenefitFactor, float] = {
    BenefitFactor.LEARNING_NEED: 0.17,
    BenefitFactor.UNCERTAINTY_REDUCTION: 0.10,
    BenefitFactor.CURRICULUM_VALUE: 0.08,
    BenefitFactor.GOAL_RELEVANCE: 0.09,
    BenefitFactor.SCHEDULE_URGENCY: 0.08,
    BenefitFactor.CONTEXT_FIT: 0.13,
    BenefitFactor.PERSONAL_RELEVANCE: 0.08,
    BenefitFactor.TRANSFER_VALUE: 0.05,
    BenefitFactor.COVERAGE_DEBT: 0.08,
    BenefitFactor.OPPORTUNITY_EXPIRY: 0.02,
    BenefitFactor.COMMUNICATIVE_IMPACT: 0.12,
}

#: BF-02 §12 lines 372–378, "Cost".
COST_WEIGHTS: Mapping[CostFactor, float] = {
    CostFactor.INTERRUPTION_COST: 0.40,
    CostFactor.COGNITIVE_LOAD: 0.20,
    CostFactor.OVEREXPOSURE: 0.20,
    CostFactor.SUPPORT_COST: 0.10,
    CostFactor.USER_RESISTANCE: 0.10,
}


@dataclass(frozen=True)
class PolicyProfileParameters:
    """One BF-02 profile: three multipliers and two thresholds.

    §12's formula (lines 380–391) is the shape; the numbers are the reference
    profile's. ``initiative_multiplier`` multiplies the benefit,
    ``cost_multiplier`` the cost, ``automatic_activation_threshold`` is §14's
    per-candidate gate, and ``coverage_service_bonus`` is §13's starvation
    safeguard — zero for LOUNGE, whose reference row is ``LOUNGE       +0``.
    """

    profile: PlannerProfile
    initiative_multiplier: Mapping[InitiativeClass, float]
    cost_multiplier: float
    automatic_activation_threshold: float
    coverage_service_bonus: float


#: BF-02 §13 lines 422–428 and the reference profile's ``policy_profiles``.
POLICY_PROFILES: Mapping[PlannerProfile, PolicyProfileParameters] = {
    PlannerProfile.LOUNGE: PolicyProfileParameters(
        profile=PlannerProfile.LOUNGE,
        initiative_multiplier={
            InitiativeClass.REACTIVE: 1.0,
            InitiativeClass.OPPORTUNISTIC: 0.9,
            InitiativeClass.PROACTIVE: 0.55,
        },
        cost_multiplier=1.0,
        automatic_activation_threshold=0.36,
        coverage_service_bonus=0.0,
    ),
    PlannerProfile.BALANCED: PolicyProfileParameters(
        profile=PlannerProfile.BALANCED,
        initiative_multiplier={
            InitiativeClass.REACTIVE: 1.0,
            InitiativeClass.OPPORTUNISTIC: 0.95,
            InitiativeClass.PROACTIVE: 0.8,
        },
        cost_multiplier=0.8,
        automatic_activation_threshold=0.195,
        coverage_service_bonus=0.08,
    ),
    PlannerProfile.STUDY_FIRST: PolicyProfileParameters(
        profile=PlannerProfile.STUDY_FIRST,
        initiative_multiplier={
            InitiativeClass.REACTIVE: 1.0,
            InitiativeClass.OPPORTUNISTIC: 0.98,
            InitiativeClass.PROACTIVE: 0.95,
        },
        cost_multiplier=0.55,
        automatic_activation_threshold=0.18,
        coverage_service_bonus=0.10,
    ),
}

#: BF-02 §15's near-tie window: a candidate is in the tie set when the best
#: utility minus its own is at most this (the reference profile's
#: ``tie_epsilon``).
TIE_EPSILON = 0.015

#: BF-02 §11 lines 337–344's reference floors for a scaffolded candidate:
#: "candidate 必须显式体现支架成本" / "scaffold 不能被当成'免费
#: prerequisite'".
SCAFFOLD_MIN_SUPPORT_COST = 0.25
SCAFFOLD_MIN_COGNITIVE_LOAD = 0.20

#: BF-02 §16 line 513's third criterion as the rank a larger value wins:
#: "REACTIVE > OPPORTUNISTIC > PROACTIVE" (the reference profile's
#: ``initiative_rank``).
INITIATIVE_TIE_RANK: Mapping[InitiativeClass, int] = {
    InitiativeClass.REACTIVE: 3,
    InitiativeClass.OPPORTUNISTIC: 2,
    InitiativeClass.PROACTIVE: 1,
}

#: BF-02 §10 lines 300–305's four readiness rows, as the level each path
#: needs: "PROBE → R2+ / user-initiated teaching → R3+ / automatic
#: general/review → R3+ / automatic CURRENT_USER_ERROR → R4".
ELIGIBLE_PROBE_READINESS = "R2_PLANNER_READY"
ELIGIBLE_USER_INITIATED_READINESS = "R3_TEACHING_READY"
ELIGIBLE_AUTOMATIC_READINESS = "R3_TEACHING_READY"
ELIGIBLE_CURRENT_USER_ERROR_READINESS = "R4_DETECTION_READY"


# -- the order, as a contract -------------------------------------------------


class KernelStep(StrEnum):
    """§10.1's eleven steps, in order, one value per canonical line.

    The values are §10.1's lines 608–618 with the ``→`` list marker dropped
    and nothing else changed, so a reader — and this cut's suite — can compare
    the implementation's executed order with the canonical block character for
    character. The order is the contract: a step may not be moved, and a run
    that stops early (a degraded context) records the prefix it actually
    walked.
    """

    CANONICALIZE = "CandidateProposal canonicalize"
    FEATURE_ASSEMBLY = "authoritative feature assembly"
    CONTEXT_VALIDITY = "planning-context validity"
    HARD_ELIGIBILITY = "hard eligibility"
    POLICY_UTILITY = "policy utility"
    COVERAGE_SAFEGUARD = "coverage-starvation safeguard"
    ACTIVATION = "per-candidate activation"
    REQUEST_PRIORITY = "explicit-request priority"
    PARETO_PRUNE = "Pareto prune"
    TIE_BREAK = "near-tie deterministic tie-break"
    DECIDE = "SELECT / NO_TARGET"


#: §10.1's order, executable.
KERNEL_STEP_ORDER: tuple[KernelStep, ...] = tuple(KernelStep)


class TieBreakCriterion(StrEnum):
    """BF-02 §16's eight criteria, in the order a near-tie is resolved.

    Line for line: "1 request_aligned / 2 user_initiated / 3 REACTIVE >
    OPPORTUNISTIC > PROACTIVE / 4 higher opportunity expiry / 5 lower
    interruption cost / 6 lower overexposure / 7 lower cognitive load /
    8 stable candidate_id". A near-tie is the only place these apply — §16's
    closing line: "Tie-break 仍然只是 near-tie 规则，不代替 utility".
    """

    REQUEST_ALIGNED = "request_aligned"
    USER_INITIATED = "user_initiated"
    INITIATIVE_CLASS = "REACTIVE > OPPORTUNISTIC > PROACTIVE"
    OPPORTUNITY_EXPIRY = "higher opportunity expiry"
    INTERRUPTION_COST = "lower interruption cost"
    OVEREXPOSURE = "lower overexposure"
    COGNITIVE_LOAD = "lower cognitive load"
    CANDIDATE_ID = "stable candidate_id"


#: §16's order, executable. The eighth criterion is applied to the remaining
#: finalists rather than folded into the sort key.
TIE_BREAK_ORDER: tuple[TieBreakCriterion, ...] = tuple(TieBreakCriterion)


# -- the candidate-side vocabularies -----------------------------------------


class GoalRelation(StrEnum):
    """docs/DATA_MODEL.md §24.14 "Planner Candidate Additions", verbatim:
    ``goal_relation = NONE | PREPARATORY | DIRECT_TARGET_LEVEL``."""

    NONE = "NONE"
    PREPARATORY = "PREPARATORY"
    DIRECT_TARGET_LEVEL = "DIRECT_TARGET_LEVEL"


class ReadinessLevel(StrEnum):
    """``elc.curriculum.readiness.READINESS_LEVELS``, reused rather than
    re-spelled: one ladder, one vocabulary, so a candidate's level and the
    supply's answer are the same words.

    BF-02 §10's floors name R2/R3/R4; the rank is the ladder's index (R0
    lowest), matching the reference profile's ``readiness_rank``.
    """

    R0_INDEXED = "R0_INDEXED"
    R1_LEXICALLY_RESOLVED = "R1_LEXICALLY_RESOLVED"
    R2_PLANNER_READY = "R2_PLANNER_READY"
    R3_TEACHING_READY = "R3_TEACHING_READY"
    R4_DETECTION_READY = "R4_DETECTION_READY"


#: The ladder's index — the reference profile's ``readiness_rank``.
READINESS_RANK: Mapping[ReadinessLevel, int] = {
    level: index for index, level in enumerate(ReadinessLevel)
}


class PrerequisiteState(StrEnum):
    """BF-02 §11's prerequisite contract (lines 325–348), four words.

    ``READY_WITH_SCAFFOLD`` and ``UNKNOWN`` + ``prerequisite_scaffoldable``
    are the two shapes that must carry a scaffold cost; ``BLOCKED`` is the
    hard prerequisite §13's coverage bonus may not break. No canonical
    document lists these four words — BF-02 does, and the frozen suite's
    input validation uses exactly this spelling. Revisit: canonical text
    names the prerequisite vocabulary.
    """

    READY = "READY"
    READY_WITH_SCAFFOLD = "READY_WITH_SCAFFOLD"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"


class CoverageServiceState(StrEnum):
    """BF-02 §13's coverage-service classes: CRITICAL is the state the
    starvation safeguard answers, and §15's dominance classes are read off
    this field.

    Revisit: canonical text lists the vocabulary (docs/DATA_MODEL.md §24.14
    names the column and not its words).
    """

    NONE = "NONE"
    WATCH = "WATCH"
    DUE = "DUE"
    CRITICAL = "CRITICAL"


class ActivationPath(StrEnum):
    """BF-02 §8/§14's two paths: an explicit request is activated by its path,
    an automatic candidate by its profile's threshold."""

    AUTOMATIC = "AUTOMATIC"
    USER_INITIATED = "USER_INITIATED"


class ExclusionReason(StrEnum):
    """Why a candidate left the set at step 4 — hard exclusion, never a
    penalty (module docstring, hard rule one). The spellings are the frozen
    suite's, so one exclusion has one name across BF-02 and this kernel."""

    EXPIRED = "EXPIRED"
    DEPRECATED = "DEPRECATED"
    SUPPRESSED = "SUPPRESSED"
    MODALITY_UNAVAILABLE = "MODALITY_UNAVAILABLE"
    HARD_PREREQUISITE_BLOCKED = "HARD_PREREQUISITE_BLOCKED"
    PREREQUISITE_UNKNOWN_UNRESOLVED = "PREREQUISITE_UNKNOWN_UNRESOLVED"
    JUST_CHAT = "JUST_CHAT"
    OUTSIDE_TARGETED_SCOPE = "OUTSIDE_TARGETED_SCOPE"
    NON_LEARNING_TASK_SCOPE = "NON_LEARNING_TASK_SCOPE"
    CONTENT_NOT_READY = "CONTENT_NOT_READY"


class NoTargetReason(StrEnum):
    """The two reasons a *successful* run decides nothing. A third word for
    "the context was unusable" would be the laundering BF-02 §5 forbids, so
    there is none."""

    NO_ELIGIBLE_CANDIDATE = "NO_ELIGIBLE_CANDIDATE"
    BELOW_ACTIVATION_THRESHOLD = "BELOW_ACTIVATION_THRESHOLD"


class DegradedReason(StrEnum):
    """Why a run carried no decision. The first two are BF-02 §5's own
    conditions (and the frozen suite's error codes); the third is this cut's
    candidate-level closure of the same rule; the fourth is an absent
    context."""

    FEATURE_ASSEMBLY_INCOMPLETE = "FEATURE_ASSEMBLY_INCOMPLETE"
    SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
    FACTOR_AUTHORITY_UNKNOWN = "FACTOR_AUTHORITY_UNKNOWN"
    PLANNING_CONTEXT_UNAVAILABLE = "PLANNING_CONTEXT_UNAVAILABLE"


class FactorSource(StrEnum):
    """Where a factor's number came from — the trace's answer to "is this
    traced to an authority face, or supplied upstream?"."""

    AUTHORITY = "AUTHORITY"
    DECLARED = "DECLARED"


class PlannerInputError(ValueError):
    """A violated input contract: the caller's data, not the world's.

    BF-02 §4 line 124 ("Kernel 接收到重复 canonical_key 属于 input contract
    error"), §4's conflicting-identity rule, §11's scaffold floors and §20's
    "complete normalized factor vectors" are contracts over the *input*, so
    breaking one raises instead of answering DEGRADED — a run that never
    started is not a planner execution status.
    """


#: §11's TargetMode × LearningIntent pairing (the frozen suite's table, and
#: the reason a PROBE that consolidates is an input contract error rather than
#: a low-scoring candidate). docs/DOMAIN_MODEL.md §11 lists both vocabularies
#: without pairing them; BF-02's suite pins the pairs. Revisit: canonical text
#: pairs them, or a mode gains an intent.
MODE_ALLOWED_INTENTS: Mapping[TargetMode, tuple[LearningIntent, ...]] = {
    TargetMode.RESOURCE_PRACTICE: (
        LearningIntent.ESTABLISH,
        LearningIntent.DEVELOP,
        LearningIntent.WITHDRAW_SUPPORT,
        LearningIntent.EXPAND_REPERTOIRE,
    ),
    TargetMode.CAPABILITY_PRACTICE: (
        LearningIntent.ESTABLISH,
        LearningIntent.DEVELOP,
        LearningIntent.WITHDRAW_SUPPORT,
        LearningIntent.EXPAND_REPERTOIRE,
    ),
    TargetMode.PROBE: (LearningIntent.PROBE,),
    TargetMode.REVIEW: (LearningIntent.CONSOLIDATE,),
    TargetMode.TRANSFER: (LearningIntent.TRANSFER,),
}


# -- the input contract ------------------------------------------------------


@dataclass(frozen=True)
class CandidateProposal:
    """One generator proposal — BF-02 §3's ``Generator CandidateProposal[]``.

    The fields are the canonical candidate model's (docs/DATA_MODEL.md §14
    ``RawTargetCandidate / TargetCandidate`` plus §24.14's additions:
    ``canonical_key`` / ``request_priority`` / ``goal_relation`` /
    ``coverage_service_state``), and §4's five identity fields are here by
    name: ``focus_target`` / ``target_mode`` / ``evidence_modality`` /
    ``learning_intent`` / ``opportunity_binding_class``.

    ``benefit`` / ``cost`` are the assembly's per-candidate output — BF-02
    §20's "complete normalized factor vectors": a missing name or a value
    outside ``[0, 1]`` is an input contract error, and a declared number for a
    factor a landed authority owns must agree with that authority.

    ``schedule_row`` is the §5.2 row the Scheduler holds for this candidate's
    target (docs/DATA_MODEL.md §14's ``schedule_item_id?``, resolved by the
    caller — this kernel does no I/O). It is what makes ``schedule_urgency``
    an authority answer instead of a declaration.
    """

    candidate_id: str
    canonical_key: str
    focus_target: str
    target_mode: TargetMode
    learning_intent: LearningIntent
    evidence_modality: EvidenceModality
    opportunity_binding_class: str
    initiative_class: InitiativeClass
    benefit: Mapping[BenefitFactor, float] = field(default_factory=dict)
    cost: Mapping[CostFactor, float] = field(default_factory=dict)
    origins: tuple[str, ...] = ()
    user_initiated: bool = False
    request_aligned: bool = False
    request_priority: int = 0
    content_readiness: ReadinessLevel = ReadinessLevel.R3_TEACHING_READY
    prerequisite_state: PrerequisiteState = PrerequisiteState.READY
    prerequisite_scaffoldable: bool = False
    coverage_service_state: CoverageServiceState = CoverageServiceState.NONE
    modality_available: bool = True
    expired: bool = False
    deprecated: bool = False
    suppressed: bool = False
    runtime_generated_ready: bool = False
    task_aligned: bool = False
    critical_repair: bool = False
    goal_relation: GoalRelation = GoalRelation.NONE
    schedule_row: ScheduleRowPort | None = None


@dataclass(frozen=True)
class PlanningInput:
    """BF-02 §5's PlanningContext **plus** §4's canonical candidate set.

    ``planning_context`` is P7-0's
    :class:`~elc.planner.feature_assembly.FeatureAuthority` — the record a
    context assembly produces by reading the real authority faces — or
    ``None`` when the caller could not assemble one at all (a run with no
    context is ``UNAVAILABLE``, not a ``NO_TARGET``).

    ``proposals`` are the raw generator proposals; step 1 canonicalizes them.
    """

    decision_cycle_id: DecisionCycleId
    planning_context: FeatureAuthority | None
    user_intent_scope: UserIntentScope
    proposals: tuple[CandidateProposal, ...]


@dataclass(frozen=True)
class CanonicalCandidate:
    """One canonical candidate — BF-02 §4's merge, already applied.

    ``candidate_ids`` is every proposal id that merged into it (sorted, so two
    arrival orders produce one record) and ``candidate_id`` is the stable id
    §16's eighth criterion uses (module docstring, judgement 4). The factor
    vector is carried through **unmerged**: two proposals that disagree about
    it are refused (judgement 3), which is §4's "origin count != utility
    bonus" as an executable rule.
    """

    candidate_id: str
    candidate_ids: tuple[str, ...]
    canonical_key: str
    focus_target: str
    target_mode: TargetMode
    learning_intent: LearningIntent
    evidence_modality: EvidenceModality
    opportunity_binding_class: str
    initiative_class: InitiativeClass
    benefit: Mapping[BenefitFactor, float]
    cost: Mapping[CostFactor, float]
    origins: tuple[str, ...]
    user_initiated: bool
    request_aligned: bool
    request_priority: int
    content_readiness: ReadinessLevel
    prerequisite_state: PrerequisiteState
    prerequisite_scaffoldable: bool
    coverage_service_state: CoverageServiceState
    modality_available: bool
    expired: bool
    deprecated: bool
    suppressed: bool
    runtime_generated_ready: bool
    task_aligned: bool
    critical_repair: bool
    goal_relation: GoalRelation
    schedule_row: ScheduleRowPort | None


# -- the assembly's output ---------------------------------------------------


@dataclass(frozen=True)
class FactorReading:
    """One factor's number, and where it came from.

    ``authority`` is set exactly when ``source`` is
    :attr:`FactorSource.AUTHORITY`, and names the P7-0 authority the number
    was read from — so a trace can answer "which authorities did this
    decision actually consume?" without a second lookup.
    """

    factor: BenefitFactor | CostFactor
    value: float
    source: FactorSource
    authority: AuthorityName | None = None


@dataclass(frozen=True)
class FactorGap:
    """A factor no authority could answer — the reason a run degrades.

    A gap is not a zero: BF-02 §5 forbids answering an unreadable authority
    with ``0``, so the candidate is not scored at all and the run carries no
    decision.
    """

    factor: BenefitFactor | CostFactor
    authority: AuthorityName
    reason: str


@dataclass(frozen=True)
class FactorAssembly:
    """One candidate's assembled factor vector — readings and gaps.

    An empty ``gaps`` means the vector is usable; a non-empty ``gaps`` means
    the candidate cannot be scored this cycle, and the run degrades
    (:attr:`DegradedReason.FACTOR_AUTHORITY_UNKNOWN`).
    """

    candidate_id: str
    benefit: tuple[FactorReading, ...]
    cost: tuple[FactorReading, ...]
    gaps: tuple[FactorGap, ...]

    def value_of(self, factor: BenefitFactor | CostFactor) -> float:
        """The assembled number for one factor (raises for a gap)."""

        for reading in (*self.benefit, *self.cost):
            if reading.factor is factor:
                return reading.value
        raise KeyError(f"factor {factor} was not assembled")

    def source_of(self, factor: BenefitFactor | CostFactor) -> FactorSource:
        """Where one factor's number came from (raises for a gap)."""

        for reading in (*self.benefit, *self.cost):
            if reading.factor is factor:
                return reading.source
        raise KeyError(f"factor {factor} was not assembled")


# -- the trace ---------------------------------------------------------------


@dataclass(frozen=True)
class CandidateTrace:
    """Everything a reviewer needs to ask "why this candidate, why not that".

    An **excluded** candidate carries its exclusion reason and no score at all
    (``benefit_score is None``): hard exclusion is not a penalty, and a
    utility would invite a reader to compare a candidate the Planner refused
    to consider. A scored candidate carries the readings it was scored from,
    the two partial sums, the coverage-service adjustment, the utility, the
    activation verdict and the dominance/tie facts.
    """

    candidate_id: str
    canonical_key: str
    merged_from: tuple[str, ...]
    initiative_class: InitiativeClass
    request_priority: int
    coverage_service_state: CoverageServiceState
    benefit: tuple[FactorReading, ...]
    cost: tuple[FactorReading, ...]
    gaps: tuple[FactorGap, ...]
    excluded: ExclusionReason | None
    benefit_score: float | None
    cost_score: float | None
    coverage_service_bonus: float | None
    utility: float | None
    activation_path: ActivationPath | None
    activation_threshold: float | None
    activated: bool | None
    dominated_by: tuple[str, ...]
    in_tie_set: bool
    selected: bool


@dataclass(frozen=True)
class ContextTrace:
    """The context half of the trace: P7-0's record, as step 3 read it.

    The four BF-02 §5 names are carried verbatim (including P7-0's
    ``reasons``), together with the profile the kernel used and the verdict
    step 3 reached. ``None`` fields mean the caller held no context at all.
    """

    feature_assembly_status: FeatureAssemblyStatus | None
    snapshot_status: SnapshotStatus | None
    schedule_authority: ScheduleAuthority | None
    missing_authorities: tuple[AuthorityName, ...]
    natural_break_available: bool
    planner_profile: PlannerProfile | None
    automatic_teaching_enabled: bool
    policy_mapping_version: str | None
    reasons: tuple[str, ...]
    execution_status: PlannerExecutionStatusValue
    error_code: str | None


@dataclass(frozen=True)
class PlannerTrace:
    """The audit record: what ran, what it saw, and what it would have done.

    ``steps`` is the order actually walked — a degraded run records the prefix
    it stopped at, so a reordered or skipped step shows up as a different
    tuple. ``candidates`` covers **every** canonical candidate in canonical
    order (excluded, unactivated, dominated and selected alike), which is what
    makes the decision replayable rather than merely reported.
    """

    decision_cycle_id: DecisionCycleId
    planner_version: PlannerVersion
    policy_version: PolicyVersion
    steps: tuple[KernelStep, ...]
    context: ContextTrace
    candidates: tuple[CandidateTrace, ...]
    decision: PlannerDecisionOutcome | None
    selected_candidate_id: str | None
    no_target_reason: NoTargetReason | None
    runtime_outcome: RuntimeDecisionOutcomeValue


@dataclass(frozen=True)
class KernelResult:
    """The kernel's answer: the canonical outcome record and its trace.

    ``outcome`` is the existing :class:`~elc.planner.types.PlanningOutcome`,
    so the coupling "SUCCEEDED carries a decision, a degraded status carries
    none" lives in exactly one place; ``trace`` is this cut's audit record. A
    degraded result still carries an evaluation record — with no ranked
    candidates — and the why is in its ``reason_trace``.
    """

    outcome: PlanningOutcome
    trace: PlannerTrace


# -- step 1: canonicalization ------------------------------------------------


def canonicalize_proposals(
    proposals: Sequence[CandidateProposal],
) -> tuple[CanonicalCandidate, ...]:
    """BF-02 §4's merge, one canonical candidate per ``canonical_key``.

    The merge is exactly §4's five lines — origins union, ``user_initiated``
    OR, ``request_aligned`` OR, ``request_priority`` = the minimum explicit
    priority, ``initiative`` = the most immediate lane — and the identity
    fields of one key may not disagree (a duplicate ``canonical_key`` whose
    proposals describe different candidates is an input contract error).

    The output is ordered by ``canonical_key``, so a decision cannot depend on
    the order the generators happened to emit proposals in. The factor vector
    is *not* merged: proposals of one key must declare the same vector
    (judgement 3).
    """

    by_key: dict[str, list[CandidateProposal]] = {}
    for proposal in proposals:
        if not proposal.canonical_key:
            raise PlannerInputError(
                f"proposal {proposal.candidate_id!r} has no canonical_key"
            )
        by_key.setdefault(proposal.canonical_key, []).append(proposal)
    canonical: list[CanonicalCandidate] = []
    for key in sorted(by_key):
        group = by_key[key]
        first = group[0]
        for other in group[1:]:
            for field_name in _IDENTITY_FIELDS:
                mine = getattr(first, field_name)
                theirs = getattr(other, field_name)
                if mine != theirs:
                    raise PlannerInputError(
                        f"{key}: conflicting proposal identity field"
                        f" {field_name} ({mine!r} vs {theirs!r})"
                    )
            if _vector_of(other) != _vector_of(first):
                raise PlannerInputError(
                    f"{key}: proposals disagree about the factor vector — §4"
                    " forbids merging a factor vector (origin count !="
                    " utility bonus), so one vector must be recomputed from"
                    " the authoritative views instead"
                )
        canonical.append(
            CanonicalCandidate(
                candidate_id=min(p.candidate_id for p in group),
                candidate_ids=tuple(sorted(p.candidate_id for p in group)),
                canonical_key=key,
                focus_target=first.focus_target,
                target_mode=first.target_mode,
                learning_intent=first.learning_intent,
                evidence_modality=first.evidence_modality,
                opportunity_binding_class=first.opportunity_binding_class,
                initiative_class=max(
                    (p.initiative_class for p in group),
                    key=lambda lane: INITIATIVE_TIE_RANK[lane],
                ),
                benefit=dict(first.benefit),
                cost=dict(first.cost),
                origins=tuple(sorted({o for p in group for o in p.origins})),
                user_initiated=any(p.user_initiated for p in group),
                request_aligned=any(p.request_aligned for p in group),
                request_priority=min(p.request_priority for p in group),
                content_readiness=first.content_readiness,
                prerequisite_state=first.prerequisite_state,
                prerequisite_scaffoldable=first.prerequisite_scaffoldable,
                coverage_service_state=first.coverage_service_state,
                modality_available=first.modality_available,
                expired=first.expired,
                deprecated=first.deprecated,
                suppressed=first.suppressed,
                runtime_generated_ready=first.runtime_generated_ready,
                task_aligned=first.task_aligned,
                critical_repair=first.critical_repair,
                goal_relation=first.goal_relation,
                schedule_row=first.schedule_row,
            )
        )
    ids = [candidate.candidate_id for candidate in canonical]
    if len(set(ids)) != len(ids):
        raise PlannerInputError(
            "two canonical candidates share a candidate_id — the ids are what"
            " §16's eighth criterion and every trace row resolve to, so they"
            " have to be distinct"
        )
    return tuple(canonical)


#: §4's five identity fields — "同一个：focus target / target mode / modality /
#: learning intent / opportunity binding class 形成一个 canonical_key".
_IDENTITY_FIELDS = (
    "focus_target",
    "target_mode",
    "evidence_modality",
    "learning_intent",
    "opportunity_binding_class",
)


def _refuse_contradictory_scope(
    scope: UserIntentScope, candidates: Sequence[CanonicalCandidate]
) -> None:
    """BF-02 §9 (lines 274–292), verbatim: ``UserIntentScope = JUST_CHAT``
    together with a user-initiated learning candidate "属于上游契约错误".

    The document's own remedy is upstream — "用户如果显式发起学习请求，本
    DecisionCycle 的 UserIntentScope 应先变化为 LEARNING_REQUEST or
    TARGETED_LEARNING_REQUEST" — and its last line forbids the kernel guessing
    which authority is right, so this is a refusal rather than an exclusion:
    the caller's scope word and the caller's candidate disagree.
    """

    if scope is not UserIntentScope.JUST_CHAT:
        return
    for candidate in candidates:
        if candidate.user_initiated:
            raise PlannerInputError(
                f"{candidate.candidate_id}: a user-initiated candidate under"
                " UserIntentScope=JUST_CHAT is BF-02 §9's contradictory"
                " scope — an upstream contract error, with the scope word as"
                " the thing that has to change first"
            )


#: One factor's name and value, as an order-free comparison key.
_Vector = tuple[tuple[str, float], ...]


def _vector_of(
    proposal: CandidateProposal,
) -> tuple[_Vector, _Vector]:
    """A hashable, order-free view of one proposal's declared factor vector.

    A name the proposal does not carry is read as ``0.0`` here — this is the
    **comparison** that decides whether two arrivals of one key agree, never a
    score (judgement 14e): a proposal that omits a factor still fails §20's
    completeness check when its vector is assembled, so the tolerance cannot
    turn a missing number into a used one.
    """

    return (
        tuple((f.value, proposal.benefit.get(f, 0.0)) for f in BENEFIT_FACTORS),
        tuple((f.value, proposal.cost.get(f, 0.0)) for f in COST_FACTORS),
    )


# -- step 2: authoritative feature assembly ----------------------------------


def assemble_candidate_factors(
    candidate: CanonicalCandidate, authority: FeatureAuthority | None
) -> FactorAssembly:
    """One candidate's factor vector, assembled rather than assumed.

    The declared vector is validated first — all sixteen names, each a real
    number in ``[0, 1]``, BF-02 §20's "complete normalized factor vectors" —
    then the two factors a landed authority owns are read from that authority:

    - ``schedule_urgency`` — :func:`…feature_assembly.schedule_urgency_of`
      over the candidate's §5.2 row and the context's schedule authority. A
      declared number that differs from the authority's answer is an input
      contract error; a leg that answers ``None`` (no row, or a schedule
      authority that is not ``CURRENT``) is a gap, never a zero;
    - ``goal_relevance`` — :func:`…feature_assembly.goal_relevance_of`. That
      leg answers UNKNOWN in this repository, so the declared reading stands
      as :attr:`FactorSource.DECLARED` unless the context names
      ``GOAL_ASSESSMENT_PACK_MAPPING`` missing, in which case a declared
      number is refused (a gap).

    Every other factor is the candidate's own reading, carried as DECLARED.
    """

    _validate_identity(candidate)
    readings = _validate_declared_vector(candidate)
    _validate_scaffold_costs(candidate)
    gaps: list[FactorGap] = []
    owned: dict[BenefitFactor, FactorReading] = {}

    schedule_value, schedule_gap = _schedule_leg(candidate, authority)
    if schedule_gap is not None:
        gaps.append(schedule_gap)
    else:
        owned[BenefitFactor.SCHEDULE_URGENCY] = FactorReading(
            factor=BenefitFactor.SCHEDULE_URGENCY,
            value=_number(schedule_value),
            source=FactorSource.AUTHORITY,
            authority=AuthorityName.SCHEDULE,
        )

    goal_reading, goal_gap = _goal_leg(candidate, authority)
    if goal_gap is not None:
        gaps.append(goal_gap)
    elif goal_reading is not None:
        owned[BenefitFactor.GOAL_RELEVANCE] = goal_reading

    benefit: list[FactorReading] = []
    for factor in BENEFIT_FACTORS:
        if factor in owned:
            benefit.append(owned[factor])
            continue
        benefit.append(readings[str(factor)])
    cost = [readings[str(factor)] for factor in COST_FACTORS]
    return FactorAssembly(
        candidate_id=candidate.candidate_id,
        benefit=tuple(benefit),
        cost=tuple(cost),
        gaps=tuple(gaps),
    )


def _number(value: float | None) -> float:
    """A leg's number; a ``None`` means the caller should have made a gap."""

    if value is None:
        raise PlannerInputError("an authority leg answered with no number")
    return value


def _validate_identity(candidate: CanonicalCandidate) -> None:
    """BF-02 §11's mode/intent pairing, and §8's non-negative priority.

    docs/DOMAIN_MODEL.md §11 names TargetMode and LearningIntent but does not
    pair them; BF-02's frozen suite does (a PROBE that consolidates, or a
    REVIEW that establishes, is a contract error rather than a low-scoring
    candidate). Revisit: canonical text pairs them.
    """

    allowed = MODE_ALLOWED_INTENTS.get(candidate.target_mode, ())
    if candidate.learning_intent not in allowed:
        raise PlannerInputError(
            f"{candidate.candidate_id}: {candidate.target_mode.value} cannot"
            f" carry {candidate.learning_intent.value} — BF-02 §11's pairing"
            f" admits {', '.join(intent.value for intent in allowed)}"
        )
    if candidate.request_priority < 0:
        raise PlannerInputError(
            f"{candidate.candidate_id}: request_priority"
            f" {candidate.request_priority} is negative (§8 numbers explicit"
            " requests from zero)"
        )


def _validate_scaffold_costs(candidate: CanonicalCandidate) -> None:
    """BF-02 §11's floors: a scaffolded candidate may not look free.

    "如果 READY_WITH_SCAFFOLD or UNKNOWN + prerequisite_scaffoldable 则
    candidate 必须显式体现支架成本" with the reference minimum
    ``support_cost >= .25`` / ``cognitive_load >= .20``; the structural rule
    behind the numbers is "scaffold 不能被当成'免费 prerequisite'".
    """

    scaffolded = candidate.prerequisite_state is (
        PrerequisiteState.READY_WITH_SCAFFOLD
    ) or (
        candidate.prerequisite_state is PrerequisiteState.UNKNOWN
        and candidate.prerequisite_scaffoldable
    )
    if not scaffolded:
        return
    if candidate.cost[CostFactor.SUPPORT_COST] < SCAFFOLD_MIN_SUPPORT_COST:
        raise PlannerInputError(
            f"{candidate.candidate_id}: support_cost"
            f" {candidate.cost[CostFactor.SUPPORT_COST]!r} is below the"
            f" scaffold floor {SCAFFOLD_MIN_SUPPORT_COST} — a scaffold is not"
            " a free prerequisite (BF-02 §11)"
        )
    if candidate.cost[CostFactor.COGNITIVE_LOAD] < SCAFFOLD_MIN_COGNITIVE_LOAD:
        raise PlannerInputError(
            f"{candidate.candidate_id}: cognitive_load"
            f" {candidate.cost[CostFactor.COGNITIVE_LOAD]!r} is below the"
            f" scaffold floor {SCAFFOLD_MIN_COGNITIVE_LOAD} — a scaffold is"
            " not a free prerequisite (BF-02 §11)"
        )


def _validate_declared_vector(
    candidate: CanonicalCandidate,
) -> dict[str, FactorReading]:
    """BF-02 §20's complete normalized vector, or an input contract error."""

    readings: dict[str, FactorReading] = {}
    for benefit_factor in BENEFIT_FACTORS:
        readings[str(benefit_factor)] = _checked_reading(
            candidate.candidate_id,
            benefit_factor,
            candidate.benefit.get(benefit_factor),
        )
    for cost_factor in COST_FACTORS:
        readings[str(cost_factor)] = _checked_reading(
            candidate.candidate_id,
            cost_factor,
            candidate.cost.get(cost_factor),
        )
    return readings


def _checked_reading(
    candidate_id: str,
    factor: BenefitFactor | CostFactor,
    value: float | None,
) -> FactorReading:
    """One declared factor, or the input contract error it broke."""

    if value is None:
        raise PlannerInputError(
            f"{candidate_id}: factor {factor.value!r} is not declared — a"
            " factor vector is complete or it is not a vector (BF-02 §20)"
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlannerInputError(
            f"{candidate_id}: factor {factor.value!r} is not a number"
            f" ({value!r})"
        )
    if not 0.0 <= float(value) <= 1.0:
        raise PlannerInputError(
            f"{candidate_id}: factor {factor.value!r} outside [0, 1]"
            f" ({value!r})"
        )
    return FactorReading(
        factor=factor, value=float(value), source=FactorSource.DECLARED
    )


def _schedule_leg(
    candidate: CanonicalCandidate, authority: FeatureAuthority | None
) -> tuple[float | None, FactorGap | None]:
    """``schedule_urgency`` from the Scheduler's own answer (P7-0).

    Three outcomes, and judgement 11 names the reading behind them: the leg
    answers, a declared number contradicts it and the input contract is broken,
    or the leg answers nothing and the factor is a gap. The gap covers two
    facts this kernel cannot tell apart today — a row it holds but whose
    authority is not ``CURRENT``, and a target the Scheduler holds no row for,
    including the ``NOT_SCHEDULED`` rows the §10 view does not carry
    (judgement 13) — and the row's own currency is the *view's* property, so a
    caller who hands a row the view does not hold gets its number unchecked
    (judgement 14d).
    """

    declared = candidate.benefit[BenefitFactor.SCHEDULE_URGENCY]
    if authority is None:
        return None, FactorGap(
            factor=BenefitFactor.SCHEDULE_URGENCY,
            authority=AuthorityName.SCHEDULE,
            reason=(
                "the caller holds no PlanningContext, so no schedule"
                " authority was read: BF-02 §5 forbids answering this factor"
                " with a number — a declared one included"
            ),
        )
    if authority.schedule_authority is not ScheduleAuthority.CURRENT:
        return None, FactorGap(
            factor=BenefitFactor.SCHEDULE_URGENCY,
            authority=AuthorityName.SCHEDULE,
            reason=(
                "the schedule authority is "
                f"{authority.schedule_authority.value}: BF-02 §5's stale or"
                " missing Scheduler, whose numbers describe an earlier"
                " evidence set — the declared reading is refused rather than"
                " used"
            ),
        )
    value = schedule_urgency_of(
        candidate.schedule_row, authority.schedule_authority
    )
    if value is None:
        return None, FactorGap(
            factor=BenefitFactor.SCHEDULE_URGENCY,
            authority=AuthorityName.SCHEDULE,
            reason=(
                "the Scheduler holds no §5.2 row for this target: P7-0 reads"
                " that as 'the Scheduler was never asked', which is unknown"
                " rather than zero — and not the declared reading either"
            ),
        )
    if declared != value:
        raise PlannerInputError(
            f"{candidate.candidate_id}: declared schedule_urgency"
            f" {declared!r} disagrees with the §5.2 row the Scheduler"
            f" answered {value!r} — the factor is the Scheduler's, not the"
            " caller's"
        )
    return value, None


def _goal_leg(
    candidate: CanonicalCandidate, authority: FeatureAuthority | None
) -> tuple[FactorReading | None, FactorGap | None]:
    """``goal_relevance`` from the goal/assessment-pack leg (P7-0)."""

    declared = candidate.benefit[BenefitFactor.GOAL_RELEVANCE]
    if authority is not None and (
        AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING
        in authority.missing_authorities
    ):
        return None, FactorGap(
            factor=BenefitFactor.GOAL_RELEVANCE,
            authority=AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING,
            reason=(
                "the context names the Goal/Assessment pack mapping missing,"
                " so no goal relation can be turned into a number: 0 would"
                " claim the candidate is known to be irrelevant to the"
                " user's goals, which is what BF-02 §5 forbids"
            ),
        )
    value = goal_relevance_of(candidate.goal_relation.value)
    if value is not None and value != declared:
        raise PlannerInputError(
            f"{candidate.candidate_id}: declared goal_relevance"
            f" {declared!r} disagrees with the mapping's answer {value!r}"
        )
    if value is not None:
        return (
            FactorReading(
                factor=BenefitFactor.GOAL_RELEVANCE,
                value=value,
                source=FactorSource.AUTHORITY,
                authority=AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING,
            ),
            None,
        )
    return (
        FactorReading(
            factor=BenefitFactor.GOAL_RELEVANCE,
            value=declared,
            source=FactorSource.DECLARED,
        ),
        None,
    )


# -- steps 3-11 and the entry point ------------------------------------------


@dataclass(frozen=True)
class _Scored:
    """The two partial sums, the service adjustment and the utility."""

    benefit: float
    cost: float
    bonus: float
    utility: float


@dataclass(frozen=True)
class _Verdict:
    """Step 3's answer: the status, its code, and the parameters to use.

    ``parameters`` is set exactly when the status is ``SUCCEEDED``, so
    "a usable context" and "a profile to score with" are one fact rather than
    two that can disagree.
    """

    status: PlannerExecutionStatusValue
    error_code: str | None
    parameters: PolicyProfileParameters | None


def plan(planning_input: PlanningInput) -> KernelResult:
    """Run the eleven steps over one cycle and answer with their trace.

    Pure: the same :class:`PlanningInput` always produces an equal result, and
    the kernel holds no store, reads no clock and consumes no randomness
    (pinned by this cut's suite, which also replays one candidate set in two
    arrivals).
    """

    authority = planning_input.planning_context
    steps: list[KernelStep] = []

    # 1 — CandidateProposal canonicalize (BF-02 §4).
    steps.append(KernelStep.CANONICALIZE)
    candidates = canonicalize_proposals(planning_input.proposals)
    _refuse_contradictory_scope(planning_input.user_intent_scope, candidates)

    # 2 — authoritative feature assembly (P7-0's legs, per candidate).
    steps.append(KernelStep.FEATURE_ASSEMBLY)
    assemblies = {
        candidate.candidate_id: assemble_candidate_factors(candidate, authority)
        for candidate in candidates
    }

    # 3 — planning-context validity (BF-02 §5).
    steps.append(KernelStep.CONTEXT_VALIDITY)
    verdict = _context_verdict(authority, assemblies)
    context = _context_trace(authority, verdict)
    if verdict.parameters is None:
        return _undecided(
            planning_input, tuple(steps), context, candidates, assemblies
        )

    parameters = verdict.parameters
    scope = planning_input.user_intent_scope
    natural_break = context.natural_break_available

    # 4 — hard eligibility. Exclusion, not penalty: an excluded candidate
    # leaves the set and is never scored.
    steps.append(KernelStep.HARD_ELIGIBILITY)
    scored: list[CanonicalCandidate] = []
    exclusions: dict[str, ExclusionReason] = {}
    for candidate in candidates:
        reason = _exclusion_of(candidate, scope)
        if reason is None:
            scored.append(candidate)
        else:
            exclusions[candidate.candidate_id] = reason

    # 5 — policy utility, and 6 — the coverage-starvation safeguard.
    steps.append(KernelStep.POLICY_UTILITY)
    scores = {
        candidate.candidate_id: _score(
            assemblies[candidate.candidate_id],
            candidate,
            parameters,
            natural_break,
        )
        for candidate in scored
    }
    steps.append(KernelStep.COVERAGE_SAFEGUARD)

    # 7 — per-candidate activation (BF-02 §14).
    steps.append(KernelStep.ACTIVATION)
    paths = {
        candidate.candidate_id: _activation_path(candidate, scope)
        for candidate in scored
    }
    thresholds = {
        candidate.candidate_id: (
            None
            if paths[candidate.candidate_id] is ActivationPath.USER_INITIATED
            else parameters.automatic_activation_threshold
        )
        for candidate in scored
    }
    activated = {
        candidate.candidate_id: (
            thresholds[candidate.candidate_id] is None
            or scores[candidate.candidate_id].utility
            >= _number(thresholds[candidate.candidate_id])
        )
        for candidate in scored
    }
    active = [
        candidate for candidate in scored if activated[candidate.candidate_id]
    ]

    # 8 — explicit-request priority (BF-02 §8): with an eligible user-initiated
    # candidate the set is restricted to the minimum explicit priority.
    steps.append(KernelStep.REQUEST_PRIORITY)
    user_active = [
        candidate
        for candidate in active
        if paths[candidate.candidate_id] is ActivationPath.USER_INITIATED
    ]
    if user_active:
        minimum = min(candidate.request_priority for candidate in user_active)
        active = [
            candidate
            for candidate in user_active
            if candidate.request_priority == minimum
        ]

    # 9 — Pareto prune (BF-02 §15), within one dominance class.
    steps.append(KernelStep.PARETO_PRUNE)
    active, dominated = _pareto_prune(active, paths)

    # 10 — near-tie deterministic tie-break (BF-02 §16).
    steps.append(KernelStep.TIE_BREAK)
    tie_set, finalists = _tie_break(active, scores)

    # 11 — SELECT / NO_TARGET.
    steps.append(KernelStep.DECIDE)
    selected: CanonicalCandidate | None = None
    no_target_reason: NoTargetReason | None = None
    if not scored:
        no_target_reason = NoTargetReason.NO_ELIGIBLE_CANDIDATE
    elif not active:
        no_target_reason = NoTargetReason.BELOW_ACTIVATION_THRESHOLD
    else:
        selected = finalists[0]

    selected_id = None if selected is None else selected.candidate_id
    tie_ids = {candidate.candidate_id for candidate in tie_set}
    traces = tuple(
        _candidate_trace(
            candidate=candidate,
            assembly=assemblies[candidate.candidate_id],
            exclusion=exclusions.get(candidate.candidate_id),
            score=scores.get(candidate.candidate_id),
            path=paths.get(candidate.candidate_id),
            threshold=thresholds.get(candidate.candidate_id),
            activated=activated.get(candidate.candidate_id),
            dominated_by=dominated.get(candidate.candidate_id, ()),
            in_tie_set=candidate.candidate_id in tie_ids,
            selected=candidate.candidate_id == selected_id,
        )
        for candidate in candidates
    )
    reason_trace = _success_reasons(
        planning_input,
        candidates,
        exclusions,
        scores,
        paths,
        thresholds,
        activated,
        dominated,
        tie_set,
        selected,
        no_target_reason,
    )
    evaluation = _evaluation(
        planning_input.decision_cycle_id,
        candidates,
        exclusions,
        scores,
        reason_trace,
    )
    decision = PlannerDecisionOutcome(
        PlannerDecisionOutcome.SELECT
        if selected is not None
        else PlannerDecisionOutcome.NO_TARGET
    )
    decision_record = PlannerDecision(
        planner_decision_id=PlannerDecisionId(
            f"{_DECISION_PREFIX}{planning_input.decision_cycle_id}"
        ),
        decision_cycle_id=planning_input.decision_cycle_id,
        decision=decision,
        planner_evaluation_id=evaluation.planner_evaluation_id,
        selected_candidate_id=(
            None if selected_id is None else TargetId(selected_id)
        ),
        no_target_reason=(
            None if no_target_reason is None else no_target_reason.value
        ),
    )
    trace = PlannerTrace(
        decision_cycle_id=planning_input.decision_cycle_id,
        planner_version=evaluation.planner_version,
        policy_version=evaluation.policy_version,
        steps=tuple(steps),
        context=context,
        candidates=traces,
        decision=decision,
        selected_candidate_id=selected_id,
        no_target_reason=no_target_reason,
        runtime_outcome=runtime_decision_outcome_of(
            PlannerExecutionStatusValue.SUCCEEDED
        ),
    )
    return KernelResult(
        outcome=PlanningOutcome(
            evaluation=evaluation,
            execution_status=PlannerExecutionStatusRecord(
                decision_cycle_id=planning_input.decision_cycle_id,
                status=PlannerExecutionStatusValue.SUCCEEDED,
            ),
            decision=decision_record,
        ),
        trace=trace,
    )


def _context_verdict(
    authority: FeatureAuthority | None,
    assemblies: Mapping[str, FactorAssembly],
) -> _Verdict:
    """Step 3 — BF-02 §5, read off P7-0's record and this cut's gaps.

    The context half is P7-0's verdict, quoted and never re-derived: an absent
    context is ``UNAVAILABLE``, an incomplete assembly is ``DEGRADED`` /
    ``FEATURE_ASSEMBLY_INCOMPLETE``, an invalid snapshot is ``DEGRADED`` /
    ``SNAPSHOT_INVALID``, and a context that names no profile degrades as
    ``FEATURE_ASSEMBLY_INCOMPLETE`` again (judgement 14a — P7-0 leaves the
    profile ``None`` exactly when it could not map the policy). The candidate
    half is this cut's closure: a factor with no authority answer degrades the
    run instead of being scored as a ``0``.

    ``FAILED`` is deliberately unreachable — like
    :func:`elc.planner.feature_assembly.execution_status_of`, this kernel has
    no collaborator that can throw, so the word belongs to an execution this
    cut does not have. Revisit: the kernel gains a collaborator to read.
    """

    if authority is None:
        return _Verdict(
            status=PlannerExecutionStatusValue.UNAVAILABLE,
            error_code=DegradedReason.PLANNING_CONTEXT_UNAVAILABLE.value,
            parameters=None,
        )
    if authority.status is not FeatureAssemblyStatus.COMPLETE:
        return _Verdict(
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code=DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value,
            parameters=None,
        )
    if authority.snapshot_status is not SnapshotStatus.VALID:
        return _Verdict(
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code=DegradedReason.SNAPSHOT_INVALID.value,
            parameters=None,
        )
    if authority.planner_profile is None:
        return _Verdict(
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code=DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value,
            parameters=None,
        )
    if any(assembly.gaps for assembly in assemblies.values()):
        return _Verdict(
            status=PlannerExecutionStatusValue.DEGRADED,
            error_code=DegradedReason.FACTOR_AUTHORITY_UNKNOWN.value,
            parameters=None,
        )
    return _Verdict(
        status=PlannerExecutionStatusValue.SUCCEEDED,
        error_code=None,
        parameters=POLICY_PROFILES[authority.planner_profile],
    )


def _context_trace(
    authority: FeatureAuthority | None, verdict: _Verdict
) -> ContextTrace:
    """The context half of the trace, from P7-0's own fields."""

    return ContextTrace(
        feature_assembly_status=(
            None if authority is None else authority.status
        ),
        snapshot_status=None if authority is None else authority.snapshot_status,
        schedule_authority=(
            None if authority is None else authority.schedule_authority
        ),
        missing_authorities=(
            () if authority is None else authority.missing_authorities
        ),
        natural_break_available=(
            False if authority is None else authority.natural_break_available
        ),
        planner_profile=None if authority is None else authority.planner_profile,
        automatic_teaching_enabled=(
            False if authority is None else authority.automatic_teaching_enabled
        ),
        policy_mapping_version=(
            None if authority is None else authority.policy_mapping_version
        ),
        reasons=() if authority is None else authority.reasons,
        execution_status=verdict.status,
        error_code=verdict.error_code,
    )


def runtime_decision_outcome_of(
    status: PlannerExecutionStatusValue,
) -> RuntimeDecisionOutcomeValue:
    """The Runtime's turn-level outcome this status implies (BF-02 §5 lines
    168–174): a degraded planner run is ``DEGRADED_NO_AUTOMATIC_TEACHING``
    rather than a fabricated ``NO_TARGET``.

    The **record** (docs/DATA_MODEL.md §14 ``RuntimeDecisionOutcome``) belongs
    to the Runtime; this function only answers the value the Planner's status
    implies, so a caller can build one without re-deciding the coupling. A
    successful run is ``NORMAL`` whether it selected or found no target:
    ``NO_TARGET`` is a decision, not a degradation.
    """

    if status is PlannerExecutionStatusValue.SUCCEEDED:
        return RuntimeDecisionOutcomeValue.NORMAL
    return RuntimeDecisionOutcomeValue.DEGRADED_NO_AUTOMATIC_TEACHING


# -- step 4: hard eligibility ------------------------------------------------


def _exclusion_of(
    candidate: CanonicalCandidate, scope: UserIntentScope
) -> ExclusionReason | None:
    """The first hard rule that excludes this candidate, or ``None``.

    None of these rules is a magnitude: each one removes the candidate
    (module docstring, hard rule one). The readiness floors are BF-02 §10's
    four rows, read in the precedence the module docstring registers
    (judgement 5), and the runtime-generated escape hatch is §10's
    "user-initiated only" — it can never carry an automatic candidate past its
    floor.
    """

    if candidate.expired:
        return ExclusionReason.EXPIRED
    if candidate.deprecated:
        return ExclusionReason.DEPRECATED
    if candidate.suppressed:
        return ExclusionReason.SUPPRESSED
    if not candidate.modality_available:
        return ExclusionReason.MODALITY_UNAVAILABLE
    if candidate.prerequisite_state is PrerequisiteState.BLOCKED:
        return ExclusionReason.HARD_PREREQUISITE_BLOCKED
    if candidate.prerequisite_state is PrerequisiteState.UNKNOWN and not (
        candidate.target_mode is TargetMode.PROBE
        or candidate.prerequisite_scaffoldable
    ):
        return ExclusionReason.PREREQUISITE_UNKNOWN_UNRESOLVED
    if scope is UserIntentScope.JUST_CHAT:
        return ExclusionReason.JUST_CHAT
    if scope is UserIntentScope.TARGETED_LEARNING_REQUEST and not (
        candidate.request_aligned
    ):
        return ExclusionReason.OUTSIDE_TARGETED_SCOPE
    if scope is UserIntentScope.NON_LEARNING_TASK and not (
        candidate.user_initiated
        or candidate.task_aligned
        or candidate.critical_repair
    ):
        return ExclusionReason.NON_LEARNING_TASK_SCOPE

    floor = _readiness_floor(candidate)
    runtime_escape = (
        candidate.runtime_generated_ready and candidate.user_initiated
    )
    if (
        READINESS_RANK[candidate.content_readiness] < READINESS_RANK[floor]
        and not runtime_escape
    ):
        return ExclusionReason.CONTENT_NOT_READY
    return None


def _readiness_floor(candidate: CanonicalCandidate) -> ReadinessLevel:
    """BF-02 §10's four rows, read in the registered precedence."""

    if candidate.target_mode is TargetMode.PROBE:
        return ReadinessLevel(ELIGIBLE_PROBE_READINESS)
    if candidate.user_initiated:
        return ReadinessLevel(ELIGIBLE_USER_INITIATED_READINESS)
    if "CURRENT_USER_ERROR" in candidate.origins:
        return ReadinessLevel(ELIGIBLE_CURRENT_USER_ERROR_READINESS)
    return ReadinessLevel(ELIGIBLE_AUTOMATIC_READINESS)


# -- steps 5-6: utility and the coverage safeguard ---------------------------


def _score(
    assembly: FactorAssembly,
    candidate: CanonicalCandidate,
    parameters: PolicyProfileParameters,
    natural_break_available: bool,
) -> _Scored:
    """BF-02 §12's formula plus §13's service bonus.

    ``Utility = initiative_multiplier(policy) × Benefit −
    cost_multiplier(policy) × Cost + eligible coverage-service bonus``, with
    both sums folded in §10.1's factor order so no mapping-insertion order can
    reach the result. The bonus is §13's two-layer safeguard: a CRITICAL
    coverage-service state, a natural break available, and a profile that
    carries a bonus at all (LOUNGE's reference row is ``+0``; judgement 14b
    reads that third condition as ``coverage_service_bonus > 0.0`` rather than
    as a list of profiles).
    """

    benefit = sum(
        BENEFIT_WEIGHTS[factor] * assembly.value_of(factor)
        for factor in BENEFIT_FACTORS
    )
    cost = sum(
        COST_WEIGHTS[factor] * assembly.value_of(factor)
        for factor in COST_FACTORS
    )
    utility = (
        parameters.initiative_multiplier[candidate.initiative_class] * benefit
        - parameters.cost_multiplier * cost
    )
    bonus = 0.0
    if (
        candidate.coverage_service_state is CoverageServiceState.CRITICAL
        and natural_break_available
        and parameters.coverage_service_bonus > 0.0
    ):
        bonus = parameters.coverage_service_bonus
        utility += bonus
    return _Scored(benefit=benefit, cost=cost, bonus=bonus, utility=utility)


def _activation_path(
    candidate: CanonicalCandidate, scope: UserIntentScope
) -> ActivationPath:
    """BF-02 §8/§14: an explicit request has a path, an automatic candidate a
    threshold.

    The two scope words are §12's request scopes — a user-initiated candidate
    under ``JUST_CHAT`` never reaches this function, because §9's
    contradictory scope is excluded at step 4 instead of being guessed at.
    """

    if candidate.user_initiated and scope in (
        UserIntentScope.LEARNING_REQUEST,
        UserIntentScope.TARGETED_LEARNING_REQUEST,
    ):
        return ActivationPath.USER_INITIATED
    return ActivationPath.AUTOMATIC


# -- step 9: Pareto dominance --------------------------------------------------


def _dominance_class(
    candidate: CanonicalCandidate, path: ActivationPath
) -> tuple[object, ...]:
    """§15's four class members: activation path, initiative class, request
    priority and coverage-service class."""

    return (
        path,
        candidate.initiative_class,
        candidate.request_priority,
        candidate.coverage_service_state,
    )


def _pareto_prune(
    active: Sequence[CanonicalCandidate],
    paths: Mapping[str, ActivationPath],
) -> tuple[list[CanonicalCandidate], dict[str, tuple[str, ...]]]:
    """Remove the strictly dominated candidates before any tie-break (§15).

    ``A`` dominates ``B`` inside one class when every benefit factor is at
    least ``B``'s, every cost factor is at most ``B``'s, and at least one
    comparison is strict. A pruned candidate records **every** dominator in
    canonical order, so the trace says why it left rather than only that it
    did.
    """

    kept: list[CanonicalCandidate] = []
    dominated: dict[str, tuple[str, ...]] = {}
    for index, candidate in enumerate(active):
        dominators = tuple(
            other.candidate_id
            for other_index, other in enumerate(active)
            if other_index != index and _dominates(other, candidate, paths)
        )
        if dominators:
            dominated[candidate.candidate_id] = dominators
        else:
            kept.append(candidate)
    return kept, dominated


def _dominates(
    a: CanonicalCandidate,
    b: CanonicalCandidate,
    paths: Mapping[str, ActivationPath],
) -> bool:
    """§15's comparison is over the factor vectors, not over their sums."""

    if _dominance_class(a, paths[a.candidate_id]) != _dominance_class(
        b, paths[b.candidate_id]
    ):
        return False
    benefits_ge = all(
        a.benefit[factor] >= b.benefit[factor] for factor in BENEFIT_FACTORS
    )
    costs_le = all(a.cost[factor] <= b.cost[factor] for factor in COST_FACTORS)
    strict = any(
        a.benefit[factor] > b.benefit[factor] for factor in BENEFIT_FACTORS
    ) or any(a.cost[factor] < b.cost[factor] for factor in COST_FACTORS)
    return benefits_ge and costs_le and strict


# -- step 10: the near-tie deterministic tie-break ----------------------------


def _tie_break(
    active: Sequence[CanonicalCandidate],
    scores: Mapping[str, _Scored],
) -> tuple[list[CanonicalCandidate], list[CanonicalCandidate]]:
    """§16 over the activated, non-dominated candidates.

    The tie set is the near-tie window — the best utility minus a candidate's
    own is at most :data:`TIE_EPSILON` — and the finalists are those sharing
    the best §16 key. The eighth criterion ("stable candidate_id") is the
    deterministic floor: the finalists are ordered by id and the first one is
    the selection, so an exactly-tied pair still has one answer.
    """

    if not active:
        return [], []
    best = max(scores[candidate.candidate_id].utility for candidate in active)
    tie_set = [
        candidate
        for candidate in active
        if best - scores[candidate.candidate_id].utility <= TIE_EPSILON
    ]
    best_key = max(_tie_key(candidate) for candidate in tie_set)
    finalists = sorted(
        (
            candidate
            for candidate in tie_set
            if _tie_key(candidate) == best_key
        ),
        key=lambda candidate: candidate.candidate_id,
    )
    return tie_set, finalists


def _tie_key(candidate: CanonicalCandidate) -> tuple[float, ...]:
    """§16's first seven criteria, in order, as one comparable key.

    Criterion 3 is "REACTIVE > OPPORTUNISTIC > PROACTIVE" and criteria 5–7 are
    *lower* costs, so those four are negated — a larger key still wins. The
    eighth criterion is applied to the finalists rather than folded in here.
    """

    return (
        1.0 if candidate.request_aligned else 0.0,
        1.0 if candidate.user_initiated else 0.0,
        float(INITIATIVE_TIE_RANK[candidate.initiative_class]),
        candidate.benefit[BenefitFactor.OPPORTUNITY_EXPIRY],
        -candidate.cost[CostFactor.INTERRUPTION_COST],
        -candidate.cost[CostFactor.OVEREXPOSURE],
        -candidate.cost[CostFactor.COGNITIVE_LOAD],
    )


# -- the records this cut mints ----------------------------------------------


#: The id prefixes this cut mints (module docstring, judgement 7).
_EVALUATION_PREFIX = "pe-"
_DECISION_PREFIX = "pd-"


def _evaluation(
    decision_cycle_id: DecisionCycleId,
    candidates: Sequence[CanonicalCandidate],
    exclusions: Mapping[str, ExclusionReason],
    scores: Mapping[str, _Scored],
    reason_trace: tuple[str, ...],
) -> PlannerEvaluation:
    """The canonical evaluation record: ranked candidates and the reason trace.

    ``ranked_candidates`` holds every eligible candidate in the ranking the
    kernel used — utility descending, then §16's key, then the stable id
    (judgement 14c: the decision's own ranking, with no order fixed for the
    record) — and ``()`` on a degraded run, where nothing was scored. The id is
    content-addressed from the decision cycle: no clock, and two runs of one
    cycle agree.

    ``frontier_candidate_ids`` is the run's
    :class:`~elc.planner.frontier.ActiveLearningFrontier`, built here from the
    very set step 4 kept — so the column §14 names and the frontier's own
    definition (survivors are members, exclusions are not) are one fact rather
    than two that could drift. P7-1 left this column to p7-3 and judgement 12
    said so; the frontier's own module states the order reading that makes it
    step 4's set and no twelfth step.
    """

    frontier = frontier_of(
        candidates,
        {cid: reason.value for cid, reason in exclusions.items()},
    )
    ranked = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.candidate_id not in exclusions
        ),
        key=lambda candidate: (
            -scores[candidate.candidate_id].utility,
            tuple(-value for value in _tie_key(candidate)),
            candidate.candidate_id,
        ),
    )
    return PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId(
            f"{_EVALUATION_PREFIX}{decision_cycle_id}"
        ),
        decision_cycle_id=decision_cycle_id,
        planner_version=PlannerVersion(PLANNER_KERNEL_MODEL_VERSION),
        policy_version=PolicyVersion(PLANNER_PROFILE_VERSION),
        ranked_candidates=tuple(
            TargetCandidate(
                candidate_id=candidate.candidate_id,
                canonical_key=candidate.canonical_key,
                target_id=TargetId(candidate.focus_target),
                initiative_class=candidate.initiative_class,
                target_mode=candidate.target_mode,
                learning_intent=candidate.learning_intent,
                request_priority=candidate.request_priority,
                goal_relation=candidate.goal_relation,
            )
            for candidate in ranked
        ),
        reason_trace=reason_trace,
        frontier_candidate_ids=frontier.candidate_ids,
    )


def _candidate_trace(
    *,
    candidate: CanonicalCandidate,
    assembly: FactorAssembly,
    exclusion: ExclusionReason | None,
    score: _Scored | None,
    path: ActivationPath | None,
    threshold: float | None,
    activated: bool | None,
    dominated_by: tuple[str, ...],
    in_tie_set: bool,
    selected: bool,
) -> CandidateTrace:
    """One trace row; an excluded candidate carries no score at all."""

    return CandidateTrace(
        candidate_id=candidate.candidate_id,
        canonical_key=candidate.canonical_key,
        merged_from=candidate.candidate_ids,
        initiative_class=candidate.initiative_class,
        request_priority=candidate.request_priority,
        coverage_service_state=candidate.coverage_service_state,
        benefit=assembly.benefit,
        cost=assembly.cost,
        gaps=assembly.gaps,
        excluded=exclusion,
        benefit_score=None if score is None else score.benefit,
        cost_score=None if score is None else score.cost,
        coverage_service_bonus=None if score is None else score.bonus,
        utility=None if score is None else score.utility,
        activation_path=path,
        activation_threshold=threshold,
        activated=activated,
        dominated_by=dominated_by,
        in_tie_set=in_tie_set,
        selected=selected,
    )


def _undecided(
    planning_input: PlanningInput,
    steps: tuple[KernelStep, ...],
    context: ContextTrace,
    candidates: Sequence[CanonicalCandidate],
    assemblies: Mapping[str, FactorAssembly],
) -> KernelResult:
    """A degraded or unavailable run: no decision, and the why in the trace.

    Nothing is scored here — no candidate carries a utility — because scoring
    a vector the assembly could not complete is what BF-02 §5 exists to
    prevent. The record is still built through :class:`PlanningOutcome`, so
    the coupling "a degraded status carries no PlannerDecision" is enforced by
    the type rather than by this function's discipline.

    ``frontier_candidate_ids`` is ``()`` here and that is the honest value
    rather than an empty frontier: step 4 never ran, so no set survived it
    (``elc.planner.frontier`` reads a frontier as the fourth step's answer).
    """

    reasons: list[str] = [
        f"p7-1: execution_status={context.execution_status.value}"
        f" error_code={context.error_code}"
        " — no PlannerDecision (BF-02 §5 lines 161-174: an incomplete"
        " assembly or an invalid snapshot degrades instead of fabricating"
        " NO_TARGET)"
    ]
    reasons.append(
        "p7-1: missing_authorities=["
        + ", ".join(name.value for name in context.missing_authorities)
        + "]"
    )
    for index, reason in enumerate(context.reasons):
        reasons.append(f"p7-1: authority reason[{index}]: {reason}")
    for candidate in candidates:
        for gap in assemblies[candidate.candidate_id].gaps:
            reasons.append(
                f"p7-1: factor gap {candidate.candidate_id}:"
                f" {gap.factor.value} needs {gap.authority.value}"
                f" — {gap.reason}"
            )
    evaluation = PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId(
            f"{_EVALUATION_PREFIX}{planning_input.decision_cycle_id}"
        ),
        decision_cycle_id=planning_input.decision_cycle_id,
        planner_version=PlannerVersion(PLANNER_KERNEL_MODEL_VERSION),
        policy_version=PolicyVersion(PLANNER_PROFILE_VERSION),
        ranked_candidates=(),
        reason_trace=tuple(reasons),
        frontier_candidate_ids=(),
    )
    return KernelResult(
        outcome=PlanningOutcome(
            evaluation=evaluation,
            execution_status=PlannerExecutionStatusRecord(
                decision_cycle_id=planning_input.decision_cycle_id,
                status=context.execution_status,
                error_code=context.error_code,
            ),
            decision=None,
        ),
        trace=PlannerTrace(
            decision_cycle_id=planning_input.decision_cycle_id,
            planner_version=evaluation.planner_version,
            policy_version=evaluation.policy_version,
            steps=steps,
            context=context,
            candidates=tuple(
                _candidate_trace(
                    candidate=candidate,
                    assembly=assemblies[candidate.candidate_id],
                    exclusion=None,
                    score=None,
                    path=None,
                    threshold=None,
                    activated=None,
                    dominated_by=(),
                    in_tie_set=False,
                    selected=False,
                )
                for candidate in candidates
            ),
            decision=None,
            selected_candidate_id=None,
            no_target_reason=None,
            runtime_outcome=runtime_decision_outcome_of(context.execution_status),
        ),
    )


def _success_reasons(
    planning_input: PlanningInput,
    candidates: Sequence[CanonicalCandidate],
    exclusions: Mapping[str, ExclusionReason],
    scores: Mapping[str, _Scored],
    paths: Mapping[str, ActivationPath],
    thresholds: Mapping[str, float | None],
    activated: Mapping[str, bool],
    dominated: Mapping[str, tuple[str, ...]],
    tie_set: Sequence[CanonicalCandidate],
    selected: CanonicalCandidate | None,
    no_target_reason: NoTargetReason | None,
) -> tuple[str, ...]:
    """One line per fact a reviewer needs in order to replay the decision."""

    reasons: list[str] = [
        f"p7-1: user_intent_scope={planning_input.user_intent_scope.value}"
        f" proposals={len(planning_input.proposals)}"
        f" canonical={len(candidates)}"
    ]
    for candidate in candidates:
        score = scores.get(candidate.candidate_id)
        if score is None:
            reasons.append(
                f"p7-1: excluded {candidate.candidate_id}:"
                f" {exclusions[candidate.candidate_id].value}"
            )
            continue
        threshold = thresholds[candidate.candidate_id]
        spelled = "none" if threshold is None else f"{threshold:.6f}"
        reasons.append(
            f"p7-1: {candidate.candidate_id}"
            f" benefit={score.benefit:.6f} cost={score.cost:.6f}"
            f" coverage_service_bonus={score.bonus:.6f}"
            f" utility={score.utility:.6f}"
            f" activation={paths[candidate.candidate_id].value}"
            f" threshold={spelled}"
            f" activated={activated[candidate.candidate_id]}"
        )
        if candidate.candidate_id in dominated:
            reasons.append(
                f"p7-1: pareto removed {candidate.candidate_id} (dominated by"
                f" {', '.join(dominated[candidate.candidate_id])})"
            )
    reasons.append(
        "p7-1: tie set ["
        + ", ".join(candidate.candidate_id for candidate in tie_set)
        + f"] within epsilon={TIE_EPSILON}"
    )
    if selected is not None:
        reasons.append(
            f"p7-1: decision SELECT {selected.candidate_id} (utility"
            f" {scores[selected.candidate_id].utility:.6f},"
            f" activation={paths[selected.candidate_id].value})"
        )
    else:
        reason = (
            no_target_reason
            if no_target_reason is not None
            else NoTargetReason.NO_ELIGIBLE_CANDIDATE
        )
        reasons.append(f"p7-1: decision NO_TARGET reason={reason.value}")
    return tuple(reasons)
