"""P9-4 ① — the exposure derivation and its acknowledgment refinement (pure).

Two faces of ``elc.runtime.exposure_reconciliation``, and nothing else in this
file: the §22 estimate's five value columns as a function of the durable facts
one delivery left (R2's table), and the one refinement RA §14 allows
(``ClientRenderAck``: ``certainty`` / ``confirmed_exposure`` rise, nothing
moves down). No database is opened here — the module is SQL-free, clock-free
and ledger-free by construction, and the last two tests in this file pin that
against the source rather than promising it:

- **the derivation table is total** over §13's four terminal words crossed with
  the two prefix shapes (and the two "no record" cases), one assertion per row,
  so a word that gains no row shows up as a failure rather than as a silent
  default;
- **the acknowledgment ladder only goes up**, including the reverse cases
  (an already-confirmed estimate, a repeated acknowledgment, a non-final chunk
  that confirms a render but not the send) and the one estimate no
  acknowledgment may move (a ``NONE`` ceiling: nothing was sent, so nothing can
  be confirmed);
- **the reason text is deterministic** — the same facts produce the same bytes,
  which is what lets the store compare a re-entry as a replay;
- **the module holds no SQL and no ledger**: its import set is declared and
  asserted by equality, and R4's one-way rule is pinned on the module plus on
  the controller's estimate writer (the estimate path names no §20 write).
"""

from __future__ import annotations

import ast
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from elc.conversation.types import DeliveryState
from elc.platform.types import ActionId, DomainErrorCode
from elc.runtime.delivery_records import ClientRenderAck, ExposureEstimate
from elc.runtime.exposure_reconciliation import (
    ACK_CERTAINTY_LADDER,
    DELIVERY_STATES_WITH_AN_ESTIMATE,
    EXPOSURE_LEVEL_LADDER,
    DeliveryExposureFacts,
    certainty_rank,
    exposure_estimate_of,
    exposure_rank,
    refine_with_ack,
    refinement_refusal,
)
from elc.teaching.types import (
    AnswerExposureState,
    ExposureEstimateCertainty,
)
from tests.conftest import SRC_ROOT

ACTION = ActionId("ga-turn-p9-4-pure-opening")

#: The acknowledgment every refinement test starts from: the client reporting
#: it rendered the final chunk of the action's stream.
FINAL_ACK = ClientRenderAck(
    action_id=ACTION,
    assistant_turn_id="aturn-p9-4-pure-opening",
    rendered_chunk_seq=3,
    rendered_text_hash="hash-of-the-final-chunk",
    acked_at="2026-09-24T09:00:03+00:00",
    final_rendered=True,
)

def _estimate(
    *,
    terminal_state: str | None,
    sent_prefix: str,
    attempted: bool = True,
    full_text_length: int | None = None,
    released: str | None = None,
) -> ExposureEstimate:
    return exposure_estimate_of(
        action_id=ACTION,
        facts=DeliveryExposureFacts(
            terminal_state=terminal_state,
            sent_prefix=sent_prefix,
            send_attempted=attempted,
            full_text_length=full_text_length,
            released_prefix=released,
        ),
    )


_PARTIAL = _estimate(
    terminal_state="SENT_PARTIAL", sent_prefix="abcd", full_text_length=10
)
_CONFIRMED = refine_with_ack(_PARTIAL, ack=FINAL_ACK)

#: ``(base, illegal, the sentence the refusal must carry)`` — one entry per way
#: a submission can stop being a refinement (§22's two movable columns and the
#: three that may not move at all).
ILLEGAL_MOVES: list[tuple[ExposureEstimate, ExposureEstimate, str]] = [
    (
        _CONFIRMED,
        replace(_CONFIRMED, certainty="UNKNOWN"),
        "only raises",
    ),
    (
        _CONFIRMED,
        replace(_CONFIRMED, confirmed_exposure="NONE"),
        "only raises",
    ),
    (
        _PARTIAL,
        replace(_PARTIAL, exposure_level="FULL"),
        "never what was sent",
    ),
    (
        _PARTIAL,
        replace(_PARTIAL, max_possible_exposure="FULL"),
        "never what was sent",
    ),
    (
        _PARTIAL,
        replace(_PARTIAL, action_id=ActionId("ga-other")),
        "identity",
    ),
    (
        replace(_PARTIAL, confirmed_exposure="FULL"),
        replace(_PARTIAL, confirmed_exposure="PARTIAL"),
        "only raises",
    ),
]


