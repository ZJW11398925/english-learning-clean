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
    UserTurnId,
)

__all__ = [
    "ABORT_REASONS",
    "ATTEMPT_OUTCOMES",
    "AbortReason",
    "AnswerExposureState",
    "AttemptEvaluationRecord",
    "AttemptOutcome",
    "AttemptRecord",
    "AuthorizationBasis",
    "COMPLETION_OUTCOMES",
    "CompletionOutcome",
    "EphemeralTeachingDirective",
    "ExposureEstimateCertainty",
    "GateDecisionContext",
    "GateDecisionRecord",
    "GateDecisionValue",
    "GateExecutionStatusRecord",
    "GateExecutionStatusValue",
    "MomentSource",
    "MomentState",
    "PresentationPhase",
    "ResumeDirective",
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


class CompletionOutcome(StrEnum):
    """docs/STATE_MACHINES.md §6 teaching completion outcomes, word for
    word. "这些只描述 teaching episode，不写 mastery" — the vocabulary is
    the episode's closure, never a learner-state write."""

    SUCCESS_UNSUPPORTED = "SUCCESS_UNSUPPORTED"
    SUCCESS_SUPPORTED = "SUCCESS_SUPPORTED"
    SUCCESS_ALTERNATIVE = "SUCCESS_ALTERNATIVE"
    PARTIAL_PROGRESS = "PARTIAL_PROGRESS"
    REVEALED = "REVEALED"
    USER_SATISFIED = "USER_SATISFIED"
    NO_FURTHER_VALUE = "NO_FURTHER_VALUE"


class AbortReason(StrEnum):
    """docs/STATE_MACHINES.md §7 teaching abort reasons, word for word.

    "Abort 本身不产生 negative mastery evidence" (§7): the reason is the
    episode's closure trace, never a learner claim."""

    USER_SKIP = "USER_SKIP"
    USER_REJECTED_TARGET = "USER_REJECTED_TARGET"
    USER_TOPIC_SHIFT = "USER_TOPIC_SHIFT"
    USER_SWITCH_TARGET = "USER_SWITCH_TARGET"
    AMBIGUOUS_EXIT = "AMBIGUOUS_EXIT"
    POLICY_STOP = "POLICY_STOP"
    ATTEMPT_LIMIT = "ATTEMPT_LIMIT"
    CONTENT_INVALID = "CONTENT_INVALID"
    SNAPSHOT_INVALIDATED = "SNAPSHOT_INVALIDATED"
    PRE_DELIVERY_INVALIDATED = "PRE_DELIVERY_INVALIDATED"
    SYSTEM_FAILURE = "SYSTEM_FAILURE"
    DELIVERY_FAILURE = "DELIVERY_FAILURE"
    EXPIRED = "EXPIRED"
    SYSTEM_RECOVERY_ABORT = "SYSTEM_RECOVERY_ABORT"


#: The two canonical §6/§7 word lists as tuples (the migration CHECK sets
#: and the repo-native tests share exactly these).
COMPLETION_OUTCOMES = tuple(item.value for item in CompletionOutcome)
ABORT_REASONS = tuple(item.value for item in AbortReason)


class AnswerExposureState(StrEnum):
    """ExposureEstimate ``exposure_level`` (docs/STATE_MACHINES.md §13
    lines 434-438) — how much of the answer was visible when the attempt
    happened. Deliberately teaching-owned: the Learning domain has its own
    copy of this vocabulary for evidence claims (the AST pin)."""

    NONE = "NONE"
    PARTIAL = "PARTIAL"
    FULL = "FULL"


class ExposureEstimateCertainty(StrEnum):
    """ExposureEstimate ``certainty`` (docs/STATE_MACHINES.md §13 lines
    428-432). ``SERVER_SENT_UNCONFIRMED`` is the honest value for the Local
    V1 buffered delivery (no ClientRenderAck yet)."""

    CONFIRMED_RENDERED = "CONFIRMED_RENDERED"
    SERVER_SENT_UNCONFIRMED = "SERVER_SENT_UNCONFIRMED"
    UNKNOWN = "UNKNOWN"


class AttemptOutcome(StrEnum):
    """docs/STATE_MACHINES.md §5 evaluation outcomes, word for word.

    Deliberately teaching-owned (the ``TeachingSupportLevel`` precedent):
    the Learning domain has its own copy of this vocabulary for evidence
    claims, and ``teaching`` never imports the learning package (the AST
    pin of this slice). The two lists are kept identical word for word and
    pinned as such by test; the conversion between the five-value attempt
    outcome and the four-value §6 claim outcome happens in Learning.
    """

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILURE = "FAILURE"
    ALTERNATIVE_SUCCESS = "ALTERNATIVE_SUCCESS"
    ABSTAIN = "ABSTAIN"


#: The five §5 words, as a tuple (the migration CHECK set and the tests
#: share exactly this).
ATTEMPT_OUTCOMES = tuple(item.value for item in AttemptOutcome)


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
    """docs/DATA_MODEL.md §17 AttemptRecord — the ten-column set word for
    word (migration 0008). ``attempt_index`` starts at 1 and counts
    attempts inside one moment (the moment's own ``attempt_index`` mirrors
    the count after each recorded attempt, so UNIQUE(moment_id,
    attempt_index) is the §25 attempt identity).

    ``support_level_before_attempt`` is the support the attempt was made
    under; ``answer_exposure_state``/``exposure_estimate_id`` /
    ``support_attribution_*`` are the §13 exposure facts of the moment at
    that point — the conservative attribution basis (§13: "不确定时使用
    conservative upper-bound support attribution")."""

    attempt_id: AttemptId
    moment_id: MomentId
    attempt_index: int
    user_turn_id: UserTurnId
    support_level_before_attempt: TeachingSupportLevel
    answer_exposure_state: AnswerExposureState
    exposure_estimate_id: str | None
    support_attribution_certainty: ExposureEstimateCertainty
    support_attribution_basis: str
    created_at: str | None = None


@dataclass(frozen=True)
class AttemptEvaluationRecord:
    """docs/DATA_MODEL.md §17 AttemptEvaluationRecord — the nine-column set
    word for word (migration 0008).

    ``outcome`` carries the full STATE_MACHINES §5 five-value set: the
    evaluator does NOT fold ALTERNATIVE_SUCCESS into SUCCESS here — the
    capability-positive / resource-neutral mapping is the Learning evidence
    conversion (DEC-…2babb21e.5 Q4). ``evidence_proposal_refs`` records
    which durable evidence proposals this evaluation produced (empty when
    the attempt produced none, e.g. an ABSTAIN with no claim)."""

    attempt_evaluation_id: AttemptEvaluationId
    moment_id: MomentId
    attempt_id: AttemptId
    evaluator_id: str
    evaluator_version: str
    outcome: str
    confidence: float
    evidence_proposal_refs: tuple[str, ...] = ()
    created_at: str | None = None


@dataclass(frozen=True)
class EphemeralTeachingDirective:
    """Teaching Planner output (docs/DOMAIN_MODEL.md §14): converts a
    TargetCandidate for Persona Runtime consumption; creates no persona
    prompt and no persona identity (D-INV-002).

    Phase 3 P3-1B: the directive carries exactly the fields Persona Runtime
    needs to render the ``[teaching]`` section — the moment/action links,
    the presentation ladder position (phase + support, computed by Teaching
    from the target fixture, never chosen by the provider) and the text of
    the currently delivered ladder step. The Persona authoritative prompt
    stays with ``PromptCompiler``; the directive is a view, not a prompt."""

    moment_id: MomentId
    action_id: ActionId
    focus_target_id: TargetId
    hint: str | None
    focus_target_type: str = "RESOURCE"
    action_type: str = "TEACHING_OPEN"
    presentation_phase: PresentationPhase = PresentationPhase.INITIAL_PROMPT
    support_level: TeachingSupportLevel = TeachingSupportLevel.NONE
    attempt_index: int = 0
    teaching_text: str | None = None
    reveal_text: str | None = None
    explanation_text: str | None = None


@dataclass(frozen=True)
class ResumeDirective:
    """The narrow Persona Resume view (docs/STATE_MACHINES.md §1
    ``RESUMING → PERSONA_RESUME``).

    Deliberately NOT the TeachingMoment record: the resume action carries
    only what the persona needs to return to normal conversation — the
    closed episode's outcome/reason and its focus target. No attempts, no
    snapshots, no ladder internals leak into the resume prompt (the moment
    is TEACHING_TERMINAL by then; "只传 ResumeDirective 不泄 Moment")."""

    moment_id: MomentId
    conversation_id: ConversationId
    focus_target_type: str
    focus_target_id: str
    closure: str  # CompletionOutcome value | AbortReason value
    completion_outcome: str | None = None
    abort_reason: str | None = None

    def as_view_fields(self) -> tuple[tuple[str, str], ...]:
        """The directive's canonical (key, value) pairs, in fixed order —
        what Persona Runtime renders into the resume section. Keys and
        order are pinned here so the prompt is byte-deterministic."""

        return (
            ("moment_id", str(self.moment_id)),
            ("focus_target_type", self.focus_target_type),
            ("focus_target_id", self.focus_target_id),
            ("closure", self.closure),
            ("completion_outcome", self.completion_outcome or ""),
            ("abort_reason", self.abort_reason or ""),
        )
