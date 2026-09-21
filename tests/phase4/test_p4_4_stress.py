"""P4-4 压力与故障注入（TASK-OPI-4d516e4f-9575-4cbf-8d08-6bf19a95bd25.26 (B)）。

VAL-OPI-5ba74efc-….80 的收口面：E2E 场景（test_p4_4_full_chain）证明链路对，
本文件证明它在压力与故障下**仍然对**。五组，逐条对应任务书 (B)：

1. **多轮累积** — 两会话交替 44 轮真链路：memory 行不重复（确定性 id ＋
   规范化 dedupe）、job 数 == 轮数 × 支持类型数、episode 每会话恒 1 行且 version
   随内容前进、正常路径无残留 FAILED_RETRYABLE；
2. **失败注入矩阵** — candidate provider 失败 / 候选无输出 / persona provider
   失败（含 no-output）/ 分类器 Err / 依赖 store Err / 确定性装配错配，各自的
   turn 结局与 job 结局（REJECTED vs FAILED_RETRYABLE vs COMMITTED）；
3. **重试两路** — FAILED_RETRYABLE 由「下一轮」与「启动恢复」两条路各自走到
   COMMITTED，attempt_count 递增、行不重复；
4. **crash-gap 与启动幂等** — 删 job 行后 ensure 补两类型并跑到 COMMITTED、
   stale RUNNING 重开、在册 PENDING 被 drain、重复启动行字节不变；
5. **并发** — 不同会话 guard 不互斥（含真链路：持 A 的 guard 时 B 的整轮照跑，
   且 CP4 在持有的外来 guard 下照常落地）、同会话 keyed mutex 串行（worker
   线程 + 事件序）。

**口径**：只断言完成态、计数与不重复（job 行数、memory 行数、episode 行数、
attempt_count、状态字），**不使用任何墙钟阈值**；并发用 threading 的
Event/Lock 同步，无 sleep、无 timeout 判据。**耗时**这类运行读数只作环境观测、
不进断言——轮数/行数/job 计数恰是断言对象，不得与耗时并列。

故障注入一律落在**真实链路的既有缝**上（P4-4 conftest 的三个探针）：
``ProbeExecutor``（包真执行器、可在 project() 返回注入 Err）、
``RefusingCandidates`` / ``PerConversationCandidates``（candidate provider）、
``FlakyClassifier``（分类器读）。没有任何场景替换掉真控制器、真 store。

红线自查：本文件经 Write 通道落盘；SQL 走 conftest 只读 helper（参数绑定）；
未触碰 migrations / behavioral_baselines / docs；不越 Phase 5+ 面。
"""

from __future__ import annotations

import threading

import pytest

from elc.persona import ScriptedPersonaProvider, no_output, provider_failure
from elc.platform.sync import CoordinatorBusyError
from elc.platform.types import ConversationId, DomainErrorCode, Ok, UserId
from elc.relationship import SamePersonaExistingRelationshipSummary
from elc.relationship.episode import EPISODE_WINDOW_MAX_TURNS
from elc.runtime.controller import ConversationCoordinator
from elc.runtime.projections import (
    PROJECTION_TYPE_EPISODE,
    PROJECTION_TYPE_RELATIONSHIP,
    SUPPORTED_PROJECTION_TYPES,
    CP4ProjectionRuntime,
    projection_id_for,
    turn_slice_hash,
)
from elc.runtime.types import ProjectionJobRecord, ProjectionJobState
from tests.conftest import AssemblyGenerationStore
from tests.phase3.conftest import make_lease, make_teaching_coordinator

from .conftest import (
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    FlakyClassifier,
    PerConversationCandidates,
    RecordingProvider,
    RefusingCandidates,
    commit_chat_turn,
    episode_row,
    memory_candidate,
    memory_rows,
    open_conversation_for,
    projection_job_row,
    projection_job_rows,
    relationship_projection_with,
    runtime_with_probes,
    turn_slice,
)

CONV_A = "conv-stress-a"
CONV_B = "conv-stress-b"
STRESS_MEMORY = "STRESS-MEMO the user keeps a plain notebook."
ROUNDS = 22  # per conversation; 44 alternating turns in total
OTHER_USER = UserId("user-2")


