"""Conversation context supply — docs/DOMAIN_MODEL.md §12 and §13 (P7-2).

Two things live here, and both are *reads*: what the current exchange is
*demanding* of the Planner (§12's ``UserIntentScope``) and how protected the
current flow is (§13's ``ConversationPriorityView``). Neither decides anything
about teaching — the Gate keeps the authorization authority (§13's own closing
line: "它用于表达当前对话保护级别；Gate 保留最终授权权威") — and neither owns a
store: every fact here arrives through a read face a caller already holds.

**§12 — the six words, and which of them this reader can answer.**
docs/DOMAIN_MODEL.md §12 pins the vocabulary verbatim::

    OPEN
    LEARNING_REQUEST
    TARGETED_LEARNING_REQUEST
    JUST_CHAT
    NON_LEARNING_TASK
    ACTIVE_TEACHING_CONTINUATION

``TARGETED_LEARNING_REQUEST`` is, in the document's words, "a candidate-scope
constraint, not an ordinary bonus" — so the resolver below does not merely
*label* the cycle: the word it returns is what restricts the candidate set
(the kernel's step 4 reads it, ``OUTSIDE_TARGETED_SCOPE``). Four of the six
words are reachable from a landed read face; two are **registered as
unproduced**, and saying so is this module's honest half:

- ``OPEN`` / ``LEARNING_REQUEST`` / ``TARGETED_LEARNING_REQUEST`` /
  ``JUST_CHAT`` are read from §9's constraint view
  (:class:`~elc.user_config.constraints.entries_of_type`), which P6-3 landed and
  P7-0 declared as a PlanningContext leg. ``MANUAL_FOCUS`` is the user's own
  durable act ("focus on this manually", the §9 Types word) and ``JUST_CHAT``
  is the user's own hard switch — neither is a model inference, which is what
  makes them admissible as a scope authority;
- ``NON_LEARNING_TASK`` and ``ACTIVE_TEACHING_CONTINUATION`` have **no
  landed producer**: the first needs the turn's task/small-talk reading, which
  RUNTIME_ARCHITECTURE §4 step 3 lists as a durable artifact
  ("UserIntentScope") that no cut records yet — this module lands the *rule*
  and the vocabulary, not that artifact; the second needs the open
  TeachingMoment state, which belongs to the Gate/Teaching cut and has no
  Planner-side read face. A scope word nothing can read is not a word this
  resolver invents.

**The precedence this cut declares** (and the basis for it). A ``MANUAL_FOCUS``
entry in force *outranks* a ``JUST_CHAT`` entry, because BF-02 §9 (lines
274–292) makes exactly that call: "用户如果显式发起学习请求，本 DecisionCycle 的
UserIntentScope 应先变化为 LEARNING_REQUEST or TARGETED_LEARNING_REQUEST" —
the scope word is the thing that changes first, and the request is the reason.
That sentence is also why the kernel can keep its own §9 refusal
(``JUST_CHAT`` + a user-initiated candidate is an upstream contract error): a
caller that routed both facts through this resolver never hands the kernel that
pair. §9 carries no priority column, so "which request first" is BF-02 §8's
"only when the user's semantics really express an order" — nothing in V1
records one, so every manual request is priority ``0`` and same-level requests
go to utility (§8's own sentence).

**§13 — the view, verbatim, and one declared reading.** The three fields and
both word lists are §13's; the one reading this cut adds is
:func:`interruption_cost_band_of`: §13's ``flow_priority`` ladder and BF-02
§6's ``interruption_cost`` ladder are both four-word ladders and they share the
word ``PROTECTED``, so the pairing is the only monotone one — and it is the
reason BF-02 §17's sentence matters here ("``interruption_cost = PROTECTED`` is
a cost, never an exclusion"): a PROTECTED flow raises a candidate's cost, and
the kernel may still SELECT. Nothing in this module denies anything.

**What this module does not do.** It does not read the constraint *window*
(the read that produced the rows already compared instants — P6-3's
``active_constraints``), it does not bind ``THIS_SESSION`` (P6-3's rule 2 makes
the binding the caller's, carried on the view), and it does not decide
suppression: a §9 ``DO_NOT_AUTO_TEACH`` / ``SUPPRESS_REVIEW`` row is read by the
*generator* (elc.planner.candidates), which marks a candidate — the kernel then
names the exclusion in its trace. One home per rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from elc.planner.types import UserIntentScope
from elc.platform.types import TargetId
from elc.user_config.constraints import entries_of_type
from elc.user_config.types import PlannerConstraintType, PlannerConstraintView

__all__ = [
    "FLOW_PRIORITY_WORDS",
    "FLOW_TO_INTERRUPTION_COST_BAND",
    "INTERACTION_PHASE_WORDS",
    "REACHABLE_SCOPE_WORDS",
    "ConversationPriorityView",
    "FlowPriority",
    "InteractionPhase",
    "RequestedTarget",
    "ScopeResolution",
    "UNPRODUCED_SCOPE_WORDS",
    "interruption_cost_band_of",
    "natural_break_available_of",
    "resolve_user_intent_scope",
]


# -- §13: the protection level ----------------------------------------------


class FlowPriority(StrEnum):
    """docs/DOMAIN_MODEL.md §13's ``flow_priority`` block, word for word."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    PROTECTED = "PROTECTED"


