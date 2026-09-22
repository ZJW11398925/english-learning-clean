"""Shared fixtures for the Gate 2 (BF-05 deletion / tombstone) suite.

Two deliberate choices, both following the Phase 5 / Phase 6 conftests:

- **the app.db is a real one** — migrations through v14, an opened runtime
  epoch, and the conversation / learning / teaching / relationship /
  user-config / scheduler stores over the same connection. Nothing is
  hand-seeded and no ``_seed``-style helper exists here: the world a deletion
  test asserts on is built by the shipped chain (migrations → stores → the
  coordinator) or not at all;
- **the learning rows come from the real supply** where a probe needs them —
  the content.db built from this repository's authoring trees, consumed
  through ``ContentBackedTeachingTargetProvider`` and
  ``ContentBackedSilentTargets``. The Phase 3 fixture target provider is never
  imported.

The document readers are re-declared rather than imported from another
phase's conftest: §24's column block is read out of the contract at test time
(this suite's own extraction pin), and the deletion suite is meant to keep its
assertions independent of another phase's fixture module.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pytest

from elc.content.build import build_content_db
from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.deletion.controller import DeletionController
from elc.deletion.store import SqliteDeletionStore
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
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    ClientMessageId,
    EvidenceModality,
    InputId,
    InteractionChannel,
    Ok,
    PersonaId,
    TargetId,
    TurnId,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.relationship.controller import RelationshipController
from elc.relationship.episode_store import SqliteEpisodeStore
from elc.relationship.projection import (
    EpisodeProjectionExecutor,
    RelationshipProjectionExecutor,
)
from elc.relationship.recorder import RelationshipRecorder
from elc.relationship.store import SqliteRelationshipStore
from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    RelationshipMemoryProposal,
    RelationshipMemoryType,
)
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.projections import CP4ProjectionRuntime
from elc.runtime.types import InputEnvelope
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    ScheduleVersion,
)
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.targets import TeachingTargetProvider
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    PlannerConstraint,
    PlannerConstraintScope,
    PlannerConstraintType,
    ProfileFact,
    UserProfile,
)
from tests.conftest import REPO_ROOT, AssemblyGenerationStore

SECURITY_DOC = "SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md"
BASELINE_SECURITY = REPO_ROOT / "behavioral_baselines" / "security"
CONTRACT_PATH = BASELINE_SECURITY / SECURITY_DOC

#: The deletion world: two conversations of one persona (so a per-conversation
#: deletion has a sibling to leave alone), one conversation of another persona
#: (so a relationship deletion has a pair to leave alone), one user.
CONV = ConvId("conv-del-1")
CONV_OTHER = ConvId("conv-del-2")
CONV_OTHER_PERSONA = ConvId("conv-del-3")
USER = UserId("user-del")
PERSONA = PersonaId("persona-del")
PERSONA_OTHER = PersonaId("persona-del-other")
RUNTIME_VERSION = "runtime-v1"
REQUESTED_AT = "2026-09-22T09:00:00+00:00"
#: The §24.5 whole-utterance RESOURCE form the silent chain admits: one
#: natural turn on it lands one Performance Evidence claim.
SILENT_UTTERANCE = "I think it is going to rain."
TARGET_TYPE = "RESOURCE"
TARGET_ID = TargetId("res-hedge-i-think")
MODALITY = EvidenceModality.TEXT_PRODUCTION

__all__ = [
    "BASELINE_SECURITY",
    "CONTRACT_PATH",
    "CONV",
    "CONV_OTHER",
    "CONV_OTHER_PERSONA",
    "MODALITY",
    "PERSONA",
    "PERSONA_OTHER",
    "REQUESTED_AT",
    "RUNTIME_VERSION",
    "SECURITY_DOC",
    "SILENT_UTTERANCE",
    "TARGET_ID",
    "TARGET_TYPE",
    "USER",
    "canonical_blocks",
    "canonical_lines",
    "commit_chat_turn",
    "make_lease",
]


# ---------------------------------------------------------------------------
# The real world
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def built_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The repository's content.db, built once for the whole session."""

    output = tmp_path_factory.mktemp("gate2-content") / "content.db"
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
def conversation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def learning(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteLearningStore:
    return SqliteLearningStore(db, fence)


@pytest.fixture()
def learning_controller(learning: SqliteLearningStore) -> LearningController:
    return LearningController(learning)


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


@pytest.fixture()
def scheduler_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteSchedulerStore:
    return SqliteSchedulerStore(db, fence)


@pytest.fixture()
def scheduler_controller(
    scheduler_store: SqliteSchedulerStore,
    learning_controller: LearningController,
) -> SchedulerController:
    """The Scheduler face wired to the real Learning reads (P6-2's shape)."""

    return SchedulerController(scheduler_store, learning=learning_controller)


@pytest.fixture()
def relationship_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteRelationshipStore:
    return SqliteRelationshipStore(db, fence)


@pytest.fixture()
def episode_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteEpisodeStore:
    return SqliteEpisodeStore(db, fence)


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
def projection_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteProjectionStore:
    return SqliteProjectionStore(db, fence)


@pytest.fixture()
def production_provider(
    built_content_db: Path,
) -> Iterator[TeachingTargetProvider]:
    provider = ContentBackedTeachingTargetProvider(built_content_db)
    yield provider
    provider.close()


@pytest.fixture()
def silent_supply(built_content_db: Path) -> Iterator[ContentBackedTargetSupply]:
    supply = ContentBackedTargetSupply(built_content_db)
    yield supply
    supply.close()


@pytest.fixture()
def silent_targets(
    silent_supply: ContentBackedTargetSupply,
) -> ContentBackedSilentTargets:
    return ContentBackedSilentTargets(silent_supply)


@pytest.fixture()
def conversation(conversation_store: SqliteConversationStore) -> ConvId:
    """The persona-carrying conversation the probes delete."""

    result = conversation_store.open_conversation(
        CONV, user_id=USER, persona_id=PERSONA, scene_id=None
    )
    assert result is not None
    return CONV


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
    """The live assembly this suite drives real turns through.

    Every port is the real one; the persona provider is a scripted stand-in
    for a model, which is the one thing a repo-native test cannot have.
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


@pytest.fixture()
def relationship_controller(
    relationship_store: SqliteRelationshipStore,
) -> RelationshipController:
    return RelationshipController(relationship_store)


@pytest.fixture()
def relationship_executor(
    conversation_store: SqliteConversationStore,
    relationship_controller: RelationshipController,
) -> RelationshipProjectionExecutor:
    """The shipped CP4 RELATIONSHIP executor, with no candidate provider.

    ``candidates=None`` is the executor's own documented Local V1 shape ("this
    assembly has no provider"): the Recorder proposes nothing and the
    projection commits having done exactly that. It is here because
    ``CP4ProjectionRuntime`` refuses an incomplete executor set — the episode
    rebuild this suite exercises needs a runtime assembled the way the app
    assembles one.
    """

    return RelationshipProjectionExecutor(
        recorder=RelationshipRecorder(conversation_store),
        controller=relationship_controller,
        conversation=conversation_store,
        user_id=USER,
    )


@pytest.fixture()
def episode_executor(
    episode_store: SqliteEpisodeStore,
    relationship_controller: RelationshipController,
    conversation_store: SqliteConversationStore,
) -> EpisodeProjectionExecutor:
    """The shipped CP4 EPISODE executor over the real stores.

    Built here exactly as the app assembly builds it; the deletion controller
    reaches it through ``CP4ProjectionRuntime``, never by calling ``project``
    on a hand-made job view.
    """

    return EpisodeProjectionExecutor(
        store=episode_store,
        controller=relationship_controller,
        conversation=conversation_store,
        user_id=USER,
    )


@pytest.fixture()
def projection_runtime(
    projection_store: SqliteProjectionStore,
    conversation_store: SqliteConversationStore,
    relationship_executor: RelationshipProjectionExecutor,
    episode_executor: EpisodeProjectionExecutor,
) -> CP4ProjectionRuntime:
    """The CP4 runtime the deletion controller rebuilds episodes through."""

    return CP4ProjectionRuntime(
        store=projection_store,
        executors=(relationship_executor, episode_executor),
        turns=conversation_store,
    )


@pytest.fixture()
def deletion_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteDeletionStore:
    return SqliteDeletionStore(db, fence)


@pytest.fixture()
def deletion_controller(
    deletion_store: SqliteDeletionStore,
    learning_controller: LearningController,
    scheduler_controller: SchedulerController,
    projection_runtime: CP4ProjectionRuntime,
) -> DeletionController:
    """The authority face with all three rebuild ports wired."""

    return DeletionController(
        deletion_store,
        learning=learning_controller,
        scheduler=scheduler_controller,
        projections=projection_runtime,
    )


def make_lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder


# ---------------------------------------------------------------------------
# The world: one real app.db with rows in every table a scope touches
# ---------------------------------------------------------------------------

WATERMARK = "wm-1"
MAIN_MEMORY = "the user likes the rain"
OTHER_MEMORY = "the user dislikes the cold"
FOREIGN_MEMORY = "a different pair remembers"


@dataclass
class World:
    """The rows the probes assert on, named by role rather than by id."""

    conversations: dict[str, ConvId] = field(default_factory=dict)
    turns: dict[str, TurnId] = field(default_factory=dict)
    memories: dict[str, str] = field(default_factory=dict)
    schedule_item_id: str = "si-probe-1"
    review_event_id: str = "re-probe-1"
    constraint_id: str = "pc-probe-1"
    content_digest: str = ""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_memory(
    controller, persona: PersonaId, content: str, turn: TurnId
) -> str:
    """One real memory through the authority face (§5 write flow)."""

    proposal = RelationshipMemoryProposal(
        persona_id=persona,
        user_id=USER,
        memory_type=RelationshipMemoryType.USER_STATED_FACT,
        provenance=MemoryProvenance.USER_STATED_FACT,
        content=content,
        source_turn_id=turn,
        source_turn_ids=(turn,),
        provenance_refs=(str(turn),),
        recorder_version="probe-recorder-v1",
    )
    result = controller.propose_memory(proposal)
    assert isinstance(result, Ok), result
    return str(result.value)


def turn_id_of(db: sqlite3.Connection, conversation: ConvId) -> TurnId:
    """The newest turn of a conversation (probe helper)."""

    row = db.execute(
        "SELECT turn_id FROM turn_record WHERE conversation_id = ?"
        " ORDER BY turn_sequence DESC LIMIT 1",
        (str(conversation),),
    ).fetchone()
    assert row is not None, f"no turn in {conversation}"
    return TurnId(str(row[0]))


@pytest.fixture()
def world(
    conversation,
    conversation_store,
    silent_coordinator,
    relationship_controller,
    scheduler_store,
    user_config_store,
    projection_runtime,
    db: sqlite3.Connection,
    built_content_db: Path,
) -> World:
    """Build the world through the shipped faces, then hand it over.

    Three conversations — two of one persona, one of another — so a
    per-conversation deletion has a sibling to leave alone and a relationship
    deletion has a second pair to leave alone; one real turn per conversation
    through the coordinator (which lands real silent evidence); one memory per
    pair, sourced from its own conversation's turn; one schedule row with one
    review event; one planner constraint created from the main turn; and one
    user profile.
    """

    result = World()
    result.conversations["main"] = CONV
    for key, conversation_id, persona in (
        ("other", CONV_OTHER, PERSONA),
        ("foreign", CONV_OTHER_PERSONA, PERSONA_OTHER),
    ):
        opened = conversation_store.open_conversation(
            conversation_id, USER, persona, None
        )
        assert isinstance(opened, Ok), opened
        result.conversations[key] = conversation_id

    turn_no = 0
    for key, conversation_id in result.conversations.items():
        turn_no += 1
        committed = commit_chat_turn(
            silent_coordinator,
            f"cm-{key}",
            SILENT_UTTERANCE,
            turn_no,
            conversation=conversation_id,
        )
        assert isinstance(committed, Ok), committed
        turn = turn_id_of(db, conversation_id)
        result.turns[key] = turn
        ran = projection_runtime.run_after_turn(conversation_id, turn)
        assert isinstance(ran, Ok), ran

    result.memories["main"] = _record_memory(
        relationship_controller, PERSONA, MAIN_MEMORY, result.turns["main"]
    )
    result.memories["other"] = _record_memory(
        relationship_controller, PERSONA, OTHER_MEMORY, result.turns["other"]
    )
    result.memories["foreign"] = _record_memory(
        relationship_controller,
        PERSONA_OTHER,
        FOREIGN_MEMORY,
        result.turns["foreign"],
    )

    item = ScheduleItem(
        schedule_item_id=result.schedule_item_id,
        target_type=TARGET_TYPE,
        target_id=TARGET_ID,
        evidence_modality=MODALITY,
        review_state=ReviewState.UPCOMING,
        review_urgency=None,
        next_review_window_start=None,
        next_review_window_end=None,
        spacing_stage=None,
        source_learning_watermark=WATERMARK,
        version=ScheduleVersion("sv-1"),
        updated_at="",
    )
    written = scheduler_store.upsert_schedule_item(item)
    assert isinstance(written, Ok), written
    event = ReviewEvent(
        review_event_id=result.review_event_id,
        schedule_item_id=result.schedule_item_id,
        teaching_moment_id=None,
        source_turn_id=result.turns["main"],
        event_type="RECALL_ATTEMPT",
        engaged=True,
        evidence_group_id=None,
        created_at="",
    )
    appended = scheduler_store.record_review_event(event)
    assert isinstance(appended, Ok), appended

    constraint = PlannerConstraint(
        constraint_id=result.constraint_id,
        target_type=None,
        target_id=None,
        constraint_type=PlannerConstraintType.DO_NOT_AUTO_TEACH,
        scope=PlannerConstraintScope.UNTIL_USER_REENABLES,
        starts_at="2026-09-22T09:00:00+00:00",
        expires_at=None,
        created_from_turn_id=result.turns["main"],
        active=True,
    )
    recorded = user_config_store.record_planner_constraint(constraint)
    assert isinstance(recorded, Ok), recorded

    profile = UserProfile(
        user_profile_id=USER,
        revision="rev-1",
        profile_facts=(
            ProfileFact(
                text="lives in Lisbon",
                sensitivity=MemorySensitivityClass.PERSONAL,
            ),
        ),
        preferences=("concise explanations",),
        settings=("dark mode",),
    )
    persisted = user_config_store.upsert_user_profile(profile)
    assert isinstance(persisted, Ok), persisted

    result.content_digest = _digest(built_content_db)
    return result


def commit_chat_turn(
    coordinator: ConversationCoordinator,
    cmid: str,
    text: str,
    turn_no: int,
    *,
    conversation: ConvId = CONV,
):
    """One Basic Persona Conversation turn, through the real coordinator."""

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
    assert result is not None
    return result


# ---------------------------------------------------------------------------
# Canonical-document readers (the contract is the authority these tests pin)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```")


def canonical_blocks(doc: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block under ``heading`` in the security contract."""

    lines = CONTRACT_PATH.read_text(encoding="utf-8").splitlines()
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
            if head_level <= level:
                break
        if _FENCE_RE.match(lines[index]):
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
    blocks = canonical_blocks(doc, heading)
    assert len(blocks) > block, (
        f"{doc} {heading!r}: block {block} missing (found {len(blocks)})"
    )
    return blocks[block]
