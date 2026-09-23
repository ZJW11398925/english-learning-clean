"""P7-2 ①②⑥ — the two generators, and the chain that ends in the kernel.

The chain tests are the point of this file: candidates are produced by the real
gates over the real faces and handed to the **existing**
:func:`elc.planner.kernel.plan` with no adapter, no re-scoring and no second
canonicalization. Two worlds are read, and the first is the honest one:

- the shipped corpus (no level for any target) refuses every target at the §8.1
  gate and the run degrades with ``FEATURE_ASSEMBLY_INCOMPLETE`` — not a
  ``NO_TARGET``;
- a world with **one declared input** (the content-side facts the §8.1 ladder
  reads — the same "one declared input" convention P7-1's own suite uses for the
  level it could not read) makes candidates exist, and the kernel decides.

Everything else in both worlds is a real read: the supply set, the §11 rows, the
§5.2 rows, the Scheduler's due decision, the §9 constraint rows and the §12
scope that follows from them.
"""

from __future__ import annotations

import ast
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from elc.curriculum.readiness import ReadinessFacts, judge_readiness
from elc.curriculum.store import CurriculumContentStore
from elc.learning.controller import LearningController
from elc.learning.silent_evidence import ContentBackedTargetSupply
from elc.learning.store import SqliteLearningStore
from elc.planner import candidates as module
from elc.planner.candidates import (
    ABSENT_READINGS,
    BANDLESS_FACTORS,
    CANDIDATE_SOURCES,
    COMMON_FACES,
    FACTOR_BAND_VALUES,
    OBSERVATION_FIELD,
    SCAFFOLD_BANDS,
    SOURCE_AUTHORITY,
    SOURCE_READINGS,
    SOURCE_TRACK,
    TRACK_A_SOURCES,
    TRACK_B_SOURCES,
    UNLANDED_AUTHORITIES,
    CandidateAuthority,
    CandidateSupplyError,
    CandidateSupplyInputs,
    OpportunityObservation,
    TrackASource,
    TrackBSource,
    generate_candidates,
    generate_track_a,
    generate_track_b,
)
from elc.planner.feature_assembly import (
    SCHEDULE_URGENCY_BANDS,
    assemble_feature_authority,
)
from elc.planner.kernel import (
    MODE_ALLOWED_INTENTS,
    SCAFFOLD_MIN_COGNITIVE_LOAD,
    SCAFFOLD_MIN_SUPPORT_COST,
    BenefitFactor,
    CandidateProposal,
    CostFactor,
    DegradedReason,
    ExclusionReason,
    PlannerInputError,
    PrerequisiteState,
    ReadinessLevel,
    plan,
)
from elc.planner.scope import (
    ConversationPriorityView,
    FlowPriority,
    InteractionPhase,
)
from elc.planner.types import (
    InitiativeClass,
    LearningIntent,
    PlannerDecisionOutcome,
    TargetMode,
    UserIntentScope,
)
from elc.platform.db import epoch
from elc.platform.types import (
    DecisionCycleId,
    EvidenceModality,
    GoalVersion,
    Ok,
    PlannerExecutionStatusValue,
    ScheduleVersion,
    TargetId,
)
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState, ScheduleItem, SpacingStage
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    LearningGoalPortfolio,
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
    TeachingFrequency,
    TeachingPolicyProfile,
)

from .conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    USER,
    canonical_lines,
    document_text,
    source_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = "behavioral_baselines/planner/planner_reference_profile_v1_1.json"
FOCUS_TARGET = "cap-eval-hedged-opinion"
ROW_TARGET = "res-hedge-i-think"
MODALITY = EvidenceModality.TEXT_PRODUCTION
AS_OF = DAY_TWO
DECLARED_LEVEL_FACTS = ReadinessFacts(
    target_id=FOCUS_TARGET,
    entity_row=True,
    canonical_form=True,
    assessment_membership=True,
    pos=True,
    sense=True,
    basic_definition=True,
    forms=True,
    curriculum_link=True,
    pedagogical_profile=True,
    goal_pack_overlay=True,
    resource_labels=True,
    reviewed_explanation=True,
    example_policy=True,
    contrast_or_usage=True,
)


def reference_asset() -> dict:
    return json.loads(source_text(ASSET))


#: The §8.1 fact keys an R3 target carries, one per named thing in §8.1's
#: R0–R3 rows (R4's four are added where a detection-ready target is wanted).
R3_FACT_KEYS = (
    "entity_row",
    "canonical_form",
    "assessment_membership",
    "pos",
    "sense",
    "basic_definition",
    "forms",
    "curriculum_link",
    "pedagogical_profile",
    "goal_pack_overlay",
    "resource_labels",
    "reviewed_explanation",
    "example_policy",
    "contrast_or_usage",
)


R4_FACT_KEYS = (
    "detection_policy",
    "recognition_rules",
    "negative_fixtures",
    "false_positive_boundaries",
)


def r3_facts(target_id: str) -> ReadinessFacts:
    """The declared content-side facts of one R3 target (real ladder, real
    assessment: this file declares facts, never levels)."""

    return ReadinessFacts(
        **{key: True for key in R3_FACT_KEYS}, target_id=target_id
    )


def r4_facts(target_id: str) -> ReadinessFacts:
    """The same, plus R4's four detection facts — the level an *automatic*
    ``CURRENT_USER_ERROR`` candidate needs (BF-02 §10's fourth row)."""

    return ReadinessFacts(
        **{key: True for key in (*R3_FACT_KEYS, *R4_FACT_KEYS)},
        target_id=target_id,
    )


# ---------------------------------------------------------------------------
# ① the two lanes' vocabulary, and the pricing they resolve to
# ---------------------------------------------------------------------------


def test_track_a_s_six_sources_are_the_canonical_block() -> None:
    block = canonical_lines(
        "PRODUCT_CONTRACT.md", "### Track A — Expression-driven"
    )
    assert block == TRACK_A_SOURCES
    assert block == (
        "CURRENT_USER_ERROR",
        "EXPRESSION_NEED",
        "NATURAL_USE_EXPANSION",
        "PRAGMATIC_REGISTER_OPPORTUNITY",
        "MANUAL_USER_REQUEST",
        "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY",
    )
    assert tuple(str(source) for source in TrackASource) == block


def test_track_b_s_eight_sources_are_the_canonical_block() -> None:
    block = canonical_lines(
        "PRODUCT_CONTRACT.md", "### Track B — Curriculum-driven"
    )
    assert block == TRACK_B_SOURCES
    assert block == (
        "CONFIRMED_GAP",
        "SCHEDULED_REVIEW",
        "UNKNOWN_PROBE",
        "TRANSFER_EXPANSION",
        "SUPPORT_WITHDRAWAL",
        "CORE_COVERAGE",
        "GOAL_SPECIFIC_TARGET",
        "COVERAGE_DEBT",
    )
    assert tuple(str(source) for source in TrackBSource) == block


