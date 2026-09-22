"""Phase 7 tests — the P7-0 consumption boundary.

The world here is the shipped chain and nothing else: migrations applied to an
in-memory app.db, an opened runtime epoch, the real Scheduler / User
Configuration / Learning authority faces over it, and — for the one test that
needs content — the content.db built from this repository's authoring trees.
No ``_seed``-shaped helper exists here and no fixture target provider is
imported (the P5-1 red line, kept by phase 6 and kept again here).

The builders are re-declared rather than imported from tests/phase6/conftest:
they are this suite's own inputs, and a phase's assertions should not ride on
another phase's fixture module (the phase-6 conftest's reason, applied one
phase on).
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Mapping, Sequence

import pytest

from elc.content.build import build_content_db
from elc.content.store import ContentStore
from elc.conversation import SqliteConversationStore
from elc.curriculum.store import CurriculumContentStore
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.learning.types import LearningSnapshot, LearningSnapshotId
from elc.planner.feature_assembly import FeatureAuthority, assemble_feature_authority
from elc.planner.kernel import (
    BENEFIT_FACTORS,
    COST_FACTORS,
    BenefitFactor,
    CandidateProposal,
    CostFactor,
    PlanningInput,
)
from elc.planner.types import (
    InitiativeClass,
    LearningIntent,
    TargetMode,
    UserIntentScope,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ConversationId as ConvId,
)
from elc.platform.types import (
    DecisionCycleId,
    EvidenceModality,
    GoalId,
    GoalModality,
    GoalVersion,
    Ok,
    PolicyVersion,
    ScheduleVersion,
    TargetId,
    UserId,
)
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    ScheduleView,
    SpacingStage,
)
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from tests.conftest import REPO_ROOT

DOCS_ROOT = REPO_ROOT / "docs"
BASELINES = REPO_ROOT / "behavioral_baselines"

#: One fixed world: a conversation, a user, and one real corpus target
#: (``res-hedge-i-think``, content_src/index.json — the same target phase 6
#: schedules, so a schedule row written here points at a target the shipped
#: supply also knows).
CONV = ConvId("conv-p7-0")
OTHER_CONV = ConvId("conv-p7-0-other")
USER = UserId("user-p7-0")
TARGET_TYPE = "RESOURCE"
TARGET_ID = TargetId("res-hedge-i-think")
MODALITY = EvidenceModality.TEXT_PRODUCTION
OTHER_MODALITY = EvidenceModality.TEXT_COMPREHENSION

#: Three instants a day apart, so an inclusive boundary and an exclusive one
#: cannot answer alike, plus the two ISO-8601 spellings of **one** instant
#: (``+08:00`` and ``Z``) that the instant/byte-order split turns on.
DAY_ONE = "2026-09-22T09:00:00+00:00"
DAY_TWO = "2026-09-23T09:00:00+00:00"
DAY_THREE = "2026-09-24T09:00:00+00:00"
OFFSET_SPELLING = "2026-09-22T17:00:00+08:00"
SAME_INSTANT_UTC = "2026-09-22T09:00:00+00:00"

#: The five minutes after ``DAY_ONE``, used where "strictly inside" matters.
DAY_ONE_PLUS = "2026-09-22T09:05:00+00:00"

CONSTRAINT_ID = "pc-p7-0"

#: The Learning watermark the P7-1 kernel suite assembles its complete
#: contexts at, and the spelling every §5.2 row it builds carries — one
#: watermark, so the schedule authority reads CURRENT unless a test makes it
#: stale on purpose.
WATERMARK = 3
WATERMARK_SPELLING = "3"

__all__ = [
    "BASELINES",
    "CONSTRAINT_ID",
    "CONV",
    "DAY_ONE",
    "DAY_ONE_PLUS",
    "DAY_THREE",
    "DAY_TWO",
    "DOCS_ROOT",
    "MODALITY",
    "OFFSET_SPELLING",
    "OTHER_CONV",
    "OTHER_MODALITY",
    "SAME_INSTANT_UTC",
    "TARGET_ID",
    "TARGET_TYPE",
    "USER",
    "WATERMARK",
    "WATERMARK_SPELLING",
    "baseline_lines",
    "benefit_vector",
    "canonical_lines",
    "complete_context",
    "constraint",
    "content_supply",
    "conversations",
    "cost_vector",
    "db",
    "document_text",
    "fence",
    "focus",
    "instant",
    "kernel_input",
    "kernel_row",
    "learning_controller",
    "learning_snapshot",
    "portfolio",
    "proposal",
    "review_event",
    "rowless_proposal",
    "schedule_item",
    "scheduler_controller",
    "scheduler_store",
    "source_text",
    "teaching_policy",
    "user_config_controller",
    "user_config_store",
    "wired_scheduler",
]


# -- the world ---------------------------------------------------------------


@pytest.fixture()
def db() -> Iterator[sqlite3.Connection]:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture()
def fence(db: sqlite3.Connection) -> RuntimeEpochFence:
    return epoch.open_runtime_epoch(db)


@pytest.fixture()
def scheduler_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteSchedulerStore:
    return SqliteSchedulerStore(db, fence)


@pytest.fixture()
def scheduler_controller(
    scheduler_store: SqliteSchedulerStore,
) -> SchedulerController:
    """The Scheduler face with **no** Learning port: every durable read works
    and the currency handshake refuses (its own test)."""

    return SchedulerController(scheduler_store)


@pytest.fixture()
def learning_controller(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> LearningController:
    return LearningController(SqliteLearningStore(db, fence))


@pytest.fixture()
def wired_scheduler(
    scheduler_store: SqliteSchedulerStore,
    learning_controller: LearningController,
) -> SchedulerController:
    """The Scheduler face wired to the real Learning watermark read."""

    return SchedulerController(scheduler_store, learning=learning_controller)


@pytest.fixture()
def user_config_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteUserConfigStore:
    return SqliteUserConfigStore(db, fence)


@pytest.fixture()
def user_config_controller(
    user_config_store: SqliteUserConfigStore,
) -> UserConfigController:
    return UserConfigController(user_config_store)


@pytest.fixture()
def conversations(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> tuple[ConvId, ConvId]:
    """The two conversations this suite writes focuses for.

    §5.1 gives ``SessionFocus`` a real ``conversation_id`` foreign key
    (migration 0011), so a focus cannot be written into a world where the
    conversation does not exist — the durable chain decides that, not a
    fixture shortcut.
    """

    store = SqliteConversationStore(db, fence)
    for conversation in (CONV, OTHER_CONV):
        result = store.open_conversation(
            conversation, user_id=USER, persona_id=None, scene_id=None
        )
        assert isinstance(result, Ok), result
    return (CONV, OTHER_CONV)


@pytest.fixture(scope="session")
def built_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The repository's content.db, built once for the whole session."""

    output = tmp_path_factory.mktemp("p7-0-content") / "content.db"
    build_content_db(output)
    return output


