"""VAL ③ (coordinator wiring) + VAL ④ (two crash states at the
coordinator face) — the full CP0 → analysis → CP1 → persona chain.

RA §4 steps 2-4 canonical order: CP0 → durable AnalysisArtifacts →
Learning validates/commits (CP1, durable watermark) → generation. The
turn rides the STATE_MACHINES §10 ANALYZING slot between USER_COMMITTED
and GENERATING.

Crash semantics (RA §22/§23):
- Crash after CP0 (before analysis/CP1): the new epoch adopts the
  nonterminal turn (RA §24), re-enters at ANALYZING and runs analysis +
  CP1 exactly once — no double evidence.
- Crash after CP1 (turn still ANALYZING): re-entry replays the committed
  CP1 idempotently — no double evidence — and proceeds to generation.
- A turn already GENERATING never re-runs the learning leg.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.conversation.types import ConversationId
from elc.learning.analysis import LearningTurnAnalysis
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.types import TurnStatus
from tests.phase2.conftest import (
    RUNTIME_VERSION,
    commit_ok,
    make_envelope,
)


def _turn_command(
    store: SqliteConversationStore,
    conversation: ConversationId,
    client_message_id: str,
    raw_content: str,
) -> CommitUserTurn:
    return CommitUserTurn(
        conversation_id=conversation,
        envelope=make_envelope(conversation, client_message_id),
        raw_content=raw_content,
        runtime_version=RUNTIME_VERSION,
    )


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    epoch_value: int,
    provider: ScriptedPersonaProvider,
    learning: LearningTurnAnalysis | None,
) -> ConversationCoordinator:
    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(epoch_value)
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
    )


class BrokenLearningLeg:
    """Fault-injection stand-in: every call fails like a crashed leg."""

    def record_learning_analysis(self, turn):  # type: ignore[no-untyped-def]
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="injected learning-leg failure",
            )
        )

    def commit_learning_evidence(self, proposal, turn, persona_id=None):  # type: ignore[no-untyped-def]
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="injected learning-leg failure",
            )
        )


def test_full_chain_cp0_analysis_cp1_then_persona(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    provider = ScriptedPersonaProvider()
    coordinator = _coordinator(
        store, generation_store, fence.current, provider, learning
    )
    completion = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-full", "the full chain turn")
    )
    assert isinstance(completion, Ok), completion
    turn_id = completion.value.turn_id

    # Artifact: one durable LEARNING_EVIDENCE row, COMMITTED.
    artifact = db.execute(
        "SELECT analysis_type, producer_id, status FROM analysis_artifact"
        " WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert artifact is not None
    assert artifact[0] == "LEARNING_EVIDENCE"
    assert artifact[1] == "deterministic-learning-evidence"
    assert artifact[2] == "COMMITTED"

    # CP1: group + commit + watermark durable before generation ran.
    group = db.execute(
        "SELECT evidence_group_id, source_turn_id, evidence_modality"
        " FROM evidence_group WHERE source_turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert group is not None
    assert group[2] == "TEXT_PRODUCTION"
    assert learning.get_evidence_watermark() == 1
    commit = db.execute(
        "SELECT evidence_commit_id, watermark_after FROM evidence_commit"
    ).fetchone()
    assert commit[1] == 1

    # The turn completed through persona generation.
    assert completion.value.reply_text is not None
    assert completion.value.outcome == "REPLIED_FULL"


def test_learning_leg_failure_pins_turn_at_analyzing(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """A learning-leg failure pins the turn at ANALYZING (the canonical
    order forbids generating before CP1); after the fault clears, the
    re-run completes the chain without double evidence."""
    provider = ScriptedPersonaProvider()
    broken = BrokenLearningLeg()
    coordinator = _coordinator(
        store, generation_store, fence.current, provider, broken
    )
    failed = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-analyzing", "analyzing slot")
    )
    assert not isinstance(failed, Ok)
    row = db.execute(
        "SELECT status FROM turn_record"
        " WHERE input_id = 'in-cm-analyzing'"
    ).fetchone()
    assert row[0] == "ANALYZING"
    assert provider.call_count == 0  # generation never started
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0

    healed = _coordinator(
        store, generation_store, fence.current, provider, learning
    )
    completed = healed.begin_turn(
        _turn_command(store, conversation, "cm-analyzing", "analyzing slot")
    )
    assert isinstance(completed, Ok), completed
    assert learning.get_evidence_watermark() == 1
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1


def test_crash_after_cp0_reentry_commits_evidence_once(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Crash after CP0, before analysis: a new epoch adopts the
    nonterminal turn (RA §24), re-enters at ANALYZING and runs analysis +
    CP1 exactly once."""
    from elc.conversation.store import SqliteConversationStore
    from elc.platform.db import epoch as epoch_module
    from elc.platform.db.generation_store import SqliteGenerationStore

    command = _turn_command(
        store, conversation, "cm-crash0", "crash after cp0"
    )
    commit_ok(store, conversation, "cm-crash0", "crash after cp0")

    # "Crash": the turn sits at USER_COMMITTED under the old epoch; a
    # restart opens a newer epoch and re-dispatches the same input with
    # stores bound to the new fence (P1 recovery convention).
    new_fence = epoch_module.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)
    new_generation = SqliteGenerationStore(db, new_fence)
    new_learning = SqliteLearningStore(db, new_fence)
    provider = ScriptedPersonaProvider()
    coordinator = _coordinator(
        new_store, new_generation, new_fence.current, provider, new_learning
    )
    completion = coordinator.begin_turn(command)
    assert isinstance(completion, Ok), completion

    assert db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM evidence_commit").fetchone()[0] == 1
    assert new_learning.get_evidence_watermark() == 1


