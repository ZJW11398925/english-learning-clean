"""SQLite adapter for the Runtime-owned DecisionCycle store (Phase 3 P3-1A).

TASK-OPI-2babb21e-bc72-47a2-9382-e773c92211d2.17 ②. The §4 authority
(port + bindings type) lives in ``elc.runtime.decision_cycles`` — Runtime
owns DecisionCycle (DOMAIN_MODEL §16) and stays SQL-free (Gate item 2).
The physical rows live in app.db, colocated with the conversation
persistence so the cycle-creation unit is a real short transaction
(DATA_MODEL §2: 物理共库不等于 Domain Authority 合并) — the same split as
the §14 generation authority (elc.runtime.generation) and its executor
(elc.platform.db.generation_store).

Discipline:
- cycle row creation + ``turn_record.active_decision_cycle_id`` update are
  ONE short transaction under the TurnRecord state_version CAS plus the
  owner_epoch fence (STATE_MACHINES §20; RUNTIME §24) — a stale version, a
  fenced epoch or a terminal turn refuses and leaves no cycle row;
- ``cycle_index`` is allocated inside that unit (0 for the turn's first
  cycle, +1 per same-turn replan; UNIQUE (turn_id, cycle_index) is the
  durable guard, §4/§25);
- a re-record of the same decision_cycle_id replays the durable row and
  writes nothing (stable opaque id, DATA_MODEL §1.2 — the P1 store
  precedent);
- the ACL of this migration-0007 schema allows NULL snapshot/version
  columns (legacy cycles + phases whose version sources have not arrived);
  the adapter writes exactly the bindings it is handed, never a default.

All SQL is a fixed literal with bound parameters — no identifier assembly.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
    RuntimeEpoch,
    TurnId,
)
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.types import (
    TERMINAL_TURN_STATUSES,
    DecisionCycleRecord,
    TurnStatus,
)

__all__ = ["SqliteDecisionCycleStore", "StaleStoreEpochError"]

T = TypeVar("T")


class StaleStoreEpochError(StaleEpochError):
    """A decision-cycle write was fenced by a newer runtime epoch."""


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


#: §4 column order used by every SELECT in this module.
_CYCLE_COLUMNS = (
    "decision_cycle_id",
    "turn_id",
    "cycle_index",
    "learning_snapshot_id",
    "evidence_watermark",
    "curriculum_version",
    "goal_version",
    "schedule_version",
    "policy_version",
    "context_view_version",
    "relationship_view_version",
    "planner_decision_id",
    "gate_decision_id",
    "created_at",
)


def _cycle_record(row: sqlite3.Row) -> DecisionCycleRecord:
    """Decode one §4 row (default tuple rows; positional column order is
    the _CYCLE_COLUMNS literal used by every SELECT here)."""

    return DecisionCycleRecord(
        decision_cycle_id=DecisionCycleId(str(row[0])),
        turn_id=TurnId(str(row[1])),
        cycle_index=int(row[2]),
        learning_snapshot_id=None if row[3] is None else str(row[3]),
        evidence_watermark=None if row[4] is None else int(row[4]),
        curriculum_version=None if row[5] is None else str(row[5]),
        goal_version=None if row[6] is None else str(row[6]),
        schedule_version=None if row[7] is None else str(row[7]),
        policy_version=None if row[8] is None else str(row[8]),
        context_view_version=None if row[9] is None else str(row[9]),
        relationship_view_version=None if row[10] is None else str(row[10]),
        planner_decision_id=None if row[11] is None else str(row[11]),
        gate_decision_id=None if row[12] is None else str(row[12]),
        created_at=None if row[13] is None else str(row[13]),
    )


class SqliteDecisionCycleStore:
    """Durable §4 DecisionCycle rows (Runtime-owned authority, app.db)."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    @property
    def current_epoch(self) -> RuntimeEpoch:
        return RuntimeEpoch(self._fence.current)

    def _require_current_epoch(self) -> None:
        """Fence inside the write transaction: the adopted epoch must still
        be the newest epoch row in app.db (RUNTIME §24 restart ownership)."""
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"decision-cycle store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- DecisionCycleStore ------------------------------------------------

    def record_decision_cycle(
        self,
        *,
        decision_cycle_id: DecisionCycleId,
        turn_id: TurnId,
        bindings: DecisionCycleBindings,
        expected_turn_state_version: int,
    ) -> Result[DecisionCycleRecord]:
        """One short transaction: cycle row + active pointer + CAS (§4)."""

        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                replay = self._conn.execute(
                    "SELECT " + ", ".join(_CYCLE_COLUMNS)
                    + " FROM decision_cycle WHERE decision_cycle_id = ?",
                    (decision_cycle_id,),
                ).fetchone()
                if replay is not None:
                    if str(replay[1]) != turn_id:
                        return _err(
                            DomainErrorCode.CONFLICT,
                            f"decision_cycle_id {decision_cycle_id} is already"
                            f" durable for turn {replay[1]}",
                        )
                    return Ok(_cycle_record(replay))

                turn = self._conn.execute(
                    "SELECT status, owner_epoch, state_version FROM turn_record"
                    " WHERE turn_id = ?",
                    (turn_id,),
                ).fetchone()
                if turn is None:
                    return _err(
                        DomainErrorCode.NOT_FOUND,
                        f"turn record not found: {turn_id}",
                    )
                if TurnStatus(str(turn[0])) in TERMINAL_TURN_STATUSES:
                    return _err(
                        DomainErrorCode.VALIDATION_FAILED,
                        f"turn {turn_id} is terminal ({turn[0]}); no new"
                        " DecisionCycle opens on a terminal turn",
                    )
                if int(turn[1]) != self._fence.current:
                    return _err(
                        DomainErrorCode.AUTHORITY_VIOLATION,
                        f"owner_epoch={turn[1]} fenced by"
                        f" current epoch={self._fence.current}",
                    )
                if int(turn[2]) != expected_turn_state_version:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"state_version CAS mismatch on {turn_id}: expected"
                        f" {expected_turn_state_version}, durable {turn[2]}",
                    )

                index_row = self._conn.execute(
                    "SELECT COALESCE(MAX(cycle_index), -1) + 1"
                    " FROM decision_cycle WHERE turn_id = ?",
                    (turn_id,),
                ).fetchone()
                assert index_row is not None  # aggregate always returns a row
                cycle_index = int(index_row[0])
                created_at = _now()
                self._conn.execute(
                    "INSERT INTO decision_cycle ("
                    " decision_cycle_id, turn_id, cycle_index,"
                    " learning_snapshot_id, evidence_watermark,"
                    " curriculum_version, goal_version, schedule_version,"
                    " policy_version, context_view_version,"
                    " relationship_view_version, planner_decision_id,"
                    " gate_decision_id, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
                    (
                        decision_cycle_id,
                        turn_id,
                        cycle_index,
                        bindings.learning_snapshot_id,
                        bindings.evidence_watermark,
                        bindings.curriculum_version,
                        bindings.goal_version,
                        bindings.schedule_version,
                        bindings.policy_version,
                        bindings.context_view_version,
                        bindings.relationship_view_version,
                        created_at,
                    ),
                )
                cursor = self._conn.execute(
                    "UPDATE turn_record SET active_decision_cycle_id = ?,"
                    " state_version = state_version + 1, updated_at = ?"
                    " WHERE turn_id = ? AND state_version = ?"
                    " AND owner_epoch = ?",
                    (
                        decision_cycle_id,
                        created_at,
                        turn_id,
                        expected_turn_state_version,
                        self._fence.current,
                    ),
                )
                if cursor.rowcount != 1:
                    # The CAS above already validated the row in this same
                    # transaction; a miss means the row changed under us —
                    # refuse rather than pin an active cycle nobody owns.
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"active_decision_cycle_id CAS refused on {turn_id}",
                    )
                return Ok(
                    DecisionCycleRecord(
                        decision_cycle_id=decision_cycle_id,
                        turn_id=turn_id,
                        cycle_index=cycle_index,
                        learning_snapshot_id=bindings.learning_snapshot_id,
                        evidence_watermark=bindings.evidence_watermark,
                        curriculum_version=bindings.curriculum_version,
                        goal_version=bindings.goal_version,
                        schedule_version=bindings.schedule_version,
                        policy_version=bindings.policy_version,
                        context_view_version=bindings.context_view_version,
                        relationship_view_version=(
                            bindings.relationship_view_version
                        ),
                        planner_decision_id=None,
                        gate_decision_id=None,
                        created_at=created_at,
                    )
                )
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def get_decision_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[DecisionCycleRecord | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_CYCLE_COLUMNS)
            + " FROM decision_cycle WHERE decision_cycle_id = ?",
            (decision_cycle_id,),
        ).fetchone()
        return Ok(None if row is None else _cycle_record(row))

    def get_active_decision_cycle(
        self, turn_id: TurnId
    ) -> Result[DecisionCycleRecord | None]:
        row = self._conn.execute(
            "SELECT d.decision_cycle_id, d.turn_id, d.cycle_index,"
            " d.learning_snapshot_id, d.evidence_watermark,"
            " d.curriculum_version, d.goal_version, d.schedule_version,"
            " d.policy_version, d.context_view_version,"
            " d.relationship_view_version, d.planner_decision_id,"
            " d.gate_decision_id, d.created_at"
            " FROM turn_record t JOIN decision_cycle d"
            "   ON d.decision_cycle_id = t.active_decision_cycle_id"
            " WHERE t.turn_id = ?",
            (turn_id,),
        ).fetchone()
        return Ok(None if row is None else _cycle_record(row))

    def get_turn_cycle(
        self, turn_id: TurnId, cycle_index: int
    ) -> Result[DecisionCycleRecord | None]:
        row = self._conn.execute(
            "SELECT " + ", ".join(_CYCLE_COLUMNS)
            + " FROM decision_cycle WHERE turn_id = ? AND cycle_index = ?",
            (turn_id, cycle_index),
        ).fetchone()
        return Ok(None if row is None else _cycle_record(row))
