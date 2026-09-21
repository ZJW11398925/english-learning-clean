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
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
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
from tests.conftest import AssemblyGenerationStore

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
) -> AssemblyGenerationStore:
    return AssemblyGenerationStore(db, fence)


@pytest.fixture()
def decision_cycle_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteDecisionCycleStore:
    """The Runtime-owned DecisionCycle store over the same app.db + epoch
    fence (migration 0007: every generation action belongs to a cycle, so
    every assembly that opens a turn needs both stores)."""

    return SqliteDecisionCycleStore(db, fence)


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

    decision_cycles = (
        generation_store.decision_cycles
        if isinstance(generation_store, AssemblyGenerationStore)
        else None
    )
    persona = make_persons_runtime(generation_store, provider, max_provider_attempts)
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=store,
        conversation_queries=store,
        persona=persona,
        generation_actions=generation_store,
        decision_cycles=decision_cycles,
    )


def seed_decision_cycle(
    db: sqlite3.Connection, turn_id: str, cycle_id: str | None = None
) -> str:
    """Seed one raw §4 DecisionCycle row for tests that build generation
    actions by hand.

    Migration 0007 tightens ``generation_action_intent.decision_cycle_id``
    to NOT NULL + FK(decision_cycle): every action belongs to a cycle, so a
    hand-built action needs a parent row. Deliberately raw (no
    active_decision_cycle_id pointer, no state_version CAS bump) — these
    flows drive the TurnRecord themselves and keep their own state_version
    arithmetic.
    """

    resolved = cycle_id if cycle_id is not None else f"dcy-{turn_id}"
    db.execute(
        "INSERT INTO decision_cycle (decision_cycle_id, turn_id, cycle_index,"
        " created_at) VALUES (?, ?, 0, '2026-09-20T00:00:00+00:00')",
        (resolved, turn_id),
    )
    db.commit()  # the seed leaves no open transaction for the store units
    return resolved


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