def _columns(estimate: ExposureEstimate) -> tuple[str, str, str, str]:
    return (
        estimate.certainty,
        estimate.exposure_level,
        estimate.max_possible_exposure,
        estimate.confirmed_exposure,
    )


# -- ① the derivation table ----------------------------------------------------

SENT = DeliveryState.SENT_COMPLETE.value
PARTIAL = DeliveryState.SENT_PARTIAL.value
FAILED = DeliveryState.FAILED.value
CANCELLED = DeliveryState.CANCELLED.value

SERVER = ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED.value
UNKNOWN = ExposureEstimateCertainty.UNKNOWN.value


def test_the_derivation_table_is_the_declared_one() -> None:
    """R2's table, row by row — including the two shapes the shipped writers
    cannot produce today (a ``FAILED`` row carrying a prefix, and a
    ``SENT_COMPLETE`` row shorter than the validated text), which are
    registered arms rather than omissions."""

    complete = _estimate(
        terminal_state=SENT,
        sent_prefix="abcdefghij",
        full_text_length=10,
    )
    assert _columns(complete) == ("SERVER_SENT_UNCONFIRMED", "FULL", "FULL", "NONE")

    short = _estimate(
        terminal_state=SENT,
        sent_prefix="abcd",
        full_text_length=10,
    )
    assert _columns(short) == ("SERVER_SENT_UNCONFIRMED", "PARTIAL", "PARTIAL", "NONE")

    partial = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        full_text_length=10,
    )
    assert _columns(partial) == (
        "SERVER_SENT_UNCONFIRMED",
        "PARTIAL",
        "PARTIAL",
        "NONE",
    )

    cancelled = _estimate(
        terminal_state=CANCELLED,
        sent_prefix="abcd",
        full_text_length=10,
    )
    assert _columns(cancelled) == (
        "SERVER_SENT_UNCONFIRMED",
        "PARTIAL",
        "PARTIAL",
        "NONE",
    )

    failed = _estimate(terminal_state=FAILED, sent_prefix="")
    assert _columns(failed) == ("SERVER_SENT_UNCONFIRMED", "NONE", "NONE", "NONE")

    # the buffer-whole shape: no second length is held, so the word is the fact
    buffered = exposure_estimate_of(
        action_id=ACTION,
        facts=DeliveryExposureFacts.buffered(text="abcdefghij"),
    )
    assert _columns(buffered) == ("SERVER_SENT_UNCONFIRMED", "FULL", "FULL", "NONE")
    assert buffered.derivation_reason == "sent 10 chars; no render ack"

    # no §22 row at all: the server cannot even say it tried
    no_row = _estimate(terminal_state=None, sent_prefix="", attempted=False)
    assert _columns(no_row) == ("UNKNOWN", "NONE", "NONE", "NONE")
    # ... and with an attempted send the certainty is the other one
    attempted = _estimate(terminal_state=None, sent_prefix="", attempted=True)
    assert _columns(attempted) == ("SERVER_SENT_UNCONFIRMED", "NONE", "NONE", "NONE")


@pytest.mark.parametrize("state", [SENT, PARTIAL, FAILED, CANCELLED, None])
def test_an_empty_prefix_is_none_whatever_the_word_says(state: str | None) -> None:
    """Reading 2: §17's sent boundary is the durable fact, so a word with
    nothing behind it is not exposure — the row P9-2 registered ("the send
    began and its record was lost") lands as ``NONE`` rather than as a
    smoothing of the word."""

    estimate = _estimate(terminal_state=state, sent_prefix="", attempted=True)
    assert estimate.exposure_level == "NONE"
    assert estimate.max_possible_exposure == "NONE"
    assert estimate.confirmed_exposure == "NONE"
    assert estimate.certainty == "SERVER_SENT_UNCONFIRMED"
    assert estimate.derivation_reason.startswith("nothing was sent")


