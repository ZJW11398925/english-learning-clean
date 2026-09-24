"""P9-2 ① — the guarded stream driver, on its own two faces.

The driver is a pure function of a source and a record face, so this suite
hands it **scripted sources** (``ScriptedTransport``: the steps a test writes
down, in order) and a **spy record face** (``RecordingSink``: the accumulated
prefixes and sequences the driver handed over, in order). Nothing here touches
a database: the durable half of the delivery lives in
``tests/phase9/test_p9_2_stream_turn.py``.

What the assertions are for, one reading at a time (the module states them;
these are the cases that make each one falsifiable):

- a release happens exactly once per accepted chunk, and the prefix is the
  concatenation of what was released — never of what the source *offered*;
- the order is emit → record, and a stopped run's durable prefix can be one
  chunk behind its sent prefix (both directions are asserted, so the order
  cannot silently flip);
- the guard judges the **accumulation**, and its refusals are the shipped
  validator's decisions/reason codes — the byte that would break the contract
  never enters the prefix, and the transport is never asked for a chunk after
  the refusal (no lookahead);
- the six terminal shapes: a natural end, an early stop, a refused transport, a
  refused guard, a refused record, and a source that produced nothing;
- the source's own reason travels verbatim and this module invents no
  cancellation word (so a ``STOPPED("cancelled by the user")`` is data, not a
  transition);
- a source that never ends, a source that raises and a step kind this module
  does not know are all *stops with a reason*, never a hang and never an
  exception out of the driver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from elc.persona.types import (
    GenerationContract,
    ProviderOutput,
    ValidatorDecision,
)
from elc.persona.validator import ResponseValidator
from elc.platform.types import (
    ActionId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
)
from elc.runtime.guarded_stream import (
    SMALL_BUFFER_CHUNKS,
    DeliveryMode,
    LocalSingleChunkTransport,
    StreamRun,
    StreamStep,
    StreamStepKind,
    guard_verdict,
    local_single_chunk_transport,
    run_guarded_stream,
)
from elc.runtime.types import GenerationActionType

ACTION_ID = ActionId("act-p9-2-driver")

#: A reply long enough to be cut in three places by every test that wants a
#: multi-chunk run.
FULL_REPLY = "Sure — let's rehearse the past tense once more, slowly."


# -- the source a test scripts -------------------------------------------------


@dataclass
class ScriptedTransport:
    """A source whose steps are written down, with two failure switches.

    ``refuse_emit_at`` refuses the *n*-th release (1-based) with a
    ``UNAVAILABLE`` error, which is how a broken client boundary looks through
    the port; ``raise_on_step`` raises out of ``take`` instead of answering,
    which is how a broken source looks. Both are recorded (``events``), so a
    test can assert what the driver asked for and in which order.
    """

    steps: tuple[StreamStep, ...]
    refuse_emit_at: int | None = None
    raise_on_step: int | None = None
    events: list[str] | None = None

    def __post_init__(self) -> None:
        self._index = 0
        self._emit_calls = 0
        self.emitted: list[str] = []
        self.steps_taken = 0

    def take(self) -> StreamStep:
        self.steps_taken += 1
        if (
            self.raise_on_step is not None
            and self.steps_taken == self.raise_on_step
        ):
            raise RuntimeError("the source fell over")
        if self._index >= len(self.steps):
            return StreamStep.end()
        step = self.steps[self._index]
        self._index += 1
        return step

    def emit(self, text: str) -> Result[None]:
        self._emit_calls += 1
        if (
            self.refuse_emit_at is not None
            and self._emit_calls == self.refuse_emit_at
        ):
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message="the client boundary is gone",
                )
            )
        self.emitted.append(text)
        if self.events is not None:
            self.events.append(f"emit:{text}")
        return Ok(None)


class RecordingSink:
    """The record face a test watches: every (prefix, sequence) the driver
    confirmed, in order, with an optional refusal after ``refuse_after``."""

    def __init__(
        self,
        *,
        refuse_after: int | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, int]] = []
        self._refuse_after = refuse_after
        self._events = events

    def __call__(self, prefix: str, sequence: int) -> Result[None]:
        if (
            self._refuse_after is not None
            and len(self.calls) >= self._refuse_after
        ):
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message="the record face refused this chunk",
                )
            )
        self.calls.append((prefix, sequence))
        if self._events is not None:
            self._events.append(f"record:{sequence}:{prefix}")
        return Ok(None)


class CountingValidator:
    """The shipped validator, wrapped only to record what it was asked — the
    rule set and the version stay ``elc.persona.validator``'s."""

    def __init__(self) -> None:
        self._inner = ResponseValidator()
        self.asked: list[str] = []

    def decide(
        self, output: ProviderOutput, contract: GenerationContract | None
    ) -> tuple[ValidatorDecision, tuple[str, ...]]:
        self.asked.append(output.text or "")
        return self._inner.decide(output, contract)


