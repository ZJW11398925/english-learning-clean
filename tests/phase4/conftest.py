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
from typing import Iterator

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
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ClientMessageId,
    InputId,
    InteractionChannel,
    MessageSequence,
    Ok,
    PersonaId,
    RelationshipMemoryId,
    TurnId,
    TurnSequence,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.relationship import (
    RELATIONSHIP_RECORDER_VERSION,
    MemoryProvenance,
    MemorySensitivityClass,
    PersistenceAuthorization,
    RelationshipController,
    RelationshipMemoryCandidate,
    RelationshipMemoryProposal,
    RelationshipMemoryType,
    RelationshipRecorder,
    RelationshipRecorderKey,
    RelationshipRecorderOutcome,
    SamePersonaExistingRelationshipSummary,
)
from elc.relationship.store import SqliteRelationshipStore
from elc.runtime.controller import ConversationCoordinator, TeachingReplyRequest
from elc.runtime.types import InputEnvelope
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.targets import TeachingTargetProvider
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
