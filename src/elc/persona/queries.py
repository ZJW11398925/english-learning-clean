"""Persona domain query face."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.persona.types import CharacterPackageRecord
from elc.platform.types import CharacterPackageId, PersonaId, Result


@runtime_checkable
class PersonaQueries(Protocol):
    """Persona-owned reads."""

    def get_character_package(
        self, character_package_id: CharacterPackageId
    ) -> Result[CharacterPackageRecord | None]:
        ...

    def resolve_persona(
        self, persona_id: PersonaId
    ) -> Result[CharacterPackageRecord | None]:
        ...
