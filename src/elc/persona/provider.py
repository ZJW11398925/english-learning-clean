"""Provider adapter face + deterministic fake provider (Phase 1 P1B).

No real model is wired in Phase 1 (zero network, zero secret reads — the
task forbids real provider calls). :class:`ScriptedPersonaProvider` is the
deterministic fake with exactly the two §3-relevant behaviours:

- normal output (deterministic text derived from the prompt), and
- no-output / raised failure (provider-side empty answer or exception).

The script advances one entry per call and repeats its final entry, so a
retry loop is fully predictable in tests. The adapter contract itself (the
``PersonaProvider`` protocol) is the seam a real transport fills later —
external calls must always run outside any DB transaction
(docs/RUNTIME_ARCHITECTURE.md §24.1; R-INV-004).
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from elc.persona.types import CompiledPrompt, ProviderOutput
from elc.platform.types import PersonaId


def request_hash(prompt: CompiledPrompt) -> str:
    """Deterministic request fingerprint for ProviderAttempt.request_hash
    (docs/DATA_MODEL.md §20)."""

    return hashlib.sha256(prompt.prompt_text.encode("utf-8")).hexdigest()


def result_hash(text: str) -> str:
    """Deterministic result fingerprint for ProviderAttempt.result_hash."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_reply(prompt: CompiledPrompt) -> str:
    """Deterministic normal output derived from the compiled prompt.

    Echoes the latest user line of the history section (or the persona id
    when no history is present) — same prompt in, same text out.
    """

    last_user = ""
    for line in prompt.prompt_text.splitlines():
        if " user: " in line:
            last_user = line.split(" user: ", maxsplit=1)[1]
    if last_user:
        return f"{prompt.persona_id} says: {last_user}"
    return f"{prompt.persona_id} greets you."


@runtime_checkable
class PersonaProvider(Protocol):
    """Provider call face; implementations must be side-effect-free with
    respect to app.db (external call outside any transaction, §24.1)."""

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        ...


def normal_output(text: str = "persona reply") -> ProviderOutput:
    """Scripted entry: a normal provider answer (fixed deterministic text;
    use :func:`derive_reply` to derive one from a prompt instead)."""

    return ProviderOutput(text=text, error=None)


def no_output() -> ProviderOutput:
    """Scripted entry: provider answered nothing (§3 provider no-output)."""

    return ProviderOutput(text="", error=None)


def provider_failure(reason: str = "provider exploded") -> ProviderOutput:
    """Scripted entry: provider-side failure surfaced as a value."""

    return ProviderOutput(text=None, error=reason)


class ScriptedPersonaProvider:
    """Deterministic fake provider — the only provider in Phase 1.

    ``script`` entries are ProviderOutput values or exceptions (the latter
    are raised on call, standing in for transport failures). Repeating the
    final entry keeps a retry loop deterministic once the script runs out.
    """

    def __init__(
        self,
        script: tuple[ProviderOutput | BaseException, ...] | None = None,
        persona_id: PersonaId | None = None,
    ) -> None:
        self._script = script if script is not None else ()
        self._persona_id = persona_id
        self._cursor = 0
        self.calls: list[str] = []  # request hashes, for test assertions

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def call(self, prompt: CompiledPrompt) -> ProviderOutput:
        self.calls.append(request_hash(prompt))
        if not self._script:
            return ProviderOutput(text=derive_reply(prompt), error=None)
        index = min(self._cursor, len(self._script) - 1)
        self._cursor += 1
        entry = self._script[index]
        if isinstance(entry, BaseException):
            raise entry
        return entry
