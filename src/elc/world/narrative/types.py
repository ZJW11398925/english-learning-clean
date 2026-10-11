"""The Narrative V3 record shapes and lifecycle vocabularies (V3-1,
DEC-OPI-bab4da9f…11/…16) — the foundations cut's type face.

The vocabularies are the canonical word lists, spelled word for word:

- :class:`ChapterStatus` — STATE_MACHINES §21's four words
  (``PLANNED`` / ``ACTIVE`` / ``SETTLING`` / ``CLOSED``); the store's
  CHECK and this StrEnum spell the same list, so a third word cannot
  reach the row and a moved word reddens a test.
- :class:`SceneStatus` — §22's five words (``PLANNED`` / ``ACTIVE`` /
  ``COMMITTED`` / ``CLOSED`` / ``DISCARDED``); ``DISCARDED`` is
  reachable only from ``PLANNED`` (a scene a commit has touched cannot
  be un-happened).
- :class:`PlanRevisionStatus` — §24's four words (``PROPOSED`` /
  ``ADOPTED`` / ``SUPERSEDED`` / ``REJECTED``); the Plan face is
  append-only versioned — revisions are never rewritten, ``ADOPTED``
  points at the current plan and is unique per planned row.

**The Plan/Canon boundary is a type distinction, not a convention**
(DOMAIN_MODEL §20.3-2/§20.3-8, N-INV-001, N-R-INV-007): the two canon
progress records (:class:`WorldChapterRecord`, :class:`WorldSceneRecord`)
carry the lifecycle statuses the commit face moves and the actual tick
columns; the two plan-face records (:class:`WorldChapterPlanRecord`,
:class:`WorldSceneDossierRecord`) carry :class:`PlanRevisionStatus` and
the ``planned_*_tick`` fields. A reader that wants to know whether a
row can lie about the world's past checks the type: a
:class:`PlanFaceRecord` subclass is a plan — uncommitted content,
never readable as fact (N-INV-001) — while a
:class:`CanonProgressRecord` subclass is the progress row the commit
face moves. The marker bases exist so the boundary is checkable by
:class:`issubclass` in code and pinned by tests, not just by docstring.

The field sets are DATA_MODEL §26.2.1's semantic fields (the migration's
column names spell them); ``state_version`` is the row's CAS counter
(the house store discipline — bumped on every write, checked on every
move). The JSON codecs (:func:`encode_scenes` / :func:`decode_scenes`)
freeze the Blueprint's scene table into the plan row's ``scenes``
column with the same deterministic law the world types' effects and
participants codecs spell.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from elc.platform.types import DomainError, DomainErrorCode, Err, Ok, Result

__all__ = [
    "ChapterStatus",
    "SceneStatus",
    "PlanRevisionStatus",
    "CanonProgressRecord",
    "PlanFaceRecord",
    "WorldChapterRecord",
    "WorldChapterPlanRecord",
    "WorldSceneRecord",
    "WorldSceneDossierRecord",
    "encode_scenes",
    "decode_scenes",
]


class ChapterStatus(StrEnum):
    """The chapter row's four-word lifecycle (STATE_MACHINES §21).

    ``PLANNED`` — the Blueprint is in (Plan face), the chapter has not
    opened; ``ACTIVE`` — at least one scene is active; ``SETTLING`` —
    the end-of-chapter settlement is running (a short window); ``CLOSED``
    — the settlement is done (summary / narrative memory landed). A
    ``CLOSED`` chapter never reopens (§21's rule; corrections go through
    later chapters, N-INV-003).
    """

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    SETTLING = "SETTLING"
    CLOSED = "CLOSED"


class SceneStatus(StrEnum):
    """The scene row's five-word lifecycle (STATE_MACHINES §22).

    ``PLANNED`` — Plan face: the Blueprint/Dossier planned the scene (a
    replanning may ``DISCARDED`` it); ``ACTIVE`` — the Dossier is in,
    passage segments are being written (User Gate stops included);
    ``COMMITTED`` — every segment of the scene has committed (the canon
    face holds); ``CLOSED`` — the scene is closed (the next scene's
    input package is built); ``DISCARDED`` — reachable **only from
    ``PLANNED``**: a replanning retired the scene before it ever
    happened.
    """

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    CLOSED = "CLOSED"
    DISCARDED = "DISCARDED"


class PlanRevisionStatus(StrEnum):
    """A plan row's four-word revision lifecycle (STATE_MACHINES §24).

    ``PROPOSED`` — the Director / Scene Planner produced the revision;
    ``ADOPTED`` — it is the current plan (older revisions stay as
    history); ``SUPERSEDED`` — a newer revision took its place (history
    preserved); ``REJECTED`` — explicitly vetoed (the reason rides the
    adopting face's caller). The Plan face is append-only: no revision
    is ever rewritten.
    """

    PROPOSED = "PROPOSED"
    ADOPTED = "ADOPTED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class CanonProgressRecord:
    """Type marker for the canon-face progress rows.

    A subclass is a row the **commit face** moves
    (:class:`WorldChapterRecord`, :class:`WorldSceneRecord`): its status
    words come from :class:`ChapterStatus` / :class:`SceneStatus`, its
    tick fields are actual ticks (written by commit transactions —
    DATA_MODEL §26.2.2), and reading it as fact is reading what has
    happened. This marker is the boundary's canon half.
    """


class PlanFaceRecord:
    """Type marker for the Plan-face rows.

    A subclass is a row the **planning face** writes
    (:class:`WorldChapterPlanRecord`, :class:`WorldSceneDossierRecord`):
    its status words come from :class:`PlanRevisionStatus`, its tick
    fields carry the ``planned_`` prefix, and **nothing it says is a
    fact** — uncommitted Plan content must never be read as canon
    (N-INV-001 / N-R-INV-007). The status word itself is the boundary
    marker: a plan row's ``ADOPTED`` says "this is the current plan",
    never "this happened". This marker is the boundary's plan half, and
    it deliberately shares no base with :class:`CanonProgressRecord` —
    a type confusion between the two faces is a bug the type system
    can see.
    """


@dataclass(frozen=True)
class WorldChapterRecord(CanonProgressRecord):
    """One chapter's canon-face progress row (migration 0029's
    ``world_chapter``; DATA_MODEL §26.2.1).

    ``opened_at_tick`` / ``closed_at_tick`` are canon-face tick fields —
    integer story ticks, ``None`` until the lifecycle face stamps them
    (the values ride from the caller's read of the current actual tick;
    the commit-transaction law governs ``world.current_tick`` itself).
    ``state_version`` is the row's CAS counter.
    """

    chapter_id: str
    world_id: str
    chapter_index: int
    status: ChapterStatus
    opened_at_tick: int | None
    closed_at_tick: int | None
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class WorldChapterPlanRecord(PlanFaceRecord):
    """One chapter's Plan face, append-only versioned (migration 0029's
    ``world_chapter_plan``; DATA_MODEL §26.2.1 + STATE_MACHINES §24).

    The Blueprint's semantic fields verbatim: ``goal`` /
    ``dramatic_question``, the planned time span
    (``planned_start_tick`` / ``planned_end_tick`` — Plan time, the
    planned_ prefix law), the soft-expectation set ``closing_pressure``
    / ``desired_development`` / ``soft_outcomes`` /
    ``chapter_questions_to_advance`` (never a postcondition — the V3-0R
    wording law), and ``scenes`` — the scene table's frozen JSON (the
    :func:`encode_scenes` law). ``plan_revision`` is unique per chapter
    together with the chapter (DATA §26.2.4); revisions are never
    rewritten.
    """

    chapter_plan_id: str
    chapter_id: str
    plan_revision: int
    status: PlanRevisionStatus
    goal: str
    dramatic_question: str
    planned_start_tick: int
    planned_end_tick: int
    closing_pressure: str
    desired_development: str
    soft_outcomes: str
    chapter_questions_to_advance: str
    scenes: tuple[dict[str, Any], ...]
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class WorldSceneRecord(CanonProgressRecord):
    """One scene's canon-face progress row (migration 0029's
    ``world_scene``; DATA_MODEL §26.2.1).

    ``actual_start_tick`` / ``actual_end_tick`` are the scene's actual
    span — decided by the scene's commits (STATE_MACHINES §26: the
    actual span is the commits', and it may differ from the planned
    one); V3-1 ships no commit transaction, so the lifecycle face
    leaves them ``None`` and the commit cuts write them.
    """

    scene_id: str
    chapter_id: str
    scene_index: int
    status: SceneStatus
    actual_start_tick: int | None
    actual_end_tick: int | None
    created_at: str
    updated_at: str
    state_version: int


@dataclass(frozen=True)
class WorldSceneDossierRecord(PlanFaceRecord):
    """One scene's execution plan, append-only versioned (migration
    0029's ``world_scene_dossier``; DATA_MODEL §26.2.1 + STATE_MACHINES
    §24 — the Scene Planner's instant re-planning of the Blueprint).

    ``pov_actor_id`` — the scene's one POV (the Writer's discipline: a
    scene has one main POV, no uncontrolled head-hopping);
    ``participants`` — the participant namespace (cast ids ∪
    {player_character_id} ∪ residents), the world types' strict-JSON
    participants codec's payload; ``place``, ``planned_start_tick``,
    the POV-discipline pair ``revealable`` / ``must_hide``,
    ``entry_goals``, ``exit_condition`` and ``elasticity`` carry the
    Dossier's semantic content verbatim. ``dossier_revision`` is unique
    per scene together with the scene (DATA §26.2.4).
    """

    dossier_id: str
    scene_id: str
    dossier_revision: int
    status: PlanRevisionStatus
    pov_actor_id: str
    participants: tuple[str, ...]
    place: str
    planned_start_tick: int
    revealable: str
    must_hide: str
    entry_goals: str
    exit_condition: str
    elasticity: str
    created_at: str
    updated_at: str
    state_version: int


def encode_scenes(scenes: tuple[dict[str, Any], ...]) -> str:
    """Freeze the Blueprint's scene table into the plan row's ``scenes``
    column text — the same deterministic law the world types'
    :func:`elc.world.types.encode_effects` spells (compact separators,
    insertion order, non-escaped characters): the same table always
    encodes to the same bytes, so a replay writes what the first write
    wrote.

    The elements pass through as the caller's objects (the scene
    entries' shape is the Director's own — purpose, planned time, place,
    POV, participants, goals, beats, revealable/must-hide, gates, exit,
    elasticity; the design doc §2.2 names the fields) — this codec
    owns the *array-ness and determinism*, not the entries' schema
    (that is V3-4's reconciliation face, the DECISION_REGISTER's L3).
    """

    payload = [dict(scene) for scene in scenes]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_scenes(text: str) -> Result[tuple[dict[str, Any], ...]]:
    """The strict inverse of :func:`encode_scenes`.

    A payload that is not valid JSON, not a JSON array, or carries a
    non-object element answers a value-semantics ``Err``
    (``VALIDATION_FAILED``) whose message names the reason — the
    discrimination words are ``not valid JSON`` / ``not a JSON array`` /
    ``is not a JSON object``. The elements' own schema is the Director's,
    not this codec's. Decoding is a read-side concern only (the write
    face encodes from typed records and cannot produce a bad payload).
    """

    def _err(message: str) -> Err[Any]:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=f"scenes refused: {message}",
            )
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return _err(f"not valid JSON ({exc})")
    if not isinstance(payload, list):
        return _err("not a JSON array")
    for element in payload:
        if not isinstance(element, dict):
            return _err(f"element {element!r} is not a JSON object")
    return Ok(tuple(payload))
