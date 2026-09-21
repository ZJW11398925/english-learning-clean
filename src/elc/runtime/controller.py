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

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeVar

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
    CharacterPackageRecord,
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
    EvidenceModality,
    GateDecisionId,
    InputId,
    MessageSequence,
    MomentId,
    Ok,
    PersonaId,
    PolicyVersion,
    ProjectionJobId,
    ProviderAttemptId,
    Result,
    RuntimeEpoch,
    TurnId,
    TurnSequence,
)
from elc.runtime.decision_cycles import (
    DecisionCycleBindings,
    DecisionCycleStore,
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
from elc.teaching.gate import (
    GATE_POLICY_VERSION,
    GateVerdict,
    UserInitiatedOpenFacts,
)
from elc.teaching.request import (
    TeachingRequest,
    intent_scope_for_request,
    teaching_request_payload,
)
from elc.teaching.store import CP2OpenRequest, cp2_action_intent
from elc.teaching.targets import TeachingTargetProvider, TeachingTargetView
from elc.teaching.types import (
    AuthorizationBasis,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)

if TYPE_CHECKING:
    # Annotations only: the coordinator calls the injected authority faces,
    # and importing the concrete controllers here would deepen the runtime
    # package's import graph for no runtime benefit (the P1/P2 assemblies
    # inject the store ports).
    from elc.learning.controller import LearningController
    from elc.learning.types import LearningSnapshot
    from elc.teaching.controller import TeachingController

#: Delivery certainty for a server-side buffered delivery with no
#: ClientRenderAck yet (STATE_MACHINES §13 ExposureEstimate certainty).
SERVER_SENT_UNCONFIRMED = "SERVER_SENT_UNCONFIRMED"

#: Conversation window size handed to Persona Runtime (RUNTIME §11
#: ConversationWindow view).
CONVERSATION_WINDOW_MAX_TURNS = 20

#: GenerationContract id of the CP2 first teaching action (§20
#: generation_contract_id; the teaching-generation contract itself is
#: P3-1B's — the row is created at PREPARED and not dispatched here).
TEACHING_OPEN_CONTRACT_ID = "gc-teaching-open"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


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


@dataclass(frozen=True)
class TeachingTurnResult:
    """The outcome of one ``request_teaching`` command turn (P3-1A).

    The three Gate outputs map here directly: ALLOW carries
    ``moment_id`` / ``action_id`` / ``moment_state=OPENING`` /
    ``action_status=PREPARED``; DENY carries the reason codes and no
    moment; DEGRADED carries ``missing_or_unknown`` and no decision.

    ``outcome`` stays None in P3-1A: the stop point is CP2 (the opening
    delivery is P3-1B), so no user-visible delivery happened and the turn
    is deliberately left nonterminal with no ``turn_outcome`` — the
    outcome is chosen by the real delivery (STATE_MACHINES §10 "Turn
    outcome 单独记录").
    """

    turn_id: TurnId
    conversation_id: ConversationId
    decision_cycle_id: DecisionCycleId | None
    gate_execution_status: str
    gate_decision: str | None
    reason_codes: tuple[str, ...]
    missing_or_unknown: tuple[str, ...]
    moment_id: MomentId | None
    action_id: ActionId | None
    moment_state: MomentState | None
    action_status: GenerationActionStatus | None
    turn_status: TurnStatus
    outcome: str | None


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
        raise NotImplementedError(
            "DecisionCycle creation is the Runtime-owned DecisionCycleStore"
            " port (elc.runtime.decision_cycles, P3-1A TASK-…17 ②), driven"
            " by ConversationCoordinator — this skeleton entry stays a"
            " pointer"
        )

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
        raise NotImplementedError(
            "use the Runtime-owned DecisionCycleStore read face"
            " (elc.runtime.decision_cycles, P3-1A TASK-…17 ②)"
        )


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
    STATE_MACHINES §10 order). A learning-leg failure degrades per
    RA §21 (REJECTED / durable-pending + normal persona; see
    _run_learning_analysis) — it never blocks the turn. ``learning=None``
    keeps the Phase 1 assembly (the P1 tests pin that loop); no
    DecisionCycle is created here (Phase 3+, DEC-…eaaa5a1d.26 a).

    Phase 3 P3-0 (TASK-…55 ③): the optional ``character_package``
    injection lets the normal path carry a non-None canonical §5.1
    CharacterPackage into the GenerationContext (PromptCompiler consumes
    its fields). ``character_package=None`` keeps the existing assembly
    (the P1 tests pin that loop). Real production package sourcing
    (registry / durable store / persona resolution) is Phase 5 — until
    then tests inject the persona domain's deterministic
    ``sample_character_package`` fixture.

    Phase 3 P3-1A (TASK-…17 ②⑤⑥): four more optional ports turn the same
    coordinator into the user-initiated teaching entry point —

    - ``decision_cycles`` (elc.runtime.decision_cycles.DecisionCycleStore):
      every normal persona turn opens its §4 cycle after CP1, and the
      teaching path opens cycle 0 / repair cycles under the TurnRecord
      state_version CAS;
    - ``learning_controller`` (elc.learning.controller.LearningController):
      the snapshot read + the pre-cycle repair face
      (``stale_projection_targets`` → ``rebuild_learner_state``);
    - ``teaching`` (elc.teaching.controller.TeachingController): the Gate
      profile, CP2, the two other Gate outputs and the durable reads;
    - ``targets`` (elc.teaching.targets.TeachingTargetProvider): the
      narrow target/content validity port the Gate consumes.

    ``request_teaching`` needs all four (otherwise it refuses with
    DEPENDENCY_UNAVAILABLE); ``begin_turn`` only uses ``decision_cycles``
    when it is present. Every other assembly (P1, P2, P3-0) keeps the
    exact behavior its tests pin — the same optional-injection discipline
    as ``learning`` / ``character_package`` above.
    """

    def __init__(
        self,
        lease: ConversationCoordinatorLease,
        conversation_commands: ConversationCommands,
        conversation_queries: ConversationQueries,
        persona: PersonaRuntime,
        generation_actions: GenerationActionStore,
        learning: LearningTurnAnalysis | None = None,
        character_package: CharacterPackageRecord | None = None,
        decision_cycles: DecisionCycleStore | None = None,
        learning_controller: LearningController | None = None,
        teaching: TeachingController | None = None,
        targets: TeachingTargetProvider | None = None,
    ) -> None:
        self._lease = lease
        self._commands = conversation_commands
        self._queries = conversation_queries
        self._persona = persona
        self._generation = generation_actions
        self._learning = learning
        self._character_package = character_package
        self._decision_cycles = decision_cycles
        self._learning_controller = learning_controller
        self._teaching = teaching
        self._targets = targets

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
                    # RA §21 degradation: the learning leg never blocks
                    # the turn (review F1) — Learning's REJECT decision
                    # and an unavailable commit both continue to the
                    # normal persona path, so no dispatch can leave this
                    # turn pinned at ANALYZING (see _run_learning_analysis
                    # for the two degraded outcomes and the no-stuck
                    # argument).
                    self._run_learning_analysis(
                        cp0.turn_id, command.conversation_id
                    )
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

            # RA §4 step 5 / migration 0007 lineage (P3-1A ②): every
            # generation action belongs to a DecisionCycle, and the normal
            # persona turn opens its own — before generation, after the
            # CP1 learning leg (RA §8 analysis-before-planner order). The
            # bindings are all-None on this path: Phase 3 has no
            # Planner/Gate and no Curriculum/Goal/Schedule/Policy source to
            # stamp (planner/gate/快照字段全 NULL; None is the honest "no
            # source", never a fabricated version). Re-entry with an
            # existing cycle replays the durable row (deterministic id, no
            # second write, no extra state_version bump).
            if self._decision_cycles is None:
                return Err(
                    DomainError(
                        code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                        message=(
                            "every generation action must belong to a"
                            " decision cycle (migration 0007); inject the"
                            " DecisionCycleStore"
                        ),
                    )
                )
            cycle_result = self._decision_cycles.record_decision_cycle(
                decision_cycle_id=self._cycle_id(cp0.turn_id, ""),
                turn_id=cp0.turn_id,
                bindings=DecisionCycleBindings(),
                expected_turn_state_version=state_version,
            )
            if isinstance(cycle_result, Err):
                return cycle_result
            active_cycle = cycle_result.value
            version_result = self._turn_state_version(cp0.turn_id)
            if isinstance(version_result, Err):
                return version_result
            state_version = version_result.value

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
                    decision_cycle_id=str(active_cycle.decision_cycle_id),
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
                character_package=self._character_package,
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

    # -- user-initiated teaching open (P3-1A) --------------------------------

    def request_teaching(
        self, request: TeachingRequest
    ) -> Result[TeachingTurnResult]:
        """One user-initiated TeachingMoment command turn (TASK-…17 ⑤⑥).

        Flow (RA §4 with the mother decision's teaching specialization):
        coordinator guard → CP0 (command turn) → Learning snapshot read
        with at most one pre-cycle repair → DecisionCycle → Gate
        USER_INITIATED OPEN (target resolution + durable lock + snapshot
        consistency facts) → CP2 / DENY / DEGRADED. Stop point: CP2 —
        TEACHING_OPEN stays PREPARED and the opening delivery is P3-1B's.

        Deliberate scope notes:

        - a command turn runs no LEARNING_EVIDENCE analysis: nothing was
          said (``raw_content=""``), so there is no observable behavior —
          no TEXT_* Evidence, no analysis artifact, no watermark move, and
          the turn goes USER_COMMITTED → DECIDING without ANALYZING;
        - the turn is never terminalized here (no delivery happened), so
          no ``turn_outcome`` is written — the outcome belongs to the real
          delivery (STATE_MACHINES §10);
        - re-entry (duplicate client_message_id, or a crash after CP2)
          replays the durable outcome instead of re-running the Gate: one
          cycle opens at most one moment (RUNTIME §23);
        - snapshot CONFLICT has exactly two handling points (mother
          decision): PRE-cycle the coordinator repairs the lagging
          targets and re-reads (the Gate never ran, so no DEGRADED row is
          written), POST-cycle the Gate reports DEGRADED with
          ``missing_or_unknown=[LEARNING_SNAPSHOT]`` and the coordinator
          freezes that cycle, opens ``cycle_index+1`` and re-runs the Gate
          once — a second degradation stops with no teaching and both
          DEGRADED rows as the trace. The Gate itself never rebuilds.
        - target resolution failure is deterministic: an unknown target
          (resolver NOT_FOUND) yields MISSING + content INVALID (a target
          that does not exist has no content that could be valid) → DENY
          TARGET_INVALID; any other resolver failure leaves both facts
          UNKNOWN → DEGRADED.
        """

        decision_cycles = self._decision_cycles
        learning = self._learning_controller
        teaching = self._teaching
        targets = self._targets
        if (
            decision_cycles is None
            or learning is None
            or teaching is None
            or targets is None
        ):
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "request_teaching needs the P3-1A assembly"
                        " (decision_cycles + learning_controller + teaching"
                        " + targets injected)"
                    ),
                )
            )

        with self._lease.hold(request.conversation_id):
            cp0_result = self._commands.commit_user_turn(
                CommitUserTurn(
                    conversation_id=request.conversation_id,
                    envelope=InputEnvelope(
                        input_id=self._command_input_id(request),
                        client_message_id=request.client_message_id,
                        conversation_id=str(request.conversation_id),
                        persona_id=None,
                        scene_id=None,
                        interaction_channel=request.interaction_channel,
                        raw_payload=teaching_request_payload(request),
                        received_at=request.requested_at or _now(),
                    ),
                    raw_content="",
                    normalized_content=None,
                    runtime_version=request.runtime_version,
                )
            )
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
                claimed = self._commands.claim_turn_for_recovery(cp0.turn_id)
                if isinstance(claimed, Err):
                    return claimed
                turn = claimed.value

            # Idempotent replay: a turn that already has an active cycle
            # returns the durable Gate outcome (never a second Gate run).
            existing_cycle = decision_cycles.get_active_decision_cycle(
                cp0.turn_id
            )
            if isinstance(existing_cycle, Err):
                return existing_cycle
            if existing_cycle.value is not None:
                return self._replay_teaching(turn, existing_cycle.value, teaching)
            if turn.status in TERMINAL_TURN_STATUSES:
                return _conflict(
                    "terminal teaching turn without an active decision"
                    " cycle: nothing durable to replay"
                )

            state_version = turn.state_version
            if turn.status == TurnStatus.USER_COMMITTED:
                advanced = self._commands.transition_turn(
                    cp0.turn_id, state_version, TurnStatus.DECIDING
                )
                if isinstance(advanced, Err):
                    return advanced
                state_version = advanced.value.state_version
            elif turn.status != TurnStatus.DECIDING:
                return _conflict(
                    "teaching turn re-entry from status"
                    f" {turn.status.value} is outside the P3-1A flow"
                )

            # Pre-cycle snapshot: repair the lagging projection at most
            # once, and only then open the cycle (no Gate run → no
            # DEGRADED row).
            snapshot_result = self._snapshot_with_repair(learning)
            if isinstance(snapshot_result, Err):
                return snapshot_result
            snapshot = snapshot_result.value

            cycle_result = decision_cycles.record_decision_cycle(
                decision_cycle_id=self._cycle_id(cp0.turn_id, ""),
                turn_id=cp0.turn_id,
                bindings=DecisionCycleBindings(
                    learning_snapshot_id=str(snapshot.learning_snapshot_id),
                    evidence_watermark=snapshot.evidence_watermark,
                ),
                expected_turn_state_version=state_version,
            )
            if isinstance(cycle_result, Err):
                return cycle_result
            cycle = cycle_result.value

            candidate_id = f"cand-explicit-{cp0.turn_id}"

            repair_used = False
            while True:
                # Each attempt assembles its facts fresh (the repair cycle
                # is a new execution, not a replay of the frozen one).
                view, target_status, content_status = self._resolve_target(
                    targets, request
                )
                lock_result = teaching.observed_lock_state(
                    request.conversation_id
                )
                lock_state = (
                    lock_result.value if isinstance(lock_result, Ok) else "UNKNOWN"
                )
                facts = UserInitiatedOpenFacts(
                    decision_cycle_id=str(cycle.decision_cycle_id),
                    candidate_id=candidate_id,
                    user_intent_scope=intent_scope_for_request(request),
                    target_status=target_status,
                    content_status=content_status,
                    lock_state=lock_state,
                    learning_snapshot_status=self._snapshot_status(
                        learning, cycle
                    ),
                )
                verdict = teaching.decide_user_initiated_open(facts)
                status_record = self._gate_status_record(
                    cp0.turn_id, cycle, facts, verdict
                )

                if verdict.decision == "ALLOW":
                    return self._commit_teaching_open(
                        request=request,
                        turn_id=cp0.turn_id,
                        cycle=cycle,
                        candidate_id=candidate_id,
                        view=view,
                        verdict=verdict,
                        status_record=status_record,
                        teaching=teaching,
                    )

                if verdict.decision == "DENY":
                    denial = teaching.record_gate_denial(
                        status_record,
                        GateDecisionRecord(
                            gate_decision_id=self._gate_decision_id(
                                cp0.turn_id, cycle
                            ),
                            decision_cycle_id=cycle.decision_cycle_id,
                            candidate_id=candidate_id,
                            context=GateDecisionContext.OPEN,
                            decision=GateDecisionValue.DENY,
                            reason_codes=verdict.reasons,
                            policy_version=PolicyVersion(GATE_POLICY_VERSION),
                        ),
                    )
                    if isinstance(denial, Err):
                        return denial
                    return Ok(
                        self._teaching_result(
                            turn_id=cp0.turn_id,
                            conversation_id=request.conversation_id,
                            turn_status=TurnStatus.DECIDING,
                            cycle=cycle,
                            verdict=verdict,
                        )
                    )

                # DEGRADED: persist the trace; only a snapshot degradation
                # has a repair move (one repair cycle), and only once.
                degraded = teaching.record_gate_degraded(status_record)
                if isinstance(degraded, Err):
                    return degraded
                if repair_used or (
                    "LEARNING_SNAPSHOT" not in verdict.missing_or_unknown
                ):
                    # No teaching, one DEGRADED row: either the single
                    # repair is already spent (two DEGRADED rows are the
                    # trace) or the unknown fact is not the snapshot — a
                    # target/content (or any other) UNKNOWN has no repair
                    # move, so it must not burn a second cycle. No Moment,
                    # no synthetic DENY in either case.
                    return Ok(
                        self._teaching_result(
                            turn_id=cp0.turn_id,
                            conversation_id=request.conversation_id,
                            turn_status=TurnStatus.DECIDING,
                            cycle=cycle,
                            verdict=verdict,
                        )
                    )
                repair_used = True
                repaired = self._snapshot_with_repair(learning)
                if isinstance(repaired, Err):
                    return Ok(
                        self._teaching_result(
                            turn_id=cp0.turn_id,
                            conversation_id=request.conversation_id,
                            turn_status=TurnStatus.DECIDING,
                            cycle=cycle,
                            verdict=verdict,
                        )
                    )
                version_result = self._turn_state_version(cp0.turn_id)
                if isinstance(version_result, Err):
                    return version_result
                next_cycle = decision_cycles.record_decision_cycle(
                    decision_cycle_id=self._cycle_id(cp0.turn_id, "-repair1"),
                    turn_id=cp0.turn_id,
                    bindings=DecisionCycleBindings(
                        learning_snapshot_id=str(
                            repaired.value.learning_snapshot_id
                        ),
                        evidence_watermark=repaired.value.evidence_watermark,
                    ),
                    expected_turn_state_version=version_result.value,
                )
                if isinstance(next_cycle, Err):
                    return next_cycle
                cycle = next_cycle.value

    def _commit_teaching_open(
        self,
        *,
        request: TeachingRequest,
        turn_id: TurnId,
        cycle: DecisionCycleRecord,
        candidate_id: str,
        view: TeachingTargetView | None,
        verdict: GateVerdict,
        status_record: GateExecutionStatusRecord,
        teaching: TeachingController,
    ) -> Result[TeachingTurnResult]:
        """CP2: the five-fact atomic open, then the stop-point result."""

        if view is None:
            return _conflict(
                "Gate ALLOW without a resolved target view (the Gate"
                " degrades on unknown validity, so this is unreachable)"
            )
        moment_id = MomentId(f"tm-{turn_id}")
        gate_decision_id = self._gate_decision_id(turn_id, cycle)
        action_id = ActionId(f"ga-{turn_id}-teaching-open")
        moment = TeachingMomentRecord(
            moment_id=moment_id,
            conversation_id=request.conversation_id,
            persona_id=self._conversation_persona(request.conversation_id),
            source=MomentSource.USER_INITIATED,
            decision_cycle_id=cycle.decision_cycle_id,
            candidate_id=candidate_id,
            gate_decision_id=gate_decision_id,
            focus_target=TeachingTargetRef(
                target_type=request.target_type,
                target_id=str(request.focus_target_id),
            ),
            supporting_targets=(),
            target_mode=request.target_mode
            if request.target_mode is not None
            else view.target_mode,
            learning_intent=view.learning_intent,
            evidence_modality=EvidenceModality(view.evidence_modality),
            evidence_goal=None,
            preferred_support_ceiling=None,
            learning_snapshot_id=cycle.learning_snapshot_id,
            evidence_watermark=cycle.evidence_watermark,
            curriculum_version=cycle.curriculum_version,
            content_version=None,
            policy_version=cycle.policy_version,
            lifecycle_state=MomentState.OPENING,
            presentation_phase=PresentationPhase.INITIAL_PROMPT,
            attempt_index=0,
            support_level=TeachingSupportLevel.NONE,
            completion_outcome=None,
            abort_reason=None,
            state_version=1,
        )
        opened = teaching.commit_cp2_open(
            CP2OpenRequest(
                gate_execution_status=status_record,
                gate_decision=GateDecisionRecord(
                    gate_decision_id=gate_decision_id,
                    decision_cycle_id=cycle.decision_cycle_id,
                    candidate_id=candidate_id,
                    context=GateDecisionContext.OPEN,
                    decision=GateDecisionValue.ALLOW,
                    reason_codes=(),
                    policy_version=PolicyVersion(GATE_POLICY_VERSION),
                ),
                moment=moment,
                action=cp2_action_intent(
                    turn_id=turn_id,
                    moment_id=moment_id,
                    decision_cycle_id=cycle.decision_cycle_id,
                    action_id=action_id,
                    assistant_turn_id=f"aturn-{turn_id}-teaching-open",
                    generation_contract_id=TEACHING_OPEN_CONTRACT_ID,
                    owner_epoch=self._lease.epoch
                    if self._lease.epoch is not None
                    else 1,
                ),
                owner_epoch=self._lease.epoch if self._lease.epoch is not None else 1,
            )
        )
        if isinstance(opened, Err):
            return opened
        return Ok(
            self._teaching_result(
                turn_id=turn_id,
                conversation_id=request.conversation_id,
                turn_status=TurnStatus.DECIDING,
                cycle=cycle,
                verdict=verdict,
                moment_id=opened.value,
                action_id=action_id,
                moment_state=MomentState.OPENING,
                action_status=GenerationActionStatus.PREPARED,
            )
        )

    def _replay_teaching(
        self,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        teaching: TeachingController,
    ) -> Result[TeachingTurnResult]:
        """Replay the durable outcome of a turn that already ran the Gate."""

        moment_result = teaching.get_moment_for_cycle(cycle.decision_cycle_id)
        if isinstance(moment_result, Err):
            return moment_result
        moment = moment_result.value
        if moment is not None:
            action_result = self._generation.get_action_for_turn(turn.turn_id)
            if isinstance(action_result, Err):
                return action_result
            action = action_result.value
            return Ok(
                self._teaching_result(
                    turn_id=turn.turn_id,
                    conversation_id=ConversationId(turn.conversation_id),
                    turn_status=turn.status,
                    cycle=cycle,
                    verdict=GateVerdict(
                        execution_status="SUCCEEDED",
                        decision="ALLOW",
                        primary_reason=None,
                        reasons=(),
                        missing_or_unknown=(),
                    ),
                    moment_id=moment.moment_id,
                    action_id=action.action_id if action is not None else None,
                    moment_state=moment.lifecycle_state,
                    action_status=(
                        action.status if action is not None else None
                    ),
                    decision_cycle_id=cycle.decision_cycle_id,
                )
            )
        statuses = teaching.get_gate_execution_statuses(cycle.decision_cycle_id)
        if isinstance(statuses, Err):
            return statuses
        if not statuses.value:
            return _conflict(
                "active teaching cycle without a Gate outcome: nothing"
                " durable to replay"
            )
        latest = statuses.value[-1]
        decisions = teaching.get_gate_decisions(cycle.decision_cycle_id)
        if isinstance(decisions, Err):
            return decisions
        decision = decisions.value[-1] if decisions.value else None
        verdict = GateVerdict(
            execution_status=latest.status.value,
            decision=decision.decision.value if decision is not None else None,
            primary_reason=(
                decision.reason_codes[0] if decision is not None
                and decision.reason_codes else None
            ),
            reasons=decision.reason_codes if decision is not None else (),
            missing_or_unknown=latest.missing_or_unknown,
        )
        return Ok(
            self._teaching_result(
                turn_id=turn.turn_id,
                conversation_id=ConversationId(turn.conversation_id),
                turn_status=turn.status,
                cycle=cycle,
                verdict=verdict,
            )
        )

    def _teaching_result(
        self,
        *,
        turn_id: TurnId,
        conversation_id: ConversationId,
        turn_status: TurnStatus,
        cycle: DecisionCycleRecord,
        verdict: GateVerdict,
        moment_id: MomentId | None = None,
        action_id: ActionId | None = None,
        moment_state: MomentState | None = None,
        action_status: GenerationActionStatus | None = None,
        decision_cycle_id: DecisionCycleId | None = None,
    ) -> TeachingTurnResult:
        return TeachingTurnResult(
            turn_id=turn_id,
            conversation_id=conversation_id,
            decision_cycle_id=(
                decision_cycle_id
                if decision_cycle_id is not None
                else cycle.decision_cycle_id
            ),
            gate_execution_status=verdict.execution_status,
            gate_decision=verdict.decision,
            reason_codes=verdict.reasons,
            missing_or_unknown=verdict.missing_or_unknown,
            moment_id=moment_id,
            action_id=action_id,
            moment_state=moment_state,
            action_status=action_status,
            turn_status=turn_status,
            outcome=None,
        )

    def _gate_status_record(
        self,
        turn_id: TurnId,
        cycle: DecisionCycleRecord,
        facts: UserInitiatedOpenFacts,
        verdict: GateVerdict,
    ) -> GateExecutionStatusRecord:
        return GateExecutionStatusRecord(
            gate_execution_status_id=(
                f"ges-{turn_id}-{cycle.cycle_index}"
            ),
            decision_cycle_id=cycle.decision_cycle_id,
            moment_id=None,
            gate_context=GateDecisionContext.OPEN,
            authorization_basis=AuthorizationBasis.DECISION_CYCLE,
            authorization_status=facts.authorization_status,
            status=(
                GateExecutionStatusValue.SUCCEEDED
                if verdict.execution_status == "SUCCEEDED"
                else GateExecutionStatusValue.DEGRADED
            ),
            missing_or_unknown=verdict.missing_or_unknown,
        )

    @staticmethod
    def _gate_decision_id(
        turn_id: TurnId, cycle: DecisionCycleRecord
    ) -> GateDecisionId:
        return GateDecisionId(f"gd-{turn_id}-{cycle.cycle_index}")

    @staticmethod
    def _cycle_id(turn_id: TurnId, suffix: str) -> DecisionCycleId:
        """Deterministic cycle id (stable opaque id, DATA_MODEL §1.2):
        derived from the turn + a role suffix, so a crash re-entry
        re-derives the identical id and the store replays the durable row
        instead of double-writing."""

        return DecisionCycleId(f"dcy-{turn_id}{suffix}")

    @staticmethod
    def _command_input_id(request: TeachingRequest) -> InputId:
        """The command turn's stable opaque input id (DATA_MODEL §4/§1.2).

        ``client_message_id`` is OPTIONAL dedupe (mother decision ⑥): with
        one supplied, the input id derives from it, so a repeat call
        dedupes at CP0 to the original turn (replay, not a second turn).
        WITHOUT one there is no dedupe key at all, so every call mints a
        FRESH input id — the P1 uuid-minting precedent
        (``conversation.store._new_id``). A derived constant here would be
        silently deduped by ``_cp0_commit_for_input`` and swallow a
        genuine second request as a replay of the first (review F1); the
        freshness applies to NEW calls only — re-entering an already-open
        turn still goes through the CP0 dedupe / active-cycle replay paths.
        """

        if request.input_id is not None:
            return request.input_id
        if request.client_message_id is not None:
            return InputId(f"in-{request.client_message_id}")
        return InputId(f"in-teaching-{uuid.uuid4().hex}")

    def _snapshot_with_repair(
        self, learning: LearningController
    ) -> Result[LearningSnapshot]:
        """Read the Learning snapshot; on the read-time staleness refusal
        rebuild the lagging targets once and re-read (the P3-1A
        pre-cycle repair — the Gate never runs before this succeeds)."""

        snapshot = learning.get_learning_snapshot()
        if isinstance(snapshot, Ok):
            return snapshot
        if snapshot.error.code != DomainErrorCode.CONFLICT:
            return snapshot
        stale = learning.stale_projection_targets()
        if isinstance(stale, Err):
            return stale
        for target_id, modality in stale.value:
            rebuilt = learning.rebuild_learner_state(target_id, modality)
            if isinstance(rebuilt, Err):
                return rebuilt
        return learning.get_learning_snapshot()

    @staticmethod
    def _snapshot_status(
        learning: LearningController, cycle: DecisionCycleRecord
    ) -> str:
        """The Gate's LEARNING_SNAPSHOT fact: VALID only while the durable
        watermark still equals the cycle's stamp (a commit / supersede /
        invalidate since cycle creation is exactly the staleness the
        DEGRADED path exists for). No repair here — that is the
        coordinator's move, never the Gate's."""

        fresh = learning.get_learning_snapshot()
        if isinstance(fresh, Err):
            return "UNKNOWN"
        if cycle.evidence_watermark is None:
            return "UNKNOWN"
        if fresh.value.evidence_watermark != cycle.evidence_watermark:
            return "UNKNOWN"
        return "VALID"

    @staticmethod
    def _resolve_target(
        targets: TeachingTargetProvider, request: TeachingRequest
    ) -> tuple[TeachingTargetView | None, str, str]:
        resolved = targets.resolve(request.target_type, str(request.focus_target_id))
        if isinstance(resolved, Ok):
            view = resolved.value
            return view, view.target_status, view.content_status
        if resolved.error.code == DomainErrorCode.NOT_FOUND:
            return None, "MISSING", "INVALID"
        return None, "UNKNOWN", "UNKNOWN"

    def _turn_state_version(self, turn_id: TurnId) -> Result[int]:
        current = self._commands.get_turn_record(turn_id)
        if isinstance(current, Err):
            return current
        if current.value is None:
            return _missing(f"turn record not found: {turn_id}")
        return Ok(current.value.state_version)

    def _conversation_persona(
        self, conversation_id: ConversationId
    ) -> PersonaId | None:
        record = self._queries.get_conversation(conversation_id)
        if isinstance(record, Ok) and record.value is not None:
            return record.value.persona_id
        return None

    # -- internals -----------------------------------------------------------

    def _run_learning_analysis(
        self, turn_id: TurnId, conversation_id: ConversationId
    ) -> None:
        """RA §4 steps 3-4 through the injected LearningTurnAnalysis
        port: durable LEARNING_EVIDENCE artifact (idempotent re-entry)
        → Learning validates/commits → CP1 with the durable watermark.

        RA §21 degradation — this leg never blocks the turn (review F1).
        Two degraded outcomes, both with the normal persona reply:

        - REJECTED: Learning's validation refuses the proposal (an
          unobservable behavior) and durably flips the artifact to
          REJECTED; the turn continues and the artifact stays REJECTED
          as the audit trail.
        - pending: the commit is unavailable (every other failure — a
          dependency-down analysis leg, a transient store failure, a
          re-entry CONFLICT on an already-decided artifact). The durable
          proposal stays PRODUCED (pending) and the turn continues —
          deliberately no retry and no block.

        Both are "Learning commit unavailable → durable proposal pending
        + normal persona + no risky automatic remediation" (RA §21).
        RA §8's analysis-before-generation order governs the normal
        path; §21 is the sanctioned degraded path around it.

        Because no failure returns from here, a dispatched turn always
        advances past ANALYZING in the same call: a crash at ANALYZING
        resolves on re-dispatch (the epoch claim adopts the turn, RA
        §24; the leg re-runs and either commits, replays the commit, or
        degrades). The permanent stuck-at-ANALYZING channel of review F1
        (REJECTED artifact → re-entry CONFLICT loop, no terminalize
        path) is therefore unreachable under this semantics — SM §10
        FAILED_RECOVERABLE/FAILED_FINAL terminalization stays reserved
        for the generation/delivery legs (the P1B precedent)."""

        slice_result = self._queries.get_canonical_turn_slice(turn_id)
        if isinstance(slice_result, Err):
            return  # RA §21 degraded path: never block the turn
        slice_ = slice_result.value
        if slice_ is None:
            return  # ditto — unreachable after CP0 in the same call
        learning = self._learning
        assert learning is not None  # caller holds the Phase 2 assembly
        artifact = learning.record_learning_analysis(slice_)
        if isinstance(artifact, Err):
            return  # pending: nothing durable yet, turn continues
        persona_id = self._persona_id(conversation_id)
        # Ok → CP1 durable (the normal RA §4 path). Err → one of the two
        # RA §21 degraded outcomes above; the durable artifact state
        # (REJECTED vs PRODUCED) is Learning's audit trail, not a branch
        # for the coordinator.
        learning.commit_learning_evidence(
            artifact.value, slice_, str(persona_id)
        )

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
