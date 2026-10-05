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

#: The settings-page provider face (user veto: model/endpoint must be
#: page-settable, not launch-command-only). Two keys, both optional —
#: a saved pair overrides the launch arguments from the next open on (the
#: page is the user's chosen place for it; single-principal local app).
APP_SETTING_PROVIDER_BASE_URL_KEY = "provider_base_url"
APP_SETTING_PROVIDER_MODEL_KEY = "provider_model"
#: The model-profile face (user direction: several saved models, switched
#: any time): each profile is one row under this prefix, the row's value a
#: strict JSON document (name / base_url / model / api_key-or-null) written
#: only by the profile write face — a row that fails the face's parse is
#: omitted from the read face, never guessed into a profile.
APP_SETTING_PROVIDER_PROFILE_PREFIX = "provider_profile:"
#: Which profile the live pair came from ("" = custom edits / launch args).
APP_SETTING_PROVIDER_ACTIVE_PROFILE_KEY = "provider_active_profile"
#: The page-saved API key (startup-system cut, user direction: nothing
#: provider-shaped is fixed at launch). Stored in the local single-user
#: app.db only — never returned by any read face (the GET answers
#: ``api_key_set`` alone), never logged, never in any transcript; the
#: RA §24.3 surfaces are unchanged. A saved key takes precedence over the
#: launch environment's source at send time.
APP_SETTING_PROVIDER_API_KEY_KEY = "provider_api_key"
#: The W-L language pair. ``reply_language`` is the ``[response]`` section's
#: language-row word (``zh`` / ``en`` / ``follow`` — the vocabulary lives on
#: :data:`elc.persona.types.RESPONSE_LANGUAGE_WORDS`; the coordinator's
#: best-effort port reads this key per turn). ``ui_language`` is the page's
#: own presentation word (``zh`` / ``en`` — the world inbox's bilingual
#: face; full-page i18n is registered out of scope). Both are stored only
#: by the web write faces, both answer the caller's default when absent —
#: this store carries no vocabulary and substitutes nothing.
APP_SETTING_REPLY_LANGUAGE_KEY = "reply_language"
APP_SETTING_UI_LANGUAGE_KEY = "ui_language"


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

    def items(self, prefix: str) -> list[tuple[str, str]]:
        """Every ``(key, value)`` whose key starts with ``prefix``, key-ordered.

        The provider-profile face's one read (multiple rows under one prefix
        in the key-addressed table); a plain SELECT on the shared connection
        like ``get`` — the caller's thread, no fence (a read fences nothing).
        """

        rows = self._db.execute(
            "SELECT key, value FROM app_setting WHERE key LIKE ?"
            " ORDER BY key",
            (prefix + "%",),
        ).fetchall()
        return [(str(key), str(value)) for key, value in rows]

    def delete(self, key: str) -> None:
        """Remove one row — absent is a no-op (idempotent delete)."""

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
                "DELETE FROM app_setting WHERE key = ?", (key,)
            )
