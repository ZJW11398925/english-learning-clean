"""Scheduler → Planner authority handshake (P7-0).

The Scheduler decides review due (D-INV-009) and the Planner *consumes* its
view; between the two there is one question this module answers, and it is the
question BF-02 §5 (lines 128–166) refuses to let a consumer answer with a
number. Quoted, verbatim:

    Planner 不允许：missing Scheduler → schedule_urgency = 0
    也不允许：stale LearningSnapshot → 假装仍有效

    PlanningContext 至少包含：feature_assembly_status / snapshot_status /
    missing_authorities[] / natural_break_available

    如果：feature_assembly_status != COMPLETE or snapshot_status != VALID
    返回：PlannerExecutionStatus = DEGRADED / PlannerDecision = none

Two halves of that rule belong to two different packages, and this module is
the Scheduler's half only:

- **here** — a durable §5.2 row records ``source_learning_watermark``: the
  Learning evidence watermark the row was computed from (P6-2 R6, the decimal
  spelling ``str(get_learning_watermark())``). Comparing that recorded value
  with the *current* watermark is what tells a current row from a stale one,
  and :func:`currency_of` is that comparison — pure, no store, no clock;
- **in the Planner** — what a STALE (or absent) authority does to the
  feature vector and to the decision. That is BF-02 §5's degradation rule and
  it lives in :mod:`elc.planner.feature_assembly`; it is deliberately **not**
  implemented here, because a Scheduler that turned its own staleness into a
  substitute factor value would be answering the Planner's question.

**What STALE means, and what it does not.** ``STALE`` says one thing: the row
was computed against an evidence watermark that is no longer the current one,
so its ``review_state`` / ``review_urgency`` / window describe an earlier
world. It does **not** say the row is wrong — the due decision remains the
Scheduler's, and a stale row is still the durable record of what the Scheduler
concluded then. It also does not say "no schedule authority": a *missing*
authority (no view, no rows at all) is a different state, and this module
answers for rows that exist. The third state — a target with no row — is
``Ok(None)`` on the read face below, which is not staleness either: BF-02 §5's
missing-Scheduler case is about a Planner holding no schedule authority, not
about a target with nothing due yet (elc.scheduler.spacing's ``NOT_SCHEDULED``
anchor note says the same from the other side).

**A non-numeric stored watermark is not an error here.** §5.2 declares the
column TEXT and this package carries it verbatim (a caller-written row may
hold anything), so the comparison is a comparison of the recorded value's
spelling with the current watermark's spelling: equal ⇒ CURRENT, anything else
⇒ STALE. Parsing it would be an interpretation the column never received, and
"it does not match the current watermark" is exactly what a consumer needs to
know.
"""

from __future__ import annotations

from enum import StrEnum

from elc.scheduler.types import ScheduleItem

__all__ = ["ScheduleCurrency", "currency_of"]


class ScheduleCurrency(StrEnum):
    """Whether one §5.2 row was computed against the current evidence set.

    Two words, because the second question (what to do about it) is the
    consumer's: ``CURRENT`` = the row's ``source_learning_watermark`` is the
    current Learning watermark; ``STALE`` = it is not. There is deliberately no
    third word for "no row": that is the absence of a row, answered by the
    read face's ``Ok(None)``, and folding it in here would let a caller report
    "stale" for a target the Scheduler simply has not scheduled yet.

    Revisit: a canonical clause gives ``source_learning_watermark`` a form of
    its own to compare (a number, a timestamp, a per-target watermark) rather
    than the decimal spelling R6 declared, or a consumer appears that needs a
    third word here (e.g. "the row predates the watermark's configuration") —
    either one re-opens this two-word comparison.
    """

    CURRENT = "CURRENT"
    STALE = "STALE"


def currency_of(
    item: ScheduleItem, current_watermark: int | str
) -> ScheduleCurrency:
    """The handshake for one row: CURRENT or STALE (module docstring).

    ``current_watermark`` is what ``get_learning_watermark()`` answers — an
    ``int`` from the Learning face, or its already-spelled form (``str``) when
    a caller carries it that way. Both are compared as the spelling the §5.2
    column holds, so one rule covers both call shapes and no arithmetic is
    done on either side.

    Pure: no store, no clock, no I/O — the caller does the two reads and this
    function decides the comparison, so the decision has one home and the two
    faces that ask (the Scheduler's handshake face and the Planner's assembly)
    cannot drift apart.
    """

    return (
        ScheduleCurrency.CURRENT
        if item.source_learning_watermark == str(current_watermark)
        else ScheduleCurrency.STALE
    )
