"""Empty Persona Domain Controller — a Phase 0 red-line skeleton
(implementation lives in the store / runtime modules, mirroring P1A's
conversation split; the controller stays a skeleton until its
VALIDATE/COMMIT/REJECT/ABSTAIN decision face lands). See
``tests/architecture/test_surface_census.py`` for ``elc.persona``'s row
(``elc.persona.runtime:PersonaRuntime`` + ``elc.persona.store``)."""

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
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.persona: see SURFACE_CENSUS (character package registry)"
        )

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
        raise NotImplementedError(
            "Phase 0 skeleton (red line) — not the live face; live faces for"
            " elc.persona: see SURFACE_CENSUS (persona resolution)"
        )
