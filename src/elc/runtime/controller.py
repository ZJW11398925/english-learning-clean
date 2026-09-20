"""Conversation Orchestrator — Phase 1 P1B minimum closed loop.

The orchestrator coordinates through domain command/query interfaces only:
its DB posture is "none" — no sqlite3 import, no SQL execution, no direct
table mutation (Gate item 2; enforced by tests/architecture). Persistence
lives in the conversation domain store and elc.platform.db (including the
generation action / provider attempt store, whose §14 state-machine
authority this package owns in elc.runtime.generation).

ConversationCoordinator (TASK-OPI-d7937fd7.9 deliverable ⑥) assembles the
P1A pieces with the P1B persona pipeline into the minimum turn loop of
docs/IMPLEMENTATION_PLAN.md §3:

    coordinator guard (ConversationCoordinatorLease)
    → CP0 commit (idempotent InputEnvelope dedupe + UserTurn + TurnRecord)
    → TurnRecord USER_COMMITTED → GENERATING (state_version CAS)
    → generation pipeline on the §14 action machine via the runtime-owned
      GenerationActionStore port (action-level retry, R-INV-007)
    → BUFFERED_VALIDATED delivery: validated output buffered at
      READY_TO_DELIVER, then canonicalized exactly once via the
      conversation store (SENT_COMPLETE / SENT_PARTIAL)
    → action TERMINAL + turn terminalization (REPLIED_* / FAILED_*).

Duplicate input replays the original CP0 commit and short-circuits on the
terminal TurnRecord; a crash after user commit is re-dispatched under a new
runtime_epoch with the same stable action_id (RUNTIME §23/§24) — the
UserTurn is never replayed and a whole turn is never retried.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from elc.conversation.commands import CommitUserTurn, ConversationCommands
from elc.conversation.queries import ConversationQueries
from elc.conversation.types import (
    AssistantTurnRecord,
    DeliveryState,
    TurnOutcome,
)
from elc.learning.analysis import LearningTurnAnalysis
from elc.persona.runtime import PersonaRuntime, action_intent_for_turn
from elc.persona.types import (
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
)
from elc.platform.sync import KeyedMutex
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    MessageSequence,
    Ok,
    PersonaId,
    ProjectionJobId,
    ProviderAttemptId,
    Result,
    RuntimeEpoch,
    TurnId,
    TurnSequence,
)
from elc.runtime.generation import GenerationActionStore
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    DecisionCycleRecord,
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    ProjectionJobRecord,
    ProviderAttemptRecord,
    RecoveryAction,
    TurnCompletion,
    TurnRecordData,
    TurnStatus,
)

#: Delivery certainty for a server-side buffered delivery with no
#: ClientRenderAck yet (STATE_MACHINES §13 ExposureEstimate certainty).
SERVER_SENT_UNCONFIRMED = "SERVER_SENT_UNCONFIRMED"

#: Conversation window size handed to Persona Runtime (RUNTIME §11
#: ConversationWindow view).
CONVERSATION_WINDOW_MAX_TURNS = 20


@dataclass(frozen=True)
class AssistantDelivery:
    """One BUFFERED_VALIDATED delivery request (RUNTIME §13): the validated
    text plus the delivery-state/outcome pair the coordinator finalizes
    (SENT_COMPLETE→REPLIED_FULL or SENT_PARTIAL→REPLIED_PARTIAL)."""

    conversation_id: ConversationId
    turn_id: TurnId
    action_id: ActionId
    assistant_turn_id: str
    text: str
    turn_sequence: TurnSequence
    message_sequence: MessageSequence
    delivery_state: DeliveryState
    outcome: TurnOutcome


class RuntimeOrchestrator:
    """Sequencing, retry, recovery — owns no canonical truth.

    Phase 0 twelve-domain skeleton kept for later phases. The single
    working orchestrator facade of Phase 1 is :class:`ConversationCoordinator`
    (below): every method here either points there or names the phase that
    will implement it — there is deliberately no second live entry point.
    tests/architecture Gate 1 (phase1_class_allowlist) pins exactly this
    split: only ConversationCoordinator graduated from the skeleton.
    """

    def __init__(self) -> None:
        # Live per-conversation coordinator (docs/RUNTIME_ARCHITECTURE.md §24).
        # In-process keyed mutex + runtime_epoch + durable turn/action state;
        # deliberately NOT a distributed lock service.
        self._mutex = KeyedMutex()
        self._epoch: RuntimeEpoch | None = None

    @property
    def runtime_epoch(self) -> RuntimeEpoch | None:
        """Epoch opened at startup; None until the startup fence runs."""
        return self._epoch

    def open_startup_fence(self, current_epoch: RuntimeEpoch) -> None:
        """Adopt the current epoch (opened via platform.db.epoch at startup)."""
        self._epoch = current_epoch

    def ingest_input(self, envelope: InputEnvelope) -> Result[InputId]:
        raise NotImplementedError("use ConversationCoordinator.begin_turn")

    def request_interrupt(self, interrupt: InterruptRequest) -> Result[InputId]:
        raise NotImplementedError("Phase 9: guarded barge-in handoff")

    def begin_turn(self, command: CommitUserTurn) -> Result[TurnCompletion]:
        raise NotImplementedError("use ConversationCoordinator.begin_turn")

    def open_decision_cycle(
        self, cycle: DecisionCycleRecord
    ) -> Result[DecisionCycleId]:
        raise NotImplementedError("Phase 2: decision cycle")

    def create_generation_action(
        self,
        turn_id: TurnId,
        action_type: GenerationActionType,
        action_id: ActionId,
    ) -> Result[ActionId]:
        raise NotImplementedError(
            "generation actions are created through the runtime-owned"
            " GenerationActionStore port (elc.runtime.generation) — the"
            " Phase 1 loop lives on ConversationCoordinator.begin_turn"
        )

    def create_provider_attempt(
        self, action_id: ActionId, attempt: ProviderAttemptRecord
    ) -> Result[ProviderAttemptId]:
        raise NotImplementedError(
            "provider attempts are appended through the runtime-owned"
            " GenerationActionStore port — action-level retry runs in the"
            " Phase 1 loop (ConversationCoordinator.begin_turn via"
            " PersonaRuntime.run_action)"
        )

    def enqueue_projection(
        self, job: ProjectionJobRecord
    ) -> Result[ProjectionJobId]:
        raise NotImplementedError("Phase 4: CP4 projection job")

    def startup_recovery(self) -> Result[tuple[RecoveryAction, ...]]:
        raise NotImplementedError("use StartupRecoveryScanner")

    def get_turn_record(self, turn_id: TurnId) -> Result[TurnRecordData | None]:
        raise NotImplementedError("use the conversation query face")

    def get_decision_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[DecisionCycleRecord | None]:
        raise NotImplementedError("Phase 2: decision cycle read")


class ConversationCoordinator:
    """The single working orchestrator facade of Phase 1: lease +
    conversation store + persona pipeline (IMPLEMENTATION_PLAN §3).
    RuntimeOrchestrator above stays an unimplemented skeleton, so this is
    the only live turn-loop entry point. SQL-free by construction.

    Phase 2 P2A (TASK-…30 ⑥): inject the ``learning`` port
    (LearningTurnAnalysis, implemented by elc.learning.store.
    SqliteLearningStore) to open RA §4 steps 3-4 between CP0 and persona
    generation — durable LEARNING_EVIDENCE AnalysisArtifact → Learning
    validates/commits → CP1 (durable watermark) — under the canonical
    TurnRecord statuses (USER_COMMITTED → ANALYZING → GENERATING,
    STATE_MACHINES §10 order). ``learning=None`` keeps the Phase 1
    assembly (the P1 tests pin that loop); no DecisionCycle is created
    here (Phase 3+, DEC-…eaaa5a1d.26 a)."""

    def __init__(
        self,
        lease: ConversationCoordinatorLease,
        conversation_commands: ConversationCommands,
        conversation_queries: ConversationQueries,
        persona: PersonaRuntime,
        generation_actions: GenerationActionStore,
        learning: LearningTurnAnalysis | None = None,
    ) -> None:
        self._lease = lease
        self._commands = conversation_commands
        self._queries = conversation_queries
        self._persona = persona
        self._generation = generation_actions
        self._learning = learning

    # -- minimum turn loop ---------------------------------------------------

    def begin_turn(self, command: CommitUserTurn) -> Result[TurnCompletion]:
        """One full turn: guard → CP0 → generation → buffered validated
        delivery → terminalization. Idempotent on client_message_id
        (duplicate input replays the original turn's terminal result)."""

        with self._lease.hold(command.conversation_id):
            cp0_result = self._commands.commit_user_turn(command)
            if isinstance(cp0_result, Err):
                return cp0_result
            cp0 = cp0_result.value

            turn_result = self._commands.get_turn_record(cp0.turn_id)
            if isinstance(turn_result, Err):
                return turn_result
            turn = turn_result.value
            if turn is None:
                return _missing(f"turn record not found: {cp0.turn_id}")
            epoch = self._lease.epoch
            if epoch is not None and turn.owner_epoch != epoch:
                # Crash after user commit: the new epoch adopts the old
                # nonterminal turn (RUNTIME §24; UserTurn never replayed).
                claimed = self._commands.claim_turn_for_recovery(cp0.turn_id)
                if isinstance(claimed, Err):
                    return claimed
                turn = claimed.value

            if turn.status in TERMINAL_TURN_STATUSES:
                # Duplicate input whose turn already finalized: replay the
                # durable terminal result; nothing re-runs (§3 duplicate
                # input; never retry whole turn).
                return self._replay_terminal(turn)

            state_version = turn.state_version
            if self._learning is not None:
                # RA §4 steps 2-4 canonical order: CP0 → durable
                # AnalysisArtifacts → Learning validates/commits (CP1)
                # → generation. ANALYZING is the SM §10 coordination
                # slot for steps 3-4; re-entry after a crash replays the
                # analysis and CP1 idempotently (deterministic store
                # keys), and a turn already past ANALYZING never re-runs
                # them ("crash after CP1 不重复 Evidence", RA §22/§23).
                if turn.status == TurnStatus.USER_COMMITTED:
                    advanced = self._commands.transition_turn(
                        cp0.turn_id, state_version, TurnStatus.ANALYZING
                    )
                    if isinstance(advanced, Err):
                        return advanced
                    turn = advanced.value
                    state_version = turn.state_version
                if turn.status == TurnStatus.ANALYZING:
                    learned = self._run_learning_analysis(
                        cp0.turn_id, command.conversation_id
                    )
                    if isinstance(learned, Err):
                        return learned
                    advanced = self._commands.transition_turn(
                        cp0.turn_id, state_version, TurnStatus.GENERATING
                    )
                    if isinstance(advanced, Err):
                        return advanced
                    state_version = advanced.value.state_version
                elif turn.status != TurnStatus.GENERATING:
                    return _conflict(
                        "turn re-entry from status"
                        f" {turn.status.value} is outside the Phase 2 loop"
                    )
            elif turn.status == TurnStatus.USER_COMMITTED:
                advanced = self._commands.transition_turn(
                    cp0.turn_id, state_version, TurnStatus.GENERATING
                )
                if isinstance(advanced, Err):
                    return advanced
                state_version = advanced.value.state_version
            elif turn.status != TurnStatus.GENERATING:
                return _conflict(
                    "turn re-entry from status"
                    f" {turn.status.value} is outside the Phase 1 loop"
                )

            existing_result = self._generation.get_action_for_turn(cp0.turn_id)
            if isinstance(existing_result, Err):
                return existing_result
            existing = existing_result.value
            action_epoch = self._lease.epoch
            if existing is not None and action_epoch is not None:
                if existing.owner_epoch != action_epoch:
                    # Crash recovery: the new epoch adopts the old-epoch
                    # action (same stable action_id; §23/§24) and re-arms
                    # it at REQUESTED for re-dispatch.
                    claimed_action = self._generation.claim_action_for_recovery(
                        existing.action_id
                    )
                    if isinstance(claimed_action, Err):
                        return claimed_action
                    existing = claimed_action.value
            intent = (
                existing
                if existing is not None
                else action_intent_for_turn(
                    turn_id=cp0.turn_id,
                    action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
                    generation_contract_id="gc-normal-persona-reply",
                )
            )

            context_result = self._queries.get_conversation_window(
                command.conversation_id, CONVERSATION_WINDOW_MAX_TURNS
            )
            window = (
                context_result.value
                if isinstance(context_result, Ok)
                else None
            )
            persona_id = self._persona_id(command.conversation_id)
            contract = self._contract(persona_id)
            context = GenerationContext(
                character_package=None,
                relationship_view=None,
                episode_view=None,
                world_lore_view=None,
                disclosed_user_profile=None,
                conversation_window=window,
                language_policy="default",
                generation_policy="default",
                generation_contract=contract,
                ephemeral_teaching_directive=None,
            )
            request = PromptCompilationRequest(
                conversation_id=command.conversation_id,
                persona_id=persona_id,
                interaction_channel=command.envelope.interaction_channel,
                generation_context=context,
                generation_contract=contract,
            )

            run_result = self._persona.run_action(intent, request, contract)
            if isinstance(run_result, Err):
                return run_result
            generation = run_result.value

            if generation.buffered_reply is None:
                # Provider/validator failure exhausted the action budget:
                # action already TERMINAL undelivered; terminalize the turn
                # FAILED_* without any assistant content in the transcript.
                terminal = self._commands.terminalize_turn(
                    cp0.turn_id, TurnOutcome.FAILED_USER_VISIBLE
                )
                if isinstance(terminal, Err):
                    return terminal
                return Ok(
                    TurnCompletion(
                        turn_id=cp0.turn_id,
                        action_id=intent.action_id,
                        assistant_turn_id=None,
                        turn_status=terminal.value.status,
                        action_status=generation.final_status,
                        outcome=TurnOutcome.FAILED_USER_VISIBLE.value,
                        reply_text=None,
                        failure_reason=generation.failure_reason,
                        state_version=terminal.value.state_version,
                    )
                )

            reply = generation.buffered_reply
            delivery = AssistantDelivery(
                conversation_id=command.conversation_id,
                turn_id=cp0.turn_id,
                action_id=reply.action_id,
                assistant_turn_id=reply.assistant_turn_id,
                text=reply.text,
                turn_sequence=cp0.turn_sequence,
                message_sequence=cp0.message_sequence,
                delivery_state=DeliveryState.SENT_COMPLETE,
                outcome=TurnOutcome.REPLIED_FULL,
            )
            return self.finalize_delivery(delivery, state_version)

    # -- buffered validated delivery (RUNTIME §13) ---------------------------

    def finalize_delivery(
        self, delivery: AssistantDelivery, turn_state_version: int
    ) -> Result[TurnCompletion]:
        """BUFFERED_VALIDATED finalization: action READY_TO_DELIVER →
        DELIVERING → canonical AssistantTurn (exactly once, gated on the
        SENT_* delivery state) → action TERMINAL → turn terminalization.

        Works under the coordinator guard; the caller holds it (begin_turn
        does; tests may hold it explicitly for partial deliveries)."""

        action_result = self._generation.get_action(delivery.action_id)
        if isinstance(action_result, Err):
            return action_result
        action = action_result.value
        if action is None:
            return _missing("generation action not found for delivery")
        if action.status == GenerationActionStatus.READY_TO_DELIVER:
            begun = self._persona.begin_delivery(delivery.action_id)
            if isinstance(begun, Err):
                return begun
        elif action.status != GenerationActionStatus.DELIVERING:
            return _conflict(
                "delivery from action status"
                f" {action.status.value} is outside the Phase 1 loop"
            )

        turn_result = self._commands.get_turn_record(delivery.turn_id)
        if isinstance(turn_result, Err):
            return turn_result
        turn = turn_result.value
        if turn is None:
            return _missing(f"turn record not found: {delivery.turn_id}")
        if turn.status == TurnStatus.GENERATING:
            advanced = self._commands.transition_turn(
                delivery.turn_id,
                turn.state_version,
                TurnStatus.DELIVERING,
            )
            if isinstance(advanced, Err):
                return advanced
            turn = advanced.value

        record = AssistantTurnRecord(
            assistant_turn_id=AssistantTurnId(delivery.assistant_turn_id),
            turn_id=delivery.turn_id,
            conversation_id=delivery.conversation_id,
            turn_sequence=delivery.turn_sequence,
            message_sequence=delivery.message_sequence,
            action_id=delivery.action_id,
            content=delivery.text,
            delivery_state=delivery.delivery_state,
            delivery_certainty=SERVER_SENT_UNCONFIRMED,
        )
        canonical = self._commands.canonicalize_assistant_turn(record)
        if isinstance(canonical, Err):
            return canonical

        completed = self._persona.complete_delivery(delivery.action_id)
        if isinstance(completed, Err):
            return completed

        terminal = self._commands.terminalize_turn(
            delivery.turn_id, delivery.outcome
        )
        if isinstance(terminal, Err):
            return terminal
        return Ok(
            TurnCompletion(
                turn_id=delivery.turn_id,
                action_id=delivery.action_id,
                assistant_turn_id=delivery.assistant_turn_id,
                turn_status=terminal.value.status,
                action_status=GenerationActionStatus.TERMINAL,
                outcome=delivery.outcome.value,
                reply_text=delivery.text,
                failure_reason=None,
                state_version=terminal.value.state_version,
            )
        )

    # -- late callback guard (STATE_MACHINES §14) -----------------------------

    def accept_late_result(
        self, action_id: ActionId, text: str
    ) -> Result[str]:
        """A provider result arriving after its moment. Terminal actions
        and fenced (old-epoch) actions only ever yield an audit verdict —
        the result never enters the canonical transcript (§14 late-result
        rule; RUNTIME §24.1). Phase 1 has no async provider, so a live
        nonterminal action receiving an out-of-band result is out of
        pipeline scope."""

        del text  # audited, never canonicalized from here
        fetched = self._generation.get_action(action_id)
        if isinstance(fetched, Err):
            return fetched
        action = fetched.value
        if action is None:
            return _missing(f"generation action not found: {action_id}")
        if action.status == GenerationActionStatus.TERMINAL:
            return Ok("DISCARDED_TERMINAL_ACTION")
        epoch = self._lease.epoch
        if epoch is not None and action.owner_epoch != epoch:
            return Ok("DISCARDED_FENCED_EPOCH")
        return _conflict(
            "late result on a live nonterminal action is outside the"
            " Phase 1 pipeline"
        )

    # -- internals -----------------------------------------------------------

    def _run_learning_analysis(
        self, turn_id: TurnId, conversation_id: ConversationId
    ) -> Result[None]:
        """RA §4 steps 3-4 through the injected LearningTurnAnalysis
        port: durable LEARNING_EVIDENCE artifact (idempotent re-entry)
        → Learning validates/commits → CP1 with the durable watermark.
        Failure of the learning leg fails the turn (the canonical order
        forbids generating before the current turn's behavior entered
        Learning, RA §8)."""

        slice_result = self._queries.get_canonical_turn_slice(turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        if slice_ is None:
            return _missing(f"canonical turn slice not found: {turn_id}")
        learning = self._learning
        assert learning is not None  # caller holds the Phase 2 assembly
        artifact = learning.record_learning_analysis(slice_)
        if isinstance(artifact, Err):
            return artifact
        persona_id = self._persona_id(conversation_id)
        committed = learning.commit_learning_evidence(
            artifact.value, slice_, str(persona_id)
        )
        if isinstance(committed, Err):
            return committed
        return Ok(None)

    def _replay_terminal(self, turn: TurnRecordData) -> Result[TurnCompletion]:
        slice_result = self._queries.get_canonical_turn_slice(turn.turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        assistant = slice_.assistant_turn if slice_ is not None else None
        action_id = assistant.action_id if assistant is not None else None
        outcome = slice_.outcome if slice_ is not None else None
        return Ok(
            TurnCompletion(
                turn_id=turn.turn_id,
                action_id=action_id if action_id is not None else ActionId(""),
                assistant_turn_id=(
                    assistant.assistant_turn_id if assistant is not None else None
                ),
                turn_status=turn.status,
                action_status=GenerationActionStatus.TERMINAL,
                outcome=outcome.value if outcome is not None else None,
                reply_text=assistant.content if assistant is not None else None,
                failure_reason=None,
                state_version=turn.state_version,
            )
        )

    def _persona_id(self, conversation_id: ConversationId) -> PersonaId:
        record = self._queries.get_conversation(conversation_id)
        if isinstance(record, Ok) and record.value is not None:
            persona = record.value.persona_id
            if persona is not None:
                return persona
        return PersonaId("persona-default")

    def _contract(self, persona_id: PersonaId) -> GenerationContract:
        return GenerationContract(
            generation_contract_id="gc-normal-persona-reply",
            action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
            persona_id=persona_id,
            allowed_disclosures=(),
            language_policy="default",
            style_constraints=(),
        )


_E = TypeVar("_E")


def _missing(message: str) -> Err[_E]:
    return Err(DomainError(code=DomainErrorCode.NOT_FOUND, message=message))


def _conflict(message: str) -> Err[_E]:
    return Err(DomainError(code=DomainErrorCode.CONFLICT, message=message))
