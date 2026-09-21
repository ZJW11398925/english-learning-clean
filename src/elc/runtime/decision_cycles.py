"""DecisionCycle authority — Runtime-owned (Phase 3 P3-1A, TASK-…17 ②).

docs/DATA_MODEL.md §4 DecisionCycle; docs/DOMAIN_MODEL.md §16 lists
DecisionCycle among the Runtime-specific records ("Runtime / Platform ...
DecisionCycle"). The authority therefore lives here — as a pure,
SQL-free port (Gate item 2 keeps this package SQL-free) — while the
durable SQLite adapter is colocated with the conversation persistence in
app.db (``elc.platform.db.decision_cycle_store``; DATA_MODEL §2: 物理共库
不等于 Domain Authority 合并). The generation-action precedent: the §14
authority lives in ``elc.runtime.generation`` and its executor in
``elc.platform.db.generation_store``.

Cycle semantics owned here:

- one row per (turn, cycle_index); the index starts at 0 and increments
  within the same turn (docs/DATA_MODEL.md §4 Unique (turn_id,
  cycle_index); STATE_MACHINES §11 same-turn explicit target switch);
- the snapshot/version bindings are fixed inside one cycle (R-INV-003) —
  Planner / Gate / Teaching action planning never silently switch versions
  inside a cycle (RUNTIME_ARCHITECTURE §9);
- creating a cycle and pointing ``turn_record.active_decision_cycle_id``
  at it is ONE short transaction under the TurnRecord state_version CAS
  (STATE_MACHINES §20), so an out-of-order or fenced writer can never pin
  an active cycle the runtime does not own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from elc.platform.types import DecisionCycleId, Result, TurnId
from elc.runtime.types import DecisionCycleRecord

__all__ = [
    "DecisionCycleBindings",
    "DecisionCycleStore",
]


@dataclass(frozen=True)
class DecisionCycleBindings:
    """The §4 snapshot/version bindings fixed inside one cycle (R-INV-003).

    ``None`` means "no source in this phase" — a value is only ever stamped
    from a real authority (the Learning snapshot's id + watermark in
    Phase 3); nothing is fabricated to fill a column. A legacy cycle
    (migration 0007 backfill) carries the all-None bindings: it predates
    the snapshot machinery and says so honestly.
    """

    learning_snapshot_id: str | None = None
    evidence_watermark: int | None = None
    curriculum_version: str | None = None
    goal_version: str | None = None
    schedule_version: str | None = None
    policy_version: str | None = None
    context_view_version: str | None = None
    relationship_view_version: str | None = None


@runtime_checkable
class DecisionCycleStore(Protocol):
    """Runtime-owned DecisionCycle write/read face (§4).

    Implemented by ``elc.platform.db.decision_cycle_store.
    SqliteDecisionCycleStore`` (keyword-only construction: connection +
    runtime epoch fence).
    """

    def record_decision_cycle(
        self,
        *,
        decision_cycle_id: DecisionCycleId,
        turn_id: TurnId,
        bindings: DecisionCycleBindings,
        expected_turn_state_version: int,
    ) -> Result[DecisionCycleRecord]:
        """Create the next cycle of ``turn_id`` and point the turn's
        ``active_decision_cycle_id`` at it — one short transaction.

        ``cycle_index`` is allocated inside the unit (0 for the first
        cycle of the turn, +1 per same-turn replan; UNIQUE (turn_id,
        cycle_index) is the durable guard). The TurnRecord write is a
        state_version CAS plus the owner_epoch fence: a stale version, a
        fenced epoch or a terminal turn refuses (CONFLICT /
        AUTHORITY_VIOLATION) and leaves no cycle row behind.
        """
        ...

    def get_decision_cycle(
        self, decision_cycle_id: DecisionCycleId
    ) -> Result[DecisionCycleRecord | None]:
        """§4 row read (None = not found)."""
        ...

    def get_active_decision_cycle(
        self, turn_id: TurnId
    ) -> Result[DecisionCycleRecord | None]:
        """The cycle ``turn_record.active_decision_cycle_id`` points at
        (None when the turn has no active cycle)."""
        ...

    def get_turn_cycle(
        self, turn_id: TurnId, cycle_index: int
    ) -> Result[DecisionCycleRecord | None]:
        """The (turn, cycle_index) row — the deterministic lookup the
        same-turn replan path uses after a frozen cycle."""
        ...
