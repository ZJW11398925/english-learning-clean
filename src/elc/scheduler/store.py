"""SQLite durable store for the Scheduler domain (Phase 6 P6-1).

The bounded context owns review truth (docs/DOMAIN_MODEL.md §9:
review_state / review_urgency / next_review_window / spacing_stage, plus the
history of review events), so its durable executor lives in the domain
package — the conversation / learning / teaching / relationship / user_config
store precedent. The authority face is :mod:`elc.scheduler.controller`; every
byte that reaches the disk is here, in the two tables migration 0012 creates
(``schedule_item`` / ``review_event``, docs/DATA_MODEL.md §5.2).

**The ScheduleItem discipline (a versioned current projection).** One row per
``(target_type, target_id, evidence_modality)`` — the modality key, which is
what "current schedule" means — and its ``version`` is a stamp in the §1.4
sense:

- **idempotent replay** — the same ``schedule_item_id`` with the same
  ``version`` *and* the same content returns the durable row and writes
  nothing (the crash-retry face);
- **a moved version** — a different ``version`` replaces the content and
  stamps a fresh ``updated_at`` from this store's own clock;
- **a stamped version that would be rewritten** — the same version with
  *different* content is a ``CONFLICT``: a version is a version stamp, not
  decoration (docs/DATA_MODEL.md §1.4), and §5.2 pins no ordering for it, so
  this store compares versions for **equality, never for order**;
- **the modality key is unique** — a write whose
  ``(target_type, target_id, evidence_modality)`` is already held by a
  *different* ``schedule_item_id`` is a ``CONFLICT``: the key is the
  definition of the current projection, so two rows under one key would be
  two answers to one question.

**The ReviewEvent discipline (append-first).** §5.2 gives a review event no
version column, and §1.3 asks for facts to be appended rather than rewritten,
so:

- the identity is ``review_event_id``; the same id with the same content is
  an idempotent replay (returns the durable row, writes nothing);
- **an undeclared ``created_at`` is a wildcard on replay** — the caller that
  said nothing about when the event happened cannot disagree with the durable
  row's store-stamped time, so a retry of the same silent content replays
  (the ScheduleItem/``updated_at`` symmetry: a store-stamped column never
  answers a content question). A **declared** time is content and must match
  the durable value verbatim; a different declared time is a different fact
  and is refused;
- the same id with *different* content is a ``CONFLICT`` — **not** an update.
  There is no stamp a caller could move to declare "this is the same event,
  corrected", so rewriting the row in place would be the silent content change
  under an unchanged identity the rest of this store refuses, and a durable
  fact that nothing could version. A correction is a new event (a new
  ``review_event_id``), which is also what §5.2's missing unique index on
  ``schedule_item_id`` invites: several events for one row over time are the
  history.

**One error vocabulary per call.** Every refusal a caller can receive is a
``DomainError`` in this module's own words: an unknown parent row is
``NOT_FOUND`` (checked up front, one probe per foreign key the event names),
a stamped/deduplicated refusal is ``CONFLICT``. The database's own message
text is never handed back — a ``CHECK``/``UNIQUE`` refusal is classified and
reported as one of those families, so nothing a caller reads is quotable
sqlite phrasing.

Fencing: every write checks the store epoch against the newest durable epoch
before anything is written (the teaching / relationship / user_config store
precedent; a stale store is a programming error and raises).

Keying convention (Local V1, declared rather than assumed): §5.2 pins **no
owner/user column** for either object, so this store keys a schedule row by
its own content key (the ``UNIQUE`` migration 0012 lands) and reads it by that
same key — ``get_schedule_item(target_type, target_id, evidence_modality)``.
Adding a user column would exceed the canonical column set (§5.2's twelve
columns are the set), so the linking rule lives here, in one place, and the
controller names it too. ``review_event`` needs no such convention: §5.2 gives
it ``schedule_item_id`` and it is read by that FK.

What this module deliberately does **not** do: it computes no due/overdue
decision, fills no window, advances no spacing stage, and gives no meaning to
``review_urgency`` (carried verbatim, ``None`` = not configured) or to
``source_learning_watermark`` (carried verbatim, opaque). Those readings —
DOMAIN_MODEL §9's due decision, §10's ScheduleView, and the spacing ladder —
are :mod:`elc.scheduler.spacing`'s (the pure policy) and
:mod:`elc.scheduler.controller`'s (the composition), which read the rows this
store holds: it stores what it is handed and returns what it stored, so the
decision has exactly one home and the durable layer has none. It also
declares no vocabulary for ``event_type`` (§5.2 pins none; see
:class:`elc.scheduler.types.ReviewEvent`).

All SQL is a fixed literal with bound parameters — no identifier assembly, no
runtime value in any statement text.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Mapping, TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    EvidenceGroupId,
    EvidenceModality,
    MomentId,
    Ok,
    Result,
    ScheduleVersion,
    TargetId,
    TurnId,
)
from elc.scheduler.types import (
    ReviewEvent,
    ReviewState,
    ScheduleItem,
    SpacingStage,
)

__all__ = ["StaleSchedulerStoreError", "SqliteSchedulerStore"]

T = TypeVar("T")

#: The two §5.2 tables this module is the only writer of (migration 0012).
SCHEDULE_ITEM_TABLE = "schedule_item"
REVIEW_EVENT_TABLE = "review_event"

#: The four foreign keys §5.2's ReviewEvent carries, each with the **fixed**
#: existence probe this store runs before the insert: one literal statement
#: per key, selected by field name — never assembled, so no identifier ever
#: reaches any statement text (the repo-wide SQL discipline). The probes are
#: what turns "sqlite refused to insert" into this domain's ``NOT_FOUND``.
_FOREIGN_KEY_PROBES: Mapping[str, str] = {
    "schedule_item_id": (
        "SELECT 1 FROM schedule_item WHERE schedule_item_id = ?"
    ),
    "teaching_moment_id": (
        "SELECT 1 FROM teaching_moment WHERE moment_id = ?"
    ),
    "source_turn_id": "SELECT 1 FROM turn_record WHERE turn_id = ?",
    "evidence_group_id": (
        "SELECT 1 FROM evidence_group WHERE evidence_group_id = ?"
    ),
}

#: The durable constraint families a caller can hit once the foreign keys are
#: pre-checked, in the order they are looked for in sqlite's text. The names
#: are this module's (they are what the refusal means), not the database's.
_CONSTRAINT_FAMILIES = ("FOREIGN KEY", "UNIQUE", "CHECK", "NOT NULL")


class StaleSchedulerStoreError(StaleEpochError):
    """This store's epoch is no longer the newest durable epoch."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _constraint_family(exc: sqlite3.IntegrityError) -> str:
    """Which durable rule refused the write, in this module's words.

    sqlite's message is **read**, never re-emitted: a ``DomainError.message``
    is this domain's vocabulary, so what a caller gets is the family the
    caller can act on. Once the foreign keys are pre-checked, a refusal here
    is a ``CHECK`` or a ``UNIQUE`` rule (§5.2's vocabularies, or an id taken
    between the probe and the insert); ``FOREIGN KEY`` stays in the list
    because that race — a parent row removed after the probe — is the one way
    it can still happen.
    """

    text = str(exc)
    for family in _CONSTRAINT_FAMILIES:
        if family in text:
            return family
    return "UNKNOWN"


