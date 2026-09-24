"""P9-1 ② — the delivery-record store: five faces, one rule each.

The write half is exercised on the real chain: a durable conversation, its CP0
turn, a real DecisionCycle row and a real ``generation_action_intent`` row —
no ``_seed``-shaped helper and no fixture target provider (the P5-1 red line).
Against that world the five faces are driven through every verdict they have:

- **round trips** for all five rows, plus the two negative spaces (an absent
  row reads as ``Ok(None)`` / an empty tuple);
- **replay** (a byte-identical re-submission returns the durable row and
  touches nothing — ``total_changes`` is the witness);
- **conflict** (a differing re-submission is ``Err(CONFLICT)`` and the durable
  row is unchanged);
- the **four advance invariants** of the server-delivery row, each with its
  positive and negative direction;
- the **epoch fence** (a stale fence refuses and writes nothing), and the same
  database read back through a **second connection**;
- the **no-clock rule** (the instant is content: a differing instant is a
  conflict, a missing one is refused);
- the **vocabulary refusals** (§22's word columns are refused by the port with
  ``VALIDATION_FAILED``; §21.1's two ``decision`` columns are refused by the
  schema, which the adapter answers as ``CONFLICT``).
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import CommitUserTurn
from elc.persona.types import ValidatorDecision, ValidatorResult
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.delivery_store import (
    SqliteDeliveryRecordStore,
    StaleDeliveryRecordStoreError,
)
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    DecisionCycleId,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    TurnId,
)
from elc.runtime.delivery_records import (
    ClientRenderAck,
    ExposureEstimate,
    PreDeliveryGuardResult,
    ServerDeliveryRecord,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
)
from tests.phase7.conftest import CONV, USER
from tests.phase8.conftest import (
    RECEIVED_AT,
    RUNTIME_VERSION,
    open_cycle,
)

ACTION_ID = ActionId("act-p9-1")
ASSISTANT_TURN = "at-p9-1"
STARTED = "2026-09-24T09:00:00+00:00"
ACKED = "2026-09-24T09:00:02+00:00"
TERMINAL = "2026-09-24T09:00:05+00:00"
CREATED = "2026-09-24T09:00:01+00:00"
GUARDED = "2026-09-24T08:59:59+00:00"


# -- the world ---------------------------------------------------------------


@pytest.fixture()
def store(
    db: sqlite3.Connection, fence
) -> SqliteDeliveryRecordStore:
    return SqliteDeliveryRecordStore(db, fence)


def _action_intent(turn_id, cycle_id, action_id: str) -> GenerationActionIntentRecord:
    return GenerationActionIntentRecord(
        action_id=ActionId(action_id),
        turn_id=turn_id,
        decision_cycle_id=cycle_id,
        moment_id=None,
        assistant_turn_id=ASSISTANT_TURN,
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-p9-1",
        status=GenerationActionStatus.PREPARED,
        attempt_count=0,
    )


@pytest.fixture()
def action(db: sqlite3.Connection, fence, cycle) -> ActionId:
    """One durable action on the P8-0 world's real turn and cycle."""

    result = SqliteGenerationStore(db, fence).create_action(
        _action_intent(cycle.turn_id, cycle.decision_cycle_id, str(ACTION_ID))
    )
    assert isinstance(result, Ok), result
    return ACTION_ID


def _server(**overrides: object) -> ServerDeliveryRecord:
    bag: dict[str, object] = {
        "action_id": ACTION_ID,
        "assistant_turn_id": ASSISTANT_TURN,
        "state": "SENDING",
        "sent_prefix": "",
        "last_chunk_seq": 0,
        "started_at": STARTED,
        "terminal_at": None,
    }
    bag.update(overrides)
    return ServerDeliveryRecord(**bag)  # type: ignore[arg-type]


def _ack(**overrides: object) -> ClientRenderAck:
    bag: dict[str, object] = {
        "action_id": ACTION_ID,
        "assistant_turn_id": ASSISTANT_TURN,
        "rendered_chunk_seq": 0,
        "rendered_text_hash": "sha256:chunk-0",
        "acked_at": ACKED,
        "final_rendered": False,
    }
    bag.update(overrides)
    return ClientRenderAck(**bag)  # type: ignore[arg-type]


