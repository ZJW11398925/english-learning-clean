"""P1B unit checks — deterministic minimum Response Validator (VAL ③),
deterministic PromptCompiler, and the §14 transition table with invalid
transition refusals (STATE_MACHINES §20: no out-of-order overwrite)."""

from __future__ import annotations

import sqlite3

import pytest

from elc.conversation import SqliteConversationStore
from elc.persona import (
    DEFAULT_FORBIDDEN_CLAIMS,
    GenerationContract,
    PromptCompiler,
    ProviderOutput,
    ResponseValidator,
    ValidatorDecision,
    action_intent_for_turn,
    no_output,
)
from elc.persona.provider import request_hash
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import ActionId, ConversationId, Err, PersonaId
from elc.runtime.generation import GENERATION_ACTION_TRANSITIONS
from elc.runtime.types import GenerationActionStatus, GenerationActionType

from .conftest import commit_ok


def _committed_turn(
    store: SqliteConversationStore, conversation: ConversationId, tag: str
) -> str:
    cp0 = commit_ok(store, conversation, f"cmid-unit-{tag}", f"unit-{tag}")
    return cp0.turn_id


def _contract(max_length: int | None = None) -> GenerationContract:
    return GenerationContract(
        generation_contract_id="gc-test",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=PersonaId("persona-test"),
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
        max_length=max_length,
    )


def test_validator_minimum_rules_are_deterministic() -> None:
    """VAL ③: the four-rule minimum set (RUNTIME §12 / SM §15) is a pure
    function of (output, contract)."""

    validator = ResponseValidator()
    ok = ProviderOutput(text="hello there", error=None)

    # Rule 1: no-output → RETRY (§3 provider no-output).
    assert validator.decide(no_output(), _contract()) == (
        ValidatorDecision.RETRY,
        ("PROVIDER_NO_OUTPUT",),
    )
    assert validator.decide(ProviderOutput(text=None, error="boom"), _contract())[
        0
    ] == ValidatorDecision.RETRY

    # Rule 2: max_length exceeded → RETRY (GenerationContract compliance).
    long_output = ProviderOutput(text="x" * 11, error=None)
    assert validator.decide(long_output, _contract(max_length=10)) == (
        ValidatorDecision.RETRY,
        ("MAX_LENGTH_EXCEEDED",),
    )

    # Rule 3: forbidden claim → ABORT_DELIVERY (§21 no false mastery claim).
    for claim in DEFAULT_FORBIDDEN_CLAIMS:
        bad = ProviderOutput(text=f"good news: {claim}!", error=None)
        assert validator.decide(bad, _contract()) == (
            ValidatorDecision.ABORT_DELIVERY,
            ("FORBIDDEN_CLAIM",),
        )

    # Rule 4: otherwise → ACCEPT.
    assert validator.decide(ok, _contract()) == (ValidatorDecision.ACCEPT, ())

    # Determinism: repeated calls agree byte for byte.
    for _ in range(3):
        assert validator.decide(ok, _contract()) == (ValidatorDecision.ACCEPT, ())
        assert validator.decide(long_output, _contract(max_length=10)) == (
            ValidatorDecision.RETRY,
            ("MAX_LENGTH_EXCEEDED",),
        )


def test_validator_result_carries_sm15_vocabulary() -> None:
    validator = ResponseValidator()
    result = validator.validate(
        ActionId("ga-1"),
        2,
        no_output(),
        _contract(),
        created_at="2026-09-20T00:00:00+00:00",
    )
    # DATA_MODEL §21.1 ValidatorResult column set + §15 decision values.
    assert result.action_id == ActionId("ga-1")
    assert result.attempt_no == 2
    assert result.decision == ValidatorDecision.RETRY
    assert result.reason_codes == ("PROVIDER_NO_OUTPUT",)
    assert result.validator_version


