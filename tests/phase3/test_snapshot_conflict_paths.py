"""VAL ⑤ — the two snapshot-CONFLICT handling points (mother decision).

PRE-cycle (before the Gate runs): the coordinator repairs the lagging
targets and re-reads; only a successful read opens a cycle. The Gate never
ran, so **no** DEGRADED row is written.

POST-cycle (the cycle's snapshot went stale after it was created, e.g. a
concurrent learning commit): the Gate reports
``GateExecutionStatus(DEGRADED)`` with ``missing_or_unknown=
[LEARNING_SNAPSHOT]`` and no GateDecision; the coordinator freezes that
cycle, opens ``cycle_index+1`` with a fresh snapshot and re-runs the Gate
once. A second degradation stops with no teaching (no Moment / Lock /
Action, no synthetic DENY) and both DEGRADED rows stay as the trace.

The Gate itself never rebuilds: it is a pure decision over facts
(elc.teaching.gate) — the repair belongs to the coordinator.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.persona import ScriptedPersonaProvider
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import ClientMessageId, Ok, TargetId
from elc.teaching.gate import GateVerdict, UserInitiatedOpenFacts
from elc.teaching.request import TeachingRequest
from tests.phase2.conftest import make_claim, make_group

from .conftest import CONV, make_lease, make_teaching_coordinator
from .target_fixtures import (
    UNAVAILABLE_TARGET_PROVIDER,
    FixtureTeachingTargetProvider,
)

REQUESTED_AT = "2026-09-21T08:00:00+00:00"
FOCUS_TARGET = "res-hedge-i-think"


def _request(client_message_id: str) -> TeachingRequest:
    return TeachingRequest(
        conversation_id=CONV,
        focus_target_id=TargetId(FOCUS_TARGET),
        client_message_id=ClientMessageId(client_message_id),
        requested_at=REQUESTED_AT,
    )


def _commit_evidence(
    learning,
    store,
    client_message_id: str,
    group_id: str,
    target_id: str = FOCUS_TARGET,
) -> str:
    """One real evidence commit from its own turn (the §6 group key is
    (source_turn_id, evidence_modality), so each side commit needs a
    turn)."""

    from tests.phase2.conftest import commit_ok

    cp0 = commit_ok(store, CONV, client_message_id, "side utterance")
    result = learning.commit_evidence_group(
        make_group(group_id, (make_claim(),), target_id=target_id),
        source_turn_id=cp0.turn_id,
        conversation_id=str(CONV),
    )
    assert isinstance(result, Ok), result
    return str(cp0.turn_id)


class CommittingTargetProvider:
    """Resolver whose first ``resolve`` call also commits learning evidence
    — the deterministic stand-in for a concurrent learning commit landing
    between cycle creation and the Gate's fact assembly.

    ``commits`` controls how many resolve calls land a commit (1 exercises
    the single-repair path, 2 the second-degradation stop).
    """

    def __init__(
        self,
        learning,
        store,
        *,
        commits: int = 1,
        inner: FixtureTeachingTargetProvider | None = None,
    ) -> None:
        self._learning = learning
        self._store = store
        self._remaining = commits
        self._counter = 0
        self._inner = inner if inner is not None else FixtureTeachingTargetProvider()

    def resolve(self, target_type: str, target_id: str):
        if self._remaining > 0:
            self._remaining -= 1
            self._counter += 1
            _commit_evidence(
                self._learning,
                self._store,
                f"cm-side-{self._counter}",
                f"eg-side-{self._counter}",
            )
        return self._inner.resolve(target_type, target_id)


def _coordinator(
    store,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    targets,
):
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycle_store,
        teaching_controller,
        targets,
    )


def _cycle_rows(db: sqlite3.Connection):
    return db.execute(
        "SELECT decision_cycle_id, cycle_index, evidence_watermark"
        " FROM decision_cycle ORDER BY cycle_index"
    ).fetchall()


def _status_rows(db: sqlite3.Connection):
    return db.execute(
        "SELECT decision_cycle_id, status, missing_or_unknown"
        " FROM gate_execution_status ORDER BY created_at,"
        " gate_execution_status_id"
    ).fetchall()


def test_pre_cycle_repair_never_writes_degraded(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """The stale projection exists BEFORE the request: the coordinator
    repairs it, opens the cycle with the fresh watermark, and the Gate
    allows. No DEGRADED row exists."""

    del conversation
    # A committed-but-not-rebuilt projection: watermark 1 → 2 with the
    # target's §11 row still stamped at 1.
    from tests.phase2.conftest import commit_ok

    del commit_ok
    _commit_evidence(learning, store, "cm-snap-seed", "eg-snap-seed")
    rebuilt = learning.rebuild_learner_state(
        TargetId(FOCUS_TARGET), "TEXT_PRODUCTION"
    )
    assert isinstance(rebuilt, Ok)
    _commit_evidence(learning, store, "cm-snap-stale", "eg-snap-stale")
    assert learning.get_evidence_watermark() == 2
    refused = learning.get_learning_snapshot()
    assert not isinstance(refused, Ok)  # the stale read refuses

    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        FixtureTeachingTargetProvider(),
    )
    result = coordinator.request_teaching(_request("cm-snap-pre"))
    assert isinstance(result, Ok), result
    assert result.value.gate_decision == "ALLOW"
    assert result.value.moment_id is not None

    # The Gate ran exactly once, after the repair: its SUCCEEDED row is
    # bound to the request's own cycle — no DEGRADED row exists anywhere
    # (the pre-cycle path never executed the Gate on a stale snapshot).
    statuses = _status_rows(db)
    assert len(statuses) == 1
    assert statuses[0][0] == result.value.decision_cycle_id
    assert statuses[0][1] == "SUCCEEDED"
    assert statuses[0][2] == "[]"
    assert db.execute(
        "SELECT COUNT(*) FROM gate_execution_status WHERE status = 'DEGRADED'"
    ).fetchone()[0] == 0
    # One cycle, stamped with the repaired watermark (2), one moment.
    cycles = _cycle_rows(db)
    assert len(cycles) == 1
    assert cycles[0][0] == result.value.decision_cycle_id
    assert cycles[0][2] == 2
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 1


def test_post_cycle_degraded_freezes_the_cycle_and_repairs_once(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """A concurrent commit lands between cycle creation and the Gate: the
    Gate degrades on LEARNING_SNAPSHOT, the coordinator freezes cycle 0,
    opens cycle 1 and re-runs the Gate — which now allows."""

    del conversation
    _commit_evidence(learning, store, "cm-snap-seed2", "eg-snap-seed2")
    assert isinstance(
        learning.rebuild_learner_state(TargetId(FOCUS_TARGET), "TEXT_PRODUCTION"),
        Ok,
    )

    provider = CommittingTargetProvider(learning, store, commits=1)
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        provider,
    )
    result = coordinator.request_teaching(_request("cm-snap-post"))
    assert isinstance(result, Ok), result
    assert result.value.gate_decision == "ALLOW"
    assert result.value.moment_id is not None

    cycles = _cycle_rows(db)
    assert [row[1] for row in cycles] == [0, 1]
    assert cycles[0][2] == 1  # the frozen cycle keeps its stamp
    assert cycles[1][2] == 2  # the repair cycle sees the advanced watermark

    statuses = _status_rows(db)
    assert [(row[1], row[2]) for row in statuses] == [
        ("DEGRADED", '["LEARNING_SNAPSHOT"]'),
        ("SUCCEEDED", "[]"),
    ]
    # The frozen cycle carries no GateDecision; the repair cycle's ALLOW
    # decision is attached to cycle 1.
    decisions = db.execute(
        "SELECT decision_cycle_id, decision FROM gate_decision"
    ).fetchall()
    assert decisions == [(cycles[1][0], "ALLOW")]
    # The turn's active cycle is the repair cycle; the moment is bound to it.
    pointer = db.execute(
        "SELECT active_decision_cycle_id FROM turn_record WHERE turn_id = ?",
        (result.value.turn_id,),
    ).fetchone()
    assert pointer is not None and pointer[0] == cycles[1][0]
    moment_cycle = db.execute(
        "SELECT decision_cycle_id FROM teaching_moment"
    ).fetchone()
    assert moment_cycle == (cycles[1][0],)


def test_second_degradation_stops_with_the_trace_only(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """A commit landing on every Gate attempt: after the single repair the
    slice stops — no Moment / Lock / Action, no synthetic DENY, and the two
    DEGRADED rows are the trace."""

    del conversation
    _commit_evidence(learning, store, "cm-snap-seed3", "eg-snap-seed3")
    assert isinstance(
        learning.rebuild_learner_state(TargetId(FOCUS_TARGET), "TEXT_PRODUCTION"),
        Ok,
    )

    provider = CommittingTargetProvider(learning, store, commits=2)
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        provider,
    )
    result = coordinator.request_teaching(_request("cm-snap-twice"))
    assert isinstance(result, Ok), result
    assert result.value.gate_execution_status == "DEGRADED"
    assert result.value.gate_decision is None
    assert result.value.missing_or_unknown == ("LEARNING_SNAPSHOT",)
    assert result.value.moment_id is None

    cycles = _cycle_rows(db)
    assert [row[1] for row in cycles] == [0, 1]  # at most one repair
    statuses = _status_rows(db)
    assert [(row[1], row[2]) for row in statuses] == [
        ("DEGRADED", '["LEARNING_SNAPSHOT"]'),
        ("DEGRADED", '["LEARNING_SNAPSHOT"]'),
    ]
    assert db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM generation_action_intent"
    ).fetchone()[0] == 0
    # The turn stays nonterminal (nothing was delivered) and carries no
    # outcome — P3-1B owns the delivery leg.
    turn = db.execute(
        "SELECT status, turn_outcome FROM turn_record WHERE turn_id = ?",
        (result.value.turn_id,),
    ).fetchone()
    assert turn == ("DECIDING", None)


def test_non_snapshot_degradation_never_burns_a_repair_cycle(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
) -> None:
    """Review F2: only a LEARNING_SNAPSHOT unknown has a repair move. An
    unknown target/content validity (resolver unavailable) is a DEGRADED
    with no repair: one cycle, one DEGRADED row, no rerun, no moment."""

    del conversation
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        UNAVAILABLE_TARGET_PROVIDER,
    )
    result = coordinator.request_teaching(_request("cm-snap-resolver"))
    assert isinstance(result, Ok), result
    assert result.value.gate_execution_status == "DEGRADED"
    assert result.value.gate_decision is None
    assert result.value.missing_or_unknown == (
        "CONTENT_VALIDITY",
        "TARGET_VALIDITY",
    )
    assert result.value.moment_id is None

    cycles = _cycle_rows(db)
    assert len(cycles) == 1
    assert cycles[0][1] == 0  # no repair cycle was opened
    statuses = _status_rows(db)
    assert len(statuses) == 1
    assert statuses[0][1] == "DEGRADED"
    assert db.execute("SELECT COUNT(*) FROM gate_decision").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM active_teaching_lock"
    ).fetchone()[0] == 0


def test_gate_profile_never_reaches_storage() -> None:
    """The Gate is a pure decision: the module imports no store and never
    calls a rebuild (the coordinator owns repair)."""

    import ast
    from pathlib import Path

    from tests.conftest import SRC_ROOT

    source = (SRC_ROOT / "teaching" / "gate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert not [m for m in modules if m.startswith("elc.platform.db")]
    assert not [m for m in modules if m.startswith("elc.learning")]
    assert "rebuild_learner_state" not in source
    assert Path("src/elc/teaching/gate.py").exists()


def test_degraded_verdict_fact_key_is_the_task_word() -> None:
    """The fact key the DEGRADED trace carries is LEARNING_SNAPSHOT (the
    §14.1 missing_or_unknown vocabulary), not a paraphrase."""

    verdict = GateVerdict(
        execution_status="DEGRADED",
        decision=None,
        primary_reason=None,
        reasons=(),
        missing_or_unknown=("LEARNING_SNAPSHOT",),
    )
    assert verdict.missing_or_unknown == ("LEARNING_SNAPSHOT",)
    facts = UserInitiatedOpenFacts(
        decision_cycle_id="dcy-x",
        candidate_id="cand-x",
        learning_snapshot_status="UNKNOWN",
    )
    assert facts.learning_snapshot_status == "UNKNOWN"
