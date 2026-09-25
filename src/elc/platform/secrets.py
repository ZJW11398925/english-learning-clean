"""Secret seam (prep-1) — where a provider key is resolved, and nowhere else.

docs/DATA_MODEL.md §2 keeps secrets out of app.db ("app.db only keeps
``secret_ref``"); docs/RUNTIME_ARCHITECTURE.md §24.3 resolves the value at
**send time**, outside the prompt compiler, the durable generation action,
ordinary logs and any portable export; docs/PRODUCT_CONTRACT.md §11 keeps the
key locally in V1.

:class:`SecretSource` is that one-face seam, and its contract is the value-
shaped one the rest of this runtime uses for external failure: **"no key here"
is ``None``, never an exception**. A missing file, an unreadable file, invalid
JSON, an absent key and an unset variable all answer ``None``; the adapter that
asked turns that into its ``missing-secret`` reason.

Both V1 implementations are read-only and live outside app.db: a JSON file the
caller keeps outside the checkout, and one environment variable. Nothing in
this module writes — no file, no database, no log line. A secret that reached a
log would be as leaked as one that reached a table.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from elc.platform.types import SecretRef

__all__ = [
    "EnvSecretSource",
    "FileSecretSource",
    "SecretSource",
]


@runtime_checkable
class SecretSource(Protocol):
    """Resolve a ``secret_ref`` to its value at send time (RA §24.3).

    ``None`` is the honest answer for every failure this seam can meet, so a
    caller need not distinguish "no file" from "no key in the file" to decide
    whether it may send.
    """

    def resolve(self, ref: SecretRef) -> str | None: ...


@dataclass(frozen=True)
class FileSecretSource:
    """One JSON document, re-read per call, holding ``{"<ref>": "<key>"}``.

    Re-read on every resolve so a rotated file is picked up without a restart
    and a file that does not exist yet is not an accident of construction
    order. Anything that is not "a string under this ref" answers ``None``: a
    missing or unreadable path, a directory, invalid JSON, a non-object
    document, an absent key and an empty value are one fact to the caller.
    """

    path: Path

    def resolve(self, ref: SecretRef) -> str | None:
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            document = json.loads(text)
        except ValueError:
            return None
        if not isinstance(document, dict):
            return None
        value = document.get(str(ref))
        return value if isinstance(value, str) and value else None


@dataclass(frozen=True)
class EnvSecretSource:
    """One environment variable; ``ref`` is ignored (the variable *is* the ref).

    An unset or empty variable answers ``None``, exactly like the file
    source's missing key — the two sources are interchangeable to the adapter.
    """

    var: str

    def resolve(self, ref: SecretRef) -> str | None:
        del ref  # The variable's name is this source's whole addressing scheme.
        value = os.environ.get(self.var)
        return value if value else None
