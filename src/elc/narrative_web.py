"""The V3 reading face — the minimal 试读面 over the Gold Scenario
(V3-8e, TASK-OPI-cddb517c-…33 / the opening ruling
``DEC-OPI-cddb517c-…31``; REGISTER v1.7.6 item 2 designates
:mod:`elc.world.gold` for this face's reuse).

**What this module is.** The assembly layer's service half (elc root,
next to ``web.py``): the two halves the V3-8c register left to this cut —

1. **the BYOK egress adapted onto the ``TextCompletion`` seam**
   (:class:`PersonaEgressCompletion`): the persona package's
   ``OpenAICompatibleProvider`` (+ its ``SecretSource``) answers the
   world's prompts as :class:`~elc.world.llm_providers.CompletionOutcome`
   values — ``text`` on a surfaced answer, one short body-free ``error``
   code otherwise, **never a raise** (the seam's own value semantics).
   The provider is read **per call** through the live accessor the
   assembly hands over (``host.coordinator.persona_provider`` — the very
   object every letter dials): the coordinates, the secret source and
   the settings page's hot swaps all ride unchanged — **no second
   configuration face, no second credential channel**. The prompt never
   rides back in a value, and a key a hostile endpoint echoes is refused
   by the persona adapter before it can (its ``key-echo`` arm);
2. **the reading face's service half** (:class:`NarrativeWebFace`): the
   route implementations ``web.py``'s new branches ship to the host
   thread (the one-thread work queue). ``web.py`` adds the branches and
   the static entry; every semantic lives here.

**The drive policy (the durable-position law).** The reader drives the
Gold Scenario one step at a time, and **every position is derived from
the durable rows** — ``segment_commit`` / ``world_scene`` /
``user_gate`` — never from process memory: a web restart loses nothing,
and a re-opened page continues exactly where the story stands.

- the **roster** is the current adopted Blueprint's scenes whose
  ``world_scene`` rows are ``PLANNED`` / ``ACTIVE``, in ``scene_index``
  order (a scene a real replan discarded is gone from the plan and from
  the roster — the durable face wins over any script);
- the **current scene** is the roster's first ``ACTIVE`` scene, else its
  first ``PLANNED`` one;
- an **author-anchored scene**
  (:func:`elc.world.gold.gold_beats_by_scene`'s ``scene_id`` matches)
  drives on the author script: the i-th
  :class:`~elc.world.pipeline.SegmentBeat` is its i-th segment, the gate
  beat is the author's (its options are the gate's options; the
  submission is the user's own free input);
- an **open scene** (a scene a real replan created — no script) drives
  on the minimal default: **one segment per continue** (a
  :class:`~elc.world.pipeline.SegmentBeat` — one tick, language ``en``),
  and the reader's 「结束本场」 drives the closing segment with
  ``is_last_segment=True`` (the two defaults are this face's own
  calibration, stated here once);
- **one continue call = one segment** (one real writing under a real
  model). A drive that continues a scene past its first segment must
  re-present the committed prefix to the orchestrator (the V3-8b script
  law: the i-th beat is the i-th segment), so the prefix is
  **reconstructed from the durable rows** (the stored length, language
  and terminality) and every committed beat is re-driven as a replay;
- **the replay providers keep the model out of canon re-writes**: a
  committed segment's prose is durable canon and is answered from the
  row (:class:`DurableReplayWriter` — the committed passage is returned
  verbatim, never a fresh generation that would CONFLICT the library
  face's append-only replay arm), and a committed gate's ruling is
  answered from the durable ``user_action`` row
  (:class:`DurableReplayResolver`). A key with no committed row
  delegates to the real provider — **exactly one real model call per
  fresh beat**, whatever the prefix re-presents;
- the **gate** is where the story stops (STATE §23): a continue that
  reaches a gate beat with no durable row **opens the gate** and stops
  (the OPEN row is the durable stop); a gate already awaiting a
  submission is **not** driven by continue — the submission is the
  reader's own act (``/api/v3/submit``), which drives ``open → NCP-1 →
  the ruling → NCP-2 → the auto-routed replan → the continuation passage
  carrying its ``outcome_ref`` → the gate CLOSED`` — **one drive call**.
  A gate the database already holds a submission for is **re-driven from
  that durable submission** (a crashed ruling finishes; a committed
  ruling replays through the replay providers and its continuation
  lands) — the request body is the durable face's equal-or-nothing.

Two recovery steps ride the same durable reads: a chapter left
``SETTLING`` (a crashed settlement) is finished by ``advance`` (the next
step *is* its settlement), and ``next_chapter`` refuses until the latest
chapter is ``CLOSED`` (the SETTLING 前置律's flip side — a chapter's
story does not overlap the next plan).

**One derivation law, two readers.** The read half
(:class:`_DurableReads`) is built over one connection and answers the
whole state (and the walk the write routes drive from). The face builds
it over the host's own connection (on the work queue); the state poll
route serves it **off the queue** through :func:`narrative_state_ro`
over its own short read-only connection — the ``/api/teaching/current``
posture: a poll must not queue behind a generation (a drive may hold the
worker for the whole model round trip), and a poll must never 500.

**The honesty faces.** A host without the V3 legs (a stub) answers one
sentence instead of pretending; an unconfigured endpoint (no
``base_url`` / ``model``) answers the honest refusal naming the settings
face, never a fabricated passage; the reader's exposure records are
**decoupled** — ``/api/v3/ack`` writes ``reader_exposure`` rows through
:func:`elc.world.settlement.record_exposure` and touches nothing else
(N-INV-005: the record face writes no actor memory and no belief); the
page is a **separate file set** under ``webui/`` reached by URL
(``/v3``) — no main-UI entry, no main-UI change. Streaming stays the
seam's registered extension point (a later cut's explicit re-open): this
face drives blocking calls and the page renders progress by polling.

Discipline: every write path runs on the thread that opened the host's
connection (``web.py``'s work queue) and lands inside a library face's
own short transaction (this module spells ``SELECT`` reads only and no
``BEGIN``); ``now`` is read per call through the injected clock (the
``web.py`` stamp: ISO 8601 UTC, bookkeeping, never story time); no SQL
string building; no new dependency.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from elc.persona.openai_provider import OpenAICompatibleProvider
from elc.persona.types import CompiledPrompt
from elc.platform.db.epoch import RuntimeEpochFence, load_current_epoch
from elc.platform.types import Err, PersonaId
from elc.world.action import (
    ActionStatus,
    Adjudication,
    GateStatus,
    UserActionRecord,
    UserGateRecord,
    action_of,
    get_gate,
    open_gate,
)
from elc.world.bible import SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.gold import (
    ACTION_DURATION_TICKS,
    WORLD_ID,
    gold_beats_by_scene,
    seed_gold_world,
)
from elc.world.llm_providers import (
    CompletionOutcome,
    LlmDirectorProvider,
    LlmPlannerProvider,
    LlmProviderError,
    LlmResolverProvider,
    LlmWriterProvider,
    TextCompletion,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    ChapterStatus,
    SceneStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneRecord,
)
from elc.world.pipeline import GateBeat, Pipeline, SceneRun, SegmentBeat
from elc.world.settlement import (
    ChapterSettlementRecord,
    chapter_settlements_of,
    record_exposure,
)
from elc.world.store import SqliteWorldStore
from elc.world.time import read_current_tick

if TYPE_CHECKING:
    from elc.world.providers import PovContext, ResolverContext

__all__ = [
    "REASON_NO_EGRESS",
    "READER_ID",
    "DurableReplayResolver",
    "DurableReplayWriter",
    "NarrativeWebFace",
    "PersonaEgressCompletion",
    "narrative_state_ro",
    "v3_ack_request",
    "v3_continue_request",
    "v3_submit_request",
]

#: The reader the exposure records name: the local principal the whole
#: local face serves (``host.open_conversation``'s own default user id —
#: one user, one reader, no second identity channel).
READER_ID = "local-user"

#: The egress's short code for "the live provider is not an OpenAI-shaped
#: one" (a scripted double, or none at all): a body-free value, never a
#: raise, never a fabricated completion.
REASON_NO_EGRESS = "no-egress"

#: The egress adapter's two ``CompiledPrompt`` fields. The world's
#: prompts are not a persona's, so the identity and the contract name are
#: this assembly's own fixed words — they ride no prompt and no durable
#: row (the persona seam's record needs the three fields; nothing reads
#: these two back).
WORLD_PROMPT_PERSONA_ID: PersonaId = PersonaId("world-v3-narrator")
WORLD_PROMPT_CONTRACT = "world-v3-text-completion"

#: The three route grammars' one 人话 each — the caller (``web.py``'s
#: route branch) sends them verbatim as the 400 body.
V3_CONTINUE_GRAMMAR = (
    'need an empty body or a JSON object {"end_scene": true|false}'
)
V3_SUBMIT_GRAMMAR = (
    'need a JSON body {"submission_id": "...", "intent_text": "...",'
    ' "selected_option": "..."?} — or {} to re-drive the gate the'
    " database already holds a submission for"
)
V3_ACK_GRAMMAR = 'need a JSON body {"passage_ids": ["...", ...]}'

#: The one default tick an open scene's continue moves (see the module
#: docstring: the open-scene calibration, stated once).
OPEN_SCENE_SEGMENT_TICKS = 1

#: The one sentence a host without the V3 legs answers (a stub host —
#: construction is lazy, so the existing suite family's doubles never
#: reach it).
_NO_LEGS_SENTENCE = (
    "这个进程没有 V3 世界腿（app_db 连接 / 世界存储缺失）——阅读面需要"
    "一次完整装配（python -m elc web --app-db …）。"
)

#: The unavailable-state sentence the off-queue poll answers when its own
#: read-only connection cannot open at all (the reader keeps its last
#: render; the next tick retries).
_STATE_READ_FAILED = (
    "阅读状态的这一次读取没有成功（app.db 打不开或不可读）——"
    "下一个轮询会再试。"
)


def _utc_now() -> str:
    """The house stamp (``web.py``'s own): ISO 8601 UTC — bookkeeping,
    never story time."""

    return datetime.now(tz=UTC).isoformat()


def _empty_state() -> dict[str, Any]:
    """The reading state's honest empty shape — every face present, none
    invented (the page renders it without special cases)."""

    return {
        "world": None,
        "chapter": None,
        "scene": None,
        "roster": [],
        "passages": [],
        "gates": [],
        "settlement": None,
        "plan": None,
        "next": {"kind": "none", "scene_id": None, "detail": None},
        "controls": {
            "can_start": False,
            "can_continue": False,
            "can_submit": False,
            "can_end_scene": False,
            "can_settle": False,
            "can_next_chapter": False,
        },
        "reader_id": READER_ID,
        "note": None,
    }


def _not_ready_state() -> dict[str, Any]:
    return {
        "ok": False,
        "did": None,
        "error": _NO_LEGS_SENTENCE,
        **_empty_state(),
    }


def v3_continue_request(payload: object) -> tuple[str | None, bool]:
    """The continue route's grammar: no body (or ``{}``) is the plain
    continue; a JSON object carrying exactly one boolean ``end_scene``
    asks for the open scene's closing segment. Anything else is the
    400 人话."""

    if payload is None or payload == {}:
        return None, False
    if (
        isinstance(payload, dict)
        and set(payload) == {"end_scene"}
        and isinstance(payload["end_scene"], bool)
    ):
        return None, bool(payload["end_scene"])
    return V3_CONTINUE_GRAMMAR, False


def v3_submit_request(
    payload: object,
) -> tuple[str | None, dict[str, Any] | None]:
    """The submit route's grammar: the user's own submission
    (``submission_id`` / ``intent_text`` required non-empty strings, an
    optional non-empty ``selected_option``) or ``{}`` — the durable
    re-drive of a gate the database already holds a submission for.
    Anything else is the 400 人话."""

    if payload is None or payload == {}:
        return None, {}
    if not isinstance(payload, dict):
        return V3_SUBMIT_GRAMMAR, None
    if not set(payload) <= {"submission_id", "intent_text", "selected_option"}:
        return V3_SUBMIT_GRAMMAR, None
    for key in ("submission_id", "intent_text"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            return V3_SUBMIT_GRAMMAR, None
    selected = payload.get("selected_option")
    if selected is not None and (
        not isinstance(selected, str) or not selected.strip()
    ):
        return V3_SUBMIT_GRAMMAR, None
    return (
        None,
        {
            "submission_id": payload["submission_id"],
            "intent_text": payload["intent_text"],
            "selected_option": selected,
        },
    )


def v3_ack_request(
    payload: object,
) -> tuple[str | None, tuple[str, ...] | None]:
    """The ack route's grammar: ``{"passage_ids": [...]}`` — a list of
    non-empty passage ids (the ones the page rendered). Anything else is
    the 400 人话."""

    if not isinstance(payload, dict) or set(payload) != {"passage_ids"}:
        return V3_ACK_GRAMMAR, None
    raw = payload["passage_ids"]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, list):
        return V3_ACK_GRAMMAR, None
    words: list[str] = []
    for word in raw:
        if not isinstance(word, str) or not word.strip():
            return V3_ACK_GRAMMAR, None
        words.append(word)
    return None, tuple(words)


# ---------------------------------------------------------------------------
# 2a — the BYOK egress on the TextCompletion seam
# ---------------------------------------------------------------------------


class PersonaEgressCompletion:
    """The persona package's BYOK egress as a ``TextCompletion``.

    ``provider_of`` is read **per call** — the assembly hands
    ``host.coordinator.persona_provider``, so the live object every
    letter dials is the one this seam dials: the same ``base_url`` /
    ``model`` / ``secret_ref``, the same ``SecretSource`` resolution at
    send time (the key's value never enters a value this module
    answers), and the settings page's hot swap takes effect on the next
    call with no re-assembly.

    The mapping is the task's one line each way: a surfaced answer is
    ``CompletionOutcome(text=…)``; a provider failure value is
    ``CompletionOutcome(text=None, error=<short code>)`` — the persona
    adapter's own vocabulary (``not-configured`` / ``missing-secret`` /
    ``timeout`` / ``http-<status>`` / ``key-echo`` / …), body-free by
    that adapter's construction. Nothing here raises and nothing here
    ever carries the prompt or a credential back: a failure value is a
    code, and a reply that echoed the key is refused by the persona
    adapter before this seam sees it.
    """

    def __init__(self, provider_of: Callable[[], object]) -> None:
        self._provider_of = provider_of

    def complete(self, prompt: str) -> CompletionOutcome:
        """One prompt's completion — see the class docstring."""

        live = self._provider_of()
        if not isinstance(live, OpenAICompatibleProvider):
            return CompletionOutcome(text=None, error=REASON_NO_EGRESS)
        output = live.call(
            CompiledPrompt(
                persona_id=WORLD_PROMPT_PERSONA_ID,
                prompt_text=prompt,
                generation_contract=WORLD_PROMPT_CONTRACT,
            )
        )
        if output.error is not None:
            return CompletionOutcome(text=None, error=output.error)
        return CompletionOutcome(text=output.text, error=None)


