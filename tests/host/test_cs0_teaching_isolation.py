"""cs-0 — 教学/角色隔离刀的钉（附笺模式，DEC-OPI-a31b14c9-…19 附笺裁决）。

产品铁律：角色（笔友人设）不能意识到「教学系统」的存在。本文件钉五面：

1. **黑名单钉**（正向钉，变异必红）：全部六个 action 类型的编译样例里，
   运行时机制词零出现——moment_id / presentation_phase / support_level /
   attempt_index / focus_target_* / TEACHING_* / PERSONA_RESUME /
   closure: / completion_outcome / abort_reason / gc-teaching；视图的
   机制字段填满区分值也不得泄漏（编译器只读附笺）。
2. **附笺钉**：``[enclosed-note]`` 节 = 版本词 + 固定携带指令 + 附笺正文
   （逐字、转义、字节确定）；在线 e2e（真 host + 真语料 + 脚本信使）：
   交付文本 = 信 + 附笺逐字复合（「Anyway.」来自语料 canonical_forms[0]，
   框架词是系统文案常量），provider 只看到中性指令与附笺正文。
3. **[response] 措辞钉**：机制词退役、语义逐字保留（英语表达保留英文
   原文，一字不改）。
4. **历史读面过滤钉**：含教学 assistant 轮的会话里，person-visible 读面
   （窗口 / 可见切片 / [history] 编译 / episode.recent_events /
   recorder 消费面）一致地不带教学文本与信件文本；写面不动（完整
   transcript 读仍可读）；用户自己的话照旧可见。
5. **既有 e2e 语义保持**：phase8 教学 e2e 全绿由全量承担，本文件不重复。

诚实边界：这是软隔离——钉的是「编译产物与可见读面零机制词、附笺逐字
来自语料」，不声称模型永不自发提及任何机制（那不是可钉命题）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from elc.content.build import build_content_db
from elc.conversation.commands import describe_slice
from elc.conversation.types import ConversationStatus
from elc.detection.pilot import PILOT_VERSION, register_pilot
from elc.detection.registry import DetectorRegistry
from elc.host import open_host
from elc.persona.commands import (
    ENCLOSED_NOTE_INSTRUCTION,
    RESPONSE_SECTION,
    PromptCompiler,
)
from elc.persona.provider import ScriptedPersonaProvider
from elc.persona.types import (
    ENCLOSED_NOTE_PROMPT_KEY_ORDER,
    ENCLOSED_NOTE_PROMPT_SECTION_VERSION,
    CompiledPrompt,
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
    ProviderOutput,
    TeachingPromptView,
)
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    Ok,
    PersonaId,
    UserId,
)
from elc.relationship.episode import rebuild_episode
from elc.relationship.recorder import (
    RelationshipMemoryCandidate,
    RelationshipRecorder,
    RelationshipRecorderKey,
)
from elc.relationship.types import (
    MemoryProvenance,
    RelationshipMemoryType,
    SamePersonaExistingRelationshipSummary,
)
from elc.runtime.controller import OPENING_NOTE_TEMPLATE
from elc.runtime.types import GenerationActionType, InputEnvelope
from elc.teaching.rollout import RolloutStage

CONV = ConversationId("cs0-conv")
LETTER = "I read your last letter twice — the city sounds wonderful."
ERROR_TEXT = "Any way, let's continue with the plan."
EV_TARGET = "res-discourse-anyway"

#: The corpus note the opening carries: canonical_forms[0] of the EV target
#: (read from the built artifact in the e2e; the frame is the system copy).
ANYWAY_FORM = "Anyway."

#: cs-0 的机制词黑名单（编译产物与可见读面都必须为零）。
MECHANISM_WORDS = (
    "moment_id",
    "presentation_phase",
    "support_level",
    "attempt_index",
    "focus_target_type",
    "focus_target_id",
    "TEACHING_OPEN",
    "TEACHING_HINT",
    "TEACHING_REVEAL",
    "TEACHING_EXPLANATION",
    "PERSONA_RESUME",
    "closure:",
    "completion_outcome",
    "abort_reason",
    "gc-teaching",
)


class RecordingProvider(ScriptedPersonaProvider):
    """The scripted messenger that keeps the prompts it was handed."""

    def __init__(self, script: tuple[ProviderOutput, ...]) -> None:
        super().__init__(script=script)
        self.prompts: list[CompiledPrompt] = []

    def call(self, prompt: CompiledPrompt):
        self.prompts.append(prompt)
        return super().call(prompt)


def _request(
    *,
    action_type: GenerationActionType,
    contract_id: str,
    directive: TeachingPromptView | None,
    conversation_window=None,
) -> PromptCompilationRequest:
    contract = GenerationContract(
        generation_contract_id=contract_id,
        action_type=action_type,
        persona_id=PersonaId("persona-cs0"),
        allowed_disclosures=(),
        language_policy="follow-user",
        style_constraints=(),
    )
    return PromptCompilationRequest(
        conversation_id=CONV,
        persona_id=PersonaId("persona-cs0"),
        interaction_channel=InteractionChannel.TEXT,
        generation_context=GenerationContext(
            character_package=None,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=conversation_window,
            language_policy="follow-user",
            generation_policy="default",
            generation_contract=contract,
            ephemeral_teaching_directive=directive,
        ),
        generation_contract=contract,
    )


def _compile(request: PromptCompilationRequest) -> str:
    compiled = PromptCompiler().compile(request)
    assert isinstance(compiled, Ok), compiled
    return compiled.value.prompt_text


# ---------------------------------------------------------------------------
# ① 黑名单钉——六个 action 类型 × 机制字段填满区分值，编译产物零机制词


@pytest.mark.parametrize(
    "action_type",
    [
        GenerationActionType.NORMAL_PERSONA_REPLY,
        GenerationActionType.TEACHING_OPEN,
        GenerationActionType.TEACHING_HINT,
        GenerationActionType.TEACHING_REVEAL,
        GenerationActionType.TEACHING_EXPLANATION,
        GenerationActionType.PERSONA_RESUME,
    ],
)
def test_compiled_prompts_carry_zero_mechanism_words(
    action_type: GenerationActionType,
) -> None:
    """The compile face never renders the runtime's own vocabulary: the
    view's mechanism carrier fields are filled with distinctive values and
    none of them (nor any contract id of the old shape) reaches the bytes."""

    directive = TeachingPromptView(
        action_type=action_type.value,
        moment_id="mom-cs0-leak",
        presentation_phase="FULL_REVEAL",
        support_level="FULL_FORM_SHOWN",
        attempt_index=7,
        focus_target_type="RESOURCE",
        focus_target_id="res-cs0-leak",
        hint="hint text",
        reveal="reveal text",
        explanation="explanation text",
        closure="USER_SKIP",
        completion_outcome="COMPLETED",
        abort_reason="USER_SKIP",
        enclosed_note="Hedge the claim.",
    )
    contract_id = (
        "gc-normal"
        if action_type is GenerationActionType.NORMAL_PERSONA_REPLY
        else None
    )
    text = _compile(
        _request(
            action_type=action_type,
            contract_id=contract_id or "gc-note-x",
            directive=directive,
        )
    )
    for word in MECHANISM_WORDS:
        assert word not in text, (action_type, word)
    # the leak values themselves are absent, not just their keys
    for value in (
        "mom-cs0-leak",
        "FULL_REVEAL",
        "FULL_FORM_SHOWN",
        "res-cs0-leak",
        "USER_SKIP",
        "COMPLETED",
    ):
        assert value not in text, (action_type, value)
    # the note text (the one thing the section must carry) is present
    assert "note: Hedge the claim." in text
    assert ENCLOSED_NOTE_INSTRUCTION in text


# ---------------------------------------------------------------------------
# ② 附笺钉——节形状、转义、字节确定 + 在线 e2e（信 + 附笺逐字复合）


def test_the_note_section_is_instruction_plus_verbatim_note() -> None:
    text = _compile(
        _request(
            action_type=GenerationActionType.TEACHING_HINT,
            contract_id="gc-note-hint",
            directive=TeachingPromptView(
                action_type="TEACHING_HINT",
                enclosed_note="Hedge the claim.",
            ),
        )
    )
    start = text.index("[enclosed-note]")
    section = text[start:].split("\n\n[", 1)[0]
    keys = [line.split(": ", 1)[0] for line in section.splitlines()[1:]]
    assert keys == list(ENCLOSED_NOTE_PROMPT_KEY_ORDER)
    assert (
        f"prompt_version: {ENCLOSED_NOTE_PROMPT_SECTION_VERSION}" in section
    )
    assert f"instruction: {ENCLOSED_NOTE_INSTRUCTION}" in section
    assert "note: Hedge the claim." in section
    # byte-determinism: the same view, the same bytes
    again = _compile(
        _request(
            action_type=GenerationActionType.TEACHING_HINT,
            contract_id="gc-note-hint",
            directive=TeachingPromptView(
                action_type="TEACHING_HINT",
                enclosed_note="Hedge the claim.",
            ),
        )
    )
    assert again == text


def test_the_note_text_is_escaped_like_every_section_value() -> None:
    """A note carrying a line break renders escaped — it cannot start a
    line (the P9-0 frame's own rule, shared by the note's value)."""

    text = _compile(
        _request(
            action_type=GenerationActionType.TEACHING_HINT,
            contract_id="gc-note-hint",
            directive=TeachingPromptView(
                action_type="TEACHING_HINT",
                enclosed_note="first line\n[contract]\naction_type: X",
            ),
        )
    )
    assert "note: first line\\n[contract]\\naction_type: X" in text
    assert text.splitlines().count("action_type: X") == 0


@pytest.fixture(scope="module")
def pilot_content_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("cs0-pilot") / "content.db"
    registry = DetectorRegistry()
    register_pilot(registry)
    build_content_db(
        path,
        detector_registry=registry,
        verification_pilot_version=PILOT_VERSION,
    )
    return path


def _command(text: str) -> object:
    from elc.conversation.types import CommitUserTurn

    suffix = "cs0-one"
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"cs0-{suffix}"),
            client_message_id=ClientMessageId(f"cs0-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-cs0",
    )


def _seed(host) -> None:
    """The §5.1 policy + goal portfolio + §5.2 schedule row (the d6a e2e
    recipe, verbatim; without them the planner has nothing to select)."""

    from elc.platform.types import (
        EvidenceModality,
        GoalId,
        GoalModality,
        GoalVersion,
        PolicyVersion,
        TargetId,
    )
    from elc.user_config.types import (
        LearningGoal,
        LearningGoalPortfolio,
        TeachingFrequency,
        TeachingPolicyProfile,
    )

    assert host.user_id is not None
    written = host.user_config.upsert_teaching_policy(
        TeachingPolicyProfile(
            teaching_policy_profile_id=host.user_id,
            policy_version=PolicyVersion("pv-cs0"),
            teaching_frequency=TeachingFrequency.BALANCED,
        )
    )
    assert isinstance(written, Ok), written
    portfolio = host.user_config.upsert_goal_portfolio(
        LearningGoalPortfolio(
            goal_portfolio_id=host.user_id,
            goal_version=GoalVersion("gv-cs0"),
            goals=(
                LearningGoal(
                    goal_id=GoalId("goal-cs0"),
                    goal_modality=GoalModality.SPEAKING,
                    description="a long-term goal",
                ),
            ),
            modality_weights={GoalModality.SPEAKING: 1.0},
            assessment_targets=(),
            effective_from=datetime.now(tz=UTC).isoformat(),
        )
    )
    assert isinstance(portfolio, Ok), portfolio
    row = host.curriculum.get_target(TargetId(EV_TARGET))
    assert isinstance(row, Ok), row
    scheduled = host.scheduler.recompute_schedule_item(
        row.value.target_type,
        TargetId(EV_TARGET),
        EvidenceModality(row.value.evidence_modality),
        datetime.now(tz=UTC).isoformat(),
    )
    assert isinstance(scheduled, Ok), scheduled


@pytest.fixture()
def cs0_world(tmp_path: Path, pilot_content_db: Path):
    """One real process: production host, real corpus, scripted messenger —
    the same online path the d6a e2e drives, plus the prompts it saw."""

    provider = RecordingProvider(script=(ProviderOutput(text=LETTER),))
    host = open_host(
        tmp_path / "app.db",
        provider=provider,
        content_db_path=pilot_content_db,
        rollout_stage=RolloutStage.STUDY_FIRST,
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        _seed(host)
        yield host, provider
    finally:
        host.close()


def test_the_letter_carries_the_corpus_note_verbatim(cs0_world) -> None:
    """The opening delivery is the letter with the note appended byte for
    byte: the note is the corpus's canonical form in the fixed frame, and
    the messenger's prompt carries only the neutral instruction."""

    host, provider = cs0_world
    result = host.coordinator.begin_turn(_command(ERROR_TEXT))
    assert isinstance(result, Ok), result
    assert result.value.reply_text is not None

    expected_note = OPENING_NOTE_TEMPLATE.format(form=ANYWAY_FORM)
    # the canonical text is letter + blank line + note, byte for byte
    assert result.value.reply_text == f"{LETTER}\n\n{expected_note}"
    # the messenger saw the neutral instruction and the corpus note — and
    # none of the runtime's own vocabulary
    assert len(provider.prompts) == 1
    prompt_text = provider.prompts[0].prompt_text
    assert ENCLOSED_NOTE_INSTRUCTION in prompt_text
    assert f"note: {expected_note}" in prompt_text
    for word in MECHANISM_WORDS:
        assert word not in prompt_text, word
    # the note's frame words are the system copy; the form is the corpus's
    assert OPENING_NOTE_TEMPLATE.format(form=ANYWAY_FORM) == (
        "这封信里附了一条表达：「Anyway.」——回信时试着用上它。"
    )


