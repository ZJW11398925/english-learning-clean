"""p10-2 —— 25 类 runtime failure scenario 套件 B（非崩溃类失败 12 类）。

IP §11 的验收句是「复现 OQ-025A 25 类 runtime failure scenario」，而 OQ-025A 在
仓内**无载体**（只有 `docs/IMPLEMENTATION_PLAN.md:496` 一句）⇒ 按 `OQ-024A→60 例`
/`OQ-023A→43 例`先例走**可执行替代**（开工 DEC `DEC-OPI-9dba34fb-….29` R7）：以
**A 半（`tests/phase10/test_p10_1_failure_scenarios_a.py` 的 CP0–CP3 崩溃窗口
13 类）+ B 半（本文件：非崩溃类失败 12 类）= 25 类**为命名网格。本文件**不**是
既有 crash/recovery 回归的重复，也不重复 A 半：A 半的主题是「崩在某个 checkpoint
的窗口里」，B 半的主题是**进程没有崩、但某个面不工作**——端口降级、读失败、迟到
回调、epoch 竞争、多残件并存、残件与正常路径交错。

**与 A 半口径一致声明（R3）**：同一网格形态（一 tag 一名、tag 的 snake_case 是
本文件 `test_` 函数名的前缀）、同一构造纪律（真 app.db 世界 + 真写入面 + **零
`_seed()` 零 fixture 供给**）、同一四问（下面 `(i)`–`(iv)` 的适用/N-A 逐类作答）、
同一交付事实（p10-0 落地的 `ACTION`/`MOMENT`/`ANALYSIS`/`DELIVERY` 四类 kind 今日
**零消费者**——每类都点名谁 apply、谁不 apply）、同一外壳（`Refusing` 从 A 半**导入**
而非复制，R2）。

十二类 ↔ §11/§22 扫面 × 失败形态映射表（R3；每行可核：tag 是本文件 `SCENARIOS` 的
字面量、也在本 docstring 里，tag 的 snake_case 是本文件 `test_` 函数名的前缀，
faces 是既有面的**名字**——行号只是引用，名字才是钉，由最后一个测试逐个复核）：

    #  tag                          | §11 残件 / §22 扫面      | 失败形态
    1  degraded-learning-leg        | pending AnalysisArtifact | 端口降级（Err）
    2  degraded-projection-line     | pending projections      | 端口降级（Err）
    3  degraded-ledger-write        | §20 exposure event       | 写失败（Err）
    4  scan-read-failure            | 四类 P10-0 扫面 + P4-2   | 读失败（Err / raise）
    5  epoch-race-action-claim      | GenerationActionIntent   | 旧 epoch 触碰
    6  epoch-race-turn-canonicalize | TurnRecord / transcript  | 旧 epoch 触碰
    7  late-callback-foreign-epoch  | GenerationActionIntent   | 迟到回调（外来）
    8  late-callback-cancelled      | ServerDeliveryRecord     | 迟到回调（已取消）
    9  multi-residue-coexist        | 六类残件同现             | 多残件并存
    10 residue-then-normal-turn     | TeachingLockLease        | 残件与正常路径交错
    11 interrupt-during-recovery    | interrupt_request        | 恢复与新输入交错
    12 idempotent-second-startup    | 六类残件                 | 幂等重跑

四条口径不变量（任务书 §2 末）逐类**适用者断言、不适用者写明理由**；本文件把「汇总
表 vs 逐类答案一致」做成**可执行**的（A 半评审的 MEDIUM 就是它不一致）：下表每行的
`(i)`–`(iv)` 短答与本文件 `INVARIANTS` 逐字相同，且每个类测试的 docstring 必须逐字
含同一短答——`test_the_summary_table_and_the_per_class_answers_agree` 逐条复核：

    1  degraded-learning-leg
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) N/A：无未决投递
    2  degraded-projection-line
       (i) N/A：不重入 turn | (ii) 适用 | (iii) 适用 | (iv) N/A：投影无投递
    3  degraded-ledger-write
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) 适用
    4  scan-read-failure
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) N/A：无投递
    5  epoch-race-action-claim
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) N/A：无投递
    6  epoch-race-turn-canonicalize
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) N/A：无投递
    7  late-callback-foreign-epoch
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) 适用
    8  late-callback-cancelled
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) 适用
    9  multi-residue-coexist
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) 适用
    10 residue-then-normal-turn
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) 适用
    11 interrupt-during-recovery
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) 适用
    12 idempotent-second-startup
       (i) 适用 | (ii) 适用 | (iii) 适用 | (iv) N/A：无投递

世界与构造（R2）：真库世界 + 真写入面，**零 `_seed()` 零 fixture 供给**。三个世界：
phase-3 app.db 世界（`tests/phase3/conftest.py`，类 1/2/3/4/5/6/9/10/11/12）+ phase-9
**文件库**世界（`tests/phase9/test_p9_2_stream_turn.py` 的 `StreamWorld`——§22 交付行与
流式 transport 只有它带得动，类 7/8）+ 本文件 `six_kind_world`（唯一一处多重残件同现：
真教学开课 / 真 CP0 / 真 DecisionCycle / 真 analysis producer / 真 action / 真 §22 写
入）。

**被迫世界与降级注入逐处就地声明**（在每个类测试的 docstring 里）：降级 = 一个具名面
返回 `Err`（`Refusing`，A 半外壳，导入复用）；读失败 = 一个具名读面返回 `Err`（子类
覆写——`@runtime_checkable` 的 isinstance 是**静态**检查，动态代理转发面在它眼里不存
在，这条机制事实写在类 4）；抛错 = 一个具名面 `raise`。测试内 SQL 只用于控制组读回与
被迫世界（删/改一行以造出「崩在两次写之间」的 durable 形状），不用于被测读面本身。

红线：本文件经 Write/Edit 落盘；未触碰 `migrations/`、`docs/`、`behavioral_baselines/`、
`tests/architecture/`、`tests/conftest.py`、`registry.py`、任何 `src/`；未改动
`test_p10_0_*.py` 与 `test_p10_1_*.py`；零迁移。**通道偏差一处（as-found，已留痕）**：
一次 Bash heredoc 的读改写（CR=0、LF 保持、无 BOM，字节实测无痕），见回执自报。
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from elc.conversation import (
    AssistantTurnRecord,
    CommitUserTurn,
    SqliteConversationStore,
)
from elc.conversation.types import DeliveryState, TurnOutcome
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.planner.ledger_store import SqliteLedgerStore
from elc.platform.db import epoch
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.planner_store import SqlitePlannerRecordStore
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    ConversationId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    MessageSequence,
    Ok,
    Result,
    TurnId,
    TurnSequence,
    UserId,
)
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.automatic_turn import AutomaticTurnWiring
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.delivery_records import ServerDeliveryRecord
from elc.runtime.projections import (
    PROJECTION_TYPE_EPISODE,
    PROJECTION_TYPE_RELATIONSHIP,
    CP4ProjectionRuntime,
    projection_id_for,
)
from elc.runtime.recovery import (
    MOMENT_RECOVERY_ACTION,
    RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY,
    RECOVERY_DISPOSITION_RESUME_ACTION,
    RECOVERY_DISPOSITION_RESUME_ANALYSIS,
    RECOVERY_KIND_ACTION,
    RECOVERY_KIND_ANALYSIS,
    RECOVERY_KIND_DELIVERY,
    RECOVERY_KIND_LOCK,
    RECOVERY_KIND_MOMENT,
    RECOVERY_KIND_TURN,
    TEACHING_LOCK_RECOVERY_ACTION,
    StartupRecoveryScanner,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    InterruptRequest,
    TurnStatus,
)
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from elc.teaching.types import MomentState
from tests.conftest import SRC_ROOT, AssemblyGenerationStore
from tests.phase3.conftest import (
    CONV,
    RECEIVED_AT,
    RUNTIME_VERSION,
    make_lease,
)
from tests.phase3.target_fixtures import FixtureTeachingTargetProvider
from tests.phase4.conftest import NoopProjectionExecutor, complete_executors
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    StreamWorld,
    action_of,
    begin_turn_ok,
    count,
    pieces,
    stream_world,
)
from tests.phase9.test_p9_3_barge_in import (
    InterruptingFactory,
    bind,
    coordinator_for,
    coordinator_over,
    open_turn_with_action,
)
from tests.phase9.test_p9_3_late_callbacks import snapshot
from tests.phase10.test_p10_1_failure_scenarios_a import (
    Refusing,
    WatchingClaimStore,
    World,
)

FOCUS_TARGET = "res-hedge-i-think"
STARTED_AT = "2026-09-20T08:00:02+00:00"

#: R3's table as one literal the last test checks: (tag, the §11 residue class
#: the class is about, the cited faces as the *names* they are pinned by).
SCENARIOS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("degraded-learning-leg", "pending AnalysisArtifact",
     ("_run_learning_analysis", "record_learning_analysis",
      "commit_learning_evidence", "pending_analysis_artifacts")),
    ("degraded-projection-line", "pending projections",
     ("_recover_projections", "recover_stale_running", "ensure_missing_jobs",
      "run_pending")),
    ("degraded-ledger-write", "the §20 exposure event a delivery owes",
     ("_with_exposure", "_record_skip_exposure", "record_exposure",
      "record_ledger_event")),
    ("scan-read-failure", "the four P10-0 scan surfaces",
     ("StartupRecoveryScanner", "evidence_proposal_refs",
      "_reconcile_evidence_refs", "_retry_pending_evidence")),
    ("epoch-race-action-claim", "GenerationActionIntent",
     ("claim_action_for_recovery", "transition_action",
      "_require_current_epoch")),
    ("epoch-race-turn-canonicalize", "TurnRecord + the transcript",
     ("canonicalize_assistant_turn", "claim_turn_for_recovery",
      "terminalize_turn", "transition_turn")),
    ("late-callback-foreign-epoch", "GenerationActionIntent",
     ("accept_late_result",)),
    ("late-callback-cancelled", "ServerDeliveryRecord",
     ("accept_late_result", "_cancel_interrupted_action")),
    ("multi-residue-coexist", "all six residue classes at once",
     ("run_startup_recovery", "recover_orphan_teaching",
      "_close_residual_turns", "_abort_opening")),
    ("residue-then-normal-turn", "TeachingLockLease + TeachingMoment",
     ("recover_orphan_teaching", "begin_turn", "request_teaching")),
    ("interrupt-during-recovery", "interrupt_request",
     ("request_interrupt", "_reconcile_pending_interrupt",
      "_cancel_interrupted_turn")),
    ("idempotent-second-startup", "all six residue classes",
     ("run_startup_recovery", "reconcile_delivering_residue")),
)

#: The four invariants' short answers, per tag — the same literals the module
#: docstring's table carries and each class test's docstring repeats. The pin
#: ``test_the_summary_table_and_the_per_class_answers_agree`` is what makes the
#: agreement checkable instead of reviewed by eye (the A-half lesson).
INVARIANTS: dict[str, tuple[str, str, str, str]] = {
    "degraded-learning-leg": ("适用", "适用", "适用", "N/A：无未决投递"),
    "degraded-projection-line": (
        "N/A：不重入 turn", "适用", "适用", "N/A：投影无投递"),
    "degraded-ledger-write": ("适用", "适用", "适用", "适用"),
    "scan-read-failure": ("适用", "适用", "适用", "N/A：无投递"),
    "epoch-race-action-claim": ("适用", "适用", "适用", "N/A：无投递"),
    "epoch-race-turn-canonicalize": ("适用", "适用", "适用", "N/A：无投递"),
    "late-callback-foreign-epoch": ("适用", "适用", "适用", "适用"),
    "late-callback-cancelled": ("适用", "适用", "适用", "适用"),
    "multi-residue-coexist": ("适用", "适用", "适用", "适用"),
    "residue-then-normal-turn": ("适用", "适用", "适用", "适用"),
    "interrupt-during-recovery": ("适用", "适用", "适用", "适用"),
    "idempotent-second-startup": ("适用", "适用", "适用", "N/A：无投递"),
}

#: The modules the cited faces live in: the faces are pinned as *names* against
#: these blobs (the line numbers in the docstrings are citations), so a renamed
#: face fails this suite instead of quietly diverging from the table.
FACE_SOURCES = (
    SRC_ROOT / "runtime" / "controller.py",
    SRC_ROOT / "runtime" / "recovery.py",
    SRC_ROOT / "runtime" / "projections.py",
    SRC_ROOT / "runtime" / "exposure.py",
    SRC_ROOT / "conversation" / "store.py",
    SRC_ROOT / "learning" / "controller.py",
    SRC_ROOT / "learning" / "store.py",
    SRC_ROOT / "platform" / "db" / "generation_store.py",
    SRC_ROOT / "platform" / "db" / "delivery_store.py",
    SRC_ROOT / "planner" / "ledger_store.py",
    SRC_ROOT / "teaching" / "controller.py",
)

#: The tables the counted worlds touch — the no-extra-work pins read this list,
#: so a scenario cannot "pass" by writing into a table nobody counted.
COUNTED_TABLES = (
    "turn_record", "user_turn", "input_envelope", "assistant_turn",
    "generation_action_intent", "decision_cycle", "teaching_moment",
    "active_teaching_lock", "analysis_artifact", "evidence_group",
    "evidence_claim", "server_delivery_record", "planning_ledger",
    "planning_ledger_event", "runtime_epoch", "interrupt_request",
    "projection_job",
)


# -- the assembly this file drives --------------------------------------------


def coordinator_of(
    world: World,
    *,
    persona: object = None,
    actions: object = None,
    learning: object = None,
    learning_controller: object = None,
    teaching: object = None,
    commands: object = None,
    decision_cycles: object = None,
    projections: object = None,
    automatic: object = None,
    delivery_records: object = None,
) -> ConversationCoordinator:
    """One coordinator over this world's stores, with every optional face
    *replaceable by name* — the phase-3 assembly plus the injections this half
    needs (the delivery-record face, the automatic wiring, the projections)."""

    chosen = world.generation if actions is None else actions
    learning_port = world.learning if learning is None else learning
    cycles = (
        chosen.decision_cycles  # type: ignore[attr-defined]
        if decision_cycles is None else decision_cycles
    )
    return ConversationCoordinator(
        lease=make_lease(world.fence),
        conversation_commands=world.store if commands is None else commands,  # type: ignore[arg-type]
        conversation_queries=world.store,
        persona=(_persona(chosen) if persona is None else persona),  # type: ignore[arg-type]
        generation_actions=chosen,  # type: ignore[arg-type]
        learning=learning_port,  # type: ignore[arg-type]
        decision_cycles=cycles,  # type: ignore[arg-type]
        learning_controller=(
            LearningController(learning_port)  # type: ignore[arg-type]
            if learning_controller is None else learning_controller  # type: ignore[arg-type]
        ),
        teaching=world.teaching if teaching is None else teaching,  # type: ignore[arg-type]
        targets=world.targets,
        projections=projections,  # type: ignore[arg-type]
        automatic_teaching=automatic,  # type: ignore[arg-type]
        delivery_records=delivery_records,  # type: ignore[arg-type]
    )


def _persona(actions: object) -> PersonaRuntime:
    return PersonaRuntime(
        actions=actions,  # type: ignore[arg-type]
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )


def _chat_command(cmid: str, conversation: str = CONV) -> CommitUserTurn:
    return CommitUserTurn(
        conversation_id=conversation,  # type: ignore[arg-type]
        envelope=InputEnvelope(
            input_id=InputId(f"in-{cmid}"),
            client_message_id=ClientMessageId(cmid),
            conversation_id=conversation,
            persona_id=None, scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=f"raw-{cmid}", received_at=RECEIVED_AT,
        ),
        raw_content="I think it is fine.",
        runtime_version=RUNTIME_VERSION,
    )


def _teaching_request(cmid: str, conversation: str = CONV) -> TeachingRequest:
    return TeachingRequest(
        conversation_id=conversation,  # type: ignore[arg-type]
        focus_target_id=FOCUS_TARGET,
        client_message_id=ClientMessageId(cmid), requested_at=RECEIVED_AT,
    )


def _reply_request(cmid: str) -> TeachingReplyRequest:
    return TeachingReplyRequest(
        conversation_id=CONV,
        envelope=TeachingResponseEnvelope(
            control_intent=TeachingControlIntent.SKIP, attempt_present=False,
        ),
        client_message_id=ClientMessageId(cmid), requested_at=RECEIVED_AT,
    )


def _commit_chat_turn(
    store: SqliteConversationStore, cmid: str, conversation: str = CONV
) -> str:
    result = store.commit_user_turn(_chat_command(cmid, conversation))
    assert isinstance(result, Ok), result
    return str(result.value.turn_id)


def _begin_turn(coordinator: ConversationCoordinator, cmid: str) -> object:
    result = coordinator.begin_turn(_chat_command(cmid))
    assert isinstance(result, Ok), result
    return result.value


def _action_record(
    action_id: str, turn_id: str, cycle_id: str, status: GenerationActionStatus
) -> GenerationActionIntentRecord:
    return GenerationActionIntentRecord(
        action_id=ActionId(action_id), turn_id=TurnId(turn_id),
        decision_cycle_id=DecisionCycleId(cycle_id), moment_id=None,
        assistant_turn_id=f"at-{action_id}",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-p10-2", status=status, attempt_count=0,
    )


def _open_turn_with_action(world: World, cmid: str) -> tuple[str, str]:
    """One durable turn whose DecisionCycle and nonterminal action exist —
    the CP0+cycle+action shape a crash (or a barge-in) finds."""

    turn_id = _commit_chat_turn(world.store, cmid)
    cycle_id = f"dcy-{turn_id}"
    recorded = world.decision_cycles.record_decision_cycle(
        decision_cycle_id=DecisionCycleId(cycle_id), turn_id=TurnId(turn_id),
        bindings=DecisionCycleBindings(), expected_turn_state_version=1,
    )
    assert isinstance(recorded, Ok), recorded
    action_id = f"act-{turn_id}"
    created = world.generation.create_action(
        _action_record(action_id, turn_id, cycle_id, GenerationActionStatus.REQUESTED)
    )
    assert isinstance(created, Ok), created
    return (turn_id, action_id)


def _counts(db: sqlite3.Connection, *tables: str) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _rows(
    db: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()
) -> list[tuple[object, ...]]:
    return [tuple(row) for row in db.execute(sql, params).fetchall()]


def _turn_row(
    db: sqlite3.Connection, turn_id: str
) -> tuple[str, str | None, int, int]:
    rows = _rows(
        db,
        "SELECT status, turn_outcome, owner_epoch, state_version FROM turn_record"
        " WHERE turn_id = ?",
        (turn_id,),
    )
    assert rows, f"no turn_record row: {turn_id}"
    status, outcome, owner, version = rows[0]
    return (
        str(status), None if outcome is None else str(outcome),
        int(owner), int(version),
    )


def _action_row(db: sqlite3.Connection, action_id: str) -> tuple[str, str, int]:
    rows = _rows(
        db,
        "SELECT action_id, status, owner_epoch FROM generation_action_intent"
        " WHERE action_id = ?",
        (action_id,),
    )
    assert rows, f"no generation_action_intent row: {action_id}"
    return (str(rows[0][0]), str(rows[0][1]), int(rows[0][2]))


def _moment_rows(
    db: sqlite3.Connection,
) -> list[tuple[str, str, str | None, int]]:
    return [
        (str(row[0]), str(row[1]),
         None if row[2] is None else str(row[2]), int(row[3]))
        for row in _rows(
            db,
            "SELECT moment_id, lifecycle_state, abort_reason, state_version"
            " FROM teaching_moment ORDER BY moment_id",
        )
    ]


def _delivery_row(
    db: sqlite3.Connection, action_id: str
) -> tuple[str, str, int, str | None]:
    rows = _rows(
        db,
        "SELECT state, sent_prefix, last_chunk_seq, terminal_at"
        " FROM server_delivery_record WHERE action_id = ?",
        (action_id,),
    )
    assert rows, f"no server_delivery_record row: {action_id}"
    return (
        str(rows[0][0]), str(rows[0][1]), int(rows[0][2]),
        None if rows[0][3] is None else str(rows[0][3]),
    )


def _scan(
    store: object, lease: object, teaching: object, **ports: object
) -> tuple[tuple[str, str, str], ...]:
    """One scan, as the caller-injected shape (the four P10-0 ports are
    optional and absent unless a caller passes them)."""

    plan = StartupRecoveryScanner(
        store, lease, teaching, **ports  # type: ignore[arg-type]
    ).scan()
    assert isinstance(plan, Ok), plan
    return tuple((item.kind, item.id, item.action) for item in plan.value)


def _kinds(plan: tuple[tuple[str, str, str], ...], kind: str) -> list[str]:
    return [item_id for item_kind, item_id, _ in plan if item_kind == kind]


def _words(plan: tuple[tuple[str, str, str], ...], kind: str) -> list[str]:
    return [word for item_kind, _, word in plan if item_kind == kind]


@pytest.fixture()
def world(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    store: SqliteConversationStore,
    learning: SqliteLearningStore,
    generation_store: AssemblyGenerationStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    target_provider: FixtureTeachingTargetProvider,
    conversation: object,
) -> World:
    """The A-half world (imported), built from the phase-10 fixture set."""

    del conversation  # requested for its side effect
    return World(
        db=db, fence=fence, store=store, learning=learning,
        generation=generation_store, decision_cycles=decision_cycle_store,
        teaching_store=teaching_store, teaching=teaching_controller,
        targets=target_provider,
    )


# -- the six-kind world (classes 9 and 12) ------------------------------------


@dataclass(frozen=True)
class SixKind:
    """One old-epoch residue of every kind the P10-0 scan reads."""

    world: World
    turn_id: str
    analysis_id: str
    action_id: str
    moment_id: str
    teaching_turn_id: str


@pytest.fixture()
def six_kind(world: World) -> SixKind:
    """The multi-residue world, every row by a real face: a delivered teaching
    opening (MOMENT + LOCK), a chat turn stopped at CP0 (TURN + pending
    ANALYSIS), and that turn's nonterminal action with an unterminated §22
    send (ACTION + DELIVERY)."""

    opened = coordinator_of(world).request_teaching(
        _teaching_request("cm-p10-2-six-open")
    )
    assert isinstance(opened, Ok), opened
    moment_id = str(opened.value.moment_id)
    teaching_turn_id = str(opened.value.turn_id)

    turn_id = _commit_chat_turn(world.store, "cm-p10-2-six-pending")
    cycle_id = f"dcy-{turn_id}"
    recorded = world.decision_cycles.record_decision_cycle(
        decision_cycle_id=DecisionCycleId(cycle_id), turn_id=TurnId(turn_id),
        bindings=DecisionCycleBindings(), expected_turn_state_version=1,
    )
    assert isinstance(recorded, Ok), recorded
    turn_slice = world.store.get_canonical_turn_slice(TurnId(turn_id))
    assert isinstance(turn_slice, Ok), turn_slice
    proposal = world.learning.record_learning_analysis(turn_slice.value)
    assert isinstance(proposal, Ok), proposal
    analysis_id = str(proposal.value.analysis_id)

    action_id = "act-p10-2-six"
    created = world.generation.create_action(
        _action_record(action_id, turn_id, cycle_id, GenerationActionStatus.REQUESTED)
    )
    assert isinstance(created, Ok), created
    written = SqliteDeliveryRecordStore(world.db, world.fence).record_server_delivery(
        ServerDeliveryRecord(
            action_id=ActionId(action_id), assistant_turn_id=f"at-{action_id}",
            state="SENDING", sent_prefix="", last_chunk_seq=0,
            started_at=STARTED_AT, terminal_at=None,
        )
    )
    assert isinstance(written, Ok), written
    return SixKind(
        world=world, turn_id=turn_id, analysis_id=analysis_id,
        action_id=action_id, moment_id=moment_id,
        teaching_turn_id=teaching_turn_id,
    )


# -- the injection shells (the §0 discipline's own shapes) --------------------


class RefusingLedger:
    """The real §20 ledger store with **one named face** refused — so the
    three reads still answer the durable row and only the write fails."""

    def __init__(self, inner: SqliteLedgerStore) -> None:
        self.inner = inner

    def record_ledger_event(self, **kwargs: object) -> Result[object]:
        return Err(DomainError(
            code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
            message="injected ledger refusal",
        ))

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)


class NoTurnRecoveryRead:
    """Everything forwarded except the recovery read face, which is **hidden**
    (``hasattr`` False) — the "this assembly's commands cannot scan" shape."""

    def __init__(self, inner: object) -> None:
        self.inner = inner

    def __getattr__(self, name: str) -> object:
        if name == "recoverable_turn_records":
            raise AttributeError(name)
        return getattr(self.inner, name)


class RaisingDeliveryRead:
    """The §22 residue read, raising instead of answering rows."""

    def unterminal_delivery_records(self, current_epoch: object) -> tuple[str, ...]:
        raise RuntimeError("the §22 residue read exploded")


class RefusingEvidenceRefs(TeachingController):
    """The P4-2 ref scan's read face, refused.

    A **subclass**, not a proxy, and that is a mechanism fact this suite pins:
    ``@runtime_checkable`` protocols are checked statically (Python 3.12's
    ``__instancecheck__`` does not see a ``__getattr__``-forwarded member), so
    the A-half's ``Refusing`` shell cannot make ``isinstance(teaching,
    TeachingEvidenceRefSource)`` fail — the only honest way to refuse *this*
    face is to declare it.
    """

    def evidence_proposal_refs(
        self,
    ) -> Result[tuple[tuple[str, tuple[str, ...]], ...]]:
        return Err(DomainError(
            code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
            message="injected ref-scan refusal",
        ))


class RefusingEvidenceRetry(LearningController):
    """The durable pending-evidence retry face, refused (same subclass reason)."""

    def retry_pending_teaching_evidence(
        self,
    ) -> Result[tuple[tuple[str, object], ...]]:
        return Err(DomainError(
            code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
            message="injected backlog refusal",
        ))


class InterruptingProjections:
    """A real CP4 runtime whose first ``recover_stale_running`` writes a
    durable interrupt request *before* forwarding — the in-process shape of
    the user typing while the startup pass is running."""

    def __init__(
        self, inner: CP4ProjectionRuntime, *, store: SqliteConversationStore,
        action_id: str, turn_id: str, input_id: str,
    ) -> None:
        self.inner = inner
        self.store = store
        self.action_id = action_id
        self.turn_id = turn_id
        self.input_id = input_id
        self.fired = False

    def recover_stale_running(self) -> Result[object]:
        if not self.fired:
            self.fired = True
            written = self.store.request_interrupt(
                InterruptRequest(
                    input_id=InputId(self.input_id), conversation_id=str(CONV),
                    active_turn_id=self.turn_id, active_action_id=self.action_id,
                    reason="the user typed while the startup pass ran",
                )
            )
            assert isinstance(written, Ok), written
        return self.inner.recover_stale_running()  # type: ignore[no-any-return]

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)


def _assistant_for(
    world: World, turn_id: str, content: str, action_id: str
) -> AssistantTurnRecord:
    """One transcript row for a turn, with the turn's own sequences."""

    turn_slice = world.store.get_canonical_turn_slice(TurnId(turn_id))
    assert isinstance(turn_slice, Ok) and turn_slice.value is not None
    user_turn = turn_slice.value.user_turn
    return AssistantTurnRecord(
        assistant_turn_id=f"at-{action_id}", turn_id=TurnId(turn_id),
        conversation_id=ConversationId(user_turn.conversation_id),
        turn_sequence=TurnSequence(user_turn.turn_sequence),
        message_sequence=MessageSequence(user_turn.message_sequence),
        action_id=ActionId(action_id), content=content,
        delivery_state=DeliveryState.SENT_COMPLETE,
        delivery_certainty="SERVER_SENT_UNCONFIRMED",
    )