def _coordinator(
    *,
    store,
    generation_store: AssemblyGenerationStore,
    lease,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    provider,
    projections: CP4ProjectionRuntime | None = None,
    persona_views=None,
) -> ConversationCoordinator:
    """The shared P3-1A helper with an explicit lease (the E2E file's
    ``_coordinator``, duplicated here because the phase-3 suites' own files
    each carry this thin assembly call; nothing in it is a second assembly)."""

    return make_teaching_coordinator(
        store,
        generation_store,
        lease,
        provider,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        projections=projections,
        persona_views=persona_views,
    )


def _plain_runtime(projection_store, store, relationship, episode):
    """The real CP4 runtime (no probe) over the two real executors."""

    return CP4ProjectionRuntime(
        store=projection_store,
        executors=(relationship, episode),
        turns=store,
    )


def _runs_of(runs, projection_type: str = PROJECTION_TYPE_RELATIONSHIP) -> list:
    """The run results of one projection type (the queue orders by
    ``created_at, projection_id``, which fixes no order between types)."""

    return [item for item in runs if item.projection_type == projection_type]


def _statuses(db) -> set[str]:
    return {str(row[5]) for row in projection_job_rows(db)}


class _OtherScopeController:
    """The real Relationship controller with one face answering for another
    user (the assembly-defect injection of the deterministic-refusal case)."""

    def __init__(self, inner, other_user: UserId) -> None:
        self._inner = inner
        self._other_user = other_user

    def get_existing_summary(self, persona_id, user_id):
        del user_id
        summary = self._inner.get_existing_summary(persona_id, self._other_user)
        if not isinstance(summary, Ok):
            return summary
        return Ok(
            SamePersonaExistingRelationshipSummary(
                persona_id=summary.value.persona_id,
                user_id=self._other_user,
                memories=summary.value.memories,
            )
        )

    def __getattr__(self, name):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# 1. multi-round accumulation
# ---------------------------------------------------------------------------


def test_44_alternating_turns_accumulate_without_duplicates(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    """44 real turns over two conversations: counts, dedupe, version advance."""

    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    conv_a = open_conversation_for(store, CONV_A, PERSONA_A)
    conv_b = open_conversation_for(store, CONV_B, PERSONA_B)
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        projections=_plain_runtime(
            projection_store, store, relationship_projection, episode_projection
        ),
        persona_views=persona_views,
    )

    turns: list[tuple[object, object]] = []
    early_versions: dict[str, str] = {}
    for round_no in range(1, ROUNDS + 1):
        for conversation, marker in ((conv_a, "A"), (conv_b, "B")):
            turn = commit_chat_turn(
                coordinator,
                f"cm-{marker}-{round_no}",
                f"turn {round_no} on side {marker}: I keep a note.",
                round_no,
                conversation=conversation,
            )
            assert turn.outcome == "REPLIED_FULL"
            assert turn.turn_status.value == "COMPLETED"
            turns.append((conversation, turn))
        if round_no == 1:
            early_versions = {
                CONV_A: str(episode_row(db, conv_a)[2]),
                CONV_B: str(episode_row(db, conv_b)[2]),
            }
        if round_no % 10 == 0:
            # The happy path leaves no residue at any point: every job the
            # 44 turns produced is finished work.
            assert _statuses(db) == {"COMMITTED"}

    assert len(turns) == 2 * ROUNDS >= 40

    # Jobs: one per (type, turn) — exactly turns × supported types, all
    # COMMITTED, all first-attempt, all under their deterministic ids.
    rows = projection_job_rows(db)
    assert len(rows) == len(turns) * len(SUPPORTED_PROJECTION_TYPES)
    assert _statuses(db) == {"COMMITTED"}
    assert {int(row[6]) for row in rows} == {1}
    assert len({str(row[0]) for row in rows}) == len(rows)
    expected_ids = {
        str(projection_id_for(type_word, turn.turn_id))
        for _, turn in turns
        for type_word in SUPPORTED_PROJECTION_TYPES
    }
    assert {str(row[0]) for row in rows} == expected_ids

    # Memories: one row per (persona, user) pair — 44 assertions of the same
    # content dedupe onto one row each (deterministic id + normalized match),
    # so a duplicate is impossible rather than unlikely.
    memories = memory_rows(db)
    assert len(memories) == 2
    assert {str(row[1]) for row in memories} == {str(PERSONA_A), str(PERSONA_B)}
    assert {str(row[2]) for row in memories} == {str(REL_USER)}
    assert {str(row[5]) for row in memories} == {STRESS_MEMORY}

    # Episodes: one row per conversation (migration 0010's UNIQUE), its
    # version moved by content, its window the bounded 20-turn slice.
    assert len(db.execute("SELECT episode_id FROM episode").fetchall()) == 2
    episode_a = episode_row(db, conv_a)
    episode_b = episode_row(db, conv_b)
    assert str(episode_a[1]) == str(conv_a)
    assert str(episode_b[1]) == str(conv_b)
    assert str(episode_a[2]) != early_versions[CONV_A]
    assert str(episode_b[2]) != early_versions[CONV_B]
    for episode in (episode_a, episode_b):
        assert str(episode[2]).startswith("epv-")
        assert int(episode[4]) == ROUNDS
        assert int(episode[3]) == ROUNDS - EPISODE_WINDOW_MAX_TURNS + 1


