"""The Scene Planner's V3-5 machine face (TASK-OPI-be7b094f…34 / the
opening ruling DEC-OPI-be7b094f…32) — the deterministic half of the
design's §2.3 Scene Planner: read the chapter's adopted Blueprint, locate
the scene's own element in its ``scenes`` table, land the Dossier's
revision 1 and activate the scene.

**What ships here is the structure, not the prose** (the same
schema-and-table-side-only scope V3-4 spelled for the Blueprint): the
LLM-driven scene-planning face — reading the POV character's cognition
view, choosing entrances and elasticity from the moment's needs — is
registered for a later cut. The deterministic baseline assembles the
dossier from durable data alone:

- the **element** comes from the chapter's current ``ADOPTED`` plan
  revision (the L3 law: the newest adopted revision's ``scenes`` JSON
  is the content authority; the ``world_scene`` rows are progress
  anchors). The scene is located by its durable identity — the burned
  ``scene_id`` key first, then a ``scene_ref`` equal to its
  ``scene_index``, then the reconciliation's own positional law (an
  element carrying no identity key sits at its anchor's ordinal). A
  ``DISCARDED`` anchor is never activatable (the consumption cut's
  ban): the status check below refuses it before the plan is even read;
- the dossier's fields ride **verbatim** from the element
  (``pov_actor_id`` / ``participants`` / ``place`` / ``entry_goals`` /
  ``exit_condition`` / ``elasticity`` / ``revealable`` / ``must_hide``
  — the canonical ten minus the two the planner owns, ``scene_id`` and
  the tick), with **one deliberate substitution**: ``planned_start_tick``
  is ``max(context.current_tick, element's planned_start_tick)`` — the
  V3-5R time law (TASK-OPI-dc1bafdf…13 / DEC-OPI-dc1bafdf…11's item 4,
  DATA §26.2.1's "V3-5R 落法"): when the world's reality has run past
  the Blueprint's older guess the current tick wins, a future-planned
  start is kept — and the scene's actual span still moves only through
  the commits (STATE §26);
- **the scene's planning context** (:class:`SceneContext`, V3-5R's
  HIGH-1): ``current_tick`` as the Director context reads it, the POV's
  canonical identity, and the POV's **V3 cognition view**
  (:func:`elc.world.cognition.v3_cognition_view`) — the lineage-based
  read (V3 events only via their ``segment_commit`` row, actual-interval
  order, canonical-identity layers). The view rides out on
  :attr:`SceneOpening.context`; a read refusal rides out unchanged;
- the write chain is the store's own faces, each idempotent by id:
  create dossier revision 1 (``f"{scene_id}-d1"`` — the planner's local
  naming for replays; the contract freezes three derivation laws and
  this is not one of them), adopt it (``PROPOSED → ADOPTED`` — the #4
  prerequisite the activation will check), then
  :meth:`SqliteNarrativeStore.activate_scene` (``PLANNED → ACTIVE`` —
  the actual tick columns stay untouched: the scene's actual span is
  its commits', V3-5's SEGMENT COMMIT).

Refusals are value semantics (never an exception): a dangling scene —
``NOT_FOUND``; a scene not ``PLANNED`` (including ``DISCARDED`` — a
retired anchor is never activatable) — ``VALIDATION_FAILED``; a chapter
without an ``ADOPTED`` Blueprint, a plan carrying no element for the
scene, or an element missing / mistyping a canonical field (the
``planned_start_tick`` tick included — a corrupted plan row answered
honestly) — ``VALIDATION_FAILED``; any store or cognition refusal rides
out unchanged.

**The replay boundary, stated honestly**: a retry after a crash between
the dossier's adoption and the scene's activation is refused loudly (the
adoption face accepts only ``PROPOSED`` revisions) — it never silently
mints a second dossier or a second scene, and the residue is exactly the
``adopted dossier + PLANNED scene`` a recovery face can pick up. The
Director's own crash/replay closure is this cut's (see
:mod:`elc.world.director`); a Scene Planner replay buffer is not — if a
later cut wants one, it reopens this docstring.

Discipline (the house law): value semantics; **no hidden clock** (every
stamp is the caller's ``now``); **no transaction of its own** (the store
faces own their short transactions — a nested BEGIN would break that
composability, the :mod:`elc.world.time` posture); **no SQL at all**
(this module reads through the stores and the Director context face);
the Package is not consulted anywhere (the durable rows are the runtime
authority — the V3-3R recipe).
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
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.cognition import V3CognitionView, v3_cognition_view
from elc.world.director import build_director_context
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    SceneStatus,
    WorldSceneDossierRecord,
    WorldSceneRecord,
)
from elc.world.store import SqliteWorldStore

__all__ = ["SceneContext", "SceneOpening", "ScenePlanner", "dossier_id_for"]

#: The element's plain-text keys the dossier carries verbatim (the
#: canonical ten minus ``scene_id`` / ``scene_ref`` (identity, not
#: dossier content), ``participants`` / ``pov_actor_id`` /
#: ``planned_start_tick`` (checked separately — the tick's own law is
#: the V3-5R ``max(current_tick, element)`` substitution — see the
#: module docstring).
_DOSSIER_TEXT_KEYS = (
    "place",
    "entry_goals",
    "exit_condition",
    "elasticity",
    "revealable",
    "must_hide",
)


def dossier_id_for(scene_id: str, dossier_revision: int) -> str:
    """The Scene Planner's own revision naming:
    ``f"{scene_id}-d{dossier_revision}"`` — local idempotence only (the
    contract's three derivation laws cover chapter / plan / scene
    identities; a dossier id serves replays of revision 1)."""

    return f"{scene_id}-d{dossier_revision}"


@dataclass(frozen=True)
class SceneContext:
    """One scene's planning context (V3-5R, TASK-OPI-dc1bafdf…13 /
    DEC-OPI-dc1bafdf…11's HIGH-1): the canonical story time the Director
    context reads (``current_tick``), the POV's own canonical identity,
    and the POV's V3 cognition view — the lineage read
    (:func:`elc.world.cognition.v3_cognition_view`) the scene plans
    from. The view is built for this scene's POV, so its ``viewer_id``
    equals ``pov_actor_id``; the dossier's ``planned_start_tick`` rides
    ``max(current_tick, element's)`` (the V3-5R time law)."""

    current_tick: int
    pov_actor_id: str
    cognition: V3CognitionView


@dataclass(frozen=True)
class SceneOpening:
    """One ``open_scene`` ``Ok`` shape: the activated scene row, the
    adopted dossier revision, the Blueprint element both were built
    from (the caller's own mapping — the content source, verbatim), and
    the scene's planning context (:class:`SceneContext` — the canonical
    tick and the POV's cognition view this open read)."""

    scene: WorldSceneRecord
    dossier: WorldSceneDossierRecord
    element: dict[str, Any]
    context: SceneContext


class ScenePlanner:
    """The Scene Planner over one database — the deterministic baseline:
    open one planned scene (dossier rev 1 from the adopted Blueprint
    element, adopted, scene activated).

    Construction mirrors the composition root (the Director's own
    shape): the caller hands the same connection's stores — the
    context face needs the world / cast / Bible stores, the plan face
    needs the narrative store.
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

    def open_scene(self, scene_id: str, now: str) -> Result[SceneOpening]:
        """Open one planned scene — the deterministic chain the module
        docstring spells (refusals included). ``now`` stamps every row;
        no tick moves (the commits own ``world.current_tick``). The
        POV's V3 cognition view is read here (its refusal rides out
        unchanged) and the dossier's ``planned_start_tick`` rides
        ``max(current_tick, element's)`` — the V3-5R time law."""

        scene = self._narrative.get_scene(scene_id)
        if scene is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"scene {scene_id!r} not opened: it does not exist"
                    ),
                )
            )
        if scene.status is not SceneStatus.PLANNED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} is {scene.status.value!r};"
                        " only a PLANNED scene opens (a DISCARDED anchor"
                        " is retired — a consumption cut never activates"
                        " one; an ACTIVE or settled scene is already past"
                        " this step)"
                    ),
                )
            )
        chapter = self._narrative.get_chapter(scene.chapter_id)
        if chapter is None:  # the FK makes this unreachable; answered honestly
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"scene {scene_id!r} not opened: chapter"
                        f" {scene.chapter_id!r} does not exist"
                    ),
                )
            )
        plan = self._narrative.adopted_plan(scene.chapter_id)
        if plan is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} not opened: chapter"
                        f" {scene.chapter_id!r} holds no ADOPTED Blueprint"
                        " (plan revision) — the dossier is assembled from"
                        " the current plan"
                    ),
                )
            )
        located = _locate_element(plan.scenes, scene)
        if located is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} not opened: the adopted"
                        f" Blueprint {plan.chapter_plan_id!r} carries no"
                        f" element for it (scene_id {scene.scene_id!r} /"
                        f" scene_ref {scene.scene_index!r}) — the newest"
                        " adopted revision's scenes table is the content"
                        " source"
                    ),
                )
            )
        element, ordinal = located
        fields = _element_fields(element, ordinal)
        if isinstance(fields, Err):
            return Err(fields.error)
        director_context = build_director_context(
            self._conn,
            chapter.world_id,
            world_store=self._worlds,
            cast_store=self._cast,
            bible_store=self._bible,
        )
        # The POV's V3 cognition view (V3-5R HIGH-1): the lineage-based
        # read this scene plans from; a refusal rides out unchanged.
        cognition = v3_cognition_view(
            self._conn,
            world_id=chapter.world_id,
            viewer_id=fields.value["pov_actor_id"],
        )
        if isinstance(cognition, Err):
            return Err(cognition.error)
        context = SceneContext(
            current_tick=director_context.current_tick,
            pov_actor_id=fields.value["pov_actor_id"],
            cognition=cognition.value,
        )
        # The V3-5R time law (DEC-OPI-dc1bafdf…11's item 4): the later
        # of the world's reality and the Blueprint's own guess.
        planned_start_tick = max(
            context.current_tick, fields.value["planned_start_tick"]
        )
        dossier_id = dossier_id_for(scene_id, 1)
        created = self._narrative.create_dossier(
            dossier_id,
            scene_id,
            1,
            pov_actor_id=fields.value["pov_actor_id"],
            participants=fields.value["participants"],
            place=fields.value["place"],
            planned_start_tick=planned_start_tick,
            revealable=fields.value["revealable"],
            must_hide=fields.value["must_hide"],
            entry_goals=fields.value["entry_goals"],
            exit_condition=fields.value["exit_condition"],
            elasticity=fields.value["elasticity"],
            now=now,
        )
        if isinstance(created, Err):
            return Err(created.error)
        adopted = self._narrative.adopt_dossier(
            dossier_id, now, expected_state_version=created.value.state_version
        )
        if isinstance(adopted, Err):
            return Err(adopted.error)
        activated = self._narrative.activate_scene(
            scene_id, now, expected_state_version=scene.state_version
        )
        if isinstance(activated, Err):
            return Err(activated.error)
        return Ok(
            SceneOpening(
                scene=activated.value,
                dossier=adopted.value,
                element=element,
                context=context,
            )
        )


