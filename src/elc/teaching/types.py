"""Teaching domain — TeachingMoment lifecycle + Teaching Gate authority.

Owns (docs/DOMAIN_MODEL.md §14): TeachingMoment, AttemptRecord,
AttemptEvaluationRecord, PresentationAction, TeachingResponseEnvelope,
TeachingLockLease, teaching lifecycle.

The Teaching Gate is the ONLY authorization authority for executing a
teaching action; the Planner only judges worth-teaching (§14). Gate unknown
critical state yields GateExecutionStatus=DEGRADED with NO synthetic
GateDecision(DENY) (docs/DATA_MODEL.md §14.1). Gate does not recompute
learning_need and never reranks after DENY within one DecisionCycle.

Phase 3 P3-1A (TASK-OPI-2babb21e-….17 ③④): the TeachingMoment record is
redefined from the Phase 0 seven-field stub to the full docs/DATA_MODEL.md
§15 column set (the P3-0 CharacterPackage precedent), the GateDecision /
GateExecutionStatus records to the full §14.1 sets, and the presentation
vocabularies (STATE_MACHINES §3) are pinned here. The Gate profile itself
lives in elc.teaching.gate; the durable CP2 executor in elc.teaching.store.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.platform.types import (
    ActionId,
    AttemptEvaluationId,
    AttemptId,
    ConversationId,
    DecisionCycleId,
    EvidenceModality,
    GateDecisionId,
    MomentId,
    PersonaId,
    PolicyVersion,
    TargetId,
)

__all__ = [
    "AttemptEvaluationRecord",
    "AttemptRecord",
    "AuthorizationBasis",
    "EphemeralTeachingDirective",
    "GateDecisionContext",
    "GateDecisionRecord",
    "GateDecisionValue",
    "GateExecutionStatusRecord",
    "GateExecutionStatusValue",
    "MomentSource",
    "MomentState",
    "PresentationPhase",
    "TeachingMomentRecord",
    "TeachingSupportLevel",
    "TeachingTargetRef",
]


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


class MomentSource(StrEnum):
    """docs/DATA_MODEL.md §15 source vocabulary, word for word."""

    AUTOMATIC = "AUTOMATIC"
    USER_INITIATED = "USER_INITIATED"
    MANUAL_FOCUS = "MANUAL_FOCUS"
    SCHEDULED_STUDY = "SCHEDULED_STUDY"


class PresentationPhase(StrEnum):
    """docs/STATE_MACHINES.md §3 teaching presentation phases, word for
    word. Vocabulary only — the presentation progression is P3-1B."""

    INITIAL_PROMPT = "INITIAL_PROMPT"
    HINT_SEMANTIC = "HINT_SEMANTIC"
    HINT_STRUCTURAL = "HINT_STRUCTURAL"
    HINT_PARTIAL_FORM = "HINT_PARTIAL_FORM"
    FULL_REVEAL = "FULL_REVEAL"
    POST_REVEAL_OPTIONAL_ATTEMPT = "POST_REVEAL_OPTIONAL_ATTEMPT"
    EXPLANATION = "EXPLANATION"


class TeachingSupportLevel(StrEnum):
    """docs/STATE_MACHINES.md §3 support levels, word for word.

    Deliberately teaching-owned: the Learning domain has its own support
    vocabulary for evidence claims, and ``teaching`` never imports the
    learning package internals (the AST pin of this slice)."""

    NONE = "NONE"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    SEMANTIC_HINT = "SEMANTIC_HINT"
    STRUCTURAL_HINT = "STRUCTURAL_HINT"
    PARTIAL_FORM = "PARTIAL_FORM"
    FULL_FORM_SHOWN = "FULL_FORM_SHOWN"


@dataclass(frozen=True)
class TeachingTargetRef:
    """One target as a (type, id) pair — the §15 ``focus_target`` /
    ``supporting_targets[]`` element. The durable form is JSON under the
    canonical column name (migration 0007 storage note)."""

    target_type: str
    target_id: str

    def as_document(self) -> dict[str, str]:
        return {"target_type": self.target_type, "target_id": self.target_id}


@dataclass(frozen=True)
class GateDecisionRecord:
    """docs/DATA_MODEL.md §14.1 gate_decision (eight columns)."""

    gate_decision_id: GateDecisionId
    decision_cycle_id: DecisionCycleId
    candidate_id: str
    context: GateDecisionContext
    decision: GateDecisionValue
    reason_codes: tuple[str, ...]
    policy_version: PolicyVersion
    created_at: str | None = None


@dataclass(frozen=True)
class GateExecutionStatusRecord:
    """docs/DATA_MODEL.md §14.1 gate_execution_status — no synthetic DENY
    on DEGRADED; ``missing_or_unknown`` carries the fact keys."""

    gate_execution_status_id: str
    decision_cycle_id: DecisionCycleId | None
    moment_id: MomentId | None
    gate_context: GateDecisionContext
    authorization_basis: AuthorizationBasis
    authorization_status: str  # VALID | INVALIDATED | UNKNOWN
    status: GateExecutionStatusValue
    missing_or_unknown: tuple[str, ...]
    created_at: str | None = None


@dataclass(frozen=True)
class TeachingMomentRecord:
    """docs/DATA_MODEL.md §15 TeachingMoment — the full thirty-column set.

    Single FocusTarget (docs/DOMAIN_MODEL.md §15); v1 has no long-lived
    suspended zombie moment. ``None`` on a version column means "no source
    in this phase" — see migration 0007's header.
    """

    moment_id: MomentId
    conversation_id: ConversationId
    persona_id: PersonaId | None
    source: MomentSource
    decision_cycle_id: DecisionCycleId
    candidate_id: str
    gate_decision_id: GateDecisionId
    focus_target: TeachingTargetRef
    supporting_targets: tuple[TeachingTargetRef, ...]
    target_mode: str
    learning_intent: str
    evidence_modality: EvidenceModality
    evidence_goal: str | None
    preferred_support_ceiling: str | None
    learning_snapshot_id: str | None
    evidence_watermark: int | None
    curriculum_version: str | None
    content_version: str | None
    policy_version: str | None
    lifecycle_state: MomentState
    presentation_phase: PresentationPhase
    attempt_index: int
    support_level: TeachingSupportLevel
    completion_outcome: str | None
    abort_reason: str | None
    state_version: int
    created_at: str | None = None
    opened_at: str | None = None
    teaching_terminal_at: str | None = None
    closed_at: str | None = None


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