def _estimate(**overrides: object) -> ExposureEstimate:
    bag: dict[str, object] = {
        "action_id": ACTION_ID,
        "certainty": "SERVER_SENT_UNCONFIRMED",
        "exposure_level": "PARTIAL",
        "max_possible_exposure": "PARTIAL",
        "confirmed_exposure": "NONE",
        "derivation_reason": "buffered delivery with no ACK yet",
    }
    bag.update(overrides)
    return ExposureEstimate(**bag)  # type: ignore[arg-type]


def _validator(**overrides: object) -> ValidatorResult:
    bag: dict[str, object] = {
        "validator_result_id": "vr-p9-1",
        "action_id": ACTION_ID,
        "attempt_no": 1,
        "decision": ValidatorDecision.ACCEPT,
        "reason_codes": ("STYLE_OK",),
        "validator_version": "validator-v1",
        "created_at": CREATED,
    }
    bag.update(overrides)
    return ValidatorResult(**bag)  # type: ignore[arg-type]


def _guard(**overrides: object) -> PreDeliveryGuardResult:
    bag: dict[str, object] = {
        "pre_delivery_guard_result_id": "pg-p9-1",
        "action_id": ACTION_ID,
        "decision": "VALID",
        "reason_codes": (),
        "checked_lineage_version": "lineage-v1",
        "created_at": GUARDED,
    }
    bag.update(overrides)
    return PreDeliveryGuardResult(**bag)  # type: ignore[arg-type]


def _unwrap(result):
    assert isinstance(result, Ok), result
    return result.value


def _count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# -- ① round trips -----------------------------------------------------------


def test_a_server_delivery_row_round_trips(db, store, action) -> None:
    record = _server()
    written = _unwrap(store.record_server_delivery(record))
    assert written == record
    assert _unwrap(store.get_server_delivery_record(action)) == record
    assert _count(db, "server_delivery_record") == 1
    row = db.execute(
        "SELECT action_id, assistant_turn_id, state, sent_prefix,"
        " last_chunk_seq, started_at, terminal_at FROM server_delivery_record"
    ).fetchone()
    assert row == (
        str(ACTION_ID),
        ASSISTANT_TURN,
        "SENDING",
        "",
        0,
        STARTED,
        None,
    )


def test_an_ack_row_round_trips(db, store, action) -> None:
    ack = _ack(rendered_chunk_seq=3, final_rendered=True)
    written = _unwrap(store.append_client_render_ack(ack))
    assert written == ack
    assert _unwrap(store.list_client_render_acks(action)) == (ack,)
    assert _unwrap(store.get_server_delivery_record(action)) is None


def test_the_ack_boolean_lands_as_the_one_bit(db, store, action) -> None:
    _unwrap(store.append_client_render_ack(_ack(final_rendered=True)))
    row = db.execute("SELECT final_rendered FROM client_render_ack").fetchone()
    assert row == (1,)
    assert _unwrap(store.list_client_render_acks(action))[0].final_rendered is True


def test_an_estimate_row_round_trips(db, store, action) -> None:
    estimate = _estimate()
    written = _unwrap(store.record_initial_exposure_estimate(estimate))
    assert written == estimate
    assert _unwrap(store.get_exposure_estimate(action)) == estimate


def test_a_validator_row_round_trips(db, store, action) -> None:
    result = _validator(reason_codes=("A", "B"))
    written = _unwrap(store.append_validator_result(result))
    assert written == result
    assert _unwrap(store.list_validator_results(action)) == (result,)
    row = db.execute(
        "SELECT reason_codes, decision FROM validator_result"
    ).fetchone()
    assert row == ('["A","B"]', "ACCEPT")


def test_a_guard_row_round_trips(db, store, action) -> None:
    guard = _guard(reason_codes=("LINEAGE_OK",))
    written = _unwrap(store.append_pre_delivery_guard_result(guard))
    assert written == guard
    assert _unwrap(store.list_pre_delivery_guard_results(action)) == (guard,)


def test_absent_rows_read_as_none_and_empty(store) -> None:
    missing = ActionId("act-p9-1-absent")
    assert store.get_server_delivery_record(missing) == Ok(None)
    assert store.get_exposure_estimate(missing) == Ok(None)
    assert store.list_client_render_acks(missing) == Ok(())
    assert store.list_validator_results(missing) == Ok(())
    assert store.list_pre_delivery_guard_results(missing) == Ok(())


def test_the_ack_read_is_ordered_by_chunk(db, store, action) -> None:
    _unwrap(store.append_client_render_ack(_ack(rendered_chunk_seq=2)))
    _unwrap(store.append_client_render_ack(_ack(rendered_chunk_seq=0)))
    _unwrap(store.append_client_render_ack(_ack(rendered_chunk_seq=1)))
    assert [
        ack.rendered_chunk_seq
        for ack in _unwrap(store.list_client_render_acks(action))
    ] == [0, 1, 2]


