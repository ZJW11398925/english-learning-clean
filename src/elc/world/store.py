"""The World bounded context's durable face — :class:`SqliteWorldStore`
(migration 0023's three identity tables).

W-1-0's write and read face over ``world`` / ``world_actor`` /
``world_conversation``. Identity only: the store binds worlds, actors and
conversations and reads them back; it launches no world behaviour (the
package banner's boundary is the store's too).

Idempotence is the seeded shape (W-1-4's host seed will sit on it):

- ``create_world``: the same id replayed with the same shape (name +
  template) is an ``Ok`` no-op; the same id with a different shape is a
  ``CONFLICT``;
- ``bind_actor``: the same actor tuple replayed is a no-op; a different
  shape under a taken actor id, or a (world, persona) pair another actor
  already holds (the table's UNIQUE), is a ``CONFLICT``;
- ``bind_conversation``: the same binding tuple replayed is a no-op; a
  different shape under a taken binding id, or a conversation bound to a
  different (world, actor) pair (the column's UNIQUE), is a ``CONFLICT``.

Dangling references are value-semantics refusals, never exceptions: a
write naming a world / persona card / conversation that does not exist
comes back ``NOT_FOUND`` — the database's own foreign keys (the
connection profile turns them on) are what actually refuse, and the store
wraps the refusal into the ``Result`` vocabulary. An actor that exists but
belongs to another world is refused by the composite FK the migration
spells — the store surfaces it as ``CONFLICT`` (the actor and the world
both exist; the pairing does not).

Error vocabulary (the domain ``Result`` words this store answers with):
``CONFLICT`` = a shape or uniqueness clash with an existing row;
``NOT_FOUND`` = a referenced identity (world, persona card, conversation)
does not exist.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    ConversationId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    PersonaId,
    Result,
)
from elc.world.types import (
    WorldActorRecord,
    WorldConversationRecord,
    WorldRecord,
)

__all__ = ["SqliteWorldStore"]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


class SqliteWorldStore:
    """The identity-binding write and read face over migration 0023.

    Same shape as every store over the shared app.db connection
    (:class:`~elc.world_lore.store.SqliteWorldLoreStore`,
    :class:`~elc.persona.card_store.SqliteCharacterCardStore`): every
    statement is fixed literal text with bound parameters, writes go
    through one short transaction each, reads are plain queries.

    ``fence`` is the house constructor shape (every app.db store takes the
    shared epoch fence); migration 0023 carries no ``write_epoch`` column,
    so the fence is held unused — identity rows are creator-stamped, not
    epoch-stamped.
    """

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- write face ----------------------------------------------------------

    def create_world(
        self,
        world_id: str,
        name: str,
        template_world_id: str | None,
        now: str,
    ) -> Result[WorldRecord]:
        """Create one world, idempotently by id (W-1-4's seed sits here).

        A replay of the same id with the same name and the same template
        answers the stored row unchanged; a same-id different-shape call
        answers ``CONFLICT`` — worlds do not rename through the create
        face. A dangling ``template_world_id`` is refused by the table's
        own FK and surfaces as ``NOT_FOUND``.
        """

        existing = self._world_row(world_id)
        if existing is not None:
            if (existing.name, existing.template_world_id) == (name, template_world_id):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"world {world_id!r} already exists with a different"
                        " shape; create_world does not rename or re-parent"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world (world_id, name, template_world_id, created_at)"
                " VALUES (?, ?, ?, ?)",
                (world_id, name, template_world_id, now),
            )
        except sqlite3.Error as exc:
            # The ml3R LOW-1 judgement (elc.world_lore.store): when BEGIN
            # itself failed, nothing of ours began — in_transaction then
            # belongs to the caller and must not be rolled back here; a
            # failing ROLLBACK of our own must not break the Result
            # contract.
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"world {world_id!r} not created: its template world"
                        f" does not exist ({exc})"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        return Ok(
            WorldRecord(
                world_id=world_id,
                name=name,
                template_world_id=template_world_id,
                created_at=now,
            )
        )

    def bind_actor(
        self,
        actor_id: str,
        world_id: str,
        persona_id: str,
        now: str,
    ) -> Result[WorldActorRecord]:
        """Bind one actor into one world through one character card.

        The same tuple replayed answers the stored row unchanged. A taken
        actor id with a different shape answers ``CONFLICT``; so does a
        (world, persona) pair another actor already holds (the table's
        UNIQUE — one card speaks as at most one actor per world). A world
        or a persona card that does not exist is refused by the FKs and
        surfaces as ``NOT_FOUND``.
        """

        existing = self._actor_row(actor_id)
        if existing is not None:
            if (
                existing.world_id,
                str(existing.persona_id),
            ) == (world_id, persona_id):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"actor {actor_id!r} already binds world"
                        f" {existing.world_id!r} to persona"
                        f" {existing.persona_id!r}"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_actor (actor_id, world_id, persona_id, created_at)"
                " VALUES (?, ?, ?, ?)",
                (actor_id, world_id, persona_id, now),
            )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=self._refusal_code(exc),
                    message=f"actor {actor_id!r} not bound: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(
            WorldActorRecord(
                actor_id=actor_id,
                world_id=world_id,
                persona_id=PersonaId(persona_id),
                created_at=now,
            )
        )

    def bind_conversation(
        self,
        binding_id: str,
        world_id: str,
        actor_id: str,
        conversation_id: str,
        now: str,
    ) -> Result[WorldConversationRecord]:
        """Bind one conversation into one world through one of its actors.

        The same tuple replayed answers the stored row unchanged. A taken
        binding id with a different shape answers ``CONFLICT``; so does a
        conversation that is already bound to a different (world, actor)
        pair (the column's UNIQUE — one conversation, one world). The
        composite FK refuses an actor that does not belong to the named
        world; the store surfaces that pairing refusal as ``CONFLICT``
        (both identities exist — the pair does not). A dangling world,
        actor or conversation surfaces as ``NOT_FOUND``.
        """

        existing = self._conversation_row(binding_id)
        if existing is not None:
            if (
                existing.world_id,
                existing.actor_id,
                str(existing.conversation_id),
            ) == (world_id, actor_id, conversation_id):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"binding {binding_id!r} already binds conversation"
                        f" {existing.conversation_id!r} into world"
                        f" {existing.world_id!r} through actor"
                        f" {existing.actor_id!r}"
                    ),
                )
            )
        if self._world_row(world_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"binding {binding_id!r} not written: world"
                        f" {world_id!r} does not exist"
                    ),
                )
            )
        if self._actor_row(actor_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"binding {binding_id!r} not written: actor"
                        f" {actor_id!r} does not exist"
                    ),
                )
            )
        if self._conversation_exists(conversation_id) is False:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"binding {binding_id!r} not written: conversation"
                        f" {conversation_id!r} does not exist"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_conversation ("
                " binding_id, world_id, actor_id, conversation_id, created_at"
                ") VALUES (?, ?, ?, ?, ?)",
                (binding_id, world_id, actor_id, conversation_id, now),
            )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    # Past the three NOT_FOUND pre-checks above, the
                    # database's own refusals are exactly two: the
                    # conversation column's UNIQUE (already bound elsewhere
                    # — a CONFLICT) and the composite FK (an actor that
                    # does not belong to this world — also a CONFLICT: both
                    # identities exist, the pairing does not). Both refusals
                    # live in the table, not here — deleting either
                    # constraint turns this face permissive, never this
                    # pre-check.
                    code=self._refusal_code(exc, fk=DomainErrorCode.CONFLICT),
                    message=f"binding {binding_id!r} not written: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(
            WorldConversationRecord(
                binding_id=binding_id,
                world_id=world_id,
                actor_id=actor_id,
                conversation_id=ConversationId(conversation_id),
                created_at=now,
            )
        )

    # -- read face -----------------------------------------------------------

    def get_world(self, world_id: str) -> WorldRecord | None:
        """One world by id; ``None`` when the id is unknown."""

        return self._world_row(world_id)

    def list_worlds(self) -> tuple[WorldRecord, ...]:
        """Every world, id-ascending (the durable order — deterministic
        reads are content, not an implementation detail)."""

        rows = self._conn.execute(
            "SELECT world_id, name, template_world_id, created_at"
            " FROM world ORDER BY world_id ASC"
        ).fetchall()
        return tuple(
            WorldRecord(
                world_id=str(row[0]),
                name=str(row[1]),
                template_world_id=None if row[2] is None else str(row[2]),
                created_at=str(row[3]),
            )
            for row in rows
        )

    def actors_of(self, world_id: str) -> tuple[WorldActorRecord, ...]:
        """One world's actors, id-ascending."""

        rows = self._conn.execute(
            "SELECT actor_id, world_id, persona_id, created_at"
            " FROM world_actor WHERE world_id = ? ORDER BY actor_id ASC",
            (world_id,),
        ).fetchall()
        return tuple(
            WorldActorRecord(
                actor_id=str(row[0]),
                world_id=str(row[1]),
                persona_id=PersonaId(str(row[2])),
                created_at=str(row[3]),
            )
            for row in rows
        )

    def conversations_of(self, world_id: str) -> tuple[WorldConversationRecord, ...]:
        """One world's conversation bindings, binding-id ascending."""

        rows = self._conn.execute(
            "SELECT binding_id, world_id, actor_id, conversation_id, created_at"
            " FROM world_conversation WHERE world_id = ? ORDER BY binding_id ASC",
            (world_id,),
        ).fetchall()
        return tuple(
            WorldConversationRecord(
                binding_id=str(row[0]),
                world_id=str(row[1]),
                actor_id=str(row[2]),
                conversation_id=ConversationId(str(row[3])),
                created_at=str(row[4]),
            )
            for row in rows
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _refusal_code(
        exc: sqlite3.Error, fk: DomainErrorCode = DomainErrorCode.NOT_FOUND
    ) -> DomainErrorCode:
        """Map the database's own refusal to the store's vocabulary: a
        UNIQUE clash is a ``CONFLICT`` (the identities exist, the shapes
        collide); a FOREIGN KEY refusal is ``fk`` — ``NOT_FOUND`` where a
        referenced identity is missing (world / persona / template /
        conversation), ``CONFLICT`` on the composite FK (world and actor
        both exist; the pairing does not)."""

        text = str(exc)
        if "UNIQUE constraint failed" in text:
            return DomainErrorCode.CONFLICT
        return fk

    def _world_row(self, world_id: str) -> WorldRecord | None:
        row = self._conn.execute(
            "SELECT world_id, name, template_world_id, created_at"
            " FROM world WHERE world_id = ?",
            (world_id,),
        ).fetchone()
        if row is None:
            return None
        return WorldRecord(
            world_id=str(row[0]),
            name=str(row[1]),
            template_world_id=None if row[2] is None else str(row[2]),
            created_at=str(row[3]),
        )

    def _actor_row(self, actor_id: str) -> WorldActorRecord | None:
        row = self._conn.execute(
            "SELECT actor_id, world_id, persona_id, created_at"
            " FROM world_actor WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        if row is None:
            return None
        return WorldActorRecord(
            actor_id=str(row[0]),
            world_id=str(row[1]),
            persona_id=PersonaId(str(row[2])),
            created_at=str(row[3]),
        )

    def _conversation_row(
        self, binding_id: str
    ) -> WorldConversationRecord | None:
        row = self._conn.execute(
            "SELECT binding_id, world_id, actor_id, conversation_id, created_at"
            " FROM world_conversation WHERE binding_id = ?",
            (binding_id,),
        ).fetchone()
        if row is None:
            return None
        return WorldConversationRecord(
            binding_id=str(row[0]),
            world_id=str(row[1]),
            actor_id=str(row[2]),
            conversation_id=ConversationId(str(row[3])),
            created_at=str(row[4]),
        )

    def _conversation_exists(self, conversation_id: str) -> bool:
        """Whether the conversation row exists (migration 0002's table) —
        the NOT_FOUND pre-check; the binding table's own UNIQUE is what
        refuses a second binding."""

        row = self._conn.execute(
            "SELECT 1 FROM conversation WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return row is not None
