"""The World Director's V3-4 machine face (TASK-OPI-be7b094f…11 /
DEC-OPI-be7b094f…7; the V3-4R correction, TASK-OPI-be7b094f…23 /
DEC-OPI-be7b094f…21) — the schema-and-table side of the cut: the strict
Blueprint schema, the durable cast-input assembly, the context read
face, and the two write faces that land a Blueprint as an adopted plan
revision and reconcile its ``scenes[]`` against ``world_scene``
(:meth:`Director.open_next_chapter` / :meth:`Director.revise_blueprint`).

**Scope (the ruling's own words — schema-and-table-side-only)**: the
LLM driven Blueprint *production* face (prompt / provider / strict
parse) is not here; it is registered as its own later cut (a V3-8 Gold
Scenario dependency). What ships here is what the contract spells:

- **The strict Blueprint schema** (DATA §26.2.1's V3-4 block — the L3
  landing, revised by the V3-4R review; :func:`validate_blueprint`):
  the nine chapter fields verbatim, the ``scenes[]`` canonical key set
  (:data:`BLUEPRINT_SCENE_KEYS` — ``purpose`` / ``place`` /
  ``pov_actor_id`` / ``participants`` / ``planned_start_tick`` /
  ``entry_goals`` / ``exit_condition`` / ``elasticity`` /
  ``revealable`` / ``must_hide``; a missing key or a wrong type is
  refused), the canonical identity law (AI side =
  ``world_actor.actor_id``, user side =
  ``world_player_character.player_character_id``; a ``persona_id`` or
  a resident name is not a V3 participant — the V3-3R freeze), and the
  Director's own supplemental keys (beats / gate hints, whatever the
  Director grows) passing through unjudged. **The V3-4R tightening**:
  ``scenes`` is non-empty; the chapter's window never runs backwards
  (``planned_start_tick <= planned_end_tick``); a scene's
  ``planned_start_tick`` is non-negative and never starts beyond the
  chapter's ``planned_end_tick``; ``pov_actor_id`` must be among the
  element's ``participants`` (a POV is present in her own scene). The
  schema is deliberately still not a plot plausibility checker.

- **POV eligibility is authority, not decoration** (the V3-4R review's
  item 3): a ``pov_actor_id`` naming an AI actor demands that actor's
  ``world_actor_profile.pov_eligible`` to be ``True`` — an explicit
  ``False`` is refused, and an undeclared eligibility (``None``, or
  no profile row at all) is **not automatically authorized** (the MVP
  refuses; the message says so). The ``player_character_id`` is
  allowed as a POV outright — the reader is the protagonist of her
  own story.

- **The wording law's schema half** (the design doc §2.2 / §三 1.5):
  **the soft-expectation set is never a postcondition** —
  ``closing_pressure`` says *where the chapter presses*, never *where
  it must arrive*; hard conditions may only be world rules / happened
  causality / irrevocable facts. The machine half of the law here is
  the non-empty-string check on the four soft fields plus this
  docstring's pin; there is deliberately **no postcondition detector**
  — a manufactured one would be exactly the rail-switch the law
  forbids (the Director is not the railway's dispatcher).

- **Scene identity is durable and separate from presentation order**
  (the V3-4R review's item 1, the HIGH): the ``scenes[]`` array states
  the presentation / plan order and carries no identity of its own.
  An element may carry the optional stable identity ``scene_ref`` (an
  integer pointing at a ``world_scene`` anchor's ``scene_index`` **of
  the same chapter**); an element without one matches the anchor at
  its own array ordinal. ``DISCARDED`` anchors are retired forever —
  never revived, never re-minted, never referenced. **Identity
  stamping**: when the Director mints an anchor for an element, it
  burns the derived ``scene_id`` into that element of the plan row's
  ``scenes`` JSON (the one added key, injected before the revision row
  lands; every other byte rides untouched). Later revisions never
  rewrite a burned identity, and a burned ``scene_id`` resubmitted
  next to a disagreeing ``scene_ref`` is refused. Elements minted
  fresh (no ref, no live anchor at their ordinal, no burned id) take
  an **unused monotonic** ``scene_index`` (``max(existing) + 1``): no
  ghost or placeholder scene rows exist.

- **The durable cast-input assembly** (:func:`build_cast_input`; the
  V3-3R external review's item 5, thickened by the V3-4R review's item
  3): ``world_actor`` (the actor ids) + ``character_card`` (the live
  ``web._world_actor_names`` join, ``world_actor → character_card``,
  read wider: ``name`` plus the six person fields ``identity`` /
  ``personality`` / ``background`` / ``speech_style`` / ``values`` /
  ``boundaries``; a card the table does not name falls back to the
  actor id for the name and to empty strings for the six — the honest
  undeclared) + ``world_actor_profile`` + ``world_player_character``,
  unified through :func:`elc.world.cast.participant_namespace`. **The
  Package is a seed source, never the runtime authority** — nothing
  here reads it (no import, no table; pinned by a source scan). The
  player's ``location`` / ``state`` / ``knowledge_refs`` are the
  creation-time seed (the V3-3R freeze) and deliberately do not exist
  on :class:`DirectorPlayerCharacter` — their current authority is
  ``world_state_fact`` / V3-7's actor memory.

- **The Director's context read face** (:func:`build_director_context`):
  the current Bible revision, the cast input, the world's
  ``active_storylines`` (migration 0028, live), its ``current_facts``
  (the ``world_state_fact`` CURRENT half, migration 0024) and the
  **canonical story time** (``current_tick``, read through
  :func:`elc.world.time.read_current_tick`). The tick arm is the V3-4R
  review's item 2: a Director producing planned ticks must know the
  canonical time — initial chapter planning takes ``current_tick`` as
  its reality anchor, a replanning may keep the historical planned
  time of what already happened, and fresh planning must not
  unconsciously regress the canonical time. This cut only places the
  canonical time in front of the Director — it rewrites no payload.
  Chapter Summaries and Reader Exposure do not exist yet: they are
  V3-7's / V3-5's arms, registered here as such.

- **World authority is fail-closed** (the V3-4R review's item 2): a
  world holding no ``CURRENT`` ``world_bible_revision`` is refused
  ``NOT_FOUND`` by both write faces **before anything is written** —
  without world authority there is no Director (DATA §26.2.1's
  fail-closed block).

- **The two write faces — Plan-face only** (the Plan≠Canon pin):
  :meth:`Director.open_next_chapter` mints the next chapter
  (``PLANNED`` — it never opens a chapter; the ``ACTIVE`` flip is the
  lifecycle face's), creates and adopts plan revision 1, and mints one
  ``PLANNED`` ``world_scene`` anchor per freshly-resolved element.
  :meth:`Director.revise_blueprint` appends the next plan revision and
  reconciles by **identity** (the L3 rules, V3-4R): a ``scene_ref``
  (or a burned ``scene_id``) names its anchor, whose row is not
  touched even when the element's content changed (the row is a
  progress anchor, the JSON is the content source); a positional
  element matches its ordinal's live anchor; a fresh element mints
  the unused monotonic index; an anchor no element claims and that is
  still ``PLANNED`` is discarded; an ``ACTIVE`` / ``COMMITTED`` /
  ``CLOSED`` row is never touched (N-INV-003 — a replanning has no
  write power over what happened); a ``scene_index`` is never re-used.
  **The Director never advances ``world.current_tick``** (#3 /
  N-INV-007 — the commit transactions are the only movers) and writes
  **no canon progress word at all**: what it lands is a plan revision
  plus identity anchors (the Plan≠Canon boundary of the L3 block).

**Crash / replay closure (landed in V3-5 — the V3-4R review's item 4,
DEC-OPI-be7b094f…32)**: both write faces are retry-safe against the two
residue shapes the V3-4 review's F1 left open, so a retry never
silently lands a new chapter or a new revision:

- :meth:`Director.open_next_chapter` **reuses** a dangling chapter —
  the world's ``PLANNED`` chapter holding no plan revision at all
  (a crashed open before its Blueprint landed; the smallest
  ``chapter_index`` wins when several exist) — instead of deriving the
  next index and moving on;
- :meth:`Director.revise_blueprint` **reuses** the chapter's dangling
  ``PROPOSED`` latest revision: a payload whose shape matches the
  residue adopts it and continues; a payload that differs rejects the
  residue and mints the next revision (the same shape law the creation
  face spells — plans are append-only, so a same-id replay with the
  same shape is a no-op and a different shape is a ``CONFLICT``, and
  the residue is resolved before either can happen).

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
posture): **value semantics** — every write-face refusal is a
``Result`` ``Err``, never an exception (``VALIDATION_FAILED`` for the
caller's own payload, ``NOT_FOUND`` for a dangling world / chapter, and
any store refusal riding out unchanged; the context read face is not a
``Result`` face and raises on its one out-of-contract input — its own
docstring says so); **no hidden clock** (every row's stamps ride the
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
from collections.abc import Iterable, Mapping
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
    PlanRevisionStatus,
    SceneStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneRecord,
    encode_scenes,
)
from elc.world.store import SqliteWorldStore, WorldStorylineRecord
from elc.world.time import read_current_tick
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
    durable instance data alone (the V3-3R item-5 recipe, thickened by
    the V3-4R review's item 3).

    ``actor_id`` is the canonical V3 participant identity (not the
    persona id); ``name`` is the card's display name with the fallback
    law (a card the table does not name, or names emptily, falls back
    to the actor id — a plain signature, never a broken one). The six
    person fields — ``identity`` / ``personality`` / ``background`` /
    ``speech_style`` / ``values`` / ``boundaries`` — ride from the
    ``character_card`` row (who she *is*); a card the join cannot name
    leaves all six the empty string — the honest undeclared, never a
    guessed value, and never a reason to drop the member.
    ``profile`` is the ``world_actor_profile`` row, or ``None`` for an
    actor the world never seeded a profile for (the honest undeclared);
    the profile still answers *who she is in this world* — the six card
    fields never replace it.
    """

    actor_id: str
    name: str
    identity: str
    personality: str
    background: str
    speech_style: str
    values: str
    boundaries: str
    profile: ActorProfileRecord | None


