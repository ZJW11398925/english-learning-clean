"""The Narrative V3 pipeline orchestrator (V3-8a, TASK-OPI-06b954e0…4 /
the opening ruling ``DEC-OPI-06b954e0-…2``; RA §27's "编排面" paragraph;
DOMAIN §20.2's first row; **V3-8b**: the CHAPTER arm's production
returns to the Director provider (HIGH-3), the continuation obligation
of a committed-unclosed gate is driven from durable state (the HARD
GATE) and the external starting-sequence state is gone). — the
deterministic drive of the chapter / scene / settlement loop, calling
the library faces in the RA §27 order.

**Zero write power, no transaction of its own** (the contract's
sentence: 编排器是「谁在何时调用谁」的驱动器，不是第二个 authority):
every write in this module lands inside the called library face's own
short transaction — ``Director.open_next_chapter`` /
``ScenePlanner.open_scene`` / ``PovWriter.write_segment`` (NCP-3) /
``open_gate`` / ``submit_gate`` (NCP-1) / ``begin_resolving`` /
``commit_action`` (NCP-2) / ``ScenePlanner.replan_scene`` /
``Director.apply_action_replan`` / Chapter Settlement (NCP-4). The
orchestrator spells **no SQL** and opens no ``BEGIN`` (N-R-INV-004's
"两套提交全或无" is the commits' own, unchanged). Every step is an
idempotent library call, so re-driving the same call after a crash is a
replay, not a second story (the replay arms answer first — the same
``segment_key``, the same NCP-1 pair, the same ``action_commit_key``).

**The drive order** (RA §27's diagram, executable):

- :meth:`Pipeline.open_chapter` — the Director's Plan-face act on the
  caller's Blueprint payload; :meth:`Pipeline.plan_chapter` — the same
  act with the payload **produced by the DirectorProvider** from the
  full ``DirectorContext`` (V3-8b's initial arm; the chapter-level plan
  is the world's, never a POV-limited planner's);
- :meth:`Pipeline.run_scene` — ``open_scene`` (dossier rev 1 from the
  adopted Blueprint element, scene ``ACTIVE``; an ``ACTIVE`` scene is
  continued from its durable rows — the crash mid-drive replays its
  committed beats and writes on) → for each :class:`SegmentBeat`: compile
  the POV-safe input
  (:func:`elc.world.providers.pov_context_of`, the V3-5R hard door's
  physical form), ask the Writer provider for the prose, hand it to
  ``PovWriter.write_segment`` (guards + SEGMENT COMMIT); for each
  :class:`GateBeat`: ``open_gate`` → ``submit_gate`` (NCP-1) →
  ``begin_resolving`` → ask the Resolver provider for the
  ``Adjudication`` → ``commit_action`` (NCP-2) → **auto-route the
  ruling's ``replan_scope``** through the durable obligation
  (``replan_scene`` / ``apply_action_replan``, claim → work → complete);
  the segment that follows a committed ruling carries its
  ``outcome_ref`` (the V3-6R chain — the orchestrator names the ruling
  the continuation resumes, never the caller);
- :meth:`Pipeline.settle` — the store's ``ACTIVE → SETTLING`` flip
  (when the chapter is still ``ACTIVE``; the flip itself judges the
  SETTLING precondition — no ``ACTIVE`` scene, no open gate, no
  ``PENDING`` obligation, V3-8b's HIGH-1) then NCP-4's
  ``settle_chapter``;
- :meth:`Pipeline.resume` — **the crash-resume face**: read
  ``recovery_scan``'s seven families, filter them to the named world and
  route — ``ANSWERED`` / ``RESOLVING`` gates re-adjudicate with the
  **same ``submission_id``** (the durable anchor: one outcome, never
  two), ``PENDING`` obligations consume through their scope's face,
  ``COMMITTED``-unclosed gates with no continuation passage get their
  **first continuation segment driven from durable state** (V3-8b's
  HARD GATE: the sequence derives from the ``segment_commit`` rows, the
  committed action rides as the forced ``outcome_ref`` and the gate
  closes in that same commit — the caller re-supplies nothing),
  ``SETTLING`` chapters settle to ``CLOSED``. ``ACTIVE`` scenes are read
  and reported, not routed — a scene the continuation above did not
  touch is the caller's to drive, and nothing durable is broken by
  waiting.

**The script law (V3-8b)**: a drive's beats are the scene's own script
— the i-th :class:`SegmentBeat` is the scene's i-th segment — so a
re-drive of the same script replays its committed segments positionally
and no externally-supplied starting sequence exists: the V3-8a
``first_segment_seq`` state is gone (the contract's 「取消/降级外部
``first_segment_seq`` 状态」). A mid-scene continuation derives its
``segment_seq`` from the durable ``segment_commit`` rows — the recovery
scan's own derivation, consumed by :meth:`Pipeline.resume` — never from
in-process memory.

**The deterministic baseline, stated honestly**: the prose, the plan
content, the Blueprints and the verdicts come from the provider
protocols (:mod:`elc.world.providers`) — scripted in CI. The
orchestrator's value is the **drive order and the recovery routing**,
not literary quality; the real LLM wiring **landed in V3-8c**
(``elc/world/llm_providers.py`` — the four faces over the
``TextCompletion`` seam; the persona BYOK egress adapts onto that seam
at the assembly face) and the fake stays behind the same Protocols as
the CI baseline.

**The caller supplies what is the caller's**: the Beat script and the
user's own submission, ``action_duration_ticks`` (the one calibration
the ruling's story-time cost rides until the LLM resolver judges it —
one value for this pipeline instance, so a crash retry replays the
ruling's shape byte for byte) and a ``now`` on every call (no hidden
clock).

Discipline: value semantics — every refusal rides the library faces'
``Result`` ``Err`` out unchanged; no SQL string building (this module
spells no SQL at all); the Package is not consulted (the durable rows
are the runtime authority).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from elc.platform.types import (
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    Result,
)
from elc.world import settlement as settlement_faces
from elc.world.action import (
    ActionOutcome,
    ActionStatus,
    ReplanScope,
    ReplanStatus,
    UserActionRecord,
    UserGateRecord,
    action_by_id,
    action_of,
    begin_resolving,
    commit_action,
    get_gate,
    open_gate,
    recovery_scan,
    replan_obligation,
    replan_request_id_for,
    scene_of_action,
    submit_gate,
)
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.cognition import v3_cognition_view
from elc.world.director import ChapterOpening, Director
from elc.world.memory import v3_memory_view
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    SceneStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneDossierRecord,
)
from elc.world.providers import (
    DirectorPlanContext,
    DirectorProvider,
    PlannerProvider,
    ResolverContext,
    ResolverProvider,
    ScenePlanContext,
    WriterProvider,
    pov_context_of,
)
from elc.world.scene import SceneContext, SceneOpening, ScenePlanner
from elc.world.settlement import ChapterSettlementRecord, CommitOutcome
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.writer import PovWriter

__all__ = [
    "GateBeat",
    "Pipeline",
    "RecoveryRun",
    "ReplanConsumption",
    "SceneRun",
    "SegmentBeat",
]


@dataclass(frozen=True)
class SegmentBeat:
    """One segment the drive writes: the Writer provider produces the
    prose; the length, the language and the terminality are the
    driver's (the LLM planner's seat in a later wiring — the RA §27
    diagram's 「POV Writer：正文段」 edge)."""

    language: str = "en"
    duration_ticks: int = 1
    is_last_segment: bool = False


