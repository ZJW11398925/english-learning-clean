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

**p-2 adds the memory readout and the delete face.** ``GET /api/memory``
is the diagnostics construction once more (read-only SQL on the work
queue, panel-level guards, honest empty shapes): five panels over what
the parlor *remembers* — relationship memories, episode summaries, the
learner_target_state rows (row-level: each row's target, watermark and
the state document's key set, never a guessed reading of the keys), the
evidence counts with the last five claims, and the §24 deletion ledger
through the host's own deletion controller (删除也要透明: a tombstone is
the opaque digest §24 pins, never the deleted body). ``POST /api/delete``
is the page's one destructive act: the grammar accepts exactly the three
scopes with behaviour legs (``CONVERSATION`` / ``LEARNING_TARGET`` /
``RELATIONSHIP_PAIR``, each with its own key — every other scope word,
including the deletion vocabulary's other four, answers a 400 人话), the
request goes through the controller's own ``execute`` (an ``Err`` is a
runtime fact: 200 + ``accepted: false`` + the controller's code and
sentence, passed through verbatim), and a ``CONVERSATION`` body without a
``conversation_id`` names the conversation this face serves — the page
never learns its own id, so the face supplies the honest referent.

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

**p-3 adds the goal-management face** — the first screen where the page
*writes* user configuration. ``GET /api/goals`` answers the whole read in
one payload: the portfolio's eight columns (§5.1 verbatim), the policy's
version + frequency + its eight unpinned columns passed through raw
(``None`` = 未配置 — the store's own honesty, carried as JSON null), the
session focus of the conversation this face serves as a note when one
exists (临时侧重，不改长期目标 — the §5.1 semantics; ``None`` stays
``None``, never fabricated), and the §4 taxonomy reference block whose
three non-stored faces are labelled "canonical 词表参考 · V1 无存储位" and
are never editable. The two writes surface the store's own version
discipline: ``POST /api/goals`` upserts the full new combination as the
next version (an unchanged replay answers idempotent and writes nothing; a
same-version-different-content CONFLICT — another writer won the race —
rides HTTP 409 with one human sentence), and ``POST
/api/teaching_frequency`` rewrites the one policy column, rebuilding the
other columns verbatim. Out-of-vocabulary words are 400 人话 refusals
(fail-closed, never a silent drop), the write faces' version scheme is
:func:`_next_version` (declared there), and a host without the user-config
leg answers the honest refusal shape instead of pretending to save.
"""

from __future__ import annotations

import json
import math
import queue
import socket
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
from elc.conversation.store import (
    TEACHING_REQUEST_PAYLOAD_MARKER,
    TEACHING_RESPONSE_PAYLOAD_MARKER,
)
from elc.conversation.types import CommitUserTurn
from elc.curriculum.readiness import READINESS_LEVELS
from elc.deletion.controller import DeletionController
from elc.deletion.types import DeletionRequest, DeletionScope
from elc.host import Host
from elc.persona.card_store import (
    CharacterCardRecord,
    SqliteCharacterCardStore,
    persona_id_for_card,
    stamp_key_for,
)
from elc.persona.penpal import (
    PENPAL_CHARACTER_PACKAGE,
    PENPAL_CHARACTER_PACKAGE_ID,
    PENPAL_PERSONA_ID,
)
from elc.persona.provider import PersonaProvider
from elc.planner.trace_document import decode_factor_trace
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    DomainErrorCode,
    Err,
    GoalId,
    GoalModality,
    GoalVersion,
    InputId,
    InteractionChannel,
    PersonaId,
    PolicyVersion,
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
from elc.user_config.types import (
    LearningGoal,
    LearningGoalPortfolio,
    SessionFocus,
    TeachingFrequency,
    TeachingPolicyProfile,
)

__all__ = [
    "DEFAULT_WEB_CONVERSATION_ID",
    "WebOpenError",
    "main",
    "port_is_serving",
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
    "AWAITING_USER": "等你回应",
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
# the p-2 memory panels — what the parlor remembers, one read-only face
# ---------------------------------------------------------------------------

#: How many recent evidence claims the memory view's evidence panel serves
#: (the learning view's width, same number, own name).
_MEMORY_EVIDENCE_ROWS = 5

#: cs-1: the semantic partition of the memory readout's five panels — which
#: side of the character/learning/audit line each panel answers. The field
#: is additive and purely declarative today (the page does not read it yet;
#: cs-2 wires the character face), but the partition is the server's to
#: name, so it is declared here once and stamped on every panel — including
#: a panel that answered with its error shape, whose partition is just as
#: much a fact about it.
_MEMORY_PANEL_DOMAINS: dict[str, str] = {
    "relationship_memory": "character",
    "episode": "character",
    "learner_states": "learning",
    "evidence": "learning",
    "tombstones": "audit",
}

#: The three scopes the delete face accepts — the ones with behaviour legs
#: on this assembly — each mapped to its own request key. The deletion
#: vocabulary's other four words are the store's, not this face's: they
#: answer the route's 400 人话, never a silent widening.
_DELETE_SCOPE_KEYS: dict[DeletionScope, str] = {
    DeletionScope.CONVERSATION: "conversation_id",
    DeletionScope.LEARNING_TARGET: "target_id",
    DeletionScope.RELATIONSHIP_PAIR: "persona_id",
}


def _json_array_column(raw: object) -> list[str] | str:
    """One JSON-array column, decoded when it parses as one (the goals
    panel's convention); anything else passes through as the raw string —
    a memory panel reports what the row says, never a cleaner shape it
    invented for it."""

    try:
        loaded = json.loads(str(raw))
    except (TypeError, ValueError):
        return str(raw)
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    return str(raw)


def _relationship_memory_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """关系记忆 — every relationship_memory row, canonical text in full (v1
    serves the whole row; truncation is the page's display choice, never a
    data decision made server-side)."""

    rows = db.execute(
        "SELECT relationship_memory_id, memory_type, provenance, status,"
        " canonical_content, sensitivity_class, persistence_authorization,"
        " confidence, persona_id, user_id, created_at, updated_at"
        " FROM relationship_memory ORDER BY relationship_memory_id"
    ).fetchall()
    return {
        "memories": [
            {
                "relationship_memory_id": str(row[0]),
                "memory_type": str(row[1]),
                "provenance": str(row[2]),
                "status": str(row[3]),
                "canonical_content": str(row[4]),
                "sensitivity_class": str(row[5]),
                "persistence_authorization": str(row[6]),
                "confidence": None if row[7] is None else float(row[7]),
                "persona_id": str(row[8]),
                "user_id": str(row[9]),
                "created_at": str(row[10]),
                "updated_at": str(row[11]),
            }
            for row in rows
        ]
    }


def _episode_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """剧情记忆 — every episode row: the summary plus the two JSON-array
    columns decoded (:func:`_json_array_column`), status and version."""

    rows = db.execute(
        "SELECT episode_id, conversation_id, version, summary, open_threads,"
        " recent_events, status, updated_at FROM episode"
        " ORDER BY episode_id"
    ).fetchall()
    return {
        "episodes": [
            {
                "episode_id": str(row[0]),
                "conversation_id": str(row[1]),
                "version": str(row[2]),
                "summary": str(row[3]),
                "open_threads": _json_array_column(row[4]),
                "recent_events": _json_array_column(row[5]),
                "status": str(row[6]),
                "updated_at": str(row[7]),
            }
            for row in rows
        ]
    }


def _learner_state_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """学习者状态 — row-level (the p-1 I-4 closure): every
    learner_target_state row with its target key, the durable evidence
    watermark and the state document's *key set*. The keys are names, not
    readings — what a key means is the estimator's vocabulary and this
    panel does not guess at it."""

    rows = db.execute(
        "SELECT target_id, target_type, evidence_modality, estimator_version,"
        " evidence_watermark, state_json, updated_at"
        " FROM learner_target_state"
        " ORDER BY target_id, target_type, evidence_modality"
    ).fetchall()
    states: list[dict[str, Any]] = []
    for row in rows:
        try:
            document = json.loads(str(row[5]))
        except (TypeError, ValueError):
            document = None
        states.append(
            {
                "target_id": str(row[0]),
                "target_type": str(row[1]),
                "evidence_modality": str(row[2]),
                "estimator_version": str(row[3]),
                "evidence_watermark": int(row[4]),
                "state_keys": (
                    sorted(str(key) for key in document)
                    if isinstance(document, dict)
                    else None
                ),
                "updated_at": str(row[6]),
            }
        )
    return {"states": states}


def _memory_evidence_panel(db: sqlite3.Connection) -> dict[str, Any]:
    """证据 — the two counts plus the last five claims (numbers, not
    readings; the learning panel's own shape on its own endpoint)."""

    rows = db.execute(
        "SELECT target_id, polarity, outcome, performance_type, created_at"
        " FROM evidence_claim"
        " ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (_MEMORY_EVIDENCE_ROWS,),
    ).fetchall()
    claims = db.execute("SELECT COUNT(*) FROM evidence_claim").fetchone()
    commits = db.execute(
        "SELECT COUNT(*) FROM evidence_commit"
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
        "evidence_commit_count": int(commits[0]) if commits else 0,
    }


def _tombstones_of(controller: DeletionController) -> dict[str, Any]:
    """删除台账 — the §24 ledger through the controller's own read face.
    A tombstone carries the opaque digest §24 pins (``entity_hash``), never
    the deleted body — transparency about *what kind of thing* went and
    when, which is all the ledger honestly holds."""

    read = controller.list_tombstones()
    if isinstance(read, Err):
        raise RuntimeError(
            "the tombstone ledger could not be read:"
            f" {read.error.code.value}: {read.error.message}"
        )
    return {
        "tombstones": [
            {
                "tombstone_id": record.tombstone_id,
                "entity_kind": record.entity_kind,
                "entity_hash": record.entity_hash,
                "deleted_at": record.deleted_at,
                "deletion_scope": record.deletion_scope.value,
                "scope_version": record.scope_version,
            }
            for record in read.value
        ]
    }


# ---------------------------------------------------------------------------
# the cs-2 partner dossier — one read-only face over the penpal's true source
# ---------------------------------------------------------------------------


def _partner_card_face() -> dict[str, Any]:
    """The character card's narrative face, shaped for the page.

    The single-source rule (cs-1, pinned) makes this a derivation, never a
    second spelling: the name is the identity line's first segment (the
    text before the card's own em dash) and the identity line is the rest
    — both read out of :data:`PENPAL_CHARACTER_PACKAGE` at call time. The
    three prose fields pass through whole (the page renders them as the
    dossier's paragraphs, it does not re-shape the words). Nothing here
    hardcodes a value of the character: a changed card changes this face.
    """

    card = PENPAL_CHARACTER_PACKAGE
    identity = str(card.identity)
    head, sep, tail = identity.partition(" — ")
    return {
        "name": head if sep else identity,
        "identity_line": tail if sep else "",
        "background": str(card.background),
        "values": str(card.values),
        "letter_habits": str(card.speech_style),
    }


#: The canonical command-turn discriminator (the conversation store's own
#: window filter, cs-2R MEDIUM-1: the same two payload markers, bound the
#: same way). A teaching request or reply commits a ``user_turn`` whose
#: ``raw_content`` is empty and whose envelope payload carries the typed
#: marker — a command, not something the user said — and the dossier
#: counts letters, so both stats queries exclude those rows with the same
#: two clauses (P3-1A/P3-1B's rule, reused rather than re-derived).
_LETTER_FILTER_SQL = (
    " FROM user_turn u"
    " JOIN input_envelope e ON e.input_id = u.input_id"
    " WHERE u.conversation_id = ?"
    "  AND NOT (u.raw_content = '' AND e.raw_payload LIKE ?)"
    "  AND NOT (u.raw_content = '' AND e.raw_payload LIKE ?)"
)


def _partner_stats_panel(db: sqlite3.Connection, conversation: str) -> dict[str, Any]:
    """The correspondence statistics, from the conversation's own letters.

    Three counts the dossier head names: how many letters went out (the
    committed ``user_turn`` rows minus the command turns — a teaching
    request or reply rides an empty ``raw_content`` with a typed envelope
    payload and is excluded by :data:`_LETTER_FILTER_SQL`, the store's own
    window discriminator), the first letter's day and the latest one (the
    rows' own ``created_at`` min/max, passed through as the ISO strings
    they are). The per-day timeline rides along (the most recent 60 days
    that carried letters — the LIMIT applies *after* the GROUP BY day, so
    it trims quiet days, never lettered ones — oldest first): one row per
    day that saw a letter, the day and the count — the dossier's 极简
    时间线 renders these, it does not re-derive them.
    """

    row = db.execute(
        "SELECT COUNT(*), MIN(u.created_at), MAX(u.created_at)"
        + _LETTER_FILTER_SQL,
        (
            conversation,
            f"%{TEACHING_REQUEST_PAYLOAD_MARKER}%",
            f"%{TEACHING_RESPONSE_PAYLOAD_MARKER}%",
        ),
    ).fetchone()
    days = [
        (str(day), int(count))
        for day, count in db.execute(
            "SELECT substr(u.created_at, 1, 10) AS day, COUNT(*)"
            + _LETTER_FILTER_SQL
            + " GROUP BY day ORDER BY day DESC LIMIT 60",
            (
                conversation,
                f"%{TEACHING_REQUEST_PAYLOAD_MARKER}%",
                f"%{TEACHING_RESPONSE_PAYLOAD_MARKER}%",
            ),
        ).fetchall()
    ]
    days.reverse()
    return {
        "turns": int(row[0]) if row else 0,
        "first_letter_at": None if row is None or row[1] is None else str(row[1]),
        "latest_letter_at": None if row is None or row[2] is None else str(row[2]),
        "timeline": [{"date": day, "turns": count} for day, count in days],
    }


def _partner_memories_panel(
    db: sqlite3.Connection, persona_id: str = str(PENPAL_PERSONA_ID)
) -> dict[str, Any]:
    """What a character remembers about you — the ACTIVE relationship rows.

    Scoped by the character's persona id (the parameter; the default is the
    penpal's imported constant, so every caller before MC-0 reads exactly
    what it always read), newest first (``updated_at`` desc, the row id
    breaking a same-stamp tie). Local V1 is single-user, so the persona key
    names the whole pair today — a second user side would need the
    ``user_id`` leg added here, and this sentence would be the place (cs-2R
    LOW-2: the pair wording is narrowed to what the SQL actually reads).
    Only ``ACTIVE`` rows are "remembered" — a superseded or withdrawn row
    is the memory's history, not its present. The canonical text passes
    through whole; nothing here paraphrases what was remembered."""

    rows = db.execute(
        "SELECT canonical_content, memory_type, updated_at"
        " FROM relationship_memory"
        " WHERE persona_id = ? AND status = 'ACTIVE'"
        " ORDER BY updated_at DESC, relationship_memory_id",
        (persona_id,),
    ).fetchall()
    return {
        "memories": [
            {
                "content": str(row[0]),
                "memory_type": str(row[1]),
                "updated_at": str(row[2]),
            }
            for row in rows
        ]
    }


def _partner_episode_panel(
    db: sqlite3.Connection, conversation: str
) -> dict[str, Any]:
    """The latest ACTIVE episode — the dossier's 近况 face.

    The conversation's own episode row (Local V1 keeps one per
    conversation): the summary and the open threads decoded through the
    memory face's array reader. No ACTIVE episode is the honest ``None``
    — the correspondence has not been summarized yet, and the page says
    so instead of inventing a near-past."""

    row = db.execute(
        "SELECT summary, open_threads, updated_at FROM episode"
        " WHERE conversation_id = ? AND status = 'ACTIVE'"
        " ORDER BY updated_at DESC, episode_id DESC LIMIT 1",
        (conversation,),
    ).fetchone()
    if row is None:
        return {"episode": None}
    return {
        "episode": {
            "summary": str(row[0]),
            "open_threads": _json_array_column(row[1]),
            "updated_at": str(row[2]),
        }
    }


# ---------------------------------------------------------------------------
# the MC-0 characters — user-authored cards, one conversation each
# ---------------------------------------------------------------------------


def _conversation_for_character(character_id: str) -> str:
    """The one conversation a character's letters live in — the mapping rule.

    A **convention, not a table**: the penpal keeps her shipped conversation
    (:data:`DEFAULT_WEB_CONVERSATION_ID` — backward compatibility: every
    ``web-default`` letter ever written stays hers), every other character
    gets ``web-<character_id>``. The ids are unique, so the derived
    conversation ids are too, and the derivation is stable under renames —
    the letters stay in the same envelope when the character is reworded.
    """

    if character_id == str(PENPAL_CHARACTER_PACKAGE_ID):
        return DEFAULT_WEB_CONVERSATION_ID
    return f"web-{character_id}"


def _character_of_conversation(conversation_id: str) -> str | None:
    """The reverse mapping — which character a conversation id names.

    The ``None`` is honest: a conversation id that follows neither shape
    (``web-test``, the tests' own; ``cli-default``) names no character, and
    the caller answers ``current_character_id: None`` rather than guessing.
    """

    if conversation_id == DEFAULT_WEB_CONVERSATION_ID:
        return str(PENPAL_CHARACTER_PACKAGE_ID)
    if conversation_id.startswith("web-"):
        return conversation_id[len("web-") :]
    return None


def _character_summary(record: CharacterCardRecord) -> dict[str, Any]:
    """One list row — the roster face the page renders.

    ``identity_line`` is the card's own identity text, whole (the roster's
    简介行; the dossier face may reshape further). ``stamp_key`` is the
    derived stamp variant key (:func:`elc.persona.card_store.stamp_key_for`
    — the server only derives it; the stamp art is the frontend's).
    """

    return {
        "character_id": record.character_id,
        "name": record.name,
        "identity_line": record.identity,
        "is_builtin": record.is_builtin,
        "stamp_key": stamp_key_for(record.character_id),
        "persona_id": record.persona_id,
        "revision": record.revision,
        "updated_at": record.updated_at,
    }


def _character_card_face(record: CharacterCardRecord) -> dict[str, Any]:
    """The dossier card for a table-sourced character — the penpal face's
    five keys, table-fed.

    The keys match :func:`_partner_card_face` exactly so the page renders
    both shapes with one reader. The derivation differs where the sources
    differ: a user card carries its name as a column (the penpal's name is
    partitioned out of her identity line), and the identity text is the
    user's own free prose — it passes through whole, never re-split.
    """

    return {
        "name": record.name,
        "identity_line": record.identity,
        "background": record.background,
        "values": record.values,
        "letter_habits": record.speech_style,
    }


#: The create/update body's whole field vocabulary — the prose a card
#: carries, by its column name (``values`` included; it is JSON here, no
#: SQL quoting needed). A body with any other key is a bad request, never
#: a silent widening (the /api/delete grammar's rule).
_CHARACTER_CARD_FIELDS = (
    "name",
    "identity",
    "personality",
    "background",
    "speech_style",
    "values",
    "boundaries",
    "opening",
    "scenario",
)

#: The card fields' length caps (mc-1's F-2): the name rides the
#: envelope's addressee line and the stamp's initial, forty characters
#: is already a mouthful for both; every prose field answers one dossier
#: face, and two thousand characters is a whole honest card of it. A
#: longer field is a bad request — a 400 人话 naming the field, never a
#: silent truncation (the shelf stores as given or refuses).
_CHARACTER_NAME_MAX = 40
_CHARACTER_PROSE_MAX = 2000


def _character_request_parts(
    payload: Any, *, name_required: bool
) -> tuple[str | None, dict[str, str] | None]:
    """The create/update grammar: only card fields, all strings.

    ``(error, None)`` is a bad request (the 400 人话 rides the error);
    ``(None, fields)`` is the parsed body — only the keys present, so the
    update face rewords exactly what the caller sent. The name, when sent,
    must be non-empty (a card without a name is a blank stamp); at create
    time it must be sent at all.
    """

    if not isinstance(payload, dict):
        return (
            "请求体得是 JSON 对象：带 \"name\"（必填），其余卡面"
            "（identity、personality、background、speech_style、"
            "values、boundaries、opening、scenario）可带可不带",
            None,
        )
    fields: dict[str, str] = {}
    for key, value in payload.items():
        if key not in _CHARACTER_CARD_FIELDS:
            return (
                f"没有叫 {key!r} 的卡面——能写的面是："
                + "、".join(_CHARACTER_CARD_FIELDS),
                None,
            )
        if not isinstance(value, str):
            return (f"「{key}」得是一段文字", None)
        cap = (
            _CHARACTER_NAME_MAX if key == "name" else _CHARACTER_PROSE_MAX
        )
        if len(value) > cap:
            return (
                f"「{key}」太长了——最多 {cap} 字",
                None,
            )
        fields[key] = value
    if "name" in fields and not fields["name"].strip():
        return ("一张卡得有名字——名字不能是空白", None)
    if name_required and "name" not in fields:
        return ("新建一张卡得带 \"name\"——名字不能是空白", None)
    return None, fields


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


# ---------------------------------------------------------------------------
# the p-3 goal faces — the §4 vocabularies, the version scheme, the grammar
# ---------------------------------------------------------------------------


#: docs/PRODUCT_CONTRACT.md §4.3's GoalModality words, derived from the
#: platform enum — the single source the §5.1 ``goals[]`` column already
#: binds (GoalModality is a *goal* vocabulary, never an evidence modality).
_GOAL_MODALITY_WORDS: tuple[str, ...] = tuple(
    modality.value for modality in GoalModality
)

#: docs/PRODUCT_CONTRACT.md §4.5's External Assessment words, word for word
#: (no enum exists; the tuple is the citation). The score/date/skill
#: priorities §4.5 also names have **no V1 storage column** and are not
#: accepted here: the face stores what the columns hold, nothing else.
_ASSESSMENT_WORDS: tuple[str, ...] = ("CET4", "CET6", "IELTS", "TOEFL")

#: docs/PRODUCT_CONTRACT.md §4.6's Register/Style words, word for word.
_REGISTER_WORDS: tuple[str, ...] = (
    "CASUAL",
    "NEUTRAL",
    "POLITE",
    "FORMAL",
    "ACADEMIC",
    "PERSUASIVE",
    "LITERARY",
    "PLAYFUL",
)

#: docs/PRODUCT_CONTRACT.md §4.1 / §4.2 / §4.4's words, word for word — the
#: three faces canonical §4 names but **V1 has no storage column for**. They
#: are served as the taxonomy block's reference only, never editable, never
#: stored (诚实：不伪造存储位).
_CONTEXT_DOMAIN_WORDS: tuple[str, ...] = (
    "DAILY_CONVERSATION",
    "SOCIAL_RELATIONSHIP",
    "ACADEMIC",
    "WORKPLACE",
    "TRAVEL",
    "DEBATE",
    "PUBLIC_SPEAKING",
    "TECHNICAL",
    "FICTION_ROLEPLAY",
)

_GENRE_DISCOURSE_WORDS: tuple[str, ...] = (
    "CASUAL_CHAT",
    "NARRATIVE",
    "ARGUMENTATION",
    "EXPOSITION",
    "DESCRIPTION",
    "PERSUASION",
    "DAILY_WRITING",
    "ACADEMIC_WRITING",
    "CREATIVE_WRITING",
    "LITERARY_READING",
    "POETRY_READING",
    "POETRY_WRITING",
)

_EXPRESSIVE_DEPTH_WORDS: tuple[str, ...] = (
    "FOUNDATIONAL",
    "FUNCTIONAL",
    "NATURAL",
    "NUANCED",
    "ADVANCED",
)

#: The teaching-frequency picker's words — the implementation-declared
#: :class:`~elc.user_config.types.TeachingFrequency` list, not a canonical
#: one (the enum's own docstring says so; migration 0011 puts no CHECK on
#: the column for the same reason).
_FREQUENCY_WORDS: tuple[str, ...] = tuple(
    frequency.value for frequency in TeachingFrequency
)

#: The taxonomy reference block the GET serves once per read: the six §4
#: faces with their storage truth (``stored: true`` = the editor's own
#: picker words; ``stored: false`` = canonical reference, V1 无存储位) plus
#: the frequency picker's implementation-declared words. Built once — the
#: block is a constant, not a read.
_TAXONOMY_REFERENCE: dict[str, Any] = {
    "faces": [
        {
            "name": "goal_modality",
            "section": "4.3",
            "stored": True,
            "words": list(_GOAL_MODALITY_WORDS),
        },
        {
            "name": "external_assessment",
            "section": "4.5",
            "stored": True,
            "words": list(_ASSESSMENT_WORDS),
        },
        {
            "name": "register_style",
            "section": "4.6",
            "stored": True,
            "words": list(_REGISTER_WORDS),
        },
        {
            "name": "context_domain",
            "section": "4.1",
            "stored": False,
            "words": list(_CONTEXT_DOMAIN_WORDS),
        },
        {
            "name": "genre_discourse",
            "section": "4.2",
            "stored": False,
            "words": list(_GENRE_DISCOURSE_WORDS),
        },
        {
            "name": "expressive_depth",
            "section": "4.4",
            "stored": False,
            "words": list(_EXPRESSIVE_DEPTH_WORDS),
        },
    ],
    "teaching_frequency": {
        "words": list(_FREQUENCY_WORDS),
        "note": (
            "implementation-declared (elc.user_config.types."
            "TeachingFrequency), not canonical"
        ),
    },
    "non_stored_note": "canonical 词表参考 · V1 无存储位",
}

#: The frequency write's 400 sentence — one grammar line, the picker's own
#: words spelled out.
_FREQUENCY_GRAMMAR = (
    'need a JSON body {"teaching_frequency":'
    f" {' | '.join(_FREQUENCY_WORDS)}"
)


def _next_version(current: str | None) -> str:
    """The two write faces' next version string, from the current one.

    The store's version discipline is value-based (elc.user_config.store:
    the same version with different content is a ``CONFLICT``, any different
    version replaces), so a successor only has to differ from the current
    value — this scheme also keeps it monotonic and readable where it can:
    an integer current bumps by one, and any non-integer current yields
    ``"1"``. The scheme is this face's own, disclosed rather than canonical
    (versions are opaque strings to the store): the seed writers use the
    non-integer ``gv-seed-v1`` / ``pv-seed-v1`` strings, so the first web
    write after a seed lands on ``"1"`` and the endpoint keeps bumping
    integers from there; a first write at all also starts at ``"1"``.
    """

    if current is not None and current.isdigit():
        return str(int(current) + 1)
    return "1"


def _no_user_config_answer() -> dict[str, Any]:
    """The honest refusal both write faces share when this host carries no
    user-config leg (the prep-1 tier): the delete face's shape — 200,
    ``accepted: false``, the dependency's own code and one human sentence.
    Nothing is written, nothing is pretended."""

    return {
        "accepted": False,
        "conflict": False,
        "code": "DEPENDENCY_UNAVAILABLE",
        "error": "本进程未装配用户配置面（无 content-tier），目标与教学频率不可写",
    }


def _goal_request_parts(
    payload: Any,
) -> tuple[
    str | None, list[dict[str, Any]], dict[str, Any], list[str], list[str]
]:
    """The W1 body, parsed and fail-closed.

    Returns ``(error, goals, weights, assessment, register)``: a non-empty
    ``error`` is the 400 人话 sentence (the other four are meaningless
    then); a ``None`` error means the four pieces are in grammar — each
    goal's ``goal_id`` / ``description`` a non-empty string, ``goal_modality``
    inside §4.3, every weight key inside §4.3 and its value a number, every
    assessment word inside §4.5, every register word inside §4.6. An
    out-of-vocabulary word is refused, never silently dropped (fail-closed
    over 发明); the body must carry all four pieces (the full new
    combination) — a missing one is a 400, never an assumed empty.
    """

    def _reject(
        message: str,
    ) -> tuple[
        str | None, list[dict[str, Any]], dict[str, Any], list[str], list[str]
    ]:
        return (message, [], {}, [], [])

    if not isinstance(payload, dict):
        return _reject(
            'need a JSON body {"goals": [...], "modality_weights": {...},'
            ' "assessment_targets": [...], "register_style_goals": [...]}'
        )
    for key in (
        "goals",
        "modality_weights",
        "assessment_targets",
        "register_style_goals",
    ):
        if key not in payload:
            return _reject(
                f'"{key}" is missing: the body is the full new combination'
                " (goals / modality_weights / assessment_targets /"
                " register_style_goals)"
            )
    raw_goals = payload["goals"]
    if not isinstance(raw_goals, list):
        return _reject('"goals" needs a list')
    goals: list[dict[str, Any]] = []
    for index, item in enumerate(raw_goals):
        if not isinstance(item, dict):
            return _reject(f"goals[{index}] needs an object")
        goal_id = item.get("goal_id")
        modality = item.get("goal_modality")
        description = item.get("description")
        if not isinstance(goal_id, str) or not goal_id.strip():
            return _reject(
                f"goals[{index}].goal_id needs a non-empty string"
            )
        if not isinstance(modality, str) or modality not in (
            _GOAL_MODALITY_WORDS
        ):
            return _reject(
                f"goals[{index}].goal_modality must be one of"
                f" {'/'.join(_GOAL_MODALITY_WORDS)}; got {modality!r}"
            )
        if not isinstance(description, str) or not description.strip():
            return _reject(
                f"goals[{index}].description needs a non-empty string"
            )
        goals.append(
            {
                "goal_id": goal_id,
                "goal_modality": modality,
                "description": description,
            }
        )
    raw_weights = payload["modality_weights"]
    if not isinstance(raw_weights, dict):
        return _reject('"modality_weights" needs an object')
    weights: dict[str, Any] = {}
    for key, value in raw_weights.items():
        if not isinstance(key, str) or key not in _GOAL_MODALITY_WORDS:
            return _reject(
                "modality_weights keys must be one of"
                f" {'/'.join(_GOAL_MODALITY_WORDS)}; got {key!r}"
            )
        # p-3 disposition (review F-2): Python's json accepts bare NaN /
        # Infinity on both ends — a weight that slipped through would ride
        # the store's own json.dumps into the durable row and poison the
        # GET payload for every JSON.parse reader — so only finite numbers.
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            return _reject(
                f"modality_weights[{key}] needs a finite number;"
                f" got {value!r}"
            )
        weights[key] = value
    lists: dict[str, list[str]] = {}
    for key, allowed in (
        ("assessment_targets", _ASSESSMENT_WORDS),
        ("register_style_goals", _REGISTER_WORDS),
    ):
        raw = payload[key]
        if not isinstance(raw, list):
            return _reject(f'"{key}" needs a list')
        for word in raw:
            if not isinstance(word, str) or word not in allowed:
                return _reject(
                    f"{key} words must be one of"
                    f" {'/'.join(allowed)}; got {word!r}"
                )
        lists[key] = raw
    return (None, goals, weights, lists["assessment_targets"], lists[
        "register_style_goals"
    ])


def _frequency_request_word(payload: Any) -> str | None:
    """The W2 body's one word, or ``None`` when it is outside the grammar
    (the picker's four words are case-sensitive — the enum's own words)."""

    if not isinstance(payload, dict):
        return None
    word = payload.get("teaching_frequency")
    if not isinstance(word, str) or word not in _FREQUENCY_WORDS:
        return None
    return word


def _portfolio_face(portfolio: LearningGoalPortfolio) -> dict[str, Any]:
    """The durable portfolio's eight columns, verbatim (§5.1's shape; the
    read re-shapes nothing — enums spell their own words, ``effective_from``
    carries the F-4 ``""`` sentinel as the value it is)."""

    return {
        "goal_version": str(portfolio.goal_version),
        "goals": [
            {
                "goal_id": str(goal.goal_id),
                "goal_modality": str(goal.goal_modality.value),
                "description": goal.description,
            }
            for goal in portfolio.goals
        ],
        "modality_weights": {
            str(key.value): float(value)
            for key, value in portfolio.modality_weights.items()
        },
        "assessment_targets": [
            str(target) for target in portfolio.assessment_targets
        ],
        "register_style_goals": [
            str(register) for register in portfolio.register_style_goals
        ],
        "effective_from": portfolio.effective_from,
        "updated_at": portfolio.updated_at,
    }


def _policy_face(policy: TeachingPolicyProfile) -> dict[str, Any]:
    """The policy's ten served columns: version + frequency + the eight
    unpinned columns verbatim — ``None`` = 未配置, carried as JSON null,
    the store's own honesty passed through (no invented default)."""

    return {
        "policy_version": str(policy.policy_version),
        "teaching_frequency": str(policy.teaching_frequency.value),
        "mode": policy.mode,
        "interruption_budget": policy.interruption_budget,
        "curriculum_initiative": policy.curriculum_initiative,
        "correction_strictness": policy.correction_strictness,
        "hint_policy": policy.hint_policy,
        "assessment_visibility": policy.assessment_visibility,
        "practice_density": policy.practice_density,
        "persona_freedom": policy.persona_freedom,
    }


def _session_focus_face(focus: SessionFocus) -> dict[str, Any]:
    """The conversation's current focus row, verbatim — the read the note
    renders (临时侧重：the §5.1 semantics live in the page's words, the
    payload only carries the durable row)."""

    return {
        "session_focus_id": focus.session_focus_id,
        "conversation_id": str(focus.conversation_id),
        "base_goal_portfolio_version": str(focus.base_goal_portfolio_version),
        "temporary_goal_weights": {
            str(key.value): float(value)
            for key, value in focus.temporary_goal_weights.items()
        },
        "manual_focus_target": (
            None
            if focus.manual_focus_target is None
            else str(focus.manual_focus_target)
        ),
        "starts_at": focus.starts_at,
        "expires_at": focus.expires_at,
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
        # MC-0: the character card store (the assembly always builds one;
        # getattr with a default for the same test-double reason as the
        # word path above — a stub host simply has no roster, and the
        # roster faces say so loudly instead of pretending).
        self._cards: SqliteCharacterCardStore | None = getattr(
            host, "character_cards", None
        )

    def _require_cards(self) -> SqliteCharacterCardStore:
        """The card store, or the loud refusal (never a silent empty)."""

        if self._cards is None:
            raise RuntimeError(
                "this host carries no character card store"
            )
        return self._cards

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
        explanation the page should show — and ``delivery_kind`` (v3-1,
        additive, present exactly when ``delivery_text`` is) is the
        delivery's own kind word (``HINT`` / ``REVEAL`` / ``EXPLANATION``
        / ``RETRY``), which routes the card's block: the reference answer
        (REVEAL) renders as its own labelled block (`.note-answer`),
        never mixed into the letter body. A control word outside the
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
            # v3-1（B3，additive，随 delivery_text 同现）: the delivery's
            # own kind word (HINT / REVEAL / EXPLANATION / RETRY / RESUME
            # — the runtime's ``TeachingReplyTurnResult.delivery_kind``;
            # RESUME = 主路径收场的 persona 收场句，落普通交付行), so the
            # page can route the block: the reference answer (REVEAL)
            # renders as its own labelled block, never mixed into the
            # letter body; a RETRY's fixed line stays a plain note line.
            # Kind truth first, fallback second (v3-1 处置刀如实化): the
            # main-path closing reveal carries delivery_kind "RESUME" (the
            # persona resume line is that delivery's own truth — SM §1
            # PERSONA_RESUME leg; routing it to REVEAL would mislabel a
            # persona sentence as "参考答案"). The closure=="REVEALED"
            # fallback below is reachable only on the replay path
            # (_replay_teaching_reply: kind=None + durable reply text),
            # where the durable text is the corpus reveal form — there the
            # REVEAL label is the honest one.
            kind = getattr(result.value, "delivery_kind", None)
            if not kind and getattr(result.value, "closure", None) == (
                "REVEALED"
            ):
                kind = "REVEAL"
            answer["delivery_kind"] = str(kind or "")
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

    def memory(self) -> dict[str, Any]:
        """p-2: the memory readout — five guarded panels, read-only SQL on
        the work queue (the diagnostics face's construction; a person pulls
        it from the 仪表 screen, never mid-generation). cs-1 stamps each
        panel with its semantic partition (:data:`_MEMORY_PANEL_DOMAINS`)
        — an additive key the page does not read yet (cs-2 will)."""

        db = self._host.db
        readout = {
            "relationship_memory": _diagnostics_panel(
                "relationship_memory", _relationship_memory_panel, db
            ),
            "episode": _diagnostics_panel("episode", _episode_panel, db),
            "learner_states": _diagnostics_panel(
                "learner_states", _learner_state_panel, db
            ),
            "evidence": _diagnostics_panel(
                "memory_evidence", _memory_evidence_panel, db
            ),
            "tombstones": _diagnostics_panel(
                "tombstones",
                lambda _db: self._tombstones(),
                db,
            ),
        }
        for name, panel in readout.items():
            panel["domain"] = _MEMORY_PANEL_DOMAINS[name]
        return readout

    def _tombstones(self) -> dict[str, Any]:
        """The tombstone panel's read: the host's own deletion controller,
        or the honest refusal when this host carries none (``open_host``
        always wires one; the guard is the posture, not an expectation)."""

        controller = self._host.deletion
        if controller is None:
            raise RuntimeError(
                "no deletion controller is wired into this host"
            )
        return _tombstones_of(controller)

    def partner(self) -> dict[str, Any]:
        """cs-2: the penpal dossier — one read, four faces, work queue.

        The dossier page's whole read (the overlay card it replaces pulled
        three of these out of ``/api/memory``; the page now has a face of
        its own):

        - ``card`` — the character's narrative face
          (:func:`_partner_card_face`), derived from
          :data:`PENPAL_CHARACTER_PACKAGE` at call time — the single-source
          rule holds server-side too (the page never spells a value of the
          character, this face never spells a second copy);
        - ``stats`` / ``memories`` / ``episode`` — three guarded SQL reads
          (the diagnostics construction: a panel that explodes answers
          ``{"error": …}`` in its own slot, the others still answer). The
          stats read is scoped to the conversation this face serves (its
          letters — command turns excluded); the memories read to the
          penpal's persona id (Local V1's single-user pair); the episode
          read to the conversation's ACTIVE row.

        Read-only, always: nothing here writes (the memory face's
        content-snapshot posture applies verbatim)."""

        db = self._host.db
        conversation = str(self._conversation_id)
        return {
            "card": _partner_card_face(),
            "stats": _diagnostics_panel(
                "stats",
                lambda conn: _partner_stats_panel(conn, conversation),
                db,
            ),
            "memories": _diagnostics_panel(
                "memories", _partner_memories_panel, db
            ),
            "episode": _diagnostics_panel(
                "episode",
                lambda conn: _partner_episode_panel(conn, conversation),
                db,
            ),
        }

    def partner_of(self, character_id: str) -> tuple[int, Any]:
        """The dossier, parameterized (MC-0) — one character's four faces.

        ``(status, payload)`` for the write-route discipline: an unknown
        character is a 404, a known one a 200 carrying the same four keys
        as :meth:`partner` — the card from the table row, the statistics
        and the episode from **the character's own conversation** (the
        mapping rule, :func:`_conversation_for_character` — the letters
        live in its envelope whether or not this process has served it
        yet; a never-opened conversation reads honest zeros), the memories
        from the card's persona pair. ``character_id`` /
        ``conversation_id`` ride along so the page knows what it read.
        Read-only, always."""

        cards = self._require_cards()
        read = cards.get(character_id)
        if isinstance(read, Err):
            return (
                404,
                {"error": f"no such character card: {character_id}"},
            )
        record = read.value
        conversation = _conversation_for_character(character_id)
        db = self._host.db
        return (
            200,
            {
                "character_id": character_id,
                "conversation_id": conversation,
                "card": _character_card_face(record),
                "stats": _diagnostics_panel(
                    "stats",
                    lambda conn: _partner_stats_panel(conn, conversation),
                    db,
                ),
                "memories": _diagnostics_panel(
                    "memories",
                    lambda conn: _partner_memories_panel(
                        conn, record.persona_id
                    ),
                    db,
                ),
                "episode": _diagnostics_panel(
                    "episode",
                    lambda conn: _partner_episode_panel(conn, conversation),
                    db,
                ),
            },
        )

    def characters(self) -> dict[str, Any]:
        """The roster (MC-0) — every card, builtin first, plus the current.

        The current character is the reverse-mapped owner of the
        conversation this face serves, and ``None`` when the id names no
        card (the tests' ``web-test``; an honest absent, never a guess).
        Read-only, on the work queue like every face."""

        cards = self._require_cards()
        read = cards.list_all()
        if isinstance(read, Err):
            raise RuntimeError(
                "the character roster could not be read:"
                f" {read.error.code.value}: {read.error.message}"
            )
        items = [_character_summary(record) for record in read.value]
        known = {item["character_id"] for item in items}
        current = _character_of_conversation(str(self._conversation_id))
        return {
            "characters": items,
            "current_character_id": (
                current if current is not None and current in known else None
            ),
        }

    def character_create(
        self, fields: dict[str, str]
    ) -> tuple[int, Any]:
        """One new user-authored card (MC-0) — ``(status, payload)``.

        The id is server-minted (``card-`` + hex), the persona derived
        (``persona-<id>`` — one card, one persona, one isolated memory),
        the prose stored as given (**untrusted text is stored as-is** —
        the no-blacklist ruling; rendering escapes it, the store is a
        shelf). The lifecycle words come off the penpal's card (the one
        production-proven values — no second spelling), the revision
        starts at 1, the card is born ``is_builtin: False`` — a user card
        can be edited and deleted like any other user card."""

        cards = self._require_cards()
        character_id = cards.mint_user_card_id()
        now = datetime.now(tz=UTC).isoformat()
        record = CharacterCardRecord(
            character_id=character_id,
            persona_id=persona_id_for_card(character_id),
            name=fields.get("name", ""),
            identity=fields.get("identity", ""),
            personality=fields.get("personality", ""),
            background=fields.get("background", ""),
            speech_style=fields.get("speech_style", ""),
            values=fields.get("values", ""),
            boundaries=fields.get("boundaries", ""),
            opening=fields.get("opening", ""),
            scenario=fields.get("scenario", ""),
            generation_policy=PENPAL_CHARACTER_PACKAGE.generation_policy,
            lore_refs=(),
            revision=1,
            status=PENPAL_CHARACTER_PACKAGE.status,
            is_builtin=False,
            created_at=now,
            updated_at=now,
        )
        created = cards.create(record)
        if isinstance(created, Err):
            return (409, {"error": created.error.message})
        return (200, {"character": _character_summary(created.value)})

    def character_update(
        self, character_id: str, fields: dict[str, str]
    ) -> tuple[int, Any]:
        """Reword one card (MC-0) — the builtin included (editable, the
        adjudication's ruling; it is the *deletion* that is refused).

        ``NOT_FOUND`` is a 404, a shape refusal a 400, and an accepted
        update a 200 carrying the row after the rewrite (revision bumped,
        ``updated_at`` re-stamped by the store)."""

        cards = self._require_cards()
        updated = cards.update(character_id, fields)
        if isinstance(updated, Err):
            code = updated.error.code
            status = 404 if code is DomainErrorCode.NOT_FOUND else 400
            return (status, {"error": updated.error.message})
        return (200, {"character": _character_summary(updated.value)})

    def character_delete(self, character_id: str) -> tuple[int, Any]:
        """Remove one user-authored card (MC-0) — the builtin is refused.

        ``AUTHORITY_VIOLATION`` (there is exactly one Nell) rides 409, an
        unknown id 404. Deleting retires the card from the roster; the
        conversation and the memories it earned stay (history is not
        rewritten here — the deeper walk is BF-05's business, out of this
        cut's scope)."""

        cards = self._require_cards()
        deleted = cards.delete(character_id)
        if isinstance(deleted, Err):
            status = (
                404
                if deleted.error.code is DomainErrorCode.NOT_FOUND
                else 409
            )
            return (status, {"error": deleted.error.message})
        return (200, {"deleted": character_id})

    def character_switch(self, character_id: str) -> tuple[int, Any]:
        """Serve this character from now on (MC-0) — the envelope switch.

        The character's own conversation is opened **lazily here, at the
        switch** (the adjudicated timing: the opening is idempotent and
        cheap on the host thread, and the conversation is born bound to the
        card's persona — cs-1's lesson was that an unbound row makes the
        turn pipeline and the projections disagree; a first-letter build
        would leave the roster reading an unbuilt envelope). Then this
        face re-points: history, turns, the dossier and the teaching face
        all read the new conversation from their next request on. The
        handlers run on the one work-queue thread, so the re-point is
        ordered against every other face; the one off-queue reader (the
        ``/api/teaching/current`` poll) reads a plain attribute swap —
        a stale poll may answer one beat late, never a torn answer.

        An unknown character is a 404 before anything opens; a refused
        open is raised (the route's 500 posture — a runtime fact, not a
        grammar error)."""

        cards = self._require_cards()
        read = cards.get(character_id)
        if isinstance(read, Err):
            return (
                404,
                {"error": f"no such character card: {character_id}"},
            )
        record = read.value
        conversation = _conversation_for_character(character_id)
        opened = self._host.open_conversation(
            ConversationId(conversation),
            persona_id=PersonaId(record.persona_id),
        )
        if isinstance(opened, Err):
            raise RuntimeError(
                f"cannot open conversation {conversation}:"
                f" {opened.error.code.value}: {opened.error.message}"
            )
        self._conversation_id = ConversationId(conversation)
        return (
            200,
            {
                "switched": True,
                "character": _character_summary(record),
                "conversation": conversation,
            },
        )

    def delete(
        self,
        scope: DeletionScope,
        conversation_id: str | None,
        target_id: str | None,
        persona_id: str | None,
    ) -> dict[str, Any]:
        """p-2: one destructive request, through the BF-05 authority face.

        The controller owns every semantic — what the scope removes, the
        tombstones, the rebuilds — and this face only constructs the
        request and passes the answer through: an ``Ok`` is the outcome
        summary (scope, notes, the rebuild attempts with their own ok
        verdicts, the tombstone and per-table tallies), an ``Err`` is a
        runtime fact (200 + ``accepted: false`` + the controller's own
        code and sentence, verbatim — the teaching faces' refusal shape).
        Nothing here deletes a row itself, ever.
        """

        controller = self._host.deletion
        if controller is None:
            return {
                "accepted": False,
                "code": "DEPENDENCY_UNAVAILABLE",
                "message": "no deletion controller is wired into this host",
                "scope": scope.value,
            }
        request = DeletionRequest(
            scope=scope,
            conversation_id=(
                None if conversation_id is None
                else ConversationId(conversation_id)
            ),
            target_id=None if target_id is None else TargetId(target_id),
            persona_id=None if persona_id is None else PersonaId(persona_id),
        )
        result = controller.execute(request)
        if isinstance(result, Err):
            return {
                "accepted": False,
                "code": result.error.code.value,
                "message": result.error.message,
                "scope": scope.value,
            }
        outcome = result.value
        return {
            "accepted": True,
            "code": None,
            "message": None,
            "scope": outcome.scope.value,
            "notes": list(outcome.notes),
            "rebuilds": [
                {
                    "kind": attempt.kind,
                    "key": attempt.key,
                    "ok": attempt.ok,
                    "detail": attempt.detail,
                }
                for attempt in outcome.rebuilds
            ],
            "rebuilds_ok": sum(
                1 for attempt in outcome.rebuilds if attempt.ok
            ),
            "rebuilds_total": len(outcome.rebuilds),
            "tombstoned": outcome.execution.tombstoned,
            "tallies": {
                tally.table: tally.removed
                for tally in outcome.execution.tallies
            },
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

    def goals(self) -> dict[str, Any]:
        """The goal screen's one read (p-3) — portfolio + policy + the
        served conversation's session focus + the taxonomy reference.

        Read-only, on the work queue (the diagnostics construction: a person
        pulls the screen, never mid-generation). The three durable reads go
        through the host's own user-config controller; an unreadable row is
        a server fact (the route's 500 posture), an unwritten row is
        ``None`` — the honest empty shape the page greets with 写下第一个
        目标, never a fabricated portfolio. The session-focus note is keyed
        to **the conversation this face serves** (the delete face's honest
        referent rule: §5.1 keys a focus to a conversation, and this page
        knows exactly one). A host without the user-config leg (the prep-1
        tier) answers ``available: false`` — the refusal is the honest
        shape, and the taxonomy block still rides along because it is a
        constant, not a read.
        """

        controller = self._host.user_config
        if controller is None:
            return {
                "available": False,
                "portfolio": None,
                "policy": None,
                "session_focus": None,
                "taxonomy": _TAXONOMY_REFERENCE,
            }
        user_id = self._host.user_id
        assert user_id is not None  # the assembly sets the pair together
        portfolio = controller.get_goal_portfolio(user_id)
        if isinstance(portfolio, Err):
            raise RuntimeError(
                "the goal portfolio could not be read:"
                f" {portfolio.error.code.value}: {portfolio.error.message}"
            )
        policy = controller.get_teaching_policy(user_id)
        if isinstance(policy, Err):
            raise RuntimeError(
                "the teaching policy could not be read:"
                f" {policy.error.code.value}: {policy.error.message}"
            )
        focus = controller.get_session_focus_for_conversation(
            self._conversation_id
        )
        if isinstance(focus, Err):
            raise RuntimeError(
                "the session focus could not be read:"
                f" {focus.error.code.value}: {focus.error.message}"
            )
        return {
            "available": True,
            "portfolio": (
                None
                if portfolio.value is None
                else _portfolio_face(portfolio.value)
            ),
            "policy": (
                None if policy.value is None else _policy_face(policy.value)
            ),
            "session_focus": (
                None
                if focus.value is None
                else _session_focus_face(focus.value)
            ),
            "taxonomy": _TAXONOMY_REFERENCE,
        }

    def goals_save(
        self,
        goals: list[dict[str, Any]],
        weights: dict[str, Any],
        assessment: list[str],
        register: list[str],
    ) -> tuple[int, dict[str, Any]]:
        """The goal screen's one write (p-3 W1): the full new combination as
        the portfolio's next version.

        The store owns every rule (elc.user_config.store: same version +
        same content = an idempotent Ok, same version + different content =
        ``CONFLICT``, any moved version replaces); this face reads the
        current row, answers 200 with ``idempotent`` and writes nothing when
        the combination already reads back the same, and otherwise upserts
        ``GoalVersion(_next_version(current))`` with ``effective_from``
        preserved (the F-4 ``""`` sentinel on the first write — no clock
        value is invented: F-4 forbids substituting a clock for a
        declaration the user never made). The replay comparison covers the
        four content pieces in the store's own normal form (weights through
        the word-keyed float map; lists as sequences — order is content);
        ``effective_from`` is preserved by construction, so it is not
        compared. A ``CONFLICT`` rides HTTP 409 with the one human sentence;
        any other refusal is a runtime fact (200 + ``accepted: false``), the
        teaching faces' shape.
        """

        controller = self._host.user_config
        if controller is None or self._host.user_id is None:
            return (200, _no_user_config_answer())
        user_id = self._host.user_id
        current = controller.get_goal_portfolio(user_id)
        if isinstance(current, Err):
            raise RuntimeError(
                "the goal portfolio could not be read:"
                f" {current.error.code.value}: {current.error.message}"
            )
        portfolio_now = current.value
        incoming_goals = tuple(
            LearningGoal(
                goal_id=GoalId(str(goal["goal_id"])),
                goal_modality=GoalModality(str(goal["goal_modality"])),
                description=str(goal["description"]),
            )
            for goal in goals
        )
        incoming_weights = {
            GoalModality(str(key)): float(value)
            for key, value in weights.items()
        }
        incoming = (
            tuple(
                (goal.goal_id, goal.goal_modality.value, goal.description)
                for goal in incoming_goals
            ),
            {key.value: value for key, value in incoming_weights.items()},
            tuple(assessment),
            tuple(register),
        )
        if portfolio_now is not None:
            durable = (
                tuple(
                    (goal.goal_id, goal.goal_modality.value, goal.description)
                    for goal in portfolio_now.goals
                ),
                {
                    key.value: float(value)
                    for key, value in portfolio_now.modality_weights.items()
                },
                tuple(portfolio_now.assessment_targets),
                tuple(portfolio_now.register_style_goals),
            )
            if durable == incoming:
                return (
                    200,
                    {
                        "accepted": True,
                        "idempotent": True,
                        "goal_version": str(portfolio_now.goal_version),
                        "conflict": False,
                        "error": None,
                    },
                )
        version = _next_version(
            None if portfolio_now is None else str(portfolio_now.goal_version)
        )
        written = controller.upsert_goal_portfolio(
            LearningGoalPortfolio(
                goal_portfolio_id=user_id,
                goal_version=GoalVersion(version),
                goals=incoming_goals,
                modality_weights=incoming_weights,
                assessment_targets=tuple(assessment),
                register_style_goals=tuple(register),
                effective_from=(
                    ""
                    if portfolio_now is None
                    else portfolio_now.effective_from
                ),
            )
        )
        if isinstance(written, Err):
            if written.error.code is DomainErrorCode.CONFLICT:
                return (
                    409,
                    {
                        "accepted": False,
                        "conflict": True,
                        "error": "配置已被别处更新，请重读再改",
                        "detail": (
                            f"{written.error.code.value}:"
                            f" {written.error.message}"
                        ),
                    },
                )
            return (
                200,
                {
                    "accepted": False,
                    "conflict": False,
                    "error": (
                        f"{written.error.code.value}:"
                        f" {written.error.message}"
                    ),
                },
            )
        return (
            200,
            {
                "accepted": True,
                "idempotent": False,
                "goal_version": str(written.value),
                "conflict": False,
                "error": None,
            },
        )

    def teaching_frequency(self, word: str) -> tuple[int, dict[str, Any]]:
        """The goal screen's one policy write (p-3 W2): the single
        ``teaching_frequency`` column, everything else verbatim.

        The current policy's eight unpinned columns are rebuilt exactly as
        they read (zero invented values — the unpinned columns have no
        default in this slice), ``effective_from`` is preserved (the F-4
        ``""`` sentinel on the first write), and the version moves by
        :func:`_next_version`. An unchanged frequency answers 200 with
        ``idempotent`` and writes nothing (no empty version churn); a
        ``CONFLICT`` rides 409 like W1; the word itself was validated at the
        HTTP layer and is re-derived here only to fail closed (a
        :class:`~elc.user_config.types.TeachingFrequency` construction
        cannot be talked past the enum).
        """

        controller = self._host.user_config
        if controller is None or self._host.user_id is None:
            return (200, _no_user_config_answer())
        user_id = self._host.user_id
        try:
            frequency = TeachingFrequency(word)
        except ValueError:
            return (
                400,
                {
                    "accepted": False,
                    "conflict": False,
                    "error": _FREQUENCY_GRAMMAR,
                },
            )
        current = controller.get_teaching_policy(user_id)
        if isinstance(current, Err):
            raise RuntimeError(
                "the teaching policy could not be read:"
                f" {current.error.code.value}: {current.error.message}"
            )
        policy_now = current.value
        if policy_now is not None and policy_now.teaching_frequency is (
            frequency
        ):
            return (
                200,
                {
                    "accepted": True,
                    "idempotent": True,
                    "policy_version": str(policy_now.policy_version),
                    "teaching_frequency": word,
                    "conflict": False,
                    "error": None,
                },
            )
        version = _next_version(
            None if policy_now is None else str(policy_now.policy_version)
        )
        written = controller.upsert_teaching_policy(
            TeachingPolicyProfile(
                teaching_policy_profile_id=user_id,
                policy_version=PolicyVersion(version),
                teaching_frequency=frequency,
                mode=None if policy_now is None else policy_now.mode,
                interruption_budget=(
                    None
                    if policy_now is None
                    else policy_now.interruption_budget
                ),
                curriculum_initiative=(
                    None
                    if policy_now is None
                    else policy_now.curriculum_initiative
                ),
                correction_strictness=(
                    None
                    if policy_now is None
                    else policy_now.correction_strictness
                ),
                hint_policy=(
                    None if policy_now is None else policy_now.hint_policy
                ),
                assessment_visibility=(
                    None
                    if policy_now is None
                    else policy_now.assessment_visibility
                ),
                practice_density=(
                    None if policy_now is None else policy_now.practice_density
                ),
                persona_freedom=(
                    None if policy_now is None else policy_now.persona_freedom
                ),
                effective_from=(
                    "" if policy_now is None else policy_now.effective_from
                ),
            )
        )
        if isinstance(written, Err):
            if written.error.code is DomainErrorCode.CONFLICT:
                return (
                    409,
                    {
                        "accepted": False,
                        "conflict": True,
                        "error": "配置已被别处更新，请重读再改",
                        "detail": (
                            f"{written.error.code.value}:"
                            f" {written.error.message}"
                        ),
                    },
                )
            return (
                200,
                {
                    "accepted": False,
                    "conflict": False,
                    "error": (
                        f"{written.error.code.value}:"
                        f" {written.error.message}"
                    ),
                },
            )
        return (
            200,
            {
                "accepted": True,
                "idempotent": False,
                "policy_version": str(written.value),
                "teaching_frequency": word,
                "conflict": False,
                "error": None,
            },
        )

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

        The store's user-visible window read (cs-0 处置 M-1: the *user* may
        read back every delivered assistant turn, the teaching letters
        included — the composed delivery text travels whole; the
        role-visible filter that keeps those texts from the persona's
        history stays on ``get_conversation_window`` and never touches this
        face). Delivered assistant output only; teaching command turns never
        appear; oldest first.
        """

        window = self._host.conversations.get_user_visible_conversation_window(
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
            # W-7 review LOW-1: the API URLs are as unversioned as the
            # statics — a polled endpoint (teaching/current) replaying a
            # cached answer is the same stale-mix failure one layer up.
            self.send_header("Cache-Control", "no-cache")
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
            # W-7: the assets carry no versioned names, so a browser that
            # heuristically caches them can mix an old shell with a new
            # script across a delivery — no-cache makes every load
            # revalidate against the one source of truth on disk.
            self.send_header("Cache-Control", "no-cache")
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

        def _read_json_body(self) -> Any:
            """(p-3) The POST body, parsed once — the turn face's inline
            read, extracted for the two new write faces only (the existing
            branches keep their own lines untouched; the helper is theirs
            alone). A body that is not JSON answers ``None``, which every
            caller turns into its own 400."""

            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None

        def _run_host_write(
            self, route: Callable[[], tuple[int, Any]]
        ) -> None:
            """(p-3) The write faces that answer their own status — the
            queue discipline of :meth:`_run_on_host_thread` (same box, same
            failure posture, same wait) with the route's ``(status,
            payload)`` sent verbatim: the CONFLICT arm answers 409, an
            exception on the host thread is still a 500. A separate method
            on purpose: the existing route arms keep their exact lines (the
            byte-identical posture), and only the two new write faces ride
            this one."""

            box: dict[str, Any] = {}
            failure: list[str] = []
            done = threading.Event()

            def job() -> None:
                try:
                    box["answer"] = route()
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
            status, payload = box["answer"]
            self._send_json(status, payload)

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
            elif self.path == "/api/memory":
                # p-2: the memory readout — five guarded panels, read-only,
                # on the work queue (the diagnostics construction).
                self._run_on_host_thread(face.memory)
            elif self.path == "/api/partner":
                # cs-2: the penpal dossier — the card's narrative face out
                # of its single source plus three guarded SQL reads, on the
                # work queue (the diagnostics construction).
                self._run_on_host_thread(face.partner)
            elif self.path == "/api/characters":
                # MC-0: the character roster — every card, builtin first,
                # plus which one this face currently serves. Read-only on
                # the work queue (the diagnostics construction).
                self._run_on_host_thread(face.characters)
            elif self.path.startswith("/api/partner?"):
                # MC-0: the dossier, parameterized — one character's card
                # and its own conversation's statistics/memories/episode.
                # The grammar is one ?character_id=<id>; a request without
                # it is a bad request (the bare /api/partner above is the
                # no-parameter face, untouched). An unknown character is
                # the parameterized face's own 404.
                values = parse_qs(urlsplit(self.path).query).get(
                    "character_id"
                )
                if not values:
                    self._send_json(
                        400, {"error": "need ?character_id=<id>"}
                    )
                else:
                    asked = values[0]
                    self._run_host_write(lambda: face.partner_of(asked))
            elif self.path == "/api/goals":
                # p-3: the goal screen's read — the portfolio, the policy,
                # the served conversation's session focus and the taxonomy
                # reference, read-only on the work queue (the diagnostics
                # construction). A read failure is a server fact: the
                # route's own 500 posture.
                self._run_on_host_thread(face.goals)
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path == "/api/goals":
                # p-3 W1: the full new combination as the portfolio's next
                # version. The grammar is validated here, fail-closed (an
                # out-of-vocabulary word is a 400 人话, never a silent
                # drop); the store's version discipline rides 200 / 409
                # from the face (an idempotent replay, a CONFLICT 上浮).
                error, goals, weights, assessment, register = (
                    _goal_request_parts(self._read_json_body())
                )
                if error is not None:
                    self._send_json(400, {"error": error})
                    return
                self._run_host_write(
                    lambda: face.goals_save(
                        goals, weights, assessment, register
                    )
                )
                return
            if self.path == "/api/teaching_frequency":
                # p-3 W2: the one policy column. One word inside the
                # implementation-declared four, case-sensitive (the enum's
                # own words); anything else is the 400 below.
                word = _frequency_request_word(self._read_json_body())
                if word is None:
                    self._send_json(400, {"error": _FREQUENCY_GRAMMAR})
                    return
                self._run_host_write(lambda: face.teaching_frequency(word))
                return
            if self.path == "/api/characters":
                # MC-0: one new user-authored card. The grammar is
                # validated here, fail-closed (an unknown field or a
                # missing/empty name is a 400 人话); the store's own
                # refusals ride 409 from the face.
                error, fields = _character_request_parts(
                    self._read_json_body(), name_required=True
                )
                if error is not None or fields is None:
                    self._send_json(400, {"error": error})
                    return
                self._run_host_write(lambda: face.character_create(fields))
                return
            if self.path == "/api/characters/switch":
                # MC-0: the envelope switch — serve this character's
                # conversation from now on (the face opens it lazily
                # here, bound to the card's persona, then re-points).
                payload = self._read_json_body()
                asked = (
                    payload.get("character_id")
                    if isinstance(payload, dict)
                    else None
                )
                if not isinstance(asked, str) or not asked.strip():
                    self._send_json(
                        400,
                        {
                            "error": (
                                'need a JSON body {"character_id": "..."}'
                            )
                        },
                    )
                    return
                self._run_host_write(lambda: face.character_switch(asked))
                return
            if self.path not in (
                "/api/turn",
                "/api/teaching_reply",
                "/api/teach_me",
                "/api/delete",
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
            if self.path == "/api/delete":
                # p-2 grammar: {"scope": <one of the three words>} plus the
                # scope's own key (and nothing else — a key outside the
                # scope's own is a 400, never a silent widening). A
                # CONVERSATION body without a conversation_id names the
                # conversation this face serves: the page never learns its
                # own id, so the face supplies the honest referent. A scope
                # word outside the three — including the deletion
                # vocabulary's other four — is the 400 人话 below; a missing
                # key for a valid scope reaches the controller and comes
                # back as its own VALIDATION_FAILED (200, honestly).
                if not isinstance(payload, dict):
                    self._send_json(
                        400,
                        {
                            "error": (
                                'need a JSON body {"scope": "CONVERSATION"'
                                ' | "LEARNING_TARGET" | "RELATIONSHIP_PAIR",'
                                " plus that scope's own key"
                            )
                        },
                    )
                    return
                scope_word = payload.get("scope")
                scope: DeletionScope | None = None
                if isinstance(scope_word, str):
                    try:
                        scope = DeletionScope(scope_word)
                    except ValueError:
                        scope = None
                if scope not in _DELETE_SCOPE_KEYS:
                    self._send_json(
                        400,
                        {
                            "error": (
                                "此版本不支持该范围："
                                f"{scope_word!r}（只支持 CONVERSATION /"
                                " LEARNING_TARGET / RELATIONSHIP_PAIR）"
                            )
                        },
                    )
                    return
                own_key = _DELETE_SCOPE_KEYS[scope]
                keys: dict[str, str] = {}
                for key in ("conversation_id", "target_id", "persona_id"):
                    value = payload.get(key)
                    if value is None:
                        continue
                    if not isinstance(value, str) or not value.strip():
                        self._send_json(
                            400,
                            {"error": f'"{key}" needs a non-empty string'},
                        )
                        return
                    keys[key] = value
                extra = set(payload) - {"scope", own_key}
                if extra:
                    self._send_json(
                        400,
                        {
                            "error": (
                                f"{scope.value} 只接受 {own_key}；多出的键："
                                + "、".join(sorted(extra))
                            )
                        },
                    )
                    return
                conversation_id = keys.get("conversation_id")
                if scope is DeletionScope.CONVERSATION and (
                    conversation_id is None
                ):
                    conversation_id = face.conversation_id
                final_scope = scope
                self._run_on_host_thread(
                    lambda: face.delete(
                        final_scope,
                        conversation_id,
                        keys.get("target_id"),
                        keys.get("persona_id"),
                    )
                )
                return
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str) or not text.strip():
                self._send_json(
                    400, {"error": 'need a JSON body {"text": "..."}'}
                )
                return
            self._run_on_host_thread(lambda: face.turn(text))

        def _character_path_id(self) -> str | None:
            """The id out of a ``/api/characters/<id>`` path, or ``None``
            when the path is not that shape (the caller answers 404)."""

            prefix = "/api/characters/"
            if not self.path.startswith(prefix):
                return None
            character_id = self.path[len(prefix):]
            if not character_id or "/" in character_id:
                return None
            return character_id

        def do_PUT(self) -> None:
            # MC-0: reword one card. The grammar is the shared one (a name
            # may be reworded but not emptied); at least one field must
            # ride along. The builtin is editable like any other card.
            character_id = self._character_path_id()
            if character_id is None:
                self._send_json(404, {"error": "not found"})
                return
            error, fields = _character_request_parts(
                self._read_json_body(), name_required=False
            )
            if error is not None:
                self._send_json(400, {"error": error})
                return
            if not fields:
                self._send_json(
                    400, {"error": "an update needs at least one field"}
                )
                return
            self._run_host_write(
                lambda: face.character_update(character_id, fields)
            )

        def do_DELETE(self) -> None:
            # MC-0: remove one user-authored card; the builtin is refused
            # (409, the store's AUTHORITY_VIOLATION), an unknown id a 404.
            character_id = self._character_path_id()
            if character_id is None:
                self._send_json(404, {"error": "not found"})
                return
            self._run_host_write(lambda: face.character_delete(character_id))

    return _WebServer(("127.0.0.1", port), Handler, face=face, work=work)


def port_is_serving(port: int) -> bool:
    """True when something already accepts connections on 127.0.0.1:port.

    Windows lets a second ``ThreadingHTTPServer`` bind an in-use loopback
    port silently (``allow_reuse_address`` is SO_REUSEADDR there — a
    hijack permission, not the POSIX TIME_WAIT relief), which is how a
    restart that did not stop the old instance left two runtimes on one
    app.db and killed every turn at the door. A connect probe is the
    cross-platform truth: TIME_WAIT leftovers accept nothing, a live
    listener does. The CLI's ``web`` branch calls this **before**
    ``open_host`` — opening the host bumps the store epoch, which fences
    a live instance's writes even when this start is then refused.
    """

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


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
    cs-1 binds the conversation to the fixed penpal
    (``elc.persona.penpal``) — the same binding the chat command makes, so
    both faces serve the same character; a legacy row that predates the
    binding is adopted (an empty persona is filled, a bound one is never
    overwritten).

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

    Before any of that, the port itself is probed: a second instance on an
    already-serving port refuses with the same :class:`WebOpenError`
    before touching the database (Windows would otherwise let both bind
    silently — the dual-instance incident behind W-7, where two runtimes
    on one app.db answered every turn with an instant 500).
    """

    if port_is_serving(port):
        raise WebOpenError(
            f"port {port} is already serving an elc web instance —"
            " stop the old one first; two instances on one app.db"
            " corrupt each other's turns"
        )

    opened = host.open_conversation(
        ConversationId(conversation), persona_id=PENPAL_PERSONA_ID
    )
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