@pytest.fixture()
def content_supply(built_content_db: Path) -> Iterator[CurriculumContentStore]:
    """The curriculum-side read face over the session's built content.db."""

    supply = CurriculumContentStore(ContentStore(built_content_db))
    yield supply
    supply.close()


# -- the builders ------------------------------------------------------------


def schedule_item(
    item_id: str = "si-p7-0",
    *,
    target_type: str = TARGET_TYPE,
    target_id: TargetId = TARGET_ID,
    modality: EvidenceModality = MODALITY,
    review_state: ReviewState = ReviewState.UPCOMING,
    urgency: float | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    stage: SpacingStage | None = None,
    watermark: str = "0",
    version: str = "sv-1",
) -> ScheduleItem:
    """One §5.2 ScheduleItem; ``watermark`` is a decimal spelling on purpose
    (R6), so a caller can make a row current or stale by arithmetic on the
    number it read."""

    return ScheduleItem(
        schedule_item_id=item_id,
        target_type=target_type,
        target_id=target_id,
        evidence_modality=modality,
        review_state=review_state,
        review_urgency=urgency,
        next_review_window_start=window_start,
        next_review_window_end=window_end,
        spacing_stage=stage,
        source_learning_watermark=watermark,
        version=ScheduleVersion(version),
    )