class InteractionPhase(StrEnum):
    """docs/DOMAIN_MODEL.md §13's ``interaction_phase`` block, word for word."""

    OPEN = "OPEN"
    DEEP_EXCHANGE = "DEEP_EXCHANGE"
    TASK_EXECUTION = "TASK_EXECUTION"
    STORY_FLOW = "STORY_FLOW"
    USER_SUPPORT = "USER_SUPPORT"
    TEACHING = "TEACHING"
    WRAP_UP = "WRAP_UP"


#: §13's two blocks, restated at module level so a pin can compare the
#: canonical text with a constant *and* with the enum's members rather than
#: trusting one spelling (the P6-0 review F-2 shape).
FLOW_PRIORITY_WORDS: tuple[str, ...] = ("LOW", "NORMAL", "HIGH", "PROTECTED")
INTERACTION_PHASE_WORDS: tuple[str, ...] = (
    "OPEN",
    "DEEP_EXCHANGE",
    "TASK_EXECUTION",
    "STORY_FLOW",
    "USER_SUPPORT",
    "TEACHING",
    "WRAP_UP",
)


@dataclass(frozen=True)
class ConversationPriorityView:
    """docs/DOMAIN_MODEL.md §13 — the three fields, verbatim.

    "它用于表达当前对话保护级别；Gate 保留最终授权权威": this record *expresses*
    the protection level and authorizes nothing. Its ``natural_break_available``
    field is the same boolean BF-02 §5 puts on the PlanningContext and BF-02
    §13's coverage-starvation safeguard reads, so a caller that assembled a
    context from this view passed the same fact through both faces.

    **The producer landed in P8-4** (RA §4 step 3's conversation leg): this cut
    landed the *shape*, the two vocabularies and the two readings below, and the
    cut that wires the ordinary turn derives an instance from the conversation's
    own durable state — ``elc.runtime.automatic_turn.
    conversation_priority_view_of`` (a live teaching lock/moment reads TEACHING
    + PROTECTED + no natural break; otherwise OPEN + NORMAL + a break). That
    derivation is deliberately **not** here: this module is the consumption face
    ("what a reader may read off §13's view"), and the producer has to read the
    durable world, which no module here does.
    """

    flow_priority: FlowPriority
    interaction_phase: InteractionPhase
    natural_break_available: bool


#: §13 ``flow_priority`` → BF-02 §6 ``interruption_cost`` reference band, by
#: their shared word. A declared reading (module docstring): the two ladders are
#: four-word ladders with one word in common (``PROTECTED``) and the same
#: direction, so the identity pairing is the only monotone one. ``LOW``'s
#: partner is BF-02's ``LOW`` (0.1), not a zero — BF-02 §6's cost ladder has no
#: zero band, and a flow that is merely unprotected is not a flow that costs
#: nothing to interrupt. Revisit: canonical text pairs the two vocabularies, or
#: BF-02's cost bands are re-laddered.
FLOW_TO_INTERRUPTION_COST_BAND: dict[FlowPriority, str] = {
    FlowPriority.LOW: "LOW",
    FlowPriority.NORMAL: "NORMAL",
    FlowPriority.HIGH: "HIGH",
    FlowPriority.PROTECTED: "PROTECTED",
}


