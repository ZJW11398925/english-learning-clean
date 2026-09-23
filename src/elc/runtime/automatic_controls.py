"""The three automatic-open controls, derived from their two views (P8-2).

BF-03's automatic branch protects a *new AUTOMATIC OPEN* with three facts
whose authorities p8-1's gate profiles registered and deliberately did not
read:

- ``automatic_session_budget_exhausted`` ← docs/DATA_MODEL.md §5.2's
  ``SessionBudgetView`` (BF-03 §16: "只阻止 ``new AUTOMATIC OPEN``"; "用户主动
  发起的新教学请求也不受 automatic session budget 限制");
- ``hard_cooldown_active`` ← the same view (BF-03 §17: again only a new
  automatic opening; it does not stop a user-initiated OPEN or an active
  moment's continuation);
- ``hard_protected_flow`` ← docs/DOMAIN_MODEL.md §13's
  :class:`~elc.planner.scope.ConversationPriorityView`
  (``flow_priority == "PROTECTED"``; §13: "Gate 保留最终授权权威").

This module is the one mapping, so no caller re-invents it:

    SessionBudgetView ─────► automatic_session_budget_exhausted
                            └► hard_cooldown_active
    ConversationPriorityView ► hard_protected_flow

**Why this lives in ``elc.runtime``.** The three booleans *are* the automatic
decision unit's declared controls (:class:`elc.runtime.automatic_teaching.
TeachingControlFacts`), and the runtime package is the only landed layer that
already reads both domains this derivation spans (its automatic unit imports
the Planner's records and the Teaching domain's types), so putting it here
adds no domain→domain edge — the alternative, ``elc.teaching`` importing
``elc.planner.scope``, would. It is pure: no store, no SQL, no clock, no I/O
(Gate item 2 covers this package), and it derives from values a caller
already holds rather than reading anything itself.

**The three readings, and their two shapes of absence.**

1. **budget** — ``exhausted`` exactly when the view exists, its
   ``automatic_teaching_remaining`` is **not** ``None`` and it is ``<= 0``.
   ``None`` means "no budget number was read" (§5.1 pins no budget
   vocabulary), which is **not** "zero left": the ``None``/``0`` distinction
   is what keeps a spent budget from being indistinguishable from an
   unreadable one. Reading ``None`` as exhausted would deny every automatic
   opening in a world whose policy simply has no budget column, and reading it
   as remaining would spend a budget this repository cannot see — the mapping
   refuses both;
2. **cooldown** — ``active`` exactly when the view exists and
   ``cooldown_remaining > 0`` (the view already floors at ``0.0``, so "no
   automatic opening yet" is ``0.0`` and inactive);
3. **flow** — ``protected`` exactly when the §13 view exists and its
   ``flow_priority`` **is** :attr:`elc.planner.scope.FlowPriority.PROTECTED`,
   compared as the P7-2 enum rather than as a re-spelled string so a
   vocabulary change moves both sides at once. ``LOW`` / ``NORMAL`` / ``HIGH``
   are all unprotected for this fact: the Gate's other flow rules (§12's
   interruption cost) are the Gate's, this mapping only names the one control.

**An absent view is ``False`` (fail-open), and why.** Both views may be
missing — no session state was read, no §13 producer has landed (RA §4 step
3's conversation leg) — and the answer is ``False`` for each control that
would have read it. This is the frozen reference's own default (all three
controls default to ``False``, and the Gate's ``AutomaticOpenFacts`` carries
the same healthy defaults), and the reason it is the honest reading is that a
control is a **throttle, not an authorization**: BF-03 §12/§16/§17's controls
can only *add* a DENY to a Gate that already decides on safety, validity,
lock, scope and the §8 caps. Answering ``True`` for an unread view would make
this module manufacture a DENY no durable fact supports; answering ``False``
leaves the Gate exactly as capable as the facts it does hold. **Revisit**: the
cut that makes the budget leg mandatory for the automatic path (a turn that
may not open without a session-budget read) — that cut changes the controls'
defaults *and* the Gate's caller-declared posture together, and it must say
what an unreadable budget means there. A view that exists but cannot be read
is a different case and stays the caller's: ``TeachingController.
get_session_budget_view`` returns an ``Err`` for it, and a caller that ignores
the ``Err`` and passes ``None`` here is declaring "no session state", which is
the reading above.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.planner.scope import ConversationPriorityView, FlowPriority
from elc.teaching.types import SessionBudgetView

__all__ = ["AutomaticControls", "automatic_controls_of"]


@dataclass(frozen=True)
class AutomaticControls:
    """The three view-derived controls, in the order they are derived.

    A value record, not a decision: it says what the two views imply, and the
    Gate still decides (docs/DOMAIN_MODEL.md §13: "它用于表达当前对话保护级
    别；Gate 保留最终授权权威"). :class:`elc.runtime.automatic_teaching.
    TeachingControlFacts` is what carries these into the automatic unit, and a
    caller that wants to declare a control rather than derive it still may.
    """

    automatic_session_budget_exhausted: bool
    hard_cooldown_active: bool
    hard_protected_flow: bool


def automatic_controls_of(
    *,
    session_budget_view: SessionBudgetView | None,
    conversation_priority_view: ConversationPriorityView | None,
) -> AutomaticControls:
    """BF-03's three controls as the two views state them (module docstring).

    ``None`` for either view means "no such fact was read", and each control
    that would have read it answers ``False`` — the fail-open posture the
    module docstring argues and registers. Nothing here writes, reads or
    raises: the views are values, and every mapping is total.
    """

    remaining = (
        None
        if session_budget_view is None
        else session_budget_view.automatic_teaching_remaining
    )
    budget_exhausted = remaining is not None and remaining <= 0
    cooldown_active = (
        session_budget_view is not None
        and session_budget_view.cooldown_remaining > 0
    )
    return AutomaticControls(
        automatic_session_budget_exhausted=budget_exhausted,
        hard_cooldown_active=cooldown_active,
        hard_protected_flow=(
            conversation_priority_view is not None
            and conversation_priority_view.flow_priority
            is FlowPriority.PROTECTED
        ),
    )
