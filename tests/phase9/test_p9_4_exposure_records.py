"""P9-4 ② — the §22 estimate on the real chain, and the acknowledgment entry.

The three durable faces of this cut, over file-backed app.db files and the
shipped stores — no ``_seed``-shaped helper, no fixture target provider:

- **the initial estimate is written by the delivery itself** and is readable by
  a **second connection** (the P9-2 discipline: the writing connection's view is
  never the evidence). The streamed face's estimate is derived from the frozen
  §22 row, so a partial run records ``PARTIAL`` — and the negative half is
  asserted too (no column may claim ``FULL`` for a prefix that shorter than the
  validated text);
- **the buffered (teaching) face writes its own estimate and no §22 row** — the
  registered split (a buffered delivery is atomic: it declares its word and its
  whole text, and the §22 row is the streamed face's record);
- **the acknowledgment entry** (``accept_render_ack``): the row is appended, the
  estimate is refined **upward only**, a repeated acknowledgment is a replay
  (no second row, no second write) and a differing one is ``CONFLICT``; an
  acknowledgment for an action with no estimate refines nothing and mints no
  row; and the entry moves **nothing else** — the proof is a full table-count
  diff around the call, plus the transcript's ``delivery_certainty`` read back
  unchanged;
- **the estimate path and the acknowledgment path append no §20 event** (R4):
  behaviourally (an acknowledgment against a real teaching delivery leaves the
  ledger's event count exactly where it was) and by the AST pin in the pure
  suite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.persona.types import ProviderOutput
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.types import (
    ActionId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
)
from elc.runtime import ConversationCoordinator
from elc.runtime.delivery_records import ClientRenderAck
from elc.runtime.guarded_stream import StreamStep
from elc.runtime.lease import ConversationCoordinatorLease
from tests.phase8.p8_4_world import (
    acceptance_supply,
    count_events,
    wiring,
)
from tests.phase8.p8_4_world import begin_turn_ok as p8_begin_turn_ok
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    ScriptedSource,
    SourceFactory,
    StreamWorld,
    action_of,
    begin_turn_ok,
    coordinator_,
    pieces,
    stream_world,
)

ACKED_AT = "2026-09-24T09:30:00+00:00"


@pytest.fixture()
def world(tmp_path: Path) -> StreamWorld:
    return stream_world(tmp_path)


def teaching_coordinator(
    p8world, *, records: object | None = None
) -> ConversationCoordinator:
    """The P8-4 assembly **with the §22 record face wired** — the world's own
    ``coordinator`` builder passes none, and every estimate assertion below
    needs one (the shape P9-3's teaching suite uses)."""

    runtime = PersonaRuntime(
        actions=p8world.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=p8world.lease,
        conversation_commands=p8world.store,
        conversation_queries=p8world.store,
        persona=runtime,
        generation_actions=p8world.generation,
        decision_cycles=p8world.generation.decision_cycles,
        learning_controller=p8world.learning,
        teaching=p8world.teaching,
        targets=p8world.targets,
        automatic_teaching=wiring(p8world, supply=acceptance_supply()),
        delivery_records=(
            SqliteDeliveryRecordStore(p8world.db, p8world.fence)
            if records is None
            else records  # type: ignore[arg-type]
        ),
    )


def _table_counts(db: sqlite3.Connection) -> dict[str, int]:
    """Every table's row count — the diff around a call is how "this wrote
    nothing else" is measured (never predicted from the code)."""

    names = [
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    return {
        name: int(db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        for name in names
    }


def _ack(
    action_id: ActionId, *, seq: int = 1, final: bool = True, **overrides: object
) -> ClientRenderAck:
    values: dict[str, object] = {
        "action_id": action_id,
        "assistant_turn_id": f"aturn-{action_id}",
        "rendered_chunk_seq": seq,
        "rendered_text_hash": f"hash-{seq}",
        "acked_at": ACKED_AT,
        "final_rendered": final,
    }
    values.update(overrides)
    return ClientRenderAck(**values)  # type: ignore[arg-type]


def _estimate_row(world: StreamWorld, action_id: ActionId) -> tuple[object, ...]:
    """The estimate as a **second** connection reads it (never the writer)."""

    from elc.platform.db import connection

    second = connection.connect(world.path)
    try:
        row = second.execute(
            "SELECT certainty, exposure_level, max_possible_exposure,"
            " confirmed_exposure, derivation_reason FROM exposure_estimate"
            " WHERE action_id = ?",
            (str(action_id),),
        ).fetchone()
    finally:
        second.close()
    assert row is not None, "no exposure_estimate row for this action"
    return tuple(row)


class RefusingEstimateStore:
    """The real §22 store with its estimate write refused (the P9-2 spy shape:
    every other face goes through, and the refusal is counted)."""

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.calls = 0

    def record_initial_exposure_estimate(self, estimate: object) -> object:
        self.calls += 1
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message="the estimate face refused this write (injected)",
            )
        )

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


# -- ① the streamed face's estimate -------------------------------------------


def test_a_healthy_streamed_turn_persists_its_initial_estimate(
    world: StreamWorld,
) -> None:
    """The whole reply was sent, so the estimate is ``FULL`` / ``FULL`` with
    nothing confirmed yet — and the row is the *derivation's*, byte for byte
    (the reason included), read back through a second connection."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-estimate")
    action_id = action_of(world, str(completion.turn_id))

    assert _estimate_row(world, action_id) == (
        "SERVER_SENT_UNCONFIRMED",
        "FULL",
        "FULL",
        "NONE",
        f"sent {len(REPLY)} of {len(REPLY)} chars; no render ack",
    )
    assert world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 1


def test_a_partial_stream_records_a_partial_estimate_and_never_full(
    world: StreamWorld,
) -> None:
    """The negative half of the conservative rule: the durable prefix is
    shorter than the validated text, so no column of the estimate may say
    ``FULL`` — §14's "宁可低估，不高估" as a durable fact rather than a
    promise."""

    kept = pieces(REPLY, 3)[0]
    source = ScriptedSource(
        steps=(StreamStep.chunk(kept), StreamStep.stopped("the window closed"))
    )
    completion = begin_turn_ok(
        coordinator_(world, transport=SourceFactory(source)),
        "cmid-p9-4-partial",
    )
    action_id = action_of(world, str(completion.turn_id))

    row = _estimate_row(world, action_id)
    assert row[:4] == (
        "SERVER_SENT_UNCONFIRMED",
        "PARTIAL",
        "PARTIAL",
        "NONE",
    )
    assert row[4] == (
        f"sent {len(kept)} of {len(REPLY)} chars; partial send; no render ack"
    )
    assert "FULL" not in row


# -- ② the buffered (teaching) face's estimate --------------------------------


def test_the_teaching_opening_writes_an_estimate_and_no_delivery_row(
    db: sqlite3.Connection, p8world
) -> None:
    """§13's second mode: the automatic opening is delivered through
    ``finalize_delivery``, so CP3a lands an estimate for it — the atomic
    spelling (``sent N chars``, ``FULL``) — while the §22 row stays empty
    (only the streamed face writes one)."""

    coordinator = teaching_coordinator(p8world)
    completion = p8_begin_turn_ok(coordinator, "cmid-p9-4-teaching")

    assert db.execute(
        "SELECT COUNT(*) FROM server_delivery_record"
    ).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM exposure_estimate").fetchone()[0] == 1
    assert db.execute(
        "SELECT certainty, exposure_level, max_possible_exposure,"
        " confirmed_exposure FROM exposure_estimate"
    ).fetchone() == ("SERVER_SENT_UNCONFIRMED", "FULL", "FULL", "NONE")
    reason = db.execute(
        "SELECT derivation_reason FROM exposure_estimate"
    ).fetchone()[0]
    assert "no render ack" in reason and "sent " in reason
    # and the delivery's own §20 event is the delivery leg's (not the estimate's)
    assert count_events(db) == 1
    assert completion.ledger_event == "teaching_presented"


# -- ③ the acknowledgment entry ------------------------------------------------


def test_an_ack_refines_the_estimate_upward_and_moves_nothing_else(
    world: StreamWorld,
) -> None:
    """The entry's whole contract in one measurement: one ACK row, one refined
    estimate (certainty to ``CONFIRMED_RENDERED``, confirmation to the sent
    level), the transcript untouched — and a full table-count diff showing that
    exactly those two rows are the difference."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-refine")
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)
    estimate_before = _estimate_row(world, action_id)
    before_counts = _table_counts(world.db)
    transcript_before = world.db.execute(
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone()

    coordinator = coordinator_(world)
    receipt = coordinator.accept_render_ack(_ack(action_id))
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is True
    assert receipt.value.note is None
    assert receipt.value.ack == _ack(action_id)
    estimate = receipt.value.estimate
    assert estimate is not None
    assert estimate.certainty == "CONFIRMED_RENDERED"
    assert estimate.confirmed_exposure == "FULL"
    assert estimate.exposure_level == estimate.max_possible_exposure == "FULL"
    assert "render ack for chunk 1 (final)" in estimate.derivation_reason

    after_counts = _table_counts(world.db)
    changed = {
        table: (before_counts[table], after_counts[table])
        for table in after_counts
        if before_counts[table] != after_counts[table]
    }
    # the *only* new row is the acknowledgment itself: the estimate is the same
    # row with its two columns raised (no second row, no other table touched)
    assert changed == {"client_render_ack": (0, 1)}
    assert _estimate_row(world, action_id) != estimate_before
    # the transcript is not the estimate's to move (R3's last clause)
    assert world.db.execute(
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn"
    ).fetchone() == transcript_before
    assert transcript_before[2] == "SERVER_SENT_UNCONFIRMED"
    # the durable row is the refined one, seen from a second connection
    assert _estimate_row(world, action_id)[0] == "CONFIRMED_RENDERED"


def test_a_repeated_ack_replays_and_a_different_one_is_conflict(
    world: StreamWorld,
) -> None:
    """The append face's rule, on the entry: the same acknowledgment is a
    replay (one row, nothing written the second time), a differing one under
    the same key is ``CONFLICT`` and leaves the durable row alone."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-replay")
    action_id = action_of(world, str(completion.turn_id))
    coordinator = coordinator_(world)
    first = coordinator.accept_render_ack(_ack(action_id))
    assert isinstance(first, Ok), first
    written_once = _estimate_row(world, action_id)

    second = coordinator.accept_render_ack(_ack(action_id))
    assert isinstance(second, Ok), second
    assert second.value.ack == first.value.ack
    assert second.value.estimate == first.value.estimate
    assert second.value.refined is False  # nothing left to raise
    assert world.db.execute(
        "SELECT COUNT(*) FROM client_render_ack"
    ).fetchone()[0] == 1
    assert _estimate_row(world, action_id) == written_once

    refused = coordinator.accept_render_ack(
        _ack(action_id, **{"rendered_text_hash": "a-different-hash"})
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert world.db.execute(
        "SELECT COUNT(*) FROM client_render_ack"
    ).fetchone()[0] == 1
    assert _estimate_row(world, action_id) == written_once


def test_a_non_final_ack_raises_certainty_only(world: StreamWorld) -> None:
    """The coverage rule on the durable face: a chunk-level acknowledgment
    confirms a render and not the send, so the confirmation column stays where
    the derivation put it while the certainty rises."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-nonfinal")
    action_id = action_of(world, str(completion.turn_id))

    receipt = coordinator_(world).accept_render_ack(
        _ack(action_id, seq=1, final=False)
    )
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.estimate is not None
    assert receipt.value.estimate.certainty == "CONFIRMED_RENDERED"
    assert receipt.value.estimate.confirmed_exposure == "NONE"
    assert receipt.value.estimate.max_possible_exposure == "FULL"