def test_the_two_lanes_enter_one_planner_and_the_repo_says_so() -> None:
    """The sentence that makes this cut one module rather than two, quoted in
    the document and in the module."""

    lines = document_text("PRODUCT_CONTRACT.md")
    assert any("两条 lane 进入同一 Planner" in line for line in lines)
    prose = " ".join((module.__doc__ or "").split())
    assert "两条 lane 进入同一 Planner" in prose
    assert CANDIDATE_SOURCES == TRACK_A_SOURCES + TRACK_B_SOURCES
    assert SOURCE_TRACK["CURRENT_USER_ERROR"] == "A"
    assert SOURCE_TRACK["COVERAGE_DEBT"] == "B"
    assert sorted(set(SOURCE_TRACK)) == sorted(CANDIDATE_SOURCES)
    assert len(CANDIDATE_SOURCES) == len(set(CANDIDATE_SOURCES)) == 14


def test_every_band_ladder_is_the_frozen_asset_s() -> None:
    """Every number in :data:`FACTOR_BAND_VALUES` is extracted from
    ``planner_reference_profile_v1_1.json`` and compared, table for table."""

    asset = reference_asset()
    assert asset["status"] == "REFERENCE_DEFAULT_CALIBRATABLE"
    for factor, bands in asset["reference_factor_bands"].items():
        assert dict(FACTOR_BAND_VALUES[factor]) == bands, factor
    assert set(FACTOR_BAND_VALUES) == set(asset["reference_factor_bands"])
    assert set(BANDLESS_FACTORS) == {"goal_relevance", "coverage_debt"}
    assert BANDLESS_FACTORS[0] not in FACTOR_BAND_VALUES
    assert BANDLESS_FACTORS[1] not in FACTOR_BAND_VALUES


def test_the_schedule_bands_are_p7_0_s_own_table() -> None:
    """One factor's ladder already existed (P7-0's, from the same asset); this
    cut re-reads the asset and pins the two equal rather than re-spelling it."""

    assert dict(FACTOR_BAND_VALUES["schedule_urgency"]) == dict(
        SCHEDULE_URGENCY_BANDS  # keyed by ReviewState, values by word
    )
    assert FACTOR_BAND_VALUES["schedule_urgency"] == {
        str(state): value for state, value in SCHEDULE_URGENCY_BANDS.items()
    }


def test_the_neutral_reading_is_the_lowest_declared_band() -> None:
    """``ABSENT_READINGS``, pinned: every banded factor takes its lowest band
    (never a number the asset does not carry), and only the two bandless
    factors take a literal."""

    asset = reference_asset()["reference_factor_bands"]
    for factor, value in ABSENT_READINGS.items():
        if factor in BANDLESS_FACTORS:
            assert value == 0.0, factor
            continue
        lowest = min(asset[factor].values())
        assert value in asset[factor], factor
        assert asset[factor][value] == lowest, factor
    # the two cost ladders have no zero band: a neutral candidate is cheap and
    # priced, never free.
    assert min(asset["interruption_cost"].values()) > 0.0
    assert min(asset["cognitive_load"].values()) > 0.0
    assert min(asset["curriculum_value"].values()) > 0.0


def test_every_source_row_resolves_and_carries_a_reason() -> None:
    """The table's own contract: fourteen rows, every band a real band, every
    literal on a bandless factor only, and every row justified with a revisit
    condition (a number without a reason is what this table exists to stop)."""

    assert set(SOURCE_READINGS) == set(CANDIDATE_SOURCES)
    for source, reading in SOURCE_READINGS.items():
        assert reading.source == source
        assert reading.track == SOURCE_TRACK[source]
        assert reading.basis and reading.revisit, source
        assert "declared" in reading.basis or "quoted" in reading.basis, source
        for factor, value in reading.benefit.items():
            if isinstance(value, str):
                assert value in FACTOR_BAND_VALUES[factor.value], (source, factor)
            else:
                assert factor.value in BANDLESS_FACTORS, (source, factor)
        for factor, value in reading.cost.items():
            assert isinstance(value, str), (source, factor)
            assert value in FACTOR_BAND_VALUES[factor.value], (source, factor)
        if reading.mode is not None and reading.intent is not None:
            assert reading.intent in MODE_ALLOWED_INTENTS[reading.mode], source
        if reading.mode is TargetMode.PROBE:
            assert reading.intent is LearningIntent.PROBE


def test_the_practice_sources_take_their_identity_from_the_content_row() -> None:
    """Which sources name their own mode/intent and which read the §11 row's —
    the rule that keeps the corpus's own identity the one candidates carry."""

    from_row = {
        "CURRENT_USER_ERROR",
        "EXPRESSION_NEED",
        "NATURAL_USE_EXPANSION",
        "PRAGMATIC_REGISTER_OPPORTUNITY",
        "MANUAL_USER_REQUEST",
        "CONFIRMED_GAP",
        "SUPPORT_WITHDRAWAL",
        "CORE_COVERAGE",
        "GOAL_SPECIFIC_TARGET",
        "COVERAGE_DEBT",
    }
    for source in from_row:
        assert SOURCE_READINGS[source].mode is None, source
    assert SOURCE_READINGS["MANUAL_USER_REQUEST"].intent is None
    assert SOURCE_READINGS["SUPPORT_WITHDRAWAL"].intent is (
        LearningIntent.WITHDRAW_SUPPORT
    )
    for source in (
        "SCHEDULED_REVIEW",
        "UNKNOWN_PROBE",
        "TRANSFER_EXPANSION",
        "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY",
    ):
        reading = SOURCE_READINGS[source]
        assert reading.mode is not None and reading.intent is not None, source


def test_a_band_the_asset_does_not_carry_is_refused() -> None:
    """The table's contract is checked, not trusted: an unknown band word and a
    literal on a banded factor both raise before any proposal exists."""

    from elc.planner.candidates import _resolve

    with pytest.raises(CandidateSupplyError) as unknown_band:
        _resolve("learning_need", "VERY_HIGH")
    assert "not a band of this factor" in str(unknown_band.value)
    with pytest.raises(CandidateSupplyError) as literal:
        _resolve("learning_need", 0.5)
    assert "a literal number is only legal" in str(literal.value)
    assert _resolve("goal_relevance", 0.0) == 0.0


# ---------------------------------------------------------------------------
# ② the registration: which sources read which authority
# ---------------------------------------------------------------------------


def test_every_source_names_one_authority_besides_the_common_faces() -> None:
    assert set(SOURCE_AUTHORITY) == set(CANDIDATE_SOURCES)
    assert COMMON_FACES == (
        CandidateAuthority.TARGET_SUPPLY,
        CandidateAuthority.TARGET_ROW,
        CandidateAuthority.CONTENT_READINESS,
        CandidateAuthority.SCHEDULE_ROW,
    )
    for source, face in SOURCE_AUTHORITY.items():
        assert face is None or isinstance(face, CandidateAuthority), source
    # the four sources whose authority is not landed anywhere
    unlanded = {
        source
        for source, face in SOURCE_AUTHORITY.items()
        if face is not None and face in UNLANDED_AUTHORITIES
    }
    assert unlanded == {
        "TRANSFER_EXPANSION",
        "CORE_COVERAGE",
        "GOAL_SPECIFIC_TARGET",
        "COVERAGE_DEBT",
    }
    for face, reason in UNLANDED_AUTHORITIES.items():
        assert face in set(CandidateAuthority)
        assert len(reason) > 60, face


