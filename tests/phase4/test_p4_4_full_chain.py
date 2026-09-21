"""P4-4 全链端到端验收（TASK-OPI-4d516e4f-9575-4cbf-8d08-6bf19a95bd25.26 ①-④）。

VAL-OPI-5ba74efc-….80 的四条命题在这个文件里逐条落锤，每一场景都从 CP0 走
真链路：canonical conversation store（CP0 / CP3a）＋ learning（CP1）＋
teaching 端口 ＋ relationship 与 episode 两个真实 CP4 执行器 ＋ user_config
披露门 ＋ persona_views 装配 ＋ ScriptedPersonaProvider。没有手搭 store、没有
替代执行器——唯一例外是**故障注入**：一个把真实执行器包起来、可在调用点返回
指定 ``DomainError`` 的探针（``_ProbeExecutor``），它只在注入场景里失败，正常
路径逐字节就是真执行器本身。

- ① 单轮成功链：turn REPLIED_FULL → canonical transcript 三件齐（user turn /
  assistant turn / turn outcome 全部从 store 读回）→ guard 已释放（两个执行器
  **从自己体内**看到 ``lease.is_held(conv) is False`` 且
  ``conn.in_transaction is False``）→ 两个投影 job 各自 COMMITTED
  （base / attempt 如实）。另一场景：单 executor 注入失败，兄弟类型照常
  COMMITTED，失败者 FAILED_RETRYABLE → 下一轮重试 → COMMITTED，两类型互不
  阻塞、行不重复。
- ② 投影未完不阻下轮：RELATIONSHIP 持续失败停在 FAILED_RETRYABLE → 下一轮仍
  REPLIED_FULL，其 prompt 的 ``[history]`` 与该会话 canonical slice 的渲染
  **逐字一致**（连贯性来自 transcript，不是投影）。
- ③ 投影完成后 context 增量：同一会话投影前 prompt 无 relationship / episode
  内容项 → 投影后 prompt 含记忆与摘要，且与 durable 行逐字对账；同一 durable
  状态两次独立重建请求、两次编译逐字节相等。
- ④ 全链隔离：A / B 两会话两 persona 交替多轮，A 的 memory content /
  episode summary / persona_id 字符**双向**不出现在 B 的任何 prompt（含负
  控），关系行按 (persona,user)、Episode 行按 conversation 各自成域（读面对
  账）。

证据学口径：断言只读 durable 行与 provider 实际收到的 prompt 文本
（``RecordingProvider`` 记录 PromptCompiler 交出的字节，见 P4-3 先例），对账
一律「prompt 里的字符串 == durable 行的列」，不引入任何实现内部数字。

红线自查：本文件经 Write 通道落盘；SQL 全部走 conftest 的只读 helper（参数
绑定）；未触碰 migrations / behavioral_baselines / docs；不越 Phase 5+ 面；
无墙钟判据。
"""

from __future__ import annotations

from elc.conversation import SqliteConversationStore
from elc.persona import PromptCompiler
from elc.persona.types import (
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
)
from elc.platform.types import (
    ConversationId,
    DomainErrorCode,
    InteractionChannel,
    Ok,
    PersonaId,
)
from elc.relationship.episode import EPISODE_ABSENT_BASE_VERSION
from elc.runtime.controller import (
    CONVERSATION_WINDOW_MAX_TURNS,
    ConversationCoordinator,
)
from elc.runtime.persona_views import ControllerPersonaViews
from elc.runtime.projections import (
    PROJECTION_TYPE_EPISODE,
    PROJECTION_TYPE_RELATIONSHIP,
    SUPPORTED_PROJECTION_TYPES,
    CP4ProjectionRuntime,
    projection_id_for,
)
from elc.runtime.types import GenerationActionType
from tests.conftest import AssemblyGenerationStore
from tests.phase3.conftest import make_lease, make_teaching_coordinator

