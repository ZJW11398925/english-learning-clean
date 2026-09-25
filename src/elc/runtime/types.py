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

CP4 projection contracts (P4-0 ④ — semantics fixed here; the runtime that
executes them is P4-2, and nothing in this slice pretends otherwise):

- **stable projection_id** — the job id is *derived*, not minted: one
  (projection_type, source turn) pair always yields the same
  ``projection_id``, so a re-enqueue or a recovery补齐 addresses the same
  durable row.
- **idempotent enqueue** — enqueuing an existing job is a replay of the
  durable row, never a second job and never a reset of its state.
- **state machine** — PENDING → RUNNING → COMMITTED, and
  FAILED_RETRYABLE → REJECTED; the five words are DATA_MODEL §22.1's and
  are enforced durably by migration 0002's status CHECK (see
  ProjectionJobState).
- **source-aware + version-aware revalidation** — a retry revalidates
  ``source_turn_slice_hash`` (the canonical slice the job was computed
  from is unchanged) and ``base_domain_version`` (the derived base the
  projection builds on). DATA_MODEL §22.1: "Projection retry 必须
  source-aware + version-aware revalidation，不允许 blind SQL replay".
- **CP4 never holds the ConversationCoordinatorLease** — projections run
  after the canonical turn, and a failing projection does not keep
  occupying the conversation's one-coordinator guarantee
  (RUNTIME_ARCHITECTURE §19 "不继续占用 ConversationCoordinatorLease").
- **failure is not the turn's failure** — a projection failure never rolls
  back the transcript, never re-sends the assistant message and never
  blocks the next turn (§19/§21 "turn still succeeds / projection
  retry/rebuild").
- **crash-gap** — a job that was lost between the turn's commit points is
  not re-derived from a message log: ``ensure_projection_jobs`` re-creates
  it from the same deterministic id (the P4-2 face; P4-3 widened it to one
  job per supported type — the crash-gap rule is per ``(projection_type,
  turn)`` pair, so a turn missing both types is repaired for both), which
  is exactly what the stable-id rule buys.

Not in this package's contract: teaching-evidence proposals. Learning's
durable pending proposal (migration 0009, ``teaching_evidence_proposal``)
is canonical evidence input owned by the Learning domain, deliberately NOT
a projection_job row — evidence truth never rides a rebuildable
projection's retry policy.
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
    (R-INV-003); occupies no message sequence.

    Phase 3 P3-1A: the record carries the full §4 column set — the
    snapshot/version columns are ``None`` when no authority has stamped
    them (the legacy backfill of migration 0007 and the Phase 3 cycles
    whose Curriculum/Goal/Schedule/Policy sources have not arrived yet;
    see elc.runtime.decision_cycles.DecisionCycleBindings). ``None`` is
    the honest "no source", never a fabricated version string.
    """

    decision_cycle_id: DecisionCycleId
    turn_id: TurnId
    cycle_index: int
    learning_snapshot_id: str | None
    evidence_watermark: int | None
    curriculum_version: str | None
    goal_version: str | None
    schedule_version: str | None
    policy_version: str | None
    context_view_version: str | None
    relationship_view_version: str | None = None
    planner_decision_id: str | None = None
    gate_decision_id: str | None = None
    created_at: str | None = None


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
    """docs/DOMAIN_MODEL.md §16 ProjectionJob (registry schema).

    The durable CP4 work row is migration 0002's ``projection_job`` table;
    its semantics are adjudicated in this module's docstring (P4-0 ④
    contracts). This record is the registry schema view — a projection job
    is derived, rebuildable work, never a domain truth.
    """

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

    kind: str  # TURN | ACTION | MOMENT | ANALYSIS | DELIVERY | LOCK
    id: str
    action: str


@dataclass(frozen=True)
class TurnCompletion:
    """Terminal result of one full turn through the minimum pipeline
    (IMPLEMENTATION_PLAN §3: UserTurn durable → Persona Runtime →
    Validator → Delivery → AssistantTurn).

    ``ledger_event`` / ``ledger_failure`` are the §20 exposure write's outcome
    on a turn that delivered a teaching action (P8-4) — the word recorded, and
    the readable reason when a word existed but the write did not happen. Both
    stay ``None`` on an ordinary persona turn (nothing to present) and whenever
    no ledger writer was injected; ``elc.runtime.controller.
    TeachingActionDelivery`` states the two fields' meaning.

    ``delivery_state`` / ``delivery_failure_reason`` are the P9-2 streamed
    delivery's own two (RUNTIME §13 GUARDED_STREAM): the §13 terminal word the
    delivery froze at, and the delivery side's note of any non-fatal but
    visible secondary failure — the delivery did not reach ``SENT_COMPLETE``
    (a stopped source, a refused chunk, a refused transport, a refused record
    write, and, on the streamed face, the §21.1 guard row's own refused write
    joined onto the invalidation reason), **or** it did reach it and a write
    beside it was refused (P9-4's §22 initial estimate: a ``SENT_COMPLETE``
    delivery that ends ``REPLIED_FULL`` can still carry the note — both
    delivery faces join it here, and the buffered teaching leg reads it back
    off this field). ``None`` when nothing went wrong; §20's ledger write and
    the buffered face's §21.1 note keep ``ledger_failure`` as their own
    channel. ``delivery_failure_reason`` stays ``None`` on every
    ``BUFFERED_VALIDATED`` finalization whose estimate write succeeded (§13's
    other mode declares its word on the request, and this cut changes no line
    of that path). ``reply_text`` is the **prefix actually sent** on a streamed
    delivery, so the two fields and the text never contradict each other: a
    partial delivery reports ``SENT_PARTIAL`` with its reason beside the exact
    prefix the client received.
    """

    turn_id: TurnId
    action_id: ActionId
    assistant_turn_id: str | None
    turn_status: TurnStatus
    action_status: GenerationActionStatus
    outcome: str | None  # TurnOutcome value (str to avoid a cycle here)
    reply_text: str | None
    failure_reason: str | None
    state_version: int
    ledger_event: str | None = None
    ledger_failure: str | None = None
    delivery_state: str | None = None
    delivery_failure_reason: str | None = None
