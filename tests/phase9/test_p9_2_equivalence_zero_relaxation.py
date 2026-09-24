"""P9-2 ③ — the equivalence, and the lines this cut did not cross.

Three claims, each checkable in the shipped tree:

- **the default stream is the buffered delivery**: the same world, two
  conversations, and the ordinary turn's streamed reply (V1's single-chunk
  placeholder) is compared **field by field** with the same reply finalized
  through ``finalize_delivery`` — content, delivery state, certainty, outcome,
  turn and action statuses. The two arms are not the same code path (that is
  the point: the shipped ordinary path *is* the stream now), so the comparison
  is driven through each face's own entry: ``begin_turn`` for the stream,
  ``run_action`` + ``finalize_delivery`` for the buffered one (the Phase 1
  manual-delivery precedent, ``tests/phase1/test_generation_scenarios.py``).
  The one difference the cut registers rather than removes is stated in the
  test: the buffered request declares its word, so ``TurnCompletion``'s two new
  fields stay ``None`` there.
- **the teaching legs never take the stream**: §13's default table sends every
  teaching action type through ``BUFFERED_VALIDATED``, and the wired §22 record
  face stays empty on an automatic teaching open — the teaching delivery is
  ``finalize_delivery``'s, unchanged (the assertion is on the real ALLOW chain
  of the P8-4 world, with the record port wired).
- **no word, no rule set and no canonical boundary moved**: §13's six states
  and its two canonical ones, the validator's version string, the buffered
  face's two literals (``SENT_COMPLETE`` / ``SERVER_SENT_UNCONFIRMED``) and the
  absence of any ``finalize_delivery`` call inside the new face are pinned
  against the source, so "zero relaxation" is a fact about this tree rather
  than a promise in a report;
- **the contract's own delivery word is read on both arms**: the ordinary
  reply's ``GenerationContract`` declares ``GUARDED_STREAM`` and the teaching
  leg's declares ``BUFFERED_VALIDATED`` — both taken from the provider prompt
  the run was actually handed (the field is rendered and persisted nowhere
  else), so the single carrier the table feeds and the one the teaching site
  still builds are pinned against drifting apart one-sidedly.
"""

from __future__ import annotations

import ast
import dataclasses
import sqlite3
from pathlib import Path

import pytest

from elc.conversation.types import (
    CANONICAL_DELIVERY_STATES,
    CommitUserTurn,
    DeliveryState,
    TurnOutcome,
)
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.persona.runtime import action_intent_for_turn
from elc.persona.types import (
    CompiledPrompt,
    GenerationContext,
    PromptCompilationRequest,
    ProviderOutput,
)
from elc.persona.validator import VALIDATOR_VERSION
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    DecisionCycleId,
    InputId,
    InteractionChannel,
    Ok,
    PersonaId,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.controller import AssistantDelivery
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.guarded_stream import (
    DELIVERY_MODE_BY_ACTION,
    DeliveryMode,
    delivery_mode_of,
)
from elc.runtime.types import (
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    TurnStatus,
)
from tests.conftest import SRC_ROOT
from tests.phase7.conftest import USER
from tests.phase8 import p8_4_world
from tests.phase8.conftest import RECEIVED_AT
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    StreamWorld,
    begin_turn_ok,
    count,
    stream_world,
)

CONTROLLER = SRC_ROOT / "runtime" / "controller.py"
DRIVER = SRC_ROOT / "runtime" / "guarded_stream.py"

BUFFERED_CONV = ConversationId("conv-p9-2-buffered")

#: The shapes the mode lookup must refuse politely: a plain string spelling of
#: a real action type (a caller that lost the enum), ``None``, and an object.
FOREIGN_MODES: tuple[object, ...] = ("NORMAL_PERSONA_REPLY", None, object())


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    """The same world the streamed suite drives, built by the same function."""

    return stream_world(tmp_path)


