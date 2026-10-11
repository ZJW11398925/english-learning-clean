"""The world package loader (W-1-4) — builtin worlds as data, not code.

A world package is one JSON file under the repository's ``worlds``
directory (beside ``content_src/``): the world's identity (id, name,
version, calendar_start), its setting prose, the cast it binds through
existing character cards (each member optionally carrying a one-line
``vignette`` of the member's life and — v8 — an optional six-key
narrative profile the seed lands in ``world_actor_profile``: the
Director input saying who is the protagonist, who may carry a POV and
at what weight, what her long-term drive and current arc seed are, and
what is private to her), an optional ``residents`` section —
the town's purely narrative residents, who have no persona and bind no
actor (prompt material, never correspondence faces; the web face's
``world_residents`` reads the *bound* cast and is a different thing) —
an optional ``initial_storylines`` section (v5, C2: the world's opening
arcs, ``{theme, resolve_at}`` pairs the seed lands as migration 0028's
``world_storyline`` rows), an optional ``voice`` section (v6, C3: the
characters' own voice library — see :mod:`elc.world.voice` for the canon
and the faces), an optional ``user_character`` section (v7, D-1: the
reader's own character in the town — her id, name, one-line anchor and
home; prompt material and the ``participants`` vocabulary's extension,
see :class:`UserCharacter`), the pre-authored event pool the engine draws
from, and a supply
declaration. :func:`load_world_package` decodes one
file strictly — bad
JSON, a missing or unexpected key, a value of the wrong shape, an unknown
moment word, an unknown supply family word, a name collision between
a resident and the cast, a voice entry whose character name is not one
of the town's own or whose ``samples`` sides are not
:data:`~elc.world.voice.VOICE_SAMPLE_COUNT` passages each, a
``user_character`` section outside its exact four-key non-empty-string
shape, or a cast member's profile key outside its own shape (a
``story_role`` outside the three canonical words, a non-bool
``pov_eligible``, a negative or non-int ``pov_weight`` or a blank arc
text) are all ``Err``
refusals
whose message names the offending key or word — and
:func:`ensure_builtin_worlds` seeds every ``*.json`` in a directory
through the store's idempotent create/bind faces at open time (and hands
the decoded packages back, so a caller that needs the package faces — the
voice library — reads them from the same pass). Any
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
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.cast import SqliteCastStore, StoryRole
from elc.world.engine.types import Condition, MomentKind, PoolEvent
from elc.world.store import SqliteWorldStore
from elc.world.types import StateEffect
from elc.world.voice import (
    VOICE_MAX_QUIRKS,
    VOICE_SAMPLE_COUNT,
    CharacterVoice,
)

__all__ = [
    "BUILTIN_WORLDS_DIR",
    "SUPPLY_FAMILY_WORDS",
    "WORLD_PACKAGE_VERSION",
    "CastMember",
    "Resident",
    "SupplyDeclaration",
    "UserCharacter",
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

#: The package schema version this loader reads (v8, V3-3 /
#: TASK-OPI-bab4da9f…52): every v7 face is kept (the bilingual pool
#: events, ``calendar_start``, an optional cast ``vignette``, an optional
#: ``residents`` section, an optional ``initial_storylines`` section,
#: the optional ``voice`` library and the optional ``user_character``
#: section), plus the v8 addition — a cast member may carry her
#: narrative profile (``story_role`` / ``pov_eligible`` / ``pov_weight``
#: / ``long_term_drive`` / ``current_arc_seed`` / ``private_context``,
#: all optional; the profile the seed lands in
#: :mod:`elc.world.cast`'s ``world_actor_profile``). A document stamped
#: with any other version
#: is a refusal naming the number — a v7-and-below file cannot ride in
#: half-read, and a future v9 must be read by the cut that writes it,
#: never guessed at by this one.
WORLD_PACKAGE_VERSION = 8


class WorldPackageError(RuntimeError):
    """A builtin world package failed to load or seed (the composition
    boundary raises it so a failed open is loud, never a half-seeded
    world — the ``world_lore`` seed precedent)."""


@dataclass(frozen=True)
class CastMember:
    """One cast row: the character card the actor speaks through (the
    persona must exist as a card when the package seeds), the name
    the world's prose knows it by, — v4, optional — a one-line
    ``vignette`` of the member's off-stage life (identity, daily round,
    and what they care about) the narrator's prompt carries as material,
    and — v8, optional — the member's narrative profile
    (:class:`~elc.world.cast.StoryRole` / ``pov_eligible`` /
    ``pov_weight`` / ``long_term_drive`` / ``current_arc_seed`` /
    ``private_context``): who she is *in this world* — the Director
    input the seed lands in ``world_actor_profile`` (the design
    supplement §7.2's separation: the card answers *who she is*, the
    profile answers *who she is in this world*; never the same
    question, never one table). A member without the six rides as
    before (the profile columns honest ``None`` / empty), and the
    profile face is the seed's business — the loader only decodes and
    validates it (a declared word outside the vocabulary, a non-bool
    ``pov_eligible``, a negative or non-int ``pov_weight`` or a blank
    arc text is a refusal naming the key)."""

    persona_id: str
    name: str
    vignette: str | None = None
    story_role: str | None = None
    pov_eligible: bool | None = None
    pov_weight: int | None = None
    long_term_drive: str | None = None
    current_arc_seed: str | None = None
    private_context: str | None = None


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
class UserCharacter:
    """The reader's own character in the town (v7, D-1 /
    DEC-OPI-a4cf2d0e…40 — the design supplement
    ``docs/IMPLEMENTATION_PLAN.md`` §19's first engineering meaning).

    The world's player is **a resident of the town**, not an outside
    observer (living-world-spec §3.2 v2.2): ``id`` is the durable
    participant id the chronicle's ``participants`` column may name
    (beside the cast's persona ids — the narrator's teaching names it,
    the parser verifies the union), ``name`` what the world calls her,
    ``anchor`` one line saying who she is here, and ``home`` where she
    lives. All four are required non-empty strings (a half-drawn
    resident would ride the narrator's prompt as a half-drawn person).

    Prompt material end to end, plus the id's one parser seat: no
    persona, no character card, no actor binding, no store column —
    the section is the world package's declaration, nothing more. The
    name is the package's default; a later cut may let the user's own
    name override it (the settings face's business, never the
    loader's).
    """

    id: str
    name: str
    anchor: str
    home: str


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
    loaded package every step — a re-seeded package arms the
    material on the next open, and no already-written chronicle is
    rewritten (append-only history, no backfill).

    v5 (C2, DEC-OPI-b290799a…45): ``initial_storylines`` is the world's
    opening arcs as ``(theme, resolve_at)`` pairs — the package names
    the arcs, never their ids: the seed derives each line's id
    (:func:`_line_id_for`, the actor-id derivation's sibling) and lands
    the rows through the store's idempotent create face at open time.
    The section's absence decodes to the empty tuple, an honest
    three-line-capped-by-the-author zero; the reader (:meth:`elc.world.
    store.SqliteWorldStore.active_storylines`) is what the narrator's
    prompt is fed from, and the package's own copy stays here as the
    seed's source.

    v6 (C3, DEC-OPI-a4cf2d0e…6): ``voice`` is the characters' own voice
    library as ``(name, CharacterVoice)`` pairs in the file's own order —
    the key every direct lookup goes through is :meth:`voice_for`, and
    the loader has already promised every name is one of the town's
    (cast ∪ residents, case-insensitively; the one-name-space law). The
    section's absence decodes to the empty tuple — an honest
    no-library world, and the byte-identical prompt law's other half: a
    package without voices renders exactly the pre-v6 bytes on both
    prompt faces. The face is prompt material end to end: no store
    column, no actor binding, no seed row.

    v7 (D-1, DEC-OPI-a4cf2d0e…40): ``user_character`` is the reader's
    own character in the town (:class:`UserCharacter`) — the world
    knows who lives here. The section's absence decodes to ``None``:
    an honest world without a declared player, whose prompt is exactly
    the pre-v7 bytes on both faces and whose ``participants``
    vocabulary is exactly the cast roster (the conditional law).
    """

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
    initial_storylines: tuple[tuple[str, str], ...] = ()
    voice: tuple[tuple[str, CharacterVoice], ...] = ()
    user_character: UserCharacter | None = None

    def to_event_pool(self) -> tuple[PoolEvent, ...]:
        """The engine's pool argument, as loaded (no re-decode)."""

        return self.event_pool

    def voice_for(self, name: str) -> CharacterVoice | None:
        """One character's voice-library entry, or ``None`` when the
        library does not name them — the honest "this character has no
        authored voice yet", never a guessed one.

        The match is case-insensitive (the town's own name-space law:
        prose does not distinguish case, and neither does the town), so a
        caller resolving a cast member's name reaches the entry the file
        spells in its own casing.
        """

        folded = name.casefold()
        for key, voice in self.voice:
            if key.casefold() == folded:
                return voice
        return None

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
#: The optional top-level sections (v4, wr-9; v5, C2; v6, C3; v7, D-1):
#: absent is legal, present is decoded strictly — a section is never
#: half-read.
_PACKAGE_OPTIONAL_KEYS = (
    "residents",
    "initial_storylines",
    "voice",
    "user_character",
)
_CAST_KEYS = ("persona_id", "name")
_CAST_OPTIONAL_KEYS = (
    "vignette",
    "story_role",
    "pov_eligible",
    "pov_weight",
    "long_term_drive",
    "current_arc_seed",
    "private_context",
)
_RESIDENT_KEYS = ("name", "role", "vignette")
#: The v7 ``user_character`` section's exact keys, all required
#: non-empty strings.
_USER_CHARACTER_KEYS = ("id", "name", "anchor", "home")
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
#: The v6 ``voice`` entry's five canon keys, all required, plus the
#: optional sixth (:data:`~elc.world.voice.CharacterVoice`).
_VOICE_KEYS = ("speech_habits", "never_says", "quirks", "samples", "register")
_VOICE_OPTIONAL_KEYS = ("motivation",)
_SAMPLE_KEYS = ("en", "zh")


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
    pre-v4 bare-name shape stays legal) and the optional v8 profile six
    (:class:`~elc.world.cast.StoryRole`'s word for ``story_role``,
    a JSON bool for ``pov_eligible``, a non-negative non-bool int for
    ``pov_weight``, and three non-blank arc texts; absent decodes to
    ``None``/``None`` — the honest undeclared, the profile's NULL/empty
    posture). A declared key outside its shape is a refusal naming the
    key."""

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
    story_role: str | None = None
    if "story_role" in entry:
        raw = entry["story_role"]
        words = {role.value for role in StoryRole}
        if not isinstance(raw, str) or raw not in words:
            return _err(
                f"{where}: story_role must be one of"
                f" {', '.join(sorted(words))} when present,"
                f" got {raw!r}"
            )
        story_role = raw
    pov_eligible: bool | None = None
    if "pov_eligible" in entry:
        raw = entry["pov_eligible"]
        if not isinstance(raw, bool):
            return _err(
                f"{where}: pov_eligible must be a JSON bool when"
                f" present, got {raw!r}"
            )
        pov_eligible = raw
    pov_weight: int | None = None
    if "pov_weight" in entry:
        raw = entry["pov_weight"]
        # `type(raw) is not int` is the bool exclusion too (True is a
        # bool, not an int, under this check — the ``days`` face's own
        # posture): a JSON true/false is not a weight.
        if type(raw) is not int or raw < 0:
            return _err(
                f"{where}: pov_weight must be a non-negative int when"
                f" present, got {raw!r}"
            )
        pov_weight = raw
    arc_texts: dict[str, str | None] = {}
    for key in (
        "long_term_drive",
        "current_arc_seed",
        "private_context",
    ):
        if key in entry:
            raw = entry[key]
            if not isinstance(raw, str) or not raw.strip():
                return _err(
                    f"{where}: {key!r} must be a non-empty string when"
                    " present"
                )
            arc_texts[key] = raw
    return Ok(
        CastMember(
            persona_id=persona_id,
            name=name,
            vignette=vignette,
            story_role=story_role,
            pov_eligible=pov_eligible,
            pov_weight=pov_weight,
            long_term_drive=arc_texts.get("long_term_drive"),
            current_arc_seed=arc_texts.get("current_arc_seed"),
            private_context=arc_texts.get("private_context"),
        )
    )


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


def _decode_user_character(value: object, where: str) -> Result[UserCharacter]:
    """The optional v7 ``user_character`` section (D-1): exactly
    ``{id, name, anchor, home}``, all four required non-empty strings, no
    other key (a missing or unexpected key, or a wrong scalar shape, is
    a refusal naming it — the residents decoder's posture, because the
    section rides the narrator's prompt the same way)."""

    if not isinstance(value, dict):
        return _err(f"{where}: not a JSON object")
    for key in _USER_CHARACTER_KEYS:
        if key not in value:
            return _err(f"{where}: key {key!r} is missing")
    for key in value:
        if key not in _USER_CHARACTER_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    for key in _USER_CHARACTER_KEYS:
        raw = value[key]
        if not isinstance(raw, str) or not raw.strip():
            return _err(f"{where}: {key!r} must be a non-empty string")
    return Ok(
        UserCharacter(
            id=value["id"],
            name=value["name"],
            anchor=value["anchor"],
            home=value["home"],
        )
    )


def _decode_initial_storylines(
    value: object, where: str
) -> Result[tuple[tuple[str, str], ...]]:
    """The v5 ``initial_storylines`` section (C2): an array of
    ``{theme, resolve_at}`` pairs — both required non-empty strings, no
    other key (an arc the seed lands needs its topic and its closure
    condition; anything less is half an arc). An empty array is legal
    (a world with no opening arcs), and shape errors are refused with
    the offending entry named, the residents decoder's posture."""

    if not isinstance(value, list):
        return _err(
            f"{where}: must be an array of theme/resolve_at pairs"
        )
    lines: list[tuple[str, str]] = []
    for index, entry in enumerate(value):
        spot = f"{where} entry {index}"
        if not isinstance(entry, dict):
            return _err(f"{spot}: not a JSON object")
        if set(entry) != {"theme", "resolve_at"}:
            return _err(
                f"{spot}: expected exactly the keys 'theme' and"
                f" 'resolve_at', got {sorted(entry)!r}"
            )
        theme = entry["theme"]
        resolve_at = entry["resolve_at"]
        if not isinstance(theme, str) or not theme.strip():
            return _err(f"{spot}: 'theme' must be a non-empty string")
        if not isinstance(resolve_at, str) or not resolve_at.strip():
            return _err(
                f"{spot}: 'resolve_at' must be a non-empty string"
            )
        lines.append((theme, resolve_at))
    return Ok(tuple(lines))


def _decode_voice_words(
    value: object, where: str
) -> Result[tuple[str, ...]]:
    """The shared string-list shape of ``never_says`` / ``quirks``:
    every entry a non-empty string, no entry declared twice (a repeated
    word is a typo — the supply-families posture). An empty array is
    legal: a person who bans or tics nothing is not half a person, and
    the honest zero costs no refusal."""

    if not isinstance(value, list):
        return _err(f"{where}: must be an array of strings")
    words: list[str] = []
    for index, word in enumerate(value):
        if not isinstance(word, str) or not word.strip():
            return _err(f"{where} entry {index}: must be a non-empty string")
        if word in words:
            return _err(
                f"{where} entry {index}: {word!r} is declared twice"
            )
        words.append(word)
    return Ok(tuple(words))


def _decode_voice_samples(
    value: object, where: str
) -> Result[tuple[tuple[str, ...], tuple[str, ...]]]:
    """The ``{en, zh}`` sample pair (域三 裁断点五, the user's
    adjudication: 「语样双语各三段——英文为源 + 中文对照」): each side
    exactly :data:`~elc.world.voice.VOICE_SAMPLE_COUNT` non-empty
    passages, English the source and Chinese its companion. A section
    whose sides disagree in count — or whose side is not exactly the
    canon's number — is refused with the offending side and the count in
    the message (half a paired library cannot ride in silently)."""

    if not isinstance(value, dict):
        return _err(f"{where}: not a JSON object")
    for key in _SAMPLE_KEYS:
        if key not in value:
            return _err(f"{where}: key {key!r} is missing")
    for key in value:
        if key not in _SAMPLE_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    sides: dict[str, tuple[str, ...]] = {}
    for key in _SAMPLE_KEYS:
        raw = value[key]
        if not isinstance(raw, list) or len(raw) != VOICE_SAMPLE_COUNT:
            got = len(raw) if isinstance(raw, list) else repr(raw)
            return _err(
                f"{where}: {key!r} must be an array of exactly"
                f" {VOICE_SAMPLE_COUNT} passages (the canon's bilingual"
                f" pair — English the source, Chinese its companion),"
                f" got {got}"
            )
        for index, passage in enumerate(raw):
            if not isinstance(passage, str) or not passage.strip():
                return _err(
                    f"{where}: {key!r} entry {index} must be a non-empty"
                    " string"
                )
        sides[key] = tuple(raw)
    return Ok((sides["en"], sides["zh"]))


def _decode_voice_entry(entry: object, where: str) -> Result[CharacterVoice]:
    """One voice-library entry: the canon's five keys — ``speech_habits``
    / ``never_says`` / ``quirks`` / ``samples`` / ``register`` — all
    required, plus the optional sixth ``motivation`` (one static
    sentence, R4's P6 first leg). A missing or unexpected key is a
    refusal naming it; the quirks ceiling and the bilingual sample pair
    are the canon's own bounds."""

    if not isinstance(entry, dict):
        return _err(f"{where}: not a JSON object")
    for key in _VOICE_KEYS:
        if key not in entry:
            return _err(f"{where}: key {key!r} is missing")
    for key in entry:
        if key not in _VOICE_KEYS and key not in _VOICE_OPTIONAL_KEYS:
            return _err(f"{where}: unexpected key {key!r}")
    speech_habits = entry["speech_habits"]
    register = entry["register"]
    if not isinstance(speech_habits, str) or not speech_habits.strip():
        return _err(f"{where}: speech_habits must be a non-empty string")
    if not isinstance(register, str) or not register.strip():
        return _err(f"{where}: register must be a non-empty string")
    never_says = _decode_voice_words(
        entry["never_says"], f"{where}: never_says"
    )
    if isinstance(never_says, Err):
        return never_says
    quirks = _decode_voice_words(entry["quirks"], f"{where}: quirks")
    if isinstance(quirks, Err):
        return quirks
    if len(quirks.value) > VOICE_MAX_QUIRKS:
        return _err(
            f"{where}: quirks must carry at most {VOICE_MAX_QUIRKS}"
            f" entries (the canon's ceiling), got {len(quirks.value)}"
        )
    samples = _decode_voice_samples(entry["samples"], f"{where}: samples")
    if isinstance(samples, Err):
        return samples
    motivation: str | None = None
    if "motivation" in entry:
        raw = entry["motivation"]
        if not isinstance(raw, str) or not raw.strip():
            return _err(
                f"{where}: motivation must be a non-empty string when"
                " present"
            )
        motivation = raw
    samples_en, samples_zh = samples.value
    return Ok(
        CharacterVoice(
            speech_habits=speech_habits,
            register=register,
            quirks=quirks.value,
            never_says=never_says.value,
            samples_en=samples_en,
            samples_zh=samples_zh,
            motivation=motivation,
        )
    )


def _decode_voice_section(
    value: object, where: str, known_names: frozenset[str]
) -> Result[tuple[tuple[str, CharacterVoice], ...]]:
    """The optional v6 ``voice`` section (C3): a JSON object mapping each
    character name to the five-key voice entry. Every name must be one
    of the town's own — the cast's or a resident's, case-insensitively
    (``known_names`` carries them folded) — two names colliding
    case-insensitively are refused (the one-name-space law continues),
    and an empty object is the same honest zero as an absent section.
    The file's own order survives into the returned tuple: it is the
    order both prompt faces render in, and re-reading the same file
    answers the same order."""

    if not isinstance(value, dict):
        return _err(
            f"{where}: must be an object mapping character names to"
            " voice entries"
        )
    seen: set[str] = set()
    entries: list[tuple[str, CharacterVoice]] = []
    for name, entry in value.items():
        if not isinstance(name, str) or not name.strip():
            return _err(f"{where}: character names must be non-empty strings")
        folded = name.casefold()
        if folded in seen:
            return _err(
                f"{where}: character name {name!r} collides with another"
                " voice entry's name (one town, one name-space,"
                " case-insensitively)"
            )
        seen.add(folded)
        if folded not in known_names:
            return _err(
                f"{where}: character name {name!r} is neither a cast"
                " member nor a resident of this world (the voice library's"
                " names are the town's own names)"
            )
        decoded = _decode_voice_entry(entry, f"{where}: {name}")
        if isinstance(decoded, Err):
            return decoded
        entries.append((name, decoded.value))
    return Ok(tuple(entries))


def _decode_pool_event(entry: object, where: str) -> Result[PoolEvent]:
    """One pool event: ``kind`` / ``narration`` / ``narration_zh`` /
    ``days`` required (the Chinese narration is not optional prose, it
    is the package's second language; ``days`` is the story's own span,
    a v3 face kept through v4 and v5 and v6 — a negative or non-int span would
    move the
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
    than :data:`WORLD_PACKAGE_VERSION` (v8 — the v7 face kept, plus an
    optional per-cast-member narrative profile), a
    duplicated event kind, an unknown moment word, an unknown supply
    family word, a resident whose name collides with the cast's or with
    another resident's (case-insensitively), an ``initial_storylines``
    entry outside the exact ``{theme, resolve_at}`` shape, a v6
    ``voice`` entry whose character name is neither the cast's nor a
    resident's — whose name collides with another entry's, whose shape is
    not the canon's five keys (plus the optional ``motivation``), whose
    ``quirks`` exceed the ceiling or whose ``samples`` sides are not
    :data:`~elc.world.voice.VOICE_SAMPLE_COUNT` passages each — and a
    v7 ``user_character`` section outside its exact four-key
    non-empty-string shape. The loader
    never guesses
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
            f" loader reads v{WORLD_PACKAGE_VERSION} packages — the v7"
            " face kept, plus an optional per-cast-member narrative"
            " profile: story_role / pov_eligible / pov_weight /"
            " long_term_drive / current_arc_seed / private_context —"
            " the Director input the seed lands in"
            " world_actor_profile;"
            " v7-and-below files are refused rather than read half-way),"
            f" got {version}"
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
    raw_storylines = document.get("initial_storylines", [])
    decoded_storylines = _decode_initial_storylines(
        raw_storylines, f"{where}: initial_storylines"
    )
    if isinstance(decoded_storylines, Err):
        return decoded_storylines
    # v6 (C3, DEC-OPI-a4cf2d0e…6): the voice library — decoded after the
    # residents so the name-space check sees the whole town (cast +
    # residents), the one-name-space law the resident decoder opened.
    raw_voice = document.get("voice", {})
    decoded_voice = _decode_voice_section(
        raw_voice, f"{where}: voice", frozenset(known_names)
    )
    if isinstance(decoded_voice, Err):
        return decoded_voice
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
    # v7 (D-1, DEC-OPI-a4cf2d0e…40): the reader's own character — decoded
    # after the town's own faces (the section is prompt material and the
    # participants vocabulary's one extension; the town's name-space
    # checks are the cast's and the residents', unchanged). Absent
    # decodes to ``None`` — the honest world without a declared player;
    # an explicit ``null`` is present-but-wrong-shape and refused, the
    # residents / voice siblings' own posture.
    user_character: UserCharacter | None = None
    if "user_character" in document:
        decoded_user = _decode_user_character(
            document["user_character"], f"{where}: user_character"
        )
        if isinstance(decoded_user, Err):
            return decoded_user
        user_character = decoded_user.value
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
            initial_storylines=decoded_storylines.value,
            voice=decoded_voice.value,
            user_character=user_character,
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


def _line_id_for(world_id: str, ordinal: int) -> str:
    """The derived storyline id: ``line-<world token>-<ordinal,
    zero-padded>`` — ``world-berrymoor`` plus the package's own order
    derives ``line-berrymoor-0000``. The ordinal is the section
    position at seed time, so a replayed seed re-derives the same ids
    and lands through the store's idempotent create face; zero-padding
    keeps the ids and the durable order legible past ten lines
    (``_run_id_for``'s own spelling)."""

    world_token = world_id.removeprefix("world-")
    return f"line-{world_token}-{ordinal:04d}"


def _bible_id_for(world_id: str, revision: int) -> str:
    """The derived Bible revision id: ``bible-<world token>-<revision
    zero-padded>`` — ``world-berrymoor`` derives ``bible-berrymoor-0001``."""

    world_token = world_id.removeprefix("world-")
    return f"bible-{world_token}-{revision:04d}"


def _bible_calendar_for(calendar_start: str) -> str:
    """The creation-time mapping of the package's calendar declaration
    (v3, A2's ``calendar_start``) into the Bible's ``calendar`` field —
    the instance calendar's authority seat: ``start=<ISO date>``. V3
    readers take the world's epoch from here and never re-read the
    package for it."""
    return f"start={calendar_start}"


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
    bible_store: SqliteBibleStore,
    cast_store: SqliteCastStore,
) -> tuple[WorldPackage, ...]:
    """Seed every ``*.json`` world package in ``worlds_dir`` into the
    store, idempotently, at composition time, and return the decoded
    packages (in the same sorted-by-file-name order) for callers that
    need the package faces — the v6 voice library is the first one:
    re-reading the files a second time would be a second decode of the
    same bytes, so the seed hands back what it read.

    One deterministic pass, sorted by file name. Each package is decoded
    strictly (:func:`load_world_package` — an ``Err`` raises, the message
    carries the refusal), the package's cast personas are verified to
    exist as character cards through the caller-wired ``persona_exists``
    face **before any write**, then the world is created through the
    store's idempotent ``create_world`` (a replay of the same id and
    shape is a no-op, so an open re-seed writes nothing) and each cast
    member is bound under the derived actor id (see
    :func:`_actor_id_for` — ``world-berrymoor`` plus the cast name's
    given word derives ``actor-berrymoor-nell``). The package's v5
    ``initial_storylines`` land the same way, through the store's
    idempotent ``create_storyline`` under the derived line ids (see
    :func:`_line_id_for`) — a re-seed re-derives the same ids and
    rewrites nothing. The v6 ``voice`` section seeds nothing: it is
    prompt material, and the returned package carries it whole. The v7
    ``user_character`` section seeds nothing either — no persona, no
    actor binding, no row: it is prompt material plus the
    ``participants`` vocabulary's one extension, and the returned
    package carries it whole (the narrator and the chronicle read are
    its consumers, not this seed).

    V3-2 (DEC-OPI-bab4da9f…29): a world's birth carries its Bible's
    seed — the seed is attempted in the same open pass, immediately
    after each ``create_world`` lands in its own short transaction
    (**two separate short transactions, not one ACID group**;
    fail-closed and idempotent, so a retry of an interrupted open
    completes a partial seed — a truly atomic world+initial-Bible
    creation service for user-created worlds is a registered
    later-cut obligation, not built here). The package's ``setting``
    prose becomes the Bible's ``premise`` and the package's
    ``calendar_start`` rides the creation-time mapping
    (:func:`_bible_calendar_for`) into the Bible's ``calendar`` — the
    instance calendar's authority seat — while the other twelve
    content fields stay the empty string (honest undeclared: the
    template spoke only what it declared). The content rides the
    caller-wired ``bible_store``'s idempotent ``seed_bible`` under the
    derived revision id (see :func:`_bible_id_for`). The face is
    idempotent and **never rewriting** (N-INV-006's machine half): a
    re-open re-seeds nothing, and a template file edited between opens
    changes no stored row — the instance Bible's authority lives in
    ``world_bible_revision``, and a template's later update making it
    into a stored world is an explicit revision decision, never a
    silent push. The ``bible_store`` keyword is **required**,
    deliberately: no caller can silently skip the Bible seed and open
    a world without its authority row (the ``persona_exists``
    keyword's own posture — fail-closed, the same family).

    V3-3 (TASK-OPI-bab4da9f…52): a world's birth also carries its cast
    narrative profiles and its durable player character — the Director
    input (who is the protagonist, who may carry a POV and at what
    weight, what each AI actor's long-term drive and current arc seed
    are, what is private to each, and who the player is) landed as
    migration 0031's rows through the caller-wired ``cast_store``
    (**another required keyword**, the same fail-closed family — no
    open skips the cast's durable half). Each cast member's profile is
    seeded **immediately after her ``bind_actor`` lands** —
    ``story_role`` / ``pov_eligible`` / ``pov_weight`` riding the
    package's declared values (absent honest ``None``) and the three
    arc texts the package's words (absent the empty string) — and the
    package's ``user_character`` lands as the world's one
    ``world_player_character`` row under the **same id the package
    declares** (``actor-berrymoor-you`` stays ``actor-berrymoor-you``):
    name from the package's ``name``, background from the
    ``anchor``, location from the ``home``, the rest honestly empty.
    Both seeds ride the same atomicity posture as the Bible's (the
    V3-2R corrected wording): **two separate short transactions, not
    one ACID group**, fail-closed and idempotent, so a retry of an
    interrupted open completes a partial seed — and **never
    rewriting**: a replayed open re-seeds nothing, and a template file
    edited between opens (a member's arc re-worded, the player's name
    changed) changes no stored row — the instance profile and the
    instance player are the authority, and a template's later update
    making it into a stored world is an explicit later decision, never
    a silent push. The old ``world_actor`` chain is untouched (the
    design supplement §7.1's boundary); the narrator's roster and the
    ``participants`` vocabulary it computes live are *not* rewired by
    this cut — the durable namespace half
    (:func:`elc.world.cast.participant_namespace`) is the derivation
    the later cuts' consumers read.

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
    packages: list[WorldPackage] = []
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
        # V3-2 (DEC-OPI-bab4da9f…29): the world's birth carries its
        # Bible's seed — attempted immediately after the create_world
        # above, in its own short transaction (two separate short
        # transactions, not one ACID group; fail-closed and idempotent,
        # so a retry of an interrupted open completes a partial seed).
        # The package's setting prose as the premise, the calendar_start
        # through the creation-time calendar mapping, the other twelve
        # fields honestly undeclared. The face is idempotent and never
        # rewriting (N-INV-006: a template's later update replayed
        # through this seed changes no stored row — a re-open writes
        # nothing, a re-worded template is silently ignored), so a
        # failed seed here means the database itself refused (the FK's
        # dangling world), and fail-closed is the same posture every
        # other seed refusal below keeps.
        content = BibleContent(
            premise=" · ".join(package.setting),
            calendar=_bible_calendar_for(package.calendar_start),
        )
        seeded_bible = bible_store.seed_bible(
            _bible_id_for(package.world_id, 1), package.world_id, content, now
        )
        if isinstance(seeded_bible, Err):
            raise WorldPackageError(
                f"builtin world {package.world_id!r} Bible not seeded:"
                f" {seeded_bible.error.message}"
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
            # V3-3 (TASK-OPI-bab4da9f…52): each member's narrative
            # profile lands immediately after her bind — the Director
            # input (story role, POV eligibility and weight, the
            # long-term drive, the current arc's seed, the private
            # context) as migration 0031's world_actor_profile row.
            # The face is idempotent and never rewriting (a replayed
            # open writes nothing; a template's later edit is silently
            # ignored), and the same atomicity posture as the Bible's
            # seed above holds: its own short transaction, fail-closed
            # (a refusal here fails this open — never a half-cast
            # world).
            seeded_profile = cast_store.seed_actor_profile(
                actor_id,
                package.world_id,
                story_role=(
                    StoryRole(member.story_role)
                    if member.story_role is not None
                    else None
                ),
                pov_eligible=member.pov_eligible,
                pov_weight=member.pov_weight,
                long_term_drive=member.long_term_drive or "",
                current_arc_seed=member.current_arc_seed or "",
                private_context=member.private_context or "",
                now=now,
            )
            if isinstance(seeded_profile, Err):
                raise WorldPackageError(
                    f"builtin world {package.world_id!r}: actor"
                    f" {actor_id!r} narrative profile not seeded:"
                    f" {seeded_profile.error.message}"
                )
        # V3-3 (TASK-OPI-bab4da9f…52): the package's ``user_character``
        # becomes the world's one durable player character under the
        # same id the package declares — name from the package's name,
        # background from the anchor, location from the home, the rest
        # honestly empty. The same idempotent, never-rewriting,
        # fail-closed posture as every seed above.
        if package.user_character is not None:
            seeded_player = cast_store.seed_player_character(
                package.user_character.id,
                package.world_id,
                name=package.user_character.name,
                background=package.user_character.anchor,
                location=package.user_character.home,
                now=now,
            )
            if isinstance(seeded_player, Err):
                raise WorldPackageError(
                    f"builtin world {package.world_id!r}: player"
                    " character not seeded:"
                    f" {seeded_player.error.message}"
                )
        # v5 (C2, DEC-OPI-b290799a…45): the package's opening arcs land
        # through the store's idempotent create face — the derived line
        # id plus the same section shape replays as a no-op, so an open
        # re-seed writes nothing. The lines are born ``active`` with no
        # opening event (``opened_by=None``: a package-initial line has
        # no chronicle row to name — the migration's own no-FK
        # posture); closure is the projection's or the explicit face's
        # business, never the seed's.
        for ordinal, (theme, resolve_at) in enumerate(
            package.initial_storylines
        ):
            line_id = _line_id_for(package.world_id, ordinal)
            seeded_line = store.create_storyline(
                line_id, package.world_id, theme, None, resolve_at, now
            )
            if isinstance(seeded_line, Err):
                raise WorldPackageError(
                    f"builtin world {package.world_id!r}: storyline"
                    f" {line_id!r} not seeded:"
                    f" {seeded_line.error.message}"
                )
        packages.append(package)
    return tuple(packages)
