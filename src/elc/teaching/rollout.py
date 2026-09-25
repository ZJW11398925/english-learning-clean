"""The rollout gate — Phase 8 P8-5 (RISK_SPIKE): the stage face, the content
gate, the six observations, and the HOLD this cut answers with.

docs/IMPLEMENTATION_PLAN.md §12 fixes the whole subject in one block: the
rollout order (``manual/user-initiated → Study-first → Balanced → Lounge``),
the six observations, and the one rule about what a *response* to a bad
observation may be ("提高 threshold / policy cost", "而不是修改 Learning
truth"). docs/RUNTIME_ARCHITECTURE.md's automatic path (P8-0..P8-4) is the
thing being rolled out, and BF-02 §10's four content floors are what decides
whether it *can* be: every teaching mode names a minimum §8.1 readiness, and
the shipped corpus's answer is one target at R4 (C1's evidence face) with the
other thirteen reading no level — their sources state no evidence.

This module is the executable half of that block, and it is deliberately
**read-only**: it declares a process-level stage, checks BF-02 §10 against a
readiness table, reads the six observations off durable faces, and answers
GO/HOLD. It writes nothing, opens nothing, calibrates nothing, and touches no
frozen baseline.

**① The stage face.** :class:`RolloutStage` carries §12's four words as
spelled (hyphenated and slashed forms included — the external spelling is the
document's), :data:`ROLLOUT_STAGES` is their order, and the stage's home is a
**process-level declaration**: a construction/injection parameter of whatever
assembles the automatic leg, never a user-data table (§12 is release
configuration; the mode itself is §5.1's ``teaching_frequency``, and the two
are different things). An **undeclared** stage is
:data:`DEFAULT_ROLLOUT_STAGE` = ``manual/user-initiated``, the only stage that
does not run automatic teaching — so "nothing was said" fails closed.

**② The enabled fact, and the one source both legs come from.**
:func:`automatic_teaching_enabled_of` composes the two legs BF-03's switch has
always named:

- the **stage leg** (:func:`stage_allows_automatic`) — only
  ``manual/user-initiated`` refuses; every later stage allows. The criterion is
  monotone by construction: the four words are an order, not a set of four
  independent switches (§12's own arrows);
- the **mode leg** (:func:`mode_allows_automatic`) — §5.1's
  ``teaching_frequency`` through
  :data:`elc.planner.feature_assembly.TEACHING_FREQUENCY_TO_PROFILE`'s own
  ``automatic_teaching_enabled`` flag, i.e. the table the Planner already
  assembles ``FeatureAuthority.automatic_teaching_enabled`` from. ``OFF`` is
  ``False`` there, so ``OFF`` refuses at every stage — this module adds **no
  third source** and re-spells none of the four pairs.

Both legs ``False``-unless-proven: an undeclared stage refuses, an absent or
unknown frequency refuses, and the conjunction is what a caller may act on.

**③ The content gate (BF-02 §10, four floors).** :data:`GATE_ROWS` is §10's
fenced block, one row per line — ``PROBE`` needs R2, ``user-initiated
teaching`` and ``automatic general/review`` need R3, ``automatic
CURRENT_USER_ERROR`` needs R4 — and :func:`rollout_gate_of` counts, per row,
how many targets of a readiness table reach the threshold (the rank is
:data:`READINESS_RANK`, the ladder's index, the same rank the kernel's
``readiness_rank`` reads). A ``None`` level is **never** counted as usable:
§8.1 has no level under R0, and "unknown" is not "R2". §10's second sentence is
carried as the executable rule it states: ``runtime_generated_ready`` is a
user-initiated fallback only — no row or function **of this module** reads it,
and it cannot lower any threshold here. That is where the claim stops: the flag
does have one reader repo-wide, the fallback leg §10 itself permits
(``planner/kernel.py``'s
``candidate.runtime_generated_ready and candidate.user_initiated``), which is
not a row of this gate (see :data:`RUNTIME_GENERATED_READY_RULE`).

The verdict rule is executable, not prose: a row is
:attr:`RolloutVerdict.GO` **iff** :func:`gate_row_verdict` sees at least one
usable target, and the report's overall verdict is GO only when **every** row
is GO (:attr:`RolloutGateReport.verdict`). That conjunction is this cut's
**registered reading** of the task book's rule ("both automatic rows 0 ⇒
overall HOLD"): the book's condition is implied, and the conjunction is the
strict, fail-closed form of it — a rollout cannot enter a stage whose *preceding*
row is empty either. Both readings agree on the shipped corpus (C1's one R4
target makes every row GO, so the answer is GO under either).

**What would turn a row GO is also executable**: each row carries
``required_facts`` — the cumulative §8.1 fact keys
(:func:`elc.curriculum.readiness.required_fact_keys`) that must become present
on at least one target. That is the content-side 补课 list, expressed as the
ladder's own keys rather than as a second prose list, so the checker and the
remediation cannot drift.

**④ The six observations (IP §12), and what each one honestly is.**
:data:`OBSERVATION_SPECS` gives every indicator its definition, its durable
carrier, a one-line honesty declaration, and — for the indicators whose direct
signal this repository **does not carry** — a declared proxy with the reason
and the revisit condition. The one that matters most: ``unwanted
interruption``'s direct signal (a user saying the teaching was unwanted) has
no carrier at all, so the reading is an explicit proxy (automatic moments the
user left with an implicit-exit reason), named as a proxy in the datum itself.
No reading ever fabricates a value: an empty database answers zero, which is
the correct answer, not a gap.

:func:`observations_of` is the pure core over already-read records;
:func:`collect_observations` is the thin collector over
:class:`RolloutObservationPort`. **Five reads, four of which no durable face in
``src/`` answers today** — the ledger's is real
(:meth:`elc.planner.ledger_store.SqliteLedgerStore.read_ledger`), while the
whole-table enumerations (moments / Gate decisions / Planner decisions /
EvidenceClaim count) do not exist. The port is where those shapes are
registered; no production object satisfies it yet, and this module says so
rather than pretending otherwise (see the port's docstring for the Revisit).

**⑤ The HOLD, and where it is held now.** The content gate moved under C1's
evidence face: on the shipped corpus every row reads 1 usable target (the one
R4 target; the other thirteen read ``level=None``) and
:func:`corpus_rollout_gate` answers **GO** — so the content gate no longer
holds the rollout. The rollout is **still HOLD**, carried by the two gates
this module sits beside: the stage leg (no stage is declared, and
:func:`stage_allows_automatic` refuses an undeclared stage) and the
Calibration100 volume gate (14 resources < 100, CORE_A 0 < 30, CORE_C 0 < 2).
What R5 founded the HOLD on — a corpus no target could serve — was C1's to
change; opening the rollout remains the separate adjudication. :data:
`GATE_OPENING_CONDITIONS` and :data:`BACKOFF_MEANS` are the
two condition lists: what opens a row (the ladder's keys, or the report's own
GO), and what a rollout may do when an observation is bad (IP §12: raise the
threshold / policy cost — and this cut only *names* those levers: BF-02
§14/§12's numbers live in the frozen baselines and a retune is §21's
``planner_profile_version++`` plus the full benchmark regression, never an
edit here).

**⑥ The callback into the Gate's own registration.** ``elc/teaching/gate.py``
declares (its control-fact authority 1) that ``automatic_teaching_enabled`` is
"the product mode … crossed with the rollout stage" and registers the Revisit
"p8-5 (rollout gate) lands the … read face for this fact's caller; p8-4 passes
the Planner's value". This module is that read face, and
``elc.runtime.automatic_turn`` now composes the fact the registration
describes: the Planner's assembled value **and** the wiring's declared stage.

**What this module deliberately does not do** (each absence a decision):

- it does not calibrate :data:`elc.teaching.budget.COOLDOWN_WINDOW_SECONDS` /
  ``RECENT_TEACHING_WINDOW_SECONDS``. Those constants' Revisit names p8-5 as a
  possible calibrator, and this cut declines: calibration is BF-03 §21-class
  work (a measurement over real usage), and there is no real usage to measure —
  the rollout is still HOLD, held by the undeclared stage leg and the
  Calibration100 volume gate, no longer by the content gate (C1's corpus
  answers it GO). Registered in the receipt
  and in ``tests/phase8/test_p8_5_honesty.py``;
- it does not open any stage. Nothing here mutates anything, and the shipped
  corpus's answer is HOLD, so a source text that claimed a stage was open would
  be contradicted by this module's own checker (pinned by test);
- it does not read ``runtime_generated_ready`` as a threshold bypass (§10's
  second sentence), and it does not invent a fifth readiness level or a new
  readiness threshold rule: the ranks and the facts are the ladder's.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Protocol, Sequence

from elc.curriculum.readiness import (
    READINESS_LEVELS,
    ReadinessAssessment,
    required_fact_keys,
)
from elc.planner.feature_assembly import TEACHING_FREQUENCY_TO_PROFILE
from elc.planner.ledger import LedgerEvent, PlanningLedger, overexposure_of
from elc.platform.types import (
    Err,
    Ok,
    PlannerDecision,
    PlannerDecisionOutcome,
    Result,
)
from elc.teaching.types import (
    AbortReason,
    GateDecisionContext,
    GateDecisionRecord,
    MomentSource,
    TeachingMomentRecord,
)
from elc.user_config.types import TeachingFrequency

__all__ = [
    "AUTOMATIC_STAGES",
    "BACKOFF_MEANS",
    "DEFAULT_ROLLOUT_STAGE",
    "GATE_OPENING_CONDITIONS",
    "GATE_ROWS",
    "NEUTRAL_OVEREXPOSURE_BANDS",
    "OBSERVATION_INDICATORS",
    "OBSERVATION_SPECS",
    "READINESS_RANK",
    "ROLLOUT_STAGES",
    "RUNTIME_GENERATED_READY_RULE",
    "UNWANTED_INTERRUPTION_PROXY_WORDS",
    "GateRowSpec",
    "ObservationReading",
    "ObservationSpec",
    "ReadinessTableFace",
    "RolloutGateReport",
    "RolloutGateRow",
    "RolloutObservationPort",
    "RolloutStage",
    "RolloutVerdict",
    "automatic_teaching_enabled_of",
    "collect_observations",
    "corpus_rollout_gate",
    "gate_row_verdict",
    "mode_allows_automatic",
    "observations_of",
    "opening_conditions",
    "rollout_gate_of",
    "stage_allows_automatic",
    "usable_targets_for",
]


# ---------------------------------------------------------------------------
# ① The stage face — docs/IMPLEMENTATION_PLAN.md §12's order, word for word
# ---------------------------------------------------------------------------


class RolloutStage(StrEnum):
    """§12's rollout order, as four words.

    The **spelling is the document's** — ``manual/user-initiated`` keeps its
    slash, ``Study-first`` its hyphen — because §12's block *is* the external
    vocabulary a rollout declares (§12 calls the order a 建议顺序 and names no
    enum; the internal member names are this cut's, the values are the
    document's). The order is meaningful: see
    :data:`AUTOMATIC_STAGES`.

    A stage is a **process-level declaration**, not user data: nothing in
    ``§5.1``/``§9`` carries it, it has no table, and BF-05's deletion scopes do
    not apply to it (there is nothing to delete). A caller declares it where it
    constructs the automatic leg's wiring; the default is the conservative
    one.
    """

    MANUAL_USER_INITIATED = "manual/user-initiated"
    STUDY_FIRST = "Study-first"
    BALANCED = "Balanced"
    LOUNGE = "Lounge"


#: §12's order, first → last. The external spellings above are asserted equal
#: to the document's block (tests/phase8/test_p8_5_honesty.py parses §12).
ROLLOUT_STAGES: tuple[RolloutStage, ...] = (
    RolloutStage.MANUAL_USER_INITIATED,
    RolloutStage.STUDY_FIRST,
    RolloutStage.BALANCED,
    RolloutStage.LOUNGE,
)

#: The stages that may run automatic teaching — every stage **after** the
#: manual one, which is §12's suggestion read as the order it is (a rollout
#: starts with user-initiated teaching only and opens the automatic switch by
#: moving to the next stage). Membership is the criterion
#: :func:`stage_allows_automatic` implements; it is monotone in
#: :data:`ROLLOUT_STAGES` by construction (a test pins that no later stage is
#: outside it).
AUTOMATIC_STAGES: tuple[RolloutStage, ...] = (
    RolloutStage.STUDY_FIRST,
    RolloutStage.BALANCED,
    RolloutStage.LOUNGE,
)

#: The fail-closed stage: what an **undeclared** stage means. §12's first
#: stage is the only one that does not teach automatically, so "nothing was
#: declared" and "rollout has not started" are the same state.
DEFAULT_ROLLOUT_STAGE: RolloutStage = RolloutStage.MANUAL_USER_INITIATED


def stage_allows_automatic(stage: RolloutStage | None) -> bool:
    """The stage leg of ``automatic_teaching_enabled``: does this stage run
    automatic teaching at all?

    ``None`` — an undeclared stage — is :data:`DEFAULT_ROLLOUT_STAGE`'s answer
    (``False``): the fail-closed reading stated in the module docstring. A
    value that is not a :class:`RolloutStage` **raises** rather than being
    read as either answer: an unknown word is a contract breach, not a
    conservative stage (the repository's "an unknown word is refused, not
    guessed" rule — ``elc.runtime.automatic_turn.conversation_priority_view_of``
    takes the same posture one package over).
    """

    if stage is None:
        return False
    if not isinstance(stage, RolloutStage):
        raise ValueError(
            f"unknown rollout stage {stage!r}: docs/IMPLEMENTATION_PLAN.md"
            f" §12 names {[item.value for item in ROLLOUT_STAGES]}, and a"
            " stage this module cannot place is not read as a conservative"
            " one"
        )
    return stage in AUTOMATIC_STAGES


def mode_allows_automatic(teaching_frequency: TeachingFrequency | None) -> bool:
    """The §5.1 mode leg: the switch
    :data:`elc.planner.feature_assembly.TEACHING_FREQUENCY_TO_PROFILE` already
    carries.

    The **one source** is that table's ``automatic_teaching_enabled`` flag —
    ``OFF ⇒ False`` is its own row's value, not a second rule spelled here —
    and an absent or unknown frequency answers ``False`` (fail-closed; the
    Planner's own ``profile_mapping_of`` reports the same gap as a missing
    authority rather than guessing a profile).
    """

    if teaching_frequency is None:
        return False
    mapping = TEACHING_FREQUENCY_TO_PROFILE.get(teaching_frequency)
    return mapping is not None and mapping.automatic_teaching_enabled


def automatic_teaching_enabled_of(
    *, stage: RolloutStage | None, teaching_frequency: TeachingFrequency | None
) -> bool:
    """The composed read face: stage leg × §5.1 mode leg (module ②).

    This is the face ``elc/teaching/gate.py``'s authority-1 registration asks
    for ("the product mode … crossed with the rollout stage"), for a caller
    that holds the policy word. A caller that holds the **Planner's assembled
    value** instead — ``FeatureAuthority.automatic_teaching_enabled``, the
    value P8-1's disposal F2 required the wiring to pass — composes it with
    :func:`stage_allows_automatic` directly, which is what
    ``elc.runtime.automatic_turn`` does: the value is the same table's answer,
    read once, so composing it again here would be a second read that could
    disagree.
    """

    return stage_allows_automatic(stage) and mode_allows_automatic(
        teaching_frequency
    )


# ---------------------------------------------------------------------------
# ② The content gate — BF-02 §10's four floors, counted
# ---------------------------------------------------------------------------


class RolloutVerdict(StrEnum):
    """One row's (or the report's) answer. A word of this cut's: §12 and BF-02
    §10 name no verdict vocabulary, and the two words are the ones the task
    book's receipt speaks."""

    GO = "GO"
    HOLD = "HOLD"