def _item_columns(item: ScheduleItem) -> tuple[object, ...]:
    """One ScheduleItem as its durable column values, in migration 0012's
    order (the store's single serialization point)."""

    return (
        item.schedule_item_id,
        item.target_type,
        str(item.target_id),
        item.evidence_modality.value,
        item.review_state.value,
        None if item.review_urgency is None else float(item.review_urgency),
        item.next_review_window_start,
        item.next_review_window_end,
        None if item.spacing_stage is None else item.spacing_stage.value,
        item.source_learning_watermark,
        str(item.version),
        item.updated_at,
    )


def _event_columns(event: ReviewEvent) -> tuple[object, ...]:
    """One ReviewEvent as its durable column values, in 0012's order."""

    return (
        event.review_event_id,
        event.schedule_item_id,
        None
        if event.teaching_moment_id is None
        else str(event.teaching_moment_id),
        None if event.source_turn_id is None else str(event.source_turn_id),
        event.event_type,
        1 if event.engaged else 0,
        None
        if event.evidence_group_id is None
        else str(event.evidence_group_id),
        event.created_at,
    )


def _item_from_row(row: sqlite3.Row) -> ScheduleItem:
    """One ``schedule_item`` row (0012's column order) decoded.

    The row type is ``sqlite3.Row`` — the conversation store's decoding
    convention: the column values are the database's, and this is the single
    point where a §5.2 row becomes an object.
    """

    return ScheduleItem(
        schedule_item_id=str(row[0]),
        target_type=str(row[1]),
        target_id=TargetId(str(row[2])),
        evidence_modality=EvidenceModality(str(row[3])),
        review_state=ReviewState(str(row[4])),
        review_urgency=None if row[5] is None else float(row[5]),
        next_review_window_start=(
            None if row[6] is None else str(row[6])
        ),
        next_review_window_end=None if row[7] is None else str(row[7]),
        spacing_stage=(
            None if row[8] is None else SpacingStage(str(row[8]))
        ),
        source_learning_watermark=str(row[9]),
        version=ScheduleVersion(str(row[10])),
        updated_at=str(row[11]),
    )


