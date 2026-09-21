"""P4-3 ③ — the PromptCompiler consumes the three §11 views (TASK-…19 ④).

docs/RUNTIME_ARCHITECTURE.md §11 lists the views Persona Runtime consumes
(CharacterPackage / RelationshipView / EpisodeView / WorldLoreView /
DisclosedUserProfile / ConversationWindow); §24.3 pins the disclosure half
("PromptCompiler/Provider adapter 只能消费 action-specific disclosure
view"). What is asserted here:

- the section order is the declared constant, and the compiled text really
  renders the sections in it;
- each of the three new sections is versioned and renders its version key
  first (the ``[teaching]`` precedent: a stored prompt says which template
  produced it);
- two compilations of the same views are byte-identical, and absent views
  produce exactly the pre-P4-3 prompt (no empty sections, no drift);
- ``updated_at`` never reaches the prompt (the view has no such field, and
  the durable stamp is not rendered under any other key);
- Persona A's material cannot appear in Persona B's prompt, in either
  direction — the isolation is structural (the views are scope-bound reads),
  and this is the test that would catch a compiler that re-used one view for
  the other persona.
"""

from __future__ import annotations

from elc.conversation.types import ConversationStatus
from elc.persona.commands import PROMPT_SECTION_ORDER, PromptCompiler
from elc.persona.types import (
    EPISODE_PROMPT_KEY_ORDER,
    EPISODE_PROMPT_SECTION_VERSION,
    PROFILE_PROMPT_KEY_ORDER,
    PROFILE_PROMPT_SECTION_VERSION,
    RELATIONSHIP_PROMPT_KEY_ORDER,
    RELATIONSHIP_PROMPT_SECTION_VERSION,
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
)
from elc.platform.types import (
    ConversationId,
    EpisodeId,
    InteractionChannel,
    Ok,
    PersonaId,
    RelationshipMemoryId,
    UserId,
)
from elc.relationship.episode import EpisodeView
from elc.relationship.types import (
    MemoryProvenance,
    MemoryStatus,
    RelationshipMemoryRecord,
    RelationshipMemoryType,
    RelationshipView,
)
from elc.runtime.types import GenerationActionType
from elc.user_config.types import DisclosedUserProfile, DisclosureLevel

PERSONA_A = PersonaId("persona-a")
PERSONA_B = PersonaId("persona-b")
USER = UserId("user-1")
CONVERSATION = ConversationId("conv-prompt")

A_MEMORY = "The user told Maya they live in Berlin."
B_MEMORY = "The user told Ben they play the drums."
A_THREAD = "ask about the Berlin move"
B_THREAD = "ask about the drum kit"
A_FACT = "the user lives in Berlin"
B_FACT = "the user plays the drums"
SECRET_FACT = "the user is quietly leaving their job"
EPISODE_STAMP = "2026-09-21T12:34:56.789012+00:00"


def _memory(memory_id: str, content: str) -> RelationshipMemoryRecord:
    return RelationshipMemoryRecord(
        relationship_memory_id=RelationshipMemoryId(memory_id),
        persona_id=PERSONA_A,
        user_id=USER,
        memory_type=RelationshipMemoryType.USER_STATED_FACT,
        provenance=MemoryProvenance.USER_STATED_FACT,
        canonical_content=content,
        source_turn_id=None,
        status=MemoryStatus.ACTIVE,
        created_at=EPISODE_STAMP,
        updated_at=EPISODE_STAMP,
    )


def _relationship_view(persona_id: PersonaId, *contents: str) -> RelationshipView:
    return RelationshipView(
        persona_id=persona_id,
        user_id=USER,
        active_memories=tuple(
            _memory(f"rm-{persona_id}-{index}", content)
            for index, content in enumerate(contents, start=1)
        ),
    )


def _episode_view(*threads: str) -> EpisodeView:
    return EpisodeView(
        episode_id=EpisodeId("ep-conv-prompt"),
        version="epv-0123456789abcdef0123",
        summary="I live in Berlin. / I read every evening.",
        open_threads=threads,
        recent_events=("#1 [turn-1] user: hi | assistant: hey | outcome: —",),
        status=ConversationStatus.ACTIVE,
    )


def _profile(persona_id: PersonaId, *facts: str, level=DisclosureLevel.RICH):
    return DisclosedUserProfile(
        persona_id=persona_id, disclosure_level=level, disclosed_facts=facts
    )