# ---------------------------------------------------------------------------
# the durable replay providers (canon first — see the module docstring)
# ---------------------------------------------------------------------------


class DurableReplayWriter:
    """The Writer arm over the durable canon first.

    A segment key (``context.scene_id`` + ``context.segment_seq``) the
    database already holds is answered with its **stored** prose — the
    committed passage is canon, and a drive that re-presents it to the
    orchestrator (the script law's committed prefix) must replay it
    byte-equal; a fresh generation would CONFLICT the library face's
    append-only replay arm. A key with no committed row delegates to the
    inner writer: one real writing per fresh segment.
    """

    def __init__(
        self, conn: sqlite3.Connection, inner: LlmWriterProvider
    ) -> None:
        self._conn = conn
        self._inner = inner

    def write_segment(self, context: PovContext) -> str:
        """The stored body, or the inner writer's fresh prose."""

        row = self._conn.execute(
            "SELECT p.body FROM segment_commit c"
            " JOIN narrative_passage p ON p.passage_id = c.passage_id"
            " WHERE c.scene_id = ? AND c.segment_seq = ?"
            " AND c.kind = 'SEGMENT'",
            (context.scene_id, context.segment_seq),
        ).fetchone()
        if row is not None:
            return str(row[0])
        return self._inner.write_segment(context)


