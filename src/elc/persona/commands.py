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
from elc.platform.types import CharacterPackageId, Result


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
    """

    def compile(self, request: PromptCompilationRequest) -> Result[CompiledPrompt]:
        raise NotImplementedError("Phase 1: Persona Runtime + PromptCompiler")
