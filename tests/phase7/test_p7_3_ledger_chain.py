"""P7-3 ⑥⑦ — the ledger on the real chain, and the frontier of a real run.

Everything here is a real read: app.db with the migrations applied, the shipped
content.db, the Scheduler's own due decision, the §9 constraint view, the §8.1
ladder (with P7-2's one-declared-input convention for the level this corpus
cannot answer) and the kernel. The ledger is the caller's view — that is the
whole carrier of P7-3 — a caller-assembled view, ``NO_TABLE_V1`` then; P8-3
gave the ledger durable tables behind ``elc.planner.ledger_store``, and this
suite still hands the kernel a view rather than a store) — and the one thing
these tests add to the world is that view.

Two facts are the point:

- the ledger **turns the ``COVERAGE_DEBT`` source on** and the three readings it
  moves come from it — with no ledger, the same world behaves exactly as it did
  before this cut (same gap text, same absent literals);
- a ``CRITICAL`` obligation's candidate is what §13's starvation safeguard is
  for: at a natural break it becomes selectable, and without one it does not
  (the shape the frozen ``S12_COVERAGE_STARVATION`` case is about).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from elc.planner.candidates import (
    ABSENT_READINGS,
    FACTOR_BAND_VALUES,
    UNLANDED_AUTHORITIES,
    CandidateAuthority,
    CandidateSupplyInputs,
    generate_candidates,
)
from elc.planner.frontier import frontier_of
from elc.planner.kernel import (
    BenefitFactor,
    CostFactor,
    CoverageServiceState,
    ExclusionReason,
    KernelStep,
    PlanningInput,
    canonicalize_proposals,
    plan,
)
from elc.planner.ledger import (
    CoverageObligation,
    LedgerEvent,
    LedgerWindow,
    ObligationScope,
    PauseReason,
    PlanningLedger,
    TargetLedgerRow,
    accrue,
)
from elc.planner.scope import (
    ConversationPriorityView,
    FlowPriority,
    InteractionPhase,
)
from elc.planner.types import (
    InitiativeClass,
    PlannerDecisionOutcome,
    TargetMode,
)
from elc.platform.types import DecisionCycleId

from .test_p7_2_generators_and_chain import (
    AS_OF,
    DECLARED_LEVEL_FACTS,
    FOCUS_TARGET,
    DeclaredLevels,
    World,
)

OBLIGATION_KEY = "co-p73-1"
WINDOW_START = "2026-09-16T09:00:00+00:00"
WINDOW_END = "2026-09-24T09:00:00+00:00"
WINDOW = LedgerWindow(start=WINDOW_START, end=WINDOW_END)


@pytest.fixture()
def world(db, content_supply) -> World:
    """The real world P7-2's chain tests build, with **no** manual focus — so
    the §12 scope is OPEN and a candidate is excluded only by its own facts."""

    built = World(db, content_supply)
    built.policy_and_goals()
    built.schedule_row("CAPABILITY", FOCUS_TARGET, "si-p73-focus")
    return built


@pytest.fixture()
def levels(world: World) -> DeclaredLevels:
    return DeclaredLevels(world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS})


def obligation(
    debt: float = 1.0,
    *,
    paused: bool = False,
    scope: str = "TARGET",
    target: str = FOCUS_TARGET,
    key: str = OBLIGATION_KEY,
) -> CoverageObligation:
    """One real obligation for this world's one graded target."""

    return CoverageObligation(
        obligation_key=key,
        scope_type=scope,
        target_or_family_id=target,
        goal_id=None,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        debt_value=debt,
        accrual_paused=paused,
        pause_reason=(
            PauseReason.UNAVAILABLE_IN_CURRENT_RUNTIME.value if paused else None
        ),
        last_served_at=None,
        last_engaged_at=None,
    )