def _projection_runtime(world: World) -> CP4ProjectionRuntime:
    return CP4ProjectionRuntime(
        store=SqliteProjectionStore(world.db, world.fence),
        executors=complete_executors(
            NoopProjectionExecutor(PROJECTION_TYPE_RELATIONSHIP)
        ),
        turns=world.store,
    )


def stream_world_mkdir(path: Path) -> StreamWorld:
    """``stream_world`` needs its directory to exist (it writes ``app.db``
    inside it); the P9-2 helper's own ``tmp_path`` is always there."""

    path.mkdir(parents=True, exist_ok=True)
    return stream_world(path)


# 1 — degraded-learning-leg


def test_degraded_learning_leg_keeps_the_turn_and_names_the_pending_artifact(
    world: World,
) -> None:
    """degraded-learning-leg（RA §21 降级；RA §4 steps 3-4；IP §11 的 pending
    AnalysisArtifact）.

    两条降级臂，都是「Learning 不可用 ⇒ turn 不停」：①分析产出面 Err ⇒ 连 durable
    artifact 都没留下（`_run_learning_analysis` 的第一条降级返回，controller.py:7566）
    ⇒ 正常 persona 回复 + COMPLETED；②提交面 Err ⇒ artifact 停在 PRODUCED
    （pending），回复照发（同一方法的第二条降级，:7573-7575）⇒ 新 epoch 的扫描把它
    具名为 ANALYSIS + RESUME_ANALYSIS，但**不自动重试**（§21「no risky automatic
    remediation」；该 turn 已 COMPLETED ⇒ 入口只重放终局，:1380-1384）。

    **降级注入，已声明**：①②各以一个具名面返回 `Err` 的 `Refusing` 实现（A 半外壳）。
    (i) 适用：同一 `client_message_id` 的重入 adopt 同一个 turn、不产第二行。
    (ii) 适用：group/claim 计数跨降级与跨重入都不动（本世界恒 0）。
    (iii) 适用：①②的 turn 都到 COMPLETED/REPLIED_FULL；②的残件被具名分类。
    (iv) N/A：无未决投递（本类没有「可能已送出」的未决投递——回复已投递完成）。
    """

    db = world.db
    degraded = coordinator_of(
        world, learning=Refusing(world.learning, "record_learning_analysis")
    )
    done_a = _begin_turn(degraded, "cm-p10-2-degraded-analysis")
    turn_a = str(done_a.turn_id)
    assert done_a.outcome == "REPLIED_FULL"
    assert _turn_row(db, turn_a)[:2] == ("COMPLETED", "REPLIED_FULL")
    assert _counts(db, "analysis_artifact", "evidence_group") == {
        "analysis_artifact": 0, "evidence_group": 0
    }

    degraded_b = coordinator_of(
        world, learning=Refusing(world.learning, "commit_learning_evidence")
    )
    done_b = _begin_turn(degraded_b, "cm-p10-2-degraded-commit")
    turn_b = str(done_b.turn_id)
    assert done_b.outcome == "REPLIED_FULL"
    assert _turn_row(db, turn_b)[:2] == ("COMPLETED", "REPLIED_FULL")
    assert _rows(db, "SELECT status FROM analysis_artifact") == [("PRODUCED",)]
    assert _counts(db, "evidence_group", "assistant_turn") == {
        "evidence_group": 0, "assistant_turn": 2
    }

    new = world.restart()
    plan = new.scan()
    assert _kinds(plan, RECOVERY_KIND_ANALYSIS) == [
        str(_rows(db, "SELECT analysis_id FROM analysis_artifact")[0][0])
    ]
    assert _words(plan, RECOVERY_KIND_ANALYSIS) == [
        RECOVERY_DISPOSITION_RESUME_ANALYSIS
    ]

    before = _counts(db, *COUNTED_TABLES)
    again = _begin_turn(coordinator_of(new), "cm-p10-2-degraded-commit")
    assert str(again.turn_id) == turn_b  # the same turn, replayed
    assert _counts(db, *COUNTED_TABLES) == before
    assert _rows(db, "SELECT status FROM analysis_artifact") == [("PRODUCED",)]