def test_prompt_compiler_is_deterministic() -> None:
    """Same request in, byte-identical prompt out (no randomness)."""

    from elc.persona import GenerationContext, PromptCompilationRequest
    from elc.platform.types import ConversationId, InteractionChannel

    def build() -> PromptCompilationRequest:
        context = GenerationContext(
            character_package=None,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=None,
            language_policy="default",
            generation_policy="default",
            generation_contract=_contract(),
            ephemeral_teaching_directive=None,
        )
        return PromptCompilationRequest(
            conversation_id=ConversationId("conv-1"),
            persona_id=PersonaId("persona-test"),
            interaction_channel=InteractionChannel.TEXT,
            generation_context=context,
            generation_contract=_contract(),
        )

    compiler = PromptCompiler()
    first = compiler.compile(build())
    second = compiler.compile(build())
    assert first.value.prompt_text == second.value.prompt_text
    assert request_hash(first.value) == request_hash(second.value)
    assert first.value.generation_contract == "gc-test"


def test_transition_action_table_and_invalid_transitions(
    generation_store: SqliteGenerationStore,
    store: SqliteConversationStore,
    conversation: ConversationId,
    db: sqlite3.Connection,
) -> None:
    """SM §14 forward order + §20 refusals: TERMINAL is immutable, a
    mismatched expected status is a conflict, and a fenced owner_epoch
    cannot advance the action."""

    actions = generation_store
    intent = action_intent_for_turn(
        turn_id=_committed_turn(store, conversation, "chain"),
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc",
    )
    assert isinstance(actions.create_action(intent).value, str)

    def status() -> GenerationActionStatus:
        fetched = actions.get_action(intent.action_id)
        assert fetched.value is not None
        return fetched.value.status

    # §14 forward walk: PREPARED → REQUESTED → GENERATING → VALIDATING →
    # READY_TO_DELIVER → DELIVERING → TERMINAL.
    chain = (
        GenerationActionStatus.PREPARED,
        GenerationActionStatus.REQUESTED,
        GenerationActionStatus.GENERATING,
        GenerationActionStatus.VALIDATING,
        GenerationActionStatus.READY_TO_DELIVER,
        GenerationActionStatus.DELIVERING,
        GenerationActionStatus.TERMINAL,
    )
    for expected, new in zip(chain, chain[1:], strict=False):
        stepped = actions.transition_action(intent.action_id, expected, new)
        assert not isinstance(stepped, Err), stepped
        assert stepped.value.status == new
    assert status() == GenerationActionStatus.TERMINAL

    # TERMINAL is immutable (§14 late-result rule): every transition out of
    # TERMINAL is refused.
    for new in (
        GenerationActionStatus.REQUESTED,
        GenerationActionStatus.GENERATING,
        GenerationActionStatus.TERMINAL,
    ):
        refused = actions.transition_action(
            intent.action_id, GenerationActionStatus.TERMINAL, new
        )
        assert isinstance(refused, Err)

    # Status CAS mismatch is a conflict, never an overwrite (§20).
    other = action_intent_for_turn(
        turn_id=_committed_turn(store, conversation, "mismatch"),
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc",
    )
    assert isinstance(actions.create_action(other).value, str)
    mismatch = actions.transition_action(
        other.action_id,
        GenerationActionStatus.GENERATING,
        GenerationActionStatus.VALIDATING,
    )
    assert isinstance(mismatch, Err)

    # A fenced (old-epoch) owner cannot advance the action (§24 fencing).
    # (Seed first: the conversation store is bound to the current epoch.)
    from elc.platform.db import epoch
    from elc.platform.db.generation_store import StaleStoreEpochError

    fenced_turn = _committed_turn(store, conversation, "fenced")
    old_fence = epoch.open_runtime_epoch(db)
    old_store = SqliteGenerationStore(db, old_fence)
    fenced_intent = action_intent_for_turn(
        turn_id=fenced_turn,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc",
    )
    assert isinstance(old_store.create_action(fenced_intent).value, str)
    epoch.open_runtime_epoch(db)  # a newer epoch now exists
    with pytest.raises(StaleStoreEpochError):
        old_store.transition_action(
            fenced_intent.action_id,
            GenerationActionStatus.PREPARED,
            GenerationActionStatus.REQUESTED,
        )