from .conftest import (
    PERSONA_A,
    PERSONA_B,
    REL_USER,
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

#: The two facts of this file's world, named once.
CONV_A = "conv-p4-4-a"
CONV_B = "conv-p4-4-b"
MEMORY_A = "MEMO-ALPHA the user keeps a flat near the park."
MEMORY_B = "MEMO-BRAVO the user plays the drums on Fridays."
REL_STORE_OFFLINE = "relationship projection store offline (injected)"


# ---------------------------------------------------------------------------
# assembly (the shared P3-1A helper, with the lease handle kept)
# ---------------------------------------------------------------------------


def _coordinator(
    *,
    store: SqliteConversationStore,
    generation_store: AssemblyGenerationStore,
    lease,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    provider,
    projections: CP4ProjectionRuntime | None = None,
    persona_views: ControllerPersonaViews | None = None,
) -> ConversationCoordinator:
    """The shared P3-1A/P3-1B assembly over this test's epoch.

    ``make_viewing_coordinator`` mints its own lease; the ① guard pin has to
    hold the *same* handle the coordinator holds, so this file goes one step
    further down to the same shared helper (no second assembly).
    """

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


def _section(text: str, name: str) -> str:
    """One rendered ``[name]`` section of a compiled prompt."""

    for block in text.split("\n\n"):
        if block.startswith(f"[{name}]\n"):
            return block
    raise AssertionError(f"no [{name}] section in prompt:\n{text}")


def _prompt_of(provider: RecordingProvider, index: int = -1) -> str:
    assert provider.prompts, "the provider was never called"
    return provider.prompts[index].prompt_text


def _assistant_rows(db) -> list[tuple[object, ...]]:
    """Every canonical assistant turn, in message order (the "not re-sent"
    inventory: a re-send would add a row, a rewrite would change one)."""

    return [
        tuple(row)
        for row in db.execute(
            "SELECT assistant_turn_id, turn_id, content FROM assistant_turn"
            " ORDER BY message_sequence"
        ).fetchall()
    ]


def _section_value(text: str, name: str, key: str) -> str:
    """One ``key: value`` of one rendered section, value verbatim.

    The P4-3 convention (pinned in test_p4_3_prompt_sections): a view that is
    *present but empty* still renders its section — the section is a function
    of the view, not of its content — so "no memories yet" is the empty
    ``memories:`` value, never a missing section. Importing the helper form
    from that file's ``_keys`` idea keeps this file's reads structural rather
    than string-shaped.
    """

    prefix = f"{key}: "
    for line in _section(text, name).splitlines()[1:]:
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f"no {key!r} in the [{name}] section:\n{text}")


# ---------------------------------------------------------------------------
# ① the single-turn success chain
# ---------------------------------------------------------------------------


