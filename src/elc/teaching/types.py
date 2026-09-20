"""Teaching domain — TeachingMoment lifecycle + Teaching Gate authority.

Owns (docs/DOMAIN_MODEL.md §14): TeachingMoment, AttemptRecord,
AttemptEvaluationRecord, PresentationAction, TeachingResponseEnvelope,
TeachingLockLease, teaching lifecycle.

The Teaching Gate is the ONLY authorization authority for executing a
teaching action; the Planner only judges worth-teaching (§14). Gate unknown
critical state yields GateExecutionStatus=DEGRADED with NO synthetic
GateDecision(DENY) (docs/DATA_MODEL.md §14.1). Gate does not recompute
learning_need and never reranks after DENY within one DecisionCycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    ActionId,
    AttemptEvaluationId,
    AttemptId,
    DecisionCycleId,
    GateDecisionId,
    MomentId,
    PolicyVersion,
    StateVersion,
    TargetId,
)


class GateDecisionContext(StrEnum):
    """docs/DOMAIN_MODEL.md §14 decision contexts."""

    OPEN = "OPEN"
    AUTO_CONTINUE = "AUTO_CONTINUE"
    USER_REQUESTED_CONTINUE = "USER_REQUESTED_CONTINUE"


class GateDecisionValue(StrEnum):
    """docs/DATA_MODEL.md §14.1 — NO_TARGET implies no GateDecision at all."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class GateExecutionStatusValue(StrEnum):
    """docs/DATA_MODEL.md §14.1 — DEGRADED means critical facts unknown."""

    SUCCEEDED = "SUCCEEDED"
    DEGRADED = "DEGRADED"


class AuthorizationBasis(StrEnum):
    """OPEN binds DecisionCycle authorization; continuation binds
    ActiveMoment authorization (docs/DATA_MODEL.md §24.2)."""

    DECISION_CYCLE = "DECISION_CYCLE"
    ACTIVE_MOMENT = "ACTIVE_MOMENT"


class MomentState(StrEnum):
    """TeachingMoment lifecycle — the canonical state list, word for word,
    from docs/STATE_MACHINES.md §1 "Canonical lifecycle states" lines 13-22.
    Vocabulary only: transitions are owned by the Teaching domain
    controller (later phases), not by this enum."""

    AUTHORIZED = "AUTHORIZED"
    OPENING = "OPENING"
    AWAITING_USER = "AWAITING_USER"
    EVALUATING = "EVALUATING"
    DECIDING_NEXT_ACTION = "DECIDING_NEXT_ACTION"
    COMPLETING = "COMPLETING"
    ABORTING = "ABORTING"
    TEACHING_TERMINAL = "TEACHING_TERMINAL"
    RESUMING = "RESUMING"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class GateDecisionRecord:
    """docs/DATA_MODEL.md §14.1."""

    gate_decision_id: GateDecisionId
    decision_cycle_id: DecisionCycleId
    candidate_id: str
    context: GateDecisionContext
    decision: GateDecisionValue
    reason_codes: tuple[str, ...]
    policy_version: PolicyVersion


@dataclass(frozen=True)
class GateExecutionStatusRecord:
    """docs/DATA_MODEL.md §14.1 — no synthetic DENY on DEGRADED."""

    decision_cycle_id: DecisionCycleId | None
    moment_id: MomentId | None
    gate_context: GateDecisionContext
    authorization_basis: AuthorizationBasis
    authorization_status: str  # VALID | INVALIDATED | UNKNOWN
    status: GateExecutionStatusValue
    missing_or_unknown: tuple[str, ...]


@dataclass(frozen=True)
class TeachingMomentRecord:
    """Single-FocusTarget moment (docs/DOMAIN_MODEL.md §15)."""

    moment_id: MomentId
    conversation_id: str
    focus_target_id: TargetId
    state: MomentState
    state_version: StateVersion
    opened_by_gate_decision_id: GateDecisionId
    full_answer_exposed: bool


@dataclass(frozen=True)
class AttemptRecord:
    """docs/DOMAIN_MODEL.md §14 — one user attempt inside a moment."""

    attempt_id: AttemptId
    moment_id: MomentId
    attempt_index: int
    content: str


@dataclass(frozen=True)
class AttemptEvaluationRecord:
    attempt_evaluation_id: AttemptEvaluationId
    attempt_id: AttemptId
    evaluator_version: str
    outcome: str


@dataclass(frozen=True)
class EphemeralTeachingDirective:
    """Teaching Planner output (docs/DOMAIN_MODEL.md §14): converts a
    TargetCandidate for Persona Runtime consumption; creates no persona
    prompt and no persona identity (D-INV-002)."""

    moment_id: MomentId
    action_id: ActionId
    focus_target_id: TargetId
    hint: str | None
