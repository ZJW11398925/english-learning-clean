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
  are bypassed by a user-initiated request in BF-03 v1.1 (§12/§13/§16/§17).

The AUTOMATIC branch of the Gate is **implemented** (Phase 8 P8-1) as two
more profiles of this same pure module:
:class:`AutomaticOpenFacts` / :func:`decide_automatic_open` (the
planner-authorized OPEN: the planner facts are *inputs* the caller read off
the durable run — this profile never re-decides the selection and never
fabricates a PlannerDecision) and :class:`AutoContinuationFacts` /
:func:`decide_auto_continuation` (the unsolicited mid-moment continuation,
which is the one path the auto-teach preference and flow protection still
guard when the moment itself was auto-opened). Both reproduce the frozen
reference's automatic branch word for word; the two USER_INITIATED
profiles above are untouched by that addition (their fact sets, defaults
and refusals are unchanged).

NO_SOURCE facts (P3-1A, docstring-flagged, never fabricated):

- safety/privacy: the BF-05 Safety/Privacy contract and its durable
  authority do not exist yet, so the fact is assembled as an explicit
  ``ALLOW`` from an explicit *absence of source* — the constant
  :data:`SAFETY_PRIVACY_NO_SOURCE` documents that this is "no authority
  said BLOCK", not "an authority said it is safe". Datasource wiring lands
  with the authority (later slice).