def test_a_failed_row_with_a_prefix_is_partial() -> None:
    """Reading 3's registered arm: the pair no shipped writer produces, and the
    honest reading of it — the boundary the record holds is text the client
    received, whatever word the run lost."""

    estimate = _estimate(terminal_state=FAILED, sent_prefix="abcd")
    assert estimate.exposure_level == "PARTIAL"
    assert estimate.max_possible_exposure == "PARTIAL"


# -- ①b the released boundary, the ceiling's second half (P9-R2) ---------------


def test_the_released_half_is_the_ceilings_second_half() -> None:
    """Reading 11's arms, one assertion each: ``released_prefix`` is §17's
    *other* boundary (what the client boundary received, which a run that
    stopped between the release and the record leaves ahead of the durable
    prefix), and the ceiling is the higher of the two readings. The rows where
    the half is not held (``None``) and where it is held empty (``""``) both
    fall back to the durable level — a fallback and a known-empty boundary read
    the same row on purpose, and the field still says which fact it was."""

    # (a) the durable boundary covers the validated text and the released half
    #     agrees: nothing to raise, and the bytes are the ones this module has
    #     always written
    agrees = _estimate(
        terminal_state=SENT,
        sent_prefix="abcdefghij",
        full_text_length=10,
        released="abcdefghij",
    )
    assert (agrees.exposure_level, agrees.max_possible_exposure) == (
        "FULL",
        "FULL",
    )
    assert agrees.derivation_reason == "sent 10 of 10 chars; no render ack"

    # (b) the durable prefix is short and the released half covers the whole
    #     text: the level is the record's (PARTIAL), the ceiling is the
    #     release's (FULL) — through the streamed constructor as well, which is
    #     the face that holds both halves
    ahead = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        full_text_length=10,
        released="abcdefghij",
    )
    assert (ahead.exposure_level, ahead.max_possible_exposure) == (
        "PARTIAL",
        "FULL",
    )
    assert ahead.confirmed_exposure == "NONE"
    assert ahead.derivation_reason == (
        "sent 4 of 10 chars; partial send; the client boundary may hold more"
        " than the record shows (released 10 of 10 chars); no render ack"
    )
    streamed = exposure_estimate_of(
        action_id=ACTION,
        facts=DeliveryExposureFacts.streamed(
            terminal_state=PARTIAL,
            sent_prefix="abcd",
            validated_text="abcdefghij",
            released_prefix="abcdefghij",
        ),
    )
    assert _columns(streamed) == _columns(ahead)
    assert streamed.derivation_reason == ahead.derivation_reason

    # (c) nothing durable, something released: the level stays the empty
    #     boundary's NONE and the ceiling is the released half's PARTIAL
    nothing_durable = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="",
        full_text_length=10,
        released="abcd",
    )
    assert (nothing_durable.exposure_level, nothing_durable.max_possible_exposure) == (
        "NONE",
        "PARTIAL",
    )
    assert nothing_durable.confirmed_exposure == "NONE"
    assert "may hold more" in nothing_durable.derivation_reason
    assert nothing_durable.derivation_reason.startswith("nothing was sent")

    # (d) the caller does not hold the released half: the ceiling falls back to
    #     the durable level, and a released half *behind* the record cannot
    #     lower the ceiling either
    unheld = _estimate(
        terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10
    )
    assert unheld.max_possible_exposure == unheld.exposure_level == "PARTIAL"
    assert "may hold more" not in unheld.derivation_reason
    behind = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        full_text_length=10,
        released="ab",
    )
    assert behind.max_possible_exposure == behind.exposure_level == "PARTIAL"
    assert behind.derivation_reason == unheld.derivation_reason

    # (e) the half is held and empty: the same row as the fallback, a different
    #     fact (the facts carry which one it was)
    held_empty = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        full_text_length=10,
        released="",
    )
    assert held_empty.max_possible_exposure == held_empty.exposure_level == "PARTIAL"
    assert held_empty == unheld  # one row for two facts, deliberately
    assert DeliveryExposureFacts(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        send_attempted=True,
        full_text_length=10,
        released_prefix="",
    ) != DeliveryExposureFacts(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        send_attempted=True,
        full_text_length=10,
        released_prefix=None,
    )