#: The ladder's index — "the rank is the ladder's index (R0 lowest)", the same
#: reading ``elc.planner.kernel.READINESS_RANK`` carries ("the reference
#: profile's ``readiness_rank``"). Derived from the canonical vocabulary
#: (:data:`elc.curriculum.readiness.READINESS_LEVELS`) so the two cannot drift
#: in **order**; a test holds it against the kernel's table by value.
READINESS_RANK: Mapping[str, int] = {
    level: index for index, level in enumerate(READINESS_LEVELS)
}

#: BF-02 §10's second sentence, quoted as the rule it is: "``runtime_generated_ready``
#: 仅允许作为 ``user-initiated`` 的 fallback/escape hatch. 它**不能**让
#: ``automatic CURRENT_USER_ERROR R1/R2/R3`` 绕过 R4，也不能让普通 proactive
#: automatic target 绕过 R3." No row of :data:`GATE_ROWS` reads that flag, and
#: no function in this module takes it: a fallback that could raise a row's
#: count would be exactly the bypass §10 forbids. Both halves of that sentence
#: are **this module's** claim: repo-wide the flag has one reader — the
#: user-initiated leg §10 permits (``elc.planner.kernel``'s
#: ``candidate.runtime_generated_ready and candidate.user_initiated``, which
#: this gate neither reads nor counts).
RUNTIME_GENERATED_READY_RULE = (
    "runtime_generated_ready is a user-initiated fallback only: it cannot let"
    " an automatic CURRENT_USER_ERROR target below R4 through, and it cannot"
    " let an ordinary proactive automatic target below R3 through"
)