@dataclass(frozen=True)
class DirectorPlayerCharacter:
    """The reader's own durable character as the Director sees her — the
    profile face: her id, name, background, appearance, abilities and
    limits (``name`` / ``background`` / ``appearance`` / ``abilities``
    / ``limits`` are the character's 档案, DATA §26.2.1's freeze block;
    a field the writer declared nothing for rides the empty string).

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
    appearance: str
    abilities: str
    limits: str


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
    """What the Director's planning reads today.

    The arms are the ones the contract names: the Bible revision (the
    instance-level world authority), the cast input, the world's
    ``active_storylines`` (0028's two-layer read), the
    ``world_state_fact`` CURRENT half (0024) and ``current_tick`` —
    the canonical story time (the V3-4R review's item 2,
    :func:`elc.world.time.read_current_tick`). A Director producing
    planned ticks must know the canonical time: initial chapter
    planning takes ``current_tick`` as its reality anchor; a
    replanning may keep the historical planned time of what already
    happened, and fresh planning must not unconsciously regress the
    canonical time. Chapter Summaries and Reader Exposure are **not**
    arms yet — they are V3-7's / V3-5's (registered; a later cut grows
    this shape, not a placeholder now).
    """

    world_id: str
    bible: BibleRevision | None
    cast: DirectorCastInput
    storylines: tuple[WorldStorylineRecord, ...]
    current_facts: tuple[WorldStateFact, ...]
    current_tick: int


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
    ``f"{chapter_id}-s{scene_index:02d}"`` — the durable anchor
    index's own name (since V3-4R the index is the unused-monotonic
    anchor identity, not necessarily the array ordinal)."""

    return f"{chapter_id}-s{scene_index:02d}"


# ---------------------------------------------------------------------------
# the scene-identity resolution (the V3-4R spine; DATA §26.2.1's L3 block)
# ---------------------------------------------------------------------------


def _refuse(reason: str) -> Err[Any]:
    """One refusal as a human sentence (the
    :func:`~elc.world.narrative.types.decode_scenes` message shape) —
    the shared spelling of the schema's and the resolution's
    value-semantics refusals."""

    return Err(
        DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=f"Blueprint refused: {reason}",
        )
    )


def _next_unused_scene_index(existing_indexes: Iterable[int]) -> int:
    """The fresh anchor's ``scene_index`` — ``max(existing) + 1`` (the
    V3-4R unused-monotonic law; an empty chapter mints 1).

    The one minting authority: a fresh element never takes its array
    ordinal, never re-uses a retired ``scene_index`` and never fills a
    gap — indexes grow monotonically and the retired stay retired
    (DATA §26.2.1's L3 diff rules; the source scan pins that no
    positional ``range`` minting survives in this module).
    """

    return max(existing_indexes, default=0) + 1