- suppression: the §9 objects (TeachingPreference / PlannerConstraint,
  docs/DATA_MODEL.md §9) are **durable since migration 0013** (P6-0 for
  the preference rows, P6-3 for the constraint rows) — the tables exist.
  What this module still does not have is a durable read face to hand it
  an *applied* suppression fact at this call site, so
  :data:`TARGET_SUPPRESSED_NO_SOURCE` = False keeps the same honest
  NO_SOURCE meaning: "no authority said suppressed", not "an authority
  said it is teachable". The constraint's consumption is the Planner's
  (P7-2 marks a candidate; the Gate's own fact stays declared).

Both are deterministic (never UNKNOWN) precisely because an absent source
must not degrade a user's explicit request; the trace stays truthful via
this docstring and the constants.

Critical-state completeness: the eight fact keys of the opening profiles —
LEARNING_SNAPSHOT, AUTHORIZATION_STATUS, TARGET_VALIDITY,
CONTENT_VALIDITY, LOCK_STATE, SAFETY_PRIVACY_STATUS, SUBJECT_STATUS,
GATE_STATE (docs/DATA_MODEL.md §14.1 ``missing_or_unknown[]``). Any
UNKNOWN fact yields ``GateExecutionStatus=DEGRADED`` with no GateDecision.
``missing_or_unknown`` is emitted in the frozen reference's deterministic
(sorted) order. The continuation profiles carry the same facts **minus
the learning snapshot** (seven keys, the BF-03 v1.1 cross-layer repair:
an active moment's own new Evidence does not invalidate its
continuation).

Contract errors (BF-03 §21) raise :class:`GateInputError`: calling the
Gate with an invalid context/action/enum is a program error, not a
decision — it is never DENY and never DEGRADED.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from elc.teaching.targets import CONTENT_STATUSES, TARGET_STATUSES

__all__ = [
    "AUTOMATIC_OPEN_FACT_KEYS",
    "AUTOMATIC_OPEN_REASON_CODES",
    "AUTO_CONTINUATION_FACT_KEYS",
    "AUTO_CONTINUATION_REASON_CODES",
    "CONTINUATION_ACTIONS",
    "CONTINUATION_REASON_CODES",
    "DENY_PRECEDENCE",
    "GATE_CONTEXTS",
    "GATE_POLICY_VERSION",
    "MISSING_OR_UNKNOWN_FACT_KEYS",
    "OPEN_ACTIONS",
    "SAFETY_PRIVACY_NO_SOURCE",
    "TARGET_SUPPRESSED_NO_SOURCE",
    "USER_INITIATED_CONTINUATION_INTENTS",
    "USER_INITIATED_OPEN_INTENTS",
    "USER_INITIATED_OPEN_REASON_CODES",
    "USER_INTENT_SCOPES",
    "AutoContinuationFacts",
    "AutomaticOpenFacts",
    "ContinuationFacts",
    "EnvFactsNoSource",
    "GateInputError",
    "GateVerdict",
    "UserInitiatedOpenFacts",
    "decide_auto_continuation",
    "decide_automatic_open",
    "decide_user_initiated_open",
    "decide_user_requested_continuation",
    "with_lock_state",
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
#: PlannerConstraint are **durable since migration 0013** (the tables
#: exist); what is absent at this call site is a durable *read* of an
#: applied suppression, and an absent source never blocks a user's request.
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


class _CarriedFacts(Protocol):
    """The typed face of "a fact bundle of this module": the fields the four
    profiles share, which is what the shared validators below may touch.

    A structural Protocol with read-only members (every bundle is a frozen
    dataclass) rather than a base class: the two original bundles are
    frozen against their Phase 3 tests (a base class would change their MRO
    and their field order), and the two automatic bundles need no shared
    state — only shared *checks*.
    """

    @property
    def proposed_action(self) -> str: ...
    @property
    def authorization_basis(self) -> str: ...
    @property
    def authorization_status(self) -> str: ...
    @property
    def subject_status(self) -> str: ...
    @property
    def target_status(self) -> str: ...
    @property
    def content_status(self) -> str: ...
    @property
    def lock_state(self) -> str: ...
    @property
    def learning_snapshot_status(self) -> str: ...
    @property
    def gate_state_status(self) -> str: ...
    @property
    def safety_privacy_status(self) -> str: ...


class _OpeningCarriedFacts(_CarriedFacts, Protocol):
    """A bundle the opening contract applies to: the shared facts plus the
    two identity fields the two OPEN profiles carry identically.

    ``decision_cycle_id``/``candidate_id`` are the §15 names; the automatic
    bundle exposes ``selected_candidate_id`` as the §14 decision column's
    spelling of the same selection (checked by
    :class:`_PlannerAuthorizedOpeningFacts`).
    """

    @property
    def decision_cycle_id(self) -> str: ...
    @property
    def candidate_id(self) -> str: ...


class _PlannerAuthorizedOpeningFacts(_OpeningCarriedFacts, Protocol):
    """An **AUTOMATIC** opening's bundle: the planner half of the contract
    is a *fact the caller read from the durable run*, so the planner fields
    are part of the type — and, with them, the *absence* of an existing
    moment (``moment_id`` is ``None``: an opening starts one) and the
    ``user_initiated`` flag that must be false on this path.

    The USER_INITIATED bundle does not match this Protocol — which is
    exactly the Phase 3 specialization, now expressed in the type system
    rather than only in a docstring (that bundle carries neither planner
    field nor the flag: its authorization path *is* the request).
    """

    @property
    def moment_id(self) -> str | None: ...
    @property
    def selected_candidate_id(self) -> str: ...
    @property
    def user_initiated(self) -> bool: ...
    @property
    def planner_execution_status(self) -> str: ...
    @property
    def planner_decision(self) -> str: ...


class _ContinuationCarriedFacts(_CarriedFacts, Protocol):
    """A bundle the continuation contract applies to: the shared facts plus
    the one field the continuation lifecycle check reads (its own
    ``moment_state``)."""

    @property
    def moment_state(self) -> str: ...


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise GateInputError(message)


def _check_fact_values(facts: _CarriedFacts) -> None:
    """The five critical facts every profile carries, plus the gate-state
    status and the learning-snapshot status an opening carries.

    The allowed sets are the frozen BF-03 v1.1 reference's own sets, and the
    order is the order the reference checks them in — shared by all four
    profiles so one spelling of "invalid lock_state" cannot drift from
    another.

    P8-1 hoisted this loop out of the two original validators. What that
    preserved and what it did not: the **refusal class and the decision face
    are unchanged** (the same :class:`GateInputError`; every profile's verdict
    is byte-for-byte what it was — re-checked against the pre-cut revision on
    the clean, multi-blocker and DEGRADED bundles), but which contract error a
    **multi-fault** input reports first can differ, because the two original
    validators interleaved these checks differently. The P8-1 review found 23
    such combinations among 231 two-fault pairs; an independent re-run over
    this profile's 15 single-fault candidates (the pre-cut file loaded beside
    the current one) finds 4 of 105 pairs whose first-reported message flips —
    e.g. an empty ``decision_cycle_id`` plus a bad ``user_intent_scope``: the
    cycle error used to win, the scope error does now. Nothing pinned those
    messages, and a single-fault input reports the same error as before.
    """

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


def _check_opening_facts(facts: _OpeningCarriedFacts) -> None:
    """The BF-03 v1.1 opening contract both OPEN profiles share: the
    DECISION_CYCLE basis, the OPENING action, and a non-empty decision
    cycle and selected candidate.

    The two profiles differ in exactly the checks they perform themselves:
    the authorization path's word, the user-intent scope their path
    requires, the ``user_initiated`` flag that agrees with the path, and —
    for the automatic path only — the planner half of the contract
    (:func:`_check_planner_authorized_open`).
    """

    _check(
        facts.authorization_basis == "DECISION_CYCLE",
        "OPEN requires DECISION_CYCLE authorization basis (BF-03 §3)",
    )
    _check(facts.proposed_action == "OPENING", "OPEN requires the OPENING action")
    _check(bool(facts.decision_cycle_id), "OPEN requires a decision cycle")
    _check(bool(facts.candidate_id), "OPEN requires a selected candidate")


def _check_planner_authorized_open(
    facts: _PlannerAuthorizedOpeningFacts,
) -> None:
    """The automatic opening's planner half: the run the caller read
    succeeded and **selected**, the selection is non-empty, and no moment
    exists yet (an opening starts one — the frozen reference's
    ``moment_id is None`` check).

    The user-initiated bundle never sees these checks: it has no planner
    fields to check and its own validator carries the path's requirements.
    """

    _check(
        facts.planner_execution_status == "SUCCEEDED",
        "OPEN requires successful Planner execution",
    )
    _check(
        facts.planner_decision == "SELECT",
        "OPEN requires Planner SELECT",
    )
    _check(
        bool(facts.selected_candidate_id),
        "OPEN requires selected candidate",
    )
    _check(
        facts.moment_id is None,
        "OPEN must not have existing moment_id",
    )
    _check(
        not facts.user_initiated,
        "automatic OPEN cannot be user_initiated",
    )


def _opening_unknown_facts(facts: _CarriedFacts) -> tuple[str, ...]:
    """Critical-state completeness of the opening profiles, keyed by the
    §14.1 fact keys in a fixed order; callers sort the result exactly like
    the frozen reference's ``sorted(set(unknown))``."""

    return tuple(
        key
        for key, status in (
            ("LEARNING_SNAPSHOT", facts.learning_snapshot_status),
            ("AUTHORIZATION_STATUS", facts.authorization_status),
            ("TARGET_VALIDITY", facts.target_status),
            ("CONTENT_VALIDITY", facts.content_status),
            ("LOCK_STATE", facts.lock_state),
            ("SAFETY_PRIVACY_STATUS", facts.safety_privacy_status),
            ("SUBJECT_STATUS", facts.subject_status),
        )
        if status == "UNKNOWN"
    ) + ("GATE_STATE",) * (1 if facts.gate_state_status == "INCOMPLETE" else 0)


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
        facts.gate_context == "OPEN",
        "this profile decides the OPEN context only (continuation is P3-1B)",
    )
    _check(
        facts.user_intent_scope in USER_INTENT_SCOPES,
        f"invalid user_intent_scope: {facts.user_intent_scope}",
    )
    _check_opening_facts(facts)
    _check_fact_values(facts)


def _critical_unknown(facts: UserInitiatedOpenFacts) -> tuple[str, ...]:
    """Critical-state completeness, mapped to the §14.1 fact keys.

    Deterministic (sorted) emission, exactly like the frozen reference's
    ``sorted(set(unknown))``.
    """

    return tuple(sorted(set(_opening_unknown_facts(facts))))


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


# ---------------------------------------------------------------------------
# USER_REQUESTED_CONTINUE — the continuation profile (Phase 3 P3-1B).
# ---------------------------------------------------------------------------

#: The proposed actions a continuation may carry (the frozen reference's
#: ACTIONS minus OPENING, plus the closing feedback move).
CONTINUATION_ACTIONS = ("HINT", "RETRY", "EXPLANATION", "REVEAL", "TERMINAL_FEEDBACK")

#: The one user-intent scope a continuation is authorized by (BF-03 §11
#: continuation branch: ``ui != ACTIVE_TEACHING_CONTINUATION`` blocks).
USER_INITIATED_CONTINUATION_INTENTS = ("ACTIVE_TEACHING_CONTINUATION",)

#: The DENY codes the USER_REQUESTED_CONTINUE profile can emit, in
#: precedence order. HARD_ATTEMPT_LIMIT / HARD_TEACHING_TURN_LIMIT are the
#: two hard-flow-protection codes the frozen reference evaluates exactly
#: here (§8 "user-requested continue 不绕过 hard cap").
CONTINUATION_REASON_CODES = tuple(
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
        "TEACHING_LOCK_INVALID",
        "MOMENT_NOT_CONTINUABLE",
        "HARD_ATTEMPT_LIMIT",
        "HARD_TEACHING_TURN_LIMIT",
    }
)

