"""The world package loader (W-1-4) — builtin worlds as data, not code.

A world package is one JSON file under the repository's ``worlds``
directory (beside ``content_src/``): the world's identity (id, name,
version, calendar_start), its setting prose, the cast it binds through
existing character cards (each member optionally carrying a one-line
``vignette`` of the member's life), an optional ``residents`` section —
the town's purely narrative residents, who have no persona and bind no
actor (prompt material, never correspondence faces; the web face's
``world_residents`` reads the *bound* cast and is a different thing) —
the pre-authored event pool the engine draws from, and a supply
declaration. :func:`load_world_package` decodes one
file strictly — bad
JSON, a missing or unexpected key, a value of the wrong shape, an unknown
moment word, an unknown supply family word or a name collision between
a resident and the cast are all ``Err`` refusals
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
from datetime import UTC, date, datetime, timedelta
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
    "WORLD_PACKAGE_VERSION",
    "CastMember",
    "Resident",
    "SupplyDeclaration",
    "WorldPackage",
    "WorldPackageError",
    "ensure_builtin_worlds",
    "load_world_package",
    "story_days_of",
    "story_elapsed_days_of",
    "world_date_of",
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

#: The package schema version this loader reads (v4, wr-9 /
#: DEC-OPI-c73dbff3…50): every pool event still carries its narration in
#: both languages and the package its ``calendar_start`` (the v3 face,
#: kept), plus the v4 additions — a cast member may carry an optional
#: one-line ``vignette`` of their life, and the package may carry an
#: optional ``residents`` section naming the town's purely narrative
#: residents (no persona, no actor binding). A document stamped with any
#: other version is a refusal naming the number — a v3-and-below file
#: cannot ride in half-read, and a future v5 must be read by the cut
#: that writes it, never guessed at by this one.
WORLD_PACKAGE_VERSION = 4


class WorldPackageError(RuntimeError):
    """A builtin world package failed to load or seed (the composition
    boundary raises it so a failed open is loud, never a half-seeded
    world — the ``world_lore`` seed precedent)."""


@dataclass(frozen=True)
class CastMember:
    """One cast row: the character card the actor speaks through (the
    persona must exist as a card when the package seeds), the name
    the world's prose knows it by, and — v4, optional — a one-line
    ``vignette`` of the member's off-stage life (identity, daily round,
    and what they care about) the narrator's prompt carries as material.
    A member without a vignette rides the prompt as a bare name (the
    pre-v4 shape, still legal)."""

    persona_id: str
    name: str
    vignette: str | None = None


@dataclass(frozen=True)
class Resident:
    """One purely narrative resident (v4, wr-9): a name, a role in the
    town's life, and a one-line vignette — all three required non-empty.

    A resident has **no persona and binds no actor**: they are prompt
    material for the narrator's cast-of-the-town face, never
    correspondence faces (no letters to or from a resident; the web
    face's ``world_residents`` rows are the *bound cast*, a different
    thing). The loader refuses a resident whose name collides with the
    cast's or with another resident's, case-insensitively — one town,
    one name-space."""

    name: str
    role: str
    vignette: str


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
    """One decoded world package — the JSON file's sections in their
    durable shapes.

    ``event_pool`` already carries the engine's own record shapes
    (:class:`~elc.world.engine.types.PoolEvent` with its
    :class:`~elc.world.engine.types.Condition` and
    :class:`~elc.world.types.StateEffect` parts), and
    :meth:`to_event_pool` is the bridge the engine consumes: the package
    is engine-ready as loaded, with no second translation.

    W-L: ``narrations_zh`` is the pool's Chinese narrations as
    ``(kind, narration_zh)`` pairs — the presentation face's lookup
    source (:meth:`narration_zh_for`), so the inbox can render the
    package's own Chinese prose without re-reading the file. Kinds are
    unique in a pool (the loader refuses a duplicate), so the kind key is
    total over the package's own events.

    A2 (DEC-…88): ``calendar_start`` is the virtual world calendar's
    day zero — an ISO date. The world's story does not follow real time
    (spec §198); every presented day derives from this start through
    :func:`world_date_of`, and no world presentation face ever renders
    the caller's wall clock.

    v4 (wr-9, DEC-OPI-c73dbff3…50): ``residents`` is the town's purely
    narrative cast (:class:`Resident` — no persona, no actor binding);
    the section's absence in the file decodes to the empty tuple, an
    honest zero-resident world. The narrator reads it live from the
    loaded package every step — a re-seeded v4 package arms the
    material on the next open, and no already-written chronicle is
    rewritten (append-only history, no backfill)."""

    world_id: str
    name: str
    version: int
    calendar_start: str
    setting: tuple[str, ...]
    cast: tuple[CastMember, ...]
    event_pool: tuple[PoolEvent, ...]
    supply: SupplyDeclaration
    narrations_zh: tuple[tuple[str, str], ...] = ()
    residents: tuple[Resident, ...] = ()

    def to_event_pool(self) -> tuple[PoolEvent, ...]:
        """The engine's pool argument, as loaded (no re-decode)."""

        return self.event_pool

    def narration_zh_for(self, kind: str) -> str | None:
        """The Chinese narration for one event kind, or ``None`` when the
        kind is not this package's (the caller's honest fallback to the
        English row — a v1-era durable event, or a kind the pool never
        carried, renders in English and says so, never guessed into
        Chinese)."""

        for key, narration in self.narrations_zh:
            if key == kind:
                return narration
        return None


