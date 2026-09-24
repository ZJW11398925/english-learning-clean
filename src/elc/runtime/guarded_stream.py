"""GUARDED_STREAM — the chunk guard and its pure driver (P9-2).

docs/RUNTIME_ARCHITECTURE.md §13 names two delivery modes. ``BUFFERED_VALIDATED``
is "provider complete → full validation → delivery" (the shipped path: the
whole answer is validated and then canonicalized once); ``GUARDED_STREAM`` is
the one "默认用于普通 persona chat" and it asks for exactly four things:

    small buffer / chunk guard
    server delivery tracking
    client render ack where possible
    late callback protection

This module is the first of those four and nothing else: the chunk vocabulary,
the transport port a source plugs into, the mode table §13's default column
states, and the pure driver that releases chunks one at a time — each one
through the guard, before it is released. The server-side tracking (the §22
``ServerDeliveryRecord``) is the caller's face (``elc.runtime.controller``
holds it, ``elc.platform.db.delivery_store`` writes it), and the ACK / late
callback halves are later cuts' (P9-3/P9-4).

The module holds **no clock** (``docs/RUNTIME_ARCHITECTURE.md`` instants are the
caller's: every instant column of a delivery record arrives on the record, the
p9-1 reading) and **no database**: it imports no sqlite3, no ``elc.platform.db``,
calls no ``execute``-family method and carries no statement text — the runtime
package's Gate item 2 posture against a store that *is* the driver's argument.

---------------------------------------------------------------------------
**The driver's rules — each one a reading, each with its re-open condition**
---------------------------------------------------------------------------

1. **One chunk in flight, and the guard runs before the release.**
   :data:`SMALL_BUFFER_CHUNKS` is ``1``: the driver holds no lookahead window —
   it takes a step, and the chunk that step carries is guarded *before* it is
   handed to the transport. §17 makes the sent boundary irreversible ("如果已发送
   部分内容：不自动从头重放"), so the only place a constraint can still act is
   before the release; a buffer of one is what that leaves. Revisit: canonical
   gives the guard a lookahead (a window the run may revise before release), or
   §17's "已发送即已发送" is revised.
2. **The guard is the shipped Response Validator, on the accumulated text.**
   Every chunk is judged by ``elc.persona.validator.ResponseValidator.decide``
   over the text the client would hold if that chunk were released (what has
   been released so far, plus this chunk), against the action's own
   ``GenerationContract``: the same rule set and the same
   :data:`~elc.persona.validator.VALIDATOR_VERSION` the buffered path validates
   the whole answer with. ``ACCEPT`` releases; anything else stops the run
   **before** the release, so the refused chunk never enters the prefix. The
   refusal is reported (:attr:`StreamRun.guard_decision` /
   :attr:`StreamRun.guard_reason_codes`), never swallowed. Revisit: canonical
   gives the streaming mode a rule set of its own (then §12's validator is not
   this guard's authority either).
3. **The driver does not trust the source.** A transport may hand over text
   beyond the validated buffer (that is what a real delta source does, and a
   test's scripted one can), so *every* chunk is guarded — the driver never
   treats "this was already validated once" as a property of a chunk. What the
   guard does not accept is not released, whichever side it came from.
   Revisit: a source arrives whose chunks are covered by a canonical
   provenance the guard would only be repeating.
4. **Release, then record (the order is a decision).** One chunk's accepted
   bytes go to the client boundary first (:meth:`StreamTransport.emit`) and are
   entered into the caller's record face second (``on_chunk``). A crash between
   the two therefore leaves the durable prefix *behind* what the boundary
   received — the conservative direction: the record under-reports what was
   sent, and the transcript (which is canonicalized from the durable prefix,
   §17's "canonicalize 已发送/确认边界") never claims text the record did not
   confirm. The opposite order would let a crash record bytes that never
   reached the client — a claim the runtime cannot take back. Revisit: a
   transport whose ``emit`` is itself durable (then the two steps are one).
5. **An empty chunk is guarded like any other.** The rule set's own
   no-output arm (``PROVIDER_NO_OUTPUT`` → ``RETRY``) applies to the
   accumulated text, so a *leading* empty chunk stops the run before anything
   is released (nothing has been accepted; the run ends ``FAILED`` with no
   prefix), while an empty chunk after real text is released as a zero-length
   chunk (the accumulator is non-empty, ``ACCEPT``, and the chunk sequence
   advances). Neither is special-cased: both are what applying rule 2 and rule
   3 literally means. Revisit: canonical gives the stream an explicit
   empty-chunk rule (then this reading retires in its favour).
6. **The terminal word comes from §13's six, and only three of them are this
   driver's.** ``SENT_COMPLETE`` when the source ended after at least one
   release; ``SENT_PARTIAL`` when the run stopped (early stop, a refused
   chunk, a failed transport, a failed record write, the step budget) after at
   least one release; ``FAILED`` when nothing was released at all. ``NOT_SENT``
   describes a row that never started, and ``SENDING`` is the open row the
   caller writes before the first chunk; ``CANCELLED`` is **not this driver's
   word** — §13's cancellation face (an interrupt request, a superseded action,
   an old worker's late callback) is P9-3's, and this module invents no
   cancellation semantics: a source's own reason travels through
   :attr:`StreamRun.stop_reason` verbatim, as data. Revisit: P9-3 lands and
   names the cancellation transitions (the words stay §13's; what this driver
   must stop claiming is that no other word exists).
7. **A source that never ends is stopped by the budget.**
   :data:`STREAM_STEP_BUDGET` bounds one run's steps, so an untrusted (or
   broken) source cannot hold the turn open forever. Exhausting it is a stop
   like any other: the prefix that was released stays, the reason is reported.
   Revisit: the transport protocol gains its own termination guarantee (then
   the budget is redundant and retires).
8. **This driver writes no §21.1 row.** The guard's verdict rides
   :class:`StreamRun` (and, for a stopped run, the caller's
   ``delivery_failure_reason``); the durable ``ValidatorResult`` /
   ``PreDeliveryGuardResult`` rows of §21.1 belong to the faces that own those
   checks (the Response Validator's own attempt face and §15's PreDeliveryGuard)
   and are not written here. Revisit: the PreDeliveryGuard lands on this path
   (then its row is written by that face, at that point, and this note moves).
9. **The mode table is §13's default column, and it fails closed.** The two
   words are the only two modes; every §20 action type has an entry
   (:data:`DELIVERY_MODE_BY_ACTION`), and an action type outside the table
   takes ``BUFFERED_VALIDATED`` — the fully-validated path is the stricter one,
   so an unknown shape never gets the weaker guard. §13 also lists *"high-risk
   disclosure-sensitive action"* under ``BUFFERED_VALIDATED``; V1 has no such
   action (the §20 action-type vocabulary has no high-risk member and no
   disclosure-sensitive classifier exists), so the row is registered as
   **without a carrier** rather than invented as a fake action type. Revisit:
   a real external provider or production candidate provider is switched on
   (the third production gate's trigger, kept in step with it) — a
   disclosure-sensitive classifier lands, and with it the table's fifth row.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Mapping, Protocol, runtime_checkable

from elc.conversation.types import DeliveryState
from elc.persona.types import (
    GenerationContract,
    ProviderOutput,
    ValidatorDecision,
)
from elc.persona.validator import ResponseValidator
from elc.platform.types import ActionId, Err, Ok, Result
from elc.runtime.types import GenerationActionType

__all__ = [
    "DELIVERY_MODE_BY_ACTION",
    "SMALL_BUFFER_CHUNKS",
    "STREAM_STEP_BUDGET",
    "DeliveryMode",
    "LocalSingleChunkTransport",
    "StreamRun",
    "StreamStep",
    "StreamStepKind",
    "StreamTransport",
    "StreamTransportFactory",
    "delivery_mode_of",
    "guard_verdict",
    "local_single_chunk_transport",
    "run_guarded_stream",
]

#: The one-chunk guard window (RA §13's "small buffer / chunk guard"): the
#: driver holds at most this many chunks before the guard has judged them, and
#: it holds none *through* a release — the chunk in hand is guarded, then
#: released, then forgotten. Revisit: the guard gains a lookahead window.
SMALL_BUFFER_CHUNKS = 1

#: One run's step budget: how many ``take()`` answers the driver reads before
#: it stops a source that never ends. Declared rather than derived (no
#: canonical number exists); it is a safety valve, not a delivery policy —
#: the prefix released before it is kept and reported. Revisit: the transport
#: protocol gains a termination guarantee of its own.
STREAM_STEP_BUDGET = 10_000


# ---------------------------------------------------------------------------
# The mode table (§13's default column)
# ---------------------------------------------------------------------------


class DeliveryMode(StrEnum):
    """docs/RUNTIME_ARCHITECTURE.md §13's two delivery modes."""

    BUFFERED_VALIDATED = "BUFFERED_VALIDATED"
    GUARDED_STREAM = "GUARDED_STREAM"