class DurableReplayResolver:
    """The Resolver arm over the durable ruling first.

    A gate whose ``user_action`` row is already ``COMMITTED`` answers the
    **stored** ruling (the seven-field
    :class:`~elc.world.action.Adjudication` the commit wrote) — a
    re-driven gate (a crashed continuation, a reader retry) must not
    re-judge what canon already holds, and
    :func:`~elc.world.action.commit_action`'s replay arm compares the
    shape it is handed. A gate with no committed ruling (absent, or still
    ``ANSWERED`` / ``RESOLVING``) delegates to the inner resolver: the
    ruling has not landed, and this call is the one that lands it.
    """

    def __init__(
        self, conn: sqlite3.Connection, inner: LlmResolverProvider
    ) -> None:
        self._conn = conn
        self._inner = inner

    def adjudicate(self, context: ResolverContext) -> Adjudication:
        """The stored ruling, or the inner resolver's fresh verdict."""

        ruling = _committed_ruling(action_of(self._conn, context.gate_id))
        if ruling is not None:
            return ruling
        return self._inner.adjudicate(context)


def _committed_ruling(stored: UserActionRecord | None) -> Adjudication | None:
    """One action row's ruling, or ``None`` — the durable shape the
    ``COMMITTED`` status promises (the eight fields land together;
    anything short of all of them is delegated instead, never guessed)."""

    if stored is None or stored.status is not ActionStatus.COMMITTED:
        return None
    if (
        stored.interpretation is None
        or stored.outcome is None
        or stored.actual_action is None
        or stored.consequences is None
        or stored.state_effects is None
        or stored.participants is None
        or stored.replan_scope is None
    ):
        return None
    return Adjudication(
        interpretation=stored.interpretation,
        outcome=stored.outcome,
        actual_action=stored.actual_action,
        consequences=stored.consequences,
        state_effects=stored.state_effects,
        participants=stored.participants,
        replan_scope=stored.replan_scope,
    )


# ---------------------------------------------------------------------------
# the durable read half (one derivation law, two readers)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CommittedSegment:
    """One committed segment as the prefix reconstruction reads it —
    every field off the durable rows (the passage's body / language, the
    commit's span and terminality)."""

    segment_seq: int
    body: str
    language: str
    duration_ticks: int
    is_last_segment: bool


@dataclass(frozen=True)
class _Walk:
    """One durable-position walk's answer: the committed **prefix** the
    orchestrator must re-present (reconstruction) and the **action
    point** the caller may drive, plus the durable rows it was read
    from.

    ``kind`` words: ``segment`` (drive the fresh beat) / ``gate_open``
    (open the gate — the reader's submission is pending) /
    ``gate_submit`` (a submission is needed, or the stored one re-drives)
    / ``scene_done`` (a corrupted script — answered honestly).
    """

    prefix: tuple[SegmentBeat | GateBeat, ...]
    kind: str
    beat: SegmentBeat | GateBeat | None
    gate: UserGateRecord | None
    stored_action: UserActionRecord | None


def _prefix_from_segments(
    committed: tuple[_CommittedSegment, ...],
) -> tuple[SegmentBeat | GateBeat, ...]:
    """One open scene's committed prefix, reconstructed from the rows
    (length, language, terminality — the stored length is the only
    duration source an open scene has)."""

    return tuple(
        SegmentBeat(
            language=segment.language,
            duration_ticks=segment.duration_ticks,
            is_last_segment=segment.is_last_segment,
        )
        for segment in committed
    )


def _fresh_passage_ids(
    prefix: Sequence[SegmentBeat | GateBeat], driven: SceneRun
) -> list[str]:
    """The segments **one drive added** — the drive's own answers minus
    the re-presented committed prefix (a replay re-writes nothing; the
    route's ``did`` says what the click wrote, and the state carries the
    whole story)."""

    prefix_segments = sum(
        1 for beat in prefix if isinstance(beat, SegmentBeat)
    )
    return [
        outcome.passage_id for outcome in driven.segments[prefix_segments:]
    ]


