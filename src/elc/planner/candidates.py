"""Candidate supply — Track A and Track B generators (P7-2).

docs/PRODUCT_CONTRACT.md §6 pins two lanes and their sources, verbatim::

    Track A — Expression-driven
      CURRENT_USER_ERROR
      EXPRESSION_NEED
      NATURAL_USE_EXPANSION
      PRAGMATIC_REGISTER_OPPORTUNITY
      MANUAL_USER_REQUEST
      CURRENT_CONTEXT_TRANSFER_OPPORTUNITY
        "此刻什么与用户真实表达最相关。"

    Track B — Curriculum-driven
      CONFIRMED_GAP
      SCHEDULED_REVIEW
      UNKNOWN_PROBE
      TRANSFER_EXPANSION
      SUPPORT_WITHDRAWAL
      CORE_COVERAGE
      GOAL_SPECIFIC_TARGET
      COVERAGE_DEBT
        "长期什么不能一直没学。"

    "两条 lane 进入同一 Planner，不做成两个系统。"

This module is the supply side of that sentence: both lanes end in **the same**
:class:`~elc.planner.kernel.CandidateProposal` type, in one call
(:func:`generate_candidates`), and the next thing that happens to those
proposals is BF-02 §3's pipeline — whose step 1 (canonicalize/merge), step 4
(hard eligibility), step 5 (utility) and step 9–10 (Pareto, tie-break) are
**not** re-implemented here. The generators generate; the kernel decides.

**What a generator may write, and what it may not.** BF-02 §20 freezes the
kernel's input as "complete normalized factor vectors", and P7-1's kernel says
where each number's *authority* lies: ``schedule_urgency`` is the Scheduler's
answer and must be the §5.2 row's own, ``goal_relevance`` has no mapping to read,
and the other fourteen factors are the candidate's own declared reading "which
is what makes the trace able to answer 'which numbers did an authority answer,
and which did a generator supply?'". So every declared factor below comes from
a table with a basis, and the numbers it resolves to are BF-02's **reference
factor bands** (``planner_reference_profile_v1_1.json``'s
``reference_factor_bands``), never hand-picked decimals:

- :data:`FACTOR_BAND_VALUES` is the frozen ladder, factor name → band word →
  number, and this cut's suite extracts the asset and compares all of it;
- :data:`SOURCE_READINGS` is one row per source: the mode/intent/initiative the
  source means, the bands it moves, and the reason — quoted where the frozen
  golden scenarios price the same source (``GS01``/``GS03``/``GS04``/``GS21``/
  ``GS23``), declared where they do not;
- :data:`ABSENT_READINGS` is the neutral reading a source that says nothing
  gets: the *lowest declared band* of each factor (BF-02 §6's cost ladders have
  no zero band, and ``curriculum_value``'s lowest band is ``MINOR``), plus the
  two literal zeros for the two factors the asset gives no band at all —
  ``goal_relevance`` (no mapping is landed, P7-0's own registration) and
  ``coverage_debt`` (nothing said how much debt a target carries *for a call
  that hands in no ledger*; P7-3 landed the ledger, and the ledger leg below
  reads the obligation's own number whenever a caller hands one in). A literal
  is refused for any *other* factor, so "the number came from a band" is
  checkable rather than promised.

**Which sources can answer today, and which are registered absent.** §6's
vocabulary is complete below — fourteen rows, fourteen source words — but a
source answers only when the authority it reads exists, and this repository
lands five of them:

=================================  ==========================================
answers today                      reads
=================================  ==========================================
``SCHEDULED_REVIEW``               the Scheduler's own due decision and row
``UNKNOWN_PROBE``                  the §11 learner state (never observed)
``CONFIRMED_GAP``                  BF-01 §25's ``CONFIRMED_GAP`` flag
``SUPPORT_WITHDRAWAL``             BF-01 §25's ``SUPPORT_DEPENDENT`` flag
``COVERAGE_DEBT``                  the caller's ``PlanningLedger`` view
=================================  ==========================================

The last row answers **only when the call hands a ledger in**: P7-3 landed the
PlanningLedger (`elc.planner.ledger`) as the caller's own view, and a call that
hands in none gets the same registered gap it always got — the gap text for that
authority is deliberately unchanged, because it is the honest description of a
call with no ledger in hand.

The other nine are **registered, not approximated**. Five Track A sources and
one Track B source need a *turn-scoped* observation the repository does not
produce: RUNTIME_ARCHITECTURE §4 step 3 lists the durable artifacts the
conversation leg should write (a "Teaching opportunity proposal", the
``UserIntentScope``, the ``ConversationPriorityView``) and no cut records one,
so a caller may hand an observation in
(:class:`TurnOpportunityObservation` — the shape this cut declares *because* the
artifact has none) and the sources answer; production hands nothing in, the
generator invents nothing, and each affected source emits a
:class:`SourceGap` naming its missing producer. The remaining three wait for an
authority nobody has landed: ``TRANSFER_EXPANSION`` (D-INV-010 gives the Planner
the transfer decision, but nothing answers "transfer where" — no transfer
policy, and V1's modality pair has none), ``CORE_COVERAGE`` (§7 gives Curriculum
a *core tier*; the registry's four columns carry none and the corpus declares
none), and ``GOAL_SPECIFIC_TARGET`` (the Goal/Assessment pack mapping
IMPLEMENTATION_PLAN §7 line 340 lists is not built — P7-0 registers the same
absence on its own leg). ``COVERAGE_DEBT`` was the fourth until P7-3 landed the
ledger; what it waits for now is a caller who hands one in.

**Three calls this module makes, each registered where it is made:**

1. **the readiness gate refuses, the prerequisite resolver marks.** A target
   whose §8.1 ladder answer is "no level" cannot be a candidate — the kernel's
   vocabulary has no "unknown readiness" word, and §8.1 has no level under R0 —
   so it is refused with the ladder's blocking keys and the cycle's context
   assembly reads the same ``None`` (P7-0's ``CURRICULUM_READINESS`` leg, which
   is what makes a real run degrade instead of quietly finding nothing). A
   *prerequisite* that is unknown or blocked does **not** drop the candidate:
   the state travels on the proposal and the kernel names the exclusion in its
   trace (``PREREQUISITE_UNKNOWN_UNRESOLVED`` / ``HARD_PREREQUISITE_BLOCKED``),
   which is the auditable direction. Revisit: canonical text gives readiness an
   "unknown" word, or the content side lands the facts §8.1's ladder requires;
2. **a target with no §5.2 row is refused rather than generated with a
   ``0``.** BF-02 §5 forbids answering ``schedule_urgency`` with a number when
   the Scheduler was never asked, and P7-1's kernel turns a rowless candidate
   into a run-level ``DEGRADED`` — so the supply side refuses the target and
   names the Scheduler, instead of handing the kernel a vector it would have to
   reject. P6-2 writes a ``NOT_SCHEDULED`` row for exactly this distinction
   ("refusing to write it would leave the Planner unable to distinguish 'no
   review debt' from 'the Scheduler was never asked'"), which is why the
   refusal only fires for a target with *no* row at all. Revisit: p7-1's
   judgement 13 is closed (a fourth bucket, a direct §5.2 lookup, or an
   assembly that says which of the two it saw) — then a rowless target can
   travel as a declared gap;
3. **suppression is marked, never applied.** §9's ``DO_NOT_AUTO_TEACH`` marks an
   *automatic* candidate ``suppressed`` (its own word is "automatically", so a
   user-initiated candidate of the same target is not marked) and
   ``SUPPRESS_REVIEW`` marks a ``REVIEW`` candidate — both through the kernel's
   step 4, so the trace carries ``SUPPRESSED`` and §13's "coverage service still
   不能突破 suppression" holds by construction. Dropping them here would hide
   the exclusion from the audit. ``JUST_CHAT`` is not a per-candidate mark at
   all: it is a §12 scope word (elc.planner.scope resolves it), and BF-02 §9's
   contradiction is refused by the kernel when a caller routes around that
   resolver.

**The ledger leg (P7-3), and the three readings it moves.** A call may hand in
a :class:`~elc.planner.ledger.PlanningLedger` view — P7-3 landed it as the
caller's own read-only view (`NO_TABLE_V1` then; P8-3 gave it durable tables
behind ``elc.planner.ledger_store``, while the producer that would *present* a
Moment is still p8-4's). Exactly three readings change, and nothing else
does:

- ``overexposure`` — **every** candidate's cost factor reads its target's band
  off the ledger's window count, because the factor is a fact about the *target*
  (how often it has been shown) rather than about the source that proposed it.
  The band word is the ledger's and the number stays in
  :data:`FACTOR_BAND_VALUES`; a call with no ledger keeps the neutral ``NONE``;
- ``coverage_debt`` — the ``COVERAGE_DEBT`` source's own number, read from the
  governing obligation's ``debt_value`` (the ledger declares the column to live
  in ``[0, 1]``). The row's declared literal ``1.0`` is what the frozen golden
  prices a full obligation at and is the *no-ledger* reading; other sources keep
  the absent literal ``0.0``, because a candidate that is not proposing coverage
  service is not claiming a debt;
- ``coverage_service_state`` — the same obligation's ladder position
  (:func:`~elc.planner.ledger.coverage_service_state_of`), which is what BF-02
  §13's safeguard reads. Only the ledger-reading source carries a state other
  than ``NONE``: the state is the *obligation's*, and a review or a probe of the
  same target is not proposing the coverage service.

Two consequences worth stating rather than leaving to a reader: the ledger
**never** filters here (its ``serviceable_targets`` is a list of targets a
coverage-debt candidate may be built for, and every one of them still travels
through the kernel's step 4 like any other candidate), and a paused obligation
proposes nothing at all — it must not accrue impossible debt (BF-06 §14), so
there is no debt for a cycle to pay.

**One order this cut does not decide, and registers instead.** docs/
STATE_MACHINES.md §19's "Planner Flow State" walks the same flow as
DOMAIN_MODEL §10.1 with one extra step::

    → hard eligibility (scope/prereq/readiness/modality/suppression)
    → ActiveLearningFrontier
    → Policy Utility

§10.1's block — the one P7-1 made executable, step for step — has no
``ActiveLearningFrontier`` line at all, so the two canonical documents put the
frontier in different places relative to policy utility. This cut is the step
*before* both versions of the divergence (it hands candidates to
canonicalization) and it depends on neither reading: no proposal here is
ordered, pruned or filtered by a frontier, and the generator's emission order is
§6's source order rather than a frontier's. The difference is therefore
**registered, not resolved** *by this cut*: the step belongs to p7-3 (the cut
that owns ``ActiveLearningFrontier`` and ``PlanningLedger``), and its placement
decides whether an eligibility-excluded candidate still consumes frontier
coverage — which is exactly the judgement a frontier cut has to make. **P7-3 has
since made it**, and this paragraph is kept as the registration it was: the
frontier stands where §19 puts it, its members are step 4's survivors (an
excluded candidate is not a member), §10.1's eleven steps are untouched, and
:mod:`elc.planner.frontier` states the reading while the kernel fills
``PlannerEvaluation.frontier_candidate_ids`` from it. Revisit: a canonical
revision brings §19 and §10.1 into line.

**The fields beside the priced vector, and where their values come from.**
Only the vector is priced; every other field a proposal carries is a read of a
landed row or a declared word, and this paragraph is the registry:

- **identity** is the §11 row's own (``target_mode`` / ``learning_intent`` /
  ``evidence_modality``), plus this module's ``opportunity_binding_class``
  (the source word, registered above) and the §5.2 row carried as
  ``schedule_row`` because the Scheduler owns it; the two supply gates'
  answers travel as ``content_readiness`` / ``prerequisite_state`` /
  ``prerequisite_scaffoldable``;
- **eligibility** is declared, and each declaration is a consequence of a gate
  or of a registered absence rather than a guess: ``modality_available=True``
  because a §11 row outside V1's modality pair is refused before a proposal
  exists (the ``MODALITY`` gate); ``expired`` / ``deprecated`` false because no
  authority reads out an expired opportunity, and the shipped supply face's
  §24.11 filter keeps retired entities out of the target set before this module
  runs; ``runtime_generated_ready`` false because this generator produces no
  runtime-generated content; ``task_aligned`` / ``critical_repair`` false
  because no task binding and no critical-repair seat is published;
  ``goal_relation=NONE`` per §24.14's vocabulary with the one authority P7-1's
  input contract still names (the goal pack mapping), and
  ``coverage_service_state`` is ``NONE`` unless the ``COVERAGE_DEBT`` source
  reads it off the ledger — the authority landed, so the word here is the
  ledger's answer for the one source that proposes coverage service (the ledger
  leg above). A cut that lands the goal mapping reads that word here instead of
  keeping the literal, because the kernel's hard rules do read these words.
- one flag is read **two ways** in this repository, and both readings fail
  closed with only §11's word differing: ``INSUFFICIENT_EVIDENCE`` is "no state
  to judge" to the probe condition (:func:`_has_no_state` — a target a probe
  may resolve) and "proven unmet" to the prerequisite resolver
  (:func:`elc.planner.supply.prerequisite_state_of` — a ``HARD`` edge carrying
  it is ``BLOCKED``). Neither reading lets the flag mean *satisfied*, and the
  kernel excludes both words (``PREREQUISITE_UNKNOWN_UNRESOLVED`` is bypassed
  only for a probe or a scaffold).

**What this module is not.** It does not rank, score, prune or select (the
kernel does); it does not write anything (no store, no clock, no randomness —
the same input always produces the same proposals, in the same order); it does
not own a ledger (``coverage_debt`` / ``overexposure`` /
``coverage_service_state`` are **read** off the caller's
:class:`~elc.planner.ledger.PlanningLedger` view, never computed here), and it
claims nothing about shadow mode, the Gate or automatic teaching.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from elc.content.queries import ContentTargetView
from elc.planner.feature_assembly import schedule_urgency_of
from elc.planner.kernel import (
    MODE_ALLOWED_INTENTS,
    SCAFFOLD_MIN_COGNITIVE_LOAD,
    SCAFFOLD_MIN_SUPPORT_COST,
    BenefitFactor,
    CandidateProposal,
    CostFactor,
    CoverageServiceState,
    GoalRelation,
    PrerequisiteState,
    ReadinessLevel,
    ScheduleAuthority,
)
from elc.planner.ledger import LedgerReadings, PlanningLedger
from elc.planner.scope import (
    ConversationPriorityView,
    ScopeResolution,
    interruption_cost_band_of,
    resolve_user_intent_scope,
)
from elc.planner.supply import (
    LearnerStatePort,
    PrerequisiteOutcome,
    PrerequisitePort,
    ReadinessPort,
    prerequisite_state_of,
    readiness_of_target,
)
from elc.planner.types import (
    InitiativeClass,
    LearningIntent,
    TargetMode,
)
from elc.platform.types import (
    Err,
    EvidenceModality,
    Ok,
    Result,
    TargetId,
)
from elc.scheduler.types import ReviewState
from elc.user_config.constraints import applies_to, entries_of_type
from elc.user_config.types import PlannerConstraintType, PlannerConstraintView

__all__ = [
    "ABSENT_READINGS",
    "BANDLESS_FACTORS",
    "CANDIDATE_SOURCES",
    "COMMON_FACES",
    "FACTOR_BAND_VALUES",
    "REFUSAL_GATES",
    "SCAFFOLD_BANDS",
    "SOURCE_AUTHORITY",
    "SOURCE_READINGS",
    "SOURCE_TRACK",
    "TRACK_A_SOURCES",
    "TRACK_B_SOURCES",
    "CandidateAuthority",
    "CandidateSupply",
    "CandidateSupplyError",
    "CandidateSupplyInputs",
    "OpportunityObservation",
    "ReviewViewPort",
    "SchedulePort",
    "SourceGap",
    "SourceReading",
    "SupplyTargetPort",
    "TargetRefusal",
    "TargetRowPort",
    "TargetSupplyPort",
    "TrackASource",
    "TrackBSource",
    "generate_candidates",
    "generate_track_a",
    "generate_track_b",
]


# -- §6's two lanes, word for word -------------------------------------------


class TrackASource(StrEnum):
    """docs/PRODUCT_CONTRACT.md §6 "Track A — Expression-driven", six words.

    "此刻什么与用户真实表达最相关。" The order is the document's, and it is
    this module's generation order too.
    """

    CURRENT_USER_ERROR = "CURRENT_USER_ERROR"
    EXPRESSION_NEED = "EXPRESSION_NEED"
    NATURAL_USE_EXPANSION = "NATURAL_USE_EXPANSION"
    PRAGMATIC_REGISTER_OPPORTUNITY = "PRAGMATIC_REGISTER_OPPORTUNITY"
    MANUAL_USER_REQUEST = "MANUAL_USER_REQUEST"
    CURRENT_CONTEXT_TRANSFER_OPPORTUNITY = (
        "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY"
    )


class TrackBSource(StrEnum):
    """docs/PRODUCT_CONTRACT.md §6 "Track B — Curriculum-driven", eight words.

    "长期什么不能一直没学。"
    """

    CONFIRMED_GAP = "CONFIRMED_GAP"
    SCHEDULED_REVIEW = "SCHEDULED_REVIEW"
    UNKNOWN_PROBE = "UNKNOWN_PROBE"
    TRANSFER_EXPANSION = "TRANSFER_EXPANSION"
    SUPPORT_WITHDRAWAL = "SUPPORT_WITHDRAWAL"
    CORE_COVERAGE = "CORE_COVERAGE"
    GOAL_SPECIFIC_TARGET = "GOAL_SPECIFIC_TARGET"
    COVERAGE_DEBT = "COVERAGE_DEBT"


TRACK_A_SOURCES: tuple[str, ...] = tuple(str(s) for s in TrackASource)
TRACK_B_SOURCES: tuple[str, ...] = tuple(str(s) for s in TrackBSource)

#: The fourteen source words in §6's order — Track A's six, then Track B's
#: eight. `generate_candidates` emits in exactly this order (each source's own
#: targets in the supply's order), so two runs of one world are byte-identical
#: and the ordering cannot depend on which lane was asked first.
CANDIDATE_SOURCES: tuple[str, ...] = TRACK_A_SOURCES + TRACK_B_SOURCES

#: Which lane a source belongs to ("A" | "B").
SOURCE_TRACK: Mapping[str, str] = {
    **{source: "A" for source in TRACK_A_SOURCES},
    **{source: "B" for source in TRACK_B_SOURCES},
}


class CandidateAuthority(StrEnum):
    """What a source needs before it can answer.

    Two families, and the distinction is the whole registration:

    - the **call faces** (``TARGET_SUPPLY`` / ``TARGET_ROW`` /
      ``CONTENT_READINESS`` / ``SCHEDULE_ROW`` / ``SCHEDULE_DECISION`` /
      ``LEARNER_STATE`` / ``TURN_OPPORTUNITY`` / ``CONSTRAINT_VIEW``) exist as
      read faces in this repository; a call that does not hold one gets a
      ``SourceGap`` saying so;
    - the **unlanded authorities** (``TRANSFER_POLICY`` / ``CORE_TIER`` /
      ``GOAL_PACK_MAPPING`` / ``PLANNING_LEDGER``) have no face anywhere yet, so
      the sources that read them gap on every call, with the reason naming what
      would have to land first.
    """

    TARGET_SUPPLY = "TARGET_SUPPLY"
    TARGET_ROW = "TARGET_ROW"
    CONTENT_READINESS = "CONTENT_READINESS"
    SCHEDULE_ROW = "SCHEDULE_ROW"
    SCHEDULE_VIEW = "SCHEDULE_VIEW"
    LEARNER_STATE = "LEARNER_STATE"
    TURN_OPPORTUNITY = "TURN_OPPORTUNITY"
    CONSTRAINT_VIEW = "CONSTRAINT_VIEW"
    TRANSFER_POLICY = "TRANSFER_POLICY"
    CORE_TIER = "CORE_TIER"
    GOAL_PACK_MAPPING = "GOAL_PACK_MAPPING"
    PLANNING_LEDGER = "PLANNING_LEDGER"


#: The faces every candidate needs, whatever its source (the target set, the
#: §11 row the identity comes from, the §8.1 level, and the §5.2 row the
#: ``schedule_urgency`` leg needs). A call missing one of these gaps *every*
#: source, which is why they are checked first.
COMMON_FACES: tuple[CandidateAuthority, ...] = (
    CandidateAuthority.TARGET_SUPPLY,
    CandidateAuthority.TARGET_ROW,
    CandidateAuthority.CONTENT_READINESS,
    CandidateAuthority.SCHEDULE_ROW,
)

#: The face each source reads **besides** :data:`COMMON_FACES`, or ``None`` for
#: a source whose own authority is already one of them. (``SCHEDULED_REVIEW``
#: still names the Scheduler's *decision*: a row is a different read from "is
#: this due at ``as_of``".)
SOURCE_AUTHORITY: Mapping[str, CandidateAuthority | None] = {
    "CURRENT_USER_ERROR": CandidateAuthority.TURN_OPPORTUNITY,
    "EXPRESSION_NEED": CandidateAuthority.TURN_OPPORTUNITY,
    "NATURAL_USE_EXPANSION": CandidateAuthority.TURN_OPPORTUNITY,
    "PRAGMATIC_REGISTER_OPPORTUNITY": CandidateAuthority.TURN_OPPORTUNITY,
    "MANUAL_USER_REQUEST": CandidateAuthority.CONSTRAINT_VIEW,
    "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY": CandidateAuthority.TURN_OPPORTUNITY,
    "CONFIRMED_GAP": CandidateAuthority.LEARNER_STATE,
    "SCHEDULED_REVIEW": CandidateAuthority.SCHEDULE_VIEW,
    "UNKNOWN_PROBE": CandidateAuthority.LEARNER_STATE,
    "TRANSFER_EXPANSION": CandidateAuthority.TRANSFER_POLICY,
    "SUPPORT_WITHDRAWAL": CandidateAuthority.LEARNER_STATE,
    "CORE_COVERAGE": CandidateAuthority.CORE_TIER,
    "GOAL_SPECIFIC_TARGET": CandidateAuthority.GOAL_PACK_MAPPING,
    "COVERAGE_DEBT": CandidateAuthority.PLANNING_LEDGER,
}

#: One line per unlanded authority — the reason a source that reads it gaps on
#: every call, whatever the caller holds.
UNLANDED_AUTHORITIES: Mapping[CandidateAuthority, str] = {
    CandidateAuthority.TRANSFER_POLICY: (
        "no transfer policy: D-INV-010 gives the Planner the transfer-need"
        " decision, but nothing answers which target transfers where — the"
        " §11 state carries a transfer dimension and band and no face says"
        " which modality or context a target should move to, and V1's modality"
        " pair (TEXT_PRODUCTION / TEXT_COMPREHENSION) has no transfer rule"
    ),
    CandidateAuthority.CORE_TIER: (
        "no core tier: docs/DOMAIN_MODEL.md §7 gives Curriculum a core tier"
        " and the registry's four columns carry none — the corpus declares no"
        " core capability, so CORE_COVERAGE would be a coverage claim about a"
        " tier nobody published"
    ),
    CandidateAuthority.GOAL_PACK_MAPPING: (
        "no Goal/Assessment pack mapping: IMPLEMENTATION_PLAN §7 line 340"
        " lists it and it is not built (P7-0 registers the same absence on its"
        " own goal leg), so no assessment target can be turned into a teaching"
        " target"
    ),
    CandidateAuthority.PLANNING_LEDGER: (
        "no PlanningLedger view for this call: the ledger is durable since"
        " P8-3 (migration 0016's three tables behind elc.planner.ledger_store),"
        " but this caller handed in no view of it — and no shipped producer"
        " writes exposure or accrual facts yet (the delivery path is p8-4's),"
        " so nothing has assembled one either"
    ),
}


# -- BF-02 §6's reference bands, and the neutral reading ----------------------


def _bands(**values: float) -> dict[str, float]:
    """One factor's band ladder, in the asset's declaration order."""

    return dict(values)


#: BF-02 §6's ``reference_factor_bands``, factor name → band word → number,
#: verbatim from ``behavioral_baselines/planner/
#: planner_reference_profile_v1_1.json``. **Reference values, not frozen ones**
#: (BF-02 §21: the weights, thresholds and normalization-band numbers are
#: "reference defaults and empirically calibratable"), which is why this cut's
#: suite extracts the asset and compares every number below rather than
#: trusting the transcription.
FACTOR_BAND_VALUES: Mapping[str, Mapping[str, float]] = {
    "learning_need": _bands(
        NONE=0.0, LOW=0.25, MODERATE=0.5, HIGH=0.75, CONFIRMED_GAP=1.0
    ),
    "uncertainty_reduction": _bands(
        NONE=0.0, LOW=0.25, MEDIUM=0.5, HIGH=0.75, UNKNOWN_OR_CONFLICTED=1.0
    ),
    "curriculum_value": _bands(
        MINOR=0.25, SUPPORTING=0.5, IMPORTANT=0.75, CORE=1.0
    ),
    "schedule_urgency": _bands(
        NOT_SCHEDULED=0.0, UPCOMING=0.25, DUE=0.75, OVERDUE=1.0
    ),
    "context_fit": _bands(
        NONE=0.0, LOW=0.25, MEDIUM=0.5, HIGH=0.75, DIRECT=1.0
    ),
    "personal_relevance": _bands(
        NONE=0.0, RELEVANT=0.5, RECURRING=0.75, CURRENT_EXPRESSION=1.0
    ),
    "transfer_value": _bands(
        NONE=0.0, LOW=0.25, MEDIUM=0.5, HIGH=0.75, DIRECT_OPPORTUNITY=1.0
    ),
    "opportunity_expiry": _bands(
        PERSISTENT=0.0, SESSION=0.25, NEXT_TURN=0.75, THIS_TURN=1.0
    ),
    "interruption_cost": _bands(
        LOW=0.1, NORMAL=0.35, HIGH=0.75, PROTECTED=1.0
    ),
    "cognitive_load": _bands(LOW=0.2, MEDIUM=0.5, HIGH=0.8, OVERLOAD=1.0),
    "overexposure": _bands(
        NONE=0.0, LOW=0.25, MEDIUM=0.5, HIGH=0.75, SATURATED=1.0
    ),
    "support_cost": _bands(
        NONE=0.0, LOW=0.25, MEDIUM=0.5, HIGH=0.75, VERY_HIGH=1.0
    ),
    "user_resistance": _bands(
        NONE=0.0, RECENT_SKIP=0.35, REPEATED_SKIP=0.75, SOFT_RESISTANCE=1.0
    ),
    "communicative_impact": _bands(
        NONE=0.0, LOW=0.1, MEDIUM=0.5, HIGH=0.8, BLOCKING=1.0
    ),
}

#: The two factors the frozen asset gives **no band**: ``goal_relevance`` is
#: assembled from the Goal/Assessment pack mapping (not built) and
#: ``coverage_debt`` from the PlanningLedger (p7-3's). Their readings are
#: literals, and :func:`_resolve` refuses a literal for every other factor, so
#: "this number came from a band" is a checked property of the table.
BANDLESS_FACTORS: tuple[str, ...] = ("goal_relevance", "coverage_debt")

#: The neutral reading: what a source that says nothing about a factor gets.
#: Benefit factors drop to their lowest band (``0.0`` where the ladder has a
#: zero), and the two cost ladders that have no zero band drop to their lowest
#: band instead — BF-02 §6's ``interruption_cost`` starts at ``LOW`` (0.1) and
#: ``cognitive_load`` at ``LOW`` (0.2), so a neutral candidate is cheap *and
#: priced*, never free. ``curriculum_value`` likewise starts at ``MINOR``
#: (0.25): the ladder has no zero, so "no curriculum claim" is its floor.
ABSENT_READINGS: Mapping[str, str | float] = {
    "learning_need": "NONE",
    "uncertainty_reduction": "NONE",
    "curriculum_value": "MINOR",
    "goal_relevance": 0.0,
    "schedule_urgency": "NOT_SCHEDULED",
    "context_fit": "NONE",
    "personal_relevance": "NONE",
    "transfer_value": "NONE",
    "coverage_debt": 0.0,
    "opportunity_expiry": "PERSISTENT",
    "communicative_impact": "NONE",
    "interruption_cost": "LOW",
    "cognitive_load": "LOW",
    "overexposure": "NONE",
    "support_cost": "NONE",
    "user_resistance": "NONE",
}

#: The bands a scaffolded candidate's two cost factors are raised to (BF-02
#: §11: "scaffold 不能被当成'免费 prerequisite'", with reference floors
#: ``support_cost >= .25`` / ``cognitive_load >= .20``). ``MEDIUM`` is what the
#: scaffold *reading* costs — the reference floors are minimums, not targets,
#: and the kernel refuses a scaffolded candidate below them.
SCAFFOLD_BANDS: Mapping[str, str] = {
    "support_cost": "MEDIUM",
    "cognitive_load": "MEDIUM",
}


# -- one row per source ------------------------------------------------------


@dataclass(frozen=True)
class SourceReading:
    """What one source means, and how it prices it.

    ``mode`` / ``intent`` are ``None`` when the §11 target row supplies them —
    the *practice* sources teach the target as authored, so their identity comes
    from the content row (``RESOURCE_PRACTICE`` / ``CAPABILITY_PRACTICE`` and the
    row's own intent) rather than from a second opinion here. A source whose
    semantics name a different intent (a gap is developed, support is withdrawn,
    a probe probes, a review consolidates, a transfer transfers) carries it, and
    the two mode-owning sources carry both.

    ``benefit`` / ``cost`` are the bands the source moves; a factor absent from
    them keeps its :data:`ABSENT_READINGS` value. ``basis`` and ``revisit`` are
    mandatory on purpose: a number without a reason is what this table exists to
    prevent.

    There is no ``binding_class`` field: the opportunity's binding **is** the
    source (see :func:`_canonical_key`), so one source's proposals can never
    collide with another's on BF-02 §4's five-field key — a field that restated
    the source would be a second place for the two to disagree.
    """

    source: str
    track: str
    mode: TargetMode | None
    intent: LearningIntent | None
    initiative: InitiativeClass
    benefit: Mapping[BenefitFactor, str | float]
    cost: Mapping[CostFactor, str | float]
    basis: str
    revisit: str


_B = BenefitFactor
_C = CostFactor

#: The fourteen rows, in §6's order. Every number resolves through
#: :data:`FACTOR_BAND_VALUES`; the basis names the frozen precedent where one
#: exists (the golden scenarios' own candidates for the same origin) and says
#: "declared" where the pairing is this cut's.
SOURCE_READINGS: Mapping[str, SourceReading] = {
    # -- Track A -----------------------------------------------------------
    "CURRENT_USER_ERROR": SourceReading(
        source="CURRENT_USER_ERROR",
        track="A",
        mode=None,
        intent=LearningIntent.DEVELOP,
        initiative=InitiativeClass.REACTIVE,
        benefit={
            _B.LEARNING_NEED: "HIGH",
            _B.CONTEXT_FIT: "DIRECT",
            _B.PERSONAL_RELEVANCE: "CURRENT_EXPRESSION",
            _B.OPPORTUNITY_EXPIRY: "THIS_TURN",
            _B.COMMUNICATIVE_IMPACT: "MEDIUM",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "LOW"},
        basis=(
            "declared, on BF-02 §6's own example: the band answers '当前问题对"
            "用户正在表达的意思造成多大损害', where 'wrong negation changing"
            " intended meaning' outranks 'minor article error' — so the source"
            " moves it, and with no severity authority in V1 the mid band is"
            " declared. learning_need stops at HIGH because the top band's word"
            " is the estimator's own flag (BF-01 §25/§26) and this source reads"
            " no flag: GS03's candidate carries CURRENT_USER_ERROR *and*"
            " CONFIRMED_GAP and prices learning_need at the top band for the"
            " gap, not for the error. The reactive pricing (LOW interruption,"
            " THIS_TURN expiry, DIRECT context fit, CURRENT_EXPRESSION"
            " relevance) is what '此刻什么与用户真实表达最相关' means"
        ),
        revisit=(
            "the error-detection cut lands a severity reading (BF-02 §10's R4"
            " detection policy) → communicative_impact comes from it rather"
            " than from the declared mid band"
        ),
    ),
    "EXPRESSION_NEED": SourceReading(
        source="EXPRESSION_NEED",
        track="A",
        mode=None,
        intent=LearningIntent.ESTABLISH,
        initiative=InitiativeClass.REACTIVE,
        benefit={
            _B.LEARNING_NEED: "HIGH",
            _B.CONTEXT_FIT: "DIRECT",
            _B.PERSONAL_RELEVANCE: "CURRENT_EXPRESSION",
            _B.OPPORTUNITY_EXPIRY: "THIS_TURN",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "LOW"},
        basis=(
            "declared: the user needed a form to say something and does not"
            " have it, which is a need *and* a current-expression relevance"
            " (DATA_MODEL §10's ExpressionNeed record names personal_relevance"
            " and recurrence_count as its own columns — this row is the"
            " declared stand-in until that table and its reader land)."
            " ESTABLISH is §11's intent for 'this form is not there yet'"
        ),
        revisit=(
            "DATA_MODEL §10's ExpressionNeed table lands with a read face →"
            " its personal_relevance / recurrence_count columns feed this row"
            " (and the generator's ESTABLISH reading is re-read against the"
            " record's status)"
        ),
    ),
    "NATURAL_USE_EXPANSION": SourceReading(
        source="NATURAL_USE_EXPANSION",
        track="A",
        mode=None,
        intent=LearningIntent.EXPAND_REPERTOIRE,
        initiative=InitiativeClass.OPPORTUNISTIC,
        benefit={
            _B.LEARNING_NEED: "MODERATE",
            _B.TRANSFER_VALUE: "MEDIUM",
            _B.CONTEXT_FIT: "HIGH",
            _B.OPPORTUNITY_EXPIRY: "SESSION",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "MEDIUM"},
        basis=(
            "declared: the user already reached for a form naturally, so the"
            " need is moderate and the value is in widening the repertoire"
            " around it (EXPAND_REPERTOIRE, §11's own intent word). The"
            " opportunity outlives the turn but not the session, and new"
            " material costs a MEDIUM load where the current form did not"
        ),
        revisit=(
            "a cut lands the expansion reading (which related forms exist — a"
            " curriculum-side repertoire face, or the approved links P5-R"
            " gated) → the target set changes; the bands stay this cut's"
            " declaration until one does"
        ),
    ),
    "PRAGMATIC_REGISTER_OPPORTUNITY": SourceReading(
        source="PRAGMATIC_REGISTER_OPPORTUNITY",
        track="A",
        mode=None,
        intent=LearningIntent.DEVELOP,
        initiative=InitiativeClass.OPPORTUNISTIC,
        benefit={
            _B.CONTEXT_FIT: "LOW",
            _B.PERSONAL_RELEVANCE: "NONE",
            _B.COMMUNICATIVE_IMPACT: "LOW",
            _B.OPPORTUNITY_EXPIRY: "THIS_TURN",
        },
        cost={_C.INTERRUPTION_COST: "NORMAL", _C.COGNITIVE_LOAD: "LOW"},
        basis=(
            "declared, against GS01's own candidate: the golden scenario"
            " 'Natural chat with no worthwhile teaching' is exactly this origin"
            " and its expected outcome is NO_TARGET — so the row is priced as"
            " the discretionary case it is (low context fit, no personal"
            " relevance, a LOW communicative impact, no learning need), which"
            " under the reference BALANCED profile lands well under §14's"
            " automatic threshold. The load is a NORMAL interruption because a"
            " register remark is an interjection into a flow that was going"
            " somewhere else"
        ),
        revisit=(
            "the golden scenarios are retired or a register-opportunity"
            " reading lands (which register the current context admits, and how"
            " far the user is from it) → the bands are re-read against it"
        ),
    ),
    "MANUAL_USER_REQUEST": SourceReading(
        source="MANUAL_USER_REQUEST",
        track="A",
        mode=None,
        intent=None,
        initiative=InitiativeClass.REACTIVE,
        benefit={
            _B.LEARNING_NEED: "HIGH",
            _B.CONTEXT_FIT: "DIRECT",
            _B.PERSONAL_RELEVANCE: "CURRENT_EXPRESSION",
            _B.OPPORTUNITY_EXPIRY: "SESSION",
        },
        cost={_C.INTERRUPTION_COST: "HIGH", _C.COGNITIVE_LOAD: "LOW"},
        basis=(
            "declared, on §9's own word: the entry this source reads is"
            " MANUAL_FOCUS ('focus on this manually' — the user's durable act,"
            " not an inference), so the candidate is user_initiated and"
            " request_aligned and §14's threshold does not gate it (BF-02:"
            " '显式 user learning request … 不使用 automatic interruption"
            " threshold'). The session binding is §9's own scope vocabulary"
            " (THIS_SESSION / UNTIL_DATE / UNTIL_USER_REENABLES — a manual"
            " focus is not a one-turn event), and the golden scenarios price"
            " manual candidates at two different numbers rather than one band"
            " — GS05/GS08 at .8 and GS09–GS12 at .0 — so the HIGH band is this"
            " cut's declaration and not a quotation. The flow is the user's,"
            " which BF-02 §17 keeps a cost rather than an exclusion"
        ),
        revisit=(
            "§9 gains a priority column, or a turn-scoped request producer"
            " lands → BF-02 §8's request_priority distinction becomes readable"
            " and the binding class is re-read"
        ),
    ),
    "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY": SourceReading(
        source="CURRENT_CONTEXT_TRANSFER_OPPORTUNITY",
        track="A",
        mode=TargetMode.TRANSFER,
        intent=LearningIntent.TRANSFER,
        initiative=InitiativeClass.OPPORTUNISTIC,
        benefit={
            _B.LEARNING_NEED: "MODERATE",
            _B.TRANSFER_VALUE: "DIRECT_OPPORTUNITY",
            _B.CONTEXT_FIT: "DIRECT",
            _B.OPPORTUNITY_EXPIRY: "THIS_TURN",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "MEDIUM"},
        basis=(
            "declared: the name is the reading — the current context is the"
            " transfer opportunity (CURRENT + CONTEXT + TRANSFER), so"
            " transfer_value takes the ladder's DIRECT_OPPORTUNITY band and the"
            " expiry is the turn. §11's TRANSFER mode pairs with TRANSFER"
            " intent, and that pairing is the only one the mode admits"
        ),
        revisit=(
            "a ContextOpportunitySet producer lands (DOMAIN_MODEL §10's own"
            " input authority) → this row is re-read against what that artifact"
            " actually carries"
        ),
    ),
    # -- Track B -----------------------------------------------------------
    "CONFIRMED_GAP": SourceReading(
        source="CONFIRMED_GAP",
        track="B",
        mode=None,
        intent=LearningIntent.DEVELOP,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "CONFIRMED_GAP",
            _B.CURRICULUM_VALUE: "SUPPORTING",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={
            _C.INTERRUPTION_COST: "NORMAL",
            _C.COGNITIVE_LOAD: "MEDIUM",
            _C.SUPPORT_COST: "LOW",
        },
        basis=(
            "quoted twice over: the source *is* one of BF-01 §25's learning"
            " flags (with §26's reference thresholds — estimate ≤ .35 ∧"
            " confidence ≥ .65 — behind it), and the factor band it moves is"
            " the ladder's own CONFIRMED_GAP word, so the number is the flag"
            " the estimator already published rather than a second judgement."
            " GS03/GS06 pair CONFIRMED_GAP with DEVELOP and price"
            " learning_need at the ladder's own top band (1.0); GS04 carries"
            " the same origin beside SUPPORT_WITHDRAWAL and prices .8, which"
            " sits between the HIGH band (.75) and that top band. The gap does"
            " not expire this turn, which is why its expiry is PERSISTENT"
        ),
        revisit=(
            "the estimator's flags are re-laddered (BF-01 §25 is the frozen"
            " list) or a cut prices a confirmed gap differently → the band moves"
            " with the reference profile's version, per BF-02 §21"
        ),
    ),
    "SCHEDULED_REVIEW": SourceReading(
        source="SCHEDULED_REVIEW",
        track="B",
        mode=TargetMode.REVIEW,
        intent=LearningIntent.CONSOLIDATE,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "LOW",
            _B.CURRICULUM_VALUE: "SUPPORTING",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "LOW"},
        basis=(
            "declared, on GS23's own numbers: the golden scenario is this"
            " origin and its title is 'Strong-but-stale knowledge can produce"
            " low-cost retrieval review' — both cost factors sit at their"
            " lowest bands, and learning_need sits at the LOW band (.25, which"
            " is the golden's own number for it). §11's REVIEW mode pairs with"
            " CONSOLIDATE exactly, and the target is the one the Scheduler"
            " declared due; schedule_urgency is not written here at all (the"
            " §5.2 row owns it)"
        ),
        revisit=(
            "GS23 is retired or a review-cost reading lands (what a review"
            " attempt actually costs the flow) → the bands are re-read"
        ),
    ),
    "UNKNOWN_PROBE": SourceReading(
        source="UNKNOWN_PROBE",
        track="B",
        mode=TargetMode.PROBE,
        intent=LearningIntent.PROBE,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.UNCERTAINTY_REDUCTION: "HIGH",
            _B.CURRICULUM_VALUE: "IMPORTANT",
            _B.CONTEXT_FIT: "MEDIUM",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "LOW"},
        basis=(
            "declared, on GS21 ('Study-first may probe high-value unknown"
            " target'): the golden prices uncertainty_reduction at the top band"
            " and curriculum_value at CORE, and this row keeps the same"
            " direction one band down — a probe is worth what it can resolve,"
            " and nothing in this repository grades a corpus target CORE"
            " (CORE_COVERAGE's own registered gap). A probe is cheap: its whole"
            " shape is one small answer, so both cost factors sit at their"
            " lowest bands"
        ),
        revisit=(
            "a content-level or core-tier face lands (then curriculum_value can"
            " be read instead of declared), or BF-02's probe pricing is"
            " calibrated (BF-02 §21)"
        ),
    ),
    "TRANSFER_EXPANSION": SourceReading(
        source="TRANSFER_EXPANSION",
        track="B",
        mode=TargetMode.TRANSFER,
        intent=LearningIntent.TRANSFER,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "MODERATE",
            _B.TRANSFER_VALUE: "HIGH",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "MEDIUM"},
        basis=(
            "declared for a source this cut cannot run (its authority is"
            " registered unlanded): when a transfer reading lands, the shape is"
            " §11's TRANSFER mode with TRANSFER intent, a HIGH transfer_value"
            " and a standing expiry. The row exists so the vocabulary and the"
            " pricing are visible before the authority is"
        ),
        revisit=(
            "the transfer policy lands (D-INV-010's planner-side decision with"
            " a readable 'transfer where') → this row is re-read against it and"
            " the source moves out of the gap list"
        ),
    ),
    "SUPPORT_WITHDRAWAL": SourceReading(
        source="SUPPORT_WITHDRAWAL",
        track="B",
        mode=None,
        intent=LearningIntent.WITHDRAW_SUPPORT,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "HIGH",
            _B.CURRICULUM_VALUE: "SUPPORTING",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={
            _C.INTERRUPTION_COST: "LOW",
            _C.COGNITIVE_LOAD: "MEDIUM",
            _C.SUPPORT_COST: "MEDIUM",
        },
        basis=(
            "quoted and declared: the source reads BF-01 §25's SUPPORT_DEPENDENT"
            " flag, and §11's own intent word for it is WITHDRAW_SUPPORT"
            " (allowed for both practice modes). GS04 pairs the two and prices"
            " learning_need at .8 — the golden's own number, above the HIGH"
            " band (.75) and below the ladder's top (1.0), so no band word is"
            " quoted here. The *withdrawal* is where the cost sits — the"
            " attempt is the user's to make — so support_cost takes the MEDIUM"
            " band rather than the absent NONE"
        ),
        revisit=(
            "a cut prices the withdrawal attempt (how much support is being"
            " withdrawn, and what it costs to hold it back) → support_cost is"
            " read rather than declared"
        ),
    ),
    "CORE_COVERAGE": SourceReading(
        source="CORE_COVERAGE",
        track="B",
        mode=None,
        intent=LearningIntent.DEVELOP,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "MODERATE",
            _B.CURRICULUM_VALUE: "CORE",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "MEDIUM"},
        basis=(
            "declared for a source this cut cannot run: the name says what it"
            " would price — a core-tier target must not stay uncovered — and"
            " curriculum_value takes the ladder's top band for it. The row"
            " exists, and the source still gaps, because no core tier is"
            " published"
        ),
        revisit=(
            "Curriculum publishes a core tier (§7's own item) → the source runs"
            " over that tier and this row is re-read against it"
        ),
    ),
    "GOAL_SPECIFIC_TARGET": SourceReading(
        source="GOAL_SPECIFIC_TARGET",
        track="B",
        mode=None,
        intent=LearningIntent.DEVELOP,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "MODERATE",
            _B.CURRICULUM_VALUE: "IMPORTANT",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "MEDIUM"},
        basis=(
            "declared for a source this cut cannot run: a goal-specific target"
            " would carry its importance through curriculum_value, and"
            " goal_relevance stays at the declared literal 0.0 because the"
            " mapping that would fill it is the very authority this source is"
            " waiting for — a positive number here would claim the mapping P7-0"
            " registers as absent"
        ),
        revisit=(
            "the Goal/Assessment pack mapping lands → goal_relevance becomes an"
            " authority reading and this source runs"
        ),
    ),
    "COVERAGE_DEBT": SourceReading(
        source="COVERAGE_DEBT",
        track="B",
        mode=None,
        intent=LearningIntent.DEVELOP,
        initiative=InitiativeClass.PROACTIVE,
        benefit={
            _B.LEARNING_NEED: "MODERATE",
            _B.CURRICULUM_VALUE: "CORE",
            _B.COVERAGE_DEBT: 1.0,
            _B.CONTEXT_FIT: "MEDIUM",
            _B.OPPORTUNITY_EXPIRY: "PERSISTENT",
        },
        cost={_C.INTERRUPTION_COST: "LOW", _C.COGNITIVE_LOAD: "MEDIUM"},
        basis=(
            "declared on GS20's own candidate: the golden's 'debt' candidate —"
            " the one §13's starvation safeguard exists to surface at a natural"
            " break — prices curriculum_value at CORE and coverage_debt at 1.0"
            " (the factor has no band in the reference asset, which is why the"
            " literal is legal here and only here). That literal is the reading"
            " of a call that hands in **no** ledger; a call that hands one in"
            " reads the obligation's own debt_value instead (elc.planner."
            "ledger), and coverage_service_state is read from the same"
            " obligation — never computed here"
        ),
        revisit=(
            "read: p7-3 landed the PlanningLedger and CoverageDebt, so this"
            " source runs whenever a caller hands a ledger view in and the row's"
            " literal 1.0 is now only the no-ledger reading. Revisit: a"
            " calibrated debt scale lands (the ledger declares [0, 1]), or"
            " GS20/S12 are retired"
        ),
    ),
}


# -- the caller's inputs ------------------------------------------------------


@dataclass(frozen=True)
class OpportunityObservation:
    """RA §4 step 3's "Teaching opportunity proposal", one turn's worth.

    **No producer is landed in this repository** — the artifact is listed in
    RUNTIME_ARCHITECTURE §4 step 3 and no cut records one — which is why this
    cut declares the shape instead of reading it, and why a call that does not
    hand one in gets a :class:`SourceGap` per Track A source rather than an
    invented observation. The five fields are one per Track A source that needs
    a turn-scoped fact; each carries the target ids the turn produced, and
    nothing else — the pricing is the source rows' and the identity is the
    content rows'.

    ``MANUAL_USER_REQUEST`` is deliberately **not** here: the user's own
    durable §9 act is a better authority than an inferred turn reading, and the
    generator reads it from the constraint view.
    """

    current_user_errors: tuple[str, ...] = ()
    expression_needs: tuple[str, ...] = ()
    natural_use_expansions: tuple[str, ...] = ()
    pragmatic_register_opportunities: tuple[str, ...] = ()
    current_context_transfers: tuple[str, ...] = ()


#: Which observation field each Track A source reads.
OBSERVATION_FIELD: Mapping[str, str] = {
    "CURRENT_USER_ERROR": "current_user_errors",
    "EXPRESSION_NEED": "expression_needs",
    "NATURAL_USE_EXPANSION": "natural_use_expansions",
    "PRAGMATIC_REGISTER_OPPORTUNITY": "pragmatic_register_opportunities",
    "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY": "current_context_transfers",
}


class SupplyTargetPort(Protocol):
    """One supply-eligible target, as the supply face names it.

    Two fields: the §11 kind and the artifact id. Satisfied structurally by
    :class:`elc.learning.target_resolution.TargetSupplyFacts` — the record
    :class:`elc.learning.silent_evidence.ContentBackedTargetSupply` already
    answers — so the Planner consumes the face the chat leg uses rather than a
    second supply reader. Its §24.5 payload fields (canonical forms, slots) are
    deliberately not declared: a *candidate* does not need them.
    """

    target_type: str
    target_id: str


class TargetSupplyPort(Protocol):
    """The supply set: ``facts()`` → every §24.11-eligible target.

    The same method name and result shape as the landed face, so
    ``ContentBackedTargetSupply`` satisfies this port unchanged (pinned by
    test). The §24.11 filter is that face's; this module never re-applies it,
    and therefore never invents a candidate for excluded content ("excluded ≠
    deleted": the target stays resolvable, it just is not supply).
    """

    def facts(self) -> Result[tuple[SupplyTargetPort, ...]]:
        ...


class TargetRowPort(Protocol):
    """The §11 target row a candidate's identity comes from.

    Satisfied structurally by
    :class:`elc.curriculum.store.CurriculumContentStore.get_target`. Its four
    facts are the identity the generator reads — mode, intent, modality — and
    the entity id.
    """

    def get_target(self, entity_id: str) -> Result[ContentTargetView]:
        ...


class ReviewRowPort(Protocol):
    """A §5.2 row as the review source reads it.

    Wider than P7-0's :class:`~elc.planner.feature_assembly.ScheduleRowPort` on
    purpose and for the same declared reason: the *candidate* needs the row's
    own key (target kind, target id, modality) as well as the three factor
    columns, while the factor leg needs only the three. A port that named
    fields a reader does not consume is what both declarations avoid.
    """

    target_type: str
    target_id: TargetId
    evidence_modality: EvidenceModality
    review_state: ReviewState
    review_urgency: float | None
    source_learning_watermark: str


class ReviewViewPort(Protocol):
    """The §10 view, as far as this module reads it: the two due buckets.

    The buckets are the Scheduler's **own** due classification
    (:meth:`elc.scheduler.controller.SchedulerController.get_schedule_view`,
    produced by P6-2 with the same ruler ``is_review_due`` uses), which is why
    the review source reads membership instead of re-deciding due-ness: D-INV-009
    keeps the decision on the Scheduler's side, and the view *is* that side's
    answer. Only ``due_items`` / ``overdue_items`` are declared: a review
    candidate exists when the Scheduler says due or overdue, and the view's
    third bucket (``upcoming``) is P7-0's urgency leg rather than this source's
    condition, so naming it would declare a read this module does not make.
    ``schedule_version`` and ``as_of`` are not declared either — the context
    record is what dates this cycle (P7-0's ``schedule_authority`` leg), and a
    port that named them would invite a second reading of staleness.
    """

    due_items: Sequence[ReviewRowPort]
    overdue_items: Sequence[ReviewRowPort]


class SchedulePort(Protocol):
    """The two Scheduler reads this module consumes: the row and the §10 view.

    Satisfied structurally by :class:`elc.scheduler.controller.SchedulerController`
    (``get_schedule_item`` / ``get_schedule_view``) — the same two faces P7-0
    froze as the Planner's Scheduler boundary. The per-target row is what makes
    ``schedule_urgency`` the Scheduler's own number; the view is what makes
    "which targets the Scheduler declared due" the Scheduler's own answer
    rather than a second derivation from a row this module holds.
    """

    def get_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[ReviewRowPort | None]:
        ...

    def get_schedule_view(self, as_of: str) -> Result[ReviewViewPort]:
        ...


@dataclass(frozen=True)
class CandidateSupplyInputs:
    """Everything a call hands the generators — every leg optional.

    Each optional leg is one authority: the absent ones produce
    :class:`SourceGap` entries naming what is missing, which is the whole
    difference between "no candidate because the world says so" and "no
    candidate because nobody could be asked". ``as_of`` is the DecisionCycle's
    instant (the one a §10 view would be classified at and the one the review
    decision is asked about); it is deliberately not read off a clock.

    ``ledger`` is P7-3's leg and it is **appended** to the surface this cut
    landed, so every construction that existed before it keeps its meaning and
    a call that hands in none behaves exactly as it did (module docstring, "the
    ledger leg"). What it turns on is the ``PLANNING_LEDGER`` authority: the
    ``COVERAGE_DEBT`` source runs, and three readings
    (``overexposure`` / ``coverage_debt`` / ``coverage_service_state``) come
    from the ledger instead of from the absent literals.
    """

    as_of: str
    targets: TargetSupplyPort | None = None
    target_rows: TargetRowPort | None = None
    readiness: ReadinessPort | None = None
    prerequisites: PrerequisitePort | None = None
    learner_state: LearnerStatePort | None = None
    schedule: SchedulePort | None = None
    constraints: PlannerConstraintView | None = None
    priority: ConversationPriorityView | None = None
    observation: OpportunityObservation | None = None
    ledger: PlanningLedger | None = None


@dataclass(frozen=True)
class SourceGap:
    """One source that could not run, and the authority it was missing.

    "Could not run" is not "found nothing": a source whose condition is simply
    false for every target (no target is due) produces no gap — the Scheduler
    answered, the answer was "not due" — while a source with no authority to
    ask produces one line here for the whole call.
    """

    source: str
    authority: CandidateAuthority
    reason: str


@dataclass(frozen=True)
class TargetRefusal:
    """One target the generator will not build a candidate for, and why.

    ``gate`` is one of :data:`REFUSAL_GATES`; ``source`` is ``None`` when the
    refusal happened before any source ran (the target's own legs) and the
    source word when one source named a target the supply does not carry.
    """

    target_id: str
    gate: str
    reason: str
    source: str | None = None


#: The refusal gates, one word per check that can stop a target before a
#: candidate exists: the §11 row, the V1 modality pair, the §8.1 ladder, the
#: §5.2 row, the mode/intent pairing BF-02 §11 pins, and "a source named a
#: target the supply set does not carry".
REFUSAL_GATES: tuple[str, ...] = (
    "TARGET_ROW",
    "MODALITY",
    "CONTENT_READINESS",
    "SCHEDULE_ROW",
    "MODE_INTENT_PAIR",
    "OUTSIDE_SUPPLY",
)


@dataclass(frozen=True)
class CandidateSupply:
    """One call's proposals plus everything that stopped one from existing.

    ``readiness`` is the §8.1 answer for every target the call read, including
    the ``None`` answers, keyed by target id — the supply side's own read, so
    nothing downstream has to judge a level twice. Two ways to hand it to P7-0's
    :func:`~elc.planner.feature_assembly.assemble_feature_authority`, and the
    difference is stated rather than left to the caller:

    - :attr:`candidate_readiness` is the subset for the targets that became
      candidates, which is the scope P7-0's ``CURRICULUM_READINESS`` leg names
      ("no content level is reachable for N *candidate(s)* the caller holds") —
      a cycle plans over candidates, and an ungraded target that no source could
      propose is not one;
    - the full ``readiness`` mapping is the broader truth about the world this
      cycle looked at, and feeding *it* makes the assembly INCOMPLETE whenever
      any read target is ungraded. That is not a bug: it is the coarse reading
      ("the level supply is not complete"), and a caller that wants it gets the
      honest DEGRADED rather than a decision over a supply it cannot vouch for.

    ``scope`` is the §12 resolution the same pass made, so a caller can build a
    :class:`~elc.planner.kernel.PlanningInput` from one call's answers without
    resolving the scope a second time (two resolutions could disagree; one
    cannot).
    """

    proposals: tuple[CandidateProposal, ...]
    gaps: tuple[SourceGap, ...]
    refusals: tuple[TargetRefusal, ...]
    readiness: Mapping[str, str | None]
    scope: ScopeResolution

    def proposals_of(self, source: str) -> tuple[CandidateProposal, ...]:
        """The proposals one source produced, in emission order."""

        return tuple(
            proposal
            for proposal in self.proposals
            if source in proposal.origins
        )

    @property
    def candidate_readiness(self) -> Mapping[str, str | None]:
        """The §8.1 levels of the targets that became candidates.

        The scope P7-0's ``CURRICULUM_READINESS`` leg names (class docstring):
        one entry per candidate target, each a real ladder word — a candidate
        only exists for a target whose level was read, so a ``None`` can only
        appear for a target that *also* produced no candidate, which is why the
        property drops those entries instead of handing P7-0 a key it would have
        to interpret.
        """

        targets = {proposal.focus_target for proposal in self.proposals}
        return {
            target: self.readiness[target]
            for target in sorted(targets)
            if target in self.readiness
        }

    @property
    def sources_answered(self) -> tuple[str, ...]:
        """The sources that produced at least one proposal, in §6's order."""

        produced = {origin for p in self.proposals for origin in p.origins}
        return tuple(source for source in CANDIDATE_SOURCES if source in produced)


class CandidateSupplyError(ValueError):
    """A supply-side contract breach: the caller's inputs disagree with §6.

    Three shapes reach it, all of them the *caller's* data rather than the
    world's: a reading that names a band the reference ladder does not carry, a
    literal number for a factor that has a band ladder, and a reading whose
    factor is neither (a typo in the table would otherwise price a candidate
    silently). It is a ``ValueError`` so a caller can catch one class, and it is
    raised before any proposal exists.
    """


# -- the per-target context ---------------------------------------------------


@dataclass(frozen=True)
class _TargetContext:
    """One target's legs, read once and shared by every source.

    ``level`` is non-optional on purpose: a target whose §8.1 answer is "no
    level" never gets a context (that is the refusal), so the type carries the
    fact that the candidate's ``content_readiness`` field can always be filled
    with a real ladder word.

    ``ledger`` is the same read once per target, and it is ``None`` exactly when
    the call handed in no ledger at all — so "the ledger says nothing about this
    target" (a :class:`LedgerReadings` with ``obligation=None``) and "there is
    no ledger" stay two different facts. Both keep the absent literals, but only
    the second is the no-ledger reading the module's docstring registers.
    """

    target_type: str
    target_id: str
    row: ContentTargetView
    modality: EvidenceModality
    level: ReadinessLevel
    readiness_reasons: tuple[str, ...]
    prerequisites: PrerequisiteOutcome
    schedule_row: ReviewRowPort
    flags: tuple[str, ...]
    auto_suppressed: bool
    review_suppressed: bool
    ledger: LedgerReadings | None = None


def _resolve(factor: str, value: str | float) -> float:
    """One reading, resolved through the frozen band ladder.

    A band word must exist in :data:`FACTOR_BAND_VALUES`; a literal must be a
    factor the ladder does not carry (:data:`BANDLESS_FACTORS`). Everything else
    is a :class:`CandidateSupplyError` — the table is checked, not trusted.
    """

    if isinstance(value, str):
        bands = FACTOR_BAND_VALUES.get(factor)
        if bands is None or value not in bands:
            raise CandidateSupplyError(
                f"{factor}: {value!r} is not a band of this factor"
                " (BF-02 §6's reference_factor_bands)"
            )
        return bands[value]
    if factor not in BANDLESS_FACTORS:
        raise CandidateSupplyError(
            f"{factor}: a literal number is only legal for a factor with no"
            f" band ladder ({', '.join(BANDLESS_FACTORS)}), and this one has"
            " one — the reading must name a band"
        )
    return float(value)


def _declared_vector(
    reading: SourceReading,
    ctx: _TargetContext,
    inputs: CandidateSupplyInputs,
    scaffolded: bool,
) -> tuple[dict[BenefitFactor, float], dict[CostFactor, float]]:
    """The complete declared vector BF-02 §20 requires.

    Four layers, in order: the neutral reading, the source's own bands, the
    ledger leg when the call handed a ledger in, and the two legs that are
    *facts about this candidate* rather than readings — ``schedule_urgency``
    (the §5.2 row's own answer, through P7-0's conversion) and the scaffold
    floors when the prerequisite outcome is one BF-02 §11 prices. The ledger
    sits before the schedule leg because the two move different factors and the
    order between them is therefore immaterial; it sits after the source's own
    bands because a ledger reading **replaces** a declared one (module
    docstring, "the ledger leg").
    """

    benefit: dict[BenefitFactor, float] = {}
    for benefit_factor in BenefitFactor:
        benefit[benefit_factor] = _resolve(
            benefit_factor.value,
            reading.benefit.get(
                benefit_factor, ABSENT_READINGS[benefit_factor.value]
            ),
        )
    cost: dict[CostFactor, float] = {}
    for cost_factor in CostFactor:
        cost[cost_factor] = _resolve(
            cost_factor.value,
            reading.cost.get(cost_factor, ABSENT_READINGS[cost_factor.value]),
        )

    if ctx.ledger is not None:
        # every candidate reads its target's own exposure, whatever proposed it
        cost[CostFactor.OVEREXPOSURE] = _resolve(
            CostFactor.OVEREXPOSURE.value, ctx.ledger.overexposure.band
        )
        if reading.source == "COVERAGE_DEBT":
            obligation = ctx.ledger.obligation
            if obligation is None:
                raise CandidateSupplyError(
                    f"{ctx.target_id}: a COVERAGE_DEBT candidate exists only"
                    " for an obligation the ledger carries, and this target has"
                    " none — the source's target list and the ledger's"
                    " obligations are the same fact, so this is a caller's"
                    " ledger disagreeing with itself"
                )
            benefit[BenefitFactor.COVERAGE_DEBT] = _resolve(
                BenefitFactor.COVERAGE_DEBT.value, obligation.debt_value
            )

    schedule = schedule_urgency_of(ctx.schedule_row, ScheduleAuthority.CURRENT)
    if schedule is None:
        raise CandidateSupplyError(
            f"{ctx.target_id}: the §5.2 row answered no schedule_urgency — the"
            " generator carries a row precisely so this factor is the"
            " Scheduler's number; a row that answers nothing is a row the"
            " kernel would gap on"
        )
    benefit[BenefitFactor.SCHEDULE_URGENCY] = schedule

    band = interruption_cost_band_of(inputs.priority)
    if band is not None:
        cost[CostFactor.INTERRUPTION_COST] = _resolve(
            CostFactor.INTERRUPTION_COST.value, band
        )

    if scaffolded:
        for name, floor in (
            (CostFactor.SUPPORT_COST, SCAFFOLD_MIN_SUPPORT_COST),
            (CostFactor.COGNITIVE_LOAD, SCAFFOLD_MIN_COGNITIVE_LOAD),
        ):
            raised = _resolve(name.value, SCAFFOLD_BANDS[name.value])
            if raised < floor:  # pragma: no cover - the bands are above them
                raise CandidateSupplyError(
                    f"{name.value}: the scaffold band {raised} is below BF-02"
                    f" §11's floor {floor}"
                )
            cost[name] = max(cost[name], raised)
    return benefit, cost


def _canonical_key(
    source: str,
    target_id: str,
    mode: TargetMode,
    modality: EvidenceModality,
    intent: LearningIntent,
) -> str:
    """BF-02 §4's five identity fields, joined in the document's own order.

    The fifth field, ``opportunity_binding_class``, carries the **source word**,
    and that is a declared reading with a reason and a cost worth stating: §4
    merges duplicate *proposals*, and two sources that bound the same target for
    different reasons are two opportunities — but the same (target, mode,
    modality, intent) reached from two sources with two pricing rows would be
    one key carrying two vectors, which is the shape P7-1's kernel refuses
    (judgement 3: "§4 forbids merging a factor vector") and which would raise
    ``PlannerInputError`` on a normal world. Binding by source makes that shape
    unreachable by construction: one source's proposals can only collide with
    the same source's, and one source proposes at most once per target.

    The cost of the reading is that §4's cross-source merge is never exercised
    by this generator (GS22's ``COVERAGE_DEBT`` + ``CURRENT_EXPRESSION_NEED``
    case). That is deliberate: merging across sources is only sound when the two
    readings agree, and nothing in this table makes them — so a cut that wants
    the merge has to make the readings agree first.

    Revisit: canonical text gives ``opportunity_binding_class`` a vocabulary (the
    frozen golden scenarios spell a constant ``CURRENT``), or a later cut needs
    cross-source merging — then the two sources' rows must produce one vector.
    GS22's merge is the acceptance any such cut has to reproduce, and a cut that
    re-asks for it (p7-4's shadow mode is the next candidate, its acceptance
    naming the canonicalization scenarios) must make the two sources' *readings*
    agree first: while ``COVERAGE_DEBT`` and ``CURRENT_EXPRESSION_NEED`` price
    one target differently, a second proposal for that key is the factor-vector
    conflict the kernel refuses, not a merge.
    """

    return "|".join(
        (target_id, mode.value, modality.value, intent.value, source)
    )


def _candidate_id(source: str, canonical_key: str) -> str:
    """A content-addressed proposal id: same source + same key, same id.

    Deterministic and stable (P7-1's fourth judgement is about the *merged*
    candidate's id; this is a proposal's), so two runs of one world produce the
    same id and no clock or counter is read.
    """

    digest = hashlib.sha256(
        "\x1f".join((source, canonical_key)).encode("utf-8")
    ).hexdigest()
    return f"cp-{digest[:24]}"


def _practice_mode(source: str, row: ContentTargetView) -> TargetMode | None:
    """The mode a practice source teaches with: the §11 row's own.

    ``None`` when the row names a mode the source's semantics do not fit (a
    "practice this target as authored" source cannot run on a row that says
    ``REVIEW``): the pairing is BF-02 §11's, and the caller's refusal names it
    rather than this function guessing.
    """

    mode = TargetMode(row.target_mode)
    if mode in (TargetMode.RESOURCE_PRACTICE, TargetMode.CAPABILITY_PRACTICE):
        return mode
    return None


# -- the generation ----------------------------------------------------------


def _gap_for(
    source: str, inputs: CandidateSupplyInputs
) -> SourceGap | None:
    """Why this source cannot run in this call, or ``None`` when it can."""

    absent = {
        CandidateAuthority.TARGET_SUPPLY: (
            inputs.targets is None,
            "no supply face: the set of §24.11-eligible targets cannot be read,"
            " and a generator that invented targets would be inventing content",
        ),
        CandidateAuthority.TARGET_ROW: (
            inputs.target_rows is None,
            "no §11 target-row face: a candidate's mode, intent and modality"
            " come from the content row (BF-02 §4's identity), so without it"
            " there is no candidate to build",
        ),
        CandidateAuthority.CONTENT_READINESS: (
            inputs.readiness is None,
            "no §8.1 readiness face: §8.1 has no level under R0 and the kernel"
            " has no 'unknown readiness' word, so a candidate built without one"
            " would be a level this cut invented",
        ),
        CandidateAuthority.SCHEDULE_ROW: (
            inputs.schedule is None,
            "no §5.2 row face: BF-02 §5 forbids answering schedule_urgency with"
            " a number when the Scheduler was never asked, and the kernel gaps"
            " on a rowless candidate — so the row is required, not optional",
        ),
        CandidateAuthority.SCHEDULE_VIEW: (
            inputs.schedule is None,
            "no §10 schedule view: which targets the Scheduler declared due is"
            " its own classification (D-INV-009), and this source reads the"
            " view's buckets rather than deriving due-ness from a row of its"
            " own",
        ),
        CandidateAuthority.LEARNER_STATE: (
            inputs.learner_state is None,
            "no §11 learner-state face: a source that reads BF-01's flags"
            " cannot tell 'no evidence' from 'no authority' without it, and"
            " guessing the first would make every target a probe",
        ),
        CandidateAuthority.TURN_OPPORTUNITY: (
            inputs.observation is None,
            "no turn observation: RA §4 step 3's 'Teaching opportunity"
            " proposal' is a durable artifact no cut records yet, so nothing"
            " produced this source's input — the generator supplies the shape"
            " (OpportunityObservation) and refuses to infer one",
        ),
        CandidateAuthority.CONSTRAINT_VIEW: (
            inputs.constraints is None,
            "no §9 constraint view: the manual request this source reads is the"
            " user's own durable act (MANUAL_FOCUS), so without the view there"
            " is no request to serve — and a request inferred from the text"
            " would be a second authority",
        ),
        CandidateAuthority.PLANNING_LEDGER: (
            inputs.ledger is None,
            UNLANDED_AUTHORITIES[CandidateAuthority.PLANNING_LEDGER],
        ),
    }
    for authority in COMMON_FACES:
        missing, reason = absent[authority]
        if missing:
            return SourceGap(source=source, authority=authority, reason=reason)
    face = SOURCE_AUTHORITY[source]
    if face is None:
        return None
    if face in absent:
        missing, reason = absent[face]
    else:
        # a source whose authority has no face anywhere: it gaps on every call,
        # whatever the caller holds (TRANSFER_POLICY / CORE_TIER /
        # GOAL_PACK_MAPPING — PLANNING_LEDGER reads its own entry above, because
        # p7-3 landed the ledger as a view a caller can hold)
        missing, reason = True, UNLANDED_AUTHORITIES[face]
    if missing:
        return SourceGap(source=source, authority=face, reason=reason)
    return None


def _flags_of_state(state: object) -> tuple[str, ...]:
    """The flags a §11 state record carries, read defensively (see supply.py)."""

    projection = getattr(state, "projection", None)
    flags = getattr(projection, "learning_flags", ()) if projection else ()
    return tuple(str(flag) for flag in flags)


def _context_for(
    target: SupplyTargetPort,
    inputs: CandidateSupplyInputs,
    readiness_map: dict[str, str | None],
    refusals: list[TargetRefusal],
) -> _TargetContext | None:
    """Read one target's legs, or record why it never becomes a candidate."""

    target_id = str(target.target_id)
    assert inputs.target_rows is not None
    assert inputs.schedule is not None
    row = inputs.target_rows.get_target(target_id)
    if isinstance(row, Err):
        refusals.append(
            TargetRefusal(
                target_id=target_id,
                gate="TARGET_ROW",
                reason=(
                    "the §11 target row could not be read"
                    f" ({row.error.code.value}): a candidate's identity comes"
                    " from that row, so the target cannot become one"
                ),
            )
        )
        return None
    try:
        modality = EvidenceModality(row.value.evidence_modality)
    except ValueError:
        refusals.append(
            TargetRefusal(
                target_id=target_id,
                gate="MODALITY",
                reason=(
                    f"the §11 row names evidence modality"
                    f" {row.value.evidence_modality!r}, which is not one of V1's"
                    " two (DATA_MODEL §24.14): a candidate cannot carry a"
                    " modality the runtime cannot deliver"
                ),
            )
        )
        return None

    outcome = readiness_of_target(target_id, inputs.readiness)
    level = outcome.level
    readiness_map[target_id] = None if level is None else level.value
    if level is None:
        refusals.append(
            TargetRefusal(
                target_id=target_id,
                gate="CONTENT_READINESS",
                reason="; ".join(outcome.reasons),
            )
        )
        return None

    prerequisites = prerequisite_state_of(
        target.target_type,
        target_id,
        modality,
        prerequisites=inputs.prerequisites,
        learner_state=inputs.learner_state,
    )
    schedule_row = inputs.schedule.get_schedule_item(
        target.target_type, TargetId(target_id), modality
    )
    if isinstance(schedule_row, Err):
        refusals.append(
            TargetRefusal(
                target_id=target_id,
                gate="SCHEDULE_ROW",
                reason=(
                    "the §5.2 row read failed"
                    f" ({schedule_row.error.code.value})"
                ),
            )
        )
        return None
    if schedule_row.value is None:
        refusals.append(
            TargetRefusal(
                target_id=target_id,
                gate="SCHEDULE_ROW",
                reason=(
                    "the Scheduler holds no §5.2 row for this target: BF-02 §5"
                    " forbids answering schedule_urgency with a number for a"
                    " target the Scheduler was never asked about, and the"
                    " kernel degrades on a rowless candidate — so no candidate"
                    " is built rather than one carrying a 0"
                ),
            )
        )
        return None

    flags: tuple[str, ...] = ()
    if inputs.learner_state is not None:
        state = inputs.learner_state.get_learner_target_state(
            TargetId(target_id), modality
        )
        if isinstance(state, Ok) and state.value is not None:
            flags = _flags_of_state(state.value)

    auto_suppressed = False
    review_suppressed = False
    if inputs.constraints is not None:
        for entry in entries_of_type(
            inputs.constraints, PlannerConstraintType.DO_NOT_AUTO_TEACH
        ):
            if applies_to(entry, target.target_type, TargetId(target_id)):
                auto_suppressed = True
        for entry in entries_of_type(
            inputs.constraints, PlannerConstraintType.SUPPRESS_REVIEW
        ):
            if applies_to(entry, target.target_type, TargetId(target_id)):
                review_suppressed = True

    return _TargetContext(
        target_type=target.target_type,
        target_id=target_id,
        row=row.value,
        modality=modality,
        level=level,
        readiness_reasons=outcome.reasons,
        prerequisites=prerequisites,
        schedule_row=schedule_row.value,
        flags=flags,
        auto_suppressed=auto_suppressed,
        review_suppressed=review_suppressed,
        ledger=(
            None
            if inputs.ledger is None
            else inputs.ledger.readings_for(target_id, as_of=inputs.as_of)
        ),
    )


def _wanted(
    source: str,
    contexts: Mapping[str, _TargetContext],
    inputs: CandidateSupplyInputs,
    scope: ScopeResolution,
) -> tuple[str, ...]:
    """The target ids one source wants to propose for, in order, deduplicated.

    A source's condition is read from the faces it declared: the Scheduler's
    own due answer for a review, the estimator's flags for a gap, an absence of
    state for a probe, the ledger's own obligations for a coverage debt, and the
    observation / constraint view for the rest. Two kinds of source answer here,
    and the difference decides what the caller's ``OUTSIDE_SUPPLY`` refusal can
    ever see: the observation-backed sources (``OBSERVATION_FIELD``),
    ``MANUAL_USER_REQUEST`` and ``COVERAGE_DEBT`` name ids straight from the
    turn's declared observation, the §9 request view and the ledger's
    obligations, so an id the supply does not carry is still returned and the
    caller records an ``OUTSIDE_SUPPLY`` refusal rather than dropping it
    silently — while the four context-derived sources (a due row, a flag, no
    state) answer by sweeping the contexts and therefore never name an id the
    supply lacks.
    """

    if source in OBSERVATION_FIELD:
        assert inputs.observation is not None
        return tuple(
            str(value)
            for value in getattr(inputs.observation, OBSERVATION_FIELD[source])
        )
    if source == "MANUAL_USER_REQUEST":
        return tuple(
            str(request.target_id) for request in scope.request_targets
        )
    if source == "SCHEDULED_REVIEW":
        assert inputs.schedule is not None
        view = inputs.schedule.get_schedule_view(inputs.as_of)
        if isinstance(view, Err):
            return ()
        due_keys = {
            (row.target_type, str(row.target_id), str(row.evidence_modality))
            for row in (*view.value.due_items, *view.value.overdue_items)
        }
        return tuple(
            ctx.target_id
            for ctx in contexts.values()
            if (ctx.target_type, ctx.target_id, str(ctx.modality)) in due_keys
        )
    if source in ("CONFIRMED_GAP", "SUPPORT_WITHDRAWAL"):
        flag = (
            "CONFIRMED_GAP" if source == "CONFIRMED_GAP" else "SUPPORT_DEPENDENT"
        )
        return tuple(
            ctx.target_id for ctx in contexts.values() if flag in ctx.flags
        )
    if source == "UNKNOWN_PROBE":
        return tuple(
            ctx.target_id
            for ctx in contexts.values()
            if _has_no_state(ctx, inputs)
        )
    if source == "COVERAGE_DEBT":
        assert inputs.ledger is not None
        return inputs.ledger.serviceable_targets()
    return ()


def _has_no_state(
    ctx: _TargetContext, inputs: CandidateSupplyInputs
) -> bool:
    """Whether Learning holds no §11 state for this target × modality.

    ``_context_for`` already read the row (its flags are on the context); this
    asks the same face the same question so "never observed" is a read rather
    than an inference from an empty flag tuple — a state whose flags are all
    clear is *known*, not unknown. ``INSUFFICIENT_EVIDENCE`` counts as unknown:
    BF-01 §25's own word for "the evidence does not support a state".
    """

    assert inputs.learner_state is not None
    state = inputs.learner_state.get_learner_target_state(
        TargetId(ctx.target_id), ctx.modality
    )
    if not isinstance(state, Ok):
        return False
    if state.value is None:
        return True
    flags = _flags_of_state(state.value)
    return "INSUFFICIENT_EVIDENCE" in flags


def _build(
    source: str,
    ctx: _TargetContext,
    inputs: CandidateSupplyInputs,
    refusals: list[TargetRefusal],
) -> CandidateProposal | None:
    """One proposal, or the refusal that stopped it."""

    reading = SOURCE_READINGS[source]
    if reading.mode is None:
        mode = _practice_mode(source, ctx.row)
        if mode is None:
            refusals.append(
                TargetRefusal(
                    target_id=ctx.target_id,
                    gate="MODE_INTENT_PAIR",
                    source=source,
                    reason=(
                        f"the §11 row names target mode"
                        f" {ctx.row.target_mode!r}, which is not a practice mode:"
                        " this source teaches the target as authored, so it has"
                        " no shape for a row that already names a probe, a"
                        " review or a transfer"
                    ),
                )
            )
            return None
    else:
        mode = reading.mode
    intent = (
        reading.intent
        if reading.intent is not None
        else LearningIntent(ctx.row.learning_intent)
    )
    if intent not in MODE_ALLOWED_INTENTS[mode]:
        refusals.append(
            TargetRefusal(
                target_id=ctx.target_id,
                gate="MODE_INTENT_PAIR",
                source=source,
                reason=(
                    f"{mode.value} cannot carry {intent.value}: BF-02 §11's"
                    " pairing admits "
                    + ", ".join(
                        allowed.value for allowed in MODE_ALLOWED_INTENTS[mode]
                    )
                    + " — the row's own intent and this source's intent"
                    " disagree, and the kernel would refuse the proposal"
                ),
            )
        )
        return None

    scaffolded = ctx.prerequisites.scaffoldable or (
        ctx.prerequisites.state is PrerequisiteState.READY_WITH_SCAFFOLD
    )
    benefit, cost = _declared_vector(reading, ctx, inputs, scaffolded)
    user_initiated = source == "MANUAL_USER_REQUEST"
    suppressed = (ctx.auto_suppressed and not user_initiated) or (
        ctx.review_suppressed and mode is TargetMode.REVIEW
    )
    canonical_key = _canonical_key(
        source, ctx.target_id, mode, ctx.modality, intent
    )
    coverage_service_state = CoverageServiceState.NONE
    if source == "COVERAGE_DEBT" and ctx.ledger is not None:
        # only the ledger-reading source carries a service state: the state is
        # the *obligation's*, and nothing else here proposes coverage service
        coverage_service_state = ctx.ledger.service_state
    return CandidateProposal(
        candidate_id=_candidate_id(source, canonical_key),
        canonical_key=canonical_key,
        focus_target=ctx.target_id,
        target_mode=mode,
        learning_intent=intent,
        evidence_modality=ctx.modality,
        opportunity_binding_class=source,
        initiative_class=reading.initiative,
        benefit=benefit,
        cost=cost,
        origins=(source,),
        user_initiated=user_initiated,
        request_aligned=user_initiated,
        request_priority=0,
        content_readiness=ctx.level,
        prerequisite_state=ctx.prerequisites.state,
        prerequisite_scaffoldable=scaffolded,
        coverage_service_state=coverage_service_state,
        modality_available=True,
        expired=False,
        deprecated=False,
        suppressed=suppressed,
        runtime_generated_ready=False,
        task_aligned=False,
        critical_repair=False,
        goal_relation=GoalRelation.NONE,
        schedule_row=ctx.schedule_row,
    )


def _generate(
    inputs: CandidateSupplyInputs, sources: Sequence[str]
) -> CandidateSupply:
    """The shared generation pass, over a source subset in the given order."""

    gaps: list[SourceGap] = []
    refusals: list[TargetRefusal] = []
    readiness_map: dict[str, str | None] = {}
    proposals: list[CandidateProposal] = []

    active: list[str] = []
    for source in sources:
        gap = _gap_for(source, inputs)
        if gap is None:
            active.append(source)
        else:
            gaps.append(gap)

    contexts: dict[str, _TargetContext] = {}
    if inputs.targets is not None:
        facts = inputs.targets.facts()
        if isinstance(facts, Err):
            for source in active:
                gaps.append(
                    SourceGap(
                        source=source,
                        authority=CandidateAuthority.TARGET_SUPPLY,
                        reason=(
                            "the supply face could not answer"
                            f" ({facts.error.code.value}): an unreadable supply"
                            " set is not an empty one"
                        ),
                    )
                )
            active = []
        else:
            for target in facts.value:
                ctx = _context_for(target, inputs, readiness_map, refusals)
                if ctx is not None:
                    contexts[ctx.target_id] = ctx

    scope = resolve_user_intent_scope(inputs.constraints)
    for source in active:
        for target_id in _wanted(source, contexts, inputs, scope):
            ctx = contexts.get(target_id)
            if ctx is None:
                if any(
                    refusal.target_id == target_id
                    and refusal.source is None
                    for refusal in refusals
                ):
                    continue
                refusals.append(
                    TargetRefusal(
                        target_id=target_id,
                        gate="OUTSIDE_SUPPLY",
                        source=source,
                        reason=(
                            "this source named a target the supply set does not"
                            " carry: a candidate needs the target's §11 row and"
                            " its §5.2 row, and nothing may be invented for an"
                            " id the content side does not offer"
                        ),
                    )
                )
                continue
            proposal = _build(source, ctx, inputs, refusals)
            if proposal is not None:
                proposals.append(proposal)

    return CandidateSupply(
        proposals=tuple(proposals),
        gaps=tuple(gaps),
        refusals=tuple(refusals),
        readiness=dict(sorted(readiness_map.items())),
        scope=scope,
    )


def generate_track_a(inputs: CandidateSupplyInputs) -> CandidateSupply:
    """§6's expression-driven lane, six sources, in the document's order."""

    return _generate(inputs, TRACK_A_SOURCES)


def generate_track_b(inputs: CandidateSupplyInputs) -> CandidateSupply:
    """§6's curriculum-driven lane, eight sources, in the document's order."""

    return _generate(inputs, TRACK_B_SOURCES)


def generate_candidates(inputs: CandidateSupplyInputs) -> CandidateSupply:
    """Both lanes, one proposal set: §6's "两条 lane 进入同一 Planner".

    Track A first, then Track B, each in §6's own source order and each
    source's targets in the supply's order — so the arrival order is a property
    of the documents rather than of the caller, and the kernel's step 1 cannot
    be affected by it (P7-1 pins that the arrival order cannot change the
    decision; this pins that the generator's order cannot either).
    """

    return _generate(inputs, CANDIDATE_SOURCES)
