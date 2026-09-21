"""Shared fixtures for the Phase 6 tests (P6-0: the §5.1 goal / policy /
session-focus objects, their durable rows and their authority faces).

Two deliberate choices, both following the Phase 5 conftest:

- **the app.db is a real one** — migrations through v11, an opened runtime
  epoch, and the conversation / learning / teaching / user-config stores over
  the same connection. Nothing is hand-seeded and no ``_seed``-style helper
  exists here: the world a P6-0 test asserts on is built by the shipped
  chain (migrations → stores → the coordinator) or not at all;
- **the learning rows come from the real supply** — the content.db built
  from this repository's authoring trees, consumed through
  ``ContentBackedTeachingTargetProvider`` and ``ContentBackedSilentTargets``.
  The Phase 3 fixture target provider is never imported (the P5-1 red line,
  kept here and pinned by test).

The canonical-document readers are re-declared rather than imported from
tests/phase5/conftest: they are this suite's own extraction pins (§5.1's
column blocks are read out of the document at test time, not typed twice),
and phase 6 is meant to keep its assertions independent of another phase's
fixture module.
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
    GoalId,
    GoalModality,
    GoalVersion,
    InputId,
    InteractionChannel,
    Ok,
    PolicyVersion,
    TargetId,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.types import InputEnvelope
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.targets import TeachingTargetProvider
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
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

__all__ = [
    "CONV",
    "DOCS_ROOT",
    "OTHER_USER",
    "REQUESTED_AT",
    "RUNTIME_VERSION",
    "SILENT_UTTERANCE",
    "USER",
    "canonical_blocks",
    "canonical_lines",
    "commit_chat_turn",
    "goal",
    "make_lease",
    "portfolio",
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