@dataclass(frozen=True)
class GateRowSpec:
    """One BF-02 §10 row: the word, the floor, and what opening it requires.

    ``row_word`` is §10's own line with its threshold removed — ``PROBE``,
    ``user-initiated teaching``, ``automatic general/review``, ``automatic
    CURRENT_USER_ERROR`` — so a reader can hold the row against the
    document's block line by line (pinned by test). ``automatic`` marks the
    two rows whose targets are opened by the *automatic* path (the rows the
    rollout's switch governs). ``required_facts`` is the cumulative §8.1 fact
    key set of ``required_level``, read off the ladder's own
    ``required_fact_keys`` — the executable form of "what content work opens
    this row".
    """

    row_word: str
    required_level: str
    automatic: bool
    required_facts: tuple[str, ...]


def _row_spec(row_word: str, required_level: str, *, automatic: bool) -> GateRowSpec:
    return GateRowSpec(
        row_word=row_word,
        required_level=required_level,
        automatic=automatic,
        required_facts=required_fact_keys(required_level),
    )


#: BF-02 §10's block (`behavioral_baselines/planner/
#: BF-02_Planner_Decision_Spec_v1.1.md` lines 290–322), row for row, in the
#: document's order. The two ``automatic`` rows are §10's own words
#: ("automatic general/review", "automatic CURRENT_USER_ERROR"); the other two
#: are the modes §12's rollout order starts from (``PROBE`` is the Planner's
#: own probe profile; ``user-initiated teaching`` is §12's first stage).
GATE_ROWS: tuple[GateRowSpec, ...] = (
    _row_spec("PROBE", "R2_PLANNER_READY", automatic=False),
    _row_spec("user-initiated teaching", "R3_TEACHING_READY", automatic=False),
    _row_spec("automatic general/review", "R3_TEACHING_READY", automatic=True),
    _row_spec("automatic CURRENT_USER_ERROR", "R4_DETECTION_READY", automatic=True),
)