def ledger(
    *,
    debt: float | None = 1.0,
    paused: bool = False,
    scope: str = "TARGET",
    presentations: tuple[str, ...] = (),
) -> PlanningLedger:
    """One caller-assembled ledger: an obligation, and this target's row."""

    rows: dict[str, TargetLedgerRow] = {}
    if presentations:
        row = TargetLedgerRow(
            target_key=FOCUS_TARGET, overexposure_window=WINDOW
        )
        for at in presentations:
            row = row.record(LedgerEvent.TEACHING_PRESENTED, at=at)
        rows[FOCUS_TARGET] = row
    obligations = (
        () if debt is None else (obligation(debt, paused=paused, scope=scope),)
    )
    return PlanningLedger(rows=rows, obligations=obligations)


def inputs_for(
    world: World,
    levels: DeclaredLevels,
    view: PlanningLedger | None,
    *,
    break_available: bool = False,
) -> CandidateSupplyInputs:
    """One call's inputs: the real world, plus the ledger under test.

    ``break_available`` moves the two legs a natural break is made of — §13's
    flow priority (which prices the interruption) and the view's own break flag.
    The default is the world P7-2's chain tests use: a NORMAL flow whose break is
    not available.
    """

    priority = ConversationPriorityView(
        flow_priority=(
            FlowPriority.LOW if break_available else FlowPriority.NORMAL
        ),
        interaction_phase=InteractionPhase.OPEN,
        natural_break_available=break_available,
    )
    return replace(world.inputs(levels=levels), ledger=view, priority=priority)


def planning_input(supply, authority) -> PlanningInput:  # noqa: ANN001
    """The kernel input a caller builds from one supply call — no adapter."""

    return PlanningInput(
        decision_cycle_id=DecisionCycleId("dc-p73"),
        planning_context=authority,
        user_intent_scope=supply.scope.scope,
        proposals=supply.proposals,
    )


def debt_proposal(supply):  # noqa: ANN001, ANN201
    proposals = supply.proposals_of("COVERAGE_DEBT")
    assert len(proposals) == 1, proposals
    return proposals[0]


# ---------------------------------------------------------------------------
# ⑥ no ledger: exactly what this world did before the cut
# ---------------------------------------------------------------------------


def test_without_a_ledger_the_source_gaps_with_the_same_text(
    world: World, levels: DeclaredLevels
) -> None:
    supply = generate_candidates(inputs_for(world, levels, None))
    gaps = {gap.source: gap for gap in supply.gaps}
    assert gaps["COVERAGE_DEBT"].authority is CandidateAuthority.PLANNING_LEDGER
    assert gaps["COVERAGE_DEBT"].reason == (
        UNLANDED_AUTHORITIES[CandidateAuthority.PLANNING_LEDGER]
    )
    assert set(supply.sources_answered) == {"SCHEDULED_REVIEW", "UNKNOWN_PROBE"}
    assert ABSENT_READINGS["overexposure"] == "NONE"
    neutral = FACTOR_BAND_VALUES["overexposure"]["NONE"]
    assert neutral == 0.0
    for proposal in supply.proposals:
        assert proposal.benefit[BenefitFactor.COVERAGE_DEBT] == 0.0
        assert proposal.cost[CostFactor.OVEREXPOSURE] == neutral
        assert proposal.coverage_service_state is CoverageServiceState.NONE


def test_the_shipped_corpus_is_still_unreachable_with_a_ledger(
    world: World,
) -> None:
    """A ledger does not make the corpus teachable: the same 14 targets are
    refused at the §8.1 gate, and the debt source has nothing to propose
    because no candidate target exists."""

    supply = generate_candidates(inputs_for(world, world.supply, ledger()))
    assert supply.proposals == ()
    assert {refusal.gate for refusal in supply.refusals} == {"CONTENT_READINESS"}
    assert len(supply.refusals) == 14
    assert "COVERAGE_DEBT" not in {gap.source for gap in supply.gaps}


# ---------------------------------------------------------------------------
# ⑥ the ledger on: one source runs, and three readings come from it
# ---------------------------------------------------------------------------


