"""Shared fixtures for the Phase 6 tests (P6-0: the §5.1 goal / policy /
session-focus objects; P6-1: the §5.2 schedule / review-event objects — their
durable rows and their authority faces; P6-3: the §9 PlannerConstraint row).

Two deliberate choices, both following the Phase 5 conftest:

- **the app.db is a real one** — migrations through v12, an opened runtime
  epoch, and the conversation / learning / teaching / user-config / scheduler
  stores over the same connection. Nothing is hand-seeded and no
  ``_seed``-style helper exists here: the world a P6-0/P6-1 test asserts on is
  built by the shipped chain (migrations → stores → the coordinator) or not at
  all;
- **the learning rows come from the real supply** — the content.db built
  from this repository's authoring trees, consumed through
  ``ContentBackedTeachingTargetProvider`` and ``ContentBackedSilentTargets``.
  The Phase 3 fixture target provider is never imported (the P5-1 red line,
  kept here and pinned by test).

The canonical-document readers are re-declared rather than imported from
tests/phase5/conftest: they are this suite's own extraction pins (§5.1's /
§5.2's column blocks are read out of the document at test time, not typed
twice), and phase 6 is meant to keep its assertions independent of another
phase's fixture module.

The two §5.2 keys the scheduler fixtures carry (``TARGET_ID`` /
``MODALITY``) name a real RESOURCE of this repository's content corpus
(``res-hedge-i-think``, content_src/index.json), so a schedule row written in
a test points at a target the shipped supply also knows.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterator, Mapping

import pytest

from elc.content.build import build_content_db
from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.learning.controller import LearningController
from elc.learning.silent_evidence import (
    ContentBackedSilentTargets,
    ContentBackedTargetSupply,
)
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
    sample_character_package,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    EvidenceGroupId,
    EvidenceModality,
    GoalId,
    GoalModality,
    GoalVersion,
    InputId,
    InteractionChannel,
    MomentId,
    Ok,
    PolicyVersion,
    ScheduleVersion,
    TargetId,
    TurnId,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.types import InputEnvelope
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    SpacingStage,
)
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.targets import TeachingTargetProvider
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
from tests.conftest import REPO_ROOT, AssemblyGenerationStore

DOCS_ROOT = REPO_ROOT / "docs"

#: The P6-0 world: one conversation, one user, one fixed clock.
CONV = ConvId("conv-p6-0")
USER = UserId("user-p6-0")
OTHER_USER = UserId("user-p6-0-other")
RUNTIME_VERSION = "runtime-v1"
REQUESTED_AT = "2026-09-22T09:00:00+00:00"
#: The §24.5 whole-utterance RESOURCE form the silent chain admits (the same
#: canonical corpus form the P5-2 suites use): one natural turn on it lands
#: one Performance Evidence claim, so the P6-0 invariants have real learning
#: rows to compare against.
SILENT_UTTERANCE = "I think it is going to rain."

#: The P6-1 world: one §5.2 modality key over the corpus target above.
TARGET_TYPE = "RESOURCE"
CAPABILITY_TARGET_TYPE = "CAPABILITY"
TARGET_ID = TargetId("res-hedge-i-think")
CAPABILITY_TARGET_ID = TargetId("cap-ref-ask-clarification")
MODALITY = EvidenceModality.TEXT_PRODUCTION
OTHER_MODALITY = EvidenceModality.TEXT_COMPREHENSION
SCHEDULE_VERSION = ScheduleVersion("sv-1")
WATERMARK = "wm-1"

#: The P6-3 world: one §9 constraint window and the instant the read faces ask
#: about. The three instants are deliberately spaced a day apart so an
#: inclusive boundary and an exclusive one cannot answer alike.
CONSTRAINT_ID = "pc-1"
CONSTRAINT_START = "2026-09-22T09:00:00+00:00"
CONSTRAINT_END = "2026-09-24T09:00:00+00:00"
AS_OF = "2026-09-23T09:00:00+00:00"

__all__ = [
    "AS_OF",
    "CAPABILITY_TARGET_ID",
    "CAPABILITY_TARGET_TYPE",
    "CONSTRAINT_END",
    "CONSTRAINT_ID",
    "CONSTRAINT_START",
    "CONV",
    "DOCS_ROOT",
    "MODALITY",
    "OTHER_MODALITY",
    "OTHER_USER",
    "REQUESTED_AT",
    "RUNTIME_VERSION",
    "SCHEDULE_VERSION",
    "SILENT_UTTERANCE",
    "TARGET_ID",
    "TARGET_TYPE",
    "USER",
    "WATERMARK",
    "canonical_blocks",
    "canonical_lines",
    "commit_chat_turn",
    "due_controller",
    "goal",
    "learning_controller",
    "make_lease",
    "planner_constraint",
    "portfolio",
    "review_event",
    "schedule_item",
    "session_focus",
    "teaching_policy",
]


@pytest.fixture(scope="session")
def built_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The repository's content.db, built once for the whole session."""

    output = tmp_path_factory.mktemp("p6-0-content") / "content.db"
    build_content_db(output)
    return output


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
def user_config_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteUserConfigStore:
    """The durable goal / policy / focus rows (migration 0011)."""

    return SqliteUserConfigStore(db, fence)


