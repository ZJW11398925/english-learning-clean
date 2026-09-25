"""p10-0 —— 四类 recovery scan surface 的真库钉子。

TASK-OPI-9dba34fb-….35（Phase 10 首刀）。IP §11 要 Recovery worker 扫七类，
本刀补齐此前没有读面的四类：旧 epoch 的 GenerationActionIntent / TeachingMoment
/ pending AnalysisArtifact / 未终态 ServerDeliveryRecord。本文件不重复模块
docstring 的论证，只钉四件事：

① 四类 kind 的**真库**扫描：残件行全部由真写入面造出（真教学开课 / CP0 提交 /
   真 Learning proposal 与 commit / 真 generation action 写入 / 真 §22 交付记录
   写入），再在**新 epoch** 下扫描 ⇒ 命中且 disposition 词正确；同一世界在**当前
   epoch** 下扫描 ⇒ 四类全空（当前 epoch 的行是活工作，不是残件）；
② 端口缺席 ⇒ plan 形状回到 P10-0 之前（TURN/LOCK 两 kind），且四类 kind 各自
   只在对应端口注入时出现；
③ plan 顺序 = TURN → ACTION → MOMENT → ANALYSIS → DELIVERY → LOCK（确定性、
   可重放、纯读）；
④ 模块 docstring 的 disposition 执行者表、四个无写入者 status 的裁定表、Lease
   的 epoch 投影表述**字面在册**，且 schema 里确无 lease 表（零迁移）。

红线自查：本文件全部经 Write/Edit 通道落盘；未触碰 migrations / behavioral_
baselines / docs / tests/architecture / registry.py；测试内 SQL 只用于控制组
（把行改成某个 durable 形状或删掉一行锁），不用于读面本身。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from elc.conversation import CommitUserTurn, SqliteConversationStore
from elc.learning.store import SqliteLearningStore
from elc.persona import ScriptedPersonaProvider
from elc.platform.db import epoch
from elc.platform.db.delivery_store import SqliteDeliveryRecordStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    ActionId,
    ClientMessageId,
    DecisionCycleId,
    InputId,
    Ok,
    TurnId,
)
from elc.runtime import recovery
from elc.runtime.decision_cycles import DecisionCycleBindings
from elc.runtime.delivery_records import ServerDeliveryRecord
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
    AnalysisArtifactRecoverySource,
    DeliveryRecordRecoverySource,
    GenerationActionRecoverySource,
    StartupRecoveryScanner,
    TeachingMomentRecoverySource,
    recovery_disposition,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    InputEnvelope,
    InteractionChannel,
    TurnStatus,
)
from elc.teaching.controller import TeachingController
from elc.teaching.request import TeachingRequest
from elc.teaching.store import SqliteTeachingStore
from tests.phase3.conftest import (
    CONV,
    RECEIVED_AT,
    RUNTIME_VERSION,
    make_lease,
    make_teaching_coordinator,
)

FOCUS_TARGET = "res-hedge-i-think"
STARTED_AT = "2026-09-25T10:00:00+00:00"
TERMINAL_AT = "2026-09-25T10:00:01+00:00"

#: Every table this cut's four kinds read, plus the ones the teaching world
#: writes while it is being built — the purity check counts them all.
COUNTED_TABLES = (
    "turn_record",
    "generation_action_intent",
    "teaching_moment",
    "active_teaching_lock",
    "analysis_artifact",
    "server_delivery_record",
    "decision_cycle",
    "gate_decision",
    "gate_execution_status",
)

#: R1's kind → disposition word table, as one literal a plan may carry.
REGISTERED_KIND_WORDS = (
    (RECOVERY_KIND_TURN, RECOVERY_DISPOSITION_RESUME_ANALYSIS),
    (RECOVERY_KIND_ACTION, RECOVERY_DISPOSITION_RESUME_ACTION),
    (RECOVERY_KIND_MOMENT, MOMENT_RECOVERY_ACTION),
    (RECOVERY_KIND_ANALYSIS, RECOVERY_DISPOSITION_RESUME_ANALYSIS),
    (RECOVERY_KIND_DELIVERY, RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY),
    (RECOVERY_KIND_LOCK, TEACHING_LOCK_RECOVERY_ACTION),
)


# ---------------------------------------------------------------------------
# The world: every durable shape the four kinds read, built by real faces
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class World:
    """One old epoch's residue, as durable ids (see :func:`build_world`)."""

    #: A chat turn stopped at CP0 whose analysis is still pending.
    pending_turn_id: str
    pending_analysis_id: str
    #: A nonterminal action of that turn's cycle, and its unterminated send.
    orphan_action_id: str
    unterminated_delivery_action_id: str
    #: Controls: a TERMINAL action, a terminated send, a committed analysis.
    terminal_action_id: str
    terminated_delivery_action_id: str
    committed_turn_id: str
    committed_analysis_status: str
    #: The teaching flow's own residue: a nonterminal moment + its lock.
    moment_id: str
    teaching_turn_id: str