def _scene_id_index(scene_id: str) -> int | None:
    """The ``scene_index`` a derived ``scene_id`` spells, or ``None``
    when the string carries no ``-s<digits>`` tail (the derivation
    law's own spelling, ``f"{chapter_id}-s{index:02d}"``)."""

    head, _, digits = scene_id.rpartition("-s")
    if not head or not digits.isdigit():
        return None
    return int(digits)


def _element_identity(scene: Mapping[str, Any]) -> int | None:
    """The anchor identity one ``scenes[]`` element declares, or
    ``None`` — the explicit ``scene_ref`` first, then the burned
    ``scene_id``'s own index (the read-back form: a stamped element
    resolves by its burned identity when no ``scene_ref`` rides with
    it). Both keys have passed the schema's own type / agreement
    checks before this face runs."""

    if "scene_ref" in scene:
        return int(scene["scene_ref"])
    scene_id = scene.get("scene_id")
    if isinstance(scene_id, str):
        return _scene_id_index(scene_id)
    return None


@dataclass(frozen=True)
class _SceneTarget:
    """One element's resolution: the anchor it speaks for and the
    element as it lands in the plan row's ``scenes`` JSON.

    ``is_new`` marks a freshly minted anchor — its element carries the
    burned ``scene_id`` key; an existing anchor's element rides as
    given (a burned identity is never rewritten on arrival).
    """

    ordinal: int
    scene_index: int
    scene_id: str
    is_new: bool
    element: dict[str, Any]


def _resolve_scene_targets(
    chapter_id: str,
    scenes: tuple[dict[str, Any], ...],
    anchors: tuple[WorldSceneRecord, ...],
) -> Result[tuple[_SceneTarget, ...]]:
    """Resolve every ``scenes[]`` element to the anchor it speaks for —
    the identity resolution both write faces run **before any write**
    (DATA §26.2.1's L3 block, V3-4R).

    An element's identity is its ``scene_ref``, or its burned
    ``scene_id``, or the live anchor at its own array ordinal; a fresh
    element (no ref, no live anchor at its ordinal, no burned id) mints
    :func:`_next_unused_scene_index`. Refused, every one a
    value-semantics sentence naming the element's ordinal:

    - a reference (``scene_ref`` / ``scene_id``) naming no anchor of
      **this chapter** — another chapter's ``scene_index`` is no
      identity here;
    - a reference naming a ``DISCARDED`` anchor — retired anchors are
      never revived, never re-minted, never referenced;
    - a reference whose array ordinal is already occupied by another
      anchor (``scene_index != scene_ref`` at that ordinal) — the
      explicit identity and the positional one would disagree;
    - two elements claiming one anchor identity.

    The burned identity is cross-checked in full: an element carrying
    both a ``scene_ref`` and a ``scene_id`` whose strings disagree is
    refused (the schema's tail comparison is the payload-local half,
    this is the anchored half).
    """

    by_index = {row.scene_index: row for row in anchors}
    by_id = {row.scene_id: row for row in anchors}
    claimed: dict[int, int] = {}
    next_index = _next_unused_scene_index(by_index)
    targets: list[_SceneTarget] = []
    for ordinal, element in enumerate(scenes, start=1):
        ref = element.get("scene_ref")
        scene_id = element.get("scene_id")
        if ref is None and isinstance(scene_id, str):
            named = by_id.get(scene_id)
            if named is None:
                return _refuse(
                    f"scenes[{ordinal}].scene_id {scene_id!r} names no"
                    f" anchor of chapter {chapter_id!r} — a burned"
                    " identity is addressable only in its own chapter"
                )
            if named.status is SceneStatus.DISCARDED:
                return _refuse(
                    f"scenes[{ordinal}].scene_id {scene_id!r} names a"
                    f" DISCARDED anchor of chapter {chapter_id!r} — a"
                    " retired anchor is never revived, never re-minted"
                    " and never referenced"
                )
            ref = named.scene_index
        if ref is not None:
            anchor = by_index.get(int(ref))
            if anchor is None:
                return _refuse(
                    f"scenes[{ordinal}].scene_ref {ref!r} names no anchor"
                    f" of chapter {chapter_id!r} — only this chapter's"
                    " anchors are addressable (another chapter's"
                    " scene_index is no identity here)"
                )
            if anchor.status is SceneStatus.DISCARDED:
                return _refuse(
                    f"scenes[{ordinal}].scene_ref {ref!r} names a"
                    f" DISCARDED anchor of chapter {chapter_id!r} — a"
                    " retired anchor is never revived, never re-minted"
                    " and never referenced"
                )
            if isinstance(scene_id, str) and scene_id != anchor.scene_id:
                return _refuse(
                    f"scenes[{ordinal}].scene_id {scene_id!r} disagrees"
                    " with the anchor its scene_ref"
                    f" {ref!r} names ({anchor.scene_id!r}) — the burned"
                    " identity and its reference must agree"
                )
            position = by_index.get(ordinal)
            if position is not None and position.scene_index != int(ref):
                return _refuse(
                    f"scenes[{ordinal}].scene_ref {ref!r} conflicts with"
                    " the anchor already at this array position"
                    f" (scene_index {ordinal}) — an element carrying a"
                    " scene_ref must sit at its own position or at a"
                    " position no anchor occupies"
                )
            if anchor.scene_index in claimed:
                return _refuse(
                    f"scenes[{ordinal}] claims scene_ref"
                    f" {anchor.scene_index} already claimed by"
                    f" scenes[{claimed[anchor.scene_index]}] — one"
                    " anchor identity per element"
                )
            claimed[anchor.scene_index] = ordinal
            targets.append(
                _SceneTarget(
                    ordinal=ordinal,
                    scene_index=anchor.scene_index,
                    scene_id=anchor.scene_id,
                    is_new=False,
                    element=dict(element),
                )
            )
            continue
        position = by_index.get(ordinal)
        if position is not None and position.status is not SceneStatus.DISCARDED:
            if position.scene_index in claimed:
                return _refuse(
                    f"scenes[{ordinal}] matches scene_index"
                    f" {position.scene_index} already claimed by"
                    f" scenes[{claimed[position.scene_index]}] — one"
                    " anchor identity per element"
                )
            claimed[position.scene_index] = ordinal
            targets.append(
                _SceneTarget(
                    ordinal=ordinal,
                    scene_index=position.scene_index,
                    scene_id=position.scene_id,
                    is_new=False,
                    element=dict(element),
                )
            )
            continue
        fresh_id = scene_id_for(chapter_id, next_index)
        stamped = dict(element)
        stamped["scene_id"] = fresh_id
        targets.append(
            _SceneTarget(
                ordinal=ordinal,
                scene_index=next_index,
                scene_id=fresh_id,
                is_new=True,
                element=stamped,
            )
        )
        claimed[next_index] = ordinal
        next_index += 1
    return Ok(tuple(targets))