@pytest.fixture()
def user_config_controller(
    user_config_store: SqliteUserConfigStore,
) -> UserConfigController:
    return UserConfigController(user_config_store)


@pytest.fixture()
def scheduler_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteSchedulerStore:
    """The durable schedule / review-event rows (migration 0012)."""

    return SqliteSchedulerStore(db, fence)


@pytest.fixture()
def scheduler_controller(
    scheduler_store: SqliteSchedulerStore,
) -> SchedulerController:
    return SchedulerController(scheduler_store)


@pytest.fixture()
def learning_controller(
    learning: SqliteLearningStore,
) -> LearningController:
    """The real Learning authority face (P6-2's read input, DOMAIN_MODEL §9)."""

    return LearningController(learning)


@pytest.fixture()
def due_controller(
    scheduler_store: SqliteSchedulerStore,
    learning_controller: LearningController,
) -> SchedulerController:
    """The Scheduler face wired to the real Learning reads (P6-2).

    The same durable store the P6-1 fixtures use, plus the one optional port a
    recomputation needs: the freshness/watermark read face, handed over
    structurally because the scheduler package imports no other domain.
    """

    return SchedulerController(scheduler_store, learning=learning_controller)


@pytest.fixture()
def production_provider(
    built_content_db: Path,
) -> Iterator[TeachingTargetProvider]:
    """The production target provider over the session's built content.db."""

    provider = ContentBackedTeachingTargetProvider(built_content_db)
    yield provider
    provider.close()


@pytest.fixture()
def silent_supply(built_content_db: Path) -> Iterator[ContentBackedTargetSupply]:
    """The P5-2 supply read face over the session's built content.db."""

    supply = ContentBackedTargetSupply(built_content_db)
    yield supply
    supply.close()


@pytest.fixture()
def silent_targets(
    silent_supply: ContentBackedTargetSupply,
) -> ContentBackedSilentTargets:
    """The chat-leg resolver over the session's built content.db."""

    return ContentBackedSilentTargets(silent_supply)


@pytest.fixture()
def conversation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def conversation(conversation_store: SqliteConversationStore) -> ConvId:
    result = conversation_store.open_conversation(
        CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok), result
    return result.value