class _DurableReads:
    """The reading face's read half — every method a pure read over one
    connection (the stores it builds over that connection hold their
    fence unused for these tables: migrations 0023/0029 carry no
    ``write_epoch``).

    Both readers construct one: the face, over the host's own connection
    (on the work queue), and :func:`narrative_state_ro`, over its own
    short read-only connection (the poll that must not queue behind a
    drive). One derivation law, two readers — the walk the write routes
    drive from is this class's too.
    """

    def __init__(
        self, conn: sqlite3.Connection, fence: RuntimeEpochFence
    ) -> None:
        self._conn = conn
        self._worlds = SqliteWorldStore(conn, fence)
        self._narrative = SqliteNarrativeStore(conn, fence)
        #: The author-anchored scripts (one fresh mapping; the beats are
        #: frozen values — see the module docstring).
        self._anchored: dict[str, tuple[SegmentBeat | GateBeat, ...]] = (
            gold_beats_by_scene()
        )

    # -- the durable reads ---------------------------------------------------

    def _current_chapter(self) -> WorldChapterRecord | None:
        chapters = self._narrative.chapters_of(WORLD_ID)
        return chapters[-1] if chapters else None

    def _chapter_scenes(
        self, chapter_id: str
    ) -> tuple[WorldSceneRecord, ...]:
        return self._narrative.scenes_of(chapter_id)

    def _roster(
        self, chapter_id: str
    ) -> tuple[tuple[str, WorldSceneRecord], ...]:
        """The current plan's ``PLANNED`` / ``ACTIVE`` scenes, in
        ``scene_index`` order (see the module docstring).

        The plan's claim over a scene row is read the way the Director's
        own identity resolution reads it (DATA §26.2.1's L3 block): an
        element's identity is its ``scene_ref``, else its burned
        ``scene_id``, else the anchor at its own array ordinal — a
        re-planned element the Director matched to an existing anchor may
        carry neither key (the anchor it matched *is* its identity), so a
        read that demanded ``scene_id`` would lose the whole post-replan
        roster."""

        plan = self._narrative.adopted_plan(chapter_id)
        if plan is None:
            return ()
        scenes = self._chapter_scenes(chapter_id)
        by_index = {scene.scene_index: scene for scene in scenes}
        by_id = {scene.scene_id: scene for scene in scenes}
        claimed: set[int] = set()
        for ordinal, element in enumerate(plan.scenes, start=1):
            ref = element.get("scene_ref")
            scene_id = element.get("scene_id")
            if isinstance(ref, int) and not isinstance(ref, bool):
                index: int | None = int(ref)
            elif isinstance(scene_id, str) and scene_id in by_id:
                index = by_id[scene_id].scene_index
            elif ordinal in by_index:
                index = ordinal
            else:
                index = None  # a fresh element whose row is not there yet
            if index is not None and index in by_index:
                claimed.add(index)
        rows = [
            scene
            for index, scene in sorted(by_index.items())
            if index in claimed
            and scene.status in (SceneStatus.PLANNED, SceneStatus.ACTIVE)
        ]
        return tuple((scene.scene_id, scene) for scene in rows)

    def _committed_segments(
        self, scene_id: str
    ) -> tuple[_CommittedSegment, ...]:
        rows = self._conn.execute(
            "SELECT c.segment_seq, p.body, p.language,"
            " c.actual_end_tick - c.actual_start_tick, c.is_last_segment"
            " FROM segment_commit c"
            " JOIN narrative_passage p ON p.passage_id = c.passage_id"
            " WHERE c.scene_id = ? AND c.kind = 'SEGMENT'"
            " ORDER BY c.segment_seq ASC",
            (scene_id,),
        ).fetchall()
        return tuple(
            _CommittedSegment(
                segment_seq=int(row[0]),
                body=str(row[1]),
                language=str(row[2]),
                duration_ticks=int(row[3]),
                is_last_segment=bool(row[4]),
            )
            for row in rows
        )

    def _gate_of(self, scene_id: str, gate_seq: int) -> UserGateRecord | None:
        return get_gate(self._conn, f"{scene_id}-g{gate_seq:02d}")

    def _scene_gates(self, scene_id: str) -> tuple[UserGateRecord, ...]:
        rows = self._conn.execute(
            "SELECT gate_id FROM user_gate WHERE scene_id = ?"
            " ORDER BY gate_id ASC",
            (scene_id,),
        ).fetchall()
        gates: list[UserGateRecord] = []
        for row in rows:
            gate = get_gate(self._conn, str(row[0]))
            if gate is not None:
                gates.append(gate)
        return tuple(gates)

    def _stored_submission(
        self, gate: UserGateRecord
    ) -> UserActionRecord | None:
        return action_of(self._conn, gate.gate_id)

    def _chapter_passages(self, chapter_id: str) -> list[dict[str, Any]]:
        """The chapter's committed passages, in lineage order (the
        settlement's own order: actual span, then commit id)."""

        rows = self._conn.execute(
            "SELECT p.passage_id, p.scene_id, p.segment_seq, p.body,"
            " p.language FROM segment_commit c"
            " JOIN narrative_passage p ON p.passage_id = c.passage_id"
            " JOIN world_scene s ON s.scene_id = c.scene_id"
            " WHERE s.chapter_id = ? AND c.kind = 'SEGMENT'"
            " ORDER BY c.actual_start_tick ASC, c.actual_end_tick ASC,"
            " c.commit_id ASC",
            (chapter_id,),
        ).fetchall()
        return [
            {
                "passage_id": str(row[0]),
                "scene_id": str(row[1]),
                "segment_seq": int(row[2]),
                "body": str(row[3]),
                "language": str(row[4]),
            }
            for row in rows
        ]

    def _open_gates(self, chapter_id: str) -> list[dict[str, Any]]:
        """Every gate of the chapter's scenes that is not ``CLOSED`` —
        the durable stop the page renders (options and status)."""

        gates: list[dict[str, Any]] = []
        for scene in self._chapter_scenes(chapter_id):
            for gate in self._scene_gates(scene.scene_id):
                if gate.status is GateStatus.CLOSED:
                    continue
                stored = self._stored_submission(gate)
                gates.append(
                    {
                        "gate_id": gate.gate_id,
                        "scene_id": gate.scene_id,
                        "status": gate.status.value,
                        "opened_at_tick": gate.opened_at_tick,
                        "options": list(gate.options),
                        "submission_id": (
                            None if stored is None else stored.submission_id
                        ),
                        "intent_text": (
                            None if stored is None else stored.intent_text
                        ),
                    }
                )
        return gates

    def _settlement_of(
        self, chapter_id: str
    ) -> ChapterSettlementRecord | None:
        for row in chapter_settlements_of(self._conn, WORLD_ID):
            if row.chapter_id == chapter_id:
                return row
        return None

    # -- the durable-position walk -------------------------------------------

    def walk(self, scene_id: str) -> _Walk:
        """Position one scene's next step from the durable rows (the
        module docstring's law). A ``PLANNED`` scene walks the same — its
        first beat is the action point and the drive opens it."""

        committed = self._committed_segments(scene_id)
        script = self._anchored.get(scene_id)
        if script is None:
            # An open scene (a real replan's own): one segment per
            # continue; the closing beat is the reader's 「结束本场」.
            return _Walk(
                prefix=_prefix_from_segments(committed),
                kind="segment",
                beat=None,
                gate=None,
                stored_action=None,
            )
        prefix: list[SegmentBeat | GateBeat] = []
        segment_position = 0
        for beat in script:
            if isinstance(beat, SegmentBeat):
                segment_position += 1
                if segment_position <= len(committed):
                    settled = committed[segment_position - 1]
                    prefix.append(
                        SegmentBeat(
                            language=settled.language,
                            duration_ticks=settled.duration_ticks,
                            is_last_segment=settled.is_last_segment,
                        )
                    )
                    continue
                return _Walk(
                    prefix=tuple(prefix),
                    kind="segment",
                    beat=beat,
                    gate=None,
                    stored_action=None,
                )
            gate = self._gate_of(scene_id, beat.gate_seq)
            if gate is None:
                return _Walk(
                    prefix=tuple(prefix),
                    kind="gate_open",
                    beat=beat,
                    gate=None,
                    stored_action=None,
                )
            stored = self._stored_submission(gate)
            if gate.status is GateStatus.CLOSED and stored is not None:
                prefix.append(
                    GateBeat(
                        gate_seq=beat.gate_seq,
                        options=gate.options,
                        submission_id=stored.submission_id,
                        intent_text=stored.intent_text,
                        selected_option=stored.selected_option,
                    )
                )
                continue
            return _Walk(
                prefix=tuple(prefix),
                kind="gate_submit",
                beat=beat,
                gate=gate,
                stored_action=stored,
            )
        # The script is exhausted: an anchored scene's last SegmentBeat
        # carries ``is_last_segment`` and commits the scene, so reaching
        # here with an ACTIVE scene is a corrupted script — answered
        # honestly, never guessed at.
        return _Walk(
            prefix=tuple(prefix),
            kind="scene_done",
            beat=None,
            gate=None,
            stored_action=None,
        )

    def continuation_after(
        self, scene_id: str, gate_seq: int
    ) -> SegmentBeat | None:
        """The script beat after one gate — the segment that will carry
        the ruling's ``outcome_ref`` (the author script's own order;
        ``None`` when the script holds none, answered honestly)."""

        script = self._anchored.get(scene_id)
        if script is None:
            return None
        seen = False
        for beat in script:
            if isinstance(beat, GateBeat):
                seen = seen or beat.gate_seq == gate_seq
                continue
            if seen:
                return beat
        return None

    # -- the state face ------------------------------------------------------

    def state(self) -> dict[str, Any]:
        """The whole reading state, derived from the durable rows — the
        world's existence, the latest chapter (status / index), the
        roster and the current scene (status / POV), this chapter's
        committed passages (id / seq / body / language), the gates not
        ``CLOSED`` (options / status), the settlement when one landed and
        the adopted plan's summary (the «下一章» face)."""

        world = self._worlds.get_world(WORLD_ID)
        if world is None:
            return {
                "ok": True,
                "did": None,
                "error": None,
                **_empty_state(),
                "world": {
                    "exists": False,
                    "world_id": WORLD_ID,
                    "name": None,
                    "current_tick": None,
                },
                "next": {
                    "kind": "start",
                    "scene_id": None,
                    "detail": "还没有世界——点「开始」，种下 Gold 世界。",
                },
                "controls": {
                    "can_start": True,
                    "can_continue": False,
                    "can_submit": False,
                    "can_end_scene": False,
                    "can_settle": False,
                    "can_next_chapter": False,
                },
            }
        tick = read_current_tick(self._conn, WORLD_ID)
        chapter = self._current_chapter()
        payload: dict[str, Any] = {
            "ok": True,
            "did": None,
            "error": None,
            **_empty_state(),
            "world": {
                "exists": True,
                "world_id": WORLD_ID,
                "name": getattr(world, "name", None),
                "current_tick": (
                    None if isinstance(tick, Err) else tick.value
                ),
            },
        }
        if chapter is None:  # the world exists; no chapter planned yet
            payload["next"] = {
                "kind": "start",
                "scene_id": None,
                "detail": "世界在，第一幕还没计划——点「开始」让导演起笔。",
            }
            payload["controls"] = {
                "can_start": True,
                "can_continue": False,
                "can_submit": False,
                "can_end_scene": False,
                "can_settle": False,
                "can_next_chapter": False,
            }
            return payload
        payload["chapter"] = {
            "chapter_id": chapter.chapter_id,
            "chapter_index": chapter.chapter_index,
            "status": chapter.status.value,
        }
        plan = self._narrative.adopted_plan(chapter.chapter_id)
        if plan is not None:
            payload["plan"] = self._plan_face(plan)
        payload["passages"] = self._chapter_passages(chapter.chapter_id)
        payload["gates"] = self._open_gates(chapter.chapter_id)
        settlement = self._settlement_of(chapter.chapter_id)
        if settlement is not None:
            payload["settlement"] = {
                "chapter_id": settlement.chapter_id,
                "summary": settlement.summary,
                "storyline_updates": settlement.storyline_updates,
                "hooks": settlement.hooks,
                "resolved_lines": settlement.resolved_lines,
                "created_at_revision": settlement.created_at_revision,
            }
        roster = self._roster(chapter.chapter_id)
        payload["roster"] = [
            {
                "scene_id": scene_id,
                "scene_index": scene.scene_index,
                "status": scene.status.value,
                "anchored": scene_id in self._anchored,
            }
            for scene_id, scene in roster
        ]
        next_face, controls, current = self._next_face(chapter, plan, roster)
        payload["next"] = next_face
        payload["controls"] = controls
        if current is not None:
            dossier = (
                self._narrative.adopted_dossier(current.scene_id)
                if current.status is SceneStatus.ACTIVE
                else None
            )
            payload["scene"] = {
                "scene_id": current.scene_id,
                "scene_index": current.scene_index,
                "status": current.status.value,
                "pov_actor_id": (
                    None if dossier is None else dossier.pov_actor_id
                ),
                "place": None if dossier is None else dossier.place,
            }
        return payload

    @staticmethod
    def _plan_face(plan: WorldChapterPlanRecord) -> dict[str, Any]:
        return {
            "chapter_plan_id": plan.chapter_plan_id,
            "plan_revision": plan.plan_revision,
            "goal": plan.goal,
            "dramatic_question": plan.dramatic_question,
            "planned_start_tick": plan.planned_start_tick,
            "planned_end_tick": plan.planned_end_tick,
            "scene_count": len(plan.scenes),
            "places": [
                str(element.get("place", "")) for element in plan.scenes
            ],
        }

    def _next_face(
        self,
        chapter: WorldChapterRecord,
        plan: WorldChapterPlanRecord | None,
        roster: tuple[tuple[str, WorldSceneRecord], ...],
    ) -> tuple[dict[str, Any], dict[str, bool], WorldSceneRecord | None]:
        """The next-step face, the control bits and the current scene —
        the same durable derivation the write routes drive from (one
        law, two readers)."""

        controls = {
            "can_start": False,
            "can_continue": False,
            "can_submit": False,
            "can_end_scene": False,
            "can_settle": False,
            "can_next_chapter": False,
        }
        if chapter.status is ChapterStatus.CLOSED:
            controls["can_next_chapter"] = True
            return (
                {
                    "kind": "next_chapter",
                    "scene_id": None,
                    "detail": "本章已经结束——点「下一章」让导演起新的一幕。",
                },
                controls,
                None,
            )
        if plan is None:
            return (
                {
                    "kind": "none",
                    "scene_id": None,
                    "detail": (
                        "本章还没有被采纳的计划（state 面如实呈现；"
                        "重新「开始」是幂等的）。"
                    ),
                },
                controls,
                None,
            )
        if not roster:
            controls["can_settle"] = True
            return (
                {
                    "kind": "settle",
                    "scene_id": None,
                    "detail": "本章的计划场都走完了——点「结束本章」。",
                },
                controls,
                None,
            )
        current = self._current_scene(roster)
        if current is None:
            return (
                {
                    "kind": "none",
                    "scene_id": None,
                    "detail": "计划里没有可驱动的场。",
                },
                controls,
                None,
            )
        scene_id, scene = current
        walk = self.walk(scene_id)
        if walk.kind == "segment":
            controls["can_continue"] = True
            if scene_id not in self._anchored:
                controls["can_end_scene"] = True
            return (
                {
                    "kind": "segment",
                    "scene_id": scene_id,
                    "detail": "下一段由笔自己写下——点「继续」。",
                },
                controls,
                scene,
            )
        if walk.kind == "gate_open":
            controls["can_continue"] = True
            beat = walk.beat
            return (
                {
                    "kind": "gate",
                    "scene_id": scene_id,
                    "detail": (
                        "故事走到一个你想开口的地方——点「继续」把门打开。"
                    ),
                    "gate_options": (
                        list(beat.options)
                        if isinstance(beat, GateBeat)
                        else []
                    ),
                },
                controls,
                scene,
            )
        if walk.kind == "gate_submit":
            controls["can_submit"] = True
            gate = walk.gate
            return (
                {
                    "kind": "gate",
                    "scene_id": scene_id,
                    "detail": (
                        "门开着等你——写下你要说的话，或选一个自然举动。"
                        if walk.stored_action is None
                        else "这个门的裁定/续段还没有落完——直接「提交」续跑。"
                    ),
                    "gate_options": (
                        list(gate.options) if gate is not None else []
                    ),
                },
                controls,
                scene,
            )
        return (
            {
                "kind": "none",
                "scene_id": scene_id,
                "detail": "这一幕的脚本走完了，但场还没闭合——检查一下状态。",
            },
            controls,
            scene,
        )

    @staticmethod
    def _current_scene(
        roster: tuple[tuple[str, WorldSceneRecord], ...]
    ) -> tuple[str, WorldSceneRecord] | None:
        for scene_id, scene in roster:
            if scene.status is SceneStatus.ACTIVE:
                return scene_id, scene
        return roster[0] if roster else None


