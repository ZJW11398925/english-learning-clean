"""Feature-assembly authority — what the Planner may assume, and what it may
not (P7-0).

The single most important rule this cut lands is BF-02 v1.1 §5's (lines
128–166), quoted verbatim:

    Planner 不允许：
        missing Scheduler → schedule_urgency = 0
    也不允许：
        stale LearningSnapshot → 假装仍有效

    PlanningContext 至少包含：
        feature_assembly_status
        snapshot_status
        missing_authorities[]
        natural_break_available

    如果：
        feature_assembly_status != COMPLETE
        or
        snapshot_status != VALID
    返回：
        PlannerExecutionStatus = DEGRADED
        PlannerDecision = none

    Runtime 才输出 DEGRADED_NO_AUTOMATIC_TEACHING，而不是伪造 NO_TARGET。

This module is that rule, made executable: it reads the authorities a
PlanningContext would hold, answers the two statuses and the missing-authority
list, and never substitutes a number for an authority it does not have.

**What this module is not.** It is not the Planner kernel: no candidate is
scored, no factor vector is completed, no decision is produced, and shadow
mode does not exist. What lands here is the *authority boundary* — the part
every later Planner cut has to answer first, and the part BF-02 §5 refuses to
let anyone fudge.

Three readings are this cut's own judgement rather than a quotation, and each
one says so where it is made:

- **the profile mapping** (:data:`TEACHING_FREQUENCY_TO_PROFILE`): §5.1's
  ``teaching_frequency`` and BF-02's profile words are two vocabularies and no
  document maps one to the other (the ``TeachingFrequency`` docstring says the
  words are implementation-declared). Each pair below carries its basis: the
  profile *word* is BF-02's and quoted, the *pairing* is a declared judgement
  with a revisit condition;
- **the schedule-urgency conversion** (:func:`schedule_urgency_of`): BF-02 §6's
  numbers are reference values, and the row's stored ``review_urgency`` is the
  Scheduler's own;
- **the readiness and goal-mapping legs** of ``missing_authorities``: the
  Planner needs a target's content level and the goal/assessment pack mapping
  (IMPLEMENTATION_PLAN §7 line 340), and neither is landed — this corpus
  reports no level for any target and ``assessment_targets`` has no consumer —
  so the honest production answer today is INCOMPLETE (see
  :func:`assemble_feature_authority`).

**Versioning.** :data:`POLICY_PROFILE_MAPPING_VERSION` stamps the policy →
profile mapping and :data:`FEATURE_ASSEMBLY_MODEL_VERSION` the assembly's own
readings; a calibration that moves a number or a pairing moves the stamp with
it (BF-02 §21: a parameter change is ``planner_profile_version++`` plus a full
benchmark regression and a decision diff review, not an edit).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Protocol, Sequence

from elc.platform.types import PlannerExecutionStatusValue
from elc.scheduler.types import ReviewState
from elc.user_config.types import TeachingFrequency

__all__ = [
    "FEATURE_ASSEMBLY_MODEL_VERSION",
    "POLICY_PROFILE_MAPPING_VERSION",
    "SCHEDULE_URGENCY_BANDS",
    "TEACHING_FREQUENCY_TO_PROFILE",
    "AuthorityName",
    "FeatureAssemblyStatus",
    "FeatureAuthority",
    "GoalPortfolioPort",
    "LearningSnapshotPort",
    "PlannerProfile",
    "ProfileMapping",
    "ScheduleAuthority",
    "ScheduleRowPort",
    "ScheduleViewPort",
    "SnapshotStatus",
    "TeachingPolicyPort",
    "assemble_feature_authority",
    "execution_status_of",
    "goal_relevance_of",
    "profile_mapping_of",
    "schedule_authority_of",
    "schedule_urgency_of",
]

#: Stamps the two versioned readings of this module (module docstring).
FEATURE_ASSEMBLY_MODEL_VERSION = "fa1"
POLICY_PROFILE_MAPPING_VERSION = "tp2bf02-v1"


# -- the statuses and the authority vocabulary -------------------------------


class FeatureAssemblyStatus(StrEnum):
    """BF-02 §5's ``feature_assembly_status``.

    ``COMPLETE`` = every authority the assembly needs is present and usable;
    ``INCOMPLETE`` = at least one is not, and the reason is in
    :attr:`FeatureAuthority.missing_authorities` / ``reasons``. The two words
    are BF-02's; nothing here mints a third.
    """

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class SnapshotStatus(StrEnum):
    """BF-02 §5's ``snapshot_status`` — the Learning snapshot's currency.

    ``VALID`` = a snapshot is present **and** was computed at the current
    Learning evidence watermark; ``INVALID`` = it is absent, the current
    watermark is unknown, or the snapshot's ``evidence_watermark`` is an older
    one (BF-02 §5's "stale LearningSnapshot → 假装仍有效" is this word).
    """

    VALID = "VALID"
    INVALID = "INVALID"


class ScheduleAuthority(StrEnum):
    """The Scheduler's half of the same question, in three words.

    ``CURRENT`` = a §10 view is present and no row in it is stale;
    ``STALE`` = a view is present and at least one row's
    ``source_learning_watermark`` is not the current watermark (so its
    ``review_state`` / ``review_urgency`` describe an earlier evidence set);
    ``MISSING`` = no view at all. ``STALE`` and ``MISSING`` are different
    facts and both are unusable, which is exactly why BF-02 §5 forbids
    answering either with a number.
    """

    CURRENT = "CURRENT"
    STALE = "STALE"
    MISSING = "MISSING"


class AuthorityName(StrEnum):
    """What a ``missing_authorities[]`` entry can name.

    BF-02 §5 pins the list and not its vocabulary, so these seven words are
    this cut's, one per authority the assembly reads. An entry appears when
    the assembly cannot *use* that authority — absent, or present but not
    current — and the matching line in
    :attr:`FeatureAuthority.reasons` says which of the two it was.

    **The declaration order is the assembly's emission order** (the order
    :func:`assemble_feature_authority` checks its inputs in), so two
    assemblies of one world produce byte-identical records and a reader can
    match ``missing_authorities[i]`` with ``reasons[i]`` by position.
    """

    LEARNING_SNAPSHOT = "LEARNING_SNAPSHOT"
    SCHEDULE = "SCHEDULE"
    TEACHING_POLICY = "TEACHING_POLICY"
    GOAL_PORTFOLIO = "GOAL_PORTFOLIO"
    GOAL_ASSESSMENT_PACK_MAPPING = "GOAL_ASSESSMENT_PACK_MAPPING"
    CURRICULUM_READINESS = "CURRICULUM_READINESS"
    PLANNER_CONSTRAINT = "PLANNER_CONSTRAINT"


class PlannerProfile(StrEnum):
    """BF-02's three policy profiles, word for word.

    BF-02 §13's reference block (lines 424–427) names all three
    (``BALANCED`` / ``STUDY_FIRST`` / ``LOUNGE``) and
    ``planner_reference_profile_v1_1.json``'s ``policy_profiles`` carries them
    with their multipliers and activation thresholds. They are BF-02's
    vocabulary, never §5.1's — §5.1's ``teaching_frequency`` is a different
    column with a different (implementation-declared) word list, and the
    mapping between the two is :data:`TEACHING_FREQUENCY_TO_PROFILE`.
    """

    LOUNGE = "LOUNGE"
    BALANCED = "BALANCED"
    STUDY_FIRST = "STUDY_FIRST"


#: BF-02 §6's reference ``schedule_urgency`` bands, taken from
#: ``behavioral_baselines/planner/planner_reference_profile_v1_1.json``'s
#: ``reference_factor_bands.schedule_urgency`` (NOT_SCHEDULED 0.0 / UPCOMING
#: 0.25 / DUE 0.75 / OVERDUE 1.0). **Reference values, not frozen ones**:
#: BF-02 §21 says the 92/92 regression does not validate them, and the profile
#: JSON's own ``status`` is ``REFERENCE_DEFAULT_CALIBRATABLE``. A phase-7 pin
#: extracts them from that frozen asset and compares them here *and* with the
#: Scheduler's own anchor table, so one number has one source and a
#: transcription slip fails a test instead of shipping.
SCHEDULE_URGENCY_BANDS: Mapping[ReviewState, float] = {
    ReviewState.NOT_SCHEDULED: 0.0,
    ReviewState.UPCOMING: 0.25,
    ReviewState.DUE: 0.75,
    ReviewState.OVERDUE: 1.0,
}


# -- the versioned policy → profile mapping ----------------------------------


@dataclass(frozen=True)
class ProfileMapping:
    """One ``teaching_frequency`` → (BF-02 profile, BF-03 switch) pair.

    ``basis`` is the pair's justification and it is deliberately *not* one
    kind of thing: where the profile **word** is BF-02's, the text quotes the
    block it comes from; where the **pairing** is this cut's reading, the text
    says so and ``revisit`` names the condition that re-opens it. A mapping
    this table cannot justify is a mapping it does not carry.
    """

    teaching_frequency: TeachingFrequency
    profile: PlannerProfile
    automatic_teaching_enabled: bool
    basis: str
    revisit: str


#: BF-02's profile words are quoted from §13's reference block and from the
#: reference profile JSON; the *pairings* are declared judgements (module
#: docstring). Reading the table: a policy that says "teach me as often as is
#: useful" gets BF-02's middle profile, and the two ends are the two ends of
#: BF-02's own three-step scale — the direction a monotone pairing has to go.
TEACHING_FREQUENCY_TO_PROFILE: Mapping[TeachingFrequency, ProfileMapping] = {
    TeachingFrequency.OFF: ProfileMapping(
        teaching_frequency=TeachingFrequency.OFF,
        profile=PlannerProfile.LOUNGE,
        automatic_teaching_enabled=False,
        basis=(
            "OFF is 'no teaching', and the only BF-03 §13 switch that stops"
            " automatic teaching is its own: automatic_teaching_enabled ="
            " false blocks automatic OPEN and AUTO_CONTINUE while leaving"
            " USER_INITIATED OPEN / USER_REQUESTED_CONTINUE alone (BF-03"
            " lines 394–409). The *profile* still has to answer, because a"
            " user-initiated request is ranked through it — so a policy that"
            " asked for no teaching at all is assembled at BF-02's least"
            " intervening profile (LOUNGE, §13's +0 row)."
        ),
        revisit=(
            "a canonical column carries the automatic-teaching switch itself"
            " (§5.1 does not: P6-0 removed the Phase 0 field the canonical set"
            " does not have), or a decision lands the OFF case explicitly"
        ),
    ),
    TeachingFrequency.MINIMAL: ProfileMapping(
        teaching_frequency=TeachingFrequency.MINIMAL,
        profile=PlannerProfile.LOUNGE,
        automatic_teaching_enabled=True,
        basis=(
            "declared judgement: MINIMAL asks for the least teaching that is"
            " still teaching, and LOUNGE is BF-02's least intervening profile"
            " (initiative_multiplier PROACTIVE 0.55, activation threshold"
            " 0.36 — the reference profile's own numbers). No document pins"
            " the pairing; the direction is the only monotone one."
        ),
        revisit=(
            "BF-02 adds a fourth profile, or a calibration study contradicts"
            " the ordering (a pairing change moves"
            " POLICY_PROFILE_MAPPING_VERSION)"
        ),
    ),
    TeachingFrequency.BALANCED: ProfileMapping(
        teaching_frequency=TeachingFrequency.BALANCED,
        profile=PlannerProfile.BALANCED,
        automatic_teaching_enabled=True,
        basis=(
            "declared judgement on a quoted word: BF-02's middle profile is"
            " spelled BALANCED (§13's reference block, and the reference"
            " profile's policy_profiles key), so the middle frequency is"
            " mapped to the middle profile by the only name the two"
            " vocabularies share. The frequencies themselves are"
            " implementation-declared (elc.user_config.types."
            "TeachingFrequency), so the *pairing* is still a judgement."
        ),
        revisit=(
            "either vocabulary is re-spelled or re-scoped; the same calibration"
            " clause as the rows above"
        ),
    ),
    TeachingFrequency.EAGER: ProfileMapping(
        teaching_frequency=TeachingFrequency.EAGER,
        profile=PlannerProfile.STUDY_FIRST,
        automatic_teaching_enabled=True,
        basis=(
            "declared judgement, capped by BF-02: BF-02 declares exactly three"
            " profiles, so an eager policy is assembled at the most active"
            " declared one (STUDY_FIRST) and the fact that the user asked for"
            " more is a calibration input — BF-02 §21: adding or retuning a"
            " profile is planner_profile_version++ plus a full benchmark"
            " regression and a decision diff review, never a fourth word"
            " invented here."
        ),
        revisit=(
            "a calibration study moves the top of the scale, or BF-02 gains a"
            " profile louder than STUDY_FIRST"
        ),
    ),
}


def profile_mapping_of(
    teaching_policy: TeachingPolicyPort,
) -> ProfileMapping | None:
    """The mapping for one policy, or ``None`` when it cannot be mapped.

    ``None`` means the policy's ``teaching_frequency`` is not one of the four
    declared words — a value the schema does not forbid (migration 0011 puts
    no CHECK on the column, precisely because the word list is
    implementation-declared) and that this table therefore cannot map. The
    caller reports the gap (:func:`assemble_feature_authority` does, as a
    missing ``TEACHING_POLICY`` authority); it never guesses a profile, and it
    never falls back to "the default policy", because there is no default
    profile in BF-02.
    """

    return TEACHING_FREQUENCY_TO_PROFILE.get(teaching_policy.teaching_frequency)


# -- the two authority judgements --------------------------------------------


def schedule_authority_of(
    schedule_view: ScheduleViewPort | None, current_watermark: int
) -> ScheduleAuthority:
    """The §10 view's currency (the P7-0 handshake, read at view level).

    ``MISSING`` when there is no view; ``STALE`` when any row the view holds
    carries a ``source_learning_watermark`` that is not the current one; else
    ``CURRENT``. An **empty** view is CURRENT: "the Scheduler has nothing due"
    is an answer, not an absence, and BF-02 §5's missing-Scheduler case is
    about a Planner holding no schedule authority at all.

    The comparison is the Scheduler's own primitive
    (:func:`elc.scheduler.authority.currency_of`) — same rule, one spelling of
    it; this function only decides *which* rows it is asked about.
    """

    if schedule_view is None:
        return ScheduleAuthority.MISSING
    expected = str(current_watermark)
    for row in _rows_of(schedule_view):
        if row.source_learning_watermark != expected:
            return ScheduleAuthority.STALE
    return ScheduleAuthority.CURRENT


def schedule_urgency_of(
    row: ScheduleRowPort | None, authority: ScheduleAuthority
) -> float | None:
    """The ``schedule_urgency`` factor for one candidate — never a fake ``0``.

    ``None`` = **UNKNOWN**, and that word is this function's whole point: BF-02
    §5 forbids turning a missing or stale Scheduler authority into ``0``, and
    ``0`` in a factor vector claims something the assembly cannot claim
    ("known to be irrelevant"). The three cases, in order:

    1. ``authority`` is not ``CURRENT`` → UNKNOWN. A stale row's number
       describes an earlier evidence set and is not this candidate's urgency;
    2. ``row is None`` → UNKNOWN. This is **not** "no review debt": P6-2 wrote
       a ``NOT_SCHEDULED`` row for exactly this reason — "refusing to write it
       would leave the Planner unable to distinguish 'no review debt' from
       'the Scheduler was never asked'" (elc.scheduler.controller) — so a
       target with no row is a target the Scheduler was never asked about, and
       its factor is unknown rather than zero;
    3. otherwise the **row's own** ``review_urgency`` when the Scheduler
       configured it, and BF-02 §6's reference band for its ``review_state``
       when it did not (a caller-written row). The stored column wins because
       it is the Scheduler's own number (§5.2's column, P6-2 R4); the band is
       the assembly's fallback, and the two are pinned equal for
       Scheduler-written rows so a divergence means someone wrote the column
       by hand.

    The returned number, when there is one, is a *reference* value: BF-02 §6's
    bands are calibratable (§21), which is why
    :data:`FEATURE_ASSEMBLY_MODEL_VERSION` stamps the reading.
    """

    if authority is not ScheduleAuthority.CURRENT:
        return None
    if row is None:
        return None
    if row.review_urgency is not None:
        return row.review_urgency
    return SCHEDULE_URGENCY_BANDS[row.review_state]


def goal_relevance_of(goal_relation: str | None) -> float | None:
    """The ``goal_relevance`` factor: **UNKNOWN (``None``) in this cut**.

    ``goal_relevance`` is assembled from a candidate's goal leg through the
    goal/assessment pack mapping IMPLEMENTATION_PLAN §7 line 340 lists
    ("Goal/Assessment pack mapping") — and that mapping is not landed: §5.1's
    ``assessment_targets`` column has no consumer anywhere in this repository,
    so nothing can turn a goal relation into a number.

    ``0`` is therefore forbidden here and ``None`` is the honest answer: ``0``
    would say "known to be irrelevant to this user's goals", which is a claim
    about a mapping nobody has built. The parameter is the leg the mapping
    would consume, so the seam is where the mapping will plug in; when it
    lands, this function returns the mapping's number and the missing-
    authority entry below retires with it.
    """

    return None


# -- the assembly ------------------------------------------------------------


@dataclass(frozen=True)
class FeatureAuthority:
    """BF-02 §5's PlanningContext fields, and the two context-level readings.

    ``status`` / ``snapshot_status`` / ``missing_authorities`` /
    ``natural_break_available`` are the four §5 names; ``schedule_authority``
    is context-level (a view's currency is a fact about the context, not about
    one candidate) and ``reasons`` is the trace a reviewer reads to see *why*
    something is missing (one line per entry of ``missing_authorities``, in the
    same order).

    **The candidate-level factors are not fields here.** ``schedule_urgency``
    and ``goal_relevance`` are per-candidate by nature, so they are functions
    on this module (:func:`schedule_urgency_of` / :func:`goal_relevance_of`)
    and folding one of them into this record would imply a value for the whole
    context — the exact kind of global answer BF-02 §5's per-authority reading
    avoids.

    ``reasons`` is a trace, not a decision: nothing here selects, ranks or
    suppresses anything, and the Planner kernel that would consume this record
    is a later cut.
    """

    status: FeatureAssemblyStatus
    snapshot_status: SnapshotStatus
    schedule_authority: ScheduleAuthority
    missing_authorities: tuple[AuthorityName, ...]
    natural_break_available: bool
    planner_profile: PlannerProfile | None
    automatic_teaching_enabled: bool
    policy_mapping_version: str
    reasons: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """``status is COMPLETE and snapshot_status is VALID`` — BF-02 §5's
        conjunction, in one place so the two statuses cannot be read apart."""

        return (
            self.status is FeatureAssemblyStatus.COMPLETE
            and self.snapshot_status is SnapshotStatus.VALID
        )


def execution_status_of(
    authority: FeatureAuthority,
) -> PlannerExecutionStatusValue:
    """BF-02 §5 lines 153–166: the two statuses decide SUCCEEDED vs DEGRADED.

    SUCCEEDED exactly when ``feature_assembly_status == COMPLETE`` **and**
    ``snapshot_status == VALID``; DEGRADED otherwise. The pairing with
    ``PlannerDecision = none`` is already enforced structurally by
    :class:`elc.planner.types.PlanningOutcome` (a DEGRADED status carrying a
    decision is refused), so this function only answers the status half and
    the outcome type does the rest — one home per rule.

    FAILED / UNAVAILABLE are deliberately not reachable here: they are the
    execution's own failures (a raised collaborator, an unreadable store), not
    assembly verdicts (docs/DATA_MODEL.md §14's vocabulary).
    """

    if authority.complete:
        return PlannerExecutionStatusValue.SUCCEEDED
    return PlannerExecutionStatusValue.DEGRADED


def assemble_feature_authority(
    *,
    learning_snapshot: LearningSnapshotPort | None,
    current_learning_watermark: int | None,
    schedule_view: ScheduleViewPort | None,
    teaching_policy: TeachingPolicyPort | None,
    goal_portfolio: GoalPortfolioPort | None,
    curriculum_readiness: Mapping[str, str | None] | None,
    constraint_view_present: bool,
    natural_break_available: bool = False,
) -> FeatureAuthority:
    """Assemble the authority record for one PlanningContext (BF-02 §5).

    Every input is what a caller *holds*, and every gap is reported rather
    than filled:

    =========================  =====================================
    input                      gap when
    =========================  =====================================
    ``learning_snapshot``      absent, or its ``evidence_watermark`` is
                               not ``current_learning_watermark`` →
                               ``snapshot_status = INVALID`` **and** a
                               ``LEARNING_SNAPSHOT`` entry
    ``current_learning_watermark``  ``None`` (the Learning watermark is
                               unreadable) → same as above
    ``schedule_view``          absent → ``SCHEDULE`` (authority MISSING);
                               present with a stale row → ``SCHEDULE``
                               (authority STALE) — BF-02 §5's prohibition,
                               with the reason saying which
    ``teaching_policy``        absent, or its frequency is not a declared
                               word → ``TEACHING_POLICY`` (and the profile
                               is ``None``)
    ``goal_portfolio``         absent → ``GOAL_PORTFOLIO``; present and
                               naming ``assessment_targets`` →
                               ``GOAL_ASSESSMENT_PACK_MAPPING``
                               (IMPLEMENTATION_PLAN §7 line 340 is not
                               implemented, so those names have no reader)
    ``curriculum_readiness``   absent (no level supply) →
                               ``CURRICULUM_READINESS``; present with a
                               ``None`` level for any candidate → the same
                               entry (a target whose level is unknown is a
                               target whose eligibility cannot be judged)
    ``constraint_view_present``  ``False`` → ``PLANNER_CONSTRAINT`` (a
                               Planner that cannot see the user's
                               constraints cannot claim completeness)
    =========================  =====================================

    The order of ``missing_authorities`` / ``reasons`` is fixed (the
    :class:`AuthorityName` declaration order) so two assemblies of one world
    are identical records.

    ``natural_break_available`` is carried through unchanged: BF-02 §5 lists
    it in the PlanningContext and BF-02 §13's coverage-starvation safeguard
    reads it, but *where it comes from* is the context assembly's question,
    not this record's — nothing here derives it, and defaulting it to
    ``False`` is a value, not a missing authority.

    **Today's answer, honestly.** With this repository's shipped supply every
    leg of the table fires except the schedule one: no Planner assembles a
    PlanningContext yet, the corpus reports no content level for any target,
    and the goal/assessment mapping does not exist. A caller that wires the
    real faces therefore gets ``INCOMPLETE`` — which is the point: BF-02 §5's
    DEGRADED is the correct production verdict until the gaps are closed, and
    a synthetic ``0`` would hide it.
    """

    missing: list[AuthorityName] = []
    reasons: list[str] = []

    def note(name: AuthorityName, reason: str) -> None:
        missing.append(name)
        reasons.append(reason)

    snapshot_status = SnapshotStatus.VALID
    if learning_snapshot is None:
        snapshot_status = SnapshotStatus.INVALID
        note(
            AuthorityName.LEARNING_SNAPSHOT,
            "no Learning snapshot: BF-02 §5's snapshot_status cannot be VALID"
            " without one, and a factor vector assembled from nothing is what"
            " its DEGRADED rule exists to prevent",
        )
    elif current_learning_watermark is None:
        snapshot_status = SnapshotStatus.INVALID
        note(
            AuthorityName.LEARNING_SNAPSHOT,
            "the current Learning evidence watermark is unreadable, so the"
            " snapshot's currency cannot be established (BF-02 §5: a snapshot"
            " that cannot be shown current is not valid)",
        )
    elif learning_snapshot.evidence_watermark != current_learning_watermark:
        snapshot_status = SnapshotStatus.INVALID
        note(
            AuthorityName.LEARNING_SNAPSHOT,
            "the snapshot's evidence_watermark is not the current Learning"
            " watermark: this is BF-02 §5's stale snapshot, and treating it as"
            " valid is the one thing that sentence forbids",
        )

    schedule_authority = ScheduleAuthority.MISSING
    if schedule_view is None:
        note(
            AuthorityName.SCHEDULE,
            "no Scheduler view: BF-02 §5 forbids answering this with"
            " schedule_urgency = 0, so the factor is left unknown and the"
            " assembly is incomplete",
        )
    elif current_learning_watermark is None:
        schedule_authority = ScheduleAuthority.STALE
        note(
            AuthorityName.SCHEDULE,
            "the current Learning watermark is unreadable, so no schedule row"
            " can be shown current: a row that cannot be shown current is not"
            " used as one (BF-02 §5's stale-authority rule, read fail-closed)",
        )
    else:
        schedule_authority = schedule_authority_of(
            schedule_view, current_learning_watermark
        )
        if schedule_authority is ScheduleAuthority.STALE:
            note(
                AuthorityName.SCHEDULE,
                "the Scheduler view holds at least one row computed at an"
                " older Learning watermark: BF-02 §5's stale authority, whose"
                " numbers describe an earlier evidence set",
            )

    mapping = (
        None if teaching_policy is None else profile_mapping_of(teaching_policy)
    )
    if teaching_policy is None:
        note(
            AuthorityName.TEACHING_POLICY,
            "no TeachingPolicyProfile: BF-02 §20 lists it among the frozen"
            " inputs, so without one neither a profile nor the"
            " automatic-teaching switch can be assembled",
        )
    elif mapping is None:
        note(
            AuthorityName.TEACHING_POLICY,
            "the policy's teaching_frequency is not one of the four declared"
            " words, so no BF-02 profile can be assembled from it (the mapping"
            " never guesses a default profile)",
        )

    if goal_portfolio is None:
        note(
            AuthorityName.GOAL_PORTFOLIO,
            "no goal portfolio: goal_relevance has no leg to read, and 0 would"
            " claim the candidate is known to be irrelevant to the user's goals",
        )
    elif goal_portfolio.assessment_targets:
        note(
            AuthorityName.GOAL_ASSESSMENT_PACK_MAPPING,
            "the portfolio names assessment targets and the Goal/Assessment"
            " pack mapping (IMPLEMENTATION_PLAN §7 line 340) is not"
            " implemented: nothing in this repository consumes"
            " assessment_targets, so the goal leg cannot be turned into a"
            " factor",
        )

    if curriculum_readiness is None:
        note(
            AuthorityName.CURRICULUM_READINESS,
            "no content-level supply: a candidate's eligibility cannot be"
            " judged without one (the Planner's hard eligibility reads it)",
        )
    else:
        unknown_levels = sorted(
            target
            for target, level in curriculum_readiness.items()
            if level is None
        )
        if unknown_levels:
            note(
                AuthorityName.CURRICULUM_READINESS,
                "no content level is reachable for"
                f" {len(unknown_levels)} candidate(s) the caller holds"
                f" (first: {unknown_levels[0]}): a target whose level is"
                " unknown is one whose eligibility cannot be judged",
            )

    if not constraint_view_present:
        note(
            AuthorityName.PLANNER_CONSTRAINT,
            "no PlannerConstraintView: the user's constraints are the"
            " suppression authority, and a Planner that cannot read them"
            " cannot claim a complete assembly",
        )

    return FeatureAuthority(
        status=(
            FeatureAssemblyStatus.COMPLETE
            if not missing
            else FeatureAssemblyStatus.INCOMPLETE
        ),
        snapshot_status=snapshot_status,
        schedule_authority=schedule_authority,
        missing_authorities=tuple(missing),
        natural_break_available=natural_break_available,
        planner_profile=None if mapping is None else mapping.profile,
        automatic_teaching_enabled=(
            False if mapping is None else mapping.automatic_teaching_enabled
        ),
        policy_mapping_version=POLICY_PROFILE_MAPPING_VERSION,
        reasons=tuple(reasons),
    )


# -- the structural ports ----------------------------------------------------
#
# The Planner reads views, not stores: each port declares exactly the fields
# this module uses and nothing else, the elc.scheduler.spacing.LearningReadPort
# convention (a port that named more would invite a reader to consume more).


class LearningSnapshotPort(Protocol):
    """The one DATA_MODEL §12 field the assembly reads: ``evidence_watermark``.

    Satisfied structurally by :class:`elc.learning.types.LearningSnapshot` as
    it stands — same field name, same ``int`` type. The snapshot's targets are
    deliberately not declared: completing a factor vector is the Planner
    kernel's job (a later cut), not this record's.
    """

    evidence_watermark: int


class ScheduleRowPort(Protocol):
    """The three §5.2 columns the urgency conversion reads.

    Satisfied structurally by :class:`elc.scheduler.types.ScheduleItem`.
    """

    review_state: ReviewState
    review_urgency: float | None
    source_learning_watermark: str


class ScheduleViewPort(Protocol):
    """The three §10 buckets (docs/DOMAIN_MODEL.md §10).

    Satisfied structurally by :class:`elc.scheduler.types.ScheduleView`. All
    three are read and none is optional: a row that is due, overdue or upcoming
    is still a row whose currency decides whether this assembly may use it.
    """

    due_items: Sequence[ScheduleRowPort]
    overdue_items: Sequence[ScheduleRowPort]
    upcoming: Sequence[ScheduleRowPort]


class TeachingPolicyPort(Protocol):
    """The one §5.1 column the profile mapping reads: ``teaching_frequency``.

    Satisfied structurally by
    :class:`elc.user_config.types.TeachingPolicyProfile`. The eight unpinned
    columns beside it are deliberately not declared — this cut invents no
    vocabulary for them (the type module says the same).
    """

    teaching_frequency: TeachingFrequency


class GoalPortfolioPort(Protocol):
    """The one §5.1 column the goal legs read: ``assessment_targets``.

    Satisfied structurally by
    :class:`elc.user_config.types.LearningGoalPortfolio`. The column is read
    only to answer "is the pack mapping needed *and* absent?" — nothing here
    interprets an assessment name.
    """

    assessment_targets: Sequence[str]


def _rows_of(view: ScheduleViewPort) -> tuple[ScheduleRowPort, ...]:
    """Every row the §10 view holds, in its own bucket order."""

    return (*view.due_items, *view.overdue_items, *view.upcoming)
