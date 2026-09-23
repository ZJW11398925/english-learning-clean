"""P7-3 ①④ — the frontier, its seven members, and the column it fills.

Three things are pinned here and they are one reading each:

- the **seven member words** are docs/DOMAIN_MODEL.md's ``ActiveLearningFrontier``
  block line for line, and the fourteen §6 source words are mapped onto them by
  one declared table whose every row carries its reason (no canonical document
  pairs the two lists);
- the **position** is §19's, the **members** are hard eligibility's survivors,
  and neither is a twelfth step: §10.1's ``KernelStep`` values are re-read
  against their own canonical block here, unchanged;
- the **column** docs/DATA_MODEL.md §14 names (``frontier_candidate_ids[]``) is
  filled by the kernel from that very set, so the record and the definition
  cannot drift.
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

from elc.planner.candidates import CANDIDATE_SOURCES
from elc.planner.frontier import (
    FRONTIER_MAPPING_REVISIT,
    FRONTIER_MEMBERS,
    MISSING_FRONTIER_AUTHORITIES,
    SOURCE_FRONTIER_MEMBERS,
    ActiveLearningFrontier,
    ExcludedCandidate,
    FrontierMember,
    FrontierMemberEntry,
    frontier_members_of_origins,
    frontier_of,
)
from elc.planner.kernel import (
    KERNEL_STEP_ORDER,
    ExclusionReason,
    KernelStep,
    PlannerExecutionStatusValue,
    canonicalize_proposals,
    plan,
)
from elc.planner.types import PlannerDecisionOutcome, PlannerEvaluation
from elc.platform.types import (
    DecisionCycleId,
    PlannerEvaluationId,
    PlannerVersion,
    PolicyVersion,
)

from .conftest import (
    DOCS_ROOT,
    canonical_lines,
    kernel_input,
    proposal,
    source_text,
)

DOMAIN_MODEL = "DOMAIN_MODEL.md"
STATE_MACHINES = "STATE_MACHINES.md"
DATA_MODEL = "DATA_MODEL.md"

SECTION_10_1 = "## 10.1 Planner Decision Kernel — Behavioral Baseline V1"
SECTION_19 = "## 19. Planner Flow State"
FRONTIER_SECTION = "### ActiveLearningFrontier"
EVALUATION_SECTION = "### PlannerEvaluation"


# ---------------------------------------------------------------------------
# ① the union, verbatim, and the declared mapping onto §6's sources
# ---------------------------------------------------------------------------


def test_the_seven_member_words_are_the_canonical_union_block() -> None:
    """The enum and the document, character for character: the block's seven
    lines with the ``∪`` list marker dropped are the seven member values, in
    the document's order."""

    lines = list(canonical_lines(DOMAIN_MODEL, FRONTIER_SECTION))
    assert len(lines) == 7
    canonical = [line.removeprefix("∪ ") for line in lines]
    assert canonical == [member.value for member in FRONTIER_MEMBERS]
    assert FRONTIER_MEMBERS == tuple(FrontierMember)


def test_the_frontier_s_section_says_the_union_is_what_eligibility_left() -> None:
    """The section's own closing line is the whole reading — the union is what
    "经过 eligibility … 后" leaves standing — which is why this cut filters
    nothing and why an excluded candidate is not a member."""

    text = (DOCS_ROOT / DOMAIN_MODEL).read_text(encoding="utf-8")
    assert "经过 eligibility/prerequisite/content readiness" in text
    assert "后形成 Frontier。" in text


def test_the_fourteen_source_words_are_mapped_and_only_those() -> None:
    """The table is total over §6's vocabulary — the same fourteen words P7-2
    declared — and carries no row for a word §6 does not have."""

    assert set(SOURCE_FRONTIER_MEMBERS) == set(CANDIDATE_SOURCES)
    assert len(SOURCE_FRONTIER_MEMBERS) == 14
    for source, membership in SOURCE_FRONTIER_MEMBERS.items():
        assert membership.source == source
        assert membership.members, source
        assert set(membership.members) <= set(FrontierMember), source