#: §20 action type → §13's default delivery mode. The table is total over the
#: shipped vocabulary (the readme of the enum is the §20 list) and the two
#: teaching types §13 does not name individually — ``TEACHING_EXPLANATION``
#: and ``PERSONA_RESUME`` — follow the three it does: an explanation is a
#: teaching presentation, and a resume is the teaching completion leg's own
#: delivery (RA §13's ``BUFFERED_VALIDATED`` column ("TEACHING_OPEN /
#: TEACHING_HINT / TEACHING_REVEAL") plus the delivery kinds the teaching
#: controller delivers). Revisit: canonical moves any of the six.
DELIVERY_MODE_BY_ACTION: Mapping[GenerationActionType, DeliveryMode] = {
    GenerationActionType.NORMAL_PERSONA_REPLY: DeliveryMode.GUARDED_STREAM,
    GenerationActionType.TEACHING_OPEN: DeliveryMode.BUFFERED_VALIDATED,
    GenerationActionType.TEACHING_HINT: DeliveryMode.BUFFERED_VALIDATED,
    GenerationActionType.TEACHING_REVEAL: DeliveryMode.BUFFERED_VALIDATED,
    GenerationActionType.TEACHING_EXPLANATION: DeliveryMode.BUFFERED_VALIDATED,
    GenerationActionType.PERSONA_RESUME: DeliveryMode.BUFFERED_VALIDATED,
}


