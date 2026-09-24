"""The PlanningLedger's durable half — every statement (P8-3).

TASK-OPI-6d40862d-….9 ①②③. migration 0016 lands three tables —
``planning_ledger`` (§14's per-key row), ``coverage_obligation`` (§14's
``coverage_obligations[]``, eleven fields) and ``planning_ledger_event`` (RA
§20's five events, append-first) — and this module is where their SQL lives.
The pure core is **unchanged**: :mod:`elc.planner.ledger` still owns the five
event words, their effects, the obligation's eleven fields, the ladders and the
three declared numbers, and this module derives nothing. It persists what the
core already answered:

- the row's projection is read off ``TargetLedgerRow``'s own derived
  properties (``last_selected_at`` / ``last_presented_at`` /
  ``teaching_exposure_counts`` / ``recent_skips``), so no stored column is a
  second computation of what the log says;
- the event appended is the row's own last log record, so the log's identity
  (word + instant) has one source;
- an obligation's current values are the ones the caller's
  ``apply_ledger_event`` / ``accrue`` returned.

**One short transaction, and what it contains.** :meth:`SqliteLedgerStore.
record_ledger_event` commits one §20 event **and** the current projection it
leaves — the ``planning_ledger`` row, the new ``planning_ledger_event`` row and
the obligations the caller derived — inside one ``short_transaction`` under the
owner-epoch fence (the P6-1 ``schedule_item`` + ``review_event`` unit shape: a
current projection and an append-first log committed together). A failure
anywhere rolls the whole unit back; there is no half-appended event and no
projection that does not include the event the log carries.
:meth:`SqliteLedgerStore.upsert_obligation` is the second write face, and it
exists because the core has a second write path: an obligation **accrues**
without any §20 event (BF-06 §14's rule is about *not* serving), so a
debt that no event produces must be persistable on its own.

**Replay, not re-append.** A re-entry with an ``event_id`` the log already
carries and the same content (key, word, instant) is a **replay**: the durable
event row comes back and nothing is written. The same id with different content
is ``CONFLICT`` — an event is a fact and is never rewritten (docs/DATA_MODEL.md
§1.3; the 0012 ``review_event_id`` precedent). The *projection* is deliberately
not compared on a replay: it is a pure function of the log (the core is
deterministic and clock-free), so an identical appended fact implies an
identical projection — comparing a derived value against a derived value would
be asking a copy whether it agrees with itself. The identity cannot be the
content: the core's log does not collapse a repeat ("two presentations at one
instant are two presentations"), which is why ``event_id`` is a caller-minted
id rather than a content hash.

**The log is read back as the fact.** :meth:`SqliteLedgerStore.get_ledger_row`
builds the core's ``TargetLedgerRow`` out of the event log plus the three
columns that are **not** functions of it (``overexposure_window`` /
``probe_counts`` / ``review_offers`` — the core's own split), then holds the
stored derived columns against the log. A row whose stored copy disagrees with
its log is refused rather than answered: the core's own sentence is "one fact,
one source, so no stored copy can disagree with the log", and a read that
picked one of the two answers would be the disagreement it refuses (the
scheduler store's dirty-row rule, ``VALIDATION_FAILED``).

**Read faces.** By key: the current row (:meth:`get_ledger_row`), its stored
projection (:meth:`get_ledger_projection`) and its event stream
(:meth:`list_ledger_events`); by key: the obligations, **including the
unserved and the paused ones** (:meth:`list_obligations` — "which debts are
waiting" is exactly what a caller must be able to ask without a service filter
having decided for it); and the whole ledger as the core's view
(:meth:`read_ledger`), which is the shape
``elc.planner.types.PlanningRequest.planning_ledger`` takes.

**Two columns §14 names are not materialized** (migration 0016's header states
the argument: DATA_MODEL §26 lists "some PlanningLedger rollups" among the
rebuildable projections and forbids a projection being the only source of
truth). :meth:`read_ledger` therefore answers the core's own defaults for
``coverage_debt_rollups`` (``{}``) and ``recent_target_families`` (``()``), and
the cut that first *reads* a rollup out of the durable ledger lands its home.

**No producer, registered rather than implied.** Nothing in ``src/`` calls this
store yet: the delivery path that *presents* a Moment — p8-4's — is what makes
``teaching_presented`` (and the two lighter presentations) happen, and §20's
"SELECT != exposure" is the reason a selection cannot write this log instead.
The shipped caller count is zero today, which is a fact a test checks rather
than a sentence a reader is asked to trust.

All SQL is a fixed literal with bound parameters — no identifier assembly, and
no statement names ``planning_ledger_event`` with an ``UPDATE`` or a
``DELETE`` (the log is append-only; its removal is the BF-05 walk's).
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Sequence, TypeVar

from elc.planner.ledger import (
    PLANNING_LEDGER_MODEL_VERSION,
    CoverageObligation,
    LedgerEvent,
    LedgerEventRecord,
    LedgerInputError,
    LedgerKeyType,
    LedgerWindow,
    PlanningLedger,
    TargetLedgerRow,
)
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)

__all__ = [
    "LedgerEventRow",
    "LedgerRowProjection",
    "PLANNING_LEDGER_STORE_SOURCES",
    "SqliteLedgerStore",
    "StaleLedgerStoreError",
]

T = TypeVar("T")

#: The three tables this module reads and writes, in the order §14 names their
#: halves (the row, the obligations, the event log). It is a declaration other
#: modules can hold this one to — the migration creates exactly these, the BF-05
#: walk names exactly these, and a cut that adds a fourth ledger table has to
#: move this tuple, that walk and the migration together.
PLANNING_LEDGER_STORE_SOURCES: tuple[str, ...] = (
    "planning_ledger",
    "coverage_obligation",
    "planning_ledger_event",
)


class StaleLedgerStoreError(StaleEpochError):
    """This store's epoch is no longer the newest durable epoch."""


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _constraint_family(exc: sqlite3.IntegrityError) -> str:
    """Which durable rule refused a write, in this module's words.

    sqlite's message is **read**, never re-emitted (the scheduler store's rule:
    a ``DomainError.message`` is this domain's vocabulary).
    """

    text = str(exc)
    for family in ("FOREIGN KEY", "UNIQUE", "CHECK", "NOT NULL"):
        if family in text:
            return family
    return "UNKNOWN"


