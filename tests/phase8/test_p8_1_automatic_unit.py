"""P8-1 ③④ — the SQL-free automatic decision unit, over the durable world.

The unit is driven the only way that proves anything: a real conversation
→ CP0 turn → decision cycle (this suite's fixtures), P7-0's real record
store over a real in-memory app.db, P7-4's real kernel run for the SELECT
answer, and the real ``SqliteTeachingStore`` behind the real
``TeachingController`` for the CP2 five-fact commit.

What is asserted, in the order the unit performs it:

1. the Planner half is durable **first** (P8-0's port), so a failure there
   leaves the Gate's tables untouched;
2. only a SUCCEEDED + SELECT run reaches the Gate — ``NO_TARGET`` is a
   decision that teaches nothing, and no Gate row exists for it;
3. ALLOW commits the five facts in **one** short transaction, all five
   readable off the durable rows;
4. DENY writes two facts and no Moment / lock / action; DEGRADED writes one
   status row and **no** GateDecision;
5. a replay re-derives the same ids and the durable store recognizes them —
   and, since P8-1's disposal cut, a cycle that already has a Gate trace is
   **replayed** rather than re-decided (both directions: a durable ALLOW
   survives controls that now deny, a durable DENY survives controls that
   now allow, and neither asks the Gate);
6. the moment template's derived fields are refused, not silently
   overwritten;
7. the lock fact is the durable ``active_teaching_lock`` row's, and the
   declared critical facts make the Gate's DEGRADED answer reachable (its
   one-row trace is durable, and a torn trace is refused);
8. the module is SQL-free and imports cold.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys

import pytest

from elc.planner.shadow import run_shadow
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    DecisionCycleId,
    Err,
    Ok,
    PlannerExecutionStatusValue,
)
from elc.runtime.automatic_teaching import (
    TEACHING_OPEN_CONTRACT_ID,
    AutomaticTeachingTurn,
    TeachingControlFacts,
    automatic_action_id,
    automatic_gate_decision_id,
    automatic_gate_execution_status_id,
    automatic_moment_id,
    decide_automatic_teaching,
)
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import (
    MomentSource,
    MomentState,
    PresentationPhase,
    TeachingMomentRecord,
    TeachingSupportLevel,
    TeachingTargetRef,
)
from tests.conftest import REPO_ROOT
from tests.phase7.conftest import TARGET_ID, WATERMARK, proposal
from tests.phase8.conftest import (
    CONV,
    failed_outcome,
    request_of,
    supply_of,
    table_counts,
)

TEACHING_TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)


@pytest.fixture()
def teaching_controller(db: sqlite3.Connection, fence) -> TeachingController:
    return TeachingController(SqliteTeachingStore(db, fence))


def _moment_template(turn_id, *, overrides: dict | None = None):
    """The §15 template of the moment an ALLOW would open: the teaching
    content fields filled, and the derived fields left at their defaults
    (the unit refuses a pre-set one instead of overwriting it)."""

    base = TeachingMomentRecord(
        moment_id=automatic_moment_id(turn_id),
        conversation_id=CONV,
        persona_id=None,
        source=MomentSource.AUTOMATIC,
        decision_cycle_id=DecisionCycleId("dc-unused"),
        candidate_id="cand-unused",
        gate_decision_id=automatic_gate_decision_id(turn_id),
        focus_target=TeachingTargetRef("RESOURCE", str(TARGET_ID)),
        supporting_targets=(),
        target_mode="RESOURCE_PRACTICE",
        learning_intent="ESTABLISH",
        evidence_modality="TEXT_PRODUCTION",
        evidence_goal=None,
        preferred_support_ceiling=None,
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        content_version=None,
        policy_version=None,
        lifecycle_state=MomentState.OPENING,
        presentation_phase=PresentationPhase.INITIAL_PROMPT,
        attempt_index=0,
        support_level=TeachingSupportLevel.NONE,
        completion_outcome=None,
        abort_reason=None,
        state_version=1,
    )
    if overrides:
        from dataclasses import replace

        base = replace(base, **overrides)
    return base


#: The current test's durable connection + fence, so the builders below can
#: read the cycle row without every call site restating them. Populated by
#: the autouse fixture; emptied between tests.
_WORLD: dict[str, object] = {}


@pytest.fixture(autouse=True)
def _world(db: sqlite3.Connection, fence) -> None:
    _WORLD["db"] = db
    _WORLD["fence"] = fence
    yield
    _WORLD.clear()


def _select_run(cycle, **overrides):
    return run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id, **overrides),
        supply=supply_of(proposal("cand-p8-1")),
        current_learning_watermark=WATERMARK,
    )


def _cycle_record(cycle):
    """The durable ``decision_cycle`` row — the record the unit takes its
    bindings from (read through the real store, not restated)."""

    read = SqliteDecisionCycleStore(
        _WORLD["db"], _WORLD["fence"]  # type: ignore[arg-type]
    ).get_decision_cycle(cycle.decision_cycle_id)
    assert isinstance(read, Ok), read
    assert read.value is not None
    return read.value


def _turn(cycle, *, moment=None, epoch: int = 1):
    record = _cycle_record(cycle)
    if moment is None:
        moment = _moment_template(record.turn_id)
    return AutomaticTeachingTurn(
        turn_id=record.turn_id,
        conversation_id=CONV,
        persona_id=None,
        cycle=record,
        moment=moment,
        owner_epoch=epoch,
    )


def _decide(
    cycle,
    *,
    moment=None,
    epoch: int = 1,
    controls: TeachingControlFacts | None = None,
    outcome=None,
    store: SqlitePlannerRecordStore,
    teaching: TeachingController,
):
    cycle_record = _cycle_record(cycle)
    if moment is None:
        moment = _moment_template(cycle_record.turn_id)
    return decide_automatic_teaching(
        turn=_turn(cycle, moment=moment, epoch=epoch),
        outcome=outcome if outcome is not None else _select_run(cycle).outcome,
        controls=controls or TeachingControlFacts(),
        planner_store=store,
        teaching=teaching,
    )


# -- the ALLOW path ----------------------------------------------------------


def test_allow_opens_the_moment_and_leaves_five_durable_facts(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    decided = _decide(
        cycle, store=planner_store, teaching=teaching_controller
    )
    assert isinstance(decided, Ok), decided
    result = decided.value

    assert result.normal_persona_generation is False
    assert result.moment_id == automatic_moment_id(cycle.turn_id)
    assert result.action_id == automatic_action_id(cycle.turn_id)
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "ALLOW"

    counts = table_counts(db, *TEACHING_TABLES)
    assert counts == dict.fromkeys(TEACHING_TABLES, 1)
    # The Planner half is durable too — the same cycle's four §14 rows.
    assert table_counts(
        db, "planner_evaluation", "planner_decision", "planner_execution_status"
    ) == {
        "planner_evaluation": 1,
        "planner_decision": 1,
        "planner_execution_status": 1,
    }

    moment = db.execute(
        "SELECT moment_id, source, lifecycle_state, presentation_phase,"
        " candidate_id, decision_cycle_id, gate_decision_id, state_version"
        " FROM teaching_moment"
    ).fetchone()
    assert moment is not None
    assert moment[0] == str(result.moment_id)
    assert moment[1] == "AUTOMATIC"
    assert moment[2] == "OPENING"
    assert moment[3] == "INITIAL_PROMPT"
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "ALLOW"
    assert moment[4] == "cand-p8-1"
    assert moment[5] == str(cycle.decision_cycle_id)
    assert moment[6] == str(automatic_gate_decision_id(cycle.turn_id))
    assert moment[7] == 1

    lock = db.execute(
        "SELECT conversation_id, moment_id FROM active_teaching_lock"
    ).fetchone()
    assert lock == (str(CONV), str(result.moment_id))
    action = db.execute(
        "SELECT action_type, generation_contract_id, status, moment_id"
        " FROM generation_action_intent"
    ).fetchone()
    assert action == (
        "TEACHING_OPEN",
        TEACHING_OPEN_CONTRACT_ID,
        "PREPARED",
        str(result.moment_id),
    )
    gate = db.execute(
        "SELECT context, decision, reason_codes FROM gate_decision"
    ).fetchone()
    assert gate == ("OPEN", "ALLOW", "[]")
    status = db.execute(
        "SELECT gate_context, authorization_basis, status FROM"
        " gate_execution_status"
    ).fetchone()
    assert status == ("OPEN", "DECISION_CYCLE", "SUCCEEDED")

    # … and the durable rows read back through the domain faces too.
    stored = teaching_controller.get_moment(result.moment_id)
    assert isinstance(stored, Ok) and stored.value is not None
    assert stored.value.source is MomentSource.AUTOMATIC


def test_the_planner_half_is_durable_before_the_gate_is_asked(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """The unit's first write is P8-0's; the Gate's own rows are the
    second. Read in between: the Planner records exist while no teaching
    table does — the crash window RA §23 describes for CP1→CP2."""

    recorded = planner_store.record_planner_cycle(
        turn_id=cycle.turn_id, outcome=_select_run(cycle).outcome
    )
    assert isinstance(recorded, Ok)
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 0
    )
    assert planner_store.get_planner_decision_for_cycle(
        cycle.decision_cycle_id
    ).value is not None


# -- the three arms that teach nothing ---------------------------------------


def test_a_no_target_run_never_reaches_the_gate_or_the_moment_tables(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    shadow = run_shadow(
        request_of(decision_cycle_id=cycle.decision_cycle_id),
        supply=supply_of(),
        current_learning_watermark=WATERMARK,
    )
    assert shadow.decision is not None and shadow.decision.value == "NO_TARGET"

    decided = _decide(
        cycle,
        outcome=shadow.outcome,
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is None
    assert result.moment_id is None
    assert result.action_id is None
    assert result.normal_persona_generation is True
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 0
    )
    # … and the Planner decision is still durable (the run *was* a run).
    assert result.planner_records.decision is not None


def test_a_denied_open_writes_only_the_two_gate_facts(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    decided = _decide(
        cycle,
        controls=TeachingControlFacts(automatic_teaching_enabled=False),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.primary_reason == "AUTO_TEACH_DISABLED"
    assert result.moment_id is None
    assert result.normal_persona_generation is True

    assert table_counts(
        db, "gate_execution_status", "gate_decision"
    ) == {"gate_execution_status": 1, "gate_decision": 1}
    assert table_counts(
        db,
        "teaching_moment",
        "active_teaching_lock",
        "generation_action_intent",
    ) == {
        "teaching_moment": 0,
        "active_teaching_lock": 0,
        "generation_action_intent": 0,
    }
    row = db.execute("SELECT decision, reason_codes FROM gate_decision").fetchone()
    assert row == ("DENY", '["AUTO_TEACH_DISABLED"]')
    # The Planner half is durable on the DENY arm too (P8-0's four §14 rows;
    # the review's m7 mutation: without this the DENY arm never asserted it).
    assert table_counts(
        db, "planner_evaluation", "planner_decision", "planner_execution_status"
    ) == {
        "planner_evaluation": 1,
        "planner_decision": 1,
        "planner_execution_status": 1,
    }
    assert result.planner_records.decision is not None
    assert planner_store.get_planner_decision_for_cycle(
        cycle.decision_cycle_id
    ).value is not None


def test_a_degraded_run_writes_one_status_row_and_no_decision(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """A run the *assembly* degraded: P8-0 persists a status row and no
    decision, and the unit stops before the Gate — there is no run whose
    admissibility could be asked about, so no GateExecutionStatus and no
    GateDecision exist either."""

    degraded = failed_outcome(
        cycle.decision_cycle_id, PlannerExecutionStatusValue.DEGRADED
    )
    decided = _decide(
        cycle,
        outcome=degraded,
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is None
    assert result.moment_id is None
    assert result.normal_persona_generation is True
    assert result.planner_records.decision is None
    assert result.planner_records.execution_status.status is (
        PlannerExecutionStatusValue.DEGRADED
    )
    assert table_counts(
        db, "gate_execution_status", "gate_decision"
    ) == {"gate_execution_status": 0, "gate_decision": 0}
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 0
    )
    # … and the durable Planner rows are exactly the degraded trace.
    assert table_counts(
        db, "planner_evaluation", "planner_execution_status", "planner_decision"
    ) == {
        "planner_evaluation": 1,
        "planner_execution_status": 1,
        "planner_decision": 0,
    }


def test_a_planner_record_failure_stops_before_the_gate(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """The Planner half is the unit's first act: when it refuses, nothing
    downstream happened at all."""

    decided = decide_automatic_teaching(
        turn=_turn(cycle),
        outcome=_select_run(cycle).outcome,
        controls=TeachingControlFacts(),
        planner_store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Ok), decided
    # A second, contradictory submission of the same cycle is refused by
    # P8-0's replay contract (judgement 3) …
    replay = decide_automatic_teaching(
        turn=_turn(cycle),
        outcome=failed_outcome(
            cycle.decision_cycle_id, PlannerExecutionStatusValue.FAILED
        ),
        controls=TeachingControlFacts(),
        planner_store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(replay, Err)
    # … and the first call's teaching rows are the only ones there are.
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 1
    )


# -- the durable lock fact and the declared critical facts (F4) --------------


def test_a_foreign_lock_in_the_conversation_denies_the_automatic_open(
    db: sqlite3.Connection,
    fence,
    cycle,
    other_turn,
    planner_store,
    teaching_controller,
) -> None:
    """F4(i): the lock fact is BF-03 §14's — the durable
    ``active_teaching_lock`` row's — not a hard-coded ``NONE``.

    The world is built the honest way: a second turn in the same conversation
    gets its own cycle and its own automatic opening (the only face that
    takes the lock), and *then* the first cycle's turn is decided — it must
    see ``OWNED_BY_OTHER`` and deny, with zero teaching rows of its own."""

    from elc.conversation import SqliteConversationStore
    from tests.phase8.conftest import open_cycle

    turn_read = SqliteConversationStore(db, fence).get_turn_record(other_turn)
    assert isinstance(turn_read, Ok) and turn_read.value is not None
    other = open_cycle(
        db,
        fence,
        decision_cycle_id=DecisionCycleId("dc-p8-1-lock"),
        turn_id=other_turn,
        expected_turn_state_version=turn_read.value.state_version,
    )
    opened = _decide(other, store=planner_store, teaching=teaching_controller)
    assert isinstance(opened, Ok), opened
    assert opened.value.moment_id is not None  # … and CONV is now locked

    decided = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "DENY"
    assert result.gate_verdict.primary_reason == "TEACHING_LOCK_CONFLICT"
    assert result.gate_verdict.reasons == ("TEACHING_LOCK_CONFLICT",)
    assert result.moment_id is None
    assert result.normal_persona_generation is True
    # Zero rows of its own: the cycle's only gate fact is the DENY, and the
    # conversation's one moment / lock / action are the *other* turn's.
    assert table_counts(db, "teaching_moment", "active_teaching_lock",
                        "generation_action_intent") == {
        "teaching_moment": 1,
        "active_teaching_lock": 1,
        "generation_action_intent": 1,
    }
    mine = db.execute(
        "SELECT COUNT(*) FROM teaching_moment WHERE decision_cycle_id = ?",
        (str(cycle.decision_cycle_id),),
    ).fetchone()
    assert mine == (0,)
    row = db.execute(
        "SELECT decision FROM gate_decision WHERE decision_cycle_id = ?",
        (str(cycle.decision_cycle_id),),
    ).fetchone()
    assert row == ("DENY",)


def test_a_degraded_gate_answer_is_reachable_and_durable(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """F4(ii): with the critical facts on the caller's record, ``UNKNOWN`` is
    expressible — so the Gate's DEGRADED answer (unreachable while every
    critical fact was hard-coded healthy: the review's m11 mutation deleted
    its write and the suite stayed green) has an asserting test.

    The durable trace is one status row and **no** GateDecision; the
    re-entry direction is its own test below."""

    decided = _decide(
        cycle,
        controls=TeachingControlFacts(gate_state_status="INCOMPLETE"),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.execution_status == "DEGRADED"
    assert result.gate_verdict.decision is None
    assert result.gate_verdict.missing_or_unknown == ("GATE_STATE",)
    assert result.moment_id is None
    assert result.action_id is None
    assert result.normal_persona_generation is True
    assert table_counts(db, *TEACHING_TABLES) == {
        "gate_execution_status": 1,
        "gate_decision": 0,
        "teaching_moment": 0,
        "active_teaching_lock": 0,
        "generation_action_intent": 0,
    }
    row = db.execute(
        "SELECT status, missing_or_unknown FROM gate_execution_status"
    ).fetchone()
    assert row == ("DEGRADED", '["GATE_STATE"]')


def test_a_durable_degraded_status_is_replayed_when_the_facts_recover(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller, monkeypatch
) -> None:
    """F1's rule applied to the third durable shape: after a DEGRADED
    answer, a re-entry whose facts are healthy again replays the durable
    degradation — it neither re-decides (which would insert a second status
    row and hit the store's bare unique-constraint CONFLICT, F12) nor
    launders the missing decision into an ALLOW."""

    import elc.runtime.automatic_teaching as unit

    first = _decide(
        cycle,
        controls=TeachingControlFacts(gate_state_status="INCOMPLETE"),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(first, Ok), first

    monkeypatch.setattr(
        unit, "decide_automatic_open", _forbid("decide_automatic_open")
    )
    monkeypatch.setattr(
        teaching_controller,
        "record_gate_degraded",
        _forbid("record_gate_degraded"),
    )
    replay = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(replay, Ok), replay
    replayed = replay.value
    assert replayed.gate_verdict is not None
    assert replayed.gate_verdict.execution_status == "DEGRADED"
    assert replayed.gate_verdict.decision is None
    assert replayed.gate_verdict.missing_or_unknown == ("GATE_STATE",)
    assert replayed.moment_id is None
    assert replayed.normal_persona_generation is True
    assert table_counts(db, *TEACHING_TABLES) == {
        "gate_execution_status": 1,
        "gate_decision": 0,
        "teaching_moment": 0,
        "active_teaching_lock": 0,
        "generation_action_intent": 0,
    }


def test_the_declared_authorization_fact_reaches_the_durable_status_row(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """The declared critical facts are passed to the Gate **and** written to
    the §14.1 status row — the user-initiated path's own reading
    (``authorization_status=facts.authorization_status`` in
    ``elc.runtime.controller``). A durable row must never claim ``VALID``
    for a fact the caller declared unknown, or the trace would lie about
    the very fact whose unknown-ness degraded it."""

    decided = _decide(
        cycle,
        controls=TeachingControlFacts(authorization_status="UNKNOWN"),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Ok), decided
    result = decided.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.execution_status == "DEGRADED"
    assert result.gate_verdict.missing_or_unknown == ("AUTHORIZATION_STATUS",)
    row = db.execute(
        "SELECT status, authorization_status, missing_or_unknown FROM"
        " gate_execution_status"
    ).fetchone()
    assert row == ("DEGRADED", "UNKNOWN", '["AUTHORIZATION_STATUS"]')
    assert table_counts(db, "gate_decision") == {"gate_decision": 0}


def test_a_torn_succeeded_status_is_refused_not_repaired(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """The third durable shape: a ``SUCCEEDED`` status row with no
    GateDecision.

    No face in this repository writes that — CP2 and both record faces write
    a SUCCEEDED status together with its decision, in one short transaction —
    so the row is written here directly, the way
    ``tests/phase8/test_p8_0_reads.py`` pins a read shape its world cannot
    otherwise establish. The unit must neither ask the Gate again (which
    would insert a second, contradictory fact) nor invent the missing
    decision: it refuses and writes nothing."""

    db.execute(
        "INSERT INTO gate_execution_status ("
        " gate_execution_status_id, decision_cycle_id, moment_id,"
        " gate_context, authorization_basis, authorization_status, status,"
        " missing_or_unknown, created_at"
        ") VALUES (?, ?, NULL, 'OPEN', 'DECISION_CYCLE', 'VALID',"
        " 'SUCCEEDED', '[]', 'now')",
        (
            automatic_gate_execution_status_id(cycle.turn_id),
            str(cycle.decision_cycle_id),
        ),
    )
    db.commit()  # the row is durable state, not a pending transaction
    decided = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(decided, Err), decided
    assert "torn" in decided.error.message
    assert table_counts(db, *TEACHING_TABLES) == {
        "gate_execution_status": 1,
        "gate_decision": 0,
        "teaching_moment": 0,
        "active_teaching_lock": 0,
        "generation_action_intent": 0,
    }


# -- replay ------------------------------------------------------------------


def test_a_second_call_on_the_same_cycle_does_not_overwrite_the_moment(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """A literal re-entry of one cycle: the Planner half replays (P8-0's
    judgement 2), the cycle's Gate trace is replayed **without asking the
    Gate again** (F1's repair), and the answer names the durable moment
    rather than a second one — the durable ``(moment, first action)`` pair
    is canonical.

    ``action_id`` is ``None`` on this path: a replay reports no action id,
    because this unit's declared teaching surface has no action read (the
    durable action is read through ``GenerationStore.get_action_for_turn``,
    the coordinator's own replay face). The first call still derives and
    returns the id it wrote."""

    first = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(first, Ok)
    assert first.value.action_id == automatic_action_id(cycle.turn_id)
    second = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(second, Ok), second
    result = second.value
    assert result.moment_id == automatic_moment_id(cycle.turn_id)
    assert result.moment_id == first.value.moment_id
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "ALLOW"
    assert result.action_id is None
    assert result.normal_persona_generation is False
    assert table_counts(
        db, "teaching_moment", "active_teaching_lock"
    ) == {"teaching_moment": 1, "active_teaching_lock": 1}
    assert table_counts(db, *TEACHING_TABLES) == {
        "gate_execution_status": 1,
        "gate_decision": 1,
        "teaching_moment": 1,
        "active_teaching_lock": 1,
        "generation_action_intent": 1,
    }


def _forbid(name: str):
    """A stand-in that fails the test the moment it is called."""

    def _refuse(*args, **kwargs):
        raise AssertionError(f"{name} was called on a replay")

    return _refuse


def test_a_durable_allow_is_replayed_even_when_the_new_controls_deny(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller, monkeypatch
) -> None:
    """F1's first direction: after a durable ALLOW, a re-entry whose fresh
    facts say DENY answers with the durable ALLOW — the moment stays, zero
    new rows, and the Gate is never asked (the stub asserts that, not the
    row counts)."""

    import elc.runtime.automatic_teaching as unit

    first = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(first, Ok) and first.value.moment_id is not None

    monkeypatch.setattr(
        unit, "decide_automatic_open", _forbid("decide_automatic_open")
    )
    monkeypatch.setattr(
        teaching_controller, "commit_cp2_open", _forbid("commit_cp2_open")
    )
    monkeypatch.setattr(
        teaching_controller, "record_gate_denial", _forbid("record_gate_denial")
    )
    monkeypatch.setattr(
        teaching_controller,
        "record_gate_degraded",
        _forbid("record_gate_degraded"),
    )

    second = _decide(
        cycle,
        controls=TeachingControlFacts(automatic_teaching_enabled=False),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(second, Ok), second
    result = second.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "ALLOW"
    assert result.gate_verdict.reasons == ()
    assert result.moment_id == first.value.moment_id
    assert result.normal_persona_generation is False
    # Zero new rows: every teaching table holds exactly the first call's one.
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 1
    )
    stored = db.execute(
        "SELECT decision FROM gate_decision"
    ).fetchone()
    assert stored == ("ALLOW",)  # the durable fact, untouched


def test_a_durable_deny_is_replayed_instead_of_conflicting(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller, monkeypatch
) -> None:
    """F1's second direction: after a durable DENY, a re-entry whose fresh
    facts say ALLOW answers with the durable DENY, writes nothing, and does
    **not** reach the CP2 unit's unique-constraint path (the store's bare
    ``UNIQUE constraint failed: gate_execution_status...`` CONFLICT, F12) —
    the commit faces and the Gate are stubbed to fail if called."""

    import elc.runtime.automatic_teaching as unit

    first = _decide(
        cycle,
        controls=TeachingControlFacts(automatic_teaching_enabled=False),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(first, Ok), first
    assert first.value.gate_verdict is not None
    assert first.value.gate_verdict.decision == "DENY"

    monkeypatch.setattr(
        unit, "decide_automatic_open", _forbid("decide_automatic_open")
    )
    monkeypatch.setattr(
        teaching_controller, "commit_cp2_open", _forbid("commit_cp2_open")
    )
    monkeypatch.setattr(
        teaching_controller, "record_gate_denial", _forbid("record_gate_denial")
    )
    monkeypatch.setattr(
        teaching_controller,
        "record_gate_degraded",
        _forbid("record_gate_degraded"),
    )

    # The healthy defaults would compute ALLOW if the unit re-decided.
    second = _decide(cycle, store=planner_store, teaching=teaching_controller)
    assert isinstance(second, Ok), second
    result = second.value
    assert result.gate_verdict is not None
    assert result.gate_verdict.decision == "DENY"
    assert result.gate_verdict.primary_reason == "AUTO_TEACH_DISABLED"
    assert result.gate_verdict.reasons == ("AUTO_TEACH_DISABLED",)
    assert result.moment_id is None
    assert result.action_id is None
    assert result.normal_persona_generation is True
    assert table_counts(
        db, "gate_execution_status", "gate_decision"
    ) == {"gate_execution_status": 1, "gate_decision": 1}
    assert table_counts(
        db,
        "teaching_moment",
        "active_teaching_lock",
        "generation_action_intent",
    ) == {
        "teaching_moment": 0,
        "active_teaching_lock": 0,
        "generation_action_intent": 0,
    }


def test_a_fenced_epoch_writes_nothing(
    db: sqlite3.Connection, cycle, planner_store, teaching_controller
) -> None:
    """A stale epoch is refused by the CP2 unit's own fence: five facts or
    none, and here it is none — the planner half stays (it already
    committed in this world)."""

    decided = _decide(
        cycle, epoch=99, store=planner_store, teaching=teaching_controller
    )
    assert isinstance(decided, Err), decided
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 0
    )


# -- the template refusals ---------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"source": MomentSource.MANUAL_FOCUS},
        {"lifecycle_state": MomentState.AWAITING_USER},
        {"presentation_phase": PresentationPhase.HINT_SEMANTIC},
        {"moment_id": "tm-somewhere-else"},
        {"conversation_id": "conv-somewhere-else"},
    ],
)
def test_a_template_that_pre_empts_a_derived_field_is_refused_before_writing(
    db: sqlite3.Connection,
    cycle,
    planner_store,
    teaching_controller,
    overrides: dict,
) -> None:
    decided = _decide(
        cycle,
        moment=_moment_template(cycle.turn_id, overrides=overrides),
        store=planner_store,
        teaching=teaching_controller,
    )
    assert isinstance(decided, Err), decided
    assert table_counts(db, *TEACHING_TABLES) == dict.fromkeys(
        TEACHING_TABLES, 0
    )
    # The Planner half did commit — the refusal happens at the CP2 step,
    # which is where the template is read.
    assert planner_store.get_planner_decision_for_cycle(
        cycle.decision_cycle_id
    ).value is not None


# -- the module's own honesty ------------------------------------------------


def test_the_opening_contract_id_is_the_coordinators_own_value() -> None:
    """The mirrored constant: ``elc.runtime.controller`` declares the CP2
    opening contract and this module declares it again (neither may import
    the other's package face); the equality is held here, exactly like the
    ``CONVERSATION_WINDOW_MAX_TURNS`` pair."""

    import elc.runtime.automatic_teaching as unit
    import elc.runtime.controller as controller

    assert unit.TEACHING_OPEN_CONTRACT_ID == controller.TEACHING_OPEN_CONTRACT_ID
    assert controller.TEACHING_CONTRACT_BY_ACTION["TEACHING_OPEN"] == (
        TEACHING_OPEN_CONTRACT_ID
    )


def test_the_module_is_sql_free_and_imports_cold() -> None:
    """RA §4's split held at the level this cut owns: the unit carries no
    SQL machinery of its own — no ``sqlite3`` / ``elc.platform.db`` import,
    no DB call surface — and it imports in a cold interpreter.

    The transitive closure is **not** SQL-free, and saying so is part of the
    finding: ``elc.teaching.gate`` is reached through the ``elc.teaching``
    package, whose ``__init__`` (P3-1B's face sync) eagerly imports the
    teaching controller and therefore the teaching store; and
    ``elc.runtime.decision_cycles`` imports ``elc.platform.db.epoch``/``tx``
    (the Runtime-owned cycle port's pre-existing shape). Both predate this
    cut; Gate item 2 pins the runtime package at the *direct* import level
    precisely because the transitive one is already dirty. What this cut
    adds is the two deferred ``elc.teaching.store`` imports inside its
    helpers, so the unit's own import-time surface stays free of the store
    (the package's is not)."""

    import ast

    source = (
        REPO_ROOT / "src" / "elc" / "runtime" / "automatic_teaching.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "sqlite3" not in imported
    assert not [name for name in imported if name.startswith("elc.platform.db")]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "execute",
                "executemany",
                "executescript",
                "commit",
                "rollback",
            }, node.func.attr

    program = "\n".join(
        [
            "import os, sys",
            "ROOT = os.environ['ROOT']",
            "sys.path[:0] = [os.path.join(ROOT, 'src'), ROOT]",
            "import elc.runtime.automatic_teaching as m",
            "assert m.decide_automatic_teaching is not None",
            "assert m.TEACHING_OPEN_CONTRACT_ID == 'gc-teaching-open'",
            "print('COLD-AUTOMATIC')",
        ]
    )
    env = dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1", ROOT=str(REPO_ROOT)
    )
    proc = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    assert "COLD-AUTOMATIC" in proc.stdout


def test_the_unit_is_not_wired_into_the_coordinator_yet() -> None:
    """The boundary P8-1 declares: the ordinary turn's planner → gate →
    moment connection (and the ``EphemeralTeachingDirective`` / prompt /
    delivery legs) is p8-4's. The coordinator must not import this module
    until that cut lands."""

    controller_source = (
        REPO_ROOT / "src" / "elc" / "runtime" / "controller.py"
    ).read_text(encoding="utf-8")
    assert "automatic_teaching" not in controller_source
    assert "decide_automatic_teaching" not in controller_source