def delivery_mode_of(action_type: object) -> DeliveryMode:
    """§13's default mode for one action type; unknown shapes fail closed.

    ``BUFFERED_VALIDATED`` is the stricter mode (the whole answer passes the
    validator before any byte leaves), so a value outside the table — a
    foreign action type, a plain string spelling of one — is answered with it
    rather than with the streaming mode. Reading 9 states the direction.
    """

    if isinstance(action_type, GenerationActionType):
        return DELIVERY_MODE_BY_ACTION[action_type]
    return DeliveryMode.BUFFERED_VALIDATED


# ---------------------------------------------------------------------------
# The source: steps and the transport port
# ---------------------------------------------------------------------------


class StreamStepKind(StrEnum):
    """The three shapes one ``take()`` can answer with."""

    CHUNK = "CHUNK"
    END = "END"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class StreamStep:
    """One step of a source: a chunk, a natural end, or an early stop.

    ``STOPPED.reason`` is the source's own words and travels through
    :attr:`StreamRun.stop_reason` **verbatim** — this module attaches no
    meaning to it (reading 6): a cancellation, an interrupt and a late
    callback are P9-3's vocabulary, not this driver's.
    """

    kind: StreamStepKind
    text: str = ""
    reason: str | None = None

    @staticmethod
    def chunk(text: str) -> StreamStep:
        """One chunk of text (possibly empty — reading 5)."""

        return StreamStep(kind=StreamStepKind.CHUNK, text=text)

    @staticmethod
    def end() -> StreamStep:
        """The source is complete: nothing more will be produced."""

        return StreamStep(kind=StreamStepKind.END)

    @staticmethod
    def stopped(reason: str) -> StreamStep:
        """The source stopped early, in its own words."""

        return StreamStep(kind=StreamStepKind.STOPPED, reason=reason)


