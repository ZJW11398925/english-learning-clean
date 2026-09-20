"""Canonical base types for every domain (docs/IMPLEMENTATION_PLAN.md §17-01).

Single source of truth for:
- stable opaque IDs (docs/DATA_MODEL.md §1.2 — never mutable text as key),
- version fields (docs/DATA_MODEL.md §1.4 / §26.1),
- Result/Error envelope,
- the three type-separated modality vocabularies
  (docs/DATA_MODEL.md §24.14: GoalModality vs EvidenceModality vs InteractionChannel),
- PlannerDecision(NO_TARGET) vs PlannerExecutionStatus(DEGRADED/FAILED/UNAVAILABLE),
  which must remain two non-interchangeable types
  (docs/DOMAIN_MODEL.md §10, docs/DATA_MODEL.md §14).

Every ID / version type is defined exactly once, here. Domains re-export the
names they own; they never redefine them (enforced by tests/architecture).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Mapping, NewType, TypeVar, Union

# ---------------------------------------------------------------------------
# Stable opaque IDs (docs/DATA_MODEL.md §1.2)
# ---------------------------------------------------------------------------

ConversationId = NewType("ConversationId", str)
PersonaId = NewType("PersonaId", str)
UserId = NewType("UserId", str)
SceneId = NewType("SceneId", str)
CharacterPackageId = NewType("CharacterPackageId", str)

InputId = NewType("InputId", str)
ClientMessageId = NewType("ClientMessageId", str)
TurnId = NewType("TurnId", str)
UserTurnId = NewType("UserTurnId", str)
AssistantTurnId = NewType("AssistantTurnId", str)
ActionId = NewType("ActionId", str)
DeliveryId = NewType("DeliveryId", str)
ClientAckId = NewType("ClientAckId", str)

DecisionCycleId = NewType("DecisionCycleId", str)
AnalysisId = NewType("AnalysisId", str)
PlannerEvaluationId = NewType("PlannerEvaluationId", str)
PlannerDecisionId = NewType("PlannerDecisionId", str)
GateDecisionId = NewType("GateDecisionId", str)
ProviderAttemptId = NewType("ProviderAttemptId", str)

MomentId = NewType("MomentId", str)
AttemptId = NewType("AttemptId", str)
AttemptEvaluationId = NewType("AttemptEvaluationId", str)

TargetId = NewType("TargetId", str)
ResourceId = NewType("ResourceId", str)
CapabilityId = NewType("CapabilityId", str)
ContentId = NewType("ContentId", str)
CurriculumNodeId = NewType("CurriculumNodeId", str)
GoalId = NewType("GoalId", str)

EvidenceGroupId = NewType("EvidenceGroupId", str)
EvidenceClaimId = NewType("EvidenceClaimId", str)
EvidenceCommitId = NewType("EvidenceCommitId", str)
LearningOpportunityId = NewType("LearningOpportunityId", str)
LearningSnapshotId = NewType("LearningSnapshotId", str)

RelationshipMemoryId = NewType("RelationshipMemoryId", str)
EpisodeId = NewType("EpisodeId", str)
ProjectionJobId = NewType("ProjectionJobId", str)
SecretRef = NewType("SecretRef", str)
WorldLoreFactId = NewType("WorldLoreFactId", str)

# Sequence counters are canonical conversation-owned state
# (docs/DATA_MODEL.md §3 "Sequence Semantics"). Distinct types: cross
# assignment between turn_sequence and message_sequence is a type error.
TurnSequence = NewType("TurnSequence", int)
MessageSequence = NewType("MessageSequence", int)

# runtime_epoch restart ownership boundary (docs/RUNTIME_ARCHITECTURE.md §24).
RuntimeEpoch = NewType("RuntimeEpoch", int)


# ---------------------------------------------------------------------------
# Version fields (docs/DATA_MODEL.md §1.4, §26.1)
# ---------------------------------------------------------------------------

EstimatorVersion = NewType("EstimatorVersion", str)
PlannerVersion = NewType("PlannerVersion", str)
PolicyVersion = NewType("PolicyVersion", str)
EvaluatorVersion = NewType("EvaluatorVersion", str)
ValidatorVersion = NewType("ValidatorVersion", str)
ContentVersion = NewType("ContentVersion", str)
CurriculumVersion = NewType("CurriculumVersion", str)
GoalVersion = NewType("GoalVersion", str)
ScheduleVersion = NewType("ScheduleVersion", str)
StateVersion = NewType("StateVersion", str)
SchemaVersion = NewType("SchemaVersion", str)
RuntimeSchemaVersion = NewType("RuntimeSchemaVersion", str)
RuntimeVersion = NewType("RuntimeVersion", str)

VERSION_FIELDS: Mapping[str, type] = {
    "estimator_version": EstimatorVersion,
    "planner_version": PlannerVersion,
    "policy_version": PolicyVersion,
    "evaluator_version": EvaluatorVersion,
    "validator_version": ValidatorVersion,
    "content_version": ContentVersion,
    "curriculum_version": CurriculumVersion,
    "goal_version": GoalVersion,
    "schedule_version": ScheduleVersion,
    "state_version": StateVersion,
    "schema_version": SchemaVersion,
    "runtime_schema_version": RuntimeSchemaVersion,
    "runtime_version": RuntimeVersion,
}


# ---------------------------------------------------------------------------
# Result / Error envelope
# ---------------------------------------------------------------------------

T = TypeVar("T")
#: Covariant phantom parameter for Err: the error envelope never carries
#: its result type at runtime, so an ``Err[X]`` may flow wherever an
#: ``Err[Y]`` is expected (errors propagate across result types — the
#: orchestrator forwards a domain Err unchanged to its own callers).
TErr = TypeVar("TErr", covariant=True)


class DomainErrorCode(StrEnum):
    """Coarse canonical failure vocabulary for domain command/query results."""

    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_FOUND = "NOT_FOUND"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    AUTHORITY_VIOLATION = "AUTHORITY_VIOLATION"
    CONFLICT = "CONFLICT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


@dataclass(frozen=True)
class DomainError:
    code: DomainErrorCode
    message: str
    details: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err(Generic[TErr]):
    """Error envelope; ``TErr`` is a phantom covariance marker only."""

    error: DomainError


#: Result: the value channel is parameterized (Ok[T]); the error channel is
#: deliberately untyped (Err[Any]) — a failure carries no result payload,
#: so any Err flows wherever a Result is expected.
Result = Union[Ok[T], Err[Any]]


# ---------------------------------------------------------------------------
# Modality vocabularies — three type-separated enums
# (docs/DATA_MODEL.md §24.14; docs/PRODUCT_CONTRACT.md GoalModality /
# InteractionChannel split). A goal modality is not an evidence modality is
# not an interaction channel; they are never assignable to each other.
# ---------------------------------------------------------------------------


class GoalModality(StrEnum):
    """Long-term goal modality (docs/DATA_MODEL.md §24.14)."""

    SPEAKING = "SPEAKING"
    LISTENING = "LISTENING"
    READING = "READING"
    WRITING = "WRITING"


class EvidenceModality(StrEnum):
    """V1 evidence modality. Future: VOICE_PRODUCTION | AUDIO_COMPREHENSION.

    Frozen V1 members only (docs/DATA_MODEL.md §24.14): `fluency?` in TEXT
    modality must not be read as speaking fluency; pronunciation/speaking
    fluency can only be written by a future VOICE_PRODUCTION evaluator.
    """

    TEXT_PRODUCTION = "TEXT_PRODUCTION"
    TEXT_COMPREHENSION = "TEXT_COMPREHENSION"


class InteractionChannel(StrEnum):
    """V1 interaction channel: typed chat only (docs/DATA_MODEL.md §24.14)."""

    TEXT = "TEXT"


# ---------------------------------------------------------------------------
# Planner decision vs execution status — two non-interchangeable types
# (docs/DOMAIN_MODEL.md §10: "`Planner failure/unavailable` 不伪装成
# PlannerDecision；它由 Runtime 的 PlannerExecutionStatus 表达。"
# docs/DATA_MODEL.md §14: "Runtime degradation is not a PlannerDecision.")
# ---------------------------------------------------------------------------


class PlannerDecisionOutcome(StrEnum):
    """The only two legitimate planner decision values."""

    SELECT = "SELECT"
    NO_TARGET = "NO_TARGET"


class PlannerExecutionStatusValue(StrEnum):
    """Execution health of a planner run. Never a decision.

    DEGRADED/FAILED/UNAVAILABLE must not be laundered into a synthetic
    PlannerDecision(NO_TARGET) (docs/DOMAIN_MODEL.md §10.1 last paragraph).
    """

    SUCCEEDED = "SUCCEEDED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class PlannerDecision:
    """docs/DATA_MODEL.md §14 PlannerDecision."""

    planner_decision_id: PlannerDecisionId
    decision_cycle_id: DecisionCycleId
    decision: PlannerDecisionOutcome
    planner_evaluation_id: PlannerEvaluationId
    selected_candidate_id: TargetId | None = None
    no_target_reason: str | None = None


@dataclass(frozen=True)
class PlannerExecutionStatusRecord:
    """docs/DATA_MODEL.md §14 PlannerExecutionStatus.

    Named `...Record` to keep the enum value type and the durable record
    type visibly distinct.
    """

    decision_cycle_id: DecisionCycleId
    status: PlannerExecutionStatusValue
    error_code: str | None = None


class RuntimeDecisionOutcomeValue(StrEnum):
    """Turn-level outcome (docs/DATA_MODEL.md §14 RuntimeDecisionOutcome)."""

    NORMAL = "NORMAL"
    DEGRADED_NO_AUTOMATIC_TEACHING = "DEGRADED_NO_AUTOMATIC_TEACHING"
