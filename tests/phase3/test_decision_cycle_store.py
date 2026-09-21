"""VAL ② — the Runtime-owned DecisionCycle store.

docs/DATA_MODEL.md §4 + STATE_MACHINES §11/§20: a cycle row and the
turn's ``active_decision_cycle_id`` are written in ONE short transaction
under the TurnRecord state_version CAS; ``cycle_index`` starts at 0 and
increments within the same turn; a normal persona turn opens a cycle too
(all-None bindings — no Planner/Gate and no Curriculum/Goal/Schedule/
Policy source in Phase 3).

The store implements the SQL-free port declared in
elc.runtime.decision_cycles (runtime_checkable), which is what the
coordinator consumes.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import Err, Ok, TurnId
from elc.runtime.decision_cycles import (
    DecisionCycleBindings,
    DecisionCycleStore,
)
from tests.phase2.conftest import commit_ok


def _cycle_count(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT COUNT(*) FROM decision_cycle").fetchone()[0])


def test_store_implements_the_runtime_port(
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    assert isinstance(decision_cycle_store, DecisionCycleStore)


def test_record_cycle_writes_row_and_active_pointer_together(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-dc-1", "hello")
    result = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-cm-dc-1",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(
            learning_snapshot_id="lsnap-x", evidence_watermark=3
        ),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(result, Ok), result
    cycle = result.value
    assert cycle.cycle_index == 0
    assert cycle.learning_snapshot_id == "lsnap-x"
    assert cycle.evidence_watermark == 3
    assert cycle.planner_decision_id is None
    assert cycle.gate_decision_id is None

    pointer = db.execute(
        "SELECT active_decision_cycle_id, state_version FROM turn_record"
        " WHERE turn_id = ?",
        (cp0.turn_id,),
    ).fetchone()
    assert pointer is not None
    assert pointer[0] == "dcy-cm-dc-1"  # the pointer landed in the unit
    assert int(pointer[1]) == cp0.state_version + 1  # CAS advanced it

    active = decision_cycle_store.get_active_decision_cycle(cp0.turn_id)
    assert isinstance(active, Ok) and active.value is not None
    assert active.value.decision_cycle_id == "dcy-cm-dc-1"
    fetched = decision_cycle_store.get_decision_cycle("dcy-cm-dc-1")
    assert isinstance(fetched, Ok) and fetched.value == cycle
    at_index = decision_cycle_store.get_turn_cycle(cp0.turn_id, 0)
    assert isinstance(at_index, Ok) and at_index.value == cycle


def test_cycle_index_increments_within_the_same_turn(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    """STATE_MACHINES §11: a same-turn replan gets cycle_index + 1 (the
    §4 UNIQUE (turn_id, cycle_index) keeps them distinct)."""

    cp0 = commit_ok(store, conversation, "cm-dc-2", "hello")
    first = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-t2-0",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(first, Ok) and first.value.cycle_index == 0
    second = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-t2-1",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(evidence_watermark=1),
        expected_turn_state_version=first.value.cycle_index + 2,
    )
    assert isinstance(second, Ok), second
    assert second.value.cycle_index == 1
    assert _cycle_count(db) == 2
    pointer = db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (cp0.turn_id,),
    ).fetchone()
    assert pointer is not None and pointer[0] == "dcy-t2-1"


def test_state_version_cas_mismatch_writes_nothing(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-dc-3", "hello")
    refused = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-t3",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=99,
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "CONFLICT"
    assert "state_version CAS mismatch" in refused.error.message
    assert _cycle_count(db) == 0
    pointer = db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (cp0.turn_id,),
    ).fetchone()
    assert pointer is not None and pointer[0] is None


def test_terminal_turn_refuses_a_new_cycle(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-dc-4", "hello")
    from elc.conversation.types import TurnOutcome

    terminal = store.terminalize_turn(cp0.turn_id, TurnOutcome.NO_ASSISTANT_OUTPUT)
    assert isinstance(terminal, Ok)
    refused = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-t4",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=terminal.value.state_version,
    )
    assert isinstance(refused, Err)
    assert refused.error.code.value == "VALIDATION_FAILED"
    assert _cycle_count(db) == 0


def test_stable_id_replays_without_a_second_write(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    cp0 = commit_ok(store, conversation, "cm-dc-5", "hello")
    first = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-t5",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(evidence_watermark=2),
        expected_turn_state_version=cp0.state_version,
    )
    assert isinstance(first, Ok)
    version_after_first = db.execute(
        "SELECT state_version FROM turn_record WHERE turn_id = ?",
        (cp0.turn_id,),
    ).fetchone()[0]

    replay = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-t5",
        turn_id=cp0.turn_id,
        bindings=DecisionCycleBindings(evidence_watermark=999),
        expected_turn_state_version=cp0.state_version,  # stale on purpose
    )
    assert isinstance(replay, Ok)
    assert replay.value == first.value  # durable row, no rewrite
    assert _cycle_count(db) == 1
    assert (
        db.execute(
            "SELECT state_version FROM turn_record WHERE turn_id = ?",
            (cp0.turn_id,),
        ).fetchone()[0]
        == version_after_first
    )


def test_unknown_turn_is_not_found(
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    missing = decision_cycle_store.record_decision_cycle(
        decision_cycle_id="dcy-x",
        turn_id=TurnId("turn-missing"),
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=1,
    )
    assert isinstance(missing, Err)
    assert missing.error.code.value == "NOT_FOUND"


def test_legacy_cycle_reads_with_all_none_bindings(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    conversation,
    decision_cycle_store: SqliteDecisionCycleStore,
) -> None:
    """A 0007 legacy row (all bindings NULL) decodes honestly: None is
    "no source", never a fabricated stamp."""

    cp0 = commit_ok(store, conversation, "cm-dc-6", "hello")
    db.execute(
        "INSERT INTO decision_cycle (decision_cycle_id, turn_id, cycle_index,"
        " created_at) VALUES ('dcy-legacy', ?, 0, '2026-01-01T00:00:00Z')",
        (cp0.turn_id,),
    )
    db.commit()
    fetched = decision_cycle_store.get_decision_cycle("dcy-legacy")
    assert isinstance(fetched, Ok) and fetched.value is not None
    assert fetched.value.learning_snapshot_id is None
    assert fetched.value.evidence_watermark is None
    assert fetched.value.curriculum_version is None
    assert fetched.value.created_at == "2026-01-01T00:00:00Z"


def test_normal_persona_turn_opens_its_own_cycle(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
) -> None:
    """RA §4 step 5, P3-1A ②: the normal persona turn opens a cycle — with
    the all-None bindings (planner/gate/快照字段全 NULL) — and its action
    carries that cycle id (migration 0007 lineage)."""

    from elc.persona import ScriptedPersonaProvider

    from .conftest import begin_turn_ok, make_coordinator, make_lease

    provider = ScriptedPersonaProvider()
    coordinator = make_coordinator(
        store, generation_store, make_lease(_fence_of(db)), provider
    )
    completion = begin_turn_ok(coordinator, conversation, "cm-dc-normal", "hi")
    assert completion.outcome == "REPLIED_FULL"

    cycles = db.execute(
        "SELECT decision_cycle_id, cycle_index, learning_snapshot_id,"
        " evidence_watermark, planner_decision_id, gate_decision_id"
        " FROM decision_cycle WHERE turn_id = ?",
        (completion.turn_id,),
    ).fetchall()
    assert len(cycles) == 1
    assert cycles[0][1] == 0
    assert tuple(cycles[0][2:]) == (None, None, None, None)
    pointer = db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (completion.turn_id,),
    ).fetchone()
    assert pointer is not None and pointer[0] == cycles[0][0]
    action_cycle = db.execute(
        "SELECT decision_cycle_id FROM generation_action_intent"
        " WHERE turn_id = ?",
        (completion.turn_id,),
    ).fetchone()
    assert action_cycle is not None and action_cycle[0] == cycles[0][0]


def _fence_of(db: sqlite3.Connection) -> RuntimeEpochFence:
    from elc.platform.db import epoch

    current = epoch.load_current_epoch(db)
    assert current is not None
    return RuntimeEpochFence(current=current)