def test_the_ledger_turns_the_coverage_debt_source_on(
    world: World, levels: DeclaredLevels
) -> None:
    supply = generate_candidates(inputs_for(world, levels, ledger(debt=1.0)))
    assert "COVERAGE_DEBT" not in {gap.source for gap in supply.gaps}
    assert set(supply.sources_answered) == {
        "SCHEDULED_REVIEW",
        "UNKNOWN_PROBE",
        "COVERAGE_DEBT",
    }
    proposal = debt_proposal(supply)
    assert proposal.focus_target == FOCUS_TARGET
    assert proposal.target_mode is TargetMode.CAPABILITY_PRACTICE
    assert proposal.initiative_class is InitiativeClass.PROACTIVE
    assert proposal.user_initiated is False
    assert proposal.benefit[BenefitFactor.COVERAGE_DEBT] == 1.0
    assert proposal.coverage_service_state is CoverageServiceState.CRITICAL


def test_the_three_readings_come_from_the_ledger(
    world: World, levels: DeclaredLevels
) -> None:
    """``coverage_debt`` is the obligation's own number and
    ``coverage_service_state`` its ladder position — one obligation, two
    readings — while ``overexposure`` is read for **every** candidate of that
    target, whatever proposed it."""

    supply = generate_candidates(
        inputs_for(
            world,
            levels,
            ledger(
                debt=0.6,
                presentations=(
                    "2026-09-21T09:00:00+00:00",
                    "2026-09-22T09:00:00+00:00",
                    "2026-09-23T09:00:00+00:00",
                ),
            ),
        )
    )
    bands = FACTOR_BAND_VALUES["overexposure"]
    assert bands["HIGH"] == 0.75
    for proposal in supply.proposals:
        assert proposal.cost[CostFactor.OVEREXPOSURE] == bands["HIGH"]
    proposal = debt_proposal(supply)
    assert proposal.benefit[BenefitFactor.COVERAGE_DEBT] == 0.6
    assert proposal.coverage_service_state is CoverageServiceState.DUE


def test_an_exposure_outside_the_window_is_not_counted(
    world: World, levels: DeclaredLevels
) -> None:
    """The band follows the window rather than the total: the same row with its
    one presentation before the window answers the neutral band."""

    outside = "2026-09-01T09:00:00+00:00"
    supply = generate_candidates(
        inputs_for(world, levels, ledger(debt=1.0, presentations=(outside,)))
    )
    proposal = debt_proposal(supply)
    assert proposal.cost[CostFactor.OVEREXPOSURE] == 0.0
    assert len(supply.readiness) == 14  # the world really looked at the corpus


def test_a_paused_obligation_proposes_nothing_and_moves_no_debt(
    world: World, levels: DeclaredLevels
) -> None:
    paused = obligation(debt=1.0, paused=True)
    supply = generate_candidates(
        inputs_for(world, levels, PlanningLedger(obligations=(paused,)))
    )
    assert supply.proposals_of("COVERAGE_DEBT") == ()
    assert "COVERAGE_DEBT" not in {gap.source for gap in supply.gaps}
    outcome = accrue(paused, amount=0.5, at=AS_OF)
    assert outcome.changed is False
    assert outcome.obligation.debt_value == 1.0
    assert PauseReason.UNAVAILABLE_IN_CURRENT_RUNTIME.value in outcome.reason


def test_a_family_scoped_obligation_proposes_nothing_and_is_not_a_refusal(
    world: World, levels: DeclaredLevels
) -> None:
    family = obligation(
        debt=1.0, scope=ObligationScope.TARGET_FAMILY.value
    )
    supply = generate_candidates(
        inputs_for(world, levels, PlanningLedger(obligations=(family,)))
    )
    assert supply.proposals_of("COVERAGE_DEBT") == ()
    assert "OUTSIDE_SUPPLY" not in {r.gate for r in supply.refusals}
    assert set(supply.sources_answered) == {"SCHEDULED_REVIEW", "UNKNOWN_PROBE"}


