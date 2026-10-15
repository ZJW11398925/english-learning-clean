"""The dual-seat world's turn spine (DS-1, the technical definition
§1–§5, §7, §10 — docs/design/2026-10-14-dual-seat-world-technical-
definition.md) — the code-owned turn trunk the definition's §1 rules:
「代码脊柱拥有回合主干，导演 agent 在决策点产出结构化调度决定」.

**What this module is.** One drive = one beat of one of the three beat
types (§1: ``open`` 章首铺陈 / ``advance`` 世界推进 / ``reply`` 你的话驱
动), executed through the pipeline order the definition spells:

- ``reply``: ①+③ the dispatch arm's one structured decision (the
  intent reading rides the same answer — the stage-0 probe's shape)
  → ④ the responding character arms **in parallel** (§2's private-seat
  proposals) → ⑤ ONE batch adjudication (§1b: k proposals + your event
  → one δ, the seven-field
  :class:`~elc.world.action.Adjudication` verbatim, the batch riding
  ``state_effects``) → ⑥ the canon commit through the existing chain
  (``open_gate`` → ``submit_gate`` → ``begin_resolving`` →
  :func:`elc.world.action.commit_action` — the three checks, the
  namespace check, the replay arm all unchanged) → the private
  thoughts land (§2 F4, :func:`elc.world.memory.record_belief` — the
  zero-migration form: the character's OWN memory row, per-viewer
  private by construction; the dedicated ``PRIVATE_THOUGHT`` kind word
  needs a storage-side CHECK move and is registered for the migration
  blade) → ⑦ the narration arm's second-person streamed prose → the
  SEGMENT COMMIT (PovWriter: the guards, the lineage, the
  ``outcome_ref`` closing the gate — the V3-6R forced law the spine
  satisfies, never the caller) → ⑧ the stop decision (§4's markers +
  policy);
- ``open`` / ``advance``: ①④ skipped (no words to read, no one to
  answer), the dispatch arm decides the world event and the pacing,
  the narration renders, the SEGMENT COMMIT lands.

**Zero write power of its own** (the Pipeline's discipline, kept):
every write here is a library face's own short transaction —
``open_scene`` / ``open_gate`` / ``submit_gate`` / ``begin_resolving``
/ ``commit_action`` / ``PovWriter.write_segment`` / ``record_belief``
— and the engine half spells no SQL and no ``BEGIN`` of its own (the
read half, :class:`TurnReads`, spells read-only SELECTs — the
narrative_web one-law-two-readers posture). Every step is idempotent,
so a crash mid-drive replays: the POC failure semantics are §10 F8's
own — the turn re-runs from the last committed δ (a committed ruling
answers its stored shape; the narration regenerates; committed
segments replay byte-equal).

**The script law is rebuilt here** (§10 F1): beats are produced by the
dispatch decision + the spine, never by a plan script — the drive asks
the durable rows where the story stands (the standing gate, the
committed segments) and executes the next beat. The replay anchor is
**the committed δ rows themselves** (:func:`turn_steps_of` — the
segment / action lineage read back in canonical order; the full
turn-log resume stays §10's registered post-POC blade).

**The guardrails ride from day one** (§1 F7, the DS-3 节奏律): one
drive runs at most :data:`DRIVE_BEAT_CEILING` beats and at most
:data:`DRIVE_CALL_CEILING` model calls — BOTH are **pure guardrails**:
they bound the 「一直写个没完」 accident, they are never routine stops.
Hitting either is a *reasoned* stop (the sentence rides
``DriveRun.note`` — 「有故之停，不得无解释之停」) and an anomaly signal
(the note rides ``DriveRun.notes`` — the normal path drives to a
natural hanging point and never touches a ceiling).

**The stop law** (§4 + the DS-3 节奏律): the narration arm's own
markers — ``addresses_you`` / ``impends_on_you`` are the natural
hanging points and the ONLY routine stops (「轮到你了」);
``beat_complete`` never stops (the drive continues — the default is
推进到自然悬点). The dispatch pacing word stays a scheduling signal,
never a stop. Every stop decision is recorded
(:class:`StopDecision`; the drive's answer carries the full log — the
measurement face the POC acceptance reviews).

**The harness registry is the only door to a privileged act** (§3):
each execution point authorizes through :mod:`elc.world.harness` first
— ``dispatch_character`` / ``canon_delta`` / ``memory_write`` /
``render_narration`` all name their principal; a violation is the loud
programmer error, never a silent pass.

Discipline: model failures surface as
:class:`~elc.world.llm_providers.LlmProviderError` and propagate (the
caller — the web face — owns the human sentence, the V3 posture);
library ``Result`` refusals stop the drive as ``DriveRun.error`` (the
code and message ride; the landed beats stay durable); no hidden clock
(every durable stamp is the caller's ``now``); no SQL string building;
threads only for the character arms' parallel model calls (pure model
I/O — no shared-connection work inside a thread).
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

from elc.platform.types import Err, Result
from elc.world import harness
from elc.world.action import (
    ActionStatus,
    Adjudication,
    GateStatus,
    ReplanScope,
    UserActionRecord,
    UserGateRecord,
    action_of,
    begin_resolving,
    commit_action,
    get_gate,
    open_gate,
    submit_gate,
)
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.cognition import v3_cognition_view
from elc.world.director import Director
from elc.world.ds_situation import situation_face_of
from elc.world.llm_providers import (
    BatchAdjudicationContext,
    CharacterContext,
    CharacterProposal,
    DispatchContext,
    DispatchDecision,
    LlmBatchAdjudicatorProvider,
    LlmCharacterProvider,
    LlmDispatcherProvider,
    LlmNarratorProvider,
    NarrationContext,
    NarrationResult,
    WorldAdjudicationContext,
    pack_memories,
)
from elc.world.memory import MemoryKind, record_belief, v3_memory_view
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    SceneStatus,
    WorldChapterRecord,
    WorldSceneDossierRecord,
    WorldSceneRecord,
)
from elc.world.pipeline import Pipeline
from elc.world.scene import ScenePlanner
from elc.world.settlement import (
    CommitOutcome,
)
from elc.world.settlement import (
    settle_chapter as land_settlement,
)
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick
from elc.world.types import StateEffect, WorldEvent
from elc.world.writer import PovWriter

__all__ = [
    "DRIVE_BEAT_CEILING",
    "DRIVE_CALL_CEILING",
    "DS_MEMORY_CAP",
    "MOOD_KEY_PREFIX",
    "AdvanceBeat",
    "DriveRun",
    "OpenBeat",
    "ReplyBeat",
    "SettleRecord",
    "StopDecision",
    "TurnEngine",
    "TurnReads",
    "TurnRecord",
    "TurnRefusal",
    "TurnStep",
    "turn_steps_of",
]


#: One drive's beat ceiling (§1 F7: 「建议 3 拍」) — a PURE guardrail
#: under the DS-3 节奏律 (§4): it bounds the runaway accident, it is
#: never a routine stop; hitting it carries the sentence AND the
#: anomaly note (the normal path stops at a natural hanging point).
DRIVE_BEAT_CEILING = 3

#: One drive's model-call ceiling (§1 F7: 「建议 12 次」) — the cost
#: guardrail, likewise PURE under the rhythm law: a reply or world beat
#: spends ~5 calls (dispatch + k characters + adjudication +
#: narration), so twelve covers one beat plus one more with retry
#: headroom; hitting it is the reasoned stop + the anomaly signal.
DRIVE_CALL_CEILING = 12

#: The character pack's memory cap (DS-1 §2 F5: 「建议 ≤24 条」) — the
#: recency truncation applied to every pack.
DS_MEMORY_CAP = 24

#: The canonical-key prefix a protagonist's living goal / mood facts
#: ride (DS-1 §2's minimal face, zero migration: the facts land as
#: world state through the ruling's δ — the batch adjudication's own
#: ``state_effects`` — and each pack reads only its own character's).
MOOD_KEY_PREFIX = "protagon."

#: The recent-narration tail's character budget (the context packs'
#: continuity face; the probe's token calibration keeps the packs far
#: under their §8 budgets with this).
_TAIL_CHARS = 1200

#: The reasoned stops' own sentences (zh — the immersion face's own
#: voice, the reading-face note family's posture). Under the DS-3 rhythm
#: law (§4) these are PURE guardrails: hitting either is a *reasoned*
#: stop the normal path should never reach — the anomaly note rides
#: beside the sentence.
_BEAT_CEILING_SENTENCE = (
    "本次已连走 {written} 拍（一次驱动至多 {ceiling} 拍）——世界停在这，"
    "轮到你了。"
)
_CALL_CEILING_SENTENCE = (
    "这一次驱动用满了模型调用预算（{ceiling} 次）——世界先停在这，"
    "轮到你了。"
)

#: The ceilings' anomaly note (DS-3 §4 节奏律): a ceiling stop is a
#: dispatch-anomaly signal — the normal path drives to a natural
#: hanging point, so a ceiling stop means the narration never offered
#: one. Rides :data:`DriveRun.notes`, never the user-facing note.
_CEILING_ANOMALY_NOTE = (
    "dispatch anomaly: the drive hit the {which} ceiling — the rhythm"
    " law expects a natural stop (addresses_you / impends_on_you),"
    " and the narration offered none in {written} beat(s)"
)


@dataclass(frozen=True)
class OpenBeat:
    """The chapter-opening beat (§1: 章首铺陈) — no user words, the
    world's first narration of the planned chapter."""

    kind: str = "open"


