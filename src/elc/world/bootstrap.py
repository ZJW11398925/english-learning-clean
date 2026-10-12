"""The atomic world-creation service (V3-8a, TASK-OPI-06b954e0…4 / the
opening ruling ``DEC-OPI-06b954e0-…2``; RA §27's "原子创建服务" paragraph;
DOMAIN §20.2's third row) — :func:`create_world_with_bible`: the world
and its initial authority are born together, or not at all.

**One short transaction, all or nothing** (the contract's sentence:
世界与其初始权威同生同灭；半创建不留残骸): the ``world`` row, the first
``world_bible_revision`` (``CURRENT``), the durable player-character
seed and the AI cast seeds (each ``world_actor`` row plus its
``world_actor_profile``) land in **one** ``BEGIN IMMEDIATE`` …
``COMMIT``. A mid-group refusal — a dangling ``persona_id`` the
``world_actor`` FK refuses, a taken id — rolls the whole group back:
the test injects exactly such a failure and reads zero rows of every
kind afterwards.

**The service composes the stores' faces, it does not re-spell their
SQL**: every INSERT rides the ``*_tx`` arm the store already owns
(:meth:`elc.world.store.SqliteWorldStore._create_world_tx` /
``_bind_actor_tx``, :meth:`elc.world.bible.SqliteBibleStore._seed_bible_tx`,
:meth:`elc.world.cast.SqliteCastStore._seed_actor_profile_tx` /
``_seed_player_character_tx`` — the no-transaction arm pattern, the
public faces above them unchanged). No second spelling of any column
list lives here: the arms are the one truth, called inside this
service's own transaction.

**Idempotency key = ``world_id``** (the contract's sentence): a replay
whose **shape** equals what is stored answers the stored rows — zero
write (the world, its revision-1 Bible with the same fourteen content
fields, its player row and its cast rows with the same profiles, all
compared field by field); a replay of the same id with a **different**
shape answers ``CONFLICT`` and writes nothing — this face never renames,
re-seeds or "updates" an existing world (the N-INV-006 posture's
creation-side twin: the template's later word does not rewrite a world,
here the creator's own replay does not either). A stored world that is
not this payload's shape at all — the one ``ensure_builtin_worlds``
created without this service, say — is the same ``CONFLICT``: the
service owns only its own product.

**Refusals are value semantics, judged before anything is written**: a
malformed payload (empty identities, a mistyped seed field, duplicate
actor ids within the payload) is ``VALIDATION_FAILED`` with a human
sentence naming the field; a stored-shape clash is ``CONFLICT``; a
dangling ``template_world_id`` or a cast seed's missing ``persona_id``
is the database's FOREIGN KEY refusal surfaced as ``NOT_FOUND`` (the
store family's mapping); anything else the database refuses is
``DEPENDENCY_UNAVAILABLE`` with the raw error riding the message.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.bible import (
    BIBLE_FIELDS,
    BibleContent,
    BibleRevision,
    SqliteBibleStore,
)
from elc.world.cast import (
    ActorProfileRecord,
    PlayerCharacterRecord,
    SqliteCastStore,
    StoryRole,
)
from elc.world.store import SqliteWorldStore
from elc.world.types import WorldActorRecord, WorldRecord

__all__ = [
    "ActorSeed",
    "PlayerSeed",
    "WorldCreationOutcome",
    "create_world_with_bible",
]


@dataclass(frozen=True)
class ActorSeed:
    """One AI cast member's creation-time seed (the package's v8 cast
    declaration's durable half: the ``world_actor`` binding plus the
    :class:`~elc.world.cast.ActorProfileRecord` fields).

    ``story_role`` / ``pov_eligible`` / ``pov_weight`` ride ``None``
    for the honest undeclared (the seed never guesses — the profile
    table's own NULL law); the three arc texts ride as given (an
    undeclared field the empty string).
    """

    actor_id: str
    persona_id: str
    story_role: StoryRole | None = None
    pov_eligible: bool | None = None
    pov_weight: int | None = None
    long_term_drive: str = ""
    current_arc_seed: str = ""
    private_context: str = ""


@dataclass(frozen=True)
class PlayerSeed:
    """The reader's durable character seed (one per world — the
    ``UNIQUE (world_id)`` law). The eight content fields ride as given;
    the V3-3R seed semantics (``location`` / ``state`` /
    ``knowledge_refs`` are creation-time seed, never the running
    facts) are the cast store's own docstring's — this record only
    carries them.
    """

    player_character_id: str
    name: str
    background: str = ""
    appearance: str = ""
    abilities: str = ""
    limits: str = ""
    location: str = ""
    state: str = ""
    knowledge_refs: str = ""


@dataclass(frozen=True)
class WorldCreationOutcome:
    """One creation's answer shape — the durable rows as they stand
    after the group lands (or as they stand stored, on a same-shape
    replay): the world, its ``CURRENT`` Bible revision, the reader's
    character (``None`` for a world that declares none) and the AI cast
    (``actor_id`` ascending — the durable order)."""

    world: WorldRecord
    bible: BibleRevision
    player: PlayerCharacterRecord | None
    actors: tuple[WorldActorRecord, ...]
    profiles: tuple[ActorProfileRecord, ...]


def create_world_with_bible(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    bible_store: SqliteBibleStore,
    cast_store: SqliteCastStore,
    world_id: str,
    name: str,
    bible_revision_id: str,
    bible: BibleContent,
    template_world_id: str | None = None,
    actors: tuple[ActorSeed, ...] = (),
    player: PlayerSeed | None = None,
    now: str,
) -> Result[WorldCreationOutcome]:
    """Create one world with its initial authority, atomically (see the
    module docstring for the one-short-transaction law, the
    ``world_id``-keyed idempotency and the refusals).

    The payload is validated **before anything is written**; the replay
    read runs before the fresh path's transaction, and the fresh path
    is one ``BEGIN IMMEDIATE`` … ``COMMIT`` whose arms are the stores'
    own no-transaction inserts — the world, its revision-1 ``CURRENT``
    Bible, one ``world_actor`` + ``world_actor_profile`` pair per AI
    seed (in the given order, skipping nothing) and, when declared, the
    player row. ``now`` stamps every row (no hidden clock).
    """

    validated = _validate_payload(
        world_id=world_id,
        name=name,
        bible_revision_id=bible_revision_id,
        bible=bible,
        actors=actors,
        player=player,
    )
    if isinstance(validated, Err):
        return Err(validated.error)

    stored = _stored_shape(
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=world_id,
    )
    if stored is not None:
        return _replay_answer(
            stored,
            world_id=world_id,
            name=name,
            template_world_id=template_world_id,
            bible=bible,
            actors=actors,
            player=player,
        )

    began = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        began = True
        world_store._create_world_tx(  # the arm is the face
            world_id, name, template_world_id, now
        )
        bible_store._seed_bible_tx(
            bible_revision_id, world_id, bible, now
        )
        for seed in actors:
            world_store._bind_actor_tx(
                seed.actor_id, world_id, seed.persona_id, now
            )
            cast_store._seed_actor_profile_tx(
                seed.actor_id,
                world_id,
                story_role=seed.story_role,
                pov_eligible=seed.pov_eligible,
                pov_weight=seed.pov_weight,
                long_term_drive=seed.long_term_drive,
                current_arc_seed=seed.current_arc_seed,
                private_context=seed.private_context,
                now=now,
            )
        if player is not None:
            cast_store._seed_player_character_tx(
                player.player_character_id,
                world_id,
                name=player.name,
                background=player.background,
                appearance=player.appearance,
                abilities=player.abilities,
                limits=player.limits,
                location=player.location,
                state=player.state,
                knowledge_refs=player.knowledge_refs,
                now=now,
            )
    except sqlite3.Error as exc:
        if began:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        return Err(
            DomainError(
                code=_refusal_code(exc),
                message=(
                    f"world {world_id!r} not created with its initial"
                    f" Bible: the whole group rolled back ({exc})"
                ),
            )
        )
    conn.execute("COMMIT")
    return _read_back(
        world_store=world_store,
        bible_store=bible_store,
        cast_store=cast_store,
        world_id=world_id,
    )


def _validate_payload(
    *,
    world_id: str,
    name: str,
    bible_revision_id: str,
    bible: BibleContent,
    actors: tuple[ActorSeed, ...],
    player: PlayerSeed | None,
) -> Result[None]:
    """The payload's own judgement, before anything is written (the
    module docstring's refusal list, ``VALIDATION_FAILED`` family)."""

    if not isinstance(world_id, str) or not world_id.strip():
        return _refuse(
            f"world creation refused: world_id must be a non-empty"
            f" string; got {world_id!r}"
        )
    if not isinstance(name, str) or not name.strip():
        return _refuse(
            f"world {world_id!r} creation refused: the name must be a"
            " non-empty string — a world is born with its name"
        )
    if not isinstance(bible_revision_id, str) or not bible_revision_id.strip():
        return _refuse(
            f"world {world_id!r} creation refused: bible_revision_id must"
            " be a non-empty string (the first revision's own identity)"
        )
    if not isinstance(bible, BibleContent):
        return _refuse(
            f"world {world_id!r} creation refused: bible must be a"
            f" BibleContent; got {type(bible).__name__}"
        )
    if isinstance(actors, (str, bytes)) or not isinstance(
        actors, (list, tuple)
    ):
        return _refuse(
            f"world {world_id!r} creation refused: actors must be a"
            f" sequence of ActorSeed entries; got {type(actors).__name__}"
        )
    seen: set[str] = set()
    for seed in actors:
        if not isinstance(seed, ActorSeed):
            return _refuse(
                f"world {world_id!r} creation refused: every actor seed"
                f" must be an ActorSeed; got {type(seed).__name__}"
            )
        if not isinstance(seed.actor_id, str) or not seed.actor_id.strip():
            return _refuse(
                f"world {world_id!r} creation refused: an actor seed's"
                f" actor_id must be a non-empty string; got"
                f" {seed.actor_id!r}"
            )
        if seed.actor_id in seen:
            return _refuse(
                f"world {world_id!r} creation refused: actor id"
                f" {seed.actor_id!r} appears twice in one payload — one"
                " actor is bound once"
            )
        seen.add(seed.actor_id)
        if not isinstance(seed.persona_id, str) or not seed.persona_id.strip():
            return _refuse(
                f"world {world_id!r} creation refused: actor"
                f" {seed.actor_id!r}'s persona_id must be a non-empty"
                " string (the character_card the actor speaks through)"
            )
        if seed.story_role is not None and not isinstance(
            seed.story_role, StoryRole
        ):
            return _refuse(
                f"world {world_id!r} creation refused: actor"
                f" {seed.actor_id!r}'s story_role must be None or a"
                f" StoryRole word; got {seed.story_role!r}"
            )
        if seed.pov_eligible is not None and not isinstance(
            seed.pov_eligible, bool
        ):
            return _refuse(
                f"world {world_id!r} creation refused: actor"
                f" {seed.actor_id!r}'s pov_eligible must be None or a"
                f" bool; got {seed.pov_eligible!r}"
            )
        if seed.pov_weight is not None and (
            not isinstance(seed.pov_weight, int)
            or isinstance(seed.pov_weight, bool)
            or seed.pov_weight < 0
        ):
            return _refuse(
                f"world {world_id!r} creation refused: actor"
                f" {seed.actor_id!r}'s pov_weight must be None or a"
                f" non-negative integer; got {seed.pov_weight!r}"
            )
        for label, text in (
            ("long_term_drive", seed.long_term_drive),
            ("current_arc_seed", seed.current_arc_seed),
            ("private_context", seed.private_context),
        ):
            if not isinstance(text, str):
                return _refuse(
                    f"world {world_id!r} creation refused: actor"
                    f" {seed.actor_id!r}'s {label} must be a string; got"
                    f" {type(text).__name__}"
                )
    if player is not None:
        if not isinstance(player, PlayerSeed):
            return _refuse(
                f"world {world_id!r} creation refused: player must be"
                f" None or a PlayerSeed; got {type(player).__name__}"
            )
        if (
            not isinstance(player.player_character_id, str)
            or not player.player_character_id.strip()
        ):
            return _refuse(
                f"world {world_id!r} creation refused: the player"
                " character's id must be a non-empty string; got"
                f" {player.player_character_id!r}"
            )
        if not isinstance(player.name, str) or not player.name.strip():
            return _refuse(
                f"world {world_id!r} creation refused: the player"
                " character's name must be a non-empty string — a"
                " half-drawn person does not sit at the table"
            )
        for label, text in (
            ("background", player.background),
            ("appearance", player.appearance),
            ("abilities", player.abilities),
            ("limits", player.limits),
            ("location", player.location),
            ("state", player.state),
            ("knowledge_refs", player.knowledge_refs),
        ):
            if not isinstance(text, str):
                return _refuse(
                    f"world {world_id!r} creation refused: the player"
                    f" character's {label} must be a string; got"
                    f" {type(text).__name__}"
                )
    return Ok(None)


