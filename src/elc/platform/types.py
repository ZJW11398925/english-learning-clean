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


@dataclass(frozen=True)
class PlannerEvaluationRecord:
    """docs/DATA_MODEL.md §14 PlannerEvaluation — the **durable row's** shape.

    Phase 8 P8-0. The id-shaped counterpart of
    :class:`elc.planner.types.PlannerEvaluation`, which is what the kernel
    answers with: that record carries ``ranked_candidates`` as
    :class:`~elc.planner.types.TargetCandidate` objects and its own
    ``policy_version`` spelling, while §14's table stores candidate **ids**
    (``ranked_candidate_ids[]``) and ``policy_profile_version``. Both sides
    are canonical — §14 is the durable shape and the kernel's record is the
    computed one — so the map between them lives in exactly one place
    (elc.planner.records documents it; elc.platform.db.planner_store
    performs it) and neither record is renamed after the other.

    ``frontier_candidate_ids`` / ``ranked_candidate_ids`` / ``factor_trace``
    are the three TEXT columns §14 spells with bracket/trace shapes. The two
    id columns are deterministic JSON arrays (the elc/teaching/store.py
    ``_array_document`` precedent) and stay so; ``factor_trace`` is the one
    column **P9-0** moved off that encoding — it carries the versioned
    :class:`FactorTraceDocument` the planner's trace is serialized to, and
    this record's field is that document (see that type, and
    ``elc/planner/trace_document.py`` for the one encoder/decoder). The field
    keeps a second arm for the **legacy** encoding a row written before P9-0
    carries: a bare JSON array of the run's prose reasons, which the decoder
    answers as the tuple of lines it always was (the ``version`` key's
    absence is the discriminant, registered in elc.planner.records judgement
    9). ``created_at`` is the store's own stamp; this record is minted **for
    the row** in P8-0 and carries it (the ``DecisionCycleRecord`` precedent),
    while the two older §14 records keep their own field sets and
    :class:`RuntimeDecisionOutcome` follows the sibling-adapter convention
    above — all three asymmetries are registered in elc.planner.records.
    """

    planner_evaluation_id: PlannerEvaluationId
    decision_cycle_id: DecisionCycleId
    frontier_candidate_ids: tuple[str, ...]
    ranked_candidate_ids: tuple[str, ...]
    factor_trace: FactorTraceDocument | tuple[str, ...]
    planner_version: PlannerVersion
    policy_profile_version: PolicyVersion
    created_at: str


# ---------------------------------------------------------------------------
# The §14 ``factor_trace`` document (Phase 9 P9-0)
# ---------------------------------------------------------------------------
#
# The **shape** of the decoded column lives here, beside the record that
# carries it, for a structural reason: ``elc/platform/types.py`` is the
# shared kernel's leaf (it imports nothing from ``elc.*``), so the record's
# field can be typed with this document without a planner → platform → planner
# import cycle. The **encoder / decoder** — the single point where the
# document is turned into bytes and back — lives in
# ``elc.planner.trace_document`` (the §14 section is Planner Data, and that
# module is where the kernel's own trace types are known).


@dataclass(frozen=True)
class FactorReadingDocument:
    """One factor's number and where it came from, as the document carries it.

    The decoded counterpart of the kernel's ``FactorReading``
    (``elc.planner.kernel``): ``factor`` / ``source`` / ``authority`` are the
    words the kernel's enums spell (recorded as their string values — the
    document is durable text and does not depend on an enum's identity), and
    ``authority`` is non-``None`` exactly when the number was read from a
    P7-0 authority.
    """

    factor: str
    value: float
    source: str
    authority: str | None


@dataclass(frozen=True)
class FactorGapDocument:
    """One factor no authority could answer, as the document carries it.

    The decoded counterpart of the kernel's ``FactorGap``: a candidate with a
    non-empty ``gaps`` tuple is not scored at all (BF-02 §5 forbids answering
    an unreadable authority with ``0``), so the gap is why a run degrades.
    """

    factor: str
    authority: str
    reason: str


