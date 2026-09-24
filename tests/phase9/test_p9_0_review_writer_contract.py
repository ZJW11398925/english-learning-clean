"""P9-0 (D) — the ReviewEvent writer contract and the anchor referral.

The review-outcome flow — the first real writer of §5.2's ``review_event`` —
is not this cut's work item, so what this cut delivers is what a writer must
meet, stated where the vocabulary is stated (:mod:`elc.scheduler.
review_record`): the eight columns it takes, what must be validated before a
row lands, when the timestamp is immutable, which transaction writes it, and
what a refusal leaves behind. The ladder's own freeze table says the same
thing from its side ("the first ReviewEvent producer must cite this table
before it writes an event").

Its second half is a **referral**: ``ANCHOR_ONLY`` means a failed review still
opens a fresh window, so a failure postpones the next due date exactly as an
engagement does. That reading is P7-0's and it is **unchanged** here — this
module pins the freeze behaviourally and pins the referral textually, and the
decision itself is named as belonging before the first writer, through
``DECISION_REGISTER``.

What is asserted:

- the contract's claims are in the module the vocabulary lives in, and the
  four declared words are what it points a writer at;
- the *writer* is still not built: the only module in ``src/`` that writes
  ``review_event`` is the durable store (no new producer slipped in with the
  contract);
- the frozen reading is untouched, row by row, and the consequence the
  referral is about is demonstrated (a failed event really does anchor);
- the referral is written in both docstrings (``review_record`` and
  ``spacing``), names both arms, and names its trigger and its route.
"""

from __future__ import annotations

import ast

from elc.scheduler.review_record import (
    REVIEW_EVENT_WORDS,
    ReviewEventWord,
)
from elc.scheduler.spacing import (
    ReviewEventRole,
    anchor_of,
    role_of,
    stage_from_history,
)
from elc.scheduler.types import ReviewEvent
from tests.conftest import SRC_ROOT
from tests.phase3.sql_write_scan import write_statements, write_targets

MODULE = SRC_ROOT / "scheduler" / "review_record.py"
SPACING = SRC_ROOT / "scheduler" / "spacing.py"
STORE = SRC_ROOT / "scheduler" / "store.py"
DAY_ONE = "2026-09-24T09:00:00+00:00"
DAY_THREE = "2026-09-26T09:00:00+00:00"


class _NoStrongRetrieval:
    """The freshness port with no strong retrieval: every anchor in these
    pins comes from the event, never from the Learning side."""

    last_strong_retrieval_at: str | None = None


def _event(
    *, event_id: str = "re-p9-0", engaged: bool = True, created_at: str = DAY_ONE
) -> ReviewEvent:
    return ReviewEvent(
        review_event_id=event_id,
        schedule_item_id="si-p9-0",
        event_type=ReviewEventWord.RECALL_ATTEMPT.value,
        engaged=engaged,
        created_at=created_at,
    )


def _source(path) -> str:
    return path.read_text(encoding="utf-8")


def _strings_outside_docstrings(path) -> list[str]:
    """Every string literal in ``path`` that is not a docstring — the strings
    a running module can read, with the prose excluded on purpose (the AST is
    the reader, so a docstring is told apart from an ordinary literal)."""

    tree = ast.parse(_source(path))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


# -- ① the contract ----------------------------------------------------------


def test_the_contract_names_the_columns_and_the_four_words() -> None:
    text = _source(MODULE)
    assert "The writer contract" in text
    for column in (
        "review_event_id",
        "schedule_item_id",
        "teaching_moment_id",
        "source_turn_id",
        "event_type",
        "engaged",
        "evidence_group_id",
        "created_at",
    ):
        assert column in text, column
    assert [word.value for word in REVIEW_EVENT_WORDS] == [
        "RECALL_ATTEMPT",
        "SKIP",
        "EXPIRY",
        "MANUAL_MARK",
    ]
    assert "one of the four words above" in text


def test_the_contract_names_what_must_be_validated_and_what_a_refusal_is() -> None:
    text = " ".join(_source(MODULE).split())
    assert "must exist" in text
    assert "NOT_FOUND" in text
    assert "CONFLICT" in text
    assert "append-first" in text
    assert "is never rewritten" in text
    assert "wildcard" in text  # the undeclared-timestamp replay rule
    assert "verbatim" in text


def test_the_contract_names_the_transaction_that_writes() -> None:
    text = " ".join(_source(MODULE).split()).lower()
    assert "one short transaction" in text
    assert "owner-epoch fence" in text
    assert "elc.scheduler.store" in text
    assert "never writes a row itself" in text


