"""The W-1 local web face — one study-first dogfood page over one host.

``python -m elc web --app-db … --base-url … --model … [--content-db …]
[--rollout-stage …] [--port 8760]`` serves the same assembly the ``chat``
command builds (the argument validation, the provider construction and the
host opening are ``elc.cli.main``'s — this module never re-implements them;
the CLI's ``web`` branch is the only caller and ``main`` here is the thin
delegating entry for it). The page's shell is static HTML/CSS/JS under
``elc/webui/`` next to this module (F-G1 split the once-embedded page
string into seven files this module serves): a conversation area that
POSTs one turn at a time, a teaching-moment card for the moments the turn
opened, an observations button that pulls the durable readout, and a
history load on page open. The UI text is Chinese; the conversation
itself is the user's English.

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
handler threads parse HTTP, serialize JSON, read one static ``webui/`` file
and nothing else. This is also the single-user serial assumption, made
structural rather than hoped for: concurrent requests queue, and the host
never interleaves two turns.

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

**The static face (F-G1).** The shell (``index.html``) and its six assets
(three CSS sheets — ``tokens.css`` / ``components.css`` / ``screens.css`` —
and three ES modules — ``api.js`` / ``components.js`` / ``app.js``) live in
``webui/`` next to this module and are served **per request** from an
allowlist (:data:`_STATIC_TYPES`): the allowlist *is* the path check, so a
name outside it never touches the filesystem, and a file that cannot be
read answers 404 with one human sentence — never a bare traceback, never a
fabricated page. Zero external resources stays the law (no CDN, no web
font, no framework — the page still runs over ``dependencies = []``, the
assets served from the repo itself); the component library and its single
sources are governed by ``docs/FRONTEND_SPEC.md``.

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
token sheet (``--bg #fbf9f4`` / three ink levels / two hairline rules /
the ochre pencil / the touch wash / the serif-sans-mono font stacks)
lives in ``webui/tokens.css`` as the tokens' only source, and the form
laws are absolute — zero cards, zero chat bubbles, zero tab bar, zero
radius, zero shadow: layers are hairlines, whitespace and the ink
levels, and every action is an underlined pencil text link. The shell is
three screens switched by plain JS ``show``/``hide`` (no router): **开张**
(a first-visit cover, remembered in localStorage — an honest "this is what
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

**p-1 adds the word-card face and the 今日 screen.** ``GET
/api/word?q=<text>`` is one read-only lookup over content.db's word list
(the §24.2/§24.3 rows the build wrote): the query's tokens must contain a
lemma's tokens as a whole-word run — case-insensitive, edge punctuation
stripped — and the **longest** hit wins ("a bit of luck" answers "a bit",
and "make senses" matches nothing, the whole-word alignment keeping a bare
substring accident out); a miss answers ``{"found": false}``, a 200 fact,
never a 404. The page's letters fragment their text into clickable words
and open a #15 word-card on the answer; the 今日 screen (a fourth page
behind the parlor's brand bar) re-serves the learning readout's due rows
with an inline 教我这个, the recent-evidence targets and the teachable
list — no invented daily activity, the screen reuses three existing
read-only faces and adds nothing writable.

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
from urllib.parse import parse_qs, urlsplit

from elc.cli import (
    RUNTIME_VERSION,
    ObservationSection,
    observation_drift_count,
    observation_sections,
)
from elc.cli import main as cli_main
from elc.content.store import open_read_only
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


# ---------------------------------------------------------------------------
# the static face — the webui/ directory next to this module (F-G1)
# ---------------------------------------------------------------------------

#: The shell's home: F-G1 split the once-embedded page string into seven
#: files (the HTML shell, three CSS sheets, three ES modules) read from
#: here. Read **per request**, not cached at import: the files are tens of
#: kilobytes on a loopback-only single-user server, a per-request read
#: keeps the served bytes equal to the repo's (an edited sheet shows on
#: the next reload with no restart), and it keeps the failure posture per
#: request (below) instead of a startup snapshot that can go stale.
_WEBUI_ROOT = Path(__file__).with_name("webui")

#: The whole static route table, file name → Content-Type. The allowlist
#: *is* the path check: a request for anything else (``..``, a
#: subdirectory, a name that merely looks like a file) has no entry here
#: and answers 404 without the filesystem ever being touched.
_STATIC_TYPES: dict[str, str] = {
    "index.html": "text/html; charset=utf-8",
    "tokens.css": "text/css; charset=utf-8",
    "components.css": "text/css; charset=utf-8",
    "screens.css": "text/css; charset=utf-8",
    "api.js": "text/javascript; charset=utf-8",
    "components.js": "text/javascript; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}


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


# ---------------------------------------------------------------------------
# the p-1 word-card lookup — one read-only face over content.db's word list
# ---------------------------------------------------------------------------


#: Characters stripped from both ends of every whitespace-separated token
#: before two sides compare (the page strips its clicked windows with the
#: same set, so "Anyway," matches the lemma "anyway"). Punctuation *inside*
#: a token stays: "I'm" is one token, the way the lemma "I'm not sure"
#: spells it.
_WORD_EDGE_CHARS = "\"'`.,;:!?()[]{}<>…—–-“”‘’《》「」*_/\\|=+~^%$#@&"

#: The en-side reading order inside one sense: the definition role is the
#: card's canonical gloss, the other roles follow alphabetically — a
#: deterministic tie-break for the ordinal ties the corpus actually has
#: (every role lands on ordinal 0), not a semantic claim about the others.
_WORD_TEXT_ORDER = (
    "ORDER BY ordinal, CASE role WHEN 'definition' THEN 0 ELSE 1 END, role"
)

#: The content_text roles that pass through under their own role word —
#: surveyed, not guessed (the p-1 survey: the corpus carries definition /
#: usage / teaching_note / disambiguation in en and translation in zh;
#: gloss is in the build's vocabulary but in no row). The card maps the
#: zh-language text to ``zh`` and the en-language one to ``en``; these ride
#: the response verbatim beside them, for a later face to render.
_WORD_PASSTHROUGH_ROLES = ("gloss", "usage", "teaching_note", "disambiguation")

#: How many example sentences a card serves (the task's own bound).
_WORD_EXAMPLE_LIMIT = 2


def _word_tokens(text: str) -> list[str]:
    """A query or a lemma as lowercased, edge-stripped word tokens."""

    tokens: list[str] = []
    for raw in str(text).split():
        token = raw.strip(_WORD_EDGE_CHARS).casefold()
        if token:
            tokens.append(token)
    return tokens


def _contains_run(sequence: list[str], sub: list[str]) -> bool:
    """Whether ``sub`` sits in ``sequence`` as a contiguous whole-word run
    (the alignment that keeps "make senses" from matching "make sense" —
    a bare substring test would)."""

    if not sub:
        return False
    return any(
        sequence[i : i + len(sub)] == sub
        for i in range(len(sequence) - len(sub) + 1)
    )


def _word_lookup(conn: sqlite3.Connection, q: str) -> dict[str, Any]:
    """One word-card answer, read-only SELECTs over the built content.db.

    The match is whole-word aligned containment: the query's token run
    must contain a lemma's token run contiguously, and the **longest**
    hit wins (a same-length tie goes to the smaller entity id, so the
    answer never depends on row order). Nothing here ranks by frequency
    or guesses a role: senses are the corpus's own rows (``zh`` = the
    sense's first zh-language text, ``en`` = the first en one — the
    definition role ordered first by :data:`_WORD_TEXT_ORDER`), the
    remaining roles ride the response under their own role word
    (:data:`_WORD_PASSTHROUGH_ROLES`), and examples are the entity's own
    ``content_example`` rows, primary-target first — they carry no
    ``sense_id``, so the same ≤2 list rides every sense of the entity
    (today one sense per entity).
    """

    q_tokens = _word_tokens(q)
    if not q_tokens:
        return {"found": False}
    hits: list[tuple[int, str, str, str]] = []
    for entity_id, lemma, pos in conn.execute(
        "SELECT entity_id, lemma, pos FROM content_lexical_entry"
    ):
        lemma_tokens = _word_tokens(str(lemma))
        if _contains_run(q_tokens, lemma_tokens):
            hits.append(
                (len(lemma_tokens), str(entity_id), str(lemma), str(pos))
            )
    if not hits:
        return {"found": False}
    hits.sort(key=lambda hit: (-hit[0], hit[1]))
    _, entity_id, lemma, pos = hits[0]
    examples = [
        str(row[0])
        for row in conn.execute(
            "SELECT form FROM content_example WHERE entity_id = ?"
            " ORDER BY CASE role WHEN 'PRIMARY_TARGET' THEN 0 ELSE 1 END,"
            " ordinal LIMIT ?",
            (entity_id, _WORD_EXAMPLE_LIMIT),
        )
    ]
    forms = [
        {"written": str(row[0]), "form_type": str(row[1])}
        for row in conn.execute(
            "SELECT written, form_type FROM content_form"
            " WHERE entity_id = ? ORDER BY form_id",
            (entity_id,),
        )
    ]
    senses: list[dict[str, Any]] = []
    for (sense_id,) in conn.execute(
        "SELECT sense_id FROM content_sense WHERE entity_id = ?"
        " ORDER BY ordinal, sense_id",
        (entity_id,),
    ):
        sense: dict[str, Any] = {"zh": None, "en": None, "examples": examples}
        for role, language, text in conn.execute(
            "SELECT role, language, text FROM content_text"
            " WHERE entity_id = ? AND sense_id = ? " + _WORD_TEXT_ORDER,
            (entity_id, str(sense_id)),
        ):
            role, language = str(role), str(language)
            if sense["zh"] is None and language == "zh":
                sense["zh"] = str(text)
            elif sense["en"] is None and language == "en":
                sense["en"] = str(text)
            elif role in _WORD_PASSTHROUGH_ROLES and role not in sense:
                sense[role] = str(text)
        senses.append(sense)
    return {
        "found": True,
        "lemma": lemma,
        "pos": pos,
        "forms": forms,
        "senses": senses,
        "entity_id": entity_id,
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
        # The word-card face's one parameter: the content artifact's path,
        # read off the store once (ContentStore does not publish it — the
        # lookup opens its own per-request read-only connections, the W-4
        # posture, and never touches the store's connection). getattr with
        # a default, not attribute access: a host without the full-chain
        # tier (the test doubles' shape) simply has no word list.
        self._word_db_path: Path | None = None
        content_store = getattr(host, "content_store", None)
        if content_store is not None:
            self._word_db_path = getattr(content_store, "_db_path", None)

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

    def word(self, q: str) -> dict[str, Any]:
        """One word-card lookup over the content leg's word list (p-1).

        The diagnostics face's construction with the W-4 connection
        posture: the lookup runs on the work queue (a person's click is
        never mid-generation), over this face's own short **read-only**
        connection (``mode=ro`` enforced by SQLite, opened per request
        and closed before answering — ContentStore's connection stays
        private to the store; only its artifact path is read, once, in
        ``__init__``). Without a content leg there is no word list and
        every lookup honestly misses (``{"found": false}`` — the card
        never opens, and nothing pretends otherwise). The SQL is fully
        parameterized; the lookup writes nothing, ever.
        """

        if self._word_db_path is None:
            return {"found": False}
        conn = open_read_only(self._word_db_path)
        try:
            return _word_lookup(conn, q)
        finally:
            conn.close()

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
        touches nothing but HTTP parsing, JSON, the queue and the per-request
        read of one allowlisted ``webui/`` file.
        """

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_page_file(self, name: str) -> None:
            """Serve one ``webui/`` file, read per request (F-G1).

            The name comes straight off the :data:`_STATIC_TYPES` allowlist
            (the caller checked), so the path join cannot escape the
            directory. Fail-closed: a file that cannot be read (missing,
            unreadable) answers 404 with one human sentence — never a bare
            traceback, never a half page; the browser shows the line
            instead of a broken shell.
            """

            try:
                body = (_WEBUI_ROOT / name).read_bytes()
            except OSError:
                self._send_json(
                    404,
                    {
                        "error": (
                            f"the page file {name} is missing or unreadable"
                            " — the webui/ directory next to elc/web.py is"
                            " part of the installation"
                        )
                    },
                )
                return
            self.send_response(200)
            self.send_header("Content-Type", _STATIC_TYPES[name])
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
                self._send_page_file("index.html")
            elif self.path.startswith("/static/"):
                # The static face: the allowlist is the path check — a name
                # outside it (``..``, a subdirectory, a lookalike) answers
                # 404 without touching the filesystem (fail-closed).
                name = self.path[len("/static/"):]
                if name in _STATIC_TYPES:
                    self._send_page_file(name)
                else:
                    self._send_json(404, {"error": "no such page file"})
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
            elif self.path == "/api/word" or self.path.startswith("/api/word?"):
                # The p-1 word-card lookup — read-only SQL over content.db
                # on the work queue (the diagnostics face's construction).
                # Grammar: one query parameter ?q=<text>; a request without
                # it is a bad request, and a lookup that misses — or a q
                # that strips to nothing — answers {"found": false}, a 200
                # fact, never a 404.
                q_values = parse_qs(urlsplit(self.path).query).get("q")
                if not q_values:
                    self._send_json(400, {"error": "need ?q=<text>"})
                else:
                    looked_up = q_values[0]
                    self._run_on_host_thread(lambda: face.word(looked_up))
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