@dataclass(frozen=True)
class CandidateTraceDocument:
    """One candidate's trace, field for field with the kernel's
    ``CandidateTrace``.

    **Every** field of the kernel's record is here, not a subset: the P9-0
    finding was that the durable column carried the run's prose and none of
    this, so the document is complete by construction — a reader can
    reconstruct what the kernel looked at per candidate (the readings it was
    scored from, the two partial sums, the coverage-service adjustment, the
    utility, the activation verdict and the dominance/tie facts) without
    re-running anything. An excluded candidate carries its exclusion reason
    and ``None`` scores, exactly as the kernel carries it (hard exclusion is
    not a penalty).
    """

    candidate_id: str
    canonical_key: str
    merged_from: tuple[str, ...]
    initiative_class: str
    request_priority: int
    coverage_service_state: str
    benefit: tuple[FactorReadingDocument, ...]
    cost: tuple[FactorReadingDocument, ...]
    gaps: tuple[FactorGapDocument, ...]
    excluded: str | None
    benefit_score: float | None
    cost_score: float | None
    coverage_service_bonus: float | None
    utility: float | None
    activation_path: str | None
    activation_threshold: float | None
    activated: bool | None
    dominated_by: tuple[str, ...]
    in_tie_set: bool
    selected: bool


@dataclass(frozen=True)
class FactorTraceDocument:
    """The decoded §14 ``factor_trace`` column: a versioned, structured trace.

    Four keys, and each answers one question a reader of the durable row
    asks:

    - ``version`` — which template produced the document. It is also the
      **discriminant** between this encoding and the legacy one a row
      written before P9-0 carries (a bare JSON array of prose lines, no
      ``version`` key); ``elc.planner.trace_document`` owns both words;
    - ``provenance`` — whether the candidates below are the kernel's own
      trace or the row states that no trace was recorded for the cycle. The
      distinction is not cosmetic: a caller may record a cycle without
      holding a ``PlannerTrace`` (a leg that could not run records its own
      degraded shape), and "the run looked at nothing" must not be readable
      as "nobody wrote down what it looked at" — nor the reverse;
    - ``reasons`` — the run's prose ``reason_trace``, verbatim and in its own
      order. P9-0 **split** the two: the column is no longer the prose array
      it used to be, and the prose now travels as one named part of the
      structured document instead of *being* the column's content;
    - ``candidates`` — the per-candidate trace tuples, canonicalized (see
      the encoder's own rules).
    """

    version: str
    provenance: str
    reasons: tuple[str, ...]
    candidates: tuple[CandidateTraceDocument, ...]


@dataclass(frozen=True)
class RuntimeDecisionOutcome:
    """docs/DATA_MODEL.md §14 RuntimeDecisionOutcome — the durable record.

    Phase 8 P8-0. ``turn_id`` is the key (§14 gives this block no independent
    id, and RUNTIME_ARCHITECTURE §4 step 9A defines the outcome at the turn
    level); ``decision_cycle_id`` is optional because §14 spells it ``?`` —
    ``None`` is the honest shape of a turn whose outcome was recorded without
    a cycle. ``reason_codes`` is the bracketed list column and carries the
    caller's own words: §14 pins the *outcome* vocabulary (two words) and
    pins none for the reasons, so this record mints none either.

    The four fields are the block's non-clock columns, and ``created_at`` —
    which §14 also lists — is the **store's** stamp, not a record field (the
    convention the sibling adapters follow: the in-memory record carries no
    clock). The name is §14's; the enum is spelled
    ``RuntimeDecisionOutcomeValue`` so the two are visibly distinct — the
    same split :class:`PlannerExecutionStatusRecord` carries.
    """

    turn_id: TurnId
    decision_cycle_id: DecisionCycleId | None
    outcome: RuntimeDecisionOutcomeValue
    reason_codes: tuple[str, ...]
