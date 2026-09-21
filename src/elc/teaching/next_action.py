"""DECIDING_NEXT_ACTION — the SM §1 branch table, as a pure decision.

docs/STATE_MACHINES.md §1 "Main flow":

    DECIDING_NEXT_ACTION
        ├─ HINT / RETRY ───────────→ AWAITING_USER
        ├─ REVEAL / EXPLAIN ───────→ AWAITING_USER or COMPLETING
        ├─ USER SWITCH ─────────────→ ABORTING
        ├─ SKIP / TOPIC SHIFT ──────→ ABORTING
        └─ SUCCESS ─────────────────→ COMPLETING

and docs/DOMAIN_MODEL.md §15's eight supported moves (hint / retry /
reveal / explanation / skip / reject / topic shift / explicit target
switch).

This module decides *which* branch one envelope takes. It is pure: it
takes the envelope, the durable evaluation (if any) and the §8 limit
verdict, and returns a :class:`NextAction` — the state the moment moves to,
the delivery kind (if any), the closure (if any), and the abort reason (if
any). Every write happens afterwards through the Teaching store's short
transactions.

Decision order (fixed and tested):

1. an explicit target switch closes the current moment and opens the same
   turn's next DecisionCycle (SM §2: "先关闭当前 Moment，再同 turn 新
   DecisionCycle"; the cycle_index+1 mechanism is P3-1A's);
2. SKIP / REJECT_TARGET / CHANGE_TOPIC abort with the §7 reason word for
   the control intent (USER_SKIP / USER_REJECTED_TARGET /
   USER_TOPIC_SHIFT);
3. a SUCCESS / ALTERNATIVE_SUCCESS attempt completes the moment (the
   closing outcome distinguishes supported vs unsupported success, and the
   alternative realization gets its own §6 word);
4. ASK_ANSWER → the next reveal rung, ASK_EXPLANATION → the explanation,
   ASK_HINT → the next hint rung, ASK_CLARIFICATION / META_DISCUSSION /
   NONE / CONTINUE → the retry-like continuation for a non-successful
   attempt. These are *continuations*: SM §1's "REVEAL / EXPLAIN →
   AWAITING_USER **or** COMPLETING" resolves to AWAITING_USER here (the
   §3 POST_REVEAL_OPTIONAL_ATTEMPT phase exists precisely because a reveal
   does not have to end the episode);
5. the §8 limits decide whether a continuation is authorized at all — the
   hard caps convert it into the closing move (a terminalizing REVEAL, the
   frozen reference's exemption: "hard attempt cap 阻新 HINT/RETRY 但允许
   terminalizing REVEAL/feedback"), and a soft cap with no explicit user
   request closes the episode without showing the answer
   (PARTIAL_PROGRESS). Nothing is silently dropped.

An ABSTAIN evaluation (an attempt that could not be judged) never
completes a moment by itself: it is a retry-like continuation, and the
moment still closes through an explicit move.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.teaching.envelope import TeachingControlIntent, TeachingResponseEnvelope
from elc.teaching.limits import (
    TeachingLimits,
    TeachingLoad,
    continuation_verdict,
)
from elc.teaching.types import (
    AbortReason,
    AttemptOutcome,
    CompletionOutcome,
    MomentState,
    TeachingSupportLevel,
)

__all__ = [
    "NextAction",
    "closing_outcome_for",
    "decide_next_action",
]

#: The control intents that map 1:1 onto an SM §7 abort reason.
_ABORT_BY_INTENT = {
    TeachingControlIntent.SKIP: AbortReason.USER_SKIP,
    TeachingControlIntent.REJECT_TARGET: AbortReason.USER_REJECTED_TARGET,
    TeachingControlIntent.CHANGE_TOPIC: AbortReason.USER_TOPIC_SHIFT,
    TeachingControlIntent.SWITCH_TARGET: AbortReason.USER_SWITCH_TARGET,
}


@dataclass(frozen=True)
class NextAction:
    """The decided branch of DECIDING_NEXT_ACTION.

    Exactly one of ``delivery_kind`` / ``closure`` is meaningful:
    - a continuation carries ``delivery_kind`` (HINT / RETRY / REVEAL /
      EXPLANATION) and moves the moment to ``moment_state``;
    - a closure carries ``closure`` (a §6 outcome or a §7 abort reason)
      and moves the moment to COMPLETING or ABORTING;
    - ``switch_target_request`` marks the explicit-target-switch branch
      (close then same-turn next cycle) — the caller owns the cycle move;
    - ``limit_reason`` names the §8 cap that forced a closing conversion
      (the BF-03 reason word), so the trace says why the episode stopped.
    """

    moment_state: MomentState
    delivery_kind: str | None
    closure: str | None
    completion_outcome: str | None
    abort_reason: str | None
    terminalizing: bool = False
    switch_target_request: str | None = None
    limit_reason: str | None = None
    refused_kind: str | None = None

    @property
    def is_closure(self) -> bool:
        return self.closure is not None

    @property
    def shows_answer(self) -> bool:
        """True when the closing move delivers the full form (the §8
        exemption): the caller renders the reveal text with the closure."""

        return self.closure is not None and self.delivery_kind == "REVEAL"


def closing_outcome_for(
    outcome: str, support_level: str
) -> CompletionOutcome:
    """§6 word for a successful attempt.

    Unsupported success means the learner produced the target without
    teaching support (NONE / CONTEXT_ONLY); anything above that is a
    supported success. An alternative realization always gets its own §6
    word (SM §5: "ALTERNATIVE_SUCCESS → valid capability success")."""

    if outcome == AttemptOutcome.ALTERNATIVE_SUCCESS.value:
        return CompletionOutcome.SUCCESS_ALTERNATIVE
    if support_level in (
        TeachingSupportLevel.NONE.value,
        TeachingSupportLevel.CONTEXT_ONLY.value,
    ):
        return CompletionOutcome.SUCCESS_UNSUPPORTED
    return CompletionOutcome.SUCCESS_SUPPORTED


def decide_next_action(
    *,
    envelope: TeachingResponseEnvelope,
    evaluation_outcome: str | None,
    support_level_before_attempt: str,
    limits: TeachingLimits,
    load: TeachingLoad,
) -> NextAction:
    """Decide the §1 branch. Pure — the caller executes it."""

    intent = envelope.control_intent

    # 1. Explicit target switch: close, then the same turn's next cycle.
    if intent is TeachingControlIntent.SWITCH_TARGET:
        return NextAction(
            moment_state=MomentState.ABORTING,
            delivery_kind=None,
            closure=AbortReason.USER_SWITCH_TARGET.value,
            completion_outcome=None,
            abort_reason=AbortReason.USER_SWITCH_TARGET.value,
            terminalizing=True,
            switch_target_request=envelope.target_switch_request,
        )

    # 2. Leaving control intents abort with their §7 reason.
    if intent in _ABORT_BY_INTENT:
        reason = _ABORT_BY_INTENT[intent]
        return NextAction(
            moment_state=MomentState.ABORTING,
            delivery_kind=None,
            closure=reason.value,
            completion_outcome=None,
            abort_reason=reason.value,
            terminalizing=True,
        )

    # 3. A successful attempt completes the moment.
    if evaluation_outcome in (
        AttemptOutcome.SUCCESS.value,
        AttemptOutcome.ALTERNATIVE_SUCCESS.value,
    ) and intent not in (
        TeachingControlIntent.ASK_ANSWER,
        TeachingControlIntent.ASK_EXPLANATION,
        TeachingControlIntent.ASK_HINT,
    ):
        outcome = closing_outcome_for(evaluation_outcome, support_level_before_attempt)
        return NextAction(
            moment_state=MomentState.COMPLETING,
            delivery_kind=None,
            closure=outcome.value,
            completion_outcome=outcome.value,
            abort_reason=None,
            terminalizing=True,
        )

    # 4. The requested continuation (an explicit move, never a default).
    kind = _delivery_kind_for(intent)
    verdict = continuation_verdict(
        limits,
        load,
        delivery_kind=kind,
        user_requested_continue=_is_user_requested_continue(intent),
    )
    if verdict.allowed:
        return _continuation(kind)

    # 5. The §8 conversion — never a silent stop. A hard cap exempts the
    #    terminalizing reveal (the frozen reference's retry_like /
    #    terminalizing classes); a soft cap reached without an explicit
    #    user request ends the episode with the progress it has, and shows
    #    no answer the user did not ask for. ``refused_kind`` names the move
    #    the limits blocked, so the continuation Gate can record exactly
    #    what it refused before the episode closes.
    if verdict.closing_only:
        return NextAction(
            moment_state=MomentState.COMPLETING,
            delivery_kind="REVEAL",
            closure=CompletionOutcome.REVEALED.value,
            completion_outcome=CompletionOutcome.REVEALED.value,
            abort_reason=None,
            terminalizing=True,
            limit_reason=verdict.degraded_reason,
            refused_kind=kind,
        )
    return NextAction(
        moment_state=MomentState.COMPLETING,
        delivery_kind=None,
        closure=CompletionOutcome.PARTIAL_PROGRESS.value,
        completion_outcome=CompletionOutcome.PARTIAL_PROGRESS.value,
        abort_reason=None,
        terminalizing=True,
        limit_reason=verdict.degraded_reason,
        refused_kind=kind,
    )


def _delivery_kind_for(intent: TeachingControlIntent) -> str:
    if intent is TeachingControlIntent.ASK_HINT:
        return "HINT"
    if intent is TeachingControlIntent.ASK_ANSWER:
        return "REVEAL"
    if intent is TeachingControlIntent.ASK_EXPLANATION:
        return "EXPLANATION"
    # ASK_CLARIFICATION / META_DISCUSSION / CONTINUE / NONE: the user asked
    # nothing that changes the ladder rung — the retry-like continuation
    # re-prompts at the same rung (SM §1 "HINT / RETRY → AWAITING_USER").
    return "RETRY"


def _is_user_requested_continue(intent: TeachingControlIntent) -> bool:
    """SM §8: only an explicit request lowers the interruption cost.

    ASK_HINT / ASK_ANSWER / ASK_EXPLANATION / ASK_CLARIFICATION and a bare
    CONTINUE are explicit user moves; META_DISCUSSION and NONE are not.
    (The AUTO_CONTINUE path is Phase 8 and never reaches this slice.)"""

    return intent in (
        TeachingControlIntent.ASK_HINT,
        TeachingControlIntent.ASK_ANSWER,
        TeachingControlIntent.ASK_EXPLANATION,
        TeachingControlIntent.ASK_CLARIFICATION,
        TeachingControlIntent.CONTINUE,
    )


def _continuation(kind: str) -> NextAction:
    """One authorized continuation: the moment stays live (AWAITING_USER)
    at the ladder position the delivery will show. Nothing here is
    terminalizing — an authorized reveal leaves the moment open at
    FULL_REVEAL, which is what the §3 POST_REVEAL_OPTIONAL_ATTEMPT phase
    exists for."""

    return NextAction(
        moment_state=MomentState.AWAITING_USER,
        delivery_kind=kind,
        closure=None,
        completion_outcome=None,
        abort_reason=None,
        terminalizing=False,
    )