def _event_from_row(row: sqlite3.Row) -> ReviewEvent:
    """One ``review_event`` row (0012's column order) decoded."""

    return ReviewEvent(
        review_event_id=str(row[0]),
        schedule_item_id=str(row[1]),
        teaching_moment_id=(
            None if row[2] is None else MomentId(str(row[2]))
        ),
        source_turn_id=None if row[3] is None else TurnId(str(row[3])),
        event_type=str(row[4]),
        engaged=bool(int(row[5])),
        evidence_group_id=(
            None if row[6] is None else EvidenceGroupId(str(row[6]))
        ),
        created_at=str(row[7]),
    )


class SqliteSchedulerStore:
    """Durable ``schedule_item`` / ``review_event`` rows (docs/DATA_MODEL.md
    §5.2; migration 0012)."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleSchedulerStoreError(
                f"scheduler store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- the write units ---------------------------------------------------

    def upsert_schedule_item(self, item: ScheduleItem) -> Result[ScheduleItem]:
        """One durable schedule row; the ``updated_at`` is the store's.

        ``item.updated_at`` is ignored (the durable clock is this module's,
        the teaching / relationship / user_config precedent) and the value
        that comes back is the **durable** state — stamped, and identical to
        what a later read returns.

        The four rules the module docstring states are what this method
        applies, in this order: a replay of the same id+version+content
        (zero writes), a refusal of the same id+version with different
        content, a refusal of a modality key held by another row, and
        otherwise an insert or a replace under a moved version. Nothing here
        interprets a column: ``review_urgency`` / the two window columns /
        ``spacing_stage`` / ``source_learning_watermark`` travel verbatim.
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._item_row(item.schedule_item_id)
                if (
                    existing is not None
                    and existing.version == item.version
                ):
                    if _same_item(existing, item):
                        return Ok(existing)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"schedule item {item.schedule_item_id} already"
                        f" carries version {item.version} with different"
                        " content; move the version to change the row"
                        " (docs/DATA_MODEL.md §1.4)",
                    )
                holder = self._item_row_for_key(
                    item.target_type,
                    item.target_id,
                    item.evidence_modality,
                )
                if (
                    holder is not None
                    and holder.schedule_item_id != item.schedule_item_id
                ):
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"schedule key ({item.target_type}, {item.target_id},"
                        f" {item.evidence_modality.value}) is already held by"
                        f" schedule item {holder.schedule_item_id}; one"
                        " current schedule row per target and modality"
                        " (docs/DATA_MODEL.md §5.2)",
                    )
                now = _now()
                if existing is None:
                    self._insert_item(item, now=now)
                else:
                    self._replace_item(item, now=now)
                return Ok(
                    ScheduleItem(
                        schedule_item_id=item.schedule_item_id,
                        target_type=item.target_type,
                        target_id=item.target_id,
                        evidence_modality=item.evidence_modality,
                        review_state=item.review_state,
                        review_urgency=item.review_urgency,
                        next_review_window_start=item.next_review_window_start,
                        next_review_window_end=item.next_review_window_end,
                        spacing_stage=item.spacing_stage,
                        source_learning_watermark=(
                            item.source_learning_watermark
                        ),
                        version=item.version,
                        updated_at=now,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(
                DomainErrorCode.CONFLICT,
                f"schedule item {item.schedule_item_id} was refused by a"
                f" durable {_constraint_family(exc)} rule; nothing was written"
                " (docs/DATA_MODEL.md §5.2)",
            )

    def record_review_event(self, event: ReviewEvent) -> Result[ReviewEvent]:
        """One durable review event; append-first (§1.3, module docstring).

        ``created_at`` follows the 0007 ``teaching_moment`` precedent: the
        caller's timestamp is used **verbatim** when it declares one, and this
        store's clock fills it otherwise — the store never overrides a
        declared time, and never invents one a caller gave.

        **Replay and the undeclared time.** The idempotent-replay question is
        asked first (the crash-retry face), and it treats an undeclared
        ``created_at`` (``""``) as a **wildcard**: a caller that declared no
        time cannot disagree with the store-stamped one the durable row
        carries, so retrying the same silent content replays instead of
        failing (the ScheduleItem/``updated_at`` symmetry — a store-stamped
        column never answers a content question). A **declared** time is
        content: it must equal the durable value verbatim to replay, and a
        different declared time is a different fact (``CONFLICT``), never
        silently restamped.

        **The four foreign keys are pre-checked**, not left to the insert:
        ``schedule_item_id`` and each non-``None`` ``teaching_moment_id`` /
        ``source_turn_id`` / ``evidence_group_id`` gets one fixed existence
        probe, and a missing parent row comes back as ``NOT_FOUND`` — a
        caller never sees sqlite's own text (module docstring: one error
        vocabulary per call). What remains for the ``IntegrityError`` catch is
        a ``CHECK``/``UNIQUE`` refusal, reported as ``CONFLICT`` with the
        family named and no database phrasing. Nothing else is related: §5.2
        pins no constraint tying the event's own identifiers to the schedule
        row's key, so none is enforced (types module docstring).
        """

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._event_row(event.review_event_id)
                if existing is not None:
                    if _same_event(existing, event):
                        return Ok(existing)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"review event {event.review_event_id} already exists"
                        " with different content; a review event is a fact and"
                        " is never rewritten — append a new review_event_id"
                        " (docs/DATA_MODEL.md §1.3)",
                    )
                missing = self._missing_parent(event)
                if missing is not None:
                    return missing
                created_at = event.created_at or _now()
                self._conn.execute(
                    "INSERT INTO review_event ("
                    " review_event_id, schedule_item_id, teaching_moment_id,"
                    " source_turn_id, event_type, engaged, evidence_group_id,"
                    " created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        event.review_event_id,
                        event.schedule_item_id,
                        None
                        if event.teaching_moment_id is None
                        else str(event.teaching_moment_id),
                        None
                        if event.source_turn_id is None
                        else str(event.source_turn_id),
                        event.event_type,
                        1 if event.engaged else 0,
                        None
                        if event.evidence_group_id is None
                        else str(event.evidence_group_id),
                        created_at,
                    ),
                )
                return Ok(
                    ReviewEvent(
                        review_event_id=event.review_event_id,
                        schedule_item_id=event.schedule_item_id,
                        teaching_moment_id=event.teaching_moment_id,
                        source_turn_id=event.source_turn_id,
                        event_type=event.event_type,
                        engaged=event.engaged,
                        evidence_group_id=event.evidence_group_id,
                        created_at=created_at,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(
                DomainErrorCode.CONFLICT,
                f"review event {event.review_event_id} was refused by a"
                f" durable {_constraint_family(exc)} rule; nothing was written"
                " (docs/DATA_MODEL.md §5.2)",
            )

    def _missing_parent(self, event: ReviewEvent) -> Err[ReviewEvent] | None:
        """The first foreign key of ``event`` that names no existing row.

        One fixed probe per key (``_FOREIGN_KEY_PROBES``), ``None`` skipped —
        a column §5.2 spells with ``?`` and the caller left empty is not a
        reference at all. The check is what makes the refusal this domain's
        ``NOT_FOUND`` rather than the insert's integrity error; it runs after
        the idempotent-replay question, so a retry that already succeeded
        still answers with the durable row.
        """

        for field in (
            "schedule_item_id",
            "teaching_moment_id",
            "source_turn_id",
            "evidence_group_id",
        ):
            value = getattr(event, field)
            if value is None:
                continue
            probe = self._conn.execute(
                _FOREIGN_KEY_PROBES[field], (str(value),)
            ).fetchone()
            if probe is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"review event {event.review_event_id} names {field}"
                    f" {value}, which does not exist"
                    " (docs/DATA_MODEL.md §5.2 ReviewEvent)",
                )
        return None

    # -- reads -------------------------------------------------------------

    def get_schedule_item(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> Result[ScheduleItem | None]:
        """The current row for one modality key (``None`` = never written).

        The read is by the §5.2 key itself rather than by
        ``schedule_item_id``: the key is what a caller has (a target and its
        evidence modality), and this is also the lookup a deletion by target
        starts from.
        """

        return Ok(
            self._item_row_for_key(target_type, target_id, evidence_modality)
        )

    def list_review_events(
        self, schedule_item_id: str
    ) -> Result[tuple[ReviewEvent, ...]]:
        """Every event of one schedule row, in durable order.

        Ordered by ``(created_at, review_event_id)`` — the deterministic order
        this slice declares, so two reads of the same history answer the same
        way even when two events share a timestamp. An unknown
        ``schedule_item_id`` answers the empty tuple, not an error: "this row
        has no events yet" and "this row does not exist" are both "nothing to
        report", and the caller that needs to tell them apart has
        :meth:`get_schedule_item`.
        """

        rows = self._conn.execute(
            "SELECT review_event_id, schedule_item_id, teaching_moment_id,"
            " source_turn_id, event_type, engaged, evidence_group_id,"
            " created_at FROM review_event WHERE schedule_item_id = ?"
            " ORDER BY created_at, review_event_id",
            (schedule_item_id,),
        ).fetchall()
        return Ok(tuple(_event_from_row(row) for row in rows))

    def list_schedule_items(self) -> Result[tuple[ScheduleItem, ...]]:
        """Every current schedule row, in durable order (``schedule_item_id``).

        The read the §10 view is built from, and nothing more than that: the
        rows come back exactly as stored, in an order that is a property of the
        rows (the id), so two reads of one world answer identically. No state,
        window or stage is computed or filtered here — the classification is
        :mod:`elc.scheduler.spacing`'s, and a store that filtered by it would be
        a second home for the due decision (D-INV-009).

        An empty table answers the empty tuple: "no target has been scheduled
        yet" is a state of the world, not a failure.
        """

        rows = self._conn.execute(
            "SELECT schedule_item_id, target_type, target_id,"
            " evidence_modality, review_state, review_urgency,"
            " next_review_window_start, next_review_window_end,"
            " spacing_stage, source_learning_watermark, version, updated_at"
            " FROM schedule_item ORDER BY schedule_item_id"
        ).fetchall()
        return Ok(tuple(_item_from_row(row) for row in rows))

    # -- internals ---------------------------------------------------------

    def _insert_item(self, item: ScheduleItem, *, now: str) -> None:
        self._conn.execute(
            "INSERT INTO schedule_item ("
            " schedule_item_id, target_type, target_id, evidence_modality,"
            " review_state, review_urgency, next_review_window_start,"
            " next_review_window_end, spacing_stage,"
            " source_learning_watermark, version, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _item_columns(item)[:11] + (now,),
        )

    def _replace_item(self, item: ScheduleItem, *, now: str) -> None:
        self._conn.execute(
            "UPDATE schedule_item SET target_type = ?, target_id = ?,"
            " evidence_modality = ?, review_state = ?, review_urgency = ?,"
            " next_review_window_start = ?, next_review_window_end = ?,"
            " spacing_stage = ?, source_learning_watermark = ?, version = ?,"
            " updated_at = ? WHERE schedule_item_id = ?",
            _item_columns(item)[1:11] + (now, item.schedule_item_id),
        )

    def _item_row(self, schedule_item_id: str) -> ScheduleItem | None:
        row = self._conn.execute(
            "SELECT schedule_item_id, target_type, target_id,"
            " evidence_modality, review_state, review_urgency,"
            " next_review_window_start, next_review_window_end,"
            " spacing_stage, source_learning_watermark, version, updated_at"
            " FROM schedule_item WHERE schedule_item_id = ?",
            (schedule_item_id,),
        ).fetchone()
        if row is None:
            return None
        return _item_from_row(row)

    def _item_row_for_key(
        self,
        target_type: str,
        target_id: TargetId,
        evidence_modality: EvidenceModality,
    ) -> ScheduleItem | None:
        row = self._conn.execute(
            "SELECT schedule_item_id, target_type, target_id,"
            " evidence_modality, review_state, review_urgency,"
            " next_review_window_start, next_review_window_end,"
            " spacing_stage, source_learning_watermark, version, updated_at"
            " FROM schedule_item WHERE target_type = ? AND target_id = ?"
            " AND evidence_modality = ?",
            (target_type, str(target_id), evidence_modality.value),
        ).fetchone()
        if row is None:
            return None
        return _item_from_row(row)

    def _event_row(self, review_event_id: str) -> ReviewEvent | None:
        row = self._conn.execute(
            "SELECT review_event_id, schedule_item_id, teaching_moment_id,"
            " source_turn_id, event_type, engaged, evidence_group_id,"
            " created_at FROM review_event WHERE review_event_id = ?",
            (review_event_id,),
        ).fetchone()
        if row is None:
            return None
        return _event_from_row(row)


def _same_item(durable: ScheduleItem, incoming: ScheduleItem) -> bool:
    """Whether the durable row already holds exactly this content.

    ``updated_at`` is deliberately not compared: it is the store's clock, and
    two writes of unchanged content differ only there. ``version`` is not
    compared either — the caller of this helper compares it first, and this
    function answers the *content* question under a shared stamp.

    Every other column is compared verbatim, ``None`` included (``None`` is a
    value, not a wildcard: this slice gives ``review_urgency`` /
    ``spacing_stage`` / the window columns no interpretation, so it cannot
    decide that two different raw values mean the same thing). The modality
    key columns are part of the comparison too — a row whose target moved is
    different content under any stamp.
    """

    return (
        durable.target_type == incoming.target_type
        and str(durable.target_id) == str(incoming.target_id)
        and durable.evidence_modality == incoming.evidence_modality
        and durable.review_state == incoming.review_state
        and durable.review_urgency == incoming.review_urgency
        and durable.next_review_window_start
        == incoming.next_review_window_start
        and durable.next_review_window_end == incoming.next_review_window_end
        and durable.spacing_stage == incoming.spacing_stage
        and durable.source_learning_watermark
        == incoming.source_learning_watermark
    )


def _same_event(durable: ReviewEvent, incoming: ReviewEvent) -> bool:
    """Whether the durable row already holds exactly this content.

    ``review_event_id`` is the identity (the row was read by it) and is not
    compared. ``created_at`` is compared through
    :func:`_same_declared_time`: an undeclared time is a replay wildcard, a
    declared one must match verbatim — a declared time is content (§5.2's
    column; the 0007 precedent), so the same id with a *different* declared
    time is a different fact and is refused rather than silently restamped.
    """

    return (
        durable.schedule_item_id == incoming.schedule_item_id
        and durable.teaching_moment_id == incoming.teaching_moment_id
        and durable.source_turn_id == incoming.source_turn_id
        and durable.event_type == incoming.event_type
        and durable.engaged == incoming.engaged
        and durable.evidence_group_id == incoming.evidence_group_id
        and _same_declared_time(durable, incoming)
    )


def _same_declared_time(durable: ReviewEvent, incoming: ReviewEvent) -> bool:
    """The ``created_at`` leg of the content question.

    Undeclared (``""``) is a **wildcard**: the caller declared no time, so it
    cannot be in conflict with the store-stamped value the durable row holds —
    which is what makes a retry of the same silent write a replay instead of a
    refusal (ScheduleItem's ``updated_at`` gets the same treatment: a column
    the store stamped never decides a content question). Declared is content:
    it must equal the durable value verbatim.
    """

    if incoming.created_at == "":
        return True
    return durable.created_at == incoming.created_at
