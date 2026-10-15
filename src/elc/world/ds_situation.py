"""The dual-seat chapter's situation plan machine (DS-3, the technical
definition §6 — docs/design/2026-10-14-dual-seat-world-technical-
definition.md) — the /ds product path's own chapter planning face.

**What this module is.** The four-question contract, landed: the
director agent's situation planner arm
(:class:`~elc.world.llm_providers.LlmSituationPlannerProvider`) answers
①这一幕你在哪 ②什么事冲你来 ③谁对你说第一句话 ④第一幕交互悬点 beside
the minimal field set (本章世界事件候选×你的处境与位置×各主角目标×节奏
与结算预期), and this face lands it as the chapter's adopted plan —
the same Plan-face rows the rest of the spine reads, so the drive half
(``elc.world.turns``) and the dossier machinery
(:meth:`elc.world.scene.ScenePlanner.open_scene`) work unchanged.

**Storage: zero migration** (the cut's own law): the situation document
rides the existing ``world_chapter_plan`` row — ``goal`` carries ②'s
answer (the chapter's pressure), and the ``scenes`` table's one element
carries the canonical ten keys the dossier derives from BESIDE the
situation keys (supplemental keys pass through verbatim — the Director
schema's own law; :func:`situation_face_of` reads them back). The old
literary columns (``dramatic_question`` and the soft-expectation set)
land empty: the plan CONTRACT carries no literary-structure field (§6:
四场铺陈/氛围开场/dramatic_question 章法不得回流), and the old blueprint
machine (:meth:`elc.world.pipeline.Pipeline.plan_chapter`) stays the
retired test face — the product path never asks it again.

**Landing is replay-safe** (the Director's own residue law): a world
whose latest chapter already holds an adopted plan answers that opening
zero-write; a ``PLANNED`` chapter holding no plan revision at all (a
crashed open) is reused — the retry never lands a second chapter. Every
write is a store face's own short transaction; this module spells no
SQL and no ``BEGIN`` of its own; no hidden clock (every stamp is the
caller's ``now``).
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
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.director import (
    build_director_context,
    chapter_id_for,
    plan_id_for,
    scene_id_for,
)
from elc.world.llm_providers import (
    LlmSituationPlannerProvider,
    SituationPlan,
    SituationPlanContext,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneRecord,
)
from elc.world.store import SqliteWorldStore

__all__ = [
    "SITUATION_DOC_KEYS",
    "SituationOpening",
    "plan_situation_chapter",
    "situation_face_of",
]


#: The situation document's own keys, as the plan element carries them
#: (DS-3 §6 verbatim: the four questions + the minimal field set).
#: ``first_speaker`` / ``protagonist_goals`` keys are identity strings;
#: everything else is prose. The canonical ten dossier keys live beside
#: them in the same element.
SITUATION_DOC_KEYS = (
    "where_you_stand",
    "what_presses_on_you",
    "first_speaker",
    "first_words",
    "open_question",
    "world_event_candidates",
    "protagonist_goals",
    "pacing",
    "settlement_expectation",
)

#: The situation plan's story-time window (the plan face's own guess —
#: the actual span is the commits', STATE_MACHINES §26, and never this
#: number): one DS tick is one minute of story time, so four hours of
#: story time is the chapter's generous planned horizon.
_CHAPTER_TICK_HORIZON = 240


@dataclass(frozen=True)
class SituationOpening:
    """One situation plan's landing — the chapter row (``PLANNED``),
    the adopted plan revision carrying the situation document, and the
    one planned scene anchor the opening beat opens."""

    chapter: WorldChapterRecord
    plan: WorldChapterPlanRecord
    scene: WorldSceneRecord
    fresh_plan: bool


def situation_face_of(
    plan: WorldChapterPlanRecord | None,
) -> dict[str, Any] | None:
    """The plan's situation document, or ``None`` — the read side both
    the state face and the dispatch arm share. A plan whose first
    element carries the situation keys answers the document verbatim; a
    legacy blueprint plan (the retired test face's rows) answers
    ``None`` — the caller falls back to the plan's ``goal`` alone, so
    old rows stay readable without pretending they carry the four
    questions."""

    if plan is None or not plan.scenes:
        return None
    element = plan.scenes[0]
    if not isinstance(element, dict):
        return None
    if any(key not in element for key in SITUATION_DOC_KEYS):
        return None
    return {
        key: element[key] for key in SITUATION_DOC_KEYS
    }


def plan_situation_chapter(
    conn: sqlite3.Connection,
    *,
    world_store: SqliteWorldStore,
    cast_store: SqliteCastStore,
    bible_store: SqliteBibleStore,
    narrative_store: SqliteNarrativeStore,
    planner: LlmSituationPlannerProvider,
    world_id: str,
    now: str,
    author_direction: str | None = None,
) -> Result[SituationOpening]:
    """Plan the world's next chapter as a SITUATION (DS-3 §6) — the
    four questions asked, the document landed as the chapter's adopted
    plan revision, the one scene anchor reconciled. See the module
    docstring; refusals ride out as value semantics, nothing written on
    a refused plan."""

    try:
        context = build_director_context(
            conn,
            world_id,
            world_store=world_store,
            cast_store=cast_store,
            bible_store=bible_store,
        )
    except ValueError as exc:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=f"chapter not planned: {exc}",
            )
        )
    if context.bible is None:
        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"chapter not planned for world {world_id!r}: the"
                    " world holds no CURRENT Bible revision — without"
                    " world authority the Director does not plan"
                    " (DATA §26.2.1's fail-closed block)"
                )
            )
        )
    player = context.cast.player_character
    if player is None:
        return Err(
            DomainError(
                code=DomainErrorCode.VALIDATION_FAILED,
                message=(
                    f"chapter not planned for world {world_id!r}: the"
                    " world declares no player character — the four"
                    " questions are all about YOU, so a world without"
                    " you has no situation plan"
                )
            )
        )
    chapters = narrative_store.chapters_of(world_id)
    residue: WorldChapterRecord | None = None
    if chapters:
        last = chapters[-1]
        if last.status in (
            ChapterStatus.PLANNED,
            ChapterStatus.ACTIVE,
        ):
            adopted = narrative_store.adopted_plan(last.chapter_id)
            if adopted is not None:
                # already planned — the idempotent zero-write answer
                # (the start face's own posture; a re-ask never re-casts
                # and never lands a second chapter). The one anchor
                # reconciles idempotently (a crash between adopt and
                # reconcile converges here).
                scene_id = scene_id_for(last.chapter_id, 1)
                reconciled = narrative_store.create_scene(
                    scene_id, last.chapter_id, 1, now
                )
                if isinstance(reconciled, Err):
                    return Err(reconciled.error)
                return Ok(
                    SituationOpening(
                        chapter=last,
                        plan=adopted,
                        scene=reconciled.value,
                        fresh_plan=False,
                    )
                )
            if last.status is ChapterStatus.PLANNED and not (
                narrative_store.plans_of(last.chapter_id)
            ):
                # the residue law: a crashed open before its plan
                # landed — the retry reuses the chapter, never skips
                # the index
                residue = last
    if residue is not None:
        chapter_id = residue.chapter_id
        chapter_index = residue.chapter_index
        chapter = residue
    else:
        chapter_index = chapters[-1].chapter_index + 1 if chapters else 1
        chapter_id = chapter_id_for(world_id, chapter_index)
        # the chapter row lands BEFORE the model call: a crashed open
        # leaves exactly the residue the law above reuses on the retry
        # (the Director's own crash posture)
        created = narrative_store.create_chapter(
            chapter_id, world_id, chapter_index, now
        )
        if isinstance(created, Err):
            return Err(created.error)
        chapter = created.value
    members = tuple(
        (member.actor_id, member.name) for member in context.cast.members
    )
    # "where the world stands now": the latest adopted dossier's place —
    # the opening chapter reads the honest empty string.
    place = _last_place_of(conn, world_id)
    doc = planner.plan(
        SituationPlanContext(
            world_id=world_id,
            chapter_index=chapter_index,
            current_tick=context.current_tick,
            premise=context.bible.premise,
            hard_rules=context.bible.hard_rules,
            place=place,
            recent_narration="",
            cast_members=members,
            player_id=player.player_character_id,
            player_name=player.name,
            author_direction=author_direction,
        )
    )
    element = _element_of(
        doc,
        player_id=player.player_character_id,
        tick=context.current_tick,
    )
    scene_id = scene_id_for(chapter_id, 1)
    created_scene = narrative_store.create_scene(
        scene_id, chapter_id, 1, now
    )
    if isinstance(created_scene, Err):
        return Err(created_scene.error)
    plan_id = plan_id_for(chapter_id, 1)
    created_plan = narrative_store.create_plan(
        plan_id,
        chapter_id,
        1,
        goal=doc.what_presses_on_you,
        # the literary columns land empty: the plan CONTRACT carries no
        # literary-structure field (§6) — the situation document rides
        # the element below, and these columns are retired storage.
        dramatic_question="",
        planned_start_tick=context.current_tick,
        planned_end_tick=context.current_tick + _CHAPTER_TICK_HORIZON,
        closing_pressure="",
        desired_development="",
        soft_outcomes="",
        chapter_questions_to_advance="",
        scenes=(element,),
        now=now,
    )
    if isinstance(created_plan, Err):
        return Err(created_plan.error)
    adopted_plan = narrative_store.adopt_plan(
        plan_id, now, expected_state_version=created_plan.value.state_version
    )
    if isinstance(adopted_plan, Err):
        return Err(adopted_plan.error)
    return Ok(
        SituationOpening(
            chapter=chapter,
            plan=adopted_plan.value,
            scene=created_scene.value,
            fresh_plan=True,
        )
    )


def _element_of(
    doc: SituationPlan, *, player_id: str, tick: int
) -> dict[str, Any]:
    """The situation document as the plan row's one scene element — the
    canonical ten keys the dossier machinery derives (verbatim from the
    situation answers), the situation keys beside them (the verbatim
    pass-through the read face shares). The two POV-discipline keys land
    empty on purpose: the DS narration's limited-knowledge law rides the
    player's cognition / memory views (the spine's own context shape),
    never these V3 writer fields."""

    goals = "; ".join(
        f"{actor_id}: {goal}" for actor_id, goal in doc.protagonist_goals
    )
    element: dict[str, Any] = {
        "purpose": doc.what_presses_on_you,
        "place": doc.place,
        "pov_actor_id": player_id,
        "participants": [player_id]
        + [actor_id for actor_id, _goal in doc.protagonist_goals],
        "planned_start_tick": tick,
        "entry_goals": goals,
        "exit_condition": doc.open_question,
        "elasticity": doc.pacing,
        "revealable": "",
        "must_hide": "",
    }
    element.update(
        {
            "where_you_stand": doc.where_you_stand,
            "what_presses_on_you": doc.what_presses_on_you,
            "first_speaker": doc.first_speaker,
            "first_words": doc.first_words,
            "open_question": doc.open_question,
            "world_event_candidates": list(doc.world_event_candidates),
            "protagonist_goals": {
                actor_id: goal
                for actor_id, goal in doc.protagonist_goals
            },
            "pacing": doc.pacing,
            "settlement_expectation": doc.settlement_expectation,
        }
    )
    return element


def _last_place_of(conn: sqlite3.Connection, world_id: str) -> str:
    """The latest adopted dossier's place — the "where the world stands
    now" line the next chapter's plan context carries (a pure read; the
    honest empty string when nothing is adopted yet)."""

    row = conn.execute(
        "SELECT d.place FROM world_scene_dossier d"
        " JOIN world_scene s ON s.scene_id = d.scene_id"
        " JOIN world_chapter c ON c.chapter_id = s.chapter_id"
        " WHERE c.world_id = ? AND d.status = 'ADOPTED'"
        " ORDER BY c.chapter_index DESC, s.scene_index DESC,"
        " d.dossier_revision DESC LIMIT 1",
        (world_id,),
    ).fetchone()
    return "" if row is None or row[0] is None else str(row[0])