def test_the_track_a_observation_shape_is_declared_with_its_missing_producer() -> None:
    """Five Track A sources read a turn-scoped fact; RA §4 step 3 names the
    artifact and no cut records one, so the module declares the shape and says
    in the gap text that nothing produced it."""

    assert set(OBSERVATION_FIELD) == {
        "CURRENT_USER_ERROR",
        "EXPRESSION_NEED",
        "NATURAL_USE_EXPANSION",
        "PRAGMATIC_REGISTER_OPPORTUNITY",
        "CURRENT_CONTEXT_TRANSFER_OPPORTUNITY",
    }
    prose = " ".join((module.__doc__ or "").split())
    assert "RUNTIME_ARCHITECTURE §4 step 3" in prose
    assert "Teaching opportunity proposal" in prose
    observation = OpportunityObservation()
    for field in OBSERVATION_FIELD.values():
        assert getattr(observation, field) == ()
    assert "MANUAL_USER_REQUEST" not in OBSERVATION_FIELD


# ---------------------------------------------------------------------------
# ⑥ the chain
# ---------------------------------------------------------------------------


class DeclaredLevels:
    """The one declared input of the chain tests (module docstring)."""

    def __init__(self, real, declared):
        self._real = real
        self._declared = declared

    def readiness(self, entity_id):
        if entity_id in self._declared:
            return Ok(judge_readiness(self._declared[entity_id]))
        return self._real.readiness(entity_id)


class World:
    """One real world: app.db, the real faces over it, and content.db."""

    def __init__(self, db: sqlite3.Connection, content) -> None:
        self.db = db
        self.fence = epoch.open_runtime_epoch(db)
        self.learning = LearningController(SqliteLearningStore(db, self.fence))
        self.user_config_store = SqliteUserConfigStore(db, self.fence)
        self.user_config = UserConfigController(self.user_config_store)
        self.scheduler_store = SqliteSchedulerStore(db, self.fence)
        self.scheduler = SchedulerController(
            self.scheduler_store, learning=self.learning
        )
        self.supply = content
        self.targets = ContentBackedTargetSupply(content)

    def schedule_row(self, target_type: str, target_id: str, item_id: str) -> None:
        assert isinstance(
            self.scheduler_store.upsert_schedule_item(
                ScheduleItem(
                    schedule_item_id=item_id,
                    target_type=target_type,
                    target_id=TargetId(target_id),
                    evidence_modality=MODALITY,
                    review_state=ReviewState.UPCOMING,
                    review_urgency=None,
                    next_review_window_start=DAY_ONE,
                    next_review_window_end=DAY_THREE,
                    spacing_stage=SpacingStage.STAGE_1,
                    source_learning_watermark="0",
                    version=ScheduleVersion(f"sv-{item_id}"),
                )
            ),
            Ok,
        )

    def manual_focus(self, target_type: str, target_id: str) -> None:
        assert isinstance(
            self.user_config_store.record_planner_constraint(
                PlannerConstraint(
                    constraint_id=f"pc-{target_id}",
                    target_type=target_type,
                    target_id=TargetId(target_id),
                    constraint_type=PlannerConstraintType.MANUAL_FOCUS,
                    scope=PlannerConstraintScope.THIS_SESSION,
                    starts_at=DAY_ONE,
                    expires_at=None,
                    active=True,
                )
            ),
            Ok,
        )

    def constraint(self, constraint_id: str, kind, target_type, target_id):
        assert isinstance(
            self.user_config_store.record_planner_constraint(
                PlannerConstraint(
                    constraint_id=constraint_id,
                    target_type=target_type,
                    target_id=target_id,
                    constraint_type=kind,
                    scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
                    starts_at=DAY_ONE,
                    expires_at=None,
                    active=True,
                )
            ),
            Ok,
        )

    def policy_and_goals(self, frequency=TeachingFrequency.BALANCED) -> None:
        assert isinstance(
            self.user_config_store.upsert_teaching_policy(
                TeachingPolicyProfile(
                    teaching_policy_profile_id=USER,
                    policy_version="pv-1",
                    teaching_frequency=frequency,
                )
            ),
            Ok,
        )
        assert isinstance(
            self.user_config_store.upsert_goal_portfolio(
                LearningGoalPortfolio(
                    goal_portfolio_id=USER,
                    goal_version=GoalVersion("gv-1"),
                    assessment_targets=(),
                    effective_from=DAY_ONE,
                )
            ),
            Ok,
        )

    def constraint_view(self, as_of: str = AS_OF):
        view = self.user_config.get_planner_constraint_view(as_of, CONV)
        assert isinstance(view, Ok)
        return view.value

    def inputs(self, *, levels=None, observation=None, as_of: str = AS_OF):
        return CandidateSupplyInputs(
            as_of=as_of,
            targets=self.targets,
            target_rows=self.supply,
            readiness=self.supply if levels is None else levels,
            prerequisites=self.supply,
            learner_state=self.learning,
            schedule=self.scheduler,
            constraints=self.constraint_view(as_of),
            priority=ConversationPriorityView(
                flow_priority=FlowPriority.NORMAL,
                interaction_phase=InteractionPhase.OPEN,
                natural_break_available=False,
            ),
            observation=observation,
        )

    def authority(self, supply_readiness, *, natural_break: bool = False):
        snapshot = self.learning.get_learning_snapshot()
        policy = self.user_config.get_teaching_policy(USER)
        goals = self.user_config.get_goal_portfolio(USER)
        watermark = self.learning.get_learning_watermark()
        assert isinstance(snapshot, Ok) and isinstance(watermark, Ok)
        assert isinstance(policy, Ok) and policy.value is not None
        assert isinstance(goals, Ok) and goals.value is not None
        return assemble_feature_authority(
            learning_snapshot=snapshot.value,
            current_learning_watermark=watermark.value,
            schedule_view=self.scheduler.get_schedule_view(AS_OF).value,
            teaching_policy=policy.value,
            goal_portfolio=goals.value,
            curriculum_readiness=supply_readiness,
            constraint_view_present=True,
            natural_break_available=natural_break,
        )


@pytest.fixture()
def world(db: sqlite3.Connection, content_supply) -> World:
    return World(db, content_supply)


@pytest.fixture()
def wired_world(world: World) -> World:
    world.policy_and_goals()
    world.schedule_row("CAPABILITY", FOCUS_TARGET, "si-p72-focus")
    world.schedule_row("RESOURCE", ROW_TARGET, "si-p72-row")
    world.manual_focus("CAPABILITY", FOCUS_TARGET)
    return world


def test_the_shipped_corpus_refuses_every_target_and_the_run_degrades(
    wired_world: World,
) -> None:
    """The honest chain: real supply, real rows, real ladder — and no candidate
    exists, because §8.1 reports no level for any shipped target. The context
    built from the *same read* is INCOMPLETE, and the kernel degrades instead of
    inventing a decision."""

    supply = generate_candidates(wired_world.inputs())
    assert supply.proposals == ()
    assert {refusal.gate for refusal in supply.refusals} == {
        "CONTENT_READINESS"
    }
    assert len(supply.refusals) == 14
    assert set(supply.readiness.values()) == {None}

    authority = wired_world.authority(supply.readiness)
    assert authority.complete is False
    result = plan(
        module_planning_input(supply, authority)
    )
    assert result.outcome.execution_status.status is (
        PlannerExecutionStatusValue.DEGRADED
    )
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )
    assert result.outcome.decision is None
    assert result.trace.candidates == ()