def test_1_one_turn_lands_the_transcript_and_both_projections(
    store,
    generation_store,
    db,
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
    """①: CP0 → prompt → CP3a → CP4, with every intermediate read back."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(MEMORY_A),)
    lease = make_lease(fence)
    runtime, (rel_probe, ep_probe) = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    rel_probe.observe(lease, db, conversation)
    ep_probe.observe(lease, db, conversation)
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        lease=lease,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        projections=runtime,
        persona_views=persona_views,
    )

    turn = commit_chat_turn(
        coordinator, "cm-1", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    assert turn.turn_status.value == "COMPLETED"

    # The canonical transcript, three pieces, read back through the store's
    # own read face (not from the returned object).
    slice_ = turn_slice(store, turn.turn_id)
    assert slice_.user_turn.raw_content == "I live in Berlin."
    assert slice_.assistant_turn is not None
    assert slice_.assistant_turn.content == turn.reply_text
    assert slice_.outcome is not None and slice_.outcome.value == "REPLIED_FULL"

    # RA §19 / §24.1, seen from inside both real executors: the guard was
    # released before CP4 ran and no transaction was open at that moment.
    assert rel_probe.calls == 1 and ep_probe.calls == 1
    assert rel_probe.lease_held is False and rel_probe.in_transaction is False
    assert ep_probe.lease_held is False and ep_probe.in_transaction is False
    assert lease.is_held(conversation) is False
    # … and the probe is not vacuous: this same handle does report a held
    # guard while one is held.
    with lease.hold(conversation):
        assert lease.is_held(conversation) is True
    assert lease.is_held(conversation) is False

    # One job per supported type, each COMMITTED, each with its honest base
    # and attempt count.
    rows = projection_job_rows(db)
    assert len(rows) == len(SUPPORTED_PROJECTION_TYPES)
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, turn.turn_id)
    ep_job = projection_id_for(PROJECTION_TYPE_EPISODE, turn.turn_id)
    rel_row = projection_job_row(db, rel_job)
    assert rel_row[5] == "COMMITTED" and rel_row[6] == 1
    assert str(rel_row[4]).startswith("rv-")  # the summary digest, recomputed
    ep_row = projection_job_row(db, ep_job)
    assert ep_row[5] == "COMMITTED" and ep_row[6] == 1
    # The first episode of a conversation has no base: the job records the
    # declared absent-sentinel, never a fabricated digest.
    assert ep_row[4] == EPISODE_ABSENT_BASE_VERSION

    # … and the durable effects are there: one memory row, one episode row.
    assert len(memory_rows(db)) == 1
    assert memory_rows(db)[0][5] == MEMORY_A
    assert str(memory_rows(db)[0][1]) == str(PERSONA_A)
    assert episode_row(db, conversation)[2].startswith("epv-")


def test_1b_a_single_failing_executor_leaves_its_sibling_alone(
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
    db,
) -> None:
    """①(另一场景): one type fails, the other commits; the retry lands it."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(MEMORY_A),)
    runtime, (rel_probe, _) = runtime_with_probes(
        projection_store, store, relationship_projection, episode_projection
    )
    rel_probe.fail_with(
        DomainErrorCode.DEPENDENCY_UNAVAILABLE, REL_STORE_OFFLINE
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
        coordinator, "cm-1b-1", "I live in Berlin.", 1, conversation=conversation
    )
    assert first.outcome == "REPLIED_FULL"
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, first.turn_id)
    ep_job = projection_id_for(PROJECTION_TYPE_EPISODE, first.turn_id)
    rel_row = projection_job_row(db, rel_job)
    assert rel_row[5] == "FAILED_RETRYABLE" and rel_row[6] == 1
    ep_row = projection_job_row(db, ep_job)
    assert ep_row[5] == "COMMITTED" and ep_row[6] == 1
    assert memory_rows(db) == []  # the failing leg wrote nothing
    # The sibling really landed its own durable effect (not a vacuous "the
    # row exists" check): the episode carries this turn's utterance.
    episode = episode_row(db, conversation)
    assert "I live in Berlin." in str(episode[5])
    assert str(episode[3]) == "1" and str(episode[4]) == "1"

    # The next turn retries the failed sibling (the conversation's pending
    # queue is drained by every post-turn run) and lands both types.
    rel_probe.failure = None
    second = commit_chat_turn(
        coordinator, "cm-1b-2", "I read every evening.", 2,
        conversation=conversation,
    )
    assert second.outcome == "REPLIED_FULL"
    assert projection_job_row(db, rel_job)[5] == "COMMITTED"
    assert projection_job_row(db, rel_job)[6] == 2  # retried once
    rows = projection_job_rows(db)
    assert len(rows) == 2 * len(SUPPORTED_PROJECTION_TYPES)
    assert {row[5] for row in rows} == {"COMMITTED"}
    # No duplicate rows: the job ids are the deterministic per-(type, turn)
    # ids, and the retry addressed the same row.
    assert len({row[0] for row in rows}) == len(rows)
    assert projection_job_row(db, ep_job)[6] == 1  # the sibling was not rerun


# ---------------------------------------------------------------------------
# ② a pending projection never carries the next turn
# ---------------------------------------------------------------------------


