"""P4-3 ④ — the coordinator fills the §11 views (TASK-…19 ⑤).

docs/RUNTIME_ARCHITECTURE.md §11: Persona Runtime consumes the views and
"Orchestrator 只传结构化 view/reference，不拼 prompt" (DOMAIN_MODEL §16
D-INV-001). The coordinator holds no store and no SQL (Gate item 2), so the
views arrive through the narrow ``PersonaViewSource`` port
(elc.runtime.persona_views); this file pins what that wiring does:

- **no port** ⇒ three ``None``s and a prompt byte-identical to the pre-P4-3
  world (the optional-injection discipline the P1/P2/P3 assemblies rely on);
- **port present** ⇒ the three views reach the GenerationContext and their
  content reaches the compiled prompt;
- **a refusal or an exception is not the turn's failure** (RA §21/§19): the
  leg degrades to ``None``, the turn still replies fully, and the prompt
  simply has no such section;
- **the user leg is the assembly's** and a read for another user is refused
  rather than answered (DOMAIN_MODEL §17's isolation, one axis over);
- **the end-to-end claim**: a real chat turn's Relationship memory and
  Episode really do appear in the *next* turn's prompt — and Persona A's
  material never appears in Persona B's.
"""

from __future__ import annotations

import sqlite3

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    UserId,
)
from elc.runtime.controller import ConversationCoordinator
from elc.runtime.persona_views import ControllerPersonaViews, PersonaViewSource
from elc.user_config.types import DisclosureLevel

from .conftest import (
    CONV,
    PERSONA_A,
    PERSONA_B,
    REL_USER,
    RecordingProvider,
    commit_chat_turn,
    episode_row,
    fact,
    make_viewing_coordinator,
    memory_candidate,
    open_conversation_for,
    policy,
    profile,
    rule,
)


class _NullSource:
    """A port whose every leg answers "nothing to show" (``Ok(None)``)."""

    def __init__(self, user_id: UserId = REL_USER) -> None:
        self._user_id = user_id
        self.calls: list[str] = []

    @property
    def user_id(self) -> UserId:
        return self._user_id

    def relationship_view(self, persona_id, user_id):
        self.calls.append("relationship_view")
        return Ok(None)

    def episode_view(self, conversation_id):
        self.calls.append("episode_view")
        return Ok(None)

    def disclosed_user_profile(self, user_id, persona_id):
        self.calls.append("disclosed_user_profile")
        return Ok(None)


class _FailingSource(_NullSource):
    """A port whose legs refuse — the degradation cases."""

    def __init__(
        self,
        *,
        code: DomainErrorCode = DomainErrorCode.DEPENDENCY_UNAVAILABLE,
        explode: bool = False,
        user_id: UserId = REL_USER,
    ) -> None:
        super().__init__(user_id=user_id)
        self._code = code
        self._explode = explode
        self.seen: list[str] = []

    def _answer(self, name: str):
        self.seen.append(name)
        if self._explode:
            raise RuntimeError("view source exploded (injected)")
        return Err(DomainError(code=self._code, message="view source offline"))

    def relationship_view(self, persona_id, user_id):
        return self._answer("relationship_view")

    def episode_view(self, conversation_id):
        return self._answer("episode_view")

    def disclosed_user_profile(self, user_id, persona_id):
        return self._answer("disclosed_user_profile")


def _coordinator(
    *,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    provider,
    projections=None,
    persona_views=None,
) -> ConversationCoordinator:
    return make_viewing_coordinator(
        store,
        generation_store,
        fence,
        learning,
        decision_cycle_store,
        teaching_controller,
        target_provider,
        provider,
        projections=projections,
        persona_views=persona_views,
    )


def _prompt_of(provider: RecordingProvider) -> str:
    assert provider.prompts, "the provider was never called"
    return provider.prompts[-1].prompt_text


# -- ④ the absent port ------------------------------------------------------


def test_no_port_means_three_nones(coordinator: ConversationCoordinator) -> None:
    assert coordinator._persona_views_for(CONV, PERSONA_A) == (None, None, None)


def test_a_port_with_nothing_to_show_compiles_the_portless_prompt(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """The compatibility pin: an assembly without the port and an assembly
    whose port has nothing to show compile the *same bytes*. Two
    conversations with the same persona and the same utterance are the
    control (nothing conversation-specific is rendered when the views are
    empty)."""

    portless_provider = RecordingProvider()
    portless = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=portless_provider,
    )
    first = open_conversation_for(store, "conv-null-a", PERSONA_A)
    commit_chat_turn(portless, "cm-null-a", "I live in Berlin.", 1, conversation=first)

    null_source = _NullSource()
    ported_provider = RecordingProvider()
    ported = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=ported_provider,
        persona_views=null_source,
    )
    second = open_conversation_for(store, "conv-null-b", PERSONA_A)
    commit_chat_turn(ported, "cm-null-b", "I live in Berlin.", 1, conversation=second)

    assert null_source.calls == [
        "relationship_view",
        "episode_view",
        "disclosed_user_profile",
    ]
    assert ported_provider.prompt_texts == portless_provider.prompt_texts
    text = ported_provider.prompt_texts[0]
    assert "[profile]" not in text
    assert "[relationship]" not in text
    assert "[episode]" not in text