def _refuse(reason: str) -> Err[Any]:
    return Err(
        DomainError(
            code=DomainErrorCode.VALIDATION_FAILED, message=reason
        )
    )


@dataclass(frozen=True)
class _StoredShape:
    """What the world id already holds — the replay comparison's own
    read (``None`` when the world does not exist yet)."""

    world: WorldRecord | None
    bible: BibleRevision | None
    player: PlayerCharacterRecord | None
    actors: tuple[WorldActorRecord, ...]
    profiles: tuple[ActorProfileRecord, ...]


def _stored_shape(
    *,
    world_store: SqliteWorldStore,
    bible_store: SqliteBibleStore,
    cast_store: SqliteCastStore,
    world_id: str,
) -> _StoredShape | None:
    """The durable rows one world id already holds, or ``None`` — the
    replay read (pure; no transaction of its own)."""

    world = world_store.get_world(world_id)
    if world is None:
        return None
    return _StoredShape(
        world=world,
        bible=bible_store.current_bible(world_id),
        player=cast_store.player_character(world_id),
        actors=world_store.actors_of(world_id),
        profiles=cast_store.actor_profiles_of(world_id),
    )


def _replay_answer(
    stored: _StoredShape,
    *,
    world_id: str,
    name: str,
    template_world_id: str | None,
    bible: BibleContent,
    actors: tuple[ActorSeed, ...],
    player: PlayerSeed | None,
) -> Result[WorldCreationOutcome]:
    """The stored world against the payload, field by field — the same
    shape rides back as the stored rows (zero write), any difference is
    ``CONFLICT`` (the module docstring's law)."""

    stored_world = stored.world
    assert stored_world is not None  # _stored_shape answered a world
    if (stored_world.name, stored_world.template_world_id) != (
        name,
        template_world_id,
    ):
        return _clash(
            world_id,
            "its world row differs (name / template)",
        )
    stored_bible = stored.bible
    if stored_bible is None or stored_bible.revision != 1:
        return _clash(
            world_id,
            "it holds no revision-1 Bible (the initial authority this"
            " service creates)",
        )
    if tuple(
        getattr(stored_bible, field) for field in BIBLE_FIELDS
    ) != tuple(getattr(bible, field) for field in BIBLE_FIELDS):
        return _clash(world_id, "its initial Bible's content differs")
    if (stored.player is None) != (player is None):
        return _clash(
            world_id,
            "its player character presence differs (declared vs none)",
        )
    if player is not None and stored.player is not None:
        if (
            stored.player.player_character_id,
            stored.player.name,
            stored.player.background,
            stored.player.appearance,
            stored.player.abilities,
            stored.player.limits,
            stored.player.location,
            stored.player.state,
            stored.player.knowledge_refs,
        ) != (
            player.player_character_id,
            player.name,
            player.background,
            player.appearance,
            player.abilities,
            player.limits,
            player.location,
            player.state,
            player.knowledge_refs,
        ):
            return _clash(
                world_id, "its player character's content differs"
            )
    payload_cast = {seed.actor_id: seed for seed in actors}
    stored_cast = {actor.actor_id: actor for actor in stored.actors}
    if set(payload_cast) != set(stored_cast):
        return _clash(
            world_id,
            "its cast roster differs (the actor ids themselves)",
        )
    profiles = {profile.actor_id: profile for profile in stored.profiles}
    for actor_id, seed in payload_cast.items():
        if str(stored_cast[actor_id].persona_id) != seed.persona_id:
            return _clash(
                world_id,
                f"actor {actor_id!r}'s persona binding differs",
            )
        profile = profiles.get(actor_id)
        if profile is None:
            return _clash(
                world_id, f"actor {actor_id!r} holds no profile"
            )
        if (
            profile.story_role,
            profile.pov_eligible,
            profile.pov_weight,
            profile.long_term_drive,
            profile.current_arc_seed,
            profile.private_context,
        ) != (
            seed.story_role,
            seed.pov_eligible,
            seed.pov_weight,
            seed.long_term_drive,
            seed.current_arc_seed,
            seed.private_context,
        ):
            return _clash(
                world_id, f"actor {actor_id!r}'s profile differs"
            )
    return Ok(
        WorldCreationOutcome(
            world=stored_world,
            bible=stored_bible,
            player=stored.player,
            actors=stored.actors,
            profiles=stored.profiles,
        )
    )