def test_an_ack_for_a_delivery_with_no_estimate_refines_nothing(
    world: StreamWorld,
) -> None:
    """Registered reading 7 of the entry: the estimate is CP3a's record, so an
    acknowledgment naming a delivery that never produced one (the provider
    answered nothing, so the action ended undelivered) appends its own row and
    **mints no estimate** — "不得凭空造 FULL" taken literally."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    coordinator = type(coordinator_(world))(
        lease=lease,
        conversation_commands=world.store,
        conversation_queries=world.store,
        persona=PersonaRuntime(
            actions=world.generation,
            provider=ScriptedPersonaProvider(script=(ProviderOutput(text=""),)),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=2,
        ),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=world.deliveries,
    )
    completion = begin_turn_ok(coordinator, "cmid-p9-4-no-estimate")
    assert completion.outcome == "FAILED_USER_VISIBLE"
    action_id = action_of(world, str(completion.turn_id))
    assert world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 0

    receipt = coordinator.accept_render_ack(_ack(action_id))
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is False
    assert receipt.value.estimate is None
    assert receipt.value.note is not None
    assert "no exposure estimate" in receipt.value.note
    assert world.db.execute(
        "SELECT COUNT(*) FROM client_render_ack"
    ).fetchone()[0] == 1
    assert world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 0


def test_the_entry_refuses_without_the_record_face(world: StreamWorld) -> None:
    """The port's absence is a refusal with a name, never a silent no-op: the
    acknowledgment is the caller's act and it has nowhere durable to go."""

    coordinator = coordinator_(world, records=False)
    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-unwired")
    action_id = action_of(world, str(completion.turn_id))
    refused = coordinator.accept_render_ack(_ack(action_id))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert world.db.execute(
        "SELECT COUNT(*) FROM client_render_ack"
    ).fetchone()[0] == 0


