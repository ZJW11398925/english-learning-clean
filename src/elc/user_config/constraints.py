"""How a §9 constraint is read by a consumer (P7-0).

P6-3 landed the durable row and its five faces and deliberately interpreted
nothing: ``scope`` travelled verbatim, the two target columns were carried as
§9 spells them, and the store registered that "which session is current" is a
consumer's question. This module is that consumer's reading, and it is a pure
module in the :mod:`elc.user_config.disclosure` sense — no store, no SQL, no
clock: it turns rows someone else read into the entries a consumer acts on.

**Two readings are frozen here, and neither is quoted from the canonical set.**
§9 pins no rule for either, so each one is a judgement with a reason, written
where it is applied:

1. **The half-declared target leg is widened, not dropped** —
   :func:`applies_to`. A row with exactly one of ``target_type`` /
   ``target_id`` present cannot be read as a narrowing (there is no target it
   names), and the *type* of the constraint is perfectly readable. Dropping it
   would silently un-apply a prohibition the user stated; the fail-safe
   direction for a prohibition is to keep it, so a half-declared row applies to
   **every** target — the same answer a not-target-limited row gets — and
   :attr:`~elc.user_config.types.PlannerConstraintEntry.target_leg` marks it
   ``HALF_DECLARED`` so the widening is visible instead of silent. The
   narrower alternative ("it names no target, so it names nothing") is what the
   store's target-scoped *row* read answers, and the two are not in conflict:
   that read answers "which rows name this target verbatim", this one answers
   "what does the user's constraint set forbid". **Revisit condition**: the
   write face starts refusing a half-declared pair, or the canonical set pins a
   rule for it — either one retires this judgement, because then the shape
   stops being reachable.
2. **``THIS_SESSION`` is bound by the caller's conversation** —
   :func:`build_view` takes it as an argument. §9 gives the object no
   conversation column, so a row cannot say which session it is about; the
   binding is therefore the reader's, and carrying it on the view is what keeps
   a consumer from honouring the scope against nothing (the P6-3 registration's
   "the cut that wires the first consumer answers it"). No column is added and
   no row is rewritten: the answer is an argument.

Everything else is carried verbatim: the window was already decided by the
read that produced the rows (``active_constraints`` compares instants and
returns what is in force), the four ``constraint_type`` words and the three
``scope`` words stay §9's, and this module applies no constraint to any
teaching decision — that is the Planner's and the Gate's cut, and neither is
wired here.
"""

from __future__ import annotations

from typing import Sequence

from elc.platform.types import ConversationId, TargetId
from elc.user_config.types import (
    PlannerConstraint,
    PlannerConstraintEntry,
    PlannerConstraintType,
    PlannerConstraintView,
    TargetLeg,
)

__all__ = [
    "applies_to",
    "build_view",
    "entries_for_target",
    "entries_of_type",
    "target_leg_of",
]


def target_leg_of(constraint: PlannerConstraint) -> TargetLeg:
    """Which of the three shapes §9's two target columns are in.

    Both NULL is "not target-limited", both present is "target-limited", and
    exactly one present is ``HALF_DECLARED`` — a shape §9 leaves open
    (:class:`~elc.user_config.types.PlannerConstraint` says so) and whose
    reading :func:`applies_to` freezes.
    """

    has_type = constraint.target_type is not None
    has_id = constraint.target_id is not None
    if has_type and has_id:
        return TargetLeg.TARGET_LIMITED
    if has_type or has_id:
        return TargetLeg.HALF_DECLARED
    return TargetLeg.NOT_TARGET_LIMITED


def applies_to(
    entry: PlannerConstraintEntry, target_type: str, target_id: TargetId
) -> bool:
    """Whether one entry speaks about this target (module docstring, rule 1).

    Three answers, one per :class:`~elc.user_config.types.TargetLeg`:

    - ``NOT_TARGET_LIMITED`` — yes: the constraint is about teaching / review /
      chat in general;
    - ``TARGET_LIMITED`` — yes when both legs match verbatim, where "verbatim"
      is text equality on each leg exactly as the store's own target read
      compares them (no case folding, no id normalisation);
    - ``HALF_DECLARED`` — also **yes**: the widening the module docstring
      reasons out. This is the one place the widening is decided.
    """

    if entry.target_leg is TargetLeg.NOT_TARGET_LIMITED:
        return True
    if entry.target_leg is TargetLeg.HALF_DECLARED:
        return True
    return (
        entry.target_type == target_type
        and entry.target_id is not None
        and str(entry.target_id) == str(target_id)
    )


def build_view(
    constraints: Sequence[PlannerConstraint],
    *,
    as_of: str,
    bound_conversation_id: ConversationId,
) -> PlannerConstraintView:
    """The consumer view over the rows a read already filtered (rule 2).

    The rows are expected to be the ones ``active_constraints(as_of)``
    answered — in force at ``as_of`` — so this function takes no clock and
    re-decides nothing about the window; it normalizes each row (carrying its
    nine columns and spelling its target shape) and stamps the view with the
    instant it was built for and the conversation ``THIS_SESSION`` binds to.

    Ordering is the read's (``constraint_id`` byte order); the view preserves
    it, so two views of one world are identical.
    """

    return PlannerConstraintView(
        as_of=as_of,
        bound_conversation_id=bound_conversation_id,
        entries=tuple(_entry_of(constraint) for constraint in constraints),
    )


def entries_for_target(
    view: PlannerConstraintView, target_type: str, target_id: TargetId
) -> tuple[PlannerConstraintEntry, ...]:
    """The view's entries that speak about one target (:func:`applies_to`)."""

    return tuple(
        entry for entry in view.entries if applies_to(entry, target_type, target_id)
    )


def entries_of_type(
    view: PlannerConstraintView, constraint_type: PlannerConstraintType
) -> tuple[PlannerConstraintEntry, ...]:
    """The view's entries of one §9 type, in the view's order.

    A read, not a policy: nothing here decides what a ``DO_NOT_AUTO_TEACH``
    entry *does* — the cut that applies a suppression is the one that has to
    say so (and none is wired yet, the P6-3 statement this does not change).
    """

    return tuple(
        entry
        for entry in view.entries
        if entry.constraint_type is constraint_type
    )


def _entry_of(constraint: PlannerConstraint) -> PlannerConstraintEntry:
    """One durable row as its view entry — nine columns plus the leg shape."""

    return PlannerConstraintEntry(
        constraint_id=constraint.constraint_id,
        constraint_type=constraint.constraint_type,
        scope=constraint.scope,
        target_leg=target_leg_of(constraint),
        target_type=constraint.target_type,
        target_id=constraint.target_id,
        starts_at=constraint.starts_at,
        expires_at=constraint.expires_at,
        active=constraint.active,
    )
