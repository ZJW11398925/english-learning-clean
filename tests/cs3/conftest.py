"""cs-3（无限聊天刀）共享夹具：phase4 stress 的真装配 + 真的 candidate 生产者.

装配助手（``make_lease`` / ``make_teaching_coordinator``）照 P3-1A 纪律
import 不复制；store 构造夹具与 phase4/deletion 各包 conftest 同形——薄构造
各自声明是仓内既有惯例。本包唯一的语义差异是 RELATIONSHIP 执行器的
candidate 缝：cs-3 用真的 ``PatternCandidateProvider``（host.py 装配同形），
不是脚本桩——验收 ② 的「名字记忆」必须走真的 17 模式生产链。
"""

from __future__ import annotations

import sqlite3
import time
from typing import Iterator

import pytest

from elc.conversation.commands import CommitUserTurn
from elc.conversation.store import SqliteConversationStore
from elc.conversation.types import ConversationStatus
from elc.learning.store import SqliteLearningStore
from elc.persona import ScriptedPersonaProvider
from elc.persona.provider import ProviderOutput
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.decision_cycle_store import SqliteDecisionCycleStore
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.db.projection_store import SqliteProjectionStore
from elc.platform.types import (
    ClientMessageId,
    InputId,
    InteractionChannel,
    Ok,
)
from elc.relationship import (
    EpisodeProjectionExecutor,
    RelationshipProjectionExecutor,
)
from elc.relationship.candidates import PatternCandidateProvider
from elc.relationship.controller import RelationshipController
from elc.relationship.episode import rebuild_episode
from elc.relationship.episode_store import SqliteEpisodeStore
from elc.relationship.recorder import RelationshipRecorder
from elc.relationship.store import SqliteRelationshipStore
from elc.relationship.types import SamePersonaExistingRelationshipSummary
from elc.runtime.controller import ConversationCoordinator
from elc.runtime.persona_views import ControllerPersonaViews
from elc.runtime.projections import CP4ProjectionRuntime
from elc.runtime.types import InputEnvelope
from elc.teaching.controller import TeachingController
from elc.teaching.store import SqliteTeachingStore
from elc.user_config.controller import UserConfigController
from elc.user_config.store import SqliteUserConfigStore
from tests.conftest import AssemblyGenerationStore
from tests.phase3.conftest import make_lease, make_teaching_coordinator
from tests.phase3.target_fixtures import FixtureTeachingTargetProvider
from tests.phase4.conftest import (
    PERSONA_A,
    REL_USER,
    open_conversation_for,
)

#: 测试会话与两端定数（PERSONA_A / REL_USER 沿用 phase4 的定值）。
CONVERSATION = "conv-cs3-unlimited"

#: 第 3 轮的叙事句——刻意不匹配 17 模式（无 name/job/live/from/like 形状），
#: 它进 prompt 的唯一通道是 episode-v2 的封存层。
PUPPY_LINE = "I'm adopting a puppy next month."

#: 第 5 轮的模式句——17 模式可捕，走 [relationship] 通道。
MARY_LINE = "my name is Mary"

#: 中段填充句的模板（含轮号，逐轮可辨识；无模式形状）。刻意**短于**两句
#: 植入句：段首+最长的折叠规则是一条记忆政策（研究简报失败模式 1 的
#: 漏检面），场景设计必须与合作——「关键事实」以段内最长行的身份被记住。
_FILLER = "turn {index}: all is well."

#: 固定信封时间戳（J4：数据里的时刻必须是常量，零 clock）。
REQUESTED_AT = "2026-10-02T10:00:00+00:00"
RUNTIME_VERSION = "runtime-cs3"

#: 六十轮共用的固定回复。**必须是 script 固定文本，不能用裸
#: ``ScriptedPersonaProvider()``**：裸桩走 ``derive_reply`` 的回声规则，而
#: ``[episode]`` 的 recent_events describe 行（prompt 末节的最后一次
#: ``" user: "`` 匹配）会让回声吞进 describe 尾巴——逐轮翻倍的指数爆炸
#: （phase4 stress 同形态单例 35.5s 的既有病灶，本刀登记不改）。
#: script 耗尽后 ScriptedPersonaProvider 重复末项，六十轮恒定小文本。
REPLY_TEXT = "Glad you told me."


