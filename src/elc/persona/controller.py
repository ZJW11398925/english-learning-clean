"""Empty Persona Domain Controller (Phase 1 will implement)."""

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
        raise NotImplementedError("Phase 1: character package registry")

    def compile_prompt(
        self, request: PromptCompilationRequest
    ) -> Result[CompiledPrompt]:
        raise NotImplementedError("Phase 1: Persona Runtime / PromptCompiler")

    def resolve_persona(
        self, persona_id: PersonaId
    ) -> Result[CharacterPackageRecord | None]:
        raise NotImplementedError("Phase 1: persona resolution")