def chunks(*items: str | StreamStep) -> tuple[StreamStep, ...]:
    """The steps a test writes down: plain strings become chunks, steps are
    used as given (so a stop or an end can sit between the chunks), and an end
    always closes the source."""

    return (
        tuple(
            StreamStep.chunk(item) if isinstance(item, str) else item
            for item in items
        )
        + (StreamStep.end(),)
    )


def contract(
    *, max_length: int | None = None, forbidden: tuple[str, ...] = ()
) -> GenerationContract:
    """The §21 contract the guard reads: only the two rules the driver's
    refusal cases turn on are parameterized."""

    return GenerationContract(
        generation_contract_id="gc-p9-2-guard",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=PersonaId("persona-p9-2"),
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
        forbidden_claims=forbidden,
        max_length=max_length,
    )


def run(
    steps: tuple[StreamStep, ...],
    *,
    contract_: GenerationContract | None = None,
    sink: Callable[[str, int], Result[None]] | None = None,
    **transport_options: object,
) -> tuple[StreamRun, ScriptedTransport]:
    transport = ScriptedTransport(steps=steps, **transport_options)  # type: ignore[arg-type]
    result = run_guarded_stream(
        transport=transport, contract=contract_, on_chunk=sink
    )
    return result, transport


# -- the happy run -------------------------------------------------------------


def test_a_multi_chunk_run_releases_every_chunk_in_order() -> None:
    sink = RecordingSink()
    steps = chunks(
        "Sure — ", "let's rehearse ", "the past tense once more, slowly."
    )
    result, transport = run(steps, sink=sink)

    assert result.state == "SENT_COMPLETE"
    assert result.sent_prefix == FULL_REPLY
    assert result.durable_prefix == FULL_REPLY
    assert result.chunks == 3
    assert result.last_chunk_seq == 3
    assert result.stop_reason is None
    assert result.failure_reason is None
    assert result.guard_decision is None
    # the boundary received the same three chunks, in the same order
    assert transport.emitted == [
        "Sure — ",
        "let's rehearse ",
        "the past tense once more, slowly.",
    ]
    # and the record face saw the accumulating prefixes, one sequence apart
    assert sink.calls == [
        ("Sure — ", 1),
        ("Sure — let's rehearse ", 2),
        (FULL_REPLY, 3),
    ]


@pytest.mark.parametrize(
    ("steps", "expected_state", "expected_chunks", "expected_prefix", "emitted"),
    [
        (chunks("one", "two"), "SENT_COMPLETE", 2, "onetwo", ["one", "two"]),
        (
            chunks("one", StreamStep.stopped("the source gave up")),
            "SENT_PARTIAL",
            1,
            "one",
            ["one"],
        ),
        (chunks(StreamStep.stopped("nothing yet")), "FAILED", 0, "", []),
        ((StreamStep.end(),), "FAILED", 0, "", []),
    ],
)
def test_the_terminal_word_is_decided_by_what_was_released(
    steps: tuple[StreamStep, ...],
    expected_state: str,
    expected_chunks: int,
    expected_prefix: str,
    emitted: list[str],
) -> None:
    """§13's words, on the four shapes the driver can end in: a natural end
    after a release is ``SENT_COMPLETE``, any stop after a release is
    ``SENT_PARTIAL``, and a run that released nothing is ``FAILED`` (never a
    ``SENT_*`` word — nothing was sent)."""

    result, transport = run(steps)

    assert result.state == expected_state
    assert result.chunks == expected_chunks
    assert result.sent_prefix == expected_prefix
    assert transport.emitted == emitted


def test_the_emit_happens_before_the_record() -> None:
    """The ordering is a decision (reading 4), so it is asserted as an ordered
    log rather than as two independent facts: a flip of the two steps would
    put every ``record:`` before its ``emit:``."""

    events: list[str] = []
    sink = RecordingSink(events=events)
    result, _ = run(chunks("Hi", " there"), sink=sink, events=events)

    assert result.state == "SENT_COMPLETE"
    assert events == [
        "emit:Hi",
        "record:1:Hi",
        "emit: there",
        "record:2:Hi there",
    ]