_PACKAGE_KEYS = (
    "world_id",
    "name",
    "version",
    "calendar_start",
    "setting",
    "cast",
    "event_pool",
    "supply",
)
#: The optional top-level sections (v4, wr-9): absent is legal, present
#: is decoded strictly — a section is never half-read.
_PACKAGE_OPTIONAL_KEYS = ("residents",)
_CAST_KEYS = ("persona_id", "name")
_CAST_OPTIONAL_KEYS = ("vignette",)
_RESIDENT_KEYS = ("name", "role", "vignette")
_EVENT_REQUIRED_KEYS = ("kind", "narration", "narration_zh", "days")
_EVENT_KEYS = (
    "kind",
    "narration",
    "narration_zh",
    "days",
    "effects",
    "conditions",
    "moment",
)
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
    """One cast row: ``{persona_id, name}`` required, plus the optional
    v4 ``vignette`` (a one-line life; absent decodes to ``None`` — the
    pre-v4 bare-name shape stays legal)."""

    if not isinstance(entry, dict):
        return _err(f"{where}: not a JSON object")
    for key in _CAST_KEYS:
        if key not in entry:
            return _err(f"{where}: key {key!r} is missing")
    for key in entry:
        if key not in _CAST_KEYS and key not in _CAST_OPTIONAL_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    persona_id = entry["persona_id"]
    name = entry["name"]
    if not isinstance(persona_id, str) or not persona_id:
        return _err(f"{where}: persona_id must be a non-empty string")
    if not isinstance(name, str) or not name:
        return _err(f"{where}: name must be a non-empty string")
    vignette: str | None = None
    if "vignette" in entry:
        raw = entry["vignette"]
        if not isinstance(raw, str) or not raw.strip():
            return _err(
                f"{where}: vignette must be a non-empty string when"
                " present"
            )
        vignette = raw
    return Ok(CastMember(persona_id=persona_id, name=name, vignette=vignette))


def _decode_resident(entry: object, where: str) -> Result[Resident]:
    """One purely narrative resident: exactly ``{name, role, vignette}``,
    all three required non-empty strings (a resident is prompt
    material — a half-drawn one would ride the narrator's prompt as a
    half-drawn person)."""

    if not isinstance(entry, dict):
        return _err(f"{where}: not a JSON object")
    for key in _RESIDENT_KEYS:
        if key not in entry:
            return _err(f"{where}: key {key!r} is missing")
    for key in entry:
        if key not in _RESIDENT_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    for key in _RESIDENT_KEYS:
        value = entry[key]
        if not isinstance(value, str) or not value.strip():
            return _err(f"{where}: {key!r} must be a non-empty string")
    return Ok(
        Resident(
            name=entry["name"], role=entry["role"], vignette=entry["vignette"]
        )
    )