# ---------------------------------------------------------------------------
# 2. the failure-injection matrix
# ---------------------------------------------------------------------------


def test_a_provider_failure_and_a_projection_failure_never_fail_the_turn(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
) -> None:
    """Both legs down at once: the turn still replies, and the retry lands both."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    refusing = RefusingCandidates(content="healed after the retry")
    relationship = relationship_projection_with(
        store, relationship_controller, refusing
    )
    runtime, (rel_probe, ep_probe) = runtime_with_probes(
        projection_store, store, relationship, episode_projection
    )
    ep_probe.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE, "episode store offline (injected)"
    )
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        projections=runtime,
        persona_views=persona_views,
    )

    first = commit_chat_turn(
        coordinator, "cm-fail-1", "I live in Berlin.", 1, conversation=conversation
    )
    assert first.outcome == "REPLIED_FULL"
    assert first.turn_status.value == "COMPLETED"
    # The transcript is intact and readable while both projections failed.
    slice_ = turn_slice(store, first.turn_id)
    assert slice_.assistant_turn is not None
    assert slice_.outcome is not None and slice_.outcome.value == "REPLIED_FULL"
    assert refusing.calls >= 1
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, first.turn_id)
    ep_job = projection_id_for(PROJECTION_TYPE_EPISODE, first.turn_id)
    assert projection_job_row(db, rel_job)[5] == "FAILED_RETRYABLE"
    assert projection_job_row(db, ep_job)[5] == "FAILED_RETRYABLE"
    assert memory_rows(db) == []
    assert db.execute("SELECT episode_id FROM episode").fetchall() == []

    # Both legs come back: the next turn retries both and lands them.
    refusing.heal()
    ep_probe.failure = None
    second = commit_chat_turn(
        coordinator, "cm-fail-2", "I read every evening.", 2,
        conversation=conversation,
    )
    assert second.outcome == "REPLIED_FULL"
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    assert projection_job_row(db, rel_job)[6] == 2
    assert projection_job_row(db, ep_job)[5] == "COMMITTED"
    assert projection_job_row(db, ep_job)[6] == 2
    assert [str(row[5]) for row in memory_rows(db)] == [refusing.content]
    assert len(db.execute("SELECT episode_id FROM episode").fetchall()) == 1


def test_an_empty_candidate_answer_commits_and_is_not_a_failure(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
) -> None:
    """No output is an *answer*: nothing asserted ⇒ an honest empty commit.

    The distinction the matrix needs: a provider ``Err`` is a retryable
    failure, an empty assertion set is a legitimate outcome — the projection
    commits having done exactly that (``RelationshipCandidateProvider``'s
    documented contract)."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    empty = PerConversationCandidates({})  # answers Ok(()) for every turn
    relationship = relationship_projection_with(store, relationship_controller, empty)
    runtime, (_, ep_probe) = runtime_with_probes(
        projection_store, store, relationship, episode_projection
    )
    ep_probe.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE, "episode store offline (injected)"
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-empty", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    assert empty.calls >= 1
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    ep_job = projection_id_for(PROJECTION_TYPE_EPISODE, turn.turn_id)
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    assert projection_job_row(db, rel_job)[6] == 1
    assert memory_rows(db) == []  # nothing was asserted, nothing was written
    assert projection_job_row(db, ep_job)[5] == "FAILED_RETRYABLE"


