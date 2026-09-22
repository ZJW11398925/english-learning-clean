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
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

import pytest

from elc.content.build import build_content_db
from elc.content.store import ContentStore
from elc.conversation import SqliteConversationStore
from elc.curriculum.store import CurriculumContentStore
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ConversationId as ConvId,
)
from elc.platform.types import (
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
    "canonical_lines",
    "constraint",
    "content_supply",
    "conversations",
    "db",
    "document_text",
    "fence",
    "focus",
    "instant",
    "learning_controller",
    "portfolio",
    "review_event",
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
# Canonical-document reader (re-declared: this suite's own extraction pins)
# ---------------------------------------------------------------------------

_FENCE = "```"


def canonical_lines(doc: str, heading: str, block: int = 0) -> tuple[str, ...]:
    """The ``block``-th fenced block after ``heading`` in ``docs/<doc>``."""

    lines = (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"heading {heading!r} not found in {doc}"
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
    assert len(blocks) > block, f"{doc} {heading!r}: block {block} missing"
    return blocks[block]


def document_text(doc: str) -> list[str]:
    """Every line of one canonical document (1-based via ``enumerate``)."""

    return (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()


def source_text(relative: str) -> str:
    """One source file's text, by repo-relative path."""

    return (REPO_ROOT / relative).read_text(encoding="utf-8")
