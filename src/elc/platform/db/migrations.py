"""Idempotent SQL migration runner (docs/IMPLEMENTATION_PLAN.md §17-02).

- migrations live in <repo>/migrations as numbered `*.sql` files,
- `schema_migrations` is the version table (docs/DATA_MODEL.md §26.1:
  "数据库迁移必须显式更新版本，禁止依赖代码猜 schema"),
- applying is idempotent: each file runs at most once, inside one immediate
  transaction together with its version-table insert,
- `schema_meta.last_migration_id` is updated on every apply.

Migration ids come from repository-controlled filenames validated against a
strict pattern before being embedded into SQL literals; application data
always travels through bound parameters, never string assembly.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from elc.platform.db.connection import DEFAULT_MIGRATIONS_DIR

_MIGRATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_VERSION_TABLE = "schema_migrations"
_META_TABLE = "schema_meta"


class MigrationError(RuntimeError):
    """A migration file is malformed or failed to apply."""


def ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_VERSION_TABLE} ("
        "migration_id TEXT PRIMARY KEY,"
        "applied_at   TEXT NOT NULL"
        ")"
    )
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_META_TABLE} ("
        "key   TEXT PRIMARY KEY,"
        "value TEXT NOT NULL"
        ")"
    )
    conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    ensure_version_table(conn)
    rows = conn.execute(
        f"SELECT migration_id FROM {_VERSION_TABLE} ORDER BY migration_id"
    ).fetchall()
    return {row[0] for row in rows}


def list_migrations(migrations_dir: Path = DEFAULT_MIGRATIONS_DIR) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"))


def apply_migrations(
    conn: sqlite3.Connection,
    migrations_dir: Path = DEFAULT_MIGRATIONS_DIR,
) -> list[str]:
    """Apply every not-yet-applied migration, oldest first. Idempotent.

    Returns the ids applied by this call (empty when the schema is current).
    """
    ensure_version_table(conn)
    done = applied_migrations(conn)
    newly_applied: list[str] = []

    for path in list_migrations(migrations_dir):
        migration_id = path.name[: -len(".sql")]
        if not _MIGRATION_ID_PATTERN.fullmatch(migration_id):
            raise MigrationError(f"invalid migration id: {path.name}")
        if migration_id in done:
            continue

        script = path.read_text(encoding="utf-8")
        # One atomic unit: DDL + version-table insert. Migration ids are
        # validated identifiers from the repository tree, so embedding them
        # in the script literal is safe; executescript cannot bind params.
        literal = migration_id.replace("'", "''")
        unit = (
            "BEGIN IMMEDIATE;\n"
            f"{script}\n"
            f"INSERT INTO {_VERSION_TABLE} (migration_id, applied_at) "
            f"VALUES ('{literal}', strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
            f"INSERT INTO {_META_TABLE} (key, value) "
            f"VALUES ('last_migration_id', '{literal}') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;\n"
            "COMMIT;"
        )
        try:
            conn.executescript(unit)
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise MigrationError(f"migration {migration_id} failed: {exc}") from exc
        newly_applied.append(migration_id)

    return newly_applied


def schema_version(conn: sqlite3.Connection) -> str | None:
    ensure_version_table(conn)
    row = conn.execute(
        f"SELECT value FROM {_META_TABLE} WHERE key='schema_version'"
    ).fetchone()
    return None if row is None else str(row[0])