@pytest.mark.parametrize(
    "scripted",
    [provider_failure("provider exploded (injected)"), no_output()],
    ids=["provider-failure", "provider-no-output"],
)
def test_a_persona_provider_failure_and_a_projection_failure_coexist(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
    scripted,
) -> None:
    """The persona provider dies while a projection is down: the turn is
    honest (FAILED_USER_VISIBLE, no assistant side) and the conversation is
    not wedged — the projection line ran, saw no canonical turn, and queued
    nothing (RA §19: a projection runs *after* the canonical turn)."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    dying = ScriptedPersonaProvider(script=(scripted,))
    runtime, (rel_probe, _) = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    rel_probe.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE, "relationship store offline"
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=dying,
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-dying", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "FAILED_USER_VISIBLE"
    assert turn.turn_status.value == "FAILED_FINAL"
    assert turn.reply_text is None
    slice_ = turn_slice(store, turn.turn_id)
    assert slice_.assistant_turn is None
    assert slice_.outcome is not None
    assert slice_.outcome.value == "FAILED_USER_VISIBLE"
    assert db.execute("SELECT assistant_turn_id FROM assistant_turn").fetchall() == []
    assert projection_job_rows(db) == []  # no canonical turn, no CP4 work

    # A live provider over the same stores picks the conversation back up.
    recovered = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=ScriptedPersonaProvider(),
        projections=_plain_runtime(
            projection_store, store, relationship_projection, episode_projection
        ),
        persona_views=persona_views,
    )
    following = commit_chat_turn(
        recovered, "cm-dying-2", "Anyway, hello.", 2, conversation=conversation
    )
    assert following.outcome == "REPLIED_FULL"
    assert _statuses(db) == {"COMMITTED"}
    assert len(projection_job_rows(db)) == len(SUPPORTED_PROJECTION_TYPES)


def test_a_classifier_read_failure_is_retryable_never_an_empty_success(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    """A classifier ``Err`` must not be washed into a COMMITTED non-event.

    The Recorder fails *closed* (P4-1: an unclassifiable turn produces no
    proposal at all — zero writes), and that failure is a **dependency**
    failure, so the job has to stay retryable: committing it would spend the
    deterministic id on a turn nobody ever projected, and a later, working
    assembly would replay that row as finished work forever.
    """

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    classifier = FlakyClassifier(store)
    classifier.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE,
        "command-turn classifier offline (injected)",
    )
    relationship = relationship_projection_with(
        store, relationship_controller, scripted_candidates, classifier=classifier
    )
    runtime, (rel_probe, _) = runtime_with_probes(
        projection_store, store, relationship, episode_projection
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-cls", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    assert classifier.calls >= 1
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    # Fail-closed really wrote nothing …
    assert memory_rows(db) == []
    assert rel_probe.calls == 1  # the real executor ran; the refusal is its own
    # … and the job is retryable, never a committed empty success.
    assert projection_job_row(db, rel_job)[5] == "FAILED_RETRYABLE"
    assert projection_job_row(db, rel_job)[6] == 1

    # The classifier comes back: the retry lands the memory it could not read.
    classifier.heal()
    commit_chat_turn(
        coordinator, "cm-cls-2", "I read every evening.", 2,
        conversation=conversation,
    )
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    assert projection_job_row(db, rel_job)[6] == 2
    assert [str(row[5]) for row in memory_rows(db)] == [STRESS_MEMORY]


def test_a_classifier_failure_with_nothing_asserted_is_the_declared_boundary(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
) -> None:
    """The honest *boundary* of the classifier rule, pinned rather than left
    implicit.

    The Recorder's fail-closed arm only leaves a trace when there was a
    candidate to refuse: with an empty assertion set the outcome is
    ``(proposals=(), refusals=())`` — indistinguishable from an honest empty
    answer — so the executor has nothing to read and the job commits having
    projected nothing. That is defensible *because nothing can be lost* (a
    projection of "nothing was asserted" is exactly what it produced), and
    the classifier read really did happen and really did fail (asserted
    below). Making such a read failure visible in the durable row would need
    a new field on the P4-1 ``RelationshipRecorderOutcome``, which is out of
    this slice's minimal-fix scope and is reported as a boundary instead.
    """

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    empty = PerConversationCandidates({})
    classifier = FlakyClassifier(store)
    classifier.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE,
        "command-turn classifier offline (injected)",
    )
    relationship = relationship_projection_with(
        store, relationship_controller, empty, classifier=classifier
    )
    runtime, _ = runtime_with_probes(
        projection_store, store, relationship, episode_projection
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-cls-empty", "I live in Berlin.", 1,
        conversation=conversation,
    )
    assert turn.outcome == "REPLIED_FULL"
    assert classifier.calls >= 1  # the read was attempted, and it failed
    assert empty.calls >= 1  # … and it had nothing to assert
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    assert memory_rows(db) == []  # nothing was asserted, nothing was written


def test_a_store_refusal_of_one_leg_keeps_that_leg_retryable(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    """A dependency-grade store refusal is retryable — never a rejection."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    runtime, (_, ep_probe) = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    ep_probe.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE, "episode store offline (injected)"
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-store", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    ep_job = projection_id_for(PROJECTION_TYPE_EPISODE, turn.turn_id)
    assert projection_job_row(db, ep_job)[5] == "FAILED_RETRYABLE"
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"

    ep_probe.failure = None
    commit_chat_turn(
        coordinator, "cm-store-2", "I read every evening.", 2,
        conversation=conversation,
    )
    assert projection_job_row(db, ep_job)[5] == "COMMITTED"
    assert projection_job_row(db, ep_job)[6] == 2
    assert len(db.execute("SELECT episode_id FROM episode").fetchall()) == 1