def test_2_a_retryable_projection_failure_does_not_block_the_next_turn(
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    relationship_controller,
    episode_projection,
    projection_store,
    persona_views,
    db,
) -> None:
    """②: continuity comes from the transcript, never from the projection."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    refusing = RefusingCandidates()
    relationship = relationship_projection_with(
        store, relationship_controller, refusing
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
        projections=CP4ProjectionRuntime(
            store=projection_store,
            executors=(relationship, episode_projection),
            turns=store,
        ),
        persona_views=persona_views,
    )

    first = commit_chat_turn(
        coordinator, "cm-2-1", "I live in Berlin.", 1, conversation=conversation
    )
    assert first.outcome == "REPLIED_FULL"
    rel_job = projection_id_for(PROJECTION_TYPE_RELATIONSHIP, first.turn_id)
    assert projection_job_row(db, rel_job)[5] == "FAILED_RETRYABLE"
    assert memory_rows(db) == []
    # Direct "not re-sent" pin #1 (P4-4 review F-P44-3): the failed projection
    # left the canonical assistant side exactly as the delivery wrote it —
    # one row, its content the reply text.
    after_failure = _assistant_rows(db)
    assert len(after_failure) == 1
    assert after_failure[0][1] == str(first.turn_id)
    assert after_failure[0][2] == first.reply_text

    second = commit_chat_turn(
        coordinator, "cm-2-2", "I read every evening.", 2,
        conversation=conversation,
    )
    assert second.outcome == "REPLIED_FULL"
    assert second.turn_status.value == "COMPLETED"
    # The failure is persistent: the retry attempt ran (attempt 2) and the
    # job is still waiting, never silently dropped.
    assert projection_job_row(db, rel_job)[5] == "FAILED_RETRYABLE"
    assert projection_job_row(db, rel_job)[6] == 2
    # Direct "not re-sent" pin #2: the retry attempt changed neither the
    # first answer (same row, byte for byte) nor the row count beyond the
    # new turn's own single delivery.
    rows_now = _assistant_rows(db)
    assert len(rows_now) == 2
    assert rows_now[0] == after_failure[0]
    assert rows_now[1][1] == str(second.turn_id)
    assert rows_now[1][2] == second.reply_text

    # The prompt's history is the canonical transcript *as it stood when the
    # prompt was compiled*: every slice of the window, with this turn's own
    # assistant leg omitted — a turn's output is canonicalized after its
    # prompt is built (DOMAIN_MODEL §3: only delivered output is canonical),
    # so the later window read has exactly one line more than the prompt did.
    prompt = _prompt_of(provider)
    window = store.get_conversation_window(
        conversation, CONVERSATION_WINDOW_MAX_TURNS
    )
    assert isinstance(window, Ok), window
    expected: list[str] = []
    for slice_ in window.value.slices:
        expected.append(
            f"#{slice_.turn_sequence} user: {slice_.user_turn.raw_content}"
        )
        if slice_.assistant_turn is None or slice_.turn_id == second.turn_id:
            continue
        expected.append(
            f"#{slice_.turn_sequence} assistant: "
            f"{slice_.assistant_turn.content}"
        )
    assert _section(prompt, "history").splitlines()[1:] == expected
    assert len(expected) == 3  # two user legs + turn 1's answer
    # The line that carries the continuity is turn 1's answer, verbatim from
    # the transcript, while the relationship projection was down.
    assert f"#1 assistant: {first.reply_text}" in _section(prompt, "history")
    # … so the second turn is coherent although the projection never landed:
    # the relationship section renders its view, and that view is empty —
    # the honest "nothing remembered yet", never a missing section (the
    # P4-3 convention) and never a stale memory.
    assert _section_value(prompt, "relationship", "memories") == ""
    assert MEMORY_A not in prompt
    # The episode did land (the other type is independent).
    assert "[episode]" in prompt
    assert "I live in Berlin." in prompt


# ---------------------------------------------------------------------------
# ③ the projected context of the next turn, reconciled with the durable rows
# ---------------------------------------------------------------------------


def test_3_the_next_prompt_carries_the_projection_and_reconciles(
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
    db,
) -> None:
    """③: before → after, durable row by durable row, plus byte determinism."""

    conversation = open_conversation_for(store, CONV_A, PERSONA_A)
    scripted_candidates.candidates = (memory_candidate(MEMORY_A),)
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
        projections=CP4ProjectionRuntime(
            store=projection_store,
            executors=(relationship_projection, episode_projection),
            turns=store,
        ),
        persona_views=persona_views,
    )

    first_turn = commit_chat_turn(
        coordinator, "cm-3-1", "I live in Berlin.", 1, conversation=conversation
    )
    assert first_turn.outcome == "REPLIED_FULL"
    before = _prompt_of(provider)
    # Nothing was projected before this turn's own prompt was compiled: no
    # episode at all, an empty relationship view, and the memory text (the
    # candidate's own words, not the utterance) is nowhere.
    assert "[episode]" not in before
    assert _section_value(before, "relationship", "memories") == ""
    assert MEMORY_A not in before

    # The state the *next* turn's prompt is compiled from: the rows this
    # turn's own projection landed. Captured now, deliberately — turn 2's
    # projection moves the episode again, and the prompt under test predates
    # that move (reading the rows after turn 2 would reconcile the prompt
    # against a later generation of the row and prove nothing).
    memory_at_compile = memory_rows(db)[0]
    episode_at_compile = episode_row(db, conversation)

    commit_chat_turn(
        coordinator, "cm-3-2", "I read every evening.", 2,
        conversation=conversation,
    )
    after = _prompt_of(provider)
    assert f"USER_STATED_FACT: {memory_at_compile[5]}" in after
    assert f"summary: {episode_at_compile[5]}" in after
    assert f"episode_id: {episode_at_compile[0]}" in after
    assert f"version: {episode_at_compile[2]}" in after
    # The prompt renders the *content* columns only (the P3-0 rule): the
    # durable stamp stays out.
    assert str(episode_at_compile[9]) not in after
    # … and the snapshot above is of a live projection: turn 2's own run
    # really moved the row (a frozen or replayed projection would not).
    moved = episode_row(db, conversation)
    assert moved[2] != episode_at_compile[2]
    assert str(moved[4]) != str(episode_at_compile[4])

    # Byte determinism over the same durable state: two independent
    # reconstructions of the request (fresh reads through the real port and
    # the real window) compile to the same bytes.
    current = episode_row(db, conversation)
    first = _recompiled_prompt(store, persona_views, conversation, PERSONA_A)
    second = _recompiled_prompt(store, persona_views, conversation, PERSONA_A)
    assert first == second
    assert MEMORY_A in first  # the reconstruction really consumes the rows
    assert str(current[5]) in first


def _recompiled_prompt(
    store: SqliteConversationStore,
    views: ControllerPersonaViews,
    conversation: ConversationId,
    persona_id: PersonaId,
) -> str:
    """Compile one prompt from the durable state, through the real faces.

    The live pipeline compiles a prompt per turn *before* that turn's own
    projections run, so a reconstruction made afterwards is deliberately not
    compared with a live prompt: what it pins is that the compiler is a
    function of the durable state (same reads, same bytes).
    """

    window = store.get_conversation_window(
        conversation, CONVERSATION_WINDOW_MAX_TURNS
    )
    relationship = views.relationship_view(persona_id, REL_USER)
    episode = views.episode_view(conversation)
    profile = views.disclosed_user_profile(REL_USER, persona_id)
    for outcome in (window, relationship, episode, profile):
        assert isinstance(outcome, Ok), outcome
    contract = GenerationContract(
        generation_contract_id="gc-normal-persona-reply",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=persona_id,
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
    )
    request = PromptCompilationRequest(
        conversation_id=conversation,
        persona_id=persona_id,
        interaction_channel=InteractionChannel.TEXT,
        generation_context=GenerationContext(
            character_package=None,
            relationship_view=relationship.value,
            episode_view=episode.value,
            world_lore_view=None,
            disclosed_user_profile=profile.value,
            conversation_window=window.value,
            language_policy="default",
            generation_policy="default",
            generation_contract=contract,
            ephemeral_teaching_directive=None,
        ),
        generation_contract=contract,
    )
    compiled = PromptCompiler().compile(request)
    assert isinstance(compiled, Ok), compiled
    return compiled.value.prompt_text


# ---------------------------------------------------------------------------
# ④ two conversations, two personas, one assembly
# ---------------------------------------------------------------------------


def test_4_alternating_personas_stay_isolated_in_both_directions(
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
    db,
) -> None:
    """④: the A/B isolation, asserted on what each persona was actually told."""

    conv_a = open_conversation_for(store, CONV_A, PERSONA_A)
    conv_b = open_conversation_for(store, CONV_B, PERSONA_B)
    candidates = PerConversationCandidates({CONV_A: MEMORY_A, CONV_B: MEMORY_B})
    relationship = relationship_projection_with(
        store, relationship_controller, candidates
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
        projections=CP4ProjectionRuntime(
            store=projection_store,
            executors=(relationship, episode_projection),
            turns=store,
        ),
        persona_views=persona_views,
    )

    # Six turns, strictly alternating: each conversation sees the other's
    # projections land between its own turns.
    turn_no = 0
    for round_no in range(1, 4):
        for conversation, marker in ((conv_a, "ALPHA"), (conv_b, "BRAVO")):
            turn_no += 1
            turn = commit_chat_turn(
                coordinator,
                f"cm-4-{marker}-{round_no}",
                f"{marker}-{round_no} I keep notes.",
                turn_no,
                conversation=conversation,
            )
            assert turn.outcome == "REPLIED_FULL"

    prompts = provider.prompt_texts
    assert len(prompts) == 6
    a_prompts = [prompts[index] for index in (0, 2, 4)]
    b_prompts = [prompts[index] for index in (1, 3, 5)]

    # The negative control first: each side really does see its own material
    # (otherwise the absence assertions below would be vacuous).
    assert MEMORY_A in a_prompts[-1] and "ALPHA-3" in a_prompts[-1]
    assert MEMORY_B in b_prompts[-1] and "BRAVO-3" in b_prompts[-1]

    for prompt in b_prompts:
        for leaked in (MEMORY_A, "ALPHA", str(PERSONA_A)):
            assert leaked not in prompt, leaked
    for prompt in a_prompts:
        for leaked in (MEMORY_B, "BRAVO", str(PERSONA_B)):
            assert leaked not in prompt, leaked

    # … and the durable rows are scoped, not merely unrendered: one memory
    # per (persona, user) pair, one episode per conversation.
    view_a = relationship_controller.get_relationship_view(PERSONA_A, REL_USER)
    view_b = relationship_controller.get_relationship_view(PERSONA_B, REL_USER)
    assert isinstance(view_a, Ok) and isinstance(view_b, Ok)
    assert [entry.canonical_content for entry in view_a.value.active_memories] == [
        MEMORY_A
    ]
    assert [entry.canonical_content for entry in view_b.value.active_memories] == [
        MEMORY_B
    ]
    rows = memory_rows(db)
    assert len(rows) == 2
    assert {str(row[1]) for row in rows} == {str(PERSONA_A), str(PERSONA_B)}
    assert {str(row[2]) for row in rows} == {str(REL_USER)}
    assert {str(row[5]) for row in rows} == {MEMORY_A, MEMORY_B}
    # The episodes are per conversation as well: each summary carries its own
    # conversation's utterances and none of the other's.
    episode_a = episode_row(db, conv_a)
    episode_b = episode_row(db, conv_b)
    assert "ALPHA" in str(episode_a[5]) and "BRAVO" not in str(episode_a[5])
    assert "BRAVO" in str(episode_b[5]) and "ALPHA" not in str(episode_b[5])
    assert str(episode_a[1]) == str(conv_a)
    assert str(episode_b[1]) == str(conv_b)