# -- the stops, one cause at a time -------------------------------------------


def test_a_stopped_source_keeps_the_prefix_and_its_own_reason() -> None:
    reason = "client window closed mid-answer"
    result, _ = run(chunks("First part. ", StreamStep.stopped(reason)))

    assert result.state == "SENT_PARTIAL"
    assert result.sent_prefix == "First part. "
    # the source's words travel verbatim: no cancellation vocabulary is minted
    assert result.stop_reason == reason
    assert result.guard_decision is None
    # a stop is not a refusal: the driver reports it as the source's own
    # reason (the boundary's caller turns it into its delivery-failure text)
    assert result.failure_reason is None
    assert "CANCELLED" not in (result.stop_reason or "")


def test_a_transport_that_refuses_a_chunk_stops_before_the_record() -> None:
    sink = RecordingSink()
    result, transport = run(
        chunks("Kept. ", "Lost."), sink=sink, refuse_emit_at=2
    )

    assert result.state == "SENT_PARTIAL"
    assert result.sent_prefix == "Kept. "
    assert result.durable_prefix == "Kept. "
    assert result.chunks == 1
    assert result.last_chunk_seq == 1
    assert transport.emitted == ["Kept. "]
    assert sink.calls == [("Kept. ", 1)]
    assert "the client boundary is gone" in (result.failure_reason or "")


@pytest.mark.parametrize(
    ("refuse_emit_at", "expected_state", "expected_prefix", "emitted"),
    [
        (1, "FAILED", "", []),
        (2, "SENT_PARTIAL", "a", ["a"]),
        (3, "SENT_PARTIAL", "ab", ["a", "b"]),
    ],
)
def test_a_refused_release_releases_nothing_of_that_chunk(
    refuse_emit_at: int,
    expected_state: str,
    expected_prefix: str,
    emitted: list[str],
) -> None:
    """A refused release is refused whole: the chunk is not in ``emitted`` and
    not in the prefix, and a refusal of the *first* chunk is the ``FAILED``
    shape (nothing was sent), not a zero-length partial."""

    sink = RecordingSink()
    result, transport = run(
        chunks("a", "b", "c"), sink=sink, refuse_emit_at=refuse_emit_at
    )

    assert result.state == expected_state
    assert result.sent_prefix == expected_prefix
    assert transport.emitted == emitted
    assert sink.calls == [
        (expected_prefix[: index + 1], index + 1)
        for index in range(len(emitted))
    ]


@pytest.mark.parametrize(
    ("refuse_after", "expected_state", "expected_sent", "expected_durable"),
    [
        (0, "SENT_PARTIAL", "a", ""),
        (1, "SENT_PARTIAL", "ab", "a"),
    ],
)
def test_a_record_face_that_refuses_a_chunk_keeps_the_durable_prefix_behind(
    refuse_after: int,
    expected_state: str,
    expected_sent: str,
    expected_durable: str,
) -> None:
    """The one direction the ordering decision has: the refused chunk *was*
    released, so the sent prefix carries it while the durable prefix does
    not — the conservative edge (the record under-reports, never over). A
    refusal of the very first record is the empty-durable-prefix shape the
    coordinator's own tests carry forward (``refuse_after=0``: nothing was
    ever confirmed)."""

    sink = RecordingSink(refuse_after=refuse_after)
    result, transport = run(chunks("a", "b", "c"), sink=sink)

    assert result.state == expected_state
    assert result.sent_prefix == expected_sent
    assert result.durable_prefix == expected_durable
    assert result.last_chunk_seq == len(expected_durable)
    assert transport.emitted == list(expected_sent)
    assert "the record face refused this chunk" in (result.failure_reason or "")


def test_the_guard_runs_on_the_accumulated_text_every_chunk() -> None:
    """Not "once per run" and not "per chunk in isolation": the guard is asked
    about the text the client would hold, so the third call sees all three
    chunks. A driver that guarded single chunks would fail this."""

    watcher = CountingValidator()
    transport = ScriptedTransport(steps=chunks("a", "b", "c"))
    result = run_guarded_stream(
        transport=transport, contract=contract(), validator=watcher
    )

    assert result.state == "SENT_COMPLETE"
    assert watcher.asked == ["a", "ab", "abc"]


