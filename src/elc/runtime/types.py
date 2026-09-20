"""Runtime / Platform domain — Conversation Orchestrator coordination records.

Owns (docs/DOMAIN_MODEL.md §16): TurnRecord, DecisionCycle,
AnalysisArtifact, GenerationActionIntent, ProviderAttempt,
ServerDeliveryRecord, ClientRenderAck, ExposureEstimate,
ConversationCoordinatorLease (logical), runtime_epoch metadata,
ProjectionJob.

The Orchestrator owns sequencing, not truth (§16): it may assign turns,
resolve runtime state, call domain commands, handle retry/recovery and emit
traces — but never directly updates Domain-owned canonical state
(D-INV-001). Architecturally enforced by tests/architecture (Gate item 2):
this package must not touch sqlite3 / SQL at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    ActionId,
    ClientMessageId,
    DecisionCycleId,
    InputId,
    InteractionChannel,
    ProjectionJobId,
    ProviderAttemptId,
    RuntimeEpoch,
    RuntimeVersion,
    TurnId,
    TurnSequence,
)


class TurnStatus(StrEnum):
    """TurnRecord coordination states, word for word, from
    docs/STATE_MACHINES.md §10 lines 278-291 (协调状态). Vocabulary only:
    transition semantics belong to the Runtime Orchestrator (later phases)."""

    RECEIVED = "RECEIVED"
    USER_COMMITTED = "USER_COMMITTED"
    ANALYZING = "ANALYZING"
    DECIDING = "DECIDING"
    GENERATING = "GENERATING"
    DELIVERING = "DELIVERING"
    DELIVERY_TERMINAL = "DELIVERY_TERMINAL"
    POSTPROCESSING = "POSTPROCESSING"
    COMPLETED = "COMPLETED"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    FAILED_RECOVERABLE = "FAILED_RECOVERABLE"
    FAILED_FINAL = "FAILED_FINAL"


class GenerationActionStatus(StrEnum):
    """GenerationActionIntent states, word for word, from
    docs/STATE_MACHINES.md §14 lines 465-472.

    Corrects the Phase 0 six-value placeholder (PENDING/IN_FLIGHT/ACCEPTED/
    SUPERSEDED/CANCELLED/FAILED — adjudicated as a legacy deviation in
    DEC-OPI-091f35c3.7): §14 pins exactly the seven values below. An action
    may have multiple ProviderAttempts but at most one canonical accepted
    result; a late result for a cancelled/superseded action must never
    produce a canonical side effect (§14; action-level retry, never
    whole-turn retry — R-INV-007)."""

    PREPARED = "PREPARED"
    REQUESTED = "REQUESTED"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    READY_TO_DELIVER = "READY_TO_DELIVER"
    DELIVERING = "DELIVERING"
    TERMINAL = "TERMINAL"


class ProjectionJobState(StrEnum):
    """ProjectionJob states, word for word, from docs/DATA_MODEL.md §22.1
    (correcting the Phase 0 three-value placeholder PENDING/COMPLETED/
    FAILED); identical to the projection_job status CHECK constraint in
    migrations/0002_conversation_core.sql. CP4 work; pending/failure never
    blocks the next user-visible turn."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMMITTED = "COMMITTED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    REJECTED = "REJECTED"


class GenerationActionType(StrEnum):
    """docs/DATA_MODEL.md §20 action types."""

    NORMAL_PERSONA_REPLY = "NORMAL_PERSONA_REPLY"
    TEACHING_OPEN = "TEACHING_OPEN"
    TEACHING_HINT = "TEACHING_HINT"
    TEACHING_REVEAL = "TEACHING_REVEAL"
    TEACHING_EXPLANATION = "TEACHING_EXPLANATION"
    PERSONA_RESUME = "PERSONA_RESUME"


@dataclass(frozen=True)
class InputEnvelope:
    """docs/DATA_MODEL.md §4 — durable outside the coordinator guard."""

    input_id: InputId
    client_message_id: ClientMessageId | None
    conversation_id: str
    persona_id: str | None
    scene_id: str | None
    interaction_channel: InteractionChannel
    raw_payload: str
    received_at: str


@dataclass(frozen=True)
class InterruptRequest:
    """Barge-in request; durable while the old coordinator still holds the
    guard (docs/RUNTIME_ARCHITECTURE.md §24)."""

    input_id: InputId
    conversation_id: str
    active_turn_id: TurnId | None
    active_action_id: ActionId | None
    reason: str