# -- the durable records -----------------------------------------------------


@dataclass(frozen=True)
class LedgerEventRow:
    """One appended fact: §20's word, its key and its instant.

    ``event_id`` is the durable identity (migration 0016's header: §20 names
    none, and the identity cannot be the content because the core's log does
    not collapse a repeat). ``as_of`` is the core's ``LedgerEventRecord.at``
    under the durable column name.
    """

    event_id: str
    ledger_key: str
    event: LedgerEvent
    as_of: str


@dataclass(frozen=True)
class LedgerRowProjection:
    """§14's stored per-key columns, as stored — the projection, not the fact.

    This is what a reader auditing the durable rows wants: the columns §14
    names, one field each, with no derivation in between. The *fact* is the
    event log, and :meth:`SqliteLedgerStore.get_ledger_row` is where the two are
    held against each other. ``version`` is the model version the writer
    stamped (``elc.planner.ledger.PLANNING_LEDGER_MODEL_VERSION``).
    """

    ledger_key: str
    ledger_key_type: LedgerKeyType
    last_selected_at: str | None
    last_presented_at: str | None
    teaching_exposure_counts: int
    probe_counts: int
    review_offers: int
    recent_skips: int
    overexposure_window: LedgerWindow | None
    version: str


# -- decoding (§14's columns → the core's objects) ---------------------------
#
# The decoders refuse rather than coerce: a column that holds something the
# declared shape cannot describe is answered with ``VALIDATION_FAILED`` naming
# the column and the value, never with a guessed default (the scheduler store's
# ``_DirtyRowError`` contract). The one extra case here is the core's own
# input contract — ``CoverageObligation`` refuses a half-declared pause and a
# debt outside its declared range — so the decoder catches ``LedgerInputError``
# and carries its sentence into the refusal instead of letting a raw exception
# reach a caller.


class _DirtyRowError(Exception):
    """A durable row the §14 column set cannot describe."""

    def __init__(self, column: str, value: object, expected: str) -> None:
        super().__init__(column)
        self.column = column
        self.value = value
        self.expected = expected


def _text(value: object, column: str) -> str:
    if not isinstance(value, str):
        raise _DirtyRowError(column, value, "TEXT")
    return value


def _optional_text(value: object, column: str) -> str | None:
    if value is None:
        return None
    return _text(value, column)