# -- ① §13's default table ------------------------------------------------------


@pytest.mark.parametrize(
    "action_type",
    [
        GenerationActionType.NORMAL_PERSONA_REPLY,
        GenerationActionType.TEACHING_OPEN,
        GenerationActionType.TEACHING_HINT,
        GenerationActionType.TEACHING_REVEAL,
        GenerationActionType.TEACHING_EXPLANATION,
        GenerationActionType.PERSONA_RESUME,
    ],
)
def test_the_mode_table_answers_every_action_type(
    action_type: GenerationActionType,
) -> None:
    """§13's default column, one row at a time: ordinary persona chat streams,
    everything else is buffered-validated."""

    expected = (
        DeliveryMode.GUARDED_STREAM
        if action_type is GenerationActionType.NORMAL_PERSONA_REPLY
        else DeliveryMode.BUFFERED_VALIDATED
    )
    assert delivery_mode_of(action_type) is expected
    assert DELIVERY_MODE_BY_ACTION[action_type] is expected


def test_the_mode_table_is_total_and_fails_closed() -> None:
    """Every member of the §20 vocabulary has a row (no default-by-accident),
    and the two words are the only two modes."""

    assert set(DELIVERY_MODE_BY_ACTION) == set(GenerationActionType)
    assert {mode.value for mode in DeliveryMode} == {
        "BUFFERED_VALIDATED",
        "GUARDED_STREAM",
    }


@pytest.mark.parametrize("foreign", FOREIGN_MODES)
def test_the_mode_lookup_refuses_a_foreign_shape_politely(
    foreign: object,
) -> None:
    """A value outside the table takes the stricter mode — including a plain
    string spelling of a real action type, which is the shape a caller that
    lost the enum would hand over: the streaming mode is opt-in by *type*, not
    by text."""

    assert delivery_mode_of(foreign) is DeliveryMode.BUFFERED_VALIDATED


# -- ② the buffered arm, driven by hand (the Phase 1 precedent) ----------------


