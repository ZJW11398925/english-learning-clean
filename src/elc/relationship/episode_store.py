"""SQLite durable store for the Episode projection (Phase 4 P4-3).

docs/DATA_MODEL.md §5.3 owns the row; elc.relationship.episode owns what the
row *means*. This module is the durable executor — the P4-1
``SqliteRelationshipStore`` precedent: the pure rebuild lives above, every
byte that reaches the disk lives here, and the table arrives with migration
0010 (nothing here creates schema).

Discipline:

- every write is one ``short_transaction`` (docs/DATA_MODEL.md §2 short
  atomic commits) and checks the store epoch against the newest durable epoch
  before anything is written; a stale store is a programming error and raises
  (the repo-wide fence convention);
- ``upsert_episode`` is **idempotent**: the same episode id with the same
  content version returns the id and writes nothing (the crash-retry face —
  the version *is* the content digest, so a replay proves there is nothing
  new), and a different version replaces the content columns and stamps a
  fresh ``updated_at`` from the store's own clock;
- a different *version* is what "the episode moved" means. The version is a
  derived digest, not a counter (elc.relationship.episode
  ``episode_version_for``), so the store never compares it for order: it
  compares it for equality, and "前进" is spelled "differs" here — the
  canonical text pins no monotonic episode counter;
- ``updated_at`` is never taken from the caller's record: the durable clock
  is this module's, exactly as in the relationship / teaching stores. That is
  also why it is not part of the version: a rebuild is a pure function of the
  transcript and must not change the row's content digest by running later.

All SQL is a fixed literal with bound parameters — no identifier assembly, no
runtime value in any statement text. The two list columns follow migration
0009/0004's storage note: a canonical list stores as JSON text with sorted
keys, never as a second table.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import TypeVar

from elc.conversation.types import ConversationStatus
from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    EpisodeId,
    Err,
    Ok,
    Result,
)
from elc.relationship.episode import EpisodeRecord, EpisodeView

__all__ = ["StaleStoreEpochError", "SqliteEpisodeStore"]

T = TypeVar("T")


class StaleStoreEpochError(StaleEpochError):
    """This store's epoch is no longer the newest durable epoch."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _list_document(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), sort_keys=True, separators=(",", ":"))


def _list_from_document(document: str) -> tuple[str, ...]:
    loaded = json.loads(document)
    return tuple(str(item) for item in loaded)