# ---------------------------------------------------------------------------
# ③ [response] 措辞钉——机制词退役、语义逐字保留


def test_the_response_section_keeps_the_semantics_without_the_word() -> None:
    assert "teaching" not in RESPONSE_SECTION
    assert "teach" not in RESPONSE_SECTION
    # the W-8 semantics, verbatim (minus the retired word): an expression
    # stays in English exactly as given
    assert (
        "english expressions: keep an expression itself in English,"
        " exactly as given" in RESPONSE_SECTION
    )
    assert (
        "language: follow the user — reply in the language the user writes"
        " in (simplified Chinese by default)" in RESPONSE_SECTION
    )
    text = _compile(
        _request(
            action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
            contract_id="gc-normal",
            directive=None,
        )
    )
    assert text.count("[response]") == 1
    assert RESPONSE_SECTION in text
    assert text.index("[response]") > text.index("[channel]")


# ---------------------------------------------------------------------------
# ④ 历史读面过滤钉——三个消费方一个视图，写面不动


def test_the_teaching_text_stays_out_of_the_persona_visible_reads(
    cs0_world,
) -> None:
    """One teaching turn in the transcript: the window, the visible slice
    read, the compiled [history], the episode's recent_events and the
    recorder's consumption face all see no teaching text and no letter —
    while the full transcript read and the durable row keep them (the write
    face is untouched) and the user's own words stay visible."""

    host, provider = cs0_world
    result = host.coordinator.begin_turn(_command(ERROR_TEXT))
    assert isinstance(result, Ok), result
    turn_id = result.value.turn_id
    composed = result.value.reply_text
    assert composed is not None

    window_result = host.conversations.get_conversation_window(CONV, 10)
    assert isinstance(window_result, Ok), window_result
    slices = window_result.value.slices
    assert len(slices) == 1
    visible = slices[0]
    # the teaching assistant text is not persona-visible …
    assert visible.assistant_turn is None
    # … the user's own words are …
    assert visible.user_turn.raw_content == ERROR_TEXT
    # … and the full transcript read keeps the composed row (write face).
    full = host.conversations.get_canonical_turn_slice(turn_id)
    assert isinstance(full, Ok) and full.value is not None
    assert full.value.assistant_turn is not None
    assert full.value.assistant_turn.content == composed
    # the visible-slice read (the recorder's face) filters the same way
    seen = host.conversations.get_persona_visible_turn_slice(turn_id)
    assert isinstance(seen, Ok) and seen.value is not None
    assert seen.value.assistant_turn is None

    # consumer 1 — the compiled [history]: no teaching text, no letter, the
    # user's line present
    history_text = _compile(
        _request(
            action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
            contract_id="gc-normal",
            directive=None,
            conversation_window=window_result.value,
        )
    )
    assert f"#1 user: {ERROR_TEXT}" in history_text
    assert ANYWAY_FORM not in history_text
    assert LETTER not in history_text

    # consumer 2 — the episode's recent_events over the same window
    rebuilt = rebuild_episode(
        conversation_id=CONV,
        slices=slices,
        relationship_summary=SamePersonaExistingRelationshipSummary(
            persona_id=PersonaId("persona-cs0"),
            user_id=UserId("user-cs0"),
        ),
        conversation_status=ConversationStatus.ACTIVE,
    )
    assert isinstance(rebuilt, Ok), rebuilt
    assert len(rebuilt.value.recent_events) == 1
    assert rebuilt.value.recent_events[0] == describe_slice(visible)
    assert ANYWAY_FORM not in rebuilt.value.recent_events[0]
    assert LETTER not in rebuilt.value.recent_events[0]

    # consumer 3 — the recorder on the visible slice: an assistant-grounded
    # candidate finds no assistant turn to ground on (its provenance refs
    # stay user-side), while the same candidate over the full transcript
    # slice carries the assistant row's id — the filter's effect on the
    # recorder's consumption face, made visible in the refs.
    recorder = RelationshipRecorder(command_turns=host.conversations)
    summary = SamePersonaExistingRelationshipSummary(
        persona_id=PersonaId("persona-cs0"),
        user_id=UserId("user-cs0"),
    )
    candidate = RelationshipMemoryCandidate(
        memory_type=RelationshipMemoryType.SHARED_EVENT,
        provenance=MemoryProvenance.USER_STATED_FACT,
        content="the user answered and the reply came",
    )
    outcome = recorder.record_turn(
        turn=seen.value,
        existing=summary,
        key=RelationshipRecorderKey(candidates=(candidate,)),
    )
    # the assistant-grounded candidate is refused outright on the visible
    # slice: with no persona-visible assistant turn there is no assistant
    # side to ground on, so the teaching turn cannot seed such a memory
    assert outcome.proposals == ()
    assert len(outcome.refusals) == 1
    full_outcome = recorder.record_turn(
        turn=full.value,
        existing=summary,
        key=RelationshipRecorderKey(candidates=(candidate,)),
    )
    assert len(full_outcome.proposals) == 1
    assistant_id = str(full.value.assistant_turn.assistant_turn_id)
    assert assistant_id in full_outcome.proposals[0].provenance_refs