# ---------------------------------------------------------------------------
# the strict Blueprint schema (the L3 landing; value semantics only)
# ---------------------------------------------------------------------------


def _plan_shape_matches(
    plan: WorldChapterPlanRecord,
    blueprint: ChapterBlueprint,
    targets: tuple[_SceneTarget, ...],
) -> bool:
    """Whether one existing plan row's shape equals what this validated
    Blueprint and its resolved targets would write — the residue-reuse
    law's comparison (the same shape law the store's idempotent creation
    spells: the same id with the same shape is a no-op, a different
    shape is a ``CONFLICT``).

    The compared fields are the ones :meth:`Director._create_and_adopt_plan`
    writes: the eight chapter fields verbatim and the scenes table as
    the resolution's own elements (fresh elements already carrying their
    burned ``scene_id``), under the store's deterministic codec.
    """

    return (
        plan.goal,
        plan.dramatic_question,
        plan.planned_start_tick,
        plan.planned_end_tick,
        plan.closing_pressure,
        plan.desired_development,
        plan.soft_outcomes,
        plan.chapter_questions_to_advance,
        encode_scenes(plan.scenes),
    ) == (
        blueprint.goal,
        blueprint.dramatic_question,
        blueprint.planned_start_tick,
        blueprint.planned_end_tick,
        blueprint.closing_pressure,
        blueprint.desired_development,
        blueprint.soft_outcomes,
        blueprint.chapter_questions_to_advance,
        encode_scenes(tuple(target.element for target in targets)),
    )