class SqliteEpisodeStore:
    """Durable ``episode`` rows: the §5.3 projection's write and read face.

    One conversation holds one episode in Local V1 (the stance declared in
    elc.relationship.episode), so ``conversation_id`` is UNIQUE in migration
    0010 and every read is keyed by it.
    """

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"episode store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- the write unit ----------------------------------------------------

    def upsert_episode(self, record: EpisodeRecord) -> Result[EpisodeId]:
        """Land one rebuilt episode; timestamps are the store's.

        Three outcomes, and nothing else:

        - **new row** — inserted;
        - **same version** — the content digest proves the rebuild saw the
          same truth: the id is returned and *nothing* is written (the
          idempotent replay; not even ``updated_at`` moves, because there was
          no write to stamp). The same version with *different* content is a
          ``CONFLICT``: the digest is derived from exactly the content
          columns, so that combination means the derivation changed under a
          version it did not bump (a programming error, never a rewrite);
        - **different version** — the episode moved: the content columns are
          replaced and ``updated_at`` is stamped from this store's clock.

        A row whose ``conversation_id`` is not the incoming record's is a
        ``CONFLICT`` too: the episode id is derived from the conversation, so
        an id collision across conversations is an error, not a move.
        """

        episode_id = record.episode_id
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._row(episode_id)
                if existing is None:
                    self._insert(record, now=_now())
                    return Ok(episode_id)
                if existing.conversation_id != record.conversation_id:
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"episode {episode_id} belongs to conversation"
                        f" {existing.conversation_id}, not"
                        f" {record.conversation_id}; the id is derived from"
                        " the conversation (DATA_MODEL §1.2 stable ids)",
                    )
                if existing.version == record.version:
                    if _same_content(existing, record):
                        return Ok(episode_id)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"episode {episode_id} already carries version"
                        f" {record.version} with a different content; the"
                        " version is the content digest, so the same version"
                        " must mean the same episode (elc.relationship"
                        ".episode.episode_version_for)",
                    )
                self._replace(record, now=_now())
                return Ok(episode_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def _insert(self, record: EpisodeRecord, *, now: str) -> None:
        self._conn.execute(
            "INSERT INTO episode ("
            " episode_id, conversation_id, version,"
            " source_turn_sequence_start, source_turn_sequence_end, summary,"
            " open_threads, recent_events, status, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(record.episode_id),
                str(record.conversation_id),
                record.version,
                int(record.source_turn_sequence_start),
                int(record.source_turn_sequence_end),
                record.summary,
                _list_document(record.open_threads),
                _list_document(record.recent_events),
                record.status.value,
                now,
            ),
        )

    def _replace(self, record: EpisodeRecord, *, now: str) -> None:
        self._conn.execute(
            "UPDATE episode SET version = ?, source_turn_sequence_start = ?,"
            " source_turn_sequence_end = ?, summary = ?, open_threads = ?,"
            " recent_events = ?, status = ?, updated_at = ?"
            " WHERE episode_id = ?",
            (
                record.version,
                int(record.source_turn_sequence_start),
                int(record.source_turn_sequence_end),
                record.summary,
                _list_document(record.open_threads),
                _list_document(record.recent_events),
                record.status.value,
                now,
                str(record.episode_id),
            ),
        )

    # -- reads -------------------------------------------------------------

    def get_episode(
        self, conversation_id: ConversationId
    ) -> Result[EpisodeRecord | None]:
        """The conversation's episode row (``None`` = never projected)."""

        row = self._conn.execute(
            "SELECT episode_id, conversation_id, version,"
            " source_turn_sequence_start, source_turn_sequence_end, summary,"
            " open_threads, recent_events, status, updated_at"
            " FROM episode WHERE conversation_id = ?",
            (str(conversation_id),),
        ).fetchone()
        return Ok(None if row is None else self._record(row))

    def episode_view(
        self, conversation_id: ConversationId
    ) -> Result[EpisodeView | None]:
        """The prompt-facing view of that row (content columns only)."""

        record = self.get_episode(conversation_id)
        if isinstance(record, Err):
            return record
        return Ok(None if record.value is None else record.value.as_view())

    # -- internals ---------------------------------------------------------

    def _row(self, episode_id: EpisodeId) -> EpisodeRecord | None:
        row = self._conn.execute(
            "SELECT episode_id, conversation_id, version,"
            " source_turn_sequence_start, source_turn_sequence_end, summary,"
            " open_threads, recent_events, status, updated_at"
            " FROM episode WHERE episode_id = ?",
            (str(episode_id),),
        ).fetchone()
        return None if row is None else self._record(row)

    def _record(self, row: sqlite3.Row) -> EpisodeRecord:
        return EpisodeRecord(
            episode_id=EpisodeId(str(row[0])),
            conversation_id=ConversationId(str(row[1])),
            version=str(row[2]),
            source_turn_sequence_start=int(row[3]),
            source_turn_sequence_end=int(row[4]),
            summary=str(row[5]),
            open_threads=_list_from_document(str(row[6])),
            recent_events=_list_from_document(str(row[7])),
            status=ConversationStatus(str(row[8])),
            updated_at=str(row[9]),
        )


def _same_content(durable: EpisodeRecord, incoming: EpisodeRecord) -> bool:
    """Whether the two rows carry the same *content* (timestamps excluded).

    The comparison the idempotent-replay rule needs: ``updated_at`` is the
    store's clock, so two rebuilds of unchanged truth differ only there.
    """

    return (
        durable.source_turn_sequence_start == incoming.source_turn_sequence_start
        and durable.source_turn_sequence_end == incoming.source_turn_sequence_end
        and durable.summary == incoming.summary
        and durable.open_threads == incoming.open_threads
        and durable.recent_events == incoming.recent_events
        and durable.status == incoming.status
    )