@runtime_checkable
class StreamTransport(Protocol):
    """The client boundary of one streamed delivery.

    ``take`` answers the next step — the driver calls it until the source ends,
    stops, or the run is stopped. ``emit`` hands one accepted chunk to the
    client boundary and **may fail** (`Err`), which stops the run before
    anything of that chunk is recorded (reading 4). No face returns a
    cancellation: pausing, cancelling and superseding are not this port's
    (reading 6).
    """

    def take(self) -> StreamStep:
        """The next step of this source."""

        ...

    def emit(self, text: str) -> Result[None]:
        """Hand one guarded chunk to the client boundary (may fail)."""

        ...


@runtime_checkable
class StreamTransportFactory(Protocol):
    """Builds the transport for one delivery (the coordinator's injection
    point). It receives the validated buffer — for V1's in-process placeholder
    that is the whole answer — and the action the delivery belongs to, so a
    source that needs the action's identity has it without reaching for the
    coordinator."""

    def __call__(
        self, *, validated_text: str, action_id: ActionId
    ) -> StreamTransport: ...


class LocalSingleChunkTransport:
    """V1's transport: the validated text leaves as **one** chunk.

    The shipped assembly has no client render face (the interaction surface was
    postponed by ``DEC-…d7937fd7.12``), so ``emit`` writes into an in-process
    placeholder — the chunks this boundary received, readable through
    :attr:`emitted` for a caller that wants to see them — and the delivery's
    observable halves (transcript, delivery state, certainty, turn/action
    statuses) are exactly the buffered path's. Reading 1 is kept even here: the
    single chunk still goes through the guard before it is released, which is
    what makes "one chunk in flight" the default rather than a special case.
    """

    def __init__(self, text: str) -> None:
        self._steps: list[StreamStep] = [StreamStep.chunk(text), StreamStep.end()]
        self._index = 0
        self._emitted: list[str] = []

    @property
    def emitted(self) -> tuple[str, ...]:
        """What this boundary received, in order."""

        return tuple(self._emitted)

    def take(self) -> StreamStep:
        if self._index >= len(self._steps):
            return StreamStep.end()
        step = self._steps[self._index]
        self._index += 1
        return step

    def emit(self, text: str) -> Result[None]:
        self._emitted.append(text)
        return Ok(None)


def local_single_chunk_transport(
    *, validated_text: str, action_id: ActionId
) -> StreamTransport:
    """The default :class:`StreamTransportFactory`: V1's one-chunk source.

    ``action_id`` is accepted and unused — the placeholder source is
    action-independent — so that this callable *is* the factory protocol and
    the coordinator's default needs no adapter.
    """

    return LocalSingleChunkTransport(validated_text)


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StreamRun:
    """What one guarded run did — the honest half of a streamed delivery.

    Two prefixes, because reading 4 has two boundaries: ``sent_prefix`` is what
    the client boundary received, ``durable_prefix`` is what the caller's record
    face confirmed. They differ exactly when a run stopped between the release
    and the record (a failed write, a crash) — and the transcript is
    canonicalized from the **durable** one (§17), so the run reports both rather
    than letting a reader guess which one "the prefix" is.

    ``chunks`` counts the releases (an empty released chunk counts, reading 5);
    ``last_chunk_seq`` is the durable chunk sequence — the same number while the
    record face kept up. Every reason this run did not end ``SENT_COMPLETE`` is
    in ``failure_reason`` (and the source's own words, when it stopped, in
    ``stop_reason``): a stopped run is never silent.
    """

    state: str
    sent_prefix: str
    durable_prefix: str
    chunks: int
    last_chunk_seq: int
    stop_reason: str | None = None
    failure_reason: str | None = None
    guard_decision: str | None = None
    guard_reason_codes: tuple[str, ...] = ()