def gate_row_verdict(usable_targets: int) -> RolloutVerdict:
    """One row's verdict — **the** executable condition of this cut.

    GO iff at least one target reaches the row's floor. There is no partial
    credit, no "almost ready", and no other input: a row that no target can
    serve is HOLD — which, since C1's evidence face, is the answer **no** row
    gives over the shipped corpus (its one R4 target serves all four; before
    C1 it served none).
    """

    return RolloutVerdict.GO if usable_targets > 0 else RolloutVerdict.HOLD


def usable_targets_for(
    levels: Iterable[str | None], *, required_level: str
) -> int:
    """How many of ``levels`` reach ``required_level`` on the ladder's rank.

    A ``None`` level is **not** counted (it is not R0: §8.1 has no level there
    and the honest answer to "which level" is none), and neither is a word the
    ladder does not carry — an unknown level would otherwise compare as
    whatever ``READINESS_RANK`` happens to hold, and it does not hold one.
    """

    required = READINESS_RANK.get(required_level)
    if required is None:
        raise ValueError(f"unknown readiness level: {required_level!r}")
    usable = 0
    for level in levels:
        if level is None:
            continue
        rank = READINESS_RANK.get(level)
        if rank is not None and rank >= required:
            usable += 1
    return usable


@dataclass(frozen=True)
class RolloutGateRow:
    """One row's reading: the floor, the count, the verdict, and the facts its
    threshold needs (the spec's own set, carried so a reader of the report does
    not have to look it up)."""

    row_word: str
    required_level: str
    automatic: bool
    usable_targets: int
    verdict: RolloutVerdict
    required_facts: tuple[str, ...]

    def line(self) -> str:
        """The row as one readable line (the receipt's own shape)."""

        return (
            f"{self.row_word}: required {self.required_level}, usable targets"
            f" {self.usable_targets} → {self.verdict.value}"
        )


@dataclass(frozen=True)
class RolloutGateReport:
    """Four rows, one verdict, and the counting behind them.

    ``verdict`` is :attr:`RolloutVerdict.GO` only when **every** row is GO
    (the registered conjunction reading, module docstring); otherwise HOLD,
    with :attr:`blocking_rows` naming each row that answers HOLD.
    ``automatic_verdict`` is the same rule over the two automatic rows alone,
    so a reader can see the task book's condition separately from the
    conjunction. ``targets_considered`` / ``targets_without_level`` count the
    table the report was made over (the shipped corpus answers 14 and 13 —
    C1's one leveled target leaves thirteen without a level);
    ``unknown_levels`` names any level word the ladder does not carry (empty
    for every answer the ladder itself produces).
    """

    rows: tuple[RolloutGateRow, ...]
    verdict: RolloutVerdict
    targets_considered: int
    targets_without_level: int
    unknown_levels: tuple[str, ...]

    def row(self, row_word: str) -> RolloutGateRow:
        for entry in self.rows:
            if entry.row_word == row_word:
                return entry
        raise ValueError(f"unknown gate row: {row_word!r}")

    @property
    def blocking_rows(self) -> tuple[RolloutGateRow, ...]:
        return tuple(
            entry for entry in self.rows if entry.verdict is RolloutVerdict.HOLD
        )

    @property
    def automatic_rows(self) -> tuple[RolloutGateRow, ...]:
        return tuple(entry for entry in self.rows if entry.automatic)

    @property
    def automatic_verdict(self) -> RolloutVerdict:
        return (
            RolloutVerdict.GO
            if all(
                entry.verdict is RolloutVerdict.GO
                for entry in self.automatic_rows
            )
            else RolloutVerdict.HOLD
        )

    def summary(self) -> tuple[str, ...]:
        """The report as readable lines (rows first, verdict last)."""

        lines = [entry.line() for entry in self.rows]
        lines.append(
            f"targets: {self.targets_considered} considered,"
            f" {self.targets_without_level} without a level"
            + (
                f", unreadable level words {list(self.unknown_levels)}"
                if self.unknown_levels
                else ""
            )
        )
        lines.append(
            f"verdict: {self.verdict.value} (automatic rows:"
            f" {self.automatic_verdict.value})"
        )
        for entry in self.blocking_rows:
            lines.append(f"blocked: {entry.line()}")
        return tuple(lines)