def _request(
    *,
    relationship=None,
    episode=None,
    disclosed=None,
    persona_id: PersonaId = PERSONA_A,
) -> PromptCompilationRequest:
    contract = GenerationContract(
        generation_contract_id="gc-normal-persona-reply",
        action_type=GenerationActionType.NORMAL_PERSONA_REPLY,
        persona_id=persona_id,
        allowed_disclosures=(),
        language_policy="default",
        style_constraints=(),
    )
    return PromptCompilationRequest(
        conversation_id=CONVERSATION,
        persona_id=persona_id,
        interaction_channel=InteractionChannel.TEXT,
        generation_context=GenerationContext(
            character_package=None,
            relationship_view=relationship,
            episode_view=episode,
            world_lore_view=None,
            disclosed_user_profile=disclosed,
            conversation_window=None,
            language_policy="default",
            generation_policy="default",
            generation_contract=contract,
            ephemeral_teaching_directive=None,
        ),
        generation_contract=contract,
    )


def _compile(request: PromptCompilationRequest) -> str:
    compiled = PromptCompiler().compile(request)
    assert isinstance(compiled, Ok), compiled
    return compiled.value.prompt_text


def _section(text: str, name: str) -> str:
    """The rendered ``[name]`` section (its header line through the last
    line before the next header)."""

    blocks = text.split("\n\n")
    for block in blocks:
        if block.startswith(f"[{name}]\n"):
            return block
    raise AssertionError(f"no [{name}] section in prompt:\n{text}")


def _keys(section: str) -> list[str]:
    return [line.split(": ", 1)[0] for line in section.splitlines()[1:]]


# -- ③ the section order ----------------------------------------------------


def test_the_declared_section_order_is_the_compiled_order() -> None:
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
    text = _compile(
        _request(
            relationship=_relationship_view(PERSONA_A, A_MEMORY),
            episode=_episode_view(A_THREAD),
            disclosed=_profile(PERSONA_A, A_FACT),
        )
    )
    rendered = [
        line[1:-1]
        for line in text.splitlines()
        if line.startswith("[") and line.endswith("]")
    ]
    # Every section present is rendered in the declared order (profile and
    # the two Phase-4 views are here; teaching is absent — no directive).
    assert rendered == [
        "persona",
        "profile",
        "contract",
        "relationship",
        "episode",
        "channel",
    ]
    assert rendered == [
        name for name in PROMPT_SECTION_ORDER if name in set(rendered)
    ]


def test_absent_views_produce_exactly_the_pre_p4_3_prompt() -> None:
    bare = _compile(_request())
    assert "[profile]" not in bare
    assert "[relationship]" not in bare
    assert "[episode]" not in bare
    # Explicitly passing None is the same request (the coordinator's
    # best-effort read collapses to this).
    assert _compile(_request(relationship=None, episode=None, disclosed=None)) == bare


# -- ③ the versions and the key orders --------------------------------------


def test_each_new_section_is_versioned_and_renders_its_version_first() -> None:
    text = _compile(
        _request(
            relationship=_relationship_view(PERSONA_A, A_MEMORY),
            episode=_episode_view(A_THREAD),
            disclosed=_profile(PERSONA_A, A_FACT),
        )
    )
    for name, version in (
        ("profile", PROFILE_PROMPT_SECTION_VERSION),
        ("relationship", RELATIONSHIP_PROMPT_SECTION_VERSION),
        ("episode", EPISODE_PROMPT_SECTION_VERSION),
    ):
        section = _section(text, name)
        assert section.startswith(f"[{name}]\nprompt_version: ")
        assert section.splitlines()[1] == f"prompt_version: {version}"


def test_the_section_versions_are_pinned() -> None:
    assert PROFILE_PROMPT_SECTION_VERSION == "profile-prompt-v1"
    assert RELATIONSHIP_PROMPT_SECTION_VERSION == "relationship-prompt-v1"
    assert EPISODE_PROMPT_SECTION_VERSION == "episode-prompt-v1"


def test_each_section_renders_the_pinned_key_order() -> None:
    text = _compile(
        _request(
            relationship=_relationship_view(PERSONA_A, A_MEMORY),
            episode=_episode_view(A_THREAD),
            disclosed=_profile(PERSONA_A, A_FACT),
        )
    )
    assert _keys(_section(text, "profile")) == list(PROFILE_PROMPT_KEY_ORDER)
    assert _keys(_section(text, "relationship")) == list(
        RELATIONSHIP_PROMPT_KEY_ORDER
    )
    assert _keys(_section(text, "episode")) == list(EPISODE_PROMPT_KEY_ORDER)