# 2 — degraded-projection-line


def test_degraded_projection_line_reports_unavailable_and_the_retry_repairs(
    world: World,
) -> None:
    """degraded-projection-line（P4-2 F2 的失败容错；IP §11 的 pending
    projections）.

    CP4 sweep 的第一步被拒（`recover_stale_running` Err）⇒ 该腿在 outcome 上具名
    `projection_recovery_unavailable=True`、两条空元组是「没读」而不是「没有」
    （controller.py:4136-4141 的早退），**启动仍然完成**，且**同一次 pass 的其它腿
    照跑**（本世界的孤立教学锁仍被 sweep 释放：`recovered_moments` 非空）。durable
    行不动（PENDING 仍 PENDING）；第二次 pass（同一 `Refusing` 只拒一次）把 crash
    gap 补回并把队列排干（:4139-4162 的三步）。

    **被迫世界，已声明**：crash gap（删一行 job、把另一行改回 PENDING）用两条直接
    语句造出——那是「崩在 enqueue 与 run 之间」的 durable 形状，没有任何 shipped
    单一面会留成这样。**降级注入**：`Refusing`（拒一次）。
    (i) N/A：不重入 turn（投影 sweep 从不重入 user turn；本测试不断言 turn 行，
    turn 的可解释终态由类 1/9/10 承担）。
    (ii) 适用（零形状）：投影 sweep 不写 Learning 行，断言 group 计数不变。
    (iii) 适用——本类的主场：PENDING 行到 COMMITTED，gap 被确定性 job id 补回。
    (iv) N/A：投影无投递（投影面没有投递这回事）。
    """

    db = world.db
    projections = _projection_runtime(world)
    opened = coordinator_of(world).request_teaching(
        _teaching_request("cm-p10-2-projection-open")
    )
    assert isinstance(opened, Ok), opened
    moment_id = str(opened.value.moment_id)
    done = _begin_turn(
        coordinator_of(world, projections=projections), "cm-p10-2-projection-turn"
    )
    turn_id = str(done.turn_id)
    relationship = str(projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn_id))
    episode = projection_id_for(PROJECTION_TYPE_EPISODE, turn_id)
    db.execute("DELETE FROM projection_job WHERE projection_id = ?", (relationship,))
    db.execute(
        "UPDATE projection_job SET status = 'PENDING' WHERE projection_id = ?",
        (episode,),
    )
    db.commit()
    assert _rows(db, "SELECT projection_id, status FROM projection_job") == [
        (episode, "PENDING")
    ]

    new = world.restart()
    degraded = Refusing(_projection_runtime(new), "recover_stale_running")
    coordinator = coordinator_of(new, projections=degraded)
    first = coordinator.run_startup_recovery()
    assert isinstance(first, Ok), first
    assert first.value.projection_recovery_unavailable is True
    assert first.value.projection_jobs == () and first.value.projection_runs == ()
    assert first.value.recovered_moments == (moment_id,)  # the other lines ran
    assert _rows(db, "SELECT projection_id, status FROM projection_job") == [
        (episode, "PENDING")
    ]
    groups_before = _counts(db, "evidence_group")

    second = coordinator.run_startup_recovery()
    assert isinstance(second, Ok), second
    assert second.value.projection_recovery_unavailable is False
    assert relationship in {str(job) for job in second.value.projection_jobs}
    assert _counts(db, "evidence_group") == groups_before
    assert {status for _, status in _rows(
        db, "SELECT projection_id, status FROM projection_job"
    )} == {"COMMITTED"}
    assert _rows(
        db, "SELECT status FROM projection_job WHERE projection_id = ?", (episode,)
    ) == [("COMMITTED",)]