#: The matchable moment lifecycle state of a continuation (the frozen
#: reference's ``moment_state == "DECIDING_NEXT_ACTION"`` check).
CONTINUATION_MOMENT_STATE = "DECIDING_NEXT_ACTION"


@dataclass(frozen=True)
class ContinuationFacts:
    """One USER_REQUESTED_CONTINUE fact bundle (BF-03 v1.1 continuation
    branch, ``authorization_basis = ACTIVE_MOMENT``, TASK-…2.2 ⑥⑦).

    Identity/context fields first, then the critical facts whose
    UNKNOWN-ness degrades the Gate, exactly like the OPEN bundle. The four
    continuation-only fields carry the frozen reference's own facts:

    - ``moment_state`` — the live moment's lifecycle state (a continuation
      only exists while the moment is DECIDING_NEXT_ACTION);
    - ``hard_attempt_limit_exhausted`` / ``hard_teaching_turn_limit_exhausted``
      — the §8 hard caps, computed from the durable counts
      (elc.teaching.limits.TeachingLoad);
    - ``terminalizing_action`` / ``retry_like_action`` — the proposed
      move's class, which is what turns a hard cap into a DENY instead of
      a blanket stop (the §8 exemption).
    """

    moment_id: str
    decision_cycle_id: str | None = None
    candidate_id: str = ""
    proposed_action: str = "HINT"
    gate_context: str = "USER_REQUESTED_CONTINUE"
    authorization_path: str = "USER_INITIATED"
    authorization_basis: str = "ACTIVE_MOMENT"
    user_intent_scope: str = "ACTIVE_TEACHING_CONTINUATION"
    continuation_requested: bool = True

    authorization_status: str = "VALID"
    subject_status: str = "ACTIVE"
    target_status: str = "VALID"
    content_status: str = "VALID"
    lock_state: str = "OWNED_BY_THIS_MOMENT"
    moment_state: str = CONTINUATION_MOMENT_STATE
    learning_snapshot_status: str = "VALID"
    gate_state_status: str = "COMPLETE"
    safety_privacy_status: str = SAFETY_PRIVACY_NO_SOURCE
    target_suppressed: bool = TARGET_SUPPRESSED_NO_SOURCE

    hard_attempt_limit_exhausted: bool = False
    hard_teaching_turn_limit_exhausted: bool = False