def test_a_stale_slice_hash_is_rejected_and_never_retried(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    """Deterministic refusal #1: the durable slice moved under the job."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    plain = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        persona_views=persona_views,
    )
    turn = commit_chat_turn(
        plain, "cm-det-hash", "I live in Berlin.", 1, conversation=conversation
    )
    assert projection_job_rows(db) == []  # no project port: no job rows

    runtime, _ = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    job_id = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    stale = projection_store.enqueue_projection(
        ProjectionJobRecord(
            projection_job_id=job_id,
            conversation_id=str(conversation),
            source_turn_id=turn.turn_id,
            projection_type=PROJECTION_TYPE_RELATIONSHIP,
            source_version="a-hash-the-slice-no-longer-has",
            state=ProjectionJobState.PENDING,
        )
    )
    assert isinstance(stale, Ok), stale

    runs = runtime.run_pending(conversation)
    assert isinstance(runs, Ok), runs
    assert [item.status.value for item in runs.value] == ["REJECTED"]
    assert runs.value[0].detail == "source_turn_slice_hash changed"
    row = projection_job_row(db, job_id)
    assert row[5] == "REJECTED" and row[6] == 0 and row[4] is None
    # Finished work is not retried: a second pass has nothing to run, and the
    # rejected row is byte-for-byte where the first pass left it.
    again = runtime.run_pending(conversation)
    assert isinstance(again, Ok) and again.value == ()
    assert projection_job_row(db, job_id) == row


def test_an_unsupported_projection_type_is_rejected_and_never_retried(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
) -> None:
    """Deterministic refusal #2: a type no executor is registered for."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    plain = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        persona_views=persona_views,
    )
    turn = commit_chat_turn(
        plain, "cm-det-type", "I live in Berlin.", 1, conversation=conversation
    )
    runtime, _ = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    job_id = projection_id_for("PLANNING_LEDGER", turn.turn_id)
    assert isinstance(
        projection_store.enqueue_projection(
            ProjectionJobRecord(
                projection_job_id=job_id,
                conversation_id=str(conversation),
                source_turn_id=turn.turn_id,
                projection_type="PLANNING_LEDGER",
                source_version=turn_slice_hash(turn_slice(store, turn.turn_id)),
                state=ProjectionJobState.PENDING,
            )
        ),
        Ok,
    )

    runs = runtime.run_pending(conversation)
    assert isinstance(runs, Ok), runs
    assert [item.status.value for item in runs.value] == ["REJECTED"]
    assert "unsupported projection_type" in runs.value[0].detail
    row = projection_job_row(db, job_id)
    assert row[5] == "REJECTED" and row[6] == 0
    again = runtime.run_pending(conversation)
    assert isinstance(again, Ok) and again.value == ()
    assert projection_job_row(db, job_id) == row