class Cs3RecordingProvider(ScriptedPersonaProvider):
    """The prompt-capturing messenger with one fixed reply (the cs-1
    RecordingProvider shape)."""

    def __init__(self) -> None:
        super().__init__(script=(ProviderOutput(text=REPLY_TEXT),))
        self.prompts: list[object] = []

    def call(self, prompt: object):
        self.prompts.append(prompt)
        return super().call(prompt)  # type: ignore[arg-type]

    @property
    def prompt_texts(self) -> list[str]:
        return [prompt.prompt_text for prompt in self.prompts]  # type: ignore[attr-defined]


# -- the store fixtures (the phase4 shapes, declared for this package) ------


@pytest.fixture()
def db() -> Iterator[sqlite3.Connection]:
    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture()
def fence(db: sqlite3.Connection) -> RuntimeEpochFence:
    return epoch.open_runtime_epoch(db)


@pytest.fixture()
def store(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteConversationStore:
    return SqliteConversationStore(db, fence)


@pytest.fixture()
def generation_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> AssemblyGenerationStore:
    return AssemblyGenerationStore(db, fence)


@pytest.fixture()
def learning(db: sqlite3.Connection, fence: RuntimeEpochFence) -> SqliteLearningStore:
    return SqliteLearningStore(db, fence)


@pytest.fixture()
def decision_cycle_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteDecisionCycleStore:
    return SqliteDecisionCycleStore(db, fence)


@pytest.fixture()
def teaching_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteTeachingStore:
    return SqliteTeachingStore(db, fence)


@pytest.fixture()
def teaching_controller(teaching_store: SqliteTeachingStore) -> TeachingController:
    return TeachingController(teaching_store)


@pytest.fixture()
def target_provider() -> FixtureTeachingTargetProvider:
    return FixtureTeachingTargetProvider()


@pytest.fixture()
def relationship_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteRelationshipStore:
    return SqliteRelationshipStore(db, fence)


@pytest.fixture()
def relationship_controller(
    relationship_store: SqliteRelationshipStore,
) -> RelationshipController:
    return RelationshipController(relationship_store)


@pytest.fixture()
def episode_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteEpisodeStore:
    return SqliteEpisodeStore(db, fence)


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


@pytest.fixture()
def persona_views(
    relationship_controller: RelationshipController,
    episode_store: SqliteEpisodeStore,
    user_config_controller: UserConfigController,
) -> ControllerPersonaViews:
    return ControllerPersonaViews(
        relationship=relationship_controller,
        episodes=episode_store,
        user_config=user_config_controller,
        user_id=REL_USER,
    )


@pytest.fixture()
def projection_store(
    db: sqlite3.Connection, fence: RuntimeEpochFence
) -> SqliteProjectionStore:
    return SqliteProjectionStore(db, fence)


@pytest.fixture()
def episode_projection(
    store: SqliteConversationStore,
    episode_store: SqliteEpisodeStore,
    relationship_controller: RelationshipController,
) -> EpisodeProjectionExecutor:
    """The live EPISODE executor (the phase4 shape): real episode store, real
    relationship read face, real conversation store."""

    return EpisodeProjectionExecutor(
        store=episode_store,
        controller=relationship_controller,
        conversation=store,
        user_id=REL_USER,
    )


@pytest.fixture()
def cs3_relationship_projection(
    store: SqliteConversationStore,
    relationship_controller: RelationshipController,
) -> RelationshipProjectionExecutor:
    """The RELATIONSHIP executor as the shipped assembly builds it: the real
    recorder over the durable classifier, the real controller, and the real
    candidate *producer* (elc.relationship.candidates) — the host.py shape,
    with no scripted stub in the memory channel."""

    return RelationshipProjectionExecutor(
        recorder=RelationshipRecorder(store),
        controller=relationship_controller,
        conversation=store,
        user_id=REL_USER,
        candidates=PatternCandidateProvider(),
    )


@pytest.fixture()
def provider() -> Cs3RecordingProvider:
    return Cs3RecordingProvider()


@pytest.fixture()
def cs3_coordinator(
    store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    fence: RuntimeEpochFence,
    learning: SqliteLearningStore,
    decision_cycle_store: SqliteDecisionCycleStore,
    teaching_controller: TeachingController,
    target_provider: FixtureTeachingTargetProvider,
    persona_views: ControllerPersonaViews,
    projection_store: SqliteProjectionStore,
    episode_projection,
    cs3_relationship_projection: RelationshipProjectionExecutor,
    provider: Cs3RecordingProvider,
) -> ConversationCoordinator:
    """The P3-1A assembly plus the CP4 port over both real executors (the
    phase4 stress shape; the projections run to COMMITTED inside each turn).
    """

    runtime = CP4ProjectionRuntime(
        store=projection_store,
        executors=(cs3_relationship_projection, episode_projection),
        turns=store,
    )
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        provider,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        projections=runtime,
        persona_views=persona_views,
    )


