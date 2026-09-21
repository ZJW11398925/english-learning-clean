"""Shared fixtures for the Phase 2 P2A tests (Learning durable core,
TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.30).

Each test gets a fresh in-memory app.db with migrations through 0004, an
opened runtime epoch, and the learning / conversation / generation stores
bound to that epoch.
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

import pytest

from elc.conversation import CommitUserTurn, Cp0Commit, SqliteConversationStore
from elc.learning.store import SqliteLearningStore
from elc.learning.types import (
    AttemptOutcome,
    ErrorAttribution,
    EvidenceClaimView,
    EvidenceGroupRecord,
    EvidencePolarity,
    EvidenceQualifier,
    EvidenceStatus,
    ExposureLevel,
    PerformanceType,
    SupportLevel,
)
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ClientMessageId,
    EvaluatorVersion,
    EvidenceGroupId,
    EvidenceModality,
    InputId,
    InteractionChannel,
    Ok,
    TargetId,
    UserId,
)
from elc.platform.types import ConversationId as ConvId
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.types import InputEnvelope
from tests.conftest import AssemblyGenerationStore

CONV = ConvId("conv-p2a")
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
) -> AssemblyGenerationStore:
    return AssemblyGenerationStore(db, fence)


@pytest.fixture()
def conversation(store: SqliteConversationStore) -> ConvId:
    result = store.open_conversation(
        CONV, user_id=UserId("user-1"), persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok)
    return result.value


def make_envelope(
    conversation_id: ConvId,
    client_message_id: str,
    raw_payload: str = "raw-payload",
) -> InputEnvelope:
    return InputEnvelope(
        input_id=InputId(f"in-{client_message_id}"),
        client_message_id=ClientMessageId(client_message_id),
        conversation_id=str(conversation_id),
        persona_id=None,
        scene_id=None,
        interaction_channel=InteractionChannel.TEXT,
        raw_payload=raw_payload,
        received_at=RECEIVED_AT,
    )


def commit_ok(
    store: SqliteConversationStore,
    conversation_id: ConvId,
    client_message_id: str,
    raw_content: str,
) -> Cp0Commit:
    command = CommitUserTurn(
        conversation_id=conversation_id,
        envelope=make_envelope(conversation_id, client_message_id),
        raw_content=raw_content,
        runtime_version=RUNTIME_VERSION,
    )
    result = store.commit_user_turn(command)
    assert isinstance(result, Ok), f"CP0 failed: {result}"
    return result.value


def canonical_slice(
    store: SqliteConversationStore, cp0: Cp0Commit
):
    slice_result = store.get_canonical_turn_slice(cp0.turn_id)
    assert isinstance(slice_result, Ok) and slice_result.value is not None
    return slice_result.value


def make_claim(
    *,
    polarity: EvidencePolarity = EvidencePolarity.POSITIVE,
    performance_type: PerformanceType = PerformanceType.RECOGNITION,
    outcome: AttemptOutcome = AttemptOutcome.SUCCESS,
    qualifiers: tuple[EvidenceQualifier, ...] = (),
    claim_role: str = "primary",
    scope: str = "RESOURCE",
    confidence: float = 0.9,
) -> EvidenceClaimView:
    return EvidenceClaimView(
        evidence_claim_id="ecl-pending",
        claim_role=claim_role,
        scope=scope,
        performance_type=performance_type,
        evidence_modality=EvidenceModality.TEXT_PRODUCTION,
        qualifiers=qualifiers,
        polarity=polarity,
        outcome=outcome,
        support=SupportLevel.NONE,
        exposure=ExposureLevel.NONE,
        evaluator_confidence=confidence,
        error_attribution=ErrorAttribution.UNKNOWN,
        accuracy=None,
        pragmatic_fit=None,
        status=EvidenceStatus.ACTIVE,
        provenance="test",
    )


def make_group(
    group_id: str,
    claims: tuple[EvidenceClaimView, ...],
    target_id: str = "res-1",
) -> EvidenceGroupRecord:
    return EvidenceGroupRecord(
        evidence_group_id=EvidenceGroupId(group_id),
        moment_id=None,
        attempt_id=None,
        target_id=TargetId(target_id),
        evaluator_version=EvaluatorVersion("evaluator-test-v1"),
        claims=claims,
    )


def make_coordinator(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    provider: ScriptedPersonaProvider,
    learning: SqliteLearningStore | None = None,
):
    # Migration 0007: every generation action belongs to a DecisionCycle —
    # the fixture pair carries both stores (AssemblyGenerationStore).
    decision_cycles = (
        generation_store.decision_cycles
        if isinstance(generation_store, AssemblyGenerationStore)
        else None
    )
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
        learning=learning,
        decision_cycles=decision_cycles,
    )


def make_lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder
