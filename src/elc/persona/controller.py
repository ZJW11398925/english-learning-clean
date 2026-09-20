"""Empty Persona Domain Controller (implementation lives in the store /
runtime modules, mirroring P1A's conversation split; the controller stays a
skeleton until its VALIDATE/COMMIT/REJECT/ABSTAIN decision face lands)."""

from __future__ import annotations

from elc.persona.types import (
    CharacterPackageRecord,
    CompiledPrompt,
    PromptCompilationRequest,
)
from elc.platform.types import CharacterPackageId, PersonaId, Result


class PersonaController:
    """Owns character identity truth. No implementation in Phase 0."""

    def register_character_package(
        self, package: CharacterPackageRecord
    ) -> Result[CharacterPackageId]:
        raise NotImplementedError("Phase 2+: character package registry")

    def compile_prompt(
        self, request: PromptCompilationRequest
    ) -> Result[CompiledPrompt]:
        raise NotImplementedError(
            "prompt compilation lives in PromptCompiler / PersonaRuntime"
            " (D-INV-012)"
        )

    def resolve_persona(
        self, persona_id: PersonaId
    ) -> Result[CharacterPackageRecord | None]:
        raise NotImplementedError("Phase 2+: persona resolution")