def test_the_validator_read_is_ordered_by_attempt(db, store, action) -> None:
    _unwrap(
        store.append_validator_result(
            _validator(
                validator_result_id="vr-late",
                attempt_no=2,
                decision=ValidatorDecision.RETRY,
            )
        )
    )
    _unwrap(
        store.append_validator_result(
            _validator(validator_result_id="vr-first", attempt_no=1)
        )
    )
    assert [
        result.attempt_no
        for result in _unwrap(store.list_validator_results(action))
    ] == [1, 2]


def test_the_guard_read_is_ordered_by_instant(db, store, action) -> None:
    _unwrap(
        store.append_pre_delivery_guard_result(
            _guard(
                pre_delivery_guard_result_id="pg-late",
                created_at="2026-09-24T09:00:04+00:00",
            )
        )
    )
    _unwrap(
        store.append_pre_delivery_guard_result(
            _guard(pre_delivery_guard_result_id="pg-early", created_at=GUARDED)
        )
    )
    assert [
        guard.pre_delivery_guard_result_id
        for guard in _unwrap(store.list_pre_delivery_guard_results(action))
    ] == ["pg-early", "pg-late"]


# -- ② replay -----------------------------------------------------------------


def test_a_server_replay_writes_nothing(db, store, action) -> None:
    record = _server()
    _unwrap(store.record_server_delivery(record))
    before = db.total_changes
    again = _unwrap(store.record_server_delivery(record))
    assert again == record
    assert db.total_changes == before


def test_an_ack_replay_writes_nothing(db, store, action) -> None:
    ack = _ack()
    _unwrap(store.append_client_render_ack(ack))
    before = db.total_changes
    assert _unwrap(store.append_client_render_ack(ack)) == ack
    assert db.total_changes == before
    assert _count(db, "client_render_ack") == 1


def test_a_validator_replay_writes_nothing(db, store, action) -> None:
    result = _validator()
    _unwrap(store.append_validator_result(result))
    before = db.total_changes
    assert _unwrap(store.append_validator_result(result)) == result
    assert db.total_changes == before


def test_a_guard_replay_writes_nothing(db, store, action) -> None:
    guard = _guard()
    _unwrap(store.append_pre_delivery_guard_result(guard))
    before = db.total_changes
    assert _unwrap(store.append_pre_delivery_guard_result(guard)) == guard
    assert db.total_changes == before


def test_an_estimate_replay_writes_nothing(db, store, action) -> None:
    estimate = _estimate()
    _unwrap(store.record_initial_exposure_estimate(estimate))
    before = db.total_changes
    assert _unwrap(store.record_initial_exposure_estimate(estimate)) == estimate
    assert db.total_changes == before


# -- ③ conflict ---------------------------------------------------------------


def _assert_conflict(result, *, table: str, db) -> None:
    assert isinstance(result, Err), result
    assert result.error.code is DomainErrorCode.CONFLICT
    assert _count(db, table) == 1


def test_a_differing_ack_is_a_conflict_and_leaves_the_row(db, store, action) -> None:
    ack = _ack()
    _unwrap(store.append_client_render_ack(ack))
    _assert_conflict(
        store.append_client_render_ack(
            replace(ack, rendered_text_hash="sha256:other")
        ),
        table="client_render_ack",
        db=db,
    )
    assert _unwrap(store.list_client_render_acks(action)) == (ack,)


def test_a_differing_validator_row_is_a_conflict(db, store, action) -> None:
    result = _validator()
    _unwrap(store.append_validator_result(result))
    _assert_conflict(
        store.append_validator_result(
            replace(result, decision=ValidatorDecision.ABORT_DELIVERY)
        ),
        table="validator_result",
        db=db,
    )
    assert _unwrap(store.list_validator_results(action)) == (result,)


def test_a_differing_guard_row_is_a_conflict(db, store, action) -> None:
    guard = _guard()
    _unwrap(store.append_pre_delivery_guard_result(guard))
    _assert_conflict(
        store.append_pre_delivery_guard_result(
            replace(guard, decision="INVALIDATE_ACTION")
        ),
        table="pre_delivery_guard_result",
        db=db,
    )
    assert _unwrap(store.list_pre_delivery_guard_results(action)) == (guard,)


