"""BF-02's frozen 43-case stress suite, re-run through this repository's own
chain (P7-4).

``behavioral_baselines/planner/run_stress.py`` is the frozen runner: it loads
``planner_stress_cases_v1_1.json``, asks the frozen reference implementation
(``planner_reference_v1_1.py``) for each case's answer, and compares it with the
case's own ``expected``. This module is that runner's in-repo twin — the **same
43 cases**, the **same** ``expected`` values (the JSON is read-only; its
``expected`` is never edited), and the reference implementation's decision tree
reproduced one branch at a time — with the reference replaced by this
repository's chain: :func:`proposals_of` / :func:`authority_of` adapt one case's
``input`` into a :class:`~elc.planner.kernel.PlanningInput` and
:func:`run_input` runs :func:`elc.planner.kernel.plan` over it.

docs/IMPLEMENTATION_PLAN.md §8's Acceptance line is "复现 OQ-023A 12+ conflict
cases". ``OQ-023A`` has **no carrier** in this repository or in the archived
one, which is why the Phase 7 phase-acceptance records the frozen 43-case suite
as its executable substitute. This module reproduces that substitute; it claims
nothing about an ``OQ-023A`` artifact.

**The adapter boundary, and why the divergences live here.** The suite's
``input.candidates[]`` is BF-02 §4's **post-merge** layering: each row already
carries an ``id`` and the identity fields a ``canonical_key`` is made of. Two
kernel readings then meet input the kernel does not accept, and both were
registered by P7-1 as things *this* cut has to model explicitly (kernel
docstring judgements 8–10) rather than tune away — modelling them here is what
keeps the kernel's own semantics at zero:

- **duplicate identities (S04, S42).** §4's last line makes a duplicate
  ``canonical_key`` an input contract error, while the kernel's merge serves
  the **proposal** layer (two generator arrivals that describe one candidate).
  The suite's two shapes are the *canonical* layer carrying a duplicate — S04's
  ``d1``/``d2`` sharing one key, S42's ``x`` twice — so :func:`proposals_of`
  refuses them at the boundary, by key and by id respectively, and the kernel's
  merge semantics stay untouched. Revisit: a cut reconciles §4's last line with
  the kernel's merge — the canonical layer refusing the shape itself, or §4's
  line read as a proposal-layer rule only;
- **a missing factor under an INCOMPLETE assembly (S20).** BF-02 §5 answers
  ``DEGRADED`` for the context before any vector is read, while §20's
  completeness is a contract over the input and the kernel walks step 1 and 2
  before step 3. :func:`degraded_reason_of` therefore reads BF-02 §5's two
  words *before* the kernel runs (the reference's own ``_precheck_context``
  order), and the kernel keeps §10.1's order. Revisit: judgement 3 below names
  the condition that re-opens this order — the same reading, read beside the
  other verdicts;

**Declared judgements.** Each entry is this cut's reading rather than a
quotation, and each names the condition that re-opens it:

1. **the field mapping, per case field.** ``id`` → ``candidate_id``;
   ``canonical_key`` (defaulting to the id, the reference's own
   ``c.get("canonical_key") or cid``) → ``canonical_key``; ``initiative`` →
   ``initiative_class``; ``target_mode`` / ``learning_intent`` verbatim;
   ``content_readiness``'s ``R0``–``R4`` → the ladder's five words
   (``elc.curriculum.readiness``'s, which the kernel reuses rather than
   re-spelling); every eligibility boolean verbatim (``expired`` /
   ``deprecated`` / ``suppressed`` / ``modality_available`` /
   ``user_initiated`` / ``request_aligned`` / ``runtime_generated_ready`` /
   ``prerequisite_scaffoldable``, each defaulting to the kernel's own default);
   ``origins`` / ``request_priority`` / ``prerequisite_state`` /
   ``coverage_service_state`` verbatim; ``benefit`` / ``cost`` by factor name,
   **missing names left missing** so §20's completeness check is the kernel's
   to make. Three kernel fields the suite does not carry are synthesized and
   are decision-inert: ``focus_target`` = the candidate's ``id`` (the one
   stable name a case gives it), ``evidence_modality`` = one declared word for
   every candidate, and ``opportunity_binding_class`` = one declared word.
   ``goal_relation`` stays the kernel's default (``NONE``), and the suite's
   ``scaffold_required`` is read by nothing: BF-02 §11's floors are read off
   ``prerequisite_state`` + ``prerequisite_scaffoldable``, which is the
   reference's own reading. Revisit: canonical text names the three synthesized
   fields, or BF-02 gains a case that distinguishes them;
2. **§20's vector is an *input*, spelled by a synthesized §5.2 row.** The suite
   hands complete vectors and no ``ScheduleItem``, while the kernel's judgement
   11 accepts a declared ``schedule_urgency`` only when the candidate's §5.2 row
   answers the same number (P7-0's ``schedule_urgency_of`` owns it). The
   adapter therefore synthesizes one :class:`~elc.scheduler.types.ScheduleItem`
   per candidate whose ``review_urgency`` **is** the declared number, and
   declares the context's ``schedule_authority`` as ``CURRENT``. That is the
   reading the kernel's judgement 11 invited ("canonical text says whether the
   factor vector is an *input* to the assembly or its *output*; §20 lists it
   among the frozen inputs"), taken here and nowhere near production code. The
   row's ``review_state`` is inert because the stored column is set (P7-0
   answers through the Scheduler's own number first, falling back to the band
   only for a row with no urgency), so one word serves every candidate. A
   candidate whose vector leaves the name out altogether (S20's ``x``, judgement
   1) still gets its row — the shape is one row per candidate — and the number
   its column carries is then :data:`_UNDECLARED_ROW_URGENCY` rather than a
   second declaration: §20's completeness check refuses that vector before the
   leg could read the row, so the placeholder cannot reach a verdict (pinned by
   test).
   Revisit: canonical rules the vector an assembly **output**, or a real
   Scheduler supplies §5.2 rows — then the rows are read and not synthesized;
3. **BF-02 §5's two words are read before the kernel (S20).** Judgement 2 of
   the list above, spelled as code: a context whose
   ``feature_assembly_status != COMPLETE`` is ``DEGRADED`` /
   ``FEATURE_ASSEMBLY_INCOMPLETE`` and one whose ``snapshot_status != VALID``
   is ``SNAPSHOT_INVALID``, each with no decision. The error codes are the
   kernel's own :class:`~elc.planner.kernel.DegradedReason` values, so the
   suite, the kernel and BF-02 §5's line "``PlannerExecutionStatus = DEGRADED``
   / ``PlannerDecision = none``" use one spelling. Revisit: canonical text
   settles the precedence between a context verdict and §20's vector contract —
   the kernel's judgement 9 registers the same condition;
4. **the suite's ``snapshot_status`` is a free word.** S06 spells ``STALE``,
   which is not one of BF-02 §5's two words (``VALID`` / ``INVALID``) that P7-0
   records, so any non-``VALID`` spelling maps to ``INVALID`` — the same
   verdict, with the precheck's error code naming the fact. Revisit: BF-02 or
   canonical text gives the status a third word;
5. **``missing_authorities`` words are carried and not translated.** The
   suite's own word for the Scheduler entry is ``SCHEDULER`` and P7-0's
   spelling is ``SCHEDULE``; the adapter maps the words its declared table
   carries (:data:`SUITE_AUTHORITY_WORDS`) and writes every word it cannot place
   into the record's ``reasons`` verbatim, so nothing is dropped silently while
   the typed tuple stays P7-0's vocabulary. No case's verdict reads the list
   (its one consumer is the goal leg's ``GOAL_ASSESSMENT_PACK_MAPPING`` check,
   and no case names it). Revisit: canonical or BF-02 pins the list's
   vocabulary;
6. **the policy word is the profile row.** ``policy_profile``'s three words are
   BF-02 §13's own (``LOUNGE`` / ``BALANCED`` / ``STUDY_FIRST``) and
   :data:`elc.planner.kernel.POLICY_PROFILES` carries one row per word, so the
   mapping is a lookup rather than a translation; the numbers themselves are
   pinned against ``planner_reference_profile_v1_1.json`` by the P7-1 suite.
   ``automatic_teaching_enabled`` is set ``True`` on the record because BF-02's
   profiles carry no such switch (§5.1's ``teaching_frequency`` does, and the
   suite has no policy row); the kernel reads no such field, so it is
   decision-inert here. Revisit: the suite gains a case whose verdict depends on
   the automatic-teaching switch;
7. **``gate_state`` is not a Planner input (S39).** The reference ignores the
   key and so does this adapter: BF-02 §17 is explicit that the Planner may
   SELECT while a later Gate hard state will DENY, and reading Gate state here
   would rebuild a second ranking. Revisit: BF-02 gives the Planner a Gate
   input;
8. **the runner's own readings of the decision tree.** The reference's ``run()``
   compares the **rounded** (6 places) utilities of two candidates for
   ``EQUAL_UTILITY`` and the same rounded numbers for the two monotonicity
   customs; this module reproduces the rounding rather than the raw floats, and
   the three cases' raw numbers satisfy their predicates as well (pinned by
   test, so the replica is not the thing being measured).
   ``ORDER_DETERMINISM`` compares the run's ``PlannerDecision`` **record** under
   a reversed candidate list — the reference compares its decision dicts — and
   the stronger fact (the whole :class:`~elc.planner.kernel.KernelResult` is
   equal under reversal for S31) is pinned separately. ``HI_UTILITY_GE`` /
   ``LOW_COST_UTILITY_GE`` read the *scored* set, i.e. every candidate step 4
   kept whether or not it activated (the kernel's ``CandidateTrace.utility``).
   Revisit: ``run_stress.py`` changes a predicate, or a case's raw numbers stop
   agreeing with its rounded ones;
9. **``NOT_SCHEDULED``'s gap is not exercised here.** The kernel's judgement 13
   registers that a target the Scheduler never scheduled has no §5.2 row and its
   ``schedule_urgency`` is therefore a gap rather than BF-02 §6's ``0.0``;
   every candidate in this replay carries a synthesized row (judgement 2), so no
   case reaches that gap — including the forty cases whose candidates all
   declare ``0.0`` and which a *row-less* adaptation would have turned into
   gaps. The two facts therefore stay distinguishable in this
   module: "the suite says 0.0" (a row answers ``0.0``) and "the Scheduler was
   never asked" (no row) are different adaptations, and this one is the
   suite's. Revisit: a §5.2 row becomes a real read here, or the kernel's gap is
   closed by a fourth bucket;
10. **this module is a replay, not a production path.** Nothing in ``src/elc``
    imports it (it is not exported from the package's ``__init__``), the kernel
    it runs is the same one every consumer runs, and the frozen reference is
    never imported — only its *cases* are read. Revisit: a cut decides the
    acceptance suite belongs on the production face.

**Versioning.** :data:`STRESS_SUITE_MODEL_VERSION` stamps this module's own
readings (judgements 1–9). It moves with them and not with BF-02's numbers.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from elc.planner.feature_assembly import (
    AuthorityName,
    FeatureAssemblyStatus,
    FeatureAuthority,
    PlannerProfile,
    ScheduleAuthority,
    ScheduleRowPort,
    SnapshotStatus,
)
from elc.planner.kernel import (
    BenefitFactor,
    CandidateProposal,
    CostFactor,
    CoverageServiceState,
    DegradedReason,
    GoalRelation,
    PlannerInputError,
    PlanningInput,
    PrerequisiteState,
    ReadinessLevel,
    plan,
)
from elc.planner.types import (
    InitiativeClass,
    LearningIntent,
    TargetMode,
    UserIntentScope,
)
from elc.platform.types import (
    DecisionCycleId,
    EvidenceModality,
    PlannerDecision,
    PlannerDecisionOutcome,
    PlannerExecutionStatusValue,
    ScheduleVersion,
    TargetId,
)
from elc.scheduler.types import ReviewState, ScheduleItem

__all__ = [
    "CASE_CUSTOM_WORDS",
    "DEFAULT_PLANNING_CONTEXT",
    "STRESS_SUITE_MODEL_VERSION",
    "SUITE_AUTHORITY_WORDS",
    "CaseKind",
    "CaseRefusal",
    "CaseRun",
    "CaseVerdict",
    "authority_of",
    "degraded_reason_of",
    "load_cases",
    "planning_input_of",
    "proposals_of",
    "run_input",
    "schedule_row_of",
    "stress_report",
    "stress_table",
    "verdict_of",
]

#: Stamps this module's own readings (module docstring, "Declared judgements").
STRESS_SUITE_MODEL_VERSION = "bf02-suite-1"

#: The reference's own default PlanningContext (``_planning_context``), for the
#: cases that name none: COMPLETE / VALID / no natural break / nothing missing.
DEFAULT_PLANNING_CONTEXT: Mapping[str, Any] = {
    "feature_assembly_status": "COMPLETE",
    "snapshot_status": "VALID",
    "natural_break_available": False,
    "missing_authorities": [],
}

#: The five custom predicates the suite's ``expected.custom`` can name.
CASE_CUSTOM_WORDS = (
    "DEGRADED",
    "EQUAL_UTILITY",
    "HI_UTILITY_GE",
    "LOW_COST_UTILITY_GE",
    "ORDER_DETERMINISM",
)

#: The suite's authority words this adapter can place in P7-0's vocabulary
#: (judgement 5). One pairing, because one word occurs in the frozen file.
SUITE_AUTHORITY_WORDS: Mapping[str, AuthorityName] = {
    "SCHEDULER": AuthorityName.SCHEDULE,
}

#: The suite's §8.1 ladder words → the kernel's readiness levels (judgement 1).
_READINESS: Mapping[str, ReadinessLevel] = {
    "R0": ReadinessLevel.R0_INDEXED,
    "R1": ReadinessLevel.R1_LEXICALLY_RESOLVED,
    "R2": ReadinessLevel.R2_PLANNER_READY,
    "R3": ReadinessLevel.R3_TEACHING_READY,
    "R4": ReadinessLevel.R4_DETECTION_READY,
}

#: The three synthesized fields (judgement 1) and the synthesized row's columns
#: (judgement 2), each declared once so no reader has to infer it from a call
#: site. Every one of them is decision-inert in this replay.
_SYNTHESIZED_MODALITY = EvidenceModality.TEXT_PRODUCTION
_SYNTHESIZED_BINDING_CLASS = "TURN"
_SYNTHESIZED_REVIEW_STATE = ReviewState.DUE

#: The urgency the synthesized row carries for a candidate whose vector leaves
#: ``schedule_urgency`` out altogether (judgement 1 keeps a missing name
#: missing, so there is no declared number to spell). It is BF-02 §6's band for
#: a target with no recorded urgency, and it is inert by construction: §20's
#: completeness check refuses that vector before ``_schedule_leg`` could read
#: the row, so the placeholder cannot reach a verdict (pinned by test).
_UNDECLARED_ROW_URGENCY = 0.0
_SYNTHESIZED_WATERMARK = "0"
_SYNTHESIZED_VERSION = ScheduleVersion("sv-suite")
_SYNTHESIZED_TARGET_TYPE = "RESOURCE"
_SYNTHESIZED_POLICY_MAPPING_VERSION = "bf02-suite-1"


# -- the records -------------------------------------------------------------


class CaseKind(StrEnum):
    """What one replayed case answered — the decision tree's four shapes."""

    SELECT = "SELECT"
    NO_TARGET = "NO_TARGET"
    DEGRADED = "DEGRADED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class CaseRefusal:
    """One case this chain refused, and the contract it broke.

    The type and the message are kept rather than folded into a ``bool``: the
    suite's six ``error: true`` cases each name a *different* condition, and
    "caught something" is not the claim their ``description`` makes.
    """

    error_type: str
    message: str


