"""The P8-5 test world: the observation port's adapter, and file-backed dbs.

Two things live here, and both exist because P8-5's deliverables have to run
over a **real** app.db rather than over hand-made records:

1. :class:`ObservationProbe` — the one implementation of
   :class:`elc.teaching.rollout.RolloutObservationPort` that exists today. The
   module's port docstring registers that four of its five reads are
   whole-table enumerations no durable face answers yet; this adapter composes
   what *does* exist (the per-conversation / per-cycle faces plus the real
   ledger store) with the three smallest probes that fill the gap — a
   ``SELECT DISTINCT <key>`` per table to find the keys, and one ``COUNT(*)``
   for the §6 claims. That is deliberately the *minimum* SQL a rollout report
   needs, written where a test's SQL lives, so the readings themselves stay
   pure and the missing production faces stay registered rather than faked.
2. :func:`open_file_db` / :func:`join_epoch` — a file-backed database and a
   **second connection** to it on the same runtime epoch (the P8-5 ⑤ evidence:
   ``:memory:`` would give two writers two different databases, which is the
   one thing a concurrency probe must not do). ``open_runtime_epoch`` fences
   every older epoch, so a second participant joins the *existing* epoch
   instead of opening a new one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

from elc.planner.ledger import PlanningLedger
from elc.planner.ledger_store import SqliteLedgerStore
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    ConversationId,
    DecisionCycleId,
    Err,
    Ok,
    PlannerDecision,
    Result,
)
from elc.teaching.rollout import (
    ObservationReading,
    collect_observations,
)
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import GateDecisionRecord, TeachingMomentRecord

__all__ = [
    "COUNT_CLAIMS",
    "LIST_DECISION_CYCLES",
    "LIST_GATE_CYCLES",
    "LIST_MOMENT_CONVERSATIONS",
    "ObservationProbe",
    "join_epoch",
    "open_file_db",
    "readings",
]

#: The three key-enumeration probes and the one count, declared as data so the
#: adapter's SQL is visible in one place (each is read-only).
LIST_MOMENT_CONVERSATIONS = (
    "SELECT DISTINCT conversation_id FROM teaching_moment"
)
LIST_GATE_CYCLES = "SELECT DISTINCT decision_cycle_id FROM gate_decision"
LIST_DECISION_CYCLES = "SELECT DISTINCT decision_cycle_id FROM planner_decision"
COUNT_CLAIMS = "SELECT COUNT(*) FROM evidence_claim"


class ObservationProbe:
    """The rollout observation port over one real connection.

    ``list_moments`` / ``list_gate_decisions`` / ``list_planner_decisions``
    compose the existing per-key reads over the keys the three probes answer;
    ``count_evidence_claims`` is the one count; ``read_ledger`` is the real
    store's own whole-ledger face. Nothing here classifies anything — the
    classification is :func:`elc.teaching.rollout.observations_of`.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        fence: RuntimeEpochFence,
    ) -> None:
        self._conn = conn
        self._teaching = SqliteTeachingStore(conn, fence)
        self._planner = SqlitePlannerRecordStore(conn, fence)
        self._ledger = SqliteLedgerStore(conn, fence)

    def list_moments(self) -> Result[Sequence[TeachingMomentRecord]]:
        moments: list[TeachingMomentRecord] = []
        for (conversation_id,) in self._conn.execute(
            LIST_MOMENT_CONVERSATIONS
        ).fetchall():
            page = self._teaching.list_moments_for_conversation(
                ConversationId(str(conversation_id))
            )
            if isinstance(page, Err):
                return page
            moments.extend(page.value)
        return Ok(tuple(moments))

    def list_gate_decisions(self) -> Result[Sequence[GateDecisionRecord]]:
        decisions: list[GateDecisionRecord] = []
        for (cycle_id,) in self._conn.execute(LIST_GATE_CYCLES).fetchall():
            page = self._teaching.get_gate_decisions(
                DecisionCycleId(str(cycle_id))
            )
            if isinstance(page, Err):
                return page
            decisions.extend(page.value)
        return Ok(tuple(decisions))

    def list_planner_decisions(self) -> Result[Sequence[PlannerDecision]]:
        decisions: list[PlannerDecision] = []
        for (cycle_id,) in self._conn.execute(LIST_DECISION_CYCLES).fetchall():
            decision = self._planner.get_planner_decision_for_cycle(
                DecisionCycleId(str(cycle_id))
            )
            if isinstance(decision, Err):
                return decision
            if decision.value is not None:
                decisions.append(decision.value)
        return Ok(tuple(decisions))

    def count_evidence_claims(self) -> Result[int]:
        return Ok(int(self._conn.execute(COUNT_CLAIMS).fetchone()[0]))

    def read_ledger(self) -> Result[PlanningLedger]:
        return self._ledger.read_ledger()


def readings(
    conn: sqlite3.Connection,
    fence: RuntimeEpochFence,
    *,
    as_of: str,
) -> tuple[ObservationReading, ...]:
    """The six readings over one real database (the collector, asserted ``Ok``)."""

    collected = collect_observations(ObservationProbe(conn, fence), as_of=as_of)
    assert isinstance(collected, Ok), collected
    return collected.value


def open_file_db(path: Path) -> tuple[sqlite3.Connection, RuntimeEpochFence]:
    """A file-backed app.db with the real migrations and a fresh epoch."""

    conn = connection.connect(path)
    migrations.apply_migrations(conn)
    fence = epoch.open_runtime_epoch(conn)
    return conn, fence


def join_epoch(path: Path) -> tuple[sqlite3.Connection, RuntimeEpochFence]:
    """A **second** connection to the same file, on the same runtime epoch.

    Two processes of one run share an epoch number; opening a new epoch here
    would fence the first connection's writes (``RuntimeEpochFence`` is an
    equality, not an ordering), which is a different experiment than "two
    writers race".
    """

    conn = connection.connect(path)
    current = epoch.load_current_epoch(conn)
    if current is None:
        raise AssertionError(f"{path} carries no runtime epoch")
    return conn, RuntimeEpochFence(current=current)