def review_event(
    event_id: str = "re-p7-0",
    *,
    schedule_item_id: str = "si-p7-0",
    engaged: bool = True,
    created_at: str = "",
) -> ReviewEvent:
    return ReviewEvent(
        review_event_id=event_id,
        schedule_item_id=schedule_item_id,
        event_type="RECALL_ATTEMPT",
        engaged=engaged,
        created_at=created_at,
    )


def focus(
    focus_id: str = "sf-p7-0",
    *,
    conversation: ConvId = CONV,
    base_version: str = "gv-1",
    starts_at: str = DAY_ONE,
    expires_at: str | None = None,
    target: str | None = None,
) -> SessionFocus:
    return SessionFocus(
        session_focus_id=focus_id,
        conversation_id=conversation,
        base_goal_portfolio_version=GoalVersion(base_version),
        temporary_goal_weights={GoalModality.SPEAKING: 1.0},
        manual_focus_target=None if target is None else TargetId(target),
        starts_at=starts_at,
        expires_at=expires_at,
    )


def constraint(
    constraint_id: str = CONSTRAINT_ID,
    *,
    constraint_type: PlannerConstraintType = (
        PlannerConstraintType.DO_NOT_AUTO_TEACH
    ),
    scope: PlannerConstraintScope = PlannerConstraintScope.UNTIL_DATE,
    target_type: str | None = None,
    target_id: TargetId | None = None,
    starts_at: str = DAY_ONE,
    expires_at: str | None = DAY_THREE,
    active: bool = True,
) -> PlannerConstraint:
    """One §9 constraint; every leg is a parameter, so the half-declared
    shapes are constructible without a second builder."""

    return PlannerConstraint(
        constraint_id=constraint_id,
        target_type=target_type,
        target_id=target_id,
        constraint_type=constraint_type,
        scope=scope,
        starts_at=starts_at,
        expires_at=expires_at,
        active=active,
    )


def portfolio(
    *,
    user_id: UserId = USER,
    version: str = "gv-1",
    assessment_targets: tuple[str, ...] = ("ielts-speaking",),
) -> LearningGoalPortfolio:
    return LearningGoalPortfolio(
        goal_portfolio_id=user_id,
        goal_version=GoalVersion(version),
        goals=(
            LearningGoal(
                goal_id=GoalId("goal-1"),
                goal_modality=GoalModality.SPEAKING,
                description="a long-term goal",
            ),
        ),
        modality_weights={GoalModality.SPEAKING: 1.0},
        assessment_targets=assessment_targets,
        effective_from=DAY_ONE,
    )


def teaching_policy(
    *,
    user_id: UserId = USER,
    version: str = "pv-1",
    frequency: TeachingFrequency = TeachingFrequency.BALANCED,
) -> TeachingPolicyProfile:
    return TeachingPolicyProfile(
        teaching_policy_profile_id=user_id,
        policy_version=PolicyVersion(version),
        teaching_frequency=frequency,
    )


def instant(text: str) -> datetime:
    """One instant, parsed — the tests compare instants, never bytes."""

    return datetime.fromisoformat(text).astimezone(UTC)


# ---------------------------------------------------------------------------
# The P7-1 kernel's inputs
# ---------------------------------------------------------------------------
#
# The kernel's input contract is BF-02's frozen one: a canonical candidate set
# carrying **complete normalized factor vectors** (§20), plus §5's
# PlanningContext. These builders spell a complete vector first and let a test
# override a single factor, so a test that means to move one number cannot
# accidentally leave another one missing — and the two §5.2 shapes (a row that
# answers, and no row at all) are two named builders rather than a sentinel.

#: Every factor at zero, overridden by name (``learning_need=1.0``).
def benefit_vector(**overrides: float) -> dict[BenefitFactor, float]:
    vector = {factor: 0.0 for factor in BENEFIT_FACTORS}
    for name, value in overrides.items():
        vector[BenefitFactor(name)] = value
    return vector