# 3 — degraded-ledger-write


def test_degraded_ledger_write_never_rolls_back_the_delivery(world: World) -> None:
    """degraded-ledger-write（RA §20 + R-INV-010 的形状；RUNTIME §4 step 20）.

    §20 的曝光写失败**不是**投递的失败：开课交付照常落地（moment AWAITING_USER、
    turn COMPLETED/REPLIED_FULL、transcript 有内容），失败只让那一行 §20 事件缺席，
    并把原因送进既有 `ledger_failure` 通道（`_with_exposure` 的 2012-2018）。SKIP 臂
    把这条通道**在公开结果上**钉住：同一个只有写面被拒的 writer 下，SKIP 的 abort 照
    常关闭时刻，而 `TeachingReplyTurnResult` 报 `ledger_event is None` +
    `ledger_failure == "injected ledger refusal"`（同族面 `_record_skip_exposure`
    的 (None, reason) 返回）。**对照组**证明「0 行」不是真空：同一世界第二个会话用
    真 writer 开课 ⇒ 恰一行 `teaching_presented`。

    **降级注入，已声明**：`RefusingLedger` 包住真 store（三个读面仍真），只拒写面。
    (i) 适用：两个会话各自的 CP0 恰一行、SKIP 是新 turn（迟到的控制意图不是重放）。
    (ii) 适用（零形状）：教学 turn 不产 analysis artifact，断言 0。
    (iii) 适用：时刻到 AWAITING_USER 再被 SKIP 关到 CLOSED/USER_SKIP；交付不被回滚。
    (iv) 适用：写失败既不补发也不改交付方向。
    """

    db = world.db
    ledger = SqliteLedgerStore(db, world.fence)
    wiring = AutomaticTurnWiring(
        planner_store=SqlitePlannerRecordStore(db, world.fence),
        teaching=world.teaching,
        ledger=RefusingLedger(ledger),  # type: ignore[arg-type]
    )
    opened = coordinator_of(world, automatic=wiring).request_teaching(
        _teaching_request("cm-p10-2-ledger")
    )
    assert isinstance(opened, Ok), opened
    moment_id = str(opened.value.moment_id)
    turn_id = str(opened.value.turn_id)
    assert _moment_rows(db) == [(moment_id, "AWAITING_USER", None, 2)]
    assert _turn_row(db, turn_id)[:2] == ("COMPLETED", "REPLIED_FULL")
    assert _rows(
        db, "SELECT delivery_state FROM assistant_turn WHERE turn_id = ?", (turn_id,)
    ) == [("SENT_COMPLETE",)]
    content = _rows(db, "SELECT content FROM assistant_turn WHERE turn_id = ?",
                    (turn_id,))
    assert len(content) == 1 and str(content[0][0]).strip()
    assert _counts(db, "planning_ledger", "planning_ledger_event") == {
        "planning_ledger": 0, "planning_ledger_event": 0
    }

    replied = coordinator_of(world, automatic=wiring).respond_to_teaching(
        _reply_request("cm-p10-2-ledger-skip")
    )
    assert isinstance(replied, Ok), replied
    assert replied.value.closure == "USER_SKIP"  # the abort is not blocked
    assert replied.value.ledger_event is None
    assert replied.value.ledger_failure == "injected ledger refusal"
    assert _moment_rows(db) == [(moment_id, "CLOSED", "USER_SKIP", 8)]
    assert _counts(db, "planning_ledger_event") == {"planning_ledger_event": 0}
    assert _counts(db, "analysis_artifact") == {"analysis_artifact": 0}

    control = SqliteConversationStore(db, world.fence).open_conversation(
        "conv-p10-2-ledger-control", user_id=UserId("user-2"),
        persona_id=None, scene_id=None,
    )
    assert isinstance(control, Ok), control
    wiring_real = AutomaticTurnWiring(
        planner_store=SqlitePlannerRecordStore(db, world.fence),
        teaching=world.teaching, ledger=ledger,
    )
    opened_control = coordinator_of(world, automatic=wiring_real).request_teaching(
        _teaching_request("cm-p10-2-ledger-control", "conv-p10-2-ledger-control")
    )
    assert isinstance(opened_control, Ok), opened_control
    assert _rows(db, "SELECT event, ledger_key FROM planning_ledger_event") == [
        ("teaching_presented", FOCUS_TARGET)
    ]


# 4 — scan-read-failure