@dataclass(frozen=True)
class AdvanceBeat:
    """The world-advance beat (§1: 世界推进，无你的输入) — the dispatch
    arm may insert a world event; nobody is asked to answer."""

    kind: str = "advance"


@dataclass(frozen=True)
class ReplyBeat:
    """The user's own words driving a beat (§1: 你的话或待落签驱动) —
    the submission is the user's own (the id is the idempotency
    anchor's half; the durable face wins on a re-drive)."""

    submission_id: str
    intent_text: str
    selected_option: str | None = None
    kind: str = "reply"


@dataclass(frozen=True)
class StopDecision:
    """One beat's stop verdict (DS-1 §4 + the DS-3 节奏律) — the
    markers, the pacing that informed it, the verdict and its reason.
    The drive's answer carries the whole log (the measurement face).
    The reason vocabulary under the rhythm law:
    ``addresses_you`` / ``impends_on_you`` (the natural hanging points
    — the ONLY routine stops; 「轮到你了」) / ``beat_complete`` (the
    drive continues — the ceilings are pure guardrails, never routine
    stops). The drive-level words (``beat_ceiling`` / ``call_ceiling``)
    stay the reasoned guardrail stops, each carrying its sentence and
    the anomaly note."""

    beat_kind: str
    addresses_you: bool
    impends_on_you: bool
    beat_complete: bool
    pacing: str
    stopped: bool
    reason: str


@dataclass(frozen=True)
class TurnRecord:
    """One executed beat's landing — what it called, what it wrote, and
    where the stop law left the story."""

    beat_kind: str
    narration: str
    passage_id: str | None
    gate_id: str | None
    dispatch: DispatchDecision | None
    proposals: tuple[CharacterProposal, ...]
    stop: StopDecision
    calls_used: int


@dataclass(frozen=True)
class DriveRun:
    """One drive's answer — the turns in order, the fresh passages, the
    reasoned stop and its note, the full stop log, the call count (the
    §8 cost face's own reading), the honest bookkeeping notes and the
    refusal channel (a library refusal stops the drive; the landed
    beats stay durable)."""

    world_id: str
    chapter_id: str | None
    scene_id: str | None
    turns: tuple[TurnRecord, ...]
    fresh_passage_ids: tuple[str, ...]
    stopped_on: str
    note: str | None
    stop_log: tuple[StopDecision, ...] = ()
    calls_used: int = 0
    notes: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class SettleRecord:
    """One chapter's offstage settlement answer (DS-1 §7) — the world
    summary line, the per-protagonist living-state lines, the landed
    settlement's own summary and the honest bookkeeping notes."""

    chapter_id: str
    offstage_event_id: str
    world_summary: str
    protagonist_lines: tuple[tuple[str, str], ...]
    settlement_summary: str
    calls_used: int
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TurnStep:
    """One committed step of the turn log (:func:`turn_steps_of`) — the
    recovery anchor's own row: a narration landing or a ruling, in
    canonical order, read back from the durable rows."""

    commit_id: str
    kind: str  # "narration" | "ruling"
    scene_id: str
    passage_id: str | None
    action_id: str | None
    outcome: str | None
    actual_start_tick: int
    actual_end_tick: int