def cost_vector(**overrides: float) -> dict[CostFactor, float]:
    vector = {factor: 0.0 for factor in COST_FACTORS}
    for name, value in overrides.items():
        vector[CostFactor(name)] = value
    return vector


#: The vector the builders declare by default: learning_need at HIGH and
#: context_fit at DIRECT, which is 0.17 × 0.75 + 0.13 × 1.0 = 0.2575 under
#: BALANCED — above §14's 0.195 threshold, so the default proposal is one a
#: successful run can actually select. A test that wants a candidate below the
#: threshold passes its own vector rather than mutating this one.
DEFAULT_BENEFIT: Mapping[BenefitFactor, float] = benefit_vector(
    learning_need=0.75, context_fit=1.0
)


def kernel_row(
    item_id: str = "si-p7-1",
    *,
    state: ReviewState = ReviewState.DUE,
    urgency: float | None = 0.75,
    watermark: str = WATERMARK_SPELLING,
) -> ScheduleItem:
    """The §5.2 row a candidate names — the leg ``schedule_urgency`` reads."""

    return schedule_item(
        item_id,
        review_state=state,
        urgency=urgency,
        watermark=watermark,
    )


def learning_snapshot(watermark: int = WATERMARK) -> LearningSnapshot:
    """One §12 snapshot; the assembly reads its ``evidence_watermark``."""

    return LearningSnapshot(
        learning_snapshot_id=LearningSnapshotId("ls-p7-1"),
        user_scope_id=str(USER),
        as_of=DAY_TWO,
        estimator_version="est-v1",
        evidence_watermark=watermark,
        targets=(),
    )


def schedule_view(*rows: ScheduleItem) -> ScheduleView:
    """A §10 view holding the rows a test built (due bucket by default)."""

    return ScheduleView(
        schedule_version="sd1",
        as_of=DAY_TWO,
        due_items=tuple(rows),
        overdue_items=(),
        upcoming=(),
    )


def complete_context(**overrides: object) -> FeatureAuthority:
    """P7-0's record with every BF-02 §5 leg present and usable.

    Assembled by the real :func:`elc.planner.feature_assembly.
    assemble_feature_authority` over the real view shapes, so a caller gets
    ``COMPLETE`` / ``VALID`` and the BALANCED profile — and an override that
    makes one leg unusable goes through the same function P7-0's own suite
    exercises.
    """

    bag: dict[str, object] = {
        "learning_snapshot": learning_snapshot(),
        "current_learning_watermark": WATERMARK,
        "schedule_view": schedule_view(kernel_row()),
        "teaching_policy": teaching_policy(),
        "goal_portfolio": portfolio(assessment_targets=()),
        "curriculum_readiness": {str(TARGET_ID): "R3_TEACHING_READY"},
        "constraint_view_present": True,
    }
    bag.update(overrides)
    return assemble_feature_authority(**bag)  # type: ignore[arg-type]


def proposal(
    candidate_id: str = "c-p7-1",
    *,
    canonical_key: str | None = None,
    benefit: Mapping[BenefitFactor, float] | None = None,
    cost: Mapping[CostFactor, float] | None = None,
    schedule_urgency: float = 0.75,
    schedule_row: ScheduleItem | None = None,
    **fields: object,
) -> CandidateProposal:
    """One proposal whose ``schedule_urgency`` a §5.2 row spells.

    The declared reading and the row agree by construction (both take
    ``schedule_urgency``), which is the shape the kernel accepts; a test that
    wants the two to disagree passes ``schedule_row`` explicitly, and one that
    wants the Scheduler-never-asked case uses :func:`rowless_proposal`. A
    keyword in ``fields`` replaces the default of the same name, so a test can
    move one identity field without restating the rest.
    """

    vector = dict(benefit if benefit is not None else DEFAULT_BENEFIT)
    vector[BenefitFactor.SCHEDULE_URGENCY] = schedule_urgency
    defaults: dict[str, object] = {
        "canonical_key": candidate_id if canonical_key is None else canonical_key,
        "focus_target": str(TARGET_ID),
        "target_mode": TargetMode.RESOURCE_PRACTICE,
        "learning_intent": LearningIntent.DEVELOP,
        "evidence_modality": MODALITY,
        "opportunity_binding_class": "ob-p7-1",
        "initiative_class": InitiativeClass.REACTIVE,
        "benefit": vector,
        "cost": dict(cost if cost is not None else cost_vector()),
        "schedule_row": (
            kernel_row(urgency=schedule_urgency)
            if schedule_row is None
            else schedule_row
        ),
    }
    defaults.update(fields)
    return CandidateProposal(candidate_id=candidate_id, **defaults)  # type: ignore[arg-type]