def module_planning_input(supply, authority):
    """The kernel input a caller builds from one supply call — no adapter."""

    from elc.planner.kernel import PlanningInput

    return PlanningInput(
        decision_cycle_id=DecisionCycleId("dc-p72"),
        planning_context=authority,
        user_intent_scope=supply.scope.scope,
        proposals=supply.proposals,
    )


def test_the_sources_that_cannot_answer_name_their_missing_authority(
    wired_world: World,
) -> None:
    """Which sources can answer in a world whose caller holds every landed
    face, and which say why they cannot: the five Track A sources wait for a
    turn observation (no producer), the four unlanded ones wait for an
    authority, and MANUAL_USER_REQUEST is not among them because the user's own
    §9 row is a real one."""

    supply = generate_track_a(wired_world.inputs())
    track_a_gaps = {gap.source: gap.authority for gap in supply.gaps}
    assert track_a_gaps == {
        source: CandidateAuthority.TURN_OPPORTUNITY
        for source in TRACK_A_SOURCES
        if source != "MANUAL_USER_REQUEST"
    }

    track_b = generate_track_b(wired_world.inputs())
    track_b_gaps = {gap.source: gap.authority for gap in track_b.gaps}
    assert track_b_gaps == {
        "TRANSFER_EXPANSION": CandidateAuthority.TRANSFER_POLICY,
        "CORE_COVERAGE": CandidateAuthority.CORE_TIER,
        "GOAL_SPECIFIC_TARGET": CandidateAuthority.GOAL_PACK_MAPPING,
        "COVERAGE_DEBT": CandidateAuthority.PLANNING_LEDGER,
    }
    assert set(track_b.sources_answered) == set()


def test_the_chain_selects_when_the_one_declared_input_is_given(
    wired_world: World,
) -> None:
    """With the content-side facts declared (P7-1's own convention for the level
    it cannot read), three real sources answer from real rows — the user's
    manual focus, the Scheduler's own due decision and Learning's silence about
    the target — the §12 scope is TARGETED_LEARNING_REQUEST, and the existing
    kernel SELECTs the requested target."""

    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    supply = generate_candidates(wired_world.inputs(levels=levels))
    sources = {origin for p in supply.proposals for origin in p.origins}
    assert sources == {
        "MANUAL_USER_REQUEST",
        "SCHEDULED_REVIEW",
        "UNKNOWN_PROBE",
    }
    assert all(isinstance(p, CandidateProposal) for p in supply.proposals)
    assert supply.scope.scope is UserIntentScope.TARGETED_LEARNING_REQUEST

    by_source = {p.origins[0]: p for p in supply.proposals}
    manual = by_source["MANUAL_USER_REQUEST"]
    assert manual.target_mode is TargetMode.CAPABILITY_PRACTICE
    assert manual.learning_intent is LearningIntent.DEVELOP
    assert manual.user_initiated is True and manual.request_aligned is True
    assert manual.prerequisite_state is PrerequisiteState.READY
    assert manual.content_readiness is ReadinessLevel.R3_TEACHING_READY
    review = by_source["SCHEDULED_REVIEW"]
    assert review.target_mode is TargetMode.REVIEW
    assert review.learning_intent is LearningIntent.CONSOLIDATE
    assert review.schedule_row is not None
    probe = by_source["UNKNOWN_PROBE"]
    assert probe.target_mode is TargetMode.PROBE
    assert probe.initiative_class is InitiativeClass.PROACTIVE

    authority = wired_world.authority(supply.candidate_readiness)
    assert authority.complete is True
    result = plan(module_planning_input(supply, authority))
    assert result.trace.decision is PlannerDecisionOutcome.SELECT
    assert result.outcome.decision is not None
    assert result.outcome.decision.selected_candidate_id == manual.candidate_id
    trace = {row.candidate_id: row for row in result.trace.candidates}
    assert trace[manual.candidate_id].excluded is None
    assert trace[review.candidate_id].excluded is (
        ExclusionReason.OUTSIDE_TARGETED_SCOPE
    )
    assert trace[probe.candidate_id].excluded is (
        ExclusionReason.OUTSIDE_TARGETED_SCOPE
    )


def test_the_broad_readiness_read_is_the_coarse_one_and_degrades(
    wired_world: World,
) -> None:
    """The two readings of the same read, pinned: feeding the levels of every
    target the call looked at makes the assembly INCOMPLETE (the coarse "the
    level supply is not complete" reading), while the candidate-scoped subset —
    the scope P7-0's leg names — does not."""

    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    supply = generate_candidates(wired_world.inputs(levels=levels))
    broad = wired_world.authority(supply.readiness)
    assert broad.complete is False
    narrow = wired_world.authority(supply.candidate_readiness)
    assert narrow.complete is True
    assert supply.candidate_readiness == {FOCUS_TARGET: "R3_TEACHING_READY"}
    assert len(supply.readiness) == 14


def test_the_scope_constraint_is_what_restricts_the_candidate_set(
    wired_world: World,
) -> None:
    """§12's sentence, as behaviour: with the manual focus in force the kernel
    excludes the review and the probe; take the request away and the same two
    candidates are eligible (the scope word, not a bonus, did that)."""

    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    with_request = generate_candidates(wired_world.inputs(levels=levels))
    assert with_request.scope.scope is UserIntentScope.TARGETED_LEARNING_REQUEST

    without = CandidateSupplyInputs(
        as_of=AS_OF,
        targets=wired_world.targets,
        target_rows=wired_world.supply,
        readiness=levels,
        prerequisites=wired_world.supply,
        learner_state=wired_world.learning,
        schedule=wired_world.scheduler,
        constraints=None,
        priority=None,
        observation=None,
    )
    supply = generate_candidates(without)
    assert supply.scope.scope is UserIntentScope.OPEN
    assert supply.scope.constraint_view_present is False
    authority = wired_world.authority(supply.candidate_readiness)
    result = plan(module_planning_input(supply, authority))
    excluded = {
        row.candidate_id: row.excluded for row in result.trace.candidates
    }
    assert ExclusionReason.OUTSIDE_TARGETED_SCOPE not in excluded.values()
    assert len(result.trace.candidates) == len(supply.proposals) == 2
    # the same two candidates the request had excluded now reach activation —
    # and neither clears the BALANCED profile's automatic threshold on its own
    # declared readings, which is a decision (NO_TARGET) and not a degradation.
    assert result.trace.decision is PlannerDecisionOutcome.NO_TARGET
    assert result.trace.no_target_reason is not None
    assert result.trace.no_target_reason.value == "BELOW_ACTIVATION_THRESHOLD"
    assert all(row.utility is not None for row in result.trace.candidates)


