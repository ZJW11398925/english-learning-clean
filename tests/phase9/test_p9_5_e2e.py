"""P9-5 B — two whole chains, step by step (IP §10's two delivery modes).

``begin_turn`` is one call from the outside, so "the chain's steps" are only
observable from a boundary the coordinator itself calls. Both chains below are
therefore driven through a **window**: a wrapper over the conversation command
face that takes a read of the durable tables *before* each named write. The
steps in each docstring are those boundaries, and every step is asserted on the
rows the window read — never on the returned object alone.

The two chains are the two default rows of RA §13's table:

- ① **GUARDED_STREAM** — ordinary persona chat (``NORMAL_PERSONA_REPLY``),
  delivered as a stream under the pre-delivery guard, canonicalized from the
  durable ``sent_prefix``, with PA §6's no-wait-ACK turn terminalization and the
  asynchronous refinement landing afterwards;
- ② **BUFFERED_VALIDATED** — the teaching legs' mode, on the real ALLOW chain
  of the P8-4 world (a real gate decision, a real moment, a real lock): the
  whole validated text is delivered at once, the §20 exposure event is the
  delivery leg's, and §22's ``server_delivery_record`` stays **empty** because
  a buffered delivery keeps no stream boundary to record.

Nothing is copied from the single-point suites: ① asserts the row's *advance
sequence* plus the two windows, ② asserts the teaching chain's durable ladder
(CP2's facts → the delivery → the §20 event → the moment's move) and the
buffered face's **§22 silence** — the reading the two modes are told apart by.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Mapping

import pytest

from elc.platform.types import Ok
from elc.runtime.guarded_stream import StreamStep
from tests.phase8.p8_4_world import (
    PLANNER_FACT_TABLES,
    TEACHING_FACT_TABLES,
    World,
    count_events,
)
from tests.phase8.p8_4_world import (
    begin_turn_ok as p8_begin_turn_ok,
)
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    RecordingStore,
    ScriptedSource,
    SourceFactory,
    action_of,
    begin_turn_ok,
    pieces,
    second_connection_row,
    stream_world,
)
from tests.phase9.test_p9_3_barge_in import (
    coordinator_for,
    second_connection_rows,
)
from tests.phase9.test_p9_5_promise_list import (
    MASTERY_TABLES,
    all_rows,
    count_rows,
    estimate_row,
    render_ack,
    rows_of,
    table_counts,
    teaching_coordinator,
)

__all__ = ["ChainWindow", "WATCHED_BOUNDARIES", "WindowedCommands"]

#: The three boundaries every chain below is watched at, in the order the
#: shipped coordinator hits them.
WATCHED_BOUNDARIES: tuple[str, ...] = (
    "commit_user_turn",
    "canonicalize_assistant_turn",
    "terminalize_turn",
)


# -- the window ----------------------------------------------------------------


class ChainWindow:
    """The intermediate durable rows of one turn, read inside the chain.

    ``take(boundary)`` reads the tables a delivery chain writes — the
    transcript, the turn rows, the §22 row, the estimate, the §21.1 guard rows,
    the §20 log, the moment and its lock, the gate decisions — at the instant
    *before* the named command runs. The point is to assert rows that the final
    state no longer shows (a turn that was ``GENERATING``, a moment that was
    ``OPENING``, a transcript that did not exist yet) without predicting them
    from the code.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.windows: list[tuple[str, dict[str, object]]] = []

    def take(self, boundary: str) -> None:
        self.windows.append((boundary, self._snapshot()))

    def _snapshot(self) -> dict[str, object]:
        return {
            "transcript": all_rows(self.db, "assistant_turn"),
            "turns": rows_of(
                self.db,
                "SELECT turn_id, status, turn_outcome FROM turn_record"
                " ORDER BY turn_id",
            ),
            "delivery": rows_of(
                self.db,
                "SELECT action_id, state, sent_prefix, last_chunk_seq,"
                " started_at, terminal_at FROM server_delivery_record"
                " ORDER BY action_id",
            ),
            "estimate": all_rows(self.db, "exposure_estimate"),
            "guard": rows_of(
                self.db,
                "SELECT action_id, decision FROM pre_delivery_guard_result"
                " ORDER BY action_id",
            ),
            "events": all_rows(self.db, "planning_ledger_event"),
            "moment": rows_of(
                self.db,
                "SELECT moment_id, lifecycle_state FROM teaching_moment",
            ),
            "locks": count_rows(self.db, "active_teaching_lock"),
            "gate_decisions": count_rows(self.db, "gate_decision"),
            "acks": count_rows(self.db, "client_render_ack"),
        }

    def boundaries(self) -> tuple[str, ...]:
        return tuple(boundary for boundary, _ in self.windows)

    def at(self, boundary: str) -> Mapping[str, object]:
        """The **first** window taken at ``boundary``."""

        taken = [snap for name, snap in self.windows if name == boundary]
        assert taken, f"the chain never reached {boundary!r}"
        return taken[0]

    def times(self, boundary: str) -> int:
        return sum(1 for name, _ in self.windows if name == boundary)