def test_a_ledger_naming_an_unknown_target_is_an_outside_supply_refusal(
    world: World, levels: DeclaredLevels
) -> None:
    stray = obligation(debt=1.0, target="res-not-in-this-corpus", key="co-stray")
    supply = generate_candidates(
        inputs_for(world, levels, PlanningLedger(obligations=(stray,)))
    )
    refusals = [
        refusal
        for refusal in supply.refusals
        if refusal.source == "COVERAGE_DEBT"
    ]
    assert len(refusals) == 1
    assert refusals[0].gate == "OUTSIDE_SUPPLY"
    assert refusals[0].target_id == "res-not-in-this-corpus"


# ---------------------------------------------------------------------------
# ⑦ the end-to-end: the frontier column, and §13's safeguard on the real chain
# ---------------------------------------------------------------------------


def test_the_frontier_of_a_real_run_is_the_survivors(
    world: World, levels: DeclaredLevels
) -> None:
    supply = generate_candidates(inputs_for(world, levels, ledger(debt=1.0)))
    authority = world.authority(supply.candidate_readiness, natural_break=True)
    result = plan(planning_input(supply, authority))
    survivors = tuple(
        row.candidate_id
        for row in result.trace.candidates
        if row.excluded is None
    )
    excluded = {
        row.candidate_id: row.excluded.value
        for row in result.trace.candidates
        if row.excluded is not None
    }
    assert result.outcome.evaluation.frontier_candidate_ids == survivors
    assert len(survivors) == len(supply.proposals)
    assert debt_proposal(supply).candidate_id in survivors
    assert not set(excluded) & set(survivors)
    rebuilt = frontier_of(canonicalize_proposals(supply.proposals), excluded)
    assert rebuilt.candidate_ids == (
        result.outcome.evaluation.frontier_candidate_ids
    )
    assert rebuilt.excluded_ids == tuple(sorted(excluded))


def test_the_critical_debt_candidate_needs_a_natural_break(
    world: World, levels: DeclaredLevels
) -> None:
    """§13's safeguard, end to end: in a flow that *is* a natural break the
    CRITICAL obligation's candidate wins; with the context's break flag down it
    is not even activated, and the cycle's decision is NO_TARGET.

    Three legs carry the shape, and all three are real reads rather than test
    convenience: the flow priority is LOW (so the interruption cost is the
    ladder's own ``LOW`` band, which is what "a break" costs), the ledger says
    ``CRITICAL``, and the context's ``natural_break_available`` is the leg §13
    reads — the kernel takes it from P7-0's ``FeatureAuthority``, which is why
    the second run differs from the first in that flag alone. These are the real
    utilities of this world: ``0.232`` with the bonus (activated, threshold
    ``0.195``) and ``0.152`` without it.
    """

    at_break = generate_candidates(
        inputs_for(world, levels, ledger(debt=1.0), break_available=True)
    )
    proposal = debt_proposal(at_break)
    first = plan(
        planning_input(
            at_break,
            world.authority(at_break.candidate_readiness, natural_break=True),
        )
    )
    assert first.trace.decision is PlannerDecisionOutcome.SELECT
    assert first.trace.selected_candidate_id == proposal.candidate_id
    rows = {row.candidate_id: row for row in first.trace.candidates}
    bonus = rows[proposal.candidate_id].coverage_service_bonus
    assert bonus is not None and bonus > 0.0
    assert rows[proposal.candidate_id].activated is True
    assert rows[proposal.candidate_id].utility == pytest.approx(0.232)

    quiet = plan(
        planning_input(
            at_break,
            world.authority(at_break.candidate_readiness, natural_break=False),
        )
    )
    quiet_rows = {row.candidate_id: row for row in quiet.trace.candidates}
    assert quiet_rows[proposal.candidate_id].coverage_service_bonus == 0.0
    assert quiet_rows[proposal.candidate_id].activated is False
    assert quiet_rows[proposal.candidate_id].utility == pytest.approx(0.152)
    assert quiet.trace.decision is PlannerDecisionOutcome.NO_TARGET
    assert quiet.trace.no_target_reason.value == "BELOW_ACTIVATION_THRESHOLD"