@pytest.mark.parametrize("state", [SENT, PARTIAL, FAILED, CANCELLED])
def test_the_released_level_does_not_read_the_state_word(state: str) -> None:
    """Reading 11: the word describes how the *run* ended, while the released
    height is a fact about the client boundary — so a row that released the
    whole text carries the whole-text ceiling whatever word it froze with, and
    the three durable columns are exactly what they are without the half (R4:
    the released boundary moves the ceiling and nothing else)."""

    estimate = _estimate(
        terminal_state=state,
        sent_prefix="abcd",
        full_text_length=10,
        released="abcdefghij",
    )
    baseline = _estimate(
        terminal_state=state, sent_prefix="abcd", full_text_length=10
    )
    assert estimate.max_possible_exposure == "FULL"
    assert estimate.exposure_level == baseline.exposure_level
    assert estimate.certainty == baseline.certainty
    assert estimate.confirmed_exposure == baseline.confirmed_exposure


def test_the_ceiling_is_never_below_the_level_across_the_table() -> None:
    """The invariant every arm leans on, walked over the declared table crossed
    with five released shapes (not held, held empty, behind, short of the
    validated text, covering it): ``max_possible_exposure`` is never below
    ``exposure_level``; a half that is not held or held empty leaves the
    ceiling at the level; a half that covers the validated text makes it
    ``FULL``; and a half in between can only reach ``PARTIAL`` (never higher
    than the level it finds, except out of ``NONE``)."""

    for state in (SENT, PARTIAL, FAILED, CANCELLED, None):
        for prefix in ("", "abcd", "abcdefghij"):
            if state is None and prefix != "":
                continue  # the no-row shape holds no durable prefix
            for released in (None, "", "ab", "abcd", "abcdefghij"):
                estimate = _estimate(
                    terminal_state=state,
                    sent_prefix=prefix,
                    full_text_length=10,
                    released=released,
                )
                assert exposure_rank(estimate.max_possible_exposure) >= (
                    exposure_rank(estimate.exposure_level)
                ), (state, prefix, released)
                if released is None or released == "":
                    assert estimate.max_possible_exposure == (
                        estimate.exposure_level
                    ), (state, prefix, released)
                elif len(released) < 10:
                    # a released half short of the validated text: it lifts the
                    # ceiling out of NONE to PARTIAL and is otherwise behind the
                    # record's own reading (it can neither raise nor lower it)
                    if estimate.exposure_level == "NONE":
                        assert estimate.max_possible_exposure == "PARTIAL", (
                            state,
                            prefix,
                            released,
                        )
                    else:
                        assert estimate.max_possible_exposure == (
                            estimate.exposure_level
                        ), (state, prefix, released)
                else:
                    assert estimate.max_possible_exposure == "FULL", (
                        state,
                        prefix,
                        released,
                    )


def test_a_raised_ceiling_survives_the_acknowledgment_tail_swap() -> None:
    """Readings 5 and 11 together: the fragment is placed **before** the
    no-acknowledgment tail, so reading 5's tail swap keeps it — a refined row
    whose ceiling sits above its level still explains itself, and a final
    acknowledgment confirms the ceiling it was derived with."""

    raised = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="abcd",
        full_text_length=10,
        released="abcdefghij",
    )
    refined = refine_with_ack(raised, ack=FINAL_ACK)
    assert refined.certainty == "CONFIRMED_RENDERED"
    assert refined.confirmed_exposure == "FULL"  # the ceiling, confirmed
    assert refined.exposure_level == "PARTIAL"  # the record's word, unmoved
    assert refined.max_possible_exposure == "FULL"
    assert refined.derivation_reason.startswith(
        "sent 4 of 10 chars; partial send; the client boundary may hold more"
        " than the record shows (released 10 of 10 chars)"
    )
    assert "render ack for chunk 3 (final)" in refined.derivation_reason
    assert "no render ack" not in refined.derivation_reason