def interruption_cost_band_of(
    view: ConversationPriorityView | None,
) -> str | None:
    """The ``interruption_cost`` band a candidate inherits from the flow, or
    ``None`` when there is no view.

    ``None`` is not a zero: BF-02 §5's rule ("missing authority → no number")
    is read here one factor over — a caller holding no §13 view gets no band
    from this function, and the generator falls back to its source's own
    declared default rather than pricing the flow at ``0``. The Gate keeps the
    authorization authority either way (§13); this only prices a cost.
    """

    if view is None:
        return None
    return FLOW_TO_INTERRUPTION_COST_BAND[view.flow_priority]


def natural_break_available_of(
    view: ConversationPriorityView | None,
) -> bool:
    """BF-02 §5's ``natural_break_available``, read off §13's view — the one
    reading every caller shares (P8-4).

    docs/DOMAIN_MODEL.md §13's :class:`ConversationPriorityView` carries the
    field under BF-02 §5's own name, so the view *is* the authority and this
    function only reads it. It lives here, beside
    :func:`interruption_cost_band_of`, because this module owns §13's shape and
    its two readings — and it exists because two callers now need the same
    answer: the shadow run's context assembly (P7-4's :func:`elc.planner.shadow.
    run_shadow`, where P8-2 moved the value's *source* from a keyword argument
    to the request's view) and P8-4's automatic turn, which builds that view on
    every ordinary turn. One function is what keeps the two from drifting:
    "§13's view expresses the protection level and authorizes nothing" — reading
    this one field delegates no authorization, and the Gate keeps that (§12's
    ``PROTECTED`` leg is the Gate's own read of ``flow_priority``, not this
    one).

    A ``None`` view answers ``False`` — the **fail-closed** reading: a natural
    break one cannot see is not one the run may claim (P7-0's own default, and
    "a value, not a missing authority"). That sentence is the whole of the
    semantics, and it did not change when the reading moved here.

    Revisit: canonical text puts the fact somewhere other than §13's view, or a
    caller appears that must read it without holding a view.
    """

    return view is not None and view.natural_break_available


# -- §12: the constraint view the resolver reads -----------------------------
#
# The input is P6-3's concrete consumer view
# (:class:`elc.user_config.types.PlannerConstraintView`) rather than a
# hand-rolled port: P6-3 built that record *for a consumer* (its two frozen
# readings — the widened half-declared leg and the caller-bound
# ``THIS_SESSION`` — are exactly what a consumer must not re-decide), and its
# helpers (:func:`elc.user_config.constraints.entries_of_type`) are the read
# this module consumes instead of re-implementing. A second port spelling of
# the same three fields would be a second place to get the widening wrong.


@dataclass(frozen=True)
class RequestedTarget:
    """One ``MANUAL_FOCUS`` entry's target leg, carried verbatim.

    Both legs travel as §9 spells them (P6-3's rule 1 widens a half-declared
    pair rather than dropping it, so ``target_id`` may be present while
    ``target_type`` is ``None``); the generator matches on the id and on the
    type only when the row declares one.
    """

    constraint_id: str
    target_type: str | None
    target_id: TargetId


@dataclass(frozen=True)
class ScopeResolution:
    """The scope word plus the facts that produced it.

    ``request_targets`` is only populated for
    :attr:`~elc.planner.types.UserIntentScope.TARGETED_LEARNING_REQUEST` — and
    it is what makes the word a *scope constraint* rather than a label: the
    generator supplies those targets as the request's candidates, and the
    kernel excludes everything else in that cycle (``OUTSIDE_TARGETED_SCOPE``).
    """

    scope: UserIntentScope
    request_targets: tuple[RequestedTarget, ...]
    reasons: tuple[str, ...]
    constraint_view_present: bool


