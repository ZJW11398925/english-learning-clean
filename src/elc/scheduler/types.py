"""Scheduler domain — review truth.

Owns (docs/DOMAIN_MODEL.md §9): review_state, review_urgency,
next_review_window, spacing_stage. Reads learning freshness / last strong
retrieval / stability evidence / teaching history.

"Learning 不能直接输出 `REVIEW_DUE`；Scheduler 才决定 due/overdue"
(DOMAIN_MODEL §9) — that sentence is D-INV-009 (DOMAIN_MODEL.md line 903:
"Scheduler 决定 review due；Learning 只提供 freshness"), and it is the split
these objects carry: Learning owns evidence and freshness, the Scheduler owns
the review row and the due decision, and the Planner *consumes* a
:class:`ScheduleView` (DOMAIN_MODEL §10) without owning any review truth.

Phase 6 P6-1 (TASK-OPI-6259f6fd-….12 ②②): the Phase 0 skeletons were
replaced by docs/DATA_MODEL.md **§5.2**'s column sets, verbatim —

- ``ScheduleItem`` — §5.2's twelve columns: schedule_item_id / target_type /
  target_id / evidence_modality / review_state / review_urgency /
  next_review_window_start? / next_review_window_end? / spacing_stage? /
  source_learning_watermark / version / updated_at;
- ``ReviewEvent`` — §5.2's eight columns: review_event_id /
  schedule_item_id / teaching_moment_id? / source_turn_id? / event_type /
  engaged / evidence_group_id? / created_at.

**The vocabulary replacement.** The Phase 0 skeleton's :class:`ReviewState`
carried five words of its own invention (NEW / LEARNING / REVIEW / LAPSED /
SUSPENDED), which are **disjoint** from §5.2's ``review_state`` block and
which the canonical set does not contain; they are removed rather than
renamed (the P6-0 lesson: §5.2's vocabulary *is* the authority, so a word the
canonical block does not carry may not survive the rewrite of the object that
carries it). The one surviving implementation-declared word list,
:class:`SpacingStage`, says so in its own docstring and is not given a
schema CHECK anywhere (migration 0012's header).

**Decision scope.** This module — and P6-1's slice of the domain — carries
review *truth*: the objects and their durable rows. The review *policy* (how a
due decision is computed, how the ladder advances, how a view is produced) is
P6-2's and lives in :mod:`elc.scheduler.spacing`, a pure module with no store
and no clock; :class:`SchedulerController` composes the two by reading the
durable rows and asking the policy. The objects here stay interpretation-free:
they carry whatever the Scheduler computed, and P6-2 is what computes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    EvidenceGroupId,
    EvidenceModality,
    MomentId,
    ScheduleVersion,
    TargetId,
    TurnId,
)

#: docs/DATA_MODEL.md §5.2's ``review_state`` block, word for word — the one
#: review vocabulary the canonical documents pin. It is declared at module
#: level (and restated by :class:`ReviewState` below) so a pin can compare
#: the canonical block text with this constant *and* with the enum's members,
#: rather than trusting a single spelling: the P6-0 review finding (F-2) asked
#: for exactly this second shape, because a word list can hide in a module
#: constant just as easily as in an enum.
REVIEW_STATES: tuple[str, ...] = ("NOT_SCHEDULED", "UPCOMING", "DUE", "OVERDUE")


class ReviewState(StrEnum):
    """Coarse review lifecycle state — docs/DATA_MODEL.md §5.2, word for word.

    The four canonical words are ``NOT_SCHEDULED`` / ``UPCOMING`` / ``DUE`` /
    ``OVERDUE`` (:data:`REVIEW_STATES`). **The Phase 0 skeleton's five words
    (NEW / LEARNING / REVIEW / LAPSED / SUSPENDED) are deleted**, not renamed:
    they were invented before §5.2 existed as a specification and the
    canonical block does not contain any of them — in particular there is no
    ``SUSPENDED``, which is why the Phase 0 ``suspend_review`` face is gone
    too.

    The same four words appear in BF-02 as the ``schedule_urgency`` feature
    map's inputs (NOT_SCHEDULED 0.0 / UPCOMING 0.25 / DUE 0.75 / OVERDUE 1.0).
    That map is a **Planner feature assembly** (Phase 7) and is not this
    enum's semantics: this module states the state, and the read that turns a
    state into a number belongs to the consumer.
    """

    NOT_SCHEDULED = "NOT_SCHEDULED"
    UPCOMING = "UPCOMING"
    DUE = "DUE"
    OVERDUE = "OVERDUE"


class SpacingStage(StrEnum):
    """Scheduler-owned spacing stage — an **implementation-declared word list**.

    docs/DATA_MODEL.md §5.2 spells the column ``spacing_stage?`` and pins **no
    value range**, so STAGE_0 … STAGE_4 are this repository's declaration, not
    a canonical vocabulary — which is why migration 0012 puts no CHECK on the
    column (a CHECK would freeze an implementation word list into a canonical
    column) and why :attr:`ScheduleItem.spacing_stage` is ``... | None``
    (``None`` = 未分阶, no stage has been assigned).

    **This slice implements no transition and no ladder policy.** Nothing here
    advances a stage: the ladder's rules (what moves a target from one stage
    to the next) are not in §5.2 and live in :mod:`elc.scheduler.spacing`.
    **Revisit condition (P6-2's answer): the cut kept this list as it is** —
    ``spacing.stage_from_history`` counts the row's own engaged events and
    clamps into ``SPACING_STAGES``, whose order is exactly this enum's
    declaration order, and it says so where the transitions live. A cut that
    replaces the *words* must move the ladder with them: the list and the
    transitions are still decided together, and neither may move alone.
    """

    STAGE_0 = "STAGE_0"
    STAGE_1 = "STAGE_1"
    STAGE_2 = "STAGE_2"
    STAGE_3 = "STAGE_3"
    STAGE_4 = "STAGE_4"


@dataclass(frozen=True, kw_only=True)
class ScheduleItem:
    """docs/DATA_MODEL.md §5.2 ScheduleItem — twelve columns, word for word.

    The key is the **modality key**: one current row per
    ``(target_type, target_id, evidence_modality)`` (migration 0012's
    ``UNIQUE``), which is the same modality leg the learning projection keys
    on (``learner_target_state``, migration 0005) minus the user-scope column
    §5.2 does not carry. That key is also what makes the row addressable for a
    deletion by target without inventing a second lookup path.

    ``target_type`` is a bare ``str``: §5.2 names the column, migration 0012
    enforces the two canonical words (RESOURCE / CAPABILITY), and the platform
    declares no ``TargetType`` type to use here (``elc.learning.types``'s
    ``LearnerTargetStateRecord.target_type`` makes the same choice with the
    same evidence). ``target_id`` and ``evidence_modality`` do have platform
    types and use them — note that :class:`elc.platform.types.EvidenceModality`
    is the frozen V1 text pair, so ``VOICE_PRODUCTION`` /
    ``AUDIO_COMPREHENSION`` are unreachable through this field *and* refused by
    the migration's CHECK (§24.14; IP §16 DoD #22).

    **R4 — ``review_urgency`` is carried raw, with zero interpretation.** §5.2
    names the column and pins neither its type nor a value range, so this
    implementation carries it as ``float | None`` verbatim: no range is
    declared, no conversion is performed, and ``None`` means "not configured"
    (nothing more). BF-02 §6's numeric picture (NOT_SCHEDULED 0.0 / UPCOMING
    0.25 / DUE 0.75 / OVERDUE 1.0) is a **Planner feature assembly** (Phase 7)
    and not this column's semantics, and BF-02 §5's "missing Scheduler →
    schedule_urgency = 0" is a Phase 7 behaviour this slice is explicitly
    **not** allowed to implement. A consumer that wants a number derives it;
    nothing here stores one it did not receive.

    **P6-2 fills it, and R4 is the reading.** What a row *written by the
    Scheduler* now carries is derived: :func:`elc.scheduler.spacing.urgency_of`
    answers with the state's anchor, and ``recompute_schedule_item`` writes it
    — so a scheduled row's urgency has a value while a caller-written row still
    carries whatever it declared (``None`` = not configured). No interpolation
    and no scaling: one state, one anchor. The Phase 7 sentences above stay
    true of the *Planner's* use of the number (assembling BF-02 §6's benefit
    factor inside a PlanningContext), which is not this column's meaning.

    **R8 — ``version`` keeps §5.2's bare spelling.** §5.1's three objects had
    their ``version`` qualified (``goal_version`` / ``policy_version``)
    because three objects in one canonical family shared the bare name and the
    platform registry binds a version *type* by field name. §5.2's
    ScheduleItem block spells ``version`` and shares that bare name with
    nothing inside its own family, so the natural reading is kept and the
    field is typed :class:`elc.platform.types.ScheduleVersion`. The registry
    entry therefore carries **no** ``version_field`` binding — forging one
    would claim the canonical text says ``schedule_version`` where it says
    ``version``. Version comparison is **equality only, never order**: §5.2
    pins no ordering, and the store refuses a content change under an
    unchanged stamp (docs/DATA_MODEL.md §1.4).

    The fields are keyword-only because §5.2 declares the optional columns
    (``review_urgency`` / ``next_review_window_start?`` /
    ``next_review_window_end?`` / ``spacing_stage?``) *before* the required
    ``source_learning_watermark`` / ``version`` — a defaulted field cannot
    precede a required one in a positional dataclass, and keeping both the
    canonical column order (pinned by test) and the "not configured"
    ``None`` default is worth more than positional construction (the
    ``TeachingPolicyProfile`` precedent).

    ``source_learning_watermark`` is the durable form of DOMAIN_MODEL §9's
    read input ("Learning freshness / last strong retrieval / stability
    evidence"). **R6 gives it its meaning**: it is the Learning evidence
    watermark the row was computed from, carried as a **decimal string**
    (``str(get_learning_watermark())``), so a consumer recognises a stale row
    by ``item.source_learning_watermark != str(current watermark)`` — that
    comparison is the consumer's (BF-02 §5's stale-snapshot check is a
    Planner-side reading), and the durable layer neither parses nor compares
    it. A caller-written row still carries whatever string it declared: the
    column is opaque where it is stored. ``updated_at`` is the store's own
    clock: a constructed item leaves it empty and the durable writer stamps it.
    """

    schedule_item_id: str
    target_type: str
    target_id: TargetId
    evidence_modality: EvidenceModality
    review_state: ReviewState
    review_urgency: float | None = None
    next_review_window_start: str | None = None
    next_review_window_end: str | None = None
    spacing_stage: SpacingStage | None = None
    source_learning_watermark: str
    version: ScheduleVersion
    updated_at: str = ""


@dataclass(frozen=True, kw_only=True)
class ReviewEvent:
    """docs/DATA_MODEL.md §5.2 ReviewEvent — eight columns, word for word.

    One review *event*: an append-first fact about a schedule row (docs/
    DATA_MODEL.md §1.3 — a new event is a new row with a new
    ``review_event_id``, never a rewrite of an earlier one), which is why
    migration 0012 lands no unique index on ``schedule_item_id``: several
    events per row over time are the history. ``schedule_item_id`` is a real
    FK to :class:`ScheduleItem`, so the store refuses an event naming a row
    that does not exist with ``NOT_FOUND`` rather than a bare sqlite error.

    The three ``?`` columns are honestly optional: ``teaching_moment_id`` /
    ``source_turn_id`` / ``evidence_group_id`` are ``None`` when the event is
    not tied to a moment, does not originate in a turn, or cites no evidence
    group. §5.2 pins **no** relation between an event's own identifiers and
    the schedule row's key, so none is enforced here: an event may record an
    outcome about a group whose modality differs from the row's, and inventing
    a rule the canonical set does not make is what this slice refuses to do.

    **R5 — ``event_type`` carries no vocabulary.** §5.2 names the column and
    pins no value range, and neither ``behavioral_baselines/`` nor the
    canonical documents declare a single word for it (grepped, not assumed).
    It is therefore a raw ``str``, NOT NULL, with no CHECK in the schema, no
    branch-on-value anywhere in this slice, and no module constant here.
    **The p6-2 due policy did not claim it either**: the ladder and the window
    read ``engaged`` (§5.2's typed column) and ``created_at`` (recency) and
    give ``event_type`` no meaning at all — so the word list is still
    unclaimed, and it belongs to the flow that records *what a review did*
    (the review-outcome path, Phase 8). A constant declared here now would let
    a test pass over a vocabulary the canonical set never approved.

    ``engaged`` is the canonical boolean column (migration 0012 stores it as
    ``INTEGER CHECK (engaged IN (0, 1))``, the ``attempt_observed``
    precedent). ``created_at`` is the caller's timestamp when given and the
    store's clock otherwise (the 0007 ``created_at or _now()`` precedent) —
    never invented when the caller declared one.
    """

    review_event_id: str
    schedule_item_id: str
    teaching_moment_id: MomentId | None = None
    source_turn_id: TurnId | None = None
    event_type: str
    engaged: bool
    evidence_group_id: EvidenceGroupId | None = None
    created_at: str = ""


@dataclass(frozen=True)
class ScheduleView:
    """Planner input authority (docs/DOMAIN_MODEL.md §10).

    P6-1 declared the shape; **P6-2 produces it**
    (``SchedulerController.get_schedule_view``), and the fields below are what
    a production answers with:

    - ``schedule_version`` is the model stamp the buckets were classified by —
      :data:`elc.scheduler.spacing.SCHEDULER_MODEL_VERSION`, not a row's
      content-addressed ``ScheduleItem.version`` (one view holds many rows and
      therefore many row versions, so the view must say *which policy read
      them*);
    - ``as_of`` is the instant the classification was made at, carried so the
      Planner can tell a stale view from a fresh one without re-deriving it
      (the field is this cut's declaration: §5.2 has no ScheduleView block, and
      the spelling follows §5.2's own view block, whose ``SessionBudgetView``
      does carry ``as_of``);
    - the three buckets are the states the Planner acts on — ``due_items`` for
      ``DUE``, ``overdue_items`` for ``OVERDUE``, ``upcoming`` for
      ``UPCOMING`` — and **``NOT_SCHEDULED`` rows appear in none of them**.
      That is the one membership rule worth stating: a target with no review
      obligation is not "upcoming", it is unscheduled, and putting it in a
      bucket would hand the Planner a review debt the Scheduler never
      declared;
    - inside a bucket the order is ``(next_review_window_start,
      schedule_item_id)`` **ascending on the stored spelling** of the window
      column, not on the instant it spells: the key is the column's text as the
      durable row holds it, exactly the convention the store's history read
      uses for ``created_at`` (p6-1's F-3 byte-order note). The two orders
      differ only for rows whose windows are written with different UTC offsets
      — and they are *meant* to: membership is a question about instants,
      ordering is a question about rows, and a deterministic answer to the
      second is a property of the stored values (the tie-break on
      ``schedule_item_id`` makes it total, since two rows may legitimately
      share a window). Reading the order as an instant order is a Phase 7
      Planner-assembly decision and is **not** what this view declares;
    - the order is deterministic either way: two reads of one world answer
      byte-identically instead of in whatever order the rows happened to
      arrive.
    """

    schedule_version: ScheduleVersion
    as_of: str
    due_items: tuple[ScheduleItem, ...] = ()
    overdue_items: tuple[ScheduleItem, ...] = ()
    upcoming: tuple[ScheduleItem, ...] = ()
