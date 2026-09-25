"""p10-1 —— 25 类 runtime failure scenario 套件 A（CP0–CP3 崩溃窗口 13 类）。

IP §11 的验收句是「复现 OQ-025A 25 类 runtime failure scenario」，而 OQ-025A 在
仓内**无载体**（只有 `docs/IMPLEMENTATION_PLAN.md:496` 一句）⇒ 按 `OQ-024A→60 例`
/`OQ-023A→43 例`先例走**可执行替代**（开工 DEC `DEC-OPI-9dba34fb-….29` R7）：以
**RA §23 五 checkpoint × IP §11 残件类**为网格自建 25 类。本文件是 **A 半**：
CP0–CP3 崩溃窗口 **13 个命名场景**，逐类一个测试函数；B 半（降级/竞态/残件）归
p10-2。本文件**不是**既有 61+ 条 crash/recovery 回归的重复：那些是零散回归，这是
命名网格，且它把 p10-0 落地的四类新扫描 kind（`ACTION`/`MOMENT`/`ANALYSIS`/
`DELIVERY`，**今日零消费者**）逐类接到「真库扫到 + 谁 apply / 谁没 apply」的事实上。

十三类 ↔ 网格映射表（R3；每行可核：tag 是下面 `SCENARIOS` 的字面量、也出现在本
docstring 里，tag 的 snake_case 是本文件唯一一个 ``test_`` 函数名的前缀，faces 是
既有恢复面的**名字**——行号只是引用，名字才是钉，由最后一个测试逐个复核）：

    #  tag                          | RA §23 checkpoint      | IP §11 残件类
    1  CP0-crash-turn               | Crash after CP0        | non-terminal TurnRecord
    2  CP0-crash-analysis           | Crash after CP0        | pending AnalysisArtifact
    3  CP1-crash-teaching           | Crash after CP1        | non-terminal TurnRecord
    4  CP1-crash-persona            | Crash after CP1        | non-terminal TurnRecord
    5  CP2-crash-action             | Crash after CP2        | GenerationActionIntent
    6  CP2-crash-moment-opening     | Crash after CP2        | TeachingMoment + lock
    7  CP2-crash-orphan-lock        | Crash after CP2        | TeachingLockLease
    8  CP3-under-record             | Crash around CP3       | ServerDeliveryRecord
    9  CP3-no-blind-replay          | Crash around CP3       | TurnRecord + Delivery
    10 CP3-partial-prefix           | Crash around CP3       | Delivery + TurnRecord
    11 terminal-resume-fail         | Terminal + resume fail | TeachingMoment + Turn
    12 terminal-teaching-then-reply | Terminal + resume fail | TeachingMoment + lock
    13 projection-crash-gap         | CP4（canonical 之后）    | pending projections

两点口径：RA §22 的残件清单比 IP §11 多一类 **ServerDeliveryRecord**（§22 八类、
§11 七类）⇒ CP3 三类含它；「ConversationCoordinatorLease」在 Local V1 **无表**
（p10-0 R7：以三个 `owner_epoch` 投影代）⇒ 无独立场景，落在每类的入场（「谁是
owner」）断言里。§24.1 四词逐类钉住：CP0 ⇒ RESUME_ANALYSIS、CP1 ⇒ RESUME_DECISION、
CP2 ⇒ RESUME_ACTION_BY_STABLE_ACTION_ID、CP3 ⇒ CONSERVATIVE_DELIVERY_RECONCILIATION。

四条口径不变量（任务书 §2 末）逐类**适用者断言、不适用者写明理由**；各测试
docstring 末行按此表逐类作答，N/A 的理由也写在那里：

    (i) 不重放已提交 user turn：适用 1/2/3/4/5/9/10；(ii) 不重复 Evidence：适用
    1/2/5/9/10，3/6/7/8/11/12 以「命令 turn 无 analysis artifact ⇒ 断言 0」的形态
    适用，4/13 无 leg；(iii) 不丢 work：13 类全适用；(iv) 保守方向（不盲发）：适用
    6/8/9/10/11/12，其余窗口里根本没有发生过投递。

世界与构造（R2）：真库世界 + 真写入面 + 新 epoch 扫描，**零 `_seed()` 零 fixture
供给**。两类世界：`tests/phase3/conftest.py` 的 app.db 世界（`World.restart` 在同一
连接上开新 epoch），以及 `tests/phase9/test_p9_2_stream_turn.py` 的**文件库**世界
（§22 交付面与流式 transport 只有它有）。冲撞注入 = 「真面 + 一个具名面被拒一次」的
外壳（`Refusing`，与 P8-4 的 `RefusingPersona`/`FailingCommands` 同形）。**被迫世界**
（某 durable 形状今日无单一写入面能一次留下）逐处就地写明：4 的 persona-`DECIDING`、
10 的「CP3a 半未落」、11 的 epoch-1 闭包走 `_abort_opening` 的同一条公开 walk。红线：
本文件全部经 Write/Edit 落盘；未触碰 `migrations/`、`docs/`、`behavioral_baselines/`、
`tests/architecture/`、`tests/conftest.py`、`registry.py`；测试内 SQL 只用于控制组
读回与被迫世界；零迁移。
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.learning.controller import LearningController
from elc.learning.store import SqliteLearningStore
from elc.persona import (
    PersonaRuntime,
    PromptCompiler,
    ResponseValidator,
    ScriptedPersonaProvider,
)
from elc.platform.db import epoch
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    DomainError,
    DomainErrorCode,
    Err,
    InputId,
    InteractionChannel,
    Ok,
    Result,
    TurnId,
)
from elc.runtime import ConversationCoordinator, ConversationCoordinatorLease
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.guarded_stream import StreamStep
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
    RECOVERY_DISPOSITION_RESUME_DECISION,
    RECOVERY_KIND_ACTION,
    RECOVERY_KIND_ANALYSIS,
    RECOVERY_KIND_DELIVERY,
    RECOVERY_KIND_LOCK,
    RECOVERY_KIND_MOMENT,
    RECOVERY_KIND_TURN,
    TEACHING_LOCK_RECOVERY_ACTION,
    StartupRecoveryScanner,
)
from elc.runtime.types import GenerationActionStatus, InputEnvelope, TurnStatus
from elc.teaching.controller import TeachingController
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.store import MomentTransition, SqliteTeachingStore
from elc.teaching.types import AbortReason, MomentState
from tests.conftest import SRC_ROOT, AssemblyGenerationStore
from tests.phase3.conftest import (
    CONV,
    RECEIVED_AT,
    RUNTIME_VERSION,
    make_lease,
    make_teaching_coordinator,
)
from tests.phase3.target_fixtures import FixtureTeachingTargetProvider
from tests.phase4.conftest import NoopProjectionExecutor, complete_executors
from tests.phase9.test_p9_2_stream_turn import (
    REPLY,
    RecordingStore,
    ScriptedSource,
    SourceFactory,
    StreamWorld,
    action_of,
    begin_turn_ok,
    command,
    persona_runtime,
    pieces,
    second_connection_row,
    stream_world,
)

FOCUS_TARGET = "res-hedge-i-think"
CANONICAL_ANSWER = "I think it is going to rain."

#: R3's table as one literal the last test checks: (tag, §23 checkpoint, §11
#: class, the cited recovery faces as the *names* they are pinned by).
SCENARIOS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("CP0-crash-turn", "Crash after CP0", "non-terminal TurnRecord",
     ("begin_turn", "_begin_turn_guarded", "claim_turn_for_recovery")),
    ("CP0-crash-analysis", "Crash after CP0", "pending AnalysisArtifact",
     ("_run_learning_analysis", "record_learning_analysis")),
    ("CP1-crash-teaching", "Crash after CP1", "non-terminal TurnRecord",
     ("request_teaching", "_resume_or_replay_teaching")),
    ("CP1-crash-persona", "Crash after CP1", "non-terminal TurnRecord",
     ("_begin_turn_guarded", "recovery_disposition")),
    ("CP2-crash-action", "Crash after CP2", "GenerationActionIntent",
     ("claim_action_for_recovery", "get_action_for_turn")),
    ("CP2-crash-moment-opening", "Crash after CP2", "TeachingMoment (+lock)",
     ("abort_undelivered_openings", "_abort_opening")),
    ("CP2-crash-orphan-lock", "Crash after CP2", "TeachingLockLease",
     ("recover_orphan_teaching", "orphan_teaching_lock_moments")),
    ("CP3-under-record", "Crash around CP3", "ServerDeliveryRecord",
     ("reconcile_delivering_residue", "_reconcile_delivering_turn")),
    ("CP3-no-blind-replay", "Crash around CP3", "TurnRecord + DeliveryRecord",
     ("_reconcile_delivering_turn", "_delivery_row")),
    ("CP3-partial-prefix", "Crash around CP3", "DeliveryRecord + TurnRecord",
     ("canonicalize_assistant_turn", "_write_initial_estimate")),
    ("terminal-resume-fail", "Teaching terminal + Resume failed",
     "TeachingMoment (+Turn)", ("_close_residual_turns", "TurnRecoveryClosure")),
    ("terminal-teaching-then-reply", "Teaching terminal + Resume failed",
     "TeachingMoment + lock",
     ("_respond_to_teaching_guarded", "_terminalize_moment")),
    ("projection-crash-gap", "CP4 (after the canonical turn)",
     "pending projections", ("_recover_projections", "ensure_missing_jobs")),
)

#: The modules the cited faces live in: the faces are pinned as *names* against
#: these blobs (the line numbers in the docstrings are citations), so a renamed
#: face fails this suite instead of quietly diverging from the table.
FACE_SOURCES = (
    SRC_ROOT / "runtime" / "controller.py",
    SRC_ROOT / "runtime" / "recovery.py",
    SRC_ROOT / "runtime" / "projections.py",
    SRC_ROOT / "conversation" / "store.py",
    SRC_ROOT / "learning" / "store.py",
    SRC_ROOT / "platform" / "db" / "generation_store.py",
    SRC_ROOT / "teaching" / "controller.py",
)

#: Every table the counted worlds touch — the no-extra-work pins read this
#: list, so a scenario cannot "pass" by writing into a table nobody counted.
COUNTED_TABLES = (
    "turn_record", "user_turn", "input_envelope", "assistant_turn",
    "generation_action_intent", "decision_cycle", "teaching_moment",
    "active_teaching_lock", "analysis_artifact", "evidence_group",
    "evidence_claim",
)


@dataclass
class World:
    """The phase-3 app.db world of one epoch, with the two faces this suite
    needs: a *hand-built* P3-1A coordinator (so one named face can be the
    refusing one) and the caller-injected recovery scan."""

    db: sqlite3.Connection
    fence: RuntimeEpochFence
    store: SqliteConversationStore
    learning: SqliteLearningStore
    generation: AssemblyGenerationStore
    decision_cycles: SqliteDecisionCycleStore
    teaching_store: SqliteTeachingStore
    teaching: TeachingController
    targets: FixtureTeachingTargetProvider

    def coordinator(
        self, *, persona: object = None, actions: object = None,
        decision_cycles: object = None,
        projections: CP4ProjectionRuntime | None = None,
    ) -> ConversationCoordinator:
        chosen = self.generation if actions is None else actions
        cycles = (
            chosen.decision_cycles  # type: ignore[attr-defined]
            if decision_cycles is None else decision_cycles
        )
        return ConversationCoordinator(
            lease=make_lease(self.fence),
            conversation_commands=self.store,
            conversation_queries=self.store,
            persona=(_persona(chosen) if persona is None else persona),  # type: ignore[arg-type]
            generation_actions=chosen,  # type: ignore[arg-type]
            learning=self.learning,
            decision_cycles=cycles,  # type: ignore[arg-type]
            learning_controller=LearningController(self.learning),
            teaching=self.teaching,
            targets=self.targets,
            projections=projections,
        )

    def restart(self) -> "World":
        """A restart: a new runtime_epoch on the same connection, every store
        rebuilt on it (p10-0's ``Restarted`` shape)."""

        fence = epoch.open_runtime_epoch(self.db)
        return World(
            db=self.db, fence=fence,
            store=SqliteConversationStore(self.db, fence),
            learning=SqliteLearningStore(self.db, fence),
            generation=AssemblyGenerationStore(self.db, fence),
            decision_cycles=SqliteDecisionCycleStore(self.db, fence),
            teaching_store=SqliteTeachingStore(self.db, fence),
            teaching=TeachingController(SqliteTeachingStore(self.db, fence)),
            targets=self.targets,
        )

    def scan(
        self, *, deliveries: object = None
    ) -> tuple[tuple[str, str, str], ...]:
        """The recovery plan with the four p10-0 kind ports *injected by the
        caller* — which is exactly what the startup line does not do."""

        plan = StartupRecoveryScanner(
            self.store, make_lease(self.fence), self.teaching,
            generation_actions=self.generation,
            teaching_moments=self.teaching_store,
            analysis_artifacts=self.learning,
            delivery_records=deliveries,  # type: ignore[arg-type]
        ).scan()
        assert isinstance(plan, Ok), plan
        return tuple((item.kind, item.id, item.action) for item in plan.value)


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
    """The phase-3 assembly's own world (`conversation` opens the conversation
    every teaching face addresses)."""

    del conversation  # requested for its side effect
    return World(
        db=db, fence=fence, store=store, learning=learning,
        generation=generation_store, decision_cycles=decision_cycle_store,
        teaching_store=teaching_store, teaching=teaching_controller,
        targets=target_provider,
    )


def _persona(actions: object) -> PersonaRuntime:
    return PersonaRuntime(
        actions=actions,  # type: ignore[arg-type]
        provider=ScriptedPersonaProvider(),
        compiler=PromptCompiler(),
        validator=ResponseValidator(),
        max_provider_attempts=3,
    )


class Refusing:
    """A real object with **one named face** refused on its first call.

    The same shape as P8-4's ``RefusingPersona``/``FailingCommands`` and P3-1A's
    ``FailOnceGenerationStore``, generalised: each crash window is exactly "this
    one face of this one object did not finish", and everything else stays the
    shipped implementation.
    """

    def __init__(self, inner: object, face: str) -> None:
        self.inner = inner
        self.face = face
        self.refused = False

    def __getattr__(self, name: str) -> object:
        if name != self.face:
            return getattr(self.inner, name)

        def refuse(*args: object, **kwargs: object) -> Result[object]:
            if not self.refused:
                self.refused = True
                return Err(DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"injected crash at {self.face}",
                ))
            return getattr(self.inner, name)(*args, **kwargs)  # type: ignore[no-any-return]

        return refuse