@dataclass(frozen=True)
class Restarted:
    """The world after a restart: every store rebuilt on the new epoch."""

    fence: RuntimeEpochFence
    store: SqliteConversationStore
    learning: SqliteLearningStore
    generation: SqliteGenerationStore
    teaching_store: SqliteTeachingStore
    teaching: TeachingController
    delivery: SqliteDeliveryRecordStore


def _commit_chat_turn(store: SqliteConversationStore, cmid: str) -> str:
    """One real CP0 commit (RA §4 step 1) — no analysis, no generation."""

    result = store.commit_user_turn(
        CommitUserTurn(
            conversation_id=CONV,
            envelope=InputEnvelope(
                input_id=InputId(f"in-{cmid}"),
                client_message_id=ClientMessageId(cmid),
                conversation_id=str(CONV),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload="raw-payload",
                received_at=RECEIVED_AT,
            ),
            raw_content="I think it is fine.",
            runtime_version=RUNTIME_VERSION,
        )
    )
    assert isinstance(result, Ok), result
    return str(result.value.turn_id)


def _slice_of(store: SqliteConversationStore, turn_id: str):
    result = store.get_canonical_turn_slice(TurnId(turn_id))
    assert isinstance(result, Ok), result
    return result.value


def _record(
    action_id: str,
    turn_id: str,
    cycle_id: str,
    status: GenerationActionStatus,
) -> GenerationActionIntentRecord:
    return GenerationActionIntentRecord(
        action_id=ActionId(action_id),
        turn_id=TurnId(turn_id),
        decision_cycle_id=DecisionCycleId(cycle_id),
        moment_id=None,
        assistant_turn_id=f"at-{action_id}",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        generation_contract_id="gc-p10-0-probe",
        status=status,
        attempt_count=0,
    )


