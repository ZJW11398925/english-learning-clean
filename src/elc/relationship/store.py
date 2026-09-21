"""SQLite durable store for the Relationship domain (Phase 4 P4-1).

The Relationship domain owns Persona×User memory truth (docs/DOMAIN_MODEL.md
§5), so its durable executor lives in the domain package — the
conversation-store / learning-store / teaching-store precedent. The §18
authority face is elc.relationship.controller; this module executes the §5
write flow's last leg:

    Relationship Recorder proposal → validate/dedupe → canonical memory

One write unit is one short transaction (docs/DATA_MODEL.md §1.3 append-first
for facts; §2 short atomic commits):

- **idempotent replay** — a row with the incoming memory id already exists:
  the same semantic payload returns that id and writes nothing (the
  crash-retry face), a different payload is a CONFLICT;
- **dedupe** — an ACTIVE row of the same (persona, user, memory_type) whose
  canonical content matches after normalization (the rule lives in
  elc.relationship.validation) is the same memory: its id is returned and
  nothing is written;
- **append-first supersede** — a declared ``supersedes_memory_id`` flips the
  old row to SUPERSEDED and inserts the replacement as the new ACTIVE row in
  the same transaction. The old row is never rewritten in place, never
  physically deleted, and its own supersede chain stays intact (§1.3
  "不原地抹除历史");
- **insert** — otherwise the row is appended.

Fencing: every write checks the store epoch against the newest durable epoch
before anything is written (the teaching-store precedent; a stale store is a
programming error and raises). Cross-scope reads do not exist: every read is
scoped to one (persona_id, user_id) pair, and a supersede pointer that names
another persona's row is refused with AUTHORITY_VIOLATION rather than
followed (DOMAIN_MODEL §17 "Relationship 不跨 Persona 泄漏"; BF-05 §29).

All SQL is a fixed literal with bound parameters — no identifier assembly,
no runtime value in any statement text. JSON columns follow migration 0009's
storage note (the 0004 qualifiers precedent: arrays are JSON text with sorted
keys).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime
from typing import TypeVar

from elc.platform.db.epoch import RuntimeEpochFence, StaleEpochError
from elc.platform.db.tx import short_transaction
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    RelationshipMemoryId,
    Result,
    TurnId,
    UserId,
)
from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    MemoryStatus,
    PersistenceAuthorization,
    RelationshipMemoryRecord,
    RelationshipMemorySummaryEntry,
    RelationshipMemoryType,
    RelationshipView,
    SamePersonaExistingRelationshipSummary,
)
from elc.relationship.validation import find_duplicate

__all__ = ["StaleStoreEpochError", "SqliteRelationshipStore"]

T = TypeVar("T")


class StaleStoreEpochError(StaleEpochError):
    """This store's epoch is no longer the newest durable epoch."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _err(code: DomainErrorCode, message: str) -> Err[T]:
    return Err(DomainError(code=code, message=message))


def _array_document(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), sort_keys=True, separators=(",", ":"))


def _array_from_document(document: str) -> tuple[str, ...]:
    loaded = json.loads(document)
    return tuple(str(item) for item in loaded)


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