def test_a_max_length_breach_stops_before_the_offending_chunk() -> None:
    result, transport = run(
        chunks("Hello", "!"),
        contract_=contract(max_length=5),
    )

    assert result.state == "SENT_PARTIAL"
    assert result.sent_prefix == "Hello"
    assert result.chunks == 1
    assert result.guard_decision == ValidatorDecision.RETRY.value
    assert result.guard_reason_codes == ("MAX_LENGTH_EXCEEDED",)
    assert transport.emitted == ["Hello"]
    # the refused chunk is not in the prefix, and the driver asked for no
    # chunk beyond it (no lookahead)
    assert "!" not in result.sent_prefix
    assert transport.steps_taken == 2


def test_a_forbidden_claim_stops_before_the_offending_chunk() -> None:
    """The same shape for the §21 second rule — and here the violating text is
    text the *source* offered although the buffered validation could not have
    produced it, which is exactly the case reading 3 covers."""

    result, transport = run(
        chunks("Let's practise. ", "this is guaranteed to work"),
        contract_=contract(forbidden=("guaranteed",)),
    )

    assert result.state == "SENT_PARTIAL"
    assert result.sent_prefix == "Let's practise. "
    assert result.guard_decision == ValidatorDecision.ABORT_DELIVERY.value
    assert result.guard_reason_codes == ("FORBIDDEN_CLAIM",)
    assert transport.emitted == ["Let's practise. "]


def test_the_first_chunk_is_guarded_before_it_is_released_even_alone() -> None:
    """A one-chunk run that violates the contract releases nothing: the guard
    acts on the very first chunk, so ``sent_prefix`` stays empty and the run
    is ``FAILED`` rather than a partial delivery of the bad text."""

    result, transport = run(
        chunks("you have mastered it all"),
        contract_=contract(forbidden=("mastered it all",)),
    )

    assert result.state == "FAILED"
    assert result.sent_prefix == ""
    assert result.chunks == 0
    assert transport.emitted == []
    assert result.guard_decision == ValidatorDecision.ABORT_DELIVERY.value


# -- the empty chunk (reading 5) ----------------------------------------------


def test_a_leading_empty_chunk_stops_before_anything_is_released() -> None:
    """The rule set's no-output arm on the accumulation: nothing has been
    accepted yet, so there is no text the guard could accept, and the run ends
    ``FAILED`` with the validator's own reason."""

    result, transport = run(chunks("", "Hello"))

    assert result.state == "FAILED"
    assert result.sent_prefix == ""
    assert result.chunks == 0
    assert result.guard_decision == ValidatorDecision.RETRY.value
    assert result.guard_reason_codes == ("PROVIDER_NO_OUTPUT",)
    assert transport.emitted == []


def test_an_empty_chunk_after_text_is_a_zero_length_release() -> None:
    """The other side of the same reading: with text behind it the accumulation
    is non-empty, the guard accepts, and the empty chunk is released and
    counted (the prefix does not grow; the sequence does)."""

    sink = RecordingSink()
    result, transport = run(chunks("Hi", ""), sink=sink)

    assert result.state == "SENT_COMPLETE"
    assert result.sent_prefix == "Hi"
    assert result.chunks == 2
    assert result.last_chunk_seq == 2
    assert transport.emitted == ["Hi", ""]
    assert sink.calls == [("Hi", 1), ("Hi", 2)]


# -- sources that misbehave ----------------------------------------------------


def test_a_source_that_ends_without_a_chunk_is_failed_and_says_so() -> None:
    result, transport = run((StreamStep.end(),))

    assert result.state == "FAILED"
    assert result.sent_prefix == ""
    assert result.chunks == 0
    assert result.last_chunk_seq == 0
    assert result.stop_reason is None
    assert "ended without releasing a chunk" in (result.failure_reason or "")
    assert transport.emitted == []


def test_an_unknown_step_kind_stops_the_run() -> None:
    """A step shape this module does not know is refused rather than guessed
    at — the vocabulary is three words and the fourth is a failure."""

    result, _ = run((StreamStep(kind="FORK"), StreamStep.end()))  # type: ignore[arg-type]

    assert result.state == "FAILED"
    assert "unknown stream step" in (result.failure_reason or "")


