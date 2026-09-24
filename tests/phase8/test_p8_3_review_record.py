"""P8-3 ⑥ — §5.2's ``event_type`` words and the review-outcome reading.

The column: §5.2 names it and pins no vocabulary; migration 0012 carries it raw
(``TEXT NOT NULL``, no CHECK) and no face branched on a value until this cut.
What is pinned here is that this cut's declaration stays a *declaration* — four
words in one module, none of them in the schema, none of them read by any
decision — and that the outcome reading is a total, two-column function of
§5.2's own answer columns, consistent with the Scheduler's frozen ladder.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from elc.platform.types import EvidenceModality, TargetId
from elc.scheduler.review_record import (
    REVIEW_EVENT_WORDS,
    REVIEW_OUTCOMES,
    ReviewEventWord,
    ReviewOutcome,
    outcome_of_history,
    review_outcome_of,
)
from elc.scheduler.spacing import ReviewEventRole, role_of
from elc.scheduler.types import ReviewEvent, SpacingStage
from tests.conftest import REPO_ROOT, SRC_ROOT

MODULE = "src/elc/scheduler/review_record.py"

STAMP = "2026-09-23T09:00:00+00:00"
LATER = "2026-09-23T09:05:00+00:00"
EVIDENCE_GROUP = "eg-1"

#: The declared words, verbatim and in the declared order (the module explains
#: them in this order: the act, then the three shapes an event with no evidence
#: group can be).
DECLARED_WORDS = ("RECALL_ATTEMPT", "SKIP", "EXPIRY", "MANUAL_MARK")


def event(
    *,
    event_id: str = "re-1",
    word: str = ReviewEventWord.RECALL_ATTEMPT.value,
    engaged: bool = True,
    evidence_group_id: str | None = None,
    created_at: str = STAMP,
    source_turn_id: str | None = None,
) -> ReviewEvent:
    return ReviewEvent(
        review_event_id=event_id,
        schedule_item_id="si-p8-3",
        teaching_moment_id=None,
        source_turn_id=source_turn_id,
        event_type=word,
        engaged=engaged,
        evidence_group_id=evidence_group_id,
        created_at=created_at,
    )


def _source() -> str:
    return (REPO_ROOT / MODULE).read_text(encoding="utf-8")


# -- ⑥ the vocabulary --------------------------------------------------------


def test_the_four_words_are_the_declared_list() -> None:
    assert [word.value for word in REVIEW_EVENT_WORDS] == list(DECLARED_WORDS)
    assert tuple(ReviewEventWord) == REVIEW_EVENT_WORDS
    assert [word.name for word in ReviewEventWord] == list(DECLARED_WORDS)


def test_every_word_carries_a_basis_and_a_revisit() -> None:
    """The module's own claim: a word without a basis is not declared, it is
    invented. Each entry names what it rests on and what re-opens it."""

    text = _source()
    for word in DECLARED_WORDS:
        assert f"ReviewEventWord.{word}" in text, word
    assert text.count("Revisit:") >= 4
    assert "declared" in text
    assert "no **" not in text.split("**The words")[0][-200:]


def test_the_failure_case_is_registered_rather_than_folded_away() -> None:
    """No word for a failure: §5.2 has no outcome column and the ladder's own
    reading is ``engaged=False`` (elc.scheduler.spacing)."""

    text = " ".join(_source().split())
    assert "a failed review has no column of its own" in text or (
        "No word for a *failure*" in text
    )
    assert "engaged=False" in text
    assert "spacing" in text


def test_no_migration_carries_a_word() -> None:
    """The schema is unchanged: §5.2's column is raw, and this cut's word list
    is not frozen into it (0012's R5 reading, kept)."""

    schema = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "migrations").glob("*.sql"))
    )
    for word in ("RECALL_ATTEMPT", "MANUAL_MARK", "EXPIRY"):
        assert word not in schema, word
    assert "'SKIP'" not in schema
    assert "USER_SKIP" in schema  # 0008's own reason vocabulary, untouched


def test_the_review_event_column_is_still_raw(db) -> None:
    import sqlite3  # noqa: F401  (the fixture's type, named for the reader)

    ddl = " ".join(
        str(
            db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                ("review_event",),
            ).fetchone()[0]
        ).split()
    )
    assert "event_type TEXT NOT NULL" in ddl
    assert "event_type TEXT NOT NULL CHECK" not in ddl
    for word in DECLARED_WORDS:
        assert word not in ddl, word


def test_the_eight_columns_of_a_review_event_are_untouched() -> None:
    """This cut declares words *about* §5.2's object; it does not move it."""

    import dataclasses

    assert [
        field.name for field in dataclasses.fields(ReviewEvent)
    ] == [
        "review_event_id",
        "schedule_item_id",
        "teaching_moment_id",
        "source_turn_id",
        "event_type",
        "engaged",
        "evidence_group_id",
        "created_at",
    ]


