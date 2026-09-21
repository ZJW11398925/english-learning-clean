"""Shared fixtures for the Phase 4 P4-0 tests.

Each test gets a fresh in-memory app.db (migrations through 0009), an
opened runtime epoch, and the learning / conversation / teaching stores
bound to that epoch. The P3-1A/P3-1B assembly helpers (``make_lease``,
``make_teaching_coordinator``) stay owned by tests/phase3/conftest.py and
are imported, never copied: the P3 assembly is the one this slice drives,
and a second copy would drift.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterator

import pytest

from elc.conversation import (
    AssistantTurnRecord,
    CanonicalTurnSlice,
    CommitUserTurn,
    DeliveryState,
    SqliteConversationStore,
)
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.persona import ScriptedPersonaProvider
from elc.persona.types import CompiledPrompt
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    MessageSequence,
    Ok,
    PersonaId,
    ProjectionJobId,
    RelationshipMemoryId,
    Result,
    TurnId,
    TurnSequence,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.relationship import (
    RELATIONSHIP_RECORDER_VERSION,
    EpisodeProjectionExecutor,
    MemoryProvenance,
    MemorySensitivityClass,
    PersistenceAuthorization,
    RelationshipController,
    RelationshipMemoryCandidate,
    RelationshipMemoryProposal,
    RelationshipMemoryType,
    RelationshipProjectionExecutor,
    RelationshipRecorder,
    RelationshipRecorderKey,
    RelationshipRecorderOutcome,
    SamePersonaExistingRelationshipSummary,
)
from elc.relationship.episode_store import SqliteEpisodeStore
from elc.relationship.store import SqliteRelationshipStore
from elc.runtime.controller import ConversationCoordinator, TeachingReplyRequest
from elc.runtime.persona_views import ControllerPersonaViews
from elc.runtime.projections import (
    SUPPORTED_PROJECTION_TYPES,
    CP4ProjectionRuntime,
    ProjectionExecutor,
    ProjectionJobView,
)
from elc.runtime.types import InputEnvelope, TurnRecordData
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.targets import TeachingTargetProvider
from elc.user_config import (
    DisclosureLevel,
    DisclosurePolicy,
    DisclosureRule,
    ProfileFact,
    SqliteUserConfigStore,
    UserConfigController,
    UserProfile,
)
from tests.conftest import AssemblyGenerationStore
from tests.phase3.conftest import make_lease, make_teaching_coordinator
from tests.phase3.target_fixtures import FixtureTeachingTargetProvider

CONV = ConvId("conv-p4")
RUNTIME_VERSION = "runtime-v1"
REQUESTED_AT = "2026-09-21T10:00:00+00:00"
#: tests/phase3/target_fixtures.py validated target + its canonical answer
#: (the same pair the P3-3 full-chain acceptance drives).
FOCUS_TARGET = "res-hedge-i-think"
CANONICAL_ANSWER = "I think it is going to rain."
WRONG_ANSWER = "The weather is terrible today."


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
def learning(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteLearningStore:
    return SqliteLearningStore(db, fence)


@pytest.fixture()
def learning_controller(learning: SqliteLearningStore) -> LearningController:
    return LearningController(learning)


@pytest.fixture()
def store(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def generation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> AssemblyGenerationStore:
    return AssemblyGenerationStore(db, fence)


@pytest.fixture()
def conversation(store: SqliteConversationStore) -> ConvId:
    result = store.open_conversation(
        CONV, user_id=UserId("user-1"), persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok)
    return result.value


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
def target_provider() -> FixtureTeachingTargetProvider:
    return FixtureTeachingTargetProvider()


@pytest.fixture()
def coordinator(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    conversation: ConvId,
) -> ConversationCoordinator:
    """The live P3-1A/P3-1B assembly over this test's epoch.

    Depends on the ``conversation`` fixture: every teaching face addresses a
    conversation, so the row is opened before any test can drive one.
    """

    del conversation
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )


# -- drivers ---------------------------------------------------------------


def open_moment(
    coordinator: ConversationCoordinator,
    cmid: str,
    target: str = FOCUS_TARGET,
):
    """One user-initiated teaching request (Gate ALLOW → CP2 → opening)."""

    result = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=target,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def reply(coordinator: ConversationCoordinator, envelope, cmid: str):
    return coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=envelope,
            client_message_id=ClientMessageId(cmid),
            requested_at=REQUESTED_AT,
        )
    )


def reply_ok(coordinator: ConversationCoordinator, envelope, cmid: str):
    result = reply(coordinator, envelope, cmid)
    assert isinstance(result, Ok), result
    return result.value


def attempt(
    text: str, intent: TeachingControlIntent = TeachingControlIntent.CONTINUE
) -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(
        control_intent=intent,
        attempt_present=True,
        attempt=AttemptPayload(text=text),
    )


def control(intent: TeachingControlIntent) -> TeachingResponseEnvelope:
    return TeachingResponseEnvelope(control_intent=intent)


def commit_chat_turn(
    coordinator: ConversationCoordinator,
    cmid: str,
    text: str,
    turn_no: int,
    *,
    conversation: ConvId = CONV,
):
    """One Basic Persona Conversation turn (the IP §1.5 slice's first leg).

    Built here rather than imported: the P3-3 acceptance helper lives in a
    test module, and a conftest is the right owner of a driver several
    phase-4 files share.
    """

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


# -- P4-1: the Relationship durable core -----------------------------------

#: Two personas over one user: the isolation pair of VAL-…72 ③.
PERSONA_A = PersonaId("persona-a")
PERSONA_B = PersonaId("persona-b")
REL_USER = UserId("user-1")


@pytest.fixture()
def relationship_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteRelationshipStore:
    return SqliteRelationshipStore(db, fence)


@pytest.fixture()
def relationship_controller(
    relationship_store: SqliteRelationshipStore,
) -> RelationshipController:
    return RelationshipController(relationship_store)


@pytest.fixture()
def recorder(store: SqliteConversationStore) -> RelationshipRecorder:
    """The P4-1 Recorder over the real conversation store: the store *is* the
    durable command-turn classifier (the P4-G1 seam)."""

    return RelationshipRecorder(store)


def open_conversation_for(
    store: SqliteConversationStore,
    conversation_id: str,
    persona_id: PersonaId | None,
) -> ConvId:
    """One conversation row owned by one persona (or by none)."""

    result = store.open_conversation(
        ConvId(conversation_id),
        user_id=REL_USER,
        persona_id=persona_id,
        scene_id=None,
    )
    assert isinstance(result, Ok), result
    return result.value


def speak(
    store: SqliteConversationStore,
    conversation_id: ConvId,
    client_message_id: str,
    text: str,
) -> TurnId:
    """One CP0 user turn (the transcript's user leg)."""

    result = store.commit_user_turn(
        CommitUserTurn(
            conversation_id=conversation_id,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{client_message_id}"),
                client_message_id=ClientMessageId(client_message_id),
                conversation_id=str(conversation_id),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-{client_message_id}",
                received_at=REQUESTED_AT,
            ),
            raw_content=text,
            runtime_version=RUNTIME_VERSION,
        )
    )
    assert isinstance(result, Ok), result
    return result.value.turn_id


def deliver_reply(
    store: SqliteConversationStore,
    turn_id: TurnId,
    conversation_id: ConvId,
    content: str,
    *,
    assistant_turn_id: str = "at-1",
    delivery_state: DeliveryState = DeliveryState.SENT_COMPLETE,
) -> AssistantTurnId:
    """Canonicalize one delivered assistant turn.

    Only delivered output enters the transcript (DOMAIN_MODEL §3 key rule),
    so this is what makes a turn's assistant side canonical at all.
    """

    result = store.canonicalize_assistant_turn(
        AssistantTurnRecord(
            assistant_turn_id=AssistantTurnId(assistant_turn_id),
            turn_id=turn_id,
            conversation_id=conversation_id,
            turn_sequence=TurnSequence(0),
            message_sequence=MessageSequence(0),
            action_id=ActionId(f"act-{assistant_turn_id}"),
            content=content,
            delivery_state=delivery_state,
            delivery_certainty="SERVER_SENT_UNCONFIRMED",
        )
    )
    assert isinstance(result, Ok), result
    return result.value


def turn_slice(store: SqliteConversationStore, turn_id: TurnId) -> CanonicalTurnSlice:
    result = store.get_canonical_turn_slice(turn_id)
    assert isinstance(result, Ok), result
    assert result.value is not None, f"turn not found: {turn_id}"
    return result.value


def newest_command_turn_slice(
    store: SqliteConversationStore,
    db: sqlite3.Connection,
    conversation_id: ConvId,
) -> CanonicalTurnSlice:
    """The newest command turn of a conversation, read through the durable
    classifier rather than by guessing at the payload text."""

    rows = db.execute(
        "SELECT turn_id FROM user_turn WHERE conversation_id = ?"
        " ORDER BY turn_sequence DESC",
        (str(conversation_id),),
    ).fetchall()
    for (turn_id,) in rows:
        classified = store.is_command_payload_turn(TurnId(str(turn_id)))
        assert isinstance(classified, Ok), classified
        if classified.value:
            return turn_slice(store, TurnId(str(turn_id)))
    raise AssertionError("no command turn found in this conversation")


def memory_candidate(
    content: str,
    *,
    memory_type: RelationshipMemoryType = (
        RelationshipMemoryType.USER_STATED_FACT
    ),
    provenance: MemoryProvenance = MemoryProvenance.USER_STATED_FACT,
    cited: tuple[str, ...] = (),
    supersedes: RelationshipMemoryId | None = None,
    sensitivity_class: MemorySensitivityClass = (
        MemorySensitivityClass.PERSONAL
    ),
    persistence_authorization: PersistenceAuthorization = (
        PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
    ),
    confidence: float | None = None,
) -> RelationshipMemoryCandidate:
    """One declared candidate assertion (the recorder's MODEL_PROPOSAL face)."""

    return RelationshipMemoryCandidate(
        memory_type=memory_type,
        provenance=provenance,
        content=content,
        sensitivity_class=sensitivity_class,
        persistence_authorization=persistence_authorization,
        confidence=confidence,
        supersedes_memory_id=supersedes,
        cited_message_ids=cited,
    )


def record_turn(
    recorder: RelationshipRecorder,
    slice_: CanonicalTurnSlice,
    summary: SamePersonaExistingRelationshipSummary,
    *candidates: RelationshipMemoryCandidate,
) -> RelationshipRecorderOutcome:
    return recorder.record_turn(
        turn=slice_,
        existing=summary,
        key=RelationshipRecorderKey(candidates=tuple(candidates)),
    )


def memory_proposal(
    content: str,
    *,
    source_turn_id: TurnId | None,
    persona_id: PersonaId = PERSONA_A,
    user_id: UserId = REL_USER,
    memory_type: RelationshipMemoryType = (
        RelationshipMemoryType.USER_STATED_FACT
    ),
    provenance: MemoryProvenance = MemoryProvenance.USER_STATED_FACT,
    provenance_refs: tuple[str, ...] | None = None,
    recorder_version: str = RELATIONSHIP_RECORDER_VERSION,
    confidence: float | None = None,
    supersedes_memory_id: RelationshipMemoryId | None = None,
    sensitivity_class: MemorySensitivityClass = (
        MemorySensitivityClass.PERSONAL
    ),
    persistence_authorization: PersistenceAuthorization = (
        PersistenceAuthorization.VALIDATED_DOMAIN_WRITE
    ),
) -> RelationshipMemoryProposal:
    """One hand-assembled proposal (the controller's input face).

    ``provenance_refs`` defaults to the source turn's id — the shape a real
    Recorder produces (elc.relationship.recorder assembles the refs from the
    slice it read).
    """

    if provenance_refs is None:
        provenance_refs = (
            () if source_turn_id is None else (str(source_turn_id),)
        )
    return RelationshipMemoryProposal(
        persona_id=persona_id,
        user_id=user_id,
        memory_type=memory_type,
        provenance=provenance,
        content=content,
        source_turn_id=source_turn_id,
        source_turn_ids=(
            () if source_turn_id is None else (source_turn_id,)
        ),
        provenance_refs=provenance_refs,
        confidence=confidence,
        supersedes_memory_id=supersedes_memory_id,
        recorder_version=recorder_version,
        sensitivity_class=sensitivity_class,
        persistence_authorization=persistence_authorization,
    )


def memory_rows(db: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Every durable relationship_memory row, in durable order."""

    return db.execute(
        "SELECT relationship_memory_id, persona_id, user_id, memory_type,"
        " provenance, canonical_content, source_turn_id, status,"
        " source_turn_ids, provenance_refs, confidence,"
        " supersedes_memory_id, recorder_version, validator_version,"
        " sensitivity_class, persistence_authorization"
        " FROM relationship_memory"
        " ORDER BY created_at, relationship_memory_id"
    ).fetchall()


# -- P4-2: the CP4 projection world ----------------------------------------


class ScriptedCandidates:
    """A MODEL_PROPOSAL source a test scripts up front (P4-2).

    The provider face the Relationship executor consumes: it answers every
    turn with the same declared assertions, exactly like a v0 assembly whose
    provider produced them. Mutable on purpose — a test fills it before
    driving the turn that should project.
    """

    def __init__(
        self, candidates: tuple[RelationshipMemoryCandidate, ...] = ()
    ) -> None:
        self.candidates = candidates

    def candidates_for(
        self, turn: CanonicalTurnSlice
    ) -> Result[tuple[RelationshipMemoryCandidate, ...]]:
        del turn
        return Ok(self.candidates)


@pytest.fixture()
def projection_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteProjectionStore:
    """The durable CP4 work queue over migration 0002's projection_job."""

    return SqliteProjectionStore(db, fence)


@pytest.fixture()
def scripted_candidates() -> ScriptedCandidates:
    return ScriptedCandidates()


@pytest.fixture()
def relationship_projection(
    store: SqliteConversationStore,
    relationship_controller: RelationshipController,
    projection_store: SqliteProjectionStore,
    scripted_candidates: ScriptedCandidates,
) -> RelationshipProjectionExecutor:
    """The live RELATIONSHIP executor: the real recorder (over the durable
    command-turn classifier), the real controller, the real conversation
    store as the turn source, and a scripted candidate provider.

    The unused ``projection_store`` dependency is declared on purpose: it
    keeps the fixture graph honest about which world this executor is built
    for (the store is injected into the runtime below, not into the
    executor — an executor never writes the queue itself).
    """

    del projection_store
    return RelationshipProjectionExecutor(
        recorder=RelationshipRecorder(store),
        controller=relationship_controller,
        conversation=store,
        user_id=REL_USER,
        candidates=scripted_candidates,
    )


class NoopProjectionExecutor:
    """An executor that always commits — the filler for supported types a
    single-type probe does not care about.

    P4-3 (review LOW-2): ``CP4ProjectionRuntime`` refuses an incomplete
    executor set at construction, because the ensure face enqueues one job
    per supported type and a missing executor would reject those jobs
    *terminally*. A probe that scripts one type therefore has to supply
    something for the other; this is the something — it never fails, never
    observes and never counts anything a test asserts on.
    """

    def __init__(self, projection_type: str, detail: str = "noop") -> None:
        self.projection_type = projection_type
        self.detail = detail
        self.calls = 0

    def base_version(self, turn: TurnRecordData) -> Result[str]:
        del turn
        return Ok(f"bv-{self.projection_type}")

    def project(self, view: ProjectionJobView) -> Result[str]:
        del view
        self.calls += 1
        return Ok(self.detail)


def complete_executors(
    *executors: ProjectionExecutor,
) -> tuple[ProjectionExecutor, ...]:
    """The given executors plus a no-op filler for every supported type they
    do not cover (P4-3: a complete set is now a construction requirement)."""

    present = {executor.projection_type for executor in executors}
    fillers = tuple(
        NoopProjectionExecutor(type_word)
        for type_word in SUPPORTED_PROJECTION_TYPES
        if type_word not in present
    )
    return (*executors, *fillers)


@pytest.fixture()
def episode_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteEpisodeStore:
    """The durable episode projection rows (migration 0010)."""

    return SqliteEpisodeStore(db, fence)


@pytest.fixture()
def episode_projection(
    store: SqliteConversationStore,
    episode_store: SqliteEpisodeStore,
    relationship_controller: RelationshipController,
) -> EpisodeProjectionExecutor:
    """The live EPISODE executor (P4-3 ①): the real episode store, the real
    relationship read face and the real conversation store."""

    return EpisodeProjectionExecutor(
        store=episode_store,
        controller=relationship_controller,
        conversation=store,
        user_id=REL_USER,
    )


@pytest.fixture()
def projection_runtime(
    projection_store: SqliteProjectionStore,
    store: SqliteConversationStore,
    relationship_projection: RelationshipProjectionExecutor,
    episode_projection: EpisodeProjectionExecutor,
) -> CP4ProjectionRuntime:
    """The CP4 runtime over the real durable queue and turn source.

    P4-3: one executor per entry of ``SUPPORTED_PROJECTION_TYPES`` — the
    runtime enqueues and dispatches a job per supported type, so an assembly
    that registered only the RELATIONSHIP executor would reject every
    EPISODE job as unsupported (an incomplete assembly, not a legitimate
    one).
    """

    return CP4ProjectionRuntime(
        store=projection_store,
        executors=(relationship_projection, episode_projection),
        turns=store,
    )


@pytest.fixture()
def projecting_coordinator(
    store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    conversation: ConvId,
    projection_runtime: CP4ProjectionRuntime,
) -> ConversationCoordinator:
    """The P3-1A/P3-1B assembly *plus* the CP4 port: every turn that ends Ok
    runs its post-turn projections (one per supported type, P4-3) after the
    guard is released."""

    del conversation
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        projections=projection_runtime,
    )


# -- P4-3: Episode / disclosure / persona views -----------------------------


@pytest.fixture()
def user_config_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteUserConfigStore:
    """The durable profile / disclosure rows (migration 0010)."""

    return SqliteUserConfigStore(db, fence)


@pytest.fixture()
def user_config_controller(
    user_config_store: SqliteUserConfigStore,
) -> UserConfigController:
    return UserConfigController(user_config_store)


@pytest.fixture()
def persona_views(
    relationship_controller: RelationshipController,
    episode_store: SqliteEpisodeStore,
    user_config_controller: UserConfigController,
) -> ControllerPersonaViews:
    """The domain composition the coordinator asks for its §11 views."""

    return ControllerPersonaViews(
        relationship=relationship_controller,
        episodes=episode_store,
        user_config=user_config_controller,
        user_id=REL_USER,
    )


class RecordingProvider(ScriptedPersonaProvider):
    """Scripted provider that keeps every compiled prompt it was handed
    (the tests/phase3 provider, owned here too so the P4-3 E2E can read the
    prompt the live coordinator actually compiled)."""

    def __init__(self) -> None:
        super().__init__()
        self.prompts: list[CompiledPrompt] = []

    def call(self, prompt: CompiledPrompt):
        self.prompts.append(prompt)
        return super().call(prompt)

    @property
    def prompt_texts(self) -> list[str]:
        return [prompt.prompt_text for prompt in self.prompts]


def make_viewing_coordinator(
    store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: TeachingTargetProvider,
    provider: ScriptedPersonaProvider,
    *,
    projections: CP4ProjectionRuntime | None = None,
    persona_views: ControllerPersonaViews | None = None,
) -> ConversationCoordinator:
    """The P3-1A assembly with a chosen provider plus the two P4 ports.

    The provider is a parameter (not a fixture) because the E2E pins what the
    *compiled prompt* contained, which means reading the prompt the live
    pipeline handed to the provider.
    """

    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        provider,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        projections=projections,
        persona_views=persona_views,
    )


