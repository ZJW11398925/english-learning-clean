"""P7-1 ③ — the kernel over the real faces: P7-0's record, the Scheduler's own
rows and watermark, the real User Configuration rows, and today's honest
answer on the shipped supply.

The world here is the shipped chain — migrations applied to an in-memory
app.db, an opened runtime epoch, the real Scheduler / User Configuration /
Learning faces over it, and the content.db this repository's authoring trees
build. One input is *declared* rather than read, and it says so where it is
used: a candidate's **content level**. The corpus reports ``None`` for every
target (P7-0's own suite pins that), so a test that wants the *decision* path
rather than the degraded one declares the level the content side will report
when its work lands. Everything else about the assembly is a real read — the
kernel derives none of the four §5 names, the profile, the policy version or
the schedule authority, which is what these pins hold it to.
"""

from __future__ import annotations

import ast
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from elc.curriculum.readiness import judge_readiness
from elc.learning.controller import LearningController
from elc.planner import kernel
from elc.planner.feature_assembly import (
    AuthorityName,
    assemble_feature_authority,
)
from elc.planner.kernel import (
    AUTHORITY_ASSEMBLED_FACTORS,
    PLANNER_PROFILE_VERSION,
    BenefitFactor,
    DegradedReason,
    FactorSource,
    PlannerInputError,
    plan,
)
from elc.planner.types import (
    PlannerDecisionOutcome,
    PlanningRequest,
    UserIntentScope,
)
from elc.platform.types import DecisionCycleId, Ok
from elc.scheduler.authority import ScheduleCurrency, currency_of
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import ReviewState, SpacingStage
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import TeachingFrequency

from .conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    TARGET_ID,
    USER,
    benefit_vector,
    complete_context,
    constraint,
    cost_vector,
    kernel_input,
    learning_snapshot,
    portfolio,
    proposal,
    schedule_item,
    source_text,
    teaching_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The instant the real view is asked about, and the window that makes the
#: row land in its due bucket (the phase-7 suite's own three instants).
DUE_WINDOW = (DAY_ONE, DAY_THREE)
ROW_ID = "si-p7-1-real"
DECLARED_LEVEL = "R3_TEACHING_READY"


def _due_row(
    item_id: str = ROW_ID,
    *,
    urgency: float | None = 0.75,
    watermark: str = "0",
):
    """A §5.2 row a caller decided, written through the store's write face."""

    return schedule_item(
        item_id,
        review_state=ReviewState.DUE,
        urgency=urgency,
        window_start=DUE_WINDOW[0],
        window_end=DUE_WINDOW[1],
        stage=SpacingStage.STAGE_1,
        watermark=watermark,
        version=f"sv-{item_id}",
    )


def _real_world(
    store: SqliteUserConfigStore,
    controller: UserConfigController,
    learning: LearningController,
    scheduler: SqliteSchedulerStore,
    *,
    frequency: TeachingFrequency = TeachingFrequency.BALANCED,
    row=None,
):
    """Real §5.1/§5.2/§9 rows, read back through the real faces."""

    assert isinstance(
        store.upsert_teaching_policy(teaching_policy(frequency=frequency)), Ok
    )
    assert isinstance(
        store.upsert_goal_portfolio(portfolio(assessment_targets=())), Ok
    )
    assert isinstance(store.record_planner_constraint(constraint()), Ok)
    written = row if row is not None else _due_row()
    assert isinstance(scheduler.upsert_schedule_item(written), Ok)

    policy = controller.get_teaching_policy(USER)
    goals = controller.get_goal_portfolio(USER)
    constraints = controller.get_planner_constraint_view(DAY_TWO, CONV)
    watermark = learning.get_learning_watermark()
    view = SchedulerController(scheduler, learning=learning).get_schedule_view(
        DAY_TWO
    )
    assert isinstance(policy, Ok) and policy.value is not None
    assert isinstance(goals, Ok) and goals.value is not None
    assert isinstance(constraints, Ok)
    assert isinstance(watermark, Ok)
    assert isinstance(view, Ok)
    return policy.value, goals.value, watermark.value, view.value


def _table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    return {
        name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in names
    }


# -- ① today's honest answer on the shipped supply ---------------------------


