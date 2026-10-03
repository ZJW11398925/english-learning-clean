"""cs-3 无限聊天刀验收钉（对 VAL 六组的 ⑤⑥ 组）.

命题（用户原话钉死）：**单角色无限聊天**——与同一角色连续对话 N≫20 轮后，
早期关键事实仍在 prompt 内（记忆外显），而非窗口数字；用户透明（零切卷）。

场景：同一会话 60 轮真链路（真 coordinator + 真 CP4 + 真的
``PatternCandidateProvider``），第 3 轮植入叙事句（刻意不匹配 17 模式，
进 prompt 的唯一通道是 episode-v2 的封存层），第 5 轮植入模式句（走
[relationship] 通道）。对第 60 轮捕获的 prompt 断言七件（研究简报 §5）；
变异三组证明钉承重（配额归零 / 版本不 bump / prompt 窗口擅改）。

红线自查：经 Write 通道落盘；SQL 只读 helper（episode_row/memory_rows 为
phase4 conftest 的参数绑定只读）；零迁移、零 provider 成本（脚本假
provider）；无 sleep、无墙钟阈值断言（⑦ 是量级比，带下限防抖）。
"""

from __future__ import annotations

import hashlib

from elc.persona.commands import UNTRUSTED_SECTION_END
from elc.relationship import episode as episode_module
from elc.relationship.episode import (
    EPISODE_ARCHIVE_LINES_PER_SEGMENT,
    EPISODE_ARCHIVE_SEGMENT_TURNS,
    EPISODE_SUMMARY_MAX_UTTERANCES,
    EPISODE_SUMMARY_UTTERANCE_MAX_CHARS,
    EPISODE_WINDOW_MAX_TURNS,
    episode_version_for,
)
from elc.runtime import controller as controller_module
from tests.phase4.conftest import episode_row, memory_rows

from .conftest import (
    PUPPY_LINE,
    cs3_line,
    fresh_interpreter_rebuild_digest,
    rebuilt_episode_of,
    run_conversation,
    snapshot_app_db,
)

ROUNDS = 60  # = 3 × prompt window；满足 N≫20

#: 封存层与现势层的分节符（episode-v2 的唯一非逐字字节）。
_LAYER_SEPARATOR = " || "

#: ⑦ 的防抖下限：第 1 轮可能落在计时精度底部，阈值以
#: ``5 × max(第 1 轮, 本下限)`` 计（量级断言，任务书允许宽松）。
_LATENCY_FLOOR_SECONDS = 0.005

#: ④ 的绝对上界：60 轮的 prompt 实测 ~4 KB（Persona 卡 + 20 轮 [history] +
#: 配额封顶的 [episode]）；护栏取实测的两倍带余量，真正承重的是上面的配额
#: 断言。实测读数随本文件其餘断言一起维护。
_PROMPT_ABSOLUTE_BOUND = 8_000

#: 跨进程重建脚本：开文件库 → 全历史读 → 纯函数折叠 → 打印
#: ``version + summary 摘要``（fold 无 clock 无随机，种子不得到达字节）。
_REBUILD_SCRIPT = (
    "import sys, hashlib;"
    "from elc.platform.db import connection, epoch;"
    "from elc.conversation.store import SqliteConversationStore;"
    "from elc.conversation.types import ConversationStatus;"
    "from elc.platform.types import ConversationId, PersonaId, UserId;"
    "from elc.relationship.episode import rebuild_episode;"
    "from elc.relationship.types import SamePersonaExistingRelationshipSummary;"
    "conn = connection.connect(sys.argv[1]);"
    "fence = epoch.open_runtime_epoch(conn);"
    "store = SqliteConversationStore(conn, fence);"
    "conv = ConversationId(sys.argv[2]);"
    "hist = store.get_full_persona_visible_history(conv);"
    "rebuilt = rebuild_episode(conversation_id=conv, slices=hist.value.slices,"
    " relationship_summary=SamePersonaExistingRelationshipSummary("
    "persona_id=PersonaId('persona-a'), user_id=UserId('user-1'), memories=()),"
    " conversation_status=ConversationStatus.ACTIVE);"
    "record = rebuilt.value;"
    "print(record.version,"
    " hashlib.sha256(record.summary.encode('utf-8')).hexdigest())"
)


def _section(prompt: str, name: str) -> str:
    """One framed untrusted section of a compiled prompt (the cs-1 reader)."""

    start = prompt.index(f"[{name}]")
    end = prompt.index(UNTRUSTED_SECTION_END, start)
    return prompt[start:end]


def _summary_value(episode_section: str) -> str:
    line = next(
        line
        for line in episode_section.splitlines()
        if line.startswith("summary: ")
    )
    return line[len("summary: ") :]


