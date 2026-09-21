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
from elc.relationship.episode import EpisodeView
from elc.relationship.types import RelationshipView
from elc.runtime.types import GenerationActionType
from elc.user_config.types import DisclosedUserProfile


@dataclass(frozen=True)
class CharacterPackageRecord:
    """Persona-owned character aggregate — the canonical CharacterPackage
    column set, word for word (docs/DATA_MODEL.md §5.1:235-256; "Owned by
    Persona Domain").

    P3-0 (TASK-OPI-eaaa5a1d-7ac7-4746-bcdf-c02bc9147492.55 ③): the former
    Phase 0 schema stub (display_name / language_policy / generation_policy)
    is replaced by the real §5.1 shape. ``revision`` is the package
    revision counter; ``lore_refs`` is the §5.1 ``lore_refs[]`` list
    (tuple storage form — implementation-defined per DATA_MODEL §27);
    ``status`` / ``updated_at`` are lifecycle metadata. Real production
    sourcing (registry / durable store / persona resolution) lands in
    Phase 5 — until then the persona domain supplies the deterministic
    :func:`sample_character_package` fixture below.
    """

    character_package_id: CharacterPackageId
    persona_id: PersonaId
    revision: int
    identity: str
    personality: str
    background: str
    speech_style: str
    values: str
    boundaries: str
    opening: str
    scenario: str
    generation_policy: str
    lore_refs: tuple[str, ...]
    status: str
    updated_at: str