@pytest.mark.parametrize(
    ("breach_at", "expected_state", "expected_prefix", "expected_steps"),
    [
        (1, "FAILED", "", 1),
        (2, "SENT_PARTIAL", "a", 2),
        (3, "SENT_PARTIAL", "aa", 3),
    ],
)
def test_the_guard_acts_at_the_chunk_that_would_break_the_contract(
    breach_at: int,
    expected_state: str,
    expected_prefix: str,
    expected_steps: int,
) -> None:
    """A table over where the breach sits: the prefix is everything before the
    offending chunk, the run is ``FAILED`` when that is nothing, and the driver
    stops asking the source right there (the "no lookahead" half of
    reading 1)."""

    violating = "you have mastered it all"
    offered = ["a"] * (breach_at - 1) + [violating, "d"]
    result, transport = run(
        chunks(*offered),
        contract_=contract(forbidden=("mastered it all",)),
    )

    assert result.state == expected_state
    assert result.sent_prefix == expected_prefix
    assert result.chunks == len(expected_prefix)
    assert transport.steps_taken == expected_steps
    assert violating not in result.sent_prefix
    assert result.guard_decision == ValidatorDecision.ABORT_DELIVERY.value
    assert result.guard_reason_codes == ("FORBIDDEN_CLAIM",)


@pytest.mark.parametrize(
    ("budget", "expected"), [(1, "x"), (2, "xx"), (4, "xxxx")]
)
def test_the_step_budget_stops_a_source_that_never_ends(
    budget: int, expected: str
) -> None:
    """A source that keeps answering chunks cannot hold the turn open: the
    budget ends the run with the prefix it had, and says why."""

    transport = ScriptedTransport(
        steps=tuple(StreamStep.chunk("x") for _ in range(20))
    )
    result = run_guarded_stream(
        transport=transport, contract=contract(), step_budget=budget
    )

    assert result.state == "SENT_PARTIAL"
    assert result.sent_prefix == expected
    assert result.chunks == budget
    assert f"step budget ({budget})" in (result.failure_reason or "")


@pytest.mark.parametrize(
    ("raise_on_step", "expected_state", "expected_prefix"),
    [(1, "FAILED", ""), (3, "SENT_PARTIAL", "ab")],
)
def test_a_source_that_raises_is_stopped_with_what_was_released(
    raise_on_step: int, expected_state: str, expected_prefix: str
) -> None:
    """A raise is a stop, whether it happens before the first chunk (nothing
    released — ``FAILED``) or later (the released prefix stays); it never
    leaves the driver as an exception."""

    result, _ = run(
        chunks("a", "b", "c", "d"), raise_on_step=raise_on_step
    )

    assert result.state == expected_state
    assert result.sent_prefix == expected_prefix
    assert "the source fell over" in (result.failure_reason or "")


def test_a_run_without_a_record_face_counts_its_releases() -> None:
    """The driver's no-record branch: with nothing to be behind, the durable
    counter follows the releases (the shape an assembly without the §22 port
    takes — its caller's own tests carry the durable half)."""

    result, _ = run(chunks("a", "b", "c"))

    assert result.state == "SENT_COMPLETE"
    assert result.chunks == result.last_chunk_seq == 3
    assert result.durable_prefix == result.sent_prefix == "abc"


# -- the port's default source -------------------------------------------------


def test_the_local_source_releases_the_whole_text_as_one_chunk() -> None:
    transport = LocalSingleChunkTransport(FULL_REPLY)
    result = run_guarded_stream(transport=transport, contract=contract())

    assert result.state == "SENT_COMPLETE"
    assert result.chunks == 1
    assert result.last_chunk_seq == 1
    assert result.sent_prefix == FULL_REPLY
    assert transport.emitted == (FULL_REPLY,)


def test_the_default_factory_builds_the_local_source() -> None:
    """The coordinator's default callable answers the port, and the two
    spellings of "the whole text, one chunk" agree."""

    transport = local_single_chunk_transport(
        validated_text=FULL_REPLY, action_id=ACTION_ID
    )
    result = run_guarded_stream(transport=transport, contract=contract())
    assert isinstance(transport, LocalSingleChunkTransport)
    assert result.sent_prefix == FULL_REPLY