class WindowedCommands:
    """The real conversation command face, watched at the three boundaries.

    Everything else is delegated unchanged, so the chain under test is the
    shipped one; the wrapper only *reads* before the three writes.
    """

    def __init__(self, inner: object, window: ChainWindow) -> None:
        self._inner = inner
        self._window = window

    def commit_user_turn(self, *args: object, **kwargs: object):
        self._window.take("commit_user_turn")
        return self._inner.commit_user_turn(*args, **kwargs)  # type: ignore[attr-defined]

    def canonicalize_assistant_turn(self, *args: object, **kwargs: object):
        self._window.take("canonicalize_assistant_turn")
        return self._inner.canonicalize_assistant_turn(  # type: ignore[attr-defined]
            *args, **kwargs
        )

    def terminalize_turn(self, *args: object, **kwargs: object):
        self._window.take("terminalize_turn")
        return self._inner.terminalize_turn(*args, **kwargs)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


# -- ① the streamed ordinary chat chain ---------------------------------------


@pytest.mark.parametrize("cuts", [1, 3])
def test_the_guarded_stream_chat_chain_step_by_step(
    tmp_path: Path, cuts: int
) -> None:
    """**Chain ①: GUARDED_STREAM ordinary chat**, over a real app.db, at two
    chunkings (V1's one-chunk default and a three-chunk source) so no step
    below is a property of one transport.

    The steps, and what each one is asserted on:

    1. **CP0** (``commit_user_turn``) — the user turn is durable and *nothing
       else* is: the window read at that boundary shows zero transcript rows,
       zero §22 rows, zero estimates, zero §21.1 rows and zero §20 events;
    2. **the action** — the persona runtime walks §14's action machine to
       ``READY_TO_DELIVER``, bound to the turn's own decision cycle;
    3. **§15's PreDeliveryGuard** — one §21.1 row, ``VALID``, written *after*
       the §22 row opened (the window at canonicalization shows both);
    4. **the §22 row's advancement** — ``SENDING`` with an empty prefix, one
       ``SENT_PARTIAL`` per accepted chunk (prefix so far, sequence number),
       then frozen ``SENT_COMPLETE`` with the terminal instant (the submission
       log *and* the durable row on a second connection);
    5. **CP3a's estimate** — written after the row froze: ``FULL``/``FULL`` with
       ``confirmed_exposure = NONE`` and the derivation's own reason;
    6. **the transcript** — canonicalized from the **durable** ``sent_prefix``
       verbatim, ``SENT_COMPLETE``, ``SERVER_SENT_UNCONFIRMED`` (both rows read
       independently);
    7. **the turn and the action terminalize** — ``COMPLETED`` /
       ``REPLIED_FULL``, action ``TERMINAL``;
    8. **no ACK is waited for** (RA §6) — the turn writes zero
       ``client_render_ack`` rows, and the acknowledgment that arrives
       *afterwards* moves the estimate's certainty only.
    """

    stream = stream_world(tmp_path)
    window = ChainWindow(stream.db)
    chunks = pieces(REPLY, cuts)
    source = ScriptedSource(
        steps=tuple(StreamStep.chunk(piece) for piece in chunks)
    )
    spy = RecordingStore(stream.deliveries)
    coordinator = coordinator_for(
        stream,
        transport=SourceFactory(source),
        commands=WindowedCommands(stream.store, window),
        records=spy,
    )

    completion = begin_turn_ok(coordinator, "cmid-p9-5-e2e-stream")
    turn_id = str(completion.turn_id)
    action_id = action_of(stream, turn_id)

    # every boundary was reached exactly once (a second terminalization or a
    # re-canonicalization would be a different chain)
    assert window.boundaries() == WATCHED_BOUNDARIES

    # 1. CP0: the write that makes the turn durable is this one, so the window
    #    taken before it finds an empty chain — every table this chain writes
    at_cp0 = window.at("commit_user_turn")
    assert at_cp0["transcript"] == ()
    assert at_cp0["delivery"] == []
    assert at_cp0["estimate"] == ()
    assert at_cp0["guard"] == []
    assert at_cp0["events"] == ()
    assert at_cp0["turns"] == []

    # 3. the guard ran and its row is durable before the transcript exists
    at_cp3 = window.at("canonicalize_assistant_turn")
    assert at_cp3["transcript"] == ()  # the transcript is this write's
    assert at_cp3["guard"] == [(str(action_id), "VALID")]
    # 4. … and by then the §22 row is already frozen at the run's terminal word
    delivery_at_cp3 = at_cp3["delivery"]
    assert len(delivery_at_cp3) == 1  # type: ignore[arg-type]
    (
        delivery_action,
        state,
        prefix,
        sequence,
        started_at,
        terminal_at,
    ) = delivery_at_cp3[0]  # type: ignore[index]
    assert delivery_action == str(action_id)
    assert (state, prefix, sequence) == ("SENT_COMPLETE", REPLY, len(chunks))
    assert terminal_at is not None and started_at != ""

    # 5. CP3a's estimate is durable *before* the transcript is canonicalized
    #    (the streamed face's own order: the row freezes, the estimate lands,
    #    the transcript is written from the durable prefix) — and the transcript
    #    still does not exist at that boundary
    at_terminal = window.at("terminalize_turn")
    assert len(at_terminal["estimate"]) == 1  # type: ignore[arg-type]
    assert len(at_cp3["estimate"]) == 1  # type: ignore[arg-type]
    assert at_cp3["estimate"][0][0] == str(action_id)  # type: ignore[index]
    assert at_terminal["transcript"] != ()
    assert at_cp3["transcript"] == ()
    assert [
        row[1] for row in at_terminal["turns"]  # type: ignore[union-attr]
    ] == ["DELIVERING"]

    # 4'. the row's whole life, as the submissions the caller made
    expected_submissions: list[tuple[str, str, int, str | None]] = [
        ("SENDING", "", 0, None)
    ]
    for index, piece in enumerate(chunks, start=1):
        expected_submissions.append(
            ("SENT_PARTIAL", "".join(chunks[:index]), index, None)
        )
    expected_submissions.append(
        ("SENT_COMPLETE", REPLY, len(chunks), spy.submitted[-1].terminal_at)
    )
    assert [
        (row.state, row.sent_prefix, row.last_chunk_seq, row.terminal_at)
        for row in spy.submitted
    ] == expected_submissions
    assert spy.submitted[-1].terminal_at is not None
    assert {row.started_at for row in spy.submitted} == {started_at}
    assert source.emitted == chunks

    # 6. the transcript and the §22 row are two rows read independently
    durable_state, durable_prefix, durable_seq, _, durable_terminal = (
        second_connection_row(stream, action_id)
    )
    assert (durable_state, durable_prefix, durable_seq) == (
        "SENT_COMPLETE",
        REPLY,
        len(chunks),
    )
    assert durable_terminal == spy.submitted[-1].terminal_at
    transcript = second_connection_rows(
        stream,
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn",
    )
    assert transcript == [(durable_prefix, "SENT_COMPLETE", "SERVER_SENT_UNCONFIRMED")]

    # 5'. the estimate's columns, read where CP3a wrote them
    assert estimate_row(stream.db, action_id) == (
        "SERVER_SENT_UNCONFIRMED",
        "FULL",
        "FULL",
        "NONE",
        f"sent {len(REPLY)} of {len(REPLY)} chars; no render ack",
    )

    # 7. terminalization
    assert (completion.turn_status.value, completion.outcome) == (
        "COMPLETED",
        "REPLIED_FULL",
    )
    assert completion.reply_text == durable_prefix
    assert completion.failure_reason is None
    assert completion.delivery_failure_reason is None
    action = stream.generation.get_action(action_id)
    assert isinstance(action, Ok) and action.value is not None
    assert action.value.status.value == "TERMINAL"

    # 8. the no-wait-ACK turn, and the acknowledgment that arrives later
    assert count_rows(stream.db, "client_render_ack") == 0
    before_counts = table_counts(stream.db)
    transcript_rows_before = all_rows(stream.db, "assistant_turn")
    receipt = coordinator.accept_render_ack(
        render_ack(action_id, seq=len(chunks), final=True)
    )
    assert isinstance(receipt, Ok), receipt
    assert receipt.value.refined is True
    assert estimate_row(stream.db, action_id)[:4] == (
        "CONFIRMED_RENDERED",
        "FULL",
        "FULL",
        "FULL",
    )
    # the refinement moved the two §22 rows and nothing else
    moved = {
        table: (before_counts[table], count)
        for table, count in table_counts(stream.db).items()
        if count != before_counts[table]
    }
    assert moved == {"client_render_ack": (0, 1)}
    assert all_rows(stream.db, "assistant_turn") == transcript_rows_before
    assert second_connection_rows(
        stream,
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn",
    ) == transcript