class WatchingClaimStore:
    """The generation store, recording every recovery claim it answers: the
    re-arm is a *returned* fact (``claim_rearm``'s policy), so watching the face
    pins "re-armed at REQUESTED under the new epoch" without re-implementing
    that policy in the test."""

    def __init__(self, inner: object) -> None:
        self.inner = inner
        self.claims: list[tuple[str, str, int]] = []

    def claim_action_for_recovery(self, action_id: ActionId) -> Result[object]:
        result = self.inner.claim_action_for_recovery(action_id)  # type: ignore[attr-defined]
        if isinstance(result, Ok):
            self.claims.append(
                (str(action_id), result.value.status.value,
                 int(result.value.owner_epoch))
            )
        return result  # type: ignore[no-any-return]

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)


def _chat_command(cmid: str) -> CommitUserTurn:
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"in-{cmid}"),
            client_message_id=ClientMessageId(cmid),
            conversation_id=str(CONV), persona_id=None, scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=f"raw-{cmid}", received_at=RECEIVED_AT,
        ),
        raw_content="I think it is fine.",
        runtime_version=RUNTIME_VERSION,
    )


def _teaching_request(cmid: str) -> TeachingRequest:
    return TeachingRequest(
        conversation_id=CONV, focus_target_id=FOCUS_TARGET,
        client_message_id=ClientMessageId(cmid), requested_at=RECEIVED_AT,
    )


