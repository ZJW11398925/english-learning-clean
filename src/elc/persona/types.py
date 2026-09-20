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
from enum import StrEnum

from elc.platform.types import (
    ActionId,
    CharacterPackageId,
    ConversationId,
    InteractionChannel,
    PersonaId,
)
from elc.runtime.types import GenerationActionType


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

    The §11 views travel inside :class:`GenerationContext` (the canonical
    GenerationContext structure, docs/RUNTIME_ARCHITECTURE.md §11); the
    orchestrator hands over views/references only, never prompt text.

    Teaching influence arrives only as an `EphemeralTeachingDirective`
    inside the context — produced by the Teaching Planner, never as a
    prompt fragment owned here.
    """

    conversation_id: ConversationId
    persona_id: PersonaId
    interaction_channel: InteractionChannel
    generation_context: GenerationContext | None = None
    generation_contract: GenerationContract | None = None


@dataclass(frozen=True)
class CompiledPrompt:
    """The final provider prompt. Provenance: Persona Runtime / PromptCompiler."""

    persona_id: PersonaId
    prompt_text: str
    generation_contract: str


#: docs/DATA_MODEL.md §21: Forbidden claims 至少防止 the two false-mastery
#: phrasings below (word for word from the canonical list).
DEFAULT_FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "你已经完全掌握",
    "整句已经完全地道",
)


@dataclass(frozen=True)
class GenerationContract:
    """docs/DATA_MODEL.md §21 GenerationContract (column set verbatim).

    basic Phase 1 contract: the declaration the deterministic Response
    Validator checks the provider output against (RUNTIME_ARCHITECTURE §12
    "GenerationContract compliance"). ``response_mode`` names the delivery
    mode (RUNTIME §13); Phase 1 P1B implements the BUFFERED_VALIDATED path.
    """

    generation_contract_id: str
    action_type: GenerationActionType
    persona_id: PersonaId
    allowed_disclosures: tuple[str, ...]
    language_policy: str
    style_constraints: tuple[str, ...]
    forbidden_claims: tuple[str, ...] = DEFAULT_FORBIDDEN_CLAIMS
    teaching_focus: str | None = None
    presentation_phase: str | None = None
    reveal_policy: str | None = None
    response_mode: str = "BUFFERED_VALIDATED"
    max_length: int | None = None


@dataclass(frozen=True)
class GenerationContext:
    """docs/RUNTIME_ARCHITECTURE.md §11 GenerationContext — the structured
    views Persona Runtime consumes (DOMAIN_MODEL §4). The orchestrator only
    hands over views/references; it never assembles prompt text
    (D-INV-012)."""

    character_package: CharacterPackageRecord | None
    relationship_view: object | None
    episode_view: object | None
    world_lore_view: object | None
    disclosed_user_profile: object | None
    conversation_window: object | None
    language_policy: str
    generation_policy: str
    generation_contract: GenerationContract | None = None
    ephemeral_teaching_directive: object | None = None


class ValidatorDecision(StrEnum):
    """docs/STATE_MACHINES.md §15 Response Validator output, word for word."""

    ACCEPT = "ACCEPT"
    RETRY = "RETRY"
    FALLBACK = "FALLBACK"
    ABORT_DELIVERY = "ABORT_DELIVERY"


@dataclass(frozen=True)
class ValidatorResult:
    """docs/DATA_MODEL.md §21.1 ValidatorResult (column set verbatim).

    Registry-riding runtime record (DOMAIN_MODEL §18): validators are
    proposal-only and never write domain truth themselves (R-INV-013).
    """

    validator_result_id: str
    action_id: ActionId
    attempt_no: int
    decision: ValidatorDecision
    reason_codes: tuple[str, ...]
    validator_version: str
    created_at: str | None = None


@dataclass(frozen=True)
class ProviderOutput:
    """One provider call outcome — deterministic fake-provider contract.

    ``text`` empty/None plus ``error`` None means a no-output success;
    ``error`` set means the provider itself failed (exception surfaced as a
    deterministic value by the fake provider)."""

    text: str | None
    error: str | None = None

    def has_output(self) -> bool:
        return self.text is not None and self.text != ""