def _validate_continuation(facts: ContinuationFacts) -> None:
    _check(
        facts.gate_context == "USER_REQUESTED_CONTINUE",
        "this profile decides the USER_REQUESTED_CONTINUE context only"
        " (AUTO_CONTINUE is decide_auto_continuation)",
    )
    _check(
        facts.proposed_action in CONTINUATION_ACTIONS,
        f"invalid continuation action: {facts.proposed_action}",
    )
    _check(
        facts.authorization_path == "USER_INITIATED",
        "a user-requested continuation is a user-initiated path",
    )
    _check(
        facts.authorization_basis == "ACTIVE_MOMENT",
        "continuation requires ACTIVE_MOMENT authorization basis (BF-03"
        " §3 cross-layer v1.1)",
    )
    _check(bool(facts.moment_id), "continuation requires moment_id")
    _check(
        facts.continuation_requested,
        "USER_REQUESTED_CONTINUE requires continuation_requested",
    )
    _check(
        facts.user_intent_scope in USER_INTENT_SCOPES,
        f"invalid user_intent_scope: {facts.user_intent_scope}",
    )
    _check_fact_values(facts)


def _continuation_unknown_facts(
    facts: _ContinuationCarriedFacts,
) -> tuple[str, ...]:
    """Critical-state completeness of the continuation profiles, keyed by
    the §14.1 fact keys (the same seven as the opening profiles minus
    LEARNING_SNAPSHOT — the BF-03 v1.1 cross-layer repair)."""

    return tuple(
        key
        for key, status in (
            ("AUTHORIZATION_STATUS", facts.authorization_status),
            ("TARGET_VALIDITY", facts.target_status),
            ("CONTENT_VALIDITY", facts.content_status),
            ("LOCK_STATE", facts.lock_state),
            ("SAFETY_PRIVACY_STATUS", facts.safety_privacy_status),
            ("SUBJECT_STATUS", facts.subject_status),
        )
        if status == "UNKNOWN"
    ) + ("GATE_STATE",) * (1 if facts.gate_state_status == "INCOMPLETE" else 0)


def _continuation_unknown(facts: ContinuationFacts) -> tuple[str, ...]:
    """Critical-state completeness for the continuation profile.

    Same six critical facts as the OPEN profile: a continuation is
    authorized by the ACTIVE_MOMENT lineage, so the Learning snapshot is
    NOT one of its critical facts (STATE_MACHINES §12.1: an active moment
    committing new Attempt Evidence moves the watermark without
    invalidating its own continuation). The snapshot fact therefore never
    degrades a continuation.
    """

    return tuple(sorted(set(_continuation_unknown_facts(facts))))


def decide_user_requested_continuation(facts: ContinuationFacts) -> GateVerdict:
    """Decide one USER_REQUESTED_CONTINUE (BF-03 v1.1 continuation branch,
    behavioral_baselines/gate/teaching_gate_reference_v1_1.py lines
    154-184, reproduced for the user-requested path).

    Order (frozen): contract validation → critical-state completeness →
    the applicable check families in BF-03 decision order → deny
    precedence ordering → ALLOW. The two §8 hard-cap rules fire exactly as
    the reference has them: HARD_ATTEMPT_LIMIT on retry-like moves,
    HARD_TEACHING_TURN_LIMIT on non-terminalizing moves.
    """

    _validate_continuation(facts)

    unknown = _continuation_unknown(facts)
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
    if facts.user_intent_scope not in USER_INITIATED_CONTINUATION_INTENTS:
        reasons.append("USER_INTENT_BLOCK")
    if facts.lock_state == "OWNED_BY_OTHER":
        reasons.append("TEACHING_LOCK_CONFLICT")
    elif facts.lock_state != "OWNED_BY_THIS_MOMENT":
        reasons.append("TEACHING_LOCK_INVALID")
    if facts.moment_state != CONTINUATION_MOMENT_STATE:
        reasons.append("MOMENT_NOT_CONTINUABLE")

    retry_like = facts.proposed_action in {"RETRY", "HINT"}
    terminalizing = facts.proposed_action in {"REVEAL", "TERMINAL_FEEDBACK"}
    if facts.hard_attempt_limit_exhausted and retry_like:
        reasons.append("HARD_ATTEMPT_LIMIT")
    if facts.hard_teaching_turn_limit_exhausted and not terminalizing:
        reasons.append("HARD_TEACHING_TURN_LIMIT")

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


