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
    """Action-level retry, never whole-turn retry (R-INV-007)."""

    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    ACCEPTED = "ACCEPTED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ProjectionJobState(StrEnum):
    """CP4 work; pending/failure never blocks the next user-visible turn."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


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
    """docs/DATA_MODEL.md §4 TurnRecord (schema view)."""

    turn_id: TurnId
    conversation_id: str
    turn_sequence: TurnSequence
    input_id: InputId
    status: TurnStatus
    active_decision_cycle_id: DecisionCycleId | None
    failure_class: str | None
    runtime_version: RuntimeVersion
    owner_epoch: RuntimeEpoch


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
class ProviderAttemptRecord:
    """docs/DATA_MODEL.md §20 — many attempts, one canonical accepted result."""

    provider_attempt_id: ProviderAttemptId
    action_id: ActionId
    attempt_no: int
    request_hash: str
    status: str


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