# ---------------------------------------------------------------------------
# the reading face's write half
# ---------------------------------------------------------------------------


class NarrativeWebFace:
    """The V3 reading face's service half — every write path runs on the
    host's thread (``web.py`` ships them through the work queue) and
    every write is a library face's own short transaction (this class
    spells no ``BEGIN``; the only SQL is read-only, in the read half).

    Construction is cheap and lazy-safe: a host without the V3 legs (a
    stub in the existing suites) answers one honest sentence per call,
    and nothing here is built eagerly.
    """

    def __init__(
        self, host: object, *, clock: Callable[[], str] | None = None
    ) -> None:
        conn = getattr(host, "db", None)
        fence = getattr(host, "fence", None)
        self._conn: sqlite3.Connection | None = conn
        self._worlds: SqliteWorldStore | None = getattr(
            host, "world_store", None
        )
        self._bibles: SqliteBibleStore | None = None
        self._casts: SqliteCastStore | None = None
        self._narrative: SqliteNarrativeStore | None = None
        self._reads: _DurableReads | None = None
        if self._conn is not None and fence is not None:
            # The stores are value-thin wrappers over this host's own
            # connection and epoch fence (the composition root's own
            # shape; the Host dataclass exposes ``world_store`` and
            # ``fence``, and the Bible / cast / narrative stores are
            # built here the way the open builds its own).
            self._bibles = SqliteBibleStore(self._conn, fence)
            self._casts = SqliteCastStore(self._conn, fence)
            self._narrative = SqliteNarrativeStore(self._conn, fence)
            self._reads = _DurableReads(self._conn, fence)
        coordinator = getattr(host, "coordinator", None)
        persona_provider = getattr(coordinator, "persona_provider", None)
        self._provider_of: Callable[[], object] = (
            persona_provider
            if callable(persona_provider)
            else (lambda: None)
        )
        self._completion: TextCompletion = PersonaEgressCompletion(
            self._provider_of
        )
        self._clock = clock if clock is not None else _utc_now

    # -- the honest refusals -------------------------------------------------

    def state(self) -> dict[str, Any]:
        """The reading state (the read half's own; see
        :meth:`_DurableReads.state`)."""

        if self._reads is None:
            return _not_ready_state()
        return self._reads.state()

    def _no_legs(self) -> dict[str, Any]:
        return _not_ready_state()

    def _refuse(self, error: str) -> dict[str, Any]:
        return {**self.state(), "ok": False, "did": None, "error": error}

    def _landed(self, did: dict[str, Any]) -> dict[str, Any]:
        """One write route's answer: the state's own faces with the
        action's fields on top (the state payload carries ``ok`` /
        ``did`` / ``error`` placeholders — the action's values win, so
        the merge order is this method's whole point)."""

        return {**self.state(), "ok": True, "did": did, "error": None}

    def _egress_refusal(self) -> str | None:
        """The endpoint preflight: an honest sentence naming the settings
        face when the live provider cannot dial out at all. The key is
        deliberately not resolved here (a read face never touches the
        credential; the send-time failure values answer that)."""

        live = self._provider_of()
        if not isinstance(live, OpenAICompatibleProvider):
            return (
                "这个进程没有接 OpenAI 兼容的模型端点——先在「设置」里"
                "填好端点与模型名（或用 --base-url / --model 启动），"
                "再回来继续。"
            )
        if not live.config.base_url or not live.config.model:
            return (
                "模型端点还没配置（base_url / model 为空）——打开「设置」"
                "填好端点与模型名，再回来继续。"
            )
        return None

    @staticmethod
    def _provider_failure(reason: str) -> str:
        return (
            f"这一次写作没有完成（{reason}）——模型端点没有给出可用的"
            "回答；重试一次即可，若一直这样，去「设置」检查端点 / "
            "模型名 / 密钥。"
        )

    def _legs_ready(self) -> bool:
        return (
            self._conn is not None
            and self._worlds is not None
            and self._bibles is not None
            and self._casts is not None
            and self._narrative is not None
            and self._reads is not None
        )

    # -- the drive -----------------------------------------------------------

    def _pipeline(self) -> Pipeline:
        """A fresh orchestrator over the host's own connection and stores
        — the replay-aware writer / resolver in front of the real egress
        (see the module docstring). Constructed per drive: the instance
        holds no state worth keeping, and the durable rows are the
        position."""

        assert (
            self._conn is not None
            and self._worlds is not None
            and self._bibles is not None
            and self._casts is not None
            and self._narrative is not None
        )
        return Pipeline(
            self._conn,
            world_store=self._worlds,
            cast_store=self._casts,
            bible_store=self._bibles,
            narrative_store=self._narrative,
            writer_provider=DurableReplayWriter(
                self._conn, LlmWriterProvider(self._completion)
            ),
            planner_provider=LlmPlannerProvider(self._completion),
            director_provider=LlmDirectorProvider(self._completion),
            resolver_provider=DurableReplayResolver(
                self._conn, LlmResolverProvider(self._completion)
            ),
            action_duration_ticks=ACTION_DURATION_TICKS,
        )

    def _drive(
        self,
        scene_id: str,
        beats: Sequence[SegmentBeat | GateBeat],
        now: str,
    ) -> tuple[SceneRun | None, str | None]:
        """One orchestrator drive, the provider failure surfaced as one
        human sentence (the ``LlmProviderError`` posture the V3-8c
        register hands to this assembly face; every other failure stays
        the loud server fact it is)."""

        try:
            driven = self._pipeline().run_scene(scene_id, beats, now)
        except LlmProviderError as exc:
            return None, self._provider_failure(exc.reason)
        if isinstance(driven, Err):
            return None, (
                f"这一步没能落下去：{driven.error.code.value}:"
                f" {driven.error.message}"
            )
        return driven.value, None

    # -- the write routes ----------------------------------------------------

    def start(self) -> dict[str, Any]:
        """The idempotent start: seed the Gold world when absent, plan
        the first chapter when the world holds none, then answer the
        state. A replay of either half is the library faces' own
        zero-write no-op."""

        if not self._legs_ready():
            return self._no_legs()
        assert (
            self._conn is not None
            and self._worlds is not None
            and self._bibles is not None
            and self._casts is not None
            and self._narrative is not None
        )
        now = self._clock()
        if self._worlds.get_world(WORLD_ID) is None:
            created = seed_gold_world(
                self._conn,
                world_store=self._worlds,
                bible_store=self._bibles,
                cast_store=self._casts,
                now=now,
            )
            if isinstance(created, Err):
                return self._refuse(
                    "Gold 世界没能落下去："
                    f"{created.error.code.value}: {created.error.message}"
                )
        if not self._narrative.chapters_of(WORLD_ID):
            refusal = self._egress_refusal()
            if refusal is not None:
                return self._refuse(refusal)
            planned = self._plan_chapter(now)
            if planned is not None:
                return self._refuse(planned)
        return self._landed({"kind": "start"})

    def advance(self, end_scene: bool) -> dict[str, Any]:
        """Drive the next step — one segment, or open the gate the
        script stops at (see the module docstring). The position is the
        durable walk's; the prefix is reconstructed; the replay
        providers keep the model out of canon re-writes."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._reads is not None
        chapter = self._reads._current_chapter()
        if chapter is None:
            return self._refuse("还没有第一幕——先点「开始」。")
        if chapter.status is ChapterStatus.CLOSED:
            return self._refuse("本章已经结束——点「下一章」。")
        if chapter.status is ChapterStatus.SETTLING:
            error = self._settle_chapter(chapter.chapter_id)
            if error is not None:
                return self._refuse(error)
            return self._landed({"kind": "settle"})
        roster = self._reads._roster(chapter.chapter_id)
        if not roster:
            return self._refuse("本章的计划场都走完了——点「结束本章」。")
        current = self._reads._current_scene(roster)
        if current is None:
            return self._refuse("计划里没有可驱动的场。")
        scene_id, scene = current
        if end_scene and scene_id in self._reads._anchored:
            return self._refuse(
                "这一幕的收束由作者脚本定席（它的最后一段自带终场）——"
                "「结束本场」只对重规划新建的场有效。"
            )
        walk = self._reads.walk(scene_id)
        if walk.kind == "gate_submit":
            if walk.stored_action is not None:
                return self._refuse(
                    "这个门已经有一个提交在库里（durable 面优先）——"
                    "直接「提交」续跑，不必再写一遍。"
                )
            return self._refuse(
                "门开着等你——写下你要说的话，或选一个自然举动。"
            )
        if walk.kind == "scene_done":
            return self._refuse(
                "这一幕的脚本走完了，但场还没闭合——检查一下状态。"
            )
        now = self._clock()
        refusal = self._egress_refusal()
        if refusal is not None:
            return self._refuse(refusal)
        if walk.kind == "gate_open":
            opened = self._open_gate_for(scene_id, scene, walk.beat, now)
            if isinstance(opened, str):
                return self._refuse(opened)
            return self._landed(
                {"kind": "gate_open", "gate_id": opened.gate_id}
            )
        beat = walk.beat
        if not isinstance(beat, SegmentBeat):
            # An open scene's beat is this face's own calibration (the
            # module docstring: one tick; the reader's 「结束本场」 is
            # the closing flag).
            beat = SegmentBeat(
                duration_ticks=OPEN_SCENE_SEGMENT_TICKS,
                is_last_segment=end_scene,
            )
        driven, error = self._drive(scene_id, (*walk.prefix, beat), now)
        if error is not None:
            return self._refuse(error)
        assert driven is not None
        return self._landed(
            {
                "kind": "segment",
                "scene_id": scene_id,
                "passage_ids": _fresh_passage_ids(walk.prefix, driven),
            }
        )

    def submit(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """The reader's own submission, end to end: the durable gate is
        located, the submission is the body's (a fresh gate) or the
        stored one (a re-drive — the durable face wins), and one drive
        carries ``open → NCP-1 → the ruling → NCP-2 → the auto-routed
        replan → the continuation passage with its outcome_ref → the gate
        CLOSED``."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._reads is not None
        chapter = self._reads._current_chapter()
        if chapter is None:
            return self._refuse("还没有第一幕——先点「开始」。")
        roster = self._reads._roster(chapter.chapter_id)
        current = self._reads._current_scene(roster) if roster else None
        if current is None:
            return self._refuse("此刻没有等你提交的门。")
        scene_id, scene = current
        walk = self._reads.walk(scene_id)
        if walk.kind not in ("gate_open", "gate_submit"):
            return self._refuse("此刻没有等你提交的门——先让故事走到那里。")
        beat = walk.beat
        if not isinstance(beat, GateBeat):
            return self._refuse("脚本状态不对——检查一下状态。")
        now = self._clock()
        refusal = self._egress_refusal()
        if refusal is not None:
            return self._refuse(refusal)
        gate = walk.gate
        if gate is None:
            opened = self._open_gate_for(scene_id, scene, beat, now)
            if isinstance(opened, str):
                return self._refuse(opened)
            gate = opened
        stored = walk.stored_action
        if stored is None:
            stored = self._reads._stored_submission(gate)
        if stored is None:
            if not request:
                return self._refuse(
                    "门开着等你——请求体要带上你的 submission_id 与"
                    " intent_text（或选一个自然举动）。"
                )
            submission = GateBeat(
                gate_seq=beat.gate_seq,
                options=gate.options,
                submission_id=str(request["submission_id"]),
                intent_text=str(request["intent_text"]),
                selected_option=request.get("selected_option"),
            )
        else:
            for key, word in (
                ("submission_id", stored.submission_id),
                ("intent_text", stored.intent_text),
                ("selected_option", stored.selected_option),
            ):
                if key in request and request[key] != word:
                    return self._refuse(
                        "这个门已经有一个提交在库里（durable 面优先）——"
                        "重试请直接提交（空请求体）。"
                    )
            submission = GateBeat(
                gate_seq=beat.gate_seq,
                options=gate.options,
                submission_id=stored.submission_id,
                intent_text=stored.intent_text,
                selected_option=stored.selected_option,
            )
        beats: list[SegmentBeat | GateBeat] = [*walk.prefix, submission]
        continuation = self._reads.continuation_after(
            scene_id, beat.gate_seq
        )
        if continuation is not None:
            beats.append(continuation)
        driven, error = self._drive(scene_id, beats, now)
        if error is not None:
            return self._refuse(error)
        assert driven is not None
        closed = [
            result.gate_id
            for result in driven.gates
            if result.status is GateStatus.CLOSED
        ]
        return self._landed(
            {
                "kind": "submit",
                "scene_id": scene_id,
                "gate_id": gate.gate_id,
                "closed_gates": closed,
                "passage_ids": _fresh_passage_ids(walk.prefix, driven),
            }
        )

    def settle(self) -> dict[str, Any]:
        """End the chapter — only when the plan's scenes are all walked
        (the roster is empty) and the reader asks for it; the flip, the
        SETTLING precondition and NCP-4 are the pipeline's own."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._reads is not None
        chapter = self._reads._current_chapter()
        if chapter is None:
            return self._refuse("还没有第一幕——先点「开始」。")
        if chapter.status is ChapterStatus.CLOSED:
            return self._landed(
                {"kind": "settle", "chapter_id": chapter.chapter_id}
            )
        roster = self._reads._roster(chapter.chapter_id)
        if roster:
            return self._refuse(
                f"本章还有 {len(roster)} 个计划中的场没有走完——先继续。"
            )
        error = self._settle_chapter(chapter.chapter_id)
        if error is not None:
            return self._refuse(error)
        return self._landed(
            {"kind": "settle", "chapter_id": chapter.chapter_id}
        )

    def next_chapter(self) -> dict[str, Any]:
        """Plan the next chapter through the real Director provider —
        only when the latest chapter is CLOSED (the SETTLING 前置律's
        flip side: a chapter's story does not overlap the next plan)."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._reads is not None
        chapter = self._reads._current_chapter()
        if chapter is None:
            return self._refuse("还没有第一幕——先点「开始」。")
        if chapter.status is not ChapterStatus.CLOSED:
            return self._refuse(
                f"本章还没结束（{chapter.status.value}）——先走完场、"
                "结束本章，再开下一章。"
            )
        refusal = self._egress_refusal()
        if refusal is not None:
            return self._refuse(refusal)
        planned = self._plan_chapter(self._clock())
        if planned is not None:
            return self._refuse(planned)
        return self._landed({"kind": "next_chapter"})

    def ack(self, passage_ids: Sequence[str]) -> dict[str, Any]:
        """Record what the page rendered: one ``reader_exposure`` row per
        passage id through
        :func:`elc.world.settlement.record_exposure` — the decoupled
        record face (never part of a commit transaction), idempotent (the
        first record wins), and N-INV-005's own seal: no actor memory, no
        belief."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._conn is not None
        now = self._clock()
        recorded: list[str] = []
        missed: list[dict[str, str]] = []
        for passage_id in passage_ids:
            outcome = record_exposure(
                self._conn,
                passage_id=passage_id,
                reader_id=READER_ID,
                now=now,
            )
            if isinstance(outcome, Err):
                missed.append(
                    {
                        "passage_id": passage_id,
                        "error": (
                            f"{outcome.error.code.value}:"
                            f" {outcome.error.message}"
                        ),
                    }
                )
            else:
                recorded.append(passage_id)
        return {
            "ok": not missed,
            "reader_id": READER_ID,
            "recorded": recorded,
            "missed": missed,
        }

    # -- the writes' helpers -------------------------------------------------

    def _plan_chapter(self, now: str) -> str | None:
        """One ``Pipeline.plan_chapter`` through the real Director
        provider; the refusal sentence, or ``None`` on success."""

        try:
            planned = self._pipeline().plan_chapter(WORLD_ID, now)
        except LlmProviderError as exc:
            return self._provider_failure(exc.reason)
        if isinstance(planned, Err):
            return (
                "第一幕没能计划出来："
                f"{planned.error.code.value}: {planned.error.message}"
            )
        return None

    def _settle_chapter(self, chapter_id: str) -> str | None:
        """One ``Pipeline.settle``; the refusal sentence, or ``None``."""

        settled = self._pipeline().settle(chapter_id, self._clock())
        if isinstance(settled, Err):
            return (
                "本章没能结束："
                f"{settled.error.code.value}: {settled.error.message}"
            )
        return None

    def _open_gate_for(
        self,
        scene_id: str,
        scene: WorldSceneRecord,
        beat: SegmentBeat | GateBeat | None,
        now: str,
    ) -> UserGateRecord | str:
        """Open the gate the script stops at: an ACTIVE scene takes it
        directly; a PLANNED scene is opened first (a scene adopts its
        dossier before it can stop). Answers the row, or the refusal
        sentence."""

        if not isinstance(beat, GateBeat):
            return "脚本状态不对——检查一下状态。"
        assert self._conn is not None
        if scene.status is SceneStatus.PLANNED:
            driven, error = self._drive(scene_id, (), now)
            if error is not None:
                return error
            assert driven is not None
        opened = open_gate(
            self._conn,
            scene_id=scene_id,
            gate_seq=beat.gate_seq,
            options=beat.options,
            now=now,
        )
        if isinstance(opened, Err):
            return (
                f"门没能打开：{opened.error.code.value}:"
                f" {opened.error.message}"
            )
        return opened.value


def narrative_state_ro(app_db_path: str) -> dict[str, Any]:
    """The reading state over its own short read-only connection — the
    ``/api/teaching/current`` posture (``web.py``'s one documented
    exception to the one-thread rule): a poll must not queue behind a
    drive that holds the work queue for a whole model round trip, and a
    poll must never 500. Any failure answers the honest unavailable
    shape; the page's next tick retries."""

    try:
        uri = Path(app_db_path).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            fence = RuntimeEpochFence(
                current=load_current_epoch(connection) or 0
            )
            return _DurableReads(connection, fence).state()
        finally:
            connection.close()
    except Exception:
        # A poll that cannot read says so in one sentence — the page's
        # next tick retries, and the drive's own response re-renders.
        # ``Exception`` (not ``sqlite3.Error``): the teaching poll's own
        # except face (web.py) — an undecodable row must not take the
        # poll's connection down with it.
        return {
            "ok": False,
            "did": None,
            "error": _STATE_READ_FAILED,
            **_empty_state(),
        }