class TurnRefusal(Exception):
    """A library ``Result`` refusal, unwrapped — the drive's internal
    stop channel (the code and message land on ``DriveRun.error``; the
    landed beats stay durable). Never escapes the module."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class TurnReads:
    """The turn spine's read half — every method a pure read over one
    connection (the read-only-SELECT posture narrative_web's
    ``_DurableReads`` spells; one derivation law, two readers: the
    engine drives from these reads and the web face renders them)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        narrative_store: SqliteNarrativeStore,
        world_store: SqliteWorldStore,
    ) -> None:
        self._conn = conn
        self._narrative = narrative_store
        self._worlds = world_store

    def current_chapter(
        self, world_id: str
    ) -> WorldChapterRecord | None:
        chapters = self._narrative.chapters_of(world_id)
        return chapters[-1] if chapters else None

    def current_scene(
        self, chapter_id: str
    ) -> WorldSceneRecord | None:
        """The chapter's drivable scene: the first ``ACTIVE``, else the
        first ``PLANNED`` (the roster's own order)."""

        current: WorldSceneRecord | None = None
        for scene in self._narrative.scenes_of(chapter_id):
            if scene.status is SceneStatus.ACTIVE:
                return scene
            if current is None and scene.status is SceneStatus.PLANNED:
                current = scene
        return current

    def adopted_dossier(
        self, scene_id: str
    ) -> WorldSceneDossierRecord | None:
        return self._narrative.adopted_dossier(scene_id)

    def adopted_plan(self, chapter_id: str):
        return self._narrative.adopted_plan(chapter_id)

    def committed_segments(self, scene_id: str) -> list[TurnStep]:
        """The scene's committed narration landings, in sequence order —
        the replay prefix's own source."""

        rows = self._conn.execute(
            "SELECT c.commit_id, c.passage_id, c.action_id,"
            " c.actual_start_tick, c.actual_end_tick"
            " FROM segment_commit c"
            " WHERE c.scene_id = ? AND c.kind = 'SEGMENT'"
            " ORDER BY c.segment_seq ASC",
            (scene_id,),
        ).fetchall()
        return [
            TurnStep(
                commit_id=str(row[0]),
                kind="narration",
                scene_id=scene_id,
                passage_id=None if row[1] is None else str(row[1]),
                action_id=None,
                outcome=None,
                actual_start_tick=int(row[3]),
                actual_end_tick=int(row[4]),
            )
            for row in rows
        ]

    def last_narration(self, scene_id: str) -> str:
        """The scene's most recent committed prose (the context packs'
        continuity tail; the honest empty string when none)."""

        row = self._conn.execute(
            "SELECT p.body FROM segment_commit c"
            " JOIN narrative_passage p ON p.passage_id = c.passage_id"
            " WHERE c.scene_id = ? AND c.kind = 'SEGMENT'"
            " ORDER BY c.segment_seq DESC LIMIT 1",
            (scene_id,),
        ).fetchone()
        if row is None:
            return ""
        body = str(row[0])
        return body[-_TAIL_CHARS:] if len(body) > _TAIL_CHARS else body

    def standing_gate(self, scene_id: str) -> UserGateRecord | None:
        """The scene's one gate short of ``CLOSED`` (the durable stop),
        or ``None`` — the one-gate law's read side."""

        rows = self._conn.execute(
            "SELECT gate_id FROM user_gate"
            " WHERE scene_id = ? AND status != 'CLOSED'"
            " ORDER BY gate_id ASC",
            (scene_id,),
        ).fetchall()
        for row in rows:
            gate = self.gate(str(row[0]))
            if gate is not None and gate.status is not GateStatus.CLOSED:
                return gate
        return None

    def gate(self, gate_id: str) -> UserGateRecord | None:
        """One gate row by id, or ``None`` (the library read)."""

        return get_gate(self._conn, gate_id)

    def next_gate_seq(self, scene_id: str) -> int:
        """The scene's next gate number — one past the highest gate row
        it holds (a crashed pre-submit gate keeps its number; the
        durable face wins)."""

        row = self._conn.execute(
            "SELECT COALESCE(MAX(gate_seq), 0) FROM ("
            " SELECT CAST(substr(gate_id, ?) AS INTEGER) AS gate_seq"
            " FROM user_gate WHERE scene_id = ?)",
            (len(scene_id) + 3, scene_id),
        ).fetchone()
        return int(row[0]) + 1 if row is not None else 1

    def next_segment_seq(self, scene_id: str) -> int:
        """One past the scene's committed segment count (the SEGMENT
        COMMIT's replay arm keys on this position)."""

        row = self._conn.execute(
            "SELECT COUNT(*) FROM segment_commit"
            " WHERE scene_id = ? AND kind = 'SEGMENT'",
            (scene_id,),
        ).fetchone()
        return int(row[0]) + 1 if row is not None else 1

    def continuation_owed(self, scene_id: str) -> bool:
        """Whether the scene holds a ``COMMITTED`` gate whose ruling no
        committed passage has resumed past (the recovery routing's own
        question — the V3-6R forced law's read side): a continuation
        passage's span starts at or after the ruling's own end tick."""

        gate = self.standing_gate(scene_id)
        if gate is None or gate.status is not GateStatus.COMMITTED:
            return False
        row = self._conn.execute(
            "SELECT COUNT(*) FROM segment_commit"
            " WHERE scene_id = ? AND kind = 'SEGMENT'"
            " AND actual_start_tick >= ("
            "  SELECT actual_end_tick FROM segment_commit"
            "  WHERE action_id = ? AND kind = 'ACTION_OUTCOME')",
            (scene_id, f"{gate.gate_id}-a"),
        ).fetchone()
        if row is None:
            return True
        return int(row[0]) == 0

    def offstage_narration(self, event_id: str) -> str | None:
        """The chapter's offstage settlement event's narration, or
        ``None`` — the settle re-drive's replay read (the durable face
        wins; only the stored summary line is read, never rebuilt)."""

        row = self._conn.execute(
            "SELECT narration FROM world_event WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return None if row is None else str(row[0])


def turn_steps_of(
    conn: sqlite3.Connection, chapter_id: str
) -> tuple[TurnStep, ...]:
    """The chapter's committed turn steps, in canonical order (actual
    span, then commit id) — the replay anchor derived from the durable
    rows themselves (the module docstring's §10 F8 posture: the POC
    re-runs a turn from the last committed δ; this read is where that
    δ list lives). A narration step and a ruling step are the two
    kinds; both are already-canon facts, never process state."""

    rows = conn.execute(
        "SELECT c.commit_id, c.kind, c.scene_id, c.passage_id, c.action_id,"
        " a.outcome, c.actual_start_tick, c.actual_end_tick"
        " FROM segment_commit c"
        " JOIN world_scene s ON s.scene_id = c.scene_id"
        " LEFT JOIN user_action a ON a.user_action_id = c.action_id"
        " WHERE s.chapter_id = ? AND c.kind IN ('SEGMENT', 'ACTION_OUTCOME')"
        " ORDER BY c.actual_start_tick ASC, c.actual_end_tick ASC,"
        " c.commit_id ASC",
        (chapter_id,),
    ).fetchall()
    return tuple(
        TurnStep(
            commit_id=str(row[0]),
            kind="ruling" if str(row[1]) == "ACTION_OUTCOME" else "narration",
            scene_id=str(row[2]),
            passage_id=None if row[3] is None else str(row[3]),
            action_id=None if row[4] is None else str(row[4]),
            outcome=None if row[5] is None else str(row[5]),
            actual_start_tick=int(row[6]),
            actual_end_tick=int(row[7]),
        )
        for row in rows
    )


class TurnEngine:
    """The dual-seat turn trunk over one database — the beat pipeline's
    only driver; every write is a library face's own transaction (see
    the module docstring).

    ``action_duration_ticks`` is the ruling's story-time cost (the
    Pipeline's own calibration posture: one value per engine instance
    keeps a crash retry's replay shape equal). ``language`` is the
    prose word every prompt carries (the shared ``v3_prose_language``
    setting's live value, read per drive by the face)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        world_store: SqliteWorldStore,
        cast_store: SqliteCastStore,
        bible_store: SqliteBibleStore,
        narrative_store: SqliteNarrativeStore,
        dispatcher: LlmDispatcherProvider,
        character: LlmCharacterProvider,
        adjudicator: LlmBatchAdjudicatorProvider,
        narrator: LlmNarratorProvider,
        action_duration_ticks: int,
        language: str,
        clock: Callable[[], str],
        replan_pipeline: Pipeline | None = None,
    ) -> None:
        self._conn = conn
        self._worlds = world_store
        self._casts = cast_store
        self._bibles = bible_store
        self._narrative = narrative_store
        self._dispatcher = dispatcher
        self._character = character
        self._adjudicator = adjudicator
        self._narrator = narrator
        self._duration = action_duration_ticks
        self._language = language
        self._clock = clock
        self._replan_pipeline = replan_pipeline
        self._reads = TurnReads(
            conn, narrative_store=narrative_store, world_store=world_store
        )
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
        self._calls = 0
        self._notes: list[str] = []

    # -- the drive -----------------------------------------------------------

    def drive(
        self,
        world_id: str,
        beat: OpenBeat | AdvanceBeat | ReplyBeat,
        now: str,
        *,
        on_chunk: Callable[[str], None] | None = None,
        on_stage: Callable[[str], None] | None = None,
    ) -> DriveRun:
        """Run one drive from the durable position: the recovery routing
        first (a committed-unclosed gate's owed continuation lands
        before anything else), then the requested beat, then — while
        the stop law says continue and the ceilings allow — further
        world beats. A model failure propagates (the face owns the
        sentence); a library refusal stops the drive as
        ``DriveRun.error`` with the landed beats durable."""

        self._calls = 0
        self._notes = []
        turns: list[TurnRecord] = []
        stop_log: list[StopDecision] = []
        fresh: list[str] = []
        chapter_id: str | None = None
        scene_id: str | None = None
        stopped_on = "exhausted"
        note: str | None = None
        try:
            while True:
                chapter = self._reads.current_chapter(world_id)
                if chapter is None:
                    return self._answer(
                        world_id, None, scene_id, turns, fresh, "no_chapter",
                        "还没有章——先「开始」让导演起笔。", stop_log,
                    )
                if chapter.status not in (
                    ChapterStatus.PLANNED, ChapterStatus.ACTIVE
                ):
                    # PLANNED is the opening beat's own state: the first
                    # landing activates the chapter (the commit faces'
                    # #3 law); SETTLING / CLOSED refuse.
                    return self._answer(
                        world_id, chapter.chapter_id, scene_id, turns, fresh,
                        "chapter_not_active",
                        f"本章状态是 {chapter.status.value}——先走完章间面。",
                        stop_log,
                    )
                scene = self._reads.current_scene(chapter.chapter_id)
                if scene is None:
                    return self._answer(
                        world_id, chapter.chapter_id, scene_id, turns, fresh,
                        "no_scene", "本章没有可驱动的场——检查状态。", stop_log,
                    )
                chapter_id = chapter.chapter_id
                scene_id = scene.scene_id
                if len(turns) >= DRIVE_BEAT_CEILING:
                    stopped_on = "beat_ceiling"
                    note = _BEAT_CEILING_SENTENCE.format(
                        written=len(turns), ceiling=DRIVE_BEAT_CEILING
                    )
                    self._notes.append(
                        _CEILING_ANOMALY_NOTE.format(
                            which="beat",
                            written=len(turns),
                        )
                    )
                    break
                if self._calls >= DRIVE_CALL_CEILING:
                    stopped_on = "call_ceiling"
                    note = _CALL_CEILING_SENTENCE.format(
                        ceiling=DRIVE_CALL_CEILING
                    )
                    self._notes.append(
                        _CEILING_ANOMALY_NOTE.format(
                            which="call",
                            written=len(turns),
                        )
                    )
                    break
                if self._reads.continuation_owed(scene.scene_id):
                    record = self._land_continuation(
                        world_id, chapter.chapter_id, scene, now,
                        on_chunk, on_stage,
                    )
                    turns.append(record)
                    stop_log.append(record.stop)
                    if record.passage_id is not None:
                        fresh.append(record.passage_id)
                    continue
                record = self._drive_beat(
                    world_id, chapter.chapter_id, scene, beat, now,
                    on_chunk, on_stage,
                )
                beat = AdvanceBeat()  # a drive continues as the world
                turns.append(record)
                stop_log.append(record.stop)
                if record.passage_id is not None:
                    fresh.append(record.passage_id)
                if record.stop.stopped:
                    stopped_on = record.stop.reason
                    break
                # the rhythm law (§4): beat_complete NEVER stops — the
                # drive continues (as the world) until a natural hanging
                # point, a guardrail, or a refusal; the pacing word is a
                # scheduling signal, not a stop.
        except TurnRefusal as refusal:
            return self._answer(
                world_id, chapter_id, scene_id, turns, fresh, "refused",
                f"{refusal.code}: {refusal.message}", stop_log,
                error=f"{refusal.code}: {refusal.message}",
            )
        return self._answer(
            world_id, chapter_id, scene_id, turns, fresh, stopped_on,
            note, stop_log,
        )

    # -- the chapter-end arm (DS-1 §7: 幕外自转) ------------------------------

    def settle_chapter(
        self, world_id: str, now: str
    ) -> SettleRecord:
        """Land one chapter's offstage settlement (§7): each protagonist
        gets ONE time-passage call (the private seat asked where she
        now stands, given the chapter's events and her own memory), the
        director's world summary rides the dispatch arm's world-event
        face, and the whole δ lands through ``canon_delta`` — the
        offstage event (:func:`elc.world.store.SqliteWorldStore.record_event`,
        the one atomic event + effects landing) carries the living
        goal / mood facts, the memory consolidation rides
        ``record_belief`` anchored to that same event, and the chapter
        flips ``ACTIVE → SETTLING → CLOSED`` through the library faces
        (:meth:`~elc.world.narrative.store.SqliteNarrativeStore.settle_chapter`
        then NCP-4's
        :func:`elc.world.settlement.settle_chapter` — the one-version
        compression, the tick never advanced).

        **Replay shape**: the offstage event's id derives from the
        chapter id — a crash after it lands answers the stored facts on
        the re-drive (the pre-settle calls are skipped, the flip and
        the NCP-4 compression finish the settle); the NCP-4 row itself
        is one-per-chapter by its PK (re-runs are no-ops)."""

        harness.authorize(
            harness.Tool.SETTLE_CHAPTER, harness.Principal.SPINE
        )
        calls_at_entry = self._calls
        chapter = self._reads.current_chapter(world_id)
        if chapter is None:
            raise TurnRefusal("NOT_FOUND", "没有可结算的章——先「开始」。")
        if chapter.status is ChapterStatus.CLOSED:
            raise TurnRefusal(
                "VALIDATION_FAILED",
                f"chapter {chapter.chapter_id!r} is already CLOSED — its"
                " settlement landed once and does not re-run",
            )
        scene = self._reads.current_scene(chapter.chapter_id)
        if scene is None:
            raise TurnRefusal(
                "VALIDATION_FAILED",
                f"chapter {chapter.chapter_id!r} holds no drivable scene",
            )
        dossier = self._ensure_scene_open(scene, now)
        tick = self._tick(world_id)
        event_id = f"{chapter.chapter_id}:offstage"
        player = self._casts.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        protagonists = tuple(
            participant
            for participant in dossier.participants
            if participant != player_id
        )
        if scene.status is SceneStatus.ACTIVE and self._reads.committed_segments(
            scene.scene_id
        ):
            # the SETTLING precondition (no running story): the chapter's
            # closing segment lands first — one last narration beat, the
            # scene commits, then the offstage δ and the flip follow.
            context = self._narration_context(
                world_id, dossier, "settle", None, (), ruling=None
            )
            narration = self._narrate(context, None)
            self._write_segment(
                scene.scene_id,
                narration.prose,
                self._reads.next_segment_seq(scene.scene_id),
                True,
                now,
                outcome_ref=None,
            )
        stored = self._reads.offstage_narration(event_id)
        if stored is None:
            proposals = self._gather_settle_proposals(
                world_id, dossier, protagonists, tick
            )
            decision = self._dispatch(
                world_id, dossier, tick, "settle", chapter.chapter_id, None
            )
            world_summary = decision.world_event or decision.reading
            effects: list[StateEffect] = []
            lines: list[tuple[str, str]] = []
            for proposal in proposals:
                if proposal.intent.strip():
                    effects.append(
                        StateEffect(
                            key=f"{MOOD_KEY_PREFIX}{proposal.actor_id}.goal",
                            statement=proposal.intent,
                        )
                    )
                    lines.append((proposal.actor_id, proposal.intent))
                if proposal.private_thought.strip():
                    effects.append(
                        StateEffect(
                            key=f"{MOOD_KEY_PREFIX}{proposal.actor_id}.mood",
                            statement=proposal.private_thought,
                        )
                    )
            landed = self._worlds.record_event(
                WorldEvent(
                    event_id=event_id,
                    world_id=world_id,
                    kind="offstage",
                    narration=world_summary,
                    effects=tuple(effects),
                    occurred_at=now,
                    source="ds-settle",
                    participants=protagonists,
                )
            )
            if isinstance(landed, Err):
                raise TurnRefusal(
                    landed.error.code.value, landed.error.message
                )
            self._consolidate_memory(world_id, event_id, proposals, tick, now)
        else:
            world_summary = stored
            lines = [
                (
                    fact.canonical_key.rsplit(".", 1)[0].replace(
                        MOOD_KEY_PREFIX, ""
                    ),
                    fact.statement,
                )
                for fact in self._worlds.current_facts(world_id)
                if fact.canonical_key.startswith(MOOD_KEY_PREFIX)
                and fact.canonical_key.endswith(".goal")
            ]
        if chapter.status is ChapterStatus.ACTIVE:
            flipped = self._narrative.settle_chapter(
                chapter.chapter_id,
                now,
                expected_state_version=chapter.state_version,
            )
            if isinstance(flipped, Err):
                raise TurnRefusal(
                    flipped.error.code.value, flipped.error.message
                )
        settlement = land_settlement(
            self._conn,
            narrative_store=self._narrative,
            world_store=self._worlds,
            chapter_id=chapter.chapter_id,
            now=now,
        )
        if isinstance(settlement, Err):
            raise TurnRefusal(
                settlement.error.code.value, settlement.error.message
            )
        return SettleRecord(
            chapter_id=chapter.chapter_id,
            offstage_event_id=event_id,
            world_summary=world_summary,
            protagonist_lines=tuple(lines),
            settlement_summary=settlement.value.summary,
            calls_used=self._calls - calls_at_entry,
            notes=tuple(self._notes),
        )

    def _gather_settle_proposals(
        self,
        world_id: str,
        dossier: WorldSceneDossierRecord,
        protagonists: tuple[str, ...],
        tick: int,
    ) -> tuple[CharacterProposal, ...]:
        """§7's per-protagonist time-passage calls — the private seat
        asked where she now stands (the chapter's last narration is the
        summary she lives past); the same arm, the same pack law."""

        if not protagonists:
            return ()
        harness.authorize(
            harness.Tool.DISPATCH_CHARACTER, harness.Principal.SPINE
        )
        decision = DispatchDecision(
            reading="the chapter has closed and time passes offstage",
            responders=tuple(protagonists),
            world_event=None,
            pacing="settle",
            options=(),
        )
        packs = {
            actor: self._character_pack(
                world_id,
                actor,
                dossier,
                tick,
                decision,
                "(the chapter has closed — you have not seen the"
                " reader's character since the last scene; where do you"
                " now stand, and what occupies you offstage?)",
            )
            for actor in protagonists
        }
        with ThreadPoolExecutor(max_workers=min(len(protagonists), 4)) as pool:
            futures = {
                actor: pool.submit(self._character.propose, pack)
                for actor, pack in packs.items()
            }
            for _future in futures.values():
                self._calls += 1
            return tuple(future.result() for future in futures.values())

    def _consolidate_memory(
        self,
        world_id: str,
        event_id: str,
        proposals: tuple[CharacterProposal, ...],
        tick: int,
        now: str,
    ) -> None:
        """§7's 记忆整固 — each protagonist's settled stance lands as
        her own memory row anchored to the offstage event (the same
        zero-migration form the private thoughts ride; a refusal is
        honest bookkeeping, never a drive failure)."""

        for proposal in proposals:
            content = proposal.intent.strip() or proposal.action.strip()
            if not content:
                continue
            harness.authorize(
                harness.Tool.MEMORY_WRITE, harness.Principal.CHARACTER
            )
            outcome = record_belief(
                self._conn,
                world_id=world_id,
                event_id=event_id,
                participant_id=proposal.actor_id,
                kind=MemoryKind.INFERRED,
                content=f"结算 · 我此刻的位置：{content}",
                learned_at_tick=tick,
                now=now,
            )
            if isinstance(outcome, Err):
                self._notes.append(
                    "settle memory of"
                    f" {proposal.actor_id} not landed:"
                    f" {outcome.error.code.value}: {outcome.error.message}"
                )

    # -- the beat pipelines --------------------------------------------------

    def _drive_beat(
        self,
        world_id: str,
        chapter_id: str,
        scene: WorldSceneRecord,
        beat: OpenBeat | AdvanceBeat | ReplyBeat,
        now: str,
        on_chunk: Callable[[str], None] | None,
        on_stage: Callable[[str], None] | None = None,
    ) -> TurnRecord:
        """One beat through the §1 order (see the module docstring).
        The world beats skip ① only (DS-3: 跳①不跳④) — the dispatch
        decision, the present characters' proposals, ONE world
        adjudication into δ, then the narration; nobody decides for the
        user, and nobody stands idle."""

        if isinstance(beat, ReplyBeat):
            return self._drive_reply(
                world_id, chapter_id, scene, beat, now, on_chunk, on_stage
            )
        beat_kind = "open" if isinstance(beat, OpenBeat) else "advance"
        calls_at_entry = self._calls
        dossier = self._ensure_scene_open(scene, now)
        tick = self._tick(world_id)
        # the world δ's replay anchor: the event id derives from the
        # segment position this beat lands at — a crash after the δ
        # landed answers the stored outcome on the re-drive (§10 F8:
        # the turn re-runs from the last committed δ; the narration
        # regenerates, the canon never re-lands)
        segment_seq = self._reads.next_segment_seq(scene.scene_id)
        event_id = f"{scene.scene_id}:beat-{segment_seq}"
        world_outcome = self._reads.offstage_narration(event_id)
        decision: DispatchDecision | None = None
        proposals: tuple[CharacterProposal, ...] = ()
        if world_outcome is None:
            if on_stage is not None:
                on_stage("dispatching")
            decision = self._dispatch(
                world_id, dossier, tick, beat_kind, chapter_id, None
            )
            # ④ does not skip: every present protagonist's own model
            # runs, each deciding what she does and says (§1 跳①不跳④)
            if on_stage is not None:
                on_stage("responding")
            proposals = self._gather_proposals(
                world_id, dossier, decision, None
            )
            if on_stage is not None:
                on_stage("adjudicating")
            ruling = self._adjudicate_world(
                world_id, dossier, proposals, decision.world_event
            )
            self._land_world_event(
                world_id, event_id, ruling, proposals, now
            )
            self._land_private_thoughts(world_id, event_id, proposals)
            world_outcome = ruling.outcome
            if ruling.replan_scope is not ReplanScope.NONE:
                self._notes.append(
                    "world ruling asked replan scope"
                    f" {ruling.replan_scope.value} — a world beat lands"
                    " no replan obligation (the situation plan absorbs"
                    " the pressure at the next chapter)"
                )
        else:
            self._notes.append(
                f"world beat replayed from its stored δ ({event_id})"
            )
        context = self._narration_context(
            world_id,
            dossier,
            beat_kind,
            decision,
            proposals,
            ruling=None,
            world_outcome=world_outcome,
        )
        narration = self._narrate(context, on_chunk, on_stage)
        commit = self._write_segment(
            scene.scene_id,
            narration.prose,
            self._reads.next_segment_seq(scene.scene_id),
            False,
            now,
            outcome_ref=None,
        )
        stop = self._stop_decision(
            beat_kind,
            narration,
            "" if decision is None else decision.pacing,
        )
        return TurnRecord(
            beat_kind=beat_kind,
            narration=narration.prose,
            passage_id=commit.passage_id,
            gate_id=None,
            dispatch=decision,
            proposals=proposals,
            stop=stop,
            calls_used=self._calls - calls_at_entry,
        )

    def _drive_reply(
        self,
        world_id: str,
        chapter_id: str,
        scene: WorldSceneRecord,
        beat: ReplyBeat,
        now: str,
        on_chunk: Callable[[str], None] | None,
        on_stage: Callable[[str], None] | None = None,
    ) -> TurnRecord:
        """A ``reply`` beat, end to end (§1 ①→⑧) — the durable face
        wins on every anchor: a standing gate's stored submission
        re-drives as this beat's own words."""

        calls_at_entry = self._calls
        dossier = self._ensure_scene_open(scene, now)
        standing = self._reads.standing_gate(scene.scene_id)
        standing_action = (
            None if standing is None else action_of(self._conn, standing.gate_id)
        )
        if standing_action is not None and standing_action.status is not (
            ActionStatus.COMMITTED
        ):
            # The durable face wins: this gate already holds a submission
            # (a crashed pre-commit chain) — the beat re-drives THAT one.
            beat = ReplyBeat(
                submission_id=standing_action.submission_id,
                intent_text=standing_action.intent_text,
                selected_option=standing_action.selected_option,
            )
        tick = self._tick(world_id)
        if on_stage is not None:
            on_stage("dispatching")
        decision = self._dispatch(
            world_id, dossier, tick, "reply", chapter_id, beat.intent_text
        )
        if on_stage is not None:
            on_stage("responding")
        proposals = self._gather_proposals(
            world_id, dossier, decision, beat.intent_text
        )
        if standing is None:
            gate = self._unwrap(open_gate(
                self._conn,
                scene_id=scene.scene_id,
                gate_seq=self._reads.next_gate_seq(scene.scene_id),
                options=_gate_options_of(decision, self._language),
                now=now,
            ))
        else:
            gate = standing
        action = self._unwrap(submit_gate(
            self._conn,
            gate_id=gate.gate_id,
            submission_id=beat.submission_id,
            intent_text=beat.intent_text,
            selected_option=beat.selected_option,
            now=now,
        ))
        if action.status is ActionStatus.ANSWERED:
            self._unwrap(begin_resolving(
                self._conn, gate_id=gate.gate_id, now=now
            ))
        ruling = self._stored_ruling(action)
        if ruling is None:
            if on_stage is not None:
                on_stage("adjudicating")
            ruling = self._adjudicate(
                world_id, gate, action, dossier, proposals,
                decision.world_event,
            )
        outcome = self._unwrap(commit_action(
            self._conn,
            world_store=self._worlds,
            narrative_store=self._narrative,
            gate_id=gate.gate_id,
            submission_id=action.submission_id,
            adjudication=ruling,
            duration_ticks=self._duration,
            now=now,
        ))
        self._land_private_thoughts(world_id, outcome.event_id, proposals)
        if outcome.replan_scope is not ReplanScope.NONE:
            # §1b: the replan_scope three-word semantics ride unchanged —
            # the ruling's plan verdict is consumed through the same
            # library protocol the V3 gate drive auto-routes (the
            # engine's Pipeline holds the scope faces; without it the
            # obligation stays PENDING and the settlement's own
            # precondition refuses the chapter — the honest block, never
            # a silent drop).
            if self._replan_pipeline is None:
                self._notes.append(
                    "replan obligation"
                    f" {outcome.user_action_id} left pending — the engine"
                    " holds no replan pipeline"
                )
            else:
                consumed = self._unwrap(
                    self._replan_pipeline.consume_pending_replans(
                        world_id, now
                    )
                )
                if consumed:
                    self._notes.append(
                        f"replan consumed: {len(consumed)} obligation(s)"
                        " ("
                        + ", ".join(
                            f"{c.scope.value}->{c.target_ref}"
                            for c in consumed
                        )
                        + ")"
                    )
        context = self._narration_context(
            world_id, dossier, "reply", decision, proposals, ruling=ruling
        )
        narration = self._narrate(context, on_chunk, on_stage)
        commit = self._write_segment(
            scene.scene_id,
            narration.prose,
            self._reads.next_segment_seq(scene.scene_id),
            False,
            now,
            outcome_ref=outcome.user_action_id,
        )
        stop = self._stop_decision("reply", narration, decision.pacing)
        return TurnRecord(
            beat_kind="reply",
            narration=narration.prose,
            passage_id=commit.passage_id,
            gate_id=gate.gate_id,
            dispatch=decision,
            proposals=proposals,
            stop=stop,
            calls_used=self._calls - calls_at_entry,
        )

    def _land_continuation(
        self,
        world_id: str,
        chapter_id: str,
        scene: WorldSceneRecord,
        now: str,
        on_chunk: Callable[[str], None] | None,
        on_stage: Callable[[str], None] | None = None,
    ) -> TurnRecord:
        """One committed-unclosed gate's owed continuation (the
        recovery routing): the stored ruling rides as the committed
        outcome the narration resumes, and the landing segment carries
        its ``outcome_ref`` — the gate closes in the commit (the V3-6R
        forced law; the caller re-supplies nothing)."""

        calls_at_entry = self._calls
        gate = self._reads.standing_gate(scene.scene_id)
        if gate is None:  # the routing read just saw it; honest guard
            raise TurnRefusal(
                "NOT_FOUND", f"gate of scene {scene.scene_id!r} vanished"
            )
        action = action_of(self._conn, gate.gate_id)
        if action is None:  # the FK makes this unreachable; answered honestly
            raise TurnRefusal(
                "NOT_FOUND",
                f"gate {gate.gate_id!r} holds no submission row",
            )
        ruling = self._stored_ruling(action)
        if ruling is None:
            raise TurnRefusal(
                "VALIDATION_FAILED",
                f"gate {gate.gate_id!r} owes a continuation but holds no"
                " committed ruling — a corrupted chain",
            )
        dossier = self._ensure_scene_open(scene, now)
        context = self._narration_context(
            world_id, dossier, "advance", None, (), ruling=ruling
        )
        narration = self._narrate(context, on_chunk, on_stage)
        commit = self._write_segment(
            scene.scene_id,
            narration.prose,
            self._reads.next_segment_seq(scene.scene_id),
            False,
            now,
            outcome_ref=action.user_action_id,
        )
        stop = StopDecision(
            beat_kind="advance",
            addresses_you=narration.addresses_you,
            impends_on_you=narration.impends_on_you,
            beat_complete=narration.beat_complete,
            pacing="hold",
            stopped=narration.addresses_you or narration.impends_on_you,
            reason=(
                "addresses_you"
                if narration.addresses_you
                else "impends_on_you"
                if narration.impends_on_you
                else "beat_complete"
            ),
        )
        return TurnRecord(
            beat_kind="advance",
            narration=narration.prose,
            passage_id=commit.passage_id,
            gate_id=gate.gate_id,
            dispatch=None,
            proposals=(),
            stop=stop,
            calls_used=self._calls - calls_at_entry,
        )

    # -- the arms' execution points (harness-authorized) ---------------------

    def _dispatch(
        self,
        world_id: str,
        dossier: WorldSceneDossierRecord,
        tick: int,
        beat_kind: str,
        chapter_id: str,
        user_utterance: str | None,
    ) -> DispatchDecision:
        """③ the dispatch arm's one structured decision — the spine
        executes it (the arm itself holds no power; F9)."""

        self._calls += 1

        bible = self._bibles.current_bible(world_id)
        plan = self._reads.adopted_plan(chapter_id)
        player = self._casts.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        members = {
            member.actor_id: member.name
            for member in self._director.context(world_id).cast.members
        }
        responders = tuple(
            f"{participant} ({members[participant]})"
            if participant in members
            else participant
            for participant in dossier.participants
            if participant != player_id
        )
        plan_fields: dict[str, Any] = {}
        doc = situation_face_of(plan)
        if doc is not None:
            # ③不退化 (DS-3): the scheduling input carries the chapter's
            # situation plan — the 登场 / 逼近 choices stay cross-
            # checkable against the plan's own fields
            candidates = doc.get("world_event_candidates")
            plan_fields = {
                "plan_where": str(doc.get("where_you_stand", "")),
                "plan_pressing": str(doc.get("what_presses_on_you", "")),
                "plan_open_question": str(doc.get("open_question", "")),
                "plan_pacing": str(doc.get("pacing", "")),
                "plan_candidates": tuple(
                    str(candidate)
                    for candidate in (
                        candidates if isinstance(candidates, list) else ()
                    )
                    if str(candidate).strip()
                ),
            }
        return self._dispatcher.decide(
            DispatchContext(
                world_id=world_id,
                place=dossier.place,
                current_tick=tick,
                beat_kind=beat_kind,
                chapter_goal="" if plan is None else plan.goal,
                situation=(
                    f"{dossier.place} — the reader's character"
                    f" ({player_id}) is present"
                ),
                user_utterance=user_utterance,
                responders=responders,
                recent_narration=self._reads.last_narration(
                    dossier.scene_id
                ),
                premise="" if bible is None else bible.premise,
                hard_rules="" if bible is None else bible.hard_rules,
                language=self._language,
                **plan_fields,
            )
        )

    def _gather_proposals(
        self,
        world_id: str,
        dossier: WorldSceneDossierRecord,
        decision: DispatchDecision,
        user_utterance: str | None,
    ) -> tuple[CharacterProposal, ...]:
        """④ the responding character arms **in parallel** (§2) — the
        spine dispatches each pack-compiled private seat
        (``dispatch_character`` is the spine's tool; the packs are one
        character's own faces, the shape is the door). The responder
        ids are validated against the scene's own participants first
        (the namespace discipline the identity contract rides).
        ``user_utterance`` is ``None`` on a world beat (DS-3 跳①不跳④:
        the same arms run with no words of the user's to read)."""

        player = self._casts.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        eligible = [
            participant
            for participant in dossier.participants
            if participant != player_id
        ]
        responders = [
            responder.split(" (", 1)[0].strip()
            for responder in decision.responders
        ]
        actors = [
            responder for responder in responders if responder in eligible
        ]
        if not actors:
            return ()
        harness.authorize(harness.Tool.DISPATCH_CHARACTER, harness.Principal.SPINE)
        tick = self._tick(world_id)
        packs = {
            actor: self._character_pack(
                world_id, actor, dossier, tick, decision, user_utterance
            )
            for actor in actors
        }
        with ThreadPoolExecutor(max_workers=min(len(actors), 4)) as pool:
            futures = {
                actor: pool.submit(self._character.propose, pack)
                for actor, pack in packs.items()
            }
            for actor, future in futures.items():
                self._calls += 1
            proposals = [future.result() for future in futures.values()]
        return tuple(proposals)

    def _character_pack(
        self,
        world_id: str,
        actor_id: str,
        dossier: WorldSceneDossierRecord,
        tick: int,
        decision: DispatchDecision,
        user_utterance: str | None,
    ) -> CharacterContext:
        """One private seat's context pack (§2) — the card, the durable
        profile, the retrieved memory (layered + recency-truncated),
        the living goal / mood facts, the situation, the touching event
        and the character's own perceivable face. No other
        participant's private face rides."""

        members = {
            member.actor_id: member
            for member in self._director.context(world_id).cast.members
        }
        member = members.get(actor_id)
        profile = None if member is None else member.profile
        harness.authorize(harness.Tool.MEMORY_READ, harness.Principal.CHARACTER)
        memory_read = v3_memory_view(
            self._conn, world_id=world_id, viewer_id=actor_id
        )
        if isinstance(memory_read, Err):
            raise TurnRefusal(
                memory_read.error.code.value, memory_read.error.message
            )
        cognition_read = v3_cognition_view(
            self._conn, world_id=world_id, viewer_id=actor_id
        )
        if isinstance(cognition_read, Err):
            raise TurnRefusal(
                cognition_read.error.code.value,
                cognition_read.error.message,
            )
        prefix = f"{MOOD_KEY_PREFIX}{actor_id}."
        living = [
            f"{fact.canonical_key.split('.', 2)[-1]}: {fact.statement}"
            for fact in self._worlds.current_facts(world_id)
            if fact.canonical_key.startswith(prefix)
        ]
        if user_utterance is None:
            # a world beat (DS-3 跳①不跳④): the pack reads the world's
            # own move — nobody's words to answer, the beat itself
            event = (
                "a world beat (no words of the user's) — the dispatch"
                f" reads it as: {decision.reading}"
            )
            situation = (
                f"{dossier.place} — the reader's character is present,"
                " mid-scene; the world is moving around them"
            )
        else:
            event = (
                f"the user's words, just now: {user_utterance!r}"
                f" — read as: {decision.reading}"
            )
            situation = (
                f"{dossier.place} — the reader's character is present"
                " and has just spoken"
            )
        if decision.world_event:
            event += f"; a world event inserts: {decision.world_event!r}"
        return CharacterContext(
            actor_id=actor_id,
            name="" if member is None else member.name,
            identity="" if member is None else member.identity,
            personality="" if member is None else member.personality,
            background="" if member is None else member.background,
            speech_style="" if member is None else member.speech_style,
            values="" if member is None else member.values,
            boundaries="" if member is None else member.boundaries,
            long_term_drive=(
                "" if profile is None else profile.long_term_drive
            ),
            current_arc_seed=(
                "" if profile is None else profile.current_arc_seed
            ),
            private_context=(
                "" if profile is None else profile.private_context
            ),
            goal_mood="; ".join(living),
            memories=pack_memories(memory_read.value, DS_MEMORY_CAP),
            place=dossier.place,
            current_tick=tick,
            situation=situation,
            event=event,
            perceivable=cognition_read.value,
            recent_narration=self._reads.last_narration(dossier.scene_id),
            language=self._language,
        )

    def _adjudicate(
        self,
        world_id: str,
        gate: UserGateRecord,
        action: UserActionRecord,
        dossier: WorldSceneDossierRecord,
        proposals: tuple[CharacterProposal, ...],
        world_event: str | None,
    ) -> Adjudication:
        """⑤ the ONE batch adjudication (§1b) — the world-authoritative
        arms are the resolver chain's own (the reuse the definition
        names), assembled from the same store reads
        :meth:`elc.world.pipeline.Pipeline._resolver_context_of`
        spells; the k proposals and the dispatch world event ride
        beside them. The commit (⑥) authorizes ``canon_delta`` for the
        adjudicator principal — the ruling is its product."""

        player = self._casts.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        player_cognition = None
        player_memory = None
        if player is not None:
            cognition = v3_cognition_view(
                self._conn,
                world_id=world_id,
                viewer_id=player.player_character_id,
            )
            if isinstance(cognition, Err):
                raise TurnRefusal(
                    cognition.error.code.value, cognition.error.message
                )
            player_cognition = cognition.value
            memories = v3_memory_view(
                self._conn,
                world_id=world_id,
                viewer_id=player.player_character_id,
            )
            if isinstance(memories, Err):
                raise TurnRefusal(
                    memories.error.code.value, memories.error.message
                )
            player_memory = memories.value
        pov_read = v3_cognition_view(
            self._conn, world_id=world_id, viewer_id=dossier.pov_actor_id
        )
        if isinstance(pov_read, Err):
            raise TurnRefusal(pov_read.error.code.value, pov_read.error.message)
        pov_memory = v3_memory_view(
            self._conn, world_id=world_id, viewer_id=dossier.pov_actor_id
        )
        if isinstance(pov_memory, Err):
            raise TurnRefusal(
                pov_memory.error.code.value, pov_memory.error.message
            )
        counterparts = tuple(
            profile
            for profile in (
                self._casts.actor_profile(participant)
                for participant in dossier.participants
                if participant != player_id
            )
            if profile is not None
        )
        self._calls += 1
        return self._adjudicator.adjudicate(
            BatchAdjudicationContext(
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
                cognition=pov_read.value,
                memory=pov_memory.value,
                current_tick=self._tick(world_id),
                proposals=proposals,
                world_event=world_event,
            )
        )

    def _adjudicate_world(
        self,
        world_id: str,
        dossier: WorldSceneDossierRecord,
        proposals: tuple[CharacterProposal, ...],
        world_event: str | None,
    ) -> Adjudication:
        """⑤ for a world beat (DS-3 §1 跳①不跳④) — the ONE batch
        adjudication over the k proposals beside the dispatch arm's
        optional world event, the world-authoritative arms the same
        :meth:`_adjudicate` keeps (the POV's own views, the bible, the
        settled facts), minus the user submission: no user action rides
        an ``open`` / ``advance`` beat."""

        player = self._casts.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        pov_read = v3_cognition_view(
            self._conn, world_id=world_id, viewer_id=dossier.pov_actor_id
        )
        if isinstance(pov_read, Err):
            raise TurnRefusal(pov_read.error.code.value, pov_read.error.message)
        pov_memory = v3_memory_view(
            self._conn, world_id=world_id, viewer_id=dossier.pov_actor_id
        )
        if isinstance(pov_memory, Err):
            raise TurnRefusal(
                pov_memory.error.code.value, pov_memory.error.message
            )
        counterparts = tuple(
            profile
            for profile in (
                self._casts.actor_profile(participant)
                for participant in dossier.participants
                if participant != player_id
            )
            if profile is not None
        )
        self._calls += 1
        return self._adjudicator.adjudicate_world(
            WorldAdjudicationContext(
                scene_id=dossier.scene_id,
                bible=self._bibles.current_bible(world_id),
                current_facts=self._worlds.current_facts(world_id),
                place=dossier.place,
                participants=dossier.participants,
                counterparts=counterparts,
                pov_actor_id=dossier.pov_actor_id,
                cognition=pov_read.value,
                memory=pov_memory.value,
                current_tick=self._tick(world_id),
                proposals=proposals,
                world_event=world_event,
            )
        )

    def _land_world_event(
        self,
        world_id: str,
        event_id: str,
        ruling: Adjudication,
        proposals: tuple[CharacterProposal, ...],
        now: str,
    ) -> None:
        """⑥ for a world beat — the δ lands as one chronicle event
        (the settle arm's own atomic landing face; ``canon_delta`` is
        the adjudicator principal's tool and the ruling is its
        product). Idempotent by event id: a replayed id with the same
        shape answers the stored event, a different shape is the loud
        conflict."""

        harness.authorize(
            harness.Tool.CANON_DELTA, harness.Principal.ADJUDICATOR
        )
        participants = tuple(
            dict.fromkeys(proposal.actor_id for proposal in proposals)
        )
        landed = self._worlds.record_event(
            WorldEvent(
                event_id=event_id,
                world_id=world_id,
                kind="world",
                narration=ruling.outcome,
                effects=tuple(ruling.state_effects),
                occurred_at=now,
                source="ds-world",
                participants=participants,
            )
        )
        if isinstance(landed, Err):
            raise TurnRefusal(
                landed.error.code.value, landed.error.message
            )

    def _land_private_thoughts(
        self,
        world_id: str,
        event_id: str,
        proposals: tuple[CharacterProposal, ...],
    ) -> None:
        """§2 F4: each proposal's private thought lands as ITS OWN
        character's memory row (``memory_write`` is the character
        seat's tool; per-viewer privacy is the table's own read law).
        The kind is ``INFERRED`` — the zero-migration form (the
        storage-side CHECK carries five words; the dedicated
        ``PRIVATE_THOUGHT`` kind is the registered migration blade's).
        A landing refusal is honest bookkeeping on ``DriveRun.notes``,
        never a silent drop and never a drive failure (the ruling is
        already canon)."""

        tick = self._tick(world_id)
        for proposal in proposals:
            if not proposal.private_thought.strip():
                continue
            harness.authorize(
                harness.Tool.MEMORY_WRITE, harness.Principal.CHARACTER
            )
            outcome = record_belief(
                self._conn,
                world_id=world_id,
                event_id=event_id,
                participant_id=proposal.actor_id,
                kind=MemoryKind.INFERRED,
                content=proposal.private_thought,
                learned_at_tick=tick,
                now=self._clock(),
            )
            if isinstance(outcome, Err):
                self._notes.append(
                    "private thought of"
                    f" {proposal.actor_id} not landed:"
                    f" {outcome.error.code.value}: {outcome.error.message}"
                )

    def _narrate(
        self,
        context: NarrationContext,
        on_chunk: Callable[[str], None] | None,
        on_stage: Callable[[str], None] | None = None,
    ) -> NarrationResult:
        """⑦ the narration arm (§12 item 2) — streamed when the seam
        carries the streaming face (``render_narration`` is the
        narrator's tool; the face wraps the increments)."""

        harness.authorize(
            harness.Tool.RENDER_NARRATION, harness.Principal.NARRATOR
        )
        if on_stage is not None:
            on_stage("writing")
        self._calls += 1
        return self._narrator.render(context, on_chunk=on_chunk)

    def _narration_context(
        self,
        world_id: str,
        dossier: WorldSceneDossierRecord,
        beat_kind: str,
        decision: DispatchDecision | None,
        proposals: tuple[CharacterProposal, ...],
        *,
        ruling: Adjudication | None,
        world_outcome: str | None = None,
    ) -> NarrationContext:
        """The narration arm's compiled input (§12 item 2) — the
        player's own limited-knowledge face is the whole of what the
        prose may present as known; the proposals ride their PUBLIC
        face only (speech / action — never an intent or a private
        thought: the witness filter is the context's shape)."""

        player = self._casts.player_character(world_id)
        player_id = None if player is None else player.player_character_id
        player_name = "" if player is None else player.name
        player_cognition = None
        player_memory = None
        if player is not None:
            harness.authorize(
                harness.Tool.MEMORY_READ, harness.Principal.SPINE
            )
            cognition = v3_cognition_view(
                self._conn,
                world_id=world_id,
                viewer_id=player.player_character_id,
            )
            if isinstance(cognition, Err):
                raise TurnRefusal(
                    cognition.error.code.value, cognition.error.message
                )
            player_cognition = cognition.value
            memories = v3_memory_view(
                self._conn,
                world_id=world_id,
                viewer_id=player.player_character_id,
            )
            if isinstance(memories, Err):
                raise TurnRefusal(
                    memories.error.code.value, memories.error.message
                )
            player_memory = memories.value
        public = tuple(
            (proposal.actor_id, proposal.speech, proposal.action)
            for proposal in proposals
        )
        return NarrationContext(
            world_id=world_id,
            player_id=player_id or "",
            player_name=player_name or player_id or "you",
            place=dossier.place,
            current_tick=self._tick(world_id),
            beat_kind=beat_kind,
            player_cognition=player_cognition,
            player_memory=player_memory,
            committed_outcome=None if ruling is None else ruling.outcome,
            committed_actual_action=(
                None if ruling is None else ruling.actual_action
            ),
            committed_consequences=(
                None if ruling is None else ruling.consequences
            ),
            committed_effects=(
                () if ruling is None else ruling.state_effects
            ),
            public_proposals=public,
            world_event=None if decision is None else decision.world_event,
            recent_narration=self._reads.last_narration(dossier.scene_id),
            language=self._language,
            world_outcome=world_outcome,
        )

    # -- the shared small faces ----------------------------------------------

    def _ensure_scene_open(
        self, scene: WorldSceneRecord, now: str
    ) -> WorldSceneDossierRecord:
        """The scene arm's two doors (the Pipeline's own posture): a
        ``PLANNED`` scene opens through ``ScenePlanner.open_scene``
        (dossier rev 1, scene ``ACTIVE``); an ``ACTIVE`` scene rides
        its adopted dossier; a settled scene is refused (a completed
        drive is not re-runnable)."""

        if scene.status is SceneStatus.PLANNED:
            self._unwrap(self._planner.open_scene(scene.scene_id, now))
        elif scene.status is not SceneStatus.ACTIVE:
            raise TurnRefusal(
                "VALIDATION_FAILED",
                f"scene {scene.scene_id!r} is {scene.status.value!r} —"
                " a drive opens a PLANNED scene or continues an ACTIVE"
                " one",
            )
        dossier = self._narrative.adopted_dossier(scene.scene_id)
        if dossier is None:
            raise TurnRefusal(
                "VALIDATION_FAILED",
                f"scene {scene.scene_id!r} holds no ADOPTED Dossier —"
                " the beat's plan face is its dossier",
            )
        return dossier

    def _write_segment(
        self,
        scene_id: str,
        body: str,
        segment_seq: int,
        is_last_segment: bool,
        now: str,
        *,
        outcome_ref: str | None,
    ) -> CommitOutcome:
        """The SEGMENT COMMIT (NCP-3) — the guards, the lineage, the
        tick advance, the memory arm; a replayed position answers the
        stored row (the replay keeps canon byte-stable)."""

        result = self._writer.write_segment(
            scene_id,
            body,
            self._language,
            segment_seq,
            1,
            is_last_segment,
            now,
            outcome_ref=outcome_ref,
        )
        return self._unwrap(result)

    def _stop_decision(
        self, beat_kind: str, narration: NarrationResult, pacing: str
    ) -> StopDecision:
        """⑧ the stop law (§4 + the DS-3 节奏律): the natural hanging
        points stop at 「轮到你了」 — an address or an impend;
        ``beat_complete`` NEVER stops (the drive continues, the ceilings
        are the pure guardrails). The pacing word rides the verdict as
        the scheduling signal it is. The whole verdict rides the log
        (the measurement face)."""

        addresses = narration.addresses_you
        impends = narration.impends_on_you
        if addresses:
            return StopDecision(
                beat_kind, addresses, impends, narration.beat_complete,
                pacing, True, "addresses_you",
            )
        if impends:
            return StopDecision(
                beat_kind, addresses, impends, narration.beat_complete,
                pacing, True, "impends_on_you",
            )
        return StopDecision(
            beat_kind, addresses, impends, narration.beat_complete,
            pacing, False, "beat_complete",
        )

    def _stored_ruling(
        self, action: UserActionRecord
    ) -> Adjudication | None:
        """One action row's stored ruling, or ``None`` — the
        durable-first posture (a re-driven turn re-runs from the last
        committed δ; a committed ruling is never re-judged). The
        private faces of this module mirror the reading face's own
        shape test (the eight terminal columns land together)."""

        if action.status is not ActionStatus.COMMITTED:
            return None
        if (
            action.interpretation is None
            or action.outcome is None
            or action.actual_action is None
            or action.consequences is None
            or action.state_effects is None
            or action.participants is None
            or action.replan_scope is None
        ):
            return None
        return Adjudication(
            interpretation=action.interpretation,
            outcome=action.outcome,
            actual_action=action.actual_action,
            consequences=action.consequences,
            state_effects=action.state_effects,
            participants=action.participants,
            replan_scope=action.replan_scope,
        )

    def _tick(self, world_id: str) -> int:
        """The canonical story time (the ``clock`` tool's read; the
        stamp every caller supplies remains the bookkeeping one)."""

        harness.authorize(harness.Tool.CLOCK, harness.Principal.SPINE)
        tick = read_current_tick(self._conn, world_id)
        if isinstance(tick, Err):
            raise TurnRefusal(tick.error.code.value, tick.error.message)
        return tick.value

    @staticmethod
    def _unwrap(value: Result):
        """A library ``Result``'s ``Ok`` — or the refusal that stops the
        drive (``DriveRun.error``; the landed beats stay durable)."""

        if isinstance(value, Err):
            raise TurnRefusal(
                value.error.code.value, value.error.message
            )
        return value.value

    def _answer(
        self,
        world_id: str,
        chapter_id: str | None,
        scene_id: str | None,
        turns: list[TurnRecord],
        fresh: list[str],
        stopped_on: str,
        note: str | None,
        stop_log: list[StopDecision],
        *,
        error: str | None = None,
    ) -> DriveRun:
        """One drive's assembled answer (see :class:`DriveRun`)."""

        return DriveRun(
            world_id=world_id,
            chapter_id=chapter_id,
            scene_id=scene_id,
            turns=tuple(turns),
            fresh_passage_ids=tuple(fresh),
            stopped_on=stopped_on,
            note=note,
            stop_log=tuple(stop_log),
            calls_used=self._calls,
            notes=tuple(self._notes),
            error=error,
        )


def _gate_options_of(
    decision: DispatchDecision, language: str
) -> tuple[str, ...]:
    """The dispatch decision's options as the gate's 2–4 natural
    behaviours — the usable words kept in order, padded from the
    language's fallback pair when the arm answered short (the gate
    face's own 2–4 bound is the store's; the spine pads, never
    fabricates beyond it)."""

    words = tuple(
        option.strip()
        for option in getattr(decision, "options", ())
        if isinstance(option, str) and option.strip()
    )
    if len(words) > 4:
        words = words[:4]
    if len(words) >= 2:
        return words
    fallback = {
        "en": ("Act as you see fit", "Hold back and watch"),
        "zh": ("照你想的做", "先按兵不动"),
    }.get(language, ("Act as you see fit", "Hold back and watch"))
    if not words:
        return fallback
    return (words[0], fallback[0] if words[0] != fallback[0] else fallback[1])
