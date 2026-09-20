"""app.db connection + SQLite profile (docs/DATA_MODEL.md §2, §26.1).

Local Runtime V1 profile: app.db holds all mutable user/runtime state needed
for short atomic commits; content.db stays a read-only build artifact;
secrets live in a secret store by reference only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MIGRATIONS_DIR = REPO_ROOT / "migrations"


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open an app.db connection with the canonical local profile.

    - foreign keys ON (mirrors baseline LocalRuntime profile),
    - WAL for file databases (in-memory keeps its memory journal),
    - explicit CHECK instead of implicit autocommit surprises.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    return conn