def test_every_member_has_at_least_one_mapper() -> None:
    """No member of the union is left without a row naming it, so "which
    sources make this member" is always answerable."""

    mapped = {
        member
        for membership in SOURCE_FRONTIER_MEMBERS.values()
        for member in membership.members
    }
    assert mapped == set(FRONTIER_MEMBERS)
    for member in FRONTIER_MEMBERS:
        sources = [
            source
            for source, membership in SOURCE_FRONTIER_MEMBERS.items()
            if member in membership.members
        ]
        assert sources, member


def test_every_row_says_whether_it_quotes_or_declares() -> None:
    """A pairing with no canonical table behind it has to say so: every row's
    basis names which of the two it is, and the table-level revisit names the
    condition that re-opens all fourteen at once."""

    for source, membership in SOURCE_FRONTIER_MEMBERS.items():
        assert "declared" in membership.basis or "quoted" in membership.basis, (
            source
        )
        assert len(membership.basis) > 40, source
    assert "canonical text maps" in FRONTIER_MAPPING_REVISIT
    assert "source word" in FRONTIER_MAPPING_REVISIT


def test_the_rows_that_claim_a_quotation_are_the_five_that_can() -> None:
    """Which rows lean on a document rather than on this cut's reading — and
    which therefore move if that document moves: the source words that read a
    named canonical artifact (the §11 intent of a probe, BF-01 §25's two flags,
    the Scheduler's own due decision, D-INV-010's transfer item, and
    DATA_MODEL §10's ExpressionNeed). Everything else is declared."""

    quoted = {
        source
        for source, membership in SOURCE_FRONTIER_MEMBERS.items()
        if "quoted" in membership.basis
    }
    assert quoted == {
        "EXPRESSION_NEED",
        "CONFIRMED_GAP",
        "SCHEDULED_REVIEW",
        "UNKNOWN_PROBE",
        "TRANSFER_EXPANSION",
    }
    for source in set(SOURCE_FRONTIER_MEMBERS) - quoted:
        assert "declared" in SOURCE_FRONTIER_MEMBERS[source].basis, source


def test_the_two_two_family_sources_are_the_ones_that_say_so() -> None:
    """Two Track A sources belong to two families and say so; every other row
    names one — the shape that keeps "which member" a reading rather than a
    guess."""

    two = {
        source: membership.members
        for source, membership in SOURCE_FRONTIER_MEMBERS.items()
        if len(membership.members) > 1
    }
    assert set(two) == {
        "NATURAL_USE_EXPANSION",
        "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY",
    }
    assert FrontierMember.TRANSFER_OPPORTUNITIES in two[
        "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY"
    ]
    assert FrontierMember.PERSONAL_EXPRESSION_NEEDS in two[
        "NATURAL_USE_EXPANSION"
    ]


# ---------------------------------------------------------------------------
# ④ the two registered gates, and the "no new filter" rule
# ---------------------------------------------------------------------------


def test_the_two_unlanded_gates_are_registered_and_not_applied() -> None:
    """``user constraints`` and ``cognitive feasibility`` are names in the
    document's closing line, and neither is a predicate here: both are
    registered with the authority that would have to answer them, each says
    what re-opens it, and the module's *code* never reads the table."""

    assert set(MISSING_FRONTIER_AUTHORITIES) == {
        "user constraints",
        "cognitive feasibility",
    }
    for name, reason in MISSING_FRONTIER_AUTHORITIES.items():
        assert "Revisit:" in reason, name
        assert len(reason) > 80, name
    assert "SessionBudgetView" in MISSING_FRONTIER_AUTHORITIES[
        "cognitive feasibility"
    ]
    assert "step 4" in MISSING_FRONTIER_AUTHORITIES["user constraints"]

    tree = ast.parse(source_text("src/elc/planner/frontier.py"))
    loads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id == "MISSING_FRONTIER_AUTHORITIES"
        and isinstance(node.ctx, ast.Load)
    ]
    assert loads == [], [node.lineno for node in loads]


