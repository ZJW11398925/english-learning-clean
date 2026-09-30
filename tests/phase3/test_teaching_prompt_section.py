"""VAL ⑨ — the ``[teaching]`` prompt section is Persona-owned, versioned and
byte-deterministic (P3-1B).

DOMAIN_MODEL §11/§14: Teaching produces an ``EphemeralTeachingDirective`` —
never a persona prompt — and the Persona Runtime's PromptCompiler owns the
final prompt. The projection from the directive to the persona-owned
``TeachingPromptView`` happens in the orchestrator (the one place that knows
both packages; the AST pin forbids either domain importing the other).

What is pinned here:

- the section renders ``[teaching]`` with the keys of
  ``TEACHING_PROMPT_KEY_ORDER`` in exactly that order and its template
  version inside the section, so a stored prompt says which template
  produced it;
- the whole prompt is byte-deterministic (same view → same bytes) and the
  section order is ``persona → contract → history → teaching → channel``;
- the provider only ever receives the phase / support the Teaching domain
  stamped (it never picks a ladder rung), and a resume prompt carries the
  narrow ``ResumeDirective`` fields — no attempt ids, no snapshot, no
  ladder internals.
"""

from __future__ import annotations

import sqlite3

from elc.conversation import SqliteConversationStore
from elc.persona import PromptCompiler, ScriptedPersonaProvider
from elc.persona.commands import PROMPT_SECTION_ORDER
from elc.persona.types import (
    TEACHING_PROMPT_KEY_ORDER,
    TEACHING_PROMPT_SECTION_VERSION,
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


def _section(prompt: CompiledPrompt) -> str:
    text = prompt.prompt_text
    start = text.index("[teaching]")
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
        generation_contract_id="gc-teaching-hint",
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
    section = _section(compiled.value)
    assert section.startswith("[teaching]\nprompt_version: ")
    assert f"prompt_version: {TEACHING_PROMPT_SECTION_VERSION}" in section
    keys = [line.split(": ", 1)[0] for line in section.splitlines()[1:]]
    assert keys == list(TEACHING_PROMPT_KEY_ORDER)
    # Byte-determinism: the same view compiles to exactly the same bytes.
    again = compiler.compile(request)
    assert isinstance(again, Ok)
    assert again.value.prompt_text == compiled.value.prompt_text
    # P4-3 semantic sync (TASK-OPI-4d516e4f.19 ④): the order this test pins
    # is the same declared constant it always pinned — P4-3 inserted the
    # three §11 views Persona Runtime consumes (profile / relationship /
    # episode) at their stated positions. The teaching section keeps its
    # place relative to persona/contract/history/channel; only the three new
    # sections are added. Nothing was removed.
    assert PROMPT_SECTION_ORDER == (
        "persona",
        "profile",
        "contract",
        "history",
        "relationship",
        "episode",
        "teaching",
        "channel",
    )


def test_the_delivered_teaching_prompt_carries_the_domains_own_stage(
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

    opening_section = _section(provider.prompts[0])
    assert "action_type: TEACHING_OPEN" in opening_section
    assert "presentation_phase: INITIAL_PROMPT" in opening_section
    assert f"moment_id: {opened.value.moment_id}" in opening_section

    hint_section = _section(provider.prompts[1])
    assert "action_type: TEACHING_HINT" in hint_section
    assert "presentation_phase: HINT_SEMANTIC" in hint_section
    assert "support_level: SEMANTIC_HINT" in hint_section
    # The rung text comes from the validated target fixture, not the provider.
    assert "Hedge the claim so it does not sound like a fact." in hint_section
    # The prompt never carries the moment's internals.
    assert "attempt_id" not in provider.prompts[1].prompt_text
    assert "snapshot" not in provider.prompts[1].prompt_text


def test_the_resume_prompt_carries_only_the_resume_directive(
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
    """⑧/⑨: the resume action is rendered from a ResumeDirective — the closed
    episode's outcome/reason and its focus target, nothing else."""

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
    assert isinstance(opened, Ok)
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
    resume_section = _section(provider.prompts[-1])
    assert "action_type: PERSONA_RESUME" in resume_section
    assert "closure: USER_SKIP" in resume_section
    assert "abort_reason: USER_SKIP" in resume_section
    assert f"moment_id: {opened.value.moment_id}" in resume_section
    # No ladder internals leaked into the resume message: every ladder field
    # is present-but-empty (the section's shape never depends on which
    # optional fields are set), and the reveal shown here is the *closing*
    # reveal of the episode, not a hint rung.
    assert "hint: \n" in resume_section
    assert "explanation: \n" in resume_section
    assert provider.prompts[-1].prompt_text.count("[teaching]") == 1


def test_the_teaching_prompt_carries_the_response_stance() -> None:
    """W-8 随迁钉：编译产物携带固定可信节 [response]——存在、在
    [channel] 之后、三行立场逐字、同一 request 两次 compile 字节相同。"""

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
        "teaching expressions: keep a taught expression itself in "
        "English, exactly as given\n"
        "format: plain prose, no markdown markers (**, *, #, `, _)"
    )
    first = PromptCompiler().compile(build())
    assert isinstance(first, Ok), first
    text = first.value.prompt_text
    assert block in text
    assert text.count("[response]") == 1
    assert text.index("[response]") > text.index("[channel]")
    second = PromptCompiler().compile(build())
    assert isinstance(second, Ok), second
    assert second.value.prompt_text == text