# -- ④ the degradation cases ------------------------------------------------


def test_a_refusing_view_leg_never_fails_the_turn(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    source = _FailingSource()
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        persona_views=source,
    )
    conversation = open_conversation_for(store, "conv-refuse", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-refuse", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    assert source.seen == [
        "relationship_view",
        "episode_view",
        "disclosed_user_profile",
    ]
    text = _prompt_of(provider)
    # The turn really ran: its own utterance is in the history section, and
    # it produced a reply.
    assert "#1 user: I live in Berlin." in text
    assert turn.reply_text
    assert "[profile]" not in text and "[relationship]" not in text


def test_an_exploding_view_leg_never_fails_the_turn(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    source = _FailingSource(explode=True)
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        persona_views=source,
    )
    conversation = open_conversation_for(store, "conv-boom", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-boom", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    assert "[episode]" not in _prompt_of(provider)


def test_an_exploding_user_id_property_never_fails_the_turn(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """Review LOW-1: the port's ``user_id`` property is a *read* like the
    three legs, and it happens after the transcript is already durable — so
    it lives inside the same guard. An unguarded raise would have travelled
    out of ``begin_turn``, which is exactly what the module promises cannot
    happen ("every read is best-effort … the turn proceeds")."""

    class _ExplodingUserSource(_NullSource):
        @property
        def user_id(self) -> UserId:
            raise RuntimeError("user scope exploded (injected)")

    source = _ExplodingUserSource()
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        persona_views=source,
    )
    conversation = open_conversation_for(store, "conv-uid", PERSONA_A)
    turn = commit_chat_turn(
        coordinator, "cm-uid", "I live in Berlin.", 1, conversation=conversation
    )
    assert turn.outcome == "REPLIED_FULL"
    # No leg was asked (there is no user to ask for), and the whole set
    # degraded together.
    assert source.calls == []
    assert coordinator._persona_views_for(conversation, PERSONA_A) == (
        None,
        None,
        None,
    )
    text = _prompt_of(provider)
    assert "#1 user: I live in Berlin." in text  # the turn really ran


def test_an_unavailable_leg_is_none_and_not_an_error(
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        persona_views=_FailingSource(),
    )
    assert coordinator._persona_views_for(CONV, PERSONA_A) == (None, None, None)


# -- ④ the user leg ---------------------------------------------------------


def test_the_composition_serves_one_user(
    relationship_controller, episode_store, user_config_controller
) -> None:
    views = ControllerPersonaViews(
        relationship=relationship_controller,
        episodes=episode_store,
        user_config=user_config_controller,
        user_id=REL_USER,
    )
    assert isinstance(views, PersonaViewSource)
    assert views.user_id == REL_USER
    assert isinstance(views.relationship_view(PERSONA_A, REL_USER), Ok)
    assert isinstance(views.episode_view(CONV), Ok)
    assert isinstance(views.disclosed_user_profile(REL_USER, PERSONA_A), Ok)


def test_a_read_for_another_user_is_refused(
    relationship_controller, episode_store, user_config_controller
) -> None:
    """Answering it would mean reading another user's rows through a source
    configured for this one (DOMAIN_MODEL §17, one axis over)."""

    views = ControllerPersonaViews(
        relationship=relationship_controller,
        episodes=episode_store,
        user_config=user_config_controller,
        user_id=REL_USER,
    )
    other = UserId("user-2")
    for outcome in (
        views.relationship_view(PERSONA_A, other),
        views.disclosed_user_profile(other, PERSONA_A),
    ):
        assert isinstance(outcome, Err)
        assert outcome.error.code is DomainErrorCode.VALIDATION_FAILED
        assert str(REL_USER) in outcome.error.message
    # The episode leg has no user axis at all (a conversation, one projection)
    # — pinned so nobody "adds" one later without noticing this test.
    assert isinstance(views.episode_view(CONV), Ok)


def test_the_coordinator_passes_the_sources_own_user(
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
) -> None:
    """The orchestrator never invents a user: it hands back what the port
    says it serves, and the port is what refuses a mismatch."""

    class _RecordingSource(_NullSource):
        def __init__(self) -> None:
            super().__init__()
            self.asked: list[tuple[str, object]] = []

        def relationship_view(self, persona_id, user_id):
            self.asked.append(("relationship_view", user_id))
            return super().relationship_view(persona_id, user_id)

    source = _RecordingSource()
    provider = RecordingProvider()
    coordinator = _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        persona_views=source,
    )
    conversation = open_conversation_for(store, "conv-user", PERSONA_A)
    commit_chat_turn(coordinator, "cm-user", "Hello.", 1, conversation=conversation)
    assert source.asked == [("relationship_view", REL_USER)]


# -- ④ the end-to-end claim -------------------------------------------------