def test_the_module_branches_on_no_event_word() -> None:
    """No comparison, no attribute read and no string literal of
    ``event_type`` in the module that declares the words — the declaration is
    not a switch."""

    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr != "event_type"
        if isinstance(node, ast.Compare):
            names = [
                side.attr
                for side in [node.left, *node.comparators]
                if isinstance(side, ast.Attribute)
            ]
            assert "event_type" not in names
        if isinstance(node, ast.Constant) and node.value == "event_type":
            raise AssertionError("a literal event_type in code")


def test_the_module_imports_nothing_but_its_own_types() -> None:
    tree = ast.parse(_source())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    assert modules <= {
        "__future__",
        "enum",
        "typing",
        "elc.scheduler.types",
    }, modules


def test_the_module_imports_cold() -> None:
    """One subprocess, the module as a consumer meets it (the P4-3 rule)."""

    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "import elc.scheduler.review_record as record",
            "assert [w.value for w in record.REVIEW_EVENT_WORDS] =="
            " ['RECALL_ATTEMPT', 'SKIP', 'EXPIRY', 'MANUAL_MARK']",
            "print('COLD-REVIEW', record.ReviewOutcome.UNKNOWN.value)",
        ]
    )
    process = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        env=dict(
            os.environ, PYTHONDONTWRITEBYTECODE="1", ROOT=str(REPO_ROOT)
        ),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert process.returncode == 0, process.stderr
    assert "COLD-REVIEW UNKNOWN" in process.stdout