@dataclass(frozen=True)
class TurnRecordData:
    """docs/DATA_MODEL.md §4 TurnRecord (schema view).

    ``state_version`` is the compare-and-swap counter every multi-event
    state transition must advance through (docs/STATE_MACHINES.md §20:
    "state_version + compare-and-swap").
    """

    turn_id: TurnId
    conversation_id: str
    turn_sequence: TurnSequence
    input_id: InputId
    status: TurnStatus
    active_decision_cycle_id: DecisionCycleId | None
    failure_class: str | None
    runtime_version: RuntimeVersion
    owner_epoch: RuntimeEpoch
    state_version: int


#: Terminal coordination states (docs/STATE_MACHINES.md §10): once a
#: TurnRecord reaches one of these, no further coordination transition is
#: legal; recovery scanning skips them (docs/RUNTIME_ARCHITECTURE.md §22
#: "Recovery 扫描非 terminal").
TERMINAL_TURN_STATUSES: frozenset[TurnStatus] = frozenset(
    {
        TurnStatus.COMPLETED,
        TurnStatus.CANCELLED_BY_USER,
        TurnStatus.FAILED_FINAL,
    }
)


@dataclass(frozen=True)
class DecisionCycleRecord:
    """docs/DATA_MODEL.md §4 — snapshot/version fields fixed inside the cycle
    (R-INV-003); occupies no message sequence."""

    decision_cycle_id: DecisionCycleId
    turn_id: TurnId
    cycle_index: int
    learning_snapshot_id: str | None
    evidence_watermark: str | None
    curriculum_version: str | None
    goal_version: str | None
    schedule_version: str | None
    policy_version: str | None
    context_view_version: str | None


@dataclass(frozen=True)
class GenerationActionIntentRecord:
    """docs/DATA_MODEL.md §20 GenerationActionIntent (column set verbatim;
    decision_cycle_id stays nullable until the decision phases — Phase 2
    tightens it, same transition window as turn_record's adjudication in
    DEC-OPI-091f35c3.7)."""

    action_id: ActionId
    turn_id: TurnId
    decision_cycle_id: DecisionCycleId | None
    moment_id: str | None
    assistant_turn_id: str
    action_type: GenerationActionType
    generation_contract_id: str
    status: GenerationActionStatus
    attempt_count: int
    created_at: str | None = None
    owner_epoch: RuntimeEpoch | None = None


@dataclass(frozen=True)
class ProviderAttemptRecord:
    """docs/DATA_MODEL.md §20 — many attempts, one canonical accepted result."""

    provider_attempt_id: ProviderAttemptId
    action_id: ActionId
    attempt_no: int
    request_hash: str
    status: str
    provider_request_id: str | None = None
    result_hash: str | None = None
    created_at: str | None = None
    terminal_at: str | None = None


@dataclass(frozen=True)
class ProjectionJobRecord:
    """docs/DOMAIN_MODEL.md §16 ProjectionJob (registry schema)."""

    projection_job_id: ProjectionJobId
    conversation_id: str
    source_turn_id: TurnId
    projection_type: str
    source_version: str
    state: ProjectionJobState


@dataclass(frozen=True)
class ValidatorResultRecord:
    """Registry schema (docs/DOMAIN_MODEL.md §18): validators are
    proposal-only; results ride the runtime trace and own no domain writes
    (R-INV-013)."""

    validator_result_id: str
    turn_id: TurnId
    validator_version: str
    proposal_status: str  # VALIDATE | COMMIT | REJECT | ABSTAIN (controller call)
    checked_refs: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryAction:
    """Startup/opportunistic recovery plan item (docs/RUNTIME_ARCHITECTURE.md
    §24.1: CP0→RESUME_ANALYSIS, CP1→RESUME_DECISION,
    CP2→RESUME_ACTION_BY_STABLE_ACTION_ID, CP3 uncertain→
    CONSERVATIVE_DELIVERY_RECONCILIATION)."""

    kind: str  # TURN | PROJECTION | LOCK | TEACHING
    id: str
    action: str


@dataclass(frozen=True)
class TurnCompletion:
    """Terminal result of one full turn through the minimum pipeline
    (IMPLEMENTATION_PLAN §3: UserTurn durable → Persona Runtime →
    Validator → Delivery → AssistantTurn)."""

    turn_id: TurnId
    action_id: ActionId
    assistant_turn_id: str | None
    turn_status: TurnStatus
    action_status: GenerationActionStatus
    outcome: str | None  # TurnOutcome value (str to avoid a cycle here)
    reply_text: str | None
    failure_reason: str | None
    state_version: int