def rowless_proposal(
    candidate_id: str = "c-p7-1", **fields: object
) -> CandidateProposal:
    """The same proposal with **no** §5.2 row: the Scheduler was never asked.

    A different shape rather than a sentinel — P7-0 reads this one as UNKNOWN
    ("a target with no row is a target the Scheduler was never asked about"),
    and it is the reachable candidate-level gap under a COMPLETE context.
    """

    return replace(
        proposal(candidate_id, **fields),  # type: ignore[arg-type]
        schedule_row=None,
    )


#: Marks "no context at all" in :func:`kernel_input` (``None`` is a value
#: there: a caller who could not assemble a context hands the kernel None).
_NO_CONTEXT: object = object()


def kernel_input(
    proposals: Sequence[CandidateProposal] = (),
    *,
    context: object = _NO_CONTEXT,
    scope: UserIntentScope = UserIntentScope.OPEN,
    cycle: str = "dc-p7-1",
) -> PlanningInput:
    """One kernel input: the proposals, a context, and the scope word.

    The context defaults to :func:`complete_context` — the *inputs* are
    synthetic here, exactly as BF-02 §20's frozen contract describes them, and
    the faces that produce them are the later cuts' work.
    """

    return PlanningInput(
        decision_cycle_id=DecisionCycleId(cycle),
        planning_context=(
            complete_context() if context is _NO_CONTEXT else context  # type: ignore[arg-type]
        ),
        user_intent_scope=scope,
        proposals=tuple(proposals),
    )


# ---------------------------------------------------------------------------
# Canonical-document reader (re-declared: this suite's own extraction pins)
# ---------------------------------------------------------------------------

_FENCE = "```"


def _fenced_blocks(text: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block after ``heading``, blank lines dropped."""

    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"heading {heading!r} not found"
    blocks: list[tuple[str, ...]] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level and stripped[: head_level + 1].endswith(" "):
                break
        if lines[index].startswith(_FENCE):
            body: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith(_FENCE):
                if lines[index].strip():
                    body.append(lines[index].strip())
                index += 1
            if body:
                blocks.append(tuple(body))
        index += 1
    assert blocks, f"{heading!r}: no fenced block"
    return blocks


def canonical_lines(doc: str, heading: str, block: int = 0) -> tuple[str, ...]:
    """The ``block``-th fenced block after ``heading`` in ``docs/<doc>``."""

    blocks = _fenced_blocks(
        (DOCS_ROOT / doc).read_text(encoding="utf-8"), heading
    )
    assert len(blocks) > block, f"{doc} {heading!r}: block {block} missing"
    return blocks[block]


def baseline_lines(doc: str, heading: str, block: int = 0) -> tuple[str, ...]:
    """The same, for a file under ``behavioral_baselines/`` — BF-02's own
    numbered sections are where the numbers and the tie-break order live."""

    blocks = _fenced_blocks(
        (BASELINES / doc).read_text(encoding="utf-8"), heading
    )
    assert len(blocks) > block, f"{doc} {heading!r}: block {block} missing"
    return blocks[block]


def document_text(doc: str) -> list[str]:
    """Every line of one canonical document (1-based via ``enumerate``)."""

    return (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()


def source_text(relative: str) -> str:
    """One source file's text, by repo-relative path."""

    return (REPO_ROOT / relative).read_text(encoding="utf-8")
