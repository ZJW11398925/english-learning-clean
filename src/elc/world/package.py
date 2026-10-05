"""The world package loader (W-1-4) — builtin worlds as data, not code.

A world package is one JSON file under the repository's ``worlds/``
directory (beside ``content_src/``): the world's identity (id, name,
version), its setting prose, the cast it binds through existing character
cards, the pre-authored event pool the engine draws from, and a supply
declaration. :func:`load_world_package` decodes one file strictly — bad
JSON, a missing or unexpected key, a value of the wrong shape, an unknown
moment word or an unknown supply family word are all ``Err`` refusals
whose message names the offending key or word — and
:func:`ensure_builtin_worlds` seeds every ``*.json`` in a directory
through the store's idempotent create/bind faces at open time. Any
refusal (or a cast persona with no character card) raises
:class:`WorldPackageError`, so the composition root's open fails loudly
instead of serving a half-seeded world — the ``world_lore`` seed
precedent (``elc.world_lore.content``), fail-closed.

There is no build pipeline: a world package is read as it ships. The
build-and-artifact discipline (deterministic digests, audit records, a
versioned schema constant) is the ``elc.content`` domain's, not this
one's — if world packages ever need those, that is a registered future
cut, not a stub smuggled in here.

The supply declaration is **declared-not-consumed** (W-1-4): the
families word travels with the package and nothing in the runtime reads
it yet. The loader still validates its shape and vocabulary — a typo
must not ride in silently — and the declaration waits for the cut that
consumes it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.engine.types import Condition, MomentKind, PoolEvent
from elc.world.store import SqliteWorldStore
from elc.world.types import StateEffect

__all__ = [
    "BUILTIN_WORLDS_DIR",
    "SUPPLY_FAMILY_WORDS",
    "CastMember",
    "SupplyDeclaration",
    "WorldPackage",
    "WorldPackageError",
    "ensure_builtin_worlds",
    "load_world_package",
]

#: The repository's builtin worlds directory (``worlds/`` at the repo
#: root) — the default :func:`ensure_builtin_worlds` reads, overridable
#: per call (tests inject a temporary directory).
BUILTIN_WORLDS_DIR = Path(__file__).resolve().parents[3] / "worlds"

#: The supply declaration's family vocabulary (W-1-4): the five capability
#: families whose canonical realizations exist in the current corpus
#: (``cap-disc-topic-shift`` / ``cap-eval-hedged-opinion`` /
#: ``cap-interact-backchannel`` / ``cap-ref-ask-clarification`` /
#: ``cap-stance-soften-disagreement``). Deliberately narrower than
#: ``elc.curriculum.types.CapabilityFamily``'s fourteen curriculum words:
#: a package may only declare supply the corpus can actually serve, and a
#: word outside this five is a load refusal, not a note.
SUPPLY_FAMILY_WORDS: tuple[str, ...] = (
    "DISC",
    "EVAL",
    "INTERACT",
    "REF",
    "STANCE",
)


class WorldPackageError(RuntimeError):
    """A builtin world package failed to load or seed (the composition
    boundary raises it so a failed open is loud, never a half-seeded
    world — the ``world_lore`` seed precedent)."""


@dataclass(frozen=True)
class CastMember:
    """One cast row: the character card the actor speaks through (the
    persona must exist as a card when the package seeds) and the name
    the world's prose knows it by."""

    persona_id: str
    name: str


@dataclass(frozen=True)
class SupplyDeclaration:
    """The package's supply face — declared, not consumed (W-1-4).

    ``families`` are capability-family words from
    :data:`SUPPLY_FAMILY_WORDS`; ``note`` is the declaration's own
    sentence — the JSON file carries it as the supply section's first
    key, because JSON has no comments and the note is the comment."""

    families: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class WorldPackage:
    """One decoded world package — the JSON file's seven sections in
    their durable shapes.

    ``event_pool`` already carries the engine's own record shapes
    (:class:`~elc.world.engine.types.PoolEvent` with its
    :class:`~elc.world.engine.types.Condition` and
    :class:`~elc.world.types.StateEffect` parts), and
    :meth:`to_event_pool` is the bridge the engine consumes: the package
    is engine-ready as loaded, with no second translation."""

    world_id: str
    name: str
    version: int
    setting: tuple[str, ...]
    cast: tuple[CastMember, ...]
    event_pool: tuple[PoolEvent, ...]
    supply: SupplyDeclaration

    def to_event_pool(self) -> tuple[PoolEvent, ...]:
        """The engine's pool argument, as loaded (no re-decode)."""

        return self.event_pool


