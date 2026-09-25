"""The P8-4 test world (this cut's own; no other phase's fixture is imported).

One ordinary turn with the automatic leg wired, over the shipped chain and
nothing else: migrations into an in-memory app.db, an opened runtime epoch,
the real stores (conversation / generation / teaching / planner / ledger /
learning / scheduler / user-config), the repository's own ``content.db`` built
from its authoring trees, and the coordinator with the optional wiring bundle.
No ``_seed``-shaped helper exists here and the Phase 3 fixture target provider
is never imported (the P5-1 red line, held by phases 6/7/8).

**Two kinds of input, and the split is the point.**

- The **authorities** are real: the §5.1 policy / goal portfolio rows and the
  §5.2 schedule row are written through the shipped controller faces, and the
  curriculum reads go to the real ``CurriculumContentStore`` over the real
  artifact. That is what makes ``DEC-…0f76024b.…3``'s "read the authority,
  never invent it" checkable.
- The **candidate set** may be handed in (``supply=``): BF-02 §20's proposals
  are the kernel's frozen inputs, and the real generators still answer **zero**
  candidates over the corpus (the sources' unlanded authorities — the
  goal-pack mapping and friends — gap on every call; the corpus's own
  readiness answer is one R4 target plus thirteen level-less targets since
  C1), so the only
  honest way to exercise an ALLOW today is the same injection point P8-1's
  suite uses — ``supply_of(proposal(...))``. That supply is a *test* supply and
  every test that passes one says so; a test that passes none runs the real
  generators over the real corpus.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from elc.content.build import build_content_db
from elc.content.store import ContentStore
from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.curriculum.provider import ContentBackedTeachingTargetProvider
from elc.curriculum.store import CurriculumContentStore
from elc.deletion.controller import DeletionController
from elc.deletion.store import SqliteDeletionStore
from elc.learning.controller import LearningController
from elc.learning.silent_evidence import ContentBackedTargetSupply
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.planner.candidates import CandidateSupply
from elc.planner.ledger_store import SqliteLedgerStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.types import (
    ClientMessageId,
    EvidenceModality,
    GoalId,
    GoalModality,
    GoalVersion,
    InputId,
    InteractionChannel,
    Ok,
    PolicyVersion,
    Result,
    ScheduleVersion,
    TargetId,
)
from elc.runtime.automatic_turn import AutomaticTurnWiring
from elc.runtime.controller import ConversationCoordinator, TurnCompletion
from elc.runtime.lease import ConversationCoordinatorLease
from elc.runtime.types import InputEnvelope
from elc.scheduler.controller import SchedulerController
from elc.scheduler.store import SqliteSchedulerStore
from elc.scheduler.types import (
    ReviewState,
    ScheduleItem,
    SpacingStage,
)
from elc.teaching.controller import TeachingController
from elc.teaching.rollout import RolloutStage
from elc.teaching.store import SqliteTeachingStore
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    TeachingFrequency,
    TeachingPolicyProfile,
)
from tests.conftest import AssemblyGenerationStore
from tests.phase7.conftest import (
    CONV,
    DAY_ONE,
    DAY_THREE,
    DAY_TWO,
    TARGET_ID,
    USER,
    proposal,
)
from tests.phase8.conftest import supply_of

__all__ = [
    "CONTENT_VERSION",
    "GOAL_VERSION",
    "LEDGER_TABLES",
    "PLANNER_FACT_TABLES",
    "POLICY_VERSION",
    "RECEIVED_AT",
    "SCHEDULE_ITEM_ID",
    "TEACHING_FACT_TABLES",
    "TEACHING_ONLY_TABLES",
    "TURN_TEXT",
    "World",
    "acceptance_supply",
    "begin_turn",
    "begin_turn_ok",
    "build_content",
    "command",
    "count_events",
    "counts",
    "deletion_controller",
    "events",
    "make_lease",
    "moments",
    "open_conversation",
    "proposal_of",
    "supply_proposal",
    "wiring",
    "world",
]

#: The ordinary turn every test drives: a plain conversational message (the
#: §4 step 3 leg is the conversation's own state, not the utterance).
TURN_TEXT = "I think we should rehearse that once more."
RECEIVED_AT = DAY_TWO

#: The durable words this world's §5.1 / §5.2 rows carry — distinct enough
#: that a binding stamped from the wrong record is visible.
POLICY_VERSION = "pv-p8-4"
GOAL_VERSION = "gv-p8-4"
SCHEDULE_ITEM_ID = "si-p8-4"
CONTENT_VERSION = "curriculum-v1"

#: §14's CP2 five teaching facts, in the order P8-1's suite names them.
TEACHING_FACT_TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
    "generation_action_intent",
)
#: The four teaching-**only** among them: ``generation_action_intent`` is
#: written by the ordinary persona turn as well, so a "nothing teaching
#: happened" assertion reads these four and looks at the action row's own id.
TEACHING_ONLY_TABLES = (
    "gate_execution_status",
    "gate_decision",
    "teaching_moment",
    "active_teaching_lock",
)
#: The Planner half P8-0 landed, plus the Runtime outcome row.
PLANNER_FACT_TABLES = (
    "planner_evaluation",
    "planner_decision",
    "planner_execution_status",
    "runtime_decision_outcome",
)
#: The PlanningLedger's three tables.
LEDGER_TABLES = ("planning_ledger", "coverage_obligation", "planning_ledger_event")

#: The BF-02 §20 target the proposals name — the corpus target phase 6/7 use.
PROPOSAL_TARGET = TARGET_ID


def proposal_of(candidate_id: str = "cand-p8-4"):
    """One BF-02 §20 proposal (P7's frozen builder, unchanged)."""

    return proposal(candidate_id)


def acceptance_supply(candidate_id: str = "cand-p8-4") -> CandidateSupply:
    """The ALLOW acceptance's injected candidate set (P8-1's own口径).

    A *test* supply: BF-02 §20's inputs are synthetic by contract, and the
    shipped corpus cannot answer R3 for any target — see the module docstring.
    """

    return supply_of(proposal(candidate_id))


#: An alias with the argument's own name at the call site.
supply_proposal = acceptance_supply


def counts(db: sqlite3.Connection, *tables: str) -> dict[str, int]:
    """Row counts read from the database (never predicted)."""

    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def make_lease(fence: RuntimeEpochFence) -> ConversationCoordinatorLease:
    holder = ConversationCoordinatorLease()
    holder.adopt_epoch(fence.current)
    return holder


@dataclass
class World:
    """Every authority one ordinary turn's automatic leg reads, over one db.

    ``content_path`` is the built artifact both the curriculum face and the
    real teaching-target provider read; the ledger store is the same object the
    wiring hands the delivery path's write half.
    """

    db: sqlite3.Connection
    fence: RuntimeEpochFence
    content_path: Path
    store: SqliteConversationStore
    generation: AssemblyGenerationStore
    teaching: TeachingController
    planner: SqlitePlannerRecordStore
    ledger: SqliteLedgerStore
    learning: LearningController
    scheduler: SchedulerController
    user_config: UserConfigController
    curriculum: CurriculumContentStore
    targets: ContentBackedTeachingTargetProvider
    real_supply: ContentBackedTargetSupply
    lease: ConversationCoordinatorLease


def world(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    content_path: Path,
    *,
    conversation: bool = True,
) -> World:
    """Build the whole real chain and (by default) the durable §5.1/§5.2 world.

    The three configuration rows are written through the shipped faces
    (:meth:`UserConfigController.upsert_teaching_policy` /
    :meth:`upsert_goal_portfolio` / :meth:`SchedulerController.
    upsert_schedule_item`), so a test that reads them reads what the product
    writes. ``assessment_targets=()`` is deliberate: a portfolio that names
    assessment targets raises BF-02 §5's ``GOAL_ASSESSMENT_PACK_MAPPING`` gap
    (that mapping is not built), and this world means to be *complete*.
    """

    store = SqliteConversationStore(db, fence)
    generation = AssemblyGenerationStore(db, fence)
    teaching = TeachingController(SqliteTeachingStore(db, fence))
    planner = SqlitePlannerRecordStore(db, fence)
    ledger = SqliteLedgerStore(db, fence)
    learning = LearningController(SqliteLearningStore(db, fence))
    scheduler = SchedulerController(
        SqliteSchedulerStore(db, fence), learning=learning
    )
    user_config = UserConfigController(SqliteUserConfigStore(db, fence))
    curriculum = CurriculumContentStore(ContentStore(content_path))
    targets = ContentBackedTeachingTargetProvider(content_path)
    real_supply = ContentBackedTargetSupply(content_path)

    if conversation:
        opened = store.open_conversation(
            CONV, user_id=USER, persona_id=None, scene_id=None
        )
        assert isinstance(opened, Ok), opened

        policy = user_config.upsert_teaching_policy(
            TeachingPolicyProfile(
                teaching_policy_profile_id=USER,
                policy_version=PolicyVersion(POLICY_VERSION),
                teaching_frequency=TeachingFrequency.BALANCED,
            )
        )
        assert isinstance(policy, Ok), policy
        portfolio = user_config.upsert_goal_portfolio(
            LearningGoalPortfolio(
                goal_portfolio_id=USER,
                goal_version=GoalVersion(GOAL_VERSION),
                goals=(
                    LearningGoal(
                        goal_id=GoalId("goal-1"),
                        goal_modality=GoalModality.SPEAKING,
                        description="a long-term goal",
                    ),
                ),
                modality_weights={GoalModality.SPEAKING: 1.0},
                assessment_targets=(),
                effective_from=DAY_ONE,
            )
        )
        assert isinstance(portfolio, Ok), portfolio
        # DUE at RECEIVED_AT (DAY_TWO) with the window DAY_ONE..DAY_THREE, and
        # its source watermark is the fresh store's own watermark (0), so the
        # §10 view is CURRENT rather than stale.
        row = scheduler.upsert_schedule_item(
            ScheduleItem(
                schedule_item_id=SCHEDULE_ITEM_ID,
                target_type="RESOURCE",
                target_id=TargetId(str(PROPOSAL_TARGET)),
                evidence_modality=EvidenceModality.TEXT_PRODUCTION,
                review_state=ReviewState.DUE,
                review_urgency=0.75,
                next_review_window_start=DAY_ONE,
                next_review_window_end=DAY_THREE,
                spacing_stage=SpacingStage.STAGE_1,
                source_learning_watermark="0",
                version=ScheduleVersion("sv-p8-4"),
            )
        )
        assert isinstance(row, Ok), row

    return World(
        db=db,
        fence=fence,
        content_path=content_path,
        store=store,
        generation=generation,
        teaching=teaching,
        planner=planner,
        ledger=ledger,
        learning=learning,
        scheduler=scheduler,
        user_config=user_config,
        curriculum=curriculum,
        targets=targets,
        real_supply=real_supply,
        lease=make_lease(fence),
    )


def build_content(path: Path) -> Path:
    """One built content.db at ``path`` (the repository's authoring trees)."""

    build_content_db(path)
    return path


def wiring(
    world: World,
    *,
    supply: CandidateSupply | None = None,
    ledger: bool = True,
    learning: bool = True,
    scheduler: bool = True,
    user_config: bool = True,
    curriculum: bool = True,
    user_id: bool = True,
    rollout_stage: RolloutStage | None = RolloutStage.STUDY_FIRST,
) -> AutomaticTurnWiring:
    """The coordinator's optional wiring bundle over the real faces.

    ``supply`` is the assembly's own injection point (``None`` ⇒ the
    generators run over the ports); the ``*`` flags let a test withhold one
    authority and watch the assembly report it as a missing leg instead of a
    number.

    ``rollout_stage`` defaults to ``Study-first`` — the first stage P8-5's
    rollout gate lets automatic teaching run at, declared here because an
    ALLOW chain needs an open stage (``elc.teaching.rollout``). A test that
    wants the fail-closed default passes ``rollout_stage=None``; that the
    default *without* a declaration refuses is pinned in
    ``tests/phase8/test_p8_5_rollout_gate.py``.
    """

    return AutomaticTurnWiring(
        planner_store=world.planner,
        teaching=world.teaching,
        learning=world.learning if learning else None,
        scheduler=world.scheduler if scheduler else None,
        user_config=world.user_config if user_config else None,
        curriculum=world.curriculum if curriculum else None,
        supply=None,
        ledger=world.ledger if ledger else None,
        session_budget=world.teaching,
        user_id=USER if user_id else None,
        candidate_supply=supply,
        rollout_stage=rollout_stage,
    )


def coordinator(
    world: World,
    *,
    automatic: AutomaticTurnWiring | None = None,
    persona: object | None = None,
    commands: object | None = None,
    generation: object | None = None,
) -> ConversationCoordinator:
    """The ordinary-turn coordinator, with or without the automatic wiring.

    ``generation`` replaces the coordinator's generation face (the leg's own
    read-back, :meth:`GenerationStore.get_action_for_turn`, is read through it);
    the persona runtime below keeps the real store, exactly as the shipped
    assembly wires the two.
    """

    runtime = PersonaRuntime(
        actions=world.generation,
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )
    return ConversationCoordinator(
        lease=world.lease,
        conversation_commands=world.store if commands is None else commands,
        conversation_queries=world.store,
        persona=runtime if persona is None else persona,
        generation_actions=(
            world.generation if generation is None else generation
        ),
        decision_cycles=world.generation.decision_cycles,
        learning_controller=world.learning,
        teaching=world.teaching,
        targets=world.targets,
        automatic_teaching=automatic,
    )


def command(
    client_message_id: str,
    *,
    conversation: object = CONV,
    received_at: str = RECEIVED_AT,
    text: str = TURN_TEXT,
) -> CommitUserTurn:
    """One committed user turn's command (CP0 runs inside the coordinator)."""

    return CommitUserTurn(
        conversation_id=conversation,  # type: ignore[arg-type]
        envelope=InputEnvelope(
            input_id=InputId(f"in-{client_message_id}"),
            client_message_id=ClientMessageId(client_message_id),
            conversation_id=str(conversation),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=f"raw-{client_message_id}",
            received_at=received_at,
        ),
        raw_content=text,
        runtime_version="runtime-p8-4",
    )


def begin_turn(
    coordinator_: ConversationCoordinator,
    client_message_id: str,
    **overrides: object,
) -> Result[TurnCompletion]:
    """Drive one ordinary turn (the raw result, Err included)."""

    return coordinator_.begin_turn(command(client_message_id, **overrides))


def begin_turn_ok(
    coordinator_: ConversationCoordinator,
    client_message_id: str,
    **overrides: object,
) -> TurnCompletion:
    result = begin_turn(coordinator_, client_message_id, **overrides)
    assert isinstance(result, Ok), result
    return result.value


def deletion_controller(world_: World) -> DeletionController:
    """The BF-05 authority face over this world's db (the real one)."""

    return DeletionController(
        SqliteDeletionStore(world_.db, world_.fence),
        learning=world_.learning,
        scheduler=world_.scheduler,
    )


def open_conversation(world_: World, conversation: object) -> None:
    """One more real conversation row (§5.1 style rows need it)."""

    result = world_.store.open_conversation(
        conversation, user_id=USER, persona_id=None, scene_id=None
    )
    assert isinstance(result, Ok), result


def events(db: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Every ledger event, in deterministic id order, with its provenance."""

    return [
        tuple(row)
        for row in db.execute(
            "SELECT event_id, ledger_key, event, as_of, moment_id"
            " FROM planning_ledger_event ORDER BY event_id"
        )
    ]


def moments(db: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Every moment row, its conversation and its state."""

    return [
        tuple(row)
        for row in db.execute(
            "SELECT moment_id, conversation_id, lifecycle_state"
            " FROM teaching_moment ORDER BY moment_id"
        )
    ]


def count_events(db: sqlite3.Connection, *, moment_id: str | None = None) -> int:
    if moment_id is None:
        return int(
            db.execute("SELECT COUNT(*) FROM planning_ledger_event").fetchone()[0]
        )
    return int(
        db.execute(
            "SELECT COUNT(*) FROM planning_ledger_event WHERE moment_id = ?",
            (moment_id,),
        ).fetchone()[0]
    )