def test_a_differing_estimate_is_a_conflict_written_once(db, store, action) -> None:
    estimate = _estimate()
    _unwrap(store.record_initial_exposure_estimate(estimate))
    _assert_conflict(
        store.record_initial_exposure_estimate(
            replace(estimate, derivation_reason="refined elsewhere")
        ),
        table="exposure_estimate",
        db=db,
    )
    assert _unwrap(store.get_exposure_estimate(action)) == estimate


# -- ④ the four advance invariants -------------------------------------------


def test_a_later_chunk_advances_the_row(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server()))
    second = _server(state="SENT_PARTIAL", sent_prefix="I thi", last_chunk_seq=3)
    assert _unwrap(store.record_server_delivery(second)) == second
    assert _unwrap(store.get_server_delivery_record(action)) == second
    row = db.execute(
        "SELECT state, sent_prefix, last_chunk_seq FROM server_delivery_record"
    ).fetchone()
    assert row == ("SENT_PARTIAL", "I thi", 3)


def test_a_decreasing_chunk_sequence_is_refused(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server(last_chunk_seq=3)))
    refused = store.record_server_delivery(_server(last_chunk_seq=2))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "never decreases" in refused.error.message
    assert _count(db, "server_delivery_record") == 1
    assert (
        _unwrap(store.get_server_delivery_record(action)).last_chunk_seq == 3
    )


def test_a_growing_prefix_advances_the_row(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server(sent_prefix="I thi")))
    second = _server(sent_prefix="I think", last_chunk_seq=7)
    assert _unwrap(store.record_server_delivery(second)).sent_prefix == "I think"


def test_a_prefix_that_does_not_extend_is_refused(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server(sent_prefix="I think")))
    for submitted in ("I th", "X think", ""):
        refused = store.record_server_delivery(_server(sent_prefix=submitted))
        assert isinstance(refused, Err), submitted
        assert refused.error.code is DomainErrorCode.CONFLICT
        assert "never shrinks" in refused.error.message
    assert _count(db, "server_delivery_record") == 1


def test_a_changed_assistant_turn_is_refused(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server()))
    refused = store.record_server_delivery(
        _server(assistant_turn_id="at-somebody-else")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "cannot change" in refused.error.message


def test_a_changed_start_instant_is_refused(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server()))
    refused = store.record_server_delivery(
        _server(started_at="2026-09-24T10:00:00+00:00")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "start instant is content" in refused.error.message


def test_setting_the_terminal_instant_advances_and_freezes(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server(sent_prefix="I thi")))
    terminal = _server(
        state="SENT_COMPLETE",
        sent_prefix="I think we should",
        last_chunk_seq=9,
        terminal_at=TERMINAL,
    )
    assert _unwrap(store.record_server_delivery(terminal)) == terminal
    # frozen: a differing submission is refused ...
    refused = store.record_server_delivery(
        _server(
            state="SENT_COMPLETE",
            sent_prefix="I think we should",
            last_chunk_seq=9,
            terminal_at=TERMINAL,
            assistant_turn_id="at-somebody-else",
        )
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    # ... and the byte-identical one is still the replay
    before = db.total_changes
    assert _unwrap(store.record_server_delivery(terminal)) == terminal
    assert db.total_changes == before


def test_a_terminal_row_cannot_go_back(db, store, action) -> None:
    _unwrap(store.record_server_delivery(_server(terminal_at=TERMINAL)))
    refused = store.record_server_delivery(_server(terminal_at=None))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "a terminal row is frozen" in refused.error.message


# -- ⑤ fencing and the second connection -------------------------------------


def test_a_stale_fence_refuses_a_write_and_writes_nothing(db, store, action) -> None:
    epoch.open_runtime_epoch(db)  # a restart: the store's fence is now stale
    with pytest.raises(StaleDeliveryRecordStoreError):
        store.record_server_delivery(_server())
    assert _count(db, "server_delivery_record") == 0


def test_a_stale_fence_refuses_every_write_face(db, store, action) -> None:
    epoch.open_runtime_epoch(db)
    for call in (
        lambda: store.record_server_delivery(_server()),
        lambda: store.append_client_render_ack(_ack()),
        lambda: store.append_validator_result(_validator()),
        lambda: store.append_pre_delivery_guard_result(_guard()),
        lambda: store.record_initial_exposure_estimate(_estimate()),
    ):
        with pytest.raises(StaleDeliveryRecordStoreError):
            call()
    for table in (
        "server_delivery_record",
        "client_render_ack",
        "exposure_estimate",
        "validator_result",
        "pre_delivery_guard_result",
    ):
        assert _count(db, table) == 0, table


def test_a_second_connection_sees_the_committed_row(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    first = connection.connect(path)
    try:
        migrations.apply_migrations(first)
        fence = epoch.open_runtime_epoch(first)
        _file_world(first, fence)
        store = SqliteDeliveryRecordStore(first, fence)
        _unwrap(store.record_server_delivery(_server(sent_prefix="I thi")))
        second = connection.connect(path)
        try:
            row = second.execute(
                "SELECT state, sent_prefix, last_chunk_seq"
                " FROM server_delivery_record WHERE action_id = ?",
                (str(ACTION_ID),),
            ).fetchone()
            assert row == ("SENDING", "I thi", 0)
            assert (
                second.execute(
                    "SELECT MAX(epoch) FROM runtime_epoch"
                ).fetchone()[0]
                == fence.current
            )
        finally:
            second.close()
    finally:
        first.close()


def _file_world(conn: sqlite3.Connection, fence) -> None:
    """Conversation → CP0 turn → cycle → action, on a file-backed db."""

    store = SqliteConversationStore(conn, fence)
    opened = store.open_conversation(
        CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    commit = store.commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId("in-p9-1-file"),
                client_message_id=ClientMessageId("cmid-p9-1-file"),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-p9-1-file",
                received_at=RECEIVED_AT,
            ),
            raw_content="A file-backed turn.",
            runtime_version=RUNTIME_VERSION,
            turn_id=TurnId("turn-p9-1-file"),
        )
    )
    assert isinstance(commit, Ok), commit
    world = open_cycle(
        conn,
        fence,
        decision_cycle_id=DecisionCycleId("dc-p9-1-file"),
        turn_id=commit.value.turn_id,
        expected_turn_state_version=commit.value.state_version,
    )
    result = SqliteGenerationStore(conn, fence).create_action(
        _action_intent(world.turn_id, world.decision_cycle_id, str(ACTION_ID))
    )
    assert isinstance(result, Ok), result