def test_the_frontier_module_imports_no_kernel_type_and_no_store() -> None:
    """The dependency runs one way: the kernel imports the frontier and the
    frontier imports no ``elc`` module at all (its port is structural), no
    store, no DB module and no clock."""

    tree = ast.parse(source_text("src/elc/planner/frontier.py"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert not any(module.startswith("elc") for module in modules), modules
    assert "sqlite3" not in modules
    for forbidden in ("datetime", "time", "random", "uuid", "os"):
        assert forbidden not in {module.split(".")[0] for module in modules}


def test_the_resolution_is_written_where_the_divergence_was_registered() -> None:
    """P7-2 registered the §19/§10.1 difference and handed it here; the
    registration is kept *and* the resolution is stated, so a reader of either
    file learns that the question is settled."""

    from elc.planner import candidates as supply_module

    prose = " ".join((supply_module.__doc__ or "").split())
    assert "ActiveLearningFrontier" in prose
    assert "registered, not resolved" in prose
    assert "P7-3 has since made it" in prose
    frontier_prose = " ".join(
        (
            ast.get_docstring(ast.parse(source_text("src/elc/planner/frontier.py")))
            or ""
        ).split()
    )
    assert "position: after hard eligibility, before Policy Utility" in (
        frontier_prose
    )
    assert "excluded candidate is **not** a frontier member" in frontier_prose


def test_section_nineteen_still_puts_the_frontier_between_the_two_steps() -> None:
    """The position, read off the two canonical blocks rather than asserted:
    the line before the frontier is hard eligibility's, the line after it is
    Policy Utility's, and §10.1's own block still has no frontier line."""

    flow = list(canonical_lines(STATE_MACHINES, SECTION_19))
    at = flow.index("→ ActiveLearningFrontier")
    assert "hard eligibility" in flow[at - 1]
    assert flow[at + 1] == "→ Policy Utility"
    kernel_order = list(canonical_lines(DOMAIN_MODEL, SECTION_10_1))
    assert not any("ActiveLearningFrontier" in line for line in kernel_order)


# ---------------------------------------------------------------------------
# ④ the membership reading, and the candidates it must not touch
# ---------------------------------------------------------------------------


def test_the_members_are_the_step_four_survivors() -> None:
    """The one rule: a survivor is a member, an excluded candidate is not, and
    the two halves together hold the canonical set."""

    candidates = canonicalize_proposals(
        (
            proposal("c-a", origins=("EXPRESSION_NEED",)),
            proposal("c-b", canonical_key="c-b", origins=("SCHEDULED_REVIEW",)),
            proposal("c-c", canonical_key="c-c", origins=("COVERAGE_DEBT",)),
        )
    )
    frontier = frontier_of(candidates, {"c-c": ExclusionReason.EXPIRED.value})
    assert frontier.candidate_ids == ("c-a", "c-b")
    assert frontier.excluded_ids == ("c-c",)
    assert frontier.members_of("c-a") == (FrontierMember.PERSONAL_EXPRESSION_NEEDS,)
    assert frontier.members_of("c-b") == (FrontierMember.SCHEDULED_REVIEW,)
    with pytest.raises(KeyError):
        frontier.members_of("c-c")
    assert {candidate.candidate_id for candidate in candidates} == (
        set(frontier.candidate_ids) | set(frontier.excluded_ids)
    )


def test_an_excluded_candidate_carries_its_reason_and_no_membership() -> None:
    """The excluded half is a record of *why*, so the frontier answers "why not
    that one" without re-running step 4."""

    candidates = canonicalize_proposals((proposal("c-a", suppressed=True),))
    frontier = frontier_of(candidates, {"c-a": ExclusionReason.SUPPRESSED.value})
    assert frontier.members == ()
    assert frontier.excluded == (
        ExcludedCandidate(
            candidate_id="c-a", exclusion=ExclusionReason.SUPPRESSED.value
        ),
    )


def test_a_candidate_cannot_be_a_member_and_excluded_at_once() -> None:
    entry = FrontierMemberEntry(
        candidate_id="c-a",
        focus_target="res-hedge-i-think",
        origins=("EXPRESSION_NEED",),
        members=(FrontierMember.PERSONAL_EXPRESSION_NEEDS,),
        unmapped_origins=(),
    )
    with pytest.raises(ValueError) as raised:
        ActiveLearningFrontier(
            members=(entry,),
            excluded=(ExcludedCandidate(candidate_id="c-a", exclusion="EXPIRED"),),
        )
    assert "both a frontier member and excluded" in str(raised.value)


def test_an_exclusion_for_a_candidate_outside_the_set_is_refused() -> None:
    candidates = canonicalize_proposals((proposal("c-a"),))
    with pytest.raises(ValueError) as raised:
        frontier_of(candidates, {"c-elsewhere": "EXPIRED"})
    assert "c-elsewhere" in str(raised.value)


def test_a_member_with_no_origin_is_still_a_member() -> None:
    """BF-02 §20's frozen suite hands complete vectors and no generator labels,
    and a caller may build a proposal by hand: an empty origin tuple is an
    empty membership and never a reason to leave the frontier."""

    candidates = canonicalize_proposals((proposal("c-a", origins=()),))
    frontier = frontier_of(candidates, {})
    assert frontier.candidate_ids == ("c-a",)
    assert frontier.members_of("c-a") == ()
    entry = frontier.entry_of("c-a")
    assert entry.origins == ()
    assert entry.unmapped_origins == ()


def test_an_origin_the_table_does_not_carry_is_reported_not_dropped() -> None:
    members, unmapped = frontier_members_of_origins(
        ("NOT_A_SOURCE_WORD", "EXPRESSION_NEED", "ANOTHER_UNKNOWN")
    )
    assert members == (FrontierMember.PERSONAL_EXPRESSION_NEEDS,)
    assert unmapped == ("ANOTHER_UNKNOWN", "NOT_A_SOURCE_WORD")


def test_the_membership_order_is_the_document_s_order_not_the_origins() -> None:
    """Two arrival orders, one membership tuple — the record cannot depend on
    which source ran first."""

    forward, _ = frontier_members_of_origins(
        ("PRAGMATIC_REGISTER_OPPORTUNITY", "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY")
    )
    backward, _ = frontier_members_of_origins(
        ("CURRENT_CONTEXT_TRANSFER_OPPORTUNITY", "PRAGMATIC_REGISTER_OPPORTUNITY")
    )
    assert forward == backward == (
        FrontierMember.TRANSFER_OPPORTUNITIES,
        FrontierMember.CURRENT_CONTEXT_OPPORTUNITIES,
    )


def test_two_sources_of_one_family_name_that_family_once() -> None:
    members, unmapped = frontier_members_of_origins(
        ("EXPRESSION_NEED", "CURRENT_USER_ERROR", "MANUAL_USER_REQUEST")
    )
    assert members == (FrontierMember.PERSONAL_EXPRESSION_NEEDS,)
    assert unmapped == ()


# ---------------------------------------------------------------------------
# ④ the column: appended, defaulted, and filled from the survivors
# ---------------------------------------------------------------------------


def test_the_column_is_appended_and_defaulted() -> None:
    """docs/DATA_MODEL.md §14 lists ``frontier_candidate_ids[]`` third; this cut
    appends it last so no existing field or construction moves, and the
    document's own order is pinned beside it."""

    names = [entry.name for entry in dataclasses.fields(PlannerEvaluation)]
    assert names[-1] == "frontier_candidate_ids"
    assert names[:6] == [
        "planner_evaluation_id",
        "decision_cycle_id",
        "planner_version",
        "policy_version",
        "ranked_candidates",
        "reason_trace",
    ]
    section = list(canonical_lines(DATA_MODEL, EVALUATION_SECTION))
    assert section[:3] == [
        "planner_evaluation_id",
        "decision_cycle_id",
        "frontier_candidate_ids[]",
    ]
    built = PlannerEvaluation(
        planner_evaluation_id=PlannerEvaluationId("pe-x"),
        decision_cycle_id=DecisionCycleId("dc-x"),
        planner_version=PlannerVersion("pk1"),
        policy_version=PolicyVersion("planner-v1.1-reference-2026-09-stress-tested"),
        ranked_candidates=(),
        reason_trace=(),
    )
    assert built.frontier_candidate_ids == ()


def test_the_kernel_step_values_are_untouched() -> None:
    """The frontier is not a twelfth step: §10.1's eleven lines are the eleven
    values, in order, and no value mentions the frontier."""

    order = [step.value for step in KERNEL_STEP_ORDER]
    assert len(order) == 11
    assert not any("Frontier" in value for value in order)
    assert KernelStep.HARD_ELIGIBILITY.value == "hard eligibility"
    assert KernelStep.POLICY_UTILITY.value == "policy utility"


def test_the_kernel_fills_the_column_from_the_survivors() -> None:
    """One run, three candidates, one exclusion: the column is exactly the
    survivors, in canonical order, and a frontier built by hand from the same
    canonical set agrees with it value for value."""

    alive = proposal("c-alive")
    other = proposal("c-other", canonical_key="c-other")
    gone = proposal("c-gone", canonical_key="c-gone", expired=True)
    result = plan(kernel_input((alive, other, gone)))
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.SUCCEEDED
    )
    assert result.outcome.evaluation.frontier_candidate_ids == (
        "c-alive",
        "c-other",
    )
    canonical = canonicalize_proposals((alive, other, gone))
    by_hand = frontier_of(canonical, {"c-gone": ExclusionReason.EXPIRED.value})
    assert by_hand.candidate_ids == (
        result.outcome.evaluation.frontier_candidate_ids
    )
    rows = {row.candidate_id: row for row in result.trace.candidates}
    assert rows["c-gone"].excluded is ExclusionReason.EXPIRED
    assert set(rows) == set(result.outcome.evaluation.frontier_candidate_ids) | {
        "c-gone"
    }


def test_a_run_whose_candidates_have_no_origin_words_still_has_a_frontier() -> None:
    """The membership of each member is empty and the ids are still the
    survivors: membership is a label read, never a condition."""

    pair = (proposal("c-a"), proposal("c-b", canonical_key="c-b"))
    result = plan(kernel_input(pair))
    assert result.outcome.evaluation.frontier_candidate_ids == ("c-a", "c-b")
    frontier = frontier_of(canonicalize_proposals(pair), {})
    assert [entry.members for entry in frontier.members] == [(), ()]


def test_a_degraded_run_carries_no_frontier_and_stops_before_step_four() -> None:
    """``()`` here is "no set survived a step that never ran", not an empty
    eligible set: the run stopped at step 3, and the trace's step prefix says
    so."""

    result = plan(kernel_input((proposal("c1"),), context=None))
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.UNAVAILABLE
    )
    assert result.outcome.evaluation.frontier_candidate_ids == ()
    assert result.trace.steps == KERNEL_STEP_ORDER[:3]
    assert KernelStep.HARD_ELIGIBILITY not in result.trace.steps