def _reply_request(cmid: str, text: str) -> TeachingReplyRequest:
    return TeachingReplyRequest(
        conversation_id=CONV,
        envelope=TeachingResponseEnvelope(
            control_intent=TeachingControlIntent.CONTINUE,
            attempt_present=True, attempt=AttemptPayload(text=text),
        ),
        client_message_id=ClientMessageId(cmid), requested_at=RECEIVED_AT,
    )


def _commit_chat_turn(store: SqliteConversationStore, cmid: str) -> str:
    """One real CP0 commit (RA §4 step 1) — the crash window is *after* it."""

    result = store.commit_user_turn(_chat_command(cmid))
    assert isinstance(result, Ok), result
    return str(result.value.turn_id)


def _begin_turn_ok(coordinator: ConversationCoordinator, cmid: str) -> object:
    result = coordinator.begin_turn(_chat_command(cmid))
    assert isinstance(result, Ok), result
    return result.value


def _counts(db: sqlite3.Connection, *tables: str) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _turn_row(db: sqlite3.Connection, turn_id: str) -> tuple[str, str | None, int]:
    row = db.execute(
        "SELECT status, turn_outcome, owner_epoch FROM turn_record"
        " WHERE turn_id = ?", (turn_id,),
    ).fetchone()
    assert row is not None, f"no turn_record row: {turn_id}"
    return (str(row[0]), None if row[1] is None else str(row[1]), int(row[2]))


def _action_row(db: sqlite3.Connection, turn_id: str) -> tuple[str, str, int]:
    row = db.execute(
        "SELECT action_id, status, owner_epoch FROM generation_action_intent"
        " WHERE turn_id = ?", (turn_id,),
    ).fetchone()
    assert row is not None, f"no generation_action_intent row: {turn_id}"
    return (str(row[0]), str(row[1]), int(row[2]))


def _moment_row(db: sqlite3.Connection) -> tuple[str, str, str | None, str | None, int]:
    """The single moment of this world: (id, lifecycle, abort, outcome, version)."""

    rows = db.execute(
        "SELECT moment_id, lifecycle_state, abort_reason, completion_outcome,"
        " state_version FROM teaching_moment"
    ).fetchall()
    assert len(rows) == 1, rows
    row = rows[0]
    return (str(row[0]), str(row[1]),
            None if row[2] is None else str(row[2]),
            None if row[3] is None else str(row[3]), int(row[4]))


def _transcript_row(world: StreamWorld, turn_id: str) -> tuple[object, ...]:
    """The assistant turn as the durable transcript holds it."""

    row = world.db.execute(
        "SELECT content, delivery_state FROM assistant_turn WHERE turn_id = ?",
        (turn_id,),
    ).fetchone()
    assert row is not None, f"no assistant_turn row: {turn_id}"
    return tuple(row)


def _kinds(plan: tuple[tuple[str, str, str], ...], kind: str) -> list[str]:
    return [item_id for item_kind, item_id, _ in plan if item_kind == kind]


def _words(plan: tuple[tuple[str, str, str], ...], kind: str) -> list[str]:
    return [word for item_kind, _, word in plan if item_kind == kind]


def _plan_ids(items: object, kind: str) -> list[str]:
    """The ids of one kind in a *raw* plan (``StartupRecoveryOutcome.plan``),
    which carries ``RecoveryAction`` items rather than this file's triples."""

    return [str(item.id) for item in items if item.kind == kind]  # type: ignore[attr-defined]


# 1 — CP0-crash-turn


def test_cp0_crash_turn_names_the_committed_turn_and_never_replays_it(
    world: World,
) -> None:
    """CP0-crash-turn（RA §23 "Crash after CP0 / 从 analysis 继续"）.

    A death between the CP0 commit and the analysis leg. The new epoch names
    exactly that turn (`TURN` + `RESUME_ANALYSIS`, executed by
    `_begin_turn_guarded` at controller.py:1424-1441) and the re-entry with the
    same `client_message_id` adopts that same turn — never a second one.

    (i)(ii) 适用：三个行计数各恰 1、evidence_group 恰 1，重入前后不动；
    (iii) 适用：COMPLETED / REPLIED_FULL；(iv) N/A：无投递。
    """

    db = world.db
    turn_id = _commit_chat_turn(world.store, "cm-p10-1-cp0")
    assert _turn_row(db, turn_id) == ("USER_COMMITTED", None, 1)
    before = _counts(db, *COUNTED_TABLES)

    new = world.restart()
    plan = new.scan()
    assert (RECOVERY_KIND_TURN, turn_id,
            RECOVERY_DISPOSITION_RESUME_ANALYSIS) in plan
    assert _kinds(plan, RECOVERY_KIND_ANALYSIS) == []  # nothing produced yet
    assert _kinds(plan, RECOVERY_KIND_ACTION) == []

    done = _begin_turn_ok(new.coordinator(), "cm-p10-1-cp0")
    assert str(done.turn_id) == turn_id  # the same turn, adopted
    assert done.outcome == "REPLIED_FULL"
    assert _turn_row(db, turn_id) == ("COMPLETED", "REPLIED_FULL", new.fence.current)
    after = _counts(db, *COUNTED_TABLES)
    assert [after[k] for k in
            ("turn_record", "user_turn", "input_envelope")] == [1, 1, 1]
    assert all(after[k] == before[k] for k in
               ("turn_record", "user_turn", "input_envelope"))
    assert after["analysis_artifact"] == after["evidence_group"] == 1

    again = _begin_turn_ok(new.coordinator(), "cm-p10-1-cp0")  # a plain replay
    assert str(again.turn_id) == turn_id
    assert _counts(db, *COUNTED_TABLES) == after


# 2 — CP0-crash-analysis