def _row_of(
    spec: GateRowSpec, levels: Sequence[str | None]
) -> RolloutGateRow:
    """One row's reading, made the only way a row is ever made."""

    usable = usable_targets_for(levels, required_level=spec.required_level)
    return RolloutGateRow(
        row_word=spec.row_word,
        required_level=spec.required_level,
        automatic=spec.automatic,
        usable_targets=usable,
        verdict=gate_row_verdict(usable),
        required_facts=spec.required_facts,
    )


def rollout_gate_of(
    targets: Iterable[tuple[str, str | None]],
) -> RolloutGateReport:
    """Check BF-02 §10 against one readiness table.

    ``targets`` is ``(target_id, level)`` pairs — the shape
    ``elc.curriculum.store.CurriculumContentStore.readiness_by_target`` answers
    once its assessments are flattened. The report is a pure function of the
    pairs: no IO, no clock, no store.
    """

    levels: list[str | None] = []
    unknown: list[str] = []
    for _, level in targets:
        levels.append(level)
        if level is not None and level not in READINESS_RANK:
            unknown.append(level)
    rows = tuple(_row_of(spec, levels) for spec in GATE_ROWS)
    verdict = (
        RolloutVerdict.GO
        if all(entry.verdict is RolloutVerdict.GO for entry in rows)
        else RolloutVerdict.HOLD
    )
    return RolloutGateReport(
        rows=rows,
        verdict=verdict,
        targets_considered=len(levels),
        targets_without_level=sum(1 for level in levels if level is None),
        unknown_levels=tuple(sorted(set(unknown))),
    )


class ReadinessTableFace(Protocol):
    """The §8.1 corpus table, as the one read this checker needs.

    Satisfied structurally by
    :class:`elc.curriculum.store.CurriculumContentStore` — its
    ``readiness_by_target`` is the same method P5-1 landed, so no adapter
    stands between the checker and the ladder (the ``ReadinessPort``
    precedent one package over).
    """

    def readiness_by_target(self) -> Result[tuple[ReadinessAssessment, ...]]:
        ...


def corpus_rollout_gate(face: ReadinessTableFace) -> Result[RolloutGateReport]:
    """The checker over a real readiness table (module ⑤).

    An ``Err`` from the table is returned untouched: a corpus whose levels
    cannot be read has no gate answer, and this function does not manufacture
    a HOLD (or a GO) out of a failed read — the two are different facts.
    """

    table = face.readiness_by_target()
    if isinstance(table, Err):
        return table
    pairs = tuple(
        (str(assessment.target_id), assessment.level)
        for assessment in table.value
    )
    return Ok(rollout_gate_of(pairs))


def opening_conditions() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """What would open each row, as executable conditions (module ③).

    One tuple per row: ``(row_word, required_level, required_facts)``. The
    condition is the row's own verdict rule plus the fact set: the row turns GO
    when at least one target carries every key in ``required_facts`` (the
    cumulative §8.1 key set, in ladder order) — i.e. when the content-side 补课
    lands on a real target. Nothing else turns a row GO: no configuration, no
    threshold, no flag this module reads.
    """

    return tuple(
        (spec.row_word, spec.required_level, spec.required_facts)
        for spec in GATE_ROWS
    )


#: The two levers IP §12 allows as a response to a bad observation, plus the
#: one it forbids. Declared as data because the cut **names** the levers and
#: moves neither: BF-02 §14's ``automatic_activation_threshold`` and BF-02
#: §12's policy cost live in the frozen baselines, and a retune is BF-02 §21's
#: process (``planner_profile_version++`` + the full benchmark regression + a
#: decision diff review), not an edit in this repository's source. Revisit: a
#: calibration decision lands (BF-02 §21 / IP §13) and the numbers move
#: through that process.
BACKOFF_MEANS: tuple[str, ...] = (
    "raise the automatic activation threshold (BF-02 §14's"
    " automatic_activation_threshold, retuned only through BF-02 §21:"
    " planner_profile_version++ with the full benchmark regression and a"
    " decision diff review)",
    "raise the policy cost (BF-02 §12's weight table, same §21 process)",
    "never by changing Learning truth (docs/IMPLEMENTATION_PLAN.md §12;"
    " Learning evidence is BF-01's and this module only reads it)",
)

#: The four rows' opening conditions in one flat list (module ③/⑤): the row
#: word, its floor, and the executable answer to "what opens this row".
GATE_OPENING_CONDITIONS: tuple[tuple[str, str], ...] = tuple(
    (
        spec.row_word,
        f"at least one target reaches {spec.required_level} (its cumulative"
        f" §8.1 facts present)",
    )
    for spec in GATE_ROWS
)


# ---------------------------------------------------------------------------
# ③ The six observations — docs/IMPLEMENTATION_PLAN.md §12
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationSpec:
    """One §12 indicator, declared whole: what it means, where it can be read,
    what this repository honestly can and cannot answer, and — when there is
    no direct carrier — the proxy that stands in for it."""

    indicator: str
    definition: str
    carrier: str
    honesty: str
    proxy_of: str | None
    proxy_because: str | None
    revisit: str


