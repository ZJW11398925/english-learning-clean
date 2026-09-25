"""P10-3 — the two long-pending questions, decided and pinned.

Two half-registrations become rulings in this cut, each with a reason, a reopen
condition and a load-bearing pin:

1. **the PreDeliveryGuard's ``UNCHECKED`` fact (``None`` = "nobody could read
   it") never invalidates** — fail-open, formally confirmed. The ruling is
   written into ``elc.runtime.pre_delivery_guard`` (reading 2's adjudication
   block) as a *reading*, with §15's closed list and the two-word /
   no-``DEGRADED`` schema argument spelled out; here it is pinned as behaviour
   by a contrast pair over the real chains — a teaching delivery whose §9
   constraint authority is not wired answers ``VALID`` with exactly the two
   ``UNCHECKED_*`` codes, an ordinary reply answers ``VALID`` with none — and
   re-pinned as the ``3**7`` grid's two invariants;
2. **``ConversationCoordinator._delivery_interrupted()`` read failure ⇒
   ``False``** — the stream keeps sending. The reason is that the user's STOP
   is a durable request (§17.1 rules 1-2), rule 3 reserves cancellation for the
   lease holder / recovery owner, and a failed read is neither act nor actor;
   §17's rule for uncertainty is conservative canonicalization, not
   cancellation.

Both directions were pre-decided by the Phase 10 opening DEC's R6 and land
here. Both are readings, never claimed as canonical text: the two declaration
pins assert the rulings' own words — each reason's leading phrase, the reopen
conditions, the attribution and the retirement of the old claim — so a later cut
that wants to move a ruling has to edit the module's own text (deleting any one
reason paragraph turns them red; the P10-3 disposition added the per-reason
phrases after the review showed a whole reason could be dropped silently while
the block's other phrases stayed satisfied).

**Capability boundary (registered, not to be over-read).** These are
phrase-existence pins over the module's own text: they force a mover to touch
the module's words, and they notice a dropped reason — they do **not** prove the
reasons are the right ones (that argument lives with canonical and with review,
not here), and they are not a proof that the module and this file agree on
meaning. The behaviour pins assert what the shipped code then does.

The harness facts this file leans on:

- ``ConversationQueries`` is a **constructor port** (``elc.conversation.queries``
  / ``controller.py``'s ``conversation_queries``), so a wrapper that answers
  ``Err`` for exactly one read while delegating every other one is a legal
  public-face harness. That is the fact that retires ``_delivery_interrupted``'s
  old registration (the module's own words now say so and name this file and
  this test), and it is exercised by
  ``test_a_failed_interrupt_read_keeps_the_stream_sending_and_is_recorded_unchecked``
  plus ``test_the_broken_read_is_confined_to_one_read``;
- the multi-step stream world, the scripted source and the second-connection
  read are ``tests.phase9.test_p9_2_stream_turn``'s, and the teaching world is
  ``tests.phase9.test_p9_3_teaching_guard``'s — imported rather than copied
  (the phase-9 precedent: a phase's fixtures are its world, and that module's
  ``stream_world`` docstring says a sibling suite may ask for it by name).

Registered (this cut): the read-failure arm's real-world trigger is a broken or
degrading read (a DB-level ``Err``) while a delivery is mid-stream; no shipped
path forces it, which is why the harness is a port wrapper and not a production
configuration. The ruling is what the code does when it happens.

Registered too, because it is the difference between what is *pinned* and what
is only *ruled*: the failing-read world carries **no** interrupt request at all,
so the pin proves the read-failure arm (the delivery goes out, the
under-coverage is recorded) and **not** the harder shape the ruling's own risk
sentence names — a genuinely *pending* STOP that the broken read cannot see.
Revisit: a cut plants a durable request mid-stream (the p9-3
``InterruptingSource`` shape, at the moment the delivery is already being sent)
and pins that the stream goes out anyway, which is the accepted trade rather
than a second fact — this cut registers the gap instead of claiming it covered.
"""

from __future__ import annotations

import ast
import itertools
from pathlib import Path
from typing import Callable

import pytest

