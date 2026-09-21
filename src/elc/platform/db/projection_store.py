"""SQLite adapter for the Runtime-owned CP4 projection job queue (P4-2).

The §22.1 authority (the port + the deterministic ids + the failure-code
mapping) lives in ``elc.runtime.projections`` — Runtime owns ProjectionJob
(docs/DOMAIN_MODEL.md §16) and stays SQL-free (tests/architecture Gate item
2). The physical rows live in app.db, in the table migration 0002 already
created, so this slice adds **no** schema and **no** migration: every face
below is a state transition over the nine §22.1 columns.

Discipline (the generation-store / decision-cycle-store precedent):

- every write runs in one ``short_transaction`` and checks the store epoch
  against the newest durable epoch before anything is written (a stale store
  is a programming error and raises, the repo-wide fence convention);
- every state move is a compare-and-swap on the durable ``status`` column:
  a claim only fires from PENDING / FAILED_RETRYABLE, a completion only from
  RUNNING, a rejection never from COMMITTED / REJECTED. A mismatch is a
  ``CONFLICT`` with the durable word in the message — never a silent
  overwrite (STATE_MACHINES §20's CAS intent on the §22.1 column set, which
  pins no state_version column);
- enqueue is idempotent on ``projection_id``: the same payload replays the
  durable row with no write, a different payload is a ``CONFLICT``, and an
  existing row's state is never reset (P4-0 ④'s "stable projection_id" +
  "idempotent enqueue" contract);
- conversation-scoped reads join through ``turn_record``: migration 0002's
  ``projection_job`` table has no ``conversation_id`` column, so a job's
  conversation is only reachable through its source turn (the F1 note in
  ``elc.runtime.projections.ProjectionJobStore`` carries the same fact).

All SQL is a fixed literal with bound parameters — no identifier assembly,
no runtime value in any statement text.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    ProjectionJobId,
    Result,
    TurnId,
)
from elc.runtime.projections import ProjectionJobView
from elc.runtime.types import (
    ProjectionJobRecord,
    ProjectionJobState,
    TurnStatus,
)

__all__ = ["StaleStoreEpochError", "SqliteProjectionStore"]

T = TypeVar("T")

#: The two statuses a job may be claimed from (§22.1: PENDING → RUNNING and
#: the FAILED_RETRYABLE → RUNNING retry edge).
_CLAIMABLE = (
    ProjectionJobState.PENDING,
    ProjectionJobState.FAILED_RETRYABLE,
)


class StaleStoreEpochError(StaleEpochError):
    """A projection write was fenced by a newer runtime epoch."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