def test_the_real_chain_degrades_while_thirteen_targets_stay_ungraded(
    db: sqlite3.Connection,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    scheduler_store: SqliteSchedulerStore,
    content_supply,
) -> None:
    """Real durable rows, real read faces, the real corpus — and a Planner
    that may not proceed. The gap narrowed with C1 (旧真值: the corpus graded
    nothing — 14 ungraded candidates; 新真值: it grades one target R4 and
    leaves thirteen ungraded), but the kernel's answer is the same: it
    degrades instead of inventing a number or a NO_TARGET, because an
    ungraded candidate's eligibility cannot be judged."""

    policy, goals, watermark, view = _real_world(
        user_config_store,
        user_config_controller,
        learning_controller,
        scheduler_store,
    )
    assert view.due_items, "the row was not read back"

    levels: dict[str, str | None] = {}
    entity_ids = content_supply.supply_entity_ids()
    assert isinstance(entity_ids, Ok)
    assert entity_ids.value, "the shipped supply is empty — nothing asserted"
    for entity_id in entity_ids.value:
        facts = content_supply.readiness_facts(str(entity_id))
        assert isinstance(facts, Ok)
        levels[str(entity_id)] = judge_readiness(facts.value).level
    assert levels["res-colloc-make-a-decision"] == "R4_DETECTION_READY"
    assert sum(1 for level in levels.values() if level is None) == 13

    authority = assemble_feature_authority(
        learning_snapshot=learning_snapshot(watermark),
        current_learning_watermark=watermark,
        schedule_view=view,
        teaching_policy=policy,
        goal_portfolio=goals,
        curriculum_readiness=levels,
        constraint_view_present=True,
    )
    real_row = view.due_items[0]
    result = plan(
        kernel_input(
            (
                proposal(
                    "c-real",
                    schedule_urgency=real_row.review_urgency,
                    schedule_row=real_row,
                ),
            ),
            context=authority,
        )
    )
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )
    assert result.outcome.decision is None
    assert result.trace.decision is None
    assert result.trace.candidates[0].utility is None
    assert result.trace.context.schedule_authority is not None
    reasons = "\n".join(result.trace.context.reasons)
    assert "no content level is reachable" in reasons
    # 旧真值: "14 candidate(s)" → 新真值 (C1): the one graded target leaves
    # the note's count at the thirteen still-ungraded candidates.
    assert "13 candidate(s)" in reasons
    assert AuthorityName.CURRICULUM_READINESS in (
        result.trace.context.missing_authorities
    )
    assert AuthorityName.SCHEDULE not in result.trace.context.missing_authorities