def _buffered_reply_turn(world_: StreamWorld) -> tuple[object, object]:
    """One reply finalized through ``finalize_delivery`` in the same world.

    The plumbing is the Phase 1 manual-delivery recipe
    (``tests/phase1/test_generation_scenarios.py``): a second conversation, the
    real CP0 commit, a real DecisionCycle row for the action's foreign key, a
    real ``run_action`` over the *same* scripted provider text, and then the
    buffered finalization. Nothing here is the streaming face.
    """

    opened = world_.store.open_conversation(
        BUFFERED_CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    committed = world_.store.commit_user_turn(
        CommitUserTurn(
            conversation_id=BUFFERED_CONV,
            envelope=InputEnvelope(
                input_id=InputId("in-p9-2-buffered"),
                client_message_id=ClientMessageId("cmid-p9-2-buffered"),
                conversation_id=str(BUFFERED_CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-p9-2-buffered",
                received_at=RECEIVED_AT,
            ),
            raw_content="One more time, please.",
            runtime_version="runtime-p9-2",
        )
    )
    assert isinstance(committed, Ok), committed
    cp0 = committed.value
    transitioned = world_.store.transition_turn(
        cp0.turn_id, cp0.state_version, TurnStatus.GENERATING
    )
    assert isinstance(transitioned, Ok), transitioned

    cycle_id = DecisionCycleId("dc-p9-2-buffered")
    cycle = world_.generation.decision_cycles.record_decision_cycle(
        decision_cycle_id=cycle_id,
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(
            learning_snapshot_id=None,
            evidence_watermark=None,
            curriculum_version=None,
            goal_version=None,
            schedule_version=None,
            policy_version=None,
            context_view_version=None,
            relationship_view_version=None,
        ),
        expected_turn_state_version=transitioned.value.state_version,
    )
    assert isinstance(cycle, Ok), cycle

    intent = action_intent_for_turn(
        turn_id=cp0.turn_id,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-normal-persona-reply",
        decision_cycle_id=str(cycle_id),
    )
    runtime = PersonaRuntime(
        actions=world_.generation,
        provider=ScriptedPersonaProvider(
            script=(ProviderOutput(text=REPLY),)
        ),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    run = runtime.run_action(
        intent,
        PromptCompilationRequest(
            conversation_id=BUFFERED_CONV,
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
        ),
        None,
    )
    assert isinstance(run, Ok), run
    assert run.value.buffered_reply is not None, run

    coordinator = ConversationCoordinator(
        lease=_lease_of(world_),
        conversation_commands=world_.store,
        conversation_queries=world_.store,
        persona=runtime,
        generation_actions=world_.generation,
        decision_cycles=world_.generation.decision_cycles,
    )
    completion = coordinator.finalize_delivery(
        AssistantDelivery(
            conversation_id=BUFFERED_CONV,
            turn_id=cp0.turn_id,
            action_id=intent.action_id,
            assistant_turn_id=intent.assistant_turn_id,
            text=run.value.buffered_reply.text,
            turn_sequence=cp0.turn_sequence,
            message_sequence=cp0.message_sequence,
            delivery_state=DeliveryState.SENT_COMPLETE,
            outcome=TurnOutcome.REPLIED_FULL,
        ),
        turn_state_version=0,
    )
    assert isinstance(completion, Ok), completion
    return completion.value, cp0


def _lease_of(world_: StreamWorld):
    from elc.runtime.lease import ConversationCoordinatorLease

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world_.fence.current)
    return lease


def test_a_single_chunk_stream_matches_the_buffered_face_field_for_field(
    world: StreamWorld,
) -> None:
    """The equivalence the whole cut rests on. Both arms deliver the same
    scripted text over the same world; the compared fields are read from each
    arm's own durable rows (the assistant_turn slice and the turn/action
    records), never from the objects that produced them."""

    streamed = _streamed_completion(world, "cmid-p9-2-equivalence")
    buffered, _ = _buffered_reply_turn(world)

    streamed_slice = _slice(world, str(streamed.turn_id))
    buffered_slice = _slice(world, str(buffered.turn_id))
    assert streamed_slice.assistant_turn is not None
    assert buffered_slice.assistant_turn is not None

    compared = (
        "turn_sequence",
        "message_sequence",
        "content",
        "delivery_state",
        "delivery_certainty",
    )
    assert [
        getattr(streamed_slice.assistant_turn, field) for field in compared
    ] == [
        getattr(buffered_slice.assistant_turn, field) for field in compared
    ]
    assert streamed_slice.assistant_turn.content == REPLY
    assert streamed_slice.outcome is buffered_slice.outcome
    assert streamed_slice.outcome is TurnOutcome.REPLIED_FULL
    assert streamed_slice.assistant_turn.delivery_state is DeliveryState.SENT_COMPLETE
    assert (
        streamed_slice.assistant_turn.delivery_certainty
        == buffered_slice.assistant_turn.delivery_certainty
        == "SERVER_SENT_UNCONFIRMED"
    )

    for completion in (streamed, buffered):
        assert completion.turn_status is TurnStatus.COMPLETED
        assert completion.action_status is GenerationActionStatus.TERMINAL
        assert completion.outcome == "REPLIED_FULL"
        assert completion.reply_text == REPLY
        assert completion.failure_reason is None
        action = world.generation.get_action(completion.action_id)
        assert action.value is not None
        assert action.value.status is GenerationActionStatus.TERMINAL

    # the registered difference: the streamed face names its own word, the
    # buffered request declares one and its completion carries no copy of it
    assert streamed.delivery_state == "SENT_COMPLETE"
    assert streamed.delivery_failure_reason is None
    assert buffered.delivery_state is None
    assert buffered.delivery_failure_reason is None

    # and the buffered arm wrote no §22 row: only the streamed turn has one
    assert count(world.db, "server_delivery_record") == 1


def _streamed_completion(world_: StreamWorld, client_message_id: str):
    from tests.phase9.test_p9_2_stream_turn import (
        begin_turn_ok,
        coordinator_,
    )

    return begin_turn_ok(coordinator_(world_), client_message_id)


def _slice(world_: StreamWorld, turn_id: str):
    from tests.phase9.test_p9_2_stream_turn import slice_of

    return slice_of(world_, turn_id)


# -- ③ the teaching legs are untouched ----------------------------------------


def test_the_teaching_leg_delivers_through_the_buffered_face_with_the_port_wired(
    db: sqlite3.Connection, p8world
) -> None:
    """The P8-4 world's real ALLOW chain, with this cut's §22 record face wired
    into the same coordinator: the automatic teaching open is delivered (one
    assistant turn), and **no** ``server_delivery_record`` row exists — the
    teaching delivery is still ``finalize_delivery``'s, and its completion
    carries neither of the stream's two fields."""

    coordinator = ConversationCoordinator(
        lease=p8world.lease,
        conversation_commands=p8world.store,
        conversation_queries=p8world.store,
        persona=PersonaRuntime(
            actions=p8world.generation,
            provider=ScriptedPersonaProvider(),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=p8world.generation,
        decision_cycles=p8world.generation.decision_cycles,
        learning_controller=p8world.learning,
        teaching=p8world.teaching,
        targets=p8world.targets,
        automatic_teaching=p8_4_world.wiring(
            p8world, supply=p8_4_world.acceptance_supply()
        ),
        delivery_records=SqliteDeliveryRecordStore(db, p8world.fence),
    )
    result = coordinator.begin_turn(p8_4_world.command("cmid-p9-2-teaching"))
    assert isinstance(result, Ok), result
    completion = result.value

    assert completion.action_id is not None
    assert str(completion.action_id).endswith("automatic-open")
    assert count(db, "assistant_turn") == 1
    assert count(db, "teaching_moment") == 1
    assert count(db, "server_delivery_record") == 0

    row = db.execute(
        "SELECT delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone()
    assert row == ("SENT_COMPLETE", "SERVER_SENT_UNCONFIRMED")
    # the buffered face leaves the stream's two honesty fields alone
    assert completion.delivery_state is None
    assert completion.delivery_failure_reason is None
    assert completion.ledger_event == "teaching_presented"


def test_the_default_coordinator_of_the_p8_world_writes_no_delivery_row(
    db: sqlite3.Connection, p8world
) -> None:
    """The P8-4 builder's own assembly (no ``delivery_records``) is what the
    shipped default path is — and an ordinary turn through it streams without a
    §22 row: the port's absence, in a world built before this cut existed."""

    coordinator = p8_4_world.coordinator(p8world)
    result = coordinator.begin_turn(
        p8_4_world.command("cmid-p9-2-p8-default")
    )
    assert isinstance(result, Ok), result
    assert result.value.outcome == "REPLIED_FULL"
    assert result.value.delivery_state == "SENT_COMPLETE"
    assert count(db, "server_delivery_record") == 0
    assert count(db, "assistant_turn") == 1


# -- ④ the words, the version and the two faces -------------------------------


def test_the_delivery_words_and_the_validator_version_did_not_move() -> None:
    assert {state.value for state in DeliveryState} == {
        "NOT_SENT",
        "SENDING",
        "SENT_PARTIAL",
        "SENT_COMPLETE",
        "FAILED",
        "CANCELLED",
    }
    # only the SENT_* pair may enter the transcript (§3 key rule)
    assert CANONICAL_DELIVERY_STATES == {
        DeliveryState.SENT_PARTIAL,
        DeliveryState.SENT_COMPLETE,
    }
    assert VALIDATOR_VERSION == "response-validator-v1-p1b"
    # the guard is the shipped class, not a copy of its rules
    import elc.persona.validator as persona_validator
    import elc.runtime.guarded_stream as driver

    assert driver.ResponseValidator is persona_validator.ResponseValidator


def test_the_buffered_face_still_declares_its_word_and_certainty() -> None:
    """``finalize_delivery`` is the teaching legs' face and this cut left it
    alone: its canonicalization still takes the request's delivery state and
    stamps the unconfirmed certainty, byte for byte."""

    source = CONTROLLER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = _method(tree, "finalize_delivery")
    body = ast.unparse(method)
    assert "delivery_state=delivery.delivery_state" in body
    assert "delivery_certainty=SERVER_SENT_UNCONFIRMED" in body
    assert "self._persona.complete_delivery(delivery.action_id)" in body


def test_the_streamed_face_does_not_fall_back_to_the_buffered_face() -> None:
    """A streamed delivery may not "become" a buffered one: the new face builds
    its own record and calls the canonicalization itself, and it never calls
    ``finalize_delivery``."""

    tree = ast.parse(CONTROLLER.read_text(encoding="utf-8"))
    streamed = _method(tree, "finalize_streamed_delivery")
    called = {
        node.func.attr
        for node in ast.walk(streamed)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "finalize_delivery" not in called
    assert "canonicalize_assistant_turn" in called
    assert "complete_delivery" in called
    # the no-content exit is its own method, and that one terminalizes the
    # action undelivered rather than delivering anything
    assert "_stream_without_content" in called
    without_content = ast.unparse(_method(tree, "_stream_without_content"))
    assert "terminalize_failure" in without_content
    assert "FAILED_USER_VISIBLE" in without_content


def test_the_driver_module_is_the_one_this_cut_added_and_nothing_else() -> None:
    """The new module's faces exist, and the ordinary path's mode question is
    answered by the table rather than by the caller's wiring."""

    import elc.runtime.guarded_stream as driver

    for name in (
        "DeliveryMode",
        "StreamStep",
        "StreamStepKind",
        "StreamRun",
        "StreamTransport",
        "StreamTransportFactory",
        "LocalSingleChunkTransport",
        "run_guarded_stream",
        "delivery_mode_of",
    ):
        assert hasattr(driver, name), name

    # the entry point's fields are the ones the controller reads
    fields = {field.name for field in dataclasses.fields(driver.StreamRun)}
    assert {
        "state",
        "sent_prefix",
        "durable_prefix",
        "chunks",
        "last_chunk_seq",
        "stop_reason",
        "failure_reason",
        "guard_decision",
        "guard_reason_codes",
    } <= fields


def test_the_new_module_import_set_is_the_declared_one() -> None:
    """Declared and asserted by equality (the P8-4 discipline): the driver
    reads the persona's validator, the platform's types, the conversation's
    words and the runtime's action vocabulary — no store, no controller and no
    database module, which is what "SQL-free" means for this package."""

    tree = ast.parse(DRIVER.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported == {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "elc.conversation.types",
        "elc.persona.types",
        "elc.persona.validator",
        "elc.platform.types",
        "elc.runtime.types",
    }
    assert not [name for name in imported if name.startswith("elc.platform.db")]
    assert "sqlite3" not in imported


def test_the_streamed_completions_two_fields_are_the_declared_ones() -> None:
    """The honest face (R9) is two defaulted fields on ``TurnCompletion``: a
    completion built the pre-cut way carries neither, so every existing
    construction and comparison stays true."""

    from elc.runtime.types import TurnCompletion

    fields = {field.name: field for field in dataclasses.fields(TurnCompletion)}
    assert "delivery_state" in fields
    assert "delivery_failure_reason" in fields
    assert fields["delivery_state"].default is None
    assert fields["delivery_failure_reason"].default is None


# -- ⑤ the contract's delivery word, on both arms -------------------------------


class PromptRecordingProvider:
    """The scripted provider with a log of the prompts it was handed.

    ``response_mode`` is rendered into the prompt's ``[contract]`` block and
    stored nowhere else, so the provider call is the one place the value the
    run actually declared can be read — and reading it there is what makes
    this a pin on behaviour rather than on the source text.
    """

    def __init__(
        self, script: tuple[ProviderOutput, ...] | None = None
    ) -> None:
        self._inner = ScriptedPersonaProvider(script=script)
        self.prompts: list[str] = []

    @property
    def call_count(self) -> int:
        return self._inner.call_count

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.prompts.append(prompt.prompt_text)
        return self._inner.call(prompt)


def _contract_fields(prompt_text: str) -> dict[str, str]:
    """The ``[contract]`` block's key/value lines, as the provider read them."""

    for block in prompt_text.split("\n\n"):
        if block.startswith("[contract]\n"):
            return dict(line.split(": ", 1) for line in block.splitlines()[1:])
    raise AssertionError(f"no [contract] block in the prompt:\n{prompt_text}")


def test_the_ordinary_contract_declares_the_streaming_mode(
    world: StreamWorld,
) -> None:
    """The ordinary reply's contract must name the delivery its run really
    performs — the provider is told ``GUARDED_STREAM``, and it is the word the
    mode table gives this action type (read off that one lookup, not a second
    copy of it). Before the fix the field kept the dataclass default and every
    ordinary prompt declared ``BUFFERED_VALIDATED``."""

    provider = PromptRecordingProvider(script=(ProviderOutput(text=REPLY),))
    coordinator = ConversationCoordinator(
        lease=_lease_of(world),
        conversation_commands=world.store,
        conversation_queries=world.store,
        persona=PersonaRuntime(
            actions=world.generation,
            provider=provider,
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
    )
    completion = begin_turn_ok(coordinator, "cmid-p9-2-mode-normal")

    assert completion.delivery_state == "SENT_COMPLETE"  # the stream ran
    assert len(provider.prompts) == 1
    fields = _contract_fields(provider.prompts[0])
    assert fields["action_type"] == "NORMAL_PERSONA_REPLY"
    assert fields["response_mode"] == "GUARDED_STREAM"
    assert fields["response_mode"] == (
        delivery_mode_of(GenerationActionType.NORMAL_PERSONA_REPLY).value
    )


def test_the_teaching_contract_keeps_the_buffered_mode(db, p8world) -> None:
    """The other arm, so the two carriers cannot drift apart one-sidedly: the
    teaching leg's contract (built at its own site) still declares
    ``BUFFERED_VALIDATED`` — the mode its delivery really goes through, and
    the word the table gives the action type the automatic open dispatches."""

    provider = PromptRecordingProvider()
    coordinator = ConversationCoordinator(
        lease=p8world.lease,
        conversation_commands=p8world.store,
        conversation_queries=p8world.store,
        persona=PersonaRuntime(
            actions=p8world.generation,
            provider=provider,
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=3,
        ),
        generation_actions=p8world.generation,
        decision_cycles=p8world.generation.decision_cycles,
        learning_controller=p8world.learning,
        teaching=p8world.teaching,
        targets=p8world.targets,
        automatic_teaching=p8_4_world.wiring(
            p8world, supply=p8_4_world.acceptance_supply()
        ),
    )
    result = coordinator.begin_turn(
        p8_4_world.command("cmid-p9-2-mode-teaching")
    )
    assert isinstance(result, Ok), result

    assert len(provider.prompts) == 1
    fields = _contract_fields(provider.prompts[0])
    assert fields["action_type"] == "TEACHING_OPEN"
    assert fields["response_mode"] == "BUFFERED_VALIDATED"
    assert fields["response_mode"] == (
        delivery_mode_of(GenerationActionType.TEACHING_OPEN).value
    )


def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"no method {name!r} in the controller")