def build_world(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    learning: SqliteLearningStore,
    generation: SqliteGenerationStore,
    decision_cycles,
    teaching: TeachingController,
    targets,
    delivery: SqliteDeliveryRecordStore,
    fence: RuntimeEpochFence,
) -> World:
    """Build the old-epoch world for the p10-0 scan, every row by a real face.

    The teaching leg is the real P3-1A assembly's ``request_teaching`` (CP2
    commit + opening delivery), and the four new kinds' rows come from the
    real write faces: CP0 (``commit_user_turn``), the Learning analysis
    producer, the DecisionCycle unit, the generation action writer and the
    §22 delivery-record writer. The two controls (a TERMINAL action and a
    terminal send) ride the same faces.
    """

    coordinator = make_teaching_coordinator(
        store,
        generation,
        make_lease(fence),
        ScriptedPersonaProvider(),
        learning,
        decision_cycles,
        teaching,
        targets,
    )
    opened = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=FOCUS_TARGET,
            client_message_id=ClientMessageId("cm-p10-0-open"),
            requested_at=RECEIVED_AT,
        )
    )
    assert isinstance(opened, Ok), opened
    moment_id = str(opened.value.moment_id)
    teaching_turn_id = str(opened.value.turn_id)

    # A chat turn stopped at CP0: its analysis stays pending, and its cycle
    # carries the nonterminal action whose send never terminated.
    pending_turn_id = _commit_chat_turn(store, "cm-p10-0-pending")
    cycle_id = f"dcy-p10-0-{pending_turn_id}"
    recorded = decision_cycles.record_decision_cycle(
        decision_cycle_id=DecisionCycleId(cycle_id),
        turn_id=TurnId(pending_turn_id),
        bindings=DecisionCycleBindings(),
        expected_turn_state_version=1,
    )
    assert isinstance(recorded, Ok), recorded
    proposal = learning.record_learning_analysis(
        _slice_of(store, pending_turn_id)
    )
    assert isinstance(proposal, Ok), proposal
    pending_analysis_id = str(proposal.value.analysis_id)

    orphan_action_id = "act-p10-0-orphan"
    created = generation.create_action(
        _record(
            orphan_action_id,
            pending_turn_id,
            cycle_id,
            GenerationActionStatus.REQUESTED,
        )
    )
    assert isinstance(created, Ok), created
    written = delivery.record_server_delivery(
        ServerDeliveryRecord(
            action_id=ActionId(orphan_action_id),
            assistant_turn_id=f"at-{orphan_action_id}",
            state="SENDING",
            sent_prefix="",
            last_chunk_seq=0,
            started_at=STARTED_AT,
            terminal_at=None,
        )
    )
    assert isinstance(written, Ok), written

    terminal_action_id = "act-p10-0-terminal"
    created = generation.create_action(
        _record(
            terminal_action_id,
            pending_turn_id,
            cycle_id,
            GenerationActionStatus.REQUESTED,
        )
    )
    assert isinstance(created, Ok), created
    moved = generation.transition_action(
        ActionId(terminal_action_id),
        GenerationActionStatus.REQUESTED,
        GenerationActionStatus.TERMINAL,
    )
    assert isinstance(moved, Ok), moved
    closed = delivery.record_server_delivery(
        ServerDeliveryRecord(
            action_id=ActionId(terminal_action_id),
            assistant_turn_id=f"at-{terminal_action_id}",
            state="SENT_COMPLETE",
            sent_prefix="hello",
            last_chunk_seq=0,
            started_at=STARTED_AT,
            terminal_at=TERMINAL_AT,
        )
    )
    assert isinstance(closed, Ok), closed

    # A second CP0 turn whose analysis reaches a real commit — the "over"
    # shape the ANALYSIS kind must never name.
    committed_turn_id = _commit_chat_turn(store, "cm-p10-0-committed")
    committed_slice = _slice_of(store, committed_turn_id)
    proposal_b = learning.record_learning_analysis(committed_slice)
    assert isinstance(proposal_b, Ok), proposal_b
    committed = learning.commit_learning_evidence(
        proposal_b.value, committed_slice
    )
    assert isinstance(committed, Ok), committed
    committed_analysis_status = str(
        db.execute(
            "SELECT status FROM analysis_artifact WHERE analysis_id = ?",
            (str(proposal_b.value.analysis_id),),
        ).fetchone()[0]
    )

    return World(
        pending_turn_id=pending_turn_id,
        pending_analysis_id=pending_analysis_id,
        orphan_action_id=orphan_action_id,
        unterminated_delivery_action_id=orphan_action_id,
        terminal_action_id=terminal_action_id,
        terminated_delivery_action_id=terminal_action_id,
        committed_turn_id=committed_turn_id,
        committed_analysis_status=committed_analysis_status,
        moment_id=moment_id,
        teaching_turn_id=teaching_turn_id,
    )


@pytest.fixture()
def world(
    db: sqlite3.Connection,
    fence: RuntimeEpochFence,
    store: SqliteConversationStore,
    generation_store: SqliteGenerationStore,
    learning: SqliteLearningStore,
    decision_cycle_store,
    teaching_store: SqliteTeachingStore,
    teaching_controller: TeachingController,
    target_provider,
    conversation,
    delivery_store: SqliteDeliveryRecordStore,
) -> World:
    """The p10-0 world, built once per test on the real phase-3 assembly."""

    del teaching_store, conversation  # requested for their side effects
    return build_world(
        db,
        store,
        learning,
        generation_store,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        delivery_store,
        fence,
    )