def test_cp0_crash_analysis_names_the_pending_artifact_and_commits_one_group(
    world: World,
) -> None:
    """CP0-crash-analysis（RA §23 "不重复 Evidence"）.

    `ANALYZING` + a `PRODUCED` artifact: the ANALYSIS kind (p10-0's
    `AnalysisArtifactRecoverySource`) names the artifact, and the re-entry
    replays the analysis under its deterministic key before committing **one**
    evidence group (`_run_learning_analysis` is the executing leg).

    (i) 适用：同一个 turn，无第二行。(ii) 适用——本类就是它的主场：group/claim
    计数跨修复不动，重复分析答同一个 `analysis_id`。(iii) 适用：artifact 到
    COMMITTED、turn 到 COMPLETED。(iv) N/A：无投递。
    """

    db = world.db
    turn_id = _commit_chat_turn(world.store, "cm-p10-1-cp0-analysis")
    advanced = world.store.transition_turn(TurnId(turn_id), 1, TurnStatus.ANALYZING)
    assert isinstance(advanced, Ok), advanced
    turn_slice = world.store.get_canonical_turn_slice(TurnId(turn_id))
    assert isinstance(turn_slice, Ok), turn_slice
    proposal = world.learning.record_learning_analysis(turn_slice.value)
    assert isinstance(proposal, Ok), proposal
    analysis_id = str(proposal.value.analysis_id)
    replay = world.learning.record_learning_analysis(turn_slice.value)
    assert isinstance(replay, Ok), replay
    assert str(replay.value.analysis_id) == analysis_id  # idempotent producer
    assert db.execute(
        "SELECT status FROM analysis_artifact WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone() == ("PRODUCED",)

    new = world.restart()
    plan = new.scan()
    assert (RECOVERY_KIND_TURN, turn_id,
            RECOVERY_DISPOSITION_RESUME_ANALYSIS) in plan
    assert _kinds(plan, RECOVERY_KIND_ANALYSIS) == [analysis_id]
    assert _words(plan, RECOVERY_KIND_ANALYSIS) == [
        RECOVERY_DISPOSITION_RESUME_ANALYSIS
    ]

    done = _begin_turn_ok(new.coordinator(), "cm-p10-1-cp0-analysis")
    assert str(done.turn_id) == turn_id
    assert db.execute(
        "SELECT status FROM analysis_artifact WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone() == ("COMMITTED",)
    groups, claims = _counts(db, "evidence_group", "evidence_claim").values()
    assert groups == 1
    after = _counts(db, *COUNTED_TABLES)

    again = _begin_turn_ok(new.coordinator(), "cm-p10-1-cp0-analysis")
    assert str(again.turn_id) == turn_id
    assert _counts(db, *COUNTED_TABLES) == after
    assert list(_counts(db, "evidence_group", "evidence_claim").values()) == [
        1, claims
    ]


# 3 — CP1-crash-teaching


def test_cp1_crash_teaching_repairs_through_the_teaching_entries(
    world: World,
) -> None:
    """CP1-crash-teaching（RA §23 "Crash after CP1 → 从 DecisionCycle 继续"）.

    The teaching turn stopped at `DECIDING` because the cycle write died — the
    CP1 window proper (no cycle, no moment, no action). The new epoch names it
    `TURN` + `RESUME_DECISION`; the *ordinary* loop refuses it (a command
    payload turn is not a persona turn, controller.py:1394-1400); the teaching
    entry re-enters and repairs (`request_teaching` → the fresh-cycle branch).

    (i) 适用：命令 turn 的 CP0 重放为同一个 turn、唯一一行。(ii) N/A 且已留痕：
    教学命令 turn 不说任何话（`raw_content=""`）⇒ 根本没有 analysis artifact，前后
    各断言为 0。(iii) 适用：AWAITING_USER 且 opening action TERMINAL。(iv) N/A：
    崩前没发过任何东西。
    """

    db = world.db
    coordinator = world.coordinator(
        decision_cycles=Refusing(world.decision_cycles, "record_decision_cycle")
    )
    crashed = coordinator.request_teaching(_teaching_request("cm-p10-1-cp1-teaching"))
    assert isinstance(crashed, Err), crashed
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    assert _turn_row(db, turn_id)[0] == "DECIDING"
    assert _counts(db, "decision_cycle", "teaching_moment") == {
        "decision_cycle": 0, "teaching_moment": 0
    }

    new = world.restart()
    plan = new.scan()
    assert (RECOVERY_KIND_TURN, turn_id,
            RECOVERY_DISPOSITION_RESUME_DECISION) in plan
    # the CP1 residue is the turn and nothing else: no cycle ⇒ no dependent row
    assert [item for item in plan
            if item[0] in (RECOVERY_KIND_ACTION, RECOVERY_KIND_MOMENT)] == []

    refused = new.coordinator().begin_turn(_chat_command("cm-p10-1-cp1-teaching"))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "teaching command turn" in refused.error.message
    assert _turn_row(db, turn_id)[0] == "DECIDING"  # the refusal wrote nothing
    assert db.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0] == 1

    repaired = new.coordinator().request_teaching(
        _teaching_request("cm-p10-1-cp1-teaching")
    )
    assert isinstance(repaired, Ok), repaired
    assert repaired.value.moment_state is MomentState.AWAITING_USER
    assert repaired.value.action_status is GenerationActionStatus.TERMINAL
    assert _turn_row(db, turn_id) == ("COMPLETED", "REPLIED_FULL", new.fence.current)
    assert db.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 0


# 4 — CP1-crash-persona


def test_cp1_crash_persona_refuses_the_turn_and_names_resume_decision(
    world: World,
) -> None:
    """CP1-crash-persona（RA §23 "Crash after CP1"）.

    A persona-loop turn durably at `DECIDING`: the fact is named
    `RESUME_DECISION`, and the *persona* entry refuses it (the CP1 slot belongs
    to the teaching flow: controller.py:1449-1453). Both halves are pinned — the
    classification and the refusal — because a classification nobody acts on is
    exactly what this suite exists to make visible.

    **被迫世界，已声明**：没有任何 shipped persona 写入面产出 `DECIDING`；该行用
    conversation store 自己的 `transition_turn`（教学路也走的同一个 CAS 协调写）
    造出。Revisit：persona 写入面能到 DECIDING。

    (i) 适用：被拒的重入走 CP0 dedupe，不产第二个 turn。(ii) N/A：被拒的 turn 什么
    都不跑。(iii) 适用：具名 + 拒绝即解释。(iv) N/A：无投递。**已登记**：拒绝仍会
    *adopt* 该 turn（RUNTIME §24 restart ownership 在状态分支之前），所以
    owner_epoch 会动而状态不动——与 `abort_undelivered_openings` 登记的同一性质。
    """

    db = world.db
    turn_id = _commit_chat_turn(world.store, "cm-p10-1-cp1-persona")
    forced = world.store.transition_turn(TurnId(turn_id), 1, TurnStatus.DECIDING)
    assert isinstance(forced, Ok), forced

    new = world.restart()
    plan = new.scan()
    assert (RECOVERY_KIND_TURN, turn_id,
            RECOVERY_DISPOSITION_RESUME_DECISION) in plan

    refused = new.coordinator().begin_turn(_chat_command("cm-p10-1-cp1-persona"))
    assert isinstance(refused, Err), refused
    assert refused.error.code is DomainErrorCode.CONFLICT
    assert "outside the Phase 2 loop" in refused.error.message
    # adopted, never advanced: the status is the crash's, the owner is new
    assert _turn_row(db, turn_id) == ("DECIDING", None, new.fence.current)
    assert _counts(db, "turn_record", "assistant_turn") == {
        "turn_record": 1, "assistant_turn": 0
    }


# 5 — CP2-crash-action


def test_cp2_crash_action_rearms_the_same_stable_action_id(world: World) -> None:
    """CP2-crash-action（RA §23 "Crash after CP2 → 继续同 action_id"）.

    `GENERATING` + a nonterminal action whose validated buffer is committed
    (`READY_TO_DELIVER` = CP2 done, the delivery never began). The p10-0 ACTION
    kind names it, and the re-entry claims exactly that row — re-armed at
    `REQUESTED` under the new epoch, same stable `action_id`, no second action
    (controller.py:1549-1560).

    (i) 适用：重入 adopt 同一个 turn。(ii) 适用：崩前已提交的 analysis 仍只有 1 个
    group。(iii) 适用：TERMINAL + COMPLETED。(iv) N/A：拒绝在第一次 emit 之前。
    """

    db = world.db
    crashed = world.coordinator(
        persona=Refusing(_persona(world.generation), "begin_delivery")
    ).begin_turn(_chat_command("cm-p10-1-cp2-action"))
    assert isinstance(crashed, Err), crashed
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    action_id, status, owner = _action_row(db, turn_id)
    assert (status, owner) == ("READY_TO_DELIVER", 1)
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 0

    new = world.restart()
    plan = new.scan()
    assert (RECOVERY_KIND_TURN, turn_id, RECOVERY_DISPOSITION_RESUME_ACTION) in plan
    assert _kinds(plan, RECOVERY_KIND_ACTION) == [action_id]
    assert _words(plan, RECOVERY_KIND_ACTION) == [RECOVERY_DISPOSITION_RESUME_ACTION]

    watching = WatchingClaimStore(new.generation)
    done = _begin_turn_ok(new.coordinator(actions=watching), "cm-p10-1-cp2-action")
    assert str(done.turn_id) == turn_id
    assert watching.claims == [
        (action_id, "REQUESTED", new.fence.current)  # re-armed, not rebuilt
    ]
    assert int(
        db.execute("SELECT COUNT(*) FROM generation_action_intent").fetchone()[0]
    ) == 1
    assert _action_row(db, turn_id) == (action_id, "TERMINAL", new.fence.current)
    assert db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0] == 1


# 6 — CP2-crash-moment-opening