# ---------------------------------------------------------------------------
# The AUTOMATIC branch — Phase 8 P8-1 (BF-03 v1.1 automatic profiles).
# ---------------------------------------------------------------------------
#
# Two profiles, one per automatic gate context:
#
# - AUTOMATIC OPEN: the Planner already judged worth-teaching (SUCCEEDED +
#   SELECT) and the Runtime asks the Gate whether the *unsolicited*
#   interruption may execute now. The planner facts therefore arrive as
#   fields of the fact bundle — they are this profile's **input**, read off
#   the durable run (docs/DATA_MODEL.md §14) — and the profile refuses a
#   bundle that does not carry them rather than inventing a selection.
# - AUTO_CONTINUE: the runtime advances an *auto-opened* active moment
#   without the user having asked. This is the one continuation the
#   auto-teach preference and the conversation-flow protection still guard
#   (BF-03 §12/§16/§17); a continuation the user requested is
#   USER_INITIATED and keeps its own profile above, unaffected.
#
# Both reproduce behavioral_baselines/gate/teaching_gate_reference_v1_1.py
# (the frozen oracle, never imported) word for word, including the two
# asymmetries the reference carries on purpose: the automatic controls
# block only *new* automatic openings (budget / cooldown: BF-03 §16/§17 —
# neither blocks a continuation), and the flow protection fires on
# ``(OPEN ∧ AUTOMATIC) or AUTO_CONTINUE`` while a USER_REQUESTED_CONTINUE
# bypasses it (BF-03 §12: an explicit request is not an interruption).
#
# Control facts are **caller-declared**, with their authorities registered
# below (the same posture the frozen reference has: it consumes the facts
# and never asks where they come from). Declared authorities and their
# revisit conditions:
#
# 1. ``automatic_teaching_enabled`` ← the product mode (Balanced /
#    Study-first / Lounge, docs/PRODUCT_CONTRACT.md §5) crossed with the
#    rollout stage (docs/IMPLEMENTATION_PLAN.md §12). The repository **does**
#    derive this fact today, and the derivation is named here so a wiring cut
#    cannot miss it: the Planner's §5.1 assembly maps the durable
#    ``teaching_frequency`` column onto BF-02's three profiles and carries
#    the switch with it —
#    ``planner/feature_assembly.py:254``'s
#    ``TEACHING_FREQUENCY_TO_PROFILE`` (``OFF`` ⇒
#    ``automatic_teaching_enabled=False``), read through the
#    ``TeachingPolicyPort`` of ``planner/feature_assembly.py:768`` (satisfied
#    structurally by the durable §5.1 row ``TeachingPolicyProfile``,
#    migration 0011), copied into the ``FeatureAuthority`` at
#    ``planner/feature_assembly.py:717`` and traced by
#    ``planner/kernel.py:1779``. What this module does not have is a read
#    face at its own call site, so the fact stays the caller's declaration —
#    and the wiring cuts (p8-4 / p8-5) **must pass the Planner's assembled
#    value**, or a user whose durable policy turned automatic teaching off
#    could still be taught automatically. The LOUNGE profile only raises the
#    activation threshold (BF-02 §13's +0 row); it is **not** a substitute
#    for the ``AUTO_TEACH_DISABLED`` DENY. Revisit: p8-5 (rollout gate)
#    lands the durable read face for this fact's caller; p8-4 passes the
#    Planner's value.
# 2. ``hard_protected_flow`` ← docs/DOMAIN_MODEL.md §13's
#    ConversationPriorityView.flow_priority == "PROTECTED" (the same view
#    P7-2 assembled). This module does not read that view: the derivation
#    belongs to whoever assembles the turn's facts. Revisit: the cut that
#    wires the automatic path into a turn (p8-4), which must either
#    pass the derived fact or name why it cannot.
# 3. ``automatic_session_budget_exhausted`` / ``hard_cooldown_active`` ←
#    the SessionBudgetView (docs/DOMAIN_MODEL.md §13: TeachingPolicyProfile
#    + Runtime Session State). P8-2 landed that view and its production face
#    (``TeachingController.get_session_budget_view``); this profile still
#    consumes the **injected** control facts and derives nothing itself.
#    Revisit: the wiring cut (p8-4 / p8-5) decides who assembles the fact
#    inside a turn — there is no caller today.
# 4. ``moment_consent_class`` (``AUTO_OPENED`` / ``USER_AUTHORIZED``) is
#    the frozen reference's own word for *how the active moment came to
#    be*; it is not a column of docs/DATA_MODEL.md §15. Until canonical or
#    a later cut gives it a durable carrier, this profile takes a declared
#    ``moment_consent_class`` field whose value a caller derives from the
#    moment's §15 ``source``: ``AUTOMATIC`` ⟹ ``AUTO_OPENED``, anything
#    else (USER_INITIATED / MANUAL_FOCUS / SCHEDULED_STUDY) ⟹
#    ``USER_AUTHORIZED`` — :func:`moment_consent_class_of` spells that
#    reading once, here, so the derivation is not re-invented per caller.
#    Revisit: canonical names the carrier, or a cut gives the word a
#    durable column.