def _restart(db: sqlite3.Connection) -> Restarted:
    """A restart: a new epoch, and every store rebuilt on it."""

    new_fence = epoch.open_runtime_epoch(db)
    new_teaching_store = SqliteTeachingStore(db, new_fence)
    return Restarted(
        fence=new_fence,
        store=SqliteConversationStore(db, new_fence),
        learning=SqliteLearningStore(db, new_fence),
        generation=SqliteGenerationStore(db, new_fence),
        teaching_store=new_teaching_store,
        teaching=TeachingController(new_teaching_store),
        delivery=SqliteDeliveryRecordStore(db, new_fence),
    )


def _new_ports(new: Restarted) -> dict[str, object]:
    """The four P10-0 ports, satisfied by the real stores."""

    return {
        "generation_actions": new.generation,
        "teaching_moments": new.teaching_store,
        "analysis_artifacts": new.learning,
        "delivery_records": new.delivery,
    }


def _scan(
    lease,
    store: SqliteConversationStore,
    teaching: TeachingController,
    **ports: object,
):
    return StartupRecoveryScanner(store, lease, teaching, **ports).scan()


def _items(plan, kind: str) -> list:
    assert isinstance(plan, Ok), plan
    return [item for item in plan.value if item.kind == kind]


def _ids(plan, kind: str) -> list[str]:
    return [item.id for item in _items(plan, kind)]


def _order(plan) -> list[str]:
    assert isinstance(plan, Ok), plan
    return list(dict.fromkeys(item.kind for item in plan.value))


def _counts(db: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in COUNTED_TABLES
    }


def _full_plan(db: sqlite3.Connection, world: World, new: Restarted):
    assert world  # the world is the fixture's, the plan is the new epoch's
    return _scan(make_lease(new.fence), new.store, new.teaching, **_new_ports(new))


# ---------------------------------------------------------------------------
# ① 真库命中：四类 kind 各命中旧 epoch 的残件，词是 R1 的词
# ---------------------------------------------------------------------------


def test_action_kind_names_the_old_epoch_nonterminal_action(
    world: World, db: sqlite3.Connection
) -> None:
    """ACTION names the PREPARED old-epoch action and nothing else: a
    TERMINAL old-epoch action is over, not residue."""

    new = _restart(db)
    plan = _full_plan(db, world, new)
    assert _ids(plan, RECOVERY_KIND_ACTION) == [world.orphan_action_id]
    assert _items(plan, RECOVERY_KIND_ACTION)[0].action == (
        RECOVERY_DISPOSITION_RESUME_ACTION
    )
    assert world.terminal_action_id not in _ids(plan, RECOVERY_KIND_ACTION)


def test_moment_kind_names_the_old_epoch_nonterminal_moment(
    world: World, db: sqlite3.Connection
) -> None:
    """MOMENT names the AWAITING_USER moment whose owning turn is old-epoch
    (it still holds a lock, so LOCK names it too — two kinds, two faces)."""

    new = _restart(db)
    plan = _full_plan(db, world, new)
    assert _ids(plan, RECOVERY_KIND_MOMENT) == [world.moment_id]
    assert _items(plan, RECOVERY_KIND_MOMENT)[0].action == (
        MOMENT_RECOVERY_ACTION
    )
    assert _ids(plan, RECOVERY_KIND_LOCK) == [world.moment_id]


def test_analysis_kind_names_the_pending_old_epoch_artifact(
    world: World, db: sqlite3.Connection
) -> None:
    """ANALYSIS names the PRODUCED artifact a crash left before CP1; the
    committed one is never named."""

    new = _restart(db)
    plan = _full_plan(db, world, new)
    assert _ids(plan, RECOVERY_KIND_ANALYSIS) == [world.pending_analysis_id]
    assert _items(plan, RECOVERY_KIND_ANALYSIS)[0].action == (
        RECOVERY_DISPOSITION_RESUME_ANALYSIS
    )
    assert world.committed_analysis_status not in (
        "PRODUCED",
        "COMMIT_PENDING",
    )


def test_delivery_kind_names_the_unterminated_old_epoch_send(
    world: World, db: sqlite3.Connection
) -> None:
    """DELIVERY names the §22 row with no terminal instant; the frozen one
    (terminal_at set) is never named."""

    new = _restart(db)
    plan = _full_plan(db, world, new)
    assert _ids(plan, RECOVERY_KIND_DELIVERY) == [
        world.unterminated_delivery_action_id
    ]
    assert _items(plan, RECOVERY_KIND_DELIVERY)[0].action == (
        RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY
    )
    assert world.terminated_delivery_action_id not in _ids(
        plan, RECOVERY_KIND_DELIVERY
    )