def test_an_excluded_candidate_is_not_a_frontier_member_on_the_real_chain(
    world: World, levels: DeclaredLevels
) -> None:
    """§9's SUPPRESS_REVIEW marks the review candidate, the kernel's step 4
    excludes it, and the frontier's two halves show it: the excluded id is on
    the excluded side (with the reason) and is not a member, while the debt
    candidate the ledger proposed is one."""

    from elc.user_config.types import PlannerConstraintType

    world.constraint(
        "pc-p73-no-review", PlannerConstraintType.SUPPRESS_REVIEW, None, None
    )
    supply = generate_candidates(inputs_for(world, levels, ledger(debt=1.0)))
    review = supply.proposals_of("SCHEDULED_REVIEW")[0]
    result = plan(
        planning_input(
            supply,
            world.authority(supply.candidate_readiness, natural_break=True),
        )
    )
    rows = {row.candidate_id: row for row in result.trace.candidates}
    assert rows[review.candidate_id].excluded is (ExclusionReason.SUPPRESSED)
    assert review.candidate_id not in (
        result.outcome.evaluation.frontier_candidate_ids
    )
    excluded = {
        row.candidate_id: row.excluded.value
        for row in result.trace.candidates
        if row.excluded is not None
    }
    rebuilt = frontier_of(canonicalize_proposals(supply.proposals), excluded)
    assert rebuilt.excluded_ids == (review.candidate_id,)
    assert review.candidate_id not in rebuilt.candidate_ids
    assert debt_proposal(supply).candidate_id in rebuilt.candidate_ids


def test_the_service_state_is_what_carries_the_safeguard(
    world: World, levels: DeclaredLevels
) -> None:
    """The same run with the debt below the ladder's top: the safeguard does not
    fire, because the state that travels to the kernel is ``DUE`` and §13 reads
    ``CRITICAL``."""

    supply = generate_candidates(
        inputs_for(world, levels, ledger(debt=0.5))
    )
    proposal = debt_proposal(supply)
    assert proposal.coverage_service_state is CoverageServiceState.DUE
    result = plan(
        planning_input(
            supply,
            world.authority(supply.candidate_readiness, natural_break=True),
        )
    )
    rows = {row.candidate_id: row for row in result.trace.candidates}
    assert rows[proposal.candidate_id].coverage_service_bonus == 0.0


def test_the_ledger_never_decides_and_never_filters(
    world: World, levels: DeclaredLevels
) -> None:
    """Every candidate the ledger's world produced reaches the kernel's step 4,
    the whole eleven-step order runs, and the frontier's two halves together
    hold the canonical set — the ledger proposes, it does not decide."""

    supply = generate_candidates(inputs_for(world, levels, ledger(debt=1.0)))
    authority = world.authority(supply.candidate_readiness)
    result = plan(planning_input(supply, authority))
    seen = {row.candidate_id for row in result.trace.candidates}
    assert seen == {proposal.candidate_id for proposal in supply.proposals}
    assert result.trace.steps == tuple(KernelStep)
    excluded = [
        row for row in result.trace.candidates if row.excluded is not None
    ]
    assert len(result.outcome.evaluation.frontier_candidate_ids) + len(
        excluded
    ) == len(supply.proposals)


def test_a_debt_candidate_carries_the_ledger_s_reading_and_not_a_declared_one(
    world: World, levels: DeclaredLevels
) -> None:
    """Two ledgers, one world: the same source row prices the same target at the
    obligation's own number, so the factor is the ledger's rather than the row's
    declared literal (the frozen golden's 1.0)."""

    for debt, expected_state in (
        (0.3, CoverageServiceState.WATCH),
        (0.9, CoverageServiceState.CRITICAL),
    ):
        supply = generate_candidates(
            inputs_for(world, levels, ledger(debt=debt))
        )
        proposal = debt_proposal(supply)
        assert proposal.benefit[BenefitFactor.COVERAGE_DEBT] == debt
        assert proposal.coverage_service_state is expected_state