#: The §14.1 fact keys an **AUTOMATIC OPEN** reports as
#: ``missing_or_unknown`` — deliberately the same eight as the
#: USER_INITIATED OPEN profile (same context, same execution facts, plus
#: the repo-native LEARNING_SNAPSHOT the phase-3 profile registered).
AUTOMATIC_OPEN_FACT_KEYS = (
    "LEARNING_SNAPSHOT",
    "AUTHORIZATION_STATUS",
    "TARGET_VALIDITY",
    "CONTENT_VALIDITY",
    "LOCK_STATE",
    "SAFETY_PRIVACY_STATUS",
    "SUBJECT_STATUS",
    "GATE_STATE",
)

#: The §14.1 fact keys an **AUTO_CONTINUE** reports — the seven of the
#: continuation profiles (no LEARNING_SNAPSHOT: BF-03 v1.1's cross-layer
#: repair says an active moment's own new Evidence must not invalidate its
#: continuation; the frozen reference's ``_critical_unknown`` checks the
#: same six facts plus the gate state).
AUTO_CONTINUATION_FACT_KEYS = (
    "AUTHORIZATION_STATUS",
    "TARGET_VALIDITY",
    "CONTENT_VALIDITY",
    "LOCK_STATE",
    "SAFETY_PRIVACY_STATUS",
    "SUBJECT_STATUS",
    "GATE_STATE",
)

#: The DENY codes the AUTOMATIC OPEN profile can emit, in precedence order.
#: AUTO_TEACH_DISABLED / HARD_PROTECTED_FLOW /
#: AUTO_SESSION_BUDGET_EXHAUSTED / HARD_COOLDOWN_ACTIVE are the four
#: automatic-only controls this path does *not* bypass; the two hard
#: attempt/turn caps and the two continuation lifecycle codes belong to the
#: continuation contexts (they stay vocabulary-only here, like the
#: USER_INITIATED OPEN profile's counterparts).
AUTOMATIC_OPEN_REASON_CODES = tuple(
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
        "AUTO_TEACH_DISABLED",
        "TEACHING_LOCK_CONFLICT",
        "HARD_PROTECTED_FLOW",
        "AUTO_SESSION_BUDGET_EXHAUSTED",
        "HARD_COOLDOWN_ACTIVE",
    }
)

#: The DENY codes the AUTO_CONTINUE profile can emit, in precedence order.
#: AUTO_TEACH_DISABLED fires only for an ``AUTO_OPENED`` moment (a
#: user-authorized episode keeps going: BF-03 §17), HARD_PROTECTED_FLOW
#: fires here too (§12), and the two hard caps are the §8 continuation
#: rules. AUTO_SESSION_BUDGET_EXHAUSTED / HARD_COOLDOWN_ACTIVE are absent
#: on purpose: the frozen reference evaluates them for new openings only.
AUTO_CONTINUATION_REASON_CODES = tuple(
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
        "AUTO_TEACH_DISABLED",
        "TEACHING_LOCK_CONFLICT",
        "TEACHING_LOCK_INVALID",
        "MOMENT_NOT_CONTINUABLE",
        "HARD_PROTECTED_FLOW",
        "HARD_ATTEMPT_LIMIT",
        "HARD_TEACHING_TURN_LIMIT",
    }
)

#: BF-03's moment-consent words (see declared authority 4 above).
_MOMENT_CONSENT_CLASSES = ("AUTO_OPENED", "USER_AUTHORIZED")

#: docs/DATA_MODEL.md §15 source vocabulary, as the consent derivation
#: reads it (declared authority 4). Re-declared as data rather than
#: imported from elc.teaching.types: this module's only import is the
#: target-status vocabulary, and the §15 set is what the derivation's
#: refusal has to spell.
_MOMENT_SOURCES = ("AUTOMATIC", "USER_INITIATED", "MANUAL_FOCUS", "SCHEDULED_STUDY")


def moment_consent_class_of(moment_source: str) -> str:
    """The declared reading of BF-03's ``moment_consent_class`` off the
    moment's §15 ``source`` (declared authority 4 in the section header).

    ``AUTOMATIC`` ⟹ ``AUTO_OPENED``; every other source word — an episode
    the user started, opened from a manual focus or as scheduled study —
    ⟹ ``USER_AUTHORIZED``. An unknown source word is a contract error, not
    a guess: the caller passes a §15 vocabulary word.
    """

    _check(
        moment_source in _MOMENT_SOURCES,
        f"invalid moment source: {moment_source}",
    )
    return "AUTO_OPENED" if moment_source == "AUTOMATIC" else "USER_AUTHORIZED"