def test_scan_read_failure_is_named_and_a_raising_one_is_never_empty(
    world: World,
) -> None:
    """scan-read-failure（RA §22 纯读契约；P4-2 F1/F2 的失败容错；P10-0 端口语义）.

    四条读面、三种失败形态，逐条断言「不崩、不静默」在哪一层成立：

    ① **Err 形状的扫面（P4-2 的两条）**：`evidence_proposal_refs` 或
    `retry_pending_teaching_evidence` 返回 Err ⇒ 该腿置具名 `*_unavailable=True`
    且结论保持**空**（controller.py:4258-4259 / :4222-4223）——「没读」与「没有」
    由那个 flag 分开，健康 pass 两条都是 False/() 就是反证；启动仍 Ok；
    ② **读面整体缺席**：`run_startup_recovery` 取不到 `TurnRecordRecoverySource` ⇒
    具名 `Err(DEPENDENCY_UNAVAILABLE)`（:4020-4029），一个 turn 都不扫——fail-closed；
    ③ **异常形状（P10-0 的四类端口）**：那四个协议声明的是 `tuple` 返回，**没有 Err
    通道**；扫描器也没有 try/except，所以不可读**绝不**被吞成空 plan——它直接
    `raise`（本测试在 scanner 上断言），且一个字节都没写。这条与 ① 的一致性写在
    P10-0 的端口 docstring 里（`GenerationActionRecoverySource` 等的 **Not
    scanning it** 段）：没有面的那件事必须看得见。
    **Revisit**：给四类端口加 Err 形状（或给 scanner 加容错）的那一刀要重写 ③ 的
    断言与本节口径。

    **降级注入，已声明**：①用子类覆写（机制事实：`@runtime_checkable` 的
    isinstance 是静态检查，动态代理转发面在它眼里不存在 ⇒ A 半的 `Refusing` 外壳
    对这条腿无效）；②用隐藏单个属性的包装；③用抛错的读面。
    (i) 适用：②的 fail-closed 保证没有 turn 被重放（行数不变）。
    (ii) 适用（零形状）：本类不产 Learning 行。
    (iii) 适用：①的残件**具名分类**（unavailable 标记），②的残件保持原状待下一位
    executor，③的异常响亮而不静默。
    (iv) N/A：无投递（本类没有投递面）。
    """

    db = world.db
    healthy = coordinator_of(world).run_startup_recovery()
    assert isinstance(healthy, Ok), healthy
    assert healthy.value.evidence_ref_scan_unavailable is False
    assert healthy.value.teaching_evidence_retry_unavailable is False
    assert healthy.value.dangling_evidence_refs == ()
    assert healthy.value.committed_evidence_proposals == ()

    refs = coordinator_of(
        world, teaching=RefusingEvidenceRefs(world.teaching_store)
    ).run_startup_recovery()
    assert isinstance(refs, Ok), refs
    assert refs.value.evidence_ref_scan_unavailable is True
    assert refs.value.dangling_evidence_refs == ()  # "not read", never "none"

    retry = coordinator_of(
        world,
        learning_controller=RefusingEvidenceRetry(world.learning),
    ).run_startup_recovery()
    assert isinstance(retry, Ok), retry
    assert retry.value.teaching_evidence_retry_unavailable is True
    assert retry.value.committed_evidence_proposals == ()

    before = _counts(db, *COUNTED_TABLES)
    missing = coordinator_of(
        world, commands=NoTurnRecoveryRead(world.store)
    ).run_startup_recovery()
    assert isinstance(missing, Err), missing
    assert missing.error.code is DomainErrorCode.DEPENDENCY_UNAVAILABLE
    assert "TurnRecordRecoverySource" in missing.error.message
    assert _counts(db, *COUNTED_TABLES) == before

    with pytest.raises(RuntimeError, match="the §22 residue read exploded"):
        StartupRecoveryScanner(
            world.store, make_lease(world.fence), world.teaching,
            delivery_records=RaisingDeliveryRead(),  # type: ignore[arg-type]
        ).scan()
    assert _counts(db, *COUNTED_TABLES) == before


# 5 — epoch-race-action-claim


def test_epoch_race_action_claim_fences_the_old_worker_and_arms_the_new_one(
    world: World,
) -> None:
    """epoch-race-action-claim（RUNTIME §24；STATE_MACHINES §17.1 rule 3；IP §11 的
    GenerationActionIntent）.

    一个旧 epoch 的非终态 action，在**新 epoch 已开**之后被旧 worker 的 store 对象
    触碰：写事务内的 `_require_current_epoch`（generation_store.py:98-105）先 `raise`
    `StaleStoreEpochError` —— 合法边（REQUESTED → GENERATING）也一样，因为 fence 在
    边检查之后、UPDATE 之前（:168-172）。新 epoch 的 `claim_action_for_recovery` 不受
    影响：同一个 stable action_id 被重挂在 REQUESTED、owner 换成新 epoch（:242-256）；
    **claim 之后**旧 worker 再写仍然被拒（row 的 owner 已不是它的 epoch），而新 epoch
    自己的推进成功。

    (i) 适用：本类只碰 action，不重入任何 user turn（turn 行断言不动）。
    (ii) 适用：断言 0 个 evidence group（无 analysis leg 落盘）。
    (iii) 适用：work 被具名（行的状态可读）+ 被新 epoch 的 claim 接住并推进。
    (iv) N/A：无投递（本类没有投递面）。
    """

    db = world.db
    turn_id, action_id = _open_turn_with_action(world, "cm-p10-2-race-action")
    assert _action_row(db, action_id) == (action_id, "REQUESTED", 1)
    turn_before = _turn_row(db, turn_id)

    new = world.restart()
    with pytest.raises(StaleEpochError):
        world.generation.transition_action(
            ActionId(action_id),
            GenerationActionStatus.REQUESTED,
            GenerationActionStatus.GENERATING,
        )
    with pytest.raises(StaleEpochError):
        world.generation.create_action(
            _action_record(
                "act-p10-2-race-b", turn_id, f"dcy-{turn_id}",
                GenerationActionStatus.REQUESTED,
            )
        )
    assert _action_row(db, action_id) == (action_id, "REQUESTED", 1)
    assert _counts(db, "generation_action_intent") == {
        "generation_action_intent": 1
    }

    claimed = new.generation.claim_action_for_recovery(ActionId(action_id))
    assert isinstance(claimed, Ok), claimed
    assert claimed.value.status is GenerationActionStatus.REQUESTED
    assert int(claimed.value.owner_epoch) == new.fence.current
    assert _action_row(db, action_id) == (action_id, "REQUESTED", new.fence.current)

    with pytest.raises(StaleEpochError):  # the old worker is still fenced
        world.generation.transition_action(
            ActionId(action_id),
            GenerationActionStatus.REQUESTED,
            GenerationActionStatus.GENERATING,
        )
    assert _action_row(db, action_id) == (action_id, "REQUESTED", new.fence.current)

    advanced = new.generation.transition_action(
        ActionId(action_id),
        GenerationActionStatus.REQUESTED,
        GenerationActionStatus.GENERATING,
    )
    assert isinstance(advanced, Ok), advanced
    assert _action_row(db, action_id) == (
        action_id, "GENERATING", new.fence.current
    )
    assert _turn_row(db, turn_id) == turn_before
    assert _counts(db, "evidence_group") == {"evidence_group": 0}


# 6 — epoch-race-turn-canonicalize


def test_epoch_race_turn_canonicalize_is_fenced_and_unpolluted(world: World) -> None:
    """epoch-race-turn-canonicalize（RUNTIME §24；DATA_MODEL §19；IP §11 的
    TurnRecord）.

    旧 worker 在**新 epoch 已开**之后写 transcript：`canonicalize_assistant_turn`
    在写之前 `raise` `StaleStoreEpochError`（conversation/store.py:488 的
    `_require_current_epoch`；P3-0 已为此立过测试），transcript 一个字节不动，且事务
    不留在打开状态；新 epoch 自己 `claim_turn_for_recovery` + canonicalize 落到**唯一
    一行**、再重放同一内容仍返回同一行。

    **已登记的第二臂（不是本类主场的反例，而是同一竞争的另一半）**：同一 store 的
    `terminalize_turn` / `transition_turn` 是**更弱的箍**——它们只比 row 的
    owner_epoch 与 store 自持的 epoch，从不查「全库最新 epoch」；该事实写在
    conversation/store.py:470-477 的 docstring 里（P3-0 review F2 的更正自认，
    "whether those two units gain a store-level fence is an open P3+ question"）。
    本刀据实把这一臂断言为 **as-found** 并登记 Revisit：某个切面给这两个 unit 加
    store 级 fence 时，这条断言必须随之改写（任务书本类句写的是 canonicalize/
    terminalize 都被拒；canonicalize 成立，terminalize 不成立——据实驳回）。

    (i) 适用：陈旧内容永不进 transcript（两种 arm 后 assistant_turn 恰一行）。
    (ii) 适用：本类无 analysis leg，断言 0 组。
    (iii) 适用：新 epoch 的残件到达可解释的 durable 行（claim + canonicalize）。
    (iv) N/A：无投递（本类没有投递面）。
    """

    db = world.db
    turn_one = _commit_chat_turn(world.store, "cm-p10-2-race-one")
    turn_two = _commit_chat_turn(world.store, "cm-p10-2-race-two")
    transcript_before = _counts(db, "assistant_turn", "turn_record")

    new = world.restart()
    with pytest.raises(StaleEpochError):
        world.store.canonicalize_assistant_turn(
            _assistant_for(world, turn_one, "stale draft", "act-p10-2-stale-one")
        )
    assert _counts(db, "assistant_turn", "turn_record") == transcript_before
    assert db.in_transaction is False

    claimed = new.store.claim_turn_for_recovery(TurnId(turn_one))
    assert isinstance(claimed, Ok), claimed
    canonical = new.store.canonicalize_assistant_turn(
        _assistant_for(world, turn_one, "the recovered reply", "act-p10-2-race-one")
    )
    assert isinstance(canonical, Ok), canonical
    replay = new.store.canonicalize_assistant_turn(
        _assistant_for(world, turn_one, "the recovered reply", "act-p10-2-race-one-2")
    )
    assert isinstance(replay, Ok), replay
    assert replay.value == canonical.value
    assert _rows(
        db, "SELECT content FROM assistant_turn WHERE turn_id = ?", (turn_one,)
    ) == [("the recovered reply",)]

    with pytest.raises(StaleEpochError):  # still fenced after the new epoch acted
        world.store.canonicalize_assistant_turn(
            _assistant_for(world, turn_one, "second stale draft", "act-p10-2-stale-2")
        )
    assert _counts(db, "assistant_turn") == {"assistant_turn": 1}

    # arm B, as-found: the weaker fence (the registration cited above)
    transitioned = world.store.transition_turn(
        TurnId(turn_two), 1, TurnStatus.GENERATING
    )
    assert isinstance(transitioned, Ok), transitioned
    terminal = world.store.terminalize_turn(
        TurnId(turn_two), TurnOutcome.REPLIED_FULL
    )
    assert isinstance(terminal, Ok), terminal
    assert _turn_row(db, turn_two)[:2] == ("COMPLETED", "REPLIED_FULL")
    assert _counts(db, "assistant_turn") == {"assistant_turn": 1}  # no content
    adopted = new.store.claim_turn_for_recovery(TurnId(turn_two))
    assert isinstance(adopted, Ok), adopted  # already terminal ⇒ unchanged
    assert _counts(db, "evidence_group") == {"evidence_group": 0}