def _locate_element(
    scenes: tuple[dict[str, Any], ...], scene: WorldSceneRecord
) -> tuple[dict[str, Any], int] | None:
    """The scene's element in the adopted plan's ``scenes`` table, or
    ``None`` — the identity precedence the L3 rules spell: the burned
    ``scene_id`` key first, then a ``scene_ref`` equal to the anchor's
    ``scene_index``, then the reconciliation's own positional law (an
    element carrying neither identity key sits at its anchor's array
    ordinal, one-based)."""

    for ordinal, element in enumerate(scenes, start=1):
        burned = element.get("scene_id")
        if isinstance(burned, str) and burned == scene.scene_id:
            return element, ordinal
        ref = element.get("scene_ref")
        if isinstance(ref, int) and not isinstance(ref, bool):
            if ref == scene.scene_index:
                return element, ordinal
    for ordinal, element in enumerate(scenes, start=1):
        if "scene_id" in element or "scene_ref" in element:
            continue
        if ordinal == scene.scene_index:
            return element, ordinal
    return None


def _element_fields(
    element: Mapping[str, Any], ordinal: int
) -> Result[dict[str, Any]]:
    """The dossier's element-derived fields, validated in the Blueprint's
    own ordinal language (``scenes[N]`` — the coordinate every plan
    refusal uses). The adopted plan passed the Director's schema, so a
    malformed element here is a corrupted plan row answered honestly,
    not a caller mistake; the ``planned_start_tick`` tick is validated
    here too (the Director's schema guarantees an int — the V3-5R time
    law reads the value, and a corrupted row is refused, never guessed)."""

    pov = element.get("pov_actor_id")
    if not isinstance(pov, str):
        return _refuse(
            f"scenes[{ordinal}].pov_actor_id must be a string; got"
            f" {type(pov).__name__}"
        )
    participants = element.get("participants")
    if isinstance(participants, (str, bytes)) or not isinstance(
        participants, (list, tuple)
    ):
        return _refuse(
            f"scenes[{ordinal}].participants must be a sequence of"
            f" participant identities; got {type(participants).__name__}"
        )
    words: list[str] = []
    for word in participants:
        if not isinstance(word, str):
            return _refuse(
                f"scenes[{ordinal}].participants carries a non-string"
                f" entry {word!r}"
            )
        words.append(word)
    planned_start = element.get("planned_start_tick")
    if not isinstance(planned_start, int) or isinstance(planned_start, bool):
        return _refuse(
            f"scenes[{ordinal}].planned_start_tick must be an integer tick;"
            f" got {type(planned_start).__name__}"
        )
    fields: dict[str, Any] = {
        "pov_actor_id": pov,
        "participants": tuple(words),
        "planned_start_tick": planned_start,
    }
    for key in _DOSSIER_TEXT_KEYS:
        value = element.get(key)
        if not isinstance(value, str):
            return _refuse(
                f"scenes[{ordinal}].{key} must be a string; got"
                f" {type(value).__name__}"
            )
        fields[key] = value
    return Ok(fields)


def _refuse(reason: str) -> Err[Any]:
    """One refusal as a human sentence (the Director schema's own
    ``Blueprint refused`` family — the plan face's vocabulary)."""

    return Err(
        DomainError(
            code=DomainErrorCode.VALIDATION_FAILED,
            message=f"scene plan refused: {reason}",
        )
    )