#: §12's block is six **indicator words** (``docs/IMPLEMENTATION_PLAN.md``
#: Detail Block 12's 观察 list), and what is word for word is the
#: ``indicator`` field — each spec carries one of the document's six words, in
#: the document's order (pinned by test). ``definition`` is this module's own
#: English gloss of that word, a sentence rather than the document's text.
#: Each spec's ``carrier`` names the durable face that answers it (or says the
#: direct signal has none); ``honesty`` is the one-line truth about what the
#: reading is; ``proxy_of``/``proxy_because`` are present only where a proxy
#: stands in for a signal this repository does not carry (never silently: a
#: proxy is declared here *and* carried on every reading it produces).
OBSERVATION_SPECS: tuple[ObservationSpec, ...] = (
    ObservationSpec(
        indicator="unwanted interruption",
        definition=(
            "how often automatic teaching was shown at a moment the user did"
            " not want it"
        ),
        carrier=(
            "teaching_moment (source=AUTOMATIC) joined with abort_reason —"
            " the implicit-exit words only"
        ),
        honesty=(
            "the direct signal (a user saying the teaching was unwanted) has"
            " **no carrier** in this repository: no feedback, rating or"
            " complaint table exists. The reading is an explicit proxy, and"
            " the ledger's user_skip is deliberately left to the skip/reject"
            " indicator so the two do not count one fact twice."
        ),
        proxy_of="a user-reported unwanted interruption",
        proxy_because=(
            "an automatic moment the user left with an implicit-exit reason"
            " (USER_TOPIC_SHIFT / AMBIGUOUS_EXIT) is the closest durable trace"
            " of the same friction: the user did not decide about the teaching,"
            " they moved away from it. It is a *lower bound* on the friction —"
            " a user who stayed and disliked it leaves no trace at all — and it"
            " is only comparable across stages of the same product, never a"
            " count of complaints."
        ),
        revisit=(
            "a feedback / engagement carrier lands (a skip-with-reason pair, a"
            " rating, BF-03 §17's session state gaining a dislike signal) —"
            " then the proxy is replaced by the real reading"
        ),
    ),
    ObservationSpec(
        indicator="skip/reject",
        definition=(
            "how often the user explicitly refused or abandoned the teaching"
            " that was offered"
        ),
        carrier=(
            "planning_ledger_event.event = user_skip (the §20 log), plus"
            " teaching_moment.abort_reason in {USER_SKIP,"
            " USER_REJECTED_TARGET}"
        ),
        honesty=(
            "readable today: the ledger half is a real durable log with a real"
            " whole-ledger read face (SqliteLedgerStore.read_ledger), and the"
            " moment half reads the §15 column. The reading's **value is the"
            " ledger's count** (the §20 log is the canonical record of a"
            " rejection) and the moment's abort count is carried beside it in"
            " the breakdown — one skip can appear in both (a moment's abort"
            " and its ledger event are two records of one act), so the two are"
            " never summed into one number."
        ),
        proxy_of=None,
        proxy_because=None,
        revisit=(
            "the ledger's recent_skips projection and the moment aborts are"
            " reconciled by a canonical rule (which of the two is the fact) —"
            " then a single number becomes stateable"
        ),
    ),
    ObservationSpec(
        indicator="continuation",
        definition=(
            "how often an already-open teaching moment was continued (and how"
            " often the runtime declined to continue it)"
        ),
        carrier=(
            "gate_decision.context (AUTO_CONTINUE / USER_REQUESTED_CONTINUE"
            " / OPEN)"
        ),
        honesty=(
            "readable today up to a point: the durable Gate decisions carry"
            " their context word, so the continuation decisions are countable."
            " What is **not** readable is the rate: it needs the number of live"
            " automatic moments as its denominator, and that count has no"
            " whole-table face. The reading therefore reports the decision"
            " counts by context and names the missing denominator instead of"
            " inventing a percentage."
        ),
        proxy_of=None,
        proxy_because=None,
        revisit=(
            "a moment-count face (or a report that reads moments per"
            " conversation) lands — then the denominator exists and a rate can"
            " be stated"
        ),
    ),
    ObservationSpec(
        indicator="NO_TARGET appropriateness",
        definition=(
            "whether answering 'nothing worth teaching' was the right answer"
            " at the moments the Planner answered it"
        ),
        carrier=(
            "planner_decision.decision (SELECT / NO_TARGET) with"
            " no_target_reason text"
        ),
        honesty=(
            "**the wrong table is easy to name here, so this module names the"
            " right one**: NO_TARGET is a ``planner_decision`` word, never a"
            " ``planner_execution_status`` word — the status vocabulary is"
            " SUCCEEDED/DEGRADED/FAILED/UNAVAILABLE and §14.1's separation is"
            " exactly that a failure is not laundered into NO_TARGET. The"
            " *distribution* is readable; *appropriateness* (was it right to"
            " not teach?) is a judgement no durable signal records, so this"
            " reading reports the counts and the reasons and claims no"
            " appropriateness verdict."
        ),
        proxy_of=None,
        proxy_because=None,
        revisit=(
            "a review or outcome signal about NO_TARGET cycles lands (an"
            " engagement read, a user signal, a replayable benchmark over real"
            " turns) — then appropriateness becomes decidable"
        ),
    ),
    ObservationSpec(
        indicator="overexposure",
        definition=(
            "how concentrated the teaching exposure is — how many targets are"
            " being presented again and again inside the ledger's own window."
            " The value counts the rows whose ledger band is not neutral"
            " (NEUTRAL_OVEREXPOSURE_BANDS), so the ladder's own LOW rung —"
            " one presentation inside the window — is a recorded exposure"
            " too; the per-band breakdown is the reading's granularity, not a"
            " second threshold"
        ),
        carrier=(
            "planning_ledger rows through elc.planner.ledger.overexposure_of"
            " (the log's presentations inside the row's window or the declared"
            " fallback window)"
        ),
        honesty=(
            "readable today: this is a real durable reading over the §20 log,"
            " computed by the ledger's own core function (this module"
            " re-implements neither the window nor the band table). The count"
            " is per key at one instant; a workspace-level rate needs the same"
            " missing denominator the continuation reading names. What the"
            " scalar answers is \"how many targets carry a recorded exposure"
            " at this instant\", not \"how many are past a chosen danger"
            " line\" — the bands are carried so a reader can apply their own"
            " line without this module inventing one."
        ),
        proxy_of=None,
        proxy_because=None,
        revisit=(
            "a canonical calibration fixes the fallback window (today a"
            " declared 7 days in elc.planner.ledger) — the reading follows it"
        ),
    ),
    ObservationSpec(
        indicator="Evidence gain",
        definition=(
            "how much real learning evidence the teaching produced"
            " (docs/PRODUCT_CONTRACT.md's goal, never a mastery claim)"
        ),
        carrier="evidence_claim rows (the §6 durable claims, DATA_MODEL §6)",
        honesty=(
            "readable today as a count, with one registered limit: 'gain' per"
            " teaching act needs claims joined to the presentations that"
            " produced them, and no durable face answers that join (claims"
            " carry evidence_group / opportunity provenance, not exposure"
            " provenance). The reading is the count and says so — the shipped"
            " database answers 0, which is the correct number, not a gap."
        ),
        proxy_of=None,
        proxy_because=None,
        revisit=(
            "the rollout report that joins claims to exposures lands (it needs"
            " an exposure→claim provenance leg) — then the per-teaching rate"
            " replaces the bare count"
        ),
    ),
)