def test_a_real_row_is_what_the_schedule_factor_comes_from(
    db: sqlite3.Connection,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """The declared content level is the one input that is not read (module
    docstring); with it, a real §5.2 row, a real policy and a real watermark
    are enough for the kernel to decide — and the schedule reading is the
    Scheduler's own number, not the caller's."""

    policy, goals, watermark, view = _real_world(
        user_config_store,
        user_config_controller,
        learning_controller,
        scheduler_store,
    )
    real_row = view.due_items[0]
    assert real_row.review_urgency == 0.75

    authority = assemble_feature_authority(
        learning_snapshot=learning_snapshot(watermark),
        current_learning_watermark=watermark,
        schedule_view=view,
        teaching_policy=policy,
        goal_portfolio=goals,
        curriculum_readiness={str(TARGET_ID): DECLARED_LEVEL},
        constraint_view_present=True,
    )
    assert authority.complete

    result = plan(
        kernel_input(
            (
                proposal(
                    "c-real",
                    schedule_urgency=real_row.review_urgency,
                    schedule_row=real_row,
                ),
            ),
            context=authority,
        )
    )
    assert result.trace.decision is PlannerDecisionOutcome.SELECT
    readings = result.trace.candidates[0].benefit
    schedule = [
        reading
        for reading in readings
        if reading.factor is BenefitFactor.SCHEDULE_URGENCY
    ][0]
    assert schedule.value == real_row.review_urgency
    assert schedule.source is FactorSource.AUTHORITY
    assert currency_of(real_row, watermark) is ScheduleCurrency.CURRENT


def test_a_real_row_at_another_watermark_is_stale_and_degrades(
    db: sqlite3.Connection,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """The same world with one number moved: the row records a watermark the
    Learning face does not report, so the authority is STALE — and the
    declared reading is refused rather than used."""

    current = learning_controller.get_learning_watermark()
    assert isinstance(current, Ok)
    policy, goals, watermark, view = _real_world(
        user_config_store,
        user_config_controller,
        learning_controller,
        scheduler_store,
        row=_due_row(watermark=str(current.value + 1)),
    )
    real_row = view.due_items[0]
    assert currency_of(real_row, watermark) is ScheduleCurrency.STALE

    authority = assemble_feature_authority(
        learning_snapshot=learning_snapshot(watermark),
        current_learning_watermark=watermark,
        schedule_view=view,
        teaching_policy=policy,
        goal_portfolio=goals,
        curriculum_readiness={str(TARGET_ID): DECLARED_LEVEL},
        constraint_view_present=True,
    )
    result = plan(
        kernel_input(
            (
                proposal(
                    "c-real",
                    schedule_urgency=real_row.review_urgency,
                    schedule_row=real_row,
                ),
            ),
            context=authority,
        )
    )
    (row,) = result.trace.candidates
    (gap,) = row.gaps
    assert gap.factor is BenefitFactor.SCHEDULE_URGENCY
    assert "stale" in gap.reason
    assert result.outcome.execution_status.error_code == (
        DegradedReason.FEATURE_ASSEMBLY_INCOMPLETE.value
    )
    assert result.outcome.decision is None


# -- ② the profile and the version come from P7-0 ----------------------------


@pytest.mark.parametrize(
    ("frequency", "profile", "threshold", "automatic"),
    [
        pytest.param(
            TeachingFrequency.OFF, "LOUNGE", 0.36, False, id="off"
        ),
        pytest.param(
            TeachingFrequency.MINIMAL, "LOUNGE", 0.36, True, id="minimal"
        ),
        pytest.param(
            TeachingFrequency.BALANCED, "BALANCED", 0.195, True, id="balanced"
        ),
        pytest.param(
            TeachingFrequency.EAGER, "STUDY_FIRST", 0.18, True, id="eager"
        ),
    ],
)
def test_the_profile_comes_from_the_real_policy_row(
    db: sqlite3.Connection,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    scheduler_store: SqliteSchedulerStore,
    frequency: TeachingFrequency,
    profile: str,
    threshold: float,
    automatic: bool,
) -> None:
    """P7-0's mapping is the only place §5.1's implementation-declared
    frequency becomes a BF-02 profile word, and the kernel reads the profile
    and the threshold from that record rather than deciding either itself."""

    policy, goals, watermark, view = _real_world(
        user_config_store,
        user_config_controller,
        learning_controller,
        scheduler_store,
        frequency=frequency,
    )
    authority = assemble_feature_authority(
        learning_snapshot=learning_snapshot(watermark),
        current_learning_watermark=watermark,
        schedule_view=view,
        teaching_policy=policy,
        goal_portfolio=goals,
        curriculum_readiness={str(TARGET_ID): DECLARED_LEVEL},
        constraint_view_present=True,
    )
    assert authority.complete
    assert authority.planner_profile is not None
    assert authority.planner_profile.value == profile
    assert authority.automatic_teaching_enabled is automatic

    real_row = view.due_items[0]
    result = plan(
        kernel_input(
            (
                proposal(
                    "c-real",
                    schedule_urgency=real_row.review_urgency,
                    schedule_row=real_row,
                ),
            ),
            context=authority,
        )
    )
    assert result.trace.context.planner_profile.value == profile
    assert result.trace.candidates[0].activation_threshold == threshold
    assert result.trace.context.automatic_teaching_enabled is automatic
    assert result.trace.context.policy_mapping_version == (
        authority.policy_mapping_version
    )
    assert result.outcome.evaluation.policy_version == PLANNER_PROFILE_VERSION


def test_the_mapping_version_travels_from_p7_0_to_the_trace() -> None:
    """One version field, read from the record the assembly built — the trace
    can be dated without asking which mapping the caller used."""

    context = complete_context()
    result = plan(kernel_input((proposal("c1"),), context=context))
    assert result.trace.context.policy_mapping_version == (
        context.policy_mapping_version
    )
    assert result.trace.context.policy_mapping_version is not None


# -- ③ what the kernel does not read -----------------------------------------


def test_a_protected_interruption_cost_is_a_cost_and_not_a_gate() -> None:
    """BF-02 §17: the Planner may SELECT even when a later Gate hard state will
    DENY — "interruption_cost = PROTECTED/high" is a large cost, not a
    prohibition, and the Planner keeps no second pedagogy ranking.

    BF-02's own example is the study-first profile, and the arithmetic is its:
    benefit 0.17 + 0.13 + 0.12 + 0.08 × 0.75 = 0.48, cost 0.40 × 1.0 = 0.40,
    utility 0.48 − 0.55 × 0.40 = 0.26 against a 0.18 threshold.
    """

    context = complete_context(
        teaching_policy=teaching_policy(frequency=TeachingFrequency.EAGER)
    )
    result = plan(
        kernel_input(
            (
                proposal(
                    "high",
                    benefit=benefit_vector(
                        learning_need=1.0,
                        context_fit=1.0,
                        communicative_impact=1.0,
                    ),
                    cost=cost_vector(interruption_cost=1.0),
                ),
            ),
            context=context,
        )
    )
    row = result.trace.candidates[0]
    assert row.excluded is None
    assert row.cost_score == pytest.approx(0.40)
    assert row.activated is True
    assert result.trace.decision is PlannerDecisionOutcome.SELECT


def test_the_kernel_imports_neither_the_gate_nor_a_store() -> None:
    """The boundary, structurally: no Gate package (BF-02 §17 — the Planner
    does not re-rank for the Gate), no durable store and no DB module."""

    tree = ast.parse(source_text("src/elc/planner/kernel.py"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert not any(module.startswith("elc.teaching") for module in modules)
    assert not any(module.startswith("elc.platform.db") for module in modules)
    assert not any(module.endswith(".store") for module in modules)
    assert "sqlite3" not in modules


def test_the_authority_assembled_factors_are_the_two_p7_0_legs(
    db: sqlite3.Connection,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """Which factors a real run read from an authority, and which it took from
    the candidate: today exactly ``schedule_urgency`` is authority-sourced —
    the goal leg answers UNKNOWN until its mapping lands, and the other
    fourteen are upstream readings."""

    policy, goals, watermark, view = _real_world(
        user_config_store,
        user_config_controller,
        learning_controller,
        scheduler_store,
    )
    authority = assemble_feature_authority(
        learning_snapshot=learning_snapshot(watermark),
        current_learning_watermark=watermark,
        schedule_view=view,
        teaching_policy=policy,
        goal_portfolio=goals,
        curriculum_readiness={str(TARGET_ID): DECLARED_LEVEL},
        constraint_view_present=True,
    )
    real_row = view.due_items[0]
    result = plan(
        kernel_input(
            (
                proposal(
                    "c-real",
                    schedule_urgency=real_row.review_urgency,
                    schedule_row=real_row,
                ),
            ),
            context=authority,
        )
    )
    (row,) = result.trace.candidates
    from_authority = {
        reading.factor
        for reading in (*row.benefit, *row.cost)
        if reading.source is FactorSource.AUTHORITY
    }
    assert from_authority == {BenefitFactor.SCHEDULE_URGENCY}
    assert BenefitFactor.SCHEDULE_URGENCY in AUTHORITY_ASSEMBLED_FACTORS
    assert BenefitFactor.GOAL_RELEVANCE in AUTHORITY_ASSEMBLED_FACTORS
    assert len(AUTHORITY_ASSEMBLED_FACTORS) == 2


def test_the_kernel_writes_nothing_to_the_database(
    db: sqlite3.Connection,
    learning_controller: LearningController,
    user_config_store: SqliteUserConfigStore,
    user_config_controller: UserConfigController,
    scheduler_store: SqliteSchedulerStore,
) -> None:
    """A real world, a full run, and the durable state unchanged: the kernel
    answers, and no cut in this phase has landed a planner write face."""

    policy, goals, watermark, view = _real_world(
        user_config_store,
        user_config_controller,
        learning_controller,
        scheduler_store,
    )
    authority = assemble_feature_authority(
        learning_snapshot=learning_snapshot(watermark),
        current_learning_watermark=watermark,
        schedule_view=view,
        teaching_policy=policy,
        goal_portfolio=goals,
        curriculum_readiness={str(TARGET_ID): DECLARED_LEVEL},
        constraint_view_present=True,
    )
    before = _table_counts(db)
    assert before, "the schema is empty — nothing asserted"
    real_row = view.due_items[0]
    for scope in (UserIntentScope.OPEN, UserIntentScope.JUST_CHAT):
        plan(
            kernel_input(
                (
                    proposal(
                        "c-real",
                        schedule_urgency=real_row.review_urgency,
                        schedule_row=real_row,
                    ),
                ),
                context=authority,
                scope=scope,
            )
        )
    assert _table_counts(db) == before


def test_a_cold_interpreter_imports_the_kernel() -> None:
    """The P4-3 lesson at its strongest: a fresh interpreter importing the new
    module first must succeed — an import cycle can hide behind a lucky
    test-session order, and this cut adds a cross-package reference
    (``elc.planner.kernel`` → ``elc.planner.feature_assembly``)."""

    env = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(REPO_ROOT / "src"),
    )
    for statement in (
        "import elc.planner.kernel",
        "from elc.planner.kernel import plan",
        "import elc.planner",
        "from elc.planner import KERNEL_STEP_ORDER, plan as planner_plan",
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


def test_the_validated_input_error_names_the_contract() -> None:
    """The error the kernel raises is the module's own, and it is a
    ``ValueError``: a caller can catch one class for every contract breach
    (BF-02 §4's duplicate key through §20's vector)."""

    assert issubclass(PlannerInputError, ValueError)
    with pytest.raises(PlannerInputError):
        plan(kernel_input((proposal("c1", benefit={}),)))


def test_the_service_is_still_a_skeleton_and_the_package_exposes_the_kernel(
    db: sqlite3.Connection,
) -> None:
    """P7-1's own scope claim: the kernel exists and is reachable through the
    package, the service is still the Phase 0 skeleton, and nothing here claims
    shadow mode."""

    import elc.planner as planner

    assert planner.plan is kernel.plan
    assert planner.KERNEL_STEP_ORDER == kernel.KERNEL_STEP_ORDER
    request = PlanningRequest(
        decision_cycle_id=DecisionCycleId("dc-p7-1"),
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