def guard_verdict(
    validator: ResponseValidator,
    contract: GenerationContract | None,
    accumulated_text: str,
) -> tuple[ValidatorDecision, tuple[str, ...]]:
    """Ask the shipped validator about the text a release would put in the
    client's hands — the one place the stream guard and the buffered path's
    full validation meet (reading 2)."""

    return validator.decide(ProviderOutput(text=accumulated_text), contract)


def run_guarded_stream(
    *,
    transport: StreamTransport,
    validator: ResponseValidator | None = None,
    contract: GenerationContract | None,
    on_chunk: Callable[[str, int], Result[None]] | None = None,
    step_budget: int = STREAM_STEP_BUDGET,
) -> StreamRun:
    """Drive one source through the guard, releasing chunk by chunk.

    The loop is readings 1-5 in order: take a step → guard the accumulated
    text → release (`emit`) → record (`on_chunk`). ``on_chunk`` receives the
    accumulated prefix *after* this chunk and the chunk's sequence number
    (1-based; the caller's row advance) and may refuse — a refused record stops
    the run with the durable prefix one chunk behind (reading 4), which is the
    conservative edge, never a lost one.

    ``validator`` defaults to the shipped :class:`ResponseValidator` itself —
    the guard's authority is ``elc.persona.validator``'s, not a copy of it —
    and the parameter exists so a caller (or a test) can hand over the same
    class wrapped in its own observability. No clock is read and nothing is
    stored: the whole run is a value (:class:`StreamRun`) built from what the
    two injected faces answered.
    """

    guard = validator if validator is not None else ResponseValidator()
    released: list[str] = []
    durable: list[str] = []
    last_chunk_seq = 0
    stop_reason: str | None = None
    failure_reason: str | None = None
    guard_decision: str | None = None
    guard_reason_codes: tuple[str, ...] = ()
    steps = 0

    while True:
        steps += 1
        if steps > step_budget:
            failure_reason = (
                f"the source exceeded this run's step budget ({step_budget})"
                " and was stopped"
            )
            break
        try:
            step = transport.take()
        except Exception as exc:  # noqa: BLE001 — the source boundary
            failure_reason = f"the stream source raised: {exc}"
            break

        if step.kind is StreamStepKind.END:
            break
        if step.kind is StreamStepKind.STOPPED:
            stop_reason = step.reason
            break
        if step.kind is not StreamStepKind.CHUNK:
            failure_reason = f"unknown stream step {step.kind!r}"
            break

        accumulated = "".join(released) + step.text
        decision, reason_codes = guard_verdict(guard, contract, accumulated)
        if decision is not ValidatorDecision.ACCEPT:
            guard_decision = decision.value
            guard_reason_codes = tuple(reason_codes)
            failure_reason = (
                "the guard refused the next chunk before it was released:"
                f" {decision.value} ({', '.join(reason_codes)})"
            )
            break

        emitted = transport.emit(step.text)
        if isinstance(emitted, Err):
            failure_reason = f"the transport refused the chunk: {emitted.error.message}"
            break
        released.append(step.text)

        recorded = (
            Ok(None) if on_chunk is None else on_chunk(accumulated, last_chunk_seq + 1)
        )
        if isinstance(recorded, Err):
            failure_reason = (
                "the delivery record refused the chunk"
                f" (it was already released): {recorded.error.message}"
            )
            break
        durable.append(step.text)
        last_chunk_seq += 1

    if not released:
        state = DeliveryState.FAILED
        if failure_reason is None:
            failure_reason = (
                "the source ended without releasing a chunk"
                if stop_reason is None
                else f"the source stopped before any chunk: {stop_reason}"
            )
    elif failure_reason is not None or stop_reason is not None:
        state = DeliveryState.SENT_PARTIAL
    else:
        state = DeliveryState.SENT_COMPLETE

    return StreamRun(
        state=state.value,
        sent_prefix="".join(released),
        durable_prefix="".join(durable),
        chunks=len(released),
        last_chunk_seq=last_chunk_seq,
        stop_reason=stop_reason,
        failure_reason=failure_reason,
        guard_decision=guard_decision,
        guard_reason_codes=guard_reason_codes,
    )
