"""The World bounded context's durable face — :class:`SqliteWorldStore`
(migration 0023's three identity tables, migration 0024's event tree +
minimal state projection, and migration 0025's world run).

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

Run face (W-1-2): ``create_run`` / ``checkpoint_run`` /
``terminalize_run`` are the only writers of migration 0025's
``world_run`` row, and the deterministic engine
(:mod:`elc.world.engine.engine`) is the only caller that moves a run —
creation is the zeroth checkpoint (``AT_CHECKPOINT`` / ``NOTICE`` /
cursor 0 / version 1), a NOTICE pause advances the cursor, the RESPONSE
stop (or the engine's fail-closed cycle ceiling) terminates the run.
``state_version`` bumps on every run write — it is the row's own write
counter, deliberately not a canonical version spelling.

Reveal face (W-1-3): :class:`WorldRevealItem` is migration 0026's queue
row — the durable form of a run's "future-revealable special moment"
(spec §4.1: revealing is a presentation trigger, never run fuel). Two
methods are the face's *whole* write half, and nothing else in the
package writes either column set: ``enqueue_reveals`` lands one
``PENDING`` item per event an engine step produced, all of them in one
short transaction (the whole face lands or nothing does — a step that
refuses never leaves half an inbox behind), and ``reveal_all`` is the
atomic flip that turns one world's whole ``PENDING`` slice to
``REVEALED`` at the moment the user next looks (and returns the world's
whole inbox, revealed history included, in the durable order). The
item's id derives — ``<event_id>:reveal`` — so the same event can never
enqueue twice, the same derivation law ``world_state_fact``'s
``fact_id`` spells; the record shape lives here beside its face rather
than in :mod:`elc.world.types` (that module is the frozen identity and
event shapes; this cut's authorization names the store's reveal face).

Attribution face (C1-a, DEC-OPI-41a4df20…55): migration 0027 adds two
columns to ``world_event`` — ``participants`` (the strict JSON array
the types codec owns; the who of the chronicle) and ``run_id`` (the run
the event rode; ``None`` for a legacy row, honestly empty). Every
write/read above carries them; 存量行 answer the migration's DEFAULT
with zero back-fill inference. The **interaction face** lands beside
the event face: :meth:`SqliteWorldStore.record_interaction_event` is
the only writer of the two user interaction kinds
(:data:`INTERACTION_EVENT_KINDS` — the letter-sent fact and the
direction-chosen call), and its discipline is the queue law's mirror:
an interaction row lands **directly ``REVEALED``** (the user just did
it — there is nothing to sit in an inbox), in the same one short
transaction as its chronicle entry, while the world's own events keep
walking the ``PENDING`` queue exactly as before.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
from elc.world.engine.types import MomentKind, RunStatus, WorldRunRecord
from elc.world.types import (
    WorldActorRecord,
    WorldConversationRecord,
    WorldEvent,
    WorldRecord,
    WorldStateFact,
    decode_effects,
    decode_participants,
    encode_effects,
    encode_participants,
)

__all__ = [
    "SqliteWorldStore",
    "WorldRevealItem",
    "INTERACTION_EVENT_KINDS",
    "INTERACTION_SOURCE",
]

#: The two user interaction kinds the chronicle carries (C1-a): the
#: letter-sent fact and the direction-chosen call.
#: :meth:`SqliteWorldStore.record_interaction_event` refuses every other
#: word (fail-closed — the world's own events go through
#: :meth:`SqliteWorldStore.record_event` and the PENDING queue, never
#: here).
INTERACTION_EVENT_KINDS: tuple[str, ...] = (
    "user-letter-sent",
    "user-direction-chosen",
)

#: The ``source`` word every interaction row carries — the origin the
#: presentation faces read to narrate the row honestly (never the
#: narrator's word, never the engine's).
INTERACTION_SOURCE = "user_interaction"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(frozen=True)
class WorldRevealItem:
    """One reveal-queue row (migration 0026's ``world_reveal_item``
    table).

    The durable form of a run's "future-revealable special moment": one
    event the run wrote, sitting ``PENDING`` until the inbox's atomic
    reveal flips the world's slice to ``REVEALED`` (``revealed_at`` is
    ``None`` while pending, the reveal moment after). ``item_id``
    derives — ``<event_id>:reveal`` — so one event can never enqueue
    twice. ``actor_id`` is the cast member the item is signed by (the
    comms step's chosen correspondent); ``None`` is the world's own
    narration. The record shape lives in this module beside the face
    that writes it (the module docstring carries the reason); the
    projection's read joins ``world_event`` for the prose — the item
    carries the pointer, never a copy.
    """

    item_id: str
    world_id: str
    source_event_id: str
    actor_id: str | None
    status: str
    revealed_at: str | None
    created_at: str


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
            decoded_participants = decode_participants(str(stored[7]))
            if isinstance(decoded_participants, Err):
                return Err(
                    DomainError(
                        code=decoded_participants.error.code,
                        message=(
                            f"event {event.event_id!r} replay cannot be"
                            f" verified: {decoded_participants.error.message}"
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
                decoded_participants.value,
                None if stored[8] is None else str(stored[8]),
            )
            if stored_shape == (
                event.world_id,
                event.kind,
                event.narration,
                event.effects,
                event.occurred_at,
                event.source,
                event.participants,
                event.run_id,
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
                        participants=decoded_participants.value,
                        run_id=None if stored[8] is None else str(stored[8]),
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
                " occurred_at, source, participants, run_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.world_id,
                    event.kind,
                    event.narration,
                    encode_effects(event.effects),
                    event.occurred_at,
                    event.source,
                    encode_participants(event.participants),
                    event.run_id,
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

    # -- interaction face (C1-a) -----------------------------------------------

    def record_interaction_event(
        self, event: WorldEvent, now: str
    ) -> Result[WorldEvent]:
        """Write one user interaction row and reveal it, atomically.

        The only writer of the two interaction kinds
        (:data:`INTERACTION_EVENT_KINDS` — C1-a's letter-sent fact and
        direction-chosen call). The discipline is the reveal queue's
        law **mirrored**: the world's own events land ``PENDING`` and
        wait for the inbox's presentation trigger, but an interaction
        is the user's own just-done act — its item lands **directly
        ``REVEALED``** (``revealed_at`` = the caller's ``now``), so the
        chronicle rows and their presentation exist in the same one
        short transaction: the whole face lands or nothing does.

        Refusals, before anything is written: a kind outside the
        two-word vocabulary, a non-empty ``effects`` tuple (an
        interaction settles no state claim), a ``source`` that is not
        :data:`INTERACTION_SOURCE`, or a non-``None`` ``run_id`` (an
        interaction is not a run event) — each a ``VALIDATION_FAILED``
        naming the law. The replay law is :meth:`record_event`'s own:
        the same ``event_id`` with the same shape answers the stored
        row unchanged (nothing re-written, the reveal included); a
        different shape is a ``CONFLICT``; a dangling world is a
        ``NOT_FOUND`` (the table's FK is the backstop).
        """

        if event.kind not in INTERACTION_EVENT_KINDS:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"event {event.event_id!r} refused: kind"
                        f" {event.kind!r} is not an interaction kind"
                        f" (the vocabulary is"
                        f" {', '.join(INTERACTION_EVENT_KINDS)});"
                        " the world's own events go through record_event"
                    ),
                )
            )
        if event.effects:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"event {event.event_id!r} refused: an"
                        " interaction row settles no state claim"
                        " (empty effects); nothing was written"
                    ),
                )
            )
        if event.source != INTERACTION_SOURCE:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"event {event.event_id!r} refused: source"
                        f" {event.source!r} is not the interaction"
                        f" source {INTERACTION_SOURCE!r}; nothing was"
                        " written"
                    ),
                )
            )
        if event.run_id is not None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"event {event.event_id!r} refused: an"
                        " interaction row is not a run event (run_id"
                        " stays None); nothing was written"
                    ),
                )
            )

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
            decoded_participants = decode_participants(str(stored[7]))
            if isinstance(decoded_participants, Err):
                return Err(
                    DomainError(
                        code=decoded_participants.error.code,
                        message=(
                            f"event {event.event_id!r} replay cannot be"
                            f" verified: {decoded_participants.error.message}"
                        ),
                    )
                )
            if (
                str(stored[1]),
                str(stored[2]),
                str(stored[3]),
                decoded.value,
                str(stored[5]),
                str(stored[6]),
                decoded_participants.value,
                None if stored[8] is None else str(stored[8]),
            ) == (
                event.world_id,
                event.kind,
                event.narration,
                event.effects,
                event.occurred_at,
                event.source,
                event.participants,
                event.run_id,
            ):
                return Ok(event)
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

        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_event ("
                " event_id, world_id, kind, narration, effects,"
                " occurred_at, source, participants, run_id"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.world_id,
                    event.kind,
                    event.narration,
                    encode_effects(event.effects),
                    event.occurred_at,
                    event.source,
                    encode_participants(event.participants),
                    event.run_id,
                ),
            )
            self._conn.execute(
                "INSERT INTO world_reveal_item ("
                " item_id, world_id, source_event_id, actor_id,"
                " status, revealed_at, created_at"
                ") VALUES (?, ?, ?, NULL, 'REVEALED', ?, ?)",
                (
                    f"{event.event_id}:reveal",
                    event.world_id,
                    event.event_id,
                    now,
                    now,
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
                            f"interaction {event.event_id!r} not written:"
                            f" a referenced identity does not exist ({exc})"
                        ),
                    )
                )
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=(
                        f"interaction {event.event_id!r} not written: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        return Ok(event)

    # -- run face (W-1-2) -----------------------------------------------------

    def create_run(
        self,
        run_id: str,
        world_id: str,
        trigger_turn_id: str | None,
        seed: int,
        now: str,
    ) -> Result[WorldRunRecord]:
        """Create one world run at its zeroth checkpoint, idempotently by id.

        Creation **is the zeroth checkpoint** (the W-1-2 adjudication's
        status vocabulary has no third starting word): the row lands at
        ``AT_CHECKPOINT`` / ``NOTICE`` / cursor 0 / ``state_version`` 1 —
        the not-yet-advanced starting point the engine's first
        ``advance`` continues from. A replay of the same id with the same
        shape (world, trigger, seed) answers the stored row unchanged; a
        same-id different-shape call is a ``CONFLICT`` (runs do not
        rewrite). A dangling world is refused by the table's own FK and
        surfaces as ``NOT_FOUND``. ``trigger_turn_id`` deliberately
        carries no foreign key — the run must not pin a conversation's
        lifetime (Revisit W-1-3).
        """

        existing = self._run_row(run_id)
        if existing is not None:
            if (
                existing.world_id,
                existing.trigger_turn_id,
                existing.seed,
            ) == (world_id, trigger_turn_id, seed):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"run {run_id!r} already exists with a different"
                        " shape; runs do not rewrite"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_run ("
                " run_id, world_id, trigger_turn_id, seed, status,"
                ' checkpoint_kind, "cursor", state_version, created_at,'
                " updated_at"
                ") VALUES (?, ?, ?, ?, 'AT_CHECKPOINT', 'NOTICE', 0, 1, ?, ?)",
                (run_id, world_id, trigger_turn_id, seed, now, now),
            )
        except sqlite3.Error as exc:
            # The ml3R LOW-1 judgement (see create_world): when BEGIN
            # itself failed, nothing of ours began; a failing ROLLBACK of
            # our own must not break the Result contract.
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=self._refusal_code(exc),
                    message=f"run {run_id!r} not created: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(
            WorldRunRecord(
                run_id=run_id,
                world_id=world_id,
                trigger_turn_id=trigger_turn_id,
                seed=seed,
                status=RunStatus.AT_CHECKPOINT,
                checkpoint_kind=MomentKind.NOTICE,
                cursor=0,
                state_version=1,
                created_at=now,
                updated_at=now,
            )
        )

    def checkpoint_run(self, run_id: str, now: str) -> Result[WorldRunRecord]:
        """Advance the run's cursor by one cycle and bump its version.

        The engine calls this when a cycle ends at a NOTICE checkpoint:
        the completed cycle is behind the run, the cursor names the next
        cycle's PRNG slot — ``(seed, cursor)`` — and ``state_version``
        bumps (the row was rewritten; ``updated_at`` moves with it).
        ``checkpoint_kind`` stays what it was: this cut's only checkpoint
        word is NOTICE (DIRECTION arrives W-2-2). A run that does not
        exist is ``NOT_FOUND``; a run already ``TERMINAL`` is refused
        (``VALIDATION_FAILED``) — a finished run does not checkpoint.
        """

        row = self._run_row(run_id)
        if row is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"run {run_id!r} not checkpointed: the run does"
                        " not exist"
                    ),
                )
            )
        if row.status == RunStatus.TERMINAL:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"run {run_id!r} is TERMINAL; a finished run does"
                        " not checkpoint"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                'UPDATE world_run SET "cursor" = "cursor" + 1,'
                " state_version = state_version + 1, updated_at = ?"
                " WHERE run_id = ?",
                (now, run_id),
            )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"run {run_id!r} not checkpointed: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        updated = self._run_row(run_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def terminalize_run(self, run_id: str, now: str) -> Result[WorldRunRecord]:
        """Terminate the run at the RESPONSE stop.

        The engine calls this when a cycle ends at a RESPONSE moment (or
        when its fail-closed cycle ceiling burns out — the trace, not
        this row, carries that distinction): the run becomes
        ``TERMINAL``, ``checkpoint_kind`` becomes ``RESPONSE`` (the
        world waits for the next reply), and ``state_version`` bumps. A
        run that does not exist is ``NOT_FOUND``; a run already
        ``TERMINAL`` is refused (``VALIDATION_FAILED``) — terminal is
        absorbing, and a second termination is a caller bug, not a
        no-op.
        """

        row = self._run_row(run_id)
        if row is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"run {run_id!r} not terminalized: the run does"
                        " not exist"
                    ),
                )
            )
        if row.status == RunStatus.TERMINAL:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"run {run_id!r} is already TERMINAL; terminal is"
                        " absorbing and does not terminate twice"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "UPDATE world_run SET status = 'TERMINAL',"
                " checkpoint_kind = 'RESPONSE',"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE run_id = ?",
                (now, run_id),
            )
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"run {run_id!r} not terminalized: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        updated = self._run_row(run_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    # -- reveal face (W-1-3) ---------------------------------------------------

    def enqueue_reveals(
        self, items: tuple[WorldRevealItem, ...]
    ) -> Result[tuple[WorldRevealItem, ...]]:
        """Land one ``PENDING`` reveal item per produced event, atomically.

        The only creator of migration 0026's rows. The whole tuple lands
        in **one short transaction** — the orchestration's "same short
        transaction" discipline: an engine step that wrote events either
        leaves its whole inbox tail behind or nothing of it, and a
        refusal anywhere upstream means this face is never reached with
        a partial step (zero items for a refused step, never half).

        The caller's items must carry the enqueue shape exactly —
        ``status == 'PENDING'`` and ``revealed_at is None``; any other
        shape is a ``VALIDATION_FAILED`` before anything is written
        (there is no other legal enqueue shape; the PENDING→REVEALED
        flip belongs to :meth:`reveal_all` alone). An empty tuple is a
        legal no-op (a step whose trace carried no events).

        Idempotence rides the derived id: a replayed ``item_id`` with
        the same shape answers the stored rows unchanged (nothing is
        re-inserted); the same id with a different shape is a
        ``CONFLICT`` for the whole face. A dangling world, event or
        actor is refused by the table's own FKs and surfaces as
        ``NOT_FOUND``.
        """

        if not items:
            return Ok(())
        for item in items:
            if item.status != "PENDING" or item.revealed_at is not None:
                return Err(
                    DomainError(
                        code=DomainErrorCode.VALIDATION_FAILED,
                        message=(
                            f"reveal item {item.item_id!r} refused: the"
                            " enqueue shape is PENDING with no reveal"
                            " moment (the flip is reveal_all's alone);"
                            " nothing was written"
                        ),
                    )
                )
        fresh: list[WorldRevealItem] = []
        for item in items:
            stored = self._reveal_row(item.item_id)
            if stored is not None:
                if (
                    stored.world_id,
                    stored.source_event_id,
                    stored.actor_id,
                    stored.created_at,
                ) == (
                    item.world_id,
                    item.source_event_id,
                    item.actor_id,
                    item.created_at,
                ):
                    # WR-2 disposition (review LOW-1): a same-shape replay
                    # stays in the stored row and is **excluded from the
                    # insert set** — the old arm's ``continue`` skipped
                    # only the pre-read and the INSERT loop re-inserted
                    # the row anyway (a UNIQUE crash the docstring's
                    # "nothing is re-inserted" claim never matched).
                    continue
                return Err(
                    DomainError(
                        code=DomainErrorCode.CONFLICT,
                        message=(
                            f"reveal item {item.item_id!r} already exists"
                            " with a different shape; reveal items derive"
                            " from their event and do not rewrite"
                        ),
                    )
                )
            fresh.append(item)
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            for item in fresh:
                self._conn.execute(
                    "INSERT INTO world_reveal_item ("
                    " item_id, world_id, source_event_id, actor_id,"
                    " status, revealed_at, created_at"
                    ") VALUES (?, ?, ?, ?, 'PENDING', NULL, ?)",
                    (
                        item.item_id,
                        item.world_id,
                        item.source_event_id,
                        item.actor_id,
                        item.created_at,
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
                            "reveal items not enqueued: a referenced"
                            f" identity does not exist ({exc})"
                        ),
                    )
                )
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"reveal items not enqueued: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(tuple(items))

    def reveal_all(
        self, world_id: str, now: str
    ) -> Result[tuple[WorldRevealItem, ...]]:
        """Reveal one world's whole pending slice, atomically, and read
        the whole inbox back.

        The only ``PENDING`` → ``REVEALED`` mover: one short transaction
        flips every pending item of the world (``revealed_at`` stamped
        with the caller's ``now`` — the moment the user next looked, the
        spec §4.1 presentation trigger) and then reads every item of the
        world back, revealed history included, in the durable order
        (``created_at``, then ``item_id`` — deterministic reads are
        content, not an implementation detail). A second reveal does not
        re-stamp: the UPDATE matches nothing, the read returns the same
        rows, ``revealed_at`` stays the first reveal's moment. A world
        that does not exist is ``NOT_FOUND``.
        """

        if self._world_row(world_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"inbox of {world_id!r} not read: the world does"
                        " not exist"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "UPDATE world_reveal_item SET status = 'REVEALED',"
                " revealed_at = ? WHERE world_id = ? AND status = 'PENDING'",
                (now, world_id),
            )
            rows = self._conn.execute(
                "SELECT item_id, world_id, source_event_id, actor_id,"
                " status, revealed_at, created_at"
                " FROM world_reveal_item WHERE world_id = ?"
                " ORDER BY created_at ASC, item_id ASC",
                (world_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"inbox of {world_id!r} not read: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(tuple(self._reveal(row) for row in rows))

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

    def event_kinds_of(self, world_id: str) -> tuple[str, ...]:
        """One world's chronicle kinds, in durable order (event id
        ascending — the ``<run_id>:<cursor>`` derivation makes that the
        story's own order). The virtual world calendar's read half (A2,
        DEC-…88/…90): ``elc.world.package.story_days_of`` sums the
        happened events' story spans over this read, so the world's today
        is derived from the durable chronicle, never from a clock. A
        narrow face on purpose — the full rows stay the web face's own
        direct-SQL read."""

        rows = self._conn.execute(
            "SELECT kind FROM world_event WHERE world_id = ?"
            " ORDER BY event_id ASC",
            (world_id,),
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

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
            " occurred_at, source, participants, run_id"
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
            decoded_participants = decode_participants(str(row[7]))
            if isinstance(decoded_participants, Err):
                return Err(
                    DomainError(
                        code=decoded_participants.error.code,
                        message=(
                            f"chronicle of {world_id!r} refused at event"
                            f" {str(row[0])!r}:"
                            f" {decoded_participants.error.message}"
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
                    participants=decoded_participants.value,
                    run_id=None if row[8] is None else str(row[8]),
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

    # -- run read face (W-1-2) -------------------------------------------------

    def get_run(self, run_id: str) -> WorldRunRecord | None:
        """One run by id; ``None`` when the id is unknown."""

        return self._run_row(run_id)

    def list_runs(self, world_id: str) -> tuple[WorldRunRecord, ...]:
        """One world's runs, ``created_at`` then ``run_id`` ascending (the
        durable order — deterministic reads are content, not an
        implementation detail)."""

        rows = self._conn.execute(
            "SELECT run_id, world_id, trigger_turn_id, seed, status,"
            ' checkpoint_kind, "cursor", state_version, created_at,'
            " updated_at"
            " FROM world_run WHERE world_id = ?"
            " ORDER BY created_at ASC, run_id ASC",
            (world_id,),
        ).fetchall()
        return tuple(self._run(row) for row in rows)

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
        it through the strict codec where it can answer an ``Err``. The
        same posture covers migration 0027's two attribution columns
        (``participants`` at index 7, ``run_id`` at index 8)."""

        row = self._conn.execute(
            "SELECT event_id, world_id, kind, narration, effects,"
            " occurred_at, source, participants, run_id"
            " FROM world_event WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return None if row is None else tuple(row)

    def _run_row(self, run_id: str) -> WorldRunRecord | None:
        """One ``world_run`` row as its frozen record, or ``None``. The
        two lifecycle words are cast through the engine's vocabularies —
        the row's own CHECKs bound them to exactly those words, so the
        cast cannot meet a third."""

        row = self._conn.execute(
            "SELECT run_id, world_id, trigger_turn_id, seed, status,"
            ' checkpoint_kind, "cursor", state_version, created_at,'
            " updated_at"
            " FROM world_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._run(row)

    def _reveal_row(self, item_id: str) -> WorldRevealItem | None:
        """One raw ``world_reveal_item`` row (the idempotence pre-read)."""

        row = self._conn.execute(
            "SELECT item_id, world_id, source_event_id, actor_id,"
            " status, revealed_at, created_at"
            " FROM world_reveal_item WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            return None
        return self._reveal(row)

    @staticmethod
    def _reveal(row: tuple[Any, ...]) -> WorldRevealItem:
        """One raw ``world_reveal_item`` row as its frozen record (pure
        column read — ``status`` is CHECK-bound to the two lifecycle
        words the migration spells)."""

        return WorldRevealItem(
            item_id=str(row[0]),
            world_id=str(row[1]),
            source_event_id=str(row[2]),
            actor_id=None if row[3] is None else str(row[3]),
            status=str(row[4]),
            revealed_at=None if row[5] is None else str(row[5]),
            created_at=str(row[6]),
        )

    @staticmethod
    def _run(row: tuple[Any, ...]) -> WorldRunRecord:
        """One raw ``world_run`` row as its frozen record (pure column
        read — ``status`` / ``checkpoint_kind`` are CHECK-bound to the
        two vocabularies the engine's enums spell)."""

        return WorldRunRecord(
            run_id=str(row[0]),
            world_id=str(row[1]),
            trigger_turn_id=None if row[2] is None else str(row[2]),
            seed=int(row[3]),
            status=RunStatus(str(row[4])),
            checkpoint_kind=MomentKind(str(row[5])),
            cursor=int(row[6]),
            state_version=int(row[7]),
            created_at=str(row[8]),
            updated_at=str(row[9]),
        )

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