def test_cp2_crash_moment_opening_is_closed_by_the_delivery_failure_walk(
    world: World,
) -> None:
    """CP2-crash-moment-opening（RA §23 "Crash after CP2"；§7 DELIVERY_FAILURE）.

    CP2 committed the moment (`OPENING` + its lock) and the opening delivery
    died at the action's own edge: the p10-0 MOMENT kind names it, and the
    startup line closes it through §7's abort walk with `DELIVERY_FAILURE`
    (controller.py:4418 → :5017) — the word the *live* faces use for an opening
    that was never presented — releasing the lock and writing **no** estimate
    and **no** §20 event.

    (i) N/A：本窗口不重入任何 user turn（recovery 改为 adopt），以行数钉死没人
    重放。(ii) 适用（零形状）：命令 turn 不产 analysis artifact，断言为 0。
    (iii) 适用：moment 以自有词关闭、turn 经 turn-level closure 到 COMPLETED。
    (iv) 适用：投递从未发生，断言没有任何投递侧行被发明出来。
    """

    db = world.db
    crashed = world.coordinator(
        persona=Refusing(_persona(world.generation), "begin_delivery")
    ).request_teaching(_teaching_request("cm-p10-1-cp2-moment"))
    assert isinstance(crashed, Err), crashed
    moment_id, state, _, _, _ = _moment_row(db)
    assert state == "OPENING"
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 1
    assert _action_row(db, turn_id)[1] == "READY_TO_DELIVER"
    assert db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 0

    new = world.restart()
    plan = new.scan()
    assert _kinds(plan, RECOVERY_KIND_MOMENT) == [moment_id]
    assert _words(plan, RECOVERY_KIND_MOMENT) == [MOMENT_RECOVERY_ACTION]
    assert _kinds(plan, RECOVERY_KIND_LOCK) == [moment_id]

    outcome = new.coordinator().run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.aborted_openings == (moment_id,)
    assert outcome.value.recovered_moments == ()  # the §7 walk spoke first
    assert _moment_row(db)[1:3] == ("CLOSED", "DELIVERY_FAILURE")
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    assert _counts(db, "exposure_estimate", "planning_ledger_event",
                   "analysis_artifact") == {
        "exposure_estimate": 0, "planning_ledger_event": 0, "analysis_artifact": 0
    }
    assert [(str(c.turn_id), c.outcome, c.action_status)
            for c in outcome.value.closed_turns] == [
        (turn_id, "NO_ASSISTANT_OUTPUT", "READY_TO_DELIVER")
    ]
    assert _turn_row(db, turn_id)[:2] == ("COMPLETED", "NO_ASSISTANT_OUTPUT")
    # the startup line's own plan carries no MOMENT item — p10-0's "classified,
    # not yet consumed" fact (the apply face reaches the moment via the lock)
    assert _plan_ids(outcome.value.plan, RECOVERY_KIND_MOMENT) == []

    counts = _counts(db, *COUNTED_TABLES)
    again = new.coordinator().run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.aborted_openings == ()
    assert _counts(db, *COUNTED_TABLES) == counts


# 7 — CP2-crash-orphan-lock


def test_cp2_crash_orphan_lock_is_named_and_swept_with_recovery_abort(
    world: World,
) -> None:
    """CP2-crash-orphan-lock（STATE_MACHINES §9 / RA §22 的 TeachingLockLease）.

    The opening *was* delivered (`AWAITING_USER`, lock held) when the process
    died. The LOCK kind names the orphan, the startup sweep releases it and
    closes the moment with `SYSTEM_RECOVERY_ABORT` (controller.py:3922) — and
    the delivered case is *not* stolen by §7's `DELIVERY_FAILURE` walk, which is
    what tells the two CP2 residues apart. `ConversationCoordinatorLease` 在
    Local V1 无表（p10-0 R7：三个 `owner_epoch` 投影代），故它的 sweep 面就是这
    一条 claim：拥有它的 turn 断言未被触碰。

    (i) N/A：recovery 从不重入 turn。(ii) N/A 且已留痕：命令 turn 无 analysis
    artifact（断言 0）。(iii) 适用：moment 到 CLOSED、锁消失。(iv) N/A：崩前投递
    已经发生，没有东西可再发。
    """

    db = world.db
    delivered = make_teaching_coordinator(
        world.store, world.generation, make_lease(world.fence),
        ScriptedPersonaProvider(), world.learning, world.decision_cycles,
        world.teaching, world.targets,
    ).request_teaching(_teaching_request("cm-p10-1-cp2-lock"))
    assert isinstance(delivered, Ok), delivered
    moment_id, state, _, _, _ = _moment_row(db)
    assert state == "AWAITING_USER"
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 1
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    before_turn = _turn_row(db, turn_id)
    assert before_turn == ("COMPLETED", "REPLIED_FULL", 1)

    new = world.restart()
    plan = new.scan()
    assert _kinds(plan, RECOVERY_KIND_LOCK) == [moment_id]
    assert _words(plan, RECOVERY_KIND_LOCK) == [TEACHING_LOCK_RECOVERY_ACTION]
    assert _kinds(plan, RECOVERY_KIND_MOMENT) == [moment_id]  # still nonterminal

    outcome = new.coordinator().run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.recovered_moments == (moment_id,)
    assert outcome.value.aborted_openings == ()  # the opening *was* presented
    assert _moment_row(db)[1:3] == ("CLOSED", "SYSTEM_RECOVERY_ABORT")
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    assert _turn_row(db, turn_id) == before_turn  # untouched, still epoch 1
    assert db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 0

    counts = _counts(db, *COUNTED_TABLES)
    again = new.coordinator().run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.recovered_moments == ()
    assert _counts(db, *COUNTED_TABLES) == counts


# 8/9/10 — the CP3 windows, on the file-backed §22 world


@dataclass
class StreamEpoch:
    """A restart of the file-backed §22 world (P9-2's ``StreamWorld``)."""

    fence: RuntimeEpochFence
    store: SqliteConversationStore
    generation: AssemblyGenerationStore
    deliveries: SqliteDeliveryRecordStore

    def coordinator(
        self, world: StreamWorld, *, transport: object = None,
        records: object = None,
    ) -> ConversationCoordinator:
        lease = ConversationCoordinatorLease()
        lease.adopt_epoch(self.fence.current)
        return ConversationCoordinator(
            lease=lease,
            conversation_commands=self.store,
            conversation_queries=self.store,
            persona=persona_runtime(world),
            generation_actions=self.generation,
            decision_cycles=self.generation.decision_cycles,
            delivery_records=(
                self.deliveries if records is None else records  # type: ignore[arg-type]
            ),
            stream_transport=transport,  # type: ignore[arg-type]
        )


def _stream_epoch(world: StreamWorld) -> StreamEpoch:
    fence = epoch.open_runtime_epoch(world.db)
    return StreamEpoch(
        fence=fence,
        store=SqliteConversationStore(world.db, fence),
        generation=AssemblyGenerationStore(world.db, fence),
        deliveries=SqliteDeliveryRecordStore(world.db, fence),
    )


def _stream_crash_coordinator(
    world: StreamWorld, *, transport: object, records: object, commands: object
) -> ConversationCoordinator:
    """The live epoch's coordinator with the stream face injected (P9-2's own
    construction) and one named face replaced by the test."""

    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(world.fence.current)
    return ConversationCoordinator(
        lease=lease,
        conversation_commands=commands,  # type: ignore[arg-type]
        conversation_queries=world.store,
        persona=persona_runtime(world),
        generation_actions=world.generation,
        decision_cycles=world.generation.decision_cycles,
        delivery_records=records,  # type: ignore[arg-type]
        stream_transport=transport,  # type: ignore[arg-type]
    )


def _stream_plan(
    new: StreamEpoch, *, deliveries: object
) -> tuple[tuple[str, str, str], ...]:
    lease = ConversationCoordinatorLease()
    lease.adopt_epoch(new.fence.current)
    plan = StartupRecoveryScanner(
        new.store, lease, None,
        generation_actions=new.generation,
        delivery_records=deliveries,  # type: ignore[arg-type]
    ).scan()
    assert isinstance(plan, Ok), plan
    return tuple((item.kind, item.id, item.action) for item in plan.value)