def test_the_explanation_note_reads_the_corpus_teaching_notes(
    pilot_content_db: Path,
) -> None:
    """G2's explanation face: the §24.3 teaching_note rows are the corpus's
    own explanation words, read in authored order — the note an explanation
    delivery assembles (pinned on the real built artifact)."""

    from elc.content.store import ContentStore
    from elc.curriculum.store import CurriculumContentStore
    from elc.runtime.controller import _explanation_note_for
    from elc.teaching.targets import TeachingTargetView

    supply = CurriculumContentStore(ContentStore(pilot_content_db))
    try:
        teaching = supply.get_teaching_content(EV_TARGET)
        assert isinstance(teaching, Ok), teaching
        notes = teaching.value.teaching_notes
        assert len(notes) >= 1
        assert "any way" in notes[0]  # the corpus's own words, not a model's
        view = TeachingTargetView(
            target_type="RESOURCE",
            target_id=EV_TARGET,
            target_status="VALID",
            content_status="VALID",
            target_mode="RESOURCE_PRACTICE",
            learning_intent="ESTABLISH",
            evidence_modality="TEXT_PRODUCTION",
            teaching_notes=notes,
        )
        assert _explanation_note_for(view) == " ".join(notes)
        assert _explanation_note_for(None) == ""
    finally:
        supply.close()
