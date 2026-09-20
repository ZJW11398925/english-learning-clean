"""Persona Runtime command face — the only PromptCompiler in the codebase.

docs/DOMAIN_MODEL.md D-INV-012: the final provider prompt is built only by
Persona Runtime / PromptCompiler. tests/architecture enforces that this
class exists nowhere else.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.persona.types import (
    CharacterPackageRecord,
    CompiledPrompt,
    PromptCompilationRequest,
)
from elc.platform.types import (
    ActionId,
    CharacterPackageId,
    Ok,
    Result,
    RuntimeEpoch,
    TurnId,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    ProviderAttemptRecord,
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


@runtime_checkable
class GenerationActionStore(Protocol):
    """Durable face for GenerationActionIntent / ProviderAttempt rows
    (implemented by elc.persona.store.SqliteGenerationStore; §14 state
    authority + CP2.5 attempt log, RUNTIME §6)."""

    def create_action(
        self, intent: GenerationActionIntentRecord
    ) -> Result[ActionId]:
        ...

    def transition_action(
        self,
        action_id: ActionId,
        expected: GenerationActionStatus,
        new: GenerationActionStatus,
    ) -> Result[GenerationActionIntentRecord]:
        ...

    def record_attempt(
        self, attempt: ProviderAttemptRecord
    ) -> Result[ProviderAttemptRecord]:
        ...

    def get_action(
        self, action_id: ActionId
    ) -> Result[GenerationActionIntentRecord | None]:
        ...

    def get_action_for_turn(
        self, turn_id: TurnId
    ) -> Result[GenerationActionIntentRecord | None]:
        ...

    def claim_action_for_recovery(
        self, action_id: ActionId
    ) -> Result[GenerationActionIntentRecord]:
        ...

    def recoverable_generation_actions(
        self, current_epoch: RuntimeEpoch
    ) -> tuple[GenerationActionIntentRecord, ...]:
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
            style = "; ".join(contract.style_constraints) if contract else ""
            forbidden = "; ".join(contract.forbidden_claims) if contract else ""
            sections.append(
                "[persona]\n"
                f"name: {package.display_name}\n"
                f"persona_id: {package.persona_id}\n"
                f"language_policy: {package.language_policy}\n"
                f"generation_policy: {package.generation_policy}\n"
                f"style_constraints: {style}\n"
                f"forbidden_claims: {forbidden}"
            )
        else:
            sections.append(
                f"[persona]\npersona_id: {request.persona_id}\n"
                "language_policy: default"
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

        if context is not None and context.ephemeral_teaching_directive is not None:
            directive = str(context.ephemeral_teaching_directive)
            sections.append(f"[directive]\n{directive}")

        sections.append(f"[channel]\n{request.interaction_channel.value}")
        prompt_text = "\n\n".join(sections)
        return Ok(
            CompiledPrompt(
                persona_id=request.persona_id,
                prompt_text=prompt_text,
                generation_contract=contract_id,
            )
        )