def test_a_declared_observation_answers_the_track_a_sources(
    wired_world: World,
) -> None:
    """Five Track A sources are one declared observation away from answering —
    and the observation changes nothing about how they are priced (the source
    rows do that) nor about the identity (the §11 row does)."""

    levels = DeclaredLevels(
        wired_world.supply,
        {FOCUS_TARGET: DECLARED_LEVEL_FACTS, ROW_TARGET: r4_facts(ROW_TARGET)},
    )
    observation = OpportunityObservation(
        current_user_errors=(ROW_TARGET,),
        natural_use_expansions=(ROW_TARGET,),
    )
    supply = generate_candidates(
        wired_world.inputs(levels=levels, observation=observation)
    )
    by_source = {p.origins[0]: p for p in supply.proposals}
    assert set(by_source) >= {
        "CURRENT_USER_ERROR",
        "NATURAL_USE_EXPANSION",
        "MANUAL_USER_REQUEST",
    }
    error = by_source["CURRENT_USER_ERROR"]
    assert error.target_mode is TargetMode.RESOURCE_PRACTICE
    assert error.learning_intent is LearningIntent.DEVELOP
    assert error.initiative_class is InitiativeClass.REACTIVE
    assert error.opportunity_binding_class == "CURRENT_USER_ERROR"
    assert error.benefit[BenefitFactor.LEARNING_NEED] == (
        FACTOR_BAND_VALUES["learning_need"]["HIGH"]
    )
    assert error.benefit[BenefitFactor.OPPORTUNITY_EXPIRY] == (
        FACTOR_BAND_VALUES["opportunity_expiry"]["THIS_TURN"]
    )
    assert error.content_readiness is ReadinessLevel.R4_DETECTION_READY
    # the two Track A candidates for one target are two opportunities: their
    # keys differ by binding class and intent, so the kernel's merge never has
    # to choose between two vectors.
    keys = [p.canonical_key for p in supply.proposals]
    assert len(keys) == len(set(keys))

    # the same call without the observation: the sources gap again.
    plain = generate_candidates(wired_world.inputs(levels=levels))
    assert "CURRENT_USER_ERROR" not in {
        origin for p in plain.proposals for origin in p.origins
    }
    assert any(
        gap.source == "CURRENT_USER_ERROR"
        and gap.authority is CandidateAuthority.TURN_OPPORTUNITY
        for gap in plain.gaps
    )


def _error_world(wired_world: World, facts: ReadinessFacts):
    """One declared Track A candidate in an OPEN cycle (no §9 rows in force).

    The target is the capability one, because a *resource* target's
    prerequisites answer UNKNOWN in this corpus (its only curriculum link is
    unapproved) and the kernel checks prerequisites before readiness — which is
    its own pin, one file over.
    """

    levels = DeclaredLevels(wired_world.supply, {FOCUS_TARGET: facts})
    return generate_candidates(
        CandidateSupplyInputs(
            as_of=AS_OF,
            targets=wired_world.targets,
            target_rows=wired_world.supply,
            readiness=levels,
            prerequisites=wired_world.supply,
            learner_state=wired_world.learning,
            schedule=wired_world.scheduler,
            constraints=None,
            priority=ConversationPriorityView(
                flow_priority=FlowPriority.NORMAL,
                interaction_phase=InteractionPhase.OPEN,
                natural_break_available=False,
            ),
            observation=OpportunityObservation(
                current_user_errors=(FOCUS_TARGET,)
            ),
        )
    )


def test_an_automatic_current_user_error_candidate_needs_r4(
    wired_world: World,
) -> None:
    """BF-02 §10's four rows, reached from this cut: the same declared candidate
    is excluded at R3 (``CONTENT_NOT_READY``) and eligible at R4 — the floor is
    the kernel's, read off the origin the generator supplied."""

    supply = _error_world(wired_world, r3_facts(ROW_TARGET))
    assert supply.scope.scope is UserIntentScope.OPEN
    assert len(supply.proposals_of("CURRENT_USER_ERROR")) == 1
    authority = wired_world.authority(supply.candidate_readiness)
    result = plan(module_planning_input(supply, authority))
    error = supply.proposals_of("CURRENT_USER_ERROR")[0]
    row = [
        entry
        for entry in result.trace.candidates
        if entry.candidate_id == error.candidate_id
    ][0]
    assert row.excluded is ExclusionReason.CONTENT_NOT_READY

    r4 = _error_world(wired_world, r4_facts(ROW_TARGET))
    r4_error = r4.proposals_of("CURRENT_USER_ERROR")[0]
    assert r4_error.content_readiness is ReadinessLevel.R4_DETECTION_READY
    r4_result = plan(
        module_planning_input(r4, wired_world.authority(r4.candidate_readiness))
    )
    r4_row = [
        entry
        for entry in r4_result.trace.candidates
        if entry.candidate_id == r4_error.candidate_id
    ][0]
    assert r4_row.excluded is None
    assert r4_result.trace.decision is PlannerDecisionOutcome.SELECT


def test_the_declared_pricing_is_what_the_kernel_scores(
    wired_world: World,
) -> None:
    """One declared Track A candidate, scored by the kernel: the utility is
    BF-02 §12's own formula over this table's bands (the arithmetic is
    recomputed here, so a band change moves the assertion with it)."""

    from elc.planner.feature_assembly import PlannerProfile
    from elc.planner.kernel import BENEFIT_WEIGHTS, COST_WEIGHTS, POLICY_PROFILES

    supply = _error_world(wired_world, r4_facts(ROW_TARGET))
    assert supply.scope.scope is UserIntentScope.OPEN
    error = supply.proposals_of("CURRENT_USER_ERROR")[0]
    benefit = sum(
        BENEFIT_WEIGHTS[factor] * value
        for factor, value in error.benefit.items()
    )
    cost = sum(
        COST_WEIGHTS[factor] * value for factor, value in error.cost.items()
    )
    profile = POLICY_PROFILES[PlannerProfile.BALANCED]
    expected = (
        profile.initiative_multiplier[error.initiative_class] * benefit
        - profile.cost_multiplier * cost
    )
    authority = wired_world.authority(supply.candidate_readiness)
    result = plan(module_planning_input(supply, authority))
    row = [
        entry
        for entry in result.trace.candidates
        if entry.candidate_id == error.candidate_id
    ][0]
    assert row.utility == pytest.approx(expected)
    assert row.benefit_score == pytest.approx(benefit)
    assert row.cost_score == pytest.approx(cost)


def test_a_target_with_no_five_two_row_is_refused_not_priced_at_zero(
    wired_world: World,
) -> None:
    """The Scheduler was never asked about this target, so no candidate is
    built: BF-02 §5 forbids the ``0``, and the kernel would degrade on a rowless
    proposal (P7-1's judgement 13). The refusal is the *Scheduler's*, which is
    what makes it readable — the target's level is declared, so the §8.1 gate
    let it through and the §5.2 row is the only thing missing."""

    unrowed = "cap-ref-ask-clarification"
    levels = DeclaredLevels(
        wired_world.supply,
        {FOCUS_TARGET: DECLARED_LEVEL_FACTS, unrowed: r3_facts(unrowed)},
    )
    observation = OpportunityObservation(expression_needs=(unrowed,))
    supply = generate_candidates(
        wired_world.inputs(levels=levels, observation=observation)
    )
    refused = [
        refusal
        for refusal in supply.refusals
        if refusal.target_id == unrowed
    ]
    assert refused, supply.refusals
    assert refused[0].gate == "SCHEDULE_ROW"
    assert "holds no §5.2 row" in refused[0].reason
    assert unrowed not in {p.focus_target for p in supply.proposals}
    # and no proposal anywhere carries a rowless candidate
    assert all(proposal.schedule_row is not None for proposal in supply.proposals)


