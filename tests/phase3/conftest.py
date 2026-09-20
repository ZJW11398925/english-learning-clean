"""Shared fixtures for the Phase 3 P3-0 tests (entry gates).

Each test gets a fresh in-memory app.db (migrations through 0006), an
opened runtime epoch, and the learning / conversation / generation stores
bound to that epoch. Claim/group builders are reused from
tests/phase2/conftest.py, which stays their owner.
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

import pytest

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.persona.types import CharacterPackageRecord
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ClientMessageId,
    InputId,
    InteractionChannel,
    Ok,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.types import InputEnvelope

CONV = ConvId("conv-p3")
RUNTIME_VERSION = "runtime-v1"
RECEIVED_AT = "2026-09-20T08:00:00+00:00"


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
def store(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def generation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteGenerationStore:
    return SqliteGenerationStore(db, fence)


@pytest.fixture()
def conversation(store: SqliteConversationStore) -> ConvId:
    result = store.open_conversation(
        CONV, user_id=UserId("user-1"), persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok)
    return result.value


def make_lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder


def make_coordinator(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    provider: ScriptedPersonaProvider,
    character_package: CharacterPackageRecord | None = None,
) -> ConversationCoordinator:
    """P3-0 ③ assembly face: the coordinator with an optional injected
    canonical §5.1 CharacterPackage (None keeps the P1/P2 assembly)."""

    persona = PersonaRuntime(
        actions=generation_store,
        provider=provider,
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=store,
        conversation_queries=store,
        persona=persona,
        generation_actions=generation_store,
        character_package=character_package,
    )


def begin_turn_ok(
    coordinator: ConversationCoordinator,
    conversation: ConvId,
    client_message_id: str,
    raw_content: str,
):
    """Drive one full turn through the coordinator and unwrap the
    completion (the Ok path is the expected normal path)."""

    command = CommitUserTurn(
        conversation_id=conversation,
        envelope=InputEnvelope(
            input_id=InputId(f"in-{client_message_id}"),
            client_message_id=ClientMessageId(client_message_id),
            conversation_id=str(conversation),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload="raw-payload",
            received_at=RECEIVED_AT,
        ),
        raw_content=raw_content,
        runtime_version=RUNTIME_VERSION,
    )
    result = coordinator.begin_turn(command)
    assert isinstance(result, Ok), f"begin_turn failed: {result}"
    return result.value
