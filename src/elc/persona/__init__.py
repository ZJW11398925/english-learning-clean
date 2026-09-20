"""Persona domain — CharacterPackage + the sole PromptCompiler.

docs/DOMAIN_MODEL.md §4. PromptCompiler lives only here (Gate item 3).
"""

from elc.persona.commands import PersonaCommands, PromptCompiler
from elc.persona.controller import PersonaController
from elc.persona.queries import PersonaQueries
from elc.persona.types import (
    CharacterPackageRecord,
    CompiledPrompt,
    PromptCompilationRequest,
)

__all__ = [
    "CharacterPackageRecord",
    "CompiledPrompt",
    "PersonaCommands",
    "PersonaController",
    "PersonaQueries",
    "PromptCompilationRequest",
    "PromptCompiler",
]