#: §12's six words, split by whether a landed read face can answer them (module
#: docstring). Pinned by test, so a cut that lands a producer moves a word from
#: one tuple to the other *and* changes the reasons below.
REACHABLE_SCOPE_WORDS: tuple[str, ...] = (
    "OPEN",
    "LEARNING_REQUEST",
    "TARGETED_LEARNING_REQUEST",
    "JUST_CHAT",
)
UNPRODUCED_SCOPE_WORDS: tuple[str, ...] = (
    "NON_LEARNING_TASK",
    "ACTIVE_TEACHING_CONTINUATION",
)

_NO_VIEW_REASON = (
    "no §9 PlannerConstraintView: nothing declares a just-chat switch, a"
    " manual focus or a general learning request, so the scope is OPEN —"
    " 'nothing declared' is a word (§12) and the caller records the missing"
    " constraint authority separately (P7-0's constraint_view_present leg)"
)


def resolve_user_intent_scope(
    constraints: PlannerConstraintView | None,
) -> ScopeResolution:
    """§12's word for one DecisionCycle, from the §9 rows in force.

    Three answers, in the precedence the module docstring justifies, each with
    the line a reader needs to see *why*:

    ==========================================  =========================
    the constraints in force                    the scope word
    ==========================================  =========================
    ``MANUAL_FOCUS`` naming a target            ``TARGETED_LEARNING_REQUEST``
    ``MANUAL_FOCUS`` naming no target           ``LEARNING_REQUEST``
    ``JUST_CHAT``                               ``JUST_CHAT``
    (nothing)                                   ``OPEN``
    ==========================================  =========================

    ``NON_LEARNING_TASK`` / ``ACTIVE_TEACHING_CONTINUATION`` are unreachable
    here and the docstring says why; a caller that must express one has no
    authority to read it from, which is a registered absence rather than a
    silently defaulted word.
    """

    if constraints is None:
        return ScopeResolution(
            scope=UserIntentScope.OPEN,
            request_targets=(),
            reasons=(_NO_VIEW_REASON,),
            constraint_view_present=False,
        )

    targeted: list[RequestedTarget] = []
    general_focus = False
    for entry in entries_of_type(
        constraints, PlannerConstraintType.MANUAL_FOCUS
    ):
        if entry.target_id is None:
            general_focus = True
            continue
        targeted.append(
            RequestedTarget(
                constraint_id=entry.constraint_id,
                target_type=entry.target_type,
                target_id=entry.target_id,
            )
        )

    if targeted:
        return ScopeResolution(
            scope=UserIntentScope.TARGETED_LEARNING_REQUEST,
            request_targets=tuple(targeted),
            reasons=(
                f"{len(targeted)} MANUAL_FOCUS entr(y/ies) name a target: §12's"
                " TARGETED_LEARNING_REQUEST is the candidate-scope word, and"
                " BF-02 §9's remedy sentence is why an explicit request"
                " outranks a just-chat switch in the same cycle",
            ),
            constraint_view_present=True,
        )
    if general_focus:
        return ScopeResolution(
            scope=UserIntentScope.LEARNING_REQUEST,
            request_targets=(),
            reasons=(
                "a MANUAL_FOCUS entry names no target: the user asked for"
                " learning without narrowing it, which is §12's"
                " LEARNING_REQUEST rather than a scope constraint",
            ),
            constraint_view_present=True,
        )
    if entries_of_type(constraints, PlannerConstraintType.JUST_CHAT):
        return ScopeResolution(
            scope=UserIntentScope.JUST_CHAT,
            request_targets=(),
            reasons=(
                "a JUST_CHAT entry is in force and no explicit request"
                " outranks it: §9's own switch, read as the §12 word of the"
                " same name",
            ),
            constraint_view_present=True,
        )
    return ScopeResolution(
        scope=UserIntentScope.OPEN,
        request_targets=(),
        reasons=(
            "the constraint view holds no entry that bears on the scope: OPEN"
            " is §12's word for 'nothing is declared', not a guessed"
            " small-talk reading",
        ),
        constraint_view_present=True,
    )