@dataclass(frozen=True)
class GateBeat:
    """One user-will stop the drive handles (the RA §27 diagram's
    「遇到用户意志点」 edge): ``gate_seq`` names the gate's derived
    identity (``f"{scene_id}-g{gate_seq:02d}"``), ``options`` are the
    2–4 natural behaviour options, and the **user's own submission**
    (``submission_id`` / ``intent_text`` / ``selected_option``) rides
    here — the user is the caller's, never a provider's."""

    gate_seq: int
    options: tuple[str, ...]
    submission_id: str
    intent_text: str
    selected_option: str | None = None


@dataclass(frozen=True)
class ReplanConsumption:
    """One ruling's ``replan_scope`` verdict as it was consumed through
    the durable obligation: the request id, the scope word and the
    claimed target revision (``dossier_id`` for ``SCENE``,
    ``chapter_plan_id`` for ``CHAPTER``)."""

    replan_request_id: str
    scope: ReplanScope
    target_ref: str


@dataclass(frozen=True)
class SceneRun:
    """One :meth:`Pipeline.run_scene` drive's answer: the opening (the
    activated scene, the adopted dossier, the element, the POV
    context), every segment this drive wrote (the commit outcomes), the
    gates it handled (their rows **re-read at the end** — a gate a
    later segment resumed past stands ``CLOSED``), the rulings
    (``ActionOutcome``) and the replans the verdicts auto-routed."""

    opening: SceneOpening
    segments: tuple[CommitOutcome, ...]
    gates: tuple[UserGateRecord, ...]
    actions: tuple[ActionOutcome, ...]
    replans: tuple[ReplanConsumption, ...]


@dataclass(frozen=True)
class RecoveryRun:
    """One :meth:`Pipeline.resume` walk's answer for one world: the
    gates re-adjudicated and committed (the scan's own ``gate_id``
    order), the obligations consumed, the continuations driven
    (V3-8b's HARD GATE: the ``gate_id``s whose first continuation
    passage landed — each one closed its gate in that same commit), the
    chapters settled, and the ``ACTIVE`` scenes the walk read and **did
    not** route (an interrupted scene is continued by the caller's next
    drive — nothing durable is broken by waiting)."""

    world_id: str
    gates_committed: tuple[str, ...]
    replans_consumed: tuple[ReplanConsumption, ...]
    continuations_driven: tuple[str, ...]
    chapters_settled: tuple[str, ...]
    active_scene_ids: tuple[str, ...]


