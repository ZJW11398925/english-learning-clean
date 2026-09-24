"""§5.2's ``event_type`` words, and what a recorded review's outcome is (P8-3).

docs/DATA_MODEL.md §5.2 names the column and pins **no** vocabulary: neither
the canonical documents nor ``behavioral_baselines/`` declare one word for it
(grepped, not assumed). Migration 0012 therefore carries it raw — ``TEXT NOT
NULL``, no CHECK, no branch on a value anywhere in the scheduler — and
``elc/scheduler/types.py``'s R5 registration states why that was the honest
shape then and what would change it: "the word list is still unclaimed, and it
belongs to the flow that records *what a review did* (the review-outcome path,
Phase 8)". This is that path's cut, and this module is the claim — the words
are **declared here**, in one place, with a basis per word and a revisit per
reading, and the schema still carries none of them.

**The words, and the basis for each.** The list is minimal on purpose: one word
for the act a review event normally records, plus the three shapes migration
0012's own header already names for an event that cites no evidence group
("NULL = the event cites no evidence group (a skip, an expiry, a manual
mark)"). No canonical sentence carries any of the four, so each entry is a
declared reading with a condition that re-opens it:

- :attr:`ReviewEventWord.RECALL_ATTEMPT` — a review attempt happened. The
  review flow's own default word, and the spelling this repository already
  speaks: the Phase 6 suite builds its events with it
  (``tests/phase6/conftest.py``), which is evidence that the word is the
  implementation's and not a document's. Revisit: canonical text pins a
  vocabulary — then these four move to it, word for word;
- :attr:`ReviewEventWord.SKIP` — the review was due and the user declined it.
  RA §20 names the same act ``user_skip`` for the ledger's log; the behaviour
  §5.2 carries for it is ``engaged=False`` (``elc.scheduler.spacing``'s own
  frozen reading: "a producer that wants to record 'the review happened and did
  not engage' says ``engaged=False``"), so this word names the act and decides
  nothing. Revisit: the two logs are given one shared word (a single
  vocabulary for "the user declined"), or §5.2 gains a column for the act;
- :attr:`ReviewEventWord.EXPIRY` — the review's window closed without a review.
  The scheduler is the only face that knows a window (D-INV-009: "Scheduler 决定
  review due；Learning 只提供 freshness"), so the event that records the
  closing is the scheduler's — and it is *recorded*, not inferred, which is why
  it is a word here rather than a read of the due policy. Revisit: an expiry
  becomes derivable from the row alone (a ``review_state`` transition recorded
  elsewhere) — then this word carries nothing and is retired;
- :attr:`ReviewEventWord.MANUAL_MARK` — a review fact recorded by hand (a
  repair, an import, the user's own statement), the third shape 0012's header
  names. Revisit: a manual mark becomes indistinguishable from an attempt (the
  flow stops needing to say "a human wrote this"), or a second manual shape
  appears.

**What is deliberately not declared.** No word for a *failure*: §5.2 gives the
event no outcome column, and ``elc.scheduler.spacing`` fixes the reading —
"a failed review has no column of its own … a producer that wants to record
'the review happened and did not engage' says ``engaged=False``". So a failed
recall is ``RECALL_ATTEMPT`` with ``engaged=False``, and no fifth word is
invented for it. The words also carry no effect: nothing in ``src/`` branches
on ``event_type`` (the due policy reads ``engaged`` and ``created_at`` and
gives it no meaning), and the outcome reading below reads only §5.2's two
answer columns — a word outside this list changes nothing anywhere, which is
the same guarantee 0012's R5 registration gave and this cut keeps.

**The success / failure reading, and where "unknown" lives.** A recorded event
answers two independent questions, each with its own §5.2 column:
``engaged`` — did the user engage (the column the ladder counts) — and
``evidence_group_id?`` — was evidence recorded for it. :func:`review_outcome_of`
reads exactly those two and nothing else:

- ``engaged=True`` **with** an evidence group → :attr:`ReviewOutcome.SUCCESS`:
  the review engaged and its evidence is named;
- ``engaged=True`` **without** one → :attr:`ReviewOutcome.UNEVIDENCED_SUCCESS`:
  the engagement is the outcome (the ladder advances it — ``spacing``'s own
  reading), and no evidence claim was recorded. It is *not* folded into
  ``SUCCESS``: "the user did it" and "the system has evidence about it" are two
  facts, and a caller that needs the second must see the difference;
- ``engaged=False`` → :attr:`ReviewOutcome.FAILURE`, **whatever**
  ``evidence_group_id`` holds. The pair has no coupling in §5.2 — the column
  answers "was evidence recorded", not "did the review succeed" — and when the
  two disagree the engagement column is the outcome's spine (it is the one the
  ladder and the anchor read). The odd combination is registered rather than
  smoothed over;

:attr:`ReviewOutcome.UNKNOWN` is reachable only from :func:`outcome_of_history`
with an **empty** history: §5.2 has no unknown event and ``engaged`` is NOT
NULL, so "we do not know whether a review happened" is the absence of a
record, never a value one. That is also why there is no third truth value on a
recorded event: a row either engaged or did not.

This reading is *not* a second ladder and does not move the Scheduler's:
``spacing.py``'s ``ReviewRole`` table is what the due policy reads (it is
frozen there, and it keys on the same two columns), and the agreement is by
construction — both read ``engaged``. Nothing in this module is wired into the
due decision, the Gate or the Planner; it is the vocabulary and the outcome a
recorder or a reporter needs, declared once, with the revisit conditions above.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Sequence

from elc.scheduler.types import ReviewEvent

__all__ = [
    "REVIEW_EVENT_WORDS",
    "REVIEW_OUTCOMES",
    "ReviewEventWord",
    "ReviewOutcome",
    "outcome_of_history",
    "review_outcome_of",
]


class ReviewEventWord(StrEnum):
    """The words §5.2's ``event_type`` carries in this cut (module docstring).

    Four words, each with a basis and a revisit there; the schema carries
    **none** of them (0012's ``event_type TEXT NOT NULL`` is unchanged), and no
    face branches on a word.
    """

    RECALL_ATTEMPT = "RECALL_ATTEMPT"
    SKIP = "SKIP"
    EXPIRY = "EXPIRY"
    MANUAL_MARK = "MANUAL_MARK"


#: The declared words, in the order the module explains them: the act first,
#: then the three shapes an event with no evidence group can be.
REVIEW_EVENT_WORDS: tuple[ReviewEventWord, ...] = tuple(ReviewEventWord)


class ReviewOutcome(StrEnum):
    """What a recorded review came to — or that nothing was recorded.

    The three recorded words are functions of ``engaged`` and
    ``evidence_group_id`` alone (:func:`review_outcome_of`), and ``UNKNOWN`` is
    the empty history's answer, never a value a row can carry.
    """

    SUCCESS = "SUCCESS"
    UNEVIDENCED_SUCCESS = "UNEVIDENCED_SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


#: Every outcome word, for a caller that walks them.
REVIEW_OUTCOMES: tuple[ReviewOutcome, ...] = tuple(ReviewOutcome)


def review_outcome_of(event: ReviewEvent) -> ReviewOutcome:
    """One recorded event's outcome, off §5.2's two answer columns.

    ``event_type`` is deliberately **not** read: the word names the act (the
    vocabulary above), while the outcome is what the two columns say about it.
    A word outside :data:`REVIEW_EVENT_WORDS` therefore changes nothing here —
    the schema does not carry the list and this face does not enforce it.
    """

    if not event.engaged:
        return ReviewOutcome.FAILURE
    if event.evidence_group_id is None:
        return ReviewOutcome.UNEVIDENCED_SUCCESS
    return ReviewOutcome.SUCCESS


def outcome_of_history(events: Sequence[ReviewEvent]) -> ReviewOutcome:
    """A schedule row's review history as one outcome.

    An empty history is :attr:`ReviewOutcome.UNKNOWN` — the absence of a
    record, the only shape "we do not know" takes (module docstring). A
    non-empty one is its **latest** event's outcome, in the deterministic
    durable order ``(created_at, review_event_id)`` — the order
    ``elc.scheduler.store.list_review_events`` reads a history in, so this
    reading and the durable one cannot disagree about which event is last.
    """

    if not events:
        return ReviewOutcome.UNKNOWN
    latest = max(
        events,
        key=lambda event: (event.created_at, event.review_event_id),
    )
    return review_outcome_of(latest)