def _live_coordinator(
    *,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    projection_runtime,
    persona_views,
    provider,
) -> ConversationCoordinator:
    return _coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        provider=provider,
        projections=projection_runtime,
        persona_views=persona_views,
    )


def test_a_real_turn_fills_the_next_turns_prompt(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    projection_runtime,
    persona_views,
    user_config_controller,
    scripted_candidates,
) -> None:
    """The whole Phase-4 promise in one flow: a canonical chat turn writes a
    Relationship memory and an Episode, and the *next* turn's prompt carries
    both — through the real stores, the real projections and the real
    PromptCompiler."""

    conversation = open_conversation_for(store, "conv-e2e", PERSONA_A)
    scripted_candidates.candidates = (
        memory_candidate("The user lives in Berlin."),
    )
    assert isinstance(
        user_config_controller.set_disclosure_policy(
            policy(rule(DisclosureLevel.RICH, PERSONA_A))
        ),
        Ok,
    )
    assert isinstance(
        user_config_controller.upsert_user_profile(
            profile(fact("the user lives in Berlin")), explicit_consent=False
        ),
        Ok,
    )
    provider = RecordingProvider()
    coordinator = _live_coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        projection_runtime=projection_runtime,
        persona_views=persona_views,
        provider=provider,
    )
    first = commit_chat_turn(
        coordinator, "cm-e2e-1", "I live in Berlin.", 1, conversation=conversation
    )
    assert first.outcome == "REPLIED_FULL"
    prompt_after_first = _prompt_of(provider)
    # Turn 1 ran before anything was projected, so its own prompt cannot
    # carry this turn's memory (the projection runs after the turn).
    assert "USER_STATED_FACT: The user lives in Berlin." not in prompt_after_first
    # … but it does carry the disclosure view (written before the turn).
    assert "[profile]" in prompt_after_first
    assert "the user lives in Berlin" in prompt_after_first

    # The episode the first turn's projection landed — the row turn 2's
    # prompt will render.
    episode_before_second = episode_row(db, conversation)

    second = commit_chat_turn(
        coordinator, "cm-e2e-2", "I read every evening.", 2, conversation=conversation
    )
    assert second.outcome == "REPLIED_FULL"
    prompt = _prompt_of(provider)

    # The relationship section carries the memory the first turn produced.
    assert "[relationship]" in prompt
    assert "USER_STATED_FACT: The user lives in Berlin." in prompt
    # The episode section carries the transcript-derived summary of turn 1.
    assert "[episode]" in prompt
    assert "I live in Berlin." in prompt
    assert episode_before_second[2] in prompt  # the version at compile time
    assert str(episode_before_second[0]) in prompt  # … and its id
    # The episode's durable stamp is not in the prompt (the P3-0 rule), and
    # the projection moved after turn 2 (a second, different version).
    assert str(episode_before_second[9]) not in prompt
    assert episode_row(db, conversation)[2] != episode_before_second[2]


def test_the_next_turn_prompt_keeps_persona_a_out_of_persona_b(
    db: sqlite3.Connection,
    store,
    generation_store,
    fence,
    learning,
    decision_cycle_store,
    teaching_controller,
    target_provider,
    projection_runtime,
    persona_views,
    scripted_candidates,
) -> None:
    """VAL-…72 ③'s isolation rule, seen from the prompt: two personas over
    one user, two conversations, and neither prompt contains the other's
    material."""

    conversation_a = open_conversation_for(store, "conv-e2e-a", PERSONA_A)
    conversation_b = open_conversation_for(store, "conv-e2e-b", PERSONA_B)
    scripted_candidates.candidates = (memory_candidate("A-only memory."),)
    provider_a = RecordingProvider()
    coordinator_a = _live_coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        projection_runtime=projection_runtime,
        persona_views=persona_views,
        provider=provider_a,
    )
    commit_chat_turn(
        coordinator_a, "cm-e2e-a1", "I live in Berlin.", 1, conversation=conversation_a
    )
    commit_chat_turn(
        coordinator_a,
        "cm-e2e-a2",
        "I read every evening.",
        2,
        conversation=conversation_a,
    )
    prompt_a = _prompt_of(provider_a)
    assert "A-only memory." in prompt_a

    scripted_candidates.candidates = (memory_candidate("B-only memory."),)
    provider_b = RecordingProvider()
    coordinator_b = _live_coordinator(
        store=store,
        generation_store=generation_store,
        fence=fence,
        learning=learning,
        decision_cycle_store=decision_cycle_store,
        teaching_controller=teaching_controller,
        target_provider=target_provider,
        projection_runtime=projection_runtime,
        persona_views=persona_views,
        provider=provider_b,
    )
    commit_chat_turn(
        coordinator_b, "cm-e2e-b1", "I play the drums.", 1, conversation=conversation_b
    )
    prompt_b = _prompt_of(provider_b)

    assert f"persona_id: {PERSONA_B}" in prompt_b
    for leaked in ("A-only memory.", str(PERSONA_A), "I live in Berlin."):
        assert leaked not in prompt_b
    for leaked in ("B-only memory.", str(PERSONA_B), "I play the drums."):
        assert leaked not in prompt_a
