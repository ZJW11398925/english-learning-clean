"""The dual-seat immersion face (DS-1, the technical definition §11–§12
— the POC's own service half, elc root next to ``narrative_web.py``).

**What this module is.** The route implementations ``web.py``'s new
branches ship to the host thread (the one-thread work queue); every
semantic lives here. The page is a **separate file set** under
``webui/`` reached by URL (``/ds``) — no main-UI entry, no main-UI
change (the V3 reading face's own posture).

**The seats.** The reading face serves the **immersion seat** (§0:
second person 「你」, your limited knowledge, act at any time, natural
stops). The **director seat** is the settings face (``bible_edit``,
graded — §6 F3) and the chapter-gap face (the direction word, the
V3-8h soft-expectation law through the shared Director provider). The
two seats never blur: an edit is not a turn, a direction is not a
canon row.

**The drives.** One drive = one beat of the turn spine
(:meth:`elc.world.turns.TurnEngine.drive`), carried over **SSE** (the
web.py streaming posture): the narration's prose increments flow as
``delta`` frames (the streaming seam DS-1 re-opened — the marker tail
never reaches the wire), the one ``final`` frame carries the drive's
report beside the whole state. The state poll rides **off the queue**
(:func:`ds_state_ro` over its own short read-only connection — the
``/api/teaching/current`` posture: a poll must not queue behind a
drive, and a poll must never 500).

**The tiers.** The dispatch / batch-adjudication arms dial the
**light tier** when the ``ds_light_model`` setting names a model word
(the stage-0 probe: 3.5s vs 30.6s on the same prompt, same endpoint);
the word rides ``PersonaEgressCompletion.with_model`` — the same
coordinates, the same secret source, no second credential channel.
Empty or absent keeps the live model for every arm; §12 F11's premise
(「世界在定夺（轻短促）」) holds only under a configured light tier,
and the state face answers ``light_model`` so the page can word its
stage line honestly.

**The graded bible** (§6 F3): a textual edit lands at once (one
``revise_bible`` — the full-content CAS face; the fourteen fields ride
as given); a structural edit parks on ``ds_pending_bible`` until the
next chapter plan lands, the pending list rendered on the settings
face. ``bible_edit`` is the **director seat's** tool
(:data:`elc.world.harness.Principal.DIRECTOR_SEAT`) — the registry
authorizes every landing.

**The opening.** The POC's micro world rides
:mod:`elc.world.ds_opening` — a **draft** seed (the flag rides the
state payload as ``draft``): one situation waiting for your reply, two
protagonists, your own painter. No gold-style frozen script: the
opening beat is the live loop's first ``open`` drive.

Discipline: every write path runs on the host's thread and lands
inside a library face's own short transaction (this module's own SQL
is read-only, in the read half); ``now`` is the injected clock (ISO
8601 UTC, bookkeeping); no SQL string building; no new dependency; the
provider is read per call through the live accessor (the settings
page's hot swap lands on the next call).
"""

from __future__ import annotations

import json
import queue
import sqlite3
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from elc.narrative_web import (
    V3_PROSE_LANGUAGE_KEY,
    PersonaEgressCompletion,
    prose_language_of,
)
from elc.platform.db.app_settings import AppSettingStore
from elc.platform.db.epoch import (
    RuntimeEpochFence,
    load_current_epoch,
)
from elc.platform.types import Err
from elc.world.bible import BibleContent, SqliteBibleStore
from elc.world.cast import SqliteCastStore
from elc.world.ds_opening import (
    DS_ACTION_DURATION_TICKS,
    DS_OPENING_IS_DRAFT,
    DS_WORLD_ID,
    seed_ds_world,
)
from elc.world.ds_situation import (
    plan_situation_chapter,
    situation_face_of,
)
from elc.world.harness import Principal, Tool, authorize
from elc.world.llm_providers import (
    PROSE_LANGUAGE_DEFAULT,
    CompletionOutcome,
    LlmBatchAdjudicatorProvider,
    LlmCharacterProvider,
    LlmDispatcherProvider,
    LlmNarratorProvider,
    LlmProviderError,
    LlmSituationPlannerProvider,
)
from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import ChapterStatus
from elc.world.pipeline import Pipeline
from elc.world.store import SqliteWorldStore
from elc.world.turns import (
    AdvanceBeat,
    OpenBeat,
    ReplyBeat,
    TurnEngine,
    TurnReads,
    TurnRefusal,
    turn_steps_of,
)

if TYPE_CHECKING:
    from elc.world.narrative.types import WorldChapterPlanRecord

__all__ = [
    "DS_BIBLE_GRAMMAR",
    "DS_LIGHT_MODEL_KEY",
    "DS_PENDING_BIBLE_KEY",
    "DS_REPLY_GRAMMAR",
    "DS_STOP_NOTE_KEY",
    "DualSeatWebFace",
    "RetryingTextCompletion",
    "ds_state_ro",
    "ds_turn_request",
]


#: The light-tier setting's ``app_setting`` key: the model word the
#: dispatch / adjudication arms dial on the same endpoint (empty or
#: absent = the live model for every arm — the honest single-model
#: posture; the probe's reading rides the report).
DS_LIGHT_MODEL_KEY = "ds_light_model"

