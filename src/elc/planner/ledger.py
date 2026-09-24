"""PlanningLedger — the exposure and coverage-debt book, as a pure core (P7-3).

Three canonical documents describe this object, and this module is all three
made executable without a table:

docs/DATA_MODEL.md §14's column set, verbatim (it opens with its own rule)::

    ### PlanningLedger

    不记录 mastery。

    target/family last_selected_at
    last_presented_at
    teaching_exposure_counts
    probe_counts
    review_offers
    recent_skips/rejections
    overexposure_window
    coverage_obligations[]
      obligation_key
      scope_type
      target_or_family_id
      goal_id?
      window_start
      window_end
      debt_value
      accrual_paused
      pause_reason?
      last_served_at?
      last_engaged_at?
    coverage_debt_rollups
    recent_target_families
    version

docs/RUNTIME_ARCHITECTURE.md §20's five events and its two rules, verbatim::

    ## 20. PlanningLedger

    区分：

    candidate_selected
    teaching_presented
    hint_presented
    reveal_presented
    user_skip

    `SELECT != exposure`。

    CoverageDebt 不因 selection 自动偿还。

and docs/DOMAIN_MODEL.md §10 lists ``PlanningLedger`` among the Planner's
**input authorities** — so the ledger is a *read face* the Planner consumes,
not a thing the Planner writes.

**The coverage rule this repository already froze.** BF-06 §14 ("Unsupported
goal 不制造不可能偿还的 CoverageDebt") has an executable form:
``behavioral_baselines/modality/modality_scope_reference_v1.py``'s
``coverage_obligation(goal_modality, runtime)``, which answers three keys —
``direct_obligation`` / ``accrue_direct_coverage_debt`` /
``preparatory_training_allowed`` — and marks a SPEAKING obligation
``UNAVAILABLE_IN_CURRENT_RUNTIME`` while ``voice_input`` is unavailable (the
same for LISTENING and its evaluator). docs/DATA_MODEL.md §24.14,
docs/IMPLEMENTATION_PLAN.md §7 and docs/DECISION_REGISTER.md's security line
state the same rule in one sentence each: with no voice/audio runtime, direct
obligations pause and *no impossible direct CoverageDebt accrues* (a text
target may still carry a ``PREPARATORY`` goal relevance). ``src`` never imports
``behavioral_baselines`` in this repository, so
:func:`direct_obligation_of` **transcribes** that rule and this cut's suite
loads the pinned reference from its own file and compares every answer — the
same "transcribe, then pin" pattern ``elc.learning.estimator`` and
``elc.teaching.gate`` use.

**The table landed (P8-3), and the reasoning that held it back is kept.**
``PLANNING_LEDGER_STORAGE`` used to be ``NO_TABLE_V1`` for a chain of landed
facts rather than an omission, and those facts are the record of *why* the
table arrives with the company it needs:

- ``SELECT != exposure`` (RA §20). Phase 7 *selects*; nothing *presents* a
  teaching episode until Phase 8 wires the Gate and the Moment, so there is no
  writer of ``teaching_presented`` (or of the two lighter presentations) to
  write a durable exposure row from. A table whose only writer does not exist
  is a table that can only hold invented data — and that is still true today:
  P8-3 lands the table and its **store faces** (``elc.planner.ledger_store``),
  not a producer. The delivery path that presents a Moment is p8-4's, so the
  durable ledger's honest state right now is "the shape and the writer exist,
  the producer does not" (the store's module docstring carries the same line,
  and the count of shipped callers is a checked fact, not prose);
- the ledger is a **projection** in the canonical reading anyway: RA §6 lists
  "PlanningLedger actual exposure/outcome" among CP4's rebuildable projections
  and DATA_MODEL §26 lists "some PlanningLedger rollups" beside them, with the
  document's own rule that a rebuildable projection is never the only source of
  truth. The durable sources are the conversation's turns, the review events
  and the teaching moments — the ledger is what a projection reads *off* them.
  That is why migration 0016 does **not** materialize the two rollup-shaped
  columns (``coverage_debt_rollups`` / ``recent_target_families``): they stay
  read-side, and the per-key rows, the obligations and the event log are what
  the three tables hold;
- a durable user-history table owes a deletion leg the day it exists:
  ``behavioral_baselines/security/SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md``
  lists "PlanningLedger user history" under ``LEARNING_PRIVATE`` and "related
  PlanningLedger history" under the ``LEARNING_TARGET`` scope — the BF-05
  invariant the deletion cut landed is "delete the history the scope names",
  and a new user-history table with no statement in that walk would break it
  the moment it was written. P8-3 lands all three tables **and** their
  statements in both walks (``LEARNING_TARGET_SWEPT_TABLES`` /
  ``LEARNING_HISTORY_SWEPT_TABLES``, and one SELECT plus one DELETE literal per
  table) in the same change — the condition
  :data:`PLANNING_LEDGER_STORAGE_REVISIT` named before this cut.

**Still the pure core.** What this module carries is unchanged: the five event
words, the two original rules as behaviour, the obligation's eleven fields, the
three declared ladders and the view types the column set names. Storage is a
separate module (``elc.planner.ledger_store``): the durable unit is "one §20
event appended and the current projection it leaves", committed in one short
transaction, and the store derives nothing — it persists what
:meth:`TargetLedgerRow.record` / :func:`apply_ledger_event` / :func:`accrue`
already answered.

**Three numbers the canonical documents do not carry, and how each is
declared.** Every one is a module constant with a basis and a revisit, none is
read as a canonical number, and each is pinned where a pin is possible:

- :data:`DEBT_REPAID_PER_SERVING` / :data:`DEBT_REPAID_PER_ENGAGEMENT` — the
  *rates*. ``docs/ARCHITECTURE_BASELINE.md``'s calibratable list names
  "CoverageDebt rates / service bonus" explicitly, so a rate exists as a
  parameter and not as a number; the declared value retires one unit of debt
  per act, and the unit is whatever the accrual entry added;
- :data:`SERVICE_STATE_RUNGS` — the ladder from a debt to BF-02 §13's four
  service words. The words are the frozen golden reference's
  ``COVERAGE_SERVICE_STATES`` (reused through
  :class:`elc.planner.kernel.CoverageServiceState`, never re-spelled) and the
  rungs are declared, in the shape of BF-02 §6's own band rungs, because no
  asset maps a debt to a service state (the frozen 43 cases take
  ``coverage_service_state`` as an *input*);
- :data:`OVEREXPOSURE_WINDOW_DAYS` and :data:`OVEREXPOSURE_RUNGS` — the window
  length and the count→band table. The band *words and numbers* are the frozen
  reference profile's ``reference_factor_bands.overexposure`` (pinned by this
  cut's suite straight from the asset); the window length and the count table
  are declared because the asset carries neither.

**Fail-closed, in the direction each reading's own kind requires.** An
obligation whose goal modality is unknown (no ``runtime`` capability map was
handed in) is **paused**, not accrued: the whole point of the BF-06 §14 rule is
that the system must never permanently believe the user "never covered
speaking", so a missing capability map answers ``UNAVAILABLE_IN_CURRENT_RUNTIME``
rather than assuming a runtime. The overexposure reading's own absence case is
the opposite direction and it is the honest one: a ledger with no row for a
target records no exposure of it, which is the neutral band (``NONE``) and not
a bandless claim — "nothing recorded" is an answer the ledger can give, because
the ledger *is* the exposure authority (RA §20) and an empty book is an empty
book.

**What this module is not.** It is not a store (no SQL, no table, no clock, no
I/O: every input arrives as an argument), it is not the kernel's §13 safeguard
(that rule is already `kernel._score`'s — this module only *answers* the service
state it reads, and re-implementing the bonus here would be a second copy of
the same decision), and it claims nothing about shadow mode, the Gate or
automatic teaching.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum

from elc.planner.kernel import CoverageServiceState
from elc.platform.types import GoalModality

__all__ = [
    "DEBT_REPAID_PER_ENGAGEMENT",
    "DEBT_REPAID_PER_SERVING",
    "EVENT_EFFECTS",
    "EXPOSURE_EVENTS",
    "LEDGER_EVENTS",
    "LEDGER_KEY_TYPES",
    "LEDGER_VALUE_RANGE",
    "OVEREXPOSURE_RUNGS",
    "OVEREXPOSURE_WINDOW_DAYS",
    "PLANNING_LEDGER_MODEL_VERSION",
    "PLANNING_LEDGER_STORAGE",
    "PLANNING_LEDGER_STORAGE_REVISIT",
    "SERVING_EVENTS",
    "SERVICE_STATE_RUNGS",
    "CoverageObligation",
    "DirectObligationRule",
    "EventEffect",
    "EventOutcome",
    "LedgerEvent",
    "LedgerEventRecord",
    "LedgerInputError",
    "LedgerKeyType",
    "LedgerReadings",
    "LedgerStorage",
    "LedgerWindow",
    "ObligationScope",
    "OverexposureReading",
    "PauseReason",
    "PlanningLedger",
    "TargetLedgerRow",
    "accrue",
    "apply_ledger_event",
    "coverage_service_state_of",
    "direct_obligation_of",
    "engage",
    "overexposure_band_of",
    "overexposure_of",
    "serve",
]

#: Stamps this module's own declared readings (module docstring: the three
#: numbers that are not canonical, plus the ladder and the window). A change to
#: any of them is a change to this value — the pattern
#: ``elc.scheduler.spacing``'s own model version uses.
PLANNING_LEDGER_MODEL_VERSION = "pl1"


class LedgerInputError(ValueError):
    """A contract breach in the caller's data (never a missing authority).

    A malformed instant, a debt outside the declared range or a paused
    obligation with no reason is the *caller's* bookkeeping; a *missing*
    authority (no capability map) is answered fail-closed instead of raised.
    """


# -- storage (registered) ----------------------------------------------------


class LedgerStorage(StrEnum):
    """How the ledger is carried, as a word rather than as a silence.

    ``NO_TABLE_V1`` = the ledger is a read-only view a caller assembles from
    the durable facts it already holds (module docstring: no exposure writer
    exists yet, and a user-history table without a deletion leg would break the
    source-aware deletion invariant). It is **kept** as a member after the flip
    — the word describes a state this repository really had, and a probe that
    deletes a word a reader may still find in a trace or a log is a second way
    to lose the history.

    ``DURABLE_TABLES_V1`` = the ledger has durable tables of its own (migration
    0016: ``planning_ledger`` / ``coverage_obligation`` /
    ``planning_ledger_event``, reached through ``elc.planner.ledger_store``),
    and every one of them is in the BF-05 deletion walk of the same change.
    The producer of exposure events is still absent (module docstring) — this
    word says where the ledger *lives*, not who writes it. Revisit: the tables
    are replaced or a second carrier (a projection cache, an export) becomes
    the ledger's home — then the word moves with it.
    """

    NO_TABLE_V1 = "NO_TABLE_V1"
    DURABLE_TABLES_V1 = "DURABLE_TABLES_V1"


PLANNING_LEDGER_STORAGE: LedgerStorage = LedgerStorage.DURABLE_TABLES_V1

#: The condition that re-opens the storage decision (module docstring).
#:
#: The condition this constant carried **before P8-3** — "an exposure writer
#: lands (Phase 8's teaching wiring presents a Moment, or a cut persists a
#: shadow-mode selection) ⇒ land the table in the same change *and* its
#: statements in the BF-05 deletion walk" — is **satisfied**: P8-3 landed
#: 0016's three tables and both deletion legs in the same change
#: (``LEARNING_TARGET_SWEPT_TABLES`` for the contract's "related
#: PlanningLedger history", ``LEARNING_HISTORY_SWEPT_TABLES`` for
#: "PlanningLedger user history", and one SELECT plus one DELETE literal per
#: table in ``elc/deletion/store.py``). What re-opens the *new* decision is
#: named here, so the word stays checkable rather than becoming prose.
PLANNING_LEDGER_STORAGE_REVISIT = (
    "the durable ledger landed in Phase 8 (P8-3: migration 0016's three"
    " tables behind elc.planner.ledger_store, with both BF-05 deletion legs"
    " — LEARNING_TARGET and LEARNING_HISTORY — and the per-table statements"
    " landed in the same change, the condition this constant named before the"
    " cut) ⇒ the storage word moves with the table, and the next re-opening is"
    " named: a second carrier becomes the ledger's home (a materialized rollup"
    " projection, an export, a rebuilt cache), or the delivery path (p8-4)"
    " needs the ledger's tables to carry something §14 does not name (a"
    " presentation's Moment reference, a conversation provenance leg) — then"
    " the carrier, its deletion walk and this word all move in one change"
    " (the scopes SECURITY_PRIVACY_DELETION_CONTRACT names for PlanningLedger"
    " user history: LEARNING_PRIVATE's and the LEARNING_TARGET scope's)"
)


# -- RA §20's five events ----------------------------------------------------


class LedgerEvent(StrEnum):
    """docs/RUNTIME_ARCHITECTURE.md §20's five words, in the document's order.

    The vocabulary is the document's and the effects are
    :data:`EVENT_EFFECTS`' — the two rules §20 states in prose ("SELECT !=
    exposure"; "CoverageDebt 不因 selection 自动偿还") are one entry each, and
    the table is total over the five words so a new word cannot arrive without
    an effect. Revisit: §20 gains or loses a word, or a word's effect changes.
    """

    CANDIDATE_SELECTED = "candidate_selected"
    TEACHING_PRESENTED = "teaching_presented"
    HINT_PRESENTED = "hint_presented"
    REVEAL_PRESENTED = "reveal_presented"
    USER_SKIP = "user_skip"


#: §20's five words, in the document's order — the order this module reads
#: them in when it explains them, and the order a caller's log is expected in.
LEDGER_EVENTS: tuple[LedgerEvent, ...] = tuple(LedgerEvent)


class EventEffect(StrEnum):
    """What one event does to the ledger's own two facts (exposure, repayment).

    Three words rather than two booleans: an event either exposes the target
    and serves the obligation, exposes it without serving it, or does neither —
    and "neither" is the word that has to exist for §20's two rules to be
    statable as facts about events rather than as prose about selections.
    """

    NEITHER = "NEITHER"
    EXPOSURE_ONLY = "EXPOSURE_ONLY"
    EXPOSURE_AND_SERVING = "EXPOSURE_AND_SERVING"


#: One effect per word of §20's five. Reading the declaration:
#:
#: - ``candidate_selected`` → :attr:`EventEffect.NEITHER`: "`SELECT !=
#:   exposure`" and "CoverageDebt 不因 selection 自动偿还" — a selection records
#:   no presentation and repays nothing, which is the *whole* reason §20 lists
#:   it beside the three presentation words;
#: - ``teaching_presented`` → :attr:`EventEffect.EXPOSURE_AND_SERVING`: a
#:   teaching episode for the target was delivered, so the target was exposed
#:   *and* the coverage obligation it belongs to was served;
#: - ``hint_presented`` / ``reveal_presented`` → :attr:`EventEffect.
#:   EXPOSURE_ONLY`: both deliver the target (an exposure) while deliberately
#:   withholding part of the teaching — that is what the two words mean — so
#:   the obligation is **not** served by them. The alternative reading (any
#:   delivery serves) is registered as a revisit: it would let a debt be repaid
#:   by a hint, and §13's safeguard exists to surface what has not been taught.
#:   Revisit: a canonical document states the two presentation words' coverage
#:   effect (RA §20's own rules, or a document saying a hint/reveal *serves* an
#:   obligation), or a sixth event word arrives carrying a serving effect —
#:   then this row's effect moves, and the debts a hint and a reveal repay move
#:   with it;
#: - ``user_skip`` → :attr:`EventEffect.NEITHER`: a skip is a rejection, not a
#:   delivery and not engagement. §20's five words carry no engagement word at
#:   all, which is why :func:`engage` takes that fact as an argument rather
#:   than reading it off an event (see the function's own note).
EVENT_EFFECTS: Mapping[LedgerEvent, EventEffect] = {
    LedgerEvent.CANDIDATE_SELECTED: EventEffect.NEITHER,
    LedgerEvent.TEACHING_PRESENTED: EventEffect.EXPOSURE_AND_SERVING,
    LedgerEvent.HINT_PRESENTED: EventEffect.EXPOSURE_ONLY,
    LedgerEvent.REVEAL_PRESENTED: EventEffect.EXPOSURE_ONLY,
    LedgerEvent.USER_SKIP: EventEffect.NEITHER,
}

#: The three words that present the target to the user (RA §20's three
#: presentation events) — the events an exposure count is made of.
EXPOSURE_EVENTS: tuple[LedgerEvent, ...] = tuple(
    event
    for event in LEDGER_EVENTS
    if EVENT_EFFECTS[event] is not EventEffect.NEITHER
)

#: The one word that **serves** a coverage obligation (see
#: :data:`EVENT_EFFECTS` for why a hint and a reveal do not).
SERVING_EVENTS: tuple[LedgerEvent, ...] = tuple(
    event
    for event in LEDGER_EVENTS
    if EVENT_EFFECTS[event] is EventEffect.EXPOSURE_AND_SERVING
)


# -- coverage obligations ----------------------------------------------------


class PauseReason(StrEnum):
    """Why an obligation is not accruing, in the canonical word.

    ``UNAVAILABLE_IN_CURRENT_RUNTIME`` is docs/DATA_MODEL.md §24.14's word
    (BF-06 §14 spells the same one, and
    ``modality_scope_reference_v1.py``'s ``direct_obligation`` answers it), and
    it is the *only* word this cut can produce: a second word would need a
    second reason a runtime can state. Revisit: a canonical document lists the
    vocabulary (today §24.14 names one word) or a non-runtime pause lands.
    """

    UNAVAILABLE_IN_CURRENT_RUNTIME = "UNAVAILABLE_IN_CURRENT_RUNTIME"


class LedgerKeyType(StrEnum):
    """Which key face a ``target/family`` row's key belongs to (§14's key line).

    §14 spells the row's key ``target/family``, so the column set's first line
    names **two** key faces and no canonical document lists a vocabulary for
    them — this is this cut's spelling of exactly the two, and it exists
    because the durable row needs to say which face its key is: a family row
    whose id happens to spell a target's must not be swept by that target's
    deletion (``elc/deletion/store.py`` reads this word for the
    ``LEARNING_TARGET`` walk), and a reader that wants only target-keyed rows
    can say so without matching on id strings.

    The core's own key is a single string (``TargetLedgerRow.target_key``,
    ``PlanningLedger.rows``): the two faces are one key space with a label
    rather than two namespaces, and migration 0016's single ``ledger_key``
    column is that shape — a composite durable key would let one id exist
    twice and fold onto one core key. Revisit: canonical text lists the key
    faces (or a third one — a goal-keyed ledger row), or a face is retired.
    """

    TARGET = "TARGET"
    TARGET_FAMILY = "TARGET_FAMILY"


#: §14's two key faces, in the document's order (it spells them
#: ``target/family``), for a reader that wants to walk them.
LEDGER_KEY_TYPES: tuple[LedgerKeyType, ...] = tuple(LedgerKeyType)


class ObligationScope(StrEnum):
    """The key space ``scope_type`` + ``target_or_family_id`` addresses.

    Declared, not quoted: §14's column pair names *that* there is a scope type
    and a scoped id, and its optional ``goal_id`` names a third key space — the
    three words are this cut's spelling of exactly those three (a target, a
    target family, a goal). No canonical document lists ``scope_type``'s
    vocabulary. Revisit: canonical text lists it, or a fourth key space
    appears.
    """

    TARGET = "TARGET"
    TARGET_FAMILY = "TARGET_FAMILY"
    GOAL = "GOAL"


@dataclass(frozen=True)
class DirectObligationRule:
    """BF-06 §14's answer for one goal modality, with the reference's keys.

    The three field names are the frozen reference's own
    (``direct_obligation`` / ``accrue_direct_coverage_debt`` /
    ``preparatory_training_allowed``), so a test can compare this record with
    ``modality_scope_reference_v1.coverage_obligation``'s dict key for key
    instead of trusting a transcription.
    """

    direct_obligation: str
    accrue_direct_coverage_debt: bool
    preparatory_training_allowed: bool


def direct_obligation_of(
    goal_modality: GoalModality, runtime: Mapping[str, bool] | None
) -> DirectObligationRule:
    """BF-06 §14's rule, transcribed from the frozen reference module.

    The reference reads two capability flags — ``voice_input`` for SPEAKING and
    ``listening_comprehension_evaluator`` for LISTENING (the same two BF-06 §14
    names) — and answers ``UNAVAILABLE_IN_CURRENT_RUNTIME`` with
    ``accrue_direct_coverage_debt=False`` while either is missing; both are
    ``AVAILABLE`` with accrual on when it is present, and
    ``preparatory_training_allowed`` is ``True`` in every case (the text target
    keeps its ``PREPARATORY`` goal relevance). Modalities the rule says nothing
    about (READING / WRITING) answer ``AVAILABLE``: the frozen function falls
    through to that arm for them, and this cut keeps the fall-through rather
    than inventing a rule for reading and writing.

    ``runtime=None`` is this cut's own addition to the reference's contract
    (the reference takes a dict and nothing else) and it means the caller holds
    no capability map at all: that is **paused** rather than assumed, for every
    modality, because the rule exists so the system never permanently believes
    a user "never covered speaking" — and assuming a runtime is the direction
    that creates impossible debt (module docstring, fail-closed). A caller that
    holds the map gets the reference's own answer, which is what this cut's
    suite pins against the frozen module.
    """

    if runtime is None:
        return _unavailable_in_current_runtime()
    if goal_modality is GoalModality.SPEAKING and not runtime.get(
        "voice_input", False
    ):
        return _unavailable_in_current_runtime()
    if goal_modality is GoalModality.LISTENING and not runtime.get(
        "listening_comprehension_evaluator", False
    ):
        return _unavailable_in_current_runtime()
    return DirectObligationRule(
        direct_obligation="AVAILABLE",
        accrue_direct_coverage_debt=True,
        preparatory_training_allowed=True,
    )


def _unavailable_in_current_runtime() -> DirectObligationRule:
    return DirectObligationRule(
        direct_obligation=PauseReason.UNAVAILABLE_IN_CURRENT_RUNTIME.value,
        accrue_direct_coverage_debt=False,
        preparatory_training_allowed=True,
    )


#: The declared range of ``debt_value`` (§14 names the column and no range; a
#: four-rung service ladder needs one). Inclusive on both ends, and the two
#: accrual/repayment entries below refuse a value outside it rather than
#: clamping silently.
#:
#: Revisit: a canonical document or a calibrated profile gives ``debt_value`` a
#: scale of its own (a column-level range, a percentage, or a debt unit) — then
#: the range, the ladder's rungs and the two repayment rates move in one change,
#: because a rung read against two scales is two ladders.
LEDGER_VALUE_RANGE = (0.0, 1.0)

#: The rate a serving act retires, and the rate an engagement act retires.
#: **Declared** (module docstring): ``docs/ARCHITECTURE_BASELINE.md``'s
#: calibratable list names "CoverageDebt rates / service bonus" as a parameter
#: set and no document gives the number, so "one act retires one unit" is this
#: cut's declared value — the unit being whatever an accrual added. Revisit: a
#: calibrated profile lands, or canonical text spells the repayment rule.
DEBT_REPAID_PER_SERVING = 1.0
DEBT_REPAID_PER_ENGAGEMENT = 1.0


@dataclass(frozen=True)
class CoverageObligation:
    """One ``coverage_obligations[]`` entry — §14's eleven fields, by name.

    The four optional fields are spelled ``X | None`` with ``None`` as "the
    column is absent", which is the same reading P6-0 gave §5.1's optional
    columns; the three required text fields are what an obligation *is* (a key,
    a scope, a window).

    Two invariants are checked at construction because both are canonical
    sentences rather than style:

    - ``accrual_paused`` and ``pause_reason`` agree — a pause has a reason and a
      reason has a pause, so a half-declared pause cannot exist;
    - ``debt_value`` is inside :data:`LEDGER_VALUE_RANGE` — the declared range
      above, refused rather than clamped.
    """

    obligation_key: str
    scope_type: str
    target_or_family_id: str
    goal_id: str | None
    window_start: str
    window_end: str
    debt_value: float
    accrual_paused: bool
    pause_reason: str | None
    last_served_at: str | None
    last_engaged_at: str | None

    def __post_init__(self) -> None:
        low, high = LEDGER_VALUE_RANGE
        if not low <= self.debt_value <= high:
            raise LedgerInputError(
                f"{self.obligation_key}: debt_value {self.debt_value!r} is"
                f" outside the declared range [{low}, {high}] — an obligation"
                " outside its own scale cannot be put on the service ladder"
            )
        if self.accrual_paused and not self.pause_reason:
            raise LedgerInputError(
                f"{self.obligation_key}: accrual_paused with no pause_reason"
                " — a pause is a statement about *why* nothing accrues"
                " (DATA_MODEL §24.14's UNAVAILABLE_IN_CURRENT_RUNTIME)"
            )
        if not self.accrual_paused and self.pause_reason is not None:
            raise LedgerInputError(
                f"{self.obligation_key}: pause_reason"
                f" {self.pause_reason!r} on an obligation that is not paused"
            )


@dataclass(frozen=True)
class EventOutcome:
    """What one event did to one obligation: the row, and whether it moved.

    ``changed`` is the exhaustive answer to "did this event touch the debt or a
    timestamp?", and ``reason`` says why, in the ledger's own words — so the two
    §20 rules are checkable as facts about a record rather than as prose.
    """

    obligation: CoverageObligation
    changed: bool
    reason: str


def accrue(
    obligation: CoverageObligation, *, amount: float, at: str
) -> EventOutcome:
    """Add debt to an obligation — **unless it is paused**.

    The BF-06 §14 rule is that an unsupported direct obligation does not accrue
    *impossible* CoverageDebt, so this is the one entry point an accrual can
    take and it refuses on two counts, both of them returned rather than
    raised as a missing-answer:

    - a paused obligation is **not** increased and the outcome's reason is the
      pause word — whatever the caller's `amount`, and whoever the caller is
      (there is no second accrual entry in this module);
    - a negative or zero amount is a caller error and raises, because "accrual"
      that lowers the debt is repayment wearing the wrong word (repayment goes
      through :func:`serve` / :func:`engage`).

    ``debt_value`` is declared to live in :data:`LEDGER_VALUE_RANGE`, so a sum
    past the top raises rather than silently clipping: an obligation whose debt
    left its own scale has no ladder position.

    ``at`` is validated as an instant (a naive timestamp is refused, the rule
    ``elc.scheduler.spacing`` states for the same column family) even though
    the accrual itself does not stamp a column — the caller's instant is what
    an audit reads beside the debt.
    """

    _instant(at, "at")
    if amount < 0:
        raise LedgerInputError(
            f"{obligation.obligation_key}: accrual amount {amount!r} is"
            " negative — debt decreases through serving or engagement"
            " (serve/engage), never through an accrual entry"
        )
    if obligation.accrual_paused:
        return EventOutcome(
            obligation=obligation,
            changed=False,
            reason=(
                f"accrual_paused={obligation.pause_reason}: an unsupported"
                " direct obligation does not accrue impossible CoverageDebt"
                " (BF-06 §14 / DATA_MODEL §24.14), so debt stays"
                f" {obligation.debt_value!r}"
            ),
        )
    if amount == 0.0:
        return EventOutcome(
            obligation=obligation,
            changed=False,
            reason="an accrual of zero moves nothing",
        )
    _, high = LEDGER_VALUE_RANGE
    total = obligation.debt_value + amount
    if total > high:
        raise LedgerInputError(
            f"{obligation.obligation_key}: accruing {amount!r} onto"
            f" {obligation.debt_value!r} leaves the declared range"
            f" [{LEDGER_VALUE_RANGE[0]}, {high}] — the ledger refuses a debt"
            " outside its own scale instead of clipping it"
        )
    return EventOutcome(
        obligation=replace(obligation, debt_value=total),
        changed=True,
        reason=f"accrued {amount!r} (debt {total!r})",
    )


def _repay(obligation: CoverageObligation, *, amount: float) -> CoverageObligation:
    low, _ = LEDGER_VALUE_RANGE
    return replace(
        obligation, debt_value=max(low, obligation.debt_value - amount)
    )


def serve(obligation: CoverageObligation, *, at: str) -> CoverageObligation:
    """A serving act: ``last_served_at`` is stamped and the debt is paid down.

    Servable only through a delivery — see :data:`EVENT_EFFECTS` for which
    words serve — and a serving on a *paused* obligation is refused: an
    obligation the runtime cannot serve has nothing to serve, so stamping it
    would claim a delivery that could not have happened. The refusal is a
    raise, because this is a caller asking to record an impossible fact rather
    than a reading deciding what to say.
    """

    _instant(at, "at")
    if obligation.accrual_paused:
        raise LedgerInputError(
            f"{obligation.obligation_key}: cannot be served —"
            f" accrual_paused={obligation.pause_reason} (an obligation the"
            " runtime cannot serve is not served by stamping it)"
        )
    stamped = replace(obligation, last_served_at=at)
    return _repay(stamped, amount=DEBT_REPAID_PER_SERVING)


def engage(obligation: CoverageObligation, *, at: str) -> CoverageObligation:
    """An engagement act: ``last_engaged_at`` is stamped and the debt is paid.

    §20's five words carry **no engagement word** (see :data:`EVENT_EFFECTS`),
    so engagement is not something this module can read off an event: the fact
    arrives from the authority that observes the user engaging with the served
    target (a Learning-side Attempt is the shape Phase 3 landed; reading one
    is a later cut's wiring), and this function is where such a fact stamps the
    obligation. §14's ``last_engaged_at`` column exists for it; nothing in
    Phase 7 writes it.

    Revisit: a canonical document adds an engagement word to the ledger's event
    vocabulary (then engagement is read off the log like the other effects and
    this entry point is re-cut around that word), or the observing authority's
    shape changes (a fact that is not a Learning-side Attempt), or the
    repayment rate is calibrated (then the amount this stamps is re-read).
    """

    _instant(at, "at")
    if obligation.accrual_paused:
        raise LedgerInputError(
            f"{obligation.obligation_key}: cannot be engaged —"
            f" accrual_paused={obligation.pause_reason}"
        )
    stamped = replace(obligation, last_engaged_at=at)
    return _repay(stamped, amount=DEBT_REPAID_PER_ENGAGEMENT)


def apply_ledger_event(
    obligation: CoverageObligation, event: LedgerEvent, *, at: str
) -> EventOutcome:
    """One §20 event against one obligation, through :data:`EVENT_EFFECTS`.

    The two original rules read as behaviour, and both are *no-ops with a
    reason* rather than silences: ``candidate_selected`` changes nothing
    ("CoverageDebt 不因 selection 自动偿还"), a hint or a reveal exposes without
    serving, and a skip is a rejection. Only a serving event reaches
    :func:`serve`.
    """

    effect = EVENT_EFFECTS[event]
    if event in SERVING_EVENTS:
        served = serve(obligation, at=at)
        return EventOutcome(
            obligation=served,
            changed=served != obligation,
            reason=(
                f"{event.value}: the target was presented *as teaching*, so"
                " the obligation is served (last_served_at) and the debt is"
                f" paid down by {DEBT_REPAID_PER_SERVING!r}"
            ),
        )
    if event in EXPOSURE_EVENTS:
        _instant(at, "at")
        return EventOutcome(
            obligation=obligation,
            changed=False,
            reason=(
                f"{event.value}: an exposure, not a service — a hint or a"
                " reveal withholds part of the teaching, so the obligation is"
                " not repaid by it (the exposure is recorded on the row's"
                " presentation log)"
            ),
        )
    _instant(at, "at")
    if event is LedgerEvent.CANDIDATE_SELECTED:
        reason = (
            "candidate_selected: SELECT != exposure, and CoverageDebt does not"
            " repay itself because a candidate was selected (RA §20)"
        )
    else:
        reason = (
            f"{event.value}: a rejection, not a delivery and not engagement —"
            " §20's five words carry no engagement word, so nothing is served"
            " and nothing is repaid"
        )
    assert effect is EventEffect.NEITHER
    return EventOutcome(obligation=obligation, changed=False, reason=reason)


# -- the service ladder (declared) -------------------------------------------


#: The ladder from a debt to BF-02 §13's service words: the highest rung whose
#: value the debt has reached. The **words** are the frozen golden reference's
#: ``COVERAGE_SERVICE_STATES`` (``kernel.CoverageServiceState``, reused); the
#: **rungs** are declared (module docstring) in the shape of BF-02 §6's own
#: band ladder — ``0.25`` / ``0.50`` / ``0.75``, the reference ladder's
#: non-zero rungs — so "how far along" means the same thing for a debt as for a
#: factor's band. The frozen 43 cases take ``coverage_service_state`` as an
#: input, which is why no asset answers this mapping. Revisit: a calibrated
#: profile or a canonical sentence gives the ladder, or ``debt_value`` is given
#: a scale other than the declared ``[0, 1]``.
SERVICE_STATE_RUNGS: tuple[tuple[float, CoverageServiceState], ...] = (
    (0.75, CoverageServiceState.CRITICAL),
    (0.50, CoverageServiceState.DUE),
    (0.25, CoverageServiceState.WATCH),
    (0.00, CoverageServiceState.NONE),
)


def coverage_service_state_of(
    obligation: CoverageObligation,
) -> CoverageServiceState:
    """One obligation's service class, or ``NONE`` for a paused one.

    A paused obligation answers ``NONE`` rather than a rung: it cannot accrue
    debt (BF-06 §14), so it cannot be starved, and answering ``CRITICAL`` for it
    would let §13's safeguard spend a teaching slot on an obligation the runtime
    cannot serve. The state that travels to the kernel is therefore the state of
    a debt that *can* exist.
    """

    if obligation.accrual_paused:
        return CoverageServiceState.NONE
    for rung, state in SERVICE_STATE_RUNGS:
        if obligation.debt_value >= rung:
            return state
    return CoverageServiceState.NONE


# -- overexposure (declared window, declared count table) --------------------


#: How far back an exposure count looks when a row names no window of its own.
#: **Declared** (module docstring): the column ```overexposure_window`` exists
#: and no asset gives a length, so this is the fallback length. Seven days is
#: the shortest span that can hold several review slots of the Scheduler's own
#: day-scale ladder, which is the scale "repeated exposure" is counted over.
#: Revisit: a calibrated profile lands, or the ledger's windows start arriving
#: from a durable row (then the fallback is only a default).
OVEREXPOSURE_WINDOW_DAYS = 7

#: The count → band table, most exposed first: at least four presentations
#: inside the window is ``SATURATED``, three ``HIGH``, two ``MEDIUM``, one
#: ``LOW``, none ``NONE``. The five **words** are the frozen reference
#: profile's ``reference_factor_bands.overexposure`` keys and the **numbers**
#: stay in ``elc.planner.candidates.FACTOR_BAND_VALUES`` (this module answers
#: band words, never decimals, so the factor's numbers have one home); the
#: count table itself is declared — the asset carries no count→band rule.
#: Revisit: a calibrated count table lands, or the band ladder is re-spelled.
OVEREXPOSURE_RUNGS: tuple[tuple[int, str], ...] = (
    (4, "SATURATED"),
    (3, "HIGH"),
    (2, "MEDIUM"),
    (1, "LOW"),
    (0, "NONE"),
)


def overexposure_band_of(count: int) -> str:
    """The band word for a presentation count inside one window."""

    if count < 0:
        raise LedgerInputError(
            f"a presentation count cannot be negative ({count!r})"
        )
    for rung, band in OVEREXPOSURE_RUNGS:
        if count >= rung:
            return band
    return OVEREXPOSURE_RUNGS[-1][1]


@dataclass(frozen=True)
class LedgerWindow:
    """One window, as §14's ``overexposure_window`` column needs it.

    Half-open ``(start, end]``, declared: a look-back window's start instant
    belongs to the window before it, while a presentation at ``end`` (the
    cycle's ``as_of``) happened inside. The two instants are compared **as
    instants** — parsed with ``datetime.fromisoformat``, exactly as
    ``elc.scheduler.spacing`` compares the same column family — because two
    spellings of one instant are two different strings and only the instant can
    answer "when". A naive timestamp is refused rather than assumed to be UTC.

    Revisit: a canonical document fixes the window's inclusivity (a closed
    ``[start, end]``, or a ``start`` that counts inside its own window), or the
    bounds start arriving from a durable row whose spelling is normalized by
    its writer (then the string-vs-instant argument is re-asked for *this* row),
    or the Scheduler's own window convention for the same column family changes
    under ``elc.scheduler.spacing`` — then this reading, which follows it, is
    re-read beside it.
    """

    start: str
    end: str

    def contains(self, at: str) -> bool:
        """Whether one instant falls inside the half-open window."""

        moment = _instant(at, "at")
        return _instant(self.start, "start") < moment <= _instant(
            self.end, "end"
        )


@dataclass(frozen=True)
class LedgerEventRecord:
    """One event in a row's log: the word, and when it happened."""

    event: LedgerEvent
    at: str


@dataclass(frozen=True)
class TargetLedgerRow:
    """One ``target/family`` row of §14's column set.

    The row's **fact** is its event log (``events``), and the columns §14 names
    that are functions of it are derived properties
    (:attr:`last_selected_at` / :attr:`last_presented_at` /
    :attr:`teaching_exposure_counts` / :attr:`recent_skips`) — one fact, one
    source, so no stored copy can disagree with the log. The three columns that
    are *not* functions of the log are stored: ``overexposure_window`` (the
    row's own window, a policy), and ``probe_counts`` / ``review_offers``, which
    have **no writer** in this cut — none of §20's five words is a probe or a
    review offer, so a count with no event behind it is carried and never
    invented (see this module's registrations: the cut that lands a probe
    attempt or a review offer fills them).
    """

    target_key: str
    events: tuple[LedgerEventRecord, ...] = ()
    overexposure_window: LedgerWindow | None = None
    probe_counts: int = 0
    review_offers: int = 0

    def record(self, event: LedgerEvent, *, at: str) -> TargetLedgerRow:
        """Append one event to the log (append-only; no dedupe).

        The log is append-only and this core does not collapse a repeat: two
        presentations at one instant are two presentations, and a caller
        replaying a durable log must not append a record it already appended —
        replay belongs to the writer's cut, which owns the table it replays
        from. ``at`` is validated as an aware instant.
        """

        _instant(at, "at")
        return replace(
            self,
            events=(*self.events, LedgerEventRecord(event=event, at=at)),
        )

    def _events_of(self, events: Sequence[LedgerEvent]) -> tuple[str, ...]:
        wanted = set(events)
        return tuple(
            record.at
            for record in self.events
            if record.event in wanted
        )

    @property
    def last_selected_at(self) -> str | None:
        """§14's column: when this key was last *selected* (not presented)."""

        stamps = self._events_of((LedgerEvent.CANDIDATE_SELECTED,))
        return None if not stamps else _latest(stamps)

    @property
    def last_presented_at(self) -> str | None:
        """§14's column: when this key was last presented to the user."""

        stamps = self._events_of(EXPOSURE_EVENTS)
        return None if not stamps else _latest(stamps)

    @property
    def teaching_exposure_counts(self) -> int:
        """§14's column, read off the log's ``teaching_presented`` events."""

        return sum(
            1
            for record in self.events
            if record.event is LedgerEvent.TEACHING_PRESENTED
        )

    @property
    def recent_skips(self) -> int:
        """§14's ``recent_skips/rejections`` column, off the log's skips.

        Carried and read by nothing in this cut: BF-02 §6's ``user_resistance``
        ladder has no mapping from a skip count in any asset (its words are
        NONE / RECENT_SKIP / REPEATED_SKIP / SOFT_RESISTANCE), so no factor is
        moved by this number. Revisit: an asset maps skips onto that ladder.
        """

        return sum(
            1
            for record in self.events
            if record.event is LedgerEvent.USER_SKIP
        )

    @property
    def presentations(self) -> tuple[LedgerEventRecord, ...]:
        """Every presentation in the log, in the order it was recorded."""

        return tuple(
            record
            for record in self.events
            if record.event in EXPOSURE_EVENTS
        )


@dataclass(frozen=True)
class OverexposureReading:
    """The ledger's answer to "how exposed is this target", and its window.

    ``band`` is a word of the frozen reference profile's ``overexposure``
    ladder (never a number: the number lives in the factor band table), and the
    reading carries the three inputs it was made of — the window, the count
    inside it, and the last presentation instant — so a trace can show them.
    """

    band: str
    count: int
    window: LedgerWindow
    last_presented_at: str | None
    reasons: tuple[str, ...]


def overexposure_of(
    row: TargetLedgerRow | None, *, as_of: str
) -> OverexposureReading:
    """One row's overexposure reading at one instant.

    Three inputs, as the factor's authority names them: the row's own
    ``overexposure_window`` when it carries one, else the declared fallback
    window ending at ``as_of``; the presentations inside that window; and
    ``last_presented_at``. A row that is ``None`` — the ledger holds no history
    for this target — answers the neutral band: an empty book records no
    exposure, which is an answer the exposure authority *can* give (module
    docstring, fail-closed).

    Revisit: a canonical document reads the absent row the other way (fail
    closed on *unknown* exposure rather than on "nothing recorded"), or the
    exposure authority moves off the ledger row (a projection that knows more
    than the book) — then "no row" stops being this module's own answer and the
    band for it is re-decided.
    """

    window = (
        row.overexposure_window
        if row is not None and row.overexposure_window is not None
        else _fallback_window(as_of)
    )
    presentations = () if row is None else row.presentations
    inside = tuple(
        record for record in presentations if window.contains(record.at)
    )
    band = overexposure_band_of(len(inside))
    reasons = [
        f"window ({window.start}, {window.end}]"
        + (
            " — the row's own"
            if row is not None and row.overexposure_window is not None
            else f" — the declared fallback of {OVEREXPOSURE_WINDOW_DAYS} days"
        ),
        f"presentations inside the window: {len(inside)} → band {band}",
    ]
    last_presented = None if row is None else row.last_presented_at
    if row is None:
        reasons.append(
            "no row for this target: the ledger records no presentation of it,"
            " and 'nothing recorded' is the neutral band (the ledger is the"
            " exposure authority, so an empty book is an empty book)"
        )
    elif last_presented is not None:
        reasons.append(f"last_presented_at={last_presented}")
    return OverexposureReading(
        band=band,
        count=len(inside),
        window=window,
        last_presented_at=last_presented,
        reasons=tuple(reasons),
    )


def _fallback_window(as_of: str) -> LedgerWindow:
    moment = _instant(as_of, "as_of")
    start = moment - timedelta(days=OVEREXPOSURE_WINDOW_DAYS)
    return LedgerWindow(start=start.isoformat(), end=as_of)


@dataclass(frozen=True)
class LedgerReadings:
    """Everything the supply side reads off the ledger for one target.

    ``obligation`` is the *governing* live obligation when the target has one
    (see :meth:`PlanningLedger.governing_obligation_of`), ``service_state`` is
    that obligation's ladder position (``NONE`` when there is none, or when the
    only ones are paused), and ``reasons`` says how the reading was reached.
    """

    target_id: str
    overexposure: OverexposureReading
    obligation: CoverageObligation | None
    service_state: CoverageServiceState
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PlanningLedger:
    """The ledger as a read-only view — §14's columns, and no store.

    A caller assembles one from the durable facts it holds (module docstring:
    ``NO_TABLE_V1``); the ledger itself is pure, deterministic and
    clock-free — every method that needs "now" takes the cycle's instant.

    ``rows`` is keyed by §14's ``target/family`` key, ``obligations`` is the
    ``coverage_obligations[]`` list, and ``coverage_debt_rollups`` /
    ``recent_target_families`` / ``version`` are the three row-independent
    columns, carried as the document names them (the rollups are a *projection*
    per DATA_MODEL §26 — they are read, never computed here, so the ledger
    cannot turn a rollup into a second debt).
    """

    rows: Mapping[str, TargetLedgerRow] = field(default_factory=dict)
    obligations: tuple[CoverageObligation, ...] = ()
    coverage_debt_rollups: Mapping[str, float] = field(default_factory=dict)
    recent_target_families: tuple[str, ...] = ()
    version: str = PLANNING_LEDGER_MODEL_VERSION

    def row_of(self, target_key: str) -> TargetLedgerRow | None:
        """One row, or ``None`` when the ledger holds no history for the key."""

        return self.rows.get(target_key)

    def record_event(
        self, target_key: str, event: LedgerEvent, *, at: str
    ) -> PlanningLedger:
        """This ledger with one event appended to one row's log.

        The only write this module has, and it writes nothing durable: a new
        :class:`PlanningLedger` comes back and the caller decides what to do
        with it (``NO_TABLE_V1``). A key with no row yet gets one, because a
        first presentation is exactly how a row begins to exist.
        """

        existing = self.rows.get(target_key) or TargetLedgerRow(
            target_key=target_key
        )
        updated = existing.record(event, at=at)
        return replace(
            self, rows={**self.rows, target_key: updated}
        )

    def obligations_for(self, target_id: str) -> tuple[CoverageObligation, ...]:
        """Every obligation whose ``target_or_family_id`` is this key.

        The key is matched **as spelled**, so a family- or goal-scoped row whose
        id happens to be this string lands here too — the target-scoped read is
        :meth:`target_scoped_obligations_for`, which is what the readings use.
        Ordered by ``obligation_key`` so a lookup's order is a property of the
        ledgers rather than of how they were built.
        """

        return tuple(
            sorted(
                (
                    obligation
                    for obligation in self.obligations
                    if obligation.target_or_family_id == target_id
                ),
                key=lambda obligation: obligation.obligation_key,
            )
        )

    def target_scoped_obligations_for(
        self, target_id: str
    ) -> tuple[CoverageObligation, ...]:
        """The TARGET-scoped obligations that name this target.

        A family- or goal-scoped row is not a target's debt: its
        ``target_or_family_id`` is a family or a goal key, and no face in this
        repository resolves those to targets (see
        :meth:`serviceable_targets`).
        """

        return tuple(
            obligation
            for obligation in self.obligations_for(target_id)
            if obligation.scope_type == ObligationScope.TARGET.value
        )

    def governing_obligation_of(
        self, target_id: str
    ) -> CoverageObligation | None:
        """The obligation a debt candidate for one target would carry.

        Declared reading: among the target's **live** TARGET-scoped obligations
        (a paused one is not live — BF-06 §14 stops it accruing, so it cannot be
        the debt this cycle should pay) the one with the highest ``debt_value``
        governs, and ties break on ``obligation_key`` so the choice is a
        function of the data rather than of the tuple's order. ``None`` means
        the target has no live obligation.

        Revisit: a canonical document states which obligation governs a target
        (then the sentence replaces this reading), ``debt_value`` is given a
        unit that makes two obligations' debts comparable by a stated rule
        other than largest-first, a family/goal → targets read face lands (then
        a non-TARGET-scoped obligation could govern), or a window rule says a
        debt outside its own window does not govern — each of those replaces
        exactly one clause of this reading.
        """

        live = [
            obligation
            for obligation in self.target_scoped_obligations_for(target_id)
            if not obligation.accrual_paused
        ]
        if not live:
            return None
        return min(
            sorted(live, key=lambda obligation: obligation.obligation_key),
            key=lambda obligation: -obligation.debt_value,
        )

    def serviceable_obligations(self) -> tuple[CoverageObligation, ...]:
        """The obligations a coverage-debt candidate may be proposed for.

        Live (not paused), owing something (``debt_value > 0``) **and
        TARGET-scoped** — the last condition is the one that keeps this list
        and :meth:`serviceable_targets` the same fact: a candidate is built for
        a target, so a family- or goal-scoped obligation (see
        :meth:`serviceable_targets`) is carried and proposed for nothing.
        Ordered by ``obligation_key`` so two ledgers that hold the same
        obligations in different orders propose the same candidates in the same
        order. A paused obligation is absent by construction: it must not
        accrue impossible debt, so there is no debt for a cycle to pay.
        """

        return tuple(
            sorted(
                (
                    obligation
                    for obligation in self.obligations
                    if not obligation.accrual_paused
                    and obligation.debt_value > LEDGER_VALUE_RANGE[0]
                    and obligation.scope_type == ObligationScope.TARGET.value
                ),
                key=lambda obligation: obligation.obligation_key,
            )
        )

    def serviceable_targets(self) -> tuple[str, ...]:
        """The target ids of :meth:`serviceable_obligations`, deduplicated.

        **TARGET-scoped obligations only.** A candidate is built for a *target*,
        and only a ``scope_type=``\\ :attr:`ObligationScope.TARGET` obligation's
        ``target_or_family_id`` **is** a target id: a family-scoped or
        goal-scoped obligation names a key the supply side cannot resolve to
        targets — no face in this repository maps a family or a goal onto its
        members — so a cycle cannot propose coverage service for one. They are
        carried on the ledger and proposed for nothing, which is registered
        rather than guessed at. Revisit: a family/goal → targets read face
        lands (then the mapping is read, not invented).
        """

        seen: dict[str, None] = {}
        for obligation in self.serviceable_obligations():
            if obligation.scope_type != ObligationScope.TARGET.value:
                continue
            seen.setdefault(obligation.target_or_family_id, None)
        return tuple(seen)

    def overexposure_of(
        self, target_id: str, *, as_of: str
    ) -> OverexposureReading:
        """One target's overexposure reading over this ledger's rows."""

        return overexposure_of(self.row_of(target_id), as_of=as_of)

    def readings_for(self, target_id: str, *, as_of: str) -> LedgerReadings:
        """Everything the supply side reads for one target, in one record."""

        overexposure = self.overexposure_of(target_id, as_of=as_of)
        obligation = self.governing_obligation_of(target_id)
        reasons = list(overexposure.reasons)
        if obligation is None:
            named = self.obligations_for(target_id)
            scoped = self.target_scoped_obligations_for(target_id)
            if scoped:
                reasons.append(
                    "obligations exist for this target and every one is"
                    " paused: a paused obligation answers no service state"
                    " (it cannot accrue, so it cannot be starved)"
                )
            elif named:
                reasons.append(
                    "obligations name this key and none is TARGET-scoped: a"
                    " family- or goal-scoped obligation is not a target's debt"
                )
            else:
                reasons.append("no coverage obligation names this target")
        else:
            reasons.append(
                f"governing obligation {obligation.obligation_key}:"
                f" debt={obligation.debt_value!r}"
                f" scope={obligation.scope_type}"
            )
        return LedgerReadings(
            target_id=target_id,
            overexposure=overexposure,
            obligation=obligation,
            service_state=(
                CoverageServiceState.NONE
                if obligation is None
                else coverage_service_state_of(obligation)
            ),
            reasons=tuple(reasons),
        )


# -- the instant rule (shared with elc.scheduler.spacing's wording) ----------


def _instant(text: str, field_name: str) -> datetime:
    """One ISO-8601 instant, or a refusal the caller can read.

    Empty, unparsable and **naive** timestamps are refused: the ledger has no
    authority to pick a zone for a caller, which is the rule
    ``elc.scheduler.spacing`` states for the same column family.
    """

    if not text:
        raise LedgerInputError(
            f"{field_name} is empty; an instant must be an ISO-8601 timestamp"
            " carrying a UTC offset"
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise LedgerInputError(
            f"{field_name} {text!r} is not an ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None:
        raise LedgerInputError(
            f"{field_name} {text!r} carries no UTC offset; the ledger will not"
            " assume a zone (write the offset, e.g. +00:00)"
        )
    return parsed


def _latest(stamps: Sequence[str]) -> str:
    """The latest of several instants, returned as the caller spelled it."""

    return max(stamps, key=lambda text: _instant(text, "at"))