class SqliteRelationshipStore:
    """Durable relationship_memory rows: the §5 flow's last leg + reads."""

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- fencing -----------------------------------------------------------

    def _require_current_epoch(self) -> None:
        row = self._conn.execute("SELECT MAX(epoch) FROM runtime_epoch").fetchone()
        newest = None if row is None or row[0] is None else int(row[0])
        if newest is None or newest != self._fence.current:
            raise StaleStoreEpochError(
                f"relationship store epoch={self._fence.current} fenced by"
                f" db epoch={newest}"
            )

    # -- the write unit ----------------------------------------------------

    def commit_memory(
        self, record: RelationshipMemoryRecord
    ) -> Result[RelationshipMemoryId]:
        """One durable memory write (§5 last leg); timestamps are the store's.

        The caller (the controller, after validation and the sensitivity
        gate) hands a fully assembled row; ``created_at`` / ``updated_at`` on
        it are ignored — the durable clock is this module's, exactly as in
        the teaching store.
        """

        memory_id = record.relationship_memory_id
        try:
            with short_transaction(self._conn):
                self._require_current_epoch()
                existing = self._memory_by_id(memory_id)
                if existing is not None:
                    if _same_payload(existing, record):
                        return Ok(memory_id)
                    return _err(
                        DomainErrorCode.CONFLICT,
                        f"memory {memory_id} already exists with a different"
                        " payload; a re-proposal must be identical"
                        " (docs/DATA_MODEL.md §1.2 stable ids)",
                    )
                if record.supersedes_memory_id is not None:
                    executed = self._supersede(record)
                    if isinstance(executed, Err):
                        return executed
                    if not executed.value:
                        # Degenerate no-op: the "replacement" is the same text
                        # as the row it would replace. Nothing is written.
                        return Ok(record.supersedes_memory_id)
                else:
                    duplicate = find_duplicate(
                        memory_type=record.memory_type,
                        canonical_content=record.canonical_content,
                        existing=self._active_rows(
                            record.persona_id, record.user_id
                        ),
                    )
                    if duplicate is not None:
                        # Dedupe: the same memory is already ACTIVE. Nothing
                        # is written and the durable row stays canonical.
                        return Ok(duplicate.relationship_memory_id)
                now = _now()
                self._insert(record, now=now)
                return Ok(memory_id)
        except sqlite3.IntegrityError as exc:
            return _err(DomainErrorCode.CONFLICT, str(exc))

    def _supersede(
        self, record: RelationshipMemoryRecord
    ) -> Result[bool]:
        """Execute one declared supersede (append-first); caller holds the tx.

        ``Ok(True)`` = the target row was flipped and the caller appends the
        replacement; ``Ok(False)`` = degenerate no-op (the replacement's
        content equals the target's), nothing to write; ``Err`` = refused.

        A declared update never silently becomes an append and never silently
        disappears: every refusal below is returned as an Err, and the caller
        branches on the value instead of assuming it ran.
        """

        target_id = record.supersedes_memory_id
        assert target_id is not None  # caller checked
        target = self._memory_by_id(target_id)
        if target is None:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"supersede target not found: {target_id}",
            )
        if (
            target.persona_id != record.persona_id
            or target.user_id != record.user_id
        ):
            return _err(
                DomainErrorCode.AUTHORITY_VIOLATION,
                f"memory {target_id} belongs to another Persona×User pair; a"
                " relationship write never crosses personas (DOMAIN_MODEL §17;"
                " BF-05 §29)",
            )
        if target.memory_type is not record.memory_type:
            return _err(
                DomainErrorCode.VALIDATION_FAILED,
                f"memory {target_id} is a {target.memory_type.value}; a"
                f" {record.memory_type.value} never supersedes it (§5 type"
                " boundary)",
            )
        if target.status is not MemoryStatus.ACTIVE:
            return _err(
                DomainErrorCode.CONFLICT,
                f"memory {target_id} is {target.status.value}; only an ACTIVE"
                " memory can be superseded (append-first never rewrites"
                " history)",
            )
        if (
            find_duplicate(
                memory_type=record.memory_type,
                canonical_content=record.canonical_content,
                existing=(target,),
            )
            is not None
        ):
            return Ok(False)
        updated = self._conn.execute(
            "UPDATE relationship_memory SET status = ?, updated_at = ?"
            " WHERE relationship_memory_id = ? AND status = ?",
            (
                MemoryStatus.SUPERSEDED.value,
                _now(),
                str(target_id),
                MemoryStatus.ACTIVE.value,
            ),
        )
        if updated.rowcount != 1:
            return _err(
                DomainErrorCode.CONFLICT,
                f"memory {target_id} changed while superseding it",
            )
        return Ok(True)

    def _insert(self, record: RelationshipMemoryRecord, *, now: str) -> None:
        self._conn.execute(
            "INSERT INTO relationship_memory ("
            " relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization,"
            " created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(record.relationship_memory_id),
                str(record.persona_id),
                str(record.user_id),
                record.memory_type.value,
                record.provenance.value,
                record.canonical_content,
                _optional(record.source_turn_id),
                record.status.value,
                _array_document(
                    tuple(str(item) for item in record.source_turn_ids)
                ),
                _array_document(record.provenance_refs),
                record.confidence,
                _optional(record.supersedes_memory_id),
                record.recorder_version,
                _optional(record.validator_version),
                record.sensitivity_class.value,
                record.persistence_authorization.value,
                now,
                now,
            ),
        )

    # -- reads -------------------------------------------------------------

    def get_relationship_view(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[RelationshipView]:
        """The ACTIVE memories of one Persona×User pair (§4 view).

        Always one pair: the scope is bound into the query, so the view can
        never contain another persona's memory (DOMAIN_MODEL §17).
        """

        rows = self._conn.execute(
            "SELECT relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization, created_at,"
            " updated_at FROM relationship_memory"
            " WHERE persona_id = ? AND user_id = ? AND status = ?"
            " ORDER BY created_at, relationship_memory_id",
            (str(persona_id), str(user_id), MemoryStatus.ACTIVE.value),
        ).fetchall()
        return Ok(
            RelationshipView(
                persona_id=persona_id,
                user_id=user_id,
                active_memories=tuple(self._record(row) for row in rows),
            )
        )

    def get_existing_summary(
        self, persona_id: PersonaId, user_id: UserId
    ) -> Result[SamePersonaExistingRelationshipSummary]:
        """The BF-05 ``SamePersonaExistingRelationshipSummary`` of one pair
        (the Recorder's second allow-listed input): ACTIVE rows only, in
        durable order, never a cross-persona scan."""

        rows = self._conn.execute(
            "SELECT relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization, created_at,"
            " updated_at FROM relationship_memory"
            " WHERE persona_id = ? AND user_id = ? AND status = ?"
            " ORDER BY created_at, relationship_memory_id",
            (str(persona_id), str(user_id), MemoryStatus.ACTIVE.value),
        ).fetchall()
        return Ok(
            SamePersonaExistingRelationshipSummary(
                persona_id=persona_id,
                user_id=user_id,
                memories=tuple(
                    RelationshipMemorySummaryEntry(
                        relationship_memory_id=record.relationship_memory_id,
                        memory_type=record.memory_type,
                        provenance=record.provenance,
                        canonical_content=record.canonical_content,
                        status=record.status,
                        confidence=record.confidence,
                    )
                    for record in (self._record(row) for row in rows)
                ),
            )
        )

    def get_scoped_memory(
        self,
        persona_id: PersonaId,
        user_id: UserId,
        memory_id: RelationshipMemoryId,
    ) -> Result[RelationshipMemoryRecord | None]:
        """One memory, only if it belongs to that Persona×User pair.

        The scoped read face: a row of another pair reads as ``None`` — not as
        a refusal and not as the row (DOMAIN_MODEL §17; BF-05 §29: another
        persona's memory is never visible here, not even its existence).
        """

        row = self._conn.execute(
            "SELECT relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization, created_at,"
            " updated_at FROM relationship_memory"
            " WHERE relationship_memory_id = ? AND persona_id = ? AND user_id = ?",
            (str(memory_id), str(persona_id), str(user_id)),
        ).fetchone()
        if row is None:
            return Ok(None)
        return Ok(self._record(row))

    # -- internals ---------------------------------------------------------

    def _memory_by_id(
        self, memory_id: RelationshipMemoryId
    ) -> RelationshipMemoryRecord | None:
        row = self._conn.execute(
            "SELECT relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization, created_at,"
            " updated_at FROM relationship_memory"
            " WHERE relationship_memory_id = ?",
            (str(memory_id),),
        ).fetchone()
        return None if row is None else self._record(row)

    def _active_rows(
        self, persona_id: PersonaId, user_id: UserId
    ) -> tuple[RelationshipMemoryRecord, ...]:
        rows = self._conn.execute(
            "SELECT relationship_memory_id, persona_id, user_id, memory_type,"
            " provenance, canonical_content, source_turn_id, status,"
            " source_turn_ids, provenance_refs, confidence,"
            " supersedes_memory_id, recorder_version, validator_version,"
            " sensitivity_class, persistence_authorization, created_at,"
            " updated_at FROM relationship_memory"
            " WHERE persona_id = ? AND user_id = ? AND status = ?"
            " ORDER BY created_at, relationship_memory_id",
            (str(persona_id), str(user_id), MemoryStatus.ACTIVE.value),
        ).fetchall()
        return tuple(self._record(row) for row in rows)

    def _record(self, row: sqlite3.Row) -> RelationshipMemoryRecord:
        return RelationshipMemoryRecord(
            relationship_memory_id=RelationshipMemoryId(str(row[0])),
            persona_id=PersonaId(str(row[1])),
            user_id=UserId(str(row[2])),
            memory_type=RelationshipMemoryType(str(row[3])),
            provenance=MemoryProvenance(str(row[4])),
            canonical_content=str(row[5]),
            source_turn_id=None if row[6] is None else TurnId(str(row[6])),
            status=MemoryStatus(str(row[7])),
            source_turn_ids=tuple(
                TurnId(item) for item in _array_from_document(str(row[8]))
            ),
            provenance_refs=_array_from_document(str(row[9])),
            confidence=None if row[10] is None else float(row[10]),
            supersedes_memory_id=(
                None if row[11] is None else RelationshipMemoryId(str(row[11]))
            ),
            recorder_version=str(row[12]),
            validator_version=None if row[13] is None else str(row[13]),
            sensitivity_class=MemorySensitivityClass(str(row[14])),
            persistence_authorization=PersistenceAuthorization(str(row[15])),
            created_at=str(row[16]),
            updated_at=str(row[17]),
        )


def _same_payload(
    durable: RelationshipMemoryRecord, incoming: RelationshipMemoryRecord
) -> bool:
    """The idempotent-replay comparison: every semantic field, no timestamps
    (the durable clock is the store's, so two retries differ only there)."""

    ignored = {"created_at", "updated_at"}
    return all(
        getattr(durable, field.name) == getattr(incoming, field.name)
        for field in dataclass_fields(durable)
        if field.name not in ignored
    )
