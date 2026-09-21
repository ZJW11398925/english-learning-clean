"""P1B — the six IMPLEMENTATION_PLAN §3 acceptance scenarios as pipeline-
level integration tests (TASK-OPI-d7937fd7.9 deliverable ⑦; VAL ①-⑦).

§3 Acceptance list, in order:

    duplicate input     → test_duplicate_input_replays_terminal_turn
    provider no-output  → test_provider_no_output_fails_terminal_undelivered
    provider retry      → test_provider_retry_stays_action_level
    late callback       → test_late_callback_discarded_* (2 tests)
    crash after user commit
                        → test_crash_after_user_commit_recovers_via_new_epoch
    assistant partial/failure terminalization
                        → test_partial_and_failure_terminalization (2)

And the §3 closing invariant — "此阶段必须已经不需要 retry whole turn" —
is asserted inside every retry/recovery scenario: exactly one user_turn row
and one turn_record row survive, only ProviderAttempt rows multiply.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from elc.conversation import SqliteConversationStore
from elc.persona import (
    ProviderOutput,
    ScriptedPersonaProvider,
    action_intent_for_turn,
    no_output,
    normal_output,
)
from elc.platform.db import epoch
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import ConversationId, Ok
from elc.runtime import (
    ConversationCoordinatorLease,
    StartupRecoveryScanner,
)
from elc.runtime.types import (
    GenerationActionStatus,
    GenerationActionType,
    ProviderAttemptRecord,
    TurnStatus,
)
from tests.conftest import AssemblyGenerationStore

from .conftest import (
    RUNTIME_VERSION,
    commit_ok,
    make_coordinator,
    make_envelope,
    seed_decision_cycle,
)

# Full-literal count statements (no identifier assembly).
_COUNT_SQL = {
    "user_turn": "SELECT COUNT(*) FROM user_turn",
    "turn_record": "SELECT COUNT(*) FROM turn_record",
    "assistant_turn": "SELECT COUNT(*) FROM assistant_turn",
    "provider_attempt": "SELECT COUNT(*) FROM provider_attempt",
    "generation_action_intent": "SELECT COUNT(*) FROM generation_action_intent",
}


def _count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(_COUNT_SQL[table]).fetchone()[0])


def _command(conversation_id: ConversationId, client_message_id: str, text: str):
    from elc.conversation import CommitUserTurn

    return CommitUserTurn(
        conversation_id=conversation_id,
        envelope=make_envelope(conversation_id, client_message_id),
        raw_content=text,
        runtime_version=RUNTIME_VERSION,
    )


def _no_whole_turn_retry(db: sqlite3.Connection) -> None:
    """§3 closing invariant: no scenario ever rebuilt the UserTurn or the
    TurnRecord (action-level retry only, R-INV-007)."""

    assert _count(db, "user_turn") == 1
    assert _count(db, "turn_record") == 1


def _unwrap(result: Any) -> Any:
    assert isinstance(result, Ok), f"expected Ok, got {result}"
    return result.value


# ---------------------------------------------------------------------------
# §3 scenario 1 — duplicate input
# ---------------------------------------------------------------------------


def test_duplicate_input_replays_terminal_turn(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 duplicate input / VAL ①: the second begin_turn with the same
    client_message_id replays the durable terminal result — one UserTurn,
    one AssistantTurn, one action, zero re-generation."""

    provider = ScriptedPersonaProvider()
    coordinator = make_coordinator(store, generation_store, lease, provider)

    first = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-dup", "hello"))
    )
    assert first.outcome == "REPLIED_FULL"
    assert first.turn_status == TurnStatus.COMPLETED
    assert first.reply_text

    calls_after_first = provider.call_count

    second = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-dup", "hello"))
    )
    # Same durable turn, same canonical assistant content, nothing re-ran.
    assert second.turn_id == first.turn_id
    assert second.reply_text == first.reply_text
    assert second.outcome == "REPLIED_FULL"
    assert provider.call_count == calls_after_first  # no second generation

    _no_whole_turn_retry(db)
    assert _count(db, "assistant_turn") == 1
    assert _count(db, "generation_action_intent") == 1
    assert _count(db, "provider_attempt") == 1


# ---------------------------------------------------------------------------
# §3 scenario 2 — provider no-output
# ---------------------------------------------------------------------------


