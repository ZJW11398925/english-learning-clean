"""Persona Runtime command face — the only PromptCompiler in the codebase.

docs/DOMAIN_MODEL.md D-INV-012: the final provider prompt is built only by
Persona Runtime / PromptCompiler. tests/architecture enforces that this
class exists nowhere else.

The GenerationActionStore port moved to elc.runtime.generation in
TASK-OPI-eaaa5a1d.6: GenerationActionIntent / ProviderAttempt are
Runtime-specific records (docs/DOMAIN_MODEL.md §16), so their durable face
and §14 state-machine authority are runtime-owned, not persona-owned.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.persona.types import (
    CharacterPackageRecord,
    CompiledPrompt,
    PromptCompilationRequest,
    TeachingPromptView,
    episode_prompt_fields,
    profile_prompt_fields,
    relationship_prompt_fields,
)
from elc.platform.types import (
    CharacterPackageId,
    Ok,
    Result,
)

#: The fixed section order of the compiled prompt (Phase 3 P3-1B ⑨ pinned
#: it; Phase 4 P4-3 ④ extends it with the three §11 views the persona
#: consumes — docs/RUNTIME_ARCHITECTURE.md §11 lists CharacterPackage,
#: RelationshipView, EpisodeView, WorldLoreView, DisclosedUserProfile,
#: ConversationWindow among the GenerationContext members):
#:
#:     persona → profile → contract → history → relationship → episode →
#:     teaching → channel
#:
#: The new sections sit where they do for stated reasons, not by accident:
#: ``profile`` immediately after ``persona`` (both are "who is talking to
#: whom"); ``relationship``/``episode`` after ``history`` (they are the
#: distilled form of what history shows in full, so the model reads the
#: transcript first and the continuity summary after it); ``teaching`` stays
#: last-but-one because it is the ephemeral directive of *this* turn.
#: Byte-determinism of the compiled prompt depends on this order, so it lives
#: here as a declared constant and is asserted by test rather than being
#: implied by the sequence of appends below. A section is only emitted when
#: its view is present, so every pre-P4-3 assembly compiles byte-identical
#: prompts (pinned by the P1/P3 suites).
PROMPT_SECTION_ORDER = (
    "persona",
    "profile",
    "contract",
    "history",
    "relationship",
    "episode",
    "teaching",
    "channel",
)


@runtime_checkable
class PersonaCommands(Protocol):
    """Persona Runtime writes: package registration + prompt compilation."""

    def register_character_package(
        self, package: CharacterPackageRecord
    ) -> Result[CharacterPackageId]:
        ...

    def compile_prompt(
        self, request: PromptCompilationRequest
    ) -> Result[CompiledPrompt]:
        """Build the final provider prompt via PromptCompiler."""
        ...


class PromptCompiler:
    """Persona Runtime prompt compiler — the sole final-prompt authority.

    Consumes only the views handed in via PromptCompilationRequest. It never
    creates TeachingDirectives (D-INV-002) and never resolves secrets:
    provider disclosure flows through action-specific minimal views and
    secret_ref resolution happens in the transport layer at send time
    (docs/RUNTIME_ARCHITECTURE.md §24.3).

    Deterministic assembly (IMPLEMENTATION_PLAN §3 "PromptCompiler"): the
    same request always yields byte-identical prompt text — no randomness,
    no timestamps, no environment reads; conversation-window slices render
    in turn_sequence order.

    P3-0 (TASK-…55 ③): the [persona] section consumes the canonical
    CharacterPackage §5.1 fields (identity / personality / background /
    speech_style / values / boundaries / opening / scenario /
    generation_policy / lore_refs plus the id/revision provenance) —
    package fields really enter the compiled prompt (a different package
    yields a different prompt, pinned by test). Lifecycle metadata
    (status / updated_at) deliberately stays OUT of the prompt: it is not
    character content, and rendering a clock stamp would break
    byte-determinism.

    P4-3 (TASK-OPI-4d516e4f-….19 ④): three §11 views join the prompt —
    [profile] (the DisclosedUserProfile the disclosure decision produced:
    facts / level / persona), [relationship] (the RelationshipView's ACTIVE
    memories, in the view's own order) and [episode] (the EpisodeView's
    content columns). Each section is versioned and renders its version key
    first, exactly like [teaching]. Scope isolation is structural, not
    defensive: the compiler renders what the views hold, and the views are
    scope-bound reads (one Persona×User pair, one disclosure grant), so
    Persona A's material cannot appear in Persona B's prompt — there is no
    cross-persona object in the request to render. The compiler still
    resolves no secrets and creates no teaching directive (D-INV-002;
    RUNTIME §24.3 "PromptCompiler … 只能消费 action-specific disclosure
    view").
    """

    def compile(self, request: PromptCompilationRequest) -> Result[CompiledPrompt]:
        contract = request.generation_contract
        context = request.generation_context
        contract_id = (
            contract.generation_contract_id if contract is not None else "default"
        )
        sections: list[str] = []

        if context is not None and context.character_package is not None:
            package = context.character_package
            lore_refs = "; ".join(package.lore_refs)
            style = "; ".join(contract.style_constraints) if contract else ""
            forbidden = "; ".join(contract.forbidden_claims) if contract else ""
            sections.append(
                "[persona]\n"
                f"character_package_id: {package.character_package_id}\n"
                f"persona_id: {package.persona_id}\n"
                f"revision: {package.revision}\n"
                f"identity: {package.identity}\n"
                f"personality: {package.personality}\n"
                f"background: {package.background}\n"
                f"speech_style: {package.speech_style}\n"
                f"values: {package.values}\n"
                f"boundaries: {package.boundaries}\n"
                f"opening: {package.opening}\n"
                f"scenario: {package.scenario}\n"
                f"generation_policy: {package.generation_policy}\n"
                f"lore_refs: {lore_refs}\n"
                f"language_policy: {context.language_policy}\n"
                f"style_constraints: {style}\n"
                f"forbidden_claims: {forbidden}"
            )
        else:
            sections.append(
                f"[persona]\npersona_id: {request.persona_id}\n"
                "language_policy: default"
            )

        if context is not None and context.disclosed_user_profile is not None:
            sections.append(
                _section("profile", profile_prompt_fields(
                    context.disclosed_user_profile
                ))
            )

        if contract is not None:
            disclosures = "; ".join(contract.allowed_disclosures)
            max_length = (
                str(contract.max_length) if contract.max_length is not None else "none"
            )
            sections.append(
                "[contract]\n"
                f"generation_contract_id: {contract.generation_contract_id}\n"
                f"action_type: {contract.action_type.value}\n"
                f"response_mode: {contract.response_mode}\n"
                f"allowed_disclosures: {disclosures}\n"
                f"max_length: {max_length}"
            )

        window = getattr(context, "conversation_window", None) if context else None
        slices = getattr(window, "slices", None) if window is not None else None
        if slices:
            lines: list[str] = []
            for slice_ in slices:
                user_text = getattr(slice_.user_turn, "raw_content", "")
                assistant = slice_.assistant_turn
                assistant_text = (
                    assistant.content if assistant is not None else ""
                )
                seq = getattr(slice_, "turn_sequence", 0)
                lines.append(f"#{seq} user: {user_text}")
                if assistant_text:
                    lines.append(f"#{seq} assistant: {assistant_text}")
            sections.append("[history]\n" + "\n".join(lines))

        if context is not None and context.relationship_view is not None:
            sections.append(
                _section("relationship", relationship_prompt_fields(
                    context.relationship_view
                ))
            )

        if context is not None and context.episode_view is not None:
            sections.append(
                _section("episode", episode_prompt_fields(context.episode_view))
            )

        if context is not None and context.ephemeral_teaching_directive is not None:
            sections.append(
                _rendered_teaching_section(
                    context.ephemeral_teaching_directive
                )
            )

        sections.append(f"[channel]\n{request.interaction_channel.value}")
        prompt_text = "\n\n".join(sections)
        return Ok(
            CompiledPrompt(
                persona_id=request.persona_id,
                prompt_text=prompt_text,
                generation_contract=contract_id,
            )
        )


def _section(name: str, fields: tuple[tuple[str, str], ...]) -> str:
    """One P4-3 section: ``[name]`` plus its ``key: value`` lines.

    The shape is the ``[teaching]`` one — a fixed key order, one line per
    key, values already rendered to text — so a section's line count and key
    order never depend on which optional values are set.
    """

    lines = "\n".join(f"{key}: {value}" for key, value in fields)
    return f"[{name}]\n{lines}"


def _rendered_teaching_section(directive: object) -> str:
    """Render the teaching section of the prompt — PromptCompiler-owned.

    Phase 3 P3-1B ⑨: Teaching produces a directive, Persona Runtime owns
    the prompt. The canonical directive projection is
    :class:`TeachingPromptView`; it renders as the ``[teaching]`` section
    with the keys of :data:`TEACHING_PROMPT_KEY_ORDER` in that exact order
    and ``key: value`` lines, so the same view always yields the same
    bytes. Any other object keeps the pre-P3-1B ``[directive]`` rendering
    (no silent drop of a caller's directive).
    """

    if isinstance(directive, TeachingPromptView):
        lines = "\n".join(
            f"{key}: {value}" for key, value in directive.as_prompt_fields()
        )
        return "[teaching]\n" + lines
    return f"[directive]\n{str(directive)}"