from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.types import (
    ActionId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.guarded_stream import StreamStep, StreamTransport
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.pre_delivery_guard import (
    CONDITION_ATTRIBUTES,
    UNCHECKED_PREFIX,
    GuardCondition,
    PreDeliveryDecision,
    PreDeliveryGuardFacts,
    guard_verdict,
)
from elc.runtime.types import TurnStatus
from tests.conftest import SRC_ROOT
from tests.phase8.conftest import CONV
from tests.phase8.p8_4_world import begin_turn_ok as begin_ordinary_turn_ok
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    ScriptedSource,
    SourceFactory,
    StreamWorld,
    action_of,
    begin_turn_ok,
    count,
    persona_runtime,
    pieces,
    second_connection_row,
    slice_of,
    stream_world,
)
from tests.phase9.test_p9_3_teaching_guard import (  # noqa: F401  (fixture)
    FileWorld,
    coordinator_over,
    file_world,
    teaching_request,
)

MODULE = SRC_ROOT / "runtime" / "pre_delivery_guard.py"
CONTROLLER = SRC_ROOT / "runtime" / "controller.py"

#: The test the controller's ruling names as its pin, kept as literals so the
#: module's text and this file cannot drift silently.
INTERRUPT_PIN_FILE = "tests/phase10/test_p10_3_adjudications.py"
INTERRUPT_PIN_FUNCTION = (
    "test_a_failed_interrupt_read_keeps_the_stream_sending"
    "_and_is_recorded_unchecked"
)

#: §15's seven conditions in the module's reading order (the order the codes
#: come out in), pinned as a literal so a rename or a move has to touch this.
CONDITION_ORDER = (
    "CONVERSATION_INACTIVE",
    "ACTION_CANCELLED",
    "ACTION_SUPERSEDED",
    "TEACHING_LOCK_INVALID",
    "NEW_TARGET_SUPPRESSED",
    "JUST_CHAT_HARD_SWITCH",
    "LINEAGE_MISMATCH",
)


# -- the world, the one broken read, and the two readers ----------------------


@pytest.fixture()
def stream_file_world(tmp_path: Path) -> StreamWorld:
    """The p9-2 file-backed world, through its own ``stream_world`` builder."""

    return stream_world(tmp_path)


@pytest.fixture()
def teaching_file_world(request: pytest.FixtureRequest) -> FileWorld:
    """The p9-3 teaching world, asked for by name from the fixture this module
    imported above — re-used, not re-implemented (that module's fixture is the
    one place the world is built)."""

    return request.getfixturevalue("file_world")


class FailingInterruptRead:
    """The conversation query face with exactly one read broken.

    ``ConversationQueries`` is a constructor port, so this is a legal
    public-face harness rather than a stub: every read delegates verbatim to
    the world's real store (``__getattr__``, so *all* of them) except
    ``list_pending_interrupts_for_action``, which answers ``Err`` and counts
    that it was asked. The reconciler's own read
    (``list_pending_interrupts_for_conversation``) is deliberately left alone,
    so the failure under test is a *read* failure confined to one read — the
    shape the ruling is about.
    """

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.action_reads = 0

    def list_pending_interrupts_for_action(
        self, action_id: ActionId
    ) -> Result[tuple[object, ...]]:
        self.action_reads += 1
        del action_id
        return Err(
            DomainError(
                code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                message="the interrupt face could not be read",
            )
        )

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