#: The last drive's stop-note seat (the V3 drive-note posture): the
#: reasoned stop's sentence (and the last stop decision's markers, as
#: one JSON line) lives here between drives; every drive clears it
#: first. Bookkeeping, never canon.
DS_STOP_NOTE_KEY = "ds_stop_note"

#: The structural bible edits' pending seat (§6 F3 分级生效): a JSON
#: list of ``{"field", "value"}`` parked until the next chapter plan
#: lands. Bookkeeping on the generic settings table — zero migration.
DS_PENDING_BIBLE_KEY = "ds_pending_bible"

#: The reply route's grammar (fail-closed, the V3 route posture).
DS_REPLY_GRAMMAR = (
    'need a JSON body {"text": "<your words>", "submission_id":'
    ' "..."/} — the id is optional (the server mints one), the words'
    " are not"
)

#: The bible-edit route's grammar.
DS_BIBLE_GRAMMAR = (
    'need a JSON body {"field": <one of the fourteen bible fields>,'
    ' "value": "<text>", "mode": "now"|"next"}'
)

#: The fourteen Bible fields (the :class:`BibleContent` vocabulary —
#: the settings face's editable rows).
_BIBLE_FIELDS = (
    "premise",
    "genre",
    "tone",
    "calendar",
    "physics",
    "magic_rules",
    "geography",
    "society",
    "politics",
    "technology",
    "religion",
    "history",
    "hard_rules",
    "narrative_preferences",
)

#: The state face's honest empty shape (the page renders it without
#: special cases). ``language`` is **not** a literal here: the shape's
#: consumers that cannot read the setting (no legs / a failed ro read)
#: answer :data:`PROSE_LANGUAGE_DEFAULT` beside the spread, and every
#: real derivation overrides the word with the live
#: ``prose_language_of`` read — the shared ``v3_prose_language`` key is
#: the one truth, never a hardcoded ``en``.
_EMPTY_STATE: dict[str, Any] = {
    "ok": True,
    "did": None,
    "error": None,
    "world": None,
    "chapter": None,
    "plan": None,
    "passages": [],
    "steps": [],
    "stop": None,
    "settlement": None,
    "bible": [],
    "pending_bible": [],
    "light_model": "",
    "draft": DS_OPENING_IS_DRAFT,
    "next": {"kind": "start", "detail": "点「开始」，种下灰隼要塞。"},
    "controls": {},
    "note": None,
}

_NO_LEGS_SENTENCE = (
    "这个进程没有 DS 世界腿（app_db 连接 / 世界存储缺失）——沉浸面需要"
    "一次完整装配（python -m elc web --app-db …）。"
)

_STATE_READ_FAILED = (
    "沉浸状态的这一次读取没有成功（app.db 打不开或不可读）——"
    "下一个轮询会再试。"
)

#: The transport-class failure reasons one automatic retry buys (the
#: DS-4 law, the technical definition §8): a mid-call transport death
#: is the endpoint's transient, not the answer's verdict. The
#: answer-class failures (``bad-shape`` / ``bad-payload`` /
#: ``no-output`` / ``http-4xx`` / ``missing-secret`` …) are NOT
#: retried — they are the fail-closed semantics' own verdicts.
_RETRYABLE_REASONS = frozenset({"timeout", "transport-error"})

#: The one pause between the first attempt and its single re-dial.
_RETRY_DELAY_SECONDS = 2.0