def test_the_package_keeps_the_module_out_of_its_exported_face() -> None:
    """The scheduler package's ``__all__`` is a reviewed list (phase 6 pins it
    name by name); this cut's vocabulary is reachable by import, not exported
    — the ``planner.stress_suite`` / ``db.planner_store`` precedent."""

    package = (SRC_ROOT / "scheduler" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "review_record" in package  # the docstring points at it
    assert "ReviewEventWord" not in package
    assert "REVIEW_EVENT_WORDS" not in package


# -- ⑥ the outcome reading ---------------------------------------------------


@pytest.mark.parametrize(
    "engaged, group, expected",
    [
        (True, EVIDENCE_GROUP, ReviewOutcome.SUCCESS),
        (True, None, ReviewOutcome.UNEVIDENCED_SUCCESS),
        (False, None, ReviewOutcome.FAILURE),
        (False, EVIDENCE_GROUP, ReviewOutcome.FAILURE),
    ],
)
def test_the_four_column_combinations(
    engaged: bool, group: str | None, expected: ReviewOutcome
) -> None:
    assert (
        review_outcome_of(
            event(engaged=engaged, evidence_group_id=group)
        )
        is expected
    )


def test_engagement_without_evidence_is_not_folded_into_success() -> None:
    """"The user did it" and "the system has evidence about it" are two facts;
    the un-evidenced success is its own word."""

    assert ReviewOutcome.UNEVIDENCED_SUCCESS is not ReviewOutcome.SUCCESS
    unevidenced = review_outcome_of(event(evidence_group_id=None))
    evidenced = review_outcome_of(event(evidence_group_id=EVIDENCE_GROUP))
    assert unevidenced != evidenced


@pytest.mark.parametrize(
    "word",
    ["RECALL_ATTEMPT", "SKIP", "EXPIRY", "MANUAL_MARK", "SOMETHING_ELSE", ""],
)
def test_the_word_never_decides_the_outcome(word: str) -> None:
    """The column names the act; the two answer columns decide the outcome —
    including for a word outside the declared list, which changes nothing
    (the schema carries no list and this face enforces none)."""

    assert (
        review_outcome_of(
            event(word=word, evidence_group_id=EVIDENCE_GROUP)
        )
        is ReviewOutcome.SUCCESS
    )
    assert (
        review_outcome_of(event(word=word, engaged=False))
        is ReviewOutcome.FAILURE
    )
    assert (
        review_outcome_of(event(word=word, evidence_group_id=None))
        is ReviewOutcome.UNEVIDENCED_SUCCESS
    )


def test_no_recorded_event_answers_unknown() -> None:
    """UNKNOWN is the empty history's answer, never a row's: §5.2 has no
    unknown event and ``engaged`` is NOT NULL."""

    for engaged in (True, False):
        for group in (None, EVIDENCE_GROUP):
            outcome = review_outcome_of(
                event(engaged=engaged, evidence_group_id=group)
            )
            assert outcome is not ReviewOutcome.UNKNOWN
            assert outcome in REVIEW_OUTCOMES


def test_the_outcome_words_are_the_four_declared_ones() -> None:
    assert [word.value for word in REVIEW_OUTCOMES] == [
        "SUCCESS",
        "UNEVIDENCED_SUCCESS",
        "FAILURE",
        "UNKNOWN",
    ]
    assert tuple(ReviewOutcome) == REVIEW_OUTCOMES


def test_an_empty_history_is_unknown() -> None:
    assert outcome_of_history(()) is ReviewOutcome.UNKNOWN


def test_the_latest_event_decides_and_the_order_is_the_stores() -> None:
    """``(created_at, review_event_id)`` — the order
    ``elc.scheduler.store.list_review_events`` reads a history in, so the two
    cannot disagree about which event is last."""

    earlier_failure = event(
        event_id="re-z", engaged=False, created_at=STAMP
    )
    later_success = event(
        event_id="re-a",
        engaged=True,
        evidence_group_id=EVIDENCE_GROUP,
        created_at=LATER,
    )
    assert (
        outcome_of_history((later_success, earlier_failure))
        is ReviewOutcome.SUCCESS
    )
    assert (
        outcome_of_history((earlier_failure, later_success))
        is ReviewOutcome.SUCCESS
    )
    # a tie on the instant is broken by the id (the durable read's own tie)
    tie_old = event(event_id="re-a", engaged=False, created_at=STAMP)
    tie_new = event(
        event_id="re-b",
        engaged=True,
        evidence_group_id=EVIDENCE_GROUP,
        created_at=STAMP,
    )
    assert (
        outcome_of_history((tie_new, tie_old)) is ReviewOutcome.SUCCESS
    )
    assert outcome_of_history((tie_old, tie_new)) is ReviewOutcome.SUCCESS


def test_a_history_of_one_is_that_events_outcome() -> None:
    for word in DECLARED_WORDS:
        for engaged in (True, False):
            only = event(word=word, engaged=engaged)
            assert outcome_of_history((only,)) == review_outcome_of(only)


def test_an_unstamped_event_still_answers() -> None:
    """``created_at`` is stamped by the store on the way in, so an in-memory
    event may carry ``""``; the reading must still answer (it is a read of the
    history, not a durable query)."""

    unstamped = event(created_at="", engaged=False)
    assert outcome_of_history((unstamped,)) is ReviewOutcome.FAILURE


# -- ⑥ the agreement with the Scheduler's own ladder -------------------------


@pytest.mark.parametrize(
    "engaged, expected_role",
    [
        (True, ReviewEventRole.ANCHOR_AND_ADVANCE),
        (False, ReviewEventRole.ANCHOR_ONLY),
    ],
)
def test_the_two_readings_agree_because_both_read_engaged(
    engaged: bool, expected_role: ReviewEventRole
) -> None:
    """This cut adds no second ladder: ``spacing.role_of`` is the due policy's
    table and it keys on the same column — a success is an event the ladder
    advances, a failure is one it only anchors on."""

    one = event(engaged=engaged, created_at=STAMP)
    assert role_of(one) is expected_role
    outcome = review_outcome_of(one)
    if engaged:
        assert outcome in (
            ReviewOutcome.SUCCESS,
            ReviewOutcome.UNEVIDENCED_SUCCESS,
        )
    else:
        assert outcome is ReviewOutcome.FAILURE


def test_the_ladder_is_still_the_schedulers() -> None:
    """The reading does not touch the stage arithmetic: two engaged events move
    the ladder exactly as they did before this cut (``min(engaged, STAGE_4)``)."""

    history = (
        event(event_id="re-1", created_at=STAMP),
        event(event_id="re-2", created_at=LATER),
    )
    from elc.scheduler.spacing import stage_from_history

    assert stage_from_history(history) is SpacingStage.STAGE_2
    assert review_outcome_of(history[-1]) is ReviewOutcome.UNEVIDENCED_SUCCESS
    quiet = (event(event_id="re-3", engaged=False, created_at=LATER),)
    assert stage_from_history(quiet) is SpacingStage.STAGE_0
    assert review_outcome_of(quiet[0]) is ReviewOutcome.FAILURE


def test_the_scheduler_package_still_declares_no_lease_or_ttl() -> None:
    """RA §24.1's permanent prohibition, re-checked over the file this cut
    adds."""

    text = _source().lower()
    for word in ("lease", "heartbeat", "ttl", "distributed_lock"):
        assert word not in text, word
    assert re.search(r"\bexpire_after\b", text) is None


def test_the_module_names_the_documents_it_answers_to() -> None:
    text = _source()
    assert "docs/DATA_MODEL.md §5.2" in text
    assert "0012" in text
    assert "event_type" in text
    assert TargetId("t-1") is not None and EvidenceModality.TEXT_PRODUCTION
    assert Path(MODULE).name == "review_record.py"