def test_an_assembly_scope_mismatch_is_rejected_and_never_retried(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    """Deterministic refusal #3: the summary describes another user.

    The assembly check (DEC-…115 待裁 B 附条件) refuses *before* the recorder
    runs and before any write, so the job is rejected with zero side effects
    — and never retried, because the same mis-assembly would refuse forever.
    """

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    misassembled = relationship_projection_with(
        store,
        _OtherScopeController(relationship_controller, OTHER_USER),
        scripted_candidates,
    )
    runtime, _ = runtime_with_probes(
        projection_store, store, misassembled, episode_projection
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-det-scope", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    row = projection_job_row(db, rel_job)
    assert row[5] == "REJECTED" and row[6] == 1
    assert memory_rows(db) == []  # zero writes: the check runs first
    again = runtime.run_pending(conversation)
    assert isinstance(again, Ok) and again.value == ()
    assert projection_job_row(db, rel_job) == row


# ---------------------------------------------------------------------------
# 3. the two retry paths
# ---------------------------------------------------------------------------


def test_a_retryable_job_lands_on_the_next_turn(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
) -> None:
    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    refusing = RefusingCandidates(content="landed on the retry")
    relationship = relationship_projection_with(
        store, relationship_controller, refusing
    )
    runtime = _plain_runtime(
        projection_store, store, relationship, episode_projection
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )

    first = commit_chat_turn(
        coordinator, "cm-retry-turn-1", "I live in Berlin.", 1,
        conversation=conversation,
    )
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, first.turn_id)
    assert projection_job_row(db, rel_job)[5] == "FAILED_RETRYABLE"

    refusing.heal()
    commit_chat_turn(
        coordinator, "cm-retry-turn-2", "I read every evening.", 2,
        conversation=conversation,
    )
    row = projection_job_row(db, rel_job)
    assert row[5] == "COMMITTED" and row[6] == 2
    # The retry wrote the memory once; the second turn's identical assertion
    # dedupes onto the same row.
    assert [str(item[5]) for item in memory_rows(db)] == [refusing.content]
    assert len(projection_job_rows(db)) == 2 * len(SUPPORTED_PROJECTION_TYPES)


def test_a_retryable_job_lands_at_startup(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
) -> None:
    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    refusing = RefusingCandidates(content="landed at startup")
    relationship = relationship_projection_with(
        store, relationship_controller, refusing
    )
    runtime = _plain_runtime(
        projection_store, store, relationship, episode_projection
    )
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )
    turn = commit_chat_turn(
        coordinator, "cm-retry-start", "I live in Berlin.", 1,
        conversation=conversation,
    )
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    assert projection_job_row(db, rel_job)[5] == "FAILED_RETRYABLE"

    refusing.heal()
    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_recovery_unavailable is False
    assert [item.status.value for item in _runs_of(
        outcome.value.projection_runs
    )] == ["COMMITTED"]
    assert _runs_of(outcome.value.projection_runs)[0].projection_job_id == rel_job
    row = projection_job_row(db, rel_job)
    assert row[5] == "COMMITTED" and row[6] == 2
    assert [str(item[5]) for item in memory_rows(db)] == [refusing.content]


# ---------------------------------------------------------------------------
# 4. the crash gap and the idempotent startup
# ---------------------------------------------------------------------------


def test_a_deleted_job_pair_is_rebuilt_and_run_by_startup(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=_plain_runtime(
            projection_store, store, relationship_projection, episode_projection
        ),
        persona_views=persona_views,
    )
    turn = commit_chat_turn(
        coordinator, "cm-gap", "I live in Berlin.", 1, conversation=conversation
    )
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    ep_job = projection_id_for(PROJECTION_TYPE_EPISODE, turn.turn_id)
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    episode_before = episode_row(db, conversation)
    memory_before = memory_rows(db)

    # The crash simulation: both rows vanish, nothing else does.
    db.execute(
        "DELETE FROM projection_job WHERE source_turn_id = ?", (str(turn.turn_id),)
    )
    db.commit()  # close the implicit tx before the store's own unit
    assert projection_job_rows(db) == []

    outcome = coordinator.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_recovery_unavailable is False
    assert outcome.value.projection_jobs == (rel_job, ep_job)
    assert {item.status.value for item in outcome.value.projection_runs} == {
        "COMMITTED"
    }
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    assert projection_job_row(db, ep_job)[5] == "COMMITTED"
    # The repair replays, it does not duplicate: the same memory row (the
    # deterministic id + dedupe) and the *same* episode generation — a
    # rebuild of unchanged truth is a zero-write replay.
    assert memory_rows(db) == memory_before
    assert episode_row(db, conversation) == episode_before


