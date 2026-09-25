"""Offline helpers for the prep-1 suite — no socket, no urlopen, no http.

Every provider call in this suite goes through an injected ``HttpPost`` (the
seam ``elc.persona.openai_provider`` documents and keeps as the repository's
single egress point), and every model answer is a scripted
``ScriptedPersonaProvider`` entry. Nothing in ``tests/host`` imports ``socket``,
``urllib`` or ``http``; the offline claim is executable in
``test_cli.py::test_the_only_egress_point_and_no_server`` (a source scan) and
restated here for the reader.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from elc.persona.openai_provider import OpenAICompatibleConfig
from elc.platform.types import SecretRef

__all__ = [
    "FIXED_SECRET_REF",
    "REPLY_TEXT",
    "SENTINEL_KEY",
    "FixedSecret",
    "RecordingPost",
    "app_db_bytes",
    "completion",
    "config",
    "db_text_cells",
]

#: The key every leak pin looks for: long enough to be unambiguous, and not a
#: substring of anything else this suite writes anywhere.
SENTINEL_KEY = "sk-prep1-sentinel-key-DO-NOT-LEAK-4f2c"

#: What the offline transport answers with on a successful call.
REPLY_TEXT = "offline reply from the injected transport"

#: The ref the injected secret sources answer for.
FIXED_SECRET_REF = SecretRef("api-key")


@dataclass
class RecordingPost:
    """An ``HttpPost`` that answers what the test set and records every call.

    ``raises`` is how a transport failure is spelled: the adapter must turn it
    into a reason value (and must not carry the exception's text anywhere).
    """

    status: int = 200
    payload: bytes = b""
    raises: BaseException | None = None
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.calls.append(
            {"url": url, "headers": dict(headers), "body": body, "timeout": timeout}
        )
        if self.raises is not None:
            raise self.raises
        return self.status, self.payload

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def authorization(self) -> object:
        return self.calls[0]["headers"]["Authorization"]  # type: ignore[index]


@dataclass(frozen=True)
class FixedSecret:
    """A ``SecretSource`` over one fixed value (``None`` = "no key here")."""

    value: str | None = SENTINEL_KEY

    def resolve(self, ref: SecretRef) -> str | None:
        del ref  # One value for every ref: that is all the pins need.
        return self.value


def completion(text: str = REPLY_TEXT) -> bytes:
    """A minimal OpenAI-compatible 2xx body."""

    return json.dumps({"choices": [{"message": {"content": text}}]}).encode("utf-8")


def config(**overrides: object) -> OpenAICompatibleConfig:
    """The offline coordinates: an un-routable host and a model name."""

    fields: dict[str, object] = {
        "base_url": "http://offline.invalid/v1",
        "model": "offline-model",
        "secret_ref": FIXED_SECRET_REF,
    }
    fields.update(overrides)
    return OpenAICompatibleConfig(**fields)  # type: ignore[arg-type]


def db_text_cells(db: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every string/bytes cell of every table in app.db: ``(table, value)``."""

    cells: list[tuple[str, str]] = []
    tables = [
        str(row[0])
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]
    for table in tables:
        for row in db.execute(f"SELECT * FROM {table}"):
            for value in row:
                if isinstance(value, str):
                    cells.append((table, value))
                elif isinstance(value, bytes):
                    cells.append((table, value.decode("utf-8", "replace")))
    return cells


def app_db_bytes(path: Path) -> bytes:
    """The app.db file plus its WAL/SHM siblings, as raw bytes.

    Stronger than the table scan: it also covers pages the tables no longer
    reference. The key must be absent from all of them too.
    """

    blob = b""
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            blob += candidate.read_bytes()
    return blob