# 7 — late-callback-foreign-epoch


def test_late_callback_foreign_epoch_is_discarded_with_zero_canonical_effect(
    tmp_path: Path,
) -> None:
    """late-callback-foreign-epoch（STATE_MACHINES §14 late-result rule；RUNTIME
    §24.1；IP §11 的 GenerationActionIntent）.

    外来 epoch 的 provider 结果：`accept_late_result` 答 `DISCARDED_FENCED_EPOCH`
    （controller.py:3729-3731）——它能判这条结果「不属于它能处理的行动」，因此
    audited 而不 canonicalize。snapshot（P9-3 的 helper，导入复用）逐字段守恒：
    transcript 内容/状态、§22 行、§21.1 行、provider attempt 计数、切片 outcome
    全部不动；**残件不被丢弃**：同一 world 在新 epoch 的扫描下仍被具名为 TURN +
    ACTION（executor = 入口重入，p10-0 的执行者表）。

    (i) 适用：已提交 user turn 不被重放（turn 行守恒、无第二行）。
    (ii) 适用（零形状）：本窗口无 analysis leg 落盘，snapshot 的 attempt/group 计数
    守恒且 group 总数断言 0。
    (iii) 适用：work 被具名分类（TURN/ACTION items 仍在），不是被「丢掉的回调」。
    (iv) 适用：迟到结果不进 transcript、不触发任何发送。
    """

    world = stream_world(tmp_path)
    turn_id, action_id = open_turn_with_action(world, "cmid-p10-2-late-foreign")
    before = snapshot(world, str(turn_id), action_id)
    assert before["assistant_rows"] == 0
    assert before["delivery_rows"] == 0
    assert before["attempt_count"] == 0

    fence2 = epoch.open_runtime_epoch(world.db)
    lease2 = ConversationCoordinatorLease()
    lease2.adopt_epoch(fence2.current)
    bound = bind(world)
    try:
        result = coordinator_over(bound, lease=lease2).accept_late_result(
            action_id, "the answer, from a process that is gone"
        )
    finally:
        bound.db.close()
    assert isinstance(result, Ok), result
    assert result.value == "DISCARDED_FENCED_EPOCH"
    assert snapshot(world, str(turn_id), action_id) == before
    assert count(world.db, "evidence_group") == 0

    new_store = SqliteConversationStore(world.db, fence2)
    new_generation = AssemblyGenerationStore(world.db, fence2)
    # the pre-P10-0 plan shape (three ports): the turn is the only residue name
    assert _scan(new_store, lease2, None) == (
        (RECOVERY_KIND_TURN, str(turn_id), RECOVERY_DISPOSITION_RESUME_ANALYSIS),
    )
    with_ports = _scan(
        new_store, lease2, None, generation_actions=new_generation,
        teaching_moments=SqliteTeachingStore(world.db, fence2),
        analysis_artifacts=SqliteLearningStore(world.db, fence2),
        delivery_records=SqliteDeliveryRecordStore(world.db, fence2),
    )
    assert (RECOVERY_KIND_TURN, str(turn_id),
            RECOVERY_DISPOSITION_RESUME_ANALYSIS) in with_ports
    assert _kinds(with_ports, RECOVERY_KIND_ACTION) == [str(action_id)]
    assert _rows(
        world.db, "SELECT status FROM turn_record WHERE turn_id = ?", (str(turn_id),)
    ) == [("USER_COMMITTED",)]


# 8 — late-callback-cancelled


def test_late_callback_cancelled_or_superseded_changes_nothing(
    tmp_path: Path,
) -> None:
    """late-callback-cancelled（STATE_MACHINES §14/§18；P9-3 读法；IP §11 的
    ServerDeliveryRecord）.

    两条取消面各一臂，都在 late 回调前后逐字段比对：

    ① **barge-in 取消**（`InterruptingFactory` 在流式交付中途写真实 interrupt 行）：
    §22 行 CANCELLED、transcript 恰是已送出的那一段、切片 outcome
    CANCELLED_BY_USER；迟到结果答 `DISCARDED_TERMINAL_ACTION` 且 snapshot 全等；
    ② **superseded/§15 硬失效**（陈旧 turn 的交付被 PreDeliveryGuard 判
    INVALIDATE_ACTION）：根本没有 transcript 行、§22 行 CANCELLED 空前缀；迟到结果
    同样零副作用。

    **被迫世界，已声明**：①的中断写在 `take` 内部（p9-3 的源自己写请求），②的陈旧
    形状由「先开后来的 turn 再重入陈旧 cmid」造出——两者都是 shipped 面能产生的
    durable 形状。
    (i) 适用：已提交 user turn 不重放（snapshot 的 assistant 行/内容/切片 outcome
    逐字段守恒，两次 snapshot 之间没有第二个 turn）。
    (ii) 适用（零形状）：0 组（断言 group 计数）。
    (iii) 适用：cancel 本身已是可解释终态（CANCELLED / CANCELLED_BY_USER）。
    (iv) 适用——本类的主场：迟到结果既不补发也不改写任何已冻结点。
    """

    chunks = pieces(REPLY, 3)
    world = stream_world(tmp_path)
    factory = InterruptingFactory(world=world, chunks=chunks, after_chunks=1)
    completion = begin_turn_ok(
        coordinator_for(world, transport=factory), "cmid-p10-2-late-cancelled"
    )
    turn_id = str(completion.turn_id)
    action_id = action_of(world, turn_id)
    before = snapshot(world, turn_id, action_id)
    assert before["delivery_state"] == "CANCELLED"
    assert before["slice_outcome"] == "CANCELLED_BY_USER"
    assert before["assistant_content"] == "".join(chunks[:1])
    assert before["attempt_count"] == 1
    discarded = coordinator_for(world).accept_late_result(action_id, "too late")
    assert isinstance(discarded, Ok), discarded
    assert discarded.value == "DISCARDED_TERMINAL_ACTION"
    assert snapshot(world, turn_id, action_id) == before
    assert count(world.db, "evidence_group") == 0

    other = stream_world_mkdir(tmp_path / "superseded")
    stale_turn, _ = open_turn_with_action(other, "cmid-p10-2-late-stale")
    coordinator = coordinator_for(other)
    begin_turn_ok(coordinator, "cmid-p10-2-late-later")
    begin_turn_ok(coordinator, "cmid-p10-2-late-stale")
    stale_action = action_of(other, str(stale_turn))
    stale_before = snapshot(other, str(stale_turn), stale_action)
    assert stale_before["guard_decisions"] == ("INVALIDATE_ACTION",)
    assert stale_before["delivery_state"] == "CANCELLED"
    assert stale_before["assistant_content"] is None
    stale_discarded = coordinator_for(other).accept_late_result(
        stale_action, "also too late"
    )
    assert isinstance(stale_discarded, Ok), stale_discarded
    assert stale_discarded.value == "DISCARDED_TERMINAL_ACTION"
    assert snapshot(other, str(stale_turn), stale_action) == stale_before
    assert count(other.db, "evidence_group") == 0


# 9 — multi-residue-coexist