# ---------------------------------------------------------------------------
# ② 当前 epoch 的同类行不是残件：四类全空
# ---------------------------------------------------------------------------


def test_the_current_epoch_scan_is_empty_for_all_six_kinds(
    world: World,
    store: SqliteConversationStore,
    fence: RuntimeEpochFence,
    teaching_controller: TeachingController,
    generation_store: SqliteGenerationStore,
    learning: SqliteLearningStore,
    teaching_store: SqliteTeachingStore,
    delivery_store: SqliteDeliveryRecordStore,
) -> None:
    """The same durable world, scanned by the epoch that owns it: every row
    is live work (the turns, the action, the moment and its lock, the
    pending analysis, the open send), so the plan carries nothing at all.

    This is the widened form of the two pre-P10-0 pins (a lock owned by the
    current epoch is a mutual-exclusion fact; a current-epoch action is
    live), extended to all six kinds at once.
    """

    plan = _scan(
        make_lease(fence),
        store,
        teaching_controller,
        generation_actions=generation_store,
        teaching_moments=teaching_store,
        analysis_artifacts=learning,
        delivery_records=delivery_store,
    )
    assert isinstance(plan, Ok), plan
    assert plan.value == ()
    assert world.pending_turn_id  # the turn really is in the plan's read set


# ---------------------------------------------------------------------------
# ③ 控制组：旧 epoch 但已是「过」形状的行
# ---------------------------------------------------------------------------


def test_moment_kind_ignores_a_moment_the_sweep_already_closed(
    world: World, db: sqlite3.Connection
) -> None:
    """After the real sweep runs under the new epoch the moment is CLOSED and
    its lock is gone — CLOSED is terminal, so neither kind names it."""

    new = _restart(db)
    swept = new.teaching_store.recover_orphan_teaching_locks(new.fence.current)
    assert isinstance(swept, Ok), swept
    assert swept.value == (world.moment_id,)
    plan = _full_plan(db, world, new)
    assert world.moment_id not in _ids(plan, RECOVERY_KIND_MOMENT)
    assert world.moment_id not in _ids(plan, RECOVERY_KIND_LOCK)


def test_moment_kind_sees_a_lock_free_moment_the_lock_kind_cannot(
    world: World, db: sqlite3.Connection
) -> None:
    """The load-bearing new surface: a moment whose lock is already gone
    (released, or never re-taken past OPENING) is nonterminal old-epoch work
    the orphan-lock read cannot see. The plan names it as MOMENT and LOCK
    stays empty.

    The lock row is removed by a direct statement because no production face
    deletes a lock without closing its moment; the shape is a durable fact
    either way, and this test is about the read predicate.
    """

    db.execute(
        "DELETE FROM active_teaching_lock WHERE moment_id = ?",
        (world.moment_id,),
    )
    db.commit()
    new = _restart(db)
    plan = _full_plan(db, world, new)
    assert _ids(plan, RECOVERY_KIND_MOMENT) == [world.moment_id]
    assert _ids(plan, RECOVERY_KIND_LOCK) == []


# ---------------------------------------------------------------------------
# ④ 端口缺席 / 逐端口：plan 形状只在端口注入时扩张
# ---------------------------------------------------------------------------


def test_absent_new_ports_keep_the_pre_p10_0_plan_shape(
    world: World, db: sqlite3.Connection
) -> None:
    """A scanner without the four new ports sees exactly the pre-P10-0 plan
    (TURN items, then the lock residue) — the shape every earlier suite
    pins."""

    new = _restart(db)
    legacy = StartupRecoveryScanner(
        new.store, make_lease(new.fence), new.teaching
    ).scan()
    assert _order(legacy) == [RECOVERY_KIND_TURN, RECOVERY_KIND_LOCK]
    explicit_none = _scan(
        make_lease(new.fence),
        new.store,
        new.teaching,
        generation_actions=None,
        teaching_moments=None,
        analysis_artifacts=None,
        delivery_records=None,
    )
    assert explicit_none == legacy
    full = _full_plan(db, world, new)
    assert _order(full)[0] == RECOVERY_KIND_TURN
    assert _order(full)[-1] == RECOVERY_KIND_LOCK