def test_the_refinement_face_refuses_illegal_moves_and_unknown_actions(
    world: StreamWorld,
) -> None:
    """The durable rule on the store face (judgement 11): only the two
    acknowledgment columns may rise, the sent level and the action's identity
    may not move, a word outside §13 is refused, and an *unknown* action is
    ``NOT_FOUND`` — refinement moves the CP3a row and mints none. Each refusal
    leaves the durable estimate exactly as it was."""

    from dataclasses import replace as _replace

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-illegal")
    action_id = action_of(world, str(completion.turn_id))
    durable = world.deliveries.get_exposure_estimate(action_id)
    assert isinstance(durable, Ok) and durable.value is not None
    estimate = durable.value

    for illegal, expected in (
        (_replace(estimate, certainty="UNKNOWN"), DomainErrorCode.VALIDATION_FAILED),
        (_replace(estimate, certainty="MAYBE"), DomainErrorCode.VALIDATION_FAILED),
        (
            _replace(estimate, exposure_level="PARTIAL"),
            DomainErrorCode.VALIDATION_FAILED,
        ),
        (
            _replace(estimate, max_possible_exposure="PARTIAL"),
            DomainErrorCode.VALIDATION_FAILED,
        ),
        (
            # a renamed action is an *unknown* action from the store's view (the
            # lookup is by the submitted id): NOT_FOUND, never a move of another
            # action's row. The pure face's identity check is exercised by
            # ``test_p9_4_exposure_derivation``.
            _replace(estimate, action_id=ActionId("ga-somewhere-else")),
            DomainErrorCode.NOT_FOUND,
        ),
    ):
        refused = world.deliveries.refine_exposure_estimate(illegal)
        assert isinstance(refused, Err), illegal
        assert refused.error.code is expected, illegal
        assert _estimate_row(world, action_id) == (
            estimate.certainty,
            estimate.exposure_level,
            estimate.max_possible_exposure,
            estimate.confirmed_exposure,
            estimate.derivation_reason,
        )

    # a legal raise still goes through (the control for the refusals above)
    raised = world.deliveries.refine_exposure_estimate(
        _replace(estimate, certainty="CONFIRMED_RENDERED")
    )
    assert isinstance(raised, Ok), raised
    assert _estimate_row(world, action_id)[0] == "CONFIRMED_RENDERED"