def _crash_a_streamed_turn(
    world: StreamWorld, *, cmid: str, steps: tuple[StreamStep, ...],
    records: object,
) -> tuple[str, ActionId, ScriptedSource, SourceFactory]:
    """One streamed turn whose terminalization was refused: the CP3 window, as
    a durable `DELIVERING` turn plus its live source/factory counters."""

    source = ScriptedSource(steps=steps)
    factory = SourceFactory(source)
    crashed = _stream_crash_coordinator(
        world, transport=factory, records=records,
        commands=Refusing(world.store, "terminalize_turn"),
    ).begin_turn(command(cmid))
    assert isinstance(crashed, Err), crashed
    turn_id = str(
        world.db.execute(
            "SELECT turn_id FROM turn_record WHERE status = 'DELIVERING'"
        ).fetchone()[0]
    )
    return (turn_id, action_of(world, turn_id), source, factory)


def test_cp3_under_record_reconciles_the_unfrozen_delivery_without_resending(
    tmp_path: Path,
) -> None:
    """CP3-under-record（RA §23 "Crash around CP3"；RA §22 的 ServerDeliveryRecord）.

    The delivery leg finished (action TERMINAL) but the turn was never
    terminalized, and the §22 row never froze (its terminal write was refused —
    the registered divergence). The p10-0 DELIVERY kind names the action
    (`terminal_at IS NULL` + old epoch), and the startup line finishes the turn
    from the delivery's own facts (controller.py:4359 → :2307) with **no
    resend**: the transport factory the new epoch holds is never asked, and the
    row and transcript are byte-identical afterwards.

    (i) 适用（durable 形态）：transcript 不被重写、不新增 turn 行。(ii) N/A 且已
    留痕：普通流式 turn 在投递前已提交 analysis，group 计数断言不动。(iii) 适用：
    COMPLETED / REPLIED_PARTIAL，且行自己说明原因。(iv) 适用——本类的主场。
    """

    world = stream_world(tmp_path)
    first = pieces(REPLY, 3)[0]
    turn_id, action_id, _source, _factory = _crash_a_streamed_turn(
        world, cmid="cm-p10-1-cp3-under-record",
        steps=(StreamStep.chunk(first), StreamStep.stopped("the window closed")),
        records=RecordingStore(world.deliveries, refuse_at=3),  # open, chunk, freeze
    )
    row_before = second_connection_row(world, action_id)
    assert row_before[0] == "SENT_PARTIAL"
    assert row_before[4] is None  # the freeze never landed: the residue
    transcript_before = _transcript_row(world, turn_id)
    assert transcript_before == (first, "SENT_PARTIAL")
    groups_before = int(
        world.db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0]
    )

    new = _stream_epoch(world)
    plan = _stream_plan(new, deliveries=new.deliveries)
    assert (RECOVERY_KIND_TURN, turn_id,
            RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY) in plan
    assert _kinds(plan, RECOVERY_KIND_DELIVERY) == [action_id]
    assert _words(plan, RECOVERY_KIND_DELIVERY) == [
        RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY
    ]

    startup_source = ScriptedSource(steps=(StreamStep.chunk(first),))
    startup_factory = SourceFactory(startup_source)
    outcome = new.coordinator(
        world, transport=startup_factory, records=new.deliveries
    ).run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert [(str(r.turn_id), r.outcome, r.repaired_transcript)
            for r in outcome.value.reconciled_turns] == [
        (turn_id, "REPLIED_PARTIAL", False)
    ]
    assert startup_factory.calls == []  # no blind resend, at the boundary
    assert startup_source.emitted == [] and startup_source._emit_calls == 0
    assert second_connection_row(world, action_id) == row_before
    assert _transcript_row(world, turn_id) == transcript_before
    assert _turn_row(world.db, turn_id)[:2] == ("COMPLETED", "REPLIED_PARTIAL")
    assert int(
        world.db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0]
    ) == groups_before
    # the startup line's own plan carries no DELIVERY item (p10-0 R5)
    assert _plan_ids(outcome.value.plan, RECOVERY_KIND_DELIVERY) == []


def test_cp3_no_blind_replay_closes_from_the_canonical_transcript(
    tmp_path: Path,
) -> None:
    """CP3-no-blind-replay（RA §23 "delivery uncertain → 不盲目重放"）.

    The process died after the last recorded chunk and before the
    terminalization: the §22 row is frozen `SENT_PARTIAL` with the durable
    prefix and the transcript already carries it. The re-entry closes the turn
    from the **canonical transcript** — and the counting transport the new epoch
    holds is never touched: the same `ScriptedSource` behind the same
    `SourceFactory` keeps its call/emit counters exactly where the crash left
    them (controller.py:1402-1417 hands a DELIVERING turn to the reconciliation
    instead of to the loop).

    (i) 适用：同 `client_message_id` 找到同一个 turn。(ii) N/A 且已留痕：analysis
    在投递前已提交（计数不动）。(iii) 适用：COMPLETED / REPLIED_PARTIAL。
    (iv) 适用：release/emit 计数就是钉子。
    """

    world = stream_world(tmp_path)
    chunk = pieces(REPLY, 3)[0]
    turn_id, action_id, source, factory = _crash_a_streamed_turn(
        world, cmid="cm-p10-1-no-replay",
        steps=(StreamStep.chunk(chunk), StreamStep.stopped("the window closed")),
        records=RecordingStore(world.deliveries),
    )
    assert len(factory.calls) == 1 and factory.calls[0][1] == action_id
    calls_before, emits_before = len(factory.calls), source._emit_calls
    assert emits_before == 1
    transcript_rows = int(
        world.db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0]
    )
    groups_before = int(
        world.db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0]
    )

    new = _stream_epoch(world)
    # the second epoch holds the SAME factory: if anything re-ran the delivery,
    # its counters would move
    repaired = begin_turn_ok(
        new.coordinator(world, transport=factory, records=new.deliveries),
        "cm-p10-1-no-replay",
    )
    assert str(repaired.turn_id) == turn_id
    assert repaired.outcome == "REPLIED_PARTIAL"
    assert repaired.reply_text == chunk  # the transcript, verbatim
    assert len(factory.calls) == calls_before
    assert source._emit_calls == emits_before
    assert source.emitted == [chunk]
    assert int(
        world.db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0]
    ) == transcript_rows
    assert world.db.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0] == 1
    assert _turn_row(world.db, turn_id)[:2] == ("COMPLETED", "REPLIED_PARTIAL")
    assert int(
        world.db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0]
    ) == groups_before


