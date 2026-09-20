"""Persona domain — CharacterPackage ownership and the final prompt.

Owns (docs/DOMAIN_MODEL.md §4): CharacterPackage, character identity,
personality, background, speech style, values, boundaries,
opening/scenario, generation policy, lore references.

PromptCompiler belongs to Persona Runtime — and to nothing else
(docs/DOMAIN_MODEL.md §4 "PromptCompiler 属于 Persona Runtime";
D-INV-012: the final provider prompt can only be built here).

Consumes (views, never owns): RelationshipView, EpisodeView, WorldLoreView,
DisclosedUserProfile, ConversationWindow, LanguagePolicy, GenerationPolicy,
EphemeralTeachingDirective?, GenerationContract.

Does NOT own: teaching target selection, learner state, relationship writes.
D-INV-002: Persona Runtime does not create TeachingDirective.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.platform.types import (
    CharacterPackageId,
    ConversationId,
    InteractionChannel,
    PersonaId,
)


@dataclass(frozen=True)
class CharacterPackageRecord:
    """Persona-owned character aggregate (schema stub, docs/DOMAIN_MODEL.md §4)."""

    character_package_id: CharacterPackageId
    persona_id: PersonaId
    display_name: str
    language_policy: str
    generation_policy: str


@dataclass(frozen=True)
class PromptCompilationRequest:
    """Inputs consumed by Persona Runtime to build the final provider prompt.

    Teaching influence arrives only as an `EphemeralTeachingDirective`
    produced by the Teaching Planner — never as a prompt fragment owned here.
    """

    conversation_id: ConversationId
    persona_id: PersonaId
    interaction_channel: InteractionChannel
    conversation_window: object | None
    disclosed_user_profile: object | None
    relationship_view: object | None
    episode_view: object | None
    world_lore_view: object | None
    ephemeral_teaching_directive: object | None


@dataclass(frozen=True)
class CompiledPrompt:
    """The final provider prompt. Provenance: Persona Runtime / PromptCompiler."""

    persona_id: PersonaId
    prompt_text: str
    generation_contract: str