def test_provider_no_output_fails_terminal_undelivered(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 provider no-output / VAL ②: every attempt is a durable FAILED
    ProviderAttempt; the bounded budget ends with the action TERMINAL
    undelivered and the turn FAILED_FINAL — nothing enters the transcript."""

    provider = ScriptedPersonaProvider(
        script=(no_output(), no_output(), no_output())
    )
    coordinator = make_coordinator(store, generation_store, lease, provider)

    result = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-empty", "hi"))
    )
    assert result.outcome == "FAILED_USER_VISIBLE"
    assert result.turn_status == TurnStatus.FAILED_FINAL
    assert result.assistant_turn_id is None
    assert result.reply_text is None
    assert result.failure_reason == "provider no-output"

    # VAL ②: attempts left a durable trace; action failed terminal.
    assert _count(db, "provider_attempt") == 3
    assert provider.call_count == 3
    action = _unwrap(generation_store.get_action_for_turn(result.turn_id))
    assert action is not None
    assert action.status == GenerationActionStatus.TERMINAL
    assert action.attempt_count == 3
    attempts = _unwrap(generation_store.attempts_for(action.action_id))
    assert [a.attempt_no for a in attempts] == [1, 2, 3]
    assert all(a.status == "FAILED" for a in attempts)
    assert all(a.result_hash is None for a in attempts)

    # Undelivered output never enters the canonical transcript (§3 key
    # rule / VAL ③ negative half).
    assert _count(db, "assistant_turn") == 0
    _no_whole_turn_retry(db)


# ---------------------------------------------------------------------------
# §3 scenario 3 — provider retry
# ---------------------------------------------------------------------------


def test_provider_retry_stays_action_level(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 provider retry / VAL ②⑦: two failed attempts then a good one —
    all under ONE stable action_id; the UserTurn/TurnRecord are never
    rebuilt; the accepted attempt canonicalizes exactly once."""

    provider = ScriptedPersonaProvider(
        script=(no_output(), no_output(), normal_output())
    )
    coordinator = make_coordinator(store, generation_store, lease, provider)

    result = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-retry", "hey"))
    )
    assert result.outcome == "REPLIED_FULL"
    assert result.reply_text

    action = _unwrap(generation_store.get_action_for_turn(result.turn_id))
    assert action is not None
    assert action.status == GenerationActionStatus.TERMINAL
    attempts = _unwrap(generation_store.attempts_for(action.action_id))
    assert [a.attempt_no for a in attempts] == [1, 2, 3]
    assert [a.status for a in attempts] == ["FAILED", "FAILED", "SUCCEEDED"]
    # Many attempts, at most one canonical accepted result (§14/§16): only
    # the succeeded attempt carries a result_hash.
    assert [a.result_hash is not None for a in attempts] == [False, False, True]

    _no_whole_turn_retry(db)
    assert _count(db, "assistant_turn") == 1  # canonicalized exactly once
    assert _count(db, "provider_attempt") == 3