def test_cp3_partial_prefix_takes_the_durable_boundary_and_keeps_the_ceiling(
    tmp_path: Path,
) -> None:
    """CP3-partial-prefix（RA §23 CP3 + RA §14 的保守方向）.

    The record lagged the release (one chunk's write refused), so the durable
    prefix is **shorter** than what the client boundary received — the P9-R2
    reading: the transcript takes the *durable* boundary (conservative), while
    the estimate's `max_possible_exposure` sits above its `exposure_level` (the
    ceiling never understates what the user may hold). The crash ate the
    transcript half; the repair rebuilds it from the §22 row's own prefix
    (controller.py:2307's `canonicalize_assistant_turn` call) and leaves the
    existing estimate alone.

    **被迫世界，已声明**：frozen 行 + CP3a 半缺失是 P9-4 已登记的那条臂；本测试用
    两条直接语句删 transcript 并把 turn 放回 `DELIVERING`，就地写明。

    (i) 适用：修复 adopt 同一个 turn。(ii) N/A 且已留痕：analysis 在投递前已提交
    （计数不动）。(iii) 适用：COMPLETED / REPLIED_PARTIAL。(iv) 适用：transcript
    取 durable 边界，release 不抬 level。
    """

    world = stream_world(tmp_path)
    chunks = pieces(REPLY, 3)
    durable = "".join(chunks[:2])
    spy = RecordingStore(world.deliveries, refuse_at=4)  # open, chunks 1-2
    denied = _stream_crash_coordinator(
        world,
        transport=SourceFactory(
            ScriptedSource(steps=tuple(StreamStep.chunk(p) for p in chunks))
        ),
        records=spy, commands=world.store,
    ).begin_turn(command("cm-p10-1-partial-prefix"))
    assert isinstance(denied, Ok), denied
    turn_id = str(denied.value.turn_id)
    action_id = action_of(world, turn_id)
    row = second_connection_row(world, action_id)
    assert row[0] == "SENT_PARTIAL" and row[1] == durable
    assert len(durable) < len(REPLY)  # the release ran ahead of the record
    levels = world.db.execute(
        "SELECT exposure_level, max_possible_exposure FROM exposure_estimate"
        " WHERE action_id = ?", (str(action_id),),
    ).fetchone()
    assert levels == ("PARTIAL", "FULL")  # the ceiling is the released half's
    groups_before = int(
        world.db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0]
    )
    # the forced CP3a gap
    world.db.execute("DELETE FROM assistant_turn WHERE turn_id = ?", (turn_id,))
    world.db.execute(
        "UPDATE turn_record SET status = 'DELIVERING', turn_outcome = NULL"
        " WHERE turn_id = ?", (turn_id,),
    )
    world.db.commit()

    new = _stream_epoch(world)
    plan = _stream_plan(new, deliveries=new.deliveries)
    assert (RECOVERY_KIND_TURN, turn_id,
            RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY) in plan
    # the row is frozen, so the DELIVERY kind (`terminal_at IS NULL`) names
    # nothing: the CP3 residue is a turn item here
    assert _kinds(plan, RECOVERY_KIND_DELIVERY) == []

    repaired = begin_turn_ok(
        new.coordinator(
            world, transport=SourceFactory(ScriptedSource(steps=())),
            records=new.deliveries,
        ),
        "cm-p10-1-partial-prefix",
    )
    assert str(repaired.turn_id) == turn_id
    assert repaired.outcome == "REPLIED_PARTIAL"
    transcript = _transcript_row(world, turn_id)
    assert transcript == (durable, "SENT_PARTIAL")  # the durable boundary
    assert transcript[0] != REPLY
    assert world.db.execute(
        "SELECT exposure_level, max_possible_exposure FROM exposure_estimate"
        " WHERE action_id = ?", (str(action_id),),
    ).fetchone() == levels  # the existing estimate is left alone
    assert world.db.execute("SELECT COUNT(*) FROM turn_record").fetchone()[0] == 1
    assert int(
        world.db.execute("SELECT COUNT(*) FROM evidence_group").fetchone()[0]
    ) == groups_before


# 11 — terminal-resume-fail


def test_terminal_resume_fail_closes_the_turn_without_reopening_the_moment(
    world: World,
) -> None:
    """terminal-resume-fail（RA §23 "Teaching terminal + Resume failed → 不 reopen"）.

    The moment is already terminal when the new epoch arrives (closed in the
    dead epoch, its lock released) while its turn is still nonterminal. The
    recovery must **not** reopen the moment and must bring the turn to an
    explicable end: `_close_residual_turns` (controller.py:4276) adopts the
    turn, reads the outcome from the canonical transcript
    (`NO_ASSISTANT_OUTPUT`: no assistant row exists) and records where the
    action stopped instead of advancing it.

    **被迫世界，已声明**：moment 在 *dead* epoch 里走 `_abort_opening` 的同一条
    公开 walk（`transition_moment` → ABORTING、`terminalize_moment` →
    TEACHING_TERMINAL、→ RESUMING → CLOSED）关闭——残件就是「某个面死在 moment 关闭
    与 turn 收口之间」，即 startup 线自己的内部崩溃窗口。Revisit：某个 shipped 单一
    面直接留下该残件。

    (i) N/A：recovery 从不重入 turn。(ii) N/A 且已留痕：命令 turn 无 analysis
    artifact（断言 0）。(iii) 适用：COMPLETED / NO_ASSISTANT_OUTPUT。(iv) 适用：
    本 opening 没发过东西，moment 也没被重开去发。
    """

    db = world.db
    crashed = world.coordinator(
        persona=Refusing(_persona(world.generation), "begin_delivery")
    ).request_teaching(_teaching_request("cm-p10-1-terminal"))
    assert isinstance(crashed, Err), crashed
    moment_id, state, _, _, _ = _moment_row(db)
    assert state == "OPENING"
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])

    # the same public walk `_abort_opening` performs, in the *dead* epoch
    active = world.teaching.get_active_moment(CONV)
    assert isinstance(active, Ok) and active.value is not None
    moment = active.value
    stepped = world.teaching.transition_moment(
        moment.moment_id,
        MomentTransition(lifecycle_state=MomentState.ABORTING,
                         abort_reason=AbortReason.DELIVERY_FAILURE.value),
        moment.state_version,
    )
    assert isinstance(stepped, Ok), stepped
    current = stepped.value
    terminal = world.teaching.terminalize_moment(
        current.moment_id, abort_reason=AbortReason.DELIVERY_FAILURE.value
    )
    assert isinstance(terminal, Ok), terminal
    current = terminal.value
    for state_word in (MomentState.RESUMING, MomentState.CLOSED):
        advanced = world.teaching.transition_moment(
            current.moment_id,
            MomentTransition(
                lifecycle_state=state_word,
                closed_at=None if state_word is MomentState.RESUMING else RECEIVED_AT,
            ),
            current.state_version,
        )
        assert isinstance(advanced, Ok), advanced
        current = advanced.value
    closed_before = _moment_row(db)
    assert closed_before[1:3] == ("CLOSED", "DELIVERY_FAILURE")
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    assert _turn_row(db, turn_id)[0] == "GENERATING"  # the residue
    action_before = _action_row(db, turn_id)

    new = world.restart()
    plan = new.scan()
    assert (RECOVERY_KIND_TURN, turn_id, RECOVERY_DISPOSITION_RESUME_ACTION) in plan
    outcome = new.coordinator().run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert [(str(c.turn_id), c.moment_id, c.outcome, c.action_status)
            for c in outcome.value.closed_turns] == [
        (turn_id, moment_id, "NO_ASSISTANT_OUTPUT", action_before[1])
    ]
    # the moment was not reopened: same state, same reason, same state_version
    assert _moment_row(db) == closed_before
    assert _action_row(db, turn_id) == action_before  # left where it stopped
    assert _turn_row(db, turn_id)[:2] == ("COMPLETED", "NO_ASSISTANT_OUTPUT")
    assert db.execute("SELECT COUNT(*) FROM analysis_artifact").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM teaching_moment").fetchone()[0] == 1


# 12 — terminal-teaching-then-reply


