"""The World Director's V3-4 machine face (TASK-OPI-be7b094f…11 /
DEC-OPI-be7b094f…7) — the schema-and-table side of the cut: the strict
Blueprint schema, the durable cast-input assembly, the context read
face, and the two write faces that land a Blueprint as an adopted plan
revision and reconcile its ``scenes[]`` against ``world_scene``
(:meth:`Director.open_next_chapter` / :meth:`Director.revise_blueprint`).

**Scope (the ruling's own words — schema-and-table-side-only)**: the
LLM driven Blueprint *production* face (prompt / provider / strict
parse) is not here; it is registered as its own later cut (a V3-8 Gold
Scenario dependency). What ships here is what the contract spells:

- **The strict Blueprint schema** (DATA §26.2.1's V3-4 block — the L3
  landing; :func:`validate_blueprint`): the nine chapter fields
  verbatim, the ``scenes[]`` canonical key set
  (:data:`BLUEPRINT_SCENE_KEYS` — ``purpose`` / ``place`` /
  ``pov_actor_id`` / ``participants`` / ``planned_start_tick`` /
  ``entry_goals`` / ``exit_condition`` / ``elasticity`` /
  ``revealable`` / ``must_hide``; a missing key or a wrong type is
  refused), the canonical identity law (AI side =
  ``world_actor.actor_id``, user side =
  ``world_player_character.player_character_id``; a ``persona_id`` or
  a resident name is not a V3 participant — the V3-3R freeze), and the
  Director's own supplemental keys (beats / gate hints, whatever the
  Director grows) passing through unjudged.

- **The wording law's schema half** (the design doc §2.2 / §三 1.5):
  **the soft-expectation set is never a postcondition** —
  ``closing_pressure`` says *where the chapter presses*, never *where
  it must arrive*; hard conditions may only be world rules / happened
  causality / irrevocable facts. The machine half of the law here is
  the non-empty-string check on the four soft fields plus this
  docstring's pin; there is deliberately **no postcondition detector**
  — a manufactured one would be exactly the rail-switch the law
  forbids (the Director is not the railway's dispatcher).

- **The durable cast-input assembly** (:func:`build_cast_input`; the
  V3-3R external review's item 5): ``world_actor`` (the actor ids) +
  ``character_card.name`` (the live ``web._world_actor_names`` join,
  ``world_actor → character_card.name``; a card the table does not
  name falls back to the actor id) + ``world_actor_profile`` +
  ``world_player_character``, unified through
  :func:`elc.world.cast.participant_namespace`. **The Package is a seed
  source, never the runtime authority** — nothing here reads it (no
  import, no table; pinned by a source scan). The player's
  ``location`` / ``state`` / ``knowledge_refs`` are the creation-time
  seed (the V3-3R freeze) and deliberately do not exist on
  :class:`DirectorPlayerCharacter` — their current authority is
  ``world_state_fact`` / V3-7's actor memory.

- **The Director's context read face** (:func:`build_director_context`):
  the current Bible revision, the cast input, the world's
  ``active_storylines`` (migration 0028, live) and its ``current_facts``
  (the ``world_state_fact`` CURRENT half, migration 0024). Chapter
  Summaries and Reader Exposure do not exist yet: they are V3-7's /
  V3-5's arms, registered here as such.

- **The two write faces — Plan-face only** (the Plan≠Canon pin):
  :meth:`Director.open_next_chapter` mints the next chapter
  (``PLANNED`` — it never opens a chapter; the ``ACTIVE`` flip is the
  lifecycle face's), creates and adopts plan revision 1, and creates
  one ``PLANNED`` ``world_scene`` anchor per ``scenes[]`` element.
  :meth:`Director.revise_blueprint` appends the next plan revision and
  reconciles by **position** (the L3 rules): a new ordinal gets a new
  ``PLANNED`` row; a vanished ordinal's still-``PLANNED`` row is
  discarded; an ``ACTIVE`` / ``COMMITTED`` / ``CLOSED`` row is never
  touched (N-INV-003 — a replanning has no write power over what
  happened); a surviving ordinal's row is not touched even when the
  element's content changed (the row is a progress anchor, the JSON is
  the content source); a ``scene_index`` is never re-used.
  **The Director never advances ``world.current_tick``** (#3 /
  N-INV-007 — the commit transactions are the only movers) and writes
  **no canon progress word at all**: what it lands is a plan revision
  plus position anchors (the Plan≠Canon boundary of the L3 block).

The derivation laws (DATA §26.2.1's L3 block, spelled word for word):
``chapter_id = f"{world_id}-ch{chapter_index:02d}"``,
``plan_id = f"{chapter_id}-bp-r{plan_revision}"`` and
``scene_id = f"{chapter_id}-s{scene_index:02d}"`` — derived ids serve
idempotence and reconciliation only (narrative time attribution never
rides an id's naming, §26.2.2's lineage requirement). A same-id replay
of any single store write is the store's own idempotent no-op; the
Director composes those writes one step at a time and owns no replay
buffer of its own.

Discipline (the house store law, :mod:`elc.world.narrative.store`'s
posture): **value semantics** — every refusal is a ``Result`` ``Err``,
never an exception (``VALIDATION_FAILED`` for the caller's own payload,
``NOT_FOUND`` for a dangling world / chapter, and any store refusal
riding out unchanged); **no hidden clock** (every row's stamps ride the
caller's ``now`` — the write faces take it as a parameter); **no
transaction of its own** — the Director composes the store's own short
transactions (the store faces already own ``BEGIN IMMEDIATE`` …
``COMMIT``; a nested BEGIN would break exactly that composability, the
:mod:`elc.world.time` posture); **no SQL string building** — the one
read join below is parameter-bound literals, and every write goes
through :class:`~elc.world.narrative.store.SqliteNarrativeStore`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.bible import BibleRevision, SqliteBibleStore
from elc.world.cast import (
    ActorProfileRecord,
    SqliteCastStore,
    participant_namespace,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    SceneStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneRecord,
    encode_scenes,
)
from elc.world.store import SqliteWorldStore, WorldStorylineRecord
from elc.world.types import WorldStateFact

__all__ = [
    "BLUEPRINT_SCENE_KEYS",
    "ChapterBlueprint",
    "ChapterOpening",
    "Director",
    "DirectorCastInput",
    "DirectorCastMember",
    "DirectorContext",
    "DirectorPlayerCharacter",
    "build_cast_input",
    "build_director_context",
    "chapter_id_for",
    "plan_id_for",
    "scene_id_for",
    "validate_blueprint",
]

#: The ``scenes[]`` element's canonical key set (DATA §26.2.1's V3-4
#: block, word for word): the ten keys every Blueprint scene carries.
#: A missing key or a wrong type is refused; keys beyond this set are
#: the Director's own (beats, gate hints) and are not judged.
BLUEPRINT_SCENE_KEYS = (
    "purpose",
    "place",
    "pov_actor_id",
    "participants",
    "planned_start_tick",
    "entry_goals",
    "exit_condition",
    "elasticity",
    "revealable",
    "must_hide",
)

#: The chapter's own nine fields (§26.2.1): every one is required (a
#: missing one is refused); their types are checked field by field.
_BLUEPRINT_TEXT_FIELDS = (
    "goal",
    "dramatic_question",
)
_BLUEPRINT_TICK_FIELDS = (
    "planned_start_tick",
    "planned_end_tick",
)
#: The soft-expectation set — the four fields the wording law names
#: (never a postcondition; the schema refuses an empty/blank one).
_SOFT_EXPECTATION_FIELDS = (
    "closing_pressure",
    "desired_development",
    "soft_outcomes",
    "chapter_questions_to_advance",
)
#: The scene element's plain-text keys (the canonical set minus the
#: identity pair and the tick).
_SCENE_TEXT_KEYS = (
    "purpose",
    "place",
    "entry_goals",
    "exit_condition",
    "elasticity",
    "revealable",
    "must_hide",
)


@dataclass(frozen=True)
class DirectorCastMember:
    """One AI-controlled actor as the Director sees her — assembled from
    durable instance data alone (the V3-3R item-5 recipe).

    ``actor_id`` is the canonical V3 participant identity (not the
    persona id); ``name`` is the card's display name with the fallback
    law (a card the table does not name, or names emptily, falls back
    to the actor id — a plain signature, never a broken one);
    ``profile`` is the ``world_actor_profile`` row, or ``None`` for an
    actor the world never seeded a profile for (the honest undeclared).
    """

    actor_id: str
    name: str
    profile: ActorProfileRecord | None


@dataclass(frozen=True)
class DirectorPlayerCharacter:
    """The reader's own durable character as the Director sees her — the
    profile face only: her id, name and background.

    The V3-3R seed freeze is carried **structurally**: ``location`` /
    ``state`` / ``knowledge_refs`` are creation-time seed, not running
    facts, and deliberately do not exist on this shape — the current
    location and state's authority is ``world_state_fact``, the current
    knowledge / belief's is V3-7's actor memory. A consumer that wants
    the seed reads the cast store's own record and knows what it is
    reading; the Director's input simply cannot carry the seed by
    accident.
    """

    player_character_id: str
    name: str
    background: str


@dataclass(frozen=True)
class DirectorCastInput:
    """The Director's cast input: the world's AI actors (id ascending),
    the reader's character (or ``None`` — the conditional law), and
    :func:`elc.world.cast.participant_namespace`'s frozen vocabulary
    over exactly those two durable identity sources.
    """

    members: tuple[DirectorCastMember, ...]
    player_character: DirectorPlayerCharacter | None
    namespace: frozenset[str]


@dataclass(frozen=True)
class DirectorContext:
    """What the Director's first planning reads today.

    The arms are the ones the contract names: the Bible revision (the
    instance-level world authority), the cast input, the world's
    ``active_storylines`` (0028's two-layer read) and the
    ``world_state_fact`` CURRENT half (0024). Chapter Summaries and
    Reader Exposure are **not** arms yet — they are V3-7's / V3-5's
    (registered; a later cut grows this shape, not a placeholder now).
    """

    world_id: str
    bible: BibleRevision | None
    cast: DirectorCastInput
    storylines: tuple[WorldStorylineRecord, ...]
    current_facts: tuple[WorldStateFact, ...]


@dataclass(frozen=True)
class ChapterBlueprint:
    """One validated Blueprint — the chapter fields verbatim, and the
    ``scenes`` table as the caller's own mappings (canonical keys
    validated, identities checked against the namespace, supplemental
    keys passed through unjudged).

    The scenes ride **as given** (insertion order included): the store's
    :func:`~elc.world.narrative.types.encode_scenes` law freezes them
    deterministically, so a replay of the same payload writes the same
    bytes and the store's idempotent creation answers the stored row.
    """

    goal: str
    dramatic_question: str
    planned_start_tick: int
    planned_end_tick: int
    closing_pressure: str
    desired_development: str
    soft_outcomes: str
    chapter_questions_to_advance: str
    scenes: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ChapterOpening:
    """A write face's ``Ok`` shape: the chapter row (``PLANNED``), its
    adopted plan revision, and the chapter's scene anchors after the
    reconciliation, ``scene_index`` ascending (discarded anchors
    included — history is rows, not errors).
    """

    chapter: WorldChapterRecord
    plan: WorldChapterPlanRecord
    scenes: tuple[WorldSceneRecord, ...]


# ---------------------------------------------------------------------------
# the derivation laws (DATA §26.2.1's L3 block, word for word)
# ---------------------------------------------------------------------------


def chapter_id_for(world_id: str, chapter_index: int) -> str:
    """The chapter identity law: ``f"{world_id}-ch{chapter_index:02d}"``
    — deterministic within a world, replayable, and serving idempotence
    / reconciliation only (never narrative time attribution)."""

    return f"{world_id}-ch{chapter_index:02d}"


def plan_id_for(chapter_id: str, plan_revision: int) -> str:
    """The plan identity law: ``f"{chapter_id}-bp-r{plan_revision}"`` —
    the revision number without zero padding, the contract's own
    spelling."""

    return f"{chapter_id}-bp-r{plan_revision}"


def scene_id_for(chapter_id: str, scene_index: int) -> str:
    """The scene anchor identity law:
    ``f"{chapter_id}-s{scene_index:02d}"`` — the array ordinal's own
    name."""

    return f"{chapter_id}-s{scene_index:02d}"


# ---------------------------------------------------------------------------
# the strict Blueprint schema (the L3 landing; value semantics only)
# ---------------------------------------------------------------------------


def _refuse(reason: str) -> Err[Any]:
    """One schema refusal as a human sentence (the
    :func:`~elc.world.narrative.types.decode_scenes` message shape)."""

    return Err(
        DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=f"Blueprint refused: {reason}",
        )
    )


def _scene_refusal(
    scene: Mapping[str, Any], ordinal: int, namespace: frozenset[str]
) -> str | None:
    """The canonical key set's own refusals for one ``scenes[]`` element
    (DATA §26.2.1's L3 block, key by key) — the reason sentence, or
    ``None`` when the element passes.

    ``ordinal`` is the array position (1-based) — the blueprint's own
    word for the position the reconciliation keys on, so a refusal
    names the same coordinate the diff will use. Supplemental keys are
    the Director's own: unjudged in meaning, but the element must still
    be JSON-encodable (the plan row's ``scenes`` column is JSON — a
    value the column cannot carry is refused here, in the caller's own
    vocabulary, rather than exploding out of the store's encoder).
    """

    for key in _SCENE_TEXT_KEYS:
        if key not in scene:
            return (
                f"scenes[{ordinal}] is missing the canonical key {key!r}"
                " (the L3 scene key set)"
            )
        if not isinstance(scene[key], str):
            return (
                f"scenes[{ordinal}].{key} must be a string; got"
                f" {type(scene[key]).__name__}"
            )
    if "planned_start_tick" not in scene:
        return (
            f"scenes[{ordinal}] is missing the canonical key"
            " 'planned_start_tick' (the L3 scene key set)"
        )
    tick = scene["planned_start_tick"]
    if isinstance(tick, bool) or not isinstance(tick, int):
        return (
            f"scenes[{ordinal}].planned_start_tick must be an integer"
            f" tick; got {tick!r}"
        )
    if "pov_actor_id" not in scene:
        return (
            f"scenes[{ordinal}] is missing the canonical key"
            " 'pov_actor_id' (the L3 scene key set)"
        )
    pov = scene["pov_actor_id"]
    if not isinstance(pov, str):
        return (
            f"scenes[{ordinal}].pov_actor_id must be a string; got"
            f" {type(pov).__name__}"
        )
    if pov not in namespace:
        return (
            f"scenes[{ordinal}].pov_actor_id {pov!r} is not a canonical"
            " participant identity — the namespace is the durable cast's"
            " actor ids union the player character id (V3-3R freeze: a"
            " persona id is a template identity, a resident name is"
            " prose)"
        )
    if "participants" not in scene:
        return (
            f"scenes[{ordinal}] is missing the canonical key"
            " 'participants' (the L3 scene key set)"
        )
    participants = scene["participants"]
    if isinstance(participants, (str, bytes)) or not isinstance(
        participants, (list, tuple)
    ):
        return (
            f"scenes[{ordinal}].participants must be a sequence of"
            " participant identities (the durable namespace); got"
            f" {type(participants).__name__}"
        )
    for word in participants:
        if not isinstance(word, str):
            return (
                f"scenes[{ordinal}].participants carries a non-string"
                f" entry {word!r}"
            )
        if word not in namespace:
            return (
                f"scenes[{ordinal}].participants name {word!r} is not a"
                " canonical participant identity — the namespace is the"
                " durable cast's actor ids union the player character id"
                " (V3-3R freeze: a persona id is a template identity, a"
                " resident name is prose)"
            )
    try:
        encode_scenes((dict(scene),))
    except (TypeError, ValueError) as exc:
        return (
            f"scenes[{ordinal}] is not JSON-encodable (the plan row's"
            f" scenes column is JSON): {exc}"
        )
    return None


def validate_blueprint(
    payload: Mapping[str, Any], *, namespace: frozenset[str]
) -> Result[ChapterBlueprint]:
    """The Blueprint's strict schema (DATA §26.2.1's V3-4 block; the
    machine face of the wording law's schema half).

    Refused, every one as a value-semantics ``VALIDATION_FAILED`` naming
    the offending field (never an exception, never a partial answer):

    - the payload not being a mapping;
    - a missing / mistyped chapter field — the nine §26.2.1 fields are
      all required, the six text fields must be strings, the two ticks
      integers (a bool is not a tick);
    - an empty / blank soft-expectation field (the four the wording law
      names: ``closing_pressure`` / ``desired_development`` /
      ``soft_outcomes`` / ``chapter_questions_to_advance`` — a
      direction must be stated; the fields are **never** a
      postcondition, and the schema has no detector for one);
    - ``scenes`` not being a sequence of mappings, or an element missing
      a canonical key (:data:`BLUEPRINT_SCENE_KEYS`) or carrying a
      wrong type;
    - an identity outside ``namespace`` — ``pov_actor_id`` and every
      ``participants`` word must be a durable V3 participant (an AI
      actor's ``actor_id`` or the ``player_character_id``; a
      ``persona_id`` and a resident name are both refused — the V3-3R
      freeze), and an element that is not JSON-encodable.

    Supplemental keys beyond the canonical set are the Director's own
    and pass through **verbatim** into the returned records (the
    scenes keep the caller's mappings and their insertion order).
    """

    if not isinstance(payload, Mapping):
        return _refuse(
            "the payload must be a mapping of the chapter fields; got"
            f" {type(payload).__name__}"
        )
    for key in _BLUEPRINT_TEXT_FIELDS:
        if key not in payload:
            return _refuse(
                f"the chapter field {key!r} is missing (the nine"
                " §26.2.1 chapter fields are all required)"
            )
        if not isinstance(payload[key], str):
            return _refuse(
                f"the chapter field {key!r} must be a string; got"
                f" {type(payload[key]).__name__}"
            )
    for key in _SOFT_EXPECTATION_FIELDS:
        if key not in payload:
            return _refuse(
                f"the chapter field {key!r} is missing (the nine"
                " §26.2.1 chapter fields are all required)"
            )
        value = payload[key]
        if not isinstance(value, str):
            return _refuse(
                f"the chapter field {key!r} must be a string; got"
                f" {type(value).__name__}"
            )
        if not value.strip():
            return _refuse(
                f"the chapter field {key!r} must be a non-empty string —"
                " the soft-expectation set states a direction, never a"
                " postcondition (the wording law, design §2.2)"
            )
    for key in _BLUEPRINT_TICK_FIELDS:
        if key not in payload:
            return _refuse(
                f"the chapter field {key!r} is missing (the nine"
                " §26.2.1 chapter fields are all required)"
            )
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int):
            return _refuse(
                f"the chapter field {key!r} must be an integer tick; got"
                f" {value!r}"
            )
    if "scenes" not in payload:
        return _refuse(
            "the chapter field 'scenes' is missing (the nine §26.2.1"
            " chapter fields are all required)"
        )
    raw_scenes = payload["scenes"]
    if isinstance(raw_scenes, (str, bytes)) or not isinstance(
        raw_scenes, (list, tuple)
    ):
        return _refuse(
            "the chapter field 'scenes' must be a sequence of scene"
            f" mappings; got {type(raw_scenes).__name__}"
        )
    scenes: list[dict[str, Any]] = []
    for ordinal, element in enumerate(raw_scenes, start=1):
        if not isinstance(element, Mapping):
            return _refuse(
                f"scenes[{ordinal}] is not a mapping (the scene draft's"
                " own shape)"
            )
        reason = _scene_refusal(element, ordinal, namespace)
        if reason is not None:
            return _refuse(reason)
        scenes.append(dict(element))
    return Ok(
        ChapterBlueprint(
            goal=payload["goal"],
            dramatic_question=payload["dramatic_question"],
            planned_start_tick=payload["planned_start_tick"],
            planned_end_tick=payload["planned_end_tick"],
            closing_pressure=payload["closing_pressure"],
            desired_development=payload["desired_development"],
            soft_outcomes=payload["soft_outcomes"],
            chapter_questions_to_advance=payload[
                "chapter_questions_to_advance"
            ],
            scenes=tuple(scenes),
        )
    )


# ---------------------------------------------------------------------------
# the durable cast-input assembly (the V3-3R item-5 recipe)
# ---------------------------------------------------------------------------


def _card_names(conn: sqlite3.Connection, world_id: str) -> dict[str, str]:
    """One world's actor ids mapped to their card names — the web face's
    ``_world_actor_names`` join, read-side only (``world_actor`` →
    ``character_card.name``); a card the table does not name (or names
    emptily) falls back to the actor id, a plain signature.

    The read is parameter-bound and names no package face: a world
    assembled without a package still answers every name (the seed
    source is not the runtime authority)."""

    rows = conn.execute(
        "SELECT a.actor_id, c.name FROM world_actor a"
        " LEFT JOIN character_card c ON c.persona_id = a.persona_id"
        " WHERE a.world_id = ? ORDER BY a.actor_id ASC",
        (world_id,),
    ).fetchall()
    names: dict[str, str] = {}
    for row in rows:
        actor_id = str(row[0])
        names[actor_id] = str(row[1]) if row[1] not in (None, "") else actor_id
    return names


def build_cast_input(
    conn: sqlite3.Connection,
    world_id: str,
    *,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
) -> DirectorCastInput:
    """Assemble the Director's cast input from durable instance data
    alone (the V3-3R external review's item 5, the cast module's recipe
    docstring being the contract):

    - the actor ids — :meth:`elc.world.store.SqliteWorldStore.actors_of`'s
      records' ``actor_id`` halves (the V3-3R canonical identity; never
      the persona half);
    - the display names — the ``world_actor → character_card.name``
      join (:func:`_card_names`), falling back to the actor id;
    - the profiles — :meth:`elc.world.cast.SqliteCastStore.actor_profiles_of`
      (a ``None`` profile is the honest undeclared);
    - the reader's character — :meth:`elc.world.cast.SqliteCastStore.player_character`,
      narrowed to the profile face (:class:`DirectorPlayerCharacter`:
      the seed fields do not ride — the V3-3R freeze);
    - the vocabulary — :func:`elc.world.cast.participant_namespace` over
      exactly those two sources, never stored.

    The Package is not consulted (no import, no table): a user-created
    world without a package assembles its cast input all the same.
    """

    actors = world_store.actors_of(world_id)
    profiles = {
        profile.actor_id: profile
        for profile in cast_store.actor_profiles_of(world_id)
    }
    names = _card_names(conn, world_id)
    members = tuple(
        DirectorCastMember(
            actor_id=str(actor.actor_id),
            name=names.get(str(actor.actor_id), str(actor.actor_id)),
            profile=profiles.get(str(actor.actor_id)),
        )
        for actor in actors
    )
    player_row = cast_store.player_character(world_id)
    player = (
        None
        if player_row is None
        else DirectorPlayerCharacter(
            player_character_id=player_row.player_character_id,
            name=player_row.name,
            background=player_row.background,
        )
    )
    namespace = participant_namespace(
        actor_ids=[member.actor_id for member in members],
        player_character_id=(
            None if player_row is None else player_row.player_character_id
        ),
    )
    return DirectorCastInput(
        members=members, player_character=player, namespace=namespace
    )


def build_director_context(
    conn: sqlite3.Connection,
    world_id: str,
    *,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
) -> DirectorContext:
    """The Director's context read face: the Bible revision, the cast
    input, the world's active storylines and its CURRENT facts — the
    arms the contract names (Chapter Summaries / Reader Exposure are
    later cuts' arms and are not invented here)."""

    return DirectorContext(
        world_id=world_id,
        bible=bible_store.current_bible(world_id),
        cast=build_cast_input(
            conn, world_id, world_store=world_store, cast_store=cast_store
        ),
        storylines=world_store.active_storylines(world_id),
        current_facts=world_store.current_facts(world_id),
    )


# ---------------------------------------------------------------------------
# the Director (the two write faces; Plan-face only)
# ---------------------------------------------------------------------------


class Director:
    """The World Director over one database — the V3-4 face: validate a
    Blueprint, read the context, and land a Blueprint as a chapter's
    adopted plan revision plus its scene anchors.

    Construction mirrors the composition root: the caller hands the
    same connection's stores (and the connection itself — the cast-name
    join reads through it). ``Director`` writes nothing of its own:
    every write is a store face call, and every refusal (its own or the
    store's) rides out as a value-semantics ``Err``.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        world_store: SqliteWorldStore,
        cast_store: SqliteCastStore,
        bible_store: SqliteBibleStore,
        narrative_store: SqliteNarrativeStore,
    ) -> None:
        self._conn = conn
        self._worlds = world_store
        self._cast = cast_store
        self._bible = bible_store
        self._narrative = narrative_store

    # -- read / validate faces ------------------------------------------------

    def context(self, world_id: str) -> DirectorContext:
        """The Director's context read (the module-level face, bound)."""

        return build_director_context(
            self._conn,
            world_id,
            world_store=self._worlds,
            cast_store=self._cast,
            bible_store=self._bible,
        )

    def validate_blueprint(
        self, world_id: str, payload: Mapping[str, Any]
    ) -> Result[ChapterBlueprint]:
        """The schema face bound to a world: the namespace derives from
        the world's durable cast input (:func:`build_cast_input`), so
        the identity check judges against the live instance — never a
        package declaration."""

        cast = build_cast_input(
            self._conn, world_id, world_store=self._worlds, cast_store=self._cast
        )
        return validate_blueprint(payload, namespace=cast.namespace)

    # -- write faces ----------------------------------------------------------

    def open_next_chapter(
        self,
        world_id: str,
        blueprint_payload: Mapping[str, Any],
        now: str,
    ) -> Result[ChapterOpening]:
        """Plan the world's next chapter — a Plan-face act only.

        The chapter index is the world's existing maximum plus one (the
        first chapter is 1; §21's monotone ``+1``); the chapter id, the
        plan id (revision 1) and every scene anchor id derive from the
        L3 laws. The sequence, each step one store short transaction:
        create the chapter (``PLANNED``), create plan revision 1, adopt
        it (``ADOPTED`` — the #4 prerequisite the lifecycle face will
        check), then reconcile the ``scenes[]`` table into ``PLANNED``
        anchors (``scene_index`` = array ordinal 1..N).

        **The chapter is not opened** (``ACTIVE`` is the lifecycle
        face's move, with its prerequisites) and **no tick moves** (the
        Director has no write path to ``world.current_tick``; #3 /
        N-INV-007). ``now`` is the caller's stamp for every row.

        Refusals: the world does not exist — ``NOT_FOUND``; the payload
        fails the schema — ``VALIDATION_FAILED`` (nothing is written);
        any store refusal rides out unchanged.
        """

        if self._worlds.get_world(world_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"chapter not planned for world {world_id!r}: the"
                        " world does not exist"
                    ),
                )
            )
        validated = self.validate_blueprint(world_id, blueprint_payload)
        if isinstance(validated, Err):
            return Err(validated.error)
        blueprint = validated.value
        chapters = self._narrative.chapters_of(world_id)
        chapter_index = chapters[-1].chapter_index + 1 if chapters else 1
        chapter_id = chapter_id_for(world_id, chapter_index)
        created_chapter = self._narrative.create_chapter(
            chapter_id, world_id, chapter_index, now
        )
        if isinstance(created_chapter, Err):
            return Err(created_chapter.error)
        created_plan = self._create_and_adopt_plan(
            chapter_id, 1, blueprint, now
        )
        if isinstance(created_plan, Err):
            return Err(created_plan.error)
        reconciled = self._reconcile_scenes(
            chapter_id, len(blueprint.scenes), now
        )
        if isinstance(reconciled, Err):
            return Err(reconciled.error)
        return Ok(
            ChapterOpening(
                chapter=created_chapter.value,
                plan=created_plan.value,
                scenes=reconciled.value,
            )
        )

    def revise_blueprint(
        self,
        chapter_id: str,
        blueprint_payload: Mapping[str, Any],
        now: str,
    ) -> Result[ChapterOpening]:
        """Replan a chapter's remaining part — a new plan revision, and
        the ``scenes[]`` table reconciled against the existing anchors
        (the L3 Diff rules, position-keyed).

        The new revision is the chapter's existing maximum plus one; it
        is created and adopted in the same posture as
        :meth:`open_next_chapter` (adoption supersedes the old revision
        in one store transaction — the Plan face is append-only, the
        old revision stays as history). Then, by array position against
        ``world_scene.scene_index``:

        - a position with no anchor row gets a new ``PLANNED`` row;
        - a vanished position's row is discarded **only while it is
          still ``PLANNED``** (§22: only a never-opened scene can be
          un-planned);
        - an ``ACTIVE`` / ``COMMITTED`` / ``CLOSED`` row is **never
          touched** (N-INV-003 — a replanning has no write power over
          what the world has touched);
        - a surviving position's row is not touched even when the
          element's content changed (the row is a progress anchor; the
          JSON of the newest adopted revision is the content source);
        - a ``scene_index`` is never re-used (a retired index stays
          retired — the anchor rows are history too).

        The chapter's status **is** consulted for the two terminal-ish
        words (the V3-4 review's F3): a ``SETTLING`` or ``CLOSED``
        chapter has no 「剩余部分」 left to replan (§21 「CLOSED 不可
        reopen；修正走后续章」 / §24 「只重规划剩余部分」), so revising
        one is refused ``VALIDATION_FAILED`` before anything is
        written. A ``PLANNED`` or ``ACTIVE`` chapter's plan is open to
        revision, and §24's own law (「对已 COMMITTED 场无写权」) is
        enforced by the rules above, not by refusing the revision.

        Refusals: the chapter does not exist — ``NOT_FOUND``; the
        chapter is ``SETTLING`` / ``CLOSED`` — ``VALIDATION_FAILED``
        (nothing is written); the payload fails the schema —
        ``VALIDATION_FAILED``; any store refusal rides out unchanged.
        """

        chapter = self._narrative.get_chapter(chapter_id)
        if chapter is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"chapter {chapter_id!r} not revised: it does not"
                        " exist"
                    ),
                )
            )
        if chapter.status in (ChapterStatus.SETTLING, ChapterStatus.CLOSED):
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter {chapter_id!r} not revised: it is"
                        f" {chapter.status.value!r} — a settled chapter"
                        " has no remaining part to replan (§21/§24:"
                        " corrections go through the next chapter)"
                    ),
                )
            )
        validated = self.validate_blueprint(
            chapter.world_id, blueprint_payload
        )
        if isinstance(validated, Err):
            return Err(validated.error)
        blueprint = validated.value
        plans = self._narrative.plans_of(chapter_id)
        plan_revision = plans[-1].plan_revision + 1 if plans else 1
        created_plan = self._create_and_adopt_plan(
            chapter_id, plan_revision, blueprint, now
        )
        if isinstance(created_plan, Err):
            return Err(created_plan.error)
        reconciled = self._reconcile_scenes(
            chapter_id, len(blueprint.scenes), now
        )
        if isinstance(reconciled, Err):
            return Err(reconciled.error)
        return Ok(
            ChapterOpening(
                chapter=chapter,
                plan=created_plan.value,
                scenes=reconciled.value,
            )
        )

    # -- shared write machinery ------------------------------------------------

    def _create_and_adopt_plan(
        self,
        chapter_id: str,
        plan_revision: int,
        blueprint: ChapterBlueprint,
        now: str,
    ) -> Result[WorldChapterPlanRecord]:
        """Create one plan revision from a validated Blueprint and adopt
        it (the two store short transactions; every field verbatim, the
        scenes under the store's own deterministic codec)."""

        created = self._narrative.create_plan(
            plan_id_for(chapter_id, plan_revision),
            chapter_id,
            plan_revision,
            goal=blueprint.goal,
            dramatic_question=blueprint.dramatic_question,
            planned_start_tick=blueprint.planned_start_tick,
            planned_end_tick=blueprint.planned_end_tick,
            closing_pressure=blueprint.closing_pressure,
            desired_development=blueprint.desired_development,
            soft_outcomes=blueprint.soft_outcomes,
            chapter_questions_to_advance=blueprint.chapter_questions_to_advance,
            scenes=blueprint.scenes,
            now=now,
        )
        if isinstance(created, Err):
            return Err(created.error)
        adopted = self._narrative.adopt_plan(
            created.value.chapter_plan_id,
            now,
            expected_state_version=created.value.state_version,
        )
        if isinstance(adopted, Err):
            return Err(adopted.error)
        return Ok(adopted.value)

    def _reconcile_scenes(
        self, chapter_id: str, scene_count: int, now: str
    ) -> Result[tuple[WorldSceneRecord, ...]]:
        """The L3 reconciliation, position-keyed (see
        :meth:`revise_blueprint` for the rules): create the missing
        positions (array ordinals ``1..scene_count`` with no anchor
        row), discard the vanished positions' still-``PLANNED`` rows
        (``scene_index > scene_count``), touch nothing else, and answer
        the chapter's rows in ``scene_index`` order.

        Creation at an ordinal is guarded by the existing rows'
        identity — a row already occupies every created index, so a
        ``scene_index`` is never minted twice (the table's UNIQUE backs
        the same law at the storage level)."""

        existing = self._narrative.scenes_of(chapter_id)
        occupied = {row.scene_index for row in existing}
        for scene_index in range(1, scene_count + 1):
            if scene_index in occupied:
                continue
            created = self._narrative.create_scene(
                scene_id_for(chapter_id, scene_index),
                chapter_id,
                scene_index,
                now,
            )
            if isinstance(created, Err):
                return Err(created.error)
        for row in existing:
            if row.scene_index <= scene_count:
                continue
            if row.status is not SceneStatus.PLANNED:
                continue  # ACTIVE / COMMITTED / CLOSED / DISCARDED: history
            discarded = self._narrative.discard_scene(
                row.scene_id, now, expected_state_version=row.state_version
            )
            if isinstance(discarded, Err):
                return Err(discarded.error)
        return Ok(self._narrative.scenes_of(chapter_id))