def test_an_ack_against_a_raised_ceiling_with_nothing_durable_is_a_no_op() -> None:
    """Reading 7's truth update (P9-R2): the criterion is ``exposure_level``
    and not the ceiling, because a ceiling raised by the released half is a
    *possible* exposure rather than a confirmable one — the row comes back as
    it is, certainty included."""

    nothing_durable = _estimate(
        terminal_state=PARTIAL,
        sent_prefix="",
        full_text_length=10,
        released="abcd",
    )
    assert nothing_durable.max_possible_exposure == "PARTIAL"
    assert refine_with_ack(nothing_durable, ack=FINAL_ACK) is nothing_durable


def test_the_reason_text_is_deterministic_and_names_the_boundary() -> None:
    """Reading 5: the store compares the reason as content, so the same facts
    must produce the same bytes — and the bytes must name what the columns
    mean (how much was sent, and why the level is what it is)."""

    first = _estimate(terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10)
    second = _estimate(terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10)
    assert first.derivation_reason == second.derivation_reason
    assert first.derivation_reason == (
        "sent 4 of 10 chars; partial send; no render ack"
    )
    assert _estimate(
        terminal_state=SENT, sent_prefix="abcdefghij", full_text_length=10
    ).derivation_reason == "sent 10 of 10 chars; no render ack"
    assert _estimate(
        terminal_state=SENT, sent_prefix="abcd", full_text_length=10
    ).derivation_reason == (
        "sent 4 of 10 chars; the sent prefix is short of the validated text;"
        " no render ack"
    )
    assert _estimate(
        terminal_state=CANCELLED, sent_prefix="abcd"
    ).derivation_reason == "sent 4 chars; the send was cancelled; no render ack"
    assert _estimate(
        terminal_state=FAILED, sent_prefix=""
    ).derivation_reason == (
        "nothing was sent; the delivery failed; no render ack"
    )


def test_the_action_id_is_the_callers_and_the_reason_ignores_it() -> None:
    other = exposure_estimate_of(
        action_id=ActionId("ga-another-action"),
        facts=DeliveryExposureFacts(
            terminal_state=PARTIAL, sent_prefix="abcd", send_attempted=True
        ),
    )
    assert other.action_id == ActionId("ga-another-action")
    assert other.derivation_reason == _estimate(
        terminal_state=PARTIAL, sent_prefix="abcd"
    ).derivation_reason


@pytest.mark.parametrize("state", ["SENDING", "NOT_SENT"])
def test_an_open_delivery_row_has_no_estimate(state: str) -> None:
    """The estimate is CP3a's record of a *frozen* delivery; a caller asking
    about an open row is asking the wrong question, and the module says so
    instead of inventing a level for it."""

    with pytest.raises(ValueError, match="frozen delivery"):
        _estimate(terminal_state=state, sent_prefix="abcd")


def test_the_vocabularies_are_the_canonical_ones() -> None:
    assert DELIVERY_STATES_WITH_AN_ESTIMATE == (
        "SENT_COMPLETE",
        "SENT_PARTIAL",
        "FAILED",
        "CANCELLED",
    )
    # the ladders are the enums' own words, ordered by what they mean (the
    # enums are declared in canonical §13 order, which is not the ladder's)
    assert ACK_CERTAINTY_LADDER == (
        "UNKNOWN",
        "SERVER_SENT_UNCONFIRMED",
        "CONFIRMED_RENDERED",
    )
    assert set(ACK_CERTAINTY_LADDER) == {
        member.value for member in ExposureEstimateCertainty
    }
    assert EXPOSURE_LEVEL_LADDER == ("NONE", "PARTIAL", "FULL")
    assert set(EXPOSURE_LEVEL_LADDER) == {
        member.value for member in AnswerExposureState
    }
    # the table's spellings are the enums' (no second spelling anywhere)
    assert SENT == DeliveryState.SENT_COMPLETE.value
    assert SERVER == ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED.value
    assert UNKNOWN == ExposureEstimateCertainty.UNKNOWN.value