#: §12's six words, in the document's order (derived from the specs so the two
#: cannot drift).
OBSERVATION_INDICATORS: tuple[str, ...] = tuple(
    spec.indicator for spec in OBSERVATION_SPECS
)

#: The abort reasons the unwanted-interruption proxy counts: the two words
#: that mean "the user moved away without deciding about the teaching"
#: (§7's USER_TOPIC_SHIFT is a topic shift; AMBIGUOUS_EXIT is an exit the
#: runtime could not classify). An explicit USER_SKIP / USER_REJECTED_TARGET
#: is a *decision about the teaching* and belongs to skip/reject.
UNWANTED_INTERRUPTION_PROXY_WORDS: tuple[str, ...] = (
    AbortReason.USER_TOPIC_SHIFT.value,
    AbortReason.AMBIGUOUS_EXIT.value,
)

#: The abort reasons the skip/reject reading counts from the moment side.
_SKIP_REJECT_MOMENT_WORDS: tuple[str, ...] = (
    AbortReason.USER_SKIP.value,
    AbortReason.USER_REJECTED_TARGET.value,
)

#: The overexposure bands that mean "nothing recorded": a row answering one of
#: these is not counted by the reading. The **words** are
#: ``elc.planner.ledger.OVEREXPOSURE_RUNGS``' (the frozen reference profile's
#: keys); this cut decides only which of them count as "not exposed" — and the
#: decision is *only* ``NONE``, because the ladder's own semantics is that the
#: LOW rung (one presentation inside the window) is already a recorded
#: exposure. Counting MEDIUM-and-above would be a second, undeclared danger
#: line; the band breakdown is what carries that granularity instead.
NEUTRAL_OVEREXPOSURE_BANDS: tuple[str, ...] = ("NONE",)


@dataclass(frozen=True)
class ObservationReading:
    """One indicator's reading: the value, the words behind it, and the spec
    it was made under (so the honesty declaration travels with the number)."""

    indicator: str
    value: int
    breakdown: tuple[tuple[str, int], ...]
    spec: ObservationSpec

    @property
    def carrier(self) -> str:
        return self.spec.carrier

    @property
    def is_proxy(self) -> bool:
        return self.spec.proxy_of is not None

    def line(self) -> str:
        """The reading as one readable line."""

        detail = ", ".join(f"{word}={count}" for word, count in self.breakdown)
        proxy = " (proxy)" if self.is_proxy else ""
        return f"{self.indicator}{proxy}: {self.value} [{detail}]"


def _spec_of(indicator: str) -> ObservationSpec:
    for spec in OBSERVATION_SPECS:
        if spec.indicator == indicator:
            return spec
    raise ValueError(f"unknown observation indicator: {indicator!r}")


def _counts(pairs: Iterable[tuple[str, int]]) -> tuple[tuple[str, int], ...]:
    """A deterministic word → count table (sorted by word, zero counts kept:
    a zero is a reading too)."""

    merged: dict[str, int] = {}
    for word, count in pairs:
        merged[word] = merged.get(word, 0) + count
    return tuple(sorted(merged.items()))


def _ledger_event_count(ledger: PlanningLedger, event: LedgerEvent) -> int:
    return sum(
        1
        for row in ledger.rows.values()
        for record in row.events
        if record.event is event
    )


