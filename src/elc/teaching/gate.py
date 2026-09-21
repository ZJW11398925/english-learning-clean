"""Teaching Gate — USER_INITIATED OPEN applicable profile (Phase 3 P3-1A).

Authority: docs/DOMAIN_MODEL.md §14 — the Gate is the only "may execute now?"
authority; docs/STATE_MACHINES.md §12.1 and docs/RUNTIME_ARCHITECTURE.md
§24.2 fix its scope. docs/DATA_MODEL.md §14.1 fixes the durable output
shapes: ``GateExecutionStatus(SUCCEEDED) + GateDecision(ALLOW|DENY)``, or
``GateExecutionStatus(DEGRADED)`` with **no** GateDecision — critical
execution facts unknown must never be laundered into a synthetic DENY
(and never risked into an ALLOW).

Frozen semantics: ``behavioral_baselines/gate/teaching_gate_reference_v1_1.py``
(GATE BEHAVIORAL BASELINE V1.1, BF-03 + the cross-layer v1.1 repair). This
module is the repo-native profile for the slice's only context —
USER-initiated OPEN — and reproduces the reference's decision logic for
that path word for word (the differential test in tests/phase3 compares
both implementations over a fact matrix). Nothing under
``behavioral_baselines/`` is imported or modified: the frozen reference is
a test oracle only.

USER_INITIATED OPEN (mother decision DEC-OPI-2babb21e-….5 core ruling ①):

- BF-03 v1.1 requires Planner SUCCEEDED + SELECT for an AUTOMATIC OPEN. A
  user-initiated OPEN has an explicit request candidate plus its
  DecisionCycle; the planner fields are NOT_APPLICABLE here and no
  PlannerDecision is fabricated (a synthetic SELECT would be exactly the
  kind of laundered state DOMAIN_MODEL §10 forbids). The two paths meet in
  the same execution-admissibility core.
- Applicable check families (the six of the task book), in the frozen
  decision order:

  1. safety/privacy      → SAFETY_PRIVACY_BLOCK / UNKNOWN→DEGRADED
  2. suppression         → TARGET_SUPPRESSED (any context; explicit user
                           requests do not bypass it — BF-03 §10/§20)
  3. target/content      → TARGET_INVALID / CONTENT_INVALID /
                           UNKNOWN→DEGRADED
  4. authorization       → AUTHORIZATION_INVALID (decision-cycle
     lineage               authorization), ACTION_CANCELLED /
                           ACTION_SUPERSEDED (subject lineage), and the
                           latest-user-intent revalidation of BF-03 §11
                           (USER_INTENT_BLOCK)
  5. lock/lifecycle      → TEACHING_LOCK_CONFLICT (BF-03 §14 OPEN: any
                           existing lock denies)
  6. hard limits         → HARD_ATTEMPT_LIMIT / HARD_TEACHING_TURN_LIMIT
                           belong to continuation contexts only (the
                           frozen reference evaluates them under
                           AUTO_CONTINUE / USER_REQUESTED_CONTINUE); an
                           OPEN has no active moment, so they cannot fire
                           here and stay vocabulary-only in this slice
                           (continuation lands with P3-1B).

- Automatic-only controls are deliberately absent from this profile:
  auto-teach preference, automatic opening budget / cooldown and
  conversation-flow protection all guard *unsolicited* interruption and
  are bypassed by a user-initiated request in BF-03 v1.1 (§12/§13/§16/§17);
  the AUTOMATIC branch of the Gate is Phase 8 and stays unimplemented.

NO_SOURCE facts (P3-1A, docstring-flagged, never fabricated):

- safety/privacy: the BF-05 Safety/Privacy contract and its durable
  authority do not exist yet, so the fact is assembled as an explicit
  ``ALLOW`` from an explicit *absence of source* — the constant
  :data:`SAFETY_PRIVACY_NO_SOURCE` documents that this is "no authority
  said BLOCK", not "an authority said it is safe". Datasource wiring lands
  with the authority (later slice).
- suppression: TeachingPreference / PlannerConstraint (docs/DATA_MODEL.md
  §9) are Phase 6/7 tables that do not exist yet, so
  :data:`TARGET_SUPPRESSED_NO_SOURCE` = False with the same honest
  NO_SOURCE meaning.

Both are deterministic (never UNKNOWN) precisely because an absent source
must not degrade a user's explicit request; the trace stays truthful via
this docstring and the constants.

Critical-state completeness: the eight fact keys of this slice —
LEARNING_SNAPSHOT, AUTHORIZATION_STATUS, TARGET_VALIDITY,
CONTENT_VALIDITY, LOCK_STATE, SAFETY_PRIVACY_STATUS, SUBJECT_STATUS,
GATE_STATE (docs/DATA_MODEL.md §14.1 ``missing_or_unknown[]``). Any
UNKNOWN fact yields ``GateExecutionStatus=DEGRADED`` with no GateDecision.
``missing_or_unknown`` is emitted in the frozen reference's deterministic
(sorted) order.

Contract errors (BF-03 §21) raise :class:`GateInputError`: calling the
Gate with an invalid context/action/enum is a program error, not a
decision — it is never DENY and never DEGRADED.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from elc.teaching.targets import CONTENT_STATUSES, TARGET_STATUSES

__all__ = [
    "DENY_PRECEDENCE",
    "GATE_CONTEXTS",
    "GATE_POLICY_VERSION",
    "MISSING_OR_UNKNOWN_FACT_KEYS",
    "OPEN_ACTIONS",
    "SAFETY_PRIVACY_NO_SOURCE",
    "TARGET_SUPPRESSED_NO_SOURCE",
    "USER_INITIATED_OPEN_REASON_CODES",
    "USER_INTENT_SCOPES",
    "EnvFactsNoSource",
    "GateInputError",
    "GateVerdict",
    "UserInitiatedOpenFacts",
    "decide_user_initiated_open",
]

#: BF-03 gate contexts (docs/DATA_MODEL.md §14.1 ``context`` vocabulary).
GATE_CONTEXTS = ("OPEN", "AUTO_CONTINUE", "USER_REQUESTED_CONTINUE")

#: BF-03 proposed-action vocabulary for an OPEN (the reference's ACTIONS
#: set restricted to the opening action; continuations are P3-1B).
OPEN_ACTIONS = ("OPENING",)

#: BF-03 user intent scopes (the reference's USER_INTENTS set).
USER_INTENT_SCOPES = (
    "OPEN",
    "LEARNING_REQUEST",
    "TARGETED_LEARNING_REQUEST",
    "JUST_CHAT",
    "NON_LEARNING_TASK",
    "ACTIVE_TEACHING_CONTINUATION",
)

#: The intention scopes a USER_INITIATED OPEN may carry (BF-03 §11:
#: "User-initiated OPEN: 最新 intent 必须仍然 LEARNING_REQUEST /
#: TARGETED_LEARNING_REQUEST").
USER_INITIATED_OPEN_INTENTS = ("LEARNING_REQUEST", "TARGETED_LEARNING_REQUEST")

#: The frozen BF-03 v1.1 deny precedence (behavioral_baselines/gate/
#: teaching_gate_reference_v1_1.py DENY_PRECEDENCE, word for word). The
#: gate returns every hit and orders them by this list, so a trace never
#: depends on the incidental order of code checks (BF-03 §22).
DENY_PRECEDENCE = (
    "SAFETY_PRIVACY_BLOCK",
    "ACTION_CANCELLED",
    "ACTION_SUPERSEDED",
    "AUTHORIZATION_INVALID",
    "TARGET_INVALID",
    "CONTENT_INVALID",
    "TARGET_SUPPRESSED",
    "USER_INTENT_BLOCK",
    "AUTO_TEACH_DISABLED",
    "TEACHING_LOCK_CONFLICT",
    "TEACHING_LOCK_INVALID",
    "MOMENT_NOT_CONTINUABLE",
    "HARD_PROTECTED_FLOW",
    "AUTO_SESSION_BUDGET_EXHAUSTED",
    "HARD_COOLDOWN_ACTIVE",
    "HARD_ATTEMPT_LIMIT",
    "HARD_TEACHING_TURN_LIMIT",
)

#: The DENY codes the USER_INITIATED OPEN profile can actually emit, in
#: precedence order. USER_INTENT_BLOCK is part of BF-03 §11 for this path
#: (the task book's abbreviated OPEN list omits it); HARD_ATTEMPT_LIMIT /
#: HARD_TEACHING_TURN_LIMIT are continuation-only in the frozen reference
#: and cannot fire on an OPEN; AUTO_TEACH_DISABLED / HARD_PROTECTED_FLOW /
#: AUTO_SESSION_BUDGET_EXHAUSTED / HARD_COOLDOWN_ACTIVE are automatic-only
#: controls a user-initiated request bypasses; TEACHING_LOCK_INVALID /
#: MOMENT_NOT_CONTINUABLE are continuation lifecycle codes (P3-1B).
USER_INITIATED_OPEN_REASON_CODES = tuple(
    code
    for code in DENY_PRECEDENCE
    if code
    in {
        "SAFETY_PRIVACY_BLOCK",
        "ACTION_CANCELLED",
        "ACTION_SUPERSEDED",
        "AUTHORIZATION_INVALID",
        "TARGET_INVALID",
        "CONTENT_INVALID",
        "TARGET_SUPPRESSED",
        "USER_INTENT_BLOCK",
        "TEACHING_LOCK_CONFLICT",
    }
)

#: docs/DATA_MODEL.md §14.1 ``missing_or_unknown[]`` fact keys of this
#: slice — the eight execution facts whose unknown-ness degrades the Gate.
MISSING_OR_UNKNOWN_FACT_KEYS = (
    "LEARNING_SNAPSHOT",
    "AUTHORIZATION_STATUS",
    "TARGET_VALIDITY",
    "CONTENT_VALIDITY",
    "LOCK_STATE",
    "SAFETY_PRIVACY_STATUS",
    "SUBJECT_STATUS",
    "GATE_STATE",
)

#: Policy identity stamped on every GateDecision row (docs/DATA_MODEL.md
#: §14.1 ``policy_version``): the frozen BF-03 v1.1 semantics this profile
#: reproduces.
GATE_POLICY_VERSION = "bf-03-gate-v1.1"

#: NO_SOURCE safety/privacy fact (see module docstring): no durable
#: Safety/Privacy authority exists in P3-1A, so the applicable-profile
#: fact is an explicit ALLOW-by-absence. Wiring the real BF-05 view is a
#: later slice; this constant is the single place the policy is named.
SAFETY_PRIVACY_NO_SOURCE = "ALLOW"

#: NO_SOURCE suppression fact (see module docstring): TeachingPreference /
#: PlannerConstraint are Phase 6/7 tables; no durable suppression source
#: exists in P3-1A, and an absent source never blocks a user's request.
TARGET_SUPPRESSED_NO_SOURCE = False

#: allowed value sets of the critical facts (BF-03 v1.1 reference sets).
_AUTHORIZATION_STATUSES = ("VALID", "INVALIDATED", "UNKNOWN")
_SUBJECT_STATUSES = ("ACTIVE", "CANCELLED", "SUPERSEDED", "UNKNOWN")
_SAFETY_PRIVACY_STATUSES = ("ALLOW", "BLOCK", "UNKNOWN")
_LOCK_STATES = ("NONE", "OWNED_BY_THIS_MOMENT", "OWNED_BY_OTHER", "UNKNOWN")
_GATE_STATE_STATUSES = ("COMPLETE", "INCOMPLETE")
_SNAPSHOT_STATUSES = ("VALID", "UNKNOWN")


class GateInputError(ValueError):
    """BF-03 §21 contract error: the caller violated the Gate interface.
    Neither a DENY nor a DEGRADED — a program error."""


@dataclass(frozen=True)
class EnvFactsNoSource:
    """The two NO_SOURCE environment facts, as a type — so a reader sees
    "no durable source" instead of a bare constant at every call site."""

    safety_privacy_status: str = SAFETY_PRIVACY_NO_SOURCE
    target_suppressed: bool = TARGET_SUPPRESSED_NO_SOURCE


@dataclass(frozen=True)
class UserInitiatedOpenFacts:
    """One USER_INITIATED OPEN fact bundle.

    Identity/context fields come first, then the critical facts whose
    UNKNOWN-ness degrades the Gate. Defaults describe the healthy path;
    the NO_SOURCE environment facts default to their explicit
    no-source values (see the constants above) — a caller that has a real
    authority overrides them, it never "fills in" a guess.
    """

    decision_cycle_id: str
    candidate_id: str
    proposed_action: str = "OPENING"
    gate_context: str = "OPEN"
    authorization_path: str = "USER_INITIATED"
    authorization_basis: str = "DECISION_CYCLE"
    user_intent_scope: str = "TARGETED_LEARNING_REQUEST"

    authorization_status: str = "VALID"
    subject_status: str = "ACTIVE"
    target_status: str = "VALID"
    content_status: str = "VALID"
    lock_state: str = "NONE"
    learning_snapshot_status: str = "VALID"
    gate_state_status: str = "COMPLETE"
    safety_privacy_status: str = SAFETY_PRIVACY_NO_SOURCE
    target_suppressed: bool = TARGET_SUPPRESSED_NO_SOURCE


@dataclass(frozen=True)
class GateVerdict:
    """The Gate's output (docs/DATA_MODEL.md §14.1).

    ``execution_status=SUCCEEDED`` pairs with ``decision`` ALLOW or DENY;
    ``execution_status=DEGRADED`` always carries ``decision=None`` and the
    ``missing_or_unknown`` fact keys — never a synthetic DENY.
    """

    execution_status: str
    decision: str | None
    primary_reason: str | None
    reasons: tuple[str, ...]
    missing_or_unknown: tuple[str, ...]
    policy_version: str = GATE_POLICY_VERSION

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOW"


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise GateInputError(message)


def _validate(facts: UserInitiatedOpenFacts) -> None:
    _check(facts.gate_context in GATE_CONTEXTS, "invalid gate_context")
    _check(
        facts.proposed_action in OPEN_ACTIONS,
        "USER_INITIATED OPEN requires the OPENING action",
    )
    _check(
        facts.authorization_path == "USER_INITIATED",
        "this profile decides USER_INITIATED authorization paths only",
    )
    _check(
        facts.authorization_basis == "DECISION_CYCLE",
        "OPEN requires DECISION_CYCLE authorization basis (BF-03 §3)",
    )
    _check(
        facts.gate_context == "OPEN",
        "this profile decides the OPEN context only (continuation is P3-1B)",
    )
    _check(bool(facts.decision_cycle_id), "OPEN requires a decision cycle")
    _check(bool(facts.candidate_id), "OPEN requires a selected candidate")
    _check(
        facts.user_intent_scope in USER_INTENT_SCOPES,
        f"invalid user_intent_scope: {facts.user_intent_scope}",
    )
    for name, value, allowed in (
        (
            "authorization_status",
            facts.authorization_status,
            _AUTHORIZATION_STATUSES,
        ),
        ("subject_status", facts.subject_status, _SUBJECT_STATUSES),
        ("target_status", facts.target_status, TARGET_STATUSES),
        ("content_status", facts.content_status, CONTENT_STATUSES),
        (
            "safety_privacy_status",
            facts.safety_privacy_status,
            _SAFETY_PRIVACY_STATUSES,
        ),
        ("lock_state", facts.lock_state, _LOCK_STATES),
        (
            "learning_snapshot_status",
            facts.learning_snapshot_status,
            _SNAPSHOT_STATUSES,
        ),
        ("gate_state_status", facts.gate_state_status, _GATE_STATE_STATUSES),
    ):
        _check(value in allowed, f"invalid {name}: {value}")


def _critical_unknown(facts: UserInitiatedOpenFacts) -> tuple[str, ...]:
    """Critical-state completeness, mapped to the §14.1 fact keys.

    Deterministic (sorted) emission, exactly like the frozen reference's
    ``sorted(set(unknown))``.
    """

    unknown: list[str] = []
    if facts.learning_snapshot_status == "UNKNOWN":
        unknown.append("LEARNING_SNAPSHOT")
    if facts.authorization_status == "UNKNOWN":
        unknown.append("AUTHORIZATION_STATUS")
    if facts.target_status == "UNKNOWN":
        unknown.append("TARGET_VALIDITY")
    if facts.content_status == "UNKNOWN":
        unknown.append("CONTENT_VALIDITY")
    if facts.lock_state == "UNKNOWN":
        unknown.append("LOCK_STATE")
    if facts.safety_privacy_status == "UNKNOWN":
        unknown.append("SAFETY_PRIVACY_STATUS")
    if facts.subject_status == "UNKNOWN":
        unknown.append("SUBJECT_STATUS")
    if facts.gate_state_status == "INCOMPLETE":
        unknown.append("GATE_STATE")
    return tuple(sorted(set(unknown)))


def decide_user_initiated_open(facts: UserInitiatedOpenFacts) -> GateVerdict:
    """Decide one USER_INITIATED OPEN (BF-03 v1.1 semantics).

    Order (frozen): contract validation → critical-state completeness →
    the six applicable check families in BF-03 decision order → deny
    precedence ordering → ALLOW.
    """

    _validate(facts)

    unknown = _critical_unknown(facts)
    if unknown:
        return GateVerdict(
            execution_status="DEGRADED",
            decision=None,
            primary_reason=None,
            reasons=(),
            missing_or_unknown=unknown,
        )

    reasons: list[str] = []
    if facts.safety_privacy_status == "BLOCK":
        reasons.append("SAFETY_PRIVACY_BLOCK")
    if facts.subject_status == "CANCELLED":
        reasons.append("ACTION_CANCELLED")
    if facts.subject_status == "SUPERSEDED":
        reasons.append("ACTION_SUPERSEDED")
    if facts.authorization_status == "INVALIDATED":
        reasons.append("AUTHORIZATION_INVALID")
    if facts.target_status in {"INVALID", "DEPRECATED", "MISSING"}:
        reasons.append("TARGET_INVALID")
    if facts.content_status == "INVALID":
        reasons.append("CONTENT_INVALID")
    if facts.target_suppressed:
        reasons.append("TARGET_SUPPRESSED")
    if facts.user_intent_scope not in USER_INITIATED_OPEN_INTENTS:
        reasons.append("USER_INTENT_BLOCK")
    if facts.lock_state in {"OWNED_BY_OTHER", "OWNED_BY_THIS_MOMENT"}:
        reasons.append("TEACHING_LOCK_CONFLICT")

    ordered = tuple(reason for reason in DENY_PRECEDENCE if reason in set(reasons))
    if ordered:
        return GateVerdict(
            execution_status="SUCCEEDED",
            decision="DENY",
            primary_reason=ordered[0],
            reasons=ordered,
            missing_or_unknown=(),
        )
    return GateVerdict(
        execution_status="SUCCEEDED",
        decision="ALLOW",
        primary_reason=None,
        reasons=(),
        missing_or_unknown=(),
    )


def with_lock_state(
    facts: UserInitiatedOpenFacts, lock_state: str
) -> UserInitiatedOpenFacts:
    """Convenience: the same bundle with an observed lock state — the one
    fact the caller reads from the durable lock row before deciding."""

    return replace(facts, lock_state=lock_state)