def test_the_ranks_are_the_ladders_and_a_foreign_word_raises() -> None:
    assert [certainty_rank(word) for word in ACK_CERTAINTY_LADDER] == [0, 1, 2]
    assert [exposure_rank(word) for word in EXPOSURE_LEVEL_LADDER] == [0, 1, 2]
    with pytest.raises(ValueError, match="certainty"):
        certainty_rank("MAYBE")
    with pytest.raises(ValueError, match="exposure word"):
        exposure_rank("MOSTLY")


# -- ② the acknowledgment: upward only ----------------------------------------


def test_a_non_final_ack_confirms_the_render_but_not_the_send() -> None:
    """Reading 6: coverage is what confirms a level, and only the final
    acknowledgment covers what the server sent — a chunk-level acknowledgment
    says a render happened and nothing more (the conservative direction)."""

    partial = _estimate(
        terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10
    )
    ack = replace(FINAL_ACK, rendered_chunk_seq=1, final_rendered=False)
    refined = refine_with_ack(partial, ack=ack)
    assert refined.certainty == "CONFIRMED_RENDERED"
    assert refined.confirmed_exposure == "NONE"  # not the coverage arm
    assert refined.exposure_level == partial.exposure_level == "PARTIAL"
    assert refined.max_possible_exposure == "PARTIAL"
    assert "render ack for chunk 1" in refined.derivation_reason
    assert "no render ack" not in refined.derivation_reason


def test_a_final_ack_confirms_exactly_what_the_server_sent() -> None:
    full = _estimate(
        terminal_state=SENT, sent_prefix="abcdefghij", full_text_length=10
    )
    refined = refine_with_ack(full, ack=FINAL_ACK)
    assert refined.certainty == "CONFIRMED_RENDERED"
    assert refined.confirmed_exposure == "FULL"
    assert refined.exposure_level == "FULL"
    assert refined.derivation_reason == (
        "sent 10 of 10 chars; render ack for chunk 3 (final): everything the"
        " server sent was rendered"
    )
    # and a partial send is confirmed only up to what was sent
    partial = _estimate(
        terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10
    )
    confirmed = refine_with_ack(partial, ack=FINAL_ACK)
    assert confirmed.confirmed_exposure == "PARTIAL"  # never FULL


@pytest.mark.parametrize("certainty", ACK_CERTAINTY_LADDER)
@pytest.mark.parametrize("confirmed", EXPOSURE_LEVEL_LADDER)
@pytest.mark.parametrize(
    "shape", ["final-complete", "non-final-complete", "final-partial"]
)
def test_no_column_ever_moves_down(
    shape: str, confirmed: str, certainty: str
) -> None:
    """The invariant all the other refinement tests lean on, as a matrix: every
    (certainty, confirmed) starting pair §13 can spell, crossed with the three
    acknowledgment shapes that matter, and for each one — whatever the
    acknowledgment — ``certainty`` and ``confirmed_exposure`` keep their rank or
    rise, while the sent level does not move at all."""

    if shape.endswith("complete"):
        base = _estimate(
            terminal_state=SENT, sent_prefix="abcdefghij", full_text_length=10
        )
    else:
        base = _estimate(
            terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10
        )
    before = replace(
        base, certainty=certainty, confirmed_exposure=confirmed
    )
    after = refine_with_ack(
        before,
        ack=replace(FINAL_ACK, final_rendered=shape.startswith("final")),
    )
    assert certainty_rank(after.certainty) >= certainty_rank(before.certainty)
    assert exposure_rank(after.confirmed_exposure) >= exposure_rank(
        before.confirmed_exposure
    )
    assert after.exposure_level == before.exposure_level
    assert after.max_possible_exposure == before.max_possible_exposure
    assert after.action_id == before.action_id


