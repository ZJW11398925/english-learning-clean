"""Phase 8 tests — the P8-0 world: a durable cycle and the CP2 unit over it.

The chain this suite drives is the shipped one and nothing else: migrations
into an in-memory app.db, an opened runtime epoch, the conversation store's
real CP0 commit (a user turn), the Runtime-owned DecisionCycle store's real
cycle row, this cut's CP2 unit, and the deletion suite's durable executor for
the removal half. No ``_seed``-shaped helper exists here and no fixture target
provider is imported (the P5-1 red line, held by phase 6, phase 7 and this
suite).

Two groups of things are borrowed, and the split is deliberate:

- the **fixtures** the kernel work needs (``db`` / ``fence``) are declared
  here rather than imported from tests.phase7.conftest — four lines each, and
  a conftest that imports another phase's *fixture functions* would tie the
  two suites' collection together (phase 7's own note: a phase's assertions
  should own their world);
- the **builders** the kernel needs (``proposal`` / ``learning_snapshot`` /
  ``schedule_item`` / ``portfolio`` / ``teaching_policy`` / ``constraint``)
  are P7's, imported as plain functions: they are BF-02 §20's frozen inputs,
  and re-spelling them here would be a second copy of a frozen vector.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterator

import pytest

from elc.conversation import SqliteConversationStore
from elc.conversation.types import CommitUserTurn
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.planner.candidates import CandidateSupply
from elc.planner.scope import ScopeResolution
from elc.planner.types import (
    PlannerEvaluation,
    PlanningOutcome,
    PlanningRequest,
    UserIntentScope,
)
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    ClientMessageId,
    DecisionCycleId,
    InputId,
    InteractionChannel,
    Ok,
    PlannerEvaluationId,
    PlannerExecutionStatusRecord,
    PlannerExecutionStatusValue,
    PlannerVersion,
    PolicyVersion,
    TurnId,
)
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.types import InputEnvelope
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from tests.conftest import (
    DOCS_ROOT,
    REPO_ROOT,
    SRC_ROOT,
)
from tests.phase7.conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    TARGET_ID,
    USER,
    WATERMARK,
    constraint,
    kernel_row,
    learning_snapshot,
    portfolio,
    proposal,
    schedule_item,
    schedule_view,
    teaching_policy,
)

__all__ = [
    "CONV",
    "DAY_ONE",
    "DAY_THREE",
    "DAY_TWO",
    "DOCS_ROOT",
    "REPO_ROOT",
    "SRC_ROOT",
    "TARGET_ID",
    "USER",
    "WATERMARK",
    "CycleWorld",
    "canonical_blocks_verbatim",
    "columns_and_vocabulary",
    "constraint",
    "cycle",
    "db",
    "failed_outcome",
    "fence",
    "kernel_row",
    "learning_controller",
    "learning_snapshot",
    "open_cycle",
    "other_turn",
    "planner_store",
    "portfolio",
    "proposal",
    "request_of",
    "schedule_item",
    "schedule_view",
    "scheduler_store",
    "second_cycle",
    "supply_of",
    "table_counts",
    "teaching_policy",
    "user_config_controller",
    "user_config_store",
    "wired_scheduler",
]

CONVERSATION_TURN = "I think we should rehearse that once more."

RUNTIME_VERSION = "runtime-p8-0"

#: The turn the P8-0 world commits and the cycle it opens, plus a second
#: turn with **no** cycle (the shape §14's ``decision_cycle_id?`` is for).
TURN_ID = TurnId("turn-p8-0")
OTHER_TURN_ID = TurnId("turn-p8-0-other")
CYCLE_ID = DecisionCycleId("dc-p8-0")
SECOND_CYCLE_ID = DecisionCycleId("dc-p8-0-b")

RECEIVED_AT = "2026-09-23T09:00:00+00:00"


# -- the world ---------------------------------------------------------------


@pytest.fixture()
def db() -> Iterator[sqlite3.Connection]:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture()
def fence(db: sqlite3.Connection) -> RuntimeEpochFence:
    return epoch.open_runtime_epoch(db)


@dataclass(frozen=True)
class CycleWorld:
    """One durable conversation → turn → decision cycle, through the real
    faces (no fixture row is hand-written).

    ``state_version`` is the turn's state_version **after** the cycle opened —
    what a second cycle of the same turn has to pass as its CAS expectation.
    """

    turn_id: TurnId
    decision_cycle_id: DecisionCycleId
    state_version: int


def open_cycle(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    *,
    decision_cycle_id: DecisionCycleId,
    turn_id: TurnId,
    expected_turn_state_version: int,
) -> CycleWorld:
    """Open one more cycle on an existing turn (the real DecisionCycle unit).

    A test that needs more than the two cycles the fixtures hand out calls
    this with the previous cycle's ``state_version`` — the CAS the durable
    turn row demands, not a fixture shortcut.
    """

    bindings = DecisionCycleBindings(
        learning_snapshot_id=None,
        evidence_watermark=None,
        curriculum_version=None,
        goal_version=None,
        schedule_version=None,
        policy_version=None,
        context_view_version=None,
        relationship_view_version=None,
    )
    recorded = SqliteDecisionCycleStore(db, fence).record_decision_cycle(
        decision_cycle_id=decision_cycle_id,
        turn_id=turn_id,
        bindings=bindings,
        expected_turn_state_version=expected_turn_state_version,
    )
    assert isinstance(recorded, Ok), recorded
    return CycleWorld(
        turn_id=turn_id,
        decision_cycle_id=decision_cycle_id,
        # the cycle unit's TurnRecord CAS bumps the turn's state_version once
        state_version=expected_turn_state_version + 1,
    )


@pytest.fixture()
def cycle(db: sqlite3.Connection, fence: RuntimeEpochFence) -> CycleWorld:
    """Conversation → CP0 turn → one decision cycle, all through real faces.

    The conversation row comes first because §5.1-style rows and the cycle's
    own FK require it (migration 0002/0006); the turn is the conversation
    store's own CP0 unit, so its ``state_version`` is the durable CAS value a
    second cycle has to satisfy.
    """

    opened = SqliteConversationStore(db, fence).open_conversation(
        CONV, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(opened, Ok), opened
    commit = SqliteConversationStore(db, fence).commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId("in-p8-0"),
                client_message_id=ClientMessageId("cmid-p8-0"),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-p8-0",
                received_at=RECEIVED_AT,
            ),
            raw_content=CONVERSATION_TURN,
            runtime_version=RUNTIME_VERSION,
            turn_id=TURN_ID,
        )
    )
    assert isinstance(commit, Ok), commit
    return open_cycle(
        db,
        fence,
        decision_cycle_id=CYCLE_ID,
        turn_id=commit.value.turn_id,
        expected_turn_state_version=commit.value.state_version,
    )


@pytest.fixture()
def other_turn(
    db: sqlite3.Connection, fence: RuntimeEpochFence, cycle: CycleWorld
) -> TurnId:
    """One more CP0 turn in the same conversation, with **no** cycle — the
    turn shape a §14 outcome row's optional ``decision_cycle_id`` describes.
    """

    commit = SqliteConversationStore(db, fence).commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId("in-p8-0-other"),
                client_message_id=ClientMessageId("cmid-p8-0-other"),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-p8-0-other",
                received_at=RECEIVED_AT,
            ),
            raw_content="A second turn with no decision cycle.",
            runtime_version=RUNTIME_VERSION,
            turn_id=OTHER_TURN_ID,
        )
    )
    assert isinstance(commit, Ok), commit
    return commit.value.turn_id


@pytest.fixture()
def second_cycle(
    db: sqlite3.Connection, fence: RuntimeEpochFence, cycle: CycleWorld
) -> CycleWorld:
    """A **second** cycle on the same turn — the same-turn replan shape (§4's
    ``cycle_index`` arithmetic; STATE_MACHINES §11's explicit target switch).
    """

    return open_cycle(
        db,
        fence,
        decision_cycle_id=SECOND_CYCLE_ID,
        turn_id=cycle.turn_id,
        expected_turn_state_version=cycle.state_version,
    )


@pytest.fixture()
def planner_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqlitePlannerRecordStore:
    return SqlitePlannerRecordStore(db, fence)


@pytest.fixture()
def learning_controller(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> LearningController:
    return LearningController(SqliteLearningStore(db, fence))


@pytest.fixture()
def scheduler_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteSchedulerStore:
    return SqliteSchedulerStore(db, fence)


@pytest.fixture()
def wired_scheduler(
    scheduler_store: SqliteSchedulerStore,
    learning_controller: LearningController,
) -> SchedulerController:
    """The Scheduler face wired to the real Learning watermark read."""

    return SchedulerController(scheduler_store, learning=learning_controller)


@pytest.fixture()
def user_config_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteUserConfigStore:
    return SqliteUserConfigStore(db, fence)


@pytest.fixture()
def user_config_controller(
    user_config_store: SqliteUserConfigStore,
) -> UserConfigController:
    return UserConfigController(user_config_store)


# -- the kernel inputs (P7's builders, P7-4's request shape) ------------------


def supply_of(
    *proposals: object, readiness: str = "R3_TEACHING_READY"
) -> CandidateSupply:
    """P7-2's own answer for a cycle: proposals, their targets' §8.1 levels,
    and the §12 resolution (P7-4's builder, kept in shape)."""

    built = tuple(proposals)
    targets = {getattr(item, "focus_target") for item in built}
    return CandidateSupply(
        proposals=built,  # type: ignore[arg-type]
        gaps=(),
        refusals=(),
        readiness={target: readiness for target in sorted(targets)},
        scope=ScopeResolution(
            scope=UserIntentScope.OPEN,
            request_targets=(),
            reasons=(),
            constraint_view_present=True,
        ),
    )


def request_of(**overrides: object) -> PlanningRequest:
    """One view-complete PlanningRequest for one durable cycle."""

    bag: dict[str, object] = {
        "decision_cycle_id": CYCLE_ID,
        "learning_snapshot": learning_snapshot(),
        "curriculum_candidate_view": None,
        "schedule_view": schedule_view(kernel_row()),
        "goal_view": portfolio(assessment_targets=()),
        "teaching_policy_view": teaching_policy(),
        "context_opportunity_set": None,
        "planner_constraint_view": constraint(),
        "session_budget_view": None,
        "user_intent_scope": UserIntentScope.OPEN,
        "conversation_priority_view": None,
        "planning_ledger": None,
    }
    bag.update(overrides)
    return PlanningRequest(**bag)  # type: ignore[arg-type]


def failed_outcome(
    decision_cycle_id: DecisionCycleId,
    status: PlannerExecutionStatusValue,
    *,
    error_code: str | None = "STORE_UNREADABLE",
) -> PlanningOutcome:
    """One *constructed* degraded outcome (FAILED / UNAVAILABLE).

    P7-0's assembly answers SUCCEEDED or DEGRADED and nothing else
    (``execution_status_of``: FAILED / UNAVAILABLE are "the execution's own
    failures, not assembly verdicts"). A failure that happened *outside* the
    assembly is therefore a record a caller holds, not something a kernel run
    can produce — this builder is that caller, and it fabricates nothing the
    kernel would have: the evaluation is the honest empty trace of a run that
    did not get to rank anything, and there is no decision (§14 line 889).
    """

    return PlanningOutcome(
        evaluation=PlannerEvaluation(
            planner_evaluation_id=PlannerEvaluationId(
                f"pe-{decision_cycle_id}"
            ),
            decision_cycle_id=decision_cycle_id,
            planner_version=PlannerVersion("planner-p8-0"),
            policy_version=PolicyVersion("policy-p8-0"),
            ranked_candidates=(),
            reason_trace=(f"p8-0: execution failure ({status.value})",),
            frontier_candidate_ids=(),
        ),
        execution_status=PlannerExecutionStatusRecord(
            decision_cycle_id=decision_cycle_id,
            status=status,
            error_code=error_code,
        ),
        decision=None,
    )


def table_counts(db: sqlite3.Connection, *tables: str) -> dict[str, int]:
    """Row counts read from the database (never predicted)."""

    return {
        table: int(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
        for table in tables
    }


# ---------------------------------------------------------------------------
# Canonical-document reader (re-declared: this suite's own extraction pins)
# ---------------------------------------------------------------------------
#
# Phase 7's reader strips whitespace off every fenced line, and the two §14
# blocks this cut turns into tables **interleave their vocabulary with the
# column list** — the vocabulary lines are indented, and stripping them would
# make the words indistinguishable from column names. The reader here keeps
# the raw lines, so the filter that separates the two is explicit and can
# itself be pinned.

_FENCE = "```"


def canonical_blocks_verbatim(doc: str, heading: str) -> list[tuple[str, ...]]:
    """Every fenced block after ``heading`` in ``docs/<doc>``, raw lines.

    Blank lines are dropped; leading whitespace is **kept** (the one
    difference from tests.phase7.conftest's reader, and the reason this one
    exists).
    """

    lines = (DOCS_ROOT / doc).read_text(encoding="utf-8").splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"heading {heading!r} not found"
    blocks: list[tuple[str, ...]] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            head_level = len(stripped) - len(stripped.lstrip("#"))
            if head_level <= level and stripped[: head_level + 1].endswith(" "):
                break
        if lines[index].startswith(_FENCE):
            body: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith(_FENCE):
                if lines[index].strip():
                    body.append(lines[index])
                index += 1
            if body:
                blocks.append(tuple(body))
        index += 1
    assert blocks, f"{heading!r}: no fenced block"
    return blocks


def columns_and_vocabulary(
    block: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split one §14 block into its column list and its indented vocabulary.

    The filter is "an indented line is a vocabulary word, a flush line is a
    column" — the shape §14's PlannerExecutionStatus and RuntimeDecisionOutcome
    blocks actually have. A block whose indentation changed would fail the
    caller's comparison (a vocabulary word would appear among the columns, or
    a column among the words), which is what makes the filter checkable rather
    than convenient.
    """

    columns = tuple(line.strip() for line in block if not line[:1].isspace())
    vocabulary = tuple(line.strip() for line in block if line[:1].isspace())
    return columns, vocabulary


