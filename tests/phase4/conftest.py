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

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.persona import ScriptedPersonaProvider
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    InputId,
    InteractionChannel,
    Ok,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
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