def test_transition_table_rejects_out_of_table_nonterminal_edges(
    generation_store: SqliteGenerationStore,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """F2 (TASK-OPI-eaaa5a1d.13): an out-of-table nonterminal edge is
    refused by transition_action even when the durable status matches —
    in particular the §24 recovery re-arm edge READY_TO_DELIVER →
    REQUESTED stays out of the edge table (it is held only by the claim
    channel, claim_rearm / RECOVERY_REARM_STATUS), so mis-adding an
    illegal edge to GENERATION_ACTION_TRANSITIONS cannot let a re-arm or
    a pipeline skip sneak past the CAS."""

    actions = generation_store
    intent = action_intent_for_turn(
        turn_id=_committed_turn(store, conversation, "oob"),
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc",
    )
    assert isinstance(actions.create_action(intent).value, str)

    # Drive the durable status to VALIDATING so the refusal below is the
    # edge-table refusal, not a status CAS mismatch or the TERMINAL rule.
    to_validating = (
        GenerationActionStatus.PREPARED,
        GenerationActionStatus.REQUESTED,
        GenerationActionStatus.GENERATING,
        GenerationActionStatus.VALIDATING,
    )
    for expected, new in zip(to_validating, to_validating[1:], strict=False):
        stepped = actions.transition_action(intent.action_id, expected, new)
        assert not isinstance(stepped, Err), stepped

    skipped = actions.transition_action(
        intent.action_id,
        GenerationActionStatus.VALIDATING,
        GenerationActionStatus.GENERATING,
    )
    assert isinstance(skipped, Err)
    assert skipped.error.code.value == "VALIDATION_FAILED"
    assert "is not a STATE_MACHINES §14 transition" in skipped.error.message

    stepped = actions.transition_action(
        intent.action_id,
        GenerationActionStatus.VALIDATING,
        GenerationActionStatus.READY_TO_DELIVER,
    )
    assert not isinstance(stepped, Err), stepped

    rearm = actions.transition_action(
        intent.action_id,
        GenerationActionStatus.READY_TO_DELIVER,
        GenerationActionStatus.REQUESTED,
    )
    assert isinstance(rearm, Err)
    assert rearm.error.code.value == "VALIDATION_FAILED"
    assert "is not a STATE_MACHINES §14 transition" in rearm.error.message

    # And the table content itself: neither re-arm edge is a table key —
    # a hand-added DELIVERING → REQUESTED would fail this guard too.
    assert (
        GenerationActionStatus.READY_TO_DELIVER,
        GenerationActionStatus.REQUESTED,
    ) not in GENERATION_ACTION_TRANSITIONS
    assert (
        GenerationActionStatus.DELIVERING,
        GenerationActionStatus.REQUESTED,
    ) not in GENERATION_ACTION_TRANSITIONS


def test_claim_action_for_recovery_is_idempotent_for_own_epoch(
    generation_store: SqliteGenerationStore,
    store: SqliteConversationStore,
    conversation: ConversationId,
) -> None:
    """F5 (DEC-OPI-d7937fd7.19): claiming an action the current epoch
    already owns returns it unchanged — a validated READY_TO_DELIVER buffer
    survives the recovery call (status stays READY_TO_DELIVER,
    attempt_count untouched), mirroring claim_turn_for_recovery's
    already-ours early return."""

    intent = action_intent_for_turn(
        turn_id=_committed_turn(store, conversation, "idem"),
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc",
    )
    assert isinstance(generation_store.create_action(intent).value, str)

    chain = (
        GenerationActionStatus.PREPARED,
        GenerationActionStatus.REQUESTED,
        GenerationActionStatus.GENERATING,
        GenerationActionStatus.VALIDATING,
        GenerationActionStatus.READY_TO_DELIVER,
    )
    for expected, new in zip(chain, chain[1:], strict=False):
        stepped = generation_store.transition_action(intent.action_id, expected, new)
        assert not isinstance(stepped, Err), stepped

    before = generation_store.get_action(intent.action_id)
    assert before.value is not None
    assert before.value.status == GenerationActionStatus.READY_TO_DELIVER

    claimed = generation_store.claim_action_for_recovery(intent.action_id)
    assert not isinstance(claimed, Err), claimed
    assert claimed.value.status == GenerationActionStatus.READY_TO_DELIVER
    assert claimed.value.attempt_count == before.value.attempt_count
    assert claimed.value.owner_epoch == before.value.owner_epoch