def test_two_compilations_of_the_same_views_are_byte_identical() -> None:
    request = _request(
        relationship=_relationship_view(PERSONA_A, A_MEMORY),
        episode=_episode_view(A_THREAD, "another thread"),
        disclosed=_profile(PERSONA_A, A_FACT, level=DisclosureLevel.RICH),
    )
    first = _compile(request)
    second = _compile(request)
    assert first == second
    # Sanity: the sections are joined with a blank line, so the assertions
    # above are reading real section boundaries.
    assert "\n\n[profile]\n" in first


# -- ③ what each section renders --------------------------------------------


def test_the_relationship_section_renders_the_active_memories_in_order() -> None:
    text = _compile(
        _request(
            relationship=_relationship_view(PERSONA_A, "first memory", "second memory")
        )
    )
    section = _section(text, "relationship")
    assert f"persona_id: {PERSONA_A}" in section
    assert f"user_id: {USER}" in section
    assert section.splitlines()[-1] == (
        "memories: USER_STATED_FACT: first memory;"
        " USER_STATED_FACT: second memory"
    )


def test_the_profile_section_renders_only_what_was_disclosed() -> None:
    """The withheld fact is not in the request at all — the disclosure view
    is the only profile shape the compiler ever sees — so it cannot be
    rendered even by accident."""

    text = _compile(
        _request(disclosed=_profile(PERSONA_A, A_FACT, level=DisclosureLevel.MINIMAL))
    )
    section = _section(text, "profile")
    assert A_FACT in section
    assert SECRET_FACT not in text
    assert "disclosure_level: MINIMAL" in section
    assert f"persona_id: {PERSONA_A}" in section


def test_the_episode_section_renders_the_content_columns() -> None:
    text = _compile(
        _request(episode=_episode_view(A_THREAD, B_THREAD))
    )
    section = _section(text, "episode")
    assert "episode_id: ep-conv-prompt" in section
    assert "version: epv-0123456789abcdef0123" in section
    assert "status: ACTIVE" in section
    assert "summary: I live in Berlin. / I read every evening." in section
    assert f"open_threads: {A_THREAD}; {B_THREAD}" in section
    assert "recent_events: #1 [turn-1] user: hi | assistant: hey | outcome: —" in (
        section
    )


def test_the_episode_section_never_carries_updated_at() -> None:
    """The durable stamp is lifecycle metadata: the view has no such field,
    and no key of the section renders one."""

    text = _compile(
        _request(
            relationship=_relationship_view(PERSONA_A, A_MEMORY),
            episode=_episode_view(A_THREAD),
        )
    )
    assert "updated_at" not in text
    assert EPISODE_STAMP not in text
    episode_keys = _keys(_section(text, "episode"))
    assert "updated_at" not in episode_keys
    # The memory row's own stamps are not rendered either (the view carries
    # the record, and the section renders type + content only).
    relationship_section = _section(text, "relationship")
    assert EPISODE_STAMP not in relationship_section


# -- ③ isolation ------------------------------------------------------------


def test_persona_a_material_never_appears_in_persona_bs_prompt() -> None:
    prompt_a = _compile(
        _request(
            relationship=_relationship_view(PERSONA_A, A_MEMORY),
            episode=_episode_view(A_THREAD),
            disclosed=_profile(PERSONA_A, A_FACT),
            persona_id=PERSONA_A,
        )
    )
    prompt_b = _compile(
        _request(
            relationship=_relationship_view(PERSONA_B, B_MEMORY),
            episode=_episode_view(B_THREAD),
            disclosed=_profile(PERSONA_B, B_FACT),
            persona_id=PERSONA_B,
        )
    )
    assert A_MEMORY in prompt_a and B_MEMORY in prompt_b
    for leaked in (A_MEMORY, A_THREAD, A_FACT, str(PERSONA_A)):
        assert leaked not in prompt_b
    for leaked in (B_MEMORY, B_THREAD, B_FACT, str(PERSONA_B)):
        assert leaked not in prompt_a
    assert prompt_a != prompt_b


def test_a_prompt_without_the_views_carries_no_persona_material() -> None:
    """The positive control for the isolation pin: remove the views and the
    material is simply not there (nothing is smuggled through another
    section)."""

    text = _compile(_request())
    for absent in (A_MEMORY, A_THREAD, A_FACT):
        assert absent not in text