class SqliteProjectionStore:
    """Durable CP4 work queue over migration 0002's ``projection_job``."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"projection store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- writes ------------------------------------------------------------

    def enqueue_projection(
        self, job: ProjectionJobRecord
    ) -> Result[ProjectionJobId]:
        """Make one job durable (idempotently) — see the module docstring.

        Birth state: a **new** row is only ever written PENDING. A record
        whose ``state`` is anything else is refused with VALIDATION_FAILED and
        writes nothing — a job born RUNNING / COMMITTED / FAILED_RETRYABLE /
        REJECTED would be a row the state machine never walked (and a born
        COMMITTED / REJECTED row would be invisible to every pending read
        forever). The §22.1 machine owns every later move; the caller only
        declares the birth.

        The registry field ``source_version`` maps to the durable column
        ``source_turn_slice_hash`` (DOMAIN_MODEL §16 ↔ DATA_MODEL §22.1).
        Replay compares exactly the three payload facts the caller owns
        (projection type, source turn, slice hash) — the row's status,
        attempt count and base version are the queue's own state, so a
        re-enqueue never resets them and never reads them as a mismatch.
        """

        projection_id = job.projection_job_id
        if job.state is not ProjectionJobState.PENDING:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                "new projection rows are born PENDING; a job record with any"
                " other state is a caller bug",
            )
        try:
            with short_transaction(self._conn):
                existing = self._job_row(projection_id)
                if existing is not None:
                    if _same_payload(existing, job):
                        return Ok(projection_id)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"projection {projection_id} already exists with a"
                        " different payload; a stable projection_id names one"
                        " job (docs/DATA_MODEL.md §1.2)",
                    )
                self._require_current_epoch()
                self._conn.execute(
                    "INSERT INTO projection_job ("
                    " projection_id, projection_type, source_turn_id,"
                    " source_turn_slice_hash, base_domain_version, status,"
                    " attempt_count, created_at, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(projection_id),
                        job.projection_type,
                        str(job.source_turn_id),
                        job.source_version,
                        None,
                        job.state.value,
                        0,
                        _now(),
                        _now(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))
        return Ok(projection_id)

    def claim_projection(
        self, projection_id: ProjectionJobId, *, base_version: str | None
    ) -> Result[ProjectionJobView]:
        """PENDING / FAILED_RETRYABLE → RUNNING under a status CAS.

        The retry edge is the same statement: a FAILED_RETRYABLE job claimed
        again advances ``attempt_count`` once more and stores the freshly
        computed ``base_domain_version`` (DATA_MODEL §22.1's version-aware
        revalidation — the base is recomputed by the caller, never read back
        from the row).

        Column semantics: ``base_domain_version`` is the base *snapshot at
        claim time* — the version the run was authorized against, recorded so
        a retry can be reasoned about afterwards. Execution itself is never
        driven from this column: the executor reads the current base (here,
        the current same-persona summary) again for the work it does, so a
        base that moves between claim and execution does not make the run
        write against a stale view.
        """

        with short_transaction(self._conn):
            self._require_current_epoch()
            row = self._job_row(projection_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"projection job not found: {projection_id}",
                )
            durable = ProjectionJobState(str(row[5]))
            if durable not in _CLAIMABLE:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"projection {projection_id} is {durable.value}; only"
                    " PENDING / FAILED_RETRYABLE may be claimed (§22.1:"
                    " PENDING → RUNNING, FAILED_RETRYABLE → RUNNING)",
                )
            updated = self._conn.execute(
                "UPDATE projection_job SET status = ?, base_domain_version = ?,"
                " attempt_count = attempt_count + 1, updated_at = ?"
                " WHERE projection_id = ? AND status = ?",
                (
                    ProjectionJobState.RUNNING.value,
                    base_version,
                    _now(),
                    str(projection_id),
                    durable.value,
                ),
            )
            if updated.rowcount != 1:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"projection {projection_id} changed while being claimed"
                    f" (durable status moved past {durable.value})",
                )
            return Ok(self._view(projection_id))

    def complete_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView]:
        """RUNNING → COMMITTED (the projection landed)."""

        return self._advance(
            projection_id,
            expected=(ProjectionJobState.RUNNING,),
            new=ProjectionJobState.COMMITTED,
            refusal=(
                "only a RUNNING projection this run claimed may complete"
                " (§22.1: RUNNING → COMMITTED)"
            ),
        )

    def fail_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView]:
        """RUNNING → FAILED_RETRYABLE (a transient failure; the job may be
        claimed again later)."""

        return self._advance(
            projection_id,
            expected=(ProjectionJobState.RUNNING,),
            new=ProjectionJobState.FAILED_RETRYABLE,
            refusal=(
                "only a RUNNING projection may fail retryably (§22.1:"
                " RUNNING → FAILED_RETRYABLE)"
            ),
        )

    def reject_projection(
        self, projection_id: ProjectionJobId, *, reason: str
    ) -> Result[ProjectionJobView]:
        """PENDING / RUNNING / FAILED_RETRYABLE → REJECTED.

        ``reason`` is the caller's explanation of the deterministic refusal.
        The §22.1 column set is closed and this slice adds no migration, so
        the durable row has no reason column: the reason travels back with
        the caller's run trace, never into the table.
        """

        del reason  # the caller's trace; §22.1 has no column for it
        return self._advance(
            projection_id,
            expected=(
                ProjectionJobState.PENDING,
                ProjectionJobState.RUNNING,
                ProjectionJobState.FAILED_RETRYABLE,
            ),
            new=ProjectionJobState.REJECTED,
            refusal=(
                "a COMMITTED / REJECTED projection is finished work and is"
                " never re-opened by a rejection (§22.1: FAILED_RETRYABLE →"
                " REJECTED)"
            ),
        )

    def reopen_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView]:
        """RUNNING → FAILED_RETRYABLE — the stale-run re-open (§22 startup).

        A RUNNING row whose run never reported is residue, not work in
        progress, once a *new* process start is looking at it (see
        ``CP4ProjectionRuntime.recover_stale_running``): the re-open puts it
        back on the retry edge so the ordinary claim path can pick it up
        again — with the same source-aware + version-aware revalidation every
        retry gets. Only RUNNING may be re-opened: a PENDING /
        FAILED_RETRYABLE row is already claimable and a COMMITTED / REJECTED
        row is finished work, so those refuse with ``CONFLICT``.
        """

        return self._advance(
            projection_id,
            expected=(ProjectionJobState.RUNNING,),
            new=ProjectionJobState.FAILED_RETRYABLE,
            refusal=(
                "only a RUNNING projection is a stale run; a PENDING /"
                " FAILED_RETRYABLE row is already claimable and a COMMITTED /"
                " REJECTED row is finished work (§22 startup re-open)"
            ),
        )

    def _advance(
        self,
        projection_id: ProjectionJobId,
        *,
        expected: tuple[ProjectionJobState, ...],
        new: ProjectionJobState,
        refusal: str,
    ) -> Result[ProjectionJobView]:
        """One CAS-guarded status move (the shared body of the three
        non-claim transitions)."""

        with short_transaction(self._conn):
            self._require_current_epoch()
            row = self._job_row(projection_id)
            if row is None:
                return _err(
                    DomainErrorCode.NOT_FOUND,
                    f"projection job not found: {projection_id}",
                )
            durable = ProjectionJobState(str(row[5]))
            if durable not in expected:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"projection {projection_id} is {durable.value}; {refusal}",
                )
            updated = self._conn.execute(
                "UPDATE projection_job SET status = ?, updated_at = ?"
                " WHERE projection_id = ? AND status = ?",
                (new.value, _now(), str(projection_id), durable.value),
            )
            if updated.rowcount != 1:
                return _err(
                    DomainErrorCode.CONFLICT,
                    f"projection {projection_id} changed while advancing it"
                    f" (durable status moved past {durable.value})",
                )
            return Ok(self._view(projection_id))

    # -- reads -------------------------------------------------------------

    def get_projection(
        self, projection_id: ProjectionJobId
    ) -> Result[ProjectionJobView | None]:
        """One durable job row (``None`` = never enqueued). Pure read."""

        row = self._job_row(projection_id)
        return Ok(None if row is None else self._record(row))

    def pending_projections(
        self, conversation_id: ConversationId
    ) -> Result[tuple[ProjectionJobView, ...]]:
        """The conversation's PENDING + FAILED_RETRYABLE jobs, oldest first.

        ``projection_job`` has no conversation column (migration 0002), so
        the scope is applied through the source turn's own row — an inner
        join on ``turn_record``, which is also what makes this read
        conversation-scoped without a second index or a denormalized column.
        """

        rows = self._conn.execute(
            "SELECT p.projection_id, p.projection_type, p.source_turn_id,"
            " p.source_turn_slice_hash, p.base_domain_version, p.status,"
            " p.attempt_count, p.created_at, p.updated_at"
            " FROM projection_job AS p"
            " JOIN turn_record AS t ON t.turn_id = p.source_turn_id"
            " WHERE t.conversation_id = ? AND p.status IN (?, ?)"
            " ORDER BY p.created_at, p.projection_id",
            (
                str(conversation_id),
                ProjectionJobState.PENDING.value,
                ProjectionJobState.FAILED_RETRYABLE.value,
            ),
        ).fetchall()
        return Ok(tuple(self._record(row) for row in rows))

    def unfinished_projections(
        self,
    ) -> Result[tuple[ProjectionJobView, ...]]:
        """Every unfinished job in the queue, oldest first.

        The whole-registry read (PENDING + FAILED_RETRYABLE, no conversation
        filter): the startup sweep has to drain what is *in the queue*, not
        only the jobs it just repaired or re-opened — a PENDING row left by a
        crash between its enqueue and its run belongs to a conversation the
        sweep would otherwise never visit. A pure read; the durable order is
        the queue's own (``created_at``, then id).
        """

        rows = self._conn.execute(
            "SELECT projection_id, projection_type, source_turn_id,"
            " source_turn_slice_hash, base_domain_version, status,"
            " attempt_count, created_at, updated_at"
            " FROM projection_job WHERE status IN (?, ?)"
            " ORDER BY created_at, projection_id",
            (
                ProjectionJobState.PENDING.value,
                ProjectionJobState.FAILED_RETRYABLE.value,
            ),
        ).fetchall()
        return Ok(tuple(self._record(row) for row in rows))

    def running_projections(self) -> Result[tuple[ProjectionJobView, ...]]:
        """Every RUNNING job, oldest first (the §22 startup scan).

        Not conversation-scoped on purpose: a RUNNING row is global residue —
        it is in nobody's *pending* set — and the startup pass is the one
        place that may look at all of them (``recover_stale_running``).
        """

        rows = self._conn.execute(
            "SELECT projection_id, projection_type, source_turn_id,"
            " source_turn_slice_hash, base_domain_version, status,"
            " attempt_count, created_at, updated_at"
            " FROM projection_job WHERE status = ?"
            " ORDER BY created_at, projection_id",
            (ProjectionJobState.RUNNING.value,),
        ).fetchall()
        return Ok(tuple(self._record(row) for row in rows))

    def turns_missing_projection(
        self, projection_type: str
    ) -> Result[tuple[TurnId, ...]]:
        """The COMPLETED turns with no job of this type (the crash-gap read).

        An anti-join, not a scan-and-compare: the durable shape of a crash
        between the turn's commit points is "the turn completed and its job
        row is not there", and that is exactly ``LEFT JOIN ... IS NULL``.
        Ordered by conversation, then turn sequence — the order the repair
        walks (and the order a reviewer reads).
        """

        rows = self._conn.execute(
            "SELECT t.turn_id FROM turn_record AS t"
            " LEFT JOIN projection_job AS p ON p.source_turn_id = t.turn_id"
            " AND p.projection_type = ?"
            " WHERE t.status = ? AND p.projection_id IS NULL"
            " ORDER BY t.conversation_id, t.turn_sequence, t.turn_id",
            (projection_type, TurnStatus.COMPLETED.value),
        ).fetchall()
        return Ok(tuple(TurnId(str(row[0])) for row in rows))

    # -- internals ---------------------------------------------------------

    def _job_row(self, projection_id: ProjectionJobId) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT projection_id, projection_type, source_turn_id,"
            " source_turn_slice_hash, base_domain_version, status,"
            " attempt_count, created_at, updated_at"
            " FROM projection_job WHERE projection_id = ?",
            (str(projection_id),),
        ).fetchone()

    def _view(self, projection_id: ProjectionJobId) -> ProjectionJobView:
        row = self._job_row(projection_id)
        assert row is not None  # the caller held the row in the same tx
        return self._record(row)

    @staticmethod
    def _record(row: sqlite3.Row) -> ProjectionJobView:
        return ProjectionJobView(
            projection_job_id=ProjectionJobId(str(row[0])),
            projection_type=str(row[1]),
            source_turn_id=TurnId(str(row[2])),
            source_turn_slice_hash=str(row[3]),
            base_domain_version=(
                None if row[4] is None else str(row[4])
            ),
            status=ProjectionJobState(str(row[5])),
            attempt_count=int(row[6]),
            created_at=str(row[7]),
            updated_at=str(row[8]),
        )


def _same_payload(durable: sqlite3.Row, incoming: ProjectionJobRecord) -> bool:
    """The replay comparison: the three payload facts the caller owns.

    ``status`` / ``attempt_count`` / ``base_domain_version`` are the queue's
    own state (and ``created_at`` / ``updated_at`` are the store's clock), so
    they are deliberately not compared: a re-enqueue must not be able to
    reset a claimed job back to PENDING by shipping the original record.
    """

    return (
        str(durable[1]) == incoming.projection_type
        and str(durable[2]) == str(incoming.source_turn_id)
        and str(durable[3]) == incoming.source_version
    )
