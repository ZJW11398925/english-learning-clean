"""VAL ③ — the canonical §5.1 CharacterPackage fixture enters the normal
chain (P3-0 ③).

Pins:
- the persona domain's record carries the DATA_MODEL §5.1:235-256 column
  set exactly, and ``sample_character_package`` supplies a deterministic
  real-shaped instance;
- PromptCompiler consumes the package fields (same request + different
  packages → different prompts; every consumed field is visible in the
  text — nothing is silently dropped);
- ConversationCoordinator's normal path carries a non-None package end
  to end (the provider-observed request hash changes with the package,
  the turn still completes REPLIED_FULL), while ``character_package=None``
  keeps the pre-P3 assembly.
"""

from __future__ import annotations

import sqlite3
from dataclasses import fields

from elc.conversation import SqliteConversationStore
from elc.persona import (
    GenerationContext,
    PromptCompilationRequest,
    PromptCompiler,
    ScriptedPersonaProvider,
    sample_character_package,
)
from elc.persona.types import CharacterPackageRecord
from elc.platform.db import connection, epoch, migrations
from elc.platform.db.generation_store import SqliteGenerationStore
from elc.platform.types import (
    CharacterPackageId,
    ConversationId,
    InteractionChannel,
    Ok,
    PersonaId,
    UserId,
)

from .conftest import begin_turn_ok, make_coordinator, make_lease

# DATA_MODEL §5.1:235-256 verbatim column list.
CHARACTER_PACKAGE_COLUMNS = [
    "character_package_id",
    "persona_id",
    "revision",
    "identity",
    "personality",
    "background",
    "speech_style",
    "values",
    "boundaries",
    "opening",
    "scenario",
    "generation_policy",
    "lore_refs",
    "status",
    "updated_at",
]


def test_character_package_record_matches_canonical_column_set() -> None:
    names = [field.name for field in fields(CharacterPackageRecord)]
    assert names == CHARACTER_PACKAGE_COLUMNS


def test_sample_package_is_real_shaped_and_deterministic() -> None:
    first = sample_character_package()
    second = sample_character_package()
    assert first == second  # fixed values — no clock, no randomness
    assert first.character_package_id == CharacterPackageId(
        "cpkg-sample-maya"
    )
    assert first.revision == 1
    assert first.identity
    assert first.personality
    assert first.background
    assert first.speech_style
    assert first.values
    assert first.boundaries
    assert first.opening
    assert first.scenario
    assert first.generation_policy
    assert first.lore_refs  # lore_refs[] is carried, not dropped
    assert first.status == "ACTIVE"
    assert first.updated_at

    # Every keyword override reaches the record (a real fixture builder,
    # not a constant echo).
    overridden = sample_character_package(
        personality="dry and precise", lore_refs=("lore-x",)
    )
    assert overridden.personality == "dry and precise"
    assert overridden.lore_refs == ("lore-x",)


def _request(persona_id: PersonaId) -> PromptCompilationRequest:
    context = GenerationContext(
        character_package=None,
        relationship_view=None,
        episode_view=None,
        world_lore_view=None,
        disclosed_user_profile=None,
        conversation_window=None,
        language_policy="default",
        generation_policy="default",
    )
    return PromptCompilationRequest(
        conversation_id=ConversationId("conv-pkg"),
        persona_id=persona_id,
        interaction_channel=InteractionChannel.TEXT,
        generation_context=context,
    )


def _request_with_package(
    package: CharacterPackageRecord,
) -> PromptCompilationRequest:
    request = _request(package.persona_id)
    return PromptCompilationRequest(
        conversation_id=request.conversation_id,
        persona_id=request.persona_id,
        interaction_channel=request.interaction_channel,
        generation_context=GenerationContext(
            character_package=package,
            relationship_view=None,
            episode_view=None,
            world_lore_view=None,
            disclosed_user_profile=None,
            conversation_window=None,
            language_policy="default",
            generation_policy="default",
        ),
    )


