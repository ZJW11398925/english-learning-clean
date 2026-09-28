"""The W-1 local web face — one study-first dogfood page over one host.

``python -m elc web --app-db … --base-url … --model … [--content-db …]
[--rollout-stage …] [--port 8760]`` serves the same assembly the ``chat``
command builds (the argument validation, the provider construction and the
host opening are ``elc.cli.main``'s — this module never re-implements them;
the CLI's ``web`` branch is the only caller and ``main`` here is the thin
delegating entry for it). The page is a single embedded HTML/JS string, no
framework: a conversation area that POSTs one turn at a time, a
teaching-moment card for the moments the turn opened, an observations button
that pulls the durable readout, and a history load on page open. The UI text
is Chinese; the conversation itself is the user's English.

**Bound to 127.0.0.1 only, no auth.** This is a single-user, single-process
dogfood surface for the D-6-b browser run on one machine — it is not a
service: anyone who can reach the machine's loopback can drive the
conversation and read app.db's durable readout. It never listens on a
non-loopback address (pinned in ``tests/host/test_w1_web.py``), and nothing
here is a second egress point: the only network call a turn can cause is the
provider adapter's own POST, exactly as in ``chat``.

**One thread owns the host.** ``sqlite3`` connections answer only the thread
that opened them, while ``ThreadingHTTPServer`` runs each request in its own
thread — so every host-touching operation (a turn, a history window, the
observations readout) is shipped as a closure over a work queue and executed
by the :func:`run_web` caller's loop, the thread that opened the host. The
handler threads parse HTTP and serialize JSON and nothing else. This is also
the single-user serial assumption, made structural rather than hoped for:
concurrent requests queue, and the host never interleaves two turns.

**The one exception: ``/api/teaching/current`` never touches the host.**
A turn's generation stalls the work queue for the whole model round trip
(seconds on a real provider), and the teaching moment row is durable long
before that — ``OPENING`` is committed at the CP2 open, before the persona
call, so the card's data is readable locally while the model is still
talking. That route therefore runs :func:`_current_teaching_ro` directly on
the handler thread over its own short read-only connection (never the host's
connections, never the work queue): the page's send-time poll gets the card
in about a request's time instead of queueing behind the generation. Every
other route keeps the one-thread rule unchanged.

The turn face mirrors ``elc.cli`` exactly where it must:

- the envelope is minted per turn the way ``cli._commit`` mints it (fresh
  ``input_id`` / ``client_message_id`` with a ``web-`` prefix, the same
  ``runtime-v1`` version, the same channel) — re-running never collides with
  a previous turn's ``client_message_id``, which would make CP0 replay the
  old turn instead of answering this one (pinned shape-equal to the CLI's in
  ``tests/host/test_w1_web.py``);
- a turn-level failure is a **runtime fact, not an HTTP error**: an
  ``Err`` from ``begin_turn`` (or a terminal status without a reply) answers
  200 with ``failure_reason`` filled; only a malformed request body (no JSON,
  or no non-empty ``text`` string in it) is a 400;
- ``teaching_moments`` are the moments of **this turn**, read through the
  durable lineage (``teaching_moment → decision_cycle → turn_id``), never
  "whatever is latest"; ``kind`` is the moment's ``target_mode`` word
  (RESOURCE_PRACTICE / CAPABILITY_PRACTICE / PROBE / REVIEW / TRANSFER).
  Each moment also carries the card's human face (W-1R): ``title`` is the
  target's own words read out of content.db (the id tail plus rung 0 of its
  hint ladder — the authored function sentence; the raw id when the content
  side cannot answer), and ``status_cn`` / ``kind_cn`` are the fixed Chinese
  readings of the two vocabularies (unknown words pass through untranslated
  — fail-open display beats a broken card).

The teaching reply face (W-2) closes the day-one deadlock the first
dogfood run hit: a turn's teaching moment lands at ``AWAITING_USER``
holding the conversation's one-focus lock, and with no way to answer it
every later turn stayed teaching-less while the lock held.
``POST /api/teaching_reply`` with ``{"control": "skip"}`` locates the
conversation's ``AWAITING_USER`` moment through the durable lock, submits
a :class:`~elc.runtime.controller.TeachingReplyRequest` (SKIP, no
attempt) through the coordinator's existing ``respond_to_teaching``
entry — the §4 pipeline, the §7 abort and the lock release are the
runtime's own, unmodified — and answers ``{accepted, moment_state,
error}``. W-3 adds the attempt control: ``{"control": "attempt",
"text": "..."}`` submits the user's own English sentence as the
envelope's attempt (``CONTINUE`` + ``attempt_present`` + an
``AttemptPayload`` — the §4 step-3 evaluation, the durable records and
the evidence chain are the runtime's, unmodified), and the answer grows
a ``feedback`` field: the reply result's own evaluation outcome word
with its Chinese reading, or ``null`` when the reply carried no
evaluation (a skip, a refusal) — never a fabricated verdict. A refused
reply is a **runtime fact, not an HTTP error** (200 + ``accepted:
false`` + the error sentence), exactly like the turn face; only a body
outside the grammar (an unknown control word, an attempt without a
non-empty ``text``) is a 400.

W-6 makes the attempt loop legible on the page (作答回路可感化). A
submitted reply is visible the instant it goes out — every control on
the card is disabled and a busy strip says so (``批改中…``), because a
help reply waits out a model round trip and a silent wait reads as a
dead page; a fetch that dies is said in one human line instead of
silence. The attempt's verdict renders as a result strip (✓ / ◐ / ✗
before the verdict's own words), and the ro current card carries
``last_attempt_feedback`` — the moment's latest durable evaluation
outcome through the same reading, so a refresh does not bury the
verdict. The reply grammar grows the three help arms SM §1 already
names: ``{"control": "hint"}`` / ``{"control": "reveal"}`` /
``{"control": "explanation"}`` map onto ``ASK_HINT`` / ``ASK_ANSWER`` /
``ASK_EXPLANATION`` — the mapping is the whole feature; the envelopes,
the §4 pipeline, the §8 limits and the ladder are the runtime's,
unmodified. One runtime fact the mapping inherits (pinned, not fought):
an authorized user-requested reveal **keeps the moment open** at
``FULL_REVEAL`` — SM §3's ``POST_REVEAL_OPTIONAL_ATTEMPT`` phase exists
precisely because seeing the answer does not have to end the episode.

**F-1R re-typesets the shell onto the VS1 letter design** (the user's
accepted visual anchor — the archived exploration repo's 9/19 chat
parlor; its token values and layout laws move in as *values and shapes
only*, not one line of its code). One paper theme, no dark switch: the
``<style>`` is the letter token sheet (``--bg #fbf9f4`` / three ink
levels / two hairline rules / the ochre pencil / the touch wash / the
serif-sans-mono font stacks), and the form laws are absolute — zero
cards, zero chat bubbles, zero tab bar, zero radius, zero shadow:
layers are hairlines, whitespace and the ink levels, and every action
is an underlined pencil text link. Zero external resources stays the
law (no CDN, no web font, no framework — the shell is still one
embedded string over ``dependencies = []``). The shell is three screens
switched by plain JS ``show``/``hide`` (no router): **开张** (a
first-visit cover, remembered in localStorage — an honest "this is what
this is": the runtime has no persona-authoring face, so the cover
invents none), **客厅** (the default — everything the W series built,
re-typeset: the stream as letters, the user's line a torn-edge reply
slip and the parlor's a plain sheet, the teaching moment a short note
in the letter flow, the input a borderless pen line with a 寄出 link),
and **仪表** (the set screen — the honest facts screen: the endpoint
and the model name have no page-side source and are not shown, the
学习 and 诊断 blocks expand in place, and 回客厅 leads back).

**F-2 turns the shell into the learning face** — three read/act features on
top of F-1, all honest and none new in kind:

- ``GET /api/learning`` is the 学习 view's one read, built exactly like
  ``/api/diagnostics`` (read-only SQL on the work queue, panel-level
  guards, honest empty shapes, a content-snapshot pin): the schedule
  panel (every ``schedule_item`` row, DUE/OVERDUE first and
  NOT_SCHEDULED last), the goals panel (the portfolio's ``goals`` and
  ``modality_weights`` JSON parsed and passed through verbatim) and the
  evidence panel (the last five ``evidence_claim`` rows plus the
  ``learner_target_state`` and ``evidence_claim`` counts — numbers, not
  readings).
- ``GET /api/targets`` names what can be taught, from the first face the
  host actually holds: with a content leg the curriculum readiness table
  is read and every target at readiness R3 or above is listed (the
  ``source`` word says so); without one the fallback is the
  ``schedule_item`` target set — "schedule 覆盖的供给目标", never an
  invented corpus. Display names are :func:`_target_display_name`'s, the
  card's own.
- ``POST /api/teach_me`` is the 学习 view's one act: a
  :class:`~elc.teaching.request.TeachingRequest` through the
  coordinator's own ``request_teaching`` entry — and that one call is
  the whole chain, survey result: the P3-1B opening delivery is
  dispatched inside the same entry (the stale "stops at CP2" docstring
  notwithstanding, pinned by the happy-path test), so the moment is at
  ``AWAITING_USER`` when the answer lands and the W-4 poll picks the
  card up. An ``Err``, a DENY or a DEGRADED is a runtime fact (200 +
  ``accepted: false`` + the error sentence); only a body outside the
  ``{"target_id": …}`` grammar is a 400.
- the chat view says why a quiet turn was quiet: when the turn response
  carries no teaching moments, the page pulls ``/api/diagnostics`` and
  renders one gray line from the why-not-teach panel (the top
  not-activated candidate's utility against its threshold, or the DENY
  reason codes); a failed or empty pull is silent — the line never
  blocks a chat.

``/api/diagnostics`` is the diagnostics view's one read: **read-only SQL**
assembled into the five panels IP §15 asks a front end to answer. It runs
on the work queue (:meth:`_WebFace.diagnostics` over ``host.db``) rather
than on a handler-thread ro connection — the deliberate simple choice,
written down: the diagnostics view is pulled by a person who is *not*
mid-generation (the W-4 poll exists precisely because the card races the
model), so nothing here needs to bypass the queue, and riding it keeps the
one-connection one-thread discipline with zero new concurrency. Every
panel is a plain ``SELECT`` (no write, ever — pinned by a before/after
content-snapshot test that fails on insert-class *and* update-class
mutations alike), each guarded separately:
a panel whose read explodes answers ``{"error": …}`` in its own slot,
never a 500 for the whole readout, and a panel with no durable rows
answers its honest empty shape (the page says 暂无数据 / 无降级记录,
never a fabricated number).
The five panels:

1. **Why did it teach?** — the latest ``planner_evaluation`` whose
   ``factor_trace`` document marks a candidate ``selected: true`` (the
   column is decoded by its own reader,
   ``elc.planner.trace_document.decode_factor_trace``; a legacy prose row
   simply has no candidates to speak of), with the candidate's
   ``canonical_key`` / ``benefit_score`` / ``cost_score`` / ``utility``
   and the matching ``gate_decision`` row's ``decision`` + ``reason_codes``.
2. **Why did it NOT teach?** — the latest evaluation's top-3 **not
   activated** candidates in ranking order (``utility`` against
   ``activation_threshold``, ``activated: false``, each cost factor's
   reading — the overexposure band value among them), plus the latest
   ``DENY`` gate row's ``reason_codes``.
3. **What evidence changed?** — the last five ``attempt_evaluation_record``
   rows (``outcome`` / ``confidence`` / ``created_at``).
4. **What support was visible?** — the last five teaching-class
   ``generation_action_intent`` rows (``action_type`` / ``created_at``)
   plus the ``exposure_estimate`` row count.
5. **Why was a turn degraded?** — the latest ``DEGRADED`` row of
   ``planner_execution_status`` and the latest
   ``DEGRADED_NO_AUTOMATIC_TEACHING`` row of ``runtime_decision_outcome``
   (either table may legitimately be empty — the honest answer is
   无降级记录).

``observations`` serves ``elc.cli``'s readings core (the six §12 indicator
declarations, the six durable-counts sections, the drift signal) — the same
numbers the ``observations`` command prints, by construction. ``history``
serves the conversation store's canonical window (last 50 turns, delivered
assistant output only — the store's own §3 key rule), so what the page
recovers on load is exactly what the transcript holds.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import sys
import threading
import uuid
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

from elc.cli import (
    RUNTIME_VERSION,
    ObservationSection,
    observation_drift_count,
    observation_sections,
)
from elc.cli import main as cli_main
from elc.conversation.types import CommitUserTurn
from elc.curriculum.readiness import READINESS_LEVELS
from elc.host import Host
from elc.persona.provider import PersonaProvider
from elc.planner.trace_document import decode_factor_trace
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    Err,
    InputId,
    InteractionChannel,
    TargetId,
)
from elc.runtime.controller import TeachingReplyRequest
from elc.runtime.types import InputEnvelope
from elc.teaching.envelope import (
    AttemptPayload,
    TeachingControlIntent,
    TeachingResponseEnvelope,
)
from elc.teaching.request import TeachingRequest
from elc.teaching.rollout import OBSERVATION_SPECS
from elc.teaching.types import MomentState

__all__ = [
    "DEFAULT_WEB_CONVERSATION_ID",
    "WebOpenError",
    "main",
    "run_web",
]


class WebOpenError(RuntimeError):
    """The conversation the page serves could not be opened (run_web raises
    before binding; the CLI branch answers it with chat's open-failure
    shape — one human sentence and exit 1, never a 500-per-request loop)."""

#: The default conversation the web face opens (idempotent; distinct from the
#: CLI's so the two surfaces never interleave one transcript by accident).
DEFAULT_WEB_CONVERSATION_ID = "web-default"

#: How many canonical turns ``/api/history`` serves (the page's load-time
#: recovery window).
HISTORY_TURNS = 50

#: How long a handler thread waits for the host's thread to answer before it
#: reports the worker as gone (generous: the worker loop polls its queue and
#: never blocks on anything but the work itself).
_WORKER_WAIT_SECONDS = 60.0

#: The card's Chinese readings of the moment lifecycle vocabulary (the
#: canonical ``MomentState`` words, docs/STATE_MACHINES.md §1). Display only:
#: a word outside the map passes through untranslated.
_STATUS_CN: dict[str, str] = {
    "AUTHORIZED": "已授权",
    "OPENING": "正在打开",
    "AWAITING_USER": "等待您回应",
    "EVALUATING": "正在评判",
    "DECIDING_NEXT_ACTION": "正在决定下一步",
    "COMPLETING": "正在收尾",
    "ABORTING": "正在中止",
    "TEACHING_TERMINAL": "教学已终局",
    "RESUMING": "正在续接",
    "CLOSED": "已结束",
}

#: The card's Chinese readings of the target-mode vocabulary (the five words
#: the module docstring names). Display only, same fail-open rule.
_KIND_CN: dict[str, str] = {
    "RESOURCE_PRACTICE": "资源练习",
    "CAPABILITY_PRACTICE": "能力练习",
    "PROBE": "探测",
    "REVIEW": "复习",
    "TRANSFER": "迁移",
}

#: The attempt feedback's Chinese readings of the evaluator's outcome
#: vocabulary (STATE_MACHINES §5's five words, the durable
#: ``attempt_evaluation_record.outcome`` CHECK). Display only, same
#: fail-open rule: a word outside the map passes through untranslated.
_OUTCOME_CN: dict[str, str] = {
    "SUCCESS": "回答正确",
    "ALTERNATIVE_SUCCESS": "回答正确（另一种合格表达）",
    "PARTIAL": "部分正确",
    "FAILURE": "未命中目标表达",
    "ABSTAIN": "本次作答无法评判",
}

#: The W-6 help words the page sends, and the runtime control intents they
#: map onto (SM §4's own vocabulary). The mapping is the whole feature: the
#: envelopes, the §4 pipeline, the §8 limits and the hint ladder are the
#: runtime's, unmodified — ``ASK_HINT`` delivers the next hint rung,
#: ``ASK_ANSWER`` delivers the reveal, ``ASK_EXPLANATION`` the explanation,
#: and an authorized reveal keeps the moment open at ``FULL_REVEAL`` (SM §3
#: ``POST_REVEAL_OPTIONAL_ATTEMPT``), it does not close it.
_HELP_INTENT_BY_WORD: dict[str, TeachingControlIntent] = {
    "hint": TeachingControlIntent.ASK_HINT,
    "reveal": TeachingControlIntent.ASK_ANSWER,
    "explanation": TeachingControlIntent.ASK_EXPLANATION,
}

#: The read-only current card's Chinese status readings: the shared
#: vocabulary map with the generation-window word said the way the user
#: meets it — an ``OPENING`` moment here means "the teaching is opening"
#: (the model is still finishing its reply), which the generic "正在打开"
#: does not say on a card the user is actively waiting on.
_RO_STATUS_CN: dict[str, str] = {
    **_STATUS_CN,
    MomentState.OPENING.value: "教学开启中…",
}

#: The teaching-class words of ``generation_action_intent.action_type`` (the
#: CHECK's six words minus the two persona words) — the support panel's
#: row filter, word for word from migration 0003's vocabulary.
_TEACHING_ACTION_TYPES: tuple[str, ...] = (
    "TEACHING_OPEN",
    "TEACHING_HINT",
    "TEACHING_REVEAL",
    "TEACHING_EXPLANATION",
)

#: How many recent ``planner_evaluation`` rows the why-teach panel may walk
#: back through before it answers the honest empty shape (bounded work: the
#: scan stops at the first selected candidate, and a conversation whose
#: every recent evaluation selected nothing has its real answer anyway).
_DIAG_EVAL_SCAN = 50

#: How many rows the list-shaped panels serve (evidence / support).
_DIAG_PANEL_ROWS = 5

#: How many not-activated candidates the why-not-teach panel serves.
_DIAG_NOT_TEACH_CANDIDATES = 3

#: How many recent evidence claims the learning view's evidence panel
#: serves (the diagnostics list panels' width, same number, own name: the
#: two faces widen independently).
_LEARNING_EVIDENCE_ROWS = 5

#: The learning view's targets floor: readiness R3 and above can be taught
#: (the §8.1 ladder's own words; the index keeps the comparison a ladder
#: fact instead of a two-word list that the next level would silently
#: exclude).
_TARGETS_READINESS_FLOOR = "R3_TEACHING_READY"

#: The schedule panel's reading order, as SQL: the due states first, the
#: not-scheduled rows last (the task's own words — a person reads the
#: panel top-down), then recency and the id pair for a deterministic tie.
_SCHEDULE_PANEL_ORDER = (
    "CASE review_state"
    " WHEN 'DUE' THEN 0 WHEN 'OVERDUE' THEN 0"
    " WHEN 'UPCOMING' THEN 1 ELSE 2 END,"
    " updated_at DESC, target_id, target_type, evidence_modality"
)


def _readable_outcome(outcome: str) -> str:
    """One evaluator outcome word, readable: ``FAILURE（未命中目标表达）``.

    The shared shape of the reply face's ``feedback`` and the ro card's
    ``last_attempt_feedback`` — one reading, two readers."""

    return f"{outcome}（{_OUTCOME_CN.get(outcome, outcome)}）"


def _feedback_of(result: Any) -> str | None:
    """The readable face of a reply result's own evaluation verdict.

    The runtime's ``TeachingReplyTurnResult`` carries the evaluator's
    outcome word (``evaluation_outcome``) when the reply was judged and
    ``None`` when it was not (a skip, an attemptless control) — this
    passes the fact through as ``<WORD>（<Chinese reading>）`` and ``None``
    stays ``None``. Nothing here re-judges or fabricates: no verdict word,
    no feedback.
    """

    outcome = getattr(result, "evaluation_outcome", None)
    if not outcome:
        return None
    return _readable_outcome(str(outcome))


def _target_display_name(target_id: str) -> str:
    """The spoken name of one focus target, out of its id.

    Content ids are authored ``<kind>-<category>-<keyword phrase>``
    (``res-discourse-anyway``, ``cap-stance-soften-disagreement``); the
    keyword phrase after the two leading segments is the name a person says
    (``anyway``, ``soften disagreement``). An id without the two leading
    segments is returned whole — the caller's fallback shape.
    """

    parts = target_id.split("-")
    if len(parts) < 3:
        return target_id
    return " ".join(parts[2:])


# ---------------------------------------------------------------------------
# the F-1 diagnostics panels — read-only SELECTs over app.db, one per why
# ---------------------------------------------------------------------------


def _reason_codes_of(raw: object) -> list[str] | str:
    """The bracketed reason-codes column, as a list when it parses as one.

    The column's durable form is a JSON array (``'["HARD_COOLDOWN_ACTIVE"]'``);
    the diagnostics face hands the page the decoded list so it can join it
    with human separators. A value that does not parse is passed through as
    the raw string — a diagnostics panel reports what the row says, it does
    not invent a cleaner shape for it."""

    try:
        loaded = json.loads(str(raw))
    except (TypeError, ValueError):
        return str(raw)
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    return str(raw)


def _candidate_face(candidate: Any) -> dict[str, Any]:
    """One decoded candidate trace, as the page reads it.

    The identification, the two partial sums, the utility against its
    activation threshold, and every cost reading — the overexposure band
    value among them, carried like any other factor number (the verdict
    that silenced a candidate is a *number* the kernel scored, and the
    panel shows the number, not a paraphrase)."""

    return {
        "candidate_id": candidate.candidate_id,
        "canonical_key": candidate.canonical_key,
        "benefit_score": candidate.benefit_score,
        "cost_score": candidate.cost_score,
        "utility": candidate.utility,
        "activation_threshold": candidate.activation_threshold,
        "activated": candidate.activated,
        "selected": candidate.selected,
        "costs": [
            {"factor": reading.factor, "value": reading.value}
            for reading in candidate.cost
        ],
    }


def _why_teach_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """Why did it teach — the latest evaluation that actually selected one.

    Walks the recent evaluations newest-first and stops at the first whose
    ``factor_trace`` document marks a candidate ``selected: true``; the
    matching gate row is the same cycle's decision for the same candidate
    id. A legacy prose-array row (P9-0's predecessor encoding) has no
    candidate trace to speak of and is stepped over, not decoded by
    guessing. Nothing selected in the scanned window is the honest empty
    shape."""

    rows = db.execute(
        "SELECT decision_cycle_id, factor_trace, created_at"
        " FROM planner_evaluation"
        " ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (_DIAG_EVAL_SCAN,),
    ).fetchall()
    for cycle_id, trace, created_at in rows:
        document = decode_factor_trace(str(trace))
        if isinstance(document, tuple):
            continue
        chosen = [c for c in document.candidates if c.selected]
        if not chosen:
            continue
        candidate = chosen[0]
        gate = db.execute(
            "SELECT decision, reason_codes, created_at FROM gate_decision"
            " WHERE decision_cycle_id = ? AND candidate_id = ?"
            " ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (str(cycle_id), candidate.candidate_id),
        ).fetchone()
        return {
            "created_at": str(created_at),
            "candidate": _candidate_face(candidate),
            "gate": None
            if gate is None
            else {
                "decision": str(gate[0]),
                "reason_codes": _reason_codes_of(gate[1]),
                "created_at": str(gate[2]),
            },
        }
    return {"created_at": None, "candidate": None, "gate": None}


def _why_not_teach_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """Why did it NOT teach — the latest evaluation's silenced candidates.

    The top-3 **not activated** candidates in the evaluation's own ranking
    order (``ranked_candidate_ids``), each with its utility against the
    activation threshold and every cost reading; plus the latest ``DENY``
    gate row's reason codes (a different silence: the gate's no, not the
    kernel's). No evaluation at all is the honest empty shape — and the
    DENY row is still reported, because a conversation can be gated before
    it is ever planned over."""

    row = db.execute(
        "SELECT ranked_candidate_ids, factor_trace, created_at"
        " FROM planner_evaluation"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    candidates: list[dict[str, Any]] = []
    created_at: str | None = None
    if row is not None:
        created_at = str(row[2])
        document = decode_factor_trace(str(row[1]))
        if not isinstance(document, tuple):
            ranked = json.loads(str(row[0])) if row[0] else []
            by_id = {c.candidate_id: c for c in document.candidates}
            for cid in ranked if isinstance(ranked, list) else []:
                candidate = by_id.get(str(cid))
                if candidate is not None and candidate.activated is not True:
                    candidates.append(_candidate_face(candidate))
                    if len(candidates) >= _DIAG_NOT_TEACH_CANDIDATES:
                        break
    deny = db.execute(
        "SELECT reason_codes, created_at FROM gate_decision"
        " WHERE decision = 'DENY'"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    return {
        "created_at": created_at,
        "candidates": candidates,
        "gate_deny": None
        if deny is None
        else {
            "reason_codes": _reason_codes_of(deny[0]),
            "created_at": str(deny[1]),
        },
    }


def _evidence_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """What evidence changed — the last five judged attempts."""

    rows = db.execute(
        "SELECT outcome, confidence, created_at FROM attempt_evaluation_record"
        " ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (_DIAG_PANEL_ROWS,),
    ).fetchall()
    return {
        "records": [
            {
                "outcome": str(row[0]),
                "confidence": float(row[1]),
                "created_at": str(row[2]),
            }
            for row in rows
        ]
    }


def _support_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """What support was visible — teaching deliveries and their exposure.

    The last five teaching-class action intents (the four words of
    :data:`_TEACHING_ACTION_TYPES`, the CHECK vocabulary minus the two
    persona words) plus the ``exposure_estimate`` row count — how many
    exposure estimates the delivery records ever wrote."""

    rows = db.execute(
        "SELECT action_type, created_at FROM generation_action_intent"
        " WHERE action_type IN (?, ?, ?, ?)"
        " ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (*_TEACHING_ACTION_TYPES, _DIAG_PANEL_ROWS),
    ).fetchall()
    counted = db.execute("SELECT COUNT(*) FROM exposure_estimate").fetchone()
    return {
        "actions": [
            {"action_type": str(row[0]), "created_at": str(row[1])}
            for row in rows
        ],
        "exposure_estimate_count": int(counted[0]) if counted else 0,
    }


def _degraded_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """Why was a turn degraded — the two degradation ledgers, latest rows.

    ``planner_execution_status``'s ``DEGRADED`` word and
    ``runtime_decision_outcome``'s ``DEGRADED_NO_AUTOMATIC_TEACHING`` word
    (the only outcome word on that table that carries "DEGRADED"). Either
    table may legitimately be empty — both ``None`` is the ordinary
    healthy answer, and the page says 无降级记录."""

    execution = db.execute(
        "SELECT status, error_code, created_at FROM planner_execution_status"
        " WHERE status = 'DEGRADED'"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    outcome = db.execute(
        "SELECT outcome, reason_codes, created_at FROM runtime_decision_outcome"
        " WHERE outcome = 'DEGRADED_NO_AUTOMATIC_TEACHING'"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1"
    ).fetchone()
    return {
        "planner_execution": None
        if execution is None
        else {
            "status": str(execution[0]),
            "error_code": None if execution[1] is None else str(execution[1]),
            "created_at": str(execution[2]),
        },
        "runtime_outcome": None
        if outcome is None
        else {
            "outcome": str(outcome[0]),
            "reason_codes": _reason_codes_of(outcome[1]),
            "created_at": str(outcome[2]),
        },
    }


# ---------------------------------------------------------------------------
# the F-2 learning panels — read-only SELECTs over app.db, one per face
# ---------------------------------------------------------------------------


def _schedule_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """The review schedule, in the order a person reads it.

    Every ``schedule_item`` row — the whole current projection, no window —
    with the eight columns the panel names (the migration's own words);
    DUE and OVERDUE first, NOT_SCHEDULED last (:data:`_SCHEDULE_PANEL_ORDER`).
    The numbers are the rows' own: review_urgency and the window pair pass
    through verbatim, nothing here derives a "due-ness" the Scheduler did
    not already write.
    """

    rows = db.execute(
        "SELECT target_type, target_id, review_state, review_urgency,"
        " next_review_window_start, next_review_window_end, spacing_stage,"
        f" updated_at FROM schedule_item ORDER BY {_SCHEDULE_PANEL_ORDER}"
    ).fetchall()
    return {
        "items": [
            {
                "target_type": str(row[0]),
                "target_id": str(row[1]),
                "review_state": str(row[2]),
                "review_urgency": None if row[3] is None else float(row[3]),
                "next_review_window_start": (
                    None if row[4] is None else str(row[4])
                ),
                "next_review_window_end": (
                    None if row[5] is None else str(row[5])
                ),
                "spacing_stage": None if row[6] is None else str(row[6]),
                "updated_at": str(row[7]),
            }
            for row in rows
        ]
    }


def _goals_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """The goal portfolios, their JSON parsed and passed through verbatim.

    ``goals`` is a JSON array and ``modality_weights`` a JSON object in the
    column's durable form (migration 0011); this panel decodes both and
    hands the page the parsed value — the shape the user-config controller
    wrote, never a re-shape of it. A column that does not parse explodes
    into the panel guard's ``{"error": …}`` — the page shows the read
    failure, not a guessed portfolio.
    """

    rows = db.execute(
        "SELECT goal_portfolio_id, goal_version, goals, modality_weights"
        " FROM goal_portfolio ORDER BY goal_portfolio_id"
    ).fetchall()
    return {
        "portfolios": [
            {
                "goal_portfolio_id": str(row[0]),
                "goal_version": str(row[1]),
                "goals": json.loads(str(row[2])),
                "modality_weights": json.loads(str(row[3])),
            }
            for row in rows
        ]
    }


def _learning_evidence_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """The evidence ledger at a glance: recent claims plus the two counts.

    The last five ``evidence_claim`` rows (newest first) and the row
    counts of ``evidence_claim`` and ``learner_target_state`` — the counts
    are counts, not readings: the panel serves the numbers the tables
    hold, the page labels them and adds nothing.
    """

    rows = db.execute(
        "SELECT target_id, polarity, outcome, performance_type, created_at"
        " FROM evidence_claim"
        " ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (_LEARNING_EVIDENCE_ROWS,),
    ).fetchall()
    claims = db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()
    states = db.execute(
        "SELECT COUNT(*) FROM learner_target_state"
    ).fetchone()
    return {
        "claims": [
            {
                "target_id": str(row[0]),
                "polarity": str(row[1]),
                "outcome": str(row[2]),
                "performance_type": str(row[3]),
                "created_at": str(row[4]),
            }
            for row in rows
        ],
        "evidence_claim_count": int(claims[0]) if claims else 0,
        "learner_target_state_count": int(states[0]) if states else 0,
    }


def _diagnostics_panel(
    name: str,
    build: Callable[[sqlite3.Connection], dict[str, Any]],
    db: sqlite3.Connection,
) -> dict[str, Any]:
    """One panel, guarded: a read that explodes answers an error word.

    The five panels are independent reads; one dirty table must not take
    the whole readout down (the route would otherwise 500 and the page
    would show nothing at all). The error is the panel's own shape —
    ``{"error": "<Exception>: <message>"}`` — which the page renders as a
    read-failure line in that one slot."""

    try:
        return build(db)
    except Exception as exc:
        return {"error": f"{name}: {type(exc).__name__}: {exc}"}


_PAGE = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>英语客厅 · Study-first dogfood</title>
<style>
  /* F-1R 设计令牌：唯一出处 = 旧仓 VS1「对话客厅」chat.css 的纸感令牌
     （逐值采用，不复制其代码）：纸 #fbf9f4 / 三级墨 / 两档发丝线 /
     赭红铅笔 / 触压底。形态法则（用户否掉上一版的条款，逐条遵守）：
     零卡片、零气泡、零底栏页签、零大圆角面板、零阴影、零青绿——
     分层靠上下发丝线、留白与三级墨色；动作一律是赭红下划线文字链接。 */
  :root {
    --bg: #fbf9f4;
    --ink: #1b1a17;
    --ink-soft: #5c574e;
    --ink-faint: #726a5e;
    --rule: #ded7c9;
    --rule-soft: #ebe5d8;
    --pencil: #a8562f;
    --touch: #f0e9dc;
    --f-serif: Georgia, 'Times New Roman', 'Songti SC', 'SimSun',
      'Noto Serif CJK SC', serif;
    --f-sans: system-ui, -apple-system, 'Segoe UI', 'PingFang SC',
      'Microsoft YaHei', sans-serif;
    --f-mono: ui-monospace, 'Cascadia Mono', Consolas, monospace;
    --read-pad: 18px;
    --safe-bottom: env(safe-area-inset-bottom, 0px);
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html, body { margin: 0; padding: 0; background: var(--bg); }
  body {
    color: var(--ink); font-family: var(--f-serif); font-size: 16px;
    line-height: 1.55; -webkit-text-size-adjust: 100%;
    -webkit-tap-highlight-color: transparent;
  }
  #stage { max-width: 430px; margin: 0 auto; min-height: 100vh;
           position: relative; }
  button { border: 0; background: none; padding: 0; cursor: pointer;
           font: inherit; color: inherit; }
  button:focus-visible, input:focus-visible {
    outline: 1px solid var(--pencil); outline-offset: 2px; }
  .note { color: var(--ink-faint); font-size: .85rem;
          font-family: var(--f-sans); }

  /* ── 开张屏（first visit；localStorage 记住后不再出现）────────────── */
  .ob { padding: 54px var(--read-pad) 60px; min-height: 100vh; }
  .ob .formhead { text-align: center; font-family: var(--f-sans);
                  font-size: 11px; letter-spacing: 0.3em;
                  color: var(--ink-faint); margin: 0 0 26px; }
  .ob h1 { text-align: center; margin: 0 0 10px; font-size: 27px;
           font-weight: 500; letter-spacing: 0.14em; }
  .ob .sub { text-align: center; margin: 0 0 10px; font-size: 13px;
             color: var(--ink-soft); }
  .ob .go { display: block; margin: 26px auto 0; font-family: var(--f-serif);
            font-size: 17px; font-weight: 700; color: var(--ink);
            text-decoration: underline; text-decoration-thickness: 1px;
            text-underline-offset: 0.32em; }
  .ob .go:active { opacity: 0.55; }
  .ob .hint { margin: 14px 0 0; text-align: center;
              font-family: var(--f-sans); font-size: 11px;
              color: var(--ink-faint); }

  /* ── 客厅屏：伙伴卡（上下发丝线夹住）+ 信笺流 + 写信区 ─────────────── */
  .top { position: sticky; top: 0; z-index: 5; background: var(--bg);
         border-bottom: 1px solid var(--rule);
         padding: 10px var(--read-pad) 8px;
         display: flex; align-items: baseline; gap: 10px; }
  .who { font-size: 15px; font-weight: 600; letter-spacing: 0.18em; }
  .who-sub { font-size: 11px; color: var(--ink-faint);
             font-family: var(--f-sans); margin-top: 2px; }
  .meter { margin-left: auto; font-family: var(--f-mono); font-size: 11px;
           color: var(--ink-soft); text-decoration: underline dotted;
           text-underline-offset: 0.28em;
           text-decoration-color: var(--rule); }
  .meter:active { opacity: 0.55; }

  .flow { padding: 18px var(--read-pad) 250px; }
  .letter { margin: 0 0 18px; max-width: 84%; }
  .letter.may { margin-right: auto; }
  .letter.me { margin-left: auto; }
  .say { margin: 0; font-size: 16px; white-space: pre-wrap;
         overflow-wrap: anywhere; }
  /* 我的回信 = 撕边信纸（--touch 衬底 + 顶部撕口；不是气泡：零圆角零描边） */
  .letter.me .paper {
    background: var(--touch); padding: 10px 14px 12px; font-weight: 600;
    clip-path: polygon(0 6px, 4% 2px, 11% 7px, 19% 1px, 27% 6px, 36% 2px,
                       46% 7px, 55% 2px, 64% 6px, 74% 1px, 83% 7px, 92% 2px,
                       100% 6px, 100% 100%, 0 100%);
  }
  .typing { margin: 0 0 18px; font-family: var(--f-sans); font-size: 12px;
            color: var(--ink-faint); }
  .sysline { text-align: center; margin: 0 0 14px;
             font-family: var(--f-sans); font-size: 11px;
             color: var(--ink-faint); }
  .errline { margin: 0 0 14px; padding: 8px 10px;
             border-left: 1px solid var(--pencil);
             font-family: var(--f-sans); font-size: 12px;
             color: var(--pencil); line-height: 1.7;
             white-space: pre-wrap; overflow-wrap: anywhere; }
  /* F-2 blocked 行：本轮没有教学时的一行诚实小字（数据不在就沉默）。 */
  .blockedline { margin: 0 0 14px; font-family: var(--f-sans);
                 font-size: 11px; color: var(--ink-faint); }

  /* 教学时刻 = 信流里的一张短笺（rule-soft 底色块；零圆角零阴影） */
  .note-paper { margin: 0 0 18px; background: var(--rule-soft);
                padding: 12px 14px 14px; font-size: 15px; }
  .note-paper > b { font-weight: 600; overflow-wrap: anywhere; }
  .note-paper.skipped { opacity: 0.55; }
  .replyrow { display: flex; gap: 14px; margin-top: 10px;
              align-items: baseline; }
  .replytext { flex: 1; min-width: 0; border: 0;
               border-bottom: 1px solid var(--rule); background: none;
               outline: none; padding: 4px 2px; font-family: var(--f-serif);
               font-size: 15px; color: var(--ink); }
  .replytext::placeholder { color: var(--ink-faint); font-size: 13px;
                            font-family: var(--f-sans); }
  .replytext:focus { border-bottom-color: var(--pencil); }
  .linklike { font-family: var(--f-sans); font-size: 12px;
              color: var(--pencil); text-decoration: underline;
              text-decoration-thickness: 1px; text-underline-offset: 3px; }
  .linklike:active { opacity: 0.55; }
  .skiplink { display: block; margin-top: 10px;
              font-family: var(--f-sans); font-size: 11px;
              color: var(--ink-faint); text-decoration: underline dotted;
              text-underline-offset: 0.28em;
              text-decoration-color: var(--rule); }
  .skiplink:active { opacity: 0.55; }
  /* W-6 结果条：赭红/墨色呈现，不用绿红底色块。 */
  .resultstrip { margin-top: 8px; font-size: .9rem; }
  .resultstrip.ok { color: var(--pencil); }
  .resultstrip.part { color: var(--ink-soft); }
  .resultstrip.miss { color: var(--ink); }
  .busystrip { margin-top: 6px; color: var(--ink-soft);
               font-family: var(--f-sans); font-size: .85rem; }

  /* 写信区：固定底、上发丝线、无边框输入行 + 寄出链接 */
  .dock { position: fixed; left: 0; right: 0; bottom: 0; z-index: 8;
          background: var(--bg); border-top: 1px solid var(--rule);
          padding: 10px var(--read-pad)
                   calc(14px + var(--safe-bottom));
          max-width: 430px; margin: 0 auto; }
  .dock-row { display: flex; align-items: stretch; gap: 12px; }
  .pen { width: 100%; border: 0; background: none; outline: none;
         resize: none; overflow-y: auto;
         font-family: var(--f-serif); font-size: 16px; color: var(--ink);
         line-height: 1.6; padding: 10px 2px; min-height: 64px;
         max-height: 160px;
         background-image: repeating-linear-gradient(
           to bottom, transparent 0 25px, var(--rule-soft) 25px 26px);
         background-attachment: local; }
  .pen::placeholder { color: var(--ink-faint); font-size: 13px;
                      font-family: var(--f-sans); }
  .send { flex: none; align-self: flex-end; font-family: var(--f-serif);
          font-size: 15px; font-weight: 700; color: var(--ink);
          text-decoration: underline; text-decoration-thickness: 1px;
          text-underline-offset: 0.3em; }
  .send:active { opacity: 0.55; }

  /* ── 仪表屏：诚实事实屏——mono 仪表 + 学习/诊断两个链接区块 ────────── */
  .set { padding: 30px var(--read-pad) 60px; min-height: 100vh; }
  .set h2 { margin: 0 0 6px; font-size: 24px; font-weight: 500;
            letter-spacing: 0.12em; }
  .set .sub { margin: 0 0 8px; font-family: var(--f-sans); font-size: 12px;
              color: var(--ink-faint); line-height: 1.7; }
  .setlinks { display: flex; gap: 22px; margin-top: 18px;
              border-top: 1px solid var(--rule); padding-top: 14px; }
  .setlink { font-family: var(--f-serif); font-size: 15px; font-weight: 600;
             color: var(--pencil); text-decoration: underline;
             text-decoration-thickness: 1px; text-underline-offset: 3px; }
  .setblock { margin-top: 4px; }
  .sec { margin-top: 22px; border-top: 1px solid var(--rule-soft);
         padding-top: 12px; }
  .sec h3 { margin: 0 0 8px; font-family: var(--f-sans); font-size: 11px;
            letter-spacing: 0.18em; color: var(--ink-faint);
            font-weight: 500; }
  .kv { display: flex; gap: 8px; padding: 3px 0; font-size: 12px;
        font-family: var(--f-mono); font-variant-numeric: tabular-nums;
        align-items: baseline; }
  .kv b { color: var(--ink-soft); font-weight: 500; flex: none;
          font-family: var(--f-sans); font-size: 12px; }
  .kvgroup { border-left: 1px solid var(--rule); padding: 4px 10px;
             margin-top: 8px; }
  .kvtitle { display: block; color: var(--ink-soft); font-size: 12px;
             font-family: var(--f-sans); }
  .diagerror { color: var(--pencil); font-size: 12px;
               font-family: var(--f-sans); }
  .refresh { margin-top: 10px; font-family: var(--f-sans); font-size: 12px;
             color: var(--ink-soft); text-decoration: underline dotted;
             text-underline-offset: 0.28em;
             text-decoration-color: var(--rule); }
  .refresh:active { opacity: 0.55; }
  pre { font-family: var(--f-mono); font-size: 11px; line-height: 1.7;
        color: var(--ink-soft); overflow-x: auto; white-space: pre-wrap;
        overflow-wrap: anywhere; border-top: 1px solid var(--rule-soft);
        border-bottom: 1px solid var(--rule-soft); padding: 8px 0; }
  .back { display: block; margin-top: 30px; font-family: var(--f-sans);
          font-size: 12px; color: var(--ink-soft);
          text-decoration: underline dotted;
          text-underline-offset: 0.3em; }
</style>
</head>
<body>
<div id="stage">

  <!-- 开张屏：first visit 一次（localStorage 记住）。诚实映射 runtime：
       没有用户自定义人设面，就不伪装——进入即开聊，这就是全部的「设定」。 -->
  <section id="screen-onboard" class="ob">
    <p class="formhead">✉ 第一步，也是唯一步</p>
    <h1>把英语请进客厅</h1>
    <p class="sub">跟一位固定伙伴用英语闲聊——想说什么，就说什么。</p>
    <p class="sub">客厅在旁听着：看得懂你的每一步，该教的时候才开口。</p>
    <button id="ob-go" class="go" type="button">就这么定 →</button>
    <p class="hint">进入后，右上角的「仪表」摊开客厅的全部账目与记录。</p>
  </section>

  <!-- 客厅屏：伙伴卡（上下发丝线夹住）+ 信笺流（教学短笺随信流）+ 写信区 -->
  <section id="screen-living" hidden>
    <header class="top">
      <div>
        <div class="who">英语客厅</div>
        <div class="who-sub">固定伙伴 · 你说英语，它用英语回你</div>
      </div>
      <button id="meter-toggle" class="meter" type="button">仪表</button>
    </header>
    <main class="flow">
      <div id="messages" aria-live="polite"></div>
      <div id="moments"></div>
    </main>
    <div class="dock">
      <form id="send" class="dock-row">
        <textarea id="text" class="pen" rows="2" autocomplete="off"
                  placeholder="用英语说点什么……"></textarea>
        <button type="submit" class="send">寄出 →</button>
      </form>
    </div>
  </section>

  <!-- 仪表屏（设置）：诚实事实屏。模型端点与模型名由启动命令给定，页面没有
       读取它们的口——宁缺勿假，不显示。学习与诊断两个区块点开即读（就地
       展开），回客厅链接回客厅屏。 -->
  <section id="screen-set" class="set" hidden>
    <h2>仪表</h2>
    <p class="sub">客厅的账目与记录摊在这里——只读，如实。</p>
    <p class="sub">本地单用户 · 127.0.0.1 · 无鉴权。模型端点与模型名由启动
       命令给定，页面不读取、不显示（宁缺勿假）。</p>
    <div class="setlinks">
      <button type="button" class="setlink" data-block="learning">学习</button>
      <button type="button" class="setlink" data-block="diagnostics">诊断</button>
    </div>

    <section id="set-learning" class="setblock" hidden>
      <div class="sec">
        <h3>可教目标</h3>
        <div id="target-list"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>复习日程</h3>
        <div id="learn-schedule"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>学习目标</h3>
        <div id="learn-goals"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>证据记录</h3>
        <div id="learn-evidence"><p class="note">暂无数据</p></div>
      </div>
      <button id="learning-refresh" class="refresh" type="button">刷新读数</button>
    </section>

    <section id="set-diagnostics" class="setblock" hidden>
      <div class="sec">
        <h3>观察读数</h3>
        <button id="obs" class="refresh" type="button">拉取观察读数</button>
        <pre id="obsout" hidden></pre>
      </div>
      <div class="sec">
        <h3>为什么教了这一课？</h3>
        <div id="why-teach"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>为什么没有教？</h3>
        <div id="why-not-teach"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>证据有什么变化？</h3>
        <div id="why-evidence"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>你看到了哪些支持？</h3>
        <div id="why-support"><p class="note">暂无数据</p></div>
      </div>
      <div class="sec">
        <h3>有没有轮次被降级？</h3>
        <div id="why-degraded"><p class="note">无降级记录</p></div>
      </div>
      <button id="diag-refresh" class="refresh" type="button">刷新读数</button>
    </section>

    <button id="back-to-living" class="back" type="button">← 回客厅</button>
  </section>

</div>
<script>
"use strict";
const messages = document.getElementById("messages");
const momentsBox = document.getElementById("moments");

function scrollBottom() {
  window.scrollTo(0, document.body.scrollHeight);
}

// F-1R: the letter flow — a turn's words become letters, never bubbles.
// The user's line is the torn-edge reply slip (.letter.me .paper), the
// parlor's is the plain sheet (.letter.may); a failure is marginalia (a
// pencil rule in the left margin), a system note is a centered faint
// line. Every word rides textContent — the user's own words stay inert
// text, never markup.
function addLine(cls, text) {
  let node;
  if (cls === "user") {
    node = document.createElement("div");
    node.className = "letter me";
    const paper = document.createElement("div");
    paper.className = "paper";
    const say = document.createElement("p");
    say.className = "say";
    say.textContent = text;            // textContent, never markup: the
    paper.appendChild(say);            // user's own words stay inert text
    node.appendChild(paper);
  } else if (cls === "assistant") {
    node = document.createElement("div");
    node.className = "letter may";
    const say = document.createElement("p");
    say.className = "say";
    say.textContent = text;
    node.appendChild(say);
  } else if (cls === "typing") {
    node = document.createElement("p");
    node.className = "typing";
    node.textContent = text;
  } else if (cls === "failure") {
    node = document.createElement("p");
    node.className = "errline";
    node.textContent = text;
  } else {
    node = document.createElement("p");
    node.className = "sysline";
    node.textContent = text;
  }
  messages.appendChild(node);
  scrollBottom();
  return node;
}

// F-1R: the three screens — 开张 / 客厅 / 仪表 — plain show/hide, no
// router, no tab bar: the parlor header's 仪表 link leads to the set
// screen and its 回客厅 link leads back.
const screens = {
  onboard: document.getElementById("screen-onboard"),
  living: document.getElementById("screen-living"),
  set: document.getElementById("screen-set"),
};

function showScreen(name) {
  for (const key of Object.keys(screens)) {
    screens[key].hidden = key !== name;
  }
  window.scrollTo(0, 0);
}

document.getElementById("meter-toggle").addEventListener("click",
  () => showScreen("set"));
document.getElementById("back-to-living").addEventListener("click",
  () => showScreen("living"));

// F-1R: the set screen's two blocks — 学习 and 诊断 — expand in place
// (the F-1R task book leaves the choice to this page, recorded here):
// the expansion pulls the block's read, the refresh links re-pull.
function toggleSetBlock(name) {
  document.getElementById("set-learning").hidden = name !== "learning";
  document.getElementById("set-diagnostics").hidden =
    name !== "diagnostics";
  if (name === "diagnostics") loadDiagnostics();
  if (name === "learning") { loadTargets(); loadLearning(); }
}

for (const link of document.querySelectorAll(".setlink")) {
  link.addEventListener("click", () =>
    toggleSetBlock(link.dataset.block || "learning"));
}

// F-1R: the first-visit screen. localStorage remembers the visit; a
// storage that refuses (privacy mode) answers "seen" so nobody is
// trapped on the cover page, and a mark that fails to persist costs
// nothing — the parlor does not depend on it.
const ONBOARD_KEY = "elp.parlor.onboarded.v1";

function seenOnboard() {
  try {
    return localStorage.getItem(ONBOARD_KEY) === "1";
  } catch {
    return true;
  }
}

function markOnboarded() {
  try {
    localStorage.setItem(ONBOARD_KEY, "1");
  } catch {
    // 存不进去就下次再问一次：聊天不受影响
  }
}

document.getElementById("ob-go").addEventListener("click", () => {
  markOnboarded();
  showScreen("living");
});

// W-6: the attempt loop, made legible. The verdict is a prominent strip
// (the symbol is display only; the words are the runtime's own), and a
// submitted reply is visible the instant it goes out — a help reply waits
// out a model round trip, and a silent wait reads as a dead page.
function outcomeSymbol(feedback) {
  const word = String(feedback).split("（")[0];
  if (word === "SUCCESS" || word === "ALTERNATIVE_SUCCESS") return "✓";
  if (word === "PARTIAL") return "◐";
  if (word === "FAILURE") return "✗";
  return "";
}

function showResultStrip(card, feedback) {
  const symbol = outcomeSymbol(feedback);
  const strip = document.createElement("div");
  strip.className = "resultstrip " +
    (symbol === "✓" ? "ok" : symbol === "✗" ? "miss" : "part");
  strip.textContent = (symbol ? symbol + " " : "") + "判分反馈：" + feedback;
  card.appendChild(strip);
}

function setReplyBusy(card, busy, note) {
  for (const button of Array.from(card.querySelectorAll("button"))) {
    button.disabled = busy;
  }
  const input = card.querySelector(".replytext");
  if (input) input.disabled = busy;
  let strip = card.querySelector(".busystrip");
  if (busy) {
    if (!strip) {
      strip = document.createElement("div");
      strip.className = "busystrip";
      card.appendChild(strip);
    }
    strip.textContent = note;
  } else if (strip) {
    strip.remove();
  }
}

// W-4: the teaching card must not wait for the model. The moment row is
// durable the instant the turn opens it (OPENING), so the page polls the
// read-only current face (served off the work queue — it answers while the
// generation is still running) and re-renders with the turn response.
let momentTimer = null;
let momentPollStart = 0;
const MOMENT_POLL_MS = 400;
const MOMENT_POLL_MAX_MS = 90000;

function stopMomentPolling() {
  if (momentTimer !== null) {
    clearInterval(momentTimer);
    momentTimer = null;
  }
}

function startMomentPolling() {
  stopMomentPolling();
  momentPollStart = Date.now();
  momentTimer = setInterval(async () => {
    if (Date.now() - momentPollStart > MOMENT_POLL_MAX_MS) {
      stopMomentPolling();
      return;
    }
    try {
      const res = await fetch("/api/teaching/current");
      const data = await res.json();
      if (data.moment) showMoments([data.moment]);
    } catch {
      // a failed poll just waits for the next tick; the turn response
      // re-renders the card authoritatively when it lands
    }
  }, MOMENT_POLL_MS);
}

function showMoments(list) {
  momentsBox.textContent = "";
  if (!list.length) {
    const p = document.createElement("p");
    p.className = "note";
    p.textContent = "本轮没有打开教学时刻。";
    momentsBox.appendChild(p);
    return;
  }
  for (const m of list) {
    const card = document.createElement("div");
    card.className = "note-paper";
    const b = document.createElement("b");
    if (m.title) {
      b.textContent = "教学时刻：" + m.title;
      card.appendChild(b);
      card.appendChild(document.createTextNode(
        " · 状态 " + (m.status_cn || m.lifecycle_state) +
        " · " + (m.kind_cn || m.kind)));
    } else {
      b.textContent = m.focus_target_id;
      card.appendChild(b);
      card.appendChild(document.createTextNode(
        " · 状态 " + m.lifecycle_state + " · 类型 " + m.kind));
    }
    if (m.last_attempt_feedback) {
      // W-6: the verdict survives a refresh — the ro current card carries
      // the moment's latest durable evaluation outcome
      showResultStrip(card, m.last_attempt_feedback);
    }
    if (m.lifecycle_state === "AWAITING_USER") {
      // the W-2/W-3 reply face: a moment waiting for the user offers the
      // attempt box (their own English sentence, judged) and the skip
      addReplyControls(card);
    }
    momentsBox.appendChild(card);
  }
}

function addReplyControls(card) {
  const row = document.createElement("div");
  row.className = "replyrow";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "replytext";
  input.autocomplete = "off";
  input.placeholder = "用英语试着造个句子…";
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "send";
  submit.textContent = "寄出作答";
  submit.addEventListener("click", () => submitAttempt(card, input));
  row.appendChild(input);
  row.appendChild(submit);
  card.appendChild(row);
  // W-6: the three help arms SM §1 names, as pencil links at the note's
  // tail — the words map onto the runtime's ASK_HINT / ASK_ANSWER /
  // ASK_EXPLANATION and nothing else
  const help = document.createElement("div");
  help.className = "replyrow";
  help.appendChild(helpButton("看提示", "hint", "取提示中…", "已看提示", card));
  help.appendChild(helpButton("看答案", "reveal", "取答案中…", "已看答案", card));
  help.appendChild(helpButton("解释", "explanation", "取解释中…", "已看解释", card));
  card.appendChild(help);
  // W-2: the skip — a faint small link under the help arms; the moment's
  // lock releases through the runtime's own reply entry, nothing else
  const skip = document.createElement("button");
  skip.type = "button";
  skip.className = "skiplink";
  skip.textContent = "跳过这一题";
  skip.addEventListener("click", () =>
    postReply(card, { control: "skip" }, "跳过中…", "教学已跳过"));
  card.appendChild(skip);
}

function helpButton(label, control, busyText, doneNote, card) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", () => {
    if (control === "reveal" &&
        !window.confirm("看答案将显示完整目标表达，之后你仍可作答，确定？")) {
      return;
    }
    postReply(card, { control: control }, busyText, doneNote);
  });
  return button;
}

function disarmMomentCard(card) {
  for (const row of Array.from(card.querySelectorAll(".replyrow"))) {
    row.remove();
  }
}

function readReplyAnswer(card, data) {
  // the reply result's own words, never a fabricated one: the new state
  // plus the feedback verdict (as the W-6 result strip) when the reply
  // carried one
  disarmMomentCard(card);
  card.appendChild(document.createElement("br"));
  const b = document.createElement("b");
  b.textContent = data.moment_state === "AWAITING_USER"
    ? "再试一次？"
    : "本次回应已收下";
  card.appendChild(b);
  card.appendChild(document.createTextNode(
    " · 状态 " + (data.moment_state || "未知")));
  if (data.feedback !== null && data.feedback !== undefined) {
    showResultStrip(card, data.feedback);
  }
  if (data.moment_state === "AWAITING_USER") {
    // the moment lives on (a miss re-prompts, an authorized reveal leaves
    // the post-reveal optional attempt open): the user can retry or skip
    addReplyControls(card);
  } else {
    card.classList.add("skipped");
  }
}

async function postReply(card, payload, busyText, doneNote) {
  // W-6: one reply path for all five control words — the busy strip goes
  // up before the fetch and every control is disabled, so the multi-second
  // model round trip is never silent; a failed fetch (network gone, a
  // non-2xx) is one human line, and the card rearms either way
  setReplyBusy(card, true, busyText);
  try {
    const res = await fetch("/api/teaching_reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.status !== 200) {
      addLine("failure", data.error || "提交失败，请重试");
      return;
    }
    if (!data.accepted) {
      addLine("failure", data.error || "无法提交这个作答");
      return;
    }
    addLine("system", doneNote);
    if (data.delivery_text) {
      // the runtime's own delivered words (the hint rung / the reveal
      // form / the explanation), shown like any assistant line
      addLine("assistant", data.delivery_text);
    }
    readReplyAnswer(card, data);
  } catch {
    addLine("failure", "提交失败，请重试");
  } finally {
    setReplyBusy(card, false);
  }
}

async function submitAttempt(card, input) {
  const text = input.value.trim();
  if (!text) return;
  await postReply(card, { control: "attempt", text: text }, "批改中…", "已提交作答");
}

async function postTurn(text) {
  addLine("user", text);
  // the placeholder is the user's "it is working" signal: removed the
  // moment the turn response lands (or fails) — never left behind
  const pending = addLine("typing", "（生成中…）");
  startMomentPolling();
  let data = null;
  try {
    const res = await fetch("/api/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    });
    data = await res.json();
  } finally {
    stopMomentPolling();
    pending.remove();
  }
  if (data !== null) {
    if (data.reply !== null && data.reply !== undefined) {
      addLine("assistant", data.reply);
    } else if (data.turn_status !== null && data.turn_status !== undefined) {
      addLine("failure", "[" + data.turn_status + "] " +
        (data.failure_reason || "无回复"));
    } else if (data.failure_reason) {
      addLine("failure", data.failure_reason);
    }
    const moments = data.teaching_moments || [];
    showMoments(moments);
    // F-2: a turn that taught nothing says why, in one gray line under
    // the transcript — read from the diagnostics face, silent when the
    // read fails or has nothing to say.
    if (!moments.length) showBlockedNote();
  }
}

document.getElementById("send").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  postTurn(text);
});

// The pen is a lined-paper textarea (the anchor's own .pen): plain Enter
// posts the letter, Shift+Enter stays a line break.
document.getElementById("text").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.getElementById("send").requestSubmit();
  }
});

document.getElementById("obs").addEventListener("click", async () => {
  const out = document.getElementById("obsout");
  const res = await fetch("/api/observations");
  const data = await res.json();
  const lines = [];
  for (const ind of data.indicators) {
    lines.push(ind.indicator + " — " + ind.definition);
  }
  lines.push("");
  for (const s of data.sections) {
    lines.push(s.title + ":");
    if (s.error !== null) { lines.push("  (unreadable: " + s.error + ")"); continue; }
    if (!s.rows.length) { lines.push("  (no rows)"); continue; }
    for (const row of s.rows) lines.push("  " + row.join(" | "));
  }
  lines.push("  gate rows naming " + data.drift_reason +
    " (the drift signal): " + data.drift_count);
  out.hidden = false;
  out.textContent = lines.join("\\n");
});

// F-1: the diagnostics view — the five whys, read from /api/diagnostics.
// Chinese labels over the raw numbers; a panel with nothing to say says so.
const OUTCOME_CN = {
  SUCCESS: "回答正确",
  ALTERNATIVE_SUCCESS: "回答正确（另一种合格表达）",
  PARTIAL: "部分正确",
  FAILURE: "未命中目标表达",
  ABSTAIN: "本次作答无法评判",
};
const ACTION_CN = {
  TEACHING_OPEN: "打开教学",
  TEACHING_HINT: "给提示",
  TEACHING_REVEAL: "展示答案",
  TEACHING_EXPLANATION: "给解释",
};

function fmtNum(value) {
  return (value === null || value === undefined) ? "—" : String(value);
}

function diagBox(id) {
  return document.getElementById(id);
}

function diagEmpty(box, word) {
  const p = document.createElement("p");
  p.className = "note";
  p.textContent = word || "暂无数据";
  box.appendChild(p);
}

function diagError(box, message) {
  const p = document.createElement("p");
  p.className = "diagerror";
  p.textContent = "读取失败：" + message;
  box.appendChild(p);
}

function diagLine(box, label, value) {
  const row = document.createElement("div");
  row.className = "kv";
  const b = document.createElement("b");
  b.textContent = label + "：";
  row.appendChild(b);
  row.appendChild(document.createTextNode(String(value)));
  box.appendChild(row);
}

function diagGroup(box, title) {
  const g = document.createElement("div");
  g.className = "kvgroup";
  const b = document.createElement("b");
  b.className = "kvtitle";
  b.textContent = title;
  g.appendChild(b);
  box.appendChild(g);
  return g;
}

function renderWhyTeach(d) {
  const box = diagBox("why-teach");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  if (!d.candidate) {
    diagEmpty(box, "暂无数据——最近 50 轮规划评估里没有选中任何候选。");
    return;
  }
  const g = diagGroup(box, "被选中的候选");
  diagLine(g, "目标（canonical_key）", d.candidate.canonical_key);
  diagLine(g, "收益分 benefit", fmtNum(d.candidate.benefit_score));
  diagLine(g, "成本分 cost", fmtNum(d.candidate.cost_score));
  diagLine(g, "效用 utility", fmtNum(d.candidate.utility));
  if (d.gate) {
    const gg = diagGroup(box, "门（Gate）裁决");
    diagLine(gg, "裁决", d.gate.decision);
    const codes = d.gate.reason_codes;
    diagLine(gg, "理由码", Array.isArray(codes) ? codes.join("、") : String(codes));
    diagLine(gg, "时间", d.gate.created_at);
  }
  diagLine(box, "评估时间", d.created_at);
}

function renderWhyNot(d) {
  const box = diagBox("why-not-teach");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  const list = d.candidates || [];
  if (d.created_at === null && !list.length) {
    diagEmpty(box, "暂无数据——还没有任何一轮规划评估。");
    return;
  }
  if (!list.length) {
    diagLine(box, "本轮未激活候选", "无（本轮候选全部激活，或本轮没有候选）");
  }
  for (const c of list) {
    const g = diagGroup(box, c.canonical_key || c.candidate_id);
    diagLine(g, "效用 vs 阈值",
      fmtNum(c.utility) + "  vs  " + fmtNum(c.activation_threshold));
    diagLine(g, "是否激活",
      c.activated === false ? "未激活（activated: false）" : String(c.activated));
    for (const r of (c.costs || [])) {
      diagLine(g, "成本因子 " + r.factor, fmtNum(r.value));
    }
  }
  if (d.gate_deny) {
    const gg = diagGroup(box, "最近一次门拦截（DENY）");
    const codes = d.gate_deny.reason_codes;
    diagLine(gg, "理由码", Array.isArray(codes) ? codes.join("、") : String(codes));
    diagLine(gg, "时间", d.gate_deny.created_at);
  }
}

function renderEvidence(d) {
  const box = diagBox("why-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  const rows = d.records || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有任何一次作答被判分。");
    return;
  }
  for (const r of rows) {
    const g = diagGroup(box, OUTCOME_CN[r.outcome] || r.outcome);
    diagLine(g, "outcome", r.outcome);
    diagLine(g, "confidence", fmtNum(r.confidence));
    diagLine(g, "时间", r.created_at);
  }
}

function renderSupport(d) {
  const box = diagBox("why-support");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  const rows = d.actions || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有任何一次教学支持被交付。");
    return;
  }
  for (const a of rows) {
    const g = diagGroup(box, ACTION_CN[a.action_type] || a.action_type);
    diagLine(g, "action_type", a.action_type);
    diagLine(g, "时间", a.created_at);
  }
  diagLine(box, "曝光估计累计（exposure_estimate）",
    d.exposure_estimate_count + " 条");
}

function renderDegraded(d) {
  const box = diagBox("why-degraded");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  const pe = d.planner_execution;
  const ro = d.runtime_outcome;
  if (!pe && !ro) { diagEmpty(box, "无降级记录"); return; }
  if (pe) {
    const g = diagGroup(box, "Planner 执行状态");
    diagLine(g, "status", pe.status);
    diagLine(g, "error_code", pe.error_code === null ? "—" : pe.error_code);
    diagLine(g, "时间", pe.created_at);
  }
  if (ro) {
    const g = diagGroup(box, "运行时轮次结局");
    diagLine(g, "outcome", ro.outcome);
    const codes = ro.reason_codes;
    diagLine(g, "理由码", Array.isArray(codes) ? codes.join("、") : String(codes));
    diagLine(g, "时间", ro.created_at);
  }
}

async function loadDiagnostics() {
  try {
    const res = await fetch("/api/diagnostics");
    const data = await res.json();
    renderWhyTeach(data.why_teach);
    renderWhyNot(data.why_not_teach);
    renderEvidence(data.evidence);
    renderSupport(data.support);
    renderDegraded(data.degraded);
  } catch {
    for (const id of ["why-teach", "why-not-teach", "why-evidence",
                      "why-support", "why-degraded"]) {
      diagError(diagBox(id), "诊断读数拉取失败");
    }
  }
}

document.getElementById("diag-refresh").addEventListener("click", loadDiagnostics);

// F-2: the 学习 view — what can be taught, the schedule, the goals and
// the evidence ledger. Read-only numbers under Chinese labels; the one
// act is 教我这个, which asks the runtime to open the teaching.
async function loadTargets() {
  const box = diagBox("target-list");
  box.textContent = "";
  try {
    const res = await fetch("/api/targets");
    const data = await res.json();
    const list = data.targets || [];
    if (!list.length) { diagEmpty(box, "暂无可教目标"); return; }
    for (const t of list) {
      const row = document.createElement("div");
      row.className = "kv";
      const b = document.createElement("b");
      b.textContent = t.name || t.target_id;
      row.appendChild(b);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "teach-me";
      button.textContent = "教我这个";
      button.addEventListener("click", () => postTeachMe(t.target_id));
      row.appendChild(button);
      box.appendChild(row);
    }
  } catch {
    diagError(box, "目标清单拉取失败");
  }
}

async function postTeachMe(targetId) {
  try {
    const res = await fetch("/api/teach_me", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: targetId }),
    });
    const data = await res.json();
    if (data.accepted) {
      addLine("system", "教学已开始，卡片出现在下方");
      showScreen("living");
      startMomentPolling();
    } else {
      addLine("failure", data.error || "无法开始这节课");
    }
  } catch {
    addLine("failure", "请求失败，请重试");
  }
}

function renderSchedule(d) {
  const box = diagBox("learn-schedule");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  const rows = d.items || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有任何复习日程。");
    return;
  }
  for (const it of rows) {
    const g = diagGroup(box, it.target_id + "（" + it.target_type + "）");
    diagLine(g, "复习状态", it.review_state);
    diagLine(g, "紧迫度 review_urgency", fmtNum(it.review_urgency));
    diagLine(g, "窗口开始", fmtNum(it.next_review_window_start));
    diagLine(g, "窗口结束", fmtNum(it.next_review_window_end));
    diagLine(g, "间隔阶 spacing_stage", fmtNum(it.spacing_stage));
    diagLine(g, "更新时间", it.updated_at);
  }
}

function renderGoals(d) {
  const box = diagBox("learn-goals");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  const rows = d.portfolios || [];
  if (!rows.length) {
    diagEmpty(box, "暂无数据——还没有写下学习目标。");
    return;
  }
  for (const p of rows) {
    const g = diagGroup(box, p.goal_portfolio_id);
    const goals = p.goals || [];
    diagLine(g, "目标数", goals.length);
    for (const goal of goals) {
      diagLine(g, "目标 " + (goal.goal_id || ""),
        (goal.description || "") + " · " + (goal.goal_modality || ""));
    }
    const weights = p.modality_weights || {};
    for (const key of Object.keys(weights)) {
      diagLine(g, "权重 " + key, String(weights[key]));
    }
  }
}

function renderLearnEvidence(d) {
  const box = diagBox("learn-evidence");
  box.textContent = "";
  if (!d || d.error) { diagError(box, (d && d.error) || "空响应"); return; }
  diagLine(box, "证据记录总数", (d.evidence_claim_count || 0) + " 条");
  diagLine(box, "学习者目标状态", (d.learner_target_state_count || 0) + " 行");
  const rows = d.claims || [];
  if (!rows.length) {
    diagEmpty(box, "暂无单条记录——还没有任何证据被写入。");
    return;
  }
  for (const c of rows) {
    const g = diagGroup(box, c.target_id);
    diagLine(g, "polarity", c.polarity);
    diagLine(g, "outcome", c.outcome);
    diagLine(g, "performance_type", c.performance_type);
    diagLine(g, "时间", c.created_at);
  }
}

async function loadLearning() {
  try {
    const res = await fetch("/api/learning");
    const data = await res.json();
    renderSchedule(data.schedule);
    renderGoals(data.goals);
    renderLearnEvidence(data.evidence);
  } catch {
    for (const id of ["learn-schedule", "learn-goals", "learn-evidence"]) {
      diagError(diagBox(id), "学习读数拉取失败");
    }
  }
}

document.getElementById("learning-refresh").addEventListener("click",
  () => { loadTargets(); loadLearning(); });

// F-2: why a quiet turn was quiet — one gray line from the diagnostics
// face's why-not-teach panel. The gate lives in postTurn (only when the
// turn response carried no teaching moments); a failed or empty pull
// stays silent, the chat is never blocked by the note.
async function showBlockedNote() {
  let data = null;
  try {
    const res = await fetch("/api/diagnostics");
    data = await res.json();
  } catch {
    return;
  }
  const panel = data && data.why_not_teach;
  if (!panel || panel.error) return;
  let summary = "";
  const candidate = (panel.candidates || [])[0];
  if (candidate) {
    summary = "本轮未教学：候选 " +
      (candidate.canonical_key || candidate.candidate_id) +
      " 效用 " + fmtNum(candidate.utility) +
      " 低于阈值 " + fmtNum(candidate.activation_threshold);
  } else if (panel.gate_deny) {
    const codes = panel.gate_deny.reason_codes;
    summary = "本轮未教学：门拦截 " +
      (Array.isArray(codes) ? codes.join("、") : String(codes));
  } else {
    return;
  }
  const line = document.createElement("div");
  line.className = "blockedline";
  line.textContent = summary;
  messages.appendChild(line);
  messages.scrollTop = messages.scrollHeight;
}

async function loadHistory() {
  const res = await fetch("/api/history");
  const data = await res.json();
  for (const turn of data.turns) {
    if (turn.user !== null) addLine("user", turn.user);
    if (turn.assistant !== null) addLine("assistant", turn.assistant);
  }
  // the open teaching moment survives a refresh: rebuild its card (with
  // the attempt box and the skip button) so an open teaching is never
  // stranded without its controls
  const cur = await fetch("/api/teaching/current");
  const curData = await cur.json();
  if (curData.moment !== null) {
    showMoments([curData.moment]);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  loadHistory();
  // F-1R: the first visit sees the cover; every later visit lands in the
  // parlor directly (the cover never comes back once localStorage says so)
  showScreen(seenOnboard() ? "living" : "onboard");
});
</script>
</body>
</html>
"""


def _focus_id_of(document: str) -> str:
    """The target id out of a ``focus_target`` storage document.

    The durable form is the ``TeachingTargetRef`` JSON document (migration
    0007's storage note); the page names the id. A document that is not the
    expected shape raises — the answer is fabricated, never guessed.
    """

    parsed = json.loads(document)
    if not isinstance(parsed, dict) or "target_id" not in parsed:
        raise ValueError(
            f"teaching_moment.focus_target is not a target document: {document!r}"
        )
    return str(parsed["target_id"])


def _last_attempt_feedback_of(
    connection: sqlite3.Connection, moment_id: str
) -> str | None:
    """The open moment's latest evaluation verdict, readable (W-6).

    One read-only query over the same connection the card read on: the
    moment's most recent durable ``attempt_evaluation_record`` (the last
    ``created_at`` wins; ``rowid`` breaks a same-timestamp tie by insertion
    order), passed through :func:`_readable_outcome`. No evaluation yet —
    an untouched moment, a hint reply — is ``None``. The caller's own
    failure posture covers this read too: any exception answers
    ``{"moment": None}`` up there, never a 500."""

    row = connection.execute(
        "SELECT outcome FROM attempt_evaluation_record"
        " WHERE moment_id = ?"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (moment_id,),
    ).fetchone()
    if row is None:
        return None
    return _readable_outcome(str(row[0]))


def _current_teaching_ro(
    app_db_path: str, conversation_id: str
) -> dict[str, Any]:
    """The conversation's open teaching moment, read without the host.

    This is the W-4 immediacy face: a turn's teaching moment is durable at
    ``OPENING`` **before** the persona call starts, so the card's data sits
    in app.db for the whole (seconds-long) generation — but the host's own
    connections answer only the work-queue thread, which the turn's closure
    occupies until the model answers. This function therefore runs on the
    handler thread over its own short **read-only** connection (``mode=ro``,
    enforced by SQLite; :meth:`Path.as_uri` spells the Windows path with
    forward slashes so the URI parses), reads the same durable lock join the
    queued route used to read, and closes the connection before answering.

    It answers both ``OPENING`` (the generation-window card — "the teaching
    is opening", no reply controls) and ``AWAITING_USER`` (the W-3 reload
    card, controls and all) — exactly the poll's promise: the card appears
    while the model is still talking and turns into the reply card when the
    turn response lands.

    Two declared narrowings against the turn card (the same moment, served
    from this face): ``title`` is the target's spoken name out of its id
    (:func:`_target_display_name`) — the authored function sentence lives in
    content.db, whose path this face does not hold and whose store answers
    only the host's thread, so the hint-ladder title stays the turn card's;
    and the moment kind's own word is served unchanged. W-6 adds one field
    back the other way: ``last_attempt_feedback`` is the moment's latest
    durable evaluation verdict (readable), so a refresh re-renders the
    result strip instead of burying it. Any failure — a locked database, a
    missing file, a focus document in the wrong shape — answers
    ``{"moment": None}``: the page polls again, and a poll must never 500
    the user's browser.
    """

    try:
        uri = Path(app_db_path).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            row = connection.execute(
                "SELECT m.moment_id, m.focus_target, m.lifecycle_state,"
                " m.target_mode"
                " FROM active_teaching_lock l"
                " JOIN teaching_moment m ON m.moment_id = l.moment_id"
                " WHERE l.conversation_id = ?"
                " AND m.lifecycle_state IN (?, ?)",
                (
                    conversation_id,
                    MomentState.OPENING.value,
                    MomentState.AWAITING_USER.value,
                ),
            ).fetchone()
            if row is None:
                return {"moment": None}
            moment_id = str(row[0])
            focus_id = _focus_id_of(str(row[1]))
            state = str(row[2])
            kind = str(row[3])
            feedback = _last_attempt_feedback_of(connection, moment_id)
        finally:
            connection.close()
        return {
            "moment": {
                "focus_target_id": focus_id,
                "lifecycle_state": state,
                "kind": kind,
                "title": _target_display_name(focus_id),
                "status_cn": _RO_STATUS_CN.get(
                    state, _STATUS_CN.get(state, state)
                ),
                "kind_cn": _KIND_CN.get(kind, kind),
                "last_attempt_feedback": feedback,
            }
        }
    except Exception:
        # A poll that cannot read answers "nothing open" — the page's next
        # tick retries, and the turn response re-renders the card anyway.
        return {"moment": None}


def _commit(conversation_id: ConversationId, raw_content: str) -> CommitUserTurn:
    """One CP0 command for the web face: the CLI's envelope shape, ``web-`` ids.

    Shape-equal to ``elc.cli._commit`` on purpose (pinned in
    ``tests/host/test_w1_web.py``): only the id prefixes differ, so a turn the
    page commits is durable exactly like a turn the line loop commits.
    """

    suffix = uuid.uuid4().hex
    return CommitUserTurn(
        conversation_id=conversation_id,
        envelope=InputEnvelope(
            input_id=InputId(f"web-{suffix}"),
            client_message_id=ClientMessageId(f"web-msg-{suffix}"),
            conversation_id=str(conversation_id),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=raw_content,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=raw_content,
        runtime_version=RUNTIME_VERSION,
    )


class _WebFace:
    """The route implementations — every one touches the host, so every one
    runs on the host's thread (see the module docstring and :func:`run_web`)."""

    def __init__(self, host: Host, conversation: str) -> None:
        self._host = host
        self._conversation_id = ConversationId(conversation)
        # The read-only current face's two parameters, copied as plain
        # values: the handler thread reads these (never ``self._host``)
        # when it serves ``/api/teaching/current`` off the work queue.
        self.app_db_path = str(host.app_db_path)

    @property
    def conversation_id(self) -> str:
        """The conversation this face serves, as the read-only current
        face's parameter (a plain string, no host touch)."""

        return str(self._conversation_id)

    def turn(self, text: str) -> dict[str, Any]:
        """One committed turn, as the page renders it."""

        result = self._host.coordinator.begin_turn(
            _commit(self._conversation_id, text)
        )
        if isinstance(result, Err):
            return {
                "reply": None,
                "turn_status": None,
                "failure_reason": (
                    f"{result.error.code.value}: {result.error.message}"
                ),
                "teaching_moments": [],
            }
        completion = result.value
        return {
            "reply": completion.reply_text,
            "turn_status": completion.turn_status.value,
            "failure_reason": completion.failure_reason,
            "teaching_moments": self._moments_of_turn(str(completion.turn_id)),
        }

    def _moments_of_turn(self, turn_id: str) -> list[dict[str, str]]:
        """The moments of one turn, through the durable lineage.

        ``teaching_moment`` carries no ``turn_id`` column; the store's own
        epoch check walks ``moment → decision_cycle_id → decision_cycle.
        turn_id`` and that is the walk used here — "this turn's moments" is
        a lineage fact, not a latest-rows guess. ``focus_target_id`` is the
        id out of the moment's durable JSON document (the
        ``TeachingTargetRef`` storage form, ``elc.teaching.store``'s
        ``_target_from_document`` shape) and ``kind`` is the moment's
        ``target_mode``. ``title`` / ``status_cn`` / ``kind_cn`` are the
        card's human face on top of the same three durable facts (W-1R);
        the raw three fields stay first so older readers keep their shape.
        """

        rows = self._host.db.execute(
            "SELECT m.focus_target, m.lifecycle_state, m.target_mode"
            " FROM teaching_moment m"
            " JOIN decision_cycle d ON d.decision_cycle_id = m.decision_cycle_id"
            " WHERE d.turn_id = ?"
            " ORDER BY m.created_at, m.moment_id",
            (turn_id,),
        ).fetchall()
        moments: list[dict[str, str]] = []
        for row in rows:
            focus_id = _focus_id_of(str(row[0]))
            state = str(row[1])
            kind = str(row[2])
            moments.append(
                {
                    "focus_target_id": focus_id,
                    "lifecycle_state": state,
                    "kind": kind,
                    "title": self._moment_title(focus_id),
                    "status_cn": _STATUS_CN.get(state, state),
                    "kind_cn": _KIND_CN.get(kind, kind),
                }
            )
        return moments

    def _moment_title(self, target_id: str) -> str:
        """The card title for one focus target — the target's own words.

        Read through ``host.content_store``: rung 0 of the target's hint
        ladder is the authored function sentence ("Signal that you are
        returning to the main topic after a digression."), and the id tail
        is the spoken name — ``anyway — Signal that …``. Every failure (no
        content store on this host, unknown id, unreadable artifact) falls
        back to the raw id: a card may be plain, never broken.
        """

        store = self._host.content_store
        if store is None:
            return target_id
        try:
            view = store.get_teaching_content(target_id)
        except Exception:
            return target_id
        if isinstance(view, Err):
            return target_id
        hints = view.value.hint_ladder
        function = str(hints[0]).strip() if hints else ""
        name = _target_display_name(target_id)
        if not function:
            return name
        return f"{name} — {function}"

    def teaching_reply(
        self, control: str, text: str | None = None
    ) -> dict[str, Any]:
        """One user reply to the open teaching moment — five control words.

        The moment is located the way ``_moments_of_turn`` reads moments —
        through the durable rows, never a guess: the conversation's
        ``active_teaching_lock`` row names the one moment, and only a
        moment at ``AWAITING_USER`` is open for a reply. No such moment is
        the ordinary answer (``accepted: false`` + ``no open teaching
        moment``), not an error — the button can be pressed twice, and a
        stale page can press it after the moment already moved. The reply
        itself goes through the coordinator's own ``respond_to_teaching``
        entry with a fresh ``web-msg-`` id (CP0 replay safety, the turn
        face's id shape), so the §4 order, the durable records and the
        lock discipline stay the runtime's, unmodified:

        - ``"skip"`` submits SKIP with no attempt (the attemptless
          control the envelope contract demands);
        - ``"attempt"`` submits CONTINUE carrying the user's sentence as
          the attempt payload — the §4 step-3 evaluation judges it
          against the target's own answer key (the evaluator is pure, no
          model), a success closes the moment and releases the lock, and
          a miss re-prompts (the moment returns to ``AWAITING_USER``
          holding the lock, so the card can ask again);
        - ``"hint"`` / ``"reveal"`` / ``"explanation"`` (W-6) submit the
          SM §4 ask intents — ``ASK_HINT`` delivers the next hint rung,
          ``ASK_ANSWER`` the reveal, ``ASK_EXPLANATION`` the explanation.
          The mapping (:data:`_HELP_INTENT_BY_WORD`) is the whole
          feature; the §8 limits and the ladder stay the runtime's. An
          authorized reveal keeps the moment open at ``FULL_REVEAL``
          (SM §3's ``POST_REVEAL_OPTIONAL_ATTEMPT``: seeing the answer
          does not have to end the episode), it does not close it.

        An ``Err`` from the entry is a runtime fact — 200, ``accepted:
        false``, the error sentence; the face never fabricates a state,
        the reported ``moment_state`` is the reply result's own word (and
        stays consistent with the durable row the next read sees).
        ``feedback`` is the result's own evaluation verdict, readable, or
        ``None`` when the reply carried no evaluation — never a
        fabricated judgement. ``delivery_text`` (W-6, additive, present
        only when the runtime delivered words) is the result's own
        ``reply_text`` — the hint rung, the reveal form or the
        explanation the page should show; a control word outside the
        five-word grammar never reaches this face (the HTTP layer 400s
        it), so an unknown word here raises rather than silently meaning
        SKIP.
        """

        lock = self._host.db.execute(
            "SELECT m.lifecycle_state"
            " FROM active_teaching_lock l"
            " JOIN teaching_moment m ON m.moment_id = l.moment_id"
            " WHERE l.conversation_id = ?",
            (str(self._conversation_id),),
        ).fetchone()
        if lock is None or str(lock[0]) != MomentState.AWAITING_USER.value:
            return {
                "accepted": False,
                "moment_state": None,
                "error": "no open teaching moment",
                "feedback": None,
            }
        if control == "attempt":
            envelope = TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.CONTINUE,
                attempt_present=True,
                attempt=AttemptPayload(text=text or ""),
            )
        elif control == "skip":
            envelope = TeachingResponseEnvelope(
                control_intent=TeachingControlIntent.SKIP, attempt_present=False
            )
        else:
            intent = _HELP_INTENT_BY_WORD.get(control)
            if intent is None:
                raise ValueError(
                    f"unknown teaching reply control word: {control!r}"
                )
            envelope = TeachingResponseEnvelope(
                control_intent=intent, attempt_present=False
            )
        request = TeachingReplyRequest(
            conversation_id=self._conversation_id,
            envelope=envelope,
            client_message_id=ClientMessageId(f"web-msg-{uuid.uuid4().hex}"),
            requested_at=datetime.now(tz=UTC).isoformat(),
        )
        result = self._host.coordinator.respond_to_teaching(request)
        if isinstance(result, Err):
            return {
                "accepted": False,
                "moment_state": None,
                "error": f"{result.error.code.value}: {result.error.message}",
                "feedback": None,
            }
        answer: dict[str, Any] = {
            "accepted": True,
            "moment_state": result.value.moment_state.value,
            "error": None,
            "feedback": _feedback_of(result.value),
        }
        delivered = getattr(result.value, "reply_text", None)
        if delivered:
            answer["delivery_text"] = str(delivered)
        return answer

    def observations(self) -> dict[str, Any]:
        """The CLI readout's numbers, as JSON (one readings core)."""

        sections: tuple[ObservationSection, ...] = observation_sections(
            self._host.db
        )
        return {
            "indicators": [
                {"indicator": spec.indicator, "definition": spec.definition}
                for spec in OBSERVATION_SPECS
            ],
            "sections": [
                {
                    "title": s.title,
                    "rows": [list(row) for row in s.rows],
                    "error": s.error,
                }
                for s in sections
            ],
            "drift_reason": "TARGET_NOT_EXECUTABLY_VERIFIED",
            "drift_count": observation_drift_count(self._host.db),
        }

    def diagnostics(self) -> dict[str, Any]:
        """The five-whys readout — read-only SQL, one guarded panel per why.

        Served on the work queue over ``host.db`` (the module docstring
        records why this face does not need the W-4 ro bypass: a person
        pulls it from the diagnostics view, never mid-generation). Every
        panel is a plain ``SELECT``; nothing here writes, ever. A panel
        whose read explodes answers ``{"error": …}`` in its own slot and
        the other four still answer; a panel with no durable rows answers
        its honest empty shape, which the page renders as 暂无数据 /
        无降级记录 — never a fabricated number.
        """

        db = self._host.db
        return {
            "why_teach": _diagnostics_panel(
                "why_teach", _why_teach_panel, db
            ),
            "why_not_teach": _diagnostics_panel(
                "why_not_teach", _why_not_teach_panel, db
            ),
            "evidence": _diagnostics_panel("evidence", _evidence_panel, db),
            "support": _diagnostics_panel("support", _support_panel, db),
            "degraded": _diagnostics_panel("degraded", _degraded_panel, db),
        }

    def learning(self) -> dict[str, Any]:
        """The 学习 view's one read — the F-2 three panels.

        The diagnostics route's construction, repeated: read-only SQL on
        the work queue over ``host.db`` (the view is pulled by a person,
        never mid-generation), each panel guarded separately — a panel
        whose read explodes answers ``{"error": …}`` in its own slot and
        the other two still answer; a panel with no durable rows answers
        its honest empty shape. Nothing here writes, ever (pinned by a
        content-snapshot test, the diagnostics pin's shape).
        """

        db = self._host.db
        return {
            "schedule": _diagnostics_panel("schedule", _schedule_panel, db),
            "goals": _diagnostics_panel("goals", _goals_panel, db),
            "evidence": _diagnostics_panel(
                "learning_evidence", _learning_evidence_panel, db
            ),
        }

    def targets(self) -> dict[str, Any]:
        """What can be taught, from the first face the host actually holds.

        With a content leg (the full-chain tier), the curriculum
        readiness table is the source: every target whose §8.1 level is
        R3 or above (the ladder index, not a word list), ``source`` says
        ``readiness>=R3``. Without one (the prep-1 tier) the honest
        fallback is the ``schedule_item`` target set — "schedule 覆盖的
        供给目标", ``source`` says ``schedule_item`` — never an invented
        corpus. Names are :func:`_target_display_name`'s, the card's own
        reading of the id.
        """

        curriculum = self._host.curriculum
        if curriculum is None:
            rows = self._host.db.execute(
                "SELECT DISTINCT target_id FROM schedule_item"
                " ORDER BY target_id"
            ).fetchall()
            return {
                "source": "schedule_item",
                "targets": [
                    {
                        "target_id": str(row[0]),
                        "name": _target_display_name(str(row[0])),
                    }
                    for row in rows
                ],
            }
        read = curriculum.readiness_by_target()
        if isinstance(read, Err):
            raise RuntimeError(
                "the readiness table could not be read:"
                f" {read.error.code.value}: {read.error.message}"
            )
        floor = READINESS_LEVELS.index(_TARGETS_READINESS_FLOOR)
        return {
            "source": "readiness>=R3",
            "targets": [
                {
                    "target_id": assessment.target_id,
                    "name": _target_display_name(assessment.target_id),
                }
                for assessment in read.value
                if assessment.level is not None
                and READINESS_LEVELS.index(assessment.level) >= floor
            ],
        }

    def teach_me(self, target_id: str) -> dict[str, Any]:
        """The 学习 view's one act: teach this target now.

        A :class:`~elc.teaching.request.TeachingRequest` through the
        coordinator's own ``request_teaching`` entry (``RESOURCE`` scope,
        a fresh ``web-msg-`` id — the turn face's replay-safe shape).
        One survey fact this face is built on: that single call is the
        whole chain — the P3-1B opening delivery is dispatched inside the
        entry (the docstring's "stops at CP2" is stale P3-1A prose; the
        happy-path test pins the delivered truth), so an ALLOW answer
        already carries the moment at ``AWAITING_USER`` and the page's
        W-4 poll picks the card up. No follow-up call exists or is
        needed.

        A refusal is a runtime fact, never an HTTP error (200 +
        ``accepted: false`` + the error sentence — an ``Err`` code, or
        the Gate's own DENY reason codes such as
        ``TEACHING_LOCK_CONFLICT`` for a moment already open, or a
        DEGRADED's missing facts): the face passes the verdict through
        and fabricates nothing.
        """

        request = TeachingRequest(
            conversation_id=self._conversation_id,
            focus_target_id=TargetId(target_id),
            target_type="RESOURCE",
            client_message_id=ClientMessageId(f"web-msg-{uuid.uuid4().hex}"),
            requested_at=datetime.now(tz=UTC).isoformat(),
        )
        result = self._host.coordinator.request_teaching(request)
        if isinstance(result, Err):
            return {
                "accepted": False,
                "error": f"{result.error.code.value}: {result.error.message}",
                "moment": None,
            }
        value = result.value
        if value.gate_decision != "ALLOW" or value.moment_id is None:
            reasons = [*value.reason_codes, *value.missing_or_unknown]
            detail = "、".join(reasons) if reasons else "the gate said no"
            code = value.gate_decision or "GATE"
            return {
                "accepted": False,
                "error": f"{code}: {detail}",
                "moment": None,
            }
        state = (
            value.moment_state.value
            if value.moment_state is not None
            else None
        )
        return {
            "accepted": True,
            "error": None,
            "moment": {
                "moment_id": str(value.moment_id),
                "focus_target_id": target_id,
                "lifecycle_state": state,
                "status_cn": _RO_STATUS_CN.get(state, state) if state else None,
            },
        }

    def history(self) -> dict[str, Any]:
        """The canonical transcript window — what the page recovers on load.

        The store's own window read (delivered assistant output only;
        teaching command turns never appear), oldest first.
        """

        window = self._host.conversations.get_conversation_window(
            self._conversation_id, HISTORY_TURNS
        )
        if isinstance(window, Err):
            raise RuntimeError(
                "the conversation window could not be read:"
                f" {window.error.code.value}: {window.error.message}"
            )
        turns: list[dict[str, str | None]] = []
        for slice_ in window.value.slices:
            turns.append(
                {
                    "user": slice_.user_turn.raw_content,
                    "assistant": (
                        None
                        if slice_.assistant_turn is None
                        else slice_.assistant_turn.content
                    ),
                }
            )
        return {"turns": turns}


class _WebServer(ThreadingHTTPServer):
    """The loopback-bound server with its face and work queue attached."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        face: _WebFace,
        work: queue.Queue[Callable[[], None]],
    ) -> None:
        super().__init__(address, handler)
        self.face = face
        self.work = work


def _build_server(
    host: Host, port: int, *, conversation: str = DEFAULT_WEB_CONVERSATION_ID
) -> _WebServer:
    """Bind the face to one loopback address — the construction half of
    :func:`run_web`, exposed as the bind pin's seam (the pin reads
    ``server_address`` off this, and so can a test)."""

    face = _WebFace(host, conversation)
    work: queue.Queue[Callable[[], None]] = queue.Queue()

    class Handler(BaseHTTPRequestHandler):
        """HTTP plumbing only: parse, ship the host work, serialize.

        ``face`` and ``work`` are the closure this class is defined in — the
        handler never reaches through ``self.server``, so the request thread
        touches nothing but HTTP parsing, JSON and the queue.
        """

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self) -> None:
            body = _PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _run_on_host_thread(self, route: Callable[[], Any]) -> None:
            """Ship one host-touching route to the work loop and wait.

            The closure runs on the thread that opened the host's sqlite
            connections (the ``run_web`` caller's); a route that raises
            answers 500 with the reason — a failed read is a server fact,
            never a fabricated payload.
            """

            box: dict[str, Any] = {}
            failure: list[str] = []
            done = threading.Event()

            def job() -> None:
                try:
                    box["payload"] = route()
                except Exception as exc:  # answered, never swallowed
                    failure.append(f"{type(exc).__name__}: {exc}")
                finally:
                    done.set()

            work.put(job)
            if not done.wait(timeout=_WORKER_WAIT_SECONDS):
                self._send_json(
                    500, {"error": "the host worker did not answer in time"}
                )
                return
            if failure:
                self._send_json(500, {"error": failure[0]})
                return
            self._send_json(200, box["payload"])

        def do_GET(self) -> None:
            if self.path == "/":
                self._send_html()
            elif self.path == "/api/history":
                self._run_on_host_thread(face.history)
            elif self.path == "/api/teaching/current":
                # The one route served off the work queue (module docstring,
                # "The one exception"): a read-only poll must not queue
                # behind a turn's generation, which occupies the worker for
                # the whole model round trip. A poll that cannot read
                # answers {"moment": None}, never a 500.
                self._send_json(
                    200,
                    _current_teaching_ro(
                        face.app_db_path, face.conversation_id
                    ),
                )
            elif self.path == "/api/diagnostics":
                # The five-whys readout, read-only, on the work queue (the
                # module docstring records the choice: the diagnostics view
                # is pulled by a person, not mid-generation — no ro bypass
                # needed). Panel-level errors ride inside the payload.
                self._run_on_host_thread(face.diagnostics)
            elif self.path == "/api/learning":
                # The F-2 learning readout — the diagnostics construction
                # repeated: read-only, work queue, panel-level errors ride
                # inside the payload.
                self._run_on_host_thread(face.learning)
            elif self.path == "/api/targets":
                # The teachable-target list (readiness R3+ when the host
                # holds a content leg, the schedule set otherwise). A read
                # failure is a server fact: the route's own 500 posture.
                self._run_on_host_thread(face.targets)
            elif self.path == "/api/observations":
                self._run_on_host_thread(face.observations)
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path not in (
                "/api/turn",
                "/api/teaching_reply",
                "/api/teach_me",
            ):
                self._send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if self.path == "/api/teaching_reply":
                # The reply grammar is {"control": "skip"},
                # {"control": "attempt", "text": "..."} and the three W-6
                # help words {"control": "hint" | "reveal" |
                # "explanation"} — any other body (no JSON, another key,
                # an unknown control word, an attempt without a
                # non-empty text) is a bad request, not a runtime fact.
                control = (
                    payload.get("control") if isinstance(payload, dict) else None
                )
                if control == "attempt":
                    text = payload.get("text")
                    if not isinstance(text, str) or not text.strip():
                        self._send_json(
                            400,
                            {
                                "error": (
                                    'need a JSON body {"control": "attempt",'
                                    ' "text": "..."} with a non-empty text'
                                )
                            },
                        )
                        return
                    self._run_on_host_thread(
                        lambda: face.teaching_reply("attempt", text)
                    )
                    return
                if control == "skip":
                    self._run_on_host_thread(lambda: face.teaching_reply("skip"))
                    return
                if control in _HELP_INTENT_BY_WORD:
                    self._run_on_host_thread(
                        partial(face.teaching_reply, str(control))
                    )
                    return
                self._send_json(
                    400,
                    {
                        "error": (
                            'need a JSON body {"control": "skip"} or'
                            ' {"control": "attempt", "text": "..."} or'
                            ' {"control": "hint" | "reveal" |'
                            ' "explanation"}'
                        )
                    },
                )
                return
            if self.path == "/api/teach_me":
                # The F-2 grammar is one shape: {"target_id": "..."} — a
                # body without JSON, without a non-empty target_id string,
                # is a bad request, not a runtime fact; a runtime refusal
                # (an unknown target, the lock held) rides 200 below.
                target_id = (
                    payload.get("target_id")
                    if isinstance(payload, dict)
                    else None
                )
                if not isinstance(target_id, str) or not target_id.strip():
                    self._send_json(
                        400,
                        {"error": 'need a JSON body {"target_id": "..."}'},
                    )
                    return
                self._run_on_host_thread(lambda: face.teach_me(target_id))
                return
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str) or not text.strip():
                self._send_json(
                    400, {"error": 'need a JSON body {"text": "..."}'}
                )
                return
            self._run_on_host_thread(lambda: face.turn(text))

    return _WebServer(("127.0.0.1", port), Handler, face=face, work=work)


def run_web(
    host: Host,
    port: int,
    *,
    conversation: str = DEFAULT_WEB_CONVERSATION_ID,
    ready: threading.Event | None = None,
    stop: threading.Event | None = None,
) -> None:
    """Serve the page until ``stop`` is set — blocking, on the host's thread.

    Call this on the same thread that opened ``host``: the work loop below is
    the thread every host-touching route runs on (the module docstring's
    one-thread rule). ``ready`` is set once the server is bound and the
    accept loop is live (the test seam); ``stop`` ends the serve within one
    poll interval and closes the socket. The bind is hardwired to
    ``127.0.0.1`` — no argument can widen it.

    The conversation is opened here, before the server binds — the live
    first-request form (``python -m elc web`` against a fresh app.db) has no
    other opener: the tests that pre-open theirs keep working because the
    open is idempotent per conversation, and an open that refuses raises
    :class:`WebOpenError` for the CLI branch to answer with its human
    sentence (the ``chat`` open-failure shape, not a 500-per-request loop).

    After the open and before the bind, the host's startup recovery runs
    once — the same sweep the ``chat`` command runs at its startup. A web
    restart is exactly the shape the sweep exists for: the dead process's
    ``AWAITING_USER`` moment keeps holding the conversation's one-focus
    teaching lock, and without the sweep nothing in the web face ever
    releases it (the second dogfood deadlock arm). An ``Err`` — a refusal
    to scan at all — is said out loud on ``sys.stderr`` (this function has
    no stderr parameter of its own; the process's stderr is the honest
    place) and the serving continues: the recovery lines are
    failure-tolerant by contract, so an unavailable sweep blocks the page
    no more than it blocks chat.
    """

    opened = host.open_conversation(ConversationId(conversation))
    if isinstance(opened, Err):
        raise WebOpenError(
            f"cannot open conversation {conversation}:"
            f" {opened.error.code.value}: {opened.error.message}"
        )

    recovery = host.startup_recovery()
    if isinstance(recovery, Err):
        # The recovery lines are failure-tolerant by contract, but a refusal
        # to scan at all is said out loud; the serving goes on (the chat
        # startup's exact shape).
        print(
            "elc web: startup recovery unavailable:"
            f" {recovery.error.code.value}: {recovery.error.message}",
            file=sys.stderr,
        )

    server = _build_server(host, port, conversation=conversation)
    serve_thread = threading.Thread(target=server.serve_forever, daemon=True)
    serve_thread.start()
    if ready is not None:
        ready.set()
    try:
        while stop is None or not stop.is_set():
            try:
                job = server.work.get(timeout=0.2)
            except queue.Empty:
                continue
            job()
    finally:
        server.shutdown()
        server.server_close()


def main(
    argv: Sequence[str] | None = None,
    *,
    provider: PersonaProvider | None = None,
    stderr: TextIO | None = None,
) -> int:
    """The web command's entry: the CLI's ``web`` command, verbatim.

    Delegation, not duplication: ``elc.cli.main`` owns the argument grammar,
    the validation, the provider construction and the host assembly, and its
    ``web`` branch is the only caller of :func:`run_web`. This wrapper exists
    so the composition has a name in the module that serves it — it forwards
    ``["web", *argv]`` and answers the same exit codes (including the human
    exit 2 for a missing ``--base-url``).
    """

    forwarded = ["web", *(list(argv) if argv is not None else [])]
    return cli_main(forwarded, provider=provider, stderr=stderr)
