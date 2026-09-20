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

Degradation semantics (RA §21; review F1 fix TASK-…37):
- Learning's REJECT decision (unobservable proposal) → the artifact stays
  durably REJECTED and the turn continues on the normal persona path.
- Commit unavailable (any other learning-leg failure) → the durable
  proposal stays PRODUCED (pending), no retry, and the turn continues.
- Because no learning-leg failure blocks the turn, no dispatch can pin a
  turn at ANALYZING: the permanent stuck loop of review F1 (ANALYZING +
  REJECTED artifact → re-entry CONFLICT, no terminalize path) is
  unreachable — pinned below by the blank-utterance and
  crash-at-ANALYZING-with-REJECTED tests.
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


class CommitUnavailableLearningLeg:
    """Fault-injection stand-in for RA §21 'Learning commit unavailable':
    the durable analysis leg works (the proposal lands PRODUCED) but the
    CP1 commit fails like an unavailable dependency."""

    def __init__(self, inner: SqliteLearningStore) -> None:
        self._inner = inner

    def record_learning_analysis(self, turn):  # type: ignore[no-untyped-def]
        return self._inner.record_learning_analysis(turn)

    def commit_learning_evidence(self, proposal, turn, persona_id=None):  # type: ignore[no-untyped-def]
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="injected commit unavailability",
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


def test_learning_leg_failure_degrades_to_normal_persona(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """RA §21 degradation (replaces the pre-fix expectation that a
    learning-leg failure pins the turn at ANALYZING — review F1): the
    user still gets the normal persona reply, the turn terminalizes,
    and no evidence is committed. After the fault heals, the next turn
    runs the full chain — a degraded turn poisons nothing."""
    provider = ScriptedPersonaProvider()
    broken = BrokenLearningLeg()
    coordinator = _coordinator(
        store, generation_store, fence.current, provider, broken
    )
    degraded = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-degraded", "degraded turn")
    )
    assert isinstance(degraded, Ok), degraded
    assert degraded.value.reply_text is not None
    assert degraded.value.outcome == "REPLIED_FULL"
    assert provider.call_count == 1  # normal persona generation ran
    row = db.execute(
        "SELECT status, turn_outcome FROM turn_record"
        " WHERE input_id = 'in-cm-degraded'"
    ).fetchone()
    assert row[0] == "COMPLETED"  # never pinned at ANALYZING
    assert row[1] == "REPLIED_FULL"
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0
    assert learning.get_evidence_watermark() == 0

    # 愈合：the healed coordinator commits the NEXT turn's evidence.
    healed = _coordinator(
        store, generation_store, fence.current, provider, learning
    )
    completed = healed.begin_turn(
        _turn_command(store, conversation, "cm-healed", "healed turn")
    )
    assert isinstance(completed, Ok), completed
    assert learning.get_evidence_watermark() == 1
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1


def test_commit_unavailability_leaves_durable_pending_proposal(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """RA §21 'Learning commit unavailable → durable proposal pending +
    normal persona': the artifact stays PRODUCED (durable pending, no
    retry, no block) and a duplicate dispatch replays the terminal
    without touching it."""
    provider = ScriptedPersonaProvider()
    unavailable = CommitUnavailableLearningLeg(learning)
    coordinator = _coordinator(
        store, generation_store, fence.current, provider, unavailable
    )
    completion = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-pending", "pending proposal")
    )
    assert isinstance(completion, Ok), completion
    assert completion.value.reply_text is not None
    turn_id = completion.value.turn_id

    artifact = db.execute(
        "SELECT status FROM analysis_artifact WHERE turn_id = ?", (turn_id,)
    ).fetchone()
    assert artifact is not None
    assert artifact[0] == "PRODUCED"  # durable pending
    assert learning.get_evidence_watermark() == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0

    replay = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-pending", "pending proposal")
    )
    assert isinstance(replay, Ok), replay
    assert replay.value.outcome == "REPLIED_FULL"
    assert db.execute(
        "SELECT status FROM analysis_artifact WHERE turn_id = ?", (turn_id,)
    ).fetchone()[0] == "PRODUCED"  # untouched by the terminal replay
    assert learning.get_evidence_watermark() == 0


def test_blank_utterance_rejected_degrades_with_reply_no_deadlock(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """Blank utterance (CP0 does not gate raw_content): the analysis
    proposes observable=false, Learning REJECTS it durably — and the
    turn still completes with the normal persona reply, the artifact
    stays REJECTED, and a duplicate dispatch replays the terminal. The
    pre-fix behavior (Err return → turn pinned ANALYZING → re-entry
    CONFLICT forever) is the permanent deadlock of review F1."""
    provider = ScriptedPersonaProvider()
    coordinator = _coordinator(
        store, generation_store, fence.current, provider, learning
    )
    completion = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-blank", "   ")
    )
    assert isinstance(completion, Ok), completion
    assert completion.value.reply_text is not None
    assert completion.value.outcome == "REPLIED_FULL"
    turn_id = completion.value.turn_id
    artifact = db.execute(
        "SELECT status FROM analysis_artifact WHERE turn_id = ?", (turn_id,)
    ).fetchone()
    assert artifact is not None
    assert artifact[0] == "REJECTED"  # audit trail stays REJECTED
    assert learning.get_evidence_watermark() == 0
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 0

    replay = coordinator.begin_turn(
        _turn_command(store, conversation, "cm-blank", "   ")
    )
    assert isinstance(replay, Ok), replay  # no CONFLICT loop
    assert replay.value.turn_id == turn_id
    assert replay.value.reply_text is not None


def test_crash_at_analyzing_with_rejected_artifact_progresses(
    db: sqlite3.Connection,
    learning: SqliteLearningStore,
    store,
    generation_store,
    fence: RuntimeEpochFence,
    conversation,
) -> None:
    """The exact stuck path of review F1, crash-shaped: the turn sits at
    ANALYZING with the artifact already REJECTED, then the process
    restarts. Re-dispatch under the new epoch degrades and finishes the
    turn — the re-entry CONFLICT loop is gone (no terminalize channel
    is needed because the degraded leg always advances the turn)."""
    from elc.conversation.store import SqliteConversationStore
    from elc.platform.db import epoch as epoch_module
    from elc.platform.db.generation_store import SqliteGenerationStore

    command = _turn_command(store, conversation, "cm-stuck", "   ")
    cp0 = commit_ok(store, conversation, "cm-stuck", "   ")

    # Learning already REJECTED the durable proposal, then "crash" with
    # the turn still at ANALYZING.
    slice_result = store.get_canonical_turn_slice(cp0.turn_id)
    assert isinstance(slice_result, Ok) and slice_result.value is not None
    artifact = learning.record_learning_analysis(slice_result.value)
    assert isinstance(artifact, Ok)
    rejected = learning.commit_learning_evidence(
        artifact.value, slice_result.value, "persona-default"
    )
    assert isinstance(rejected, Err)
    advanced = store.transition_turn(cp0.turn_id, 1, TurnStatus.ANALYZING)
    assert isinstance(advanced, Ok)

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
    assert completion.value.reply_text is not None
    assert completion.value.outcome == "REPLIED_FULL"
    assert new_learning.get_evidence_watermark() == 0
    row = db.execute(
        "SELECT status FROM turn_record WHERE turn_id = ?", (cp0.turn_id,)
    ).fetchone()
    assert row[0] == "COMPLETED"  # past ANALYZING, terminal


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