@dataclass(frozen=True)
class CaseRun:
    """One case's answer, in the shape the reference's ``run()`` compares.

    ``scored`` carries every candidate step 4 kept, with its utility rounded to
    six places — the reference's ``evaluation["scored"]`` rows — so the custom
    predicates read the same numbers the frozen runner read. A ``REFUSED`` run
    carries no decision at all (the contract was broken before one existed),
    which is a different shape from a ``DEGRADED`` run (§5's status, and no
    decision either).
    """

    kind: CaseKind
    selected: str | None
    no_target_reason: str | None
    degraded_reason: str | None
    scored: tuple[tuple[str, float], ...]
    refusal: CaseRefusal | None
    decision: PlannerDecision | None
    execution_status: PlannerExecutionStatusValue | None

    @property
    def utilities(self) -> Mapping[str, float]:
        """``scored`` as a mapping, for the predicates that name candidates."""

        return dict(self.scored)


@dataclass(frozen=True)
class CaseVerdict:
    """One line of the table: the case, what this chain answered, and the verdict.

    ``expected`` is the case's own frozen ``expected``, rendered for reading;
    ``evidence`` is what the run actually answered. A ``DIVERGENCE`` is a case
    whose frozen expectation does not hold — the number this replay exists to
    drive to zero.
    """

    case_id: str
    description: str
    kind: CaseKind
    expected: str
    evidence: str
    passed: bool

    @property
    def verdict_word(self) -> str:
        return "PASS" if self.passed else "DIVERGENCE"

    def line(self) -> str:
        """One printable table row: case → what was answered → verdict.

        The evidence column is padded to :data:`EVIDENCE_WIDTH` and shortened
        past it for a **passing** scoring row, where the verdict already
        answers the reader's question. A refusal and a divergence print their
        evidence in full, because those are the lines someone has to act on —
        a refusal names the contract it broke. :attr:`evidence` itself is never
        shortened.
        """

        evidence = self.evidence
        if (
            self.passed
            and self.kind is not CaseKind.REFUSED
            and len(evidence) > self.EVIDENCE_WIDTH
        ):
            evidence = evidence[: self.EVIDENCE_WIDTH - 3] + "..."
        return (
            f"{self.case_id:<34} {self.expected:<26} {evidence:<44}"
            f" {self.verdict_word}"
        )

    #: The table's evidence column width (display only, ``line()``).
    EVIDENCE_WIDTH = 44