def test_a_stale_running_job_is_reopened_and_committed_by_startup(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    plain = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        persona_views=persona_views,
    )
    turn = commit_chat_turn(
        plain, "cm-stale", "I live in Berlin.", 1, conversation=conversation
    )
    runtime, _ = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    ensured = runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(ensured, Ok), ensured
    rel_job, ep_job = ensured.value
    claimed = projection_store.claim_projection(rel_job, base_version="rv-crashed")
    assert isinstance(claimed, Ok), claimed
    assert claimed.value.status is ProjectionJobState.RUNNING

    recovered = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )
    outcome = recovered.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.reopened_projections == (rel_job,)
    # The EPISODE row is not a *gap* — ``ensure_projection_jobs`` wrote it
    # above and it is still PENDING — so nothing is repaired; it is drained
    # by the registry half of the same pass (below).
    assert outcome.value.projection_jobs == ()
    statuses = {
        item.projection_job_id: item.status.value
        for item in outcome.value.projection_runs
    }
    assert statuses == {rel_job: "COMMITTED", ep_job: "COMMITTED"}
    row = projection_job_row(db, rel_job)
    assert row[5] == "COMMITTED" and row[6] == 2  # re-open is not an attempt
    # The stale claim's base was replaced by a freshly recomputed one.
    assert row[4] != "rv-crashed" and str(row[4]).startswith("rv-")


def test_a_registered_pending_pair_is_drained_by_startup(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    plain = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        persona_views=persona_views,
    )
    turn = commit_chat_turn(
        plain, "cm-drain", "I live in Berlin.", 1, conversation=conversation
    )
    runtime, _ = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    ensured = runtime.ensure_projection_jobs(turn.turn_id)
    assert isinstance(ensured, Ok), ensured
    assert _statuses(db) == {"PENDING"}  # enqueued, never run

    recovered = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=runtime,
        persona_views=persona_views,
    )
    outcome = recovered.run_startup_recovery()
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.projection_jobs == ()  # nothing was missing
    assert outcome.value.reopened_projections == ()
    assert {item.status.value for item in outcome.value.projection_runs} == {
        "COMMITTED"
    }
    assert _statuses(db) == {"COMMITTED"}
    assert {int(row[6]) for row in projection_job_rows(db)} == {1}


def test_repeated_startup_is_idempotent_row_for_row(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=make_lease(fence),
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=_plain_runtime(
            projection_store, store, relationship_projection, episode_projection
        ),
        persona_views=persona_views,
    )
    commit_chat_turn(
        coordinator, "cm-idem", "I live in Berlin.", 1, conversation=conversation
    )
    jobs_before = projection_job_rows(db)
    memories_before = memory_rows(db)
    episode_before = episode_row(db, conversation)

    first = coordinator.run_startup_recovery()
    assert isinstance(first, Ok), first
    assert first.value.projection_jobs == ()
    assert first.value.reopened_projections == ()
    assert first.value.projection_runs == ()
    # Row for row, byte for byte: a startup pass over finished work is a read.
    assert projection_job_rows(db) == jobs_before
    assert memory_rows(db) == memories_before
    assert episode_row(db, conversation) == episode_before

    second = coordinator.run_startup_recovery()
    assert isinstance(second, Ok), second
    assert second.value.projection_jobs == ()
    assert second.value.reopened_projections == ()
    assert second.value.projection_runs == ()
    assert projection_job_rows(db) == jobs_before
    assert memory_rows(db) == memories_before
    assert episode_row(db, conversation) == episode_before


# ---------------------------------------------------------------------------
# 5. concurrency: the keyed guard, with deterministic events
# ---------------------------------------------------------------------------