_PACKAGE_KEYS = (
    "world_id",
    "name",
    "version",
    "setting",
    "cast",
    "event_pool",
    "supply",
)
_CAST_KEYS = ("persona_id", "name")
_EVENT_REQUIRED_KEYS = ("kind", "narration")
_EVENT_KEYS = ("kind", "narration", "effects", "conditions", "moment")
_PAIR_KEYS = frozenset({"key", "statement"})
_SUPPLY_KEYS = ("families", "note")


def _err(message: str) -> Err[WorldPackage]:
    """One strict-decode refusal — the offending key or word rides the
    message, so the caller's receipt can quote the file's own mistake."""

    return Err(
        DomainError(code=DomainErrorCode.VALIDATION_FAILED, message=message)
    )


def _decode_statement_pairs(
    value: object, where: str
) -> Result[tuple[tuple[str, str], ...]]:
    """The shared ``[{key, statement}]`` array shape: every entry an
    object with exactly the two non-empty-string keys."""

    if not isinstance(value, list):
        return _err(f"{where}: must be an array of key/statement pairs")
    pairs: list[tuple[str, str]] = []
    for index, entry in enumerate(value):
        spot = f"{where} entry {index}"
        if not isinstance(entry, dict):
            return _err(f"{spot}: not a JSON object")
        if set(entry) != _PAIR_KEYS:
            return _err(
                f"{spot}: expected exactly the keys 'key' and"
                f" 'statement', got {sorted(entry)!r}"
            )
        key = entry["key"]
        statement = entry["statement"]
        if not isinstance(key, str) or not key:
            return _err(f"{spot}: 'key' must be a non-empty string")
        if not isinstance(statement, str) or not statement:
            return _err(f"{spot}: 'statement' must be a non-empty string")
        pairs.append((key, statement))
    return Ok(tuple(pairs))


def _decode_cast_member(entry: object, where: str) -> Result[CastMember]:
    """One cast row, exactly ``{persona_id, name}``."""

    if not isinstance(entry, dict):
        return _err(f"{where}: not a JSON object")
    for key in _CAST_KEYS:
        if key not in entry:
            return _err(f"{where}: key {key!r} is missing")
    for key in entry:
        if key not in _CAST_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    persona_id = entry["persona_id"]
    name = entry["name"]
    if not isinstance(persona_id, str) or not persona_id:
        return _err(f"{where}: persona_id must be a non-empty string")
    if not isinstance(name, str) or not name:
        return _err(f"{where}: name must be a non-empty string")
    return Ok(CastMember(persona_id=persona_id, name=name))


def _decode_pool_event(entry: object, where: str) -> Result[PoolEvent]:
    """One pool event: ``kind`` / ``narration`` required, ``effects`` /
    ``conditions`` / ``moment`` optional (the engine shapes' own
    defaults). An unknown moment word is refused with the word in the
    message — the vocabulary is exactly ``NOTICE`` / ``RESPONSE``
    (``DIRECTION`` is W-2-2's, and cannot ride in through a package)."""

    if not isinstance(entry, dict):
        return _err(f"{where}: not a JSON object")
    for key in _EVENT_REQUIRED_KEYS:
        if key not in entry:
            return _err(f"{where}: key {key!r} is missing")
    for key in entry:
        if key not in _EVENT_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    kind = entry["kind"]
    narration = entry["narration"]
    if not isinstance(kind, str) or not kind:
        return _err(f"{where}: kind must be a non-empty string")
    if not isinstance(narration, str) or not narration:
        return _err(f"{where}: narration must be a non-empty string")
    effects: tuple[StateEffect, ...] = ()
    if "effects" in entry:
        decoded = _decode_statement_pairs(entry["effects"], f"{where}: effects")
        if isinstance(decoded, Err):
            return decoded
        effects = tuple(
            StateEffect(key=key, statement=statement)
            for key, statement in decoded.value
        )
    conditions: tuple[Condition, ...] = ()
    if "conditions" in entry:
        decoded = _decode_statement_pairs(
            entry["conditions"], f"{where}: conditions"
        )
        if isinstance(decoded, Err):
            return decoded
        conditions = tuple(
            Condition(canonical_key=key, statement=statement)
            for key, statement in decoded.value
        )
    if "moment" in entry:
        word = entry["moment"]
        if not isinstance(word, str):
            return _err(f"{where}: moment must be a string")
        try:
            moment = MomentKind(word)
        except ValueError:
            return _err(
                f"{where}: unknown moment word {word!r} (the vocabulary"
                " is NOTICE / RESPONSE)"
            )
    else:
        moment = MomentKind.RESPONSE
    return Ok(
        PoolEvent(
            kind=kind,
            narration=narration,
            effects=effects,
            conditions=conditions,
            moment=moment,
        )
    )