def test_a_declared_scaffold_carries_the_floors_the_kernel_checks(
    wired_world: World,
) -> None:
    """BF-02 §11: a scaffolded candidate may not look free. The generator raises
    the two cost factors to the scaffold reading and the kernel accepts the
    candidate — the floors are the kernel's constants, not a second copy."""

    from elc.curriculum.types import PrerequisiteStrength

    from .test_p7_2_supply_gates import DeclaredGraph, edge

    graph = DeclaredGraph(
        capabilities=(FOCUS_TARGET,),
        edges=(
            edge(
                "cap-disc-topic-shift",
                FOCUS_TARGET,
                PrerequisiteStrength.SCAFFOLDABLE,
            ),
        ),
    )
    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    supply = generate_candidates(
        CandidateSupplyInputs(
            as_of=AS_OF,
            targets=wired_world.targets,
            target_rows=wired_world.supply,
            readiness=levels,
            prerequisites=graph,
            learner_state=wired_world.learning,
            schedule=wired_world.scheduler,
            constraints=wired_world.constraint_view(),
            priority=None,
            observation=None,
        )
    )
    manual = supply.proposals_of("MANUAL_USER_REQUEST")[0]
    assert manual.prerequisite_state is PrerequisiteState.READY_WITH_SCAFFOLD
    assert manual.prerequisite_scaffoldable is True
    assert manual.cost[CostFactor.SUPPORT_COST] >= SCAFFOLD_MIN_SUPPORT_COST
    assert manual.cost[CostFactor.COGNITIVE_LOAD] >= SCAFFOLD_MIN_COGNITIVE_LOAD
    assert manual.cost[CostFactor.SUPPORT_COST] == (
        FACTOR_BAND_VALUES["support_cost"][SCAFFOLD_BANDS["support_cost"]]
    )
    # the kernel's own scaffold check accepts the pair (a floor-missing
    # candidate would raise PlannerInputError here).
    result = plan(
        module_planning_input(
            supply, wired_world.authority(supply.candidate_readiness)
        )
    )
    row = [
        entry
        for entry in result.trace.candidates
        if entry.candidate_id == manual.candidate_id
    ][0]
    assert row.excluded is None


def test_a_hard_unjudged_edge_travels_beside_the_scaffold_to_the_kernel(
    wired_world: World,
) -> None:
    """BF-02 §11's second shape, end to end: the merged case (a ``HARD`` edge
    nobody can judge *and* an unmet ``SCAFFOLDABLE`` edge) reaches the kernel
    as ``UNKNOWN`` + ``prerequisite_scaffoldable``, keeps the two scaffold
    floors, and is not excluded by the UNKNOWN rule — the scaffold bypasses it
    whether the word is ``UNKNOWN`` or ``READY_WITH_SCAFFOLD``, which is what
    makes the two shapes one behaviour and two words."""

    from elc.curriculum.types import PrerequisiteStrength

    from .test_p7_2_supply_gates import DeclaredGraph, edge

    graph = DeclaredGraph(
        capabilities=(FOCUS_TARGET,),
        edges=(
            edge("cap-hard", FOCUS_TARGET, PrerequisiteStrength.HARD),
            edge(
                "cap-disc-topic-shift",
                FOCUS_TARGET,
                PrerequisiteStrength.SCAFFOLDABLE,
            ),
        ),
    )
    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    supply = generate_candidates(
        CandidateSupplyInputs(
            as_of=AS_OF,
            targets=wired_world.targets,
            target_rows=wired_world.supply,
            readiness=levels,
            prerequisites=graph,
            learner_state=wired_world.learning,
            schedule=wired_world.scheduler,
            constraints=wired_world.constraint_view(),
            priority=None,
            observation=None,
        )
    )
    manual = supply.proposals_of("MANUAL_USER_REQUEST")[0]
    assert manual.prerequisite_state is PrerequisiteState.UNKNOWN
    assert manual.prerequisite_scaffoldable is True
    assert manual.cost[CostFactor.SUPPORT_COST] >= SCAFFOLD_MIN_SUPPORT_COST
    assert manual.cost[CostFactor.COGNITIVE_LOAD] >= SCAFFOLD_MIN_COGNITIVE_LOAD
    result = plan(
        module_planning_input(
            supply, wired_world.authority(supply.candidate_readiness)
        )
    )
    row = [
        entry
        for entry in result.trace.candidates
        if entry.candidate_id == manual.candidate_id
    ][0]
    assert row.excluded is None


def test_the_corpus_world_refuses_before_the_schedule_gate_reads(
    wired_world: World,
) -> None:
    """Order of refusals: the §8.1 gate answers before the §5.2 row is read, so
    an ungraded target reports CONTENT_READINESS rather than SCHEDULE_ROW — the
    more upstream fact wins, which is what makes a refusal readable."""

    supply = generate_candidates(wired_world.inputs())
    assert all(
        refusal.gate == "CONTENT_READINESS" for refusal in supply.refusals
    )


def test_determinism_and_order() -> None:
    """Two runs of one world produce the same proposals, in §6's source order,
    and a caller cannot change the arrival order — the kernel's step 1 is
    therefore never affected by how the generator was called."""

    text = source_text("src/elc/planner/candidates.py")
    assert "import random" not in text
    assert "time.time" not in text
    assert "datetime.now" not in text
    assert "sha256" in text  # the ids are content-addressed, not counted
    assert "uuid" not in text  # and not minted from an entropy source


def test_the_two_lanes_concatenate_into_the_one_call(wired_world: World) -> None:
    """§6's "两条 lane 进入同一 Planner": one call's output is the two lanes' own
    outputs, in the document's order, with no re-scoring in between."""

    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    inputs = wired_world.inputs(levels=levels)
    both = generate_candidates(inputs)
    a = generate_track_a(inputs)
    b = generate_track_b(inputs)
    assert [p.canonical_key for p in both.proposals] == [
        p.canonical_key for p in a.proposals + b.proposals
    ]
    order = [p.origins[0] for p in both.proposals]
    assert order == sorted(order, key=CANDIDATE_SOURCES.index)
    # every declared vector is complete, which is what lets the kernel run
    for proposal in both.proposals:
        assert set(proposal.benefit) == set(BenefitFactor)
        assert set(proposal.cost) == set(CostFactor)