def test_a_run_that_excludes_everything_has_an_empty_frontier_and_a_decision() -> None:
    """The other empty: step 4 kept nothing, the frontier is empty, and the
    decision is still a decision (NO_TARGET)."""

    result = plan(kernel_input((proposal("c1", expired=True),)))
    assert result.outcome.evaluation.frontier_candidate_ids == ()
    assert result.trace.decision is PlannerDecisionOutcome.NO_TARGET
    assert result.outcome.decision is not None


def test_the_exclusions_in_the_trace_rebuild_the_frontier_s_other_half() -> None:
    """The kernel-side change is one column: the trace still carries the
    exclusion words, and the frontier's excluded half is derivable from them —
    which is what makes the column checkable rather than trusted."""

    pair = (
        proposal("c-alive"),
        proposal("c-gone", canonical_key="c-gone", expired=True),
    )
    result = plan(kernel_input(pair))
    rows = {row.candidate_id: row for row in result.trace.candidates}
    frontier = frontier_of(
        canonicalize_proposals(pair),
        {
            candidate_id: row.excluded.value
            for candidate_id, row in rows.items()
            if row.excluded is not None
        },
    )
    assert frontier.excluded_ids == ("c-gone",)
    assert frontier.candidate_ids == (
        result.outcome.evaluation.frontier_candidate_ids
    )