# -- the scripted-dialogue drivers ------------------------------------------


def cs3_line(index: int) -> str:
    """The deterministic scripted dialogue: the two planted sentences, then
    indexable filler (the last four turns must be nameable for the
    current-layer assertion)."""

    if index == 3:
        return PUPPY_LINE
    if index == 5:
        return MARY_LINE
    return _FILLER.format(index=index)


def drive_turn(
    coordinator: ConversationCoordinator,
    index: int,
    *,
    conversation,
) -> tuple[object, float]:
    """One Basic Persona Conversation turn with its wall-clock duration
    (the ⑦ read is an environment observation, kept out of every other
    assertion's path — the phase4 stress 口径, with the one leg ⑦ needs)."""

    started = time.perf_counter()
    result = coordinator.begin_turn(
        CommitUserTurn(
            conversation_id=conversation,
            envelope=InputEnvelope(
                input_id=InputId(f"in-cs3-{index}"),
                client_message_id=ClientMessageId(f"cs3-{index}"),
                conversation_id=str(conversation),
                persona_id=None,
                scene_id=None,
                interaction_channel=InteractionChannel.TEXT,
                raw_payload=f"raw-cs3-{index}",
                received_at=REQUESTED_AT,
            ),
            raw_content=cs3_line(index),
            runtime_version=RUNTIME_VERSION,
        )
    )
    elapsed = time.perf_counter() - started
    assert isinstance(result, Ok), result
    turn = result.value
    assert turn.outcome == "REPLIED_FULL"
    assert turn.turn_status.value == "COMPLETED"
    return turn, elapsed


def run_conversation(
    coordinator: ConversationCoordinator,
    store: SqliteConversationStore,
    rounds: int,
    *,
    conversation_id: str = CONVERSATION,
):
    """A deterministic scripted conversation over the real chain; returns
    (conversation id, per-turn durations)."""

    conversation = open_conversation_for(store, conversation_id, PERSONA_A)
    durations = [
        drive_turn(coordinator, index, conversation=conversation)[1]
        for index in range(1, rounds + 1)
    ]
    return conversation, durations


def rebuilt_episode_of(store: SqliteConversationStore, conversation):
    """The pure episode-v2 rebuild of a conversation's full persona-visible
    history (the fold the durable row must equal)."""

    history = store.get_full_persona_visible_history(conversation)
    assert isinstance(history, Ok), history
    rebuilt = rebuild_episode(
        conversation_id=conversation,
        slices=history.value.slices,
        relationship_summary=SamePersonaExistingRelationshipSummary(
            persona_id=PERSONA_A, user_id=REL_USER, memories=()
        ),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok), rebuilt
    return rebuilt.value


def snapshot_app_db(db: sqlite3.Connection, path) -> None:
    """A consistent file copy of the in-memory app.db (sqlite backup API),
    for the cross-process rebuild probes to open."""

    dest = connection.connect(path)
    try:
        db.backup(dest)
    finally:
        dest.close()


def fresh_interpreter_rebuild_digest(script: str, db_path, conversation) -> str:
    """Run the rebuild script in a fresh interpreter; return its printed
    ``version digest`` line."""

    import os
    import subprocess
    import sys
    from pathlib import Path

    src = str(Path(__file__).resolve().parents[2] / "src")
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        src + os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else src
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(db_path), str(conversation)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return completed.stdout.strip()