def test_the_refinement_face_answers_not_found_for_an_action_with_no_row(
    world: StreamWorld,
) -> None:
    """The face refines CP3a's row and mints none: an action that never
    produced an estimate gets ``NOT_FOUND``, not a fabricated one."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    coordinator = type(coordinator_(world))(
        lease=lease,
        conversation_commands=world.store,
        conversation_queries=world.store,
        persona=PersonaRuntime(
            actions=world.generation,
            provider=ScriptedPersonaProvider(script=(ProviderOutput(text=""),)),
            compiler=PromptCompiler(),
            validator=ResponseValidator(),
            max_provider_attempts=2,
        ),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=world.deliveries,
    )
    completion = begin_turn_ok(coordinator, "cmid-p9-4-not-found")
    action_id = action_of(world, str(completion.turn_id))

    from elc.runtime.delivery_records import ExposureEstimate

    refused = world.deliveries.refine_exposure_estimate(
        ExposureEstimate(
            action_id=action_id,
            certainty="CONFIRMED_RENDERED",
            exposure_level="FULL",
            max_possible_exposure="FULL",
            confirmed_exposure="FULL",
            derivation_reason="an estimate this action never had",
        )
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.NOT_FOUND
    assert "mints none" in refused.error.message
    assert world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 0


def test_a_second_chunk_ack_is_its_own_row_and_moves_nothing_further(
    world: StreamWorld,
) -> None:
    """§22 keys the ACK stream by (action, chunk): a second chunk's
    acknowledgment is a second row, and it refines nothing the first one
    already raised — the estimate is byte-identical afterwards (the entry's own
    "only raises" rule, read on the durable row)."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-two-chunks")
    action_id = action_of(world, str(completion.turn_id))
    coordinator = coordinator_(world)
    first = coordinator.accept_render_ack(_ack(action_id, seq=1, final=False))
    assert isinstance(first, Ok), first
    after_first = _estimate_row(world, action_id)
    assert after_first[0] == "CONFIRMED_RENDERED"
    assert after_first[3] == "NONE"  # a non-final ack confirms no level

    second = coordinator.accept_render_ack(_ack(action_id, seq=2, final=True))
    assert isinstance(second, Ok), second
    assert world.db.execute(
        "SELECT rendered_chunk_seq, final_rendered FROM client_render_ack"
        " ORDER BY rendered_chunk_seq"
    ).fetchall() == [(1, 0), (2, 1)]
    assert second.value.refined is True
    assert _estimate_row(world, action_id)[3] == "FULL"  # the final one confirms
    # and a replay of the *first* chunk's ack changes nothing at all
    before = _estimate_row(world, action_id)
    replay = coordinator.accept_render_ack(_ack(action_id, seq=1, final=False))
    assert isinstance(replay, Ok), replay
    assert replay.value.refined is False
    assert _estimate_row(world, action_id) == before