@dataclass(frozen=True)
class AutomaticOpenFacts:
    """One AUTOMATIC OPEN fact bundle (BF-03 v1.1, ``authorization_path =
    AUTOMATIC``, ``user_initiated = False``).

    Identity/context fields first; then the **planner facts this profile
    consumes as inputs** (never re-derived: the run that produced them is
    durable, docs/DATA_MODEL.md §14); then the critical facts whose
    UNKNOWN-ness degrades the Gate; then the controls an automatic opening
    (and only an automatic opening) must pass.

    ``candidate_id`` is the Planner's selected candidate under §15's name
    (``selected_candidate_id`` is the §14 decision column's name for the
    same value — exposed below as a read-only alias so a caller holding the
    durable decision does not have to translate).

    Defaults describe the healthy path, exactly like the two original
    bundles. The controls default to the value that *permits* the action
    (``automatic_teaching_enabled=True``, ``hard_protected_flow=False``,
    ``automatic_session_budget_exhausted=False``,
    ``hard_cooldown_active=False``), which is the frozen reference's own
    default set — the default is a declared healthy environment, not a
    claim about the product mode (declared authorities 1–3 above).
    """

    decision_cycle_id: str
    candidate_id: str
    planner_execution_status: str = "SUCCEEDED"
    planner_decision: str = "SELECT"
    proposed_action: str = "OPENING"
    gate_context: str = "OPEN"
    authorization_path: str = "AUTOMATIC"
    authorization_basis: str = "DECISION_CYCLE"
    user_intent_scope: str = "OPEN"
    user_initiated: bool = False
    moment_id: str | None = None

    authorization_status: str = "VALID"
    subject_status: str = "ACTIVE"
    target_status: str = "VALID"
    content_status: str = "VALID"
    lock_state: str = "NONE"
    learning_snapshot_status: str = "VALID"
    gate_state_status: str = "COMPLETE"
    safety_privacy_status: str = SAFETY_PRIVACY_NO_SOURCE
    target_suppressed: bool = TARGET_SUPPRESSED_NO_SOURCE

    automatic_teaching_enabled: bool = True
    hard_protected_flow: bool = False
    automatic_session_budget_exhausted: bool = False
    hard_cooldown_active: bool = False

    @property
    def selected_candidate_id(self) -> str:
        """The §14 decision column's name for :attr:`candidate_id`."""

        return self.candidate_id


@dataclass(frozen=True)
class AutoContinuationFacts:
    """One AUTO_CONTINUE fact bundle (BF-03 v1.1 continuation branch,
    ``authorization_basis = ACTIVE_MOMENT``, ``user_initiated = False``).

    Same continuation shape as :class:`ContinuationFacts` (the seven
    critical facts; the moment's lifecycle state; the two §8 hard caps and
    the move class that decides whether a cap blocks), plus the two facts
    that only the automatic continuation carries:

    - ``moment_consent_class`` — how the active moment came to be (see
      :func:`moment_consent_class_of`; an ``AUTO_OPENED`` moment stops when
      the auto-teach setting is off, a ``USER_AUTHORIZED`` one keeps
      going);
    - ``continuation_requested`` — which **must be false**: an automatic
      continuation cannot claim the user asked (the frozen reference's
      "AUTO_CONTINUE cannot claim continuation_requested", a contract
      error, not a DENY);
    - ``terminalizing_action`` — the reference's own fact for a move whose
      class is terminalizing although its ``proposed_action`` word is not
      (the §8 exemption: a reveal/feedback move is never blocked by the
      teaching-turn cap). The word class is not restated from it: a
      ``REVEAL`` / ``TERMINAL_FEEDBACK`` action is terminalizing on its
      own, and this flag can only add to that.
    """

    moment_id: str
    decision_cycle_id: str | None = None
    candidate_id: str = ""
    proposed_action: str = "HINT"
    gate_context: str = "AUTO_CONTINUE"
    authorization_path: str = "AUTOMATIC"
    authorization_basis: str = "ACTIVE_MOMENT"
    user_intent_scope: str = "ACTIVE_TEACHING_CONTINUATION"
    continuation_requested: bool = False
    moment_consent_class: str = "AUTO_OPENED"
    user_initiated: bool = False

    authorization_status: str = "VALID"
    subject_status: str = "ACTIVE"
    target_status: str = "VALID"
    content_status: str = "VALID"
    lock_state: str = "OWNED_BY_THIS_MOMENT"
    moment_state: str = CONTINUATION_MOMENT_STATE
    learning_snapshot_status: str = "VALID"
    gate_state_status: str = "COMPLETE"
    safety_privacy_status: str = SAFETY_PRIVACY_NO_SOURCE
    target_suppressed: bool = TARGET_SUPPRESSED_NO_SOURCE

    hard_attempt_limit_exhausted: bool = False
    hard_teaching_turn_limit_exhausted: bool = False
    terminalizing_action: bool = False

    automatic_teaching_enabled: bool = True
    hard_protected_flow: bool = False


def _validate_automatic_open(facts: AutomaticOpenFacts) -> None:
    _check(facts.gate_context in GATE_CONTEXTS, "invalid gate_context")
    _check(
        facts.gate_context == "OPEN",
        "this profile decides the OPEN context only"
        " (continuation is decide_auto_continuation)",
    )
    _check(
        facts.proposed_action in OPEN_ACTIONS,
        f"invalid OPENING action: {facts.proposed_action}",
    )
    _check(
        facts.authorization_path == "AUTOMATIC",
        "this profile decides AUTOMATIC authorization paths only",
    )
    _check(
        facts.user_intent_scope in USER_INTENT_SCOPES,
        f"invalid user_intent_scope: {facts.user_intent_scope}",
    )
    _check_opening_facts(facts)
    _check_planner_authorized_open(facts)
    _check_fact_values(facts)


