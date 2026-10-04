"""SQLite adapter for the host settings table (migration 0022).

The veto-response cut (user dogfood first-verification veto) made the
rollout stage page-movable (``POST /api/settings/mode``), and a durable word
needs a home that is *not* a §5.1 aggregate: the stage is a process-level
declaration (:mod:`elc.teaching.rollout`'s own reading), so it lives in a
generic host-level key/value table — ``app_setting`` (key PRIMARY KEY, value
NOT NULL). The table is deliberately generic: the living-world program
(W-1-0) reuses it for world settings in its own follow-up migration (0023),
and no second settings table gets minted.

**Two faces, minimal.** ``get`` answers the stored word or ``None`` (an
absent key is the honest "not chosen yet" — the caller's read order, not
this store, decides what absence means); ``set`` is one upsert — the same
key written twice leaves exactly one row with the newest word. This cut
writes exactly one key (``rollout_stage``, the §12 word verbatim); the store
carries no vocabulary of its own and refuses nothing — the word validation
belongs to the callers that know the key's grammar.

**One short transaction per write, no clock.** The same posture as every
sibling adapter: the write owns one :func:`short_transaction`, the fence
check sits inside the write transaction (the card store's shape restated —
the adopted epoch must still be the newest epoch row, §24 restart
ownership; a fenced epoch raises :class:`StaleEpochError` and the
transaction rolls back whole), and the store reads no clock — the only fact
is the word itself. Reads are plain SELECTs on the shared connection (the
caller's thread).

All SQL is a fixed literal with bound parameters — no identifier assembly.
"""

from __future__ import annotations

import sqlite3

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction

#: The one key this cut writes — the rollout tier's §12 word, verbatim
#: (``Study-first`` keeps its hyphen). The constant is the single spelling
#: both the reader (:meth:`elc.host.open_host`'s persisted leg) and the
#: writer (``POST /api/settings/mode``) import, so a renamed key cannot
#: fork into two spellings.
APP_SETTING_ROLLOUT_STAGE_KEY = "rollout_stage"


class AppSettingStore:
    """The ``app_setting`` key/value face — get/set, upsert semantics."""

    def __init__(self, db: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._db = db
        self._fence = fence

    def get(self, key: str) -> str | None:
        """The stored word for ``key``, or ``None`` when absent."""

        row = self._db.execute(
            "SELECT value FROM app_setting WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row[0])

    def set(self, key: str, value: str) -> None:
        """Upsert one word — the same key written twice leaves one row."""

        with short_transaction(self._db):
            row = self._db.execute(
                "SELECT MAX(epoch) FROM runtime_epoch"
            ).fetchone()
            newest = None if row is None or row[0] is None else int(row[0])
            if newest is None or newest != self._fence.current:
                raise StaleEpochError(
                    f"app_setting epoch={self._fence.current}"
                    f" fenced by db epoch={newest}"
                )
            self._db.execute(
                "INSERT INTO app_setting (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