def test_crash_after_cp1_reentry_does_not_repeat_evidence(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Crash after CP1 with the turn still ANALYZING: re-entry replays
    the committed CP1 (same watermark) and finishes the turn through
    generation."""
    from elc.conversation.store import SqliteConversationStore
    from elc.platform.db import epoch as epoch_module
    from elc.platform.db.generation_store import SqliteGenerationStore

    command = _turn_command(
        store, conversation, "cm-crash1", "crash after cp1"
    )
    cp0 = commit_ok(store, conversation, "cm-crash1", "crash after cp1")

    # Analysis + CP1 committed, then "crash" before GENERATING.
    slice_result = store.get_canonical_turn_slice(cp0.turn_id)
    assert isinstance(slice_result, Ok) and slice_result.value is not None
    artifact = learning.record_learning_analysis(slice_result.value)
    assert isinstance(artifact, Ok)
    commit = learning.commit_learning_evidence(
        artifact.value, slice_result.value, "persona-default"
    )
    assert isinstance(commit, Ok)
    advanced = store.transition_turn(
        cp0.turn_id, 1, TurnStatus.ANALYZING
    )
    assert isinstance(advanced, Ok)
    assert learning.get_evidence_watermark() == 1

    new_fence = epoch_module.open_runtime_epoch(db)
    new_store = SqliteConversationStore(db, new_fence)
    new_generation = SqliteGenerationStore(db, new_fence)
    new_learning = SqliteLearningStore(db, new_fence)
    provider = ScriptedPersonaProvider()
    coordinator = _coordinator(
        new_store, new_generation, new_fence.current, provider, new_learning
    )
    completion = coordinator.begin_turn(command)
    assert isinstance(completion, Ok), completion

    # No double evidence: replay returned the original commit.
    assert new_learning.get_evidence_watermark() == 1
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM evidence_commit").fetchone()[0] == 1


def test_phase1_assembly_without_learning_stays_usable(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """learning=None keeps the Phase 1 loop (the P1 tests pin it): no
    ANALYZING slot, no analysis artifacts."""
    provider = ScriptedPersonaProvider()
    coordinator = _coordinator(
        store, generation_store, fence.current, provider, None
    )
    completion = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-p1", "phase one behavior")
    )
    assert isinstance(completion, Ok), completion
    assert db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
