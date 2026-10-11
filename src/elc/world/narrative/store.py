"""The Narrative V3 durable foundations (V3-1, DEC-OPI-bab4da9f…11/…16)
— :class:`SqliteNarrativeStore`, the SQL face of migration 0029's four
tables.

The cut ships **foundations only**: the lifecycle words, the Plan/Canon
boundary as physical tables, and the CAS discipline — no commit
transaction (SEGMENT / ACTION OUTCOME COMMIT are the later cuts',
RUNTIME_ARCHITECTURE §28), no passage / gate / action table, no
planning engine. Every transition method below is a *lifecycle flip*;
where a later cut's commit transaction must be the real mover (the
scene's ``COMMITTED`` flip, the actual tick columns) the docstring says
so plainly — the flip face exists so the state machine is testable and
so the commit cut has a named word to call inside its own short
transaction.

Discipline (the house store law, :mod:`elc.world.store`'s posture):

- **Value semantics** — every refusal is a ``Result`` ``Err``, never an
  exception: ``CONFLICT`` = a shape or uniqueness clash with an
  existing row (or a stale ``state_version``); ``NOT_FOUND`` = a
  referenced identity (world, chapter, scene) does not exist;
  ``VALIDATION_FAILED`` = the caller's own payload or move is malformed
  (an illegal lifecycle word); ``DEPENDENCY_UNAVAILABLE`` = the
  database itself failed outside the vocabulary above (the raw sqlite
  error rides the message). Messages are human sentences naming the row
  and the reason.
- **state_version CAS** — creation mints ``state_version = 1``; every
  lifecycle move takes the caller's ``expected_state_version`` and
  updates under ``WHERE ... state_version = ?``: a rowcount of zero
  means either the row is gone (``NOT_FOUND``) or another writer moved
  it first (``CONFLICT`` — re-read and retry is the caller's move).
  Every successful write bumps the counter.
- **Idempotent creation** — the same id replayed with the same shape
  answers the stored row unchanged (its own lifecycle word included:
  the create face never rewrites a word — the transition faces are the
  only writers of status); the same id with a different shape is a
  ``CONFLICT`` (plans do not rewrite).
- **No hidden clock** — every row's ``created_at`` / ``updated_at`` is
  stamped with the caller's ``now`` (the create/transition faces take
  it as a parameter); the store consults no clock of its own.
- **One short transaction per write** — ``BEGIN IMMEDIATE`` …
  ``COMMIT``/``ROLLBACK`` with the began-flag posture (a failed BEGIN
  owns nothing; a failing ROLLBACK of our own must not break the
  Result contract).

The two state machines (STATE_MACHINES §21 / §22, the illegal list §27
— every illegal move is refused with ``VALIDATION_FAILED``):

- Chapter: ``PLANNED → ACTIVE → SETTLING → CLOSED``. A world holds **at
  most one ACTIVE chapter** (MVP, §21's rule / §27's list — the second
  is refused); ``CLOSED`` never reopens (corrections go through later
  chapters, N-INV-003).
- Scene: ``PLANNED → ACTIVE → COMMITTED → CLOSED``, and ``DISCARDED``
  reachable **only from PLANNED** (§22: a scene a commit has touched is
  a happened thing — it can only close in the direction it actually
  went; §27's list spells the same).

The Plan face (§24, append-only): a plan/dossier revision is created
``PROPOSED`` and never rewritten; adopting moves ``PROPOSED →
ADOPTED`` and automatically supersedes the chapter's/scene's currently
``ADOPTED`` revision (``ADOPTED`` is unique per planned row — one
short transaction lands both words); rejecting moves ``PROPOSED →
REJECTED``. ``SUPERSEDED`` and ``REJECTED`` rows are history — nothing
moves them again.

**Plan/Canon isolation is structural**: this store is the only writer
of the four tables, and its canon reads (:meth:`get_chapter`,
:meth:`chapters_of`, :meth:`active_chapter`, :meth:`get_scene`,
:meth:`scenes_of`) query the two progress tables only — no method that
answers a canon-progress question touches ``world_chapter_plan`` or
``world_scene_dossier`` (N-INV-001 / N-R-INV-007: uncommitted Plan
content is never readable as fact). The Plan face's own reads
(:meth:`plans_of`, :meth:`adopted_plan`, :meth:`dossiers_of`,
:meth:`adopted_dossier`) are the planning face's, typed
:class:`~elc.world.narrative.types.PlanFaceRecord` on the record side —
the type distinction carries the boundary.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from elc.platform.db.epoch import RuntimeEpochFence
from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world.narrative.types import (
    ChapterStatus,
    PlanRevisionStatus,
    SceneStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneDossierRecord,
    WorldSceneRecord,
    decode_scenes,
    encode_scenes,
)
from elc.world.types import decode_participants, encode_participants

__all__ = ["SqliteNarrativeStore"]


class SqliteNarrativeStore:
    """Migration 0029's four narrative tables' write and read face.

    ``fence`` is the house constructor shape (every app.db store takes
    the shared epoch fence); migration 0029 carries no ``write_epoch``
    column, so the fence is held unused — the narrative rows are
    creator-stamped, not epoch-guarded (the 0023 posture).
    """

    def __init__(self, conn: sqlite3.Connection, fence: RuntimeEpochFence) -> None:
        self._conn = conn
        self._fence = fence

    # -- chapter face (canon progress) ----------------------------------------

    def create_chapter(
        self,
        chapter_id: str,
        world_id: str,
        chapter_index: int,
        now: str,
    ) -> Result[WorldChapterRecord]:
        """Create one chapter row, idempotently by id.

        The row mints ``PLANNED`` — the Blueprint is in (Plan face),
        the chapter has not opened (§21). A replay of the same id with
        the same shape (world, index) answers the stored row unchanged
        (its own status included); the same id with a different shape,
        or a different chapter already holding the world's
        ``chapter_index`` (the table's UNIQUE — the idempotency key
        set, DATA §26.2.4), is a ``CONFLICT``. A dangling ``world_id``
        is refused by the table's own FK and surfaces as ``NOT_FOUND``.
        """

        existing = self.get_chapter(chapter_id)
        if existing is not None:
            if (existing.world_id, existing.chapter_index) == (
                world_id,
                chapter_index,
            ):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"chapter {chapter_id!r} already exists with a"
                        " different shape; chapters do not rewrite"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_chapter ("
                " chapter_id, world_id, chapter_index, status,"
                " opened_at_tick, closed_at_tick, created_at, updated_at,"
                " state_version"
                ") VALUES (?, ?, ?, 'PLANNED', NULL, NULL, ?, ?, 1)",
                (chapter_id, world_id, chapter_index, now, now),
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
                    message=f"chapter {chapter_id!r} not created: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        created = self.get_chapter(chapter_id)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    def activate_chapter(
        self,
        chapter_id: str,
        opened_at_tick: int,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldChapterRecord]:
        """Open one chapter: ``PLANNED → ACTIVE`` (§21).

        Legal only from ``PLANNED`` — anything else (``ACTIVE`` again,
        ``SETTLING``, ``CLOSED``) is refused ``VALIDATION_FAILED``; a
        ``CLOSED`` chapter never reopens (§27's list). **A world holds
        at most one ACTIVE chapter** (MVP, §21's rule): if another
        chapter of the same world is already ``ACTIVE`` the move is
        refused before anything is written. (The twin check runs
        *outside* the CAS transaction — under Local V1's single-
        connection discipline the window is unreachable; the race-free
        form — the check inside the ``BEGIN IMMEDIATE``, or a partial
        UNIQUE index — is a **registered obligation for the commit cuts
        (V3-5/V3-6)**: the V3-1 review's MEDIUM.) ``opened_at_tick`` is
        the canon-face tick stamp — the caller's value (in the full
        pipeline the chapter opens as its first scene starts, and the
        value rides from the current actual tick); the CAS counter
        makes the move stale-safe.
        """

        row = self.get_chapter(chapter_id)
        if row is None:
            return self._missing("chapter", chapter_id)
        if row.status != ChapterStatus.PLANNED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter {chapter_id!r} is {row.status.value!r};"
                        " only a PLANNED chapter opens"
                    ),
                )
            )
        twin = self.active_chapter(row.world_id)
        if twin is not None and twin.chapter_id != chapter_id:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter {chapter_id!r} not opened: world"
                        f" {row.world_id!r} already holds an ACTIVE"
                        f" chapter ({twin.chapter_id!r}) — a world runs"
                        " one chapter at a time (MVP)"
                    ),
                )
            )
        moved = self._cas_update(
            "world_chapter",
            "chapter_id",
            chapter_id,
            "status = 'ACTIVE', opened_at_tick = ?",
            (opened_at_tick,),
            now,
            expected_state_version,
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_chapter(chapter_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def settle_chapter(
        self,
        chapter_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldChapterRecord]:
        """Begin the end-of-chapter settlement: ``ACTIVE → SETTLING``
        (§21 — the short window between the closing determination and
        the settlement's outputs landing). Legal only from ``ACTIVE``;
        a crash inside ``SETTLING`` is the recovery face's problem (a
        later cut's — re-running the settlement lands the same summary
        once), not this flip's.
        """

        row = self.get_chapter(chapter_id)
        if row is None:
            return self._missing("chapter", chapter_id)
        if row.status != ChapterStatus.ACTIVE:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter {chapter_id!r} is {row.status.value!r};"
                        " only an ACTIVE chapter starts settling"
                    ),
                )
            )
        moved = self._cas_status(
            "world_chapter",
            "chapter_id",
            chapter_id,
            ChapterStatus.SETTLING,
            now,
            expected_state_version,
            "chapter",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_chapter(chapter_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def close_chapter(
        self,
        chapter_id: str,
        closed_at_tick: int,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldChapterRecord]:
        """Finish the settlement: ``SETTLING → CLOSED`` (§21 — the
        settlement's outputs are all in; the chapter is done). Legal
        only from ``SETTLING`` — ``ACTIVE`` must pass through
        ``SETTLING`` first (the settlement is what closes a chapter),
        and a ``CLOSED`` chapter never reopens (§27's list).
        ``closed_at_tick`` is the canon-face tick stamp, the caller's
        value as :meth:`activate_chapter` spells.
        """

        row = self.get_chapter(chapter_id)
        if row is None:
            return self._missing("chapter", chapter_id)
        if row.status != ChapterStatus.SETTLING:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter {chapter_id!r} is {row.status.value!r};"
                        " only a SETTLING chapter closes (settlement"
                        " runs first)"
                    ),
                )
            )
        moved = self._cas_update(
            "world_chapter",
            "chapter_id",
            chapter_id,
            "status = 'CLOSED', closed_at_tick = ?",
            (closed_at_tick,),
            now,
            expected_state_version,
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_chapter(chapter_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def get_chapter(self, chapter_id: str) -> WorldChapterRecord | None:
        """One chapter row by id, or ``None`` (the pure column read —
        a missing id is an answer, not an error)."""

        row = self._conn.execute(
            "SELECT chapter_id, world_id, chapter_index, status,"
            " opened_at_tick, closed_at_tick, created_at, updated_at,"
            " state_version FROM world_chapter WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
        if row is None:
            return None
        return WorldChapterRecord(
            chapter_id=str(row[0]),
            world_id=str(row[1]),
            chapter_index=int(row[2]),
            status=ChapterStatus(str(row[3])),
            opened_at_tick=None if row[4] is None else int(row[4]),
            closed_at_tick=None if row[5] is None else int(row[5]),
            created_at=str(row[6]),
            updated_at=str(row[7]),
            state_version=int(row[8]),
        )

    def chapters_of(self, world_id: str) -> tuple[WorldChapterRecord, ...]:
        """One world's chapters, ``chapter_index`` ascending (the
        durable order — deterministic reads are content). Every
        lifecycle word rides out: history is rows, not errors."""

        rows = self._conn.execute(
            "SELECT chapter_id FROM world_chapter WHERE world_id = ?"
            " ORDER BY chapter_index ASC",
            (world_id,),
        ).fetchall()
        return tuple(
            chapter
            for chapter in (self.get_chapter(str(row[0])) for row in rows)
            if chapter is not None
        )

    def active_chapter(self, world_id: str) -> WorldChapterRecord | None:
        """The world's one ``ACTIVE`` chapter, or ``None`` — the read
        the single-ACTIVE enforcement and the pipeline's "where are we"
        both use (the store never assumes the invariant holds; it
        returns what is there)."""

        rows = self._conn.execute(
            "SELECT chapter_id FROM world_chapter"
            " WHERE world_id = ? AND status = 'ACTIVE'",
            (world_id,),
        ).fetchall()
        if not rows:
            return None
        chapter = self.get_chapter(str(rows[0][0]))
        assert chapter is not None  # selected from the same table
        return chapter

    # -- scene face (canon progress) ------------------------------------------

    def create_scene(
        self,
        scene_id: str,
        chapter_id: str,
        scene_index: int,
        now: str,
    ) -> Result[WorldSceneRecord]:
        """Create one scene row, idempotently by id.

        The row mints ``PLANNED`` (§22 — the Plan face planned it; the
        actual tick columns stay ``None`` until the scene's commits
        stamp them, STATE_MACHINES §26: the actual span is the commits',
        and V3-1 ships no commit). A replay of the same id with the same
        shape (chapter, index) answers the stored row unchanged; the
        same id with a different shape, or a different scene already
        holding the chapter's ``scene_index`` (the table's UNIQUE, DATA
        §26.2.4), is a ``CONFLICT``. A dangling ``chapter_id`` is
        refused by the table's own FK and surfaces as ``NOT_FOUND``.
        """

        existing = self.get_scene(scene_id)
        if existing is not None:
            if (existing.chapter_id, existing.scene_index) == (
                chapter_id,
                scene_index,
            ):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"scene {scene_id!r} already exists with a"
                        " different shape; scenes do not rewrite"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_scene ("
                " scene_id, chapter_id, scene_index, status,"
                " actual_start_tick, actual_end_tick, created_at,"
                " updated_at, state_version"
                ") VALUES (?, ?, ?, 'PLANNED', NULL, NULL, ?, ?, 1)",
                (scene_id, chapter_id, scene_index, now, now),
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
                    message=f"scene {scene_id!r} not created: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        created = self.get_scene(scene_id)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    def activate_scene(
        self,
        scene_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldSceneRecord]:
        """Begin the scene: ``PLANNED → ACTIVE`` (§22 — the Dossier is
        in, the passage segments start). Legal only from ``PLANNED``.
        The actual tick columns are deliberately not touched here: the
        scene's actual span is its commits' (§26), and the commit
        transactions are the later cuts' write face."""

        row = self.get_scene(scene_id)
        if row is None:
            return self._missing("scene", scene_id)
        if row.status != SceneStatus.PLANNED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} is {row.status.value!r};"
                        " only a PLANNED scene activates"
                    ),
                )
            )
        moved = self._cas_status(
            "world_scene",
            "scene_id",
            scene_id,
            SceneStatus.ACTIVE,
            now,
            expected_state_version,
            "scene",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_scene(scene_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def commit_scene(
        self,
        scene_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldSceneRecord]:
        """Mark the scene committed: ``ACTIVE → COMMITTED`` (§22).

        **This is the flip half of SCENE COMMIT, not the commit
        itself** — the SCENE COMMIT is the scene's last SEGMENT COMMIT
        (the alias law, STATE_MACHINES §22 / the disposition's M4), and
        the SEGMENT COMMIT transaction (passage + event + state + tick,
        NCP-3) is V3-5's. This face is the status word that transaction
        will call inside its own short transaction; the ``ACTIVE →
        COMMITTED`` flip and that commit land in the same transaction
        there. Legal only from ``ACTIVE`` — a committed scene's canon
        face is settled, and an earlier word cannot jump there.
        """

        row = self.get_scene(scene_id)
        if row is None:
            return self._missing("scene", scene_id)
        if row.status != SceneStatus.ACTIVE:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} is {row.status.value!r};"
                        " only an ACTIVE scene commits (the commit is"
                        " its last segment's, not a step of this face)"
                    ),
                )
            )
        moved = self._cas_status(
            "world_scene",
            "scene_id",
            scene_id,
            SceneStatus.COMMITTED,
            now,
            expected_state_version,
            "scene",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_scene(scene_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def close_scene(
        self,
        scene_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldSceneRecord]:
        """Close the scene: ``COMMITTED → CLOSED`` (§22 — the next
        scene's input package is built). Legal only from ``COMMITTED``;
        the ``CLOSED`` word is terminal in this machine (a closed scene
        never reopens, §27's list)."""

        row = self.get_scene(scene_id)
        if row is None:
            return self._missing("scene", scene_id)
        if row.status != SceneStatus.COMMITTED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} is {row.status.value!r};"
                        " only a COMMITTED scene closes"
                    ),
                )
            )
        moved = self._cas_status(
            "world_scene",
            "scene_id",
            scene_id,
            SceneStatus.CLOSED,
            now,
            expected_state_version,
            "scene",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_scene(scene_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def discard_scene(
        self,
        scene_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldSceneRecord]:
        """Retire a never-opened scene: ``PLANNED → DISCARDED`` (§22 —
        a replanning made the scene moot before it ever happened).

        **Reachable only from ``PLANNED``**: an ``ACTIVE`` scene has
        the Dossier's writing under way, and a ``COMMITTED`` scene has
        canon on the ground — neither can be un-happened (§22's rule;
        §27's 「有已 commit 段落的 scene → DISCARDED」 is the committed
        end of the same refusal). A ``CLOSED`` or already-``DISCARDED``
        scene is likewise refused — the words after ``PLANNED`` are all
        happened things.
        """

        row = self.get_scene(scene_id)
        if row is None:
            return self._missing("scene", scene_id)
        if row.status != SceneStatus.PLANNED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} is {row.status.value!r};"
                        " only a PLANNED scene is discarded (a scene"
                        " the world has touched is a happened thing)"
                    ),
                )
            )
        moved = self._cas_status(
            "world_scene",
            "scene_id",
            scene_id,
            SceneStatus.DISCARDED,
            now,
            expected_state_version,
            "scene",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_scene(scene_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def get_scene(self, scene_id: str) -> WorldSceneRecord | None:
        """One scene row by id, or ``None`` (the pure column read)."""

        row = self._conn.execute(
            "SELECT scene_id, chapter_id, scene_index, status,"
            " actual_start_tick, actual_end_tick, created_at, updated_at,"
            " state_version FROM world_scene WHERE scene_id = ?",
            (scene_id,),
        ).fetchone()
        if row is None:
            return None
        return WorldSceneRecord(
            scene_id=str(row[0]),
            chapter_id=str(row[1]),
            scene_index=int(row[2]),
            status=SceneStatus(str(row[3])),
            actual_start_tick=None if row[4] is None else int(row[4]),
            actual_end_tick=None if row[5] is None else int(row[5]),
            created_at=str(row[6]),
            updated_at=str(row[7]),
            state_version=int(row[8]),
        )

    def scenes_of(self, chapter_id: str) -> tuple[WorldSceneRecord, ...]:
        """One chapter's scenes, ``scene_index`` ascending (the durable
        order). Every lifecycle word rides out — a discarded scene is
        the Plan's history, not an error."""

        rows = self._conn.execute(
            "SELECT scene_id FROM world_scene WHERE chapter_id = ?"
            " ORDER BY scene_index ASC",
            (chapter_id,),
        ).fetchall()
        return tuple(
            scene
            for scene in (self.get_scene(str(row[0])) for row in rows)
            if scene is not None
        )

    # -- chapter plan face (PLAN, append-only) --------------------------------

    def create_plan(
        self,
        chapter_plan_id: str,
        chapter_id: str,
        plan_revision: int,
        goal: str,
        dramatic_question: str,
        planned_start_tick: int,
        planned_end_tick: int,
        closing_pressure: str,
        desired_development: str,
        soft_outcomes: str,
        chapter_questions_to_advance: str,
        scenes: tuple[dict[str, Any], ...],
        now: str,
    ) -> Result[WorldChapterPlanRecord]:
        """Create one chapter-plan revision, idempotently by id.

        The revision mints ``PROPOSED`` (§24 — the Director produced
        it; adoption is a separate, explicit move). The Blueprint's
        semantic fields ride verbatim (DATA §26.2.1); ``scenes`` is the
        scene table, frozen by :func:`encode_scenes`'s deterministic
        law. A replay of the same id with the same shape answers the
        stored row unchanged (its own revision status included); the
        same id with a different shape, or another revision already
        holding the chapter's ``plan_revision`` (the table's UNIQUE,
        DATA §26.2.4), is a ``CONFLICT`` — plans are append-only and
        never rewritten. A dangling ``chapter_id`` surfaces as
        ``NOT_FOUND`` through the table's own FK.
        """

        encoded_scenes = encode_scenes(scenes)
        existing = self.get_plan(chapter_plan_id)
        if existing is not None:
            if (
                existing.chapter_id,
                existing.plan_revision,
                existing.goal,
                existing.dramatic_question,
                existing.planned_start_tick,
                existing.planned_end_tick,
                existing.closing_pressure,
                existing.desired_development,
                existing.soft_outcomes,
                existing.chapter_questions_to_advance,
                encode_scenes(existing.scenes),
            ) == (
                chapter_id,
                plan_revision,
                goal,
                dramatic_question,
                planned_start_tick,
                planned_end_tick,
                closing_pressure,
                desired_development,
                soft_outcomes,
                chapter_questions_to_advance,
                encoded_scenes,
            ):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"chapter plan {chapter_plan_id!r} already exists"
                        " with a different shape; plan revisions are"
                        " append-only and do not rewrite"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_chapter_plan ("
                " chapter_plan_id, chapter_id, plan_revision, status,"
                " goal, dramatic_question, planned_start_tick,"
                " planned_end_tick, closing_pressure, desired_development,"
                " soft_outcomes, chapter_questions_to_advance, scenes,"
                " created_at, updated_at, state_version"
                ") VALUES (?, ?, ?, 'PROPOSED', ?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?, ?, 1)",
                (
                    chapter_plan_id,
                    chapter_id,
                    plan_revision,
                    goal,
                    dramatic_question,
                    planned_start_tick,
                    planned_end_tick,
                    closing_pressure,
                    desired_development,
                    soft_outcomes,
                    chapter_questions_to_advance,
                    encoded_scenes,
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
            return Err(
                DomainError(
                    code=self._refusal_code(exc),
                    message=(
                        f"chapter plan {chapter_plan_id!r} not created:"
                        f" {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        created = self.get_plan(chapter_plan_id)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    def adopt_plan(
        self,
        chapter_plan_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldChapterPlanRecord]:
        """Adopt one chapter-plan revision: ``PROPOSED → ADOPTED`` (§24
        — it becomes the current plan).

        Legal only from ``PROPOSED`` (``SUPERSEDED`` / ``REJECTED`` are
        history — nothing adopts them again). The chapter's currently
        ``ADOPTED`` revision (if any) is automatically superseded in
        the **same short transaction** — ``ADOPTED`` is unique per
        chapter, and the two words land together or not at all. The
        superseded row's ``state_version`` bumps too (every write
        counts).
        """

        row = self.get_plan(chapter_plan_id)
        if row is None:
            return self._missing("chapter plan", chapter_plan_id)
        if row.status != PlanRevisionStatus.PROPOSED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter plan {chapter_plan_id!r} is"
                        f" {row.status.value!r}; only a PROPOSED revision"
                        " is adopted"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            cursor = self._conn.execute(
                "UPDATE world_chapter_plan SET status = 'ADOPTED',"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE chapter_plan_id = ? AND state_version = ?",
                (now, chapter_plan_id, expected_state_version),
            )
            if cursor.rowcount != 1:
                self._conn.execute("ROLLBACK")
                began = False
                return self._cas_miss("world_chapter_plan", chapter_plan_id)
            self._conn.execute(
                "UPDATE world_chapter_plan SET status = 'SUPERSEDED',"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE chapter_id = ? AND status = 'ADOPTED'"
                " AND chapter_plan_id != ?",
                (now, row.chapter_id, chapter_plan_id),
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
                    message=(
                        f"chapter plan {chapter_plan_id!r} not adopted:"
                        f" {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        adopted = self.get_plan(chapter_plan_id)
        assert adopted is not None  # the UPDATE above just touched it
        return Ok(adopted)

    def reject_plan(
        self,
        chapter_plan_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldChapterPlanRecord]:
        """Explicitly veto one chapter-plan revision: ``PROPOSED →
        REJECTED`` (§24 — the reason is the caller's record to keep;
        this face records the word). Legal only from ``PROPOSED``; a
        rejected revision is history."""

        row = self.get_plan(chapter_plan_id)
        if row is None:
            return self._missing("chapter plan", chapter_plan_id)
        if row.status != PlanRevisionStatus.PROPOSED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"chapter plan {chapter_plan_id!r} is"
                        f" {row.status.value!r}; only a PROPOSED revision"
                        " is rejected"
                    ),
                )
            )
        moved = self._cas_status(
            "world_chapter_plan",
            "chapter_plan_id",
            chapter_plan_id,
            PlanRevisionStatus.REJECTED,
            now,
            expected_state_version,
            "chapter plan",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_plan(chapter_plan_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def get_plan(self, chapter_plan_id: str) -> WorldChapterPlanRecord | None:
        """One chapter-plan revision by id, or ``None``."""

        row = self._conn.execute(
            "SELECT chapter_plan_id, chapter_id, plan_revision, status,"
            " goal, dramatic_question, planned_start_tick,"
            " planned_end_tick, closing_pressure, desired_development,"
            " soft_outcomes, chapter_questions_to_advance, scenes,"
            " created_at, updated_at, state_version"
            " FROM world_chapter_plan WHERE chapter_plan_id = ?",
            (chapter_plan_id,),
        ).fetchone()
        if row is None:
            return None
        decoded = decode_scenes(str(row[12]))
        if isinstance(decoded, Err):
            # The column is this store's own encoder's output; a payload
            # it cannot decode is a corrupted row, surfaced honestly.
            raise ValueError(
                f"chapter plan {chapter_plan_id!r} carries an"
                f" undecodable scenes column: {decoded.error.message}"
            )
        return WorldChapterPlanRecord(
            chapter_plan_id=str(row[0]),
            chapter_id=str(row[1]),
            plan_revision=int(row[2]),
            status=PlanRevisionStatus(str(row[3])),
            goal=str(row[4]),
            dramatic_question=str(row[5]),
            planned_start_tick=int(row[6]),
            planned_end_tick=int(row[7]),
            closing_pressure=str(row[8]),
            desired_development=str(row[9]),
            soft_outcomes=str(row[10]),
            chapter_questions_to_advance=str(row[11]),
            scenes=decoded.value,
            created_at=str(row[13]),
            updated_at=str(row[14]),
            state_version=int(row[15]),
        )

    def plans_of(
        self, chapter_id: str
    ) -> tuple[WorldChapterPlanRecord, ...]:
        """One chapter's plan revisions, ``plan_revision`` ascending —
        the Plan face's history, every revision word riding out (the
        read never filters; :meth:`adopted_plan` is the current-plan
        read)."""

        rows = self._conn.execute(
            "SELECT chapter_plan_id FROM world_chapter_plan"
            " WHERE chapter_id = ? ORDER BY plan_revision ASC",
            (chapter_id,),
        ).fetchall()
        return tuple(
            plan
            for plan in (self.get_plan(str(row[0])) for row in rows)
            if plan is not None
        )

    def adopted_plan(self, chapter_id: str) -> WorldChapterPlanRecord | None:
        """The chapter's current plan — its one ``ADOPTED`` revision —
        or ``None`` while nothing is adopted (a ``PLANNED`` chapter
        with no adopted Blueprint is exactly that: planned-in-name,
        waiting for its Blueprint adoption)."""

        rows = self._conn.execute(
            "SELECT chapter_plan_id FROM world_chapter_plan"
            " WHERE chapter_id = ? AND status = 'ADOPTED'",
            (chapter_id,),
        ).fetchall()
        if not rows:
            return None
        plan = self.get_plan(str(rows[0][0]))
        assert plan is not None  # selected from the same table
        return plan

    # -- scene dossier face (PLAN, append-only) -------------------------------

    def create_dossier(
        self,
        dossier_id: str,
        scene_id: str,
        dossier_revision: int,
        pov_actor_id: str,
        participants: tuple[str, ...],
        place: str,
        planned_start_tick: int,
        revealable: str,
        must_hide: str,
        entry_goals: str,
        exit_condition: str,
        elasticity: str,
        now: str,
    ) -> Result[WorldSceneDossierRecord]:
        """Create one scene-dossier revision, idempotently by id.

        The revision mints ``PROPOSED`` (§24 — the Scene Planner's
        instant re-planning of the Blueprint). ``participants`` is the
        participant namespace, frozen by the world types' strict-JSON
        participants codec (the C1-a law: the same tuple always encodes
        to the same bytes). A replay of the same id with the same shape
        answers the stored row unchanged; the same id with a different
        shape, or another revision already holding the scene's
        ``dossier_revision`` (the table's UNIQUE, DATA §26.2.4), is a
        ``CONFLICT``. A dangling ``scene_id`` surfaces as ``NOT_FOUND``
        through the table's own FK.
        """

        encoded_participants = encode_participants(participants)
        existing = self.get_dossier(dossier_id)
        if existing is not None:
            if (
                existing.scene_id,
                existing.dossier_revision,
                existing.pov_actor_id,
                existing.participants,
                existing.place,
                existing.planned_start_tick,
                existing.revealable,
                existing.must_hide,
                existing.entry_goals,
                existing.exit_condition,
                existing.elasticity,
            ) == (
                scene_id,
                dossier_revision,
                pov_actor_id,
                participants,
                place,
                planned_start_tick,
                revealable,
                must_hide,
                entry_goals,
                exit_condition,
                elasticity,
            ):
                return Ok(existing)
            return Err(
                DomainError(
                    code=DomainErrorCode.CONFLICT,
                    message=(
                        f"scene dossier {dossier_id!r} already exists"
                        " with a different shape; dossier revisions are"
                        " append-only and do not rewrite"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            self._conn.execute(
                "INSERT INTO world_scene_dossier ("
                " dossier_id, scene_id, dossier_revision, status,"
                " pov_actor_id, participants, place, planned_start_tick,"
                " revealable, must_hide, entry_goals, exit_condition,"
                " elasticity, created_at, updated_at, state_version"
                ") VALUES (?, ?, ?, 'PROPOSED', ?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?, ?, 1)",
                (
                    dossier_id,
                    scene_id,
                    dossier_revision,
                    pov_actor_id,
                    encoded_participants,
                    place,
                    planned_start_tick,
                    revealable,
                    must_hide,
                    entry_goals,
                    exit_condition,
                    elasticity,
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
            return Err(
                DomainError(
                    code=self._refusal_code(exc),
                    message=(
                        f"scene dossier {dossier_id!r} not created: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        created = self.get_dossier(dossier_id)
        assert created is not None  # the INSERT above just landed it
        return Ok(created)

    def adopt_dossier(
        self,
        dossier_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldSceneDossierRecord]:
        """Adopt one scene-dossier revision: ``PROPOSED → ADOPTED``
        (§24) — the same law :meth:`adopt_plan` spells: legal only from
        ``PROPOSED``, the scene's currently ``ADOPTED`` revision
        superseded in the same short transaction (``ADOPTED`` unique
        per scene), every write bumping its counter."""

        row = self.get_dossier(dossier_id)
        if row is None:
            return self._missing("scene dossier", dossier_id)
        if row.status != PlanRevisionStatus.PROPOSED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene dossier {dossier_id!r} is"
                        f" {row.status.value!r}; only a PROPOSED revision"
                        " is adopted"
                    ),
                )
            )
        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            cursor = self._conn.execute(
                "UPDATE world_scene_dossier SET status = 'ADOPTED',"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE dossier_id = ? AND state_version = ?",
                (now, dossier_id, expected_state_version),
            )
            if cursor.rowcount != 1:
                self._conn.execute("ROLLBACK")
                began = False
                return self._cas_miss("world_scene_dossier", dossier_id)
            self._conn.execute(
                "UPDATE world_scene_dossier SET status = 'SUPERSEDED',"
                " state_version = state_version + 1, updated_at = ?"
                " WHERE scene_id = ? AND status = 'ADOPTED'"
                " AND dossier_id != ?",
                (now, row.scene_id, dossier_id),
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
                    message=(
                        f"scene dossier {dossier_id!r} not adopted: {exc}"
                    ),
                )
            )
        self._conn.execute("COMMIT")
        adopted = self.get_dossier(dossier_id)
        assert adopted is not None  # the UPDATE above just touched it
        return Ok(adopted)

    def reject_dossier(
        self,
        dossier_id: str,
        now: str,
        expected_state_version: int,
    ) -> Result[WorldSceneDossierRecord]:
        """Explicitly veto one scene-dossier revision: ``PROPOSED →
        REJECTED`` (§24) — the same law :meth:`reject_plan` spells."""

        row = self.get_dossier(dossier_id)
        if row is None:
            return self._missing("scene dossier", dossier_id)
        if row.status != PlanRevisionStatus.PROPOSED:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene dossier {dossier_id!r} is"
                        f" {row.status.value!r}; only a PROPOSED revision"
                        " is rejected"
                    ),
                )
            )
        moved = self._cas_status(
            "world_scene_dossier",
            "dossier_id",
            dossier_id,
            PlanRevisionStatus.REJECTED,
            now,
            expected_state_version,
            "scene dossier",
        )
        if isinstance(moved, Err):
            return Err(moved.error)
        updated = self.get_dossier(dossier_id)
        assert updated is not None  # the UPDATE above just touched it
        return Ok(updated)

    def get_dossier(self, dossier_id: str) -> WorldSceneDossierRecord | None:
        """One scene-dossier revision by id, or ``None``."""

        row = self._conn.execute(
            "SELECT dossier_id, scene_id, dossier_revision, status,"
            " pov_actor_id, participants, place, planned_start_tick,"
            " revealable, must_hide, entry_goals, exit_condition,"
            " elasticity, created_at, updated_at, state_version"
            " FROM world_scene_dossier WHERE dossier_id = ?",
            (dossier_id,),
        ).fetchone()
        if row is None:
            return None
        decoded = decode_participants(str(row[5]))
        if isinstance(decoded, Err):
            raise ValueError(
                f"scene dossier {dossier_id!r} carries an undecodable"
                f" participants column: {decoded.error.message}"
            )
        return WorldSceneDossierRecord(
            dossier_id=str(row[0]),
            scene_id=str(row[1]),
            dossier_revision=int(row[2]),
            status=PlanRevisionStatus(str(row[3])),
            pov_actor_id=str(row[4]),
            participants=decoded.value,
            place=str(row[6]),
            planned_start_tick=int(row[7]),
            revealable=str(row[8]),
            must_hide=str(row[9]),
            entry_goals=str(row[10]),
            exit_condition=str(row[11]),
            elasticity=str(row[12]),
            created_at=str(row[13]),
            updated_at=str(row[14]),
            state_version=int(row[15]),
        )

    def dossiers_of(
        self, scene_id: str
    ) -> tuple[WorldSceneDossierRecord, ...]:
        """One scene's dossier revisions, ``dossier_revision``
        ascending — the Plan face's history
        (:meth:`adopted_dossier` is the current-plan read)."""

        rows = self._conn.execute(
            "SELECT dossier_id FROM world_scene_dossier"
            " WHERE scene_id = ? ORDER BY dossier_revision ASC",
            (scene_id,),
        ).fetchall()
        return tuple(
            dossier
            for dossier in (self.get_dossier(str(row[0])) for row in rows)
            if dossier is not None
        )

    def adopted_dossier(self, scene_id: str) -> WorldSceneDossierRecord | None:
        """The scene's current dossier — its one ``ADOPTED`` revision —
        or ``None`` while nothing is adopted."""

        rows = self._conn.execute(
            "SELECT dossier_id FROM world_scene_dossier"
            " WHERE scene_id = ? AND status = 'ADOPTED'",
            (scene_id,),
        ).fetchall()
        if not rows:
            return None
        dossier = self.get_dossier(str(rows[0][0]))
        assert dossier is not None  # selected from the same table
        return dossier

    # -- shared machinery -------------------------------------------------------

    def _cas_status(
        self,
        table: str,
        id_column: str,
        row_id: str,
        target: ChapterStatus | SceneStatus | PlanRevisionStatus,
        now: str,
        expected_state_version: int,
        noun: str,
    ) -> Result[None]:
        """The one-word CAS flip every simple transition rides: move
        ``status`` to ``target`` under the version guard, bump the
        counter, stamp the caller's ``updated_at``. A version miss is
        ``CONFLICT`` (or ``NOT_FOUND`` if the row vanished between the
        read and the write — the caller re-reads either way)."""

        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            cursor = self._conn.execute(
                f"UPDATE {table} SET status = ?,"
                " state_version = state_version + 1, updated_at = ?"
                f" WHERE {id_column} = ? AND state_version = ?",
                (target.value, now, row_id, expected_state_version),
            )
            if cursor.rowcount != 1:
                self._conn.execute("ROLLBACK")
                began = False
                return self._cas_miss(table, row_id)
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"{noun} {row_id!r} not moved: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(None)

    def _cas_update(
        self,
        table: str,
        id_column: str,
        row_id: str,
        assignments: str,
        params: tuple[Any, ...],
        now: str,
        expected_state_version: int,
    ) -> Result[None]:
        """The CAS flip with extra assignments (the tick stamps) —
        same guard, same counter bump, same miss vocabulary."""

        began = False
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            began = True
            cursor = self._conn.execute(
                f"UPDATE {table} SET {assignments},"
                " state_version = state_version + 1, updated_at = ?"
                f" WHERE {id_column} = ? AND state_version = ?",
                (*params, now, row_id, expected_state_version),
            )
            if cursor.rowcount != 1:
                self._conn.execute("ROLLBACK")
                began = False
                return self._cas_miss(table, row_id)
        except sqlite3.Error as exc:
            if began:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            return Err(
                DomainError(
                    code=DomainErrorCode.DEPENDENCY_UNAVAILABLE,
                    message=f"{table} row {row_id!r} not moved: {exc}",
                )
            )
        self._conn.execute("COMMIT")
        return Ok(None)

    def _cas_miss(self, table: str, row_id: str) -> Err[Any]:
        """The CAS miss's two honest answers: the row is gone
        (``NOT_FOUND``) or another writer moved it first
        (``CONFLICT``)."""

        present = self._row_version(table, row_id)
        if present is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"{table} row {row_id!r} not moved: it does not"
                        " exist"
                    ),
                )
            )
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    f"{table} row {row_id!r} not moved: another writer"
                    " moved it first (its state_version is now"
                    f" {present}; the expected one is stale) — re-read"
                    " and retry"
                ),
            )
        )

    def _row_version(self, table: str, row_id: str) -> int | None:
        """The row's current ``state_version``, or ``None`` — the CAS
        miss's disambiguator. ``table``/``row_id`` ride only from this
        store's own closed call sites (no caller input reaches the
        f-string)."""

        id_column = {
            "world_chapter": "chapter_id",
            "world_scene": "scene_id",
            "world_chapter_plan": "chapter_plan_id",
            "world_scene_dossier": "dossier_id",
        }[table]
        row = self._conn.execute(
            f"SELECT state_version FROM {table} WHERE {id_column} = ?",
            (row_id,),
        ).fetchone()
        return None if row is None else int(row[0])

    def _missing(self, noun: str, row_id: str) -> Err[Any]:
        """The dangling-reference refusal, as a human sentence."""

        return Err(
            DomainError(
                code=DomainErrorCode.NOT_FOUND,
                message=(
                    f"{noun} {row_id!r} not moved: it does not exist"
                ),
            )
        )

    @staticmethod
    def _refusal_code(exc: sqlite3.Error) -> DomainErrorCode:
        """Map the database's own refusal to the store's vocabulary: a
        UNIQUE clash is a ``CONFLICT`` (the identities exist, the
        shapes collide); a FOREIGN KEY refusal is ``NOT_FOUND`` (a
        referenced identity is missing) — the world store's mapping,
        spelled the same here."""

        text = str(exc)
        if "UNIQUE constraint failed" in text:
            return DomainErrorCode.CONFLICT
        return DomainErrorCode.NOT_FOUND