@pytest.mark.parametrize(
    ("port_name", "kind"),
    [
        ("generation_actions", RECOVERY_KIND_ACTION),
        ("teaching_moments", RECOVERY_KIND_MOMENT),
        ("analysis_artifacts", RECOVERY_KIND_ANALYSIS),
        ("delivery_records", RECOVERY_KIND_DELIVERY),
    ],
)
def test_each_new_kind_appears_iff_its_port_is_injected(
    world: World, db: sqlite3.Connection, port_name: str, kind: str
) -> None:
    """Dropping one port removes exactly that kind: the four sources are
    independent, and none of them is reached through another."""

    new = _restart(db)
    ports = _new_ports(new)
    assert kind in _order(_scan(
        make_lease(new.fence), new.store, new.teaching, **ports
    ))
    without = dict(ports)
    without[port_name] = None
    assert kind not in _order(_scan(
        make_lease(new.fence), new.store, new.teaching, **without
    ))


# ---------------------------------------------------------------------------
# ⑤ plan 顺序 / 确定性 / 纯读
# ---------------------------------------------------------------------------


def test_the_plan_order_is_turn_action_moment_analysis_delivery_lock(
    world: World, db: sqlite3.Connection
) -> None:
    """The kind order is the plan's identity (P10-0 R6): TURN → ACTION →
    MOMENT → ANALYSIS → DELIVERY → LOCK, and every kind is present in this
    world."""

    new = _restart(db)
    plan = _full_plan(db, world, new)
    assert _order(plan) == [
        RECOVERY_KIND_TURN,
        RECOVERY_KIND_ACTION,
        RECOVERY_KIND_MOMENT,
        RECOVERY_KIND_ANALYSIS,
        RECOVERY_KIND_DELIVERY,
        RECOVERY_KIND_LOCK,
    ]
    assert _ids(plan, RECOVERY_KIND_TURN) == [
        world.pending_turn_id,
        world.committed_turn_id,
    ]
    for item in plan.value:
        assert (item.kind, item.action) in REGISTERED_KIND_WORDS


def test_the_scan_is_idempotent_and_writes_nothing(
    world: World, db: sqlite3.Connection
) -> None:
    """§22's pure-read bargain: two scans of one durable state return the
    same plan, and no table moved between them."""

    new = _restart(db)
    before = _counts(db)
    first = _full_plan(db, world, new)
    second = _full_plan(db, world, new)
    assert first == second
    assert _counts(db) == before


# ---------------------------------------------------------------------------
# ⑥ 词表 / 端口形状 / 模块 docstring 的两张表与 Lease 投影
# ---------------------------------------------------------------------------


def test_the_kind_and_disposition_vocabulary_is_registered() -> None:
    """The six kinds and the four §24.1 words are module constants, and the
    mapping function speaks the same constants (one definition, two faces)."""

    assert (
        RECOVERY_KIND_TURN,
        RECOVERY_KIND_ACTION,
        RECOVERY_KIND_MOMENT,
        RECOVERY_KIND_ANALYSIS,
        RECOVERY_KIND_DELIVERY,
        RECOVERY_KIND_LOCK,
    ) == ("TURN", "ACTION", "MOMENT", "ANALYSIS", "DELIVERY", "LOCK")
    assert (
        RECOVERY_DISPOSITION_RESUME_ANALYSIS,
        RECOVERY_DISPOSITION_RESUME_DECISION,
        RECOVERY_DISPOSITION_RESUME_ACTION,
        RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY,
    ) == (
        "RESUME_ANALYSIS",
        "RESUME_DECISION",
        "RESUME_ACTION_BY_STABLE_ACTION_ID",
        "CONSERVATIVE_DELIVERY_RECONCILIATION",
    )
    assert MOMENT_RECOVERY_ACTION == "CLOSE_ORPHAN_MOMENT"
    assert recovery_disposition(TurnStatus.USER_COMMITTED) == (
        RECOVERY_DISPOSITION_RESUME_ANALYSIS
    )
    assert recovery_disposition(TurnStatus.DECIDING) == (
        RECOVERY_DISPOSITION_RESUME_DECISION
    )
    assert recovery_disposition(TurnStatus.GENERATING) == (
        RECOVERY_DISPOSITION_RESUME_ACTION
    )
    assert recovery_disposition(TurnStatus.DELIVERING) == (
        RECOVERY_DISPOSITION_CONSERVATIVE_DELIVERY
    )