def test_terminal_teaching_then_reply_is_refused_without_reopening(
    world: World,
) -> None:
    """terminal-teaching-then-reply（RA §23 "Teaching terminal + Resume failed"）.

    A healthy episode ran to its own end (opening → reply → CLOSED with a §6
    completion outcome), and a **late** reply arrives. It is refused — "no
    active teaching moment" (controller.py:5303-5310) — and the moment stays
    exactly as it closed: no reopen, no new moment, no second lock.

    (i) N/A 且已写明理由：迟到的答复按定义就是**新** turn（它的 CP0 先落、拒绝在
    后）；这里要钉的是「episode 不被重开」。(ii) 适用（零形状）：两个 turn 都是教学
    turn、不产 analysis artifact，断言 0。(iii) 适用：拒绝即可解释终局，episode 痕迹
    分毫未动。(iv) 适用：不为已关闭的 episode 重发或重开任何东西。
    """

    db = world.db
    coordinator = make_teaching_coordinator(
        world.store, world.generation, make_lease(world.fence),
        ScriptedPersonaProvider(), world.learning, world.decision_cycles,
        world.teaching, world.targets,
    )
    opened = coordinator.request_teaching(_teaching_request("cm-p10-1-episode"))
    assert isinstance(opened, Ok), opened
    answered = coordinator.respond_to_teaching(
        _reply_request("cm-p10-1-episode-reply", CANONICAL_ANSWER)
    )
    assert isinstance(answered, Ok), answered
    assert answered.value.moment_state is MomentState.CLOSED
    closed_before = _moment_row(db)
    assert closed_before[1] == "CLOSED"
    assert closed_before[3] is not None and closed_before[2] is None  # §6 outcome
    assert db.execute("SELECT COUNT(*) FROM active_teaching_lock").fetchone()[0] == 0
    actions_before = int(
        db.execute("SELECT COUNT(*) FROM generation_action_intent").fetchone()[0]
    )

    late = coordinator.respond_to_teaching(
        _reply_request("cm-p10-1-episode-late", CANONICAL_ANSWER)
    )
    assert isinstance(late, Err), late
    assert late.error.code is DomainErrorCode.CONFLICT
    assert "no active teaching moment" in late.error.message
    assert _moment_row(db) == closed_before  # no reopen, not one column moved
    assert _counts(db, "teaching_moment", "active_teaching_lock",
                   "analysis_artifact") == {
        "teaching_moment": 1, "active_teaching_lock": 0, "analysis_artifact": 0
    }
    assert int(
        db.execute("SELECT COUNT(*) FROM generation_action_intent").fetchone()[0]
    ) == actions_before


# 13 — projection-crash-gap


def test_projection_crash_gap_rebuilds_the_deterministic_job_and_runs_it(
    world: World,
) -> None:
    """projection-crash-gap（IP §11 "pending projections"；RA §22 的 pending 面）.

    The process died between the CP4 `ensure` and the `drain`: one job row never
    landed (the gap) and the other is still PENDING (the queue). The startup
    sweep repairs the gap under the **deterministic** job id, keeps the PENDING
    row, and drains both to COMMITTED in one pass (controller.py:4088's three
    ordered steps) — work is not lost, and a second pass has nothing to do.

    (i) N/A：recovery 不重入 turn（turn 保持 COMPLETED）。(ii) 适用（零形状）：
    投影 sweep 不写 Learning 行。(iii) 适用——本类的主场：两个 job 都到 COMMITTED。
    (iv) N/A：投影没有投递。
    """

    db = world.db
    projections = CP4ProjectionRuntime(
        store=SqliteProjectionStore(db, world.fence),
        executors=complete_executors(
            NoopProjectionExecutor(PROJECTION_TYPE_RELATIONSHIP)
        ),
        turns=world.store,
    )
    coordinator = world.coordinator(projections=projections)
    done = coordinator.begin_turn(_chat_command("cm-p10-1-projection"))
    assert isinstance(done, Ok), done
    turn_id = str(done.value.turn_id)
    relationship = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn_id)
    episode = projection_id_for(PROJECTION_TYPE_EPISODE, turn_id)

    def jobs() -> set[tuple[str, str]]:
        return {
            (str(row[0]), str(row[1]))
            for row in db.execute(
                "SELECT projection_id, status FROM projection_job"
            ).fetchall()
        }

    assert jobs() == {(str(relationship), "COMMITTED"), (episode, "COMMITTED")}
    # the crash gap: the RELATIONSHIP row never landed, the EPISODE row was
    # never drained
    db.execute(
        "DELETE FROM projection_job WHERE projection_id = ?", (str(relationship),)
    )
    db.execute(
        "UPDATE projection_job SET status = 'PENDING' WHERE projection_id = ?",
        (episode,),
    )
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM projection_job").fetchone()[0] == 1
    learning_before = _counts(db, "analysis_artifact", "evidence_group")

    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_jobs == (relationship,)
    assert outcome.value.projection_recovery_unavailable is False
    assert jobs() == {(str(relationship), "COMMITTED"), (episode, "COMMITTED")}
    assert {str(run.projection_job_id) for run in outcome.value.projection_runs} == {
        str(relationship), episode
    }
    assert _counts(db, "analysis_artifact", "evidence_group") == learning_before
    assert _turn_row(db, turn_id)[:2] == ("COMPLETED", "REPLIED_FULL")

    again = coordinator.run_startup_recovery()
    assert isinstance(again, Ok), again
    assert again.value.projection_jobs == ()
    assert again.value.projection_runs == ()


# the table itself + the p10-0 consumption fact (honesty pins)


def test_the_thirteen_scenario_tags_map_one_to_one_onto_named_tests() -> None:
    """R3: the docstring carries one line per tag, each tag names exactly one
    test function, every cited recovery face is still a face of one of the
    modules this suite cites, and the four §24.1 words are the constants this
    file asserts with."""

    module = sys.modules[__name__]
    doc = module.__doc__ or ""
    tags = [tag for tag, _, _, _ in SCENARIOS]
    assert len(tags) == len(set(tags)) == 13
    names = [name for name in vars(module) if name.startswith("test_")]
    source = "\n".join(path.read_text(encoding="utf-8") for path in FACE_SOURCES)
    for tag, checkpoint, residue, faces in SCENARIOS:
        assert tag in doc, tag
        slug = tag.replace("-", "_").lower()
        matching = [name for name in names if name.startswith(f"test_{slug}")]
        assert len(matching) == 1, (tag, matching)
        assert checkpoint and residue
        for face in faces:
            # a face is a method or a dataclass the plan's own records use
            assert f"def {face}" in source or f"class {face}" in source, face
    assert {
        RECOVERY_DISPOSITION_RESUME_ANALYSIS,
        RECOVERY_DISPOSITION_RESUME_DECISION,
        RECOVERY_DISPOSITION_RESUME_ACTION,
        RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY,
    } == {
        "RESUME_ANALYSIS", "RESUME_DECISION",
        "RESUME_ACTION_BY_STABLE_ACTION_ID",
        "CONSERVATIVE_DELIVERY_RECONCILIATION",
    }
    assert len(names) == 15  # thirteen scenarios + the two honesty pins


def test_the_startup_line_itself_consumes_only_turns_and_locks(
    world: World,
) -> None:
    """p10-0 R5's fact, pinned where the suite can see it: the four new kinds
    are *classifiable* but not *consumed* — `run_startup_recovery` builds its
    scanner from three ports (turn source + lease + teaching locks), so its own
    plan carries TURN / LOCK items and never the four new words, while the same
    durable world scanned with the four ports injected names them.

    This is the honesty half of the suite: every scenario above says which face
    applies a residue; this test says which face does not.
    """

    db = world.db
    crashed = world.coordinator(
        persona=Refusing(_persona(world.generation), "begin_delivery")
    ).request_teaching(_teaching_request("cm-p10-1-consumption"))
    assert isinstance(crashed, Err), crashed
    moment_id, state, _, _, _ = _moment_row(db)
    assert state == "OPENING"
    turn_id = str(db.execute("SELECT turn_id FROM turn_record").fetchone()[0])
    action_id = _action_row(db, turn_id)[0]

    new = world.restart()
    injected = new.scan()
    assert set(_kinds(injected, RECOVERY_KIND_MOMENT)) == {moment_id}
    assert set(_kinds(injected, RECOVERY_KIND_LOCK)) == {moment_id}
    assert set(_kinds(injected, RECOVERY_KIND_ACTION)) == {action_id}
    assert set(_kinds(injected, RECOVERY_KIND_TURN)) == {turn_id}

    startup = new.coordinator().run_startup_recovery()
    assert isinstance(startup, Ok), startup
    assert {item.kind for item in startup.value.plan} == {
        RECOVERY_KIND_TURN, RECOVERY_KIND_LOCK
    }
    assert _plan_ids(startup.value.plan, RECOVERY_KIND_MOMENT) == []
    assert _plan_ids(startup.value.plan, RECOVERY_KIND_ACTION) == []