def _integer(value: object, column: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _DirtyRowError(column, value, "INTEGER")
    return value


def _number(value: object, column: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _DirtyRowError(column, value, "REAL")
    return float(value)


def _flag(value: object, column: str) -> bool:
    if value not in (0, 1):
        raise _DirtyRowError(column, value, "0 or 1")
    return bool(value)


def _event_word(value: object) -> LedgerEvent:
    text = _text(value, "event")
    try:
        return LedgerEvent(text)
    except ValueError:
        raise _DirtyRowError("event", value, "one of §20's five words") from None


def _key_type(value: object) -> LedgerKeyType:
    text = _text(value, "ledger_key_type")
    try:
        return LedgerKeyType(text)
    except ValueError:
        raise _DirtyRowError(
            "ledger_key_type", value, "one of §14's two key faces"
        ) from None


def _object_document(values: dict[str, object]) -> str:
    """The one JSON encoding this module writes (elc/teaching/store.py's call).

    ``json.dumps(..., sort_keys=True, separators=(",", ":"))`` — the array
    document's call applied to an object, so the two shapes share one
    deterministic encoding rather than two spellings of "JSON text".
    """

    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def _window_document(window: LedgerWindow | None) -> str | None:
    if window is None:
        return None
    return _object_document({"end": window.end, "start": window.start})


def _window_from_document(document: object, column: str) -> LedgerWindow | None:
    if document is None:
        return None
    text = _text(document, column)
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        raise _DirtyRowError(
            column, text, "a JSON object with start and end"
        ) from None
    if not isinstance(loaded, dict) or set(loaded) != {"start", "end"}:
        raise _DirtyRowError(column, text, "a JSON object with start and end")
    return LedgerWindow(
        start=_text(loaded["start"], f"{column}.start"),
        end=_text(loaded["end"], f"{column}.end"),
    )


def _projection_from_row(row: Sequence[object]) -> LedgerRowProjection:
    return LedgerRowProjection(
        ledger_key=_text(row[0], "ledger_key"),
        ledger_key_type=_key_type(row[1]),
        last_selected_at=_optional_text(row[2], "last_selected_at"),
        last_presented_at=_optional_text(row[3], "last_presented_at"),
        teaching_exposure_counts=_integer(
            row[4], "teaching_exposure_counts"
        ),
        probe_counts=_integer(row[5], "probe_counts"),
        review_offers=_integer(row[6], "review_offers"),
        recent_skips=_integer(row[7], "recent_skips"),
        overexposure_window=_window_from_document(
            row[8], "overexposure_window"
        ),
        version=_text(row[9], "version"),
    )


def _event_from_row(row: Sequence[object]) -> LedgerEventRow:
    return LedgerEventRow(
        event_id=_text(row[0], "event_id"),
        ledger_key=_text(row[1], "ledger_key"),
        event=_event_word(row[2]),
        as_of=_text(row[3], "as_of"),
    )


def _obligation_from_row(row: Sequence[object]) -> CoverageObligation:
    try:
        return CoverageObligation(
            obligation_key=_text(row[0], "obligation_key"),
            scope_type=_text(row[1], "scope_type"),
            target_or_family_id=_text(row[2], "target_or_family_id"),
            goal_id=_optional_text(row[3], "goal_id"),
            window_start=_text(row[4], "window_start"),
            window_end=_text(row[5], "window_end"),
            debt_value=_number(row[6], "debt_value"),
            accrual_paused=_flag(row[7], "accrual_paused"),
            pause_reason=_optional_text(row[8], "pause_reason"),
            last_served_at=_optional_text(row[9], "last_served_at"),
            last_engaged_at=_optional_text(row[10], "last_engaged_at"),
        )
    except LedgerInputError as exc:
        raise _DirtyRowError(
            "coverage_obligation", str(row[0]), f"a valid obligation ({exc})"
        ) from None


def _same_event(
    durable: LedgerEventRow, *, event: LedgerEvent, key: str, as_of: str
) -> bool:
    return (
        durable.event is event
        and durable.ledger_key == key
        and durable.as_of == as_of
    )


# -- the statements (fixed literals, bound parameters) -----------------------
#
# One literal per shape, as module constants rather than inline strings, so the
# set of tables this module touches is readable in one place (a test holds it
# against ``PLANNING_LEDGER_STORE_SOURCES`` and migration 0016's tables).

_SELECT_PROJECTION = (
    "SELECT ledger_key, ledger_key_type, last_selected_at,"
    " last_presented_at, teaching_exposure_counts, probe_counts,"
    " review_offers, recent_skips, overexposure_window, version"
    " FROM planning_ledger WHERE ledger_key = ?"
)

_SELECT_PROJECTIONS = (
    "SELECT ledger_key, ledger_key_type, last_selected_at,"
    " last_presented_at, teaching_exposure_counts, probe_counts,"
    " review_offers, recent_skips, overexposure_window, version"
    " FROM planning_ledger ORDER BY ledger_key"
)

_SELECT_EVENTS = (
    "SELECT event_id, ledger_key, event, as_of FROM planning_ledger_event"
    " WHERE ledger_key = ? ORDER BY as_of, event_id"
)

_SELECT_EVENT = (
    "SELECT event_id, ledger_key, event, as_of FROM planning_ledger_event"
    " WHERE event_id = ?"
)

_SELECT_OBLIGATION = (
    "SELECT obligation_key, scope_type, target_or_family_id, goal_id,"
    " window_start, window_end, debt_value, accrual_paused, pause_reason,"
    " last_served_at, last_engaged_at FROM coverage_obligation"
    " WHERE obligation_key = ?"
)

_SELECT_OBLIGATIONS = (
    "SELECT obligation_key, scope_type, target_or_family_id, goal_id,"
    " window_start, window_end, debt_value, accrual_paused, pause_reason,"
    " last_served_at, last_engaged_at FROM coverage_obligation"
    " ORDER BY obligation_key"
)

_SELECT_OBLIGATIONS_FOR_KEY = (
    "SELECT obligation_key, scope_type, target_or_family_id, goal_id,"
    " window_start, window_end, debt_value, accrual_paused, pause_reason,"
    " last_served_at, last_engaged_at FROM coverage_obligation"
    " WHERE target_or_family_id = ? ORDER BY obligation_key"
)

_INSERT_PROJECTION = (
    "INSERT INTO planning_ledger (ledger_key, ledger_key_type,"
    " last_selected_at, last_presented_at, teaching_exposure_counts,"
    " probe_counts, review_offers, recent_skips, overexposure_window, version)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(ledger_key) DO UPDATE SET"
    " ledger_key_type = excluded.ledger_key_type,"
    " last_selected_at = excluded.last_selected_at,"
    " last_presented_at = excluded.last_presented_at,"
    " teaching_exposure_counts = excluded.teaching_exposure_counts,"
    " probe_counts = excluded.probe_counts,"
    " review_offers = excluded.review_offers,"
    " recent_skips = excluded.recent_skips,"
    " overexposure_window = excluded.overexposure_window,"
    " version = excluded.version"
)

_INSERT_EVENT = (
    "INSERT INTO planning_ledger_event (event_id, ledger_key, event, as_of)"
    " VALUES (?, ?, ?, ?)"
)

_INSERT_OBLIGATION = (
    "INSERT INTO coverage_obligation (obligation_key, scope_type,"
    " target_or_family_id, goal_id, window_start, window_end, debt_value,"
    " accrual_paused, pause_reason, last_served_at, last_engaged_at)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(obligation_key) DO UPDATE SET"
    " scope_type = excluded.scope_type,"
    " target_or_family_id = excluded.target_or_family_id,"
    " goal_id = excluded.goal_id,"
    " window_start = excluded.window_start,"
    " window_end = excluded.window_end,"
    " debt_value = excluded.debt_value,"
    " accrual_paused = excluded.accrual_paused,"
    " pause_reason = excluded.pause_reason,"
    " last_served_at = excluded.last_served_at,"
    " last_engaged_at = excluded.last_engaged_at"
)


class SqliteLedgerStore:
    """The PlanningLedger's durable rows, one short transaction per unit.

    Fencing: every write checks the store epoch against the newest durable
    epoch and raises :class:`StaleLedgerStoreError` when it is stale — the
    scheduler / planner store contract (a fenced write is not a ``Result``
    error; it is the process's ownership boundary, RA §24).
    """

    def __init__(
        self, conn: sqlite3.Connection, fence: RuntimeEpochFence
    ) -> None:
        self._conn = conn
        self._fence = fence

    def _require_current_epoch(self) -> None:
        row = self._conn.execute(
            "SELECT MAX(epoch) FROM runtime_epoch"
        ).fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or self._fence.is_stale(newest):
            raise StaleLedgerStoreError(
                f"ledger store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- writes ------------------------------------------------------------

    def record_ledger_event(
        self,
        *,
        event_id: str,
        event: LedgerEvent,
        row: TargetLedgerRow,
        key_type: LedgerKeyType = LedgerKeyType.TARGET,
        obligations: Sequence[CoverageObligation] = (),
    ) -> Result[LedgerEventRow]:
        """One §20 event appended, and the current projection it leaves.

        The unit is "this event **and** the row it leaves", so ``row`` is the
        core's row *after* :meth:`TargetLedgerRow.record` — the log's identity
        (word and instant) comes from its last record, and the projection is
        read off its own derived properties. A ``row`` whose log does not end
        with ``event`` is refused (``VALIDATION_FAILED``) rather than written:
        the projection and the append would otherwise describe two different
        instants, which is the disagreement this store exists to not create.

        ``obligations`` are the ones the caller's ``apply_ledger_event`` (and
        any ``accrue``) produced for this event; they are upserted in the same
        transaction (the obligation is current state — the log is the history).
        An obligation that no event produces has its own face:
        :meth:`upsert_obligation`.

        Replay: an ``event_id`` the log already carries with the same content
        returns the durable row and writes nothing; a different content under
        the same id is ``CONFLICT`` (module docstring).

        **The row handed in must be this key's durable log plus this event.**
        A `log` that carries less (or other) history than the durable one
        cannot be the projection that log leaves, so it is refused with
        ``CONFLICT`` — the unit is "append to the log you read", and a base
        that has moved under the caller is a lost update rather than a licence
        to re-base. This is what keeps the store's own read face true: a
        projection that disagrees with its log would be refused by
        :meth:`get_ledger_row` forever, so this face never creates one.
        """

        if not row.events or row.events[-1].event is not event:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"ledger event {event_id} was offered with a row whose log"
                f" does not end with it (last:"
                f" {row.events[-1].event.value if row.events else 'no event'})"
                " — the unit is one event *and* the projection it leaves"
                " (docs/RUNTIME_ARCHITECTURE.md §20)",
            )
        as_of = row.events[-1].at
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                durable = self._event_row(event_id)
                if isinstance(durable, Err):
                    return durable
                if durable.value is not None:
                    if _same_event(
                        durable.value,
                        event=event,
                        key=row.target_key,
                        as_of=as_of,
                    ):
                        return Ok(durable.value)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"ledger event {event_id} already exists with different"
                        " content; an event is a fact and is never rewritten —"
                        " append a new event_id (docs/DATA_MODEL.md §1.3)",
                    )
                durable_log = self.list_ledger_events(row.target_key)
                if isinstance(durable_log, Err):
                    return durable_log
                # A multiset, not a sequence: the durable read orders by
                # ``(as_of, event_id)`` while a row's log is in append order,
                # and both are legal (an event may be appended out of instant
                # order). What must match is the *content* — including a
                # deliberate repeat, two identical events being two events.
                base = Counter(
                    (record.event, record.as_of)
                    for record in durable_log.value
                )
                offered = Counter(
                    (record.event, record.at) for record in row.events[:-1]
                )
                if base != offered:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"ledger event {event_id} was offered with a base log"
                        f" of {sum(offered.values())} event(s) while"
                        f" {row.target_key!r} carries {sum(base.values())};"
                        " the row must be this key's durable log plus the event"
                        " being appended — re-read the row and retry"
                        " (docs/DATA_MODEL.md §1.3)",
                    )
                self._write_projection(row, key_type=key_type)
                self._conn.execute(
                    _INSERT_EVENT,
                    (event_id, row.target_key, event.value, as_of),
                )
                for obligation in obligations:
                    self._write_obligation(obligation)
                return Ok(
                    LedgerEventRow(
                        event_id=event_id,
                        ledger_key=row.target_key,
                        event=event,
                        as_of=as_of,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(
                DomainErrorCode.CONFLICT,
                f"ledger event {event_id} was refused by a durable"
                f" {_constraint_family(exc)} rule; nothing was written"
                " (docs/DATA_MODEL.md §14 / RUNTIME_ARCHITECTURE.md §20)",
            )

    def upsert_obligation(
        self, obligation: CoverageObligation
    ) -> Result[CoverageObligation]:
        """One obligation's current values, as the caller's core call left them.

        A debt is current state (the §20 log is the history), so this is an
        upsert by ``obligation_key``: the newest values replace the row's. The
        object's own constructor has already refused a half-declared pause and
        a debt outside the declared range, and the schema's pause agreement
        holds the same invariant durably — a value that reaches this face is one
        the core accepted.
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                self._write_obligation(obligation)
                return Ok(obligation)
        except sqlite3.IntegrityError as exc:
            return _err(
                DomainErrorCode.CONFLICT,
                f"obligation {obligation.obligation_key} was refused by a"
                f" durable {_constraint_family(exc)} rule; nothing was written"
                " (docs/DATA_MODEL.md §14)",
            )

    # -- reads -------------------------------------------------------------

    def get_ledger_projection(
        self, ledger_key: str
    ) -> Result[LedgerRowProjection | None]:
        """One row's stored §14 columns (``None`` = never written)."""

        rows = self._conn.execute(
            _SELECT_PROJECTION, (ledger_key,)
        ).fetchall()
        if not rows:
            return Ok(None)
        try:
            return Ok(_projection_from_row(rows[0]))
        except _DirtyRowError as exc:
            return self._dirty("planning_ledger", ledger_key, exc)

    def get_ledger_row(
        self, ledger_key: str
    ) -> Result[TargetLedgerRow | None]:
        """One row as the core's object: its log, and the three columns that
        are not functions of the log.

        The stored derived columns are **held against the log** on the way out
        (module docstring): a projection that disagrees with the fact it
        projects is refused, not answered. The returned row's derived
        properties are the log's, always.
        """

        projection = self.get_ledger_projection(ledger_key)
        if isinstance(projection, Err):
            return projection
        if projection.value is None:
            return Ok(None)
        events = self.list_ledger_events(ledger_key)
        if isinstance(events, Err):
            return events
        built = TargetLedgerRow(
            target_key=projection.value.ledger_key,
            events=tuple(
                LedgerEventRecord(event=row.event, at=row.as_of)
                for row in events.value
            ),
            overexposure_window=projection.value.overexposure_window,
            probe_counts=projection.value.probe_counts,
            review_offers=projection.value.review_offers,
        )
        for column, stored, derived in (
            (
                "last_selected_at",
                projection.value.last_selected_at,
                built.last_selected_at,
            ),
            (
                "last_presented_at",
                projection.value.last_presented_at,
                built.last_presented_at,
            ),
            (
                "teaching_exposure_counts",
                projection.value.teaching_exposure_counts,
                built.teaching_exposure_counts,
            ),
            ("recent_skips", projection.value.recent_skips, built.recent_skips),
        ):
            if stored != derived:
                return _err(
                    DomainErrorCode.VALIDATION_FAILED,
                    f"planning_ledger {ledger_key!r} column {column} holds"
                    f" {stored!r} while its event log says {derived!r}; the"
                    " projection is a function of the log and this read does"
                    " not choose between the two answers"
                    " (docs/DATA_MODEL.md §14)",
                )
        return Ok(built)

    def list_ledger_events(
        self, ledger_key: str
    ) -> Result[tuple[LedgerEventRow, ...]]:
        """One key's event stream, in the deterministic order
        ``(as_of, event_id)`` — append-first, and several events for one key
        are the history."""

        rows = self._conn.execute(_SELECT_EVENTS, (ledger_key,)).fetchall()
        try:
            return Ok(tuple(_event_from_row(row) for row in rows))
        except _DirtyRowError as exc:
            return self._dirty("planning_ledger_event", ledger_key, exc)

    def get_obligation(
        self, obligation_key: str
    ) -> Result[CoverageObligation | None]:
        """One obligation by its own key (``None`` = never written)."""

        rows = self._conn.execute(
            _SELECT_OBLIGATION, (obligation_key,)
        ).fetchall()
        if not rows:
            return Ok(None)
        try:
            return Ok(_obligation_from_row(rows[0]))
        except _DirtyRowError as exc:
            return self._dirty("coverage_obligation", obligation_key, exc)

    def list_obligations(
        self, *, target_or_family_id: str | None = None
    ) -> Result[tuple[CoverageObligation, ...]]:
        """The obligations, **including the unserved and the paused ones**.

        No service filter is applied and none may be: the core's service ladder
        and ``overexposure_of`` are the readings, and a read face that returned
        only "starved" obligations would have decided the ladder for its
        caller. ``target_or_family_id`` narrows to the key as **spelled** — the
        core's own match (its ``obligations_for``), so a family- or goal-scoped
        row whose id spells this key is included here exactly as the core
        includes it; the TARGET-scoped read is the caller's filter (the core's
        ``target_scoped_obligations_for``), not this store's.
        """

        if target_or_family_id is None:
            rows = self._conn.execute(_SELECT_OBLIGATIONS).fetchall()
        else:
            rows = self._conn.execute(
                _SELECT_OBLIGATIONS_FOR_KEY, (target_or_family_id,)
            ).fetchall()
        try:
            return Ok(tuple(_obligation_from_row(row) for row in rows))
        except _DirtyRowError as exc:
            return self._dirty("coverage_obligation", None, exc)

    def read_ledger(self) -> Result[PlanningLedger]:
        """The whole durable ledger, as the core's own view.

        ``rows`` is rebuilt through :meth:`get_ledger_row` (so every row is
        held against its log on the way in), ``obligations`` is the durable
        list, and ``version`` is
        ``elc.planner.ledger.PLANNING_LEDGER_MODEL_VERSION`` — the constant the
        writer stamps every row with, so there is one source for the number.

        ``coverage_debt_rollups`` / ``recent_target_families`` are the core's
        defaults: two columns §14 names are deliberately **not materialized**
        (migration 0016's header, DATA_MODEL §26), and answering the core's
        empty values is the honest reading of "nothing recorded them" — a
        computed rollup here would be a second implementation of a projection
        the document puts on the rebuildable side.
        """

        stored_rows = self._conn.execute(_SELECT_PROJECTIONS).fetchall()
        built: dict[str, TargetLedgerRow] = {}
        for stored in stored_rows:
            try:
                key = _text(stored[0], "ledger_key")
            except _DirtyRowError as exc:
                return self._dirty("planning_ledger", None, exc)
            row = self.get_ledger_row(key)
            if isinstance(row, Err):
                return row
            if row.value is not None:
                built[key] = row.value
        obligations = self.list_obligations()
        if isinstance(obligations, Err):
            return obligations
        return Ok(
            PlanningLedger(
                rows=built,
                obligations=obligations.value,
                version=PLANNING_LEDGER_MODEL_VERSION,
            )
        )

    # -- the statements, and the refusals ----------------------------------

    def _write_projection(
        self, row: TargetLedgerRow, *, key_type: LedgerKeyType
    ) -> None:
        self._conn.execute(
            _INSERT_PROJECTION,
            (
                row.target_key,
                key_type.value,
                row.last_selected_at,
                row.last_presented_at,
                row.teaching_exposure_counts,
                row.probe_counts,
                row.review_offers,
                row.recent_skips,
                _window_document(row.overexposure_window),
                PLANNING_LEDGER_MODEL_VERSION,
            ),
        )

    def _write_obligation(self, obligation: CoverageObligation) -> None:
        self._conn.execute(
            _INSERT_OBLIGATION,
            (
                obligation.obligation_key,
                obligation.scope_type,
                obligation.target_or_family_id,
                obligation.goal_id,
                obligation.window_start,
                obligation.window_end,
                obligation.debt_value,
                1 if obligation.accrual_paused else 0,
                obligation.pause_reason,
                obligation.last_served_at,
                obligation.last_engaged_at,
            ),
        )

    def _event_row(self, event_id: str) -> Result[LedgerEventRow | None]:
        rows = self._conn.execute(_SELECT_EVENT, (event_id,)).fetchall()
        if not rows:
            return Ok(None)
        try:
            return Ok(_event_from_row(rows[0]))
        except _DirtyRowError as exc:
            return self._dirty("planning_ledger_event", event_id, exc)

    def _dirty(
        self, table: str, ident: object, exc: _DirtyRowError
    ) -> Err[T]:
        return _err(
            DomainErrorCode.VALIDATION_FAILED,
            f"{table} {ident!r} column {exc.column} holds {exc.value!r}, which"
            f" is not {exc.expected}; this read does not coerce a row the §14"
            " column set cannot describe (docs/DATA_MODEL.md §14)",
        )