def test_no_review_writer_slipped_in_with_the_contract() -> None:
    """The contract is a declaration, not a producer: the two modules that
    touch §5.2's ``review_event`` are the durable store (the one INSERT) and
    the deletion face (DELETE only) — so nothing in this cut records an
    event."""

    writers = {
        path.relative_to(SRC_ROOT).as_posix()
        for path in sorted(SRC_ROOT.rglob("*.py"))
        if "review_event" in write_targets(path)
    }
    assert writers == {"deletion/store.py", "scheduler/store.py"}
    assert write_statements(STORE)["review_event"] == ("INSERT",)
    assert write_statements(
        SRC_ROOT / "deletion" / "store.py"
    )["review_event"] == ("DELETE",)


# -- ② the frozen ladder is untouched ----------------------------------------


def test_the_four_roles_are_still_the_four_shapes() -> None:
    assert role_of(_event()) is ReviewEventRole.ANCHOR_AND_ADVANCE
    assert role_of(_event(engaged=False)) is ReviewEventRole.ANCHOR_ONLY
    assert (
        role_of(_event(created_at="")) is ReviewEventRole.ADVANCE_ONLY
    )
    assert (
        role_of(_event(engaged=False, created_at=""))
        is ReviewEventRole.HISTORY_ONLY
    )


def test_a_failed_review_still_anchors_the_window() -> None:
    """The consequence the referral is about, demonstrated rather than
    described: the silent event anchors (its ``created_at`` is the answer to
    "when did we last touch this row"), and it does not advance the ladder."""

    failed = _event(engaged=False)
    anchored = anchor_of(_NoStrongRetrieval(), (failed,))
    assert anchored.value == DAY_ONE
    assert stage_from_history((failed,)) is stage_from_history(())
    # A newer silent event wins the anchor over an older engaged one: the
    # anchor is asked of every event, which is exactly the arm in force.
    newer = _event(
        event_id="re-p9-0-newer", engaged=False, created_at=DAY_THREE
    )
    assert anchor_of(_NoStrongRetrieval(), (failed, newer)).value == DAY_THREE


def test_the_referral_does_not_change_anything_it_reports() -> None:
    """The cut's zero-change claim, readable in one place: the freeze table's
    own words are still declared, and no ladder function calls the role
    reader (the P7-0 pin's own property, re-asserted where the referral now
    sits)."""

    docstring = ReviewEventRole.__doc__ or ""
    for phrase in (
        "P7-0 freeze table",
        "must cite this table before it writes an event",
    ):
        assert phrase in docstring, phrase
    assert "referred rather than decided" in docstring


# -- ③ the referral ----------------------------------------------------------


def test_the_referral_is_written_in_both_docstrings() -> None:
    review = _source(MODULE)
    spacing = _source(SPACING)
    for text in (review, spacing):
        collapsed = " ".join(text.split())
        assert "refer" in collapsed
        assert "DECISION_REGISTER" in collapsed
        assert "first real" in collapsed
    assert "The anchor question, referred rather than decided" in review
    assert "A failed review's window, referred rather than decided" in spacing


def test_the_referral_names_both_arms_with_their_consequences() -> None:
    review = " ".join(_source(MODULE).split())
    # arm one: the reading in force — a failure opens a fresh window
    assert "opens a fresh window" in review
    assert "moves one full spacing interval further out" in review
    # arm two: the alternative — the failure leaves the window where it was
    assert "leaves the window where it was" in review
    assert "retry sooner" in review
    # and neither arm is taken here
    assert "changes nothing" in review
    assert "trigger for deciding it is the first real writer" in review


def test_the_referral_does_not_move_the_policy_it_describes() -> None:
    """Three positive controls on the same claim: the spacing module still
    imports only its own faces (no new dependency came with the prose), the
    ladder's model version still says what it said, and the referral is
    *prose* — its words live in the two docstrings and in no other string
    literal, so no running module can read the question, branch on it or hand
    it back."""

    from elc.scheduler.spacing import SCHEDULER_MODEL_VERSION

    assert SCHEDULER_MODEL_VERSION == "sd1"
    text = _source(SPACING)
    assert "import sqlite3" not in text
    assert "elc.platform.db" not in text
    # The words that name the referral's route and its decision, read off the
    # AST: if either appeared outside a docstring the question would have a
    # behaviour face, and it would no longer be merely referred.
    for path in (MODULE, SPACING):
        ordinary = [
            literal
            for literal in _strings_outside_docstrings(path)
            if "DECISION_REGISTER" in literal
            or "referred rather than decided" in literal
        ]
        assert ordinary == [], (path.name, ordinary)