# -- ⑥ the no-clock rule ------------------------------------------------------


def test_a_different_ack_instant_is_a_conflict(db, store, action) -> None:
    ack = _ack()
    _unwrap(store.append_client_render_ack(ack))
    refused = store.append_client_render_ack(
        replace(ack, acked_at="2026-09-24T09:00:03+00:00")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert _unwrap(store.list_client_render_acks(action)) == (ack,)


def test_a_different_validator_instant_is_a_conflict(db, store, action) -> None:
    result = _validator()
    _unwrap(store.append_validator_result(result))
    refused = store.append_validator_result(
        replace(result, created_at="2026-09-24T09:00:09+00:00")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT


def test_a_validator_row_without_an_instant_is_refused(db, store, action) -> None:
    refused = store.append_validator_result(_validator(created_at=None))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "the instant is content" in refused.error.message
    assert _count(db, "validator_result") == 0


def test_a_guard_row_without_an_instant_cannot_be_built() -> None:
    """``created_at`` is a required field of the record — §21.1's block lists
    it without a ``?`` — so the second import face has no ``None`` spelling to
    refuse; the type is the guard."""

    with pytest.raises(TypeError):
        PreDeliveryGuardResult(  # type: ignore[call-arg]
            pre_delivery_guard_result_id="pg-x",
            action_id=ACTION_ID,
            decision="VALID",
            reason_codes=(),
            checked_lineage_version="lineage-v1",
        )


# -- ⑦ the vocabulary refusals ------------------------------------------------


def test_an_out_of_vocabulary_state_is_refused(db, store, action) -> None:
    refused = store.record_server_delivery(_server(state="ALMOST_DONE"))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert "not one of the words" in refused.error.message
    assert _count(db, "server_delivery_record") == 0


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("certainty", "PROBABLY"),
        ("exposure_level", "HALF"),
        ("max_possible_exposure", "MOST"),
        ("confirmed_exposure", "SOME"),
    ],
)
def test_an_out_of_vocabulary_estimate_word_is_refused(
    db, store, action, column: str, value: str
) -> None:
    refused = store.record_initial_exposure_estimate(_estimate(**{column: value}))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.VALIDATION_FAILED
    assert column in refused.error.message
    assert _count(db, "exposure_estimate") == 0


