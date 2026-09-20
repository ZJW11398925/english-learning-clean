"""Persona domain — CharacterPackage + the sole PromptCompiler.

docs/DOMAIN_MODEL.md §4. PromptCompiler lives only here (Gate item 3).
The GenerationActionStore port and SqliteGenerationStore moved to
elc.runtime.generation / elc.platform.db.generation_store in
TASK-OPI-eaaa5a1d.6 (GenerationActionIntent / ProviderAttempt are
Runtime-specific records, DOMAIN_MODEL §16).
"""

from elc.persona.commands import (
    PersonaCommands,
    PromptCompiler,
)
from elc.persona.controller import PersonaController
from elc.persona.provider import (
    PersonaProvider,
    ScriptedPersonaProvider,
    no_output,
    normal_output,
    provider_failure,
)
from elc.persona.queries import PersonaQueries
from elc.persona.runtime import (
    DEFAULT_MAX_PROVIDER_ATTEMPTS,
    BufferedReply,
    GenerationOutcome,
    PersonaRuntime,
    action_intent_for_turn,
)
from elc.persona.types import (
    DEFAULT_FORBIDDEN_CLAIMS,
    CharacterPackageRecord,
    CompiledPrompt,
    GenerationContext,
    GenerationContract,
    PromptCompilationRequest,
    ProviderOutput,
    ValidatorDecision,
    ValidatorResult,
)
from elc.persona.validator import (
    VALIDATOR_VERSION,
    ResponseValidator,
)

__all__ = [
    "DEFAULT_FORBIDDEN_CLAIMS",
    "DEFAULT_MAX_PROVIDER_ATTEMPTS",
    "VALIDATOR_VERSION",
    "BufferedReply",
    "CharacterPackageRecord",
    "CompiledPrompt",
    "GenerationContext",
    "GenerationContract",
    "GenerationOutcome",
    "PersonaCommands",
    "PersonaController",
    "PersonaProvider",
    "PersonaQueries",
    "PersonaRuntime",
    "PromptCompiler",
    "PromptCompilationRequest",
    "ProviderOutput",
    "ResponseValidator",
    "ScriptedPersonaProvider",
    "ValidatorDecision",
    "ValidatorResult",
    "action_intent_for_turn",
    "no_output",
    "normal_output",
    "provider_failure",
]