# -- ② the buffered teaching chain --------------------------------------------


def test_the_buffered_teaching_chain_step_by_step(
    db: sqlite3.Connection, p8world: World
) -> None:
    """**Chain ②: BUFFERED_VALIDATED teaching**, on the real ALLOW chain.

    The steps, and what each one is asserted on:

    1. **CP0** — the user turn is durable; the window read at that boundary
       shows no moment, no lock, no gate decision, no transcript and no §20
       event (the automatic leg has not run yet);
    2. **CP2** — the planner half plus the §14 five teaching facts are durable
       and the moment is ``OPENING`` with its lock held (the window at
       canonicalization reads them);
    3. **the buffered delivery** — the whole validated text, delivered whole:
       the transcript is the delivered text verbatim, ``SENT_COMPLETE`` with
       ``SERVER_SENT_UNCONFIRMED``, and **§22's row stays empty** (a buffered
       delivery keeps no stream boundary to record — the reading that tells the
       two modes apart);
    4. **CP3a's estimate** — one row, ``FULL``/``FULL``/``NONE`` with the atomic
       face's own reason (``sent N chars``, not ``sent N of N``);
    5. **§20** — exactly one ``teaching_presented`` event, with the
       deterministic id ``ev-<action_id>`` and the moment in its provenance
       column (written after the turn's own writes, which is why the window at
       the terminalization boundary still shows zero);
    6. **the moment's ladder** — ``OPENING`` → ``AWAITING_USER``, its lock still
       held (a live moment keeps it), and no ACK row anywhere (RA §6).
    """

    window = ChainWindow(db)
    coordinator = teaching_coordinator(
        p8world, commands=WindowedCommands(p8world.store, window)
    )
    completion = p8_begin_turn_ok(coordinator, "cmid-p9-5-e2e-teaching")
    assert completion.action_id is not None
    action_id = completion.action_id

    assert window.boundaries() == WATCHED_BOUNDARIES

    # 1. CP0: the turn row is this write's, so the window taken before it finds
    #    an empty automatic leg — no moment, no lock, no gate decision
    at_cp0 = window.at("commit_user_turn")
    assert at_cp0["transcript"] == ()
    assert at_cp0["moment"] == []
    assert at_cp0["locks"] == 0
    assert at_cp0["gate_decisions"] == 0
    assert at_cp0["events"] == ()
    assert at_cp0["delivery"] == []
    assert at_cp0["estimate"] == ()
    assert at_cp0["turns"] == []

    # 2. CP2: the gate decided, the moment is OPENING with its lock held, the
    #    planner half is durable — and the delivery has not happened yet
    at_cp3 = window.at("canonicalize_assistant_turn")
    assert at_cp3["gate_decisions"] == 1
    assert at_cp3["locks"] == 1
    assert [
        row[1] for row in at_cp3["moment"]  # type: ignore[union-attr]
    ] == ["OPENING"]
    assert at_cp3["transcript"] == ()
    assert at_cp3["estimate"] == ()
    assert at_cp3["events"] == ()
    assert at_cp3["delivery"] == []  # a buffered delivery keeps no §22 row

    # 3./4. at the terminalization boundary the transcript and the estimate are
    #    durable; the §20 event is *not* yet (the leg writes it after delivery)
    at_terminal = window.at("terminalize_turn")
    assert at_terminal["transcript"] != ()
    assert at_terminal["estimate"] != ()
    assert at_terminal["events"] == ()
    assert at_terminal["delivery"] == []

    # 3'. the transcript is the delivered text, verbatim, on the buffered word
    assert completion.reply_text is not None and completion.reply_text != ""
    assert rows_of(
        db,
        "SELECT content, delivery_state, delivery_certainty FROM assistant_turn",
    ) == [
        (
            completion.reply_text,
            "SENT_COMPLETE",
            "SERVER_SENT_UNCONFIRMED",
        )
    ]
    assert count_rows(db, "server_delivery_record") == 0
    assert count_rows(db, "client_render_ack") == 0

    # 4'. the atomic estimate: the text as its boundary, no comparison length
    assert estimate_row(db, action_id) == (
        "SERVER_SENT_UNCONFIRMED",
        "FULL",
        "FULL",
        "NONE",
        f"sent {len(completion.reply_text)} chars; no render ack",
    )

    # 5. §20: exactly one presentation, with the deterministic id and the moment
    assert count_events(db) == 1
    assert completion.ledger_event == "teaching_presented"
    assert completion.ledger_failure is None
    event = all_rows(db, "planning_ledger_event")
    assert len(event) == 1
    assert event[0][0] == f"ev-{action_id}"
    assert event[0][2] == "teaching_presented"
    assert event[0][4] == str(
        db.execute("SELECT moment_id FROM teaching_moment").fetchone()[0]
    )

    # 6. the moment's ladder and its lock
    assert rows_of(
        db, "SELECT lifecycle_state FROM teaching_moment"
    ) == [("AWAITING_USER",)]
    assert count_rows(db, "active_teaching_lock") == 1
    assert count_rows(db, "assistant_turn") == 1

    # CP2's facts are all durable, one row each (the two declared groups)
    for table in TEACHING_FACT_TABLES + PLANNER_FACT_TABLES:
        assert count_rows(db, table) == 1, table

    # and the chain wrote no mastery, no evidence and no attempt row
    for table in MASTERY_TABLES:
        assert all_rows(db, table) == (), table

    # 6'. the turn's terminal word and the action's own status
    assert (completion.turn_status.value, completion.outcome) == (
        "COMPLETED",
        "REPLIED_FULL",
    )
    assert rows_of(
        db,
        "SELECT status, turn_outcome FROM turn_record",
    ) == [("COMPLETED", "REPLIED_FULL")]
    assert rows_of(
        db,
        "SELECT status FROM generation_action_intent",
    ) == [("TERMINAL",)]
