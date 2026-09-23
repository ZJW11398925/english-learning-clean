"""ActiveLearningFrontier — the eligible set, named (P7-3).

docs/STATE_MACHINES.md §19's "Planner Flow State" walks the decision flow with
one step docs/DOMAIN_MODEL.md §10.1 does not have::

    → hard eligibility (scope/prereq/readiness/modality/suppression)
    → ActiveLearningFrontier
    → Policy Utility

and docs/DOMAIN_MODEL.md's own section says what the frontier *is*::

    ### ActiveLearningFrontier

    动态计算：

    curriculum candidates
    ∪ scheduled review
    ∪ confirmed gaps
    ∪ unknown probes
    ∪ transfer opportunities
    ∪ personal expression needs
    ∪ current context opportunities

    经过 eligibility/prerequisite/content readiness/user constraints/cognitive
    feasibility 后形成 Frontier。

**The two documents' order, and how this cut reads them together.** §10.1's
eleven-step block — the one P7-1 made executable, step for step — has no
``ActiveLearningFrontier`` line, so the two canonical documents put the frontier
in different places relative to policy utility (P7-2 registered the difference
and handed it to p7-3 by name). Read together there is exactly one place it can
stand, and it is §19's:

- **position: after hard eligibility, before Policy Utility.** §10.1's order is
  untouched: :class:`~elc.planner.kernel.KernelStep` keeps its eleven values in
  their eleven positions (P7-1's suite pins them against the canonical block
  character for character), and no step is inserted anywhere. What §19's line
  names is not a twelfth *step* but the set §10.1's fourth step has already
  produced, and a set is not a position in a pipeline. **Registered:** this
  position is argued on the *set's identity* (members = step 4's survivors), not
  on where a frontier value is materialized — the implementation builds it
  inside ``kernel._evaluation``, at the end of the flow, and every consumer
  today reads it off the evaluation record, which is an observation difference
  of nothing because the frontier filters nothing and decides nothing. Revisit:
  a consumer needs to read the frontier **before** Policy Utility runs (a step
  5/6 reading of the member set, a trace field that has to be filled mid-flow,
  or a second record carrying the set) — then the set's identity and its
  materialization point have to be reconciled, and that reconciliation is a cut
  of its own rather than a move of the value;
- **members: the candidates hard eligibility did not exclude.** That is the
  whole reading — "经过 eligibility … 后形成 Frontier" — and it is why this cut
  does **not** filter anything: the frontier is a *view of the survivor set*,
  so adding a member test here would silently change the eligible set, which is
  the one thing the frontier may not do. An excluded candidate is **not** a
  frontier member (it is recorded on the excluded side, with the reason step 4
  gave), and the frontier's coverage of the canonical set is checkable rather
  than asserted: :attr:`ActiveLearningFrontier.members` and
  :attr:`ActiveLearningFrontier.excluded` are disjoint and together hold every
  canonical candidate the kernel was given;
- **the only kernel-side change is the column.** docs/DATA_MODEL.md §14 lists
  ``frontier_candidate_ids[]`` on ``PlannerEvaluation``;
  :class:`~elc.planner.types.PlannerEvaluation` carries it now, appended and
  defaulted so no existing construction moves, and the kernel fills it from the
  step-4 survivors through :func:`frontier_of` — so the column and this module's
  definition cannot drift apart.

**No new causal filter — and the two authorities that would need one are
registered.** DOMAIN_MODEL's closing line names five gates:
``eligibility`` / ``prerequisite`` / ``content readiness`` are steps the kernel
already walks (§10.1's hard eligibility, BF-02 §10's readiness floors, BF-02
§11's prerequisite contract), ``user constraints`` is read on the supply side
(§9's constraint view marks suppression and resolves the §12 scope, both of
which the kernel's step 4 then decides on), and ``cognitive feasibility`` **has
no authority in this repository at all**: DOMAIN_MODEL §10's input block names
``SessionBudgetView`` as the authority for a session's budget, P6-1 registered
it to Phase 8 (its input is BF-03 §17's runtime session state, which no cut
produces), and this cut does not invent a number where that view would be. See
:data:`MISSING_FRONTIER_AUTHORITIES`: an entry there is a *registration*, never
a predicate, and nothing in this module reads it.

**The seven members and the fourteen source words.** §6's Track A / Track B
sources (docs/PRODUCT_CONTRACT.md: six and eight words, landed by P7-2) are how
a candidate says *why* it exists, and the union block above is how the document
says *what kinds* of opportunity the frontier is made of. No canonical document
maps one list onto the other, so the pairing is this cut's **declared reading**:
:data:`SOURCE_FRONTIER_MEMBERS` is one row per source word — total over all
fourteen — each carrying the members it belongs to and its reason, and
:data:`FRONTIER_MAPPING_REVISIT` names what re-opens the table. Three of the
seven member lines are quoted back by a source of the same name
(``scheduled review`` / ``confirmed gaps`` / ``unknown probes``), two more are
the whole family of one Track A name, and the rest are declared; no member is
left without a mapper, which is checkable one row at a time.

**Membership is a label, never a condition.** A candidate with no §6 source
word — BF-02 §20's frozen suite supplies vectors and no generator labels, and a
caller may build a proposal by hand — is a frontier member with an empty
membership tuple and its unknown origin words listed in
:attr:`FrontierMemberEntry.unmapped_origins`. That is deliberate: eligibility
is step 4's answer, membership is a reading of the origin label, and a reading
that could remove a candidate would be the filter this module refuses to add.

**What this module is not.** It is not a second eligibility check, not a
scheduler of any kind, and it holds no store: it is a pure function of the
canonical candidate set and that set's exclusions. It decides nothing about
teaching (the Gate keeps the authorization authority), and it says nothing
about shadow mode, which is p7-4's work item.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

__all__ = [
    "FRONTIER_MAPPING_REVISIT",
    "FRONTIER_MEMBERS",
    "MISSING_FRONTIER_AUTHORITIES",
    "SOURCE_FRONTIER_MEMBERS",
    "ActiveLearningFrontier",
    "ExcludedCandidate",
    "FrontierCandidatePort",
    "FrontierMember",
    "FrontierMemberEntry",
    "FrontierMembership",
    "frontier_members_of_origins",
    "frontier_of",
]


class FrontierMember(StrEnum):
    """docs/DOMAIN_MODEL.md's ``ActiveLearningFrontier`` block, line for line.

    The seven values are the fenced block's own words with the ``∪`` list
    marker dropped and nothing else changed, in the document's order, so the
    enum and the canonical block can be compared character for character (this
    cut's suite does exactly that). Revisit: the block is edited — a member
    added, renamed, reordered or dropped — or a canonical document lists the
    union's members in a second place.
    """

    CURRICULUM_CANDIDATES = "curriculum candidates"
    SCHEDULED_REVIEW = "scheduled review"
    CONFIRMED_GAPS = "confirmed gaps"
    UNKNOWN_PROBES = "unknown probes"
    TRANSFER_OPPORTUNITIES = "transfer opportunities"
    PERSONAL_EXPRESSION_NEEDS = "personal expression needs"
    CURRENT_CONTEXT_OPPORTUNITIES = "current context opportunities"


#: The union in the document's order — the order members are emitted in, so two
#: origin orders produce one membership tuple and a record cannot depend on the
#: order the generators happened to run in.
FRONTIER_MEMBERS: tuple[FrontierMember, ...] = tuple(FrontierMember)


@dataclass(frozen=True)
class FrontierMembership:
    """One §6 source word's place in the union, and the reason for it.

    ``basis`` is mandatory: it says *why* these members and not others, quoting
    the frozen precedent where the pairing is quotation (a source whose name is
    a member's name; a golden scenario's own origin) and saying "declared"
    where it is this cut's reading. The table-level
    :data:`FRONTIER_MAPPING_REVISIT` is the one condition that re-opens every
    row, because every row is re-read at once when the two canonical lists move.
    """

    source: str
    members: tuple[FrontierMember, ...]
    basis: str


#: The fourteen rows, in §6's order (docs/PRODUCT_CONTRACT.md: Track A's six
#: then Track B's eight — the order P7-2's ``CANDIDATE_SOURCES`` emits in).
#: **This is the declared reading**, with the reason on every row; the suite
#: checks that the table is total over the source vocabulary, that every member
#: has at least one mapper, and that every value is one of the seven block
#: words. A basis is written from the *origin's own semantics* rather than from
#: a factor band, which is what makes "an origin belongs to a family" a claim
#: about the source and not a second pricing of it.
SOURCE_FRONTIER_MEMBERS: Mapping[str, FrontierMembership] = {
    # -- Track A — expression-driven ---------------------------------------
    "CURRENT_USER_ERROR": FrontierMembership(
        source="CURRENT_USER_ERROR",
        members=(FrontierMember.PERSONAL_EXPRESSION_NEEDS,),
        basis=(
            "declared: the source prices the user's own expression"
            " (personal_relevance at the ladder's CURRENT_EXPRESSION band,"
            " context_fit DIRECT, expiry THIS_TURN — P7-2's own row), so the"
            " opportunity it describes is a need *inside what the user was"
            " saying*. It is not also a 'current context opportunity': the"
            " context fit is a pricing of the same turn, and membership is read"
            " from the origin's semantics rather than from a factor band"
        ),
    ),
    "EXPRESSION_NEED": FrontierMembership(
        source="EXPRESSION_NEED",
        members=(FrontierMember.PERSONAL_EXPRESSION_NEEDS,),
        basis=(
            "quoted on the record and declared on the pairing:"
            " docs/DATA_MODEL.md's ExpressionNeed is 'Personal Expression"
            " Frontier' material (its own line, next to the record's columns),"
            " and the source's shape is a user who needed a form they did not"
            " have. The members word is the same phrase in both documents"
        ),
    ),
    "NATURAL_USE_EXPANSION": FrontierMembership(
        source="NATURAL_USE_EXPANSION",
        members=(
            FrontierMember.PERSONAL_EXPRESSION_NEEDS,
            FrontierMember.CURRENT_CONTEXT_OPPORTUNITIES,
        ),
        basis=(
            "declared, two members: the user already reached for the form — an"
            " expression fact — *and* the opportunity is the moment they used"
            " it — a context fact. The source's own pricing says both"
            " (context_fit HIGH with expiry SESSION, next to EXPAND_REPERTOIRE)"
        ),
    ),
    "PRAGMATIC_REGISTER_OPPORTUNITY": FrontierMembership(
        source="PRAGMATIC_REGISTER_OPPORTUNITY",
        members=(FrontierMember.CURRENT_CONTEXT_OPPORTUNITIES,),
        basis=(
            "declared: what the current context admits is the whole source, and"
            " GS01's own candidate — 'natural chat with no worthwhile"
            " teaching', expected outcome NO_TARGET — is this origin. The"
            " opportunity exists in the context and is not worth teaching,"
            " which is exactly why membership is not a filter"
        ),
    ),
    "MANUAL_USER_REQUEST": FrontierMembership(
        source="MANUAL_USER_REQUEST",
        members=(FrontierMember.PERSONAL_EXPRESSION_NEEDS,),
        basis=(
            "declared: this word is §9's MANUAL_FOCUS — the user's own durable"
            " act of asking for a target — which is the strongest expression"
            " need in the vocabulary and the only *user-initiated* one"
        ),
    ),
    "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY": FrontierMembership(
        source="CURRENT_CONTEXT_TRANSFER_OPPORTUNITY",
        members=(
            FrontierMember.TRANSFER_OPPORTUNITIES,
            FrontierMember.CURRENT_CONTEXT_OPPORTUNITIES,
        ),
        basis=(
            "declared: the name is the reading — CURRENT + CONTEXT + TRANSFER"
            " — so the opportunity belongs to the transfer family and to the"
            " moment it occurs in. §11's TRANSFER mode pairs with TRANSFER"
            " intent, which is the same two facts one layer down"
        ),
    ),
    # -- Track B — curriculum-driven ---------------------------------------
    "CONFIRMED_GAP": FrontierMembership(
        source="CONFIRMED_GAP",
        members=(FrontierMember.CONFIRMED_GAPS,),
        basis=(
            "quoted: the source word carries the member's word, and the source"
            " reads BF-01 §25's CONFIRMED_GAP flag — the estimator's own"
            " statement that this is a gap"
        ),
    ),
    "SCHEDULED_REVIEW": FrontierMembership(
        source="SCHEDULED_REVIEW",
        members=(FrontierMember.SCHEDULED_REVIEW,),
        basis=(
            "quoted: the source word is the member's word; the source reads the"
            " Scheduler's own due decision, which is what 'scheduled' means"
        ),
    ),
    "UNKNOWN_PROBE": FrontierMembership(
        source="UNKNOWN_PROBE",
        members=(FrontierMember.UNKNOWN_PROBES,),
        basis=(
            "quoted: the source word is the member's word; a probe exists to"
            " reduce uncertainty about a target the learner state does not"
            " describe, which is the member's own 'unknown'"
        ),
    ),
    "TRANSFER_EXPANSION": FrontierMembership(
        source="TRANSFER_EXPANSION",
        members=(FrontierMember.TRANSFER_OPPORTUNITIES,),
        basis=(
            "quoted: the source word carries the member's word, and D-INV-010"
            " gives the Planner the transfer decision this source would read"
            " (its policy is not landed; the membership is unaffected)"
        ),
    ),
    "SUPPORT_WITHDRAWAL": FrontierMembership(
        source="SUPPORT_WITHDRAWAL",
        members=(FrontierMember.CURRICULUM_CANDIDATES,),
        basis=(
            "declared: the target is an authored curriculum entity whose"
            " support is being withdrawn (BF-01 §25's SUPPORT_DEPENDENT beside"
            " §11's WITHDRAW_SUPPORT), so the candidate is the curriculum's own"
            " target one stage further along rather than a new expression need"
        ),
    ),
    "CORE_COVERAGE": FrontierMembership(
        source="CORE_COVERAGE",
        members=(FrontierMember.CURRICULUM_CANDIDATES,),
        basis=(
            "declared on §7's own ownership: the core tier is Curriculum's, so"
            " an uncovered core target is a curriculum candidate by"
            " construction (the tier is not published, which is the source's"
            " own registered gap and not a membership question)"
        ),
    ),
    "GOAL_SPECIFIC_TARGET": FrontierMembership(
        source="GOAL_SPECIFIC_TARGET",
        members=(FrontierMember.CURRICULUM_CANDIDATES,),
        basis=(
            "declared: the source turns a goal into a curriculum target through"
            " the Goal/Assessment pack mapping, so what it proposes is a"
            " curriculum candidate — IMPLEMENTATION_PLAN §7's mapping is not"
            " built, and the membership does not depend on its landing"
        ),
    ),
    "COVERAGE_DEBT": FrontierMembership(
        source="COVERAGE_DEBT",
        members=(FrontierMember.CURRICULUM_CANDIDATES,),
        basis=(
            "declared on §6's own line ('长期什么不能一直没学') and BF-02 §13's"
            " safeguard: a coverage obligation is a long-run curriculum"
            " statement — which target must not stay uncovered — so the"
            " candidate that pays it is a curriculum candidate. Its pricing"
            " additionally reads the PlanningLedger (elc.planner.ledger), which"
            " is an authority reading and not a family"
        ),
    ),
}

#: The one condition that re-opens every row above: the two canonical lists
#: moving, or a canonical document pairing them.
FRONTIER_MAPPING_REVISIT = (
    "canonical text maps §6's fourteen source words onto the union's members"
    " (then the pairing is quoted rather than declared), a source word or a"
    " union member is added/renamed/dropped, or a cut lands an origin whose"
    " semantics the table's basis does not cover — the row is then re-read"
    " against the origin's own wording rather than against this table"
)

#: The two names in DOMAIN_MODEL's closing line that could be read as asking
#: for a *filter*, with the authority each would need. Nothing in this module
#: reads this map: an entry is a registration, and a registration is not a
#: predicate (module docstring).
MISSING_FRONTIER_AUTHORITIES: Mapping[str, str] = {
    "user constraints": (
        "read, not a frontier filter: §9's constraint view is what the supply"
        " side marks suppression and resolves the §12 scope word from (P7-2),"
        " and both travel to the kernel's step 4, which is where this"
        " document's 'eligibility' is decided. A second constraint filter here"
        " would decide the same fact twice. Revisit: canonical text says the"
        " frontier applies a user-constraint filter *besides* hard eligibility"
        " — then the filter is a step-4 rule and moves to the kernel, not here"
    ),
    "cognitive feasibility": (
        "no authority in Phase 7: DOMAIN_MODEL §10's input block names"
        " SessionBudgetView for a session's budget and P6-1 registered that"
        " view to Phase 8 (its input is BF-03 §17's runtime session state,"
        " which no cut produces) — so 'cognitive feasibility' has no number to"
        " read and none is invented here. The candidate-side cognitive cost is"
        " BF-02 §6's cognitive_load factor, which the generator prices and the"
        " kernel weighs; a *feasibility* cap on how much a session may hold"
        " needs the view above. Revisit: SessionBudgetView lands (or a cut"
        " lands any session-scope feasibility reading) — then the frontier"
        " question is re-asked with an authority behind it"
    ),
}


class FrontierCandidatePort(Protocol):
    """The three fields this module reads off a canonical candidate.

    Declared narrowly on purpose: the frontier is a function of *identity and
    origin*, and a port that named a factor would invite this module to price
    one. Satisfied structurally by
    :class:`~elc.planner.kernel.CanonicalCandidate`, which is why the kernel can
    build its evaluation's frontier column without an adapter — and why this
    module imports no kernel type, so the dependency runs one way only.

    The three members are read-only properties rather than plain attributes
    because the record that satisfies them is a **frozen** dataclass: a
    writable-attribute protocol is only satisfied by a settable attribute, and
    this module never writes a candidate.
    """

    @property
    def candidate_id(self) -> str: ...

    @property
    def focus_target(self) -> str: ...

    @property
    def origins(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class FrontierMemberEntry:
    """One frontier member: the candidate, and the union families it came from.

    ``members`` is in :data:`FRONTIER_MEMBERS` order and is deduplicated, so a
    candidate that reached the frontier through two sources of one family
    carries that family once. ``unmapped_origins`` lists the origin words the
    table does not carry (sorted, so the record is order-free) — a hand-built
    proposal's empty origins land there as an empty tuple, and a word the table
    has not met lands there as itself rather than being dropped or guessed at.
    """

    candidate_id: str
    focus_target: str
    origins: tuple[str, ...]
    members: tuple[FrontierMember, ...]
    unmapped_origins: tuple[str, ...]


@dataclass(frozen=True)
class ExcludedCandidate:
    """One candidate hard eligibility removed — not a frontier member.

    ``exclusion`` is the kernel's own exclusion word, carried as a string so
    this module names no kernel enum: the frontier records *that* a candidate
    left and *why*, and the vocabulary of "why" is step 4's.
    """

    candidate_id: str
    exclusion: str


@dataclass(frozen=True)
class ActiveLearningFrontier:
    """The eligible set: the step-4 survivors, and the exclusions beside them.

    ``members`` are the candidates that passed hard eligibility, ``excluded``
    are the ones it removed. **What this constructor guarantees is that the two
    halves are disjoint** — an id may not appear on both sides, checked here and
    refused with ``ValueError`` — and disjointness is exactly the invariant that
    makes the frontier a *view* rather than a second filter.

    **Coverage is :func:`frontier_of`'s property, not this constructor's.** That
    ``members`` and ``excluded`` together hold every canonical candidate the run
    was given is established by that walk over the candidate set (which is also
    where a stray exclusion id is refused), not by ``__post_init__``: a frontier
    built by hand is accepted here even when it names only part of a candidate
    set, so a frontier that dropped a candidate quietly is a frontier that did
    not come through :func:`frontier_of`. Disjointness is the only claim this
    class makes on its own; coverage is the walk's, and the walk is where a
    consumer who needs it must get its frontier from.
    """

    members: tuple[FrontierMemberEntry, ...]
    excluded: tuple[ExcludedCandidate, ...]

    def __post_init__(self) -> None:
        overlap = {
            entry.candidate_id for entry in self.members
        } & {entry.candidate_id for entry in self.excluded}
        if overlap:
            raise ValueError(
                "a candidate cannot be both a frontier member and excluded"
                f" from it: {sorted(overlap)}"
            )

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        """The member ids — docs/DATA_MODEL.md §14's ``frontier_candidate_ids[]``."""

        return tuple(entry.candidate_id for entry in self.members)

    @property
    def excluded_ids(self) -> tuple[str, ...]:
        """The ids hard eligibility removed, in the kernel's canonical order."""

        return tuple(entry.candidate_id for entry in self.excluded)

    def members_of(self, candidate_id: str) -> tuple[FrontierMember, ...]:
        """The union families one member came from (empty for a member with no
        §6 origin word, which is a member all the same)."""

        for entry in self.members:
            if entry.candidate_id == candidate_id:
                return entry.members
        raise KeyError(f"{candidate_id} is not a frontier member")

    def entry_of(self, candidate_id: str) -> FrontierMemberEntry:
        """The whole membership record for one member."""

        for entry in self.members:
            if entry.candidate_id == candidate_id:
                return entry
        raise KeyError(f"{candidate_id} is not a frontier member")


def frontier_members_of_origins(
    origins: Sequence[str],
) -> tuple[tuple[FrontierMember, ...], tuple[str, ...]]:
    """The union families a set of origin words names, and the words it cannot.

    Returns the members in :data:`FRONTIER_MEMBERS` order (deduplicated) and the
    origin words :data:`SOURCE_FRONTIER_MEMBERS` does not carry (deduplicated
    and sorted). An unknown word is *reported*, never mapped by guess and never
    dropped: the second tuple is what makes "the table met a word it has no row
    for" visible in the record.
    """

    member_set: set[FrontierMember] = set()
    unmapped: set[str] = set()
    for origin in origins:
        membership = SOURCE_FRONTIER_MEMBERS.get(origin)
        if membership is None:
            unmapped.add(origin)
        else:
            member_set.update(membership.members)
    members = tuple(
        member for member in FRONTIER_MEMBERS if member in member_set
    )
    return members, tuple(sorted(unmapped))


def frontier_of(
    candidates: Sequence[FrontierCandidatePort],
    exclusions: Mapping[str, str],
) -> ActiveLearningFrontier:
    """The frontier of one run: survivors as members, exclusions beside them.

    ``exclusions`` maps a candidate id to the word step 4 removed it with. The
    walk is over ``candidates`` — the canonical set, in the kernel's canonical
    order — so both halves are ordered by the candidates' own order and a run's
    frontier is a function of that run's data alone. A candidate whose id is
    not in ``exclusions`` is a member; a member's membership tuple is read from
    its origin words (see :func:`frontier_members_of_origins`).

    Raises :class:`ValueError` when ``exclusions`` names an id the candidate set
    does not carry: that is a caller's bookkeeping error, and answering it
    silently would make the two halves fail to cover the canonical set.
    """

    ids = {candidate.candidate_id for candidate in candidates}
    strays = sorted(set(exclusions) - ids)
    if strays:
        raise ValueError(
            "exclusions name candidate ids the candidate set does not carry:"
            f" {strays}"
        )
    members: list[FrontierMemberEntry] = []
    excluded: list[ExcludedCandidate] = []
    for candidate in candidates:
        reason = exclusions.get(candidate.candidate_id)
        if reason is not None:
            excluded.append(
                ExcludedCandidate(
                    candidate_id=candidate.candidate_id,
                    exclusion=str(reason),
                )
            )
            continue
        member_set, unmapped = frontier_members_of_origins(candidate.origins)
        members.append(
            FrontierMemberEntry(
                candidate_id=candidate.candidate_id,
                focus_target=candidate.focus_target,
                origins=tuple(candidate.origins),
                members=member_set,
                unmapped_origins=unmapped,
            )
        )
    return ActiveLearningFrontier(
        members=tuple(members), excluded=tuple(excluded)
    )