def test_judgement_twelve_records_the_column_as_landed() -> None:
    """kernel.py's own registration of the evaluation record's shape names the
    column as landed rather than as missing."""

    docstring = ast.get_docstring(
        ast.parse(source_text("src/elc/planner/kernel.py"))
    )
    assert docstring is not None
    assert "p7-3 appended" in docstring
    assert "frontier_candidate_ids" in docstring
    assert "elc.planner.frontier" in docstring


# ---------------------------------------------------------------------------
# ④ the two halves: coverage is the walk's, disjointness is the class's
# ---------------------------------------------------------------------------


def test_frontier_of_covers_every_candidate_it_was_given() -> None:
    """The true contract of the two halves, checked on the walk that
    establishes it: for any candidate set the survivors and the exclusions are
    disjoint and together hold exactly that set — including the two degenerate
    inputs (nothing excluded, everything excluded), where a dropped candidate
    would leave no trace in either id tuple."""

    cases = (
        ((), {}),
        ((proposal("c-a"),), {}),
        ((proposal("c-a"),), {"c-a": ExclusionReason.EXPIRED.value}),
        (
            (
                proposal("c-a"),
                proposal("c-b", canonical_key="c-b", suppressed=True),
                proposal("c-c", canonical_key="c-c", expired=True),
            ),
            {
                "c-b": ExclusionReason.SUPPRESSED.value,
                "c-c": ExclusionReason.EXPIRED.value,
            },
        ),
    )
    for specs, exclusions in cases:
        candidates = canonicalize_proposals(specs)
        frontier = frontier_of(candidates, exclusions)
        full = {candidate.candidate_id for candidate in candidates}
        assert set(frontier.candidate_ids) | set(
            frontier.excluded_ids
        ) == full
        assert not set(frontier.candidate_ids) & set(frontier.excluded_ids)
        assert len(frontier.candidate_ids) + len(frontier.excluded_ids) == len(
            full
        )


def test_the_class_guarantees_disjointness_and_not_coverage() -> None:
    """The other half of the contract, as the class's own: a hand-built
    frontier is accepted with no members and with a single member even though
    neither covers the candidate set it would have come from — ``__post_init__``
    holds no candidate set to compare the halves against, so coverage is
    ``frontier_of``'s property and never this constructor's — while an id that
    appears on both sides is still refused here."""

    entry = FrontierMemberEntry(
        candidate_id="c-a",
        focus_target="res-hedge-i-think",
        origins=("EXPRESSION_NEED",),
        members=(FrontierMember.PERSONAL_EXPRESSION_NEEDS,),
        unmapped_origins=(),
    )
    empty = ActiveLearningFrontier(members=(), excluded=())
    assert empty.candidate_ids == ()
    assert empty.excluded_ids == ()
    partial = ActiveLearningFrontier(members=(entry,), excluded=())
    assert partial.candidate_ids == ("c-a",)
    assert partial.excluded_ids == ()
    with pytest.raises(ValueError) as raised:
        ActiveLearningFrontier(
            members=(entry,),
            excluded=(
                ExcludedCandidate(candidate_id="c-a", exclusion="EXPIRED"),
            ),
        )
    assert "both a frontier member and excluded" in str(raised.value)