def stream_coordinator(
    world: StreamWorld,
    *,
    queries: object,
    transport: Callable[..., StreamTransport],
) -> ConversationCoordinator:
    """The p9-2 assembly, with the query face a test hands over."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=world.store,
        conversation_queries=queries,  # type: ignore[arg-type]
        persona=persona_runtime(world),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=world.deliveries,
        stream_transport=transport,
    )


def guard_row(
    store: SqliteDeliveryRecordStore, action_id: ActionId | str
) -> tuple[str, tuple[str, ...]]:
    """The one §21.1 row of one action, as the record store reads it back."""

    rows = store.list_pre_delivery_guard_results(ActionId(action_id))
    assert isinstance(rows, Ok), rows
    assert len(rows.value) == 1, rows
    return rows.value[0].decision, rows.value[0].reason_codes


def guard_source() -> str:
    return MODULE.read_text(encoding="utf-8")


def interrupt_ruling_text() -> str:
    """The ``_delivery_interrupted`` docstring, read off the module's AST (so
    the pin is about *that* text and not about a guessed line window)."""

    tree = ast.parse(CONTROLLER.read_text(encoding="utf-8"))
    node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_delivery_interrupted"
    )
    docstring = ast.get_docstring(node, clean=False)
    assert docstring, "the method lost its docstring"
    return docstring


# -- ① the module declaration: UNCHECKED never invalidates --------------------


def test_the_unchecked_ruling_is_in_the_modules_own_words() -> None:
    """Registration-style pin over the module's own text: the adjudication
    block exists, carries this cut's attribution, states its reasons in the
    terms the ruling rests on (the §15 closed list; the two-word vocabulary and
    the CHECK with no ``DEGRADED``), says it is a reading rather than canonical
    text, and names its reopen conditions."""

    flat = " ".join(guard_source().split())
    assert "Adjudicated (P10-3" in flat
    assert "fail-open is the ruling" in flat
    assert "a reading, not canonical text" in flat
    assert "封闭列表" in flat  # ① §15's seven are a closed list
    assert "two words" in flat  # ② the decision vocabulary
    assert "no DEGRADED here" in flat
    assert "CHECK (decision IN ('VALID', 'INVALIDATE_ACTION'))" in flat
    assert "Reopen conditions (this adjudication)" in flat
    assert "adds an eighth" in flat  # reopen 1: an eighth §15 condition
    assert "real client lands" in flat.lower()  # reopen 2
    # each reason's leading phrase, so a reason paragraph deleted whole is
    # noticed (disposition F2: the review dropped (c) silently while every
    # phrase above stayed satisfied elsewhere in the file)
    assert "(a) §15's seven hard-invalidation conditions" in flat
    assert "(b) the decision vocabulary is exactly" in flat
    assert "(c) the two places canonical does speak about uncertainty" in flat
    # ... and the corrected Gate contrast (disposition F1) is what is pinned:
    # the Gate's DEGRADED is a separate status column, never this row's word
    assert "separate status column" in flat


# -- ② the controller declaration: a failed read keeps sending ----------------


def test_the_interrupt_read_failure_ruling_retires_its_old_claim() -> None:
    """The controller half: the ruling's words, the grounds for retiring the
    P9-3 claim (the constructor port), the *absence* of the retired wording,
    and the name of the pin that replaced it. The module and this file are
    bound both ways — the method names this test, and this test asserts the
    method's words."""

    flat = " ".join(interrupt_ruling_text().split())
    assert "Adjudicated (P10-3" in flat
    assert "a failed read keeps sending" in flat
    assert "a reading, not canonical text" in flat
    assert "durable request" in flat
    assert "rule 3" in flat
    assert "_reconcile_pending_interrupt" in flat
    assert "Reopen conditions (this adjudication)" in flat
    assert "user control is formally ruled to outrank availability" in flat
    assert "real client lands" in flat.lower()
    assert "ConversationQueries" in flat
    # each reason's leading phrase (disposition F2: the review dropped (a) and
    # (b) together and this pin stayed green, because the two reasons' words
    # appear again in the block's other paragraphs)
    assert "(a) the user's STOP is a" in flat
    assert "(b) §17.1 rule 3 names the only actor" in flat
    assert "(c) nothing is lost by keeping on" in flat
    # the retired claim is quoted as it was, and its falsity is stated
    assert "recorded this read-failure arm as unreachable" in flat
    assert "That claim is false in the shipped tree" in flat
    # the retired wording is gone and its replacement is marked
    assert "untestable" not in flat
    assert "Superseded (P10-3)" in flat
    assert "constructor port" in flat
    assert INTERRUPT_PIN_FILE in flat, "the ruling must name the pin's file"
    assert INTERRUPT_PIN_FUNCTION in flat, "the ruling must name the pin"
    # ... and the pin it names is a real test in this file
    assert INTERRUPT_PIN_FUNCTION in globals()


# -- ③ the behaviour pin: a clean VALID vs an under-covered VALID -------------