def test_multi_residue_coexist_is_named_in_order_and_each_executor_answers(
    six_kind: SixKind,
) -> None:
    """multi-residue-coexist（IP §11 七类残件 + RA §22；P10-0 的四类新 kind）.

    一次扫描把六类同现的残件全部具名，顺序是 P10-0 钉的
    TURN → ACTION → MOMENT → ANALYSIS → DELIVERY → LOCK（recovery.py:507-545）；
    **startup 线自己的 plan 只带 TURN + LOCK**（它只插三个端口，R5），所以另外四类
    在这一线上的答案是**无 apply**——逐类点名 executor：

    - **TURN**（聊天 turn）：startup 线的两条和解都不收它（无 moment 归
      `_close_residual_turns` 的 continue、action 非 TERMINAL 归
      `reconcile_delivering_residue` 的 continue）⇒ 仍 USER_COMMITTED，executor =
      入口重入；
    - **ACTION**：同上，入口的 claim 分支（controller.py:1543-1558）会重挂它；
    - **ANALYSIS**：入口重入重放 analysis leg（本测试把三者的效果一起驱动）；
    - **MOMENT + LOCK**：本线唯一真 apply 的两类——`recover_orphan_teaching`
      释放锁并把 moment 关到 CLOSED/SYSTEM_RECOVERY_ABORT（本测试断言）；
    - **DELIVERY**：无 apply（startup 的 plan 不带它），入口的重投递被 §22 记录面
      自己的不变量拒（「开始瞬间是内容」），于是 turn 落 FAILED_USER_VISIBLE 而
      §22 行**一步未动**——这就是 (iv) 的保守方向：不确定时绝不盲目重发。

    (i) 适用：入口复用同一个 turn_id（断言 turn 行数不变、id 相同）。
    (ii) 适用：同一个 analysis id 到 COMMITTED、evidence group 恰 1。
    (iii) 适用：六类各自到「被 apply」或「具名 + executor」的可解释处。
    (iv) 适用——见上 DELIVERY 段。
    """

    world = six_kind.world
    db = world.db
    new = world.restart()
    new_deliveries = SqliteDeliveryRecordStore(db, new.fence)
    plan = new.scan(deliveries=new_deliveries)
    assert [kind for kind, _, _ in plan] == [
        RECOVERY_KIND_TURN, RECOVERY_KIND_ACTION, RECOVERY_KIND_MOMENT,
        RECOVERY_KIND_ANALYSIS, RECOVERY_KIND_DELIVERY, RECOVERY_KIND_LOCK,
    ]
    assert plan == (
        (RECOVERY_KIND_TURN, six_kind.turn_id, RECOVERY_DISPOSITION_RESUME_ANALYSIS),
        (RECOVERY_KIND_ACTION, six_kind.action_id,
         RECOVERY_DISPOSITION_RESUME_ACTION),
        (RECOVERY_KIND_MOMENT, six_kind.moment_id, MOMENT_RECOVERY_ACTION),
        (RECOVERY_KIND_ANALYSIS, six_kind.analysis_id,
         RECOVERY_DISPOSITION_RESUME_ANALYSIS),
        (RECOVERY_KIND_DELIVERY, six_kind.action_id,
         RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY),
        (RECOVERY_KIND_LOCK, six_kind.moment_id, TEACHING_LOCK_RECOVERY_ACTION),
    )
    assert _kinds(plan, RECOVERY_KIND_LOCK) == [six_kind.moment_id]

    outcome = coordinator_of(new).run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert {item.kind for item in outcome.value.plan} == {
        RECOVERY_KIND_TURN, RECOVERY_KIND_LOCK
    }
    assert outcome.value.recovered_moments == (six_kind.moment_id,)
    assert outcome.value.closed_turns == ()
    assert outcome.value.reconciled_turns == ()
    assert _rows(
        db, "SELECT lifecycle_state, abort_reason FROM teaching_moment"
    ) == [("CLOSED", "SYSTEM_RECOVERY_ABORT")]
    assert _counts(db, "active_teaching_lock") == {"active_teaching_lock": 0}
    # the four kinds the startup line does not consume are exactly as they were
    assert _turn_row(db, six_kind.turn_id)[:2] == ("USER_COMMITTED", None)
    assert _action_row(db, six_kind.action_id) == (
        six_kind.action_id, "REQUESTED", 1
    )
    assert _rows(db, "SELECT status FROM analysis_artifact") == [("PRODUCED",)]
    assert _delivery_row(db, six_kind.action_id) == ("SENDING", "", 0, None)

    watching = WatchingClaimStore(new.generation)
    done = _begin_turn(
        coordinator_of(
            new, actions=watching, delivery_records=new_deliveries
        ),
        "cm-p10-2-six-pending",
    )
    assert str(done.turn_id) == six_kind.turn_id  # the same turn, adopted
    assert watching.claims == [
        (six_kind.action_id, "REQUESTED", new.fence.current)
    ]
    assert done.outcome == "FAILED_USER_VISIBLE"
    assert done.turn_status is TurnStatus.FAILED_FINAL
    assert done.reply_text is None
    assert done.delivery_state == "FAILED"
    assert "the start instant is content" in (done.delivery_failure_reason or "")
    assert _rows(db, "SELECT status FROM analysis_artifact WHERE analysis_id = ?",
                 (six_kind.analysis_id,)) == [("COMMITTED",)]
    assert _counts(db, "evidence_group", "evidence_claim") == {
        "evidence_group": 1, "evidence_claim": 0
    }
    assert _delivery_row(db, six_kind.action_id) == ("SENDING", "", 0, None)
    assert _counts(db, "assistant_turn") == {"assistant_turn": 1}  # the opening's
    assert _turn_row(db, six_kind.teaching_turn_id)[:2] == (
        "COMPLETED", "REPLIED_FULL"
    )


# 10 — residue-then-normal-turn


def test_residue_then_normal_turn_share_the_conversation_without_pollution(
    world: World,
) -> None:
    """residue-then-normal-turn（STATE_MACHINES §9 orphan lock 的 sweep；RUNTIME
    §24；IP §11 的 TeachingLockLease）.

    同一会话先 recovery 再正常 `begin_turn`：sweep 把孤儿锁释放、把 moment 关到
    CLOSED/SYSTEM_RECOVERY_ABORT，而**这个 moment 的 turn 一行未动**（owner 仍是死
    epoch）；随后普通 turn 照常走完（REPLIED_FULL/SENT_COMPLETE、新 action 的
    owner 是新 epoch），并且**会话没有被封**——同一个会话来一次新的教学开课仍 ALLOW，
    旧 moment 的行（含 state_version）逐列不动。

    (i) 适用：recovery 前已提交的 turn 逐列不动（重放/改写都没有）。
    (ii) 适用：recovery 自己不写 Learning 行；新 turn 恰产 1 组（不重复）。
    (iii) 适用：锁被释放、会话可再教学 = 残件到达可解释终局而不是把会话钉死。
    (iv) 适用：为已交付的 opening **不重发**（`reconciled_turns`/`aborted_openings`
    都空，assistant 行数在 normal turn 前仍是 1）。
    """

    db = world.db
    opened = coordinator_of(world).request_teaching(
        _teaching_request("cm-p10-2-res-open")
    )
    assert isinstance(opened, Ok), opened
    moment_id = str(opened.value.moment_id)
    turn_id = str(opened.value.turn_id)
    turn_before = _turn_row(db, turn_id)
    learning_before = _counts(db, "analysis_artifact", "evidence_group")

    new = world.restart()
    outcome = coordinator_of(new).run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.recovered_moments == (moment_id,)
    assert outcome.value.aborted_openings == ()
    assert outcome.value.reconciled_turns == ()
    assert outcome.value.closed_turns == ()
    assert _moment_rows(db) == [(moment_id, "CLOSED", "SYSTEM_RECOVERY_ABORT", 3)]
    assert _counts(db, "active_teaching_lock") == {"active_teaching_lock": 0}
    assert _counts(db, "assistant_turn") == {"assistant_turn": 1}
    assert _counts(db, "analysis_artifact", "evidence_group") == learning_before

    done = _begin_turn(coordinator_of(new), "cm-p10-2-res-chat")
    assert done.outcome == "REPLIED_FULL"
    assert done.delivery_state == "SENT_COMPLETE"
    assert _turn_row(db, turn_id) == turn_before  # the old turn, untouched
    assert _counts(db, "assistant_turn") == {"assistant_turn": 2}
    assert _counts(db, "evidence_group") == {"evidence_group": 1}

    second = coordinator_of(new).request_teaching(
        _teaching_request("cm-p10-2-res-second")
    )
    assert isinstance(second, Ok), second
    assert second.value.gate_decision == "ALLOW"
    assert second.value.moment_state is MomentState.AWAITING_USER
    assert str(second.value.moment_id) != moment_id
    assert {row[0]: row[1:] for row in _moment_rows(db)} == {
        moment_id: ("CLOSED", "SYSTEM_RECOVERY_ABORT", 3),
        str(second.value.moment_id): ("AWAITING_USER", None, 2),
    }


# 11 — interrupt-during-recovery


def test_interrupt_during_recovery_keeps_the_request_and_the_reconciler_takes_it(
    world: World,
) -> None:
    """interrupt-during-recovery（RA §17.1 rules 3-5；IP §11 的 interrupt_request）.

    恢复过程中用户发新输入：本测试把 durable interrupt 行写在**同一次
    `run_startup_recovery` 之内**（投影腿的第一步，写完之后才转发——p9-3 的
    「源自写请求」同形而用于 recovery）。断言三段：

    ① **恢复不被破坏**：pass 照常 Ok，且它自己的活（孤立锁 sweep）照做；
    ② **请求持久化**：`list_pending_interrupts_for_conversation` 仍具名它，恢复
    对当前 epoch 的活 turn/action 一动未动；
    ③ **reconciler 接管**：下一个入口（`begin_turn`）在 guard 内先和解
    （controller.py:1355-1359 → :1116-1181）——被点名的 turn 落
    CANCELLED_BY_USER、action 落 TERMINAL、pending 清空，且**没有为它发明任何
    assistant 行**（未投递的 provider 输出永不进 transcript）。

    **被迫世界，已声明**：中断写在投影腿里（一个 real `CP4ProjectionRuntime` 的
    包装，先写请求再转发），因为 shipped 面没有「恢复中途」这个可注入的钟。
    (i) 适用：被中断 turn 不被重放（它落 CANCELLED_BY_USER，不是重新生成）。
    (ii) 适用：Learning 行只属新 turn（恰 1 组、1 artifact，且不是被中断 turn 的）。
    (iii) 适用：中断是 durable 的（请求行 + 取消后的行），并到达可解释终态。
    (iv) 适用：被中断的 turn 一步都没送（无 assistant 行），不盲发。
    """

    db = world.db
    opened = coordinator_of(world).request_teaching(
        _teaching_request("cm-p10-2-11-open")
    )
    assert isinstance(opened, Ok), opened
    moment_id = str(opened.value.moment_id)

    new = world.restart()
    live_turn, live_action = _open_turn_with_action(new, "cm-p10-2-11-live")
    spy = InterruptingProjections(
        _projection_runtime(new), store=new.store, action_id=live_action,
        turn_id=live_turn, input_id="in-p10-2-11",
    )
    outcome = coordinator_of(new, projections=spy).run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert spy.fired is True
    assert outcome.value.recovered_moments == (moment_id,)

    pending = new.store.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(pending, Ok), pending
    assert [(request.input_id, request.active_action_id)
            for request in pending.value] == [
        ("in-p10-2-11", ActionId(live_action))
    ]
    assert _turn_row(db, live_turn)[:2] == ("USER_COMMITTED", None)
    assert _action_row(db, live_action) == (
        live_action, "REQUESTED", new.fence.current
    )

    done = _begin_turn(coordinator_of(new), "cm-p10-2-11-next")
    assert done.outcome == "REPLIED_FULL"
    assert _turn_row(db, live_turn)[:2] == (
        "CANCELLED_BY_USER", "CANCELLED_BY_USER"
    )
    assert _action_row(db, live_action) == (
        live_action, "TERMINAL", new.fence.current
    )
    after = new.store.list_pending_interrupts_for_conversation(CONV)
    assert isinstance(after, Ok), after
    assert after.value == ()
    assert _counts(db, "assistant_turn") == {"assistant_turn": 2}
    assert _rows(
        db, "SELECT COUNT(*) FROM assistant_turn WHERE turn_id = ?", (live_turn,)
    ) == [(0,)]
    assert _counts(db, "analysis_artifact", "evidence_group") == {
        "analysis_artifact": 1, "evidence_group": 1
    }
    assert _rows(db, "SELECT turn_id FROM analysis_artifact") == [
        (str(done.turn_id),)  # the new turn's, never the interrupted one's
    ]


