"""The World bounded context's durable face — :class:`SqliteWorldStore`
(migration 0023's three identity tables and migration 0024's event tree +
minimal state projection).

W-1-0's identity face binds worlds, actors and conversations and reads
them back. W-1-1 adds the event face: :meth:`SqliteWorldStore.record_event`
is the *only* writer of either migration-0024 table — one short fenced
transaction inserts the chronicle entry and settles its effects into
``world_state_fact`` (the projection is a reading of the tree, never an
independent write). The read face is three shapes: the chronicle (the
tree, in its own order), the current facts (the projection's ``CURRENT``
half) and one key's fact history (the superseded rows included).

Identity idempotence is the seeded shape (W-1-4's host seed will sit on
it):

- ``create_world``: the same id replayed with the same shape (name +
  template) is an ``Ok`` no-op; the same id with a different shape is a
  ``CONFLICT``;
- ``bind_actor``: the same actor tuple replayed is a no-op; a different
  shape under a taken actor id, or a (world, persona) pair another actor
  already holds (the table's UNIQUE), is a ``CONFLICT``;
- ``bind_conversation``: the same binding tuple replayed is a no-op; a
  different shape under a taken binding id, or a conversation bound to a
  different (world, actor) pair (the column's UNIQUE), is a ``CONFLICT``.

Event idempotence: the same ``event_id`` replayed with the same shape is
an ``Ok`` no-op (neither the chronicle entry nor its settlement is
redone); the same id with a different shape is a ``CONFLICT``. An event
carrying the same canonical key twice is refused before anything is
written (``VALIDATION_FAILED``) — the whole face lands or nothing does.

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
does not exist; ``VALIDATION_FAILED`` = the caller's own payload is
malformed (a duplicated canonical key inside one event; a state-facts
effects column that does not decode); ``DEPENDENCY_UNAVAILABLE`` = the
database itself failed outside the vocabulary above (world_lore's
precedent — the raw sqlite error rides the message).
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
    WorldEvent,
    WorldRecord,
    WorldStateFact,
    decode_effects,
    encode_effects,
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
            # N-W10-6 (closed in W-1-1): the catch used to attribute every
            # sqlite failure to the missing template. The refusal is
            # narrowed by message family: a FOREIGN KEY refusal here can
            # only be the template FK (the id's UNIQUE is pre-checked, the
            # NOT NULLs are caller input) and stays ``NOT_FOUND``; any
            # other database failure is the database's own and answers the
            # house's storage word (world_lore's precedent), raw error
            # riding the message — never re-attributed to the template.
            if "FOREIGN KEY" in str(exc):
                return Err(
                    DomainError(
                        code=DomainErrorCode.NOT_FOUND,
                        message=(
                            f"world {world_id!r} not created: its template"
                            f" world does not exist ({exc})"
                        ),
                    )
                )
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"world {world_id!r} not created: write failed ({exc})",
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

    # -- event face (W-1-1) ---------------------------------------------------

    def record_event(self, event: WorldEvent) -> Result[WorldEvent]:
        """Write one chronicle event and settle its effects, atomically.

        The only writer of migration 0024's tables — the event row and
        its ``world_state_fact`` settlement land in one short fenced
        transaction, so the projection is never caught between an event
        and its claims: the whole face lands or nothing does.

        Refusals, before anything is written:

        - an event carrying the same canonical key twice is a
          ``VALIDATION_FAILED`` (one event, one claim per key);
        - a dangling ``world_id`` is a ``NOT_FOUND`` (the table's FK is
          the backstop);
        - a replayed ``event_id`` with a different shape is a
          ``CONFLICT`` (events are append-only — the same id answers the
          stored event unchanged, and neither the entry nor its
          settlement is redone).

        Each effect settles the same way: the key's ``CURRENT`` fact (if
        any) flips to ``SUPERSEDED``, then this event's claim is inserted
        as the new ``CURRENT`` row. The fact's id is derived —
        ``<event_id>:<key>`` — and its ``recorded_at`` is the event's own
        ``occurred_at``: the projection is derived from the tree, clock
        and all. An empty effects tuple is a legal pure-narration event
        (the chronicle entry lands, zero settlement rows).
        """

        seen_keys: set[str] = set()
        for effect in event.effects:
            if effect.key in seen_keys:
                return Err(
                    DomainError(
                        code=DomainErrorCode.VALIDATION_FAILED,
                        message=(
                            f"event {event.event_id!r} refused: canonical"
                            f" key {effect.key!r} appears twice in one"
                            " event (one event, one claim per key);"
                            " nothing was written"
                        ),
                    )
                )
            seen_keys.add(effect.key)

        stored = self._event_values(event.event_id)
        if stored is not None:
            decoded = decode_effects(str(stored[4]))
            if isinstance(decoded, Err):
                return Err(
                    DomainError(
                        code=decoded.error.code,
                        message=(
                            f"event {event.event_id!r} replay cannot be"
                            f" verified: {decoded.error.message}"
                        ),
                    )
                )
            stored_shape = (
                str(stored[1]),
                str(stored[2]),
                str(stored[3]),
                decoded.value,
                str(stored[5]),
                str(stored[6]),
            )
            if stored_shape == (
                event.world_id,
                event.kind,
                event.narration,
                event.effects,
                event.occurred_at,
                event.source,
            ):
                return Ok(
                    WorldEvent(
                        event_id=str(stored[0]),
                        world_id=str(stored[1]),
                        kind=str(stored[2]),
                        narration=str(stored[3]),
                        effects=decoded.value,
                        occurred_at=str(stored[5]),
                        source=str(stored[6]),
                    )
                )
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"event {event.event_id!r} already exists with a"
                        " different shape; events are append-only and do"
                        " not rewrite"
                    ),
                )
            )

        if self._world_row(event.world_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"event {event.event_id!r} not written: world"
                        f" {event.world_id!r} does not exist"
                    ),
                )
            )

        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_event ("
                " event_id, world_id, kind, narration, effects,"
                " occurred_at, source"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.world_id,
                    event.kind,
                    event.narration,
                    encode_effects(event.effects),
                    event.occurred_at,
                    event.source,
                ),
            )
            for effect in event.effects:
                # The settlement: this key's CURRENT fact (if any) flips
                # to SUPERSEDED, then the event's claim lands as the new
                # CURRENT row. At most one CURRENT row per key is the
                # invariant this face maintains (the table keeps no
                # UNIQUE on the key — the superseded history is the
                # design) — every write runs through here.
                self._conn.execute(
                    "UPDATE world_state_fact SET status = 'SUPERSEDED'"
                    " WHERE world_id = ? AND canonical_key = ?"
                    " AND status = 'CURRENT'",
                    (event.world_id, effect.key),
                )
                self._conn.execute(
                    "INSERT INTO world_state_fact ("
                    " fact_id, world_id, source_event_id, canonical_key,"
                    " statement, status, recorded_at"
                    ") VALUES (?, ?, ?, ?, ?, 'CURRENT', ?)",
                    (
                        f"{event.event_id}:{effect.key}",
                        event.world_id,
                        event.event_id,
                        effect.key,
                        effect.statement,
                        event.occurred_at,
                    ),
                )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            if "FOREIGN KEY" in str(exc):
                return Err(
                    DomainError(
                        code=DomainErrorCode.NOT_FOUND,
                        message=(
                            f"event {event.event_id!r} not written: a"
                            f" referenced identity does not exist ({exc})"
                        ),
                    )
                )
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"event {event.event_id!r} not written: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(event)

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

    # -- event / projection read face (W-1-1) ---------------------------------

    def chronicle_of(self, world_id: str) -> Result[tuple[WorldEvent, ...]]:
        """One world's chronicle, event order ascending (``occurred_at``,
        then ``event_id`` — the durable order; deterministic reads are
        content, not an implementation detail).

        The one read face that parses a column: each row's ``effects``
        text goes through the strict codec, so a hand-corrupted column
        answers a value-semantics ``Err`` naming the offending event —
        never an exception, never a silently-decoded fact. (The other two
        projection reads are pure column reads — nothing to parse.)
        """

        rows = self._conn.execute(
            "SELECT event_id, world_id, kind, narration, effects,"
            " occurred_at, source"
            " FROM world_event WHERE world_id = ?"
            " ORDER BY occurred_at ASC, event_id ASC",
            (world_id,),
        ).fetchall()
        events: list[WorldEvent] = []
        for row in rows:
            decoded = decode_effects(str(row[4]))
            if isinstance(decoded, Err):
                return Err(
                    DomainError(
                        code=decoded.error.code,
                        message=(
                            f"chronicle of {world_id!r} refused at event"
                            f" {str(row[0])!r}: {decoded.error.message}"
                        ),
                    )
                )
            events.append(
                WorldEvent(
                    event_id=str(row[0]),
                    world_id=str(row[1]),
                    kind=str(row[2]),
                    narration=str(row[3]),
                    effects=decoded.value,
                    occurred_at=str(row[5]),
                    source=str(row[6]),
                )
            )
        return Ok(tuple(events))

    def current_facts(self, world_id: str) -> tuple[WorldStateFact, ...]:
        """The projection's ``CURRENT`` half: one world's live facts, key
        ascending (the durable order)."""

        rows = self._conn.execute(
            "SELECT fact_id, world_id, source_event_id, canonical_key,"
            " statement, status, recorded_at"
            " FROM world_state_fact WHERE world_id = ? AND status = 'CURRENT'"
            " ORDER BY canonical_key ASC",
            (world_id,),
        ).fetchall()
        return tuple(self._fact(row) for row in rows)

    def fact_history(
        self, world_id: str, canonical_key: str
    ) -> tuple[WorldStateFact, ...]:
        """One key's whole fact lineage in one world — superseded rows
        included — oldest first (``recorded_at``, then ``fact_id``; the
        durable order)."""

        rows = self._conn.execute(
            "SELECT fact_id, world_id, source_event_id, canonical_key,"
            " statement, status, recorded_at"
            " FROM world_state_fact WHERE world_id = ? AND canonical_key = ?"
            " ORDER BY recorded_at ASC, fact_id ASC",
            (world_id, canonical_key),
        ).fetchall()
        return tuple(self._fact(row) for row in rows)

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

    def _event_values(self, event_id: str) -> tuple[object, ...] | None:
        """One raw ``world_event`` row (the idempotence pre-read); the
        effects text stays undecoded here — :meth:`record_event` decodes
        it through the strict codec where it can answer an ``Err``."""

        row = self._conn.execute(
            "SELECT event_id, world_id, kind, narration, effects,"
            " occurred_at, source"
            " FROM world_event WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return None if row is None else tuple(row)

    @staticmethod
    def _fact(row: tuple[object, ...]) -> WorldStateFact:
        """One ``world_state_fact`` row as its frozen record (pure column
        read — every column is NOT NULL, ``status`` is CHECK-bound)."""

        return WorldStateFact(
            fact_id=str(row[0]),
            world_id=str(row[1]),
            source_event_id=str(row[2]),
            canonical_key=str(row[3]),
            statement=str(row[4]),
            status=str(row[5]),
            recorded_at=str(row[6]),
        )