def observations_of(
    *,
    moments: Sequence[TeachingMomentRecord],
    gate_decisions: Sequence[GateDecisionRecord],
    planner_decisions: Sequence[PlannerDecision],
    evidence_claim_count: int,
    ledger: PlanningLedger,
    as_of: str,
) -> tuple[ObservationReading, ...]:
    """The six readings, over already-read records — the pure core.

    Every count is a count of the records handed in: the same function over an
    empty database answers all zeros (the honest reading), and over the
    p8-4 world's real rows it answers what those rows say. No clock is read and
    nothing is classified by wall time: ``as_of`` is the caller's instant, the
    one the overexposure window ends at (the same instant every other view
    takes).
    """

    automatic_moments = [
        moment
        for moment in moments
        if moment.source is MomentSource.AUTOMATIC
    ]
    interruption_words = set(UNWANTED_INTERRUPTION_PROXY_WORDS)
    skip_words = set(_SKIP_REJECT_MOMENT_WORDS)

    interruption_breakdown = _counts(
        (str(moment.abort_reason), 1)
        for moment in automatic_moments
        if moment.abort_reason in interruption_words
    )
    interruption = sum(count for _, count in interruption_breakdown)

    ledger_skips = _ledger_event_count(ledger, LedgerEvent.USER_SKIP)
    moment_skips = sum(
        1 for moment in moments if moment.abort_reason in skip_words
    )
    skip_breakdown = _counts(
        (
            ("ledger.user_skip", ledger_skips),
            ("moment.abort_reason", moment_skips),
        )
    )
    continuation_breakdown = _counts(
        (str(record.context), 1) for record in gate_decisions
    )
    continuation = sum(
        1
        for record in gate_decisions
        if record.context is GateDecisionContext.AUTO_CONTINUE
    )

    decision_breakdown = _counts(
        (str(decision.decision), 1) for decision in planner_decisions
    )
    no_target = sum(
        1
        for decision in planner_decisions
        if decision.decision is PlannerDecisionOutcome.NO_TARGET
    )

    overexposure_breakdown = _counts(
        (overexposure_of(row, as_of=as_of).band, 1)
        for row in ledger.rows.values()
    )
    overexposed = sum(
        1
        for row in ledger.rows.values()
        if overexposure_of(row, as_of=as_of).band
        not in NEUTRAL_OVEREXPOSURE_BANDS
    )

    return (
        ObservationReading(
            indicator="unwanted interruption",
            value=interruption,
            breakdown=interruption_breakdown,
            spec=_spec_of("unwanted interruption"),
        ),
        ObservationReading(
            indicator="skip/reject",
            value=ledger_skips,
            breakdown=skip_breakdown,
            spec=_spec_of("skip/reject"),
        ),
        ObservationReading(
            indicator="continuation",
            value=continuation,
            breakdown=continuation_breakdown,
            spec=_spec_of("continuation"),
        ),
        ObservationReading(
            indicator="NO_TARGET appropriateness",
            value=no_target,
            breakdown=decision_breakdown,
            spec=_spec_of("NO_TARGET appropriateness"),
        ),
        ObservationReading(
            indicator="overexposure",
            value=overexposed,
            breakdown=overexposure_breakdown,
            spec=_spec_of("overexposure"),
        ),
        ObservationReading(
            indicator="Evidence gain",
            value=evidence_claim_count,
            breakdown=(("evidence_claim", evidence_claim_count),),
            spec=_spec_of("Evidence gain"),
        ),
    )


class RolloutObservationPort(Protocol):
    """The five reads the six observations need — and the honest state of each.

    **One of the five exists** as a durable read face today:
    ``read_ledger`` is :meth:`elc.planner.ledger_store.SqliteLedgerStore.
    read_ledger`'s shape (rows with their logs, obligations, version), and the
    skip/reject and overexposure readings run on it. The other four are
    **whole-table enumerations no durable face in ``src/`` answers yet** — the
    stores read moments / gate decisions / planner decisions / claims by key or
    by conversation, never as a table — so **no production object satisfies
    this port today**, and this port is where the shapes a rollout report needs
    are registered rather than invented per call site:

    - ``list_moments`` — every §15 moment row (the abort-reason distribution);
    - ``list_gate_decisions`` — every §14.1 decision row (the context counts);
    - ``list_planner_decisions`` — every §14 decision row (SELECT/NO_TARGET);
    - ``count_evidence_claims`` — the §6 claim count (one number, no body).

    The rollout report (or a dashboard) that needs them lands them; until then
    a caller that holds a connection can satisfy the port with four read-only
    probes, which is what ``tests/phase8/p8_5_world.py`` does to prove the
    readings run over a real app.db. Revisit: the first production rollout
    report lands, and the four faces move to the stores that own those tables
    (then this port keeps its shapes and gains real implementers).
    """

    def list_moments(self) -> Result[Sequence[TeachingMomentRecord]]:
        ...

    def list_gate_decisions(self) -> Result[Sequence[GateDecisionRecord]]:
        ...

    def list_planner_decisions(self) -> Result[Sequence[PlannerDecision]]:
        ...

    def count_evidence_claims(self) -> Result[int]:
        ...

    def read_ledger(self) -> Result[PlanningLedger]:
        ...


def collect_observations(
    port: RolloutObservationPort, *, as_of: str
) -> Result[tuple[ObservationReading, ...]]:
    """Read the five faces and answer §12's six readings.

    A failed read is returned untouched (the caller's ``Err``): a rollout
    report that cannot read its inputs must say so — it has no partial number
    to publish, and this function invents none (the ``_read``-family posture of
    the runtime assembly, one package over).
    """

    moments = port.list_moments()
    if isinstance(moments, Err):
        return moments
    gate_decisions = port.list_gate_decisions()
    if isinstance(gate_decisions, Err):
        return gate_decisions
    planner_decisions = port.list_planner_decisions()
    if isinstance(planner_decisions, Err):
        return planner_decisions
    claims = port.count_evidence_claims()
    if isinstance(claims, Err):
        return claims
    ledger = port.read_ledger()
    if isinstance(ledger, Err):
        return ledger
    return Ok(
        observations_of(
            moments=moments.value,
            gate_decisions=gate_decisions.value,
            planner_decisions=planner_decisions.value,
            evidence_claim_count=claims.value,
            ledger=ledger.value,
            as_of=as_of,
        )
    )