def test_a_clean_valid_and_an_under_covered_valid_are_told_apart(
    teaching_file_world: FileWorld,
) -> None:
    """The contrast pair, on **one** real world and one guard.

    (甲) a **teaching** opening whose §9 constraint authority is not wired: its
    ``new_target_suppressed`` / ``just_chat_hard_switch`` legs answer ``None``,
    so the guard answers ``VALID`` and the row's codes are exactly the two
    ``UNCHECKED_*`` spellings — an under-covered check is visible in the
    durable row, and the delivery still went out (moment ``AWAITING_USER``, one
    assistant row).

    (乙) an **ordinary** persona reply through the same coordinator and the same
    delivery-record face: §15's three teaching conditions are not applicable and
    answer ``False`` (never ``None``), so its row is ``VALID`` with **no** code
    at all — the clean reading.

    The row-level proof of "``False``, not ``None``" is exactly the absence of
    the three ``UNCHECKED_<teaching condition>`` codes: a ``None`` would have
    spelled one, and the codes are the only column that distinguishes the two
    readings. That is what "recorded, never silent" has to mean — clean and
    under-covered are tellable apart from the durable row alone.
    """

    world_ = teaching_file_world.world
    records = SqliteDeliveryRecordStore(
        teaching_file_world.db, teaching_file_world.fence
    )
    coordinator = coordinator_over(world_, delivery_records=records)

    # (甲) the teaching delivery, with no §9 constraint authority wired
    opened = coordinator.request_teaching(teaching_request("cmid-p10-3-teach"))
    assert isinstance(opened, Ok), opened
    assert opened.value.gate_decision == "ALLOW"
    under_covered = guard_row(records, opened.value.action_id)
    assert under_covered == (
        "VALID",
        (
            "UNCHECKED_NEW_TARGET_SUPPRESSED",
            "UNCHECKED_JUST_CHAT_HARD_SWITCH",
        ),
    )
    assert count(teaching_file_world.db, "assistant_turn") == 1
    moment = teaching_file_world.db.execute(
        "SELECT lifecycle_state FROM teaching_moment"
    ).fetchone()
    assert moment is not None
    assert str(moment[0]) == "AWAITING_USER"

    # (乙) the ordinary reply, same world, same guard, and no code at all
    replied = begin_ordinary_turn_ok(coordinator, "cmid-p10-3-ordinary")
    assert replied.turn_status is TurnStatus.COMPLETED
    assert replied.delivery_state == "SENT_COMPLETE"
    clean = guard_row(records, replied.action_id)
    assert clean == ("VALID", ())
    assert clean != under_covered, "the contrast has to be row-visible"
    assert replied.action_id != opened.value.action_id
    assert count(teaching_file_world.db, "assistant_turn") == 2


# -- ④ the exhaustive re-pin over the whole grid ------------------------------


def test_the_whole_grid_says_no_true_is_valid_and_every_none_is_recorded() -> None:
    """``3**7 = 2187`` readings, recomputed in this cut: the decision is
    ``VALID`` exactly when no fact is ``True`` (however many are unread), every
    ``None`` produces its own ``UNCHECKED_<condition>`` code and nothing else
    does, the codes come out in the module's declared condition order, and the
    incomplete reads are exactly the ones the verdict names as unchecked.

    This is the whole rule at the value level — the pin the
    "``None`` ⇒ ``INVALIDATE_ACTION``" mutation has to fail.
    """

    answers: tuple[bool | None, ...] = (True, False, None)
    grid = list(itertools.product(answers, repeat=len(CONDITION_ORDER)))
    assert len(grid) == 3**7 == 3 ** len(CONDITION_ORDER) == 2187

    for digits in grid:
        given = PreDeliveryGuardFacts(
            **{
                condition.lower(): answer
                for condition, answer in zip(
                    CONDITION_ORDER, digits, strict=True
                )
            }
        )
        verdict = guard_verdict(given)
        assert verdict.decision == (
            PreDeliveryDecision.INVALIDATE_ACTION.value
            if any(answer is True for answer in digits)
            else PreDeliveryDecision.VALID.value
        )
        assert verdict.reason_codes == tuple(
            condition
            if answer is True
            else f"{UNCHECKED_PREFIX}{condition}"
            for condition, answer in zip(
                CONDITION_ORDER, digits, strict=True
            )
            if answer is not False
        )
        unchecked = [
            code
            for code in verdict.reason_codes
            if code.startswith(UNCHECKED_PREFIX)
        ]
        assert len(unchecked) == sum(1 for answer in digits if answer is None)
        assert unchecked == [
            f"{UNCHECKED_PREFIX}{condition.value}"
            for condition in GuardCondition
            if getattr(given, CONDITION_ATTRIBUTES[condition]) is None
        ]


# -- ⑤ the behaviour pin: one bad read, two faces, neither cancels ------------


