"""Content Library command face — read-only release loading."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from elc.platform.types import ContentVersion, Result


@runtime_checkable
class ContentCommands(Protocol):
    """content.db stays read-only: the only write is loading a new
    versioned release build (docs/DATA_MODEL.md §2)."""

    def load_content_release(
        self, release_manifest: str
    ) -> Result[ContentVersion]:
        ...