class RetryingTextCompletion:
    """The transport-class single retry over a ``TextCompletion`` seam
    (the DS-4 law, the technical definition §8).

    2026-10-15's endpoint windows hiccuped three times mid-drive (SSL
    EOF / empty answers) and every hiccup died straight into the user's
    drive: the scene row had already advanced, the prose had not
    landed, and the face went mute. This wrapper answers one
    ``timeout`` / ``transport-error`` outcome with a ~2s pause and
    exactly ONE re-dial — the second result rides out whatever it is
    (a second death is the honest refusal, the manual retry law stays
    as the second layer). The streaming face retries the WHOLE call (a
    mid-stream death is the same transport class; the narration is not
    landed yet, regenerating is harmless): the first attempt's
    half-rendered prose is already on the wire and stays there, the
    retry's own increments are withheld so the page never shows the
    same prose twice, and the final frame's authoritative state
    re-renders the flow whole.

    Only the DS arms dial this (the face's two tiers below); the
    persona shared transport and the V3 paths are untouched."""

    def __init__(
        self,
        inner: Any,
        *,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._inner = inner
        self._sleep = sleep if sleep is not None else time.sleep

    def complete(self, prompt: str) -> CompletionOutcome:
        """One prompt's completion with the one transport-class retry."""

        outcome = self._inner.complete(prompt)
        if outcome.error not in _RETRYABLE_REASONS:
            return outcome
        self._sleep(_RETRY_DELAY_SECONDS)
        return self._inner.complete(prompt)

    def complete_streaming(
        self, prompt: str, on_chunk: Callable[[str], None]
    ) -> CompletionOutcome:
        """The streaming face's whole-call retry — the dead first
        attempt's streamed increments are dropped on the floor (they
        already reached the wire), the retry streams nowhere and
        returns the honest whole for the parser and the final render."""

        outcome = self._inner.complete_streaming(prompt, on_chunk)
        if outcome.error not in _RETRYABLE_REASONS:
            return outcome
        self._sleep(_RETRY_DELAY_SECONDS)
        return self._inner.complete_streaming(prompt, lambda _chunk: None)


def _utc_now() -> str:
    """The house stamp (web.py's own): ISO 8601 UTC."""

    return datetime.now(tz=UTC).isoformat()


def ds_turn_request(payload: object) -> tuple[str | None, dict[str, Any] | None]:
    """The reply route's grammar: exactly ``{"text": <non-empty str>}``
    plus an optional non-empty ``submission_id``; anything else is the
    400 人话."""

    if not isinstance(payload, dict):
        return DS_REPLY_GRAMMAR, None
    if not set(payload) <= {"text", "submission_id"}:
        return DS_REPLY_GRAMMAR, None
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return DS_REPLY_GRAMMAR, None
    submission_id = payload.get("submission_id")
    if submission_id is not None and (
        not isinstance(submission_id, str) or not submission_id.strip()
    ):
        return DS_REPLY_GRAMMAR, None
    return None, {
        "text": text,
        "submission_id": (
            submission_id.strip() if submission_id else None
        ),
    }


def ds_bible_request(payload: object) -> tuple[str | None, dict[str, Any] | None]:
    """The bible-edit route's grammar: one known field, a non-empty
    value, one graded mode word."""

    if not isinstance(payload, dict):
        return DS_BIBLE_GRAMMAR, None
    if set(payload) != {"field", "value", "mode"}:
        return DS_BIBLE_GRAMMAR, None
    if payload["field"] not in _BIBLE_FIELDS:
        return DS_BIBLE_GRAMMAR, None
    if not isinstance(payload["value"], str) or not payload["value"].strip():
        return DS_BIBLE_GRAMMAR, None
    if payload["mode"] not in ("now", "next"):
        return DS_BIBLE_GRAMMAR, None
    return None, dict(payload)


def _stop_note_of(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """The stored stop line — the state face's ``stop`` (the last
    drive's reasoned stop, markers and sentence)."""

    row = conn.execute(
        "SELECT value FROM app_setting WHERE key = ?",
        (DS_STOP_NOTE_KEY,),
    ).fetchone()
    if row is None:
        return None
    try:
        parsed = json.loads(str(row[0]))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _pending_bible_of(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """The parked structural edits (§6 F3) — the settings face's
    待落 list."""

    row = conn.execute(
        "SELECT value FROM app_setting WHERE key = ?",
        (DS_PENDING_BIBLE_KEY,),
    ).fetchone()
    if row is None:
        return []
    try:
        parsed = json.loads(str(row[0]))
    except ValueError:
        return []
    return parsed if isinstance(parsed, list) else []


def _light_model_of(conn: sqlite3.Connection) -> str:
    """The effective light-tier word (empty = follow the live model)."""

    row = conn.execute(
        "SELECT value FROM app_setting WHERE key = ?",
        (DS_LIGHT_MODEL_KEY,),
    ).fetchone()
    return "" if row is None else str(row[0])


class DualSeatWebFace:
    """The dual-seat immersion face's service half — every write path
    runs on the host's thread (web.py ships them through the work
    queue) and every write is a library face's own short transaction.
    Construction is cheap and lazy-safe (the reading face's own
    posture)."""

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
        self._reads: TurnReads | None = None
        if conn is not None and fence is not None and self._worlds is not None:
            self._bibles = SqliteBibleStore(conn, fence)
            self._casts = SqliteCastStore(conn, fence)
            self._narrative = SqliteNarrativeStore(conn, fence)
            self._reads = TurnReads(
                conn, narrative_store=self._narrative,
                world_store=self._worlds,
            )
        coordinator = getattr(host, "coordinator", None)
        persona_provider = getattr(coordinator, "persona_provider", None)
        self._provider_of: Callable[[], object] = (
            persona_provider
            if callable(persona_provider)
            else (lambda: None)
        )
        self._app_settings: AppSettingStore | None = getattr(
            host, "app_settings", None
        )
        # The two tiers ride the ONE egress adapter: the main tier for
        # the character / narrator arms, the light tier (when the
        # setting names a word) for the dispatch / adjudication arms.
        # Both dial through the DS-4 transport-class retry — the
        # endpoint's transient deaths pause ~2s and re-dial exactly
        # once before the refusal reaches the user.
        self._completion = RetryingTextCompletion(
            PersonaEgressCompletion(self._provider_of)
        )
        self._light_completion = RetryingTextCompletion(
            PersonaEgressCompletion(
                self._provider_of, model_of=self._light_model
            )
        )
        self._clock = clock if clock is not None else _utc_now

    # -- the honest refusals -------------------------------------------------

    def _legs_ready(self) -> bool:
        return (
            self._conn is not None
            and self._worlds is not None
            and self._bibles is not None
            and self._casts is not None
            and self._narrative is not None
            and self._reads is not None
        )

    def _no_legs(self) -> dict[str, Any]:
        return {
            "ok": False,
            "did": None,
            "error": _NO_LEGS_SENTENCE,
            **_EMPTY_STATE,
            "language": PROSE_LANGUAGE_DEFAULT,
        }

    def _refuse(self, error: str) -> dict[str, Any]:
        return {**self.state(), "ok": False, "did": None, "error": error}

    def _landed(self, did: dict[str, Any]) -> dict[str, Any]:
        return {**self.state(), "ok": True, "did": did, "error": None}

    def _egress_refusal(self) -> str | None:
        """The endpoint preflight (the reading face's own posture)."""

        live = self._provider_of()
        configured = getattr(getattr(live, "config", None), "base_url", None)
        model = getattr(getattr(live, "config", None), "model", None)
        if configured is None and model is None:
            return (
                "这个进程没有接 OpenAI 兼容的模型端点——先在「设置」里"
                "填好端点与模型名，再回来继续。"
            )
        if not configured or not model:
            return (
                "模型端点还没配置（base_url / model 为空）——打开「设置」"
                "填好端点与模型名，再回来继续。"
            )
        return None

    @staticmethod
    def _provider_failure(reason: str) -> str:
        """One failure code as one actionable human sentence (the
        reading face's own posture, the DS face's voice)."""

        if reason == "timeout":
            return (
                "模型这一次想了太久、超过了等待上限（约 180 秒）——"
                "再点一次重试；若一直这样，换更快的模型 / 端点。"
            )
        if reason in ("http-401", "missing-secret", "key-echo"):
            return (
                f"模型端点没能通过这把密钥（{reason}）——打开「设置」"
                "检查端点与密钥，保存后再回来继续。"
            )
        if reason in ("not-configured", "no-egress"):
            return (
                f"这个进程没有可用的模型端点（{reason}）——先在「设置」"
                "里填好端点与模型名，再回来继续。"
            )
        if reason == "http-429":
            return "模型端点限流了（http-429）——等一会儿再点一次。"
        return (
            f"这一次没有完成（{reason}）——模型端点没有给出可用的回答；"
            "重试一次即可。"
        )

    # -- the settings reads --------------------------------------------------

    def _light_model(self) -> str:
        if self._conn is None:
            return ""
        return _light_model_of(self._conn)

    def _prose_language(self) -> str:
        if self._conn is None:
            return "en"
        return prose_language_of(self._conn)

    def _write_bookkeeping(self, key: str, value: str | None) -> None:
        """One bookkeeping upsert/delete on the host's generic settings
        table (the V3 drive-note posture: an unchanged word writes
        nothing; a host without the settings leg skips the persistence
        and the answer still carries the value)."""

        if self._app_settings is None:
            return
        try:
            current = self._app_settings.get(key)
            if value is None:
                if current is not None:
                    self._app_settings.delete(key)
                return
            if current != value:
                self._app_settings.set(key, value)
        except Exception:  # noqa: BLE001 — bookkeeping never outweighs canon
            return

    # -- the engine ----------------------------------------------------------

    def _engine(self) -> TurnEngine:
        """A fresh turn trunk over the host's own connection and stores
        — the arms over the two tiers, the language read live (a switch
        lands on the very next drive), the clock injected."""

        conn = self._conn
        worlds = self._worlds
        bibles = self._bibles
        casts = self._casts
        narrative = self._narrative
        assert (
            conn is not None
            and worlds is not None
            and bibles is not None
            and casts is not None
            and narrative is not None
        )
        language = self._prose_language()
        return TurnEngine(
            conn,
            world_store=worlds,
            cast_store=casts,
            bible_store=bibles,
            narrative_store=narrative,
            dispatcher=LlmDispatcherProvider(
                self._light_completion, language=language
            ),
            character=LlmCharacterProvider(
                self._completion, language=language
            ),
            adjudicator=LlmBatchAdjudicatorProvider(
                self._light_completion, language=language
            ),
            narrator=LlmNarratorProvider(
                self._completion, language=language
            ),
            action_duration_ticks=DS_ACTION_DURATION_TICKS,
            language=language,
            clock=self._clock,
            replan_pipeline=self._planner(),
        )

    def _planner(self) -> Pipeline:
        """A fresh chapter pipeline — kept for the **replan
        consumption** the spine owes (the SCENE / CHAPTER protocol arms)
        and nothing else: the /ds product path PLANS through the
        situation machine (:meth:`_plan_situation`, DS-3 §6), never
        through the blueprint machine (``plan_chapter`` — the retired
        test face; the plan-gate production is the replaced V3-8i face,
        §6 F2)."""

        conn = self._conn
        worlds = self._worlds
        bibles = self._bibles
        casts = self._casts
        narrative = self._narrative
        assert (
            conn is not None
            and worlds is not None
            and bibles is not None
            and casts is not None
            and narrative is not None
        )
        language = self._prose_language()
        from elc.world.llm_providers import (
            LlmDirectorProvider,
            LlmPlannerProvider,
            LlmResolverProvider,
            LlmWriterProvider,
        )

        return Pipeline(
            conn,
            world_store=worlds,
            cast_store=casts,
            bible_store=bibles,
            narrative_store=narrative,
            writer_provider=LlmWriterProvider(
                self._completion, language=language
            ),
            planner_provider=LlmPlannerProvider(
                self._completion, language=language
            ),
            director_provider=LlmDirectorProvider(
                self._completion, language=language
            ),
            resolver_provider=LlmResolverProvider(
                self._completion, language=language
            ),
            action_duration_ticks=DS_ACTION_DURATION_TICKS,
            require_plan_gates=False,
        )

    def _situation_planner(self) -> LlmSituationPlannerProvider:
        """The situation planner arm over the main completion (the
        director seat's own tier), the language read live."""

        return LlmSituationPlannerProvider(
            self._completion, language=self._prose_language()
        )

    def _plan_situation(
        self, author_direction: str | None = None
    ) -> str | None:
        """Plan the world's next chapter through the situation machine
        (DS-3 §6) — the refusal sentence, or ``None`` on a landing. The
        legs are the caller's own invariant (every caller checks
        :meth:`_legs_ready` first)."""

        assert (
            self._conn is not None
            and self._worlds is not None
            and self._bibles is not None
            and self._casts is not None
            and self._narrative is not None
        )
        planned = plan_situation_chapter(
            self._conn,
            world_store=self._worlds,
            cast_store=self._casts,
            bible_store=self._bibles,
            narrative_store=self._narrative,
            planner=self._situation_planner(),
            world_id=DS_WORLD_ID,
            now=self._clock(),
            author_direction=author_direction,
        )
        if isinstance(planned, Err):
            return (
                "这一章的情境没能计划出来："
                f"{planned.error.code.value}: {planned.error.message}"
            )
        return None

    # -- the state face ------------------------------------------------------

    def state(self) -> dict[str, Any]:
        """The whole immersion state, derived from the durable rows (the
        read half; the ro poll calls the same derivation over its own
        connection)."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._conn is not None and self._reads is not None
        return _derive_state(
            self._conn, self._reads, self._prose_language(),
            self._light_model(),
        )

    # -- the write routes ----------------------------------------------------

    def start(self) -> dict[str, Any]:
        """The idempotent start: seed the draft opening world when
        absent, plan the first chapter as a SITUATION when the world
        holds none (DS-3 §6 — the four questions; the blueprint machine
        is the retired test face), then answer the state."""

        if not self._legs_ready():
            return self._no_legs()
        assert (
            self._conn is not None and self._worlds is not None
            and self._bibles is not None and self._casts is not None
            and self._narrative is not None
        )
        now = self._clock()
        if self._worlds.get_world(DS_WORLD_ID) is None:
            created = seed_ds_world(
                self._conn,
                world_store=self._worlds,
                bible_store=self._bibles,
                cast_store=self._casts,
                now=now,
            )
            if isinstance(created, Err):
                return self._refuse(
                    "开局世界没能落下去："
                    f"{created.error.code.value}: {created.error.message}"
                )
            # the user's own ruling (DS-3, 2026-10-15): the opening's
            # prose is Chinese — the SHARED word lands once, at the seed
            # (the language button keeps its switch; the V3 reading face
            # reads the same key; existing passages never rewrite)
            self._write_bookkeeping(V3_PROSE_LANGUAGE_KEY, "zh")
        if not self._narrative.chapters_of(DS_WORLD_ID) or (
            self._narrative.adopted_plan(
                self._narrative.chapters_of(DS_WORLD_ID)[
                    -1
                ].chapter_id
            )
            is None
        ):
            # no chapter yet, or the latest chapter holds no ADOPTED plan
            # (a crashed open — the situation machine's residue law
            # reuses that chapter and re-casts; a start after the crash
            # must never be a permanent no-op)
            refusal = self._egress_refusal()
            if refusal is not None:
                return self._refuse(refusal)
            try:
                failure = self._plan_situation()
            except LlmProviderError as exc:
                return self._refuse(self._provider_failure(exc.reason))
            if failure is not None:
                return self._refuse(failure)
        return self._landed({"kind": "start"})

    def drive_beat(
        self,
        action: str,
        events: "queue.Queue[str | dict[str, Any]]",
        *,
        text: str | None = None,
        submission_id: str | None = None,
    ) -> dict[str, Any]:
        """One SSE drive (``open`` / ``advance`` / ``reply``) — the turn
        spine runs the beat, the narration's increments flow onto the
        event queue as they arrive, and the answer is the state beside
        the drive's report (the one ``final`` frame's payload)."""

        if not self._legs_ready():
            return self._no_legs()
        refusal = self._egress_refusal()
        if refusal is not None:
            return self._refuse(refusal)
        self._write_bookkeeping(DS_STOP_NOTE_KEY, None)
        now = self._clock()
        beat: OpenBeat | AdvanceBeat | ReplyBeat
        if action == "open":
            beat = OpenBeat()
        elif action == "advance":
            beat = AdvanceBeat()
        elif action == "reply":
            if text is None or not text.strip():
                return self._refuse(DS_REPLY_GRAMMAR)
            beat = ReplyBeat(
                submission_id=submission_id
                or f"ds-web-{now}",
                intent_text=text,
            )
        else:
            return self._refuse(f"unknown drive action {action!r}")
        try:
            run = self._engine().drive(
                DS_WORLD_ID,
                beat,
                now,
                on_chunk=lambda chunk: events.put(chunk),
                on_stage=lambda stage: events.put(
                    {"type": "stage", "stage": stage}
                ),
            )
        except LlmProviderError as exc:
            return self._refuse(self._provider_failure(exc.reason))
        note = run.note
        stop_line = None
        if run.turns:
            last = run.turns[-1].stop
            stop_line = {
                "beat_kind": last.beat_kind,
                "addresses_you": last.addresses_you,
                "impends_on_you": last.impends_on_you,
                "beat_complete": last.beat_complete,
                "pacing": last.pacing,
                "stopped": last.stopped,
                "reason": last.reason,
            }
        if note or stop_line is not None:
            self._write_bookkeeping(
                DS_STOP_NOTE_KEY,
                json.dumps(
                    {"note": note, "stopped_on": run.stopped_on,
                     "last": stop_line},
                    ensure_ascii=False,
                ),
            )
        did = {
            "kind": action,
            "stopped_on": run.stopped_on,
            "note": note,
            "passage_ids": list(run.fresh_passage_ids),
            "segments_written": len(run.fresh_passage_ids),
            "stop_log": [
                {
                    "beat_kind": stop.beat_kind,
                    "addresses_you": stop.addresses_you,
                    "impends_on_you": stop.impends_on_you,
                    "beat_complete": stop.beat_complete,
                    "pacing": stop.pacing,
                    "stopped": stop.stopped,
                    "reason": stop.reason,
                }
                for stop in run.stop_log
            ],
            "calls_used": run.calls_used,
            "notes": list(run.notes),
        }
        payload = self.state()
        payload["ok"] = run.error is None
        payload["did"] = did
        payload["error"] = run.error
        return payload

    def settle(self) -> dict[str, Any]:
        """Land the chapter's offstage settlement (§7) — the per-
        protagonist time-passage calls, the world summary δ, the
        memory consolidation, then the flip and the NCP-4 compression
        (the engine's own face)."""

        if not self._legs_ready():
            return self._no_legs()
        self._write_bookkeeping(DS_STOP_NOTE_KEY, None)
        try:
            record = self._engine().settle_chapter(
                DS_WORLD_ID, self._clock()
            )
        except LlmProviderError as exc:
            return self._refuse(self._provider_failure(exc.reason))
        except TurnRefusal as exc:
            return self._refuse(f"{exc.code}: {exc.message}")
        return self._landed(
            {
                "kind": "settle",
                "chapter_id": record.chapter_id,
                "world_summary": record.world_summary,
                "protagonist_lines": [
                    {"actor_id": actor, "line": line}
                    for actor, line in record.protagonist_lines
                ],
                "settlement_summary": record.settlement_summary,
                "calls_used": record.calls_used,
                "notes": list(record.notes),
            }
        )

    def next_chapter(self, direction: str | None = None) -> dict[str, Any]:
        """Plan the next chapter (the director seat's word: a soft
        expectation, the V3-8h law) — only when the latest chapter is
        CLOSED; the parked structural bible edits land here (§6 F3:
        「下一章生效」)."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._conn is not None and self._reads is not None
        chapter = self._reads.current_chapter(DS_WORLD_ID)
        if chapter is None:
            return self._refuse("还没有第一幕——先「开始」。")
        if chapter.status is not ChapterStatus.CLOSED:
            return self._refuse(
                f"本章还没结束（{chapter.status.value}）——先走完沉浸拍、"
                "结束本章，再开下一章。"
            )
        refusal = self._egress_refusal()
        if refusal is not None:
            return self._refuse(refusal)
        applied = self._apply_pending_bible()
        if applied is not None:
            return self._refuse(applied)
        try:
            failure = self._plan_situation(direction)
        except LlmProviderError as exc:
            return self._refuse(self._provider_failure(exc.reason))
        if failure is not None:
            return self._refuse(failure)
        return self._landed({"kind": "next_chapter"})

    def bible_edit(
        self, field: str, value: str, mode: str
    ) -> dict[str, Any]:
        """One graded bible edit (§6 F3; ``bible_edit`` is the director
        seat's tool): a textual edit lands at once (one
        ``revise_bible``, the full-content CAS face); a structural edit
        parks until the next chapter plan lands."""

        if not self._legs_ready():
            return self._no_legs()
        assert self._conn is not None and self._bibles is not None
        authorize(Tool.BIBLE_EDIT, Principal.DIRECTOR_SEAT)
        if mode == "next":
            pending = _pending_bible_of(self._conn)
            pending.append({"field": field, "value": value})
            self._write_bookkeeping(
                DS_PENDING_BIBLE_KEY, json.dumps(pending, ensure_ascii=False)
            )
            return self._landed(
                {"kind": "bible_edit", "field": field, "mode": mode}
            )
        bible = self._bibles.current_bible(DS_WORLD_ID)
        if bible is None:
            return self._refuse("这个世界还没有设定——先「开始」。")
        content = _bible_content_of(bible, {field: value})
        outcome = self._bibles.revise_bible(
            f"{DS_WORLD_ID}-bible-r{bible.revision + 1}",
            DS_WORLD_ID,
            content,
            expected_bible_revision_id=bible.bible_revision_id,
            expected_state_version=bible.state_version,
            now=self._clock(),
        )
        if isinstance(outcome, Err):
            return self._refuse(
                f"设定没能落下去：{outcome.error.code.value}:"
                f" {outcome.error.message}"
            )
        return self._landed(
            {"kind": "bible_edit", "field": field, "mode": mode}
        )

    def set_light_model(self, word: str) -> dict[str, Any]:
        """The light-tier word (the settings face; empty = follow the
        live model). Bookkeeping on the shared settings table."""

        if not self._legs_ready():
            return self._no_legs()
        if word.strip():
            self._write_bookkeeping(DS_LIGHT_MODEL_KEY, word.strip())
        else:
            self._write_bookkeeping(DS_LIGHT_MODEL_KEY, None)
        return self._landed(
            {"kind": "light_model", "light_model": self._light_model()}
        )

    # -- the graded bible's internals ---------------------------------------

    def _apply_pending_bible(self) -> str | None:
        """Fold the parked structural edits into ONE revision at the
        chapter gap (§6 F3) — the refusal sentence, or ``None``."""

        assert self._conn is not None and self._bibles is not None
        pending = _pending_bible_of(self._conn)
        if not pending:
            return None
        bible = self._bibles.current_bible(DS_WORLD_ID)
        if bible is None:
            return "这个世界还没有设定——无从落下一章的改动。"
        authorize(Tool.BIBLE_EDIT, Principal.DIRECTOR_SEAT)
        content = _bible_content_of(
            bible, {edit["field"]: edit["value"] for edit in pending}
        )
        outcome = self._bibles.revise_bible(
            f"{DS_WORLD_ID}-bible-r{bible.revision + 1}",
            DS_WORLD_ID,
            content,
            expected_bible_revision_id=bible.bible_revision_id,
            expected_state_version=bible.state_version,
            now=self._clock(),
        )
        if isinstance(outcome, Err):
            return (
                "待落设定没能随新章生效："
                f"{outcome.error.code.value}: {outcome.error.message}"
            )
        self._write_bookkeeping(DS_PENDING_BIBLE_KEY, None)
        return None


def _bible_content_of(bible, overrides: Mapping[str, str]) -> BibleContent:
    """The fourteen fields as one :class:`BibleContent` — the current
    values with the overrides folded in (``revise_bible`` writes all
    fourteen as given; the caller says what the world is like)."""

    values = {
        field: getattr(bible, field)
        for field in _BIBLE_FIELDS
    }
    values.update(overrides)
    return BibleContent(**values)


def _derive_state(
    conn: sqlite3.Connection,
    reads: TurnReads,
    language: str,
    light_model: str,
) -> dict[str, Any]:
    """The whole immersion state from the durable rows (one derivation
    law, two readers: the face and the ro poll)."""

    payload: dict[str, Any] = {
        "ok": True,
        "did": None,
        "error": None,
        **_EMPTY_STATE,
        "language": language,
        "light_model": light_model,
    }
    worlds = SqliteWorldStore(
        conn, RuntimeEpochFence(current=load_current_epoch(conn) or 0)
    )
    world = worlds.get_world(DS_WORLD_ID)
    if world is None:
        payload["world"] = {
            "exists": False,
            "world_id": DS_WORLD_ID,
            "name": None,
            "current_tick": None,
        }
        payload["next"] = {
            "kind": "start",
            "detail": "点「开始」，种下灰隼要塞。",
        }
        payload["controls"] = {"can_start": True}
        return payload
    tick = read_tick(conn, DS_WORLD_ID)
    payload["world"] = {
        "exists": True,
        "world_id": DS_WORLD_ID,
        "name": getattr(world, "name", None),
        "current_tick": tick,
    }
    chapter = reads.current_chapter(DS_WORLD_ID)
    if chapter is None:
        payload["next"] = {
            "kind": "start",
            "detail": "世界在，第一幕还没计划——点「开始」让导演起笔。",
        }
        payload["controls"] = {"can_start": True}
        return payload
    payload["chapter"] = {
        "chapter_id": chapter.chapter_id,
        "chapter_index": chapter.chapter_index,
        "status": chapter.status.value,
    }
    plan = reads.adopted_plan(chapter.chapter_id)
    if plan is not None:
        payload["plan"] = _plan_face(plan)
    payload["passages"] = _chapter_passages(conn, chapter.chapter_id)
    payload["steps"] = [
        {
            "commit_id": step.commit_id,
            "kind": step.kind,
            "scene_id": step.scene_id,
            "passage_id": step.passage_id,
            "outcome": step.outcome,
        }
        for step in turn_steps_of(conn, chapter.chapter_id)
    ]
    stored = _settlement_of(conn, chapter.chapter_id)
    if stored is not None:
        payload["settlement"] = stored
    payload["bible"] = _bible_rows(conn)
    payload["pending_bible"] = _pending_bible_of(conn)
    payload["stop"] = _stop_note_of(conn)
    next_face, controls = _next_face(reads, chapter.status.value)
    payload["next"] = next_face
    payload["controls"] = controls
    return payload


def _plan_face(plan: WorldChapterPlanRecord) -> dict[str, Any]:
    """The situation plan's read face (DS-3 §6) — the four questions'
    answers beside the minimal field set, read from the plan element's
    situation document; a legacy blueprint row (the retired test face's
    own storage) answers the goal line alone, honestly."""

    face: dict[str, Any] = {
        "chapter_plan_id": plan.chapter_plan_id,
        "plan_revision": plan.plan_revision,
        "goal": plan.goal,
        "scene_count": len(plan.scenes),
        "places": [str(element.get("place", "")) for element in plan.scenes],
    }
    doc = situation_face_of(plan)
    if doc is None:
        return face
    face.update(
        {
            "where_you_stand": doc["where_you_stand"],
            "what_presses_on_you": doc["what_presses_on_you"],
            "first_speaker": doc["first_speaker"],
            "first_words": doc["first_words"],
            "open_question": doc["open_question"],
            "world_event_candidates": list(doc["world_event_candidates"]),
            "protagonist_goals": dict(doc["protagonist_goals"]),
            "pacing": doc["pacing"],
            "settlement_expectation": doc["settlement_expectation"],
        }
    )
    return face


def _chapter_passages(
    conn: sqlite3.Connection, chapter_id: str
) -> list[dict[str, Any]]:
    """The chapter's committed narration, in lineage order."""

    rows = conn.execute(
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


def _settlement_of(
    conn: sqlite3.Connection, chapter_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT summary, storyline_updates, hooks, resolved_lines"
        " FROM chapter_settlement WHERE chapter_id = ?",
        (chapter_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "chapter_id": chapter_id,
        "summary": str(row[0]),
        "storyline_updates": str(row[1]),
        "hooks": str(row[2]),
        "resolved_lines": str(row[3]),
    }


def _bible_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """The fourteen setting rows as the settings face reads them — the
    current revision's values, each row's pending state riding the
    graded-edit face's own bookkeeping."""

    cursor = conn.execute(
        "SELECT * FROM world_bible_revision"
        " WHERE world_id = ? AND status = 'CURRENT'",
        (DS_WORLD_ID,),
    )
    row = cursor.fetchone()
    if row is None:
        return []
    columns = [description[0] for description in cursor.description]
    values = dict(zip(columns, row))
    return [
        {"field": field, "value": str(values.get(field, ""))}
        for field in _BIBLE_FIELDS
    ]


def _next_face(
    reads: TurnReads, status: str
) -> tuple[dict[str, Any], dict[str, bool]]:
    """The next-step face and the control bits — the durable
    position's own sentences (the immersion face's voice). The DS-4
    law: the judgment is the committed-segment count, never the scene
    row's status — zero committed segments IS the opening's position
    (a mid-opening transport death leaves the row ACTIVE with no prose
    on the ground, and the opening button is the recovery path; the
    engine re-runs the beat from the last committed δ), and settling a
    chapter with no landed segment is refused the button at all."""

    controls = {
        "can_start": False,
        "can_open": False,
        "can_reply": False,
        "can_settle": False,
        "can_next_chapter": False,
    }
    if status == "CLOSED":
        controls["can_next_chapter"] = True
        return (
            {
                "kind": "next_chapter",
                "detail": "本章已落定——章间面在下方，写个方向再开下一章。",
            },
            controls,
        )
    chapter = reads.current_chapter(DS_WORLD_ID)
    if chapter is None:
        return ({"kind": "start", "detail": "点「开始」。"}, controls)
    scene = reads.current_scene(chapter.chapter_id)
    if scene is None:
        return (
            {"kind": "none", "detail": "本章没有可驱动的场。"},
            controls,
        )
    passages = reads.committed_segments(scene.scene_id)
    if not passages:
        # DS-4 据浅场回收: zero committed segments — the opening
        # button, whatever the scene row says (PLANNED or the
        # crash-advanced ACTIVE alike). settle stays off: there is
        # nothing on the ground to settle.
        controls["can_open"] = True
        return (
            {
                "kind": "opening",
                "detail": "世界还没落第一笔——点「开篇」重新落笔。",
            },
            controls,
        )
    controls["can_reply"] = True
    controls["can_settle"] = True
    return (
        {
            "kind": "your_turn",
            "detail": "轮到你了——说什么、做什么，随时开口。",
        },
        controls,
    )


def read_tick(conn: sqlite3.Connection, world_id: str) -> int | None:
    """The canonical story time (the read half's own SELECT; ``None``
    when the row is absent — the honest undeclared)."""

    row = conn.execute(
        "SELECT current_tick FROM world WHERE world_id = ?", (world_id,)
    ).fetchone()
    return None if row is None or row[0] is None else int(row[0])


def ds_state_ro(app_db_path: str) -> dict[str, Any]:
    """The immersion state over its own short read-only connection —
    the ``/api/teaching/current`` posture: a poll must not queue behind
    a drive, and a poll must never 500."""

    try:
        uri = Path(app_db_path).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            fence = RuntimeEpochFence(
                current=load_current_epoch(connection) or 0
            )
            reads = TurnReads(
                connection,
                narrative_store=SqliteNarrativeStore(connection, fence),
                world_store=SqliteWorldStore(connection, fence),
            )
            return _derive_state(
                connection,
                reads,
                prose_language_of(connection),
                _light_model_of(connection),
            )
        finally:
            connection.close()
    except Exception:
        return {
            "ok": False,
            "did": None,
            "error": _STATE_READ_FAILED,
            **_EMPTY_STATE,
            "language": PROSE_LANGUAGE_DEFAULT,
        }