def test_a_failed_interrupt_read_keeps_the_stream_sending_and_is_recorded_unchecked(
    stream_file_world: StreamWorld,
) -> None:
    """The read-failure ruling on the real streamed chain.

    The same broken read is consumed twice — once by the stream's "is this
    still wanted?" question, once by the guard's ``action_cancelled`` leg — and
    the two faces answer it the way the ruling says: the stream keeps sending
    (the whole reply is released, the §22 row freezes ``SENT_COMPLETE`` with the
    whole text as its durable prefix, the turn is ``COMPLETED`` /
    ``REPLIED_FULL``, the transcript's single row equals the whole reply) and
    the §21.1 row records the under-coverage (``VALID`` with
    ``UNCHECKED_ACTION_CANCELLED``).

    The stream is three chunks, so the question is asked once before every step
    the driver took: four asks (three chunks and the step that answered END)
    plus the guard's own read — the count is what proves the read was asked
    *during* the stream, not only once by the guard.

    Registered (disposition F3, the "or delete" half): this world carries no
    interrupt row at all, so the count asserts that a failed read **fabricates**
    nothing. That it also deletes nothing is a construction fact rather than an
    observation — the ``Err`` arm reads and returns without writing (it is four
    lines) — so it is recorded here instead of being dressed up as a second
    assertion over an empty table.
    """

    world = stream_file_world
    queries = FailingInterruptRead(world.store)
    source = ScriptedSource(
        steps=tuple(StreamStep.chunk(piece) for piece in pieces(REPLY, 3))
    )
    completion = begin_turn_ok(
        stream_coordinator(
            world, queries=queries, transport=SourceFactory(source)
        ),
        "cmid-p10-3-broken-read",
    )
    action_id = action_of(world, str(completion.turn_id))

    # (i) the read was really asked — at least once per step attempt
    assert queries.action_reads >= 5, (
        "the stream must ask the durable face before every step; only"
        f" {queries.action_reads} reads were made"
    )

    # (ii) keep-sending: the whole reply went out and nothing was cancelled
    state, prefix, sequence, _, terminal_at = second_connection_row(
        world, action_id
    )
    assert (state, prefix, sequence) == ("SENT_COMPLETE", REPLY, 3)
    assert terminal_at is not None
    assert completion.turn_status is TurnStatus.COMPLETED
    assert completion.outcome == "REPLIED_FULL"
    assert completion.delivery_state == "SENT_COMPLETE"
    assert completion.reply_text == REPLY
    assert count(world.db, "assistant_turn") == 1
    canonical = slice_of(world, str(completion.turn_id))
    assert canonical.assistant_turn is not None
    assert canonical.assistant_turn.content == REPLY
    assert count(world.db, "interrupt_request") == 0, (
        "a failed read must not fabricate an interrupt request"
    )

    # (iii) the same bad read on the guard face: recorded, not invalidating
    assert guard_row(world.deliveries, action_id) == (
        "VALID",
        ("UNCHECKED_ACTION_CANCELLED",),
    )


def test_the_broken_read_is_confined_to_one_read(
    stream_file_world: StreamWorld,
) -> None:
    """The harness claim the ruling's retirement rests on: the wrapper breaks
    exactly one read and delegates every other one verbatim — so the
    reconciler's read (``list_pending_interrupts_for_conversation``, the leg
    §17.1 rule 3's owner uses) stays healthy, and what is under test is a
    *read* failure rather than a broken world."""

    world = stream_file_world
    queries = FailingInterruptRead(world.store)

    # the one read is broken, says so, and says it was asked
    broken = queries.list_pending_interrupts_for_action(ActionId("ga-probe"))
    assert isinstance(broken, Err)
    assert broken.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert queries.action_reads == 1

    # every other read is the real store's own bound method, verbatim
    for name in (
        "get_conversation",
        "get_canonical_turn_slice",
        "get_conversation_window",
        "get_sequence_positions",
        "is_command_payload_turn",
        "list_pending_interrupts_for_conversation",
        "list_pending_interrupts_for_turn",
    ):
        assert getattr(queries, name) == getattr(world.store, name), name

    # ... and the reconciler's read answers the store's own value
    healthy = queries.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(healthy, Ok), healthy
    assert healthy == world.store.list_pending_interrupts_for_conversation(CONV)
    assert queries.action_reads == 1, "the healthy read is not counted as one"