class Pipeline:
    """The Narrative V3 drive over one database — constructed with the
    connection, the same connection's stores and the four provider
    protocols; it builds the library faces (Director / ScenePlanner /
    PovWriter) from those stores itself and holds no other state.

    ``action_duration_ticks`` is the deterministic baseline's one
    calibration: the story-time cost NCP-2 advances for a ruling (the
    LLM resolver judging its own duration is the later wiring). One
    value for the instance keeps a crash retry's replay shape equal —
    the ruling's ``duration_ticks`` rides the replay comparison.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        world_store: SqliteWorldStore,
        cast_store: SqliteCastStore,
        bible_store: SqliteBibleStore,
        narrative_store: SqliteNarrativeStore,
        writer_provider: WriterProvider,
        planner_provider: PlannerProvider,
        director_provider: DirectorProvider,
        resolver_provider: ResolverProvider,
        action_duration_ticks: int,
    ) -> None:
        self._conn = conn
        self._worlds = world_store
        self._cast = cast_store
        self._bibles = bible_store
        self._narrative = narrative_store
        self._writer_provider = writer_provider
        self._planner_provider = planner_provider
        self._director_provider = director_provider
        self._resolver_provider = resolver_provider
        self._action_duration_ticks = action_duration_ticks
        self._director = Director(
            conn,
            world_store=world_store,
            cast_store=cast_store,
            bible_store=bible_store,
            narrative_store=narrative_store,
        )
        self._planner = ScenePlanner(
            conn,
            world_store=world_store,
            cast_store=cast_store,
            bible_store=bible_store,
            narrative_store=narrative_store,
        )
        self._writer = PovWriter(
            conn, narrative_store=narrative_store, world_store=world_store
        )

    # -- the chapter arm -----------------------------------------------------

    def open_chapter(
        self,
        world_id: str,
        blueprint: Mapping[str, Any],
        now: str,
    ) -> Result[ChapterOpening]:
        """Plan the world's next chapter from the caller's own Blueprint
        payload — the Director's Plan-face act, called in the RA §27
        order's first step (the payload is the caller's:
        :meth:`plan_chapter` is the same act with the payload produced
        by the Director provider)."""

        return self._director.open_next_chapter(world_id, blueprint, now)

    def plan_chapter(self, world_id: str, now: str) -> Result[ChapterOpening]:
        """Plan the world's next chapter through the **Director
        provider** — V3-8b's initial-Blueprint arm (HIGH-3): the
        Blueprint's production is the world's own planning face, fed the
        full ``DirectorContext`` (the no-trigger arm of
        :class:`~elc.world.providers.DirectorPlanContext`);
        ``Director.open_next_chapter`` keeps the validation and the
        persistence. A dangling world is answered ``NOT_FOUND`` before
        the provider is asked (the context read presumes the world)."""

        tick = read_current_tick(self._conn, world_id)
        if isinstance(tick, Err):
            return Err(tick.error)
        payload = self._director_provider.draft_blueprint(
            DirectorPlanContext(
                director_context=self._director.context(world_id),
                chapter_id=None,
                replan_request_id=None,
                trigger=None,
                blueprint=None,
            )
        )
        return self._director.open_next_chapter(world_id, payload, now)

    # -- the scene arm -------------------------------------------------------

    def run_scene(
        self,
        scene_id: str,
        beats: Sequence[SegmentBeat | GateBeat],
        now: str,
    ) -> Result[SceneRun]:
        """Drive one scene through ``beats`` (see the module docstring):
        a ``PLANNED`` scene opens first (its dossier rev 1, the scene
        ``ACTIVE``); an already-``ACTIVE`` scene — the crash mid-drive —
        is continued from its durable rows (the same opening shape, the
        committed beats replay), and a settled scene refuses (a
        completed drive is not re-runnable). Then the beats in order.

        **The script law (V3-8b)**: the beats are the scene's own
        script from its first segment — the i-th
        :class:`SegmentBeat` is the scene's i-th segment — so a
        re-drive of the same script replays its committed segments
        positionally (the library face's replay arm answers each stored
        ``segment_key``). The V3-8a ``first_segment_seq`` knob is gone:
        a mid-scene continuation is a durable-state matter and enters
        through :meth:`resume`, whose seventh family derives its
        ``segment_seq`` from the ``segment_commit`` rows.

        The first refusal stops the drive and rides out unchanged; the
        writes that already landed are durable (every step is
        idempotent, so a retry converges)."""

        opened = self._open_or_continue(scene_id, now)
        if isinstance(opened, Err):
            return Err(opened.error)
        opening = opened.value
        segments: list[CommitOutcome] = []
        gates: list[UserGateRecord] = []
        actions: list[ActionOutcome] = []
        replans: list[ReplanConsumption] = []
        handled_gate_ids: list[str] = []
        next_seq = 1
        pending_ref: str | None = None
        for beat in beats:
            if isinstance(beat, GateBeat):
                driven = self._drive_gate(scene_id, beat, now)
                if isinstance(driven, Err):
                    return Err(driven.error)
                gate, action, consumed = driven.value
                handled_gate_ids.append(gate.gate_id)
                actions.append(action)
                if consumed is not None:
                    replans.append(consumed)
                pending_ref = action.user_action_id
                continue
            if not isinstance(beat, SegmentBeat):
                return Err(
                    DomainError(
                        code=DomainErrorCode.VALIDATION_FAILED,
                        message=(
                            f"scene {scene_id!r} not driven: a beat must"
                            " be a SegmentBeat or a GateBeat; got"
                            f" {type(beat).__name__}"
                        ),
                    )
                )
            written = self._drive_segment(
                scene_id, next_seq, beat, pending_ref, now
            )
            if isinstance(written, Err):
                return Err(written.error)
            segments.append(written.value)
            if pending_ref is not None:
                # The continuation named the ruling once — the forced
                # law's own shape (STATE §25's V3-6R 落法): the segment
                # after a committed gate carries its outcome_ref.
                pending_ref = None
            next_seq += 1
        for gate_id in handled_gate_ids:
            final = get_gate(self._conn, gate_id)
            if final is not None:
                gates.append(final)
        return Ok(
            SceneRun(
                opening=opening,
                segments=tuple(segments),
                gates=tuple(gates),
                actions=tuple(actions),
                replans=tuple(replans),
            )
        )

    # -- the chapter-end arm -------------------------------------------------

    def settle(
        self, chapter_id: str, now: str
    ) -> Result[ChapterSettlementRecord]:
        """Land one chapter's settlement — the RA §27 diagram's
        chapter-end step: the narrative store's ``ACTIVE → SETTLING``
        flip first (only when the chapter is still ``ACTIVE``; a
        ``SETTLING`` chapter — the NCP-4 crash's own state — goes
        straight to the settlement), then NCP-4's
        :func:`elc.world.settlement.settle_chapter` (the one-version
        row and the ``SETTLING → CLOSED`` flip in one short
        transaction). The flip judges V3-8b's SETTLING precondition
        inside its own transaction (no ``ACTIVE`` scene, no gate outside
        ``CLOSED``, no ``PENDING`` obligation): a chapter still holding
        a running story refuses ``VALIDATION_FAILED`` naming it and
        stays ``ACTIVE`` — the caller commits or discards the remaining
        scenes first. A ``PLANNED`` or settled ``CLOSED`` chapter is
        refused by the settlement face itself (the honest answer)."""

        chapter = self._narrative.get_chapter(chapter_id)
        if chapter is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"chapter {chapter_id!r} not settled: it does not"
                        " exist"
                    ),
                )
            )
        if chapter.status is ChapterStatus.ACTIVE:
            flipped = self._narrative.settle_chapter(
                chapter_id, now, expected_state_version=chapter.state_version
            )
            if isinstance(flipped, Err):
                return Err(flipped.error)
        return settlement_faces.settle_chapter(
            self._conn,
            narrative_store=self._narrative,
            world_store=self._worlds,
            chapter_id=chapter_id,
            now=now,
        )

    # -- the crash-resume arm ------------------------------------------------

    def resume(self, world_id: str, now: str) -> Result[RecoveryRun]:
        """Walk ``recovery_scan``'s seven families for one world and
        route what is routable (see the module docstring):

        - gates ``ANSWERED`` / ``RESOLVING`` — re-adjudicate **with the
          stored ``submission_id``** (the NCP-1 anchor; the resolver
          provider answers the same gate again and ``commit_action``
          lands the unique outcome — a crash after NCP-1 loses no
          ruling and invents no second one), then route the ruling's
          own replan obligation when one was born;
        - obligations ``PENDING`` — consume through the scope's face
          (``replan_scene`` / ``apply_action_replan``; the chapter-level
          one is produced by the Director provider, V3-8b's HIGH-3);
        - **continuations** — V3-8b's HARD GATE: a ``COMMITTED`` gate
          whose scene holds no passage carrying its action is a ruling
          nobody resumed past; the walk drives its **first continuation
          passage** from durable state — the sequence rides the scan's
          ``next_segment_seq`` (derived from the ``segment_commit``
          rows, ``max + 1``), the committed action rides as the forced
          ``outcome_ref``, and the gate closes in that same commit.
          The caller re-supplies nothing: no in-process GateBeat, no
          starting sequence;
        - ``SETTLING`` chapters — :meth:`settle` them to ``CLOSED``;
        - ``ACTIVE`` scenes — read and reported, never routed.

        Families in other worlds are filtered out; the walk is
        world-scoped because the resume is. Every route is an idempotent
        library call, so re-running the walk after a completed one is a
        zero-write no-op. A refusal stops the walk and rides out
        unchanged (the routes already taken are durable and replay).

        **One scan, one walk**: the walk routes the families the scan
        found. A ruling this walk itself commits (the ``ANSWERED``
        family) births its continuation obligation *after* the scan —
        the next walk (or the caller's next drive) carries it, and
        because every route is idempotent, walking twice converges
        without a second story."""

        scan = recovery_scan(self._conn, narrative_store=self._narrative)
        if isinstance(scan, Err):
            return Err(scan.error)
        gates_committed: list[str] = []
        replans_consumed: list[ReplanConsumption] = []
        continuations_driven: list[str] = []
        chapters_settled: list[str] = []
        active_scene_ids: list[str] = []

        for gate in scan.value.gates:
            world = self._world_of_scene(gate.scene_id)
            if world is None:
                return Err(self._dangling_scene(gate.scene_id))
            if world != world_id:
                continue
            action = action_of(self._conn, gate.gate_id)
            if action is None:  # the FK makes this unreachable
                return Err(
                    DomainError(
                        code=DomainErrorCode.NOT_FOUND,
                        message=(
                            f"gate {gate.gate_id!r} not resumed: its"
                            " submission row does not exist"
                        ),
                    )
                )
            if action.status is ActionStatus.ANSWERED:
                moved = begin_resolving(
                    self._conn, gate_id=gate.gate_id, now=now
                )
                if isinstance(moved, Err):
                    return Err(moved.error)
            context = self._resolver_context_of(gate, action)
            if isinstance(context, Err):
                return Err(context.error)
            ruling = self._resolver_provider.adjudicate(context.value)
            committed = commit_action(
                self._conn,
                world_store=self._worlds,
                narrative_store=self._narrative,
                gate_id=gate.gate_id,
                submission_id=action.submission_id,
                adjudication=ruling,
                duration_ticks=self._action_duration_ticks,
                now=now,
            )
            if isinstance(committed, Err):
                return Err(committed.error)
            gates_committed.append(gate.gate_id)
            if committed.value.replan_scope is not ReplanScope.NONE:
                consumed = self._consume_replan(
                    replan_request_id_for(
                        gate.gate_id, action.submission_id
                    ),
                    now,
                )
                if isinstance(consumed, Err):
                    return Err(consumed.error)
                replans_consumed.append(consumed.value)

        for obligation in scan.value.replans:
            world = self._world_of_obligation(obligation.replan_request_id)
            if world is None:
                return Err(
                    DomainError(
                        code=DomainErrorCode.NOT_FOUND,
                        message=(
                            "replan obligation"
                            f" {obligation.replan_request_id!r} not"
                            " resumed: its action chain (obligation →"
                            " action → gate → scene) is dangling"
                        ),
                    )
                )
            if world != world_id:
                continue
            consumed = self._consume_replan(
                obligation.replan_request_id, now
            )
            if isinstance(consumed, Err):
                return Err(consumed.error)
            replans_consumed.append(consumed.value)

        for continuation in scan.value.continuations:
            world = self._world_of_scene(continuation.scene_id)
            if world is None:
                return Err(self._dangling_scene(continuation.scene_id))
            if world != world_id:
                continue
            scene = self._narrative.get_scene(continuation.scene_id)
            if scene is None:  # unreachable through the FK; answered honestly
                return Err(self._dangling_scene(continuation.scene_id))
            if scene.status is not SceneStatus.ACTIVE:
                return Err(
                    DomainError(
                        code=DomainErrorCode.VALIDATION_FAILED,
                        message=(
                            f"gate {continuation.gate_id!r} not"
                            f" continued: its scene"
                            f" {continuation.scene_id!r} is"
                            f" {scene.status.value!r} — a continuation"
                            " passage lands in an ACTIVE scene (the"
                            " story the ruling resumed is still open)"
                        ),
                    )
                )
            driven = self._drive_continuation(
                continuation.scene_id,
                continuation.next_segment_seq,
                continuation.user_action_id,
                now,
            )
            if isinstance(driven, Err):
                return Err(driven.error)
            continuations_driven.append(continuation.gate_id)

        for chapter in scan.value.settling_chapters:
            if chapter.world_id != world_id:
                continue
            settled = self.settle(chapter.chapter_id, now)
            if isinstance(settled, Err):
                return Err(settled.error)
            chapters_settled.append(chapter.chapter_id)

        for scene in scan.value.scenes:
            if self._world_of_scene(scene.scene_id) == world_id:
                active_scene_ids.append(scene.scene_id)

        return Ok(
            RecoveryRun(
                world_id=world_id,
                gates_committed=tuple(gates_committed),
                replans_consumed=tuple(replans_consumed),
                continuations_driven=tuple(continuations_driven),
                chapters_settled=tuple(chapters_settled),
                active_scene_ids=tuple(active_scene_ids),
            )
        )

    # -- the drives' internals ----------------------------------------------

    def _open_or_continue(
        self, scene_id: str, now: str
    ) -> Result[SceneOpening]:
        """The scene arm's two doors: a ``PLANNED`` scene opens through
        :meth:`elc.world.scene.ScenePlanner.open_scene` (the dossier
        rev 1 chain), and an already-``ACTIVE`` scene — the crash
        mid-drive, its earlier beats committed — is **continued**: the
        opening is assembled from the durable rows (the scene, its
        adopted dossier, the element mapping the plan face spells and
        the POV context), the same shape ``open_scene`` would have
        answered. A settled scene (``COMMITTED`` / ``CLOSED`` /
        ``DISCARDED``) is past this door — a completed drive is not
        re-runnable, its rows are canon."""

        scene = self._narrative.get_scene(scene_id)
        if scene is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"scene {scene_id!r} not driven: it does not exist"
                    ),
                )
            )
        if scene.status is SceneStatus.PLANNED:
            return self._planner.open_scene(scene_id, now)
        if scene.status is not SceneStatus.ACTIVE:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} not driven: it is"
                        f" {scene.status.value!r} — a drive opens a"
                        " PLANNED scene or continues an ACTIVE one; a"
                        " settled scene's canon is not this face's to"
                        " move (a completed drive is not re-runnable)"
                    ),
                )
            )
        dossier = self._narrative.adopted_dossier(scene_id)
        if dossier is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"scene {scene_id!r} not continued: it holds no"
                        " ADOPTED Dossier — an ACTIVE scene's plan face"
                        " is its dossier"
                    ),
                )
            )
        chapter = self._chapter_of_scene(scene_id)
        if isinstance(chapter, Err):
            return Err(chapter.error)
        context = self._scene_context_of(chapter.value, dossier)
        if isinstance(context, Err):
            return Err(context.error)
        return Ok(
            SceneOpening(
                scene=scene,
                dossier=dossier,
                element=_element_mapping_of(dossier),
                context=context.value,
            )
        )

    def _drive_segment(
        self,
        scene_id: str,
        segment_seq: int,
        beat: SegmentBeat,
        outcome_ref: str | None,
        now: str,
    ) -> Result[CommitOutcome]:
        """One segment: compile the POV-safe input from the **current**
        adopted dossier (a replanning between beats may have moved the
        plan face — the Writer writes from the plan that stands), ask
        the Writer provider, hand the prose to ``PovWriter``."""

        dossier = self._narrative.adopted_dossier(scene_id)
        if dossier is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"segment {segment_seq} of scene {scene_id!r} not"
                        " driven: the scene holds no ADOPTED Dossier —"
                        " the Writer's input is the current plan"
                    ),
                )
            )
        chapter = self._chapter_of_scene(scene_id)
        if isinstance(chapter, Err):
            return Err(chapter.error)
        context = self._scene_context_of(chapter.value, dossier)
        if isinstance(context, Err):
            return Err(context.error)
        pov = pov_context_of(
            dossier=dossier, context=context.value, segment_seq=segment_seq
        )
        body = self._writer_provider.write_segment(pov)
        return self._writer.write_segment(
            scene_id,
            body,
            beat.language,
            segment_seq,
            beat.duration_ticks,
            beat.is_last_segment,
            now,
            outcome_ref=outcome_ref,
        )

    def _drive_gate(
        self,
        scene_id: str,
        beat: GateBeat,
        now: str,
    ) -> Result[
        tuple[UserGateRecord, ActionOutcome, ReplanConsumption | None]
    ]:
        """One gate, end to end (see :meth:`run_scene`): open → submit
        (NCP-1) → the durable resolver stop (``begin_resolving``, when
        the submission row is still ``ANSWERED``) → the provider's
        verdict → NCP-2 → the auto-routed replan when the verdict
        invalidated the plan. Every step is the library face's own
        idempotent call, so a re-drive replays (a gate already
        ``COMMITTED`` skips the durable stop — ``commit_action``'s
        replay arm answers its stored outcome first)."""

        opened = open_gate(
            self._conn,
            scene_id=scene_id,
            gate_seq=beat.gate_seq,
            options=beat.options,
            now=now,
        )
        if isinstance(opened, Err):
            return Err(opened.error)
        gate = opened.value
        submitted = submit_gate(
            self._conn,
            gate_id=gate.gate_id,
            submission_id=beat.submission_id,
            intent_text=beat.intent_text,
            selected_option=beat.selected_option,
            now=now,
        )
        if isinstance(submitted, Err):
            return Err(submitted.error)
        action = submitted.value
        if action.status is ActionStatus.ANSWERED:
            moved = begin_resolving(self._conn, gate_id=gate.gate_id, now=now)
            if isinstance(moved, Err):
                return Err(moved.error)
        context = self._resolver_context_of(gate, action)
        if isinstance(context, Err):
            return Err(context.error)
        ruling = self._resolver_provider.adjudicate(context.value)
        committed = commit_action(
            self._conn,
            world_store=self._worlds,
            narrative_store=self._narrative,
            gate_id=gate.gate_id,
            submission_id=beat.submission_id,
            adjudication=ruling,
            duration_ticks=self._action_duration_ticks,
            now=now,
        )
        if isinstance(committed, Err):
            return Err(committed.error)
        outcome = committed.value
        consumed: ReplanConsumption | None = None
        if outcome.replan_scope is not ReplanScope.NONE:
            routed = self._consume_replan(
                replan_request_id_for(gate.gate_id, beat.submission_id), now
            )
            if isinstance(routed, Err):
                return Err(routed.error)
            consumed = routed.value
        return Ok((gate, outcome, consumed))

    def _consume_replan(
        self, replan_request_id: str, now: str
    ) -> Result[ReplanConsumption]:
        """Consume one ruling's plan verdict through its durable
        obligation (the claim → work → complete protocol lives in the
        library faces; this drive only picks the scope's face and feeds
        the scope's provider the context the division freeze gives it).

        An ``APPLIED`` obligation answers its stored target zero-write
        (the crash after the plan change). A ``PENDING`` one resolves
        its scene through the durable chain and calls
        ``ScenePlanner.replan_scene`` (``SCENE`` — the revised element
        from :class:`~elc.world.providers.PlannerProvider`, the
        POV-safe scene context its primary input) or
        ``Director.apply_action_replan`` (``CHAPTER`` — the revised
        Blueprint from :class:`~elc.world.providers.DirectorProvider`,
        produced from the full ``DirectorContext`` plus the committed
        ruling that triggered it: V3-8b's HIGH-3, the chapter's plan is
        the world's, never the POV-limited planner's)."""

        obligation = replan_obligation(self._conn, replan_request_id)
        if obligation is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"replan obligation {replan_request_id!r} not"
                        " consumed: it does not exist (a NONE ruling"
                        " births no obligation — there is nothing to"
                        " route)"
                    ),
                )
            )
        if obligation.status is ReplanStatus.APPLIED:
            assert obligation.target_ref is not None  # the composite CHECK
            return Ok(
                ReplanConsumption(
                    replan_request_id=replan_request_id,
                    scope=obligation.scope,
                    target_ref=obligation.target_ref,
                )
            )
        if (
            obligation.scope is not ReplanScope.SCENE
            and obligation.scope is not ReplanScope.CHAPTER
        ):
            raise ValueError(
                f"replan obligation {replan_request_id!r} carries the"
                f" scope {obligation.scope!r}, which no consumer answers"
                " — a corrupted obligation row"
            )
        scene_id = scene_of_action(self._conn, replan_request_id)
        if scene_id is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"replan obligation {replan_request_id!r} not"
                        " consumed: its action chain (obligation → action"
                        " → gate → scene) is dangling — the obligation"
                        " names no scene"
                    ),
                )
            )
        dossier = self._narrative.adopted_dossier(scene_id)
        if dossier is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"replan obligation {replan_request_id!r} not"
                        f" consumed: scene {scene_id!r} holds no ADOPTED"
                        " Dossier — the ruling scene's plan face is gone"
                    ),
                )
            )
        chapter = self._chapter_of_scene(scene_id)
        if isinstance(chapter, Err):
            return Err(chapter.error)
        context = self._scene_context_of(chapter.value, dossier)
        if isinstance(context, Err):
            return Err(context.error)
        if obligation.scope is ReplanScope.SCENE:
            element = self._planner_provider.replan_element(
                ScenePlanContext(
                    world_id=chapter.value.world_id,
                    scene_id=scene_id,
                    pov_actor_id=dossier.pov_actor_id,
                    current_tick=context.value.current_tick,
                    element=_element_mapping_of(dossier),
                    cognition=context.value.cognition,
                    memory=context.value.memory,
                )
            )
            replanned = self._planner.replan_scene(
                replan_request_id, element, now
            )
            if isinstance(replanned, Err):
                return Err(replanned.error)
            return Ok(
                ReplanConsumption(
                    replan_request_id=replan_request_id,
                    scope=obligation.scope,
                    target_ref=replanned.value.dossier_id,
                )
            )
        plan = self._narrative.adopted_plan(chapter.value.chapter_id)
        if plan is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"replan obligation {replan_request_id!r} not"
                        f" consumed: chapter {chapter.value.chapter_id!r}"
                        " holds no ADOPTED Blueprint — a CHAPTER"
                        " replanning revises the current plan"
                    ),
                )
            )
        trigger = action_by_id(self._conn, obligation.user_action_id)
        if trigger is None:  # the FK makes this unreachable
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"replan obligation {replan_request_id!r} not"
                        " consumed: its action row"
                        f" {obligation.user_action_id!r} does not exist —"
                        " the trigger of a CHAPTER replanning is the"
                        " committed ruling itself"
                    ),
                )
            )
        payload = self._director_provider.replan_blueprint(
            DirectorPlanContext(
                director_context=self._director.context(
                    chapter.value.world_id
                ),
                chapter_id=chapter.value.chapter_id,
                replan_request_id=replan_request_id,
                trigger=trigger,
                blueprint=_blueprint_mapping_of(plan),
            )
        )
        applied = self._director.apply_action_replan(
            replan_request_id, payload, now
        )
        if isinstance(applied, Err):
            return Err(applied.error)
        return Ok(
            ReplanConsumption(
                replan_request_id=replan_request_id,
                scope=obligation.scope,
                target_ref=applied.value.plan.chapter_plan_id,
            )
        )

    def _resolver_context_of(
        self,
        gate: UserGateRecord,
        action: UserActionRecord,
    ) -> Result[ResolverContext]:
        """Compile the Resolver provider's **world-authoritative** input
        (V3-8b's HIGH-2; V3-8a's POV-limited ``AdjudicationContext`` is
        replaced): the user's own submission (from the durable
        ``user_action`` row) beside the world's real authority — the
        ``CURRENT`` Bible, the settled ``world_state_fact`` half, the
        player's durable row and the scene's counterpart profiles — the
        ruling scene's own plan face (its adopted dossier's place /
        participants) and **two knowledge arms** (V3-8c's F4): the
        player character's **own** cognition / memory read
        (``viewer = player_character_id`` — the authority for *what the
        user character knows*; both ``None`` when the world declares no
        player) and the POV's read (the presentation face, RA §27's
        「＋ 当前 POV 面」). The reads are the stores' own public faces;
        nothing here interprets a value (the honesty statements live on
        the record's docstring)."""

        dossier = self._narrative.adopted_dossier(gate.scene_id)
        if dossier is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.VALIDATION_FAILED,
                    message=(
                        f"ruling of gate {gate.gate_id!r} not assembled:"
                        f" scene {gate.scene_id!r} holds no ADOPTED"
                        " Dossier — the resolver context reads the"
                        " scene's plan face"
                    ),
                )
            )
        chapter = self._chapter_of_scene(gate.scene_id)
        if isinstance(chapter, Err):
            return Err(chapter.error)
        context = self._scene_context_of(chapter.value, dossier)
        if isinstance(context, Err):
            return Err(context.error)
        world_id = chapter.value.world_id
        player = self._cast.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        player_cognition = None
        player_memory = None
        if player is not None:
            cognition_read = v3_cognition_view(
                self._conn,
                world_id=world_id,
                viewer_id=player.player_character_id,
            )
            if isinstance(cognition_read, Err):
                return Err(cognition_read.error)
            player_cognition = cognition_read.value
            memory_read = v3_memory_view(
                self._conn,
                world_id=world_id,
                viewer_id=player.player_character_id,
            )
            if isinstance(memory_read, Err):
                return Err(memory_read.error)
            player_memory = memory_read.value
        counterparts = tuple(
            profile
            for profile in (
                self._cast.actor_profile(participant)
                for participant in dossier.participants
                if participant != player_id
            )
            if profile is not None
        )
        return Ok(
            ResolverContext(
                gate_id=gate.gate_id,
                scene_id=gate.scene_id,
                submission_id=action.submission_id,
                intent_text=action.intent_text,
                selected_option=action.selected_option,
                options=gate.options,
                bible=self._bibles.current_bible(world_id),
                current_facts=self._worlds.current_facts(world_id),
                player_character=player,
                place=dossier.place,
                participants=dossier.participants,
                counterparts=counterparts,
                player_cognition=player_cognition,
                player_memory=player_memory,
                pov_actor_id=dossier.pov_actor_id,
                cognition=context.value.cognition,
                memory=context.value.memory,
                current_tick=context.value.current_tick,
            )
        )

    def _drive_continuation(
        self,
        scene_id: str,
        segment_seq: int,
        outcome_ref: str,
        now: str,
    ) -> Result[CommitOutcome]:
        """Drive one committed-unclosed gate's **first continuation
        passage** — V3-8b's HARD GATE (see :meth:`resume`): the
        sequence is the recovery scan's durable derivation
        (``segment_commit`` ``max + 1``) and the committed action rides
        as the forced ``outcome_ref``, so the library face's forced law
        is satisfied and the gate closes in the same commit. The
        deterministic baseline gives the continuation the default
        one-tick, non-terminal beat — its length and terminality are
        the planner's seat in the LLM wiring, the same seat every
        :class:`SegmentBeat` drives from."""

        return self._drive_segment(
            scene_id,
            segment_seq,
            SegmentBeat(),
            outcome_ref,
            now,
        )

    def _scene_context_of(
        self,
        chapter: WorldChapterRecord,
        dossier: WorldSceneDossierRecord,
    ) -> Result[SceneContext]:
        """Compile the scene's POV context for the plan face that
        stands — the V3-5R HIGH-1 read re-run per call (the dossier is
        the scene's own; a replanning may have moved it): the chapter's
        world's canonical tick and the POV's own cognition / memory
        views. A view refusal rides out unchanged."""

        tick = read_current_tick(self._conn, chapter.world_id)
        if isinstance(tick, Err):
            return Err(tick.error)
        cognition = v3_cognition_view(
            self._conn,
            world_id=chapter.world_id,
            viewer_id=dossier.pov_actor_id,
        )
        if isinstance(cognition, Err):
            return Err(cognition.error)
        memory = v3_memory_view(
            self._conn,
            world_id=chapter.world_id,
            viewer_id=dossier.pov_actor_id,
        )
        if isinstance(memory, Err):
            return Err(memory.error)
        return Ok(
            SceneContext(
                current_tick=tick.value,
                pov_actor_id=dossier.pov_actor_id,
                cognition=cognition.value,
                memory=memory.value,
            )
        )

    def _chapter_of_scene(self, scene_id: str) -> Result[WorldChapterRecord]:
        """The chapter one scene belongs to — the row read the helpers
        above share (a dangling scene is answered, never guessed)."""

        scene = self._narrative.get_scene(scene_id)
        if scene is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"scene {scene_id!r} does not exist — the drive"
                        " reads its chapter from the durable rows"
                    ),
                )
            )
        chapter = self._narrative.get_chapter(scene.chapter_id)
        if chapter is None:  # the FK makes this unreachable; answered honestly
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=(
                        f"scene {scene_id!r}'s chapter"
                        f" {scene.chapter_id!r} does not exist"
                    ),
                )
            )
        return Ok(chapter)

    def _world_of_scene(self, scene_id: str) -> str | None:
        """The world one scene belongs to, or ``None`` when the row (or
        its chapter) is gone — the honest filter read (no SQL of this
        module's own)."""

        scene = self._narrative.get_scene(scene_id)
        if scene is None:
            return None
        chapter = self._narrative.get_chapter(scene.chapter_id)
        if chapter is None:
            return None
        return chapter.world_id

    def _world_of_obligation(self, replan_request_id: str) -> str | None:
        """The world one obligation's durable chain names, or ``None``
        when a link is missing."""

        scene_id = scene_of_action(self._conn, replan_request_id)
        if scene_id is None:
            return None
        return self._world_of_scene(scene_id)

    @staticmethod
    def _dangling_scene(scene_id: str) -> DomainError:
        return DomainError(
            code=DomainErrorCode.NOT_FOUND,
            message=(
                f"recovery walk refused: scene {scene_id!r} (a scan row)"
                " does not resolve to a world — a corrupted chain"
            ),
        )