def test_a_repeated_ack_returns_the_same_row_and_writes_nothing_new() -> None:
    """Idempotence at the pure face: the second application of one
    acknowledgment is the first one's row, byte for byte (which is what makes
    the durable write a replay rather than a second fact)."""

    before = _estimate(
        terminal_state=SENT, sent_prefix="abcdefghij", full_text_length=10
    )
    once = refine_with_ack(before, ack=FINAL_ACK)
    twice = refine_with_ack(once, ack=FINAL_ACK)
    assert twice == once
    assert refine_with_ack(twice, ack=FINAL_ACK) == once
    # already-confirmed input: nothing to raise, so the row is returned as is
    assert refine_with_ack(once, ack=FINAL_ACK) is once


def test_an_ack_against_nothing_sent_is_a_no_op() -> None:
    """Reading 7: the durable record says nothing was sent, so there is no
    rendering for an acknowledgment to confirm — a client claiming otherwise
    cannot make the server claim an exposure the delivery did not have."""

    nothing = _estimate(terminal_state=FAILED, sent_prefix="")
    assert refine_with_ack(nothing, ack=FINAL_ACK) is nothing
    no_row = _estimate(terminal_state=None, sent_prefix="", attempted=False)
    assert refine_with_ack(no_row, ack=FINAL_ACK) is no_row


def test_an_ack_for_another_action_is_refused() -> None:
    estimate = _estimate(terminal_state=PARTIAL, sent_prefix="abcd")
    with pytest.raises(ValueError, match="acknowledgment names action"):
        refine_with_ack(
            estimate, ack=replace(FINAL_ACK, action_id=ActionId("ga-other"))
        )


def test_refinement_refusal_accepts_the_refined_row_and_refuses_the_moves() -> None:
    """The durable face's rule, on the pure spelling: a legal refinement is
    accepted; a lower certainty, a lower confirmation, a renamed action and a
    moved sent level are each refused with ``VALIDATION_FAILED``."""

    before = _estimate(
        terminal_state=PARTIAL, sent_prefix="abcd", full_text_length=10
    )
    legal = refine_with_ack(before, ack=FINAL_ACK)
    assert refinement_refusal(before, legal) is None
    assert refinement_refusal(before, before) is None
    # a certainty raise that moves nothing else is legal too
    raise_only = replace(before, certainty="CONFIRMED_RENDERED")
    assert refinement_refusal(before, raise_only) is None

    for base, illegal, _sentence in ILLEGAL_MOVES:
        refusal = refinement_refusal(base, illegal)
        assert refusal is not None, illegal
        assert refusal.code is DomainErrorCode.VALIDATION_FAILED


@pytest.mark.parametrize("index", range(len(ILLEGAL_MOVES)))
def test_each_illegal_move_is_refused_with_its_own_sentence(index: int) -> None:
    """One case per illegal move (the test above proves the class; this names
    each sentence so a refusal cannot be refused for the wrong reason)."""

    base, illegal, expected = ILLEGAL_MOVES[index]
    refusal = refinement_refusal(base, illegal)
    assert refusal is not None
    assert refusal.code is DomainErrorCode.VALIDATION_FAILED
    assert expected in refusal.message, (expected, refusal.message)


# -- ③ the module is SQL-free, clock-free and ledger-free (R4) ----------------


MODULE_PATH = SRC_ROOT / "runtime" / "exposure_reconciliation.py"
CONTROLLER_PATH = SRC_ROOT / "runtime" / "controller.py"


def _imported_modules(path: object) -> set[str]:
    tree = ast.parse(Path(str(path)).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported

def _method(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"no method {name!r}")


def _code_of(method: ast.FunctionDef) -> str:
    """One method's code without its docstring — prose is not a call surface,
    and a docstring that *names* the face this test forbids is not a call to
    it (the same reason the repository's other AST pins strip docstrings
    before comparing)."""

    stripped = copy.deepcopy(method)
    stripped.body = [
        statement
        for statement in stripped.body
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        )
    ]
    return ast.unparse(stripped)