@pytest.mark.parametrize(
    ("text", "contract_", "decision", "codes"),
    [
        ("", None, "RETRY", ("PROVIDER_NO_OUTPUT",)),
        ("Hello!", contract(max_length=5), "RETRY", ("MAX_LENGTH_EXCEEDED",)),
        (
            "all done",
            contract(forbidden=("all done",)),
            "ABORT_DELIVERY",
            ("FORBIDDEN_CLAIM",),
        ),
        (
            "all done",
            contract(max_length=3, forbidden=("all done",)),
            "RETRY",
            ("MAX_LENGTH_EXCEEDED",),
        ),
        ("fine", contract(), "ACCEPT", ()),
        (
            "ok",
            contract(max_length=5, forbidden=("never",)),
            "ACCEPT",
            (),
        ),
    ],
)
def test_the_guard_verdicts_are_the_shipped_validators(
    text: str,
    contract_: GenerationContract | None,
    decision: str,
    codes: tuple[str, ...],
) -> None:
    """``guard_verdict`` adds no rule of its own: its answers are
    ``ResponseValidator.decide``'s, including the no-output arm and the
    precedence between the two content rules (length first, the claim second,
    the order §12's rule list states)."""

    verdict, reason_codes = guard_verdict(
        ResponseValidator(), contract_, text
    )

    assert verdict.value == decision
    assert reason_codes == codes


def test_the_driver_asks_the_source_only_for_the_steps_it_uses() -> None:
    """One ``take`` per release plus the end: the driver never reads ahead of
    the chunk it is about to release, and it stops reading as soon as the
    source answers ``END``."""

    result, transport = run(chunks("a", "b"))

    assert result.chunks == 2
    assert transport.steps_taken == 3  # two chunks and the end


def test_a_stop_with_an_empty_reason_is_still_a_stop() -> None:
    """The reporting distinguishes "no reason was given" from "the source did
    not stop": an empty string is a stop like any other (the driver checks
    the step's kind, not the truthiness of its reason)."""

    result, _ = run(chunks("kept", StreamStep.stopped("")))

    assert result.state == "SENT_PARTIAL"
    assert result.sent_prefix == "kept"
    assert result.stop_reason == ""


@pytest.mark.parametrize(
    ("text", "expected_state"),
    [(FULL_REPLY, "SENT_COMPLETE"), ("", "FAILED")],
)
def test_the_default_source_releases_what_it_was_given(
    text: str, expected_state: str
) -> None:
    """The placeholder source hands over the buffer it was built with — and
    when that buffer is empty the guard's no-output arm answers before any
    release, so the run is the ``FAILED`` shape rather than an empty
    ``SENT_COMPLETE`` claim."""

    transport = LocalSingleChunkTransport(text)
    result = run_guarded_stream(transport=transport, contract=contract())

    assert result.state == expected_state
    assert result.sent_prefix == text
    assert transport.emitted == (() if text == "" else (text,))


def test_the_guard_is_the_shipped_validator_and_the_window_is_one_chunk() -> None:
    """Two declarations the rest of this file leans on: the guard is
    ``elc.persona.validator``'s class (it is not a second rule set, and the
    version rides that module), and the buffer a run may hold ahead of a
    release is exactly one chunk (reading 1)."""

    import elc.persona.validator as persona_validator
    import elc.runtime.guarded_stream as driver

    assert driver.ResponseValidator is persona_validator.ResponseValidator
    assert SMALL_BUFFER_CHUNKS == 1

    decision, codes = guard_verdict(
        ResponseValidator(), contract(), "fine text"
    )
    assert decision is ValidatorDecision.ACCEPT
    assert codes == ()


def test_the_step_vocabulary_is_the_three_declared_shapes() -> None:
    assert {kind.value for kind in StreamStepKind} == {
        "CHUNK",
        "END",
        "STOPPED",
    }
    assert StreamStep.chunk("x").kind is StreamStepKind.CHUNK
    assert StreamStep.end().kind is StreamStepKind.END
    assert StreamStep.stopped("why").kind is StreamStepKind.STOPPED
    assert StreamStep.stopped("why").reason == "why"
    # the three factories carry nothing they should not
    assert StreamStep.end().text == ""
    assert StreamStep.end().reason is None


def test_a_run_holds_no_cancellation_word_of_its_own() -> None:
    """§13's sixth word is not this driver's (reading 6): the three states it
    answers with are the three above, and a source's cancellation-shaped reason
    stays a reason."""

    assert DeliveryMode.GUARDED_STREAM.value == "GUARDED_STREAM"
    states = {
        run(chunks("a", "b"))[0].state,
        run(chunks("a", StreamStep.stopped("cancelled by the user")))[0].state,
        run(chunks(StreamStep.stopped("cancelled by the user")))[0].state,
    }
    assert states == {"SENT_COMPLETE", "SENT_PARTIAL", "FAILED"}
    assert "CANCELLED" not in states