# -- ④ the one-way rule: the estimate path appends no §20 event ----------------


def test_an_ack_leaves_the_exposure_log_exactly_where_the_delivery_left_it(
    db: sqlite3.Connection, p8world
) -> None:
    """R4's one-way rule on the real chain: a teaching delivery appends its
    §20 ``teaching_presented`` (the delivery leg's write), and the
    acknowledgment — the estimate path's own second write — appends **none**.
    The count is the whole argument: one before, one after."""

    coordinator = teaching_coordinator(p8world)
    completion = p8_begin_turn_ok(coordinator, "cmid-p9-4-oneway")
    action_id = ActionId(str(completion.action_id))
    assert count_events(db) == 1
    events_before = db.execute(
        "SELECT event_id, event FROM planning_ledger_event"
    ).fetchall()

    receipt = coordinator.accept_render_ack(_ack(action_id))
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is True
    assert count_events(db) == 1
    assert db.execute(
        "SELECT event_id, event FROM planning_ledger_event"
    ).fetchall() == events_before
    # the ledger row's own derivation is unchanged too: only the §22 rows moved
    del action_id


def test_the_streamed_turn_writes_no_ledger_event_at_all(world: StreamWorld) -> None:
    """The ordinary persona turn is not a teaching presentation: no §20 word
    names it, and no face invents one — the estimate exists and the log stays
    empty."""

    completion = begin_turn_ok(coordinator_(world), "cmid-p9-4-ordinary")
    assert completion.ledger_event is None
    assert world.db.execute(
        "SELECT COUNT(*) FROM planning_ledger_event"
    ).fetchone()[0] == 0


def test_a_refused_estimate_write_never_changes_the_buffered_delivery(
    db: sqlite3.Connection, p8world
) -> None:
    """R-INV-010's shape, on the buffered face: the estimate is a derived
    record, so a refused write leaves the delivery exactly as it was — the
    reply is durable, the turn is completed — and the reason is reported
    through the delivery's own note channel rather than swallowed."""

    refusing = RefusingEstimateStore(
        SqliteDeliveryRecordStore(p8world.db, p8world.fence)
    )
    coordinator = teaching_coordinator(p8world, records=refusing)
    completion = p8_begin_turn_ok(coordinator, "cmid-p9-4-refused")
    assert completion.outcome == "REPLIED_FULL"
    assert completion.reply_text is not None
    assert refusing.calls == 1
    assert completion.ledger_failure is not None
    assert "exposure estimate could not be written" in completion.ledger_failure
    assert completion.ledger_event == "teaching_presented"
    # the delivery itself is untouched: transcript, action, one §20 event
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 1
    assert db.execute("SELECT status FROM turn_record").fetchone() == (
        "COMPLETED",
    )
    assert count_events(db) == 1
    assert db.execute("SELECT COUNT(*) FROM exposure_estimate").fetchone()[0] == 0


def test_a_refused_estimate_write_never_changes_the_streamed_delivery(
    world: StreamWorld,
) -> None:
    """The same shape on the streamed face, whose note channel is
    ``delivery_failure_reason``: the prefix still lands, the turn still
    completes ``REPLIED_FULL``, and the refusal is readable beside it."""

    refusing = RefusingEstimateStore(world.deliveries)
    completion = begin_turn_ok(
        coordinator_(world, records=refusing), "cmid-p9-4-refused-stream"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert completion.reply_text == REPLY
    assert refusing.calls == 1
    assert completion.delivery_failure_reason is not None
    assert "exposure estimate could not be written" in (
        completion.delivery_failure_reason
    )
    assert world.db.execute(
        "SELECT COUNT(*) FROM assistant_turn"
    ).fetchone()[0] == 1
    assert world.db.execute(
        "SELECT COUNT(*) FROM exposure_estimate"
    ).fetchone()[0] == 0
    assert world.db.execute(
        "SELECT content FROM assistant_turn"
    ).fetchone()[0] == REPLY