def test_the_module_import_set_is_the_declared_one() -> None:
    """Declared and asserted by equality (the P8-4/P9-2 discipline): the
    derivation reads the conversation's delivery words, the platform's types,
    the §22 row shapes and the teaching enumerations — no database module, no
    ledger and no clock."""

    imported = _imported_modules(MODULE_PATH)
    assert imported == {
        "__future__",
        "dataclasses",
        "elc.conversation.types",
        "elc.platform.types",
        "elc.runtime.delivery_records",
        "elc.teaching.types",
    }
    assert not [
        name
        for name in imported
        if name.startswith("elc.platform.db")
        or name.startswith("elc.planner")
    ]
    assert "sqlite3" not in imported and "datetime" not in imported


def test_the_module_carries_no_sql_call_surface_and_no_sql_text() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in (
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            ), node.func.attr
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            for marker in (
                "insert into",
                "update ",
                "delete from",
                "create table",
            ):
                assert marker not in lowered, node.value


def test_the_delivery_kind_table_is_the_dispatched_slots() -> None:
    """The reconciliation reads an action id back to learn *which* kind it
    delivered, and the slot is the only durable carrier of that (a retry and a
    hint share one action type). The table is pinned against the dispatch sites:
    every literal ``slot=`` the controller spells is a key, the continuation's
    dynamic slots (the delivery kinds lowercased) are keys too, and an unknown
    slot answers ``None`` rather than a guessed word."""

    from elc.runtime.controller import (
        CONTINUATION_ACTION_BY_DELIVERY,
        DELIVERY_KIND_BY_SLOT,
        delivery_kind_of_action,
    )

    assert DELIVERY_KIND_BY_SLOT == {
        "teaching-open": "OPENING",
        "automatic-open": "OPENING",
        "hint": "HINT",
        "retry": "RETRY",
        "reveal": "REVEAL",
        "explanation": "EXPLANATION",
        "resume": "RESUME",
    }
    assert delivery_kind_of_action(ActionId("ga-turn-1-automatic-open")) == "OPENING"
    assert delivery_kind_of_action(ActionId("ga-turn-1-hint")) == "HINT"
    assert delivery_kind_of_action(ActionId("ga-turn-1-resume")) == "RESUME"
    assert delivery_kind_of_action(ActionId("ga-turn-1-unknown")) is None
    # the longest matching suffix wins
    assert delivery_kind_of_action(ActionId("ga-x-reveal-hint")) == "HINT"
    assert delivery_kind_of_action(ActionId("ga-x-hint-reveal")) == "REVEAL"

    tree = ast.parse(CONTROLLER_PATH.read_text(encoding="utf-8"))
    literals = {
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "slot"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }
    assert literals <= set(DELIVERY_KIND_BY_SLOT), literals
    # the continuation's dynamic spelling is the delivery kind lowercased
    assert {kind.lower() for kind in CONTINUATION_ACTION_BY_DELIVERY} <= set(
        DELIVERY_KIND_BY_SLOT
    )


def test_the_estimate_path_names_no_section_20_write() -> None:
    """R4's one-way rule, pinned on the controller's estimate writer: the
    initial estimate and the acknowledgment entry both write §22 rows and
    neither names a §20 exposure write — the ledger's own appends belong to the
    delivery leg (``_with_exposure``) and to the reconciliation's
    exactly-once helper."""

    tree = ast.parse(CONTROLLER_PATH.read_text(encoding="utf-8"))
    forbidden = (
        "record_exposure",
        "record_event",
        "record_skip",
        "record_ledger_event",
        "ledger_event_of",
        "exposure_event_id",
        "apply_ledger_event",
        "_with_exposure",
        "_ensure_exposure_once",
    )
    for name in ("_write_initial_estimate", "accept_render_ack"):
        body = _code_of(_method(tree, name))
        for word in forbidden:
            assert word not in body, (name, word)

    writer = _code_of(_method(tree, "_write_initial_estimate"))
    # and the two §22 faces it does use are the ones declared
    assert "record_initial_exposure_estimate" in writer
    assert "exposure_estimate_of" in writer
    ack = _code_of(_method(tree, "accept_render_ack"))
    assert "append_client_render_ack" in ack
    assert "refine_with_ack" in ack
    assert "refine_exposure_estimate" in ack
    # the ACK entry is asynchronous (RA §6): it takes no coordinator guard
    assert "_lease" not in ack