def _clash(world_id: str, reason: str) -> Err[Any]:
    return Err(
        DomainError(
            code=DomainErrorCode.CONFLICT,
            message=(
                f"world {world_id!r} not created: it already exists with"
                f" a different shape — {reason}; the creation service"
                " does not rewrite an existing world (re-read and use the"
                " stored rows, or choose another id)"
            ),
        )
    )


def _read_back(
    *,
    world_store: SqliteWorldStore,
    bible_store: SqliteBibleStore,
    cast_store: SqliteCastStore,
    world_id: str,
) -> Result[WorldCreationOutcome]:
    """The freshly landed group, read back through the stores' public
    read faces (the arms write; the faces answer)."""

    world = world_store.get_world(world_id)
    bible = bible_store.current_bible(world_id)
    assert world is not None  # the group above just landed it
    assert bible is not None
    return Ok(
        WorldCreationOutcome(
            world=world,
            bible=bible,
            player=cast_store.player_character(world_id),
            actors=world_store.actors_of(world_id),
            profiles=cast_store.actor_profiles_of(world_id),
        )
    )


def _refusal_code(exc: sqlite3.Error) -> DomainErrorCode:
    """Map the database's own refusal to the store vocabulary — the
    same three families every store spells: a UNIQUE / PK clash is
    ``CONFLICT``, a FOREIGN KEY refusal is ``NOT_FOUND`` (a referenced
    identity — the template world, the persona card — is missing), any
    other database failure answers ``DEPENDENCY_UNAVAILABLE`` with the
    raw error riding the message."""

    text = str(exc)
    if "UNIQUE constraint failed" in text:
        return DomainErrorCode.CONFLICT
    if "FOREIGN KEY constraint failed" in text:
        return DomainErrorCode.NOT_FOUND
    return DomainErrorCode.DEPENDENCY_UNAVAILABLE