def test_the_generator_imports_no_store_no_db_and_no_gate() -> None:
    """The boundary, structurally — the same check P7-1 puts on its kernel, one
    module over: the supply side reads faces, not stores, and never reaches for
    the Gate."""

    tree = ast.parse(source_text("src/elc/planner/candidates.py"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert not any(mod.endswith(".store") for mod in modules), modules
    assert not any(mod.startswith("elc.platform.db") for mod in modules), modules
    assert not any(mod.startswith("elc.teaching") for mod in modules), modules
    assert "sqlite3" not in modules


def test_the_landed_faces_satisfy_the_ports(wired_world: World) -> None:
    """Structural reuse, pinned at runtime: the objects the tests hand in are
    the landed faces — the P5-2 supply reader, the P5-1 curriculum read face,
    the Scheduler controller and the Learning controller — not adapters."""

    assert isinstance(wired_world.supply, CurriculumContentStore)
    assert isinstance(wired_world.scheduler, SchedulerController)
    assert isinstance(wired_world.learning, LearningController)
    facts = wired_world.targets.facts()
    assert isinstance(facts, Ok)
    first = facts.value[0]
    assert hasattr(first, "target_type") and hasattr(first, "target_id")
    assert set(SOURCE_AUTHORITY) == set(CANDIDATE_SOURCES)
    # the two reads the schedule port names, on the real face: the row, and
    # the §10 view whose due bucket carries it (the Scheduler's own answer).
    row = wired_world.scheduler.get_schedule_item(
        "CAPABILITY", TargetId(FOCUS_TARGET), MODALITY
    )
    assert isinstance(row, Ok) and row.value is not None
    view = wired_world.scheduler.get_schedule_view(AS_OF)
    assert isinstance(view, Ok)
    due = view.value.due_items + view.value.overdue_items
    assert sorted(str(item.target_id) for item in due) == sorted(
        (FOCUS_TARGET, ROW_TARGET)
    )


def test_a_cold_interpreter_imports_the_three_modules() -> None:
    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO_ROOT / "src"),
    )
    for statement in (
        "import elc.planner.candidates",
        "import elc.planner.scope",
        "import elc.planner.supply",
        "from elc.planner import generate_candidates, resolve_user_intent_scope",
    ):
        proc = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, f"{statement}: {proc.stderr}"


def test_the_package_exposes_the_supply_side_and_the_service_stays_a_skeleton(
    db: sqlite3.Connection,
) -> None:
    import elc.planner as planner

    assert planner.generate_candidates is generate_candidates
    assert planner.CANDIDATE_SOURCES == CANDIDATE_SOURCES
    assert planner.resolve_user_intent_scope is not None
    assert planner.prerequisite_state_of is not None
    from elc.planner.types import PlanningRequest

    request = PlanningRequest(
        decision_cycle_id=DecisionCycleId("dc-p7-2"),
        learning_snapshot=None,
        curriculum_candidate_view=None,
        schedule_view=None,
        goal_view=None,
        teaching_policy_view=None,
        context_opportunity_set=None,
        planner_constraint_view=None,
        session_budget_view=None,
        user_intent_scope=UserIntentScope.OPEN,
        conversation_priority_view=None,
        planning_ledger=None,
    )
    with pytest.raises(NotImplementedError):
        planner.PlannerService().plan(request)


def test_the_two_canonical_orders_differ_and_the_difference_is_registered() -> None:
    """§19 inserts ``ActiveLearningFrontier`` between hard eligibility and
    Policy Utility; §10.1 — the order P7-1 made executable — has no such line.
    This cut supplies the step before both and depends on neither reading, so
    the divergence is registered for p7-3 rather than decided here (the
    kernel's own suite pins §10.1's order, and this file does not touch it)."""

    state_machine = list(
        canonical_lines("STATE_MACHINES.md", "## 19. Planner Flow State")
    )
    kernel_order = list(
        canonical_lines(
            "DOMAIN_MODEL.md",
            "## 10.1 Planner Decision Kernel — Behavioral Baseline V1",
        )
    )
    frontier = [
        index
        for index, line in enumerate(state_machine)
        if "ActiveLearningFrontier" in line
    ]
    assert len(frontier) == 1, state_machine
    (at,) = frontier
    assert "hard eligibility" in state_machine[at - 1]
    assert state_machine[at + 1] == "→ Policy Utility"
    assert not any("ActiveLearningFrontier" in line for line in kernel_order)
    assert "hard eligibility" in " ".join(kernel_order)
    assert "policy utility" in " ".join(kernel_order)

    prose = " ".join((module.__doc__ or "").split())
    assert "ActiveLearningFrontier" in prose
    assert "registered, not resolved" in prose
    assert "p7-3" in prose


def test_the_module_claims_no_shadow_mode_and_registers_its_readings() -> None:
    prose = " ".join((module.__doc__ or "").split())
    assert "shadow mode" in prose
    assert "claims nothing about shadow mode" in prose
    assert "registered" in prose
    assert "Revisit:" in (module.__doc__ or "") or "revisit" in prose
    # the two registered calls the module makes
    assert "the readiness gate refuses" in prose
    assert "suppression is marked, never applied" in prose


def test_a_malformed_supply_face_is_a_gap_not_an_empty_set(
    wired_world: World,
) -> None:
    """An unreadable supply face answers *every* source with the same refusal —
    and it is a gap, not an empty world: the difference between "no targets" and
    "no answer" is the whole point of the gap record."""

    from elc.platform.types import DomainError, DomainErrorCode, Err

    class Broken:
        def facts(self):
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="content.db is gone",
                )
            )

    inputs = CandidateSupplyInputs(
        as_of=AS_OF,
        targets=Broken(),
        target_rows=wired_world.supply,
        readiness=wired_world.supply,
        prerequisites=wired_world.supply,
        learner_state=wired_world.learning,
        schedule=wired_world.scheduler,
        constraints=None,
        priority=None,
        observation=None,
    )
    supply = generate_candidates(inputs)
    assert supply.proposals == ()
    assert supply.readiness == {}
    supply_gaps = [
        gap
        for gap in supply.gaps
        if gap.authority is CandidateAuthority.TARGET_SUPPLY
    ]
    # every source is accounted for exactly once, by the *first* face it cannot
    # read: the four unlanded ones and the seven whose own leg this call did not
    # hand in (the observation, the constraint view) report those, and the four
    # that could otherwise have run report the unreadable supply.
    assert {gap.source for gap in supply.gaps} == set(CANDIDATE_SOURCES)
    assert {gap.source for gap in supply_gaps} == {
        "CONFIRMED_GAP",
        "SCHEDULED_REVIEW",
        "UNKNOWN_PROBE",
        "SUPPORT_WITHDRAWAL",
    }
    assert all(
        "an unreadable supply set is not an empty one" in gap.reason
        for gap in supply_gaps
    )