def test_validator_retry_is_bounded_and_action_level(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """VAL ③: validator RETRY (§15 "Retry bounded") drives the same
    action-level loop — an over-length output retries under the same
    action_id, the next output within contract ACCEPTs and buffers."""

    from elc.persona import (
        GenerationContext,
        GenerationContract,
        PersonaRuntime,
        PromptCompiler,
        ResponseValidator,
    )
    from elc.persona.types import PromptCompilationRequest
    from elc.platform.types import InteractionChannel, PersonaId

    cp0 = commit_ok(store, conversation, "cm-vretry", "yo")
    _unwrap(
        store.transition_turn(cp0.turn_id, cp0.state_version, TurnStatus.GENERATING)
    )
    # Migration 0007 lineage: the hand-built action needs its cycle row.
    cycle_id = seed_decision_cycle(db, cp0.turn_id)
    intent = action_intent_for_turn(
        turn_id=cp0.turn_id,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-test",
        decision_cycle_id=cycle_id,
    )
    too_long = ProviderOutput(text="y" * 200, error=None)
    fine = ProviderOutput(text="ok", error=None)
    runtime = PersonaRuntime(
        actions=generation_store,
        provider=ScriptedPersonaProvider(script=(too_long, fine)),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
    )
    contract = GenerationContract(
        generation_contract_id="gc-test",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=PersonaId("persona-default"),
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
        max_length=10,
    )
    request = PromptCompilationRequest(
        conversation_id=conversation,
        persona_id=PersonaId("persona-default"),
        interaction_channel=InteractionChannel.TEXT,
        generation_context=GenerationContext(
            character_package=None,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=None,
            language_policy="default",
            generation_policy="default",
            generation_contract=contract,
        ),
        generation_contract=contract,
    )
    outcome = _unwrap(runtime.run_action(intent, request, contract))
    assert outcome.buffered_reply is not None
    assert outcome.buffered_reply.text == "ok"
    assert outcome.final_status == GenerationActionStatus.READY_TO_DELIVER

    # RETRY consumed one attempt; the loop stayed on the same action.
    attempts = _unwrap(generation_store.attempts_for(intent.action_id))
    assert [a.attempt_no for a in attempts] == [1, 2]
    assert [a.status for a in attempts] == ["SUCCEEDED", "SUCCEEDED"]
    assert [v.decision.value for v in outcome.validator_results] == [
        "RETRY",
        "ACCEPT",
    ]
    _no_whole_turn_retry(db)
    assert _count(db, "assistant_turn") == 0  # buffered, not yet delivered


# ---------------------------------------------------------------------------
# §3 scenario 4 — late callback (supersede / fencing)
# ---------------------------------------------------------------------------


def test_late_callback_on_terminal_action_is_discarded(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 late callback / VAL ④: a result arriving after the action is
    TERMINAL never changes it and never enters the transcript (§14
    late-result rule)."""

    provider = ScriptedPersonaProvider()
    coordinator = make_coordinator(store, generation_store, lease, provider)
    result = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-late", "hi"))
    )

    verdict = _unwrap(
        coordinator.accept_late_result(result.action_id, "late model output")
    )
    assert verdict == "DISCARDED_TERMINAL_ACTION"

    action = _unwrap(generation_store.get_action(result.action_id))
    assert action is not None
    assert action.status == GenerationActionStatus.TERMINAL
    # Transcript untouched: still exactly one assistant turn with the
    # original validated content.
    assert _count(db, "assistant_turn") == 1
    slice_ = _unwrap(store.get_canonical_turn_slice(result.turn_id))
    assert slice_ is not None
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.content == result.reply_text


def test_late_callback_from_fenced_epoch_is_discarded(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 late callback / VAL ④ (supersede/old-epoch half): a callback for
    an old-epoch nonterminal action is fenced out — no state change, no
    transcript entry — and the durable action refuses the old owner's
    writes (§24.1 fencing)."""

    # Old-epoch process: CP0 + action dispatched mid-flight, then "crash".
    cp0 = commit_ok(store, conversation, "cm-fence", "hi")
    _unwrap(
        store.transition_turn(cp0.turn_id, cp0.state_version, TurnStatus.GENERATING)
    )
    # Migration 0007 lineage: the hand-built action needs its cycle row.
    cycle_id = seed_decision_cycle(db, cp0.turn_id)
    intent = action_intent_for_turn(
        turn_id=cp0.turn_id,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-normal-persona-reply",
        decision_cycle_id=cycle_id,
    )
    _unwrap(generation_store.create_action(intent))
    _unwrap(
        generation_store.transition_action(
            intent.action_id,
            GenerationActionStatus.PREPARED,
            GenerationActionStatus.REQUESTED,
        )
    )

    # Restart: a newer epoch exists; the new coordinator is the recovery
    # owner. The old action's late result is fenced out.
    fence2 = epoch.open_runtime_epoch(db)
    store2 = SqliteConversationStore(db, RuntimeEpochFence(current=fence2.current))
    gen2 = AssemblyGenerationStore(db, RuntimeEpochFence(current=fence2.current))
    lease2 = ConversationCoordinatorLease()
    lease2.adopt_epoch(fence2.current)
    coordinator2 = make_coordinator(
        store2, gen2, lease2, ScriptedPersonaProvider()
    )
    verdict = _unwrap(coordinator2.accept_late_result(intent.action_id, "late"))
    assert verdict == "DISCARDED_FENCED_EPOCH"

    # The old owner can no longer advance the action (durable fencing), and
    # nothing entered the transcript.
    from elc.platform.db.generation_store import StaleStoreEpochError

    with pytest.raises(StaleStoreEpochError):
        generation_store.transition_action(
            intent.action_id,
            GenerationActionStatus.REQUESTED,
            GenerationActionStatus.GENERATING,
        )
    action = _unwrap(gen2.get_action(intent.action_id))
    assert action is not None
    assert action.status == GenerationActionStatus.REQUESTED  # unchanged
    assert _count(db, "assistant_turn") == 0
    _no_whole_turn_retry(db)


# ---------------------------------------------------------------------------
# §3 scenario 5 — crash after user commit
# ---------------------------------------------------------------------------


def test_crash_after_user_commit_recovers_via_new_epoch(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 crash after user commit / VAL ⑤: a new runtime_epoch adopts the
    old nonterminal turn, re-dispatches generation under the SAME stable
    action_id with the attempt sequence continuing, and the committed
    UserTurn is never replayed (RUNTIME §22/§23/§24.1)."""

    # -- epoch 1: user committed, generation dispatched, one failed
    # attempt logged, then the process dies.
    command = _command(conversation, "cm-crash", "hello again")
    cp0 = _unwrap(store.commit_user_turn(command))
    _unwrap(
        store.transition_turn(cp0.turn_id, cp0.state_version, TurnStatus.GENERATING)
    )
    # Migration 0007 lineage: the hand-built action needs its cycle row.
    cycle_id = seed_decision_cycle(db, cp0.turn_id)
    intent = action_intent_for_turn(
        turn_id=cp0.turn_id,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-normal-persona-reply",
        decision_cycle_id=cycle_id,
    )
    _unwrap(generation_store.create_action(intent))
    _unwrap(
        generation_store.transition_action(
            intent.action_id,
            GenerationActionStatus.PREPARED,
            GenerationActionStatus.REQUESTED,
        )
    )
    prompt_hash = "h" * 64
    _unwrap(
        generation_store.record_attempt(
            ProviderAttemptRecord(
                provider_attempt_id="pa-crash-1",
                action_id=intent.action_id,
                attempt_no=1,
                request_hash=prompt_hash,
                status="FAILED",
                provider_request_id=None,
                result_hash=None,
                created_at="2026-09-20T00:00:00+00:00",
                terminal_at="2026-09-20T00:00:00+00:00",
            )
        )
    )

    # -- epoch 2: startup scan identifies the old-epoch nonterminal work.
    fence2 = epoch.open_runtime_epoch(db)
    store2 = SqliteConversationStore(db, RuntimeEpochFence(current=fence2.current))
    gen2 = AssemblyGenerationStore(db, RuntimeEpochFence(current=fence2.current))
    lease2 = ConversationCoordinatorLease()
    lease2.adopt_epoch(fence2.current)
    scanner = StartupRecoveryScanner(source=store2, lease=lease2)
    plan = _unwrap(scanner.scan())
    assert [(item.kind, item.id, item.action) for item in plan] == [
        ("TURN", cp0.turn_id, "RESUME_ACTION_BY_STABLE_ACTION_ID")
    ]

    # -- epoch 2: the coordinator recovers by re-dispatching the SAME turn.
    provider = ScriptedPersonaProvider()  # normal deterministic output
    coordinator2 = make_coordinator(store2, gen2, lease2, provider)
    recovered = _unwrap(coordinator2.begin_turn(command))

    assert recovered.turn_id == cp0.turn_id  # same turn, not a new one
    assert recovered.outcome == "REPLIED_FULL"
    assert recovered.reply_text

    # UserTurn not replayed (§22: 只恢复未完成 action，不重跑整个 user turn).
    _no_whole_turn_retry(db)
    assert _count(db, "assistant_turn") == 1

    # Same stable action_id; the attempt sequence continued from the
    # durable attempt_count (§23 "继续同 action_id"; §20 attempt_no).
    action = _unwrap(gen2.get_action_for_turn(cp0.turn_id))
    assert action is not None
    assert action.action_id == intent.action_id
    assert action.status == GenerationActionStatus.TERMINAL
    attempts = _unwrap(gen2.attempts_for(action.action_id))
    assert [a.attempt_no for a in attempts] == [1, 2]
    assert [a.status for a in attempts] == ["FAILED", "SUCCEEDED"]

    slice_ = _unwrap(store2.get_canonical_turn_slice(cp0.turn_id))
    assert slice_ is not None
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.delivery_state.value == "SENT_COMPLETE"
    assert slice_.outcome is not None
    assert slice_.outcome.value == "REPLIED_FULL"


# ---------------------------------------------------------------------------
# §3 scenario 6 — assistant partial / failure terminalization
# ---------------------------------------------------------------------------


def test_partial_delivery_terminalizes_as_replied_partial(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 assistant partial terminalization / VAL ⑥: a buffered reply of
    which only a prefix was actually sent canonicalizes as SENT_PARTIAL,
    terminalizes REPLIED_PARTIAL, and enters the transcript marked partial."""

    from elc.conversation.types import DeliveryState, TurnOutcome
    from elc.persona import (
        PersonaRuntime,
        PromptCompiler,
        ResponseValidator,
    )
    from elc.runtime import AssistantDelivery

    cp0 = commit_ok(store, conversation, "cm-partial", "tell me more")
    _unwrap(
        store.transition_turn(cp0.turn_id, cp0.state_version, TurnStatus.GENERATING)
    )
    # Migration 0007 lineage: the hand-built action needs its cycle row.
    cycle_id = seed_decision_cycle(db, cp0.turn_id)
    intent = action_intent_for_turn(
        turn_id=cp0.turn_id,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-normal-persona-reply",
        decision_cycle_id=cycle_id,
    )
    runtime = PersonaRuntime(
        actions=generation_store,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
    )
    from elc.persona.types import GenerationContext, PromptCompilationRequest
    from elc.platform.types import InteractionChannel, PersonaId

    request = PromptCompilationRequest(
        conversation_id=conversation,
        persona_id=PersonaId("persona-default"),
        interaction_channel=InteractionChannel.TEXT,
        generation_context=GenerationContext(
            character_package=None,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=None,
            language_policy="default",
            generation_policy="default",
        ),
    )
    outcome = _unwrap(runtime.run_action(intent, request, None))
    assert outcome.buffered_reply is not None

    # VAL ③ positive half: at READY_TO_DELIVER the validated output is
    # buffered (queued) but NOT yet in the transcript (BUFFERED_VALIDATED:
    # provider complete → full validation → delivery).
    assert outcome.final_status == GenerationActionStatus.READY_TO_DELIVER
    assert _count(db, "assistant_turn") == 0

    # Only a prefix reached the client: canonicalize the sent boundary.
    coordinator = make_coordinator(
        store, generation_store, lease, ScriptedPersonaProvider()
    )
    full_text = outcome.buffered_reply.text
    prefix = full_text[: max(1, len(full_text) // 2)]
    completion = _unwrap(
        coordinator.finalize_delivery(
            AssistantDelivery(
                conversation_id=conversation,
                turn_id=cp0.turn_id,
                action_id=intent.action_id,
                assistant_turn_id=intent.assistant_turn_id,
                text=prefix,
                turn_sequence=cp0.turn_sequence,
                message_sequence=cp0.message_sequence,
                delivery_state=DeliveryState.SENT_PARTIAL,
                outcome=TurnOutcome.REPLIED_PARTIAL,
            ),
            turn_state_version=2,
        )
    )
    assert completion.outcome == "REPLIED_PARTIAL"
    assert completion.turn_status == TurnStatus.COMPLETED

    slice_ = _unwrap(store.get_canonical_turn_slice(cp0.turn_id))
    assert slice_ is not None
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.content == prefix
    assert slice_.assistant_turn.delivery_state == DeliveryState.SENT_PARTIAL
    assert slice_.outcome is not None
    assert slice_.outcome == TurnOutcome.REPLIED_PARTIAL

    action = _unwrap(generation_store.get_action(intent.action_id))
    assert action is not None
    assert action.status == GenerationActionStatus.TERMINAL
    _no_whole_turn_retry(db)


def test_failure_terminalization_keeps_undelivered_out_of_transcript(
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    lease: ConversationCoordinatorLease,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """§3 assistant failure terminalization / VAL ⑥: when generation fails,
    the action ends TERMINAL, the turn ends FAILED_FINAL, and no content
    enters the transcript (DOMAIN_MODEL §3 key rule)."""

    provider = ScriptedPersonaProvider(script=(no_output(),))
    coordinator = make_coordinator(
        store, generation_store, lease, provider, max_provider_attempts=1
    )
    result = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-fail", "hi"))
    )
    assert result.outcome == "FAILED_USER_VISIBLE"
    assert result.turn_status == TurnStatus.FAILED_FINAL
    assert _count(db, "assistant_turn") == 0
    action = _unwrap(generation_store.get_action_for_turn(result.turn_id))
    assert action is not None
    assert action.status == GenerationActionStatus.TERMINAL

    # A terminal FAILED turn is immutable: a replayed duplicate input gets
    # the durable failure back, never a retry of the whole turn.
    replay = _unwrap(
        coordinator.begin_turn(_command(conversation, "cm-fail", "hi"))
    )
    assert replay.turn_status == TurnStatus.FAILED_FINAL
    assert replay.reply_text is None
    assert provider.call_count == 1
    _no_whole_turn_retry(db)