def _element_mapping_of(dossier: WorldSceneDossierRecord) -> dict[str, Any]:
    """One dossier's content in the Blueprint element's own shape — the
    current Plan-face content a replanning starts from (the Planner
    provider's ``element`` input; the keys are the canonical ten the
    Director's schema froze)."""

    return {
        "pov_actor_id": dossier.pov_actor_id,
        "participants": list(dossier.participants),
        "planned_start_tick": dossier.planned_start_tick,
        "place": dossier.place,
        "entry_goals": dossier.entry_goals,
        "exit_condition": dossier.exit_condition,
        "elasticity": dossier.elasticity,
        "revealable": dossier.revealable,
        "must_hide": dossier.must_hide,
    }


def _blueprint_mapping_of(plan: WorldChapterPlanRecord) -> dict[str, Any]:
    """One adopted plan revision's content in the Blueprint payload's
    own shape (the Director's schema's nine chapter fields plus the
    scenes table) — the CHAPTER arm's starting content."""

    return {
        "goal": plan.goal,
        "dramatic_question": plan.dramatic_question,
        "planned_start_tick": plan.planned_start_tick,
        "planned_end_tick": plan.planned_end_tick,
        "closing_pressure": plan.closing_pressure,
        "desired_development": plan.desired_development,
        "soft_outcomes": plan.soft_outcomes,
        "chapter_questions_to_advance": plan.chapter_questions_to_advance,
        "scenes": [dict(element) for element in plan.scenes],
    }