# ---------------------------------------------------------------------------
# the acceptance: N≫20 turns, the early facts still in the prompt
# ---------------------------------------------------------------------------


def test_after_60_turns_the_early_facts_are_still_in_the_prompt(
    cs3_coordinator,
    provider,
    store,
    db,
    episode_store,
) -> None:
    """The unlimited-chat命题的七件断言，全对第 60 轮的 prompt 实测。"""

    conversation, durations = run_conversation(
        cs3_coordinator, store, ROUNDS
    )
    assert len(provider.prompts) == ROUNDS
    prompt = provider.prompts[-1].prompt_text

    # -- ① 记忆外显（叙事）：第 3 轮的事实在 [episode] 封存层 -------------
    episode_section = _section(prompt, "episode")
    assert "prompt_version: episode-prompt-v2" in episode_section
    summary = _summary_value(episode_section)
    assert PUPPY_LINE in summary
    archive_part, current_part = summary.split(_LAYER_SEPARATOR)
    assert PUPPY_LINE in archive_part  # 封存层，不是现势层
    # 现势层仍是最最近四句逐字（episode-v1 的行为原样保住）。捕获的第 60 轮
    # prompt 编译于第 60 轮 canonical 之前（投影在轮后跑，CP4），所以它折叠
    # 的是 1..59——现势层是 56..59，封存层算到 39。
    assert current_part == " / ".join(
        cs3_line(index)
        for index in (ROUNDS - 4, ROUNDS - 3, ROUNDS - 2, ROUNDS - 1)
    )

    # -- ② 记忆外显（模式事实）：Mary 在 [relationship]，且真的落库 --------
    relationship_section = _section(prompt, "relationship")
    assert "USER_STATED_FACT: The user's name is Mary." in relationship_section
    memories = memory_rows(db)
    assert [str(row[5]) for row in memories] == ["The user's name is Mary."]
    # 叙事句没有被 17 模式误捕（它是封存层的独占事实）。
    assert all(PUPPY_LINE not in str(row[5]) for row in memories)

    # -- ③ 非窗口残余：第 3 轮原文不在 [history]（它走的是记忆通道） -------
    history_section = _section(prompt, "history")
    assert PUPPY_LINE not in history_section

    # -- ④ prompt 有界：绝对护栏 + 折叠配额把 [episode] summary 封顶 --------
    # （段配额生效：封存层 ≤ 2 行/段、现势层 ≤ 4 句、逐句 ≤ 120+1 字——
    #   summary 的增长被配额钉住，而不是全 transcript 逐字入 prompt。）
    full = store.get_full_persona_visible_history(conversation)
    assert len(prompt) < _PROMPT_ABSOLUTE_BOUND
    compiled_turns = ROUNDS - 1  # 捕获的 prompt 编译于第 60 轮 canonical 之前
    archive_slices = compiled_turns - EPISODE_WINDOW_MAX_TURNS
    segment_count = -(-archive_slices // EPISODE_ARCHIVE_SEGMENT_TURNS)
    quota_lines = (
        segment_count * EPISODE_ARCHIVE_LINES_PER_SEGMENT
        + EPISODE_SUMMARY_MAX_UTTERANCES
    )
    # 处置刀（评审 LOW-1）：每行最坏 = 120 截断 + 1 个省略号 + 前后
    # " / " 连接符（首行只挂一侧），显式按最坏 123+1 计——原式 988 比
    # 真最坏 990 少 2，全最长行场景会假红。
    assert len(summary) <= (
        quota_lines * (EPISODE_SUMMARY_UTTERANCE_MAX_CHARS + 1 + 3)
        + len(_LAYER_SEPARATOR)
    )
    assert len(full.value.slices) == ROUNDS

    # -- ⑤ 确定性与幂等（进程内半）：同一 transcript 重建字节同一，且 -------
    #      重建行与 durable 行版本相等（zero-write replay 仍成立）。
    durable = episode_row(db, conversation)
    rebuilt = rebuilt_episode_of(store, conversation)
    assert rebuilt.version == str(durable[2])
    assert rebuilt.source_turn_sequence_start == 1
    assert rebuilt.source_turn_sequence_end == ROUNDS
    episode_store.upsert_episode(rebuilt)
    assert episode_row(db, conversation) == durable  # 一字未动

    # -- ⑥ 用户透明：会话行数恒 1、status 恒 ACTIVE（无切卷事件） ----------
    rows = db.execute(
        "SELECT conversation_id, status FROM conversation"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == str(conversation)
    assert rows[0][1] == "ACTIVE"

    # -- ⑦ 投影不阻塞：第 60 轮与第 1 轮同量级（CP4 异步位回归读数） -------
    assert durations[-1] < 5 * max(durations[0], _LATENCY_FLOOR_SECONDS)


def test_two_fresh_interpreters_rebuild_the_fold_byte_identical(
    cs3_coordinator,
    store,
    db,
    tmp_path,
) -> None:
    """⑤ 的跨进程半：两个新解释器（不同 ``PYTHONHASHSEED``）对同一份真链路
    transcript 重建 episode，版本与 summary 摘要逐字节相等——折叠是纯函数，
    哈希随机化到不了它的字节。"""

    conversation, _ = run_conversation(cs3_coordinator, store, 25)
    in_process = rebuilt_episode_of(store, conversation)

    db_path = tmp_path / "cs3-replay.db"
    snapshot_app_db(db, db_path)
    digests = {
        fresh_interpreter_rebuild_digest(
            _REBUILD_SCRIPT, db_path, conversation, seed=seed
        )
        for seed in ("0", "12345")
    }
    assert len(digests) == 1  # 两个种子的输出逐字节相等
    version, summary_digest = next(iter(digests)).split()
    assert version == in_process.version
    assert summary_digest == hashlib.sha256(
        in_process.summary.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# the mutations: each pin is carried, not decorative
# ---------------------------------------------------------------------------


def test_mutation_with_the_archive_disabled_the_early_fact_leaves_the_prompt(
    cs3_coordinator,
    provider,
    store,
    monkeypatch,
) -> None:
    """变异一（配额归零 ⇒ ① RED）：现势层深度被改成覆盖一切时封存层为空，
    第 3 轮的叙事句从 prompt 里**彻底消失**——① 的「仍在 prompt」完全由
    折叠承载。"""

    monkeypatch.setattr(episode_module, "EPISODE_WINDOW_MAX_TURNS", 10**9)
    conversation, _ = run_conversation(cs3_coordinator, store, 25)
    prompt = provider.prompts[-1].prompt_text
    summary = _summary_value(_section(prompt, "episode"))
    assert PUPPY_LINE not in summary
    assert _LAYER_SEPARATOR not in summary  # 封存层确实禁用
    # the full RED of ①: the sentence is nowhere in the prompt at all
    assert PUPPY_LINE not in prompt


def test_mutation_a_template_change_without_a_bump_is_undetectable_by_content(
    cs3_coordinator,
    store,
) -> None:
    """变异二（版本不 bump ⇒ 确定性/幂等钉 RED）：同一真链路 transcript 的
    同一份折叠内容，换一个模板标签就得到另一个版本串——模板语义的差异
    **只**活在版本串里；若 digest 不含模板版本（「不 bump」的实质），新旧
    语义的行就是同一个串，zero-write replay 会把旧语义的行当新语义重放。

    机制事实（本变异钉的实现注记）：:func:`episode_version_for` 的
    ``projection_version`` 是**定义期默认参数**，import 之后 patch 模块
    常量到不了 digest——所以这里的标签对照走显式入参（p4-3 版本钉同形）。
    """

    conversation, _ = run_conversation(cs3_coordinator, store, 25)
    current = rebuilt_episode_of(store, conversation)
    fields = dict(
        conversation_id=current.conversation_id,
        source_turn_sequence_start=current.source_turn_sequence_start,
        source_turn_sequence_end=current.source_turn_sequence_end,
        summary=current.summary,
        open_threads=current.open_threads,
        recent_events=current.recent_events,
        status=current.status,
    )
    # 现役标签精确复现 durable 语义（标签在 digest 里承重）……
    assert episode_version_for(**fields, projection_version="episode-v2") == (
        current.version
    )
    # ……换标签 ⇒ 换串（不 bump 的两语义行本会共用一个串）。
    assert episode_version_for(**fields, projection_version="episode-v1") != (
        current.version
    )


def test_mutation_with_the_prompt_window_moved_the_history_pin_flips(
    cs3_coordinator,
    provider,
    store,
    monkeypatch,
) -> None:
    """变异三（``CONVERSATION_WINDOW_MAX_TURNS`` 擅改 ⇒ ③ RED）：窗口被改大
    后第 3 轮原文漏进 [history]——持等钉要防的漂移形态本尊。"""

    monkeypatch.setattr(controller_module, "CONVERSATION_WINDOW_MAX_TURNS", 30)
    conversation, _ = run_conversation(cs3_coordinator, store, 25)
    prompt = provider.prompts[-1].prompt_text
    history_section = _section(prompt, "history")
    assert PUPPY_LINE in history_section  # ③ 翻红：窗口漂移被钉住
    # 深度等式不再成立（test_p4_3_gates 的持等钉此刻必 RED）。
    assert 30 != EPISODE_WINDOW_MAX_TURNS