def test_every_section13_word_is_accepted(db, fence, store, cycle, action) -> None:
    """The refusal is the *vocabulary's* edge, not an over-tight constant:
    every word §13 lists is written and read back.

    The six state words advance one action's row (the sequence grows, the
    prefix stays empty — both monotone), and the three exposure words need one
    action each: the estimate is written once, so the second word on the same
    action would be a conflict rather than a vocabulary verdict.
    """

    for index, state in enumerate(
        (
            "NOT_SENT",
            "SENDING",
            "SENT_PARTIAL",
            "SENT_COMPLETE",
            "FAILED",
            "CANCELLED",
        )
    ):
        record = _server(state=state, last_chunk_seq=index)
        assert _unwrap(store.record_server_delivery(record)).state == state
    for index, certainty in enumerate(
        ("CONFIRMED_RENDERED", "SERVER_SENT_UNCONFIRMED", "UNKNOWN")
    ):
        other = ActionId(f"act-p9-1-words-{index}")
        created = SqliteGenerationStore(db, fence).create_action(
            _action_intent(cycle.turn_id, cycle.decision_cycle_id, str(other))
        )
        assert isinstance(created, Ok), created
        estimate = _estimate(action_id=other, certainty=certainty)
        written = _unwrap(store.record_initial_exposure_estimate(estimate))
        assert written.certainty == certainty
    for column, word in (
        ("exposure_level", "FULL"),
        ("max_possible_exposure", "FULL"),
        ("confirmed_exposure", "PARTIAL"),
    ):
        other = ActionId(f"act-p9-1-level-{column}")
        created = SqliteGenerationStore(db, fence).create_action(
            _action_intent(cycle.turn_id, cycle.decision_cycle_id, str(other))
        )
        assert isinstance(created, Ok), created
        estimate = _estimate(action_id=other, **{column: word})
        written = _unwrap(store.record_initial_exposure_estimate(estimate))
        assert getattr(written, column) == word


def test_the_validator_decision_vocabulary_is_the_enums(db, store, action) -> None:
    """``ValidatorResult.decision`` is the shipped ``ValidatorDecision`` enum,
    so the §21.1 CHECK is the schema's backstop and the type system holds the
    vocabulary first: the two are asserted to be the same four words, which is
    what makes "an out-of-vocabulary word cannot reach this column" a fact
    rather than an assumption (the guard column below is the reachable arm —
    its field is a plain ``str``)."""

    from elc.persona.types import ValidatorDecision

    assert tuple(member.value for member in ValidatorDecision) == (
        "ACCEPT",
        "RETRY",
        "FALLBACK",
        "ABORT_DELIVERY",
    )
    _unwrap(store.append_validator_result(_validator()))
    assert _count(db, "validator_result") == 1


def test_the_guard_decision_is_refused_by_the_schema(db, store, action) -> None:
    refused = store.append_pre_delivery_guard_result(
        replace(_guard(), decision="MAYBE")
    )
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert _count(db, "pre_delivery_guard_result") == 0


# -- ⑧ the action foreign key, and row isolation ------------------------------


def test_a_row_without_its_action_is_refused(db, store) -> None:
    """The five ``action_id`` columns reference the action table; the adapter
    answers the durable constraint as ``CONFLICT`` and writes nothing."""

    for call, table in (
        (lambda: store.record_server_delivery(_server()), "server_delivery_record"),
        (lambda: store.append_client_render_ack(_ack()), "client_render_ack"),
        (
            lambda: store.record_initial_exposure_estimate(_estimate()),
            "exposure_estimate",
        ),
        (lambda: store.append_validator_result(_validator()), "validator_result"),
        (
            lambda: store.append_pre_delivery_guard_result(_guard()),
            "pre_delivery_guard_result",
        ),
    ):
        refused = call()
        assert isinstance(refused, Err), table
        assert refused.error.code is DomainErrorCode.CONFLICT
        assert _count(db, table) == 0, table


def test_two_actions_rows_do_not_mix(db, fence, store, cycle, action) -> None:
    other = ActionId("act-p9-1-other")
    result = SqliteGenerationStore(db, fence).create_action(
        _action_intent(cycle.turn_id, cycle.decision_cycle_id, str(other))
    )
    assert isinstance(result, Ok), result
    _unwrap(store.record_server_delivery(_server()))
    _unwrap(
        store.record_server_delivery(
            replace(_server(), action_id=other, sent_prefix="theirs")
        )
    )
    assert (
        _unwrap(store.get_server_delivery_record(action)).sent_prefix == ""
    )
    assert (
        _unwrap(store.get_server_delivery_record(other)).sent_prefix == "theirs"
    )
