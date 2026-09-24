"""SQLite adapter for the §22 / §21.1 delivery records (P9-1).

TASK-OPI-e26b27a7-….3 §1-B. docs/DATA_MODEL.md §22 "Delivery Data" names
three records and §21.1 two more, and docs/RUNTIME_ARCHITECTURE.md §6 CP3a is
the commit point the §22 pair belongs to. The **port** — the four new row
shapes, the reused §21.1 shape, the vocabulary refusals and the single column
map — is :mod:`elc.runtime.delivery_records`; this module is where the SQL
lives, colocated with the other app.db adapters (``planner_store`` is the
sibling this one is modelled on: same epoch fence, same ``Ok``/``Err``
envelope, same fixed-literal statements with bound parameters).

**One short transaction per write, and no clock.** Every write owns one
``short_transaction`` under the owner-epoch fence: a fenced epoch raises
:class:`StaleDeliveryRecordStoreError` and the transaction rolls back whole.
The adapter reads no clock at all — ``started_at`` / ``terminal_at`` /
``acked_at`` / ``created_at`` arrive on the records, they are compared
**verbatim** on a replay, and a differing instant is a ``CONFLICT``
(``elc/runtime/delivery_records.py`` judgement 5). That is deliberately not
``planner_store``'s convention, and the port states why: these instants *are*
the delivery facts, not store bookkeeping.

**Replay vs. conflict — one rule, five faces.** A submission byte-identical to
the durable row is a **replay**: the durable row is returned and nothing is
written (RA §23's crash-window posture — a re-entry never doubles a fact).
A submission that differs is handled by the face's own rule:

* ``record_server_delivery`` **advances** while the four invariants of
  ``elc/runtime/delivery_records.py`` judgement 4 hold (``last_chunk_seq``
  never decreases, ``sent_prefix`` only grows, ``assistant_turn_id`` /
  ``started_at`` never change, a row with ``terminal_at`` set is frozen) and
  is ``CONFLICT`` otherwise;
* the four append faces (``client_render_ack``, ``validator_result``,
  ``pre_delivery_guard_result``, the initial exposure estimate) are
  ``CONFLICT`` — an appended fact is never rewritten, and the estimate is
  written once (judgement 7; refinement is P9-4's explicit face).

**Two refusal vocabularies, on purpose.** §22's word columns have no schema
CHECK (the words are STATE_MACHINES §13's), so this adapter calls the port's
Python refusals **before** the transaction opens and answers
``VALIDATION_FAILED``; §21.1's two ``decision`` columns are spelled inline by
migration 0018, so an out-of-vocabulary value there is the schema's
``IntegrityError`` and this adapter answers ``CONFLICT`` (the
``SqlitePlannerRecordStore`` posture for a durable-constraint refusal). The
thread is the port's judgement 2.

**Reads are plain and absent rows are facts.** The five reads answer
``Ok(None)`` / an empty tuple for an unknown action; ordering is pinned in the
statements (chunk sequence for the ACKs, ``attempt_no`` then id for the
validator rows, instant then id for the guard rows) so two callers see one
order.

All SQL is a fixed literal with bound parameters — no identifier assembly.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TypeVar

from elc.persona.types import ValidatorDecision, ValidatorResult
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ActionId,
    AssistantTurnId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
    RuntimeEpoch,
)
from elc.runtime.delivery_records import (
    CLIENT_RENDER_ACK_COLUMNS,
    EXPOSURE_ESTIMATE_COLUMNS,
    PRE_DELIVERY_GUARD_RESULT_COLUMNS,
    SERVER_DELIVERY_RECORD_COLUMNS,
    VALIDATOR_RESULT_COLUMNS,
    ClientRenderAck,
    ExposureEstimate,
    PreDeliveryGuardResult,
    ServerDeliveryRecord,
    certainty_word_refusal,
    exposure_word_refusal,
    state_word_refusal,
)

__all__ = ["SqliteDeliveryRecordStore", "StaleDeliveryRecordStoreError"]

T = TypeVar("T")


class StaleDeliveryRecordStoreError(StaleEpochError):
    """A delivery-record write was fenced by a newer runtime epoch."""


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _conflict(message: str) -> Err[T]:
    return _err(DomainErrorCode.CONFLICT, message)


def _array_document(values: tuple[str, ...]) -> str:
    """The deterministic JSON array document the ``reason_codes`` columns
    carry — the same call elc/teaching/store.py and elc/planner/ledger_store.py
    make for the same column name (one encoding, not a second spelling)."""

    return json.dumps(list(values), sort_keys=True, separators=(",", ":"))


def _array_from_document(document: object) -> tuple[str, ...]:
    loaded = json.loads(str(document))
    return tuple(str(item) for item in loaded)


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


# ---------------------------------------------------------------------------
# Row decoders (positional order = the port's ``*_COLUMNS``, the literal every
# SELECT here uses)
# ---------------------------------------------------------------------------


def _server_record(row: sqlite3.Row) -> ServerDeliveryRecord:
    return ServerDeliveryRecord(
        action_id=ActionId(str(row[0])),
        assistant_turn_id=AssistantTurnId(str(row[1])),
        state=str(row[2]),
        sent_prefix=str(row[3]),
        last_chunk_seq=int(row[4]),
        started_at=str(row[5]),
        terminal_at=_optional(row[6]),
    )


def _ack_record(row: sqlite3.Row) -> ClientRenderAck:
    return ClientRenderAck(
        action_id=ActionId(str(row[0])),
        assistant_turn_id=AssistantTurnId(str(row[1])),
        rendered_chunk_seq=int(row[2]),
        rendered_text_hash=str(row[3]),
        acked_at=str(row[4]),
        final_rendered=bool(row[5]),
    )


def _estimate_record(row: sqlite3.Row) -> ExposureEstimate:
    return ExposureEstimate(
        action_id=ActionId(str(row[0])),
        certainty=str(row[1]),
        exposure_level=str(row[2]),
        max_possible_exposure=str(row[3]),
        confirmed_exposure=str(row[4]),
        derivation_reason=str(row[5]),
    )


def _validator_record(row: sqlite3.Row) -> ValidatorResult:
    return ValidatorResult(
        validator_result_id=str(row[0]),
        action_id=ActionId(str(row[1])),
        attempt_no=int(row[2]),
        decision=ValidatorDecision(str(row[3])),
        reason_codes=_array_from_document(row[4]),
        validator_version=str(row[5]),
        created_at=_optional(row[6]),
    )


def _guard_record(row: sqlite3.Row) -> PreDeliveryGuardResult:
    return PreDeliveryGuardResult(
        pre_delivery_guard_result_id=str(row[0]),
        action_id=ActionId(str(row[1])),
        decision=str(row[2]),
        reason_codes=_array_from_document(row[3]),
        checked_lineage_version=str(row[4]),
        created_at=str(row[5]),
    )


# ---------------------------------------------------------------------------
# The write rules (judgement 4 / judgement 5 of the port)
# ---------------------------------------------------------------------------


def _same_server_row(
    durable: ServerDeliveryRecord, submitted: ServerDeliveryRecord
) -> bool:
    """Byte-for-byte agreement on every non-key column (the key is the
    lookup). A replay must be the same unit — judgement 5."""

    return (
        durable.assistant_turn_id == submitted.assistant_turn_id
        and durable.state == submitted.state
        and durable.sent_prefix == submitted.sent_prefix
        and durable.last_chunk_seq == submitted.last_chunk_seq
        and durable.started_at == submitted.started_at
        and durable.terminal_at == submitted.terminal_at
    )


def _advance_refusal(
    durable: ServerDeliveryRecord, submitted: ServerDeliveryRecord
) -> DomainError | None:
    """The four invariants a differing submission must satisfy to advance the
    row (judgement 4); the first one it breaks is the refusal."""

    action_id = durable.action_id
    if submitted.assistant_turn_id != durable.assistant_turn_id:
        return DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"server delivery {action_id} belongs to assistant turn"
                f" {durable.assistant_turn_id}; the submission names"
                f" {submitted.assistant_turn_id} — which delivery this is"
                " cannot change"
            ),
        )
    if submitted.started_at != durable.started_at:
        return DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"server delivery {action_id} started at"
                f" {durable.started_at}; the submission says"
                f" {submitted.started_at} — the start instant is content"
            ),
        )
    if durable.terminal_at is not None and submitted.terminal_at != (
        durable.terminal_at
    ):
        return DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"server delivery {action_id} is terminal at"
                f" {durable.terminal_at}; a terminal row is frozen and the"
                " submission would change it"
            ),
        )
    if submitted.last_chunk_seq < durable.last_chunk_seq:
        return DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"server delivery {action_id} is at chunk"
                f" {durable.last_chunk_seq}; the submission moves it back to"
                f" {submitted.last_chunk_seq} — the sequence never decreases"
            ),
        )
    if not submitted.sent_prefix.startswith(durable.sent_prefix):
        return DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"server delivery {action_id} has sent prefix"
                f" {durable.sent_prefix!r}; the submission's"
                f" {submitted.sent_prefix!r} does not extend it — the sent"
                " boundary never shrinks"
            ),
        )
    return None


def _same_ack(durable: ClientRenderAck, submitted: ClientRenderAck) -> bool:
    """Same event: the key is the lookup, the four content columns agree
    (``final_rendered`` compared as the 0/1 the schema holds)."""

    return (
        durable.assistant_turn_id == submitted.assistant_turn_id
        and durable.rendered_text_hash == submitted.rendered_text_hash
        and durable.acked_at == submitted.acked_at
        and int(durable.final_rendered) == int(submitted.final_rendered)
    )


class SqliteDeliveryRecordStore:
    """Durable §22 / §21.1 delivery rows (app.db)."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> RuntimeEpoch:
        return RuntimeEpoch(self._fence.current)

    def _require_current_epoch(self) -> None:
        """Fence inside the write transaction: the adopted epoch must still
        be the newest epoch row in app.db (RUNTIME §24 restart ownership;
        the ``SqlitePlannerRecordStore`` rule)."""

        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleDeliveryRecordStoreError(
                f"delivery-record store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- writes ------------------------------------------------------------

    def record_server_delivery(
        self, record: ServerDeliveryRecord
    ) -> Result[ServerDeliveryRecord]:
        """One action's §22 delivery fact: insert, replay or advance."""

        refusal = state_word_refusal(record.state)
        if refusal is not None:
            return Err(refusal)
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                durable = self._read_server_delivery(record.action_id)
                if durable is None:
                    self._conn.execute(
                        "INSERT INTO server_delivery_record ("
                        " action_id, assistant_turn_id, state, sent_prefix,"
                        " last_chunk_seq, started_at, terminal_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            record.action_id,
                            record.assistant_turn_id,
                            record.state,
                            record.sent_prefix,
                            record.last_chunk_seq,
                            record.started_at,
                            record.terminal_at,
                        ),
                    )
                elif _same_server_row(durable, record):
                    return Ok(durable)
                else:
                    advance = _advance_refusal(durable, record)
                    if advance is not None:
                        return Err(advance)
                    self._conn.execute(
                        "UPDATE server_delivery_record SET"
                        " assistant_turn_id = ?, state = ?, sent_prefix = ?,"
                        " last_chunk_seq = ?, started_at = ?, terminal_at = ?"
                        " WHERE action_id = ?",
                        (
                            record.assistant_turn_id,
                            record.state,
                            record.sent_prefix,
                            record.last_chunk_seq,
                            record.started_at,
                            record.terminal_at,
                            record.action_id,
                        ),
                    )
                written = self._read_server_delivery(record.action_id)
                assert written is not None  # the unit wrote it above
                return Ok(written)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def append_client_render_ack(
        self, ack: ClientRenderAck
    ) -> Result[ClientRenderAck]:
        """One §22 render ACK event: insert, or replay when it is the same
        event (the key is the action and the chunk)."""

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                durable = self._read_ack(
                    ack.action_id, ack.rendered_chunk_seq
                )
                if durable is not None:
                    if _same_ack(durable, ack):
                        return Ok(durable)
                    return _conflict(
                        "client render ack of action"
                        f" {ack.action_id} chunk {ack.rendered_chunk_seq} is"
                        " already durable with different content; an"
                        " appended event is never rewritten"
                    )
                self._conn.execute(
                    "INSERT INTO client_render_ack ("
                    " action_id, assistant_turn_id, rendered_chunk_seq,"
                    " rendered_text_hash, acked_at, final_rendered"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        ack.action_id,
                        ack.assistant_turn_id,
                        ack.rendered_chunk_seq,
                        ack.rendered_text_hash,
                        ack.acked_at,
                        int(ack.final_rendered),
                    ),
                )
                return Ok(ack)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def append_validator_result(
        self, result: ValidatorResult
    ) -> Result[ValidatorResult]:
        """One §21.1 ValidatorResult row.

        ``created_at`` must be set: the instant is content (the port's
        judgement 5) and this store reads no clock — a ``None`` is
        ``VALIDATION_FAILED``, never a store-stamped value.
        """

        if result.created_at is None:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"validator result {result.validator_result_id} carries no"
                " created_at; the instant is content (the store reads no"
                " clock), so a re-entry could not be compared against it",
            )
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                durable = self._read_validator(result.validator_result_id)
                if durable is not None:
                    if durable == result:
                        return Ok(durable)
                    return _conflict(
                        f"validator result {result.validator_result_id} is"
                        " already durable with different content; a validator"
                        " result is never rewritten"
                    )
                self._conn.execute(
                    "INSERT INTO validator_result ("
                    " validator_result_id, action_id, attempt_no, decision,"
                    " reason_codes, validator_version, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        result.validator_result_id,
                        result.action_id,
                        result.attempt_no,
                        result.decision.value,
                        _array_document(result.reason_codes),
                        result.validator_version,
                        result.created_at,
                    ),
                )
                return Ok(result)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def append_pre_delivery_guard_result(
        self, result: PreDeliveryGuardResult
    ) -> Result[PreDeliveryGuardResult]:
        """One §21.1 PreDeliveryGuardResult row."""

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                durable = self._read_guard(result.pre_delivery_guard_result_id)
                if durable is not None:
                    if durable == result:
                        return Ok(durable)
                    return _conflict(
                        "pre-delivery guard result"
                        f" {result.pre_delivery_guard_result_id} is already"
                        " durable with different content; a guard result is"
                        " never rewritten"
                    )
                self._conn.execute(
                    "INSERT INTO pre_delivery_guard_result ("
                    " pre_delivery_guard_result_id, action_id, decision,"
                    " reason_codes, checked_lineage_version, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        result.pre_delivery_guard_result_id,
                        result.action_id,
                        result.decision,
                        _array_document(result.reason_codes),
                        result.checked_lineage_version,
                        result.created_at,
                    ),
                )
                return Ok(result)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def record_initial_exposure_estimate(
        self, estimate: ExposureEstimate
    ) -> Result[ExposureEstimate]:
        """The §6 CP3a initial estimate for one action: insert, or replay when
        it is the same estimate. A differing submission is ``CONFLICT`` — the
        estimate is written once (the port's judgement 7)."""

        for column, word in (
            ("certainty", estimate.certainty),
            ("exposure_level", estimate.exposure_level),
            ("max_possible_exposure", estimate.max_possible_exposure),
            ("confirmed_exposure", estimate.confirmed_exposure),
        ):
            refusal = (
                certainty_word_refusal(word)
                if column == "certainty"
                else exposure_word_refusal(column, word)
            )
            if refusal is not None:
                return Err(refusal)
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                durable = self._read_estimate(estimate.action_id)
                if durable is not None:
                    if durable == estimate:
                        return Ok(durable)
                    return _conflict(
                        f"exposure estimate of action {estimate.action_id} is"
                        " already durable with different content; the initial"
                        " estimate is written once (refinement is a later"
                        " cut's explicit face)"
                    )
                self._conn.execute(
                    "INSERT INTO exposure_estimate ("
                    " action_id, certainty, exposure_level,"
                    " max_possible_exposure, confirmed_exposure,"
                    " derivation_reason"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        estimate.action_id,
                        estimate.certainty,
                        estimate.exposure_level,
                        estimate.max_possible_exposure,
                        estimate.confirmed_exposure,
                        estimate.derivation_reason,
                    ),
                )
                return Ok(estimate)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    # -- in-transaction reads ----------------------------------------------

    def _read_server_delivery(
        self, action_id: ActionId
    ) -> ServerDeliveryRecord | None:
        row = self._conn.execute(
            "SELECT " + ", ".join(SERVER_DELIVERY_RECORD_COLUMNS)
            + " FROM server_delivery_record WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        return None if row is None else _server_record(row)

    def _read_ack(
        self, action_id: ActionId, rendered_chunk_seq: int
    ) -> ClientRenderAck | None:
        row = self._conn.execute(
            "SELECT " + ", ".join(CLIENT_RENDER_ACK_COLUMNS)
            + " FROM client_render_ack"
            " WHERE action_id = ? AND rendered_chunk_seq = ?",
            (action_id, rendered_chunk_seq),
        ).fetchone()
        return None if row is None else _ack_record(row)

    def _read_estimate(self, action_id: ActionId) -> ExposureEstimate | None:
        row = self._conn.execute(
            "SELECT " + ", ".join(EXPOSURE_ESTIMATE_COLUMNS)
            + " FROM exposure_estimate WHERE action_id = ?",
            (action_id,),
        ).fetchone()
        return None if row is None else _estimate_record(row)

    def _read_validator(
        self, validator_result_id: str
    ) -> ValidatorResult | None:
        row = self._conn.execute(
            "SELECT " + ", ".join(VALIDATOR_RESULT_COLUMNS)
            + " FROM validator_result WHERE validator_result_id = ?",
            (validator_result_id,),
        ).fetchone()
        return None if row is None else _validator_record(row)

    def _read_guard(
        self, pre_delivery_guard_result_id: str
    ) -> PreDeliveryGuardResult | None:
        row = self._conn.execute(
            "SELECT " + ", ".join(PRE_DELIVERY_GUARD_RESULT_COLUMNS)
            + " FROM pre_delivery_guard_result"
            " WHERE pre_delivery_guard_result_id = ?",
            (pre_delivery_guard_result_id,),
        ).fetchone()
        return None if row is None else _guard_record(row)

    # -- reads -------------------------------------------------------------

    def get_server_delivery_record(
        self, action_id: ActionId
    ) -> Result[ServerDeliveryRecord | None]:
        return Ok(self._read_server_delivery(action_id))

    def get_exposure_estimate(
        self, action_id: ActionId
    ) -> Result[ExposureEstimate | None]:
        return Ok(self._read_estimate(action_id))

    def list_client_render_acks(
        self, action_id: ActionId
    ) -> Result[tuple[ClientRenderAck, ...]]:
        rows = self._conn.execute(
            "SELECT " + ", ".join(CLIENT_RENDER_ACK_COLUMNS)
            + " FROM client_render_ack WHERE action_id = ?"
            " ORDER BY rendered_chunk_seq",
            (action_id,),
        ).fetchall()
        return Ok(tuple(_ack_record(row) for row in rows))

    def list_validator_results(
        self, action_id: ActionId
    ) -> Result[tuple[ValidatorResult, ...]]:
        rows = self._conn.execute(
            "SELECT " + ", ".join(VALIDATOR_RESULT_COLUMNS)
            + " FROM validator_result WHERE action_id = ?"
            " ORDER BY attempt_no, validator_result_id",
            (action_id,),
        ).fetchall()
        return Ok(tuple(_validator_record(row) for row in rows))

    def list_pre_delivery_guard_results(
        self, action_id: ActionId
    ) -> Result[tuple[PreDeliveryGuardResult, ...]]:
        rows = self._conn.execute(
            "SELECT " + ", ".join(PRE_DELIVERY_GUARD_RESULT_COLUMNS)
            + " FROM pre_delivery_guard_result WHERE action_id = ?"
            " ORDER BY created_at, pre_delivery_guard_result_id",
            (action_id,),
        ).fetchall()
        return Ok(tuple(_guard_record(row) for row in rows))
