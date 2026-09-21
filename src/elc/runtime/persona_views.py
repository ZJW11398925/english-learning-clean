"""The persona-facing view port — how the orchestrator fills a GenerationContext.

docs/RUNTIME_ARCHITECTURE.md §11 names the views Persona Runtime consumes and
states the orchestrator's duty: "Orchestrator 只传结构化 view/reference，不拼
prompt" (DOMAIN_MODEL §16 D-INV-001: the orchestrator owns sequencing, not
truth). This module is that duty's runtime half: a narrow port the coordinator
asks for the three Phase-4 views, plus one composition over the domain faces
that supply them.

**Why a port at all.** Gate item 2 keeps ``elc.runtime`` free of SQL and of
``elc.platform.db``, and the views live behind three different domain faces
(RelationshipController, the Episode store's read face, UserConfigController).
A port keeps the coordinator's constructor honest — one optional dependency,
structural typing, no domain import — and keeps the wiring decision in the
assembly (the P4-2 ``projections`` port precedent).

**User scope belongs to the assembly** (the P4-2 review's 异议 8 precedent:
``RelationshipProjectionExecutor`` takes ``user_id`` at construction because a
ConversationRecord has no user leg — DATA_MODEL §3's Conversation column set
carries no ``user_id``, and elc.conversation.store discards the argument it
never persists). The runtime therefore cannot resolve "whose" views these
are; the assembly says so once, here, and the port *refuses* a call that asks
for a different user instead of silently answering for the configured one.

**Best-effort reads.** Every face returns a ``Result``, and the coordinator
treats a refusal as "no view": a view that cannot be read is ``None``, the
turn proceeds, and the prompt simply has no such section (RA §21: a
Relationship/Episode read failure must not block the turn; §19 "turn still
succeeds"). Nothing in this module raises into the caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
    UserId,
)

if TYPE_CHECKING:
    # Annotations only, and deliberately so: this module is imported by
    # ``elc.runtime.__init__``, and ``elc.relationship.episode`` imports
    # ``elc.conversation.commands``, which imports ``elc.runtime.types`` —
    # so a runtime import here would close the cycle
    # ``conversation.commands → runtime.__init__ → persona_views →
    # relationship.episode → conversation.commands`` and make the import
    # graph depend on which package a caller happened to import first (the
    # P4-3 review's cold-start probe caught exactly that). PEP 563 keeps
    # every annotation below a string, so nothing here is evaluated at
    # runtime.
    from elc.relationship.episode import EpisodeView
    from elc.relationship.types import RelationshipView
    from elc.user_config.types import DisclosedUserProfile

__all__ = ["ControllerPersonaViews", "PersonaViewSource"]


@runtime_checkable
class PersonaViewSource(Protocol):
    """The three §11 views the coordinator may ask for, as ``Result``s.

    ``Ok(None)`` means "there is nothing to show" (no episode projected yet,
    no relationship memory, no profile) and is *not* an error: it is the
    ordinary state of a fresh conversation. ``Err`` means the read itself
    failed; the coordinator degrades to ``None`` either way, so the
    distinction matters to a caller that wants to log it, and to nobody else.

    ``user_id`` travels on the calls rather than only on the implementation so
    that the refusal below is expressible: a source that serves one user can
    say so, in the open, instead of quietly answering for another.
    """

    @property
    def user_id(self) -> UserId:
        """The user this source serves (the assembly's own scope)."""
        ...

    def relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView | None]:
        ...

    def episode_view(
        self, conversation_id: ConversationId
    ) -> Result[EpisodeView | None]:
        ...

    def disclosed_user_profile(
        self, user_id: UserId, persona_id: PersonaId
    ) -> Result[DisclosedUserProfile | None]:
        ...


@runtime_checkable
class RelationshipViewSource(Protocol):
    """The Relationship read face this composition needs (structural: the
    domain controller satisfies it — the runtime never imports the domain)."""

    def get_relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView]:
        ...


@runtime_checkable
class EpisodeViewSource(Protocol):
    """The Episode read face (``SqliteEpisodeStore.episode_view``)."""

    def episode_view(
        self, conversation_id: ConversationId
    ) -> Result[EpisodeView | None]:
        ...


@runtime_checkable
class DisclosedProfileSource(Protocol):
    """The disclosure read face (``UserConfigController``)."""

    def get_disclosed_user_profile(
        self, user_id: UserId, persona_id: PersonaId
    ) -> Result[DisclosedUserProfile]:
        ...


class ControllerPersonaViews:
    """The domain composition of :class:`PersonaViewSource`.

    Four injected pieces and one assembly fact:

    - ``relationship`` — the §4 RelationshipView of one Persona×User pair
      (the store's scope-bound read: another persona's memories are not in it
      — DOMAIN_MODEL §17);
    - ``episodes`` — one conversation's projected episode;
    - ``user_config`` — the disclosure decision (§5.1 "Produces
      `DisclosedUserProfile` for a specific Persona/runtime context"), so the
      full profile never travels further than that face;
    - ``user_id`` — whose views these are (see the module docstring).
    """

    def __init__(
        self,
        *,
        relationship: RelationshipViewSource,
        episodes: EpisodeViewSource,
        user_config: DisclosedProfileSource,
        user_id: UserId,
    ) -> None:
        self._relationship = relationship
        self._episodes = episodes
        self._user_config = user_config
        self._user_id = user_id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    def relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView | None]:
        """One pair's ACTIVE relationship memories (§4 RelationshipView)."""

        refusal = self._refuse_other_user(user_id)
        if refusal is not None:
            return Err(refusal)
        view = self._relationship.get_relationship_view(
            persona_id, self._user_id
        )
        if isinstance(view, Err):
            return view
        value: RelationshipView | None = view.value
        return Ok(value)

    def episode_view(
        self, conversation_id: ConversationId
    ) -> Result[EpisodeView | None]:
        """One conversation's projected episode (``Ok(None)`` = not built)."""

        return self._episodes.episode_view(conversation_id)

    def disclosed_user_profile(
        self, user_id: UserId, persona_id: PersonaId
    ) -> Result[DisclosedUserProfile | None]:
        """The action-specific profile view (§18.1 / §24.3).

        The disclosure decision is the controller's and it is total: an
        unconfigured user yields the empty MINIMAL view rather than an error.
        This face never returns the full profile — it cannot, the controller
        does not offer one (§5.1 Rules).
        """

        refusal = self._refuse_other_user(user_id)
        if refusal is not None:
            return Err(refusal)
        disclosed = self._user_config.get_disclosed_user_profile(
            self._user_id, persona_id
        )
        if isinstance(disclosed, Err):
            return disclosed
        value: DisclosedUserProfile | None = disclosed.value
        return Ok(value)

    # -- internals ---------------------------------------------------------

    def _refuse_other_user(self, user_id: UserId) -> DomainError | None:
        """Refuse a call for a user this assembly does not serve.

        Not a defensive nicety: answering it would mean reading another
        user's rows through a source configured for this one, which is the
        one thing a Persona×User-scoped port must never do (DOMAIN_MODEL §17
        "Relationship 不跨 Persona 泄漏" is the same rule one axis over).
        """

        if user_id == self._user_id:
            return None
        return DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=(
                f"this persona view source serves user {self._user_id}; a"
                f" read for {user_id} is refused rather than answered for"
                " the wrong user (DOMAIN_MODEL §17)"
            ),
        )