@pytest.fixture()
def learning(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteLearningStore:
    return SqliteLearningStore(db, fence)


@pytest.fixture()
def generation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> AssemblyGenerationStore:
    return AssemblyGenerationStore(db, fence)


@pytest.fixture()
def decision_cycle_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteDecisionCycleStore:
    return SqliteDecisionCycleStore(db, fence)


@pytest.fixture()
def teaching_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteTeachingStore:
    return SqliteTeachingStore(db, fence)


@pytest.fixture()
def teaching_controller(teaching_store: SqliteTeachingStore) -> TeachingController:
    return TeachingController(teaching_store)


def make_lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    """The coordinator lease over this test's epoch (re-declared: four lines,
    and importing it would pull another phase's conftest into the graph)."""

    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder


@pytest.fixture()
def silent_coordinator(
    conversation_store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    production_provider: TeachingTargetProvider,
    silent_targets: ContentBackedSilentTargets,
) -> ConversationCoordinator:
    """The live assembly this suite compares learning rows against.

    Every port is the real one (conversation, generation, learning, decision
    cycles, teaching, the content.db-backed target provider, and the P5-2
    silent-evidence source); the persona provider is a scripted stand-in for
    a model, which is the one thing a repo-native test cannot have.
    """

    return ConversationCoordinator(
        lease=make_lease(fence),
        conversation_commands=conversation_store,
        conversation_queries=conversation_store,
        persona=PersonaRuntime(
            actions=generation_store,
            provider=ScriptedPersonaProvider(),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=generation_store,
        learning=learning,
        character_package=sample_character_package(),
        decision_cycles=decision_cycle_store,
        learning_controller=LearningController(learning),
        teaching=teaching_controller,
        targets=production_provider,
        silent_evidence=silent_targets,
    )


# -- object builders -------------------------------------------------------


def goal(
    goal_id: str,
    *,
    modality: GoalModality = GoalModality.SPEAKING,
    description: str = "a long-term goal",
) -> LearningGoal:
    return LearningGoal(
        goal_id=GoalId(goal_id), goal_modality=modality, description=description
    )


def portfolio(
    *goals: LearningGoal,
    user_id: UserId = USER,
    version: str = "gv-1",
    weights: Mapping[GoalModality, float] | None = None,
    assessment_targets: tuple[str, ...] = ("ielts-speaking",),
    register_style_goals: tuple[str, ...] = ("workplace-formal",),
    effective_from: str = "2026-09-22T00:00:00+00:00",
) -> LearningGoalPortfolio:
    """One portfolio with the caller's content (the write face's input)."""

    return LearningGoalPortfolio(
        goal_portfolio_id=user_id,
        goal_version=GoalVersion(version),
        goals=goals,
        modality_weights=(
            {GoalModality.SPEAKING: 0.6, GoalModality.LISTENING: 0.4}
            if weights is None
            else dict(weights)
        ),
        assessment_targets=assessment_targets,
        register_style_goals=register_style_goals,
        effective_from=effective_from,
    )


def teaching_policy(
    *,
    user_id: UserId = USER,
    version: str = "pv-1",
    frequency: TeachingFrequency = TeachingFrequency.BALANCED,
    **unpinned: str | None,
) -> TeachingPolicyProfile:
    """One teaching policy; ``unpinned`` carries the eight §5.1 columns whose
    value range the canonical set does not pin (raw values, or nothing)."""

    return TeachingPolicyProfile(
        teaching_policy_profile_id=user_id,
        policy_version=PolicyVersion(version),
        teaching_frequency=frequency,
        **unpinned,
    )


def session_focus(
    focus_id: str = "sf-1",
    *,
    conversation: ConvId = CONV,
    base_version: str = "gv-1",
    weights: Mapping[GoalModality, float] | None = None,
    target: str | None = None,
    starts_at: str = "2026-09-22T09:00:00+00:00",
    expires_at: str | None = None,
) -> SessionFocus:
    """One focus over the fixed conversation of this suite."""

    return SessionFocus(
        session_focus_id=focus_id,
        conversation_id=conversation,
        base_goal_portfolio_version=GoalVersion(base_version),
        temporary_goal_weights=(
            {GoalModality.SPEAKING: 1.0} if weights is None else dict(weights)
        ),
        manual_focus_target=None if target is None else TargetId(target),
        starts_at=starts_at,
        expires_at=expires_at,
    )


def schedule_item(
    item_id: str = "si-1",
    *,
    target_type: str = TARGET_TYPE,
    target_id: TargetId = TARGET_ID,
    modality: EvidenceModality = MODALITY,
    review_state: ReviewState = ReviewState.UPCOMING,
    urgency: float | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    stage: SpacingStage | None = None,
    watermark: str = WATERMARK,
    version: str = "sv-1",
    updated_at: str = "",
) -> ScheduleItem:
    """One §5.2 ScheduleItem with the caller's content (the write face's
    input). Every optional column defaults to ``None`` = not configured, and
    the store stamps ``updated_at`` — a caller's value is ignored by design.
    """

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
        updated_at=updated_at,
    )


def review_event(
    event_id: str = "re-1",
    *,
    schedule_item_id: str = "si-1",
    event_type: str = "RECALL_ATTEMPT",
    engaged: bool = True,
    moment: str | None = None,
    turn: str | None = None,
    evidence_group: str | None = None,
    created_at: str = "",
) -> ReviewEvent:
    """One §5.2 ReviewEvent; ``event_type`` is a raw string on purpose (the
    canonical set pins no vocabulary for it — elc/scheduler/types.py)."""

    return ReviewEvent(
        review_event_id=event_id,
        schedule_item_id=schedule_item_id,
        teaching_moment_id=None if moment is None else MomentId(moment),
        source_turn_id=None if turn is None else TurnId(turn),
        event_type=event_type,
        engaged=engaged,
        evidence_group_id=(
            None if evidence_group is None else EvidenceGroupId(evidence_group)
        ),
        created_at=created_at,
    )


def planner_constraint(
    constraint_id: str = CONSTRAINT_ID,
    *,
    constraint_type: PlannerConstraintType = (
        PlannerConstraintType.DO_NOT_AUTO_TEACH
    ),
    scope: PlannerConstraintScope = PlannerConstraintScope.UNTIL_DATE,
    target_type: str | None = None,
    target_id: TargetId | None = None,
    starts_at: str = CONSTRAINT_START,
    expires_at: str | None = CONSTRAINT_END,
    created_from_turn: str | None = None,
    active: bool = True,
) -> PlannerConstraint:
    """One §9 PlannerConstraint (P6-3) with the caller's content.

    The defaults are a *closed* constraint over the fixed window
    ``CONSTRAINT_START`` → ``CONSTRAINT_END`` (``AS_OF`` sits strictly inside
    it), with no target leg and no originating turn — the shape a caller
    writes when it is stating a plain "别自动教" for the whole session. Every
    optional column is ``None`` by default, and a caller that wants a specific
    instant passes it: this builder never reads a clock (the durable row has
    no store-stamped column either).
    """

    return PlannerConstraint(
        constraint_id=constraint_id,
        target_type=target_type,
        target_id=target_id,
        constraint_type=constraint_type,
        scope=scope,
        starts_at=starts_at,
        expires_at=expires_at,
        created_from_turn_id=(
            None if created_from_turn is None else TurnId(created_from_turn)
        ),
        active=active,
    )


# -- drivers ---------------------------------------------------------------


def commit_chat_turn(
    coordinator: ConversationCoordinator,
    cmid: str,
    text: str,
    turn_no: int,
    *,
    conversation: ConvId = CONV,
):
    """One Basic Persona Conversation turn (the IP §1.5 slice's first leg)."""

    result = coordinator.begin_turn(
        CommitUserTurn(
            conversation_id=conversation,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{cmid}"),
                client_message_id=ClientMessageId(cmid),
                conversation_id=str(conversation),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{turn_no}",
                received_at=REQUESTED_AT,
            ),
            raw_content=text,
            runtime_version=RUNTIME_VERSION,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


# ---------------------------------------------------------------------------
# Canonical-document readers: pins extract the column blocks from docs/ itself
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```")


def canonical_blocks(doc: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block after `heading`, as (line, …) tuples.

    The canonical documents are the authority these tests pin against, so the
    column lists are extracted from the document text at test time rather
    than from a second hand-typed copy (the Phase 5 reader, re-declared). The
    section ends at the next heading of the same or higher level.
    """

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
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level and stripped[:head_level + 1].endswith(" "):
                break
        if _FENCE_RE.match(line):
            body: list[str] = []
            index += 1
            while index < len(lines) and not _FENCE_RE.match(lines[index]):
                if lines[index].strip():
                    body.append(lines[index].strip())
                index += 1
            if body:
                blocks.append(tuple(body))
        index += 1
    return blocks


def canonical_lines(doc: str, heading: str, block: int = 0) -> tuple[str, ...]:
    """The `block`-th fenced block after `heading` (0-based)."""

    blocks = canonical_blocks(doc, heading)
    assert len(blocks) > block, (
        f"{doc} {heading!r}: block {block} missing (found {len(blocks)})"
    )
    return blocks[block]
