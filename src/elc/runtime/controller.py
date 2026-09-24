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
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Callable, TypeVar

from elc.conversation.commands import CommitUserTurn, ConversationCommands
from elc.conversation.queries import ConversationQueries
from elc.conversation.types import (
    AssistantTurnRecord,
    CanonicalTurnSlice,
    Cp0Commit,
    DeliveryState,
    TurnOutcome,
)
from elc.learning.analysis import LearningTurnAnalysis
from elc.learning.silent_claim import SILENT_EVIDENCE_MODALITY
from elc.learning.target_match import (
    TargetMatchObservation,
    admitted_for_evidence,
    observe_target_match,
)
from elc.persona.runtime import PersonaRuntime, action_intent_for_turn
from elc.persona.types import (
    CharacterPackageRecord,
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
    TeachingPromptView,
)
from elc.planner.ledger import LedgerEvent
from elc.platform.sync import KeyedMutex
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    AttemptId,
    ClientMessageId,
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    EvidenceModality,
    GateDecisionId,
    InputId,
    InteractionChannel,
    LearningOpportunityId,
    MessageSequence,
    MomentId,
    Ok,
    PersonaId,
    PolicyVersion,
    ProjectionJobId,
    ProviderAttemptId,
    Result,
    RuntimeEpoch,
    TargetId,
    TurnId,
    TurnSequence,
    UserId,
)
from elc.relationship.episode import EpisodeView
from elc.relationship.types import RelationshipView
from elc.runtime.automatic_teaching import (
    AutomaticTeachingResult,
    automatic_action_id,
)
from elc.runtime.automatic_turn import (
    AUTOMATIC_OPEN_SLOT,
    AutomaticTurnPlan,
    AutomaticTurnWiring,
    assemble_automatic_turn,
    decide_automatic_turn,
    record_leg_failure,
)
from elc.runtime.decision_cycles import (
    DecisionCycleBindings,
    DecisionCycleStore,
)
from elc.runtime.delivery_records import (
    DeliveryRecordStore,
    ServerDeliveryRecord,
)
from elc.runtime.exposure import (
    exposure_event_id,
    ledger_event_of,
    record_exposure,
    record_skip,
    skip_event_id,
)
from elc.runtime.generation import GenerationActionStore
from elc.runtime.guarded_stream import (
    DeliveryMode,
    StreamRun,
    StreamTransportFactory,
    delivery_mode_of,
    local_single_chunk_transport,
    run_guarded_stream,
)
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.persona_views import PersonaViewSource
from elc.runtime.projections import (
    CP4ProjectionRuntime,
    ProjectionJobView,
    ProjectionRunResult,
)
from elc.runtime.recovery import (
    RECOVERY_KIND_TURN,
    DanglingEvidenceRef,
    StartupRecoveryScanner,
    TeachingEvidenceRefSource,
    TurnRecordRecoverySource,
)
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    DecisionCycleRecord,
    GenerationActionIntentRecord,
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
from elc.teaching.envelope import (
    TeachingControlIntent,
    TeachingResponseEnvelope,
    envelope_refusal,
    teaching_response_payload,
)
from elc.teaching.evaluator import evaluate_attempt, unjudgeable_evaluation
from elc.teaching.evidence import build_evidence_proposal
from elc.teaching.flow import (
    ATTEMPT_OPPORTUNITY_TYPE,
    ATTEMPT_TARGET_EXPLICITNESS,
    DEGRADED_ABORT_REASON,
    answer_key_for,
    attempt_record_for,
    closing_reason_for_gate_denial,
    continuation_facts_for,
    continuation_index_for,
    evaluation_record_for,
    opportunity_id_for,
)
from elc.teaching.gate import (
    GATE_POLICY_VERSION,
    GateVerdict,
    UserInitiatedOpenFacts,
)
from elc.teaching.ladder import (
    HINT_PHASES,
    hint_rung,
    ladder_step,
    ladder_step_refusal,
    phase_rank,
    support_rank,
)
from elc.teaching.limits import TeachingLimits, TeachingLoad
from elc.teaching.next_action import NextAction, decide_next_action
from elc.teaching.request import (
    TeachingRequest,
    intent_scope_for_request,
    teaching_request_payload,
)
from elc.teaching.store import (
    CP2OpenRequest,
    MomentTransition,
    cp2_action_intent,
)
from elc.teaching.targets import TeachingTargetProvider, TeachingTargetView
from elc.teaching.types import (
    AbortReason,
    AttemptOutcome,
    AttemptRecord,
    AuthorizationBasis,
    EphemeralTeachingDirective,
    GateDecisionContext,
    GateDecisionRecord,
    GateDecisionValue,
    GateExecutionStatusRecord,
    GateExecutionStatusValue,
    MomentSource,
    MomentState,
    PresentationPhase,
    ResumeDirective,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from elc.user_config.types import DisclosedUserProfile

if TYPE_CHECKING:
    # Annotations only: the coordinator calls the injected authority faces,
    # and importing the concrete controllers here would deepen the runtime
    # package's import graph for no runtime benefit (the P1/P2 assemblies
    # inject the store ports).
    from elc.learning.analysis import LearningEvidenceProposal
    from elc.learning.controller import LearningController
    from elc.learning.silent_evidence import SilentEvidenceSource
    from elc.learning.target_resolution import ResolvedTarget
    from elc.learning.types import LearningSnapshot
    from elc.teaching.controller import TeachingController

#: Delivery certainty for a server-side buffered delivery with no
#: ClientRenderAck yet (STATE_MACHINES §13 ExposureEstimate certainty).
SERVER_SENT_UNCONFIRMED = "SERVER_SENT_UNCONFIRMED"

#: Conversation window size handed to Persona Runtime (RUNTIME §11
#: ConversationWindow view).
#:
#: The Episode projection reads the same window and declares the same number
#: again as ``elc.relationship.episode.EPISODE_WINDOW_MAX_TURNS`` (that
#: module carries the mirror of this note). The duplication is deliberate:
#: P4-G1 forbids ``elc.relationship`` importing ``elc.runtime``, so neither
#: constant can reference the other, and a test
#: (tests/phase4/test_p4_3_gates.py) holds the equality instead.
CONVERSATION_WINDOW_MAX_TURNS = 20

#: GenerationContract id of the CP2 first teaching action (§20
#: generation_contract_id; the opening action itself is dispatched by
#: :meth:`ConversationCoordinator.request_teaching`).
TEACHING_OPEN_CONTRACT_ID = "gc-teaching-open"

#: §20 generation contract id per teaching action (P3-1B): one contract
#: per action type, so a validator rule change is a contract change.
TEACHING_CONTRACT_BY_ACTION = {
    "TEACHING_OPEN": TEACHING_OPEN_CONTRACT_ID,
    "TEACHING_HINT": "gc-teaching-hint",
    "TEACHING_REVEAL": "gc-teaching-reveal",
    "TEACHING_EXPLANATION": "gc-teaching-explanation",
    "PERSONA_RESUME": "gc-persona-resume",
}

#: delivery kind → §20 action type (the five teaching action types).
TEACHING_ACTION_BY_DELIVERY = {
    "OPENING": "TEACHING_OPEN",
    "HINT": "TEACHING_HINT",
    "RETRY": "TEACHING_HINT",
    "REVEAL": "TEACHING_REVEAL",
    "EXPLANATION": "TEACHING_EXPLANATION",
    "RESUME": "PERSONA_RESUME",
}

#: delivery kind → BF-03 proposed-action word (the continuation Gate's own
#: vocabulary, which is not the §20 action type).
CONTINUATION_ACTION_BY_DELIVERY = {
    "HINT": "HINT",
    "RETRY": "RETRY",
    "REVEAL": "REVEAL",
    "EXPLANATION": "EXPLANATION",
}

#: The SM §1 honest-reply path: a moment accepts a user reply from
#: AWAITING_USER, and the optional attempt walks it through EVALUATING to
#: DECIDING_NEXT_ACTION. Re-entry tolerates any later position on this path
#: (RA §23 resume-from-durable, never a second write).
TEACHING_REPLY_PATH = (
    MomentState.AWAITING_USER,
    MomentState.EVALUATING,
    MomentState.DECIDING_NEXT_ACTION,
)

#: A continuation refusal of the closing kind: the §8 conversion delivers
#: the full form (the frozen reference's terminalizing REVEAL).
CLOSING_FEEDBACK_DELIVERY = "REVEAL"


@dataclass(frozen=True)
class TeachingReplyRequest:
    """One active-teaching turn's input: the user's reply to the moment.

    The envelope is the typed analysis result (STATE_MACHINES §4 / DATA_MODEL
    §16) — Local V1 has no NLU authority over the reply, so the teaching
    meaning travels through :class:`TeachingResponseEnvelope` (or through the
    canonical TEACHING_RESPONSE payload a caller parsed into one), exactly
    like ``TeachingRequest`` and the TEACHING_REQUEST command turn.
    """

    conversation_id: ConversationId
    envelope: TeachingResponseEnvelope
    client_message_id: ClientMessageId | None = None
    input_id: InputId | None = None
    interaction_channel: InteractionChannel = InteractionChannel.TEXT
    requested_at: str | None = None
    runtime_version: str = "runtime-v1"


@dataclass(frozen=True)
class TeachingActionDelivery:
    """One delivered (or failed) teaching action of a teaching turn.

    ``ledger_event`` / ``ledger_failure`` are the §20 exposure write's outcome
    (P8-4): the word recorded (``teaching_presented`` / ``hint_presented`` /
    ``reveal_presented`` / ``user_skip``) when one was, and the readable reason
    when a word existed but the write did not happen. Both stay ``None`` when
    there was nothing to write — §20 has no word for the kind (a retry, an
    explanation, a resume), or no ledger writer was injected — and a failure
    never changes this record's own outcome: the delivery already happened, and
    the exposure record is derived state (R-INV-010's shape).
    """

    action_id: ActionId
    assistant_turn_id: str | None
    text: str | None
    outcome: str
    turn_status: TurnStatus
    state_version: int
    ledger_event: str | None = None
    ledger_failure: str | None = None


@dataclass(frozen=True)
class TeachingReplyTurnResult:
    """The outcome of one teaching reply turn (P3-1B).

    ``outcome`` is the *real* user-visible delivery outcome (REPLIED_FULL /
    NO_ASSISTANT_OUTPUT, or None while the turn is deliberately left
    nonterminal on a re-entry that has durable work left), never a summary
    of internal progress. ``closure`` is the §6 completion outcome or §7
    abort reason the moment closed with (None while the moment is still
    live). ``ledger_event`` / ``ledger_failure`` are the §20 exposure write's
    outcome, carried here so the reply path's reader sees it too (the
    ``TeachingActionDelivery`` docstring states the two fields' meaning).
    """

    turn_id: TurnId
    conversation_id: ConversationId
    moment_id: MomentId
    moment_state: MomentState
    attempt_id: AttemptId | None
    evaluation_outcome: str | None
    evaluation_confidence: float | None
    opportunity_id: str | None
    evidence_commit_id: str | None
    delivery_kind: str | None
    action_type: str | None
    action_id: ActionId | None
    gate_decision: str | None
    gate_reason_codes: tuple[str, ...]
    limit_reason: str | None
    closure: str | None
    next_cycle_id: DecisionCycleId | None
    turn_status: TurnStatus
    outcome: str | None
    reply_text: str | None
    ledger_event: str | None = None
    ledger_failure: str | None = None


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
class StreamedDelivery:
    """One GUARDED_STREAM delivery request (RUNTIME §13, P9-2): the validated
    buffer plus the contract the chunk guard judges the accumulation against.

    The delivery-state/outcome pair of the buffered request is **not** a field
    here: a streamed delivery's terminal word and outcome are what the run
    actually did (the durable prefix decides), so they are produced by
    :meth:`ConversationCoordinator.finalize_streamed_delivery` rather than
    declared by the caller. ``contract`` is the action's own generation
    contract — the guard's rule set is §12's validator over it, never a second
    declaration.
    """

    conversation_id: ConversationId
    turn_id: TurnId
    action_id: ActionId
    assistant_turn_id: str
    text: str
    turn_sequence: TurnSequence
    message_sequence: MessageSequence
    contract: GenerationContract | None = None


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


@dataclass(frozen=True)
class TurnRecoveryClosure:
    """One residual delivery turn the startup recovery brought to a
    terminal state (P3-3 review F7).

    ``outcome`` is the honest TurnOutcome read from the canonical
    transcript (REPLIED_FULL when the assistant turn exists — RA §23 "the
    canonicalized assistant turn is the truth" — else NO_ASSISTANT_OUTPUT).
    ``action_status`` is the *fenced residue*: the old-epoch generation
    action the new epoch may not advance, recorded here so the trace says
    which delivery leg was abandoned rather than pretending it finished.
    """

    turn_id: TurnId
    moment_id: str
    outcome: str
    action_status: str


@dataclass(frozen=True)
class StartupRecoveryOutcome:
    """The result of one startup recovery pass (P3-3 review F6).

    ``plan`` is the pure read the scan produced (RUNTIME §22/§24.1);
    ``recovered_moments`` are the orphan TeachingLockLease moments the
    sweep actually released (the apply face), and ``closed_turns`` are the
    delivery turns that sweep unsealed and this pass reconciled to a
    terminal state (review F7). Every field is durable-fact derived: no
    item appears here that is not also visible through the store reads.

    P4-2 adds the three recovery lines as *defaulted* fields — every
    existing construction (positional and keyword) and every equality
    assertion over the first three fields keeps its exact meaning:

    - ``projection_jobs`` / ``projection_runs`` — the CP4 sweep: the
      crash-gap jobs ``ensure_missing_jobs`` repaired (deterministic ids)
      and what the subsequent ``run_pending`` passes did with them;
    - ``reopened_projections`` — the RUNNING rows of a dead process that
      ``recover_stale_running`` put back on the retry edge *before* that
      sweep (a claim that never reported is residue, not live work — see the
      runtime face for the liveness argument);
    - ``committed_evidence_proposals`` — the durable PENDING teaching
      evidence proposals the explicit retry face landed (DEC-…96 F2);
    - ``dangling_evidence_refs`` — the §17 evaluation refs with no durable
      proposal row (DEC-…96 F1);
    - the three ``*_unavailable`` flags say that an optional recovery line
      could not run at all (an ``Err`` or a raised exception): startup
      completed without it, and the empty tuples above mean "not read",
      never "nothing there". The durable rows stay exactly as they were —
      a pending proposal is still pending, a fenced job still unfinished.
    """

    plan: tuple[RecoveryAction, ...]
    recovered_moments: tuple[str, ...]
    closed_turns: tuple[TurnRecoveryClosure, ...]
    projection_jobs: tuple[ProjectionJobId, ...] = ()
    projection_runs: tuple[ProjectionRunResult, ...] = ()
    projection_recovery_unavailable: bool = False
    committed_evidence_proposals: tuple[str, ...] = ()
    teaching_evidence_retry_unavailable: bool = False
    dangling_evidence_refs: tuple[DanglingEvidenceRef, ...] = ()
    evidence_ref_scan_unavailable: bool = False
    reopened_projections: tuple[ProjectionJobId, ...] = ()


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
        """CP4 projection enqueue — this facade stays a pointer (P4-0's nail).

        The contract lives in the elc.runtime.types module docstring
        (deterministic projection_id, idempotent enqueue, the §22.1
        PENDING → RUNNING → COMMITTED / FAILED_RETRYABLE → REJECTED states,
        source_turn_slice_hash + base_domain_version revalidation on retry,
        no ConversationCoordinatorLease held, a failure that neither rolls
        back the transcript nor re-sends the assistant nor blocks the next
        turn, and ``ensure_projection_jobs`` re-creating a crash-gap job per
        (type, turn) pair from its deterministic id) — and since P4-2 it is
        *implemented* by

            elc.runtime.projections.CP4ProjectionRuntime

        over the durable queue
        ``elc.platform.db.projection_store.SqliteProjectionStore`` (migration
        0002's ``projection_job`` table). This parameterless skeleton entry
        stays a raise on purpose: it is the P4-0 pin that no caller may
        mistake the contract for an implementation, and everything a caller
        would have to decide — which store, which executors, which turn
        source — is an assembly-face concern the injected runtime owns, not
        something this facade could answer.

        (The message keeps naming P4-2 because the contract pin asserts that
        word; the real entry point is the projection runtime above.)
        """

        raise NotImplementedError(
            "CP4 projection enqueue is the injected CP4ProjectionRuntime"
            " (elc.runtime.projections) over"
            " elc.platform.db.projection_store.SqliteProjectionStore; this"
            " facade is the P4-0 pin, never the entry point (P4-2 delivered"
            " the runtime and its post-turn / startup wiring)"
        )

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

    Phase 3 P3-3 (TASK-…47 ②): ``run_startup_recovery`` is the startup
    *entry* that wires the §22 scan to its apply faces — the orphan-lock
    sweep, plus the turn-level reconciliation of the delivery residue that
    sweep unseals (review F6/F7). The reply path's ``DELIVERING`` slot is
    reached before the live-moment guard and adopts a foreign-epoch turn
    only once its leg is actually finishable (review F7).

    Phase 4 P4-2 (TASK-…9 B): the optional ``projections`` port
    (elc.runtime.projections.CP4ProjectionRuntime) turns the same coordinator
    into the CP4 post-turn projection entry point —

    - ``begin_turn`` / ``respond_to_teaching`` run their whole guard body in
      private ``*_guarded`` halves and call
      :meth:`_run_post_turn_projections` *after* the guard is released
      (RA §19: a projection never continues to occupy the
      ConversationCoordinatorLease);
    - a projection failure is never the turn's failure (R-INV-010): the
      Ok result of the turn travels back unchanged and the failure lives in
      the durable job row (PENDING / FAILED_RETRYABLE), which the next turn
      or the startup sweep picks up;
    - ``run_startup_recovery`` gains the CP4 sweep and the two durable-
      backlog lines (DEC-…96 F1/F2) as defaulted outcome fields, so every
      assembly without the port keeps its exact plan shape and every
      existing construction/equality assertion over the plan stays true.

    Phase 4 P4-3 (TASK-OPI-4d516e4f-….19 ⑤): one more optional port,
    ``persona_views`` (elc.runtime.persona_views.PersonaViewSource), lets the
    same coordinator fill the three §11 views of a GenerationContext —

    - ``begin_turn`` and ``respond_to_teaching`` ask it for the persona's
      RelationshipView, the conversation's EpisodeView and the user's
      DisclosedUserProfile, and pass whatever comes back into the
      PromptCompiler request (D-INV-012: the orchestrator only hands over
      views, never prompt text);
    - every read is best-effort: a refusal or an exception becomes ``None``
      for that view and the turn proceeds (RA §21 "Learning commit
      unavailable … normal persona"; §19 "turn still succeeds"). A missing
      view costs the prompt a section, never the user a reply;
    - ``persona_views=None`` (the default, and every assembly before this
      slice) keeps the P1/P2/P3 behavior byte-identical: the three views stay
      ``None`` and the compiled prompt is exactly what it was — the same
      optional-injection discipline as ``learning`` / ``character_package`` /
      ``projections`` above.

    Phase 5 P5-2 (TASK-OPI-4d516e4f-….55 ②): one more optional port,
    ``silent_evidence`` (elc.learning.silent_evidence.SilentEvidenceSource),
    gives the chat leg its target-specific half —

    - on every normal persona turn, before the durable LEARNING_EVIDENCE
      proposal is recorded, the turn is offered to the port once: a §24.5
      form of a supply-eligible target occurring in the utterance is
      resolved, and the observation rides the durable proposal document into
      the same CP1 commit — one silent, target-specific Performance Evidence
      claim (no TeachingMoment, no Gate, no Planner choice: P-INV-009's
      natural-conversation product state);
    - the leg is best-effort in the RA §21 shape: a miss, a broken supply, an
      exception out of the port, an open teaching window on the same target
      (F-2: a full exposure must not produce independent evidence for the
      current Moment's target), a refused commit and a failed rebuild all
      mean "no claim this turn", and the turn proceeds to the normal persona
      reply unchanged;
    - ``silent_evidence=None`` (the default, and every assembly before this
      slice) keeps the P1/P2/P3/P4 behavior byte-identical: nothing is asked,
      nothing is written, and the chat leg's durable trace is exactly the P2A
      one.

    Phase 8 P8-4: one more optional port — ``automatic_teaching``
    (:class:`elc.runtime.automatic_turn.AutomaticTurnWiring`) — lands the
    ordinary turn's **automatic teaching leg**, and it is one bundle rather
    than a port per face because the leg is one chain (the §4 steps 3→8 read
    pass, the Planner run, P8-1's decision unit and the delivery):

    - **``None`` (the default, and every assembly before this slice) keeps the
      turn byte-identical**: the leg is not assembled, the cycle keeps its
      all-``None`` bindings, and no planner / Gate / ledger row is written. The
      opt-in boundary is this constructor argument, and nothing about the
      delivery, delivery-failure or replay paths changes for an assembly that
      does not pass one;
    - when it is injected, the leg runs **inside** the ordinary turn, in RA §4's
      order: the read pass and the Planner run happen before the ``DecisionCycle``
      row is written (so the row carries the bindings they read), the decision
      unit runs after it (Planner half durable → Gate → CP2), and an ALLOW's
      opening is delivered through the *same* teaching delivery leg the
      user-initiated path uses — ``EphemeralTeachingDirective`` → prompt →
      provider → validator → BUFFERED_VALIDATED → canonicalization — with the
      moment reaching ``AWAITING_USER`` only after a real delivery;
    - every failure degrades to the ordinary conversation turn (RA §21) and is
      never silent: a leg that could not assemble is recorded as §4 step 9A's
      degraded planner shape with its reason in the evaluation's trace
      (``elc.runtime.automatic_turn.record_leg_failure``), and a delivery that
      returned no message aborts the moment with the §7 ``DELIVERY_FAILURE``
      word exactly as the user-initiated opening does;
    - the same leg is what **writes §20's exposure events**
      (``elc.runtime.exposure``): a delivered presentation appends its event
      with the Moment as its provenance (migration 0017), and a user skip
      appends ``user_skip`` — once per delivery, through the one delivery leg,
      and never when no ledger writer was injected.

    Phase 9 P9-2: two more optional injections land §13's **other** delivery
    mode — ``GUARDED_STREAM`` — for ordinary persona chat, and both are
    defaulted so every assembly that does not pass them keeps its exact
    behaviour:

    - ``delivery_records`` (``elc.runtime.delivery_records.DeliveryRecordStore``)
      is the §22 record face the streamed delivery writes its
      ``ServerDeliveryRecord`` through: the row opens at ``SENDING``, advances
      per accepted chunk, and freezes at the run's §13 terminal word. When it is
      ``None`` the streamed delivery still happens — the transcript, the
      delivery state, the certainty and the turn/action statuses are
      unchanged — and no §22 row is written: the port's absence is registered,
      never simulated (the same discipline the §20 ledger writer follows just
      above);
    - ``stream_transport`` (``elc.runtime.guarded_stream.StreamTransportFactory``)
      is the client boundary the chunks are released to. Its default is V1's
      in-process placeholder (``local_single_chunk_transport``: the validated
      text leaves as **one** chunk and ``emit`` writes into an in-process
      buffer — V1 has no client render face, ``DEC-…d7937fd7.12``), which is
      why an ordinary turn through this face is field-for-field the buffered
      one.

    ``finalize_delivery`` (the ``BUFFERED_VALIDATED`` face) is untouched by
    that cut and stays the teaching legs' delivery: §13's default table sends
    every teaching action type and ``PERSONA_RESUME`` through it, and only
    ``NORMAL_PERSONA_REPLY`` through the stream
    (``elc.runtime.guarded_stream.delivery_mode_of``).
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
        projections: CP4ProjectionRuntime | None = None,
        persona_views: PersonaViewSource | None = None,
        silent_evidence: SilentEvidenceSource | None = None,
        automatic_teaching: AutomaticTurnWiring | None = None,
        delivery_records: DeliveryRecordStore | None = None,
        stream_transport: StreamTransportFactory | None = None,
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
        self._projections = projections
        self._persona_views = persona_views
        self._silent_evidence = silent_evidence
        self._automatic = automatic_teaching
        self._delivery_records = delivery_records
        self._stream_transport = stream_transport

    # -- minimum turn loop ---------------------------------------------------

    def begin_turn(self, command: CommitUserTurn) -> Result[TurnCompletion]:
        """One full turn: guard → CP0 → generation → buffered validated
        delivery → terminalization. Idempotent on client_message_id
        (duplicate input replays the original turn's terminal result).

        P4-2: the guarded half lives in :meth:`_begin_turn_guarded` and the
        CP4 post-turn projection runs *after* that guard is released — the
        projection must never extend the conversation's one-coordinator
        window (RA §19/§24.1), and its failure must never change this
        result (R-INV-010).
        """

        result = self._begin_turn_guarded(command)
        self._run_post_turn_projections(command.conversation_id, result)
        return result

    def _begin_turn_guarded(
        self, command: CommitUserTurn
    ) -> Result[TurnCompletion]:
        """The guard-holding half of ``begin_turn``: CP0 → learning leg →
        DecisionCycle → generation → buffered validated delivery →
        terminalization, exactly as P1/P2/P3 pinned it."""

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

            # Review F9: a teaching command turn belongs to the teaching
            # pipeline. Recovery must not run it through the normal persona
            # loop — the turn carries an empty utterance whose meaning lives
            # in its typed payload, so answering it would fabricate a reply
            # to silence. The durable payload is the authority.
            command_turn = self._queries.is_command_payload_turn(cp0.turn_id)
            if isinstance(command_turn, Err):
                return command_turn
            if command_turn.value:
                return _conflict(
                    f"turn {cp0.turn_id} is a teaching command turn:"
                    " re-enter through request_teaching / respond_to_teaching,"
                    " never through the normal persona turn loop"
                    " (STATE_MACHINES §1)"
                )

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
            #
            # P8-4: with the automatic leg wired, the cycle's bindings are
            # stamped from what that leg's read pass actually read (an
            # injected wiring is the only path that has such sources; the
            # read pass runs first because the row is the only place they
            # can be recorded, and it writes nothing). The leg itself — the
            # Planner half, the Gate and CP2 — runs *after* the row exists
            # (RA §4 steps 5→8), which is why an assembly failure is
            # recorded against the cycle below rather than before it.
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
            plan_result = (
                None
                if self._automatic is None
                else assemble_automatic_turn(
                    wiring=self._automatic,
                    conversation_id=command.conversation_id,
                    decision_cycle_id=self._cycle_id(cp0.turn_id, ""),
                    as_of=command.envelope.received_at,
                    supply=self._automatic.candidate_supply,
                )
            )
            cycle_result = self._decision_cycles.record_decision_cycle(
                decision_cycle_id=self._cycle_id(cp0.turn_id, ""),
                turn_id=cp0.turn_id,
                bindings=(
                    DecisionCycleBindings()
                    if not isinstance(plan_result, Ok)
                    else plan_result.value.bindings
                ),
                expected_turn_state_version=state_version,
            )
            if isinstance(cycle_result, Err):
                return cycle_result
            active_cycle = cycle_result.value
            version_result = self._turn_state_version(cp0.turn_id)
            if isinstance(version_result, Err):
                return version_result
            state_version = version_result.value

            if isinstance(plan_result, Err):
                # The leg could not assemble: the ordinary turn proceeds (RA
                # §21) and the reason is durable rather than silent (RA §4 step
                # 9A's degraded planner shape, written against the cycle above).
                self._record_automatic_leg_failure(
                    turn_id=cp0.turn_id,
                    decision_cycle_id=active_cycle.decision_cycle_id,
                    reason=plan_result.error.message,
                )
            elif isinstance(plan_result, Ok):
                automatic = self._run_automatic_leg(
                    command=command, cp0=cp0, cycle=active_cycle,
                    plan=plan_result.value,
                )
                if automatic is not None:
                    return automatic

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
            (
                relationship_view,
                episode_view,
                disclosed_profile,
            ) = self._persona_views_for(command.conversation_id, persona_id)
            context = GenerationContext(
                character_package=self._character_package,
                relationship_view=relationship_view,
                episode_view=episode_view,
                world_lore_view=None,
                disclosed_user_profile=disclosed_profile,
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
            if (
                delivery_mode_of(intent.action_type)
                is DeliveryMode.GUARDED_STREAM
            ):
                # RUNTIME §13's default table: ordinary persona chat streams
                # (each chunk guarded before it is released), every teaching
                # action type is delivered buffered-validated.
                return self.finalize_streamed_delivery(
                    StreamedDelivery(
                        conversation_id=command.conversation_id,
                        turn_id=cp0.turn_id,
                        action_id=reply.action_id,
                        assistant_turn_id=reply.assistant_turn_id,
                        text=reply.text,
                        turn_sequence=cp0.turn_sequence,
                        message_sequence=cp0.message_sequence,
                        contract=contract,
                    ),
                    state_version,
                )
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

    # -- the automatic teaching leg (P8-4) -----------------------------------

    def _run_automatic_leg(
        self,
        *,
        command: CommitUserTurn,
        cp0: Cp0Commit,
        cycle: DecisionCycleRecord,
        plan: AutomaticTurnPlan,
    ) -> Result[TurnCompletion] | None:
        """RA §4 steps 9A–10B for one ordinary turn: decide, then deliver.

        ``None`` means "this turn is an ordinary one" — the run did not select,
        the Gate denied, the Gate degraded, or the leg failed (in which case the
        reason is durable; see :meth:`_record_automatic_leg_failure`). A returned
        ``Result`` is an automatic opening that really reached the user: the
        delivery leg owns the transcript, and the moment lands at
        ``AWAITING_USER`` only after a real delivery.

        Two identity reads happen here, and both are the crash window's
        (RA §23 "crash after CP2 → 继续同 ``action_id``"): P8-1's unit re-derives
        the same ids on a re-entry and replays its durable Gate trace instead of
        re-deciding, and the **durable first action of the turn** is read back
        through ``GenerationStore.get_action_for_turn`` as the evidence for
        "continue the same action" — the unit deliberately reports
        ``action_id=None`` on a replay, so the action is read from the row the
        CP2 unit wrote and must be this turn's automatic opening. A missing or
        foreign first action is a state no writer produces, and the leg degrades
        rather than inventing one.
        """

        wiring = self._automatic
        assert wiring is not None  # the caller checks the wiring is injected
        if self._teaching is None:
            # The moment an ALLOW opens is committed through the wiring's
            # teaching face and *landed* through this coordinator's own teaching
            # controller (the one the delivery ladder, the lock release and the
            # terminal transitions belong to). An assembly that wires the second
            # without the first cannot complete the leg, and refusing here — before
            # the unit runs — is what keeps a CP2 that can never be delivered from
            # existing at all (RA §21: no half-open teaching).
            self._record_automatic_leg_failure(
                turn_id=cp0.turn_id,
                decision_cycle_id=cycle.decision_cycle_id,
                reason=(
                    "the automatic leg needs the coordinator's teaching"
                    " controller to land the moment CP2 would open; none was"
                    " injected"
                ),
            )
            return None
        try:
            decided = decide_automatic_turn(
                wiring=wiring,
                plan=plan,
                turn_id=cp0.turn_id,
                conversation_id=command.conversation_id,
                persona_id=self._persona_id(command.conversation_id),
                cycle=cycle,
                owner_epoch=(
                    self._lease.epoch if self._lease.epoch is not None else 1
                ),
            )
        except Exception as exc:  # noqa: BLE001 — a broken leg never blocks a turn
            self._record_automatic_leg_failure(
                turn_id=cp0.turn_id,
                decision_cycle_id=cycle.decision_cycle_id,
                reason=f"the automatic decision raised {exc!r}",
            )
            return None
        if isinstance(decided, Err):
            self._record_automatic_leg_failure(
                turn_id=cp0.turn_id,
                decision_cycle_id=cycle.decision_cycle_id,
                reason=decided.error.message,
            )
            return None
        result = decided.value
        if result.moment_id is None or result.normal_persona_generation:
            # RA §4 9A/9B/10A (and a DEGRADED Gate): nothing was authorized, so
            # the ordinary persona generation owns the rest of this turn.
            return None
        first = self._generation.get_action_for_turn(cp0.turn_id)
        if isinstance(first, Err):
            self._record_automatic_leg_failure(
                turn_id=cp0.turn_id,
                decision_cycle_id=cycle.decision_cycle_id,
                reason=first.error.message,
            )
            return None
        action = first.value
        expected = automatic_action_id(cp0.turn_id)
        if action is None or str(action.action_id) != str(expected):
            self._record_automatic_leg_failure(
                turn_id=cp0.turn_id,
                decision_cycle_id=cycle.decision_cycle_id,
                reason=(
                    "the automatic opening's first action was not found on the"
                    " turn (read back"
                    f" {None if action is None else action.action_id!r},"
                    f" expected {expected!r}); the authorized moment cannot be"
                    " delivered without the action CP2 planned"
                ),
            )
            return None
        return self._finish_automatic_open(
            command=command, cp0=cp0, cycle=cycle, result=result
        )

    def _record_automatic_leg_failure(
        self,
        *,
        turn_id: TurnId,
        decision_cycle_id: DecisionCycleId,
        reason: str,
    ) -> None:
        """Make one failed automatic leg durable, never silent (RA §4 9A).

        The record is P8-0's own unit (``runtime_decision_outcome`` =
        ``DEGRADED_NO_AUTOMATIC_TEACHING``, a ``DEGRADED`` status with **no**
        synthetic decision and the reason in the evaluation's trace); its shape
        and its consequences are stated on
        :func:`elc.runtime.automatic_turn.record_leg_failure`.

        Best-effort by construction (RA §21: the teaching leg never blocks a
        turn): the write's own failure is dropped here, because a turn whose
        leg failed and whose trace cannot be written is still a turn that must
        produce a reply. What is *not* dropped is the failure itself — it is
        this call's whole purpose — and the honest residue of the two failures
        together is registered on the module function above.
        """

        wiring = self._automatic
        if wiring is None:
            return
        try:
            record_leg_failure(
                wiring=wiring,
                turn_id=turn_id,
                decision_cycle_id=decision_cycle_id,
                reason=reason,
            )
        except Exception:  # noqa: BLE001 — never travel into the turn
            return

    def _finish_automatic_open(
        self,
        *,
        command: CommitUserTurn,
        cp0: Cp0Commit,
        cycle: DecisionCycleRecord,
        result: AutomaticTeachingResult,
    ) -> Result[TurnCompletion]:
        """Deliver the authorized opening, then land the open state.

        The delivery leg is the *same* one the user-initiated opening uses
        (:meth:`_deliver_teaching_action`: BUFFERED_VALIDATED → the §14 action
        machine → Validator → canonicalization → TERMINAL), addressed by the
        slot the CP2 unit spelled (``automatic-open``), so a re-entry
        re-dispatches the same durable action rather than minting a second one.

        The landing is :meth:`_finish_teaching_open`'s, with the same two
        outcomes: a real delivery moves the moment ``OPENING`` →
        ``AWAITING_USER`` with the opening phase / support and its ``opened_at``,
        and a delivery that produced no message aborts the episode with the §7
        ``DELIVERY_FAILURE`` word and releases its lock (RA §21 "teaching state
        failure → no-open teaching"): the turn then carries no assistant content,
        exactly as the user-initiated path leaves it, and the *next* turn is an
        ordinary one.
        """

        teaching = self._teaching
        assert teaching is not None  # _run_automatic_leg checked before CP2
        moment_id = result.moment_id
        assert moment_id is not None  # the caller checked the opening exists
        fresh = teaching.get_moment(moment_id)
        if isinstance(fresh, Err):
            return fresh
        if fresh.value is None:
            return _missing(f"moment not found after CP2: {moment_id}")
        moment = fresh.value
        delivery = self._deliver_teaching_action(
            turn_id=cp0.turn_id,
            conversation_id=command.conversation_id,
            turn_sequence=cp0.turn_sequence,
            message_sequence=cp0.message_sequence,
            moment=moment,
            action_type=GenerationActionType.TEACHING_OPEN,
            slot=AUTOMATIC_OPEN_SLOT,
            delivery_kind="OPENING",
            prompt_view=TeachingPromptView(
                action_type=GenerationActionType.TEACHING_OPEN.value,
                presentation_phase=PresentationPhase.INITIAL_PROMPT.value,
                support_level=TeachingSupportLevel.CONTEXT_ONLY.value,
                moment_id=str(moment_id),
                focus_target_type=str(moment.focus_target.target_type),
                focus_target_id=str(moment.focus_target.target_id),
            ),
        )
        if isinstance(delivery, Err):
            return delivery
        delivered = delivery.value
        if delivered.outcome != TurnOutcome.REPLIED_FULL.value:
            aborted = self._abort_opening(
                teaching, moment, AbortReason.DELIVERY_FAILURE.value
            )
            if isinstance(aborted, Err):
                return aborted
            return Ok(self._automatic_completion(cp0.turn_id, delivered))
        if moment.lifecycle_state is MomentState.OPENING:
            moved = teaching.transition_moment(
                moment_id,
                MomentTransition(
                    lifecycle_state=MomentState.AWAITING_USER,
                    presentation_phase=PresentationPhase.INITIAL_PROMPT,
                    support_level=TeachingSupportLevel.CONTEXT_ONLY,
                    opened_at=_now(),
                ),
                moment.state_version,
            )
            if isinstance(moved, Err):
                return moved
        return Ok(self._automatic_completion(cp0.turn_id, delivered))

    @staticmethod
    def _automatic_completion(
        turn_id: TurnId, delivered: TeachingActionDelivery
    ) -> TurnCompletion:
        """The turn-level result of one automatic opening delivery.

        The same shape :meth:`finalize_delivery` answers for an ordinary turn —
        the delivery owns the outcome — plus the §20 exposure write's two
        fields, which the delivery leg recorded.
        """

        return TurnCompletion(
            turn_id=turn_id,
            action_id=delivered.action_id,
            assistant_turn_id=delivered.assistant_turn_id,
            turn_status=delivered.turn_status,
            action_status=GenerationActionStatus.TERMINAL,
            outcome=delivered.outcome,
            reply_text=delivered.text,
            failure_reason=None,
            state_version=delivered.state_version,
            ledger_event=delivered.ledger_event,
            ledger_failure=delivered.ledger_failure,
        )

    # -- the §20 exposure record (P8-4) --------------------------------------

    def _exposed(
        self,
        delivered: Result[TeachingActionDelivery],
        *,
        moment: TeachingMomentRecord,
        delivery_kind: str,
    ) -> Result[TeachingActionDelivery]:
        """The delivery half of the exposure rule: an ``Err`` stays one, a
        delivery that produced **no message** records nothing (nothing was
        presented), and a complete delivery goes through the one write point
        (:meth:`_with_exposure`)."""

        if isinstance(delivered, Err):
            return delivered
        if delivered.value.outcome != TurnOutcome.REPLIED_FULL.value:
            return delivered
        return Ok(
            self._with_exposure(
                delivered.value, moment=moment, delivery_kind=delivery_kind
            )
        )

    def _with_exposure(
        self,
        delivered: TeachingActionDelivery,
        *,
        moment: TeachingMomentRecord,
        delivery_kind: str,
    ) -> TeachingActionDelivery:
        """One §20 event for one delivered teaching action (RA §20).

        The write happens **once per delivery**, at this one point — after a
        message really reached the user (the assistant turn is canonical; a
        failed delivery presents nothing and records nothing). The event id
        derives from the action, so a second attempt would re-offer *the same
        fact* rather than mint a second one; the store's replay rule, however,
        compares the instant as content, and this write stamps a fresh one — so
        such an attempt is refused as ``CONFLICT`` (reported on
        ``ledger_failure``), not silently replayed. No live path makes that
        attempt: a duplicate input replays the durable terminal result
        (:meth:`_replay_terminal`) and never re-enters the delivery leg, and
        the one branch that would re-offer the write
        (:meth:`_deliver_teaching_action`'s terminal branch) is not reachable
        through the ordinary loop today — both facts are registered in
        ``elc.runtime.exposure`` rather than relied on.

        The word is the delivery kind's: an opening is ``teaching_presented``, a
        hint ``hint_presented``, a reveal ``reveal_presented``; §20 carries no
        word for a retry, an explanation or a resume, and this leg registers that
        rather than inventing one. The Moment is the event's provenance
        (migration 0017's column), and the target key is the moment's focus
        target **as spelled** (the core's own key convention).

        R-INV-010's shape: a read or write that fails never changes the delivery
        (the transcript already happened) and is never silent either — the reason
        travels on the returned record's ``ledger_failure``. "Fails" includes a
        writer that raises rather than answering an ``Err`` (the same three
        failure shapes ``elc.runtime.automatic_turn._read`` recognizes for a
        port): catching it here is what keeps a broken ledger out of the turn.
        """

        wiring = self._automatic
        writer = None if wiring is None else wiring.ledger
        if writer is None:
            return delivered
        try:
            event = ledger_event_of(delivery_kind)
            if event is None:
                return delivered
            written = record_exposure(
                writer=writer,
                event_id=exposure_event_id(delivered.action_id),
                event=event,
                target_key=str(moment.focus_target.target_id),
                moment_id=moment.moment_id,
                at=_now(),
            )
        except ValueError as exc:
            return replace(delivered, ledger_failure=str(exc))
        except Exception as exc:  # noqa: BLE001 — a broken writer never blocks
            return replace(
                delivered,
                ledger_failure=f"the exposure write raised {exc!r}",
            )
        if isinstance(written, Err):
            return replace(delivered, ledger_failure=written.error.message)
        return replace(delivered, ledger_event=event.value)

    def _record_skip_exposure(
        self, moment: TeachingMomentRecord
    ) -> tuple[str | None, str | None]:
        """One §20 ``user_skip`` for the moment a user left (§7's abort).

        The same unit as :meth:`_with_exposure`, entered from the abort rather
        than from a delivery: nothing was presented, and §20's fifth word is
        exactly that rejection. The returned pair is ``(the word, the failure
        reason)`` — the abort itself is never blocked or changed by this (§7's
        closure is the moment's, the record is the ledger's).

        Only ``USER_SKIP`` reaches here. §7's other two user-leaving reasons —
        ``USER_REJECTED_TARGET`` / ``USER_TOPIC_SHIFT`` — carry no §20 word
        either (the same registration ``elc.runtime.exposure`` makes for the
        delivery kinds §20 does not name), and the caller asks for this write
        only when the user *skipped*.
        """

        wiring = self._automatic
        writer = None if wiring is None else wiring.ledger
        if writer is None:
            return (None, None)
        try:
            written = record_skip(
                writer=writer,
                event_id=skip_event_id(moment.moment_id),
                target_key=str(moment.focus_target.target_id),
                moment_id=moment.moment_id,
                at=_now(),
            )
        except Exception as exc:  # noqa: BLE001 — a broken writer never blocks
            return (None, f"the exposure write raised {exc!r}")
        if isinstance(written, Err):
            return (None, written.error.message)
        return (LedgerEvent.USER_SKIP.value, None)

    # -- the persona-facing views (P4-3) ------------------------------------

    def _persona_views_for(
        self, conversation_id: ConversationId, persona_id: PersonaId
    ) -> tuple[
        RelationshipView | None, EpisodeView | None, DisclosedUserProfile | None
    ]:
        """Best-effort read of the three §11 views of one turn (P4-3).

        Returns ``(relationship_view, episode_view, disclosed_user_profile)``
        for the GenerationContext. Every leg is *optional* and every failure
        is "no view":

        - no ``persona_views`` port (every assembly before P4-3, and every
          assembly that does not wire one) → three ``None``s, so the compiled
          prompt is byte-identical to what it was before this slice;
        - an ``Err`` from any leg → ``None`` for that leg;
        - an exception escaping any leg (a broken store, a programming error
          beyond the port's own contract) → ``None`` for that leg;
        - an exception escaping the port's own ``user_id`` property → three
          ``None``s (no leg can be asked without a user, so the whole read
          degrades together — the turn still finishes).

        The reason is RA §21's degradation rule, stated for both Phase-4
        projections: a Relationship/Episode read failure must not block the
        turn ("Learning commit unavailable … normal persona"; §19 "turn still
        succeeds / projection retry/rebuild"). A missing view costs the
        prompt a section; a raised exception would cost the user their reply.
        The ``user_id`` leg is inside the guard for exactly that reason: it
        is a *read* like any other, it happens after the transcript is
        already durable, and an unguarded property read that raises would
        have travelled out of ``begin_turn`` — the one thing this method
        exists to prevent (review LOW-1).

        The user leg comes from the port itself (``persona_views.user_id``):
        a ConversationRecord carries no ``user_id`` (DATA_MODEL §3), so the
        assembly owns that fact and the orchestrator only passes it back
        through — see elc.runtime.persona_views for the full reasoning.
        """

        views = self._persona_views
        if views is None:
            return None, None, None
        # ``_user_or_none`` wraps the property read in the same guard as the
        # three legs: without a user there is no leg to ask, so a failure
        # here degrades the whole set rather than escaping the method.
        user_id = self._user_or_none(views)
        if user_id is None:
            return None, None, None
        relationship = self._view_or_none(
            lambda: views.relationship_view(persona_id, user_id)
        )
        episode = self._view_or_none(
            lambda: views.episode_view(conversation_id)
        )
        profile = self._view_or_none(
            lambda: views.disclosed_user_profile(user_id, persona_id)
        )
        return relationship, episode, profile

    @staticmethod
    def _user_or_none(views: PersonaViewSource) -> UserId | None:
        """The port's own user scope, read under the best-effort guard.

        ``Ok(None)`` has no equivalent here — this is a property, not a
        ``Result`` — so the only two outcomes are the id and ``None``
        (unreadable, for any reason).
        """

        try:
            return views.user_id
        except Exception:  # noqa: BLE001 — a read never fails the turn
            return None

    @staticmethod
    def _view_or_none(read: Callable[[], Result[_ViewT]]) -> _ViewT | None:
        """One best-effort view read: ``Ok(value)`` → value, everything else
        → ``None`` (including anything raised outside the port's contract)."""

        try:
            outcome = read()
        except Exception:  # noqa: BLE001 — a read never fails the turn
            return None
        return outcome.value if isinstance(outcome, Ok) else None

    # -- CP4 post-turn projections (P4-2) -----------------------------------

    def _run_post_turn_projections(
        self,
        conversation_id: ConversationId,
        result: Result[TurnCompletion] | Result[TeachingReplyTurnResult],
    ) -> None:
        """Run the CP4 projections for one finished turn — outside the guard.

        Called by ``begin_turn`` / ``respond_to_teaching`` *after* their
        guard-holding halves returned, so the projection never occupies the
        conversation's one-coordinator window (RA §19 "不继续占用
        ConversationCoordinatorLease"; §24.1 "CP4 projection 在 coordinator
        guard release 后执行").

        Failure semantics (R-INV-010; RA §19/§21): a projection failure never
        rolls back the transcript, never re-sends the assistant message and
        never blocks the next turn — so a projection ``Err``, or any
        exception escaping it, is dropped here and the turn's own result is
        returned untouched. The durable job row is the trace: PENDING /
        FAILED_RETRYABLE stays claimable by the next turn's
        ``run_after_turn`` or by the startup sweep (§22 "pending
        projections").

        An ``Err`` turn result is skipped entirely: a turn that did not
        finish canonically has nothing new to project (a failed turn has no
        canonical slice), and enqueueing for it would contradict RA §19
        "默认在 canonical turn 后运行". No projections port means the
        coordinator behaves exactly as before P4-2.
        """

        projections = self._projections
        if projections is None or isinstance(result, Err):
            return
        try:
            projections.run_after_turn(conversation_id, result.value.turn_id)
        except Exception:  # noqa: BLE001 — never travel into the turn
            return

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

    # -- guarded stream delivery (RUNTIME §13 GUARDED_STREAM, P9-2) ----------

    def finalize_streamed_delivery(
        self, delivery: StreamedDelivery, turn_state_version: int
    ) -> Result[TurnCompletion]:
        """GUARDED_STREAM finalization: action READY_TO_DELIVER → DELIVERING →
        the §22 row opens at ``SENDING`` → the chunks go through the guard and
        are released one at a time (each accepted chunk is emitted, then
        advanced to ``SENT_PARTIAL``) → the row freezes at the run's §13
        terminal word → the canonical AssistantTurn is written from the
        **durable** prefix → action TERMINAL → turn terminalization.

        The rules this method adds to the driver's (``elc.runtime.
        guarded_stream`` states the guard, the release-then-record order, the
        empty-chunk reading and the step budget) are the durable ones:

        - the transcript's ``content`` is the durable ``sent_prefix``
          **verbatim** — never the buffered text, never a byte the record did
          not confirm (§17: the sent/confirmed boundary is what is
          canonicalized), so a partial delivery can never carry an unsent
          tail;
        - ``delivery_certainty`` stays ``SERVER_SENT_UNCONFIRMED``: the main
          turn does not wait for a ``ClientRenderAck`` (RA §6) and this cut
          writes no ACK row (P9-4 owns the exposure reconciliation, P9-3 the
          cancellation face);
        - ``SENT_COMPLETE`` → ``REPLIED_FULL``; ``SENT_PARTIAL`` →
          ``REPLIED_PARTIAL``; a run that released nothing is ``FAILED``: no
          AssistantTurn row, the action goes TERMINAL undelivered, the turn
          fails ``FAILED_USER_VISIBLE`` (undelivered provider output never
          enters the transcript, DOMAIN_MODEL §3);
        - a release whose **durable** prefix is empty is the same shape (the
          record is the boundary authority and it holds nothing), so it too
          writes no AssistantTurn row while the row stays ``SENT_PARTIAL`` —
          registered rather than smoothed: "the send began and its record was
          lost" has no honest transcript;
        - an opening write the record face **refuses** stops the delivery
          before the first release (nothing was sent, nothing is claimed) —
          that is a different fact from a face that is not wired, which is
          registered as absence and writes no row at all;
        - a failure *after* the prefix was durably recorded (a stopped source,
          a refused transport, a later refused record write) still delivers
          the prefix: ``SENT_PARTIAL`` / ``REPLIED_PARTIAL`` with the readable
          reason in ``delivery_failure_reason`` — the turn's own
          ``failure_reason`` stays ``None`` because the turn did produce its
          reply, and the two fields never contradict ``reply_text`` (the
          prefix actually sent);
        - a terminal row write the record face refuses leaves the row
          unfrozen (``terminal_at`` unset) while the transcript still carries
          the run's word — the divergence is registered in the reason, not
          hidden (RA §23: a delivery that cannot be reconciled conservatively
          is reported, not replayed).

        Ordering (emit → record), the guard's rule set and version, the
        empty-chunk reading and the step budget are the driver's declared
        readings; the instants come from this class's one clock (``_now``) and
        §21.1 rows are written by no face here. ``turn_state_version`` is
        accepted for symmetry with :meth:`finalize_delivery` (the durable turn
        row's own ``state_version`` is the CAS both faces use).
        """

        action_result = self._generation.get_action(delivery.action_id)
        if isinstance(action_result, Err):
            return action_result
        action = action_result.value
        if action is None:
            return _missing("generation action not found for streamed delivery")
        if action.status == GenerationActionStatus.READY_TO_DELIVER:
            begun = self._persona.begin_delivery(delivery.action_id)
            if isinstance(begun, Err):
                return begun
        elif action.status != GenerationActionStatus.DELIVERING:
            return _conflict(
                "streamed delivery from action status"
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

        started_at = _now()
        record_face = self._delivery_records
        if record_face is not None:
            opened = record_face.record_server_delivery(
                self._delivery_row(
                    delivery,
                    state=DeliveryState.SENDING,
                    sent_prefix="",
                    last_chunk_seq=0,
                    started_at=started_at,
                    terminal_at=None,
                )
            )
            if isinstance(opened, Err):
                return self._stream_without_content(
                    delivery,
                    state=DeliveryState.FAILED.value,
                    reason=(
                        "the delivery record could not be opened:"
                        f" {opened.error.message}"
                    ),
                )

        def _record_chunk(prefix: str, sequence: int) -> Result[None]:
            if record_face is None:
                return Ok(None)
            written = record_face.record_server_delivery(
                self._delivery_row(
                    delivery,
                    state=DeliveryState.SENT_PARTIAL,
                    sent_prefix=prefix,
                    last_chunk_seq=sequence,
                    started_at=started_at,
                    terminal_at=None,
                )
            )
            if isinstance(written, Err):
                return Err(written.error)
            return Ok(None)

        factory = (
            local_single_chunk_transport
            if self._stream_transport is None
            else self._stream_transport
        )
        try:
            transport = factory(
                validated_text=delivery.text, action_id=delivery.action_id
            )
            run = run_guarded_stream(
                transport=transport,
                contract=delivery.contract,
                on_chunk=_record_chunk,
            )
        except Exception as exc:  # noqa: BLE001 — the transport boundary
            run = StreamRun(
                state=DeliveryState.FAILED.value,
                sent_prefix="",
                durable_prefix="",
                chunks=0,
                last_chunk_seq=0,
                failure_reason=(
                    f"the stream boundary raised: {exc} (nothing this run"
                    " released can be proven)"
                ),
            )

        reason = run.failure_reason
        if reason is None and run.stop_reason is not None:
            # The source's own words (verbatim, the driver's reading 6) are the
            # reason a partial delivery stopped short — carried into the
            # delivery-failure field rather than left in the run value.
            reason = f"the source stopped early: {run.stop_reason}"
        terminal_at = _now()
        if record_face is not None:
            frozen = record_face.record_server_delivery(
                self._delivery_row(
                    delivery,
                    state=DeliveryState(run.state),
                    sent_prefix=run.durable_prefix,
                    last_chunk_seq=run.last_chunk_seq,
                    started_at=started_at,
                    terminal_at=terminal_at,
                )
            )
            if isinstance(frozen, Err):
                frozen_reason = (
                    "the delivery record could not be frozen:"
                    f" {frozen.error.message}"
                )
                reason = (
                    frozen_reason
                    if reason is None
                    else f"{reason}; {frozen_reason}"
                )

        if run.durable_prefix == "":
            return self._stream_without_content(
                delivery,
                state=run.state,
                reason=(
                    reason
                    or "the run released no chunk this delivery could record"
                ),
            )

        record = AssistantTurnRecord(
            assistant_turn_id=AssistantTurnId(delivery.assistant_turn_id),
            turn_id=delivery.turn_id,
            conversation_id=delivery.conversation_id,
            turn_sequence=delivery.turn_sequence,
            message_sequence=delivery.message_sequence,
            action_id=delivery.action_id,
            content=run.durable_prefix,
            delivery_state=DeliveryState(run.state),
            delivery_certainty=SERVER_SENT_UNCONFIRMED,
        )
        canonical = self._commands.canonicalize_assistant_turn(record)
        if isinstance(canonical, Err):
            return canonical

        completed = self._persona.complete_delivery(delivery.action_id)
        if isinstance(completed, Err):
            return completed

        outcome = (
            TurnOutcome.REPLIED_FULL
            if run.state == DeliveryState.SENT_COMPLETE.value
            else TurnOutcome.REPLIED_PARTIAL
        )
        terminal = self._commands.terminalize_turn(delivery.turn_id, outcome)
        if isinstance(terminal, Err):
            return terminal
        return Ok(
            TurnCompletion(
                turn_id=delivery.turn_id,
                action_id=delivery.action_id,
                assistant_turn_id=delivery.assistant_turn_id,
                turn_status=terminal.value.status,
                action_status=GenerationActionStatus.TERMINAL,
                outcome=outcome.value,
                reply_text=run.durable_prefix,
                failure_reason=None,
                state_version=terminal.value.state_version,
                delivery_state=run.state,
                delivery_failure_reason=reason,
            )
        )

    def _delivery_row(
        self,
        delivery: StreamedDelivery,
        *,
        state: DeliveryState,
        sent_prefix: str,
        last_chunk_seq: int,
        started_at: str,
        terminal_at: str | None,
    ) -> ServerDeliveryRecord:
        """One §22 row submission for this delivery (the four instants-free
        columns are the delivery's own; the instants are the caller's, the
        p9-1 no-clock rule)."""

        return ServerDeliveryRecord(
            action_id=delivery.action_id,
            assistant_turn_id=AssistantTurnId(delivery.assistant_turn_id),
            state=state.value,
            sent_prefix=sent_prefix,
            last_chunk_seq=last_chunk_seq,
            started_at=started_at,
            terminal_at=terminal_at,
        )

    def _stream_without_content(
        self, delivery: StreamedDelivery, *, state: str, reason: str
    ) -> Result[TurnCompletion]:
        """End a streamed delivery that has **nothing durable to canonicalize**:
        the action goes TERMINAL undelivered and the turn fails
        ``FAILED_USER_VISIBLE``, so undelivered provider output never enters
        the transcript (DOMAIN_MODEL §3). The reason travels in both
        ``failure_reason`` (the turn failed) and ``delivery_failure_reason``
        (why the delivery did)."""

        failed = self._persona.terminalize_failure(
            delivery.action_id, GenerationActionStatus.DELIVERING
        )
        if isinstance(failed, Err):
            return failed
        terminal = self._commands.terminalize_turn(
            delivery.turn_id, TurnOutcome.FAILED_USER_VISIBLE
        )
        if isinstance(terminal, Err):
            return terminal
        return Ok(
            TurnCompletion(
                turn_id=delivery.turn_id,
                action_id=delivery.action_id,
                assistant_turn_id=None,
                turn_status=terminal.value.status,
                action_status=GenerationActionStatus.TERMINAL,
                outcome=TurnOutcome.FAILED_USER_VISIBLE.value,
                reply_text=None,
                failure_reason=reason,
                state_version=terminal.value.state_version,
                delivery_state=state,
                delivery_failure_reason=reason,
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
                # Review F5: a crash between a post-cycle DEGRADED fact and
                # the successor cycle leaves the frozen cycle as the only
                # durable record. The re-entry finishes that one repair
                # instead of replaying "no teaching".
                return self._resume_or_replay_teaching(
                    request=request,
                    cp0=cp0,
                    turn=turn,
                    cycle=existing_cycle.value,
                    targets=targets,
                    teaching=teaching,
                    learning=learning,
                    decision_cycles=decision_cycles,
                )
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

            return self._run_open_gate(
                request=request,
                cp0=cp0,
                cycle=cycle,
                targets=targets,
                teaching=teaching,
                learning=learning,
                decision_cycles=decision_cycles,
            )

    def recover_orphan_teaching(self) -> Result[tuple[str, ...]]:
        """Release the TeachingLockLease rows left behind by a dead runtime
        epoch (STATE_MACHINES §9 / RUNTIME §22; review F2).

        Without this sweep an orphan lock seals the conversation forever:
        every later ``request_teaching`` would be refused with
        TEACHING_LOCK_CONFLICT by a lock whose owner no longer exists. The
        sweep is epoch-based, not TTL-based (Local V1 forbids heartbeat/TTL):
        a lock is orphan exactly when the turn owning its moment belongs to
        an older runtime epoch.

        Returns the recovered moment ids (empty when there is no orphan).
        """

        teaching = self._teaching
        if teaching is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "orphan teaching-lock recovery needs the teaching"
                        " controller (the P3-1A assembly)"
                    ),
                )
            )
        return teaching.recover_orphan_locks()

    def run_startup_recovery(self) -> Result[StartupRecoveryOutcome]:
        """The startup path: scan the old-epoch residue once, then apply
        what a new epoch may apply (review F6).

        RUNTIME §22 makes the startup scan the entry point for old-epoch
        nonterminal work, §24.1 gives each checkpoint its disposition, and
        §24 makes the new epoch the recovery owner. This method is that
        wiring, in one call:

        1. **scan** — ``StartupRecoveryScanner`` (a pure read, §22
           idempotent) over this coordinator's own injected ports: the
           conversation store for old-epoch nonterminal TurnRecords and
           the teaching controller for orphan TeachingLockLease rows.
           Nothing is written here;
        2. **apply the lock sweep** — ``recover_orphan_teaching`` releases
           exactly that residue (STATE_MACHINES §9), closing each orphan
           moment with ``SYSTEM_RECOVERY_ABORT`` and unsealing its
           conversation;
        3. **reconcile the delivery residue** (review F7) — the teaching
           turns that sweep unsealed are brought to a terminal state from
           the canonical transcript (:meth:`_close_residual_turns`).
           Without this step such a turn is nonterminal forever: after the
           moment closed, the reply path refuses it ("no active teaching
           moment"), and the epoch fence forbids this epoch from advancing
           its action — while every later scan keeps naming it.

        P4-2 adds three more lines, each owned by an optional port and each
        invisible when that port is absent (the plan itself never changes —
        §22's plan vocabulary is turns and locks):

        4. **the CP4 sweep** (:meth:`_recover_projections`) — the stale
           RUNNING residue of the dead process is re-opened, the crash-gap
           jobs are re-created from their deterministic ids, and the
           conversations holding either kind of work get one run; startup
           holds no coordinator guard (RA §24.1);
        5. **the durable pending evidence backlog** (:meth:`_retry_pending_evidence`)
           — the explicit retry face of RA §21's "durable proposal pending"
           (DEC-…96 F2);
        6. **the refs↔proposal reconciliation** (:meth:`_reconcile_evidence_refs`)
           — every §17 evaluation ref is checked against Learning's own
           proposal read, and the ones pointing nowhere are reported
           (DEC-…96 F1).

        Lines 4-6 are deliberately failure-tolerant: an ``Err`` or a raised
        exception marks the line unavailable in the outcome and startup still
        completes — a projection backlog or a stuck proposal is durable work
        that the next turn (or the next startup) can still take up, so none
        of them may keep the process from starting.

        Deliberately read-then-write in that order, and deliberately not
        called from the constructor: a host calls it once after the
        startup fence is adopted (the same place ``open_runtime_epoch``
        runs). An assembly without the teaching port keeps its P1/P2 plan
        shape (TURN items only) and closes nothing — there is no teaching
        action in that world to leave residue.
        """

        source = (
            self._commands
            if isinstance(self._commands, TurnRecordRecoverySource)
            else None
        )
        if source is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        "startup recovery needs a TurnRecordRecoverySource"
                        " (the conversation store's recoverable-turn read)"
                    ),
                )
            )
        scanner = StartupRecoveryScanner(source, self._lease, self._teaching)
        plan_result = scanner.scan()
        if isinstance(plan_result, Err):
            return plan_result
        plan = plan_result.value

        recovered: tuple[str, ...] = ()
        if self._teaching is not None:
            swept = self.recover_orphan_teaching()
            if isinstance(swept, Err):
                return swept
            recovered = swept.value

        closed = self._close_residual_turns(plan)
        if isinstance(closed, Err):
            return closed
        (
            reopened_projections,
            projection_jobs,
            projection_runs,
            projections_unavailable,
        ) = self._recover_projections()
        committed_evidence, evidence_retry_unavailable = (
            self._retry_pending_evidence()
        )
        dangling_refs, ref_scan_unavailable = self._reconcile_evidence_refs()
        return Ok(
            StartupRecoveryOutcome(
                plan=plan,
                recovered_moments=recovered,
                closed_turns=closed.value,
                projection_jobs=projection_jobs,
                projection_runs=projection_runs,
                projection_recovery_unavailable=projections_unavailable,
                committed_evidence_proposals=committed_evidence,
                teaching_evidence_retry_unavailable=evidence_retry_unavailable,
                dangling_evidence_refs=dangling_refs,
                evidence_ref_scan_unavailable=ref_scan_unavailable,
                reopened_projections=reopened_projections,
            )
        )

    # -- P4-2: the durable-backlog recovery lines ----------------------------

    def _recover_projections(
        self,
    ) -> tuple[
        tuple[ProjectionJobId, ...],
        tuple[ProjectionJobId, ...],
        tuple[ProjectionRunResult, ...],
        bool,
    ]:
        """The CP4 startup sweep, in three ordered steps.

        1. **re-open the stale RUNNING residue** (``recover_stale_running``)
           — a job claimed by the dead process and never reported back is not
           unfinished-by-choice work, and leaving it RUNNING would strand that
           turn's projection forever (RUNTIME §22's scan covers *pending*
           work; §24.1 makes the new epoch the recovery owner). This runs
           first, so the re-opened rows are already on the retry edge when
           step 3 looks at the queue;
        2. **repair the crash gaps** (``ensure_missing_jobs``): the COMPLETED
           turns whose job row is missing get theirs back under the
           deterministic id, and nothing is re-derived from a message log. A
           job id is a *hash*, so the conversation a repaired job belongs to
           is read back through the job's source turn (job → turn →
           conversation);
        3. **drain the queue** (``run_pending``) once per affected
           conversation, where "affected" is the union of three sets: the
           conversations of the repaired jobs, of the re-opened jobs, and of
           **every unfinished job in the registry**
           (``unfinished_projections``). The third set is what makes the
           sweep a drain rather than a repair: a PENDING row left by a crash
           between its enqueue and its run — or a FAILED_RETRYABLE row no
           turn ever came back for — sits in a conversation the first two
           sets would never name, and the user may never return to it.

        Startup holds no coordinator guard (RA §24.1 "CP4 projection 在
        coordinator guard release 后执行").

        Both failure shapes are trapped: an ``Err`` and a raised exception
        mark the line unavailable and let startup finish — the durable rows
        are untouched either way (a still-pending job stays claimable by the
        next turn's ``run_after_turn``), so a projection problem must not be
        able to stop the process from starting (the F2 rule, applied to the
        same line).
        """

        projections = self._projections
        if projections is None:
            return ((), (), (), False)
        try:
            reopened = projections.recover_stale_running()
            if isinstance(reopened, Err):
                return ((), (), (), True)
            ensured = projections.ensure_missing_jobs()
            if isinstance(ensured, Err):
                return (reopened.value, (), (), True)
            registry = projections.unfinished_projections()
            if isinstance(registry, Err):
                return (reopened.value, ensured.value, (), True)
            runs: list[ProjectionRunResult] = []
            unavailable = False
            for conversation_id in self._projection_conversations(
                projections,
                ensured.value + reopened.value,
                views=registry.value,
            ):
                outcome = projections.run_pending(conversation_id)
                if isinstance(outcome, Ok):
                    runs.extend(outcome.value)
                else:
                    unavailable = True
            return (
                reopened.value,
                ensured.value,
                tuple(runs),
                unavailable,
            )
        except Exception:  # noqa: BLE001 — startup must still complete
            return ((), (), (), True)

    def _projection_conversations(
        self,
        projections: CP4ProjectionRuntime,
        job_ids: tuple[ProjectionJobId, ...],
        *,
        views: tuple[ProjectionJobView, ...] = (),
    ) -> tuple[ConversationId, ...]:
        """The distinct conversations the given work belongs to, in the order
        the sources named it (job → source turn → conversation).

        Two sources of work are accepted: job ids (whose views are read back
        — a job id is a hash) and already-read views (the registry drain,
        which has them in hand). A job whose turn cannot be read is skipped
        rather than guessed at.
        """

        turns: list[TurnId] = [view.source_turn_id for view in views]
        for job_id in job_ids:
            view = projections.job_view(job_id)
            if isinstance(view, Err) or view.value is None:
                continue
            turns.append(view.value.source_turn_id)
        conversations: list[ConversationId] = []
        for turn_id in turns:
            record = self._commands.get_turn_record(turn_id)
            if isinstance(record, Err) or record.value is None:
                continue
            conversation_id = ConversationId(record.value.conversation_id)
            if conversation_id not in conversations:
                conversations.append(conversation_id)
        return tuple(conversations)

    def _retry_pending_evidence(self) -> tuple[tuple[str, ...], bool]:
        """The durable pending teaching-evidence backlog, landed at startup
        (DEC-…5ba74efc.96 F2; RA §21 "durable proposal pending").

        The teaching chain writes the §17 proposal PENDING *before* it
        attempts the commit, so a proposal left behind by a crash (or by an
        unavailable Learning store) is exactly the residue a new epoch may
        land: the retry face replays the commit from the durable payload and
        Learning decides again. Idempotent — committed proposals are not
        revisited (P4-0 ①).

        A failure here must not blow up startup: both an ``Err`` and a raised
        exception mark the line unavailable and leave every durable row
        exactly where it was (still PENDING, still auditable, still
        retryable).
        """

        learning = self._learning_controller
        if learning is None:
            return ((), False)
        try:
            retried = learning.retry_pending_teaching_evidence()
        except Exception:  # noqa: BLE001 — startup must still complete
            return ((), True)
        if isinstance(retried, Err):
            return ((), True)
        return (
            tuple(proposal_id for proposal_id, _ in retried.value),
            False,
        )

    def _reconcile_evidence_refs(
        self,
    ) -> tuple[tuple[DanglingEvidenceRef, ...], bool]:
        """The refs↔proposal reconciliation scan (DEC-…5ba74efc.96 F1).

        Every §17 ``evidence_proposal_refs`` entry a durable evaluation
        recorded is checked against Learning's *own* read face — every ref
        unconditionally, whatever its shape: the authority is the durable
        proposal row, never the teaching side's naming convention (a
        re-derived or prefix-filtered check would be exactly the kind of
        invented rule the F1 review asked to avoid). A ref with no row is
        reported as :class:`DanglingEvidenceRef`: a durable trace that points
        nowhere, named instead of hidden.

        An unreadable row is *not* reported as dangling — the scan line marks
        itself unavailable instead of guessing (an ``Err`` from either read,
        or a raised exception, leaves the verdict empty).
        """

        teaching = self._teaching
        learning = self._learning_controller
        if teaching is None or learning is None:
            return ((), False)
        if not isinstance(teaching, TeachingEvidenceRefSource):
            # An assembly without the scan face has nothing to reconcile —
            # declared, not silently skipped (the protocol is the seam).
            return ((), False)
        try:
            scanned = teaching.evidence_proposal_refs()
            if isinstance(scanned, Err):
                return ((), True)
            dangling: list[DanglingEvidenceRef] = []
            for evaluation_id, refs in scanned.value:
                for ref in refs:
                    proposal = learning.get_teaching_evidence_proposal(ref)
                    if isinstance(proposal, Err):
                        return ((), True)
                    if proposal.value is None:
                        dangling.append(
                            DanglingEvidenceRef(
                                evaluation_id=evaluation_id, ref=ref
                            )
                        )
            return (tuple(dangling), False)
        except Exception:  # noqa: BLE001 — startup must still complete
            return ((), True)

    def _close_residual_turns(
        self, plan: tuple[RecoveryAction, ...]
    ) -> Result[tuple[TurnRecoveryClosure, ...]]:
        """Terminal-state reconciliation for the deadline-less residue
        (review F7).

        The residue has exactly this durable shape, and each clause is a
        fact read back from the store (never from the scan's snapshot):

        - the turn is one of the old-epoch nonterminal turns the plan
          named, and it is still nonterminal;
        - its generation action belongs to a teaching moment
          (``action.moment_id`` set) — every other turn keeps the §23
          re-entry semantics and is left alone;
        - that moment is ``CLOSED``: the episode is over, so nothing will
          ever deliver the pending teaching action — the "crash around
          CP3" leg can neither be replayed (RA §23 forbids blindly
          replaying an uncertain delivery) nor advanced (the epoch fence).

        The outcome is read from the canonical transcript, not invented:
        ``REPLIED_FULL`` when the assistant turn exists (RA §23: the
        canonicalized assistant turn IS the truth), else
        ``NO_ASSISTANT_OUTPUT``. The turn is adopted into the current epoch
        first (RUNTIME §24 restart ownership; ``terminalize_turn`` is
        CAS-guarded and refuses a foreign epoch), and the fenced action is
        left exactly where it stopped — recorded in the closure, never
        advanced by an epoch that does not own it.
        """

        teaching = self._teaching
        if teaching is None:
            return Ok(())
        epoch = self._lease.epoch
        closures: list[TurnRecoveryClosure] = []
        for item in plan:
            if item.kind != RECOVERY_KIND_TURN:
                continue
            turn_id = TurnId(item.id)
            record_result = self._commands.get_turn_record(turn_id)
            if isinstance(record_result, Err):
                return record_result
            record = record_result.value
            if record is None or record.status in TERMINAL_TURN_STATUSES:
                continue
            action_result = self._generation.get_action_for_turn(turn_id)
            if isinstance(action_result, Err):
                return action_result
            action = action_result.value
            if action is None or action.moment_id is None:
                continue
            moment_result = teaching.get_moment(MomentId(action.moment_id))
            if isinstance(moment_result, Err):
                return moment_result
            moment = moment_result.value
            if moment is None or moment.lifecycle_state is not MomentState.CLOSED:
                continue
            slice_result = self._queries.get_canonical_turn_slice(turn_id)
            if isinstance(slice_result, Err):
                return slice_result
            slice_ = slice_result.value
            assistant = None if slice_ is None else slice_.assistant_turn
            if epoch is not None and record.owner_epoch != epoch:
                adopted = self._commands.claim_turn_for_recovery(turn_id)
                if isinstance(adopted, Err):
                    return adopted
            outcome = (
                TurnOutcome.REPLIED_FULL
                if assistant is not None
                else TurnOutcome.NO_ASSISTANT_OUTPUT
            )
            terminal = self._commands.terminalize_turn(turn_id, outcome)
            if isinstance(terminal, Err):
                return terminal
            closures.append(
                TurnRecoveryClosure(
                    turn_id=turn_id,
                    moment_id=str(moment.moment_id),
                    outcome=outcome.value,
                    action_status=action.status.value,
                )
            )
        return Ok(tuple(closures))

    def _run_open_gate(
        self,
        *,
        request: TeachingRequest,
        cp0: Cp0Commit,
        cycle: DecisionCycleRecord,
        targets: TeachingTargetProvider,
        teaching: TeachingController,
        learning: LearningController,
        decision_cycles: DecisionCycleStore,
        repair_used: bool = False,
    ) -> Result[TeachingTurnResult]:
        """The Gate loop of one user-initiated OPEN (P3-1A, resumable).

        Extracted so the post-cycle DEGRADED crash re-entry (review F5) can
        continue the *same* loop from the successor cycle instead of
        re-implementing it: the loop's only state is the cycle it decides
        on and whether the one repair was already spent.
        """

        candidate_id = f"cand-explicit-{cp0.turn_id}"

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
                learning_snapshot_status=self._snapshot_status(learning, cycle),
            )
            verdict = teaching.decide_user_initiated_open(facts)
            status_record = self._gate_status_record(
                cp0.turn_id, cycle, facts, verdict
            )

            if verdict.decision == "ALLOW":
                return self._commit_teaching_open(
                    request=request,
                    cp0=cp0,
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
                        gate_decision_id=self._gate_decision_id(cp0.turn_id, cycle),
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
            if self._is_repair_cycle(cycle):
                return Ok(
                    self._teaching_result(
                        turn_id=cp0.turn_id,
                        conversation_id=request.conversation_id,
                        turn_status=TurnStatus.DECIDING,
                        cycle=cycle,
                        verdict=verdict,
                    )
                )
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
            repair_used = True

    def _resume_or_replay_teaching(
        self,
        *,
        request: TeachingRequest,
        cp0: Cp0Commit,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        targets: TeachingTargetProvider,
        teaching: TeachingController,
        learning: LearningController,
        decision_cycles: DecisionCycleStore,
    ) -> Result[TeachingTurnResult]:
        """Re-enter a turn that already ran the Gate (review F5 + F9 + F2).

        Four durable states are distinguishable, and each has exactly one
        honest move:

        - the frozen cycle already opened a moment that is still ``OPENING``
          → the crash happened between CP2 and the opening delivery: finish
          the open (re-dispatch the same TEACHING_OPEN action id, land
          AWAITING_USER after a real delivery) — the F2 window, which would
          otherwise leave a PREPARED action that no one ever dispatches and
          a held lock that seals the conversation;
        - the frozen cycle carries a *snapshot* DEGRADED outcome and has no
          ``cycle_index + 1`` successor → the crash happened inside the
          repair window: finish the one repair this flow allows (the same
          at-most-one-repair semantics — a repair cycle may not spawn
          another) and continue the Gate loop on the successor;
        - the frozen cycle carries a DEGRADED outcome but is itself a repair
          cycle, or its missing fact is not the snapshot → the trace is
          complete, so replay it (never a third cycle, never a re-run);
        - the frozen cycle carries a decision (or a successor exists) →
          replay the durable outcome: one cycle opens at most one moment,
          and the Gate never re-runs on a decided cycle.
        """

        opened = teaching.get_moment_for_cycle(cycle.decision_cycle_id)
        if isinstance(opened, Err):
            return opened
        if (
            opened.value is not None
            and opened.value.lifecycle_state is MomentState.OPENING
        ):
            return self._finish_teaching_open(
                request=request,
                cp0=cp0,
                turn_id=cp0.turn_id,
                cycle=cycle,
                moment_id=opened.value.moment_id,
                moment=opened.value,
                verdict=GateVerdict(
                    execution_status="SUCCEEDED",
                    decision="ALLOW",
                    primary_reason=None,
                    reasons=(),
                    missing_or_unknown=(),
                ),
                teaching=teaching,
            )

        statuses = teaching.get_gate_execution_statuses(cycle.decision_cycle_id)
        if isinstance(statuses, Err):
            return statuses
        successor = decision_cycles.get_turn_cycle(
            cp0.turn_id, cycle.cycle_index + 1
        )
        if isinstance(successor, Err):
            return successor
        if successor.value is not None:
            return self._replay_teaching(turn, cycle, teaching)
        if not statuses.value:
            return self._replay_teaching(turn, cycle, teaching)
        latest = statuses.value[-1]
        repairable = (
            latest.status is GateExecutionStatusValue.DEGRADED
            and "LEARNING_SNAPSHOT" in latest.missing_or_unknown
            and not self._is_repair_cycle(cycle)
        )
        if not repairable:
            return self._replay_teaching(turn, cycle, teaching)
        repaired = self._snapshot_with_repair(learning)
        if isinstance(repaired, Err):
            return self._replay_teaching(turn, cycle, teaching)
        version = self._turn_state_version(cp0.turn_id)
        if isinstance(version, Err):
            return version
        next_cycle = decision_cycles.record_decision_cycle(
            decision_cycle_id=self._cycle_id(cp0.turn_id, "-repair1"),
            turn_id=cp0.turn_id,
            bindings=DecisionCycleBindings(
                learning_snapshot_id=str(repaired.value.learning_snapshot_id),
                evidence_watermark=repaired.value.evidence_watermark,
            ),
            expected_turn_state_version=version.value,
        )
        if isinstance(next_cycle, Err):
            return next_cycle
        return self._run_open_gate(
            request=request,
            cp0=cp0,
            cycle=next_cycle.value,
            targets=targets,
            teaching=teaching,
            learning=learning,
            decision_cycles=decision_cycles,
            repair_used=True,
        )

    @staticmethod
    def _is_repair_cycle(cycle: DecisionCycleRecord) -> bool:
        """True when a cycle is a same-turn repair cycle (index >= 1).

        The at-most-one-repair rule is expressed on the durable lineage, not
        on a call-frame flag, so a crash re-entry cannot spend the repair
        twice.
        """

        return cycle.cycle_index >= 1

    def _commit_teaching_open(
        self,
        *,
        request: TeachingRequest,
        cp0: Cp0Commit,
        cycle: DecisionCycleRecord,
        candidate_id: str,
        view: TeachingTargetView | None,
        verdict: GateVerdict,
        status_record: GateExecutionStatusRecord,
        teaching: TeachingController,
    ) -> Result[TeachingTurnResult]:
        """CP2: the five-fact atomic open, then the opening delivery.

        P3-1B completes the P3-1A stop point: after the five facts commit,
        the planned TEACHING_OPEN action is dispatched through the P1
        pipeline and the command turn is terminalized with the *real*
        delivery outcome (STATE_MACHINES §10: the outcome belongs to the
        delivery). The moment reaches AWAITING_USER only after the opening
        prompt was sent."""

        turn_id = cp0.turn_id
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
        # P3-1B: the opening delivery. CP2 authorized the moment and planned
        # its first action; the action is now dispatched through the P1
        # pipeline (the §14 action machine + BUFFERED_VALIDATED delivery) so
        # the command turn reaches its real user-visible outcome instead of
        # stopping at DECIDING. The moment becomes AWAITING_USER only when
        # the opening prompt was really sent (SM §1: "opening delivery
        # confirmed/estimated → AWAITING_USER").
        return self._finish_teaching_open(
            request=request,
            cp0=cp0,
            turn_id=cp0.turn_id,
            cycle=cycle,
            moment_id=opened.value,
            moment=moment,
            verdict=verdict,
            teaching=teaching,
        )

    def _finish_teaching_open(
        self,
        *,
        request: TeachingRequest,
        cp0: Cp0Commit,
        turn_id: TurnId,
        cycle: DecisionCycleRecord,
        moment_id: MomentId,
        moment: TeachingMomentRecord,
        verdict: GateVerdict,
        teaching: TeachingController,
    ) -> Result[TeachingTurnResult]:
        """Dispatch (or replay) the opening action, then land the open state.

        Shared by the fresh CP2 path and the crash re-entry (review F2): the
        opening action is addressed by its durable id (``ga-{turn}-
        teaching-open``), so re-entering after a crash between CP2 and the
        delivery re-dispatches *the same action* (RA §23 "CP2 crash → 继续同
        action_id") instead of replaying a stale PREPARED row. The
        AWAITING_USER landing happens only after a real delivery, so a crash
        between the two is closed by the re-entry too.
        """

        delivery = self._deliver_teaching_action(
            turn_id=turn_id,
            conversation_id=request.conversation_id,
            turn_sequence=cp0.turn_sequence,
            message_sequence=cp0.message_sequence,
            moment=moment,
            action_type=GenerationActionType.TEACHING_OPEN,
            slot="teaching-open",
            delivery_kind="OPENING",
            prompt_view=TeachingPromptView(
                action_type=GenerationActionType.TEACHING_OPEN.value,
                presentation_phase=PresentationPhase.INITIAL_PROMPT.value,
                support_level=TeachingSupportLevel.CONTEXT_ONLY.value,
                moment_id=str(moment_id),
                focus_target_type=request.target_type,
                focus_target_id=str(request.focus_target_id),
            ),
        )
        if isinstance(delivery, Err):
            return delivery
        delivered = delivery.value
        fresh = teaching.get_moment(moment_id)
        if isinstance(fresh, Err):
            return fresh
        if fresh.value is None:
            return _missing(f"moment not found after CP2: {moment_id}")
        current = fresh.value
        if delivered.outcome != TurnOutcome.REPLIED_FULL.value:
            # The opening prompt was never shown: the moment must not become
            # "awaiting user" (the user has nothing to answer), so the episode
            # aborts with the §7 delivery-failure word, its lock is released
            # and the episode closes. The turn keeps its real outcome
            # (NO_ASSISTANT_OUTPUT) — the abort is the teaching trace, not a
            # second user-visible message (RA §21: teaching state failure →
            # no-open teaching + normal persona).
            aborted = self._abort_opening(
                teaching, current, AbortReason.DELIVERY_FAILURE.value
            )
            if isinstance(aborted, Err):
                return aborted
            return Ok(
                self._teaching_result(
                    turn_id=turn_id,
                    conversation_id=request.conversation_id,
                    turn_status=delivered.turn_status,
                    cycle=cycle,
                    verdict=verdict,
                    moment_id=moment_id,
                    action_id=delivered.action_id,
                    moment_state=aborted.value.lifecycle_state,
                    action_status=GenerationActionStatus.TERMINAL,
                    outcome=delivered.outcome,
                )
            )
        if current.lifecycle_state is MomentState.OPENING:
            moved = teaching.transition_moment(
                moment_id,
                MomentTransition(
                    lifecycle_state=MomentState.AWAITING_USER,
                    presentation_phase=PresentationPhase.INITIAL_PROMPT,
                    support_level=TeachingSupportLevel.CONTEXT_ONLY,
                    opened_at=_now(),
                ),
                current.state_version,
            )
            if isinstance(moved, Err):
                return moved
            current = moved.value
        return Ok(
            self._teaching_result(
                turn_id=turn_id,
                conversation_id=request.conversation_id,
                turn_status=delivered.turn_status,
                cycle=cycle,
                verdict=verdict,
                moment_id=moment_id,
                action_id=delivered.action_id,
                moment_state=current.lifecycle_state,
                action_status=GenerationActionStatus.TERMINAL,
                outcome=delivered.outcome,
            )
        )

    def _abort_opening(
        self,
        teaching: TeachingController,
        moment: TeachingMomentRecord,
        reason: str,
    ) -> Result[TeachingMomentRecord]:
        """Abort a moment whose opening delivery failed (see the caller).

        The moment walks OPENING → ABORTING → TEACHING_TERMINAL (lock
        released in the same short transaction) → RESUMING → CLOSED. No
        resume action is created: the delivery just failed, so a second
        message would only fail too (RA §23: the resume may be retried or
        recovered by the next turn — never by reopening the moment).
        """

        current = moment
        if current.lifecycle_state is MomentState.OPENING:
            stepped = teaching.transition_moment(
                current.moment_id,
                MomentTransition(
                    lifecycle_state=MomentState.ABORTING, abort_reason=reason
                ),
                current.state_version,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value
        terminal = teaching.terminalize_moment(
            current.moment_id, abort_reason=reason
        )
        if isinstance(terminal, Err):
            return terminal
        current = terminal.value
        for state in (MomentState.RESUMING, MomentState.CLOSED):
            stepped = teaching.transition_moment(
                current.moment_id,
                MomentTransition(
                    lifecycle_state=state,
                    closed_at=None if state is MomentState.RESUMING else _now(),
                ),
                current.state_version,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value
        return Ok(current)

    def _replay_teaching(
        self,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        teaching: TeachingController,
    ) -> Result[TeachingTurnResult]:
        """Replay the durable outcome of a turn that already ran the Gate.

        Review F8: the returned shapes are *reconstructed* — the
        ``GateVerdict`` below is synthesized from the durable rows so the
        caller receives the same result type a fresh run would produce. It
        is a return-value shape, not a new durable fact: nothing is written
        here, and the authoritative record stays the GateExecutionStatus /
        GateDecision / TeachingMoment rows this reads.
        """

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
                    # Reconstructed return shape (review F8), not a durable
                    # fact: the durable record is the GateExecutionStatus /
                    # GateDecision pair read above, and nothing is written
                    # here.
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

    # -- P3-1B: the active-teaching reply turn -------------------------------

    def respond_to_teaching(
        self, request: TeachingReplyRequest
    ) -> Result[TeachingReplyTurnResult]:
        """One active-teaching turn (STATE_MACHINES §4 order, RA §5 pipeline).

            CP0 UserTurn
            → TeachingResponseEnvelope (parse intent, detect attempt)
            → optional AttemptRecord
            → AttemptEvaluationRecord durable
            → Learning evidence commit/proposal (LOR-linked)
            → TeachingMoment state transition
            → continuation Gate (USER_REQUESTED_CONTINUE / ACTIVE_MOMENT)
            → next teaching action / close → resume → CLOSED

        The five-step §4 order is walked in exactly that order. Shape rules
        are refused *before* anything durable beyond CP0
        (:func:`elc.teaching.envelope.envelope_refusal`), SKIP /
        REJECT_TARGET / CHANGE_TOPIC never fabricate an ABSTAIN attempt, and
        an ABSTAIN evaluation produces no evidence at all.

        Re-entry (a crash between two durable steps, or a duplicate
        client_message_id) replays the durable steps: attempt / evaluation /
        opportunity / evidence ids are deterministic on the turn and the
        moment, and every moment move is a state_version CAS.

        P4-2: as with ``begin_turn``, the guard lives in
        :meth:`_respond_to_teaching_guarded` and the CP4 post-turn
        projection runs after it is released (RA §19/§24.1; R-INV-010).
        """

        result = self._respond_to_teaching_guarded(request)
        self._run_post_turn_projections(request.conversation_id, result)
        return result

    def _respond_to_teaching_guarded(
        self, request: TeachingReplyRequest
    ) -> Result[TeachingReplyTurnResult]:
        """The guard-holding half of ``respond_to_teaching`` (P3-1B's §4
        order, unchanged)."""

        ports = self._teaching_ports()
        if isinstance(ports, Err):
            return ports
        decision_cycles, learning, teaching, targets = ports.value

        with self._lease.hold(request.conversation_id):
            cp0_result = self._commands.commit_user_turn(
                CommitUserTurn(
                    conversation_id=request.conversation_id,
                    envelope=InputEnvelope(
                        input_id=self._teaching_reply_input_id(request),
                        client_message_id=request.client_message_id,
                        conversation_id=str(request.conversation_id),
                        persona_id=None,
                        scene_id=None,
                        interaction_channel=request.interaction_channel,
                        raw_payload=teaching_response_payload(request.envelope),
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
            if (
                epoch is not None
                and turn.owner_epoch != epoch
                and turn.status is not TurnStatus.DELIVERING
            ):
                claimed = self._commands.claim_turn_for_recovery(cp0.turn_id)
                if isinstance(claimed, Err):
                    return claimed
                turn = claimed.value
            if turn.status in TERMINAL_TURN_STATUSES:
                reconciled = self._reconcile_moment_ladder(
                    turn_id=cp0.turn_id, teaching=teaching, targets=targets
                )
                if isinstance(reconciled, Err):
                    return reconciled
                return self._replay_teaching_reply(turn, teaching)

            # §4 step 1 (parse): the envelope is already typed; its shape is
            # checked before any teaching write.
            refusal = envelope_refusal(request.envelope)
            if refusal is not None:
                return Err(refusal)

            if turn.status is TurnStatus.DELIVERING:
                # P3-2 carry-over ② (DEC-…5ba74efc.20): the delivery was in
                # flight when the process died. RA §23 "crash around CP3 →
                # the canonicalized assistant turn is the truth" — the
                # re-entry finishes the leg from the durable record instead
                # of refusing the turn forever (a DELIVERING reply turn used
                # to be a permanent dead end for itself, with its moment left
                # live at DECIDING_NEXT_ACTION holding the lock).
                #
                # P3-3 review F7: this slot is reconciled *before* the live
                # moment is required, and the turn is adopted into the
                # current epoch only when the leg is actually finishable (see
                # ``_reconcile_delivering_reply``). Two residues disappear:
                # a DELIVERING turn whose moment already closed used to be
                # refused by the moment guard ("no active teaching moment"),
                # and a turn the epoch fence refuses used to be *adopted*
                # first — which hid the residue from the startup scan
                # (``owner_epoch != current``) without giving anyone the
                # right to finish it.
                return self._reconcile_delivering_reply(
                    turn=turn, teaching=teaching, targets=targets
                )

            moment_result = teaching.get_active_moment(request.conversation_id)
            if isinstance(moment_result, Err):
                return moment_result
            moment = moment_result.value
            if moment is None:
                return _conflict(
                    "no active teaching moment: a teaching reply only exists"
                    " inside a live moment (STATE_MACHINES §2)"
                )
            if moment.lifecycle_state not in TEACHING_REPLY_PATH:
                return _conflict(
                    "moment"
                    f" {moment.moment_id} is {moment.lifecycle_state.value};"
                    " a reply enters through AWAITING_USER (re-entry resumes"
                    " along EVALUATING → DECIDING_NEXT_ACTION)"
                )

            state_version = turn.state_version
            if turn.status == TurnStatus.USER_COMMITTED:
                advanced = self._commands.transition_turn(
                    cp0.turn_id, state_version, TurnStatus.DECIDING
                )
                if isinstance(advanced, Err):
                    return advanced
                state_version = advanced.value.state_version
            elif turn.status not in (TurnStatus.DECIDING, TurnStatus.GENERATING):
                # GENERATING is a legitimate re-entry slot: the delivery was
                # already in flight when the process died, and every step of
                # this flow is idempotent (attempt by (moment, user turn),
                # evaluation and action by deterministic id, Gate by durable
                # fact). Anything else is a different flow's turn.
                return _conflict(
                    "teaching reply re-entry from status"
                    f" {turn.status.value} is outside the P3-1B flow"
                )

            cycle_result = decision_cycles.record_decision_cycle(
                decision_cycle_id=self._cycle_id(cp0.turn_id, ""),
                turn_id=cp0.turn_id,
                bindings=self._reply_cycle_bindings(learning, moment),
                expected_turn_state_version=state_version,
            )
            if isinstance(cycle_result, Err):
                return cycle_result
            cycle = cycle_result.value

            # §4 steps 2-3: attempt → evaluation (durable) → evidence.
            attempt: AttemptRecord | None = None
            evaluation = None
            opportunity_id: str | None = None
            evidence_commit_id: str | None = None
            view: TeachingTargetView | None = None
            resolved = targets.resolve(
                str(moment.focus_target.target_type),
                str(moment.focus_target.target_id),
            )
            if isinstance(resolved, Ok):
                view = resolved.value
            # Review F4: the capability linkage is only usable when the
            # provider can actually resolve the declared capability. An
            # undeclared/unreachable id must never be recorded as positive
            # evidence, so the refusal is decided here, at the assembly, and
            # traced on the proposal.
            linkage = self._verified_capability_linkage(view, targets)

            if (
                request.envelope.attempt_present
                and request.envelope.attempt is not None
            ):
                evaluating = self._advance_reply_path(moment, 1, teaching)
                if isinstance(evaluating, Err):
                    return evaluating
                moment = evaluating.value
                # Review F3: the (moment, user turn) pair is the attempt's
                # identity. A re-entry reads the durable attempt it already
                # recorded — deriving a fresh index from the moment's counter
                # would record a SECOND attempt for the same reply (inflating
                # the §8 budget and orphaning the first evaluation's
                # evidence_proposal_refs).
                existing_attempt = teaching.get_attempt_for_turn(
                    moment.moment_id, cp0.user_turn_id
                )
                if isinstance(existing_attempt, Err):
                    return existing_attempt
                if existing_attempt.value is not None:
                    attempt = existing_attempt.value
                else:
                    index = continuation_index_for(moment)
                    attempt = attempt_record_for(
                        moment=moment,
                        attempt_id=f"at-{cp0.turn_id}-{index}",
                        user_turn_id=str(cp0.user_turn_id),
                        attempt_index=index,
                    )
                    recorded_attempt = teaching.record_attempt(attempt)
                    if isinstance(recorded_attempt, Err):
                        return recorded_attempt
                    # The store may have replayed a durable row for this
                    # (moment, user turn) pair; the durable attempt is the
                    # authority for everything that follows (ids, index).
                    durable_attempt = teaching.get_attempt_for_turn(
                        moment.moment_id, cp0.user_turn_id
                    )
                    if isinstance(durable_attempt, Err):
                        return durable_attempt
                    if durable_attempt.value is None:
                        return _missing(
                            "attempt not found after recording:"
                            f" {attempt.attempt_id}"
                        )
                    attempt = durable_attempt.value
                # The durable record also advanced the moment's own
                # attempt counter / state_version in the same transaction, so
                # the in-memory view is refreshed before the next CAS.
                refreshed = self._refresh_moment(moment.moment_id, teaching)
                if isinstance(refreshed, Err):
                    return refreshed
                moment = refreshed.value
                evaluation = (
                    evaluate_attempt(
                        request.envelope.attempt.text, answer_key_for(view)
                    )
                    if view is not None
                    else unjudgeable_evaluation()
                )
                # The evaluation id is deterministic on the attempt, and the
                # durable proposal (P4-0 ①) is keyed by the same attempt — so
                # the id is computed once here and travels into both the §17
                # row and the Learning chain's source_evaluation_id.
                evaluation_id = f"ae-{attempt.attempt_id}"
                recorded_evaluation = teaching.record_attempt_evaluation(
                    evaluation_record_for(
                        moment=moment,
                        attempt=attempt,
                        evaluation=evaluation,
                        evaluation_id=evaluation_id,
                    )
                )
                if isinstance(recorded_evaluation, Err):
                    return recorded_evaluation
                if moment.presentation_phase is PresentationPhase.FULL_REVEAL:
                    # STATE_MACHINES §3: an attempt made after the full form
                    # was shown is the *post-reveal* attempt, and the moment
                    # says so — the phase records the real exposure ladder
                    # position, not just the lifecycle state.
                    revealed = teaching.transition_moment(
                        moment.moment_id,
                        MomentTransition(
                            presentation_phase=(
                                PresentationPhase.POST_REVEAL_OPTIONAL_ATTEMPT
                            )
                        ),
                        moment.state_version,
                    )
                    if isinstance(revealed, Err):
                        return revealed
                    moment = revealed.value
                if evaluation.outcome is not AttemptOutcome.ABSTAIN:
                    opportunity_id, evidence_commit_id = self._commit_attempt_evidence(
                        cp0=cp0,
                        moment=moment,
                        attempt=attempt,
                        evaluation=evaluation,
                        evaluation_id=evaluation_id,
                        view=view,
                        linkage=linkage,
                        learning=learning,
                    )

            deciding = self._advance_reply_path(moment, 2, teaching)
            if isinstance(deciding, Err):
                return deciding
            moment = deciding.value

            # §4 steps 4-5: apply the control intent, then the next action.
            load = teaching.teaching_load(moment.moment_id)
            limits = TeachingLimits()
            plan = decide_next_action(
                envelope=request.envelope,
                evaluation_outcome=(
                    None if evaluation is None else evaluation.outcome.value
                ),
                support_level_before_attempt=(
                    moment.support_level.value
                    if attempt is None
                    else attempt.support_level_before_attempt.value
                ),
                limits=limits,
                load=load,
            )
            result = self._execute_next_action(
                cp0=cp0,
                turn=turn,
                cycle=cycle,
                moment=moment,
                plan=plan,
                envelope=request.envelope,
                view=view,
                attempt=attempt,
                evaluation=evaluation,
                opportunity_id=opportunity_id,
                evidence_commit_id=evidence_commit_id,
                load=load,
                limits=limits,
                targets=targets,
                teaching=teaching,
                decision_cycles=decision_cycles,
            )
            return result

    def _execute_next_action(
        self,
        *,
        cp0: Cp0Commit,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        moment: TeachingMomentRecord,
        plan: NextAction,
        envelope: TeachingResponseEnvelope,
        view: TeachingTargetView | None,
        attempt: AttemptRecord | None,
        evaluation,
        opportunity_id: str | None,
        evidence_commit_id: str | None,
        load: TeachingLoad,
        limits: TeachingLimits,
        targets: TeachingTargetProvider,
        teaching: TeachingController,
        decision_cycles: DecisionCycleStore,
    ) -> Result[TeachingReplyTurnResult]:
        """Execute the decided branch: continuation, closure, or switch.

        A continuation is additionally authorized by the Gate's
        USER_REQUESTED_CONTINUE profile (the frozen BF-03 continuation
        branch with ACTIVE_MOMENT authorization) before anything is
        delivered; a refusal converts to the closing move or to an honest
        abort, never to a silent drop.
        """

        base = {
            "cp0": cp0,
            "turn": turn,
            "cycle": cycle,
            "attempt": attempt,
            "evaluation": evaluation,
            "opportunity_id": opportunity_id,
            "evidence_commit_id": evidence_commit_id,
            "limits": limits,
            "load": load,
        }

        if envelope.control_intent is TeachingControlIntent.SWITCH_TARGET:
            # SM §2: close the current moment, THEN open the same turn's next
            # DecisionCycle (the cycle_index+1 mechanism is P3-1A's).
            closed = self._terminalize_moment(moment, plan, teaching)
            if isinstance(closed, Err):
                return closed
            version = self._turn_state_version(cp0.turn_id)
            if isinstance(version, Err):
                return version
            next_cycle = decision_cycles.record_decision_cycle(
                decision_cycle_id=self._cycle_id(cp0.turn_id, "-switch1"),
                turn_id=cp0.turn_id,
                bindings=self._reply_cycle_bindings(
                    self._learning_controller, moment
                ),
                expected_turn_state_version=version.value,
            )
            if isinstance(next_cycle, Err):
                return next_cycle
            return self._resume_and_close(
                moment=closed.value,
                plan=plan,
                view=view,
                next_cycle_id=next_cycle.value.decision_cycle_id,
                **base,
            )

        if plan.moment_state is MomentState.ABORTING:
            # The user is leaving (SKIP / REJECT_TARGET / CHANGE_TOPIC): no
            # teaching action to authorize, so the continuation Gate is not
            # consulted — the envelope itself is the instruction.
            closed = self._terminalize_moment(moment, plan, teaching)
            if isinstance(closed, Err):
                return closed
            return self._resume_and_close(
                moment=closed.value, plan=plan, view=view, **base
            )

        if plan.is_closure:
            # The next action is already a closure (SUCCESS, or the §8
            # conversion). A conversion still asks the continuation Gate
            # about the move it *refused*, so the durable trace says why the
            # episode stopped instead of only that it did — one decision per
            # turn, never a second row for the same turn.
            gate_decision: str | None = None
            gate_reasons: tuple[str, ...] = ()
            if plan.refused_kind is not None:
                refused = self._continuation_gate(
                    turn_id=cp0.turn_id,
                    cycle=cycle,
                    moment=moment,
                    plan=NextAction(
                        moment_state=plan.moment_state,
                        delivery_kind=plan.refused_kind,
                        closure=None,
                        completion_outcome=None,
                        abort_reason=None,
                    ),
                    view=view,
                    load=load,
                    limits=limits,
                    teaching=teaching,
                )
                if isinstance(refused, Err):
                    return refused
                gate_decision = refused.value.decision
                gate_reasons = refused.value.reasons
            closed = self._terminalize_moment(moment, plan, teaching)
            if isinstance(closed, Err):
                return closed
            return self._resume_and_close(
                moment=closed.value,
                plan=plan,
                view=view,
                gate_decision=gate_decision,
                gate_reason_codes=gate_reasons,
                **base,
            )

        verdict = self._continuation_gate(
            turn_id=cp0.turn_id,
            cycle=cycle,
            moment=moment,
            plan=plan,
            view=view,
            load=load,
            limits=limits,
            teaching=teaching,
        )
        if isinstance(verdict, Err):
            return verdict
        gate = verdict.value

        if gate.execution_status == "DEGRADED":
            # RA §21 "Teaching state failure": abort, no teaching action,
            # normal persona resumes.
            return self._abort_and_resume(
                moment=moment,
                reason=DEGRADED_ABORT_REASON,
                view=view,
                gate_decision=None,
                gate_reason_codes=gate.missing_or_unknown,
                **base,
            )

        if gate.decision != "ALLOW":
            hard = [
                code
                for code in gate.reasons
                if code.startswith("HARD_")
            ]
            if hard:
                # The §8 exemption: a hard cap blocks the new hint/retry but
                # allows the terminalizing reveal, so the episode closes with
                # the answer shown.
                closing = NextAction(
                    moment_state=MomentState.COMPLETING,
                    delivery_kind=CLOSING_FEEDBACK_DELIVERY,
                    closure="REVEALED",
                    completion_outcome="REVEALED",
                    abort_reason=None,
                    terminalizing=True,
                    limit_reason=hard[0],
                )
                closed = self._terminalize_moment(moment, closing, teaching)
                if isinstance(closed, Err):
                    return closed
                return self._resume_and_close(
                    moment=closed.value,
                    plan=closing,
                    view=view,
                    gate_decision=gate.decision,
                    gate_reason_codes=gate.reasons,
                    **base,
                )
            return self._abort_and_resume(
                moment=moment,
                reason=closing_reason_for_gate_denial(gate.reasons),
                view=view,
                gate_decision=gate.decision,
                gate_reason_codes=gate.reasons,
                **base,
            )

        return self._deliver_continuation(
            moment=moment,
            plan=plan,
            view=view,
            gate_decision=gate.decision,
            gate_reason_codes=gate.reasons,
            targets=targets,
            teaching=teaching,
            **base,
        )

    def _replay_continuation_gate(
        self,
        turn_id: TurnId,
        cycle: DecisionCycleRecord,
        teaching: TeachingController,
    ) -> Result[GateVerdict] | None:
        """The durable continuation verdict of one turn, or None.

        None means "this turn has not decided a continuation yet" — the
        caller runs the Gate. A recorded fact pair is reconstructed into the
        same :class:`GateVerdict` shape the fresh decision would have
        (review F1): a *reconstructed* value, not a new durable fact.
        """

        status_id = f"ges-{turn_id}-continuation"
        statuses = teaching.get_gate_execution_statuses(cycle.decision_cycle_id)
        if isinstance(statuses, Err):
            return statuses
        recorded = next(
            (
                status
                for status in statuses.value
                if str(status.gate_execution_status_id) == status_id
            ),
            None,
        )
        if recorded is None:
            return None
        if recorded.status is GateExecutionStatusValue.DEGRADED:
            return Ok(
                GateVerdict(
                    execution_status="DEGRADED",
                    decision=None,
                    primary_reason=None,
                    reasons=(),
                    missing_or_unknown=recorded.missing_or_unknown,
                )
            )
        decisions = teaching.get_gate_decisions(cycle.decision_cycle_id)
        if isinstance(decisions, Err):
            return decisions
        decision_id = f"gd-{turn_id}-continuation"
        decision = next(
            (
                row
                for row in decisions.value
                if str(row.gate_decision_id) == decision_id
            ),
            None,
        )
        if decision is None:
            return _conflict(
                "durable continuation Gate status without its decision:"
                " nothing coherent to replay"
            )
        allow = decision.decision is GateDecisionValue.ALLOW
        return Ok(
            GateVerdict(
                execution_status="SUCCEEDED",
                decision="ALLOW" if allow else "DENY",
                primary_reason=(
                    None if allow or not decision.reason_codes
                    else decision.reason_codes[0]
                ),
                reasons=decision.reason_codes,
                missing_or_unknown=(),
            )
        )

    def _deliver_continuation(
        self,
        *,
        cp0: Cp0Commit,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        moment: TeachingMomentRecord,
        plan: NextAction,
        view: TeachingTargetView | None,
        attempt: AttemptRecord | None,
        evaluation,
        opportunity_id: str | None,
        evidence_commit_id: str | None,
        load: TeachingLoad,
        limits: TeachingLimits,
        targets: TeachingTargetProvider,
        teaching: TeachingController,
        gate_decision: str | None,
        gate_reason_codes: tuple[str, ...],
    ) -> Result[TeachingReplyTurnResult]:
        """Deliver one authorized continuation and keep the moment live.

        Order matters (review F1): the ladder phase/support are landed *after*
        the delivery, because the phase is a claim about what the user was
        actually shown. A crash between the two therefore leaves the moment
        at its old rung — the re-entry recomputes the identical step and
        replays the same action id — instead of leaving the ladder advanced
        with nothing delivered. A delivery that produced no message aborts
        the episode with the §7 ``DELIVERY_FAILURE`` word (RA §21: teaching
        state failure closes teaching, and the lock is released), so the
        moment can never sit at DECIDING_NEXT_ACTION forever.
        """

        kind = plan.delivery_kind or "RETRY"
        step = ladder_step(
            current_phase=moment.presentation_phase.value,
            current_support=moment.support_level.value,
            hint_ladder=() if view is None else view.hint_ladder,
            reveal_form=None if view is None else view.reveal_form,
            delivery_kind=kind,
        )
        refusal = ladder_step_refusal(
            moment.presentation_phase.value,
            moment.support_level.value,
            step.presentation_phase.value,
            step.support_level.value,
        )
        if refusal is not None:
            return Err(refusal)
        action_type = TEACHING_ACTION_BY_DELIVERY[step.delivery_kind]
        delivery = self._deliver_teaching_action(
            turn_id=cp0.turn_id,
            conversation_id=ConversationId(turn.conversation_id),
            turn_sequence=cp0.turn_sequence,
            message_sequence=cp0.message_sequence,
            moment=moment,
            action_type=GenerationActionType(action_type),
            slot=step.delivery_kind.lower(),
            delivery_kind=step.delivery_kind,
            prompt_view=self._directive_prompt_view(
                EphemeralTeachingDirective(
                    moment_id=moment.moment_id,
                    action_id=ActionId(
                        f"ga-{cp0.turn_id}-{step.delivery_kind.lower()}"
                    ),
                    focus_target_id=TargetId(str(moment.focus_target.target_id)),
                    hint=step.text if step.delivery_kind == "HINT" else None,
                    focus_target_type=str(moment.focus_target.target_type),
                    action_type=action_type,
                    presentation_phase=step.presentation_phase,
                    support_level=step.support_level,
                    attempt_index=moment.attempt_index,
                    teaching_text=step.text,
                    reveal_text=(
                        step.text if step.delivery_kind == "REVEAL" else None
                    ),
                    explanation_text=(
                        step.text if step.delivery_kind == "EXPLANATION" else None
                    ),
                )
            ),
        )
        if isinstance(delivery, Err):
            return delivery
        delivered = delivery.value
        if delivered.outcome != TurnOutcome.REPLIED_FULL.value:
            return self._abort_and_resume(
                cp0=cp0,
                turn=turn,
                cycle=cycle,
                moment=moment,
                reason=AbortReason.DELIVERY_FAILURE.value,
                view=view,
                attempt=attempt,
                evaluation=evaluation,
                opportunity_id=opportunity_id,
                evidence_commit_id=evidence_commit_id,
                load=load,
                limits=limits,
                gate_decision=gate_decision,
                gate_reason_codes=gate_reason_codes,
            )
        moved = teaching.transition_moment(
            moment.moment_id,
            MomentTransition(
                lifecycle_state=plan.moment_state,
                presentation_phase=step.presentation_phase,
                support_level=step.support_level,
            ),
            moment.state_version,
        )
        if isinstance(moved, Err):
            return moved
        live = moved.value
        return Ok(
            TeachingReplyTurnResult(
                turn_id=cp0.turn_id,
                conversation_id=ConversationId(turn.conversation_id),
                moment_id=live.moment_id,
                moment_state=live.lifecycle_state,
                attempt_id=None if attempt is None else attempt.attempt_id,
                evaluation_outcome=(
                    None if evaluation is None else evaluation.outcome.value
                ),
                evaluation_confidence=(
                    None if evaluation is None else evaluation.confidence
                ),
                opportunity_id=opportunity_id,
                evidence_commit_id=evidence_commit_id,
                delivery_kind=step.delivery_kind,
                action_type=action_type,
                action_id=delivered.action_id,
                gate_decision=gate_decision,
                gate_reason_codes=gate_reason_codes,
                limit_reason=plan.limit_reason,
                closure=None,
                next_cycle_id=cycle.decision_cycle_id,
                turn_status=delivered.turn_status,
                outcome=delivered.outcome,
                reply_text=delivered.text,
                ledger_event=delivered.ledger_event,
                ledger_failure=delivered.ledger_failure,
            )
        )

    def _abort_and_resume(
        self,
        *,
        cp0: Cp0Commit,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        moment: TeachingMomentRecord,
        reason: str,
        view: TeachingTargetView | None,
        attempt: AttemptRecord | None,
        evaluation,
        opportunity_id: str | None,
        evidence_commit_id: str | None,
        load: TeachingLoad,
        limits: TeachingLimits,
        gate_decision: str | None,
        gate_reason_codes: tuple[str, ...],
    ) -> Result[TeachingReplyTurnResult]:
        """Abort the moment with one §7 reason and resume the persona."""

        plan = NextAction(
            moment_state=MomentState.ABORTING,
            delivery_kind=None,
            closure=reason,
            completion_outcome=None,
            abort_reason=reason,
            terminalizing=True,
        )
        closed = self._terminalize_moment(moment, plan, None)
        if isinstance(closed, Err):
            return closed
        return self._resume_and_close(
            cp0=cp0,
            turn=turn,
            cycle=cycle,
            moment=closed.value,
            plan=plan,
            view=view,
            attempt=attempt,
            evaluation=evaluation,
            opportunity_id=opportunity_id,
            evidence_commit_id=evidence_commit_id,
            limits=limits,
            load=load,
            gate_decision=gate_decision,
            gate_reason_codes=gate_reason_codes,
        )

    def _terminalize_moment(
        self,
        moment: TeachingMomentRecord,
        plan: NextAction,
        teaching: TeachingController | None,
    ) -> Result[TeachingMomentRecord]:
        """COMPLETING / ABORTING → TEACHING_TERMINAL with the lock released.

        STATE_MACHINES §9 / DATA_MODEL §18: the terminal state and the
        TeachingLockLease release are one short transaction — a terminal
        moment still holding its lock is unreachable. ``teaching is None``
        keeps the abort path readable (the caller's controller is threaded
        through its own call frame)."""

        owner = self._teaching if teaching is None else teaching
        if owner is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="teaching controller is not injected",
                )
            )
        current = moment
        if current.lifecycle_state is MomentState.DECIDING_NEXT_ACTION:
            target = plan.moment_state
            stepped = owner.transition_moment(
                current.moment_id,
                MomentTransition(
                    lifecycle_state=target,
                    completion_outcome=plan.completion_outcome,
                    abort_reason=plan.abort_reason,
                ),
                current.state_version,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value
        if current.lifecycle_state is MomentState.TEACHING_TERMINAL:
            return Ok(current)
        if current.lifecycle_state not in (
            MomentState.COMPLETING,
            MomentState.ABORTING,
        ):
            return _conflict(
                f"moment {current.moment_id} is {current.lifecycle_state.value};"
                " it can only terminalize from COMPLETING / ABORTING"
            )
        return owner.terminalize_moment(
            current.moment_id,
            completion_outcome=current.completion_outcome,
            abort_reason=current.abort_reason,
        )

    def _resume_and_close(
        self,
        *,
        cp0: Cp0Commit,
        turn: TurnRecordData,
        cycle: DecisionCycleRecord,
        moment: TeachingMomentRecord,
        plan: NextAction,
        view: TeachingTargetView | None,
        attempt: AttemptRecord | None,
        evaluation,
        opportunity_id: str | None,
        evidence_commit_id: str | None,
        limits: TeachingLimits,
        load: TeachingLoad,
        gate_decision: str | None = None,
        gate_reason_codes: tuple[str, ...] = (),
        next_cycle_id: DecisionCycleId | None = None,
    ) -> Result[TeachingReplyTurnResult]:
        """RESUMING → PERSONA_RESUME delivered → CLOSED (SM §1).

        The resume action carries a narrow :class:`ResumeDirective` (never
        the moment record), and the moment closes whether the resume was
        delivered or failed — "交付/失败 → CLOSED" — because a closed
        episode is never reopened (RA §23: the resume may be retried or
        recovered by the next turn, never by reopening the moment).
        """

        teaching = self._teaching
        assert teaching is not None  # both callers injected it
        current = moment
        delivered: TeachingActionDelivery | None = None
        if current.lifecycle_state is MomentState.TEACHING_TERMINAL:
            stepped = teaching.transition_moment(
                current.moment_id,
                MomentTransition(lifecycle_state=MomentState.RESUMING),
                current.state_version,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value
        if current.lifecycle_state is MomentState.RESUMING:
            resume_view = self._resume_prompt_view(
                ResumeDirective(
                    moment_id=current.moment_id,
                    conversation_id=current.conversation_id,
                    focus_target_type=str(current.focus_target.target_type),
                    focus_target_id=str(current.focus_target.target_id),
                    closure=plan.closure or "",
                    completion_outcome=current.completion_outcome,
                    abort_reason=current.abort_reason,
                ),
                reveal_text=None if view is None else view.reveal_form,
            )
            delivery = self._deliver_teaching_action(
                turn_id=cp0.turn_id,
                conversation_id=ConversationId(turn.conversation_id),
                turn_sequence=cp0.turn_sequence,
                message_sequence=cp0.message_sequence,
                moment=current,
                action_type=GenerationActionType.PERSONA_RESUME,
                slot="resume",
                delivery_kind="RESUME",
                prompt_view=resume_view,
            )
            if isinstance(delivery, Err):
                return delivery
            delivered = delivery.value
            closed = teaching.transition_moment(
                current.moment_id,
                MomentTransition(
                    lifecycle_state=MomentState.CLOSED, closed_at=_now()
                ),
                current.state_version,
            )
            if isinstance(closed, Err):
                return closed
            current = closed.value

        if delivered is None:
            # Re-entry after the moment had already closed: the durable turn
            # is the authority for the status/outcome.
            fresh = self._commands.get_turn_record(cp0.turn_id)
            if isinstance(fresh, Err):
                return fresh
            turn_status = turn.status if fresh.value is None else fresh.value.status
            outcome: str | None = None
        else:
            turn_status = delivered.turn_status
            outcome = delivered.outcome

        # §20's one non-presentation word this leg can write (RA §20): the user
        # *skipped* — §7's USER_SKIP abort, which is the only abort reason §20
        # names. The write is keyed on the closed moment (its id makes a
        # re-entry a replay), it never changes the closure above, and the other
        # two user-leaving reasons (``USER_REJECTED_TARGET`` /
        # ``USER_TOPIC_SHIFT``) are registered rather than mapped — §20 carries
        # no word for them. The resume delivery itself carries none either: its
        # kind is one of §20's unmapped ones (``elc.runtime.exposure``).
        ledger_event, ledger_failure = (
            self._record_skip_exposure(current)
            if plan.abort_reason == AbortReason.USER_SKIP.value
            else (None, None)
        )

        return Ok(
            TeachingReplyTurnResult(
                turn_id=cp0.turn_id,
                conversation_id=ConversationId(turn.conversation_id),
                moment_id=current.moment_id,
                moment_state=current.lifecycle_state,
                attempt_id=None if attempt is None else attempt.attempt_id,
                evaluation_outcome=(
                    None if evaluation is None else evaluation.outcome.value
                ),
                evaluation_confidence=(
                    None if evaluation is None else evaluation.confidence
                ),
                opportunity_id=opportunity_id,
                evidence_commit_id=evidence_commit_id,
                delivery_kind=None if delivered is None else "RESUME",
                action_type=(
                    None
                    if delivered is None
                    else GenerationActionType.PERSONA_RESUME.value
                ),
                action_id=None if delivered is None else delivered.action_id,
                gate_decision=gate_decision,
                gate_reason_codes=gate_reason_codes,
                limit_reason=plan.limit_reason,
                closure=plan.closure,
                next_cycle_id=(
                    cycle.decision_cycle_id
                    if next_cycle_id is None
                    else next_cycle_id
                ),
                turn_status=turn_status,
                outcome=outcome,
                reply_text=None if delivered is None else delivered.text,
                ledger_event=ledger_event,
                ledger_failure=ledger_failure,
            )
        )

    def _continuation_gate(
        self,
        *,
        turn_id: TurnId,
        cycle: DecisionCycleRecord,
        moment: TeachingMomentRecord,
        plan: NextAction,
        view: TeachingTargetView | None,
        load: TeachingLoad,
        limits: TeachingLimits,
        teaching: TeachingController,
    ) -> Result[GateVerdict]:
        """Authorize (or refuse) one continuation, durably.

        BF-03 v1.1 continuation branch: ``USER_REQUESTED_CONTINUE`` with
        ``ACTIVE_MOMENT`` authorization. The verdict is persisted as the
        same two facts a Gate outcome always is (GateExecutionStatus +
        GateDecision for DENY/ALLOW, GateExecutionStatus alone for
        DEGRADED) so a re-entry reads the decision instead of re-running
        the Gate.

        Replay (review F1): the fact ids are deterministic per turn
        (``ges-/gd-{turn}-continuation``), so a same-turn re-entry must read
        the durable decision back rather than try to insert it again — a PK
        conflict there would turn a retry into a hard failure and the hint
        would never be delivered. The durable facts are therefore the
        authority: if the pair exists, the recorded verdict is returned and
        the Gate is not re-run.
        """

        replayed = self._replay_continuation_gate(turn_id, cycle, teaching)
        if replayed is not None:
            return replayed

        proposed = CONTINUATION_ACTION_BY_DELIVERY.get(
            plan.delivery_kind or "", "TERMINAL_FEEDBACK"
        )
        lock_state = "UNKNOWN"
        observed = teaching.observed_lock_state(
            moment.conversation_id, moment.moment_id
        )
        if isinstance(observed, Ok):
            lock_state = observed.value
        facts = continuation_facts_for(
            moment=moment,
            decision_cycle_id=str(cycle.decision_cycle_id),
            proposed_action=proposed,
            lock_state=lock_state,
            load=load,
            limits=limits,
            target_status="VALID" if view is not None else "UNKNOWN",
            content_status=(
                "VALID"
                if view is not None and view.content_status == "VALID"
                else ("UNKNOWN" if view is None else view.content_status)
            ),
            candidate_id=moment.candidate_id,
        )
        verdict = teaching.decide_user_requested_continuation(facts)
        status = GateExecutionStatusRecord(
            gate_execution_status_id=f"ges-{turn_id}-continuation",
            decision_cycle_id=cycle.decision_cycle_id,
            moment_id=moment.moment_id,
            gate_context=GateDecisionContext.USER_REQUESTED_CONTINUE,
            authorization_basis=AuthorizationBasis.ACTIVE_MOMENT,
            authorization_status="VALID",
            status=(
                GateExecutionStatusValue.SUCCEEDED
                if verdict.execution_status == "SUCCEEDED"
                else GateExecutionStatusValue.DEGRADED
            ),
            missing_or_unknown=verdict.missing_or_unknown,
        )
        if verdict.decision is None:
            degraded = teaching.record_gate_degraded(status)
            if isinstance(degraded, Err):
                return degraded
            return Ok(verdict)
        decision = GateDecisionRecord(
            gate_decision_id=GateDecisionId(f"gd-{turn_id}-continuation"),
            decision_cycle_id=cycle.decision_cycle_id,
            candidate_id=moment.candidate_id,
            context=GateDecisionContext.USER_REQUESTED_CONTINUE,
            decision=(
                GateDecisionValue.ALLOW
                if verdict.decision == "ALLOW"
                else GateDecisionValue.DENY
            ),
            reason_codes=verdict.reasons,
            policy_version=PolicyVersion(GATE_POLICY_VERSION),
        )
        recorded_decision = (
            teaching.record_gate_allow(status, decision)
            if verdict.decision == "ALLOW"
            else teaching.record_gate_denial(status, decision)
        )
        if isinstance(recorded_decision, Err):
            return recorded_decision
        return Ok(verdict)

    def _commit_attempt_evidence(
        self,
        *,
        cp0: Cp0Commit,
        moment: TeachingMomentRecord,
        attempt: AttemptRecord,
        evaluation,
        evaluation_id: str,
        view: TeachingTargetView | None,
        linkage: str | None,
        learning: LearningController,
    ) -> tuple[str | None, str | None]:
        """LOR → evidence proposal → Learning commit (DEC-…2babb21e.5 Q4).

        Returns ``(opportunity_id, evidence_commit_id)``; both are None when
        the Learning leg degrades (RA §21: a durable proposal pending never
        blocks the turn, and the durable attempt/evaluation rows stay the
        trace). Teaching never reads the Learning DB: the LOR link is
        verified by Learning's own validation face
        (``_opportunity_link_refusal``), which is the only side that may
        read the table.

        P4-0 ①: the durable §17 evaluation id travels with the facts
        (``evaluation_id``) so Learning's durable proposal can name its
        source evaluation — the proposal chain is
        Attempt → Evaluation → proposal PENDING → commit attempt, and the
        ref the evaluation carries (``tep-{attempt}``) resolves to that
        durable row even when the commit itself cannot run.

        ``linkage`` is the *verified* capability linkage (review F4): the
        caller resolves it through the target provider, so a claim can never
        be recorded against an undeclared capability id.
        """

        opportunity = learning.record_opportunity(
            source_turn_id=cp0.turn_id,
            target_type=str(moment.focus_target.target_type),
            target_id=TargetId(str(moment.focus_target.target_id)),
            opportunity_type=ATTEMPT_OPPORTUNITY_TYPE,
            target_explicitness=ATTEMPT_TARGET_EXPLICITNESS,
            attempt_observed=True,
            alternative_realizations_allowed=True,
            teaching_moment_id=str(moment.moment_id),
            learning_opportunity_id=LearningOpportunityId(
                opportunity_id_for(str(attempt.attempt_id))
            ),
        )
        if isinstance(opportunity, Err):
            return (None, None)
        opportunity_id = str(opportunity.value)
        proposal = build_evidence_proposal(
            moment=moment,
            attempt=attempt,
            evaluation=evaluation,
            target_view=view,
            opportunity_id=opportunity_id,
            capability_linkage=linkage,
        )
        if proposal is None:
            return (opportunity_id, None)
        committed = learning.commit_teaching_evidence(
            proposal,
            source_turn_id=cp0.turn_id,
            conversation_id=str(moment.conversation_id),
            source_evaluation_id=evaluation_id,
            persona_id=(
                None if moment.persona_id is None else str(moment.persona_id)
            ),
        )
        if isinstance(committed, Err):
            return (opportunity_id, None)
        return (opportunity_id, str(committed.value))

    def _advance_reply_path(
        self,
        moment: TeachingMomentRecord,
        target_index: int,
        teaching: TeachingController,
    ) -> Result[TeachingMomentRecord]:
        """Walk the §1 reply path to one position, idempotently.

        A crash re-entry finds the moment already further along; the walk
        simply continues from wherever it is. Each step is one CAS-guarded
        transition, so two writers can never both advance it.
        """

        try:
            index = TEACHING_REPLY_PATH.index(moment.lifecycle_state)
        except ValueError:
            return _conflict(
                f"moment {moment.moment_id} is {moment.lifecycle_state.value};"
                " the reply path starts at AWAITING_USER"
            )
        current = moment
        while index < target_index:
            index += 1
            stepped = teaching.transition_moment(
                current.moment_id,
                MomentTransition(lifecycle_state=TEACHING_REPLY_PATH[index]),
                current.state_version,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value
        return Ok(current)

    @staticmethod
    def _verified_capability_linkage(
        view: TeachingTargetView | None,
        targets: TeachingTargetProvider,
    ) -> str | None:
        """The capability linkage of a target, only if it is *resolvable*.

        Review F4: a target fixture declares the capability its resource
        realizes, and an alternative realization is credited to that
        capability — so the declaration must be checked against the provider
        before any claim is built. An id the provider cannot resolve (not in
        the validated set, or answering non-CAPABILITY) yields None: the
        attempt then produces no capability claim and the resource stays
        neutral instead of crediting a capability that does not exist.
        """

        if view is None or view.capability_linkage is None:
            return None
        resolved = targets.resolve("CAPABILITY", view.capability_linkage)
        if isinstance(resolved, Err):
            return None
        if resolved.value.target_type != "CAPABILITY":
            return None
        return view.capability_linkage

    @staticmethod
    def _refresh_moment(
        moment_id: MomentId, teaching: TeachingController
    ) -> Result[TeachingMomentRecord]:
        """Re-read one moment after a step that changed its row.

        ``record_attempt`` advances the moment's own counter and
        ``state_version`` in its transaction, so the caller's in-memory view
        is stale by exactly that step; a CAS built on the stale version would
        be refused (correctly — that is the §20 guard doing its job).
        """

        fresh = teaching.get_moment(moment_id)
        if isinstance(fresh, Err):
            return fresh
        if fresh.value is None:
            return _missing(f"moment not found: {moment_id}")
        return Ok(fresh.value)

    def _reply_cycle_bindings(
        self, learning: LearningController | None, moment: TeachingMomentRecord
    ) -> DecisionCycleBindings:
        """The reply turn's cycle bindings from the live Learning snapshot.

        A teaching reply commits evidence *and* decides the next action, so
        the cycle records the snapshot facts of that moment in time; a
        snapshot read that fails leaves the bindings None (the honest "no
        source" value) instead of blocking the turn.
        """

        if learning is None:
            return DecisionCycleBindings()
        snapshot = learning.get_learning_snapshot()
        if isinstance(snapshot, Err):
            return DecisionCycleBindings()
        return DecisionCycleBindings(
            learning_snapshot_id=str(snapshot.value.learning_snapshot_id),
            evidence_watermark=snapshot.value.evidence_watermark,
        )

    def _deliver_teaching_action(
        self,
        *,
        turn_id: TurnId,
        conversation_id: ConversationId,
        turn_sequence: TurnSequence,
        message_sequence: MessageSequence,
        moment: TeachingMomentRecord,
        action_type: GenerationActionType,
        slot: str,
        delivery_kind: str,
        prompt_view: TeachingPromptView,
    ) -> Result[TeachingActionDelivery]:
        """Dispatch one teaching action through the P1 pipeline and deliver it.

        The full §4 steps 11-13 path: PREPARED → ProviderAttempt →
        Validator → BUFFERED_VALIDATED (READY_TO_DELIVER) → Delivery →
        canonicalize → terminal. Nothing here bypasses the pipeline: the
        teaching text reaches the user exactly like any other generation
        output, and the provider only ever receives the finished phase /
        support ("provider 不自定阶段").

        The action ids are deterministic on (turn, slot), so a re-entry
        re-dispatches the same action instead of minting a second one
        (RA §23 "继续同 action_id").

        ``delivery_kind`` is §20's own vocabulary for what this delivery
        presented (the caller's kind word — ``OPENING`` / ``HINT`` / ``REVEAL``
        / ``RETRY`` / ``EXPLANATION`` / ``RESUME``, the same words
        ``TEACHING_ACTION_BY_DELIVERY`` keys on), and it is what the one
        exposure write maps to a §20 word: a real delivery appends its event
        (:meth:`_with_exposure`), a failed one presents nothing and appends
        nothing, and a kind §20 carries no word for records nothing by name.
        """

        persona_id = self._persona_id(conversation_id)
        contract = GenerationContract(
            generation_contract_id=TEACHING_CONTRACT_BY_ACTION[
                action_type.value
            ],
            action_type=action_type,
            persona_id=persona_id,
            allowed_disclosures=(),
            language_policy="default",
            style_constraints=(),
        )
        existing_result = self._generation.get_action_for_turn(turn_id)
        if isinstance(existing_result, Err):
            return existing_result
        existing = existing_result.value
        if (
            existing is not None
            and existing.status is GenerationActionStatus.TERMINAL
        ):
            # Re-entry after the delivery itself finished: the durable
            # transcript is the answer, and a terminal action is never
            # re-dispatched (R-INV-007; RA §23 "crash around CP3" — the
            # canonicalized assistant turn is the truth). The exposure write is
            # *attempted* here too (a real delivery happened). That attempt is
            # not a store-level no-op: the event's content carries the instant,
            # this path stamps a fresh one, and the store refuses a differing
            # content under an existing id — the refusal rides
            # ``ledger_failure`` (``CONFLICT``) and the log keeps its one row
            # either way (``elc.runtime.exposure``). This branch is not
            # reachable through the ordinary loop today: a same-epoch re-entry
            # from ``DELIVERING`` is refused before the leg runs, so a turn
            # whose action is already terminal never arrives here (the CP3
            # crash case in this cut's suite registers that).
            return self._exposed(
                self._replay_action_delivery(turn_id, existing.action_id),
                moment=moment,
                delivery_kind=delivery_kind,
            )
        intent = (
            existing
            if existing is not None and existing.action_id.endswith(slot)
            else GenerationActionIntentRecord(
                action_id=ActionId(f"ga-{turn_id}-{slot}"),
                turn_id=turn_id,
                decision_cycle_id=moment.decision_cycle_id,
                moment_id=moment.moment_id,
                assistant_turn_id=f"aturn-{turn_id}-{slot}",
                action_type=action_type,
                generation_contract_id=contract.generation_contract_id,
                status=GenerationActionStatus.PREPARED,
                attempt_count=0,
                created_at=None,
                owner_epoch=self._lease.epoch,
            )
        )

        turn_result = self._commands.get_turn_record(turn_id)
        if isinstance(turn_result, Err):
            return turn_result
        turn = turn_result.value
        if turn is None:
            return _missing(f"turn record not found: {turn_id}")
        state_version = turn.state_version
        if turn.status == TurnStatus.DECIDING:
            advanced = self._commands.transition_turn(
                turn_id, state_version, TurnStatus.GENERATING
            )
            if isinstance(advanced, Err):
                return advanced
            state_version = advanced.value.state_version

        context_result = self._queries.get_conversation_window(
            conversation_id, CONVERSATION_WINDOW_MAX_TURNS
        )
        window = (
            context_result.value if isinstance(context_result, Ok) else None
        )
        (
            relationship_view,
            episode_view,
            disclosed_profile,
        ) = self._persona_views_for(conversation_id, persona_id)
        context = GenerationContext(
            character_package=self._character_package,
            relationship_view=relationship_view,
            episode_view=episode_view,
            world_lore_view=None,
            disclosed_user_profile=disclosed_profile,
            conversation_window=window,
            language_policy="default",
            generation_policy="default",
            generation_contract=contract,
            ephemeral_teaching_directive=prompt_view,
        )
        request = PromptCompilationRequest(
            conversation_id=conversation_id,
            persona_id=persona_id,
            interaction_channel=InteractionChannel.TEXT,
            generation_context=context,
            generation_contract=contract,
        )
        run_result = self._persona.run_action(intent, request, contract)
        if isinstance(run_result, Err):
            return run_result
        generation = run_result.value
        if generation.buffered_reply is None:
            terminal = self._commands.terminalize_turn(
                turn_id, TurnOutcome.NO_ASSISTANT_OUTPUT
            )
            if isinstance(terminal, Err):
                return terminal
            return Ok(
                TeachingActionDelivery(
                    action_id=generation.action_id,
                    assistant_turn_id=None,
                    text=None,
                    outcome=TurnOutcome.NO_ASSISTANT_OUTPUT.value,
                    turn_status=terminal.value.status,
                    state_version=terminal.value.state_version,
                )
            )
        reply = generation.buffered_reply
        completion = self.finalize_delivery(
            AssistantDelivery(
                conversation_id=conversation_id,
                turn_id=turn_id,
                action_id=reply.action_id,
                assistant_turn_id=reply.assistant_turn_id,
                text=reply.text,
                turn_sequence=turn_sequence,
                message_sequence=message_sequence,
                delivery_state=DeliveryState.SENT_COMPLETE,
                outcome=TurnOutcome.REPLIED_FULL,
            ),
            state_version,
        )
        if isinstance(completion, Err):
            return completion
        return Ok(
            self._with_exposure(
                TeachingActionDelivery(
                    action_id=reply.action_id,
                    assistant_turn_id=reply.assistant_turn_id,
                    text=reply.text,
                    outcome=TurnOutcome.REPLIED_FULL.value,
                    turn_status=completion.value.turn_status,
                    state_version=completion.value.state_version,
                ),
                moment=moment,
                delivery_kind=delivery_kind,
            )
        )

    def _replay_action_delivery(
        self, turn_id: TurnId, action_id: ActionId
    ) -> Result[TeachingActionDelivery]:
        """Replay a delivery whose action already reached TERMINAL.

        Two durable shapes are possible and both are honest: the assistant
        turn was canonicalized (a complete reply) or it was not (the action
        failed undelivered). The turn is terminalized if it is not already —
        the teaching turn's outcome always follows the real delivery
        (STATE_MACHINES §10).
        """

        slice_result = self._queries.get_canonical_turn_slice(turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        assistant = slice_.assistant_turn if slice_ is not None else None
        outcome = (
            TurnOutcome.REPLIED_FULL.value
            if assistant is not None
            else TurnOutcome.NO_ASSISTANT_OUTPUT.value
        )
        turn_result = self._commands.get_turn_record(turn_id)
        if isinstance(turn_result, Err):
            return turn_result
        turn = turn_result.value
        if turn is None:
            return _missing(f"turn record not found: {turn_id}")
        if turn.status in TERMINAL_TURN_STATUSES:
            return Ok(
                TeachingActionDelivery(
                    action_id=action_id,
                    assistant_turn_id=(
                        assistant.assistant_turn_id
                        if assistant is not None
                        else None
                    ),
                    text=assistant.content if assistant is not None else None,
                    outcome=outcome,
                    turn_status=turn.status,
                    state_version=turn.state_version,
                )
            )
        terminal = self._commands.terminalize_turn(
            turn_id,
            (
                TurnOutcome.REPLIED_FULL
                if assistant is not None
                else TurnOutcome.NO_ASSISTANT_OUTPUT
            ),
        )
        if isinstance(terminal, Err):
            return terminal
        return Ok(
            TeachingActionDelivery(
                action_id=action_id,
                assistant_turn_id=(
                    assistant.assistant_turn_id if assistant is not None else None
                ),
                text=assistant.content if assistant is not None else None,
                outcome=outcome,
                turn_status=terminal.value.status,
                state_version=terminal.value.state_version,
            )
        )

    def _reconcile_delivering_reply(
        self,
        *,
        turn: TurnRecordData,
        teaching: TeachingController,
        targets: TeachingTargetProvider,
    ) -> Result[TeachingReplyTurnResult]:
        """Finish a reply turn whose delivery was in flight at the crash.

        RUNTIME §24.1 maps a CP3-uncertain turn to
        CONSERVATIVE_DELIVERY_RECONCILIATION, and RA §23 has the rule the
        opening path already follows: "crash around CP3 → the canonicalized
        assistant turn is the truth". Two durable shapes are possible, and
        each has exactly one honest move:

        - the assistant turn *was* canonicalized (the message really went
          out): the delivery leg is completed from the record — the action
          leaves DELIVERING, the turn terminalizes REPLIED_FULL, and the
          ladder is reconciled from the delivered action (STATE_MACHINES
          §3). Nothing is re-generated and nothing is re-sent;
        - no assistant turn exists (the message never reached the user):
          the action terminalizes undelivered, the turn terminalizes
          NO_ASSISTANT_OUTPUT, and the episode aborts with the §7
          DELIVERY_FAILURE word and releases its lock — the
          ``_abort_opening`` move for a delivery that just failed (no
          resume message: a second message would only fail too).

        Either way the turn stops being stuck at DELIVERING and the moment
        can never sit live-but-undecidable because a crash ate its reply.

        P3-3 review F7 (two corrections to that reconciliation):

        - the caller no longer adopts a foreign-epoch DELIVERING turn before
          this method runs, so the epoch-fence refusal below leaves the
          residue *visible* to the startup scan (``owner_epoch !=
          current``) instead of silently re-owning a turn this epoch may
          not finish. The adoption happens here, and only once the leg is
          actually finishable (:meth:`_adopt_turn_for_recovery`);
        - the caller reaches this method before requiring a live moment, so
          a DELIVERING turn whose moment already closed (the ordinary shape
          after a successful startup sweep) is reconciled from the record
          instead of being refused by the moment guard forever.
        """

        slice_result = self._queries.get_canonical_turn_slice(turn.turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        assistant = slice_.assistant_turn if slice_ is not None else None

        action_result = self._generation.get_action_for_turn(turn.turn_id)
        if isinstance(action_result, Err):
            return action_result
        action = action_result.value
        if (
            action is not None
            and action.status is not GenerationActionStatus.TERMINAL
        ):
            epoch = self._lease.epoch
            if epoch is not None and action.owner_epoch != epoch:
                # The fence is the honest answer: a new epoch may not
                # advance an old-epoch action. The epoch-based teaching-lock
                # sweep (recover_orphan_teaching) is the sanctioned route.
                return _conflict(
                    f"the delivery action of turn {turn.turn_id} belongs to"
                    f" runtime epoch {action.owner_epoch}; current epoch"
                    f" {epoch} must not advance it — use the orphan-lock"
                    " recovery sweep"
                )
            if assistant is not None:
                completed = self._persona.complete_delivery(action.action_id)
                if isinstance(completed, Err):
                    return completed
            else:
                failed = self._persona.terminalize_failure(
                    action.action_id, action.status
                )
                if isinstance(failed, Err):
                    return failed

        adopted = self._adopt_turn_for_recovery(turn)
        if isinstance(adopted, Err):
            return adopted
        terminal = self._commands.terminalize_turn(
            adopted.value.turn_id,
            (
                TurnOutcome.REPLIED_FULL
                if assistant is not None
                else TurnOutcome.NO_ASSISTANT_OUTPUT
            ),
        )
        if isinstance(terminal, Err):
            return terminal

        if assistant is None:
            # Nothing was delivered, so the ladder must not move and the
            # episode must not stay live: the abort runs first (the moment
            # is still in its deciding slot).
            aborted = self._abort_lost_delivery(turn, teaching)
            if isinstance(aborted, Err):
                return aborted
        else:
            reconciled = self._reconcile_moment_ladder(
                turn_id=turn.turn_id, teaching=teaching, targets=targets
            )
            if isinstance(reconciled, Err):
                return reconciled
        return self._replay_teaching_reply(terminal.value, teaching)

    def _adopt_turn_for_recovery(
        self, turn: TurnRecordData
    ) -> Result[TurnRecordData]:
        """Adopt one turn into the current epoch when it is foreign.

        RUNTIME §24 restart ownership + SM §17.1 rule 3: the recovery owner
        finishes old work. ``terminalize_turn`` is CAS-guarded and refuses a
        foreign epoch, so the adoption is the precondition of finishing the
        leg — deliberately *late* (review F7): only a leg this epoch may
        actually finish adopts its turn, because adopting a turn the epoch
        fence then refuses would take the residue out of the scan's view
        without giving anyone the right to close it.
        """

        epoch = self._lease.epoch
        if epoch is None or turn.owner_epoch == epoch:
            return Ok(turn)
        return self._commands.claim_turn_for_recovery(turn.turn_id)

    def _abort_lost_delivery(
        self, turn: TurnRecordData, teaching: TeachingController
    ) -> Result[TeachingMomentRecord | None]:
        """Abort the episode of a delivery that never reached the user.

        The §7 DELIVERY_FAILURE walk (ABORTING → TEACHING_TERMINAL, lock
        released in the same transaction → RESUMING → CLOSED), with no
        resume message — the ``_abort_opening`` posture: the delivery just
        failed, so a second message would only fail too. A moment that is
        already terminal/closed (or gone) is not touched.
        """

        active = teaching.get_active_moment(ConversationId(turn.conversation_id))
        if isinstance(active, Err):
            return active
        moment = active.value
        if moment is None or moment.lifecycle_state in (
            MomentState.TEACHING_TERMINAL,
            MomentState.CLOSED,
        ):
            return Ok(moment)
        plan = NextAction(
            moment_state=MomentState.ABORTING,
            delivery_kind=None,
            closure=AbortReason.DELIVERY_FAILURE.value,
            completion_outcome=None,
            abort_reason=AbortReason.DELIVERY_FAILURE.value,
            terminalizing=True,
        )
        closed = self._terminalize_moment(moment, plan, teaching)
        if isinstance(closed, Err):
            return closed
        current = closed.value
        for state in (MomentState.RESUMING, MomentState.CLOSED):
            stepped = teaching.transition_moment(
                current.moment_id,
                MomentTransition(
                    lifecycle_state=state,
                    closed_at=None if state is MomentState.RESUMING else _now(),
                ),
                current.state_version,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value
        return Ok(current)

    def _reconcile_moment_ladder(
        self,
        *,
        turn_id: TurnId,
        teaching: TeachingController,
        targets: TeachingTargetProvider,
    ) -> Result[TeachingMomentRecord | None]:
        """Land the ladder of a *delivered* teaching action on re-entry.

        Review F1, second half: the delivery and the ladder landing are two
        writes, and the delivery is the one that makes the turn terminal —
        so a crash in between can leave a message the user really saw with
        the moment still at the previous rung. That state is exactly what
        STATE_MACHINES §3 forbids (a later attempt would record *less*
        support than the material actually shown).

        The durable action says what was shown, so the rung is rebuilt from
        it — never from what the crashed call intended — and only ever moved
        forward (the ladder is one-way). Nothing is re-delivered: the
        message is already in the transcript.
        """

        action_result = self._generation.get_action_for_turn(turn_id)
        if isinstance(action_result, Err):
            return action_result
        action = action_result.value
        if (
            action is None
            or action.status is not GenerationActionStatus.TERMINAL
            or action.moment_id is None
        ):
            return Ok(None)
        moment_result = teaching.get_moment(MomentId(action.moment_id))
        if isinstance(moment_result, Err):
            return moment_result
        moment = moment_result.value
        if moment is None or moment.lifecycle_state not in (
            MomentState.AWAITING_USER,
            MomentState.EVALUATING,
            MomentState.DECIDING_NEXT_ACTION,
        ):
            return Ok(moment)
        slot = str(action.action_id).rsplit("-", 1)[-1]
        if slot not in ("hint", "retry", "reveal", "explanation"):
            return Ok(moment)
        target_phase = moment.presentation_phase
        target_support = moment.support_level
        if slot == "hint":
            # The rung is addressed absolutely: how many *hint* deliveries
            # really happened (a retry re-prompts at the same rung and is
            # counted separately), so the reconciliation is idempotent no
            # matter how often the re-entry runs.
            view: TeachingTargetView | None = None
            resolved = targets.resolve(
                str(moment.focus_target.target_type),
                str(moment.focus_target.target_id),
            )
            if isinstance(resolved, Ok):
                view = resolved.value
            rung_count = len(() if view is None else view.hint_ladder)
            shown = teaching.count_delivered_slot_actions(moment.moment_id, slot)
            if shown >= 1:
                if shown > rung_count or shown > len(HINT_PHASES):
                    target_phase = PresentationPhase.FULL_REVEAL
                    target_support = TeachingSupportLevel.FULL_FORM_SHOWN
                else:
                    target_phase, target_support = hint_rung(shown - 1)
        elif slot in ("reveal", "explanation"):
            step = ladder_step(
                current_phase=moment.presentation_phase.value,
                current_support=moment.support_level.value,
                hint_ladder=(),
                reveal_form=None,
                delivery_kind=slot.upper(),
            )
            target_phase, target_support = step.presentation_phase, step.support_level
        already_landed = (
            phase_rank(target_phase.value)
            < phase_rank(moment.presentation_phase.value)
            or support_rank(target_support.value)
            < support_rank(moment.support_level.value)
        )
        if already_landed or (
            target_phase is moment.presentation_phase
            and target_support is moment.support_level
            and moment.lifecycle_state is MomentState.AWAITING_USER
        ):
            return Ok(moment)
        stepped = teaching.transition_moment(
            moment.moment_id,
            MomentTransition(
                lifecycle_state=MomentState.AWAITING_USER,
                presentation_phase=target_phase,
                support_level=target_support,
            ),
            moment.state_version,
        )
        if isinstance(stepped, Err):
            return stepped
        return Ok(stepped.value)

    def _replay_teaching_reply(
        self, turn: TurnRecordData, teaching: TeachingController
    ) -> Result[TeachingReplyTurnResult]:
        """Replay the durable outcome of a terminal teaching reply turn."""

        slice_result = self._queries.get_canonical_turn_slice(turn.turn_id)
        if isinstance(slice_result, Err):
            return slice_result
        slice_ = slice_result.value
        assistant = slice_.assistant_turn if slice_ is not None else None
        outcome = slice_.outcome if slice_ is not None else None
        action_result = self._generation.get_action_for_turn(turn.turn_id)
        if isinstance(action_result, Err):
            return action_result
        action = action_result.value
        moment_id = action.moment_id if action is not None else None
        moment: TeachingMomentRecord | None = None
        if moment_id is not None:
            moment_result = teaching.get_moment(MomentId(moment_id))
            if isinstance(moment_result, Err):
                return moment_result
            moment = moment_result.value
        if moment is None:
            active = teaching.get_active_moment(
                ConversationId(turn.conversation_id)
            )
            if isinstance(active, Err):
                return active
            moment = active.value
        return Ok(
            TeachingReplyTurnResult(
                turn_id=turn.turn_id,
                conversation_id=ConversationId(turn.conversation_id),
                moment_id=moment.moment_id if moment is not None else MomentId(""),
                moment_state=(
                    moment.lifecycle_state
                    if moment is not None
                    else MomentState.CLOSED
                ),
                attempt_id=None,
                evaluation_outcome=None,
                evaluation_confidence=None,
                opportunity_id=None,
                evidence_commit_id=None,
                delivery_kind=None,
                action_type=(
                    None if action is None else action.action_type.value
                ),
                action_id=action.action_id if action is not None else None,
                gate_decision=None,
                gate_reason_codes=(),
                limit_reason=None,
                closure=(
                    None
                    if moment is None
                    else (moment.completion_outcome or moment.abort_reason)
                ),
                next_cycle_id=(
                    None
                    if moment is None
                    else moment.decision_cycle_id
                ),
                turn_status=turn.status,
                outcome=outcome.value if outcome is not None else None,
                reply_text=assistant.content if assistant is not None else None,
            )
        )

    def _teaching_reply_input_id(self, request: TeachingReplyRequest) -> InputId:
        """The reply turn's stable opaque input id (the command-turn rule).

        With a ``client_message_id`` the id derives from it, so a repeat
        call dedupes to the original turn; without one every call mints a
        fresh id (a genuinely new reply is never swallowed as a replay of
        an older one — review F1's semantics).
        """

        if request.input_id is not None:
            return request.input_id
        if request.client_message_id is not None:
            return InputId(f"in-{request.client_message_id}")
        return InputId(f"in-teaching-reply-{uuid.uuid4().hex}")

    def _teaching_ports(
        self,
    ) -> Result[
        tuple[
            DecisionCycleStore,
            LearningController,
            TeachingController,
            TeachingTargetProvider,
        ]
    ]:
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
                        "the teaching turn needs the P3-1B assembly"
                        " (decision_cycles + learning_controller + teaching"
                        " + targets injected)"
                    ),
                )
            )
        return Ok((decision_cycles, learning, teaching, targets))

    @staticmethod
    def _directive_prompt_view(
        directive: EphemeralTeachingDirective,
    ) -> TeachingPromptView:
        """Project a Teaching directive onto the persona-owned prompt view.

        The projection lives here because ``persona`` must not import
        ``teaching`` (the AST pin) and ``teaching`` must not import
        ``persona``: the orchestrator is the one place that knows both."""
        return TeachingPromptView(
            action_type=directive.action_type,
            presentation_phase=directive.presentation_phase.value,
            support_level=directive.support_level.value,
            moment_id=str(directive.moment_id),
            focus_target_type=directive.focus_target_type,
            focus_target_id=str(directive.focus_target_id),
            attempt_index=directive.attempt_index,
            hint=directive.hint,
            reveal=directive.reveal_text,
            explanation=directive.explanation_text,
        )

    @staticmethod
    def _resume_prompt_view(
        directive: ResumeDirective, *, reveal_text: str | None = None
    ) -> TeachingPromptView:
        """Project the narrow resume directive (never the moment record).

        A closing reveal travels as the resume section's ``reveal`` text:
        the episode's last message shows the form and returns the
        conversation to normal, and the moment record itself (attempts,
        ladder internals, snapshots) never reaches the prompt."""
        fields = dict(directive.as_view_fields())
        return TeachingPromptView(
            action_type=GenerationActionType.PERSONA_RESUME.value,
            moment_id=fields["moment_id"],
            focus_target_type=fields["focus_target_type"],
            focus_target_id=fields["focus_target_id"],
            closure=fields["closure"],
            completion_outcome=fields["completion_outcome"],
            abort_reason=fields["abort_reason"],
            reveal=reveal_text,
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
        outcome: str | None = None,
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
            outcome=outcome,
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
        # P5-2: the target observation, when one exists, is part of what the
        # proposal says about this turn — one observable behavior, one
        # group (DATA_MODEL §6). P5-R makes the gate two-layered: the
        # matcher's answer becomes a TargetMatchObservation first, and only
        # an *admitted* observation may become evidence. Everything else is
        # observation-only — zero claim, zero LearnerState change, the turn
        # untouched (elc.learning.target_match, the V1 admission set: a
        # whole-sentence form-class RESOURCE match, no open teaching window
        # for that target, a readable supply; a miss or a broken supply is
        # still a dropped observation, never a blocked conversation).
        resolution = self._resolve_silent_target(slice_)
        if resolution is not None:
            observation = observe_target_match(
                turn_id=str(slice_.turn_id),
                utterance=slice_.user_turn.raw_content,
                resolution=resolution,
            )
            if not admitted_for_evidence(
                observation, slice_.user_turn.raw_content
            ) or self._observed_target_is_under_teaching(
                conversation_id, observation
            ):
                resolution = None
        artifact = self._record_learning_analysis(learning, slice_, resolution)
        if isinstance(artifact, Err):
            return  # pending: nothing durable yet, turn continues
        persona_id = self._persona_id(conversation_id)
        # Ok → CP1 durable (the normal RA §4 path). Err → one of the two
        # RA §21 degraded outcomes above; the durable artifact state
        # (REJECTED vs PRODUCED) is Learning's audit trail, not a branch
        # for the coordinator.
        committed = learning.commit_learning_evidence(
            artifact.value, slice_, str(persona_id)
        )
        if resolution is not None and isinstance(committed, Ok):
            # P5-2: the observation is durable — materialize its §11
            # projection (best-effort; see _rebuild_silent_target).
            self._rebuild_silent_target(resolution)

    def _resolve_silent_target(
        self, turn: CanonicalTurnSlice
    ) -> ResolvedTarget | None:
        """P5-2: one best-effort target observation of a chat turn.

        The port's whole contract is "an answer or None" (RA §21: a broken
        supply degrades to NO_TARGET, never to a blocked conversation), and
        an exception out of a broken implementation is caught here and means
        the same thing — the ``_persona_views_for`` precedent.
        """

        if self._silent_evidence is None:
            return None
        try:
            return self._silent_evidence.resolve_turn(turn)
        except Exception:
            return None

    def _observed_target_is_under_teaching(
        self,
        conversation_id: ConversationId,
        observation: TargetMatchObservation,
    ) -> bool:
        """P5-2 (F-2), P5-R rule 4: is this target inside an open teaching
        window?

        docs/DOMAIN_MODEL.md §6 (the sentences next to the negative-evidence
        rule): a full answer exposure cannot produce *independent* evidence
        for the current Moment's target. So while the conversation's durable
        teaching lock points at a moment about this same target, a free-chat
        occurrence of its form must not be labelled SPONTANEOUS / no-support
        — the observation is skipped (a missing claim is recoverable, a
        mislabelled independent claim is not). The rule is target-scoped: an
        open moment about another target leaves this target's observation
        alone.

        Fail-closed on a teaching port that refuses or raises ("cannot prove
        the window is free" ⇒ skip). A *missing* port means the assembly
        cannot open a moment at all (``request_teaching`` requires it), so
        the window is provably free and the observation proceeds.
        """

        teaching = self._teaching
        if teaching is None:
            return False
        try:
            active = teaching.get_active_moment(conversation_id)
        except Exception:
            return True
        if isinstance(active, Err):
            return True
        moment = active.value
        if moment is None:
            return False
        focus = moment.focus_target
        return (
            str(focus.target_type) == observation.target_type
            and str(focus.target_id) == observation.target_id
        )

    @staticmethod
    def _record_learning_analysis(
        learning: LearningTurnAnalysis,
        turn: CanonicalTurnSlice,
        resolution: ResolvedTarget | None,
    ) -> Result[LearningEvidenceProposal]:
        """RA §4 step 3 through the Phase 2 port shape.

        The Phase 2 call is exactly ``record_learning_analysis(turn)``; the
        P5-2 observation is a keyword extension reached only when a resolver
        actually answered, so every pre-P5-2 assembly — and its
        fault-injection double — keeps its call shape unchanged.
        """

        if resolution is None:
            return learning.record_learning_analysis(turn)
        return learning.record_learning_analysis(turn, resolution=resolution)

    def _rebuild_silent_target(self, resolution: ResolvedTarget) -> None:
        """P5-2: materialize the observed target's §11 projection.

        Best-effort (RA §21): without a learning-controller port there is
        nobody to ask; a refusal or an exception leaves the claim durable and
        the projection lagging — the staleness repair
        (LearningController.stale_projection_targets) rebuilds it on the next
        snapshot read, and the claim is never rolled back for a projection
        miss. The rebuild key is the observation's modality (V1 typed chat
        observes TEXT_PRODUCTION only, DATA_MODEL §24.14).
        """

        controller = self._learning_controller
        if controller is None:
            return
        try:
            controller.rebuild_learner_state(
                TargetId(resolution.target_id),
                EvidenceModality(SILENT_EVIDENCE_MODALITY),
            )
        except Exception:
            return

    def _replay_terminal(self, turn: TurnRecordData) -> Result[TurnCompletion]:
        """Answer a duplicate input from the durable transcript.

        Read-only: the canonical assistant turn and the turn's own status are
        the answer, and nothing is written. The returned completion's two
        ledger fields are therefore ``None``, and that is *this call's* fact —
        "no exposure event was written here", **not** "no exposure happened":
        a teaching delivery recorded its own §20 event when it ran (the event
        is derivable from the action and lives in the log), and whether one
        exists is a read of ``planning_ledger_event``, never the absence of a
        field on a replayed result.
        """

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

#: The value channel of one persona-view read (P4-3): the three §11 views
#: have three different types, so the best-effort helper is generic over
#: whichever one it is handed.
_ViewT = TypeVar("_ViewT")


def _missing(message: str) -> Err[_E]:
    return Err(DomainError(code=DomainErrorCode.NOT_FOUND, message=message))


def _conflict(message: str) -> Err[_E]:
    return Err(DomainError(code=DomainErrorCode.CONFLICT, message=message))