def _decode_pool_event(entry: object, where: str) -> Result[PoolEvent]:
    """One pool event: ``kind`` / ``narration`` / ``narration_zh`` /
    ``days`` required (the Chinese narration is not optional prose, it
    is the package's second language; ``days`` is the story's own span,
    a v3 face kept in v4 — a negative or non-int span would move the
    world's calendar by
    a lie), ``effects`` / ``conditions`` / ``moment`` optional (the
    engine shapes' own defaults). An unknown moment word is refused with
    the word in the message — the vocabulary is exactly ``NOTICE`` /
    ``RESPONSE`` (``DIRECTION`` is W-2-2's, and cannot ride in through
    a package)."""

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
    narration_zh = entry["narration_zh"]
    if not isinstance(kind, str) or not kind:
        return _err(f"{where}: kind must be a non-empty string")
    if not isinstance(narration, str) or not narration:
        return _err(f"{where}: narration must be a non-empty string")
    if not isinstance(narration_zh, str) or not narration_zh.strip():
        return _err(
            f"{where}: narration_zh must be a non-empty string"
        )
    days = entry["days"]
    if type(days) is not int or days < 0:
        # A2 (DEC-…90): the story's own span — a non-negative int; the
        # calendar is story-driven, so a wrong span is a wrong world.
        return _err(
            f"{where}: days must be a non-negative int, got {days!r}"
        )
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
            days=days,
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
    unexpected top-level key, a value of the wrong shape, a version other
    than :data:`WORLD_PACKAGE_VERSION` (v4 — the v3 face kept, plus an
    optional cast ``vignette`` and an optional ``residents`` section), a
    duplicated event kind, an unknown moment word, an unknown supply
    family word, a resident whose name collides with the cast's or with
    another resident's (case-insensitively). The loader never guesses
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
        if key not in _PACKAGE_KEYS and key not in _PACKAGE_OPTIONAL_KEYS:
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
    if version != WORLD_PACKAGE_VERSION:
        return _err(
            f"{where}: version must be {WORLD_PACKAGE_VERSION} (this"
            f" loader reads v{WORLD_PACKAGE_VERSION} packages — the v3"
            " face kept, plus an optional cast vignette and an optional"
            " residents section; v3-and-below files are refused rather"
            " than read half-way), got"
            f" {version}"
        )
    calendar_start = document["calendar_start"]
    if not isinstance(calendar_start, str) or not calendar_start.strip():
        return _err(
            f"{where}: calendar_start must be a non-empty ISO date"
            " (YYYY-MM-DD)"
        )
    try:
        date.fromisoformat(calendar_start)
    except ValueError:
        return _err(
            f"{where}: calendar_start must be an ISO date (YYYY-MM-DD),"
            f" got {calendar_start!r}"
        )
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
    raw_residents = document.get("residents", [])
    if not isinstance(raw_residents, list):
        return _err(f"{where}: residents must be an array")
    residents: list[Resident] = []
    # One name-space across the whole town: a resident colliding with
    # the cast or with another resident is a refusal naming the name
    # (case-insensitively — prose does not distinguish case, and neither
    # does the town).
    known_names = {member.name.casefold() for member in members}
    for index, entry in enumerate(raw_residents):
        decoded_resident = _decode_resident(
            entry, f"{where}: residents entry {index}"
        )
        if isinstance(decoded_resident, Err):
            return decoded_resident
        resident = decoded_resident.value
        folded = resident.name.casefold()
        if folded in known_names:
            return _err(
                f"{where}: resident name {resident.name!r} collides with"
                " an existing name (cast and residents share one"
                " name-space, case-insensitively)"
            )
        known_names.add(folded)
        residents.append(resident)
    pool = document["event_pool"]
    if not isinstance(pool, list) or not pool:
        return _err(f"{where}: event_pool must be a non-empty array")
    events: list[PoolEvent] = []
    narrations_zh: list[tuple[str, str]] = []
    for index, entry in enumerate(pool):
        decoded_event = _decode_pool_event(
            entry, f"{where}: event_pool entry {index}"
        )
        if isinstance(decoded_event, Err):
            return decoded_event
        event = decoded_event.value
        if any(event.kind == seen for seen, _ in narrations_zh):
            # v2 (W-L): the Chinese narrations are a kind-keyed mapping,
            # so a duplicate kind would make the lookup ambiguous — a
            # refusal naming the kind, never a silent overwrite.
            return _err(
                f"{where}: event kind {event.kind!r} is declared twice"
                " (a pool's kinds are unique — the Chinese narrations"
                " are looked up by kind)"
            )
        narrations_zh.append((event.kind, entry["narration_zh"]))
        events.append(event)
    decoded_supply = _decode_supply(document["supply"], f"{where}: supply")
    if isinstance(decoded_supply, Err):
        return decoded_supply
    return Ok(
        WorldPackage(
            world_id=world_id,
            name=name,
            version=version,
            calendar_start=calendar_start,
            setting=tuple(setting),
            cast=tuple(members),
            event_pool=tuple(events),
            supply=decoded_supply.value,
            narrations_zh=tuple(narrations_zh),
            residents=tuple(residents),
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


def story_days_of(
    package: WorldPackage,
    store: SqliteWorldStore,
    world_id: str,
) -> int:
    """The story's elapsed span (A2, DEC-…88/…90): the happened events'
    ``days`` summed, in the package's own kind→span mapping.

    The world's calendar is **story-driven** — it moves when the story's
    events say so, never because a letter was written (the run cursor is
    deliberately not a clock). A durable kind the package does not carry
    (v1-era history) contributes zero: the package does not invent a
    span it never authored.

    WR-2's disposition (DEC-OPI-5fc42174-…49 评审 MEDIUM): this pool-keyed
    sum is **no longer the calendar's base** — a generated world's kinds
    carry no package span, so summing them yields a frozen day zero (and,
    worse, a letter could stamp before its predecessor). The base is
    :func:`story_elapsed_days_of`; this function stays for the retired
    engine path's own accounting and its pins."""

    days_by_kind = {event.kind: event.days for event in package.event_pool}
    return sum(days_by_kind.get(kind, 0) for kind in store.event_kinds_of(world_id))


def story_elapsed_days_of(
    package: WorldPackage,
    store: SqliteWorldStore,
    world_id: str,
) -> int:
    """The story's elapsed span as the **furthest day ever stamped**
    (WR-2's disposition): the maximum, over the chronicle's events, of
    the day distance between a pure virtual-calendar stamp and the
    ``calendar_start`` — the story's own furthest reach, pool-era and
    generated events alike, monotonic by construction (a later letter
    can never stamp before an earlier one).

    A pure stamp is an ``occurred_at`` that is a bare ISO date
    (``YYYY-MM-DD`` — the virtual calendar's own form); a wall-clock
    moment (the pre-A2 legacy rows) is not a story day and contributes
    nothing — the same law the presentation faces already read (legacy
    rows answer no story date). An unreadable chronicle answers ``0``
    (the defensive floor the presentation faces' own guards carry — a
    store failure never fabricates a later day)."""

    start = date.fromisoformat(package.calendar_start)
    chronicle = store.chronicle_of(world_id)
    if isinstance(chronicle, Err):
        return 0
    elapsed = 0
    for event in chronicle.value:
        stamp = str(event.occurred_at)
        if len(stamp) != 10:
            continue
        try:
            day = date.fromisoformat(stamp)
        except ValueError:
            continue
        elapsed = max(elapsed, (day - start).days)
    return elapsed


def world_date_of(
    package: WorldPackage,
    store: SqliteWorldStore,
    world_id: str,
) -> str:
    """The world's own today (A2, DEC-…88/…90) — the virtual calendar's
    date, derived, never clocked.

    Spec §198: the world does not follow real time. WR-2's disposition:
    the world's day is ``calendar_start`` plus the story's **furthest
    stamped day** (:func:`story_elapsed_days_of`) — a pure function of
    the durable chronicle: a replayed history answers the same day
    (AD-6's determinism carried into time), a different story answers a
    different day even at the same letter count, and a generated beat
    advances the world's today by its own span (the pool-keyed sum of
    :func:`story_days_of` froze at day zero once the pool left the
    production path). The engine stays clockless — the presentation
    faces render from the events' ``occurred_at``, so a real wall-clock
    moment never enters a world event."""

    start = date.fromisoformat(package.calendar_start)
    return (
        start + timedelta(days=story_elapsed_days_of(package, store, world_id))
    ).isoformat()


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