def test_prompt_compiler_consumes_package_fields_not_ignores_them() -> None:
    """Same request, different packages → different prompts; each §5.1
    character field is visible in the compiled text."""

    compiler = PromptCompiler()
    maya = sample_character_package()
    quiet = sample_character_package(
        character_package_id="cpkg-quiet",
        persona_id="persona-quiet",
        identity="a quiet night-shift librarian",
        personality="dry and precise",
        speech_style="formal English, long clauses",
        opening="Good evening. The reading room is open.",
        scenario="late shift at the city library",
        lore_refs=("lore-library",),
    )

    prompt_maya = compiler.compile(_request_with_package(maya))
    prompt_quiet = compiler.compile(_request_with_package(quiet))
    assert isinstance(prompt_maya, Ok) and isinstance(prompt_quiet, Ok)

    # Different packages → different prompts (the review counterexample:
    # a package that is carried but ignored would fail this).
    assert prompt_maya.value.prompt_text != prompt_quiet.value.prompt_text

    text = prompt_maya.value.prompt_text
    for fragment in (
        f"character_package_id: {maya.character_package_id}",
        f"persona_id: {maya.persona_id}",
        f"revision: {maya.revision}",
        f"identity: {maya.identity}",
        f"personality: {maya.personality}",
        f"background: {maya.background}",
        f"speech_style: {maya.speech_style}",
        f"values: {maya.values}",
        f"boundaries: {maya.boundaries}",
        f"opening: {maya.opening}",
        f"scenario: {maya.scenario}",
        f"generation_policy: {maya.generation_policy}",
        f"lore_refs: {'; '.join(maya.lore_refs)}",
        "language_policy: default",
    ):
        assert fragment in text, fragment

    # Determinism is preserved with a package present (byte-identical
    # re-compile; lifecycle fields status/updated_at stay OUT of the
    # prompt, so no hidden clock rides the text).
    repeat = compiler.compile(_request_with_package(maya))
    assert isinstance(repeat, Ok)
    assert repeat.value.prompt_text == prompt_maya.value.prompt_text
    assert "updated_at" not in text
    assert "ACTIVE" not in text  # status is lifecycle, not prompt content

    # None keeps the pre-P3 fallback section (P1 behavior unchanged).
    bare = compiler.compile(_request(PersonaId("persona-default")))
    assert isinstance(bare, Ok)
    assert bare.value.prompt_text.startswith("[persona]\npersona_id:")


def _fresh_world(
    package: CharacterPackageRecord | None,
) -> tuple[ScriptedPersonaProvider, ConversationId]:
    """An isolated single-turn world whose coordinator carries ``package``
    (fresh db + stores + conversation; the P3-0 assembly face)."""

    conn = connection.connect(":memory:")
    migrations.apply_migrations(conn)
    fence = epoch.open_runtime_epoch(conn)
    conv_store = SqliteConversationStore(conn, fence)
    gen_store = SqliteGenerationStore(conn, fence)
    opened = conv_store.open_conversation(
        ConversationId("conv-pkg-chain"),
        user_id=UserId("user-1"),
        persona_id=None,
        scene_id=None,
    )
    assert isinstance(opened, Ok)
    provider = ScriptedPersonaProvider()
    coordinator = make_coordinator(
        conv_store, gen_store, make_lease(fence), provider, package
    )
    begin_turn_ok(coordinator, opened.value, "cm-pkg-a", "hello there")
    return provider, opened.value


def test_coordinator_normal_path_carries_the_package_end_to_end(
    store,
    generation_store,
    fence,
    conversation,
) -> None:
    """The injected package travels the normal chain: begin_turn →
    GenerationContext.character_package → PromptCompiler → provider call.
    The provider-observed request hash differs per package; the same
    package on the same first-turn history compiles byte-identically."""

    provider_a = ScriptedPersonaProvider()
    coordinator_a = make_coordinator(
        store,
        generation_store,
        make_lease(fence),
        provider_a,
        sample_character_package(),
    )
    completion = begin_turn_ok(
        coordinator_a, conversation, "cm-pkg-a", "hello there"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert completion.assistant_turn_id is not None
    assert len(provider_a.calls) == 1

    maya = sample_character_package()
    quiet = sample_character_package(
        character_package_id="cpkg-quiet",
        persona_id="persona-quiet",
        personality="dry and precise",
    )

    # Isolated worlds with identical single-turn history: same package →
    # same request hash; different package → different request hash (the
    # only varying input is the package).
    provider_maya, _ = _fresh_world(maya)
    provider_quiet, _ = _fresh_world(quiet)

    assert provider_maya.calls[0] == provider_a.calls[0]
    assert provider_quiet.calls[0] != provider_maya.calls[0]


def test_none_injection_keeps_the_pre_p3_assembly(
    store,
    generation_store,
    fence,
    conversation,
    db: sqlite3.Connection,
) -> None:
    """character_package=None (the default) keeps the Phase 1/2 loop:
    the turn completes normally and exactly one canonical assistant turn
    lands in the transcript."""

    provider = ScriptedPersonaProvider()
    coordinator = make_coordinator(
        store, generation_store, make_lease(fence), provider, None
    )
    completion = begin_turn_ok(
        coordinator, conversation, "cm-pkg-none", "still the old loop"
    )
    assert completion.outcome == "REPLIED_FULL"
    assert len(provider.calls) == 1

    window = store.get_conversation_window(conversation, 1)
    assert isinstance(window, Ok)
    assert window.value.slices[0].assistant_turn is not None
    rows = db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()
    assert rows is not None and rows[0] == 1