def _scene_refusal(
    scene: Mapping[str, Any],
    ordinal: int,
    *,
    chapter_end_tick: int,
    namespace: frozenset[str],
    player_character_id: str | None,
    pov_eligibility: Mapping[str, bool | None],
) -> str | None:
    """The canonical key set's own refusals for one ``scenes[]`` element
    (DATA §26.2.1's L3 block, key by key; the V3-4R tightening
    included) — the reason sentence, or ``None`` when the element
    passes.

    ``ordinal`` is the array position (1-based) — the blueprint's own
    word for the position the reconciliation keys on, so a refusal
    names the same coordinate the diff will use. The identity pair
    (``scene_ref`` / ``scene_id``) is checked here for type and mutual
    agreement; whether the reference *exists* is the resolution's
    question (:func:`_resolve_scene_targets` — this face knows no
    chapter). POV eligibility is the V3-4R review's item 3: the
    namespace says who is a durable participant, ``player_character_id``
    / ``pov_eligibility`` say who may carry a POV — an AI actor with an
    explicit ``False`` or an undeclared (``None`` / no profile at all)
    eligibility is refused, and the POV must be among the element's
    ``participants``. Supplemental keys are the Director's own:
    unjudged in meaning, but the element must still be JSON-encodable
    (the plan row's ``scenes`` column is JSON — a value the column
    cannot carry is refused here, in the caller's own vocabulary,
    rather than exploding out of the store's encoder).
    """

    ref: int | None = None
    if "scene_ref" in scene:
        candidate = scene["scene_ref"]
        if isinstance(candidate, bool) or not isinstance(candidate, int):
            return (
                f"scenes[{ordinal}].scene_ref must be an integer"
                " scene_index of this chapter's anchors; got"
                f" {candidate!r}"
            )
        ref = candidate
    scene_id = scene.get("scene_id")
    if "scene_id" in scene and not isinstance(scene_id, str):
        return (
            f"scenes[{ordinal}].scene_id must be a string (the derived"
            f" anchor identity); got {type(scene_id).__name__}"
        )
    if ref is not None and isinstance(scene_id, str):
        if _scene_id_index(scene_id) != ref:
            return (
                f"scenes[{ordinal}].scene_id {scene_id!r} does not"
                f" match scene_ref {ref} — the burned identity and its"
                " reference must agree"
            )
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
    if tick < 0:
        return (
            f"scenes[{ordinal}].planned_start_tick {tick!r} is"
            " negative — a planned tick never precedes the world's own"
            " zero"
        )
    if tick > chapter_end_tick:
        return (
            f"scenes[{ordinal}].planned_start_tick {tick!r} lies"
            f" beyond the chapter's planned_end_tick"
            f" {chapter_end_tick!r} — a scene never starts after the"
            " chapter's window closes"
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
    is_player = player_character_id is not None and pov == player_character_id
    if not is_player:
        eligible = pov_eligibility.get(pov)
        if eligible is False:
            return (
                f"scenes[{ordinal}].pov_actor_id {pov!r} is not"
                " POV-eligible: the actor's world_actor_profile declares"
                " pov_eligible = false"
            )
        if eligible is None:
            return (
                f"scenes[{ordinal}].pov_actor_id {pov!r} carries no"
                " declared POV eligibility"
                " (world_actor_profile.pov_eligible is null, or the"
                " actor holds no profile) — an undeclared eligibility is"
                " not automatically authorized (the MVP refuses)"
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
    if pov not in participants:
        return (
            f"scenes[{ordinal}].pov_actor_id {pov!r} is not among the"
            " element's participants — the POV is present in her own"
            " scene (the schema invariant, V3-4R)"
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
    payload: Mapping[str, Any],
    *,
    namespace: frozenset[str],
    player_character_id: str | None,
    pov_eligibility: Mapping[str, bool | None],
) -> Result[ChapterBlueprint]:
    """The Blueprint's strict schema (DATA §26.2.1's V3-4 block, revised
    by the V3-4R review; the machine face of the wording law's schema
    half).

    Refused, every one as a value-semantics ``VALIDATION_FAILED`` naming
    the offending field (never an exception, never a partial answer):

    - the payload not being a mapping;
    - a missing / mistyped chapter field — the nine §26.2.1 fields are
      all required, the six text fields must be strings, the two ticks
      integers (a bool is not a tick), and the window never runs
      backwards (``planned_start_tick <= planned_end_tick``);
    - an empty / blank soft-expectation field (the four the wording law
      names: ``closing_pressure`` / ``desired_development`` /
      ``soft_outcomes`` / ``chapter_questions_to_advance`` — a
      direction must be stated; the fields are **never** a
      postcondition, and the schema has no detector for one);
    - ``scenes`` not being a non-empty sequence of mappings, or an
      element missing a canonical key (:data:`BLUEPRINT_SCENE_KEYS`) or
      carrying a wrong type (a scene's ``planned_start_tick`` is
      non-negative and never starts beyond the chapter's
      ``planned_end_tick``);
    - an identity outside ``namespace`` — ``pov_actor_id`` and every
      ``participants`` word must be a durable V3 participant (an AI
      actor's ``actor_id`` or the ``player_character_id``; a
      ``persona_id`` and a resident name are both refused — the V3-3R
      freeze); the POV must be among the element's ``participants``
      and, when it names an AI actor, that actor's
      ``world_actor_profile.pov_eligible`` must be ``True`` (an
      explicit ``False`` and an undeclared eligibility are both
      refused — ``pov_eligibility`` / ``player_character_id`` carry
      the authority, the V3-4R review's item 3);
    - an identity pair declared twice — two elements carrying the same
      ``scene_ref`` (or the same burned ``scene_id`` index), and a
      ``scene_id`` disagreeing with its ``scene_ref``;
    - an element that is not JSON-encodable.

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
    if payload["planned_start_tick"] > payload["planned_end_tick"]:
        return _refuse(
            "the chapter's planned_start_tick"
            f" {payload['planned_start_tick']!r} runs past its"
            f" planned_end_tick {payload['planned_end_tick']!r} — a"
            " chapter's window never runs backwards"
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
            "the chapter field 'scenes' must be a non-empty sequence of"
            f" scene mappings; got {type(raw_scenes).__name__}"
        )
    if not raw_scenes:
        return _refuse(
            "the chapter field 'scenes' is empty — a chapter plans at"
            " least one scene (the V3-4R non-emptiness law; an empty"
            " plan is not a plan)"
        )
    scenes: list[dict[str, Any]] = []
    claimed: dict[int, int] = {}
    for ordinal, element in enumerate(raw_scenes, start=1):
        if not isinstance(element, Mapping):
            return _refuse(
                f"scenes[{ordinal}] is not a mapping (the scene draft's"
                " own shape)"
            )
        reason = _scene_refusal(
            element,
            ordinal,
            chapter_end_tick=payload["planned_end_tick"],
            namespace=namespace,
            player_character_id=player_character_id,
            pov_eligibility=pov_eligibility,
        )
        if reason is not None:
            return _refuse(reason)
        identity = _element_identity(element)
        if identity is not None:
            if identity in claimed:
                return _refuse(
                    f"scenes[{ordinal}] repeats the anchor identity"
                    f" {identity} claimed by scenes[{claimed[identity]}]"
                    " (scene_ref / scene_id) — one element per scene"
                    " identity"
                )
            claimed[identity] = ordinal
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


@dataclass(frozen=True)
class _CardFace:
    """One actor's card-derived face: the display ``name`` (the
    fallback law already applied) and the six person fields — a card
    the join cannot name leaves the six the empty string, the honest
    undeclared."""

    name: str
    identity: str
    personality: str
    background: str
    speech_style: str
    values: str
    boundaries: str


def _card_faces(
    conn: sqlite3.Connection, world_id: str
) -> dict[str, _CardFace]:
    """One world's actor ids mapped to their card faces — the web
    face's ``_world_actor_names`` join, read wider (``world_actor`` →
    ``character_card``: the ``name`` plus the six person fields the
    V3-4R review's item 3 thickens the cast input with); a card the
    table does not name (or names emptily) falls back to the actor id
    for the name, and a card row the join cannot reach leaves the six
    fields the empty string — a plain signature and an honest
    undeclared, never a broken member.

    The read is parameter-bound and names no package face: a world
    assembled without a package still answers every face (the seed
    source is not the runtime authority)."""

    rows = conn.execute(
        "SELECT a.actor_id, c.name, c.identity, c.personality,"
        " c.background, c.speech_style, c.\"values\", c.boundaries"
        " FROM world_actor a"
        " LEFT JOIN character_card c ON c.persona_id = a.persona_id"
        " WHERE a.world_id = ? ORDER BY a.actor_id ASC",
        (world_id,),
    ).fetchall()
    faces: dict[str, _CardFace] = {}
    for row in rows:
        actor_id = str(row[0])
        faces[actor_id] = _CardFace(
            name=str(row[1]) if row[1] not in (None, "") else actor_id,
            identity="" if row[2] is None else str(row[2]),
            personality="" if row[3] is None else str(row[3]),
            background="" if row[4] is None else str(row[4]),
            speech_style="" if row[5] is None else str(row[5]),
            values="" if row[6] is None else str(row[6]),
            boundaries="" if row[7] is None else str(row[7]),
        )
    return faces


def build_cast_input(
    conn: sqlite3.Connection,
    world_id: str,
    *,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
) -> DirectorCastInput:
    """Assemble the Director's cast input from durable instance data
    alone (the V3-3R external review's item 5, the cast module's recipe
    docstring being the contract; thickened by the V3-4R review's item
    3):

    - the actor ids — :meth:`elc.world.store.SqliteWorldStore.actors_of`'s
      records' ``actor_id`` halves (the V3-3R canonical identity; never
      the persona half);
    - the card faces — the ``world_actor → character_card`` join
      (:func:`_card_faces`): the display name (falling back to the
      actor id) and the six person fields (a card-less row leaving the
      six the empty string — the honest undeclared, the member still
      standing);
    - the profiles — :meth:`elc.world.cast.SqliteCastStore.actor_profiles_of`
      (a ``None`` profile is the honest undeclared);
    - the reader's character — :meth:`elc.world.cast.SqliteCastStore.player_character`,
      narrowed to the profile face (:class:`DirectorPlayerCharacter`:
      ``name`` / ``background`` / ``appearance`` / ``abilities`` /
      ``limits`` ride; the seed fields do not — the V3-3R freeze);
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
    faces = _card_faces(conn, world_id)
    # The join reads FROM world_actor: every actor of the world carries
    # a face (a card-less row rides as the actor id plus six empty
    # strings), so the lookup below cannot miss.
    members_list: list[DirectorCastMember] = []
    for actor in actors:
        actor_id = str(actor.actor_id)
        face = faces[actor_id]
        members_list.append(
            DirectorCastMember(
                actor_id=actor_id,
                name=face.name,
                identity=face.identity,
                personality=face.personality,
                background=face.background,
                speech_style=face.speech_style,
                values=face.values,
                boundaries=face.boundaries,
                profile=profiles.get(actor_id),
            )
        )
    members = tuple(members_list)
    player_row = cast_store.player_character(world_id)
    player = (
        None
        if player_row is None
        else DirectorPlayerCharacter(
            player_character_id=player_row.player_character_id,
            name=player_row.name,
            background=player_row.background,
            appearance=player_row.appearance,
            abilities=player_row.abilities,
            limits=player_row.limits,
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
    input, the world's active storylines, its CURRENT facts and the
    canonical story time (``current_tick``, read through
    :func:`elc.world.time.read_current_tick`) — the arms the contract
    names (Chapter Summaries / Reader Exposure are later cuts' arms and
    are not invented here).

    The face's calling precondition is a **seeded world**: the tick is
    the one arm with no honest empty answer, so a dangling world raises
    ``ValueError`` naming it (there is no canonical time to report for
    a world that does not exist — the same honest corrupted-call
    posture the store's undecodable-row raise keeps; DATA §26.2.1's
    fail-closed block presumes the world's own authority before the
    Director plans)."""

    tick = read_current_tick(conn, world_id)
    if isinstance(tick, Err):
        raise ValueError(
            f"director context of world {world_id!r} not read:"
            f" {tick.error.message}"
        )
    return DirectorContext(
        world_id=world_id,
        bible=bible_store.current_bible(world_id),
        cast=build_cast_input(
            conn, world_id, world_store=world_store, cast_store=cast_store
        ),
        storylines=world_store.active_storylines(world_id),
        current_facts=world_store.current_facts(world_id),
        current_tick=tick.value,
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
        """The schema face bound to a world: the namespace, the
        player-character id and the POV eligibility map all derive
        from the world's durable cast input
        (:func:`build_cast_input`), so the identity and POV checks
        judge against the live instance — never a package
        declaration. The eligibility map carries every actor's
        ``world_actor_profile.pov_eligible`` (``None`` for an actor
        with no profile row — the same honest undeclared the profile
        arm answers)."""

        cast = build_cast_input(
            self._conn, world_id, world_store=self._worlds, cast_store=self._cast
        )
        return validate_blueprint(
            payload,
            namespace=cast.namespace,
            player_character_id=(
                None
                if cast.player_character is None
                else cast.player_character.player_character_id
            ),
            pov_eligibility={
                member.actor_id: (
                    None if member.profile is None else member.profile.pov_eligible
                )
                for member in cast.members
            },
        )

    # -- write faces ----------------------------------------------------------

    def open_next_chapter(
        self,
        world_id: str,
        blueprint_payload: Mapping[str, Any],
        now: str,
    ) -> Result[ChapterOpening]:
        """Plan the world's next chapter — a Plan-face act only.

        The chapter index is the world's existing maximum plus one (the
        first chapter is 1; §21's monotone ``+1``) — **except when a
        replay residue exists**: the world's ``PLANNED`` chapter holding
        no plan revision at all (a crashed open before its Blueprint
        landed) is **reused** instead of skipped (its own
        ``chapter_index``, its Blueprint minted as revision 1; the
        smallest index wins when several residues exist) — a retry never
        silently lands a new chapter (the V3-4R review's item 4, landed
        in V3-5). The chapter id, the plan id (revision 1) and every
        scene anchor id derive from the L3 laws. The sequence, each step
        one store short transaction: resolve the ``scenes[]`` identities
        first (a fresh chapter's anchor set is empty and every element
        is fresh, minting array ordinals 1..N under ``max(existing) + 1``
        with the derived ``scene_id`` burned into the plan payload; a
        ``scene_ref`` / ``scene_id`` reference is refused here, before a
        single write), create the chapter (``PLANNED``) — or reuse the
        residue — create plan revision 1, adopt it (``ADOPTED`` — the #4
        prerequisite the lifecycle face will check), then reconcile the
        ``scenes[]`` table into ``PLANNED`` anchors (one row per fresh
        element — no ghost rows; a residue may already carry anchors if
        a crashed run reconciled partially, and the resolution matches
        them by identity all the same).

        **The chapter is not opened** (``ACTIVE`` is the lifecycle
        face's move, with its prerequisites) and **no tick moves** (the
        Director has no write path to ``world.current_tick``; #3 /
        N-INV-007). ``now`` is the caller's stamp for every row.

        Refusals: the world does not exist — ``NOT_FOUND``; the world
        holds no ``CURRENT`` Bible revision — ``NOT_FOUND`` (the
        fail-closed law: without world authority there is no Director;
        DATA §26.2.1's block); the payload fails the schema or its
        identity references do not resolve — ``VALIDATION_FAILED``
        (nothing is written); any store refusal rides out unchanged.
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
        if self._bible.current_bible(world_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"chapter not planned for world {world_id!r}: the"
                        " world holds no CURRENT Bible revision — without"
                        " world authority the Director does not plan"
                        " (DATA §26.2.1's fail-closed block)"
                    ),
                )
            )
        validated = self.validate_blueprint(world_id, blueprint_payload)
        if isinstance(validated, Err):
            return Err(validated.error)
        blueprint = validated.value
        residue = self._residue_chapter(world_id)
        if residue is not None:
            chapter_id = residue.chapter_id
            chapter_index = residue.chapter_index
            chapter = residue
        else:
            chapters = self._narrative.chapters_of(world_id)
            chapter_index = chapters[-1].chapter_index + 1 if chapters else 1
            chapter_id = chapter_id_for(world_id, chapter_index)
        resolved = _resolve_scene_targets(
            chapter_id, blueprint.scenes, self._narrative.scenes_of(chapter_id)
        )
        if isinstance(resolved, Err):
            return Err(resolved.error)
        targets = resolved.value
        if residue is None:
            created_chapter = self._narrative.create_chapter(
                chapter_id, world_id, chapter_index, now
            )
            if isinstance(created_chapter, Err):
                return Err(created_chapter.error)
            chapter = created_chapter.value
        # The residue's plan continuation (the V3-5 review's F1): a
        # residue carrying no revision mints revision 1 as usual; one
        # whose latest revision is still ``PROPOSED`` (a crashed open
        # between create_plan and adopt_plan) continues **through the
        # revise face's residue law** — the shapes match: adopt it and
        # reconcile on; the shapes differ: reject the residue and mint
        # the next revision. One whose adopted revision's anchors are
        # partially landed mints no new revision at all — the
        # reconciliation resumes against the adopted plan's own
        # content. Either way a retry never silently lands a new chapter
        # or a second revision next to the residue.
        if residue is not None:
            plans = self._narrative.plans_of(chapter_id)
            if plans and plans[-1].status is PlanRevisionStatus.ADOPTED:
                reconciled = self._reconcile_scenes(chapter_id, targets, now)
                if isinstance(reconciled, Err):
                    return Err(reconciled.error)
                return Ok(
                    ChapterOpening(
                        chapter=chapter,
                        plan=plans[-1],
                        scenes=reconciled.value,
                    )
                )
            if plans and plans[-1].status is PlanRevisionStatus.PROPOSED:
                continued = self._continue_proposed_residue(
                    chapter, plans[-1], blueprint, targets, now
                )
                if isinstance(continued, Err):
                    return Err(continued.error)
                return Ok(continued.value)
        created_plan = self._create_and_adopt_plan(
            chapter_id, 1, blueprint, targets, now
        )
        if isinstance(created_plan, Err):
            return Err(created_plan.error)
        reconciled = self._reconcile_scenes(chapter_id, targets, now)
        if isinstance(reconciled, Err):
            return Err(reconciled.error)
        return Ok(
            ChapterOpening(
                chapter=chapter,
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
        (the L3 Diff rules, V3-4R identity-keyed).

        The new revision is the chapter's existing maximum plus one —
        **except when a replay residue exists** (the V3-4R review's item
        4, landed in V3-5): the chapter's dangling ``PROPOSED`` latest
        revision (a crashed revise before its adoption) is reused — a
        payload whose shape matches the residue is **adopted** and the
        reconciliation continues (no new revision; the shape law is the
        store's own: the same shape replays as a no-op); a payload that
        differs **rejects** the residue and mints the next revision
        (``residue.plan_revision + 1``). Either way the retry never
        silently lands a second revision next to the residue. It is
        created and adopted in the same posture as
        :meth:`open_next_chapter` (adoption supersedes the old revision
        in one store transaction — the Plan face is append-only, the
        old revision stays as history). The ``scenes[]`` identities
        resolve first (:func:`_resolve_scene_targets` — refusals land
        before any write), then:

        - a ``scene_ref`` / burned ``scene_id`` names its anchor; the
          row is left untouched even when the element's content changed
          (the row is a progress anchor; the JSON of the newest adopted
          revision is the content source);
        - an element without a reference matches the live anchor at its
          own array ordinal the same way; an ordinal whose anchor is
          ``DISCARDED`` is no match — retired anchors are never revived
          (the element mints fresh instead);
        - a fresh element mints an unused monotonic ``scene_index``
          (``max(existing) + 1``), gets a new ``PLANNED`` row, and its
          derived ``scene_id`` is burned into the plan payload before
          the revision row lands;
        - an anchor no element claims and that is still ``PLANNED`` is
          discarded (§22: only a never-opened scene can be un-planned);
        - an ``ACTIVE`` / ``COMMITTED`` / ``CLOSED`` row is **never
          touched** (N-INV-003 — a replanning has no write power over
          what the world has touched);
        - a ``scene_index`` is never re-used (a retired index stays
          retired — the anchor rows are history too), and no ghost or
          placeholder row is ever minted.

        The chapter's status **is** consulted for the two terminal-ish
        words (the V3-4 review's F3): a ``SETTLING`` or ``CLOSED``
        chapter has no 「剩余部分」 left to replan (§21 「CLOSED 不可
        reopen；修正走后续章」 / §24 「只重规划剩余部分」), so revising
        one is refused ``VALIDATION_FAILED`` before anything is
        written. A ``PLANNED`` or ``ACTIVE`` chapter's plan is open to
        revision, and §24's own law (「对已 COMMITTED 场无写权」) is
        enforced by the rules above, not by refusing the revision.

        Refusals: the chapter does not exist — ``NOT_FOUND``; the
        chapter's world holds no ``CURRENT`` Bible revision —
        ``NOT_FOUND`` (the fail-closed law; nothing is written); the
        chapter is ``SETTLING`` / ``CLOSED`` — ``VALIDATION_FAILED``
        (nothing is written); the payload fails the schema or its
        identity references do not resolve — ``VALIDATION_FAILED``;
        any store refusal rides out unchanged.
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
        if self._bible.current_bible(chapter.world_id) is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"chapter {chapter_id!r} not revised: world"
                        f" {chapter.world_id!r} holds no CURRENT Bible"
                        " revision — without world authority the Director"
                        " does not plan (DATA §26.2.1's fail-closed"
                        " block)"
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
        resolved = _resolve_scene_targets(
            chapter_id,
            blueprint.scenes,
            self._narrative.scenes_of(chapter_id),
        )
        if isinstance(resolved, Err):
            return Err(resolved.error)
        targets = resolved.value
        plans = self._narrative.plans_of(chapter_id)
        latest = plans[-1] if plans else None
        if latest is not None and latest.status is PlanRevisionStatus.PROPOSED:
            # The dangling PROPOSED latest revision — the replay residue
            # (a crashed revise before its adoption). The two branches
            # the ruling spells (DEC-OPI-be7b094f…32): a payload whose
            # shape matches the residue adopts it and continues — no new
            # revision; a payload that differs rejects the residue and
            # mints the next revision below.
            if _plan_shape_matches(latest, blueprint, targets):
                return self._adopt_residue_and_reconcile(
                    chapter, latest, targets, now
                )
            rejected = self._narrative.reject_plan(
                latest.chapter_plan_id,
                now,
                expected_state_version=latest.state_version,
            )
            if isinstance(rejected, Err):
                return Err(rejected.error)
            plan_revision = latest.plan_revision + 1
        else:
            plan_revision = plans[-1].plan_revision + 1 if plans else 1
        created_plan = self._create_and_adopt_plan(
            chapter_id, plan_revision, blueprint, targets, now
        )
        if isinstance(created_plan, Err):
            return Err(created_plan.error)
        reconciled = self._reconcile_scenes(chapter_id, targets, now)
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

    def _adopt_residue_and_reconcile(
        self,
        chapter: WorldChapterRecord,
        residue: WorldChapterPlanRecord,
        targets: tuple[_SceneTarget, ...],
        now: str,
    ) -> Result[ChapterOpening]:
        """Adopt the chapter's dangling ``PROPOSED`` revision and resume
        the reconciliation against the caller's resolved targets — the
        residue law's same-shape branch, shared by
        :meth:`revise_blueprint` and :meth:`open_next_chapter` (the
        V3-5 review's F1: an open crashing between ``create_plan`` and
        ``adopt_plan`` leaves the same shape a crashed revise does, and
        both faces resume it identically)."""

        adopted = self._narrative.adopt_plan(
            residue.chapter_plan_id,
            now,
            expected_state_version=residue.state_version,
        )
        if isinstance(adopted, Err):
            return Err(adopted.error)
        reconciled = self._reconcile_scenes(chapter.chapter_id, targets, now)
        if isinstance(reconciled, Err):
            return Err(reconciled.error)
        return Ok(
            ChapterOpening(
                chapter=chapter,
                plan=adopted.value,
                scenes=reconciled.value,
            )
        )

    def _continue_proposed_residue(
        self,
        chapter: WorldChapterRecord,
        residue: WorldChapterPlanRecord,
        blueprint: ChapterBlueprint,
        targets: tuple[_SceneTarget, ...],
        now: str,
    ) -> Result[ChapterOpening]:
        """The open face's continuation of a ``PROPOSED`` residue (the
        V3-5 review's F1 window): the payload's shape matches the
        residue — adopt it and reconcile on (no new revision); the
        payload differs — reject the residue and mint the next revision
        (the revise face's own two-branch law, spelled once)."""

        if _plan_shape_matches(residue, blueprint, targets):
            return self._adopt_residue_and_reconcile(
                chapter, residue, targets, now
            )
        rejected = self._narrative.reject_plan(
            residue.chapter_plan_id,
            now,
            expected_state_version=residue.state_version,
        )
        if isinstance(rejected, Err):
            return Err(rejected.error)
        created_plan = self._create_and_adopt_plan(
            chapter.chapter_id,
            residue.plan_revision + 1,
            blueprint,
            targets,
            now,
        )
        if isinstance(created_plan, Err):
            return Err(created_plan.error)
        reconciled = self._reconcile_scenes(chapter.chapter_id, targets, now)
        if isinstance(reconciled, Err):
            return Err(reconciled.error)
        return Ok(
            ChapterOpening(
                chapter=chapter,
                plan=created_plan.value,
                scenes=reconciled.value,
            )
        )

    def _residue_chapter(self, world_id: str) -> WorldChapterRecord | None:
        """The replay residue :meth:`open_next_chapter` reuses: the
        world's ``PLANNED`` chapter whose planning is **incomplete** —
        any of the three crash windows the V3-5 review's F1 proves (the
        ruling DEC-OPI-be7b094f…32's 「重试不跳新章」 covers all three):

        - **no plan revision at all** (a crashed open between
          ``create_chapter`` and ``create_plan`` — the V3-4 review's F1
          shape);
        - the latest revision still ``PROPOSED`` (a crashed open between
          ``create_plan`` and ``adopt_plan``);
        - the latest revision ``ADOPTED`` but its anchors not fully
          landed (a crashed open between ``adopt_plan`` and the
          reconciliation's end — detected by the adopted revision's
          ``scenes`` table naming more identities than the chapter's
          ``world_scene`` rows carry).

        ``chapters_of`` reads in ``chapter_index`` order, so the first
        match is the smallest index when several residues exist; ``None``
        when the world holds none. A chapter whose planning is complete
        (an adopted revision whose anchors are all landed) is not this
        residue — it is a chapter waiting for its lifecycle face. A
        ``SUPERSEDED`` / ``REJECTED`` latest revision marks a chapter
        whose planning history closed without a current plan — also not
        this residue (replanning it is :meth:`revise_blueprint`'s face).
        """

        for chapter in self._narrative.chapters_of(world_id):
            if chapter.status is not ChapterStatus.PLANNED:
                continue
            plans = self._narrative.plans_of(chapter.chapter_id)
            if not plans:
                return chapter
            latest = plans[-1]
            if latest.status is PlanRevisionStatus.PROPOSED:
                return chapter
            if latest.status is PlanRevisionStatus.ADOPTED:
                anchors = self._narrative.scenes_of(chapter.chapter_id)
                if len(latest.scenes) > len(anchors):
                    return chapter
        return None

    def _create_and_adopt_plan(
        self,
        chapter_id: str,
        plan_revision: int,
        blueprint: ChapterBlueprint,
        targets: tuple[_SceneTarget, ...],
        now: str,
    ) -> Result[WorldChapterPlanRecord]:
        """Create one plan revision from a validated Blueprint and its
        resolved targets, and adopt it (the two store short
        transactions; every chapter field verbatim, the scenes table
        the resolution's own — a fresh element already carrying its
        burned ``scene_id``, an existing element riding as given, both
        under the store's own deterministic codec)."""

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
            scenes=tuple(target.element for target in targets),
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
        self,
        chapter_id: str,
        targets: tuple[_SceneTarget, ...],
        now: str,
    ) -> Result[tuple[WorldSceneRecord, ...]]:
        """The L3 reconciliation, identity-keyed (see
        :meth:`revise_blueprint` for the rules): mint one ``PLANNED``
        row per fresh target (its ``scene_index`` already the unused
        monotonic one — never an array ordinal by construction),
        discard the unclaimed still-``PLANNED`` anchors (rows no
        element speaks for; retired anchors stay retired and happened
        anchors stay untouched), touch nothing else, and answer the
        chapter's rows in ``scene_index`` order (discarded anchors
        included — history is rows, not errors).

        Creation is guarded by the resolution's own identities — every
        index came from :func:`_resolve_scene_targets`, so a
        ``scene_index`` is never minted twice (the table's UNIQUE backs
        the same law at the storage level)."""

        existing = self._narrative.scenes_of(chapter_id)
        claimed = {target.scene_index for target in targets}
        for target in targets:
            if not target.is_new:
                continue
            created = self._narrative.create_scene(
                target.scene_id, chapter_id, target.scene_index, now
            )
            if isinstance(created, Err):
                return Err(created.error)
        for row in existing:
            if row.scene_index in claimed:
                continue
            if row.status is not SceneStatus.PLANNED:
                continue  # ACTIVE / COMMITTED / CLOSED / DISCARDED: history
            discarded = self._narrative.discard_scene(
                row.scene_id, now, expected_state_version=row.state_version
            )
            if isinstance(discarded, Err):
                return Err(discarded.error)
        return Ok(self._narrative.scenes_of(chapter_id))