def _decode_supply(value: object, where: str) -> Result[SupplyDeclaration]:
    """The supply declaration: ``families`` from the declared vocabulary,
    ``note`` the JSON-file comment (declared-not-consumed)."""

    if not isinstance(value, dict):
        return _err(f"{where}: not a JSON object")
    for key in _SUPPLY_KEYS:
        if key not in value:
            return _err(f"{where}: key {key!r} is missing")
    for key in value:
        if key not in _SUPPLY_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    families = value["families"]
    note = value["note"]
    if not isinstance(families, list) or not families:
        return _err(f"{where}: families must be a non-empty array of words")
    seen: list[str] = []
    for index, word in enumerate(families):
        if not isinstance(word, str) or not word:
            return _err(f"{where}: families entry {index} must be a string")
        if word not in SUPPLY_FAMILY_WORDS:
            return _err(
                f"{where}: unknown supply family word {word!r} (the"
                " declared vocabulary is"
                f" {', '.join(SUPPLY_FAMILY_WORDS)})"
            )
        if word in seen:
            return _err(f"{where}: supply family {word!r} is declared twice")
        seen.append(word)
    if not isinstance(note, str) or not note.strip():
        return _err(f"{where}: note must be a non-empty string")
    return Ok(SupplyDeclaration(families=tuple(seen), note=note))


def load_world_package(path: str | Path) -> Result[WorldPackage]:
    """Decode one world package file, strictly.

    Every refusal is an ``Err`` naming the file and the offending key or
    word: unreadable file, bad JSON, a non-object document, a missing or
    unexpected top-level key, a value of the wrong shape, an unknown
    moment word, an unknown supply family word. The loader never guesses
    past an error — fail-closed decoding, the caller decides what a
    refusal means (the builtin seed answers: a failed open).
    """

    where = str(path)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return _err(f"{where}: cannot be read ({exc})")
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        return _err(f"{where}: not valid JSON ({exc})")
    if not isinstance(document, dict):
        return _err(f"{where}: the document is not a JSON object")
    for key in _PACKAGE_KEYS:
        if key not in document:
            return _err(f"{where}: key {key!r} is missing")
    for key in document:
        if key not in _PACKAGE_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    world_id = document["world_id"]
    name = document["name"]
    if not isinstance(world_id, str) or not world_id:
        return _err(f"{where}: world_id must be a non-empty string")
    if not isinstance(name, str) or not name:
        return _err(f"{where}: name must be a non-empty string")
    version = document["version"]
    if type(version) is not int:
        return _err(f"{where}: version must be an integer")
    setting = document["setting"]
    if not isinstance(setting, list) or not setting:
        return _err(f"{where}: setting must be a non-empty array of paragraphs")
    for index, paragraph in enumerate(setting):
        if not isinstance(paragraph, str) or not paragraph.strip():
            return _err(
                f"{where}: setting paragraph {index} must be a non-empty string"
            )
    cast = document["cast"]
    if not isinstance(cast, list) or not cast:
        return _err(f"{where}: cast must be a non-empty array")
    members: list[CastMember] = []
    for index, entry in enumerate(cast):
        decoded = _decode_cast_member(entry, f"{where}: cast entry {index}")
        if isinstance(decoded, Err):
            return decoded
        members.append(decoded.value)
    pool = document["event_pool"]
    if not isinstance(pool, list) or not pool:
        return _err(f"{where}: event_pool must be a non-empty array")
    events: list[PoolEvent] = []
    for index, entry in enumerate(pool):
        decoded_event = _decode_pool_event(
            entry, f"{where}: event_pool entry {index}"
        )
        if isinstance(decoded_event, Err):
            return decoded_event
        events.append(decoded_event.value)
    decoded_supply = _decode_supply(document["supply"], f"{where}: supply")
    if isinstance(decoded_supply, Err):
        return decoded_supply
    return Ok(
        WorldPackage(
            world_id=world_id,
            name=name,
            version=version,
            setting=tuple(setting),
            cast=tuple(members),
            event_pool=tuple(events),
            supply=decoded_supply.value,
        )
    )