def test_the_four_ports_are_runtime_checkable_and_the_stores_satisfy_them(
    generation_store: SqliteGenerationStore,
    learning: SqliteLearningStore,
    teaching_store: SqliteTeachingStore,
    delivery_store: SqliteDeliveryRecordStore,
) -> None:
    """R2's shape: four ``@runtime_checkable`` Protocols, each satisfied
    structurally by the durable store that owns the rows."""

    assert isinstance(generation_store, GenerationActionRecoverySource)
    assert isinstance(teaching_store, TeachingMomentRecoverySource)
    assert isinstance(learning, AnalysisArtifactRecoverySource)
    assert isinstance(delivery_store, DeliveryRecordRecoverySource)
    for protocol, method in (
        (GenerationActionRecoverySource, "orphan_generation_actions"),
        (TeachingMomentRecoverySource, "orphan_moment_ids"),
        (AnalysisArtifactRecoverySource, "pending_analysis_artifacts"),
        (DeliveryRecordRecoverySource, "unterminal_delivery_records"),
    ):
        assert hasattr(protocol, method)


def test_the_executor_table_is_literal_in_the_module_docstring() -> None:
    """§2-B: the disposition → executor table is in the module docstring
    with one row per word and the entry face that performs it."""

    doc = recovery.__doc__ or ""
    for word in (
        "RESUME_ANALYSIS",
        "RESUME_DECISION",
        "RESUME_ACTION_BY_STABLE_ACTION_ID",
        "CONSERVATIVE_DELIVERY_RECONCILIATION",
        "RELEASE_ORPHAN_TEACHING_LOCK",
        "CLOSE_ORPHAN_MOMENT",
    ):
        assert f"word: {word}" in doc, word
    for marker in (
        "入口重入",
        "startup 线",
        "无 (this cut classifies only",
        "``_begin_turn_guarded``",
        "``request_teaching`` / ``respond_to_teaching``",
        "``claim_action_for_recovery``",
        "``reconcile_delivering_residue``",
        "``_close_residual_turns``",
        "``recover_orphan_teaching``",
        "Revisit:",
    ):
        assert marker in doc, marker


def test_the_status_adjudication_table_is_literal_in_the_module_docstring() -> None:
    """§2-C: the four STATE_MACHINES §10 words with no writer today, each
    with its Revisit trigger, and FAILED_RECOVERABLE called out as having no
    accepting entry either."""

    doc = recovery.__doc__ or ""
    for word, revisit in (
        ("RECEIVED", "Revisit: a writer appears"),
        ("DELIVERY_TERMINAL", "Revisit: a writer appears"),
        ("POSTPROCESSING", "Revisit: a writer appears"),
        (
            "FAILED_RECOVERABLE",
            "Revisit: a writer appears, or an entry accepts the word",
        ),
    ):
        assert f"word: {word}" in doc, word
        assert revisit in doc, (word, revisit)
    assert doc.count("writer: 无") == 4
    assert "no entry accepts it either" in doc
    assert "unreachable today" in doc


def test_the_lease_projection_is_documented_and_no_lease_table_exists(
    db: sqlite3.Connection,
) -> None:
    """§2-D: the lease's sweep surface is the three owner_epoch projections,
    no lease table is added, and the schema agrees (zero migrations)."""

    doc = recovery.__doc__ or ""
    for marker in (
        "P10-0 lease projection (D)",
        "``turn_record`` (kind TURN)",
        "``generation_action_intent`` (kind ACTION)",
        "``active_teaching_lock``",
        "none is added",
    ):
        assert marker in doc, marker
    tables = {
        str(row[0])
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert not [name for name in tables if "lease" in name.lower()]