def decide_automatic_open(facts: AutomaticOpenFacts) -> GateVerdict:
    """Decide one AUTOMATIC OPEN (BF-03 v1.1 automatic branch; the frozen
    reference's decision order word for word).

    Order (frozen): contract validation → critical-state completeness → the
    check families in decision order → deny precedence ordering → ALLOW.
    The user-intent scope of this path must be ``OPEN`` (the Planner judged
    worth-teaching on its own; any other scope means the latest intent is
    no longer "let the runtime choose" — BF-03 §11), and the three
    automatic-only controls (auto-teach preference, session budget,
    cooldown) plus the flow protection fire exactly where the reference
    has them.
    """

    _validate_automatic_open(facts)

    unknown = tuple(sorted(set(_opening_unknown_facts(facts))))
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
    if facts.user_intent_scope != "OPEN":
        reasons.append("USER_INTENT_BLOCK")
    if not facts.automatic_teaching_enabled:
        reasons.append("AUTO_TEACH_DISABLED")
    if facts.lock_state in {"OWNED_BY_OTHER", "OWNED_BY_THIS_MOMENT"}:
        reasons.append("TEACHING_LOCK_CONFLICT")
    if facts.hard_protected_flow:
        reasons.append("HARD_PROTECTED_FLOW")
    if facts.automatic_session_budget_exhausted:
        reasons.append("AUTO_SESSION_BUDGET_EXHAUSTED")
    if facts.hard_cooldown_active:
        reasons.append("HARD_COOLDOWN_ACTIVE")

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


def _validate_auto_continuation(facts: AutoContinuationFacts) -> None:
    _check(facts.gate_context in GATE_CONTEXTS, "invalid gate_context")
    _check(
        facts.gate_context == "AUTO_CONTINUE",
        "this profile decides the AUTO_CONTINUE context only (a"
        " user-requested continuation is decide_user_requested_continuation)",
    )
    _check(
        facts.proposed_action in CONTINUATION_ACTIONS,
        f"invalid continuation action: {facts.proposed_action}",
    )
    _check(
        facts.authorization_path == "AUTOMATIC",
        "this profile decides AUTOMATIC authorization paths only",
    )
    _check(
        facts.authorization_basis == "ACTIVE_MOMENT",
        "continuation requires ACTIVE_MOMENT authorization basis (BF-03"
        " §3 cross-layer v1.1)",
    )
    _check(bool(facts.moment_id), "continuation requires moment_id")
    _check(
        not facts.continuation_requested,
        "AUTO_CONTINUE cannot claim continuation_requested (an automatic"
        " continuation was not asked for)",
    )
    _check(
        facts.moment_consent_class in _MOMENT_CONSENT_CLASSES,
        f"invalid moment_consent_class: {facts.moment_consent_class}",
    )
    _check(
        facts.user_intent_scope in USER_INTENT_SCOPES,
        f"invalid user_intent_scope: {facts.user_intent_scope}",
    )
    _check_fact_values(facts)


def decide_auto_continuation(facts: AutoContinuationFacts) -> GateVerdict:
    """Decide one AUTO_CONTINUE (BF-03 v1.1 automatic branch, the frozen
    reference's continuation logic for ``gate_context == "AUTO_CONTINUE"``,
    word for word).

    A lock that is not this moment's is a DENY (CONFLICT for another
    holder, LOCK_INVALID otherwise), a moment that is not
    DECIDING_NEXT_ACTION is MOMENT_NOT_CONTINUABLE, the flow protection and
    the two §8 hard caps fire as the reference has them, and the auto-teach
    preference blocks only an ``AUTO_OPENED`` moment — a user-authorized
    episode is not the setting's to stop.
    """

    _validate_auto_continuation(facts)

    unknown = tuple(sorted(set(_continuation_unknown_facts(facts))))
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
    if facts.user_intent_scope != "ACTIVE_TEACHING_CONTINUATION":
        reasons.append("USER_INTENT_BLOCK")
    if (
        facts.moment_consent_class == "AUTO_OPENED"
        and not facts.automatic_teaching_enabled
    ):
        reasons.append("AUTO_TEACH_DISABLED")
    if facts.lock_state == "OWNED_BY_OTHER":
        reasons.append("TEACHING_LOCK_CONFLICT")
    elif facts.lock_state != "OWNED_BY_THIS_MOMENT":
        reasons.append("TEACHING_LOCK_INVALID")
    if facts.moment_state != CONTINUATION_MOMENT_STATE:
        reasons.append("MOMENT_NOT_CONTINUABLE")
    if facts.hard_protected_flow:
        reasons.append("HARD_PROTECTED_FLOW")

    retry_like = facts.proposed_action in {"RETRY", "HINT"}
    terminalizing = (
        facts.proposed_action in {"REVEAL", "TERMINAL_FEEDBACK"}
        or facts.terminalizing_action
    )
    if facts.hard_attempt_limit_exhausted and retry_like:
        reasons.append("HARD_ATTEMPT_LIMIT")
    if facts.hard_teaching_turn_limit_exhausted and not terminalizing:
        reasons.append("HARD_TEACHING_TURN_LIMIT")

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
