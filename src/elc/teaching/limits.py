"""Teaching limits v0 — the SM §8 budget pair, versioned.

docs/STATE_MACHINES.md §8:

    soft_attempt_limit
    hard_attempt_limit
    soft_teaching_turn_limit
    hard_teaching_turn_limit
    "具体数值实现期校准"

v0 calibrates them at 2 / 3 / 3 / 5 (in that canonical order) and stamps
the set with :data:`LIMITS_V0_VERSION`, so a later calibration is a new
version, not a silent retune.

Counting rules (TASK-…2.2 ⑦ — the durable definitions, not formulas):

- ``attempt_count`` is the number of durable ``AttemptRecord`` rows of the
  moment (migration 0008's UNIQUE(moment_id, attempt_index) makes it
  exact); it is NOT a count of user messages.
- ``teaching_turn_count`` is the number of *delivered* teaching turns of
  the moment: TEACHING_OPEN + TEACHING_HINT + TEACHING_REVEAL +
  TEACHING_EXPLANATION actions that reached a terminal delivered state.
  A failed delivery does not consume a teaching turn.

Continuation policy (SM §8 second half + the frozen BF-03 v1.1
continuation branch, behavioral_baselines/gate/teaching_gate_reference_v1_1.py
lines 174-184):

- past a SOFT limit, automatic continuation is not allowed any more: only
  an explicit USER_REQUESTED_CONTINUE (with ACTIVE_MOMENT authorization)
  may continue — "user-requested continue 可降低 interruption cost";
- past the HARD attempt limit, retry-like moves (HINT / RETRY) are
  blocked and only terminalizing moves (REVEAL / closing feedback)
  remain — the exact reference rule
  ``hard_attempt_limit_exhausted and retry_like → HARD_ATTEMPT_LIMIT``;
- past the HARD teaching-turn limit, non-terminalizing moves are blocked
  and the moment may only be closed — ``hard_teaching_turn_limit_exhausted
  and not terminalizing → HARD_TEACHING_TURN_LIMIT``.

The two hard-cap reason words are the frozen BF-03 vocabulary; taking the
"closing move" exemption is recorded as the closure (REVEALED /
PARTIAL_PROGRESS), never as a silent continue.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ALLOWED_BY_CONTINUATION_GATE",
    "CLOSING_DELIVERY_KINDS",
    "HARD_ATTEMPT_LIMIT",
    "HARD_TEACHING_TURN_LIMIT",
    "LIMITS_V0",
    "LIMITS_V0_VERSION",
    "RETRY_LIKE_DELIVERY_KINDS",
    "SOFT_ATTEMPT_LIMIT",
    "SOFT_TEACHING_TURN_LIMIT",
    "TEACHING_TURN_ACTION_TYPES",
    "LimitVerdict",
    "TeachingLimits",
    "TeachingLoad",
    "continuation_verdict",
]

#: The four §8 limits, in the canonical §8 order (soft_attempt,
#: hard_attempt, soft_teaching_turn, hard_teaching_turn).
SOFT_ATTEMPT_LIMIT = 2
HARD_ATTEMPT_LIMIT = 3
SOFT_TEACHING_TURN_LIMIT = 3
HARD_TEACHING_TURN_LIMIT = 5

#: The v0 calibration as a versioned value set.
LIMITS_V0 = {
    "soft_attempt_limit": SOFT_ATTEMPT_LIMIT,
    "hard_attempt_limit": HARD_ATTEMPT_LIMIT,
    "soft_teaching_turn_limit": SOFT_TEACHING_TURN_LIMIT,
    "hard_teaching_turn_limit": HARD_TEACHING_TURN_LIMIT,
}

#: Policy identity of the calibration (stamped on the continuation trace).
LIMITS_V0_VERSION = "teaching-limits-v0"

#: The delivery kinds the frozen reference calls ``retry_like``
#: (proposed_action ∈ {RETRY, HINT}).
RETRY_LIKE_DELIVERY_KINDS = ("HINT", "RETRY")

#: The delivery kinds the frozen reference calls ``terminalizing``
#: (proposed_action ∈ {REVEAL, TERMINAL_FEEDBACK}).
CLOSING_DELIVERY_KINDS = ("REVEAL", "TERMINAL_FEEDBACK", "CLOSE")

#: The generation action types that count as one delivered teaching turn
#: (TASK-…2.2 ⑦): TEACHING_OPEN / TEACHING_HINT / TEACHING_REVEAL /
#: TEACHING_EXPLANATION. PERSONA_RESUME is the exit move, not a teaching
#: turn; NORMAL_PERSONA_REPLY is not part of a moment (PERSONA_RESUME
#: included in the tuple only to make the exclusion explicit).
TEACHING_TURN_ACTION_TYPES = (
    "TEACHING_OPEN",
    "TEACHING_HINT",
    "TEACHING_REVEAL",
    "TEACHING_EXPLANATION",
)

#: The verdict words a caller may receive (BF-03 stable vocabulary only).
ALLOWED_BY_CONTINUATION_GATE = "CONTINUATION_ALLOWED"


@dataclass(frozen=True)
class TeachingLimits:
    """One limit calibration (versioned)."""

    soft_attempt_limit: int = SOFT_ATTEMPT_LIMIT
    hard_attempt_limit: int = HARD_ATTEMPT_LIMIT
    soft_teaching_turn_limit: int = SOFT_TEACHING_TURN_LIMIT
    hard_teaching_turn_limit: int = HARD_TEACHING_TURN_LIMIT
    version: str = LIMITS_V0_VERSION


@dataclass(frozen=True)
class TeachingLoad:
    """The two durable counts the §8 limits are evaluated against."""

    attempt_count: int
    teaching_turn_count: int


@dataclass(frozen=True)
class LimitVerdict:
    """The continuation verdict for one proposed delivery.

    ``allowed`` — may this move be executed at all;
    ``user_request_required`` — past a soft limit, only an explicit
    USER_REQUESTED_CONTINUE may proceed;
    ``degraded_reason`` — the BF-03 reason word when a hard cap fired
    (None otherwise);
    ``closing_only`` — only terminalizing moves remain.
    """

    allowed: bool
    user_request_required: bool
    degraded_reason: str | None
    closing_only: bool
    policy_version: str = LIMITS_V0_VERSION


def continuation_verdict(
    limits: TeachingLimits,
    load: TeachingLoad,
    *,
    delivery_kind: str,
    user_requested_continue: bool,
) -> LimitVerdict:
    """Evaluate one proposed continuation against the §8 limits.

    The order mirrors the frozen reference: the hard-attempt rule fires on
    retry-like moves, the hard-turn rule fires on every non-terminalizing
    move. A hard cap is a *conversion*, never a silent stop: the caller
    turns the refusal into the corresponding closing move (REVEAL /
    closure) and records it.
    """

    retry_like = delivery_kind in RETRY_LIKE_DELIVERY_KINDS
    terminalizing = delivery_kind in CLOSING_DELIVERY_KINDS

    if load.attempt_count >= limits.hard_attempt_limit and retry_like:
        return LimitVerdict(
            allowed=False,
            user_request_required=False,
            degraded_reason="HARD_ATTEMPT_LIMIT",
            closing_only=True,
        )
    if (
        load.teaching_turn_count >= limits.hard_teaching_turn_limit
        and not terminalizing
    ):
        return LimitVerdict(
            allowed=False,
            user_request_required=False,
            degraded_reason="HARD_TEACHING_TURN_LIMIT",
            closing_only=True,
        )
    soft_reached = (
        load.attempt_count >= limits.soft_attempt_limit
        or load.teaching_turn_count >= limits.soft_teaching_turn_limit
    )
    if soft_reached and not user_requested_continue and not terminalizing:
        return LimitVerdict(
            allowed=False,
            user_request_required=True,
            degraded_reason=None,
            closing_only=False,
        )
    return LimitVerdict(
        allowed=True,
        user_request_required=False,
        degraded_reason=None,
        closing_only=False,
    )
