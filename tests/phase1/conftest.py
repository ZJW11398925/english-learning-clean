"""Shared fixtures for the Phase 1 tests (P1A TASK-OPI-091f35c3.11 +
P1B TASK-OPI-d7937fd7.9).

Each test gets a fresh in-memory app.db with migrations applied, an opened
runtime epoch, and the durable conversation / generation stores bound to
that epoch.
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

import pytest

from elc.conversation import CommitUserTurn, Cp0Commit, SqliteConversationStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
    SqliteGenerationStore,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    Ok,
    UserId,
)
from elc.runtime import ConversationCoordinatorLease
from elc.runtime.types import InputEnvelope

CONV = ConversationId("conv-p1a")
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
def store(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def generation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteGenerationStore:
    return SqliteGenerationStore(db, fence)


@pytest.fixture()
def lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder


@pytest.fixture()
def conversation(store: SqliteConversationStore) -> ConversationId:
    result = store.open_conversation(
        CONV, user_id=UserId("user-1"), persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok)
    return result.value


def make_persons_runtime(
    generation_store: SqliteGenerationStore,
    provider: ScriptedPersonaProvider,
    max_provider_attempts: int = 3,
) -> PersonaRuntime:
    """Assemble the PersonaRuntime with deterministic fake pieces."""

    return PersonaRuntime(
        actions=generation_store,
        provider=provider,
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=max_provider_attempts,
    )


def make_coordinator(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    provider: ScriptedPersonaProvider,
    max_provider_attempts: int = 3,
):
    from elc.runtime import ConversationCoordinator

    persona = make_persons_runtime(generation_store, provider, max_provider_attempts)
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=store,
        conversation_queries=store,
        persona=persona,
        generation_actions=generation_store,
    )


def make_envelope(
    conversation_id: ConversationId,
    client_message_id: str | None,
    input_id: str | None = None,
    raw_payload: str = "raw-payload",
) -> InputEnvelope:
    """Build an InputEnvelope (DATA_MODEL §4) with generated stable IDs."""
    resolved_input = input_id if input_id is not None else f"in-{client_message_id}"
    return InputEnvelope(
        input_id=InputId(resolved_input),
        client_message_id=(
            ClientMessageId(client_message_id)
            if client_message_id is not None
            else None
        ),
        conversation_id=str(conversation_id),
        persona_id=None,
        scene_id=None,
        interaction_channel=InteractionChannel.TEXT,
        raw_payload=raw_payload,
        received_at=RECEIVED_AT,
    )


def commit_ok(
    store: SqliteConversationStore,
    conversation_id: ConversationId,
    client_message_id: str,
    raw_content: str,
) -> Cp0Commit:
    """Run CP0 and unwrap the result (test helper: the Ok path is expected)."""
    command = CommitUserTurn(
        conversation_id=conversation_id,
        envelope=make_envelope(conversation_id, client_message_id),
        raw_content=raw_content,
        runtime_version=RUNTIME_VERSION,
    )
    result = store.commit_user_turn(command)
    assert isinstance(result, Ok), f"CP0 failed: {result}"
    return result.value