# -- the adapter -------------------------------------------------------------


def load_cases(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    """Read one frozen case file.

    The caller names the path: nothing here reaches into the repository on its
    own (judgement 10), so the module runs against whatever file it is handed.
    """

    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError(f"{path}: the case file is not a list of cases")
    return tuple(loaded)


def schedule_row_of(candidate_id: str, urgency: float) -> ScheduleRowPort:
    """The §5.2 row that spells one candidate's declared ``schedule_urgency``.

    Judgement 2: the row exists so the kernel's judgement 11 has something to
    answer with, and its stored column *is* the declared number. Its target id
    is the candidate's own id, since the suite names no target.

    The value is a real :class:`~elc.scheduler.types.ScheduleItem` (a test can
    say so); the cast only bridges a typing fact — P7-0's port declares
    *settable* attributes, which a frozen dataclass does not satisfy on paper
    while it satisfies the port exactly at runtime.
    """

    return cast(
        ScheduleRowPort,
        ScheduleItem(
            schedule_item_id=f"si-suite-{candidate_id}",
            target_type=_SYNTHESIZED_TARGET_TYPE,
            target_id=TargetId(candidate_id),
            evidence_modality=_SYNTHESIZED_MODALITY,
            review_state=_SYNTHESIZED_REVIEW_STATE,
            review_urgency=float(urgency),
            source_learning_watermark=_SYNTHESIZED_WATERMARK,
            version=_SYNTHESIZED_VERSION,
        ),
    )


def proposals_of(
    case_input: Mapping[str, Any], *, reverse: bool = False
) -> tuple[CandidateProposal, ...]:
    """One case's ``candidates[]`` as the kernel's proposals (judgement 1).

    The boundary checks come first and by name: a repeated ``id`` is refused
    before a repeated ``canonical_key`` because §4's key is derived from the
    candidate's own identity and S42's duplicate carries both — the id is the
    fact the case's ``description`` names, and the reference's own
    ``validate_input`` checks it first.

    Every candidate leaves with a synthesized §5.2 row (judgement 2) whose
    stored urgency **is** the number its vector declares — or
    :data:`_UNDECLARED_ROW_URGENCY` for the one candidate whose vector omits the
    name, where §20's completeness check refuses the vector before the row could
    be read.
    """

    rows = list(case_input.get("candidates", ()))
    if reverse:
        rows = list(reversed(rows))
    ids: set[str] = set()
    keys: set[str] = set()
    proposals: list[CandidateProposal] = []
    for row in rows:
        candidate_id = row.get("id")
        if not candidate_id or candidate_id in ids:
            raise PlannerInputError(
                f"duplicate candidate id {candidate_id!r}: BF-02 §4's"
                " candidates[] is the layering after the proposal merge, so"
                " one id twice is an input contract error"
            )
        ids.add(candidate_id)
        canonical_key = row.get("canonical_key") or candidate_id
        if canonical_key in keys:
            raise PlannerInputError(
                f"duplicate canonical_key {canonical_key!r}: BF-02 §4's last"
                " line makes a duplicate key an input contract error"
            )
        keys.add(canonical_key)
        declared = row.get("benefit") or {}
        urgency = declared.get(BenefitFactor.SCHEDULE_URGENCY.value)
        proposals.append(
            CandidateProposal(
                candidate_id=candidate_id,
                canonical_key=canonical_key,
                focus_target=candidate_id,
                target_mode=TargetMode(row["target_mode"]),
                learning_intent=LearningIntent(row["learning_intent"]),
                evidence_modality=_SYNTHESIZED_MODALITY,
                opportunity_binding_class=_SYNTHESIZED_BINDING_CLASS,
                initiative_class=InitiativeClass(row["initiative"]),
                benefit={
                    BenefitFactor(name): value
                    for name, value in declared.items()
                },
                cost={
                    CostFactor(name): value
                    for name, value in (row.get("cost") or {}).items()
                },
                origins=tuple(row.get("origins", ())),
                user_initiated=bool(row.get("user_initiated", False)),
                request_aligned=bool(row.get("request_aligned", False)),
                request_priority=int(row.get("request_priority", 0)),
                content_readiness=_READINESS[row.get("content_readiness", "R3")],
                prerequisite_state=PrerequisiteState(
                    row.get("prerequisite_state", "READY")
                ),
                prerequisite_scaffoldable=bool(
                    row.get("prerequisite_scaffoldable", False)
                ),
                coverage_service_state=CoverageServiceState(
                    row.get("coverage_service_state", "NONE")
                ),
                modality_available=bool(row.get("modality_available", True)),
                expired=bool(row.get("expired", False)),
                deprecated=bool(row.get("deprecated", False)),
                suppressed=bool(row.get("suppressed", False)),
                runtime_generated_ready=bool(
                    row.get("runtime_generated_ready", False)
                ),
                task_aligned=bool(row.get("task_aligned", False)),
                critical_repair=bool(row.get("critical_repair", False)),
                goal_relation=GoalRelation.NONE,
                schedule_row=schedule_row_of(
                    candidate_id,
                    (
                        _UNDECLARED_ROW_URGENCY
                        if urgency is None
                        else float(urgency)
                    ),
                ),
            )
        )
    return tuple(proposals)


def _context_of(case_input: Mapping[str, Any]) -> Mapping[str, Any]:
    """One case's PlanningContext with the reference's defaults filled in."""

    return {
        **DEFAULT_PLANNING_CONTEXT,
        **(case_input.get("planning_context") or {}),
    }


def authority_of(case_input: Mapping[str, Any]) -> FeatureAuthority:
    """One case's ``planning_context`` as P7-0's record (judgements 3–6).

    The four BF-02 §5 names are mapped verbatim; the profile comes from the
    case's own ``policy_profile`` word; the schedule authority is declared
    ``CURRENT`` because the adapter supplies the rows (judgement 2).
    """

    context = _context_of(case_input)
    words = tuple(context["missing_authorities"])
    return FeatureAuthority(
        status=FeatureAssemblyStatus(context["feature_assembly_status"]),
        snapshot_status=(
            SnapshotStatus.VALID
            if context["snapshot_status"] == SnapshotStatus.VALID.value
            else SnapshotStatus.INVALID
        ),
        schedule_authority=ScheduleAuthority.CURRENT,
        missing_authorities=tuple(
            SUITE_AUTHORITY_WORDS[word]
            for word in words
            if word in SUITE_AUTHORITY_WORDS
        ),
        natural_break_available=bool(context["natural_break_available"]),
        planner_profile=PlannerProfile(case_input["policy_profile"]),
        automatic_teaching_enabled=True,
        policy_mapping_version=_SYNTHESIZED_POLICY_MAPPING_VERSION,
        reasons=tuple(
            "bf02-suite: the case's PlanningContext names the missing"
            f" authority {word!r}, which is not one of P7-0's words"
            for word in words
            if word not in SUITE_AUTHORITY_WORDS
        ),
    )


def degraded_reason_of(case_input: Mapping[str, Any]) -> str | None:
    """BF-02 §5's two words, read before the kernel runs (judgement 3).

    ``None`` is "the context is usable"; otherwise the answer is the kernel's
    own :class:`~elc.planner.kernel.DegradedReason` value, so one fact has one
    spelling across the suite, the kernel and BF-02 §5.
    """

    context = _context_of(case_input)
    if context["feature_assembly_status"] != FeatureAssemblyStatus.COMPLETE.value:
        return DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    if context["snapshot_status"] != SnapshotStatus.VALID.value:
        return DegradedReason.SNAPSHOT_INVALID.value
    return None


def _checked_scope(case_input: Mapping[str, Any]) -> UserIntentScope:
    """The two words the reference checks before anything else.

    Its ``_precheck_context`` validates ``user_intent_scope`` and
    ``policy_profile`` first, and both are contract errors rather than verdicts;
    the frozen suite carries legal words only, so these checks are total for it
    and refuse a caller's typo instead of guessing a scope.
    """

    scope_word = case_input.get("user_intent_scope")
    if not isinstance(scope_word, str) or scope_word not in (
        UserIntentScope.__members__
    ):
        raise PlannerInputError(f"invalid user_intent_scope {scope_word!r}")
    policy_word = case_input.get("policy_profile")
    if not isinstance(policy_word, str) or policy_word not in (
        PlannerProfile.__members__
    ):
        raise PlannerInputError(f"invalid policy_profile {policy_word!r}")
    return UserIntentScope(scope_word)


def planning_input_of(
    case_input: Mapping[str, Any], *, reverse: bool = False
) -> PlanningInput:
    """One case's ``input`` as a kernel input — **without** §5's precheck.

    This is the seam the cut exists for: a caller can hand the kernel exactly
    the input the replay degrades on, which is how S20's divergence is shown to
    be the precheck's doing rather than the kernel's (judgement 3, and the
    kernel's own judgement 9). The two words are still checked, because they are
    the caller's data rather than the world's.
    """

    return PlanningInput(
        decision_cycle_id=DecisionCycleId("dc-bf02-suite"),
        planning_context=authority_of(case_input),
        user_intent_scope=_checked_scope(case_input),
        proposals=proposals_of(case_input, reverse=reverse),
    )


# -- the runner --------------------------------------------------------------


def run_input(case_input: Mapping[str, Any], *, reverse: bool = False) -> CaseRun:
    """One case's answer: the words, BF-02 §5's precheck, then the kernel.

    Every contract breach is captured as a :class:`CaseRun` of kind
    ``REFUSED`` — the reference's ``except Exception`` arm, kept as a record so
    the refusal can be examined by name (judgement 8). The arm is narrowed to
    the two families a caller's **bad case file** raises here: this module's
    own :class:`~elc.planner.kernel.PlannerInputError` (itself a
    ``ValueError``) plus the ``ValueError`` / ``KeyError`` a malformed
    vocabulary word or a missing field raises while a case is adapted — so a
    case spelling ``target_mode: "BOGUS"`` is answered with a per-case
    DIVERGENCE line rather than a traceback, while a genuine programming error
    still surfaces as one (the reference's bare ``Exception`` would have
    swallowed it). The precheck runs before the candidates are adapted, which
    is the reference's own order and the reason S20 answers ``DEGRADED`` rather
    than a vector-contract error (judgement 3).
    """

    try:
        return _run_checked(case_input, reverse=reverse)
    except (PlannerInputError, ValueError, KeyError) as refusal:
        return CaseRun(
            kind=CaseKind.REFUSED,
            selected=None,
            no_target_reason=None,
            degraded_reason=None,
            scored=(),
            refusal=CaseRefusal(
                error_type=type(refusal).__name__, message=str(refusal)
            ),
            decision=None,
            execution_status=None,
        )


def _run_checked(
    case_input: Mapping[str, Any], *, reverse: bool
) -> CaseRun:
    """The run itself, with ``PlannerInputError`` left to the caller's arm."""

    _checked_scope(case_input)
    degraded = degraded_reason_of(case_input)
    if degraded is not None:
        return CaseRun(
            kind=CaseKind.DEGRADED,
            selected=None,
            no_target_reason=None,
            degraded_reason=degraded,
            scored=(),
            refusal=None,
            decision=None,
            execution_status=PlannerExecutionStatusValue.DEGRADED,
        )
    result = plan(planning_input_of(case_input, reverse=reverse))
    scored = tuple(
        (row.candidate_id, round(row.utility, 6))
        for row in result.trace.candidates
        if row.utility is not None
    )
    decision = result.outcome.decision
    if decision is None:
        return CaseRun(
            kind=CaseKind.DEGRADED,
            selected=None,
            no_target_reason=None,
            degraded_reason=result.outcome.execution_status.error_code,
            scored=scored,
            refusal=None,
            decision=None,
            execution_status=result.outcome.execution_status.status,
        )
    return CaseRun(
        kind=(
            CaseKind.SELECT
            if decision.decision is PlannerDecisionOutcome.SELECT
            else CaseKind.NO_TARGET
        ),
        selected=(
            None
            if decision.selected_candidate_id is None
            else str(decision.selected_candidate_id)
        ),
        no_target_reason=decision.no_target_reason,
        degraded_reason=None,
        scored=scored,
        refusal=None,
        decision=decision,
        execution_status=result.outcome.execution_status.status,
    )


def _evidence_of(run: CaseRun) -> str:
    """What the run actually answered, as one printable field."""

    if run.kind is CaseKind.REFUSED:
        assert run.refusal is not None
        return f"REFUSED {run.refusal.error_type}: {run.refusal.message}"
    if run.kind is CaseKind.DEGRADED:
        return f"DEGRADED {run.degraded_reason} (no decision)"
    if run.kind is CaseKind.SELECT:
        return f"SELECT {run.selected}"
    return f"NO_TARGET {run.no_target_reason}"


def _expected_text(case: Mapping[str, Any]) -> str:
    """The case's own ``expected``, rendered for the table."""

    expected = case["expected"]
    if expected["error"]:
        return "error: true"
    if expected["custom"] is not None:
        return f"custom: {expected['custom']}"
    if expected["decision"] == "SELECT":
        return f"SELECT {expected['selected']}"
    return f"NO_TARGET {expected['reason']}"


def _pair_ge(run: CaseRun, higher: str, lower: str) -> tuple[bool, str]:
    """``scored[higher] >= scored[lower]``, with a missing id a divergence
    rather than a crash (the frozen runner's ``except`` arm would have answered
    ``False`` for the same input)."""

    utilities = run.utilities
    if higher not in utilities or lower not in utilities:
        return False, f"scored={dict(run.scored)} (wants {higher}/{lower})"
    return (
        utilities[higher] >= utilities[lower],
        f"{higher}={utilities[higher]} {lower}={utilities[lower]}",
    )


def _judge(
    case: Mapping[str, Any], run: CaseRun, expected: Mapping[str, Any]
) -> tuple[bool, str]:
    """The decision tree itself, one branch per line of the frozen runner.

    The branch order is the frozen runner's own: the ``error`` flag first, then
    the custom predicates in their declared order, then the decision type and
    its payload.
    """

    evidence = _evidence_of(run)
    if expected["error"]:
        return run.kind is CaseKind.REFUSED, evidence
    if run.kind is CaseKind.REFUSED:
        return False, evidence
    custom = expected["custom"]
    if custom == "DEGRADED":
        return run.kind is CaseKind.DEGRADED and run.decision is None, evidence
    if custom == "EQUAL_UTILITY":
        values = [value for _, value in run.scored]
        return (
            len(values) == 2 and abs(values[0] - values[1]) < 1e-9,
            f"scored={dict(run.scored)}",
        )
    if custom == "HI_UTILITY_GE":
        return _pair_ge(run, "hi", "lo")
    if custom == "LOW_COST_UTILITY_GE":
        return _pair_ge(run, "cl", "ch")
    if custom == "ORDER_DETERMINISM":
        reversed_run = run_input(case["input"], reverse=True)
        return (
            reversed_run.decision == run.decision,
            f"{evidence} vs reversed {_evidence_of(reversed_run)}",
        )
    if run.kind.value != expected["decision"]:
        return False, evidence
    if expected["decision"] == "SELECT":
        return run.selected == expected["selected"], evidence
    return run.no_target_reason == expected["reason"], evidence


def verdict_of(case: Mapping[str, Any]) -> CaseVerdict:
    """Replay ``run_stress.py``'s ``run()`` against this repository's chain."""

    run = run_input(case["input"])
    passed, evidence = _judge(case, run, case["expected"])
    return CaseVerdict(
        case_id=str(case["id"]),
        description=str(case.get("description", "")),
        kind=run.kind,
        expected=_expected_text(case),
        evidence=evidence,
        passed=passed,
    )


def stress_table(cases: Sequence[Mapping[str, Any]]) -> tuple[CaseVerdict, ...]:
    """One verdict per case, in the file's own order."""

    return tuple(verdict_of(case) for case in cases)


def stress_report(cases: Sequence[Mapping[str, Any]]) -> str:
    """The table (case → what was answered → PASS/DIVERGENCE), plus a total.

    This is §8's "人工/测试审查" in printable form: one line per case, and a
    divergence names what was answered instead of only that it differed.
    """

    verdicts = stress_table(cases)
    passed = sum(1 for verdict in verdicts if verdict.passed)
    return "\n".join(
        [
            *(verdict.line() for verdict in verdicts),
            f"BF-02 stress: {passed}/{len(verdicts)} PASS",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the suite against a case file and print the table.

    The path is the caller's: ``python -m elc.planner.stress_suite --cases
    behavioral_baselines/planner/planner_stress_cases_v1_1.json``. Exit status
    is 0 exactly when every case's frozen ``expected`` holds.
    """

    parser = argparse.ArgumentParser(
        prog="python -m elc.planner.stress_suite",
        description="replay BF-02's frozen stress cases through this chain",
    )
    parser.add_argument("--cases", required=True)
    arguments = parser.parse_args(argv)
    verdicts = stress_table(load_cases(arguments.cases))
    for verdict in verdicts:
        print(verdict.line())
    passed = sum(1 for verdict in verdicts if verdict.passed)
    print(f"BF-02 stress: {passed}/{len(verdicts)} PASS")
    return 0 if passed == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