def test_a_held_guard_does_not_block_another_conversation(
    db,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_projection,
    episode_projection,
    projection_store,
    persona_views,
    scripted_candidates,
) -> None:
    """A's guard is held for the whole of B's turn — and B's turn runs, CP4
    included (RA §19/§24.1: CP4 takes no guard)."""

    conv_a = open_conversation_for(store, CONV_A, PERSONA_A)
    conv_b = open_conversation_for(store, CONV_B, PERSONA_B)
    scripted_candidates.candidates = (memory_candidate(STRESS_MEMORY),)
    lease = make_lease(fence)
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=lease,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=RecordingProvider(),
        projections=_plain_runtime(
            projection_store, store, relationship_projection, episode_projection
        ),
        persona_views=persona_views,
    )

    with lease.hold(conv_a):
        turn = commit_chat_turn(
            coordinator, "cm-conc-1", "I live in Berlin.", 1, conversation=conv_b
        )
        assert turn.outcome == "REPLIED_FULL"
        assert lease.is_held(conv_a) is True  # still ours throughout
    assert lease.is_held(conv_a) is False
    assert _statuses(db) == {"COMMITTED"}
    assert len(projection_job_rows(db)) == len(SUPPORTED_PROJECTION_TYPES)


def test_the_keyed_mutex_admits_another_key_and_refuses_the_same_one(
    fence,
) -> None:
    """The keyed-mutex rule, without threads: one key is one owner, and a
    different key is no exclusion at all."""

    lease = make_lease(fence)
    conv_a = ConversationId("conv-stress-mutex-a")
    conv_b = ConversationId("conv-stress-mutex-b")
    with lease.hold(conv_a):
        assert lease.is_held(conv_a) is True
        with lease.hold(conv_b):  # a different conversation: admitted
            assert lease.is_held(conv_b) is True
        assert lease.is_held(conv_b) is False
        with pytest.raises(CoordinatorBusyError):
            with lease.hold(conv_a, blocking=False):
                pass
        assert lease.is_held(conv_a) is True  # the refusal changed nothing
    assert lease.is_held(conv_a) is False


def test_a_worker_thread_waits_for_the_release_in_order(fence) -> None:
    """Same-key serialization, proven by *event order* (no sleeps, no time
    constants): the worker cannot record "acquired" before the main thread
    records "released", because it cannot own the key before the release."""

    lease = make_lease(fence)
    conversation = ConversationId("conv-stress-mutex-c")
    events: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    attempting = threading.Event()
    done = threading.Event()

    def record(tag: str) -> None:
        with lock:
            events.append(tag)

    def worker() -> None:
        try:
            record("attempting")
            attempting.set()
            with lease.hold(conversation):
                record("acquired")
        except BaseException as exc:  # noqa: BLE001 — reported, not hidden
            errors.append(exc)
        finally:
            done.set()

    with lease.hold(conversation):
        thread = threading.Thread(target=worker, name="p4-4-guard-probe")
        thread.start()
        attempting.wait()  # the worker is about to block on the key
        assert events == ["attempting"]  # … and has not acquired it
        record("released")
    done.wait()
    thread.join()
    assert errors == []
    assert events == ["attempting", "released", "acquired"]


def test_a_worker_thread_takes_another_conversation_while_the_first_is_held(
    fence,
) -> None:
    """The other half of the same rule, also by event order: the second key is
    acquired *while* the first is still held — observed, not inferred."""

    lease = make_lease(fence)
    first = ConversationId("conv-stress-mutex-d")
    second = ConversationId("conv-stress-mutex-e")
    events: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    acquired = threading.Event()
    done = threading.Event()

    def record(tag: str) -> None:
        with lock:
            events.append(tag)

    def worker() -> None:
        try:
            record("attempting-b")
            with lease.hold(second):
                record("acquired-b")
                acquired.set()
        except BaseException as exc:  # noqa: BLE001 — reported, not hidden
            errors.append(exc)
        finally:
            done.set()

    with lease.hold(first):
        thread = threading.Thread(target=worker, name="p4-4-guard-probe-b")
        thread.start()
        acquired.wait()
        # … and this observation happens while the first key is *still* held:
        assert lease.is_held(first) is True
        assert events == ["attempting-b", "acquired-b"]
    done.wait()
    thread.join()
    assert errors == []
    assert lease.is_held(second) is False