def episode_rows(db: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Every durable episode row, in conversation order."""

    return db.execute(
        "SELECT episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at"
        " FROM episode ORDER BY conversation_id"
    ).fetchall()


def episode_row(
    db: sqlite3.Connection, conversation_id: ConvId
) -> tuple[object, ...]:
    row = db.execute(
        "SELECT episode_id, conversation_id, version,"
        " source_turn_sequence_start, source_turn_sequence_end, summary,"
        " open_threads, recent_events, status, updated_at"
        " FROM episode WHERE conversation_id = ?",
        (str(conversation_id),),
    ).fetchone()
    assert row is not None, f"episode not durable for {conversation_id}"
    return tuple(row)


def profile_row(db: sqlite3.Connection, user_id: UserId) -> tuple[object, ...]:
    row = db.execute(
        "SELECT user_profile_id, revision, profile_facts, preferences,"
        " settings, updated_at FROM user_profile WHERE user_profile_id = ?",
        (str(user_id),),
    ).fetchone()
    assert row is not None, f"user profile not durable for {user_id}"
    return tuple(row)


def policy_row(db: sqlite3.Connection, user_id: UserId) -> tuple[object, ...]:
    row = db.execute(
        "SELECT disclosure_policy_id, revision, rules, updated_at"
        " FROM disclosure_policy WHERE disclosure_policy_id = ?",
        (str(user_id),),
    ).fetchone()
    assert row is not None, f"disclosure policy not durable for {user_id}"
    return tuple(row)


def record_projection(conversation) -> None:
    """Consume the projection result of one teaching reply (keeps the driver
    above honest about what a reply returns)."""

    del conversation


def profile(
    *facts: ProfileFact,
    revision: str = "rev-1",
    preferences: tuple[str, ...] = (),
    settings: tuple[str, ...] = (),
    user_id: UserId = REL_USER,
) -> UserProfile:
    """One profile with the given facts (the write face's input)."""

    return UserProfile(
        user_profile_id=user_id,
        revision=revision,
        profile_facts=facts,
        preferences=preferences,
        settings=settings,
    )


def fact(
    text: str,
    sensitivity: MemorySensitivityClass = MemorySensitivityClass.PERSONAL,
) -> ProfileFact:
    return ProfileFact(text=text, sensitivity=sensitivity)


def policy(
    *rules: DisclosureRule,
    revision: str = "pol-1",
    user_id: UserId = REL_USER,
) -> DisclosurePolicy:
    """One disclosure policy keyed by its user (the Local V1 convention)."""

    return DisclosurePolicy(
        disclosure_policy_id=str(user_id),
        revision=revision,
        rules=rules,
    )


def rule(
    level: DisclosureLevel, persona_id: PersonaId | None = None
) -> DisclosureRule:
    """One disclosure rule; ``persona_id=None`` is the default rule."""

    return DisclosureRule(persona_id=persona_id, disclosure_level=level)


def projection_job_rows(db: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Every durable projection_job row, in durable order."""

    return db.execute(
        "SELECT projection_id, projection_type, source_turn_id,"
        " source_turn_slice_hash, base_domain_version, status,"
        " attempt_count, created_at, updated_at"
        " FROM projection_job"
        " ORDER BY created_at, projection_id"
    ).fetchall()


def projection_job_row(
    db: sqlite3.Connection, projection_id: ProjectionJobId
) -> tuple[object, ...]:
    row = db.execute(
        "SELECT projection_id, projection_type, source_turn_id,"
        " source_turn_slice_hash, base_domain_version, status,"
        " attempt_count, created_at, updated_at"
        " FROM projection_job WHERE projection_id = ?",
        (str(projection_id),),
    ).fetchone()
    assert row is not None, f"projection job not durable: {projection_id}"
    return tuple(row)


# -- P4-4: the full-chain probes and the fault-injection seams --------------
#
# The P4-4 suites (test_p4_4_full_chain / test_p4_4_stress) drive the *real*
# assembly, so their fault injection has to happen at a seam the real chain
# already has — never by replacing the chain. There are exactly three such
# seams, and they live here once (the ``ScriptedCandidates`` precedent: a
# helper several phase-4 files share belongs to the conftest).


class ProbeExecutor:
    """A real executor plus the two probe capabilities P4-4 needs.

    Every face delegates to the wrapped executor, so a probe without a
    configured fault *is* the real chain. Two knobs:

    - ``observe(lease, conn, conversation)`` records the guard and the open
      transaction *from inside* ``project`` (the RA §19/§24.1 pin, taken on
      the full chain);
    - ``failure`` — a ``DomainError`` returned instead of delegating. The
      refusal travels the executor face (``project()``), which is exactly
      where a real executor's ``Err`` comes from (a refusing candidate
      provider, a store write refusal), so the runtime's code mapping
      (retryable vs deterministic) is exercised for real.
    """

    def __init__(self, inner: ProjectionExecutor) -> None:
        self._inner = inner
        self.failure: DomainError | None = None
        self.calls = 0
        self.lease_held: bool | None = None
        self.in_transaction: bool | None = None
        self._observer: tuple[Any, Any, ConvId] | None = None

    @property
    def projection_type(self) -> str:
        return self._inner.projection_type

    def observe(self, lease: Any, conn: Any, conversation: ConvId) -> None:
        self._observer = (lease, conn, conversation)

    def base_version(self, turn: TurnRecordData) -> Result[str]:
        return self._inner.base_version(turn)

    def project(self, view: ProjectionJobView) -> Result[str]:
        self.calls += 1
        if self._observer is not None:
            lease, conn, conversation = self._observer
            self.lease_held = lease.is_held(conversation)
            self.in_transaction = bool(conn.in_transaction)
        if self.failure is not None:
            return Err(self.failure)
        return self._inner.project(view)

    def fail_with(self, code: DomainErrorCode, message: str) -> None:
        self.failure = DomainError(code=code, message=message)


class PerConversationCandidates:
    """A MODEL_PROPOSAL source that answers per conversation.

    ``ScriptedCandidates`` answers every turn identically, which cannot
    express the isolation suites' requirement (each persona's memory must
    carry marker text of its own). This provider keys its answer by the
    turn's conversation, through the same real executor.
    """

    def __init__(self, by_conversation: dict[str, str]) -> None:
        self.by_conversation = by_conversation
        self.calls = 0

    def candidates_for(self, turn) -> Result[tuple[Any, ...]]:
        self.calls += 1
        content = self.by_conversation.get(str(turn.conversation_id))
        if content is None:
            return Ok(())
        return Ok((memory_candidate(content),))


class RefusingCandidates:
    """A candidate provider with a switchable refusal and a payload.

    ``failure`` set ⇒ every read is ``Err`` (the transient provider failure
    the retry rules are about). ``heal()`` clears it and answers
    ``content`` — the retry's positive control, so the landed memory is a
    real assertion rather than an empty projection.
    """

    def __init__(
        self,
        content: str = "healed after the retry",
        code: DomainErrorCode = DomainErrorCode.DEPENDENCY_UNAVAILABLE,
        message: str = "candidate provider offline (injected)",
    ) -> None:
        self.content = content
        self.failure: DomainError | None = DomainError(code=code, message=message)
        self.calls = 0

    def candidates_for(self, turn) -> Result[tuple[Any, ...]]:
        del turn
        self.calls += 1
        if self.failure is not None:
            return Err(self.failure)
        return Ok((memory_candidate(self.content),))

    def heal(self) -> None:
        self.failure = None


class FlakyClassifier:
    """The durable command-turn classifier with a switchable read failure.

    ``RelationshipRecorder`` takes its classifier as a port; wrapping the
    real store's face is how a *classifier* read failure is injected without
    touching the recorder (whose fail-closed rule is P4-1 behavior and stays
    pinned by the P4-1 tests).
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.failure: DomainError | None = None
        self.calls = 0

    def is_command_payload_turn(self, turn_id: TurnId) -> Result[bool]:
        self.calls += 1
        if self.failure is not None:
            return Err(self.failure)
        return self._inner.is_command_payload_turn(turn_id)

    def fail_with(self, code: DomainErrorCode, message: str) -> None:
        self.failure = DomainError(code=code, message=message)

    def heal(self) -> None:
        self.failure = None


def runtime_with_probes(
    projection_store: SqliteProjectionStore,
    turns: SqliteConversationStore,
    *executors: ProjectionExecutor,
) -> tuple[CP4ProjectionRuntime, tuple[ProbeExecutor, ...]]:
    """A CP4 runtime over probe-wrapped copies of the given executors.

    The executors must already cover ``SUPPORTED_PROJECTION_TYPES`` (the
    runtime refuses an incomplete set at construction — P4-3 review LOW-2),
    and the returned tuple answers them in the same order.
    """

    probes = tuple(ProbeExecutor(executor) for executor in executors)
    runtime = CP4ProjectionRuntime(
        store=projection_store, executors=probes, turns=turns
    )
    return runtime, probes


def relationship_projection_with(
    store: SqliteConversationStore,
    controller: RelationshipController,
    candidates: Any,
    *,
    classifier: Any | None = None,
) -> RelationshipProjectionExecutor:
    """The ``relationship_projection`` fixture's executor with chosen seams.

    The fixture is the happy path (the real store as classifier,
    ``ScriptedCandidates`` as the proposal source); the P4-4 suites need the
    same executor with a *different* provider (per-conversation text, a
    refusal, an empty answer) or a flaky classifier — parameters of the two
    seams the executor already declares, never a second assembly.
    """

    return RelationshipProjectionExecutor(
        recorder=RelationshipRecorder(classifier if classifier is not None else store),
        controller=controller,
        conversation=store,
        user_id=REL_USER,
        candidates=candidates,
    )