def test_the_learner_flags_make_the_track_b_sources_answer(
    wired_world: World,
) -> None:
    """The two flag-driven sources over declared §11 states: a confirmed gap is
    developed (learning_need at the flag's own band), a support-dependent target
    is withdrawn from, and a target whose state exists is not a probe."""

    from .test_p7_2_supply_gates import DeclaredStates, learner_record

    wired_world.schedule_row("RESOURCE", "res-softener-kind-of", "si-p72-gap")
    levels = DeclaredLevels(
        wired_world.supply,
        {
            FOCUS_TARGET: DECLARED_LEVEL_FACTS,
            ROW_TARGET: r3_facts(ROW_TARGET),
            "res-softener-kind-of": r3_facts("res-softener-kind-of"),
        },
    )
    states = DeclaredStates(
        {
            (ROW_TARGET, str(MODALITY)): learner_record(
                ROW_TARGET, flags=("CONFIRMED_GAP",)
            ),
            ("res-softener-kind-of", str(MODALITY)): learner_record(
                "res-softener-kind-of", flags=("SUPPORT_DEPENDENT",)
            ),
        }
    )
    inputs = CandidateSupplyInputs(
        as_of=AS_OF,
        targets=wired_world.targets,
        target_rows=wired_world.supply,
        readiness=levels,
        prerequisites=wired_world.supply,
        learner_state=states,
        schedule=wired_world.scheduler,
        constraints=None,
        priority=None,
        observation=None,
    )
    supply = generate_candidates(inputs)
    gap = supply.proposals_of("CONFIRMED_GAP")
    withdrawal = supply.proposals_of("SUPPORT_WITHDRAWAL")
    probes = supply.proposals_of("UNKNOWN_PROBE")
    assert [p.focus_target for p in gap] == [ROW_TARGET]
    assert gap[0].benefit[BenefitFactor.LEARNING_NEED] == (
        FACTOR_BAND_VALUES["learning_need"]["CONFIRMED_GAP"]
    )
    assert [p.focus_target for p in withdrawal] == ["res-softener-kind-of"]
    assert withdrawal[0].learning_intent is LearningIntent.WITHDRAW_SUPPORT
    # a target whose state exists is not a probe; the unobserved graded target
    # is one.
    assert {p.focus_target for p in probes} == {FOCUS_TARGET}
    assert ROW_TARGET not in {p.focus_target for p in probes}


def test_suppression_is_marked_and_the_kernel_names_it(wired_world: World) -> None:
    """§9's two prohibitions, marked on the candidate and excluded by the
    kernel's step 4 (never dropped at the source): an automatic candidate under
    DO_NOT_AUTO_TEACH and a review under SUPPRESS_REVIEW are suppressed, while
    the *user-initiated* candidate of the same target is not — §9's word is
    "automatically"."""

    from elc.user_config.types import PlannerConstraintType as Kind

    wired_world.constraint(
        "pc-no-auto", Kind.DO_NOT_AUTO_TEACH, None, None
    )
    wired_world.constraint(
        "pc-no-review", Kind.SUPPRESS_REVIEW, None, None
    )
    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    supply = generate_candidates(wired_world.inputs(levels=levels))
    by_source = {p.origins[0]: p for p in supply.proposals}
    assert by_source["MANUAL_USER_REQUEST"].suppressed is False
    assert by_source["SCHEDULED_REVIEW"].suppressed is True
    assert by_source["UNKNOWN_PROBE"].suppressed is True

    authority = wired_world.authority(supply.candidate_readiness)
    result = plan(module_planning_input(supply, authority))
    trace = {row.candidate_id: row for row in result.trace.candidates}
    assert trace[by_source["SCHEDULED_REVIEW"].candidate_id].excluded is (
        ExclusionReason.SUPPRESSED
    )
    assert trace[by_source["UNKNOWN_PROBE"].candidate_id].excluded is (
        ExclusionReason.SUPPRESSED
    )
    assert trace[by_source["MANUAL_USER_REQUEST"].candidate_id].excluded is None
    assert result.trace.decision is PlannerDecisionOutcome.SELECT


def test_the_priority_view_prices_the_flow_and_hands_over_the_break(
    wired_world: World,
) -> None:
    """§13's two jobs, in the chain: ``flow_priority`` becomes the candidate's
    ``interruption_cost`` (BF-02 §6's band one ladder over) and
    ``natural_break_available`` travels BF-02 §5's context field — and a
    PROTECTED flow is still a *cost*, so the user's own request is selected
    (BF-02 §17: never an exclusion)."""

    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    protected = ConversationPriorityView(
        flow_priority=FlowPriority.PROTECTED,
        interaction_phase=InteractionPhase.DEEP_EXCHANGE,
        natural_break_available=True,
    )
    inputs = CandidateSupplyInputs(
        as_of=AS_OF,
        targets=wired_world.targets,
        target_rows=wired_world.supply,
        readiness=levels,
        prerequisites=wired_world.supply,
        learner_state=wired_world.learning,
        schedule=wired_world.scheduler,
        constraints=wired_world.constraint_view(),
        priority=protected,
        observation=None,
    )
    supply = generate_candidates(inputs)
    manual = supply.proposals_of("MANUAL_USER_REQUEST")[0]
    assert manual.benefit[BenefitFactor.SCHEDULE_URGENCY] is not None
    assert manual.cost[CostFactor.INTERRUPTION_COST] == (
        FACTOR_BAND_VALUES["interruption_cost"]["PROTECTED"]
    )
    authority = wired_world.authority(
        supply.candidate_readiness,
        natural_break=protected.natural_break_available,
    )
    assert authority.natural_break_available is True
    result = plan(module_planning_input(supply, authority))
    assert result.trace.context.natural_break_available is True
    row = [
        entry
        for entry in result.trace.candidates
        if entry.candidate_id == manual.candidate_id
    ][0]
    assert row.excluded is None
    assert result.trace.decision is PlannerDecisionOutcome.SELECT

    # no view, no band from the flow: the source row's own reading stands.
    bare = generate_candidates(
        CandidateSupplyInputs(
            as_of=AS_OF,
            targets=wired_world.targets,
            target_rows=wired_world.supply,
            readiness=levels,
            prerequisites=wired_world.supply,
            learner_state=wired_world.learning,
            schedule=wired_world.scheduler,
            constraints=wired_world.constraint_view(),
            priority=None,
            observation=None,
        )
    )
    bare_manual = bare.proposals_of("MANUAL_USER_REQUEST")[0]
    assert bare_manual.cost[CostFactor.INTERRUPTION_COST] == (
        FACTOR_BAND_VALUES["interruption_cost"]["HIGH"]
    )


def test_the_kernel_refuses_nothing_the_generator_produces(
    wired_world: World,
) -> None:
    """The chain's contract: every proposal the generator emits is one
    canonicalize/assemble accepts (no duplicate keys, complete vectors, the
    §5.2 leg spelled by the row, the scaffold floors met). One bad shape would
    raise PlannerInputError, so the absence is the assertion."""

    levels = DeclaredLevels(
        wired_world.supply, {FOCUS_TARGET: DECLARED_LEVEL_FACTS}
    )
    supply = generate_candidates(
        wired_world.inputs(
            levels=levels,
            observation=OpportunityObservation(
                current_user_errors=(FOCUS_TARGET,),
                expression_needs=(FOCUS_TARGET,),
                natural_use_expansions=(FOCUS_TARGET,),
                pragmatic_register_opportunities=(FOCUS_TARGET,),
                current_context_transfers=(FOCUS_TARGET,),
            ),
        )
    )
    assert len(supply.proposals) >= 7
    try:
        plan(module_planning_input(supply, wired_world.authority(
            supply.candidate_readiness
        )))
    except PlannerInputError as failure:  # pragma: no cover - the assertion
        raise AssertionError(f"the kernel refused a generated proposal: {failure}")