# 12 — idempotent-second-startup


def test_idempotent_second_startup_plans_nothing_and_writes_nothing(
    six_kind: SixKind,
) -> None:
    """idempotent-second-startup（RA §22 的幂等扫描；RUNTIME §24 的恢复所有权）.

    同一新 epoch 的紧接第二次 startup：**零写入**（全表计数逐值不变）、
    **epoch 数不动**（pass 不开新 epoch）、第二次的 plan 只剩「executor 是入口」的
    那一项（P10-0 执行者表的直接后果：startup 线只 apply 它拥有的 kind）；入口把
    自己那几项接走之后，六类扫描**为空**——残件全部到达可解释处，没有一件留下。

    (i) 适用：turn 行数与内容跨两次 pass 不变（不重放已提交 user turn）。
    (ii) 适用：evidence group **恰 1**（直接绝对值断言）；analysis 的「恰 1」在本体只有
    全表计数不变（不变性）在托——其绝对值断言在类 9（同一 fixture 断到 COMMITTED）；
    **收窄**（评审 F1）：本类 (ii) 的主张到「group 绝对值 + analysis 无新增」为止，
    Revisit = 本类需要独立给 analysis 绝对值时补断言。
    (iii) 适用——本类的主场：第一次 pass 具名全部；终局后扫描空。
    (iv) N/A：无投递（§22 行由类 9 的入口臂负责，见其 DELIVERY 段）。
    """

    world = six_kind.world
    db = world.db
    new = world.restart()
    epochs_before = _rows(db, "SELECT COUNT(*), MAX(epoch) FROM runtime_epoch")
    first = coordinator_of(new).run_startup_recovery()
    assert isinstance(first, Ok), first
    assert first.value.recovered_moments == (six_kind.moment_id,)

    before = _counts(db, *COUNTED_TABLES)
    second = coordinator_of(new).run_startup_recovery()
    assert isinstance(second, Ok), second
    assert _counts(db, *COUNTED_TABLES) == before
    assert [item.kind for item in second.value.plan] == [RECOVERY_KIND_TURN]
    assert [item.id for item in second.value.plan] == [six_kind.turn_id]
    assert second.value.recovered_moments == ()
    assert _rows(db, "SELECT COUNT(*), MAX(epoch) FROM runtime_epoch") == epochs_before

    scanned = new.scan(deliveries=SqliteDeliveryRecordStore(db, new.fence))
    assert [kind for kind, _, _ in scanned] == [
        RECOVERY_KIND_TURN, RECOVERY_KIND_ACTION,
        RECOVERY_KIND_ANALYSIS, RECOVERY_KIND_DELIVERY,
    ]

    watching = WatchingClaimStore(new.generation)
    _begin_turn(
        coordinator_of(
            new, actions=watching,
            delivery_records=SqliteDeliveryRecordStore(db, new.fence),
        ),
        "cm-p10-2-six-pending",
    )
    assert new.scan(deliveries=SqliteDeliveryRecordStore(db, new.fence)) == ()
    assert _counts(db, "evidence_group") == {"evidence_group": 1}
    assert _rows(db, "SELECT COUNT(*), MAX(epoch) FROM runtime_epoch") == epochs_before


# the table itself + the two honesty pins


def test_the_summary_table_and_the_per_class_answers_agree() -> None:
    """R3 的可执行半边：本文件的 R3 表、12 类映射、四问短答、逐类 docstring 与
    `INVARIANTS` **五处一致**——A 半评审的 MEDIUM 就是这条链上的一处不一致。

    检查项：①每个 tag 在 docstring 里有且只有一行，且该行逐字含四条短答；
    ②每个 tag 的 snake_case 是至少一个 `test_` 函数名的前缀，且 12 个 tag 覆盖的
    测试 + 两条诚实钉 == 本模块全部 `test_` 函数（没有测试逃出表外）；
    ③每个 tag 的每个 cited face 仍是 `FACE_SOURCES` 里某个模块的 def/class；
    ④`SCENARIOS`、`INVARIANTS`、docstring 的三张表的 tag 集完全相同；
    ⑤每个类测试的 docstring 逐字含它那条 `INVARIANTS` 的四条短答。
    """

    module = sys.modules[__name__]
    doc = module.__doc__ or ""
    tags = [tag for tag, _, _ in SCENARIOS]
    assert len(tags) == len(set(tags)) == 12
    assert set(tags) == set(INVARIANTS)
    table = _docstring_table(doc)
    assert set(table) == set(tags)
    for tag, answers in table.items():
        expected = tuple(
            f"({_ROMAN[index]}) {answer}"
            for index, answer in enumerate(INVARIANTS[tag])
        )
        assert answers == expected, tag
    names = [name for name in vars(module) if name.startswith("test_")]
    pins = {
        "test_the_summary_table_and_the_per_class_answers_agree",
        "test_the_four_new_kinds_have_no_line_consuming_them",
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in FACE_SOURCES)
    covered: set[str] = set()
    for tag, residue, faces in SCENARIOS:
        assert residue
        answers = INVARIANTS[tag]
        line = _table_line(doc, tag)
        for index, answer in enumerate(answers):
            marker = f"({_ROMAN[index]}) {answer}"
            assert marker in line, (tag, marker)
        slug = tag.replace("-", "_").lower()
        matching = [name for name in names if name.startswith(f"test_{slug}")]
        assert matching, tag
        covered.update(matching)
        for name in matching:
            test_doc = getattr(module, name).__doc__ or ""
            for index, answer in enumerate(answers):
                assert f"({_ROMAN[index]}) {answer}" in test_doc, (tag, name, index)
        for face in faces:
            assert f"def {face}" in source or f"class {face}" in source, face
    assert covered | pins == set(names), set(names) - covered - pins
    assert len(names) == len(covered) + len(pins)
    assert {
        RECOVERY_DISPOSITION_RESUME_ANALYSIS,
        RECOVERY_DISPOSITION_RESUME_ACTION,
        RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY,
        TEACHING_LOCK_RECOVERY_ACTION,
        MOMENT_RECOVERY_ACTION,
    } == {
        "RESUME_ANALYSIS", "RESUME_ACTION_BY_STABLE_ACTION_ID",
        "CONSERVATIVE_DELIVERY_RECONCILIATION",
        "RELEASE_ORPHAN_TEACHING_LOCK", "CLOSE_ORPHAN_MOMENT",
    }


_ROMAN = ("i", "ii", "iii", "iv")


def _docstring_table(doc: str) -> dict[str, tuple[str, str, str, str]]:
    """The module docstring's per-class rows: tag → the four short answers.

    Each class owns two lines — a tag line (no ``|`` cells) and the answers
    line right below it with exactly four ``(k) answer`` cells. The other
    table in the docstring (the mapping one, three cells on the tag's own
    line) is skipped by the cell count.
    """

    rows: dict[str, tuple[str, str, str, str]] = {}
    lines = doc.splitlines()
    for index, line in enumerate(lines[:-1]):
        head = line.split()
        tag = head[-1] if head else ""
        if tag not in INVARIANTS or "|" in line:
            continue
        cells = [cell.strip() for cell in lines[index + 1].split("|")]
        assert len(cells) == 4, lines[index + 1]
        rows[tag] = (cells[0], cells[1], cells[2], cells[3])
    return rows


def _table_line(doc: str, tag: str) -> str:
    lines = doc.splitlines()
    for index, line in enumerate(lines[:-1]):
        head = line.split()
        if head and head[-1] == tag and "|" not in line:
            return lines[index + 1]
    raise AssertionError(f"no docstring row for {tag}")


def test_the_four_new_kinds_have_no_line_consuming_them(world: World) -> None:
    """p10-0 R5 的交付事实，在本半的**失败形态**下再钉一次：四类新 kind 由扫描
    具名，而 startup 线自己的 plan 只带 TURN + LOCK——所以类 4/9/12 里「无 apply」
    的那些答案不是遗漏，而是**今日没有消费者**这个事实（recovery.py 的执行者表：
    MOMENT 的 CLOSE_ORPHAN_MOMENT 一行自己写着「无 (this cut classifies only)」）。

    本测试不重复 A 半那份同题钉子（它钉的是消费面）：这里钉的是**失败面**的后果——
    四类 kind 缺席时，startup 的 outcome 也照样 Ok，且它们的 durable 行一步未动。
    """

    db = world.db
    turn_id, action_id = _open_turn_with_action(world, "cm-p10-2-consumption")
    new = world.restart()
    outcome = coordinator_of(new).run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert [item.kind for item in outcome.value.plan] == [RECOVERY_KIND_TURN]
    assert outcome.value.projection_jobs == ()
    assert _action_row(db, action_id) == (
        action_id, "REQUESTED", 1
    )  # the ACTION residue: named by the scan, untouched by the line
    assert _turn_row(db, turn_id)[0] == "USER_COMMITTED"
    assert _counts(db, "analysis_artifact") == {"analysis_artifact": 0}