def sample_character_package(
    *,
    character_package_id: str = "cpkg-sample-maya",
    persona_id: str = "persona-maya",
    revision: int = 1,
    identity: str = (
        "Maya, a barista at a small Seattle coffee shop"
    ),
    personality: str = "warm, curious, gently playful",
    background: str = (
        "grew up in Portland; studied literature before finding coffee"
    ),
    speech_style: str = (
        "casual American English, short sentences, occasional coffee"
        " metaphors"
    ),
    values: str = "honesty, kindness, genuine curiosity about people",
    boundaries: str = "never lectures; changes topic when asked",
    opening: str = "Hey! Welcome in — what can I get started for you?",
    scenario: str = "morning shift at the coffee shop",
    generation_policy: str = "persona-normal-v1",
    lore_refs: tuple[str, ...] = ("lore-shop-menu", "lore-city-seattle"),
    status: str = "ACTIVE",
    updated_at: str = "2026-09-20T00:00:00+00:00",
) -> CharacterPackageRecord:
    """Deterministic real-shaped CharacterPackage fixture (P3-0 ③).

    Every field is a keyword override away from the defaults, the values
    are fixed (no clock, no randomness — two calls construct equal
    packages, so prompts compiled from them are byte-stable). Real
    production package sourcing is Phase 5; until then this fixture is
    the persona domain's supply of a non-None §5.1 package for the
    normal generation chain (ConversationCoordinator optional injection
    → GenerationContext → PromptCompiler)."""

    return CharacterPackageRecord(
        character_package_id=CharacterPackageId(character_package_id),
        persona_id=PersonaId(persona_id),
        revision=revision,
        identity=identity,
        personality=personality,
        background=background,
        speech_style=speech_style,
        values=values,
        boundaries=boundaries,
        opening=opening,
        scenario=scenario,
        generation_policy=generation_policy,
        lore_refs=lore_refs,
        status=status,
        updated_at=updated_at,
    )


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
    (D-INV-012).

    P4-3 (TASK-OPI-4d516e4f-….19 ④): the three Phase-4 views are typed now.
    ``relationship_view`` / ``episode_view`` / ``disclosed_user_profile``
    were ``object | None`` placeholders while the owning domains had no such
    types; both types exist (elc.relationship.types.RelationshipView,
    elc.relationship.episode.EpisodeView,
    elc.user_config.types.DisclosedUserProfile), so the compiler renders a
    *declared* shape instead of duck-typing whatever arrives. The remaining
    ``object | None`` fields are the ones whose domains have not landed
    their views yet (WorldLoreView), kept as they were — this slice types
    what it renders, not what it cannot name.

    Import direction: this module imports the view *types* from the domains
    that own them, which is exactly how §11 works — Persona Runtime consumes
    these views and owns none of them (DOMAIN_MODEL §4 "Persona Runtime
    consumes"). The pin that still holds and is re-asserted by test: persona
    never imports ``elc.teaching`` / ``elc.learning`` (D-INV-002), and the
    two-way teaching pin stays exactly as it was.
    """

    character_package: CharacterPackageRecord | None
    relationship_view: RelationshipView | None
    episode_view: EpisodeView | None
    world_lore_view: object | None
    disclosed_user_profile: DisclosedUserProfile | None
    conversation_window: object | None
    language_policy: str
    generation_policy: str
    generation_contract: GenerationContract | None = None
    ephemeral_teaching_directive: object | None = None


#: Version of the ``[teaching]`` section template (Phase 3 P3-1B, TASK-…2.2
#: ⑨). The prompt is a canonical artifact: changing the key set, the order
#: or the separators of this section is a NEW version, and the version is
#: rendered inside the section so a stored prompt says which template
#: produced it.
TEACHING_PROMPT_SECTION_VERSION = "teaching-prompt-v1"

#: The ``[teaching]`` section's key order, pinned here and enforced by the
#: compiler — byte-determinism (same view → same bytes) depends on it.
TEACHING_PROMPT_KEY_ORDER = (
    "prompt_version",
    "action_type",
    "moment_id",
    "focus_target_type",
    "focus_target_id",
    "presentation_phase",
    "support_level",
    "attempt_index",
    "hint",
    "reveal",
    "explanation",
    "closure",
    "completion_outcome",
    "abort_reason",
)


#: Version of the ``[profile]`` section template (Phase 4 P4-3,
#: TASK-OPI-4d516e4f-….19 ④). The prompt is a canonical artifact: changing
#: the key set, the order or the separators of this section is a NEW version,
#: and the version is rendered inside the section so a stored prompt says
#: which template produced it (the P3-1B ``[teaching]`` precedent).
PROFILE_PROMPT_SECTION_VERSION = "profile-prompt-v1"

#: Version of the ``[relationship]`` section template (P4-3).
RELATIONSHIP_PROMPT_SECTION_VERSION = "relationship-prompt-v1"

#: Version of the ``[episode]`` section template (P4-3).
EPISODE_PROMPT_SECTION_VERSION = "episode-prompt-v1"

#: The key order of each P4-3 section, pinned here and enforced by the
#: compiler — byte-determinism (same view → same bytes) depends on it.
#: Absent optional values render as the empty string, and lists join with
#: "; ", so a section's line count and key order never depend on the data.
PROFILE_PROMPT_KEY_ORDER = (
    "prompt_version",
    "persona_id",
    "disclosure_level",
    "disclosed_facts",
)
RELATIONSHIP_PROMPT_KEY_ORDER = (
    "prompt_version",
    "persona_id",
    "user_id",
    "memories",
)
EPISODE_PROMPT_KEY_ORDER = (
    "prompt_version",
    "episode_id",
    "version",
    "status",
    "summary",
    "open_threads",
    "recent_events",
)


def profile_prompt_fields(
    view: DisclosedUserProfile,
) -> tuple[tuple[str, str], ...]:
    """The ``[profile]`` section as canonical (key, value) pairs.

    Only what the disclosure decision authorized is rendered:
    ``DisclosedUserProfile`` is the one user-profile shape a persona may
    consume (docs/DOMAIN_MODEL.md §5.1 Rules), so the compiler cannot render
    a fact the persona was not granted — there is no fuller view in the
    request to render from.
    """

    values = {
        "prompt_version": PROFILE_PROMPT_SECTION_VERSION,
        "persona_id": str(view.persona_id),
        "disclosure_level": view.disclosure_level.value,
        "disclosed_facts": "; ".join(view.disclosed_facts),
    }
    return tuple((key, values[key]) for key in PROFILE_PROMPT_KEY_ORDER)


def relationship_prompt_fields(
    view: RelationshipView,
) -> tuple[tuple[str, str], ...]:
    """The ``[relationship]`` section as canonical (key, value) pairs.

    The memories are the view's ACTIVE rows **in the view's own order** (the
    store's durable order — DOMAIN_MODEL §5 unit Persona × User; §17
    "Relationship 不跨 Persona 泄漏", which the scope-bound read already
    guarantees: another persona's memory is not in this object). Order is
    therefore content: the section renders what the view holds, in the order
    it holds it, and never re-sorts.
    """

    memories = "; ".join(
        f"{entry.memory_type.value}: {entry.canonical_content}"
        for entry in view.active_memories
    )
    values = {
        "prompt_version": RELATIONSHIP_PROMPT_SECTION_VERSION,
        "persona_id": str(view.persona_id),
        "user_id": str(view.user_id),
        "memories": memories,
    }
    return tuple((key, values[key]) for key in RELATIONSHIP_PROMPT_KEY_ORDER)


def episode_prompt_fields(view: EpisodeView) -> tuple[tuple[str, str], ...]:
    """The ``[episode]`` section as canonical (key, value) pairs.

    The content columns only — ``EpisodeView`` has no ``updated_at`` by
    construction, so lifecycle metadata cannot reach the prompt even by
    accident (the P3-0 rule: a clock stamp in the prompt would break
    byte-determinism and put durable bookkeeping in front of the model).
    """

    values = {
        "prompt_version": EPISODE_PROMPT_SECTION_VERSION,
        "episode_id": str(view.episode_id),
        "version": view.version,
        "status": view.status.value,
        "summary": view.summary,
        "open_threads": "; ".join(view.open_threads),
        "recent_events": "; ".join(view.recent_events),
    }
    return tuple((key, values[key]) for key in EPISODE_PROMPT_KEY_ORDER)


@dataclass(frozen=True)
class TeachingPromptView:
    """The narrow teaching view the PromptCompiler is allowed to render
    (Phase 3 P3-1B ⑨; docs/DOMAIN_MODEL.md §14: the Teaching Planner
    produces the directive, Persona Runtime owns the final prompt).

    Deliberately persona-owned: Teaching must not import this package and
    this package must not import ``elc.teaching`` (the two-way AST pin), so
    the compiler renders from a view type it owns and the orchestrator
    projects the teaching directive onto it. Every field is a primitive —
    the view carries no attempt content, no ladder internals and no
    learner state (D-INV-002: no persona identity is created here).

    Absent optional fields render as the empty string, so the section's
    line count and key order never depend on which fields are set.
    """

    action_type: str
    presentation_phase: str = ""
    support_level: str = ""
    moment_id: str = ""
    focus_target_type: str = ""
    focus_target_id: str = ""
    attempt_index: int = 0
    hint: str | None = None
    reveal: str | None = None
    explanation: str | None = None
    closure: str | None = None
    completion_outcome: str | None = None
    abort_reason: str | None = None
    prompt_version: str = TEACHING_PROMPT_SECTION_VERSION

    def as_prompt_fields(self) -> tuple[tuple[str, str], ...]:
        """The canonical (key, value) pairs in :data:`TEACHING_PROMPT_KEY_ORDER`
        order — the deterministic source of the ``[teaching]`` section."""

        values = {
            "prompt_version": self.prompt_version,
            "action_type": self.action_type,
            "moment_id": self.moment_id,
            "focus_target_type": self.focus_target_type,
            "focus_target_id": self.focus_target_id,
            "presentation_phase": self.presentation_phase,
            "support_level": self.support_level,
            "attempt_index": str(self.attempt_index),
            "hint": self.hint or "",
            "reveal": self.reveal or "",
            "explanation": self.explanation or "",
            "closure": self.closure or "",
            "completion_outcome": self.completion_outcome or "",
            "abort_reason": self.abort_reason or "",
        }
        return tuple((key, values[key]) for key in TEACHING_PROMPT_KEY_ORDER)


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
