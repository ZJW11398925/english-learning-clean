"""The §22 exposure estimate's derivation, and the one refinement §14 allows (P9-4).

docs/DATA_MODEL.md §22 names ``ExposureEstimate``'s six columns, docs/
RUNTIME_ARCHITECTURE.md §6 **CP3a** commits the "initial ExposureEstimate"
beside the server delivery record and the canonical assistant turn, and RA §14
is the semantic rule the three layers carry: "服务端不宣称知道人类真的看到",
teaching evidence uses "confirmed exposure where available, otherwise
max-possible-exposure", and "late ClientRenderAck 只作为 certainty
refinement". STATE_MACHINES §13 spells the only vocabularies canonical text
declares for those columns — three ``certainty`` words and three
``exposure_level`` words — and §13's ServerDeliveryRecord block spells the six
delivery states the derivation reads.

**What this module is.** A pure mapping, in two directions:

- :func:`exposure_estimate_of` turns the durable facts one delivery left — its
  §13 terminal word, the durable ``sent_prefix``, whether the validated whole
  is known — into the estimate's five value columns (the sixth, ``action_id``,
  is the caller's);
- :func:`refine_with_ack` applies one §22 ``ClientRenderAck`` to an existing
  estimate: the two columns RA §14 lets an acknowledgment move
  (``certainty``, ``confirmed_exposure``) rise, nothing else moves, and an
  acknowledgment that raises nothing returns the row byte-identical.

No clock, no connection, no database and no ledger: this module imports no
sqlite3, no ``elc.platform.db``, calls no ``execute``-family method and
carries no statement text — the runtime package's Gate item 2 posture, and
R4's one-way rule taken literally: an estimate describes a delivery, it never
appends a §20 presentation event and never opens a teaching path.

---------------------------------------------------------------------------
**The derivation, stated once** (R2's table; every row is a reading, and the
re-open condition is beside it)
---------------------------------------------------------------------------

The input is :class:`DeliveryExposureFacts`. ``exposure_level`` is the **sent**
level — what the server can prove it put on the wire — and
``max_possible_exposure`` is the ceiling §14's conservative rule uses: the
higher of that level and the **released** level (reading 11 — what the client
boundary received, which a stopped run leaves ahead of its record).
``confirmed_exposure`` is what an acknowledgment later confirms (``NONE``
here: no acknowledgment has arrived when the row is first written).

===============  =========  =====  =====  =====  ==========
§13 terminal     prefix     level  max    conf.  certainty
===============  =========  =====  =====  =====  ==========
``SENT_COMPLETE``  non-empty  FULL   FULL   NONE   ``SERVER_SENT_UNCONFIRMED``
``SENT_COMPLETE``* non-empty  PART.  PART.  NONE   ``SERVER_SENT_UNCONFIRMED``
``SENT_PARTIAL``   non-empty  PART.  PART.  NONE   ``SERVER_SENT_UNCONFIRMED``
``CANCELLED``      non-empty  PART.  PART.  NONE   ``SERVER_SENT_UNCONFIRMED``
``FAILED``         non-empty  PART.  PART.  NONE   ``SERVER_SENT_UNCONFIRMED``
``FAILED``         empty      NONE   NONE   NONE   ``SERVER_SENT_UNCONFIRMED``
no row             —          NONE   NONE   NONE   ``UNKNOWN``
any (row)          empty      NONE   NONE   NONE   ``SERVER_SENT_UNCONFIRMED``
===============  =========  =====  =====  =====  ==========

``*`` the prefix is shorter than a validated length the caller *does* hold
(reading 1). ``FAILED`` is spelled out in both prefix shapes because reading 3
is about it: its empty arm is the general empty row's rule, stated again where
that reading names it. Every row's ``certainty`` is
:data:`~elc.teaching.types.ExposureEstimateCertainty`'s word and every level is
:data:`~elc.teaching.types.AnswerExposureState`'s; ``conf.`` is
``confirmed_exposure``.

Every row above is a shape whose released half is not held (``None``) or agrees
with the durable one, so ``max`` equals ``level`` in all of them. The two arms
where the released half is ahead of the record — the repair P9-R2 lands, reading
11 — are:

=====================  ================  =====  =====
durable prefix         released prefix   level  max
=====================  ================  =====  =====
short of validated     covers validated  PART.  FULL
empty                  non-empty         NONE   PART.
=====================  ================  =====  =====

In both, ``max`` is the higher of the two readings while ``exposure_level``
does not move: the record still says what it says, and §14's "confirmed
exposure where available, otherwise max-possible-exposure" reads a ceiling that
cannot understate what the client may hold.

The clauses that are readings rather than quotable rules:

1. **"Short of the validated text" is a real arm, and it is why the length is
   an input.** ``SENT_COMPLETE`` normally means the whole reply was sent, and
   with no second length to compare against that is what the word is taken to
   say (``full_text_length is None`` — the buffered face's atomic delivery, or
   a recovery reading the row alone). When the caller *does* hold the
   validated text's length and the durable prefix is shorter than it, the
   honest level is ``PARTIAL``: the row's word and the row's own boundary
   disagree, and §14's "宁可低估 independence，不高估" picks the boundary.
   Revisit: a shipped writer produces that pair (then it is a fact to explain,
   not a conservative fallback).
2. **An empty prefix is ``NONE`` whatever the word says.** The row's state
   word describes the run; §17 makes the *sent boundary* the durable fact the
   transcript is canonicalized from, and this derivation follows the same
   boundary — a word with nothing behind it is not exposure. That is the
   **level**; the ceiling may still sit above it when the released half is
   ahead of the record (reading 11: nothing durable is not the same fact as
   nothing released). This is the row
   P9-2 registered ("the send began and its record was lost") and it lands as
   ``NONE`` rather than as a smoothing of the word. The empty arm is checked
   **first**, so ``CANCELLED`` with nothing released reads like any other empty
   word — and the *turn outcome* of that shape is the one place two shipped
   faces are registered as diverging: the live barge-in arms
   (``elc.runtime.controller.finalize_streamed_delivery``'s interrupt stop,
   and the guard-invalidated faces reading ``_guard_invalidation_outcome``)
   keep ``CANCELLED_BY_USER`` for a cancellation the user's own act caused
   (their act is the fact, prefix or none), while the crash repair's
   empty-first rule (``_reconciled_turn_outcome``) answers
   ``NO_ASSISTANT_OUTPUT`` (the crash left no record of *which* stop it was,
   and the repair invents no user act). This module reads the boundary only —
   ``NONE`` under either reading. Revisit: canonical gives that shape a state
   word of its own.
3. **``FAILED`` with a non-empty prefix is ``PARTIAL``; its ``NONE`` needs the
   empty arm.** The two shipped writers cannot produce the pair "``FAILED``
   with a durable prefix" (the driver answers ``FAILED`` only when nothing was
   released, and a reconstructed failure that contradicts the durable prefix is
   refused by the record face) — so that arm is registered, not exercised, and
   it takes ``PARTIAL``: a boundary the record holds is text the client
   received, whatever word the run lost. ``FAILED`` with an empty prefix takes
   ``NONE`` the same way every other empty word does (reading 2's first-ness,
   not a rule of its own). Revisit: a writer produces the prefixed pair (then
   the word and the boundary need reconciling at that writer, not here).
4. **``send_attempted`` is the only thing that separates the two certainty
   words at derivation time.** ``SERVER_SENT_UNCONFIRMED`` is what the server
   knows when it *did* try to send (a row exists and the send began);
   ``UNKNOWN`` is the honest word when it cannot even say that (no row: the
   §22 face was never written for this action). §13's third word,
   ``CONFIRMED_RENDERED``, has no derivation-time producer on purpose — it is
   the acknowledgment's to give (:func:`refine_with_ack`).
5. **``derivation_reason`` is deterministic text, not a paraphrase.** The same
   facts produce the same bytes (the store compares it as content, and a
   re-entry must be a replay rather than a conflict): the phrase names how much
   was sent, the state word's own clause, and the no-acknowledgment tail. The
   tail is the marker :func:`refine_with_ack` replaces, so the refined row
   explains itself instead of carrying a sentence its own columns contradict.
   Revisit: canonical asks for structured (rather than textual) derivation
   traces.
6. **The ACK ladder is monotone, and only two columns may walk it.**
   :data:`ACK_CERTAINTY_LADDER` orders §13's three words and
   :data:`EXPOSURE_LEVEL_LADDER` orders the exposure scale;
   :func:`refine_with_ack` moves ``certainty`` to at least
   ``CONFIRMED_RENDERED`` and raises ``confirmed_exposure`` **only** when the
   acknowledgment is the final one — RA §14's "confirmed exposure where
   available": the client saying it rendered the final chunk of the stream is
   what confirms everything the server sent, and anything less confirms only
   that *some* rendering happened (so the level stays where it was — the
   conservative direction). The level a final acknowledgment confirms up to is
   the row's ``max_possible_exposure``; after reading 11 that column is the
   ceiling of what may have been released, which is what "everything the server
   sent" means once the record is known to lag the release.
   ``exposure_level`` and ``max_possible_exposure``
   never move: an acknowledgment changes what is *known*, never what was
   sent. Revisit: a cut shows an acknowledgment that can lower a column (then
   the ladder is the wrong shape and this reading is the one to reopen).
7. **An acknowledgment against a ``NONE`` *level* raises nothing.** The
   durable record says nothing was sent, so there is no rendering for an
   acknowledgment to confirm — a client claiming otherwise is either broken or
   replaying another action's event, and "confirm" is not a word the server may
   take from it. The function returns the estimate unchanged (no column moves
   down either). The criterion is ``exposure_level``, not the ceiling (P9-R2's
   truth update): a raised ``max_possible_exposure`` is a *possible* exposure,
   never a confirmable one, so reading 11's repair mints no object for an
   acknowledgment to move — the two columns read different facts, and only the
   durable one is the record's own word about a send. Revisit: canonical
   requires an acknowledgment to be recorded as a contradiction of the delivery
   record (then that record is the place), or makes an acknowledgment evidence
   about the released half (then this reading reopens).
8. **``rendered_text_hash`` is carried, never compared.** No face in this cut
   computes a hash of the durable prefix, so the coverage question is decided
   by ``final_rendered`` alone; the hash stays the acknowledgment's own
   content (it is written by the port like every other column). Revisit: a cut
   makes the prefix's hash computable — then the hash corroborates coverage
   and this reading retires.
9. **This module never writes mastery, evidence or an attempt, and it never
   touches the transcript.** §14's third sentence ("V1 不自动把已提交 Evidence
   升级为更独立的能力证据") is structural here: the module holds no such port,
   and the refined estimate is a delivery record — the transcript's
   ``delivery_certainty`` is the canonicalization's own column and no function
   here returns anything that could move it. Revisit: canonical gives a late
   acknowledgment a re-evaluation path (its own supersede trace), which this
   module would then describe rather than perform.
10. **V1 has no real client, so an acknowledgment is an injection.** The entry
    point that writes one (``elc.runtime.controller.ConversationCoordinator.
    accept_render_ack``) takes the §22 six columns from its caller; nothing in
    the shipped runtime produces one. Registered rather than simulated — the
    mapping above is exercised by its own suite, and the certainty words stay
    honest about which of them a real client has actually earned. Revisit: a
    delivery channel with a real client lands an acknowledgment.
11. **The released boundary is the ceiling's second half, and it does not read
    the state word.** §17 has two boundaries and this cut's facts carry both:
    ``sent_prefix`` is what the record confirmed, ``released_prefix`` is what
    the client boundary received. They differ exactly when a run stopped
    between the release and the record (a refused write, a crash) — the
    ``StreamRun`` that reports them says so in its own docstring. The run's
    word describes how the *run* ended, not what left the server: a
    ``SENT_PARTIAL`` that released every chunk put the whole text in the
    client's hands, so the released level is decided by the released length
    alone (at or above the validated length, or no length held at all —
    reading 1's own comparison) and **never** by ``terminal_state``. ``None``
    means the caller does not hold that half (the buffered face's atomic
    delivery, or a recovery face reading the row alone) and the ceiling falls
    back to the durable level. ``""`` is a concrete fact — the boundary
    released nothing — and it is a different fact from ``None`` even though the
    two agree on the row, deliberately: a fallback and a known-empty boundary
    are both read conservatively, and stating which one it was is the caller's
    half of the honesty. The ceiling is ``max(exposure_level, released level)``
    and only that column moves (R4: ``exposure_level``, ``certainty`` and
    ``confirmed_exposure`` are the durable reading's). When the ceiling is
    raised, ``derivation_reason`` gains one deterministic fragment naming the
    released length ("the client boundary may hold more than the record shows
    (released 2 of 4 chars)"), placed **before** the no-acknowledgment tail so
    reading 5's tail swap keeps it: a refined row whose ceiling sits above its
    level still explains itself. Revisit: canonical gives the released boundary
    a durable column of its own (then this half stops being a caller's fact and
    becomes a row's).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from elc.conversation.types import DeliveryState
from elc.platform.types import ActionId, DomainError, DomainErrorCode
from elc.runtime.delivery_records import (
    ClientRenderAck,
    ExposureEstimate,
)
from elc.teaching.types import (
    AnswerExposureState,
    ExposureEstimateCertainty,
)

__all__ = [
    "ACK_CERTAINTY_LADDER",
    "DELIVERY_STATES_WITH_AN_ESTIMATE",
    "EXPOSURE_LEVEL_LADDER",
    "DeliveryExposureFacts",
    "certainty_rank",
    "exposure_rank",
    "exposure_estimate_of",
    "refine_with_ack",
    "refinement_refusal",
]

#: §13's three ``certainty`` words in the order an acknowledgment may move them
#: (reading 6). The words are the enum's, never re-spelled here.
ACK_CERTAINTY_LADDER: tuple[str, ...] = (
    ExposureEstimateCertainty.UNKNOWN.value,
    ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED.value,
    ExposureEstimateCertainty.CONFIRMED_RENDERED.value,
)

#: §13's three exposure words, least to most (reading 6).
EXPOSURE_LEVEL_LADDER: tuple[str, ...] = (
    AnswerExposureState.NONE.value,
    AnswerExposureState.PARTIAL.value,
    AnswerExposureState.FULL.value,
)

#: The §13 words a frozen delivery can carry — the states the derivation
#: answers for. ``NOT_SENT`` / ``SENDING`` are not among them: the estimate is
#: CP3a's record, written after the row froze (reading 2's boundary), and a
#: caller asking about an open row is asking about a delivery that has not
#: happened yet.
DELIVERY_STATES_WITH_AN_ESTIMATE: tuple[str, ...] = (
    DeliveryState.SENT_COMPLETE.value,
    DeliveryState.SENT_PARTIAL.value,
    DeliveryState.FAILED.value,
    DeliveryState.CANCELLED.value,
)

#: The tail every derivation ends with, and the marker the refinement replaces
#: (reading 5).
_NO_ACK = "; no render ack"

#: The one fragment a raised ceiling adds, before the tail (reading 11).
_RELEASED_BEYOND_RECORD = (
    "; the client boundary may hold more than the record shows"
)

#: The two acknowledgment markers (the derivation's tail and the refinement's
#: own tail, in the order :func:`_base_reason` looks for them).
_ACK_MARKERS = (_NO_ACK, "; render ack")


def certainty_rank(word: str) -> int:
    """Where ``word`` sits on :data:`ACK_CERTAINTY_LADDER` (0 = ``UNKNOWN``).

    An unknown word raises: the ladder is total over §13's three words, and a
    caller asking about a fourth is asking a question with no answer.
    """

    if word not in ACK_CERTAINTY_LADDER:
        raise ValueError(
            f"certainty={word!r} is not one of §13's three words"
            f" ({', '.join(ACK_CERTAINTY_LADDER)})"
        )
    return ACK_CERTAINTY_LADDER.index(word)


def exposure_rank(word: str) -> int:
    """Where ``word`` sits on :data:`EXPOSURE_LEVEL_LADDER` (0 = ``NONE``)."""

    if word not in EXPOSURE_LEVEL_LADDER:
        raise ValueError(
            f"exposure word={word!r} is not one of §13's three words"
            f" ({', '.join(EXPOSURE_LEVEL_LADDER)})"
        )
    return EXPOSURE_LEVEL_LADDER.index(word)


def _higher(word: str, floor: str, ladder: tuple[str, ...]) -> str:
    """``word``, or ``floor`` when the floor sits higher on ``ladder``."""

    return floor if ladder.index(word) < ladder.index(floor) else word


@dataclass(frozen=True)
class DeliveryExposureFacts:
    """The durable facts one delivery left, as §22's estimate reads them.

    ``terminal_state`` is §13's word, or ``None`` for "no server delivery
    record exists for this action" (a different fact from a row that holds
    ``FAILED``). ``sent_prefix`` is the durable boundary §17 canonicalizes
    from. ``send_attempted`` is what the caller can attest about the send
    itself (reading 4). ``full_text_length`` is the validated text's length
    when the caller holds it; ``None`` means the caller holds no second length
    to compare against — the buffered face's atomic delivery, or a recovery
    face that reads the row alone — and then the state word is taken at its
    own word (reading 1).

    ``released_prefix`` is §17's **other** boundary and the ceiling's second
    half (reading 11): the text the client boundary received, which a run that
    stopped between the release and the record leaves ahead of
    ``sent_prefix``. ``None`` means the caller does **not hold** that half —
    the buffered face's atomic delivery, or a recovery face reading the row
    alone — and the ceiling falls back to the durable level. ``""`` is a
    concrete fact (the boundary released nothing), and it is not the same fact
    as ``None`` even though the two agree on the row: a fallback and a
    known-empty boundary both read conservatively, and this module states
    which one it was rather than letting a reader guess.
    """

    terminal_state: str | None
    sent_prefix: str
    send_attempted: bool
    full_text_length: int | None = None
    released_prefix: str | None = None

    @classmethod
    def streamed(
        cls,
        *,
        terminal_state: str,
        sent_prefix: str,
        validated_text: str,
        released_prefix: str,
    ) -> DeliveryExposureFacts:
        """The streamed face's facts: the run's word, **both** §17 boundaries
        and the validated text whose length the derivation compares them
        against.

        ``released_prefix`` is keyword-only and required here, unlike the
        dataclass field: this is the one caller that holds the released half
        (``StreamRun`` carries both by construction, since they differ exactly
        when a run stopped between the release and the record), and a
        streamed call that could not name it would be asking for reading 11's
        conservative fallback to be taken silently. A caller that reads a row
        alone is not this face; it constructs the facts directly and says
        ``released_prefix=None``.
        """

        return cls(
            terminal_state=terminal_state,
            sent_prefix=sent_prefix,
            send_attempted=True,
            full_text_length=len(validated_text),
            released_prefix=released_prefix,
        )

    @classmethod
    def buffered(
        cls,
        *,
        text: str,
        state: DeliveryState = DeliveryState.SENT_COMPLETE,
    ) -> DeliveryExposureFacts:
        """The buffered face's facts: validated whole, delivered whole (RA
        §13's "provider complete → full validation → delivery"). There is no
        partial boundary to compare a length against, so the length is
        ``None`` and the word the caller declares is the fact."""

        return cls(
            terminal_state=state.value,
            sent_prefix=text,
            send_attempted=True,
            full_text_length=None,
        )

    @property
    def sent_length(self) -> int:
        """How much text the durable boundary holds."""

        return len(self.sent_prefix)

    def covers_the_whole_text(self) -> bool:
        """Whether the durable boundary covers the validated text: always true
        when no second length is held (reading 1), otherwise a comparison."""

        if self.full_text_length is None:
            return True
        return self.sent_length >= self.full_text_length


def _sent_level(facts: DeliveryExposureFacts) -> str:
    """The level the durable boundary proves (readings 1-3's table)."""

    none = AnswerExposureState.NONE.value
    partial = AnswerExposureState.PARTIAL.value
    full = AnswerExposureState.FULL.value
    if facts.sent_prefix == "":
        return none
    if (
        facts.terminal_state == DeliveryState.SENT_COMPLETE.value
        and facts.covers_the_whole_text()
    ):
        return full
    return partial


def _released_level(facts: DeliveryExposureFacts) -> str:
    """The level the **released** boundary may hold — reading 11's ceiling half.

    ``None`` (the caller does not hold the half) and ``""`` (the boundary
    released nothing) both fall back to the durable level, which is reading
    11's conservative direction. Otherwise the comparison is against the
    validated length alone — and **not** against ``terminal_state``: the word
    describes how the run ended, while the question here is what the client
    boundary received, which a stopped run can leave ahead of its record.
    """

    released = facts.released_prefix
    if released is None or released == "":
        return _sent_level(facts)
    length = facts.full_text_length
    if length is None or len(released) >= length:
        return AnswerExposureState.FULL.value
    return AnswerExposureState.PARTIAL.value


def _released_beyond_record(facts: DeliveryExposureFacts) -> str:
    """The one fragment a raised ceiling adds (reading 11).

    Deterministic in the released length, and placed before :data:`_NO_ACK` by
    :func:`_reason` so reading 5's tail swap keeps it.
    """

    released = len(facts.released_prefix or "")
    length = facts.full_text_length
    detail = (
        f"released {released} chars"
        if length is None
        else f"released {released} of {length} chars"
    )
    return f"{_RELEASED_BEYOND_RECORD} ({detail})"


def _reason(facts: DeliveryExposureFacts, level: str, ceiling: str) -> str:
    """The deterministic derivation text (reading 5).

    ``ceiling`` only decides whether reading 11's fragment is present; the
    level's own bytes are unchanged when it is not, so a row whose released
    half is not held (or agrees) keeps the exact text this module has always
    written.
    """

    full = AnswerExposureState.FULL.value
    if facts.sent_length == 0:
        sent = "nothing was sent"
    elif facts.full_text_length is None:
        sent = f"sent {facts.sent_length} chars"
    else:
        sent = (
            f"sent {facts.sent_length} of {facts.full_text_length} chars"
        )
    clause = {
        DeliveryState.SENT_COMPLETE.value: (
            "" if level == full else "; the sent prefix is short of the validated text"
        ),
        DeliveryState.SENT_PARTIAL.value: "; partial send",
        DeliveryState.CANCELLED.value: "; the send was cancelled",
        DeliveryState.FAILED.value: "; the delivery failed",
        None: "; no server delivery record",
    }.get(facts.terminal_state, "; the delivery did not complete")
    beyond = "" if ceiling == level else _released_beyond_record(facts)
    return f"{sent}{clause}{beyond}{_NO_ACK}"


def exposure_estimate_of(
    *, action_id: ActionId, facts: DeliveryExposureFacts
) -> ExposureEstimate:
    """§22's estimate for one action, from the facts its delivery left (R2).

    ``action_id`` is the caller's: §22's block carries it and this function
    mints no identity. The five value columns are the table in this module's
    docstring; ``max_possible_exposure`` is that table's ``max`` — the higher
    of the durable level and reading 11's released level, so the ceiling never
    understates what the client boundary may hold. A word outside §13's
    terminal four raises, because the estimate is the record of a *frozen*
    delivery and a caller asking about an open row is asking the wrong question
    (see the constant's docstring).
    """

    state = facts.terminal_state
    if state is not None and state not in DELIVERY_STATES_WITH_AN_ESTIMATE:
        raise ValueError(
            f"terminal_state={state!r} is not one of §13's frozen delivery"
            f" words ({', '.join(DELIVERY_STATES_WITH_AN_ESTIMATE)}) or None;"
            " the §22 estimate is CP3a's record of a delivery that ended"
        )
    level = _sent_level(facts)
    # reading 11: the same one-way helper the acknowledgment ladder uses, so a
    # released half behind the record can never lower the ceiling either.
    ceiling = _higher(level, _released_level(facts), EXPOSURE_LEVEL_LADDER)
    return ExposureEstimate(
        action_id=action_id,
        certainty=(
            ExposureEstimateCertainty.SERVER_SENT_UNCONFIRMED.value
            if facts.send_attempted
            else ExposureEstimateCertainty.UNKNOWN.value
        ),
        exposure_level=level,
        max_possible_exposure=ceiling,
        confirmed_exposure=AnswerExposureState.NONE.value,
        derivation_reason=_reason(facts, level, ceiling),
    )


def _base_reason(reason: str) -> str:
    """``reason`` without whatever acknowledgment tail it already carries."""

    for marker in _ACK_MARKERS:
        index = reason.find(marker)
        if index >= 0:
            return reason[:index]
    return reason


def _refined_reason(estimate: ExposureEstimate, ack: ClientRenderAck) -> str:
    """The refined row's own explanation (reading 5's tail swap)."""

    if ack.final_rendered:
        note = (
            f"; render ack for chunk {ack.rendered_chunk_seq} (final):"
            " everything the server sent was rendered"
        )
    else:
        note = (
            f"; render ack for chunk {ack.rendered_chunk_seq}:"
            " the client rendered part of what was sent"
        )
    return _base_reason(estimate.derivation_reason) + note


def refine_with_ack(
    estimate: ExposureEstimate, *, ack: ClientRenderAck
) -> ExposureEstimate:
    """One acknowledgment applied to one estimate — upward only (readings 6-8).

    Returns ``estimate`` itself when nothing rises, so a replayed
    acknowledgment leaves the row byte-identical (the port's replay rule then
    needs no second write). ``max_possible_exposure`` / ``exposure_level``
    never move, ``certainty`` rises to at least ``CONFIRMED_RENDERED``, and
    ``confirmed_exposure`` reaches the ceiling (``max_possible_exposure`` —
    after reading 11 the highest level that may have been released) only for
    the final acknowledgment, the coverage reading 6 states. Reading 7's
    criterion is the **level** column: a raised ceiling is a possible
    exposure, not a confirmable one.
    """

    if ack.action_id != estimate.action_id:
        raise ValueError(
            f"acknowledgment names action {ack.action_id} while the estimate"
            f" is {estimate.action_id}; a refinement applies to the delivery"
            " it acknowledges"
        )
    if exposure_rank(estimate.exposure_level) == 0:
        return estimate  # reading 7: nothing was sent, so nothing is confirmable
    certainty = _higher(
        estimate.certainty,
        ExposureEstimateCertainty.CONFIRMED_RENDERED.value,
        ACK_CERTAINTY_LADDER,
    )
    confirmed = estimate.confirmed_exposure
    if ack.final_rendered:
        confirmed = _higher(
            confirmed, estimate.max_possible_exposure, EXPOSURE_LEVEL_LADDER
        )
    if (
        certainty == estimate.certainty
        and confirmed == estimate.confirmed_exposure
    ):
        return estimate
    return replace(
        estimate,
        certainty=certainty,
        confirmed_exposure=confirmed,
        derivation_reason=_refined_reason(estimate, ack),
    )


def refinement_refusal(
    before: ExposureEstimate, after: ExposureEstimate
) -> DomainError | None:
    """Why ``after`` may not replace ``before``, or ``None`` when it may.

    The durable face's rule, stated in one place so the adapter and the
    refinement's own suite read the same spelling: an acknowledgment refines
    ``certainty`` and ``confirmed_exposure`` upward, leaves the sent level
    exactly as the derivation wrote it, and never renames the action. A
    submission that would move any of those differently is refused with
    ``VALIDATION_FAILED`` (the caller's data is not a legal refinement) rather
    than being smoothed into the row — the estimate is what the evidence was
    attributed from, so a face that could move its level downward would be a
    second, quieter derivation.
    """

    if after.action_id != before.action_id:
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"a refinement of estimate {before.action_id} may not name"
                f" {after.action_id}: the action is the row's identity"
            ),
        )
    for column, was, now in (
        (
            "exposure_level",
            before.exposure_level,
            after.exposure_level,
        ),
        (
            "max_possible_exposure",
            before.max_possible_exposure,
            after.max_possible_exposure,
        ),
    ):
        if was != now:
            return DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"the refinement moves {column} from {was!r} to {now!r};"
                    " an acknowledgment changes what is known, never what was"
                    " sent (the sent level is the derivation's)"
                ),
            )
    if certainty_rank(after.certainty) < certainty_rank(before.certainty):
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"the refinement moves certainty from {before.certainty!r} to"
                f" {after.certainty!r}; an acknowledgment only raises it"
            ),
        )
    if exposure_rank(after.confirmed_exposure) < exposure_rank(
        before.confirmed_exposure
    ):
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                "the refinement moves confirmed_exposure from"
                f" {before.confirmed_exposure!r} to"
                f" {after.confirmed_exposure!r}; an acknowledgment only"
                " raises it"
            ),
        )
    return None
