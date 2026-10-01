"""VAL ⑨ — the prompt section the teaching turn compiles is Persona-owned,
versioned and byte-deterministic (P3-1B; cs-0 recast it as the neutral
``[enclosed-note]`` section).

DOMAIN_MODEL §11/§14: Teaching produces an ``EphemeralTeachingDirective`` —
never a persona prompt — and the Persona Runtime's PromptCompiler owns the
final prompt. The projection from the directive to the persona-owned
``TeachingPromptView`` happens in the orchestrator (the one place that knows
both packages; the AST pin forbids either domain importing the other).

What is pinned here (cs-0's shapes):

- the section renders ``[enclosed-note]`` with the keys of
  ``ENCLOSED_NOTE_PROMPT_KEY_ORDER`` in exactly that order and its template
  version inside the section, so a stored prompt says which template
  produced it — and no mechanism key (moment / phase / support / attempt /
  closure / outcome / reason) renders anywhere in the prompt;
- the whole prompt is byte-deterministic (same view → same bytes) and the
  section order is
  ``persona → contract → history → relationship → episode →
  enclosed-note → channel``;
- the compiled ``[contract]`` names the action with the one neutral word
  (the runtime's own action vocabulary never reaches the role), and the
  note text the delivery carries is the corpus's own words — a hint rung,
  the closing reveal — never a mechanism value;
- the provider only ever sees the note instruction and the note text (it
  never picks a ladder rung), and a resume prompt carries the closing note
  — no attempt ids, no snapshot, no ladder internals, no closure words.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.persona import PromptCompiler, ScriptedPersonaProvider
from elc.persona.commands import (
    COMPILED_ACTION_WORD,
    ENCLOSED_NOTE_INSTRUCTION,
    PROMPT_SECTION_ORDER,
)
from elc.persona.types import (
    ENCLOSED_NOTE_PROMPT_KEY_ORDER,
    ENCLOSED_NOTE_PROMPT_SECTION_VERSION,
    CompiledPrompt,
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
    TeachingPromptView,
)
from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import ClientMessageId, InteractionChannel, Ok
from elc.runtime.controller import (
    ConversationCoordinator,
    TeachingReplyRequest,
)
from elc.runtime.types import GenerationActionType
from elc.teaching.envelope import TeachingControlIntent, TeachingResponseEnvelope
from elc.teaching.request import TeachingRequest
from elc.teaching.types import MomentState

from .conftest import CONV, make_lease, make_teaching_coordinator

REQUESTED_AT = "2026-09-21T11:00:00+00:00"
TARGET = "res-hedge-i-think"

#: cs-0: the mechanism words that must never reach the compiled prompt —
#: the blacklist pin's word list, shared by every test below.
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
    """Scripted provider that keeps the compiled prompts it was handed."""

    def __init__(self) -> None:
        super().__init__()
        self.prompts: list[CompiledPrompt] = []

    def call(self, prompt: CompiledPrompt):
        self.prompts.append(prompt)
        return super().call(prompt)


def _coordinator(
    store: SqliteConversationStore,
    generation_store,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    provider: RecordingProvider,
) -> ConversationCoordinator:
    return make_teaching_coordinator(
        store,
        generation_store,
        make_lease(fence),
        provider,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
    )


def _note_section(prompt: CompiledPrompt) -> str:
    text = prompt.prompt_text
    start = text.index("[enclosed-note]")
    rest = text[start:]
    end = rest.find("\n\n[")
    return rest if end == -1 else rest[:end]


def test_the_rendered_section_follows_the_pinned_key_order() -> None:
    compiler = PromptCompiler()
    view = TeachingPromptView(
        action_type="TEACHING_HINT",
        presentation_phase="HINT_SEMANTIC",
        support_level="SEMANTIC_HINT",
        moment_id="tm-1",
        focus_target_type="RESOURCE",
        focus_target_id="res-hedge-i-think",
        attempt_index=1,
        hint="Hedge the claim.",
    )
    contract = GenerationContract(
        generation_contract_id="gc-note-hint",
        action_type=GenerationActionType.TEACHING_HINT,
        persona_id="persona-1",
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
    )
    request = PromptCompilationRequest(
        conversation_id=CONV,
        persona_id="persona-1",
        interaction_channel=InteractionChannel.TEXT,
        generation_context=GenerationContext(
            character_package=None,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=None,
            language_policy="default",
            generation_policy="default",
            generation_contract=contract,
            ephemeral_teaching_directive=view,
        ),
        generation_contract=contract,
    )
    compiled = compiler.compile(request)
    assert isinstance(compiled, Ok), compiled
    section = _note_section(compiled.value)
    assert section.startswith("[enclosed-note]\nprompt_version: ")
    assert f"prompt_version: {ENCLOSED_NOTE_PROMPT_SECTION_VERSION}" in section
    keys = [line.split(": ", 1)[0] for line in section.splitlines()[1:]]
    assert keys == list(ENCLOSED_NOTE_PROMPT_KEY_ORDER)
    # the carry instruction is the fixed neutral one, and the note text is
    # the view's own note (the legacy hint field feeds it until the
    # orchestrator fills the note field)
    assert f"instruction: {ENCLOSED_NOTE_INSTRUCTION}" in section
    assert "note: Hedge the claim." in section
    # cs-0: no mechanism word reaches the compiled prompt, whatever the
    # view's carrier fields hold
    for word in MECHANISM_WORDS:
        assert word not in compiled.value.prompt_text, word
    # Byte-determinism: the same view compiles to exactly the same bytes.
    again = compiler.compile(request)
    assert isinstance(again, Ok)
    assert again.value.prompt_text == compiled.value.prompt_text
    # P4-3 semantic sync (TASK-OPI-4d516e4f.19 ④): the order this test pins
    # is the same declared constant it always pinned — P4-3 inserted the
    # three §11 views Persona Runtime consumes (profile / relationship /
    # episode) at their stated positions. cs-0 renamed the ephemeral slot's
    # section; the position is the old one.
    assert PROMPT_SECTION_ORDER == (
        "persona",
        "profile",
        "contract",
        "history",
        "relationship",
        "episode",
        "enclosed-note",
        "channel",
    )
    # cs-0: the compiled action word is the neutral one — the runtime's
    # own vocabulary never reaches the [contract] section
    assert f"action_type: {COMPILED_ACTION_WORD}" in compiled.value.prompt_text


def test_the_delivered_teaching_prompt_carries_the_corpus_note(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    del conversation
    provider = RecordingProvider()
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        provider,
    )
    opened = coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=TARGET,
            client_message_id=ClientMessageId("cm-open"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(opened, Ok), opened

    hint = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.ASK_HINT
            ),
            client_message_id=ClientMessageId("cm-hint"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(hint, Ok), hint
    assert len(provider.prompts) == 2  # opening + hint

    opening_prompt = provider.prompts[0].prompt_text
    # the opening note is the corpus's canonical form in the fixed frame
    opening_section = _note_section(provider.prompts[0])
    assert (
        "note: 这封信里附了一条表达：「I think it is going to rain.」"
        "——回信时试着用上它。" in opening_section
    )
    assert "action_type: PERSONA_REPLY" in opening_prompt

    hint_prompt = provider.prompts[1].prompt_text
    hint_section = _note_section(provider.prompts[1])
    # The rung text comes from the validated target fixture, not the provider.
    assert "Hedge the claim so it does not sound like a fact." in hint_section
    # cs-0: no mechanism word reaches either prompt
    for word in MECHANISM_WORDS:
        assert word not in opening_prompt, word
        assert word not in hint_prompt, word
    # The prompt never carries the moment's internals.
    assert "attempt_id" not in hint_prompt
    assert "snapshot" not in hint_prompt


def test_the_resume_prompt_carries_only_the_closing_note(
    db: sqlite3.Connection,
    store: SqliteConversationStore,
    generation_store,
    conversation,
    fence: RuntimeEpochFence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """⑧/⑨ + cs-0: the resume prompt carries the neutral closing note — the
    closing reveal's form (corpus) — and no closure / outcome / reason word
    and no moment id reaches the role."""

    del conversation
    provider = RecordingProvider()
    coordinator = _coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        provider,
    )
    coordinator.request_teaching(
        TeachingRequest(
            conversation_id=CONV,
            focus_target_id=TARGET,
            client_message_id=ClientMessageId("cm-open"),
            requested_at=REQUESTED_AT,
        )
    )
    reply = coordinator.respond_to_teaching(
        TeachingReplyRequest(
            conversation_id=CONV,
            envelope=TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.SKIP
            ),
            client_message_id=ClientMessageId("cm-skip"),
            requested_at=REQUESTED_AT,
        )
    )
    assert isinstance(reply, Ok), reply
    assert reply.value.moment_state is MomentState.CLOSED
    resume_prompt = provider.prompts[-1].prompt_text
    resume_section = _note_section(provider.prompts[-1])
    # the closing reveal's form is the note (corpus content)
    assert "note: I think it is going to rain." in resume_section
    assert resume_prompt.count("[enclosed-note]") == 1
    for word in MECHANISM_WORDS:
        assert word not in resume_prompt, word


def test_the_teaching_prompt_carries_the_response_stance() -> None:
    """W-8 随迁钉（cs-0 措辞随迁）：编译产物携带固定可信节 [response]——
    存在、在 [channel] 之后、三行立场逐字（第二行已去机制词、语义逐字
    保留）、同一 request 两次 compile 字节相同。"""

    from elc.persona import (
        GenerationContext,
        GenerationContract,
        PromptCompilationRequest,
        PromptCompiler,
    )
    from elc.platform.types import (
        ConversationId,
        InteractionChannel,
        Ok,
        PersonaId,
    )
    from elc.runtime.types import GenerationActionType

    def build():
        contract = GenerationContract(
            generation_contract_id="gc-w8-pinp",
            action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
            persona_id=PersonaId("persona-w8-pinp"),
            allowed_disclosures=(),
            language_policy="follow-user",
            style_constraints=(),
        )
        context = GenerationContext(
            character_package=None,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=None,
            language_policy="follow-user",
            generation_policy="default",
            generation_contract=contract,
            ephemeral_teaching_directive=None,
        )
        return PromptCompilationRequest(
            conversation_id=ConversationId("conv-w8-pinp"),
            persona_id=PersonaId("persona-w8-pinp"),
            interaction_channel=InteractionChannel.TEXT,
            generation_context=context,
            generation_contract=contract,
        )

    block = (
        "[response]\n"
        "language: follow the user — reply in the language the user "
        "writes in (simplified Chinese by default)\n"
        "english expressions: keep an expression itself in English, "
        "exactly as given\n"
        "format: plain prose, no markdown markers (**, *, #, `, _)"
    )
    first = PromptCompiler().compile(build())
    assert isinstance(first, Ok), first
    text = first.value.prompt_text
    assert block in text
    assert text.count("[response]") == 1
    assert text.index("[response]") > text.index("[channel]")
    assert "teaching" not in text
    second = PromptCompiler().compile(build())
    assert isinstance(second, Ok), second
    assert second.value.prompt_text == text