def _actor_id_for(world_id: str, name: str) -> str:
    """The derived actor id: ``actor-<world token>-<given name>`` —
    ``world-berrymoor`` plus the cast name's given word derives
    ``actor-berrymoor-nell``. Two cast members sharing a given name
    under one world would derive the same id and fail loudly at the
    bind (``CONFLICT``), never bind silently."""

    world_token = world_id.removeprefix("world-")
    parts = name.split()
    given = parts[0].lower() if parts else ""
    return f"actor-{world_token}-{given}"


def ensure_builtin_worlds(
    store: SqliteWorldStore,
    worlds_dir: Path | None = None,
    *,
    persona_exists: Callable[[str], bool],
) -> None:
    """Seed every ``*.json`` world package in ``worlds_dir`` into the
    store, idempotently, at composition time.

    One deterministic pass, sorted by file name. Each package is decoded
    strictly (:func:`load_world_package` — an ``Err`` raises, the message
    carries the refusal), the package's cast personas are verified to
    exist as character cards through the caller-wired ``persona_exists``
    face **before any write**, then the world is created through the
    store's idempotent ``create_world`` (a replay of the same id and
    shape is a no-op, so an open re-seed writes nothing) and each cast
    member is bound under the derived actor id (see
    :func:`_actor_id_for` — ``world-berrymoor`` plus the cast name's
    given word derives ``actor-berrymoor-nell``).

    Every failure raises :class:`WorldPackageError` — the composition
    root's open fails closed (the ``world_lore`` seed posture: a database
    that cannot carry its builtin worlds must not open as if nothing
    were missing). A missing directory is the same refusal: there is no
    reading of the builtin worlds under which zero of them is success.
    """

    directory = BUILTIN_WORLDS_DIR if worlds_dir is None else Path(worlds_dir)
    if not directory.is_dir():
        raise WorldPackageError(
            f"builtin worlds directory {directory} does not exist; the"
            " builtin worlds cannot be seeded, so the open fails closed"
        )
    for path in sorted(directory.glob("*.json")):
        loaded = load_world_package(path)
        if isinstance(loaded, Err):
            raise WorldPackageError(
                f"builtin world package {path.name} refused:"
                f" {loaded.error.message}"
            )
        package = loaded.value
        for member in package.cast:
            if not persona_exists(member.persona_id):
                raise WorldPackageError(
                    f"builtin world {package.world_id!r}: cast persona"
                    f" {member.persona_id!r} has no character card; the"
                    " world cannot bind its cast, so the open fails closed"
                )
        now = datetime.now(tz=UTC).isoformat()
        created = store.create_world(package.world_id, package.name, None, now)
        if isinstance(created, Err):
            raise WorldPackageError(
                f"builtin world {package.world_id!r} not seeded:"
                f" {created.error.message}"
            )
        for member in package.cast:
            actor_id = _actor_id_for(package.world_id, member.name)
            bound = store.bind_actor(
                actor_id, package.world_id, member.persona_id, now
            )
            if isinstance(bound, Err):
                raise WorldPackageError(
                    f"builtin world {package.world_id!r}: actor"
                    f" {actor_id!r} not bound for persona"
                    f" {member.persona_id!r}: {bound.error.message}"
                )
